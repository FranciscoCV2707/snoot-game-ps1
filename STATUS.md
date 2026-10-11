# STATUS

Ultima actualizacion: 2026-10-10

## Fase actual: 10 (pruebas); disco v0.1 listo para probadores, falta tu prueba con sonido en DuckStation

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

### Fase 5 - Pipeline de audio (hecha, pendiente de que escuches el resultado)
- [x] MUSIC.XA: 63 pistas + 6 mezclas de stems, 16 carriles, 81,088 sectores (24.4% del CD), finales de familia en carril lateral
- [x] 105 efectos y ambientes en SPU-ADPCM (5.8 MB), ambientes en bucle de 6 s con empalme suave
- [x] Compilador: los cruces de musica (music1/music2) son reemplazos y las capas (stems) son mezclas con cambio de carril sincronizado
- [x] audio_index.bin, docs/formato-audio.md, 44 tests
- [ ] Tu escucha: experiments/xa_test (disco con el MUSIC.XA real)

### Fase 6 - Motor PS1: base (demo hecha, pendiente de probar en emulador)
- [x] engine/: video con doble buffer y capas, lectura de CD, LZ4, carga de imagenes IMG1, fuente de 4 bits con acentos, maquina de escribir, control
- [x] tools/engine: FONT.BIN (248 glifos, normal y cursiva) y disco de la demo
- [x] Compila sin avisos; SNOOT.EXE de 36 KB
- [x] Probada en DuckStation (base del juego de la Fase 7)

### Fase 7 - Motor PS1: interprete y escenas
- [x] VM portable (engine/src/vm.c) comparada con el simulador en PC (tests/test_vm_host.py)
- [x] Bucle de juego: escenas, dialogo, menus, cambio de capitulo; disco con `python -m tools.engine.build_game --chapters 0,...`
- [x] Capitulo 1 jugado completo en DuckStation
- [x] Arreglos tras la prueba: cuelgue del GPU con subidas de tamano impar, paletas que no se liberaban, posicion conservada en `show` sin `at`
- [x] Fondos con Pan (stairs, fanglookback, pathetic, roomthrash1): imagen completa en RAM, ventana visible en VRAM
- [x] Modo saltar segun el plan: R1 activa/detiene, ">> Saltando", sin lecturas de CD, se detiene en texto no leido, finales y cambio de capitulo; sigue tras una decision
- [x] Galeria: se marcan las imagenes vistas (SCENE/SHOW/MARK_SEEN) con la tabla de GAME.BIN
- [x] Auditoria visual contra Ren'Py de todo el juego (base, 4 rutas, 10 extras): faltantes, orden de personajes, posiciones, dimmers, destellos, fondos espejados y animaciones corregidos (ver docs/bitacora.md)
- Nota: RAM usada ~1.14 MB (bufer de 512 KB para fondos con Pan)

### Fase 8 - Audio, transiciones, guardado y menus (hecha)
- [x] Musica XA por carriles (bucles, intro -> bucle, finales de familia, stems sincronizados, fundidos); ambientes y efectos con cache en la SPU; pausa y reanudacion de la musica en cada lectura del CD
- [x] Transiciones: disolver (copia de pantalla en VRAM), fundidos a negro/blanco, sacudidas, movimiento
- [x] Creditos de arranque, titulo, pausa, guardar/cargar en 3 ranuras (2 archivos alternados con checksum), opciones de volumen, galeria, capitulos extra con la logica original, autoguardado del progreso
- [x] Chat del capitulo 4 (textscroll) y creditos finales
- [x] Probado en PCSX-Redux sin interfaz con `tools/engine/emutest.py` (guardar, Continuar, opciones, galeria, chat)

### Fase 9 - Build automatico (hecha)
- [x] `python build.py`: scripts, simulador, imagenes, audio (solo si cambio), motor y disco en ~1 minuto; disco de 213 MB (27% del CD)

