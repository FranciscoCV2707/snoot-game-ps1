# Presupuesto de audio y disco

Generado por `tools/audio/audit_audio.py`.

## Musica

- Pistas en `audio/OST`: 71; usadas por la historia: 63; sin usar: 8.
- Minutos de musica usada: 74.1.
- Sin usar (no se convierten): Amberlight Brilliance D ending, amberlight brillance live end, dinolove, good faith reprise end, good faith synth finale end, goodfaithcover, ost cover, startup

| Formato XA | Carriles | Sectores (agrupado simple) | Relleno | Sectores (carriles empaquetados) | MB empaquetado | % de un CD de 74 min |
|---|---|---|---|---|---|---|
| 37.8k estereo | 8 | 100472 | 17091 | 84280 | 187.8 | 25.3% |
| 37.8k mono | 16 | 60048 | 18341 | 42784 | 95.3 | 12.8% |
| 18.9k estereo | 16 | 60048 | 18341 | 42784 | 95.3 | 12.8% |
| 18.9k mono | 32 | 40416 | 19546 | 31136 | 69.4 | 9.4% |

## Efectos

- Archivos de efectos usados: 105 (65 de un solo disparo, 40 en bucle).
- Segundos de un solo disparo: 308.4; segundos de bucles recortados a 6 s: 228.0.

RAM de sonido disponible: 508 KB.

| Frecuencia VAG | Un solo disparo (KB) | Bucles recortados (KB) |
|---|---|---|
| 22050 Hz mono | 3795 | 2805 |
| 16000 Hz mono | 2753 | 2035 |
| 11025 Hz mono | 1897 | 1402 |

Efectos mas largos:

- `audio/effects/windLightLoop.ogg`: 131.22 s, bucle, canales ambient, ambient2, usado 3 veces en 1 capitulos
- `audio/effects/rainLoop.ogg`: 130.42 s, bucle, canales ambient, usado 1 veces en 1 capitulos
- `audio/effects/outdoorNatureLoop.ogg`: 120.56 s, bucle, canales ambient, ambient1, usado 22 veces en 5 capitulos
- `audio/effects/dinomoesLoop.ogg`: 118.36 s, bucle, canales ambient, usado 7 veces en 3 capitulos
- `audio/effects/schoolLoop.ogg`: 115.48 s, bucle, canales ambient, usado 15 veces en 5 capitulos
- `audio/effects/outdoorLoop.ogg`: 106.96 s, bucle, canales ambient, usado 18 veces en 10 capitulos
- `audio/effects/windShooterLoop.ogg`: 106.9 s, bucle, canales ambient, usado 3 veces en 1 capitulos
- `audio/effects/radioChatterLoop.ogg`: 106.44 s, bucle, canales ambient1, ambient2, ambient3, usado 3 veces en 1 capitulos
