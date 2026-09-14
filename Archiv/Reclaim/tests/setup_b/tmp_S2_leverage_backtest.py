# -*- coding: utf-8 -*-
"""S2-Zinseszins-Hochrechnung mit Hebel-500-Einordnung (Baseline phasen_volumen_profil.py).

Modell (User-Wahl): Zinseszins. Startkapital 10.000 USD (1% = 100 USD, konsistent
zur bisherigen Fix-Risk-Rechnung). Pro Trade wird ein konstanter Prozentsatz p des
AKTUELLEN Kontos riskiert; P/L = R_i * (p * Equity_{i-1}); Equity laeuft kumuliert,
am Ende Summierung (End-Equity, Gesamtgewinn USD und %).

Hebel 500 wird als Obergrenze mitgefuehrt: Notional = Risiko / SL_PCT (0.45 %),
Margin = Notional / 500. Bei p = 1 % ist der effektiv genutzte Hebel nur
Notional/Equity = p/0.0045 = 2.22x -> der 500er-Hebel bindet NIE als Limit
(er wuerde erst bei p = 225 % Risikoquote voll ausgenutzt). Damit ist klar: Der
treibende Faktor ist die Risikoquote p, nicht der Hebel.

"Im Guten wie im Schlechten": Sensitivitaetstabelle p = 0.25 % .. 100 % mit
End-Equity, Rendite, MaxDD und Totalverlust-Punkt (bei hohen p stirbt das Konto,
sobald ein -1R-Trade kommt).

Datenbasis: test/tmp_S2_monatslauf_2025-*.txt (10 Monatsberichte, 210 Trades,
+99.90R gerundet; exakt +99.88R = Baseline S2, verifiziert).
Rein lesend (I3/I4). Ausgabe: test/tmp_S2_leverage_backtest.txt
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

START_EQ = 10_000.0
SL_PCT = 0.0045
LEVERAGE = 500
P_MAIN = 0.01  # 1 % Hauptlauf
OUT = Path("test/tmp_S2_leverage_backtest.txt")

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

# ---------------------------------------------------------------- Zinseszins-Simulation
def run(pct: float, start: float = START_EQ):
    """Simuliert alle Trades mit Risikoquote pct. Liefert Zeilen, Equity-Ende,
    Gesamtgewinn, MaxDD, Pleite-Info (None wenn ueberlebt)."""
    eq = start
    peak = start
    max_dd_usd = 0.0
    max_dd_pct = 0.0  # groesster RELATIVER Rueckgang vom jeweiligen Peak (korrekte MaxDD-Definition)
    dd_tief_nr = None
    month_end: dict[str, float] = {}
    rows: list[dict] = []
    busted: str | None = None
    for t in trades:
        risk = eq * pct
        pl = t["r"] * risk
        eq += pl
        rows.append({"nr": t["nr"], "tag": t["tag"], "zeit": t["zeit"], "dir": t["dir"],
                     "entry": t["entry"], "r": t["r"], "risk": risk, "pl": pl,
                     "eq": eq, "equity": eq})
        if eq > peak:
            peak = eq
        dd = eq - peak
        dd_pct_t = dd / peak * 100.0 if peak > 0 else 0.0
        # relativer MaxDD unabhaengig vom USD-Betrag (sonst dominieren spaete
        # grosse Konten und fruehere prozentual tiefere DDs gehen verloren)
        if dd_pct_t < max_dd_pct:
            max_dd_pct = dd_pct_t
            max_dd_usd = dd
            dd_tief_nr = t["nr"]
        monat = f"{t['tag'][6:10]}-{t['tag'][3:5]}"
        month_end[monat] = eq
        if eq <= 0:
            busted = f"T{t['nr']} {t['tag']} (R {t['r']:+.2f})"
            break
    return rows, eq, eq - start, max_dd_usd, max_dd_pct, dd_tief_nr, month_end, busted


def eff_hebel(pct: float) -> float:
    """Notional/Equity bei Risikoquote pct (SL 0.45 %)."""
    return pct / SL_PCT


def margin_anteil(pct: float) -> float:
    """Margin / Equity bei Hebel 500: Notional/500 / Equity."""
    return pct / SL_PCT / LEVERAGE


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


def _maxdd_episode(tr, mode: str = "pct"):
    """Tiefste DD-Episode. mode 'pct': min dd_pct (konsistent zur KENNZAHLEN-
    Zeile der Zinseszins-Simulation), mode 'usd': min dd_usd."""
    peak = tr[0]["equity"] - tr[0]["pl"]  # Equity vor Trade 1 (Startkapital)
    peak_i = -1
    tief = {"i": None, "usd": 0.0, "pct": 0.0, "peak_i": None}
    for i, t in enumerate(tr):
        if t["equity"] > peak:
            peak = t["equity"]
            peak_i = i
        dd_usd = t["equity"] - peak
        dd_pct = dd_usd / peak * 100.0 if peak > 0 else 0.0
        if tief["i"] is None:
            tief = {"i": i, "usd": dd_usd, "pct": dd_pct, "peak_i": peak_i}
        elif mode == "pct" and dd_pct < tief["pct"] - 1e-12:
            tief = {"i": i, "usd": dd_usd, "pct": dd_pct, "peak_i": peak_i}
        elif mode == "usd" and dd_usd < tief["usd"] - 1e-9:
            tief = {"i": i, "usd": dd_usd, "pct": dd_pct, "peak_i": peak_i}
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


# ---------------------------------------------------------------- Report
out = []
def o(*a): out.append(" ".join(str(x) for x in a))

o("=" * 110)
o("S2 ZINSESZINS-HOCHRECHNUNG MIT HEBEL-500-EINORDNUNG (Baseline)")
o("=" * 110)
o(f"Fenster            : 2025-01-01 .. 2025-12-01 (210 Trades, Summe {sum(t['r'] for t in trades):+.2f}R)")
o(f"Startkapital       : {START_EQ:,.2f} USD")
o(f"Modell             : Zinseszins, Risiko = {P_MAIN*100:.1f} % des aktuellen Kontos pro Trade")
o(f"SL-Kalibrierung    : SL_PCT {SL_PCT*100:.2f}% vom Entry (Notional = Risiko / {SL_PCT*100:.2f}%)")
o(f"Hebel-Obergrenze   : {LEVERAGE}:1 (Margin = Notional / {LEVERAGE}; nur relevant, wenn sie bindet)")
o(f"Kosten             : KEINE (kein Spread, keine Slippage, keine Kommission)")
o(f"Reihenfolge        : chronologisch, trade-fuer-trade, Gewinne werden reinvestiert")
o("-" * 110)
o("HEBEL-EINORDNUNG (Hauptlauf p = 1 %):")
o(f"  Effektiv genutzter Hebel : Notional/Equity = p/SL_PCT = {eff_hebel(P_MAIN):.2f}x  "
  f"(konstant, unabhaengig vom Kontostand)")
o(f"  Benoetigte Margin        : {margin_anteil(P_MAIN)*100:.4f} % des Kontos  "
  f"(z. B. Start: Notional {START_EQ*P_MAIN/SL_PCT:,.0f} USD -> Margin "
  f"{START_EQ*P_MAIN/SL_PCT/LEVERAGE:,.2f} USD)")
o(f"  Fazit                    : Der {LEVERAGE}-Hebel bindet bei p = {P_MAIN*100:.0f} % NIE "
  f"(voll ausgenutzt erst bei p = {SL_PCT*LEVERAGE*100:.0f} % Risikoquote).")
o(f"  Treibender Faktor ist die Risikoquote p - siehe Sensitivitaetstabelle unten.")
o("-" * 110)

rows, eq_end, profit, mdd_usd, mdd_pct, dd_nr, month_end, busted = run(P_MAIN)

# maxDD-Episode + Top-3 + laengste Serien (fuer Report, p = 1 %-Pfad)
tief = _maxdd_episode(rows, mode="pct")
assert rows[tief["i"]]["nr"] == dd_nr and abs(tief["pct"] - mdd_pct) < 1e-6
peak_t = rows[tief["peak_i"]]
tief_t = rows[tief["i"]]
ep = rows[tief["peak_i"] + 1: tief["i"] + 1]
ep_v = [x for x in ep if x["r"] < 0]
ep_g = [x for x in ep if x["r"] > 0]
erhol_i = next((i for i in range(tief["i"] + 1, len(rows))
                if rows[i]["equity"] >= peak_t["equity"]), None)
vl = _laengste_serie(rows, verlust=True)
wg = _laengste_serie(rows, verlust=False)
top3 = sorted(_dd_episoden(rows), key=lambda e: e[3])[:3]  # tiefste (%) zuerst
wr = sum(1 for t in rows if t["r"] > 0) / len(rows) * 100.0
avg_r = sum(t["r"] for t in rows) / len(rows)

o("TRADE-VERLAUF (Zinseszins, p = 1 %):")
o(f"{'Nr':>4} {'Zeit (UTC)':<17} {'Dir':<5} {'Entry':>8} {'R':>7} "
  f"{'Risiko $':>10} {'P/L $':>12} {'Equity $':>14}")
o("-" * 110)
for r_ in rows:
    o(f"{r_['nr']:>4} {r_['tag']} {r_['zeit']} {r_['dir']:<5} {r_['entry']:>8.3f} "
      f"{r_['r']:>+7.2f} {r_['risk']:>10.2f} {r_['pl']:>+12.2f} {r_['eq']:>14.2f}")
if busted:
    o(f"  >>> TOTALVERLUST bei {busted} (Konto <= 0, Simulation abgebrochen)")
o("-" * 110)
o("EQUITY-ENDE JE MONAT (p = 1 %):")
for m in sorted(month_end):
    o(f"  {m}: {month_end[m]:>+14.2f} USD")
o("-" * 110)
o("KENNZAHLEN (p = 1 %, Zinseszins):")
o(f"  End-Equity / Summierung : {eq_end:>14,.2f} USD")
o(f"  Gesamtgewinn            : {profit:>+14,.2f} USD  ({profit/START_EQ*100:>+10.2f} % auf Startkapital)")
o(f"  Max Drawdown            : {mdd_usd:>14,.2f} USD ({mdd_pct:.2f} % vom Peak, "
  f"Tief T{dd_nr} {tief_t['tag']})")
_lin_usd = sum(t["r"] for t in trades) * 100.0
o(f"  Vergleich linear (fix)  : {_lin_usd:+,.2f} USD ({sum(t["r"] for t in trades):+.2f}R x 100 USD, ohne Zinseszins)")
o(f"  Zinseszins-Vorteil      : {profit - _lin_usd:+,.2f} USD gegenueber fix 100 USD/Trade")
o("-" * 110)
o("STATISTIK-AUSBAU (maxDD-Episode, laengste Serien, CRV; USD = p=1%-Pfad):")
o(f"  Trefferquote              : {wr:.2f} % Gewinner (R-basiert, gilt fuer jedes p)")
o(f"  Avg R je Trade            : {avg_r:+.2f}R (Erwartungswert, R-basiert)")
o(f"  CRV (Chance-Risiko-Verh.) : R-basiert identisch zum linearen Report (CRV = 3.30)")
o(f"  Laengste Verlustserie     : {vl['len']} Trades (T{vl['von']}-T{vl['bis']}, "
  f"{vl['von_tag']}..{vl['bis_tag']}), Summe {vl['r']:+.2f}R = {vl['usd']:+,.2f} USD (p=1%-Pfad)")
o(f"  Laengste Gewinnserie      : {wg['len']} Trades (T{wg['von']}-T{wg['bis']}, "
  f"{wg['von_tag']}..{wg['bis_tag']}), Summe {wg['r']:+.2f}R = {wg['usd']:+,.2f} USD (p=1%-Pfad)")
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
    o(f"    Erholung                : neues Hoch bei T{rows[erhol_i]['nr']} {rows[erhol_i]['tag']} "
      f"({erhol_i - tief['i']} Trades nach dem Tief)")
else:
    o("    Erholung                : kein neues Hoch bis Fenster-Ende")
o("  Top-DD-Episoden (relativ, p=1%-Pfad; Muster 'Gewinn, dann SL-Serie'):")
for k, (pi_, ti_, u, pc) in enumerate(top3, 1):
    pk_, tk_ = rows[pi_], rows[ti_]
    seg = rows[pi_ + 1: ti_ + 1]
    nv_ = sum(1 for x in seg if x["r"] < 0)
    ng_ = sum(1 for x in seg if x["r"] > 0)
    o(f"    {k}) {pc:.2f} % ({u:,.2f} USD)  T{pk_['nr']} {pk_['tag']} -> T{tk_['nr']} {tk_['tag']}  "
      f"| {len(seg)} Trades ({nv_} Verlierer / {ng_} Gewinner)")
o("  Hinweis: Die tiefste DD entsteht NICHT durch einzelne Trades, sondern durch")
o("  SL-Serien nach Gewinnphasen (siehe Episoden oben) - genau das Muster")
o("  'grosser Gewinn, dann SLs'. R-basierte Kennzahlen (Serien, CRV, Avg R)")
o("  sind p-unabhaengig; USD-Betraege gelten fuer den p = 1 %-Hauptlauf.")

# ---------------------------------------------------------------- Sensitivitaetstabelle
o("-" * 110)
o("SENSITIVITAET 'IM GUTEN WIE IM SCHLECHTEN' (Risikoquote p pro Trade):")
o(f"{'p':>6} {'Hebel':>6} {'Margin':>8} {'End-Equity':>14} {'Gesamtgewinn':>14} "
  f"{'Rendite':>10} {'MaxDD %':>8} {'Schicksal':>34}")
o("-" * 110)
for p in (0.0025, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.00):
    _, e, g, _, dd_p, _, _, b = run(p)
    if b:
        fate = f"TOTALVERLUST bei {b}"
    elif e < 1.0:
        fate = "TOTALVERLUST (End-Equity < 1 USD)"
    else:
        fate = "ueberlebt"
    dd_txt = f"{dd_p:.2f}" if abs(dd_p) < 99.9 else f"{dd_p:.3f}"
    o(f"{p*100:>5.2f}% {eff_hebel(p):>6.1f}x {margin_anteil(p)*100:>7.2f}% "
      f"{e:>14,.2f} {g:>+14,.2f} {g/START_EQ*100:>+9.1f}% {dd_txt:>8}% {fate:>34}")
o("-" * 110)
o("Lesart: Die Hebel-Spalte zeigt den tatsaechlich genutzten Hebel (Notional/Konto).")
o("Erst p = 50 % nutzt ~111x, p = 100 % ~222x des 500er-Maximums - bei p = 100 %")
o("loescht bereits der erste -1R-Trade (T2, 02.01.2025) das komplette Konto.")
o("Hebel 500 erlaubt physisch bis p = 225 % (Margin = 100 % des Kontos) - weit")
o("jenseits jeder Vernunft: JEDER Verlust-Trade wuerde das Konto ueberschulden.")
o("")
o("Hinweis: Kein Zinseszinseffekt auf Verluste ueber den SL hinaus (SL begrenzt je")
o("Trade auf p % des Kontos). Kein Kapitalabfluss (Entnahmen/Einzahlungen).")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print(f"OK -> {OUT} ({len(out)} Zeilen)")
print(f"p=1%: End {eq_end:,.2f} USD | Gewinn {profit:+,.2f} ({profit/START_EQ*100:+.2f}%) | "
      f"MaxDD {mdd_usd:,.2f} ({mdd_pct:.2f}%) | Monate {sorted(month_end)}")
