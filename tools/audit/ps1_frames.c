/*
 * Arnes de PC para la auditoria visual: ejecuta vm.c y res.c del motor con la misma logica de escena que main.c y
 * escribe, por cada linea de dialogo, la lista de imagenes que la PS1 dibujaria (de atras hacia adelante).
 * Las decisiones las elige quien lo controla por stdin (tools/audit/compare.py).
 *
 * Salida: "SAY ch local gid", "D imagen x y flip" por imagen, "E"; "MENU n local..." (espera el indice por stdin);
 * "FAIL imagen"; "END".
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "vm.h"
#include "res.h"
#include "opcodes.h"
#include "scene.h"

#define SCREEN_W 320
#define VIEW_H 180

static char root[512];
static uint8_t chbuf[256 * 1024];
static int16_t pos_x[64], pos_y[64];
static int pos_count;

int cd_read_file(const char *path, void *buf, int buf_bytes)
{
	char p[600];
	int n, id;
	FILE *f;
	const char *q = strrchr(path, '\\');

	if (!q || sscanf(q + 2, "%d", &id) != 1)
		return -1;
	sprintf(p, "%s/IMG/I%04d.IMG", root, id);
	f = fopen(p, "rb");
	if (!f)
		return -1;
	n = (int)fread(buf, 1, buf_bytes, f);
	fclose(f);
	return n;
}

int img_load(Image *img, const uint8_t *file, int sz, int vx, int vy, int cy)
{
	(void)sz;
	img->kind = file[4];
	img->full_w = file[6] | (file[7] << 8);
	img->full_h = file[8] | (file[9] << 8);
	img->x = file[10] | (file[11] << 8);
	img->y = file[12] | (file[13] << 8);
	img->w = file[14] | (file[15] << 8);
	img->h = file[16] | (file[17] << 8);
	img->big = 0;
	memcpy(img->solid, file + 18, 4);
	img->vram_x = vx;
	img->vram_y = vy;
	img->clut_y = cy;
	img->loaded = 1;
	return 0;
}

int img_load_big(Image *img, const uint8_t *file, int sz, int vx, int vy, int cy)
{
	int r = img_load(img, file, sz, vx, vy, cy);

	img->big = 1;
	return r;
}

static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t rd32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

static int loader(void *u, int ch, VmChapter *o)
{
	char p[600];
	FILE *f;

	(void)u;
	sprintf(p, "%s/SCRIPT/C%02d.VNB", root, ch);
	f = fopen(p, "rb");
	if (!f) {
		sprintf(p, "%s/SCRIPT/STORY.VNB", root);
		f = fopen(p, "rb");
	}
	if (!f)
		return -1;
	fread(chbuf, 1, sizeof chbuf, f);
	fclose(f);
	o->code = chbuf + 32;
	o->code_size = rd32(chbuf + 8);
	o->text_base = rd32(chbuf + 12);
	o->text_count = rd16(chbuf + 16);
	o->anim_count = rd16(chbuf + 18);
	o->anims = chbuf + rd32(chbuf + 24);
	return 0;
}

static Vm vm;
static int dirty;

static void notify(void *u, int op, const int32_t *a, int n)
{
	(void)u; (void)a; (void)n;
	if (op == OP_SCENE || op == OP_SHOW || op == OP_HIDE || op == OP_BACKGROUND || op == OP_ORDER)
		dirty = 1;
}

/* Fondo: la posicion final de su Pan (la captura de Ren'Py se toma cuando la escena ya se asento) */
static void bg_align(int *xa, int *ya)
{
	const uint8_t *anim = scene_anim(&vm, vm.bg_anim & 0x7FFF);

	*xa = 128;
	*ya = 256;
	if (anim && anim[0]) {
		const uint8_t *k = anim + 3 + 15 * (anim[0] - 1);

		*xa = (int16_t)rd16(k + 2);
		*ya = (int16_t)rd16(k + 4);
	}
}

static int covers_view(const Image *img, const VmSprite *s)
{
	return img->kind == 0 && !img->big && !s->anim && img->x == 0 && img->y == 0 &&
	       img->w >= SCREEN_W && img->h >= VIEW_H && img->full_w == img->w && img->full_h == img->h;
}

static const Image *get(int id)
{
	const Image *img = res_get(id);

	if (!img)
		printf("FAIL %d\n", id);
	return img;
}

