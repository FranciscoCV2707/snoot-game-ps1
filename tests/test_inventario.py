from tools.audit import inventario as inv

SAMPLE = '''label chapter_x:
    scene bg room with Dissolve(1)
    show anon neutral at left:
        easein 1 xalign 0.5
        linear 0.5 yalign 0.1
    A "Hola {i}mundo{/i}." id chapter_x_abc123
    "Narrador # no es comentario"
    $ anonscore += 1
    menu:
        "Opcion uno":
            jump uno
        "Opcion dos" if anonscore > 1:
            call dos
    play music "a.ogg" fadein 2
    init python:
        pass
    return
'''


def parse(text, rel="script/test.rpy"):
    audit = inv.Audit()
    inv.parse_text(audit, text, rel, True)
    return audit


def test_strip_comment_respects_quotes():
    assert inv.strip_comment('A "hola # no" # si') == 'A "hola # no"'
    assert inv.strip_comment("# todo") == ""


def test_bracket_balance_ignores_strings():
    assert inv.bracket_balance('x = ("a(" ,') == 1
    assert inv.bracket_balance("),") == -1


def test_guess_type():
    assert inv.guess_type("True") == "bool"
    assert inv.guess_type("-3") == "int"
    assert inv.guess_type("_('x')") == "str"
    assert inv.guess_type("{}") == "dict"


def test_parse_counts_dialogue_and_choices():
    audit = parse(SAMPLE)
    assert audit.statements["dialogue"] == 2
    assert audit.statements["menu choice"] == 2
    assert audit.statements["menu"] == 1
    assert audit.dialogue_per_file["script/test.rpy"] == 2


def test_atl_lines_are_not_unknown():
    audit = parse(SAMPLE)
    assert not audit.unknown


def test_edges_and_labels():
    audit = parse(SAMPLE)
    assert "chapter_x" in audit.labels
    assert ("chapter_x", "jump", "uno", "script/test.rpy", 11) in audit.edges
    assert ("chapter_x", "call", "dos", "script/test.rpy", 13) in audit.edges


def test_python_one_liner_and_assignment():
    audit = parse(SAMPLE)
    assert audit.assigned["anonscore"] == 1
    assert audit.statements["$"] == 1


def test_text_tags_counted():
    audit = parse(SAMPLE)
    assert audit.text_tags["i"] == 1


def test_classify_python():
    assert inv.classify_python({"file": "script/a.rpy", "kind": "$", "text": "$ x = 3"})[0] == "traducible automaticamente"
    assert inv.classify_python({"file": "src/mod_menu.rpy", "kind": "init python:", "text": "def f(): pass"})[0] == "descartable"
    assert inv.classify_python({"file": "script/a.rpy", "kind": "python:", "text": "renpy.display_menu(c)"})[0] == "a mano"


def test_extract_literal():
    text = 'define ROUTES = {\n    1: ["a", "b"],  # comentario\n    2: ["c"]\n}\n'
    assert inv.extract_literal(text, "ROUTES") == {1: ["a", "b"], 2: ["c"]}
