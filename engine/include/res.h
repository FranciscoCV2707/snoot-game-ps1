/* Gestor de imagenes en VRAM: carga bajo demanda desde el CD y reutiliza lo ya cargado. */
#pragma once
#include "img.h"

/* Llamar al empezar a preparar una escena: lo que se pida desde aqui no se desaloja hasta la siguiente llamada. */
void res_new_scene(void);
/* Devuelve la imagen cargada (0 si no existe o no cabe en VRAM). */
const Image *res_get(int image_id);
/* Igual que res_get pero sin leer del CD: 0 si la imagen no esta ya cargada. */
const Image *res_peek(int image_id);
/* Banda de VRAM para una copia de la pantalla (transiciones): desaloja lo que haya y la marca ocupada */
void res_reserve_snapshot(int *vram_x, int *vram_y);
void res_release_snapshot(void);
/* Lee de una vez a la cache de RAM las imagenes de la lista que no esten en VRAM (las que vienen en el guion);
 * descarta de la cache las que ya no estan en la lista */
void res_prefetch(const uint16_t *ids, int n);
