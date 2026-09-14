# -*- coding: utf-8 -*-
"""READ-ONLY Q29-Audit: Blocks nach Region/Richtung + Gegenprobe ohne Q29.

Kein Schreiben von Dateien, keine Engine-Aenderung (In-Memory-Patch).
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name, path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_q29", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
print(f"quartil_distanz_pct = {cfg.quartil_distanz_pct}")
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n                      # In-Memory-Trace (Spez 52.0)

V0, st0 = engine._se_trades(copy.deepcopy(scan), cfg)
R0 = sum(t.r for t in V0)

RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+"
                r"basis=([\d.]+)\s+sweep=([\d.]+)")
q = []
for s in st0["quartil_liste"]:
    m = RE.search(s)
    if m:
        q.append((int(m.group(1)), m.group(2), int(m.group(3)),
                  float(m.group(4)), float(m.group(5))))

h1 = [x for x in q if x[0] < box_end]
h2 = [x for x in q if x[0] >= box_end]
print(f"\n=== A) Q29-BLOCKS (Trace ueber ALLE Bars) ===")
print(f"  gesamt {len(q)} | H1 (bar < {box_end}) {len(h1)} | "
      f"H2 (bar >= {box_end}) {len(h2)}")
for name, lst in (("H1", h1), ("H2", h2)):
    lang = [x for x in lst if x[1] == "LONG"]
    shrt = [x for x in lst if x[1] == "SHORT"]
    print(f"  {name}: LONG {len(lang)} | SHORT {len(shrt)}")
    print(f"    kids: "
          f"{sorted({x[2] for x in lst})}")
print(f"  H1-Bars: {sorted(x[0] for x in h1)}")
print(f"  H2-Bars: {sorted(x[0] for x in h2)}")

print(f"\n=== B) SCHWELLEN-ARITHMETIK (ex_hi/ex_lo kausal 0..k) ===")
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
for k in (600, 700, 934, 991, 1000, 1050, 1259):
    ex_hi = float(hi[:k + 1].max())
    ex_lo = float(lo[:k + 1].min())
    sp = ex_hi - ex_lo
    print(f"  bar {k:4d}: ex_lo {ex_lo:.3f} ex_hi {ex_hi:.3f} sp {sp:.3f} | "
          f"LONG-Schwelle {ex_lo + 0.25 * sp:.3f} | "
          f"SHORT-Schwelle {ex_hi - 0.25 * sp:.3f}")

print(f"\n=== C) GEGENPROBE: Q29 ABGESCHALTET (In-Memory) ===")
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
A_Q = "        return distanz <= cfg.quartil_distanz_pct"
A_Q_NEW = "        return True"
assert src.count(A_Q) == 1, src.count(A_Q)
ns = dict(engine.__dict__)
exec(compile(src.replace(A_Q, A_Q_NEW), "<se_trades_q29aus>", "exec"), ns)
engine._se_trades = ns["_se_trades"]
V1, st1 = engine._se_trades(copy.deepcopy(scan), cfg)
engine._se_trades = st0 and getattr(engine, "_se_trades")

R1 = sum(t.r for t in V1)
print(f"  V0 (Q29 aktiv) : {len(V0):2d} / {R0:+.6f} R")
print(f"  V1 (Q29 aus)   : {len(V1):2d} / {R1:+.6f} R   "
      f"delta {R1 - R0:+.6f} R")
h1_0 = [t for t in V0 if t.entry_bar < box_end]
h2_0 = [t for t in V0 if t.entry_bar >= box_end]
h1_1 = [t for t in V1 if t.entry_bar < box_end]
h2_1 = [t for t in V1 if t.entry_bar >= box_end]
print(f"  H1: {len(h1_0)}/{sum(t.r for t in h1_0):+.6f} -> "
      f"{len(h1_1)}/{sum(t.r for t in h1_1):+.6f}")
print(f"  H2: {len(h2_0)}/{sum(t.r for t in h2_0):+.6f} -> "
      f"{len(h2_1)}/{sum(t.r for t in h2_1):+.6f}")
k0 = {(t.bar, t.kid) for t in V0}
k1 = {(t.bar, t.kid) for t in V1}
print(f"  NEU durch Q29-aus : "
      f"{sorted((t.bar, t.kid, round(t.r, 4)) for t in V1 if (t.bar, t.kid) not in k0)}")
print(f"  ENTFAELLT         : "
      f"{sorted((t.bar, t.kid, round(t.r, 4)) for t in V0 if (t.bar, t.kid) not in k1)}")

print(f"\n=== D) KANTEN-BASIS an den Frage-Bars ===")
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
for kid in (60, 62, 77, 79, 82, 73, 67):
    e = by_kid.get(kid)
    if e is None:
        print(f"  K{kid}: nicht im Katalog")
        continue
    vals = " ".join(f"{k}:{e.basis_bei(k):.4f}" for k in (934, 991, 1000))
    print(f"  K{kid:3d} seite={e.seite:5s} e.basis={e.basis:.4f} "
          f"geb={e.geburts_bar} piv={e.erster_pivot_bar} "
          f"wicks={len(e.wicks)} | {vals}")
