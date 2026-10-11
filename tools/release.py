"""Empaqueta una version para probadores: disco limpio (sin guion de prueba) + LEEME, en dist/ y en un .zip.

Uso: python -m tools.release 0.1
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISC = ROOT / "build" / "engine"
DIST = ROOT / "dist"

README = """Snoot Game para PlayStation - version {version} (prueba)
=========================================================

Port hecho por fans de Snoot Game (Cavemanon) a la PlayStation original. Esta es una version de prueba: puede tener
errores. Si encuentras alguno, avisanos (ver abajo).

Como jugar
----------
- Emulador recomendado: DuckStation. Abre "snoot_game.cue" (no el .bin).
- Hace falta una BIOS de PlayStation en el emulador (la que pide DuckStation).
- Para guardar se necesita una memory card en la ranura 1 (el emulador la crea sola). Usa 2 bloques.
- En consola real: graba el .bin/.cue en un CD-R (consola con chip o con un metodo para cargar copias).
  En PS2 con POPStarter (.VCD) es un emulador, no la consola real: puede fallar donde el CD-R funciona.
- Si se queda en la pantalla de inicio en "Leyendo memory card...", manten Select presionado al
  encender: se juega sin memory card (no se guarda).

Controles
---------
  X          avanzar el texto / aceptar
  O          volver
  Start      pausa (Guardar, Cargar, Opciones, Saltar texto leido, Salir al titulo)
  R1         saltar el texto ya leido (se detiene en lo nuevo y en las decisiones)
  Cuadrado   ocultar la caja de texto
  Cruceta    elegir en los menus y decisiones
  Teclado (capitulo 13D): cruceta mover, X tecla, O borrar, L1 mayusculas, Start listo

Como reportar un error
----------------------
Cuenta, por favor:
1. Que paso (por ejemplo: "falta un personaje", "se congelo", "no suena la musica", "se ve encimado").
2. Donde: capitulo y la linea de texto que estaba en pantalla (o una foto/captura).
3. Emulador o consola que usaste (y su version).
4. Si se puede repetir: que hiciste justo antes.

Notas
-----
- La musica es mono y las imagenes estan reducidas a la resolucion de la PlayStation (320x240).
- Las animaciones y transiciones se aproximan con lo que puede hacer la consola.
- Snoot Game es de Cavemanon. Este port es gratuito y no tiene relacion oficial con ellos.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    args = ap.parse_args()
    # el disco se rehace siempre: las pruebas automaticas dejan un guion (AUTOTEST.BIN) en el disco de build/
    subprocess.run([sys.executable, "-m", "tools.engine.build_game"], cwd=ROOT, check=True)
    name = f"SnootGamePS1-v{args.version}"
    out = DIST / name
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DISC / "snoot_game.bin", out / "snoot_game.bin")
    shutil.copy2(DISC / "snoot_game.cue", out / "snoot_game.cue")
    (out / "LEEME.txt").write_text(README.format(version=args.version), encoding="utf-8")
    archive = DIST / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f"{name}/{f.name}")
    print("listo:", archive, f"({archive.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
