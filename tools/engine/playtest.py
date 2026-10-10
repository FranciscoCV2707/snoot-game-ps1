"""Prueba de recorrido (Fase 10): juega solo cada entrada del menu de desarrollo en PCSX-Redux sin interfaz y resume
como termino (volvio al titulo, error de la VM o se agoto el tiempo) y cuantas imagenes no se pudieron cargar.

Uso: python -m tools.engine.playtest [filas...]   (0 = historia completa; despues los capitulos de STORY y los extras)
Sin filas: la historia completa, el inicio de cada ruta y los 10 extras. Reporte: build/reports/playtest.md
"""
import argparse
import sys
from pathlib import Path

from tools.engine import emutest
from tools.simulator.vnb import Program

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "build" / "reports" / "playtest.md"
STATES = ["RUN", "SAY", "MENU", "PAUSE", "END", "ERROR", "DEV", "TRANS", "TITLE", "PMENU", "SLOTS", "OPTIONS", "GALLERY",
          "EXTRAS", "CONFIRM", "NOTICE", "SCROLL", "CREDITS"]


def dev_rows():
    """Nombres de las filas del menu de desarrollo, como las arma build_game."""
    from tools.engine.build_game import chapter_title, spanish_strings
    program = Program(ROOT / "build" / "data")
    meta = program.meta
    rows = ["Historia completa"]
    names = {e["chapter"]: label for label, e in meta["entries"].items()}
    cond = None
    recent = []
    for _, name, a in program.chapters[program.story_index].walk():
        if name == "JUMP_IF_FALSE" and [n for n, _ in recent] == ["PUSH_VAR", "PUSH_CONST", "OP"]:
            cond = recent[1][1]["value"]
        elif name == "LOAD_CHAPTER":
            label = names.get(a["chapter"], f"chapter_{a['chapter']}").removeprefix("chapter_").replace("_", ".")
            rows.append(f"Capitulo {label}" + (f" (ruta {cond})" if cond else ""))
        recent = (recent + [(name, a)])[-3:]
    es = spanish_strings()
    rows += [es.get(title, title) for title, _ in meta["extra_chapters"]]
    return rows


def default_rows(rows):
    picks = [0]
    for route in range(1, 5):
        picks.append(next(i for i, r in enumerate(rows) if r.endswith(f"(ruta {route})")))
    picks += list(range(len(rows) - 10, len(rows)))
    return picks


def play(row, out, max_frames):
    steps = "30 press L1; 30 press R1; 30 press SELECT"
    frame = 40
    for _ in range(row):
        frame += 6
        steps += f"; {frame} press DOWN"
    steps += f"; {frame + 10} press CROSS; {frame + 40} autoplay"
    emutest.run(emutest.parse_steps(steps), out, timeout=max_frames // 30 + 300, max_frames=max_frames)
    final = out.resolve() / "final.txt"
    if not final.exists():
        return {"result": "sin respuesta del emulador"}
    info = dict(item.split("=") for item in final.read_text(encoding="utf-8").split()[1:])
    state = STATES[int(info["state"])] if int(info["state"]) < len(STATES) else info["state"]
    info["result"] = "ok (volvio al titulo)" if state == "TITLE" else "ERROR de la VM" if state == "ERROR" else \
        f"sin terminar ({state})"
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows", nargs="*", type=int)
    ap.add_argument("--max-frames", type=int, default=60 * 60 * 40)
    args = ap.parse_args()
    rows = dev_rows()
    picks = args.rows or default_rows(rows)
    lines = ["# Prueba de recorrido (autoplay en PCSX-Redux)", "",
             "| Fila | Entrada | Resultado | Capitulo / pc | Imagenes sin cargar (CD / VRAM / paletas) | Cuadros |",
             "|---|---|---|---|---|---|"]
    for row in picks:
        info = play(row, ROOT / "build" / "emutest" / f"play{row:02d}", args.max_frames)
        line = (f"| {row} | {rows[row]} | {info['result']} | {info.get('cap', '?')} / {info.get('pc', '?')} | "
                f"{info.get('res_fail_read', '?')} / {info.get('res_fail_vram', '?')} / {info.get('res_fail_clut', '?')} | "
                f"{info.get('frames', '?')} |")
        print(line, flush=True)
        lines.append(line)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("reporte:", REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
