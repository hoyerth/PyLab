# -*- coding: utf-8 -*-
"""Wirtschaftliches Backtesting S2 (Baseline): Equity-Kurve in USD.

Annahme (User): Risiko = 100 USD pro Trade (1R = 100 USD), kalibriert auf den
gesetzten SL_PCT 0.45 % (Positionsgroesse = 100 / (Entry * 0.0045)).
Keine Ausfuehrungskosten (kein Spread/Slippage/Kommission). Ergebnis je Trade
= r_mult * 100 USD. Equity startet bei 0.00 USD vor Trade 1 und laeuft
trade-fuer-trade bis zum letzten 2025-Trade (S2-Fenster-Ende 28.11.2025).

Datenbasis: test/tmp_S2_monatslauf_2025-*.txt (10 Monatsberichte, verifiziert:
210 Trades, Summe +99.90R gerundet; exakt +99.88R = Baseline S2). Rein lesend (I3/I4).
Ausgabe: test/tmp_S2_economic_backtest.txt
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

RISK_USD = 100.0
SL_PCT = 0.0045
OUT = Path("test/tmp_S2_economic_backtest.txt")

# ---------------------------------------------------------------- Trades aus Monatsberichten
trades: list[dict] = []
pat = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2})\s+"
    r"(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
)
for f in sorted(glob.glob("test/tmp_S2_monatslauf_2025-*.txt")):
    for l in open(f, encoding="utf-8").read().splitlines():
        m = pat.match(l)
        if not m:
            continue
        trades.append({
            "nr": int(m.group(1)), "phase": int(m.group(2)),
            "tag": m.group(3), "zeit": m.group(4),
            "dir": m.group(5), "entry": float(m.group(6)), "r": float(m.group(7)),
        })
trades.sort(key=lambda x: x["nr"])
assert len(trades) == 210, len(trades)
assert abs(sum(t["r"] for t in trades) - 99.88) < 0.10  # gerundete Monats-R (+99.90); exakt +99.88R

# ---------------------------------------------------------------- Equity
equity = 0.0
peak = 0.0
max_dd_usd = 0.0
max_dd_pct = 0.0
dd_start_nr = dd_start_eq = None
max_dd_len = 0
cur_dd_len = 0
month_end: dict[str, float] = {}
rows: list[dict] = []
for t in trades:
    pl = t["r"] * RISK_USD
    equity += pl
    t["pl"], t["equity"] = pl, equity
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
            if peak > 0:
                max_dd_pct = dd / peak * 100.0
            max_dd_nr = t["nr"]
    # tag-Format ist TT.MM.JJJJ -> Monatsschluessel JJJJ-MM (nicht [:7] = TT.MM.J!)
    monat = f"{t['tag'][6:10]}-{t['tag'][3:5]}"
    month_end[monat] = equity  # Trades sind chronologisch -> letzter Stand je Monat

w = [t for t in trades if t["r"] > 0]
l = [t for t in trades if t["r"] < 0]
sum_w = sum(t["pl"] for t in w)
sum_l = sum(t["pl"] for t in l)
pf_usd = sum_w / abs(sum_l) if sum_l else float("inf")
best = max(trades, key=lambda x: x["pl"])
worst = min(trades, key=lambda x: x["pl"])

# ---------------------------------------------------------------- Statistik-Ausbau (maxDD-Episode, Serien, CRV)
def _laengste_serie(tr, verlust: bool) -> dict:
    """Laengste Serie aufeinanderfolgender Verlust-/Gewinn-Trades (R<0 bzw. R>0)."""
    empty = {"len": 0, "r": 0.0, "usd": 0.0, "von": None, "bis": None,
             "von_tag": None, "bis_tag": None}
    best = dict(empty)
    cur = dict(empty)
    for t in tr:
        hit = (t["r"] < 0) if verlust else (t["r"] > 0)
        if hit:
            if cur["len"] == 0:
                cur = {"len": 0, "r": 0.0, "usd": 0.0, "von": t["nr"],
                       "bis": None, "von_tag": t["tag"], "bis_tag": None}
            cur["len"] += 1
            cur["r"] += t["r"]
            cur["usd"] += t["pl"]
            cur["bis"] = t["nr"]
            cur["bis_tag"] = t["tag"]
        else:
            if (cur["len"], abs(cur["r"])) > (best["len"], abs(best["r"])):
                best = dict(cur)
            cur = dict(empty)
    if (cur["len"], abs(cur["r"])) > (best["len"], abs(best["r"])):
        best = dict(cur)
    return best


def _maxdd_episode(tr):
    """Tiefste DD-Episode (Kriterium: min dd_usd = konsistent zur KENNZAHLEN-Zeile)."""
    peak = tr[0]["equity"] - tr[0]["pl"]  # Equity vor Trade 1
    peak_i = -1
    tief = {"i": None, "usd": 0.0, "pct": 0.0, "peak_i": None}
    for i, t in enumerate(tr):
        if t["equity"] > peak:
            peak = t["equity"]
            peak_i = i
        dd_usd = t["equity"] - peak
        if tief["i"] is None or dd_usd < tief["usd"]:
            tief = {"i": i, "usd": dd_usd,
                    "pct": dd_usd / peak * 100.0 if peak > 0 else 0.0,
                    "peak_i": peak_i}
    return tief


def _dd_episoden(tr):
    """Alle DD-Episoden (Peak -> Tief; Episode endet, sobald neues Allzeithoch)."""
    peak = tr[0]["equity"] - tr[0]["pl"]
    peak_i = -1
    tief = {"i": None, "usd": 0.0, "pct": 0.0}
    out = []
    for i, t in enumerate(tr):
        if t["equity"] > peak:
            if tief["i"] is not None and tief["usd"] < 0 and peak_i >= 0:
                out.append((peak_i, tief["i"], tief["usd"], tief["pct"]))
            peak = t["equity"]
            peak_i = i
            tief = {"i": None, "usd": 0.0, "pct": 0.0}
        dd_usd = t["equity"] - peak
        if tief["i"] is None or dd_usd < tief["usd"]:
            tief = {"i": i, "usd": dd_usd,
                    "pct": dd_usd / peak * 100.0 if peak > 0 else 0.0}
    if tief["i"] is not None and tief["usd"] < 0 and peak_i >= 0:
        out.append((peak_i, tief["i"], tief["usd"], tief["pct"]))
    return out


# maxDD-Episode (Haupt) + Top-3-DD-Episoden + laengste Serien (fuer Report)
tief = _maxdd_episode(trades)
assert abs(tief["usd"] - max_dd_usd) < 0.01
peak_t = trades[tief["peak_i"]]
tief_t = trades[tief["i"]]
ep = trades[tief["peak_i"] + 1: tief["i"] + 1]
ep_v = [x for x in ep if x["r"] < 0]
ep_g = [x for x in ep if x["r"] > 0]
erhol_i = next((i for i in range(tief["i"] + 1, len(trades))
                if trades[i]["equity"] >= peak_t["equity"]), None)
vl = _laengste_serie(trades, verlust=True)
wg = _laengste_serie(trades, verlust=False)
top3 = sorted(_dd_episoden(trades), key=lambda e: e[2])[:3]  # negativste (USD) zuerst
crv = (sum_w / len(w)) / abs(sum_l / len(l)) if l else float("inf")
wr = len(w) / len(trades) * 100.0
avg_r = sum(t["r"] for t in trades) / len(trades)

# ---------------------------------------------------------------- Report
out = []
def o(*a): out.append(" ".join(str(x) for x in a))
o("=" * 110)
o("WIRTSCHAFTLICHES BACKTESTING S2 (Baseline phasen_volumen_profil.py)")
o("=" * 110)
o(f"Fenster        : 2025-01-01 .. 2025-12-01 (letzter Trade 28.11.2025)")
o(f"Trades         : {len(trades)} (Long {sum(1 for t in trades if t['dir']=='LONG')} / "
  f"Short {sum(1 for t in trades if t['dir']=='SHORT')})")
o(f"Risiko/Trade   : {RISK_USD:.2f} USD (1R = 100 USD)")
o(f"SL-Kalibrierung: SL_PCT {SL_PCT*100:.2f}% vom Entry -> Positionsgroesse "
  f"= 100 / (Entry x 0.0045)")
o(f"Kosten         : KEINE (kein Spread, keine Slippage, keine Kommission)")
o(f"Equity-Start   : 0.00 USD (vor Trade 1), trade-fuer-trade kumuliert")
o(f"Equity-Ende    : {equity:+,.2f} USD  (= {sum(t['r'] for t in trades):+.2f}R x 100 USD)")
o("-" * 110)
o(f"{'Nr':>4} {'Zeit (UTC)':<17} {'Dir':<5} {'Entry':>8} {'R':>7} "
  f"{'P/L USD':>10} {'Equity USD':>12}")
o("-" * 110)
for t in trades:
    o(f"{t['nr']:>4} {t['tag']} {t['zeit']} {t['dir']:<5} {t['entry']:>8.3f} "
      f"{t['r']:>+7.2f} {t['pl']:>+10.2f} {t['equity']:>12.2f}")
o("-" * 110)
o("EQUITY-ENDE JE MONAT:")
for m in sorted(month_end):
    o(f"  {m}: {month_end[m]:>+12.2f} USD")
o("-" * 110)
o("KENNZAHLEN (USD, ohne Kosten):")
o(f"  End-Equity          : {equity:+,.2f} USD")
o(f"  Max Equity (Peak)   : {peak:+,.2f} USD")
o(f"  Max Drawdown        : {max_dd_usd:,.2f} USD ({max_dd_pct:.2f}% vom Peak, "
  f"Tief T{tief_t['nr']} {tief_t['tag']})")
o(f"  Gewinner            : {len(w)}  | Summe Gewinne {sum_w:+,.2f} USD")
o(f"  Verlierer           : {len(l)}  | Summe Verluste {sum_l:+,.2f} USD")
o(f"  Profit-Faktor (USD) : {pf_usd:.2f}")
o(f"  Bester Trade        : T{best['nr']} {best['tag']} {best['dir']} "
  f"R {best['r']:+.2f} = {best['pl']:+,.2f} USD")
o(f"  Schlechtester Trade : T{worst['nr']} {worst['tag']} {worst['dir']} "
  f"R {worst['r']:+.2f} = {worst['pl']:+,.2f} USD")
o(f"  Avg Gewinner        : {sum_w/len(w):+,.2f} USD | Avg Verlierer {sum_l/len(l):+,.2f} USD")
o("-" * 110)
o("STATISTIK-AUSBAU (maxDD-Episode, laengste Serien, CRV):")
o(f"  Trefferquote              : {len(w)}/{len(trades)} = {wr:.2f} % Gewinner")
o(f"  CRV (Chance-Risiko-Verh.) : {crv:.2f}  =  Avg Gewinn {sum_w/len(w):,.2f} USD : "
  f"Avg Verlust {abs(sum_l/len(l)):,.2f} USD")
o(f"  Avg R je Trade            : {avg_r:+.2f}R (Erwartungswert {avg_r*RISK_USD:+,.2f} USD/Trade)")
o(f"  Laengste Verlustserie     : {vl['len']} Trades (T{vl['von']}-T{vl['bis']}, "
  f"{vl['von_tag']}..{vl['bis_tag']}), Summe {vl['r']:+.2f}R = {vl['usd']:+,.2f} USD")
o(f"  Laengste Gewinnserie      : {wg['len']} Trades (T{wg['von']}-T{wg['bis']}, "
  f"{wg['von_tag']}..{wg['bis_tag']}), Summe {wg['r']:+.2f}R = {wg['usd']:+,.2f} USD")
o(f"  Max-DD-Episode            : {tief['usd']:,.2f} USD ({tief['pct']:.2f} % vom Peak "
  f"{peak_t['equity']:,.2f} USD)")
o(f"    Peak vor der DD         : T{peak_t['nr']} {peak_t['tag']} {peak_t['zeit']} {peak_t['dir']} "
  f"{peak_t['r']:+.2f}R -> Equity {peak_t['equity']:,.2f} USD")
o(f"    Tief der DD             : T{tief_t['nr']} {tief_t['tag']} {tief_t['zeit']} {tief_t['dir']} "
  f"{tief_t['r']:+.2f}R -> Equity {tief_t['equity']:,.2f} USD")
o(f"    Dauer                   : {len(ep)} Trades (T{ep[0]['nr']}..T{ep[-1]['nr']}, "
  f"{ep[0]['tag']}..{ep[-1]['tag']})")
o(f"    Zusammensetzung         : {len(ep_v)} Verlierer ({sum(x['r'] for x in ep_v):+.2f}R) / "
  f"{len(ep_g)} Gewinner ({sum(x['r'] for x in ep_g):+.2f}R) -> Netto "
  f"{sum(x['r'] for x in ep):+.2f}R")
if erhol_i is not None:
    o(f"    Erholung                : neues Hoch bei T{trades[erhol_i]['nr']} {trades[erhol_i]['tag']} "
      f"({erhol_i - tief['i']} Trades nach dem Tief)")
else:
    o("    Erholung                : kein neues Hoch bis Fenster-Ende")
o("  Top-DD-Episoden (USD-tiefste; Muster 'Gewinn, dann SL-Serie'):")
for k, (pi_, ti_, u, pc) in enumerate(top3, 1):
    pk_, tk_ = trades[pi_], trades[ti_]
    seg = trades[pi_ + 1: ti_ + 1]
    nv_ = sum(1 for x in seg if x["r"] < 0)
    ng_ = sum(1 for x in seg if x["r"] > 0)
    o(f"    {k}) {u:,.2f} USD ({pc:.2f} %)  T{pk_['nr']} {pk_['tag']} -> T{tk_['nr']} {tk_['tag']}  "
      f"| {len(seg)} Trades ({nv_} Verlierer / {ng_} Gewinner)")
o("  Hinweis: Die tiefste DD entsteht NICHT durch einzelne Trades, sondern durch")
o("  SL-Serien nach Gewinnphasen (siehe Episoden oben) - genau das Muster")
o("  'grosser Gewinn, dann SLs' (wiederkehrendes Muster, siehe Episoden oben).")
o("-" * 110)
o("")
o("Hinweis: Equity beginnt bei 0.00 USD (reiner P/L-Verlauf, kein Kapital-")
o("Einsatz modelliert). 1R = 100 USD unabhaengig vom Entry-Preis; die "
  "Positionsgroesse skaliert invers zum SL-Abstand (0.45% vom Entry), damit "
  "jeder Trade exakt 100 USD Risiko traegt. Kein Zinseszinseffekt (fixes R).")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print(f"OK -> {OUT} ({len(out)} Zeilen)")
print(f"End-Equity {equity:+,.2f} USD | Max DD {max_dd_usd:,.2f} USD ({max_dd_pct:.2f}%) | "
      f"PF {pf_usd:.2f} | Best T{best['nr']} {best['pl']:+,.2f} | Worst T{worst['nr']} {worst['pl']:+,.2f}")
