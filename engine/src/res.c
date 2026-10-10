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
#define GRID_H        32                /* 512 filas: las paletas de las filas 480+ estan en x < 320 (fuera de estas zonas) */
#define BAND_ROWS     16                /* una imagen no puede cruzar la fila 256 de VRAM */
#define CLUT_ROWS     16

typedef struct {
	uint8_t used, has_cells, region;
	int id;
	Image img;
	int gx, gy, gw, gh;
	int clut_bit;
	uint32_t last_use;
	uint32_t last_draw;                   /* ultimo cuadro en que se pidio para dibujar (0: solo precargada) */
} Entry;

static uint8_t file_buf[FILE_BYTES] __attribute__((aligned(4)));
static Entry entries[MAX_ENTRIES];
static uint8_t grid[2][GRID_H][GRID_W];     /* 0 libre, si no indice de entrada + 1 */
static uint16_t clut_used;
static uint32_t clock_now = 1, draw_clock = 2;
volatile uint32_t res_fail_read, res_fail_vram, res_fail_clut;   /* contadores para la prueba automatica */
volatile uint32_t res_snap_skip;                                  /* transiciones sin copia por falta de VRAM */
volatile uint32_t res_fail_log[16];                               /* ultimas imagenes que no cupieron (+0x10000: paletas) */
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

void res_tick(void)
{
	draw_clock++;
}

/* Desaloja la entrada menos usada que no pertenece a la escena actual. Con for_draw tambien puede desalojar una de
 * la escena actual que no se dibujo en este cuadro ni en el anterior (cuadros de animacion ya pasados o precargados).
 * Devuelve 0 si no hay ninguna. */
static int evict_one(int for_draw)
{
	int i, best = -1;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].last_use < clock_now && (best < 0 || entries[i].last_use < entries[best].last_use))
			best = i;
	if (best < 0 && for_draw)
		for (i = 0; i < MAX_ENTRIES; i++)
			if (entries[i].used && entries[i].last_draw + 1 < draw_clock &&
			    (best < 0 || entries[i].last_draw < entries[best].last_draw))
				best = i;
	if (best < 0)
		return 0;
	free_entry(&entries[best]);
	return 1;
}

