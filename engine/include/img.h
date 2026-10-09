/* Imagenes IMG1 (docs/formato-img.md): carga a VRAM y dibujo. */
#pragma once

#include <stdint.h>

typedef struct {
	uint8_t kind, flags;
	uint16_t full_w, full_h;      /* tamano logico a 320x240 */
	uint16_t x, y, w, h;          /* bitmap dentro del tamano logico (w par) */
	uint16_t vram_x, vram_y, clut_y;
	uint8_t loaded;
} Image;

/* Descomprime y sube la imagen a VRAM en (vram_x, vram_y) con su paleta en la fila clut_y. Devuelve 0 si salio bien. */
int img_load(Image *img, const uint8_t *file, int file_size, int vram_x, int vram_y, int clut_y);
/* Dibuja la imagen con el origen logico en (screen_x, screen_y). Los 256 px de ancho de una pagina de textura
 * obligan a partir los fondos de 320 px en dos sprites. */
void img_draw(const Image *img, int layer, int screen_x, int screen_y);
