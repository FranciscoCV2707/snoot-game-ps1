"""Compilador completo: original/ -> build/data (Fase 3).

Uso: python -m tools.script_compiler.compile
"""
import json
import struct
import sys
from pathlib import Path

from tools.script_compiler import assemble
from tools.script_compiler.lower import CompileError, Inst, Lowerer, Registry
from tools.script_compiler.opcodes import OP_CODE
from tools.script_compiler.project import GAME, Project

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "data"


class Result:
    def __init__(self):
        self.irs = {}
        self.story = None
        self.warnings = []
        self.errors = []


def lower_all(project, registry):
    result = Result()
    snapshot, group = None, None
    for name, chapter in project.lowering_order():
        if name != group:
            if group == "base":
                snapshot = dict(registry.last_key)
            registry.last_key = dict(snapshot) if (name.startswith("route") and snapshot is not None) else {}
            group = name
        try:
            ir = Lowerer(project, registry, chapter).run()
            result.irs[chapter.index] = ir
            result.warnings.extend(ir.warnings)
        except CompileError as exc:
            result.errors.append(str(exc))
    return result


def register_gallery(project, registry):
    """Registra las imagenes de la galeria (aunque la historia no las muestre) y devuelve sus entradas."""
    data = json.loads((GAME / "src" / "gallery_dataset.json").read_text(encoding="utf-8-sig"))
    entries = []
    for tab in data["tabs"]:
        for item in tab.get("items", []):
            key = project.images.resolve(item["image"].split())
            entry = {"tab": tab["tab_name"], "name": item["name"], "image": item["image"], "id": None}
            if key is not None:
                entry["id"] = registry.image_id(key)[0]
            entries.append(entry)
    return entries


def story_insts(project, registry):
    """STORY.VNB: valores iniciales, capitulos base, eleccion de ruta y cadena de la ruta (de src/storyline.rpy)."""
    insts = []
    n = [0]

    def emit(_name, **args):
        insts.append(Inst(_name, args, 0, "STORY"))

    def label(name):
        emit("LABEL", name=name)

    def call(label_name):
        emit("LOAD_CHAPTER", chapter=project.label_chapter[label_name], entry=label_name, mode=0)

    var = registry.var
    for name, value in (("anonscore", 0), ("fangscore", 0), ("wingStory", 0), ("ending_route_number", 0)):
        emit("SET_VAR", var=var(name), value=value)
    for chapter in project.base_chapters:
        call(chapter)

    def cmp(name, op, value):
        emit("PUSH_VAR", var=var(name))
        emit("PUSH_CONST", value=value)
        emit("OP", op=OP_CODE[op])

    def route(num, lbl_next):
        emit("SET_VAR", var=var("ending_route_number"), value=num)
        emit("JUMP", target="story.dispatch")

    # get_ending(anon, fang, wing)
    cmp("anonscore", ">=", 4); cmp("fangscore", ">=", 4); emit("OP", op=OP_CODE["and"])
    emit("PUSH_VAR", var=var("wingStory")); emit("OP", op=OP_CODE["and"])
    emit("JUMP_IF_FALSE", target="story.r3"); route(4, None)
    label("story.r3")
    cmp("anonscore", ">=", 3); cmp("fangscore", "<=", 4); emit("OP", op=OP_CODE["and"])
    emit("JUMP_IF_FALSE", target="story.r2"); route(3, None)
    label("story.r2")
    cmp("anonscore", "<=", 3); cmp("fangscore", ">=", 3); emit("OP", op=OP_CODE["and"])
    emit("JUMP_IF_FALSE", target="story.r1"); route(2, None)
    label("story.r1")
    emit("SET_VAR", var=var("ending_route_number"), value=1)
    label("story.dispatch")
    for num in sorted(project.ending_routes):
        cmp("ending_route_number", "==", num)
        emit("JUMP_IF_FALSE", target=f"story.skip{num}")
        for chapter in project.ending_routes[num]:
            call(chapter)
        if num != 1:
            emit("SPECIAL", id=2)
        emit("END")
        label(f"story.skip{num}")
    emit("HALT")
    return insts


