"""Prototipo de la Fase 2: compara resoluciones y formatos de fondo para PS1.

Genera build/reports/proto/index.html con cada escena en varias resoluciones y
formatos, vistas como se verian en una TV CRT (solo para comparar, no va al juego).

Pantalla 4:3 con imagen 16:9 en letterbox: la imagen ocupa 3/4 de la altura
(180 de 240 lineas, o 360 de 480).
"""
import html
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "original" / "game"
OUT = ROOT / "build" / "reports" / "proto"
FONT_PATH = GAME / "gui" / "fonts" / "NotoSansJP-Regular.ttf"
SAMPLE_TEXT = "El sentimiento de culpa sigue pesando sobre mí, pero he encontrado la manera de sobrellevarlo."
SPEAKER = "Anon"

# (nombre, ancho, altura total de pantalla)
MODES = [("320x240", 320, 240), ("512x240", 512, 240), ("640x480i", 640, 480)]
FORMATS = ["15 bits + dither PS1", "8 bits Floyd-Steinberg", "8 bits dither ordenado"]

SCENES = [
    ("outside school fog base", [("fang/basic set/fang neutral", 0.72)]),
    ("roof night", [("anon/base set/anon neutral", 0.3), ("fang/basic set/fang considering", 0.7)]),
    ("classroom", []),
    ("aquarium", []),
    ("room anon dark", [("anon/base set/anon neutral", 0.5)]),
]

PSX_DITHER = np.array([[-4, 0, -3, 1], [2, -2, 3, -1], [-3, 1, -4, 0], [3, -1, 2, -2]], dtype=np.int16)


def load(rel):
    return Image.open(GAME / "images" / f"{rel}.webp").convert("RGBA")


