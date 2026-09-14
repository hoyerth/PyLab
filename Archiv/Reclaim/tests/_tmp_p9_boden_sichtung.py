# -*- coding: utf-8 -*-
"""READ-ONLY Sichtung: Bars 990..1015, Reclaim-Kriterien an 68.4000, P9-Extrema.

Quelle: test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv (UTC, ohne Offset).
Keine Engine-, Adapter- oder Spez-Aenderung. Keine Datei wird geschrieben.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "test" / "archiv" / "silver_m15_ohlc_2026-08-10_2026-08-28.csv"

zeilen = CSV.read_text(encoding="utf-8-sig").splitlines()
rows = [z.split(",") for z in zeilen[1:] if z.strip()]
O = [float(r[1]) for r in rows]
H = [float(r[2]) for r in rows]
L = [float(r[3]) for r in rows]
C = [float(r[4]) for r in rows]
V = [float(r[5]) for r in rows]
TS = [r[0] for r in rows]
n = len(rows)
print(f"n = {n} | Spanne {TS[0]} .. {TS[-1]} | Kurse {min(L):.3f} .. {max(H):.3f}")

print("\n=== S1) BARS 990..1015 (Rohdaten, UTC = Wanduhr der DB) ===")
print(" Bar | ts               |    O      H      L      C    V  | "
      "L<68.40 C>68.40")
for k in range(990, 1016):
    m1 = "T" if L[k] < 68.40 else "."
    m2 = "T" if C[k] > 68.40 else "."
    print(f"{k:4d} | {TS[k]} | {O[k]:6.3f} {H[k]:6.3f} {L[k]:6.3f} {C[k]:6.3f} "
          f"{V[k]:5.0f} |   {m1}      {m2}")

print("\n=== S2) P9-FENSTER 848..1020 (Adapternaehe) ===")
seg = range(848, 1021)
lo_min = min(L[i] for i in seg)
hi_max = max(H[i] for i in seg)
b_lo = [i for i in seg if L[i] == lo_min][0]
b_hi = [i for i in seg if H[i] == hi_max][0]
print(f"  min low  = {lo_min:.4f} @ bar {b_lo}  ({TS[b_lo]})")
print(f"  max high = {hi_max:.4f} @ bar {b_hi}  ({TS[b_hi]})")
print(f"  Spanne (roh)      = {hi_max - lo_min:.4f}")
print(f"  Spanne (68.40..69.87) = {69.8700 - 68.4000:.4f}")
print(f"  Long-Band global  = <= {62.548 + 0.25 * (70.0 - 62.548):.4f}")
print(f"  Long-Band phasen  = <= {68.4000 + 0.25 * (69.8700 - 68.4000):.4f}")

print("\n=== S3) ALLE BARS MIT LOW < 68.4000 IM P9-FENSTER ===")
for k in seg:
    if L[k] < 68.40:
        print(f"  bar {k:4d}  {TS[k]}  L {L[k]:.4f}  C {C[k]:.4f}  "
              f"V {V[k]:.0f}  {'RECLAIM in-bar' if C[k] > 68.40 else 'unter Niveau'}")

print("\n=== S4) RECLAIM-KRITERIEN NACH DEM EXTREMTIEF ===")
print("  Stufe 1 (in-bar): L < 68.4000 UND C > 68.4000")
s1 = [k for k in range(848, 1021) if L[k] < 68.40 and C[k] > 68.40]
print(f"    {[(k, TS[k]) for k in s1]}")
print("  Stufe 2 (Folgekerze): C[k-1] > 68.40 UND C[k] > 68.40")
s2 = [k for k in range(849, 1021) if C[k] > 68.40 and C[k - 1] > 68.40]
print(f"    erste 12: {[(k, TS[k]) for k in s2[:12]]}")
print("  Erster Bar mit C > 68.4000 nach dem Extremtief:")
for k in range(b_lo, 1021):
    if C[k] > 68.40:
        print(f"    bar {k}  {TS[k]}  C {C[k]:.4f}  (Abstand zum Tief "
              f"{k - b_lo} Bars)")
        break

print("\n=== S5) SL-KANDIDATEN DER RECLAIM-SERIE ===")
print(f"  68.318 - 0.05 = {68.318 - 0.05:.4f}   (Anwender-Vorschlag, "
      f"bezieht sich auf Bar 999)")
print(f"  68.288 - 0.05 = {68.288 - 0.05:.4f}   (Bar 1000 = tatsaechliches "
      f"P9-Tief)")
sl = 68.288 - 0.05
tp = 69.8700
risiko = (68.40 - sl)
print(f"  Risiko bei Entry 68.4000 auf SL {sl:.4f} = {risiko:.4f} USD")
print(f"  Chance bis 69.8700                  = {tp - 68.40:.4f} USD "
      f"-> CRV {(tp - 68.40) / risiko:.2f}")

print("\n=== S6) LOKALE EXTREMA 988..1012 (Pivot-Rohsicht, 2er-Fenster) ===")
for k in range(990, 1013):
    ist_lo = L[k] < L[k - 1] and L[k] < L[k + 1]
    ist_hi = H[k] > H[k - 1] and H[k] > H[k + 1]
    tag = ("LOK-TIEF" if ist_lo else "") + ("/LOK-HOCH" if ist_hi else "")
    print(f"  bar {k:4d}  L {L[k]:7.3f}  H {H[k]:7.3f}  C {C[k]:7.3f}  {tag}")
