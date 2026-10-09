#pragma once

#include <stdint.h>

/* Decodifica un bloque LZ4 sin cabecera. Devuelve los bytes escritos en dst o -1 si hay un error. */
int lz4_decode(const uint8_t *src, int src_size, uint8_t *dst, int dst_size);
