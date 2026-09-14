# -*- coding: utf-8 -*-
"""Faktenpruefung der Juli-Beobachtungen (nur Juli 2026, read-only).

Prueft vier Behauptungen aus der Handelsansicht:

  J1  Niveau-Lage: lagen 59.4 / 60.4 / 62.3 ueberhaupt im Juli-Preisbereich?
  J2  Die 21 Juli-Trades: je Trade die HANDELSSPANNE (entry -> tp2) und der
      Stop -- in USD und in Prozent. Gibt es ueberhaupt eine Spanne?
  J3  Der Kern: ist eine "Kante" ein NIVEAU? Gemessen wird die Streuung der
      Dochte, aus denen die Kante gemittelt ist (``e.wicks``). Ein Niveau hat
      eine schmale Streuung; ein Mittelwert ueber strukturell verschiedene
      Preise hat eine breite.
  J4  Datumsverteilung der Trades (6.7. / 8.7.) und Mehrfachkonter je Kante.

Kein Motorwert geaendert, kein Handelseingriff.
"""
from __future__ import annotations

import copy
import importlib.util
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
for p in (str(ROOT), str(TEST)):
    if p not in sys.path:
        sys.path.insert(0, p)

spec = importlib.util.spec_from_file_location(
    "v022_juli", TEST / "tmp_kanten_engine_v022_replay.py")
V = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules["v022_juli"] = V
spec.loader.exec_module(V)  # type: ignore[union-attr]

import pandas as pd  # noqa: E402

B = V._engine()
hcfg = B.StraightEdgeHarnessKonfiguration()

START, ENDE = "2026-07-01", "2026-08-01"
B.FENSTER["LAB"] = (START, ENDE)
try:
    d = B._lade_fenster("LAB")
finally:
    del B.FENSTER["LAB"]
n = int(len(d))
orig = B._lade_fenster
B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
try:
    scan = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
finally:
    B._lade_fenster = orig  # type: ignore
scan = copy.deepcopy(scan)
scan["box_end_bar"] = int(n)

ts = pd.to_datetime(scan["d"]["ts"]).dt.strftime("%Y-%m-%d").to_numpy()
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
cl = scan["d"]["close"].to_numpy(dtype=float)

print("=" * 100)
print(f"JULI 2026 (BKZ)  Bars {n}  {ts[0]} .. {ts[-1]}  box_end {scan['box_end_bar']}")
print("=" * 100)

# ------------------------------------------------------------------ J1 Niveau-Lage
print()
print("J1  NIVEAU-LAGE")
print(f"    Preisbereich      low {lo.min():.4f} .. high {hi.max():.4f}"
      f"   (Spanne {hi.max() - lo.min():.4f} USD)")
print(f"    Schluss erst/letzt {cl[0]:.4f} .. {cl[-1]:.4f}"
      f"   ({cl[-1] - cl[0]:+.4f} USD Monatsbewegung)")
for niveau, was in ((59.4, "dein Niveau"), (60.4, "dein Niveau"), (62.3, "Abpraller 6.7.")):
    im_band = lo.min() <= niveau <= hi.max()
    # wie oft wurde das Niveau beruehrt? (Bar-Range enthaelt es)
    beruehrt = int(((lo <= niveau) & (hi >= niveau)).sum())
    nah = int((abs(cl - niveau) <= 0.15).sum())
    print(f"    {niveau:>6.1f} ({was:14s})  im Bereich: {str(im_band):5s}  "
          f"als Range beruehrt: {beruehrt:4d} Bars   Schluss <=0.15 USD: {nah:4d}")

# ------------------------------------------------------------------ Trades
setups, stats = V._se_trades_v022(copy.deepcopy(scan), V.V022KantenKonfiguration())
setups = sorted(setups, key=lambda t: int(t.entry_bar))
print()
print(f"    21-Trades-Soll laut Paritaetslauf: 21  ->  ist {len(setups)}")

print()
print("J2  HANDELSSPANNEN DER JULI-TRADES (entry -> tp2)")
print(f"    {'#':>2} {'Datum':10s} {'R':5s} {'kd':>4} {'entry':>8} {'poc':>8} "
      f"{'tp2':>8} {'sl':>8} {'Spanne':>7} {'%':>6} {'Stop':>6} {'%':>6} {'R':>7}")
spannen: List[float] = []
stops: List[float] = []
pct_spannen: List[float] = []
for i, t in enumerate(setups, 1):
    spanne = abs(float(t.tp2) - float(t.entry))
    stop = abs(float(t.sl) - float(t.entry))
    ref = float(t.entry)
    spannen.append(spanne)
    stops.append(stop)
    pct_spannen.append(spanne / ref * 100.0)
    print(f"    {i:>2} {ts[int(t.entry_bar)]:10s} {t.richtung:5s} {t.kid:>4} "
          f"{ref:>8.4f} {float(t.poc):>8.4f} {float(t.tp2):>8.4f} "
          f"{float(t.sl):>8.4f} {spanne:>7.4f} {spanne / ref * 100:>6.3f} "
          f"{stop:>6.4f} {stop / ref * 100:>6.3f} {float(t.r):>+7.3f}")
