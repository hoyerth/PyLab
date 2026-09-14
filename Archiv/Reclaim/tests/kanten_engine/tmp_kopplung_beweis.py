# -*- coding: utf-8 -*-
"""READ-ONLY: Kopplungs-Beweis + Spiegel-Kante K48 -- AUG n=1288.

Frage 1: Ist sweep_min == touch_band_pct (0.12) exakt V0?
         Und was passiert bei sweep_min > band (0.15 / 0.30)?
Frage 2: K48 (Spiegelbild zu K67 am Range-Boden) -- je gehandelt / TP2?
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

G3O = ("        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
       "        if not (hi[k] > basis and band < dist_o\r\n"
       "                <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G3U = ("    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
       "    if not (lo[k] < basis and band < dist_u\r\n"
       "            <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G2 = ("            if dist <= cfg.touch_band_pct:\r\n"
      "                continue                        # Beruehrung/in-band (Schatten)\r\n")
G2S = ("            if cfg.touch_band_pct < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
       "                pool.append(e)\r\n")


def baue(sweep_min: float) -> str:
    s = SRC.replace(G3O, "        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
                         "        if not (hi[k] > basis and SWEEP_MIN < dist_o\r\n"
                         "                <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(G3U, "    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
                       "    if not (lo[k] < basis and SWEEP_MIN < dist_u\r\n"
                       "            <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(G2, "            if dist <= SWEEP_MIN:\r\n"
                      "                continue                        # Beruehrung/in-band (Schatten)\r\n", 1)
    s = s.replace(G2S, "            if SWEEP_MIN < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
                       "                pool.append(e)\r\n", 1)
    return s.replace("V3_TP_MINDIST_PCT: float = 1.5",
                     f"V3_TP_MINDIST_PCT: float = 1.5\r\nSWEEP_MIN: float = {sweep_min}", 1)


m0 = load("b0", SRC)
cfg = m0.StraightEdgeHarnessKonfiguration()

print("=" * 116)
print("KOPPLUNGS-BEWEIS: sweep_min vs. touch_band_pct (0.12)")
print("=" * 116)
ref = None
for sm in (0.12, 0.15, 0.30, 0.60):
    mod = load(f"b_{sm}", baue(sm))
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = sc["n"]
    tr, _ = mod._se_trades(sc, cfg)
    sig = [(t.bar, t.richtung, round(t.basis, 3), round(t.r, 4)) for t in tr]
    if ref is None:
        ref = sig
    print(f"  sweep_min={sm:5.2f} %  Trades {len(tr):2d}  "
          f"Netto-R {sum(t.r for t in tr):+7.2f}  identisch zu 0.12: {sig == ref}")

print("")
print("=" * 116)
print("SPIEGEL-KANTEN: K67 (Range-Top) und K48 (Range-Boden)")
print("=" * 116)
sc = m0._se_scan("AUG", cfg)
sc["box_end_bar"] = sc["n"]
tr0, _ = m0._se_trades(sc, cfg)
d = sc["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
alle = {e.kid: e for e in list(sc["edges"]) + list(sc["seeds"])}
for kid in (67, 48, 85):
    e = alle[kid]
    print(f"  K{kid} {e.seite} basis={e.basis:.3f} pivot={e.erster_pivot_bar} "
          f"geb={e.geburts_bar} n={e.touch_anzahl} anker={e.ist_prim_anker}")
    print(f"    wicks: {[(b, round(p, 3)) for b, p in e.wicks]}")
    print(f"    als Einstiegskante gehandelt: "
          f"{[(t.bar, t.richtung, t.r) for t in tr0 if t.kid == kid] or 'NIE'}")
    print(f"    als TP2 referenziert: "
          f"{[(t.bar, t.kid) for t in tr0 if abs(t.tp2 - e.basis) < 1e-6] or 'NIE'}")
print("")
print("  Range-Extrem AUG: hi_max=%.3f (Bar %d) | lo_min=%.3f (Bar %d)"
      % (hi.max(), int(hi.argmax()), lo.min(), int(lo.argmin())))
print("  -> K67 (69.946) liegt %.3f USD unter dem Range-Top (%.3f)"
      % (hi.max() - 69.946, hi.max()))
print("  -> K48 (62.562) liegt %.3f USD ueber dem Range-Boden (%.3f)"
      % (62.562 - lo.min(), lo.min()))
