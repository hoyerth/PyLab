# test/_aufraeumen_apply.py
"""Fuehrt die Aufraeumaktion aus (verschieben, NICHT loeschen).

- nutzt denselben Klassifikator wie ``_aufraeumen_plan.py``
- legt Zielordner an, verschiebt Dateien, schreibt Manifest
  ``test/AUFRAEUMUNG_2026-09-10.md`` (alt -> neu, je Datei)
- kollisionsfrei: vorhandener Zielname wird nie ueberschrieben

Aufruf (Projekt-Root):  .venv\\Scripts\\python.exe test\\_aufraeumen_apply.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST))

import _aufraeumen_plan as plan  # noqa: E402

ORDNER = ("setup_c", "counter_engine", "silver_regime", "reclaim_live",
          "kanten_engine", "trash")
EIGENE_TOOLS = {"_aufraeumen_plan.py", "_aufraeumen_apply.py",
                "_aufraeumen_plan.tsv", "_tmp_cleanup_inventory.txt"}


def main() -> None:
    dateien = sorted(p.name for p in TEST.iterdir() if p.is_file())
    zuordnung = {n: plan.klassifiziere(n, plan.baustein(n)) for n in dateien}

    verschiebungen: list[tuple[str, str]] = []
    for n in dateien:
        ziel = zuordnung[n]
        if ziel == "<root>" or n in EIGENE_TOOLS:
            continue
        zieldir = TEST / ziel
        zieldir.mkdir(parents=True, exist_ok=True)
        zielpfad = zieldir / n
        if zielpfad.exists():
            print(f"KOLLISION - uebersprungen: {n}")
            continue
        shutil.move(str(TEST / n), str(zielpfad))
        verschiebungen.append((n, f"{ziel}/{n}"))

    # __pycache__ als Ordner
    pyc = TEST / "__pycache__"
    if pyc.is_dir():
        (TEST / "trash" / "pycache_test").mkdir(parents=True, exist_ok=True)
        for p in pyc.iterdir():
            shutil.move(str(p), str(TEST / "trash" / "pycache_test" / p.name))
        pyc.rmdir()
        verschiebungen.append(("__pycache__/", "trash/pycache_test/"))

    b = {}
    for _, neu in verschiebungen:
        b[neu.split("/")[0]] = b.get(neu.split("/")[0], 0) + 1
    print(f"\nverschoben: {len(verschiebungen)} Dateien")
    for k, v in sorted(b.items()):
        print(f"  {k:16s} {v:4d}")

    zeilen = [
        "# AUFRAEUMUNG test/ - 2026-09-10",
        "",
        "Aktion: **nur verschoben, nichts geloescht**. Jede Zeile = alte -> neue",
        "Position (relativ zu `test/`). Skripte mit `ROOT = parent.parent`",
        "muessen beim erneuten Lauf um eine Ebene angepasst werden.",
        "",
        f"Verschobene Dateien: **{len(verschiebungen)}**",
        "",
        "| alt | neu |",
        "|---|---|",
    ]
    zeilen += [f"| `{alt}` | `{neu}` |" for alt, neu in verschiebungen]
    (TEST / "AUFRAEUMUNG_2026-09-10.md").write_text(
        "\n".join(zeilen) + "\n", encoding="utf-8")
    print("\nManifest: test/AUFRAEUMUNG_2026-09-10.md")


if __name__ == "__main__":
    main()
