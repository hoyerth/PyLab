# -*- coding: utf-8 -*-
"""Extrahiert die Stats-/Listen-Anker aus _se_trades (repr, byte-treu)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent / "tmp_kanten_engine_replay.py"
src = P.read_text(encoding="utf-8")
tree = ast.parse(src)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
body = ast.get_source_segment(src, node)
assert body is not None

for marker in ('stats: Dict[str, int] = {',
               'blocker_liste: List[str] = []',
               'letzter_trade[kd.kid] = setup'):
    i = body.find(marker)
    print(f"\n=== {marker!r} @ {i} ===")
    if i >= 0:
        print(repr(body[i:i + 400]))
