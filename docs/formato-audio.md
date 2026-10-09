# Pipeline de audio y formatos (Fase 5)

## Como se usa
```powershell
python -m tools.script_compiler.compile   # genera build/data/meta.json (lista de audio y mezclas)
python -m tools.audio.convert             # genera MUSIC.XA, SFX/*.SPU, audio_index.bin y build/reports/audio.md
python experiments/xa_test/build_test.py --real   # disco de prueba con el MUSIC.XA real para escucharlo en un emulador
```

## Musica (`MUSIC.XA`)
- **Formato:** XA 37.8 kHz mono, 4 bits (D8), en un solo archivo con **16 carriles** entrelazados a 2x: el sector `n` del archivo es del carril `n % 16`, ranura `n / 16`. El archivo y el canal XA del sector son 1 y el carril. Sin banderas de fin de archivo (el motor cuenta sectores).
- **Nivel:** cada pista se lleva a -12 dB RMS con limite de -12 a +3 dB de ajuste y pico maximo de 0.97. Los stems de una misma cancion usan un nivel de grupo comun.
- **Duracion exacta:** cada pista se estira menos de 0.4% para que ocupe un numero entero de sectores; asi las copias del bucle se unen sin silencio.
- **Copias del bucle (D12):** objetivo de 90 s de audio continuo, hasta 3 copias seguidas por pista. Los fundidos al reiniciar los hace el motor con el volumen del CD (no estan grabados).
- **Familias `X intro`, `X loop`, `X end`** (3 en el juego): la intro y las copias del bucle van seguidas en un carril; el final (`end`) se graba en un **carril lateral alineado con el final de cada copia**, asi el motor puede pasar al final cambiando de carril, sin buscar en el CD.
- **Capas (stems)** del extra x9: Ren'Py suena varias pistas a la vez, pero el CD solo reproduce un flujo. El compilador convierte cada combinacion de stems activos en una **mezcla** (6 combinaciones); todas empiezan en la misma ranura de carriles distintos, por lo que `MUSIC_PLAY` con bandera de sincronizacion (bit1) cambia de carril sin perder la posicion. Los cruces de canciones (`music1`/`music2` con `stop music`) son simples reemplazos.
- **Empaquetado:** unidades repartidas en 16 carriles de igual duracion (primero los grupos sincronizados, luego las familias, luego el resto por tamano decreciente).

Resultado: 81,088 sectores (181 MB, 24.4% de un CD de 74 min), carriles de 9 minutos.

## Efectos y ambientes (`SFX/Snnn.SPU`)
- Efectos de un disparo: 22.05 kHz mono, ADPCM del SPU sin cabecera, sin normalizar (se conservan los niveles relativos del juego). Bloque final con bandera de fin sin repeticion.
- Ambientes: bucle de 6 s a 16 kHz, tomado del centro de la pista con un empalme de 0.5 s (fundido de potencia constante entre la cola y el inicio); bloque inicial con bandera de inicio de bucle y bloque final con fin y repeticion. Unos 54 KB cada uno.
- Total: 105 archivos, 5.8 MB. El reparto por paquetes de escena (508 KB de RAM de sonido) se hace en la Fase 9.

## Indice `audio_index.bin`
`"AIX1"`, u16 cantidad y por id de audio (la misma numeracion de las instrucciones del bytecode), 20 bytes: `u8 tipo (0 nada, 1 musica, 2 final de familia, 3 efecto, 4 ambiente), u8 carril, u8 copias, u8 banderas (bit0 bucle, bit1 sincronizada), u32 sector inicial relativo a MUSIC.XA (o 0), u32 duracion en ranuras (musica) o bytes (efecto), u32 auxiliar (para finales: ranuras de una copia del bucle; para efectos: frecuencia), u32 reservado`.

Para los finales de familia, `start` es el sector de la primera copia y el motor suma `k * ranuras_del_bucle * 16` para la copia `k`. `build/data/audio_out.json` guarda el detalle completo.
