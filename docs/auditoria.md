# Auditoria de Snoot Game

Generado por `tools/audit/inventario.py`. No editar a mano; las notas manuales van en `docs/auditoria_manual.md` (se anexan al final).

## Resumen

| Dato | Valor |
|---|---|
| Version de Ren'Py | 8.3.7 |
| Licencia (archivos) | CC-BY-SA-4.0.txt, GNU Affero General Public License Version Three.txt, GPL-Exception, LICENSE |
| Archivos de historia (script/) | 39 |
| Etiquetas (label) | 101 |
| Lineas de dialogo (script/) | 14691 |
| Opciones de menu (script/) | 64 |
| Menus de decision (todo) | 26 |
| Bloques de traduccion es (script/) | 14694 |
| Pares old/new de es (strings) | 748 |
| Imagenes definidas (image) | 431 |
| Videos | 1 |

## Instrucciones de Ren'Py usadas

| Instruccion | Veces |
|---|---|
| dialogue | 14595 |
| pause | 7963 |
| show | 6847 |
| window | 2743 |
| with | 929 |
| play | 825 |
| scene | 796 |
| stop | 616 |
| hide | 544 |
| image | 431 |
| define | 230 |
| $ | 203 |
| style | 198 |
| label | 101 |
| extend | 98 |
| menu choice | 69 |
| screen | 52 |
| jump | 48 |
| return | 45 |
| python block | 42 |
| transform | 42 |
| pass | 31 |
| default | 26 |
| menu | 26 |
| if | 25 |
| else | 11 |
| queue | 9 |
| elif | 5 |
| camera | 5 |
| init | 4 |
| while | 4 |
| call | 3 |
| call screen | 2 |
| layeredimage | 2 |

### Instrucciones desconocidas

Ninguna.

### Canales de audio y transiciones

| Canal | Veces |
|---|---|
| stop music | 360 |
| play music | 336 |
| play sound | 256 |
| stop ambient | 177 |
| play ambient | 170 |
| stop ambient1 | 28 |
| play ambient1 | 27 |
| stop sound | 24 |
| play audio | 15 |
| stop ambient2 | 12 |
| play ambient2 | 11 |
| queue music | 8 |
| stop music1 | 7 |
| play music1 | 6 |
| stop ambient3 | 3 |
| stop music2 | 3 |
| stop audio | 2 |
| play ambient3 | 2 |
| play music2 | 2 |
| queue sound | 1 |

