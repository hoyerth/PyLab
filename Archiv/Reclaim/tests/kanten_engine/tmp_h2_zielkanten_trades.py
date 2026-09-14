# -*- coding: utf-8 -*-
"""READ-ONLY: Welche der 14 Voll-Lauf-Trades liegen an den 5 H2-Zielkanten?

Zielkanten (aus tmp_h2_zeitbezug_diag): K67 (69.946 OBEN), K73 (69.678 OBEN),
K71 (68.891 UNTEN), K77 (68.360 UNTEN), K82 (67.546 UNTEN).

Kein Schreiben, keine Engine-Aenderung.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_h2tr", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
ts = scan["d"]["ts"]
scan["box_end_bar"] = n
setups, stats = engine._se_trades(scan, cfg)

ZIEL_KIDS = {67: "Upper1 69.90", 73: "Upper2 69.62", 71: "Lower1 68.88",
             77: "Lower2 68.40", 82: "Lower3 67.60"}

print("=" * 118)
print("VOLL-LAUF-TRADES (14) | kid, Seite, Basis, Bereich, Zielkanten-Bezug")
print("=" * 118)
print(f"{'bar':>5s} {'Zeit':16s} {'Richt':6s} {'kid':>4s} {'basis':>8s} "
      f"{'H2?':>4s} {'R':>8s}  {'Zielkante?':s}")
for t in setups:
    h2 = "ja" if t.bar >= box_end else "-"
    zk = ZIEL_KIDS.get(t.kid, "")
    print(f"{t.bar:5d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):16s} "
          f"{t.richtung:6s} {t.kid:4d} {t.basis:8.3f} {h2:>4s} "
          f"{t.r:+8.2f}  {zk}")

print("\n" + "=" * 118)
print("H2-BEREICH (bars >= 640): Trades vs. Zielkanten")
print("=" * 118)
h2_tr = [t for t in setups if t.bar >= box_end]
print(f"  Trades im H2-Bereich: {len(h2_tr)} / "
      f"{sum(t.r for t in h2_tr):+.2f} R")
for t in h2_tr:
    print(f"    bar {t.bar:4d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M')} "
          f"{t.richtung:5s} K{t.kid:<3d} basis={t.basis:8.3f} "
          f"R={t.r:+7.2f}  {'<== ZIELKANTE ' + ZIEL_KIDS[t.kid] if t.kid in ZIEL_KIDS else ''}")

print("\n" + "=" * 118)
print("Zielkanten: wurden sie gehandelt?")
print("=" * 118)
alle = list(scan["edges"]) + list(scan["seeds"])
for kid, label in sorted(ZIEL_KIDS.items()):
    e = next((x for x in alle if x.kid == kid), None)
    if e is None:
        print(f"  K{kid:<3d} {label:16s} NICHT GEFUNDEN")
        continue
    tr = [t for t in setups if t.kid == kid]
    print(f"  K{kid:<3d} {label:16s} {e.seite:6s} basis={e.basis:7.3f} "
          f"Touches={e.touch_anzahl:2d} | Trades: {len(tr)}"
          f"{' ' + ', '.join(f'bar {t.bar} ({t.r:+.2f} R)' for t in tr) if tr else ''}")
