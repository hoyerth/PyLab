# -*- coding: utf-8 -*-
"""READ-ONLY H1-Forensik: K20 vs. K31 an 12.08. / 17.08. / 18.08. + Datums-Achse.

WICHTIG: Kein Engine-Import, kein _se_scan, kein _se_trades, kein Compile.
Es wird ausschliesslich die GEOMETRIE aus der DB nachgerechnet (Basis,
Distanz, Touch-Zahl, Alter) -- die Kanten-Daten stammen aus dem Audit-Bericht
test/tmp_v3_straight_edge_harness_AUG.txt (Wick-Bars).

Audit-Referenz (Box-Lauf):
  K 20 OBEN basis= 66.459 geb= 529 n=3 wicks=[107,529,565]   (Primaer-Anker, promo_ab=229)
  K 31 OBEN basis= 66.360 geb= 249 n=5 wicks=[237,249,286,536 (+1 n.Box)]
Gesperrte Setups (Audit):
  ZYKLUS   : bar 530 K31 (Abstand 1 < 12), bar 531 K31 (Abstand 2 < 12)
  STACKING : bar 242 K20 (Pos 231 offen bis 398), bar 244 K20, bar 564 K31 (Pos 531 offen bis 639)
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
    SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
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
n = len(d)


def t(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m %H:%M")


BAND = 0.12
MAXSWEEP = 0.60
MINALTER = 24

# --- Kanten aus dem Audit-Bericht ----------------------------------------
K20_WICKS = [107, 529, 565]
K31_WICKS = [237, 249, 286, 536]
K20_BASIS_FROZEN = 66.459          # Primaer-Anker ab promo_ab=229
K20_PROMO = 229


def basis_bei(wicks, k, frozen=None):
    """Kausale Mittel-Basis (b+2 <= k); vor dem 1. Docht: dessen Preis."""
    if frozen is not None:
        return frozen
    px = [hi[b] for b in wicks if b + 2 <= k]
    return float(np.mean(px)) if px else float(hi[min(wicks)])


def touch_conf(wicks, k):
    return sum(1 for b in wicks if b + 2 <= k)


print("=" * 108)
print("0) WICK-PREISE (aus DB) und Basis-Verlaeufe")
print("=" * 108)
for name, wl in (("K20", K20_WICKS), ("K31", K31_WICKS)):
    print(f"  {name}: " + ", ".join(f"bar {b} ({t(b)}) high={hi[b]:.3f}"
                                   for b in wl))
print(f"  K20 frozen basis (ab promo {K20_PROMO}) = {K20_BASIS_FROZEN:.3f}")
print(f"  K20 vor Promotion: basis_bei = high[107] = {hi[107]:.3f}")
print(f"  K31 basis_bei(529) = mean(high[237],high[249],high[286]) = "
      f"{np.mean([hi[237], hi[249], hi[286]]):.3f}")

print("")
print("=" * 108)
print("1) BAR 229 (12.08.) -- der K20-Trade und die Kaskade")
print("=" * 108)
for k in (229, 242, 244):
    b20 = K20_BASIS_FROZEN if k >= K20_PROMO else hi[107]
    b31 = basis_bei(K31_WICKS, k)
    d20 = (hi[k] - b20) / b20 * 100.0
    d31 = (hi[k] - b31) / b31 * 100.0
    print(f"  bar {k:4d} ({t(k)}) high={hi[k]:.3f} close={cl[k]:.3f}")
    print(f"      K20 basis={b20:.3f} dist={d20:+.4f}% touch_conf="
          f"{touch_conf(K20_WICKS, k)} etabliert={k - 107 >= MINALTER} "
          f"{'IN-BAND (<=0.12) -> Skip' if d20 <= BAND else 'Kandidat (pos 0)'}")
    print(f"      K31 basis={b31:.3f} dist={d31:+.4f}% touch_conf="
          f"{touch_conf(K31_WICKS, k)} etabliert={k - 237 >= MINALTER}")

print("")
print("=" * 108)
print("2) 12.08. (Bars 184-275): ALLE Bars mit high > K20-Basis und Close zurueck")
print("=" * 108)
print(f"  {'bar':>5} {'zeit':>12} {'high':>8} {'close':>8} {'d20%':>8} {'d31%':>8} "
      f"{'K20-Sweep':>10} {'K31-Sweep':>10}")
for k in range(184, 276):
    b20 = K20_BASIS_FROZEN if k >= K20_PROMO else hi[107]
    b31 = basis_bei(K31_WICKS, k)
    d20 = (hi[k] - b20) / b20 * 100.0
    d31 = (hi[k] - b31) / b31 * 100.0
    s20 = hi[k] > b20 and BAND < d20 <= MAXSWEEP and cl[k] <= b20
    s31 = hi[k] > b31 and BAND < d31 <= MAXSWEEP and cl[k] <= b31
    if s20 or s31 or d20 > BAND or d31 > BAND:
        print(f"  {k:5d} {t(k):>12} {hi[k]:8.3f} {cl[k]:8.3f} {d20:+8.4f} "
              f"{d31:+8.4f} {str(s20):>10} {str(s31):>10}")

print("")
print("=" * 108)
print("3) 17.08./18.08. (Bars 460-643): ALLE Bars mit high > K20-Basis")
print("=" * 108)
print(f"  {'bar':>5} {'zeit':>12} {'high':>8} {'close':>8} {'d20%':>8} {'d31%':>8} "
      f"{'K20-Sweep':>10} {'K31-Sweep':>10}")
for k in range(460, 644):
    b20 = K20_BASIS_FROZEN
    b31 = basis_bei(K31_WICKS, k)
    d20 = (hi[k] - b20) / b20 * 100.0
    d31 = (hi[k] - b31) / b31 * 100.0
    s20 = hi[k] > b20 and BAND < d20 <= MAXSWEEP and cl[k] <= b20
    s31 = hi[k] > b31 and BAND < d31 <= MAXSWEEP and cl[k] <= b31
    if s20 or s31:
        print(f"  {k:5d} {t(k):>12} {hi[k]:8.3f} {cl[k]:8.3f} {d20:+8.4f} "
              f"{d31:+8.4f} {str(s20):>10} {str(s31):>10}")

print("")
print("=" * 108)
print("4) PNG-DATUMS-ACHSE: wie werden die 9 Ticks gesetzt?")
print("=" * 108)
ticks = np.linspace(0, n - 1, 9).astype(int)
print(f"  Code: ticks = np.linspace(0, n-1, 9).astype(int)  (n={n})")
print(f"  {'idx':>5} {'Label':>8} {'tatsaechliche Zeit':>20} {'Uhrzeit':>8} "
      f"{'Offset zur Tagesgrenze':>24}")
for i in ticks:
    tt = ts.iloc[i]
    tagesgrenze = tt.normalize()
    offs = (tt - tagesgrenze).total_seconds() / 3600.0
    print(f"  {i:5d} {tt.strftime('%d.%m'):>8} {str(tt):>20} "
          f"{tt.strftime('%H:%M'):>8} {offs:>21.1f} h")

print("")
print("  -> Tagesgrenzen (00:00) liegen bei:")
for day in sorted(set(ts.dt.date)):
    idx = int(np.argmax((ts.dt.date == day).to_numpy()))
    print(f"     {day}  Bar {idx:4d}")
