"""Reduccion del AST de Ren'Py a instrucciones del bytecode VNB (Fase 3, etapa 4).

Recorre cada capitulo siguiendo el flujo (etiquetas, menus, if) y lleva la cuenta de que imagen muestra cada
tag, para resolver atributos como lo hace Ren'Py (`show anon happy` conserva el volteo anterior).
"""
import ast
import re
from dataclasses import dataclass, field

from tools.script_compiler import atl as atl_module
from tools.script_compiler import rpy_parser as rp
from tools.script_compiler import textfmt
from tools.script_compiler.opcodes import FLAG_FLIP, OP_CODE, POS_KEEP, POS_NONE, Z_KEEP

MUSIC_CHANNELS = {"music": 0, "music1": 0, "music2": 0}
AMBIENT_SLOTS = {"ambient": 0, "ambient1": 1, "ambient2": 2, "ambient3": 3}
SFX_CHANNELS = {"sound", "audio"}
VOLUME_CHANNELS = {"music": 0, "ambient": 1, "ambient1": 2, "ambient2": 3, "ambient3": 4, "sound": 5, "audio": 5}
SPECIAL_TEXTSCROLL, SPECIAL_CREDITS, SPECIAL_INPUT = 1, 2, 3
TEXTSCROLL_SCALE = 0.4      # tamano del chat en la PS1 respecto al original (legible en 320 px)
SHOW_RANDOM_FIRST = ("text1",)
SCENE_FLIP = 0x8000            # bit alto del anim de SCENE: fondo espejado (`scene moes pizza mirrored`)
TEXTBOX_INSTANT = 4            # bit del modo de TEXTBOX: mostrar u ocultar la caja sin fundido
NUM = r"\s*(-?[\d.]+)\s*"
PAN_RE = re.compile(rf"\bPan\(\s*\({NUM},{NUM}\)\s*,\s*\({NUM},{NUM}\)\s*,{NUM}")


class CompileError(Exception):
    pass


@dataclass
class Inst:
    op: str
    args: dict = field(default_factory=dict)
    line: int = 0
    file: str = ""


class VState:
    """Estado de imagenes en un punto del flujo: por tag, las imagenes posibles (alternativas por camino)."""

    def __init__(self, tags=None, z=None, comp=None):
        self.tags = {k: set(v) for k, v in (tags or {}).items()}
        self.z = dict(z or {})
        self.comp = {k: list(v) for k, v in (comp or {}).items()}   # tags acompanantes (parches de video) por tag

    def copy(self):
        return VState(self.tags, self.z, self.comp)

    def merge(self, other):
        if other is None:
            return self
        for tag, keys in other.tags.items():
            self.tags.setdefault(tag, set()).update(keys)
        for tag, z in other.z.items():
            self.z.setdefault(tag, z)
        for tag, extra in other.comp.items():
            self.comp.setdefault(tag, [])
            self.comp[tag] += [c for c in extra if c not in self.comp[tag]]
        return self


def merge_states(states):
    live = [s for s in states if s is not None]
    if not live:
        return None
    out = live[0].copy()
    for s in live[1:]:
        out.merge(s)
    return out


