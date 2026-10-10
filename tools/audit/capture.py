"""Captura del juego original en Ren'Py para la auditoria visual (ver tools/audit/compare.py).

Copia tools/audit/zz_audit.rpy a una copia del juego y la ejecuta UNA instancia a la vez (varias en paralelo comparten
el archivo `persistent` de Ren'Py y fallan con WinError 32, ademas de saturar la PC).

Corridas: base (capitulos 1-11), r1-r4 (rutas de final desde el capitulo 11X) y x1-x10 (capitulos extra).
Uso: python -m tools.audit.capture --game <copia del juego> --renpy <renpy.exe> --out <carpeta> [corridas...]
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESKTOP = Path.home() / "Desktop" / "snoot"
ROUTE_STARTS = "chapter_11A,chapter_11B,chapter_11C,chapter_11D"

RUNS = {"base": {"SNOOT_AUDIT_UNTIL": ROUTE_STARTS}}
RUNS.update({f"r{n}": {"SNOOT_AUDIT_ROUTE": str(n)} for n in range(1, 5)})
RUNS.update({f"x{n}": {"SNOOT_AUDIT_LABEL": f"chapter_x{n}"} for n in range(1, 11)})


def run_one(name, renpy, game, out, seed, timeout):
    dest = out / name
    if dest.exists():
        shutil.rmtree(dest)
    env = dict(os.environ, SNOOT_AUDIT_OUT=str(dest), SNOOT_AUDIT_SEED=str(seed), **RUNS[name])
    start = time.time()
    with open(out / f"{name}.log", "w", encoding="utf-8") as log:
        try:
            subprocess.run([str(renpy), str(game)], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout,
                           check=False)
        except subprocess.TimeoutExpired:
            print(f"  {name}: se agoto el tiempo ({timeout} s)")
    shots = len(list(dest.glob("s*.png"))) if dest.exists() else 0
    lines = (dest / "log.jsonl").read_text(encoding="utf-8").count("\n") if (dest / "log.jsonl").exists() else 0
    print(f"  {name}: {shots} capturas, {lines} eventos, {time.time() - start:.0f} s", flush=True)
    crash = game / "traceback.txt"
    if crash.exists() and crash.stat().st_mtime > start:
        print(f"  {name}: Ren'Py fallo, ver {crash}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", default=list(RUNS))
    ap.add_argument("--game", type=Path, default=DESKTOP / "snoot_audit")
    ap.add_argument("--renpy", type=Path, default=DESKTOP / "renpy-8.3.7-sdk" / "renpy.exe")
    ap.add_argument("--out", type=Path, default=DESKTOP / "audit_out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    unknown = [r for r in args.runs if r not in RUNS]
    if unknown:
        raise SystemExit(f"corridas desconocidas: {unknown}")
    shutil.copy2(HERE / "zz_audit.rpy", args.game / "game" / "zz_audit.rpy")
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.runs:
        run_one(name, args.renpy, args.game, args.out, args.seed, args.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
