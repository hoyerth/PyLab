# -*- coding: utf-8 -*-
"""E-29 Sammelauswertung Binning-Sweep."""
from __future__ import annotations

import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

RE_G = re.compile(r"gesamt : n\s+(\d+)\s+R ([+-][\d.]+)\s+USD ([+-][\d.]+)"
                  r"\s+USD/Tr ([+-][\d.]+)\s+ATR/Tr ([+-][\d.]+)\s+Q_stop ([\d.]+)")
RE_H2 = re.compile(r"H2\s*: n\s+(\d+)\s+R ([+-][\d.]+).*USD ([+-][\d.]+)"
                   r"\s+USD/Tr ([+-][\d.]+).*Q_stop ([\d.]+)")
RE_H1 = re.compile(r"H1\s*: n\s+(\d+)")
RE_BARS = re.compile(r"Aufrufe (\d+)\s+Fenster-Bars\s+min ([\d.]+)\s+median "
                     r"([\d.]+)\s+max ([\d.]+)")
RE_SPANNE = re.compile(r"Preisspanne\s+min ([\d.]+)\s+median ([\d.]+)\s+max "
                       r"([\d.]+)")
RE_BW = re.compile(r"Bin-Breite\s+min ([\d.]+)\s+median ([\d.]+)\s+max ([\d.]+)")
RE_Z = re.compile(r"leere Bins\s+mean ([\d.]+)\s+median ([\d.]+)\s+max ([\d.]+)")
RE_SH = re.compile(r"POC-Gewicht mean ([\d.]+) %\s+median ([\d.]+) %")

MODE = sys.argv[1] if len(sys.argv) > 1 else "s2"
BINS = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2
                         else ["10", "15", "20", "30", "40", "60"])]

print(f"E-29 BINNING-SWEEP -- {MODE.upper()}  (Kernstandard geg960poc)")
print("")
print(f"{'bins':>5} {'Setups':>7} {'R ges':>13} {'USD/Tr':>9} {'ATR/Tr':>9}"
      f" {'Q_stop':>7} {'H1n':>5} {'H2n':>5} {'H2 R':>12} {'H2 USD/Tr':>10}")
print("-" * 104)
for b in BINS:
    p = pathlib.Path(f"test/_tmp_e29_audit_{MODE}_b{b}_out.txt")
    if not p.exists():
        print(f"{b:>5}   -- fehlt --")
        continue
    t = p.read_text(encoding="utf-8")
    g = RE_G.search(t)
    h2 = RE_H2.search(t)
    h1 = RE_H1.search(t)
    print(f"{b:>5} {g.group(1):>7} {g.group(2):>13} {g.group(4):>9} "
          f"{g.group(5):>9} {g.group(6):>7} {h1.group(1):>5} {h2.group(1):>5} "
          f"{h2.group(2):>12} {h2.group(4):>10}")
print("")
print(f"{'bins':>5} {'Aufrufe':>8} {'Bars med':>9} {'Spanne med':>11}"
      f" {'Binw med':>10} {'leer med':>9} {'leer %':>8} {'POC% med':>9}")
print("-" * 104)
for b in BINS:
    p = pathlib.Path(f"test/_tmp_e29_audit_{MODE}_b{b}_out.txt")
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    n, bmin, bmed, bmax = RE_BARS.search(t).groups()
    smed = RE_SPANNE.search(t).group(2)
    bwmed = RE_BW.search(t).group(2)
    zmean, zmed, zmax = RE_Z.search(t).groups()
    shmean, shmed = RE_SH.search(t).groups()
    print(f"{b:>5} {n:>8} {bmed:>9} {smed:>11} {bwmed:>10} {zmed:>9} "
          f"{float(zmean) / b * 100:>7.1f}% {shmed:>9}")
