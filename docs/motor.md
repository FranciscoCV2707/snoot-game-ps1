# Motor PS1 (engine/)

Estado: Fase 8 casi completa (audio, transiciones, titulo, pausa, guardado, opciones, galeria y extras). Falta probarla a fondo en consola o emulador. Se construye con `python -m tools.engine.build_game [--chapters 0,1]`, que genera `build/engine/snoot_game.cue` con los capitulos pedidos y solo las imagenes que usan. Se compila en Release (`-O2`, `CMakePresets.json`): en Debug (`-Og`) descomprimir tardaba mas del doble.

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
- **Desalojo de VRAM** (`res.c`): primero lo de escenas anteriores; si no alcanza para dibujar, lo de la escena actual que no se dibujo en este cuadro ni en el anterior (cuadros de animacion ya pasados). Los cuadros futuros de las animaciones se precargan solo con espacio libre (`res_preload`), sin desalojar ni contar como falla. Al preparar una escena, lo que ya tiene cargado se marca primero (`res_touch`) para que lo nuevo no lo desaloje. La copia de las transiciones se reserva despues de cargar lo nuevo, en la franja de la zona de fondos que menos tape lo que esta en pantalla; si lo que quitaria no se puede volver a acomodar en el resto (prueba exacta en una copia de la cuadricula), la transicion se hace como corte con la misma duracion (`res_snap_skip`). Al liberarla se reintenta lo que no cupo.
- Las zonas de sprites y fondos usan las 512 filas (dos bandas de 256): las paletas de las filas 480+ estan en x < 320.
- **Texto:** las cadenas vienen ya partidas en lineas (`\n`) y paginas; los codigos 1 a 6 y `\n`, salto de pagina se interpretan en `text.c`. Cursiva usa glifos inclinados del atlas; negrita dibuja cada glifo dos veces. Los demas codigos de tamano se ignoran por ahora.

## Controles
X avanza o completa el texto y confirma, O vuelve, Start abre la pausa (en una linea o una decision), d-pad elige, R1 salta lineas ya leidas (se detiene en lineas nuevas y menus), Cuadrado oculta la caja, Select muestra la depuracion. En el titulo, L1 + R1 + Select abre el menu de capitulos de desarrollo.

## Pantallas y guardado
- Arranque: creditos mientras se lee la memory card (con Select presionado no se usa en toda la sesion; un disco armado con `build_game.py --nocard` no instala su controlador); titulo (Comenzar, Continuar, Capitulos extra, Galeria, Opciones). Si falta la fuente se ve un bloque rojo.
- Pausa: Seguir, Saltar texto leido, Guardar, Cargar, Opciones, Salir al titulo (con confirmacion).
- `src/save.c`: 2 archivos de 1 bloque alternados (`BASLUS-99999SNOOTA`/`B`) con numero de guardado y checksum; titulo "SNOOT GAME" en Shift-JIS e icono `MCICON.BIN`.
- Datos (main.c, seccion guardado): volumenes, finales, extras terminados, galeria vista, texto leido y 3 ranuras (capitulo, instruccion del SAY o MENU, variables, llamadas, escena, musica y ambientes, tiempo).
- Se guarda al elegir Guardar, al ver un final por primera vez, al terminar una partida, al salir al titulo y al cambiar las opciones.
- Capitulos extra con la logica de `ex_ch_menu` del original (D1): segun los finales vistos y los extras terminados.
- `SPECIAL 1` (chat del capitulo 4): la imagen `texts` en espanol en tiras de 320x180 (`ui textscroll N`, 0.4x del original); empieza abajo (lo mas reciente), se desplaza con arriba/abajo (R1 rapido) con barra de posicion; al llegar arriba (donde el original tenia el boton) aparece "Presiona X para continuar".
- `SPECIAL 2` (creditos): las lineas de `credits.rpy` traducidas suben por la pantalla; X acelera.
- `SPECIAL 3` (`renpy.input` de 13D, "¿Qué escribirás?"): teclado en pantalla de 10x5 teclas (numeros, letras con ñ, acentos y signos) y una fila de acciones (Mayús, Espacio, Borrar, Listo). D-pad mueve, X escribe, O borra, L1 cambia mayusculas, Start termina; hasta 36 caracteres. Como en el original, lo escrito no se usa despues.

## Prueba automatica
`python -m tools.engine.emutest --steps "30 press CROSS; 200 shot juego; 210 quit"` arma un disco con `AUTOTEST.BIN` (botones por cuadro desde el titulo) y lo corre en PCSX-Redux sin interfaz; las capturas quedan en `build/emutest/`. No usa el teclado ni la pantalla de la PC.

