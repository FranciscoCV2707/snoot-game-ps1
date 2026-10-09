/*
 * Snoot Game PS1 - motor del juego (Fase 7): VM, escenas, dialogo, menus y modo saltar.
 *
 * Controles: X avanza, R1 salta lineas ya leidas, d-pad arriba/abajo elige en menus, Cuadrado oculta la caja,
 * Select muestra la depuracion.
 */
#include <stdio.h>
#include <string.h>
#include <psxapi.h>
#include <psxpad.h>
#include "cd.h"
#include "img.h"
#include "input.h"
#include "opcodes.h"
#include "res.h"
#include "text.h"
#include "video.h"
#include "vm.h"

#define BOX_Y 168
#define MAX_SPEAKERS 48
#define MAX_POSITIONS 48
#define CHAPTER_BYTES (48 * 1024)
#define TEXT_BYTES (80 * 1024)
#define SEEN_BYTES 2048
#define MENU_TOP 14
#define MENU_BOTTOM 226

typedef struct {
	char name[24];
	uint8_t r, g, b;
} Speaker;

typedef enum { ST_RUN, ST_SAY, ST_MENU, ST_PAUSE, ST_END, ST_ERROR } State;

static uint8_t file_buf[16 * 1024] __attribute__((aligned(4)));
static uint8_t chapter_buf[CHAPTER_BYTES] __attribute__((aligned(4)));
static uint8_t text_buf[TEXT_BYTES] __attribute__((aligned(4)));
static Speaker speakers[MAX_SPEAKERS];
static int speaker_count;
static int16_t pos_x[MAX_POSITIONS], pos_y[MAX_POSITIONS];
static int pos_count;
static int start_chapter;
static uint32_t start_offset;

static Vm vm;
static State state;
static TextRun run;
static int scene_dirty, show_box = 1, debug;
static int pause_left, say_seen_before;
static int bg_start;                        /* cuadro en que aparecio el fondo (inicio de su Pan) */
static uint8_t seen[SEEN_BYTES];
static uint32_t endings_mask, bonus_mask;

static int menu_cursor, menu_top, menu_order[VM_MENU_MAX];
static uint32_t rng_state = 12345;

/* Diagnostico de arranque sin fuente: una barra verde por etapa superada y una roja si fallo */
static int boot_stage;

static void boot_screen(int failed)
{
	int i, n;

	for (i = 0; i < 2; i++) {
		for (n = 0; n < boot_stage; n++)
			video_rect(LAYER_TEXT, 20 + n * 24, 100, 20, 40, 0, 200, 0, 0);
		if (failed)
			video_rect(LAYER_TEXT, 20 + boot_stage * 24, 100, 20, 40, 220, 0, 0, 0);
		video_flip();
	}
}

static void fatal(const char *msg)
{
	printf("ERROR: %s\n", msg);
	boot_screen(1);
	for (;;)
		VSync(0);
}

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int random_below(int n)
{
	rng_state = rng_state * 1103515245u + 12345u;
	return (int)((rng_state >> 16) % (uint32_t)n);
}

/* ---------------------------------------------------------------- progreso */
static int seen_get(int gid)
{
	return gid < SEEN_BYTES * 8 && (seen[gid >> 3] & (1 << (gid & 7)));
}

static void seen_set(int gid)
{
	if (gid < SEEN_BYTES * 8)
		seen[gid >> 3] |= (uint8_t)(1 << (gid & 7));
}

/* ---------------------------------------------------------------- datos */
static void load_game_tables(void)
{
	const uint8_t *p = file_buf;
	int size = cd_read_file("\\DATA\\GAME.BIN", file_buf, sizeof(file_buf)), i;

	if (size < 12 || memcmp(p, "GAM1", 4) != 0)
		fatal("GAME.BIN");
	start_chapter = rd16(p + 4);
	start_offset = rd32(p + 6);
	speaker_count = rd16(p + 10);
	p += 12;
	if (speaker_count > MAX_SPEAKERS)
		fatal("demasiados hablantes");
	for (i = 0; i < speaker_count; i++) {
		int n = p[3];

		speakers[i].r = p[0];
		speakers[i].g = p[1];
		speakers[i].b = p[2];
		memcpy(speakers[i].name, p + 4, n);
		speakers[i].name[n] = 0;
		p += 4 + n;
	}
	pos_count = rd16(p);
	p += 2;
	if (pos_count > MAX_POSITIONS)
		fatal("demasiadas posiciones");
	for (i = 0; i < pos_count; i++) {
		pos_x[i] = (int16_t)rd16(p);
		pos_y[i] = (int16_t)rd16(p + 2);
		p += 4;
	}
}

