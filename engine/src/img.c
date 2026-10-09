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

int img_load(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y)
{
	RECT rect;
	uint32_t raw_size, comp_size;

	img->loaded = 0;
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

	if (img->kind > 1 || img->w == 0)
		return 0;                    /* color solido o imagen vacia: nada que subir */

	raw_size = rd32(file + HEADER_SIZE + PALETTE_BYTES);
	comp_size = rd32(file + HEADER_SIZE + PALETTE_BYTES + 4);
	if (raw_size > SCRATCH_BYTES || (int)raw_size != img->w * img->h) {
		printf("img: tamano invalido %d\n", (int)raw_size);
		return -1;
	}
	if (lz4_decode(file + HEADER_SIZE + PALETTE_BYTES + 8, comp_size, scratch, raw_size) != (int)raw_size) {
		printf("img: error de LZ4\n");
		return -1;
	}

	/* Paleta de 256 entradas en una fila de CLUT */
	setRECT(&rect, 0, clut_y, 256, 1);
	LoadImage(&rect, (const uint32_t *)(file + HEADER_SIZE));
	DrawSync(0);
	/* Indices de 8 bits: 2 pixeles por palabra de VRAM */
	setRECT(&rect, vram_x, vram_y, img->w / 2, img->h);
	LoadImage(&rect, (const uint32_t *)scratch);
	DrawSync(0);
	img->loaded = 1;
	return 0;
}

void img_draw(const Image *img, int layer, int screen_x, int screen_y)
{
	img_draw_flip(img, layer, screen_x, screen_y, 0);
}

/* Cada pieza cabe en una pagina de textura de 256 px; el origen en VRAM puede caer en cualquier palabra */
void img_draw_flip(const Image *img, int layer, int screen_x, int screen_y, int flip)
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
		if (flip) {
			POLY_FT4 *p = (POLY_FT4 *)video_alloc(sizeof(POLY_FT4));
			int x = screen_x + img->full_w - (img->x + col + piece_w);
			int y = screen_y + img->y;

			if (!p)
				return;
			setPolyFT4(p);
			setXY4(p, x, y, x + piece_w, y, x, y + img->h, x + piece_w, y + img->h);
			setUV4(p, u + piece_w - 1, v, u, v, u + piece_w - 1, v + img->h - 1, u, v + img->h - 1);
			setRGB0(p, 128, 128, 128);
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
			setRGB0(s, 128, 128, 128);
			setClut(s, 0, img->clut_y);
			video_add(layer, s);
			/* la pagina de textura va antes del sprite: se agrega despues porque lo agregado despues se dibuja antes */
			video_set_tpage(layer, 1, 0, page_x, img->vram_y);
		}
		col += piece_w;
	}
}
