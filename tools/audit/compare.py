"""Auditoria visual: compara las capturas del juego original en Ren'Py con lo que dibujaria la PS1.

1. tools/audit/capture.py ejecuta tools/audit/zz_audit.rpy en una copia del juego y guarda log.jsonl y capturas.
2. Este script compila y ejecuta build/ps1_frames.exe (vm.c, res.c y scene.c del motor) con las mismas decisiones,
   empareja las lineas por texto, compone cada cuadro de PS1 con los IMG convertidos y mide la diferencia.

Uso: python -m tools.audit.compare <carpeta_de_captura> [<otra> ...] [--from chapter_N] [--top 60]
Salida por carpeta: report/ (hojas lado a lado ordenadas por diferencia), report.json y missing.json (imagenes que
Ren'Py muestra y la PS1 no).
"""
import argparse
import difflib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.images.convert import HEADER, load_img  # noqa: E402
from tools.simulator.vnb import Program  # noqa: E402

DATA = ROOT / "build" / "data"
HARNESS = ROOT / "build" / "ps1_frames.exe"
W, H = 320, 180
GCC_CANDIDATES = [Path(r"C:\msys64\ucrt64\bin\gcc.exe"), Path(r"C:\msys64\usr\bin\gcc.exe")]


def norm(text):
    text = re.sub(r"\{[^}]*\}", "", text)
    return re.sub(r"[^0-9a-zñáéíóúü]+", "", text.lower())


class Images:
    def __init__(self):
        self.cache = {}

    def get(self, iid):
        if iid not in self.cache:
            path = DATA / "IMG" / f"I{iid:04d}.IMG"
            raw = path.read_bytes()
            head = struct.unpack_from(HEADER, raw, 0)
            kind, full_w, full_h = head[1], head[3], head[4]
            solid = head[9:13]
            self.cache[iid] = (kind, full_w, full_h, solid, load_img(path), bool(head[2] & 4))
        return self.cache[iid]


