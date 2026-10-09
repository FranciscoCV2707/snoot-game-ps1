"""Tabla de imagenes del juego: nombres de Ren'Py -> recetas de recursos (Fase 3, etapa 2).

Reune las imagenes definidas automaticamente por nombre de archivo, las `image` de `src/image_definitions.rpy`
y las llamadas `renpy.image(...)`. Cada imagen es una receta (archivo, composicion, color, efecto) que el
pipeline de imagenes de la Fase 4 convierte; aqui solo se resuelven nombres y se asignan IDs.
"""
import ast
import json
import re
from pathlib import Path

from tools.script_compiler.rpy_parser import ImageDef, LayeredImage, Py, flatten, parse_file

GAME = Path(__file__).resolve().parents[2] / "original" / "game"
IMAGE_EXTS = {".webp", ".png", ".jpg", ".jpeg"}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
BUILTIN_NAMES = {("black",): {"op": "solid", "color": "#000000"}}


def name_key(words):
    return tuple(w.lower() for w in words)


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def eval_pos(node):
    """Posicion (x, y) de una capa de Composite; admite expresiones como (0, 1080-126)."""
    value = literal(node)
    if value is not None:
        return value
    from tools.script_compiler.rpy_parser import eval_number
    if isinstance(node, ast.Tuple):
        return tuple(eval_number(ast.unparse(e)) for e in node.elts)
    return (0, 0)


def arg_value(node):
    value = literal(node)
    return value if value is not None else ast.unparse(node)


def call_name(node):
    f = node.func
    parts = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))


