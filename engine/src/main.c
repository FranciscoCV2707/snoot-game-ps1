/*
 * Snoot Game PS1 - motor del juego (Fase 7): VM, escenas, dialogo, menus y modo saltar.
 *
 * Controles: X avanza, R1 salta lineas ya leidas, d-pad arriba/abajo elige en menus, Cuadrado oculta la caja,
 * Select muestra la depuracion. Con DEV_MENU, Start vuelve al menu de capitulos.
 */
#include <stdio.h>
#include <string.h>
#include <psxapi.h>
#include <psxpad.h>
#include "audio.h"
#include "cd.h"
#include "img.h"
#include "input.h"
#include "opcodes.h"
#include "res.h"
#include "scene.h"
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
#define MAX_GALLERY 256
#define SKIP_PER_FRAME 8                 /* lineas ya leidas que pasan por cuadro al saltar */
#define DEV_MENU 1                       /* desarrollo: menu de capitulos al arrancar (Start vuelve) y salto de lo no leido */
#define MAX_DEV 48

typedef struct {
	char name[24];
	uint8_t r, g, b;
} Speaker;

typedef enum { ST_RUN, ST_SAY, ST_MENU, ST_PAUSE, ST_END, ST_ERROR, ST_DEV, ST_TRANS } State;

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
static uint16_t gallery_image[MAX_GALLERY];      /* imagen -> indice de galeria, en pares */
static uint8_t gallery_index[MAX_GALLERY];
static int gallery_pairs, gallery_count;
static uint8_t gallery_seen[(MAX_GALLERY + 7) / 8];

/* Menu de capitulos (desarrollo): entradas de STORY y la variable de ruta que cada una necesita (255 = ninguna) */
static int dev_count, dev_chapter;
static uint32_t dev_offset[MAX_DEV];
static uint8_t dev_var[MAX_DEV], dev_value[MAX_DEV];
static char dev_name[MAX_DEV][32];

/* Modo saltar (R1): pasa lo ya leido sin cargar nada del CD; se detiene en texto nuevo, finales y cambios de capitulo */
static int skip_mode, eat_cross;

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
	gallery_count = rd16(p);
	gallery_pairs = rd16(p + 2);
	p += 4;
	if (gallery_count > MAX_GALLERY || gallery_pairs > MAX_GALLERY)
		fatal("galeria demasiado grande");
	for (i = 0; i < gallery_pairs; i++) {
		gallery_image[i] = rd16(p);
		gallery_index[i] = p[2];
		p += 3;
	}
	if (p + 4 > file_buf + size)
		return;
	dev_chapter = rd16(p);
	dev_count = rd16(p + 2);
	p += 4;
	if (dev_count > MAX_DEV)
		dev_count = MAX_DEV;
	for (i = 0; i < dev_count; i++) {
		int n = p[6] < 31 ? p[6] : 31;

		dev_offset[i] = rd32(p);
		dev_var[i] = p[4];
		dev_value[i] = p[5];
		memcpy(dev_name[i], p + 7, n);
		dev_name[i][n] = 0;
		p += 7 + p[6];
	}
}

