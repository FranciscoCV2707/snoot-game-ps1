# Bitácora

## 2026-10-09 - Fases 8 y 9, inicio de la 10
Hecho:
- Audio (`engine/src/audio.c`): XA por carriles, ambientes y efectos en la SPU; los efectos de mas de 192 KB se convierten a 11 kHz.
- Transiciones con copia de pantalla en VRAM (`MoveImage2`: `MoveImage` detenia el vblank en PCSX-Redux) y bit de mascara en todo lo dibujado.
- Memory card (`engine/src/save.c`), titulo, pausa, ranuras, opciones, galeria, extras, chat del capitulo 4 y creditos.
- `build.py` (todo en ~1 minuto) y `tools/release.py` (zip para probadores con LEEME).
- Pruebas sin tocar el teclado: `AUTOTEST.BIN` en el disco (botones, capturas, autoplay) + `tools/engine/emutest.py` y `tools/engine/playtest.py` en PCSX-Redux sin interfaz.

Pendiente:
- Escuchar el audio en DuckStation (las pruebas automaticas no oyen).
- Tabla de sectores precalculada y paquetes de carga contiguos (D7), si las cargas resultan lentas.

## 2026-10-09 - Auditoria visual contra Ren'Py
Hecho:
- `tools/audit/capture.py` corre `zz_audit.rpy` en una copia del juego (una instancia a la vez: varias en paralelo chocan con el `persistent` y trabaron la PC). Corridas: base (cap. 1-11), r1-r4 (rutas) y x1-x10 (extras).
- `tools/audit/compare.py` + `ps1_frames.c`: ejecutan la VM y `scene.c` del motor con las mismas decisiones, componen cada cuadro de PS1 y lo comparan con la captura (`report/`, `report.json`, `missing.json`).
- Motor: `scene.c` compartido (orden, aspecto, mezcla de solidos); animaciones ATL reproducidas en el tiempo (curvas, bucles, cambios de imagen), `showCG()` con aparicion y desvanecido, dimmers y destellos blancos con mezcla de la GPU, zoom y tinte estaticos, fondos espejados, grano de pelicula translucido, prioridad de VRAM para el fondo.
- Compilador: `ORDER` para `behind`; el estado ATL se reinicia con `scene`/`hide`; anclas de `xalign`/`xpos` y posicion inicial de los `show` con ATL como Ren'Py; tamano real de imagenes con `im.FactorScale`/`im.Crop`.
- `scene X:` con bloque ATL (zoom, blur, xoffset; extras de RAYmba) se pre-renderiza encuadrado; `xsize`/`ysize`/`size` se toman como zoom y la alineacion usa el tamano ya escalado.
- Resultado: diferencia media por cuadro 0.01-0.04 en todas las corridas; lo que queda por encima de 0.30 son casi siempre capturas de Ren'Py a mitad de una animacion (destellos, Pan, salidas).

Pendiente:
- Ren'Py conserva/reinicia el ATL de forma distinta cuando se cambia la imagen a mitad de una animacion (acuario de 12D: Fang queda en 0.68 en Ren'Py y en 0.8 en la PS1).
- Videollamada del telefono (13C): la composicion de la mano y la pantalla no coincide.
- Dimmer al 40% se aproxima con 50% (mezcla de la GPU).

## 2026-10-08 - Fase 4 (pipeline de imagenes)
Hecho:
- `tools/images/render.py` y `convert.py`: recetas -> IMG1 (8 bits, LZ4), paletas por carpeta, recorte de zona visible, alfa tramado, media resolucion para imagenes enormes.
- El compilador aporta la zona visible de cada sprite, pases de diapositivas, video como 10 fotogramas, camara y mascaras.
- Reportes en `build/reports/imagenes.md` y hojas de contacto en `build/reports/arte/`.

Pendiente:
- Revision del arte por el usuario (hojas de contacto, GIF del video, logo).
- Fase 5 (audio).

## 2026-10-08 - Fase 3 (compilador y simulador)
Hecho:
- `tools/script_compiler/` (parser, imagenes, traducciones, lowering, ATL, ensamblador) y `tools/simulator/` (VM, exploracion, reporte).
- Salidas en `build/data` y `build/reports/cobertura.md`; documentado en `docs/compilador.md`.
- Hallazgos: Ren'Py conserva atributos de imagen entre `scene`/`hide`; `setup_ending()` se ejecuta dentro del capitulo 11; hasta 11 sprites simultaneos (extra x6).

Pendiente:
- Fase 4: convertir las 615 imagenes de `meta.json`.
- Pruebas comparativas del orden de dialogo contra Ren'Py real (opcional).

## 2026-10-08 - Fase 2 (decisiones y especificacion)
Hecho:
- Prototipo de resolucion/formato (`tools/images/proto_compare.py`), prueba XA + CD (`experiments/xa_test`), interleaver XA, auditoria de audio.
- Documentos: `decisiones.md` (D1-D11), `bytecode.md` v1, `presupuesto-audio.md`, `presupuesto-memoria.md`.
- Decisiones del usuario: 320x240 con 8 bits, musica mono, video como animacion por fotogramas.

Pendiente:
- Revision del usuario.
- Fase 3.

## 2026-10-08 - Fase 1 (auditoria)
Hecho:
- `tools/audit/inventario.py` genera `docs/auditoria.md`, `build/audit/inventario.json`, `python_blocks.txt` y los grafos SVG.
- Notas manuales en `docs/auditoria_manual.md` (se anexan al documento generado).
- Hallazgos clave: extras progresivos (no "todos los finales"), ambientes largos incompatibles con XA simultaneo, 39 imagenes con texto traducido, IDs de dialogo ya incluidos en el script.

Pendiente:
- Revisar la auditoria contigo y tomar las 3 decisiones de STATUS.md.
- Fase 2.

## 2026-10-08 - Fase 0 (entorno)
Hecho:
- Instalados Python 3.12 y Graphviz; `PYTHONUTF8=1` y git configurados.
- Repositorio creado en `C:\dev\snoot-ps1` con estructura, `CLAUDE.md`, `PLAN.md`, venv y `check_env.py`.
- Juego copiado a `original/`.
- Plantilla de PSn00bSDK compilada a `.bin/.cue` (con el ajuste de rutas descrito en `entorno.md`).

- Defender excluye `C:\dev`; hola mundo verificado en DuckStation y PCSX-Redux (BIOS real).

Pendiente:
- Confirmar `check_env.py` todo en OK en una terminal nueva.
- Fase 1 (auditoría).
