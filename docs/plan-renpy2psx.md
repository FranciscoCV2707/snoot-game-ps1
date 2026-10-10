# Plan: herramientas para portar juegos de Ren'Py a PS1 (renpy2psx)

Estado: propuesta. Se empieza despues de la v0.1 de Snoot Game y en un repositorio aparte; `snoot-ps1` no se toca.

## Objetivo
Una herramienta que tome un juego de Ren'Py y produzca un disco de PS1 jugable, con un reporte claro de lo que no se pudo
portar automaticamente. Lo especial de cada juego (minijuegos, pantallas propias) se agrega como codigo aparte.

## Que se reutiliza de snoot-ps1
| Parte | Origen | Trabajo |
|---|---|---|
| Parser y compilador del guion (dialogo, menus, variables, saltos, scene/show/hide, ATL, transiciones) | `tools/script_compiler` | Quitar casos de Snoot; mover nombres y rutas a la configuracion |
| Simulador y exploracion de rutas | `tools/simulator` | Casi sin cambios |
| Imagenes (paletas de 8 bits, media resolucion, translucidas, parches de video) | `tools/images` | Parametros por juego (resolucion de origen, presupuesto de VRAM) |
| Audio (XA por carriles, SPU-ADPCM, ambientes) | `tools/audio` | Parametros por juego |
| Motor (VM, escenas, transiciones, texto, audio, memory card) | `engine/` | Separar pantallas de Snoot del nucleo |
| Disco (mkpsxiso, tabla de sectores) | `tools/engine/build_game.py` | Generalizar nombres de archivos y secciones |
| Pruebas (emutest, playtest, auditoria contra Ren'Py) | `tools/engine`, `tools/audit` | Generalizar las etiquetas de inicio |

## Lo que no se automatiza
- Python arbitrario: se traducen expresiones simples (variables, comparaciones, aritmetica); el resto se reporta.
- Pantallas `screen` propias y minijuegos: se portan a mano como modulos en C.
- Video: se convierte a animacion por cuadros si cabe en memoria; si no, se reporta.
- Idiomas con muchos glifos (japones, chino): fuera del alcance inicial.

## Fases
### F1 - Separar motor y juego
- Archivo `game.toml` por juego: rutas del juego, idioma, etiqueta de inicio, nombre del disco, pantallas incluidas, icono.
- Seccion de UI generica en el disco (titulo, logo, creditos, galeria opcional) en vez de UI01 fijo de Snoot.
- Pantallas de Snoot (extras, chat del capitulo 4) como modulo aparte con ganchos (`hooks.c`).
- Criterio: Snoot Game sigue compilando igual con su `game.toml` y su modulo.

### F2 - Analizador
- `renpy2psx analyze <juego>`: reporte HTML/Markdown con lo soportado, lo que se ignora, Python no traducible, pantallas propias, tamano estimado de disco, VRAM y RAM.
- Base: `tools/audit/inventario.py`.
- Criterio: el reporte de Snoot coincide con lo que ya sabemos.

### F3 - Comando unico
- `renpy2psx build <juego>`: guion, imagenes, audio, motor y disco (lo que hoy hace `build.py`), con cache por hash.
- `renpy2psx test <juego>`: simulador + playtest en PCSX-Redux.

### F4 - Segundo juego
- Portar *The Question* (viene con el SDK de Ren'Py): corto, sin Python complejo.
- Criterio: se juega completo en DuckStation sin tocar el codigo del motor.

### F5 - Documentacion y empaque
- Guia de uso, formato de `game.toml`, como escribir un modulo de pantallas propias.
- Ejemplo de modulo (el chat de Snoot).

### F6 (opcional) - Mas cobertura
- Mas expresiones de Python, `screen` simples (botones e imagenes), `renpy.pause` con clics, NVL.
- Probar con un tercer juego mas grande.

## Riesgos
- Juegos con mucho arte a 1080p: la conversion a 320x240 puede perder texto incrustado en imagenes (se reporta).
- Uso intensivo de Python o de `screen`: el port automatico cubre poco y el resto es trabajo manual.
- Licencias: cada port necesita permiso del autor del juego.
