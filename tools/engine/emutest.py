"""Prueba automatica en emulador: el disco trae un guion de botones (AUTOTEST.BIN) que el motor ejecuta, y PCSX-Redux
corre sin interfaz tomando las capturas que el guion pide.

No usa el teclado ni la pantalla de la PC, asi que se puede correr mientras se usa la computadora. Los cuadros se
cuentan con VSync desde que aparece el titulo (el motor los cuenta), asi que no dependen de cuanto tarde el arranque.

Pasos: "cuadro accion [argumento]" separados por ";". Acciones: press BOTON, hold BOTON CUADROS, shot NOMBRE, quit, autoplay (el motor
avanza solo y cierra el emulador al volver al titulo o ante un error).
Botones: CROSS, CIRCLE, SQUARE, TRIANGLE, START, SELECT, UP, DOWN, LEFT, RIGHT, L1, R1, L2, R2.
Ejemplo: python -m tools.engine.emutest --steps "300 shot titulo; 320 press CROSS; 900 shot juego; 910 quit"
Salida: <out>/<nombre>.png; la memory card de prueba queda en <out>/card1.mcd (con --keep-card se reusa).
"""
import argparse
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = Path.home() / "Desktop" / "snoot"
REDUX = DESKTOP / "pcsx-redux-nightly-26946.20261008.32-x64" / "pcsx-redux.exe"
BIOS = DESKTOP / "ps1 bios" / "SCPH1001.BIN"
CUE = ROOT / "build" / "engine" / "snoot_game.cue"
ELF = ROOT / "engine" / "build" / "snoot.elf"
NM = Path(r"C:\msys64\usr\local\psn00bsdk\bin\mipsel-none-elf-nm.exe")

BUTTONS = {"SELECT": 1 << 0, "START": 1 << 3, "UP": 1 << 4, "RIGHT": 1 << 5, "DOWN": 1 << 6, "LEFT": 1 << 7,
           "L2": 1 << 8, "R2": 1 << 9, "L1": 1 << 10, "R1": 1 << 11, "TRIANGLE": 1 << 12, "CIRCLE": 1 << 13,
           "CROSS": 1 << 14, "SQUARE": 1 << 15}
SHOT, QUIT, AUTOPLAY = 0xFFFF, 0xFFFE, 0xFFFD
WATCH = ("frames", "res_fail_read", "res_fail_vram", "res_fail_clut", "res_snap_skip", "stall_count", "stall_max",
         "stall_total", "cd_sync_count", "cd_sync_vblanks", "cd_sync_sectors", "cd_wait_vblanks", "res_cd_reads",
         "res_cd_bytes", "audio_cd_uploads", "audio_cd_bytes", "decode_vblanks")   # variables del motor que se anotan en cada captura

