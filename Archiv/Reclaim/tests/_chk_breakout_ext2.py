# -*- coding: utf-8 -*-
"""READ-ONLY Ausreisser-Analyse September, LEG-BASIERT (Korrektur des
open->low-Artefakts: C wird von einer Rally dominiert).

Je Fenster wird das relevante Abwaerts-Leg isoliert (Swing-Hoch -> Tief)
und die gebrochene Wand am Bar VOR dem Leg-Hoch verankert.

Zusaetzlich: Kissen/Vakuum (Korridor edges-only, Radius 0.30 %, Liveness
<= 96, Selbstkanten-Ausschluss geburt > low-2).

Kein Patch. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("eleg", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["eleg"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
d = scan["d"]
ts = list(d["ts"])
o = d["open"].to_numpy(float); h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float); c = d["close"].to_numpy(float)
v = d["tick_volume"].to_numpy(float)
EDGES = list(scan["edges"])
LIVE = int(cfg.wall_live_bars)

prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
pdm = np.where((up > dn) & (up > 0), up, 0.0)
mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
pdi = 100 * pd.Series(pdm).ewm(alpha=1 / 14, adjust=False).mean().to_numpy() / atr
mdi = 100 * pd.Series(mdm).ewm(alpha=1 / 14, adjust=False).mean().to_numpy() / atr
dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
adx = pd.Series(dx).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
r1 = np.concatenate([[0.0], np.diff(np.log(c))])


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def basis(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def un_lebend(k: int) -> List[Tuple[int, float, int]]:
    """Lebende UNTEN-Kanten bei k (edges-only): (kid, basis(k), geburt)."""
    out = []
    for e in EDGES:
        if e.seite != "UNTEN":  # type: ignore[attr-defined]
            continue
        if int(e.geburts_bar) <= k and lebt(e, k):  # type: ignore[attr-defined]
            out.append((int(e.kid), basis(e, k), int(e.geburts_bar)))  # type: ignore[attr-defined]
    return sorted(out, key=lambda t: t[1])


W = {
    "A 14.08. 02:00-09:00": (836, 864),
    "C 28.08. 08:00-18:00": (1780, 1820),
    "D 01.09. 10:00-02.09. 16:00": (1972, 2088),
    "E 10.09. 08:00-11.09. 15:00": (2598, 2718),
}

print("=" * 130)
print("LEG-BASIERTE AUSREISSER-ANALYSE  |  A (Referenz) vs C/D/E  (Swing-Hoch -> Tief)")
print("=" * 130)
KERN: Dict[str, Dict[str, float]] = {}
for lab, (k0, k1) in W.items():
    kh = k0 + int(np.argmax(h[k0:k1 + 1]))          # Leg-Hoch
    kl = kh + int(np.argmin(l[kh:k1 + 1]))          # Leg-Tief nach Hoch
    drop = (h[kh] - l[kl]) / h[kh] * 100
    bars = kl - kh
    hours = max(bars, 1) * 0.25
    wall = None
    un_hoch = un_lebend(kh - 1)
    if un_hoch:
        wall = un_hoch[0][1]
    wall = wall if wall is not None else o[k0]
    # Akzeptanz unter der Wand (im Leg + danach bis k1)
    below = [k for k in range(kh, k1 + 1) if c[k] < wall]
    streak = best = 0
    for k in range(kh, k1 + 1):
        streak = streak + 1 if c[k] < wall else 0
        best = max(best, streak)
    # Kreuzende + Kissen-Kanten
    unten_kh = un_lebend(kh - 1)
    gekreuzt = [(kid, b, gb) for kid, b, gb in un_lebend(kl) if l[kl] < b < wall]
    kissen = [(kid, b, gb) for kid, b, gb in un_lebend(kl)
              if b <= l[kl] * 1.003 and gb <= kl - 2]
    naechste = max([b for _, b, _ in un_lebend(kl) if b <= l[kl]], default=None)
    vakuum_pct = (l[kl] - naechste) / l[kl] * 100 if naechste is not None else None
    # Ruecklauf
    retr = {}
    for frac in (0.25, 0.5, 0.75, 1.0):
        ziel = l[kl] + (h[kh] - l[kl]) * frac
        hit = next((k for k in range(kl, k1 + 1) if c[k] >= ziel), None)
        retr[frac] = (0 if hit == kl else (hit - kl + 1)) if hit is not None else None
    seg_r = r1[kh:kl + 1]
    KERN[lab] = {
        "kh": kh, "kl": kl, "h": h[kh], "low": l[kl], "drop_pct": drop,
        "bars": bars, "stunden": hours, "speed_pct_h": drop / hours,
        "atr_h": atr[kh], "atr_l": atr[kl], "drop_atr": (h[kh] - l[kl]) / atr[kh],
        "adx_h": adx[kh], "adx_l": adx[kl], "adx_max": adx[kh:kl + 1].max(),
        "mdi_h": mdi[kh], "mdi_l": mdi[kl], "pdi_h": pdi[kh],
        "wall": wall, "below": len(below), "tot": k1 - kh + 1, "serie": best,
        "vol_bp": float(np.std(seg_r) * 1e4),
        "pre_vol_bp": float(np.std(r1[max(0, kh - 96):kh]) * 1e4),
        "worst_bar": float(np.min(l[kh:kl + 1] / np.concatenate([[o[kh]], c[kh:kl]]) - 1) * 100),
        "big_body": float(np.max(np.abs(c[kh:kl + 1] - o[kh:kl + 1]) / o[kh:kl + 1]) * 100),
        "retr25": retr[0.25], "retr50": retr[0.5], "retr75": retr[0.75], "retr100": retr[1.0],
        "gekreuzt": gekreuzt, "kissen": kissen, "vakuum_pct": vakuum_pct,
        "un_hoch": un_hoch,
    }

print(f"\n{'Kennzahl':<26} " + " ".join(f"{x:>16}" for x in ["A", "C", "D", "E"]))
for key, fmt in [
    ("kh", "{:.0f}"), ("kl", "{:.0f}"), ("h", "{:.4f}"), ("low", "{:.4f}"),
    ("drop_pct", "{:.3f}"), ("bars", "{:.0f}"), ("stunden", "{:.2f}"),
    ("speed_pct_h", "{:.4f}"), ("atr_h", "{:.4f}"), ("atr_l", "{:.4f}"),
    ("drop_atr", "{:.2f}"), ("adx_h", "{:.2f}"), ("adx_l", "{:.2f}"),
    ("adx_max", "{:.2f}"), ("mdi_h", "{:.2f}"), ("mdi_l", "{:.2f}"),
    ("pdi_h", "{:.2f}"), ("wall", "{:.4f}"), ("below", "{:.0f}"),
    ("tot", "{:.0f}"), ("serie", "{:.0f}"), ("vol_bp", "{:.1f}"),
    ("pre_vol_bp", "{:.1f}"), ("worst_bar", "{:.3f}"), ("big_body", "{:.3f}"),
    ("retr25", "{}"), ("retr50", "{}"), ("retr75", "{}"), ("retr100", "{}"),
    ("vakuum_pct", "{}"),
]:
    cells = []
    for lab in W:
        vv = KERN[lab][key]
        cells.append("-" if vv is None else (fmt.format(vv) if fmt != "{}" else str(vv)))
    print(f"{key:<26} " + " ".join(f"{x:>16}" for x in cells))

for lab in W:
    K = KERN[lab]
    print("\n" + "-" * 130)
    print(f"{lab}   Leg-Hoch Bar {K['kh']} ({ts[K['kh']]}) = {K['h']:.4f}   ->   "
          f"Leg-Tief Bar {K['kl']} ({ts[K['kl']]}) = {K['low']:.4f}")
    print(f"  Wand (Korridor-Boden @ Bar {K['kh']-1}): {K['wall']:.4f}")
    print("  lebende UNTEN bei Leg-Hoch-1: "
          + ", ".join(f"K{kid}@{b:.4f}(g{gb})" for kid, b, gb in K["un_hoch"]))
    print(f"  gekreuzte lebende UNTEN (Wand > b > Tief): "
          + (", ".join(f"K{kid}@{b:.4f}(g{gb})" for kid, b, gb in K["gekreuzt"]) or "keine"))
    print(f"  Kissen an/unter Tief (b <= Tief*1.003, gb<=kl-2): "
          + (", ".join(f"K{kid}@{b:.4f}(g{gb})" for kid, b, gb in K["kissen"]) or "KEINE => VAKUUM"))
    print(f"  Abstand Tief -> naechste lebende UNTEN darunter: "
          + (f"{K['vakuum_pct']:+.3f}%" if K["vakuum_pct"] is not None else "keine Kante darunter => freier Fall"))

# ---------------------------------------------- Leg-Profil (Viertel des Legs)
print("\n" + "=" * 130)
print("LEG-PROFIL (Viertel des Abwaerts-Legs): Struktur eines einzelnen Impulses vs. Trend")
print("=" * 130)
for lab in W:
    K = KERN[lab]
    kh, kl = K["kh"], K["kl"]
    q = max(1, (kl - kh) // 4)
    print(f"\n{lab}:  Leg {kh}..{kl} ({kl-kh} Bars)")
    for i in range(4):
        a = kh + i * q
        b = kl if i == 3 else min(kl, kh + (i + 1) * q - 1)
        print(f"   Q{i+1} {a}..{b}: close {c[a]:.4f}->{c[b]:.4f} ({c[b]-c[a]:+.4f})  "
              f"tief={l[a:b+1].min():.4f}  ATR {atr[a]:.4f}->{atr[b]:.4f}  "
              f"ADX {adx[a]:.1f}->{adx[b]:.1f}  -DI {mdi[a]:.1f}->{mdi[b]:.1f}")
    # Anzahl nennenswerter Abwaerts-Impulse (> 0.5 ATR)
    imp = 0
    k = kh
    while k < kl:
        lo_i = l[k]
        k2 = k
        while k2 < kl and c[k2 + 1] <= c[k2] * 1.0005:
            k2 += 1
        if (h[k] - l[k2:kl + 1].min() if k2 < kl else 0) > 0.5 * atr[k]:
            imp += 1
        k = k2 + 1
    print(f"   ADX-Verlauf: " + " ".join(f"{adx[k]:.0f}" for k in range(kh, kl + 1, max(1, (kl-kh)//10))))
    print(f"   ATR-Verlauf: " + " ".join(f"{atr[k]:.3f}" for k in range(kh, kl + 1, max(1, (kl-kh)//10))))
