# -*- coding: utf-8 -*-
"""Ausreisser-Konzentration und Payoff-Struktur im arretierten Bestand.

Frage: Woher kommt das positive Gesamtergebnis? Traegt die Breite des
Samples, oder tragen einzelne Geschaefte? Und: ist die Payoff-Form das, was
die Konstruktion zu sein behauptet (Konter an einer Abweisung) oder etwas
anderes (Trendlauf in Verkleidung)?

Read-only, kein Motoreingriff.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
for p in (str(ROOT), str(TEST)):
    if p not in sys.path:
        sys.path.insert(0, p)

spec = importlib.util.spec_from_file_location(
    "v022_ausreisser", TEST / "tmp_kanten_engine_v022_replay.py")
V = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules["v022_ausreisser"] = V
spec.loader.exec_module(V)  # type: ignore[union-attr]

import pandas as pd  # noqa: E402

B = V._engine()
FENSTER = (("MAI", "2026-05-01", "2026-06-01"),
           ("JUN", "2026-06-01", "2026-07-01"),
           ("JUL", "2026-07-01", "2026-08-01"),
           ("AUG_BASE", "AUG", "AUG"))
SOLL = {"MAI": (35, 38.318126), "JUN": (28, -11.421155),
        "JUL": (21, -4.325355), "AUG_BASE": (14, 42.450970)}


def _scan(start: str, ende: str) -> Dict[str, Any]:
    if start == "AUG":
        s = B._se_scan("AUG", B.StraightEdgeHarnessKonfiguration())
        s = copy.deepcopy(s)
        s["box_end_bar"] = int(s["n"])
        return s
    B.FENSTER["LAB"] = (start, ende)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    orig = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        s = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = orig  # type: ignore
    s = copy.deepcopy(s)
    s["box_end_bar"] = int(n)
    return s


alle: List[Tuple[str, Any, str]] = []
print("=" * 104)
print("AUSREISSER-KONZENTRATION UND PAYOFF-STRUKTUR")
print("=" * 104)
for fid, start, ende in FENSTER:
    sc = _scan(start, ende)
    ts = pd.to_datetime(sc["d"]["ts"]).dt.strftime("%Y-%m-%d").to_numpy()
    setups, _ = V._se_trades_v022(copy.deepcopy(sc), V.V022KantenKonfiguration())
    setups = sorted(setups, key=lambda t: int(t.entry_bar))
    rr = [float(t.r) for t in setups]
    soll_n, soll_r = SOLL[fid]
    assert (len(rr), round(sum(rr), 6)) == (soll_n, round(soll_r, 6)), fid

    geordnet = sorted(setups, key=lambda t: -float(t.r))
    total = round(sum(rr), 6)
    verlierer = [r for r in rr if r < 0]
    gewinner = [r for r in rr if r > 0]
    print()
    print(f"{fid}  {len(rr)} Trades  SumR {total:+.6f}")
    print(f"   Gewinner {len(gewinner):>2} ({sum(gewinner):+9.4f})   "
          f"Verlierer {len(verlierer):>2} ({sum(verlierer):+9.4f})")
    print(f"   Vollstopps (-1.000): {sum(1 for r in rr if abs(r + 1.0) < 1e-9)}"
          f"/{len(rr)}  = {sum(1 for r in rr if abs(r + 1.0) < 1e-9) / len(rr) * 100:.0f} %")
    for k in (1, 2, 3):
        oben = sum(float(t.r) for t in geordnet[:k])
        rest = round(total - oben, 6)
        print(f"   Top-{k}: {oben:+9.4f}  ->  Rest ohne Top-{k}: {rest:+9.4f}"
              f"   {'' if rest > 0 else '  <== kippt negativ'}")
    print(f"   groesster Einzelgewinn {float(geordnet[0].r):+.4f} R  "
          f"(K{int(geordnet[0].kid)}, {ts[int(geordnet[0].entry_bar)]})  "
          f"= {float(geordnet[0].r) / sum(gewinner) * 100:.1f} % der Gewinnsumme")
    for t in setups:
        alle.append((fid, t, ts[int(t.entry_bar)]))

rr_alle = [float(t.r) for _, t, _ in alle]
ges = round(sum(rr_alle), 6)
geordnet_a = sorted(alle, key=lambda x: -float(x[1].r))
print()
print("=" * 104)
print(f"GESAMT  {len(rr_alle)} Trades  SumR {ges:+.6f}")
print(f"   Vollstopps {sum(1 for r in rr_alle if abs(r + 1.0) < 1e-9)}/{len(rr_alle)}"
      f" = {sum(1 for r in rr_alle if abs(r + 1.0) < 1e-9) / len(rr_alle) * 100:.0f} %"
      f"   Flat/Teil {sum(1 for r in rr_alle if -1.0 < r < 0)}")
for k in (1, 2, 3, 5, 10):
    oben = sum(float(x[1].r) for x in geordnet_a[:k])
    rest = round(ges - oben, 6)
    print(f"   Top-{k:<2} entfernt: {oben:+9.4f}  ->  Rest {rest:+9.4f}"
          f"   {'' if rest > 0 else '  <== NEGATIV'}")
print()
print("   Die fuenf groessten Einzelgewinne:")
for fid, t, d in geordnet_a[:5]:
    print(f"     {fid:<9s} {d}  K{int(t.kid):<3} {t.richtung:5s} "
          f"entry {float(t.entry):.3f} sl {float(t.sl):.3f} tp2 {float(t.tp2):.3f} "
          f"-> {float(t.r):+8.4f} R  ({t.grund1}/{t.grund2})")
print()
print("   Verteilung der R-Ergebnisse:")
for lo_, hi_, lbl in ((-99, -0.999, "Vollstopp -1.0"), (-0.999, -0.0001, "Teilverlust"),
                      (-0.0001, 0.0001, "flat"), (0.0001, 1.0, "klein 0..1"),
                      (1.0, 3.0, "1..3"), (3.0, 99, ">3 (Trendlauf)")):
    c = sum(1 for r in rr_alle if lo_ <= r < hi_)
    print(f"     {lbl:18s} {c:>3}  {c / len(rr_alle) * 100:5.1f} %")
print()
print("=" * 104)