static void sync(void)
{
	const VmSprite *order[VM_MAX_SPRITES];
	uint16_t extra[SCENE_MAX_EVENTS];
	int rank, i, n, count, first = 0, covered = 0;

	if (!dirty)
		return;
	dirty = 0;
	res_new_scene();
	count = scene_sorted(&vm, order);
	if (vm.bg)
		res_touch(vm.bg);
	for (rank = 0; rank < count; rank++)
		res_touch(order[rank]->image);
	for (rank = count - 1; rank >= 0 && !covered; rank--) {
		const Image *img = get(order[rank]->image);

		first = rank;
		covered = img && covers_view(img, order[rank]);
	}
	if (vm.bg && !covered)
		get(vm.bg);
	/* como el motor: las imagenes futuras de las animaciones solo si sobra VRAM (sin avisar si no caben) */
	for (rank = count - 1; rank >= first; rank--) {
		n = scene_event_images(&vm, order[rank], extra, SCENE_MAX_EVENTS);
		for (i = 0; i < n; i++)
			res_preload(extra[i]);
	}
}

/* Lo mismo que draw_scene, pero de atras hacia adelante.
 * "D imagen x y espejo zoom r g b" por imagen y "R modo pasadas r g b" por color solido (ver scene.h). */
static void frame(void)
{
	const VmSprite *order[VM_MAX_SPRITES];
	int n = scene_sorted(&vm, order), rank, first = 0, draw_bg = 1, xa, ya;

	for (rank = n - 1; rank >= 0; rank--) {
		const Image *img = res_peek(order[rank]->image);

		if (img && covers_view(img, order[rank])) {
			first = rank;
			draw_bg = 0;
			break;
		}
	}
	if (draw_bg && vm.bg) {
		const Image *bg = res_peek(vm.bg);

		if (bg && bg->kind == 2) {
			printf("R 0 1 %d %d %d\n", bg->solid[0], bg->solid[1], bg->solid[2]);
		} else if (bg) {
			bg_align(&xa, &ya);
			printf("D %d %d %d %d 64 128 128 128\n", vm.bg, ((SCREEN_W - bg->full_w) * xa) / 256,
			       ((VIEW_H - bg->full_h) * ya) / 256, vm.bg_anim >> 15);
		}
	}
	for (rank = first; rank < n; rank++) {
		const VmSprite *s = order[rank];
		const Image *img;
		SpriteLook lk;

		scene_look(&vm, s, SCENE_SETTLED, &lk);
		img = res_peek(lk.image);
		if (!img || img->kind == 3 || lk.alpha < SCENE_HIDDEN_ALPHA)
			continue;
		if (img->kind == 2) {
			SolidBlend sb;

			scene_solid_blend(img->solid, lk.alpha, &sb);
			if (sb.passes)
				printf("R %d %d %d %d %d\n", sb.mode, sb.passes, sb.r, sb.g, sb.b);
		} else {
			int w = img->full_w * lk.zoom / 64, h = img->full_h * lk.zoom / 64;

			printf("D %d %d %d %d %d %d %d %d\n", lk.image, ((SCREEN_W - w) * lk.xa) / 256, ((VIEW_H - h) * lk.ya) / 256,
			       lk.flip, lk.zoom, lk.r, lk.g, lk.b);
		}
	}
	printf("E\n");
}

static void load_positions(void)
{
	char p[600];
	static uint8_t buf[16384];
	const uint8_t *q = buf;
	int n, i;
	FILE *f;

	sprintf(p, "%s/../engine/GAME.BIN", root);
	f = fopen(p, "rb");
	if (!f) {
		fprintf(stderr, "falta %s\n", p);
		exit(1);
	}
	fread(buf, 1, sizeof buf, f);
	fclose(f);
	n = rd16(q + 10);
	q += 12;
	for (i = 0; i < n; i++)
		q += 4 + q[3];
	pos_count = rd16(q);
	q += 2;
	for (i = 0; i < pos_count; i++, q += 4) {
		pos_x[i] = (int16_t)rd16(q);
		pos_y[i] = (int16_t)rd16(q + 2);
	}
}

int main(int argc, char **argv)
{
	static const VmHost host = { 0, loader, notify };
	int i;

	if (argc < 4)
		return 2;
	strcpy(root, argv[1]);
	setvbuf(stdout, 0, _IOLBF, 0);
	load_positions();
	scene_set_positions(pos_x, pos_y, pos_count);
	vm_init(&vm, &host);
	if (vm_start(&vm, atoi(argv[2]), (uint32_t)atoi(argv[3])))
		return 1;
	for (;;) {
		VmEvent ev = vm_run(&vm);

		sync();
		if (ev == VM_EV_SAY) {
			printf("SAY %d %d %d\n", vm.chapter, vm.ev_text, vm.ev_gid);
			frame();
		} else if (ev == VM_EV_MENU) {
			printf("MENU %d %d", vm.chapter, vm.menu_n);
			for (i = 0; i < vm.menu_n; i++)
				printf(" %d", vm.menu_text[i]);
			printf("\n");
			fflush(stdout);
			if (scanf("%d", &vm.choice) != 1)
				return 0;
		} else if (ev == VM_EV_END || ev == VM_EV_ERROR) {
			printf("END %s\n", vm.error ? vm.error : "");
			return 0;
		}
	}
}
