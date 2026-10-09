# STATUS

Ultima actualizacion: 2026-10-08

## Fase actual: 2 - Decisiones tecnicas y especificacion (por empezar)

## Hecho
### Fase 0 - Entorno (terminada)
- [x] Python 3.12, Graphviz, git, cmake, ninja, ffmpeg instalados
- [x] PSn00bSDK, mkpsxiso, psxavenc funcionando
- [x] Repositorio C:\dev\snoot-ps1 con estructura, CLAUDE.md, PLAN.md, .gitattributes, .gitignore
- [x] venv Python 3.12 con pillow, numpy, pytest
- [x] tools/check_env.py: 17 verificaciones en OK
- [x] Juego copiado a original/
- [x] Exclusion de Defender para C:\dev
- [x] Hola mundo PS1 verificado en DuckStation y PCSX-Redux (BIOS real)

### Fase 1 - Auditoria (terminada, pendiente de tu revision)
- [x] tools/audit/inventario.py (instrucciones, personajes, variables, persistent, Python, screens)
- [x] 0 instrucciones de Ren'Py desconocidas
- [x] Cobertura de traduccion tl/es (14,694 bloques, 0 vacios) y caracteres usados
- [x] Inventario de imagenes (589) y audio (120 min)
- [x] Grafo de la historia (build/audit/grafo_historia.svg) y de etiquetas
- [x] Material picante (persistent.lewd), galeria (203), capitulos extra, finales, version Ren'Py 8.3.7, licencia
- [x] Python clasificado: 190 automatico, 28 a mano, 22 descartable, 5 revisar
- [x] docs/auditoria.md + docs/auditoria_manual.md + build/audit/inventario.json
- [x] 10 tests pasando
- [x] Resumen de partes dificiles (al final de docs/auditoria.md)

## Decisiones tomadas (ver docs/decisiones.md)
- [x] D1: capitulos extra con la logica progresiva del original
- [x] D2: musica en XA, ambientes en VAG cortos en bucle
- [x] D3: video `fang tail.webm` convertido a animacion por fotogramas (8-16 fotogramas en bucle)

## Fase 2 en curso
- [ ] Prototipo de resolucion y formato de fondos
- [ ] Prueba tecnica XA + carga de datos del CD
- [ ] Fuente, compresion, formato de memory card
- [ ] docs/bytecode.md, docs/presupuesto-memoria.md

## Pendiente (fases siguientes)
- [ ] Fase 2 - Decisiones tecnicas y especificacion (bytecode, VRAM/RAM, memory card)
- [ ] Fase 3 - Convertidor de scripts y simulador
- [ ] Fase 4 - Pipeline de imagenes
- [ ] Fase 5 - Pipeline de audio
- [ ] Fase 6 - Motor PS1: base
- [ ] Fase 7 - Motor PS1: interprete y escenas
- [ ] Fase 8 - Motor PS1: audio, transiciones, guardado y menus
- [ ] Fase 9 - Construccion del CD y build automatico
- [ ] Fase 10 - Pruebas y control de calidad
- [ ] Fase 11 - Pulido, hardware real y distribucion

## Notas
- mkpsxiso 2.10 no admite rutas absolutas de Windows en el XML; usar rutas relativas (ver docs/entorno.md).
- PCSX-Redux requiere BIOS real (SCPH1001); con OpenBIOS no arranca el disco.
- Regenerar la auditoria: `python tools/audit/inventario.py` (necesita Graphviz en el PATH).
