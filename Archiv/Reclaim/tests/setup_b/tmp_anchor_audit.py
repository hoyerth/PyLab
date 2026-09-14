"""27-Trade AUG Anker-Audit: historische Verankerung der operativen Kanten.

Frage: Hat die operative Kante jedes AUG-Baseline-Trades (U_zone fuer SHORT,
L_zone fuer LONG) einen historischen Anker = bestaetigter Pivot der passenden
Seite (H fuer SHORT/U, L fuer LONG/L) aus einer Vorphase (ts < Phasenstart)
mit Volumen-Spike?

Metriken je Trade (Verbund 0.15-USD-Distanz + Spike):
  dist_min        : Distanz Kante -> naechster Vorphasen-Pivot der Seite
  best_ratio      : Volumen-Ratio (tick_volume / avg20 VOR der Bar) am Pivot
  n_015           : Anzahl Vorphasen-Pivots im +-0.15-Fenster um die Kante
  spike_ge_15     : davon mit Ratio >= 1.5
  spike_ge_20     : davon mit Ratio >= 2.0
  anchored_15     : spike_ge_15 >= 1  (Kante historisch verankert, Schwelle 1.5)
  anchored_20     : spike_ge_20 >= 1  (Schwelle 2.0)

Bilanz: Wie viele der 15 Verlierer waeren 'ohne echten Anker' erkannt worden
(anchored=False -> potenzielles Veto)? Wie viele der 12 Gewinner haetten einen
Anker (bleiben unangetastet)?

Daten: exec-Import-Cut (exakte Phasen/Signale, 27/27 bitgenau verifiziert);
Pivot-Erkennung = find_pivots-Identik (PIVOT_LOOKBACK=2); erweitertes Fenster
ab 2026-07-01 (Marktgedaechtnis vor dem AUG-Fensterbeginn 10.08) read-only.
Kein Produktivcode.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path("test/tmp_anchor_audit_AUG.txt")
_buf: list[str] = []


def out(*a: object) -> None:
    _buf.append(" ".join(str(x) for x in a))


# ------------------------------------------------------- 1) exec-Import (AUG)
src = io.open("scripts/phasen_volumen_profil.py", encoding="utf-8").read()
_marker = "reclaim_signals.sort(key=lambda s: s.ts)"
_cut = src.rindex(_marker) + len(_marker)
ns = {"__file__": str(Path("scripts/phasen_volumen_profil.py").resolve())}
exec(compile(src[:_cut], "phasen_volumen_profil.py", "exec"), ns)  # noqa: S102
df = ns["df"]
phases = ns["phases"]
sigs: list = ns["reclaim_signals"]
out(f"exec-Import OK | AUG-Bars {len(df)} | Phasen {len(phases)} | Signale {len(sigs)}")
out("")

# ------------------------------------------------ 2) erweitertes Fenster laden
con = duckdb.connect("data/market_data.duckdb", read_only=True)
ext = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= DATE '2026-07-01'
      AND time AT TIME ZONE 'UTC' <  DATE '2026-08-28'
    ORDER BY time
""").fetchdf()
con.close()
ext["ts"] = pd.to_datetime(ext["ts"], utc=True).dt.tz_localize(None)
ext = ext.reset_index(drop=True)
out(f"Erweitertes Fenster (Vorlauf ab 01.07): {len(ext)} Bars | "
    f"{ext['ts'].iloc[0]} .. {ext['ts'].iloc[-1]}")

# ------------------------------------------------ 3) Pivots + Volumen-Ratio
h = ext["high"].values.astype(float)
l = ext["low"].values.astype(float)
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
vol = ext["tick_volume"].values.astype(float)
avg20 = pd.Series(vol).rolling(20, min_periods=5).mean().shift(1).values
recs_piv = []
for i in range(len(ext)):
    if is_hi[i]:
        recs_piv.append({"ts": ext["ts"].iloc[i], "price": float(h[i]),
                         "typ": "H", "vol": float(vol[i]),
                         "ratio": float(vol[i] / avg20[i]) if avg20[i] else np.nan})
    if is_lo[i]:
        recs_piv.append({"ts": ext["ts"].iloc[i], "price": float(l[i]),
                         "typ": "L", "vol": float(vol[i]),
                         "ratio": float(vol[i] / avg20[i]) if avg20[i] else np.nan})
