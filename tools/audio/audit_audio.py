"""Presupuesto de audio y disco: que pistas y efectos usa el juego y cuanto ocupan en PS1.

Genera build/audit/audio_usage.json y docs/presupuesto-audio.md.
"""
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "original" / "game"
OUT = ROOT / "build" / "audit"
DOC = ROOT / "docs" / "presupuesto-audio.md"

PLAY_RE = re.compile(r"""^(play|queue)\s+(\w+)\s+(.*)$""")
PATH_RE = re.compile(r"""['"](audio/[^'"]+)['"]""")
LOOP_CHANNELS = {"music", "music1", "music2", "ambient", "ambient1", "ambient2", "ambient3"}

SECTORS_PER_MIN = {"37.8k estereo": 1125, "18.9k estereo": 562.5, "18.9k mono": 281.25}
SECTORS_PER_CD = 333000          # CD de 74 minutos
SECTOR_BYTES = 2336
VAG_BYTES_PER_SEC = {22050: 12600, 16000: 9140, 11025: 6300}
SPU_RAM_BYTES = 512 * 1024 - 4096
SLOT_COUNT = 8
LOOP_SECONDS = 6


def duration(path, ffprobe):
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def real_names():
    """Los scripts usan mayusculas distintas a las del archivo; se normaliza al nombre real."""
    return {p.relative_to(GAME).as_posix().lower(): p.relative_to(GAME).as_posix()
            for p in (GAME / "audio").rglob("*") if p.is_file()}


def collect_usage():
    names = real_names()
    usage = defaultdict(lambda: {"channels": set(), "count": 0, "loop": False, "files": set()})
    for path in sorted((GAME / "script").glob("*.rpy")):
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            m = PLAY_RE.match(line)
            if not m:
                continue
            verb, channel, rest = m.groups()
            for audio in PATH_RE.findall(rest):
                audio = names.get(audio.lower(), audio)
                u = usage[audio]
                u["channels"].add(channel)
                u["count"] += 1
                u["files"].add(path.name)
                loops = channel in LOOP_CHANNELS
                if "noloop" in rest:
                    loops = False
                elif re.search(r"\bloop\b", rest):
                    loops = True
                u["loop"] = u["loop"] or loops
    return usage


