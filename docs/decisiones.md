# Decisiones técnicas

## 2026-10-08 - D1: Capítulos extra con lógica progresiva
**Decisión:** replicar la lógica del juego original en lugar de la regla "todas las rutas".
- 0 finales vistos: sin extras. Con el primer final: x1, x2, x3.
- Cada final visto desbloquea más capítulos de las series Trish (x4-x6) y Naomi (x7-x9).
- x10 requiere los 4 finales y los 9 extras terminados.
**Motivo:** cuesta solo 13 bits en la memory card (4 finales + 9 extras), mantiene la experiencia original y evita inventar reglas nuevas.
**Alternativa descartada:** desbloqueo único al terminar todas las rutas (menos fiel al juego).

## 2026-10-08 - D2: Ambientes como VAG cortos en bucle
**Decisión:** la música va en XA (un solo stream) y los ambientes y efectos van en VAG en la RAM de sonido (512 KB).
- Los ambientes largos (rain, wind, etc.) se recortan a un bucle corto (objetivo 3 a 6 s) a baja frecuencia (11 a 16 kHz mono).
- Se cargan por capítulo; el presupuesto exacto se mide en la Fase 5.
- Si un ambiente no suena bien recortado, se baja la frecuencia en vez de usar XA.
**Motivo:** el CD solo reproduce un stream XA a la vez; música y ambiente suenan juntos en la historia (unos 210 usos).
**Alternativa descartada:** ambientes en XA con silenciar la música (cambia la escena sonora).

## 2026-10-08 - D3: Video `fang tail.webm` como animación por fotogramas
**Decisión:** no se usa video real (STR/MDEC). Se convierte a una animación en bucle de pocos fotogramas, tratada como una imagen animada por el motor.
- Original: VP9, 1920x1080, 120 fotogramas a 23.98 fps (5 s), en bucle. Se usa en el capítulo 5 (`show fang_tail_movie`) y en la galería (`fang_tail_movie`, miniatura aparte).
- Objetivo inicial: 8 a 16 fotogramas a 6 a 10 fps, en 8 bits con paleta, a la resolución de fondo elegida. Se afina en la Fase 4 viendo cuál se ve fluida sin pasar de ~1 MB de VRAM/disco.
- Si el área animada es pequeña (solo la cola), se animan solo esos recortes sobre un fondo fijo para ahorrar VRAM.
**Motivo:** mantiene el efecto sin el costo de MDEC; el motor ya necesita cambiar texturas por tiempo.
**Impacto:** el bytecode necesita una instrucción de animación simple (lista de fotogramas, tiempo por fotograma, bucle). Se incluye en la Fase 2 (`docs/bytecode.md`).
**Revisión (Fase 4, a pedido del usuario):** los 10 fotogramas completos se veían raros. Ahora es una animación por parches (imagen base más 38 rectángulos que cambian, a 12 cuadros por segundo en movimiento), con una calidad mucho más cercana al video y 405 KB en RAM.

## 2026-10-08 - D4: Resolución 320x240 (elegida por el usuario)
**Decisión:** modo de video 320x240 progresivo, imagen 16:9 en letterbox de 320x180 centrada en la pantalla 4:3 (barras negras de 30 líneas arriba y abajo). La caja de texto se superpone sobre la parte baja, incluida la barra.
**Motivo:** el usuario comparó 320x240, 512x240 y 640x480i (`tools/images/proto_compare.py`, `build/reports/proto/index.html`) y prefirió 320x240 con 8 bits y dither ordenado. Además es la opción más segura para el hardware:
- Píxeles cuadrados: no hay que pre-estirar sprites ni fuente.
- Dos framebuffers cuestan solo 300 KB; quedan ~720 KB de VRAM, suficiente para varios fondos precargados.
- Fondos de 56 KB: cargan en ~0.2 s, lo que reduce el riesgo de la prueba XA + CD.
**Costo conocido:** menos detalle que 512x240 (personajes y texto de fondo más pixelados). El convertidor de imágenes (Fase 4) queda parametrizado por resolución para poder subir a 512x240 más adelante si se desea.

## 2026-10-08 - D5: Fondos y personajes en 8 bits con dither ordenado
**Decisión:** fondos, CGs y personajes en 8 bits con paleta (256 colores) y dither ordenado, 56 KB por fondo. Personajes con paleta propia y transparencia por umbral.
**Motivo:** elección del usuario por apariencia; también es lo más pequeño y rápido de cargar.
**Mitigación del costo (posterización en degradados, p.ej. acuario y noche):** paleta propia por imagen (no una global) con el cuantizador **octree** y dither ordenado con la matriz de la PS1 a intensidad 2. En pruebas (acuario, cuarto oscuro, azotea nocturna) baja el error de color medio de 6.9 a 5.1, 5.4 a 4.4 y 6.2 a 4.6 respecto a median cut, y conserva luces y tonos (el morado del acuario). Se verifica en la hoja de contacto de la Fase 4. Las imágenes donde aun falle se pueden pasar a 15 bits de forma individual (el formato lo permite por imagen).

