# -*- coding: utf-8 -*-
"""READ-ONLY: In-Memory-Vergleich der Kanten-Regeln (Datei bleibt unberuehrt).

Baseline (np.mean) vs.
  A "1. Docht"    -- Basis friert beim Geburts-Docht ein (kein Update)
  B "engste"      -- OBEN = min(Dochte), UNTEN = max(Dochte), laufend
  C "letzter"     -- Basis = jeweils neuester Docht

Gemessen werden: Trades gesamt/H1/H2/P9, Knickzahl, K73/K82-Niveau.
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

B_AKZ = """        if not e.ist_prim_anker:            # Q13: Anker friert ein
            e.basis = float(np.mean([p for _, p in e.wicks]))"""

VARIANTEN: Dict[str, Tuple[str, str]] = {
    "A_1docht": (
        "        return float(self.basis)",
        "",
    ),
    "B_engste": (
        """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if not px:
            return self.basis
        return float(min(px) if self.seite == "OBEN" else max(px))""",
        """        if not e.ist_prim_anker:
            e.basis = float(min(p for _, p in e.wicks)
                            if e.seite == "OBEN"
                            else max(p for _, p in e.wicks))""",
    ),
    "C_letzter": (
        """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(px[-1]) if px else self.basis""",
        """        if not e.ist_prim_anker:
            e.basis = float(e.wicks[-1][1])""",
    ),
}


def baue(name: str) -> object:
    src = SRC
    if name != "BASELINE":
        nb, na = VARIANTEN[name]
        assert src.count(B_BASIS) == 1, (name, "basis_bei")
        assert src.count(B_AKZ) == 1, (name, "_akzeptiere")
        src = src.replace(B_BASIS, nb).replace(B_AKZ, na)
        assert "np.mean(px)" not in src and "np.mean([p for" not in src
    spec = importlib.util.spec_from_loader("ke_" + name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules["ke_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


def messe(name: str) -> None:
    eng = baue(name)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    n = scan["n"]
    box = scan["box_end_bar"]
    scan2 = dict(scan)
    scan2["box_end_bar"] = n
    trades, _st = eng._se_trades(scan2, cfg)
    d = scan["d"]
    ts = d["ts"].tolist()

    h1 = [t for t in trades if t.entry_bar < box]
    h2 = [t for t in trades if t.entry_bar >= box]
    p9 = [t for t in trades if 848 <= t.bar <= 1020]

    kanten = list(scan["edges"]) + list(scan["seeds"])
    knick, spruenge = 0, 0
    for e in kanten:
        w, seen = 0, None
        for k in range(n):
            v = e.basis_bei(k)
            if seen is None or abs(v - seen) > 1e-12:
                w += 1
                seen = v
        if w - 1 >= 1:
            knick += 1
            spruenge += w - 1

    def niveau(kid: int) -> str:
        e = next((x for x in kanten if x.kid == kid), None)
        if e is None:
            return "n/a"
        return (f"K{kid} {e.seite:5s} b={e.geburts_bar} "
                f"basis={e.basis:.4f} w={len(e.wicks)} "
                f"bei1020={e.basis_bei(1020):.4f} "
                f"bei1287={e.basis_bei(n - 1):.4f}")

    print(f"=== {name} ===")
    print(f"  Trades gesamt {len(trades):2d} / {sum(t.r for t in trades):+.6f} R")
    print(f"  H1  {len(h1):2d} / {sum(t.r for t in h1):+.6f} R   "
          f"(Soll 8 / +38.964262)")
    print(f"  H2  {len(h2):2d} / {sum(t.r for t in h2):+.6f} R")
    print(f"  P9  {len(p9):2d} / {sum(t.r for t in p9):+.6f} R")
    print(f"  H1-Entries: {sorted(t.entry_bar for t in h1)}")
    print(f"  H1-Trades : "
          f"{[f'K{t.kid}@{t.bar}' for t in sorted(h1, key=lambda x: x.bar)]}")
    print(f"  H2-Trades : "
          f"{[f'K{t.kid}@{t.bar}' for t in sorted(h2, key=lambda x: x.bar)]}")
    print(f"  Knicke: {knick:2d}/{len(kanten)} Linien, "
          f"{spruenge} Spruenge")
    # P12-Kanten identifizieren (OBEN nahe 69.6-69.75, UNTEN nahe 67.5)
    for e in kanten:
        if e.seite == "OBEN" and 69.55 < e.basis < 69.80 and e.geburts_bar > 900:
            print("  P12-Decke?", niveau(e.kid))
        if e.seite == "UNTEN" and 67.40 < e.basis < 67.70 and e.geburts_bar > 1000:
            print("  P12-Boden?", niveau(e.kid))
    unbek = [t for t in trades if 1020 < t.bar < 1288]
    if unbek:
        print("  Trades in P12-Fenster: "
              f"{[f'K{t.kid}@{t.bar} {t.r:+.4f}' for t in sorted(unbek, key=lambda x: x.bar)]}")
    print()


for v in ("BASELINE", "A_1docht", "B_engste", "C_letzter"):
    messe(v)
sys.exit(0)
