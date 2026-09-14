# -*- coding: utf-8 -*-
"""Read-only Fremdnamen-Analyse fuer den V022-Interface-Vertrag.

Fragestellung: Welche Namen benutzt ``StraightEdgeHarnessKonfiguration``s
``_se_trades`` (inkl. aller verschachtelten Closures), die NICHT lokal gebunden
sind? Diese Namen loest Python zur LAUFZEIT ueber die Modul-Globals auf. Wird
der Loop nach V022 kopiert, zeigen sie auf V022s Globals -- fehlt einer dort,
gibt es einen NameError, den ``py_compile`` NICHT erkennt
(belegter Praezedenzfall: H20.52 Paragraph 5, fehlender numpy-Import).

Kein Motorlauf, kein Import der Baseline, keine Dateiaenderung ausser diesem
Protokoll-Text.
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

BASELINE = Path("test/tmp_kanten_engine_replay.py")
QUELLE = BASELINE.read_text(encoding="utf-8")
BAUM = ast.parse(QUELLE)


def _bindungen(knoten: ast.AST) -> set:
    """Alle Namen, die im gegebenen Teilbaum GEBUNDEN werden."""
    namen = set()
    for n in ast.walk(knoten):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            namen.add(n.name)
            args = getattr(n, "args", None)
            if args is not None:
                for a in (list(args.posonlyargs) + list(args.args)
                          + list(args.kwonlyargs)):
                    namen.add(a.arg)
                if args.vararg:
                    namen.add(args.vararg.arg)
                if args.kwarg:
                    namen.add(args.kwarg.arg)
        elif isinstance(n, ast.Lambda):
            args = n.args
            for a in (list(args.posonlyargs) + list(args.args)
                      + list(args.kwonlyargs)):
                namen.add(a.arg)
            if args.vararg:
                namen.add(args.vararg.arg)
            if args.kwarg:
                namen.add(args.kwarg.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            namen.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            namen.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                namen.add((al.asname or al.name).split(".")[0])
        elif isinstance(n, ast.Global) or isinstance(n, ast.Nonlocal):
            namen.update(n.names)
        elif isinstance(n, ast.MatchAs) and n.name:
            namen.add(n.name)
        elif isinstance(n, ast.MatchStar) and n.name:
            namen.add(n.name)
        elif isinstance(n, ast.MatchMapping) and n.rest:
            namen.add(n.rest)
    return namen


# --- Zielknoten suchen ------------------------------------------------------
ziel = None
for n in BAUM.body:
    if isinstance(n, ast.FunctionDef) and n.name == "_se_trades":
        ziel = n
        break
assert ziel is not None, "_se_trades nicht gefunden"
print(f"_se_trades: Zeile {ziel.lineno}..{ziel.end_lineno} "
      f"({ziel.end_lineno - ziel.lineno + 1} Zeilen)")

verschachtelt = [n.name for n in ast.walk(ziel)
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                 and n is not ziel]
print(f"verschachtelte Definitionen ({len(verschachtelt)}): "
      f"{', '.join(sorted(set(verschachtelt)))}")
print()

# --- freie Namen ------------------------------------------------------------
alle_loads = {n.id for n in ast.walk(ziel)
              if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
alle_attrs = {n.attr for n in ast.walk(ziel)
              if isinstance(n, ast.Attribute)}
lokal = _bindungen(ziel)
frei = sorted(alle_loads - lokal)

# --- Modul-Ebene der Baseline klassifizieren --------------------------------
mod_defs = {n.name for n in BAUM.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))}
mod_importe = set()
for n in BAUM.body:
    if isinstance(n, ast.Import):
        for al in n.names:
            mod_importe.add((al.asname or al.name).split(".")[0])
    elif isinstance(n, ast.ImportFrom):
        for al in n.names:
            mod_importe.add(al.asname or al.name)
mod_konstanten = {t.id for n in BAUM.body if isinstance(n, ast.Assign)
                  for t in n.targets if isinstance(t, ast.Name)}
mod_konstanten |= {n.target.id for n in BAUM.body
                   if isinstance(n, ast.AnnAssign)
                   and isinstance(n.target, ast.Name)}
sichtbar = mod_defs | mod_importe | mod_konstanten

BI = set(dir(builtins))

print(f"{'Name':<34} {'Herkunft':<26} V022-Aktion")
print("-" * 96)
nachbau = []
for f in frei:
    if f in sichtbar:
        herkunft = ("Baseline-Modul-def" if f in mod_defs
                    else "Baseline-Import" if f in mod_importe
                    else "Baseline-Konstante")
        nachbau.append(f)
        aktion = ("B.%s() / verbatim" % f if f in mod_defs else
                  "verbatim mitkopieren" if f in mod_importe else "")
    elif f in BI:
        herkunft, aktion = "Builtin", ""
    else:
        herkunft, aktion = "NICHT AUFLOESBAR", "PRUEFEN"
    print(f"{f:<34} {herkunft:<26} {aktion}")

print()
print(f"Freie Namen gesamt : {len(frei)}")
print(f"  aus Baseline     : {len(nachbau)}")
print(f"  Builtins         : {len([f for f in frei if f in BI])}")
print(f"  unaufloesbar/luecke: "
      f"{len([f for f in frei if f not in sichtbar and f not in BI])}")

# --- nur die Modul-defs (Funktionen/Klassen), die V022 von aussen braucht ---
print()
print("MODUL-DEFS, die der V022-Loop von AUSSEN zieht (kein Klon!):")
for f in sorted(set(frei) & mod_defs):
    print(f"  B.{f}")

print()
print("TYPE-ALIASE/KONSTANTEN der Modul-Ebene, die im Loop-Text auftauchen:")
for f in sorted((set(frei) | alle_attrs) & (mod_konstanten | mod_defs)):
    if f not in set(frei) & mod_defs:
        print(f"  {f}")

print()
print("ANNOTATIONS-Namen (nur zur Text-Aufloesung):")
for f in sorted(set(frei) & {"Tuple", "List", "Dict", "Optional"}):
    print(f"  {f}")