static Entry *new_entry(int for_draw)
{
	int i;

	for (;;) {
		for (i = 0; i < MAX_ENTRIES; i++)
			if (!entries[i].used)
				return &entries[i];
		if (!evict_one(for_draw))
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

static const Image *load_image(int image_id, int for_draw);

/* ---------------------------------------------------------------- cache de archivos en RAM (D7)
 * Cuando ya hay que pausar la musica para leer, se aprovecha la pausa para traer tambien las imagenes de las escenas
 * que vienen; despues se descomprimen a VRAM desde aqui sin tocar el CD (sin otro corte de musica). Los archivos
 * contiguos en el disco se leen de una sola vez. */
#define CACHE_BYTES (320 * 1024)
#define MAX_CACHED 96
#define MAX_PREFETCH 32
#define MAX_GAP_SECTORS 4                /* se leen de paso huecos chicos entre archivos para no hacer otra busqueda */

static uint8_t cache_buf[CACHE_BYTES] __attribute__((aligned(4)));
static struct {
	int id, off, size;
} cached[MAX_CACHED];
static int cached_count, cache_used;

static const uint8_t *cache_lookup(int image_id, int *size)
{
	int i;

	for (i = 0; i < cached_count; i++)
		if (cached[i].id == image_id) {
			*size = cached[i].size;
			return cache_buf + cached[i].off;
		}
	return 0;
}

static int in_list(int id, const uint16_t *ids, int n)
{
	int i;

	for (i = 0; i < n; i++)
		if (ids[i] == id)
			return 1;
	return 0;
}

void res_prefetch(const uint16_t *ids, int n)
{
	int want[MAX_PREFETCH], lba[MAX_PREFETCH], size[MAX_PREFETCH], count = 0, i, j, kept = 0, used = 0;
	char path[24];

	/* 1. se quedan (compactadas al inicio) las que se van a seguir necesitando */
	for (i = 0; i < cached_count; i++)
		if (in_list(cached[i].id, ids, n)) {
			int bytes = (cached[i].size + 2047) & ~2047;

			if (cached[i].off != used)
				memmove(cache_buf + used, cache_buf + cached[i].off, bytes);
			cached[kept] = cached[i];
			cached[kept].off = used;
			used += bytes;
			kept++;
		}
	cached_count = kept;
	cache_used = used;

	/* 2. las que faltan (ni en VRAM ni aqui), ordenadas por posicion en el disco */
	for (i = 0; i < n && count < MAX_PREFETCH; i++) {
		int l, s;

		if (res_peek(ids[i]) || cache_lookup(ids[i], &s))
			continue;
		sprintf(path, "\\DATA\\I%04d.IMG", ids[i]);
		if (cd_find(path, &l, &s) != 0)
			continue;
		for (j = count; j > 0 && lba[j - 1] > l; j--) {
			want[j] = want[j - 1];
			lba[j] = lba[j - 1];
			size[j] = size[j - 1];
		}
		want[j] = ids[i];
		lba[j] = l;
		size[j] = s;
		count++;
	}

	/* 3. tramos contiguos de una sola lectura, mientras quepan */
	for (i = 0; i < count;) {
		int first = lba[i], end = lba[i] + (size[i] + 2047) / 2048, k = i + 1, sectors;

		while (k < count && lba[k] >= end && lba[k] - end <= MAX_GAP_SECTORS &&
		       (lba[k] + (size[k] + 2047) / 2048 - first) * 2048 <= CACHE_BYTES - cache_used)
			end = lba[k] + (size[k] + 2047) / 2048, k++;
		sectors = end - first;
		if (sectors * 2048 > CACHE_BYTES - cache_used || cached_count + (k - i) > MAX_CACHED)
			break;
		if (cd_read_sectors(first, sectors, cache_buf + cache_used) != 0)
			break;
		for (j = i; j < k; j++) {
			cached[cached_count].id = want[j];
			cached[cached_count].off = cache_used + (lba[j] - first) * 2048;
			cached[cached_count].size = size[j];
			cached_count++;
		}
		cache_used += sectors * 2048;
		i = k;
	}
}

#define SNAP_GY 16                      /* copia de pantalla (320 x 192 filas en la zona de fondos): lugar preferido */
#define SNAP_GH 12
#define SNAP_MARK 0xFF

static int snap_gy = SNAP_GY;

/* Costo de poner la copia en las filas gy..gy+SNAP_GH: lo que se dibujo en el ultimo cuadro cuenta mucho mas que lo
 * que solo esta guardado */
static int snapshot_cost(int gy)
{
	int i, cost = 0;

	for (i = 0; i < MAX_ENTRIES; i++) {
		const Entry *e = &entries[i];

		if (e->used && e->has_cells && e->region == 1 && e->gy < gy + SNAP_GH && e->gy + e->gh > gy)
			cost += e->gw * e->gh * (e->last_draw + 1 >= draw_clock ? 1000 : 1);
	}
	return cost;
}

static uint8_t trial[2][GRID_H][GRID_W];

/* Ocupa en `trial` un rectangulo libre de gw x gh celdas (en cualquier zona, sin cruzar bandas) */
static int trial_place(int gw, int gh)
{
	int region, band, x, y, i, j;

	for (region = 0; region < 2; region++)
		for (band = 0; band < GRID_H; band += BAND_ROWS) {
			int band_end = band + BAND_ROWS < GRID_H ? band + BAND_ROWS : GRID_H;

			for (y = band; y + gh <= band_end; y++)
				for (x = 0; x + gw <= GRID_W; x++) {
					int ok = 1;

					for (j = y; j < y + gh && ok; j++)
						for (i = x; i < x + gw && ok; i++)
							ok = !trial[region][j][i];
					if (!ok)
						continue;
					for (j = y; j < y + gh; j++)
						memset(&trial[region][j][x], 1, gw);
					return 1;
				}
		}
	return 0;
}

/* Las imagenes en pantalla que la copia en las filas gy.. desalojaria, se pueden volver a acomodar en el resto
 * (contando como libre lo que no esta en pantalla)? */
static int fits_elsewhere(int gy)
{
	uint8_t moved[MAX_ENTRIES];
	int region, x, y, i;

	for (region = 0; region < 2; region++)
		for (y = 0; y < GRID_H; y++)
			for (x = 0; x < GRID_W; x++) {
				int c = grid[region][y][x];

				if (region == 1 && y >= gy && y < gy + SNAP_GH)
					trial[region][y][x] = 1;
				else
					trial[region][y][x] = c != 0 && (c == SNAP_MARK || entries[c - 1].last_draw + 1 >= draw_clock);
			}
	for (i = 0; i < MAX_ENTRIES; i++) {
		const Entry *e = &entries[i];

		moved[i] = e->used && e->has_cells && e->region == 1 && e->gy < gy + SNAP_GH && e->gy + e->gh > gy &&
		           e->last_draw + 1 >= draw_clock;
		if (moved[i])                    /* sus celdas fuera de la franja quedan libres al desalojarla */
			for (y = e->gy; y < e->gy + e->gh; y++)
				if (y < gy || y >= gy + SNAP_GH)
					memset(&trial[1][y][e->gx], 0, e->gw);
	}
	for (;;) {                           /* de la mas grande a la mas chica */
		int best = -1;

		for (i = 0; i < MAX_ENTRIES; i++)
			if (moved[i] && (best < 0 || entries[i].gw * entries[i].gh > entries[best].gw * entries[best].gh))
				best = i;
		if (best < 0)
			return 1;
		moved[best] = 0;
		if (!trial_place(entries[best].gw, entries[best].gh))
			return 0;
	}
}

int res_reserve_snapshot(int *vram_x, int *vram_y)
{
	/* filas posibles: dentro de una banda (la copia no puede cruzar la fila 256 de VRAM) */
	static const int8_t rows[] = { SNAP_GY, GRID_H - SNAP_GH, 0, BAND_ROWS - SNAP_GH };
	int i, x, y, best = 0, best_cost = -1;

	/* lo que esta en pantalla y se quita se vuelve a cargar al dibujar: solo se acepta una franja si hay lugar para
	 * eso; si ninguna sirve, mejor sin copia */
	for (i = 0; i < (int)sizeof(rows); i++) {
		int cost = snapshot_cost(rows[i]);

		if ((best_cost < 0 || cost < best_cost) && (cost < 1000 || fits_elsewhere(rows[i]))) {
			best = rows[i];
			best_cost = cost;
		}
	}
	if (best_cost < 0) {
		res_snap_skip++;
		return 0;
	}
	for (i = 0; i < MAX_ENTRIES; i++) {
		Entry *e = &entries[i];

		if (e->used && e->has_cells && e->region == 1 && e->gy < best + SNAP_GH && e->gy + e->gh > best)
			free_entry(e);
	}
	for (y = best; y < best + SNAP_GH; y++)
		for (x = 0; x < GRID_W; x++)
			grid[1][y][x] = SNAP_MARK;
	snap_gy = best;
	*vram_x = VRAM_BG_X;
	*vram_y = best * CELL_ROWS;
	return 1;
}

void res_release_snapshot(void)
{
	int x, y;

	for (y = snap_gy; y < snap_gy + SNAP_GH; y++)
		for (x = 0; x < GRID_W; x++)
			if (grid[1][y][x] == SNAP_MARK)
				grid[1][y][x] = 0;
	failed_count = 0;                /* lo que no cupo durante la transicion se vuelve a intentar */
}

const Image *res_get(int image_id)
{
	int i;
	const Image *img;

	for (i = 0; i < failed_count; i++)
		if (failed[i] == image_id)
			return 0;
	img = load_image(image_id, 1);
	if (!img && failed_count < 16)
		failed[failed_count++] = image_id;
	return img;
}

void res_touch(int image_id)
{
	int i;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].id == image_id)
			entries[i].last_use = clock_now;
}

