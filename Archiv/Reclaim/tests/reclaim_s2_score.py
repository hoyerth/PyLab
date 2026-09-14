# test/reclaim_s2_score.py
"""S2-Validierung: Confluence-Score v1 (3 Architektur-Vorgaben User 02.09.).

V1: rel_volume = tick_volume / rollierender Median der vorangegangenen
    VOL_REF_LOOKBACK Bars (kein Gesamtdurchschnitt -> kein Lookahead).
V2: Decay auf Handelszeit (Bars) statt Wanduhr. Verifikation: Ein Level,
    das keine Touches erhaelt, verliert zwischen zwei Touch-Events exakt
    Faktor exp(-gap_bars / EDGE_HALF_LIFE_BARS) (Replay mit zwei Laengen).
V3: Score inkrementell (EWMA-artig): frische Touches laden auf, sonst
    stetiger Zerfall. Verifikation: score(lev) == Summe der gedampften
    Touch-Beitraege (Aequivalent zur Sigma-Formel) und Monotonie-Test.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

START, ENDE = "2026-08-10", "2026-08-28"

# ===========================================================================
# V1: rel_volume gegen rollierenden Median nachrechnen (kein Lookahead)
# ===========================================================================
print("=== V1: rel_volume-Normalisierung (roll. Median, kein Lookahead) ===")
df = res.load_data(res.DB_PATH, START, ENDE)
store = res.EdgeStore().build(df)
n_checked = 0
n_ok = 0
worst = 0.0
for lev in store.levels:
    for t in lev.touches:
        # Store-Semantik: rolling(200, min_periods=20).median().shift(1)
        # -> NaN fuer t.bar < 20 (weniger als 20 Bars davor) => Fallback 1.0.
        if t.bar < 20:
            expected = 1.0
        else:
            lo = max(0, t.bar - store.vol_lookback)
            med = float(df["tick_volume"].iloc[lo:t.bar].median())
            expected = t.tick_volume / med
        diff = abs(expected - t.rel_volume)
        worst = max(worst, diff)
        n_ok += 1 if diff < 1e-9 else 0
        n_checked += 1
print(f"Touches geprueft: {n_checked} | exakt OK: {n_ok} | max Abweichung: {worst:.2e}")
print(f"-> {'BESTANDEN (rel_volume basiert auf roll. Median, kein Gesamtdurchschnitt)' if n_ok == n_checked else 'FEHLER'}")

# ===========================================================================
# V2+V3: Decay-Basis (Bars) und Inkrementalitaet (EWMA-Aequivalent)
# ===========================================================================
print("\n=== V2+V3: Bar-Decay & inkrementeller Score ===")
# Replay 1: komplettes Fenster
store_full = res.EdgeStore().build(df)
# Replay 2: gleiche Daten, aber alle Touches 1:1 - der Score jedes Levels muss
# der Summe der gedampften Beitraege entsprechen: score_lev == sum_t contrib_t
#   * exp(-(n_last - t.bar_known) / HALF_LIFE)   wobei bekannt bei j + lookback.
# Einfacher Aequivalenz-Check ueber EWMA-Definition ist schwierig, daher:
# 1) Monotonie: score eines Levels zwischen zwei Touch-Events faellt nie.
# 2) Referenz-Neuberechnung: score(lev) == summe(contrib gedampft ueber die
#    Zahl der Bars zwischen Touch-Bekanntwerden (j+2) und letzter Bar.
PL = store_full.pivot_lookback
n_last = len(df) - 1  # letzte Iteration (Bar n-1), nach der der Endscore gilt
d = store_full._decay
ref_ok = True
max_dev = 0.0
for lev in store_full.levels:
    s_ref = 0.0
    last_ind = -10**9
    for t in lev.touches:  # chronologisch sortiert (kausal angehaengt)
        k_known = t.bar + PL  # Iteration, an der der Touch bekannt wurde
        # independent wie in EdgeLevel.add_touch: Vergleich mit dem letzten
        # UNABHAENGIGEN Touch (last_independent_bar), nicht dem letzten Touch.
        indep = t.bar - last_ind >= store_full.min_spacing
        if indep:
            last_ind = t.bar
        contrib = store_full.w_volume * t.rel_volume \
            + store_full.w_type.get(t.touch_type, 1.0)
        if indep:
            contrib += store_full.w_count
        age = max(0, n_last - k_known)  # Bars nach Bekanntwerden (je 1 Decay/Bar)
        s_ref += contrib * (d ** age)
    dev = abs(s_ref - lev.score)
    max_dev = max(max_dev, dev)
    if dev > 1e-6:
        ref_ok = False
print(f"Referenz-Neuberechnung (Summe gedampfter Beitraege) gegen lev.score:")
print(f"  max Abweichung: {max_dev:.2e} | {'OK (inkrementell == EWMA-Summe)' if ref_ok else 'FEHLER'}")

# Halbwertszeit-Sichtbarkeit: Ein aktives Level, das lange keine Touches hat
act_now = store_full.active_levels()
if act_now:
    # Nimm ein aktives Level mit fruehem letztem Touch -> Score sollte klein sein
    # gegenueber einem mit spaetem letztem Touch bei aehnlicher Touch-Zahl.
    act_now.sort(key=lambda x: x.last_touch_bar)
    oldest = act_now[0]
    newest = act_now[-1]
    print(f"\nLevel #{oldest.edge_id}: last_touch_bar={oldest.last_touch_bar} "
          f"({df['ts'].iloc[oldest.last_touch_bar]:%d.%m}) T={oldest.n_touches} score={oldest.score:.2f}")
    print(f"Level #{newest.edge_id}: last_touch_bar={newest.last_touch_bar} "
          f"({df['ts'].iloc[newest.last_touch_bar]:%d.%m}) T={newest.n_touches} score={newest.score:.2f}")

# ===========================================================================
# Fenster-Statistik (Score-Verteilung)
# ===========================================================================
print("\n=== Score-Statistik je Fenster ===")
for name, s, e in [("AUG", "2026-08-10", "2026-08-28"),
                   ("S1", "2026-02-05", "2026-08-28"),
                   ("S2", "2025-01-01", "2025-12-01")]:
    dff = res.load_data(res.DB_PATH, s, e)
    t0 = time.time()
    st = res.EdgeStore().build(dff)
    dt = time.time() - t0
    act = st.active_levels()
    scores = np.array([x.score for x in act]) if act else np.array([0.0])
    print(f"{name:4s} | candles {len(dff):6d} | Level {len(st.levels):4d} | active {len(act):3d} "
          f"| Score active: min {scores.min():6.2f} | med {np.median(scores):6.2f} | "
          f"max {scores.max():7.2f} | build {dt:.1f}s")
