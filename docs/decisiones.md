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

## Observación para la Fase 4
- Los personajes se componen en capas (cuerpo + cara): en el prototipo Anon aparece sin cara porque se usó solo `anon neutral` base. El pipeline debe pre-componer cuerpo y expresión en la PC.

## Pendiente (Fase 2)
- Compresión, formato de la memory card, mapa de VRAM/RAM, `docs/bytecode.md`.
