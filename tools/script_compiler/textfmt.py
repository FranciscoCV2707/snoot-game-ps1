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
        elif name in DROPPED:
            dropped.append(name)
        else:
            dropped.append(name)
    out.append(text[pos:])
    result = "".join(out).replace("\x00LB", "{").replace("\x00LS", "[").replace("\n", chr(NEWLINE))
    return result, dropped


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