| Transicion | Veces |
|---|---|
| dissolve | 1807 |
| Dissolve(.25) | 1234 |
| Dissolve(1) | 528 |
| None | 99 |
| dissolve: | 83 |
| Dissolve(2) | 83 |
| Dissolve(1.5) | 75 |
| Dissolve(0.25) | 65 |
| Dissolve(0.5) | 51 |
| Fade(1, 0, 1) | 39 |
| Dissolve(.1) | 35 |
| fade | 29 |
| easeinbottom | 25 |
| vpunch | 25 |
| Dissolve(.15) | 24 |
| Dissolve(.75) | 17 |
| hpunch | 13 |
| Dissolve(3) | 10 |
| Dissolve(1.0) | 9 |
| Dissolve(.1): | 9 |
| Dissolve(1): | 9 |
| Dissolve(.5) | 8 |
| Dissolve(.2) | 7 |
| Dissolve(.11) | 6 |
| easeinbottom: | 6 |
| Dissolve(0.15) | 5 |
| Fade(1,0,1) | 5 |
| Dissolve(.4): | 4 |
| Dissolve(.25): | 4 |
| Dissolve(0.25): | 3 |
| Dissolve(.4) | 3 |
| Dissolve(0.2) | 3 |
| Dissolve(2.5) | 2 |
| MoveTransition(0.5, time_warp=_ease_in_t | 2 |
| ease | 2 |
| Dissolve(2.0) | 2 |
| Dissolve(.22) | 2 |
| move: | 2 |
| Dissolve(.3) | 2 |
| Dissolve(9.0) | 2 |

### Etiquetas de texto e interpolaciones

| Etiqueta | Veces |
|---|---|
| cps | 2830 |
| w | 1131 |
| i | 391 |
| nw | 194 |
| fast | 170 |
| size | 40 |
| alpha | 39 |
| b | 28 |
| color | 3 |

| Variable [x] | Veces |
|---|---|
| Hey | 1 |
| Fast | 1 |
| Resuming | 1 |

## Personajes (38)

| Nombre | Definicion |
|---|---|
| base | `Character (ctc="ctc_end_marker", ctc_pause="ctc_mid_marker", ctc_timedpause=Null(), ctc_position="nestled-close")` |
| narrator | `Character(kind=base)` |
| A | `Character (_('Anon'), base, color="#36E12D", who_outlines=[(gui.name_text_thickness, '#0C300A')])` |
| F | `Character (_('Fang'), base, color="#B4D4CE", who_outlines=[(gui.name_text_thickness, '#0F3930')])` |
| Lucy | `Character (_('Lucy'), base, color="#B4D4CE", who_outlines=[(gui.name_text_thickness, '#0F3930')])` |
| Ro | `Character (_('Rosa'), base, color="#FE712B", who_outlines=[(gui.name_text_thickness, '#54230F')])` |
| St | `Character (_('Stella'), base, color="#D5FFAE", who_outlines=[(gui.name_text_thickness, '#294211')])` |
| N | `Character (_('Naomi'), base, color="#FDD2C1", who_outlines=[(gui.name_text_thickness, '#462628')])` |
| Nas | `Character (_('Naser'), base, color="#FFB561", who_outlines=[(gui.name_text_thickness, '#512322')])` |
| T | `Character (_('Trish'), base, color="#B675E6", who_outlines=[(gui.name_text_thickness, '#3A0C5D')])` |
| Attendant | `Character (_('Attendant'), base, color="#5BF0F8", who_outlines=[(gui.name_text_thickness, '#121C68')])` |
| Sp | `Character (_('Spears'), base, color="#C7C7C7", who_outlines=[(gui.name_text_thickness, '#272727')])` |
| Re | `Character (_('Reed'), base, color="#ED4C5B", who_outlines=[(gui.name_text_thickness, '#421014')])` |
| D | `Character (_('Driver'), base, color="#FFECBC", who_outlines=[(gui.name_text_thickness, '#563010')])` |
| FM | `Character (_("Fang’s mom"), base, color="#FFD8F6", who_outlines=[(gui.name_text_thickness, '#521947')])` |
| FD | `Character (_("Fang’s dad"), base, color="#D8A09A", who_outlines=[(gui.name_text_thickness, '#461B1F')])` |
| LM | `Character (_("Lucy’s mom"), base, color="#FFD8F6", who_outlines=[(gui.name_text_thickness, '#521947')])` |
| LD | `Character (_("Lucy’s dad"), base, color="#D8A09A", who_outlines=[(gui.name_text_thickness, '#461B1F')])` |
| Tsuki | `Character (_('Mr. Tsuki'), base, color="#A7F2A2", who_outlines=[(gui.name_text_thickness, '#471054')])` |
| unknown | `Character (_('(???)'), base, color="#FFF", who_outlines=[(gui.name_text_thickness, '#000')])` |
| jingo | `Character (_('Mr. Jingo'), base, color="#CD8283", who_outlines=[(gui.name_text_thickness, '#0F0D49')])` |
| MaitD | `Character (_('Maitre d’'), base, color="#AF9EFF", who_outlines=[(gui.name_text_thickness, '#241630')])` |
| Moe | `Character(_('Moe'), base, color="#A5BEED", who_outlines=[(gui.name_text_thickness, '#1F253B')])` |
| Vince | `Character (_('Vince'), base, color="#FFECBC", who_outlines=[(gui.name_text_thickness, '#563010')])` |
| Waitress | `Character (_('Waitress'), base, color="#F691C8", who_outlines=[(gui.name_text_thickness, '#512040')])` |
| Riley | `Character (_('Riley'), base, color="#B675E6", who_outlines=[(gui.name_text_thickness, '#1F0632')])` |
| Tana | `Character (_('Tana'), base, color="#B675E6", who_outlines=[(gui.name_text_thickness, '#1F0632')])` |
| Trevor | `Character (_('Trevor'), base, color="#B675E6", who_outlines=[(gui.name_text_thickness, '#1F0632')])` |
| AnonAndFang | `Character(_('Anon and Fang'), base, color="72DFA8", who_outlines=[(gui.name_text_thickness, '#113623')])` |
| SV | `Character (_('Street Vendor'), base, color="#F8E120", who_outlines=[(gui.name_text_thickness, '#58260C')])` |
| carl | `Character ('Mr. Carldewskii', base, color="#EECB99", who_outlines=[(gui.name_text_thickness, '#082337')])` |
| Drf | `Character ('Dr. Fernsworth', base, color="#DCEEF5", who_outlines=[(gui.name_text_thickness, '#253354')])` |
| FRT | `Character (_('Fang Reed & Trish'), base, color="#DCBBF7",  who_outlines=[(gui.name_text_thickness, '#191C78')])` |
| FangAndTrish | `Character(_('Fang and Trish'), base, color="#42DFA8", who_outlines=[(gui.name_text_thickness, '#183623')])` |
| NaserAndNaomi | `Character(_('Naser and Naomi'), base, color="#22DFA8", who_outlines=[(gui.name_text_thickness, '#2036B3')])` |
| TeamMember | `Character(_('Team member'), base, color="#D32552", who_outlines=[(gui.name_text_thickness, '#445F42')])` |
| Everyone | `Character(_('Everyone'), base, color="#A45489", who_outline=[(gui.name_text_thickness, '#4F5F81')])` |
| Chet | `Character(_('Chet'), base, color="#B45411", who_outline=[(gui.name_text_thickness, '#BF5F81')])` |

## Variables define/default (40)

| Tipo | Cantidad |
|---|---|
| bool | 13 |
| list/tuple | 8 |
| other | 6 |
| None | 5 |
| int | 4 |
| dict | 4 |

Lista completa en `inventario.json`. Variables de historia (`default`):

| Nombre | Tipo | Valor | Archivo |
|---|---|---|---|
| preferences.text_cps | int | `50` | options.rpy |
| preferences.afm_time | int | `15` | options.rpy |
| persistent.reloading_mods | bool | `False` | options.rpy |
| persistent.use_epilogue_menu | bool | `False` | options.rpy |
| persistent.enable_debug_scores | other | `config.developer` | options.rpy |
| persistent.enable_chapter_select | other | `config.developer` | options.rpy |
| persistent.lewd | bool | `False` | options.rpy |
| persistent.autoup | bool | `False` | options.rpy |
| persistent.show_mod_screenshots | bool | `True` | options.rpy |
| persistent.gallery_edgescroll | bool | `True` | options.rpy |
| persistent.scroll | bool | `False` | options.rpy |
| quick_menu | bool | `True` | screens.rpy |
| persistent.old_endings | None | `None` | screens.rpy |
| persistent.endings | None | `None` | screens.rpy |
| adjust | other | `ui.adjustment()` | src/cg_gallery.rpy |
| active_queue | list/tuple | `[]` | src/chapter_variables.rpy |
| current_chapter | None | `None` | src/chapter_variables.rpy |
| anonscore | int | `0` | src/chapter_variables.rpy |
| fangscore | int | `0` | src/chapter_variables.rpy |
| wingStory | bool | `False` | src/chapter_variables.rpy |
| ending_route_number | None | `None` | src/chapter_variables.rpy |
| ending_chapters_determined | bool | `False` | src/chapter_variables.rpy |
| chapter_select_used | bool | `False` | src/chapter_variables.rpy |
| persistent.seenModWarning | bool | `False` | src/mod_menu.rpy |
| persistent.seenWarning | list/tuple | `[]` | src/translation.rpy |
| persistent.languaged_up | None | `None` | src/translation.rpy |

Variables asignadas con `$` en la historia:

| Variable | Asignaciones |
|---|---|
| persistent.bonus_chapters | 9 |
| i | 7 |
| quick_menu | 7 |
| fangscore | 5 |
| anonscore | 5 |
| ending_route_number | 4 |
| late_to_spears | 2 |
| punched_into_flowerbed | 2 |
| TalkedWithTrish | 2 |
| wingStory | 1 |
| LeftStage | 1 |
| persistent.use_epilogue_menu | 1 |
| preferences.language | 1 |
| persistent.reloading_mods | 1 |
| active_queue | 1 |
| current_chapter | 1 |

Hablantes (dialogos por personaje):

| Hablante | Lineas |
|---|---|
| (narrador) | 7001 |
| A | 2501 |
| F | 1743 |
| Nas | 555 |
| T | 501 |
| Lucy | 409 |
| N | 396 |
| Re | 381 |
| Sp | 219 |
| Ro | 146 |
| unknown | 125 |
| St | 108 |
| Moe | 102 |
| FD | 98 |
| FM | 78 |
| SV | 59 |
| D | 44 |
| Drf | 31 |
| LM | 24 |
| carl | 13 |
| Tsuki | 9 |
| LD | 8 |
| jingo | 8 |
| Riley | 6 |
| Tana | 6 |
| Attendant | 5 |
| Chet | 4 |
| Vince | 3 |
| Waitress | 3 |
| MaitD | 2 |
| Trevor | 2 |
| AnonAndFang | 1 |
| FRT | 1 |
| FangAndTrish | 1 |
| Everyone | 1 |
| NaserAndNaomi | 1 |

## Datos persistentes

| persistent. | Referencias |
|---|---|
| bonus_chapters | 20 |
| use_epilogue_menu | 19 |
| enabled_mods | 13 |
| endings | 11 |
| lewd | 8 |
| newmods_default_state | 7 |
| enable_debug_scores | 6 |
| enable_chapter_select | 6 |
| show_mod_screenshots | 6 |
| old_bonus_chapters | 6 |
| old_endings | 5 |
| seenWarning | 5 |
| reloading_mods | 4 |
| gallery_edgescroll | 4 |
| scroll | 4 |
| splashtype | 4 |
| languaged_up | 4 |
| seenModWarning | 3 |
| autoup | 1 |

Referencias a `persistent.lewd` (material picante): 8

## API de Ren'Py usada (renpy.*)

| Llamada | Veces |
|---|---|
| music.set_volume | 118 |
| image | 60 |
| mark_image_seen | 28 |
| variant | 15 |
| display_menu | 14 |
| jump | 12 |
| pause | 10 |
| music.register_channel | 7 |
| seen_image | 6 |
| known_languages | 6 |
| play | 3 |
| org | 3 |
| open_file | 3 |
| check_permission | 3 |
| music.queue | 2 |
| android | 2 |
| version_only | 1 |
| license | 1 |
| filter_text_tags | 1 |
| input | 1 |
| music.stop | 1 |
| random.randint | 1 |
| list_images | 1 |
| get_registered_image | 1 |
| show | 1 |
| windows | 1 |
| macintosh | 1 |
| linux | 1 |
| request_permission | 1 |
| android.PythonActivity | 1 |
| android.PythonSDLActivity | 1 |
| list_files | 1 |
| loadable | 1 |
| revertable.RevertableList | 1 |
| include_module | 1 |
| reload_script | 1 |
| curry | 1 |
| register_shader | 1 |
| get_autoreload | 1 |
| quit | 1 |

## Bloques de Python

| Categoria | Bloques/lineas |
|---|---|
| descartable | 22 |
| traducible automaticamente | 190 |
| a mano | 28 |
| revisar | 5 |

Cada bloque con su clasificacion esta en `build/audit/python_blocks.txt`.

## Pantallas (screen) (52)

| Nombre | Archivo | Linea | Lineas |
|---|---|---|---|
| say | screens.rpy | 117 | 14 |
| input | screens.rpy | 191 | 11 |
| choice | screens.rpy | 225 | 4 |
| quick_button | screens.rpy | 262 | 12 |
| quick_buttons | screens.rpy | 278 | 2 |
| quick_menu | screens.rpy | 282 | 15 |
| navigation | screens.rpy | 333 | 17 |
| main_menu_button | screens.rpy | 389 | 11 |
| bonus_chapter_button | screens.rpy | 411 | 13 |
| main_menu_buttons | screens.rpy | 432 | 2 |
| main_menu_background | screens.rpy | 441 | 7 |
| main_menu | screens.rpy | 453 | 42 |
| game_menu | screens.rpy | 543 | 40 |
| about | screens.rpy | 668 | 19 |
| save | screens.rpy | 707 | 2 |
| load | screens.rpy | 714 | 2 |
| delete | screens.rpy | 720 | 2 |
| file_slots | screens.rpy | 726 | 56 |
| preferences | screens.rpy | 858 | 116 |
| history | screens.rpy | 1087 | 19 |
| extras | screens.rpy | 1172 | 4 |
| extrasnavigation | screens.rpy | 1184 | 23 |
| help | screens.rpy | 1220 | 28 |
| keyboard_help | screens.rpy | 1267 | 37 |
| mouse_help | screens.rpy | 1318 | 16 |
| gamepad_help | screens.rpy | 1341 | 20 |
| confirm | screens.rpy | 1404 | 18 |
| OkPrompt | screens.rpy | 1466 | 16 |
| skip_indicator | screens.rpy | 1500 | 9 |
| notify | screens.rpy | 1556 | 5 |
| nvl | screens.rpy | 1595 | 16 |
| nvl_dialogue | screens.rpy | 1627 | 10 |
| bubble | screens.rpy | 1715 | 11 |
| quick_button | screens.rpy | 1807 | 9 |
| quick_menu | screens.rpy | 1818 | 15 |
| preferences | screens.rpy | 1835 | 111 |
| cg_gallery | src/cg_gallery.rpy | 94 | 50 |
| flag_button | src/cg_gallery.rpy | 167 | 16 |
| view_movie | src/cg_gallery.rpy | 187 | 13 |
| view_image | src/cg_gallery.rpy | 204 | 21 |
| main_credits | src/credits.rpy | 182 | 62 |
| ex_ch_button | src/extra_chapters_menu.rpy | 23 | 11 |
| ex_ch_buttons | src/extra_chapters_menu.rpy | 38 | 2 |
| ex_ch_menu | src/extra_chapters_menu.rpy | 42 | 46 |
| prompt | src/misc_definitions.rpy | 178 | 2 |
| mousedetect | src/misc_definitions.rpy | 182 | 7 |
| textscroll | src/misc_definitions.rpy | 192 | 19 |
| mod_menu | src/mod_menu.rpy | 817 | 320 |
| mod_screenshot_preview | src/mod_menu.rpy | 1218 | 6 |
| mod_menu_top_buttons | src/mod_menu.rpy | 1228 | 9 |
| lang_sel | src/translation.rpy | 46 | 39 |
| lang_button | src/translation.rpy | 98 | 12 |

## Historia

Capitulos base: chapter_1, chapter_2, chapter_3, chapter_4, chapter_5, chapter_6, chapter_7, chapter_8, chapter_9, chapter_10, chapter_11

- Ruta 1: chapter_11A > chapter_12A > chapter_12_5D > chapter_13A > chapter_14A
- Ruta 2: chapter_11B > chapter_12B > chapter_13B > chapter_14B
- Ruta 3: chapter_11C > chapter_12C > chapter_12_5C > chapter_13C > chapter_14C
- Ruta 4: chapter_11D > chapter_12D > chapter_12_5D > chapter_13D > chapter_14D

Capitulos extra:

- Chicxulub Gutterlane -> `chapter_x1`
- The Mous Pad -> `chapter_x2`
- PTA Meeting -> `chapter_x3`
- Passion of the Trigga I -> `chapter_x4`
- Passion of the Trigga II -> `chapter_x5`
- Passion of the Trigga III -> `chapter_x6`
- Naomi’s Tribulations I -> `chapter_x7`
- Naomi’s Tribulations II -> `chapter_x8`
- Naomi’s Tribulations III -> `chapter_x9`
- RAYmba’s Observations -> `chapter_x10`

Saltos dinamicos (`jump/call expression`): 1

- `src/storyline.rpy:48` call expression `current_chapter`

Grafos: `build/audit/grafo_historia.svg` (capitulos) y `build/audit/grafo_labels.svg` (todas las etiquetas).

## Dialogo por archivo

| Archivo | Dialogos | Opciones | Bloques es |
|---|---|---|---|
| 1.first-two-days-anon-meets-fang.rpy | 860 | 6 | 860 |
| 10.an-excellent-reason-to-start-abusing-mod-powers.rpy | 155 | 0 | 155 |
| 11.school-assignment-and-route-lock.rpy | 1361 | 2 | 1361 |
| 11A.fang-desperately-wants-to-win-prom-night.rpy | 50 | 0 | 50 |
| 11B.anon-gets-fangs'-pronouns-right,-and-she's-smug-about-it.rpy | 54 | 0 | 54 |
| 11C.anon-gets-fangs'-pronouns-right,-but-she-tells-him-she's-okay-with-being-called-a-girl.rpy | 95 | 0 | 95 |
| 11D.anon-gets-fangs'-pronouns-right-and-she-teases-him-while-carrying-herself-with-more-confidence.rpy | 111 | 0 | 111 |
| 12.5C.prom-night-intro.rpy | 79 | 0 | 79 |
| 12.5D.prom-night-intro.rpy | 79 | 0 | 79 |
| 12A.music-museum-date.rpy | 247 | 2 | 247 |
| 12B.band-fang-likes-concert.rpy | 169 | 0 | 169 |
| 12C.anon-fang-lovey-dovey.rpy | 270 | 0 | 270 |
| 12D.aquarium.rpy | 182 | 0 | 182 |
| 13A.fang-loses-it-after-losing-prom-queen.rpy | 512 | 2 | 512 |
| 13B.fang-breaks-up-with-anon.rpy | 289 | 0 | 289 |
| 13C.fang-and-anon-go-to-beach-and-prom.rpy | 979 | 0 | 979 |
| 13D.fang-plays-well,-naomi-jealous,-fang-talks-to-anon-to-break-up-while-she-thinks-about-her-life.rpy | 1017 | 4 | 1017 |
| 14A.KO_OP-ending.rpy | 352 | 0 | 352 |
| 14B.bad-ending.rpy | 115 | 0 | 115 |
| 14C.good-ending.rpy | 312 | 0 | 312 |
| 14D.gold-ending.rpy | 273 | 0 | 273 |
| 2.fourth-day-of-school.rpy | 678 | 9 | 678 |
| 3.showing-up-at-band-practice-and-giving-feedback.rpy | 529 | 0 | 529 |
| 4.anon-needs-help-during-music-period.rpy | 383 | 3 | 383 |
| 5.fang-and-anon-cut-class-to-talk-on-the-roof.rpy | 1150 | 5 | 1151 |
| 6.anon-helps-fang-find-a-venue-for-band.rpy | 1217 | 4 | 1218 |
| 7.concert-day.rpy | 423 | 10 | 424 |
| 8.anon-and-fang-study-together.rpy | 550 | 9 | 550 |
| 9.anons'-dirty-laundry-gets-put-up-to-air.rpy | 546 | 8 | 546 |
| x1-chicxulub-gutterlane.rpy | 153 | 0 | 153 |
| x10-raymbas-observations.rpy | 214 | 0 | 214 |
| x2-the-mous-pad.rpy | 97 | 0 | 97 |
| x3-PTA-meeting.rpy | 54 | 0 | 54 |
| x4-passion-of-the-trigga.rpy | 70 | 0 | 70 |
| x5-passion-of-the-trigga.rpy | 101 | 0 | 101 |
| x6-passion-of-the-trigga.rpy | 301 | 0 | 301 |
| x7-naomi-tribulations.rpy | 266 | 0 | 266 |
| x8-naomi-tribulations.rpy | 114 | 0 | 114 |
| x9-naomi-tribulations.rpy | 284 | 0 | 284 |

## Traduccion al espanol

| Dato | Valor |
|---|---|
| Archivos de script sin traduccion es | ninguno |
| Bloques de dialogo traducidos | 14694 |
| Bloques con texto vacio | 0 |
| Bloques con texto igual al original (sospechosos) | 63 |
| Pares strings vacios | 0 |
| Imagenes con texto traducido (tl/es/images) | 39 |
| Texto espanol total (bytes UTF-8) | 767045 |
| Caracteres distintos | 115 |

Caracteres no ASCII usados: `¡¿ÁÉÍÑÓÚàáéíñóöúü‘’…♪✔✘⬆⬇`

Ejemplos de bloques iguales al original:

- 1.first-two-days-anon-meets-fang.rpy: Volcaldera Bluffs.
- 1.first-two-days-anon-meets-fang.rpy: {cps=*0.3}Ooooooh nooooooo.{/cps}
- 1.first-two-days-anon-meets-fang.rpy: {cps=*0.2}Hmmm...{/cps}{w=0.4}{nw}
- 10.an-excellent-reason-to-start-abusing-mod-powers.rpy: {cps=*.15}Haaaah.{/cps}
- 10.an-excellent-reason-to-start-abusing-mod-powers.rpy: Z{size=-5}z{/size}{size=-10}z{/size}
- 11.school-assignment-and-route-lock.rpy: Uhhhhhhhhhhhhhh{cps=*.1}...{/cps}
- 11.school-assignment-and-route-lock.rpy: {i}Fang:{/i}{fast} Ughh
- 11.school-assignment-and-route-lock.rpy: {i}Anon:{/i}{fast} ah.

## Galeria

| Pestana | Elementos |
|---|---|
| CG | 108 |
| Animations | 0 |
| Lewd | 3 |
| Fullbody | 20 |
| Backgrounds | 72 |

## Logos encontrados


## Imagenes

| Carpeta | Cantidad | MB | Con alfa | Formatos | Tamanos frecuentes |
|---|---|---|---|---|---|
| audio/OST | 2 | 0.19 | 2 | {'PNG': 2} | [('1000x1000', 2)] |
| gui | 18 | 1.69 | 18 | {'PNG': 18} | [('1920x1080', 4), ('637x273', 2), ('1682x357', 2), ('200x155', 1)] |
| gui/bar | 4 | 0.0 | 4 | {'PNG': 4} | [('38x525', 2), ('525x38', 2)] |
| gui/button | 23 | 0.06 | 23 | {'PNG': 23} | [('27x49', 4), ('511x129', 3), ('1185x52', 2), ('450x49', 2)] |
| gui/flag | 9 | 0.12 | 6 | {'PNG': 9} | [('684x360', 3), ('684x456', 1), ('686x457', 1), ('684x457', 1)] |
| gui/gallery | 1 | 0.02 | 1 | {'PNG': 1} | [('1920x1080', 1)] |
| gui/overlay | 5 | 0.52 | 5 | {'PNG': 5} | [('1920x1080', 5)] |
| gui/phone | 34 | 0.15 | 34 | {'PNG': 34} | [('27x64', 4), ('1050x18', 4), ('18x1050', 4), ('1920x1080', 3)] |
| gui/scrollbar | 8 | 0.0 | 8 | {'PNG': 8} | [('1050x18', 4), ('18x1050', 4)] |
| gui/slider | 8 | 0.0 | 8 | {'PNG': 8} | [('525x38', 2), ('15x38', 2), ('38x525', 2), ('38x15', 2)] |
| images/NotForKids! | 4 | 0.7 | 1 | {'WEBP': 4} | [('1920x1080', 4)] |
| images/RAYmba | 9 | 0.51 | 9 | {'WEBP': 9} | [('1500x1500', 5), ('1920x1080', 3), ('456x208', 1)] |
| images/animations | 1 | 0.03 | 0 | {'WEBP': 1} | [('432x243', 1)] |
| images/anon | 37 | 2.76 | 37 | {'WEBP': 37} | [('1061x1500', 21), ('1053x1500', 7), ('1920x1080', 6), ('1700x1500', 1)] |
| images/backgrounds | 81 | 24.34 | 18 | {'WEBP': 80, 'PNG': 1} | [('1920x1080', 79), ('1920x1082', 1), ('2304x1296', 1)] |
| images/cgs | 121 | 22.17 | 42 | {'WEBP': 120, 'PNG': 1} | [('1920x1080', 114), ('1920x1081', 2), ('1916x1074', 1), ('1920x4474', 1)] |
| images/ending | 9 | 0.88 | 1 | {'WEBP': 9} | [('1920x590', 4), ('1920x1080', 4), ('1920x8100', 1)] |
| images/fang | 77 | 6.47 | 77 | {'WEBP': 77} | [('1412x1500', 65), ('1920x1080', 9), ('1298x1500', 1), ('1920x1365', 1)] |
| images/fangparents | 5 | 0.41 | 5 | {'WEBP': 5} | [('1061x1500', 5)] |
| images/highres | 12 | 0.56 | 12 | {'WEBP': 12} | [('1412x1500', 5), ('1061x1500', 3), ('2015x2850', 1), ('1036x1500', 1)] |
| images/insultlayers | 9 | 0.15 | 9 | {'WEBP': 9} | [('635x146', 1), ('587x109', 1), ('1003x114', 1), ('636x99', 1)] |
| images/intros | 1 | 0.04 | 0 | {'WEBP': 1} | [('1920x1080', 1)] |
| images/moe | 2 | 0.16 | 2 | {'WEBP': 2} | [('1263x1500', 2)] |
| images/naomi | 17 | 1.2 | 17 | {'WEBP': 17} | [('1036x1500', 16), ('1920x1080', 1)] |
| images/naser | 19 | 1.69 | 19 | {'WEBP': 19} | [('1412x1500', 18), ('1541x1500', 1)] |
| images/other | 74 | 4.23 | 69 | {'WEBP': 74} | [('1920x1080', 28), ('576x920', 13), ('1061x1500', 4), ('284x107', 3)] |
| images/reed | 14 | 1.67 | 14 | {'WEBP': 14} | [('1135x1500', 12), ('1367x1500', 1), ('1404x1500', 1)] |
| images/rosa | 14 | 2.04 | 14 | {'WEBP': 14} | [('1074x1500', 8), ('1305x1500', 1), ('991x1500', 1), ('874x1500', 1)] |
| images/spears | 3 | 0.21 | 3 | {'WEBP': 3} | [('1061x1500', 3)] |
| images/stella | 17 | 1.44 | 17 | {'WEBP': 17} | [('684x1500', 14), ('1263x1500', 1), ('807x1500', 1), ('847x1500', 1)] |
| images/tracy | 4 | 0.38 | 4 | {'WEBP': 4} | [('1061x1500', 4)] |
| images/trish | 33 | 2.45 | 33 | {'WEBP': 33} | [('895x1500', 30), ('1008x1050', 2), ('1253x1080', 1)] |
| images/trishfam | 11 | 0.6 | 11 | {'WEBP': 11} | [('789x1500', 11)] |
| images/vfx | 13 | 2.14 | 13 | {'WEBP': 13} | [('1516x1384', 5), ('1920x1080', 2), ('213x70', 1), ('800x500', 1)] |
| presplash_background.png | 1 | 0.14 | 1 | {'PNG': 1} | [('600x600', 1)] |
| presplash_foreground.png | 1 | 0.01 | 1 | {'PNG': 1} | [('600x600', 1)] |
| tl/cs/images | 41 | 1.11 | 36 | {'WEBP': 41} | [('1920x1080', 24), ('1920x590', 1), ('635x146', 1), ('670x109', 1)] |
| tl/es/images | 39 | 1.21 | 34 | {'WEBP': 39} | [('1920x1080', 22), ('1920x590', 1), ('635x146', 1), ('672x107', 1)] |
| tl/fr/images | 32 | 1.71 | 27 | {'WEBP': 31, 'PNG': 1} | [('1920x1080', 16), ('1920x590', 1), ('545x197', 1), ('685x109', 1)] |
| tl/it/images | 32 | 1.49 | 27 | {'WEBP': 32} | [('1920x1080', 16), ('1920x590', 1), ('800x146', 1), ('700x109', 1)] |
| tl/pl/images | 30 | 1.07 | 24 | {'WEBP': 30} | [('1920x1080', 15), ('1920x590', 1), ('635x146', 1), ('587x109', 1)] |
| tl/pt_br/images | 36 | 1.58 | 31 | {'WEBP': 36} | [('1920x1080', 20), ('1920x590', 1), ('635x146', 1), ('587x109', 1)] |
| tl/ru/images | 36 | 1.44 | 30 | {'WEBP': 36} | [('1920x1080', 21), ('635x146', 1), ('587x109', 1), ('1003x114', 1)] |
| tl/th/images | 42 | 1.86 | 37 | {'WEBP': 42} | [('1920x1080', 25), ('1920x590', 1), ('635x146', 1), ('587x109', 1)] |

## Audio

| Carpeta | Archivos | MB | Minutos | Formatos |
|---|---|---|---|---|
| audio/OST | 69 | 74.2 | 77.5 | {'.ogg': 69} |
| audio/effects | 110 | 24.3 | 42.6 | {'.ogg': 110} |
| audio/ui | 7 | 0.0 | 0.0 | {'.wav': 7} |

Pistas mas largas (min):

- 3.46 min: `audio/OST/Amberlight Brilliance.ogg`
- 3.26 min: `audio/OST/The Hitler Song With The Really Long Name.ogg`
- 2.4 min: `audio/OST/Appreciating the Moment.ogg`
- 2.26 min: `audio/OST/Appreciating the Atmosphere.ogg`
- 2.2 min: `audio/OST/Appreciating her Company.ogg`
- 2.19 min: `audio/effects/windLightLoop.ogg`
- 2.17 min: `audio/effects/rainLoop.ogg`
- 2.13 min: `audio/OST/Dragging on and on....ogg`

## Video

- `images/animations/fang tail.webm`

---

## Hallazgos manuales (Fase 1)

### Estructura de la historia
- Capitulos 1 a 11 son lineales (`BASE_CHAPTERS`). Al terminar el 11, `get_ending(anonscore, fangscore, wingStory)` elige una de 4 rutas:
  - Golden (4): `anonscore >= 4`, `fangscore >= 4` y `wingStory`.
  - Tradwife (3): `anonscore >= 3` y `fangscore <= 4`.
  - Doomer (2): `anonscore <= 3` y `fangscore >= 3`.
  - Shooter (1): el resto. Termina el juego con `renpy.quit()`.
- Las rutas llaman a los capitulos por nombre con `call expression current_chapter` (unico salto dinamico del juego, en `src/storyline.rpy`). El compilador lo resuelve en la PC con la lista de `ENDING_ROUTES`.
- Finales: `chapter_14A` (Shooter), `14B` (Doomer), `14C` (Tradwife), `14D` (Golden). Se cuentan como vistos cuando se muestran las imagenes `e1of4` a `e4of4` (`renpy.seen_image`).
- `chapter_select_used` y `persistent.enable_chapter_select` son herramientas de desarrollo; se descartan.

### Capitulos extra (distinto a lo que decia el plan)
El plan decia "bloqueados hasta terminar todas las rutas". El juego original desbloquea de forma progresiva (`src/extra_chapters_menu.rpy`):
- Con 0 finales vistos no hay extras.
- Cada final visto desbloquea mas capitulos de las dos series (Trish: x4-x6, Naomi: x7-x9); x1 a x3 estan disponibles desde el primer final.
- `x10` (RAYmba) requiere los 4 finales y los 9 capitulos extra anteriores completos (`persistent.bonus_chapters == 0b111111111`).
- Cada capitulo extra marca su bit en `persistent.bonus_chapters` al terminar (9 bits).
- Al terminar `x10` se activa `persistent.use_epilogue_menu` (cambia el menu principal a una imagen "big ending"). En el port no aplica porque el titulo es negro con logo.
- **Decision para la Fase 2:** replicar la logica progresiva (cuesta 13 bits: 4 de finales + 9 de extras) o usar la regla simple del plan. Recomendacion: replicar la original.

### Material picante
- Variable: `persistent.lewd` (por defecto `False`). Hay un interruptor en Opciones que se descarta.
- Condiciones en la historia: 3 (`script/3...:2283` imagen `lesbo` 20 s; `script/5...:4480`; `script/7...:38` imagen `fangonamp`).
- Imagenes: carpeta `images/NotForKids!` (bikini, fangonamp base/text, lesbo) y la pestana "Lewd" de la galeria (3 elementos).
- En el port: `PICANTE = True`; el compilador deja solo la rama activa. No hay nada mas que depende de la variable.

### Texto leido, "visto" y galeria
- Ren'Py marca como leido cada dialogo; el juego trae un ID unico por linea (`id chapter_5_ad464e5e`) que une cada dialogo con su bloque `translate es` en `tl/es/`. El compilador puede usar ese ID directamente (sin calcular hashes).
- Lineas de dialogo en `script/`: 14,691. Un bit por linea son unos 1.8 KB en la memory card.
- La galeria usa `renpy.seen_image(nombre)`: una imagen esta desbloqueada si alguna vez se mostro con `show` o `scene`. El motor debe marcar un bit por cada imagen mostrada.
- Galeria (`src/gallery_dataset.json`): CG 108, Fullbody 20, Backgrounds 72, Lewd 3 (condicionada a `persistent.lewd`), Animations 0. Total 203 elementos. Tambien hay 28 llamadas a `renpy.mark_image_seen` que marcan imagenes sin mostrarlas.
- Hay 1 video: `images/animations/fang tail.webm` (galeria; conviene descartarlo o convertirlo a una animacion simple).

### Traduccion al espanol
- Cobertura de dialogo: 14,694 bloques traducidos contra 14,691 lineas de dialogo; ningun bloque vacio. Los 63 bloques "iguales al original" son interjecciones (`Hmmm...`) o nombres, no faltantes reales.
- Cadenas de menus, nombres y pantallas estan en `translate es strings` (748 pares, 0 vacios).
- Hay 39 imagenes con texto traducido en `tl/es/images/` (reemplazan imagenes con texto embebido, p.ej. `door auditorium text`, `insultlayers/text1-9`, `the ending`). El pipeline de imagenes (Fase 4) debe usar la version en espanol cuando exista.
- Caracteres especiales a incluir en la fuente: `¡¿ÁÉÍÑÓÚàáéíñóöúü‘’…` (los simbolos `♪✔✘⬆⬇` son de la interfaz). Total de caracteres distintos: 115.
- Texto en espanol sin etiquetas: unos 750 KB en UTF-8.

### Logo y menu
- Logo del titulo: `gui/snootgame.png`. Existe una variante `gui/sneedgame.png` que sale al azar (`persistent.splashtype == 1`, easter egg); se descarta.

### Audio
- Musica: 69 pistas, 77.5 minutos, 74 MB (OGG).
- Efectos: 110 archivos, 42.6 minutos en total, pero casi todo son bucles ambientales largos (`windLightLoop`, `rainLoop`, de mas de 2 min). Solo hay 7 sonidos de interfaz (WAV) que se descartan.
- Canales usados: `music`, `music1/2` (crossfade, 8 usos), `sound`, `ambient`, `ambient1-3` (utilizados ~210 veces) y `audio`.
- No hay voces.

### Python de la historia
- Menus hechos en Python (`renpy.display_menu(randomize_choices(...))`, 14 usos): el orden de las dos opciones es aleatorio y algunos arman el nombre del salto (`renpy.jump(_value + chr(0x61 + _tick))`) en un bucle de "Snot / Interrupt". Hay que traducirlos a mano.
- 190 de 245 bloques de Python se traducen automaticamente (asignaciones, volumen de musica, marcar imagen vista). 28 van a mano; 22 son descartables; 5 se revisan.
- Variables de historia: `anonscore`, `fangscore`, `wingStory`, `late_to_spears`, `punched_into_flowerbed`, `TalkedWithTrish`, `LeftStage`, `ending_route_number` y contadores auxiliares. Son pocas.

### Partes dificiles de portar (resumen)
1. **Ambientes y musica a la vez**: el CD solo puede reproducir un stream XA; la musica XA y los ambientes (bucles de minutos) no pueden sonar juntos. Hay que convertir los ambientes a VAG cortos en bucle (limite de 512 KB de RAM de sonido) o decidir por escena.
2. **Texto en imagenes**: 39 imagenes con texto traducido y las "insultlayers" se componen en pantalla; hay que resolverlas en la Fase 4.
3. **ATL/animaciones**: miles de lineas de movimiento (`easein_cubic`, `parallel`, `repeat`) en `show ... at` y `transform`; el motor solo soportara un subconjunto (posiciones fijas, quizá deslizamientos simples).
4. **Transiciones**: `Dissolve` con ~40 duraciones distintas, `Fade`, `vpunch/hpunch`, `MoveTransition`; se aproximan a unas pocas.
5. **Menus en Python con orden aleatorio** y saltos con nombre armado.
6. **Imagenes de 1920x1080** (fondos, CGs, personajes de 1500 px de alto) a 320x240: perdida grande, sobre todo en CGs con texto.
7. **Sistema de "visto"**: bits por imagen mostrada y por linea de dialogo, con el modo saltar (R1) que se detiene en lo no leido.
8. **Capitulos extra progresivos** y logica de finales con 13 bits de progreso.
9. **Texto**: 14.7 mil lineas con etiquetas `{cps}` (2,830), `{w}`, `{nw}`, `{fast}`, `{i}`, `{size}`, `{alpha}` que el motor debe interpretar o el compilador simplificar.
10. **Video** `fang tail.webm` y las 431 definiciones de imagen (capas/expresiones con `layeredimage` y composiciones en `image_definitions.rpy`).
