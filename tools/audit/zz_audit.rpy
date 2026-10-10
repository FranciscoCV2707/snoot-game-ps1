# Auditoria del port a PS1: recorre la historia saltando, elige decisiones al azar (semilla fija) y guarda una
# captura cada vez que la escena cambia. Se activa con la variable de entorno SNOOT_AUDIT_OUT.

init 999 python:
    import os, json, random as _audit_random

    AUDIT_OUT = os.environ.get("SNOOT_AUDIT_OUT")

    if AUDIT_OUT:
        os.makedirs(AUDIT_OUT, exist_ok=True)
        _audit_log = open(os.path.join(AUDIT_OUT, "log.jsonl"), "w", encoding="utf-8")
        _audit_rng = _audit_random.Random(int(os.environ.get("SNOOT_AUDIT_SEED", "1")))
        _audit_forced = [int(x) for x in os.environ.get("SNOOT_AUDIT_CHOICES", "").split(",") if x.strip()]
        _audit_state = {"sig": None, "shot": None, "n": 0, "menus": 0}

        def audit_write(**rec):
            _audit_log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            _audit_log.flush()

        def audit_sig():
            sl = renpy.game.context().scene_lists
            out = []
            for layer in ("master",):
                for e in sl.layers.get(layer, []):
                    out.append((e.tag, e.name, id(e.displayable)))
            return tuple(out)

        def audit_shot():
            _audit_state["n"] += 1
            name = "s%05d.png" % _audit_state["n"]
            surf = renpy.display.draw.screenshot(renpy.game.interface.surftree)
            surf = renpy.display.scale.smoothscale(surf, (480, 270))
            renpy.display.scale.image_save_unscaled(surf, os.path.join(AUDIT_OUT, name))
            return name

        def audit_say(event, interact=True, **kw):
            if event != "begin" or not interact:
                return
            sig = audit_sig()
            if sig != _audit_state["sig"]:
                _audit_state["sig"] = sig
                # deja terminar transiciones y animaciones antes de capturar
                renpy.config.skipping = None
                store._window_hide(None)
                renpy.pause(float(os.environ.get("SNOOT_AUDIT_WAIT", "0.7")), hard=True)
                _audit_state["shot"] = audit_shot()
                renpy.config.skipping = "slow"
            audit_write(k="say", what=kw.get("what", ""), shot=_audit_state["shot"],
                        tags=[list(t[:2]) for t in _audit_state["sig"]])

        config.all_character_callbacks.append(audit_say)

        def audit_menu(items, *args, **kwargs):
            opts = []
            for label, value in items:
                if value is None:
                    continue
                if isinstance(value, renpy.ui.ChoiceReturn):
                    if not value.sensitive:
                        continue
                opts.append((label, value))
            m = _audit_state["menus"]
            _audit_state["menus"] += 1
            i = _audit_forced[m] if m < len(_audit_forced) else _audit_rng.randrange(len(opts))
            i = min(i, len(opts) - 1)
            label, value = opts[i]
            audit_write(k="menu", options=[renpy.translate_string(l) for l, _ in opts], chosen=i)
            if isinstance(value, renpy.ui.ChoiceReturn):
                value = value.value
            renpy.config.skipping = "slow"
            return value

        renpy.exports.display_menu = audit_menu
        store.menu = audit_menu

        def audit_label(name, abnormal):
            if name and (name.startswith("chapter_") or name in ("storyline", "lending")):
                audit_write(k="label", name=name)
                # despues de los creditos el juego vuelve a empezar: la corrida ya termino
                if name == "storyline" and _audit_state.get("credits"):
                    renpy.quit()
                if name == "lending":
                    _audit_state["credits"] = True
                if name in os.environ.get("SNOOT_AUDIT_UNTIL", "").split(","):
                    renpy.quit()

        config.label_callbacks.append(audit_label)

        def audit_keep_skipping():
            if not renpy.config.skipping and _audit_state["n"]:
                renpy.config.skipping = "slow"

        config.periodic_callbacks.append(audit_keep_skipping)
        config.skip_delay = 1
        config.allow_skipping = True
        config.label_overrides["splashscreen"] = "audit_main"

label audit_main:
    $ renpy.change_language("es")
    $ persistent.lewd = True
    $ _preferences.skip_unseen = True
    $ _preferences.transitions = 2
    $ active_queue = list(BASE_CHAPTERS)
    python:
        _from = os.environ.get("SNOOT_AUDIT_FROM")
        if _from and _from in active_queue:
            active_queue = active_queue[active_queue.index(_from):]
        _route = os.environ.get("SNOOT_AUDIT_ROUTE")
        if _route:
            ending_route_number = int(_route)
            chapter_select_used = True
            ending_chapters_determined = True
            active_queue = list(ENDING_ROUTES[ending_route_number])
        _audit_state["n"] = 0
        renpy.config.skipping = "slow"
        audit_write(k="start")
    if os.environ.get("SNOOT_AUDIT_LABEL"):
        $ renpy.call(os.environ["SNOOT_AUDIT_LABEL"])
        $ renpy.quit()
    jump storyline

label main_menu:
    $ renpy.quit()
