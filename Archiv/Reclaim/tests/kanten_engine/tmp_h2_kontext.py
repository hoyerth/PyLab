# -*- coding: utf-8 -*-
"""READ-ONLY: Preis-Kontext der H2-Trades + Rallye-Form (AUG)."""
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


engine = load("ke_k", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
n = len(d)
scan["box_end_bar"] = n
trades, stats = engine._se_trades(scan, cfg)

print("=" * 108)
print("RALLYE-FORM AUG (Bars 0..1288): Close-Stuetzpunkte")
print("=" * 108)
for k in (0, 200, 400, 500, 600, 644, 700, 760, 800, 853, 900, 1000, 1039,
          1100, 1200, 1287):
    print(f"  bar {k:4d}  close={cl[k]:7.3f}  high={hi[k]:7.3f} "
          f"low={lo[k]:7.3f}")
print(f"  Fenster-Extrema: high={hi.max():.3f} (bar {int(hi.argmax())}) | "
      f"low={lo.min():.3f} (bar {int(lo.argmin())})")
print(f"  Box-Extrema (0..643): high={hi[:644].max():.3f} | "
      f"low={lo[:644].min():.3f}")
print(f"  H2-Extrema (644..):  high={hi[644:].max():.3f} | "
      f"low={lo[644:].min():.3f}")

print("")
print("=" * 108)
print("KONTEXT DER H2-TRADES (Entry-Bar +/- 2)")
print("=" * 108)
for t in trades:
    if t.bar < 644:
        continue
    eb = t.entry_bar
    print(f"  bar {t.bar:4d} {t.richtung:5s} K{t.kid:3d} entry={eb} "
          f"basis={t.basis:.3f} sweep={t.sweep:.3f} R={t.r:+.2f} "
          f"resultat={t.resultat}")
    for k in range(max(0, eb - 2), min(n, eb + 3)):
        print(f"      k={k:4d} O={d['open'].to_numpy()[k]:7.3f} "
              f"H={hi[k]:7.3f} L={lo[k]:7.3f} C={cl[k]:7.3f}")
