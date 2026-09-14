# -*- coding: utf-8 -*-
"""READ-ONLY: Warum ist K82 (und die Nachbarschaft) an Bar 1172/1259 nich
AKTIV? Ausgabe der schlaf_windows je Linie + dist_ueberdehnung-Kontrolle.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
mod = types.ModuleType("explo_diag2")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old_argv = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_diag2>", "exec"), ns)
sys.argv = _old_argv

engine = sys.modules["ke_pngset"]
cfg = ns["cfg"]
scan = ns["scan"]
n = ns["n"]
edges = list(scan["edges"]) + list(scan["seeds"])
BY = {e.kid: e for e in edges}

import pandas as pd  # noqa: E402

ts = pd.to_datetime(scan["d"]["ts"])
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)

print("=" * 110)
print("SCHLAF-WINDOW-DIAGNOSE | Kandidaten an Bar 1172 (LONG) und 1259 (LONG)")
print("=" * 110)
print(f"cfg: max_sweep_ueberdehnung_pct={cfg.max_sweep_ueberdehnung_pct} | "
      f"touch_band_pct={cfg.touch_band_pct} | "
      f"sweep_mindestdurchstich_pct={cfg.sweep_mindestdurchstich_pct} | "
      f"min_touches_handelbar={cfg.min_touches_handelbar} | "
      f"wall_live_bars={cfg.wall_live_bars} | "
      f"min_wall_alter_bars={cfg.min_wall_alter_bars} | "
      f"quartil_distanz_pct={cfg.quartil_distanz_pct}")

for k in (1172, 1259):
    print("\n" + "-" * 110)
    print(f"BAR {k}  {ts.iloc[k]:%d.%m.%Y %H:%M}  H {hi[k]:.4f} L {lo[k]:.4f}  "
          f"| range(0..{k}) lo={lo[:k + 1].min():.4f} "
          f"hi={hi[:k + 1].max():.4f}")
    sp = float(lo[k])
    q29 = (sp - lo[:k + 1].min()) / (hi[:k + 1].max() - lo[:k + 1].min()) * 100
    print(f"   Q29-Distanz% = {q29:.4f} (Grenze {cfg.quartil_distanz_pct}) "
          f"-> {'OK' if q29 <= cfg.quartil_distanz_pct else 'GESPERRT'}")
    print(f"   {'KID':>5} {'seite':<6} {'basis_bei':>10} {'dist%':>9} "
          f"{'exist':>6} {'touch':>6} {'aktiv':>6} {'lebt':>6} {'etab':>6} "
          f"{'anker':>6}  schlaf_windows")
    for e in sorted(edges, key=lambda x: x.kid):
        if e.seite != "UNTEN":
            continue
        b = e.basis_bei(k)
        d = (b - sp) / b * 100.0
        if not (abs(d) < 3.0 or (e.wicks and e.wicks[-1][0] >= k - 200)):
            continue
        print(f"   {e.kid:>5} {e.seite:<6} {b:>10.4f} {d:>9.4f} "
              f"{engine._se_trades.__name__ and '':>0}"
              f"{str(e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1):>6} "
              f"{e.touch_conf(k):>6} {str(e.ist_aktiv_bei(k)):>6} "
              f"{'':>6} {'':>6} {str(e.ist_prim_anker):>6}  "
              f"{e.schlaf_windows}")

print("\n" + "=" * 110)
print("FOKUS K82 / K60 / K62 / K85 -- vollstaendige Historie")
print("=" * 110)
for kid in (60, 62, 82, 85):
    e = BY[kid]
    print(f"\nK{kid} {e.seite} | geburt={e.geburts_bar} | erster_pivot={e.erster_pivot_bar}"
          f" | ist_prim_anker={e.ist_prim_anker}")
    print(f"   wicks        : {[(b, round(p, 4)) for b, p in e.wicks]}")
    print(f"   schlaf_windows: {e.schlaf_windows}")
    for k in (1056, 1075, 1122, 1160, 1172, 1211, 1259, 1272, 1287):
        print(f"   k={k:<5} exist={str(e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1):<5}"
              f" aktiv={str(e.ist_aktiv_bei(k)):<5} touch={e.touch_conf(k)}"
              f" basis={e.basis_bei(k):.4f}")

print("\n" + "=" * 110)
print("SCHLAF-WINDOWS ALLER LINIEN, die 1172 oder 1259 abdecken")
print("=" * 110)
for e in sorted(edges, key=lambda x: x.kid):
    hit = [(s, t) for (s, t) in e.schlaf_windows
           if (t is None or t > 1172) and s <= 1172]
    hit2 = [(s, t) for (s, t) in e.schlaf_windows
            if (t is None or t > 1259) and s <= 1259]
    if hit or hit2:
        print(f"   K{e.kid:<4} {e.seite:<6} 1172:{hit}  1259:{hit2}  "
              f"alle={e.schlaf_windows}")
print("=" * 110)
