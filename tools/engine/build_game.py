"""Construye un disco jugable con los capitulos elegidos: engine/ -> build/engine/snoot_game.bin/.cue.

Incluye los guiones, los textos y solo las imagenes que esos capitulos usan (la construccion final del CD es de la Fase 9).
Uso: python -m tools.engine.build_game [--chapters all|0,1] [--start story|chapter_1]
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.simulator.vnb import Program  # noqa: E402

DATA = ROOT / "build" / "data"
WORK = ROOT / "build" / "engine"
ENGINE = ROOT / "engine"
SDK_BIN = Path(r"C:\msys64\usr\local\psn00bsdk\bin")

XML = """<?xml version="1.0" encoding="utf-8"?>
<iso_project>
	<track type="data">
		<identifiers system="PLAYSTATION" volume="SNOOTGAME" volume_set="SNOOTGAME"
			publisher="SNOOTPS1" data_preparer="SNOOTPS1" application="PLAYSTATION" copyright="COPY.TXT;1" />
		<directory_tree>
			<file name="SYSTEM.CNF" type="data" source="system.cnf" />
			<file name="SNOOT.EXE" type="data" source="snoot.exe" />
			<file name="MUSIC.XA" type="mixed" source="../data/MUSIC.XA" />
			<dir name="DATA">
{files}
			</dir>
			<dummy sectors="256" />
		</directory_tree>
	</track>
</iso_project>
"""

ANIM_KEY_BYTES = 15
ANIM_SWAP_BYTES = 7


def run(args, **kw):
    subprocess.run([str(a) for a in args], check=True, **kw)


def parse_color(text):
    s = text.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) if len(s) >= 6 else (255, 255, 255)


def anim_images(chapter):
    """Imagenes que una animacion cambia con eventos."""
    blob = chapter.anim_data
    if not blob:
        return set()
    images = set()
    first = struct.unpack_from("<I", blob, 0)[0]
    for i in range(first // 4):
        off = struct.unpack_from("<I", blob, 4 * i)[0]
        nkeys, _, nswaps = struct.unpack_from("<BBB", blob, off)
        base = off + 3 + nkeys * ANIM_KEY_BYTES
        for j in range(nswaps):
            images.add(struct.unpack_from("<H", blob, base + j * ANIM_SWAP_BYTES + 2)[0])
    return images


def chapter_images(chapter):
    images = set()
    for _, name, a in chapter.walk():
        if name in ("SCENE", "SHOW", "BACKGROUND", "MARK_SEEN"):
            images.add(a["image"])
        elif name == "SHOW_RANDOM":
            images.update(range(a["first"], a["first"] + a["count"]))
    return images | anim_images(chapter)


def build_game_bin(meta, start_chapter, start_offset):
    out = b"GAM1" + struct.pack("<HIH", start_chapter, start_offset, len(meta["speakers"]))
    for sp in meta["speakers"]:
        name = sp["name"].encode("utf-8")[:23]
        out += bytes(parse_color(sp["color"])) + bytes([len(name)]) + name
    out += struct.pack("<H", len(meta["positions"]))
    for pos in meta["positions"]:
        out += struct.pack("<hh", round(pos["xalign"] * 256), round(pos["yalign"] * 256))
    # imagenes de la galeria: id de imagen -> indice en la galeria
    gallery = [(iid, img["gallery"]) for iid, img in enumerate(meta["images"]) if img and img.get("gallery") is not None]
    out += struct.pack("<HH", len(meta["gallery"]), len(gallery))
    for iid, index in gallery:
        out += struct.pack("<HB", iid, index)
    return out


def spanish_strings(rel="screens.rpy"):
    """Pares old -> new de una traduccion de cadenas (titulos de los capitulos extra, creditos)."""
    out, old = {}, None
    for line in (ROOT / "original" / "game" / "tl" / "es" / rel).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("old "):
            old = line[4:].strip().strip('"')
        elif line.startswith("new ") and old is not None:
            out[old] = line[4:].strip().strip('"')
            old = None
    return out


def literal_after(text, name):
    """Valor literal de `name = [...]` o `{...}` en un archivo de Ren'Py (sin las llamadas _() de traduccion)."""
    import ast
    import re
    start = text.index(name + " = ") + len(name) + 3
    depth, i, quote = 0, start, None
    while True:
        c = text[i]
        if quote:
            quote = None if c == quote else quote       # dentro de una cadena los corchetes no cuentan
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
        if depth == 0 and not quote:
            break
    body = re.sub(r"_\((\"[^\"]*\"|'[^']*')\)", r"\1", text[start:i])
    return ast.literal_eval(body)


