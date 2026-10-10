"""Genera build/data/FONT.BIN: atlas de fuente de 4 bits (16 niveles de gris) para el motor.

Los glifos salen de las cadenas de TEXT_ES.BIN (todo lo que el juego puede mostrar) mas el ASCII imprimible y los
nombres de hablantes. Cada glifo existe en estilo normal y cursiva (inclinada). El motor suma el color al fondo con
mezcla aditiva, asi el borde suavizado se funde con la caja de texto.

Formato FNT1 (little-endian):
  "FNT1", u8 alto de linea, u8 ascenso, u16 cantidad de glifos
  glifos ordenados por clave (cp*2+estilo): u16 cp, u8 estilo, u8 u, u8 v, u8 ancho, u8 alto, s8 xoff, s8 yoff, u8 avance (10 bytes)
  relleno a multiplo de 4
  atlas 256x256 de 4 bits, 2 pixeles por byte (el izquierdo en el nibble bajo)
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.simulator.vnb import TextTable  # noqa: E402

GAME = ROOT / "original" / "game"
DATA = ROOT / "build" / "data"
FONT_PATH = GAME / "gui" / "fonts" / "NotoSansJP-Regular.ttf"
SIZE = 13
ATLAS = 256
LINE_HEIGHT = 14
EXTRA_TEXT = "Comenzar Continuar Galería Opciones Guardar Cargar Volumen Música Efectos Seguir ▼▶◀↑↓ 0123456789 ñÑáéíóúÁÉÍÓÚ¿¡"
SHEAR = 0.22


def codepoints():
    text = TextTable((DATA / "TEXT_ES.BIN").read_bytes())
    chars = set(chr(c) for c in range(32, 127)) | set(EXTRA_TEXT)
    for block in text.blocks:
        for s in block:
            chars.update(c for c in s if ord(c) >= 32)
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    for sp in meta["speakers"]:
        chars.update(sp["name"])
    return sorted(chars)


def render_glyph(font, ch, italic):
    """Devuelve (mapa de 4 bits, ancho, alto, xoff, yoff, avance) con el origen en la linea base."""
    advance = font.getlength(ch)
    box = font.getbbox(ch, anchor="ls")
    if box[2] <= box[0] or box[3] <= box[1]:
        return None, 0, 0, 0, 0, max(1, round(advance))
    w, h = box[2] - box[0] + 3, box[3] - box[1] + 2
    img = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(img).text((-(box[0]) + 1, -(box[1]) + 1), ch, font=font, fill=255, anchor="ls") if False else None
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((1 - box[0], 1 - box[1]), ch, font=font, fill=255, anchor="ls")
    if italic:
        img = img.transform((w + 3, h), Image.AFFINE, (1, SHEAR, -SHEAR * h, 0, 1, 0), resample=Image.BICUBIC)
        w += 3
    arr = np.asarray(img, dtype=np.float32) / 255.0
    levels = np.clip(np.round(arr ** 0.8 * 15), 0, 15).astype(np.uint8)
    return levels, w, h, box[0] - 1, box[1] - 1, max(1, round(advance))


def build():
    font = ImageFont.truetype(str(FONT_PATH), SIZE)
    atlas = np.zeros((ATLAS, ATLAS), np.uint8)
    glyphs = []
    x = y = row_h = 0
    for italic in (0, 1):
        for ch in codepoints():
            levels, w, h, xoff, yoff, adv = render_glyph(font, ch, bool(italic))
            if levels is None:
                glyphs.append((ord(ch), italic, 0, 0, 0, 0, 0, 0, adv))
                continue
            if x + w + 1 > ATLAS:
                x, y, row_h = 0, y + row_h + 1, 0
            if y + h > ATLAS:
                raise RuntimeError("el atlas de la fuente no alcanza")
            atlas[y:y + h, x:x + w] = levels
            glyphs.append((ord(ch), italic, x, y, w, h, xoff, yoff, adv))
            x += w + 1
            row_h = max(row_h, h)
    glyphs.sort(key=lambda g: g[0] * 2 + g[1])
    ascent = -font.getbbox("Ág", anchor="ls")[1]
    blob = b"FNT1" + struct.pack("<BBH", LINE_HEIGHT, ascent, len(glyphs))
    for cp, st, u, v, w, h, xo, yo, adv in glyphs:
        blob += struct.pack("<HBBBBBbbB", cp, st, u, v, w, h, xo, yo, adv)
    blob += b"\x00" * (-len(blob) % 4)
    flat = atlas.reshape(-1)
    packed = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8)
    blob += packed.tobytes()
    (DATA / "FONT.BIN").write_bytes(blob)
    preview = Image.fromarray((atlas * 17).astype(np.uint8), "L")
    preview.save(ROOT / "build" / "reports" / "fuente_atlas.png")
    return len(glyphs), y + row_h


def main():
    (ROOT / "build" / "reports").mkdir(parents=True, exist_ok=True)
    count, used = build()
    print(f"FONT.BIN: {count} glifos, atlas usado hasta la fila {used} de {ATLAS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
