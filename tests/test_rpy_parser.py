import pytest

from tools.script_compiler import rpy_parser as p

SAMPLE = '''label chapter_x:
    play music 'audio/OST/a.ogg' fadein 2
    scene bg room with Dissolve(1)
    show anon neutral flip at left, right behind fang:
        easein 1 xalign 0.5
    A "Hola\\n{i}mundo{/i}." id chapter_x_abc123
    "Narrador" with vpunch
    extend" y mas"
    window hide
    pause (0.5)
    $ anonscore += 1
    menu:
        "Opcion uno":
            jump uno
        "Opcion dos" if anonscore > 1:
            call dos
    if anonscore >= 3:
        return
    elif late:
        pass
    else:
        stop music fadeout 3
    hide anon with dissolve
'''


@pytest.fixture
def nodes(tmp_path):
    f = tmp_path / "t.rpy"
    f.write_text(SAMPLE, encoding="utf-8")
    return p.parse_file(f)


def kinds(nodes):
    return [type(n).__name__ for n in p.flatten(nodes)]


def test_parses_all_statement_kinds(nodes):
    k = kinds(nodes)
    for expected in ("Label", "Play", "Scene", "Show", "Say", "Window", "Pause", "Py", "Menu", "If", "Stop", "Hide"):
        assert expected in k


def test_show_modifiers(nodes):
    show = next(n for n in p.flatten(nodes) if isinstance(n, p.Show))
    assert show.image == ("anon", "neutral", "flip")
    assert show.tag == "anon"
    assert show.at == ["left", "right"]
    assert show.behind == ["fang"]
    assert show.atl == [("easein 1 xalign 0.5", [])]


def test_say_id_with_and_extend(nodes):
    says = [n for n in p.flatten(nodes) if isinstance(n, p.Say)]
    assert says[0].who == "A" and says[0].text_id == "chapter_x_abc123"
    assert says[0].text == "Hola\n{i}mundo{/i}."
    assert says[1].who is None and says[1].with_ == "vpunch"
    assert says[2].extend and says[2].text == " y mas"


def test_menu_choices_and_conditions(nodes):
    menu = next(n for n in p.flatten(nodes) if isinstance(n, p.Menu))
    assert [c[0] for c in menu.choices] == ["Opcion uno", "Opcion dos"]
    assert menu.choices[1][1] == "anonscore > 1"
    assert isinstance(menu.choices[0][2][0], p.Jump)
    assert isinstance(menu.choices[1][2][0], p.Call)


def test_if_chain(nodes):
    node = next(n for n in p.flatten(nodes) if isinstance(n, p.If))
    assert [c for c, _ in node.branches] == ["anonscore >= 3", "late", None]


def test_play_and_pause_values(nodes):
    play = next(n for n in p.flatten(nodes) if isinstance(n, p.Play))
    assert play.channel == "music" and play.fadein == 2.0 and play.sources == ["audio/OST/a.ogg"]
    pause = next(n for n in p.flatten(nodes) if isinstance(n, p.Pause))
    assert pause.seconds == 0.5


def test_unknown_statement_raises(tmp_path):
    f = tmp_path / "bad.rpy"
    f.write_text("label a:\n    frobnicate the thing\n", encoding="utf-8")
    with pytest.raises(p.ParseError):
        p.parse_file(f)


def test_eval_number_and_unquote():
    assert p.eval_number("(.5+.25)") == 0.75
    assert p.unquote(r'"a\"b\ c\%"') == 'a"b c%'
