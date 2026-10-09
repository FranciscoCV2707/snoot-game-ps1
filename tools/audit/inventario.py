"""Auditoria de Snoot Game (Fase 1).

Recorre original/game y genera:
  build/audit/inventario.json, python_blocks.txt, grafo_historia.svg, grafo_labels.svg
  docs/auditoria.md (mas docs/auditoria_manual.md si existe)

No modifica original/.
"""
import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "original" / "game"
OUT = ROOT / "build" / "audit"
DOC = ROOT / "docs" / "auditoria.md"
DOC_MANUAL = ROOT / "docs" / "auditoria_manual.md"
TL_LANG = "es"

KEYWORDS = {
    "label", "jump", "call", "return", "menu", "if", "elif", "else", "while", "for", "pass",
    "scene", "show", "hide", "with", "play", "stop", "queue", "pause", "window", "nvl",
    "voice", "define", "default", "image", "transform", "screen", "init", "python", "style",
    "translate", "camera", "on", "use", "extend", "layeredimage", "testcase", "rpy",
    "key", "break", "continue", "try", "except", "finally",
}
DIALOGUE_RE = re.compile(
    r"""^(?:(?:[A-Za-z_]\w*(?:\s+[\w@.]+)*|"[^"]*")\s+)?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')(?:\s*(?:id\s+\w+|with\s+.*))*$"""
)
CHOICE_RE = re.compile(r"""^(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')(?:\s+if\s+.+)?:$""")
STRING_RE = re.compile(r""""((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'""")
TAG_RE = re.compile(r"\{(/?)(\w+)(?:=[^}]*)?\}")
INTERP_RE = re.compile(r"\[(\w+)")
PYTHON_BLOCK_RE = re.compile(r"^(?:init(?:\s+-?\d+)?\s+)?python(?:\s+\w+)*\s*:$")
PERSISTENT_RE = re.compile(r"persistent\.(\w+)")
RENPY_API_RE = re.compile(r"renpy\.([\w.]+)")

# (patron sobre el texto del bloque, categoria, motivo); la primera que coincide gana
PYTHON_RULES = [
    (r"webbrowser|steam|os\.|sys\.|subprocess|mods?\b|preferences\.language|language", "descartable",
     "Utilidad de PC (navegador, mods, idioma, archivos)"),
    (r"register_channel|config\.|gui\.|style\.|renpy\.music\.set|Preference", "descartable",
     "Configuracion de Ren'Py que el motor propio reemplaza"),
    (r"persistent\.|seen_image|mark_image_seen|endings|bonus_chapters|lewd", "a mano",
     "Logica de progreso persistente; se reescribe para la memory card"),
    (r"anonscore|fangscore|wingStory|active_queue|current_chapter|ENDING_ROUTES", "a mano",
     "Logica de flujo del juego; se reescribe en el formato del motor"),
    (r"def\s+\w+|class\s+\w+", "a mano", "Funcion o clase propia; hay que revisarla"),
]
SIMPLE_ASSIGN_RE = re.compile(r"^\$\s*[\w.\[\]'\"]+\s*([+\-*/]|//)?=\s*[^=]")


def strip_comment(line):
    quote = None
    i = 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            return line[:i].rstrip()
        i += 1
    return line.rstrip()


def bracket_balance(line):
    code = STRING_RE.sub('""', line)
    return sum(code.count(c) for c in "([{") - sum(code.count(c) for c in ")]}")


def first_string(line):
    m = STRING_RE.search(line)
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else m.group(2)


def guess_type(value):
    value = value.strip()
    if value in ("True", "False"):
        return "bool"
    if re.fullmatch(r"-?\d+", value):
        return "int"
    if re.fullmatch(r"-?\d*\.\d+", value):
        return "float"
    if value == "None":
        return "None"
    if value[:1] in "\"'" or value.startswith("_("):
        return "str"
    if value[:1] in "[(":
        return "list/tuple"
    if value[:1] == "{":
        return "dict"
    return "other"


class Audit:
    def __init__(self):
        self.statements = Counter()
        self.unknown = Counter()
        self.unknown_examples = {}
        self.play_channels = Counter()
        self.transitions = Counter()
        self.text_tags = Counter()
        self.interpolations = Counter()
        self.labels = {}
        self.edges = []
        self.dynamic = []
        self.characters = {}
        self.variables = []
        self.persistent = Counter()
        self.lewd_refs = []
        self.renpy_api = Counter()
        self.python_blocks = []
        self.screens = []
        self.images_defined = 0
        self.dialogue_per_file = Counter()
        self.choices_per_file = Counter()
        self.menus = 0
        self.assigned = Counter()
        self.speakers = Counter()
        self.lines_per_file = {}

    def note_text(self, text):
        for closing, name in TAG_RE.findall(text):
            if not closing:
                self.text_tags[name] += 1
        for name in INTERP_RE.findall(text):
            self.interpolations[name] += 1


