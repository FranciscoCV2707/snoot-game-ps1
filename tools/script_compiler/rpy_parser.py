"""Parser del subconjunto de Ren'Py que usa Snoot Game (Fase 3, etapa 1).

Convierte un archivo .rpy en un arbol de nodos. Falla con un error claro (archivo:linea) ante una
instruccion desconocida, en vez de ignorarla. No modifica los archivos de origen.
"""
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tools.audit.inventario import STRING_RE, bracket_balance, strip_comment


class ParseError(Exception):
    pass


@dataclass
class Node:
    file: str
    line: int


@dataclass
class Label(Node):
    name: str
    body: list = field(default_factory=list)


@dataclass
class Say(Node):
    who: str | None
    text: str
    text_id: str | None
    extend: bool = False
    with_: str | None = None


@dataclass
class Scene(Node):
    image: tuple
    at: list
    with_: str | None
    atl: list | None = None


@dataclass
class Show(Node):
    image: tuple
    tag: str
    at: list
    behind: list
    with_: str | None
    atl: list | None = None
    zorder: int | None = None


@dataclass
class Hide(Node):
    tag: str
    with_: str | None


@dataclass
class With(Node):
    trans: str


@dataclass
class Play(Node):
    verb: str            # play | queue
    channel: str
    sources: list        # rutas de audio ("<silence 1.0>" incluida)
    fadein: float | None
    fadeout: float | None
    loop: bool | None


@dataclass
class Stop(Node):
    channel: str
    fadeout: float | None


@dataclass
class Pause(Node):
    seconds: float | None


@dataclass
class Window(Node):
    kind: str            # show | hide | auto
    trans: str | None


@dataclass
class Jump(Node):
    target: str
    expression: bool = False


@dataclass
class Call(Node):
    target: str
    expression: bool = False


@dataclass
class CallScreen(Node):
    name: str
    with_: str | None


@dataclass
class Return(Node):
    pass


@dataclass
class Pass(Node):
    pass


@dataclass
class Menu(Node):
    caption: str | None
    choices: list        # [(texto, condicion|None, cuerpo)]


@dataclass
class If(Node):
    branches: list       # [(condicion|None, cuerpo)]


@dataclass
class While(Node):
    cond: str
    body: list


@dataclass
class Py(Node):
    code: str
    block: bool = False


@dataclass
class Define(Node):
    kind: str            # define | default
    name: str
    value: str


@dataclass
class ImageDef(Node):
    name: tuple
    value: str | None
    atl: list | None = None


@dataclass
class Transform(Node):
    name: str
    atl: list


@dataclass
class Camera(Node):
    atl: list


@dataclass
class LayeredImage(Node):
    name: str
    body: list


@dataclass
class Raw:
    """Linea logica con su sangria y sus hijos (bloque)."""
    indent: int
    text: str
    line: int
    children: list = field(default_factory=list)


SAY_RE = re.compile(
    r"""^(?:(extend)\s*(?=["'])|((?:[A-Za-z_]\w*)(?:\s+[\w@.]+)*|"[^"]*")\s+)?("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')(.*)$"""
)
KEYWORD_RE = re.compile(r"\s+(as|at|behind|onlayer|zorder|with)\s+")
DIALOGUE_TAIL_RE = re.compile(r"\s+(id\s+(\w+)|with\s+(.+?))(?=\s+id\s+|\s+with\s+|$)")


def eval_number(text):
    """Evalua una expresion numerica simple ('1.5', '(0.1)', '.5+.25') sin usar eval."""
    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            ops = {ast.Add: a + b if isinstance(node.op, ast.Add) else 0, ast.Sub: a - b if isinstance(node.op, ast.Sub) else 0,
                   ast.Mult: a * b if isinstance(node.op, ast.Mult) else 0,
                   ast.Div: a / b if isinstance(node.op, ast.Div) and b else 0}
            if type(node.op) in ops:
                return ops[type(node.op)]
        raise ValueError(f"expresion numerica no soportada: {text}")
    return walk(ast.parse(text.strip(), mode="eval").body)


