# -*- coding: utf-8 -*-
"""READ-ONLY: Trace der PRODUKTIONS-Kette (AST-Patch + Adapter V017).

Instrumentiert ``patched_src`` (den im Renderer erzeugten RAM-Patch) mit reinen
Trace-Insertionen und faehrt ihn im Original-Namespace ``ns``. Damit ist die
Aussage deckungsgleich mit dem arretierten V017-Lauf (Kontrolle 17/+65.835576).
"""
from __future__ import annotations

import copy
import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
OUT = ROOT / "test" / "_tmp_explo_prodtr_out.txt"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]

mod = types.ModuleType("explo_prodtr")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_prodtr>", "exec"), ns)
sys.argv = _old

PNS: Dict = ns["ns"]
scan0 = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
SRC = ns["patched_src"]

INS = '''    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar

    _T_BARS = (set(range(1025, 1077)) | set(range(1100, 1131))
               | set(range(1205, 1216)) | set(range(1245, 1275)))

    def _tw(*a: object) -> None:
        if k not in _T_BARS:
            return
        with open(_TRACE_PATH, "a", encoding="utf-8") as _fh:
            _fh.write(" ".join(str(x) for x in a) + "\\n")
'''

REPL: List[tuple] = [
    # (0) Infrastruktur
    ("    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar\n",
     INS),

    # (1) Kandidat
    ("            kd = _kandidat(richtung, k, sweep_px)\n",
     "            kd = _kandidat(richtung, k, sweep_px)\n"
     "            if kd is None:\n"
     "                _tw(\"    -> kd None (Kette endet in _kandidat)\")\n"
     "            _tw(\"== bar\", k, richtung, \"sweep\", round(sweep_px, 4),\n"
     "                \"kd\", (kd.kid if kd is not None else None))\n"),

    # (2) Pool nach Sortierung
    ("        pool.sort(key=lambda e: _basis_wirksam(e, k),\n"
     "                  reverse=(seite == \"OBEN\"))\n",
     "        pool.sort(key=lambda e: _basis_wirksam(e, k),\n"
     "                  reverse=(seite == \"OBEN\"))\n"
     "        if richtung == \"LONG\" and k in _T_BARS:\n"
     "            for _p in pool:\n"
     "                _tw(\"    POOL K\", _p.kid, \"wirksam\",\n"
     "                    round(_basis_wirksam(_p, k), 4), \"dist%\",\n"
     "                    round((_basis_wirksam(_p, k) - sweep_px)\n"
     "                          / _basis_wirksam(_p, k) * 100.0, 4),\n"
     "                    \"touch\", _p.touch_conf(k))\n"),

    # (3) Kandidat-Rueckgaben
    ("            if dist > cfg.max_sweep_ueberdehnung_pct:\n"
     "                return None                     # Ueberdehnung, kein Reclaim\n",
     "            if dist > cfg.max_sweep_ueberdehnung_pct:\n"
     "                _tw(\"    -> None: UEBERDEHNUNG K\", e.kid,\n"
     "                    \"dist%\", round(dist, 4), \">\",\n"
     "                    cfg.max_sweep_ueberdehnung_pct)\n"
     "                return None                     # Ueberdehnung, kein Reclaim\n"),
    ("            if dist < 0.0:\n"
     "                if _lebt(e, k):\n"
     "                    return None                 # lebende Wand nicht erreicht\n",
     "            if dist < 0.0:\n"
     "                if _lebt(e, k):\n"
     "                    _tw(\"    -> None: LEBENDE WAND NICHT ERREICHT K\",\n"
     "                        e.kid, \"dist%\", round(dist, 4))\n"
     "                    return None                 # lebende Wand nicht erreicht\n"),
    ("        if not pool:\n"
     "            return None\n"
     "        pool.sort(key=lambda e: _basis_wirksam(e, k),\n",
     "        if not pool:\n"
     "            _tw(\"    -> None: LEERER POOL\")\n"
     "            return None\n"
     "        pool.sort(key=lambda e: _basis_wirksam(e, k),\n"),

    # (4) M6
    ("            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)\n",
     "            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)\n"
     "            _tw(\"    M6-Blocker K\",\n"
     "                (None if blk is None else\n"
     "                 (blk.kid, round(_basis_wirksam(blk, k), 4))))\n"),

    # (5) Q29
    ("            if not _im_aussenquartil(richtung, k, sweep_px):\n",
     "            _tw(\"    Q29 dist%\",\n"
     "                round((sweep_px - float(np.min(lo[:k + 1])))\n"
     "                      / (float(np.max(hi[:k + 1]))\n"
     "                         - float(np.min(lo[:k + 1]))) * 100.0, 4),\n"
     "                \"grenze\", cfg.quartil_distanz_pct)\n"
     "            if not _im_aussenquartil(richtung, k, sweep_px):\n"),

    # (6) Stufe / F3 / Zyklus
    ("            if stufe_n == 0:\n",
     "            _tw(\"    STUFE\", stufe_n, stufe_name, \"basis\",\n"
     "                round(basis, 4), \"lo[k]\", round(float(lo[k]), 4))\n"
     "            if stufe_n == 0:\n"),
    ("            if k <= kd.letzter_sweep_bar:\n",
     "            _tw(\"    F3 letzter_sweep_bar\", kd.letzter_sweep_bar,\n"
     "                \"->\", k <= kd.letzter_sweep_bar)\n"
     "            if k <= kd.letzter_sweep_bar:\n"),
    ("            _vor_zeit = letzter_trade.get(kd.kid)\n",
     "            _vor_zeit = letzter_trade.get(kd.kid)\n"
     "            _tw(\"    ZYKLUS vor\",\n"
     "                (None if _vor_zeit is None else _vor_zeit.entry_bar),\n"
     "                \"entry_bar\", entry_bar, \"grenze\",\n"
     "                cfg.retest_zyklus_bars)\n"),

    # (7) Gegenkante
    ("            geg = _gegenkante(richtung, k)\n",
     "            geg = _gegenkante(richtung, k)\n"
     "            _tw(\"    GEGNER\",\n"
     "                (None if geg is None else\n"
     "                 (geg.kid, round(geg.basis_bei(k), 4))))\n"),

    # (8) Hook-2 (Adapter)
    ("            _h2 = _hook.hook_2_ziel(k, richtung)\n",
     "            _h2 = _hook.hook_2_ziel(k, richtung)\n"
     "            _tw(\"    HOOK2 modus\", _h2.modus,\n"
     "                \"ziel\", _h2.ziel_preis, \"gegen_basis\",\n"
     "                round(gegen_basis, 4))\n"),

    # (9) POC + Dedup
    ("            if not (unter < poc < ober):\n",
     "            _tw(\"    POC\", round(poc, 4), \"unter\", round(unter, 4),\n"
     "                \"ober\", round(ober, 4))\n"
     "            if not (unter < poc < ober):\n"),
    ("            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n",
     "            _tw(\"    DEDUP\", entry_bar in getradete_entry_bars,\n"
     "                \"sl\", round(sl, 4), \"entry\", round(float(op[entry_bar]), 4),\n"
     "                \"poc\", round(poc, 4), \"tp2\", round(tp2, 4))\n"
     "            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n"),
    ("            setups.append(setup)\n",
     "            _tw(\"    >>> TRADE\", k, \"K\", kd.kid, \"entry_bar\",\n"
     "                entry_bar, \"r\", round(setup.r, 6))\n"
     "            setups.append(setup)\n"),
]

probe = SRC
for old, new in REPL:
    cnt = probe.count(old)
    if cnt != 1:
        raise SystemExit(f"ANKER NICHT EINDEUTIG ({cnt}x): {old[:60]!r}")
    probe = probe.replace(old, new)

OUT.write_text("", encoding="utf-8")
PNS["_TRACE_PATH"] = str(OUT)
PNS["_hook"] = adapter
exec(compile(probe, "<se_trades_prodtrace>", "exec"), PNS)
setups, stats = PNS["_se_trades"](copy.deepcopy(scan0), cfg0)
print(f"[check] Trace-Lauf {len(setups)} Trades | R1 = "
      f"{sum(t.r for t in setups):+.6f} "
      f"(Soll 17 / +65.835576)")

import pandas as pd  # noqa: E402

ts = pd.to_datetime(scan0["d"]["ts"])
lines = OUT.read_text(encoding="utf-8").splitlines()
print(f"[out] {OUT.name}: {len(lines)} Zeilen")

cur: List[str] = []
for line in lines:
    if line.startswith("== bar"):
        if cur:
            print("\n".join(cur))
        cur = [line]
    else:
        cur.append(line)
if cur:
    print("\n".join(cur))
