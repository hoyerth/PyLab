# -*- coding: utf-8 -*-
"""E-33 PROBE -- Kanten der AUG-Zielzone (1021..1287).

Aufruf: python test/_tmp_e33_probe.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
print(f"n {n}  box_end_bar {scan['box_end_bar']}  "
      f"edges {len(scan['edges'])} seeds {len(scan['seeds'])}")
alle = list(scan["edges"]) + list(scan["seeds"])

for k in (1021, 1072, 1122, 1170, 1171, 1172, 1259, 1272, 1287):
    oben = sorted(((e.basis_bei(k), e.kid) for e in alle
                   if e.seite == "OBEN"), reverse=True)
    unten = sorted(((e.basis_bei(k), e.kid) for e in alle
                    if e.seite == "UNTEN"))
    print("")
    print(f"--- Bar {k} ---")
    print("   OBEN  (aeusserste 6): "
          + " | ".join(f"K{kid}={b:.4f}" for b, kid in oben[:6]))
    print("   UNTEN (aeusserste 6): "
          + " | ".join(f"K{kid}={b:.4f}" for b, kid in unten[:6]))

print("")
print("--- Kantenalter/Promotion (OBEN/UNTEN) ---")
for e in sorted(alle, key=lambda x: x.kid):
    if e.kid in (67, 73, 77, 82, 85, 76, 62, 60, 63, 48, 3, 17):
        print(f"   K{e.kid:3d} {e.seite:5s} basis={e.basis:.4f} "
              f"geb={e.geburts_bar:4d} erster_pivot={e.erster_pivot_bar:4d} "
              f"n_wicks={e.touch_anzahl} anker={e.ist_prim_anker} "
              f"promo_ab={e.promoviert_ab_bar} "
              f"wicks={[b for b, _ in e.wicks][:12]}...")