pv = pd.DataFrame(recs_piv)
out(f"Pivots im erweiterten Fenster: {len(pv)} (H {int((pv['typ']=='H').sum())}, "
    f"L {int((pv['typ']=='L').sum())})")

# ------------------------------------------------------- 4) Audit je Trade
rows = []
for i, s in enumerate(sigs, 1):
    p = phases[s.phase - 1]
    p_start_ts = p.start
    kante = s.U_laufend if s.typ == "SHORT" else s.L_laufend
    seite = "H" if s.typ == "SHORT" else "L"
    prior = pv[(pv["typ"] == seite) & (pv["ts"] < p_start_ts)].copy()
    if len(prior):
        prior["dist"] = (prior["price"] - kante).abs()
        best = prior.loc[prior["dist"].idxmin()]
        in_win = prior[prior["dist"] <= 0.15]
        d = {
            "nr": i, "phase": s.phase, "ts": s.ts, "dir": s.typ,
            "entry": s.einstieg_preis, "r": s.trade.r_mult,
            "kante": kante, "p_start": p_start_ts,
            "n_prior": int(len(prior)),
            "best_price": float(best["price"]),
            "best_dist": float(best["dist"]),
            "best_ratio": float(best["ratio"]) if not np.isnan(best["ratio"]) else None,
            "best_ts": best["ts"],
            "n_015": int((prior["dist"] <= 0.15).sum()),
            "spike_ge_15": int((in_win["ratio"] >= 1.5).sum()),
            "spike_ge_20": int((in_win["ratio"] >= 2.0).sum()),
        }
    else:
        d = {"nr": i, "phase": s.phase, "ts": s.ts, "dir": s.typ,
             "entry": s.einstieg_preis, "r": s.trade.r_mult,
             "kante": kante, "p_start": p_start_ts, "n_prior": 0,
             "best_price": None, "best_dist": None, "best_ratio": None,
             "best_ts": None, "n_015": 0, "spike_ge_15": 0, "spike_ge_20": 0}
    d["anchored_15"] = d["spike_ge_15"] >= 1
    d["anchored_20"] = d["spike_ge_20"] >= 1
    # Praezisere Variante: der NAECHSTE Pivot (eigentlicher Anker der Kante)
    # muss <= 0.15 entfernt liegen UND selbst Spike-Volumen tragen.
    d["anchored_near_15"] = bool(d["best_dist"] is not None
                                 and d["best_dist"] <= 0.15
                                 and d["best_ratio"] is not None
                                 and d["best_ratio"] >= 1.5)
    d["anchored_near_20"] = bool(d["best_dist"] is not None
                                 and d["best_dist"] <= 0.15
                                 and d["best_ratio"] is not None
                                 and d["best_ratio"] >= 2.0)
    rows.append(d)

# ------------------------------------------------------- 5) Report
out("")
out("=" * 150)
out("ANCHOR-AUDIT je Trade (Kante vs. Vorphasen-Pivots der Seite, ts < Phasenstart)")
out("=" * 150)
hdr = (f"{'#':>2} {'Ph':>2} {'Sig-Zeit':<16} {'Dir':<5} {'Entry':>8} {'R':>6} | "
       f"{'Kante':>7} {'Pstart':<16} | {'nVor':>4} {'bDist':>6} {'bRatio':>6} "
       f"{'bPivotBar':<16} | {'n015':>3} {'s15':>3} {'s20':>3} | "
       f"{'A15':>4} {'A20':>4} {'AN15':>4} {'AN20':>4}")