def pack_lanes(lengths, lanes):
    """Carriles de igual duracion con pistas una tras otra (primero el mas largo). Devuelve sectores totales."""
    ordered = sorted(lengths, reverse=True)
    capacity = max(ordered[0], -(-sum(ordered) // lanes))
    while True:
        loads = [0] * lanes
        for length in ordered:
            lane = loads.index(min(loads))
            loads[lane] += length
        if max(loads) <= capacity:
            return capacity * lanes
        capacity += 1


def pack_groups(lengths, per_group=SLOT_COUNT):
    """Agrupa pistas de longitud parecida de 8 en 8; devuelve sectores totales y de relleno."""
    ordered = sorted(lengths, reverse=True)
    total_slots = padding_slots = 0
    for i in range(0, len(ordered), per_group):
        group = ordered[i:i + per_group]
        slots = max(group)
        total_slots += slots
        padding_slots += slots * per_group - sum(group)
    return total_slots * per_group, padding_slots


def main():
    ffprobe = shutil.which("ffprobe") or r"C:\Users\Pako\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe"
    usage = collect_usage()
    music, sounds = {}, {}
    for audio, u in usage.items():
        full = GAME / audio
        if not full.exists():
            continue
        entry = {"seconds": round(duration(full, ffprobe), 2), "count": u["count"], "loop": u["loop"],
                 "channels": sorted(u["channels"]), "chapters": len(u["files"])}
        (music if audio.startswith("audio/OST") else sounds)[audio] = entry

    all_music = sorted(p.relative_to(GAME).as_posix() for p in (GAME / "audio" / "OST").glob("*"))
    unused_music = [m for m in all_music if m not in music]
    music_min = sum(e["seconds"] for e in music.values()) / 60

    rows = {}
    # formato: (sectores por segundo de una pista, carriles entrelazados a 2x = 150 / sectores por segundo)
    formats = {"37.8k estereo": (18.75, 8), "37.8k mono": (9.375, 16),
               "18.9k estereo": (9.375, 16), "18.9k mono": (4.6875, 32)}
    for fmt, (per_sec, lanes) in formats.items():
        slots = [int(e["seconds"] * per_sec) + 1 for e in music.values()]
        total, padding = pack_groups(slots, lanes)
        packed = pack_lanes(slots, lanes)
        rows[fmt] = {"lanes": lanes, "sectors": total, "padding": padding, "packed": packed,
                     "mb": round(total * 2336 / 1048576, 1), "packed_mb": round(packed * 2336 / 1048576, 1),
                     "pct_cd": round(total * 100 / SECTORS_PER_CD, 1),
                     "packed_pct_cd": round(packed * 100 / SECTORS_PER_CD, 1)}

    oneshots = {k: v for k, v in sounds.items() if not v["loop"]}
    loops = {k: v for k, v in sounds.items() if v["loop"]}
    sfx_total_s = sum(v["seconds"] for v in oneshots.values())
    loop_total_s = sum(min(v["seconds"], LOOP_SECONDS) for v in loops.values())
    sfx_rows = {}
    for rate, bps in VAG_BYTES_PER_SEC.items():
        sfx_rows[rate] = {"oneshot_kb": round(sfx_total_s * bps / 1024), "loops_kb": round(loop_total_s * bps / 1024)}
    biggest = sorted(sounds.items(), key=lambda kv: kv[1]["seconds"], reverse=True)[:8]

    data = {"music_used": music, "music_unused": unused_music, "music_minutes_used": round(music_min, 1),
            "disc_music": rows, "sounds": sounds, "sfx_oneshot_seconds": round(sfx_total_s, 1),
            "sfx_loop_seconds_capped": round(loop_total_s, 1), "sfx_vag_kb": sfx_rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audio_usage.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Presupuesto de audio y disco", "", "Generado por `tools/audio/audit_audio.py`.", "",
             "## Musica", "",
             f"- Pistas en `audio/OST`: {len(all_music)}; usadas por la historia: {len(music)}; sin usar: {len(unused_music)}.",
             f"- Minutos de musica usada: {music_min:.1f}.",
             "- Sin usar (no se convierten): " + (", ".join(Path(m).stem for m in unused_music) or "ninguna"), "",
             "| Formato XA | Carriles | Sectores (agrupado simple) | Relleno | Sectores (carriles empaquetados) | MB empaquetado | % de un CD de 74 min |",
             "|---|---|---|---|---|---|---|"]
    for fmt, r in rows.items():
        lines.append(f"| {fmt} | {r['lanes']} | {r['sectors']} | {r['padding']} | {r['packed']} | {r['packed_mb']} | {r['packed_pct_cd']}% |")
    lines += ["", "## Efectos", "",
              f"- Archivos de efectos usados: {len(sounds)} ({len(oneshots)} de un solo disparo, {len(loops)} en bucle).",
              f"- Segundos de un solo disparo: {sfx_total_s:.1f}; segundos de bucles recortados a {LOOP_SECONDS} s: {loop_total_s:.1f}.", "",
              f"RAM de sonido disponible: {SPU_RAM_BYTES // 1024} KB.", "",
              "| Frecuencia VAG | Un solo disparo (KB) | Bucles recortados (KB) |", "|---|---|---|"]
    for rate, r in sfx_rows.items():
        lines.append(f"| {rate} Hz mono | {r['oneshot_kb']} | {r['loops_kb']} |")
    lines += ["", "Efectos mas largos:", ""] + [f"- `{k}`: {v['seconds']} s, {'bucle' if v['loop'] else 'un disparo'}, "
                                               f"canales {', '.join(v['channels'])}, usado {v['count']} veces en {v['chapters']} capitulos" for k, v in biggest]
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
