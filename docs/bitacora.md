# Bitácora

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
