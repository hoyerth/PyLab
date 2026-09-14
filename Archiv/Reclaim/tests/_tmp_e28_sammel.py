# -*- coding: utf-8 -*-
"""E-28 Sammelauswertung: Varianten-Tabelle je Datensatz."""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

VARS = ("base", "geg", "geg960", "gegleb", "poc",
        "gegpoc", "geg960poc", "geglebpoc")

PAT = re.compile(
    r"gesamt : n\s+(\d+)\s+R ([+-][\d.]+)\s+R_adj ([+-][\d.]+)\s+"
    r"USD ([+-][\d.]+)\s+USD/Tr ([+-][\d.]+)\s+ATR/Tr ([+-][\d.]+)\s+"
    r"Q_stop ([\d.]+)\s+\|ziel\|/e\s+([\d.]+)%\s+halt\s+([\d.]+)\s+"
    r"Gew% \s*([\d.]+)")
PAT_H = re.compile(
    r"^\s+(H1|H2)\s*: n\s+(\d+)\s+R ([+-][\d.]+).*USD/Tr ([+-][\d.]+)"
    r".*Q_stop ([\d.]+)", re.M)

for modus in (sys.argv[1:] if len(sys.argv) > 1 else ["aug", "s2"]):
    print("=" * 108)
    print(f"E-28 SAMMEL -- {modus.upper()}")
    print("=" * 108)
    print(f"{'Variante':<12}{'Setups':>7}{'R gesamt':>14}{'R_adj':>13}"
          f"{'USD/Tr':>10}{'ATR/Tr':>9}{'Q_stop':>8}{'Ziel%/e':>9}"
          f"{'Halt':>7}{'Gew%':>7}   Trade-SHA")
    for v in VARS:
        p = pathlib.Path(f"test/_tmp_e28_ziel_{modus}_{v}_out.txt")
        if not p.exists():
            print(f"{v:<12}   -- nicht vorhanden --")
            continue
        t = p.read_text(encoding="utf-8")
        m = PAT.search(t)
        if not m:
            print(f"{v:<12}   -- Muster nicht gefunden --")
            continue
        tr = [ln.strip() for ln in t.split("\n") if " tp2 " in ln and "R " in ln]
        h = hashlib.sha256("|".join(tr).encode()).hexdigest()[:16]
        n, R, Ra, U, Ut, At, Q, z, ha, gw = m.groups()
        print(f"{v:<12}{n:>7}{R:>14}{Ra:>13}{Ut:>10}{At:>9}{Q:>8}{z:>8}%"
              f"{ha:>7}{gw:>7}   {h}")
    print("")
    print(f"   {'Variante':<12}{'H1 n':>6}{'H1 R':>13}{'H2 n':>6}{'H2 R':>13}"
          f"{'H2 USD/Tr':>11}{'H2 Q_stop':>11}")
    for v in VARS:
        p = pathlib.Path(f"test/_tmp_e28_ziel_{modus}_{v}_out.txt")
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        d = {mm.group(1): mm.groups() for mm in PAT_H.finditer(t)}
        if "H1" not in d or "H2" not in d:
            print(f"   {v:<12}   -- keine H1/H2-Zeilen --")
            continue
        h1, h2 = d["H1"], d["H2"]
        print(f"   {v:<12}{h1[1]:>6}{h1[2]:>13}{h2[1]:>6}{h2[2]:>13}"
              f"{h2[3]:>11}{h2[4]:>11}")
    print("")
