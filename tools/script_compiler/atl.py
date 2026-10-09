"""ATL de Ren'Py -> tabla ANIM (fotogramas clave), ver docs/bytecode.md seccion 5.

Interpreta el subconjunto de ATL que usa el juego: posicion (xalign/yalign/xpos/ypos/xcenter/ycenter/xanchor),
alfa, zoom, xzoom, rotate, matrixcolor (tinte/brillo), warpers, pause, parallel, block, repeat y choice.
Lo que no se soporta se reporta como aviso y se omite.
"""
import ast
import re
import struct
from functools import lru_cache

from tools.script_compiler.rpy_parser import eval_number

SCREEN_W, SCREEN_H = 1920.0, 1080.0
FPS = 60
MAX_KEYS = 8
DEFAULT_ALIGN = (0.5, 1.0)     # posicion de `show` sin `at`

CURVE_LINEAR, CURVE_IN, CURVE_OUT, CURVE_INOUT = 0, 1, 2, 3
WARPERS = {"linear": CURVE_LINEAR}
NUMERIC = ("alpha", "zoom", "xzoom", "yzoom", "rotate")
IGNORED_PROPS = {"subpixel", "perspective", "anchor", "around", "alignaround", "blur", "clockwise", "counterclockwise",
                 "circles", "knot", "crop", "size", "xsize", "ysize", "fit", "xoffset", "yoffset", "xysize", "events",
                 "additive", "offset", "xpan", "ypan", "delay", "yzoom"}
def split_tokens(text):
    """Separa por espacios en el nivel 0 de parentesis (los valores pueden ser tuplas o llamadas)."""
    tokens, cur, depth = [], "", 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                tokens.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        tokens.append(cur)
    return tokens


def curve_for(warper):
    if warper in WARPERS:
        return WARPERS[warper]
    if warper.startswith("easein"):
        return CURVE_IN
    if warper.startswith("easeout"):
        return CURVE_OUT
    if warper.startswith("ease"):
        return CURVE_INOUT
    return None


@lru_cache(maxsize=None)
def image_size(project, key):
    """Tamano en pixeles originales (1920x1080) de una imagen, para convertir xpos/xcenter a xalign."""
    recipe, _ = project.images.canonical(key)
    while recipe and recipe.get("op") == "effect" and recipe.get("src"):
        recipe = recipe["src"]
    if recipe and recipe.get("op") == "composite" and recipe.get("size"):
        return tuple(float(v) for v in recipe["size"])
    if recipe and recipe.get("op") == "file":
        from PIL import Image
        from tools.script_compiler.project import GAME
        try:
            with Image.open(GAME / recipe["path"]) as im:
                return float(im.width), float(im.height)
        except OSError:
            pass
    return SCREEN_W, SCREEN_H


class State:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.xalign = DEFAULT_ALIGN[0]
        self.yalign = DEFAULT_ALIGN[1]
        self.xpos = self.ypos = None
        self.xanchor = self.yanchor = 0.0
        self.alpha, self.zoom, self.xzoom, self.rotate = 1.0, 1.0, 1.0, 0.0
        self.tint = (1.0, 1.0, 1.0)

    def copy(self):
        s = State(self.w, self.h)
        s.__dict__.update(self.__dict__)
        return s

    def effective(self):
        """(xalign, yalign) equivalentes, para guardarlos en la tabla."""
        def conv(align, pos, anchor, size, screen):
            if pos is None:
                return align
            room = screen - size
            return (pos - anchor * size) / room if abs(room) > 1e-6 else 0.0
        return (conv(self.xalign, self.xpos, self.xanchor, self.w, SCREEN_W),
                conv(self.yalign, self.ypos, self.yanchor, self.h, SCREEN_H))

    def values(self):
        xa, ya = self.effective()
        return {"x": xa, "y": ya, "alpha": self.alpha, "zoom": self.zoom, "xzoom": self.xzoom,
                "rotate": self.rotate, "r": self.tint[0], "g": self.tint[1], "b": self.tint[2]}


