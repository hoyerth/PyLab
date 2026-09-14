# -*- coding: utf-8 -*-
"""READ-ONLY: Vollstaendige Inventur der EINGEBRANNTEN Engine V017 (4a356765).

Zweck: Belege fuer das Spez-Addendum §72. Es wird nichts geschrieben und keine
PNG erzeugt -- ausgefuehrt wird nur der Renderer-Kopf (alles vor dem Plot-Teil).
Die Engine wird NICHT veraendert; die Sollwert-Asserts bleiben scharf.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"

HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
_HOLD: List[object] = []

mod = types.ModuleType("doku_inventur_v017")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old_argv, _old_out = sys.argv, sys.stdout
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_doku_",
            "--protokoll-nach", "test/_tmp_doku_inventur_out.txt"]
try:
    exec(compile(HEAD, "<head_v017_doku>", "exec"), ns)
finally:
    _HOLD.append(sys.stdout)
    sys.stdout = _old_out
    sys.argv = _old_argv

V0, VB, V1 = ns["V0"], ns["V1_basis"], ns["V1"]
h1, h2 = ns["h1_1"], ns["h2_1"]
scan, n = ns["scan"], ns["n"]

print("=" * 96)
print(f"ENGINE {ns['ENGINE_NAME']}  SHA256 {ns['ENGINE_SHA']}")
print(f"Modus {ns['KONF'].mode} | n={n} box_end={ns['box_end']}")
print("=" * 96)
print(f"V0  (Engine roh)  : {len(V0):2d} / {sum(t.r for t in V0):+.6f} R"
      f"   (H1 {sum(1 for t in V0 if t.entry_bar < ns['box_end'])}"
      f" | H2 {sum(1 for t in V0 if t.entry_bar >= ns['box_end'])})")
print(f"V1_basis (v0.1)   : {len(VB):2d} / {sum(t.r for t in VB):+.6f} R"
      f"   <- R_B")
print(f"V1_aktiv (V017)   : {len(V1):2d} / {sum(t.r for t in V1):+.6f} R"
      f"   <- R1")
print(f"H1  : {len(h1)} / {sum(t.r for t in h1):+.6f} R")
print(f"H2  : {len(h2)} / {sum(t.r for t in h2):+.6f} R")
print(f"P9_BEITRAG {ns['P9_BEITRAG']:+.6f} | QUARTETT_R {ns['QUARTETT_R']:+.6f}"
      f" | DELTA(R1-RB) {sum(t.r for t in V1) - sum(t.r for t in VB):+.6f}")

print("\n--- V0 (Engine roh) Trade-Tabelle ---")
for t in sorted(V0, key=lambda x: x.bar):
    print(f"  K{t.kid:<4} bar {t.bar:<5} entry_bar {t.entry_bar:<5} "
          f"{t.richtung:<5} {t.stufe:<14} entry {t.entry:.4f} sl {t.sl:.4f} "
          f"tp2 {t.tp2:.4f} r {t.r:+.6f}")

print("\n--- V1_basis (v0.1-Referenzlauf) Trade-Tabelle ---")
for t in sorted(VB, key=lambda x: x.bar):
    print(f"  K{t.kid:<4} bar {t.bar:<5} entry_bar {t.entry_bar:<5} "
          f"{t.richtung:<5} {t.stufe:<14} entry {t.entry:.4f} sl {t.sl:.4f} "
          f"tp2 {t.tp2:.4f} r {t.r:+.6f}")

print("\n--- V1_aktiv (V017) Trade-Tabelle ---")
for t in sorted(V1, key=lambda x: x.bar):
    print(f"  K{t.kid:<4} bar {t.bar:<5} entry_bar {t.entry_bar:<5} "
          f"{t.richtung:<5} {t.stufe:<14} entry {t.entry:.4f} sl {t.sl:.4f} "
          f"tp2 {t.tp2:.4f} r {t.r:+.6f}")

print("\n--- H1 (entry_bar < box_end) ---")
for t in sorted(h1, key=lambda x: x.bar):
    print(f"  K{t.kid:<4} bar {t.bar:<5} entry_bar {t.entry_bar:<5} "
          f"{t.richtung:<5} {t.stufe:<14} r {t.r:+.6f}")
print(f"  Eintritts-Bars: {sorted(t.entry_bar for t in h1)}")
print(f"  Signal-Bars   : {sorted(t.bar for t in h1)}")

print("\n--- H2 (entry_bar >= box_end) ---")
for t in sorted(h2, key=lambda x: x.bar):
    print(f"  K{t.kid:<4} bar {t.bar:<5} entry_bar {t.entry_bar:<5} "
          f"{t.richtung:<5} {t.stufe:<14} r {t.r:+.6f}")

print("\n--- G4 ---")
for t in ns["G4_TRADES"]:
    print(f"  K{t.kid}@{t.bar} entry {t.entry:.4f} sl {t.sl:.4f} "
          f"tp2 {t.tp2:.4f} r {t.r:+.6f} {t.richtung}")

print("\n--- Quartett / P9 ---")
_q = {t.bar: t for t in V1 if t.bar in ns["KONF"].quartett_bars}
for b in sorted(_q):
    t = _q[b]
    print(f"  K{t.kid}@{b} {t.stufe} entry {t.entry:.4f} sl {t.sl:.4f} "
          f"r {t.r:+.6f}")
print(f"  QUARTETT-R {sum(t.r for t in _q.values()):+.6f}")
print(f"  K67-Quartett-Summe "
      f"{sum(t.r for t in V1 if t.kid == 67 and t.bar in ns['KONF'].quartett_bars):+.6f}")

print("\n--- Mengendifferenzen ---")
print("  REFERENZ (V1_basis \\ V1_aktiv): "
      f"{[(t.bar, t.kid, round(t.r, 6)) for t in sorted(ns['REFERENZ'], key=lambda x: x.bar)]}")
print("  NEU (V1_aktiv \\ V1_basis): "
      f"{[(t.bar, t.kid, round(t.r, 6)) for t in sorted(ns['NEU'], key=lambda x: x.bar)]}")
_rk = {(t.bar, t.kid) for t in ns["REFERENZ"]}
print("  H1-Entfallene gegenueber V016 (K8@383, K8@620):")
for t in sorted(VB, key=lambda x: x.bar):
    if t.entry_bar < ns["box_end"] and (t.bar, t.kid) in _rk:
        print(f"    K{t.kid}@{t.bar} {t.richtung} {t.stufe} "
              f"entry {t.entry:.4f} r {t.r:+.6f}")

print("\n--- Niveaus / Zaehler ---")
_kk = {e.kid: e for e in scan["edges"] + scan["seeds"]}
for k in (67, 73, 77, 82):
    print(f"  K{k}  basis {_kk[k].basis:.4f}  basis_bei({n-1}) "
          f"{_kk[k].basis_bei(n - 1):.4f}  seite {_kk[k].seite}")
print(f"  Niveauwechsel (maskiert) {ns['NIVEAUWECHSEL']}")
print(f"  Kanten {len(scan['edges'])} edges + {len(scan['seeds'])} seeds")
print("  Hinweis: WECHSEL/GATE_Q29/GATE_M6 liegen hinter dem Plot-Marker und")
print("           sind hier bewusst nicht im Namespace (Werte: Protokoll).")
print("=" * 96)
