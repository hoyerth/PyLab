# -*- coding: utf-8 -*-
"""Read-only Probe: Kantenzahl + Laufzeit der Kalibrierungs-Primitive."""
from __future__ import annotations

import importlib.util
import pickle
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg = eng.StraightEdgeHarnessKonfiguration()

scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
alle = list(scan["edges"]) + list(scan["seeds"])
print("keys       :", list(scan.keys()))
print("edges/seeds:", len(scan["edges"]), len(scan["seeds"]), "->", len(alle))
e = alle[0]
print("attrs      :", [x for x in dir(e) if not x.startswith("_")])
print("wall_live_bars:", cfg.wall_live_bars)

d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
N = scan["n"]
SPLIT = 17692

t0 = time.time()
for k in range(SPLIT, N):
    kausal = [x for x in alle if x.erster_pivot_bar + 2 <= k + 1]
print(f"kausal-Schleife {N - SPLIT} Bars: {time.time() - t0:.2f}s "
      f"(letzte kausal {len(kausal)})")

t0 = time.time()
for k in range(SPLIT, N):
    kausal = [x for x in alle if x.erster_pivot_bar + 2 <= k + 1]
    a = max(0, k - 960 + 1)
    hl, ll = float(hi[a:k + 1].max()), float(lo[a:k + 1].min())
    ob = un = None
    for x in kausal:
        bars = [b for b, _ in x.wicks if b <= k]
        if not bars or max(bars) < k - cfg.wall_live_bars:
            continue
        if not (ll <= x.basis <= hl):
            continue
        if x.seite == "OBEN" and (ob is None or x.basis > ob.basis):
            ob = x
        elif x.seite == "UNTEN" and (un is None or x.basis < un.basis):
            un = x
print(f"L960-Paar Schleife: {time.time() - t0:.2f}s")

t0 = time.time()
for k in range(SPLIT, N):
    a = max(0, k - 480)
    out = []
    for x in alle:
        pb = x.erster_pivot_bar
        if a <= pb <= k and x.ist_aktiv_bei(k) and x.erster_pivot_bar + 2 <= k + 1 \
                and x.touch_conf(k) >= 3:
            out.append(x)
print(f"pivots_im_fenster Schleife: {time.time() - t0:.2f}s "
      f"(letzte {len(out)})")
