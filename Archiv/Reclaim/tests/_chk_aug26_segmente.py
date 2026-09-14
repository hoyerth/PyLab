# -*- coding: utf-8 -*-
"""Phase 2 (READ-ONLY): Kausale Segment-Discovery ueber AUG26.

AUG26 = 2026-08-03 00:00 .. 2026-08-31 22:45 (n = 1932, 21 Handelstage).
Fenster wird NUR zur Laufzeit in ``engine.FENSTER`` ergaenzt -- die
Engine-Datei bleibt unveraendert.

Portiert wird die arretierte Segmentierungs-Routine aus
``test/_tmp_e34_auto.py`` (<=> ``_chk_v019_kausal_vergleich.py``):
  _lebt_kausal -> ecken -> Wechselpunkte -> roh -> zusammenfassen(77) -> _nah

Keine PNG-Erzeugung, keine Regel-Aenderung, keine festen Kanten-IDs.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("engine", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

# --- AUG26-Fenster (nur RAM; Monatsende exklusiv) -------------------------
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = scan["n"]
_BOX = int(scan["box_end_bar"])
scan["box_end_bar"] = n
d = scan["d"]
ts = list(d["ts"])

alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {int(e.kid): e for e in alle}
LIVE = cfg.wall_live_bars
BAND = cfg.touch_band_pct
SCHWELLE = 77

print("=" * 104)
print("PHASE 2 -- KAUSALE SEGMENT-DISCOVERY AUG26 (03.08..31.08.2026)")
print("=" * 104)
print(f"Kantenkatalog : {len(scan['edges'])} edges + {len(scan['seeds'])} seeds "
      f"= {len(alle)} Kanten")
print(f"n             : {n} Bars | box_end(19.08.) = Bar {_BOX} = {ts[_BOX]}")
print(f"Preisspanne   : {d['low'].min():.4f} .. {d['high'].max():.4f}")
print(f"Regel         : aeusserste LEBENDE Linie, kausal (bestaetigte Dochte "
      f"b+2<=k) | LIVE={LIVE} | BAND={BAND}% | Schwelle={SCHWELLE}")


# ----------------------------------------------------- Regel (Port 1:1)
def _lebt_kausal(e, k: int) -> bool:
    """Streng kausal: nur BESTAETIGTE Dochte (b + 2 <= k)."""
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]
    return bool(b) and max(b) >= k - LIVE


def ecken(k: int) -> Tuple[Optional[int], Optional[int]]:
    """(decke_kid, boden_kid) = aeusserste lebende Linien, kausal."""
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
    if cur == (None, None):
        continue
    if vor is not None and cur == vor:
        continue
    vor = cur
    wechsel.append((k, cur[0], cur[1]))

print(f"\nA. UEBERGANGSPUNKTE der zielfreien Regel: {len(wechsel)}")
print(f"   {'Bar':>5}  {'BKZ-Zeit':<20}{'Decke':<20}{'Boden':<20}")
for (k, ko, ku) in wechsel:
    so = "-" if ko is None else f"K{ko} {katalog[ko].basis_bei(k):.4f}"
    su = "-" if ku is None else f"K{ku} {katalog[ku].basis_bei(k):.4f}"
    print(f"   {k:>5}  {str(ts[k]):<20}{so:<20}{su:<20}")

# ----------------------------------------------------- Roh-Segmente
START = 0                       # AUG26: Monatsbeginn, kein AUG-Anker
roh: List[List[int]] = []
for (k, ko, ku) in wechsel:
    if k < START or ko is None or ku is None:
        continue
    if roh:
        roh[-1][1] = k - 1
    roh.append([k, n - 1, ko, ku])
if not roh:
    raise SystemExit("keine Roh-Segmente erzeugt")
print(f"\nB. ROH-SEGMENTE (vor Verschmelzung): {len(roh)}")
for s in roh:
    print(f"   {s[0]:>5}..{s[1]:<5} ({s[1] - s[0] + 1:>4} Bars)  "
          f"K{s[2]} {katalog[s[2]].basis_bei(s[0]):.4f} / "
          f"K{s[3]} {katalog[s[3]].basis_bei(s[0]):.4f}")


# ----------------------------------------------------- Verschmelzung
def _nah(p: List[int], s: List[int]) -> bool:
    """Beide Grenzniveaus praktisch gleich (<= touch_band_pct, arretiert)."""
    ko1, ko2 = katalog[p[2]].basis_bei(p[0]), katalog[s[2]].basis_bei(s[0])
    ku1, ku2 = katalog[p[3]].basis_bei(p[0]), katalog[s[3]].basis_bei(s[0])
    return (abs(ko2 - ko1) / ko1 * 100.0 <= BAND
            and abs(ku2 - ku1) / ku1 * 100.0 <= BAND)


def zusammenfassen(segs: List[List[int]], min_bars: int) -> List[List[int]]:
    """Verschmelzen: zu kurz ODER Grenzen praktisch unveraendert."""
    out: List[List[int]] = []
    for s in segs:
        if out and ((s[1] - s[0] + 1) < min_bars or _nah(out[-1], s)):
            out[-1][1] = s[1]
        else:
            out.append(list(s))
    return out


SEGS = zusammenfassen(roh, SCHWELLE)

print(f"\nC. SEGMENTE nach zusammenfassen(..., {SCHWELLE}): {len(SEGS)}")
print(f"   {'#':<3}{'Start':>6}..{'Ende':<6}{'Bars':>6}  "
      f"{'Decke':<22}{'Boden':<22}{'Startzeit'}")
for i, (a, b, ko, ku) in enumerate(SEGS, 1):
    so = f"K{ko} {katalog[ko].basis_bei(a):.4f}"
    su = f"K{ku} {katalog[ku].basis_bei(a):.4f}"
    print(f"   {i:<3}{a:>6}..{b:<6}{b - a + 1:>6}  {so:<22}{su:<22}{ts[a]}")

if SEGS:
    _f = SEGS[0]
    print(f"\n   Erstes bestaetigtes Segment: Bar {_f[0]} (= {ts[_f[0]]}), "
          f"Warmup bis dahin = {_f[0]} Bars")
    print(f"   Letztes Segment endet bei Bar {SEGS[-1][1]} (= {ts[SEGS[-1][1]]})")

# --------------------------------------------- Abgleich: Altstand + 460
print("\nD. ABGLEICH mit dem arretierten AUG-Stand, um +460 verschoben")
ALT = [(848, 1020, "P9", "K67/69.8700-override", "K77/68.3700-Literal"),
       (1033, 1173, "A1", "K67", "K82"),
       (1174, 1287, "A2", "K73", "K82")]
print(f"   {'Soll(alt+460)':<24}{'gefunden (AUG26)':<44}{'Bewertung'}")
for (a0, b0, _tag, _d, _u) in ALT:
    a1, b1 = a0 + 460, b0 + 460
    hit = [s for s in SEGS if s[0] <= a1 <= s[1] or s[0] <= b1 <= s[1]
           or (a1 <= s[0] and s[1] <= b1)]
    if hit:
        s = hit[0]
        txt = (f"{s[0]}..{s[1]}  K{s[2]}/K{s[3]}")
        bew = ("exakt" if (s[0] == a1 and s[1] == b1)
               else f"~({a1}..{b1} vs {s[0]}..{s[1]})")
    else:
        txt = "-"
        bew = "NICHT gefunden"
    print(f"   {f'{a1}..{b1}':<24}{txt:<44}{bew}")

print("\nE. ROH-/SEGMENT-STATISTIK")
print(f"   Roh-Segmente  : {len(roh)} (davon < {SCHWELLE} Bars: "
      f"{sum(1 for s in roh if s[1] - s[0] + 1 < SCHWELLE)})")
if SEGS:
    _laengen = [s[1] - s[0] + 1 for s in SEGS]
    print(f"   Segmente      : {len(SEGS)} | Laenge min/med/max = "
          f"{min(_laengen)}/{sorted(_laengen)[len(_laengen) // 2]}/{max(_laengen)}")
    _cov = sum(_laengen)
    print(f"   Abdeckung     : {_cov} von {n} Bars ({100.0 * _cov / n:.1f} %)")

print("\nENDE PHASE 2")
