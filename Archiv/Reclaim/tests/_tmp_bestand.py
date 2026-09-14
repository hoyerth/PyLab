# -*- coding: utf-8 -*-
"""Bestandsaufnahme: was gehoert zu Reclaim, was zu anderen Themen?

Read-only. Erzeugt keine Datei, verschiebt nichts.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test"

# --- Themensignaturen --------------------------------------------------------
# Reihenfolge = Prioritaet (erster Treffer gewinnt).
THEMEN = [
    ("SETUP_C",   r"setup_c|setup-c|_sc_"),
    ("COUNTER",   r"counter_engine|counter_|counte"),
    ("MAKRO",     r"makro|macro_|brent|eco"),
    ("SILVER",    r"silver|regime|phasen_volumen|volumen_profil|schwellen"),
    ("ZEITBASIS", r"zeitbasis|zeitkanon|zeitcheck|zeitzone|dst_|bkz"),
    ("DB_UI",     r"\bdb_|_db|duckdb|sqlite|_ui|marimo|_ts_|lab_"),
    ("RECLAIM",   r"rec?laim|kanten|straight_edge|_se_|segmentwand|q29|e34|gegenkante|"
                  r"kandidat|genese|genesis|sweep|wick|m6|hook|v01[789]|v02[012]|"
                  r"k4_|kid|zyklus|blocker|quartil|zulassung|funnel|trichter|"
                  r"anker|pivot|kante|kante_|kanten_engine|sichttest|sl_|tp[12]|"
                  r"trailing|alpha|capitulation|loss|consecutive|pullback|swing|"
                  r"avwap|vvwap|vwap|doku|commit_msg|handoff|section|patch|"
                  r"probe|sond|verify|audit|append|forensik|trace|diff|recon|"
                  r"patch|spec|sollwert|matrix|lauf|out$|console$"),
]

C_THEMEN = [(n, re.compile(p, re.I)) for n, p in THEMEN]


def klass(name: str) -> str:
    for n, rx in C_THEMEN:
        if rx.search(name):
            return n
    return "UNKLASSIFIZIERT"


def main() -> None:
    print("=" * 96)
    print("BESTANDSANFNAHME test/ -- Zuordnung zu Themen")
    print("=" * 96)

    gruppen: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(TEST.rglob("*")):
        if p.is_file():
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(TEST)
            gruppen[klass(rel.as_posix())].append(p)

    print(f"{'Thema':<18} {'Dateien':>8} {'Bytes':>14}   {'Top-Unterordner'}")
    print("-" * 96)
    for n in [t[0] for t in THEMEN] + ["UNKLASSIFIZIERT"]:
        fs = gruppen.get(n, [])
        if not fs:
            continue
        b = sum(f.stat().st_size for f in fs)
        ordner = Counter((f.relative_to(TEST).parts[0]
                          if len(f.relative_to(TEST).parts) > 1 else "(lose)")
                         for f in fs)
        top = ", ".join(f"{k}:{v}" for k, v in ordner.most_common(5))
        print(f"{n:<18} {len(fs):>8} {b:>14,}   {top}")

    print()
    print("=" * 96)
    print("TEST-SUBFOLDER (organische Themeninseln)")
    print("=" * 96)
    for d in sorted(x for x in TEST.iterdir() if x.is_dir()):
        fs = [f for f in d.rglob("*") if f.is_file()]
        if not fs:
            continue
        b = sum(f.stat().st_size for f in fs)
        n = d.name
        th = klass(n + "/x")
        print(f"  {n:<26} {len(fs):>5} Dateien  {b:>13,} B   Thema-Signatur: {th}")

    print()
    print("=" * 96)
    print(f"SUMME test/ ohne __pycache__: "
          f"{sum(len(v) for v in gruppen.values())} Dateien, "
          f"{sum(f.stat().st_size for v in gruppen.values() for f in v):,} B")
    print("=" * 96)


if __name__ == "__main__":
    main()
