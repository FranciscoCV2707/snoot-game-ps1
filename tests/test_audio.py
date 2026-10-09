import json
import struct
from pathlib import Path

import numpy as np
import pytest

from tools.audio import convert as ac

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "build" / "data"
HAS_DATA = (DATA / "MUSIC.XA").exists() and (DATA / "audio_index.bin").exists()


def test_loop_segment_is_seamless():
    rate = 16000
    t = np.arange(rate * 20) / rate
    x = (np.sin(2 * np.pi * 220 * t) * 0.5).astype(np.float32)
    seg = ac.loop_segment(x, rate)
    assert len(seg) % 28 == 0
    jump = abs(float(seg[0]) - float(seg[-1]))
    step = float(np.max(np.abs(np.diff(seg))))
    assert jump <= step * 2          # el salto del final al inicio no supera un paso normal de la onda


def test_music_gain_limits():
    quiet = np.full(4000, 0.001, np.float32) * np.sin(np.arange(4000) * 0.1)
    assert 20 * np.log10(ac.music_gain(quiet)) <= ac.GAIN_MAX_DB + 1e-6
    loud = np.sin(np.arange(40000) * 0.05).astype(np.float32)
    assert ac.music_gain(loud) * 1.0 <= 0.97 + 1e-6


def test_patch_sector_clears_end_flags_and_sets_lane():
    sector = bytearray(ac.SECTOR_SIZE)
    sector[2] = sector[6] = 0xE5     # fin de archivo + fin de registro + audio + form 2
    out = ac.patch_sector(bytes(sector), 5)
    assert out[0] == 1 and out[1] == 5 and out[4] == 1 and out[5] == 5
    assert out[2] & 0x81 == 0 and out[6] & 0x81 == 0 and out[2] & 0x04


def test_packing_aligns_sync_groups_and_families():
    units = [{"type": "single", "name": f"s{i}", "path": f"s{i}", "copies": 2, "loop": 100, "intro": 0, "end": 0, "sync": True}
             for i in range(3)]
    units += [{"type": "family", "name": "f", "members": {}, "copies": 3, "intro": 20, "loop": 50, "end": 10}]
    units += [{"type": "single", "name": f"x{i}", "path": f"x{i}", "copies": 1, "loop": 40 + i, "intro": 0, "end": 0} for i in range(20)]
    placed, lanes = ac.pack_lanes(units)
    sync = [u for u in placed if u.get("sync")]
    assert len({u["start"] for u in sync}) == 1 and len({u["lane"] for u in sync}) == 3
    fam = next(u for u in placed if u["type"] == "family")
    assert fam["lane"] != fam["side_lane"]
    assert max(lanes) < sum(ac.unit_length(u) for u in placed)       # se reparte entre carriles


@pytest.mark.skipif(not HAS_DATA, reason="falta build/data (ejecutar el pipeline de audio)")
def test_music_xa_layout_and_index():
    data = (DATA / "MUSIC.XA").read_bytes()
    assert len(data) % (ac.SECTOR_SIZE * ac.LANES) == 0
    sectors = len(data) // ac.SECTOR_SIZE
    for i in range(0, sectors, 997):
        lane = i % ac.LANES
        assert data[i * ac.SECTOR_SIZE + 1] == lane and data[i * ac.SECTOR_SIZE] == 1
        assert data[i * ac.SECTOR_SIZE + 2] & 0x81 == 0
    idx = (DATA / "audio_index.bin").read_bytes()
    assert idx[:4] == b"AIX1"
    count = struct.unpack_from("<H", idx, 4)[0]
    for i in range(count):
        kind, lane, copies, flags, start, slots, aux, _ = struct.unpack_from("<BBBBIIII", idx, 6 + 20 * i)
        if kind in (ac.KIND_MUSIC, ac.KIND_MUSIC_END):
            assert start % ac.LANES == lane and (start + slots * ac.LANES) // ac.LANES <= sectors // ac.LANES + 1
            assert data[start * ac.SECTOR_SIZE + 1] == lane


@pytest.mark.skipif(not HAS_DATA, reason="falta build/data (ejecutar el pipeline de audio)")
def test_spu_loop_flags():
    out = json.loads((DATA / "audio_out.json").read_text(encoding="utf-8"))
    checked = 0
    for info in out["sfx"].values():
        raw = (DATA / "SFX" / info["file"]).read_bytes()
        assert len(raw) % 16 == 0
        flags = [(i, raw[i * 16 + 1]) for i in range(len(raw) // 16) if raw[i * 16 + 1]]
        if info["loop"]:
            assert flags[0][1] & 4 and flags[-1][1] & 3 == 3     # inicio de bucle y fin con repeticion
        else:
            assert flags[-1][1] & 3 == 1                         # fin sin repeticion: el sonido se detiene
        checked += 1
    assert checked > 50