static void gallery_mark(int image)
{
	int i;

	for (i = 0; i < gallery_pairs; i++)
		if (gallery_image[i] == image)
			gallery_seen[gallery_index[i] >> 3] |= (uint8_t)(1 << (gallery_index[i] & 7));
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
		gallery_mark(args[0]);
		scene_dirty = 1;
		break;
	case OP_SHOW:
		gallery_mark(args[1]);
		scene_dirty = 1;
		break;
	case OP_SHOW_RANDOM:
		scene_dirty = 1;
		break;
	case OP_BACKGROUND:
		gallery_mark(args[0]);
		scene_dirty = 1;
		break;
	case OP_HIDE:
	case OP_ORDER:
		scene_dirty = 1;
		break;
	case OP_MARK_SEEN:
		gallery_mark(args[0]);
		break;
	case OP_ENDING:
		endings_mask |= 1u << (args[0] & 31);
		skip_mode = 0;
		break;
	case OP_LOAD_CHAPTER:
		skip_mode = 0;
		break;
	case OP_UNLOCK_BONUS:
		bonus_mask |= 1u << (args[0] & 31);
		break;
	case OP_MUSIC_PLAY:
		audio_music_play(args[0], args[1], args[2]);
		break;
	case OP_MUSIC_QUEUE:
		audio_music_queue(args[0]);
		break;
	case OP_MUSIC_STOP:
		audio_music_stop(args[0]);
		break;
	case OP_AMBIENT_PLAY:
		audio_ambient_play(args[0], args[1], args[2]);
		break;
	case OP_AMBIENT_STOP:
		audio_ambient_stop(args[0], args[1]);
		break;
	case OP_SFX_PLAY:
		if (!skip_mode)                  /* al saltar no suenan los efectos (como en Ren'Py) */
			audio_sfx_play(args[0]);
		break;
	case OP_SFX_STOP:
		audio_sfx_stop();
		break;
	case OP_VOLUME:
		audio_volume(args[0], args[1], args[2]);
		break;
	}
}

static int op_size(const OpInfo *info)
{
	const char *f;
	int n = 0;

	for (f = info->fmt; *f; f++)
		n += (*f == 'H' || *f == 'h') ? 2 : (*f == 'I') ? 4 : 1;
	return n;
}

/* Mientras se lee una linea se cargan los efectos que vienen, para no leer el CD justo cuando deben sonar */
static void preload_upcoming(void)
{
	uint32_t pc = vm.pc;
	int n;

	for (n = 0; n < 48 && pc < vm.ch.code_size; n++) {
		const uint8_t *p = vm.ch.code + pc;
		const OpInfo *info = op_info(p[0]);

		if (!info || p[0] == OP_MENU || p[0] == OP_JUMP || p[0] == OP_JUMP_IF_FALSE || p[0] == OP_CALL ||
		    p[0] == OP_RETURN || p[0] == OP_LOAD_CHAPTER || p[0] == OP_END)
			return;
		if (p[0] == OP_SFX_PLAY)
			audio_preload(rd16(p + 1));
		pc += 1 + op_size(info);
	}
}

/* Sonidos dentro de las animaciones (`play sound` en un bloque ATL): suenan al pasar su tiempo */
static void anim_sounds(void)
{
	int i, e;

	for (i = 0; i < VM_MAX_SPRITES; i++) {
		VmSprite *s = &vm.sprites[i];
		const uint8_t *anim, *ev;
		int t;

		if (!s->used || !s->anim)
			continue;
		anim = scene_anim(&vm, s->anim);
		if (!anim || !anim[2])
			continue;
		t = video_frames() - (int)s->shown_at;
		ev = anim + 3 + 15 * anim[0];
		for (e = 0; e < anim[2]; e++, ev += 7) {
			int at = rd16(ev);

			if ((ev[4] & 2) && at > s->sound_t && at <= t && !skip_mode) {
				int variants = rd16(ev + 5);

				audio_sfx_play(rd16(ev + 2) + (variants > 1 ? random_below(variants) : 0));
			}
		}
		s->sound_t = t;
	}
}

