# -*- coding: utf-8 -*-
"""READ-ONLY: K67-Struktur (Basis 69.946) -- warum nie ein Sweep?"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_loader("m", loader=None)
m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
m.__file__ = str(P)
sys.modules["m"] = m
exec(compile(P.read_text(encoding="utf-8"), str(P), "exec"), m.__dict__)

cfg = m.StraightEdgeHarnessKonfiguration()
sc = m._se_scan("AUG", cfg)
e = next(x for x in list(sc["edges"]) + list(sc["seeds"]) if x.kid == 67)
d = sc["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)

print(f"K67 {e.seite} basis={e.basis:.3f} pivot={e.erster_pivot_bar} "
      f"geburt={e.geburts_bar} n={e.touch_anzahl} anker={e.ist_prim_anker}")
print(f"Schwelle 0.12 % -> {e.basis * 1.0012:.3f} | 0.60 % -> {e.basis * 1.006:.3f}")
print("")

mx, mxb = 0.0, -1
for k in range(e.erster_pivot_bar, sc["n"]):
    bs = e.basis_bei(k)
    dist = (hi[k] - bs) / bs * 100.0
    if dist > mx:
        mx, mxb = dist, k
print(f"MAX hi-Ueberstand vs. kausale Basis: {mx:+.4f} % bei Bar {mxb} "
      f"(hi={hi[mxb]:.3f})")
print(f"MAX hi ab Pivot: {hi[e.erster_pivot_bar:].max():.3f} "
      f"(Bar {e.erster_pivot_bar + int(hi[e.erster_pivot_bar:].argmax())})")
print("")
print("Alle Bars mit hi > basis + 0.02 %:")
for k in range(e.erster_pivot_bar, sc["n"]):
    bs = e.basis_bei(k)
    dist = (hi[k] - bs) / bs * 100.0
    if dist > 0.02:
        alter = k - e.erster_pivot_bar
        print(f"  Bar {k:4d} hi={hi[k]:7.3f} basis_bei={bs:7.3f} "
              f"dist={dist:+.4f}% alter={alter:4d} "
              f"etabliert(>= {cfg.min_wall_alter_bars})={alter >= cfg.min_wall_alter_bars} "
              f"close={cl[k]:.3f} reclaim={cl[k] <= bs}")
print("")
print("Dochte (bestätigte Pivots) der Kante:")
for b, px in e.wicks:
    bs = e.basis_bei(b)
    print(f"  bar {b:4d} px={px:7.3f} basis_bei={bs:7.3f} "
          f"ueberstand={(px - bs) / bs * 100.0:+.4f}%")
