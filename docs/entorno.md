# Entorno de desarrollo

Fecha de preparación: 2026-10-08. Sistema: Windows 10 IoT Enterprise LTSC 2021.

## Versiones
| Herramienta | Versión | Ubicación |
|---|---|---|
| Python (proyecto) | 3.12.10 | `.venv` (creado con `py -3.12`) |
| Python (sistema) | 3.14.4 | No se usa en el proyecto |
| pillow / numpy / pytest | 12.3.0 / 2.5.3 / 9.1.1 | ver `requirements.txt` |
| Git | 2.53.0 | PATH |
| CMake | 4.3.1 | PATH |
| Ninja | 1.13.2 | `C:\ninja` |
| ffmpeg | 8.1 | winget |
| Graphviz | 16.1.0 | `C:\Program Files\Graphviz\bin` (agregado al PATH de usuario) |
| PSn00bSDK | 0.24 (GCC 12.2.0) | `C:\msys64\usr\local\psn00bsdk` (bin, lib, share) |
| mkpsxiso | 2.10 | mismo `bin` de PSn00bSDK |
| psxavenc | incluido en PSn00bSDK | mismo `bin` |

## Emuladores (en `E:\snoot`)
- DuckStation: `duckstation-windows-x64-release\duckstation-qt-x64-ReleaseLTCG.exe`
- PCSX-Redux: `pcsx-redux-nightly-26946.20261008.32-x64\pcsx-redux.exe` (trae OpenBIOS)
- BIOS: `ps1 bios\` (SCPH1001 NTSC-U, scph5500 NTSC-J, scph5501 NTSC-U, scph5502 PAL)

## Variables de entorno
- `PYTHONUTF8=1` (usuario). Requiere abrir una terminal nueva.
- `PSN00BSDK_LIBS=C:/msys64/usr/local/psn00bsdk/lib/libpsn00b`
- Rutas largas de Windows activadas; `git config --global core.longpaths true` y `core.autocrlf false`.

## Juego original
Copiado a `original/` desde `E:\snoot\snootgame` (sin carpeta `.git`,
por lo que no hay commit de referencia). Repositorio oficial:
https://git.cavemanon.xyz/Cavemanon/SnootGame. `original/` está en `.gitignore`.

## Notas
- **mkpsxiso y rutas absolutas:** en la plantilla de PSn00bSDK, `${PROJECT_SOURCE_DIR}/system.cnf`
  se expande a `C:/...` y mkpsxiso 2.10 lo concatena mal (`build/C:/...`). Solución: en el XML
  usar rutas relativas al directorio de build (copiar los archivos allí). Aplicar lo mismo en `build.py`.
- Prueba "hola mundo": `E:\dev\hello-ps1\build\template.cue` (generado desde la plantilla, 1056 sectores).
- Exclusión de Windows Defender para `E:\dev`: hecha.
- `template.cue` verificado en DuckStation y PCSX-Redux. En PCSX-Redux hay que usar una BIOS real
  (SCPH1001); con OpenBIOS mostró un cubo 3D propio en vez del disco.
