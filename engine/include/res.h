/* Gestor de imagenes en VRAM: carga bajo demanda desde el CD y reutiliza lo ya cargado. */
#pragma once
#include "img.h"

/* Llamar al empezar a preparar una escena: lo que se pida desde aqui no se desaloja hasta la siguiente llamada. */
void res_new_scene(void);
/* Devuelve la imagen cargada (0 si no existe o no cabe en VRAM). */
const Image *res_get(int image_id);
/* Marca como de la escena actual una imagen si ya esta cargada (no lee nada) */
void res_touch(int image_id);
/* Carga opcional (cuadros que una animacion muestra despues): solo usa VRAM libre o de escenas anteriores */
void res_preload(int image_id);
/* Llamar una vez por cuadro: lo que no se dibujo en este cuadro ni en el anterior se puede desalojar para dibujar */
void res_tick(void);
/* Igual que res_get pero sin leer del CD: 0 si la imagen no esta ya cargada. */
const Image *res_peek(int image_id);
/* Banda de VRAM para una copia de la pantalla (transiciones): desaloja lo que haya y la marca ocupada. Devuelve 0
 * (sin reservar) si para eso habria que quitar algo que se esta dibujando. */
int res_reserve_snapshot(int *vram_x, int *vram_y);
void res_release_snapshot(void);
/* Lee de una vez a la cache de RAM las imagenes de la lista que no esten en VRAM (las que vienen en el guion);
 * descarta de la cache las que ya no estan en la lista */
void res_prefetch(const uint16_t *ids, int n);
