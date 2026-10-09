/* Gestor de imagenes en VRAM: carga bajo demanda desde el CD y reutiliza lo ya cargado. */
#pragma once
#include "img.h"

/* Llamar al empezar a preparar una escena: lo que se pida desde aqui no se desaloja hasta la siguiente llamada. */
void res_new_scene(void);
/* Devuelve la imagen cargada (0 si no existe o no cabe en VRAM). */
const Image *res_get(int image_id);
