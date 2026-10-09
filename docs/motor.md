# Motor PS1 (engine/)

Estado: Fase 6 (demo del motor base). Se construye con `python -m tools.engine.build_demo`, que genera `build/engine/snoot_demo.cue`.

## Modulos
| Archivo | Que hace |
|---|---|
| `src/video.c` | GPU, dos framebuffers de 320x240, tabla de orden por capas, memoria de primitivas, recorte 16:9 |
| `src/cd.c` | Lee archivos del CD a RAM (por nombre en la demo; el juego usara una tabla de sectores) |
| `src/lz4.c` | Decodificador LZ4 (D9) |
| `src/img.c` | Carga imagenes IMG1 (paleta a CLUT, indices a VRAM) y las dibuja; parte los fondos de 320 px en dos sprites |
| `src/text.c` | Fuente de 4 bits con mezcla aditiva, UTF-8, codigos de control y efecto de maquina de escribir |
| `src/input.c` | Control con deteccion de pulsacion |
| `src/main.c` | Demo: fondo, personaje, caja de texto y tres lineas reales |

## Conceptos
- **Capas:** `video_add(capa, primitiva)`. La capa 0 queda al frente. Dentro de una capa, lo agregado despues se dibuja antes (la tabla de orden inserta al inicio), por eso las paginas de textura se agregan despues de los sprites que las usan.
- **Recorte:** la escena se dibuja solo en las 180 lineas centrales (`video_clip_scene`); la caja de texto y la interfaz usan toda la pantalla (`video_unclip`).
- **Mapa de VRAM** (palabras de 16 bits): framebuffers (0,0) y (0,240); fondo (640,0); sprites (320,0); fuente (960,0); paletas de imagenes en las filas 480 y 481; paleta de la fuente en (0,500).
- **Texto:** las cadenas vienen ya partidas en lineas (`\n`) y paginas; los codigos 1 a 6 y `\n`, salto de pagina se interpretan en `text.c`. Cursiva usa glifos inclinados del atlas; negrita dibuja cada glifo dos veces. Los demas codigos de tamano se ignoran por ahora.

## Controles de la demo
X avanza o completa el texto, Cuadrado oculta la caja, Select muestra FPS y numero de linea.
