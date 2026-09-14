# -*- coding: utf-8 -*-
"""S4 -- READ-ONLY Reconnaissance: Zeitbasis-Delta der Peripherie vs. Kanon.

Kein Schreibzugriff auf Zieldateien. Erzeugt einen Befundbericht der
Zeit-bezogenen Fundstellen in ``backtest_lab/`` und ``algos/`` und
klassifiziert sie gegen ``docs/ZEITBASIS_KANON.md`` (BKZ = `time AT TIME ZONE
'UTC'` ist Rechenbasis; Europe/Berlin|Budapest nur Anzeige-Dublette).

Klassifikation je Trefferzeile:
  A  = Query/Rechenbasis konform (`AT TIME ZONE 'UTC'`, naive UTC)
  B  = Anzeige-Dublette (Europe/Budapest|Berlin -> nur Darstellung)
  C  = Roher/naiver Zeitzugriff ohne explizite BKZ-Formulierung (Pruefpunkt)
  D  = Sonstiges (Kommentar/Doc/Typ-Hinweis)
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DATEIEN = sorted(
    list((ROOT / "backtest_lab").glob("*.py"))
    + list((ROOT / "algos").glob("*.py"))
)

R_BASIS = re.compile(r"AT TIME ZONE\s+'UTC'|naive UTC|tz_localize\(\"UTC\"\)"
                     r"|tz_convert\(\"UTC\"\)|tz_convert\('UTC'\)", re.I)
R_ANZEIGE = re.compile(r"Europe/(Berlin|Budapest)|Anzeige", re.I)
R_TERM = re.compile(r"\bWanduhr\b", re.I)
R_ROH = re.compile(r"\"time\"(?!\s*AT TIME ZONE)|SELECT\s+time\b", re.I)
R_TS = re.compile(r"tz_localize|tz_convert|astimezone|ZoneInfo|datetime\.now"
                  r"|timezone\.utc", re.I)


def klass(zeile: str, in_doc: bool) -> str | None:
    if R_TERM.search(zeile):
        return "E:VERBOTEN(Wanduhr)"
    if R_ANZEIGE.search(zeile) and R_TS.search(zeile):
        return "B Anzeige-Dublette"
    if R_BASIS.search(zeile):
        return "A BKZ-konform"
    if R_ROH.search(zeile):
        return "C roher Zeitzugriff"
    if R_TS.search(zeile) or R_ANZEIGE.search(zeile):
        return "D Kontext (Doc/Typ)"
    return None


def main() -> int:
    gesamt: dict[str, int] = {}
    print("=" * 100)
    print("S4-RECON -- Zeitbasis-Delta backtest_lab/ + algos/ (READ-ONLY)")
    print("=" * 100)
    for p in DATEIEN:
        t = p.read_text(encoding="utf-8")
        # Docstring-Zeilenbereiche via AST bestimmen (Kontext-Heuristik).
        docs: set[int] = set()
        try:
            tree = ast.parse(t)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                    d = ast.get_docstring(node, clean=False)
                    if d and node.body:
                        docs.update(range(node.body[0].lineno,
                                          node.body[0].end_lineno or
                                          node.body[0].lineno))
        except SyntaxError:
            pass
        treffer = []
        for i, l in enumerate(t.split("\n"), 1):
            k = klass(l, i in docs)
            if k:
                treffer.append((i, k, l.rstrip()))
        if not treffer:
            continue
        print(f"\n--- {p.relative_to(ROOT)}  ({len(treffer)} Fundstellen) ---")
        for i, k, l in treffer:
            gesamt[k.split()[0]] = gesamt.get(k.split()[0], 0) + 1
            print(f"  {i:5} [{k}] {l.strip()[:120]}")
    print("\n" + "=" * 100)
    print("SUMME nach Klasse:", dict(sorted(gesamt.items())))
    print("=" * 100)
    _echte_befunde()
    return 0


# ---- Fokussierte Detektoren (echte Verstoss-Kandidaten, ohne Spaltenrauschen)
F_NAKED_SELECT = re.compile(r"SELECT\s+\"time\"\s*,", re.I)
F_OFFSET = re.compile(r"tz_offset_hours|Timedelta\(hours=")
F_NAIVE_TS = re.compile(r"pd\.Timestamp\([^)]*\)\.timestamp\(\)")


def _echte_befunde() -> None:
    """Meldet nur die kanon-relevanten Verstoss-Kandidaten."""
    print("\n" + "#" * 100)
    print("# ECHTE VERSTOSS-KANDIDATEN gegen ZEITBASIS_KANON (Rechenbasis/Achse)")
    print("#" * 100)
    zaehler = {"nacktes SELECT time": 0, "tz_offset_hours-Workaround": 0,
               "naiver .timestamp() (Maschinen-TZ)": 0}
    for p in DATEIEN:
        t = p.read_text(encoding="utf-8")
        for i, l in enumerate(t.split("\n"), 1):
            for name, rx in (("nacktes SELECT time", F_NAKED_SELECT),
                             ("tz_offset_hours-Workaround", F_OFFSET),
                             ("naiver .timestamp() (Maschinen-TZ)", F_NAIVE_TS)):
                if rx.search(l):
                    zaehler[name] += 1
                    print(f"  {p.relative_to(ROOT)}:{i}  [{name}]  {l.strip()[:100]}")
    print("\n  Kandidaten-Summe:", zaehler)
    print("  (Klassen A/B/D sind kanon-konform bzw. reine Anzeige/Doku.)")


if __name__ == "__main__":
    raise SystemExit(main())
