#include <stdio.h>
#include <psxapi.h>
#include <psxcd.h>
#include "audio.h"
#include "cd.h"

int cd_init(void)
{
	return CdInit();
}

int cd_find(const char *path, int *lba, int *size)
{
	CdlFILE file;

	/* la busqueda por nombre alcanza por ahora; la tabla de sectores precalculada llega en la Fase 9 */
	if (!CdSearchFile(&file, path)) {
		printf("cd: no se encuentra %s\n", path);
		return -1;
	}
	*lba = CdPosToInt(&file.pos);
	*size = (int)file.size;
	return 0;
}

int cd_read_sectors(int lba, int sectors, void *buf)
{
	CdlLOC loc;
	int ok;

	audio_cd_begin();                /* la musica XA se pausa durante la lectura (D7) */
	CdIntToPos(lba, &loc);
	CdControl(CdlSetloc, &loc, 0);
	ok = CdRead(sectors, (uint32_t *)buf, CdlModeSpeed) && CdReadSync(0, 0) >= 0;
	audio_cd_end();
	return ok ? 0 : -1;
}

int cd_read_file(const char *path, void *buf, int buf_bytes)
{
	int lba, size, sectors;

	if (cd_find(path, &lba, &size) != 0)
		return -1;
	sectors = (size + 2047) / 2048;
	if (sectors * 2048 > buf_bytes) {
		printf("cd: %s no cabe en el buffer\n", path);
		return -1;
	}
	if (cd_read_sectors(lba, sectors, buf) != 0)
		return -1;
	return size;
}
