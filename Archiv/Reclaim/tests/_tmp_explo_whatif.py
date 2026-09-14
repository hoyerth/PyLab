# -*- coding: utf-8 -*-
"""READ-ONLY-WHAT-IF: Welche Regel unterdrueckt die vier avisierten H2-Trades?

Basis ist EXAKT der Produktionslauf: ``V1_aktiv`` entsteht im Renderer aus dem
AST-gepatchten ``_se_trades`` (RAM-Patch, Z. 462-563) mit gebundenem
``PhasenRegimeAdapter`` (V017) und ``copy.deepcopy(scan)``. Dieses Skript nutzt
denselben ``ns``-Namespace, denselben ``patched_src`` und dieselbe Aufrufart.

Szenarien (nur im RAM; die Engine-Datei bleibt byte-identisch):
  S0  Ist (V017)                              -> Kontrolle 17 Trades / +65.835576
  S1  Q29-Schwelle 200 % (Niemandsland aus)
  S2  S1 + Schlaf-Fenster K82 geloescht
  S3  S2 + K85 (Aussenwand) aus dem Pool
  S4  S3 + min_touches_handelbar = 2
  S5  nur Schlaf-Fenster K82 weg (Q29 scharf)
  S6  Ueberdehnung 0.60 -> 0.80
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

ZIEL_TRADES = 17
ZIEL_R1 = 65.835576

mod = types.ModuleType("explo_whatif")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_whatif>", "exec"), ns)
sys.argv = _old

import pandas as pd  # noqa: E402

scan0 = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
PATCHED = ns["patched_src"]
# ACHTUNG: der Kopf bindet den Namen ``ns`` auf ``dict(engine.__dict__)``
# (Renderer Z. 566) -- GENAU dieser Namespace traegt den RAM-Patch. Meine
# eigene Referenz ``ns`` zeigt weiterhin auf den Modul-Dict des Kopfes.
PNS: Dict = ns["ns"]
ts = pd.to_datetime(scan0["d"]["ts"])


def lauf(scan_obj: Dict, cfg_obj, hook) -> List:
    """Produktionsidentischer Aufruf: gepatchte _se_trades + deepcopy(scan)."""
    PNS["_hook"] = hook
    exec(compile(PATCHED, "<se_trades_whatif>", "exec"), PNS)
    setups, _stats = PNS["_se_trades"](copy.deepcopy(scan_obj), cfg_obj)
    return setups


def mit_k82_ohne_schlaf(scan_obj: Dict, ohne_k85: bool = False) -> Dict:
    sc = copy.deepcopy(scan_obj)
    for coll in ("edges", "seeds"):
        for e in sc[coll]:
            if e.kid == 82:
                e.schlaf_windows.clear()
        if ohne_k85:
            sc[coll] = [e for e in sc[coll] if e.kid != 85]
    return sc


def report(name: str, setups: List, ab_bar: int = 1020) -> None:
    r = sum(t.r for t in setups)
    lst = sorted((t for t in setups if t.bar >= ab_bar), key=lambda t: t.bar)
    print(f"\n{name}\n    {len(setups)} Trades gesamt | R1 = {r:+.6f} | "
          f"{len(lst)} ab Bar {ab_bar}")
    for t in lst:
        print(f"      K{t.kid:<3} signal {t.bar:<5} {ts.iloc[t.bar]:%d.%m %H:%M}"
              f"  entry_bar {t.entry_bar:<5} {t.richtung:<5} {t.stufe:<14}"
              f" entry {t.entry:.4f} sl {t.sl:.4f} tp2 {t.tp2:.4f}"
              f" r {t.r:+.6f}")


print("=" * 104)
print("WHAT-IF ab Produktionslauf V1_aktiv (AST-Patch + Adapter V017)")
print("=" * 104)

s0 = lauf(scan0, cfg0, adapter)
r0 = sum(t.r for t in s0)
ok = len(s0) == ZIEL_TRADES and abs(r0 - ZIEL_R1) < 1e-5
print(f"\nS0  Ist (Kontrolle)  : {len(s0)} Trades | R1 = {r0:+.6f} | "
      f"Soll {ZIEL_TRADES} / {ZIEL_R1:+.6f} -> OK: {ok}")
if not ok:
    raise SystemExit("Kontrolle fehlgeschlagen -- What-if ungueltig.")

cfg_s1 = dataclasses.replace(cfg0, quartil_distanz_pct=200.0)
report("S1  Q29 aus (200 %)", lauf(scan0, cfg_s1, adapter))
report("S2  Q29 aus + Schlafffenster K82 weg",
       lauf(mit_k82_ohne_schlaf(scan0), cfg_s1, adapter))
report("S3  S2 + K85 (Aussenwand) aus dem Pool",
       lauf(mit_k82_ohne_schlaf(scan0, ohne_k85=True), cfg_s1, adapter))
report("S4  S3 + min_touches_handelbar = 2",
       lauf(mit_k82_ohne_schlaf(scan0, ohne_k85=True),
            dataclasses.replace(cfg_s1, min_touches_handelbar=2), adapter))
report("S5  nur Schlafffenster K82 weg (Q29 scharf)",
       lauf(mit_k82_ohne_schlaf(scan0), cfg0, adapter))
report("S6  Ueberdehnung 0.60 -> 0.80",
       lauf(scan0, dataclasses.replace(cfg0,
                                       max_sweep_ueberdehnung_pct=0.80),
            adapter))
report("S7  Q29 25 -> 70 %",
       lauf(scan0, dataclasses.replace(cfg0, quartil_distanz_pct=70.0),
            adapter))
print("\n" + "=" * 104)
