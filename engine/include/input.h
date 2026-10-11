/* Control: botones con deteccion de pulsacion. */
#pragma once

#include <stdint.h>

void input_init(int with_card);
void input_update(void);
int input_down(uint16_t mask);       /* esta presionado ahora */
int input_pressed(uint16_t mask);    /* se acaba de presionar en este cuadro */
int input_raw_down(uint16_t mask);   /* presionado, leido directo del control (antes del bucle principal) */
/* Prueba automatica: botones fijos por cuadro (AUTOTEST.BIN del disco, ver tools/engine/emutest.py) */
void input_set_script(const uint8_t *entries, int count);
/* El guion puede activar el modo autoplay (prueba de recorrido) y pedir salir del emulador */
extern volatile uint32_t autotest_autoplay, autotest_quit;
