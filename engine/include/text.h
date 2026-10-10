/* Fuente de 4 bits, texto con codigos de control y efecto de maquina de escribir (docs/bytecode.md seccion 6). */
#pragma once

#include <stdint.h>

#define TEXT_STYLE   1
#define TEXT_WAIT    2
#define TEXT_SPEED   3
#define TEXT_NOWAIT  4
#define TEXT_FAST    5
#define TEXT_SIZE    6
#define TEXT_NEWLINE 0x0A
#define TEXT_PAGE    0x0B
#define TEXT_DEFAULT_CPS 50

typedef struct {
	const char *start;     /* cadena completa */
	const char *page;      /* inicio de la pagina actual */
	const char *pos;       /* hasta donde llega lo revelado */
	int cps;               /* caracteres por segundo */
	int acc;               /* acumulador 8.8 de caracteres */
	int wait;              /* cuadros de espera restantes */
	uint8_t style;         /* estilo vigente en `pos` */
	uint8_t at_page_end;   /* se llego a un salto de pagina y falta un boton */
	uint8_t at_end;        /* se reveló toda la cadena */
	uint8_t auto_next;     /* la cadena trae {nw}: avanza sola al terminar */
} TextRun;

int font_load(const uint8_t *file, int size);
int font_line_height(void);
/* Dibuja una cadena sin efecto de escritura (interfaz, depuracion). El color es un tinte (128 = blanco). */
void font_draw(int layer, int x, int y, const char *utf8, int r, int g, int b);
/* Ancho en pixeles de la primera linea */
int font_width(const char *utf8);

void text_start(TextRun *t, const char *utf8);
void text_update(TextRun *t);                  /* un cuadro de revelado */
void text_reveal_page(TextRun *t);             /* muestra de golpe lo que falta de la pagina */
int text_page_done(const TextRun *t);          /* la pagina esta completa y espera un boton */
int text_finished(const TextRun *t);           /* ademas es la ultima pagina */
void text_next_page(TextRun *t);
void text_draw(const TextRun *t, int layer, int x, int y, int r, int g, int b);