class Registry:
    """IDs compartidos entre capitulos: imagenes, audio, variables, posiciones."""

    def __init__(self, project):
        self.project = project
        self.images = [None]       # id 0 = sin imagen
        self._image_ids = {}
        self.audio = []
        self._audio_ids = {}
        self._audio_groups = {}
        self.vars = {}
        self.tag_ids = {}
        self.last_key = {}
        self.pos_state = {}
        self.camera = {"zoom": 1.0, "x": 0.0, "y": 0.0, "blur": 0.0}
        self.music = {}        # canal de Ren'Py -> ruta de la pista que suena en el
        self.music_cur = None
        self.visible = {}      # id de imagen -> [x0, y0, x1, y1] visible en pixeles originales, o None si hace falta completa

    def mark_full(self, iid):
        self.visible[iid] = None

    def mark_rect(self, iid, rect):
        if iid in self.visible and self.visible[iid] is None:
            return
        old = self.visible.get(iid)
        self.visible[iid] = list(rect) if old is None else [min(old[0], rect[0]), min(old[1], rect[1]),
                                                           max(old[2], rect[2]), max(old[3], rect[3])]

    def image_id(self, key):
        recipe, flip = self.project.images.canonical(key)
        sig = repr(sorted(recipe.items(), key=lambda kv: kv[0]))
        if sig not in self._image_ids:
            self._image_ids[sig] = len(self.images)
            self.images.append({"recipe": recipe, "names": []})
        iid = self._image_ids[sig]
        name = " ".join(key)
        if name not in self.images[iid]["names"]:
            self.images[iid]["names"].append(name)
        return iid, flip

    def textscroll_pages(self):
        """Chat de `call screen textscroll` (capitulo 4): la imagen larga `texts` en tiras de pantalla completa,
        legibles (0.4x del original) sobre fondo blanco. Devuelve los ids consecutivos de las tiras."""
        from PIL import Image
        from tools.images.render import find_file
        with Image.open(find_file("images/other/texts.webp")) as im:
            width, height = im.size
        rows = int(180 / TEXTSCROLL_SCALE)                       # filas del original por tira de 180 lineas de PS1
        zoom = atl_module.SCREEN_W / width                        # al tamano de 1920 que el convertidor reduce 6x
        ids = []
        for k in range((height + rows - 1) // rows):
            recipe = {"op": "effect", "effect": "Transform", "args": [], "kwargs": {"zoom": zoom}, "src": {
                "op": "composite", "size": [width, rows], "layers": [
                    {"pos": [0, 0], "src": {"op": "solid", "color": "#fff"}},
                    {"pos": [0, -k * rows], "src": {"op": "file", "path": "images/other/texts.webp"}}]}}
            sig = repr(recipe)
            if sig not in self._image_ids:
                self._image_ids[sig] = len(self.images)
                self.images.append({"recipe": recipe, "names": [f"ui textscroll {k}"]})
            ids.append(self._image_ids[sig])
            self.mark_full(ids[-1])
        return ids

    def camera_shot(self, layers, camera):
        """Imagen nueva con la escena vista por la camara: pantalla = zoom * punto - (x, y), en pixeles de 1920x1080."""
        zc, tx, ty = camera["zoom"], camera["x"], camera["y"]
        parts = []
        for layer in layers:
            recipe, flip = self.project.images.canonical(layer["key"])
            w, h = atl_module.recipe_size(recipe)
            zoom = layer["zoom"]
            x = layer["xalign"] * (atl_module.SCREEN_W - w * zoom)
            y = layer["yalign"] * (atl_module.SCREEN_H - h * zoom)
            src = recipe
            if flip:
                src = {"op": "flip", "src": src, "horizontal": True}
            if abs(zc * zoom - 1.0) > 1e-6 or layer.get("blur"):
                kwargs = {"zoom": zc * zoom}
                if layer.get("blur"):
                    kwargs["blur"] = layer["blur"]
                src = {"op": "effect", "effect": "Transform", "src": src, "args": [], "kwargs": kwargs}
            parts.append({"pos": [zc * x - tx, zc * y - ty], "src": src})
        recipe = {"op": "composite", "size": [int(atl_module.SCREEN_W), int(atl_module.SCREEN_H)], "layers": parts}
        sig = repr(recipe)
        if sig not in self._image_ids:
            self._image_ids[sig] = len(self.images)
            self.images.append({"recipe": recipe, "names": [f"camera shot {len(self.images)}"]})
        iid = self._image_ids[sig]
        self.mark_full(iid)
        return iid

    def audio_id(self, path):
        real = self.project.audio_path(path)
        if real is None:
            raise CompileError(f"audio no encontrado: {path}")
        if real not in self._audio_ids:
            self._audio_ids[real] = len(self.audio)
            self.audio.append({"path": real})
        return self._audio_ids[real]

    def audio_mix(self, paths):
        """Entrada de audio para una mezcla de stems (se mezcla en la Fase 5)."""
        key = "mix:" + "+".join(paths)
        if key not in self._audio_ids:
            self._audio_ids[key] = len(self.audio)
            self.audio.append({"path": key, "mix": list(paths)})
        return self._audio_ids[key]

    def audio_group(self, paths):
        """IDs consecutivos para elegir uno al azar entre varios sonidos (se duplican entradas si hace falta)."""
        ids = [self.audio_id(p) for p in paths]
        if ids == list(range(ids[0], ids[0] + len(ids))):
            return ids
        key = tuple(paths)
        if key not in self._audio_groups:
            first = len(self.audio)
            for p in paths:
                self.audio.append({"path": self.project.audio_path(p)})
            self._audio_groups[key] = list(range(first, first + len(paths)))
        return self._audio_groups[key]

    def var(self, name):
        if name not in self.vars:
            if len(self.vars) >= 64:
                raise CompileError("mas de 64 variables")
            self.vars[name] = len(self.vars)
        return self.vars[name]

    def tag(self, name):
        if name not in self.tag_ids:
            if len(self.tag_ids) >= 250:
                raise CompileError("demasiados tags")
            self.tag_ids[name] = len(self.tag_ids) + 1
        return self.tag_ids[name]


def get_ending_insts(reg, prefix, line=0, file=""):
    """get_ending(anonscore, fangscore, wingStory) de src/storyline.rpy -> asigna ending_route_number (1-4)."""
    insts = []

    def emit(_name, **args):
        insts.append(Inst(_name, args, line, file))

    def cmp(name, op, value):
        emit("PUSH_VAR", var=reg.var(name))
        emit("PUSH_CONST", value=value)
        emit("OP", op=OP_CODE[op])

    route = reg.var("ending_route_number")
    end = f"{prefix}.end"
    steps = [(4, [("anonscore", ">=", 4), ("fangscore", ">=", 4)], True), (3, [("anonscore", ">=", 3), ("fangscore", "<=", 4)], False),
             (2, [("anonscore", "<=", 3), ("fangscore", ">=", 3)], False)]
    for num, conds, wing in steps:
        nxt = f"{prefix}.n{num}"
        for name, op, value in conds:
            cmp(name, op, value)
        emit("OP", op=OP_CODE["and"])
        if wing:
            emit("PUSH_VAR", var=reg.var("wingStory"))
            emit("OP", op=OP_CODE["and"])
        emit("JUMP_IF_FALSE", target=nxt)
        emit("SET_VAR", var=route, value=num)
        emit("JUMP", target=end)
        emit("LABEL", name=nxt)
    emit("SET_VAR", var=route, value=1)
    emit("LABEL", name=end)
    return insts


class ChapterIR:
    def __init__(self, chapter):
        self.chapter = chapter
        self.insts = []
        self.strings = []        # [{"id": id de Ren'Py o None, "text": cadena con codigos}]
        self.warnings = []
        self.anims = []
        self.dropped_tags = {}


def tenths(seconds):
    return int(max(0, min(255, round((seconds or 0.0) * 10))))


def frames(seconds):
    return int(max(0, min(65535, round(seconds * 60))))


class Lowerer:
    def __init__(self, project, registry, chapter):
        self.p = project
        self.reg = registry
        self.ch = chapter
        self.ir = ChapterIR(chapter)
        self.label = None
        self.pending = {}
        self.dry = 0
        self.counter = 0
        self.pyenv = {}

    # -- utilidades ---------------------------------------------------------
    def emit(self, _name, line=0, **args):
        if not self.dry:
            self.ir.insts.append(Inst(_name, args, line, self.ch.name))

    def warn(self, node, msg):
        if not self.dry:
            self.ir.warnings.append(f"{self.ch.name}:{getattr(node, 'line', 0)}: {msg}")

    def new_label(self, hint):
        self.counter += 1
        return f".{hint}{self.counter}"

    def add_string(self, tid, text, choice=False):
        if self.dry:
            return 0
        converted, dropped = textfmt.convert(text)
        for d in dropped:
            self.ir.dropped_tags[d] = self.ir.dropped_tags.get(d, 0) + 1
        self.ir.strings.append({"id": tid, "text": converted, "choice": choice})
        return len(self.ir.strings) - 1

    # -- punto de entrada ---------------------------------------------------
    def run(self):
        state = VState()
        state = self.block(self.ch.nodes, state)
        if state is not None:
            self.emit("RETURN")
        self.prerender_camera_shots()
        return self.ir

    # -- tomas con camara -----------------------------------------------------
    def under_camera(self):
        return not self.dry and abs(self.reg.camera["zoom"] - 1.0) > 1e-6

    def shot_layer(self, tag, key):
        """Posicion y zoom finales de un sprite (pixeles de 1920x1080) para pre-renderizar una toma con camara."""
        w, h = atl_module.image_size(self.p, key)
        st = atl_module.State(w, h)
        st.__dict__.update({k: v for k, v in (self.reg.pos_state.get(tag) or {}).items() if k not in ("w", "h", "reveal")})
        xa, ya = st.effective()
        return {"key": key, "xalign": xa, "yalign": ya, "zoom": st.zoom}

    def prerender_camera_shots(self):
        """Una escena armada bajo `camera` con zoom (SCENE + SHOW) se reemplaza por una sola imagen ya encuadrada.

        En la PS1 escalar 3x los fondos de 320x180 se veria borroso; la toma se compone en la PC desde los originales
        (incluidos los sprites en alta resolucion) y el motor solo muestra un fondo fijo.
        """
        insts, out, i = self.ir.insts, [], 0
        while i < len(insts):
            inst = insts[i]
            shot = inst.args.pop("_shot", None)
            if inst.op == "SCENE" and shot:
                layers, i = [shot], i + 1
                while i < len(insts) and insts[i].op == "SHOW" and "_shot" in insts[i].args:
                    layers.append(insts[i].args.pop("_shot"))
                    i += 1
                inst.args.update(image=self.reg.camera_shot(layers, shot["camera"]), anim=0)
                out.append(inst)
                continue
            if shot:
                self.ir.warnings.append(f"{inst.file}:{inst.line}: {inst.op} bajo camera sin SCENE previo: se muestra sin zoom")
            out.append(inst)
            i += 1
        insts[:] = out

    def block(self, nodes, state):
        for node in nodes:
            if state is None and not isinstance(node, rp.Label):
                continue  # codigo inalcanzable hasta la proxima etiqueta
            state = self.node(node, state)
        return state

    def node(self, n, state):
        method = getattr(self, "n_" + type(n).__name__, None)
        if method is None:
            raise CompileError(f"{n.file}:{n.line}: nodo sin soporte {type(n).__name__}")
        return method(n, state)

    # -- flujo ----------------------------------------------------------------
    def n_Label(self, n, state):
        incoming = merge_states([state, self.pending.pop(n.name, None)])
        self.label = n.name
        self.emit("LABEL", n.line, name=n.name)
        state = incoming if incoming is not None else VState()
        return self.block(n.body, state)

    def n_Pass(self, n, state):
        return state

    def n_Return(self, n, state):
        self.emit("RETURN", n.line)
        return None

    def jump_to(self, target, state, n, mode_jump):
        chapter = self.p.label_chapter.get(target)
        if chapter is None:
            raise CompileError(f"{n.file}:{n.line}: etiqueta desconocida {target}")
        if chapter != self.ch.index:
            self.emit("LOAD_CHAPTER", n.line, chapter=chapter, entry=target, mode=1 if mode_jump else 0)
        else:
            self.emit("JUMP" if mode_jump else "CALL", n.line, target=target)
            if mode_jump:
                self.pending[target] = merge_states([self.pending.get(target), state])

    def n_Jump(self, n, state):
        if n.expression:
            raise CompileError(f"{n.file}:{n.line}: jump expression sin soporte")
        self.jump_to(n.target, state, n, True)
        return None

    def n_Call(self, n, state):
        if n.expression:
            raise CompileError(f"{n.file}:{n.line}: call expression sin soporte")
        self.jump_to(n.target, state, n, False)
        return state

    def n_CallScreen(self, n, state):
        if n.name == "textscroll":
            self.reg.textscroll_pages()
            self.emit("SPECIAL", n.line, id=SPECIAL_TEXTSCROLL)
        else:
            self.warn(n, f"call screen {n.name} ignorada")
        return state

    def n_Camera(self, n, state):
        """camera: zoom y desplazamiento de toda la escena (CAMERA) y desenfoque (variantes desenfocadas con disolver)."""
        cam = self.reg.camera
        for text, _ in n.atl:
            tokens = atl_module.split_tokens(text)
            curve, seconds, rest = 0, 0.0, tokens
            if tokens and atl_module.curve_for(tokens[0]) is not None:
                curve, seconds, rest = atl_module.curve_for(tokens[0]), rp.eval_number(tokens[1]), tokens[2:]
            moved, blur = False, None
            for name, raw in zip(rest[0::2], rest[1::2]):
                value = atl_module.parse_value(raw)
                if name == "zoom":
                    cam["zoom"], moved = float(value), True
                elif name == "xpos":
                    cam["x"], moved = float(value), True
                elif name == "ypos":
                    cam["y"], moved = float(value), True
                elif name == "blur":
                    blur = float(value)
                elif name not in ("perspective",):
                    self.warn(n, f"propiedad de camera no soportada: {name}")
            if moved:
                self.emit("CAMERA", n.line, zoom=int(round(cam["zoom"] * 256)), tx=int(cam["x"]), ty=int(cam["y"]),
                          time=frames(seconds), curve=curve)
            if blur is not None and blur != cam["blur"]:
                self.camera_blur(n, state, blur, seconds)
                cam["blur"] = blur
        return state

    def camera_blur(self, n, state, value, seconds):
        """Desenfoque de toda la escena: el fondo y los sprites pasan a su variante desenfocada con un disolver."""
        images = self.p.images
        for tag, keys in state.tags.items():
            key = sorted(keys)[0]
            recipe, flip = images.canonical(key)
            if recipe["op"] == "solid":
                continue
            target = key if value <= 0 else images.add_blur(key, value)
            iid, tflip = self.reg.image_id(target)
            if tag == "_scene":
                self.reg.mark_full(iid)
                self.emit("BACKGROUND", n.line, image=iid)
            else:
                self.emit("SHOW", n.line, tag=self.reg.tag(tag), image=iid, pos=POS_KEEP, z=Z_KEEP,
                          flags=FLAG_FLIP if tflip else 0, anim=0)
        self.emit("TRANSITION", n.line, type=1, a=frames(seconds) if seconds else 1, b=0, c=0)

    def n_Menu(self, n, state):
        end = self.new_label("menuend")
        branch_labels = [self.new_label("opt") for _ in n.choices]
        if n.caption:
            tr = self.p.tr.string(n.caption) or n.caption
            self.emit("SAY", n.line, speaker=0, text=self.add_string(None, tr))
        entries = []
        for (text, cond, _), lbl in zip(n.choices, branch_labels):
            es = self.p.tr.string(text)
            if es is None:
                raise CompileError(f"{n.file}:{n.line}: opcion de menu sin traduccion: {text}")
            entries.append((self.add_string(None, es, choice=True), lbl))
        self.emit("MENU", n.line, flags=0, choices=entries)
        outs = []
        for (text, cond, body), lbl in zip(n.choices, branch_labels):
            self.emit("LABEL", n.line, name=lbl)
            out = self.block(body, state.copy())
            if out is not None:
                self.emit("JUMP", n.line, target=end)
            outs.append(out)
        self.emit("LABEL", n.line, name=end)
        return merge_states(outs)

    def n_If(self, n, state):
        end = self.new_label("ifend")
        outs = []
        has_else = False
        for cond, body in n.branches:
            nxt = self.new_label("else")
            if cond is not None:
                self.expr(cond, n)
                self.emit("JUMP_IF_FALSE", n.line, target=nxt)
            else:
                has_else = True
            out = self.block(body, state.copy())
            if out is not None:
                self.emit("JUMP", n.line, target=end)
            outs.append(out)
            self.emit("LABEL", n.line, name=nxt)
        if not has_else:
            outs.append(state.copy())
        self.emit("LABEL", n.line, name=end)
        return merge_states(outs)

    def n_While(self, n, state):
        top, end = self.new_label("while"), self.new_label("wend")
        self.dry += 1
        probe = self.block(n.body, state.copy())
        self.dry -= 1
        body_state = merge_states([state, probe]) or state
        self.emit("LABEL", n.line, name=top)
        self.expr(n.cond, n)
        self.emit("JUMP_IF_FALSE", n.line, target=end)
        out = self.block(n.body, body_state.copy())
        self.emit("JUMP", n.line, target=top)
        self.emit("LABEL", n.line, name=end)
        return merge_states([state, out])

    # -- dialogo --------------------------------------------------------------
    def n_Say(self, n, state):
        who = n.who
        tid = n.text_id or self.p.tr.lookup(self.label, n.text)
        if who is not None and who not in self.p.speakers:
            if re.fullmatch(r"\w+", who):
                raise CompileError(f"{n.file}:{n.line}: hablante desconocido {who}")
            # nombre escrito como texto ("Trevor & Tana"): la traduccion lo trae en la linea ("Trevor y Tana")
            self.p.add_speaker(who, self.p.tr.speaker(tid) if tid else None)
        es = self.p.tr.dialogue(tid) if tid else None
        if es is None:
            if n.text.strip() == "":
                es = ""
            else:
                raise CompileError(f"{n.file}:{n.line}: dialogo sin traduccion: {n.text[:50]}")
        if n.with_:
            self.transition(n.with_, n)
        self.emit("SAYX" if n.extend else "SAY", n.line, speaker=self.p.speakers.get(who, 0), text=self.add_string(tid, es))
        return state

    def n_Window(self, n, state):
        self.emit("TEXTBOX", n.line, mode=textbox_mode(n.kind, n.trans))
        return state

    def n_Pause(self, n, state):
        self.emit("PAUSE", n.line, frames=0 if n.seconds is None else frames(n.seconds), flags=1)
        return state

    def n_With(self, n, state):
        self.transition(n.trans, n)
        return state

    # -- imagenes -------------------------------------------------------------
    def transition(self, expr, node):
        spec = parse_transition(expr)
        if spec is None:
            self.warn(node, f"transicion no soportada, se usa corte: {expr}")
            spec = (0, 0, 0, 0)
        self.emit("TRANSITION", node.line, type=spec[0], a=spec[1], b=spec[2], c=spec[3])

    def resolve(self, words, tag, state, node):
        """Elige la imagen para `show` segun el estado; devuelve la clave de imagen."""
        current = state.tags.get(tag, set()) if tag else set()
        if not current and tag in self.reg.last_key:
            current = {self.reg.last_key[tag]}   # Ren'Py recuerda los atributos de un tag aunque se oculte o cambie la escena
        if words[0] in self.p.images.layered:
            attrs = next(iter(current))[1:] if current else ()
            return self.p.images.resolve_layered(words, attrs)
        keys = set()
        for cur in (current or {()}):
            attrs = cur[1:] if cur else ()
            if len(words) == 1 and cur and words[0] == cur[0]:
                keys.add(cur)
            else:
                key = self.p.images.resolve(words, attrs)
                if key is None and len(words) == 1 and not cur:
                    key = None
                keys.add(key)
        if None in keys and len(keys) > 1:
            keys.discard(None)
        if keys == {None}:
            raise CompileError(f"{node.file}:{node.line}: imagen no resuelta: {' '.join(words)} (tag {tag})")
        if len(keys) > 1:
            self.warn(node, f"imagen ambigua {' '.join(words)}: {sorted(' '.join(k) for k in keys)}")
        return sorted(keys, key=lambda k: (len(k), k))[0]

    def n_Scene(self, n, state):
        key = self.p.images.resolve(n.image)
        if key is None:
            raise CompileError(f"{n.file}:{n.line}: fondo no resuelto: {' '.join(n.image)}")
        iid, flip = self.reg.image_id(key)
        anim = 0
        spec = self.p.images.animation_of(key)
        if spec:
            import types
            node = types.SimpleNamespace(tag="_scene", atl=None, at=[], line=n.line, file=n.file)
            self.reg.last_key["_scene"] = key
            anim, _ = atl_module.compile_anim(self, node, [], slideshow=spec)
        else:
            pan = PAN_RE.search(", ".join(n.at))
            if pan:
                x0, y0, x1, y1, seconds = (float(v) for v in pan.groups())
                anim = atl_module.compile_pan(self, key, (x0, y0), (x1, y1), seconds)
        # Ren'Py olvida el estado de los transforms al vaciar la escena: lo siguiente empieza en la posicion por defecto
        self.reg.pos_state.clear()
        if not spec and not pan and n.atl:
            framed = self.framed_scene(n, key)
            if framed is not None:
                iid, flip = framed, False
        self.reg.mark_full(iid)
        self.emit("SCENE", n.line, image=iid, anim=anim | (SCENE_FLIP if flip else 0))
        if self.under_camera():
            self.ir.insts[-1].args["_shot"] = {"key": key, "xalign": 0.5, "yalign": 1.0, "zoom": 1.0,
                                               "camera": dict(self.reg.camera)}
        state = VState()
        state.tags["_scene"] = {key}
        if n.with_:
            self.transition(n.with_, n)
        return state

    def framed_scene(self, n, key):
        """`scene X:` con bloque ATL (zoom, desenfoque, desplazamiento): el fondo se pre-renderiza encuadrado como queda
        al terminar el bloque. None si el bloque no cambia nada visible (por ejemplo `size(1920, 1080)`)."""
        import types
        node = types.SimpleNamespace(tag="_scene", atl=n.atl, at=[], line=n.line, file=n.file)
        self.reg.last_key["_scene"] = key
        atl_module.compile_anim(self, node, [])
        w, h = atl_module.image_size(self.p, key)
        st = atl_module.State(w, h)
        st.__dict__.update({k: v for k, v in self.reg.pos_state.pop("_scene", {}).items() if k not in ("w", "h")})
        xa, ya = st.effective()
        left = xa * (atl_module.SCREEN_W - w * st.zoom)
        top = ya * (atl_module.SCREEN_H - h * st.zoom)
        if abs(st.zoom - 1.0) < 1e-3 and not st.blur and abs(left) < 1 and abs(top) < 1:
            return None
        return self.reg.camera_shot([{"key": key, "xalign": xa, "yalign": ya, "zoom": st.zoom, "blur": st.blur}],
                                    {"zoom": 1.0, "x": 0.0, "y": 0.0})

    def n_Show(self, n, state):
        if n.image[0] == "expression":
            return self.show_expression(n, state)
        key = self.resolve(n.image, n.tag, state, n)
        self.reg.last_key[n.tag] = key
        iid, flip = self.reg.image_id(key)
        existing = n.tag in state.tags
        if existing and n.tag not in state.z:
            state.z[n.tag] = max(state.z.values(), default=0)
        if existing and not n.behind:
            z = Z_KEEP
        elif n.behind:
            ref = n.behind[0].split()[-1] if n.behind[0] else None
            base = state.z.get(ref, max(state.z.values(), default=0) + 1)
            z = max(-100, base - 1)
            state.z[n.tag] = z
        else:
            z = min(120, max(state.z.values(), default=0) + 1)
            state.z[n.tag] = z
        pos = POS_NONE
        extra_transforms = []
        for name in n.at:
            if name in self.p.positions and pos == POS_NONE:
                pos = self.p.positions[name]
            elif name in self.p.transforms:
                extra_transforms.append(name)
            elif name not in ("vpunch", "hpunch", "center"):
                self.warn(n, f"transform desconocido: {name}")
        spec = self.p.images.animation_of(key)
        patched = bool(spec and spec.get("patch"))
        anim, final = atl_module.compile_anim(self, n, extra_transforms, slideshow=None if patched else spec)
        flags = FLAG_FLIP if flip else 0
        self.emit("SHOW", n.line, tag=self.reg.tag(n.tag), image=iid, pos=pos, z=self.zorder(n), flags=flags, anim=anim)
        shown = self.ir.insts[-1] if not self.dry else None
        self.emit_behind(n, state)
        if patched:
            self.show_patch(n, state, spec, pos, z)
        self.track_visibility(n.tag, iid, pos, anim, bool(flip))
        if shown is not None and self.under_camera():
            shown.args["_shot"] = self.shot_layer(n.tag, key)
        state.tags[n.tag] = {final or key}
        if final:
            self.reg.last_key[n.tag] = final
        if n.with_:
            self.transition(n.with_, n)
        return state

    @staticmethod
    def zorder(n):
        """z del SHOW: el `zorder` explicito o Z_KEEP (el orden lo lleva el motor: lo nuevo va encima, como Ren'Py)."""
        return Z_KEEP if getattr(n, "zorder", None) is None else max(-100, min(120, n.zorder))

    def emit_behind(self, n, state):
        """`behind a, b`: ORDER por cada referencia deja el tag detras de la mas baja. Sus companeros lo siguen."""
        for ref in n.behind:
            ref = ref.split()[-1] if ref else None
            if ref and ref != n.tag:
                self.emit("ORDER", n.line, tag=self.reg.tag(n.tag), ref=self.reg.tag(ref), above=0)
        if n.behind:
            for companion in state.comp.get(n.tag, []):
                self.emit("ORDER", n.line, tag=self.reg.tag(companion), ref=self.reg.tag(n.tag), above=1)

    def show_patch(self, n, state, spec, pos, z):
        """Video como parches: segundo sprite (tag~patch) encima de la imagen base, que cambia de parche con el tiempo."""
        import types
        ptag = n.tag + "~patch"
        pkey = spec["frames"][0]
        piid, _ = self.reg.image_id(pkey)
        node = types.SimpleNamespace(tag=ptag, atl=None, at=[], line=n.line, file=n.file)
        self.reg.last_key[ptag] = pkey
        panim, _ = atl_module.compile_anim(self, node, [], slideshow=spec)
        pz = Z_KEEP if z == Z_KEEP else min(120, z + 1)
        self.emit("SHOW", n.line, tag=self.reg.tag(ptag), image=piid, pos=pos, z=self.zorder(n), flags=0, anim=panim)
        self.emit("ORDER", n.line, tag=self.reg.tag(ptag), ref=self.reg.tag(n.tag), above=1)
        state.z[ptag] = pz if pz != Z_KEEP else state.z.get(n.tag, 0) + 1
        state.comp.setdefault(n.tag, [])
        if ptag not in state.comp[n.tag]:
            state.comp[n.tag].append(ptag)

    def track_visibility(self, tag, iid, pos, anim, flip):
        """Registra la zona de la imagen que llega a verse en pantalla (para recortar el resto en la Fase 4)."""
        from tools.script_compiler.atl import SCREEN_H, SCREEN_W, recipe_size
        if self.dry:
            return
        aligns, full = [], False
        ids = [iid]
        if anim:
            _, keys, swaps = self.ir.anims[anim - 1]
            for k in keys:
                if k[5] != 64 or k[6] != 64 or k[7] != 0 or k[11] != 255:
                    full = True      # zoom, giro, espejo o recorte animados: se conserva la imagen completa
                aligns.append((k[1] / 256.0, k[2] / 256.0))
            ids += [sw[1] for sw in swaps if not sw[2] & 2]
        elif pos != POS_NONE and pos != POS_KEEP:
            info = self.p.position_info[pos]
            aligns.append((info["xalign"], info["yalign"]))
        else:
            previous = self.reg.pos_state.get(tag)
            if previous:
                aligns.append((previous.get("xalign", 0.5), previous.get("yalign", 1.0)))
            else:
                aligns.append((0.5, 1.0))
        if pos != POS_NONE and pos != POS_KEEP and not anim:
            info = self.p.position_info[pos]
            self.reg.pos_state[tag] = {"xalign": info["xalign"], "yalign": info["yalign"], "xpos": None, "ypos": None,
                                       "xanchor": info["xalign"], "yanchor": info["yalign"]}
        elif pos == POS_NONE and not anim and tag not in self.reg.pos_state:
            # `show x` sin `at` ni ATL: transform por defecto de Ren'Py (centro abajo), que hereda el siguiente ATL
            self.reg.pos_state[tag] = {"xalign": 0.5, "yalign": 1.0, "xpos": None, "ypos": None, "xanchor": 0.5, "yanchor": 1.0}
        for image_id in ids:
            if full:
                self.reg.mark_full(image_id)
                continue
            w, h = recipe_size(self.reg.images[image_id]["recipe"])
            for xa, ya in aligns:
                x = xa * (SCREEN_W - w)
                y = ya * (SCREEN_H - h)
                c0, c1 = max(0.0, -x), min(w, SCREEN_W - x)
                r0, r1 = max(0.0, -y), min(h, SCREEN_H - y)
                if c1 <= c0 or r1 <= r0:
                    continue          # fuera de pantalla en esta clave
                if flip:
                    c0, c1 = w - c1, w - c0
                margin = 0.04
                self.reg.mark_rect(image_id, (max(0, c0 - margin * w), max(0, r0 - margin * h),
                                              min(w, c1 + margin * w), min(h, r1 + margin * h)))

    def resolve_swap(self, words, tag, prev_key, node):
        """Imagen a la que cambia un ATL (`"anon happy" with dissolve`), con los atributos actuales del tag."""
        attrs = prev_key[1:] if prev_key else ()
        if words[0] in self.p.images.layered:
            return self.p.images.resolve_layered(words, attrs)
        key = self.p.images.resolve(words, attrs)
        if key is None:
            raise CompileError(f"{node.file}:{node.line}: imagen de ATL no resuelta: {' '.join(words)}")
        return key

    def show_expression(self, n, state):
        """show expression AlphaMask(contenido, At(mascara, transformaciones)): silueta o franja que se abre."""
        import types
        try:
            call = ast.parse(" ".join(n.image[1:]), mode="eval").body
            content = call.args[0].value
            mask_arg = call.args[1]
            if isinstance(mask_arg, ast.Call):
                mask = mask_arg.args[0].value
                transforms = [a.id for a in mask_arg.args[1:] if isinstance(a, ast.Name)]
            else:
                mask, transforms = mask_arg.value, []
            assert ast.unparse(call.func) == "AlphaMask"
        except (SyntaxError, AttributeError, IndexError, AssertionError):
            raise CompileError(f"{n.file}:{n.line}: show expression sin soporte: {' '.join(n.image)}")
        images = self.p.images
        reveal_tfs = [t for t in transforms if any("yzoom" in text for text, _ in self.p.transforms.get(t, []))]
        node = types.SimpleNamespace(tag=n.tag, atl=n.atl, at=list(n.at), line=n.line, file=n.file)
        if reveal_tfs:
            ckey, mkey = images.resolve(content.split()), images.resolve(mask.split())
            if ckey is None or mkey is None:
                raise CompileError(f"{n.file}:{n.line}: imagen de AlphaMask no resuelta")
            ratio = atl_module.image_size(self.p, mkey)[1] / atl_module.image_size(self.p, ckey)[1]
            self.reg.last_key[n.tag] = ckey
            anim, _ = atl_module.compile_anim(self, node, reveal_tfs, reveal=ratio, atl_first=True)
            key = ckey
        else:
            key = images.add_alphamask(content.split(), mask.split())
            if key is None:
                raise CompileError(f"{n.file}:{n.line}: imagen de AlphaMask no resuelta")
            self.reg.last_key[n.tag] = key
            node.at = list(n.at) + transforms
            extra = [t for t in node.at if t in self.p.transforms and t not in self.p.positions]
            anim, _ = atl_module.compile_anim(self, node, extra)
        iid, flip = self.reg.image_id(key)
        existing = n.tag in state.tags
        top = max(state.z.values(), default=0)
        z = Z_KEEP if existing and not n.behind else min(120, top + 1)
        if z != Z_KEEP:
            state.z[n.tag] = z
        pos = next((self.p.positions[a] for a in node.at if a in self.p.positions), POS_NONE)
        self.emit("SHOW", n.line, tag=self.reg.tag(n.tag), image=iid, pos=pos, z=self.zorder(n), flags=FLAG_FLIP if flip else 0,
                  anim=anim)
        self.emit_behind(n, state)
        state.tags[n.tag] = {key}
        if n.with_:
            self.transition(n.with_, n)
        return state

    def n_Hide(self, n, state):
        self.emit("HIDE", n.line, tag=self.reg.tag(n.tag))
        self.reg.pos_state.pop(n.tag, None)
        for companion in state.comp.pop(n.tag, []):
            self.emit("HIDE", n.line, tag=self.reg.tag(companion))
            self.reg.pos_state.pop(companion, None)
            state.z.pop(companion, None)
        state.tags.pop(n.tag, None)
        state.z.pop(n.tag, None)
        if n.with_:
            self.transition(n.with_, n)
        return state

    # -- audio ----------------------------------------------------------------
    def audio(self, name, node):
        if name.startswith("<"):
            return None
        return self.reg.audio_id(name)

    def n_Play(self, n, state):
        ch = n.channel
        fade = tenths(n.fadein)
        if ch in MUSIC_CHANNELS:
            return self.play_music(n, state, fade)
        for src in n.sources:
            track = self.audio(src, n)
            if ch in AMBIENT_SLOTS:
                if track is not None:
                    self.emit("AMBIENT_PLAY", n.line, slot=AMBIENT_SLOTS[ch], sound=track, fade=fade)
            elif ch in SFX_CHANNELS:
                if track is not None:
                    self.emit("SFX_PLAY", n.line, sound=track)
            else:
                self.warn(n, f"canal de audio desconocido: {ch}")
        return state

    @staticmethod
    def clean_audio_name(src):
        """Quita prefijos de Ren'Py como <sync music> y devuelve (ruta, sincronizado)."""
        sync = src.startswith("<sync")
        return (src.split(">", 1)[1] if src.startswith("<") and not src.startswith("<silence") else src), sync

    def music_flags(self, sync):
        active = self.reg.music
        return (1 if len(active) > 1 else 0) | (2 if sync else 0)

    def play_music(self, n, state, fade):
        """Musica en varios canales de Ren'Py -> un solo flujo XA: los cruces son reemplazos y las capas (stems) son mezclas."""
        reg = self.reg
        ch = n.channel
        names = [self.clean_audio_name(s) for s in n.sources]
        if n.verb == "queue":
            for name, _ in names:
                track = self.audio(name, n)
                self.emit("MUSIC_STOP", n.line, fade=0) if track is None else self.emit("MUSIC_QUEUE", n.line, track=track)
            return state
        first, sync = names[0]
        if first.startswith("<silence"):
            reg.music.pop(ch, None)
            self.emit("MUSIC_STOP", n.line, fade=0)
            return state
        path = self.p.audio_path(first)
        if path is None:
            raise CompileError(f"{n.file}:{n.line}: audio no encontrado: {first}")
        reg.music[ch] = path
        reg.music_cur = ch
        if "stem" in path.lower():
            self.emit_stem_mix(n, fade, sync)
        else:
            self.emit("MUSIC_PLAY", n.line, track=reg.audio_id(first), fade=fade, flags=self.music_flags(False))
            for extra, _ in names[1:]:
                if extra != first and not extra.startswith("<silence"):
                    self.emit("MUSIC_QUEUE", n.line, track=reg.audio_id(extra))
        return state

    def emit_stem_mix(self, n, fade, sync):
        """Capas de una misma cancion (stems) que suenan a la vez: se mezclan en la PC; el motor cambia de carril sincronizado."""
        stems = sorted({p for p in self.reg.music.values() if "stem" in p.lower()})
        flags = 2 if (sync or len(stems) > 1) else 0
        self.emit("MUSIC_PLAY", n.line, track=self.reg.audio_mix(stems), fade=fade, flags=flags)

    def n_Stop(self, n, state):
        fade = tenths(n.fadeout)
        if n.channel in MUSIC_CHANNELS:
            reg = self.reg
            path = reg.music.pop(n.channel, None)
            if path is None:
                return state
            if "stem" in path.lower():
                stems = sorted({p for p in reg.music.values() if "stem" in p.lower()})
                if stems:
                    self.emit("MUSIC_PLAY", n.line, track=reg.audio_mix(stems), fade=fade, flags=2)
                else:
                    self.emit("MUSIC_STOP", n.line, fade=fade)
            elif reg.music_cur == n.channel or not reg.music:
                self.emit("MUSIC_STOP", n.line, fade=fade)
            # si otro canal sigue sonando, es la salida de un cruce de canciones: el flujo unico ya cambio
        elif n.channel in AMBIENT_SLOTS:
            self.emit("AMBIENT_STOP", n.line, slot=AMBIENT_SLOTS[n.channel], fade=fade)
        elif n.channel in SFX_CHANNELS:
            self.emit("SFX_STOP", n.line, fade=fade)
        return state

    # -- variables y Python ----------------------------------------------------
    def expr(self, text, node):
        try:
            tree = ast.parse(text.strip(), mode="eval").body
        except SyntaxError as exc:
            raise CompileError(f"{node.file}:{node.line}: condicion invalida {text}: {exc}")
        self.expr_node(tree, node)

    def expr_node(self, t, node):
        if isinstance(t, ast.Constant):
            value = t.value
            if value is None:
                value = 0
            self.emit("PUSH_CONST", node.line, value=int(value))
        elif isinstance(t, ast.Name):
            self.emit("PUSH_VAR", node.line, var=self.reg.var(t.id))
        elif isinstance(t, ast.Attribute) and ast.unparse(t) == "persistent.lewd":
            self.emit("PUSH_CONST", node.line, value=1)   # material picante siempre activado
        elif isinstance(t, ast.Compare):
            self.expr_node(t.left, node)
            self.expr_node(t.comparators[0], node)
            self.emit("OP", node.line, op=OP_CODE[{ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}[type(t.ops[0])]])
            for op, comp in zip(t.ops[1:], t.comparators[1:]):
                raise CompileError(f"{node.file}:{node.line}: comparacion encadenada")
        elif isinstance(t, ast.BoolOp):
            self.expr_node(t.values[0], node)
            for v in t.values[1:]:
                self.expr_node(v, node)
                self.emit("OP", node.line, op=OP_CODE["and" if isinstance(t.op, ast.And) else "or"])
        elif isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
            self.expr_node(t.operand, node)
            self.emit("OP", node.line, op=OP_CODE["not"])
        elif isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.USub) and isinstance(t.operand, ast.Constant):
            self.emit("PUSH_CONST", node.line, value=-int(t.operand.value))
        elif isinstance(t, ast.BinOp) and type(t.op) in (ast.Add, ast.Sub, ast.Mult):
            self.expr_node(t.left, node)
            self.expr_node(t.right, node)
            self.emit("OP", node.line, op=OP_CODE[{ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(t.op)]])
        else:
            raise CompileError(f"{node.file}:{node.line}: expresion sin soporte: {ast.unparse(t)}")

    def n_Define(self, n, state):
        return state

    def n_Transform(self, n, state):
        self.p.transforms[n.name] = n.atl
        return state

    def n_Py(self, n, state):
        if n.block:
            return self.py_block(n, state)
        try:
            body = ast.parse(n.code).body
        except SyntaxError as exc:
            raise CompileError(f"{n.file}:{n.line}: python invalido: {exc}")
        for stmt in body:
            self.py_stmt(stmt, n)
        return state

    def py_stmt(self, s, node):
        if isinstance(s, (ast.Assign, ast.AugAssign)):
            target = s.targets[0] if isinstance(s, ast.Assign) else s.target
            if isinstance(target, ast.Name):
                var = self.reg.var(target.id)
                if isinstance(s, ast.AugAssign) and isinstance(s.value, ast.Constant) and isinstance(s.op, (ast.Add, ast.Sub)):
                    value = int(s.value.value)
                    self.emit("ADD_VAR", node.line, var=var, value=value if isinstance(s.op, ast.Add) else -value)
                elif isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant):
                    v = s.value.value
                    self.emit("SET_VAR", node.line, var=var, value=0 if v is None else int(v))
                else:
                    if isinstance(s, ast.AugAssign):
                        self.emit("PUSH_VAR", node.line, var=var)
                        self.expr_node(s.value, node)
                        self.emit("OP", node.line, op=OP_CODE[{ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(s.op)]])
                    else:
                        self.expr_node(s.value, node)
                    self.emit("STORE_VAR", node.line, var=var)
                return
            if isinstance(target, ast.Attribute) and ast.unparse(target) == "persistent.bonus_chapters":
                m = re.search(r"<<\s*(\d+)", ast.unparse(s.value))
                if m:
                    self.emit("UNLOCK_BONUS", node.line, n=int(m.group(1)))
                    return
            if isinstance(target, ast.Attribute) and ast.unparse(target).startswith("persistent."):
                self.warn(node, f"persistent ignorado: {ast.unparse(s)}")
                return
            raise CompileError(f"{node.file}:{node.line}: asignacion sin soporte: {ast.unparse(s)}")
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
            self.py_call(s.value, node)
            return
        raise CompileError(f"{node.file}:{node.line}: python sin soporte: {ast.unparse(s)[:80]}")

    def py_call(self, call, node):
        name = ast.unparse(call.func)
        if name == "webbrowser.open":
            self.warn(node, f"{name} ignorada (funcion de PC)")
            return
        if name == "renpy.input":
            # teclado en pantalla; lo escrito no se usa en el guion
            self.emit("SPECIAL", node.line, id=SPECIAL_INPUT)
            return
        args = [self.const(a) for a in call.args]
        kwargs = {k.arg: self.const(k.value) for k in call.keywords}
        if name == "renpy.music.set_volume":
            vol, delay, channel = (list(args) + [None, None, None])[:3]
            channel = kwargs.get("channel", channel) or "music"
            delay = kwargs.get("delay", delay) or 0
            self.emit("VOLUME", node.line, channel=VOLUME_CHANNELS.get(channel, 0), volume=int(max(0, min(255, round(float(vol) * 255)))), time=tenths(delay))
        elif name == "renpy.mark_image_seen":
            key = self.p.images.resolve(args[0].split())
            if key is None and args[0] in self.p.gallery_images:
                # el original usa el nombre del elemento de galeria en vez del de la imagen (error): se corrige
                key = self.p.images.resolve(self.p.gallery_images[args[0]].split())
                self.warn(node, f"mark_image_seen('{args[0]}') corregido a la imagen de galeria '{self.p.gallery_images[args[0]]}'")
            if key is None:
                self.warn(node, f"mark_image_seen de imagen inexistente (sin efecto en el original): {args[0]}")
                return
            iid, _ = self.reg.image_id(key)
            self.emit("MARK_SEEN", node.line, image=iid)
        elif name == "showCG":
            keys = [self.p.images.resolve((f"text{i}",)) for i in range(1, 10)]
            ids = [self.reg.image_id(k)[0] for k in keys]
            for i in ids:
                self.reg.mark_full(i)
            if ids != list(range(ids[0], ids[0] + 9)):
                raise CompileError("las imagenes text1..text9 no tienen IDs consecutivos")
            self.emit("SHOW_RANDOM", node.line, tag=self.reg.tag("textlayer"), first=ids[0], count=9, flags=0)
        elif name == "renpy.music.stop":
            self.emit("MUSIC_STOP", node.line, fade=tenths(kwargs.get("fadeout", 0)))
        elif name == "renpy.pause":
            self.emit("PAUSE", node.line, frames=frames(float(args[0])) if args else 0, flags=1)
        elif name == "renpy.quit":
            self.emit("END", node.line)
        elif name == "renpy.music.queue":
            track = self.audio(args[0], node)
            if track is not None:
                self.emit("MUSIC_QUEUE", node.line, track=track)
        elif name == "setup_ending":
            self.counter += 1
            if not self.dry:
                self.ir.insts.extend(get_ending_insts(self.reg, f".ending{self.counter}", node.line, self.ch.name))
        elif name in ("ending_image", "toggle_debug"):
            self.warn(node, f"{name}() lo cubre el motor (progreso de finales)")
        else:
            raise CompileError(f"{node.file}:{node.line}: llamada sin soporte: {ast.unparse(call)[:80]}")

    def const(self, t):
        try:
            return ast.literal_eval(t)
        except Exception:
            raise CompileError(f"argumento no constante: {ast.unparse(t)}")

    # -- menus escritos en Python ---------------------------------------------
    def py_block(self, n, state):
        try:
            body = ast.parse(n.code).body
        except SyntaxError as exc:
            raise CompileError(f"{n.file}:{n.line}: python invalido: {exc}")
        env = self.pyenv
        for i, s in enumerate(body):
            if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name):
                name = s.targets[0].id
                if name == "choices":
                    value = s.value
                    if isinstance(value, ast.Call) and ast.unparse(value.func) == "randomize_choices":
                        env["shuffle"] = True
                    elif isinstance(value, (ast.List, ast.Tuple)):
                        env["choices"] = self.parse_choices(value, n)
                        env["shuffle"] = False
                    continue
                if name == "_tick":
                    env["_tick"] = self.const(s.value)
                    continue
                if name == "_value" and isinstance(s.value, ast.Call) and ast.unparse(s.value.func) == "renpy.display_menu":
                    return self.py_menu(n, s.value, body[i + 1:], state)
            if isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name) and s.target.id == "_tick":
                env["_tick"] = env.get("_tick", 0) + self.const(s.value)
                continue
            if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and ast.unparse(s.value.func) == "renpy.jump" \
                    and isinstance(s.value.args[0], ast.Call) and ast.unparse(s.value.args[0].func) == "renpy.display_menu":
                fake = ast.parse("renpy.jump(_value)").body
                return self.py_menu(n, s.value.args[0], fake, state)
            self.py_stmt(s, n)
        return state

    def parse_choices(self, node, n):
        out = []
        for elt in node.elts:
            text_node, label_node = elt.elts
            text = text_node.args[0].value if isinstance(text_node, ast.Call) else text_node.value
            out.append((text, label_node.value))
        return out

    def py_menu(self, n, call, rest, state):
        env = self.pyenv
        arg = call.args[0]
        shuffle = env.get("shuffle", False)
        if isinstance(arg, ast.Call) and ast.unparse(arg.func) == "randomize_choices":
            shuffle = True
        choices = env.get("choices")
        if choices is None:
            raise CompileError(f"{n.file}:{n.line}: menu en Python sin lista de opciones")
        entries, labels = [], []
        for text, target in choices:
            es = self.p.tr.string(text)
            if es is None:
                raise CompileError(f"{n.file}:{n.line}: opcion de menu sin traduccion: {text}")
            lbl = self.new_label("pyopt")
            labels.append(lbl)
            entries.append((self.add_string(None, es, choice=True), lbl))
        self.emit("MENU", n.line, flags=1 if shuffle else 0, choices=entries)
        end = self.new_label("pyend")
        outs = []
        fall_env = None
        for (text, target), lbl in zip(choices, labels):
            self.emit("LABEL", n.line, name=lbl)
            benv = dict(env)
            benv["_value"] = target
            alive = self.py_branch(n, rest, benv, state.copy())
            if alive is not None:
                self.emit("JUMP", n.line, target=end)
                fall_env = benv
            outs.append(alive)
        self.emit("LABEL", n.line, name=end)
        if fall_env is not None:
            self.pyenv = {k: v for k, v in fall_env.items() if k != "_value"}
        return merge_states(outs)

    def py_branch(self, n, stmts, env, state):
        for s in stmts:
            if state is None:
                return None
            if isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name) and s.target.id == "_tick":
                env["_tick"] = env.get("_tick", 0) + self.const(s.value)
            elif isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name) and s.targets[0].id == "_tick":
                env["_tick"] = self.const(s.value)
            elif isinstance(s, ast.If):
                chosen = s.body if self.eval_const(s.test, env) else s.orelse
                state = self.py_branch(n, chosen, env, state)
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and ast.unparse(s.value.func) == "renpy.jump":
                target = self.eval_const(s.value.args[0], env)
                self.jump_to(target, state, n, True)
                return None
            else:
                self.py_stmt(s, n)
        return state

    def eval_const(self, t, env):
        if isinstance(t, ast.Constant):
            return t.value
        if isinstance(t, ast.Name):
            return env[t.id]
        if isinstance(t, ast.BinOp) and isinstance(t.op, ast.Add):
            return self.eval_const(t.left, env) + self.eval_const(t.right, env)
        if isinstance(t, ast.Call) and ast.unparse(t.func) == "chr":
            return chr(self.eval_const(t.args[0], env))
        if isinstance(t, ast.Compare) and len(t.ops) == 1:
            a, b = self.eval_const(t.left, env), self.eval_const(t.comparators[0], env)
            return {ast.Eq: a == b, ast.NotEq: a != b}[type(t.ops[0])]
        raise CompileError(f"expresion constante sin soporte: {ast.unparse(t)}")


