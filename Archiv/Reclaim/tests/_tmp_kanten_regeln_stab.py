# -*- coding: utf-8 -*-
"""READ-ONLY Praezisierungslauf: Regelvarianten mit kausal vereinheitlichter
Band-Pruefung (``basis_bei``) gegen die rohe Speicher-Basis (``e.basis``).

Hintergrund: ``_se_scan`` prueft Kandidaten-Dochte gegen ``c.basis`` (Rohwert
aus ``_akzeptiere``), waehrend Linie, Blocker und Kandidaten-Kaskade bereits
``basis_bei(k)`` (kausal, Pivot+2) nutzen. Der "_stab"-Satz beseitigt diese
Doppelspur an ALLEN Stellen und misst, ob das die Kid-Bindung stabilisiert.

Varianten: BASELINE | A_1docht | A_stab | B_engste | B_stab | C_letzter
Die Datei ``tmp_kanten_engine_replay.py`` wird nur in-memory gepatcht.
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

REGELN: Dict[str, Tuple[str, str]] = {
    "A_1docht": ("        return float(self.basis)", ""),
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

# --- "_stab": Band-/Tiebreak-/Referenz-Zugriffe auf basis_bei umstellen ----
STAB: List[Tuple[str, str]] = [
    ("                    if _ist_im_band(px, c.basis)",
     "                    if _ist_im_band(px, c.basis_bei(mbar))"),
    ('                                       c.basis if seite == "OBEN" else -c.basis),',
     '                                       c.basis_bei(mbar) if seite == "OBEN"\n'
     '                                       else -c.basis_bei(mbar)),'),
    ("                        aeus_ref = (max(r.basis for r in refs)",
     "                        aeus_ref = (max(r.basis_bei(mbar) for r in refs)"),
    ("                                    else min(r.basis for r in refs))",
     "                                    else min(r.basis_bei(mbar) for r in refs))"),
    ("                    aussen = (min(op[k - 1], cl[k - 1]) > e.basis\n"
     "                              and min(op[k], cl[k]) > e.basis)",
     "                    aussen = (min(op[k - 1], cl[k - 1]) > e.basis_bei(k)\n"
     "                              and min(op[k], cl[k]) > e.basis_bei(k))"),
    ("                    aussen = (max(op[k - 1], cl[k - 1]) < e.basis\n"
     "                              and max(op[k], cl[k]) < e.basis)",
     "                    aussen = (max(op[k - 1], cl[k - 1]) < e.basis_bei(k)\n"
     "                              and max(op[k], cl[k]) < e.basis_bei(k))"),
    ("                                _ist_aussen = _e.basis >= max(\n"
     "                                    r.basis for r in _lb)",
     "                                _ist_aussen = _e.basis_bei(k) >= max(\n"
     "                                    r.basis_bei(k) for r in _lb)"),
    ("                                _ist_aussen = _e.basis <= min(\n"
     "                                    r.basis for r in _lb)",
     "                                _ist_aussen = _e.basis_bei(k) <= min(\n"
     "                                    r.basis_bei(k) for r in _lb)"),
]

KOMBI: Dict[str, str] = {
    "BASELINE": "",
    "A_1docht": "A_1docht",
    "A_stab": "A_1docht+stab",
    "B_engste": "B_engste",
    "B_stab": "B_engste+stab",
    "C_letzter": "C_letzter",
    "C_stab": "C_letzter+stab",
}


def baue(name: str) -> object:
    src = SRC
    spec_ = KOMBI[name]
    if spec_:
        regel, _, extra = spec_.partition("+")
        nb, na = REGELN[regel]
        assert src.count(B_BASIS) == 1 and src.count(B_AKZ) == 1, name
        src = src.replace(B_BASIS, nb).replace(B_AKZ, na)
        assert "np.mean(px)" not in src and "np.mean([p for" not in src
    if name.endswith("_stab"):
        for alt, neu in STAB:
            assert src.count(alt) == 1, (name, alt[:48])
            src = src.replace(alt, neu)
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kz_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kz_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


ZIELE = (("K67_OVERRIDE 69.8700", "OBEN", 69.8700),
         ("P9_LITERAL   68.4000", "UNTEN", 68.4000),
         ("Upper2       69.6200", "OBEN", 69.6200),
         ("Lower3       67.6000", "UNTEN", 67.6000))


def messe(name: str) -> None:
    eng = baue(name)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    n, box = scan["n"], scan["box_end_bar"]
    s2 = dict(scan)
    s2["box_end_bar"] = n
    trades, _st = eng._se_trades(s2, cfg)
    kanten = list(scan["edges"]) + list(scan["seeds"])

    h1 = [t for t in trades if t.entry_bar < box]
    h2 = [t for t in trades if t.entry_bar >= box]
    p9 = [t for t in trades if 848 <= t.bar <= 1020]

    knick, spr = 0, 0
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

    print(f"=== {name} ===  ({KOMBI[name] or 'unpatched'})")
    print(f"  Trades {len(trades):2d} / {sum(t.r for t in trades):+.6f} R"
          f"   H1 {len(h1):2d}/{sum(t.r for t in h1):+.6f}"
          f"   H2 {len(h2):2d}/{sum(t.r for t in h2):+.6f}"
          f"   P9 {len(p9):2d}/{sum(t.r for t in p9):+.6f}")
    print(f"  H1-Entries {sorted(t.entry_bar for t in h1)}")
    print(f"  H2-Trades  {[f'K{t.kid}@{t.bar}' for t in sorted(h2, key=lambda x: x.bar)]}")
    print(f"  P9-Trades  {[f'K{t.kid}@{t.bar} {t.r:+.4f}' for t in sorted(p9, key=lambda x: x.bar)]}")
    print(f"  Knicke {knick:2d}/{len(kanten)} Linien, {spr} Spruenge")
    for lbl, seite, ziel in ZIELE:
        nah = min(kanten, key=lambda e: abs(e.basis_bei(n - 1) - ziel))
        d = abs(nah.basis_bei(n - 1) - ziel)
        print(f"  {lbl} -> K{nah.kid} {nah.seite:5s} gb={nah.geburts_bar:4d} "
              f"w={len(nah.wicks):2d} basis_bei(1287)={nah.basis_bei(n - 1):.4f} "
              f"(d={d:.4f}) anker={nah.ist_prim_anker}")
    sp = [t for t in trades if 1055 <= t.bar <= 1287]
    print(f"  Fenster >=1055: {[f'K{t.kid}@{t.bar} {t.r:+.4f}' for t in sorted(sp, key=lambda x: x.bar)]}")
    print()


for v in KOMBI:
    messe(v)
sys.exit(0)
