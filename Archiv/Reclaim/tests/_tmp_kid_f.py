# -*- coding: utf-8 -*-
"""READ-ONLY: Kid-Identitaet BASELINE vs F_extrem (Adapter-/G4-Bindung)."""
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


def scanne(name: str):
    src = SRC if name == "BASELINE" else SRC.replace(B_BASIS, F)
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kj_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kj_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod._se_scan("AUG", mod.StraightEdgeHarnessKonfiguration())


a = scanne("BASELINE")
b = scanne("F_extrem")
ka = {e.kid: e for e in list(a["edges"]) + list(a["seeds"])}
kb = {e.kid: e for e in list(b["edges"]) + list(b["seeds"])}
n = a["n"]

print(f"Kanten BASELINE {len(ka)}  F {len(kb)}  "
      f"kids gleich: {sorted(ka) == sorted(kb)}")
diff = [k for k in sorted(set(ka) & set(kb))
        if (ka[k].seite, ka[k].geburts_bar, len(ka[k].wicks))
        != (kb[k].seite, kb[k].geburts_bar, len(kb[k].wicks))]
print(f"Strukturell abweichende kids: {diff if diff else 'KEINE'}")
print()
print("Adapter-/G4-relevante Niveaus (geburt, w, basis_bei(1287)):")
for kid in (67, 73, 82, 77, 89):
    for lbl, kk in (("BASE", ka), ("F   ", kb)):
        e = kk.get(kid)
        if e is None:
            print(f"  K{kid:3d} {lbl} -- fehlt")
        else:
            print(f"  K{kid:3d} {lbl} {e.seite:5s} gb={e.geburts_bar:4d} "
                  f"w={len(e.wicks):2d} anker={e.ist_prim_anker} "
                  f"basis={e.basis:8.4f} basis_bei(1287)={e.basis_bei(n - 1):8.4f}")
print()
print("Naechste Kante je Adapter-Literal:")
for ziel, seite, lbl in ((69.8700, "OBEN", "K67_OVERRIDE"),
                         (68.4000, "UNTEN", "P9_BODEN_LITERAL"),
                         (69.6200, "OBEN", "Ziel Upper2"),
                         (67.6000, "UNTEN", "Ziel Lower3")):
    for lbl2, kk in (("BASE", ka), ("F   ", kb)):
        pool = [e for e in kk.values() if e.seite == seite]
        nah = min(pool, key=lambda e: abs(e.basis_bei(n - 1) - ziel))
        print(f"  {lbl:17s} {ziel:.4f} {lbl2} -> K{nah.kid} w={len(nah.wicks)} "
              f"{nah.basis_bei(n - 1):.4f} (d={abs(nah.basis_bei(n - 1) - ziel):.4f})")
sys.exit(0)