## Pendiente en el motor (fases siguientes)
Camara animada, packs de carga (Fase 9) y miniaturas en ranuras y galeria (opcional).

## Transiciones
- Dissolve y fundidos guardan el ultimo cuadro en VRAM (`video_snapshot`, en una franja de la zona de fondos reservada con `res_reserve_snapshot`) y lo dibujan como textura de 15 bits encima de la escena nueva.
- Todo se dibuja con el bit de mascara (DR_STP): asi la copia no tiene negros transparentes y la GPU puede mezclarla.
- Dissolve continuo: la escena nueva se dibuja con brillo t (modulacion de color de las texturas, `img_brightness`) y encima se suma la copia de la anterior con brillo 1 - t. Fundido a negro: la copia se oscurece multiplicada y la escena nueva entra subiendo el brillo. Fundido a blanco: suma de un gris.
- vpunch/hpunch desplazan toda la escena; MoveTransition lleva cada sprite de donde estaba (o desde el borde) a su posicion nueva.

## Caja de texto
- Replica `config.window = "auto"` con `Dissolve(.2)`: aparece con cada linea (el texto empieza cuando termino de aparecer), se queda vacia en las pausas siguientes y se oculta antes de `scene` y de las decisiones. `window show/hide` la fijan y `window auto` vuelve al modo automatico (`TEXTBOX`, docs/bytecode.md); con una transicion de un cuadro o menos el cambio es instantaneo.
- El fundido dura 12 cuadros: a medio camino se resta un gris (no hay mezcla variable) y al final se oscurece al 50%.
- Si la caja sigue visible durante un dissolve o fundido, la franja de la caja en la copia se dibuja al doble de brillo para no oscurecerla dos veces; si se oculta, se va con la copia.

## Audio
- RAM de la SPU: 4 KB del sistema, zona de efectos (~284 KB, se vacia entera al llenarse) y 4 espacios de 56 KB para ambientes (voces 0-3). Efectos en las voces 4-23.
- Los efectos que vienen en el guion se ponen en cola (`audio_preload`) y se suben a la SPU en segundo plano de a 32 KB; si uno suena antes, se termina de subir en el momento. Los ambientes que vienen se traen a la cache de RAM de imagenes (`RES_SOUND`) y al sonar pasan de RAM a la SPU sin leer el CD. Al saltar (R1) no suenan los efectos.
- Una cancion que empieza mientras hay una carga en curso arranca cuando termina (no se corta recien empezada).

## Lecturas del CD
- `DATA/FILES.BIN` (lo arma `build_game.py` en dos pasadas): nombre, sector y tamano de cada archivo, ordenados por nombre. `cd_find` busca ahi en vez de `CdSearchFile`.
- Cada paso de la VM (`run_vm`) agrupa sus lecturas con `audio_batch_begin/end`: la musica XA se pausa una sola vez.
- Si en ese paso cambio la escena y la musica ya esta en pausa (o no suena), `look_ahead` recorre el guion (sigue los saltos fijos, para en menus y llamadas; incluye las 9 imagenes de `showCG()`) y `res_prefetch` trae a un cache en RAM de 320 KB las imagenes que vienen, leyendo en orden de sector los archivos contiguos de una vez. Asi la siguiente escena no vuelve a cortar la musica.
- Mientras se lee una linea (`prefetch_next`) se revisa lo que se usa antes de la siguiente: si falta algo en VRAM, en la cache o en la SPU, se empieza a traer ya (la musica se pausa una linea antes, pero al avanzar no hay congelon). La precarga elige en orden del guion mientras quepa en la cache.
- La precarga se lee en segundo plano (`cd_read_start`/`cd_read_poll`, tramos de hasta 64 sectores que avanzan en `res_tick`): el juego sigue dibujando y la musica sigue en pausa hasta que termina. Si hace falta una imagen que se esta precargando se espera solo hasta ella; cualquier otra lectura o comando de la musica espera el tramo en curso (`cd_wait`). Si empieza otra cancion a mitad de la precarga, se descarta el resto para no cortarla.
- Congelones: el motor anota los cuadros que tardan mas de 0.1 s (`stall_count`, `stall_max`, `stall_log` con los 32 peores) y el playtest los lista con la linea del guion donde ocurrieron.
- Los efectos de mas de 192 KB se convierten a 11 kHz (`tools/audio/convert.py`) para caber en su zona.

## Zona segura
La interfaz (indicadores, iconos) se mantiene a unos 10 pixeles de los bordes: algunos emuladores y televisores recortan las esquinas. El triangulo de "presiona X" se vio cortado en (304, 228) y quedo bien en (290, 216).