void res_preload(int image_id)
{
	load_image(image_id, 0);
}

const Image *res_peek(int image_id)
{
	int i;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].id == image_id)
			return &entries[i].img;
	return 0;
}

/* for_draw = 0: precarga opcional; solo usa espacio libre o de escenas anteriores y no cuenta como falla */
static const Image *load_image(int image_id, int for_draw)
{
	char path[24];
	int i, size, kind, w, h, region, gw, gh, big, gx = 0, gy = 0;
	Entry *e;
	const uint8_t *data;

	for (i = 0; i < MAX_ENTRIES; i++)
		if (entries[i].used && entries[i].id == image_id) {
			entries[i].last_use = clock_now;
			if (for_draw)
				entries[i].last_draw = draw_clock;
			return &entries[i].img;
		}
	sprintf(path, "\\DATA\\I%04d.IMG", image_id);

	data = cache_lookup(image_id, &size);         /* ya leida de antemano: sin tocar el CD */
	if (!data) {
		size = cd_read_file(path, file_buf, FILE_BYTES);
		data = file_buf;
	}
	if (size < 24 + 512 + 8) {
		res_fail_read++;
		printf("res: no se pudo leer %s\n", path);
		return 0;
	}
	kind = data[4];
	w = data[14] | (data[15] << 8);
	h = data[16] | (data[17] << 8);
	region = kind == 0 ? 1 : 0;
	gw = (w / 2 + CELL_WORDS - 1) / CELL_WORDS;
	gh = (h + CELL_ROWS - 1) / CELL_ROWS;
	/* un fondo que no cabe en una banda de VRAM se queda en RAM y en VRAM solo ocupa su ventana visible */
	big = kind == 0 && (gw > GRID_W || gh > GRID_H - BAND_ROWS);
	if (big) {
		gw = (BIG_WIN_W / 2 + CELL_WORDS - 1) / CELL_WORDS;
		gh = (BIG_WIN_H + CELL_ROWS - 1) / CELL_ROWS;
	}

	e = new_entry(for_draw);
	if (!e)
		return 0;
	memset(e, 0, sizeof(*e));
	e->clut_bit = -1;
	e->id = image_id;
	e->last_use = clock_now;
	e->last_draw = for_draw ? draw_clock : 0;

	if (kind <= 1 && w > 0) {
		/* lo que no entra en su zona (sprites o fondos) usa el hueco libre de la otra antes de desalojar */
		for (;;) {
			if (find_rect(region, gw, gh, &gx, &gy))
				break;
			if (find_rect(1 - region, gw, gh, &gx, &gy)) {
				region = 1 - region;
				break;
			}
			if (!evict_one(for_draw)) {
				if (!for_draw)
					return 0;
				res_fail_log[(res_fail_vram + res_fail_clut) & 15] = (uint32_t)image_id;
				res_fail_vram++;
				printf("res: sin espacio en VRAM para %s\n", path);
				return 0;
			}
		}
		e->clut_bit = take_clut();
		while (e->clut_bit < 0 && evict_one(for_draw))
			e->clut_bit = take_clut();
		if (e->clut_bit < 0) {
			if (!for_draw)
				return 0;
			res_fail_log[(res_fail_vram + res_fail_clut) & 15] = (uint32_t)image_id | 0x10000;
			res_fail_clut++;
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
	if ((big ? img_load_big : img_load)(&e->img, data, size, region_x[region] + gx * CELL_WORDS, gy * CELL_ROWS,
	                                    CLUT_BG_Y + (e->clut_bit >= 0 ? e->clut_bit : 0)) != 0) {
		free_entry(e);
		return 0;
	}
	return &e->img;
}
