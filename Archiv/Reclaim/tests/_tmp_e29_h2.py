# -*- coding: utf-8 -*-
"""E-29: Extrahiert die H2-Trades (T3-Zeilen) aus dem b60-Output."""
from __future__ import annotations

import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

MODE = sys.argv[1] if len(sys.argv) > 1 else "s2"
BINS = sys.argv[2] if len(sys.argv) > 2 else "60"
SPLIT = 17692
p = pathlib.Path(f"test/_tmp_e29_audit_{MODE}_b{BINS}_out.txt")
t = p.read_text(encoding="utf-8")

ZEILE = re.compile(
    r"^\s+(\d+)\s+(SHORT|LONG)\s+K(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
    r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(-?\d+)\s+(\d+|-)\s+"
    r"([+-][\d.]+|-)\s+(\S+)$", re.M)

h2 = [m for m in ZEILE.finditer(t) if int(m.group(1)) >= SPLIT]
print(f"E-29 H2-ANATOMIE -- {MODE.upper()} b{BINS}   n_H2 = {len(h2)}")
print("")
print(f"{'Bar':>6} {'Ri':<6}{'K':>5}{'risk':>8}{'d_POC':>7}{'d_TP2':>7}"
      f"{'d_Bas':>7}{'MFE':>7}{'MAE':>7}{'SL@':>7}{'Div@':>7}{'R_brk':>9}  Kat")
kat = {}
mfe_ge1 = mfe_lt05 = 0
for m in h2:
    bar, ri, kid, risk, dp, dt, db, mfe, mae, sl, div, rb, k = m.groups()
    kat[k] = kat.get(k, 0) + 1
    if k == "STOP":
        if float(mfe) >= 1.0:
            mfe_ge1 += 1
        if float(mfe) < 0.5:
            mfe_lt05 += 1
    print(f"{bar:>6} {ri:<6}K{kid:>4}{risk:>8}{dp:>7}{dt:>7}{db:>7}{mfe:>7}"
          f"{mae:>7}{sl:>7}{div:>7}{rb:>9}  {k}")
print("")
print(f"Klassen: {kat}")
print(f"STOP-Outs mit MFE >= 1,0 R (hat funktioniert, dann gedreht): {mfe_ge1}")
print(f"STOP-Outs mit MFE <  0,5 R (nie in Bewegung)               : {mfe_lt05}")
d = [float(m.group(5)) for m in h2]
print(f"d_POC (Entry -> TP1) : min {min(d):.2f}  median "
      f"{sorted(d)[len(d)//2]:.2f}  max {max(d):.2f}  R-Abstand")
r_ = [float(m.group(4)) for m in h2]
print(f"risk (USD)           : min {min(r_):.4f}  median "
      f"{sorted(r_)[len(r_)//2]:.4f}  max {max(r_):.4f}")
