# -*- coding: utf-8 -*-
"""READ-ONLY Verifikation des P12-Treffers (Bar 1259) und des H1-Nullnachweises."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name, path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"),
         m.__dict__)
    return m


E = load("ke_v", P)
cfg = E.StraightEdgeHarnessKonfiguration()
scan = E._se_scan("AUG", cfg)
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
by = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}

print("=== P12-Treffer: Bar 1259 / Bodenkante K82 ===")
K82 = by[82]
print(f"  K82: seite {K82.seite} piv1 {K82.erster_pivot_bar} "
      f"geb {K82.geburts_bar} | e.basis {K82.basis:.4f}")
print(f"  wicks: {[(b, round(p, 4)) for b, p in K82.wicks]}")
for k in (1256, 1257, 1258, 1259, 1260, 1261):
    print(f"    bar {k:4d} O {op[k]:7.3f} H {hi[k]:7.3f} L {lo[k]:7.3f} "
          f"C {cl[k]:7.3f} | K82 basis_bei {K82.basis_bei(k):.4f} "
          f"touch_conf {K82.touch_conf(k)} | lo<67.6355 "
          f"{lo[k] < 67.6355} cl>67.6355 {cl[k] > 67.6355}")
poc = E.berechne_kausalen_histogramm_poc(d, 1171, 1259, 67.6355, 69.5550,
                                         cfg.num_bins)
print(f"  regel-lokaler POC (Anker 1171, 67.6355..69.5550) = {poc:.4f}")
print(f"  entry open[1260] = {op[1260]:.4f} | SL {lo[1259:1261].min() - cfg.sl_buffer_usd:.4f}")
tr = E._c_loese_trade(hi, lo, cl, 1260, float(op[1260]), "LONG",
                      float(lo[1259:1261].min()) - cfg.sl_buffer_usd, poc,
                      69.5550, cfg.tp1_anteil_pct)
print(f"  R {tr.r_mult:+.6f} | {tr.resultat} | {tr.grund1}/{tr.grund2} | "
      f"exits {tr.exit1_bar}/{tr.exit2_bar}")

print("\n=== H1-Nullnachweis (deklarierter Boden als Anker) ===")
print("  Phasenfenster mit deklariertem Boden:")
for lab, s, e_ in (("P9", 848, 1020), ("P12_RESERVE", 1171, 1272)):
    print(f"    {lab:12s} {s}..{e_}  -> H1-Ueberlappung "
          f"{'JA' if s < scan['box_end_bar'] else 'NEIN'}")
print(f"  box_end_bar = {scan['box_end_bar']} | Phasenfenster beginnen bei "
      f"620 (P6, nur Visualisierung) -> kein deklariertes Segment in H1")

print("\n=== Gegenprobe: was P6/P10/P11 ohne Segment tun wuerden ===")
for lab, s, e_ in (("P6", 620, 673), ("P10", 1030, 1075), ("P11", 1082, 1134)):
    hits = []
    for k in range(s, e_ + 1):
        for e_ in (scan["edges"] + scan["seeds"]):
            if e_.seite != "UNTEN" or e_.erster_pivot_bar + 2 > k:
                continue
            if e_.touch_conf(k) < cfg.min_touches_handelbar:
                continue
            b = float(e_.basis_bei(k))
            if lo[k] < b < cl[k]:
                hits.append((k, e_.kid))
    print(f"  {lab:4s}: {len(hits)} Treffer unter dem LOOSEN Anker "
          f"(Kante-eigene Basis) -> {hits[:8]}")
