"""Read-only-Sondierung: Volumen-Verteilung an H-Pivots im AUG-Fenster.

Frage: Ab welchem Faktor (Pivot-Volumen / 20er-Durchschnitt) ist ein
Pivot-Volumen ein 'Volumen-Spike'? Basis: find_pivots-Identik (Lookback 2)
aus phasen_volumen_profil.py + echtes tick_volume aus DuckDB read_only.
Kein Produktivcode, keine Artefakt-Schreibzugriffe.
"""
import io
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# Daten laden (identisch zu load_data im Produktions-Skript)
con = duckdb.connect("data/market_data.duckdb", read_only=True)
d = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= DATE '2026-08-10'
      AND time AT TIME ZONE 'UTC' <  DATE '2026-08-28'
    ORDER BY time
""").fetchdf()
con.close()
d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
d = d.reset_index(drop=True)

# Pivot-Identik zu find_pivots(d, n=2)
h = d["high"].values.astype(float)
l = d["low"].values.astype(float)
n = 2
hi = pd.Series(h)
lo = pd.Series(l)
is_hi = ((hi == hi.rolling(2 * n + 1, center=True, min_periods=1).max())
         & (hi.shift(n) < h) & (hi.shift(-n) < h))
is_lo = ((lo == lo.rolling(2 * n + 1, center=True, min_periods=1).min())
         & (lo.shift(n) > l) & (lo.shift(-n) > l))
is_hi[:n] = False
is_hi[-n:] = False
is_lo[:n] = False
is_lo[-n:] = False

vol = d["tick_volume"].values.astype(float)
avg20 = pd.Series(vol).rolling(20, min_periods=5).mean().shift(1).values  # kausal: Mittel VOR der Bar

rows = []
for i in range(len(d)):
    if is_hi[i]:
        rows.append(("H", i, h[i], vol[i], avg20[i]))
    if is_lo[i]:
        rows.append(("L", i, l[i], vol[i], avg20[i]))

pv = pd.DataFrame(rows, columns=["typ", "bar", "price", "vol", "avg20"])
pv["ratio"] = pv["vol"] / pv["avg20"].replace(0, np.nan)
print(f"Pivots gesamt: {len(pv)} (H {int((pv['typ']=='H').sum())}, "
      f"L {int((pv['typ']=='L').sum())})")
print(f"avg20 NaN-Faelle (Fruehphase): {int(pv['avg20'].isna().sum())}")

for t in ("H", "L"):
    sub = pv[(pv["typ"] == t) & pv["ratio"].notna()]
    r = sub["ratio"]
    print(f"\n--- {t}-Pivots (n={len(sub)}): ratio = Vol / avg20(vor Bar) ---")
    print(f"  min/med/max: {r.min():.2f} / {r.median():.2f} / {r.max():.2f}")
    for thr in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
        print(f"  >= {thr:.2f}: {int((r >= thr).sum()):3d}  ({(r >= thr).mean()*100:.0f}%)")

# Wie viele H-Pivots tragen tatsaechlich Spike-Volumen?
print("\n--- H-Pivots: bar-/zeitliche Verteilung der Spikes (>= 1.5 / >= 2.0) ---")
for thr in (1.5, 2.0):
    sub = pv[(pv["typ"] == "H") & pv["ratio"].notna() & (pv["ratio"] >= thr)]
    print(f"  >= {thr}: {len(sub)} Pivots | Bars: {sorted(sub['bar'].tolist())[:40]}")

# ---------------------------------------------------------------------------
# Kontrast-Check: 6 Kanten (T9/T10/T11/T26 Geister vs. T14/T15 Winner)
# gegen die naechsten H-Pivots VOR Phasenstart (prior bars < phase_start)
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
print("KONTRAST-CHECK: Kante vs. naechster H-Pivot VOR Phasenstart")
print("=" * 100)
trades = [
    # (trade, signal_bar, edge, phase_start_bar)
    (9,  403, 64.309, 380),
    (10, 415, 64.790, 380),
    (11, 427, 65.038, 380),
    (26, 1209, 69.126, 1171),
    (14, 535, 66.284, 380),   # Winner
    (15, 561, 66.284, 380),   # Winner
]
H = pv[pv["typ"] == "H"].copy()
for tnr, sbar, edge, pstart in trades:
    prior = H[H["bar"] < pstart].copy()
    prior["dist"] = (prior["price"] - edge).abs()
    prior = prior.sort_values("dist")
    best = prior.iloc[0]
    win = prior[prior["dist"] <= 0.15]
    spike15 = win[win["ratio"] >= 1.5]
    spike20 = win[win["ratio"] >= 2.0]
    n_all = int((prior["dist"] <= 0.15).sum())
    print(f"\nT{tnr:>2} | Signal-Bar {sbar} | Kante {edge:.3f} | Phasenstart {pstart} "
          f"(Vorphasen-Bars 0..{pstart-1})")
    print(f"    Naechster H-Pivot: Bar {int(best['bar'])} {d['ts'].iloc[int(best['bar'])]} "
          f"Preis {best['price']:.3f} | Dist {best['dist']:.3f} USD | Vol-Ratio {best['ratio']:.2f}")
    print(f"    H-Pivots im +-0.15-Fenster: {n_all} | davon Spike>=1.5: {len(spike15)} "
          f"| Spike>=2.0: {len(spike20)}")
    if len(spike20):
        for _, r in spike20.iterrows():
            print(f"      Spike>=2.0: Bar {int(r['bar'])} {d['ts'].iloc[int(r['bar'])]} "
                  f"{r['price']:.3f} (Dist {abs(r['price']-edge):.3f}, Ratio {r['ratio']:.2f})")
    elif len(spike15):
        for _, r in spike15.iterrows():
            print(f"      Spike>=1.5: Bar {int(r['bar'])} {d['ts'].iloc[int(r['bar'])]} "
                  f"{r['price']:.3f} (Dist {abs(r['price']-edge):.3f}, Ratio {r['ratio']:.2f})")

# Speziell: 66.2-66.5-Cluster VOR Bar 380 (T14/T15-Anker-Behauptung)
print("\n--- H-Pivots mit Spike im Band 66.15-66.55 VOR Bar 380 (T14/T15-Anker) ---")
band = H[(H["bar"] < 380) & (H["price"] >= 66.15) & (H["price"] <= 66.55)]
for _, r in band.sort_values("bar").iterrows():
    print(f"  Bar {int(r['bar'])} {d['ts'].iloc[int(r['bar'])]} Preis {r['price']:.3f} "
          f"Vol {int(r['vol'])} Ratio {r['ratio']:.2f}")
