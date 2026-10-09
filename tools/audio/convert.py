"""Pipeline de audio (Fase 5): musica a XA mono en 16 carriles entrelazados, efectos y ambientes a SPU-ADPCM (VAG).

Decisiones (docs/decisiones.md D2, D8, D12):
- Musica: XA 37.8 kHz mono; cada pista que se repite se graba en copias seguidas (objetivo 90 s, maximo 3) y se empaqueta
  en carriles de igual duracion. Los finales (`... end`) de una familia intro/loop/end se guardan en un carril lateral
  alineado con el final de cada copia del bucle, para poder cambiar a ellos sin buscar en el CD.
- Efectos: VAG 22.05 kHz mono. Ambientes: bucle de ~6 s a 16 kHz con empalme suave.

Uso: python -m tools.audio.convert [--only music|sfx]
"""
import argparse
import json
import math
import re
import shutil
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "original" / "game"
DATA = ROOT / "build" / "data"
TMP = ROOT / "build" / "tmp" / "audio"
SDK_BIN = Path(r"C:\msys64\usr\local\psn00bsdk\bin")

XA_RATE = 37800
SAMPLES_PER_SECTOR = 4032             # 37.8 kHz mono, 4 bits: 18 grupos x 224 muestras
LANES = 16
SECTOR_SIZE = 2336
LOOP_TARGET_SECONDS = 90
LOOP_MAX_COPIES = 3
MUSIC_TARGET_DB = -12.0               # nivel RMS objetivo de la musica
GAIN_MIN_DB, GAIN_MAX_DB = -12.0, 3.0  # limites del ajuste por pista
SFX_RATE = 22050
AMBIENT_RATE = 16000
AMBIENT_LOOP_SECONDS = 6.0
AMBIENT_CROSSFADE = 0.5
KIND_NONE, KIND_MUSIC, KIND_MUSIC_END, KIND_SFX, KIND_AMBIENT = 0, 1, 2, 3, 4
FAMILY_RE = re.compile(r"^(.*?)[\s_-]+(intro|loop|end)$", re.IGNORECASE)


def tool(name):
    return shutil.which(name) or str(Path.home() / "AppData/Local/Microsoft/WinGet/Links" / f"{name}.exe")


def run(args):
    subprocess.run([str(a) for a in args], check=True, capture_output=True)


