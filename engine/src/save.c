#include <stdio.h>
#include <string.h>
#include <psxapi.h>
#include <sys/fcntl.h>
#include "save.h"

#define BLOCK_BYTES 8192
#define HEADER_BYTES 256
#define TITLE "SNOOT GAME"

static const char *const file_name[2] = { "bu00:BASLUS-99999SNOOTA", "bu00:BASLUS-99999SNOOTB" };
static uint8_t block[BLOCK_BYTES] __attribute__((aligned(4)));
static uint8_t icon[32 + 128];
static uint32_t last_counter;
static int last_copy = -1;            /* copia leida o escrita por ultima vez (la siguiente escritura va a la otra) */

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void wr32(uint8_t *p, uint32_t v)
{
	p[0] = (uint8_t)v;
	p[1] = (uint8_t)(v >> 8);
	p[2] = (uint8_t)(v >> 16);
	p[3] = (uint8_t)(v >> 24);
}

static uint32_t checksum(const uint8_t *data)
{
	uint32_t sum = 0x5A17u;
	int i;

	for (i = SAVE_CONTROL_BYTES; i < SAVE_DATA_BYTES; i++)
		sum = (sum << 5) + sum + data[i];   /* djb2 */
	return sum;
}

void save_set_icon(const uint8_t *data)
{
	memcpy(icon, data, sizeof(icon));
}

/* La BIOS muestra el titulo en Shift-JIS: el ASCII se pasa a caracteres de ancho completo */
static void header(uint8_t *p)
{
	const char *s;
	int n = 0;

	memset(p, 0, HEADER_BYTES);
	p[0] = 'S';
	p[1] = 'C';
	p[2] = 0x11;                       /* icono de 1 cuadro */
	p[3] = 1;                          /* bloques */
	for (s = TITLE; *s && n < 62; s++, n += 2) {
		int c = *s, code = 0x8140;

		if (c >= 'A' && c <= 'Z')
			code = 0x8260 + (c - 'A');
		else if (c >= 'a' && c <= 'z')
			code = 0x8281 + (c - 'a');
		else if (c >= '0' && c <= '9')
			code = 0x824F + (c - '0');
		p[4 + n] = (uint8_t)(code >> 8);
		p[5 + n] = (uint8_t)code;
	}
	memcpy(p + 0x60, icon, sizeof(icon));
}

static int read_copy(int copy, uint8_t *data, uint32_t *counter)
{
	int fd = open(file_name[copy], FREAD), n;

	if (fd < 0)
		return -1;
	n = read(fd, block, BLOCK_BYTES);
	close(fd);
	if (n != BLOCK_BYTES || memcmp(block + HEADER_BYTES, "SNS1", 4) != 0)
		return -1;
	if (rd32(block + HEADER_BYTES + 8) != checksum(block + HEADER_BYTES))
		return -1;
	memcpy(data, block + HEADER_BYTES, SAVE_DATA_BYTES);
	*counter = rd32(block + HEADER_BYTES + 4);
	return 0;
}

static int card_present(void)
{
	struct DIRENTRY entry;

	/* sin memory card la BIOS no puede listar el directorio; con una vacia firstfile tambien da NULL, por eso se
	 * intenta ademas abrir cualquiera de las dos copias */
	return firstfile("bu00:*", &entry) != 0;
}

SaveResult save_read(uint8_t *data)
{
	static uint8_t other[SAVE_DATA_BYTES];
	uint32_t c0 = 0, c1 = 0;
	int ok0 = read_copy(0, data, &c0) == 0;
	int ok1 = read_copy(1, other, &c1) == 0;

	if (!ok0 && !ok1)
		return card_present() ? SAVE_NO_FILE : SAVE_NO_CARD;
	if (ok1 && (!ok0 || c1 > c0)) {
		memcpy(data, other, SAVE_DATA_BYTES);
		last_copy = 1;
		last_counter = c1;
	} else {
		last_copy = 0;
		last_counter = c0;
	}
	return SAVE_OK;
}

SaveResult save_write(uint8_t *data)
{
	int copy = last_copy == 0 ? 1 : 0, fd, n;

	memcpy(data, "SNS1", 4);
	wr32(data + 4, ++last_counter);
	wr32(data + 8, checksum(data));
	wr32(data + 12, 0);
	header(block);
	memcpy(block + HEADER_BYTES, data, SAVE_DATA_BYTES);

	fd = open(file_name[copy], FWRITE);
	if (fd < 0) {
		fd = open(file_name[copy], FCREATE | (1 << 16));   /* el bloque se crea vacio y se abre de nuevo */
		if (fd < 0)
			return card_present() ? SAVE_FULL : SAVE_NO_CARD;
		close(fd);
		fd = open(file_name[copy], FWRITE);
		if (fd < 0)
			return SAVE_WRITE_ERROR;
	}
	n = write(fd, block, BLOCK_BYTES);
	close(fd);
	if (n != BLOCK_BYTES)
		return SAVE_WRITE_ERROR;
	last_copy = copy;
	return SAVE_OK;
}
