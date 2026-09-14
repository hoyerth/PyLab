# -*- coding: utf-8 -*-
"""PHASE 2.1 (read-only) -- Rollenrang von K67/K82 + Lookahead-Nachweis."""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location(
    "_rl", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["_rl"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX = scan["box_end_bar"]
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].to_numpy()
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
seite_edges = {"OBEN": [e for e in alle if e.seite == "OBEN"],
               "UNTEN": [e for e in alle if e.seite == "UNTEN"]}


def exists(e, k):
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


def rang(k, seite, kid):
    c = [e for e in seite_edges[seite] if exists(e, k)]
    c.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
    for i, e in enumerate(c):
        if e.kid == kid:
            return i, len(c)
    return None, len(c)


print("=" * 100)
print("PHASE 2.1a -- Rollenrang von K67 (OBEN) und K82 (UNTEN), Bars 1021..1287")
print("=" * 100)
for kid, seite in ((67, "OBEN"), (82, "UNTEN")):
    rs = [rang(k, seite, kid)[0] for k in range(1021, n)]
    c = Counter(r for r in rs if r is not None)
    none_cnt = sum(1 for r in rs if r is None)
    print(f"   K{kid} ({seite}): nicht existent {none_cnt} Bars")
    print(f"      Rangang-Verteilung (Rang: Bars): "
          f"{sorted(c.items())[:12]}")
    if rs[0] is not None:
        print(f"      Rang bei 1021 = {rs[0]}  | bei {n - 1} = {rs[-1]}")
print()

print("=" * 100)
print("PHASE 2.1b -- LOOKAHEAD-NACHWEIS fuer Nenner (70.0000 - 62.5480)")
print("=" * 100)
hi_arg = int(np.argmax(hi))
lo_arg = int(np.argmin(lo))
print(f"   Fenster-Hoch  {hi[hi_arg]:.4f} @ Bar {hi_arg} "
      f"({np.datetime64(ts[hi_arg], 'm')}) -> "
      f"{'BOX (kausal)' if hi_arg < BOX else '*** H2 -> LOOKAHEAD ***'}")
print(f"   Fenster-Tief  {lo[lo_arg]:.4f} @ Bar {lo_arg} "
      f"({np.datetime64(ts[lo_arg], 'm')}) -> "
      f"{'BOX (kausal)' if lo_arg < BOX else '*** H2 -> LOOKAHEAD ***'}")
print()
box_hi, box_lo = float(np.max(hi[:BOX])), float(np.min(lo[:BOX]))
print(f"   BOX-only [0,{BOX}): Hoch {box_hi:.4f} Tief {box_lo:.4f} "
      f"Range {box_hi - box_lo:.4f}")
h1_hi = int(np.argmax(hi[:BOX]))
h1_lo = int(np.argmin(lo[:BOX]))
print(f"      Box-Hoch @ Bar {h1_hi} ({np.datetime64(ts[h1_hi], 'm')}), "
      f"Box-Tief @ Bar {h1_lo} ({np.datetime64(ts[h1_lo], 'm')})")
print()

print("=" * 100)
print("PHASE 2.1c -- Kausaler Faktor fuer JEDEN H2-Signalbar (rolling Box)")
print("=" * 100)
print("   Faktor(k) = (max hi[0..k] - min lo[0..k]) / (Box-Range bei 643)")
basis_nenner = float(np.max(hi[:BOX]) - np.min(lo[:BOX]))
for k in (644, 1021, 1075, 1122, 1272, 1287):
    num = float(np.max(hi[:k + 1]) - np.min(lo[:k + 1]))
    print(f"   k={k:>5}  Range[0..k]={num:>8.4f}  Faktor={num / basis_nenner:>7.4f}")
print()
print("   Vergleich der drei Nenner-Kandidaten:")
print("      Box-Range [0,644)              = "
      f"{float(np.max(hi[:BOX]) - np.min(lo[:BOX])):.4f}")
ex_o = [e for e in seite_edges['OBEN'] if exists(e, BOX - 1)]
ex_u = [e for e in seite_edges['UNTEN'] if exists(e, BOX - 1)]
ex_o.sort(key=lambda e: e.basis_bei(BOX - 1), reverse=True)
ex_u.sort(key=lambda e: e.basis_bei(BOX - 1))
print(f"      Kantenbasen bei Bar {BOX - 1}       = "
      f"{ex_o[0].basis_bei(BOX - 1) - ex_u[0].basis_bei(BOX - 1):.4f}")
print("      Fenster (enthaelt H2!)         = 7.4520  *** LOOKAHEAD ***")
