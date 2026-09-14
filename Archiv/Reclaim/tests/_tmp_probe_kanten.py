# -*- coding: utf-8 -*-
"""Probe: Genealogie der Zielkanten K67/K71/K73/K77/K82 in AUG und AUG26."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location("eng_k", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng_k"] = eng
spec.loader.exec_module(eng)  # type: ignore[union-attr]
eng.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = eng.StraightEdgeHarnessKonfiguration()

TAGE = ["10.08", "11.08", "12.08", "13.08", "14.08", "17.08", "18.08", "19.08",
        "20.08", "21.08", "24.08", "25.08", "26.08", "27.08", "28.08"]
TAGE26 = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08", "12.08",
          "13.08", "14.08", "17.08", "18.08", "19.08", "20.08", "21.08", "24.08",
          "25.08", "26.08", "27.08", "28.08", "31.08"]


def tag(F, b):
    t = TAGE26 if F == "AUG26" else TAGE
    i = b // 92
    return f"{t[i]}({b - i * 92:02d})" if 0 <= i < len(t) else "?"


ZIEL = {67: "A1/A2 decke + P9 decke", 71: "GEGEN-PIVOT 21.08. 16:30",
        73: "A2 decke", 77: "P9 boden (24.08. 03:30)", 82: "A1/A2 boden"}
for F in ("AUG", "AUG26"):
    scan = eng._se_scan(F, cfg)  # type: ignore[arg-type]
    alle = list(scan["edges"]) + list(scan["seeds"])
    n = int(scan["n"])
    print("=" * 112)
    print(f"{F}  (n = {n})")
    print("=" * 112)
    for e in sorted(alle, key=lambda x: x.kid):
        if e.kid not in ZIEL:
            continue
        w = ", ".join(f"{b}/{tag(F, b)}({p:.4f})" for b, p in e.wicks)
        print(f"   K{e.kid:<4} {e.seite:<6} erster_pivot={e.erster_pivot_bar:<5}"
              f"({tag(F, e.erster_pivot_bar):<11}) geburt={e.geburts_bar:<5} "
              f"V-S={e.touch_anzahl:<2} prim_anker={e.ist_prim_anker}")
        print(f"        [{ZIEL[e.kid]}]  wicks: {w}")
