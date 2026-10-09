import struct

import lz4.block
import numpy as np
import pytest

from tools.images import convert, render


@pytest.fixture
def out_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(convert, "OUT", tmp_path / "IMG")
    monkeypatch.setattr(convert, "TMP", tmp_path / "tmp")
    monkeypatch.setattr(convert, "REPORT_DIR", tmp_path / "rep")
    for d in ("IMG", "tmp", "rep"):
        (tmp_path / d).mkdir()
    return tmp_path


def read_img(path):
    data = path.read_bytes()
    size = struct.calcsize(convert.HEADER)
    header = struct.unpack_from(convert.HEADER, data, 0)
    words = struct.unpack_from("<256H", data, size)
    raw_size, comp_size = struct.unpack_from("<II", data, size + 512)
    body = data[size + 512 + 8:]
    pixels = lz4.block.decompress(body, uncompressed_size=raw_size) if raw_size else b""
    return header, words, pixels


def test_parse_color_and_matrix():
    assert render.parse_color("#fff") == (255, 255, 255, 255)
    assert render.parse_color("#0c054288") == (12, 5, 66, 136)
    from PIL import Image
    img = Image.new("RGBA", (2, 2), (200, 100, 50, 255))
    assert render.matrix_apply(img, "im.matrix.brightness(-1)").getpixel((0, 0))[:3] == (0, 0, 0)
    assert render.matrix_apply(img, "im.matrix.opacity(0.5)").getpixel((0, 0))[3] == 127


def test_background_conversion(out_dirs):
    recipe = {"op": "composite", "size": (1920, 1080), "layers": [
        {"pos": (0, 0), "src": {"op": "solid", "color": "#336699"}},
        {"pos": (960, 0), "src": {"op": "solid", "color": "#cc3300"}}]}
    meta = convert.phase1((1, recipe, None, "fondo"))
    assert meta["kind"] == convert.KIND_BG and (meta["full_w"], meta["full_h"]) == (320, 180)
    result = convert.phase3((meta, []))
    header, words, pixels = read_img(out_dirs / "IMG" / "I0001.IMG")
    assert header[0] == b"IMG1" and header[1] == convert.KIND_BG
    assert len(pixels) == 320 * 180
    assert all(w != 0 for w in words[:2]) and result["comp"] < result["raw"]


def test_sprite_crops_transparent_border_and_reserves_index_zero(out_dirs):
    from PIL import Image
    sprite = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
    sprite.paste((250, 20, 20, 255), (120, 180, 480, 780))
    path = out_dirs / "sprite.png"
    sprite.save(path)
    recipe = {"op": "effect", "effect": "im.Crop", "src": {"op": "file", "path": str(path)},
              "args": [[0, 0, 600, 900]], "kwargs": {}}
    # find_file acepta rutas absolutas existentes
    meta = convert.phase1((2, recipe, None, "sprite"))
    assert meta["kind"] == convert.KIND_SPRITE
    assert (meta["full_w"], meta["full_h"]) == (100, 150)
    # el suavizado del reescalado puede ensanchar el borde 1 pixel
    assert abs(meta["x"] - 20) <= 1 and abs(meta["y"] - 30) <= 1 and abs(meta["w"] - 60) <= 2 and abs(meta["h"] - 100) <= 2
    flat = [250, 20, 20] + [0] * (254 * 3)
    convert.phase3((meta, flat))
    header, words, pixels = read_img(out_dirs / "IMG" / "I0002.IMG")
    assert words[0] == 0                         # el indice 0 es transparente
    assert min(words[1:3]) != 0                  # ningun color visible vale 0x0000
    assert set(pixels) <= {0, 1} and 1 in set(pixels)   # cuerpo con el primer color; el borde suave puede quedar transparente


def test_to555_never_zero():
    assert convert.to555((0, 0, 0)) == 0x0421
    assert convert.to555((255, 255, 255)) == 0x7FFF
