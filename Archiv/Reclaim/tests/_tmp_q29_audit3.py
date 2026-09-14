# -*- coding: utf-8 -*-
"""READ-ONLY Q29-Audit v3: Klaerung bar 998 (57 vs 56) + Durchstich-Geometrie.

Ergaenzung zu _tmp_q29_audit.py / _tmp_q29_audit2.py. Keine Engine-Aenderung.
"""
from __future__ import annotations

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


engine = load("ke_q29c", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n
V0, st0 = engine._se_trades(copy.deepcopy(scan), cfg)

print("=== F) HERKUNFT BAR 998 (Protokoll 57 vs. Trace 56) ===")
for name in ("quartil_liste", "blocker_liste", "zyklus_liste",
             "stacking_liste", "frisch_liste", "promotion_liste"):
    lst = st0.get(name) or []
    treffer = [s for s in lst if re.search(r"bar\s+(99[0-9]|100[0-9])", s)]
    print(f"  {name:16s}: gesamt {len(lst):3d} | Treffer 990-1009: "
          f"{len(treffer)}")
    for s in treffer:
        print(f"      {s}")
print("  uebrige stats-Keys:", sorted(st0.keys()))
for k in sorted(st0.keys()):
    v = st0[k]
    if isinstance(v, int):
        print(f"    {k} = {v}")

print("\n=== G) DURCHSTICH-/RECLAIM-GEOMETRIE K60/K62/K77/K79/K82 (900..1060) ===")
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
for kid in (60, 62, 77, 79, 82):
    e = by_kid.get(kid)
    if e is None:
        print(f"  K{kid}: nicht im Katalog")
        continue
    print(f"  --- K{kid} seite={e.seite} piv={e.erster_pivot_bar} "
          f"geb={e.geburts_bar} wicks={[(b, round(p, 3)) for b, p in e.wicks]}")
    events = []
    for k in range(900, 1061):
        if not e.ist_aktiv_bei(k):
            continue
        b = e.basis_bei(k)
        durch = lo[k] < b if e.seite == "UNTEN" else hi[k] > b
        if durch:
            events.append((k, b, lo[k], hi[k], cl[k]))
    if not events:
        print("      kein Durchstich 900..1060")
    for (k, b, l_, h_, c_) in events:
        print(f"      bar {k:4d} basis {b:8.4f} lo {l_:8.4f} hi {h_:8.4f} "
              f"cl {c_:8.4f} | {'cl>basis RECLAIM' if c_ > b else 'cl<basis offen'}")

print("\n=== H) KONSISTENZ Q29-LOG vs. Neuberechnung ===")
RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+"
                r"basis=([\d.]+)\s+sweep=([\d.]+)")
abw = []
for s in st0["quartil_liste"]:
    m = RE.search(s)
    k, richtung, sweep = int(m.group(1)), m.group(2), float(m.group(5))
    ex_hi = float(hi[:k + 1].max())
    ex_lo = float(lo[:k + 1].min())
    sp = ex_hi - ex_lo
    dd = ((ex_hi - sweep) if richtung == "SHORT" else (sweep - ex_lo)) / sp * 100
    if dd <= cfg.quartil_distanz_pct:
        abw.append((k, richtung, round(dd, 3)))
print(f"  Sperren {len(st0['quartil_liste'])} | davon inkonsistent "
      f"(distanz <= 25 obwohl gesperrt): {len(abw)}")
for a in abw[:10]:
    print("   ", a)
alle = sorted(int(RE.search(s, x).group(1)) for x in st0["quartil_liste"])
PROT = [709, 939, 950, 951, 959, 961, 962, 991, 992, 997, 998, 1002, 1028,
        1029, 1030, 1031, 1056, 1072, 1073, 1103, 1104, 1145, 1146, 1153,
        1154, 1155, 1156, 1157, 1158, 1163, 1164, 1171]
h2_tr = sorted(b for b in alle if b >= box_end)
print(f"  H2: Trace {len(h2_tr)} vs. Protokoll "
      f"{len(PROT)} | nur im Protokoll: "
      f"{sorted(set(PROT) - set(h2_tr))} | nur im Trace: "
      f"{sorted(set(h2_tr) - set(PROT))}")
print(f"  H1: Trace {len([b for b in alle if b < box_end])} vs. Protokoll 25")
print(f"  gesamt: Trace {len(alle)} vs. Marker 57")
