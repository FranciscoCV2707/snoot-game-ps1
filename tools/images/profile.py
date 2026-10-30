"""Perfiles de recursos por plataforma.

El conversor de imagens (`tools/images/convert.py`) estaba atado a lo que cabe en la PS1: reducir 1920x1080 a
320x180, paleta de 256 entradas en 5-5-5, sprites partidos por filas de VRAM y limite de area. Ese sigue siendo el
perfil `ps1` y es el que produce el disco de la version 1.0, byte a byte igual.

Cada consola tiene el suyo: resolucion real de su pantalla, profundidad de color que da su GPU y presupuesto de
memoria. `depth` dice como se guarda el pixel:

- `psx256` - indices de 8 bits con paleta propia (PS1, y los demakes de GBA/DS/GB por presupuesto).
- `rgb565` / `rgb4444` - 16 bits de la GPU, sin paleta compartida (PSP, 3DS, DS en alta).
- `rgba8888` - 32 bits (PC, Vita, Wii, PS2, PS4, Switch).

Los perfiles no cambian el guion: las posiciones en el VNB son fracciones (`xa`/`ya` de 8 bits) que el motor
multiplica por su vista, asi que la escena se acomoda sola al cambiar el tamano de las imagens. Lo que si depende del
perfil es el tamano `full_w`/`full_h` horneado y la escala del texto del chat (`lower.TEXTSCROLL_SCALE`).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str
    view: tuple[int, int]          # vista logica que dibuja el motor (ancho, alto de la escena)
    screen: tuple[int, int]        # framebuffer de la consola
    depth: str = "psx256"          # formato de los sprites
    depth_bg: str = ""             # formato de los fondos; vacio = igual que `depth`
    scale: float = 6.0             # 1920 / ancho de la vista
    text_max_w: int = 300          # ancho maximo de un texto horneado, en pixeles de la vista
    half_area: int = 90000         # por encima, la imagen se guarda a media resolucion
    max_sprite_rows: int = 256     # limite de fila de VRAM; 0 = sin limite
    dither_strength: int = 2       # 0 = sin tramado (perfiles en color verdadero)
    textscroll_scale: float = 0.4  # tamano del chat respecto al original
    solid_full: tuple[int, int] = (320, 180)
    audio: str = "psx"             # psx = XA+SPU del disco; ogg = Vorbis + PCM
    font: str = "8x8"              # 8x8 = bitmap del motor; ttfr:<px> = atlas horneado del TTF
    extra: dict = field(default_factory=dict)

    @property
    def true_color(self) -> bool:
        return self.depth != "psx256"

    @property
    def bg_format(self) -> str:
        """Un fondo es opaco: en 16 bits no necesita alfa, y ahi esta el ahorro que hace que quepa en VRAM."""
        return self.depth_bg or self.depth


def _profile(name: str, view: tuple[int, int], screen: tuple[int, int], **kw) -> Profile:
    base = dict(scale=1920 / view[0], solid_full=view, text_max_w=int(view[0] * 0.94),
                half_area=view[0] * view[1], max_sprite_rows=0, dither_strength=0,
                textscroll_scale=1.0, depth="psx256" if name == "ps1" else "rgb565",
                audio="psx" if name in ("ps1",) else "ogg", font="8x8" if name == "ps1" else "ttf")
    base.update(kw)
    return Profile(name=name, view=view, screen=screen, **base)


PROFILES: dict[str, Profile] = {
    # PS1: los numeros historicos. Cambiar algo de aqui cambia el disco de v1.0.
    "ps1": Profile(name="ps1", view=(320, 180), screen=(320, 240), scale=6.0, depth="psx256", audio="psx",
                   font="8x8", text_max_w=300, half_area=90000, max_sprite_rows=256, dither_strength=2,
                   textscroll_scale=0.4, solid_full=(320, 180)),
    # PC: banco de pruebas; ve el recurso original tal cual.
    "pc": _profile("pc", (1920, 1080), (1920, 1080), depth="rgba8888", audio="ogg",
                   extra={"sin_reduccion": True}),
    # PSP: 480x272 reales. Su GPU no pasa de 512 px de textura y tiene 2 MB de VRAM: por eso 16 bits (fondo 261 KB
    # en 565, sprite con alfa en 4444). Los 512 px los resuelve la ventana/teselado del motor (img_load_big).
    "psp": _profile("psp", (480, 272), (480, 272), depth="rgba4444", depth_bg="rgb565"),
    "ps2": _profile("ps2", (640, 448), (640, 448), depth="rgba8888"),
    "vita": _profile("vita", (960, 544), (960, 544), depth="rgba8888"),
    "3ds": _profile("3ds", (400, 240), (400, 240), depth="rgba4444", depth_bg="rgb565"),
    "wii": _profile("wii", (640, 480), (640, 480), depth="rgba8888"),
    "xbox": _profile("xbox", (640, 480), (640, 480), depth="rgba8888"),
    "switch": _profile("switch", (1280, 720), (1280, 720), depth="rgba8888"),
    # Demakes (D19): siguen en paleta, pero con la resolucion y el texto de su pantalla.
    "gba": _profile("gba", (240, 160), (240, 160), depth="psx256", audio="ogg", font="8x8", dither_strength=2),
    "ds": _profile("ds", (256, 192), (256, 384), depth="rgb565", audio="ogg", font="8x8"),
}


def get(name: str | None) -> Profile:
    return PROFILES.get(name or "ps1") or _unknown(name)


def _unknown(name: str) -> Profile:
    raise ValueError(f"perfil desconocido: {name!r} (hay {', '.join(sorted(PROFILES))})")
