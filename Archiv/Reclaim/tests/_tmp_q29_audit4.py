# -*- coding: utf-8 -*-
"""READ-ONLY Q29-Audit v4: Gegenprobe im ADAPTER-Regime (v0.1 = amtliche Basis).

Laedt den Renderer bis zum Plot-Schnitt (kein PNG, keine Datei geschrieben),
wiederholt dort die drei Laeufe und setzt zusaetzlich Q29 in-memory aus.
"""
from __future__ import annotations

import copy
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")          # kein Re-Wrap (Renderer
#                                                  wickelt stdout selbst neu)
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

sys.argv = ["tmp_q29_audit4"]                      # _cli() ohne Argumente
voll = REN.read_text(encoding="utf-8")
_i = voll.index("import matplotlib")               # Plot-Schnitt
schnitt = voll.rindex("\n", 0, _i) + 1
kopf = voll[:schnitt]

mod = {"__name__": "renderer_q29audit", "__file__": str(REN)}
sys.modules[mod["__name__"]] = type(sys)("renderer_q29audit")
exec(compile(kopf, str(REN), "exec"), mod)

V0 = mod["V0"]
V1_basis, st_basis = mod["V1_basis"], mod["st_basis"]
box_end = mod["box_end"]
_lauf = mod["_lauf"]
DEFAULT_ADAPTER = mod["DEFAULT_ADAPTER"]
ns = mod["ns"]
cfg = mod["cfg"]

import re

_GATE_RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+"
                      r"basis=[\d.]+\s+sweep=([\d.]+)")


def RE(liste):
    """[(bar, sweep_px, kid, richtung)] aus den Engine-Sperrlisten."""
    out = []
    for s in liste:
        m = _GATE_RE.search(s)
        if m:
            out.append((int(m.group(1)), float(m.group(4)), int(m.group(3)),
                        m.group(2)))
    return out


def zeig(tag, trades):
    h1 = [t for t in trades if t.entry_bar < box_end]
    h2 = [t for t in trades if t.entry_bar >= box_end]
    print(f"  {tag:22s}: {len(trades):2d} / {sum(t.r for t in trades):+10.6f} R"
          f" | H1 {len(h1):2d}/{sum(t.r for t in h1):+10.6f}"
          f" | H2 {len(h2):2d}/{sum(t.r for t in h2):+10.6f}")


print("=== I) AMTLICHE BASIS IM ADAPTER-REGIME ===")
zeig("V0 (Engine roh)", V0)
zeig("V1_basis (DEFAULT)", V1_basis)
print(f"  Soll: V1_basis H1 8/38.964262 | H2 7/7.902085 "
      f"(BASELINE_V01_H2_R={mod['BASELINE_V01_H2_R']})")
g = RE(st_basis["quartil_liste"])
print(f"  Q29-Marker (Adapter-Lauf): {len(g)}  | M6: "
      f"{len(RE(st_basis['blocker_liste']))}")
hb = sorted(b for b, _p, _k, _r in g if b >= box_end)
print(f"  Q29 H2-Bars ({len(hb)}): {hb}")
_k0 = {(t.bar, t.kid): t for t in V0}
_k1 = {(t.bar, t.kid): t for t in V1_basis}
print("  Differenz ROH-Engine (14) vs. Adapter-v0.1 (15):")
print("    nur Adapter: "
      + (", ".join(f"K{t.kid}@{t.bar} {t.r:+.6f}"
                   for (_b, _k), t in sorted(_k1.items())
                   if (_b, _k) not in _k0) or "keine"))
print("    nur Engine : "
      + (", ".join(f"K{t.kid}@{t.bar} {t.r:+.6f}"
                   for (_b, _k), t in sorted(_k0.items())
                   if (_b, _k) not in _k1) or "keine"))

print("\n=== J) Q29 IM ADAPTER-LAUF AUSGESETZT ===")
A_Q = "        return distanz <= cfg.quartil_distanz_pct"
psrc = mod["patched_src"]
assert psrc.count(A_Q) == 1, psrc.count(A_Q)
ns["patched_src_backup"] = psrc
mod["patched_src"] = psrc.replace(A_Q, "        return True")
V1_off, st_off = _lauf(DEFAULT_ADAPTER, True)
print(f"  Q29-Sperren aus: {st_off['quartil_blockiert']} "
      f"(Liste {len(st_off['quartil_liste'])})")
