# -*- coding: utf-8 -*-
"""READ-ONLY Q29-Audit v2: Detail-Belege + Partition-Klaerung.

Ergaenzt _tmp_q29_audit.py (blockiert keine Ergebnisse, nur Erweiterung).
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


engine = load("ke_q29b", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n

V0, st0 = engine._se_trades(copy.deepcopy(scan), cfg)

print("=== A) ROHLISTE Q29 ===")
ql = st0["quartil_liste"]
print(f"  len(quartil_liste) = {len(ql)}")
RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+"
                r"basis=([\d.]+)\s+sweep=([\d.]+)")
q, unparsed = [], []
for s in ql:
    m = RE.search(s)
    if m:
        q.append((int(m.group(1)), m.group(2), int(m.group(3)),
                  float(m.group(4)), float(m.group(5))))
    else:
        unparsed.append(s)
print(f"  geparst {len(q)} | ungeparst {len(unparsed)}")
for s in unparsed:
    print(f"    UNPARSED: {s!r}")
print(f"  Trace-Bars: {sorted(x[0] for x in q)}")

print("\n=== B) H2-Q29-SPERREN im Detail (bar >= %d) ===" % box_end)
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
for (k, richtung, kid, basis, sweep) in sorted(q):
    if k < box_end:
        continue
    ex_hi = float(hi[:k + 1].max())
    ex_lo = float(lo[:k + 1].min())
    sp = ex_hi - ex_lo
    d = ((ex_hi - sweep) if richtung == "SHORT" else (sweep - ex_lo)) / sp * 100
    print(f"  bar {k:4d} {richtung:5s} K{kid:3d} basis={basis:9.4f} "
          f"sweep={sweep:9.4f} | ex_lo {ex_lo:7.3f} ex_hi {ex_hi:7.3f} "
          f"spanne {sp:5.3f} | distanz {d:6.2f} % <= 25 -> SPERRE")

print("\n=== C) V0-TRADES im Detail ===")
print(f"  {'bar':>5} {'entry':>6} {'kid':>4} {'richtung':>8} "
      f"{'stil':>16} {'r':>10}")
for t in sorted(V0, key=lambda t: t.entry_bar):
    print(f"  {t.bar:5d} {t.entry_bar:6d} {t.kid:4d} {t.richtung:>8s} "
          f"{getattr(t, 'stil', '?'):>16} {t.r:+10.6f}")
print(f"  Summe V0 = {len(V0)} / {sum(t.r for t in V0):+.6f} R")

for label, key in (("entry_bar", lambda t: t.entry_bar),
                   ("bar (Setup)", lambda t: t.bar)):
    a = [t for t in V0 if key(t) < box_end]
    b = [t for t in V0 if key(t) >= box_end]
    print(f"  Split nach {label:12s}: "
          f"H1 {len(a)}/{sum(t.r for t in a):+.6f} | "
          f"H2 {len(b)}/{sum(t.r for t in b):+.6f}")

print("\n=== D) SUBSET-SUCHE: welches H2-Praedikat ergibt 7/+7.902085 ? ===")
ziele = {"V01_H2": 7.902085, "V014_H2": 22.285802}
cands = {
    "bar>=640": lambda t: t.bar >= 640,
    "entry_bar>=640": lambda t: t.entry_bar >= 640,
    "bar>=644": lambda t: t.bar >= 644,
    "entry_bar>=644": lambda t: t.entry_bar >= 644,
}
for name, pred in cands.items():
    h2 = [t for t in V0 if pred(t)]
    tag = ""
    for z, v in ziele.items():
        if abs(sum(t.r for t in h2) - v) < 1e-5:
            tag = f"  <== {z}"
    print(f"  {name:16s}: {len(h2):2d} / {sum(t.r for t in h2):+.6f}{tag}")

print("\n=== E) Q29-AUS, nur H2-Delta im Detail ===")
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
A_Q = "        return distanz <= cfg.quartil_distanz_pct"
assert src.count(A_Q) == 1
ns = dict(engine.__dict__)
exec(compile(src.replace(A_Q, "        return True"),
             "<se_trades_q29aus>", "exec"), ns)
engine._se_trades = ns["_se_trades"]
V1, _ = engine._se_trades(copy.deepcopy(scan), cfg)
k0 = {t.entry_bar: t for t in V0}
print("  NEU (nur Q29-aus erzeugt):")
for t in sorted(V1, key=lambda t: t.entry_bar):
    if t.entry_bar not in k0:
        print(f"    bar {t.bar:4d} entry {t.entry_bar:4d} K{t.kid:3d} "
              f"{t.richtung:5s} {t.r:+9.6f}  "
              f"{'(H2)' if t.entry_bar >= box_end else '(H1)'}")
print(f"  Summe NEU = {sum(t.r for t in V1 if t.entry_bar not in k0):+.6f} R")