def parse_text(audit, text, rel, story):
    ctx = None
    label = None
    depth = 0
    menus = []
    lines = text.splitlines()
    audit.lines_per_file[rel] = len(lines)

    def close_ctx():
        nonlocal ctx
        if ctx and ctx["kind"] == "python":
            audit.python_blocks.append({
                "file": rel, "line": ctx["start"], "kind": ctx["header"], "text": "\n".join(ctx["lines"]),
            })
        if ctx and ctx["kind"] == "screen":
            audit.screens.append({"name": ctx["name"], "file": rel, "line": ctx["start"], "lines": ctx["count"]})
        ctx = None

    for lineno, raw in enumerate(lines, 1):
        line = strip_comment(raw.replace("\t", "    "))
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()

        if ctx and indent <= ctx["indent"]:
            close_ctx()
        for name in PERSISTENT_RE.findall(s):
            audit.persistent[name] += 1
            if name == "lewd":
                audit.lewd_refs.append(f"{rel}:{lineno}: {s[:100]}")
        for name in RENPY_API_RE.findall(s):
            audit.renpy_api[name] += 1

        if ctx:
            if ctx["kind"] == "python":
                ctx["lines"].append(line[ctx["indent"] + 1:] if len(line) > ctx["indent"] else s)
            elif ctx["kind"] == "screen":
                ctx["count"] += 1
            continue

        if depth > 0:
            depth += bracket_balance(s)
            continue
        depth = max(bracket_balance(s), 0)

        while menus and indent <= menus[-1]["indent"]:
            menus.pop()
        if menus and menus[-1]["child"] is None:
            menus[-1]["child"] = indent
        if menus and indent == menus[-1]["child"] and CHOICE_RE.match(s):
            audit.statements["menu choice"] += 1
            audit.choices_per_file[rel] += 1
            audit.note_text(first_string(s) or "")
            continue

        if PYTHON_BLOCK_RE.match(s):
            audit.statements["python block"] += 1
            ctx = {"kind": "python", "indent": indent, "start": lineno, "header": s, "lines": []}
            continue
        if s.startswith("$"):
            audit.statements["$"] += 1
            am = re.match(r"\$\s*([\w.]+)\s*(?:[+\-*/|&]|//)?=[^=]", s)
            if am:
                audit.assigned[am.group(1)] += 1
            audit.python_blocks.append({"file": rel, "line": lineno, "kind": "$", "text": s})
            continue

        m = re.match(r"[A-Za-z_]\w*", s)
        word = m.group(0) if m else ""
        is_dialogue = word not in KEYWORDS and DIALOGUE_RE.match(s)

        if word == "label":
            lm = re.match(r"label\s+([\w.]+)", s)
            if lm:
                label = lm.group(1)
                audit.labels[label] = {"file": rel, "line": lineno}
            audit.statements["label"] += 1
        elif word in ("jump", "call"):
            audit.statements[word] += 1
            rest = s[len(word):].strip()
            if rest.startswith("screen"):
                audit.statements["call screen"] += 1
            elif rest.startswith("expression"):
                audit.dynamic.append({"kind": word, "from": label, "file": rel, "line": lineno, "expr": rest[10:].strip()})
            else:
                dm = re.match(r"([\w.]+)", rest)
                if dm:
                    audit.edges.append((label, word, dm.group(1), rel, lineno))
        elif word == "menu":
            audit.statements["menu"] += 1
            audit.menus += 1
            menus.append({"indent": indent, "child": None})
        elif word == "screen":
            audit.statements["screen"] += 1
            sm = re.match(r"screen\s+(\w+)", s)
            name = sm.group(1) if sm else "?"
            if s.endswith(":"):
                ctx = {"kind": "screen", "indent": indent, "start": lineno, "name": name, "count": 0}
            else:
                audit.screens.append({"name": name, "file": rel, "line": lineno, "lines": 1})
        elif word in ("transform", "style", "layeredimage") or (word == "image" and s.endswith(":")):
            audit.statements[word] += 1
            if word == "image":
                audit.images_defined += 1
            if s.endswith(":"):
                ctx = {"kind": "other", "indent": indent, "start": lineno}
        elif word == "image":
            audit.statements["image"] += 1
            audit.images_defined += 1
        elif word == "init":
            audit.statements["init"] += 1
        elif word in ("define", "default"):
            audit.statements[word] += 1
            vm = re.match(r"(?:define|default)\s+(?:-?\d+\s+)?([\w.]+)\s*=\s*(.*)", s)
            if vm:
                name, value = vm.groups()
                if re.match(r"(?:Dynamic)?Character\s*\(", value):
                    audit.characters[name] = value[:150]
                elif not re.match(r"(config|gui|build|preferences|style|persistent)\.", name) or word == "default":
                    audit.variables.append({
                        "kind": word, "name": name, "type": guess_type(value), "value": value[:80], "file": rel,
                    })
        elif word in ("play", "stop", "queue"):
            audit.statements[word] += 1
            cm = re.match(r"\w+\s+(\w+)", s)
            audit.play_channels[f"{word} {cm.group(1) if cm else '?'}"] += 1
            audit.note_text("")
        elif word == "with":
            audit.statements["with"] += 1
            audit.transitions[s[4:].strip()[:40]] += 1
        elif word in KEYWORDS:
            audit.statements[word] += 1
            if word in ("scene", "show") and " with " in s:
                audit.transitions[s.split(" with ", 1)[1].strip()[:40]] += 1
            if word in ("scene", "show", "hide", "camera", "with", "on") and s.endswith(":"):
                ctx = {"kind": "other", "indent": indent, "start": lineno}
            if word == "extend":
                audit.dialogue_per_file[rel] += 1
                audit.note_text(first_string(s) or "")
        elif is_dialogue:
            audit.statements["dialogue"] += 1
            audit.speakers[word if word else "(narrador)"] += 1
            audit.dialogue_per_file[rel] += 1
            audit.note_text(first_string(s) or "")
        else:
            audit.unknown[word or s[:20]] += 1
            audit.unknown_examples.setdefault(word or s[:20], f"{rel}:{lineno}: {s[:90]}")
    close_ctx()


