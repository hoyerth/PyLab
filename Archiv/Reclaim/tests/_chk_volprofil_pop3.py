# -*- coding: utf-8 -*-
"""READ-ONLY Populations-Studie v3 (vektorisiert, NUR AUGUST 2026).

Auflage: Datenfenster ausschliesslich AUG26 = 2026-08-03 .. 2026-09-01.
S1/S2 werden nicht geladen (nur auf ausdrueckliche Anweisung).

Gegenueber v2:
  * FLOOR vollstaendig vektorisiert (Prefix-Max je Kante) -> Sekunden statt Minuten.
  * Ziel-Ereignisse aus der Population ausgeschlossen (kein Selbstbezug).
  * Konditionale Analyse: nur vergleichbare Ereignisse (Exkursion >= 1%).
  * Endgueltiges Trenn-Verdikt je Merkmal.
  * D (01.09. 10:00) liegt AUSSERHALB des August-Fensters: eigene kleine
    EXT-Auswertung nur fuer die Merkmalszeile (keine Populations-Perzentile).

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
_s = importlib.util.spec_from_file_location("epop3", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["epop3"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
WIN = ("2026-08-03", "2026-09-01")          # AUG26 (nur August)
engine.FENSTER["POP"] = WIN  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("POP", cfg)  # type: ignore[arg-type]
n = int(scan["n"]); d = scan["d"]; ts = list(d["ts"])
op = d["open"].to_numpy(float); hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float); cl = d["close"].to_numpy(float)
vo = d["tick_volume"].to_numpy(float)
EDGES = list(scan["edges"]); LIVE = int(cfg.wall_live_bars)
tsd = np.array(ts, dtype="datetime64[ns]")
bars = np.arange(n, dtype=np.int64)
print(f"Fenster {WIN}: n={n}, edges={len(EDGES)}, "
      f"[{ts[0]} .. {ts[-1]}]")

# ---------------- FLOOR vektorisiert ----------------
FLOOR = np.full(n, np.inf)
for e in EDGES:
    if e.seite != "UNTEN":
        continue
    wb = np.array([int(b) for b, _ in e.wicks], dtype=np.int64)
    wp = np.array([float(p) for _, p in e.wicks], dtype=float)
    o_ = np.argsort(wb)
    wb, wp = wb[o_], wp[o_]
    pmax = np.maximum.accumulate(wp)
    idx = np.searchsorted(wb, bars, side="right") - 1
    alive = (idx >= 0) & (wb[np.clip(idx, 0, None)] >= bars - LIVE)
    if e.ist_prim_anker:
        bas = np.full(n, float(e.basis))
    else:
        j = np.searchsorted(wb, bars - 2, side="right")
        bas = np.where(j > 0, pmax[np.clip(j - 1, 0, None)], wp[0])
    FLOOR = np.where(alive & (bas < FLOOR), bas, FLOOR)
FLOOR = np.where(np.isfinite(FLOOR), FLOOR, np.nan)

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
    h2h1 = (float(v[half:].mean() / v[:half].mean())
            if len(v) >= 2 and v[:half].mean() > 0 else 1.0)
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


# ---------------- Population (August) ----------------
TARGETS = {
    "A":   ("2026-08-14T02:30", 64.2680),
    "B_f": ("2026-08-18T16:30", 64.7980),
    "B_l": ("2026-08-19T00:30", 63.1560),
    "C":   ("2026-08-28T18:00", 67.6000),
}
tgt_bars = {lab: int(np.searchsorted(tsd, np.datetime64(t))) for lab, (t, _) in TARGETS.items()}
FT = {lab: feats(tgt_bars[lab], w) for lab, (t, w) in TARGETS.items()}

# D liegt ausserhalb August -> nur Merkmalszeile aus dem freigegebenen EXT-Scan
_s2 = importlib.util.spec_from_file_location("epop3b", EP)
e2 = importlib.util.module_from_spec(_s2)
sys.modules["epop3b"] = e2
_s2.loader.exec_module(e2)  # type: ignore[union-attr]
e2.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
sc2 = e2._se_scan("EXT", cfg)  # type: ignore[arg-type]
d2 = sc2["d"]; ts2 = np.array(list(d2["ts"]), dtype="datetime64[ns]")
lo2 = d2["low"].to_numpy(float)
vo2 = d2["tick_volume"].to_numpy(float)
hi2 = d2["high"].to_numpy(float); cl2 = d2["close"].to_numpy(float)
kD = int(np.searchsorted(ts2, np.datetime64("2026-09-01T10:00")))
kL = kD
for j in range(kD, min(kD + H, len(lo2))):
    if lo2[j] < lo2[kL]:
        kL = j
vD = vo2[kD:kL + 1]
muD = float(vD.mean()); halfD = max(len(vD) // 2, 1)
rngD = hi2[kD:kL + 1] - lo2[kD:kL + 1]
posD = np.where(rngD > 0, (cl2[kD:kL + 1] - lo2[kD:kL + 1]) / np.where(rngD > 0, rngD, 1), 0.5)
FT["D"] = {
    "exc_pct": (66.4140 - lo2[kL]) / 66.4140 * 100,
    "vol_low_ratio": float(vo2[kL] / (muD or 1)),
    "vol_h2_h1": float(vD[halfD:].mean() / (vD[:halfD].mean() or 1)),
    "vol_peak_pos": float(np.argmax(vD) / max(len(vD) - 1, 1)),
    "delta_norm": float((vD * (2 * posD - 1)).sum() / max(vD.sum(), 1)),
    "quote_unter": float((cl2[kD:kL + 1] < 66.4140).mean()),
    "vol_slope": float(np.polyfit(np.arange(len(vD), dtype=float), vD, 1)[0]) / (muD or 1),
    "reclaim_bars": -1.0,
    "vol_cv": float(vD.std() / (muD or 1)),
}

events: List[Dict[str, float]] = []
for k in range(3, n - H):
    w = FLOOR[k - 1]
    if not np.isfinite(w) or not (lo[k] < w):
        continue
    if np.isfinite(FLOOR[k - 2]) and lo[k - 1] < FLOOR[k - 2]:
        continue
    f = feats(k, float(w)); f["bar"] = float(k)
    events.append(f)

tbar = set(tgt_bars.values())
pop_all = [e for e in events if e["exc_pct"] >= 0.25]
pop_clean = [e for e in pop_all if int(e["bar"]) not in tbar]
pop_comp = [e for e in pop_clean if e["exc_pct"] >= 1.0]
print(f"Ereignisse gesamt: {len(events)}  |  >=0.25%: {len(pop_all)}  |  "
      f"ohne Ziele: {len(pop_clean)}  |  vergleichbar (exc>=1%): {len(pop_comp)}")

print("\n" + "=" * 116)
print(f"GRUNDGESAMTHEIT ohne Ziel-Ereignisse (n={len(pop_clean)})")
print("=" * 116)
print(f"{'Merkmal':<14} {'p05':>9} {'p25':>9} {'p50':>9} {'p75':>9} {'p95':>9}")
P = {m: np.array([e[m] for e in pop_clean], dtype=float) for m in MERKM}
for m in MERKM:
    a = P[m]
    print(f"{m:<14} {np.percentile(a,5):>9.4f} {np.percentile(a,25):>9.4f} "
          f"{np.percentile(a,50):>9.4f} {np.percentile(a,75):>9.4f} {np.percentile(a,95):>9.4f}")

print("\n" + "=" * 116)
print("ZIEL-EREIGNISSE + PERZENTIL IN DER BEREINIGTEN POPULATION")
print("=" * 116)
print(f"{'Merkmal':<14} " + " ".join(f"{l:>12}" for l in TARGETS))
for m in MERKM:
    a = P[m]
    print(f"{m:<14} " + " ".join(
        f"{FT[l][m]:>7.4f}({float((a<FT[l][m]).mean()*100):>3.0f}%)" for l in TARGETS))

print("\n" + "=" * 116)
print("VERDIKT: Trennt das Merkmal A von der Population UND von B/C/D?")
print("=" * 116)
PC = {m: np.array([e[m] for e in pop_comp], dtype=float) for m in MERKM}
print(f"Referenz-Population fuer 'vergleichbar': exc>=1% (n={len(pop_comp)})")
print(f"{'Merkmal':<14} {'A':>9} {'p05':>8} {'p95':>8} {'A-Lage':<15} "
      f"{'B/C/D gleich?':>14}")
for m in MERKM:
    a = PC[m]
    av = FT["A"][m]
    p05, p95 = np.percentile(a, 5), np.percentile(a, 95)
    lage = "unten-AUSR" if av < p05 else ("oben-AUSR" if av > p95 else "Kern")
    same = 0
    for lab in ["B_f", "B_l", "C", "D"]:
        vv = FT[lab][m]
        if (vv < p05) == (av < p05) and (vv > p95) == (av > p95):
            same += 1
    verdict = "TRENNT" if (lage != "Kern" and same <= 1) else (
        "moeglich" if lage != "Kern" and same <= 2 else "NEIN")
    print(f"{m:<14} {av:>9.4f} {p05:>8.4f} {p95:>8.4f} {lage:<15} "
          f"{same}/4          {verdict}")

print(f"\nKONDITIONAL: nur Ereignisse mit Exkursion >= 1% (n={len(pop_comp)})")
print(f"{'Merkmal':<14} {'p25':>9} {'p50':>9} {'p75':>9}  Verteilung")
for m in ["reclaim_bars", "vol_slope", "vol_h2_h1", "vol_peak_pos", "delta_norm", "vol_cv"]:
    a = PC[m]
    print(f"{m:<14} {np.percentile(a,25):>9.4f} {np.percentile(a,50):>9.4f} "
          f"{np.percentile(a,75):>9.4f}")

print("\n" + "=" * 116)
print("WIE VIELE VERGLEICHBARE AUSBRUECHE VERHALTEN SICH WIE A?")
print("=" * 116)
mode = ((PC["exc_pct"] >= 0.8) & (PC["exc_pct"] <= 1.8) &
        (PC["reclaim_bars"] >= 10) & (PC["vol_h2_h1"] <= 0.9))
print(f"  exc in [0.8,1.8]%  UND  reclaim>=10 Bars  UND  vol_h2_h1<=0.9 :"
      f"  {int(mode.sum())} von {len(pop_comp)}")
for lab in ["B_f", "B_l", "C", "D"]:
    f = FT[lab]
    ok = (0.8 <= f["exc_pct"] <= 1.8) and f["reclaim_bars"] >= 10 and f["vol_h2_h1"] <= 0.9
    print(f"    {lab}: exc={f['exc_pct']:.2f} reclaim={f['reclaim_bars']:.0f} "
          f"h2h1={f['vol_h2_h1']:.2f}  -> {'wie A' if ok else 'anders'}")
