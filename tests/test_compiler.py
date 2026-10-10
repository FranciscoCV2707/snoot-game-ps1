import struct
from pathlib import Path

import pytest

from tools.script_compiler import assemble, textfmt
from tools.script_compiler.lower import Inst, parse_transition, textbox_mode
from tools.script_compiler.opcodes import OP_CODE, OPS
from tools.simulator.report import extras_available
from tools.simulator.vm import VM, Coverage
from tools.simulator.vnb import Chapter

ROOT = Path(__file__).resolve().parents[1]
GAME_PRESENT = (ROOT / "original" / "game" / "script.rpy").exists()


def test_text_codes():
    text, dropped = textfmt.convert("Hola {i}mundo{/i}{w=.5}{cps=*.1}...{/cps}{nw}{color=#f00}x{/color}")
    assert text == "Hola \x01\x01mundo\x01\x00\x02\x05\x03\x05...\x03\x00\x04x"
    assert dropped == ["color"]
    assert textfmt.strip_codes(text) == "Hola mundo...x"


def test_text_escapes():
    text, _ = textfmt.convert("[[Aviso]] {{ok}} 100%%")
    assert text == "[Aviso]] {ok}} 100%"


def test_paginate_splits_lines_and_pages():
    measure = lambda s: 10 * len(s)   # 10 px por caracter
    text, pages = textfmt.paginate("aaaa bbbb cccc dddd eeee", measure, 90, 2)
    assert text == "aaaa bbbb\ncccc dddd\x0Beeee"
    assert pages == 2


def test_parse_transition():
    assert parse_transition("Dissolve(1.5)") == (1, 90, 0, 0)
    assert parse_transition("Fade(1, 0, 1)") == (2, 60, 0, 60)
    assert parse_transition("vpunch") == (3, 17, 10, 0)
    assert parse_transition("Fade(.5, 0, .5, color='#fff')") == (6, 30, 0, 30)
    assert parse_transition("easeinbottom") == (5, 30, 4, 1)
    assert parse_transition("easeoutright") == (5, 30, 2 << 4, 2)
    assert parse_transition("moveoutleft") == (5, 30, 1 << 4, 0)
    assert parse_transition("MoveTransition(0.5, time_warp=_ease_in_time_warp)") == (5, 30, 0, 1)
    assert parse_transition("None") == (0, 0, 0, 0)
    assert parse_transition("Frobnicate(2)") is None


def test_textbox_mode():
    assert textbox_mode("hide", None) == 0
    assert textbox_mode("auto", None) == 1
    assert textbox_mode("show", "Dissolve(0.0001)") == 2 | 4
    assert textbox_mode("hide", "Dissolve(0.0)") == 0 | 4
    assert textbox_mode("hide", "Dissolve(0.5)") == 0


def test_extras_logic():
    assert extras_available(0b0000, 0) == []
    assert extras_available(0b0001, 0) == [0, 1, 2]
    assert extras_available(0b0011, 0) == [0, 1, 2, 3, 6]
    assert extras_available(0b1111, 0) == list(range(9))
    assert extras_available(0b1111, 0b111111111) == list(range(10))


def test_assemble_and_decode_roundtrip():
    insts = [
        Inst("LABEL", {"name": "start"}),
        Inst("SAY", {"speaker": 3, "text": 7}),
        Inst("PUSH_VAR", {"var": 1}), Inst("PUSH_CONST", {"value": -5}), Inst("OP", {"op": OP_CODE["<"]}),
        Inst("JUMP_IF_FALSE", {"target": "end"}),
        Inst("MENU", {"flags": 1, "choices": [(1, "start"), (2, "end")]}),
        Inst("LABEL", {"name": "end"}),
        Inst("RETURN", {}),
    ]
    offsets, size = assemble.layout(insts)
    code = assemble.encode(insts, offsets, None, "t")
    assert len(code) == size
    blob = assemble.build_vnb(5, code, [(0, 0)], 100, 8, b"", 0)
    ch = Chapter(blob, "t")
    ops = [name for _, name, _ in ch.walk()]
    assert ops == ["SAY", "PUSH_VAR", "PUSH_CONST", "OP", "JUMP_IF_FALSE", "MENU", "RETURN"]
    assert ch.number == 5 and ch.text_base == 100
    _, args, _ = ch.decode(0)
    assert args == {"speaker": 3, "text": 7}


def test_vm_operators():
    stack = [3, 4]
    VM.op(stack, OP_CODE["<"], None, 0)
    assert stack == [1]
    stack = [1, 0]
    VM.op(stack, OP_CODE["and"], None, 0)
    assert stack == [0]
    stack = [0]
    VM.op(stack, OP_CODE["not"], None, 0)
    assert stack == [1]


def test_opcodes_unique():
    codes = [v[0] for v in OPS.values()]
    assert len(codes) == len(set(codes))
    for name, (code, fmt, fields) in OPS.items():
        if fmt is not None:
            assert struct.calcsize("<" + fmt) >= len(fields) or not fields


@pytest.mark.skipif(not GAME_PRESENT, reason="falta original/")
def test_full_compile_and_exploration(tmp_path):
    from tools.script_compiler.compile import compile_all
    from tools.simulator.vm import explore
    from tools.simulator.vnb import Program

    project, registry, result = compile_all(tmp_path)
    assert result.errors == []
    program = Program(tmp_path)
    starts = [(program.story_index, 0)] + [(e["chapter"], e["offset"]) for n, e in program.meta["entries"].items()
                                            if n.startswith("chapter_x")]
    cov = explore(program, starts)
    assert cov.errors == []
    assert cov.endings == {1, 2, 3, 4}
    assert cov.labels >= {n for n in program.meta["labels"].values()}
    assert cov.bonus == set(range(9))
    assert len(cov.text_ids) >= program.meta["text_total"] - 6
    inputs = [a for ch in program.chapters.values() for _, name, a in ch.walk() if name == "SPECIAL" and a["id"] == 3]
    assert len(inputs) == 1                  # renpy.input de 13D: teclado en pantalla
