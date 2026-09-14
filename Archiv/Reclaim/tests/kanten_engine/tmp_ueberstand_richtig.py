# -*- coding: utf-8 -*-
"""READ-ONLY: Vorzeichenrichtige Ueberstaende je Kante -- AUG n=1288.

Die Systemik-Tabelle in tmp_band_entkopplung2.py nutzte abs(px - basis) --
das ist das CLUSTER-Kriterium (|dist| <= 0.12 %). Fuer einen SWEEP zaehlt
jedoch der vorzeichenrichtige UEBERSTAND jenseits der Basis:
  OBEN : (hi[k]  - basis_bei(k)) / basis_bei(k) * 100  > 0
  UNTEN: (basis_bei(k) - lo[k]) / basis_bei(k) * 100  > 0
Zusaetzlich wird getrennt, ob die Bar ein eigener akzeptierter Docht ist.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_loader("m", loader=None)
m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
m.__file__ = str(P)
sys.modules["m"] = m
exec(compile(P.read_text(encoding="utf-8"), str(P), "exec"), m.__dict__)

cfg = m.StraightEdgeHarnessKonfiguration()
sc = m._se_scan("AUG", cfg)
d = sc["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
n = sc["n"]
alle = list(sc["edges"]) + list(sc["seeds"])

print("=" * 118)
print(f"VORZEICHENRICHTIGE UEBERSTAENDE -- AUG n={n}, {len(alle)} Kanten/Seeds")
print(f"Arretierung: touch_band_pct={cfg.touch_band_pct} % | "
      f"max_sweep={cfg.max_sweep_ueberdehnung_pct} % | "
      f"min_wall_alter_bars={cfg.min_wall_alter_bars}")
print("=" * 118)

zeilen = []
for e in alle:
    pivot = e.erster_pivot_bar
    if pivot < 0:
        continue
    own = {b for b, _ in e.wicks}
    best = -1e9
    best_bar = -1
    best_own = False
    ueber_band = []       # (bar, dist, ist_own, alter_ok)
    for k in range(pivot, n):
        bs = e.basis_bei(k)
        raw = hi[k] if e.seite == "OBEN" else lo[k]
        dist = ((raw - bs) if e.seite == "OBEN" else (bs - raw)) / bs * 100.0
        if dist > best:
            best, best_bar, best_own = dist, k, (k in own)
        if dist > cfg.touch_band_pct:
            ueber_band.append((k, dist, k in own, k - pivot >= cfg.min_wall_alter_bars))
    zeilen.append((best, e.kid, e.seite, e.basis, len(e.wicks),
                   best_bar, best_own, e.ist_prim_anker, ueber_band))

zeilen.sort(reverse=True)
print(f"  {'max_ueber':>9}  {'kid':>5} {'seite':5s} {'basis':>8} {'n':>3} "
      f"{'bar':>5} {'own':>4}  {'>0.12':>6}  Flags")
for best, kid, seite, basis, nw, bb, own, anker, ub in zeilen:
    flags = []
    if anker:
        flags.append("PRIMAER-ANKER")
    if best > cfg.touch_band_pct:
        flags.append(f"UBER-BAND({len(ub)} Bars)")
    print(f"  {best:+9.4f}  K{kid:<4d} {seite:5s} {basis:8.3f} {nw:3d} "
          f"{bb:5d} {'JA' if own else 'nein':>4}  {len(ub):6d}  {', '.join(flags)}")

print("")
n_ueber = sum(1 for z in zeilen if z[0] > cfg.touch_band_pct)
print(f"  Kanten mit max-Ueberstand > {cfg.touch_band_pct} %: "
      f"{n_ueber} / {len(zeilen)}")
print(f"  Kanten mit max-Ueberstand > 0.05 %: "
      f"{sum(1 for z in zeilen if z[0] > 0.05)} / {len(zeilen)}")
print(f"  Kanten, deren MAX-Ueberstand auf einem EIGENEN Docht liegt: "
      f"{sum(1 for z in zeilen if z[6])} / {len(zeilen)}")

print("")
print("=" * 118)
print("BARS JENSEITS DES BANDS (Sweep-Kandidaten) -- Detail")
print("=" * 118)
for best, kid, seite, basis, nw, bb, own, anker, ub in zeilen:
    if not ub:
        continue
    print(f"  K{kid} {seite} basis={basis:.3f} n={nw} "
          f"{'[ANKER]' if anker else ''}")
    for k, dist, o, alt in ub:
        print(f"    bar {k:4d} dist={dist:+7.4f}% eigener_docht={o} "
              f"alter_ok={alt}")
