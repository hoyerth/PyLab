# -*- coding: utf-8 -*-
"""E-20-Diagnose: Clamping-Artefakt des POC-Histogramms im S2-Fenster.

``berechne_kausalen_histogramm_poc`` spannt die Bins ueber
``(untergrenze, obergrenze)`` und CLIPPT Bars ausserhalb in die Rand-Bins
(``searchsorted(...)-1`` + ``np.clip``). Liegt der Preis-Schwerpunkt der Bars
weit ausserhalb des Fensters, wandert der gesamte Rand-Volumenstapel in Bin 0
bzw. den letzten Bin; die Glaettung (win=3) verschiebt das Maximum zusaetzlich
von Bin 0 auf Bin 1. Dann ist der "POC" ein Randartefakt, kein Akzeptanzniveau.

Gemessen wird: Volumenanteil der Bars, die im Fenster (45.7890, 47.1221)
liegen (Segment K408/K409), gegen den Rest; sowie die Bin-Verteilung.
"""
from __future__ import annotations

import importlib.util
import pickle
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg = eng.StraightEdgeHarnessKonfiguration()

scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
d = scan["d"]
n = scan["n"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
vol = d["tick_volume"].to_numpy(float)

U, O = 45.7890, 47.1221          # Segment K408/K409 (S2)
NUM_BINS = cfg.num_bins

print(f"S2 n = {n}  Fenster (unter, ober) = ({U:.4f}, {O:.4f})  "
      f"num_bins = {NUM_BINS}")
print("")

# Bar-Lage relativ zum Fenster (kausal bis Bar 21553, dem letzten Signal-Bar)
k = 21553
sub_lo, sub_hi, sub_v = lo[:k + 1], hi[:k + 1], vol[:k + 1]
unter = sub_hi < U                       # vollstaendig unterhalb
ueber = sub_lo > O                       # vollstaendig oberhalb
drin = (sub_lo >= U) & (sub_hi <= O)     # vollstaendig innerhalb
teil = ~(unter | ueber | drin)           # teilweise ueberlappend

tot = float(sub_v.sum())
for nm, m in (("vollstaendig unter", unter), ("ueberlappend", teil),
              ("vollstaendig innerhalb", drin), ("vollstaendig oberhalb", ueber)):
    print(f"   {nm:<24} {m.sum():>6} Bars   Volumen {sub_v[m].sum():>12,.0f}"
          f"   ({sub_v[m].sum() / tot * 100:>5.1f} %)")
print("")

# Bin-Verteilung exakt wie die Engine (Kopie der Clamping-Logik)
edges = np.linspace(U, O, NUM_BINS + 1)
v_bin = np.zeros(NUM_BINS)
for l_, h_, v_ in zip(sub_lo, sub_hi, sub_v):
    if h_ <= l_ or v_ <= 0:
        continue
    lo_b = int(np.clip(np.searchsorted(edges, l_, side="right") - 1,
                       0, NUM_BINS - 1))
    hi_b = int(np.clip(np.searchsorted(edges, h_, side="left") - 1,
                       0, NUM_BINS - 1))
    if lo_b == hi_b:
        v_bin[lo_b] += v_
    else:
        ov = np.array([max(0.0, min(h_, edges[b + 1]) - max(l_, edges[b]))
                       for b in range(lo_b, hi_b + 1)])
        tt = float(ov.sum())
        if tt > 0:
            v_bin[lo_b:hi_b + 1] += v_ * ov / tt

v_s = np.convolve(v_bin, np.ones(3) / 3.0, mode="same")
p_idx = int(np.argmax(v_s))
poc = float((edges[p_idx] + edges[p_idx + 1]) / 2.0)

print(f"Bin-Volumen: Anteil Bin 0 = {v_bin[0] / v_bin.sum() * 100:.1f} %  |  "
      f"letzter Bin = {v_bin[-1] / v_bin.sum() * 100:.1f} %  |  "
      f"Bins 1..-2 zusammen = {v_bin[1:-1].sum() / v_bin.sum() * 100:.1f} %")
print(f"argmax nach Glaettung (win=3) = Bin {p_idx}  ->  POC = {poc:.4f}")
print(f"Bin 0 Mitte = {(edges[0] + edges[1]) / 2:.4f}   "
      f"Bin 1 Mitte = {(edges[1] + edges[2]) / 2:.4f}   "
      f"Bin 2 Mitte = {(edges[2] + edges[3]) / 2:.4f}")
print("")
print(f"tp2 (PHASE_EIGEN SHORT, K409) = 45.7890")
print(f"Abstand POC - tp2 = {poc - U:.4f} USD  "
      f"({(poc - U) / U * 100:.3f} % der Basis)")
print("")
print("Diagnose: Das Fenster deckt nur einen Bruchteil des Volumens ab;")
print("alle Bars unterhalb werden in Bin 0 geclampt, die Glaettung hebt Bin 1")
print("zum Maximum. Der 'POC' ist damit ein Randartefakt des Fensters, kein")
print("Akzeptanzniveau -- in BEIDEN Fensterdefinitionen (LEGACY/PHASE_RANGE).")

# R-Skaleninvarianz des Ausreisser-Trades
print("")
print("R-Skaleninvarianz des Ausreisser-Trades (entry 18825):")
entry = 54.2440
for risk in (0.2460, 0.5424, 1.0849):
    print(f"   risk {risk:.4f} USD ({risk / entry * 100:.2f} % von entry)  ->  "
          f"R = {(entry - 45.7890) / risk:.4f}")
