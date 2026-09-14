# -*- coding: utf-8 -*-
"""READ-ONLY Hilfscheck: Vorkommen der Hook-Ankerstellen im Engine-Quelltext."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
s = (Path(__file__).resolve().parent / "tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8")

PROBEN = {
    "H1_OLD": ('        if not pool:\n            return None\n'
               '        pool.sort(key=lambda e: e.basis_bei(k), '
               'reverse=(seite == "OBEN"))'),
    "H2_OLD": ('            if dist < 0.0:\n'
               '                if _lebt(e, k):\n'
               '                    return None                 '
               '# lebende Wand nicht erreicht\n'),
    "H3_OLD": ('            if pos == 0:\n'
               '                return e                        '
               '# Q1: Wand handelt (Reclaim=Reife)\n'),
    "M6_OBEN": ('            if seite == "OBEN":\n'
                '                if b <= sweep_px:\n'
                '                    continue                    '
                '# erreicht -> kein Blocker\n'),
    "M6_UNTEN": ('            else:\n'
                 '                if b >= sweep_px:\n'
                 '                    continue\n'),
    "B_OLD": '            gegen_basis = geg.basis_bei(k)\n',
}
for name, p in PROBEN.items():
    print(f"  {name:10s} count={s.count(p)}")
