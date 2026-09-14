# -*- coding: utf-8 -*-
"""READ-ONLY: Arretierte Engine auf S1 (2026-02-05..2026-08-28) -- "2026 gesamt".

Drei Laeufe auf DEMSELBEN S1-Scan (ein Scan, keine Regel-Aenderung):

  V0        -- Engine native (ORIG._se_trades, ungepatcht)
  V1_basis  -- 13 Renderer-Bestands-Patches (DEFAULT_ADAPTER, 1 Segment)
  V1_kausal -- 13 + ZP-4 + ZP-5-Vorlauf, ADAPTER_V019_KAUSAL (AUG-Anker AS-IS)

WICHTIG: ``ADAPTER_V019_KAUSAL`` traegt ABSOLUTE Bar-Fenster aus AUG
(P9 848..1020 / A1 1033..1173 / A2 1174..1287). AUG beginnt in S1 bei Bar
``n_S1 - n_AUG``. Der Lauf ``V1_kausal`` ist deshalb NICHT handelbar -- er
dient nur dem Nachweis der Versatz-Wirkung. ``V1_basis`` ist die einzige
Fassung, die ohne Anpassung auf 2026 uebertragbar ist.

Es wird KEINE Produktivdatei geschrieben.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import numpy as np  # noqa: E402

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V019_KAUSAL, DEFAULT_ADAPTER, Hook2ZielModus,
)

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN_P = ROOT / "test" / "tmp_png_aug_sichttest.py"

spec = importlib.util.spec_from_file_location("engine", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine"] = engine
spec.loader.exec_module(engine)

cfg = engine.StraightEdgeHarnessKonfiguration()

WIN = sys.argv[1] if len(sys.argv) > 1 else "S1"

print("=" * 100)
print(f"ARRETIERTE ENGINE AUF {WIN} -- Fenster {engine.FENSTER[WIN]}")
print("=" * 100)

t0 = time.time()
scan = engine._se_scan(WIN, cfg)
n = scan["n"]
_BOX = int(scan["box_end_bar"])          # Kalenderkante (H1/H2-Split)
scan["box_end_bar"] = n                  # Voll-Lauf (arretierte Basis)
print(f"{WIN}-Scan: n={n}  box_end_bar(origin)={_BOX} -> {n} (Voll-Lauf)  "
      f"edges={len(scan['edges'])} seeds={len(scan['seeds'])}  "
      f"({time.time() - t0:.1f}s)")

# AUG-Offset: AUG (n=1288) liegt am Ende von S1.
_AUG_START = n - 1288
print(f"AUG-Block in S1: Bars {_AUG_START}..{n - 1} "
      f"(AUG-Bar b -> S1-Bar b + {_AUG_START})")

# ---------------------------------------------------- Renderer-Bausteine (AST)
ren = REN_P.read_text(encoding="utf-8")
ren_tree = ast.parse(ren)
basis: Dict[str, str] = {}
for _node in ren_tree.body:
    if isinstance(_node, ast.Assign) and len(_node.targets) == 1 \
            and isinstance(_node.targets[0], ast.Name) \
            and _node.targets[0].id.startswith("A_"):
        try:
            exec(compile(ast.get_source_segment(ren, _node), "<a_>", "exec"),  # noqa: S102
                 basis)
        except Exception:  # noqa: BLE001
            pass

_fn = next(x for x in ren_tree.body
           if isinstance(x, ast.FunctionDef)
           and x.name == "_wende_zielzonen_patches_v019")
ns_fn: Dict[str, object] = {}
exec(compile(ast.get_source_segment(ren, _fn), "<zp>", "exec"), ns_fn)  # noqa: S102

_src_datei = ENGINE_P.read_text(encoding="utf-8")
_src_tree = ast.parse(_src_datei)
_src_node = next(x for x in _src_tree.body
                 if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src_base = ast.get_source_segment(_src_datei, _src_node)
assert src_base is not None
src13 = src_base
_KETTE = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
for _nm in _KETTE:
    assert src13.count(basis[_nm]) == 1, (_nm, src13.count(basis[_nm]))
    src13 = src13.replace(basis[_nm], basis[_nm + "_NEW"])
patched_src = ns_fn["_wende_zielzonen_patches_v019"](src13)  # type: ignore[operator]
print(f"Quelltexte: ORIG={len(src_base)} | 13-Patch={len(src13)} | "
      f"13+ZP-4={len(patched_src)} Zeichen")

# ---------------------------------------------------- Laufzeit-Gates (Renderer)
ns: Dict[str, object] = dict(engine.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus

_SEG = ADAPTER_V019_KAUSAL.segmente
_ZZ_START, _ZZ_ENDE = int(_SEG[1].start_bar), int(_SEG[-1].end_bar)
_P9_START, _P9_ENDE = int(_SEG[0].start_bar), int(_SEG[0].end_bar)
print(f"ADAPTER_V019_KAUSAL-Fenster (AUG-Koordinaten, AS-IS): "
      f"P9 {_P9_START}..{_P9_ENDE} | ZP {_ZZ_START}..{_ZZ_ENDE}")


def _zv(kk: int) -> bool:
    _hk = ns.get("_hook")
    return (True and _hk is not None and len(getattr(_hk, "segmente", ())) > 1
            and _ZZ_START <= kk <= _ZZ_ENDE
            and not (_P9_START <= kk <= _P9_ENDE))


def _ueb(kk: int) -> float:
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS_ORIG = engine._reclaim_stufe


def _reclaim_stufe_lok(seite, kk, basis_px, hi, lo, cl, c):
    if _zv(kk):
        c = dataclasses.replace(c, max_sweep_ueberdehnung_pct=0.80)
    return _RS_ORIG(seite, kk, basis_px, hi, lo, cl, c)


ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _reclaim_stufe_lok

ORIG = engine._se_trades


def _lauf(quelle: str, hook, vorlauf: bool) -> Tuple[List, Dict]:
    """Ein Lauf auf frischer deepcopy; optional ZP-5-Vorlauf (Abschnitt 75)."""
    ns["_hook"] = hook
    exec(compile(quelle, "<se_s1>", "exec"), ns)  # noqa: S102
    sc = copy.deepcopy(scan)
    if vorlauf:
        # Dieselbe Renderer-Funktion, per AST geladen (kein Sonderpfad).
        _fkl = next(x for x in ren_tree.body
                    if isinstance(x, ast.FunctionDef)
                    and x.name == "erweitere_segmentwand_dochte")
        _nsk: Dict[str, object] = {}
        exec(compile("from __future__ import annotations\n"
                     + (ast.get_source_segment(ren, _fkl) or ""),
                     "<kl>", "exec"), _nsk)  # noqa: S102
        _nsk["erweitere_segmentwand_dochte"](
            sc, hook, cfg,
            sc["d"]["high"].to_numpy(dtype=float),
            sc["d"]["low"].to_numpy(dtype=float), _ueb)
    fn = ns["_se_trades"] if quelle is not src_base else ORIG  # noqa: F841
    if quelle is src_base:
        setups, st = ORIG(sc, cfg)
    else:
        setups, st = ns["_se_trades"](sc, cfg)  # type: ignore[operator]
    return list(setups), dict(st)


def _bilanz(name: str, setups: List) -> None:
    r = sum(float(t.r) for t in setups)
    be = _BOX
    h1 = [t for t in setups if int(t.entry_bar) < be]
    h2 = [t for t in setups if int(t.entry_bar) >= be]
    aug = [t for t in setups if int(t.entry_bar) >= _AUG_START]
    print(f"   {name:<26} n={len(setups):>4}  R={r:>+12.6f}   "
          f"H1(<{be}) {len(h1):>3}/{sum(float(t.r) for t in h1):>+11.6f}  "
          f"H2 {len(h2):>3}/{sum(float(t.r) for t in h2):>+11.6f}   "
          f"[AUG-Block {len(aug):>2}/{sum(float(t.r) for t in aug):>+11.6f}]")


print("\n" + "=" * 100)
print("ERGEBNIS -- '2026 GESAMT' (S1) vs. AUG-Referenz")
print("=" * 100)
_res: Dict[str, Tuple[List, Dict]] = {}
for _nm, _q, _hk, _vl in (
        ("V0 (Engine native)", src_base, DEFAULT_ADAPTER, False),
        ("V1_basis (13-Patch)", src13, DEFAULT_ADAPTER, False),
        ("V1_kausal (AUG-Anker AS-IS)", patched_src, ADAPTER_V019_KAUSAL, True)):
    _t = time.time()
    _s, _st = _lauf(_q, _hk, _vl)
    _res[_nm] = (_s, _st)
    _bilanz(_nm, _s)
    print(f"      (Lauf {time.time() - _t:.1f}s)")

print("\n   AUG-Referenz (arretiert): V0 14/+42.450970 | "
      "V1_basis 14/+47.815697 | V1_kausal 23/+85.577150")

print("\n   V1_kausal-Trades innerhalb des unverschobenen AUG-Fensters "
      f"({_ZZ_START}..{_ZZ_ENDE}):")
for t in sorted(_res["V1_kausal (AUG-Anker AS-IS)"][0],
                key=lambda x: int(x.bar)):
    if _ZZ_START <= int(t.bar) <= _ZZ_ENDE:
        print(f"      bar {int(t.bar):>5} K{int(t.kid):<4} "
              f"R {float(t.r):>+10.5f}  ({t.grund1}/{t.grund2})")

print("\nENDE S1-LAUF")
