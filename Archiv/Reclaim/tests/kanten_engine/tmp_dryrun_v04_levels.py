# -*- coding: utf-8 -*-
"""READ-ONLY TROCKENUEBUNG (Mentor-Frage 3): v0.4-Level gegen V3-Sweep-/
Reclaim-Bedingungen spiegeln, OHNE die Engine zu aendern.

Vorgehen (kein Schreiben, kein Patch am Engine-File):
  1. V3-Scan laeuft unveraendert (`_se_scan`), Discovery bleibt V3.
  2. Fuer jede Kante wird das v0.4-Dichte-Cluster (`_level_schnittmenge`)
     auf ihren akzeptierten Dochten berechnet und als STATISCHER Fix-Level
     an die Instanz gehaengt.
  3. Lauf A: `basis_bei` = V3-Mittel (Referenz, 14 Trades).
     Lauf B: `basis_bei` = v0.4-Fix-Level (nur Trade-Phase gepatcht).
  4. Zusaetzlich je Zielkante: isolierte Reclaim-Signalzaehlung auf beiden
     Leveln ueber die gesamte Lebenszeit und ueber P9-P12 (bars 848-1288).

Grenzen (bewusst): KEINE Phasen-Segmentierung, KEIN Geburts-Anker,
KEIN Ratchet/basis_hist. Nur der Leveling-Baustein allein.
"""
from __future__ import annotations

import copy
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


def level_schnittmenge(prices, typ: str, density_band: float = 0.15,
                       min_cluster: int = 2, erweiterung_pct: float = 1.0):
    """1:1-Port von scripts/market_segmentation._level_schnittmenge."""
    arr = np.array(prices, dtype=float)
    if not len(arr):
        return None
    d = np.array([np.sum(np.abs(arr - x) <= density_band) for x in arr])
    m = d >= min_cluster
    if not m.any():
        return float(np.max(arr)) if typ == "H" else float(np.min(arr))
    sel = arr[m]
    ext = float(np.max(sel)) if typ == "H" else float(np.min(sel))
    kern = sel[np.abs(sel - ext) <= density_band]
    if not len(kern):
        kern = sel
    if typ == "H":
        kante = float(np.min(kern))
        pool = sel[sel >= kante - density_band]
        pool = pool[pool <= kante * (1 + erweiterung_pct / 100.0)]
    else:
        kante = float(np.max(kern))
        pool = sel[sel <= kante + density_band]
        pool = pool[pool >= kante * (1 - erweiterung_pct / 100.0)]
    if not len(pool):
        pool = kern
    if len(pool) > 1:
        pool = pool[pool != (np.max(pool) if typ == "H" else np.min(pool))]
    return float(np.mean(pool)) if len(pool) else float(np.mean(kern))


