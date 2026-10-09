# Bitácora

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
