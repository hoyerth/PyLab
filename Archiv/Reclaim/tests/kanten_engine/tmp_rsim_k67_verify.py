# -*- coding: utf-8 -*-
"""READ-ONLY Verifikation des K67-Trades (V_l4r_f) + Herkunft der 3 Signale."""
from __future__ import annotations

import copy
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_ver", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = len(scan["d"])
scan["box_end_bar"] = n
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
ts = d["ts"]

k67 = next(e for e in list(scan["edges"]) + list(scan["seeds"]) if e.kid == 67)

print("=" * 120)
print("1) K67-SIGNALE (kausale V3-Basis) -- welche Bars liefern Reclaim?")
print("=" * 120)
print(f"  {'bar':>5s} {'Zeit':13s} {'basis_k':>8s} {'high':>8s} {'close':>8s} "
      f"{'stufe':>5s} {'name':16s} {'entry_bar':>9s} {'zyklus?':>8s}")
sig = []
for k in range(850, 940):
    basis = k67.basis_bei(k)
    st, name = engine._reclaim_stufe("OBEN", k, basis, hi, lo, cl, cfg)
    if st:
        eb = k + st
        if not sig:
            zyk = "TAKEN"
        else:
            zyk = ("BLOCK" if eb < 874 + cfg.retest_zyklus_bars else "frei")
        sig.append((k, st, eb))
        print(f"  {k:5d} {ts.iloc[k].strftime('%d.%m. %H:%M'):13s} "
              f"{basis:8.4f} {hi[k]:8.4f} {cl[k]:8.4f} {st:5d} {name:16s} "
              f"{eb:9d} {zyk:>8s}")

print("\n" + "=" * 120)
print("2) TRADE-VERIFIKATION bar 873 -> entry 874 (SHORT)")
print("=" * 120)
entry_bar, entry, sl = 874, 69.4740, 70.0250
risk = abs(sl - entry)
seg_hi = float(np.max(hi[entry_bar:]))
seg_hi_bar = int(entry_bar + int(np.argmax(hi[entry_bar:])))
seg_lo = float(np.min(lo[entry_bar:]))
seg_lo_bar = int(entry_bar + int(np.argmin(lo[entry_bar:])))
close_end = float(cl[-1])
print(f"  Entry      : {entry:.4f} (open[874])")
print(f"  SL         : {sl:.4f}  | risk = {risk:.4f} USD ({risk / entry * 100:.3f} %)")
print(f"  Max High ab Entry: {seg_hi:.4f} (bar {seg_hi_bar} "
      f"{ts.iloc[seg_hi_bar].strftime('%d.%m. %H:%M')}) "
      f"-> SL {'GETROFFEN' if seg_hi >= sl else 'NICHT getroffen'} "
      f"(Abstand {sl - seg_hi:+.4f})")
print(f"  Min Low  ab Entry: {seg_lo:.4f} (bar {seg_lo_bar} "
      f"{ts.iloc[seg_lo_bar].strftime('%d.%m. %H:%M')})")
print(f"  TP2 (Gegenkante) : 62.5625 | TP1/POC: 64.8390 -> beide nie erreicht")
print(f"  Close Fensterende: {close_end:.4f} -> R = "
      f"({entry:.4f} - {close_end:.4f}) / {risk:.4f} = "
      f"{(entry - close_end) / risk:+.4f}")

print("\n" + "=" * 120)
print("3) WARUM NUR 1 TRADE? (Zyklus + Dedup)")
print("=" * 120)
print(f"  retest_zyklus_bars = {cfg.retest_zyklus_bars} (Referenz = ENTRY)")
print(f"  Trade 1: entry_bar 874 -> naechster Entry erlaubt ab "
      f"{874 + cfg.retest_zyklus_bars}")
for k, st, eb in sig[1:]:
    print(f"  Signal bar {k} -> entry_bar {eb}: "
          f"{'BLOCKIERT (Zyklus)' if eb < 874 + cfg.retest_zyklus_bars else 'frei'}"
          f"{' + Dedup (gleicher Entry-Bar)' if eb in [s[2] for s in sig[:1]] else ''}")
print("  -> Nur das erste Signal (bar 873, in-bar) wird realisiert.")
