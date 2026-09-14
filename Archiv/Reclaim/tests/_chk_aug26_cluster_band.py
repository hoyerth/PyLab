# -*- coding: utf-8 -*-
"""AUG26 Schritt 2b (READ-ONLY): Plateau-Cluster mit strukturellem _nah-Band.

Befund aus Schritt 2: die Merge-Regel ``_nah`` der Engine nutzt
``cfg.touch_band_pct`` = 0,12 % (SE_BAND_PCT). Das ist ein TOUCH-Toleranzband,
kein PLATEAU-Band. Der Anwender meint mit ``_nah`` 0,5..0,8 % (G3/G4).

Hier daher:
  A) Ketten-Merge mit Band-Sweep (0,12/0,30/0,50/0,60/0,80/1,00 %),
     Kriterium "BEIDE Grenzen im Band" (konservativ, = G4-Wortlaut).
  B) dto., Kriterium "EINE Grenze im Band" (nur zum Kontrast).
  C) Plateau-Cluster der Kanten selbst (Single-Linkage auf basis_bei),
     Band-Sweep -> Anzahl Preisplateaus + Level-Tabelle.

Keine Regel-/Produktivaenderung; keine PNG-Erzeugung.
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("engine_c", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_c"] = engine
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

# ------------------------------------------------- Roh-Segmente (wie Schritt 2)
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

print("=" * 104)
print("AUG26 SCHRITT 2b: PLATEAU-CLUSTER MIT STRUKTURELLEM BAND")
print("=" * 104)
print(f"n = {n} | box_end(19.08.) = Bar {BOX} | Kanten "
      f"{len(scan['edges'])} edges + {len(scan['seeds'])} seeds | "
      f"Roh-Segmente {len(roh)}")
print(f"cfg.touch_band_pct (Engine-_nah) = {cfg.touch_band_pct} %  "
      f"<- TOUCH-Band, kein Plateau-Band")


def _grenzen(s: List[int], band: float) -> Tuple[float, float]:
    return (katalog[s[2]].basis_bei(s[0]), katalog[s[3]].basis_bei(s[0]))


def _merge(segs: List[List[int]], band: float,
           modus: str) -> List[List[int]]:
    """modus: 'beide' = beide Grenzen im Band; 'eine' = eine Grenze genuegt."""
    out: List[List[int]] = []
    for s in segs:
        if out:
            p = out[-1]
            vo1, vu1 = _grenzen(p, band)
            vo2, vu2 = _grenzen(s, band)
            do = abs(vo2 - vo1) / vo1 * 100.0
            du = abs(vu2 - vu1) / vu1 * 100.0
            treffer = (max(do, du) <= band) if modus == "beide" \
                else (min(do, du) <= band)
            if treffer:
                p[1] = s[1]
                continue
        out.append(list(s))
    return out


def _zeile(i: int, s: List[int]) -> str:
    vo, vu = _grenzen(s, 0.0)
    ist_lo = float(lo[s[0]:s[1] + 1].min())
    ist_hi = float(hi[s[0]:s[1] + 1].max())
    span = s[1] - s[0] + 1
    inv = "  [KORRIDOR INVERTIERT]" if vo < vu else ""
    aus = int(((hi[s[0]:s[1] + 1] > vo) | (lo[s[0]:s[1] + 1] < vu)).sum())
    return (f"      {i:>3}: {s[0]:>5}..{s[1]:<5} ({span:>4} Bars)  "
            f"{ts[s[0]]}  K{s[2]}/{s[3]}  "
            f"Korridor {vu:.4f}..{vo:.4f}  IST {ist_lo:.4f}..{ist_hi:.4f}  "
            f"ausserhalb {aus:>4} ({100.0 * aus / span:>5.1f} %){inv}")


BANDS = (0.12, 0.30, 0.50, 0.60, 0.80, 1.00)
for _modus, _titel in (("beide", "A) KETTEN-MERGE: BEIDE Grenzen im Band (G4-Wortlaut)"),
                       ("eine", "B) KETTEN-MERGE: EINE Grenze im Band (Kontrast)")):
    print("\n" + "-" * 104)
    print(_titel)
    print("-" * 104)
    print(f"   {'Band %':>7}{'Segmente':>10}{'>=77 Bars':>11}"
          f"{'Abdeckung Bars':>16}{'invertiert':>12}")
    for _b in BANDS:
        _segs = _merge(roh, _b, _modus)
        _cov = sum(s[1] - s[0] + 1 for s in _segs)
        _lang = sum(1 for s in _segs if s[1] - s[0] + 1 >= 77)
        _inv = sum(1 for s in _segs if _grenzen(s, _b)[0] < _grenzen(s, _b)[1])
        print(f"   {_b:>7.2f}{len(_segs):>10}{_lang:>11}{_cov:>16}{_inv:>12}")

print("\n" + "-" * 104)
print("A-DETAIL bei Band 0,60 %:")
print("-" * 104)
for _i, _s in enumerate(_merge(roh, 0.60, "beide"), 1):
    print(_zeile(_i, _s))

# ------------------------------------------------- C) Plateau-Cluster der Kanten
print("\n" + "-" * 104)
print("C) PLATEAU-CLUSTER DER KANTEN (Single-Linkage auf basis_bei(0))")
print("-" * 104)
_lvl = sorted(((float(e.basis_bei(0)), int(e.kid), e.seite) for e in alle),
              key=lambda z: z[0])
for _b in BANDS:
    _cl: List[List[Tuple[float, int, str]]] = []
    for _l in _lvl:
        if _cl and abs(_l[0] - _cl[-1][-1][0]) / _cl[-1][-1][0] * 100.0 <= _b:
            _cl[-1].append(_l)
        else:
            _cl.append([_l])
    print(f"\n   Band {_b:.2f} %  ->  {len(_cl)} Plateaus")
    for _j, _c in enumerate(_cl, 1):
        _kids = ",".join(f"K{k}" for _, k, _ in _c)
        print(f"      P{_j}: {_c[0][0]:.4f}..{_c[-1][0]:.4f}  "
              f"({len(_c)} Kanten)  {_kids}")

# ------------------------------------------------- Rollen-Zaehlung (Top-Levels)
print("\n" + "-" * 104)
print("D) ROLLEN-HAEUFIGKEIT der Grenzkanten in den Roh-Segmenten")
print("-" * 104)
_co = Counter(s[2] for s in roh)
_cu = Counter(s[3] for s in roh)
print("   Decke  Kid  n   Level      |  Boden  Kid  n   Level")
for _i in range(12):
    _l = _co.most_common(12)[_i] if _i < len(_co) else (None, 0)
    _r = _cu.most_common(12)[_i] if _i < len(_cu) else (None, 0)
    _ls = (f"K{_l[0]:<4}{_l[1]:>3}  {katalog[_l[0]].basis_bei(0):.4f}"
           if _l[0] is not None else "")
    _rs = (f"K{_r[0]:<4}{_r[1]:>3}  {katalog[_r[0]].basis_bei(0):.4f}"
           if _r[0] is not None else "")
    print(f"   {_ls:<32}|  {_rs}")

print("\nENDE AUG26 SCHRITT 2b")
