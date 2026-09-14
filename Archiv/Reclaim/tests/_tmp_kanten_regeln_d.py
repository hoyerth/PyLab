# -*- coding: utf-8 -*-
"""READ-ONLY: Docht-Tabellen K73/K82 + Zusatzregeln D/E + H1-Delta-Trace.

A  = 1. Docht (flach, eingefroren)
D  = 2. Docht (flach, eingefroren)
E  = Mittel der ersten zwei Dochte (flach, eingefroren)
B  = engste (laufend)   -- Referenz aus Vorlauf
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Dict, List, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SRC = P.read_text(encoding="utf-8")

B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""

# Varianten, die NUR basis_bei ersetzen (Speicher-Basis bleibt unveraendert,
# damit _akzeptiere/2-Body/R21 unberuehrt bleiben -> reiner Zeichen-Effekt).
NUR_BASIS: Dict[str, str] = {
    "A_1docht": """        if self.ist_prim_anker:
            return self.basis
        _s = sorted(p for _, p in self.wicks)
        return float(_s[0]) if not self.ist_prim_anker else self.basis""",
    "D_2docht": """        if self.ist_prim_anker:
            return self.basis
        _w = [p for b, p in self.wicks if b + 2 <= k] or \\
             [p for _, p in self.wicks]
        return float(_w[min(1, len(_w) - 1)])""",
    "E_mean2": """        if self.ist_prim_anker:
            return self.basis
        _w = [p for b, p in self.wicks if b + 2 <= k] or \\
             [p for _, p in self.wicks]
        return float(sum(_w[:2]) / min(2, len(_w)))""",
}


def baue(name: str):
    src = SRC
    if name != "BASELINE":
        assert src.count(B_BASIS) == 1, name
        src = src.replace(B_BASIS, NUR_BASIS[name])
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kw_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kw_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


def lauf(name: str):
    eng = baue(name)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    n, box = scan["n"], scan["box_end_bar"]
    s2 = dict(scan)
    s2["box_end_bar"] = n
    trades, _ = eng._se_trades(s2, cfg)
    return scan, trades, n, box


def dochte(scan, n, seite, ziel):
    kanten = list(scan["edges"]) + list(scan["seeds"])
    nah = min(kanten, key=lambda e: abs(e.basis_bei(n - 1) - ziel))
    print(f"    K{nah.kid} {nah.seite} gb={nah.geburts_bar} anker={nah.ist_prim_anker} "
          f"basis={nah.basis:.4f} basis_bei(1287)={nah.basis_bei(n - 1):.4f}")
    for b, p in nah.wicks:
        print(f"       bar {b:4d} docht {p:.4f}")
    return nah


for name in ("BASELINE", "A_1docht", "D_2docht", "E_mean2"):
    scan, trades, n, box = lauf(name)
    h1 = [t for t in trades if t.entry_bar < box]
    print(f"=== {name} ===  Trades {len(trades)} / {sum(t.r for t in trades):+.6f} R"
          f"   H1 {len(h1)}/{sum(t.r for t in h1):+.6f}")
    print(f"  H1: {[f'K{t.kid}@{t.bar}({t.entry_bar}){t.r:+.4f}' for t in sorted(h1, key=lambda x: x.bar)]}")
    print(f"  H2: {[f'K{t.kid}@{t.bar}{t.r:+.4f}' for t in sorted(trades, key=lambda x: x.bar) if t.entry_bar >= box]}")
    print("  --- Ziel Upper2 ~69.62 ---")
    dochte(scan, n, "OBEN", 69.6200)
    print("  --- Ziel Lower3 ~67.60 ---")
    dochte(scan, n, "UNTEN", 67.6000)
    print()
sys.exit(0)
