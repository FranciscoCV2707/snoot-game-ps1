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

## 2026-10-08 - D4: Resolución 512x240 (propuesta, pendiente de tu visto bueno)
**Decisión:** modo de video 512x240 progresivo, imagen 16:9 en letterbox de 512x180 centrada en la pantalla 4:3 (barras negras de 30 líneas arriba y abajo). La caja de texto se superpone sobre la parte baja, incluida la barra.
**Motivo:** `tools/images/proto_compare.py` compara 320x240, 512x240 y 640x480i (`build/reports/proto/index.html`).
- 320x240: se ve pixelado (personajes y fondos con detalle perdido).
- 512x240: claramente más nítido; dos framebuffers cuestan 480 KB y dejan 544 KB de VRAM.
- 640x480i: más nítido aún, pero parpadea en CRT y un fondo 15 bits ocupa 450 KB; no cabe cómodo con personajes y fuente.
**Consecuencia:** como los píxeles son más angostos (relación 0.625), los sprites y la fuente se pre-estiran 1.6x en horizontal en la conversión (lo hace la PC).

## 2026-10-08 - D5: Fondos 15 bits con dither de hardware; personajes 8 bits
**Decisión:** fondos y CGs en color directo de 15 bits (184 KB por fondo a 512x180) usando el dither por hardware de la PS1; personajes en 8 bits con paleta propia y transparencia por umbral.
**Motivo:** 8 bits con 256 colores de paleta pierde color y se ve posterizado en escenas con degradados (acuario, noche); 15 bits con dither se ve limpio.
**Costo:** el doble de tamaño en CD y de tiempo de carga por fondo (~0.6 s a 2x). Depende de la prueba XA + CD (ver abajo): si la carga corta la música, se pasa a 8 bits solo en los fondos que lo permitan.

## 2026-10-08 - D6: Fuente y caja de texto
**Decisión:** fuente de ancho variable, unos 13 px de alto (sobre 240 líneas), caja de 3 líneas. El compilador divide en páginas los textos que no caben.
**Datos:** sobre 14,6 mil líneas de diálogo en español a 13 px: 57.8% caben en 1 línea, 32.2% en 2, 8.6% en 3 y solo 1.4% necesitan 4 o más.

## Observación para la Fase 4
- Los personajes se componen en capas (cuerpo + cara): en el prototipo Anon aparece sin cara porque se usó solo `anon neutral` base. El pipeline debe pre-componer cuerpo y expresión en la PC.

## Pendiente (Fase 2)
- Tu visto bueno a D4, D5 y D6.
- Prueba técnica XA + carga de datos del CD.
- Compresión, formato de la memory card, mapa de VRAM/RAM, `docs/bytecode.md`.
