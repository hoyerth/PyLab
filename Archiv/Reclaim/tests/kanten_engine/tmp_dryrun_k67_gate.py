# -*- coding: utf-8 -*-
"""READ-ONLY: Warum handelt K67 (Upper1) trotz 2 offener Reclaim-Signale
nicht? Prueft `_etabliert` (min_wall_alter_bars) und die Kandidatenwahl."""
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


def level_schnittmenge(prices, typ, density_band=0.15, min_cluster=2,
                       erweiterung_pct=1.0):
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


engine = load("ke_k67", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
ts = scan["d"]["ts"]
scan["box_end_bar"] = n
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
cl = scan["d"]["close"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])
oben = [e for e in alle if e.seite == "OBEN"]

V04: dict[int, float] = {}
for e in alle:
    if e.wicks:
        px = [p for _, p in e.wicks]
        V04[e.kid] = float(level_schnittmenge(
            px, "H" if e.seite == "OBEN" else "L"))

for kid in (67, 73):
    e = next(x for x in alle if x.kid == kid)
    lvl = V04[kid]
    print("=" * 120)
    print(f"K{kid} {e.seite} | V3-Mittel={e.basis:.4f} | v0.4={lvl:.4f} | "
          f"pivot={e.erster_pivot_bar} ({ts.iloc[e.erster_pivot_bar].strftime('%d.%m. %H:%M')}) "
          f"| etabliert ab Bar {e.erster_pivot_bar + cfg.min_wall_alter_bars} "
          f"| aktiv={e.ist_aktiv_bei(n - 1)} | anker={e.ist_prim_anker}")
    print(f"  Dochte: {[(b, round(p, 3)) for b, p in e.wicks]}")
    print(f"  Schlaf-Fenster: {e.schlaf_windows}")
    for k in range(max(2, e.erster_pivot_bar + 2), n):
        st, name = engine._reclaim_stufe(e.seite, k, lvl, hi, lo, cl, cfg)
        if not st:
            continue
        etab = k - e.erster_pivot_bar >= cfg.min_wall_alter_bars
        # ist K67/K73 im _kandidat-Pool? aeusserste Linie derselben Seite
        pool = []
        for x in oben:
            if not x.ist_aktiv_bei(k):
                continue
            if x.erster_pivot_bar + 2 > k + 1:
                continue
            if not ((x.ist_prim_anker and k >= x.promoviert_ab_bar)
                    or x.touch_conf(k) >= 2):
                continue
            pool.append(x)
        pool.sort(key=lambda x: V04.get(x.kid, x.basis_bei(k)), reverse=True)
        pos = next((i for i, x in enumerate(pool) if x.kid == kid), -1)
        top = pool[0] if pool else None
        top_s = (f"K{top.kid} ({V04.get(top.kid, 0):.4f} "
                 f"V3={top.basis_bei(k):.4f})") if top is not None else "-"
        print(f"  bar {k:4d} {ts.iloc[k].strftime('%d.%m. %H:%M')} "
              f"stufe={st} {name:16s} etabliert={etab} "
              f"poolpos={pos}/{len(pool)} top={top_s}")
