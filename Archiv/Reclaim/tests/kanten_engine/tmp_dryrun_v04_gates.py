# -*- coding: utf-8 -*-
"""READ-ONLY: Welches Gate blockiert die 5 H2-Zielkanten, wenn das Level
v0.4-konform ist? Isolierte Kaskaden-Spiegelung je Zielkante (kein Eingriff
in die Engine, kein Schreiben).

Geprueft werden die V3-Gates in Kaskadenreihenfolge:
  1. Reclaim-Signal (`_reclaim_stufe` > 0) am v0.4-Level
  2. M6 Innenlevel-Blocker (unerreichte Aussenwand <= 0.75 %)
  3. Q29 Ausseres Quartil (<= 25 % der kausalen Spanne)
  4. TP-Raum (Gegenkante > 1.5 % + POC zwischen den Kanten)
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


engine = load("ke_gates", P)
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
seite_edges = {"OBEN": [e for e in alle if e.seite == "OBEN"],
               "UNTEN": [e for e in alle if e.seite == "UNTEN"]}

V04: dict[int, float] = {}
for e in alle:
    if e.wicks:
        px = [p for _, p in e.wicks]
        typ = "H" if e.seite == "OBEN" else "L"
        lvl = level_schnittmenge(px, typ)
        if lvl is not None:
            V04[e.kid] = float(lvl)


def _existiert(e, k: int) -> bool:
    if not e.ist_aktiv_bei(k):
        return False
    return e.erster_pivot_bar + 2 <= k + 1


def _etabliert(e, k: int) -> bool:
    return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars


def _im_quartil(richtung: str, k: int, sweep_px: float) -> bool:
    ex_hi = float(np.max(hi[:k + 1]))
    ex_lo = float(np.min(lo[:k + 1]))
    spanne = ex_hi - ex_lo
    if spanne <= 0.0:
        return True
    dist = ((ex_hi - sweep_px) if richtung == "SHORT"
            else (sweep_px - ex_lo)) / spanne * 100.0
    return dist <= cfg.quartil_distanz_pct


def _aussenblocker(richtung: str, k: int, kd, sweep_px: float):
    seite = "OBEN" if richtung == "SHORT" else "UNTEN"
    basis_k = V04.get(kd.kid, kd.basis_bei(k))
    aussen = None
    for e in seite_edges[seite]:
        if e is kd or not _existiert(e, k):
            continue
        b = V04.get(e.kid, e.basis_bei(k))
        if seite == "OBEN":
            if b <= sweep_px:
                continue
            if aussen is None or b > V04.get(aussen.kid, aussen.basis_bei(k)):
                aussen = e
        else:
            if b >= sweep_px:
                continue
            if aussen is None or b < V04.get(aussen.kid, aussen.basis_bei(k)):
                aussen = e
    if aussen is None:
        return None
    b = V04.get(aussen.kid, aussen.basis_bei(k))
    dist = ((b - basis_k) if seite == "OBEN"
            else (basis_k - b)) / basis_k * 100.0
    return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None


ZIEL = {67: "Upper1 69.90", 73: "Upper2 69.62", 71: "Lower1 68.88",
        77: "Lower2 68.40", 82: "Lower3 67.60"}

print("=" * 128)
print("GATE-ANALYSE der 5 H2-ZIELKANTEN (Level = v0.4-Dichte-Cluster)")
print("=" * 128)
print(f"{'K':>4s} {'Ziel':14s} {'Richt':6s} {'Level':>9s} {'Pivot':>6s} "
      f"{'Sig':>5s} {'Blocker':>8s} {'Quartil':>8s} {'TP-Raum':>8s} "
      f"{'OFFEN':>6s}   erste Blockade (Bar / Detail)")
for kid in sorted(ZIEL):
    e = next((x for x in alle if x.kid == kid), None)
    if e is None:
        continue
    lvl = V04.get(kid, e.basis)
    richtung = "SHORT" if e.seite == "OBEN" else "LONG"
    k0 = max(2, e.erster_pivot_bar + 2)
    sig = blk = qua = tpr = offen = 0
    erste = "-"
    for k in range(k0, n):
        sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
        st, name = engine._reclaim_stufe(e.seite, k, lvl, hi, lo, cl, cfg)
        if not st:
            continue
        sig += 1
        b = _aussenblocker(richtung, k, e, sweep_px)
        if b is not None:
            blk += 1
            if erste == "-":
                erste = (f"bar {k} {ts.iloc[k].strftime('%d.%m. %H:%M')} "
                         f"BLOCKER K{b.kid} "
                         f"{V04.get(b.kid, b.basis_bei(k)):.3f}")
            continue
        if not _im_quartil(richtung, k, sweep_px):
            qua += 1
            if erste == "-":
                ex_hi = float(np.max(hi[:k + 1]))
                ex_lo = float(np.min(lo[:k + 1]))
                sp = ex_hi - ex_lo
                dq = ((ex_hi - sweep_px) if richtung == "SHORT"
                      else (sweep_px - ex_lo)) / sp * 100.0
                erste = (f"bar {k} {ts.iloc[k].strftime('%d.%m. %H:%M')} "
                         f"QUARTIL {dq:.1f}% > {cfg.quartil_distanz_pct:.0f}%")
            continue
        # TP-Raum: naechste Gegenkante mit >= 2 Touches
        geg = None
        gs = "OBEN" if richtung == "LONG" else "UNTEN"
        for x in seite_edges[gs]:
            if x.erster_pivot_bar + 2 > k + 1:
                continue
            if x.touch_conf(k) < 2 and not x.ist_prim_anker:
                continue
            bx = V04.get(x.kid, x.basis_bei(k))
            if richtung == "LONG" and bx > lvl:
                if geg is None or bx < V04.get(geg.kid, geg.basis_bei(k)):
                    geg = x
            if richtung == "SHORT" and bx < lvl:
                if geg is None or bx > V04.get(geg.kid, geg.basis_bei(k)):
                    geg = x
        raum_ok = (geg is not None and
                   abs(V04.get(geg.kid, geg.basis_bei(k)) - lvl) / lvl
                   * 100.0 >= engine.V3_TP_MINDIST_PCT)
        if not raum_ok:
            tpr += 1
            if erste == "-":
                erste = (f"bar {k} {ts.iloc[k].strftime('%d.%m. %H:%M')} "
                         f"TP-RAUM fehlt")
            continue
        offen += 1
    print(f"{kid:4d} {ZIEL[kid]:14s} {richtung:6s} {lvl:9.4f} "
          f"{e.erster_pivot_bar:6d} {sig:5d} {blk:8d} {qua:8d} {tpr:8d} "
          f"{offen:6d}   {erste}")

print("\n" + "=" * 128)
print("LESART: 'OFFEN' > 0 bedeutet: bei v0.4-Level wuerde die Kante die "
      "V3-Gates passieren.")
print("=" * 128)