def credits_lines():
    """Creditos finales (`label lending`): (estilo, texto) con 0 nombre, 1 encabezado, 2 titulo."""
    text = (ROOT / "original" / "game" / "src" / "credits.rpy").read_text(encoding="utf-8")
    es = spanish_strings("src/credits.rpy")
    # en la traduccion los saltos de linea van escritos como \n; "[[" es el escape de Ren'Py para "["
    tr = lambda t: es.get(t.replace("\n", "\\n"), t).replace("\\n", "\n").replace("[[", "[")
    start, groups, end = (literal_after(text, n) for n in ("list_credits_start", "list_credits", "list_credits_end"))
    lines = [(2, tr(start[0])), (1, tr(start[1])), (0, tr(start[2])), (0, "")]
    for head, names in groups.items():
        lines.append((1, tr(head)))
        lines += [(0, tr(n)) for n in names]
        lines.append((0, ""))
    lines.append((2, tr(end[0])))
    lines += [(0, part) for part in tr(end[1]).split("\n")]
    return lines


def chapter_title(label, extras):
    if label in extras:
        return extras[label]
    return "Capítulo " + label.removeprefix("chapter_").replace("_", ".")


def ui_table(program, meta):
    """Seccion UI01 de GAME.BIN: logo y candado del titulo, imagenes de los 4 finales, nombre de cada capitulo y la
    lista de capitulos extra (en el orden del menu original) con su entrada."""
    by_name = {n: i for i, img in enumerate(meta["images"]) if img for n in img["names"]}
    endings = sorted((img["ending"], i) for i, img in enumerate(meta["images"]) if img and img.get("ending"))
    es = spanish_strings()
    extras = {label: es.get(title, title) for title, label in meta["extra_chapters"]}
    names = {e["chapter"]: label for label, e in meta["entries"].items()}
    out = b"UI01" + struct.pack("<HH", by_name.get("ui logo", 0), by_name.get("ui lock", 0))
    out += struct.pack("<4H", *[i for _, i in endings][:4])
    out += struct.pack("<H", len(program.chapters))
    for idx in range(len(program.chapters)):
        name = chapter_title(names[idx], extras).encode("utf-8")[:40] if idx in names else b""
        out += bytes([len(name)]) + name
    out += bytes([len(meta["extra_chapters"])])
    for _, label in meta["extra_chapters"]:
        e = meta["entries"][label]
        name = extras[label].encode("utf-8")[:40]
        out += struct.pack("<HIB", e["chapter"], e["offset"], len(name)) + name
    pages = sorted(i for i, img in enumerate(meta["images"]) if img and img["names"][0].startswith("ui textscroll "))
    out += struct.pack("<HB", pages[0] if pages else 0, len(pages))
    lines = credits_lines()
    out += struct.pack("<H", len(lines))
    for style, line in lines:
        data = line.strip().encode("utf-8")[:60]
        out += bytes([style, len(data)]) + data
    return out


def dev_chapter_table(program, meta):
    """Menu de desarrollo: cada LOAD_CHAPTER de STORY, con la variable de ruta que lo protege (si la hay)."""
    names = {e["chapter"]: label for label, e in meta["entries"].items()}
    story = program.chapters[program.story_index]
    out, recent, cond = [], [], None
    for off, name, a in story.walk():
        if name == "JUMP_IF_FALSE" and [n for n, _ in recent] == ["PUSH_VAR", "PUSH_CONST", "OP"]:
            cond = (recent[0][1]["var"], recent[1][1]["value"])
        elif name == "LOAD_CHAPTER":
            label = names.get(a["chapter"], f"chapter_{a['chapter']}").removeprefix("chapter_").replace("_", ".")
            text = f"Capitulo {label}" + (f"  (ruta {cond[1]})" if cond else "")
            var, value = cond if cond else (255, 0)
            out.append((off, var, value, text.encode("utf-8")))
        recent = (recent + [(name, a)])[-3:]
    blob = struct.pack("<HH", program.story_index, len(out))
    for off, var, value, text in out:
        blob += struct.pack("<IBBB", off, var, value, len(text)) + text
    return blob


