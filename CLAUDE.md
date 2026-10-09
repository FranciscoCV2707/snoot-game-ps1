# Proyecto: Port de Snoot Game (Ren'Py) a PlayStation 1

## Qué es
Convertimos una novela visual de Ren'Py a un formato que un motor propio en C
ejecuta en PS1. La PC hace todo el trabajo pesado (convertidores en Python);
la PS1 solo ejecuta.

## Alcance (no lo amplíes sin preguntar)
- Solo español (traducción oficial de game/tl/es). Nada de selector de idioma.
- Título: fondo negro, logo, SIN música. Comenzar / Continuar / Capítulos extra
  (bloqueado hasta ver todos los finales de las rutas principales) / Galería /
  Opciones. Sin botón Salir.
- Opciones: solo volumen de música y de efectos.
- Pausa con Start: Seguir, Saltar texto leído, Guardar, Cargar, Opciones, Salir al título.
- R1: saltar solo texto ya leído; se detiene en texto nuevo y en decisiones.
- Material picante siempre activado (constante del compilador, no es opción).
- 3 ranuras + progreso (texto leído, finales, galería) en un archivo de memory card.
- Todo en un solo CD.

## Documentos que debes leer al iniciar cada sesión
- PLAN.md: plan completo por fases
- docs/bitacora.md: qué se hizo y qué sigue
- docs/decisiones.md: decisiones técnicas tomadas (no las contradigas sin preguntar)
- docs/bytecode.md: el contrato entre convertidor y motor

## Reglas
- NUNCA modifiques nada dentro de original/. Es solo lectura.
- Trabaja solo en la tarea pedida; si ves algo más que mejorar, anótalo en
  docs/bitacora.md como pendiente en lugar de hacerlo.
- Antes de cambios grandes, propón un plan y espera aprobación.
- Todo código Python lleva tests en tests/ y debe pasar `pytest`.
- Si cambias el formato del bytecode, actualiza docs/bytecode.md, el compilador,
  el simulador y el motor en el mismo cambio, y sube el número de versión.
- Código del motor en C99, compatible con PSn00bSDK. Basarse en sus ejemplos
  oficiales y en la documentación psx-spx; no inventar registros ni funciones.
- Respeta el presupuesto de memoria de docs/presupuesto-memoria.md.
- Al terminar, actualiza docs/bitacora.md y dime exactamente cómo probar el cambio.
- Explicaciones y documentación en español; código y nombres en inglés.
- Commits: conventional commits en inglés. Commit después de cada tarea terminada.

## Reglas de Windows (obligatorias)
- Todo archivo de texto se abre con `encoding="utf-8"`. Nunca uses la codificación
  por defecto del sistema.
- Rutas siempre con `pathlib.Path`; nunca armes rutas con "/" o "\" a mano.
- Los scripts del proyecto se escriben en Python, no en .sh ni .bat.
- Cuando me des comandos para correr, dalos para PowerShell.
- Al llamar herramientas externas (mkpsxiso, psxavenc, cmake) usa
  `subprocess.run([...], check=True)` con lista de argumentos, sin `shell=True`.

## Comandos (PowerShell, con el entorno virtual activado)
- Activar entorno: `.\.venv\Scripts\Activate.ps1`
- Verificar entorno: `python tools/check_env.py`
- Tests: `pytest`
- Build completo: `python build.py`
- Solo motor: `cmake --build build/engine`
- Simulador: `python -m tools.simulator build/data/SCRIPT/`

## Entorno
- PC con Windows 10 (64 bits), proyecto en C:\dev\snoot-ps1 (ruta corta, sin OneDrive)
- Python 3.12 (venv en .venv; el Python 3.14 del sistema NO se usa), Git, CMake, Ninja, ffmpeg, Graphviz
- PSn00bSDK instalado vía MSYS2 en C:\msys64\usr\local\psn00bsdk (bin\ contiene
  mipsel-none-elf-gcc, mkpsxiso y psxavenc). Variable PSN00BSDK_LIBS ya definida.
- Emuladores en C:\Users\Pako\Desktop\snoot: duckstation-windows-x64-release (jugar),
  pcsx-redux-nightly-... (depurar, trae OpenBIOS). BIOS reales en "ps1 bios" (SCPH1001, 5500, 5501, 5502).
- Juego original copiado en original/ (sin .git; versión de origen: ver docs/entorno.md)
- Plan B para herramientas que fallen en Windows: WSL2 (Ubuntu)