FILE_RULES = [
    (r"^src/(mod_menu|translation|rounded_corners|fontranges)\.rpy$", "descartable", "Mods, idioma, esquinas de UI o fuentes de PC"),
    (r"^(gui|options|script)\.rpy$", "descartable", "Configuracion de Ren'Py, canales y GUI de PC (revisar persistent.* que contiene)"),
    (r"^screens\.rpy$", "descartable", "Pantallas de PC"),
    (r"^src/image_definitions\.rpy$", "a mano", "Definicion de imagenes; la cubre el pipeline de imagenes (Fase 4)"),
    (r"^src/credits\.rpy$", "revisar", "Creditos; decidir si van al final del juego"),
]
CODE_RULES = [
    (r"display_menu", "a mano", "Menu en Python con orden aleatorio y saltos dinamicos"),
    (r"showCG", "a mano", "Elige al azar una de 9 imagenes de texto"),
    (r"set_volume|mark_image_seen|bonus_chapters\s*\|=", "traducible automaticamente", "Instruccion simple del motor"),
    (r"ending_image|setup_ending|toggle_debug", "a mano", "Logica de finales o depuracion"),
    (r"webbrowser|MainMenu|set_mixer|renpy\.input", "descartable", "Funcion de PC"),
]


def classify_python(block):
    text = block["text"]
    for pattern, category, reason in FILE_RULES:
        if re.search(pattern, block["file"]) and not (block["kind"] == "$" and block["file"].startswith("script")):
            return category, reason
    for pattern, category, reason in CODE_RULES:
        if re.search(pattern, text):
            return category, reason
    if block["kind"] == "$":
        if re.search(r"renpy\.(quit|call|jump)", text):
            return "traducible automaticamente", "Salto o fin del juego"
        if SIMPLE_ASSIGN_RE.match(text) and "renpy." not in text:
            return "traducible automaticamente", "Asignacion simple de variable"
        if re.search(r"renpy\.(music|sound|play|pause|hide_screen|show_screen|with_statement|restart|mark_image_seen)", text):
            return "revisar", "Llamada a la API de Ren'Py; ver cada caso"
        return "revisar", "Expresion Python; ver cada caso"
    for pattern, category, reason in PYTHON_RULES:
        if re.search(pattern, text):
            return category, reason
    return "revisar", "Bloque sin clasificar"


