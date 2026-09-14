# -*- coding: utf-8 -*-
"""READ-ONLY: Welche Bars tragen exakt die Ziel-Level (Toleranz 0.004)?

Hypothese aus dem Abgleich: Die Ziel-Level entsprechen dem INNERSTEN Touch
(OBEN: min der Highs; UNTEN: max der Lows) der genannten Touch-Menge --
nicht dem Mittelwert (Engine-`basis`).

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


engine = load("ke_h2level", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
ts = d["ts"]
idx_von_zeit = {ts.iloc[i].strftime("%d.%m. %H:%M"): i for i in range(n)}

ZIEL = [
    ("Upper1", "OBEN", 69.90,
     ["21.08. 10:30", "21.08. 13:15", "21.08. 18:45",
      "24.08. 15:00", "25.08. 02:00"]),
    ("Upper2", "OBEN", 69.62,
     ["26.08. 04:30", "27.08. 03:45", "27.08. 19:00"]),
    ("Lower1", "UNTEN", 68.88, ["21.08. 16:30"]),
    ("Lower2", "UNTEN", 68.40,
     ["24.08. 03:30", "24.08. 17:45", "24.08. 20:00"]),
    ("Lower3", "UNTEN", 67.60,
     ["25.08. 04:45", "25.08. 11:00", "25.08. 15:00",
      "26.08. 17:00", "27.08. 15:45"]),
]

print("=" * 122)
print("1) SUCHE: Bars im H2 mit high/low exakt auf dem Ziel-Level "
      "(Toleranz 0.004, H2 = bars >= 640)")
print("=" * 122)
for name, seite, level, _z in ZIEL:
    arr = hi if seite == "OBEN" else lo
    treffer = [b for b in range(box_end, n)
               if abs(arr[b] - level) <= 0.004]
    print(f"\n{name:7s} Ziel {level:7.2f} ({seite})  ->  {len(treffer)} Treffer")
    for b in treffer:
        print(f"    bar {b:4d} {ts.iloc[b].strftime('%d.%m. %H:%M')} | "
              f"O {op[b]:.3f} H {hi[b]:.3f} L {lo[b]:.3f} C {cl[b]:.3f} | "
              f"Docht {arr[b]:.3f} (Delta {arr[b] - level:+.3f})")

print("\n" + "=" * 122)
print("2) INNERSTER TOUCH je Ziel-Menge (Ziel-Zeit als UTC-Projektion, +8 Bars)")
print("=" * 122)
print(f"{'Kante':7s} {'n':>2s} {'Mittelwert':>11s} {'innerster':>10s} "
      f"{'Ziel':>8s} {'Delta(Mittel)':>14s} {'Delta(innerst)':>15s}")
for name, seite, level, zeiten in ZIEL:
    bs = [idx_von_zeit[z] + 8 for z in zeiten if z in idx_von_zeit]
    px = [hi[b] if seite == "OBEN" else lo[b] for b in bs]
    mittel = sum(px) / len(px)
    innerst = min(px) if seite == "OBEN" else max(px)
    print(f"{name:7s} {len(px):2d} {mittel:11.4f} {innerst:10.4f} "
          f"{level:8.2f} {mittel - level:+14.4f} {innerst - level:+15.4f}")

print("\n" + "=" * 122)
print("3) ENGINE-`basis` (Mittel der Kanten-Wicks) vs. Ziel-Level")
print("=" * 122)
alle = list(scan["edges"]) + list(scan["seeds"])
print(f"{'Ziel':7s} {'Ziel-Lvl':>9s} {'Kante':>5s} {'basis':>8s} "
      f"{'Touches':>7s} {'innerster Wick':>15s} {'Delta':>8s}")
for name, seite, level, _z in ZIEL:
    kand = [e for e in alle if e.seite == seite]
    e = min(kand, key=lambda x: abs(x.basis - level))
    wpx = [p for _, p in e.wicks]
    inn = min(wpx) if seite == "OBEN" else max(wpx)
    print(f"{name:7s} {level:9.2f} {e.kid:5d} {e.basis:8.3f} "
          f"{e.touch_anzahl:7d} {inn:15.3f} {inn - level:+8.3f}")
