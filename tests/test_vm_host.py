"""Compara la VM del motor (C, compilada en la PC) con el simulador de Python en varias rutas de decisiones."""
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.simulator.vm import VM, Coverage
from tools.simulator.vnb import Program

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "build" / "data"
EXE = ROOT / "build" / "host" / "vm_host.exe"
GCC_CANDIDATES = [r"C:\msys64\ucrt64\bin\gcc.exe", r"C:\msys64\usr\bin\gcc.exe"]


MAX_MENUS = 200


def build_host():
    gcc = next((g for g in GCC_CANDIDATES if Path(g).exists()), None) or shutil.which("gcc")
    if not gcc:
        pytest.skip("no hay gcc nativo")
    EXE.parent.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "tests" / "host" / "vm_host.c", ROOT / "engine" / "src" / "vm.c"]
    headers = list((ROOT / "engine" / "include").glob("*.h"))
    if not EXE.exists() or EXE.stat().st_mtime < max(s.stat().st_mtime for s in sources + headers):
        env_path = str(Path(gcc).parent)
        subprocess.run([gcc, "-Wall", "-Wextra", "-O1", "-I", str(ROOT / "engine" / "include"), "-o", str(EXE)]
                       + [str(s) for s in sources], check=True, env={**os.environ, "PATH": env_path + os.pathsep + os.environ["PATH"]})


def state_line(st):
    spr = ",".join(f"{t}:{im}" for t, im in sorted(st["sprites"].items()))
    return f"STATE bg={st['bg']} spr={spr} vars={','.join(str(x) for x in st['vars'])}"


def python_trace(program, chapter, entry, choices):
    vm = VM(program, Coverage())
    vm.trace = []
    st = vm.initial(chapter, entry)
    queue = list(choices)
    menus = 0
    while True:
        kind, info = vm.run(st)
        if kind == "end":
            vm.trace += ["END", state_line(st)]
            return vm.trace
        vm.trace += [f"MENU {len(info)}", state_line(st)]
        menus += 1
        if menus >= MAX_MENUS:
            vm.trace.append("STOP")
            return vm.trace
        pick = queue.pop(0) if queue else 0
        st["pc"] = info[pick][1]
        st["stack"] = []


def host_trace(chapter, entry, choices):
    out = subprocess.run([str(EXE), str(DATA), str(chapter), str(entry), ",".join(map(str, choices)), str(MAX_MENUS)],
                         capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def random_choices(seed, count=400):
    rng = random.Random(seed)
    return [rng.randint(0, 5) for _ in range(count)]


@pytest.fixture(scope="module")
def program():
    if not (DATA / "meta.json").exists():
        pytest.skip("falta build/data")
    build_host()
    return Program(DATA)


def clamp_choices(program, chapter, entry, choices):
    """Ajusta cada decision al numero de opciones real para que ambos lados elijan lo mismo."""
    vm = VM(program, Coverage())
    st = vm.initial(chapter, entry)
    queue = list(choices)
    fixed = []
    while len(fixed) < MAX_MENUS:
        kind, info = vm.run(st)
        if kind == "end":
            return fixed
        pick = (queue.pop(0) if queue else 0) % len(info)
        fixed.append(pick)
        st["pc"] = info[pick][1]
        st["stack"] = []
    return fixed


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5])
def test_story_routes_match(program, seed):
    start = (program.story_index, 0)
    choices = clamp_choices(program, *start, random_choices(seed))
    expected = python_trace(program, *start, choices)
    got = host_trace(*start, choices)
    assert len(expected) > 100
    assert got == expected


def test_all_first_choice_route(program):
    start = (program.story_index, 0)
    expected = python_trace(program, *start, [])
    assert host_trace(*start, []) == expected
