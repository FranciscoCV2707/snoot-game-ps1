/* Video: GPU, doble buffer, tabla de orden por capas y memoria de primitivas. */
#pragma once

#include <stdint.h>
#include <psxgpu.h>

#define SCREEN_W 320
#define SCREEN_H 240
#define VIEW_Y   30            /* la imagen 16:9 de 320x180 va centrada en la pantalla de 4:3 */
#define VIEW_H   180

/* Capas: 0 se dibuja al final (al frente). Dentro de una capa, lo agregado despues se dibuja antes. */
#define LAYER_DEBUG   0
#define LAYER_TEXT    1
#define LAYER_BOX     2
#define LAYER_SPRITE0 3        /* 3..8: sprites; el menor numero queda al frente */
#define LAYER_BG      9
#define LAYER_COUNT   10

/* Posiciones en VRAM (palabras de 16 bits), ver docs/presupuesto-memoria.md */
#define VRAM_BG_X      640
#define VRAM_BG_Y      0
#define VRAM_SPRITE_X  320
#define VRAM_SPRITE_Y  0
#define VRAM_FONT_X    960
#define VRAM_FONT_Y    0
#define CLUT_BG_Y      480
#define CLUT_SPRITE_Y  481
#define CLUT_FONT_X    0
#define CLUT_FONT_Y    500

void video_init(void);
void *video_alloc(int size);
void video_add(int layer, void *prim);
void video_set_tpage(int layer, int mode, int abr, int x, int y);
void video_rect(int layer, int x, int y, int w, int h, int r, int g, int b, int blend);
void video_triangle_down(int layer, int x, int y, int w, int h, int r, int g, int b);
void video_flip(void);
int video_frames(void);
void video_clip_scene(void);   /* llamar despues de agregar la escena (se dibuja primero) */
void video_unclip(void);       /* llamar despues de agregar la caja de texto y la interfaz */
