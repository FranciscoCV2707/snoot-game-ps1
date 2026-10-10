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


def parse_transition(expr):
    from tools.script_compiler.lower import parse_transition as parse
    return parse(expr)

SCREEN_W, SCREEN_H = 1920.0, 1080.0
FPS = 60
MAX_KEYS = 64
DEFAULT_ALIGN = (0.5, 1.0)     # posicion de `show` sin `at`

CURVE_LINEAR, CURVE_IN, CURVE_OUT, CURVE_INOUT = 0, 1, 2, 3
WARPERS = {"linear": CURVE_LINEAR}
NUMERIC = ("alpha", "zoom", "xzoom", "yzoom", "rotate")
# funciones de Python llamadas desde un ATL: nombre -> sonidos entre los que elige al azar
ATL_SOUND_FUNCTIONS = {
    "fang_kicks_a_car_workaround_sfx_fuck_renpy": ("audio/effects/carKick1.ogg", "audio/effects/carKick2.ogg"),
}
MAX_REPEAT = 40
IGNORED_PROPS = {"rotate_pad", "transform_anchor", "subpixel", "perspective", "anchor", "around", "alignaround", "clockwise", "counterclockwise",
                 "circles", "knot", "crop", "fit", "xysize", "events",
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


def recipe_size(recipe):
    """Tamano en pixeles originales de una receta de imagen (1920x1080 si no se sabe). Aplica los efectos que cambian
    el tamano igual que tools/images/render.py (im.FactorScale, im.Scale, im.Crop, Transform con zoom o tamano)."""
    if recipe and recipe.get("op") == "effect" and recipe.get("src"):
        w, h = recipe_size(recipe["src"])
        name, args, kw = recipe["effect"], recipe.get("args", []), recipe.get("kwargs", {})
        if name == "im.FactorScale":
            fx = float(args[0])
            return float(round(w * fx)), float(round(h * (float(args[1]) if len(args) > 1 else fx)))
        if name == "im.Scale":
            return float(args[0]), float(args[1])
        if name == "im.Crop":
            rect = args[0] if isinstance(args[0], (list, tuple)) else args[:4]
            return float(rect[2]), float(rect[3])
        if name == "Transform":
            xs, ys, zoom = kw.get("xsize"), kw.get("ysize"), kw.get("zoom")
            if zoom:
                return float(round(w * zoom)), float(round(h * zoom))
            if xs and ys:
                return float(xs), float(ys)
            if xs:
                return float(xs), float(round(h * xs / w))
            if ys:
                return float(round(w * ys / h)), float(ys)
        return w, h
    if recipe and recipe.get("op") == "composite" and recipe.get("size"):
        return tuple(float(v) for v in recipe["size"])
    if recipe and recipe.get("op") == "file":
        from PIL import Image
        from tools.images.render import find_file
        try:
            # la ruta puede ir relativa a images/ (como la busca Ren'Py)
            with Image.open(find_file(recipe["path"])) as im:
                return float(im.width), float(im.height)
        except OSError:
            pass
    return SCREEN_W, SCREEN_H


@lru_cache(maxsize=None)
def image_size(project, key):
    """Tamano en pixeles originales (1920x1080) de una imagen, para convertir xpos/xcenter a xalign."""
    recipe, _ = project.images.canonical(key)
    return recipe_size(recipe)


class State:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.xalign = DEFAULT_ALIGN[0]
        self.yalign = DEFAULT_ALIGN[1]
        self.xpos = self.ypos = None
        self.xanchor, self.yanchor = DEFAULT_ALIGN   # Ren'Py: xalign v fija xpos = v y xanchor = v
        self.alpha, self.zoom, self.xzoom, self.rotate = 1.0, 1.0, 1.0, 0.0
        self.yzoom = 1.0
        self.xoffset = self.yoffset = 0.0       # pixeles de 1920x1080 sumados a la posicion
        self.blur = 0.0                         # solo se usa en los fondos pre-renderizados (`scene X: blur 8`)
        self.reveal = None
        self.tint = (1.0, 1.0, 1.0)

    def copy(self):
        s = State(self.w, self.h)
        s.__dict__.update(self.__dict__)
        return s

    def effective(self):
        """(xalign, yalign) equivalentes, para guardarlos en la tabla."""
        def conv(align, pos, anchor, size, screen, offset):
            if pos is None and not offset:
                return align
            if pos is None:
                pos, anchor = align * screen, align
            room = screen - size
            return (pos - anchor * size + offset) / room if abs(room) > 1e-6 else 0.0
        # el motor ubica el tamano ya escalado: (pantalla - tamano * zoom) * align
        return (conv(self.xalign, self.xpos, self.xanchor, self.w * self.zoom, SCREEN_W, self.xoffset),
                conv(self.yalign, self.ypos, self.yanchor, self.h * self.zoom, SCREEN_H, self.yoffset))

    def values(self):
        xa, ya = self.effective()
        clip = 1.0
        zoom = self.zoom
        if getattr(self, "reveal", None) is not None:
            # mascara que crece en vertical: el contenido se ve solo en una franja central
            clip = max(0.0, min(1.0, self.yzoom * self.reveal))
        return {"x": xa, "y": ya, "alpha": self.alpha, "zoom": zoom, "xzoom": self.xzoom,
                "rotate": self.rotate, "r": self.tint[0], "g": self.tint[1], "b": self.tint[2], "clip": clip}


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
        self.events = []       # cambios de imagen: (tiempo, palabras del nombre, cuadros de disolver)

    @staticmethod
    def repeat_count(text):
        """`repeat` solo = infinito (None); `repeat N` = N veces."""
        parts = text.split()
        return int(float(parts[1])) if len(parts) > 1 else None

    def apply(self, state, prop, value):
        """Aplica una propiedad instantanea sobre el estado. Devuelve False si no se soporta."""
        if prop == "xalign":
            state.xalign, state.xpos, state.xanchor = float(value), None, float(value)
        elif prop == "yalign":
            state.yalign, state.ypos, state.yanchor = float(value), None, float(value)
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
            state.xanchor, state.yanchor = state.xalign, state.yalign
        elif prop == "pos" and isinstance(value, tuple):
            state.xpos, state.ypos = px(value[0], SCREEN_W), px(value[1], SCREEN_H)
        elif prop in ("xoffset", "yoffset", "blur") and isinstance(value, (int, float)):
            setattr(state, prop, float(value))
        elif prop in ("xsize", "ysize") and isinstance(value, (int, float)):
            # tamano fijo: se expresa como zoom uniforme (el juego siempre escala proporcional)
            state.zoom = float(value) / (state.w if prop == "xsize" else state.h)
        elif prop == "size" and isinstance(value, tuple):
            state.zoom = float(value[0]) / state.w
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
            if re.match(r"(size|crop|fit)\s*\(", text):
                continue    # tamano/recorte del contenedor: no cambia lo que se ve
            if text[:1] in "\"'":
                m = re.match(r"""^(?:"([^"]*)"|'([^']*)')(?:\s+with\s+(.+))?$""", text)
                if not m:
                    self.warn(f"cambio de imagen no reconocido: {text[:40]}")
                    continue
                words = tuple((m.group(1) or m.group(2)).split())
                frames = 0
                if m.group(3):
                    spec = parse_transition(m.group(3))
                    frames = spec[1] if spec and spec[0] == 1 else 0
                self.events.append(("img", t, words, frames))
                continue
            if head == "repeat":
                count = self.repeat_count(text)
                if count is None:
                    self.loop = True
                else:   # repeat N en una secuencia: se repite lo anterior N-1 veces mas
                    for _ in range(min(count, MAX_REPEAT) - 1):
                        t, state = self.run(stmts[:i - 1], t, state)
                continue
            if head in ("block:", "block"):
                body = list(children)
                rep = None
                if body and body[-1][0].split()[0] == "repeat":
                    rep = body.pop()[0]
                elif i < len(stmts) and stmts[i][0].split()[0] == "repeat":
                    rep = stmts[i][0]
                    i += 1
                count = self.repeat_count(rep) if rep else 1
                if rep and count is None:
                    t, state = self.run(body, t, state)
                    self.loop = True
                    self.duration = t
                else:
                    for _ in range(min(count or 1, MAX_REPEAT)):
                        t, state = self.run(body, t, state)
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
            if head == "function":
                name = text.split(None, 1)[1].strip()
                if name in ATL_SOUND_FUNCTIONS:
                    self.events.append(("sfx", t, ATL_SOUND_FUNCTIONS[name]))
                else:
                    self.warn(f"funcion de ATL desconocida: {name}")
                continue
            if head in ("on", "contains", "time", "animation", "pass", "lock", "event"):
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
                    int(round(min(255, v["b"] * 128))), int(round(max(0, min(1, v["clip"])) * 255))))
    return out