def compile_all(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    project = Project()
    registry = Registry(project)
    result = lower_all(project, registry)
    if result.errors:
        return project, registry, result
    gallery = register_gallery(project, registry)
    story = story_insts(project, registry)

    # --- primera pasada: offsets de etiquetas de cada capitulo
    units = [(ch.index, ch.name, result.irs[ch.index].insts) for ch in project.chapters]
    story_index = len(project.chapters)
    units.append((story_index, "STORY", story))
    layouts = {idx: assemble.layout(insts) for idx, _, insts in units}

    def entry_resolver(chapter, label):
        return layouts[chapter][0][label]

    # --- ids de etiquetas y segunda pasada
    label_ids, bases, text_chapters, files = {}, {}, [], {}
    base = 0
    for idx, name, insts in units:
        offsets, size = layouts[idx]
        code = assemble.encode(insts, offsets, entry_resolver, name)
        exported = sorted((n, o) for n, o in offsets.items() if not n.startswith(".") and not n.startswith("story."))
        table = []
        for n, o in exported:
            table.append((label_ids.setdefault(n, len(label_ids)), o))
        strings = [s["text"] for s in result.irs[idx].strings] if idx in result.irs else []
        bases[idx] = base
        blob = assemble.build_vnb(idx, code, table, base, len(strings), b"", 0)
        base += len(strings)
        files[f"C{idx:02d}.VNB" if idx != story_index else "STORY.VNB"] = blob
        text_chapters.append((idx, strings))

    (out / "SCRIPT").mkdir(exist_ok=True)
    for fname, blob in files.items():
        (out / "SCRIPT" / fname).write_bytes(blob)
    (out / "TEXT_ES.BIN").write_bytes(assemble.build_text_table(text_chapters))

    ending_names = {"e1of4": 1, "e2of4": 2, "e3of4": 3, "e4of4": 4}
    gallery_ids = {e["id"]: i for i, e in enumerate(g for g in gallery if g["id"] is not None)}
    images = []
    for i, img in enumerate(registry.images):
        if img is None:
            images.append(None)
            continue
        entry = dict(img)
        entry["gallery"] = gallery_ids.get(i)
        entry["ending"] = next((v for nm in img["names"] for k, v in ending_names.items() if nm == k), None)
        images.append(entry)
    entries = {n: {"chapter": project.label_chapter[n], "offset": layouts[project.label_chapter[n]][0][n]}
               for n in project.label_chapter if n.startswith("chapter_")}
    meta = {
        "chapters": [{"index": ch.index, "name": ch.name, "text_base": bases[ch.index],
                      "text_count": len(result.irs[ch.index].strings), "code_size": layouts[ch.index][1]} for ch in project.chapters]
                    + [{"index": story_index, "name": "STORY", "text_base": bases[story_index], "text_count": 0, "code_size": layouts[story_index][1]}],
        "entries": entries,
        "labels": {str(v): k for k, v in label_ids.items()},
        "speakers": project.speaker_info,
        "positions": project.position_info,
        "tags": {str(v): k for k, v in registry.tag_ids.items()},
        "vars": registry.vars,
        "audio": registry.audio,
        "images": images,
        "gallery": gallery,
        "extra_chapters": project.extra_chapters,
        "base_chapters": project.base_chapters,
        "ending_routes": project.ending_routes,
        "text_total": base,
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return project, registry, result


def main():
    project, registry, result = compile_all()
    for e in result.errors:
        print("ERROR", e)
    for w in sorted(set(result.warnings))[:40]:
        print("AVISO", w)
    if result.errors:
        return 1
    total = sum(len(i.insts) for i in result.irs.values())
    print(f"capitulos: {len(result.irs)}  instrucciones: {total}  imagenes: {len(registry.images) - 1}  audio: {len(registry.audio)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