ESCAPES = {"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\"}


def unquote(token):
    """Quita las comillas y resuelve escapes al estilo de Ren'Py (\\n, \\\", y escapes desconocidos sin la barra)."""
    body = token[1:-1]
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            out.append(ESCAPES.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def logical_lines(text, file):
    """Une lineas con parentesis abiertos y devuelve (sangria, texto, numero de linea)."""
    out = []
    pending = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw.replace("\t", "    "))
        if not line.strip():
            continue
        if pending:
            pending[1] += " " + line.strip()
            pending[3] += bracket_balance(line)
            if pending[3] <= 0:
                out.append((pending[0], pending[1], pending[2]))
                pending = None
            continue
        balance = bracket_balance(line)
        indent = len(line) - len(line.lstrip())
        if balance > 0:
            pending = [indent, line.strip(), lineno, balance]
        else:
            out.append((indent, line.strip(), lineno))
    if pending:
        raise ParseError(f"{file}:{pending[2]}: parentesis sin cerrar")
    return out


def build_tree(lines):
    root = Raw(-1, "", 0)
    stack = [root]
    for indent, text, lineno in lines:
        while stack[-1].indent >= indent:
            stack.pop()
        node = Raw(indent, text, lineno)
        stack[-1].children.append(node)
        stack.append(node)
    return root.children


def raw_to_atl(raw_children):
    return [(r.text, raw_to_atl(r.children)) for r in raw_children]


def split_words_until_keyword(text):
    """Separa 'a b c at x with y' en nombre y claves (as/at/behind/onlayer/zorder/with)."""
    parts = KEYWORD_RE.split(" " + text.strip() + " ")
    name = parts[0].split()
    keys = {}
    for i in range(1, len(parts) - 1, 2):
        keys[parts[i]] = parts[i + 1].strip()
    return name, keys


def parse_with_trailing(rest):
    """Extrae ' with X' del final (X puede llevar parentesis y espacios)."""
    m = re.search(r"\s+with\s+(.+)$", rest)
    if not m:
        return rest, None
    return rest[:m.start()], m.group(1).strip()


class Parser:
    def __init__(self, file):
        self.file = file

    def err(self, raw, msg):
        raise ParseError(f"{self.file}:{raw.line}: {msg}: {raw.text[:80]}")

    def block(self, raws):
        out = []
        i = 0
        while i < len(raws):
            raw = raws[i]
            first = raw.text.split(None, 1)[0].rstrip(":")
            if first == "if":
                node, i = self.parse_if(raws, i)
                out.append(node)
                continue
            if first in ("elif", "else"):
                self.err(raw, "elif/else sin if")
            node = self.statement(raw)
            if node is not None:
                out.append(node)
            i += 1
        return out

    def parse_if(self, raws, i):
        raw = raws[i]
        branches = []
        cond = raw.text[2:].rstrip().rstrip(":").strip()
        branches.append((cond, self.block(raw.children)))
        i += 1
        while i < len(raws):
            nxt = raws[i]
            if nxt.text.startswith("elif ") or nxt.text.startswith("elif("):
                branches.append((nxt.text[4:].rstrip().rstrip(":").strip(), self.block(nxt.children)))
            elif nxt.text.rstrip(":").strip() == "else":
                branches.append((None, self.block(nxt.children)))
            else:
                break
            i += 1
        return If(self.file, raw.line, branches), i

    def statement(self, raw):
        text = raw.text
        f, ln = self.file, raw.line
        m = re.match(r"[A-Za-z_]\w*|\$", text)
        word = m.group(0) if m else ""

        if word == "label":
            lm = re.match(r"label\s+([\w.]+)\s*:\s*$", text)
            if not lm:
                self.err(raw, "label invalido")
            return Label(f, ln, lm.group(1), self.block(raw.children))
        if word == "jump":
            rest = text[4:].strip()
            if rest.startswith("expression"):
                return Jump(f, ln, rest[10:].strip(), True)
            return Jump(f, ln, rest)
        if word == "call":
            rest = text[4:].strip()
            if rest.startswith("screen"):
                body, with_ = parse_with_trailing(rest[6:].strip())
                return CallScreen(f, ln, body.split("(")[0].strip(), with_)
            if rest.startswith("expression"):
                return Call(f, ln, re.sub(r"\s+from\s+\w+$", "", rest[10:].strip()), True)
            return Call(f, ln, re.sub(r"\s+from\s+\w+$", "", rest))
        if word == "return":
            return Return(f, ln)
        if word == "pass":
            return Pass(f, ln)
        if word == "menu":
            return self.parse_menu(raw)
        if word == "while":
            return While(f, ln, text[5:].rstrip().rstrip(":").strip(), self.block(raw.children))
        if word == "$":
            return Py(f, ln, text[1:].strip())
        if word == "python":
            code = "\n".join(self.dump(raw.children))
            return Py(f, ln, code, True)
        if word == "pause":
            rest = text[5:].strip()
            return Pause(f, ln, eval_number(rest) if rest else None)
        if word == "window":
            body, with_ = parse_with_trailing(text[6:].strip())
            parts = body.split()
            return Window(f, ln, parts[0] if parts else "auto", with_ if with_ else (parts[1] if len(parts) > 1 else None))
        if word == "with":
            return With(f, ln, text[4:].strip())
        if word in ("play", "queue"):
            return self.parse_play(raw, word)
        if word == "stop":
            pm = re.match(r"stop\s+(\w+)(?:\s+fadeout\s+([\d.]+))?", text)
            if not pm:
                self.err(raw, "stop invalido")
            return Stop(f, ln, pm.group(1), float(pm.group(2)) if pm.group(2) else None)
        if word in ("scene", "show", "hide"):
            return self.parse_image_stmt(raw, word)
        if word in ("define", "default"):
            dm = re.match(r"(define|default)\s+(?:-?\d+\s+)?([\w.]+)\s*=\s*(.*)$", text)
            if not dm:
                self.err(raw, "define/default invalido")
            return Define(f, ln, dm.group(1), dm.group(2), dm.group(3))
        if word == "image":
            return self.parse_image_def(raw)
        if word == "transform":
            tm = re.match(r"transform\s+(\w+)\s*(?:\(.*\))?\s*:\s*$", text)
            if not tm:
                self.err(raw, "transform invalido")
            return Transform(f, ln, tm.group(1), raw_to_atl(raw.children))
        if word == "init":
            if re.match(r"init(\s+-?\d+)?\s+python(\s+\w+)*\s*:\s*$", text):
                return Py(f, ln, "\n".join(self.dump(raw.children)), True)
            if re.match(r"init(\s+-?\d+)?\s*:\s*$", text):
                return Py(f, ln, "", True) if not raw.children else self.block(raw.children)
            self.err(raw, "init no soportado")
        if word == "layeredimage":
            lm = re.match(r"layeredimage\s+([\w ]+?)\s*:\s*$", text)
            if not lm:
                self.err(raw, "layeredimage invalido")
            return LayeredImage(f, ln, lm.group(1), raw_to_atl(raw.children))
        if word in ("style", "screen", "translate", "on", "use"):
            return None
        if word == "camera":
            return Camera(f, ln, raw_to_atl(raw.children))
        if word == "extend":
            return self.parse_say(raw, extend=True)
        return self.parse_say(raw)

    def dump(self, raws, depth=0):
        lines = []
        for r in raws:
            lines.append("    " * depth + r.text)
            lines.extend(self.dump(r.children, depth + 1))
        return lines

    def parse_play(self, raw, verb):
        text = raw.text
        m = re.match(r"(play|queue)\s+(\w+)\s+(.*)$", text)
        if not m:
            self.err(raw, "play/queue invalido")
        channel, rest = m.group(2), m.group(3)
        sources = [unquote(s.group(0)) for s in re.finditer(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', rest)]
        fadein = re.search(r"\bfadein\s+([\d.]+)", rest)
        fadeout = re.search(r"\bfadeout\s+([\d.]+)", rest)
        loop = True if re.search(r"\bloop\b", rest) else (False if re.search(r"\bnoloop\b", rest) else None)
        return Play(self.file, raw.line, verb, channel, sources,
                    float(fadein.group(1)) if fadein else None, float(fadeout.group(1)) if fadeout else None, loop)

    def parse_image_stmt(self, raw, word):
        text = raw.text
        has_atl = text.endswith(":")
        body = text[:-1].rstrip() if has_atl else text
        body = body[len(word):].strip()
        name_words, keys = split_words_until_keyword(body)
        if not name_words:
            self.err(raw, "instruccion de imagen sin nombre")
        if name_words[0] == "screen":
            return None
        with_ = keys.get("with")
        at = [a.strip() for a in keys["at"].split(",")] if "at" in keys else []
        atl = raw_to_atl(raw.children) if has_atl else None
        if word == "scene":
            return Scene(self.file, raw.line, tuple(name_words), at, with_, atl)
        if word == "hide":
            return Hide(self.file, raw.line, keys.get("as", name_words[0]), with_)
        behind = [b.strip() for b in keys["behind"].split(",")] if "behind" in keys else []
        tag = keys.get("as", name_words[0])
        z = int(keys["zorder"]) if "zorder" in keys else None
        return Show(self.file, raw.line, tuple(name_words), tag, at, behind, with_, atl, z)

    def parse_image_def(self, raw):
        text = raw.text
        m = re.match(r"image\s+([^=:]+?)\s*(=|:)\s*(.*)$", text)
        if not m:
            self.err(raw, "image invalido")
        name = tuple(m.group(1).split())
        if m.group(2) == "=":
            return ImageDef(self.file, raw.line, name, m.group(3))
        return ImageDef(self.file, raw.line, name, None, raw_to_atl(raw.children))

    def parse_menu(self, raw):
        caption = None
        choices = []
        for child in raw.children:
            t = child.text
            cm = re.match(r"""^("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')(?:\s+if\s+(.+?))?\s*:$""", t)
            if cm:
                choices.append((unquote(cm.group(1)), cm.group(2), self.block(child.children)))
            elif STRING_RE.fullmatch(t):
                caption = unquote(t)
            elif t.startswith("set "):
                continue
            else:
                self.err(child, "linea de menu invalida")
        return Menu(self.file, raw.line, caption, choices)

    def parse_say(self, raw, extend=False):
        text = raw.text
        m = SAY_RE.match(text)
        if not m:
            self.err(raw, "instruccion desconocida")
        who = None
        if m.group(2):
            who = m.group(2).split()[0].strip('"') if not m.group(2).startswith('"') else m.group(2).strip('"')
        body = unquote(m.group(3))
        tail = m.group(4)
        text_id = None
        with_ = None
        for tm in re.finditer(r"\bid\s+(\w+)|\bwith\s+(.+?)(?=\s+id\s+|$)", tail):
            if tm.group(1):
                text_id = tm.group(1)
            else:
                with_ = tm.group(2).strip()
        return Say(self.file, raw.line, who, body, text_id, bool(m.group(1)) or extend, with_)


def parse_file(path, rel=None):
    path = Path(path)
    rel = rel or path.name
    text = path.read_text(encoding="utf-8-sig")
    tree = build_tree(logical_lines(text, rel))
    return Parser(rel).block(tree)


def flatten(nodes):
    """Recorre todos los nodos, incluidos los de bloques anidados."""
    for n in nodes:
        yield n
        if isinstance(n, Label) or isinstance(n, While):
            yield from flatten(n.body)
        elif isinstance(n, If):
            for _, body in n.branches:
                yield from flatten(body)
        elif isinstance(n, Menu):
            for _, _, body in n.choices:
                yield from flatten(body)


def main():
    game = Path(__file__).resolve().parents[2] / "original" / "game" / "script"
    counts = {}
    errors = []
    for path in sorted(game.glob("*.rpy")):
        try:
            nodes = parse_file(path)
        except ParseError as exc:
            errors.append(str(exc))
            continue
        for n in flatten(nodes):
            counts[type(n).__name__] = counts.get(type(n).__name__, 0) + 1
    print(counts)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
