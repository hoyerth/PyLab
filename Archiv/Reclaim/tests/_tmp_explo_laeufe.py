# -*- coding: utf-8 -*-
"""READ-ONLY: Drei Referenzlaeufe des Renderers im Vollbild.

Zeigt je Lauf (V0 = ungepatchter Motor, V1_basis = Adapter v0.1,
V1_aktiv = V017) die vollstaendige Tradeliste mit Signal-/Entry-Bar, damit
sichtbar wird, ob der MOTOR selbst in der H2-Reststrecke (ab Bar 1021)
handeln wuerde oder erst der Adapter blockt.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]

mod = types.ModuleType("explo_laeufe")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_laeufe>", "exec"), ns)
sys.argv = _old

import pandas as pd  # noqa: E402

ts = pd.to_datetime(ns["scan"]["d"]["ts"])
box_end = ns["box_end"]

for lbl, titel in (("V0", "V0  ungepatchter Motor (kein Adapter)"),
                   ("V1_basis", "V1_basis  Adapter v0.1"),
                   ("V1_aktiv", "V1_aktiv  Adapter V017")):
    lst = ns[lbl]
    r = sum(t.r for t in lst)
    h2 = [t for t in lst if t.entry_bar >= box_end]
    print("=" * 100)
    print(f"{titel}: {len(lst)} Trades | R = {r:+.6f} | "
          f"H2 (entry_bar >= {box_end}): {len(h2)}")
    print("=" * 100)
    for t in sorted(lst, key=lambda x: x.bar):
        mark = "  <= H2" if t.entry_bar >= box_end else ""
        print(f"   K{t.kid:<3} {t.richtung:<5} signal {t.bar:<5} "
              f"{ts.iloc[t.bar]:%d.%m. %H:%M}  entry_bar {t.entry_bar:<5} "
              f"{t.stufe:<14} entry {t.entry:.4f} tp2 {t.tp2:.4f} "
              f"r {t.r:+.6f}{mark}")
    print()
