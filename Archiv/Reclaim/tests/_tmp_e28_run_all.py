# -*- coding: utf-8 -*-
"""E-28: startet je Variante EINEN eigenen Prozess (E-27/F0: `_se_trades`
mutiert den Kantenzustand). Parallele Prozesse sind zulaessig -- die Isolation
ist pro Prozess, nicht pro Zeitachse."""
from __future__ import annotations

import concurrent.futures as cf
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKRIPT = ROOT / "test" / "_tmp_e28_ziel_lokal.py"
PY = sys.executable

MODE = sys.argv[1] if len(sys.argv) > 1 else "s2"
VARIANTEN = (sys.argv[2].split(",") if len(sys.argv) > 2
             else ["base", "geg", "geg960", "poc", "gegpoc", "geg960poc"])


def lauf(v: str) -> tuple[str, int, float]:
    t = time.time()
    p = subprocess.run([PY, str(SKRIPT), MODE, v], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        print(f"FEHLER {v}:\n{p.stderr[-2000:]}")
    return v, p.returncode, time.time() - t


t0 = time.time()
print(f"E-28 Sammellauf {MODE}: {VARIANTEN} "
      f"({len(VARIANTEN)} Prozesse parallel)")
with cf.ThreadPoolExecutor(max_workers=len(VARIANTEN)) as ex:
    for v, rc, dt in ex.map(lauf, VARIANTEN):
        print(f"   {v:<11} rc {rc}  {dt:5.1f}s")
print(f"Gesamt {time.time() - t0:.1f}s")
