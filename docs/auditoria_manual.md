## Hallazgos manuales (Fase 1)

### Estructura de la historia
- Capitulos 1 a 11 son lineales (`BASE_CHAPTERS`). Al terminar el 11, `get_ending(anonscore, fangscore, wingStory)` elige una de 4 rutas:
  - Golden (4): `anonscore >= 4`, `fangscore >= 4` y `wingStory`.
  - Tradwife (3): `anonscore >= 3` y `fangscore <= 4`.
  - Doomer (2): `anonscore <= 3` y `fangscore >= 3`.
  - Shooter (1): el resto. Termina el juego con `renpy.quit()`.
- Las rutas llaman a los capitulos por nombre con `call expression current_chapter` (unico salto dinamico del juego, en `src/storyline.rpy`). El compilador lo resuelve en la PC con la lista de `ENDING_ROUTES`.
- Finales: `chapter_14A` (Shooter), `14B` (Doomer), `14C` (Tradwife), `14D` (Golden). Se cuentan como vistos cuando se muestran las imagenes `e1of4` a `e4of4` (`renpy.seen_image`).
- `chapter_select_used` y `persistent.enable_chapter_select` son herramientas de desarrollo; se descartan.

### Capitulos extra (distinto a lo que decia el plan)
El plan decia "bloqueados hasta terminar todas las rutas". El juego original desbloquea de forma progresiva (`src/extra_chapters_menu.rpy`):
- Con 0 finales vistos no hay extras.
- Cada final visto desbloquea mas capitulos de las dos series (Trish: x4-x6, Naomi: x7-x9); x1 a x3 estan disponibles desde el primer final.
- `x10` (RAYmba) requiere los 4 finales y los 9 capitulos extra anteriores completos (`persistent.bonus_chapters == 0b111111111`).
- Cada capitulo extra marca su bit en `persistent.bonus_chapters` al terminar (9 bits).
- Al terminar `x10` se activa `persistent.use_epilogue_menu` (cambia el menu principal a una imagen "big ending"). En el port no aplica porque el titulo es negro con logo.
- **Decision para la Fase 2:** replicar la logica progresiva (cuesta 13 bits: 4 de finales + 9 de extras) o usar la regla simple del plan. Recomendacion: replicar la original.

### Material picante
- Variable: `persistent.lewd` (por defecto `False`). Hay un interruptor en Opciones que se descarta.
- Condiciones en la historia: 3 (`script/3...:2283` imagen `lesbo` 20 s; `script/5...:4480`; `script/7...:38` imagen `fangonamp`).
- Imagenes: carpeta `images/NotForKids!` (bikini, fangonamp base/text, lesbo) y la pestana "Lewd" de la galeria (3 elementos).
- En el port: `PICANTE = True`; el compilador deja solo la rama activa. No hay nada mas que depende de la variable.

### Texto leido, "visto" y galeria
- Ren'Py marca como leido cada dialogo; el juego trae un ID unico por linea (`id chapter_5_ad464e5e`) que une cada dialogo con su bloque `translate es` en `tl/es/`. El compilador puede usar ese ID directamente (sin calcular hashes).
- Lineas de dialogo en `script/`: 14,691. Un bit por linea son unos 1.8 KB en la memory card.
- La galeria usa `renpy.seen_image(nombre)`: una imagen esta desbloqueada si alguna vez se mostro con `show` o `scene`. El motor debe marcar un bit por cada imagen mostrada.
- Galeria (`src/gallery_dataset.json`): CG 108, Fullbody 20, Backgrounds 72, Lewd 3 (condicionada a `persistent.lewd`), Animations 0. Total 203 elementos. Tambien hay 28 llamadas a `renpy.mark_image_seen` que marcan imagenes sin mostrarlas.
- Hay 1 video: `images/animations/fang tail.webm` (VP9, 1920x1080, 120 fotogramas, 5 s en bucle). Se usa en el capitulo 5 y en la galeria. Decision D3: se convierte a animacion por fotogramas.

