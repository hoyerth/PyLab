"""Read-only: prueft ``verifiziere_gegen_scan`` fuer die V019-Segmentstarts.

Zweck: Kandidaten-Referenzbars fuer die Einbindung in den Renderer-V019-Pfad
bestimmen (welche ``basis_bei(ref)``-Referenz besteht die Fail-Loud-Pruefung).
Kein Schreibzugriff auf Engine/Adapter/Renderer.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)  # type: ignore[union-attr]

scan = eng._se_scan("AUG", eng.StraightEdgeHarnessKonfiguration())

starts = [int(s.start_bar) for s in ADAPTER_V019.segmente]
print("V019-Segmentstarts:", starts)

for ref in (848, 1033, 1174, 1287, *starts):
    kanten = [(e.kid, e.seite, float(e.basis_bei(ref)))
              for e in list(scan["edges"]) + list(scan["seeds"])]
    try:
        ADAPTER_V019.verifiziere_gegen_scan(kanten)
        print(f"  REF {ref:>5}  OK")
    except ValueError as exc:
        print(f"  REF {ref:>5}  FAIL  {exc}")

# --- Negativkontrollen: der Fail-Loud greift (Basis = die Renderer-Logik) ---
BASE = [(e.kid, e.seite, float(e.basis_bei(848)))
        for e in list(scan["edges"]) + list(scan["seeds"])]
NEG = {
    "Kante fehlt": [k for k in BASE if k[0] != 67],
    "Seite vertauscht": [(k[0], "UNTEN" if k[1] == "OBEN" else "OBEN", k[2])
                         for k in BASE],
    "Basis 3 % daneben": [(k[0], k[1], k[2] * 1.03) for k in BASE],
    "Basis 0 (ungueltig)": [(k[0], k[1], 0.0) for k in BASE],
}
for name, kanten in NEG.items():
    try:
        ADAPTER_V019.verifiziere_gegen_scan(kanten)
        print(f"  NEG {name:<20} UNERWARTET OK")
    except ValueError as exc:
        print(f"  NEG {name:<20} fail-loud OK  ({str(exc)[:60]}...)")
