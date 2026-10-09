"""Uso: python -m tools.simulator [--dis N] | [--explore]  (carpeta build/data)."""
import argparse
import sys
from pathlib import Path

from tools.simulator.vm import explore
from tools.simulator.vnb import Program, disassemble

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "build" / "data"))
    ap.add_argument("--dis", type=int, help="desensambla el capitulo N")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--report", action="store_true", help="escribe build/reports/cobertura.md")
    args = ap.parse_args()
    program = Program(args.data)
    if args.report:
        from tools.simulator.report import REPORT, build_report
        cov, _ = build_report(program)
        print("finales:", sorted(cov.endings), "errores:", len(cov.errors), "->", REPORT)
        return 1 if cov.errors else 0
    if args.dis is not None:
        print(disassemble(program, args.dis, args.limit))
        return 0
    if args.explore:
        starts = [(program.story_index, 0)]
        for name, entry in program.meta["entries"].items():
            if name.startswith("chapter_x"):
                starts.append((entry["chapter"], entry["offset"]))
        cov = explore(program, starts)
        print("estados:", cov.states, "ejecuciones:", cov.runs, "finales:", sorted(cov.endings), "etiquetas:", len(cov.labels))
        print("errores:", cov.errors[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
