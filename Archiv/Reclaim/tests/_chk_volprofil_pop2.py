# -*- coding: utf-8 -*-
"""READ-ONLY Populations-Studie v2: alle Bodenbraeuche 2026, Einordnung A/B/C/D.

Korrekturen gegenueber v1:
  * Zielereignisse werden ueber ihren BKZ-ZEITSTEMPEL lokalisiert (nicht ueber
    Bar-Indizes, die nur im EXT-Fenster gelten).
  * Boden-Berechnung beschleunigt (Prefix-Max pro Kante) -> Laufzeit ~Sekunden.

Ansonsten identisch: 301+ frische Bodenbraeuche, Merkmale, Perzentil-Lage.

Kein Patch. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("epop2", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["epop2"] = engine
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
tsd = np.array(ts, dtype="datetime64[ns]")
print(f"Fenster {WIN}: n={n}, edges={len(EDGES)}")

# --- Kanten vorbereiten: prefix min/max fuer O(1)-Basis ---
KANTEN: List[Dict] = []
for e in EDGES:
    if e.seite != "UNTEN":
        continue
    wb = np.array([int(b) for b, _ in e.wicks], dtype=np.int64)
    wp = np.array([float(p) for _, p in e.wicks], dtype=float)
    order = np.argsort(wb)
    wb, wp = wb[order], wp[order]
    KANTEN.append({
        "wb": wb, "wp": wp,
        "pmax": np.maximum.accumulate(wp),          # UNTEN: basis = max(px)
        "anker": bool(e.ist_prim_anker), "basis": float(e.basis),
    })


def floor_at(k: int) -> Optional[float]:
    best: Optional[float] = None
    for c in KANTEN:
        wb = c["wb"]
        i = int(np.searchsorted(wb, k, side="right")) - 1
        if i < 0 or wb[i] < k - LIVE:
            continue
        if c["anker"]:
            b = c["basis"]
        else:
            j = int(np.searchsorted(wb, k - 2, side="right"))
            b = float(c["pmax"][j - 1]) if j > 0 else float(c["wp"][0])
        if best is None or b < best:
            best = b
    return best


FLOOR = [floor_at(k) for k in range(n)]


def bar_von(bkz: str) -> int:
    """Bar-Index im POP-Fenster aus BKZ-Zeitstempel (searchsorted, Kanon)."""
    return int(np.searchsorted(tsd, np.datetime64(bkz)))


H = 24
MERKM = ["exc_pct", "vol_low_ratio", "vol_h2_h1", "vol_peak_pos", "delta_norm",
         "quote_unter", "vol_slope", "reclaim_bars", "vol_cv"]


def feats(k0: int, wall: float) -> Dict[str, float]:
    kl = k0
    for j in range(k0, min(k0 + H, n)):
        if lo[j] < lo[kl]:
            kl = j
    v = vo[k0:kl + 1]
    mu = float(v.mean()) if len(v) else 1.0
    sd = float(v.std()) if len(v) else 0.0
    half = max(len(v) // 2, 1)
    h2h1 = float(v[half:].mean() / (v[:half].mean() or 1)) if len(v) >= 2 and v[:half].mean() > 0 else 1.0
    x = np.arange(len(v), dtype=float)
    slope = float(np.polyfit(x, v, 1)[0]) / (mu or 1) if len(v) > 2 else 0.0
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


# --- Population detektieren ---
events: List[Dict[str, float]] = []
for k in range(3, n - H):
    w = FLOOR[k - 1]
    if w is None or not (lo[k] < w):
        continue
    if FLOOR[k - 2] is not None and lo[k - 1] < FLOOR[k - 2]:
        continue                              # Folgebar, kein frischer Bruch
    f = feats(k, w)
    f["bar"] = float(k)
    events.append(f)
sig = [e for e in events if e["exc_pct"] >= 0.25]
print(f"frische Bodenbraeuche: {len(events)}   mit Exkursion >= 0.25%: {len(sig)}")

Pct = {m: np.array([e[m] for e in sig], dtype=float) for m in MERKM}
print("\n" + "=" * 116)
print(f"GRUNDGESAMTHEIT (n={len(sig)})  |  Perzentile")
print("=" * 116)
print(f"{'Merkmal':<14} {'p05':>9} {'p25':>9} {'p50':>9} {'p75':>9} {'p95':>9} {'min':>9} {'max':>9}")
for m in MERKM:
    a = Pct[m]
    print(f"{m:<14} {np.percentile(a,5):>9.4f} {np.percentile(a,25):>9.4f} "
          f"{np.percentile(a,50):>9.4f} {np.percentile(a,75):>9.4f} "
          f"{np.percentile(a,95):>9.4f} {a.min():>9.4f} {a.max():>9.4f}")

# --- Ziele ueber Zeitstempel ---
TARGETS = {
    "A":   ("2026-08-14T02:30", 64.2680),
    "B_f": ("2026-08-18T16:30", 64.7980),
    "B_l": ("2026-08-19T00:30", 63.1560),
    "C":   ("2026-08-28T18:00", 67.6000),
    "D":   ("2026-09-01T10:00", 66.4140),
}
FT: Dict[str, Dict[str, float]] = {}
print("\n" + "=" * 116)
print("ZIEL-EREIGNISSE (Zeitstempel -> POP-Bar)")
print("=" * 116)
for lab, (t, w) in TARGETS.items():
    k = bar_von(t)
    FT[lab] = feats(k, w)
    print(f"  {lab:<4} {t}  POP-Bar {k:>6}  ({ts[k]})  Wand {w:.4f}  "
          f"exc={FT[lab]['exc_pct']:.3f}%")

print("\n" + "=" * 116)
print("EINORDNUNG IN DER GRUNDGESAMTHEIT  (Perzentil, 0 = niedrigster Wert)")
print("=" * 116)
print(f"{'Merkmal':<14} " + " ".join(f"{l:>10}" for l in TARGETS))
for m in MERKM:
    a = Pct[m]
    print(f"{m:<14} " + " ".join(
        f"{float((a < FT[l][m]).mean()*100):>9.0f}%" for l in TARGETS))

print("\n" + "=" * 116)
print("A GEGEN DIE POPULATION: liegt A ausserhalb des 5-95%-Kerns?")
print("=" * 116)
for m in MERKM:
    a = Pct[m]
    av = FT["A"][m]
    p05, p95 = np.percentile(a, 5), np.percentile(a, 95)
    lage = ("AUSSERHALB unten" if av < p05 else
            "AUSSERHALB oben" if av > p95 else "im 5-95-Kern")
    ok = "POTENZIELL TRENNEND" if lage != "im 5-95-Kern" else "-"
    print(f"{m:<14} A={av:>9.4f}  p05={p05:>9.4f} p95={p95:>9.4f}  {lage:<16} {ok}")

print("\n" + "=" * 116)
print("KERN-FRAGE: Kann ein Merkmal A gegen B/C/D trennen UND A von der Population?")
print("=" * 116)
for m in MERKM:
    a = Pct[m]
    pa = float((a < FT["A"][m]).mean() * 100)
    p05, p95 = np.percentile(a, 5), np.percentile(a, 95)
    a_ext = FT["A"][m] < p05 or FT["A"][m] > p95
    # liegen alle anderen im selben Aussenbereich?
    same = 0
    for lab in ["B_f", "B_l", "C", "D"]:
        vv = FT[lab][m]
        if (vv < p05) == (FT["A"][m] < p05) and (vv > p95) == (FT["A"][m] > p95):
            same += 1
    print(f"  {m:<14} A-Perzentil={pa:>4.0f}%  A_ausserhalb={str(a_ext):<5}  "
          f"B/C/D im selben Aussenbereich: {same}/4")
