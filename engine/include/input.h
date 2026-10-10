/* Control: botones con deteccion de pulsacion. */
#pragma once

#include <stdint.h>

void input_init(void);
void input_update(void);
int input_down(uint16_t mask);       /* esta presionado ahora */
int input_pressed(uint16_t mask);    /* se acaba de presionar en este cuadro */
/* Prueba automatica: botones fijos por cuadro (AUTOTEST.BIN del disco, ver tools/engine/emutest.py) */
void input_set_script(const uint8_t *entries, int count);
