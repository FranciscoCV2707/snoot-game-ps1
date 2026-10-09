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

## Pendiente (Fase 2)
- Resolución de pantalla y formato de fondos (prototipos).
- Prueba técnica XA + carga de datos del CD.
- Fuente, compresión, formato de la memory card, mapa de VRAM/RAM, `docs/bytecode.md`.
