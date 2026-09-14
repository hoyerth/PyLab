# -*- coding: utf-8 -*-
"""READ-ONLY: Knick-Forensik an K73 (P12 Decke) und K82 (P12 Boden).

Kein Schreiben, kein Patch: nur Vermessung von wicks/basis/basis_bei.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_knick", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
d = scan["d"]
ts = d["ts"].tolist()
n = scan["n"]
box_end = scan["box_end_bar"]

print(f"n={n} box_end={box_end}")
print(f"Bar 0   = {ts[0]}")
print(f"Bar {n - 1} = {ts[n - 1]}")
print()

ZIEL = {73: "P12 Decke (Upper2)", 82: "P12 Boden (Lower3)"}
kanten = list(scan["edges"]) + list(scan["seeds"])
for kid, name in ZIEL.items():
    e = next((x for x in kanten if x.kid == kid), None)
    if e is None:
        print(f"K{kid} ({name}): NICHT im Katalog")
        continue
    print(f"=== K{kid}  {name} ===")
    print(f"  seite={e.seite} geburts_bar={e.geburts_bar} "
          f"({ts[e.geburts_bar]}) status={e.status}")
    print(f"  ist_prim_anker={e.ist_prim_anker} "
          f"erster_pivot_bar={e.erster_pivot_bar} "
          f"promoviert_ab_bar={e.promoviert_ab_bar}")
    print(f"  basis (Feld)      = {e.basis:.4f}")
    print(f"  mean(wicks)       = "
          f"{sum(p for _, p in e.wicks) / len(e.wicks):.4f}   "
          f"(n wicks={len(e.wicks)})")
    print("  Touches (kausal, pivot_bar + 2 bestaetigt):")
    for i, (b, px) in enumerate(e.wicks):
        print(f"    #{i + 1}  bar {b:4d}  {ts[b]}  "
              f"px={px:.4f}  bestaetigt ab bar {b + 2} "
              f"({ts[b + 2] if b + 2 < n else '-'})")
    print("  basis_bei(k) an den Touch-Bestaetigungsbars (Treppe/Knicke):")
    prev = None
    for b, _px in e.wicks:
        k = b + 2
        if k >= n:
            continue
        v = e.basis_bei(k)
        mark = "" if prev is None or abs(v - prev) < 1e-12 else "  <== SPRUNG"
        print(f"    k={k:4d} {ts[k]}  basis_bei={v:.4f}{mark}")
        prev = v
    if e.wicks:
        kb = e.wicks[-1][0] + 2
        print(f"  Endwert bei Fensterende: basis_bei({n - 1})="
              f"{e.basis_bei(n - 1):.4f}")

print()
print("=== Benannte Marken des Anwenders (Datum -> Bar) ===")
MARKEN = [
    ("25.8. 04:45", "2026-08-25 04:45"), ("25.8. 11:00", "2026-08-25 11:00"),
    ("25.8. 15:00", "2026-08-25 15:00"), ("25.8. 15:45", "2026-08-25 15:45"),
    ("26.8. 04:30", "2026-08-26 04:30"), ("26.8. 17:00", "2026-08-26 17:00"),
    ("27.8. 03:45", "2026-08-27 03:45"), ("27.8. 15:45", "2026-08-27 15:45"),
    ("27.8. 19:00", "2026-08-27 19:00"),
]
for label, iso in MARKEN:
    hit = next(((i, t) for i, t in enumerate(ts) if str(t).startswith(iso)),
               None)
    if hit is None:
        print(f"  {label:14s} -> kein Bar gefunden ({iso})")
        continue
    i, t = hit
    print(f"  {label:14s} -> bar {i:4d}  {t}  "
          f"hi={d['high'].iloc[i]:.4f} lo={d['low'].iloc[i]:.4f} "
          f"cl={d['close'].iloc[i]:.4f}")
sys.exit(0)
