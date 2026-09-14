# -*- coding: utf-8 -*-
"""READ-ONLY Populations-Studie: alle Bodenbraeuche 2026, dann Einordnung A/B/C/D.

Statt n=1 je Ereignis: alle frischen Bodenbraeuche des Fensters 01.01.-11.09.2026
werden automatisch detektiert (Anker = min lebende UNTEN-Kante, edges-only).
Je Ereignis werden Aktivitaets-/Struktur-Merkmale ueber Horizonte H gemessen.

Dann: Perzentil-Lage von A (Referenz) und B/C/D in der Grundgesamtheit.
Damit ist die Aussage "A ist (nicht) unterscheidbar" statistisch belegt oder
widerlegt -- nicht mehr Einzelbeobachtung.

Kein Patch. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("epop", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["epop"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
WIN = ("2026-01-01", "2026-09-12")
engine.FENSTER["POP"] = WIN  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("POP", cfg)  # type: ignore[arg-type]
n = int(scan["n"]); d = scan["d"]; ts = list(d["ts"])
op = d["open"].to_numpy(float); hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float); cl = d["close"].to_numpy(float)
vo = d["tick_volume"].to_numpy(float)
EDGES = list(scan["edges"]); LIVE = int(cfg.wall_live_bars)
print(f"Populations-Fenster {WIN}: n={n} Bars, {len(EDGES)} edges")


def lebt(e: object, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb <= k]  # type: ignore[attr-defined]
    return bool(b) and max(b) >= k - LIVE


FLOOR: List[Optional[float]] = [None] * n
for k in range(n):
    u = [float(e.basis_bei(k)) for e in EDGES  # type: ignore[attr-defined]
         if e.seite == "UNTEN" and int(e.geburts_bar) <= k and lebt(e, k)]  # type: ignore[attr-defined]
    FLOOR[k] = min(u) if u else None

H = 24
MERKM = ["exc_pct", "vol_low_ratio", "vol_h2_h1", "vol_peak_pos", "delta_norm",
         "quote_unter", "vol_slope", "reclaim_bars", "vol_cv"]

events: List[Dict[str, float]] = []
for k in range(3, n - H):
    w = FLOOR[k - 1]
    if w is None:
        continue
    if not (lo[k] < w):                       # kein Bruch
        continue
    if k >= 4 and FLOOR[k - 2] is not None and lo[k - 1] < FLOOR[k - 2]:
        continue                              # kein frischer Bruch (Folgebar)
    kl = k
    for j in range(k, min(k + H, n)):
        if lo[j] < lo[kl]:
            kl = j
    exc = (w - lo[kl]) / w * 100
    v = vo[k:kl + 1]
    mu = float(v.mean()) if len(v) else 1.0
    sd = float(v.std()) if len(v) else 0.0
    x = np.arange(len(v), dtype=float)
    slope = float(np.polyfit(x, v, 1)[0]) / (mu or 1) if len(v) > 2 else 0.0
    half = max(len(v) // 2, 1)
    h2h1 = float(v[half:].mean() / (v[:half].mean() or 1)) if len(v) else 1.0
    peaki = float(np.argmax(v) / max(len(v) - 1, 1)) if len(v) else 0.0
    rng = hi[k:kl + 1] - lo[k:kl + 1]
    pos = np.where(rng > 0, (cl[k:kl + 1] - lo[k:kl + 1]) / np.where(rng > 0, rng, 1), 0.5)
    dnorm = float((v * (2 * pos - 1)).sum() / max(v.sum(), 1)) if len(v) else 0.0
    unter = int((cl[k:kl + 1] < w).sum())
    rec = next((j - k for j in range(k, min(k + H, n)) if cl[j] > w), -1)
    events.append({"bar": float(k), "wall": w, "exc_pct": exc,
                   "vol_low_ratio": float(vo[kl] / (mu or 1)),
                   "vol_h2_h1": h2h1, "vol_peak_pos": peaki, "delta_norm": dnorm,
                   "quote_unter": unter / max(len(v), 1), "vol_slope": slope,
                   "reclaim_bars": float(rec), "vol_cv": sd / (mu or 1)})
    kl = k

print(f"Detektierte frische Bodenbraeuche (H={H}): {len(events)}")
sig = [e for e in events if e["exc_pct"] >= 0.25]
print(f"davon mit Exkursion >= 0.25%: {len(sig)}")

print("\n" + "=" * 118)
print(f"GRUNDGESAMTHEIT (n={len(sig)}, Exkursion >= 0.25%)  |  Perzentile je Merkmal")
print("=" * 118)
print(f"{'Merkmal':<14} {'p05':>9} {'p25':>9} {'p50':>9} {'p75':>9} {'p95':>9} {'min':>9} {'max':>9}")
Pct: Dict[str, np.ndarray] = {}
for m in MERKM:
    a = np.array([e[m] for e in sig], dtype=float)
    Pct[m] = a
    print(f"{m:<14} {np.percentile(a,5):>9.4f} {np.percentile(a,25):>9.4f} "
          f"{np.percentile(a,50):>9.4f} {np.percentile(a,75):>9.4f} "
          f"{np.percentile(a,95):>9.4f} {a.min():>9.4f} {a.max():>9.4f}")

TARGETS = {
    "A": dict(k=836, kl=858, wall=64.2680),
    "B_f": dict(k=1078, kl=1133, wall=64.7980),
    "B_l": dict(k=1106, kl=1133, wall=63.1560),
    "C": dict(k=1820, kl=1820, wall=67.6000),
    "D": dict(k=1972, kl=2040, wall=66.4140),
}


def feats_of(k0: int, kl0: int, wall: float) -> Dict[str, float]:
    """Merkmale eines konkreten Ereignisses (Anker vorgegeben, H wie oben)."""
    kl = k0
    for j in range(k0, min(k0 + H, n)):
        if lo[j] < lo[kl]:
            kl = j
    v = vo[k0:kl + 1]; mu = float(v.mean()) if len(v) else 1.0
    sd = float(v.std()) if len(v) else 0.0
    x = np.arange(len(v), dtype=float)
    slope = float(np.polyfit(x, v, 1)[0]) / (mu or 1) if len(v) > 2 else 0.0
    half = max(len(v) // 2, 1)
    h2h1 = float(v[half:].mean() / (v[:half].mean() or 1)) if len(v) else 1.0
    peaki = float(np.argmax(v) / max(len(v) - 1, 1)) if len(v) else 0.0
    rng = hi[k0:kl + 1] - lo[k0:kl + 1]
    pos = np.where(rng > 0, (cl[k0:kl + 1] - lo[k0:kl + 1]) / np.where(rng > 0, rng, 1), 0.5)
    dnorm = float((v * (2 * pos - 1)).sum() / max(v.sum(), 1)) if len(v) else 0.0
    unter = int((cl[k0:kl + 1] < wall).sum())
    rec = next((j - k0 for j in range(k0, min(k0 + H, n)) if cl[j] > wall), -1)
    return {"exc_pct": (wall - lo[kl]) / wall * 100,
            "vol_low_ratio": float(vo[kl] / (mu or 1)), "vol_h2_h1": h2h1,
            "vol_peak_pos": peaki, "delta_norm": dnorm,
            "quote_unter": unter / max(len(v), 1), "vol_slope": slope,
            "reclaim_bars": float(rec), "vol_cv": sd / (mu or 1)}


print("\n" + "=" * 118)
print("EINORDNUNG A / B / C / D IN DER GRUNDGESAMTHEIT  (Perzentil, 0=niedrigster)")
print("=" * 118)
FT = {lab: feats_of(int(t["k"]), int(t["kl"]), float(t["wall"])) for lab, t in TARGETS.items()}
print(f"{'Merkmal':<14} " + " ".join(f"{l:>10}" for l in TARGETS))
for m in MERKM:
    a = Pct[m]
    cells = []
    for lab in TARGETS:
        p = float((a < FT[lab][m]).mean() * 100)
        cells.append(f"{p:>9.0f}%")
    print(f"{m:<14} " + " ".join(cells))

print("\n" + "=" * 118)
print("TRENNSCHAERFE GEGEN DIE POPULATION  (liegt A ausserhalb des 5-95%-Kerns?)")
print("=" * 118)
print(f"{'Merkmal':<14} {'A-Wert':>10} {'p05':>9} {'p95':>9}  A-Lage")
for m in MERKM:
    a = Pct[m]
    av = FT["A"][m]
    p05, p95 = np.percentile(a, 5), np.percentile(a, 95)
    lage = ("AUSSERHALB unten" if av < p05 else
            "AUSSERHALB oben" if av > p95 else "im 5-95-Kern")
    print(f"{m:<14} {av:>10.4f} {p05:>9.4f} {p95:>9.4f}  {lage}")

print("\n" + "=" * 118)
print("GEGENPROBE: liegen B/C/D im selben Bereich wie A? (Nur dann ist A NICHT")
print("allein durch dieses Merkmal von den uebrigen Ausreissern zu trennen.)")
print("=" * 118)
for m in MERKM:
    a = Pct[m]
    row = []
    for lab in ["B_f", "B_l", "C", "D"]:
        pb = float((a < FT[lab][m]).mean() * 100)
        pa = float((a < FT["A"][m]).mean() * 100)
        row.append(f"{lab}={pb:.0f}%(A={pa:.0f}%)")
    print(f"  {m:<14} " + "  ".join(row))
