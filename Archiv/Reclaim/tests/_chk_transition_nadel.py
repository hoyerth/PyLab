# -*- coding: utf-8 -*-
"""READ-ONLY Nadelprobe: 10.08. 15:00 (Bar 520) + Kanten-Kissen vs. Vakuum."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_spec = importlib.util.spec_from_file_location("eng4", ENGINE_P)
engine = importlib.util.module_from_spec(_spec)
sys.modules["eng4"] = engine
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
op = D["open"].to_numpy(dtype=float)
ALLE = list(scan["edges"]) + list(scan["seeds"])
LIVE = int(cfg.wall_live_bars)

print("=" * 110)
print("N1) 10.08. 14:00-16:15 (Bars 512..525) -- wo genau ist 63.7 / 15:00?")
print("=" * 110)
for k in range(510, 527):
    print(f"   {k:>4} {TS[k]} O={op[k]:.4f} H={hi[k]:.4f} L={lo[k]:.4f} C={cl[k]:.4f}")


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


print("\n" + "=" * 110)
print("N2) KISSEN vs. VAKUUM: lebende UNTERkanten unter dem jeweiligen Tagestief")
print("=" * 110)
for label, bar, tief in (("14.08. Tief", 858, lo[858]), ("19.08. Tief", 1117, lo[1117]),
                         ("19.08. 01:00", 1108, lo[1108])):
    unter: List[Tuple[float, object]] = sorted(
        [(float(e.basis_bei(bar)), e) for e in ALLE  # type: ignore[attr-defined]
         if int(e.geburts_bar) <= bar and lebt(e, bar) and e.seite == "UNTEN" and float(e.basis_bei(bar)) < tief],  # type: ignore[attr-defined]
        reverse=True)
    print(f"\n   {label}: Bar {bar} ({TS[bar]}) Tief={tief:.4f}")
    print(f"     LEBENDE Unterkanten UNTER dem Tief: {len(unter)}")
    for b, e in unter:
        print(f"        {('S' if e in scan['seeds'] else 'E')}K{int(e.kid):<4} @{b:>7.4f} "
              f"Abst={(tief-b)/b*100:>+.3f}%  geb{int(e.geburts_bar):>4} "
              f"letzterDocht={max(bb for bb,_ in e.wicks if bb<=bar)} age{bar-int(e.erster_pivot_bar)}")

print("\n" + "=" * 110)
print("N3) 14.08.: Wieviele lebende Unterkanten lagen im Anlauf-Bereich 63.4..64.0?")
print("=" * 110)
for bar in (840, 846, 858):
    band = sorted([(float(e.basis_bei(bar)), e) for e in ALLE  # type: ignore[attr-defined]
                   if int(e.geburts_bar) <= bar and e.seite == "UNTEN"  # type: ignore[attr-defined]
                   and 63.2 <= float(e.basis_bei(bar)) <= 64.1])  # type: ignore[attr-defined]
    print(f"\n   Bar {bar} ({TS[bar]}): Kandidaten 63.2..64.1 = {len(band)}")
    for b, e in band:
        print(f"        {('S' if e in scan['seeds'] else 'E')}K{int(e.kid):<4} @{b:>7.4f} leb={'J' if lebt(e,bar) else '-'} "
              f"geb{int(e.geburts_bar):>4} dochte={[(bb,round(pp,3)) for bb,pp in e.wicks]}")
