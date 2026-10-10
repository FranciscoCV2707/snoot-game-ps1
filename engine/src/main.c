/*
 * Snoot Game PS1 - motor del juego: VM, escenas, dialogo, decisiones, modo saltar, titulo, pausa, guardado, opciones,
 * galeria y capitulos extra.
 *
 * Controles: X avanza y confirma, O vuelve, R1 salta lineas ya leidas, Start abre la pausa, d-pad elige en menus,
 * Cuadrado oculta la caja, Select muestra la depuracion. En el titulo, L1 + R1 + Select abre el menu de capitulos de
 * desarrollo (ahi tambien se salta lo no leido).
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
#include "save.h"
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
#define MAX_DEV 48
#define MAX_CHAPTERS 48
#define MAX_EXTRAS 10
#define SLOTS 3

typedef struct {
	char name[24];
	uint8_t r, g, b;
} Speaker;

typedef enum {
	ST_RUN, ST_SAY, ST_MENU, ST_PAUSE, ST_END, ST_ERROR, ST_DEV, ST_TRANS,
	ST_TITLE, ST_PMENU, ST_SLOTS, ST_OPTIONS, ST_GALLERY, ST_EXTRAS, ST_CONFIRM, ST_NOTICE
} State;

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
static int dev_session;                          /* partida empezada desde el menu de desarrollo: salta lo no leido */

/* Datos de la interfaz (seccion UI01 de GAME.BIN) */
static int logo_image, lock_image;
static uint16_t ending_image[4];
static char chapter_name[MAX_CHAPTERS][42];
static int extra_count;
static uint16_t extra_chapter[MAX_EXTRAS];
static uint32_t extra_offset[MAX_EXTRAS];
static char extra_name[MAX_EXTRAS][42];

/* Partida y progreso */
static int music_level = 10, sfx_level = 10;
static uint32_t play_frames;                     /* tiempo de la partida actual */
static int playing_extra;                        /* la partida es un capitulo extra: al terminar vuelve al titulo */
static int autosave_pending;

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
	int size = cd_read_file("\\DATA\\GAME.BIN", file_buf, sizeof(file_buf)), i, n;

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
	n = rd16(p + 2);
	p += 4;
	for (i = 0; i < n; i++) {
		if (i < MAX_DEV) {
			int len = p[6] < 31 ? p[6] : 31;

			dev_offset[i] = rd32(p);
			dev_var[i] = p[4];
			dev_value[i] = p[5];
			memcpy(dev_name[i], p + 7, len);
			dev_name[i][len] = 0;
			dev_count = i + 1;
		}
		p += 7 + p[6];
	}
	/* UI01: logo, candado, imagenes de los finales, nombres de capitulo y capitulos extra */
	if (p + 4 > file_buf + size || memcmp(p, "UI01", 4) != 0)
		return;
	logo_image = rd16(p + 4);
	lock_image = rd16(p + 6);
	for (i = 0; i < 4; i++)
		ending_image[i] = rd16(p + 8 + 2 * i);
	n = rd16(p + 16);
	p += 18;
	for (i = 0; i < n; i++) {
		if (i < MAX_CHAPTERS) {
			memcpy(chapter_name[i], p + 1, p[0] < 41 ? p[0] : 41);
			chapter_name[i][p[0] < 41 ? p[0] : 41] = 0;
		}
		p += 1 + p[0];
	}
	n = *p++;
	for (i = 0; i < n; i++) {
		if (i < MAX_EXTRAS) {
			extra_chapter[i] = rd16(p);
			extra_offset[i] = rd32(p + 2);
			memcpy(extra_name[i], p + 7, p[6] < 41 ? p[6] : 41);
			extra_name[i][p[6] < 41 ? p[6] : 41] = 0;
			extra_count = i + 1;
		}
		p += 7 + p[6];
	}
}

