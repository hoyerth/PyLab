# -*- coding: utf-8 -*-
"""READ-ONLY Ergaenzung: Leg-Struktur, Zeit unter dem Level, Geschwindigkeitsprofil."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("efin2", EP)
engine = importlib.util.module_from_spec(_s)
sys.modules["efin2"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
d = scan["d"]
ts = list(d["ts"])
o = d["open"].to_numpy(float)
h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float)
c = d["close"].to_numpy(float)
v = d["tick_volume"].to_numpy(float)
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

CASES = {
    "A 14.08.02:00-09:00": dict(k0=836, k1=864, lvl=63.7970, name="K51 UNTEN"),
    "B 18.08.16:00-19.08.14:00": dict(k0=1076, k1=1160, lvl=63.1560, name="K57 UNTEN"),
}


def legs(k0: int, k1: int, min_pts: float) -> list[tuple[int, int, str, float]]:
    """Zerlegt das Fenster in Alternierungs-Legs (Swing-Pivots, kausal)."""
    idx = [k0]
    richtung = 0
    for k in range(k0 + 1, k1 + 1):
        if richtung >= 0 and l[k] < l[idx[-1]]:
            if richtung > 0:
                idx.append(idx[-1])
            richtung = -1
        elif richtung <= 0 and h[k] > h[idx[-1]]:
            if richtung < 0:
                idx.append(idx[-1])
            richtung = 1
    idx.append(k1)
    out = []
    for i in range(len(idx) - 1):
        a, b = idx[i], idx[i + 1]
        kind = "AB" if c[b] < c[a] else "AUF"
        out.append((a, b, kind, c[b] - c[a]))
    return out


for key, cfgk in CASES.items():
    k0, k1, lvl = cfgk["k0"], cfgk["k1"], cfgk["lvl"]
    print("=" * 118)
    print(f"{key}   gebrochene Wand: {cfgk['name']} @ {lvl:.4f}")
    print("=" * 118)
    # Zeit unter dem Level
    below = [k for k in range(k0, k1 + 1) if c[k] < lvl]
    lk, best, cur = None, 0, 0
    for k in range(k0, k1 + 1):
        if c[k] < lvl:
            cur += 1
            if cur > best:
                best, lk = cur, k - cur + 1
        else:
            cur = 0
    print(f"  Closes unter Level      : {len(below)}/{k1-k0+1} Bars "
          f"({len(below)/(k1-k0+1)*100:.0f}%)  maxSerie={best} ab Bar {lk}")
    print(f"  tiefer als Level (Low)  : {sum(1 for k in range(k0,k1+1) if l[k] < lvl)} Bars")
    print(f"  letzter Close < Level   : Bar {below[-1] if below else '-'} "
          f"({ts[below[-1]] if below else '-'})")
    lw = int(np.argmin(l[k0:k1 + 1])) + k0
    print(f"  Tief Bar {lw} ({ts[lw]}) Low={l[lw]:.4f}  rel.Pos={lw-k0}/{k1-k0}")
    # Ruecklauf-Meilensteine
    for frac in (0.25, 0.5, 0.75, 1.0):
        ziel = l[lw] + (o[k0] - l[lw]) * frac
        hit = next((k for k in range(lw, k1 + 1) if c[k] >= ziel), None)
        print(f"  Ruecklauf {frac*100:>3.0f}% (Close>={ziel:.4f}) : "
              + (f"Bar {hit} nach {hit-lw} Bars ({ts[hit]})" if hit else "NICHT erreicht"))
    # Geschwindigkeitsprofil (kumulierte Bewegung je Viertel)
    q = (k1 - k0 + 1) // 4
    print("  Geschwindigkeitsprofil (je Viertel):")
    for i in range(4):
        a = k0 + i * q
        b = k1 if i == 3 else k0 + (i + 1) * q - 1
        print(f"    Q{i+1} Bars {a}..{b}: {c[b]-c[a]:+.4f} pts  tief={l[a:b+1].min():.4f} "
              f"spanne={h[a:b+1].max()-l[a:b+1].min():.4f} ADX {adx[a]:.1f}->{adx[b]:.1f}")
    print("  ADX-Verlauf (jeder 4. Bar):")
    print("    " + " ".join(f"{adx[k]:.1f}" for k in range(k0, k1 + 1, 4)))
    print("  ATR-Verlauf (jeder 4. Bar):")
    print("    " + " ".join(f"{atr[k]:.4f}" for k in range(k0, k1 + 1, 4)))
    print()
