# -*- coding: utf-8 -*-
"""READ-ONLY Sweep 2: zusaetzliche Aktivitaets-Achsen (Dynamik, Profilform, Kaskade).

Ergaenzt Sweep 1 (Binned-Profil) um:
  * Volumen-Dynamik im Leg: Slope, CV, Persistenz (Autokorr), Lage des Vol-Peaks,
    Volumen am Tief / Mittel, erste vs. zweite Haelfte.
  * Profilform: Skewness, Kurtosis, Anzahl Spikes (>2x Median-Vorlauf).
  * Kauf-/Verkaufsdruck: Volumen auf Abwaerts- vs. Aufwaerts-Closes.
  * Struktur-Kaskade: Anzahl der Bodenbraeuche im Fenster.
  * Zeit-Achse: Bars unter der Wand, Zeit bis Tief.

Jede Groesse wird ueber das Gitter geprueft und auf Trennscharfe A vs B/C/D
getestet. Kein Patch. Engine-SHA hart geprueft.
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
_s = importlib.util.spec_from_file_location("esw2", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["esw2"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
d = scan["d"]; ts = list(d["ts"])
op = d["open"].to_numpy(float); hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float); cl = d["close"].to_numpy(float)
vo = d["tick_volume"].to_numpy(float)
EDGES = list(scan["edges"]); LIVE = int(cfg.wall_live_bars)


def lebt(e: object, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb <= k]  # type: ignore[attr-defined]
    return bool(b) and max(b) >= k - LIVE


def boden(k: int) -> Optional[float]:
    u = [float(e.basis_bei(k)) for e in EDGES  # type: ignore[attr-defined]
         if e.seite == "UNTEN" and int(e.geburts_bar) <= k and lebt(e, k)]  # type: ignore[attr-defined]
    return min(u) if u else None


EV: Dict[str, Dict[str, float]] = {
    "A": {"k0": 836, "k1": 864, "brk": 838, "kl": 858, "wall": 64.2680},
    "B_f": {"k0": 1076, "k1": 1160, "brk": 1078, "kl": 1133, "wall": 64.7980},
    "B_l": {"k0": 1076, "k1": 1160, "brk": 1106, "kl": 1133, "wall": 63.1560},
    "C": {"k0": 1780, "k1": 1820, "brk": 1820, "kl": 1820, "wall": 67.6000},
    "D": {"k0": 1972, "k1": 2088, "brk": 1972, "kl": 2040, "wall": 66.4140},
}
PRE = [96, 192, 384]


def kaskade(lab: str) -> int:
    """Anzahl distinkter Bodenbraeuche (neue Tiefstkante wird unterboten)."""
    A = EV[lab]
    k0, k1 = int(A["k0"]), int(A["k1"])
    cnt = 0
    akt: Optional[float] = None
    for k in range(k0, k1 + 1):
        f = boden(k)
        if f is None:
            continue
        if akt is None or f < akt - 1e-9:
            akt = f
        elif lo[k] < akt:
            cnt += 1
            akt = f
    return cnt


def feats(lab: str, pre: int) -> Dict[str, float]:
    A = EV[lab]
    k0, kl, brk = int(A["k0"]), int(A["kl"]), int(A["brk"])
    wall = float(A["wall"])
    v = vo[k0:kl + 1]
    mu = float(v.mean()); sd = float(v.std())
    x = np.arange(len(v), dtype=float)
    slope = float(np.polyfit(x, v, 1)[0]) / (mu or 1) if len(v) > 2 else float("nan")
    # Persistenz
    ac = float(np.corrcoef(v[:-1], v[1:])[0, 1]) if len(v) > 3 and v.std() > 0 else float("nan")
    # Volumen am Tief / Mittel
    low_v = float(vo[kl] / (mu or 1))
    # Lage des Volumen-Peaks im Leg (0..1)
    peaki = float(np.argmax(v) / max(len(v) - 1, 1))
    # Haelfte
    half = len(v) // 2
    r12 = float(v[half:].mean() / (v[:half].mean() or 1)) if half > 0 else float("nan")
    # Auf/Ab-Volumen
    dcl = np.diff(cl[k0:kl + 1])
    vd = v[1:]
    vup = float(vd[dcl > 0].sum()); vdn = float(vd[dcl < 0].sum())
    ud = vup / (vdn or 1)
    # Spikes gegen Vorlauf-Median
    p0 = max(0, k0 - pre)
    med = float(np.median(vo[p0:k0])) if k0 > p0 else float(np.median(vo))
    spikes = int((vo[k0:kl + 1] > 2.0 * med).sum())
    # Druck
    rng = hi[k0:kl + 1] - lo[k0:kl + 1]
    pos = np.where(rng > 0, (cl[k0:kl + 1] - lo[k0:kl + 1]) / np.where(rng > 0, rng, 1), 0.5)
    dnorm = float((vo[k0:kl + 1] * (2 * pos - 1)).sum() / max(vo[k0:kl + 1].sum(), 1))
    # Zeitachse
    unter = int((cl[k0:kl + 1] < wall).sum())
    tot = kl - k0 + 1
    # Bruch -> Tief
    latenz = kl - brk
    return {
        "vol_slope": slope, "vol_cv": sd / (mu or 1), "vol_persist": ac,
        "vol_low_ratio": low_v, "vol_peak_pos": peaki, "vol_h2_h1": r12,
        "vol_updown": ud, "spike_count": float(spikes), "delta_norm": dnorm,
        "quote_unter": unter / tot, "latenz_brk_low": float(latenz),
        "kaskade": float(kaskade(lab)), "exc_pct": (wall - lo[kl]) / wall * 100,
        "leg_bars": float(kl - k0 + 1),
    }


FEATS = list(feats("A", 96).keys())
DAT: Dict[str, Dict[str, List[float]]] = {lab: {m: [] for m in FEATS} for lab in EV}
ncfg = 0
for pre in PRE:
    ncfg += 1
    for lab in EV:
        r = feats(lab, pre)
        for m in FEATS:
            if m in r and np.isfinite(r[m]):
                DAT[lab][m].append(r[m])

print("=" * 128)
print(f"SWEEP 2  |  zusaetzliche Achsen, Vorlauf-Varianten: {PRE}  (Konfigurationen: {ncfg})")
print("=" * 128)
print(f"{'Merkmal':<16} " + " ".join(f"{l:>20}" for l in ["A", "B_first", "B_last", "C", "D"]))
for m in FEATS:
    cells = []
    for lab in ["A", "B_f", "B_l", "C", "D"]:
        s = DAT[lab][m]
        cells.append(f"{min(s):.4f}..{max(s):.4f}" if s else "-")
    print(f"{m:<16} " + " ".join(f"{c:>20}" for c in cells))

print("\n" + "=" * 128)
print("TRENNSCHAERFE  A vs X")
print("=" * 128)


def trennt(a: List[float], b: List[float]) -> Tuple[bool, float]:
    if not a or not b:
        return False, float("nan")
    amin, amax, bmin, bmax = min(a), max(a), min(b), max(b)
    ov = max(0.0, min(amax, bmax) - max(amin, bmin))
    span = max(amax, bmax) - min(amin, bmin)
    return (amax < bmin or bmax < amin), (ov / span if span > 0 else 1.0)


print(f"{'Merkmal':<16} {'vs B_first':>18} {'vs B_last':>18} {'vs C':>18} {'vs D':>18}")
score = {k: 0 for k in ["B_f", "B_l", "C", "D"]}
for m in FEATS:
    row = []
    for lab in ["B_f", "B_l", "C", "D"]:
        ok, ovl = trennt(DAT["A"][m], DAT[lab][m])
        row.append(f"{'TRENNT' if ok else 'ueberlappt'} ({ovl*100:.0f}%)")
        if ok:
            score[lab] += 1
    print(f"{m:<16} " + " ".join(f"{c:>18}" for c in row))

name = {"B_f": "A vs B_first", "B_l": "A vs B_last", "C": "A vs C", "D": "A vs D"}
print(f"\nRobuste Merkmale (von {len(FEATS)}):")
for lab in ["B_f", "B_l", "C", "D"]:
    treff = [m for m in FEATS if trennt(DAT["A"][m], DAT[lab][m])[0]]
    print(f"  {name[lab]:<14}: {score[lab]}/{len(FEATS)}  ->  {treff if treff else 'KEINE'}")

print("\n" + "=" * 128)
print("KASKADEN (strukturell, unabhaengig vom Volumen)")
print("=" * 128)
for lab in ["A", "B_f", "B_l", "C", "D"]:
    print(f"  {name.get(lab, lab):<14}: Bodenbraeuche im Fenster = {int(kaskade(lab))}")
