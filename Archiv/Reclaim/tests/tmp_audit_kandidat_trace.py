# -*- coding: utf-8 -*-
"""READ-ONLY: Gate-Kaskade von `_kandidat` an den Mentor-Signal-Bars
980 und 1020 -- warum die Engine dort KEINEN Trade erzeugt.

Reimplementiert die Pool-Bildung von `_se_trades._kandidat` (arretierte
Regeln) und protokolliert jedes Gate einzeln. Kein Engine-Patch.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import numpy as np

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


engine = load("ke_tr", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = len(scan["d"])
scan["box_end_bar"] = n
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
ts = d["ts"]
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
oben = [e for e in alle if e.seite == "OBEN"]

for k in (980, 1020):
    sweep = float(hi[k])
    print("=" * 122)
    print(f"k = {k} ({ts.iloc[k].strftime('%d.%m. %H:%M')} Berlin) | "
          f"high(Sweep) = {sweep:.4f} | close = {cl[k]:.4f}")
    print("=" * 122)
    print(f"  {'K':>4s} {'basis_bei(k)':>12s} {'touch_conf':>10s} "
          f"{'_existiert':>10s} {'_etabliert':>10s} {'_lebt':>6s} "
          f"{'dist%':>8s}  Gate-Status")
    pool = []
    for e in sorted(oben, key=lambda x: x.basis_bei(k), reverse=True):
        basis = e.basis_bei(k)
        dist = (sweep - basis) / basis * 100.0
        ex = e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1
        et = k - e.erster_pivot_bar >= cfg.min_wall_alter_bars
        bars = [b for b, _ in e.wicks if b <= k]
        lebt = bool(bars) and max(bars) >= k - cfg.wall_live_bars
        pool_ok = ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                   or e.touch_conf(k) >= 2)
        status = []
        if not ex:
            status.append("KEIN EXIST")
        if not pool_ok:
            status.append("POOL (2-Touch)")
        if not et:
            status.append(f"REIFE ({k - e.erster_pivot_bar}<{cfg.min_wall_alter_bars})")
        if ex and pool_ok and et:
            status.append("im Pool")
            pool.append((e, dist))
        print(f"  {e.kid:4d} {basis:12.4f} {e.touch_conf(k):10d} "
              f"{str(ex):>10s} {str(et):>10s} {str(lebt):>6s} {dist:+8.4f}  "
              f"{'; '.join(status)}")
    print(f"  -> Pool (existiert+2Touch+Reife, sortiert aussen->innen): "
          f"{[(x[0].kid, round(x[1], 4)) for x in pool] or 'LEER'}")
    verdict = "KEIN TRADE (Pool leer)"
    for pos, (e, dist) in enumerate(pool):
        if dist < 0.0:
            bars = [b for b, _ in e.wicks if b <= k]
            lebt = bool(bars) and max(bars) >= k - cfg.wall_live_bars
            verdict = (f"pos{pos} K{e.kid} dist={dist:+.4f}% < 0 -> "
                       f"{'WAND LEBT -> return None' if lebt else 'dormant -> continue'}")
            if lebt:
                break
            continue
        if dist > cfg.max_sweep_ueberdehnung_pct:
            verdict = (f"pos{pos} K{e.kid} dist={dist:+.4f}% -> "
                       f"UEBERDEHNUNG, return None")
            break
        if dist <= cfg.sweep_mindestdurchstich_pct:
            continue
        if pos == 0:
            verdict = f"pos{pos} K{e.kid} dist={dist:+.4f}% -> HANDELT (Q1)"
            break
        if e.touch_conf(k) < cfg.min_touches_handelbar:
            continue
        verdict = (f"pos{pos} K{e.kid} dist={dist:+.4f}% -> HANDELT "
                   f"(innere Linie, V-S={e.touch_conf(k)})")
        break
    print(f"  -> VERDIKT: {verdict}")
    print()

print("=" * 122)
print("ZUSAMMENFASSUNG DER SPERREN")
print("=" * 122)
for k in (980, 1020):
    sweep = float(hi[k])
    k67, k73 = by_kid[67], by_kid[73]
    print(f"  bar {k}: K67 basis={k67.basis_bei(k):.4f} (ueber Sweep "
          f"{sweep:.4f}, Abstand {k67.basis_bei(k) - sweep:+.4f} USD = "
          f"{(k67.basis_bei(k) - sweep) / k67.basis_bei(k) * 100:+.3f}%) | "
          f"K67 letzter Docht bar {max(b for b, _ in k67.wicks if b <= k)} "
          f"-> LEBT -> 'kein Fade unter der Wand' sperrt K73.")
