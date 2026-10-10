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
	DR_STP *off;

	ClearOTagR(ot[db], LAYER_COUNT);
	prim_next = prim_buf[db];
	/* lo ultimo que dibuja el cuadro apaga el bit de mascara: si quedara puesto tambien se escribiria en las texturas
	 * que se suben a VRAM y estropearia la mitad de sus pixeles (rayas verticales en DuckStation) */
	off = (DR_STP *)video_alloc(sizeof(DR_STP));
	setDrawStp(off, 0, 0);
	video_add(LAYER_DEBUG, off);         /* primero en la capa 0 = lo ultimo en dibujarse */
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

/* blend: 0 opaco; si no, modo de mezcla de la GPU + 1 (1 = 50%, 2 = suma, 3 = resta, 4 = suma de 1/4) */
void video_rect(int layer, int x, int y, int w, int h, int r, int g, int b, int blend)
{
	TILE *t = (TILE *)video_alloc(sizeof(TILE));

	if (!t)
		return;
	setTile(t);
	setXY0(t, x, y);
	setWH(t, w, h);
	setRGB0(t, r, g, b);
	setSemiTrans(t, blend != 0);
	video_add(layer, t);
	if (blend)
		video_set_tpage(layer, 0, blend - 1, 0, 0);
}

/* Triangulo relleno apuntando hacia abajo (indicador de "presiona X"), dibujado con una primitiva en vez de un glifo */
void video_triangle_down(int layer, int x, int y, int w, int h, int r, int g, int b)
{
	POLY_F3 *t = (POLY_F3 *)video_alloc(sizeof(POLY_F3));

	if (!t)
		return;
	setPolyF3(t);
	setXY3(t, x, y, x + w, y, x + w / 2, y + h);
	setRGB0(t, r, g, b);
	video_add(layer, t);
}

void video_flip(void)
{
	DR_STP *stp = (DR_STP *)video_alloc(sizeof(DR_STP));

	/* lo que dibuja el cuadro lleva el bit de mascara: asi una copia de la pantalla usada como textura de 15 bits no
	 * tiene negros transparentes (0x0000) y se puede mezclar (la GPU solo mezcla texeles con ese bit) */
	if (stp) {
		setDrawStp(stp, 1, 0);
		video_add(LAYER_BG, stp);        /* ultimo en la capa del fondo = lo primero en dibujarse */
	}
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

/* Copia la vista 16:9 del ultimo cuadro terminado a VRAM (x, y) */
void video_snapshot(int x, int y)
{
	RECT r;

	DrawSync(0);
	setRECT(&r, 0, draw[!db].clip.y + VIEW_Y, SCREEN_W, VIEW_H);
	MoveImage2(&r, x, y);          /* directa: MoveImage (con cola e interrupcion) detenia el vblank en PCSX-Redux */
	DrawSync(0);
}

/* Dibuja la copia como textura directa de 15 bits; blend como en video_rect */
void video_snapshot_draw(int layer, int x, int y, int blend)
{
	int col;

	for (col = 0; col < SCREEN_W; col += 256) {
		SPRT *s = (SPRT *)video_alloc(sizeof(SPRT));
		int w = SCREEN_W - col < 256 ? SCREEN_W - col : 256;

		if (!s)
			return;
		setSprt(s);
		setXY0(s, col, VIEW_Y);
		setWH(s, w, VIEW_H);
		setUV0(s, 0, y & 255);
		setRGB0(s, 128, 128, 128);
		setSemiTrans(s, blend != 0);
		video_add(layer, s);
		video_set_tpage(layer, 2, blend ? blend - 1 : 0, x + col, y);
	}
}

/* Origen vertical (en VRAM) del framebuffer donde se dibuja el cuadro actual */
int video_draw_origin_y(void)
{
	return draw[db].clip.y;
}