static void gallery_mark(int image)
{
	int i;

	for (i = 0; i < gallery_pairs; i++)
		if (gallery_image[i] == image)
			gallery_seen[gallery_index[i] >> 3] |= (uint8_t)(1 << (gallery_index[i] & 7));
	/* como ending_image() del original: un final cuenta al ver su carta (e1of4 ... e4of4) */
	for (i = 0; i < 4; i++)
		if (ending_image[i] && ending_image[i] == image && !(endings_mask & (1u << i))) {
			endings_mask |= 1u << i;
			autosave_pending = 1;
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
		endings_mask |= 1u << ((args[0] - 1) & 31);
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
	if (state != ST_TRANS || 1)
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

static void clear_scene(void)
{
	memset(vm.sprites, 0, sizeof(vm.sprites));
	vm.bg = 0;
	vm.bg_anim = 0;
	scene_dirty = 1;
}

static void begin(int chapter, uint32_t offset, int var, int value)
{
	clear_scene();
	audio_stop_all();
	memset(vm.vars, 0, sizeof(vm.vars));
	if (var < VM_VARS)
		vm.vars[var] = (int16_t)value;
	skip_mode = 0;
	play_frames = 0;
	if (vm_start(&vm, chapter, offset) != 0)
		fatal("no se pudo iniciar el capitulo");
	state = ST_RUN;
}

static void go_title(void);

/* Fila 0: la historia completa; las demas, las entradas de la tabla */
static void update_dev(void)
{
	int i;

	if (input_pressed(PAD_UP) && menu_cursor > 0)
		menu_cursor--;
	if (input_pressed(PAD_DOWN) && menu_cursor < dev_count)
		menu_cursor++;
	if (input_pressed(PAD_CIRCLE)) {
		go_title();
		return;
	}
	if (!input_pressed(PAD_CROSS))
		return;
	dev_session = 1;
	playing_extra = 0;
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

/* ---------------------------------------------------------------- guardado (D10, docs/presupuesto-memoria.md) */
/* Datos: 0 control (save.c), 16 volumenes, 20 finales u32, 24 extras terminados u32, 32 galeria vista, 64 texto
 * leido, despues las 3 ranuras. Ranura: 0 usada, 1 llamadas, 2 capitulo u16, 4 pc u32, 8 numero de guardado u32,
 * 12 tiempo u32, 16 fondo u16, 18 anim del fondo u16, 20 musica i16, 22 ambientes 4 x i16, 32 variables 64 x i16,
 * 160 llamadas 8 x (capitulo u16, pc u32), 208 contador de orden u32, 212 sprites (copia de VmSprite). */
#define OFS_OPTIONS 16
#define OFS_ENDINGS 20
#define OFS_BONUS 24
#define OFS_GALLERY 32
#define OFS_SEEN 64
#define OFS_SLOTS (OFS_SEEN + SEEN_BYTES)
#define SLOT_BYTES 1024
#define SL_VARS 32
#define SL_CALLS 160
#define SL_BORN 208
#define SL_SPRITES 212

static uint8_t save_buf[SAVE_DATA_BYTES] __attribute__((aligned(4)));
static int card_state = SAVE_NO_FILE;
static uint32_t save_number;

static void wr16(uint8_t *p, int v)
{
	p[0] = (uint8_t)v;
	p[1] = (uint8_t)(v >> 8);
}

static void wr32(uint8_t *p, uint32_t v)
{
	wr16(p, (int)(v & 0xffff));
	wr16(p + 2, (int)(v >> 16));
}

static uint8_t *slot_ptr(int i)
{
	return save_buf + OFS_SLOTS + i * SLOT_BYTES;
}

static void progress_to_buf(void)
{
	save_buf[OFS_OPTIONS] = (uint8_t)music_level;
	save_buf[OFS_OPTIONS + 1] = (uint8_t)sfx_level;
	wr32(save_buf + OFS_ENDINGS, endings_mask);
	wr32(save_buf + OFS_BONUS, bonus_mask);
	memcpy(save_buf + OFS_GALLERY, gallery_seen, sizeof(gallery_seen));
	memcpy(save_buf + OFS_SEEN, seen, SEEN_BYTES);
}

static void progress_from_buf(void)
{
	int i;

	music_level = save_buf[OFS_OPTIONS] <= 10 ? save_buf[OFS_OPTIONS] : 10;
	sfx_level = save_buf[OFS_OPTIONS + 1] <= 10 ? save_buf[OFS_OPTIONS + 1] : 10;
	endings_mask = rd32(save_buf + OFS_ENDINGS);
	bonus_mask = rd32(save_buf + OFS_BONUS);
	memcpy(gallery_seen, save_buf + OFS_GALLERY, sizeof(gallery_seen));
	memcpy(seen, save_buf + OFS_SEEN, SEEN_BYTES);
	for (i = 0; i < SLOTS; i++)
		if (rd32(slot_ptr(i) + 8) > save_number)
			save_number = rd32(slot_ptr(i) + 8);
	audio_set_levels(music_level, sfx_level);
}

static int newest_slot(void)
{
	int i, best = -1;

	for (i = 0; i < SLOTS; i++)
		if (slot_ptr(i)[0] && (best < 0 || rd32(slot_ptr(i) + 8) > rd32(slot_ptr(best) + 8)))
			best = i;
	return best;
}

static void draw_center(int y, const char *s, int r, int g, int b);

/* Pantalla de un solo mensaje dibujada ya (las operaciones de la memory card bloquean) */
static void show_now(const char *msg)
{
	int i;

	for (i = 0; i < 2; i++) {
		video_rect(LAYER_BOX, 0, 0, SCREEN_W, SCREEN_H, 0, 0, 0, 0);
		draw_center(SCREEN_H / 2 - 8, msg, 128, 128, 128);
		video_flip();
	}
}

static const char *card_error(int result)
{
	switch (result) {
	case SAVE_NO_CARD:
		return "No hay memory card en la ranura 1.";
	case SAVE_FULL:
		return "La memory card está llena\n(se necesita 1 bloque libre).";
	case SAVE_WRITE_ERROR:
		return "No se pudo escribir en la memory card.";
	}
	return 0;
}

static int write_card(const char *msg)
{
	show_now(msg);
	progress_to_buf();
	card_state = save_write(save_buf);
	return card_state;
}

static void save_slot(int i)
{
	uint8_t *s = slot_ptr(i);
	int k;

	memset(s, 0, SLOT_BYTES);
	s[0] = 1;
	s[1] = (uint8_t)vm.ncalls;
	wr16(s + 2, vm.chapter);
	wr32(s + 4, vm.ev_pc);
	wr32(s + 8, ++save_number);
	wr32(s + 12, play_frames);
	wr16(s + 16, vm.bg);
	wr16(s + 18, vm.bg_anim);
	wr16(s + 20, audio_music_current());
	for (k = 0; k < 4; k++)
		wr16(s + 22 + 2 * k, audio_ambient_current(k));
	for (k = 0; k < VM_VARS; k++)
		wr16(s + SL_VARS + 2 * k, vm.vars[k]);
	for (k = 0; k < vm.ncalls && k < VM_CALLS; k++) {
		wr16(s + SL_CALLS + 6 * k, vm.calls[k].chapter);
		wr32(s + SL_CALLS + 6 * k + 2, vm.calls[k].pc);
	}
	wr32(s + SL_BORN, vm.born_counter);
	memcpy(s + SL_SPRITES, vm.sprites, sizeof(vm.sprites));
}

static void load_slot(int i)
{
	const uint8_t *s = slot_ptr(i);
	int k, music;

	clear_scene();
	audio_stop_all();
	skip_mode = 0;
	if (vm_start(&vm, rd16(s + 2), rd32(s + 4)) != 0)
		fatal("no se pudo cargar la partida");
	for (k = 0; k < VM_VARS; k++)
		vm.vars[k] = (int16_t)rd16(s + SL_VARS + 2 * k);
	vm.ncalls = s[1] < VM_CALLS ? s[1] : VM_CALLS;
	for (k = 0; k < vm.ncalls; k++) {
		vm.calls[k].chapter = rd16(s + SL_CALLS + 6 * k);
		vm.calls[k].pc = rd32(s + SL_CALLS + 6 * k + 2);
	}
	vm.born_counter = rd32(s + SL_BORN);
	memcpy(vm.sprites, s + SL_SPRITES, sizeof(vm.sprites));
	for (k = 0; k < VM_MAX_SPRITES; k++) {
		vm.sprites[k].shown_at = 0;                    /* las animaciones quedan asentadas */
		vm.sprites[k].sound_t = 0x7fffffff;            /* y sus sonidos no se repiten */
	}
	vm.bg = rd16(s + 16);
	vm.bg_anim = rd16(s + 18);
	bg_start = -100000;
	play_frames = rd32(s + 12);
	music = (int16_t)rd16(s + 20);
	if (music >= 0)
		audio_music_play(music, 10, 0);
	for (k = 0; k < 4; k++) {
		int amb = (int16_t)rd16(s + 22 + 2 * k);

		if (amb >= 0)
			audio_ambient_play(k, amb, 10);
	}
	playing_extra = 0;
	dev_session = 0;
	scene_dirty = 1;
	state = ST_RUN;
}

/* ---------------------------------------------------------------- pantallas */
enum { UI_SAVE, UI_LOAD };
enum { CONF_OVERWRITE, CONF_QUIT };

static int ui_cursor, ui_mode, ui_slot, ui_changed, gallery_pos;
static State ui_back;                         /* a donde vuelve la pantalla actual con O */
static State pause_from;                      /* estado del juego al abrir la pausa */
static const char *notice_text;
static State notice_next;
static const char *confirm_text;
static int confirm_action, confirm_yes;

static void notice(const char *text, State next)
{
	notice_text = text;
	notice_next = next;
	state = ST_NOTICE;
}

/* Texto centrado; cada linea (separada por \n) se centra por separado */
static void draw_center(int y, const char *s, int r, int g, int b)
{
	char line[96];

	while (*s) {
		int n = 0;

		while (s[n] && s[n] != '\n' && n < (int)sizeof(line) - 1)
			n++;
		memcpy(line, s, n);
		line[n] = 0;
		font_draw(LAYER_TEXT, (SCREEN_W - font_width(line)) / 2, y, line, r, g, b);
		y += font_line_height();
		s += n;
		if (*s == '\n')
			s++;
	}
}

/* Lista centrada; `disabled` marca en gris las opciones que no se pueden usar */
static void draw_list(int y, const char *const *items, int n, int cursor, uint32_t disabled)
{
	int lh = font_line_height() + 4, i;

	for (i = 0; i < n; i++, y += lh) {
		int gray = (disabled >> i) & 1, sel = i == cursor;

		if (sel)
			video_triangle_down(LAYER_TEXT, (SCREEN_W - font_width(items[i])) / 2 - 14, y + 4, 8, 6, 255, 220, 40);
		draw_center(y, items[i], gray ? 64 : sel ? 255 : 128, gray ? 64 : sel ? 220 : 128, gray ? 64 : sel ? 40 : 128);
	}
}

/* Arriba/abajo con vuelta; devuelve 1 con X, -1 con O */
static int list_input(int *cursor, int n)
{
	if (input_pressed(PAD_UP))
		*cursor = (*cursor + n - 1) % n;
	if (input_pressed(PAD_DOWN))
		*cursor = (*cursor + 1) % n;
	if (input_pressed(PAD_CROSS))
		return 1;
	if (input_pressed(PAD_CIRCLE))
		return -1;
	return 0;
}

static void panel(void)
{
	video_rect(LAYER_BOX, 0, 0, SCREEN_W, SCREEN_H, 0, 0, 0, 1);
	video_rect(LAYER_BOX, 0, 0, SCREEN_W, SCREEN_H, 0, 0, 0, 1);
}

/* Capitulos extra visibles, como ex_ch_menu del original: segun los finales vistos y los extras terminados */
static int extra_unlocked(int i)
{
	int e = endings_mask & 15, seen_count = 0, w, k;

	if (e == 0)
		return 0;
	if (e == 15)
		return i < 9 || (bonus_mask & 0x1ff) == 0x1ff;
	for (k = 0; k < 4; k++)
		seen_count += (e >> k) & 1;
	w = 4 - seen_count;                              /* se esconden w de Trish (x4-x6) y w de Naomi (x7-x9) desde el final */
	if (i == 9 || (i >= 6 - w && i <= 5) || (i >= 9 - w && i <= 8))
		return 0;
	return 1;
}

static int extras_list(int *out)
{
	int i, n = 0;

	for (i = 0; i < extra_count; i++)
		if (extra_unlocked(i))
			out[n++] = i;
	return n;
}

static void go_title(void)
{
	clear_scene();
	audio_stop_all();
	skip_mode = 0;
	dev_session = 0;
	playing_extra = 0;
	ui_cursor = newest_slot() >= 0 ? 1 : 0;
	state = ST_TITLE;
}

static const char *const title_items[] = { "Comenzar", "Continuar", "Capítulos extra", "Galería", "Opciones" };

static void open_slots(int mode, State back)
{
	ui_mode = mode;
	ui_back = back;
	ui_cursor = newest_slot() >= 0 ? newest_slot() : 0;
	state = ST_SLOTS;
}

static void open_options(State back)
{
	ui_back = back;
	ui_cursor = 0;
	ui_changed = 0;
	state = ST_OPTIONS;
}

static void update_title(void)
{
	int extras[MAX_EXTRAS];

	if (input_down(PAD_L1) && input_down(PAD_R1) && input_pressed(PAD_SELECT) && dev_count) {
		menu_cursor = menu_top = 0;
		state = ST_DEV;
		return;
	}
	if (list_input(&ui_cursor, 5) != 1)
		return;
	switch (ui_cursor) {
	case 0:
		dev_session = 0;
		playing_extra = 0;
		begin(start_chapter, start_offset, 255, 0);
		break;
	case 1:
		if (newest_slot() < 0)
			notice(card_state == SAVE_NO_CARD ? "No hay memory card en la ranura 1." : "No hay partidas guardadas.",
			       ST_TITLE);
		else
			open_slots(UI_LOAD, ST_TITLE);
		break;
	case 2:
		if (extras_list(extras) == 0)
			notice("Termina una ruta para desbloquear\nlos capítulos extra.", ST_TITLE);
		else {
			ui_cursor = 0;
			state = ST_EXTRAS;
		}
		break;
	case 3:
		gallery_pos = 0;
		state = ST_GALLERY;
		break;
	case 4:
		open_options(ST_TITLE);
		break;
	}
}

static void draw_title(void)
{
	const Image *logo = logo_image ? res_get(logo_image) : 0;
	uint32_t disabled = newest_slot() < 0 ? 2 : 0;
	int extras[MAX_EXTRAS];

	if (!extras_list(extras))
		disabled |= 4;
	if (logo && logo->kind <= 1)
		img_draw(logo, LAYER_TEXT, (SCREEN_W - logo->full_w) / 2, 12);
	draw_list(130, title_items, 5, ui_cursor, disabled);
	if (disabled & 4) {
		const Image *lock = lock_image ? res_get(lock_image) : 0;

		if (lock && lock->kind <= 1)
			img_draw(lock, LAYER_TEXT, (SCREEN_W + font_width(title_items[2])) / 2 + 6, 130 + 2 * (font_line_height() + 4) + 2);
	}
}

static const char *const pause_items[] = { "Seguir", "Saltar texto leído", "Guardar", "Cargar", "Opciones", "Salir al título" };

static int pause_opened;                      /* cuadro en que se abrio (el mismo Start no la cierra) */

static void update_pause_menu(void)
{
	int r = list_input(&ui_cursor, 6);

	if (r < 0 || (input_pressed(PAD_START) && video_frames() != pause_opened)) {
		state = pause_from;
		return;
	}
	if (r != 1)
		return;
	switch (ui_cursor) {
	case 0:
		state = pause_from;
		break;
	case 1:
		state = pause_from;
		skip_mode = 1;
		break;
	case 2:
		open_slots(UI_SAVE, ST_PMENU);
		break;
	case 3:
		open_slots(UI_LOAD, ST_PMENU);
		break;
	case 4:
		open_options(ST_PMENU);
		break;
	case 5:
		confirm_text = "¿Salir? Lo no guardado se perderá.";
		confirm_action = CONF_QUIT;
		confirm_yes = 0;
		ui_back = ST_PMENU;
		state = ST_CONFIRM;
		break;
	}
}

static void do_save(int slot)
{
	const char *err;

	save_slot(slot);
	err = card_error(write_card("Guardando...\nNo retires la memory card."));
	if (err) {
		slot_ptr(slot)[0] = 0;
		notice(err, ST_PMENU);
	} else {
		notice("Partida guardada.", pause_from);
	}
}

static void update_slots(void)
{
	int r = list_input(&ui_cursor, SLOTS);

	if (r < 0) {
		ui_cursor = 0;
		state = ui_back;
		return;
	}
	if (r != 1)
		return;
	if (ui_mode == UI_LOAD) {
		if (slot_ptr(ui_cursor)[0])
			load_slot(ui_cursor);
		return;
	}
	if (slot_ptr(ui_cursor)[0]) {
		confirm_text = "¿Sobrescribir esta ranura?";
		confirm_action = CONF_OVERWRITE;
		confirm_yes = 0;
		ui_slot = ui_cursor;
		state = ST_CONFIRM;
		return;
	}
	do_save(ui_cursor);
}

static void draw_slots(void)
{
	int lh = font_line_height() + 10, i, newest = newest_slot();
	char line[96];

	panel();
	draw_center(30, ui_mode == UI_SAVE ? "Guardar partida" : "Cargar partida", 255, 220, 40);
	for (i = 0; i < SLOTS; i++) {
		const uint8_t *s = slot_ptr(i);
		int y = 70 + i * lh, sel = i == ui_cursor, c = sel ? 255 : 128;

		if (s[0]) {
			uint32_t secs = rd32(s + 12) / 60;
			int ch = rd16(s + 2);

			sprintf(line, "Ranura %d   %s   %02d:%02d%s", i + 1, ch < MAX_CHAPTERS ? chapter_name[ch] : "",
			        (int)(secs / 3600), (int)(secs / 60 % 60), i == newest ? "  *" : "");
		} else {
			sprintf(line, "Ranura %d   - vacía -", i + 1);
		}
		if (sel)
			video_triangle_down(LAYER_TEXT, 14, y + 4, 8, 6, 255, 220, 40);
		font_draw(LAYER_TEXT, 28, y, line, c, sel ? 220 : 128, sel ? 40 : 128);
	}
	draw_center(SCREEN_H - 30, "X elegir   O volver", 96, 96, 96);
}

static void update_confirm(void)
{
	if (input_pressed(PAD_LEFT) || input_pressed(PAD_RIGHT) || input_pressed(PAD_UP) || input_pressed(PAD_DOWN))
		confirm_yes = !confirm_yes;
	if (input_pressed(PAD_CIRCLE) || (input_pressed(PAD_CROSS) && !confirm_yes)) {
		state = confirm_action == CONF_OVERWRITE ? ST_SLOTS : ST_PMENU;
		return;
	}
	if (!input_pressed(PAD_CROSS))
		return;
	if (confirm_action == CONF_OVERWRITE) {
		do_save(ui_slot);
	} else {
		write_card("Guardando progreso...");
		go_title();
	}
}

static void draw_confirm(void)
{
	panel();
	draw_center(90, confirm_text, 128, 128, 128);
	font_draw(LAYER_TEXT, 120, 120, "Sí", confirm_yes ? 255 : 96, confirm_yes ? 220 : 96, confirm_yes ? 40 : 96);
	font_draw(LAYER_TEXT, 180, 120, "No", confirm_yes ? 96 : 255, confirm_yes ? 96 : 220, confirm_yes ? 96 : 40);
}

static void update_options(void)
{
	int *level = ui_cursor == 0 ? &music_level : ui_cursor == 1 ? &sfx_level : 0;

	if (input_pressed(PAD_UP))
		ui_cursor = (ui_cursor + 2) % 3;
	if (input_pressed(PAD_DOWN))
		ui_cursor = (ui_cursor + 1) % 3;
	if (level && input_pressed(PAD_LEFT) && *level > 0) {
		(*level)--;
		ui_changed = 1;
	}
	if (level && input_pressed(PAD_RIGHT) && *level < 10) {
		(*level)++;
		ui_changed = 1;
	}
	audio_set_levels(music_level, sfx_level);
	if (input_pressed(PAD_CIRCLE) || (ui_cursor == 2 && input_pressed(PAD_CROSS))) {
		if (ui_changed)
			write_card("Guardando opciones...");
		ui_cursor = 0;
		state = ui_back;
	}
}

static void draw_bar(int y, const char *label, int level, int sel)
{
	int i;

	font_draw(LAYER_TEXT, 60, y, label, sel ? 255 : 128, sel ? 220 : 128, sel ? 40 : 128);
	for (i = 0; i < 10; i++)
		video_rect(LAYER_TEXT, 150 + i * 11, y + 3, 8, 9, i < level ? 220 : 50, i < level ? 200 : 50, i < level ? 60 : 50, 0);
}

static void draw_options(void)
{
	panel();
	draw_center(40, "Opciones", 255, 220, 40);
	draw_bar(80, "Música", music_level, ui_cursor == 0);
	draw_bar(105, "Efectos", sfx_level, ui_cursor == 1);
	draw_center(140, "Volver", ui_cursor == 2 ? 255 : 128, ui_cursor == 2 ? 220 : 128, ui_cursor == 2 ? 40 : 128);
	draw_center(SCREEN_H - 30, "Izquierda/derecha cambia el volumen", 96, 96, 96);
}

static int gallery_seen_at(int k)
{
	return (gallery_seen[k >> 3] >> (k & 7)) & 1;
}

static int gallery_first_image(int k)
{
	int i;

	for (i = 0; i < gallery_pairs; i++)
		if (gallery_index[i] == k)
			return gallery_image[i];
	return 0;
}

static void update_gallery(void)
{
	if (input_pressed(PAD_LEFT))
		gallery_pos = (gallery_pos + gallery_count - 1) % gallery_count;
	if (input_pressed(PAD_RIGHT))
		gallery_pos = (gallery_pos + 1) % gallery_count;
	if (input_pressed(PAD_CIRCLE)) {
		ui_cursor = 3;
		state = ST_TITLE;
	}
}

static void draw_gallery(void)
{
	char line[24];
	int image = gallery_first_image(gallery_pos);

	if (gallery_seen_at(gallery_pos) && image) {
		const Image *img;

		res_new_scene();
		img = res_get(image);
		if (img && img->kind <= 1) {
			int x = (SCREEN_W - img->full_w) / 2;
			int y = VIEW_Y + (img->kind == 0 ? (VIEW_H - img->full_h) / 2 : VIEW_H - img->full_h);

			if (img->big)
				img_draw_big(img, LAYER_SPRITE0, x, y);
			else
				img_draw(img, LAYER_SPRITE0, x, y);
		}
	} else {
		video_rect(LAYER_SPRITE0, 60, VIEW_Y + 40, 200, 100, 30, 30, 30, 0);
		draw_center(VIEW_Y + 80, "???", 96, 96, 96);
	}
	video_clip_scene();
	sprintf(line, "%d / %d", gallery_pos + 1, gallery_count);
	draw_center(SCREEN_H - 24, line, 128, 128, 128);
	font_draw(LAYER_TEXT, 8, SCREEN_H - 24, "< >", 96, 96, 96);
	font_draw(LAYER_TEXT, SCREEN_W - 70, SCREEN_H - 24, "O volver", 96, 96, 96);
}

static void update_extras(void)
{
	int list[MAX_EXTRAS], n = extras_list(list), r = list_input(&ui_cursor, n);

	if (r < 0) {
		ui_cursor = 2;
		state = ST_TITLE;
		return;
	}
	if (r != 1)
		return;
	dev_session = 0;
	begin(extra_chapter[list[ui_cursor]], extra_offset[list[ui_cursor]], 255, 0);
	playing_extra = 1;
}

static void draw_extras(void)
{
	int list[MAX_EXTRAS], n = extras_list(list), i;
	const char *items[MAX_EXTRAS];

	for (i = 0; i < n; i++)
		items[i] = extra_name[list[i]];
	panel();
	draw_center(24, "Capítulos extra", 255, 220, 40);
	draw_list(50, items, n, ui_cursor, 0);
}

/* Fin de una partida: se guarda el progreso (texto leido, galeria, finales) y se vuelve al titulo */
static void finish_game(void)
{
	if (!dev_session)
		write_card("Guardando progreso...");
	go_title();
}

/* Pasa varias lineas ya leidas y pausas por cuadro; se detiene en la primera linea no leida. */
static void skip_step(void)
{
	int n;

	for (n = 0; skip_mode && n < SKIP_PER_FRAME; n++) {
		if (state == ST_SAY) {
			if (!say_seen_before && !dev_session) {
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
	if (cd_read_file("\\DATA\\MCICON.BIN", file_buf, sizeof(file_buf)) >= 160)
		save_set_icon(file_buf);
	{
		/* prueba automatica: solo existe en los discos de prueba (tools/engine/emutest.py) */
		static uint8_t autotest[4096] __attribute__((aligned(4)));
		int lba, size;

		if (cd_find("\\DATA\\AUTOTEST.BIN", &lba, &size) == 0 && size <= (int)sizeof(autotest) &&
		    cd_read_file("\\DATA\\AUTOTEST.BIN", autotest, sizeof(autotest)) > 2)
			input_set_script(autotest + 2, autotest[0] | (autotest[1] << 8));
	}
	boot_stage = 4;
	{
		/* creditos mientras se lee la memory card */
		int i;

		for (i = 0; i < 2; i++) {
			draw_center(90, "Snoot Game", 255, 220, 40);
			draw_center(108, "por Cavemanon", 128, 128, 128);
			draw_center(140, "Versión para PlayStation hecha por fans", 96, 96, 96);
			video_flip();
		}
		{
			int t0 = VSync(-1);
			card_state = save_read(save_buf);
			if (card_state == SAVE_OK)
				progress_from_buf();
			else
				memset(save_buf, 0, sizeof(save_buf));
			while (VSync(-1) - t0 < 150) {
				draw_center(90, "Snoot Game", 255, 220, 40);
				draw_center(108, "por Cavemanon", 128, 128, 128);
				draw_center(140, "Versión para PlayStation hecha por fans", 96, 96, 96);
				video_flip();
			}
		}
	}
	go_title();
	vb_start = VSync(-1);

	for (;;) {
		int vb, in_game;

		input_update();
		audio_update();
		in_game = state <= ST_ERROR || state == ST_TRANS;
		if (in_game)
			anim_sounds();
		if (in_game && input_pressed(PAD_SELECT))
			debug = !debug;
		if (input_pressed(PAD_SQUARE))
			show_box = !show_box;
		/* Start abre la pausa donde se puede guardar: en una linea o en una decision */
		if ((state == ST_SAY || state == ST_MENU) && input_pressed(PAD_START)) {
			pause_from = state;
			pause_opened = video_frames();
			skip_mode = 0;
			ui_cursor = 0;
			state = ST_PMENU;
		}
		/* R1 activa o detiene el salto; X tambien lo detiene (fuera de una decision) sin avanzar la linea */
		eat_cross = 0;
		if (!in_game) {
			/* en los menus no se salta */
		} else if (input_pressed(PAD_R1)) {
			skip_mode = !skip_mode;
		} else if (skip_mode && state != ST_MENU && input_pressed(PAD_CROSS)) {
			skip_mode = 0;
			eat_cross = 1;
		}
		if (in_game)
			play_frames++;
		if (autosave_pending && state == ST_SAY && !dev_session) {
			autosave_pending = 0;
			write_card("Guardando progreso...");
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
			finish_game();
			break;
		case ST_ERROR:
			if (input_pressed(PAD_CROSS))
				go_title();
			break;
		case ST_DEV:
			update_dev();
			break;
		case ST_TRANS:
			update_transition();
			break;
		case ST_TITLE:
			update_title();
			break;
		case ST_PMENU:
			update_pause_menu();
			break;
		case ST_SLOTS:
			update_slots();
			break;
		case ST_OPTIONS:
			update_options();
			break;
		case ST_GALLERY:
			update_gallery();
			break;
		case ST_EXTRAS:
			update_extras();
			break;
		case ST_CONFIRM:
			update_confirm();
			break;
		case ST_NOTICE:
			if (input_pressed(PAD_CROSS) || input_pressed(PAD_CIRCLE))
				state = notice_next;
			break;
		default:
			break;
		}

		transition_offset();
		if (state != ST_GALLERY)
			draw_scene();
		draw_transition();
		switch (state) {
		case ST_DEV:
			draw_dev();
			break;
		case ST_SAY:
			if (show_box)
				draw_box();
			break;
		case ST_MENU:
			draw_menu();
			break;
		case ST_ERROR:
			font_draw(LAYER_TEXT, 8, BOX_Y + 8, vm.error ? vm.error : "error", 255, 80, 80);
			break;
		case ST_TITLE:
			draw_title();
			break;
		case ST_PMENU:
			panel();
			draw_center(40, "Pausa", 255, 220, 40);
			draw_list(70, pause_items, 6, ui_cursor, 0);
			break;
		case ST_SLOTS:
			draw_slots();
			break;
		case ST_OPTIONS:
			draw_options();
			break;
		case ST_GALLERY:
			draw_gallery();
			break;
		case ST_EXTRAS:
			draw_extras();
			break;
		case ST_CONFIRM:
			draw_confirm();
			break;
		case ST_NOTICE:
			panel();
			draw_center(92, notice_text, 128, 128, 128);
			draw_center(140, "X continuar", 96, 96, 96);
			break;
		default:
			break;
		}
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
