# -*- coding: utf-8 -*-
"""READ-ONLY Pruefung: "Nur EINE valide Erweiterung je Balance".

Verbindet drei Achsen:
  R1 (A)  : delta >= 0.60% UND 2 Kerzen komplett ausserhalb (Docht inkl.)
  R2 (C)  : 2-BODY ausserhalb (min/max von op/cl)
  R3 (V)  : Kissen/Vakuum -- gibt es am Ausschlag-Extrem eine LEBENDE Vorkante
            (geburt <= k, letzter Docht >= k-96) in Bewegungsrichtung?

Zusatz (neues Kriterium des Anwenders): je Balance nur EINE valide Erweiterung
(Kissen vorhanden); jede weitere grosse Aussenbewegung = Transition.

Kein Patch, kein Einbrand. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_spec = importlib.util.spec_from_file_location("eng5", ENGINE_P)
engine = importlib.util.module_from_spec(_spec)
sys.modules["eng5"] = engine
_spec.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
D = scan["d"]
TS = list(D["ts"])
op = D["open"].to_numpy(dtype=float)
hi = D["high"].to_numpy(dtype=float)
lo = D["low"].to_numpy(dtype=float)
cl = D["close"].to_numpy(dtype=float)
ALLE = list(scan["edges"]) + list(scan["seeds"])
LIVE = int(cfg.wall_live_bars)
TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08", "12.08",
        "13.08", "14.08", "17.08", "18.08", "19.08", "20.08", "21.08", "24.08",
        "25.08", "26.08", "27.08", "28.08", "31.08"]
VERLUSTE = (391, 433, 498, 533, 1222, 1315, 1812)


def tag(bar: int) -> str:
    i = bar // 92
    return f"{TAGE[i]}({bar - i * 92:02d})" if 0 <= i < len(TAGE) else "?"


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def basis(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def ecken(k: int) -> Tuple[Optional[float], Optional[float]]:
    ob = [basis(e, k) for e in ALLE if int(e.geburts_bar) <= k and lebt(e, k) and e.seite == "OBEN"]  # type: ignore[attr-defined]
    un = [basis(e, k) for e in ALLE if int(e.geburts_bar) <= k and lebt(e, k) and e.seite == "UNTEN"]  # type: ignore[attr-defined]
    return (max(ob) if ob else None, min(un) if un else None)


# ---- Korridor (lebende Kanten) je Bar, kausal -----------------------------
O: List[Optional[float]] = [None] * n
U: List[Optional[float]] = [None] * n
for k in range(n):
    O[k], U[k] = ecken(k)


def kissen(k: int, richtung: str, extrem: float, band_pct: float = 0.30) -> List[str]:
    """Lebende Vorkanten in Bewegungsrichtung am/unter/ueber dem Extrem."""
    out = []
    for e in ALLE:
        if int(e.geburts_bar) > k or not lebt(e, k):  # type: ignore[attr-defined]
            continue
        b = basis(e, k)
        if richtung == "AB":
            if e.seite == "UNTEN" and b <= extrem * (1.0 + band_pct / 100.0):
                out.append(f"K{int(e.kid)}@{b:.4f}")
        else:
            if e.seite == "OBEN" and b >= extrem * (1.0 - band_pct / 100.0):
                out.append(f"K{int(e.kid)}@{b:.4f}")
    return out


def gekreuzt(k: int, richtung: str, ref: float, extrem: float) -> List[str]:
    """Lebende Kanten, die die Bewegung zwischen ref und extrem durchlaufen hat."""
    out = []
    for e in ALLE:
        if int(e.geburts_bar) > k or not lebt(e, k):  # type: ignore[attr-defined]
            continue
        b = basis(e, k)
        if richtung == "AB":
            if e.seite == "UNTEN" and extrem < b < ref:
                out.append(f"K{int(e.kid)}@{b:.4f}")
        else:
            if e.seite == "OBEN" and ref < b < extrem:
                out.append(f"K{int(e.kid)}@{b:.4f}")
    return out


print("=" * 138)
print("AUSSCHLAG-TABELLE (neues Extrem jenseits des lebenden Korridors) | AUG26")
print("=" * 138)
print(f"{'Bar':>5} {'Tag':<11} {'Ri':<3} {'Extrem':>8} {'Size%':>7} "
      f"{'A':>2} {'C':>2} {'Kiss':>4} {'Vakuum':>6}  Kissen/gekreuzt")
for k in range(3, n):
    for richtung in ("AUF", "AB"):
        ref = O[k - 1] if richtung == "AUF" else U[k - 1]
        if ref is None:
            continue
        extrem = hi[k] if richtung == "AUF" else lo[k]
        if richtung == "AUF" and not (extrem > ref):
            continue
        if richtung == "AB" and not (extrem < ref):
            continue
        size = (extrem - ref) / ref * 100.0 if richtung == "AUF" else (ref - extrem) / ref * 100.0
        if richtung == "AUF":
            a = size >= 0.60 and lo[k - 1] > ref and lo[k] > ref
            c = min(op[k - 1], cl[k - 1]) > ref and min(op[k], cl[k]) > ref
        else:
            a = size >= 0.60 and hi[k - 1] < ref and hi[k] < ref
            c = max(op[k - 1], cl[k - 1]) < ref and max(op[k], cl[k]) < ref
        kis = kissen(k, richtung, extrem)
        kr = gekreuzt(k, richtung, ref, extrem)
        mk = " <== VERLUST-BAR" if k in VERLUSTE else ""
        print(f"{k:>5} {tag(k):<11} {richtung:<3} {extrem:>8.4f} {size:>+7.3f} "
              f"{'A' if a else '-'} {'C' if c else '-':>2} {len(kis):>4} "
              f"{'JA' if not kis else 'nein':>6}  kis=[{','.join(kis)}] kreuz=[{','.join(kr)}]{mk}")
