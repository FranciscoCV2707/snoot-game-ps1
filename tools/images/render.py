"""Renderiza las recetas de imagen del juego a pixeles (RGBA) a la resolucion original (Fase 4, etapa 1).

Cubre archivos, composiciones, volteo, efectos (blur, sepia, recorte, escala, alfa, matriz de color), color solido,
capas (layeredimage) y mascaras alfa. Las imagenes traducidas de tl/es reemplazan a las originales, como en Ren'Py.
"""
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

GAME = Path(__file__).resolve().parents[2] / "original" / "game"
LANG = "es"
FULL = (1920, 1080)


def find_file(path):
    """Ruta real de un archivo de imagen: prefiere la version traducida de tl/<idioma>/ si existe."""
    path = path.replace("\\", "/")
    candidates = [path, f"images/{path}"]
    for rel in candidates:
        for base in (GAME / "tl" / LANG, GAME):
            full = base / rel
            if full.exists():
                return full
    lowered = {p.relative_to(GAME).as_posix().lower(): p for p in (GAME / "images").rglob("*") if p.is_file()}
    for rel in candidates:
        hit = lowered.get(rel.lower())
        if hit:
            return hit
    raise FileNotFoundError(path)


def load_file(path):
    with Image.open(find_file(path)) as im:
        return im.convert("RGBA")


def generated(name):
    """Imagenes dibujadas por codigo (interfaz propia)."""
    from PIL import ImageDraw
    if name == "lock":
        img = Image.new("RGBA", (144, 144), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.arc((34, 6, 110, 82), 180, 360, fill=(235, 235, 235, 255), width=14)
        d.line((34, 44, 34, 70), fill=(235, 235, 235, 255), width=14)
        d.line((110, 44, 110, 70), fill=(235, 235, 235, 255), width=14)
        d.rounded_rectangle((16, 66, 128, 138), radius=12, fill=(230, 190, 60, 255), outline=(40, 30, 10, 255), width=5)
        d.ellipse((62, 86, 82, 106), fill=(40, 30, 10, 255))
        d.rectangle((68, 100, 76, 124), fill=(40, 30, 10, 255))
        return img
    raise ValueError(f"imagen generada desconocida: {name}")


def video_frame(path, index):
    """Fotograma de un video a su resolucion original."""
    import io
    import shutil
    import subprocess
    ffmpeg = shutil.which("ffmpeg") or str(Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")
    data = subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(GAME / path), "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
                           "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(data)).convert("RGBA")


def parse_color(text):
    s = text.lstrip("#")
    if len(s) in (3, 4):
        s = "".join(c * 2 for c in s)
    r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4))
    a = int(s[6:8], 16) if len(s) == 8 else 255
    return r, g, b, a


def paste(canvas, img, x, y):
    """alpha_composite con recorte (acepta posiciones negativas o fuera del lienzo)."""
    x, y = int(round(x)), int(round(y))
    cw, ch = canvas.size
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(img.width, cw - x), min(img.height, ch - y)
    if right <= left or bottom <= top:
        return
    region = img.crop((left, top, right, bottom))
    canvas.alpha_composite(region, (x + left, y + top))


def matrix_apply(img, text):
    """im.matrix.brightness(b) / opacity(o) / tint(r,g,b) / saturation(s) sobre una imagen RGBA."""
    arr = np.asarray(img, dtype=np.float32).copy()
    for name, raw in re.findall(r"im\.matrix\.(\w+)\(([^)]*)\)", text):
        args = [float(v) for v in raw.split(",") if v.strip()]
        if name == "brightness":
            arr[..., :3] += 255.0 * args[0]
        elif name == "opacity":
            arr[..., 3] *= args[0]
        elif name == "tint":
            arr[..., :3] *= np.array(args[:3], dtype=np.float32)
        elif name == "saturation":
            gray = arr[..., :3].mean(axis=2, keepdims=True)
            arr[..., :3] = gray + (arr[..., :3] - gray) * args[0]
        else:
            raise ValueError(f"matriz de color sin soporte: {name}")
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def render(recipe):
    op = recipe["op"]
    if op == "file":
        return load_file(recipe["path"])
    if op == "solid":
        return Image.new("RGBA", FULL, parse_color(recipe["color"]))
    if op == "videoframe":
        return video_frame(recipe["path"], recipe["index"])
    if op == "generated":
        return generated(recipe["name"])
    if op == "composite":
        size = tuple(int(v) for v in recipe["size"])
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        for layer in recipe["layers"]:
            x, y = layer["pos"]
            paste(canvas, render(layer["src"]), x, y)
        return canvas
    if op == "stack":
        base = render(recipe["layers"][0]["src"])
        canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
        for layer in recipe["layers"]:
            img = render(layer["src"])
            if layer.get("rotate"):
                img = img.rotate(-layer["rotate"], resample=Image.BICUBIC, expand=False)
            x, y = layer.get("pos") or (0, 0)
            paste(canvas, img, x, y)
        return canvas
    if op == "flip":
        img = render(recipe["src"])
        if recipe.get("horizontal"):
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if recipe.get("vertical"):
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        return img
    if op == "effect":
        return effect(recipe)
    if op == "alphamask":
        mask = render(recipe["mask"])
        content = render(recipe["content"])
        if recipe["content"]["op"] != "solid":
            content = content.resize(mask.size, Image.LANCZOS)
        else:
            content = Image.new("RGBA", mask.size, parse_color(recipe["content"]["color"]))
        alpha = np.asarray(content.split()[3], dtype=np.float32) * np.asarray(mask.split()[3], dtype=np.float32) / 255.0
        out = content.copy()
        out.putalpha(Image.fromarray(alpha.astype(np.uint8)))
        return out
    raise ValueError(f"receta sin soporte: {op}")


