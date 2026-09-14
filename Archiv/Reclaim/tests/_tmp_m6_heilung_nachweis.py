# -*- coding: utf-8 -*-
"""READ-ONLY Nachweis der M6-Heilung (§72.3) -- isoliert und dreifach.

Die beiden Aenderungen des Ein-Hunk-Patches (§72.2) werden getrennt geprueft:

  A  ``HEUTE``          Extremum + Rueckfall ``self.wicks[0][1]``  (eingebrannt)
  B  ``OHNE_HEILUNG``   Extremum + Rueckfall ``self.basis``       (alter Pfad)
  C  ``ALT``            Mittelwert + Rueckfall ``self.basis``     (Vorgaenger)

Verglichen werden die Sperrlisten (M6/Q29) und der Trade-Satz. Damit ist
entscheidbar, ob die Heilung numerisch inert ist -- Behauptung oder Beweis.

Es werden nur Wegwerf-Engines in ``test/`` erzeugt (nach dem Lauf geloescht).
Die produktive Engine wird NICHT angefasst; die Asserts sind per
``optimize=1`` ausgehebelt, weil B und C bewusst ausserhalb der Arretierung
liegen.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
T = ROOT / "test"
ENGINE = T / "tmp_kanten_engine_replay.py"
RENDERER = T / "tmp_png_aug_sichttest.py"

HEUTE_RET = "        return float(self.wicks[0][1])"
OHNE_RET = "        return float(self.basis)"
EXTREM = ("        if px:\n"
          "            return float(min(px) if self.seite == \"OBEN\" else "
          "max(px))\n")
MITTEL = ("        if px:\n"
          "            return float(np.mean(px))\n")

src = ENGINE.read_text(encoding="utf-8")
assert src.count(HEUTE_RET) == 1 and src.count(EXTREM) == 1, "Engine-Anker"

VAR = {
    "A_HEUTE": src,
    "B_OHNE_HEILUNG": src.replace(HEUTE_RET, OHNE_RET),
    "C_ALT": src.replace(HEUTE_RET, OHNE_RET).replace(EXTREM, MITTEL),
}

HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
_HOLD: List[object] = []


def lauf(name: str, text: str) -> Dict:
    cand = T / f"_tmp_m6_{name}.py"
    cand.write_text(text, encoding="utf-8", newline="")
    mod = types.ModuleType("m6_" + name)
    mod.__file__ = str(RENDERER)
    sys.modules[mod.__name__] = mod
    ns: Dict = mod.__dict__
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = ["t", "--mode", "V017",
                "--engine", f"test/{cand.name}",
                "--probe-praefix", "_m6_",
                "--protokoll-nach", "test/_tmp_m6_out.txt"]
    try:
        exec(compile(HEAD, "<head_m6>", "exec", optimize=1), ns)
    finally:
        _HOLD.append(sys.stdout)
        sys.stdout = old_out
        sys.argv = old_argv
    cand.unlink(missing_ok=True)
    return ns


RES = {}
for _n, _t in VAR.items():
    RES[_n] = lauf(_n, _t)

print("=" * 96)
for _n, ns in RES.items():
    V1 = ns["V1"]
    print(f"{_n:16s} V1 {len(V1):2d} / {sum(t.r for t in V1):+.6f} R | "
          f"H1 {len(ns['h1_1'])} | H2 {len(ns['h2_1'])} | "
          f"NW {ns['NIVEAUWECHSEL']:3d} | "
          f"M6 {len(ns['st1'].get('blocker_liste') or [])} | "
          f"Q29 {len(ns['st1'].get('quartil_liste') or [])}")

A = RES["A_HEUTE"]["st1"]
B = RES["B_OHNE_HEILUNG"]["st1"]
C = RES["C_ALT"]["st1"]
for lbl, key in (("blocker_liste (M6)", "blocker_liste"),
                 ("quartil_liste (Q29)", "quartil_liste")):
    a = list(A.get(key) or [])
    b = list(B.get(key) or [])
    c = list(C.get(key) or [])
    print(f"\n--- {lbl} ---")
    print(f"  A vs B (nur Heilung):  identisch={a == b}"
          f"  ({len(a)} vs {len(b)})")
    print(f"  A vs C (Heilung+Hunk): identisch={a == c}"
          f"  ({len(a)} vs {len(c)})")
    if a != b:
        nur_a = [x for x in a if x not in b]
        nur_b = [x for x in b if x not in a]
        print(f"    nur in A ({len(nur_a)}): {nur_a}")
        print(f"    nur in B ({len(nur_b)}): {nur_b}")

ta = {(t.bar, t.kid) for t in RES["A_HEUTE"]["V1"]}
tb = {(t.bar, t.kid) for t in RES["B_OHNE_HEILUNG"]["V1"]}
tc = {(t.bar, t.kid) for t in RES["C_ALT"]["V1"]}
print("\n--- Trade-Schluessel (bar, kid) ---")
print(f"  A vs B identisch={ta == tb} | A vs C identisch={ta == tc}")
print(f"  A={sorted(ta)}")
print(f"  C={sorted(tc)}")
ra = {k: round(sum(t.r for t in RES["A_HEUTE"]["V1"] if (t.bar, t.kid) == k), 6)
      for k in ta}
rb = {k: round(sum(t.r for t in RES["B_OHNE_HEILUNG"]["V1"] if (t.bar, t.kid) == k),
               6) for k in tb}
print(f"  R je Trade identisch A vs B: {ra == rb}")
print("=" * 96)
