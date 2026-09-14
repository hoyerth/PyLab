# -*- coding: utf-8 -*-
"""STATISCHE Pruefung (V): welche ``stats[...]``-Schluessel werden AUSSERHALB
der k-Schleife (G4-Block) inkrementiert?  Nur solche Schluessel koennen die
Identitaet (V) der Funnel-Sonde brechen (Doppelzaehlung in ``stats``).
"""
from __future__ import annotations

import ast
import pathlib

SEGMENT = pathlib.Path("test/tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8")

BAUM = ast.parse(SEGMENT)
FN = next(n for n in BAUM.body
          if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
K = next(n for n in FN.body
         if isinstance(n, ast.For) and isinstance(n.target, ast.Name)
         and n.target.id == "k")
ELTERN: dict = {}
for x in ast.walk(FN):
    for y in ast.iter_child_nodes(x):
        ELTERN[y] = x


def _in_k(node: ast.AST) -> bool:
    p = node
    while p is not None:
        if p is K:
            return True
        p = ELTERN.get(p)
    return False


def _schluessel(node: ast.AugAssign) -> str:
    t = node.target
    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) \
            and t.value.id == "stats":
        s = t.slice
        if isinstance(s, ast.Constant):
            return str(s.value)
    return "?"


print("Alle stats[...] += (AugAssign) in _se_trades:")
for n in ast.walk(FN):
    if isinstance(n, ast.AugAssign):
        print(f"  Z{n.lineno:>5d} {'IN k-Loop' if _in_k(n) else 'AUSSERHALB'} "
              f"stats['{_schluessel(n)}'] += {ast.dump(n.value)[:40]}")

print()
print("Alle stats[...] = (Assign) in _se_trades (Setzungen, z. B. keine):")
for n in ast.walk(FN):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) \
                    and t.value.id == "stats":
                print(f"  Z{n.lineno:>5d} {'IN k-Loop' if _in_k(n) else 'AUSSERHALB'} "
                      f"stats[{ast.dump(t.slice)[:30]}] = ...")

print()
print("Setups-Appends ausserhalb der k-Schleife (G4-Anhang):")
for n in ast.walk(FN):
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) \
            and isinstance(n.value.func, ast.Attribute) \
            and n.value.func.attr == "append" \
            and isinstance(n.value.func.value, ast.Name) \
            and n.value.func.value.id == "setups":
        print(f"  Z{n.lineno:>5d} {'IN k-Loop' if _in_k(n) else 'AUSSERHALB'}")
