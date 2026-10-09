# STATUS

Ultima actualizacion: 2026-10-08

## Fase actual: 4 hecha (pendiente de tu revision del arte); siguiente: 5 - Pipeline de audio

## Hecho
### Fase 0 - Entorno (terminada)
- [x] Python 3.12, Graphviz, git, cmake, ninja, ffmpeg instalados
- [x] PSn00bSDK, mkpsxiso, psxavenc funcionando
- [x] Repositorio C:\dev\snoot-ps1 con estructura, CLAUDE.md, PLAN.md, .gitattributes, .gitignore
- [x] venv Python 3.12 con pillow, numpy, pytest, lz4
- [x] tools/check_env.py: 17 verificaciones en OK
- [x] Juego copiado a original/
- [x] Exclusion de Defender para C:\dev
- [x] Hola mundo PS1 verificado en DuckStation y PCSX-Redux (BIOS real)

### Fase 1 - Auditoria (terminada)
- [x] tools/audit/inventario.py, docs/auditoria.md (+ manual), inventario.json, grafos SVG
- [x] 0 instrucciones desconocidas; 14,691 dialogos; traduccion al espanol completa; 10 tests

### Fase 2 - Decisiones y especificacion (terminada)
- [x] D1 capitulos extra progresivos, D2 ambientes en VAG, D3 video como animacion por fotogramas
- [x] D4 320x240 (letterbox 320x180), D5 8 bits con dither ordenado y octree, D6 fuente 13 px y caja de 3 lineas
- [x] D7 prueba XA + CD: pausar, cargar por paquetes contiguos, reanudar (hueco ~0.6 s)
- [x] D8 musica XA 37.8 kHz mono con 16 carriles; efectos VAG; disco estimado ~23%
- [x] D9 compresion LZ4; D10 memory card en 1 bloque con 2 copias; D11 presupuesto VRAM/RAM
- [x] docs/bytecode.md v1, docs/presupuesto-audio.md, docs/presupuesto-memoria.md
- [x] Criterios: disco con 77% libre (>=15%), VRAM 29% libre y RAM 25% libre (>=20%), memory card 1 bloque, bytecode cubre toda la auditoria

### Fase 3 - Convertidor de scripts y simulador (terminada)
- [x] Parser de Ren'Py propio (39 de 39 archivos, 14,691 dialogos)
- [x] Tabla de imagenes, traduccion al espanol (0 lineas sin traducir), personajes, posiciones, variables
- [x] Compilador a bytecode VNB (40,579 instrucciones), STORY.VNB, TEXT_ES.BIN, meta.json
- [x] ATL -> fotogramas clave (2,716 animaciones), texto partido en lineas y paginas
- [x] Desensamblador y simulador con exploracion automatica de rutas
- [x] Cobertura: 4 finales, 93 de 93 etiquetas, 9 extras, 203 de 203 de galeria, 0 errores
- [x] Efectos fieles: camera (zoom y desenfoque), AlphaMask, cambios de imagen y sonidos dentro de ATL, transiciones de movimiento y fundido por blanco
- [x] 34 tests; docs/compilador.md y build/reports/cobertura.md

### Fase 4 - Pipeline de imagenes (hecha, pendiente de tu visto bueno al arte)
- [x] 653 imagenes convertidas (232 fondos/CG, 415 sprites con 43 paletas, 6 colores solidos) en 13 segundos
- [x] 21 MB sin comprimir, 9.9 MB en disco (5,046 sectores, 1.5% del CD); sprite medio 19 KB
- [x] Pico de sprites visibles a la vez: 215 KB (limite 320 KB), descontando lo tapado por imagenes opacas
- [x] Camara, mascaras, pases de diapositivas, capas animadas de telefono y video `fang tail` por parches (38 parches a 12 cuadros por segundo, 405 KB en RAM)
- [x] Logo del titulo, candado de extras e icono de memory card; docs/formato-img.md; 38 tests
- [ ] Tu revision: build/reports/arte/fondos_1.html (y sprites_N.html) y build/reports/arte/fang_tail.gif

## Siguiente
- [ ] Tu revision de docs/decisiones.md, docs/bytecode.md y docs/presupuesto-memoria.md
- [ ] Fase 5 - Pipeline de audio

## Pendiente (fases siguientes)
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
- Regenerar la auditoria: `python tools/audit/inventario.py`; audio: `python tools/audio/audit_audio.py`.
- Disco de prueba XA: `python experiments/xa_test/build_test.py`.
- Riesgos resueltos por diseno: D12 huecos de musica (copias seguidas + rebobinado en transiciones), D13 personajes (sin capas; solo se pre-componen fondos con texto y pantallas de telefono), D14 animaciones (zoom/giro con POLY_FT4, tinte con modulacion de color).
- Riesgo que solo se confirma en consola real (Fase 11): duracion real del salto de busqueda del CD.
- Estadisticas de bucles: `python tools/audio/segment_stats.py`.
