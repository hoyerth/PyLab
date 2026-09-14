# -*- coding: utf-8 -*-
"""READ-ONLY: K77 (G4-Bodenanker) unter Baseline vs. F -- Niveau am Event-Bar."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SRC = P.read_text(encoding="utf-8")
B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""
F = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        return float(min(px) if self.seite == "OBEN" else max(px))"""

LIT = 68.4000
for name in ("BASELINE", "F"):
    src = SRC if name == "BASELINE" else SRC.replace(B_BASIS, F)
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kk_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kk_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    scan = mod._se_scan("AUG", mod.StraightEdgeHarnessKonfiguration())
    e = next(x for x in scan["edges"] + scan["seeds"] if x.kid == 77)
    print(f"=== {name} ===  K77 {e.seite} geburt={e.geburts_bar} "
          f"wicks={len(e.wicks)} anker={e.ist_prim_anker}")
    for b, p in e.wicks:
        print(f"    Pivot bar {b:4d}  low {p:.4f}")
    for k in (1000, 1002, 1003, 1004, 1010, 1287):
        print(f"    basis_bei({k:4d}) = {e.basis_bei(k):.4f}"
              f"   {'> LITERAL' if e.basis_bei(k) > LIT else '< LITERAL'}")
    print(f"    basis(statisch) = {e.basis:.4f}   "
          f"Literal = {LIT:.4f}")
    print()
sys.exit(0)
