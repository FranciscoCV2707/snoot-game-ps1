"""Carga de todo el juego original: capitulos, personajes, posiciones, imagenes, audio, traducciones."""
import ast
import json
import re
from pathlib import Path

from tools.script_compiler.images import ImageTable, call_name, literal
from tools.script_compiler.rpy_parser import Define, Label, Transform, flatten, parse_file
from tools.script_compiler.translations import Translations

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "original" / "game"

# Posiciones predefinidas de Ren'Py que el juego usa sin definirlas
BUILTIN_POSITIONS = {
    "left": (0.0, 1.0), "right": (1.0, 1.0), "center": (0.5, 1.0), "truecenter": (0.5, 0.5),
    "topleft": (0.0, 0.0), "top": (0.5, 0.0), "topright": (1.0, 0.0),
}
POS_RE = re.compile(r"\b(xalign|yalign)\s+(-?[\d.]+)")


def chapter_sort_key(path):
    m = re.match(r"(x?)(\d+)(?:\.5)?([A-Z]?)", path.name)
    if not m:
        return (2, 99, path.name)
    return (1 if m.group(1) else 0, int(m.group(2)), path.name)


class Chapter:
    def __init__(self, index, path, nodes):
        self.index = index
        self.path = path
        self.name = path.name
        self.nodes = nodes
        self.labels = [n.name for n in flatten(nodes) if isinstance(n, Label)]


class Project:
    def __init__(self):
        self.tr = Translations()
        self.images = ImageTable()
        self.chapters = []
        for i, path in enumerate(sorted((GAME / "script").glob("*.rpy"), key=chapter_sort_key)):
            self.chapters.append(Chapter(i, path, parse_file(path, f"script/{path.name}")))
        self.label_chapter = {}
        for ch in self.chapters:
            for label in ch.labels:
                self.label_chapter[label] = ch.index
        self.speakers = {None: 0}
        self.speaker_info = [{"var": "narrator", "name": "", "color": "#ffffff"}]
        self.positions = {}
        self.position_info = []
        self.transforms = {}
        self._load_misc()
        self.audio_files = {p.relative_to(GAME).as_posix().lower(): p.relative_to(GAME).as_posix()
                            for p in (GAME / "audio").rglob("*") if p.is_file()}
        chapter_text = (GAME / "src" / "chapter_variables.rpy").read_text(encoding="utf-8-sig")
        from tools.audit.inventario import extract_literal
        self.base_chapters = list(extract_literal(chapter_text, "BASE_CHAPTERS"))
        self.ending_routes = extract_literal(chapter_text, "ENDING_ROUTES")
        extra_text = (GAME / "src" / "extra_chapters_menu.rpy").read_text(encoding="utf-8-sig")
        self.extra_chapters = re.findall(r'_\("([^"]+)"\),\s*"(chapter_\w+)"', extra_text)
        self.defaults = self._load_defaults()
        gallery = json.loads((GAME / "src" / "gallery_dataset.json").read_text(encoding="utf-8-sig"))
        self.gallery_images = {item["name"]: item["image"] for tab in gallery["tabs"] for item in tab.get("items", [])}

    def _load_misc(self):
        nodes = parse_file(GAME / "src" / "misc_definitions.rpy", "src/misc_definitions.rpy")
        for node in flatten(nodes):
            if isinstance(node, Define) and re.match(r"(?:Dynamic)?Character\s*\(", node.value):
                if node.name in ("base",):
                    continue
                tree = ast.parse(node.value, mode="eval").body
                name = literal(tree.args[0]) if tree.args and isinstance(tree.args[0], ast.Constant) else None
                if name is None and tree.args and isinstance(tree.args[0], ast.Call):
                    name = literal(tree.args[0].args[0])
                color = next((literal(k.value) for k in tree.keywords if k.arg == "color"), "#ffffff")
                es = self.tr.string(name) if name else None
                self.speakers[node.name] = len(self.speaker_info)
                self.speaker_info.append({"var": node.name, "name": es or name or "", "color": color})
            elif isinstance(node, Transform):
                self.transforms[node.name] = node.atl
        for name, (xa, ya) in BUILTIN_POSITIONS.items():
            self._add_position(name, xa, ya)
        for name, atl in self.transforms.items():
            props = {}
            plain = all(not re.match(r"(block|parallel|choice|repeat|linear|ease|pause|rotate|zoom)", t) for t, _ in atl)
            for text, _ in atl:
                for key, value in POS_RE.findall(text):
                    props[key] = float(value)
            if plain and "xalign" in props:
                self._add_position(name, props["xalign"], props.get("yalign", 0.0))

    def _add_position(self, name, xalign, yalign):
        self.positions[name] = len(self.position_info)
        self.position_info.append({"name": name, "xalign": xalign, "yalign": yalign})

    def _load_defaults(self):
        out = {}
        text = (GAME / "src" / "chapter_variables.rpy").read_text(encoding="utf-8-sig")
        for node in flatten(parse_file(GAME / "src" / "chapter_variables.rpy", "src/chapter_variables.rpy")):
            if isinstance(node, Define) and node.kind == "default":
                out[node.name] = node.value
        extra = {}
        for ch in self.chapters:
            for node in flatten(ch.nodes):
                if isinstance(node, Define) and node.kind == "default":
                    extra[node.name] = node.value
        out.update(extra)
        return out

    def audio_path(self, name):
        return self.audio_files.get(re.sub(r"/+", "/", name).lower())

    def add_speaker(self, name, translated=None):
        self.speakers[name] = len(self.speaker_info)
        self.speaker_info.append({"var": name, "name": translated or self.tr.string(name) or name, "color": "#ffffff"})

    def lowering_order(self):
        """Capitulos en el orden de la historia (base, rutas, extras), con el punto de reinicio del estado visual."""
        order, seen = [], set()
        chains = [("base", [self.label_chapter[c] for c in self.base_chapters])]
        for num in sorted(self.ending_routes):
            chains.append((f"route{num}", [self.label_chapter[c] for c in self.ending_routes[num]]))
        for _, label in self.extra_chapters:
            chains.append((label, [self.label_chapter[label]]))
        for name, chain in chains:
            for idx in chain:
                if idx not in seen:
                    seen.add(idx)
                    order.append((name, self.chapters[idx]))
        for ch in self.chapters:
            if ch.index not in seen:
                order.append(("other", ch))
        return order


def main():
    project = Project()
    print("capitulos:", len(project.chapters), "hablantes:", len(project.speaker_info),
          "posiciones:", len(project.position_info), "etiquetas:", len(project.label_chapter))
    print("posiciones:", [p["name"] for p in project.position_info])
    print("defaults:", project.defaults)
    print("transforms:", list(project.transforms))


if __name__ == "__main__":
    main()
