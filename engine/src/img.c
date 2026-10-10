#include <stdio.h>
#include <string.h>
#include <psxgpu.h>
#include "img.h"
#include "lz4.h"
#include "video.h"

#define HEADER_SIZE   24
#define PALETTE_BYTES 512
#define SCRATCH_BYTES (96 * 1024)

static uint8_t scratch[SCRATCH_BYTES] __attribute__((aligned(4)));

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

/*
 * El GPU solo cierra una transferencia si recibe un numero entero de palabras. Con ancho en palabras impar y alto impar
 * el total de medias palabras es impar y el GPU se queda esperando un dato que nunca llega. En ese caso la ultima fila
 * se sube aparte con una media palabra de relleno, que cae dentro de la celda reservada (el ancho en palabras es impar).
 */
static void upload_indices(int vram_x, int vram_y, int width_words, int height)
{
	static uint8_t last_row[1024] __attribute__((aligned(4)));
	RECT rect;
	int rows = height;

	if ((width_words * height) & 1)
		rows = height - 1;
	if (rows > 0) {
		setRECT(&rect, vram_x, vram_y, width_words, rows);
		LoadImage(&rect, (const uint32_t *)scratch);
		DrawSync(0);
	}
	if (rows != height) {
		memcpy(last_row, scratch + rows * width_words * 2, width_words * 2);
		memset(last_row + width_words * 2, 0, 2);
		setRECT(&rect, vram_x, vram_y + rows, width_words + 1, 1);
		LoadImage(&rect, (const uint32_t *)last_row);
		DrawSync(0);
	}
}

static int read_header(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y)
{
	img->loaded = 0;
	img->big = 0;
	if (file_size < HEADER_SIZE + PALETTE_BYTES + 8 || file[0] != 'I' || file[1] != 'M' || file[2] != 'G' || file[3] != '1')
		return -1;
	img->kind = file[4];
	img->flags = file[5];
	img->full_w = rd16(file + 6);
	img->full_h = rd16(file + 8);
	img->x = rd16(file + 10);
	img->y = rd16(file + 12);
	img->w = rd16(file + 14);
	img->h = rd16(file + 16);
	memcpy(img->solid, file + 18, 4);
	img->vram_x = vram_x;
	img->vram_y = vram_y;
	img->clut_y = clut_y;
	return 0;
}

/* Descomprime los indices de 8 bits en dst y sube la paleta de 256 entradas a su fila de CLUT */
static int unpack(const Image *img, const uint8_t *file, uint8_t *dst, int dst_bytes)
{
	RECT rect;
	uint32_t raw_size = rd32(file + HEADER_SIZE + PALETTE_BYTES);
	uint32_t comp_size = rd32(file + HEADER_SIZE + PALETTE_BYTES + 4);

	if ((int)raw_size > dst_bytes || (int)raw_size != img->w * img->h) {
		printf("img: tamano invalido %d\n", (int)raw_size);
		return -1;
	}
	if (lz4_decode(file + HEADER_SIZE + PALETTE_BYTES + 8, comp_size, dst, raw_size) != (int)raw_size) {
		printf("img: error de LZ4\n");
		return -1;
	}
	setRECT(&rect, 0, img->clut_y, 256, 1);
	LoadImage(&rect, (const uint32_t *)(file + HEADER_SIZE));
	DrawSync(0);
	return 0;
}

int img_load(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y)
{
	if (read_header(img, file, file_size, vram_x, vram_y, clut_y) != 0)
		return -1;
	if (img->kind > 1 || img->w == 0)
		return 0;                    /* color solido o imagen vacia: nada que subir */
	if (unpack(img, file, scratch, SCRATCH_BYTES) != 0)
		return -1;
	/* Indices de 8 bits: 2 pixeles por palabra de VRAM */
	upload_indices(vram_x, vram_y, img->w / 2, img->h);
	img->loaded = 1;
	return 0;
}

/* ---------------------------------------------------------------- fondos grandes */
#define BIG_BYTES (512 * 1024)       /* el mayor (stairs, 1328x383) ocupa 497 KB */

static uint8_t big_raw[BIG_BYTES] __attribute__((aligned(4)));
static const Image *big_owner;       /* imagen cuyos indices estan en big_raw */
static const Image *win_owner;       /* imagen cuya ventana esta en VRAM, y su esquina dentro del bitmap */
static int win_x, win_y;

