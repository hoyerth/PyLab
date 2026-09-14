# -*- coding: utf-8 -*-
"""READ-ONLY: Diagnose H2-Zielvorgabe -- Zeitbezug (Berlin vs. UTC-Projektion)
und Touch-Sets gegen die Engine-Kanten (`_p11`), Fenster AUG.

Der Anwender nennt Touch-Zeiten und Ziel-Level. Diese Diagnose prueft:
  A) Sind die Ziel-Zeiten Berlin-Wanduhr oder UTC-Projektion (-2 h)?
  B) Welche Engine-Kante traegt welches Ziel-Level?
  C) Wo liegen die Docht-Extrema (These: Extremum != erster Touch)?

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


engine = load("ke_h2diag", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
ts = d["ts"]
idx_von_zeit = {ts.iloc[i].strftime("%d.%m. %H:%M"): i for i in range(n)}

# Alle Dochte aller lebenden Kanten (edges + seeds)
dochte = []
for e in list(scan["edges"]) + list(scan["seeds"]):
    for b, px in e.wicks:
        dochte.append((b, px, e.kid, e.seite, e.basis))
dochte.sort()


def naechster_docht(b: int, seite: str, tol: int = 24):
    k = [x for x in dochte if x[3] == seite and abs(x[0] - b) <= tol]
    if not k:
        return None
    return min(k, key=lambda x: abs(x[0] - b))


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

print("=" * 126)
print("A) ZEITBEZUG: Ziel-Zeit als BERLIN vs. als UTC-Projektion (+2 h = +8 Bars)")
print("=" * 126)
print(f"{'Kante':7s} {'Ziel-Zeit':16s} | {'BAR-BERLIN':>10s} {'Docht':>7s} "
      f"{'n.Kante':>8s} {'dB':>4s} | {'BAR+2h':>7s} {'Docht':>7s} "
      f"{'n.Kante':>8s} {'dB':>4s}")
off_berlin, off_utc = [], []
for name, seite, level, zeiten in ZIEL:
    for z in zeiten:
        b = idx_von_zeit.get(z)
        if b is None:
            print(f"{name:7s} {z:16s} |  nicht vorhanden")
            continue
        b2 = b + 8
        px = hi[b] if seite == "OBEN" else lo[b]
        px2 = hi[b2] if seite == "OBEN" else lo[b2]
        nb = naechster_docht(b, seite)
        nb2 = naechster_docht(b2, seite)
        sb = f"K{nb[2]:<3d}" if nb else "-"
        db = nb[0] - b if nb else 99
        s2 = f"K{nb2[2]:<3d}" if nb2 else "-"
        d2 = nb2[0] - b2 if nb2 else 99
        if nb:
            off_berlin.append(abs(db))
        if nb2:
            off_utc.append(abs(d2))
        print(f"{name:7s} {z:16s} | {b:10d} {px:7.3f} {sb:>8s} {db:4d} | "
              f"{b2:7d} {px2:7.3f} {s2:>8s} {d2:4d}")
    print("-" * 126)

print(f"\n  Mittlere |dB| wenn Ziel-Zeit = BERLIN          : "
      f"{sum(off_berlin)/len(off_berlin):.2f} Bars")
print(f"  Mittlere |dB| wenn Ziel-Zeit = UTC-Projektion  : "
      f"{sum(off_utc)/len(off_utc):.2f} Bars")

print("\n" + "=" * 126)
print("B) ZIEL-LEVEL vs. ENGINE-KANTE (naechste Kante je Seite)")
print("=" * 126)
alle = list(scan["edges"]) + list(scan["seeds"])
print(f"{'Ziel':7s} {'Level':>7s} {'Seite':6s} | {'Kante':>5s} {'basis':>8s} "
      f"{'Delta':>7s} {'Touches':>7s} {'geb-Bar':>7s} {'geb-Zeit':>13s}")
for name, seite, level, _z in ZIEL:
    kand = [e for e in alle if e.seite == seite]
    best = min(kand, key=lambda e: abs(e.basis - level))
    print(f"{name:7s} {level:7.2f} {seite:6s} | {best.kid:5d} "
          f"{best.basis:8.3f} {best.basis - level:+7.3f} "
          f"{best.touch_anzahl:7d} {best.geburts_bar:7d} "
          f"{ts.iloc[best.geburts_bar].strftime('%d.%m. %H:%M'):>13s}")

print("\n" + "=" * 126)
print("C) DOCHT-EXTREMA der 5 Ziel-Kanten (These: Extremum != erster Touch)")
print("=" * 126)
ziel_kids = {}
for name, seite, level, _z in ZIEL:
    kand = [e for e in alle if e.seite == seite]
    ziel_kids[name] = min(kand, key=lambda e: abs(e.basis - level))
for name, seite, level, _z in ZIEL:
    e = ziel_kids[name]
    ws = sorted(e.wicks)
    print(f"\n{name}  Ziel {level:.2f} | Engine K{e.kid} basis={e.basis:.3f} "
          f"({e.seite}) | Touches {len(ws)}")
    for i, (b, px) in enumerate(ws):
        marker = ""
        if seite == "OBEN" and px == max(p for _, p in ws):
            marker = "  <== HOECHSTER"
        if seite == "UNTEN" and px == min(p for _, p in ws):
            marker = "  <== NIEDRIGSTER"
        if i == 0:
            marker += "  (erster Touch)"
        print(f"    {i+1:2d}. bar {b:4d} {ts.iloc[b].strftime('%d.%m. %H:%M')} "
              f"px={px:8.3f}{marker}")