def decode(path, rate):
    """Audio mono float32 a `rate` Hz."""
    out = subprocess.run([tool("ffmpeg"), "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(rate), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).copy()


def write_wav(path, samples, rate):
    import wave
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(pcm.tobytes())


def rms_db(x):
    active = x[np.abs(x) > 0.001]
    if len(active) < 100:
        return -60.0
    return 20 * math.log10(max(1e-6, float(np.sqrt(np.mean(active ** 2)))))


def music_gain(x, fixed=None):
    """Ganancia para llevar la musica a un nivel parecido entre pistas, sin pasar de -0.3 dB de pico."""
    if fixed is not None:
        return fixed
    gain = 10 ** ((MUSIC_TARGET_DB - rms_db(x)) / 20)
    gain = min(max(gain, 10 ** (GAIN_MIN_DB / 20)), 10 ** (GAIN_MAX_DB / 20))
    peak = float(np.max(np.abs(x))) or 1.0
    return min(gain, 0.97 / peak)


# ------------------------------------------------------------------ analisis del programa
def scan_program(program):
    """Usos de cada audio en el bytecode: canales y cadenas de musica en cola."""
    usage = defaultdict(lambda: {"music": 0, "ambient": 0, "sfx": 0})
    for idx, ch in program.chapters.items():
        for pc, name, a in ch.walk():
            if name in ("MUSIC_PLAY", "MUSIC_QUEUE"):
                usage[a["track"]]["music"] += 1
            elif name == "AMBIENT_PLAY":
                usage[a["sound"]]["ambient"] += 1
            elif name == "SFX_PLAY":
                usage[a["sound"]]["sfx"] += 1
    return usage


def families(paths):
    """Agrupa pistas `X intro`, `X loop`, `X end` por nombre base. Devuelve {base: {rol: ruta}}."""
    fam = defaultdict(dict)
    for p in paths:
        m = FAMILY_RE.match(Path(p).stem)
        if m:
            fam[m.group(1).lower()][m.group(2).lower()] = p
    return {b: roles for b, roles in fam.items() if len(roles) > 1 or "end" in roles}


# ------------------------------------------------------------------ musica
def encode_samples(x, ident, sectors=None):
    """Codifica a XA estirando levemente la pista para llenar sectores exactos (el bucle queda sin silencio)."""
    sectors = sectors or max(1, math.ceil(len(x) / SAMPLES_PER_SECTOR))
    target = sectors * SAMPLES_PER_SECTOR
    wav_rate = max(8000, round(XA_RATE * len(x) / target))
    wav, xa = TMP / f"m{ident}.wav", TMP / f"m{ident}.xa"
    write_wav(wav, x, wav_rate)
    run([SDK_BIN / "psxavenc.exe", "-t", "xa", "-f", XA_RATE, "-c", 1, "-b", 4, "-F", 1, "-C", 0, "-q", wav, xa])
    data = xa.read_bytes()
    n = len(data) // SECTOR_SIZE
    return [data[i * SECTOR_SIZE:(i + 1) * SECTOR_SIZE] for i in range(n)], round((target / len(x) - 1) * 100, 3)


def encode_track(path, ident):
    x = decode(GAME / path, XA_RATE)
    gain = music_gain(x)
    sectors, stretch = encode_samples(x * gain, ident)
    return {"sectors": sectors, "gain_db": round(20 * math.log10(gain), 1), "stretch_pct": stretch,
            "seconds": len(x) / XA_RATE}


def encode_stem_mixes(mix_entries, first_ident):
    """Mezclas de stems (capas de una cancion): un solo nivel de grupo y la misma duracion en sectores para todas."""
    stems = sorted({p for e in mix_entries for p in e["mix"]})
    audio = {p: decode(GAME / p, XA_RATE) for p in stems}
    sectors = max(math.ceil(len(x) / SAMPLES_PER_SECTOR) for x in audio.values())
    length = sectors * SAMPLES_PER_SECTOR
    resized = {}
    for p, x in audio.items():     # todas a la misma longitud exacta
        pos = np.linspace(0, len(x) - 1, length)
        resized[p] = np.interp(pos, np.arange(len(x)), x).astype(np.float32)
    total = sum(resized.values())
    gain = music_gain(total)
    tracks = {}
    for k, e in enumerate(mix_entries):
        mixed = sum(resized[p] for p in e["mix"]) * gain
        peak = float(np.max(np.abs(mixed))) or 1.0
        if peak > 0.97:
            mixed = mixed * (0.97 / peak)
        secs, _ = encode_samples(mixed.astype(np.float32), first_ident + k, sectors)
        tracks[e["path"]] = {"sectors": secs, "gain_db": round(20 * math.log10(gain), 1), "stretch_pct": 0.0,
                             "seconds": length / XA_RATE, "sync": True}
    return tracks


def patch_sector(sector, lane, last=False):
    """Pone archivo 1, el carril como canal y quita las banderas de fin (el motor cuenta los sectores)."""
    b = bytearray(sector)
    b[0] = b[4] = 1
    b[1] = b[5] = lane
    for off in (2, 6):
        b[off] &= ~0x81 & 0xFF
    return bytes(b)


def padding_sector(lane):
    b = bytearray(SECTOR_SIZE)
    b[0] = b[4] = 1
    b[1] = b[5] = lane
    b[2] = b[6] = 0x64          # audio, form 2, tiempo real
    b[3] = b[7] = 0x01          # codificacion: 37.8 kHz mono 4 bits (nivel A)
    return bytes(b)


def copies_for(slots):
    return max(1, min(LOOP_MAX_COPIES, math.ceil(LOOP_TARGET_SECONDS / (slots / 9.375))))


def plan_music(tracks, fam):
    """Unidades de empaquetado: pistas sueltas con copias, familias con carril lateral para los finales y grupos sincronizados."""
    units, used = [], set()
    for base, roles in fam.items():
        members = dict(roles)
        loop_path = members.get("loop") or members.get("intro")
        loop_len = tracks[loop_path]["slots"]
        units.append({"type": "family", "name": base, "members": members, "copies": copies_for(loop_len),
                      "intro": tracks[members["intro"]]["slots"] if "intro" in members else 0,
                      "loop": loop_len, "end": tracks[members["end"]]["slots"] if "end" in members else 0})
        used.update(members.values())
    for path, t in tracks.items():
        if path in used:
            continue
        units.append({"type": "single", "name": Path(path).stem, "path": path, "copies": copies_for(t["slots"]),
                      "loop": t["slots"], "intro": 0, "end": 0, "sync": bool(t.get("sync"))})
    return units


def unit_length(u):
    return u["intro"] + u["copies"] * u["loop"]


def pack_lanes(units):
    """Reparte las unidades en 16 carriles. Los stems sincronizados empiezan en la misma ranura (cambio de carril sin saltos
    de tiempo); las familias usan un carril principal y uno lateral alineados."""
    lanes = [0] * LANES
    placed = []
    group = [u for u in units if u["type"] == "single" and u.get("sync")]
    if group:
        order = sorted(range(LANES), key=lambda i: lanes[i])[:len(group)]
        start = max(lanes[i] for i in order)
        for u, lane in zip(group, order):
            u.update(lane=lane, side_lane=None, start=start)
            lanes[lane] = start + unit_length(u)
            placed.append(u)
    families_ = sorted((u for u in units if u["type"] == "family" and u["end"]), key=unit_length, reverse=True)
    singles = sorted([u for u in units if u not in families_ and u not in group], key=unit_length, reverse=True)
    for u in families_:
        order = sorted(range(LANES), key=lambda i: lanes[i])
        a, b = order[0], order[1]
        start = max(lanes[a], lanes[b])
        u.update(lane=a, side_lane=b, start=start)
        lanes[a] = lanes[b] = start + unit_length(u)
        placed.append(u)
    for u in singles:
        lane = min(range(LANES), key=lambda i: lanes[i])
        u.update(lane=lane, side_lane=None, start=lanes[lane])
        lanes[lane] += unit_length(u)
        placed.append(u)
    return placed, lanes


def build_music(program, usage, meta_audio):
    paths = sorted({a["path"] for i, a in enumerate(meta_audio)
                    if usage[i]["music"] and a["path"].startswith("audio/OST") and not a.get("mix")})
    mix_entries = [a for i, a in enumerate(meta_audio) if usage[i]["music"] and a.get("mix")]
    TMP.mkdir(parents=True, exist_ok=True)
    tracks = {}
    for n, path in enumerate(paths):
        t = encode_track(path, n)
        t["slots"] = len(t["sectors"])
        tracks[path] = t
        print(f"  pista {n + 1}/{len(paths)} {Path(path).name}: {t['slots']} sectores, ganancia {t['gain_db']} dB")
    if mix_entries:
        for path, t in encode_stem_mixes(mix_entries, 1000).items():
            t["slots"] = len(t["sectors"])
            tracks[path] = t
        print(f"  {len(mix_entries)} mezclas de stems")
    fam = families(paths)
    units = plan_music(tracks, fam)
    units, lanes = pack_lanes(units)
    capacity = max(lanes)
    lane_sectors = [[] for _ in range(LANES)]

    def put(lane, slot, sectors):
        lst = lane_sectors[lane]
        while len(lst) < slot:
            lst.append(None)
        for s in sectors:
            lst.append(patch_sector(s, lane))

    index = {}
    for u in units:
        lane, start = u["lane"], u["start"]
        if u["type"] == "single":
            t = tracks[u["path"]]
            put(lane, start, [s for _ in range(u["copies"]) for s in t["sectors"]])
            index[u["path"]] = {"kind": KIND_MUSIC, "lane": lane, "copies": u["copies"], "start": start * LANES + lane,
                                "slots": t["slots"], "aux": 0, "loop": True, "sync": bool(u.get("sync"))}
            continue
        m = u["members"]
        pos = start
        if "intro" in m:
            put(lane, pos, tracks[m["intro"]]["sectors"])
            index[m["intro"]] = {"kind": KIND_MUSIC, "lane": lane, "copies": 1, "start": pos * LANES + lane,
                                 "slots": u["intro"], "aux": 0, "loop": False, "sync": False}
            pos += u["intro"]
        if "loop" in m:
            put(lane, pos, [s for _ in range(u["copies"]) for s in tracks[m["loop"]]["sectors"]])
            index[m["loop"]] = {"kind": KIND_MUSIC, "lane": lane, "copies": u["copies"], "start": pos * LANES + lane,
                                "slots": u["loop"], "aux": 0, "loop": True, "sync": False}
        if "end" in m:
            # el final empieza al terminar cada copia del bucle, en el carril lateral (cambio de filtro, sin buscar en el CD)
            first = pos + u["loop"]
            for k in range(u["copies"]):
                put(u["side_lane"], first + k * u["loop"], tracks[m["end"]]["sectors"])
            index[m["end"]] = {"kind": KIND_MUSIC_END, "lane": u["side_lane"], "copies": u["copies"],
                               "start": first * LANES + u["side_lane"], "slots": u["end"], "aux": u["loop"], "loop": False,
                               "sync": False}
    slots = max(len(l) for l in lane_sectors)
    pads = [padding_sector(i) for i in range(LANES)]
    out = bytearray()
    for slot in range(slots):
        for lane in range(LANES):
            lst = lane_sectors[lane]
            s = lst[slot] if slot < len(lst) else None
            out += s if s is not None else pads[lane]
    (DATA / "MUSIC.XA").write_bytes(bytes(out))
    return {"index": index, "slots": slots, "sectors": slots * LANES, "units": len(units), "mixes": len(mix_entries),
            "capacity": capacity, "tracks": {p: {k: v for k, v in t.items() if k != "sectors"} for p, t in tracks.items()}}


# ------------------------------------------------------------------ efectos y ambientes
def loop_segment(x, rate):
    """Bucle de ~6 s sin saltos: se toma un tramo largo y su cola se funde con el inicio."""
    n = int(AMBIENT_LOOP_SECONDS * rate) // 28 * 28
    fade = int(AMBIENT_CROSSFADE * rate)
    if len(x) < n + fade:
        n = (len(x) - fade) // 28 * 28 if len(x) > fade + 560 else len(x) // 28 * 28
        fade = min(fade, len(x) - n)
    start = max(0, (len(x) - n - fade) // 2)
    seg = x[start:start + n + fade].copy()
    ramp = np.linspace(0, math.pi / 2, fade)
    head = seg[:fade] * np.sin(ramp) + seg[n:n + fade] * np.cos(ramp)
    out = seg[:n].copy()
    out[:fade] = head
    return out


def encode_spu(samples, rate, ident, looping):
    wav, spu = TMP / f"s{ident}.wav", TMP / f"s{ident}.spu"
    write_wav(wav, samples, rate)
    args = [SDK_BIN / "psxavenc.exe", "-t", "spu", "-f", rate, "-q"]
    args += ["-l", 0] if looping else []
    run(args + [wav, spu])
    return spu.read_bytes()


def build_sfx(usage, meta_audio):
    out_dir = DATA / "SFX"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    seen = {}
    for i, a in enumerate(meta_audio):
        path = a["path"]
        u = usage[i]
        if u["music"] and path.startswith("audio/OST"):
            continue
        if not (u["ambient"] or u["sfx"]):
            continue
        looping = bool(u["ambient"])
        key = (path, looping)
        if key in seen:
            result[i] = seen[key]
            continue
        rate = AMBIENT_RATE if looping else SFX_RATE
        x = decode(GAME / path, rate)
        if looping:
            x = loop_segment(x, rate)
        data = encode_spu(x, rate, i, looping)
        fname = f"S{i:03d}.SPU"
        (out_dir / fname).write_bytes(data)
        info = {"kind": KIND_AMBIENT if looping else KIND_SFX, "file": fname, "bytes": len(data), "rate": rate,
                "seconds": round(len(x) / rate, 2), "loop": looping, "path": path}
        result[i] = seen[key] = info
        if u["ambient"] and u["sfx"]:
            info["also_oneshot"] = True
    return result


# ------------------------------------------------------------------ indice y reporte
def write_index(meta_audio, music, sfx):
    rows = bytearray(b"AIX1" + struct.pack("<H", len(meta_audio)))
    for i, a in enumerate(meta_audio):
        path = a["path"]
        if path in music["index"]:
            e = music["index"][path]
            rows += struct.pack("<BBBBIIII", e["kind"], e["lane"], e["copies"], (1 if e["loop"] else 0) | (2 if e.get("sync") else 0),
                                e["start"], e["slots"], e["aux"], 0)
        elif i in sfx:
            e = sfx[i]
            rows += struct.pack("<BBBBIIII", e["kind"], 0, 0, 1 if e["loop"] else 0, 0, e["bytes"], e["rate"], 0)
        else:
            rows += struct.pack("<BBBBIIII", KIND_NONE, 0, 0, 0, 0, 0, 0, 0)
    (DATA / "audio_index.bin").write_bytes(bytes(rows))


def write_report(program, music, sfx, usage):
    chapters = defaultdict(set)
    for idx, ch in program.chapters.items():
        for pc, name, a in ch.walk():
            if name in ("AMBIENT_PLAY", "SFX_PLAY"):
                chapters[ch.name].add(a["sound" if name != "MUSIC_PLAY" else "track"])
    spu_total = sum(e["bytes"] for e in {e["file"]: e for e in sfx.values()}.values())
    per_chapter = sorted(((sum(sfx[i]["bytes"] for i in ids if i in sfx), name) for name, ids in chapters.items()), reverse=True)
    lines = ["# Reporte del pipeline de audio", "", "Generado por `python -m tools.audio.convert`.", "",
             "| Dato | Valor |", "|---|---|",
             f"| Pistas de musica (unicas) | {len(music['tracks'])} |",
             f"| Unidades de empaquetado | {music['units']} (mezclas de stems: {music['mixes']}) |",
             f"| MUSIC.XA | {music['sectors']} sectores ({music['sectors'] * SECTOR_SIZE / 1048576:.1f} MB, "
             f"{music['sectors'] * 100 / 333000:.1f}% de un CD de 74 min) |",
             f"| Longitud de los carriles | {music['slots']} ranuras ({music['slots'] / 9.375 / 60:.1f} min) |",
             f"| Efectos y ambientes (archivos unicos) | {len({e['file'] for e in sfx.values()})} |",
             f"| Datos SPU totales | {spu_total / 1024:.0f} KB |",
             f"| Mayor juego de sonidos por capitulo | {per_chapter[0][0] / 1024:.0f} KB (RAM de sonido: 508 KB) |", "",
             "## Juegos de sonidos por capitulo (KB)", "", "| Capitulo | KB |", "|---|---|"]
    lines += [f"| {n} | {b // 1024} |" for b, n in per_chapter[:12]]
    lines += ["", "## Ajuste de nivel de la musica", ""]
    gains = sorted(music["tracks"].items(), key=lambda kv: kv[1]["gain_db"])
    lines += [f"- {Path(p).stem}: {t['gain_db']:+} dB, estirada {t['stretch_pct']}%" for p, t in gains[:3] + gains[-3:]]
    (ROOT / "build" / "reports" / "audio.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (DATA / "audio_out.json").write_text(json.dumps({"music": music, "sfx": {str(k): v for k, v in sfx.items()}},
                                                     indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["music", "sfx"])
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    from tools.simulator.vnb import Program
    program = Program(DATA)
    meta_audio = program.meta["audio"]
    usage = scan_program(program)
    TMP.mkdir(parents=True, exist_ok=True)
    music = None
    if args.only != "sfx":
        print("musica...")
        music = build_music(program, usage, meta_audio)
    sfx = None
    if args.only != "music":
        print("efectos...")
        sfx = build_sfx(usage, meta_audio)
    if music and sfx:
        write_index(meta_audio, music, sfx)
        write_report(program, music, sfx, usage)
        print("listo:", DATA / "audio_index.bin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
