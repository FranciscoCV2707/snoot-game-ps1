#include <stdio.h>
#include <string.h>
#include <psxapi.h>
#include <psxcd.h>
#include "audio.h"
#include "cd.h"

/* Tabla de sectores (FILES.BIN, la arma tools/engine/build_game.py): nombre de 12 bytes, sector y tamano, ordenada
 * por nombre. Evita CdSearchFile, que vuelve a leer el directorio del disco (una busqueda mas en cada carga). */
#define MAX_FILES 1100
#define ENTRY_BYTES 20

static uint8_t table[6 + MAX_FILES * ENTRY_BYTES + 2048] __attribute__((aligned(4)));
static int table_count;

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int search_file(const char *path, int *lba, int *size)
{
	CdlFILE file;

	if (!CdSearchFile(&file, path)) {
		printf("cd: no se encuentra %s\n", path);
		return -1;
	}
	*lba = CdPosToInt(&file.pos);
	*size = (int)file.size;
	return 0;
}

int cd_init(void)
{
	int lba, size;

	if (!CdInit())
		return 0;
	if (search_file("\\DATA\\FILES.BIN", &lba, &size) == 0 && size <= (int)sizeof(table) &&
	    cd_read_sectors(lba, (size + 2047) / 2048, table) == 0 && memcmp(table, "FTB1", 4) == 0) {
		table_count = table[4] | (table[5] << 8);
		if (table_count > MAX_FILES)
			table_count = MAX_FILES;
	}
	return 1;
}

int cd_find(const char *path, int *lba, int *size)
{
	const char *name = strrchr(path, '\\');
	int lo = 0, hi = table_count - 1;

	name = name ? name + 1 : path;
	while (lo <= hi) {
		int mid = (lo + hi) / 2, cmp;
		const uint8_t *e = table + 6 + mid * ENTRY_BYTES;

		cmp = strncmp(name, (const char *)e, 12);
		if (cmp == 0) {
			*lba = (int)rd32(e + 12);
			*size = (int)rd32(e + 16);
			return 0;
		}
		if (cmp < 0)
			hi = mid - 1;
		else
			lo = mid + 1;
	}
	return search_file(path, lba, size);       /* sin tabla (discos viejos) o archivo que no esta en ella */
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