def decimate(keys):
    """Reduce a MAX_KEYS conservando extremos y los puntos que mas cambian."""
    while len(keys) > MAX_KEYS:
        scores = []
        for i in range(1, len(keys) - 1):
            a, b, c = keys[i - 1][1], keys[i][1], keys[i + 1][1]
            dev = sum(abs(b[f] - (a[f] + c[f]) / 2) for f in ("x", "y", "zoom", "alpha", "clip"))
            scores.append((dev, i))
        scores.sort()
        del keys[scores[0][1]]
    return keys


def compile_anim(lowerer, node, extra_transforms, reveal=None, atl_first=False, slideshow=None):
    """Compila el ATL de un `show`. Devuelve (id 1-based de animacion o 0, clave final de imagen o None).

    reveal: proporcion alto de la mascara / alto del contenido cuando la mascara crece en vertical (AlphaMask).
    """
    sequences = [lowerer.p.transforms[name] for name in extra_transforms]
    if node.atl:
        sequences.insert(0, node.atl) if atl_first else sequences.append(node.atl)
    if not sequences and not slideshow:
        return 0, None
    key = lowerer.reg.last_key.get(node.tag)
    w, h = image_size(lowerer.p, key) if key else (SCREEN_W, SCREEN_H)
    start = State(w, h)
    start.reveal = reveal
    pos_name = next((n for n in node.at if n in lowerer.p.positions), None)
    previous = lowerer.reg.pos_state.get(node.tag)
    if pos_name:
        info = lowerer.p.position_info[lowerer.p.positions[pos_name]]
        start.xalign, start.yalign = info["xalign"], info["yalign"]
        start.xanchor, start.yanchor = info["xalign"], info["yalign"]
    elif previous is not None:
        start.__dict__.update({k: v for k, v in previous.items() if k not in ("w", "h", "reveal")})
    elif node.atl:
        # tag nuevo con bloque ATL y sin `at`: Ren'Py no aplica el transform por defecto (centro abajo), asi que lo que
        # el bloque no fija queda en xpos/ypos/anclas 0 (esquina superior izquierda)
        start.xalign = start.yalign = start.xanchor = start.yanchor = 0.0
    warnings = []
    comp = Compiler(lowerer.p, (w, h), start, warnings.append)
    state = start.copy()
    t = 0.0
    for seq in sequences:
        t, state = comp.run(seq, t, state)
    if slideshow:
        clock = 0.0
        for k, frame in enumerate(slideshow["frames"]):
            if k:
                comp.events.append(("key", clock, frame, slideshow["dissolve"][k]))
            clock += slideshow["times"][k]
        comp.loop = comp.loop or slideshow["loop"]
        comp.duration = max(comp.duration, clock)
    lowerer.reg.pos_state[node.tag] = {k: v for k, v in state.__dict__.items()}
    for w_ in sorted(set(warnings)):
        lowerer.warn(node, w_)

    swaps, final_key, prev = [], None, key
    for ev in sorted(comp.events, key=lambda e: e[1]):
        if ev[0] == "sfx":
            ids = lowerer.reg.audio_group(ev[2])
            swaps.append((int(round(ev[1] * FPS)), ids[0], 2, len(ids)))
            continue
        _, ev_t, words, dissolve = ev
        new_key = words if ev[0] == "key" else lowerer.resolve_swap(words, node.tag, prev, node)
        iid, flip = lowerer.reg.image_id(new_key)
        swaps.append((int(round(ev_t * FPS)), iid, 1 if flip else 0, dissolve))
        prev = final_key = new_key
    if not comp.segments and not swaps:
        return 0, final_key
    keys = quantize_keys(comp.segments, start.values(), comp.loop, comp.duration)
    if len(keys) > MAX_KEYS:
        lowerer.warn(node, f"animacion con {len(keys)} fotogramas clave, se reduce a {MAX_KEYS}")
        keys = decimate(keys)
    if len(swaps) > 255:
        lowerer.warn(node, "demasiados cambios de imagen en un ATL, se recortan a 255")
        swaps = swaps[:255]
    anim = (1 if comp.loop else 0, tuple(encode_keys(keys)), tuple(swaps))
    anims = lowerer.ir.anims
    if anim in anims:
        return anims.index(anim) + 1, final_key
    if len(anims) >= 65535:
        lowerer.warn(node, "demasiadas animaciones distintas en el capitulo")
        return 0, final_key
    anims.append(anim)
    return len(anims), final_key


