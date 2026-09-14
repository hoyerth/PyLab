# -*- coding: utf-8 -*-
"""READ-ONLY: TRACE-DIFF IST vs. P9+P12 an denselben Bars.

Die Hooks sind an 903/980/1002 identisch -- trotzdem entfallen dort 4 Trades.
Dieses Skript instrumentiert ``patched_src`` und schreibt zwei Traces, die
zeilengenau verglichen werden.
"""
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
mod = types.ModuleType("tracediff")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_td>", "exec"), ns)
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

INS = '''    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar

    _T_BARS = set(range(895, 1010))

    def _tw(*a: object) -> None:
        if k not in _T_BARS:
            return
        with open(_TRACE_PATH, "a", encoding="utf-8") as _fh:
            _fh.write(" ".join(str(x) for x in a) + "\\n")
'''

REPL: List[tuple] = [
    ("    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar\n",
     INS),
    ("            kd = _kandidat(richtung, k, sweep_px)\n",
     "            kd = _kandidat(richtung, k, sweep_px)\n"
     "            _tw(\"== \", k, richtung, \"poolsort\",\n"
     "                \"freigabe\", _freigabe_kid, \"kd\",\n"
     "                (None if kd is None else kd.kid))\n"),
    ("            basis = _basis_wirksam(kd, k)\n",
     "            basis = _basis_wirksam(kd, k)\n"
     "            _tw(\"   basis\", round(basis, 4), \"raw\",\n"
     "                round(kd.basis_bei(k), 4))\n"),
    ("            if stufe_n == 0:\n",
     "            _tw(\"   STUFE\", stufe_n, stufe_name)\n"
     "            if stufe_n == 0:\n"),
    ("            if k <= kd.letzter_sweep_bar:\n",
     "            _tw(\"   F3\", kd.letzter_sweep_bar)\n"
     "            if k <= kd.letzter_sweep_bar:\n"),
    ("            _vor_zeit = letzter_trade.get(kd.kid)\n",
     "            _vor_zeit = letzter_trade.get(kd.kid)\n"
     "            _tw(\"   ZYKLUS vor\",\n"
     "                (None if _vor_zeit is None else _vor_zeit.entry_bar),\n"
     "                \"entry\", entry_bar)\n"),
    ("            geg = _gegenkante(richtung, k)\n",
     "            geg = _gegenkante(richtung, k)\n"
     "            _tw(\"   GEGNER\", (None if geg is None else geg.kid))\n"),
    ("            _h2 = _hook.hook_2_ziel(k, richtung)\n",
     "            _h2 = _hook.hook_2_ziel(k, richtung)\n"
     "            _tw(\"   H2\", _h2.modus.value, _h2.ziel_preis,\n"
     "                \"gegen_basis\", round(gegen_basis, 4))\n"),
    ("            if not (unter < poc < ober):\n",
     "            _tw(\"   POC\", round(poc, 4), round(unter, 4),\n"
     "                round(ober, 4))\n"
     "            if not (unter < poc < ober):\n"),
    ("            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n",
     "            _tw(\"   DEDUP\", entry_bar, entry_bar in getradete_entry_bars,\n"
     "                \"sl\", round(sl, 4), \"poc\", round(poc, 4),\n"
     "                \"tp2\", round(tp2, 4), \"risk\",\n"
     "                round(abs(sl - float(op[entry_bar])), 4))\n"
     "            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n"),
    ("            setups.append(setup)\n",
     "            _tw(\"   >>> TRADE\", k, kd.kid, entry_bar, round(setup.r, 6))\n"
     "            setups.append(setup)\n"),
]

probe = SRC
for old, new in REPL:
    cnt = probe.count(old)
    if cnt != 1:
        raise SystemExit(f"ANKER {cnt}x: {old[:50]!r}")
    probe = probe.replace(old, new)

OUT = ROOT / "test"
res: Dict[str, List[str]] = {}
for tag, hook in (("ist", adapter), ("p12", dataclasses.replace(
        adapter, segmente=(P9, P12)))):
    f = OUT / f"_tmp_tracediff_{tag}.txt"
    f.write_text("", encoding="utf-8")
    PNS["_TRACE_PATH"] = str(f)
    PNS["_hook"] = hook
    exec(compile(probe, "<td>", "exec"), PNS)
    got, _st = PNS["_se_trades"](copy.deepcopy(scan), cfg0)
    print(f"[{tag}] {len(got)} Trades / {sum(t.r for t in got):+.6f} R")
    res[tag] = f.read_text(encoding="utf-8").splitlines()

a, b = res["ist"], res["p12"]
print(f"\n[Trace] ist {len(a)} Zeilen | p12 {len(b)} Zeilen")
print("=" * 100)
print("ERSTE ABWEICHUNG im Trace")
print("=" * 100)
for i in range(max(len(a), len(b))):
    x = a[i] if i < len(a) else "<EOF>"
    y = b[i] if i < len(b) else "<EOF>"
    if x != y:
        print(f"  Zeile {i + 1}:")
        for j in range(max(0, i - 6), i):
            print(f"    [ist] {a[j]}")
        print(f"    [ist] {x}")
        print(f"    [p12] {y}")
        break
print("=" * 100)
