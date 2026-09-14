# -*- coding: utf-8 -*-
"""E-34n/3b — Wurde der Sweep unter K82 (Bar 1072..1078) als sweep_sperre
erkannt, aber als Touch verworfen? Read-only."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


eng = load("ke_e34n3b", ROOT / "test" / "tmp_kanten_engine_replay.py")
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
ts = scan["d"]["ts"]
print("=" * 112)
print("E-34n/3b  SWEEP-SPERREN im Fenster 1040..1120")
print("=" * 112)
print(f"{'bar':>5} {'BKZ':>12} {'seite':>6} {'preis':>9} {'ref':>9} {'dist%':>7}")
for (b, seite, px, ref, dist) in scan["sweep_sperren"]:
    if 1040 <= b <= 1120:
        print(f"{b:>5} {ts.iloc[b].strftime('%d.%m. %H:%M'):>12} "
              f"{seite:>6} {px:>9.4f} {ref:>9.4f} {dist:>7.3f}")

print("\n" + "=" * 112)
print("R21-LOG / TOMBSTEINE im Fenster (falls Modul-State vorhanden)")
print("=" * 112)
for _nm in ("R21_LOG", "WAR_AUSSEN_IDS"):
    _v = getattr(eng, _nm, None)
    if _v is None:
        print(f"  {_nm}: nicht vorhanden")
        continue
    print(f"  {_nm}: {len(_v)} Eintraege gesamt")
    for _z in list(_v)[:40]:
        if isinstance(_z, tuple) and _z and isinstance(_z[0], int) \
                and 1040 <= _z[0] <= 1120:
            print(f"    {_z}")

print("\n" + "=" * 112)
print("K82/K62/K85: Promotions-/Statuszustand")
print("=" * 112)
for e in sorted(list(scan["edges"]) + list(scan["seeds"]),
                key=lambda x: int(x.kid)):
    if int(e.kid) in (62, 82, 85):
        print(f"  K{int(e.kid)} seite={e.seite} basis={float(e.basis):.4f} "
              f"erster_pivot={int(e.erster_pivot_bar)} "
              f"geburts={int(getattr(e, 'geburts_bar', -1))} "
              f"anker={bool(e.ist_prim_anker)} "
              f"promoviert_ab={int(getattr(e, 'promoviert_ab_bar', -1))} "
              f"status={getattr(e, 'status', '?')}")
        for b, p in e.wicks:
            print(f"      wick bar {b:>5} "
                  f"({ts.iloc[b].strftime('%d.%m. %H:%M')}) {p:.4f}")
print("\nENDE E-34n/3b")
