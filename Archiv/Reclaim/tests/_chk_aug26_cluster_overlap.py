# -*- coding: utf-8 -*-
"""AUG26 Schritt 2c (READ-ONLY): Cluster ueber KORRIDOR-UEBERSCHNEIDUNG.

Befund 2b: Ketten-Merge ueber Grenzengleichheit traegt nicht (0,60 % -> 62
Segmente). Die Roh-Korridore ueberschneiden sich aber stark, z.B.
    [60.851..65.117] -> [63.040..64.863] -> [64.208..66.459]
Hier wird daher der gemeinsame KERN getestet:
    merge, solange der Schnitt der Korridore >= theta * min(Breite) bleibt.
Kern wird dabei als laufender Schnitt gefuehrt (Balance = Zone, die ALLE
Mitglieder respektieren).

Zusaetzlich: Dwell/Abdeckung je Cluster und Trend-Erkennung (Kernbreite
vs. durchlaufene Preisspanne).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("engine_o", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_o"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = scan["n"]
BOX = int(scan["box_end_bar"])
scan["box_end_bar"] = n
d = scan["d"]
ts = list(d["ts"])
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {int(e.kid): e for e in alle}


def _lebt_kausal(e, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]
    return bool(b) and max(b) >= k - cfg.wall_live_bars


def ecken(k: int) -> Tuple[Optional[int], Optional[int]]:
    oben, unten = [], []
    for e in alle:
        if not _lebt_kausal(e, k):
            continue
        (oben if e.seite == "OBEN" else unten).append(e)
    o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
    u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
    return (int(o.kid) if o else None), (int(u.kid) if u else None)


wechsel: List[Tuple[int, Optional[int], Optional[int]]] = []
vor: Optional[Tuple[Optional[int], Optional[int]]] = None
for k in range(2, n):
    cur = ecken(k)
    if cur == (None, None) or cur == vor:
        continue
    vor = cur
    wechsel.append((k, cur[0], cur[1]))

roh: List[List[int]] = []
for (k, ko, ku) in wechsel:
    if ko is None or ku is None:
        continue
    if roh:
        roh[-1][1] = k - 1
    roh.append([k, n - 1, ko, ku])

KORR: List[Tuple[float, float]] = []
for s in roh:
    vu = float(katalog[s[3]].basis_bei(s[0]))
    vo = float(katalog[s[2]].basis_bei(s[0]))
    KORR.append((min(vu, vo), max(vu, vo)))

print("=" * 104)
print("AUG26 SCHRITT 2c: CLUSTER UEBER KORRIDOR-UEBERSCHNEIDUNG (gemeinsamer Kern)")
print("=" * 104)
print(f"n = {n} | box_end = Bar {BOX} | Roh-Segmente {len(roh)}")


def _cluster(theta: float) -> List[Tuple[int, int, float, float]]:
    """Greedy: Kern = laufender Schnitt; Abbruch wenn Restkern zu klein."""
    out: List[Tuple[int, int, float, float]] = []
    i = 0
    while i < len(roh):
        k0, k1 = roh[i][0], roh[i][1]
        vu, vo = KORR[i]
        j = i + 1
        while j < len(roh):
            nu, no = KORR[j]
            iu, io = max(vu, nu), min(vo, no)
            if io <= iu:
                break
            breite_kern = io - iu
            breite_mit = min(vo - vu, no - nu)
            if breite_mit <= 0 or breite_kern < theta * breite_mit:
                break
            vu, vo = iu, io
            k1 = roh[j][1]
            j += 1
        out.append((k0, k1, vu, vo))
        i = j
    return out


for _theta in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    _c = _cluster(_theta)
    _cov = sum(b - a + 1 for a, b, _, _ in _c)
    print(f"\n{'-' * 104}")
    print(f"theta = {_theta:.1f}  ->  {len(_c)} Balances "
          f"| Abdeckung {_cov}/{n} Bars ({100.0 * _cov / n:.1f} %)")
    print(f"{'-' * 104}")
    print(f"   {'#':<4}{'Fenster':<16}{'Bars':>5}{'Anteil':>8}  "
          f"{'Kern (Balance)':<24}{'Spanne IST':<24}{'aussen':>8}")
    for _i, (_a, _b, _vu, _vo) in enumerate(_c, 1):
        _span = _b - _a + 1
        _ilo = float(lo[_a:_b + 1].min())
        _ihi = float(hi[_a:_b + 1].max())
        _aus = int(((hi[_a:_b + 1] > _vo) | (lo[_a:_b + 1] < _vu)).sum())
        print(f"   {_i:<4}{f'{_a}..{_b}':<16}{_span:>5}"
              f"{100.0 * _span / n:>7.1f}%  "
              f"{f'{_vu:.4f}..{_vo:.4f}':<24}"
              f"{f'{_ilo:.4f}..{_ihi:.4f}':<24}"
              f"{_aus:>4} ({100.0 * _aus / _span:>5.1f} %)  "
              f"{str(ts[_a])[:16]}")

print("\n" + "=" * 104)
print("GEGENPROBE: Balances aus 2c bei theta 0.6 gegen die Anwender-Erwartung")
print("=" * 104)
print("   Erwartet (G3): Boden 56.5-58.5 | Konsolidierung 63-65 | "
      "AUG-H1-Box 68-70")
print("ENDE AUG26 SCHRITT 2c")
