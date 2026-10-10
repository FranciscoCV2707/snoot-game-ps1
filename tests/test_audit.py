import numpy as np

from tools.audit.capture import RUNS
from tools.audit.compare import blend, missing_tags, norm
from tools.script_compiler.atl import recipe_size


def test_blend_modes_match_ps1_gpu():
    px = np.full((1, 1, 3), 100, np.uint8)
    for mode, color, expected in [(0, (10, 10, 10), 10), (1, (0, 0, 0), 50), (2, (200, 200, 200), 255),
                                  (3, (30, 30, 30), 70), (4, (40, 40, 40), 110)]:
        sub = px.copy()
        blend(sub, mode, color)
        assert sub[0, 0, 0] == expected


def test_missing_tags_ignores_solids_and_drawn_images():
    tags = [["garden", ["garden"]], ["dimmer_light", ["dimmer_light"]], ["naomi", ["naomi", "neutral"]],
            ["reed", ["reed", "shocked"]]]
    assert missing_tags(tags, ["garden", "naomi neutral", "rect1"], {"dimmer_light"}) == ["reed shocked"]


def test_norm_drops_text_tags():
    assert norm("{i}¡Hola, Anon!{/i}") == "holaanon"


def test_recipe_size_applies_size_effects():
    base = {"op": "composite", "size": [800, 500]}
    assert recipe_size({"op": "effect", "effect": "im.FactorScale", "args": [4.5], "src": base}) == (3600.0, 2250.0)
    assert recipe_size({"op": "effect", "effect": "im.Crop", "args": [[300, 0, 1320, 1080]], "src": base}) == (1320.0, 1080.0)
    assert recipe_size({"op": "effect", "effect": "Transform", "kwargs": {"zoom": 0.5}, "src": base}) == (400.0, 250.0)
    assert recipe_size({"op": "effect", "effect": "im.Blur", "args": [2.0], "src": base}) == (800.0, 500.0)


def test_capture_runs_cover_routes_and_extras():
    assert {"base", "r1", "r2", "r3", "r4", "x1", "x10"} <= set(RUNS)


def test_uniform_translucent_detects_even_veils_only():
    from tools.images.convert import uniform_translucent
    assert uniform_translucent(np.full((8, 8), 156, np.uint8))
    ramp = np.tile(np.linspace(30, 255, 8).astype(np.uint8), (8, 1))
    assert not uniform_translucent(ramp)
    assert not uniform_translucent(np.full((8, 8), 255, np.uint8))


def test_emutest_script_encoding():
    import struct
    from tools.engine.emutest import QUIT, SHOT, autotest_bin, parse_steps
    steps = parse_steps("40 press CROSS; 30 shot titulo; 90 quit")
    assert [s[0] for s in steps] == [30, 40, 90]
    blob = autotest_bin(steps)
    assert struct.unpack_from("<H", blob)[0] == 3
    assert struct.unpack_from("<IH", blob, 2) == (30, SHOT)
    assert struct.unpack_from("<IH", blob, 8) == (40, 1 << 14)
    assert struct.unpack_from("<IH", blob, 14) == (90, QUIT)
