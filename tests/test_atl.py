from tools.script_compiler import atl


def keys_for(stmts, start=(0.0, 0.1)):
    state = atl.State(1000.0, 1500.0)
    state.xalign, state.yalign = start
    comp = atl.Compiler(None, (1000.0, 1500.0), state, lambda m: None)
    comp.run(stmts, 0.0, state.copy())
    initial = state.values()
    keys = atl.quantize_keys(comp.segments, initial, comp.loop, comp.duration)
    return keys, comp


def test_simple_slide():
    keys, comp = keys_for([("easein_cubic 1 xalign 0.5", [])])
    assert [round(k[0], 2) for k in keys] == [0.0, 1.0]
    assert keys[0][1]["x"] == 0.0 and keys[1][1]["x"] == 0.5
    assert keys[1][2] == atl.CURVE_IN
    assert not comp.loop


def test_repeat_makes_loop():
    stmts = [("block:", [("linear 0.5 yalign 0.2", []), ("linear 0.5 yalign 0.1", []), ("repeat", [])])]
    keys, comp = keys_for(stmts)
    assert comp.loop
    assert [round(k[1]["y"], 2) for k in keys] == [0.1, 0.2, 0.1]


def test_parallel_branches_merge():
    stmts = [("parallel:", [("linear 1 xalign 1.0", [])]), ("parallel:", [("linear 2 yalign 0.5", [])])]
    keys, comp = keys_for(stmts)
    last = keys[-1][1]
    assert abs(last["x"] - 1.0) < 1e-6 and abs(last["y"] - 0.5) < 1e-6
    assert keys[-1][0] == 2.0


def test_pos_to_align_uses_sprite_size():
    state = atl.State(1000.0, 1500.0)
    comp = atl.Compiler(None, (1000.0, 1500.0), state, lambda m: None)
    s = state.copy()
    comp.apply(s, "xcenter", 0.5)          # centro de pantalla = xalign 0.5
    assert abs(s.effective()[0] - 0.5) < 1e-6
    comp.apply(s, "xpos", 0)               # borde izquierdo
    comp.apply(s, "xanchor", 0.0)
    assert s.effective()[0] == 0.0


def test_zoom_and_rotation_encoding():
    keys, _ = keys_for([("linear 0.5 zoom 2.0 rotate 90", [])])
    encoded = atl.encode_keys(keys)
    assert encoded[-1][5] == 128 and encoded[-1][7] == 64      # zoom 2.0 -> 128/64, rotate 90 -> 64


def test_anim_table_layout():
    keys, _ = keys_for([("linear 1 xalign 1.0", [])])
    table = atl.build_anim_table([(0, tuple(atl.encode_keys(keys)))])
    assert int.from_bytes(table[:4], "little") == 4
    assert table[4] == 2 and table[5] == 0
    assert len(table) == 4 + 2 + 2 * 14
