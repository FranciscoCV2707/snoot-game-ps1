"""Lectura y desensamblado de archivos .VNB (los mismos bytes que leera el motor de PS1)."""
import json
import struct
from pathlib import Path

from tools.script_compiler.opcodes import BY_CODE, OPERATORS, VERSION

HEADER_FMT = "<HHIIHHIII"
HEADER_SIZE = 32


class Chapter:
    def __init__(self, data, name):
        if data[:4] != VERSION:
            raise ValueError(f"{name}: version desconocida {data[:4]!r}")
        (self.number, nlabels, code_size, self.text_base, self.text_count, nanims,
         label_off, anim_off, _) = struct.unpack_from(HEADER_FMT, data, 4)
        self.name = name
        self.code = data[HEADER_SIZE:HEADER_SIZE + code_size]
        self.labels = [struct.unpack_from("<HI", data, label_off + 6 * i) for i in range(nlabels)]
        self.anim_data = data[anim_off:]

    def decode(self, pc):
        """Devuelve (nombre, argumentos, tamano) de la instruccion en pc."""
        code = self.code[pc]
        if code not in BY_CODE:
            raise ValueError(f"{self.name}: opcode invalido {code:#x} en {pc}")
        name, fmt, fields = BY_CODE[code]
        if name == "MENU":
            flags, n = struct.unpack_from("<BB", self.code, pc + 1)
            choices = [struct.unpack_from("<HI", self.code, pc + 3 + 6 * i) for i in range(n)]
            return name, {"flags": flags, "choices": choices}, 3 + 6 * n
        size = struct.calcsize("<" + fmt)
        values = struct.unpack_from("<" + fmt, self.code, pc + 1)
        return name, dict(zip(fields, values)), 1 + size

    def walk(self):
        pc = 0
        while pc < len(self.code):
            name, args, size = self.decode(pc)
            yield pc, name, args
            pc += size


class TextTable:
    def __init__(self, data):
        if data[:4] != b"TXT1":
            raise ValueError("TEXT_ES.BIN invalido")
        count = struct.unpack_from("<H", data, 4)[0]
        self.blocks = []
        for i in range(count):
            off, size = struct.unpack_from("<II", data, 6 + 8 * i)
            n = struct.unpack_from("<H", data, off)[0]
            offsets = struct.unpack_from(f"<{n}I", data, off + 2)
            strings = []
            for o in offsets:
                start = off + 2 + o
                end = data.index(b"\x00", start)
                strings.append(data[start:end].decode("utf-8"))
            self.blocks.append(strings)


class Program:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.meta = json.loads((self.dir / "meta.json").read_text(encoding="utf-8"))
        self.chapters = {}
        for c in self.meta["chapters"]:
            fname = "STORY.VNB" if c["name"] == "STORY" else f"C{c['index']:02d}.VNB"
            self.chapters[c["index"]] = Chapter((self.dir / "SCRIPT" / fname).read_bytes(), c["name"])
        self.story_index = next(c["index"] for c in self.meta["chapters"] if c["name"] == "STORY")
        self.text = TextTable((self.dir / "TEXT_ES.BIN").read_bytes())
        self.label_names = {int(k): v for k, v in self.meta["labels"].items()}
        self.label_at = {}
        for idx, ch in self.chapters.items():
            for lid, off in ch.labels:
                self.label_at[(idx, off)] = self.label_names[lid]
        self.images = self.meta["images"]
        self.vars_by_index = {v: k for k, v in self.meta["vars"].items()}

    def string(self, chapter, local):
        return self.text.blocks[chapter][local]


def disassemble(program, chapter_index, limit=None):
    ch = program.chapters[chapter_index]
    lines = []
    for pc, name, args in ch.walk():
        label = program.label_at.get((chapter_index, pc))
        if label:
            lines.append(f"{label}:")
        detail = ", ".join(f"{k}={v}" for k, v in args.items())
        if name == "SAY" or name == "SAYX":
            detail += f"  ; {program.string(chapter_index, args['text'])[:50]!r}"
        elif name == "OP":
            detail = OPERATORS[args["op"]]
        lines.append(f"  {pc:6d}  {name:14s} {detail}")
        if limit and len(lines) >= limit:
            break
    return "\n".join(lines)