def compile_pan(lowerer, key, start, end, seconds):
    """`scene X at Pan(start, end, t)`: la esquina superior izquierda de la pantalla recorre la imagen en linea recta.

    Se expresa como xalign/yalign del fondo (pantalla = (pantalla - imagen) * align = -punto).
    """
    w, h = image_size(lowerer.p, key)

    def values(point):
        xa = point[0] / (w - SCREEN_W) if w > SCREEN_W else 0.0
        ya = point[1] / (h - SCREEN_H) if h > SCREEN_H else 0.0
        return {"x": xa, "y": ya, "alpha": 1.0, "zoom": 1.0, "xzoom": 1.0, "rotate": 0.0,
                "r": 1.0, "g": 1.0, "b": 1.0, "clip": 1.0}

    keys = [(0.0, values(start if seconds > 0 else end), CURVE_LINEAR)]
    if seconds > 0:
        keys.append((seconds, values(end), CURVE_LINEAR))
    anim = (0, tuple(encode_keys(keys)), ())
    anims = lowerer.ir.anims
    if anim in anims:
        return anims.index(anim) + 1
    anims.append(anim)
    return len(anims)


KEY_FMT = "<HhhBBBbbBBBB"   # 15 bytes por fotograma clave
SWAP_FMT = "<HHBH"          # 7 bytes: tiempo, imagen, volteo, cuadros de disolver


def build_anim_table(anims):
    """Tabla ANIM: u32 offsets[n] relativos a la tabla; cada animacion: n claves, flags, n cambios de imagen, claves, cambios."""
    blobs = []
    for flags, keys, swaps in anims:
        body = b"".join(struct.pack(KEY_FMT, *k) for k in keys) + b"".join(struct.pack(SWAP_FMT, *sw) for sw in swaps)
        blobs.append(struct.pack("<BBB", len(keys), flags, len(swaps)) + body)
    offsets, pos = [], 4 * len(blobs)
    for b in blobs:
        offsets.append(pos)
        pos += len(b)
    return struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(blobs)
