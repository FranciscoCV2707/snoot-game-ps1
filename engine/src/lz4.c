#include "lz4.h"

int lz4_decode(const uint8_t *src, int src_size, uint8_t *dst, int dst_size)
{
	const uint8_t *ip = src;
	const uint8_t *iend = src + src_size;
	uint8_t *op = dst;
	uint8_t *oend = dst + dst_size;

	while (ip < iend) {
		unsigned token = *ip++;
		int literals = token >> 4;
		int match;
		unsigned offset;

		if (literals == 15) {
			unsigned b;
			do {
				if (ip >= iend)
					return -1;
				b = *ip++;
				literals += b;
			} while (b == 255);
		}
		if (ip + literals > iend || op + literals > oend)
			return -1;
		while (literals--)
			*op++ = *ip++;
		if (ip >= iend)
			break;                       /* el ultimo bloque solo trae literales */

		if (ip + 2 > iend)
			return -1;
		offset = ip[0] | (ip[1] << 8);
		ip += 2;
		if (offset == 0 || (int)offset > op - dst)
			return -1;
		match = token & 15;
		if (match == 15) {
			unsigned b;
			do {
				if (ip >= iend)
					return -1;
				b = *ip++;
				match += b;
			} while (b == 255);
		}
		match += 4;
		if (op + match > oend)
			return -1;
		{
			const uint8_t *mp = op - offset;
			while (match--)
				*op++ = *mp++;           /* copia byte a byte: el origen y el destino pueden solaparse */
		}
	}
	return (int)(op - dst);
}
