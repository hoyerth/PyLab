# -*- coding: utf-8 -*-
"""READ-ONLY: Diff IST vs. P12-aktiv -- WELCHE Trades entfallen genau?"""
from __future__ import annotations

import copy
import dataclasses
import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
mod = types.ModuleType("p12diff")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_p12d>", "exec"), ns)
sys.argv = _old

import pandas as pd  # noqa: E402

PNS: Dict = ns["ns"]
scan = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
SRC: str = ns["patched_src"]
P9 = ns["P9"]
P12 = ns["P12_RESERVE"]
ts = pd.to_datetime(scan["d"]["ts"])


def lauf(hook) -> List:
    PNS["_hook"] = hook
    exec(compile(SRC, "<p12d>", "exec"), PNS)
    got, _st = PNS["_se_trades"](copy.deepcopy(scan), cfg0)
    return got


a = lauf(adapter)
b = lauf(dataclasses.replace(adapter, segmente=(P9, P12)))
ka = {(t.bar, t.kid) for t in a}
kb = {(t.bar, t.kid) for t in b}
print("=" * 100)
print(f"IST (nur P9)      : {len(a):2d} Trades / {sum(t.r for t in a):+.6f} R")
print(f"P9 + P12          : {len(b):2d} Trades / {sum(t.r for t in b):+.6f} R")
print("=" * 100)
print("\nNUR IN IST (entfallen durch P12):")
for t in sorted(a, key=lambda x: x.bar):
    if (t.bar, t.kid) not in kb:
        print(f"  K{t.kid:<3} {t.richtung:<5} signal {t.bar:<5} "
              f"{ts.iloc[t.bar]:%d.%m. %H:%M} entry_bar {t.entry_bar:<5} "
              f"r {t.r:+.6f}")
print("\nNUR IN P9+P12 (neu):")
for t in sorted(b, key=lambda x: x.bar):
    if (t.bar, t.kid) not in ka:
        print(f"  K{t.kid:<3} {t.richtung:<5} signal {t.bar:<5} "
              f"{ts.iloc[t.bar]:%d.%m. %H:%M} entry_bar {t.entry_bar:<5} "
              f"r {t.r:+.6f}")
print("\nIN BEIDEN, aber mit ANDEREM R (Kollision der Entry-Bars):")
ra = {(t.bar, t.kid): t for t in a}
for t in sorted(b, key=lambda x: x.bar):
    if (t.bar, t.kid) in ra and abs(ra[(t.bar, t.kid)].r - t.r) > 1e-9:
        print(f"  K{t.kid} signal {t.bar}: IST r {ra[(t.bar, t.kid)].r:+.6f} "
              f"-> P12 r {t.r:+.6f}")

print("\n" + "=" * 100)
print("TRADELISTE P9+P12 (vollstaendig)")
print("=" * 100)
for t in sorted(b, key=lambda x: x.bar):
    print(f"  K{t.kid:<3} {t.richtung:<5} signal {t.bar:<5} "
          f"{ts.iloc[t.bar]:%d.%m. %H:%M} entry_bar {t.entry_bar:<5} "
          f"{t.stufe:<14} r {t.r:+.6f}")
print("=" * 100)
