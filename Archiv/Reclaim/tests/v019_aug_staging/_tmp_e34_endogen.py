# -*- coding: utf-8 -*-
"""E-34 (read-only) -- Sind die Kanten K73/K82 AUS DEM MARKT auffindbar?

Frage des Anwenders: wurden die Segment-Kanten nur anhand der Zielvorgabe
gefunden (= unsichtbares Ziel der Suche)?  Gegenprobe: eine kausale,
parameterfreie Regel OHNE jedes Zielwissen.

Regel "aeusserste LEBENDE Linie" (Analogie zur Engine-Q25 `_lebt`):
    lebt(e, k)  <=>  letzter Docht(b <= k) >= k - wall_live_bars
    decke(k)    = aeusserste OBEN-Linie mit lebt(e, k)
    boden(k)    = aeusserste UNTEN-Linie mit lebt(e, k)
Rein kausal: nur Dochte <= k.

Ausgabe: Wechselpunkte dieser Regel in 900..1290 -- ohne Zielvorgabe.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
scan["box_end_bar"] = scan["n"]
alle = list(scan["edges"]) + list(scan["seeds"])
LIVE = cfg.wall_live_bars
print(f"n {scan['n']}  wall_live_bars {LIVE}")


def lebt(e, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb <= k]
    return bool(b) and max(b) >= k - LIVE


def ecken(k: int):
    oben = [(e.basis_bei(k), e.kid, max(b for b, _ in e.wicks if b <= k))
            for e in alle if e.seite == "OBEN" and lebt(e, k)]
    unten = [(e.basis_bei(k), e.kid, max(b for b, _ in e.wicks if b <= k))
             for e in alle if e.seite == "UNTEN" and lebt(e, k)]
    o = max(oben) if oben else None
    u = min(unten) if unten else None
    return o, u


print("")
print("   AEUSSERSTE LEBENDE LINIE -- Wechselpunkte (kausal, ohne Zielwissen)")
print(f"   {'Bar':>5}  {'OBEN (decke)':<26}{'UNTEN (boden)':<26}")
vor_o = vor_u = None
for k in range(900, 1290):
    o, u = ecken(k)
    os_ = "-" if o is None else f"K{o[1]:<3} {o[0]:.4f} (letzter {o[2]})"
    us_ = "-" if u is None else f"K{u[1]:<3} {u[0]:.4f} (letzter {u[2]})"
    ok = (o[1] if o else None) != vor_o
    uk = (u[1] if u else None) != vor_u
    if ok or uk:
        mark = ("[OBEN-Wechsel]" if ok else "") + ("[UNTEN-Wechsel]" if uk else "")
        print(f"   {k:>5}  {os_:<26}{us_:<26}{mark}")
        vor_o = o[1] if o else None
        vor_u = u[1] if u else None

print("")
print("   ZUM VERGLEICH -- was E-33 gesetzt hat (aus der Vorgabe/Handliste):")
print("      P10 1021..1170 : decke K73, boden K82")
print("      P12 1171..1287 : decke K73, boden K82  (= bestehendes P12_RESERVE: kid 73/82)")
print("")
print("   K67-Dormanz (die M6-Ursache):")
e67 = next(e for e in alle if e.kid == 67)
letzter = max(b for b, _ in e67.wicks)
print(f"      K67 letzter Docht {letzter}  ->  wird dormant ab Bar "
      f"{letzter + LIVE + 1}")
print(f"      avisierter SHORT: Signal 1122 (Entry 1123)")
