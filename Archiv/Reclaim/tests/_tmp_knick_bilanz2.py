# -*- coding: utf-8 -*-
"""READ-ONLY: Knick-Bilanz ohne Geburts-Rampe (k >= erster bestaetigter Docht).

Trennt den Look-ahead-Artefakt im Fallback ``return self.basis`` (Speicherwert
= Mittel ueber ALLE Dochte, also Zukunftswert beim Replay frueher Bars) von den
echten Niveau-Wechseln.
"""
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

VAR = {
    "BASELINE": (None, None),
    "A_1docht": ("        return float(self.basis)", ""),
    "F_extrem": ("""        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        return float(min(px) if self.seite == "OBEN" else max(px))""", None),
}


def scanne(name: str):
    src = SRC
    nb, na = VAR[name]
    if nb is not None:
        src = src.replace(B_BASIS, nb)
        if na is not None:
            src = src.replace(B_AKZ, na)
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kr_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kr_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod._se_scan("AUG", mod.StraightEdgeHarnessKonfiguration())


for name in VAR:
    scan = scanne(name)
    n = scan["n"]
    kanten = list(scan["edges"]) + list(scan["seeds"])
    g_rampe = g_echt = 0
    l_rampe = l_echt = 0
    for e in kanten:
        b0 = min((b for b, _ in e.wicks), default=n)
        grenze = b0 + 2
        seen = None
        rampe = echt = 0
        for k in range(n):
            v = e.basis_bei(k)
            if seen is not None and abs(v - seen) > 1e-12:
                if k < grenze:
                    rampe += 1
                else:
                    echt += 1
            seen = v
        if rampe:
            l_rampe += 1
        if echt:
            l_echt += 1
        g_rampe += rampe
        g_echt += echt
    print(f"=== {name} ===")
    print(f"  {len(kanten)} Linien")
    print(f"  Geburts-Rampe (Look-ahead-Fallback): {l_rampe:2d} Linien, "
          f"{g_rampe:3d} Spruenge")
    print(f"  Echte Niveau-Wechsel (nach Bestaetigung): {l_echt:2d} Linien, "
          f"{g_echt:3d} Spruenge")
sys.exit(0)
