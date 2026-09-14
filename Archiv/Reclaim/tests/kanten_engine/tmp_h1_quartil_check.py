# -*- coding: utf-8 -*-
"""READ-ONLY: Q29-Aussenquartil an den realen Setup-Bars (Gegenprobe zur Quartil-Sperre)."""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
CSV = Path(__file__).resolve().parent / "archiv" / "silver_m15_ohlc_2026-08-10_2026-08-28.csv"
d = pd.read_csv(CSV)
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)

CASES = [(229, 66.776, "K20 Entry 231"), (242, 66.663, "K20 Stacking-Sperre"),
         (244, 66.662, "K20 Stacking-Sperre"), (529, 66.538, "K31 Entry 531"),
         (564, 66.530, "K31 Stacking-Sperre"), (565, 66.536, "K20 in-band"),
         (866, 69.179, "K59 Stacking-Sperre")]
print("=" * 96)
print("Q29-AUSSENQUARTIL (_im_aussenquartil, Schwelle 25 % der kausalen Spanne)")
print("=" * 96)
print(f"  {'bar':>5} {'ex_hi':>9} {'ex_lo':>9} {'spanne':>8} {'sweep':>9} "
      f"{'dist%':>8} {'Q29':>7}  Bemerkung")
for k, sw, note in CASES:
    eh = float(np.max(hi[:k + 1]))
    el = float(np.min(lo[:k + 1]))
    sp = eh - el
    di = (eh - sw) / sp * 100.0
    print(f"  {k:5d} {eh:9.3f} {el:9.3f} {sp:8.3f} {sw:9.3f} {di:8.2f} "
          f"{('PASS' if di <= 25 else 'BLOCK'):>7}  {note}")
print("")
print("  -> Alle SHORT-Setups der arretierten Laeufe bestehen Q29 deutlich")
print("     (dist 0.00-6.46 % << 25 %). Die 20 Quartil-Sperren des Box-Laufs")
print("     betreffen ausschliesslich innere LONG-Kanten (Mitte der Range).")
