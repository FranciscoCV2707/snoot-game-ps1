# Motor PS1 (engine/)

Estado: Fase 8 en curso (audio y transiciones hechos; siguen titulo, pausa, guardado). Se construye con `python -m tools.engine.build_game [--chapters 0,1]`, que genera `build/engine/snoot_game.cue` con los capitulos pedidos y solo las imagenes que usan.

## Modulos
| Archivo | Que hace |
|---|---|
| `src/video.c` | GPU, dos framebuffers de 320x240, tabla de orden por capas, memoria de primitivas, recorte 16:9 |
| `src/cd.c` | Lee archivos o sectores del CD a RAM (por nombre; la tabla de sectores llega en la Fase 9). Cada lectura pausa y reanuda la musica |
| `src/audio.c` | Musica XA por carriles (bucles, intro -> bucle, finales de familia, stems), ambientes en 4 voces fijas y efectos con cache en la RAM de la SPU |
| `src/scene.c` | Escena portable (tambien en la auditoria): orden, aspecto de cada sprite en el tiempo de su animacion, mezcla de colores solidos |
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
Camara animada, guardado, titulo, pausa, galeria y packs de carga.

## Transiciones
- Dissolve y fundidos guardan el ultimo cuadro en VRAM (`video_snapshot`, banda baja de la zona de fondos reservada con `res_reserve_snapshot`) y lo dibujan como textura de 15 bits encima de la escena nueva.
- Todo se dibuja con el bit de mascara (DR_STP): asi la copia no tiene negros transparentes y la GPU puede mezclarla.
- Dissolve: copia al 75% (dos pasadas al 50%), luego al 50%, luego nada. Fundido a negro/blanco: resta/suma de un gris que sube y baja.
- vpunch/hpunch desplazan toda la escena; MoveTransition lleva cada sprite de donde estaba (o desde el borde) a su posicion nueva.

## Audio
- RAM de la SPU: 4 KB del sistema, zona de efectos (~284 KB, se vacia entera al llenarse) y 4 espacios de 56 KB para ambientes (voces 0-3). Efectos en las voces 4-23.
- Al mostrar una linea se precargan los efectos de las siguientes instrucciones; al saltar (R1) no suenan los efectos.
- Los efectos de mas de 192 KB se convierten a 11 kHz (`tools/audio/convert.py`) para caber en su zona.

## Zona segura
La interfaz (indicadores, iconos) se mantiene a unos 10 pixeles de los bordes: algunos emuladores y televisores recortan las esquinas. El triangulo de "presiona X" se vio cortado en (304, 228) y quedo bien en (290, 216).
