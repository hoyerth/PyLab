# -*- coding: utf-8 -*-
"""READ-ONLY Ausreisser-Analyse September: C, D, E vs. Referenz A (echte
Expansion innerhalb einer Balance).

Aufbau:
  Teil 1  Finanzmathematik-Matrix (identische Dimensionen wie
          _chk_breakout_math.py: A/B) fuer A, C, D, E.
  Teil 2  Struktur je Fenster: gebrochene Wand, Akzeptanz, Tief, Ruecklauf,
          ADX-/ATR-Pfad, Kissen/Vakuum (Korridor strikt edges-only,
          Kissen-Radius 0.30 %, Liveness <= 96 Bars).

Kein Patch an Engine/Adapter/Renderer. Engine-SHA hart geprueft.
Fenster-Erweiterung via Laufzeit-Injektion (SHA unveraendert).
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
sys.path.insert(0, str(ROOT / "test"))
ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SHA = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
assert hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == SHA

_s = importlib.util.spec_from_file_location("eext", ENGINE_P)
engine = importlib.util.module_from_spec(_s)
sys.modules["eext"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("EXT", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
d = scan["d"]
ts = list(d["ts"])
o = d["open"].to_numpy(float)
h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float)
c = d["close"].to_numpy(float)
v = d["tick_volume"].to_numpy(float)
EDGES = list(scan["edges"])
LIVE = int(cfg.wall_live_bars)

# ------------------------------------------------------------------ Indikatoren
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
up = np.diff(h, prepend=h[0])
dn = -np.diff(l, prepend=l[0])
pdm = np.where((up > dn) & (up > 0), up, 0.0)
mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
pdi = 100 * pd.Series(pdm).ewm(alpha=1 / 14, adjust=False).mean().to_numpy() / atr
mdi = 100 * pd.Series(mdm).ewm(alpha=1 / 14, adjust=False).mean().to_numpy() / atr
dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
adx = pd.Series(dx).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
r1 = np.concatenate([[0.0], np.diff(np.log(c))])

W = {
    "A 14.08. 02:00-09:00": (836, 864),
    "C 28.08. 08:00-18:00": (1780, 1820),
    "D 01.09. 10:00-02.09. 16:00": (1972, 2088),
    "E 10.09. 08:00-11.09. 15:00": (2598, 2718),
}
BASE = 96


# ============================================================== KORRIDOR (edges)
def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def basis(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def korridor_boden(k: int) -> Tuple[Optional[float], List[Tuple[int, float]]]:
    """Tiefste lebende UNTEN-Kante (edges-only) + Liste aller lebenden UNTEN."""
    un = [(int(e.kid), basis(e, k)) for e in EDGES
          if int(e.geburts_bar) <= k and lebt(e, k) and e.seite == "UNTEN"]  # type: ignore[attr-defined]
    if not un:
        return None, []
    un.sort(key=lambda t: t[1])
    return un[0][1], un


def kissen_ab(k: int, extrem: float, band_pct: float = 0.30) -> List[Tuple[int, float, int]]:
    """Lebende UNTEN-Vorkanten (geburt <= k-2) in/unter dem Extrem (0.30 %)."""
    out = []
    for e in EDGES:
        if int(e.geburts_bar) > k - 2 or not lebt(e, k):  # type: ignore[attr-defined]
            continue
        if e.seite != "UNTEN":  # type: ignore[attr-defined]
            continue
        b = basis(e, k)
        if b <= extrem * (1.0 + band_pct / 100.0):
            out.append((int(e.kid), b, int(e.geburts_bar)))  # type: ignore[attr-defined]
    return out


# ======================================================= TEIL 1 Finanzmathematik
def blk(k0: int, k1: int) -> Dict[str, float]:
    """Kennzahlen eines Fensters [k0, k1] inkl. 96-Bar-Vorlauf."""
    seg_o, seg_h, seg_l, seg_c = o[k0:k1 + 1], h[k0:k1 + 1], l[k0:k1 + 1], c[k0:k1 + 1]
    seg_v = v[k0:k1 + 1]
    m = len(seg_c)
    hi, lo_, cl_last, op_first = seg_h.max(), seg_l.min(), seg_c[-1], seg_o[0]
    net = cl_last - op_first
    exc = op_first - lo_
    hours = m * 0.25
    tief_i = int(seg_l.argmin())
    retr = (cl_last - lo_) / (op_first - lo_) if op_first > lo_ else float("nan")
    p0 = max(0, k0 - BASE)
    pre_h, pre_l, pre_c = h[p0:k0], l[p0:k0], c[p0:k0]
    pre_net = (pre_c[-1] - pre_c[0]) if len(pre_c) else 0.0
    pre_rng = (pre_h.max() - pre_l.min()) if len(pre_c) else 0.0
    eff = abs(net) / np.abs(np.diff(seg_c)).sum() if m > 1 else float("nan")
    dn_bars = int((np.diff(seg_c) < 0).sum())
    streak = best = 0
    for i in range(1, m):
        streak = streak + 1 if seg_c[i] < seg_c[i - 1] else 0
        best = max(best, streak)
    return {
        "bars": m, "stunden": hours,
        "open": op_first, "high": hi, "low": lo_, "close": cl_last,
        "net_pts": net, "net_pct": net / op_first * 100,
        "exc_pts": exc, "exc_pct": exc / op_first * 100,
        "range_pts": hi - lo_, "range_pct": (hi - lo_) / op_first * 100,
        "speed_net_pct_h": net / op_first * 100 / hours,
        "speed_exc_pct_h": exc / op_first * 100 / hours,
        "atr_start": atr[k0], "atr_end": atr[k1],
        "exc_atr": exc / atr[k0], "range_atr": (hi - lo_) / atr[k0],
        "adx_start": adx[k0], "adx_end": adx[k1], "adx_max": adx[k0:k1 + 1].max(),
        "pdi_start": pdi[k0], "mdi_start": mdi[k0], "mdi_end": mdi[k1],
        "vol_std_bp": float(np.std(r1[k0:k1 + 1]) * 1e4),
        "vol_std_pre_bp": float(np.std(r1[p0:k0]) * 1e4),
        "effizienz": eff, "down_bars": dn_bars, "down_quote": dn_bars / max(m - 1, 1),
        "max_down_streak": best, "tief_bar_rel": tief_i,
        "retrace_nach_tief": retr,
        "close_pos_im_range": (cl_last - lo_) / (hi - lo_) if hi > lo_ else float("nan"),
        "pre_net_pct": pre_net / (pre_c[0] or 1) * 100 if len(pre_c) else 0.0,
        "pre_range_pct": pre_rng / (pre_c[0] or 1) * 100 if len(pre_c) else 0.0,
        "vol_ratio": seg_v.mean() / (v[p0:k0].mean() or 1),
        "worst_bar_pct": float(np.min(seg_l / np.concatenate([[seg_o[0]], seg_c[:-1]]) - 1) * 100),
        "biggest_body_pct": float(np.max(np.abs(seg_c - seg_o) / seg_o) * 100),
    }


print("=" * 132)
print("TEIL 1  FINANZMATHEMATIK  |  A (Referenz, echte Expansion)  vs  C/D (September)")
print("=" * 132)
R = {k: blk(*ab) for k, ab in W.items()}
keys = ["bars", "stunden", "open", "high", "low", "close", "net_pts", "net_pct",
        "exc_pts", "exc_pct", "range_pts", "range_pct", "speed_net_pct_h",
        "speed_exc_pct_h", "atr_start", "atr_end", "exc_atr", "range_atr",
        "adx_start", "adx_end", "adx_max", "pdi_start", "mdi_start", "mdi_end",
        "vol_std_bp", "vol_std_pre_bp", "effizienz", "down_bars", "down_quote",
        "max_down_streak", "tief_bar_rel", "retrace_nach_tief",
        "close_pos_im_range", "pre_net_pct", "pre_range_pct", "vol_ratio",
        "worst_bar_pct", "biggest_body_pct"]
labs = ["A", "C", "D", "E"]
print(f"{'Kennzahl':<22} " + " ".join(f"{x:>15}" for x in labs))
for kk in keys:
    row = " ".join(f"{R[k][kk]:>15.4f}" for k in W)
    print(f"{kk:<22} {row}")

# Monatsbaseline (August) und September-Referenz
aug = blk(BASE, 1931)
sep = blk(1932, n - 1)
print(f"\nBaseline August  (Bars {BASE}..1931) : net={aug['net_pct']:+.2f}% range={aug['range_pct']:.2f}% "
      f"ATR_end={aug['atr_end']:.4f} ADX_end={aug['adx_end']:.2f} vol_bp={aug['vol_std_bp']:.1f}")
print(f"Baseline September(Bars 1932..{n-1}) : net={sep['net_pct']:+.2f}% range={sep['range_pct']:.2f}% "
      f"ATR_end={sep['atr_end']:.4f} ADX_end={sep['adx_end']:.2f} vol_bp={sep['vol_std_bp']:.1f}")

# ============================================================ TEIL 2 Struktur
print("\n" + "=" * 132)
print("TEIL 2  STRUKTUR je Fenster (Korridor edges-only, Kissen-Radius 0.30 %, Liveness <= 96)")
print("=" * 132)
for lab, (k0, k1) in W.items():
    lvl, un = korridor_boden(k0 - 1)
    print("\n" + "-" * 132)
    print(f"{lab}   Bars {k0}..{k1}   [{ts[k0]} .. {ts[k1]}]")
    print("-" * 132)
    print(f"  Korridor-Boden bei Bar {k0-1} ({ts[k0-1]}): "
          + (f"{lvl:.4f}  (lebende UNTEN: " + ", ".join(f"K{kid}@{b:.4f}" for kid, b in un) + ")"
             if lvl is not None else "KEINE lebende UNTEN-Kante"))
    if lvl is None:
        lvl = o[k0]
    # Bruch
    brk_low = next((k for k in range(k0, k1 + 1) if l[k] < lvl), None)
    brk_cl = next((k for k in range(k0, k1 + 1) if c[k] < lvl), None)
    below = [k for k in range(k0, k1 + 1) if c[k] < lvl]
    below_lo = [k for k in range(k0, k1 + 1) if l[k] < lvl]
    streak = best = 0
    lake = None
    for k in range(k0, k1 + 1):
        if c[k] < lvl:
            streak += 1
            if streak > best:
                best, lake = streak, k - streak + 1
        else:
            streak = 0
    lw = int(np.argmin(l[k0:k1 + 1])) + k0
    exc = (lvl - l[lw]) / lvl * 100
    print(f"  Bruch (Low<Wand) Bar {brk_low} ({ts[brk_low] if brk_low else '-'})   "
          f"Bruch (Close<Wand) Bar {brk_cl} ({ts[brk_cl] if brk_cl else '-'})")
    print(f"  Akzeptanz: Closes<Wand {len(below)}/{k1-k0+1} ({len(below)/(k1-k0+1)*100:.0f}%) "
          f"maxSerie={best} ab Bar {lake}   Dochte<Wand {len(below_lo)}/{k1-k0+1}")
    print(f"  Tief Bar {lw} ({ts[lw]}) Low={l[lw]:.4f}  Exkursion unter Wand={exc:.3f}%  "
          f"rel.Pos={lw-k0}/{k1-k0}")
    # Ruecklauf
    for frac in (0.25, 0.5, 0.75, 1.0):
        ziel = l[lw] + (lvl - l[lw]) * frac
        hit = next((k for k in range(lw, k1 + 1) if c[k] >= ziel), None)
        print(f"    Ruecklauf {frac*100:>3.0f}% (Close>={ziel:.4f}): "
              + (f"Bar {hit} (+{hit-lw})" if hit else "NICHT erreicht"))
    # ATR/ADX-Pfad
    nq = max(1, (k1 - k0 + 1) // 4)
    print("  Pfad (4 Viertel):")
    for i in range(4):
        a = k0 + i * nq
        b = k1 if i == 3 else min(k1, k0 + (i + 1) * nq - 1)
        print(f"    Q{i+1} {a}..{b}: close {c[a]:.4f}->{c[b]:.4f} ({c[b]-c[a]:+.4f})  "
              f"ATR {atr[a]:.4f}->{atr[b]:.4f}  ADX {adx[a]:.1f}->{adx[b]:.1f}  "
              f"tief={l[a:b+1].min():.4f}")
    print(f"  ADX max={adx[k0:k1+1].max():.1f}  ATR max={atr[k0:k1+1].max():.4f} "
          f"ATR min={atr[k0:k1+1].min():.4f}")
    # Kissen / Vakuum am Tief
    kis = kissen_ab(lw, l[lw])
    print(f"  Kissen am Tief (Bar {lw}) 0.30 %: "
          + (", ".join(f"K{kid}@{b:.4f}(geb {gb})" for kid, b, gb in kis) if kis
             else "keine lebende Vorkante => VAKUUM"))
    # Tiefpunkte aller Legs (Doppelboden-Check)
    tiefs = [(k, l[k]) for k in range(k0, k1 + 1) if l[k] <= l[lw] * 1.0004]
    print(f"  gleich/tiefer als Tief (±0.04 %): {[(k, round(l[k],4)) for k,_ in [(k,0) for k in ()]] or tiefs}")
    print("  Bar-fuer-Bar (nur Bars mit Low<Wand oder Close<Wand):")
    print(f"    {'Bar':>5} {'Zeit':<20} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} "
          f"{'ATR':>7} {'ADX':>6} {'-DI':>6} {'uWand%':>7}")
    for k in range(k0, k1 + 1):
        if l[k] < lvl or c[k] < lvl:
            print(f"    {k:>5} {str(ts[k]):<20} {o[k]:>8.4f} {h[k]:>8.4f} {l[k]:>8.4f} "
                  f"{c[k]:>8.4f} {atr[k]:>7.4f} {adx[k]:>6.2f} {mdi[k]:>6.2f} "
                  f"{(lvl-l[k])/lvl*100:>+7.3f}")

# ---------------------------------------------- Konsolidierte Trennmerkmale
print("\n" + "=" * 132)
print("KONSOLIDIERTE TRENNMERKMALE  A (Referenz) vs C/D/E")
print("=" * 132)
hdr = ["Merkmal", "A", "C", "D", "E"]
rows = [
    ("Exkursion %", "exc_pct"), ("Speed Exc %/h", "speed_exc_pct_h"),
    ("Exc/ATR(Start)", "exc_atr"), ("ATR Start->Ende", None),
    ("ADX Start->Ende", None), ("ADX-Max", "adx_max"),
    ("Close<Wand-Quote", None), ("max Close-Serie", None),
    ("Retrace nach Tief", "retrace_nach_tief"),
    ("Close-Pos im Range", "close_pos_im_range"),
    ("Effizienz", "effizienz"), ("Vol Std bp", "vol_std_bp"),
]
print(f"{'Merkmal':<20} " + " ".join(f"{x:>18}" for x in labs))
for name, kk in rows:
    cells = []
    for k in W:
        if kk is None:
            if name.startswith("ATR"):
                cells.append(f"{R[k]['atr_start']:.4f}->{R[k]['atr_end']:.4f}")
            elif name.startswith("ADX"):
                cells.append(f"{R[k]['adx_start']:.1f}->{R[k]['adx_end']:.1f}")
            elif name.startswith("Close<Wand"):
                k0, k1 = W[k]
                lvl2, _ = korridor_boden(k0 - 1)
                lvl2 = lvl2 if lvl2 is not None else o[k0]
                bl = sum(1 for j in range(k0, k1 + 1) if c[j] < lvl2)
                cells.append(f"{bl}/{k1-k0+1} ({bl/(k1-k0+1)*100:.0f}%)")
            elif name.startswith("max Close"):
                k0, k1 = W[k]
                lvl2, _ = korridor_boden(k0 - 1)
                lvl2 = lvl2 if lvl2 is not None else o[k0]
                st = bs = 0
                for j in range(k0, k1 + 1):
                    st = st + 1 if c[j] < lvl2 else 0
                    bs = max(bs, st)
                cells.append(f"{bs}")
            else:
                cells.append("-")
        else:
            cells.append(f"{R[k][kk]:.4f}")
    print(f"{name:<20} " + " ".join(f"{x:>18}" for x in cells))
