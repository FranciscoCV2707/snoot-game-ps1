"""Pipeline de imagenes (Fase 4): recetas de build/data/meta.json -> build/data/IMG/*.IMG, indice y hoja de contacto.

Pasos: renderizar a la resolucion original, reducir a 1/6 (1920x1080 -> 320x180) sin halos, recortar bordes
transparentes de los sprites, cuantizar a 8 bits (fondos con paleta propia; sprites con paleta compartida por carpeta)
con dither ordenado de la PS1, y comprimir con LZ4. Formato IMG1 descrito en docs/formato-img.md.

Uso: python -m tools.images.convert [--only ID,ID] [--workers N]
"""
import argparse
import html
import json
import os
import struct
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import lz4.block
import numpy as np
from PIL import Image

from tools.images import render
from tools.images.proto_compare import PSX_DITHER, crt_preview, dither_offsets

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "build" / "data"
OUT = DATA / "IMG"
TMP = ROOT / "build" / "tmp" / "img"
REPORT_DIR = ROOT / "build" / "reports" / "arte"
SCALE = 6                    # 1920 / 320
TEXT_IMAGES = {f"text{i}" for i in range(1, 10)}                 # textos de insultos (capitulo 1): legibles al doble de tamano
NO_DITHER = TEXT_IMAGES | {"vvurm_drama_poster", "jewlcase", "fastforward"}   # imagenes con texto: sin tramado
SCALE_OVERRIDE = {"ui logo": 3, **{name: 3 for name in TEXT_IMAGES}}   # el logo del titulo se dibuja mas grande (pantalla completa de 320x240)
HALF_AREA = 90000            # sprites de mas de ~90000 pixeles se guardan a media resolucion
MAX_SPRITE_ROWS = 256       # una imagen no puede cruzar la fila 256 de VRAM: los mas altos van a media resolucion
DITHER_STRENGTH = 2
KIND_BG, KIND_SPRITE, KIND_SOLID, KIND_EMPTY = 0, 1, 2, 3
KIND_NAMES = {0: "fondo", 1: "sprite", 2: "color", 3: "vacio"}
FMT_VERSION = 1
HEADER = "<4sBBHHHHHH4BH"
FLAG_TRANSLUCENT = 4         # bit2 de flags: se dibuja con la mezcla al 50% de la GPU (CLUT con bit STP)


def uniform_translucent(alpha):
    """Alfa parejo y a medias en todo lo visible (como el grano de pelicula): se ve mejor mezclado que tramado."""
    body = alpha[alpha > 24].astype(np.float32)
    return body.size > 0 and 64 <= float(body.mean()) <= 210 and float(body.std()) < 25


def to555(rgb):
    r, g, b = (int(c) >> 3 for c in rgb)
    value = r | (g << 5) | (b << 10)
    return value or 0x0421       # 0x0000 es transparente en la PS1


def dither_field(shape, origin=(0, 0)):
    """Matriz de dither de la PS1 alineada a coordenadas absolutas de pantalla (los parches de video encajan con la base)."""
    h, w = shape[:2]
    ys = (np.arange(h) + origin[1]) % 4
    xs = (np.arange(w) + origin[0]) % 4
    return PSX_DITHER[np.ix_(ys, xs)][:, :, None]


def noisy(arr, origin=(0, 0)):
    return np.clip(arr.astype(np.int16) + dither_field(arr.shape, origin) * DITHER_STRENGTH, 0, 255).astype(np.uint8)


def has_videoframe(recipe):
    if recipe.get("op") == "videoframe":
        return True
    children = [recipe.get(k) for k in ("src", "content", "mask")] + [l["src"] for l in recipe.get("layers", [])]
    return any(has_videoframe(c) for c in children if c)


def quantize_with(rgb_arr, palette_img, dither=True, origin=(0, 0)):
    source = noisy(rgb_arr, origin) if dither else rgb_arr
    return np.asarray(Image.fromarray(source, "RGB").quantize(palette=palette_img, dither=Image.Dither.NONE))


# ------------------------------------------------------------------ fase 1: renderizar y reducir
def phase1(task):
    try:
        return phase1_run(task)
    except Exception as exc:     # se reporta y se sigue con las demas imagenes
        return {"id": task[0], "kind": KIND_EMPTY, "full_w": 1, "full_h": 1, "error": f"{type(exc).__name__}: {exc}"}


