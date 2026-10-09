/*
 * Snoot Game PS1 - Fase 6: demo del motor base.
 * Un fondo, un personaje con transparencia y tres lineas de dialogo reales con maquina de escribir.
 *
 * Controles: X avanza/completa el texto, Cuadrado oculta la caja, Select muestra la depuracion.
 */
#include <stdio.h>
#include <string.h>
#include <psxapi.h>
#include <psxpad.h>
#include "cd.h"
#include "img.h"
#include "input.h"
#include "text.h"
#include "video.h"

#define FILE_BUF_BYTES (128 * 1024)
#define MAX_LINES 8
#define BOX_Y 182

typedef struct {
	char name[24];
	uint8_t r, g, b;
	const char *text;
} DemoLine;

static uint8_t file_buf[FILE_BUF_BYTES] __attribute__((aligned(4)));
static uint8_t demo_buf[8192] __attribute__((aligned(4)));
static DemoLine lines[MAX_LINES];
static int line_count;
static Image bg_img, sprite_img;
static int sprite_xalign;      /* 0..256 */

static void fatal(const char *msg)
{
	printf("ERROR: %s\n", msg);
	for (;;) {
		VSync(0);
	}
}

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static void load_image(Image *img, int id, int vram_x, int vram_y, int clut_y)
{
	char path[24];
	int size;

	sprintf(path, "\\I%04d.IMG", id);
	size = cd_read_file(path, file_buf, FILE_BUF_BYTES);
	if (size < 0 || img_load(img, file_buf, size, vram_x, vram_y, clut_y) != 0)
		fatal(path);
}

static void load_demo(void)
{
	int size = cd_read_file("\\DEMO.BIN", demo_buf, sizeof(demo_buf)), i, bg_id, sprite_id;
	const uint8_t *p = demo_buf;

	if (size < 12 || memcmp(p, "DMO1", 4) != 0)
		fatal("DEMO.BIN");
	bg_id = rd16(p + 4);
	sprite_id = rd16(p + 6);
	line_count = rd16(p + 8);
	sprite_xalign = rd16(p + 10);
	p += 12;
	if (line_count > MAX_LINES)
		line_count = MAX_LINES;
	for (i = 0; i < line_count; i++) {
		int n = *p++, len;

		memcpy(lines[i].name, p, n);
		lines[i].name[n] = 0;
		p += n;
		lines[i].r = p[0];
		lines[i].g = p[1];
		lines[i].b = p[2];
		len = rd16(p + 3);
		p += 5;
		lines[i].text = (const char *)p;       /* la cadena termina en 0 dentro del archivo */
		p += len + 1;
	}
	load_image(&bg_img, bg_id, VRAM_BG_X, VRAM_BG_Y, CLUT_BG_Y);
	load_image(&sprite_img, sprite_id, VRAM_SPRITE_X, VRAM_SPRITE_Y, CLUT_SPRITE_Y);
}

static void draw_debug(int fps, int line)
{
	char buf[64];

	sprintf(buf, "FPS %d  CUADRO %d  LINEA %d/%d", fps, video_frames(), line + 1, line_count);
	font_draw(LAYER_DEBUG, 4, 2, buf, 255, 220, 40);
}

int main(int argc, const char *argv[])
{
	TextRun run;
	int line = 0, show_box = 1, debug = 0;
	int vb_start, frames_window = 0, fps = 0;

	video_init();
	cd_init();
	input_init();

	{
		int size = cd_read_file("\\FONT.BIN", file_buf, FILE_BUF_BYTES);
		if (size < 0 || font_load(file_buf, size) != 0)
			fatal("FONT.BIN");
	}
	load_demo();
	text_start(&run, lines[0].text);
	vb_start = VSync(-1);

	for (;;) {
		int vb;

		input_update();
		if (input_pressed(PAD_SELECT))
			debug = !debug;
		if (input_pressed(PAD_SQUARE))
			show_box = !show_box;
		if (input_pressed(PAD_CROSS) || (text_page_done(&run) && run.auto_next && text_finished(&run))) {
			if (!text_page_done(&run)) {
				text_reveal_page(&run);
			} else if (run.at_page_end) {
				text_next_page(&run);
			} else {
				line = (line + 1) % line_count;
				text_start(&run, lines[line].text);
			}
		}
		text_update(&run);

		/* fondo y personaje */
		img_draw(&bg_img, LAYER_BG, 0, VIEW_Y);
		{
			int sx = ((SCREEN_W - sprite_img.full_w) * sprite_xalign) / 256;
			int sy = VIEW_Y + ((VIEW_H - sprite_img.full_h) * 26) / 256;     /* yalign 0.1 como acenter */
			img_draw(&sprite_img, LAYER_SPRITE0, sx, sy);
		}
		video_clip_scene();

		/* caja de dialogo */
		if (show_box) {
			video_rect(LAYER_BOX, 0, BOX_Y, SCREEN_W, SCREEN_H - BOX_Y, 0, 0, 0, 1);
			font_draw(LAYER_TEXT, 8, BOX_Y + 2, lines[line].name, lines[line].r, lines[line].g, lines[line].b);
			text_draw(&run, LAYER_TEXT, 8, BOX_Y + 16, 128, 128, 128);
			if (text_page_done(&run) && ((video_frames() / 20) & 1))
				video_triangle_down(LAYER_TEXT, 304, SCREEN_H - 12, 9, 6, 255, 255, 255);
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
			draw_debug(fps, line);
		video_flip();
	}
	return 0;
}
