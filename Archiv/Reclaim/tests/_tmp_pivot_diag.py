# -*- coding: utf-8 -*-
"""READ-ONLY: Warum fehlt der 5. K82-Touch? Pivot-/Banddiagnose bar 1060-1085."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_pivot", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
d = scan["d"]
ts = d["ts"].tolist()
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
n = scan["n"]

print("Pivot-Diagnose (mbar = k-2, Docht-Erkennung) fuer 1055..1085:")
for mbar in range(1055, 1086):
    typen = engine._pivot_dual(hi, lo, mbar)
    if typen:
        px = [float(hi[mbar]) if t == "H" else float(lo[mbar]) for t in typen]
        print(f"  mbar {mbar} {ts[mbar]}  Pivot {typen}  px {px}")

print()
print("K82 wicks (n=4): 1031 / 1056 / 1172 / 1259")
b = 67.5440  # mean(67.5350, 67.5530) nach Touch #2
print(f"Band bei Touch #2 (basis {b:.4f}, 0.23 %): "
      f"[{b * (1 - 0.0023):.4f} .. {b * (1 + 0.0023):.4f}]")
for bar in (1064, 1067, 1072, 1073, 1075):
    print(f"  bar {bar} {ts[bar]}  low={lo[bar]:.4f}  "
          f"in Band: {abs(lo[bar] - b) / b * 100.0 <= 0.23}")
print()
print("SE_HARNESS_MIN_TOUCH_ABSTAND =",
      getattr(engine, "SE_HARNESS_MIN_TOUCH_ABSTAND", "?"),
      "| touch_band_pct =", cfg.touch_band_pct)
sys.exit(0)
