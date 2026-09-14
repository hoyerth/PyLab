# -*- coding: utf-8 -*-
"""READ-ONLY: Wurzelanalyse -- (a) K20/K31 bei Bar 529, (b) K70 bei Bar 881.

Beide Faelle laufen ueber dieselbe Schwelle: touch_band_pct 0.12 %.
  (a) In-Band-Vorrang: K20 (dist 0.119 %) wird als 'nur beruehrt' verworfen,
      die Kaskade faellt auf K31 (dist 0.318 %) -> K31 handelt.
  (b) Ueberschreitung zu klein: K70 (max 0.077 %) liegt UNTER dem Band
      -> kein Sweep, kein Reclaim.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P8 = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


m = load("ke_w", P8)
cfg = m.StraightEdgeHarnessKonfiguration()
scan = m._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n
trades, stats = m._se_trades(scan, cfg)
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])

print("=" * 112)
print("A) BAR 529 SHORT -- warum K31 statt K20?")
print("=" * 112)
k = 529
sweep = float(hi[k])
for kid in (20, 31):
    e = next(x for x in alle if x.kid == kid)
    b = e.basis_bei(k)
    dist = (sweep - b) / b * 100.0
    print(f"  K{kid}: basis={b:.3f} | high[529]={sweep:.3f} | "
          f"dist={dist:+.4f}% | band={cfg.touch_band_pct:.4f}% | "
          f"touch_conf={e.touch_conf(k)} | anker={e.ist_prim_anker} "
          f"(promo_ab {e.promoviert_ab_bar}) | wicks="
          f"{[(bb, round(p, 3)) for bb, p in e.wicks]}")
print(f"  -> K20 dist {0.1189:.4f}% <= band {cfg.touch_band_pct}% "
      f"=> IN-BAND (Schatten) -> Kaskade faellt nach innen auf K31")
print(f"  -> Entscheidungsmarge: {(cfg.touch_band_pct - (sweep-66.459)/66.459*100):.4f} "
      f"Prozentpunkte (~{(66.459*cfg.touch_band_pct/100) - (sweep-66.459):.4f} USD)")

print("")
print("=" * 112)
print("B) K70 (p8-K67) -- maximaler Ueberstand je OBEN-Kante und Reclaim-Fenster")
print("=" * 112)
e70 = next(x for x in alle if x.kid == 67)
print(f"  K67 (pre-K70): basis={e70.basis:.3f} pivot={e70.erster_pivot_bar} "
      f"geburts={e70.geburts_bar} n={len(e70.wicks)}")
print(f"  wicks: {[(b, round(p, 3)) for b, p in e70.wicks]}")
print("")
print("  Bars, an denen high > basis (Kandidaten fuer Sweep):")
for b, p in e70.wicks:
    if b >= len(hi):
        continue
    ex = (hi[b] - e70.basis) / e70.basis * 100.0
    print(f"    bar {b:4d} wick_high={p:.3f} | high[{b}]={hi[b]:.3f} "
          f"| Ueberstand={ex:+.4f}% | band={cfg.touch_band_pct}% "
          f"| {'UNTER Band -> kein Sweep' if ex <= cfg.touch_band_pct else 'ueber Band'}")

print("")
print("  Maximaler Ueberstand der Kante ueber ihre Lebensdauer:")
mx = -9.9
mxb = -1
for b in range(e70.erster_pivot_bar + 1, n):
    ex = (hi[b] - e70.basis) / e70.basis * 100.0
    if ex > mx:
        mx, mxb = ex, b
print(f"    max Ueberstand = {mx:+.4f}% bei Bar {mxb} "
      f"(high={hi[mxb]:.3f}) | Band={cfg.touch_band_pct}% | "
      f"max_sweep={cfg.max_sweep_ueberdehnung_pct}%")

print("")
print("  Reclaim-Bedingungen (_reclaim_stufe) an den Extrema-Bars:")
for b in (881, 880, 882):
    if b >= n:
        continue
    dist = (hi[b] - e70.basis) / e70.basis * 100.0
    ok_sweep = hi[b] > e70.basis and cfg.touch_band_pct < dist <= cfg.max_sweep_ueberdehnung_pct
    print(f"    bar {b}: O={op[b]:.3f} H={hi[b]:.3f} L={lo[b]:.3f} "
          f"C={cl[b]:.3f} | dist={dist:+.4f}% | Durchstich-Ok={ok_sweep} "
          f"| cl<=basis: {cl[b] <= e70.basis}")

print("")
print("=" * 112)
print("C) SYSTEMIK: Wie viele OBEN/UNTEN-Kanten scheitern NUR am Band?")
print("=" * 112)
print("  Kante | max Ueberstand | Bar | Band-Lage")
eng = []
for e in alle:
    if e.erster_pivot_bar < 0:
        continue
    mx = -9.9
    mxb = -1
    for b in range(e.erster_pivot_bar + 1, n):
        ex = ((hi[b] - e.basis) if e.seite == "OBEN"
              else (e.basis - lo[b])) / e.basis * 100.0
        if ex > mx:
            mx, mxb = ex, b
    eng.append((e.kid, e.seite, mx, mxb, e.touch_anzahl))
eng.sort(key=lambda x: -x[2])
print("  Kanten mit max Ueberstand im kritischen Korridor "
      f"[0.00; {cfg.touch_band_pct * 2:.2f}]%:")
for kid, seite, mx, mxb, nt in eng:
    if 0.0 < mx <= cfg.touch_band_pct * 2:
        mark = ("< BAND -> nie ein Sweep" if mx <= cfg.touch_band_pct
                else "ueber Band")
        print(f"    K{kid:3d} {seite:5s} max={mx:+.4f}% bar {mxb:4d} "
              f"n={nt:2d}  {mark}")
