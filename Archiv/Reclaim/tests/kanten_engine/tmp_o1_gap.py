# -*- coding: utf-8 -*-
"""READ-ONLY: Welche IDs deckt die O1-Akkumulationsschranke (Alter >= 96) auf?"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

B = ("        # --- §7.2 Teil 5: R21-Bereinigung (kausal bei Bar k, in-place) --\r\n"
     "        if cfg.r21_loeschung_aktiv:\r\n")
assert SRC.count(B) == 1
PREPASS = (
    "        if cfg.r21_loeschung_aktiv:\r\n"
    "            for _seite in (\"OBEN\", \"UNTEN\"):\r\n"
    "                _lb = [r for r in cluster[_seite] if _lebt_scan(r, k)]\r\n"
    "                if _lb:\r\n"
    "                    _mx = max(r.basis for r in _lb)\r\n"
    "                    _mn = min(r.basis for r in _lb)\r\n"
    "                    for _e in cluster[_seite]:\r\n"
    "                        if ((_seite == \"OBEN\" and _e.basis >= _mx)\r\n"
    "                                or (_seite == \"UNTEN\" and _e.basis <= _mn)):\r\n"
    "                            WAR_AUSSEN_IDS.add(_e.kid)\r\n"
    "\r\n")
V1 = SRC.replace(B, PREPASS + B, 1)

base = load("ke_v0", SRC)
alt = load("ke_v1", V1)
cfg = base.StraightEdgeHarnessKonfiguration()
base._se_scan("AUG", cfg)
v0 = set(base.WAR_AUSSEN_IDS)
alt._se_scan("AUG", cfg)
v1 = set(alt.WAR_AUSSEN_IDS)

print("WAR_AUSSEN_IDS: V0 =", len(v0), "| V1 =", len(v1))
print("Nur in V1 (durch Schranke verpasst):", sorted(v1 - v0))
print("Nur in V0:", sorted(v0 - v1))

sc = base._se_scan("AUG", cfg)
alle = {e.kid: e for e in list(sc["edges"]) + list(sc["seeds"])}
for kid in sorted(v1 - v0):
    e = alle.get(kid)
    if e:
        print(f"  K{kid:3d} {e.seite:5s} pivot={e.erster_pivot_bar:4d} "
              f"basis={e.basis:.3f} n={e.touch_anzahl} "
              f"geburts={e.geburts_bar}")
