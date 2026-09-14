# -*- coding: utf-8 -*-
"""Read-only Vorpruefung der G4-Loeschung (Z2753..2838) und der Fensterdaten.

Prueft die einzige verbleibende Gefahr des Loeschvorgangs: Definiert der Block
Namen, die NACH ihm (im Rest von ``_se_trades`` oder spaeter im Modul) noch
GELESEN werden? Waere das so, erzeugte die Loeschung einen NameError, den
``py_compile`` nicht sieht.

Kein Motorlauf, keine Dateiaenderung.
"""
from __future__ import annotations

import ast
from pathlib import Path

BASELINE = Path("test/tmp_kanten_engine_replay.py")
BAUM = ast.parse(BASELINE.read_text(encoding="utf-8"))

VON, BIS = 2753, 2838          # inklusive, G4/Hook-3-Block

ziel = next(n for n in BAUM.body
            if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
print(f"_se_trades: Z{ziel.lineno}..{ziel.end_lineno}")
print(f"Loeschbereich: Z{VON}..{BIS} ({BIS - VON + 1} Zeilen)")
print()

# --- 1) Namen, die der Loeschblock bindet --------------------------------
block_bind = set()
for n in ast.walk(ziel):
    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) \
            and VON <= n.lineno <= BIS:
        block_bind.add(n.id)
    if isinstance(n, ast.FunctionDef) and VON <= n.lineno <= BIS:
        block_bind.add(n.name)
print(f"im Block gebundene Namen ({len(block_bind)}):")
for x in sorted(block_bind):
    print("   " + x)
print()

# --- 2) Namen, die NACH dem Block gelesen werden -------------------------
nachher = set()
for n in ast.walk(ziel):
    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) \
            and n.lineno > BIS:
        nachher.add(n.id)
# plus alle Leser auf MODUL-Ebene (nach dem Funktionsende)
modul_nachher = set()
for n in BAUM.body:
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.lineno > ziel.end_lineno:
        for m in ast.walk(n):
            if isinstance(m, ast.Name) and isinstance(m.ctx, ast.Load):
                modul_nachher.add(m.id)

kritisch = sorted(block_bind & (nachher | modul_nachher))
print(f"Leser nach Z{BIS} in _se_trades ({len(nachher)}): "
      f"{', '.join(sorted(nachher))}")
print()
if kritisch:
    print("!! KRITISCH: im Block gebunden, danach noch gelesen:")
    for x in kritisch:
        print("   " + x)
else:
    print("OK: KEIN im Block gebundener Name wird danach noch gelesen.")
    print("    -> Loeschung Z2753..2838 ist name-resolution-sicher.")
print()

# --- 3) Gegenprobe: Namen DIREKT vor/nach der Grenze ---------------------
zeug = BASELINE.read_text(encoding="utf-8").splitlines()
for i in (2749, 2750, 2751, 2752, 2753, 2838, 2839, 2840):
    print(f"   Z{i}: {zeug[i - 1]}")

# --- 4) Fensterdefinitionen der Sonde ------------------------------------
print()
probe = Path("test/_chk_zulassung_funnel.py").read_text(encoding="utf-8")
print("Fensterdefinitionen in der Sonde:")
for i, l in enumerate(probe.splitlines(), 1):
    if ("2026-0" in l and ("MAI" in l or "JUN" in l or "JUL" in l
                           or "AUG" in l)) or "'MAI'" in l or '"MAI"' in l:
        print(f"   {i:5}: {l.rstrip()}")