def dither_offsets(shape):
    h, w = shape[:2]
    tile = np.tile(PSX_DITHER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    return tile[:, :, None]


def quant_15bit(img):
    rgb = np.asarray(img.convert("RGB"), dtype=np.int16)
    rgb = np.clip(rgb + dither_offsets(rgb.shape), 0, 255)
    rgb = (rgb >> 3) << 3
    rgb = rgb | (rgb >> 5)
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def quant_8bit(img, mode):
    base = img.convert("RGB")
    pal = base.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    if mode == "fs":
        return base.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")
    arr = np.asarray(base, dtype=np.int16)
    noisy = np.clip(arr + dither_offsets(arr.shape) * 3, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy, "RGB").quantize(palette=pal, dither=Image.Dither.NONE).convert("RGB")


def apply_format(img, fmt):
    if fmt == FORMATS[0]:
        return quant_15bit(img)
    return quant_8bit(img, "fs" if fmt == FORMATS[1] else "ordered")


def quant_sprite(sprite):
    """Personaje: 8 bits con paleta propia y transparencia por umbral."""
    alpha = np.asarray(sprite.split()[3]) > 128
    rgb = sprite.convert("RGB").quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")
    out = rgb.convert("RGBA")
    arr = np.asarray(out).copy()
    arr[~alpha, 3] = 0
    return Image.fromarray(arr, "RGBA")


def render_frame(bg_path, chars, width, total_h, fmt):
    pic_h = total_h * 3 // 4
    bg = Image.open(GAME / "images" / "backgrounds" / f"{bg_path}.webp").convert("RGB")
    bg = apply_format(bg.resize((width, pic_h), Image.LANCZOS), fmt)
    for rel, xpos in chars:
        sprite = load(rel)
        h = int(pic_h * 0.95)
        w = int(sprite.width * h / sprite.height)
        sprite = quant_sprite(sprite.resize((w, h), Image.LANCZOS))
        bg.paste(sprite, (int((width - w) * xpos), pic_h - h), sprite)
    frame = Image.new("RGB", (width, total_h), (0, 0, 0))
    frame.paste(bg, (0, (total_h - pic_h) // 2))
    return frame


def draw_textbox(frame, total_h):
    """Caja de texto a la altura de pantalla; el texto se dibuja a resolucion alta y se reduce."""
    scale = 4
    w, h = frame.size
    box_top = int(total_h * 0.76)
    big = Image.new("RGBA", (320 * scale, 240 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    draw.rectangle([0, int(240 * 0.76) * scale, 320 * scale, 240 * scale], fill=(0, 0, 0, 170))
    font = ImageFont.truetype(str(FONT_PATH), 13 * scale)
    small = ImageFont.truetype(str(FONT_PATH), 11 * scale)
    draw.text((8 * scale, (int(240 * 0.76) + 2) * scale), SPEAKER, font=small, fill=(54, 225, 45, 255))
    y = (int(240 * 0.76) + 15) * scale
    for line in wrap(SAMPLE_TEXT, font, 304 * scale):
        draw.text((8 * scale, y), line, font=font, fill=(255, 255, 255, 255))
        y += 15 * scale
    layer = big.resize((w, h), Image.BOX)
    out = frame.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def wrap(text, font, width):
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if font.getlength(trial) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def crt_preview(frame, width, total_h):
    """Vista aproximada de TV CRT: 4:3, lineas de escaneo y leve desenfoque horizontal."""
    disp_w, disp_h = 960, 720
    img = frame.resize((disp_w, disp_h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(radius=0.9))
    arr = np.asarray(img, dtype=np.float32)
    lines = total_h
    rows = np.arange(disp_h)
    phase = (rows * lines / disp_h) % 1.0
    mask = 0.72 + 0.28 * np.cos((phase - 0.5) * np.pi) ** 2
    arr *= mask[:, None, None]
    return Image.fromarray(np.clip(arr * 1.12, 0, 255).astype(np.uint8), "RGB")


def format_sizes(width, total_h, fmt):
    pic_h = total_h * 3 // 4
    pixels = width * pic_h
    data = pixels * 2 if fmt == FORMATS[0] else pixels + 512
    return data


def framebuffer_kb(width, total_h):
    rows = 240 if total_h == 480 else total_h
    return width * rows * 2 * 2 // 1024


def text_stats():
    """Cuantas lineas de caja hacen falta para el dialogo en espanol, segun el tamano de letra."""
    base = GAME / "tl" / "es" / "script"
    texts = []
    for path in sorted(base.glob("*.rpy")):
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            s = raw.strip()
            if s.startswith(('"', "A ", "F ")) or re.match(r'^[A-Za-z_]\w*\s+"', s):
                m = re.search(r'"((?:[^"\\]|\\.)*)"', s)
                if m and not s.startswith("#"):
                    t = re.sub(r"\{[^}]*\}|\[[^\]]*\]", "", m.group(1))
                    if len(t) > 1:
                        texts.append(t)
    result = {}
    for size in (9, 11, 13, 16):
        font = ImageFont.truetype(str(FONT_PATH), size * 4)
        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for t in texts:
            n = min(len(wrap(t, font, 304 * 4)), 4)
            counts[n] += 1
        total = len(texts)
        result[size] = {k: round(v * 100 / total, 1) for k, v in counts.items()}
    return len(texts), result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for bg, chars in SCENES:
        row = {"bg": bg, "cells": []}
        orig = Image.open(GAME / "images" / "backgrounds" / f"{bg}.webp").convert("RGB").resize((960, 540), Image.LANCZOS)
        ref = Image.new("RGB", (960, 720), (0, 0, 0))
        ref.paste(orig, (0, 90))
        ref.save(OUT / f"{bg}_original.jpg", quality=88)
        for mode_name, width, total_h in MODES:
            for fmt in FORMATS:
                frame = render_frame(bg, chars, width, total_h, fmt)
                frame = draw_textbox(frame, total_h)
                name = re.sub(r"[^a-z0-9]+", "_", f"{bg}_{mode_name}_{fmt}".lower()) + ".jpg"
                crt_preview(frame, width, total_h).save(OUT / name, quality=88)
                row["cells"].append((mode_name, fmt, name, format_sizes(width, total_h, fmt) // 1024))
        rows.append(row)
        print("listo:", bg)

    count, stats = text_stats()
    parts = ["<!doctype html><meta charset='utf-8'><title>Prototipo resolucion</title>",
             "<style>body{background:#111;color:#ddd;font:14px sans-serif;margin:16px}img{width:100%;max-width:480px;display:block}"
             ".g{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}table{border-collapse:collapse}"
             "td,th{border:1px solid #444;padding:4px 8px}</style>",
             "<h1>Comparacion de resolucion y formato (vista CRT aproximada)</h1>",
             "<h2>Memoria por modo</h2><table><tr><th>Modo</th><th>Framebuffers dobles (KB)</th>"
             "<th>Fondo 15 bits (KB)</th><th>Fondo 8 bits (KB)</th></tr>"]
    for mode_name, width, total_h in MODES:
        parts.append(f"<tr><td>{mode_name}</td><td>{framebuffer_kb(width, total_h)}</td>"
                     f"<td>{format_sizes(width, total_h, FORMATS[0]) // 1024}</td>"
                     f"<td>{format_sizes(width, total_h, FORMATS[1]) // 1024}</td></tr>")
    parts.append("</table><p>VRAM total: 1024 KB. 640x480 entrelazado se dibuja por campos de 640x240.</p>")
    parts.append(f"<h2>Lineas de caja necesarias ({count} lineas de dialogo en espanol, % por tamano de letra, ancho 304 de 320)</h2>"
                 "<table><tr><th>Letra (px sobre 240)</th><th>1 linea</th><th>2</th><th>3</th><th>4 o mas</th></tr>")
    for size, s in stats.items():
        parts.append(f"<tr><td>{size}</td><td>{s[1]}%</td><td>{s[2]}%</td><td>{s[3]}%</td><td>{s[4]}%</td></tr>")
    parts.append("</table>")
    for row in rows:
        parts.append(f"<h2>{html.escape(row['bg'])}</h2><div class='g'><div><b>Original</b><img src='{row['bg']}_original.jpg'></div>")
        for mode_name, fmt, name, kb in row["cells"]:
            parts.append(f"<div><b>{mode_name} - {fmt} ({kb} KB)</b><img src='{name}'></div>")
        parts.append("</div>")
    (OUT / "index.html").write_text("\n".join(parts), encoding="utf-8")
    print("Escrito:", OUT / "index.html")
    for size, s in stats.items():
        print(size, s)


if __name__ == "__main__":
    sys.exit(main())