LUA = """
local ffi = require('ffi')
local names = {%(names)s}
local outdir = '%(outdir)s'
local mem = PCSX.getMemPtr()
local shot_addr, quit_addr, state_addr, vm_addr = %(shot)d, %(quit)d, %(state)d, %(vm)d
local watch = {%(watch)s}
local failog = %(failog)s
local stalllog = %(stalllog)s
local synclog = %(synclog)s
local triggers = {%(triggers)s}
local function u32(addr) return ffi.cast('uint32_t*', mem + addr)[0] end
local seen, log_text, frames = 0, '', 0
local function take(name)
  local shot = PCSX.GPU.takeScreenShot()
  local f = Support.File.open(outdir .. '/' .. name .. '.raw', 'TRUNCATE')
  f:writeMoveSlice(shot.data)
  f:close()
  log_text = log_text .. name .. ' ' .. shot.width .. ' ' .. shot.height .. ' state=' .. tostring(u32(state_addr)) ..
    ' cap=' .. tostring(u32(vm_addr + 24)) .. ' pc=' .. tostring(u32(vm_addr + 28))
  for k, a in pairs(watch) do log_text = log_text .. ' ' .. k .. '=' .. tostring(u32(a)) end
  log_text = log_text .. ';'
  local log = Support.File.open(outdir .. '/shots.txt', 'TRUNCATE')
  log:write(log_text)
  log:close()
end
EMUTEST_LISTENER = PCSX.Events.createEventListener('GPU::Vsync', function()
  frames = frames + 1
  local n = ffi.cast('uint32_t*', mem + shot_addr)[0]
  while seen < n do
    seen = seen + 1
    take(names[seen] or ('shot' .. seen))
  end
  for _, t in ipairs(triggers) do
    if not t.at and ((t.state and u32(state_addr) == t.state) or
                     (t.cap and u32(vm_addr + 24) == t.cap and u32(vm_addr + 28) >= t.pc)) then
      t.at = frames + t.delay
    end
    if t.at and not t.done and frames >= t.at then
      t.done = true
      take(t.name)
    end
  end
  if ffi.cast('uint32_t*', mem + quit_addr)[0] ~= 0 or frames > %(max_frames)d then
    local fin = 'END frames=' .. frames .. ' state=' .. tostring(u32(state_addr)) .. ' cap=' .. tostring(u32(vm_addr + 24)) ..
      ' pc=' .. tostring(u32(vm_addr + 28))
    for k, a in pairs(watch) do fin = fin .. ' ' .. k .. '=' .. tostring(u32(a)) end
    if failog then fin = fin .. ' fallas='; for j = 0, 15 do fin = fin .. tostring(u32(failog + 4 * j)) .. ',' end end
    if stalllog then fin = fin .. ' congelones='; for j = 0, 31 do fin = fin .. tostring(u32(stalllog + 4 * j)) .. ',' end end
    if synclog then fin = fin .. ' al_momento='; for j = 0, 15 do fin = fin .. tostring(u32(synclog + 4 * j)) .. ',' end end
    local f = Support.File.open(outdir .. '/final.txt', 'TRUNCATE')
    f:write(fin)
    f:close()
    PCSX.quit(0)
  end
end)
"""


def parse_steps(text):
    """`hold BOTON N` mantiene el boton N cuadros (una pulsacion por cuadro)."""
    out = []
    for part in text.split(";"):
        words = part.split()
        if not words:
            continue
        frame = int(words[0])
        if words[1] == "hold":
            out += [(frame + k, "press", words[2]) for k in range(int(words[3]))]
        else:
            out.append((frame, words[1], words[2] if len(words) > 2 else ""))
    return sorted(out, key=lambda s: s[0])


def autotest_bin(steps):
    entries = []
    for frame, action, arg in steps:
        value = {"shot": SHOT, "quit": QUIT, "autoplay": AUTOPLAY}.get(action) or BUTTONS[arg.upper()]
        entries.append(struct.pack("<IH", frame, value))
    return struct.pack("<H", len(entries)) + b"".join(entries)


def symbols():
    env = dict(os.environ, PATH=str(NM.parent) + os.pathsep + os.environ["PATH"])
    out = subprocess.run([str(NM), str(ELF)], capture_output=True, text=True, check=True, env=env).stdout
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            table[parts[2]] = int(parts[0], 16) & 0x1FFFFF
    return table


def to_png(raw, width, height):
    """La captura viene en la resolucion de la PS1: 24 bits si el tamano coincide, si no 16 bits de 320 de ancho."""
    data = raw.read_bytes()
    raw.unlink()
    if not data:
        return None
    if len(data) == width * height * 3:
        arr = np.frombuffer(data, np.uint8).reshape(height, width, 3)
    else:
        if len(data) != width * height * 2:
            width = 320
        height = len(data) // (2 * width)
        w = np.frombuffer(data[:width * height * 2], "<u2").reshape(height, width).astype(np.uint32)
        arr = np.stack([(w & 31) << 3, ((w >> 5) & 31) << 3, ((w >> 10) & 31) << 3], axis=2).astype(np.uint8)
    png = raw.with_suffix(".png")
    Image.fromarray(arr).save(png)
    return png


