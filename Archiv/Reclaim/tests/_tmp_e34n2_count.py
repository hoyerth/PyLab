# -*- coding: utf-8 -*-
"""Hilfsdump: Umgebung der beiden 'if not pool:' im _se_trades-Segment."""
import ast
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")
T = io.open("test/tmp_kanten_engine_replay.py", encoding="utf-8").read()
ND = next(x for x in ast.parse(T).body
          if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
S = ast.get_source_segment(T, ND)
L = S.splitlines()
for i, ln in enumerate(L):
    if "if not pool:" in ln:
        print("---- bei Segmentzeile", i + 1, "----")
        for j in range(max(0, i - 4), min(len(L), i + 6)):
            print(f"{j + 1:4d}| {L[j]!r}")