static int chapter_loader(void *user, int chapter, VmChapter *out)
{
	char path[24];
	int size;

	(void)user;
	sprintf(path, "\\DATA\\C%02d.VNB", chapter);
	size = cd_read_file(path, chapter_buf, CHAPTER_BYTES);
	if (size < 32 || memcmp(chapter_buf, "VNB1", 4) != 0) {
		printf("capitulo %d no disponible\n", chapter);
		return -1;
	}
	out->code = chapter_buf + 32;
	out->code_size = rd32(chapter_buf + 8);
	out->text_base = rd32(chapter_buf + 12);
	out->text_count = rd16(chapter_buf + 16);
	out->anim_count = rd16(chapter_buf + 18);
	out->anims = chapter_buf + rd32(chapter_buf + 24);

	sprintf(path, "\\DATA\\T%02d.TXT", chapter);
	size = cd_read_file(path, text_buf, TEXT_BYTES);
	if (size < 2) {
		printf("texto %d no disponible\n", chapter);
		return -1;
	}
	return 0;
}

static const char *text_string(int local)
{
	return (const char *)(text_buf + 2 + rd32(text_buf + 2 + 4 * local));
}

static void notify(void *user, int opcode, const int32_t *args, int nargs)
{
	(void)user;
	(void)nargs;
	switch (opcode) {
	case OP_SCENE:
		bg_start = video_frames();
		scene_dirty = 1;
		break;
	case OP_SHOW:
	case OP_HIDE:
	case OP_BACKGROUND:
		scene_dirty = 1;
		break;
	case OP_ENDING:
		endings_mask |= 1u << (args[0] & 31);
		break;
	case OP_UNLOCK_BONUS:
		bonus_mask |= 1u << (args[0] & 31);
		break;
	}
}

/* ---------------------------------------------------------------- escena */
static const uint8_t *anim_data(int anim)
{
	if (anim <= 0 || anim > vm.ch.anim_count || !vm.ch.anims)
		return 0;
	return vm.ch.anims + rd32(vm.ch.anims + 4 * (anim - 1));
}

/* Posicion en 8.8 de un sprite: la de su posicion con nombre o, si no tiene, la de su animacion. */
static void sprite_align(const VmSprite *s, int *xa, int *ya)
{
	const uint8_t *anim;

	*xa = 128;
	*ya = 256;                     /* posicion por defecto de Ren'Py: centrado y apoyado abajo */
	if (s->pos < pos_count) {
		*xa = pos_x[s->pos];
		*ya = pos_y[s->pos];
		return;
	}
	anim = anim_data(s->anim);
	if (anim && anim[0]) {
		/* sin animacion de verdad todavia: se usa la posicion final (o la inicial si la animacion se repite) */
		int key = (anim[1] & 1) ? 0 : anim[0] - 1;
		const uint8_t *k = anim + 3 + 15 * key;

		*xa = (int16_t)rd16(k + 2);
		*ya = (int16_t)rd16(k + 4);
	}
}

/* Alineacion del fondo en el cuadro actual (8.8 desplazado 8 bits mas): interpolacion lineal entre claves (Pan). */
static void bg_align(int *xa, int *ya)
{
	const uint8_t *anim = anim_data(vm.bg_anim), *k0, *k1;
	int t = video_frames() - bg_start, n, i, t0, t1, x0, y0;

	*xa = 128 << 8;                /* sin animacion: posicion por defecto de Ren'Py */
	*ya = 256 << 8;
	if (!anim || !anim[0])
		return;
	n = anim[0];
	for (i = 0; i < n - 1 && t >= rd16(anim + 3 + 15 * (i + 1)); i++)
		;
	k0 = anim + 3 + 15 * i;
	x0 = (int16_t)rd16(k0 + 2);
	y0 = (int16_t)rd16(k0 + 4);
	*xa = x0 << 8;
	*ya = y0 << 8;
	if (i == n - 1)
		return;
	k1 = k0 + 15;
	t0 = rd16(k0);
	t1 = rd16(k1);
	if (t <= t0 || t1 <= t0)
		return;
	*xa += (((int16_t)rd16(k1 + 2) - x0) * 256 * (t - t0)) / (t1 - t0);
	*ya += (((int16_t)rd16(k1 + 4) - y0) * 256 * (t - t0)) / (t1 - t0);
}

static void scene_sync(void)
{
	int i;

	if (!scene_dirty)
		return;
	scene_dirty = 0;
	res_new_scene();
	if (vm.bg)
		res_get(vm.bg);
	for (i = 0; i < VM_MAX_SPRITES; i++)
		if (vm.sprites[i].used && vm.sprites[i].image)
			res_get(vm.sprites[i].image);
}

static int sprite_before(const VmSprite *a, const VmSprite *b)
{
	return a->z != b->z ? a->z < b->z : a->born < b->born;
}

