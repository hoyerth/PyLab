# -*- coding: utf-8 -*-
"""Stufe 5.2: ZP-5-Extraktion -- Bit-Identitaets-Trockenlauf (read-only).

Verglichen werden ZWEI Wege auf je eigenen deepcopy-Instanzen:

  A  INLINE  -- der arretierte Quelltext-Patch ``A_KL_DOCHT`` (ZP-5) im
                ``_se_trades``-Rumpf (Status quo).
  B  VORLAUF -- dieselbe Wirkung als eigenstaendige Funktion
                ``erweitere_segmentwand_dochte()``, ausgefuehrt auf der
                per-run deepcopy VOR ``_se_trades``.

Geprueft wird auf ZWEI Ebenen:
  (1) OBJEKT: wicks / schlaf_windows / status je kid unmittelbar nach der
      ZP-5-Wirkung (vor dem Loop) -- Transkriptions-Treue.
  (2) ERGEBNIS: alle Trades (bar/kid/r/r1/r2/grund1/grund2) der vollen
      Laeufe -- Alpha-Treue.

Kriterium (Anwender): volle Bit-Identitaet, sonst wird die Extraktion
VERWORFEN. Es wird keine Produktivdatei geschrieben.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import numpy as np  # noqa: E402

from backtest_lab.phasen_regime_adapter import ADAPTER_V019_KAUSAL  # noqa: E402

ok = True


def _pruefe(name: str, ist, soll) -> None:
    global ok
    hit = ist == soll
    ok = ok and hit
    print(f"  [{'OK ' if hit else 'FAIL'}] {name:<54} ist={ist}  soll={soll}")


class _Quiet:
    def __init__(self) -> None:
        self.puffer: List[str] = []

    def write(self, s: str) -> int:
        self.puffer.append(s)
        return len(s)

    def writelines(self, lines) -> None:
        self.puffer.extend(lines)

    def flush(self) -> None:
        return None

    def reconfigure(self, *args, **kwargs) -> None:
        return None


_stdout = sys.stdout
_quiet = _Quiet()
try:
    sys.stdout = _quiet
    _spec = importlib.util.spec_from_file_location(
        "h_zp5", ROOT / "test" / "_chk_v019_kausal_vergleich.py")
    H = importlib.util.module_from_spec(_spec)
    sys.modules["h_zp5"] = H
    _spec.loader.exec_module(H)  # type: ignore[union-attr]
finally:
    sys.stdout = _stdout

engine = H.engine
cfg = H.cfg
scan = H.scan
H.ns["_hook"] = ADAPTER_V019_KAUSAL        # fuer _zv/_ueb im Objekt-Test

print("=" * 100)
print("STUFE 5.2 -- ZP-5-EXTRAKTION: BIT-IDENTITAETS-TROCKENLAUF")
print("=" * 100)

# ---------------------------------------------------------------- Bausteine
# (a) 13-Bestands-Basis exakt wie im Harness
_src_datei = (ROOT / "test" / "tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8")
_src_tree = ast.parse(_src_datei)
_src_node = next(x for x in _src_tree.body
                 if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
_src0 = ast.get_source_segment(_src_datei, _src_node)
assert _src0 is not None
for _nm in H._KETTE:
    assert _src0.count(H.basis[_nm]) == 1, (_nm, _src0.count(H.basis[_nm]))
    _src0 = _src0.replace(H.basis[_nm], H.basis[_nm + "_NEW"])
base13 = _src0
print(f"\nBestands-Basis (13 Paare): {len(base13)} Zeichen")

# (b) Zielzonen-Paare per AST aus dem Renderer lesen
_ren = (ROOT / "test" / "tmp_png_aug_sichttest.py").read_text(encoding="utf-8")
_ren_tree = ast.parse(_ren)
_fn = next(x for x in _ren_tree.body
           if isinstance(x, ast.FunctionDef)
           and x.name == "_wende_zielzonen_patches_v019")
_paare_node = next(x for x in ast.walk(_fn)
                   if isinstance(x, ast.Assign)
                   and getattr(x.targets[0], "id", "") == "paare")
PAARE = ast.literal_eval(_paare_node.value)
print(f"Zielzonen-Paare: {[p[0] for p in PAARE]}")

_KL = [p for p in PAARE if p[0] == "A_KL_DOCHT"]
assert len(_KL) == 1
KL_NEW = _KL[0][2]

patched_mit = H.patched_src            # 13 Bestands + ZP-4 + ZP-5


def _ohne_kl(quelle: str) -> str:
    """Wendet nur die Paare 1-4 an (ZP-5 ausgelassen)."""
    out = quelle
    for _name, _alt, _neu in PAARE:
        if _name == "A_KL_DOCHT":
            continue
        assert out.count(_alt) == 1, (_name, out.count(_alt))
        out = out.replace(_alt, _neu, 1)
    return out


patched_ohne = _ohne_kl(base13)
_pruefe("patched_mit enthaelt ZP-5", "ZP-5(D)" in patched_mit, True)
_pruefe("patched_ohne enthaelt kein ZP-5", "ZP-5(D)" in patched_ohne, False)

# ---------------------------------------- (1) OBJEKT-Ebene: Vorlauf vs Inline


def erweitere_segmentwand_dochte(
    scan_copy: dict,
    hook,
    cfg_v,
    hi: np.ndarray,
    lo: np.ndarray,
    ueb,
) -> None:
    """Idempotenter Scan-Schritt: Kantenlaeufer-Durchstich (ZP-5, E-34n/10+11).

    Vorbedingungen (beide noetig): Mehrsegment-Adapter; P9 (eigenes Boden-
    Literal) ausgenommen. Nur echte Durchstiche jenseits des Touch-Bands.

    Args:
        scan_copy: Lauf-eigene Kopie (edges/seeds werden in-place erweitert).
        hook: Gebundener Phasen-Adapter (Index 0 = P9).
        cfg_v: Harness-Konfiguration (touch_band_pct).
        hi: High-Array des Fensters.
        lo: Low-Array des Fensters.
        ueb: Segment-lokale Ueberdehnungsschranke (ZP-4-Helfer).
    """
    if hook is None or len(getattr(hook, "segmente", ())) <= 1:
        return
    _alle = list(scan_copy["edges"]) + list(scan_copy["seeds"])
    _idx = {int(e.kid): e for e in _alle}
    for _seg in hook.segmente:
        if _seg.boden_deklariert_literal is not None:
            continue                      # P9 & Co: eigenes Boden-Literal
        for _ki, _seite in ((_seg.boden, "UNTEN"), (_seg.decke, "OBEN")):
            _ek = _idx.get(int(_ki.kid))
            if _ek is None:
                continue
            _s0, _s1 = int(_seg.start_bar), int(_seg.end_bar)
            _b0 = float(_ek.basis_bei(_s0))      # TRAGENDE Wahl
            _have = {b for b, _ in _ek.wicks}
            for _kb in range(max(_s0, _ek.erster_pivot_bar + 2), _s1 + 1):
                _ext = (float(lo[_kb]) if _seite == "UNTEN"
                        else float(hi[_kb]))
                _dkl = ((_b0 - _ext) if _seite == "UNTEN"
                        else (_ext - _b0)) / _b0 * 100.0
                if _dkl <= cfg_v.touch_band_pct:
                    continue                  # Band-Rauschen, kein Sweep
                if _dkl <= ueb(_kb) and _kb not in _have:
                    _ek.wicks.append((_kb, _ext))
                    _have.add(_kb)
            if _ek.schlaf_windows:            # Segmentwand schlaeft
                _ek.schlaf_windows = [        # nicht im eign. Segment
                    _w for _w in _ek.schlaf_windows
                    if not (_w[0] < _s1 and (_w[1] is None or _w[1] > _s0))]
            _ek.status = "AKTIV"


def _objekt_stand(sc: dict) -> Dict[int, Tuple]:
    out = {}
    for e in list(sc["edges"]) + list(sc["seeds"]):
        out[int(e.kid)] = (tuple((int(b), round(float(p), 12))
                                 for b, p in e.wicks),
                           tuple((int(w[0]),
                                  None if w[1] is None else int(w[1]))
                                 for w in e.schlaf_windows),
                           str(e.status))
    return out


# A: Inline-Block isoliert ausfuehren (exakt der arretierte Quelltext)
_nsA = dict(engine.__dict__)
_nsA["_hook"] = ADAPTER_V019_KAUSAL
_nsA["_ueb"] = H.ns["_ueb"]
_nsA["cfg"] = cfg
_scA = copy.deepcopy(scan)
_nsA["alle"] = list(_scA["edges"]) + list(_scA["seeds"])
_nsA["hi"] = _scA["d"]["high"].to_numpy(dtype=float)
_nsA["lo"] = _scA["d"]["low"].to_numpy(dtype=float)
exec(compile(textwrap.dedent(KL_NEW), "<kl_inline>", "exec"), _nsA)  # noqa: S102
_standA = _objekt_stand(_scA)

# B: Vorlauf-Funktion
_scB = copy.deepcopy(scan)
erweitere_segmentwand_dochte(
    _scB, ADAPTER_V019_KAUSAL, cfg,
    _scB["d"]["high"].to_numpy(dtype=float),
    _scB["d"]["low"].to_numpy(dtype=float),
    H.ns["_ueb"])
_standB = _objekt_stand(_scB)

print("\n(1) OBJEKT-EBENE (Zustand unmittelbar nach ZP-5, vor dem Loop)")
_pruefe("Kanten-Index identisch", sorted(_standA) == sorted(_standB), True)
_diff = [k for k in _standA if _standA[k] != _standB.get(k)]
_pruefe("alle Kanten objktidentisch (wicks+schlaf+status)", _diff, [])
print(f"       Kanten: {len(_standA)} | Wicks gesamt: "
      f"{sum(len(v[0]) for v in _standA.values())}")
for _k in sorted(set(_standA) | set(_standB)):
    _wa = len(_standA.get(_k, ((),))[0])
    _wb = len(_standB.get(_k, ((),))[0])
    if (_wa != _wb or _standA.get(_k) != _standB.get(_k)):
        print(f"       ABWEICHUNG K{_k}: {_wa} vs {_wb} Wicks")

# ------------------------------------------- (2) ERGEBNIS-Ebene: volle Laeufe


def _lauf(quelle: str, hook, mit_vorlauf: bool):
    H.ns["_hook"] = hook
    exec(compile(quelle, "<lauf>", "exec"), H.ns)  # noqa: S102
    sc = copy.deepcopy(scan)
    if mit_vorlauf:
        erweitere_segmentwand_dochte(
            sc, hook, cfg,
            sc["d"]["high"].to_numpy(dtype=float),
            sc["d"]["low"].to_numpy(dtype=float),
            H.ns["_ueb"])
    setups, st = H.ns["_se_trades"](sc, cfg)
    return list(setups), dict(st), sc


def _sig(t):
    return (int(t.bar), int(t.kid), round(float(t.r), 12),
            round(float(t.r1), 12), round(float(t.r2), 12),
            str(t.grund1), str(t.grund2))


_A_SET, _A_ST, _A_SC = _lauf(patched_mit, ADAPTER_V019_KAUSAL, False)
_B_SET, _B_ST, _B_SC = _lauf(patched_ohne, ADAPTER_V019_KAUSAL, True)

print("\n(2) ERGEBNIS-EBENE (volle Laeufe, ADAPTER_V019_KAUSAL)")
_pruefe("A (inline)  Trades", len(_A_SET), 23)
_pruefe("A (inline)  R", round(sum(float(t.r) for t in _A_SET), 6), 85.577150)
_pruefe("B (Vorlauf) Trades", len(_B_SET), 23)
_pruefe("B (Vorlauf) R", round(sum(float(t.r) for t in _B_SET), 6), 85.577150)
_pruefe("Trade-Signaturen bit-identisch",
        sorted(_sig(t) for t in _B_SET), sorted(_sig(t) for t in _A_SET))
_pruefe("stats identisch", _B_ST, _A_ST)
_pruefe("Endzustand Kanten bit-identisch",
        _objekt_stand(_B_SC), _objekt_stand(_A_SC))

if ok:
    print("\n  Ergebnis: Extraktion ist BIT-IDENTISCH -> extrahierbar.")
else:
    print("\n  Ergebnis: ABWEICHUNG -> Extraktion VERWERFEN "
          "(A_KL_DOCHT bleibt arretiert).")

print(f"\nGESAMT: {'OK' if ok else 'FEHLER'}")
raise SystemExit(0 if ok else 1)