def px(value, screen):
    """Valor de Ren'Py: flotante = fraccion de la pantalla, entero = pixeles."""
    return value * screen if isinstance(value, float) else float(value)


def parse_value(text):
    text = text.strip()
    if text in ("True", "False"):
        return text == "True"
    try:
        tree = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None
    if isinstance(tree, ast.Tuple):
        return tuple(ast.literal_eval(e) if isinstance(e, ast.Constant) else eval_number(ast.unparse(e)) for e in tree.elts)
    if isinstance(tree, ast.Call):
        return tree
    try:
        value = ast.literal_eval(tree)
        return value
    except Exception:
        try:
            return eval_number(text)
        except Exception:
            return None


def matrix_tint(tree):
    """TintMatrix(Color((r,g,b))) / BrightnessMatrix(v) -> (r, g, b) en 0..2 (1 = sin cambio)."""
    name = ast.unparse(tree.func)
    if name == "BrightnessMatrix":
        v = eval_number(ast.unparse(tree.args[0]))
        return (max(0.0, 1.0 + v),) * 3 if v < 0 else (min(2.0, 1.0 + v),) * 3
    if name == "TintMatrix":
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Tuple) and len(sub.elts) >= 3:
                nums = [eval_number(ast.unparse(e)) for e in sub.elts[:3]]
                return tuple(max(0.0, min(2.0, n / 255.0)) for n in nums)
    return None


class Compiler:
    def __init__(self, project, size, start, warn):
        self.project = project
        self.w, self.h = size
        self.start = start
        self.warn = warn
        self.segments = []     # (t0, t1, curve, valores finales, valores iniciales)
        self.loop = False
        self.duration = 0.0
        self.swaps = 0

    def apply(self, state, prop, value):
        """Aplica una propiedad instantanea sobre el estado. Devuelve False si no se soporta."""
        if prop == "xalign":
            state.xalign, state.xpos = float(value), None
        elif prop == "yalign":
            state.yalign, state.ypos = float(value), None
        elif prop == "xpos":
            state.xpos = px(value, SCREEN_W)
        elif prop == "ypos":
            state.ypos = px(value, SCREEN_H)
        elif prop == "xanchor":
            state.xanchor = float(value) if isinstance(value, float) else value / state.w
        elif prop == "yanchor":
            state.yanchor = float(value) if isinstance(value, float) else value / state.h
        elif prop == "xcenter":
            state.xpos, state.xanchor = px(value, SCREEN_W), 0.5
        elif prop == "ycenter":
            state.ypos, state.yanchor = px(value, SCREEN_H), 0.5
        elif prop == "align" and isinstance(value, tuple):
            state.xalign, state.yalign, state.xpos, state.ypos = float(value[0]), float(value[1]), None, None
        elif prop == "pos" and isinstance(value, tuple):
            state.xpos, state.ypos = px(value[0], SCREEN_W), px(value[1], SCREEN_H)
        elif prop in NUMERIC:
            setattr(state, prop, float(value))
        elif prop == "matrixcolor":
            tint = matrix_tint(value) if isinstance(value, ast.AST) else None
            if tint is None:
                return False
            state.tint = tint
        elif prop in IGNORED_PROPS:
            return True
        else:
            return False
        return True

    def parse_props(self, tokens, node_text):
        props = []
        i = 0
        while i + 1 < len(tokens):
            name, raw = tokens[i], tokens[i + 1]
            value = parse_value(raw)
            if name in ("clockwise", "counterclockwise", "circles"):
                i += 2
                continue
            if value is None:
                self.warn(f"valor ATL no soportado: {name} {raw}")
                i += 2
                continue
            props.append((name, value))
            i += 2
        return props

    def run(self, stmts, t, state):
        """Ejecuta una secuencia de sentencias ATL. Devuelve (tiempo final, estado)."""
        i = 0
        while i < len(stmts):
            text, children = stmts[i]
            i += 1
            head = text.split()[0] if text.split() else ""
            if text[:1] in "\"'":
                self.swaps += 1      # cambio de imagen dentro del ATL: se conserva la imagen inicial
                continue
            if head == "repeat":
                self.loop = True
                continue
            if head in ("block:", "block"):
                t, state = self.run(children, t, state)
                if i < len(stmts) and stmts[i][0].split()[0] == "repeat":
                    self.loop = True
                    self.duration = t
                    i += 1
                continue
            if head == "parallel:":
                group = [children]
                while i < len(stmts) and stmts[i][0].split()[0] == "parallel:":
                    group.append(stmts[i][1])
                    i += 1
                ends, states = [], []
                for branch in group:
                    bt, bs = self.run(branch, t, state.copy())
                    ends.append(bt)
                    states.append(bs)
                t = max(ends)
                merged = state.copy()
                for bs in states:   # cada rama toca propiedades distintas: se toma lo que cambio
                    for k, v in bs.__dict__.items():
                        if v != state.__dict__[k]:
                            merged.__dict__[k] = v
                state = merged
                continue
            if head == "choice:":
                while i < len(stmts) and stmts[i][0].split()[0] == "choice:":
                    i += 1   # solo se conserva la primera rama
                t, state = self.run(children, t, state)
                continue
            if head == "pause":
                t += eval_number(text.split(None, 1)[1])
                continue
            if head in ("on", "function", "contains", "time", "animation", "pass", "lock", "event"):
                if head not in ("pass", "animation"):
                    self.warn(f"ATL no soportado: {head}")
                continue
            tokens = split_tokens(text)
            warper = curve_for(head)
            if warper is not None or head in ("warp",):
                duration = eval_number(tokens[1])
                props = self.parse_props(tokens[2:], text)
                start = state.values()
                new = state.copy()
                for name, value in props:
                    if not self.apply(new, name, value):
                        self.warn(f"propiedad ATL no soportada: {name}")
                end_t = t + duration
                self.segments.append((t, end_t, warper if warper is not None else 0, new.values(), start))
                t = end_t
                state = new
                continue
            props = self.parse_props(tokens, text)
            if not props:
                self.warn(f"sentencia ATL no reconocida: {text[:40]}")
                continue
            new = state.copy()
            for name, value in props:
                if not self.apply(new, name, value):
                    self.warn(f"propiedad ATL no soportada: {name}")
            self.segments.append((t, t, CURVE_LINEAR, new.values(), state.values()))
            state = new
        self.duration = max(self.duration, t)
        return t, state