def extract_literal(text, name):
    m = re.search(rf"define\s+{name}\s*=\s*", text)
    if not m:
        return None
    start = m.end()
    opening = text[start]
    closing = {"(": ")", "{": "}", "[": "]"}[opening]
    depth = 0
    for i in range(start, len(text)):
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                body = "\n".join(strip_comment(ln) for ln in text[start:i + 1].splitlines())
                return ast.literal_eval(body)
    return None


def parse_translation(lang):
    base = GAME / "tl" / lang
    result = {"files": {}, "strings_pairs": 0, "strings_empty": 0, "chars": Counter(), "text_bytes": 0, "images": 0}
    block_re = re.compile(rf"^translate\s+{lang}\s+(?!strings:)(\w+):\s*$")
    all_text = []
    for path in sorted(base.rglob("*.rpy")):
        rel = path.relative_to(base).as_posix()
        entry = {"blocks": 0, "empty": 0, "same_as_original": 0, "strings": 0}
        current = None
        in_strings = False
        pending_old = None
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if re.match(rf"^translate\s+{lang}\s+strings:\s*$", raw):
                in_strings = True
                current = None
                continue
            if block_re.match(raw):
                current = {"orig": [], "new": []}
                in_strings = False
                entry["blocks"] += 1
                continue
            if raw and not raw[0].isspace():
                current = None
                in_strings = False
                continue
            s = raw.strip()
            if in_strings:
                if s.startswith("old "):
                    pending_old = first_string(s)
                elif s.startswith("new ") and pending_old is not None:
                    new = first_string(s)
                    entry["strings"] += 1
                    result["strings_pairs"] += 1
                    if not new:
                        result["strings_empty"] += 1
                    else:
                        all_text.append(new)
                    pending_old = None
                continue
            if current is not None and s:
                if s.startswith("# "):
                    text = first_string(s[2:])
                    if text is not None:
                        current["orig"].append(text)
                elif not s.startswith("#"):
                    text = first_string(s)
                    if text is not None:
                        current["new"].append(text)
                        all_text.append(text)
        result["files"][rel] = entry
    result["images"] = len([p for p in base.rglob("*") if p.suffix.lower() in (".webp", ".png", ".jpg")])
    clean = []
    for t in all_text:
        t = TAG_RE.sub("", t)
        t = re.sub(r"\[[^\]]*\]", "", t)
        clean.append(t)
        result["chars"].update(t)
    result["text_bytes"] = sum(len(t.encode("utf-8")) for t in clean)
    result.pop("_cur", None)
    return result


def translation_quality(lang):
    """Cuenta bloques cuyo texto traducido esta vacio o es igual al original."""
    base = GAME / "tl" / lang / "script"
    block_re = re.compile(rf"^translate\s+{lang}\s+(?!strings:)(\w+):\s*$")
    total = empty = same = 0
    same_examples = []
    for path in sorted(base.rglob("*.rpy")):
        orig, new, active = [], [], False

        def flush():
            nonlocal total, empty, same
            if not active:
                return
            total += 1
            if not new:
                empty += 1
            elif orig and new == orig and sum(c.isalpha() for c in "".join(new)) >= 12:
                same += 1
                if len(same_examples) < 8:
                    same_examples.append(f"{path.name}: {new[0][:70]}")

        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if block_re.match(raw):
                flush()
                orig, new, active = [], [], True
                continue
            if raw and not raw[0].isspace():
                flush()
                active = False
                continue
            s = raw.strip()
            if active and s:
                if s.startswith("# "):
                    t = first_string(s[2:])
                    if t is not None:
                        orig.append(t)
                elif not s.startswith("#"):
                    t = first_string(s)
                    if t is not None:
                        new.append(t)
        flush()
    return {"blocks": total, "empty": empty, "same_as_original": same, "same_examples": same_examples}


def inventory_images():
    try:
        from PIL import Image
    except ImportError:
        return {"error": "Pillow no instalado"}
    groups = defaultdict(lambda: {"count": 0, "bytes": 0, "sizes": Counter(), "alpha": 0, "formats": Counter()})
    unreadable = []
    for path in sorted(GAME.rglob("*")):
        if path.suffix.lower() not in (".png", ".webp", ".jpg", ".jpeg", ".gif", ".bmp"):
            continue
        rel = path.relative_to(GAME)
        if rel.parts[0] == "tl":
            key = "tl/" + rel.parts[1] + "/" + (rel.parts[2] if len(rel.parts) > 3 else "")
        elif len(rel.parts) > 2:
            key = rel.parts[0] + "/" + rel.parts[1]
        else:
            key = rel.parts[0]
        g = groups[key]
        g["count"] += 1
        g["bytes"] += path.stat().st_size
        try:
            with Image.open(path) as im:
                g["sizes"][f"{im.width}x{im.height}"] += 1
                g["formats"][im.format] += 1
                if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
                    g["alpha"] += 1
        except Exception as exc:
            unreadable.append(f"{rel}: {exc}")
    return {
        "groups": {k: {"count": v["count"], "mb": round(v["bytes"] / 1048576, 2), "alpha": v["alpha"],
                       "formats": dict(v["formats"]), "top_sizes": v["sizes"].most_common(4)}
                   for k, v in sorted(groups.items())},
        "unreadable": unreadable,
    }


