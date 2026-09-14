# -*- coding: utf-8 -*-
"""E-29: Diagnose der T3-Parser-Trefferquote (H2-Zaehlung 37 vs 39)."""
from __future__ import annotations

import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
SPLIT = 17692
t = pathlib.Path("test/_tmp_e29_audit_s2_b60_out.txt").read_text(encoding="utf-8")
ZEILE = re.compile(
    r"^\s+(\d+)\s+(SHORT|LONG)\s+K(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
    r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\d+|-)\s+([+-][\d.]+|-)\s+"
    r"(\S+)$", re.M)
alle = list(ZEILE.finditer(t))
print(f"T3-Zeilen gesamt geparst: {len(alle)}   (erwartet 271)")
h2 = [m for m in alle if int(m.group(1)) >= SPLIT]
print(f"davon H2 (bar >= {SPLIT}): {len(h2)}   (erwartet 39)")
# Kandidatenzeilen, die wie ein Trade aussehen, aber nicht matchen
alle_z = [z for z in t.split("\n") if re.match(r"^\s+\d{4,6} (SHORT|LONG)\s+K", z)]
print(f"T3-Rohzeilen (Regex auf Zeilenkopf): {len(alle_z)}")
fehlend = [z for z in alle_z if not ZEILE.match(z)]
print(f"davon nicht geparst: {len(fehlend)}")
for z in fehlend:
    print("   FEHLT >>>", z)
