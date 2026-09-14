# -*- coding: utf-8 -*-
"""R-ZERLEGUNG Bar 564: Haelften, Exits, Risk."""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_loader("ke_r", loader=None)
mod = importlib.util.module_from_spec(spec)              # type: ignore[arg-type]
mod.__file__ = str(P)
sys.modules["ke_r"] = mod
exec(compile(P.read_text(encoding="utf-8"), str(P), "exec"), mod.__dict__)

print("ANTEIL_TP1 =", mod.ANTEIL_TP1)
cfg = mod.StraightEdgeHarnessKonfiguration()
print("tp1_anteil_pct =", cfg.tp1_anteil_pct)
sc = mod._se_scan("AUG", cfg)
sc["box_end_bar"] = sc["n"]
tr, _ = mod._se_trades(sc, cfg)
d = sc["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)

for bar in (564, 529, 242, 229):
    t = [x for x in tr if x.bar == bar][0]
    res = mod._c_loese_trade(hi, lo, cl, t.entry_bar, t.entry, t.richtung,
                             t.sl, t.poc, t.tp2, cfg.tp1_anteil_pct)
    risk = abs(t.sl - t.entry)
    print(f"\nBar {bar} {t.richtung} K{t.kid}: E={t.entry:.3f} SL={t.sl:.3f} "
          f"TP1={t.poc:.3f} TP2={t.tp2:.3f} risk={risk:.3f}")
    print(f"  r1={res.r1:+.4f} exit1={res.exit1:.3f} @bar {res.exit1_bar} "
          f"grund1={res.grund1}")
    print(f"  r2={res.r2:+.4f} exit2={res.exit2:.3f} @bar {res.exit2_bar} "
          f"grund2={res.grund2}")
    print(f"  r_mult={res.r_mult:+.4f} | Probe 0.25*r1+0.75*r2 = "
          f"{0.25 * res.r1 + 0.75 * res.r2:+.4f}")
    print(f"  Preisprobe TP1: (E-TP1)/risk = {(t.entry - t.poc) / risk:+.4f} "
          f"| TP2: {(t.entry - t.tp2) / risk:+.4f}")
    # Wann wurde TP2 getroffen?
    if t.richtung == "SHORT":
        hit2 = [i for i in range(t.entry_bar, min(t.entry_bar + 120, len(lo)))
                if lo[i] <= t.tp2]
        hit1 = [i for i in range(t.entry_bar, min(t.entry_bar + 120, len(lo)))
                if lo[i] <= t.poc]
        hit_sl = [i for i in range(t.entry_bar, min(t.entry_bar + 120, len(hi)))
                  if hi[i] >= t.sl]
    else:
        hit2 = [i for i in range(t.entry_bar, min(t.entry_bar + 120, len(hi)))
                if hi[i] >= t.tp2]
        hit1 = [i for i in range(t.entry_bar, min(t.entry_bar + 120, len(hi)))
                if hi[i] >= t.poc]
        hit_sl = [i for i in range(t.entry_bar, min(t.entry_bar + 120, len(lo)))
                  if lo[i] <= t.sl]
    print(f"  Treffer: TP1 zuerst @{hit1[:3]} | TP2 @{hit2[:3]} | "
          f"SL @{hit_sl[:3]}")
