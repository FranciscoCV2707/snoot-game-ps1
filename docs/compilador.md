# Compilador de scripts y simulador (Fase 3)

## Cómo se usa
```powershell
.\.venv\Scripts\Activate.ps1
python -m tools.script_compiler.compile        # original/ -> build/data
python -m tools.simulator --report             # explora todas las rutas -> build/reports/cobertura.md
python -m tools.simulator --dis 0 --limit 80   # desensambla el capítulo 0
python -m tools.simulator --explore            # resumen de la exploración
pytest                                          # incluye compilación completa y exploración
```
Salidas en `build/data/`: `SCRIPT/Cxx.VNB` (un capítulo por archivo, 39) y `SCRIPT/STORY.VNB` (flujo del juego), `TEXT_ES.BIN` (texto en español con códigos de control y ya partido en líneas y páginas) y `meta.json` (tablas de imágenes, audio, hablantes, posiciones, variables, etiquetas, galería y capítulos extra, que consume el resto de las herramientas).

## Módulos (`tools/script_compiler/`)
| Módulo | Qué hace |
|---|---|
| `rpy_parser.py` | Parser propio del subconjunto de Ren'Py del juego; falla con `archivo:línea` ante algo desconocido |
| `images.py` | Tabla de 1,042 imágenes: archivos, `image`, `renpy.image(...)`, `layeredimage`; resolución de nombres como Ren'Py |
| `translations.py` | Une cada diálogo con `tl/es` por su `id` (o por texto si el script no lo trae) y las cadenas de menús |
| `project.py` | Carga todo: capítulos en orden de historia, personajes, posiciones, variables, rutas |
| `lower.py` | AST → instrucciones, con seguimiento del estado de imágenes por camino |
| `atl.py` | ATL → fotogramas clave (tabla ANIM) |
| `textfmt.py` | Etiquetas de texto → códigos de control; partición en líneas y páginas |
| `assemble.py` / `opcodes.py` | Codificación binaria y tabla de instrucciones |
| `compile.py` | Orquesta todo y genera `STORY.VNB` (incluido `lending` de los créditos) |
| `tools/simulator/` | `vnb.py` (lector/desensamblador), `vm.py` (máquina virtual y exploración), `report.py` |

## Resultados
- 39 de 39 capítulos compilan; 40,579 instrucciones; 615 imágenes; 170 pistas y efectos; 14,779 cadenas.
- 14,691 diálogos, todos con traducción al español (0 en inglés).
- El simulador explora 2,114 estados de decisión y alcanza los 4 finales, las 93 etiquetas, los 9 capítulos extra y las 203 imágenes de galería, con 0 errores. Ver `build/reports/cobertura.md`.
- Texto: 14,779 cadenas, de las cuales 220 (1.5%) ocupan más de una página de 3 líneas; las opciones de menú caben en 3 líneas.
- Animaciones: 2,716 distintas, hasta 8 fotogramas clave, 107 en bucle.

## Decisiones de implementación
- **Estado de imágenes en tiempo de compilación.** Ren'Py elige la imagen de `show anon happy` según los atributos que el tag ya tenía (por eso se conserva `flip`) y recuerda los atributos aunque el tag se oculte o cambie la escena. El compilador lleva ese estado por camino (alternativas en cada decisión) y, si es desconocido, usa la última imagen vista del tag. El motor solo recibe IDs de imagen.
- **`setup_ending()`** se reescribe dentro del capítulo 11 (calcula `ending_route_number` con la lógica de `get_ending`); `STORY.VNB` encadena capítulos base, ruta y créditos.
- **Menús en Python** (`renpy.display_menu(randomize_choices(...))`, con el bucle de `_tick`) se convierten a `MENU` con orden aleatorio y saltos resueltos en la PC.
- **Material picante** siempre activo: `persistent.lewd` se resuelve como verdadero.
- Se corrigió un error del original: `renpy.mark_image_seen('fangshooter')` usaba el nombre del elemento de galería en vez del de la imagen; ahora desbloquea su imagen.

## Limitaciones conocidas (se reportan como avisos al compilar)
Todo el contenido visual del juego se conserva. Lo que queda son funciones de PC que no tienen sentido en consola:
| Aviso | Veces | Efecto |
|---|---|---|
| `webbrowser.open` | 1 | abre un video de YouTube en el original; se omite |
| `renpy.input` | 1 | pide escribir un mensaje (capitulo 13D); se omite |
| `persistent.use_epilogue_menu = True` | 1 | el menu de epilogo no existe en el port |
| Texto sin traducir | 0 | - |
| Lineas inalcanzables | 5 | mensaje de error de desarrollo en el capitulo 7 (codigo muerto del original) |

Fidelidad de efectos (resuelta en la Fase 3):
| Efecto del original | Como se conserva |
|---|---|
| `camera` con zoom y desplazamiento (cap. 8) | instruccion `CAMERA` |
| `camera` con desenfoque (cap. 9) | variantes desenfocadas con disolver (`BACKGROUND` y `SHOW`) |
| `AlphaMask` (cap. 4 y extra x10) | imagen pre-renderizada y recorte vertical animado |
| Cambio de imagen dentro de un ATL (40 eventos) | eventos de la tabla ANIM |
| Funcion de sonido dentro de un ATL | evento de sonido al azar |
| `repeat N` y animaciones largas | se desenrollan, hasta 64 claves |
| `easein*`, `easeout*`, `move`, `ease`, `MoveTransition` | transicion de movimiento (tipo 5) |
| `Fade(color="#fff")` | fundido por blanco (tipo 6) |