def parse_triggers(text):
    """Capturas por estado del motor o por posicion en el guion: "state=NUM:NOMBRE[:CUADROS]" o
    "pc=CAP,PC:NOMBRE[:CUADROS]" (la captura se toma CUADROS despues de cumplirse la condicion)."""
    out = []
    for part in filter(None, (p.strip() for p in (text or "").split(";"))):
        cond, name, *rest = part.split(":")
        delay = int(rest[0]) if rest else 0
        kind, value = cond.split("=")
        if kind == "state":
            out.append(f"{{state = {int(value)}, name = '{name}', delay = {delay}}}")
        else:
            cap, pc = value.split(",")
            out.append(f"{{cap = {int(cap)}, pc = {int(pc)}, name = '{name}', delay = {delay}}}")
    return ", ".join(out)


def run(steps, out, keep_card=False, timeout=900, max_frames=None, triggers=None):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("*.png")) + list(out.glob("*.raw")) + [out / "shots.txt", out / "final.txt"]:
        old.unlink(missing_ok=True)
    if not keep_card:
        (out / "card1.mcd").unlink(missing_ok=True)
    (out / "AUTOTEST.BIN").write_bytes(autotest_bin(steps))
    subprocess.run([sys.executable, "-m", "tools.engine.build_game", "--autotest", str(out / "AUTOTEST.BIN")], cwd=ROOT,
                   check=True, capture_output=True)
    sym = symbols()
    names = ", ".join(f"'{arg}'" for _, action, arg in steps if action == "shot")
    last = max(f for f, _, _ in steps)
    script = out / "emutest.lua"
    script.write_text(LUA % {"names": names, "outdir": out.as_posix(), "shot": sym["autotest_shot"], "quit": sym["autotest_quit"],
                             "state": sym["state"], "vm": sym["vm"],
                             "watch": ", ".join(f"{n} = {sym[n]}" for n in WATCH if n in sym),
                             "failog": sym.get("res_fail_log", "nil"),
                             "stalllog": sym.get("stall_log", "nil"),
                             "synclog": sym.get("res_sync_log", "nil"),
                             "triggers": parse_triggers(triggers),
                             "max_frames": max_frames or last + 3000}, encoding="utf-8")
    args = [str(REDUX), "-no-ui", "-run", "-fastboot", "-bios", str(BIOS), "-iso", str(CUE),
            "-memcard1", str(out / "card1.mcd"), "-exec", f"dofile('{script.as_posix()}')"]
    try:
        subprocess.run(args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/IM", "pcsx-redux.exe", "/F"], capture_output=True)
    shots = []
    log = out / "shots.txt"
    for item in (log.read_text(encoding="utf-8").split(";") if log.exists() else []):
        parts = item.split()
        if len(parts) >= 3:
            png = to_png(out / f"{parts[0]}.raw", int(parts[1]), int(parts[2]))
            if png:
                shots.append(png)
            print(" ".join([parts[0]] + parts[3:]))
    return shots


def contact_sheet(shots, path, columns=4):
    if not shots:
        return None
    rows = (len(shots) + columns - 1) // columns
    sheet = Image.new("RGB", (322 * columns, 252 * rows), (40, 40, 40))
    for i, png in enumerate(shots):
        im = Image.open(png).convert("RGB").resize((320, 240))
        sheet.paste(im, ((i % columns) * 322, (i // columns) * 252))
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "emutest")
    ap.add_argument("--keep-card", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-frames", type=int, help="cierra el emulador despues de estos cuadros (por defecto el ultimo paso + 3000)")
    ap.add_argument("--triggers", help='capturas por estado o posicion: "state=18:teclado:30; pc=0,1850:insultos:40"')
    args = ap.parse_args()
    shots = run(parse_steps(args.steps), args.out, args.keep_card, args.timeout, args.max_frames, args.triggers)
    final = args.out.resolve() / "final.txt"
    if final.exists():
        print(final.read_text(encoding="utf-8"))
    for png in shots:
        print(png)
    sheet = contact_sheet(shots, args.out.resolve() / "sheet.png")
    if sheet:
        print("hoja:", sheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
