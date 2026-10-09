#include <stdio.h>
#include <psxapi.h>
#include <psxcd.h>
#include "cd.h"

int cd_init(void)
{
	return CdInit();
}

int cd_read_file(const char *path, void *buf, int buf_bytes)
{
	CdlFILE file;
	int sectors;

	/* Fase 6: la busqueda por nombre alcanza para la demo; el juego completo usa una tabla de sectores precalculada. */
	if (!CdSearchFile(&file, path)) {
		printf("cd: no se encuentra %s\n", path);
		return -1;
	}
	sectors = (file.size + 2047) / 2048;
	if (sectors * 2048 > buf_bytes) {
		printf("cd: %s no cabe en el buffer\n", path);
		return -1;
	}
	CdControl(CdlSetloc, &file.pos, 0);
	if (!CdRead(sectors, (uint32_t *)buf, CdlModeSpeed))
		return -1;
	if (CdReadSync(0, 0) < 0)
		return -1;
	return file.size;
}
