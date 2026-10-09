"""Construye el disco de la demo de la Fase 6: engine/ -> build/engine/snoot_demo.bin/.cue.

Elige un fondo, un personaje y tres lineas reales en espanol (con signos de apertura y acentos) y genera DEMO.BIN.
Uso: python -m tools.engine.build_demo
"""
import json
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
BG_NAME = "classroom"
SPRITE_NAME = "fang neutral"
SPRITE_XALIGN = 0.62
WANTED = ("¿", "ñ", "¡")          # una linea con cada uno, para comprobar los glifos

XML = """<?xml version="1.0" encoding="utf-8"?>
<iso_project>
	<track type="data">
		<identifiers system="PLAYSTATION" volume="SNOOTDEMO" volume_set="SNOOTDEMO"
			publisher="SNOOTPS1" data_preparer="SNOOTPS1" application="PLAYSTATION" copyright="COPY.TXT;1" />
		<directory_tree>
			<file name="SYSTEM.CNF" type="data" source="system.cnf" />
			<file name="SNOOT.EXE" type="data" source="snoot.exe" />
			<file name="FONT.BIN" type="data" source="FONT.BIN" />
			<file name="DEMO.BIN" type="data" source="DEMO.BIN" />
{files}
			<dummy sectors="256" />
		</directory_tree>
	</track>
</iso_project>
"""


def run(args, **kw):
    subprocess.run([str(a) for a in args], check=True, **kw)


def find_image(meta, name):
    for i, im in enumerate(meta["images"]):
        if im and im["names"][0] == name:
            return i
    raise SystemExit(f"imagen no encontrada: {name}")


def pick_lines(program, meta):
    """Tres lineas con diferente hablante y cada uno de los caracteres especiales."""
    speakers = meta["speakers"]
    chosen = []
    for ch in meta["chapters"]:
        idx = ch["index"]
        chapter = program.chapters[idx]
        for pc, name, a in chapter.walk():
            if name != "SAY" or a["speaker"] == 0 or speakers[a["speaker"]]["name"].startswith("("):
                continue
            text = program.string(idx, a["text"])
            for ch_ in WANTED:
                if ch_ in text and all(ch_ != c[0] for c in chosen) and 25 < len(text) < 130 and "\x0b" not in text:
                    chosen.append((ch_, a["speaker"], text))
                    break
            if len(chosen) == len(WANTED):
                return [(speakers[s], t) for _, s, t in chosen]
    raise SystemExit("no se encontraron lineas de ejemplo")


def parse_color(text):
    s = text.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) if len(s) >= 6 else (255, 255, 255)


def build_demo_bin(bg_id, sprite_id, lines):
    out = b"DMO1" + struct.pack("<HHHH", bg_id, sprite_id, len(lines), int(SPRITE_XALIGN * 256))
    for speaker, text in lines:
        name = speaker["name"].encode("utf-8")[:23]
        body = text.encode("utf-8")
        r, g, b = parse_color(speaker["color"])
        out += struct.pack("<B", len(name)) + name + struct.pack("<BBBH", r, g, b, len(body)) + body + b"\x00"
    return out


def main():
    program = Program(DATA)
    meta = program.meta
    bg_id, sprite_id = find_image(meta, BG_NAME), find_image(meta, SPRITE_NAME)
    lines = pick_lines(program, meta)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "DEMO.BIN").write_bytes(build_demo_bin(bg_id, sprite_id, lines))
    shutil.copy(DATA / "FONT.BIN", WORK / "FONT.BIN")
    names = []
    for i in (bg_id, sprite_id):
        shutil.copy(DATA / "IMG" / f"I{i:04d}.IMG", WORK / f"I{i:04d}.IMG")
        names.append(f'\t\t\t<file name="I{i:04d}.IMG" type="data" source="I{i:04d}.IMG" />')
    (WORK / "system.cnf").write_text("BOOT=cdrom:\\SNOOT.EXE;1\nTCB=4\nEVENT=10\nSTACK=801FFFF0\n", encoding="utf-8")
    (WORK / "iso.xml").write_text(XML.format(files="\n".join(names)), encoding="utf-8")

    env = dict(os.environ, PATH=str(SDK_BIN) + os.pathsep + os.environ["PATH"])
    run(["cmake", "--preset", "default", "."], cwd=ENGINE, env=env)
    run(["cmake", "--build", "build"], cwd=ENGINE, env=env)
    shutil.copy(ENGINE / "build" / "snoot.exe", WORK / "snoot.exe")
    run([SDK_BIN / "mkpsxiso.exe", "-y", "-o", "snoot_demo.bin", "-c", "snoot_demo.cue", "iso.xml"], cwd=WORK)
    print(f"fondo #{bg_id} '{BG_NAME}', personaje #{sprite_id} '{SPRITE_NAME}'")
    for speaker, text in lines:
        print(f"  {speaker['name']}: {text[:70]!r}")
    print("Disco listo:", WORK / "snoot_demo.cue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
