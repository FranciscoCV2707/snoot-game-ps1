# Especificación del bytecode VNB (versión 1)

Contrato entre el compilador (`tools/script_compiler`, PC) y el motor (`engine/`, PS1). Cualquier cambio de formato sube `version`, y se actualizan en el mismo cambio este documento, el compilador, el simulador, el desensamblador y el motor.

Basado en la auditoría (`docs/auditoria.md`): 0 instrucciones desconocidas, 14,691 líneas de diálogo, 101 etiquetas, unas 25 condiciones, 3 `call`, 26 menús `menu` más 14 menús en Python.

## 1. Principios
- Todo lo inteligente se resuelve en la PC. El motor ejecuta un intérprete simple: sin cadenas en el bytecode, sin resolución de nombres, sin parseo.
- Números en little-endian. Instrucciones de longitud fija según su opcode (sin prefijos de longitud), para saltar sin decodificar.
- Un archivo `.VNB` por capítulo (cargado completo a RAM, máximo 128 KB de código por capítulo).
- El texto va en tablas aparte (`TEXT_ES.BIN`); el bytecode solo trae IDs.
- Los nombres de personajes, imágenes y sonidos se convierten en IDs numéricos por el compilador.

## 2. Archivos de datos
| Archivo | Contenido |
|---|---|
| `SCRIPT/Cxx.VNB` | Código de un capítulo (ver sección 3) |
| `TEXT_ES.BIN` | Cadenas en español por capítulo (sección 6) |
| `IMG/index.bin` | id de imagen → sector, tamaño, tipo, paleta, banderas (galería, final) |
| `audio_index.bin` | id de pista/efecto → sector, duración, intro, bucle |
| `packs.bin` | id de paquete → sectores contiguos y lista de recursos (sección 7) |
| `characters.bin` | id de hablante → nombre en español, color |
| `positions.bin` | id de posición → xalign, yalign (8.8 con signo) |

## 3. Estructura de `.VNB`
```
0x00  "VNB1"   identificador y versión
0x04  u16      número de capítulo
0x06  u16      número de etiquetas exportadas
0x08  u32      tamaño del código en bytes
0x0C  u32      ID global del primer texto del capítulo (base para los bits de "leído")
0x10  u16      número de cadenas locales
0x12  u16      número de animaciones (tabla ANIM)
0x14  u32      offset de la tabla de etiquetas
0x18  u32      offset de la tabla ANIM
0x1C  u32      reservado
Código            instrucciones
Tabla de etiquetas (id u16, offset u32) × N
Tabla ANIM        (sección 5)
```
El ID global de un texto es `base + id_local`. Ese número es el bit "leído" de la partida.

## 4. Instrucciones
Formato: `opcode u8` seguido de los argumentos. Tamaños en bytes entre paréntesis.

### Diálogo y ventana
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x01 | `SAY` | hablante u8, texto u16 (4) | `A "..."`, `"..."` (hablante 0 = narrador) |
| 0x02 | `SAYX` | hablante u8, texto u16 (4) | `extend "..."` (continúa en la misma caja, sin borrar) |
| 0x03 | `TEXTBOX` | modo u8 (2): 0 ocultar, 1 automático | `window hide`, `window auto`, `window show/hide Dissolve(x)` |

### Imágenes
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x10 | `SCENE` | imagen u16 (3); 0 = negro | `scene fondo` (borra todos los sprites) |
| 0x11 | `SHOW` | tag u8, imagen u16, pos u8, z i8, flags u8, anim u8 (8) | `show anon neutral at sleft`, `behind`, `flip`, `at` con ATL |
| 0x12 | `HIDE` | tag u8 (2) | `hide fang` |
| 0x13 | `TRANSITION` | tipo u8, a u16, b u16, c u16 (8) | `with Dissolve(1)`, `with fade`, `with None` |
| 0x14 | `SHOW_RANDOM` | tag u8, primera imagen u16, cantidad u8, flags u8 (6) | `showCG()` (elige 1 de las 9 imágenes de texto en una posición aleatoria) |
| 0x15 | `MARK_SEEN` | imagen u16 (3) | `renpy.mark_image_seen(...)` |

