"""Traduccion al espanol: une cada dialogo y cadena de la historia con su texto en tl/es (Fase 3, etapa 3)."""
import re
from pathlib import Path

from tools.audit.inventario import strip_comment
from tools.script_compiler.rpy_parser import SAY_RE, unquote

GAME = Path(__file__).resolve().parents[2] / "original" / "game"
STRING_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
BLOCK_RE = re.compile(r"^translate\s+(\w+)\s+(\w+)\s*:\s*$")
ID_RE = re.compile(r"^(.*)_([0-9a-f]{8})(?:_(\d+))?$")


def normalize(text):
    """Clave de comparacion: sin espacios y con los escapes de Ren'Py ([[, {{, %%) reducidos."""
    text = text.replace("[[", "[").replace("{{", "{").replace("%%", "%")
    return re.sub(r"\s+", "", text)


class Translations:
    def __init__(self, lang="es"):
        self.lang = lang
        self.by_id = {}        # id -> {"orig": [str], "text": [str], "file": nombre}
        self.strings = {}      # texto original -> traduccion
        self._load()

    def _load(self):
        base = GAME / "tl" / self.lang
        for path in sorted(base.rglob("*.rpy")):
            self._load_file(path)

    def _load_file(self, path):
        current = None
        in_strings = False
        old = None
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if raw and not raw[0].isspace():
                m = BLOCK_RE.match(raw)
                current, in_strings, old = None, False, None
                if m and m.group(1) == self.lang:
                    if m.group(2) == "strings":
                        in_strings = True
                    else:
                        current = {"orig": [], "text": [], "file": path.name}
                        self.by_id[m.group(2)] = current
                continue
            s = raw.strip()
            if not s:
                continue
            if in_strings:
                if s.startswith("old "):
                    old = unquote(STRING_TOKEN.search(s).group(0))
                elif s.startswith("new ") and old is not None:
                    self.strings[old] = unquote(STRING_TOKEN.search(s).group(0))
                    old = None
            elif current is not None:
                if s.startswith("#"):
                    m = SAY_RE.match(s[1:].strip())
                    if m:
                        current["orig"].append(unquote(m.group(3)))
                else:
                    m = SAY_RE.match(strip_comment(s))
                    if m:
                        current["text"].append(unquote(m.group(3)))

    def build_index(self):
        """Indice (etiqueta, texto original) -> ids en el orden de tl, para dialogos sin `id` explicito."""
        self.index = {}
        self.by_text = {}
        self.all_by_text = {}
        for tid, entry in self.by_id.items():
            m = ID_RE.match(tid)
            if m and entry["orig"]:
                norm = normalize(entry["orig"][-1])
                self.all_by_text.setdefault(norm, tid)
                self.index.setdefault((m.group(1), norm), []).append(tid)
                self.by_text.setdefault(norm, []).append(tid)

    def lookup(self, label, text):
        """Siguiente id para (etiqueta, texto) en el orden de tl; cae a solo texto si la etiqueta no coincide."""
        if not hasattr(self, "index"):
            self.build_index()
        norm = normalize(text)
        pool = self.index.get(((label or "").replace(".", "_"), norm))
        if pool:
            tid = pool.pop(0)
            self.by_text[norm].remove(tid)
            return tid
        pool = self.by_text.get(norm)
        if pool:
            tid = pool.pop(0)
            m = ID_RE.match(tid)
            if m:
                self.index[(m.group(1), norm)].remove(tid)
            return tid
        return self.all_by_text.get(norm)

    def dialogue(self, text_id):
        """Texto en espanol de un dialogo por su id, o None si no existe."""
        entry = self.by_id.get(text_id)
        if not entry or not entry["text"]:
            return None
        return "".join(entry["text"]) if len(entry["text"]) > 1 else entry["text"][0]

    def string(self, original):
        return self.strings.get(original)