### Traduccion al espanol
- Cobertura de dialogo: 14,694 bloques traducidos contra 14,691 lineas de dialogo; ningun bloque vacio. Los 63 bloques "iguales al original" son interjecciones (`Hmmm...`) o nombres, no faltantes reales.
- Cadenas de menus, nombres y pantallas estan en `translate es strings` (748 pares, 0 vacios).
- Hay 39 imagenes con texto traducido en `tl/es/images/` (reemplazan imagenes con texto embebido, p.ej. `door auditorium text`, `insultlayers/text1-9`, `the ending`). El pipeline de imagenes (Fase 4) debe usar la version en espanol cuando exista.
- Caracteres especiales a incluir en la fuente: `¡¿ÁÉÍÑÓÚàáéíñóöúü‘’…` (los simbolos `♪✔✘⬆⬇` son de la interfaz). Total de caracteres distintos: 115.
- Texto en espanol sin etiquetas: unos 750 KB en UTF-8.

### Logo y menu
- Logo del titulo: `gui/snootgame.png`. Existe una variante `gui/sneedgame.png` que sale al azar (`persistent.splashtype == 1`, easter egg); se descarta.

### Audio
- Musica: 69 pistas, 77.5 minutos, 74 MB (OGG).
- Efectos: 110 archivos, 42.6 minutos en total, pero casi todo son bucles ambientales largos (`windLightLoop`, `rainLoop`, de mas de 2 min). Solo hay 7 sonidos de interfaz (WAV) que se descartan.
- Canales usados: `music`, `music1/2` (crossfade, 8 usos), `sound`, `ambient`, `ambient1-3` (utilizados ~210 veces) y `audio`.
- No hay voces.

### Python de la historia
- Menus hechos en Python (`renpy.display_menu(randomize_choices(...))`, 14 usos): el orden de las dos opciones es aleatorio y algunos arman el nombre del salto (`renpy.jump(_value + chr(0x61 + _tick))`) en un bucle de "Snot / Interrupt". Hay que traducirlos a mano.
- 190 de 245 bloques de Python se traducen automaticamente (asignaciones, volumen de musica, marcar imagen vista). 28 van a mano; 22 son descartables; 5 se revisan.
- Variables de historia: `anonscore`, `fangscore`, `wingStory`, `late_to_spears`, `punched_into_flowerbed`, `TalkedWithTrish`, `LeftStage`, `ending_route_number` y contadores auxiliares. Son pocas.

### Partes dificiles de portar (resumen)
1. **Ambientes y musica a la vez**: el CD solo puede reproducir un stream XA; la musica XA y los ambientes (bucles de minutos) no pueden sonar juntos. Hay que convertir los ambientes a VAG cortos en bucle (limite de 512 KB de RAM de sonido) o decidir por escena.
2. **Texto en imagenes**: 39 imagenes con texto traducido y las "insultlayers" se componen en pantalla; hay que resolverlas en la Fase 4.
3. **ATL/animaciones**: miles de lineas de movimiento (`easein_cubic`, `parallel`, `repeat`) en `show ... at` y `transform`; el motor solo soportara un subconjunto (posiciones fijas, quizá deslizamientos simples).
4. **Transiciones**: `Dissolve` con ~40 duraciones distintas, `Fade`, `vpunch/hpunch`, `MoveTransition`; se aproximan a unas pocas.
5. **Menus en Python con orden aleatorio** y saltos con nombre armado.
6. **Imagenes de 1920x1080** (fondos, CGs, personajes de 1500 px de alto) a 320x240: perdida grande, sobre todo en CGs con texto.
7. **Sistema de "visto"**: bits por imagen mostrada y por linea de dialogo, con el modo saltar (R1) que se detiene en lo no leido.
8. **Capitulos extra progresivos** y logica de finales con 13 bits de progreso.
9. **Texto**: 14.7 mil lineas con etiquetas `{cps}` (2,830), `{w}`, `{nw}`, `{fast}`, `{i}`, `{size}`, `{alpha}` que el motor debe interpretar o el compilador simplificar.
10. **Video** `fang tail.webm` y las 431 definiciones de imagen (capas/expresiones con `layeredimage` y composiciones en `image_definitions.rpy`).