def ease(curve, u):
    if curve == CURVE_IN:
        return u * u * u
    if curve == CURVE_OUT:
        return 1 - (1 - u) ** 3
    if curve == CURVE_INOUT:
        return 3 * u * u - 2 * u ** 3
    return u


def sample(segments, field, t, initial):
    """Valor de un campo en el tiempo t segun los segmentos (ultimo segmento que lo cambia)."""
    value = initial
    for t0, t1, curve, end, begin in segments:
        if end[field] == begin[field] and t >= t0:
            continue
        if t >= t1:
            value = end[field]
        elif t > t0:
            u = ease(curve, (t - t0) / (t1 - t0))
            value = begin[field] + (end[field] - begin[field]) * u
        elif t == t0 and t1 == t0:
            value = end[field]
    return value


def quantize_keys(segments, initial, loop, end_time):
    times = {0.0}
    for t0, t1, *_ in segments:
        times.update((t0, t1))
    if loop:
        times.add(end_time)
    times = sorted(times)
    keys = []
    for t in times:
        vals = {f: sample(segments, f, t, initial[f]) for f in initial}
        # curva del segmento que termina en t: la del que mas mueve
        best, curve = 0.0, CURVE_LINEAR
        for t0, t1, c, end, begin in segments:
            if abs(t1 - t) < 1e-9 and t1 > t0:
                delta = abs(end["x"] - begin["x"]) + abs(end["y"] - begin["y"]) + abs(end["zoom"] - begin["zoom"])
                if delta >= best:
                    best, curve = delta, c
        keys.append((t, vals, curve))
    return keys