- `tag` identifica el "lugar" del sprite (anon, fang, naser, bg...). `SHOW` con un tag que ya existe lo reemplaza. Hasta 12 sprites simultáneos más el fondo (los fondos de color sólido, como `black`, `white` o `dimmer_*`, no cuentan: se dibujan como rectángulos).
- `z` es el orden de dibujo (de `behind`): mayor se dibuja encima.
- `flags` de `SHOW`: bit0 volteado (`xzoom -1`/`flip`), bit1 empezar invisible. Las 245 definiciones `im.Flip(...)` del juego no generan imágenes nuevas: el compilador usa la imagen original con el bit de volteo (cambia las coordenadas de textura).
- `anim` indexa la tabla ANIM del capítulo (0 = ninguna).
- Los cambios de `SCENE`/`SHOW`/`HIDE` se acumulan; `TRANSITION` los presenta con el efecto indicado. Sin `TRANSITION`, el cambio se ve de golpe cuando termina la instrucción de texto o pausa siguiente.
- Tipos de `TRANSITION`: 0 corte (`with None`), 1 disolver (a = duración en cuadros), 2 fundido por negro (a = salida, b = espera, c = entrada), 3 sacudida vertical, 4 sacudida horizontal. Las demás transiciones (`MoveTransition`, `easeinbottom`, `move`) se aproximan a disolver o corte.
- Imágenes con efecto de galería o final: el índice de imágenes marca el bit; el motor lo registra al mostrarse con `SCENE`/`SHOW`. Las cuatro imágenes `e1of4`...`e4of4` registran además el final alcanzado.

### Audio
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x20 | `MUSIC_PLAY` | pista u16, fundido u8 (1/10 s), flags u8 (4) | `play music ... fadein N` (también `music1`/`music2` con bit0 crossfade) |
| 0x21 | `MUSIC_STOP` | fundido u8 (2) | `stop music fadeout N` |
| 0x22 | `AMBIENT_PLAY` | ranura u8 (0-3), sonido u16, fundido u8 (5) | `play ambient/ambient1-3 ... fadein N` |
| 0x23 | `AMBIENT_STOP` | ranura u8, fundido u8 (3) | `stop ambient... fadeout N` |
| 0x24 | `SFX_PLAY` | sonido u16 (3) | `play sound ...`, `play audio ...` |
| 0x25 | `SFX_STOP` | fundido u8 (2) | `stop sound`, `stop audio` |
| 0x26 | `VOLUME` | canal u8, volumen u8 (0-255), tiempo u8 (1/10 s) (4) | `renpy.music.set_volume(v, t, canal)` (118 usos) |
| 0x27 | `MUSIC_QUEUE` | pista u16 (3) | `queue music ...` (8 usos; pistas con intro + bucle consecutivas) |

- Canales: 0 música, 1-4 ambientes, 5 sonido. El bucle de música lo define el índice de audio (pista con inicio de bucle), no la instrucción.
- `queue music "<silence 1.0>" loop` (usado para detener un bucle) se compila a `MUSIC_STOP`.

