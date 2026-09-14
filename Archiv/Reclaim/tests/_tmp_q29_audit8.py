# -*- coding: utf-8 -*-
"""READ-ONLY: Bar-fuer-Bar-Bild 985..1015 (Q29 aus) - existiert IRGENDEIN
gueltiges K77-Setup an 68.40? Nur In-Memory, Platte unberuehrt.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
sys.argv = ["tmp_q29_audit8"]
voll = REN.read_text(encoding="utf-8")
_i = voll.index("import matplotlib")
mod = {"__name__": "q29a8", "__file__": str(REN)}
sys.modules[mod["__name__"]] = type(sys)("q29a8")
exec(compile(voll[:voll.rindex("\n", 0, _i) + 1], str(REN), "exec"), mod)

engine, cfg, scan = mod["engine"], mod["cfg"], mod["scan"]
ADAPTER = mod["DEFAULT_ADAPTER"]
src0 = mod["patched_src"]
A_Q = "        return distanz <= cfg.quartil_distanz_pct"
A_KD = "            kd = _kandidat(richtung, k, sweep_px)"
A_ST = "            entry_bar = k + stufe_n"

src = src0.replace(A_Q, "        return True", 1)
src = src.replace(A_KD, A_KD + "\n            _P.append([k, richtung, "
                              "None if kd is None else kd.kid, None])", 1)
assert src.count(A_ST) == 1
src = src.replace(A_ST, "            _P[-1][3] = stufe_n\n" + A_ST, 1)
A_ZK = '                stats["zyklus_blockiert"] += 1'
assert src.count(A_ZK) == 1
src = src.replace(A_ZK, A_ZK + "\n                _ZK.append((k, richtung, "
                              "kd.kid, stufe_n))", 1)

_ns = dict(engine.__dict__)
_ns["_hook"] = ADAPTER
_ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
_ns["_P"] = []
_ns["_ZK"] = []
exec(compile(src, "<v>", "exec"), _ns)
orig = engine._se_trades
engine._se_trades = _ns["_se_trades"]
try:
    V, st = engine._se_trades(copy.deepcopy(scan), cfg)
finally:
    engine._se_trades = orig

print(f"  Q29 aus: {len(V)} Trades / {sum(t.r for t in V):+.6f} R")
print(f"  {'bar':>5} {'rich':>5} {'kid':>5} {'stufe':>6}  Gate")
for k, r, kid, stufe in _ns["_P"]:
    if not (985 <= k <= 1015):
        continue
    gates = [f"blocker+{st['blocker']}", ""]
    print(f"  {k:5d} {r:5s} {str(kid):>5} {str(stufe):>6}")
print("\n  kein_raum-Gruende 985..1015 (Q29 aus):")
print(f"    kein_raum gesamt {st['kein_raum']} | zyklus "
      f"{st['zyklus_blockiert']} | blocker {st['blocker']}")
print("  Zyklus-Sperren 988..1012:")
for z in _ns["_ZK"]:
    if 988 <= z[0] <= 1012:
        print("    ", z)
print("\n  Alle Bars, an denen K77 Kandidat war (gesamter Lauf):")
kk = [k for k, r, kid, s in _ns["_P"] if kid == 77]
print(f"    {kk}")
print("  Alle Bars, an denen K77 Kandidat war UND stufe>0:")
kk2 = [(k, r, s) for k, r, kid, s in _ns["_P"] if kid == 77 and s]
print(f"    {kk2}")
