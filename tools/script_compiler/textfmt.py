"""Convierte el texto de Ren'Py a las cadenas del motor con codigos de control (docs/bytecode.md seccion 6)."""
import re

STYLE, WAIT, SPEED, NOWAIT, FAST, SIZE, NEWLINE, PAGE = 1, 2, 3, 4, 5, 6, 0x0A, 0x0B
TAG_RE = re.compile(r"\{(/?)(\w+)(?:=([^}]*))?\}")
DROPPED = {"alpha", "color", "font", "u", "s", "plain", "outlinecolor", "k", "rt", "rb", "a", "image", "space", "vspace", "art"}


def code(kind, arg=None):
    return chr(kind) + (chr(arg) if arg is not None else "")


def to_number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def convert(text):
    """Devuelve (texto con codigos, informe de etiquetas descartadas)."""
    dropped = []
    text = text.replace("{{", "\x00LB").replace("[[", "\x00LS").replace("%%", "%")
    out = []
    pos = 0
    for m in TAG_RE.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        closing, name, arg = m.group(1), m.group(2), m.group(3)
        if name in ("i", "em"):
            out.append(code(STYLE, 0 if closing else 1))
        elif name == "b":
            out.append(code(STYLE, 0 if closing else 2))
        elif name == "w":
            out.append(code(WAIT, int(min(25, round(to_number(arg, 0.5) * 10)))))
        elif name == "p":
            out.append(code(WAIT, 10))
        elif name == "cps":
            if closing:
                out.append(code(SPEED, 0))
            elif arg and arg.startswith("*"):
                out.append(code(SPEED, int(max(1, min(250, round(to_number(arg[1:], 1.0) * 50))))))
            else:
                out.append(code(SPEED, int(max(1, min(250, to_number(arg, 50))))))
        elif name == "nw":
            out.append(code(NOWAIT))
        elif name == "fast":
            out.append(code(FAST))
        elif name == "size":
            if closing:
                out.append(code(SIZE, 128))
            else:
                n = to_number(arg.lstrip("+") if arg else 0, 0)
                out.append(code(SIZE, int(max(-2, min(2, round(n / 5))) + 128)))
        elif not closing:
            dropped.append(name)
    out.append(text[pos:])
    result = "".join(out).replace("\x00LB", "{").replace("\x00LS", "[").replace("\n", chr(NEWLINE))
    return result, dropped


def make_measure(font_path, size, scale=4):
    """Devuelve una funcion que mide el ancho en pixeles (de la pantalla de 320) de un texto visible."""
    from PIL import ImageFont
    font = ImageFont.truetype(str(font_path), size * scale)

    def measure(text):
        return font.getlength(text) / scale
    return measure


def paginate(text, measure, width, max_lines):
    """Parte el texto en lineas (\\n) y paginas (\\x0B) segun el ancho de la caja y el maximo de lineas.

    Devuelve (texto, numero de paginas). Los codigos de control no ocupan ancho.
    """
    tokens = []
    cur = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ord(ch) in (STYLE, WAIT, SPEED, SIZE) and i + 1 < len(text):
            cur += ch + text[i + 1]          # el argumento de un codigo nunca se parte (puede valer 32, 10 u 11)
            i += 2
            continue
        if ch == " ":
            tokens.append(cur)
            cur = ""
        elif ord(ch) == NEWLINE:
            tokens.append(cur)
            tokens.append("\n")
            cur = ""
        else:
            cur += ch
        i += 1
    tokens.append(cur)

    out, line, lines_used, pages = [], "", 1, 1

    def break_line():
        nonlocal line, lines_used, pages
        if lines_used >= max_lines:
            out.append(line + chr(PAGE))
            lines_used = 1
            pages += 1
        else:
            out.append(line + chr(NEWLINE))
            lines_used += 1
        line = ""

    for tok in tokens:
        if tok == "\n":
            break_line()
            continue
        trial = (line + " " + tok) if line else tok
        if line and measure(strip_codes(trial)) > width:
            break_line()
            trial = tok
        line = trial
    out.append(line)
    return "".join(out), pages


def strip_codes(text):
    """Texto visible (sin codigos de control), para medir el ancho."""
    out = []
    i = 0
    while i < len(text):
        c = ord(text[i])
        if c in (STYLE, WAIT, SPEED, SIZE):
            i += 2
            continue
        if c in (NOWAIT, FAST):
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)
