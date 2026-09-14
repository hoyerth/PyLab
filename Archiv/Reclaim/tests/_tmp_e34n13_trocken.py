# -*- coding: utf-8 -*-
"""E-34n/13 — Trockenpruefung Patch 14 (A_KL_DOCHT): rein lesend, kein Lauf."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"

ren = REN.read_text(encoding="utf-8")
NS: dict = {}
for n in ast.parse(ren).body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 \
            and isinstance(n.targets[0], ast.Name) \
            and n.targets[0].id.startswith("A_"):
        exec(compile(ast.get_source_segment(ren, n), "<a>", "exec"), NS)  # noqa: S102
    if isinstance(n, ast.FunctionDef) and n.name == "_wende_zielzonen_patches_v019":
        exec(compile(ast.get_source_segment(ren, n), "<zp>", "exec"), NS)  # noqa: S102

src_f = ENG.read_text(encoding="utf-8")
node = next(x for x in ast.parse(src_f).body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
s = ast.get_source_segment(src_f, node)
assert s is not None
for nm in ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
           "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
           "A_M6_UNTEN", "A_TP2", "A_KBASIS"):
    assert s.count(NS[nm]) == 1, (nm, s.count(NS[nm]))
    s = s.replace(NS[nm], NS[nm + "_NEW"])

s2 = NS["_wende_zielzonen_patches_v019"](s)
print("ZP-4 + ZP-5 angewendet: OK (alle 5 Anker count == 1)")
compile(s2, "<se>", "exec")
print(f"injizierter _se_trades kompiliert OK | {len(s2)} Zeichen "
      f"(vorher {len(s)})")
i = s2.index("_kl_hook")
print("--- ZP-5-Block im gepatchten Quelltext ---")
print(s2[i - 300:i + 300])
print("--- Zaehlung Schlüsselmarker ---")
for _m in ('cfg.touch_band_pct', '0.12', '_ueb(_kb)', '0.80',
           'boden_deklariert_literal', 'basis_bei(_s0)', 'schlaf_windows'):
    print(f"  {_m:<26} {s2.count(_m)}")