def find_tool(name):
    return shutil.which(name)


def inventory_audio():
    exts = {".ogg", ".mp3", ".wav", ".flac", ".opus", ".m4a"}
    files = [p for p in sorted(GAME.rglob("*")) if p.suffix.lower() in exts and "tl" not in p.relative_to(GAME).parts[:1]]
    ffprobe = find_tool("ffprobe")
    groups = defaultdict(lambda: {"count": 0, "bytes": 0, "seconds": 0.0, "formats": Counter()})
    longest = []
    for path in files:
        rel = path.relative_to(GAME)
        key = "/".join(rel.parts[:2]) if len(rel.parts) > 2 else rel.parts[0]
        g = groups[key]
        g["count"] += 1
        g["bytes"] += path.stat().st_size
        g["formats"][path.suffix.lower()] += 1
        if ffprobe:
            r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                               capture_output=True, text=True, encoding="utf-8")
            try:
                seconds = float(r.stdout.strip())
            except ValueError:
                seconds = 0.0
            g["seconds"] += seconds
            longest.append((seconds, rel.as_posix()))
    longest.sort(reverse=True)
    return {
        "ffprobe": bool(ffprobe),
        "groups": {k: {"count": v["count"], "mb": round(v["bytes"] / 1048576, 1),
                       "minutes": round(v["seconds"] / 60, 1), "formats": dict(v["formats"])}
                   for k, v in sorted(groups.items())},
        "longest": [[round(s / 60, 2), n] for s, n in longest[:8]],
    }


def inventory_video():
    exts = {".webm", ".ogv", ".mp4", ".mkv", ".avi", ".mov"}
    return [p.relative_to(GAME).as_posix() for p in sorted(GAME.rglob("*")) if p.suffix.lower() in exts]


def story_graph(audit, chapter_text, extras):
    base = extract_literal(chapter_text, "BASE_CHAPTERS") or ()
    routes = extract_literal(chapter_text, "ENDING_ROUTES") or {}
    lines = ["digraph story {", "  rankdir=LR; node [shape=box, fontname=Helvetica];"]
    previous = None
    for ch in base:
        lines.append(f'  "{ch}";')
        if previous:
            lines.append(f'  "{previous}" -> "{ch}";')
        previous = ch
    lines.append('  decision [shape=diamond, label="get_ending(anonscore, fangscore, wingStory)"];')
    if previous:
        lines.append(f'  "{previous}" -> decision;')
    names = {1: "Shooter (cierra el juego)", 2: "Doomer", 3: "Tradwife", 4: "Golden"}
    for num, chapters in routes.items():
        prev = "decision"
        for ch in chapters:
            lines.append(f'  "{ch}";')
            lines.append(f'  "{prev}" -> "{ch}"' + (f' [label="{names.get(num, num)}"]' if prev == "decision" else "") + ";")
            prev = ch
    lines.append('  extras [shape=folder, label="Capitulos extra x1..x10\\n(segun finales vistos)"];')
    lines.append('  "chapter_14B" -> extras [style=dashed]; "chapter_14C" -> extras [style=dashed];')
    lines.append("}")
    return "\n".join(lines)


def label_graph(audit):
    lines = ["digraph labels {", "  rankdir=LR; node [shape=box, fontsize=9];"]
    seen = set()
    for src, kind, dst, _, _ in audit.edges:
        if src is None or src == dst:
            continue
        key = (src, dst, kind)
        if key in seen:
            continue
        seen.add(key)
        style = ' [style=dashed]' if kind == "call" else ""
        lines.append(f'  "{src}" -> "{dst}"{style};')
    lines.append("}")
    return "\n".join(lines)


def render_dot(dot_text, name):
    OUT.mkdir(parents=True, exist_ok=True)
    dot_path = OUT / f"{name}.dot"
    dot_path.write_text(dot_text, encoding="utf-8")
    dot = find_tool("dot") or r"C:\Program Files\Graphviz\bin\dot.exe"
    if not Path(dot).exists() and not shutil.which(dot):
        return False
    subprocess.run([dot, "-Tsvg", str(dot_path), "-o", str(OUT / f"{name}.svg")], check=True)
    return True


