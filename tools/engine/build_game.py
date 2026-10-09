"""Construye un disco jugable con los capitulos elegidos: engine/ -> build/engine/snoot_game.bin/.cue.

Incluye los guiones, los textos y solo las imagenes que esos capitulos usan (la construccion final del CD es de la Fase 9).
Uso: python -m tools.engine.build_game [--chapters 0,1] [--start chapter_1]
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
    return out


def text_block(raw, index):
    off, size = struct.unpack_from("<II", raw, 6 + 8 * index)
    return raw[off:off + size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapters", default="0")
    ap.add_argument("--start", default="chapter_1")
    args = ap.parse_args()

    program = Program(DATA)
    meta = program.meta
    entry = meta["entries"][args.start]
    chapters = sorted({int(c) for c in args.chapters.split(",")} | {entry["chapter"]})
    raw_text = (DATA / "TEXT_ES.BIN").read_bytes()

    WORK.mkdir(parents=True, exist_ok=True)
    for old in WORK.glob("*"):
        if old.is_file() and old.suffix.upper() in (".IMG", ".VNB", ".TXT", ".BIN", ".EXE"):
            old.unlink()

    sources = [("GAME.BIN", build_game_bin(meta, entry["chapter"], entry["offset"])), ("FONT.BIN", (DATA / "FONT.BIN").read_bytes())]
    images = set()
    for idx in chapters:
        fname = "STORY.VNB" if program.chapters[idx].name == "STORY" else f"C{idx:02d}.VNB"
        sources.append((f"C{idx:02d}.VNB", (DATA / "SCRIPT" / fname).read_bytes()))
        sources.append((f"T{idx:02d}.TXT", text_block(raw_text, idx)))
        images |= chapter_images(program.chapters[idx])
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
