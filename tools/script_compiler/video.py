"""Seleccion de fotogramas de un video para convertirlo en animacion (D3)."""
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

FRAMES_WANTED = 10
SIZE = (320, 180)


def ffmpeg_path(name="ffmpeg"):
    return shutil.which(name) or str(Path.home() / "AppData/Local/Microsoft/WinGet/Links" / f"{name}.exe")


@lru_cache(maxsize=None)
def decode(path):
    w, h = SIZE
    raw = subprocess.run([ffmpeg_path(), "-loglevel", "error", "-i", str(path), "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.int16)


@lru_cache(maxsize=None)
def fps(path):
    out = subprocess.run([ffmpeg_path("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    num, den = out.split("/")
    return int(num) / int(den)


def select_frames(path, wanted=FRAMES_WANTED):
    """Elige ~`wanted` fotogramas: cada vez que la imagen cambia lo bastante respecto al ultimo mostrado.

    Devuelve {"frames": [(indice, tiempo en s)], "times": [duracion de cada fotograma en s]}.
    """
    frames = decode(Path(path))
    rate = fps(Path(path))

    def pick(threshold):
        chosen, cur = [0], 0
        for i in range(1, len(frames)):
            if np.abs(frames[i] - frames[cur]).mean() > threshold:
                chosen.append(i)
                cur = i
        return chosen

    lo, hi = 0.1, 40.0
    best = pick(hi)
    for _ in range(14):
        mid = (lo + hi) / 2
        chosen = pick(mid)
        if len(chosen) > wanted:
            lo = mid
        else:
            hi, best = mid, chosen
    starts = [i / rate for i in best]
    total = len(frames) / rate
    times = [(starts[k + 1] if k + 1 < len(starts) else total) - starts[k] for k in range(len(starts))]
    return {"frames": [(i, i / rate) for i in best], "times": times}


PATCH_GAP = 2          # un cuadro cada 2 como minimo durante el movimiento (12 por segundo)
PATCH_THRESHOLD = 0.15  # cambio medio minimo respecto al cuadro mostrado para elegir uno nuevo
PATCH_DIFF = 20         # diferencia por pixel (0-255) para considerar que algo cambio respecto al cuadro base
PATCH_MARGIN = 2


def select_patches(path, gap=PATCH_GAP, threshold=PATCH_THRESHOLD):
    """Animacion por parches: cuadro base (el primero) y, para los cuadros elegidos, el rectangulo que difiere del base.

    Devuelve {"frames": [(indice, (x0, y0, x1, y1) a 320x180 o None si es igual al base)], "times": [segundos]}.
    El movimiento se muestrea a 24/gap cuadros por segundo; las pausas quedan como un solo cuadro largo.
    """
    frames = decode(Path(path))
    rate = fps(Path(path))
    chosen, last = [0], 0
    for i in range(1, len(frames)):
        if i - last >= gap and np.abs(frames[i] - frames[last]).mean() > threshold:
            chosen.append(i)
            last = i
    h, w = frames.shape[1:3]
    picks = []
    for i in chosen:
        ys, xs = np.where(np.abs(frames[i] - frames[0]).max(axis=2) > PATCH_DIFF)
        if len(xs) == 0:
            picks.append((i, None))
            continue
        rect = (max(0, int(xs.min()) - PATCH_MARGIN), max(0, int(ys.min()) - PATCH_MARGIN),
                min(w, int(xs.max()) + 1 + PATCH_MARGIN), min(h, int(ys.max()) + 1 + PATCH_MARGIN))
        rect = (rect[0] & ~1, rect[1], (rect[2] + 1) & ~1, rect[3])    # ancho par
        picks.append((i, rect))
    starts = [i / rate for i in chosen]
    total = len(frames) / rate
    times = [(starts[k + 1] if k + 1 < len(starts) else total) - starts[k] for k in range(len(starts))]
    return {"frames": picks, "times": times}