int img_load_big(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y)
{
	if (read_header(img, file, file_size, vram_x, vram_y, clut_y) != 0 || img->kind != 0 || img->w == 0)
		return -1;
	if (unpack(img, file, big_raw, BIG_BYTES) != 0)
		return -1;
	big_owner = img;
	win_owner = 0;
	img->big = 1;
	img->loaded = 1;
	return 0;
}

void img_draw_big(const Image *img, int layer, int screen_x, int screen_y)
{
	Image win;
	int ox, oy, cw, ch, row;

	if (!img->loaded || img != big_owner)
		return;
	cw = img->w < BIG_WIN_W ? img->w : BIG_WIN_W;
	ch = img->h < BIG_WIN_H ? img->h : BIG_WIN_H;
	/* esquina de la ventana dentro del bitmap: la parte de la imagen que cae en pantalla */
	ox = -screen_x - img->x;
	oy = -screen_y - img->y + VIEW_Y;
	if (ox > img->w - cw)
		ox = img->w - cw;
	if (oy > img->h - ch)
		oy = img->h - ch;
	if (ox < 0)
		ox = 0;
	if (oy < 0)
		oy = 0;

	if (win_owner != img || ox != win_x || oy != win_y) {
		for (row = 0; row < ch; row++)
			memcpy(scratch + row * cw, big_raw + (oy + row) * img->w + ox, cw);
		upload_indices(img->vram_x, img->vram_y, cw / 2, ch);
		win_owner = img;
		win_x = ox;
		win_y = oy;
	}
	win = *img;
	win.big = 0;
	win.x = 0;
	win.y = 0;
	win.w = win.full_w = cw;
	win.h = win.full_h = ch;
	img_draw(&win, layer, screen_x + img->x + ox, screen_y + img->y + oy);
}

void img_draw(const Image *img, int layer, int screen_x, int screen_y)
{
	img_draw_ex(img, layer, screen_x, screen_y, 0, 64, 128, 128, 128);
}

void img_draw_flip(const Image *img, int layer, int screen_x, int screen_y, int flip)
{
	img_draw_ex(img, layer, screen_x, screen_y, flip, 64, 128, 128, 128);
}

/* Cada pieza cabe en una pagina de textura de 256 px; el origen en VRAM puede caer en cualquier palabra.
 * Con espejo o zoom cada pieza es un POLY_FT4 (la GPU escala la textura); si no, un SPRT. */
void img_draw_ex(const Image *img, int layer, int screen_x, int screen_y, int flip, int zoom, int r, int g, int b)
{
	int col = 0;

	if (!img->loaded)
		return;
	while (col < img->w) {
		int word_x = img->vram_x + col / 2;
		int page_x = word_x & ~63;
		int u = (word_x - page_x) * 2;
		int piece_w = img->w - col;
		int v = img->vram_y & 255;

		if (piece_w > 256 - u)
			piece_w = 256 - u;
		if (flip || zoom != 64) {
			POLY_FT4 *p = (POLY_FT4 *)video_alloc(sizeof(POLY_FT4));
			int lx = flip ? img->full_w - (img->x + col + piece_w) : img->x + col;
			int x0 = screen_x + lx * zoom / 64, x1 = screen_x + (lx + piece_w) * zoom / 64;
			int y0 = screen_y + img->y * zoom / 64, y1 = screen_y + (img->y + img->h) * zoom / 64;
			int ua = flip ? u + piece_w - 1 : u, ub = flip ? u : u + piece_w - 1;

			if (!p)
				return;
			setPolyFT4(p);
			setXY4(p, x0, y0, x1, y0, x0, y1, x1, y1);
			setUV4(p, ua, v, ub, v, ua, v + img->h - 1, ub, v + img->h - 1);
			setRGB0(p, r, g, b);
			setSemiTrans(p, img->flags & IMG_TRANSLUCENT);
			p->clut = getClut(0, img->clut_y);
			p->tpage = getTPage(1, 0, page_x, img->vram_y);
			video_add(layer, p);
		} else {
			SPRT *s = (SPRT *)video_alloc(sizeof(SPRT));

			if (!s)
				return;
			setSprt(s);
			setXY0(s, screen_x + img->x + col, screen_y + img->y);
			setWH(s, piece_w, img->h);
			setUV0(s, u, v);
			setRGB0(s, r, g, b);
			setSemiTrans(s, img->flags & IMG_TRANSLUCENT);
			setClut(s, 0, img->clut_y);
			video_add(layer, s);
			/* la pagina de textura va antes del sprite: se agrega despues porque lo agregado despues se dibuja antes */
			video_set_tpage(layer, 1, 0, page_x, img->vram_y);
		}
		col += piece_w;
	}
}
