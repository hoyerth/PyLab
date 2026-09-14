# -*- coding: utf-8 -*-
"""READ-ONLY: Bar-Zeiten der K73-/K82-Dochte (Wanduhr + Anwenderzeit -2h)."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
mod = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("km", loader=None))
mod.__file__ = str(P)
sys.modules["km"] = mod
exec(compile(P.read_text(encoding="utf-8"), str(P), "exec"), mod.__dict__)

d = mod._lade_fenster("AUG")
ts = d["ts"].tolist()
lo = d["low"].tolist()
hi = d["high"].tolist()
tief = d["ts"].map(lambda x: x.tz_localize("UTC") if x.tz is None else x)

print("K73 OBEN (Dochte):")
for b, p in [(909, 69.7150), (928, 69.6380), (1023, 69.6840),
             (1122, 69.7090), (1211, 69.6110), (1272, 69.7140)]:
    t = ts[b]
    print(f"  bar {b:4d}  Motor-ts {t}  Anwenderzeit {t - __import__('datetime').timedelta(hours=2)}"
          f"  high {hi[b]:.4f}  low {lo[b]:.4f}")
print("K82 UNTEN (Dochte):")
for b, p in [(1031, 67.5350), (1056, 67.5530), (1172, 67.4940), (1259, 67.6000)]:
    t = ts[b]
    print(f"  bar {b:4d}  Motor-ts {t}  Anwenderzeit {t - __import__('datetime').timedelta(hours=2)}"
          f"  high {hi[b]:.4f}  low {lo[b]:.4f}")
print()
print("Anwender-Marken -> Motor-ts (+2h):")
import datetime as _dt
for lbl, u in [("25.8. 4:45", _dt.datetime(2026, 8, 25, 4, 45)),
               ("25.8. 11:00", _dt.datetime(2026, 8, 25, 11, 0)),
               ("25.8. 15:00", _dt.datetime(2026, 8, 25, 15, 0)),
               ("26.8. 4:30", _dt.datetime(2026, 8, 26, 4, 30)),
               ("26.8. 17:00", _dt.datetime(2026, 8, 26, 17, 0)),
               ("27.8. 3:45", _dt.datetime(2026, 8, 27, 3, 45)),
               ("27.8. 15:45", _dt.datetime(2026, 8, 27, 15, 45)),
               ("27.8. 19:00", _dt.datetime(2026, 8, 27, 19, 0))]:
    ziel = u + _dt.timedelta(hours=2)
    best = min(range(len(ts)), key=lambda i: abs(ts[i] - ziel))
    print(f"  {lbl:12s} -> bar {best:4d} ts {ts[best]} "
          f"high {hi[best]:.4f} low {lo[best]:.4f}")
sys.exit(0)
