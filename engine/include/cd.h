/* Lectura de archivos del CD a RAM. Cada lectura pausa la musica XA y la reanuda (audio_cd_begin/end). */
#pragma once

#include <stdint.h>

int cd_init(void);
/* Sector inicial y tamano en bytes de un archivo (ruta tipo "\\DATA\\FONT.BIN"). 0 si existe. */
int cd_find(const char *path, int *lba, int *size);
/* Lee `sectors` sectores de 2048 bytes desde `lba`. 0 si salio bien. */
int cd_read_sectors(int lba, int sectors, void *buf);
/* Lectura en segundo plano (sin pausar la musica: quien la usa la pausa), una a la vez. `owner` separa a quienes la
 * usan. cd_read_poll: 1 leyendo, 0 lista, -1 error. cd_busy: hay una en curso. cd_wait espera a que termine; las
 * lecturas normales y los comandos de la musica la esperan solos. */
#define CD_OWNER_RES 0
#define CD_OWNER_AUDIO 1
#define CD_OWNERS 2
int cd_read_start(int owner, int lba, int sectors, void *buf);
int cd_read_poll(int owner);
int cd_busy(void);
void cd_wait(void);
/* Lee un archivo al buffer, que debe tener tamano multiplo de 2048 y alineacion de 4.
 * Devuelve el tamano del archivo o -1 si no existe o no cabe. */
int cd_read_file(const char *path, void *buf, int buf_bytes);
