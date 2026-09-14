# -*- coding: utf-8 -*-
"""READ-ONLY: Variante F -- Linien-/Handelsniveau = Extremum der bestaetigten
Dochte (kausal), Clusterbildung (Band, 2-Body, R21, Promotion) bleibt wie
Baseline. Entscheidend: trifft F die Anwenderziele 69.62 / 67.60 bei
unveraenderter H1?

Vorlauf-Nullbefund: die kausale Vereinheitlichung (_stab) ist wirkungsgleich.
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

F = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        return float(min(px) if self.seite == "OBEN" else max(px))"""


def baue(name: str):
    src = SRC if name == "BASELINE" else SRC.replace(B_BASIS, F)
    if name != "BASELINE":
        assert src.count(B_BASIS) == 0
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kf_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kf_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


for name in ("BASELINE", "F_extrem"):
    eng = baue(name)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    n, box = scan["n"], scan["box_end_bar"]
    s2 = dict(scan)
    s2["box_end_bar"] = n
    trades, _ = eng._se_trades(s2, cfg)
    kanten = list(scan["edges"]) + list(scan["seeds"])
    h1 = [t for t in trades if t.entry_bar < box]
    knick = spr = 0
    for e in kanten:
        w, seen = 0, None
        for k in range(n):
            v = e.basis_bei(k)
            if seen is None or abs(v - seen) > 1e-12:
                w += 1
                seen = v
        if w > 1:
            knick += 1
            spr += w - 1
    print(f"=== {name} ===")
    print(f"  Trades {len(trades)} / {sum(t.r for t in trades):+.6f} R"
          f"   H1 {len(h1)}/{sum(t.r for t in h1):+.6f} (Soll 8/+38.964262)")
    print(f"  H1-Entries {sorted(t.entry_bar for t in h1)}")
    print(f"  Knicke {knick}/{len(kanten)}, {spr} Spruenge")
    for ziel, lbl in ((69.6200, "K73/Upper2"), (67.6000, "K82/Lower3")):
        nah = min(kanten, key=lambda e: abs(e.basis_bei(n - 1) - ziel))
        print(f"  {lbl:12s} Ziel {ziel:.4f} -> K{nah.kid} gb={nah.geburts_bar} "
              f"w={len(nah.wicks)} niveau={nah.basis_bei(n - 1):.4f} "
              f"(d={abs(nah.basis_bei(n - 1) - ziel):.4f})")
        # Kanten-Knick-Profil dieses Niveaus (nur die Spruenge zeigen)
        s, seen = [], None
        for k in range(n):
            v = nah.basis_bei(k)
            if seen is None or abs(v - seen) > 1e-12:
                s.append((k, round(v, 4)))
                seen = v
        print(f"     Niveau-Stufen: {s}")
    print()
sys.exit(0)
