"""Reporte de cobertura del simulador: build/reports/cobertura.md."""
from pathlib import Path

from tools.simulator.vm import explore

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "build" / "reports" / "cobertura.md"


def extras_available(endings_mask, bonus_mask, total=10):
    """Capitulos extra disponibles segun src/extra_chapters_menu.rpy (especificacion para el motor)."""
    if endings_mask == 0:
        return []
    menu = list(range(total))
    if endings_mask & 0b1111 != 0b1111:
        w = 4 - bin(endings_mask & 0b1111).count("1")
        for i in range(5, 5 - w, -1):
            menu.remove(i)
        for i in range(8, 8 - w, -1):
            menu.remove(i)
        menu.pop()
    elif bonus_mask != 0b111111111:
        menu.pop()
    return menu


def build_report(program, result=None):
    meta = program.meta
    starts = [(program.story_index, 0)]
    extra_entries = {}
    for name, entry in meta["entries"].items():
        if name.startswith("chapter_x"):
            starts.append((entry["chapter"], entry["offset"]))
            extra_entries[name] = entry
    cov = explore(program, starts)

    all_labels = {name for name in meta["labels"].values()}
    missing_labels = sorted(all_labels - cov.labels)
    text_total = meta["text_total"]
    missing_text = sorted(set(range(text_total)) - cov.text_ids)
    gallery = [g for g in meta["gallery"]]
    gallery_unreached = [g["name"] for g in gallery if g["id"] is None or g["id"] not in cov.images_shown]
    audio_unused = [i for i in range(len(meta["audio"])) if i not in cov.audio_played]
    bonus_expected = set(range(9))

    lines = ["# Cobertura del simulador", "", "Generado por `python -m tools.simulator --report`.", ""]
    lines += ["## Resumen", "", "| Dato | Valor |", "|---|---|",
              f"| Estados distintos explorados (en decisiones) | {cov.states} |",
              f"| Ejecuciones | {cov.runs} |",
              f"| Finales alcanzados | {sorted(cov.endings)} de [1, 2, 3, 4] |",
              f"| Capitulos extra desbloqueados (bits) | {sorted(cov.bonus)} de {sorted(bonus_expected)} |",
              f"| Etiquetas alcanzadas | {len(cov.labels)} de {len(all_labels)} |",
              f"| Lineas de texto vistas | {len(cov.text_ids)} de {text_total} |",
              f"| Imagenes mostradas | {len(cov.images_shown)} de {len(meta['images']) - 1} registradas |",
              f"| Elementos de galeria alcanzables | {len(gallery) - len(gallery_unreached)} de {len(gallery)} |",
              f"| Pistas/efectos usados | {len(cov.audio_played)} de {len(meta['audio'])} |",
              f"| Sprites simultaneos (maximo) | {cov.max_sprites} (limite 12; escena de multitud en x6) |",
              f"| Profundidad de CALL (maximo) | {cov.max_depth} (limite 8) |",
              f"| Pila de expresiones (maximo) | {cov.max_stack} (limite 16) |",
              f"| Errores | {len(cov.errors)} |", ""]
    if cov.errors:
        lines += ["### Errores", ""] + [f"- {e}" for e in cov.errors[:30]] + [""]
    lines += ["## Etiquetas no alcanzadas", ""] + ([f"- `{n}`" for n in missing_labels] or ["Ninguna."]) + [""]
    if missing_text:
        by_chapter = {}
        for gid in missing_text:
            for c in meta["chapters"]:
                if c["text_base"] <= gid < c["text_base"] + c["text_count"]:
                    by_chapter[c["name"]] = by_chapter.get(c["name"], 0) + 1
        lines += ["## Texto no alcanzado por capitulo", ""] + [f"- {k}: {v}" for k, v in by_chapter.items()] + [""]
    lines += ["## Galeria no alcanzable", ""] + ([f"- {n}" for n in gallery_unreached[:60]] or ["Ninguna."]) + [""]
    lines += ["## Extras (logica progresiva, D1)", "", "| Finales vistos | Extras disponibles (indices 0-9) |", "|---|---|"]
    for mask in (0b0000, 0b0001, 0b0011, 0b0111, 0b1111):
        lines.append(f"| {bin(mask)} | {extras_available(mask, 0)} |")
    lines.append(f"| 0b1111 y extras completos | {extras_available(0b1111, 0b111111111)} |")
    lines.append("")
    if result is not None:
        lines += ["## Compilacion", "", f"- Avisos: {len(set(result.warnings))}"]
        stats = getattr(result, "text_stats", None)
        if stats:
            lines.append(f"- Cadenas: {stats['strings']}; con mas de una pagina: {stats['multipage']}; opciones de menu con desborde: {stats['choice_overflow']}")
        lines += [""] + [f"  - {w}" for w in sorted(set(result.warnings))[:40]] + [""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return cov, lines