**Proporción:** las imágenes originales son 16:9 y se muestran en un letterbox de 320x180 dentro de la pantalla 4:3, por lo que no se deforman ni se ven aplastadas. Los personajes se escalan por el mismo factor.

## 2026-10-08 - D6: Fuente y caja de texto
**Decisión:** fuente de ancho variable, unos 13 px de alto (sobre 240 líneas), caja de 3 líneas. El compilador divide en páginas los textos que no caben.
**Datos:** sobre 14,6 mil líneas de diálogo en español a 13 px: 57.8% caben en 1 línea, 32.2% en 2, 8.6% en 3 y solo 1.4% necesitan 4 o más.

## 2026-10-08 - D7: Música XA y carga de datos (resultado de la prueba)
**Prueba:** `experiments/xa_test` en DuckStation (sin aceleración del CD), 8 canales XA entrelazados de 37.8 kHz estéreo.
| Prueba | Pausar | Carga | Reanudar (ack) | Hueco medido |
|---|---|---|---|---|
| 1 fondo (58 KB), con pausa | - | 550 ms | 16 ms | 600 ms |
| 4 fondos + capítulo (360 KB), con pausa | 33 ms | 1850 ms | 0 ms | 1883 ms |
| 1 fondo sin pausar la música | - | - | - | la música se detiene y no vuelve sola |
- Reproducir, cambiar de canal en caliente (L1/R1) y el formato de 8 canales entrelazados funcionan sin cortes.
- Cargar datos con la música sonando la detiene siempre; hay que pausar, cargar y reanudar en la posición guardada. La reanudación fue exacta.
- Modelo de costo: carga ≈ 0.36 s de búsqueda + 3.3 ms por KB (≈ 300 KB/s). El tiempo "Reanudar" solo mide el ack del comando; falta sumar la búsqueda de regreso a la música (estimada 0.1 a 0.3 s).

**Decisión (estrategia de carga):**
1. La música se pausa durante las cargas y se reanuda en la posición exacta (cuenta de sectores). Se enmascara con bajada y subida de volumen del CD (`SpuSetCommonCDVolume`) y con el fundido de la propia escena.
2. **Sin `CdSearchFile` en tiempo de ejecución:** la tabla de sectores se precalcula en la PC y se carga una vez al arrancar.
3. **Paquetes de escena contiguos:** el CD se ordena por uso y cada lote (fondos + sprites + script) se lee de un solo golpe. Una búsqueda por lote, no por archivo.
4. **Lotes por segmento de música:** el compilador agrupa los recursos de todo el tramo entre dos cambios de música (`play/stop music`) y los carga en el cambio de pista, donde ya hay una pausa de la música. Presupuesto de caché: ~600 KB de RAM más VRAM libre para ~8 fondos y varios sprites.
5. El compilador reporta cuántas pausas "forzadas" quedan dentro de un mismo tema (la meta es cero o pocas por capítulo) para ajustar el reparto.
6. Música en 37.8 kHz estéreo se mantiene (el entrelazado de 8 canales no desperdicia espacio); se usa `tools/audio/xa_interleave.py`. Pistas de duración distinta se agrupan por longitud en un mismo archivo para no desperdiciar sectores de relleno.

**Descartado por ahora:** intercalar sectores de datos dentro del flujo XA (permite cargar sin pausar, pero ata los datos a cada pista y complica el CD). Se retoma solo si los huecos resultan molestos en la consola real.

## 2026-10-08 - D8: Música y efectos, calidad y espacio (`docs/presupuesto-audio.md`)
**Datos reales** (`tools/audio/audit_audio.py`): de 71 pistas, la historia usa 63 (74.1 min); 8 no se usan y no se convierten. Hay 105 efectos usados: 65 de un solo disparo (308 s en total) y 40 ambientes en bucle (de más de 2 minutos cada uno).
**Decisión:**
1. **Música en mono (cambio pedido por el usuario):** XA 37.8 kHz **mono** (4 bits), con 16 carriles entrelazados a 2x. Conserva los agudos (ancho de banda ~18 kHz, igual que el estéreo de 37.8 kHz) y solo pierde la imagen estéreo. Pesa la mitad que el estéreo: 42,784 sectores empaquetados (95 MB, 12.8% de un CD) contra 84,280 (188 MB, 25.3%).
   - Se descartó 18.9 kHz mono: con 32 carriles el empaquetado queda limitado por la pista más larga y solo ahorra ~25% más (31,136 sectores, 9.4%), con pérdida clara de agudos (ancho de banda ~9 kHz).
