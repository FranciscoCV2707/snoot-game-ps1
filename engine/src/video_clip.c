/* Recorte del area de dibujo: la escena se dibuja solo dentro del recuadro 16:9 de 320x180. */
#include <psxgpu.h>
#include "video.h"

extern int video_draw_origin_y(void);

void video_clip_scene(void)
{
	DR_AREA *a = (DR_AREA *)video_alloc(sizeof(DR_AREA));
	RECT r;

	if (!a)
		return;
	setRECT(&r, 0, video_draw_origin_y() + VIEW_Y, SCREEN_W, VIEW_H);
	setDrawArea(a, &r);
	video_add(LAYER_BG, a);
}

void video_unclip(void)
{
	DR_AREA *a = (DR_AREA *)video_alloc(sizeof(DR_AREA));
	RECT r;

	if (!a)
		return;
	setRECT(&r, 0, video_draw_origin_y(), SCREEN_W, SCREEN_H);
	setDrawArea(a, &r);
	video_add(LAYER_BOX, a);
}
