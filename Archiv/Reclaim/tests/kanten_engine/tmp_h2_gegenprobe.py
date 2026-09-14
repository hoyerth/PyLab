# -*- coding: utf-8 -*-
"""READ-ONLY: Gegenprobe K51 (Trade bar 760 vs. geburts_bar 769) + H2-Kennzahlen."""
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


engine = load("ke_g", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
scan["box_end_bar"] = scan["n"]
trades, stats = engine._se_trades(scan, cfg)
alle = list(scan["edges"]) + list(scan["seeds"])

print("=" * 100)
print("GEGENPROBE: Trade-Attribution vs. Kanten-Objekt (AUG Voll-Lauf)")
print("=" * 100)
for t in trades:
    e = next((x for x in alle if x.kid == t.kid), None)
    if e is None:
        print(f"  bar {t.bar} K{t.kid}: KEIN Objekt gefunden!")
        continue
    w = e.wicks
    conf = e.touch_conf(t.bar)
    print(f"  trade bar {t.bar:4d} {t.richtung:5s} K{t.kid:3d} {e.seite:5s} "
          f"| geburts={e.geburts_bar:4d} pivot={e.erster_pivot_bar:4d} "
          f"| wicks={[(b, round(p, 3)) for b, p in w]} "
          f"| touch_conf(trade_bar)={conf} | prim={e.ist_prim_anker} "
          f"| R={t.r:+.2f}")

print("")
print("=" * 100)
print("H2-TRADE-BILANZ (bars >= 644)")
print("=" * 100)
h2 = [t for t in trades if t.bar >= 644]
box = [t for t in trades if t.bar < 644]
print(f"  BOX  : {len(box)} Trades / {sum(t.r for t in box):+.2f} R")
print(f"  H2   : {len(h2)} Trades / {sum(t.r for t in h2):+.2f} R")
short_h2 = [t for t in h2 if t.richtung == "SHORT"]
long_h2 = [t for t in h2 if t.richtung == "LONG"]
print(f"    SHORT: {len(short_h2)} / {sum(t.r for t in short_h2):+.2f} R "
      f"{[(t.bar, t.kid, round(t.r, 2)) for t in short_h2]}")
print(f"    LONG : {len(long_h2)} / {sum(t.r for t in long_h2):+.2f} R "
      f"{[(t.bar, t.kid, round(t.r, 2)) for t in long_h2]}")

geb = [e for e in alle if e.geburts_bar >= 644]
gehandelt = {t.kid for t in h2}
print("")
print(f"  H2-Neugeburten: {len(geb)} | davon gehandelt: "
      f"{sum(1 for e in geb if e.kid in gehandelt)}")
print(f"  H2-Geburten OBEN : {sum(1 for e in geb if e.seite == 'OBEN')}")
print(f"  H2-Geburten UNTEN: {sum(1 for e in geb if e.seite == 'UNTEN')}")
print(f"  H2-Geburten mit 1 Touch (Seed): "
      f"{sum(1 for e in geb if e.touch_anzahl == 1)}")
print(f"  H2-Geburten mit >= 2 Touches  : "
      f"{sum(1 for e in geb if e.touch_anzahl >= 2)}")
print(f"  H2-Geburten >= 3 Touches      : "
      f"{sum(1 for e in geb if e.touch_anzahl >= 3)}")
print("")
print("  Nie gehandelte H2-Geburten (kid/seite/geburts/touches):")
for e in sorted(geb, key=lambda x: x.geburts_bar):
    if e.kid not in gehandelt:
        print(f"    K{e.kid:3d} {e.seite:5s} geb={e.geburts_bar:4d} "
              f"basis={e.basis:.3f} n={e.touch_anzahl}")
