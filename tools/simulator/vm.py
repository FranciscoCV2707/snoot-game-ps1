"""Maquina virtual en Python que ejecuta el bytecode como lo hara la PS1 (Fase 3, etapa 6).

Modos: exploracion automatica de todas las combinaciones de decisiones (con poda de estados repetidos) y
ejecucion de un camino fijo. Reporta etiquetas alcanzadas, finales, texto leido, imagenes y errores.
"""
from dataclasses import dataclass, field

from tools.script_compiler.opcodes import OPERATORS

MAX_STEPS = 3_000_000
MAX_CALL_DEPTH = 8
MAX_STACK = 16
MAX_SPRITES = 12
NUM_VARS = 64


class SimError(Exception):
    pass


@dataclass
class Coverage:
    labels: set = field(default_factory=set)
    text_ids: set = field(default_factory=set)
    images_shown: set = field(default_factory=set)
    audio_played: set = field(default_factory=set)
    endings: set = field(default_factory=set)
    bonus: set = field(default_factory=set)
    ends: int = 0
    errors: list = field(default_factory=list)
    max_sprites: int = 0
    peak: tuple = None
    max_depth: int = 0
    max_stack: int = 0
    states: int = 0
    runs: int = 0
    menus: set = field(default_factory=set)


class VM:
    def __init__(self, program, cov):
        self.p = program
        self.cov = cov

    def initial(self, chapter, pc=0):
        return {"ch": chapter, "pc": pc, "vars": [0] * NUM_VARS, "calls": [], "sprites": {}, "bg": 0, "stack": []}

    def run(self, st, choose=None):
        """Ejecuta hasta MENU/END. Devuelve ('menu', info) o ('end', None). Modifica `st`."""
        steps = 0
        p = self.p
        cov = self.cov
        while True:
            steps += 1
            if steps > MAX_STEPS:
                raise SimError("posible bucle infinito")
            ch = p.chapters[st["ch"]]
            pc = st["pc"]
            if pc >= len(ch.code):
                raise SimError(f"{ch.name}: pc fuera de rango {pc}")
            label = p.label_at.get((st["ch"], pc))
            if label:
                cov.labels.add(label)
            name, a, size = ch.decode(pc)
            st["pc"] = pc + size
            v = st["vars"]
            stack = st["stack"]
            if name in ("SAY", "SAYX"):
                if a["text"] >= ch.text_count:
                    raise SimError(f"{ch.name}@{pc}: texto fuera de rango {a['text']}")
                cov.text_ids.add(ch.text_base + a["text"])
            elif name == "SCENE":
                self.check_image(a["image"], ch, pc)
                st["bg"] = a["image"]
                st["sprites"] = {}
                self.note_image(a["image"])
            elif name == "SHOW":
                self.check_image(a["image"], ch, pc)
                st["sprites"][a["tag"]] = a["image"]
                real = sum(1 for im in st["sprites"].values() if p.images[im]["recipe"]["op"] != "solid")
                if real > cov.max_sprites:
                    cov.max_sprites = real
                    cov.peak = (ch.name, pc, [p.images[im]["names"][0] for im in st["sprites"].values()
                                              if p.images[im]["recipe"]["op"] != "solid"])
                self.note_image(a["image"])
            elif name == "SHOW_RANDOM":
                for i in range(a["count"]):
                    self.note_image(a["first"] + i)
            elif name == "HIDE":
                st["sprites"].pop(a["tag"], None)
            elif name == "MARK_SEEN":
                self.note_image(a["image"])
            elif name == "MUSIC_PLAY" or name == "MUSIC_QUEUE":
                cov.audio_played.add(a["track"])
            elif name == "AMBIENT_PLAY":
                cov.audio_played.add(a["sound"])
            elif name == "SFX_PLAY":
                cov.audio_played.add(a["sound"])
            elif name == "SET_VAR":
                v[a["var"]] = a["value"]
            elif name == "ADD_VAR":
                v[a["var"]] += a["value"]
            elif name == "PUSH_VAR":
                stack.append(v[a["var"]])
            elif name == "PUSH_CONST":
                stack.append(a["value"])
            elif name == "STORE_VAR":
                v[a["var"]] = stack.pop()
            elif name == "OP":
                self.op(stack, a["op"], ch, pc)
            elif name == "JUMP_IF_FALSE":
                if not stack.pop():
                    st["pc"] = a["target"]
            elif name == "JUMP":
                st["pc"] = a["target"]
            elif name == "CALL":
                self.push_call(st, st["ch"], st["pc"])
                st["pc"] = a["target"]
            elif name == "RETURN":
                if not st["calls"]:
                    cov.ends += 1
                    return "end", None
                st["ch"], st["pc"] = st["calls"].pop()
            elif name == "LOAD_CHAPTER":
                if a["chapter"] not in p.chapters:
                    raise SimError(f"{ch.name}@{pc}: capitulo inexistente {a['chapter']}")
                if a["mode"] == 0:
                    self.push_call(st, st["ch"], st["pc"])
                st["ch"], st["pc"] = a["chapter"], a["entry"]
            elif name == "END":
                cov.ends += 1
                return "end", None
            elif name == "UNLOCK_BONUS":
                cov.bonus.add(a["n"])
            elif name == "ENDING":
                cov.endings.add(a["id"])
            elif name == "MENU":
                cov.menus.add((st["ch"], pc))
                for text, _ in a["choices"]:
                    cov.text_ids.add(ch.text_base + text)
                return "menu", a["choices"]
            elif name == "HALT":
                raise SimError(f"{ch.name}@{pc}: HALT")
            cov.max_stack = max(cov.max_stack, len(stack))
            if len(stack) > MAX_STACK:
                raise SimError(f"{ch.name}@{pc}: pila de expresiones desbordada")

    def push_call(self, st, ch, pc):
        if len(st["calls"]) >= MAX_CALL_DEPTH:
            raise SimError("pila de CALL desbordada")
        st["calls"].append((ch, pc))
        self.cov.max_depth = max(self.cov.max_depth, len(st["calls"]))

    def check_image(self, image, ch, pc):
        if image >= len(self.p.images) or (image != 0 and self.p.images[image] is None):
            raise SimError(f"{ch.name}@{pc}: imagen inexistente {image}")

    def note_image(self, image):
        self.cov.images_shown.add(image)
        info = self.p.images[image] if image < len(self.p.images) else None
        if info and info.get("ending"):
            self.cov.endings.add(info["ending"])

    @staticmethod
    def op(stack, code, ch, pc):
        name = OPERATORS[code]
        if name == "not":
            stack.append(0 if stack.pop() else 1)
            return
        b, a = stack.pop(), stack.pop()
        stack.append({"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b,
                      "and": bool(a and b), "or": bool(a or b), "+": a + b, "-": a - b, "*": a * b}[name])
        stack[-1] = int(stack[-1])


def explore(program, starts):
    """Recorre todas las decisiones. starts: lista de (capitulo, pc)."""
    cov = Coverage()
    vm = VM(program, cov)
    visited = set()
    work = [vm.initial(ch, pc) for ch, pc in starts]
    while work:
        st = work.pop()
        try:
            kind, info = vm.run(st)
        except SimError as exc:
            cov.errors.append(str(exc))
            continue
        cov.runs += 1
        if kind == "end":
            continue
        key = (st["ch"], st["pc"], tuple(st["vars"]), tuple(st["calls"]))
        if key in visited:
            continue
        visited.add(key)
        cov.states = len(visited)
        for _, target in info:
            nxt = {"ch": st["ch"], "pc": target, "vars": list(st["vars"]), "calls": list(st["calls"]),
                   "sprites": dict(st["sprites"]), "bg": st["bg"], "stack": []}
            work.append(nxt)
    return cov
