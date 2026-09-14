# -*- coding: utf-8 -*-
"""READ-ONLY H1-Forensik (Schritte 1-3): De-Risking vs. Stacking + Sweep-Schwelle.

Quelle: test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv (Rohdaten).
KEIN Engine-Import, kein _se_scan/_se_trades, kein Compile. Die Regeln werden
1:1 aus dem Code nachgerechnet (POC-Funktion wortgetreu reimplementiert).

Referenz-Trade 229 (Audit): SHORT K20 entry=231 E=66.424 SL=66.826
                            TP1(POC)=63.676 TP2=63.605 H1=TP1@386
Referenz-Trade 529 (Audit): SHORT K31 entry=531 E=66.324 SL=66.588
                            TP1(POC)=64.735 TP2=63.474 H1=TP1@614
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
CSV = Path(__file__).resolve().parent / "archiv" / "silver_m15_ohlc_2026-08-10_2026-08-28.csv"
d = pd.read_csv(CSV)
d["ts"] = pd.to_datetime(d["ts"])
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
op = d["open"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"]
n = len(d)
BAND, MAXSW, PUFFER, SLBUF = 0.12, 0.60, 0.01, 0.05


def zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m %H:%M")


def poc(start_bar: int, signal_bar: int, unter: float, ober: float,
        num_bins: int = 60) -> float:
    """Wortgetreue Reimplementierung von berechne_kausalen_histogramm_poc."""
    sub = d.iloc[start_bar:signal_bar + 1]
    if sub.empty:
        return (unter + ober) / 2.0
    edges = np.linspace(unter, ober, num_bins + 1)
    vol = np.zeros(num_bins, dtype=float)
    lows = sub["low"].to_numpy(float)
    highs = sub["high"].to_numpy(float)
    vols = sub["tick_volume"].to_numpy(float)
    for a, b, v in zip(lows, highs, vols):
        if b <= a or v <= 0:
            continue
        lo_b = int(np.clip(np.searchsorted(edges, a, side="right") - 1, 0, num_bins - 1))
        hi_b = int(np.clip(np.searchsorted(edges, b, side="left") - 1, 0, num_bins - 1))
        if lo_b == hi_b:
            vol[lo_b] += v
        else:
            ov = np.array([max(0.0, min(b, edges[x + 1]) - max(a, edges[x]))
                           for x in range(lo_b, hi_b + 1)])
            tot = float(ov.sum())
            if tot > 0:
                vol[lo_b:hi_b + 1] += v * ov / tot
    vol_s = np.convolve(vol, np.ones(3) / 3.0, mode="same") if len(vol) >= 3 else vol
    p = int(np.argmax(vol_s))
    return float((edges[p] + edges[p + 1]) / 2.0)


def loese(entry_bar, entry, sl, tp1, tp2, anteil1=50.0):
    """Zwei unabhaengige Haelften ab entry_bar (SHORT), wie _c_loese_trade."""
    risk = abs(sl - entry)
    hh, ll, cc = hi[entry_bar:], lo[entry_bar:], cl[entry_bar:]
    nb = len(hh)

    def first(mask):
        return int(np.argmax(mask)) if mask.any() else nb

    t1, t2, tsl = first(ll <= tp1), first(ll <= tp2), first(hh >= sl)
    r = lambda px: (entry - px) / risk  # noqa: E731
    if t1 < tsl:
        r1, b1 = r(tp1), entry_bar + t1
    elif tsl < nb:
        r1, b1 = -1.0, entry_bar + tsl
    else:
        r1, b1 = r(cc[-1]), entry_bar + nb - 1
    if t2 < tsl:
        r2, b2 = r(tp2), entry_bar + t2
    elif tsl < nb:
        r2, b2 = -1.0, entry_bar + tsl
    else:
        r2, b2 = r(cc[-1]), entry_bar + nb - 1
    w1 = anteil1 / 100.0
    return (w1 * r1 + (1 - w1) * r2, r1, r2, b1, b2, tsl, t1, t2)


print("=" * 118)
print("SCHRITT 1 -- TRADE 229 (SHORT K20): Zustand bei Bar 245 (Kandidaten-Entry 242/244)")
print("=" * 118)
E, SL, TP1, TP2 = 66.424, 66.826, 63.676, 63.605
EB = 231
print(f"  Trade 229: entry_bar={EB} E={E} SL={SL} TP1={TP1} TP2={TP2}")
print(f"  Rohdaten-Aufloesung:")
rm, r1, r2, b1, b2, tsl, t1, t2 = loese(EB, E, SL, TP1, TP2)
print(f"    SL   zuerst getroffen: bar {EB + tsl if tsl < len(hi) - EB else 'nie'}"
      f"{' (' + zeit(EB + tsl) + ')' if tsl < len(hi) - EB else ''}")
print(f"    TP1  zuerst getroffen: bar {EB + t1 if t1 < len(hi) - EB else 'nie'}"
      f"{' (' + zeit(EB + t1) + ')' if t1 < len(hi) - EB else ''}")
print(f"    TP2  zuerst getroffen: bar {EB + b2 if b2 < len(hi) - EB else 'nie'}"
      f"{' (' + zeit(EB + b2) + ')' if b2 < len(hi) - EB else ''}")
print(f"    H1-Exit bar {b1} | H2-Exit bar {b2} | R = {rm:+.2f} "
      f"(r1={r1:+.2f}, r2={r2:+.2f})")
print("")
print(f"  -> DE-RISKING-ZEITPUNKT (TP1) = Bar {b1} ({zeit(b1)})")
print(f"  -> Kandidaten-Entry der Setups 242/244 = Bar 245 ({zeit(245)})")
print(f"  -> 245 < {b1}: Position war bei Bar 245 NOCH IM VOLLEN RISIKO.")
print(f"  -> SL war bis dahin nie erreicht: {tsl >= (b1 - EB)}")
print("")
print("  Zustand der Position bei Bar 245 (Rohdaten):")
print(f"    {'bar':>5} {'zeit':>12} {'high':>8} {'low':>8} {'close':>8} "
      f"{'low<=TP1?':>10} {'high>=SL?':>10}")
for k in (242, 243, 244, 245, 246):
    print(f"    {k:5d} {zeit(k):>12} {hi[k]:8.3f} {lo[k]:8.3f} {cl[k]:8.3f} "
          f"{str(lo[k] <= TP1):>10} {str(hi[k] >= SL):>10}")

print("")
print("=" * 118)
print("SCHRITT 2 -- BAR 529: K20 (66.459) vs. K31 (66.327) in Rohdaten")
print("=" * 118)
print(f"  K20-Basis frozen = 66.459 (Primaer-Anker ab Bar 229)")
print(f"  K31-Basis(529)   = mean(high[237],high[249],high[286]) = "
      f"{np.mean([hi[237], hi[249], hi[286]]):.3f}")
print("")
print(f"  {'bar':>5} {'zeit':>12} {'open':>8} {'high':>8} {'low':>8} {'close':>8} "
      f"{'d20%':>8} {'d31%':>8}")
for k in range(526, 534):
    b31 = np.mean([hi[b] for b in (237, 249, 286) if b + 2 <= k])
    d20 = (hi[k] - 66.459) / 66.459 * 100.0
    d31 = (hi[k] - b31) / b31 * 100.0
    print(f"  {k:5d} {zeit(k):>12} {op[k]:8.3f} {hi[k]:8.3f} {lo[k]:8.3f} "
          f"{cl[k]:8.3f} {d20:+8.4f} {d31:+8.4f}")
print("")
print(f"  Bar 529: high={hi[529]:.3f} | K20-Basis={66.459:.3f} | "
      f"Ueberdeckung = {hi[529] - 66.459:+.4f} USD = {(hi[529] - 66.459) / 66.459 * 100:+.4f} %")
print(f"           reiner Sweep (High > Basis):        {hi[529] > 66.459}")
print(f"           Mindest-Band-Sweep (> 0.12 %):      {(hi[529] - 66.459) / 66.459 * 100 > 0.12}")
print(f"           Schwelle 0.12 % entspricht Preis:   {66.459 * 1.0012:.4f}")
print(f"           Fehlbetrag zur Schwelle:            {66.459 * 1.0012 - hi[529]:.4f} USD")

print("")
print("=" * 118)
print("SCHRITT 3 -- Hypothetisches K20-Setup an Bar 529 (reine Kantenueberdeckung)")
print("=" * 118)
basis20, basis31 = 66.459, float(np.mean([hi[237], hi[249], hi[286]]))
gegen = float(np.mean([hi[7], hi[398]]))     # K1 UNTEN, kausale Basis bei 529
print(f"  Gegenkante (K1 UNTEN, kausal) = mean(high[7],high[398]) = {gegen:.3f}")
print(f"  (Audit-TP2 des K31-Trades = 63.474 -> bestaetigt: {abs(gegen - 63.474) < 1e-3})")
print("")

for name, basis in (("K20 (hypothetisch)", basis20), ("K31 (arretiert)", basis31)):
    dist = (hi[529] - basis) / basis * 100.0
    # _reclaim_stufe mit band=0 (reine Ueberdeckung)
    stufe, sname = 0, "-"
    if hi[529] > basis and 0.0 < dist <= MAXSW:
        if cl[529] <= basis:
            stufe, sname = 1, "STUFE_1_IN_BAR"
        elif cl[530] <= basis and hi[530] <= hi[529] + PUFFER:
            stufe, sname = 2, "STUFE_2_KERZE_2"
        elif cl[531] <= basis and max(hi[530], hi[531]) <= hi[529] + PUFFER:
            stufe, sname = 3, "STUFE_3_KERZE_3"
    entry_bar = 529 + stufe
    reclaim_bar = entry_bar - 1
    cluster_ext = float(np.max(hi[529:reclaim_bar + 1]))
    sl = cluster_ext + SLBUF
    entry = float(op[entry_bar])
    p = poc(0, 529, gegen, basis)
    tp1, tp2 = p, gegen
    ok = sl > entry > p > tp2
    print(f"  {name}: basis={basis:.3f} dist={dist:+.4f}% -> {sname}")
    print(f"    entry_bar={entry_bar} (open={entry:.3f}) SL={sl:.3f} "
          f"(cluster_ext={cluster_ext:.3f}) TP1(POC)={p:.3f} TP2={tp2:.3f}")
    print(f"    Geometrie sl>entry>poc>tp2: {ok} | risk={abs(sl - entry):.4f}")
    if ok and stufe:
        rm, r1, r2, b1, b2, tsl, t1, t2 = loese(entry_bar, entry, sl, tp1, tp2)
        print(f"    Aufloesung: H1=TP1@{b1} ({zeit(b1)}) | H2=TP2@{b2} ({zeit(b2)}) "
              f"| R = {rm:+.2f} (r1={r1:+.2f}, r2={r2:+.2f})")
    else:
        print(f"    -> Setup NICHT handelbar (Geometrie/Stufe)")
    print("")

print("=" * 118)
print("ZUSATZ: Was aendert 'reine Ueberdeckung' an der KASKADE? (Code-Inspektion)")
print("=" * 118)
print("  Gate (ii) _kandidat: `if dist <= cfg.touch_band_pct: continue`")
print("    -> K20 wird bei 529 VOR der Sweep-Pruefung uebersprungen (0.1189 <= 0.12).")
print("    -> Eine Entkopplung NUR von _reclaim_stufe (Gate iii) ist daher wirkungslos")
print("       (Teil 6, V1: 9 Trades / +23.02 R, Signatur identisch).")
print("  Erst Gate (ii)+(ii')+(iii) gemeinsam (Teil 6, V4):")
print("    sweep_min 0.02 -> 12 Trades / +21.12 R (3 neue Verlierer: 383/492/620)")
print("    sweep_min 0.05 -> 11 Trades / +21.52 R")
print("  Anker-Vorrang allein (V2): 8 Trades / +14.61 R (Trade 529 faellt weg,")
print("    weil _reclaim_stufe weiter 0.12 verlangt).")
print("  V3 (Anker-Vorrang + sweep_min 0.05): 9 Trades / +23.00 R ->")
print("    Trade 529 wandert K31 -> K20, R +8.41 -> +8.39.")
