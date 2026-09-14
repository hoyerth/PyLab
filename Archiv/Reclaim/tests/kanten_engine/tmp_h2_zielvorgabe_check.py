# -*- coding: utf-8 -*-
"""READ-ONLY: H2-Zielvorgabe (Anwender) vs. Engine-Kanten (`_p11`), Fenster AUG.

Zielvorgabe H2 (Berlin-Wanduhr):
  Upper1 : 21.8. 10:30, 13:15, 18:45 - 24.8. 15:00, 25.8. 2:00  -> 69.9
  Upper2 : 26.8. 4:30, 27.8. 3:45, 19:00                          -> 69.62
  Lower1 : 21.8. 16:30                                            -> 68.88
  Lower2 : 24.8. 3:30, 17:45, 20:00 (mehrfach)                    -> 68.4
  Lower3 : 25.8. 4:45, 11:00, 15:00, 26.8. 17:00, 27.8. 15:45     -> 67.6

Kernthese des Anwenders: der Extrempunkt ist NICHT immer der erste Touch.

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


engine = load("ke_h2ziel", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
ts = d["ts"]

# Zeit-Index: "DD.MM. HH:MM" -> Bar
idx_von_zeit = {ts.iloc[i].strftime("%d.%m. %H:%M"): i for i in range(n)}

ZIEL = [
    ("Upper1", "OBEN", 69.90,
     ["21.08. 10:30", "21.08. 13:15", "21.08. 18:45",
      "24.08. 15:00", "25.08. 02:00"]),
    ("Upper2", "OBEN", 69.62,
     ["26.08. 04:30", "27.08. 03:45", "27.08. 19:00"]),
    ("Lower1", "UNTEN", 68.88,
     ["21.08. 16:30"]),
    ("Lower2", "UNTEN", 68.40,
     ["24.08. 03:30", "24.08. 17:45", "24.08. 20:00"]),
    ("Lower3", "UNTEN", 67.60,
     ["25.08. 04:45", "25.08. 11:00", "25.08. 15:00",
      "26.08. 17:00", "27.08. 15:45"]),
]

print("=" * 118)
print(f"H2-ZIELVORGABE vs. DB | AUG | n={n} | box_end_bar={box_end} "
      f"(H2 = bars >= {box_end})")
print("=" * 118)

print("\n--- 1. Ziel-Touchpunkte: Rohdaten und Pivot-Status ---")
print(f"{'Kante':7s} {'Zeit (Berlin)':16s} {'bar':>5s} {'H2':>3s} "
      f"{'open':>8s} {'high':>8s} {'low':>8s} {'close':>8s} "
      f"{'pivot':>6s} {'Docht':>8s}")
for name, seite, level, zeiten in ZIEL:
    for z in zeiten:
        b = idx_von_zeit.get(z)
        if b is None:
            print(f"{name:7s} {z:16s} {'--':>5s}  NICHT VORHANDEN")
            continue
        pt = engine._pivot_typ(hi, lo, b) if 2 <= b <= n - 3 else None
        docht = hi[b] if seite == "OBEN" else lo[b]
        print(f"{name:7s} {z:16s} {b:5d} {'ja' if b >= box_end else 'nein':>3s} "
              f"{op[b]:8.3f} {hi[b]:8.3f} {lo[b]:8.3f} {cl[b]:8.3f} "
              f"{str(pt):>6s} {docht:8.3f}")
    # Extremum der Ziel-Touchs
    bs = [idx_von_zeit[z] for z in zeiten if z in idx_von_zeit]
    if bs:
        if seite == "OBEN":
            ex_b = max(bs, key=lambda i: hi[i])
            ex_v = hi[ex_b]
        else:
            ex_b = min(bs, key=lambda i: lo[i])
            ex_v = lo[ex_b]
        print(f"{'':7s} -> Ziel-Level {level:.2f} | Extremum der Touches: "
              f"{ex_v:.3f} @ bar {ex_b} ({ts.iloc[ex_b].strftime('%d.%m. %H:%M')})"
              f" | Abweichung {ex_v - level:+.3f}")

print("\n" + "-" * 118)
print("--- 2. Engine-Kanten im H2-Bereich (bars >= box_end) ---")
print("-" * 118)
print(f"{'K':>4s} {'Seite':6s} {'basis':>8s} {'geb':>5s} {'erstePiv':>9s} "
      f"{'Touches':>7s} {'conf':>5s} {'Prim':>5s}  {'Wick-Zeiten (H2)':s}")
h2_edges = []
for e in sorted(scan["edges"], key=lambda x: (x.seite, -x.basis)):
    wicks_h2 = [(b, p) for b, p in e.wicks if b >= box_end]
    if not wicks_h2:
        continue
    h2_edges.append(e)
    zt = ", ".join(f"{b}({ts.iloc[b].strftime('%d.%m %H:%M')})"
                   for b, _ in wicks_h2)
    print(f"{e.kid:4d} {e.seite:6s} {e.basis:8.3f} {e.geburts_bar:5d} "
          f"{e.erster_pivot_bar:9d} {e.touch_anzahl:7d} "
          f"{e.touch_conf(n - 1):5d} {str(e.ist_prim_anker):>5s}  {zt}")

print("\n" + "-" * 118)
print("--- 3. Seeds im H2-Bereich (offen, < 2 Touches) ---")
print("-" * 118)
for e in scan["seeds"]:
    wicks_h2 = [(b, p) for b, p in e.wicks if b >= box_end]
    if not wicks_h2:
        continue
    zt = ", ".join(f"{b}({ts.iloc[b].strftime('%d.%m %H:%M')})"
                   for b, _ in wicks_h2)
    print(f"{e.kid:4d} {e.seite:6s} {e.basis:8.3f} {e.geburts_bar:5d}  {zt}")

print("\n" + "-" * 118)
print("--- 4. Abgleich Ziel-Level vs. naechstgelegene Engine-Kante ---")
print("-" * 118)
alle = list(scan["edges"]) + list(scan["seeds"])
for name, seite, level, _z in ZIEL:
    kand = [e for e in alle if e.seite == seite]
    if not kand:
        continue
    best = min(kand, key=lambda e: abs(e.basis - level))
    delta = best.basis - level
    print(f"{name:7s} Ziel {level:7.2f} | naechste K{e.kid:<3d} "
          f"basis={best.basis:8.3f} ({delta:+7.3f}) | "
          f"geb={best.geburts_bar:4d} "
          f"({ts.iloc[best.geburts_bar].strftime('%d.%m %H:%M')}) | "
          f"Touches={best.touch_anzahl} | Typ-B={best.touch_anzahl >= 3}")
