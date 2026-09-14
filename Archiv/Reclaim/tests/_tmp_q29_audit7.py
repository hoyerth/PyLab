# -*- coding: utf-8 -*-
"""READ-ONLY: Warum faellt Bar 1002 durch? Exaktes Gate + Papier-Arithmetik.

Nur In-Memory-Quelltextvarianten; auf der Platte wird NICHTS geaendert.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

sys.argv = ["tmp_q29_audit7"]
voll = REN.read_text(encoding="utf-8")
_i = voll.index("import matplotlib")
mod = {"__name__": "q29a7", "__file__": str(REN)}
sys.modules[mod["__name__"]] = type(sys)("q29a7")
exec(compile(voll[:voll.rindex("\n", 0, _i) + 1], str(REN), "exec"), mod)

engine, cfg, scan = mod["engine"], mod["cfg"], mod["scan"]
ADAPTER, box_end = mod["DEFAULT_ADAPTER"], mod["box_end"]
src0 = mod["patched_src"]

A_KD = "            kd = _kandidat(richtung, k, sweep_px)"
A_Q = "        return distanz <= cfg.quartil_distanz_pct"

KR = {
    "S-gegen": '            if richtung == "SHORT":\n'
               '                if not (gegen_basis < basis):\n'
               '                    stats["kein_raum"] += 1',
    "S-mindist": '                if abs(basis - gegen_basis) / basis * 100.0 '
                 '< V3_TP_MINDIST_PCT:\n'
                 '                    stats["kein_raum"] += 1',
    "L-gegen": '                if not (gegen_basis > basis):\n'
               '                    stats["kein_raum"] += 1',
    "L-mindist": '                if abs(gegen_basis - basis) / basis * 100.0 '
                 '< V3_TP_MINDIST_PCT:\n'
                 '                    stats["kein_raum"] += 1',
    "POC-Band": '            if not (unter < poc < ober):\n'
                '                stats["kein_raum"] += 1',
    "L-Ordnung": '                if not (sl < entry < poc < tp2):\n'
                 '                    stats["kein_raum"] += 1',
    "Risiko": '            if risk <= 0:\n'
              '                stats["kein_raum"] += 1',
}
A_POC = ("                d, poc_start, k, unter, ober, cfg.num_bins)\n"
         "            if not (unter < poc < ober):")
A_TP2 = "            tp2 = gegen_basis\n"

src = src0
for tag, anchor in KR.items():
    assert src.count(anchor) == 1, (tag, src.count(anchor))
    last = anchor.split("\n")[-1]
    indent = " " * (len(last) - len(last.lstrip()))
    neu = anchor + f'\n{indent}_KR.append(("{tag}", k, richtung))'
    src = src.replace(anchor, neu, 1)
assert src.count(A_POC) == 1
src = src.replace(A_POC, A_POC.replace(
    "            if not (unter < poc < ober):",
    "            if k == 1002:\n                _DG.append(('P1', k, basis, "
    "gegen_basis, unter, ober, poc))\n"
    "            if not (unter < poc < ober):"), 1)
assert src.count(A_TP2) == 1
src = src.replace(A_TP2, A_TP2 + "            if k == 1002:\n"
                                "                _DG.append(('P2', k, "
                                "entry_bar, entry, sl, tp2))\n", 1)


def lauf(quelle: str, **extra):
    _ns = dict(engine.__dict__)
    _ns["_hook"] = ADAPTER
    _ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
    _ns.update(extra)
    exec(compile(quelle, "<v>", "exec"), _ns)
    orig = engine._se_trades
    engine._se_trades = _ns["_se_trades"]
    try:
        return engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = orig


print("=== R1) Q29 AUS + GATE-TAGS + DIAGNOSE 1002 ===")
_kr: list = []
_dg: list = []
V1, st1 = lauf(src.replace(A_Q, "        return True", 1), _KR=_kr, _DG=_dg)
print(f"  {len(V1)} Trades / {sum(t.r for t in V1):+.6f} R")
print("  stats: " + " | ".join(f"{k}={v}" for k, v in sorted(st1.items())
                               if isinstance(v, int) and not k.endswith("liste")))
print("  kein_raum-Gruende 988..1012:")
for tag, k, r in _kr:
    if 988 <= k <= 1012:
        print(f"    bar {k:4d} {r:5s} -> {tag}")
print("  Diagnose Bar 1002:")
for eintrag in _dg:
    print("   ", eintrag)

print("\n=== R2) Q29 AUS + 991 UNTERDRUECKT -> wird 1002 frei? ===")
SKIP = A_KD + "\n            if k == 991:\n                continue"
_kr2: list = []
_dg2: list = []
V2, st2 = lauf(src.replace(A_Q, "        return True", 1).replace(
    A_KD, SKIP, 1), _KR=_kr2, _DG=_dg2)
print(f"  {len(V2)} Trades / {sum(t.r for t in V2):+.6f} R")
print("  Bars: " + str(sorted(t.bar for t in V2)))
print("  1002 vorhanden? " + ("JA" if any(t.bar == 1002 for t in V2) else "NEIN"))
for tag, k, r in _kr2:
    if 995 <= k <= 1010:
        print(f"    kein_raum bar {k:4d} {r:5s} -> {tag}")

print("\n=== R3) PAPIER: GEOMETRIE DES 1002-SETUPS (Engine-Funktionen) ===")
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
k = 1002
kd = by_kid[77]
sweep = float(lo[k])
basis = kd.basis_bei(k)
stufe_n, stufe_name = engine._reclaim_stufe("UNTEN", k, basis, hi, lo, cl, cfg)
entry_bar = k + stufe_n
reclaim_bar = entry_bar - 1
cluster_ext = float(lo[k:reclaim_bar + 1].min())
sl = cluster_ext - cfg.sl_buffer_usd
h2 = ADAPTER.hook_2_ziel(k, "LONG")
tp2 = h2.ziel_preis if h2.ziel_preis is not None else 0.0
geg_pool = [e for e in (scan["edges"] + scan["seeds"])
            if e.seite == "OBEN" and e.erster_pivot_bar + 2 <= k + 1
            and (e.touch_conf(k) >= 2)]
geg = max(geg_pool, key=lambda e: e.basis_bei(k)) if geg_pool else None
poc = engine.berechne_kausalen_histogramm_poc(d, 0, k, basis, tp2, cfg.num_bins)
entry = float(op[entry_bar])
print(f"  K77 basis_bei({k})   = {basis:.4f}   sweep lo[{k}] = {sweep:.4f}")
print(f"  stufe                = {stufe_n} ({stufe_name}) -> entry_bar "
      f"{entry_bar}, reclaim_bar {reclaim_bar}")
print(f"  cluster_ext {cluster_ext:.4f} - {cfg.sl_buffer_usd} -> SL {sl:.4f}")
print(f"  hook_2 LONG          = {h2.modus} ziel {tp2:.4f}")
print(f"  Gegenkante roh       = "
      f"{'K%d %.4f' % (geg.kid, geg.basis_bei(k)) if geg else 'keine'}")
print(f"  POC (0..{k}, {cfg.num_bins} bins) = {poc:.4f}")
print(f"  entry = open[{entry_bar}] = {entry:.4f}")
print(f"  Pruefungen: sl<entry {sl < entry} | entry<poc {entry < poc} | "
      f"poc<tp2 {poc < tp2} | sl<entry<poc<tp2 = "
      f"{sl < entry < poc < tp2}  <-- entscheidend")
risk = abs(sl - entry)
print(f"  risk = {risk:.4f} | Chance bis tp2 = {tp2 - entry:.4f} | "
      f"CRV {(tp2 - entry) / risk:.2f}")
tr = engine._c_loese_trade(hi, lo, cl, entry_bar, entry, "LONG", sl, poc, tp2,
                           cfg.tp1_anteil_pct)
print(f"  HYPOTHETISCHER Ausgang (Papier): R {tr.r_mult:+.6f} | "
      f"resultat {tr.resultat} | grund1 {tr.grund1} | "
      f"exit1 {tr.exit1_bar} | exit2 {tr.exit2_bar}")
print(f"  Kursverlauf {entry_bar}..{entry_bar + 20}: "
      + " ".join(f"{int(y)}:{lo[y]:.3f}-{hi[y]:.3f}"
                 for y in range(entry_bar, min(entry_bar + 20, len(hi)))))
