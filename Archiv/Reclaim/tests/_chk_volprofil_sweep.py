# -*- coding: utf-8 -*-
"""READ-ONLY Variabilitaets-Sweep: Trennt die Aktivitaets-/Volumen-Achse A von B/C/D?

Systematischer Gitter-Sweep ueber
  Bin-Aufloesung : 20 30 50 60 100 120 200
  Lookback       : 48 96 192 384 768 1152
  VA-Fraktion    : 0.68 0.70 0.80
  Profil-Range   : data | sym_2pct | sym_3pct
  Mess-Endpunkt  : brk (kausal) | low (ex post)
  B-Wandvariante : B_first=64.798 (K68) | B_last=63.156 (K57)

Je Metrik wird geprueft, ob sich A ueber ALLE Konfigurationen von X trennen
laesst (Intervalle disjunkt). Ergebnis: belastbare vs. fragile Diskriminatoren
-- inklusive der Moeglichkeit, dass es KEINEN gibt.

Kein Patch. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("esw", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["esw"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
d = scan["d"]; ts = list(d["ts"])
op = d["open"].to_numpy(float); hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float); cl = d["close"].to_numpy(float)
vo = d["tick_volume"].to_numpy(float)

# Anker je Event: (k0, brk, kl, wand)
EV: Dict[str, Dict[str, float]] = {
    "A": {"k0": 836, "brk": 838, "kl": 858, "wall": 64.2680},
    "B_f": {"k0": 1076, "brk": 1078, "kl": 1133, "wall": 64.7980},
    "B_l": {"k0": 1076, "brk": 1106, "kl": 1133, "wall": 63.1560},
    "C": {"k0": 1780, "brk": 1820, "kl": 1820, "wall": 67.6000},
    "D": {"k0": 1972, "brk": 1972, "kl": 2040, "wall": 66.4140},
}


def profil(k_start: int, k_end: int, bins: int,
           pmin: Optional[float] = None, pmax: Optional[float] = None) -> Dict:
    if pmin is None:
        pmin = float(lo[k_start:k_end + 1].min())
        pmax = float(hi[k_start:k_end + 1].max())
    if pmax <= pmin:
        return {}
    edges = np.linspace(pmin, pmax, bins + 1)
    vol = np.zeros(bins, dtype=float)
    for k in range(k_start, k_end + 1):
        l_, h_, v_ = lo[k], hi[k], vo[k]
        if h_ <= l_ or v_ <= 0:
            continue
        lb = int(np.clip(np.searchsorted(edges, l_, side="right") - 1, 0, bins - 1))
        hb = int(np.clip(np.searchsorted(edges, h_, side="left") - 1, 0, bins - 1))
        if lb == hb:
            vol[lb] += v_
        else:
            ov = np.array([max(0.0, min(h_, edges[b + 1]) - max(l_, edges[b]))
                           for b in range(lb, hb + 1)])
            tot = float(ov.sum())
            if tot > 0:
                vol[lb:hb + 1] += v_ * ov / tot
    mt = (edges[:-1] + edges[1:]) / 2.0
    tv = float(vol.sum())
    if tv <= 0:
        return {}
    return {"edges": edges, "mitte": mt, "vol": vol, "tot": tv}


def va(P: Dict, frac: float) -> Tuple[float, float]:
    vol, mt = P["vol"], P["mitte"]
    order = np.argsort(vol)[::-1]
    ziel = frac * P["tot"]
    acc = 0.0
    sel: List[int] = []
    for i in order:
        acc += vol[i]
        sel.append(int(i))
        if acc >= ziel:
            break
    return float(mt[min(sel)]), float(mt[max(sel)])


def metrik(lab: str, bins: int, lb: int, vaf: float, rangemode: str, end: str) -> Dict[str, float]:
    A = EV[lab]
    ke = int(A["brk"] if end == "brk" else A["kl"])
    wall = float(A["wall"]); kl = int(A["kl"])
    ks = max(0, ke - lb + 1)
    if rangemode == "data":
        lo_r = float(lo[ks:ke + 1].min()); hi_r = float(hi[ks:ke + 1].max())
    elif rangemode == "sym_2pct":
        lo_r, hi_r = wall * 0.98, wall * 1.02
    else:
        lo_r, hi_r = wall * 0.97, wall * 1.03
    P = profil(ks, ke, bins, lo_r, hi_r)
    if not P:
        return {}
    v = P["vol"]
    bi = int(np.clip(np.searchsorted(P["edges"], wall, side="right") - 1, 0, len(v) - 1))
    vmax = float(v.max()); mu = float(v.mean()); sd = float(v.std())
    p_idx = int(np.argmax(v))
    poc = float(P["mitte"][p_idx])
    vlo, vhi = va(P, vaf)
    exc = max(wall - lo[kl], 1e-9)
    ks2 = min(ks, int(A["brk"]))
    rng = hi[ks2:kl + 1] - lo[ks2:kl + 1]
    pos = np.where(rng > 0, (cl[ks2:kl + 1] - lo[ks2:kl + 1]) / np.where(rng > 0, rng, 1), 0.5)
    dv = vo[ks2:kl + 1] * (2 * pos - 1)
    vw = float((v * P["mitte"]).sum() / P["tot"])
    return {
        "wand_share": v[bi] / vmax,
        "wand_z": (v[bi] - mu) / sd if sd > 0 else float("nan"),
        "poc_pos": (poc - wall) / exc,
        "hhi": float(np.sum((v / P["tot"]) ** 2)),
        "va_lo_rel": (vlo - wall) / wall * 100,
        "va_hi_rel": (vhi - wall) / wall * 100,
        "va_breite": (vhi - vlo) / wall * 100,
        "peak_share": vmax / P["tot"],
        "vwap_pos": (vw - wall) / exc,
        "delta_norm": float(dv.sum() / max(vo[ks2:kl + 1].sum(), 1)),
        "exc_pct": (wall - lo[kl]) / wall * 100,
    }


BINS = [20, 30, 50, 60, 100, 120, 200]
LBS = [48, 96, 192, 384, 768, 1152]
VAFS = [0.68, 0.70, 0.80]
RANGES = ["data", "sym_2pct", "sym_3pct"]
ENDS = ["brk", "low"]
METRICS = ["wand_share", "wand_z", "poc_pos", "hhi", "va_lo_rel", "va_hi_rel",
           "va_breite", "peak_share", "vwap_pos", "delta_norm", "exc_pct"]

# Sammeln
DAT: Dict[str, Dict[str, List[float]]] = {lab: {m: [] for m in METRICS} for lab in EV}
ncfg = 0
for bins, lb, vaf, rg, en in itertools.product(BINS, LBS, VAFS, RANGES, ENDS):
    ncfg += 1
    for lab in EV:
        r = metrik(lab, bins, lb, vaf, rg, en)
        for m in METRICS:
            if m in r and np.isfinite(r[m]):
                DAT[lab][m].append(r[m])

print("=" * 130)
print(f"VARIABILITAETS-SWEEP  |  Konfigurationen: {ncfg}  (Bins {len(BINS)} x LB {len(LBS)} "
      f"x VA {len(VAFS)} x Range {len(RANGES)} x Ende {len(ENDS)})")
print("=" * 130)
print(f"{'Metrik':<12} " + " ".join(f"{l:>22}" for l in ["A", "B_first", "B_last", "C", "D"]))
print("(min .. max  [Spanne]  ueber alle Konfigurationen)")
for m in METRICS:
    cells = []
    for lab in ["A", "B_f", "B_l", "C", "D"]:
        s = DAT[lab][m]
        if not s:
            cells.append("-")
            continue
        cells.append(f"{min(s):.4f}..{max(s):.4f}[{max(s)-min(s):.4f}]")
    print(f"{m:<12} " + " ".join(f"{c:>22}" for c in cells))

print("\n" + "=" * 130)
print("TRENNSCHAERFE A vs X  (disjunkte Intervalle ueber ALLE Konfigurationen?)")
print("=" * 130)


def trennt(a: List[float], b: List[float]) -> Tuple[bool, float, float]:
    """(disjunkt?, A-Intervall, X-Intervall) + Ueberlappungsmass."""
    if not a or not b:
        return False, float("nan"), float("nan")
    amin, amax, bmin, bmax = min(a), max(a), min(b), max(b)
    disj = amax < bmin or bmax < amin
    ov = max(0.0, min(amax, bmax) - max(amin, bmin))
    span = max(amax, bmax) - min(amin, bmin)
    return disj, ov / span if span > 0 else 1.0, 0.0


print(f"{'Metrik':<12} {'A vs B_first':>26} {'A vs B_last':>26} {'A vs C':>26} {'A vs D':>26}")
score = {k: 0 for k in ["B_f", "B_l", "C", "D"]}
for m in METRICS:
    row = []
    for lab in ["B_f", "B_l", "C", "D"]:
        ok, ovl, _ = trennt(DAT["A"][m], DAT[lab][m])
        row.append(f"{'TRENNT' if ok else 'ueberlappt'} ({ovl*100:.0f}%)")
        if ok:
            score[lab] += 1
    print(f"{m:<12} " + " ".join(f"{c:>26}" for c in row))

print(f"\nRobuste Trennmerkmale je Paar (von {len(METRICS)}):")
name = {"B_f": "A vs B_first", "B_l": "A vs B_last", "C": "A vs C", "D": "A vs D"}
for lab in ["B_f", "B_l", "C", "D"]:
    treff = [m for m in METRICS if trennt(DAT["A"][m], DAT[lab][m])[0]]
    print(f"  {name[lab]:<14}: {score[lab]}/{len(METRICS)}  ->  {treff if treff else 'KEINE'}")

print("\n" + "=" * 130)
print("BEFUND")
print("=" * 130)
print("  Ein Merkmal gilt nur dann als belastbarer Diskriminator, wenn es A ueber das")
print("  GESAMTE Parameter-Gitter von der jeweiligen Gegengruppe trennt. Einzelne")
print("  'schoene' Beobachtungen bei einer Parameterwahl sind keine Evidenz.")
