"""Cuanto dura cada tramo de musica en la historia y cuantas veces se repite el bucle.

Estima el tiempo de cada tramo (entre un `play music` y el siguiente cambio) a partir del texto
y las pausas, en un lector rapido y en uno lento. Sirve para decidir cuantas copias seguidas de una
pista hay que grabar en el CD para que el salto de bucle casi nunca ocurra.

Uso: python tools/audio/segment_stats.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.audit.inventario import strip_comment  # noqa: E402

GAME = ROOT / "original" / "game"
USAGE = ROOT / "build" / "audit" / "audio_usage.json"
OUT = ROOT / "build" / "audit" / "segment_stats.json"
SECTORS_PER_SECOND = 9.375  # 37.8 kHz mono
SCENARIOS = {"rapido": (22.0, 0.5), "lento": (11.0, 1.5)}  # (caracteres por segundo, segundos extra por linea)
MAX_UNROLL = 4

PLAY_RE = re.compile(r"^(play|queue)\s+(music\d?)\s+(.*)$")
STOP_RE = re.compile(r"^stop\s+(music\d?)\b")
PATH_RE = re.compile(r"""['"](audio/[^'"]+)['"]""")
PAUSE_RE = re.compile(r"^pause\s+([\d.]+)")
STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
TAG_RE = re.compile(r"\{[^}]*\}|\[[^\]]*\]")


def chapter_key(path):
    m = re.match(r"(x?)(\d+)(?:\.5)?([A-Z]?)", path.name)
    return (m.group(1) == "x", int(m.group(2)), path.name) if m else (True, 99, path.name)


def main():
    usage = json.loads(USAGE.read_text(encoding="utf-8"))["music_used"]
    lengths = {k.lower(): v["seconds"] for k, v in usage.items()}
    segments = []
    current = None
    for path in sorted((GAME / "script").glob("*.rpy"), key=chapter_key):
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = strip_comment(raw.replace("\t", "    ")).strip()
            if not line:
                continue
            m = PLAY_RE.match(line)
            if m and m.group(2) == "music" and m.group(1) == "play":
                track = PATH_RE.search(m.group(3))
                if current:
                    segments.append(current)
                current = {"track": track.group(1) if track else None, "file": path.name, "chars": 0, "lines": 0, "pause": 0.0}
                continue
            if STOP_RE.match(line) and STOP_RE.match(line).group(1) == "music":
                if current:
                    segments.append(current)
                current = None
                continue
            if current is None:
                continue
            pm = PAUSE_RE.match(line)
            if pm:
                current["pause"] += float(pm.group(1))
                continue
            sm = STRING_RE.search(line)
            if sm and not re.match(r"^(define|default|image|scene|show|play|queue|stop|call|jump|label|\$|if|elif|window|with|menu)", line):
                current["chars"] += len(TAG_RE.sub("", sm.group(1)))
                current["lines"] += 1
    if current:
        segments.append(current)

    rows = []
    for seg in segments:
        length = lengths.get((seg["track"] or "").lower(), 0)
        if not length:
            continue
        est = {name: seg["chars"] / cps + seg["lines"] * extra + seg["pause"] for name, (cps, extra) in SCENARIOS.items()}
        loops_slow = est["lento"] / length
        unroll = min(MAX_UNROLL, max(1, int(loops_slow) + 1))
        rows.append({**seg, "track_seconds": length, "est_rapido": round(est["rapido"]), "est_lento": round(est["lento"]),
                     "loops_lento": round(loops_slow, 2), "unroll": unroll})

    total = len(rows)
    never_loop = sum(1 for r in rows if r["loops_lento"] <= 1)
    tracks = {}
    for r in rows:
        key = r["track"].lower()
        tracks[key] = max(tracks.get(key, 1), r["unroll"])
    extra_sectors = sum(int((u - 1) * lengths[k] * SECTORS_PER_SECOND) for k, u in tracks.items())
    base_sectors = sum(int(lengths[k] * SECTORS_PER_SECOND) for k in tracks)
    summary = {"segments": total, "no_loop_needed_slow": never_loop,
               "loop_once_or_more": total - never_loop,
               "unroll_distribution": {str(u): sum(1 for v in tracks.values() if v == u) for u in range(1, MAX_UNROLL + 1)},
               "base_music_sectors_mono": base_sectors, "extra_sectors_for_unrolling": extra_sectors}
    OUT.write_text(json.dumps({"summary": summary, "segments": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print("Tramos mas largos (estimacion lenta):")
    for r in sorted(rows, key=lambda r: r["est_lento"], reverse=True)[:8]:
        print(f"  {r['est_lento']:>5}s (rapido {r['est_rapido']}s) pista {r['track_seconds']:.0f}s x{r['loops_lento']} {r['track']} [{r['file'][:20]}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