engine = load("ke_dry", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
ts = scan["d"]["ts"]
scan["box_end_bar"] = n

hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
cl = scan["d"]["close"].to_numpy(dtype=float)

alle = list(scan["edges"]) + list(scan["seeds"])
# `_SEEdgeH` ist @dataclass(slots=True) -> keine dynamischen Attribute.
# Fix-Level daher in einer Seitentabelle je kid (kids sind eindeutig).
V04: dict[int, float] = {}
for e in alle:
    if e.wicks:
        px = [p for _, p in e.wicks]
        typ = "H" if e.seite == "OBEN" else "L"
        lvl = level_schnittmenge(px, typ)
        if lvl is not None:
            V04[e.kid] = float(lvl)

ORIG = engine._SEEdgeH.basis_bei


def _patched(self, k: int) -> float:
    v = V04.get(self.kid)
    return float(v) if v is not None else ORIG(self, k)


def run(use_v04: bool):
    sc = copy.deepcopy(scan)
    engine._SEEdgeH.basis_bei = _patched if use_v04 else ORIG
    try:
        setups, stats = engine._se_trades(sc, cfg)
    finally:
        engine._SEEdgeH.basis_bei = ORIG
    return setups, stats


ZIEL = {67: "Upper1 69.90", 73: "Upper2 69.62", 71: "Lower1 68.88",
        77: "Lower2 68.40", 82: "Lower3 67.60"}

print("=" * 128)
print("TROCKENUEBUNG: V3-Discovery konstant, NUR Leveling getauscht "
      "(v0.4-Dichte-Cluster, DENSITY_BAND=0.15)")
print("=" * 128)

ref, sref = run(False)
v04, sv04 = run(True)

print(f"\nLauf A (V3-Mittel, Referenz) : {len(ref):2d} Trades | "
      f"R-Summe = {sum(t.r for t in ref):+9.4f}")
print(f"Lauf B (v0.4-Level)          : {len(v04):2d} Trades | "
      f"R-Summe = {sum(t.r for t in v04):+9.4f}")
print(f"Delta                        : {len(v04) - len(ref):+2d} Trades | "
      f"{sum(t.r for t in v04) - sum(t.r for t in ref):+9.4f} R")

print("\n" + "-" * 128)
print("TARGET-KANTEN (5 H2-Ziele): Level und Trades in beiden Laeufen")
print("-" * 128)
print(f"{'K':>4s} {'Ziel':14s} {'Seite':6s} {'V3-Mittel':>10s} "
      f"{'v0.4':>10s} {'Delta':>9s} {'TrA':>4s} {'TrB':>4s}  Reclaim-Signale "
      f"(v0.4-Level, ganz / P9-P12)")
for kid in sorted(ZIEL):
    e = next((x for x in alle if x.kid == kid), None)
    if e is None:
        print(f"{kid:4d} {ZIEL[kid]:14s} NICHT GEFUNDEN")
        continue
    lvl = V04.get(kid, e.basis)
    seite = e.seite
    tr_a = [t for t in ref if t.kid == kid]
    tr_b = [t for t in v04 if t.kid == kid]
    # isolierte Reclaim-Signalzaehlung
    k0 = max(2, e.erster_pivot_bar + 2)
    sig_all, sig_p9 = 0, 0
    for k in range(k0, n):
        st, _ = engine._reclaim_stufe(seite, k, lvl, hi, lo, cl, cfg)
        if st:
            sig_all += 1
            if k >= 848:
                sig_p9 += 1
    print(f"{kid:4d} {ZIEL[kid]:14s} {seite:6s} {e.basis:10.4f} "
          f"{lvl:10.4f} {lvl - e.basis:+9.4f} {len(tr_a):4d} {len(tr_b):4d}  "
          f"{sig_all:4d} / {sig_p9:4d}   (pivot={e.erster_pivot_bar}, "
          f"touches={e.touch_anzahl})")

print("\n" + "-" * 128)
print("TRADE-DIFF A -> B (kind-basiert)")
print("-" * 128)
ka = {(t.kid, t.bar) for t in ref}
kb = {(t.kid, t.bar) for t in v04}
neu = sorted(kb - ka)
weg = sorted(ka - kb)
print(f"  neu  ({len(neu):2d}): "
      + (", ".join(f"K{k}@bar{b}" for k, b in neu) if neu else "-"))
print(f"  weg  ({len(weg):2d}): "
      + (", ".join(f"K{k}@bar{b}" for k, b in weg) if weg else "-"))

print("\n" + "-" * 128)
print("STATS-DIFF (Blockade-Gruende, nur Aenderungen)")
print("-" * 128)
keys = sorted(set(sref) & set(sv04))
for key in keys:
    if isinstance(sref[key], int) and sref[key] != sv04[key]:
        print(f"  {key:22s} A={sref[key]:6d}  B={sv04[key]:6d}  "
              f"delta={sv04[key] - sref[key]:+6d}")

print("\n" + "-" * 128)
print("LAUF B TRADE-LISTE (v0.4-Level)")
print("-" * 128)
print(f"{'bar':>5s} {'Zeit':14s} {'Richt':6s} {'kid':>4s} {'basis':>8s} "
      f"{'R':>8s}  Ziel")
for t in v04:
    print(f"{t.bar:5d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):14s} "
          f"{t.richtung:6s} {t.kid:4d} {t.basis:8.3f} {t.r:+8.2f}  "
          f"{ZIEL.get(t.kid, '')}")
