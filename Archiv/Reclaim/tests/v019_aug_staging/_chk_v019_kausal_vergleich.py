# -*- coding: utf-8 -*-
"""READ-ONLY Audit (V019, Frage 5): Batch- vs. KAUSALE Segmentbildung.

Frage: ist die arretierte V019 (24 Setups / +88.116626 R) mit einem
LIVE-Verfahren reproduzierbar, das die Segment-Etiketten nur aus der
Vergangenheit ableitet?

Harness = der Renderer-Pfad selbst:
  * 13 Bestands-Paare (Strings per AST aus tmp_png_aug_sichttest.py geladen),
  * ZP-4 aus der Renderer-Funktion ``_wende_zielzonen_patches_v019``
    (per AST geladen - KEINE Nachbildung),
  * ZP-5-Vorlauf aus der Renderer-Funktion ``erweitere_segmentwand_dochte``
    (ebenfalls per AST geladen, Abschnitt 75) -- Renderer und Harness nutzen
    denselben Funktionspfad, kein paralleler Sonderweg,
  * Laufzeit-Injektion ``_zv`` / ``_ueb`` / ``_reclaim_stufe_lok`` wie im
    Renderer.

Laeufe:
  A  arretiert (ADAPTER_V019)              -- KONTROLLE: muss 24 / +88.116626
  B  kausal   (Etiketten erst ab Bestaetigungsbar)

Gerueckmeldung als assert, damit ein Fehlschlag im Terminal sichtbar ist.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V019, Hook2ZielModus, P9_BODEN_RECLAIM, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN_P = ROOT / "test" / "tmp_png_aug_sichttest.py"
MIN_BARS = 77                     # = PLATEAU_REFERENZ_BARS (arretiert)

spec = importlib.util.spec_from_file_location("engine", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine"] = engine
spec.loader.exec_module(engine)

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n

# ---------------------------------------------------- 1. Renderer-Bausteine
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
print(f"Renderer-Bausteine (A_*) geladen: {len(basis) // 2} Paare")

_fn = next(x for x in ren_tree.body
           if isinstance(x, ast.FunctionDef)
           and x.name == "_wende_zielzonen_patches_v019")
ns_fn: Dict[str, object] = {}
exec(compile(ast.get_source_segment(ren, _fn), "<zp>", "exec"), ns_fn)  # noqa: S102

# ZP-5-Vorlauf: DIESELBE Renderer-Funktion, per AST geladen (Abschnitt 75).
# ``from __future__ import annotations`` wird vorangestellt, damit die
# Typ-Annotationen wie im Renderer als Strings stehen (kein Name-Lookup).
_fn_kl = next(x for x in ren_tree.body
              if isinstance(x, ast.FunctionDef)
              and x.name == "erweitere_segmentwand_dochte")
ns_kl: Dict[str, object] = {}
exec(compile("from __future__ import annotations\n"
             + (ast.get_source_segment(ren, _fn_kl) or ""),
             "<kl_docht>", "exec"), ns_kl)  # noqa: S102
_ERWEITERE = ns_kl["erweitere_segmentwand_dochte"]

_src_datei = ENGINE_P.read_text(encoding="utf-8")
_src_tree = ast.parse(_src_datei)
_src_node = next(x for x in _src_tree.body
                 if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(_src_datei, _src_node)
assert src is not None

_KETTE = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
for _nm in _KETTE:
    assert src.count(basis[_nm]) == 1, (_nm, src.count(basis[_nm]))
    src = src.replace(basis[_nm], basis[_nm + "_NEW"])
patched_src = ns_fn["_wende_zielzonen_patches_v019"](src)  # type: ignore[operator]
print(f"ZP-4-Quelltext: {len(patched_src)} Zeichen "
      f"(Bestands-13 + 4 Zielzonen-Regeln) + ZP-5-Vorlauf")

ns: Dict[str, object] = dict(engine.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus

_SEG_ARR: Tuple[PhasenSegmentEintrag, ...] = ADAPTER_V019.segmente
_ZZ_START = int(_SEG_ARR[1].start_bar)
_ZZ_ENDE = int(_SEG_ARR[-1].end_bar)
_P9_START = int(_SEG_ARR[0].start_bar)
_P9_ENDE = int(_SEG_ARR[0].end_bar)


def _zv(kk: int) -> bool:
    """Zielzonen-Fenster: an den GEBUNDENEN Adapter gekoppelt (Renderer-Gate)."""
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


def _lauf(hook: PhasenRegimeAdapter) -> Tuple[List, Dict[str, int]]:
    """Ein V019-Engine-Lauf mit gebundenem Adapter.

    Der ZP-5-Vorlauf wird -- synchron zum Renderer (Abschnitt 75) -- auf der
    laufeigenen ``sc_copy`` VOR ``_se_trades`` ausgefuehrt; das Master-Objekt
    ``scan`` bleibt unberuehrt.
    """
    ns["_hook"] = hook
    exec(compile(patched_src, "<se_v019_audit>", "exec"), ns)  # noqa: S102
    sc_copy = copy.deepcopy(scan)
    _ERWEITERE(sc_copy, hook, cfg,
               sc_copy["d"]["high"].to_numpy(dtype=float),
               sc_copy["d"]["low"].to_numpy(dtype=float), _ueb)
    setups, _st = ns["_se_trades"](sc_copy, cfg)  # type: ignore[operator]
    return list(setups), dict(_st)


def _key(t) -> Tuple[int, int]:
    return (int(t.bar), int(t.kid))


# ------------------------------------------------- 2. kausale Segmentbildung
alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {e.kid: e for e in alle}
LIVE = cfg.wall_live_bars
BAND = cfg.touch_band_pct


def _lebt_kausal(e, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]
    return bool(b) and max(b) >= k - LIVE


def _ecken(k: int) -> Tuple[Optional[int], Optional[int]]:
    oben = [e for e in alle if e.seite == "OBEN" and _lebt_kausal(e, k)]
    unten = [e for e in alle if e.seite == "UNTEN" and _lebt_kausal(e, k)]
    o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
    u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
    return (o.kid if o else None), (u.kid if u else None)


START = P9_BODEN_RECLAIM.end_bar + 1        # = 1021, aus P9 abgeleitet
_wechsel: List[Tuple[int, Optional[int], Optional[int]]] = []
_vor: Optional[Tuple[int, Optional[int], Optional[int]]] = None
for k in range(2, n):
    cur = _ecken(k)
    if cur == (None, None):
        continue
    if _vor is not None and cur == (_vor[1], _vor[2]):
        continue
    _vor = (k, cur[0], cur[1])
    _wechsel.append(_vor)

roh: List[List] = []
for (k, ko, ku) in _wechsel:
    if k < START or ko is None or ku is None:
        continue
    if roh:
        roh[-1][1] = k - 1
    roh.append([k, n - 1, ko, ku])
assert roh and all(s[1] is not None and s[2] is not None for s in roh), roh[:3]


def _nah(p: Sequence, s: Sequence) -> bool:
    ko1, ko2 = katalog[p[2]].basis_bei(p[0]), katalog[s[2]].basis_bei(s[0])
    ku1, ku2 = katalog[p[3]].basis_bei(p[0]), katalog[s[3]].basis_bei(s[0])
    return (abs(ko2 - ko1) / ko1 * 100.0 <= BAND
            and abs(ku2 - ku1) / ku1 * 100.0 <= BAND)


def batch_fassen(segs: List[List], min_bars: int) -> List[List]:
    """Arretierte Batch-Regel (== _tmp_e34_auto.zusammenfassen)."""
    out: List[List] = []
    for s in segs:
        if out and ((s[1] - s[0] + 1) < min_bars or _nah(out[-1], s)):
            out[-1][1] = s[1]
        else:
            out.append(list(s))
    return out


def kausal_fassen(segs: List[List], min_bars: int) -> List[List]:
    """Kausale Fassung: Etikett erst ab Bestaetigung (a + min_bars - 1).

    ``_nah`` ist bei ``s[0]`` entscheidbar -> sofort.  Die Laengen-Regel ist
    erst am Roh-Ende entscheidbar -> bis dahin gilt das vorige Etikett (was
    der Batch-Entscheidung 'rueckwaerts verschmelzen' entspricht).
    """
    out: List[List] = []
    for s in segs:
        if out and _nah(out[-1], s):
            out[-1][1] = s[1]
            continue
        if out and (s[1] - s[0] + 1) < min_bars:
            out[-1][1] = s[1]
            continue
        ab = s[0] if not out else s[0] + min_bars - 1
        out.append([s[0], s[1], s[2], s[3], ab])
    for i in range(len(out) - 1):
        if out[i][1] < out[i + 1][4] - 1:
            out[i][1] = out[i + 1][4] - 1
    return out


SEGS_BATCH = batch_fassen(roh, MIN_BARS)
SEGS_KAUSAL = kausal_fassen(roh, MIN_BARS)


def _fenster(segs: List[List]) -> List[Tuple[int, int, int, int]]:
    return [(s[0], s[1], s[2], s[3]) for s in segs]


print("")
print("=" * 104)
print(f"1. SEGMENTE (MIN_BARS = {MIN_BARS})")
print("=" * 104)
print(f"   {'Quelle':<12}{'Fenster':<26}{'Etiketten':<22}{'wirksam ab'}")
print(f"   {'arretiert':<12}", end="")
for i, s in enumerate(ADAPTER_V019.segmente):
    _tag = "P9 " if i == 0 else f"A{i} "
    print(f"{_tag}{s.start_bar}..{s.end_bar:<7}"
          f"K{s.decke.kid}/K{s.boden.kid:<4}   ", end="")
print("")
for s in _fenster(SEGS_BATCH):
    assert any(s[0] == e.start_bar and s[1] == e.end_bar
               for e in ADAPTER_V019.segmente), ("Batch != arretiert", s)
print("   -> Batch-Regel reproduziert die arretierten Fenster EXAKT")
print(f"   {'kausal':<12}", end="")
for s in SEGS_KAUSAL:
    _ab = s[4] if len(s) > 4 else s[0]
    print(f"{s[0]}..{s[1]}  K{s[2]}/K{s[3]} ab {_ab}   ", end="")
print("")

_txt = {i: s for i, s in enumerate(roh)}
print("")
print("   Roh-Wechselpunkte ab 1021 (kausal aus den Dochten):")
for s in roh:
    print(f"      {s[0]:>5}..{s[1]:<5} ({s[1] - s[0] + 1:>3} Bars)  "
          f"K{s[2]}/K{s[3]}")

# --------------------------------------------- 3. Adapter + Laufzeit-Vergleich
_ka: List[PhasenSegmentEintrag] = [P9_BODEN_RECLAIM]
for s in SEGS_KAUSAL:
    _a, _b, _ko, _ku = s[0], s[1], s[2], s[3]
    _src = next(e for e in ADAPTER_V019.segmente[1:]
                if e.decke.kid == _ko and e.boden.kid == _ku)
    _ka.append(dataclasses.replace(_src, start_bar=int(_a), end_bar=int(_b),
                                   phasen_id=_src.phasen_id + "_K"))
ADAPTER_KAUSAL = PhasenRegimeAdapter(segmente=tuple(_ka))

# Variante C: kausale ETIKETTEN, aber ZP-5-Fenster der zweiten Wand wie
# arretiert (1174..1287) -- trennt "Etikett" von "Injektionsfenster".
_ka_c = [P9_BODEN_RECLAIM, _ka[1], _SEG_ARR[2]]
ADAPTER_C = PhasenRegimeAdapter(segmente=tuple(_ka_c))

A_SETUPS, A_STATS = _lauf(ADAPTER_V019)
B_SETUPS, B_STATS = _lauf(ADAPTER_KAUSAL)
C_SETUPS, C_STATS = _lauf(ADAPTER_C)


def _kz(ss: List) -> Tuple[int, float]:
    return len(ss), sum(float(t.r) for t in ss)


print("")
print("=" * 104)
print("2. ERGEBNIS")
print("=" * 104)
print(f"   {'Lauf':<26}{'n':>4}{'R':>14}{'H2 (entry>=644)':>22}")
for _nm, _ss in (("A arretiert (Kontrolle)", A_SETUPS),
                 ("B kausal (Etikett verzoegert)", B_SETUPS),
                 ("C kausal + ZP-5-Fenster alt", C_SETUPS)):
    _n, _r = _kz(_ss)
    _h2 = [t for t in _ss if int(t.entry_bar) >= 644]
    print(f"   {_nm:<26}{_n:>4}{_r:>+14.6f}"
          f"{len(_h2):>10d}{sum(float(t.r) for t in _h2):>+12.6f}")

assert len(A_SETUPS) == 24, len(A_SETUPS)
assert abs(_kz(A_SETUPS)[1] - 88.116626) < 1e-6, _kz(A_SETUPS)
print("   -> Kontrolle OK: der Harness reproduziert die arretierte V019 "
      "(24 / +88.116626)")

_ka_set = {_key(t) for t in A_SETUPS}
_kb_set = {_key(t) for t in B_SETUPS}
print("")
print("   Trade-Differenz arretiert -> kausal:")
_raus = [t for t in A_SETUPS if _key(t) not in _kb_set]
_rein = [t for t in B_SETUPS if _key(t) not in _ka_set]
for t in sorted(_raus, key=lambda x: int(x.bar)):
    print(f"      ENTFALLEN  bar {int(t.bar):>5} entry {int(t.entry_bar):>5} "
          f"{t.richtung:<6} K{int(t.kid):<4} R {float(t.r):>+10.5f}")
for t in sorted(_rein, key=lambda x: int(x.bar)):
    print(f"      NEU        bar {int(t.bar):>5} entry {int(t.entry_bar):>5} "
          f"{t.richtung:<6} K{int(t.kid):<4} R {float(t.r):>+10.5f}")
for t in sorted(A_SETUPS, key=lambda x: int(x.bar)):
    if _key(t) in _kb_set:
        _p = next(x for x in B_SETUPS if _key(x) == _key(t))
        if abs(float(_p.r) - float(t.r)) > 1e-9:
            print(f"      R-DELTA    bar {int(t.bar):>5} K{int(t.kid):<4} "
                  f"{float(t.r):>+10.5f} -> {float(_p.r):>+10.5f}")

print("")
print("   Zielzonen-Trades (>=1021) im Vergleich:")
print(f"      {'Bar':>5} {'Kante':>6} {'arretiert':>12} {'kausal':>12}   Status")
for t in sorted([x for x in A_SETUPS if int(x.bar) >= 1021],
                key=lambda x: int(x.bar)):
    _p = next((x for x in B_SETUPS if _key(x) == _key(t)), None)
    if _p is None:
        _st = "ENTFAELLT (kausal)"
        _rp = "     -"
    elif abs(float(_p.r) - float(t.r)) > 1e-9:
        _st = "R-DELTA (Zielpreis/Quartil)"
        _rp = f"{float(_p.r):>+12.5f}"
    else:
        _st = "konsistent"
        _rp = f"{float(_p.r):>+12.5f}"
    print(f"      {int(t.bar):>5} {('K%d' % int(t.kid)):>6} "
          f"{float(t.r):>+12.5f} {_rp}   {_st}")

print("")
print("   Trade-Differenz A -> C (kausale Etiketten, ZP-5-Fenster A2 alt):")
_c_set = {_key(t) for t in C_SETUPS}
for t in sorted([x for x in A_SETUPS if _key(x) not in _c_set],
                key=lambda x: int(x.bar)):
    print(f"      ENTFALLEN  bar {int(t.bar):>5} K{int(t.kid):<4} "
          f"R {float(t.r):>+10.5f}")
for t in sorted([x for x in C_SETUPS if _key(x) not in _ka_set],
                key=lambda x: int(x.bar)):
    print(f"      NEU        bar {int(t.bar):>5} K{int(t.kid):<4} "
          f"R {float(t.r):>+10.5f}")

print("")
print("   Rejektions-Zaehler (Engine-stats) -- Delta arretiert -> kausal:")
for _k in sorted(set(A_STATS) | set(B_STATS)):
    _a, _b = A_STATS.get(_k, []), B_STATS.get(_k, [])
    _la = len(_a) if isinstance(_a, (list, tuple)) else int(_a)
    _lb = len(_b) if isinstance(_b, (list, tuple)) else int(_b)
    if _la != _lb:
        print(f"      {_k:<22}{_la:>6} -> {_lb:>6}   ({_lb - _la:+d})")
print("      (Bar 1211 liegt im kausal noch nicht bestaetigten A2-Fenster "
      "1174..1249)")

print("")
print(f"ENDE  (n = {n}; Box {_ZZ_START}..{_ZZ_ENDE}; P9 {_P9_START}..{_P9_ENDE})")
