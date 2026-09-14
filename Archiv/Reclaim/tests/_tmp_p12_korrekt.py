# -*- coding: utf-8 -*-
"""READ-ONLY: P12-KOMBINATIONEN -- KORRIGIERTER HARNESS.

FEHLER IM VORLAUF (dokumentiert, weil lehrreich): ``segmente=(P9, P12)``
ersetzte das AKTIVE Segment ``P9_DIRECT_69_87`` (Override 69.87) durch das
override-lose ``P9``. Folge: alle 4 V017-Zusatztrades fielen weg und das
Ergebnis war exakt der v0.1-Basissatz (14 / +47.815697 R). Richtig ist
``tuple(adapter.segmente) + (P12,)`` -- ANHAENGEN, nie neu bauen.
"""
from __future__ import annotations

import copy
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
mod = types.ModuleType("p12korr")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_p12k>", "exec"), ns)
sys.argv = _old

import pandas as pd  # noqa: E402

PNS: Dict = ns["ns"]
scan = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
SRC: str = ns["patched_src"]
P12 = ns["P12_RESERVE"]
ts = pd.to_datetime(scan["d"]["ts"])
n = ns["n"]
BOX = int(ns["box_end"])

print("=" * 104)
print("GUARD: Welches Segment traegt der aktive Adapter?")
print("=" * 104)
for seg in adapter.segmente:
    print(f"  {seg.phasen_id} {seg.start_bar}..{seg.end_bar} | "
          f"Decke K{seg.decke.kid} {seg.decke.provenienz_basis:.4f} "
          f"override={seg.decke.niveau_override} | "
          f"Boden K{seg.boden.kid} {seg.boden.provenienz_basis:.4f}")
    assert seg.decke.hat_override(), "aktives Segment OHNE Override (falsch!)"
print("  -> aktives Segment traegt den Override: OK")

AD_P12 = dataclasses.replace(adapter,
                             segmente=tuple(adapter.segmente) + (P12,))
print(f"  -> P12-Variante: {[s.phasen_id for s in AD_P12.segmente]}")

M6_OLD = "            if e is kd or not _existiert(e, k):\n"
M6_NEW = ("            if e is kd or not _existiert(e, k) or not _lebt(e, k):"
          "\n")


def variant(m6_lebt: bool = False) -> str:
    s = SRC
    if m6_lebt:
        assert s.count(M6_OLD) == 1
        s = s.replace(M6_OLD, M6_NEW)
    return s


def lauf(src: str, cfg, hook) -> List:
    PNS["_hook"] = hook
    exec(compile(src, "<p12k>", "exec"), PNS)
    got, _st = PNS["_se_trades"](copy.deepcopy(scan), cfg)
    return got


def zeile(lbl: str, got: List) -> None:
    h1 = [t for t in got if t.entry_bar < BOX]
    h2 = [t for t in got if t.entry_bar >= BOX]
    ziel = [t for t in got if t.bar >= 1021]
    print(f"  {lbl:<40} {len(got):>3} | {sum(t.r for t in got):>+11.6f} | "
          f"{len(h1):>2}/{sum(t.r for t in h1):>+10.6f} | "
          f"{len(h2):>2}/{sum(t.r for t in h2):>+10.6f} | {len(ziel):>4}")
    for t in ziel:
        print(f"        K{t.kid:<3} {t.richtung:<5} signal {t.bar:<5} "
              f"{ts.iloc[t.bar]:%d.%m %H:%M} entry {t.entry_bar:<5} "
              f"{t.stufe:<14} r {t.r:+.6f}")


print("\n" + "=" * 104)
print("P12-KOMBINATIONEN (korrekt angehaengt)")
print("=" * 104)
print(f"  {'Variante':<40} Trd |          R1 |       H1 Trd/R | "
      f"      H2 Trd/R | Ziel")
print("  " + "-" * 104)
zeile("IST (nur P9_DIRECT)", lauf(SRC, cfg0, adapter))
zeile("K1  + P12 (nur Adapter)", lauf(SRC, cfg0, AD_P12))
zeile("K2  K1 + M6 lebend", lauf(variant(m6_lebt=True), cfg0, AD_P12))
zeile("K3  K2 + Ueberdehnung 0.80",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80),
           AD_P12))
zeile("K4  K3 + Q29 aus (200 %)",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80,
                               quartil_distanz_pct=200.0), AD_P12))
zeile("K5  K4 + V-S>=2",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80,
                               quartil_distanz_pct=200.0,
                               min_touches_handelbar=2), AD_P12))
print("=" * 104)