DIRECTIONS = {"left": 1, "right": 2, "top": 3, "bottom": 4}
TRANSITION_NAMES = {
    "dissolve": (1, 30, 0, 0), "fade": (2, 30, 0, 30), "vpunch": (3, 17, 10, 0), "hpunch": (4, 17, 15, 0),
    "None": (0, 0, 0, 0), "move": (5, 30, 0, 0), "ease": (5, 30, 0, 3),
}
# familia MoveTransition: (5, cuadros, direccion de entrada | direccion de salida << 4, curva)
for _name, _d in DIRECTIONS.items():
    TRANSITION_NAMES[f"movein{_name}"] = (5, 30, _d, 0)
    TRANSITION_NAMES[f"moveout{_name}"] = (5, 30, _d << 4, 0)
    TRANSITION_NAMES[f"easein{_name}"] = (5, 30, _d, 1)
    TRANSITION_NAMES[f"easeout{_name}"] = (5, 30, _d << 4, 2)
TIME_WARPS = {"_ease_in_time_warp": 1, "_ease_out_time_warp": 2, "_ease_time_warp": 3}


def is_light(color):
    """Color de un Fade ('#fff', '#ffffff'...): claro = fundido por blanco."""
    digits = color.lstrip("#")
    if len(digits) in (3, 4):
        digits = "".join(c * 2 for c in digits[:3])
    try:
        r, g, b = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return False
    return (r + g + b) / 3 > 128


