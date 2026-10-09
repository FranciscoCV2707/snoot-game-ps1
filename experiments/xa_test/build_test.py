"""Construye el disco de prueba XA: experiments/xa_test -> build/xa_test/xa_test.bin/.cue."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.audio.xa_interleave import interleave  # noqa: E402

SDK_BIN = Path(r"C:\msys64\usr\local\psn00bsdk\bin")
OST = ROOT / "original" / "game" / "audio" / "OST"
WORK = ROOT / "build" / "xa_test"
SRC = Path(__file__).resolve().parent
TRACKS = 16  # 37.8 kHz mono: 16 carriles a 2x
SECONDS = 60

XML = """<?xml version="1.0" encoding="utf-8"?>
<iso_project>
	<track type="data">
		<identifiers system="PLAYSTATION" volume="XATEST" volume_set="XATEST"
			publisher="SNOOTPS1" data_preparer="XATEST" application="PLAYSTATION" copyright="COPY.TXT;1" />
		<directory_tree>
			<file name="SYSTEM.CNF" type="data" source="system.cnf" />
			<file name="XATEST.EXE" type="data" source="xa_test.exe" />
			<file name="MUSIC.XA" type="mixed" source="music.xa" />
			<file name="BG0.BIN" type="data" source="BG0.BIN" />
			<file name="BG1.BIN" type="data" source="BG1.BIN" />
			<file name="BG2.BIN" type="data" source="BG2.BIN" />
			<file name="BG3.BIN" type="data" source="BG3.BIN" />
			<file name="CHAP.BIN" type="data" source="CHAP.BIN" />
			<dummy sectors="512" />
		</directory_tree>
	</track>
</iso_project>
"""


def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def make_music():
    tracks = sorted(OST.glob("*.ogg"))[:TRACKS]
    encoded = []
    for channel, track in enumerate(tracks):
        wav = WORK / f"t{channel}.wav"
        xa = WORK / f"t{channel}.xa"
        run(["ffmpeg", "-y", "-loglevel", "error", "-t", SECONDS, "-i", track, "-ar", 37800, "-ac", 1, wav])
        run([SDK_BIN / "psxavenc.exe", "-t", "xa", "-f", 37800, "-c", 1, "-b", 4, "-F", 1, "-C", channel, "-q", wav, xa])
        encoded.append(xa)
        print("canal", channel, track.name)
    data, slots = interleave(encoded, TRACKS)
    (WORK / "music.xa").write_bytes(data)
    print(f"music.xa: {slots} ranuras, {len(data) // 2336} sectores")


def make_data():
    for name, size in (("BG0.BIN", 57600 + 512), ("BG1.BIN", 57600 + 512), ("BG2.BIN", 57600 + 512),
                       ("BG3.BIN", 57600 + 512), ("CHAP.BIN", 128 * 1024)):
        (WORK / name).write_bytes(os.urandom(size))


def build_exe():
    build = SRC / "build"
    env = dict(os.environ, PATH=str(SDK_BIN) + os.pathsep + os.environ["PATH"])
    run(["cmake", "--preset", "default", "."], cwd=SRC, env=env)
    run(["cmake", "--build", "build"], cwd=SRC, env=env)
    shutil.copy(build / "xa_test.exe", WORK / "xa_test.exe")


def use_real_music():
    """Usa MUSIC.XA del pipeline real (build/data) y escribe que pista empieza en cada carril."""
    import json
    shutil.copy(ROOT / "build" / "data" / "MUSIC.XA", WORK / "music.xa")
    out = json.loads((ROOT / "build" / "data" / "audio_out.json").read_text(encoding="utf-8"))
    firsts = {}
    for path, e in out["music"]["index"].items():
        if e["start"] // 16 == 0 or (e["lane"] not in firsts or e["start"] < firsts[e["lane"]][0]):
            firsts[e["lane"]] = (e["start"], path)
    lines = [f"Canal {lane:2d}: {Path(path).stem}" for lane, (start, path) in sorted(firsts.items())]
    (WORK / "CANALES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "system.cnf").write_text("BOOT=cdrom:\\XATEST.EXE;1\nTCB=4\nEVENT=10\nSTACK=801FFFF0\n", encoding="utf-8")
    (WORK / "iso.xml").write_text(XML, encoding="utf-8")
    if "--real" in sys.argv:
        use_real_music()
    else:
        make_music()
    make_data()
    build_exe()
    run([SDK_BIN / "mkpsxiso.exe", "-y", "-o", "xa_test.bin", "-c", "xa_test.cue", "iso.xml"], cwd=WORK)
    print("Disco listo:", WORK / "xa_test.cue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
