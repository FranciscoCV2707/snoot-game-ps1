# Motor PS1 (engine/)

Estado: Fase 7 en curso (primer juego jugable). Se construye con `python -m tools.engine.build_game [--chapters 0,1]`, que genera `build/engine/snoot_game.cue` con los capitulos pedidos y solo las imagenes que usan.

## Modulos
| Archivo | Que hace |
|---|---|
| `src/video.c` | GPU, dos framebuffers de 320x240, tabla de orden por capas, memoria de primitivas, recorte 16:9 |
| `src/cd.c` | Lee archivos del CD a RAM (por nombre en la demo; el juego usara una tabla de sectores) |
| `src/lz4.c` | Decodificador LZ4 (D9) |
| `src/img.c` | Carga imagenes IMG1 (paleta a CLUT, indices a VRAM) y las dibuja; parte los fondos de 320 px en dos sprites |
| `src/text.c` | Fuente de 4 bits con mezcla aditiva, UTF-8, codigos de control y efecto de maquina de escribir |
| `src/input.c` | Control con deteccion de pulsacion |
| `src/vm.c` | Maquina virtual del bytecode (portable; se prueba en la PC contra el simulador: `tests/test_vm_host.py`) |
| `src/res.c` | Gestor de imagenes: carga bajo demanda, asignacion de VRAM por celdas y desalojo de lo no usado |
| `src/main.c` | Juego: escena (fondo, sprites con z y espejo), dialogo, menus con d-pad, pausas, modo saltar, fin |

## Conceptos
- **Capas:** `video_add(capa, primitiva)`. La capa 0 queda al frente. Dentro de una capa, lo agregado despues se dibuja antes (la tabla de orden inserta al inicio), por eso las paginas de textura se agregan despues de los sprites que las usan.
- **Recorte:** la escena se dibuja solo en las 180 lineas centrales (`video_clip_scene`); la caja de texto y la interfaz usan toda la pantalla (`video_unclip`).
- **Mapa de VRAM** (palabras de 16 bits): framebuffers (0,0) y (0,240); fondo (640,0); sprites (320,0); fuente (960,0); paletas de imagenes en las filas 480 y 481; paleta de la fuente en (0,500).
- **Texto:** las cadenas vienen ya partidas en lineas (`\n`) y paginas; los codigos 1 a 6 y `\n`, salto de pagina se interpretan en `text.c`. Cursiva usa glifos inclinados del atlas; negrita dibuja cada glifo dos veces. Los demas codigos de tamano se ignoran por ahora.

## Controles
X avanza o completa el texto y confirma en menus, d-pad arriba/abajo elige, R1 salta lineas ya leidas (se detiene en lineas nuevas y menus), Cuadrado oculta la caja, Select muestra la depuracion.

## Pendiente en el motor (fases siguientes)
Animaciones de sprites, transiciones, camara, audio, guardado, SAYX (extender dialogo), SHOW_RANDOM, packs de carga y fondos/CG mas grandes que una pagina de VRAM.

## Zona segura
La interfaz (indicadores, iconos) se mantiene a unos 10 pixeles de los bordes: algunos emuladores y televisores recortan las esquinas. El triangulo de "presiona X" se vio cortado en (304, 228) y quedo bien en (290, 216).