def effect(recipe):
    name, args, kwargs = recipe["effect"], recipe.get("args", []), recipe.get("kwargs", {})
    img = render(recipe["src"])
    if name == "im.Blur":
        return img.filter(ImageFilter.GaussianBlur(float(args[0])))
    if name == "im.Sepia":
        arr = np.asarray(img, dtype=np.float32)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        out = arr.copy()
        out[..., 0] = np.clip(0.393 * r + 0.769 * g + 0.189 * b, 0, 255)
        out[..., 1] = np.clip(0.349 * r + 0.686 * g + 0.168 * b, 0, 255)
        out[..., 2] = np.clip(0.272 * r + 0.534 * g + 0.131 * b, 0, 255)
        return Image.fromarray(out.astype(np.uint8), "RGBA")
    if name == "im.Crop":
        rect = args[0] if isinstance(args[0], (list, tuple)) else args[:4]
        x, y, w, h = (int(v) for v in rect)
        return img.crop((x, y, x + w, y + h))
    if name == "im.FactorScale":
        fx = float(args[0])
        fy = float(args[1]) if len(args) > 1 else fx
        return img.resize((max(1, round(img.width * fx)), max(1, round(img.height * fy))), Image.LANCZOS)
    if name == "im.Scale":
        return img.resize((int(args[0]), int(args[1])), Image.LANCZOS)
    if name == "im.Alpha":
        arr = np.asarray(img, dtype=np.float32).copy()
        arr[..., 3] *= float(args[0])
        return Image.fromarray(arr.astype(np.uint8), "RGBA")
    if name == "im.MatrixColor":
        return matrix_apply(img, str(args[0]))
    if name == "Transform":
        xs, ys, fit, zoom = kwargs.get("xsize"), kwargs.get("ysize"), kwargs.get("fit"), kwargs.get("zoom")
        if zoom:
            return img.resize((max(1, round(img.width * zoom)), max(1, round(img.height * zoom))), Image.LANCZOS)
        if xs and ys and fit == "cover":
            k = max(xs / img.width, ys / img.height)
            big = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
            left, top = (big.width - xs) // 2, (big.height - ys) // 2
            return big.crop((left, top, left + xs, top + ys))
        if xs and not ys:
            return img.resize((xs, round(img.height * xs / img.width)), Image.LANCZOS)
        if ys and not xs:
            return img.resize((round(img.width * ys / img.height), ys), Image.LANCZOS)
        if xs and ys:
            return img.resize((xs, ys), Image.LANCZOS)
        return img
    raise ValueError(f"efecto sin soporte: {name}")


def expand(table, recipe, depth=0):
    """Resuelve referencias por nombre y capas en una receta autocontenida (para enviarla a otros procesos)."""
    if depth > 12:
        raise ValueError("receta demasiado profunda")
    op = recipe["op"]
    sub = lambda r: expand(table, r, depth + 1)
    if op == "ref":
        return sub(table.recipes[tuple(recipe["name"])])
    if op == "slideshow":
        return sub(table.recipes[tuple(recipe["frames"][0])])
    if op == "composite":
        return {"op": "composite", "size": recipe["size"],
                "layers": [{"pos": l["pos"], "src": sub(l["src"])} for l in recipe["layers"]]}
    if op == "layered":
        layers = []
        for l in recipe["layers"]:
            layers.append({"pos": l.get("pos"), "rotate": l.get("rotate", 0), "src": sub(table.recipes[tuple(l["name"])])})
        return {"op": "stack", "layers": layers}
    if op == "flip":
        return {"op": "flip", "src": sub(recipe["src"]), "horizontal": recipe.get("horizontal"), "vertical": recipe.get("vertical")}
    if op == "effect":
        return {"op": "effect", "effect": recipe["effect"], "src": sub(recipe["src"]), "args": recipe.get("args", []),
                "kwargs": recipe.get("kwargs", {})}
    if op == "alphamask":
        return {"op": "alphamask", "content": sub(recipe["content"]), "mask": sub(recipe["mask"])}
    return recipe


def first_file(recipe):
    """Primer archivo de una receta (para agrupar sprites por carpeta y compartir paleta)."""
    if recipe.get("op") == "file":
        return recipe["path"]
    for key in ("src", "content"):
        if recipe.get(key):
            hit = first_file(recipe[key])
            if hit:
                return hit
    for layer in recipe.get("layers", []):
        hit = first_file(layer["src"])
        if hit:
            return hit
    return None