zeig("V1_basis (Q29 an)", V1_basis)
zeig("V1_off (Q29 aus)", V1_off)
print(f"  delta R = {sum(t.r for t in V1_off) - sum(t.r for t in V1_basis):+.6f}")


def schluessel(ts):
    return {(int(t.bar), int(t.kid), float(round(t.r, 6))) for t in ts}


kb, ko = schluessel(V1_basis), schluessel(V1_off)
neu = sorted(ko - kb, key=lambda x: x[0])
weg = sorted(kb - ko, key=lambda x: x[0])
print(f"  NEU durch Q29-aus ({len(neu)}):")
for b, kid, r in neu:
    print(f"    bar {b:4d} K{kid:3d} {r:+9.6f} R   "
          f"{'(H2)' if b >= box_end else '(H1)'}")
print(f"  ENTFAELLT ({len(weg)}):")
for b, kid, r in weg:
    print(f"    bar {b:4d} K{kid:3d} {r:+9.6f} R")
print(f"  Summe NEU = {sum(x[2] for x in neu):+.6f} R")
print(f"  Summe ENTFAELLT = {sum(x[2] for x in weg):+.6f} R")
print(f"  Kontrolle: NEU + ENTFAELLT = "
      f"{sum(x[2] for x in neu) + sum(x[2] for x in weg):+.6f} R")

print("\n=== K) KANDIDATENWAHL 990..1005 (Klaerung bar 998) ===")
import ast as _ast

A_KD = "            kd = _kandidat(richtung, k, sweep_px)"
A_KD_NEW = (A_KD + "\n"
            "            _TRACE.append((k, richtung, None if kd is None\n"
            "                           else kd.kid))")
engine = mod["engine"]
P_RAW = ROOT / "test" / "tmp_kanten_engine_replay.py"
raw_src = P_RAW.read_text(encoding="utf-8")
_node = next(x for x in _ast.parse(raw_src).body
             if isinstance(x, _ast.FunctionDef) and x.name == "_se_trades")
_se = _ast.get_source_segment(raw_src, _node)
assert _se.count(A_KD) == 1, _se.count(A_KD)
for tag, quelle in (("ROH ", _se), ("ADPT", mod["patched_src"])):
    assert quelle.count(A_KD) == 1, (tag, quelle.count(A_KD))
    _ns = dict(engine.__dict__)
    _ns["_TRACE"] = []
    _ns["_hook"] = DEFAULT_ADAPTER
    _ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
    exec(compile(quelle.replace(A_KD, A_KD_NEW, 1), f"<kd_{tag}>", "exec"),
         _ns)
    _orig = engine._se_trades
    engine._se_trades = _ns["_se_trades"]
    try:
        engine._se_trades(copy.deepcopy(mod["scan"]), cfg)
    finally:
        engine._se_trades = _orig
    zeilen = [z for z in _ns["_TRACE"] if 990 <= z[0] <= 1005]
    print(f"  --- {tag}: " + " | ".join(
        f"{k}/{r[:1]}:{kid}" for k, r, kid in zeilen))

print("\n=== L) GEGENPROBE: Q29-Schwelle VARIANTEN (Adapter-Lauf) ===")
import dataclasses

for pct in (0.0, 10.0, 25.0, 50.0, 100.0):
    _cfg = dataclasses.replace(cfg, quartil_distanz_pct=pct)
    _ns = dict(engine.__dict__)
    _ns["_hook"] = DEFAULT_ADAPTER
    _ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
    exec(compile(ns["patched_src_backup"], "<se_trades_pct>", "exec"), _ns)
    _orig = engine._se_trades
    engine._se_trades = _ns["_se_trades"]
    try:
        V, st = engine._se_trades(copy.deepcopy(mod["scan"]), _cfg)
    finally:
        engine._se_trades = _orig
    print(f"  quartil_distanz_pct {pct:5.1f}: {len(V):2d} / "
          f"{sum(t.r for t in V):+10.6f} R | Sperren "
          f"{st['quartil_blockiert']:3d}")