static void draw_scene(void)
{
	const VmSprite *order[VM_MAX_SPRITES];
	int n = 0, i, j, rank;

	if (vm.bg) {
		const Image *bg = res_get(vm.bg);

		if (bg && bg->kind == 2) {
			video_rect(LAYER_BG, 0, VIEW_Y, SCREEN_W, VIEW_H, bg->solid[0], bg->solid[1], bg->solid[2], 0);
		} else if (bg) {
			int xa, ya, bx, by;

			bg_align(&xa, &ya);
			bx = ((SCREEN_W - bg->full_w) * xa) >> 16;
			by = VIEW_Y + (((VIEW_H - bg->full_h) * ya) >> 16);
			if (bg->big)
				img_draw_big(bg, LAYER_BG, bx, by);
			else
				img_draw(bg, LAYER_BG, bx, by);
		}
	}
	for (i = 0; i < VM_MAX_SPRITES; i++)
		if (vm.sprites[i].used && vm.sprites[i].image) {
			for (j = n; j > 0 && sprite_before(&vm.sprites[i], order[j - 1]); j--)
				order[j] = order[j - 1];
			order[j] = &vm.sprites[i];
			n++;
		}
	for (rank = n - 1; rank >= 0; rank--) {
		const VmSprite *s = order[rank];
		const Image *img = res_get(s->image);
		int xa, ya, layer = LAYER_BG - 1 - rank;

		if (!img || img->kind == 3)
			continue;
		if (layer < LAYER_SPRITE0)
			layer = LAYER_SPRITE0;
		sprite_align(s, &xa, &ya);
		if (img->kind == 2)
			video_rect(layer, 0, VIEW_Y, SCREEN_W, VIEW_H, img->solid[0], img->solid[1], img->solid[2], 0);
		else
			img_draw_flip(img, layer, ((SCREEN_W - img->full_w) * xa) / 256,
			              VIEW_Y + ((VIEW_H - img->full_h) * ya) / 256, s->flags & 1);
	}
	video_clip_scene();
}

/* ---------------------------------------------------------------- interfaz */
static void draw_box(void)
{
	const Speaker *sp = vm.ev_speaker < speaker_count ? &speakers[vm.ev_speaker] : &speakers[0];

	video_rect(LAYER_BOX, 0, BOX_Y, SCREEN_W, SCREEN_H - BOX_Y, 0, 0, 0, 1);
	if (sp->name[0])
		font_draw(LAYER_TEXT, 8, BOX_Y + 2, sp->name, sp->r, sp->g, sp->b);
	text_draw(&run, LAYER_TEXT, 8, BOX_Y + 15, 128, 128, 128);
	if (text_page_done(&run) && ((video_frames() / 20) & 1))
		video_triangle_down(LAYER_TEXT, 290, SCREEN_H - 24, 10, 7, 255, 255, 255);
}

static int option_lines(const char *s)
{
	int n = 1;

	for (; *s; s++)
		if (*s == '\n')
			n++;
	return n;
}

static void menu_begin(void)
{
	int i;

	for (i = 0; i < vm.menu_n; i++)
		menu_order[i] = i;
	if (vm.menu_flags & 1)
		for (i = vm.menu_n - 1; i > 0; i--) {
			int j = random_below(i + 1), t = menu_order[i];

			menu_order[i] = menu_order[j];
			menu_order[j] = t;
		}
	menu_cursor = 0;
	menu_top = 0;
}

/* Lista las opciones desde menu_top; ajusta menu_top para que el cursor quede visible */
static void draw_menu(void)
{
	int lh = font_line_height(), i, y, last;

	video_rect(LAYER_BOX, 0, 0, SCREEN_W, SCREEN_H, 0, 0, 0, 1);
	for (;;) {
		y = MENU_TOP;
		last = -1;
		for (i = menu_top; i < vm.menu_n; i++) {
			int h = option_lines(text_string(vm.menu_text[menu_order[i]])) * lh + 8;

			if (y + h > MENU_BOTTOM)
				break;
			y += h;
			last = i;
		}
		if (menu_cursor > last && menu_top < menu_cursor)
			menu_top++;
		else
			break;
	}
	y = MENU_TOP;
	for (i = menu_top; i <= last; i++) {
		const char *s = text_string(vm.menu_text[menu_order[i]]);
		int selected = i == menu_cursor;

		if (selected)
			video_triangle_down(LAYER_TEXT, 6, y + 4, 8, 6, 255, 220, 40);
		font_draw(LAYER_TEXT, 20, y, s, selected ? 255 : 128, selected ? 220 : 128, selected ? 40 : 128);
		y += option_lines(s) * lh + 8;
	}
}