/* ---------------------------------------------------------------- escena */
/* Alineacion del fondo en el cuadro actual (8.8 desplazado 8 bits mas): interpolacion lineal entre claves (Pan). */
static void bg_align(int *xa, int *ya)
{
	const uint8_t *anim = scene_anim(&vm, vm.bg_anim & 0x7FFF), *k0, *k1;
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

/* Imagen opaca que cubre toda la vista: lo que queda detras no se carga ni se dibuja */
static int covers_view(const Image *img, const VmSprite *s)
{
	return img->kind == 0 && !img->big && !s->anim && img->x == 0 && img->y == 0 &&
	       img->w >= SCREEN_W && img->h >= VIEW_H && img->full_w == img->w && img->full_h == img->h;
}

static void scene_sync(void)
{
	const VmSprite *order[VM_MAX_SPRITES];
	uint16_t extra[SCENE_MAX_EVENTS];
	int rank, i, n, count, first = 0, covered = 0;

	if (!scene_dirty || skip_mode)
		return;                  /* al saltar no se lee el CD: la escena se carga una vez al detenerse */
	scene_dirty = 0;
	res_new_scene();
	count = scene_sorted(&vm, order);
	for (rank = count - 1; rank >= 0 && !covered; rank--) {
		const Image *img = res_get(order[rank]->image);

		first = rank;
		covered = img && covers_view(img, order[rank]);
	}
	if (vm.bg && !covered)
		res_get(vm.bg);
	/* las imagenes que las animaciones muestran despues se cargan si sobra VRAM, para no leer el CD a mitad */
	for (rank = count - 1; rank >= first; rank--) {
		n = scene_event_images(&vm, order[rank], extra, SCENE_MAX_EVENTS);
		for (i = 0; i < n; i++)
			res_get(extra[i]);
	}
}

/* Imagen para dibujar: al saltar solo lo que ya esta en VRAM */
static const Image *scene_image(int id)
{
	return skip_mode ? res_peek(id) : res_get(id);
}

/* ---------------------------------------------------------------- transiciones */
#define TR_CUT 0
#define TR_DISSOLVE 1
#define TR_FADE 2
#define TR_VPUNCH 3
#define TR_HPUNCH 4
#define TR_MOVE 5
#define TR_FADE_WHITE 6

static int trans_type, trans_t, trans_len, trans_a, trans_b, trans_c, snap_x = -1, snap_y;
static int scene_dx, scene_dy;                       /* desplazamiento de toda la escena (sacudidas) */
static int16_t last_x[VM_MAX_SPRITES], last_y[VM_MAX_SPRITES];
static uint8_t last_tag[VM_MAX_SPRITES], last_valid[VM_MAX_SPRITES];
static int16_t from_x[VM_MAX_SPRITES], from_y[VM_MAX_SPRITES];
static uint8_t from_edge[VM_MAX_SPRITES];             /* 0 desde su posicion anterior; 1-4 entra por el borde */

static int ease256(int curve, int u)
{
	int v = 256 - u;

	switch (curve) {
	case 1:
		return (u * u * u) >> 16;
	case 2:
		return 256 - ((v * v * v) >> 16);
	case 3:
		return u < 128 ? (u * u * u) >> 14 : 256 - ((v * v * v) >> 14);
	}
	return u;
}

static void begin_transition(void)
{
	int i;

	trans_type = vm.ev_args[0];
	trans_a = vm.ev_args[1];
	trans_b = vm.ev_args[2];
	trans_c = vm.ev_args[3];
	trans_t = 0;
	switch (trans_type) {
	case TR_DISSOLVE:
	case TR_VPUNCH:
	case TR_HPUNCH:
	case TR_MOVE:
		trans_len = trans_a;
		break;
	case TR_FADE:
	case TR_FADE_WHITE:
		trans_len = trans_a + trans_b + trans_c;
		break;
	default:
		trans_len = 0;
	}
	if (skip_mode || trans_len <= 0)
		return;
	if (trans_type == TR_DISSOLVE || trans_type == TR_FADE || trans_type == TR_FADE_WHITE) {
		/* el cuadro anterior se guarda en VRAM antes de cargar lo nuevo */
		res_reserve_snapshot(&snap_x, &snap_y);
		video_snapshot(snap_x, snap_y);
	}
	if (trans_type == TR_MOVE)
		for (i = 0; i < VM_MAX_SPRITES; i++) {
			const VmSprite *s = &vm.sprites[i];

			from_edge[i] = 0;
			if (!s->used)
				continue;
			if (last_valid[i] && last_tag[i] == s->tag) {
				from_x[i] = last_x[i];
				from_y[i] = last_y[i];
			} else {
				from_edge[i] = (uint8_t)(trans_b & 15);
			}
		}
	state = ST_TRANS;
}

static void end_transition(void)
{
	if (snap_x >= 0) {
		res_release_snapshot();
		snap_x = -1;
	}
	scene_dx = scene_dy = 0;
	state = ST_RUN;
}

static void update_transition(void)
{
	if (++trans_t >= trans_len || skip_mode)
		end_transition();
}

/* Sacudidas: desplazamiento que alterna de lado cada 2 cuadros y se apaga hacia el final */
static void transition_offset(void)
{
	int amp;

	scene_dx = scene_dy = 0;
	if (state != ST_TRANS || (trans_type != TR_VPUNCH && trans_type != TR_HPUNCH))
		return;
	amp = (trans_b / 6) * (trans_len - trans_t) / trans_len;
	if ((trans_t >> 1) & 1)
		amp = -amp;
	if (trans_type == TR_VPUNCH)
		scene_dy = amp;
	else
		scene_dx = amp;
}

/* Posicion de un sprite durante MoveTransition (y registro de donde quedo cada uno) */
static void move_position(int slot, int tag, int w, int h, int *x, int *y)
{
	if (state == ST_TRANS && trans_type == TR_MOVE && vm.sprites[slot].used) {
		int e = ease256(trans_c, trans_t * 256 / trans_len), fx = from_x[slot], fy = from_y[slot];

		switch (from_edge[slot]) {
		case 1: fx = -w; fy = *y; break;
		case 2: fx = SCREEN_W; fy = *y; break;
		case 3: fx = *x; fy = VIEW_Y - h; break;
		case 4: fx = *x; fy = VIEW_Y + VIEW_H; break;
		}
		*x = fx + (*x - fx) * e / 256;
		*y = fy + (*y - fy) * e / 256;
	}
	last_x[slot] = (int16_t)*x;
	last_y[slot] = (int16_t)*y;
	last_tag[slot] = (uint8_t)tag;
	last_valid[slot] = 1;
}

/* Dissolve con la mezcla fija de la GPU: el cuadro anterior encima al 75% (dos pasadas al 50%), luego al 50% y
 * despues ya no. Los fundidos restan (negro) o suman (blanco) un gris que crece y luego decrece. */
static void draw_transition(void)
{
	int p, v, white = trans_type == TR_FADE_WHITE;

	if (state != ST_TRANS)
		return;
	p = trans_t * 256 / trans_len;
	if (trans_type == TR_DISSOLVE && snap_x >= 0) {
		if (p < 192)
			video_snapshot_draw(LAYER_FX, snap_x, snap_y, 1);
		if (p < 96)
			video_snapshot_draw(LAYER_FX, snap_x, snap_y, 1);
	} else if (trans_type == TR_FADE || white) {
		if (trans_t < trans_a) {
			v = trans_t * 255 / (trans_a ? trans_a : 1);
			video_rect(LAYER_FX, 0, VIEW_Y, SCREEN_W, VIEW_H, v, v, v, white ? 2 : 3);  /* encima de la copia */
			if (snap_x >= 0)
				video_snapshot_draw(LAYER_FX, snap_x, snap_y, 0);
		} else if (trans_t < trans_a + trans_b) {
			v = white ? 255 : 0;
			video_rect(LAYER_FX, 0, VIEW_Y, SCREEN_W, VIEW_H, v, v, v, 0);
		} else {
			v = (trans_len - trans_t) * 255 / (trans_c ? trans_c : 1);
			video_rect(LAYER_FX, 0, VIEW_Y, SCREEN_W, VIEW_H, v, v, v, white ? 2 : 3);
		}
	}
}

static void draw_bg(void)
{
	if (!vm.bg)
		video_rect(LAYER_BG, 0, VIEW_Y, SCREEN_W, VIEW_H, 0, 0, 0, 0);   /* negro dibujado: lleva el bit de mascara */
	if (vm.bg) {
		const Image *bg = scene_image(vm.bg);

		if (bg && bg->kind == 2) {
			video_rect(LAYER_BG, 0, VIEW_Y, SCREEN_W, VIEW_H, bg->solid[0], bg->solid[1], bg->solid[2], 0);
		} else if (bg) {
			int xa, ya, bx, by;

			bg_align(&xa, &ya);
			bx = (((SCREEN_W - bg->full_w) * xa) >> 16) + scene_dx;
			by = VIEW_Y + (((VIEW_H - bg->full_h) * ya) >> 16) + scene_dy;
			if (bg->big)
				img_draw_big(bg, LAYER_BG, bx, by);
			else
				img_draw_flip(bg, LAYER_BG, bx, by, vm.bg_anim >> 15);
		}
	}
}

static void draw_solid(int layer, const uint8_t *rgba, int alpha)
{
	SolidBlend sb;
	int i;

	scene_solid_blend(rgba, alpha, &sb);
	for (i = 0; i < sb.passes; i++)
		video_rect(layer, 0, VIEW_Y, SCREEN_W, VIEW_H, sb.r, sb.g, sb.b, sb.mode);
}

static void draw_scene(void)
{
	const VmSprite *order[VM_MAX_SPRITES];
	int n = scene_sorted(&vm, order), rank;

	/* de adelante hacia atras: al llegar a una imagen que tapa toda la vista no hace falta seguir */
	for (rank = n - 1; rank >= 0; rank--) {
		const VmSprite *s = order[rank];
		const Image *img;
		int layer = LAYER_BG - 1 - rank;
		SpriteLook lk;

		scene_look(&vm, s, skip_mode ? SCENE_SETTLED : (int)(video_frames() - s->shown_at), &lk);
		img = scene_image(lk.image);
		if (!img || img->kind == 3 || lk.alpha < SCENE_HIDDEN_ALPHA)
			continue;
		if (layer < LAYER_SPRITE0)
			layer = LAYER_SPRITE0;
		if (img->kind == 2) {
			draw_solid(layer, img->solid, lk.alpha);
		} else {
			int w = img->full_w * lk.zoom / 64, h = img->full_h * lk.zoom / 64;
			int x = ((SCREEN_W - w) * lk.xa) / 256, y = VIEW_Y + ((VIEW_H - h) * lk.ya) / 256;

			move_position((int)(s - vm.sprites), s->tag, w, h, &x, &y);
			img_draw_ex(img, layer, x + scene_dx, y + scene_dy, lk.flip, lk.zoom, lk.r, lk.g, lk.b);
		}
		if (covers_view(img, s)) {
			video_clip_scene();
			return;
		}
	}
	draw_bg();
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
	if (!skip_mode)
		preload_upcoming();
	text_start(&run, text_string(vm.ev_text));
	state = ST_SAY;
}

static void run_vm(void)
{
	VmEvent ev;

	vm.now = (uint32_t)video_frames();
	ev = vm_run(&vm);

	if (ev == VM_EV_TRANSITION)
		begin_transition();          /* antes de cargar lo nuevo: guarda el cuadro anterior */
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

static void begin(int chapter, uint32_t offset, int var, int value)
{
	memset(vm.sprites, 0, sizeof(vm.sprites));
	vm.bg = 0;
	audio_stop_all();
	memset(vm.vars, 0, sizeof(vm.vars));
	if (var < VM_VARS)
		vm.vars[var] = (int16_t)value;
	scene_dirty = 1;
	skip_mode = 0;
	if (vm_start(&vm, chapter, offset) != 0)
		fatal("no se pudo iniciar el capitulo");
	state = ST_RUN;
}

static void restart(void)
{
	if (DEV_MENU && dev_count) {
		menu_cursor = 0;
		menu_top = 0;
		state = ST_DEV;
		return;
	}
	begin(start_chapter, start_offset, 255, 0);
}

/* Fila 0: la historia completa; las demas, las entradas de la tabla */
static void update_dev(void)
{
	int i;

	if (input_pressed(PAD_UP) && menu_cursor > 0)
		menu_cursor--;
	if (input_pressed(PAD_DOWN) && menu_cursor < dev_count)
		menu_cursor++;
	if (!input_pressed(PAD_CROSS))
		return;
	if (menu_cursor == 0) {
		begin(start_chapter, start_offset, 255, 0);
		return;
	}
	i = menu_cursor - 1;
	begin(dev_chapter, dev_offset[i], dev_var[i], dev_value[i]);
}

static void draw_dev(void)
{
	int lh = font_line_height(), rows = (MENU_BOTTOM - MENU_TOP - lh) / lh, i, y;

	video_rect(LAYER_BOX, 0, 0, SCREEN_W, SCREEN_H, 0, 0, 0, 1);
	font_draw(LAYER_TEXT, 20, MENU_TOP - 8, "Menu de capitulos (desarrollo)", 255, 220, 40);
	if (menu_cursor < menu_top)
		menu_top = menu_cursor;
	if (menu_cursor >= menu_top + rows)
		menu_top = menu_cursor - rows + 1;
	y = MENU_TOP - 8 + lh + 4;
	for (i = menu_top; i <= dev_count && i < menu_top + rows; i++) {
		int selected = i == menu_cursor;

		if (selected)
			video_triangle_down(LAYER_TEXT, 6, y + 4, 8, 6, 255, 220, 40);
		font_draw(LAYER_TEXT, 20, y, i == 0 ? "Historia completa" : dev_name[i - 1],
		          selected ? 255 : 128, selected ? 220 : 128, selected ? 40 : 128);
		y += lh;
	}
}

/* Pasa varias lineas ya leidas y pausas por cuadro; se detiene en la primera linea no leida. */
static void skip_step(void)
{
	int n;

	for (n = 0; skip_mode && n < SKIP_PER_FRAME; n++) {
		if (state == ST_SAY) {
			if (!say_seen_before && !DEV_MENU) {
				skip_mode = 0;
				break;
			}
			seen_set(vm.ev_gid);
			state = ST_RUN;
		} else if (state == ST_PAUSE) {
			state = ST_RUN;
		} else if (state != ST_RUN) {
			break;                   /* decision, final o error: espera al jugador */
		}
		run_vm();
	}
	if (skip_mode && state == ST_SAY)
		text_reveal_page(&run);      /* la linea que queda a la vista sale completa, sin maquina de escribir */
}

static void update_say(void)
{
	int advance = (input_pressed(PAD_CROSS) && !eat_cross) ||
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
	audio_init();
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
	scene_set_positions(pos_x, pos_y, pos_count);
	vm_init(&vm, &host);
	restart();
	boot_stage = 4;
	boot_screen(0);
	vb_start = VSync(-1);

	for (;;) {
		int vb;

		input_update();
		audio_update();
		anim_sounds();
		if (input_pressed(PAD_SELECT))
			debug = !debug;
		if (input_pressed(PAD_SQUARE))
			show_box = !show_box;
		if (DEV_MENU && state != ST_DEV && input_pressed(PAD_START))
			restart();
		/* R1 activa o detiene el salto; X tambien lo detiene (fuera de una decision) sin avanzar la linea */
		eat_cross = 0;
		if (state == ST_DEV) {
			/* nada: el menu de capitulos no salta */
		} else if (input_pressed(PAD_R1)) {
			skip_mode = !skip_mode;
		} else if (skip_mode && state != ST_MENU && input_pressed(PAD_CROSS)) {
			skip_mode = 0;
			eat_cross = 1;
		}

		if (state == ST_RUN)
			run_vm();
		skip_step();
		scene_sync();
		switch (state) {
		case ST_SAY:
			update_say();
			break;
		case ST_MENU:
			update_menu();
			break;
		case ST_PAUSE:
			if (--pause_left <= 0 || (vm.ev_flags & 1 && input_pressed(PAD_CROSS) && !eat_cross))
				state = ST_RUN;
			break;
		case ST_END:
			if (input_pressed(PAD_CROSS))
				restart();
			break;
		case ST_DEV:
			update_dev();
			break;
		case ST_TRANS:
			update_transition();
			break;
		default:
			break;
		}

		transition_offset();
		draw_scene();
		draw_transition();
		if (state == ST_DEV)
			draw_dev();
		else if (state == ST_SAY && show_box)
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
		if (skip_mode)
			font_draw(LAYER_DEBUG, SCREEN_W - 84, 12, ">> Saltando", 255, 220, 40);
		video_flip();
	}
	return 0;
}
