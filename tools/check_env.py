"""Verifica que el entorno de desarrollo esta completo."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PSN00BSDK_BIN = Path(r"C:\msys64\usr\local\psn00bsdk\bin")
EMULATOR_ROOT = Path(r"C:\Users\Pako\Desktop\snoot")


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    candidate = PSN00BSDK_BIN / f"{name}.exe"
    return str(candidate) if candidate.exists() else None


def first_line(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0] if lines else ""


def check_tool(name, version_args):
    path = find_tool(name)
    if not path:
        return False, "no encontrado"
    return True, first_line([path, *version_args]) or path


def check_python():
    ok = sys.version_info[:2] == (3, 12)
    return ok, sys.version.split()[0] + ("" if ok else " (se requiere 3.12; activa el .venv)")


def check_env_var(name, expected=None):
    value = os.environ.get(name)
    if not value:
        return False, "no definida"
    if expected is not None and value != expected:
        return False, f"valor inesperado: {value}"
    return True, value


def check_path(path, label):
    return path.exists(), str(path)


def check_project_path():
    root = str(PROJECT_ROOT)
    ok = " " not in root and root.isascii() and "OneDrive" not in root
    return ok, root


def check_original():
    path = PROJECT_ROOT / "original" / "game" / "script.rpy"
    return path.exists(), str(path)


def check_modules():
    missing = []
    for module in ("PIL", "numpy", "pytest"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return not missing, "ok" if not missing else "faltan: " + ", ".join(missing)


def build_checks():
    return [
        ("Python 3.12", check_python),
        ("Modulos Python (pillow, numpy, pytest)", check_modules),
        ("git", lambda: check_tool("git", ["--version"])),
        ("cmake", lambda: check_tool("cmake", ["--version"])),
        ("ninja", lambda: check_tool("ninja", ["--version"])),
        ("ffmpeg", lambda: check_tool("ffmpeg", ["-version"])),
        ("graphviz (dot)", lambda: check_tool("dot", ["-V"])),
        ("mipsel-none-elf-gcc", lambda: check_tool("mipsel-none-elf-gcc", ["--version"])),
        ("mkpsxiso", lambda: check_tool("mkpsxiso", ["--help"])),
        ("psxavenc", lambda: check_tool("psxavenc", [])),
        ("PSN00BSDK_LIBS", lambda: check_env_var("PSN00BSDK_LIBS")),
        ("PYTHONUTF8=1", lambda: check_env_var("PYTHONUTF8", "1")),
        ("Ruta del proyecto corta", check_project_path),
        ("DuckStation", lambda: check_path(EMULATOR_ROOT / "duckstation-windows-x64-release" / "duckstation-qt-x64-ReleaseLTCG.exe", "")),
        ("PCSX-Redux", lambda: check_path(next(EMULATOR_ROOT.glob("pcsx-redux-nightly-*/pcsx-redux.exe"), EMULATOR_ROOT / "pcsx-redux.exe"), "")),
        ("BIOS de PS1", lambda: check_path(EMULATOR_ROOT / "ps1 bios" / "SCPH1001.BIN", "")),
        ("Juego original en original/", check_original),
    ]


def main():
    failed = 0
    for label, check in build_checks():
        ok, detail = check()
        failed += not ok
        print(f"[{'OK' if ok else 'FALLA'}] {label}: {detail}")
    print()
    print("Todo listo." if not failed else f"{failed} verificacion(es) fallida(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
