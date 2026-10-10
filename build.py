"""Construye el juego completo con un solo comando (Fase 9).

Pasos: scripts -> simulador (se detiene si hay errores) -> imagenes -> audio (solo si cambio) -> motor -> disco.
Uso (PowerShell, con el entorno activado):
    python build.py               todo
    python build.py --solo-scripts
    python build.py --solo-motor  motor y disco (sin reconvertir datos)
    python build.py --limpio      borra los datos convertidos y empieza de cero
Resultado: build/engine/snoot_game.bin y .cue
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "build" / "data"
SDK_BIN = Path(r"C:\msys64\usr\local\psn00bsdk\bin")
MSYS_DLLS = [Path(r"C:\msys64\ucrt64\bin"), Path(r"C:\msys64\usr\bin")]
CD_SECTORS = 333000                  # CD de 74 minutos


def step(title, args, env=None):
    print(f"== {title}", flush=True)
    t0 = time.time()
    result = subprocess.run([sys.executable, "-m"] + args, cwd=ROOT, env=env)
    if result.returncode != 0:
        raise SystemExit(f"fallo: {title}")
    print(f"   {time.time() - t0:.0f} s", flush=True)


def audio_hash():
    """El audio se reconvierte solo si cambia la lista de audio del compilador o el convertidor."""
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    h = hashlib.sha256(json.dumps(meta["audio"], sort_keys=True).encode("utf-8"))
    h.update((ROOT / "tools" / "audio" / "convert.py").read_bytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-scripts", action="store_true")
    ap.add_argument("--solo-motor", action="store_true")
    ap.add_argument("--limpio", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    env = dict(os.environ, PATH=os.pathsep.join([str(SDK_BIN), os.environ["PATH"]] + [str(p) for p in MSYS_DLLS]),
               PYTHONUTF8="1")
    if args.limpio and DATA.exists():
        shutil.rmtree(DATA)

    if not args.solo_motor:
        step("scripts", ["tools.script_compiler.compile"], env)
        step("simulador (todas las rutas)", ["tools.simulator", "--report"], env)
        if args.solo_scripts:
            return 0
        step("imagenes", ["tools.images.convert"], env)
        stamp = DATA / "audio.hash"
        current = audio_hash()
        if not (DATA / "MUSIC.XA").exists() or not stamp.exists() or stamp.read_text(encoding="utf-8") != current:
            step("audio", ["tools.audio.convert"], env)
            stamp.write_text(current, encoding="utf-8")
        else:
            print("== audio: sin cambios", flush=True)

    step("motor y disco", ["tools.engine.build_game"], env)
    bin_file = ROOT / "build" / "engine" / "snoot_game.bin"
    sectors = bin_file.stat().st_size // 2352
    print(f"\nDisco: {bin_file}")
    print(f"Tamano: {bin_file.stat().st_size / 1e6:.0f} MB, {sectors} sectores ({100 * sectors / CD_SECTORS:.1f}% de un CD de "
          f"74 min, {100 - 100 * sectors / CD_SECTORS:.1f}% libre)")
    print(f"Tiempo total: {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