def text_block(raw, index):
    off, size = struct.unpack_from("<II", raw, 6 + 8 * index)
    return raw[off:off + size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapters", default="all", help="indices separados por coma, o all")
    ap.add_argument("--start", default="story", help="story (la historia completa, capitulo tras capitulo) o una etiqueta")
    ap.add_argument("--autotest", type=Path, help="AUTOTEST.BIN de una prueba automatica (tools/engine/emutest.py)")
    args = ap.parse_args()

    program = Program(DATA)
    meta = program.meta
    if args.start == "story":
        entry = {"chapter": program.story_index, "offset": 0}
    else:
        entry = meta["entries"][args.start]
    if args.chapters == "all":
        wanted = set(range(len(program.chapters)))
    else:
        wanted = {int(c) for c in args.chapters.split(",")}
    chapters = sorted(wanted | {entry["chapter"]})
    raw_text = (DATA / "TEXT_ES.BIN").read_bytes()

    WORK.mkdir(parents=True, exist_ok=True)
    for old in WORK.glob("*"):
        if old.is_file() and old.suffix.upper() in (".IMG", ".VNB", ".TXT", ".BIN", ".EXE", ".SPU"):
            old.unlink()

    game_bin = build_game_bin(meta, entry["chapter"], entry["offset"])
    game_bin += dev_chapter_table(program, meta) if args.chapters == "all" else struct.pack("<HH", program.story_index, 0)
    game_bin += ui_table(program, meta)
    sources = [("GAME.BIN", game_bin), ("FONT.BIN", (DATA / "FONT.BIN").read_bytes()),
               ("AUDIO.BIN", (DATA / "audio_index.bin").read_bytes()), ("MCICON.BIN", (DATA / "MCICON.BIN").read_bytes())]
    sources += [(f.name, f.read_bytes()) for f in sorted((DATA / "SFX").glob("S*.SPU"))]
    if args.autotest:
        sources.append(("AUTOTEST.BIN", args.autotest.read_bytes()))
    images = set()
    for idx in chapters:
        fname = "STORY.VNB" if program.chapters[idx].name == "STORY" else f"C{idx:02d}.VNB"
        sources.append((f"C{idx:02d}.VNB", (DATA / "SCRIPT" / fname).read_bytes()))
        sources.append((f"T{idx:02d}.TXT", text_block(raw_text, idx)))
        images |= chapter_images(program.chapters[idx])
    images |= {i for i, img in enumerate(meta["images"]) if img and img["names"][0].startswith("ui ")}
    images.discard(0)
    for i in sorted(images):
        path = DATA / "IMG" / f"I{i:04d}.IMG"
        if path.exists():
            sources.append((path.name, path.read_bytes()))

    names = []
    for name, data in sources:
        (WORK / name).write_bytes(data)
        names.append(f'\t\t\t<file name="{name}" type="data" source="{name}" />')
    (WORK / "system.cnf").write_text("BOOT=cdrom:\\SNOOT.EXE;1\nTCB=4\nEVENT=10\nSTACK=801FFFF0\n", encoding="utf-8")
    (WORK / "iso.xml").write_text(XML.format(files="\n".join(names)), encoding="utf-8")

    env = dict(os.environ, PATH=str(SDK_BIN) + os.pathsep + os.environ["PATH"])
    run(["cmake", "--preset", "default", "."], cwd=ENGINE, env=env)
    run(["cmake", "--build", "build"], cwd=ENGINE, env=env)
    shutil.copy(ENGINE / "build" / "snoot.exe", WORK / "snoot.exe")
    run([SDK_BIN / "mkpsxiso.exe", "-y", "-o", "snoot_game.bin", "-c", "snoot_game.cue", "iso.xml"], cwd=WORK)
    print(f"capitulos {chapters}, {len(images)} imagenes, inicio {args.start}")
    print("Disco listo:", WORK / "snoot_game.cue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
