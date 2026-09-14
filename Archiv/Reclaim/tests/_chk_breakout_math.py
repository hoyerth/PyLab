# -*- coding: utf-8 -*-
"""READ-ONLY Finanzmathematik: Vergleich der Downside-Ausbrueche

  A) 14.08. 02:00-09:00   (Bars 836..864)
  B) 18.08. 16:00-19.08. 14:00 (Bars 1076..1160)

Dimensionen: Ausdehnung, Geschwindigkeit, Zeit, ATR, ADX/DI, Volatilitaet,
Effizienz, Volumen, Ruecklauf, Kissen/Vakuum.

Kein Patch an Engine/Adapter/Renderer. Engine-SHA hart geprueft.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SHA = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
assert hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == SHA

_s = importlib.util.spec_from_file_location("efin", ENGINE_P)
engine = importlib.util.module_from_spec(_s)
sys.modules["efin"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
d = scan["d"]
ts = list(d["ts"])
o = d["open"].to_numpy(float)
h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float)
c = d["close"].to_numpy(float)
v = d["tick_volume"].to_numpy(float)

# ------------------------------------------------------------------ Indikatoren
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
up = np.diff(h, prepend=h[0])
dn = -np.diff(l, prepend=l[0])
pdm = np.where((up > dn) & (up > 0), up, 0.0)
mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
tr_s = pd.Series(tr)
N = 14
atr = tr_s.ewm(alpha=1 / N, adjust=False).mean().to_numpy()
pdi = 100 * pd.Series(pdm).ewm(alpha=1 / N, adjust=False).mean().to_numpy() / atr
mdi = 100 * pd.Series(mdm).ewm(alpha=1 / N, adjust=False).mean().to_numpy() / atr
dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
adx = pd.Series(dx).ewm(alpha=1 / N, adjust=False).mean().to_numpy()
r1 = np.concatenate([[0.0], np.diff(np.log(c))])

W = {"A 14.08. 02:00-09:00": (836, 864), "B 18.08. 16:00-19.08. 14:00": (1076, 1160)}
BASE = 96


def blk(k0: int, k1: int) -> Dict[str, float]:
    """Kennzahlen eines Fensters [k0, k1] inkl. 96-Bar-Vorlauf."""
    seg_o, seg_h, seg_l, seg_c = o[k0:k1 + 1], h[k0:k1 + 1], l[k0:k1 + 1], c[k0:k1 + 1]
    seg_v = v[k0:k1 + 1]
    m = len(seg_c)
    hi, lo_, cl_last, op_first = seg_h.max(), seg_l.min(), seg_c[-1], seg_o[0]
    net = cl_last - op_first
    exc = op_first - lo_                     # maximale Abwaerts-Exkursion
    hours = m * 0.25
    tief_i = int(seg_l.argmin())
    retr = (cl_last - lo_) / (op_first - lo_) if op_first > lo_ else float("nan")
    # Vorlauf
    p0 = max(0, k0 - BASE)
    pre_h, pre_l, pre_c = h[p0:k0], l[p0:k0], c[p0:k0]
    pre_net = (pre_c[-1] - pre_c[0]) if len(pre_c) else 0.0
    pre_rng = (pre_h.max() - pre_l.min()) if len(pre_c) else 0.0
    # Realisierte Vol / Effizienz
    seg_r = r1[k0:k1 + 1]
    eff = abs(net) / np.abs(np.diff(seg_c)).sum() if m > 1 else float("nan")
    dn_bars = int((np.diff(seg_c) < 0).sum())
    # max. Serie fallender Closes
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
        "vol_std_bp": float(np.std(seg_r) * 1e4), "vol_std_pre_bp": float(np.std(r1[p0:k0]) * 1e4),
        "effizienz": eff, "down_bars": dn_bars, "down_quote": dn_bars / max(m - 1, 1),
        "max_down_streak": best, "tief_bar_rel": tief_i,
        "retrace_nach_tief": retr,
        "close_pos_im_range": (cl_last - lo_) / (hi - lo_) if hi > lo_ else float("nan"),
        "pre_net_pct": pre_net / (pre_c[0] or 1) * 100 if len(pre_c) else 0.0,
        "pre_range_pct": pre_rng / (pre_c[0] or 1) * 100 if len(pre_c) else 0.0,
        "vol_sum": seg_v.sum(), "vol_avg": seg_v.mean(),
        "vol_pre_avg": v[p0:k0].mean(),
        "vol_ratio": seg_v.mean() / (v[p0:k0].mean() or 1),
        "worst_bar_pct": float(np.min(seg_l / np.concatenate([[seg_o[0]], seg_c[:-1]]) - 1) * 100),
        "biggest_body_pct": float(np.max(np.abs(seg_c - seg_o) / seg_o) * 100),
    }


print("=" * 120)
print("FINANZMATHEMATISCHER VERGLEICH  |  A) 14.08. 02:00-09:00   vs   B) 18.08. 16:00-19.08. 14:00")
print("=" * 120)
R = {k: blk(*ab) for k, ab in W.items()}
keys = ["bars", "stunden", "open", "high", "low", "close", "net_pts", "net_pct",
        "exc_pts", "exc_pct", "range_pts", "range_pct", "speed_net_pct_h",
        "speed_exc_pct_h", "atr_start", "atr_end", "exc_atr", "range_atr",
        "adx_start", "adx_end", "adx_max", "pdi_start", "mdi_start", "mdi_end",
        "vol_std_bp", "vol_std_pre_bp", "effizienz", "down_bars", "down_quote",
        "max_down_streak", "tief_bar_rel", "retrace_nach_tief",
        "close_pos_im_range", "pre_net_pct", "pre_range_pct", "vol_sum", "vol_avg",
        "vol_pre_avg", "vol_ratio", "worst_bar_pct", "biggest_body_pct"]
print(f"{'Kennzahl':<22} {'A':>16} {'B':>16} {'B/A':>10}")
for k in keys:
    a_, b_ = R['A 14.08. 02:00-09:00'][k], R['B 18.08. 16:00-19.08. 14:00'][k]
    ratio = f"{b_/a_:.3f}" if isinstance(a_, float) and a_ not in (0.0,) and np.isfinite(a_) else "-"
    print(f"{k:<22} {a_:>16.4f} {b_:>16.4f} {ratio:>10}")

# Monatsbaseline
mon = blk(BASE, n - 1)
print(f"\nMonatsbaseline: net_pct={mon['net_pct']:+.2f}% range_pct={mon['range_pct']:.2f}% "
      f"ATR14_end={mon['atr_end']:.4f} ADX14_end={mon['adx_end']:.2f} vol_std_bp={mon['vol_std_bp']:.1f}")

# ------------------------------------------------------------ Bar-fuer-Bar
for name, (k0, k1) in W.items():
    print("\n" + "=" * 120)
    print(f"BAR-FUER-BAR {name}")
    print("=" * 120)
    print(f"{'Bar':>5} {'Zeit':<20} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} "
          f"{'Rng%':>7} {'Vol':>6} {'ATR14':>7} {'ADX':>6} {'+DI':>6} {'-DI':>6} {'v/ATR':>6}")
    for k in range(k0, k1 + 1):
        print(f"{k:>5} {str(ts[k]):<20} {o[k]:>8.4f} {h[k]:>8.4f} {l[k]:>8.4f} {c[k]:>8.4f} "
              f"{(h[k]-l[k])/o[k]*100:>7.3f} {v[k]:>6.0f} {atr[k]:>7.4f} {adx[k]:>6.2f} "
              f"{pdi[k]:>6.2f} {mdi[k]:>6.2f} {tr[k]/atr[k]:>6.2f}")
