#include <psxgpu.h>
#include <psxapi.h>
#include "video.h"

#define PRIM_BYTES 40000

static DISPENV disp[2];
static DRAWENV draw[2];
static uint32_t ot[2][LAYER_COUNT];
static char prim_buf[2][PRIM_BYTES] __attribute__((aligned(4)));
static char *prim_next;
static int db;
static int frames;

static void begin_frame(void)
{
	ClearOTagR(ot[db], LAYER_COUNT);
	prim_next = prim_buf[db];
}

void video_init(void)
{
	int i;

	ResetGraph(0);

	/* Dos framebuffers de 320x240: el que se muestra y el que se dibuja se alternan */
	SetDefDispEnv(&disp[0], 0, 0, SCREEN_W, SCREEN_H);
	SetDefDispEnv(&disp[1], 0, SCREEN_H, SCREEN_W, SCREEN_H);
	SetDefDrawEnv(&draw[0], 0, SCREEN_H, SCREEN_W, SCREEN_H);
	SetDefDrawEnv(&draw[1], 0, 0, SCREEN_W, SCREEN_H);
	for (i = 0; i < 2; i++) {
		setRGB0(&draw[i], 0, 0, 0);
		draw[i].isbg = 1;
		draw[i].dtd = 1;       /* dither por hardware (D5) */
	}
	db = 0;
	begin_frame();
	SetDispMask(1);
}

void *video_alloc(int size)
{
	void *p = prim_next;

	size = (size + 3) & ~3;
	if (prim_next + size > prim_buf[db] + PRIM_BYTES)
		return 0;
	prim_next += size;
	return p;
}

void video_add(int layer, void *prim)
{
	addPrim(&ot[db][layer], prim);
}

/* Selecciona pagina de textura y modo de mezcla para lo que se agregue despues a la misma capa
 * (como lo agregado despues se dibuja antes, llamar a esto DESPUES de agregar las primitivas). */
void video_set_tpage(int layer, int mode, int abr, int x, int y)
{
	DR_TPAGE *tp = (DR_TPAGE *)video_alloc(sizeof(DR_TPAGE));

	if (!tp)
		return;
	setDrawTPage(tp, 0, 0, getTPage(mode, abr, x, y));
	video_add(layer, tp);
}

void video_rect(int layer, int x, int y, int w, int h, int r, int g, int b, int semi_trans)
{
	TILE *t = (TILE *)video_alloc(sizeof(TILE));

	if (!t)
		return;
	setTile(t);
	setXY0(t, x, y);
	setWH(t, w, h);
	setRGB0(t, r, g, b);
	setSemiTrans(t, semi_trans);
	video_add(layer, t);
	if (semi_trans)
		video_set_tpage(layer, 0, 0, 0, 0);     /* mezcla 50% */
}

void video_flip(void)
{
	DrawSync(0);
	VSync(0);
	PutDispEnv(&disp[db]);
	PutDrawEnv(&draw[db]);
	DrawOTag(&ot[db][LAYER_COUNT - 1]);
	db = !db;
	frames++;
	begin_frame();
}

int video_frames(void)
{
	return frames;
}

/* Origen vertical (en VRAM) del framebuffer donde se dibuja el cuadro actual */
int video_draw_origin_y(void)
{
	return draw[db].clip.y;
}