def recipe_of(node):
    """Convierte la expresion de una imagen en una receta (dict)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        s = node.value
        if COLOR_RE.match(s):
            return {"op": "solid", "color": s}
        if "/" in s or Path(s).suffix.lower() in IMAGE_EXTS:
            return {"op": "file", "path": s}
        return {"op": "ref", "name": name_key(s.split())}
    if isinstance(node, ast.Call):
        name = call_name(node)
        args = [recipe_of(a) if isinstance(a, (ast.Constant, ast.Call)) else literal(a) for a in node.args]
        kwargs = {k.arg: literal(k.value) for k in node.keywords}
        if name == "Composite" or name == "LiveComposite":
            size = literal(node.args[0])
            layers = []
            rest = node.args[1:]
            for i in range(0, len(rest) - 1, 2):
                layers.append({"pos": eval_pos(rest[i]), "src": recipe_of(rest[i + 1])})
            return {"op": "composite", "size": size, "layers": layers}
        if name == "im.Flip":
            return {"op": "flip", "src": args[0], "horizontal": kwargs.get("horizontal", False), "vertical": kwargs.get("vertical", False)}
        if name in ("im.Blur", "im.Sepia", "im.Crop", "im.MatrixColor", "im.Scale", "im.FactorScale", "im.Alpha", "im.Grayscale", "im.Tile", "Transform"):
            return {"op": "effect", "effect": name, "src": args[0] if args else None, "args": [arg_value(a) for a in node.args[1:]], "kwargs": kwargs}
        if name == "Movie":
            return {"op": "movie", "kwargs": kwargs}
        if name == "Solid":
            return {"op": "solid", "color": literal(node.args[0])}
        return {"op": "unknown", "call": name}
    return {"op": "unknown", "call": type(node).__name__}


def auto_images():
    table = {}
    for path in sorted((GAME / "images").rglob("*")):
        if path.suffix.lower() in IMAGE_EXTS and path.is_file():
            key = name_key(path.stem.split())
            table.setdefault(key, {"op": "file", "path": path.relative_to(GAME).as_posix()})
    return table


def atl_image_recipe(atl):
    """Imagen definida con ATL: una imagen con crop/zoom, o un pase de diapositivas (cambios de imagen con pausas)."""
    from tools.script_compiler.atl import parse_transition
    frames, times, dissolves, loop, crop, zoom = [], [], [], False, None, None
    for text, _ in atl:
        m = re.match(r"""^["']([^"']*)["'](?:\s+with\s+(.+))?$""", text)
        if m:
            frames.append(name_key(m.group(1).split()))
            times.append(0.0)
            spec = parse_transition(m.group(2)) if m.group(2) else None
            dissolves.append(spec[1] if spec and spec[0] == 1 else 0)
        elif text.startswith("pause") and times:
            times[-1] += float(text.split()[1])
        elif text.strip() == "repeat":
            loop = True
        elif text.startswith("crop"):
            crop = literal(ast.parse(text[4:].strip(), mode="eval").body)
        elif text.startswith("zoom"):
            zoom = float(text.split()[1])
    if not frames:
        return {"op": "unknown", "call": "atl-sin-imagen"}
    if len(frames) == 1:
        recipe = {"op": "ref", "name": frames[0]}
        if crop:
            recipe = {"op": "effect", "effect": "im.Crop", "src": recipe, "args": [list(crop)], "kwargs": {}}
        if zoom:
            recipe = {"op": "effect", "effect": "im.FactorScale", "src": recipe, "args": [zoom], "kwargs": {}}
        return recipe
    return {"op": "slideshow", "frames": [list(f) for f in frames], "times": times, "dissolve": dissolves, "loop": loop}


def defined_images():
    """Imagenes de `image x = ...` y de `renpy.image('x', ...)` en src/image_definitions.rpy."""
    table = {}
    for node in flatten(parse_file(GAME / "src" / "image_definitions.rpy", "src/image_definitions.rpy")):
        if isinstance(node, ImageDef):
            if node.value is not None:
                try:
                    table[name_key(node.name)] = recipe_of(ast.parse(node.value, mode="eval").body)
                except SyntaxError:
                    table[name_key(node.name)] = {"op": "unknown", "call": "syntax"}
            else:
                table[name_key(node.name)] = atl_image_recipe(node.atl)
        elif isinstance(node, Py) and node.block:
            try:
                tree = ast.parse(node.code)
            except SyntaxError:
                continue
            for stmt in ast.walk(tree):
                if isinstance(stmt, ast.Call) and call_name(stmt) == "renpy.image" and len(stmt.args) >= 2:
                    nm = literal(stmt.args[0])
                    if isinstance(nm, str):
                        table[name_key(nm.split())] = recipe_of(stmt.args[1])
    return table


POS_PROP = re.compile(r"pos\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)")
ROT_PROP = re.compile(r"rotate\s+(-?[\d.]+)")


def layer_props(children):
    pos, rot = None, 0.0
    for text, _ in children:
        m = POS_PROP.match(text)
        if m:
            pos = (float(m.group(1)), float(m.group(2)))
        m = ROT_PROP.match(text)
        if m:
            rot = float(m.group(1))
    return {"pos": pos, "rotate": rot}


def layered_images():
    """layeredimage de image_definitions: nombre -> {always: [capas], groups: [(grupo, {atributo: imagen}, defecto, props)]}."""
    out = {}
    for node in flatten(parse_file(GAME / "src" / "image_definitions.rpy", "src/image_definitions.rpy")):
        if not isinstance(node, LayeredImage):
            continue
        spec = {"always": [], "groups": []}
        for text, children in node.body:
            if text.startswith("always"):
                props = layer_props(children)
                for c in children:
                    if c[0][:1] in "\"'":
                        spec["always"].append({"image": c[0].strip("\"'"), **props})
            elif text.startswith("group"):
                attrs, default = {}, None
                for ctext, cchildren in children:
                    am = re.match(r"attribute\s+(\w+)(\s+default)?\s*:", ctext)
                    if am and cchildren:
                        attrs[am.group(1)] = cchildren[0][0].strip("\"'")
                        if am.group(2):
                            default = am.group(1)
                spec["groups"].append((text.split()[1].rstrip(":"), attrs, default, layer_props(children)))
        out[node.name] = spec
    return out


class ImageTable:
    def __init__(self):
        self.recipes = {**auto_images(), **BUILTIN_NAMES}
        self.recipes.update(defined_images())
        self.layered = layered_images()
        self.tags = {}
        for key in self.recipes:
            self.tags.setdefault(key[0], []).append(key)

    def movie_frames(self, key):
        """Fotogramas elegidos de un video (Movie): se registran como imagenes `videoframe` (decision D3)."""
        cache = self.__dict__.setdefault("_movies", {})
        if key in cache:
            return cache[key]
        from tools.script_compiler.video import select_frames
        recipe = self.recipes[key]
        path = recipe["kwargs"].get("play")
        picks = select_frames(GAME / path)
        frames = []
        for n, (index, _) in enumerate(picks["frames"]):
            fkey = key + (f"~f{n}",)
            self.recipes[fkey] = {"op": "videoframe", "path": path, "index": index}
            frames.append(fkey)
        cache[key] = {"frames": frames, "times": picks["times"], "dissolve": [0] * len(frames), "loop": True}
        return cache[key]

    def animation_of(self, key):
        """Animacion de una imagen (pase de diapositivas, video o capa animada de un layeredimage), o None."""
        recipe = self.recipes.get(key)
        seen = 0
        while recipe and recipe["op"] == "ref" and seen < 8:
            key, recipe, seen = tuple(recipe["name"]), self.recipes.get(tuple(recipe["name"])), seen + 1
        if not recipe:
            return None
        if recipe["op"] == "slideshow":
            return {"frames": [tuple(f) for f in recipe["frames"]], "times": recipe["times"],
                    "dissolve": recipe["dissolve"], "loop": recipe["loop"]}
        if recipe["op"] == "movie":
            return self.movie_frames(key)
        if recipe["op"] == "layered":
            for i, layer in enumerate(recipe["layers"]):
                sub = self.animation_of(tuple(layer["name"]))
                if not sub:
                    continue
                variants = []
                for n, frame in enumerate(sub["frames"]):
                    vkey = key + (f"~v{i}_{n}",)
                    layers = [dict(l) for l in recipe["layers"]]
                    layers[i]["name"] = list(frame)
                    self.recipes[vkey] = {"op": "layered", "layers": layers}
                    variants.append(vkey)
                return {"frames": variants, "times": sub["times"], "dissolve": sub["dissolve"], "loop": sub["loop"]}
        return None

    def add_blur(self, key, value):
        """Variante desenfocada de una imagen (se renderiza en la Fase 4); `value` es el blur original de Ren'Py."""
        newkey = key + (f"~blur{int(value)}",)
        if newkey not in self.recipes:
            recipe, flip = self.canonical(key)
            blurred = {"op": "effect", "effect": "im.Blur", "src": recipe, "args": [value], "kwargs": {}}
            if flip:
                blurred = {"op": "flip", "src": blurred, "horizontal": True, "vertical": False}
            self.recipes[newkey] = blurred
        return newkey

    def add_alphamask(self, content_words, mask_words):
        """AlphaMask(contenido, mascara) estatico: una imagen con la forma de la mascara (se renderiza en la Fase 4)."""
        content, mask = self.resolve(content_words), self.resolve(mask_words)
        if content is None or mask is None:
            return None
        key = ("~mask",) + content + ("|",) + mask
        self.recipes[key] = {"op": "alphamask", "content": self.canonical(content)[0], "mask": self.canonical(mask)[0]}
        return key

    def resolve_layered(self, words, current_attrs=()):
        """Atributos efectivos de un layeredimage (por grupo: el pedido, el actual o el predeterminado)."""
        name = words[0]
        spec = self.layered[name]
        wanted, current = set(words[1:]), set(current_attrs)
        chosen = []
        layers = [{"name": name_key(c["image"].split()), "pos": c["pos"], "rotate": c["rotate"]} for c in spec["always"]]
        for group, attrs, default, props in spec["groups"]:
            pick = next((a for a in attrs if a in wanted), None) or next((a for a in attrs if a in current), None) or default
            if pick:
                chosen.append(pick)
                layers.append({"name": name_key(attrs[pick].split()), "pos": props["pos"], "rotate": props["rotate"]})
        key = (name, *sorted(chosen))
        self.recipes[key] = {"op": "layered", "layers": layers}
        return key

    def canonical(self, key, _depth=0):
        """Devuelve (receta base, volteo): resuelve referencias y envolturas de volteo."""
        recipe = self.recipes[key]
        flip = False
        while _depth < 8:
            _depth += 1
            if recipe["op"] == "ref" and recipe["name"] in self.recipes:
                recipe = self.recipes[recipe["name"]]
            elif recipe["op"] == "flip" and recipe["src"] and not recipe.get("vertical"):
                flip = not flip
                recipe = recipe["src"]
            elif recipe["op"] == "slideshow":
                recipe = self.recipes[tuple(recipe["frames"][0])]
            elif recipe["op"] == "movie":
                frames = self.movie_frames(key)
                recipe = self.recipes[frames["frames"][0]]
            else:
                break
        return recipe, flip

    def resolve(self, words, current_attrs=()):
        """Elige la imagen para `show tag attrs...` como lo hace Ren'Py. Devuelve la clave o None.

        1. Nombre exacto. 2. Imagenes con el mismo tag que contengan todos los atributos pedidos; entre ellas se
        prefiere la que comparte mas atributos con la imagen actual del tag (por eso un `flip` anterior se conserva).
        """
        key = name_key(words)
        if key in self.recipes:
            return key
        tag, wanted = key[0], set(key[1:])
        candidates = [k for k in self.tags.get(tag, []) if wanted <= set(k[1:])]
        if not candidates:
            return None
        current = set(current_attrs)
        candidates.sort(key=lambda k: (-len(current & set(k[1:])), len(k)))
        return min(candidates, key=lambda k: (-len(current & set(k[1:])), len(k), k))


def main():
    table = ImageTable()
    kinds = {}
    for r in table.recipes.values():
        kinds[r["op"]] = kinds.get(r["op"], 0) + 1
    print("imagenes:", len(table.recipes), kinds)
    unknown = sorted({r.get("call") for r in table.recipes.values() if r["op"] == "unknown"})
    print("constructores desconocidos:", unknown)
    out = Path(__file__).resolve().parents[2] / "build" / "audit" / "images_table.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({" ".join(k): v for k, v in table.recipes.items()}, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
