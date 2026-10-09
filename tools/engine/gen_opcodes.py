"""Genera engine/include/opcodes.h a partir de tools/script_compiler/opcodes.py (una sola fuente de verdad)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.script_compiler.opcodes import OPERATORS, OPS  # noqa: E402


def main():
    lines = ["/* Generado por tools/engine/gen_opcodes.py: no editar a mano. */", "#pragma once", ""]
    for name, (code, fmt, fields) in OPS.items():
        lines.append(f"#define OP_{name} 0x{code:02X}")
    lines += ["", "typedef struct {", "\tconst char *name;", "\tconst char *fmt;     /* B u8, b s8, H u16, h s16, I u32; NULL = longitud variable (MENU) */", "\tint nfields;", "} OpInfo;", "",
              "static const OpInfo *op_info(int code)", "{", "\tswitch (code) {"]
    for name, (code, fmt, fields) in OPS.items():
        f = "NULL" if fmt is None else f'"{fmt}"'
        lines.append(f'\tcase OP_{name}: {{ static const OpInfo i = {{ "{name}", {f}, {len(fields)} }}; return &i; }}')
    lines += ["\tdefault: return 0;", "\t}", "}", ""]
    ops = ", ".join(f'"{o}"' for o in OPERATORS)
    lines += [f"#define OPERATOR_COUNT {len(OPERATORS)}", f"/* orden: {' '.join(OPERATORS)} */", ""]
    for i, o in enumerate(OPERATORS):
        lines.append(f"#define OPR_{i} {i}  /* {o} */")
    (ROOT / "engine" / "include" / "opcodes.h").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("engine/include/opcodes.h:", len(OPS), "instrucciones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
