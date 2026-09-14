# -*- coding: utf-8 -*-
"""READ-ONLY: Kid-Identitaet / Adapter-Bindung + P12-Niveaus je Regel."""
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
B_AKZ = """        if not e.ist_prim_anker:            # Q13: Anker friert ein
            e.basis = float(np.mean([p for _, p in e.wicks]))"""

V = {
    "BASELINE": None,
    "A_1docht": ("        return float(self.basis)", ""),
    "B_engste": ("""        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        return float(min(px) if self.seite == "OBEN" else max(px))""",
                 """        if not e.ist_prim_anker:
            e.basis = float(min(p for _, p in e.wicks)
                            if e.seite == "OBEN"
                            else max(p for _, p in e.wicks))"""),
}


def baue(name):
    src = SRC
    if V[name]:
        nb, na = V[name]
        src = src.replace(B_BASIS, nb).replace(B_AKZ, na)
    spec = importlib.util.spec_from_loader("kx_" + name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(P)
    sys.modules["kx_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


for name in ("BASELINE", "A_1docht", "B_engste"):
    eng = baue(name)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    kanten = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
    print(f"=== {name} ===  (max kid={max(kanten)})")
    print("  Kids 60..90:")
    for kid in sorted(kanten):
        if 60 <= kid <= 95:
            e = kanten[kid]
            print(f"    K{kid:3d} {e.seite:5s} geburt={e.geburts_bar:4d} "
                  f"basis={e.basis:8.4f} w={e.touch_anzahl} "
                  f"anker={e.ist_prim_anker}")
    print("  Anker-Kids:", sorted(k for k, e in kanten.items()
                                  if e.ist_prim_anker))
    # Naechstgelegene Kante zu den Adapter-Ankern
    for ziel, lbl in ((69.8700, "K67_OVERRIDE"), (68.4000, "P9_BODEN_LITERAL"),
                      (69.6200, "Ziel Upper2"), (67.6000, "Ziel Lower3")):
        nah = min(kanten.values(),
                  key=lambda e: abs(e.basis_bei(1287) - ziel))
        print(f"  {lbl:18s} {ziel:.4f} -> K{nah.kid} {nah.seite} "
              f"basis_bei(1287)={nah.basis_bei(1287):.4f}")
    print()
sys.exit(0)
