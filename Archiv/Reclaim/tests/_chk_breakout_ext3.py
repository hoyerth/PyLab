# -*- coding: utf-8 -*-
"""READ-ONLY Korridor-Evolution Aug-Ende -> September (edges-only, korrigiert).

Aussengrenzen: Oberkante = MAX lebender OBEN-Basis, Unterkante = MIN
lebender UNTEN-Basis (wie _chk_expansion_regel.py ecken()).
Zeigt Balance-Tod + monotone Abwaertsexpansion (C/D/E als Legs EINES Trends).

Kein Patch. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("ekor2", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["ekor2"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
n = int(scan["n"]); d = scan["d"]; ts = list(d["ts"])
o = d["open"].to_numpy(float); h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float); c = d["close"].to_numpy(float)
EDGES = list(scan["edges"])
LIVE = int(cfg.wall_live_bars)


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def basis(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def ecken(k: int) -> Tuple[Optional[float], Optional[float], int, int, Optional[int], Optional[int]]:
    ob = [(int(e.kid), basis(e, k)) for e in EDGES
          if e.seite == "OBEN" and int(e.geburts_bar) <= k and lebt(e, k)]  # type: ignore[attr-defined]
    un = [(int(e.kid), basis(e, k)) for e in EDGES
          if e.seite == "UNTEN" and int(e.geburts_bar) <= k and lebt(e, k)]  # type: ignore[attr-defined]
    top = max(ob, key=lambda t: t[1]) if ob else (None, None)
    bot = min(un, key=lambda t: t[1]) if un else (None, None)
    return top[1], bot[1], len(ob), len(un), top[0], bot[0]


W = {"A": (836, 864), "C": (1780, 1820), "D": (1972, 2088), "E": (2598, 2718)}

print("=" * 118)
print("KORRIDOR-EVOLUTION (edges-only)  |  25.08. -> 11.09.  (alle 8 Bars, Markierung C/D/E)")
print("=" * 118)
print(f"{'Bar':>5} {'BKZ':<20} {'Close':>8} {'U-Kante':>8} {'O-Kante':>8} "
      f"{'Breite%':>8} {'nU':>3} {'nO':>3}  Lage")
for k in range(1740, n, 8):
    top, bot, no, nu, kto, kbo = ecken(k)
    br = (top - bot) / bot * 100 if (top and bot) else float("nan")
    lage = "IN" if (top and bot and bot <= c[k] <= top) else ("OBEN" if (top and c[k] > top) else "UNTEN")
    mark = ""
    for lab, (k0, k1) in W.items():
        if k0 <= k <= k1:
            mark = f"  [{lab}]"
    print(f"{k:>5} {str(ts[k]):<20} {c[k]:>8.4f} "
          f"{(bot if bot else float('nan')):>8.4f} {(top if top else float('nan')):>8.4f} "
          f"{br:>8.3f} {nu:>3} {no:>3}  {lage}{mark}")

print("\n" + "=" * 118)
print("TAGES-UEBERSICHT 25.08. -> 11.09. (BKZ): OHLC, Korridor am Tagesende")
print("=" * 118)
print(f"{'Tag':<12} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Net%':>7} "
      f"{'U-Kante':>8} {'O-Kante':>8} {'Breite%':>8}  Lage  Kennz.")
for day in sorted({str(t)[:10] for t in ts}):
    if day < "2026-08-25":
        continue
    idx = [k for k in range(n) if str(ts[k])[:10] == day]
    if not idx:
        continue
    a, b = idx[0], idx[-1]
    top, bot, no, nu, kto, kbo = ecken(b)
    net = (c[b] - o[a]) / o[a] * 100
    br = (top - bot) / bot * 100 if (top and bot) else float("nan")
    lage = "IN" if (top and bot and bot <= c[b] <= top) else ("OBEN" if (top and c[b] > top) else "UNTEN")
    tag = ""
    for lab, (k0, k1) in W.items():
        if not (k1 < a or k0 > b):
            tag += f"[{lab}]"
    print(f"{day:<12} {o[a]:>8.4f} {h[a:b+1].max():>8.4f} {l[a:b+1].min():>8.4f} "
          f"{c[b]:>8.4f} {net:>+7.2f} {(bot if bot else float('nan')):>8.4f} "
          f"{(top if top else float('nan')):>8.4f} {br:>8.3f}  {lage:<5} {tag}")

# ------------------------------------------------ Verlust des Bodens (Floor-Treppe)
print("\n" + "=" * 118)
print("BODEN-TREPPE (min lebende UNTEN) 25.08. -> 11.09.  -- Balance-Zerfall")
print("=" * 118)
last = None
for k in range(1740, n):
    bot = ecken(k)[1]
    if bot is None:
        continue
    if last is None or abs(bot - last) > 1e-9:
        print(f"  Bar {k:>5} {str(ts[k]):<20}  neuer Boden {bot:>8.4f}  (Close {c[k]:.4f}, "
              f"Δ {bot-last:+.4f})" if last is not None else
              f"  Bar {k:>5} {str(ts[k]):<20}  Boden {bot:>8.4f}")
        last = bot