### Fase 10 - Pruebas (en curso)
- [x] `python -m tools.engine.playtest`: recorre en autoplay la historia, las 4 rutas y los 10 extras; reporte en build/reports/playtest.md
- [x] Reporte revisado: las 15 corridas llegan al final sin errores de la VM ni de lectura del CD
- [x] Corregido tras tu prueba: rayas verticales en DuckStation (bit de mascara), sprites de RAYmba muy altos (media resolucion), chat del capitulo 4 con flechas y "Presiona X para continuar"
- [x] Fluidez: disolver continuo y fundidos a negro reales (brillo de texturas en vez de pasos)
- [x] Cargas (D7): tabla de sectores FILES.BIN, una sola pausa de la musica por paso del guion y precarga de las imagenes siguientes en un cache de RAM de 320 KB
- [x] `python -m tools.release 0.1` -> dist/SnootGamePS1-v0.1.zip (168 MB) con todo lo anterior
- [ ] Tu prueba en DuckStation con sonido (que la musica no se corte entre escenas)
- [x] VRAM: videollamada y grano de la ruta 3 completos (antes 34 cuadros sin cargar) y fondo del pasillo del capitulo 10 que se perdia tras una transicion; playtest con 0 imagenes sin cargar en las 15 corridas
- [x] Tu segunda prueba: insultos del concierto legibles y dentro de la pantalla; teclado en pantalla en 13D (`renpy.input`)
- [x] Congelones: precarga en segundo plano (imagenes, ambientes y efectos), revision de lo que viene en cada linea y motor en Release (-O2). Historia completa: de 316 congelones (peor 4.25 s, 156 s en total) a 131 (peor 1.05 s, 37 s); los que quedan son casi todos al empezar un capitulo
- [x] Version 1.0: sin barras ni indicadores de arranque, solo los creditos (dist/SnootGamePS1-v1.0.zip)
- [ ] PS2 con POPStarter (.VCD): no funciona, ni siquiera el disco sin memory card (`--nocard`), asi que la causa no es (solo) la memory card. Descartado por ahora: el usuario lo probara en una PS1 real con CD-R y se pasa al port nativo (C:\Dev\snoot-ps2)
- Conocido: en las escenas con 9 personajes (Trigga III, Naomi I) 9 transiciones se hacen como corte por falta de VRAM
- Conocido: Fang en el acuario de 12D, videollamada de 13C y dimmer del 40% (se usa 50%) no son identicos a Ren'Py
- Nota: RAM usada ~1.6 MB de 2 MB

## Siguiente
- [ ] Repartir la v0.1 a probadores y corregir lo que reporten
- [x] Caja de texto con fundido y modo `window auto` como Ren'Py
- [ ] Pulido opcional: movimientos lentos de sprites mas suaves
- [ ] Opcional: precargar el capitulo siguiente para quitar el congelon de ~0.6 s al cambiar de capitulo
- [ ] Fase 11 - Hardware real (tiempo de busqueda del CD, memory card fisica) y distribucion
## Notas
- mkpsxiso 2.10 no admite rutas absolutas de Windows en el XML; usar rutas relativas (ver docs/entorno.md).
- PCSX-Redux requiere BIOS real (SCPH1001); con OpenBIOS no arranca el disco.
- Regenerar la auditoria: `python tools/audit/inventario.py`; audio: `python tools/audio/audit_audio.py`.
- Disco de prueba XA: `python experiments/xa_test/build_test.py`.
- Riesgos resueltos por diseno: D12 huecos de musica (copias seguidas + rebobinado en transiciones), D13 personajes (sin capas; solo se pre-componen fondos con texto y pantallas de telefono), D14 animaciones (zoom/giro con POLY_FT4, tinte con modulacion de color).
- Riesgo que solo se confirma en consola real (Fase 11): duracion real del salto de busqueda del CD.
- Estadisticas de bucles: `python tools/audio/segment_stats.py`.
- Prueba en emulador sin usar teclado ni pantalla: `python -m tools.engine.emutest --steps "30 press CROSS; 200 shot juego; 210 quit"`.
- Auditoria visual: `python -m tools.audit.capture` (Ren'Py, una instancia a la vez; ~1.5 h todo) y `python -m tools.audit.compare <carpeta>...` (hojas en `<carpeta>/report/`).
