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

## 2026-10-08 - D3: Video `fang tail.webm` descartado
**Decisión:** no se porta el video. Su entrada en la galería se omite (o se reemplaza por una imagen fija si existe).
**Motivo:** requiere el formato STR/MDEC y ocupa espacio y tiempo de motor por un solo extra de galería.
**Revisar:** si sobra tiempo al final del proyecto.

## Pendiente (Fase 2)
- Resolución de pantalla y formato de fondos (prototipos).
- Prueba técnica XA + carga de datos del CD.
- Fuente, compresión, formato de la memory card, mapa de VRAM/RAM, `docs/bytecode.md`.
