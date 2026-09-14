# -*- coding: utf-8 -*-
"""Quick-Probe (READ-ONLY): Zeitstempel/Preise um 21.08. 16:00 und 24.08. 03:30."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("eng_p", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng_p"] = eng
spec.loader.exec_module(eng)  # type: ignore[union-attr]
eng.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]

cfg = eng.StraightEdgeHarnessKonfiguration()
for F in ("AUG", "AUG26"):
    scan = eng._se_scan(F, cfg)  # type: ignore[arg-type]
    d = scan["d"]
    ts = list(d["ts"])
    hi = list(d["high"])
    lo = list(d["low"])
    print("=" * 100)
    print(f"{F}: n = {scan['n']} | ts[0] = {ts[0]} | ts[-1] = {ts[-1]}")
    for k in range(len(ts)):
        t = str(ts[k])
        if ("21.08" in t and "16:00" in t) or ("24.08" in t and "03:30" in t):
            print(f"   bar {k:>5}  ts={t:<32} hi={hi[k]:.4f} lo={lo[k]:.4f}")
