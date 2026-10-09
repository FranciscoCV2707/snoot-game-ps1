# Pipeline de imagenes y formato IMG1 (Fase 4)

## Como se usa
```powershell
python -m tools.script_compiler.compile      # genera build/data/meta.json (recetas de imagen)
python -m tools.images.convert               # genera build/data/IMG/*.IMG, index.bin, MCICON.BIN y los reportes
```
Reportes: `build/reports/imagenes.md` (numeros) y `build/reports/arte/*.html` (hojas de contacto: imagen original reducida y convertida, con vista CRT para los fondos), `build/reports/arte/fang_tail.gif` (animacion del video).

## Que hace
1. **Renderiza** cada receta de imagen a su resolucion original: archivos, composiciones, capas (`layeredimage`, con posicion y giro), efectos (blur, sepia, recorte, escala, alfa, matriz de color), color solido, mascaras alfa y fotogramas de video. Las imagenes traducidas de `tl/es/` reemplazan a las originales (carteles, textos de fondos, finales), como en Ren'Py.
2. **Reduce a 1/6** (1920x1080 -> 320x180) con Lanczos y alfa premultiplicado (sin halos).
3. **Recorta**: los sprites pierden el borde transparente y la zona que el compilador sabe que nunca se ve en pantalla (por ejemplo, los pies de personajes que miden mas que la pantalla). El tamano logico se conserva para colocar el sprite igual que en el juego.
4. **Cuantiza a 8 bits** con el cuantizador octree y dither ordenado con la matriz de la PS1 (D5): fondos con paleta propia de 256 colores; sprites con una paleta de 255 colores compartida por carpeta (todas las expresiones de un personaje y atuendo), mas el indice 0 transparente. Ningun color visible vale `0x0000`.
5. **Efectos translucidos** (vineta `iris`, brillos): el alfa se convierte en tramado ordenado.
6. **Imagenes enormes** (mas de ~90,000 pixeles): se guardan a media resolucion (flag bit1) y el motor las dibuja al doble.
7. **Comprime con LZ4** (D9).

## Formato `Innnn.IMG` (little-endian)
```
0x00  "IMG1"
0x04  u8   tipo: 0 fondo/CG, 1 sprite, 2 color solido, 3 vacio
0x05  u8   flags: bit0 el indice 0 es transparente, bit1 el bitmap esta a media resolucion
0x06  u16  ancho logico   (a escala de 320x240)
0x08  u16  alto logico
0x0A  u16  x, y, ancho y alto del bitmap dentro del tamano logico (el ancho se rellena a par)
0x12  u8[4] r, g, b, a del color solido (solo tipo 2)
0x16  u16  numero de colores de la paleta
0x18  u16[256] paleta en formato PS1 (BGR 5-5-5)
      u32 tamano sin comprimir, u32 tamano comprimido
      datos: indices de 8 bits, fila por fila, bloque LZ4 sin cabecera
```
El motor sube los indices a VRAM como palabras de 16 bits (2 pixeles por palabra) y la paleta a una fila de CLUT. Los fondos de 320 px se dibujan como dos sprites (256 + 64 px). Las imagenes altas (CG de 745 y 1350 filas) se suben por franjas.

`IMG/index.bin`: `"IDX1"`, u16 cantidad y, por imagen, `u8 tipo, u8 sprite, u16 ancho, u16 alto, u16 bit de galeria (0xFFFF = ninguno), u8 final (1 a 4), u32 tamano comprimido, u32 tamano sin comprimir`.

`MCICON.BIN`: 16 colores PS1 (32 bytes) y el icono de 16x16 en 4 bits (128 bytes) para la cabecera del archivo de memory card (D10).

## Casos especiales resueltos
- **Imagenes animadas**: pases de diapositivas (`fangphonegallery`, `projector9_blur`), capas animadas de los telefonos y el video `fang tail` (D3) se convierten en varias imagenes mas eventos de la tabla ANIM (`docs/bytecode.md`). El video `fang tail` se convierte por **parches**: una imagen base (el primer cuadro, 30 KB) y 38 parches, que son el rectangulo de cada cuadro elegido que difiere de la base. El movimiento se muestrea a 12 cuadros por segundo y las pausas quedan como un solo cuadro largo. Base y parches comparten paleta y alineacion del tramado, asi que los bordes del parche no se notan. El motor dibuja la base y encima un sprite (`fang_tail_movie~patch`) que cambia de parche con eventos de la tabla ANIM en bucle: 405 KB sin comprimir en RAM, 256 KB en disco. Aparece tambien en la pestana *Animations* de la galeria (`meta.json` guarda los parches y sus tiempos).
- **Copias volteadas** (`im.Flip`): no se duplican; el motor usa el bit de espejo.
- **Interfaz**: logo del titulo (a 1/3 de escala) y candado de los extras generado por codigo.

## Resultados
Ver `build/reports/imagenes.md`: 653 imagenes, 21 MB sin comprimir y unos 10 MB en disco (~5,000 sectores, 1.5% de un CD). El pico de sprites visibles a la vez es de 215 KB (escena del extra x7), dentro de los 320 KB previstos; el simulador lo calcula descontando lo que queda tapado por una imagen opaca de pantalla completa (`build/reports/cobertura.md`).
