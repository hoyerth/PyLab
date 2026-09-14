# -*- coding: utf-8 -*-
"""READ-ONLY: POC-Anker-Vergleich fuer das Bar-1002-Setup (kein Schreiben)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
import importlib.util  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"),
         m.__dict__)
    return m


E = load("ke_poc", P)
cfg = E.StraightEdgeHarnessKonfiguration()
scan = E._se_scan("AUG", cfg)
d = scan["d"]
basis = 68.34266666666667
ENTRY = 68.5070
for lab, u, o in (("[basis .. tp2 69.9140]", basis, 69.914),
                  ("[boden 68.40 .. decke 69.87]", 68.4000, 69.8700)):
    for ps in (0, 848, 991):
        poc = E.berechne_kausalen_histogramm_poc(d, ps, 1002, u, o, cfg.num_bins)
        ok = "entry<poc OK" if ENTRY < poc else "entry<poc VERLETZT"
        print(f"  poc_start {ps:4d} {lab}: POC {poc:8.4f}  "
              f"(entry {ENTRY})  -> {ok}")
print("\n  Regel im Code: L-Ordnung  sl < entry < poc < tp2  "
      "(Z. 2641) mit tp1 = poc (Z. 2652)")
