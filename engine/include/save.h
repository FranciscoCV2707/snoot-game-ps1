/*
 * Memory card (D10): el juego guarda un bloque de datos en dos archivos alternados de 1 bloque cada uno
 * (BASLUS-99999SNOOTA y ...B). Cada copia lleva numero de guardado y checksum; al leer se usa la mas reciente
 * que este sana, asi un apagado a mitad de un guardado no borra el progreso.
 */
#pragma once

#include <stdint.h>

#define SAVE_DATA_BYTES (8192 - 256)   /* un bloque menos la cabecera de la BIOS e icono de 1 cuadro */
#define SAVE_CONTROL_BYTES 16          /* "SNS1", numero de guardado, checksum, reservado: lo llena save.c */

typedef enum {
	SAVE_OK = 0,
	SAVE_NO_CARD = -1,                 /* no hay memory card en la ranura 1 */
	SAVE_NO_FILE = -2,                 /* hay memory card pero no hay partida (o esta danada) */
	SAVE_FULL = -3,                    /* no se pudo crear el archivo: memory card llena */
	SAVE_WRITE_ERROR = -4
} SaveResult;

/* Lee el icono (MCICON.BIN: 16 colores + 16x16 a 4 bits) para la cabecera */
void save_set_icon(const uint8_t *icon_palette_and_pixels);
/* Lee la copia buena mas reciente a `data` (SAVE_DATA_BYTES) */
SaveResult save_read(uint8_t *data);
/* Escribe `data` en la copia mas vieja (los primeros SAVE_CONTROL_BYTES los completa save.c) */
SaveResult save_write(uint8_t *data);
