# -*- coding: utf-8 -*-
"""READ-ONLY B-Struktur: zwei Wandkandidaten (64.798 vs 63.156) + OHLC."""
from __future__ import annotations
import hashlib, importlib.util, sys
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(EP.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
s = importlib.util.spec_from_file_location("ebs", EP)
e = importlib.util.module_from_spec(s)
sys.modules["ebs"] = e
s.loader.exec_module(e)  # type: ignore[union-attr]
e.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")  # type: ignore[index]
cfg = e.StraightEdgeHarnessKonfiguration()
sc = e._se_scan("EXT", cfg)  # type: ignore[arg-type]
d = sc["d"]; ts = list(d["ts"])
op = d["open"].to_numpy(float); hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float); cl = d["close"].to_numpy(float)
vo = d["tick_volume"].to_numpy(float)
E = list(sc["edges"]); LIVE = int(cfg.wall_live_bars)


def lebt(x, k):
    b = [bb for bb, _ in x.wicks if bb <= k]
    return bool(b) and max(b) >= k - LIVE


def bas(x, k):
    return float(x.basis_bei(k))


print("B-Fenster OHLC (Bars 1070..1140):")
print(f"{'Bar':>5} {'Zeit':<20} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Vol':>6}  {'U-Kanten (lebend, <Close+3%)'}")
for k in range(1070, 1141):
    un = sorted([(int(x.kid), bas(x, k), int(x.geburts_bar)) for x in E
                 if x.seite == "UNTEN" and int(x.geburts_bar) <= k and lebt(x, k)],
                key=lambda t: t[1])
    nah = [f"K{kid}@{b:.4f}(g{gb})" for kid, b, gb in un if b < cl[k] * 1.03]
    print(f"{k:>5} {str(ts[k]):<20} {op[k]:>8.4f} {hi[k]:>8.4f} {lo[k]:>8.4f} {cl[k]:>8.4f} "
          f"{vo[k]:>6.0f}  {', '.join(nah[:4])}")

w1 = 64.7980
w2 = 63.1560
brk1 = next(k for k in range(1076, 1161) if lo[k] < w1)
brk2 = next(k for k in range(1076, 1161) if lo[k] < w2)
kl = int(np.argmin(lo[1076:1161])) + 1076
print(f"\nKandidat 1 (Korridor-Boden)  {w1:.4f}: Bruch Bar {brk1}, Exc={(w1-lo[kl])/w1*100:.3f}%")
print(f"Kandidat 2 (K57 tief)        {w2:.4f}: Bruch Bar {brk2}, Exc={(w2-lo[kl])/w2*100:.3f}%")
print(f"Leg-Tief Bar {kl} = {lo[kl]:.4f}")
