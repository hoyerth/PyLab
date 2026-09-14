# -*- coding: utf-8 -*-
"""E-34n/4 — Konfigurationswerte + exakte Reclaim-Rechnung fuer 1072..1076."""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_loader("ke_e34n4", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ROOT / "test" / "tmp_kanten_engine_replay.py")
sys.modules["ke_e34n4"] = eng
exec(compile((ROOT / "test" / "tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8"), "k", "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
print("=" * 100)
print("E-34n/4  KONFIGURATION")
print("=" * 100)
for f in dataclasses.fields(cfg):
    print(f"  {f.name:<40} {getattr(cfg, f.name)}")
print(f"  SE_HARNESS_MIN_TOUCH_ABSTAND (Modul)      "
      f"{eng.SE_HARNESS_MIN_TOUCH_ABSTAND}")

scan = eng._se_scan("AUG", cfg)
d = scan["d"]
ts = d["ts"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
k82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
           if int(e.kid) == 82)
k62 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
           if int(e.kid) == 62)

print("\n" + "=" * 100)
print("EXAKTE RECLAIM-RECHNUNG K82/K62 gegen die BARS 1071..1080")
print("=" * 100)
print(f"{'bar':>5} {'BKZ':>12} {'O':>8} {'H':>8} {'L':>8} {'C':>8}")
for k in range(1071, 1081):
    print(f"{k:>5} {ts.iloc[k].strftime('%d.%m. %H:%M'):>12} {op[k]:>8.4f} "
          f"{hi[k]:>8.4f} {lo[k]:>8.4f} {cl[k]:>8.4f}")

for name, e in (("K82", k82), ("K62", k62)):
    print(f"\n--- {name} (statische basis {float(e.basis):.4f}) ---")
    print(f"{'bar':>5} {'basis_bei':>9} {'dist_u%':>8} {'>mind?':>6} "
          f"{'<max?':>6} {'c>=b?':>6}  Stufe1  Stufe2  Stufe3")
    for k in range(1071, 1080):
        b = float(e.basis_bei(k))
        du = (b - lo[k]) / b * 100.0
        m1 = cl[k] >= b
        s2 = (k + 1 < len(cl) and cl[k + 1] >= b
              and lo[k + 1] >= lo[k] - cfg.doppeltop_puffer_usd)
        s3 = (k + 2 < len(cl) and cl[k + 2] >= b
              and min(lo[k + 1], lo[k + 2]) >= lo[k] - cfg.doppeltop_puffer_usd)
        st = eng._reclaim_stufe("UNTEN", k, b, hi, lo, cl, cfg)
        print(f"{k:>5} {b:>9.4f} {du:>8.4f} "
              f"{str(du > cfg.sweep_mindestdurchstich_pct):>6} "
              f"{str(du <= cfg.max_sweep_ueberdehnung_pct):>6} "
              f"{str(m1):>6}  {str(st[0] == 1):>6}  {str(s2):>6}  {str(s3):>6}"
              f"   -> {st}")

print("\n" + "=" * 100)
print("PLATEAU-KANDIDATEN (Kantenlaeufer-Touch) im Band 66.5..70.5")
print("=" * 100)
print("Kriterium: dist_u in (mindestdurchstich, max_ueberdehnung], Bar nicht "
      "als Docht akzeptiert")
alle = list(scan["edges"]) + list(scan["seeds"])
for e in sorted(alle, key=lambda x: int(x.kid)):
    if not (66.5 <= float(e.basis) <= 70.5):
        continue
    _wb = {b for b, _ in e.wicks}
    _pl = []
    for k in range(int(e.erster_pivot_bar) + 2, scan["n"]):
        b = float(e.basis_bei(k))
        du = (b - lo[k]) / b * 100.0
        if (cfg.sweep_mindestdurchstich_pct < du
                <= cfg.max_sweep_ueberdehnung_pct) and k not in _wb:
            _pl.append((k, du))
    if not _pl:
        continue
    print(f"  K{int(e.kid)} {e.seite} basis={float(e.basis):.4f} "
          f"pivot={int(e.erster_pivot_bar)} n_w={len(e.wicks)} "
          f"-> {len(_pl)} Kandidaten-Bars: "
          f"{' '.join(f'{k}({d:.2f}%)' for k, d in _pl)}")
print("\nENDE E-34n/4")
