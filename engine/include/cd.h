/* Lectura de archivos del CD a RAM. Cada lectura pausa la musica XA y la reanuda (audio_cd_begin/end). */
#pragma once

#include <stdint.h>

int cd_init(void);
/* Sector inicial y tamano en bytes de un archivo (ruta tipo "\\DATA\\FONT.BIN"). 0 si existe. */
int cd_find(const char *path, int *lba, int *size);
/* Lee `sectors` sectores de 2048 bytes desde `lba`. 0 si salio bien. */
int cd_read_sectors(int lba, int sectors, void *buf);
/* Lee un archivo al buffer, que debe tener tamano multiplo de 2048 y alineacion de 4.
 * Devuelve el tamano del archivo o -1 si no existe o no cabe. */
int cd_read_file(const char *path, void *buf, int buf_bytes);
