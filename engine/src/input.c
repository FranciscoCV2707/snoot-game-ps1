#include <psxapi.h>
#include <psxgpu.h>
#include <psxpad.h>
#include "input.h"

static char padbuff[2][34];
static uint16_t cur, prev;          /* 1 = presionado */
static const uint8_t *script;       /* prueba automatica (AUTOTEST.BIN): pares (cuadro u32, botones u16) */
static int script_count;

/* La prueba automatica pide capturas y salir con valores especiales; el Lua del emulador lee estas variables */
#define SCRIPT_SHOT 0xFFFF
#define SCRIPT_QUIT 0xFFFE
#define SCRIPT_AUTOPLAY 0xFFFD
volatile uint32_t autotest_shot, autotest_quit, autotest_autoplay;
static uint8_t script_done[2800];
static int script_base = -1;

void input_init(int with_card)
{
	/* control y memory card comparten el puerto: se inician juntos (la memory card la usa save.c). Sin memory card
	 * no se instala su controlador de la BIOS (en POPStarter dejaba colgado el CD). */
	InitPAD(padbuff[0], 34, padbuff[1], 34);
	if (with_card)
		InitCARD(1);
	StartPAD();
	if (with_card) {
		StartCARD();
		_bu_init();
	}
	ChangeClearPAD(0);
	cur = prev = 0;
}

void input_set_script(const uint8_t *entries, int count)
{
	script = entries;
	script_count = count;
}

void input_update(void)
{
	PADTYPE *pad = (PADTYPE *)padbuff[0];
	int i, now;

	prev = cur;
	cur = 0;
	if (pad->stat == 0 && (pad->type == 0x4 || pad->type == 0x5 || pad->type == 0x7))
		cur = (uint16_t)~pad->btn;     /* el hardware entrega los botones en 0 al presionarse */
	/* guion de prueba */
	if (script_base < 0)
		script_base = VSync(-1);   /* el guion cuenta desde la primera vuelta del bucle (titulo) */
	now = VSync(-1) - script_base;
	for (i = 0; i < script_count; i++) {
		const uint8_t *e = script + 6 * i;
		int at = e[0] | (e[1] << 8) | (e[2] << 16) | (e[3] << 24);

		int buttons = e[4] | (e[5] << 8);

		/* cada entrada actua una sola vez (un cuadro), aunque una carga se haya comido su cuadro exacto */
		if (now < at || script_done[i])
			continue;
		script_done[i] = 1;
		if (buttons == SCRIPT_SHOT)
			autotest_shot++;
		else if (buttons == SCRIPT_QUIT)
			autotest_quit = 1;
		else if (buttons == SCRIPT_AUTOPLAY)
			autotest_autoplay = 1;
		else
			cur |= (uint16_t)buttons;
	}
}

/* Estado del control sin pasar por input_update (antes del bucle principal; no arranca el guion de prueba) */
int input_raw_down(uint16_t mask)
{
	PADTYPE *pad = (PADTYPE *)padbuff[0];

	return pad->stat == 0 && (~pad->btn & mask) != 0;
}

int input_down(uint16_t mask)
{
	return (cur & mask) != 0;
}

int input_pressed(uint16_t mask)
{
	return ((cur & ~prev) & mask) != 0;
}