def textbox_mode(kind, trans):
    """Modo de TEXTBOX para `window hide/auto/show [transicion]`; las transiciones de un cuadro o menos son instantaneas."""
    mode = {"hide": 0, "auto": 1, "show": 2}.get(kind, 1)
    spec = parse_transition(trans) if trans else None
    if spec is not None and spec[1] <= 1:
        mode |= TEXTBOX_INSTANT
    return mode


def parse_transition(expr):
    """Interpreta una expresion de transicion de Ren'Py. Devuelve (tipo, a, b, c) en cuadros o None."""
    expr = expr.strip()
    if expr in TRANSITION_NAMES:
        return TRANSITION_NAMES[expr]
    try:
        tree = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None
    if isinstance(tree, ast.Call):
        name = ast.unparse(tree.func)
        nums = []
        for a in tree.args:
            try:
                nums.append(float(ast.literal_eval(a)))
            except Exception:
                pass
        if name == "Dissolve" and nums:
            return (1, frames(nums[0]), 0, 0)
        if name == "Fade" and len(nums) >= 3:
            color = next((k.value.value for k in tree.keywords if k.arg == "color" and isinstance(k.value, ast.Constant)), "#000")
            return (6 if is_light(color) else 2, frames(nums[0]), frames(nums[1]), frames(nums[2]))
        if name == "MoveTransition":
            kw = {k.arg: ast.unparse(k.value) for k in tree.keywords}
            enter = DIRECTIONS.get(kw.get("enter", "").replace("offscreen", ""), 0)
            leave = DIRECTIONS.get(kw.get("leave", "").replace("offscreen", ""), 0)
            return (5, frames(nums[0]) if nums else 30, enter | (leave << 4), TIME_WARPS.get(kw.get("time_warp", ""), 0))
        if name in ("Move", "ease", "easeinbottom"):
            return (0, 0, 0, 0)
        if name in ("ImageDissolve", "AlphaDissolve", "CropMove", "PushMove", "Pixellate", "ComposeTransition"):
            return (1, frames(nums[0]) if nums else 30, 0, 0)
    if isinstance(tree, ast.Name):
        return TRANSITION_NAMES.get(tree.id)
    return None
