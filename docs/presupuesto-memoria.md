# Presupuesto de memoria, compresión y memory card

Basado en D4 (320x240), D5 (8 bits con dither ordenado), D7 (cargas por paquetes) y D8 (audio). Los números de imágenes y texto vienen de la auditoría y de `proto_compare.py`; los tamaños del motor son estimaciones a confirmar en las Fases 6 a 8.

## 1. VRAM (1024x512 palabras de 16 bits = 1 MB)
Todas las coordenadas en palabras de 16 bits. Una textura de 8 bits ocupa media palabra por píxel.

| Región | Posición | Tamaño | Uso |
|---|---|---|---|
| Framebuffer A | (0,0) 320x240 | 150 KB | pantalla |
| Framebuffer B | (0,240) 320x240 | 150 KB | doble buffer |
| Paletas (CLUT) | (0,480) 320x32 | 20 KB | 32 filas; una paleta de 256 colores por fila (512 B) |
| Fondos | (640,0) y (832,0), 160x180 cada uno | 2 × 56 KB | fondo actual y fondo entrante (transición) |
| Sprites de personajes | x 320-639, y 0-511 | ~250 KB usados de 320 | asignador por estantes; hasta ~12 sprites de ~21 KB |
| Fuente y UI | (960,0) 64x256 y alrededor | ~50 KB | fuente 4 bits (atlas 256x256), caja de texto, iconos |
| **Total en uso** | | **~740 KB (71%)** | **29% libre** |

Reglas del hardware que cumple el diseño:
- Una textura de 8 bits vive dentro de una página de textura de 128 palabras de ancho (256 px) por 256 de alto, con base en x múltiplo de 64. Un fondo de 320 px de ancho se dibuja como dos sprites (256 px + 64 px) en dos páginas contiguas.
- Los fondos usan las filas y=0 (y 256 si se agregan más ranuras), sin cruzar el límite de 256 de la página.
- Los fondos extra (en espera) viven en RAM y se suben a VRAM cuando se usan (~2-3 ms por DMA).
- La transición de disolver usa el framebuffer trasero como textura de 15 bits (se diseña en la Fase 8). No se reserva una región aparte.

## 2. RAM (2 MB)
| Uso | Tamaño |
|---|---|
| BIOS y vectores (reservado) | 64 KB |
| Motor: código, datos y librerías | ~250 KB |
| Pila | 32 KB |
| Búferes de GPU (2 × (32 KB primitivas + 4 KB tabla de orden)) | 72 KB |
| Script del capítulo (máx. 128 KB por capítulo) | 128 KB |
| Tabla de texto del capítulo (el capítulo 11 tiene 1,362 líneas ≈ 80 KB) | 128 KB |
| Búfer de carga / caché de paquetes (D7) | 640 KB |
| Búfer de descompresión (un recurso a la vez) | 128 KB |
| Índices (imágenes, audio, paquetes, hablantes, posiciones) | 64 KB |
| Memory card (2 copias de 8 KB) | 16 KB |
| Bits de progreso (texto leído, imágenes vistas, finales) | 4 KB |
| **Total en uso** | **~1,526 KB (75%)** |
| **Libre** | **~522 KB (25%)** |

El búfer de carga también sirve para preparar las subidas a la RAM de sonido (SPU, 508 KB): los efectos de un paquete se leen allí y se envían por DMA.

## 3. Compresión en disco (D9)
Medición sobre muestras reales de los fondos, sprites y texto del juego (se repite con la herramienta de la Fase 4):
| Dato | LZ4 HC | zlib (referencia) |
|---|---|---|
| Fondos 8 bits con dither ordenado (12 al azar) | 0.66 del tamaño | 0.55 |
| Sprites 8 bits con transparencia (10) | 0.17 | 0.14 |
| Texto en español | 0.55 | 0.42 |
| Música XA y efectos VAG | no se comprimen (ya son ADPCM) | - |

**Decisión:** fondos, sprites, bytecode y texto en **LZ4** (compresión máxima en la PC, decodificador simple en C de ~40 líneas, muy rápido en la R3000). La compresión se hace por recurso y el índice guarda ambos tamaños.
- Motivo: el cuello de botella es el CD (~300 KB/s). Un paquete típico (4 fondos + 8 sprites) pasa de ~400 KB a ~180 KB: se ahorran unos 0.7 s de lectura por cada ~80 ms de descompresión.
- La descompresión corre con la música ya reanudada o con el fundido de entrada.
- zlib comprimiría un poco más, pero su decodificador es mucho más lento y grande para la PS1.

## 4. Memory card (D10)
Un bloque mide 8,192 bytes; los primeros 512 son la cabecera de la consola (firma "SC", título, paleta del icono y 3 cuadros de icono), quedan **7,680 bytes útiles**.

| Sección | Cálculo | Tamaño |
|---|---|---|
| Control | versión del formato, número de guardado, checksum de cada sección | 16 B |
| Opciones | volumen de música y de efectos | 4 B |
| Texto leído | 14,691 líneas de diálogo → 1,837 B; se reservan 16,384 bits | 2,048 B |
| Imágenes vistas | hasta 1,024 imágenes (galería + finales) | 128 B |
| Finales y extras | 4 bits de finales + 9 bits de capítulos extra (D1), tiempo total de juego | 8 B |
| 3 ranuras de guardado | 384 B cada una (ver abajo) | 1,152 B |
| **Total de datos** | | **3,356 B** |
| Más cabecera de la consola | | **3,868 B de 8,192 (47%)** |

Contenido de una ranura (≈330 B, se redondea a 384): capítulo u16 y offset de la instrucción `SAY` actual u32, 64 variables i16 (128 B), pila de `CALL` (8 niveles × 6 B + profundidad), escena (fondo u16 y 8 sprites × 9 B), música (pista u16, posición en sectores u32, volumen), 4 ambientes, volúmenes de canales, paquete de carga u16, título del capítulo u8, tiempo de juego u32 y número de guardado u32. Un guardado se hace siempre sobre un `SAY`: al cargar se reconstruye la escena, se carga el paquete y se vuelve a ejecutar esa línea (las animaciones de sprites reinician).

**Decisión:** el archivo ocupa **1 bloque**, y se guardan **dos copias alternadas** (2 bloques de 15): archivos `SNOOTGAME-A` y `SNOOTGAME-B`, cada uno con número de guardado y checksum. Al arrancar se lee el de número mayor que pase el checksum; si la consola se apaga a mitad de un guardado queda la copia anterior intacta. Los IDs de texto son estables (se asignan en el orden del script original), así que un texto leído nunca cambia de bit.

Cuándo se escribe: al elegir *Guardar*, automáticamente al llegar a un final (aviso "Guardando progreso..."), al salir al título y al salir de la pantalla de Opciones si cambiaron los volúmenes.
