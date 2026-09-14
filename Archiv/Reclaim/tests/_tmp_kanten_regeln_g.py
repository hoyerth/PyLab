# -*- coding: utf-8 -*-
"""READ-ONLY: Fenster-Varianten G (letzte 3 Dochte, rollierend) und
H (Extremum der ersten 3 Dochte, danach eingefroren).

Beide liefern fuer K73 69.6110 (= Anwenderziel 69.62) und fuer K82 67.6000
(= Anwenderziel 67.60), wenn die Basis clusterkonsistent gepatcht wird.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Dict, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SRC = P.read_text(encoding="utf-8")

B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""
B_AKZ = """        if not e.ist_prim_anker:            # Q13: Anker friert ein
            e.basis = float(np.mean([p for _, p in e.wicks]))"""

EXTREM = 'float(min(_w) if self.seite == "OBEN" else max(_w))'

V: Dict[str, Tuple[str, str]] = {
    # G: rollierendes Fenster der letzten 3 Dochte
    "G_last3": (
        f"""        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        _w = px[-3:]
        return {EXTREM}""",
        """        if not e.ist_prim_anker:
            _w = [p for _, p in e.wicks][-3:]
            e.basis = float(min(_w) if e.seite == "OBEN" else max(_w))""",
    ),
    # H: Extremum der ersten 3 Dochte, danach eingefroren
    "H_freeze3": (
        f"""        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        _w = px[:3]
        return {EXTREM}""",
        """        if not e.ist_prim_anker and len(e.wicks) <= 3:
            _w = [p for _, p in e.wicks][:3]
            e.basis = float(min(_w) if e.seite == "OBEN" else max(_w))""",
    ),
    # I: Einfrieren auf den ERSTEN Docht nach dem 2. Touch (Kontrollvariante)
    "I_freeze2": (
        """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        _w = px[:2]
        return float(min(_w) if self.seite == "OBEN" else max(_w))""",
        """        if not e.ist_prim_anker and len(e.wicks) <= 2:
            _w = [p for _, p in e.wicks][:2]
            e.basis = float(min(_w) if e.seite == "OBEN" else max(_w))""",
    ),
}


def baue(name: str):
    src = SRC
    nb, na = V[name]
    assert src.count(B_BASIS) == 1 and src.count(B_AKZ) == 1, name
    src = src.replace(B_BASIS, nb).replace(B_AKZ, na)
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kv_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kv_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


for name in ("G_last3", "H_freeze3", "I_freeze2"):
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
    print(f"=== {name} ===  Trades {len(trades)} / {sum(t.r for t in trades):+.6f} R"
          f"  H1 {len(h1)}/{sum(t.r for t in h1):+.6f}  (Soll 8/+38.964262)")
    print(f"  H1-Entries {sorted(t.entry_bar for t in h1)}")
    print(f"  H2 {[f'K{t.kid}@{t.bar}{t.r:+.4f}' for t in sorted(trades, key=lambda x: x.bar) if t.entry_bar >= box]}")
    print(f"  Knicke {knick}/{len(kanten)} Linien, {spr} Spruenge")
    for ziel, seite, lbl in ((69.6200, "OBEN", "K73/Upper2"),
                             (67.6000, "UNTEN", "K82/Lower3")):
        nah = min(kanten, key=lambda e: abs(e.basis_bei(n - 1) - ziel))
        print(f"  {lbl:12s} Ziel {ziel:.4f} -> K{nah.kid} gb={nah.geburts_bar} "
              f"w={len(nah.wicks)} basis_bei(1287)={nah.basis_bei(n - 1):.4f} "
              f"(d={abs(nah.basis_bei(n - 1) - ziel):.4f})")
    print()
sys.exit(0)
