# -*- coding: utf-8 -*-
"""PHASE 1.1/1.2 (read-only) -- Rollen-Resolver vs. Engine-Pool.

Fragestellung: Ist ``KantenRolle.AUSSEN_OBEN`` (= hoechste EXISTIERENDE
OBEN-Basis) identisch mit dem ``pos == 0``-Element des ``_kandidat``-Pools?

Der Pool filtert zusaetzlich (anker-promoviert ODER V-S >= 2, etabliert,
Seed-Durchstich) -- die Rollendefinition ueber ALLE existierenden Kanten
kann daher systematisch divergieren. Genau das wird hier gemessen.

Zusaetzlich: Skalierungsfaktor-Nachweis (Box-Range AUG).
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location(
    "_rr", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["_rr"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX = scan["box_end_bar"]
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
op = d["open"].to_numpy(float)
cl = d["close"].to_numpy(float)
alle = list(scan["edges"]) + list(scan["seeds"])
seite_edges = {"OBEN": [e for e in alle if e.seite == "OBEN"],
               "UNTEN": [e for e in alle if e.seite == "UNTEN"]}


def exists(e, k):
    if not e.ist_aktiv_bei(k):
        return False
    return e.erster_pivot_bar + 2 <= k + 1


def etabliert(e, k):
    return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars


def role_all_existing(k, seite):
    """Rolle ueber ALLE existierenden Kanten der Seite (Entwurfsannahme)."""
    c = [e for e in seite_edges[seite] if exists(e, k)]
    c.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
    return c


def pool_kandidat(k, seite, richtung):
    """1:1-Transkription des ``_kandidat``-Pools (Phase 1, kreuzvalidiert)."""
    sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])

    def _dist(e):
        b = e.basis_bei(k)
        if richtung == "SHORT":
            return (sweep_px - b) / b * 100.0
        return (b - sweep_px) / b * 100.0

    pool = []
    for e in seite_edges[seite]:
        if not exists(e, k):
            continue
        if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                or e.touch_conf(k) >= 2):
            continue
        if not etabliert(e, k):
            continue
        pool.append(e)
    for e in seite_edges[seite]:
        if e in pool or not exists(e, k) or e.ist_prim_anker:
            continue
        if e.touch_conf(k) >= 2 or not etabliert(e, k):
            continue
        dd = _dist(e)
        if cfg.sweep_mindestdurchstich_pct < dd <= cfg.max_sweep_ueberdehnung_pct:
            pool.append(e)
    pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
    return pool


print("=" * 100)
print("PHASE 1.1 -- AUSSEN_OBEN: existierende Menge vs. _kandidat-Pool")
print("=" * 100)
print(f"AUG n={n} box_end={BOX} | Fenster 848..1287")
print()

ref = {"OBEN": 67, "UNTEN": 82}
for seite, richtung in (("OBEN", "SHORT"), ("UNTEN", "LONG")):
    diffs = []
    keine_existing = keine_pool = 0
    for k in range(848, n):
        ex = role_all_existing(k, seite)
        po = pool_kandidat(k, seite, richtung)
        kid_ex = ex[0].kid if ex else None
        kid_po = po[0].kid if po else None
        if kid_ex is None:
            keine_existing += 1
        if kid_po is None:
            keine_pool += 1
        if kid_ex != kid_po:
            diffs.append((k, kid_ex, kid_po, min(len(ex), 3),
                          min(len(po), 3)))
    print(f"--- {seite} (Richtung {richtung}), Referenz-Kid = K{ref[seite]} ---")
    print(f"    Bars ohne existierende Kante : {keine_existing}")
    print(f"    Bars ohne Pool               : {keine_pool}")
    print(f"    Divergenzen AUSSEN_OBEN      : {len(diffs)} von {n - 848} Bars")
    if diffs:
        print(f"    erste 15: {[(k, f'K{a}', f'K{b}') for (k, a, b, _, _) in diffs[:15]]}")
        c = Counter((a, b) for (k, a, b, _, _) in diffs)
        print(f"    Top-Muster (existing -> pool): "
              f"{[((f'K{a}', f'K{b}'), c2) for ((a, b), c2) in c.most_common(8)]}")
    # Trefferquote der Rolle gegen die Referenz
    tref = sum(1 for k in range(848, n)
               if (role_all_existing(k, seite)[0].kid
                   if role_all_existing(k, seite) else None) == ref[seite])
    tpool = sum(1 for k in range(848, n)
                if (pool_kandidat(k, seite, richtung)[0].kid
                    if pool_kandidat(k, seite, richtung) else None) == ref[seite])
    print(f"    AUSSEN(existing) == K{ref[seite]}: {tref} / {n - 848} Bars")
    print(f"    POOL[0]          == K{ref[seite]}: {tpool} / {n - 848} Bars")
    print()

print("=" * 100)
print("PHASE 1.2a -- Skalierungsfaktor: Box-Range AUG")
print("=" * 100)
box_hi = float(np.max(hi[:BOX]))
box_lo = float(np.min(lo[:BOX]))
print(f"Box = bars [0, {BOX})")
print(f"   Box-Hoch        = {box_hi:.4f}")
print(f"   Box-Tief        = {box_lo:.4f}")
print(f"   Box-Range       = {box_hi - box_lo:.4f}")
print(f"   Fenster-Hoch    = {np.max(hi):.4f}  (ganzes AUG-Fenster)")
print(f"   Fenster-Tief    = {np.min(lo):.4f}")
print(f"   Fenster-Range   = {np.max(hi) - np.min(lo):.4f}")
print(f"   Von der Freigabe genutzte Nenner-Formel (70.0000 - 62.5480) "
      f"= {70.0 - 62.548:.4f}")
print(f"   -> {'IDENTISCH' if abs((70.0 - 62.548) - (box_hi - box_lo)) < 1e-9 else 'ABWEICHUNG'}"
      f" (Box-Range vs. Fenster-Range)")
print()

print("=" * 100)
print("PHASE 1.2b -- kausale Aussenkanten-Basen bei box_end (Bar 643)")
print("=" * 100)
k = BOX - 1
for seite in ("OBEN", "UNTEN"):
    ex = role_all_existing(k, seite)
    print(f"   {seite}: "
          f"{[(f'K{e.kid}', round(e.basis_bei(k), 4)) for e in ex[:3]]}")
print(f"   -> Range aus Kantenbasen (aussen O - aussen U) = "
      f"{(role_all_existing(k, 'OBEN')[0].basis_bei(k) - role_all_existing(k, 'UNTEN')[0].basis_bei(k)):.4f}")
