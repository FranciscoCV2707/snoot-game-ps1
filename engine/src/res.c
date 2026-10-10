#include <stdio.h>
#include <string.h>
#include "cd.h"
#include "img.h"
#include "res.h"
#include "video.h"

#define FILE_BYTES    (172 * 1024)      /* el mayor archivo de imagen (stairs) ocupa 164 KB */
#define MAX_ENTRIES   28
#define CELL_WORDS    16
#define CELL_ROWS     16
#define GRID_W        20                /* 320 palabras */
#define GRID_H        30                /* 480 filas */
#define BAND_ROWS     16                /* una imagen no puede cruzar la fila 256 de VRAM */
#define CLUT_ROWS     16

typedef struct {
	uint8_t used, has_cells, region;
	int id;
	Image img;
	int gx, gy, gw, gh;
	int clut_bit;
	uint32_t last_use;
} Entry;

static uint8_t file_buf[FILE_BYTES] __attribute__((aligned(4)));
static Entry entries[MAX_ENTRIES];
static uint8_t grid[2][GRID_H][GRID_W];     /* 0 libre, si no indice de entrada + 1 */
static uint16_t clut_used;
static uint32_t clock_now = 1;
static int failed[16], failed_count;      /* imagenes que no se pudieron cargar en esta escena */

static const int region_x[2] = { VRAM_SPRITE_X, VRAM_BG_X };

void res_new_scene(void)
{
	clock_now++;
	failed_count = 0;
}

static int cell_free(int region, int gx, int gy, int gw, int gh)
{
	int x, y;

	for (y = gy; y < gy + gh; y++)
		for (x = gx; x < gx + gw; x++)
			if (grid[region][y][x])
				return 0;
	return 1;
}

static int find_rect(int region, int gw, int gh, int *out_x, int *out_y)
{
	int band, y, x;

	if (gw > GRID_W || gh > BAND_ROWS)
		return 0;
	for (band = 0; band < GRID_H; band += BAND_ROWS) {
		int band_end = band + BAND_ROWS < GRID_H ? band + BAND_ROWS : GRID_H;

		for (y = band; y + gh <= band_end; y++)
			for (x = 0; x + gw <= GRID_W; x++)
				if (cell_free(region, x, y, gw, gh)) {
					*out_x = x;
					*out_y = y;
					return 1;
				}
	}
	return 0;
}

static void free_entry(Entry *e)
{
	int x, y;

	if (e->has_cells)
		for (y = e->gy; y < e->gy + e->gh; y++)
			for (x = e->gx; x < e->gx + e->gw; x++)
				grid[e->region][y][x] = 0;
	if (e->clut_bit >= 0)
		clut_used &= ~(1 << e->clut_bit);
	e->used = 0;
}

/* Desaloja la entrada menos usada que no pertenece a la escena actual. Devuelve 0 si no hay ninguna. */
static int evict_one(void)
{
	int i, best = -1;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].last_use < clock_now && (best < 0 || entries[i].last_use < entries[best].last_use))
			best = i;
	if (best < 0)
		return 0;
	free_entry(&entries[best]);
	return 1;
}

static Entry *new_entry(void)
{
	int i;

	for (;;) {
		for (i = 0; i < MAX_ENTRIES; i++)
			if (!entries[i].used)
				return &entries[i];
		if (!evict_one())
			return 0;
	}
}

static int take_clut(void)
{
	int i;

	for (i = 0; i < CLUT_ROWS; i++)
		if (!(clut_used & (1 << i))) {
			clut_used |= 1 << i;
			return i;
		}
	return -1;
}

static const Image *load_image(int image_id);

#define SNAP_GY 16                      /* copia de pantalla: banda baja de la zona de fondos, 320 x 192 filas */
#define SNAP_GH 12
#define SNAP_MARK 0xFF

