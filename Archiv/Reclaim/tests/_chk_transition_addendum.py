# -*- coding: utf-8 -*-
"""READ-ONLY Addendum: 14.08.-Pfad + 19.08.-gebrochene Kante im Detail."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import List

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
assert hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == SOLL

_spec = importlib.util.spec_from_file_location("eng3", ENGINE_P)
engine = importlib.util.module_from_spec(_spec)
sys.modules["eng3"] = engine
_spec.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
D = scan["d"]
TS = list(D["ts"])
hi = D["high"].to_numpy(dtype=float)
lo = D["low"].to_numpy(dtype=float)
cl = D["close"].to_numpy(dtype=float)
EDGES: List[object] = list(scan["edges"])
SEEDS: List[object] = list(scan["seeds"])
ALLE = EDGES + SEEDS
LIVE = int(cfg.wall_live_bars)


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def kind(e: object) -> str:
    return "S" if e in SEEDS else "E"


print("=" * 120)
print("A1) 14.08. INTRADAY-PFAD (Bars 828..919): Bewegung + naechste lebende Unterkante")
print("=" * 120)
lo_bar = int(lo[828:920].argmin()) + 828
print(f"  Tagestief 14.08. = Bar {lo_bar} ({TS[lo_bar]}) Low={lo[lo_bar]:.4f}")
for k in range(828, 920, 2):
    un = sorted([(float(e.basis_bei(k)), e) for e in ALLE
                 if int(e.geburts_bar) <= k and lebt(e, k) and e.seite == "UNTEN"])  # type: ignore[attr-defined]
    b, e = un[0]
    mark = "  <== TAGESTIEF" if k == lo_bar else ("  <== TIEF-NAEHE" if abs(k - lo_bar) <= 2 else "")
    print(f"   {k:>4} {TS[k]} H={hi[k]:>7.4f} L={lo[k]:>7.4f} C={cl[k]:>7.4f} | "
          f"n.Unterkante {kind(e)}K{int(e.kid)}@{b:>7.4f} Abst={(lo[k]-b)/b*100:+.3f}% "
          f"rib={'UNTER' if lo[k] < b else 'ueber'}{mark}")

print("\n" + "=" * 120)
print("A2) Die historische Kante im Detail (Geburt 10.08. 14:00/15:00 = Bars 512/520)")
print("=" * 120)
for e in ALLE:
    if int(e.kid) in (51, 62, 60):  # type: ignore[attr-defined]
        print(f"\n  {kind(e)}K{int(e.kid)} {e.seite} basis={float(e.basis):.4f} geb={int(e.geburts_bar)} "
              f"piv={int(e.erster_pivot_bar)} w={len(e.wicks)} status={e.status}")
        print(f"     alle Dochte (Bar, Preis): {[(b, round(p,4)) for b, p in e.wicks]}")

print("\n" + "=" * 120)
print("B1) 19.08.: die GEBROCHENEN / neuen Unterkanten im Detail")
print("=" * 120)
for e in ALLE:
    if int(e.kid) in (57, 99, 97, 100):  # type: ignore[attr-defined]
        print(f"\n  {kind(e)}K{int(e.kid)} {e.seite} basis={float(e.basis):.4f} geb={int(e.geburts_bar)} "
              f"piv={int(e.erster_pivot_bar)} w={len(e.wicks)} status={e.status}")
        print(f"     alle Dochte (Bar, Preis): {[(b, round(p,4)) for b, p in e.wicks]}")