/* ---------------------------------------------------------------- flujo */
static void start_say(void)
{
	int gid = vm.ev_gid;

	say_seen_before = seen_get(gid);
	text_start(&run, text_string(vm.ev_text));
	state = ST_SAY;
}

static void run_vm(void)
{
	VmEvent ev = vm_run(&vm);

	scene_sync();
	switch (ev) {
	case VM_EV_SAY:
		start_say();
		break;
	case VM_EV_MENU:
		menu_begin();
		state = ST_MENU;
		break;
	case VM_EV_PAUSE:
		pause_left = vm.ev_frames;
		state = ST_PAUSE;
		break;
	case VM_EV_END:
		state = ST_END;
		break;
	case VM_EV_ERROR:
		printf("VM: %s\n", vm.error);
		state = ST_ERROR;
		break;
	default:
		break;
	}
}

static void restart(void)
{
	memset(vm.sprites, 0, sizeof(vm.sprites));
	vm.bg = 0;
	memset(vm.vars, 0, sizeof(vm.vars));
	scene_dirty = 1;
	if (vm_start(&vm, start_chapter, start_offset) != 0)
		fatal("no se pudo iniciar el capitulo");
	state = ST_RUN;
}

static void update_say(int skipping)
{
	int advance = input_pressed(PAD_CROSS) || (skipping && say_seen_before) ||
	              (text_page_done(&run) && run.auto_next && text_finished(&run));

	if (advance) {
		if (!text_page_done(&run)) {
			text_reveal_page(&run);
		} else if (run.at_page_end) {
			text_next_page(&run);
		} else {
			seen_set(vm.ev_gid);
			state = ST_RUN;
			return;
		}
	}
	text_update(&run);
}

static void update_menu(void)
{
	if (input_pressed(PAD_UP) && menu_cursor > 0)
		menu_cursor--;
	if (input_pressed(PAD_DOWN) && menu_cursor < vm.menu_n - 1)
		menu_cursor++;
	if (input_pressed(PAD_CROSS)) {
		vm.choice = menu_order[menu_cursor];
		state = ST_RUN;
	}
}

static void draw_debug(int fps)
{
	char buf[64];

	sprintf(buf, "FPS %d  CAP %d  PC %d  TXT %d", fps, vm.chapter, (int)vm.pc, vm.ev_gid);
	font_draw(LAYER_DEBUG, 4, 2, buf, 255, 220, 40);
}

int main(int argc, const char *argv[])
{
	static const VmHost host = { 0, chapter_loader, notify };
	int vb_start, frames_window = 0, fps = 0;

	video_init();
	cd_init();
	input_init();
	boot_stage = 1;
	boot_screen(0);
	{
		int size = cd_read_file("\\DATA\\FONT.BIN", chapter_buf, CHAPTER_BYTES);

		if (size < 0 || font_load(chapter_buf, size) != 0)
			fatal("FONT.BIN");
	}
	boot_stage = 2;
	boot_screen(0);
	load_game_tables();
	boot_stage = 3;
	boot_screen(0);
	vm_init(&vm, &host);
	restart();
	boot_stage = 4;
	boot_screen(0);
	vb_start = VSync(-1);

	for (;;) {
		int vb, skipping;

		input_update();
		skipping = input_down(PAD_R1);
		if (input_pressed(PAD_SELECT))
			debug = !debug;
		if (input_pressed(PAD_SQUARE))
			show_box = !show_box;

		if (state == ST_RUN)
			run_vm();
		switch (state) {
		case ST_SAY:
			update_say(skipping);
			break;
		case ST_MENU:
			update_menu();
			break;
		case ST_PAUSE:
			if (--pause_left <= 0 || (vm.ev_flags & 1 && (input_pressed(PAD_CROSS) || skipping)))
				state = ST_RUN;
			break;
		case ST_END:
			if (input_pressed(PAD_CROSS))
				restart();
			break;
		default:
			break;
		}

		draw_scene();
		if (state == ST_SAY && show_box)
			draw_box();
		else if (state == ST_MENU)
			draw_menu();
		else if (state == ST_END)
			font_draw(LAYER_TEXT, 8, BOX_Y + 8, "Fin. Presiona X para volver al inicio.", 128, 128, 128);
		else if (state == ST_ERROR)
			font_draw(LAYER_TEXT, 8, BOX_Y + 8, vm.error ? vm.error : "error", 255, 80, 80);
		video_unclip();

		vb = VSync(-1);
		frames_window++;
		if (vb - vb_start >= 60) {
			fps = (frames_window * 60) / (vb - vb_start);
			frames_window = 0;
			vb_start = vb;
		}
		if (debug)
			draw_debug(fps);
		video_flip();
	}
	return 0;
}
