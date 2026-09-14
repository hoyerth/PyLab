"""Wirtschaftliche Equity-Statistik SYMBOL M15 (Reclaim-Baseline).

Liest stats_trades_<SYMBOL>_<FENSTER>.txt (engine-Export) und baut eine
USD-Equity-Kurve. Konvention (wie test/archiv/tmp_*_economic_backtest.py):
  - Risiko je Trade = 100 USD (1R = 100 USD).
  - Positionsgroesse = 100 / (Entry x SL_PCT) -> jeder Trade riskiert 100 USD.
  - P/L = r_mult x 100 USD; Equity startet 0 USD, trade-fuer-trade.
  - Keine Kosten, kein Zinseszinseffekt.

Aufruf: python test/tmp_symbol_equity.py SYMBOL FENSTER
Ausgaben:
  - test/stats_trades_<SYMBOL>_<FENSTER>_equity.txt
  - test/stats_trades_<SYMBOL>_<FENSTER>.png   (Equity-Kurve)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

TEST = Path(__file__).resolve().parent
RISK_USD = 100.0

# SL_PCT (Dezimal) je Symbol/Fenster - ATR-skalierte Kalibrierung (0.87 ATR).
SL_PCT = {
    "Coffee": {"AUG": 0.005363, "S1": 0.004481, "S2": 0.004502},
    "Cocoa": {"AUG": 0.006718, "S1": 0.007005, "S2": 0.006133},
    "Brent": {"AUG": 0.002968, "S1": 0.004536, "S2": 0.002190},
    "NGas": {"AUG": 0.003001, "S1": 0.003885, "S2": 0.003972},
    "EURUSD": {"AUG": 0.001000, "S1": 0.001000, "S2": 0.000608},
    "Ger40": {"AUG": 0.000786, "S1": 0.001429, "S2": 0.001270},
    "SILVER": {"AUG": 0.004500, "S1": 0.004500, "S2": 0.004500,
               "LONG": 0.004500},  # Baseline-Default 0.45 %; LONG = Langzeit-Stresstest
}

# Final kalibrierte VA_PCT je Symbol/Fenster (Anzeige Report/PNG-Titel).
# Eintrag je Symbol = einheitlich; je Fenster spezifisch via VA_FENSTER.
VA_LABEL = {
    "Coffee": 0.93,
    "Cocoa": 0.91,
    "Brent": 0.95,
    "NGas": 0.97,
    "Ger40": 0.89,
    "SILVER": 0.93,
}
VA_FENSTER = {
    "EURUSD": {"AUG": 0.99, "S1": 0.99, "S2": 0.91},
}

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "Cocoa"
FENSTER = sys.argv[2] if len(sys.argv) > 2 else "S1"
SRC = TEST / f"stats_trades_{SYMBOL}_{FENSTER}.txt"
OUT_TXT = TEST / f"stats_trades_{SYMBOL}_{FENSTER}_equity.txt"
OUT_PNG = TEST / f"stats_trades_{SYMBOL}_{FENSTER}.png"
SL = SL_PCT[SYMBOL][FENSTER]
VA = (VA_FENSTER.get(SYMBOL, {}).get(FENSTER)
      or VA_LABEL.get(SYMBOL, VA_LABEL["Cocoa"]))

lines = SRC.read_text(encoding="utf-8").splitlines()
hdr = next((l for l in lines if l.startswith("Fenster:")), "")

trades = []
for l in lines:
    if "|" not in l or "Trade_Nr" in l or "----" in l.replace(" ", ""):
        continue
    if l.strip().startswith("=") or l.strip().startswith("STATS") or l.strip().startswith("TRADE"):
        continue
    parts = [p.strip() for p in l.split("|")]
    if len(parts) != 10:
        continue
    try:
        nr = int(parts[0])
        r = float(parts[8].rstrip("R"))
        entry = float(parts[6])
    except ValueError:
        continue
    trades.append({"nr": nr, "dir": parts[5], "entry": entry, "r": r})
trades.sort(key=lambda t: t["nr"])
if not trades:
    raise SystemExit(f"Keine Trades in {SRC}")

equity, peak = 0.0, 0.0
max_dd_usd = 0.0
max_dd_pct = 0.0
dd_start_nr = dd_start_eq = None
cur_dd_len = max_dd_len = 0
tief_nr = None
for t in trades:
    t["pl"] = t["r"] * RISK_USD
    equity += t["pl"]
    t["equity"] = equity
    if equity > peak:
        if cur_dd_len > max_dd_len:
            max_dd_len = cur_dd_len
        cur_dd_len = 0
        peak = equity
    else:
        cur_dd_len += 1
        if dd_start_nr is None:
            dd_start_nr, dd_start_eq = t["nr"], peak
        dd = equity - peak
        if dd < max_dd_usd:
            max_dd_usd = dd
            max_dd_pct = dd / peak * 100.0 if peak > 0 else 0.0
            tief_nr = t["nr"]
w = [t for t in trades if t["r"] > 0]
l = [t for t in trades if t["r"] < 0]
sum_w = sum(t["pl"] for t in w)
sum_l = sum(t["pl"] for t in l)
pf_usd = sum_w / abs(sum_l) if sum_l else float("inf")
best = max(trades, key=lambda x: x["pl"])
worst = min(trades, key=lambda x: x["pl"])
n = len(trades)
sum_r = sum(t["r"] for t in trades)
wr = len(w) / n * 100.0
avg_r = sum_r / n
kurs_tr = sum_r * SL / n * 100.0  # Kursrendite % je Trade

out = []
def o(*a): out.append(" ".join(str(x) for x in a))
o("=" * 104)
o(f"EQUITY-STATISTIK {SYMBOL} M15 (Reclaim-Baseline, VA_PCT {VA:.2f}) - Fenster {FENSTER}")
o("=" * 104)
o(f"Quelle        : {SRC.name}  ({hdr.strip()})")
o(f"Risiko/Trade  : {RISK_USD:.2f} USD (1R = 100 USD)")
o(f"SL-Param      : SL_PCT {SL*100:.3f}% vom Entry -> Positionsgroesse = 100 / (Entry x {SL:.4f})")
o(f"Kosten        : KEINE (kein Spread, keine Slippage, keine Kommission)")
o(f"Equity-Start  : 0.00 USD (vor Trade 1), trade-fuer-trade kumuliert")
o(f"Equity-Ende   : {equity:+,.2f} USD  (= {sum_r:+.2f}R x 100 USD)")
o("-" * 104)
o(f"{'Nr':>4} {'Dir':<5} {'Entry':>8} {'R':>8} {'P/L USD':>10} {'Equity USD':>12}")
for t in trades:
    o(f"{t['nr']:>4} {t['dir']:<5} {t['entry']:>8.3f} {t['r']:>+8.2f} "
      f"{t['pl']:>+10.2f} {t['equity']:>12.2f}")
o("-" * 104)
o("KENNZAHLEN (USD):")
o(f"  Trades              : {n} (Long {sum(1 for t in trades if t['dir']=='LONG')} / "
  f"Short {sum(1 for t in trades if t['dir']=='SHORT')})")
o(f"  Win-Rate            : {wr:.1f}%  ({len(w)} Gewinn / {len(l)} Verlust)")
o(f"  Summe R             : {sum_r:+.2f}R")
o(f"  End-Equity          : {equity:+,.2f} USD")
o(f"  Max Equity (Peak)   : {peak:+,.2f} USD")
if max_dd_usd < 0:
    o(f"  Max Drawdown        : {max_dd_usd:,.2f} USD ({max_dd_pct:.2f}% vom Peak, "
      f"Tief T{tief_nr})")
else:
    o("  Max Drawdown        : 0.00 USD")
o(f"  Laengste DD-Serie   : {max_dd_len} Trades")
o(f"  Gewinner            : {len(w)}  | Summe Gewinne {sum_w:+,.2f} USD")
o(f"  Verlierer           : {len(l)}  | Summe Verluste {sum_l:+,.2f} USD")
o(f"  Profit-Faktor (USD) : {pf_usd:.2f}")
o(f"  Bester Trade        : T{best['nr']} {best['dir']} R {best['r']:+.2f} = {best['pl']:+,.2f} USD")
o(f"  Schlechtester Trade : T{worst['nr']} {worst['dir']} R {worst['r']:+.2f} = {worst['pl']:+,.2f} USD")
o(f"  Avg Gewinner        : {sum_w/len(w):+,.2f} USD | Avg Verlierer {sum_l/len(l):+,.2f} USD")
o(f"  Avg R je Trade      : {avg_r:+.2f}R  | Kursrendite je Trade: {kurs_tr:+.3f}%")
o("-" * 104)
o("Hinweis: Equity beginnt bei 0.00 USD (reiner P/L-Verlauf, kein Kapital-")
o("einsatz modelliert). 1R = 100 USD; Positionsgroesse skaliert invers zum")
o("SL-Abstand, damit jeder Trade exakt 100 USD Risiko traegt.")
with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")

eq = np.array([t["equity"] for t in trades])
fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(range(1, n + 1), eq, lw=1.8, color="#1a5fb4")
ax.axhline(0, color="#555", lw=0.8)
ax.fill_between(range(1, n + 1), eq, 0, where=eq >= 0, color="#1a5fb4", alpha=0.15)
ax.fill_between(range(1, n + 1), eq, 0, where=eq < 0, color="#c01c28", alpha=0.15)
ax.set_xlabel("Trade-Nr")
ax.set_ylabel("Equity USD (1R = 100 USD)")
ax.set_title(f"{SYMBOL} M15 | Fenster {FENSTER} | Equity-Kurve (VA_PCT {VA:.2f}, SL {SL*100:.2f}%)")
ax.grid(alpha=0.3)
txt = (f"Trades {n} | WR {wr:.1f}% | SumR {sum_r:+.2f}R\n"
       f"End-Equity {equity:+,.0f} USD | MaxDD {max_dd_usd:,.0f} USD\n"
       f"PF {pf_usd:.2f} | Kurs%/Trade {kurs_tr:+.3f}")
ax.text(0.02, 0.97, txt, transform=ax.transAxes, va="top", fontsize=9,
        family="monospace", bbox=dict(boxstyle="round", facecolor="#fdf6e3", alpha=0.95))
fig.tight_layout()
fig.savefig(OUT_PNG, dpi=140)
print(f"OK -> {OUT_TXT}")
print(f"OK -> {OUT_PNG}")
print(f"End-Equity {equity:+,.2f} USD | MaxDD {max_dd_usd:,.2f} USD | PF {pf_usd:.2f} | "
      f"Kurs%/Tr {kurs_tr:+.3f}")
