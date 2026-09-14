# -*- coding: utf-8 -*-
"""E-29: parallele Binning-Sweeps, je num_bins EIN Prozess (E-27/F0)."""
from __future__ import annotations

import concurrent.futures as cf
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKRIPT = ROOT / "test" / "_tmp_e29_audit.py"
PY = sys.executable

MODE = sys.argv[1] if len(sys.argv) > 1 else "s2"
BINS = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2
                         else ["60", "40", "30", "20", "15", "10"])]


def lauf(b: int) -> tuple[int, int, float]:
    t = time.time()
    p = subprocess.run([PY, str(SKRIPT), MODE, str(b)], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        print(f"FEHLER bins={b}:\n{p.stderr[-2500:]}")
    return b, p.returncode, time.time() - t


t0 = time.time()
print(f"E-29 Binning-Sweep {MODE}: bins={BINS} ({len(BINS)} Prozesse parallel)")
with cf.ThreadPoolExecutor(max_workers=len(BINS)) as ex:
    for b, rc, dt in ex.map(lauf, BINS):
        print(f"   bins={b:<4} rc {rc}  {dt:5.1f}s")
print(f"Gesamt {time.time() - t0:.1f}s")
