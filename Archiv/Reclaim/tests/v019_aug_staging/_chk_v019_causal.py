# -*- coding: utf-8 -*-
"""READ-ONLY Check (V019-Audit): kausales Segment-Etikett vs. arretierte Konstante.

Frage: stimmt das aus dem Markt KAUSAL ableitbare Paar (decke_kid, boden_kid)
mit den im Adapter eingefrorenen A1/A2-Etiketten ueberein - oder enthaelt die
Arretierung zukunftabhaengige Verschmelzungs-Entscheidungen (Segmentlaenge)?

Kein Schreiben, kein Engine-Eingriff: nur _se_scan + Adapter-Konstanten.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "tmp_kanten_engine_replay", str(ROOT / "test" / "tmp_kanten_engine_replay.py"))
eng = importlib.util.module_from_spec(spec)
sys.modules["tmp_kanten_engine_replay"] = eng
spec.loader.exec_module(eng)

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V019, P9_BODEN_RECLAIM,
)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n
alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {e.kid: e for e in alle}
LIVE = cfg.wall_live_bars

P9A, P9B = P9_BODEN_RECLAIM.start_bar, P9_BODEN_RECLAIM.end_bar


def lebt_kausal(e, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]
    return bool(b) and max(b) >= k - LIVE


def ecken(k: int):
    oben = [e for e in alle if e.seite == "OBEN" and lebt_kausal(e, k)]
    unten = [e for e in alle if e.seite == "UNTEN" and lebt_kausal(e, k)]
    o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
    u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
    return (o.kid if o else None), (u.kid if u else None)


frozen = {}
for s in ADAPTER_V019.segmente:
    for k in range(s.start_bar, s.end_bar + 1):
        frozen[k] = (s.decke.kid, s.boden.kid, s.phasen_id)

print("=" * 100)
print("A. KAUSALES PAAR vs. ARRETIERTES ETIKETT (ab Bar 1021)")
print("=" * 100)
prev = None
runs = []
for k in range(1021, n):
    cur = ecken(k)
    if prev is None or cur != prev[2]:
        runs.append([k, k, cur])
        prev = runs[-1]
    else:
        prev[1] = k
    prev = prev
mis = []
for a, b, cur in runs:
    fr = frozen.get(a, None)
    ok = (fr is not None and (fr[0], fr[1]) == cur)
    if not ok:
        mis.append((a, b, cur, fr))
    print(f"  {a:>5}..{b:<5} kausal=K{cur[0] if cur[0] is not None else '-'}"
          f"/K{cur[1] if cur[1] is not None else '-'}"
          f"   arretiert={('K%d/K%d (%s)' % fr) if fr else 'Luecke/ausserhalb'}")

print("")
print("B. ABWEICHENDE BARS (kausal != arretiert):")
for a, b, cur, fr in mis:
    print(f"  {a}..{b}  ({b - a + 1} Bars)  kausal K{cur[0]}/K{cur[1]}"
          f" vs. arretiert "
          f"{(('K%d/K%d' % (fr[0], fr[1])) if fr else 'None')}")

print("")
print("C. ZIELZONEN-TRADES (aus Protokoll) gegen die Abweichungsmenge:")
ziel_bars = {1075: 62, 1122: 73, 1172: 82, 1211: 76, 1268: 76, 1272: 73,
             1280: 76}
for k in sorted(ziel_bars):
    cur = ecken(k)
    fr = frozen.get(k, None)
    tag = "KAUSAL-FREMD" if (fr is None or (fr[0], fr[1]) != cur) else "konsistent"
    print(f"  Bar {k:>4} (K{ziel_bars[k]:>3})  kausal=K{cur[0]}/K{cur[1]}"
          f"  arretiert={('K%d/K%d' % (fr[:2])) if fr else '-'}   -> {tag}")

print("")
print("D. Relevanz der Etikett-Abweichung fuer den Zielpreis (A1):")
a1 = ADAPTER_V019.segmente[1]
print(f"  A1 {a1.start_bar}..{a1.end_bar}: ziel_preis_short="
      f"{a1.ziel_preis_short:.4f} (Boden K{a1.boden.kid} "
      f"basis_bei({a1.start_bar})={katalog[a1.boden.kid].basis_bei(a1.start_bar):.4f})")
for k in sorted(ziel_bars):
    e = katalog.get(ziel_bars[k])
    if e is not None:
        print(f"    Bar {k:>4} K{ziel_bars[k]:>3}: "
              f"basis_bei({k}) = {e.basis_bei(k):.4f}")
