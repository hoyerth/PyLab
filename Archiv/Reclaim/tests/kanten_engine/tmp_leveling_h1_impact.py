# -*- coding: utf-8 -*-
"""READ-ONLY: Rueckwirkung eines systemweiten Levelings (v0.4-_level_schnittmenge)
auf die V3-Kanten (`_p11`), getrennt nach H1 (Box) und H2.

Vergleicht je V3-Kante:
  - V3 `basis`      = einfaches Mittel der akzeptierten Dochte
  - v0.4-Level      = Dichte-Cluster (_level_schnittmenge) auf denselben Dochten

Wichtig: V3 akzeptiert Dochte ueber touch_band_pct (relativ, 0.12%),
v0.4 nutzt DENSITY_BAND (absolut, 0.15). Beide werden ausgewiesen.

Kein Schreiben, keine Engine-Aenderung.
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


engine = load("ke_lvl", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
ts = scan["d"]["ts"]

scan["box_end_bar"] = n
setups, _stats = engine._se_trades(scan, cfg)
getradete = {t.kid for t in setups}

alle = list(scan["edges"]) + list(scan["seeds"])
ZIEL = {67: "Upper1 69.90", 73: "Upper2 69.62", 71: "Lower1 68.88",
        77: "Lower2 68.40", 82: "Lower3 67.60"}

print("=" * 132)
print("LEVELING-RUECKWIRKUNG: V3-Mittel vs. v0.4-Dichte-Cluster (DENSITY_BAND=0.15)")
print(f"touch_band_pct={cfg.touch_band_pct}% -> absolutes Band bei ~68 USD "
      f"= {68 * cfg.touch_band_pct / 100:.4f} USD")
print("=" * 132)
print(f"{'K':>4s} {'Seite':6s} {'nW':>3s} {'V3-Mittel':>10s} "
      f"{'v0.4-Level':>11s} {'Delta':>8s} {'Delta%':>8s} "
      f"{'H1/H2':>6s} {'gehandelt':>10s} {'Ziel':>14s}")
maxd_h1, maxd_h2 = 0.0, 0.0
n_h1, n_h2 = 0, 0
for e in sorted(alle, key=lambda x: (x.seite, x.basis)):
    ws = e.wicks
    if not ws:
        continue
    px = [p for _, p in ws]
    typ = "H" if e.seite == "OBEN" else "L"
    v04 = level_schnittmenge(px, typ)
    if v04 is None:
        continue
    d = v04 - e.basis
    dp = 100.0 * d / e.basis
    in_box = any(b <= box_end - 1 for b, _ in ws)
    h2only = not in_box
    if in_box:
        n_h1 += 1
        maxd_h1 = max(maxd_h1, abs(d))
    else:
        n_h2 += 1
        maxd_h2 = max(maxd_h2, abs(d))
    print(f"{e.kid:4d} {e.seite:6s} {len(px):3d} {e.basis:10.4f} "
          f"{v04:11.4f} {d:+8.4f} {dp:+8.3f} "
          f"{'H1' if in_box else 'H2':>6s} "
          f"{'ja' if e.kid in getradete else '-':>10s} "
          f"{ZIEL.get(e.kid, ''):>14s}")

print("\n" + "=" * 132)
print("ZUSAMMENFASSUNG")
print("=" * 132)
print(f"  Kanten mit H1-Bezug : {n_h1:3d} | max |Delta| = {maxd_h1:.4f} USD")
print(f"  Kanten H2-only      : {n_h2:3d} | max |Delta| = {maxd_h2:.4f} USD")
print(f"  V3-Band bei 68 USD  : {68 * cfg.touch_band_pct / 100:.4f} USD "
      f"(touch_band_pct={cfg.touch_band_pct}%)")
print(f"  v0.4-DENSITY_BAND   : 0.1500 USD (absolut)")

print("\n" + "=" * 132)
print("GEHANDELTE KANTEN (14 Trades) -- wie stark verschiebt das Leveling?")
print("=" * 132)
print(f"{'K':>4s} {'Seite':6s} {'V3-Mittel':>10s} {'v0.4':>10s} {'Delta':>9s} "
      f"{'R-Summe':>9s}  {'Kante(n)':s}")
per_kid = {}
for t in setups:
    per_kid.setdefault(t.kid, []).append(t)
for kid in sorted(per_kid):
    e = next((x for x in alle if x.kid == kid), None)
    if e is None or not e.wicks:
        continue
    px = [p for _, p in e.wicks]
    typ = "H" if e.seite == "OBEN" else "L"
    v04 = level_schnittmenge(px, typ)
    rs = sum(t.r for t in per_kid[kid])
    print(f"{kid:4d} {e.seite:6s} {e.basis:10.4f} {v04:10.4f} "
          f"{v04 - e.basis:+9.4f} {rs:+9.2f}  {len(per_kid[kid])}")
