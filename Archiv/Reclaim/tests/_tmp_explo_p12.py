# -*- coding: utf-8 -*-
"""READ-ONLY: Was oeffnet die H2-Reststrecke -- Regime-Vakuum oder Motorfilter?

Befund der Kette: fuer JEDEN Signal-Bar > 1020 liefert
``PhasenRegimeAdapter.hook_2_ziel`` den Modus ``BLOCKIERT`` (Regime-Vakuum),
weil nur P9 (848..1020) aktiv ist und ``P12_RESERVE`` (1171..1272) bewusst
NICHT in der Selektionsliste steht. Dieses Skript quantifiziert beide Hebel:
  A  Ist (V017)
  B  P12_RESERVE zusaetzlich aktiv (P9 + P12)
  C  B + Q29 aus (200 %)
  D  C + Ueberdehnung 0.80 + touches >= 2 + K82-Schlaffenster weg
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

mod = types.ModuleType("explo_p12")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_p12>", "exec"), ns)
sys.argv = _old

PNS: Dict = ns["ns"]
scan0 = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
PATCHED = ns["patched_src"]
P9 = ns["P9"]
P12 = ns["P12_RESERVE"]
ts = ns["pd"] if False else None  # noqa: F841

import pandas as pd  # noqa: E402

ts = pd.to_datetime(scan0["d"]["ts"])
n = ns["n"]

print("=" * 104)
print("P12-WHAT-IF | H2-Reststrecke")
print("=" * 104)

# --- Adapter-Diagnose: wo autorisiert der Ist-Adapter? --------------------
print("\n[Adapter] Phasen-Scope / Segmente")
print(f"    start_scope_bar = {adapter.start_scope_bar}")
for seg in adapter.segmente:
    print(f"    aktiv: {seg.phasen_id}  {seg.start_bar}..{seg.end_bar}")
print(f"    Reserve (nicht aktiv): {P12.phasen_id} "
      f"{P12.start_bar}..{P12.end_bar}  Boden K{P12.boden.kid} "
      f"{P12.boden.provenienz_basis:.4f}  Decke K{P12.decke.kid} "
      f"{P12.decke.provenienz_basis:.4f}  long-Ziel "
      f"{P12.ziel_preis_long:.4f}  short-Ziel {P12.ziel_preis_short:.4f}")

adapter_p12 = dataclasses.replace(adapter, segmente=(P9, P12))
print("\n[Adapter] Modus-Vergleich je Bar (LONG-Ziel)")
print(f"    {'Bar':>5} {'Zeit':<14} {'Ist-Modus':<10} {'Ist-Ziel':>9} "
      f"{'P12-Modus':<10} {'P12-Ziel':>9}")
for k in (1020, 1021, 1072, 1122, 1172, 1259, 1272, 1273):
    a = adapter.hook_2_ziel(k, "LONG")
    b = adapter_p12.hook_2_ziel(k, "LONG")
    print(f"    {k:>5} {ts.iloc[k]:%d.%m. %H:%M}   {a.modus.value:<10} "
          f"{str(a.ziel_preis):>9} {b.modus.value:<10} {str(b.ziel_preis):>9}")


def lauf(scan_obj: Dict, cfg_obj, hook) -> List:
    PNS["_hook"] = hook
    exec(compile(PATCHED, "<se_trades_p12>", "exec"), PNS)
    setups, _st = PNS["_se_trades"](copy.deepcopy(scan_obj), cfg_obj)
    return setups


def mut(scan_obj: Dict, clear_k82: bool = False,
        drop_k85: bool = False) -> Dict:
    sc = copy.deepcopy(scan_obj)
    for c in ("edges", "seeds"):
        for e in sc[c]:
            if e.kid == 82 and clear_k82:
                e.schlaf_windows.clear()
        if drop_k85:
            sc[c] = [e for e in sc[c] if e.kid != 85]
    return sc


def report(name: str, got: List, lo_bar: int = 1020, hi_bar: int = 1273) -> None:
    r = sum(t.r for t in got)
    lst = sorted((t for t in got if lo_bar <= t.bar <= hi_bar),
                 key=lambda t: t.bar)
    print(f"\n{name}\n    gesamt {len(got)} Trades | R1 = {r:+.6f} | "
          f"im Fenster {lo_bar}..{hi_bar}: {len(lst)}")
    for t in lst:
        print(f"      K{t.kid:<3} {t.richtung:<5} signal {t.bar:<5} "
              f"{ts.iloc[t.bar]:%d.%m. %H:%M}  entry_bar {t.entry_bar:<5} "
              f"{t.stufe:<14} entry {t.entry:.4f} sl {t.sl:.4f} "
              f"tp2 {t.tp2:.4f} r {t.r:+.6f}")


s0 = lauf(scan0, cfg0, adapter)
print(f"\n[Kontrolle] Ist: {len(s0)} Trades | R1 = {sum(t.r for t in s0):+.6f} "
      f"(Soll 17 / +65.835576)")

report("A  Ist (V017)", s0)
report("B  P9 + P12_RESERVE aktiv", lauf(scan0, cfg0, adapter_p12))
cfg_q = dataclasses.replace(cfg0, quartil_distanz_pct=200.0)
report("C  B + Q29 aus (200 %)", lauf(scan0, cfg_q, adapter_p12))
cfg_v = dataclasses.replace(cfg_q, max_sweep_ueberdehnung_pct=0.80,
                            min_touches_handelbar=2)
report("D  C + Ueberdehnung 0.80 + touches>=2 + K82 wach + ohne K85",
       lauf(mut(scan0, clear_k82=True, drop_k85=True), cfg_v, adapter_p12))
print("\n" + "=" * 104)
