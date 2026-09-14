# -*- coding: utf-8 -*-
"""READ-ONLY Schnittmengen-Simulation (Papier):
  Q29 phasen-lokal zweiseitig + Pivot+2-Boden  x  POC-Anker (global vs. Phase)

Vier Arme, ausschliesslich In-Memory; auf der Platte wird NICHTS geaendert.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

sys.argv = ["tmp_q29_audit10"]
voll = REN.read_text(encoding="utf-8")
_i = voll.index("import matplotlib")
mod = {"__name__": "q29a10", "__file__": str(REN)}
sys.modules[mod["__name__"]] = type(sys)("q29a10")
exec(compile(voll[:voll.rindex("\n", 0, _i) + 1], str(REN), "exec"), mod)

engine, cfg, scan = mod["engine"], mod["cfg"], mod["scan"]
ADAPTER, box_end = mod["DEFAULT_ADAPTER"], mod["box_end"]
V1_basis = mod["V1_basis"]
src0 = mod["patched_src"]

PHASEN = [(620, 673), (715, 792), (802, 840), (848, 1020), (1030, 1075),
          (1082, 1134), (1171, 1272)]
n = scan["n"]
PHSTART = []
for k in range(n):
    s = 0
    for a, _b in PHASEN:
        if a <= k:
            s = a
    PHSTART.append(s)

A_HI = "        ex_hi = float(np.max(hi[:k + 1]))"
A_LO = "        ex_lo = float(np.min(lo[:k + 1]))"
A_RET = "        return distanz <= cfg.quartil_distanz_pct"
A_PS = "                d, poc_start, k, unter, ober, cfg.num_bins)"

Q29_PHASE = """        ex_hi = float(np.max(hi[:k + 1]))
        if richtung == "LONG":
            _a = _PHSTART[k]
            ex_lo = float(np.min(lo[_a:max(_a, k - 1) + 1]))
        else:
            ex_lo = float(np.min(lo[:k + 1]))"""


def quellen(q29_phase: bool, poc_phase: bool) -> str:
    s = src0
    if q29_phase:
        assert s.count(A_HI) == 1 and s.count(A_LO) == 1
        s = s.replace(A_HI + "\n" + A_LO, Q29_PHASE, 1)
        assert s.count(A_RET) == 1
        s = s.replace(A_RET, '        if richtung == "LONG":\n'
                             "            return 0.0 <= distanz <= "
                             "cfg.quartil_distanz_pct\n"
                             "        return distanz <= "
                             "cfg.quartil_distanz_pct", 1)
    if poc_phase:
        assert s.count(A_PS) == 1
        s = s.replace(A_PS, A_PS.replace("poc_start", "_PS(k)"), 1)
    return s


def lauf(quelle: str):
    _ns = dict(engine.__dict__)
    _ns["_hook"] = ADAPTER
    _ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
    _ns["_PHSTART"] = PHSTART
    _ns["_PS"] = lambda k: 848 if k >= 848 else 0
    exec(compile(quelle, "<v>", "exec"), _ns)
    orig = engine._se_trades
    engine._se_trades = _ns["_se_trades"]
    try:
        return engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = orig


ARME = [
    ("A0 IST (Q29 global, POC 0)", False, False),
    ("A1 POC = Phasenstart", False, True),
    ("A2 Q29 phase/2-seitig", True, False),
    ("A3 A2 + POC = Phasenstart", True, True),
]
print("=== SCHNITTMENGE: Q29-Modell x POC-Anker (Adapter v0.1) ===")
print(f"  Referenz V1_basis: {len(V1_basis)} / "
      f"{sum(t.r for t in V1_basis):+.6f} R | H2 "
      f"{sum(1 for t in V1_basis if t.entry_bar >= box_end)}/"
      f"{sum(t.r for t in V1_basis if t.entry_bar >= box_end):+.6f} R")
for lab, q, p in ARME:
    V, st = lauf(quellen(q, p))
    h1 = [t for t in V if t.entry_bar < box_end]
    h2 = [t for t in V if t.entry_bar >= box_end]
    _s = {t.bar: t for t in V}
    d991 = f"K{_s[991].kid} {_s[991].r:+.4f}" if 991 in _s else "-"
    d1002 = f"K{_s[1002].kid} {_s[1002].r:+.4f}" if 1002 in _s else "-"
    print(f"\n  {lab}")
    print(f"    {len(V):2d} / {sum(t.r for t in V):+10.6f} R | "
          f"H1 {len(h1):2d}/{sum(t.r for t in h1):+10.6f} | "
          f"H2 {len(h2):2d}/{sum(t.r for t in h2):+10.6f}")
    print(f"    991: {d991}  |  1002: {d1002}  |  P9-Fenster: "
          + " ".join(f"K{t.kid}@{t.bar} {t.r:+.2f}"
                     for t in sorted(V, key=lambda x: x.bar)
                     if 848 <= t.bar <= 1020))
    if 1002 in _s:
        t = _s[1002]
        print(f"    1002-Detail: entry_bar {t.entry_bar} entry {t.entry:.4f} "
              f"sl {t.sl:.4f} poc {t.poc:.4f} tp2 {t.tp2:.4f} "
              f"{t.stufe} resultat {t.resultat} exit "
              f"{t.exit1_bar}/{t.exit2_bar}")
