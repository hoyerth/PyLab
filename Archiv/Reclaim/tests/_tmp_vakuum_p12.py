# -*- coding: utf-8 -*-
"""READ-ONLY: VAKUUM-KARTE + P12-Kombinationen (H1/H2/Ziel getrennt).

Befund aus _tmp_phasenversatz.py: alle vier Motoren-Hebel zusammen liefern im
Zielbereich weiterhin 0 Trades. Verdacht: ``hook_2_ziel`` liefert fuer JEDEN Bar
ausserhalb 848..1020 den Modus BLOCKIERT. Dieses Skript vermisst die
Abdeckung (Vakuum-Karte) und faehrt die P12-Kombinationen mit H1/H2/Ziel.
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
mod = types.ModuleType("vakuum")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_vak>", "exec"), ns)
sys.argv = _old

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PNS: Dict = ns["ns"]
scan = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
SRC: str = ns["patched_src"]
eng = sys.modules["ke_pngset"]
P9 = ns["P9"]
P12 = ns["P12_RESERVE"]
d = scan["d"]
ts = pd.to_datetime(d["ts"])
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
n = ns["n"]
BOX = int(ns["box_end"])

print("=" * 108)
print("1) VAKUUM-KARTE -- welcher Bar hat welchen Hook-2-Modus?")
print("=" * 108)
for name, ad in (("IST (nur P9)", adapter),
                 ("P9 + P12", dataclasses.replace(adapter, segmente=(P9, P12)))):
    modi = [ad.hook_2_ziel(k, "LONG").modus.value for k in range(n)]
    print(f"\n  {name}")
    # Lauf-Encoding: zusammenhaengende Bloecke
    start = 0
    runs: List[Tuple[int, int, str]] = []
    for k in range(1, n + 1):
        if k == n or modi[k] != modi[start]:
            runs.append((start, k - 1, modi[start]))
            start = k
    frei = sum(1 for m in modi if m != "BLOCKIERT")
    for a, b, m in runs:
        dauer = b - a + 1
        print(f"    {a:>5}..{b:<5} ({dauer:>4} Bars, "
              f"{dauer * 15 / 60:>6.1f} h) {m}")
    print(f"    -> autorisiert: {frei}/{n} Bars "
          f"({frei / n * 100:.1f} %), Vakuum {n - frei} Bars")

print("\n" + "=" * 108)
print("2) LIEGEN DIE GROSSEN SCHWAENGE IM VAKUUM?")
print("=" * 108)
piv: List[Tuple[int, str, float]] = []
for m in range(2, n - 2):
    t = eng._pivot_typ(hi, lo, m)
    if t is not None:
        piv.append((m, t, float(hi[m]) if t == "H" else float(lo[m])))
ad_ist, ad_p12 = adapter, dataclasses.replace(adapter, segmente=(P9, P12))
gross = []
for i in range(1, len(piv)):
    b0, t0, p0 = piv[i - 1]
    b1, t1, p1 = piv[i]
    if t0 != t1 and abs(p1 - p0) >= 1.00:
        gross.append((b0, b1, abs(p1 - p0)))
print(f"  {len(gross)} Schwaenge >= 1.00 USD im gesamten AUG-Fenster")
for b0, b1, amp in gross:
    m_ist = ad_ist.hook_2_ziel(b1, "LONG").modus.value
    m_p12 = ad_p12.hook_2_ziel(b1, "LONG").modus.value
    print(f"    Bars {b0:>4}->{b1:<4} {amp:>6.4f} USD | "
          f"Ist {m_ist:<9} | P9+P12 {m_p12}")
im_vakuum = sum(1 for b0, b1, _ in gross
                if ad_ist.hook_2_ziel(b1, "LONG").modus.value == "BLOCKIERT")
print(f"  -> davon Ende im Vakuum (nur P9): {im_vakuum}/{len(gross)}")

print("\n" + "=" * 108)
print("3) P12-KOMBINATIONEN -- H1/H2/Ziel getrennt")
print("=" * 108)
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
    exec(compile(src, "<vak>", "exec"), PNS)
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
        print(f"        K{t.kid} {t.richtung} signal {t.bar} "
              f"{ts.iloc[t.bar]:%d.%m %H:%M} entry_bar {t.entry_bar} "
              f"r {t.r:+.6f}")


ad_p12 = dataclasses.replace(adapter, segmente=(P9, P12))
print(f"  {'Variante':<40} Trd |          R1 |       H1 Trd/R | "
      f"      H2 Trd/R | Ziel")
print("  " + "-" * 104)
zeile("IST (nur P9)", lauf(SRC, cfg0, adapter))
zeile("W1  nur P12 zusaetzlich aktiv", lauf(SRC, cfg0, ad_p12))
zeile("W2  W1 + M6 lebend", lauf(variant(m6_lebt=True), cfg0, ad_p12))
zeile("W3  W2 + Ueberdehnung 0.80",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80), ad_p12))
zeile("W4  W3 + Q29 aus (200 %)",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80,
                               quartil_distanz_pct=200.0), ad_p12))
zeile("W5  W4 + V-S>=2",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80,
                               quartil_distanz_pct=200.0,
                               min_touches_handelbar=2), ad_p12))
print("=" * 108)