def read_text(path):
    return path.read_text(encoding="utf-8-sig")


def run_audit():
    audit = Audit()
    story_files = 0
    for path in sorted(GAME.rglob("*.rpy")):
        rel = path.relative_to(GAME)
        if rel.parts[0] in ("tl", "dev"):
            continue
        is_story = rel.parts[0] == "script"
        story_files += is_story
        parse_text(audit, read_text(path), rel.as_posix(), is_story)

    chapter_text = read_text(GAME / "src" / "chapter_variables.rpy")
    extras_text = read_text(GAME / "src" / "extra_chapters_menu.rpy")
    extras = re.findall(r'_\("([^"]+)"\),\s*"(chapter_\w+)"', extras_text)
    gallery = json.loads(read_text(GAME / "src" / "gallery_dataset.json"))
    gallery_summary = {t["tab_name"]: len(t.get("items", [])) for t in gallery["tabs"]}

    classified = defaultdict(list)
    for block in audit.python_blocks:
        category, reason = classify_python(block)
        block["category"], block["reason"] = category, reason
        classified[category].append(block)

    translation = parse_translation(TL_LANG)
    quality = translation_quality(TL_LANG)
    story_rels = [r for r in audit.dialogue_per_file if r.startswith("script/")]
    dialogue_total = sum(audit.dialogue_per_file[r] for r in story_rels)
    per_file = {}
    for rel in sorted(story_rels):
        name = Path(rel).name
        tl_entry = translation["files"].get(f"script/{name}")
        per_file[name] = {"dialogue": audit.dialogue_per_file[rel], "choices": audit.choices_per_file[rel],
                          "translated_blocks": tl_entry["blocks"] if tl_entry else None}
    missing_tl = [n for n, v in per_file.items() if v["translated_blocks"] is None]
    tl_blocks = sum(e["blocks"] for r, e in translation["files"].items() if r.startswith("script/"))

    renpy_version = None
    toml = ROOT / "original" / "renconstruct.toml"
    if toml.exists():
        m = re.search(r'version\s*=\s*"([\d.]+)"', toml.read_text(encoding="utf-8-sig"))
        renpy_version = m.group(1) if m else None

    licenses = [p.name for p in sorted((ROOT / "original").glob("*")) if p.is_file() and
                re.search(r"licen|affero|gpl|cc-by", p.name, re.I)]

    base_chapters = extract_literal(chapter_text, "BASE_CHAPTERS")
    routes = extract_literal(chapter_text, "ENDING_ROUTES")
    graph_ok = render_dot(story_graph(audit, chapter_text, extras), "grafo_historia")
    render_dot(label_graph(audit), "grafo_labels")

    logos = [p.relative_to(GAME).as_posix() for p in sorted(GAME.rglob("*"))
             if p.is_file() and "logo" in p.name.lower() and p.suffix.lower() in (".png", ".webp", ".jpg")
             and p.relative_to(GAME).parts[0] != "tl"]

    return {
        "renpy_version": renpy_version,
        "licenses": licenses,
        "story_files": story_files,
        "lines_per_file": audit.lines_per_file,
        "statements": dict(audit.statements.most_common()),
        "unknown": {k: {"count": v, "example": audit.unknown_examples[k]} for k, v in audit.unknown.most_common()},
        "play_channels": dict(audit.play_channels.most_common()),
        "transitions": dict(audit.transitions.most_common(40)),
        "text_tags": dict(audit.text_tags.most_common()),
        "interpolations": dict(audit.interpolations.most_common()),
        "labels": len(audit.labels),
        "chapter_labels": sorted(l for l in audit.labels if l.startswith("chapter_")),
        "dynamic_jumps": audit.dynamic,
        "menus": audit.menus,
        "dialogue_lines": dialogue_total,
        "choice_lines": sum(audit.choices_per_file[r] for r in story_rels),
        "per_file": per_file,
        "characters": audit.characters,
        "variables": audit.variables,
        "assigned_vars": dict(audit.assigned.most_common()),
        "speakers": dict(audit.speakers.most_common()),
        "persistent": dict(audit.persistent.most_common()),
        "lewd_refs": audit.lewd_refs,
        "renpy_api": dict(audit.renpy_api.most_common()),
        "python_summary": {k: len(v) for k, v in classified.items()},
        "python_blocks": audit.python_blocks,
        "screens": audit.screens,
        "images_defined": audit.images_defined,
        "base_chapters": base_chapters,
        "ending_routes": routes,
        "extra_chapters": extras,
        "gallery": gallery_summary,
        "logos": logos,
        "translation": {
            "lang": TL_LANG,
            "script_blocks": tl_blocks,
            "files_missing": missing_tl,
            "strings_pairs": translation["strings_pairs"],
            "strings_empty": translation["strings_empty"],
            "quality": quality,
            "overlay_images": translation["images"],
            "text_bytes": translation["text_bytes"],
            "distinct_chars": len(translation["chars"]),
            "non_ascii_chars": "".join(sorted(c for c in translation["chars"] if ord(c) > 127)),
            "chars_count": dict(translation["chars"].most_common()),
        },
        "images": inventory_images(),
        "audio": inventory_audio(),
        "video": inventory_video(),
        "graph_rendered": graph_ok,
    }


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def write_doc(inv):
    t = inv["translation"]
    parts = ["# Auditoria de Snoot Game", "",
             "Generado por `tools/audit/inventario.py`. No editar a mano; las notas manuales van en "
             "`docs/auditoria_manual.md` (se anexan al final).", ""]
    parts += ["## Resumen", "", table(["Dato", "Valor"], [
        ["Version de Ren'Py", inv["renpy_version"]],
        ["Licencia (archivos)", ", ".join(inv["licenses"])],
        ["Archivos de historia (script/)", inv["story_files"]],
        ["Etiquetas (label)", inv["labels"]],
        ["Lineas de dialogo (script/)", inv["dialogue_lines"]],
        ["Opciones de menu (script/)", inv["choice_lines"]],
        ["Menus de decision (todo)", inv["menus"]],
        ["Bloques de traduccion es (script/)", t["script_blocks"]],
        ["Pares old/new de es (strings)", t["strings_pairs"]],
        ["Imagenes definidas (image)", inv["images_defined"]],
        ["Videos", len(inv["video"])],
    ]), ""]
    parts += ["## Instrucciones de Ren'Py usadas", "",
              table(["Instruccion", "Veces"], list(inv["statements"].items())), ""]
    parts += ["### Instrucciones desconocidas", ""]
    if inv["unknown"]:
        parts += [table(["Token", "Veces", "Ejemplo"], [[k, v["count"], f"`{v['example']}`"] for k, v in inv["unknown"].items()]), ""]
    else:
        parts += ["Ninguna.", ""]
    parts += ["### Canales de audio y transiciones", "",
              table(["Canal", "Veces"], list(inv["play_channels"].items())), "",
              table(["Transicion", "Veces"], list(inv["transitions"].items())), ""]
    parts += ["### Etiquetas de texto e interpolaciones", "",
              table(["Etiqueta", "Veces"], list(inv["text_tags"].items())), "",
              table(["Variable [x]", "Veces"], list(inv["interpolations"].items())), ""]
    parts += [f"## Personajes ({len(inv['characters'])})", "",
              table(["Nombre", "Definicion"], [[k, f"`{v}`"] for k, v in inv["characters"].items()]), ""]
    types = Counter(v["type"] for v in inv["variables"])
    parts += [f"## Variables define/default ({len(inv['variables'])})", "",
              table(["Tipo", "Cantidad"], list(types.most_common())), "",
              "Lista completa en `inventario.json`. Variables de historia (`default`):", "",
              table(["Nombre", "Tipo", "Valor", "Archivo"],
                    [[v["name"], v["type"], f"`{v['value']}`", v["file"]] for v in inv["variables"]
                     if v["kind"] == "default"][:80]), ""]
    parts += ["Variables asignadas con `$` en la historia:", "",
              table(["Variable", "Asignaciones"], list(inv["assigned_vars"].items())[:60]), "",
              "Hablantes (dialogos por personaje):", "",
              table(["Hablante", "Lineas"], list(inv["speakers"].items())), ""]
    parts += ["## Datos persistentes", "",
              table(["persistent.", "Referencias"], list(inv["persistent"].items())), "",
              f"Referencias a `persistent.lewd` (material picante): {len(inv['lewd_refs'])}", ""]
    parts += ["## API de Ren'Py usada (renpy.*)", "", table(["Llamada", "Veces"], list(inv["renpy_api"].items())[:40]), ""]
    ps = inv["python_summary"]
    parts += ["## Bloques de Python", "", table(["Categoria", "Bloques/lineas"], list(ps.items())), "",
              "Cada bloque con su clasificacion esta en `build/audit/python_blocks.txt`.", ""]
    parts += [f"## Pantallas (screen) ({len(inv['screens'])})", "",
              table(["Nombre", "Archivo", "Linea", "Lineas"], [[s["name"], s["file"], s["line"], s["lines"]] for s in inv["screens"]]), ""]
    parts += ["## Historia", "", f"Capitulos base: {', '.join(inv['base_chapters'] or [])}", ""]
    for num, chapters in (inv["ending_routes"] or {}).items():
        parts.append(f"- Ruta {num}: {' > '.join(chapters)}")
    parts += ["", "Capitulos extra:", ""] + [f"- {n} -> `{lbl}`" for n, lbl in inv["extra_chapters"]]
    parts += ["", f"Saltos dinamicos (`jump/call expression`): {len(inv['dynamic_jumps'])}", ""]
    for d in inv["dynamic_jumps"][:20]:
        parts.append(f"- `{d['file']}:{d['line']}` {d['kind']} expression `{d['expr']}`")
    parts += ["", "Grafos: `build/audit/grafo_historia.svg` (capitulos) y `build/audit/grafo_labels.svg` (todas las etiquetas).", ""]
    parts += ["## Dialogo por archivo", "",
              table(["Archivo", "Dialogos", "Opciones", "Bloques es"],
                    [[n, v["dialogue"], v["choices"], v["translated_blocks"]] for n, v in inv["per_file"].items()]), ""]
    q = t["quality"]
    parts += ["## Traduccion al espanol", "", table(["Dato", "Valor"], [
        ["Archivos de script sin traduccion es", ", ".join(t["files_missing"]) or "ninguno"],
        ["Bloques de dialogo traducidos", q["blocks"]],
        ["Bloques con texto vacio", q["empty"]],
        ["Bloques con texto igual al original (sospechosos)", q["same_as_original"]],
        ["Pares strings vacios", t["strings_empty"]],
        ["Imagenes con texto traducido (tl/es/images)", t["overlay_images"]],
        ["Texto espanol total (bytes UTF-8)", t["text_bytes"]],
        ["Caracteres distintos", t["distinct_chars"]],
    ]), "", f"Caracteres no ASCII usados: `{t['non_ascii_chars']}`", ""]
    if q["same_examples"]:
        parts += ["Ejemplos de bloques iguales al original:", ""] + [f"- {e}" for e in q["same_examples"]] + [""]
    parts += ["## Galeria", "", table(["Pestana", "Elementos"], list(inv["gallery"].items())), ""]
    parts += ["## Logos encontrados", ""] + [f"- `{p}`" for p in inv["logos"]] + [""]
    im = inv["images"]
    parts += ["## Imagenes", ""]
    if "groups" in im:
        parts += [table(["Carpeta", "Cantidad", "MB", "Con alfa", "Formatos", "Tamanos frecuentes"],
                        [[k, v["count"], v["mb"], v["alpha"], v["formats"], v["top_sizes"]] for k, v in im["groups"].items()]), ""]
        if im["unreadable"]:
            parts += ["No legibles:", ""] + [f"- {u}" for u in im["unreadable"]] + [""]
    au = inv["audio"]
    parts += ["## Audio", ""]
    parts += [table(["Carpeta", "Archivos", "MB", "Minutos", "Formatos"],
                    [[k, v["count"], v["mb"], v["minutes"], v["formats"]] for k, v in au["groups"].items()]), "",
              "Pistas mas largas (min):", ""] + [f"- {m} min: `{n}`" for m, n in au["longest"]] + [""]
    parts += ["## Video", ""] + ([f"- `{v}`" for v in inv["video"]] or ["Ninguno."]) + [""]
    text = "\n".join(parts)
    if DOC_MANUAL.exists():
        text += "\n---\n\n" + DOC_MANUAL.read_text(encoding="utf-8")
    DOC.write_text(text, encoding="utf-8")


def write_python_blocks(inv):
    chunks = []
    for b in inv["python_blocks"]:
        chunks.append(f"=== {b['file']}:{b['line']} [{b['kind']}] -> {b['category']} ({b['reason']})\n{b['text']}\n")
    (OUT / "python_blocks.txt").write_text("\n".join(chunks), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    inv = run_audit()
    (OUT / "inventario.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    write_python_blocks(inv)
    write_doc(inv)
    print(f"Lineas de dialogo: {inv['dialogue_lines']}  etiquetas: {inv['labels']}  desconocidas: {len(inv['unknown'])}")
    print(f"Escrito: {DOC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
