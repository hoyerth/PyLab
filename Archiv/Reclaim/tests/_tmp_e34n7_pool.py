# -*- coding: utf-8 -*-
"""E-34n/7 — Warum ist bei 1072..1075 die Kandidatenlinie K62 und nicht K82?
Dump des _kandidat-Pools nach dem ZP-4-Patch. Read-only.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus,
)

REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"

ren_txt = REN.read_text(encoding="utf-8")
RENNS: dict = {}
for _n in ast.parse(ren_txt).body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id.startswith("A_"):
        exec(compile(ast.get_source_segment(ren_txt, _n), "<a_>", "exec"),  # noqa: S102
             RENNS)
    if isinstance(_n, ast.FunctionDef) \
            and _n.name == "_wende_zielzonen_patches_v019":
        exec(compile(ast.get_source_segment(ren_txt, _n), "<zp4>", "exec"),  # noqa: S102
             RENNS)

src_datei = ENG.read_text(encoding="utf-8")
_node = next(x for x in ast.parse(src_datei).body
             if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, _node)
_ORDER = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
patched = src
for _nm in _ORDER:
    patched = patched.replace(RENNS[_nm], RENNS[_nm + "_NEW"])
patched = RENNS["_wende_zielzonen_patches_v019"](patched)

_ANK = ('        if _freigabe_kid is not None:\n'
        '            pool = [e for e in pool if e.kid != _freigabe_kid]')
assert patched.count(_ANK) == 1, patched.count(_ANK)
patched = patched.replace(
    _ANK,
    _ANK + '\n'
    '        if 1070 <= k <= 1080:\n'
    '            _P.append((k, richtung, int(_freigabe_kid) '
    'if _freigabe_kid is not None else -1,\n'
    '                       [(int(e.kid), round(_dist(e), 4),\n'
    '                         int(e.touch_conf(k))) for e in pool]))')

spec = importlib.util.spec_from_loader("ke_e34n7", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n7"] = eng
exec(compile(src_datei, str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n
ts = scan["d"]["ts"]
lo = scan["d"]["low"].to_numpy(dtype=float)
hi = scan["d"]["high"].to_numpy(dtype=float)

SEG = ADAPTER_V019.segmente
AUTO_A, AUTO_B = SEG[1].start_bar, SEG[-1].end_bar
P9A, P9B = SEG[0].start_bar, SEG[0].end_bar
_HOOK = [DEFAULT_ADAPTER]


def _zv(kk: int) -> bool:
    return (len(_HOOK[0].segmente) > 1
            and AUTO_A <= kk <= AUTO_B and not (P9A <= kk <= P9B))


def _ueb(kk: int) -> float:
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS = eng._reclaim_stufe


def _rs_lok(seite, kk, basis, h, l, c, cc):
    if _zv(kk):
        cc = dataclasses.replace(cc, max_sweep_ueberdehnung_pct=0.80)
    return _RS(seite, kk, basis, h, l, c, cc)


ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _rs_lok
ns["_P"] = []
ns["_hook"] = ADAPTER_V019
_HOOK[0] = ADAPTER_V019
exec(compile(patched, "<se>", "exec"), ns)
eng._se_trades = ns["_se_trades"]
res = eng._se_trades(copy.deepcopy(scan), cfg)
print("E-34n/7  _kandidat-POOL (nach ZP-4), bars 1070..1080")
print("=" * 110)
for (k, richtung, fr, pool) in ns["_P"]:
    print(f"\nbar {k} ({ts.iloc[k].strftime('%d.%m. %H:%M')}) {richtung} "
          f"L{lo[k]:.4f} H{hi[k]:.4f} | freigabe_kid={fr}")
    for (kid, dist, tc) in pool:
        mark = "  <== POS 0" if (kid, dist, tc) == pool[0] else ""
        print(f"    K{kid:<3} dist={dist:+.4f}%  touch_conf={tc}{mark}")
print("\nENDE E-34n/7")
