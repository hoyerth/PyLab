# -*- coding: utf-8 -*-
"""S3.2-Verifikation: Engine-Lauf auf BKZ -- box_end_bar, Trades, H1/H2.

Read-only Probe: laedt den Renderer-Kopf (ohne Plot) und liest den
Scan-/Trade-Zustand aus. Kein PNG wird erzeugt.

Aufruf:
    .venv\\Scripts\\python.exe test\\_tmp_s3_verify_engine.py
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"

# Renderer-Kopf bis zum Plot-Abschnitt ausfuehren (identisch zu _tmp_explo_laeufe.py).
marker = "# ---------------------------------------------------------------- Plot"
HEAD = RENDERER.read_text(encoding="utf-8").split(marker)[0]

mod = types.ModuleType("s3_verify")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
_mode = sys.argv[1] if len(sys.argv) > 1 else "V014"
sys.argv = ["t", "--mode", _mode] + sys.argv[2:]
try:
    exec(compile(HEAD, "<head>", "exec"), ns)
except AssertionError as _exc:
    # Erwartet: die jeweilige Konfiguration ist an die V017-Generation gebunden
    # und bricht fail-loud ab (Generationsbindung). Alle Messgroessen sind VOR
    # dem Assert bereits berechnet.
    print(f"[fail-loud erwartet, mode={_mode}] {type(_exc).__name__}: {_exc}")
finally:
    sys.argv = _old

print("=" * 78)
print("S3.2-VERIFIKATION (BKZ)")
print("=" * 78)
print(f"  n (Bars)          : {ns['n']}")
# `box_end` = Original-Grenze (vor dem Voll-Lauf-Override scan["box_end_bar"]=n).
be = ns["box_end"]
print(f"  box_end (H1/H2)   : {be}")
print(f"  scan[box_end_bar] : {ns['scan']['box_end_bar']}  (Voll-Lauf-Override)")

ts = ns["scan"]["d"]["ts"]
print(f"  ts[{be-1}]  : {ts.iloc[be-1]}")
print(f"  ts[{be}]    : {ts.iloc[be]}")
print(f"  ts[{be+1}]  : {ts.iloc[be+1]}")

for lbl in ("V0", "V1"):
    lst = ns.get(lbl, [])
    r = sum(t.r for t in lst)
    h1 = [t for t in lst if t.entry_bar < be]
    h2 = [t for t in lst if t.entry_bar >= be]
    print("-" * 78)
    print(f"  {lbl}: {len(lst)} Trades | R = {r:+.6f}")
    print(f"      H1 (entry_bar <  {be}): {len(h1)} / {sum(t.r for t in h1):+.6f}")
    print(f"      H2 (entry_bar >= {be}): {len(h2)} / {sum(t.r for t in h2):+.6f}")
    for t in sorted(h1, key=lambda x: x.bar):
        mark = "   <== GRENZTRADE" if 640 <= t.entry_bar < 644 else ""
        print(f"        [H1] K{t.kid:<3} {t.richtung:<5} sig {t.bar:<5} "
              f"entry_bar {t.entry_bar:<5} r {t.r:+.6f}{mark}")
    for t in sorted(h2, key=lambda x: x.bar):
        mark = "   <== GRENZTRADE" if 640 <= t.entry_bar < 644 else ""
        print(f"        [H2] K{t.kid:<3} {t.richtung:<5} sig {t.bar:<5} "
              f"entry_bar {t.entry_bar:<5} r {t.r:+.6f}{mark}")

print("=" * 78)
print("V018-SOLLWERTE (gemessen)")
print("=" * 78)
for key in ("P9_BEITRAG", "NIVEAUWECHSEL", "QUARTETT_R", "RB", "R1", "R0",
            "NETTO_PREISWECHSEL"):
    if key in ns:
        print(f"  {key:<20}: {ns[key]}")
print(f"  len(V1_basis)      : {len(ns.get('V1_basis', []))}")
print(f"  len(V1)            : {len(ns.get('V1', []))}")
_q = ns.get("QUARTETT_R")
if "KONF" in ns:
    qb = ns["KONF"].quartett_bars
    print(f"  quartett_bars      : {qb}")
    q = {t.bar: t for t in ns.get("V1", []) if t.bar in qb}
    for b in qb:
        if b in q:
            print(f"    bar {b}: K{q[b].kid} r {q[b].r:+.6f}")
    print(f"  REFERENZ           : {ns.get('REFERENZ')}")
    print(f"  NEU                : {ns.get('NEU')}")
    print(f"  G4_MARKE           : {ns.get('G4_MARKE')}")
    print(f"  G4_TRADES          : {[(t.kid, t.bar, round(t.r, 6)) for t in ns.get('G4_TRADES', [])]}")