def encode_keys(keys):
    out = []
    for t, v, curve in keys:
        frames = int(max(0, min(65535, round(t * FPS))))
        rot = int(round(v["rotate"] * 256 / 360))
        rot = ((rot + 128) % 256) - 128
        out.append((frames, int(round(max(-127, min(127, v["x"])) * 256)), int(round(max(-127, min(127, v["y"])) * 256)),
                    int(round(max(0, min(1, v["alpha"])) * 255)), curve,
                    int(round(max(0, min(255 / 64, v["zoom"])) * 64)), int(round(max(-1.98, min(1.98, v["xzoom"])) * 64)),
                    rot, int(round(min(255, v["r"] * 128))), int(round(min(255, v["g"] * 128))),
                    int(round(min(255, v["b"] * 128)))))
    return out


def decimate(keys):
    """Reduce a MAX_KEYS conservando extremos y los puntos que mas cambian."""
    while len(keys) > MAX_KEYS:
        scores = []
        for i in range(1, len(keys) - 1):
            a, b, c = keys[i - 1][1], keys[i][1], keys[i + 1][1]
            dev = sum(abs(b[f] - (a[f] + c[f]) / 2) for f in ("x", "y", "zoom", "alpha"))
            scores.append((dev, i))
        scores.sort()
        del keys[scores[0][1]]
    return keys


def compile_anim(lowerer, node, extra_transforms):
    """Devuelve el id (1-based) de la animacion de un `show`, o 0 si no tiene."""
    sequences = []
    for name in extra_transforms:
        sequences.append(lowerer.p.transforms[name])
    if node.atl:
        sequences.append(node.atl)
    if not sequences:
        return 0
    key = lowerer.reg.last_key.get(node.tag)
    w, h = image_size(lowerer.p, key) if key else (SCREEN_W, SCREEN_H)
    start = State(w, h)
    pos_name = next((n for n in node.at if n in lowerer.p.positions), None)
    previous = lowerer.reg.pos_state.get(node.tag)
    if pos_name:
        info = lowerer.p.position_info[lowerer.p.positions[pos_name]]
        start.xalign, start.yalign = info["xalign"], info["yalign"]
    elif previous is not None:
        start.__dict__.update({k: v for k, v in previous.items() if k not in ("w", "h")})
    warnings = []
    comp = Compiler(lowerer.p, (w, h), start, warnings.append)
    state = start.copy()
    t = 0.0
    for seq in sequences:
        t, state = comp.run(seq, t, state)
    lowerer.reg.pos_state[node.tag] = {k: v for k, v in state.__dict__.items()}
    for w_ in sorted(set(warnings)):
        lowerer.warn(node, w_)
    if comp.swaps:
        lowerer.warn(node, "cambio de imagen dentro de un ATL ignorado (se conserva la imagen inicial)")
    if not comp.segments:
        return 0
    initial = start.values()
    keys = quantize_keys(comp.segments, initial, comp.loop, comp.duration)
    if len(keys) > MAX_KEYS:
        lowerer.warn(node, f"animacion con {len(keys)} fotogramas clave, se reduce a {MAX_KEYS}")
        keys = decimate(keys)
    encoded = encode_keys(keys)
    flags = 1 if comp.loop else 0
    anim = (flags, tuple(encoded))
    anims = lowerer.ir.anims
    if anim in anims:
        return anims.index(anim) + 1
    if len(anims) >= 65535:
        lowerer.warn(node, "demasiadas animaciones distintas en el capitulo")
        return 0
    anims.append(anim)
    return len(anims)


KEY_FMT = "<HhhBBBbbBBB"   # 14 bytes por fotograma clave


def build_anim_table(anims):
    """Tabla ANIM: u32 offsets[n] relativos a la tabla, luego cada animacion (n, flags, claves de 14 bytes)."""
    blobs = []
    for flags, keys in anims:
        body = b"".join(struct.pack(KEY_FMT, *k) for k in keys)
        blobs.append(struct.pack("<BB", len(keys), flags) + body)
    offsets, pos = [], 4 * len(blobs)
    for b in blobs:
        offsets.append(pos)
        pos += len(b)
    return struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(blobs)
