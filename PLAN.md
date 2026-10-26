# Plan de trabajo: Port de Snoot Game (Ren'Py) a PlayStation 1

> Documento maestro del proyecto. Está pensado para trabajar fase por fase con **Claude Code**.
> Cada fase tiene: objetivo, por qué existe, tareas, entregables, criterios de "terminado", el prompt sugerido para Claude Code y los riesgos conocidos.
>
> Regla de oro: **no se avanza a la siguiente fase hasta que la actual cumple sus criterios de terminado.**
>
> **Cambios en la v4 (menús definitivos):**
> - **Pantalla de título:** fondo negro, logo de Snoot Game y **sin música**. Opciones: *Comenzar*, *Continuar*, *Capítulos extra* (bloqueado hasta terminar todas las rutas), *Galería* y *Opciones*. No hay botón *Salir* (en consola se apaga y ya).
> - **Opciones:** solo volumen de música y de efectos. Se descartan las demás opciones de Ren'Py (ventana/pantalla completa, desplazamiento con la rueda del mouse, desarrollador, mods, idioma).
> - **Material picante:** siempre activado, fijo en el disco; no es una opción.
> - **Saltar texto leído:** con **R1** durante el juego. Pasa rápido solo lo que ya leíste y se detiene en texto nuevo y en cada decisión.
> - **Menú de pausa (Start):** Seguir, Saltar texto leído, Guardar, Cargar, Opciones, Salir al título.
> - **3 ranuras de guardado** (antes 1) en un solo archivo de la memory card, para poder guardar antes de una decisión y probar otra ruta.
> - **Galería:** las imágenes especiales (CGs) se desbloquean al verlas en el juego.
> - El progreso del jugador (texto leído, finales, galería) se guarda en la memory card.
>
> **Cambios en la v3 (alcance reducido; menú y guardado reemplazados por la v4):**
> - **Solo español.** El texto se toma de la traducción oficial (`game/tl/`). El formato deja la puerta abierta a agregar inglés después sin rehacer nada.
> - **Menú sencillo:** logo arriba + *Iniciar*, *Continuar*, *Opciones* (volumen de música y de efectos). Nada de galería, créditos en menú, historial ni modo automático.
> - **Guardado simple:** una sola partida en la memory card. *Continuar* la busca y la carga; durante el juego se guarda desde un menú de pausa (botón Start).
> - **Un solo disco:** con estas decisiones el juego cabe holgado en un CD (ver "Presupuesto del disco" en la Fase 2).
> - Se agregó la licencia real del juego (código AGPLv3, arte y audio CC-BY-SA 4.0) en la Fase 11.
>
> **Cambios en la v2:**
> - El equipo de desarrollo ahora es una **PC con Windows 10/11** (antes: Mac con Xubuntu). Se reescribió la Fase 0, los comandos y el `CLAUDE.md`.
> - `build.sh` se reemplaza por **`build.py`** (Python funciona igual en Windows y Linux; Bash en Windows da problemas).
> - Nueva sección [4.4 Reglas para trabajar en Windows](#44-reglas-para-trabajar-en-windows) (codificación UTF-8, rutas, saltos de línea, antivirus).
> - Se adelantó la prueba de **música XA + carga de datos** a la Fase 2 (es el riesgo más probable del proyecto).
> - Se agregaron los datos **persistentes** de Ren'Py (finales vistos, texto leído) a la auditoría y al guardado.
> - Prueba temprana en hardware real al terminar la Fase 6 (antes solo se mencionaba en la tabla de riesgos).

---

## Índice

1. [Visión general](#1-visión-general)
2. [Qué significa "port al 100%"](#2-qué-significa-port-al-100)
3. [Conceptos clave de la PS1](#3-conceptos-clave-de-la-ps1)
4. [Arquitectura del proyecto](#4-arquitectura-del-proyecto)
5. [Cómo trabajar con Claude Code](#5-cómo-trabajar-con-claude-code)
6. [Fase 0 — Entorno y "Hola mundo" en PS1](#fase-0--entorno-y-hola-mundo-en-ps1)
7. [Fase 1 — Auditoría de Snoot Game](#fase-1--auditoría-de-snoot-game)
8. [Fase 2 — Decisiones técnicas y especificación](#fase-2--decisiones-técnicas-y-especificación)
9. [Fase 3 — Convertidor de scripts y simulador](#fase-3--convertidor-de-scripts-y-simulador)
10. [Fase 4 — Pipeline de imágenes (con vista CRT)](#fase-4--pipeline-de-imágenes-con-vista-crt)
11. [Fase 5 — Pipeline de audio](#fase-5--pipeline-de-audio)
12. [Fase 6 — Motor PS1: base](#fase-6--motor-ps1-base)
13. [Fase 7 — Motor PS1: intérprete y escenas](#fase-7--motor-ps1-intérprete-y-escenas)
14. [Fase 8 — Motor PS1: audio, transiciones, guardado y menús](#fase-8--motor-ps1-audio-transiciones-guardado-y-menús)
15. [Fase 9 — Construcción del CD y build automático](#fase-9--construcción-del-cd-y-build-automático)
16. [Fase 10 — Pruebas y control de calidad](#fase-10--pruebas-y-control-de-calidad)
17. [Fase 11 — Pulido, hardware real y distribución](#fase-11--pulido-hardware-real-y-distribución)
18. [Riesgos y planes B](#18-riesgos-y-planes-b)
19. [Apéndice A — Plantilla de CLAUDE.md](#apéndice-a--plantilla-de-claudemd)
20. [Apéndice B — Borrador de la especificación del bytecode](#apéndice-b--borrador-de-la-especificación-del-bytecode)
21. [Apéndice C — Glosario](#apéndice-c--glosario)

---

## 1. Visión general

**Meta:** que Snoot Game se pueda jugar completo en una PlayStation 1 (emulador y consola real), con toda su historia, decisiones, rutas y finales, **en español**, en **un solo disco**.

**Fuente oficial del juego:** https://git.cavemanon.xyz/Cavemanon/SnootGame (Gitea de Cavemanon). La página oficial confirma que el juego está disponible en inglés, español y tailandés.

**Idea central:** la PS1 **no puede correr Ren'Py** (Ren'Py necesita un intérprete de Python y cientos de MB de RAM; la PS1 tiene 2 MB). Por eso el proyecto tiene dos mitades:

```
 ┌──────────────────────────── EN TU PC (Windows) ────────────────────────────┐
 │                                                                             │
 │  Código de Snoot Game (.rpy, imágenes, audio)                               │
 │        │                                                                    │
 │        ▼                                                                    │
 │  CONVERTIDORES (Python)                                                     │
 │   • scripts .rpy  ──► bytecode compacto (.VNB)                              │
 │   • imágenes PNG/WEBP ──► texturas PS1 (.TIM o formato propio)              │
 │   • música/efectos ──► XA (música) y VAG (efectos)                          │
 │        │                                                                    │
 │        ▼                                                                    │
 │  CONSTRUCTOR DE CD (mkpsxiso) ──► snootgame.bin / snootgame.cue             │
 └─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
 ┌──────────────────────────── EN LA PS1 ──────────────────────────────────────┐
 │  MOTOR (C, PSn00bSDK): lee el bytecode del CD y "actúa" la novela:          │
 │  fondos, personajes, texto, decisiones, música, guardado en memory card.    │
 └─────────────────────────────────────────────────────────────────────────────┘
```

**Equipo de desarrollo:** una PC con **Windows 10 (versión 1809 o más nueva) u 11**, de 64 bits. Cualquier PC normal de los últimos años da de sobra: el proyecto no pide nada pesado.

| Requisito | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10 1809+ 64 bits | Windows 11 |
| RAM | 8 GB | 16 GB |
| Disco | 20 GB libres | SSD con 50 GB libres (el juego original + builds + imágenes de CD) |
| Otros | — | Un control USB (para probar en el emulador como en la consola) |

**Cómo se trabaja en Windows:** todo de forma **nativa** (PSn00bSDK, mkpsxiso, psxavenc, Python y los emuladores tienen versión para Windows). La terminal es **PowerShell** (o Git Bash dentro de Claude Code). **WSL2** (Linux dentro de Windows) queda como **plan B**, solo si alguna herramienta no funcionara en Windows.

---

## 2. Qué significa "port al 100%"

Para no frustrarnos, definimos desde el inicio qué sí y qué no:

| Elemento | ¿Al 100%? | Nota |
|---|---|---|
| Todo el texto y diálogos | ✅ Sí | Solo en español (traducción oficial). Inglés queda como posible extra futuro. |
| Todas las decisiones, rutas, variables y finales | ✅ Sí | Se verifica automáticamente con el simulador (Fase 3). |
| Fondos y personajes | ✅ Sí, adaptados | Menor resolución y colores; tramado pensado para CRT. |
| Música y efectos | ✅ Sí, adaptados | Calidad tipo PS1. |
| Guardar / cargar partida | ✅ Sí | 3 ranuras en memory card. Guardar y Cargar desde la pausa; Continuar desde el título. |
| Saltar texto ya leído | ✅ Sí | Botón R1. Se detiene en texto nuevo y en decisiones. |
| Galería | ✅ Sí, simplificada | Visor de imágenes desbloqueadas, una a la vez. |
| Capítulos extra | ✅ Sí | Se desbloquean al terminar todas las rutas. |
| Material picante | ✅ Siempre activo | Fijo en el disco, sin opción para desactivarlo. |
| Transiciones (dissolve, fade) | ⚠️ Aproximadas | La PS1 tiene modos de mezcla limitados. |
| Bordes suaves de personajes | ⚠️ Aproximados | La PS1 solo tiene transparencia "sí/no"; en CRT casi no se nota. |
| Calidad de imagen HD | ❌ No | Límite físico del hardware. |
| Menús de Ren'Py | 🔄 Reemplazados | Título, pausa y opciones propios y sencillos (ver Fase 8). |
| Opciones de Ren'Py (ventana, rueda del mouse, desarrollador, mods, idioma) | ❌ No | No aplican en consola. Solo quedan los volúmenes. |
| Historial y modo automático | ❌ No (por ahora) | Extras opcionales si sobra tiempo. |

**Definición de terminado del proyecto:** el simulador confirma que *todas* las etiquetas y finales son alcanzables, y el juego se puede completar en DuckStation de principio a fin en cada ruta sin errores.

---

## 3. Conceptos clave de la PS1

Lo mínimo que hay que entender para tomar buenas decisiones (y para darle contexto a Claude Code):

- **RAM principal: 2 MB.** Ahí va el motor, el script de la escena actual, buffers y variables. Nunca cabe "todo el juego": se carga por partes desde el CD.
- **VRAM: 1 MB**, organizada como una "hoja" de 1024×512 píxeles de 16 bits. Ahí viven:
  - los *framebuffers* (lo que se ve en pantalla; usamos dos para evitar parpadeo),
  - las texturas (fondos, personajes, fuente de letras),
  - las paletas de colores (CLUT).
- **Texturas:** pueden ser de 4 bits (16 colores), 8 bits (256 colores) o 15/16 bits (color directo). Una textura se dibuja como *sprite* de máximo **256×256**, así que las imágenes más grandes se parten en pedazos (*tiles*).
- **Transparencia:** el color `0x0000` en una textura es totalmente transparente. Además existe un bit de semitransparencia con 4 modos de mezcla fijos (50/50, suma, resta, suma 25%). No hay transparencia gradual tipo PNG.
- **CPU:** MIPS R3000A a ~33 MHz. Suficiente para una novela visual si no hacemos cosas pesadas en cada cuadro.
- **CD-ROM:** velocidad 2x (~300 KB/s). Leer un fondo toma fracciones de segundo, pero **mientras la música XA suena desde el CD, el lector está ocupado**: hay que planear cuándo se cargan los datos (ver Riesgos).
- **SPU (sonido):** 512 KB de RAM de audio para efectos cortos (formato VAG). La música larga se reproduce en streaming desde el CD (formato XA).
- **MDEC:** chip que descomprime imágenes tipo JPEG (lo usan los videos). Es una opción avanzada para fondos de mejor calidad.
- **Memory card:** 15 bloques de 8 KB. Una partida guardada de novela visual cabe holgada en 1 bloque.
- **Tramado (dithering):** la PS1 puede tramar por hardware y en una tele CRT el tramado se mezcla y parece un degradado suave. Lo aprovechamos en el arte.

---

## 4. Arquitectura del proyecto

### 4.1 Estructura del repositorio

```
snoot-ps1/
├── CLAUDE.md                  # Reglas e instrucciones para Claude Code (Apéndice A)
├── PLAN.md                    # Este documento
├── README.md                  # Cómo compilar y jugar
├── build.py                   # Un solo comando: convierte todo y genera el CD
├── requirements.txt           # Dependencias de Python con versión fija
├── .gitattributes             # Saltos de línea y archivos binarios (ver 4.4)
├── .gitignore
├── docs/
│   ├── entorno.md             # Versiones instaladas y cómo reinstalar (Fase 0)
│   ├── auditoria.md           # Resultado de la Fase 1
│   ├── decisiones.md          # Registro de decisiones técnicas (con fecha y motivo)
│   ├── bytecode.md            # Especificación del formato de script (Fase 2)
│   ├── presupuesto-memoria.md # RAM y VRAM: qué va dónde
│   └── bitacora.md            # Qué se hizo en cada sesión
├── original/                  # Código de Snoot Game SIN MODIFICAR (solo lectura)
├── tools/                     # Todo lo que corre en la PC (Python)
│   ├── check_env.py           # Verifica que todo el entorno está instalado
│   ├── audit/                 # Scripts de auditoría
│   ├── script_compiler/       # .rpy → bytecode
│   ├── simulator/             # Ejecuta el bytecode en la PC para probar rutas
│   ├── images/                # Conversión de imágenes + vista previa CRT
│   ├── audio/                 # Conversión de audio
│   └── disc/                  # Genera el XML de mkpsxiso
├── engine/                    # El motor en C para PS1
│   ├── CMakeLists.txt
│   ├── include/
│   └── src/
│       ├── main.c
│       ├── video.c            # Framebuffers, dibujo de sprites
│       ├── text.c             # Fuente y caja de diálogo
│       ├── input.c            # Control
│       ├── cd.c               # Lectura de archivos del CD
│       ├── assets.c           # Carga de fondos/personajes a VRAM
│       ├── vm.c               # Intérprete del bytecode
│       ├── audio.c            # XA y VAG
│       ├── save.c             # Memory card
│       └── menu.c             # Pantalla de título, pausa y opciones
├── tests/                     # Pruebas automáticas (pytest)
├── build/                     # Generado (en .gitignore)
└── disc/
    └── snootgame.xml          # Definición del CD para mkpsxiso
```

### 4.2 Flujo de datos

```
original/game/*.rpy ──► tools/script_compiler ──► build/data/SCRIPT/*.VNB ─┐
original/game/images ─► tools/images ──────────► build/data/IMG/*.TIM ────┤
original/game/audio ──► tools/audio ───────────► build/data/BGM/*.XA ─────┼─► mkpsxiso ─► .bin/.cue
                                                  build/data/SFX/*.VAG ────┤
engine/ ──────────────► CMake + PSn00bSDK ─────► build/SNOOT.EXE ─────────┘
```

### 4.3 Principio de diseño más importante

**Todo lo "inteligente" se hace en la PC, no en la PS1.** El convertidor resuelve nombres, calcula posiciones, decide qué cargar y cuándo, y deja todo listo. El motor de PS1 debe ser lo más tonto y rápido posible: leer, mostrar, esperar botón, saltar.

### 4.4 Reglas para trabajar en Windows

Son pocas, pero evitan los errores más comunes (y conviene que Claude Code las siga siempre; por eso también están en el `CLAUDE.md`):

1. **Ruta del proyecto corta, sin espacios ni acentos:** `E:\dev\snoot-ps1`. Nada de `C:\Users\José\Mis Documentos\...` ni carpetas sincronizadas con OneDrive (OneDrive bloquea archivos a mitad del build).
2. **Codificación UTF-8 siempre.** En Windows, Python abre los archivos con la codificación vieja (cp1252) si no se le indica otra cosa, y los `.rpy` (con acentos, ñ, comillas tipográficas) se rompen. Reglas:
   - Todo `open()` lleva `encoding="utf-8"` (o usar `Path.read_text(encoding="utf-8")`).
   - Además, activar el modo UTF-8 de Python a nivel sistema: variable de entorno `PYTHONUTF8=1`.
3. **Rutas con `pathlib`**, nunca concatenando cadenas con `/` o `\`. Así el mismo código corre en Windows y Linux.
4. **Saltos de línea:** archivo `.gitattributes` en la raíz para que git no altere archivos binarios ni los `.rpy`:
   ```
   * text=auto eol=lf
   *.png  binary
   *.webp binary
   *.jpg  binary
   *.ogg  binary
   *.mp3  binary
   *.wav  binary
   *.bin  binary
   *.TIM  binary
   *.VNB  binary
   *.XA   binary
   *.VAG  binary
   *.ps1  text eol=crlf
   ```
5. **Antivirus:** agregar `E:\dev\snoot-ps1` y la carpeta de PSn00bSDK como **exclusión de Windows Defender**. Si no, cada compilación y cada conversión de cientos de imágenes se vuelve mucho más lenta, y a veces Defender bloquea el `.exe` recién generado.
6. **Rutas largas:** activar el soporte de rutas largas de Windows (`LongPathsEnabled`) y en git `git config --global core.longpaths true`.
7. **Scripts del proyecto en Python, no en `.sh` ni `.bat`:** `build.py`, `tools/check_env.py`. Funcionan igual en cualquier sistema.

---

## 5. Cómo trabajar con Claude Code

### 5.1 Reglas de trabajo

1. **Una fase (o sub-tarea) por sesión.** Sesiones cortas y enfocadas funcionan mucho mejor que pedir "haz todo el port".
2. **Empieza cada sesión pidiendo que lea `CLAUDE.md`, `PLAN.md` y `docs/bitacora.md`.** Así retoma el contexto.
3. **Usa el modo plan para tareas grandes:** pide primero un plan, revísalo, y luego deja que lo ejecute.
4. **Todo cambio se prueba antes de darlo por bueno:** el código Python con `pytest`; el motor en el emulador.
5. **Commit de git después de cada tarea que funcione.** Si algo se rompe, regresas fácil.
6. **Las decisiones se documentan** en `docs/decisiones.md` (qué se decidió, por qué, alternativas descartadas).
7. **Al final de cada sesión:** pide que actualice `docs/bitacora.md` con lo hecho y lo pendiente.
8. **Cuando algo falle en el emulador,** pásale a Claude Code el error exacto, lo que esperabas ver y lo que viste (una captura ayuda mucho).

### 5.2 Plantilla de prompt para cualquier tarea

```
Lee CLAUDE.md, PLAN.md (sección de la Fase X) y docs/bitacora.md.
Tarea: [describe la tarea concreta].
Restricciones: [ej. no modificar original/, mantener compatibilidad con bytecode v1].
Criterio de terminado: [ej. los tests pasan y el emulador muestra Y].
Primero proponme un plan corto; no escribas código hasta que lo apruebe.
```

### 5.3 Cosas que Claude Code hace muy bien en este proyecto
- Parsers, convertidores y herramientas en Python.
- Pruebas automáticas y el simulador.
- Estructurar el motor en C y explicar el código.

### 5.4 Cosas donde hay que ir con más cuidado
- Programación específica de PS1 (registros, DMA, tiempos del CD): hay menos ejemplos públicos. Pide siempre que se base en los ejemplos oficiales de PSn00bSDK y en la documentación (psx-spx), y prueba cada paso en el emulador.
- Errores que solo se ven en la consola real (Fase 11).

---

## Fase 0 — Entorno y "Hola mundo" en PS1

**Objetivo:** tener todas las herramientas instaladas y comprobar que podemos compilar un programa mínimo de PS1 y correrlo en el emulador.

**Por qué:** si el entorno falla, todo lo demás falla. Mejor descubrirlo el primer día.

### Tareas
1. **Preparar Windows** (una sola vez):
   - Crear la carpeta `E:\dev\` (ver reglas de la sección 4.4).
   - Activar rutas largas: en PowerShell **como administrador**:
     ```powershell
     New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
     ```
   - Agregar `E:\dev` como exclusión en *Seguridad de Windows → Protección contra virus y amenazas → Exclusiones*.
   - Activar el modo UTF-8 de Python para tu usuario:
     ```powershell
     setx PYTHONUTF8 1
     ```
2. **Programas base con `winget`** (viene incluido en Windows 10/11; usar PowerShell normal):
   ```powershell
   winget install Git.Git
   winget install Python.Python.3.12
   winget install Kitware.CMake
   winget install Ninja-build.Ninja
   winget install Gyan.FFmpeg
   winget install Graphviz.Graphviz
   ```
   Al terminar, **cerrar y abrir de nuevo la terminal** para que se actualice el `PATH`. Configurar git:
   ```powershell
   git config --global core.longpaths true
   git config --global core.autocrlf false
   ```
   (Los saltos de línea los controla el `.gitattributes` del proyecto, no la configuración global.)
3. **Instalar Claude Code** (nativo en Windows, desde PowerShell, sin permisos de administrador):
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
   Verificar con `claude --version` y `claude doctor`. Con Git for Windows instalado (paso 2), Claude Code usa Git Bash para ejecutar comandos; sin él usaría PowerShell. Requiere una cuenta Pro, Max, Team, Enterprise o de Console.
4. Crear el repositorio `E:\dev\snoot-ps1\` con la estructura de la sección 4.1, `git init`, el `CLAUDE.md` del Apéndice A, el `.gitattributes` de la sección 4.4 y un `.gitignore` (que incluya `build/`, `.venv/`, `original/` si no se quiere versionar el juego).
5. **Entorno virtual de Python:**
   ```powershell
   cd E:\dev\snoot-ps1
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install pillow numpy pytest
   pip freeze > requirements.txt
   ```
   Si PowerShell no deja activar el entorno ("la ejecución de scripts está deshabilitada"), correr una vez:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
6. **PSn00bSDK** (incluye el compilador MIPS `mipsel-none-elf-gcc`, `elf2x` y **mkpsxiso**):
   - Descargar el ZIP de Windows de la última *release* en GitHub (`Lameguy64/PSn00bSDK`) y extraerlo en una ruta corta, por ejemplo `C:\PSn00bSDK`.
   - Agregar `C:\PSn00bSDK\bin` al `PATH` (Configuración del sistema → Variables de entorno).
   - Crear la variable de entorno `PSN00BSDK_LIBS` = `C:\PSn00bSDK\lib\libpsn00b` (muy recomendado; evita escribir rutas fijas en el proyecto).
   - Requiere CMake 3.21 o más nuevo (el de `winget` cumple).
   - Verificar: `mipsel-none-elf-gcc --version` y `mkpsxiso --help`. Si dice "no se reconoce el comando", reiniciar la PC.
7. **mkpsxiso:** ya viene con PSn00bSDK. Solo si hiciera falta una versión más nueva, descargar el binario de Windows de su repositorio (`Lameguy64/mkpsxiso`).
8. **psxavenc** (convierte audio a XA/VAG): descargar el binario para Windows de las *releases* de su repositorio (`WonderfulToolchain/psxavenc`) y ponerlo en `C:\PSn00bSDK\bin` (ya está en el `PATH`). Si no hubiera binario de Windows para la versión actual, compilarlo con MSYS2 o usarlo desde WSL2 (plan B).
9. **Emuladores** (todos tienen versión para Windows):
   - **DuckStation**: el más preciso para jugar y tiene filtros CRT.
   - **PCSX-Redux**: depurador, visor de memoria/VRAM y scripting en Lua; ideal para cazar errores.
   - **no$psx** (opcional, solo Windows): otro depurador muy detallado, útil para comparar cuando algo raro solo pasa en un emulador.
   - Evitar ePSXe y emuladores basados en MAME para pruebas: son poco precisos.
10. Compilar la **plantilla/ejemplo** de PSn00bSDK (`C:\PSn00bSDK\share\psn00bsdk\template`):
    ```powershell
    cmake --preset default .
    cmake --build ./build
    ```
    Debe generar un `.bin/.cue`; correrlo en DuckStation y PCSX-Redux.
11. Colocar el código de Snoot Game en `original/`, desde el repositorio oficial (https://git.cavemanon.xyz/Cavemanon/SnootGame):
    ```powershell
    git clone https://git.cavemanon.xyz/Cavemanon/SnootGame.git original
    ```
    O descargar el ZIP desde la página del repositorio y **extraerlo con la herramienta de Windows o 7-Zip directo en esa carpeta**, sin abrir ni guardar ningún archivo con un editor. Anotar en `docs/entorno.md` el *commit* o versión exacta descargada, para que todo el proyecto se base siempre en la misma.
12. Escribir `tools/check_env.py`: revisa versiones de Python, git, CMake, Ninja, ffmpeg, Graphviz, `mipsel-none-elf-gcc`, `mkpsxiso`, `psxavenc`, la variable `PSN00BSDK_LIBS` y `PYTHONUTF8`; imprime ✔/✘ por cada uno.

### Entregables
- Repositorio creado con estructura, `CLAUDE.md`, `PLAN.md`, `.gitignore`.
- `docs/entorno.md` con versiones exactas instaladas y cómo reinstalar todo.
- Un `hello.bin/.cue` que muestra texto en pantalla en DuckStation.

### Terminado cuando
- [ ] El ejemplo de PSn00bSDK corre en DuckStation y PCSX-Redux.
- [ ] `pytest` corre (aunque no haya tests aún).
- [ ] `python tools/check_env.py` sale todo en ✔.
- [ ] El código original está en `original/` y no se ha modificado.

### Prompt sugerido
```
Lee CLAUDE.md y PLAN.md (Fase 0 y sección 4.4). Ayúdame a preparar el entorno en
Windows 11 (PowerShell). Ve paso por paso: dime el comando, espera a que te pase la
salida, y continúa. Al final, crea docs/entorno.md con las versiones exactas y el
script de verificación tools/check_env.py que confirme que todo está instalado.
```

### Riesgos
- Versiones del toolchain incompatibles → usar exactamente la versión que recomienda PSn00bSDK.
- Emulador sin BIOS → DuckStation y PCSX-Redux necesitan una BIOS de PS1 (extraída de tu propia consola) o, en el caso de PCSX-Redux, pueden usar su BIOS libre (OpenBIOS) para pruebas.
- "Comando no reconocido" después de instalar algo → casi siempre es el `PATH`: cerrar la terminal, abrir otra, y si sigue, reiniciar.
- Windows Defender marca como sospechoso un `.exe` de PS1 recién compilado o una herramienta descargada → revisar que la exclusión de `E:\dev` y `C:\PSn00bSDK` esté puesta; descargar herramientas solo de sus repositorios oficiales.
- Alguna herramienta no funciona en Windows → plan B: instalar **WSL2 con Ubuntu** (`wsl --install`) y usar esa herramienta desde ahí sobre la misma carpeta (`/mnt/e/dev/snoot-ps1`). El resto del proyecto sigue en Windows.

---

## Fase 1 — Auditoría de Snoot Game

**Objetivo:** saber exactamente qué tiene el juego antes de diseñar nada.

**Por qué:** el diseño del convertidor y del motor depende de qué instrucciones de Ren'Py usa realmente el juego, cuántas imágenes hay, de qué tamaño, cuánto audio, etc.

### Tareas
1. Script `tools/audit/inventario.py` que recorra `original/` y genere:
   - Lista de archivos `.rpy`, líneas totales, número de líneas de diálogo.
   - **Todas las instrucciones de Ren'Py usadas** y cuántas veces: `label`, `jump`, `call`, `return`, `menu`, `if/elif/else`, `scene`, `show`, `hide`, `with`, `play`, `stop`, `queue`, `pause`, `$` (Python de una línea), `python:` (bloques), `define`, `default`, `image`, `transform`, ATL, `screen`, `window`, `nvl`, `voice`, etc.
   - Etiquetas de texto usadas (`{i}`, `{b}`, `{w}`, `{nw}`, `{p}`, `{cps}`, `{color}`, `{size}`...).
   - Personajes definidos (`define x = Character(...)`).
   - Variables: nombres, tipos y valores (bool, int, str).
   - Datos **persistentes** (`persistent.algo`): finales desbloqueados, galería, texto leído, etc. Estos no van en la partida guardada sino en un archivo aparte que dura entre partidas.
   - Todo el código Python (bloques `init python`, `$`): listarlo completo, porque cada uno hay que traducirlo o descartarlo a mano.
   - Pantallas personalizadas (`screen`) y qué hacen.
2. Inventario de imágenes: cantidad, resoluciones, formatos, si son fondos, personajes, CGs o UI; cómo se componen las expresiones de los personajes (imágenes separadas o capas).
3. Inventario de audio: pistas de música, efectos, duraciones totales, formatos; si hay voces.
4. Videos (si existen) y su duración.
5. **Traducción al español (crítico, porque es el único idioma del port):** ubicar la carpeta de español dentro de `game/tl/` y medir su cobertura:
   - porcentaje de diálogos traducidos (meta: 100%),
   - opciones de los menús de decisión y nombres de personajes (bloques `translate ... strings`),
   - lista de líneas **sin traducir** (si hay, se traducen a mano en un archivo propio del port; ver Fase 3),
   - caracteres que usa el texto en español (para saber exactamente qué letras necesita la fuente).
   - Ojo: la estructura del juego (saltos, decisiones, variables) sale de los `.rpy` en inglés; la traducción solo reemplaza las cadenas.
6. Grafo de la historia: etiquetas como nodos, `jump/call/menu` como aristas. Exportarlo como imagen (Graphviz) para ver las rutas y finales.
7. Versión de Ren'Py que usa el juego.
8. Revisar la licencia del repositorio (`LICENSE`) y anotarla (según la web oficial: código AGPLv3, assets CC-BY-SA 4.0; confirmarlo con el archivo).
9. Pantallas y lógica que **ya no se necesitan** por el alcance reducido: marcarlas como *descartables*, pero revisar si alguna cambia variables del juego antes de descartarla. Según el menú de opciones del juego original:
   - Visualizar (ventana / pantalla completa) → descartar.
   - "Habilitar movimiento de desplazamiento hacia adelante" → por su nombre, sirve para avanzar con la rueda del mouse; descartar (confirmarlo en el código).
   - Opciones de desarrollador (visor de puntos, selector de capítulos) → descartar. *Nota:* el visor de puntos puede servir como referencia para depurar el simulador.
   - Mods (todo) → descartar.
   - Idioma → descartar (solo español).
   - Extras: mods, ayuda y "acerca de" → descartar.
   - Historial → descartar por ahora.
10. **Lo que sí se conserva y hay que entender a fondo:**
    - **Material picante:** qué variable lo controla, qué escenas e imágenes dependen de ella. En el port se fija como **siempre activado**: el compilador resuelve esas condiciones en la PC y nunca se convierten las versiones alternativas que no se usan (ahorra espacio).
    - **Saltar:** cómo marca Ren'Py el texto leído; contar el **número total de líneas de diálogo** (define cuánto ocupa en la memory card guardar qué líneas se leyeron).
    - **Galería:** lista de imágenes que aparecen en ella, en qué orden, y qué condición las desbloquea.
    - **Capítulos extra:** cuáles son, en qué etiquetas empiezan, y cuál es la condición original para desbloquearlos (en el port se desbloquean al terminar todas las rutas, ver Fase 8).
    - **Finales:** lista completa de finales y la etiqueta de cada uno (se necesita para saber cuándo "se terminaron todas las rutas").
    - **Logo** del título como imagen aparte (para la pantalla de título en negro).

### Entregables
- `docs/auditoria.md` con tablas y conclusiones: qué es fácil, qué es difícil, qué hay que hacer a mano.
- `build/audit/grafo_historia.svg`.
- `build/audit/inventario.json` (datos crudos para las siguientes fases).

### Terminado cuando
- [ ] Se conoce el 100% de las instrucciones de Ren'Py usadas, sin "desconocidos".
- [ ] Cada bloque de Python está clasificado: *traducible automáticamente*, *traducir a mano* o *descartable* (ej. código solo de UI de PC).
- [ ] Tenemos números reales de imágenes y minutos de audio.
- [ ] Están identificados: la variable del material picante, la lista de la galería, los capítulos extra, todos los finales y el número total de líneas de diálogo.

### Prompt sugerido
```
Lee CLAUDE.md y PLAN.md (Fase 1). Escribe tools/audit/inventario.py que analice
original/ y genere build/audit/inventario.json y docs/auditoria.md con todo lo
que pide la Fase 1. No modifiques original/. Agrega tests básicos en tests/.
Al final, resume en 10 líneas qué partes del juego serán difíciles de portar.
```

---

## Fase 2 — Decisiones técnicas y especificación

**Objetivo:** con los datos de la auditoría, tomar las decisiones grandes y escribir la especificación del formato que conecta el convertidor con el motor.

**Por qué:** el bytecode es el "contrato" entre la PC y la PS1. Si está bien definido, el convertidor y el motor se pueden desarrollar y probar por separado.

### Decisiones a tomar (cada una con prueba visual o medición)

1. **Resolución de pantalla**
   - Opción A: 320×240 → más simple y rápida, texto más grande (menos letras por línea).
   - Opción B: 512×240 o 640×240 → más nitidez horizontal, mejor para texto.
   - Opción C: 640×480 entrelazado → más resolución pero parpadeo en CRT y más VRAM.
   - **Cómo decidir:** prototipo con un fondo y una caja de texto real del juego en cada modo, visto en DuckStation con filtro CRT.
2. **Formato de fondos**
   - 8 bits con paleta + tramado (menos VRAM, carga más rápida).
   - 15 bits color directo + tramado (mejor calidad, más VRAM).
   - MDEC (calidad tipo JPEG; más complejo; opción para después).
   - **Cómo decidir:** convertir 5 fondos representativos en cada formato y comparar con vista CRT.
3. **Formato de personajes:** 8 bits con paleta propia por personaje (probable) o 4 bits.
4. **Fuente de texto:** ancho fijo (simple) o ancho variable (más texto por línea, se ve mejor; recomendado porque el español es más largo que el inglés). Solo necesita los caracteres que aparecen en la traducción (lista que sale de la auditoría): letras, números, puntuación, á é í ó ú ü ñ, ¿ ¡, comillas y raya de diálogo.
5. **Compresión en disco:** sin compresión vs. LZ4/LZSS para scripts e imágenes (el CD tiene espacio, pero comprimir puede acelerar cargas).
6. **Estrategia música + carga de datos** (ver Riesgos): cuándo se lee del CD sin cortar la música.
7. **Idioma:** solo español. Aun así, los textos van en una tabla aparte (`TEXT_ES.BIN`) referenciada por ID desde el bytecode, nunca escritos dentro del bytecode. Así, agregar inglés en el futuro sería solo generar un `TEXT_EN.BIN` y una opción en el menú.
8. **Organización del script:** un archivo de bytecode por capítulo/etiqueta grande, cargado a RAM cuando se entra.
9. **Formato del archivo de memory card** (ver propuesta abajo): 1 o 2 bloques, según cuántas líneas de diálogo tenga el juego.
10. **Material picante:** constante fija en el compilador (`PICANTE = True`). El compilador elimina las ramas que no se usan. Se deja el interruptor en `build.py` (`--sin-picante`) por si algún día se quiere generar un disco sin ese material, pero el disco oficial del port va siempre con él.

### Tareas
1. Prototipos de las decisiones 1 y 2 (pueden ser imágenes estáticas en el emulador).
2. **Prueba técnica de la decisión 6 (la más riesgosa):** un programa mínimo que reproduzca una pista XA y, al mismo tiempo, intente cargar un fondo del CD. Medir en DuckStation y PCSX-Redux si la música se corta y cuánto tarda la carga. Con esto se elige la estrategia antes de diseñar el motor, no después.
3. Escribir `docs/decisiones.md` con cada decisión.
4. Escribir `docs/bytecode.md`: especificación completa (partiendo del Apéndice B).
5. Escribir `docs/presupuesto-memoria.md`: mapa de VRAM y RAM.

### Propuesta inicial de mapa de VRAM (a validar)

```
VRAM 1024 × 512 (unidades de 16 bits)

x: 0          320                                           1024
   ┌───────────┬─────────────────────────────────────────────┐ y:0
   │ Frame-    │  Fondo actual (texturas, partido en tiles)   │
   │ buffer A  │                                               │
   │ 320×240   ├─────────────────────────────────────────────┤
   ├───────────┤  Personajes en pantalla (hasta 3-4 sprites) │
   │ Frame-    │                                               │
   │ buffer B  ├─────────────────────────────────────────────┤
   │ 320×240   │  Fuente │ UI caja de texto │ Paletas (CLUT)  │
   └───────────┴─────────────────────────────────────────────┘ y:512
```

### Propuesta inicial de RAM (2 MB, a validar)

| Uso | Tamaño aprox. |
|---|---|
| Motor (código + librerías) | 150–250 KB |
| Script del capítulo actual | hasta 256 KB |
| Buffer de carga desde CD / descompresión | 256 KB |
| Variables y estado de la partida | < 4 KB |
| Copia del archivo de memory card (sistema + 3 ranuras) | 8–16 KB |
| Pila y margen | resto |

### Presupuesto del disco (un solo CD)

Un CD-R de 74 minutos tiene unos **333,000 sectores** (≈ 650 MB de datos). Estimación con números típicos; se reemplaza con los datos reales de la auditoría:

| Contenido | Cálculo | Sectores aprox. | % del disco |
|---|---|---|---|
| Música XA 37.8 kHz estéreo | ~1,125 sectores por minuto; ejemplo 120 min | 135,000 | ~41% |
| (alternativa) Música XA 18.9 kHz estéreo | ~560 sectores por minuto; 120 min | 67,500 | ~20% |
| Fondos y CGs | ~150 KB c/u (15 bits, 320×240); ejemplo 250 | 19,000 | ~6% |
| Personajes y expresiones | ~50 KB c/u (8 bits); ejemplo 500 | 12,500 | ~4% |
| Efectos VAG | ejemplo 10 MB | 5,000 | ~1.5% |
| Motor + bytecode + texto en español | < 3 MB | < 1,500 | < 0.5% |
| Video de apertura (si existe, formato STR) | ~9,000 sectores por minuto | depende | — |

**Conclusiones:**
- Incluso con música a máxima calidad, el total queda alrededor del 50–55% del disco. **Un solo CD alcanza con margen.**
- Lo que ocupa espacio es la **música**, no el texto. Quitar el inglés ahorra apenas 1–2 MB; su verdadera ventaja es **menos trabajo**: una sola tabla de textos, una fuente más simple, la mitad de pruebas.
- Si la auditoría encontrara mucha más música o video del esperado, la primera palanca es bajar música a 18.9 kHz, no partir en dos discos.
- **Título sin música:** si esa pista también suena dentro del juego, no ahorra espacio (ya está en el disco). Su ventaja real es que el título carga al instante y el lector de CD queda libre. Si la pista solo se usa en el título original, sí se ahorran unos MB.
- El material picante fijo también ahorra: no se convierten las versiones alternativas de esas imágenes.

### Propuesta del archivo de memory card

Un solo archivo, **"SNOOT GAME"**. Un bloque de memory card mide 8 KB, de los que quedan unos **7.9 KB útiles** después de la cabecera y el icono. Al arrancar el juego, el archivo completo se lee a RAM; al guardar, se escribe completo.

| Sección | Contenido | Tamaño aprox. |
|---|---|---|
| Cabecera de la consola | Título sin acentos (la BIOS usa Shift-JIS) + icono 16×16 | 256 B |
| Control | Versión del formato + *checksum* de cada sección (detecta datos dañados) | 16 B |
| Opciones | Volumen de música y de efectos | 4 B |
| **Progreso** (dura entre partidas) | Finales vistos (1 bit c/u), imágenes de galería vistas (1 bit c/u), capítulos extra desbloqueados, **líneas leídas (1 bit por línea)** | ~2.5 KB con 20,000 líneas |
| Ranura 1, 2 y 3 | Posición en el script, variables, banderas, pila de `CALL`, fondo/personajes/música en pantalla, nombre del capítulo, tiempo de juego, número de guardado (para saber cuál es el más reciente) | ~1 KB c/u |
| **Total estimado** | | **≈ 6 KB → cabe en 1 bloque** |

- Si el juego tiene más de ~35,000 líneas, el archivo pasa a **2 bloques**. Lo decide la auditoría.
- **Opcional (recomendado):** guardar **dos copias** (2 bloques) y alternar entre ellas. Si la consola se apaga a mitad del guardado, la otra copia sigue intacta y no se pierde todo el progreso.

**Cuándo se escribe en la memory card:**
1. Al elegir *Guardar* en una ranura (se escribe todo: ranuras + progreso + opciones).
2. **Automáticamente al llegar a un final** (aviso "Guardando progreso…"), para que los finales, la galería y el texto leído no se pierdan.
3. Al salir al título desde la pausa.
4. Al cambiar volúmenes en Opciones (al salir de esa pantalla).

Si la consola se apaga sin pasar por ninguno de esos puntos, se pierde el texto leído desde el último guardado. Es aceptable y se explica en el README.

### Terminado cuando
- [ ] Todas las decisiones están en `docs/decisiones.md` con su motivo.
- [ ] El tamaño del archivo de memory card está calculado con los números reales (1 o 2 bloques).
- [ ] El presupuesto del disco con los números reales de la auditoría confirma que cabe en un CD con ≥ 15% libre.
- [ ] `docs/bytecode.md` cubre cada instrucción encontrada en la auditoría.
- [ ] El presupuesto de memoria cierra con margen (≥ 20% libre).

### Prompt sugerido
```
Lee CLAUDE.md, PLAN.md (Fase 2) y docs/auditoria.md. Con base en la auditoría,
propón la especificación completa del bytecode en docs/bytecode.md partiendo del
borrador del Apéndice B. Cada instrucción de Ren'Py del inventario debe tener una
traducción o una justificación de por qué se descarta. Después prepara los
prototipos de resolución y formato de fondos.
```

---

## Fase 3 — Convertidor de scripts y simulador

**Objetivo:** convertir todos los `.rpy` a bytecode y comprobar en la PC que todas las rutas funcionan **antes** de tocar la PS1.

**Por qué:** depurar en la PC es 100 veces más fácil que en la consola. Si el simulador recorre todas las rutas sin errores, el motor de PS1 solo tiene que ejecutar fielmente.

### Arquitectura del convertidor

```
.rpy ──► [Lexer/Parser] ──► AST ──► [Resolución] ──► IR ──► [Generador] ──► .VNB
                                       │
                         nombres de imágenes → IDs
                         personajes → IDs
                         variables → índices
                         etiquetas → direcciones
                         textos → tabla de cadenas en español
```

### Tareas
1. **Parser de Ren'Py** (solo el subconjunto que usa el juego, según la auditoría). Maneja indentación, bloques, cadenas, etiquetas de texto.
   - Alternativa a evaluar: usar el propio parser de Ren'Py (desde el SDK de Ren'Py) para obtener el AST oficial y evitar errores de interpretación. Decidir en la primera sesión de esta fase.
2. **Traductor de expresiones:** las condiciones tipo `if fang_points >= 3 and not saw_ending:` se convierten a una mini-pila de operaciones (ver Apéndice B).
3. **Traducción manual del Python** clasificado en la Fase 1 como "a mano": se escribe su equivalente en el formato del motor y se documenta.
4. **Tabla de cadenas en español:** la estructura sale de los `.rpy` en inglés, y cada diálogo, opción y nombre se reemplaza por su versión de la carpeta de español en `game/tl/` (Ren'Py une cada línea con su traducción mediante un identificador; usar ese mismo identificador). Si una línea no tiene traducción, el compilador **falla con un error** que dice cuál es, en lugar de meter el texto en inglés sin avisar. Las traducciones hechas a mano para el port van en `tools/script_compiler/traducciones_extra.txt`.
5. **Pre-procesado de texto:** convertir etiquetas de texto a códigos de control simples; partir líneas según el ancho de la caja de diálogo y la fuente elegida (esto se calcula en la PC, no en la PS1).
   - Cada línea de diálogo recibe un **número único y estable** (su ID de texto). Ese número es el bit que se marca como "leído" para la función de saltar. Si el script se recompila, los números no deben cambiar de lugar (se asignan en orden del script original), para no estropear el progreso guardado.
   - **Material picante:** se resuelve aquí como siempre activado; las ramas `if` que dependen de esa variable se reducen a su lado activo.
6. **Generador de bytecode** según `docs/bytecode.md`, un archivo por capítulo.
7. **Desensamblador:** convierte `.VNB` de vuelta a texto legible (vital para depurar).
8. **Simulador en Python** que ejecuta el bytecode como lo haría la PS1:
   - Modo interactivo (jugar en la terminal).
   - Modo exploración automática: recorre **todas** las combinaciones de decisiones (con poda de estados repetidos) y reporta:
     - etiquetas alcanzadas / no alcanzadas,
     - finales alcanzados,
     - errores (imagen inexistente, variable sin definir, salto inválido, texto demasiado largo).
   - **Progreso entre partidas:** el simulador también lleva el "progreso" (finales vistos, galería, texto leído) como lo hará la memory card, y comprueba que:
     - al terminar todas las rutas se desbloquean los capítulos extra, y que los capítulos extra también se recorren completos;
     - toda imagen de la galería se puede desbloquear en alguna ruta;
     - con todo leído, el modo saltar llega de una decisión a la siguiente sin detenerse.
9. Pruebas comparativas: para varias rutas, comparar la secuencia de diálogos del simulador contra la de Ren'Py real (jugando en Ren'Py con auto-avance y registro, o comparando con el orden del script).

### Entregables
- `tools/script_compiler/`, `tools/simulator/`, tests en `tests/`.
- `build/data/SCRIPT/*.VNB` y `build/data/TEXT_ES.BIN`.
- `build/reports/cobertura.md`: reporte del simulador.

### Terminado cuando
- [ ] El 100% de los `.rpy` compila sin advertencias sin resolver.
- [ ] El simulador alcanza **todas** las etiquetas y **todos** los finales.
- [ ] Ninguna línea de texto excede la caja de diálogo.
- [ ] El 100% de las líneas que se muestran están en español (cero textos en inglés sin traducir).
- [ ] Tests automáticos pasan.

### Prompt sugerido
```
Lee CLAUDE.md, PLAN.md (Fase 3), docs/auditoria.md y docs/bytecode.md.
Implementa el convertidor en tools/script_compiler/ por etapas: primero el parser
con tests usando 3 archivos .rpy reales, luego resolución de nombres, luego el
generador. No avances de etapa sin que los tests de la anterior pasen.
```
```
Implementa tools/simulator/ que ejecute los .VNB. Agrega el modo de exploración
automática de todas las rutas y genera build/reports/cobertura.md.
```

---

## Fase 4 — Pipeline de imágenes (con vista CRT)

**Objetivo:** convertir todo el arte a formato PS1 con la mejor calidad posible, pensada para verse bien en CRT.

### Pasos del pipeline por imagen

```
PNG/WEBP original
   │ 1. Recorte de bordes transparentes (ahorra VRAM)
   │ 2. Escalado a resolución PS1 con filtro de buena calidad (Lanczos)
   │ 3. Tratamiento de bordes (personajes):
   │      - alfa > umbral → píxel visible; si no → transparente (0x0000)
   │      - "matte": mezclar el borde con un color neutro para evitar halos
   │ 4. Reducción de color:
   │      - fondos: 15 bits o paleta 256 según Fase 2
   │      - personajes: paleta propia de 256 (o compartida por expresiones)
   │      - con tramado (ordered dithering o error diffusion, se prueba cuál
   │        se ve mejor en CRT)
   │ 5. Evitar que un color visible quede como 0x0000 (sería transparente)
   │ 6. Partir en tiles de máximo 256×256
   │ 7. Exportar a TIM (o formato propio) + metadatos (tamaño, offsets, tiles)
   ▼
build/data/IMG/xxx.TIM + build/data/IMG/index.bin
```

### Tareas
1. Clasificar cada imagen: fondo, personaje (con expresiones), CG, UI.
2. Implementar el pipeline en `tools/images/`.
3. **Expresiones de personajes:** si el juego compone cuerpo + cara, decidir si se pre-componen en la PC (más simple, más espacio) o se dibujan en capas en la PS1 (menos espacio, más trabajo del motor). Lo decide la auditoría.
4. **Vista previa CRT** (`tools/images/crt_preview.py`): genera una imagen de cómo se verá en una tele CRT (desenfoque horizontal leve, líneas de escaneo, máscara de fósforo, brillo). **Solo para comparar, nunca se mete al juego.**
5. Hoja de contacto: una página HTML o imagen con original / convertido / vista CRT lado a lado para revisar todo el arte rápido.
6. Verificar que cada imagen convertida cabe en el espacio de VRAM asignado.
7. **Imágenes de los menús:** el logo de Snoot Game para el título (sobre negro, sin fondo ilustrado), el icono de 16×16 de la memory card y el candado de *Capítulos extra*.
8. **Galería:** marcar en `IMG/index.bin` qué imágenes son de galería y su número de bit. Si se hacen miniaturas (opcional), generarlas aquí.
9. Con el material picante fijo, **no convertir** las versiones alternativas que solo se usaban con esa opción apagada.

### Entregables
- `build/data/IMG/*` listo para el CD.
- `build/reports/arte.html` (hoja de contacto).

### Terminado cuando
- [ ] El 100% de las imágenes referenciadas por el script existe convertida (lo valida el simulador).
- [ ] Ninguna excede su presupuesto de VRAM.
- [ ] Revisión visual en la hoja de contacto aprobada por ti.

### Prompt sugerido
```
Lee CLAUDE.md, PLAN.md (Fase 4) y docs/decisiones.md. Implementa el pipeline de
imágenes en tools/images/ empezando por 5 fondos y 2 personajes de prueba.
Genera también la vista previa CRT y una hoja de contacto HTML comparando
original, convertido y CRT. Prueba dos tipos de tramado y muéstrame ambos.
```

---

## Fase 5 — Pipeline de audio

**Objetivo:** música y efectos en formatos nativos de PS1.

### Tareas
1. **Música → XA** con psxavenc. Probar calidad a 37.8 kHz y 18.9 kHz (estéreo/mono) y elegir según espacio en disco y cómo suena.
2. **Bucles:** la música de Ren'Py suele repetirse; definir cómo se repite en XA (reinicio del stream al terminar).
3. **Efectos → VAG** (cargados en la RAM de sonido, máx. 512 KB en total; se cargan por capítulo si no caben todos).
4. Normalizar volumen entre pistas.
5. Tabla de audio: ID → archivo, sector de inicio, duración, si hace bucle.
6. Si hubiera voces: evaluar si caben en el presupuesto del disco; si no, se descartan (la meta es un solo CD).

### Entregables
- `build/data/BGM/*.XA`, `build/data/SFX/*.VAG`, `build/data/audio_index.bin`.
- `docs/decisiones.md` actualizado con calidad elegida y espacio total usado.

### Terminado cuando
- [ ] Todas las pistas referenciadas existen convertidas.
- [ ] El total de datos + audio cabe en un solo CD con ≥ 15% libre.

---

## Fase 6 — Motor PS1: base

**Objetivo:** el "esqueleto" del motor: mostrar imágenes, texto y leer el control y el CD.

### Tareas (en este orden, probando cada una en el emulador)
1. **Video:** inicializar GPU, modo de pantalla elegido, doble buffer, limpiar pantalla.
2. **Lectura de CD:** abrir archivos por nombre (o por tabla de sectores precalculada), leer a RAM.
3. **Carga de texturas:** de RAM a VRAM en la posición del mapa de memoria.
4. **Dibujar un fondo** (con sus tiles) en pantalla.
5. **Dibujar un personaje** con transparencia encima del fondo.
6. **Fuente y caja de texto:** dibujar texto con acentos, la caja de diálogo y el nombre del personaje.
7. **Efecto máquina de escribir** (letra por letra) y "presiona X para continuar".
8. **Control:** leer botones. Esquema propuesto:

   | Botón | Durante el juego | En menús |
   |---|---|---|
   | **X** | Avanzar texto / elegir en una decisión | Aceptar |
   | **O** | — | Regresar |
   | **Cruceta** | Moverse entre las opciones de una decisión | Moverse (izquierda/derecha cambia volumen y cambia de imagen en la galería) |
   | **R1** | Activar / desactivar **saltar texto leído** | — |
   | **Start** | Abrir el menú de pausa | Cerrar el menú de pausa |
   | **Cuadrado** (opcional) | Ocultar la caja de texto para ver la imagen | — |
9. Pantalla de depuración (activable): FPS, RAM libre, escena actual.

### Entregables
- `engine/` compilando a `SNOOT.EXE`.
- Demo: un fondo + personaje + 3 líneas de diálogo reales que avanzan con X.

### Terminado cuando
- [ ] La demo corre estable en DuckStation y PCSX-Redux a 60 (o 50) cuadros por segundo.
- [ ] Texto en español con acentos, ñ, ¿ y ¡ se ve correcto.
- [ ] (Si tienes consola) La demo se probó al menos una vez en hardware real (ver opciones en la Fase 11). Detectar ahora un problema de consola real es mucho más barato que al final.

### Prompt sugerido
```
Lee CLAUDE.md, PLAN.md (Fase 6), docs/decisiones.md y docs/presupuesto-memoria.md.
Implementa la tarea 1 de la Fase 6 en engine/ basándote en los ejemplos oficiales
de PSn00bSDK. Haz solo esa tarea, compílala y dime qué debo ver en el emulador.
```
(Repetir para cada tarea.)

---

## Fase 7 — Motor PS1: intérprete y escenas

**Objetivo:** que el motor ejecute el bytecode real del juego.

### Tareas
1. **Máquina virtual (`vm.c`):** bucle que lee instrucciones y las ejecuta; debe poder "pausarse" esperando un botón o una carga y continuar en el siguiente cuadro.
2. Instrucciones de escena: fondo, mostrar/ocultar personaje, posición, capas.
3. Instrucciones de texto: diálogo con hablante, narración.
4. **Menús de decisión:** mostrar opciones (filtrando las que tengan condición falsa), elegir con el control, saltar.
5. Variables, condiciones y saltos (`jump`, `call`, `return`).
6. **Cambio de capítulo:** cargar el siguiente `.VNB` del CD cuando el script lo indique.
7. **Gestor de recursos:** saber qué imágenes están en VRAM, cargar las que faltan, liberar las que ya no se usan.
8. **Prueba cruzada con el simulador:** el motor puede imprimir (por consola de depuración del emulador) el mismo registro que el simulador; se comparan para una ruta completa.
9. **Progreso del jugador:** al mostrar una línea se marca su bit de "leída"; al llegar a un `ENDING` se marca el final; al mostrar una imagen que pertenece a la galería se marca como vista (el convertidor deja esa información en el índice de imágenes).
10. **Modo saltar (R1):**
    - Mientras está activo se ve un indicador pequeño en una esquina ("▶▶ Saltando").
    - Las líneas ya leídas pasan casi al instante, sin efecto de máquina de escribir; las transiciones y pausas se omiten; los efectos de sonido se silencian.
    - **Se detiene** en la primera línea **no leída**, al llegar a un final o al cambiar de capítulo, o si el jugador presiona R1 o X.
    - **En una decisión** se detiene para que el jugador elija; al elegir, **sigue saltando solo** si lo que viene ya estaba leído. Así, para sacar otra ruta basta con activar R1 una vez y elegir distinto en las decisiones.
    - **Clave para la velocidad en PS1:** durante el salto no se cargan del CD las imágenes ni la música intermedias. El motor solo va actualizando *qué debería verse y oírse*, y lo carga una sola vez al detenerse. Si no, el lector de CD haría el salto lentísimo.

### Terminado cuando
- [ ] Se puede jugar el primer capítulo completo en el emulador.
- [ ] El modo saltar se detiene exactamente en el primer texto no leído y en las decisiones.
- [ ] El registro del motor y el del simulador coinciden en al menos 3 rutas distintas.

---

## Fase 8 — Motor PS1: audio, transiciones, guardado y menús

### Tareas
1. **Música XA:** reproducir, detener, fundido de volumen, bucles.
2. **Efectos VAG:** carga a SPU y reproducción.
3. **Estrategia CD música/datos:** implementar lo decidido en la Fase 2 para que las cargas no corten la música (o que lo hagan de forma elegante).
4. **Transiciones:** fundido a negro, fundido entre fondos (aproximado con semitransparencia por pasos), aparición de personajes.
5. **Arranque:** pantalla breve de créditos (Cavemanon y el port) → se lee el archivo de la memory card a RAM (si existe) → pantalla de título.
6. **Pantalla de título** (se diseña de cero; no imita el menú de Ren'Py):
   ```
   ┌──────────────────────────────────┐
   │            fondo negro           │
   │                                  │
   │        [ LOGO SNOOT GAME ]       │  ← el logo del juego original
   │                                  │
   │            Comenzar              │
   │            Continuar             │  ← en gris si no hay ningún guardado
   │         🔒 Capítulos extra       │  ← en gris con candado hasta terminar todas las rutas
   │            Galería               │
   │            Opciones              │
   │                                  │
   └──────────────────────────────────┘
   ```
   - **Sin música** y sin fondo ilustrado: solo negro, logo y texto. Carga al instante y deja libre el lector de CD.
   - **Comenzar:** empieza la historia desde el principio. No borra ningún guardado.
   - **Continuar:** abre la lista de las 3 ranuras con la **más reciente ya seleccionada**: un X y estás jugando. Si no hay memory card o no hay guardados, aparece en gris (y si se elige, un aviso corto explica por qué).
   - **Capítulos extra:** bloqueado hasta ver **todos los finales de las rutas principales** (la lista de finales sale de la auditoría). Mientras está bloqueado, al elegirlo muestra el avance, por ejemplo: "Termina todas las rutas para desbloquear (3/5 finales)". Ya desbloqueado, muestra la lista de capítulos extra y cada uno empieza desde su inicio.
   - **Galería:** ver el punto 9.
   - **Opciones:** ver el punto 8.
   - No hay *Salir*: en consola se apaga y ya.
7. **Menú de pausa** (botón **Start** durante el juego; la escena queda congelada detrás, oscurecida):
   - Seguir
   - Saltar texto leído (activa el modo saltar y cierra el menú; lo mismo que R1, pero así el jugador sabe que existe)
   - Guardar
   - Cargar
   - Opciones
   - Salir al título (con confirmación: "¿Salir? Lo no guardado se perderá")
8. **Opciones** (las mismas desde el título y desde la pausa): volumen de música y volumen de efectos (barras de 0 a 10; al moverlas se escucha el cambio), y *Volver*. Nada más.
9. **Galería:**
   - Visor de una imagen a la vez, a pantalla completa. Izquierda/derecha para pasar de imagen, contador "5 / 32", O para volver.
   - Las imágenes no vistas aparecen como un recuadro oscuro con "???".
   - Se desbloquean al verlas en cualquier partida y quedan desbloqueadas para siempre (se guardan en el progreso).
   - Opcional si sobra tiempo: pantalla de miniaturas en cuadrícula antes del visor (las miniaturas se generan en la PC y van en el CD).
10. **Pantalla de Guardar / Cargar (3 ranuras):**
    ```
    ┌────────────────────────────────────────────┐
    │ ▶ Ranura 1   Capítulo 3   Tiempo 02:15     │  ← la más reciente marcada
    │   Ranura 2   Capítulo 1   Tiempo 00:40     │
    │   Ranura 3   — vacía —                     │
    └────────────────────────────────────────────┘
    ```
    - Cada ranura muestra capítulo y tiempo de juego. Opcional: una miniatura del fondo donde se guardó (precalculada en la PC y leída del CD; no gasta memory card).
    - Se puede guardar cuando el juego espera al jugador (en un diálogo o en una decisión); el guardado apunta al inicio de esa línea o decisión. **Truco para sacar rutas:** guardar justo en una decisión y luego cargar para elegir otra.
    - Guardar sobre una ranura ocupada pide confirmación: "¿Sobrescribir?" Sí / No.
    - Mientras guarda: "Guardando… no retires la memory card".
    - Errores con mensaje claro: no hay memory card, memory card llena (se necesita 1 bloque libre), guardado dañado o de una versión vieja.
    - El formato del archivo es el de la Fase 2 ("Propuesta del archivo de memory card"). Icono propio de 16×16; título visible en el administrador de la consola **sin acentos** ("SNOOT GAME").
11. **Guardado automático del progreso** al llegar a cada final y al salir al título (ver Fase 2), con el aviso "Guardando progreso…". Si no hay memory card, se avisa una vez y el juego sigue.
12. Pantalla de "cargando" discreta si una carga tarda más de ~0.5 s.
13. **Extras opcionales** (solo si sobra tiempo, en este orden): ocultar la caja de texto con Cuadrado, miniaturas en galería y en ranuras, historial de diálogos, modo automático.

### Terminado cuando
- [ ] Guardar y Cargar funcionan en las 3 ranuras, desde cualquier punto donde se permite guardar, y restauran la escena idéntica.
- [ ] Continuar abre la ranura más reciente; aparece en gris sin memory card o sin guardados.
- [ ] Capítulos extra se desbloquea exactamente al ver todos los finales de las rutas principales, y el desbloqueo sobrevive a apagar la consola.
- [ ] La galería muestra solo lo visto, y lo visto sobrevive a apagar la consola.
- [ ] Los errores de memory card muestran su mensaje y no cuelgan el juego.
- [ ] La música no se corta de forma molesta en cambios de escena normales.
- [ ] Los volúmenes de música y efectos funcionan y se recuerdan.

---

## Fase 9 — Construcción del CD y build automático

**Objetivo:** un solo comando genera el juego completo.

### Tareas
1. `tools/disc/make_xml.py`: genera `disc/snootgame.xml` para mkpsxiso con todos los archivos (datos en modo normal, música en modo XA).
2. Generar tabla de sectores de los archivos (si el motor la usa para cargas rápidas).
3. `build.py` (en Python para que funcione igual en Windows y Linux; se corre con `python build.py`):
   ```
   1. verificar entorno (reutiliza tools/check_env.py)
   2. convertir scripts  → simulador en modo exploración (si falla, se detiene)
   3. convertir imágenes
   4. convertir audio
   5. compilar motor
   6. generar XML y construir .bin/.cue
   7. imprimir resumen: tamaño total, espacio libre en CD, tiempo de build
   ```
4. Builds incrementales (no reconvertir lo que no cambió) para no esperar de más. Comparar por *hash* del contenido, no por fecha de modificación (en Windows las fechas cambian al copiar o extraer ZIPs).
5. Conversiones en paralelo (varias imágenes a la vez con `concurrent.futures`) para aprovechar todos los núcleos de la PC.
6. Licencia/región del disco: configurar mkpsxiso según su documentación para que arranque en emulador y consola.
7. Opciones útiles: `python build.py --solo-scripts`, `--solo-motor`, `--limpio` (borrar `build/` y empezar de cero).

### Terminado cuando
- [ ] `python build.py` desde cero genera un `.bin/.cue` jugable.
- [ ] Si algo falla, el script se detiene con un mensaje claro.

---

## Fase 10 — Pruebas y control de calidad

### Tareas
1. **Cobertura automática:** el simulador confirma todas las rutas en cada build.
2. **Pruebas automáticas en emulador** (opcional pero muy útil): usar el scripting de PCSX-Redux para "presionar botones" y seguir una ruta completa sin intervención, verificando que no se cuelga.
3. **Pruebas manuales:** jugar cada ruta hasta su final en DuckStation. Lista de verificación en `docs/qa.md`:
   - [ ] Ruta X completa, final alcanzado
   - [ ] Guardar a mitad de ruta, apagar, y Continuar desde el título
   - [ ] Guardar en una decisión y Continuar (la decisión vuelve a aparecer)
   - [ ] Sin memory card / memory card llena: mensajes correctos
   - [ ] Sin textos en inglés
   - [ ] Saltar (R1) en una segunda partida: pasa lo leído, se detiene en texto nuevo y en decisiones, y sigue solo después de elegir
   - [ ] Galería: cada imagen se desbloquea al verla y sigue desbloqueada tras apagar
   - [ ] Capítulos extra: bloqueado con el contador correcto; se desbloquea con el último final; se juegan completos
   - [ ] Título: Continuar abre la ranura más reciente
   - [ ] Sin texto cortado o desbordado
   - [ ] Sin imágenes faltantes o corruptas
   - [ ] Música correcta en cada escena
4. **Pruebas de estrés:** saltar texto rápido por todo el juego, abrir/cerrar menús muchas veces, guardar/cargar repetidamente (buscar fugas de memoria).
5. **Revisión visual con filtro CRT** en DuckStation.
6. Registro de errores en `docs/bugs.md` (qué pasa, cómo reproducirlo, estado).

### Terminado cuando
- [ ] Todas las rutas jugadas manualmente al menos una vez.
- [ ] Cero errores críticos abiertos (cuelgues, rutas bloqueadas, guardados corruptos).

---

## Fase 11 — Pulido, hardware real y distribución

### Tareas
1. **Hardware real:** opciones para arrancar el juego en una PS1:
   - unidad óptica emulada (ODE) como XStation o PSIO,
   - CD-R con consola modificada (modchip),
   - carga por cable serial con Unirom (útil para pruebas rápidas),
   - FreePSXBoot (exploit de memory card).
2. Verificar en hardware real: tiempos de carga, estabilidad del CD, calidad en tele CRT con cable compuesto y S-Video.
3. Ajustar arte si en CRT real algo se ve distinto a la vista previa.
4. Créditos que reconozcan a Cavemanon y al port. Como el menú no tiene opción de créditos, se muestran al terminar cada final y en una pantalla breve al arrancar (antes del título).
5. README final: cómo compilar, cómo jugar, limitaciones conocidas.
6. **Distribución:** según la web oficial, el código de Snoot Game es **AGPLv3** y los assets (arte, música) son **CC-BY-SA 4.0**, ambas licencias libres que permiten redistribuir obras derivadas, con condiciones. Lo que eso implica en la práctica (verificar con el archivo `LICENSE` del repositorio; esto no es asesoría legal):
   - **Atribución:** créditos claros a Cavemanon y enlace al juego original, dentro del juego y en el README.
   - **Compartir igual:** el arte y la música convertidos se publican también bajo CC-BY-SA 4.0.
   - **Código:** el bytecode viene de los scripts AGPL, así que lo más simple es publicar el motor y las herramientas del port bajo AGPLv3 y con su código fuente disponible.
   - Con eso se podría compartir tanto el **código del port** como la **imagen de CD**; aun así, la opción más conservadora sigue siendo publicar las herramientas y que cada quien genere su CD.

---

## 18. Riesgos y planes B

| Riesgo | Probabilidad | Impacto | Plan B |
|---|---|---|---|
| El juego usa Python complejo difícil de traducir | Media | Alto | Se detecta en Fase 1; se traduce a mano caso por caso o se agrega una instrucción especial al bytecode. |
| La música XA ocupa el lector del CD y no se pueden cargar imágenes sin cortarla | Alta | Medio | a) precargar recursos del siguiente bloque de escenas mientras hay texto; b) intercalar datos dentro del stream XA; c) breve fundido de música durante cargas; d) música corta en bucle desde la RAM de sonido en escenas con muchas cargas. |
| Las imágenes no se ven bien a baja resolución | Media | Medio | Probar 512×240, fondos en 15 bits, MDEC para fondos, retoques manuales a las imágenes más importantes. |
| No cabe en un CD | Baja | Medio | Según el presupuesto de la Fase 2 cabe holgado. Si la auditoría sorprende: música a 18.9 kHz, luego comprimir imágenes. |
| La traducción al español está incompleta | Baja-media | Medio | La auditoría lo mide; las líneas faltantes se traducen a mano en `traducciones_extra.txt` y el compilador no deja pasar ninguna sin traducir. |
| El texto en español es más largo y no cabe en la caja | Media | Bajo | Fuente de ancho variable y paginado automático en el convertidor. |
| Texto demasiado largo para la caja | Media | Bajo | Partir en varias páginas automáticamente (lo hace el convertidor). |
| Errores difíciles de depurar en el motor | Media | Medio | Depurador de PCSX-Redux, registro comparado con el simulador, modo de depuración en pantalla. |
| Funciona en emulador pero no en consola real | Media | Medio | Primera prueba en hardware real al terminar la Fase 6, y de nuevo en la Fase 8; DuckStation en modo preciso. |
| Errores por codificación o rutas en Windows (acentos rotos, archivos no encontrados) | Media | Bajo | Reglas de la sección 4.4 (UTF-8, `pathlib`, ruta corta) y tests que lean `.rpy` con acentos reales. |
| Una herramienta no tiene versión para Windows o falla | Baja | Medio | Usarla desde WSL2 sobre la misma carpeta del proyecto. |
| Pérdida de motivación por proyecto largo | Media | Alto | Fases con resultados visibles; la demo de la Fase 6 da una victoria temprana. |

---

## Apéndice A — Plantilla de CLAUDE.md

Copia esto como `CLAUDE.md` en la raíz del repositorio:

```markdown
# Proyecto: Port de Snoot Game (Ren'Py) a PlayStation 1

## Qué es
Convertimos una novela visual de Ren'Py a un formato que un motor propio en C
ejecuta en PS1. La PC hace todo el trabajo pesado (convertidores en Python);
la PS1 solo ejecuta.

## Alcance (no lo amplíes sin preguntar)
- Solo español (traducción oficial de game/tl/). Nada de selector de idioma.
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
- Comentarios y documentación en español.

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
- PC con Windows 11 (64 bits), proyecto en E:\dev\snoot-ps1
- Python 3.12 (venv en .venv), Git, CMake, Ninja, ffmpeg, Graphviz
- PSn00bSDK en C:\PSn00bSDK (incluye mipsel-none-elf-gcc y mkpsxiso), psxavenc
- Emuladores: DuckStation (jugar, filtro CRT), PCSX-Redux (depurar), no$psx (opcional)
- Plan B para herramientas que fallen en Windows: WSL2 (Ubuntu)
```

---

## Apéndice B — Borrador de la especificación del bytecode

> Borrador inicial. La versión final se escribe en `docs/bytecode.md` durante la Fase 2, ajustada a lo que encuentre la auditoría.

### Estructura de un archivo `.VNB`

```
Cabecera (16 bytes)
  0x00  "VNB1"        identificador y versión
  0x04  u16           número de capítulo
  0x06  u16           número de etiquetas exportadas
  0x08  u32           tamaño del código
  0x0C  u32           reservado
Tabla de etiquetas    (id u16, offset u32) × N
Código                instrucciones
```

Todos los números en *little-endian* (como la PS1).

### Instrucciones (borrador)

| Código | Nombre | Argumentos | Equivale en Ren'Py |
|---|---|---|---|
| 0x01 | `SAY` | hablante u8, texto u16 | `f "Hola"` |
| 0x02 | `NARRATE` | texto u16 | `"Narración"` |
| 0x03 | `SCENE` | imagen u16, transición u8 | `scene bg aula with dissolve` |
| 0x04 | `SHOW` | personaje u16, posición u8, capa u8 | `show fang feliz at left` |
| 0x05 | `HIDE` | personaje u16 | `hide fang` |
| 0x06 | `TRANSITION` | tipo u8, duración u8 | `with fade` |
| 0x07 | `MUSIC_PLAY` | pista u16, fundido u8, bucle u8 | `play music ...` |
| 0x08 | `MUSIC_STOP` | fundido u8 | `stop music fadeout 1.0` |
| 0x09 | `SFX_PLAY` | efecto u16 | `play sound ...` |
| 0x0A | `PAUSE` | cuadros u16 (0 = esperar botón) | `pause 1.0` |
| 0x10 | `MENU` | n u8, luego n × (texto u16, condición u16, destino u32) | `menu:` |
| 0x11 | `JUMP` | destino u32 | `jump etiqueta` |
| 0x12 | `JUMP_IF_FALSE` | destino u32 (usa resultado de la pila) | `if ...:` |
| 0x13 | `CALL` | destino u32 | `call etiqueta` |
| 0x14 | `RETURN` | — | `return` |
| 0x15 | `LOAD_CHAPTER` | capítulo u16, etiqueta u16 | salto a otro archivo |
| 0x20 | `SET_VAR` | var u8, valor i16 | `$ x = 3` |
| 0x21 | `ADD_VAR` | var u8, valor i16 | `$ x += 1` |
| 0x22 | `SET_FLAG` | bandera u16, valor u8 | `$ visto = True` |
| 0x30 | `PUSH_VAR` | var u8 | expresiones |
| 0x31 | `PUSH_CONST` | valor i16 | expresiones |
| 0x32 | `PUSH_FLAG` | bandera u16 | expresiones |
| 0x33 | `OP` | operador u8 (==, !=, <, <=, >, >=, and, or, not, +, -) | expresiones |
| 0x40 | `ENDING` | id u8 | registrar final alcanzado (marca el bit en el progreso y dispara el guardado automático del progreso) |
| 0xFE | `DEBUG` | id u16 | marca para comparar con simulador |
| 0xFF | `END` | — | fin |

### Tablas auxiliares
- `TEXT_ES.BIN`: tabla de offsets + cadenas en español (ya partidas en líneas/páginas, con códigos de control para pausas, cursiva, etc.). Incluye también los textos de la interfaz (Comenzar, Continuar, Galería, mensajes de memory card, etc.). Un futuro `TEXT_EN.BIN` usaría los mismos IDs.
- `IMG/index.bin`: id → archivo, tamaño, tiles, paleta, offsets de dibujo.
- `audio_index.bin`: id → archivo/sector, duración, bucle.
- `characters.bin`: id de hablante → nombre en español, color del nombre.

### Pendientes conocidos del borrador (resolver en la Fase 2)
- **Variables de texto:** el borrador solo maneja números y banderas. Si la auditoría encuentra variables `str` (por ejemplo, un nombre o una ruta elegida), se convierten en números con una tabla (enum) en la PC.
- **Datos persistentes:** definir instrucciones aparte (por ejemplo `SET_PERSIST` / `PUSH_PERSIST`) para no mezclarlos con las variables de la partida.
- **Texto leído:** no necesita instrucción nueva; el ID de texto de `SAY`/`NARRATE` es el número de bit que se marca como leído.
- **Galería:** tampoco; el índice de imágenes (`IMG/index.bin`) indica qué imágenes son de galería y qué número de bit marcan al mostrarse con `SCENE`/`SHOW`.
- **Material picante:** no llega al bytecode; el compilador lo resuelve como siempre activado.
- **Límites:** `var u8` permite 256 variables y la pila de `CALL` necesita un tamaño máximo; fijar ambos con los números reales de la auditoría.

---

## Apéndice C — Glosario

- **Bytecode:** instrucciones compactas en binario que el motor lee y ejecuta, como una "partitura" del juego.
- **CLUT:** paleta de colores de una textura de 4 u 8 bits.
- **CRT:** televisión de tubo; suaviza la imagen de forma natural.
- **DMA:** mecanismo para copiar datos rápido (por ejemplo, de RAM a VRAM) sin usar la CPU.
- **Framebuffer:** zona de la VRAM con la imagen que se ve en pantalla.
- **IR:** representación intermedia; paso entre el código Ren'Py y el bytecode.
- **MDEC:** chip de la PS1 que descomprime imágenes tipo JPEG.
- **mkpsxiso:** herramienta que crea la imagen de CD de PS1.
- **psxavenc:** herramienta que convierte audio a formatos de PS1.
- **PSn00bSDK:** kit de desarrollo libre para programar la PS1 en C.
- **SPU:** chip de sonido de la PS1.
- **Tile:** pedazo de una imagen grande, máximo 256×256 en PS1.
- **TIM:** formato nativo de imágenes/texturas de la PS1.
- **Tramado (dithering):** patrón de puntos que simula más colores; en CRT parece degradado.
- **VAG:** formato de efectos de sonido de PS1.
- **VRAM:** memoria de video (1 MB en PS1).
- **winget:** instalador de programas por línea de comandos incluido en Windows 10/11.
- **WSL2:** sistema para correr Linux dentro de Windows; aquí es solo plan B.
- **XA:** formato de audio en streaming desde el CD de la PS1.

---

## Orden de arranque recomendado (resumen)

1. Fase 0 completa → ya tienes un "hola mundo" en el emulador.
2. Fase 1 → sabes exactamente a qué te enfrentas.
3. Fase 2 → decisiones y contrato listos.
4. Fases 3, 4 y 5 en la PC (se pueden alternar).
5. Fases 6, 7 y 8 en la PS1 (en orden).
6. Fases 9, 10 y 11 para cerrar.

**Primera victoria visible:** el final de la Fase 6 (un fondo real de Snoot Game con diálogo en la PS1). Apúntale a llegar ahí lo antes posible.
