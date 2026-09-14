# -*- coding: utf-8 -*-
"""Anker-Pruefung (READ-ONLY): dieselbe Harness-Pipeline auf dem ALTEN
AUG-Fenster ("2026-08-10" .. "2026-08-28", n=1288) muss die arretierten
Referenzwerte reproduzieren:

    V0        = 14 Trades / +42.450970 R
    V1_basis  = 14 Trades / +47.815697 R

Damit ist belegt, dass die AUG26-Zahlen aus derselben Mechanik stammen und
nicht aus einem Harness-Artefakt.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    DEFAULT_ADAPTER,
    Hook2ZielModus,
)

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN_P = ROOT / "test" / "tmp_png_aug_sichttest.py"

spec = importlib.util.spec_from_file_location("engine_ank", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_ank"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
BOX = int(scan["box_end_bar"])
scan["box_end_bar"] = n                       # Voll-Lauf (wie Renderer Z. 630)
W = cfg.tp1_anteil_pct / 100.0

ren = REN_P.read_text(encoding="utf-8")
basis: Dict[str, str] = {}
for _node in ast.parse(ren).body:
    if isinstance(_node, ast.Assign) and len(_node.targets) == 1 \
            and isinstance(_node.targets[0], ast.Name) \
            and _node.targets[0].id.startswith("A_"):
        try:
            exec(compile(ast.get_source_segment(ren, _node), "<a_>", "exec"),  # noqa: S102
                 basis)
        except Exception:  # noqa: BLE001
            pass

_src = ENGINE_P.read_text(encoding="utf-8")
_tree = ast.parse(_src)
_node = next(x for x in _tree.body
             if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src_base = ast.get_source_segment(_src, _node)
assert src_base is not None
src13 = src_base
for _nm in ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
            "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
            "A_M6_UNTEN", "A_TP2", "A_KBASIS"):
    assert src13.count(basis[_nm]) == 1, (_nm, src13.count(basis[_nm]))
    src13 = src13.replace(basis[_nm], basis[_nm + "_NEW"])

ns: Dict[str, object] = dict(engine.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_hook"] = DEFAULT_ADAPTER
ORIG = engine._se_trades


def _lauf(quelle: str) -> Tuple[List, int, float]:
    ns["_hook"] = DEFAULT_ADAPTER
    if quelle is src_base:
        S, _st = ORIG(copy.deepcopy(scan), cfg)
    else:
        exec(compile(quelle, "<basis>", "exec"), ns)  # noqa: S102
        S, _st = ns["_se_trades"](copy.deepcopy(scan), cfg)  # type: ignore
    S = list(S)
    return S, len(S), sum(float(t.r) for t in S)


print("=" * 96)
print("ANKER: altes AUG-Fenster (2026-08-10 .. 2026-08-28)")
print("=" * 96)
print(f"n = {n} | box_end = Bar {BOX} | Kanten "
      f"{len(scan['edges'])} edges + {len(scan['seeds'])} seeds")
for _tag, _q, _soll_n, _soll_r in (
        ("V0 (Engine native)", src_base, 14, 42.450970),
        ("V1_basis (13 Patches, DEFAULT_ADAPTER)", src13, 14, 47.815697)):
    _S, _c, _r = _lauf(_q)
    _ok = ("OK" if (_c == _soll_n and abs(_r - _soll_r) < 1e-6) else "ABWEICHUNG")
    print(f"   {_tag:<42} {_c:>3} Trades / {_r:+.6f} R   "
          f"[Soll {_soll_n} / {_soll_r:+.6f}]  -> {_ok}")
print("ENDE ANKER")