2. **Ahorro por carriles:** en vez de dejar relleno (18,341 sectores, 30% en mono), las pistas se empaquetan en 16 carriles de igual duración, una tras otra dentro de cada carril. El motor busca el inicio de cada pista en su carril. Se implementa en la Fase 5 (`xa_interleave.py` pasa a aceptar listas de pistas por carril). `experiments/xa_test` ya se regeneró con 16 carriles mono para validarlo en emulador.
3. **Intro y bucle:** pistas con intro (`... intro` + `... loop`) se guardan seguidas en el mismo carril; el reinicio del bucle es una búsqueda corta dentro del archivo. Si en consola real el hueco del bucle molesta, las pistas cortas que se repiten se graban dos veces seguidas.
4. **Efectos de un disparo:** VAG a 22.05 kHz mono (≈3.8 MB en total).
5. **Ambientes:** se recortan a un bucle de ~6 s con empalme suave y se graban a 16 kHz mono (≈2.0 MB en total; ruido de fondo, pérdida inaudible). Se cargan dentro de los paquetes de escena (D7); cada paquete debe caber en los 508 KB de RAM de sonido.
6. **Reserva de espacio:** si algún día falta espacio, la palanca es bajar solo las pistas menos importantes a 18.9 kHz estéreo (mitad de tamaño). No hace falta ahora.

**Presupuesto estimado del disco (un CD de 74 min, 333,000 sectores):**
| Contenido | Sectores | % |
|---|---|---|
| Música XA mono 37.8 kHz (con carriles) | ~42,800 | ~13% |
| Imágenes (≈250 fondos/CG + ≈330 sprites, 8 bits), duplicadas en paquetes | ~21,000 | ~6% |
| Efectos VAG, duplicados en paquetes | ~10,000 | ~3% |
| Motor, bytecode, texto, índices | ~2,000 | <1% |
| **Total estimado** | **~76,000** | **~23%** |
Margen libre: ~77%. Se confirma con números reales en la Fase 9. Nota: el peso de la música en el CD no afecta los tiempos de carga (se reproduce en flujo continuo); el beneficio de bajarlo es dejar más espacio para duplicar recursos en paquetes contiguos y un `.bin` más pequeño.

## 2026-10-08 - D9: Compresión LZ4 en fondos, sprites, bytecode y texto
**Decisión:** LZ4 (máxima compresión en la PC) para fondos, sprites, `.VNB` y texto; sin compresión para XA y VAG.
**Datos medidos:** fondos 0.66, sprites 0.17, texto 0.55 del tamaño original. Un paquete típico baja de ~400 KB a ~180 KB y ahorra ~0.7 s de lectura por ~80 ms de descompresión.
**Detalle:** `docs/presupuesto-memoria.md` sección 3.

## 2026-10-08 - D10: Memory card en 1 bloque con dos copias alternadas
**Decisión:** un solo archivo de datos de 3,868 B (47% de un bloque) con 3 ranuras, progreso y opciones; se guarda en dos archivos alternados (`SNOOTGAME-A`/`-B`) usando 2 de los 15 bloques, para sobrevivir a un apagado durante el guardado. 14,691 líneas leídas ocupan 2 KB con margen para futuras ediciones.
**Detalle:** `docs/presupuesto-memoria.md` sección 4.

## 2026-10-08 - D11: Presupuesto de VRAM y RAM
**Decisión:** VRAM en uso ~740 KB (71%, 29% libre): dos framebuffers de 320x240, 32 filas de paletas, 2 ranuras de fondo, ~250 KB de sprites con asignador por estantes y fuente/UI. RAM en uso ~1,526 KB (75%, 25% libre) con 640 KB de búfer de carga. Ambos cumplen el criterio de ≥20% libre.
**Detalle:** `docs/presupuesto-memoria.md` secciones 1 y 2.

