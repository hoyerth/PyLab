# -*- coding: utf-8 -*-
"""READ-ONLY H1-Forensik: Reclaim-Stufen an K20/K31 (12.08. + 17./18.08.).

Reine Geometrie-Nachrechnung der arretierten Regeln (Engine wird NICHT
importiert, kein Scan, kein Compile):
  _reclaim_stufe: dist_o = (hi[k]-basis)/basis*100
                  hi[k] > basis und band < dist_o <= 0.60
                  STUFE_1: cl[k] <= basis
                  STUFE_2: cl[k+1] <= basis und hi[k+1] <= hi[k]+0.01
                  STUFE_3: cl[k+2] <= basis und max(hi[k+1],hi[k+2]) <= hi[k]+0.01
  entry_bar = k + stufe_n ; reclaim_bar = entry_bar - 1
  Stacking : entry_bar <= letzter exit_final_bar derselben Kante -> Sperre
  Zyklus   : k - letzter_sweep_bar < 12 -> Sperre
"""
from __future__ import annotations

import io
import sys

import duckdb
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

con = duckdb.connect("data/market_data.duckdb", read_only=True)
d = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= DATE '2026-08-10'
      AND time AT TIME ZONE 'UTC' <= TIMESTAMP '2026-08-27 23:59:59'
    ORDER BY time
""").fetchdf()
con.close()

hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
op = d["open"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = pd.to_datetime(d["ts"])

BAND, MAXSW, PUFFER = 0.12, 0.60, 0.01
K20_W, K31_W = [107, 529, 565], [237, 249, 286, 536]
K20_FROZEN, K20_PROMO = 66.459, 229


def zeit(k):
    return ts.iloc[k].strftime("%d.%m %H:%M")


def basis20(k):
    return K20_FROZEN if k >= K20_PROMO else float(hi[107])


def basis31(k):
    px = [hi[b] for b in K31_W if b + 2 <= k]
    return float(np.mean(px)) if px else float(hi[237])


def stufe(k, basis):
    """Rekonstruktion von _reclaim_stufe (Seite OBEN)."""
    if k + 2 >= len(cl):
        return 0, "-"
    dist = (hi[k] - basis) / basis * 100.0
    if not (hi[k] > basis and BAND < dist <= MAXSW):
        return 0, "kein Durchstich"
    if cl[k] <= basis:
        return 1, "STUFE_1_IN_BAR"
    if cl[k + 1] <= basis and hi[k + 1] <= hi[k] + PUFFER:
        return 2, "STUFE_2_KERZE_2"
    if cl[k + 2] <= basis and max(hi[k + 1], hi[k + 2]) <= hi[k] + PUFFER:
        return 3, "STUFE_3_KERZE_3"
    return 0, "kein Reclaim (Close bleibt oben)"


def zeige(k0, k1, titel):
    print("=" * 126)
    print(titel)
    print("=" * 126)
    print(f"  {'bar':>5} {'zeit':>12} {'open':>8} {'high':>8} {'low':>8} {'close':>8} "
          f"{'B20':>8} {'d20%':>8} {'B31':>8} {'d31%':>8}  Kandidat/Stufe")
    for k in range(k0, k1 + 1):
        b20, b31 = basis20(k), basis31(k)
        d20 = (hi[k] - b20) / b20 * 100.0
        d31 = (hi[k] - b31) / b31 * 100.0
        info = ""
        if d20 > BAND and hi[k] > b20:
            s, nm = stufe(k, b20)
            info = f"K20 KANDIDAT -> {nm}" + (f" entry={k + s}" if s else "")
        elif abs(d20) <= BAND:
            info = "K20 IN-BAND (<=0.12%) -> Skip, Kaskade faellt nach innen"
            if d31 > BAND and hi[k] > b31:
                s, nm = stufe(k, b31)
                info += f" | K31 KANDIDAT -> {nm}" + (
                    f" entry={k + s}" if s else "")
        elif d20 < 0:
            info = "K20 nicht erreicht (dist < 0) -> kein Trade"
        print(f"  {k:5d} {zeit(k):>12} {op[k]:8.3f} {hi[k]:8.3f} {lo[k]:8.3f} "
              f"{cl[k]:8.3f} {b20:8.3f} {d20:+8.4f} {b31:8.3f} {d31:+8.4f}  {info}")
    print("")


zeige(226, 250, "A) 12.08.2026 (Bars 226-250) -- K20-Trade 229 + die 2 Reclaims 242/244")
zeige(525, 570, "B) 17.08./18.08.2026 (Bars 525-570) -- K20-Touches 529/565, K31-Trade 529")

print("=" * 126)
print("C) BLOCKER-RECHNUNG (aus Audit-Bericht: Positionen und Exit-Bars)")
print("=" * 126)
print("  Trade 229 SHORT K20: entry=231, H1=TP1@386  -> exit_final (Stacking-Text) = 398")
print("  Trade 529 SHORT K31: entry=531, H1=TP1@614  -> exit_final (Stacking-Text) = 639")
print("")
print("  12.08.: Setup bar 242 -> entry_bar 245 ; Setup bar 244 -> entry_bar 245")
print("          Stacking: entry 245 <= 398 (Position 231 offen) -> BEIDE GESPERRT")
print("          Zyklus  : 242-229 = 13 >= 12  -> NICHT die Ursache")
print("          Dedup   : beide Setups haetten entry_bar 245 -> max. 1 Trade")
print("")
print("  17.08.: Setup bar 529 -> K31 (K20 in-band) -> entry 531, GENOMMEN (+8.41R)")
print("  18.08.: Setup bar 565 -> entry waere 565+stufe; K31-Position 531 offen")
print("          bis 639 -> STACKING-SPERRE (Zyklus 565-529=36 >= 12)")
print("")
print("  K20-Promotion: bar 229, frozen basis = 66.459 (Basis des Referenz-Sweeps)")
print(f"  K20-Dochte nach Freeze: 529 -> {hi[529]:.3f} = {(hi[529] - 66.459) / 66.459 * 100:+.4f}% "
      f"(<= 0.12 -> in-band)")
print(f"                          565 -> {hi[565]:.3f} = {(hi[565] - 66.459) / 66.459 * 100:+.4f}% "
      f"(<= 0.12 -> in-band)")
print(f"  K20 braeuchte fuer einen Sweep: high > {66.459 * (1 + BAND / 100):.3f}")
print(f"  Hoechster Kurs NACH der Promotion: {hi[229:].max():.3f} "
      f"(Bar {229 + int(hi[229:].argmax())}, {zeit(229 + int(hi[229:].argmax()))})")
