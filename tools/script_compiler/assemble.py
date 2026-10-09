"""Ensamblador: instrucciones (IR) -> archivo .VNB y tablas de texto (Fase 3, etapa 5)."""
import struct

from tools.script_compiler.opcodes import JUMP_OPS, OPS, VERSION, size_of

HEADER_SIZE = 32


class AssembleError(Exception):
    pass


def layout(insts):
    """Primera pasada: offsets de etiquetas y tamano del codigo."""
    offsets, pos = {}, 0
    for inst in insts:
        if inst.op == "LABEL":
            offsets.setdefault(inst.args["name"], pos)
        else:
            pos += size_of(inst.op, inst.args)
    return offsets, pos


def encode(insts, local_labels, entry_resolver, name):
    out = bytearray()
    for inst in insts:
        if inst.op == "LABEL":
            continue
        code, fmt, fields = OPS[inst.op]
        out.append(code)
        a = dict(inst.args)
        try:
            if inst.op == "MENU":
                out += struct.pack("<BB", a["flags"], len(a["choices"]))
                for text, label in a["choices"]:
                    out += struct.pack("<HI", text, local_labels[label])
                continue
            if inst.op in JUMP_OPS:
                a["target"] = local_labels[a["target"]]
            if inst.op == "LOAD_CHAPTER":
                a["entry"] = entry_resolver(a["chapter"], a["entry"])
            out += struct.pack("<" + fmt, *[a[f] for f in fields])
        except KeyError as exc:
            raise AssembleError(f"{name}:{inst.line}: {inst.op} referencia desconocida {exc}")
        except struct.error as exc:
            raise AssembleError(f"{name}:{inst.line}: {inst.op} {a}: {exc}")
    return bytes(out)


def build_vnb(chapter_number, code, label_table, text_base, text_count, anim_blob, anim_count):
    labels_blob = b"".join(struct.pack("<HI", lid, off) for lid, off in label_table)
    label_off = HEADER_SIZE + len(code)
    anim_off = label_off + len(labels_blob)
    header = VERSION + struct.pack("<HHIIHHIII", chapter_number, len(label_table), len(code), text_base,
                                   text_count, anim_count, label_off, anim_off, 0)
    assert len(header) == HEADER_SIZE
    return header + code + labels_blob + anim_blob


def build_text_table(chapters):
    """TEXT_ES.BIN. chapters: lista de (indice de capitulo, [cadenas con codigos])."""
    blocks = []
    for _, strings in chapters:
        encoded = [s.encode("utf-8") + b"\x00" for s in strings]
        offsets, pos = [], 4 * len(encoded)
        for e in encoded:
            offsets.append(pos)
            pos += len(e)
        blocks.append(struct.pack("<H", len(encoded)) + struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(encoded))
    header = b"TXT1" + struct.pack("<H", len(blocks))
    table_size = 8 * len(blocks)
    pos = len(header) + table_size
    table = b""
    for block in blocks:
        table += struct.pack("<II", pos, len(block))
        pos += len(block)
    return header + table + b"".join(blocks)