## 2026-10-08 - D12: Huecos de música (bucle y reanudación)
**Datos** (`tools/audio/segment_stats.py`): los 334 tramos de música de la historia son largos comparados con las pistas (media de 71 s): casi 8 de cada 10 se repiten más de una vez, algunos 10 veces o más (estimación en el peor caso: cuenta las dos ramas de cada decisión). Repetir un bucle exige buscar hacia atrás en el CD, y eso corta el audio unos 0.3-0.5 s. Un flujo XA solo avanza hacia adelante; cambiar de canal sí es sin hueco, pero no evita el retroceso.
**Decisión:**
1. **Copias seguidas por pista:** cada pista que se repite se graba varias veces seguidas en el CD (objetivo 90 s de audio continuo, máximo 3 copias). Costo: música de ~20.7% del CD en vez de 12.8% (`+27,000 sectores`); disco total ~30%. Los parámetros (`LOOP_TARGET_SECONDS = 90`, `LOOP_MAX_COPIES = 3`) son ajustables; con 180 s y 4 copias sería ~34% de música.
2. **Rebobinado adaptativo:** el motor espera a la siguiente transición con fundido o disolver para volver al inicio; el cambio de imagen tapa el hueco. Las escenas cambian mucho más seguido que las copias se acaban (796 `scene` en la historia), así que casi todos los saltos quedan ocultos.
3. **Salto forzado:** si las copias se acaban sin transición, fundido de 120 ms grabado al final de cada copia y de entrada al inicio: sin chasquidos, solo un breve silencio.
4. **Reanudación tras cargas:** casi no ocurre. Las cargas se hacen al cambiar de pista (la música ya está en fundido). Las demás las coloca el compilador en una transición, y el volumen del CD baja y sube en 150 ms alrededor de la pausa.
5. El simulador reporta saltos y cargas forzadas por capítulo; si son muchos, se sube `LOOP_TARGET_SECONDS`.
**Descartado:** retocar el final con una cola en la RAM de sonido (alineación muy frágil sin consola real); música en CD-DA (74 min de audio llenan todo el disco).

## 2026-10-08 - D13: Personajes y fondos con capas (corrección del riesgo)
**Hallazgo:** revisando `src/image_definitions.rpy`, los personajes **no** se componen en capas: cada expresión es un archivo completo (`anon neutral.webp`, `fang angry.webp`...). En el prototipo Anon aparece sin cara porque su diseño no tiene rostro, no por una capa faltante. Mi nota anterior era un error de interpretación.
**Lo que sí se compone:**
- 245 definiciones `im.Flip`: se resuelven con el bit de volteo del sprite, sin duplicar imágenes.
- Fondos con texto traducido (`Composite(base, texto_es)`, 39 imágenes en `tl/es/images`): el pipeline pre-compone fondo y texto en la PC (una imagen final por fondo).
- Dos `layeredimage` de pantallas de teléfono: el compilador pre-renderiza una imagen por combinación de atributos que use la historia.
**Decisión:** pre-composición total en la PC; el motor solo dibuja una textura por cada imagen. Los sprites usan paleta propia por personaje (compartida entre sus expresiones) para que no cambien de color al cambiar de cara.

## 2026-10-08 - D14: Animaciones (rotación, zoom, desenfoque, color)
**Datos** (ATL de la historia, 2,957 bloques): casi todo es posición (`xalign`/`yalign`); `zoom` (~50 usos), `rotate` (~40), `xzoom` (~13), `matrixcolor` (10), `blur` (6), `alignaround` (2).
**Decisión:** se soportan todos, con técnicas de PS1:
- **Zoom, giro y espejo animados:** sprites dibujados como cuadriláteros texturizados (`POLY_FT4`); la GPU escala y gira sin costo notable.
- **Tinte y brillo (`matrixcolor`):** modulación de color de la primitiva (hasta 2x). Sin saturación.
- **`blur`:** las escenas desenfocadas son imágenes ya incluidas en el juego; un `blur` animado se hace con disolver entre nítida y desenfocada.
- **`shudder`/`wiggle` (`alignaround`):** vibración de posición con 2 a 4 claves en bucle.
- La tabla ANIM crece a 16 bytes por clave (zoom, xzoom, rotación, r/g/b). Detalle en `docs/bytecode.md` sección 5.
**Ampliación (a pedido del usuario, para conservar la fidelidad):** cambios de imagen dentro de un ATL (eventos), sonidos disparados desde un ATL, `repeat N` desenrollado (hasta 64 claves), `camera` (instrucción `CAMERA`), desenfoque de escena con variantes pre-renderizadas, `AlphaMask` (imagen pre-renderizada y recorte vertical animado) y las transiciones de movimiento y de fundido por blanco (tipos 5 y 6).
**No soportado (documentado):** `matrixcolor` de saturación, desenfoque en vivo, curvas elásticas exactas (se aproximan).

## Observación para la Fase 4
- Los sprites usan una paleta por personaje (D13). Pre-componer en la PC solo los fondos con texto traducido y las dos pantallas de teléfono.

## Pendiente (Fase 2)
- Revisión del usuario de `docs/bytecode.md` y de los presupuestos.
