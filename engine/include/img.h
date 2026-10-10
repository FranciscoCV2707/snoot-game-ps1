/* Imagenes IMG1 (docs/formato-img.md): carga a VRAM y dibujo. */
#pragma once

#include <stdint.h>

typedef struct {
	uint8_t kind, flags;
	uint16_t full_w, full_h;      /* tamano logico a 320x240 */
	uint16_t x, y, w, h;          /* bitmap dentro del tamano logico (w par) */
	uint16_t vram_x, vram_y, clut_y;
	uint8_t solid[4];             /* r, g, b, a de las imagenes de color solido */
	uint8_t loaded;
	uint8_t big;                  /* fondo mas grande que la VRAM disponible: vive en RAM (img_load_big) */
} Image;

#define BIG_WIN_W 320             /* ventana visible de un fondo grande: lo que ocupa en VRAM */
#define BIG_WIN_H 180

/* Descomprime y sube la imagen a VRAM en (vram_x, vram_y) con su paleta en la fila clut_y. Devuelve 0 si salio bien. */
int img_load(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y);
/* Dibuja la imagen con el origen logico en (screen_x, screen_y). Los 256 px de ancho de una pagina de textura
 * obligan a partir los fondos de 320 px en dos sprites. */
void img_draw(const Image *img, int layer, int screen_x, int screen_y);
/* Igual que img_draw; flip espeja la imagen completa (SHOW con el bit de espejo). */
void img_draw_flip(const Image *img, int layer, int screen_x, int screen_y, int flip);
/* Con zoom (1/64) y modulacion de color (128 = sin cambio); el origen logico ya escalado va en (screen_x, screen_y). */
void img_draw_ex(const Image *img, int layer, int screen_x, int screen_y, int flip, int zoom, int r, int g, int b);

/* Fondos que se recorren con Pan (mas grandes que la VRAM libre): la imagen completa se descomprime en RAM y a
 * VRAM, en (vram_x, vram_y), solo sube la ventana de BIG_WIN_W x BIG_WIN_H visible. Solo uno a la vez. */
int img_load_big(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y);
/* Dibuja la ventana con el origen logico de la imagen en (screen_x, screen_y) (valores <= 0 al recorrerla). */
void img_draw_big(const Image *img, int layer, int screen_x, int screen_y);