### Pausa y especiales
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x30 | `PAUSE` | cuadros u16, flags u8 (4) | `pause N`, `renpy.pause`; bit0 saltable con un botón (Ren'Py lo permite en pausas con tiempo) |
| 0x31 | `SPECIAL` | id u8 (2) | 1 = pantalla de texto desplazable (`call screen textscroll`, capítulo 4); 2 = créditos (`label lending`) |

### Control de flujo
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x40 | `MENU` | flags u8, n u8, n × (texto u16, destino u32) | `menu:` y `renpy.display_menu(...)` |
| 0x41 | `JUMP` | destino u32 (5) | `jump etiqueta` |
| 0x42 | `JUMP_IF_FALSE` | destino u32 (5) | `if`/`elif`/`while`; usa el tope de la pila |
| 0x43 | `CALL` | destino u32 (5) | `call etiqueta` |
| 0x44 | `RETURN` | (1) | `return` |
| 0x45 | `LOAD_CHAPTER` | capítulo u16, entrada u32, modo u8 (8) | `call expression current_chapter` y saltos o llamadas a etiquetas de otro capítulo; modo 0 = llamada (apila el retorno), 1 = salto |
| 0x46 | `END` | (1) | fin del capítulo; el motor decide el siguiente paso |

- `MENU` flags: bit0 orden aleatorio de las opciones (el juego usa `randomize_choices` con 2 opciones).
- Los menús en Python con nombres de salto armados en ejecución (`_value + chr(0x61 + _tick)`) se desenrollan en el compilador a etiquetas explícitas (se tratan a mano en la Fase 3).
- Los capítulos se encadenan en un archivo `STORY.VNB` generado a partir de `src/storyline.rpy` y `chapter_variables.rpy`: carga los capítulos base 1-11, evalúa `get_ending` con variables y salta a la ruta correspondiente (`ENDING_ROUTES`). No hay lógica de capítulos en el motor.

### Variables y expresiones
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x50 | `SET_VAR` | var u8, valor i16 (4) | `$ x = 3`, `$ flag = True` (True = 1) |
| 0x51 | `ADD_VAR` | var u8, valor i16 (4) | `$ x += 1` |
| 0x52 | `PUSH_VAR` | var u8 (2) | variable en expresión |
| 0x53 | `PUSH_CONST` | valor i16 (3) | constante en expresión |
| 0x54 | `OP` | operador u8 (2) | `== != < <= > >= and or not + - *` (0 a 11, orden de `OPERATORS` en `opcodes.py`) |
| 0x55 | `STORE_VAR` | var u8 (2) | `$ x = expresión` (saca el tope de la pila y lo guarda) |

- Variables: 64 de 16 bits con signo. Las banderas booleanas son variables 0/1. La auditoría encontró unas 12 (`anonscore`, `fangscore`, `wingStory`, `late_to_spears`, `punched_into_flowerbed`, `TalkedWithTrish`, `LeftStage`, `ending_route_number` y contadores de bucles).
- Pila de expresiones: 16 entradas. Pila de `CALL`: 8 niveles (el juego usa 3 llamadas).
- Variables de texto: no hay en la historia (los textos son constantes); si apareciera una, se convierte en enumeración numérica en la PC.

### Progreso, carga y depuración
| Op | Nombre | Argumentos | Ren'Py |
|---|---|---|---|
| 0x60 | `LOAD_PACK` | paquete u16 (3) | no existe en Ren'Py; el compilador lo inserta (sección 7) |
| 0x61 | `UNLOCK_BONUS` | n u8, 0-8 (2) | `$ persistent.bonus_chapters \|= (1 << n)` |
| 0x62 | `ENDING` | id u8, 1-4 (2) | marca el final en el progreso y guarda el progreso automáticamente |
| 0xFE | `DEBUG` | id u16 (3) | marca para comparar con el simulador; el motor la ignora |
| 0xFF | `HALT` | (1) | error interno |

- Los datos `persistent` de la historia son solo escrituras; las lecturas (menú de extras, título, galería) están en el motor en C.
- Material picante: no llega al bytecode. El compilador resuelve `persistent.lewd == True` como verdadero y emite solo esa rama.
- Texto leído: sin instrucción propia; el ID global del texto de `SAY`/`SAYX` es el bit marcado.

## 5. Tabla ANIM (animaciones de sprites)
El compilador "ejecuta" los bloques ATL de Ren'Py (unas 2,957 apariciones, sobre todo `xalign`/`yalign` con `easein_cubic`, `ease_cubic`, `easeout_cubic`, `linear`, `parallel` y `repeat`) y deja una lista de fotogramas clave por sprite:
```
anim:  u8 número de fotogramas clave (1-8), u8 flags (bit0 bucle, bit1 vaivén)
clave: u16 tiempo en cuadros, s16 xalign (8.8), s16 yalign (8.8), u8 alfa (0-255), u8 curva,
       u8 zoom (1/64; 64 = 1.0), s8 xzoom (1/64; negativo = espejo), s8 rotación (360/256 grados por unidad),
       u8 r, u8 g, u8 b (modulación de color; 128 = sin cambio, 255 = 2x)   -> 16 bytes
```
- Curvas: 0 lineal, 1 aceleración (ease-in cúbica), 2 desaceleración (ease-out cúbica), 3 ease-in-out. Las demás (`back`, `elastic`, `quart`, `quad`, `bounce`) se aproximan a la más cercana.
- `parallel:` de ejes distintos se combina en la misma clave. Los bloques que superan 8 claves se recortan y se reportan. `choice:` (25 usos) toma siempre la primera rama.
- **Zoom, giro y espejo animados** (`zoom`, `xzoom`, `rotate`: unos 120 usos): los sprites con claves de estos tipos se dibujan como cuadriláteros texturizados (`POLY_FT4`) en vez de sprites rectos; la GPU de PS1 los escala y gira sin costo de CPU relevante (el giro usa una tabla de senos de 256 entradas). Sin zoom ni giro se usa el sprite recto, más barato.
- **`matrixcolor`** (10 usos): `TintMatrix` y `BrightnessMatrix(-1)` se convierten en la modulación r,g,b del sprite (la GPU multiplica la textura por ese color, hasta 2x). `BrightnessMatrix(+1)` (pasar a blanco) se aproxima con 2x de brillo. No se soporta saturación.
- **`blur`**: las escenas "desenfocadas" del juego (`home fang night blurred`, `anon prom blurred`) son imágenes distintas ya incluidas en el juego; se tratan como imágenes normales. Un `blur` animado se aproxima con un disolver entre la imagen nítida y la desenfocada.
- **`alignaround` / `shudder` / `wiggle`**: se convierten en vibración de posición (claves xalign/yalign de 2 a 4 puntos en bucle); el temblor de pantalla completo es `TRANSITION` 3/4. El zoom del logo en créditos es parte de `SPECIAL 2`.
- Las dos `layeredimage` del juego son pantallas de teléfono; el compilador las pre-renderiza como una imagen por combinación de atributos usada (ver `docs/auditoria_manual.md`).
- Posiciones con nombre (`scenter`, `sleft`, `acenter`, `ncenter`, `rleft`, ...) son entradas de `positions.bin` (xalign, yalign) tomadas de `src/misc_definitions.rpy`; algunas salen de pantalla a propósito (ej. `nleft` = -0.2).
- Animación por fotogramas (`fang tail`, ver D3): una imagen especial del índice de imágenes con lista de cuadros y tiempo por cuadro; se muestra con `SHOW` normal.

## 6. Texto
`TEXT_ES.BIN`: tabla de offsets (u32 por cadena) y cadenas UTF-8 ya convertidas al conjunto de glifos de la fuente. Las líneas largas se dividen en páginas en la PC según el ancho de la caja (D6). Códigos de control (bytes < 0x20):
| Código | Significado | Etiqueta Ren'Py |
|---|---|---|
| 0x01 | cambio de estilo: 0 normal, 1 cursiva, 2 negrita (se dibujan con otra paleta de la fuente) | `{i}`, `{b}` |
| 0x02 n | esperar n/10 s | `{w=n}` |
| 0x03 n | velocidad de texto (cps, n × 5) | `{cps=...}` (2,830 usos) |
| 0x04 | avanzar solo al terminar (sin esperar botón) | `{nw}` |
| 0x05 | continuar sin repetir lo anterior | `{fast}` |
| 0x06 n | tamaño relativo (-2..+2) | `{size=...}` |
| 0x0A | salto de línea | `\n` |
| 0x0B | salto de página (esperar botón y borrar) | partición automática |
- `{alpha}`, `{color}` (pocos usos) se descartan o se convierten en estilo.
- Las cadenas de menús, nombres de hablantes y la interfaz (Comenzar, Continuar, Galería, mensajes de memory card...) usan las mismas tablas.

## 7. Paquetes de carga (resultado de D7)
Cada paquete (`packs.bin`) es un rango contiguo de sectores en el CD con los fondos, sprites, efectos y texto que se usan hasta el siguiente cambio de música. `LOAD_PACK` lo ejecuta el motor pausando la música, leyendo de un solo golpe y reanudando. El compilador:
1. Recorre cada capítulo con el simulador y construye la lista de recursos por segmento entre `MUSIC_PLAY`/`MUSIC_STOP`.
2. Emite `LOAD_PACK` justo antes del cambio de música (donde ya hay silencio o fundido).
3. Si un segmento no cabe en el presupuesto (~600 KB de RAM más VRAM libre), lo parte en paquetes y reporta la pausa forzada.
4. El disco duplica recursos entre paquetes para que cada paquete sea contiguo (sobra espacio, ver `docs/presupuesto-audio.md`).

Si un recurso no está residente al usarse (error del compilador), el motor lo carga bajo demanda con pausa de la música y cuenta el incidente en el modo de depuración.

## 7b. Reglas de audio en ejecución (D12)
- **Bucles de música:** cada pista que se repite se graba en el CD en varias copias seguidas (`copias` en `audio_index.bin`). Al terminar las copias, el motor debe volver al inicio con una búsqueda (hueco de ~0.3-0.5 s).
- **Rebobinado adaptativo:** cuando quedan menos de 30 s de copias, el motor "arma" el rebobinado y lo ejecuta en la siguiente `TRANSITION` con fundido o disolver (el cambio de imagen tapa el hueco). Solo si las copias se acaban antes de una transición, se hace el salto forzado.
- **Salto forzado:** cada copia termina con un fundido de salida de 120 ms y empieza con uno de entrada de 120 ms grabados en el audio, para que no haya chasquidos.
- **Cargas a mitad de un tramo:** el compilador coloca `LOAD_PACK` en la última `TRANSITION` anterior al primer uso del recurso; el motor baja el volumen del CD en 150 ms, pausa, carga, reanuda en la posición guardada y sube el volumen. Las cargas al cambiar de pista no necesitan reanudar.
- El simulador cuenta saltos forzados y cargas forzadas por capítulo; la meta es que sean casos aislados.

## 8. Límites
| Recurso | Límite |
|---|---|
| Variables | 64 (i16) |
| Pila de expresiones / `CALL` | 16 / 8 |
| Sprites simultáneos | 12 + fondo (la escena de multitud del extra x6 usa 11) |
| Fotogramas clave por animación | 8 |
| Opciones por menú | 6 |
| Código por capítulo | 128 KB |
| Cadenas por capítulo | 65,535 |
| Imágenes / sonidos / pistas | u16 (65,535) |

## 9. Traducción de las instrucciones de la auditoría
| Ren'Py (veces) | Bytecode / decisión |
|---|---|
| dialogue (14,595), `extend` (98) | `SAY`, `SAYX` |
| `window auto/hide/show` (4,000+) | `TEXTBOX` |
| `show` (6,847), `scene` (796), `hide` (544) | `SHOW`, `SCENE`, `HIDE` |
| `with` (929) y transiciones en `show/scene ... with` | `TRANSITION` (ver tipos) |
| `pause` (7,963) | `PAUSE` |
| `play`/`stop`/`queue` music/ambient/sound/audio (1,810) | `MUSIC_*`, `AMBIENT_*`, `SFX_*` |
| `$` (203): asignaciones | `SET_VAR`, `ADD_VAR` |
| `$ renpy.music.set_volume` (118) | `VOLUME` |
| `$ renpy.mark_image_seen` (26+) | `MARK_SEEN` |
| `$ persistent.bonus_chapters \|= ...` (9) | `UNLOCK_BONUS` |
| `$ showCG()` (4+) | `SHOW_RANDOM` |
| `menu` (26) + `renpy.display_menu` (14) | `MENU` |
| `label` (101), `jump` (48), `call` (3), `return` (45) | etiquetas, `JUMP`, `CALL`, `RETURN` |
| `if`/`elif`/`else`/`while` (45) | `PUSH_*`, `OP`, `JUMP_IF_FALSE`, `JUMP` |
| `call expression current_chapter` | `STORY.VNB` generado + `LOAD_CHAPTER` |
| `renpy.quit()` (final Shooter) | `END` + el motor vuelve al título |
| `call screen textscroll` (1) | `SPECIAL 1` |
| `label lending` / créditos | `SPECIAL 2` |
| `define`/`default` (256) | resueltos por el compilador (variables a índices, constantes en tablas) |
| `image` (431), `layeredimage` (2) | `IMG/index.bin` (las expresiones y capas se pre-componen en la PC) |
| `transform` (42), ATL en `show` (2,957) | posiciones (`positions.bin`) y tabla ANIM |
| `style` (198), `screen` (52), `gui.*`, `config.*` | descartados: el motor tiene su propia interfaz |
| `init python`, mods, idioma, ventana, historial, rueda | descartados (ver auditoría) |
| `persistent.lewd` (8) | siempre verdadero; no llega al bytecode |
| `pass` (31), `camera` (0 en la historia) | sin efecto |

## 10. Verificación
- El desensamblador convierte `.VNB` a texto y el simulador (Python) ejecuta el mismo bytecode; las instrucciones `DEBUG` permiten comparar la secuencia contra el motor.
- Cada instrucción tiene una prueba en `tests/` (codificación, desensamble, ejecución).
- Un cambio de formato exige subir `version` ("VNB1" a "VNB2") y regenerar todo.
