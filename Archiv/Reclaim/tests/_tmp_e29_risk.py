# -*- coding: utf-8 -*-
"""E-29: Risiko-Kalibrierung -- ist der Stop degeneriert? (E-22-Nachpruefung)"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

SPLIT = 17692
MODES = sys.argv[1:] or ["s2", "aug"]
for MODE in MODES:
    if MODE == "s2":
        scan = pickle.loads(
            (ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
    else:
        scan = eng._se_scan("AUG", eng.StraightEdgeHarnessKonfiguration())
    d = scan["d"]
    hi = d["high"].to_numpy(float)
    lo = d["low"].to_numpy(float)
    cl = d["close"].to_numpy(float)
    tr = np.maximum(hi[1:] - lo[1:],
                    np.maximum(np.abs(hi[1:] - cl[:-1]),
                               np.abs(lo[1:] - cl[:-1])))
    tr = np.concatenate([[hi[1] - lo[1]], tr])
    S = pickle.loads((ROOT / "test" /
                      f"_tmp_e29_setups_{MODE}_b60.pkl").read_bytes())
    for hname, sel in (("gesamt", S),
                       ("H1", [s for s in S if s["bar"] < SPLIT]),
                       ("H2", [s for s in S if s["bar"] >= SPLIT])):
        if not sel:
            continue
        risk = np.array([abs(s["sl"] - s["entry"]) for s in sel])
        entry = np.array([s["entry"] for s in sel])
        atr = np.array([tr[max(0, int(s["bar"]) - 13):int(s["bar"]) + 1].mean()
                        for s in sel])
        dpoc = np.array([abs(s["poc"] - s["entry"]) / abs(s["sl"] - s["entry"])
                         for s in sel])
        print(f"{MODE.upper()} {hname:<7} n {len(sel):>4} | "
              f"risk/entry %: min {np.min(risk/entry)*100:5.3f} "
              f"med {np.median(risk/entry)*100:5.3f} "
              f"max {np.max(risk/entry)*100:5.3f} | "
              f"risk/ATR14: min {np.min(risk/atr):5.2f} "
              f"med {np.median(risk/atr):5.2f} max {np.max(risk/atr):5.2f} | "
              f"d_POC [R]: med {np.median(dpoc):5.2f} "
              f"p90 {np.percentile(dpoc, 90):6.2f} max {np.max(dpoc):6.2f} | "
              f"ATR14 med {np.median(atr):.4f}")
    print("")
