# -*- coding: utf-8 -*-
"""READ-ONLY M6-Trockenpruefung (Schritt 2 des Anwenderplans).

1) Feuert die Fallback-Zeile ``return self.basis`` ueberhaupt -- und wie oft?
2) Aendert der geheilte Rueckfall ``float(self.wicks[0][1])`` irgendeinen
   Trade, RB oder die Kantenmenge?

Keine Datei wird veraendert; alles in-memory.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SRC = P.read_text(encoding="utf-8")

B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""

F_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if px:
            return float(min(px) if self.seite == "OBEN" else max(px))
        return float(self.wicks[0][1])"""

# F ohne Heilung (heutiger Stand) und F mit Heilung -- beide zaehlen zusaetzlich.
F_RAW = F_BASIS.replace("        return float(self.wicks[0][1])",
                        "        globals().setdefault('_FALLBACK', []).append(int(k))\n"
                        "        return float(self.basis)")
F_HEAL = F_BASIS
ZAEHL = "        globals().setdefault('_FALLBACK', []).append(int(k))\n"
ZAEHL12 = "            globals().setdefault('_FALLBACK', []).append(int(k))\n"
CNT_RAW = B_BASIS.replace("        return float(np.mean(px)) if px else self.basis",
                          "        if not px:\n" + ZAEHL12 +
                          "            return float(self.basis)\n"
                          "        return float(np.mean(px))")
ZAEHLER = {"BASELINE": CNT_RAW, "F_raw": F_RAW, "F_heal": F_HEAL}
QUELLE = {"BASELINE": SRC, "F_raw": SRC.replace(B_BASIS, F_RAW),
          "F_heal": SRC.replace(B_BASIS, F_HEAL)}


def baue(name: str):
    src = SRC.replace(B_BASIS, ZAEHLER[name])
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("kz2_" + name, loader=None))
    mod.__file__ = str(P)
    sys.modules["kz2_" + name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


def lauf(name: str):
    eng = baue(name)
    cfg = eng.StraightEdgeHarnessKonfiguration()
    scan = eng._se_scan("AUG", cfg)
    n, box = scan["n"], scan["box_end_bar"]
    s2 = dict(scan)
    s2["box_end_bar"] = n
    trades, st = eng._se_trades(s2, cfg)
    return eng, scan, trades, st, n, box


ERGEBNIS: Dict[str, Tuple] = {}
for name in ("BASELINE", "F_raw", "F_heal"):
    eng, scan, trades, st, n, box = lauf(name)
    fb: List[int] = getattr(eng, "_FALLBACK", [])
    h1 = [t for t in trades if t.entry_bar < box]
    h2 = [t for t in trades if t.entry_bar >= box]
    print(f"=== {name} ===")
    print(f"  Fallback-Aufrufe (px leer): {len(fb)}"
          + (f"  Bars {sorted(set(fb))[:12]}" if fb else ""))
    print(f"  Trades {len(trades)} / {sum(t.r for t in trades):+.6f} R   "
          f"H1 {len(h1)}/{sum(t.r for t in h1):+.6f}   "
          f"H2 {len(h2)}/{sum(t.r for t in h2):+.6f}")
    print(f"  Blocker {st.get('blocker')}  frisch_blockiert {st.get('frisch_blockiert')}  "
          f"promotionen {st.get('promotionen')}")
    print(f"  Kanten {len(scan['edges'])} / Seeds {len(scan['seeds'])}")
    print(f"  {(sorted((t.bar, t.kid, round(t.r, 6)) for t in trades))}")
    print()
    ERGEBNIS[name] = (scan, trades, st, n, box, fb)

print("=== DIFF F_raw -> F_heal ===")
a = {(t.bar, t.kid): t.r for t in ERGEBNIS["F_raw"][1]}
b = {(t.bar, t.kid): t.r for t in ERGEBNIS["F_heal"][1]}
print(f"  Trades identisch: {sorted(a) == sorted(b)}")
print(f"  nur F_raw : {sorted(set(a) - set(b))}")
print(f"  nur F_heal: {sorted(set(b) - set(a))}")
ge = [(k, round(a[k], 6), round(b[k], 6)) for k in sorted(set(a) & set(b))
      if abs(a[k] - b[k]) > 1e-9]
print(f"  R geaendert: {ge if ge else 'KEINE'}")
sa, sb = ERGEBNIS["F_raw"][2], ERGEBNIS["F_heal"][2]
print(f"  Blocker  F_raw={sa.get('blocker')}  F_heal={sb.get('blocker')}")
print(f"  Kanten   F_raw={len(ERGEBNIS['F_raw'][0]['edges'])}  "
      f"F_heal={len(ERGEBNIS['F_heal'][0]['edges'])}")
sys.exit(0)
