"""Entrelaza varios archivos XA (uno por canal) en un solo archivo XA.

El lector de CD entrega 150 sectores por segundo a 2x. Una pista de 37.8 kHz estereo
consume un sector de cada 8, asi que ocho pistas entrelazadas llenan el flujo sin
desperdiciar espacio. Cada entrada debe codificarse antes con `psxavenc -t xa -F <archivo> -C <canal>`
(canal distinto para cada pista).
"""
import argparse
import sys
from pathlib import Path

SECTOR_SIZE = 2336
SUBHEADER_SIZE = 8
SUBMODE_OFFSET = 2
END_FLAGS = 0x81  # fin de registro (bit 0) y fin de archivo (bit 7)


def read_sectors(path):
    data = Path(path).read_bytes()
    if len(data) % SECTOR_SIZE:
        raise ValueError(f"{path}: el tamano no es multiplo de {SECTOR_SIZE}")
    return [data[i:i + SECTOR_SIZE] for i in range(0, len(data), SECTOR_SIZE)]


def padding_sector(template):
    """Sector de silencio con el mismo archivo/canal que la pista y sin banderas de fin."""
    header = bytearray(template[:SUBHEADER_SIZE])
    for offset in (SUBMODE_OFFSET, SUBMODE_OFFSET + 4):
        header[offset] &= ~END_FLAGS & 0xFF
    return bytes(header) + bytes(SECTOR_SIZE - SUBHEADER_SIZE)


def interleave(paths, channels=8):
    if not 1 <= len(paths) <= channels:
        raise ValueError(f"se esperan entre 1 y {channels} archivos")
    tracks = [read_sectors(p) for p in paths]
    slots = max(len(t) for t in tracks)
    pads = [padding_sector(t[0]) for t in tracks]
    out = bytearray()
    for slot in range(slots):
        for index in range(channels):
            if index < len(tracks) and slot < len(tracks[index]):
                out += tracks[index][slot]
            elif index < len(tracks):
                out += pads[index]
            else:
                out += pads[0]
    return bytes(out), slots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--channels", type=int, default=8)
    args = parser.parse_args()
    data, slots = interleave(args.inputs, args.channels)
    Path(args.output).write_bytes(data)
    print(f"{len(args.inputs)} pistas, {slots} ranuras, {len(data) // SECTOR_SIZE} sectores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