void res_reserve_snapshot(int *vram_x, int *vram_y)
{
	int i, x, y;

	for (i = 0; i < MAX_ENTRIES; i++) {
		Entry *e = &entries[i];

		if (e->used && e->has_cells && e->region == 1 && e->gy < SNAP_GY + SNAP_GH && e->gy + e->gh > SNAP_GY)
			free_entry(e);
	}
	for (y = SNAP_GY; y < SNAP_GY + SNAP_GH; y++)
		for (x = 0; x < GRID_W; x++)
			grid[1][y][x] = SNAP_MARK;
	*vram_x = VRAM_BG_X;
	*vram_y = SNAP_GY * CELL_ROWS;
}

void res_release_snapshot(void)
{
	int x, y;

	for (y = SNAP_GY; y < SNAP_GY + SNAP_GH; y++)
		for (x = 0; x < GRID_W; x++)
			if (grid[1][y][x] == SNAP_MARK)
				grid[1][y][x] = 0;
}

const Image *res_get(int image_id)
{
	int i;
	const Image *img;

	for (i = 0; i < failed_count; i++)
		if (failed[i] == image_id)
			return 0;
	img = load_image(image_id);
	if (!img && failed_count < 16)
		failed[failed_count++] = image_id;
	return img;
}

const Image *res_peek(int image_id)
{
	int i;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].id == image_id)
			return &entries[i].img;
	return 0;
}

static const Image *load_image(int image_id)
{
	char path[24];
	int i, size, kind, w, h, region, gw, gh, big, gx = 0, gy = 0;
	Entry *e;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].id == image_id) {
			entries[i].last_use = clock_now;
			return &entries[i].img;
		}

	sprintf(path, "\\DATA\\I%04d.IMG", image_id);
	size = cd_read_file(path, file_buf, FILE_BYTES);
	if (size < 24 + 512 + 8) {
		printf("res: no se pudo leer %s\n", path);
		return 0;
	}
	kind = file_buf[4];
	w = file_buf[14] | (file_buf[15] << 8);
	h = file_buf[16] | (file_buf[17] << 8);
	region = kind == 0 ? 1 : 0;
	gw = (w / 2 + CELL_WORDS - 1) / CELL_WORDS;
	gh = (h + CELL_ROWS - 1) / CELL_ROWS;
	/* un fondo que no cabe en una banda de VRAM se queda en RAM y en VRAM solo ocupa su ventana visible */
	big = kind == 0 && (gw > GRID_W || gh > GRID_H - BAND_ROWS);
	if (big) {
		gw = (BIG_WIN_W / 2 + CELL_WORDS - 1) / CELL_WORDS;
		gh = (BIG_WIN_H + CELL_ROWS - 1) / CELL_ROWS;
	}

	e = new_entry();
	if (!e)
		return 0;
	memset(e, 0, sizeof(*e));
	e->clut_bit = -1;
	e->id = image_id;
	e->last_use = clock_now;

	if (kind <= 1 && w > 0) {
		/* lo que no entra en su zona (sprites o fondos) usa el hueco libre de la otra antes de desalojar */
		for (;;) {
			if (find_rect(region, gw, gh, &gx, &gy))
				break;
			if (find_rect(1 - region, gw, gh, &gx, &gy)) {
				region = 1 - region;
				break;
			}
			if (!evict_one()) {
				printf("res: sin espacio en VRAM para %s\n", path);
				return 0;
			}
		}
		e->clut_bit = take_clut();
		while (e->clut_bit < 0 && evict_one())
			e->clut_bit = take_clut();
		if (e->clut_bit < 0) {
			printf("res: sin paletas libres\n");
			return 0;
		}
		e->has_cells = 1;
		e->region = (uint8_t)region;
		e->gx = gx;
		e->gy = gy;
		e->gw = gw;
		e->gh = gh;
		for (i = gy; i < gy + gh; i++)
			memset(&grid[region][i][gx], (int)(e - entries) + 1, gw);
	}
	e->used = 1;
	if ((big ? img_load_big : img_load)(&e->img, file_buf, size, region_x[region] + gx * CELL_WORDS, gy * CELL_ROWS,
	                                    CLUT_BG_Y + (e->clut_bit >= 0 ? e->clut_bit : 0)) != 0) {
		free_entry(e);
		return 0;
	}
	return &e->img;
}