print(f"    {'Median':>10s}  Spanne {statistics.median(spannen):.4f} USD "
      f"({statistics.median(pct_spannen):.3f} %)   "
      f"Stop {statistics.median(stops):.4f} USD")
print(f"    {'Mittel':>10s}  Spanne {statistics.mean(spannen):.4f} USD  "
      f"Stop {statistics.mean(stops):.4f} USD")
print(f"    Spannen < 0,50 USD: {sum(1 for s in spannen if s < 0.50)}/{len(spannen)}"
      f"   < 1,00 USD: {sum(1 for s in spannen if s < 1.00)}/{len(spannen)}"
      f"   < 1,50 USD: {sum(1 for s in spannen if s < 1.50)}/{len(spannen)}")
print(f"    Bandmasse: touch_band_pct {hcfg.touch_band_pct} % "
      f"(= {hcfg.touch_band_pct / 100 * float(cl[-1]):.4f} USD bei {cl[-1]:.2f})"
      f"  |  V3_TOUCH_BAND_PCT {B.V3_TOUCH_BAND_PCT} %"
      f" (= {B.V3_TOUCH_BAND_PCT / 100 * float(cl[-1]):.4f} USD)")

# ------------------------------------------------------------------ J3 Kern: ist eine Kante ein Niveau?
alle: List[Any] = list(scan["edges"]) + list(scan["seeds"])
kbox = int(scan["box_end_bar"]) - 3
print()
print("J3  IST EINE 'KANTE' EIN NIVEAU? -- Streuung der Dochte je Kante")
print(f"    {len(alle)} Kanten (edges {len(scan['edges'])} + seeds {len(scan['seeds'])})")
print(f"    {'kd':>4} {'Seite':6s} {'Dochte':>6} {'min':>8} {'max':>8} "
      f"{'Streuung':>9} {'%':>6} {'Basis':>8} {'ber. bei k':>10}  {'gehandelt'}")
print("    " + "-" * 92)
gehandelt_kids = {int(t.kid) for t in setups}
breit: List[float] = []
for e in sorted(alle, key=lambda x: (x.seite, x.kid)):
    w = [(int(b), float(px)) for b, px in e.wicks]
    if not w:
        continue
    px = [p for _, p in w]
    streuung = max(px) - min(px)
    basis = float(e.basis)
    breit.append(streuung)
    print(f"    {int(e.kid):>4} {e.seite:6s} {len(w):>6} {min(px):>8.4f} "
          f"{max(px):>8.4f} {streuung:>9.4f} {streuung / basis * 100:>6.3f} "
          f"{basis:>8.4f} {float(e.basis_bei(kbox)):>10.4f}  "
          f"{'JA' if int(e.kid) in gehandelt_kids else ''}")
if breit:
    print(f"    Median Docht-Streuung {statistics.median(breit):.4f} USD  "
          f"Mittel {statistics.mean(breit):.4f} USD  max {max(breit):.4f} USD")
    print(f"    Kanten mit Streuung > 1,00 USD: {sum(1 for s in breit if s > 1.00)}"
          f"/{len(breit)}   > 2,00 USD: {sum(1 for s in breit if s > 2.00)}/{len(breit)}")

# ------------------------------------------------------------------ J4 Datumsverteilung
print()
print("J4  TRADES JE DATUM + MEHRFACHKONTER")
je_datum: Dict[str, List[Any]] = {}
for t in setups:
    je_datum.setdefault(ts[int(t.entry_bar)], []).append(t)
for dat in sorted(je_datum):
    grp = je_datum[dat]
    lp = ", ".join(f"K{int(t.kid)}@{float(t.entry):.2f}/{t.richtung[:1]}"
                   f"({float(t.r):+.2f})" for t in grp)
    print(f"    {dat}  {len(grp)}x   {lp}")
je_kante: Dict[int, int] = {}
for t in setups:
    je_kante[int(t.kid)] = je_kante.get(int(t.kid), 0) + 1
mehrfach = {k: v for k, v in je_kante.items() if v > 1}
print(f"    Kanten mit Mehrfachkonter: {len(mehrfach)} von {len(je_kante)} -> {mehrfach}")
sum_r_verlust = round(sum(float(t.r) for t in setups if float(t.r) < 0), 6)
sum_r_gewinn = round(sum(float(t.r) for t in setups if float(t.r) > 0), 6)
print(f"    SumR Gewinner {sum_r_gewinn:+.6f}  Verlierer {sum_r_verlust:+.6f}  "
      f"Gesamt {round(sum(float(t.r) for t in setups), 6):+.6f}")
print(f"    stats: kein_raum {stats.get('kein_raum')}  kein_gegner "
      f"{stats.get('kein_gegner')}  quartil_blockiert "
      f"{stats.get('quartil_blockiert')}  promotionen {stats.get('promotionen')}")
print()
print("=" * 100)