def blend(sub, mode, color):
    """Mezcla de la GPU de PS1 (modo de scene.h): 0 opaco, 1 = 50%, 2 = suma, 3 = resta, 4 = suma de 1/4."""
    bg = sub.astype(np.int16)
    fg = np.array(color, np.int16)
    out = {0: bg * 0 + fg, 1: (bg + fg) // 2, 2: bg + fg, 3: bg - fg, 4: bg + fg // 4}[mode]
    sub[:] = np.clip(out, 0, 255).astype(np.uint8)


def compose(images, draws):
    """draws: [imagen, x, y, espejo, zoom, r, g, b] o [-1, modo, pasadas, r, g, b] (salida de ps1_frames)."""
    canvas = np.zeros((H, W, 3), np.uint8)
    for d in draws:
        if d[0] < 0:
            for _ in range(d[2]):
                blend(canvas, d[1], d[3:6])
            continue
        iid, x, y, flip = d[:4]
        zoom, tint = (d[4], tuple(d[5:8])) if len(d) > 4 else (64, (128, 128, 128))
        kind, full_w, full_h, solid, bitmap, translucent = images.get(iid)
        if kind == 2:
            canvas[:] = solid[:3]
            continue
        if bitmap is None:
            continue
        rgb, mask, bx, by = bitmap
        if flip:
            rgb, mask = rgb[:, ::-1], mask[:, ::-1]
            bx = full_w - bx - rgb.shape[1]
        if tint != (128, 128, 128):
            rgb = np.clip(rgb.astype(np.int32) * np.array(tint) // 128, 0, 255).astype(np.uint8)
        if zoom != 64:
            nw, nh = max(1, rgb.shape[1] * zoom // 64), max(1, rgb.shape[0] * zoom // 64)
            rgb = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.NEAREST))
            mask = np.asarray(Image.fromarray(mask).resize((nw, nh), Image.NEAREST))
            bx, by = bx * zoom // 64, by * zoom // 64
        x0, y0 = x + bx, y + by
        h, w = mask.shape
        sx0, sy0 = max(0, -x0), max(0, -y0)
        ex, ey = min(w, W - x0), min(h, H - y0)
        if ex <= sx0 or ey <= sy0:
            continue
        sub = canvas[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex]
        m = mask[sy0:ey, sx0:ex]
        if translucent:
            sub[m] = ((sub[m].astype(np.uint16) + rgb[sy0:ey, sx0:ex][m]) // 2).astype(np.uint8)
        else:
            sub[m] = rgb[sy0:ey, sx0:ex][m]
    return Image.fromarray(canvas)


def build_harness():
    """Compila build/ps1_frames.exe con gcc nativo si alguna fuente es mas nueva."""
    sources = [ROOT / "tools" / "audit" / "ps1_frames.c"] + [ROOT / "engine" / "src" / f for f in ("vm.c", "res.c", "scene.c")]
    deps = sources + list((ROOT / "engine" / "include").glob("*.h"))
    if HARNESS.exists() and all(d.stat().st_mtime <= HARNESS.stat().st_mtime for d in deps):
        return
    gcc = next((g for g in GCC_CANDIDATES if g.exists()), None)
    if not gcc:
        raise SystemExit("no hay gcc nativo (MSYS2 ucrt64)")
    env = dict(os.environ, PATH=str(gcc.parent) + os.pathsep + os.environ["PATH"])
    subprocess.run([str(gcc), "-Wall", "-Wextra", "-Wno-unused-function", "-O1", "-I", str(ROOT / "tools" / "audit" / "stub"),
                    "-I", str(ROOT / "engine" / "include"), "-o", str(HARNESS)] + [str(f) for f in sources],
                   check=True, env=env)


def story_entry(program, label):
    """(capitulo, offset) donde empieza `label`: el LOAD_CHAPTER de STORY que lo lanza o, si STORY no lo lanza
    (capitulos extra), su propia entrada. Sin etiqueta, la historia desde el principio."""
    if not label:
        return program.story_index, 0
    entry = program.meta["entries"][label]
    for off, name, a in program.chapters[program.story_index].walk():
        if name == "LOAD_CHAPTER" and a["chapter"] == entry["chapter"]:
            return program.story_index, off
    return entry["chapter"], entry["offset"]


def ps1_run(program, events, start_chapter, start_offset):
    """Ejecuta el arnes con las decisiones de Ren'Py. Devuelve [(gid, texto, draws, fails)]."""
    menus = [e for e in events if e["k"] == "menu"]
    proc = subprocess.Popen([str(HARNESS), str(DATA), str(start_chapter), str(start_offset)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, encoding="utf-8")
    out, draws, fails, mi, cur = [], [], [], 0, None
    for line in proc.stdout:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "SAY":
            ch, local, gid = map(int, parts[1:4])
            cur = (gid, program.string(ch, local))
            draws = []
        elif parts[0] == "D":
            draws.append(tuple(map(int, parts[1:])))
        elif parts[0] == "R":
            draws.append((-1,) + tuple(map(int, parts[1:])))
        elif parts[0] == "E":
            out.append((cur[0], cur[1], draws, fails))
            fails = []
        elif parts[0] == "FAIL":
            fails.append(int(parts[1]))
        elif parts[0] == "MENU":
            ch, n = int(parts[1]), int(parts[2])
            options = [norm(program.string(ch, int(t))) for t in parts[3:3 + n]]
            if mi >= len(menus):
                break
            rec = menus[mi]
            mi += 1
            wanted = norm(rec["options"][rec["chosen"]])
            best = max(range(n), key=lambda i: difflib.SequenceMatcher(None, options[i], wanted).ratio())
            proc.stdin.write(f"{best}\n")
            proc.stdin.flush()
        elif parts[0] == "END":
            break
    proc.kill()
    return out


def align(renpy_says, ps1_says):
    a = [norm(s["what"])[:60] for s in renpy_says]
    b = [norm(s[1])[:60] for s in ps1_says]
    pairs = []
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            pairs.append((block.a + k, block.b + k))
    return pairs


def score(ref, got):
    """Fraccion de celdas de 8x8 con diferencia de color notable (tolera el tramado y la reduccion)."""
    a = np.asarray(ref.resize((40, 22), Image.BOX), np.float32)
    b = np.asarray(got.resize((40, 22), Image.BOX), np.float32)
    d = np.abs(a - b).mean(axis=2)
    return float((d > 28).mean()), float(d.mean())


def missing_tags(renpy_tags, names, solids):
    """Tags que Ren'Py muestra y que no aparecen en lo que dibuja la PS1 (por el nombre base de la imagen). Los colores
    solidos se dibujan como rectangulos sin nombre y no se cuentan."""
    drawn = {n.split()[0] for n in names}
    return [" ".join(attrs) for tag, attrs in renpy_tags
            if attrs and attrs[0] not in drawn and tag not in drawn and attrs[0] not in solids]


def compare(cap, start, top):
    events = [json.loads(line) for line in (cap / "log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    program = Program(DATA)
    if start is None:
        start = next((e["name"] for e in events if e["k"] == "label" and e["name"].startswith("chapter_")), None)
    if start == "chapter_1":
        start = None
    ps1 = ps1_run(program, events, *story_entry(program, start))
    says = [e for e in events if e["k"] == "say"]
    pairs = align(says, ps1)
    print(f"{cap.name}: renpy {len(says)} lineas, ps1 {len(ps1)} lineas, emparejadas {len(pairs)}")

    images = Images()
    solids = {n.split()[0] for im in program.images if im and im["recipe"]["op"] == "solid" for n in im["names"]}
    seen, results, missing = {}, [], {}
    for ia, ib in pairs:
        shot = says[ia]["shot"]
        gid, text, draws, fails = ps1[ib]
        key = (shot, tuple(draws))
        if key in seen or not shot or not (cap / shot).exists():
            continue
        seen[key] = True
        ref = Image.open(cap / shot).convert("RGB").resize((W, H), Image.LANCZOS)
        got = compose(images, draws)
        frac, mean = score(ref, got)
        names = [program.images[d[0]]["names"][0] if d[0] >= 0 else f"rect{d[1]}" for d in draws]
        miss = missing_tags(says[ia]["tags"], names, solids)
        for m in miss:
            missing.setdefault(m, []).append(gid)
        results.append({"gid": gid, "text": text[:80], "shot": shot, "draws": draws, "fails": fails,
                        "tags": says[ia]["tags"], "frac": frac, "mean": mean, "names": names, "missing": miss})
    results.sort(key=lambda r: -r["frac"])
    rep = cap / "report"
    rep.mkdir(exist_ok=True)
    for old in rep.glob("sheet*.png"):
        old.unlink()
    (cap / "report.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (cap / "missing.json").write_text(json.dumps(missing, ensure_ascii=False, indent=1), encoding="utf-8")
    per_sheet = 6
    for s in range(0, min(top, len(results)), per_sheet):
        chunk = results[s:s + per_sheet]
        sheet = Image.new("RGB", (W * 2 + 10, (H + 30) * len(chunk)), (30, 30, 30))
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(chunk):
            ref = Image.open(cap / r["shot"]).convert("RGB").resize((W, H), Image.LANCZOS)
            sheet.paste(ref, (0, i * (H + 30)))
            sheet.paste(compose(images, r["draws"]), (W + 10, i * (H + 30)))
            d.text((2, i * (H + 30) + H + 2), f"#{s + i} gid {r['gid']} dif {r['frac']:.2f} {r['shot']}", fill=(255, 220, 40))
            d.text((2, i * (H + 30) + H + 15), " | ".join(r["names"])[:100], fill=(200, 200, 200))
        sheet.save(rep / f"sheet{s // per_sheet:03d}.png")
    bad = sum(1 for r in results if r["frac"] > 0.3)
    print(f"  {len(results)} cuadros, {bad} con diferencia > 0.30, media {np.mean([r['frac'] for r in results]):.3f}; "
          f"tags faltantes: {len(missing)}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("captures", nargs="+", type=Path)
    ap.add_argument("--from", dest="start", default=None)
    ap.add_argument("--top", type=int, default=60)
    args = ap.parse_args()
    build_harness()
    for cap in args.captures:
        compare(cap, args.start, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
