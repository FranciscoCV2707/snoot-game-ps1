/*
 * Logica de escena portable (sin nada de la PS1): orden de dibujo, aspecto de cada sprite en un instante de su
 * animacion y mezcla de los colores solidos. La usan el motor (main.c) y el arnes de la auditoria visual
 * (tools/audit/ps1_frames.c).
 */
#pragma once

#include <stdint.h>
#include "vm.h"

typedef struct {
	int image, flip;     /* imagen a dibujar (los eventos de la animacion la cambian) */
	int xa, ya;          /* alineacion 8.8 (0 = izquierda/arriba, 256 = derecha/abajo) */
	int alpha;           /* 0-255 */
	int zoom;            /* 1/64 (64 = 1.0) */
	int r, g, b;         /* modulacion de color (128 = sin cambio) */
} SpriteLook;

/* Mezcla de un rectangulo de color con la GPU: mode 0 opaco; si no, modo de la GPU + 1 (1 = 50%, 2 = suma,
 * 3 = resta, 4 = suma de 1/4), aplicado `passes` veces con el color (r, g, b). passes = 0: no se dibuja. */
typedef struct {
	int mode, passes, r, g, b;
} SolidBlend;

#define SCENE_HIDDEN_ALPHA 32    /* por debajo de este alfa el sprite no se dibuja */
#define SCENE_SETTLED (-1)       /* tiempo "animacion terminada" (al saltar y en la auditoria) */
#define SCENE_MAX_EVENTS 16

void scene_set_positions(const int16_t *pos_x, const int16_t *pos_y, int count);
const uint8_t *scene_anim(const Vm *vm, int anim);
/* Sprites con imagen ordenados de atras (0) hacia adelante; devuelve cuantos */
int scene_sorted(const Vm *vm, const VmSprite **order);
/* Aspecto del sprite `t` cuadros despues de empezar su animacion (SCENE_SETTLED: al terminar; si se repite, en su
 * primera clave). Con animacion manda su posicion (ya parte de la posicion con nombre); sin ella, la con nombre. */
void scene_look(const Vm *vm, const VmSprite *s, int t, SpriteLook *out);
/* Imagenes que la animacion del sprite muestra en sus eventos (para cargarlas antes); devuelve cuantas */
int scene_event_images(const Vm *vm, const VmSprite *s, uint16_t *out, int max);
/* Como dibujar un color solido rgba (por ejemplo dimmer_light = negro al 40%) con alfa extra `alpha` del sprite */
void scene_solid_blend(const uint8_t *rgba, int alpha, SolidBlend *out);
