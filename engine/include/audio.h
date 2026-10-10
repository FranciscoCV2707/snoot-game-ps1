/*
 * Audio (Fase 8): musica XA en 16 carriles (docs/formato-audio.md), ambientes en bucle y efectos en la SPU.
 *
 * Musica: un solo flujo XA. Bucles por cuenta de sectores, intro -> bucle sin buscar (MUSIC_QUEUE), finales de familia
 * por cambio de carril y mezclas de stems por cambio de carril en la misma posicion.
 * Efectos y ambientes: se cargan del CD a la RAM de la SPU bajo demanda (cache) o antes con audio_preload.
 * Toda lectura del CD pausa la musica y la reanuda en la misma posicion (D7): cd_read_* llama a audio_cd_begin/end.
 */
#pragma once

#include <stdint.h>

#define AUDIO_CH_MUSIC 0          /* canales de VOLUME: 0 musica, 1-4 ambientes, 5 efectos */
#define AUDIO_CH_SFX 5

int audio_init(void);
void audio_update(void);          /* una vez por cuadro: bucles, cambios de pista y fundidos */

void audio_music_play(int id, int fade_tenths, int flags);
void audio_music_queue(int id);
void audio_music_stop(int fade_tenths);
void audio_ambient_play(int slot, int id, int fade_tenths);
void audio_ambient_stop(int slot, int fade_tenths);
void audio_sfx_play(int id);
void audio_sfx_stop(void);
void audio_volume(int channel, int volume, int time_tenths);
void audio_stop_all(void);

/* Carga un efecto o ambiente a la SPU si no esta (para no leer el CD justo cuando suena) */
void audio_preload(int id);
/* Volumen de las opciones, 0-10 */
void audio_set_levels(int music, int sfx);

void audio_cd_begin(void);
void audio_cd_end(void);
