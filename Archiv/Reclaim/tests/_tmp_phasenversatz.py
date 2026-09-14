# -*- coding: utf-8 -*-
"""READ-ONLY: PHAENOMEN "PHASEN-VERSATZ" im neuen Zielbereich (ab Bar 1021).

Drei Fragen:
  1. WIE sieht der Versatz aus? (Bandlage/Mitte/Breite P9 vs. Zielbereich)
  2. Ist es ein SAUBERES ZIGZAG nach unseren Regeln? (Pivot-Kette + Amplitude)
  3. WAS kostet welcher Hebel? (H1-Erhalt vs. H2-Ausbeute, je Hebel isoliert)
Es wird NICHTS geschrieben, die Engine bleibt byte-identisch.
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
mod = types.ModuleType("phasenversatz")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_pv>", "exec"), ns)
sys.argv = _old

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PNS: Dict = ns["ns"]
scan = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
SRC: str = ns["patched_src"]
eng = sys.modules["ke_pngset"]
d = scan["d"]
ts = pd.to_datetime(d["ts"])
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
n = ns["n"]
BOX = int(ns["box_end"])          # H1/H2-Grenze VOR der Voll-Lauf-Ueberschreibung
edges = list(scan["edges"]) + list(scan["seeds"])
BY = {e.kid: e for e in edges}

print("=" * 108)
print("1) DER VERSATZ -- Bandlage je Abschnitt")
print("=" * 108)
print(f"  H1/H2-Grenze (Engine box_end) = {BOX}  "
      f"(= {ts.iloc[BOX]:%d.%m. %H:%M} Motor-Wanduhr)")

SEG: Tuple[Tuple[str, int, int], ...] = (("H1", 0, BOX - 1),
                                         ("P9", 848, 1020),
                                         ("ZIEL", 1021, n - 1))
print(f"\n  {'Abschnitt':<10} {'Bars':<12} {'Hoch':>8} {'@':>5} {'Tief':>8} "
      f"{'@':>5} {'Mitte':>8} {'Breite':>8} {'Breite%':>8}")
for lbl, a, b in SEG:
    hh, ll = float(hi[a:b + 1].max()), float(lo[a:b + 1].min())
    bh = a + int(np.argmax(hi[a:b + 1]))
    bl = a + int(np.argmin(lo[a:b + 1]))
    print(f"  {lbl:<10} {a}..{b:<7} {hh:>8.4f} {bh:>5} {ll:>8.4f} {bl:>5} "
          f"{(hh + ll) / 2:>8.4f} {hh - ll:>8.4f} "
          f"{(hh - ll) / ll * 100:>7.3f}%")

p9h, p9l = float(hi[848:1021].max()), float(lo[848:1021].min())
zh, zl = float(hi[1021:].max()), float(lo[1021:].min())
print(f"\n  VERSATZ der Bandkanten (P9 -> Ziel):")
print(f"    Oberkante {p9h:>8.4f} -> {zh:>8.4f}  = {zh - p9h:+.4f} USD "
      f"({(zh - p9h) / p9h * 100:+.3f} %)")
print(f"    Unterkante {p9l:>7.4f} -> {zl:>8.4f}  = {zl - p9l:+.4f} USD "
      f"({(zl - p9l) / p9l * 100:+.3f} %)")
print(f"    Bandmitte  {(p9h + p9l) / 2:>8.4f} -> {(zh + zl) / 2:>8.4f}  = "
      f"{((zh + zl) - (p9h + p9l)) / 2:+.4f} USD")
print(f"    Bandbreite {p9h - p9l:>8.4f} -> {zh - zl:>8.4f}  = "
      f"{(zh - zl) - (p9h - p9l):+.4f} USD "
      f"({((zh - zl) / (p9h - p9l) - 1) * 100:+.1f} %)")

print("\n  --- Leitkanten: Provenienz vs. kausal am Abschnittsende ---")
for kid, kb in ((67, 1020), (77, 1020), (73, n - 1), (82, n - 1)):
    e = BY[kid]
    print(f"    K{kid:<3} {e.seite:<6} Provenienz {e.basis:.4f} | "
          f"kausal({kb}) {e.basis_bei(kb):.4f} | "
          f"Delta {e.basis_bei(kb) - e.basis:+.4f}")

print("\n" + "=" * 108)
print("2) IST ES EIN SAUBERES ZIGZAG?  (bestaetigte Pivots ab Bar 1021)")
print("=" * 108)
piv: List[Tuple[int, str, float]] = []
for m in range(1021, n - 2):
    typ = eng._pivot_typ(hi, lo, m)
    if typ is not None:
        piv.append((m, typ, float(hi[m]) if typ == "H" else float(lo[m])))
nh = sum(1 for _, t, _ in piv if t == "H")
print(f"  {len(piv)} Pivots ({nh} H / {len(piv) - nh} L) in "
      f"{n - 1021} Bars = 1 Pivot je {(n - 1021) / len(piv):.1f} Bars")
schwuenge: List[float] = []
prev: Tuple[int, str, float] | None = None
for b, t, p in piv:
    if prev is not None and prev[1] != t:
        schwuenge.append(abs(p - prev[2]))
    prev = (b, t, p)
arr = np.array(schwuenge)
print(f"  {len(arr)} vollstaendige Schwaenge | Median {np.median(arr):.4f} USD "
      f"({np.median(arr) * 100:.0f} Pips) | Max {arr.max():.4f} "
      f"({arr.max() * 100:.0f}) | Min {arr.min():.4f}")
for grenze in (0.30, 0.50, 0.80, 1.00):
    k = int((arr >= grenze).sum())
    print(f"    Schwaenge >= {grenze:.2f} USD ({grenze / 68 * 100:.2f} %): "
          f"{k} von {len(arr)} ({k / len(arr) * 100:.0f} %) "
          f"-> Summe {arr[arr >= grenze].sum():.2f} USD")

print("\n" + "=" * 108)
print("3) WAS KOSTET WELCHER HEBEL?  (je ein Eingriff isoliert)")
print("=" * 108)
M6_OLD = "            if e is kd or not _existiert(e, k):\n"
M6_NEW = ("            if e is kd or not _existiert(e, k) or not _lebt(e, k):"
          "\n")
Q_HI = "        ex_hi = float(np.max(hi[:k + 1]))\n"
Q_HI_NEW = ("        _p0 = _PHASE_START\n"
            "        ex_hi = float(np.max(hi[(_p0 if k >= _p0 else 0):k + 1]))"
            "\n")
Q_LO = "        ex_lo = float(np.min(lo[:k + 1]))\n"
Q_LO_NEW = ("        ex_lo = float(np.min(lo[(_p0 if k >= _p0 else 0):k + 1]))"
            "\n")


def variant(m6_lebt: bool = False, q29_start: int = 0) -> str:
    s = SRC
    if m6_lebt:
        assert s.count(M6_OLD) == 1, s.count(M6_OLD)
        s = s.replace(M6_OLD, M6_NEW)
    if q29_start:
        assert s.count(Q_HI) == 1 and s.count(Q_LO) == 1
        s = s.replace(Q_HI, Q_HI_NEW).replace(Q_LO, Q_LO_NEW)
    return s


def lauf(src: str, cfg, phasen_start: int = 0) -> List:
    PNS["_hook"] = adapter
    PNS["_PHASE_START"] = phasen_start
    exec(compile(src, "<pv>", "exec"), PNS)
    got, _st = PNS["_se_trades"](copy.deepcopy(scan), cfg)
    return got


def zeile(lbl: str, got: List) -> None:
    h1 = [t for t in got if t.entry_bar < BOX]
    h2 = [t for t in got if t.entry_bar >= BOX]
    ziel = [t for t in got if t.bar >= 1021]
    print(f"  {lbl:<42} {len(got):>3} | {sum(t.r for t in got):>+11.6f} | "
          f"{len(h1):>2}/{sum(t.r for t in h1):>+10.6f} | "
          f"{len(h2):>2}/{sum(t.r for t in h2):>+10.6f} | {len(ziel):>4}")


print(f"  {'Variante':<42} Trd |          R1 |       H1 Trd/R | "
      f"      H2 Trd/R | Ziel")
print("  " + "-" * 104)
zeile("IST (V017, Referenz)", lauf(SRC, cfg0))
zeile("V1  M6 nur bei LEBENDER Aussenwand", lauf(variant(m6_lebt=True), cfg0))
zeile("V2  Q29 phasenlokal ab 848 (P9-Start)",
      lauf(variant(q29_start=848), cfg0, 848))
zeile("V3  Q29 phasenlokal ab 1021", lauf(variant(q29_start=1021), cfg0, 1021))
zeile("V4  V1 + V3", lauf(variant(m6_lebt=True, q29_start=1021), cfg0, 1021))
zeile("V5  V1 + Ueberdehnung 0.80",
      lauf(variant(m6_lebt=True),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80)))
zeile("V6  V1 + V3 + Ueberdehnung 0.80",
      lauf(variant(m6_lebt=True, q29_start=1021),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80), 1021))
zeile("V7  V1 + V3 + Ueberd. 0.80 + V-S>=2",
      lauf(variant(m6_lebt=True, q29_start=1021),
           dataclasses.replace(cfg0, max_sweep_ueberdehnung_pct=0.80,
                               min_touches_handelbar=2), 1021))
print("=" * 108)