out(hdr)
out("-" * len(hdr))
for d in rows:
    bd = f"{d['best_dist']:.3f}" if d["best_dist"] is not None else "  -  "
    br = f"{d['best_ratio']:.2f}" if d["best_ratio"] is not None else "  -  "
    bt = f"{d['best_ts']:%d.%m %H:%M}" if d["best_ts"] is not None else "      -       "
    out(f"{d['nr']:>2} {d['phase']:>2} {d['ts']:%d.%m %H:%M} {d['dir']:<5} "
        f"{d['entry']:>8.3f} {d['r']:>+6.2f} | {d['kante']:>7.3f} "
        f"{d['p_start']:%d.%m %H:%M} | {d['n_prior']:>4} {bd:>6} {br:>6} "
        f"{bt:>16} | {d['n_015']:>3} {d['spike_ge_15']:>3} {d['spike_ge_20']:>3} "
        f"| {str(d['anchored_15']):>4} {str(d['anchored_20']):>4} "
        f"{str(d['anchored_near_15']):>4} {str(d['anchored_near_20']):>4}")

# ------------------------------------------------------- 6) Bilanz
out("")
out("=" * 90)
out("BILANZ: Anker-Bedingung (anchored = >=1 Vorphasen-Pivot im +-0.15-Fenster mit Spike)")
out("=" * 90)
losers = [d for d in rows if d["r"] < 0]
winners = [d for d in rows if d["r"] > 0]
variants = (
    ("Schwelle 1.5x (irgendein Pivot im Fenster)", "anchored_15"),
    ("Schwelle 2.0x (irgendein Pivot im Fenster)", "anchored_20"),
    ("Schwelle 1.5x (NAECHSTER Pivot)", "anchored_near_15"),
    ("Schwelle 2.0x (NAECHSTER Pivot)", "anchored_near_20"),
)
for label, key in variants:
    out(f"\n--- {label} ---")
    l_ohne = [d for d in losers if not d[key]]
    l_mit = [d for d in losers if d[key]]
    w_mit = [d for d in winners if d[key]]
    w_ohne = [d for d in winners if not d[key]]
    out(f"15 VERLIERER: ohne Anker (waeren geblockt, korrekt?) = {len(l_ohne)} | "
        f"mit Anker (nicht erkannt) = {len(l_mit)}")
    if l_ohne:
        out("  ohne Anker: " + ", ".join(f"T{d['nr']}(P{d['phase']},{d['r']:+.2f}R)" for d in l_ohne))
    if l_mit:
        out("  mit Anker : " + ", ".join(f"T{d['nr']}(P{d['phase']},{d['r']:+.2f}R)" for d in l_mit))
    out(f"12 GEWINNER: mit Anker (bleiben unangetastet) = {len(w_mit)} | "
        f"ohne Anker (waeren faelschlich geblockt) = {len(w_ohne)}")
    if w_ohne:
        out("  ohne Anker: " + ", ".join(f"T{d['nr']}(P{d['phase']},{d['r']:+.2f}R)" for d in w_ohne))
    if w_mit:
        out("  mit Anker : " + ", ".join(f"T{d['nr']}(P{d['phase']},{d['r']:+.2f}R)" for d in w_mit))
    r_verhindert = -sum(d["r"] for d in l_ohne)  # vermiedene Verluste (positiv)
    r_verloren = sum(d["r"] for d in w_ohne)     # verlorene Gewinne (positiv)
    out(f"  Netto-Wirkung Blocken: verhinderte Verluste +{r_verhindert:.2f}R | "
        f"verlorene Gewinne -{r_verloren:.2f}R | Netto {r_verhindert - r_verloren:+.2f}R")

OUT.write_text("\n".join(_buf) + "\n", encoding="utf-8")
print(f"OK -> {OUT} ({len(_buf)} Zeilen)")
