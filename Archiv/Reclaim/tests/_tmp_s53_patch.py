# -*- coding: utf-8 -*-
"""Stufe 5.3, Phase 1: Renderer-Refactoring (A_KL_DOCHT -> Vorlauf-Funktion).

Fail-Loud: jede Ersetzung muss GENAU EINMAL greifen (count == 1).
"""
from __future__ import annotations

from pathlib import Path

P = Path(__file__).resolve().parent / "tmp_png_aug_sichttest.py"
s = P.read_text(encoding="utf-8")


def _rep(alt: str, neu: str, name: str) -> None:
    global s
    assert s.count(alt) == 1, (name, s.count(alt))
    s = s.replace(alt, neu, 1)


# ---------------------------------------------------------------- (A) Imports
_rep(
    "from typing import Final, Literal, Optional, Sequence, Tuple, Union",
    "from typing import (Callable, Final, List, Literal, Optional, Sequence,\n"
    "                    Tuple, Union)",
    "typing-import",
)

# ------------------------------------------------------------- (B) Docstring
_rep(
    "    Returns:\n"
    "        Quelltext mit ZP-4 (Ueberdehnung, Quartil-Reset, M6-Schlaf-Filter,\n"
    "        Sweep-Basis-Aktivierung) + Kantenlaeufer-Durchstich (ZP-5, E-34n).",
    "    Returns:\n"
    "        Quelltext mit den vier ZP-4-Regeln (Ueberdehnung, Quartil-Reset,\n"
    "        M6-Schlaf-Filter, Sweep-Basis-Aktivierung). Der Kantenlaeufer-\n"
    "        Durchstich (ZP-5, E-34n) liegt seit Stufe 5.3 NICHT mehr im\n"
    "        Quelltext, sondern in ``erweitere_segmentwand_dochte()`` und wird\n"
    "        in ``_lauf()`` auf der laufeigenen deepcopy ausgefuehrt (Abschn. 75).",
    "docstring",
)

# --------------------------------------------------- (C) Paar 5 A_KL_DOCHT raus
_start = "        # (5) ZP-5(D), arretiert in E-34n/10+11:"
_end = "         '                _ek.status = \"AKTIV\"'),\n"
_i = s.index(_start)
_j = s.index(_end, _i) + len(_end)
s = s[: _i] + s[_j:]
assert "A_KL_DOCHT" not in s, "A_KL_DOCHT-Rest"

# --------------------------------------------- (D) Vorlauf-Funktion einziehen
_KL_FUNC = '''def erweitere_segmentwand_dochte(
    scan_copy: dict,
    hook: PhasenRegimeAdapter,
    cfg: engine.StraightEdgeHarnessKonfiguration,
    hi: np.ndarray,
    lo: np.ndarray,
    ueb_fn: Callable[[int], float],
) -> None:
    """Idempotenter Scan-Schritt: Kantenlaeufer-Durchstich (ZP-5, E-34n/10+11).

    Wird ausschliesslich innerhalb von ``_lauf()`` auf der laufeigenen
    ``deepcopy`` VOR ``engine._se_trades()`` ausgefuehrt -- niemals auf dem
    Master-Objekt ``scan`` (Abschnitt 75). Vorbedingungen: Mehrsegment-
    Adapter; P9 (eigenes Boden-Literal) ausgenommen. Nur echte Durchstiche
    jenseits des Touch-Bands (``cfg.touch_band_pct``) und innerhalb der
    segment-lokalen Ueberdehnungsschranke ``ueb_fn``.

    Args:
        scan_copy: Lauf-eigene Kopie (edges/seeds werden in-place erweitert).
        hook: Gebundener Phasen-Adapter (Segment 0 = P9).
        cfg: Harness-Konfiguration (``touch_band_pct``).
        hi: High-Array des Fensters.
        lo: Low-Array des Fensters.
        ueb_fn: Segment-lokale Ueberdehnungsschranke (ZP-4-Helfer ``_ueb``).
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
                if _dkl <= cfg.touch_band_pct:
                    continue                  # Band-Rauschen, kein Sweep
                if _dkl <= ueb_fn(_kb) and _kb not in _have:
                    _ek.wicks.append((_kb, _ext))
                    _have.add(_kb)
            if _ek.schlaf_windows:            # Segmentwand schlaeft
                _ek.schlaf_windows = [        # nicht im eign. Segment
                    _w for _w in _ek.schlaf_windows
                    if not (_w[0] < _s1 and (_w[1] is None or _w[1] > _s0))]
            _ek.status = "AKTIV"


'''

_LAUF_ALT = '''def _lauf(hook: PhasenRegimeAdapter, mit_patch: bool):
    """Ein Engine-Lauf mit gebundenem Adapter (Engine-Klasse bleibt sauber)."""
    ns["_hook"] = hook
    exec(compile(patched_src, "<se_trades_sichttest>", "exec"), ns)
    if not mit_patch:
        return ORIG(copy.deepcopy(scan), cfg)
    engine._se_trades = ns["_se_trades"]
    try:
        return engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = ORIG
'''

_LAUF_NEU = _KL_FUNC + '''def _lauf(hook: PhasenRegimeAdapter, mit_patch: bool):
    """Ein Engine-Lauf mit gebundenem Adapter (Engine-Klasse bleibt sauber).

    Der ZP-5-Vorlauf laeuft -- nur bei ``mode == "V019"`` und mehrsegmentigem
    Adapter -- auf der laufeigenen ``sc_copy`` unmittelbar VOR
    ``engine._se_trades()``. Das Master-Objekt ``scan`` bleibt unberuehrt
    (Abschnitt 75, Doppel-Gatung Quelltext + Laufzeit).
    """
    ns["_hook"] = hook
    exec(compile(patched_src, "<se_trades_sichttest>", "exec"), ns)
    sc_copy = copy.deepcopy(scan)
    if not mit_patch:
        return ORIG(sc_copy, cfg)
    if KONF.mode == "V019" and len(getattr(hook, "segmente", ())) > 1:
        erweitere_segmentwand_dochte(
            sc_copy, hook, cfg,
            sc_copy["d"]["high"].to_numpy(dtype=float),
            sc_copy["d"]["low"].to_numpy(dtype=float),
            _ueb)
    engine._se_trades = ns["_se_trades"]
    try:
        return engine._se_trades(sc_copy, cfg)
    finally:
        engine._se_trades = ORIG
'''

_rep(_LAUF_ALT, _LAUF_NEU, "_lauf+vorlauf")

P.write_text(s, encoding="utf-8")
print(f"OK  {P.name}: {len(s)} Zeichen")
print(f"   ZP-Paare: {s.count('(\"A_UEB1\"')} A_UEB1, "
      f"{s.count('(\"A_KL_DOCHT\"')} A_KL_DOCHT")
print(f"   erweitere_segmentwand_dochte: "
      f"{s.count('def erweitere_segmentwand_dochte')}x def, "
      f"{s.count('erweitere_segmentwand_dochte(')}x Aufruf")
