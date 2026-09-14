# -*- coding: utf-8 -*-
"""READ-ONLY: WARUM aendert P12 (1171..1272) Trades bei Bar 903..1002?

Direkter Hook-Vergleich je Bar -- kein Engine-Lauf, nur Adapter-Aufrufe.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
import types
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
mod = types.ModuleType("hookdiff")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_hd>", "exec"), ns)
sys.argv = _old

import pandas as pd  # noqa: E402

scan = ns["scan"]
P9 = ns["P9"]
P12 = ns["P12_RESERVE"]
ad_ist = ns["adapter"]
ad_p12 = dataclasses.replace(ad_ist, segmente=(P9, P12))
ts = pd.to_datetime(scan["d"]["ts"])
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
edges = list(scan["edges"]) + list(scan["seeds"])
BY = {e.kid: e for e in edges}

print("=" * 104)
print("HOOK-VERGLEICH je Bar (Seiten UNTEN/OBEN, alle Kids im Pool)")
print("=" * 104)
for k in (903, 980, 981, 1002, 1020, 1021, 1172, 1259):
    print(f"\n--- Bar {k}  {ts.iloc[k]:%d.%m. %H:%M}  "
          f"H {hi[k]:.4f} L {lo[k]:.4f} ---")
    for ad, lbl in ((ad_ist, "IST (nur P9)"), (ad_p12, "P9 + P12")):
        seg = ad.aktive_phase_bei(k)
        h2 = ad.hook_2_ziel(k, "LONG")
        print(f"    {lbl:<12} aktive_phase="
              f"{None if seg is None else seg.phasen_id:<5} "
              f"| H2 LONG {h2.modus.value:<9} ziel={h2.ziel_preis}")
    for richtung, sweep in (("SHORT", float(hi[k])), ("LONG", float(lo[k]))):
        kanten: List[Tuple[int, float]] = []
        for e in edges:
            if e.seite != ("OBEN" if richtung == "SHORT" else "UNTEN"):
                continue
            kanten.append((e.kid, e.basis_bei(k)))
        f_ist = ad_ist.hook_1_freigabe_kid(k, sweep, richtung, kanten)
        f_p12 = ad_p12.hook_1_freigabe_kid(k, sweep, richtung, kanten)
        mark = "" if f_ist == f_p12 else "   <<< UNTERSCHIED"
        print(f"      {richtung:<5} sweep {sweep:>8.4f} | "
              f"H1-Freigabe IST {f_ist} | P9+P12 {f_p12}{mark}")

print("\n" + "=" * 104)
print("DAS ENTSCHEIDENDE PAAR: K67 und K73 an Bar 903/980/1002")
print("=" * 104)
for k in (903, 980, 1002):
    print(f"\n  Bar {k}: K67.basis={BY[67].basis_bei(k):.4f}  "
          f"K73.basis={BY[73].basis_bei(k):.4f}  hi={hi[k]:.4f}")
    for ad, lbl in ((ad_ist, "IST"), (ad_p12, "P9+P12")):
        f = ad.hook_1_freigabe_kid(
            k, float(hi[k]), "SHORT",
            [(e.kid, e.basis_bei(k)) for e in edges if e.seite == "OBEN"])
        print(f"    {lbl:<8} -> freigegeben: {f}")
print("=" * 104)