def phase1_run(task):
    iid, recipe, visible, name = task
    scale = SCALE_OVERRIDE.get(name, SCALE)
    meta = {"id": iid}
    half = False
    if recipe["op"] == "solid":
        meta.update(kind=KIND_SOLID, color=render.parse_color(recipe["color"]), full_w=320, full_h=180)
        return meta
    img = render.render(recipe)
    ow, oh = img.size
    alpha = np.asarray(img.split()[3])
    opaque = float((alpha >= 250).mean()) >= 0.97    # fondos con algun pixel semitransparente se aplanan sobre negro
    w, h = max(1, round(ow / scale)), max(1, round(oh / scale))
    kind = KIND_BG if (opaque and ow >= 1000 and not has_videoframe(recipe)) else KIND_SPRITE
    if kind == KIND_BG:
        flat = Image.new("RGBA", img.size, (0, 0, 0, 255))
        flat.alpha_composite(img)
        img = flat
    small = img.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
    ox = oy = 0
    if kind == KIND_SPRITE and visible:
        # solo se conserva la zona que llega a verse en pantalla segun el compilador
        box = (max(0, int(visible[0] // SCALE)), max(0, int(visible[1] // SCALE)),
               min(w, int(-(-visible[2] // SCALE))), min(h, int(-(-visible[3] // SCALE))))
        if box[2] > box[0] and box[3] > box[1]:
            small = small.crop(box)
            ox, oy = box[0], box[1]
    sa = np.asarray(small.split()[3])
    if kind == KIND_SPRITE:
        ys, xs = np.where(sa > 8)
        if len(xs) == 0:
            meta.update(kind=KIND_EMPTY, full_w=w, full_h=h)
            return meta
        x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        crop = small.crop((x0, y0, x1, y1))
        body = sa[y0:y1, x0:x1]
        semi = float(((body > 24) & (body < 231)).sum()) / max(1, int((body > 24).sum()))
        if crop.width * crop.height > HALF_AREA or crop.height > MAX_SPRITE_ROWS:
            half = True
            x0, y0 = (x0 + ox) // 2, (y0 + oy) // 2
            ox = oy = 0
            crop = crop.convert("RGBa").resize((max(1, crop.width // 2), max(1, crop.height // 2)), Image.LANCZOS).convert("RGBA")
    else:
        x0 = y0 = 0
        crop, semi = small, 0.0
    path = TMP / f"{iid:04d}.png"
    crop.save(path)
    meta.update(name=name, kind=kind, ow=ow, oh=oh, full_w=w, full_h=h, x=x0 + ox, y=y0 + oy, w=crop.width, h=crop.height, semi=semi, half=half,
                tmp=str(path), group=render.first_file(recipe))
    return meta


# ------------------------------------------------------------------ paletas compartidas por carpeta
def group_palettes(metas, only=None):
    groups = defaultdict(list)
    for m in metas:
        if m["kind"] == KIND_SPRITE:
            key = str(Path(m["group"]).parent) if m.get("group") else "misc"
            m["palette_group"] = key
            groups[key].append(m)
    rng = np.random.default_rng(1)
    palettes = {}
    for key, members in groups.items():
        samples = []
        for m in members:
            arr = np.asarray(Image.open(m["tmp"]))
            px = arr[arr[..., 3] >= 128][:, :3]
            if len(px):
                samples.append(px[rng.choice(len(px), min(len(px), 20000), replace=False)])
        if not samples:
            continue
        stack = np.concatenate(samples)[:400000]
        mosaic = Image.fromarray(stack.reshape(1, -1, 3), "RGB")
        pal = mosaic.quantize(255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        flat = pal.getpalette()[:255 * 3]
        flat += [0] * (255 * 3 - len(flat))
        palettes[key] = flat
    return palettes


# ------------------------------------------------------------------ fase 3: cuantizar y escribir
def palette_image(flat):
    img = Image.new("P", (1, 1))
    img.putpalette(flat + [0] * (768 - len(flat)))
    return img


def phase3(task):
    meta, flat = task
    iid, kind = meta["id"], meta["kind"]
    out = OUT / f"I{iid:04d}.IMG"
    header = dict(kind=kind, flags=0, full_w=meta["full_w"], full_h=meta["full_h"], x=0, y=0, w=0, h=0,
                  solid=(0, 0, 0, 0), ncolors=0)
    if kind == KIND_SOLID:
        header["solid"] = tuple(meta["color"])
        blob = struct.pack(HEADER, b"IMG1", kind, 0, header["full_w"], header["full_h"], 0, 0, 0, 0, *header["solid"], 0)
        blob += b"\x00" * 512 + struct.pack("<II", 0, 0)
        out.write_bytes(blob)
        return {"id": iid, "raw": 0, "comp": 0, "bytes": len(blob)}
    if kind == KIND_EMPTY:
        blob = struct.pack(HEADER, b"IMG1", kind, 0, header["full_w"], header["full_h"], 0, 0, 0, 0, 0, 0, 0, 0, 0)
        blob += b"\x00" * 512 + struct.pack("<II", 0, 0)
        out.write_bytes(blob)
        return {"id": iid, "raw": 0, "comp": 0, "bytes": len(blob)}
    arr = np.asarray(Image.open(meta["tmp"]))
    rgb, alpha = arr[..., :3], arr[..., 3]
    if kind == KIND_BG:
        base = Image.fromarray(rgb, "RGB")
        pal = base.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        idx = quantize_with(rgb, pal, meta.get("name") not in NO_DITHER)
        colors = pal.getpalette()[:768]
        flags = 0
    else:
        pal = palette_image(flat)
        idx = quantize_with(rgb, pal, meta.get("name") not in NO_DITHER, (meta.get("x", 0), meta.get("y", 0))).astype(np.int16) + 1
        translucent = meta.get("semi", 0) > 0.30 and uniform_translucent(alpha)
        if translucent:                   # velo de alfa parejo (grano de pelicula): mezcla al 50% de la GPU
            idx[alpha <= 24] = 0
        elif meta.get("semi", 0) > 0.30:  # efectos translucidos (vineta, brillos): el alfa se convierte en tramado
            tile = np.tile((PSX_DITHER + 4.5) / 8.0, (alpha.shape[0] // 4 + 1, alpha.shape[1] // 4 + 1))[:alpha.shape[0], :alpha.shape[1]]
            idx[(alpha / 255.0) <= tile] = 0
        else:
            idx[alpha < 128] = 0
        idx = idx.astype(np.uint8)
        colors = [0, 0, 0] + list(flat)
        flags = 1 | (2 if meta.get("half") else 0) | (FLAG_TRANSLUCENT if translucent else 0)
    h, w = idx.shape
    if w % 2:
        idx = np.pad(idx, ((0, 0), (0, 1)))
        w += 1
    entries = [colors[i:i + 3] for i in range(0, len(colors), 3)]
    words = [to555(c) for c in entries] + [0] * (256 - len(entries))
    if flags & FLAG_TRANSLUCENT:
        words = [w_ | 0x8000 for w_ in words]    # bit STP: la GPU solo mezcla los texeles que lo tienen
    if flags & 1:
        words[0] = 0
    raw = idx.tobytes()
    comp = lz4.block.compress(raw, mode="high_compression", compression=12, store_size=False)
    blob = struct.pack(HEADER, b"IMG1", kind, flags, meta["full_w"], meta["full_h"], meta.get("x", 0), meta.get("y", 0),
                       w, h, 0, 0, 0, 0, len(entries))
    blob += struct.pack("<256H", *words) + struct.pack("<II", len(raw), len(comp)) + comp
    out.write_bytes(blob)
    preview(meta, idx, words, flags)
    return {"id": iid, "raw": len(raw), "comp": len(comp), "bytes": len(blob), "w": w, "h": h, "colors": len(entries)}


def decode(idx, words, flags):
    pal = np.array([[(w & 31) << 3 | (w & 31) >> 2, ((w >> 5) & 31) << 3 | ((w >> 5) & 31) >> 2,
                     ((w >> 10) & 31) << 3 | ((w >> 10) & 31) >> 2] for w in words], dtype=np.uint8)
    rgb = pal[idx]
    mask = (idx != 0) if flags & 1 else np.ones(idx.shape, bool)
    return rgb, mask


def checker(w, h, cell=8):
    yy, xx = np.indices((h, w))
    base = np.where(((xx // cell + yy // cell) % 2)[..., None] == 0, 70, 95).astype(np.uint8)
    return np.repeat(base, 3, axis=2)


def preview(meta, idx, words, flags):
    """Vista previa: la original reducida (antes de cuantizar) y la convertida (con CRT para los fondos)."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    iid = meta["id"]
    rgb, mask = decode(idx, words, flags)
    orig = np.asarray(Image.open(meta["tmp"]))
    h, w = idx.shape
    if orig.shape[1] < w:
        orig = np.pad(orig, ((0, 0), (0, w - orig.shape[1]), (0, 0)))
    if meta["kind"] == KIND_BG and h != 180:
        # CG alto (se desplaza en el juego): se muestra con su proporcion real, sin pantalla ni letterbox
        for tag, source in (("o", orig[..., :3]), ("c", rgb)):
            shown = Image.fromarray(source[:, :meta["w"]], "RGB")
            shown.resize((int(shown.width * 1.5), int(shown.height * 1.5)), Image.LANCZOS if tag == "o" else Image.NEAREST).save(
                REPORT_DIR / f"{iid:04d}_{tag}.jpg", quality=85)
    elif meta["kind"] == KIND_BG:
        for tag, source in (("o", orig[..., :3]), ("c", rgb)):
            shown = Image.fromarray(source[:, :meta["w"]], "RGB")
            if tag == "c":
                canvas = Image.new("RGB", (320, 240))
                canvas.paste(shown, (0, 30) if shown.height == 180 else (0, 0))
                shown = crt_preview(canvas, 320, 240) if shown.height == 180 else shown.resize((640, 360))
                shown = shown.resize((480, 360)) if shown.height == 720 else shown
            else:
                shown = shown.resize((480, round(480 * shown.height / shown.width)), Image.LANCZOS)
            shown.save(REPORT_DIR / f"{iid:04d}_{tag}.jpg", quality=80)
    else:
        scale = 2 if w <= 160 and h <= 160 else 1
        bgc = checker(w, h)
        a = orig[..., 3:4] / 255.0
        o = (orig[..., :3] * a + bgc * (1 - a)).astype(np.uint8)
        c = np.where(mask[..., None], rgb, bgc).astype(np.uint8)
        for tag, arr in (("o", o), ("c", c)):
            Image.fromarray(arr, "RGB").resize((w * scale, h * scale), Image.NEAREST).save(REPORT_DIR / f"{iid:04d}_{tag}.png")


# ------------------------------------------------------------------ orquestacion
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="ids separados por coma")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()

    from tools.script_compiler.images import ImageTable
    meta_json = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    table = ImageTable()
    # las recetas de layeredimage generadas por el compilador se vuelven a registrar para poder expandirlas
    for im in meta_json["images"]:
        if im and im["recipe"]["op"] == "layered":
            for layer in im["recipe"]["layers"]:
                assert tuple(layer["name"]) in table.recipes, layer["name"]
    only = {int(v) for v in args.only.split(",")} if args.only else None
    tasks = []
    for iid, im in enumerate(meta_json["images"]):
        if im is None or (only and iid not in only):
            continue
        recipe = im["recipe"]
        if recipe["op"] in ("movie", "atl"):
            continue
        tasks.append((iid, render.expand(table, recipe), im.get("visible"), im["names"][0]))
    for d in (OUT, TMP, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print(f"{len(tasks)} imagenes, {args.workers} procesos")
    with ProcessPoolExecutor(args.workers) as pool:
        metas = list(pool.map(phase1, tasks, chunksize=4))
        errors = [(m["id"], m["error"]) for m in metas if m.get("error")]
        for iid, err in errors:
            print("ERROR imagen", iid, meta_json["images"][iid]["names"][:1], err)
        print("fase 1 lista")
        palettes = group_palettes(metas)
        jobs = [(m, palettes.get(m.get("palette_group"), [])) for m in metas]
        results = list(pool.map(phase3, jobs, chunksize=4))
    by_id = {m["id"]: m for m in metas}
    summary = {}
    for r in results:
        m = by_id[r["id"]]
        summary[r["id"]] = {**r, "kind": m["kind"], "full_w": m["full_w"], "full_h": m["full_h"],
                            "group": m.get("palette_group"), "semi": round(m.get("semi", 0), 3),
                            "x": m.get("x", 0), "y": m.get("y", 0), "names": meta_json["images"][r["id"]]["names"][:2]}
    (DATA / "images_out.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    write_index(meta_json, summary)
    make_memcard_icon(meta_json, summary)
    write_video_preview(meta_json, table)
    write_report(meta_json, summary, palettes)
    return 0


def make_memcard_icon(meta_json, summary):
    """Icono de 16x16 con 16 colores para la memory card (cabecera de archivo de la BIOS): MCICON.BIN."""
    logo_id = next(i for i, im in enumerate(meta_json["images"]) if im and im["names"][0] == "ui logo")
    img = Image.open(TMP / f"{logo_id:04d}.png").convert("RGBA")
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (20, 20, 40, 255))
    square.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
    small = square.convert("RGB").resize((16, 16), Image.LANCZOS)
    pal = small.quantize(15, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colors = pal.getpalette()[:45]
    words = [0] + [to555(colors[i:i + 3]) for i in range(0, len(colors), 3)]
    words += [0] * (16 - len(words))
    idx = np.asarray(pal).astype(np.int16) + 1
    packed = bytearray()
    flat = idx.flatten()
    for i in range(0, 256, 2):
        packed.append((int(flat[i]) & 15) | ((int(flat[i + 1]) & 15) << 4))
    (DATA / "MCICON.BIN").write_bytes(struct.pack("<16H", *words) + bytes(packed))


def load_img(path):
    """Lee un archivo IMG1: devuelve (rgb, mascara, x, y) del bitmap, o None si esta vacio."""
    data = Path(path).read_bytes()
    size = struct.calcsize(HEADER)
    header = struct.unpack_from(HEADER, data, 0)
    kind, flags, x, y, w, h = header[1], header[2], header[5], header[6], header[7], header[8]
    if kind not in (KIND_BG, KIND_SPRITE) or not w:
        return None
    words = struct.unpack_from("<256H", data, size)
    raw_size = struct.unpack_from("<II", data, size + 512)[0]
    idx = np.frombuffer(lz4.block.decompress(data[size + 520:], uncompressed_size=raw_size), np.uint8).reshape(h, w)
    rgb, mask = decode(idx, words, flags)
    return rgb, mask, x, y


def write_video_preview(meta_json, table):
    """GIF de la animacion del video `fang tail`: base + parche de cada cuadro, con sus tiempos reales."""
    base = patches = None
    for iid, im in enumerate(meta_json["images"]):
        for g in meta_json["gallery"]:
            if g.get("movie") and g["id"] == iid:
                base, patches = iid, g["movie"]
    if base is None:
        return
    base_img = load_img(OUT / f"I{base:04d}.IMG")
    frames = []
    for pid in patches["patches"]:
        canvas = np.zeros((180, 320, 3), np.uint8)
        rgb, mask, x, y = base_img
        canvas[y:y + rgb.shape[0], x:x + rgb.shape[1]] = rgb
        patch = load_img(OUT / f"I{pid:04d}.IMG")
        if patch:
            prgb, pmask, px, py = patch
            region = canvas[py:py + prgb.shape[0], px:px + prgb.shape[1]]
            region[pmask] = prgb[pmask]
        frame = Image.new("RGB", (320, 240))
        frame.paste(Image.fromarray(canvas), (0, 30))
        frames.append(crt_preview(frame, 320, 240).resize((640, 480)).convert("P", palette=Image.ADAPTIVE))
    durations = [max(20, int(t * 1000)) for t in patches["times"]]
    frames[0].save(REPORT_DIR / "fang_tail.gif", save_all=True, append_images=frames[1:], duration=durations, loop=0)


def write_index(meta_json, summary):
    entries = bytearray(b"IDX1" + struct.pack("<H", len(meta_json["images"])))
    for iid, im in enumerate(meta_json["images"]):
        s = summary.get(iid)
        if im is None or s is None:
            entries += struct.pack("<BBHHHBII", KIND_EMPTY, 0, 0, 0, 0xFFFF, 0, 0, 0)
            continue
        gallery = im.get("gallery")
        entries += struct.pack("<BBHHHBII", s["kind"], 1 if s["kind"] == KIND_SPRITE else 0, s["full_w"], s["full_h"],
                               0xFFFF if gallery is None else gallery, im.get("ending") or 0, s["comp"], s["raw"])
    (OUT / "index.bin").write_bytes(bytes(entries))


def write_report(meta_json, summary, palettes):
    kinds = defaultdict(list)
    for iid, s in summary.items():
        kinds[s["kind"]].append(s)
    sprites = kinds[KIND_SPRITE]
    sizes = sorted((s["w"] * s["h"] for s in sprites), reverse=True)
    raw_total = sum(s["raw"] for s in summary.values())
    comp_total = sum(s["bytes"] for s in summary.values())
    lines = ["# Reporte del pipeline de imagenes", "", "Generado por `python -m tools.images.convert`.", "",
             "| Dato | Valor |", "|---|---|",
             f"| Imagenes convertidas | {len(summary)} |",
             f"| Fondos / CG (8 bits, paleta propia) | {len(kinds[KIND_BG])} |",
             f"| Sprites (8 bits, paleta por carpeta) | {len(sprites)} ({len(palettes)} paletas) |",
             f"| Colores solidos | {len(kinds[KIND_SOLID])} |",
             f"| Tamano sin comprimir | {raw_total / 1048576:.1f} MB |",
             f"| Tamano en disco (LZ4) | {comp_total / 1048576:.1f} MB ({comp_total / 2048:.0f} sectores) |"]
    if sprites:
        lines += [f"| Sprite mas grande | {sizes[0] / 1024:.0f} KB |", f"| Sprite medio | {sum(sizes) / len(sizes) / 1024:.0f} KB |",
                  f"| Sprites de mas de 40 KB | {sum(1 for v in sizes if v > 40960)} |"]
    big = sorted(sprites, key=lambda s: s["w"] * s["h"], reverse=True)[:10]
    lines += ["", "## Sprites mas grandes", "", "| Imagen | Tamano | KB |", "|---|---|---|"]
    lines += [f"| {s['names'][0]} | {s['w']}x{s['h']} | {s['w'] * s['h'] // 1024} |" for s in big]
    semi = [s for s in sprites if s["semi"] > 0.30]
    lines += ["", f"## Sprites con semitransparencia importante ({len(semi)})", ""]
    lines += [f"- {s['names'][0]} ({s['semi']:.0%})" for s in semi[:30]]
    (ROOT / "build" / "reports" / "imagenes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_contact_sheets(meta_json, summary)


def write_contact_sheets(meta_json, summary):
    pages = {"fondos": [], "sprites": [], "otros": []}
    for iid, s in sorted(summary.items()):
        pages["fondos" if s["kind"] == KIND_BG else "sprites" if s["kind"] == KIND_SPRITE else "otros"].append((iid, s))
    css = ("<style>body{background:#161616;color:#ddd;font:13px sans-serif;margin:12px}.g{display:grid;"
           "grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:10px}.c{background:#222;padding:6px}"
           "img{max-width:100%;display:block;margin-bottom:4px}</style>")
    for name, items in pages.items():
        for part, start in enumerate(range(0, max(1, len(items)), 60), 1):
            chunk = items[start:start + 60]
            body = [f"<!doctype html><meta charset='utf-8'><title>{name} {part}</title>{css}<h1>{name} (pagina {part})</h1><div class='g'>"]
            for iid, s in chunk:
                ext = "jpg" if s["kind"] == KIND_BG else "png"
                label = html.escape(" / ".join(s["names"]))
                body.append(f"<div class='c'><b>#{iid}</b> {label}<br>{s['full_w']}x{s['full_h']}, {s['bytes'] // 1024} KB")
                if s["kind"] in (KIND_BG, KIND_SPRITE):
                    body.append(f"<img src='{iid:04d}_o.{ext}' title='original reducida'><img src='{iid:04d}_c.{ext}' title='convertida'>")
                body.append("</div>")
            body.append("</div>")
            (REPORT_DIR / f"{name}_{part}.html").write_text("\n".join(body), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
