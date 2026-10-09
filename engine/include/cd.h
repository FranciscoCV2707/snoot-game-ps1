/* Lectura de archivos del CD a RAM. */
#pragma once

#include <stdint.h>

int cd_init(void);
/* Lee un archivo (ruta tipo "\\FONT.BIN") al buffer, que debe tener tamano multiplo de 2048 y alineacion de 4.
 * Devuelve el tamano del archivo o -1 si no existe o no cabe. */
int cd_read_file(const char *path, void *buf, int buf_bytes);
