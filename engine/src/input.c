#include <psxapi.h>
#include <psxpad.h>
#include "input.h"

static char padbuff[2][34];
static uint16_t cur, prev;          /* 1 = presionado */

void input_init(void)
{
	InitPAD(padbuff[0], 34, padbuff[1], 34);
	StartPAD();
	ChangeClearPAD(0);
	cur = prev = 0;
}

void input_update(void)
{
	PADTYPE *pad = (PADTYPE *)padbuff[0];

	prev = cur;
	cur = 0;
	if (pad->stat == 0 && (pad->type == 0x4 || pad->type == 0x5 || pad->type == 0x7))
		cur = (uint16_t)~pad->btn;     /* el hardware entrega los botones en 0 al presionarse */
}

int input_down(uint16_t mask)
{
	return (cur & mask) != 0;
}

int input_pressed(uint16_t mask)
{
	return ((cur & ~prev) & mask) != 0;
}
