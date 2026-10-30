"""Genera build/data/FONT.BIN: atlas de fuente de 4 bits (16 niveles de gris) para el motor.

Los glifos salen de las cadenas de TEXT_ES.BIN (todo lo que el juego puede mostrar) mas el ASCII imprimible y los
nombres de hablantes. Cada glifo existe en estilo normal y cursiva (inclinada). El motor suma el color al fondo con
mezcla aditiva, asi el borde suavizado se funde con la caja de texto.

El cuerpo y la altura de linea los decide el PERFIL de la consola (VN_PROFILE), igual que hace el compilador de
guiones con su caja de texto: medir con un cuerpo y dibujar con otro parte las lineas donde no toca.

Formato FNT1 (little-endian) - el de PS1, que no cambia:
  "FNT1", u8 alto de linea, u8 ascenso, u16 cantidad de glifos
  glifos ordenados por clave (cp*2+estilo): u16 cp, u8 estilo, u8 u, u8 v, u8 ancho, u8 alto, s8 xoff, s8 yoff, u8 avance (10 bytes)
  relleno a multiplo de 4
  atlas 256x256 de 4 bits, 2 pixeles por byte (el izquierdo en el nibble bajo)

Formato FNT2 - para los perfiles cuyo cuerpo necesita una hoja mas grande de lo que FNT1 puede expresar (u y v son
de 8 bits, o sea como maximo 255):
  "FNT2", u8 alto de linea, u8 ascenso, u16 cantidad, u16 atlas_ancho, u16 atlas_alto
  glifos: u16 cp, u8 estilo, u16 u, u16 v, u8 ancho, u8 alto, s8 xoff, s8 yoff, u8 avance (12 bytes)
  relleno a multiplo de 4, atlas del tamano declarado
Lo lee engine/core/text.c (font_load).
"""
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.images import profile as profile_mod  # noqa: E402
from tools.simulator.vnb import TextTable  # noqa: E402

GAME = ROOT / "original" / "game"
DATA = ROOT / "build" / "data"
FONT_PATH = GAME / "gui" / "fonts" / "NotoSansJP-Regular.ttf"
PROFILE = profile_mod.get(os.environ.get("VN_PROFILE"))
SIZE = PROFILE.text_size                    # 13 en PS1, 20 en PSP, 39 en Vita
LINE_HEIGHT = round(SIZE * 14 / 13)         # conserva el ritmo de PS1 (cuerpo 13 con linea 14)
ATLAS = 256                                 # FNT1: la hoja cuadrada de siempre
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


def glyph_box(font, ch, italic):
    """(ancho, alto) del recorte que habria que guardar, sin renderizarlo: es la cuenta que usa el empaquetado."""
    box = font.getbbox(ch, anchor="ls")
    w, h = box[2] - box[0] + 3, box[3] - box[1] + 2
    if w <= 3 or h <= 2:
        return 0, 0
    return (w + 3, h) if italic else (w, h)


def sheet_needed(cps, font, width):
    """Alto que ocupan los dos estilos empaquetados en una hoja de `width` pixeles."""
    x = y = row_h = 0
    for italic in (0, 1):
        for ch in cps:
            w, h = glyph_box(font, ch, bool(italic))
            if not w:
                continue
            if x + w + 1 > width:
                x, y, row_h = 0, y + row_h + 1, 0
            x += w + 1
            row_h = max(row_h, h)
    return y + row_h


def choose_sheet(cps, font):
    """Ancho, alto y si hace falta FNT2. PS1 cae en 256x256/FNT1, o sea el FONT.BIN de v1.0 tal cual."""
    width = 256
    needed = sheet_needed(cps, font, width)
    if needed > 256:                      # FNT1 no puede pasar de la fila 255 (v es u8): hoja mas ancha
        width = 512
        needed = sheet_needed(cps, font, width)
    height = 256 if needed <= 256 else ((needed + 63) // 64) * 64
    return width, height, not (width == 256 and height == 256)


def build():
    font = ImageFont.truetype(str(FONT_PATH), SIZE)
    aw, ah, fnt2 = choose_sheet(codepoints(), font)
    atlas = np.zeros((ah, aw), np.uint8)
    glyphs = []
    x = y = row_h = 0
    for italic in (0, 1):
        for ch in codepoints():
            levels, w, h, xoff, yoff, adv = render_glyph(font, ch, bool(italic))
            if levels is None:
                glyphs.append((ord(ch), italic, 0, 0, 0, 0, 0, 0, adv))
                continue
            if x + w + 1 > aw:
                x, y, row_h = 0, y + row_h + 1, 0
            if y + h > ah:
                raise RuntimeError(f"el atlas de {aw}x{ah} no alcanza con el cuerpo {SIZE}")
            atlas[y:y + h, x:x + w] = levels
            glyphs.append((ord(ch), italic, x, y, w, h, xoff, yoff, adv))
            x += w + 1
            row_h = max(row_h, h)
    glyphs.sort(key=lambda g: g[0] * 2 + g[1])
    ascent = -font.getbbox("Ág", anchor="ls")[1]
    if fnt2:
        blob = b"FNT2" + struct.pack("<BBHHH", LINE_HEIGHT, ascent, len(glyphs), aw, ah)
    else:
        blob = b"FNT1" + struct.pack("<BBH", LINE_HEIGHT, ascent, len(glyphs))
    for cp, st, u, v, w, h, xo, yo, adv in glyphs:
        blob += (struct.pack("<HBHHBBbbB", cp, st, u, v, w, h, xo, yo, adv) if fnt2 else
                 struct.pack("<HBBBBBbbB", cp, st, u, v, w, h, xo, yo, adv))
    blob += b"\x00" * (-len(blob) % 4)
    flat = atlas.reshape(-1)
    packed = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8)
    blob += packed.tobytes()
    (DATA / "FONT.BIN").write_bytes(blob)
    preview = Image.fromarray((atlas * 17).astype(np.uint8), "L")
    preview.save(ROOT / "build" / "reports" / "fuente_atlas.png")
    return len(glyphs), y + row_h, aw, ah, fnt2


def main():
    (ROOT / "build" / "reports").mkdir(parents=True, exist_ok=True)
    count, used, aw, ah, fnt2 = build()
    print(f"FONT.BIN[{PROFILE.name}]: {count} glifos, cuerpo {SIZE}, linea {LINE_HEIGHT}, "
          f"atlas {aw}x{ah} ({'FNT2' if fnt2 else 'FNT1'}), usado hasta la fila {used}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
