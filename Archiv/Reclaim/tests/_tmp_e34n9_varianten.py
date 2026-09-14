# -*- coding: utf-8 -*-
"""E-34n/9 — ZP-5-Varianten (read-only): Blast-Radius eingrenzen.

Varianten:
  A) Spezifikation wie geliefert: ALLE Segmentwaende, OBEN+UNTEN.
  B) + Segmente mit deklariertem Boden-Literal (P9/hook-3) ausnehmen.
  C) B  + nur UNTEN-Waende (Boden).
  D) C  + Pierce nur bei echtem Sweep (dist > touch_band_pct).
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
    ADAPTER_V015, ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus,
)

ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

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

_ANK = ('    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\n'
        '        "OBEN": [e for e in alle if e.seite == "OBEN"],\n'
        '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}')
assert patched.count(_ANK) == 1


def _zp5(skip_lit: bool, only_unten: bool, sweep_only: bool) -> str:
    g_lit = ('            if _seg.boden_deklariert_literal is not None:\n'
             '                continue\n') if skip_lit else ''
    g_unt = ('                if _kl_seite != "UNTEN":\n'
             '                    continue\n') if only_unten else ''
    g_sw = ('                    if _dkl <= cfg.touch_band_pct:\n'
            '                        continue\n') if sweep_only else ''
    return ("    # --- ZP-5 (V019): Kantenlaeufer-Docht auf Segmentwaenden\n"
            "    _kl_hook = globals().get(\"_hook\")\n"
            "    if _kl_hook is not None "
            "and len(getattr(_kl_hook, \"segmente\", ())) > 1:\n"
            "        _kl_idx = {int(e.kid): e for e in alle}\n"
            "        for _seg in _kl_hook.segmente:\n"
            + g_lit +
            "            for _ki, _kl_seite in ((_seg.boden, \"UNTEN\"),\n"
            "                                   (_seg.decke, \"OBEN\")):\n"
            + g_unt +
            "                _ek = _kl_idx.get(int(_ki.kid))\n"
            "                if _ek is None:\n"
            "                    continue\n"
            "                _s0, _s1 = int(_seg.start_bar), int(_seg.end_bar)\n"
            "                _b0 = float(_ek.basis_bei(_s0))\n"
            "                _have = {b for b, _ in _ek.wicks}\n"
            "                for _kb in range(max(_s0, "
            "_ek.erster_pivot_bar + 2), _s1 + 1):\n"
            "                    _ext = (float(lo[_kb]) "
            "if _kl_seite == \"UNTEN\" else float(hi[_kb]))\n"
            "                    _dkl = ((_b0 - _ext) "
            "if _kl_seite == \"UNTEN\" else (_ext - _b0)) / _b0 * 100.0\n"
            + g_sw +
            "                    if 0.0 < _dkl <= 0.80 and _kb not in _have:\n"
            "                        _ek.wicks.append((_kb, _ext))\n"
            "                        _have.add(_kb)\n"
            "                if _ek.schlaf_windows:\n"
            "                    _ek.schlaf_windows = [\n"
            "                        _w for _w in _ek.schlaf_windows\n"
            "                        if not (_w[0] < _s1\n"
            "                                and (_w[1] is None "
            "or _w[1] > _s0))]\n"
            "                _ek.status = \"AKTIV\"\n")

spec = importlib.util.spec_from_loader("ke_e34n9", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n9"] = eng
exec(compile(src_datei, str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX_END = int(scan["box_end_bar"])      # dynamische Kalenderkante (644)
scan["box_end_bar"] = scan["n"]
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
ts = scan["d"]["ts"]
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


ORIG = eng._se_trades
ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _rs_lok


def _lauf(quelle: str, hook):
    _ns = dict(ns)
    _ns["_hook"] = hook
    _HOOK[0] = hook
    exec(compile(quelle, "<se>", "exec"), _ns)
    eng._se_trades = _ns["_se_trades"]
    try:
        _sc = copy.deepcopy(scan)
        res = eng._se_trades(_sc, cfg)
    finally:
        eng._se_trades = ORIG
    # _se_trades liefert (setups, stats) -> Trade-Liste + mutierte Scan-Kopie.
    return res[0], _sc


def _waende(sc) -> dict:
    """Docht-/Schlaf-Zustand aller deklarierten Segmentwaende einer Scan-Kopie."""
    _idx = {int(e.kid): e for e in list(sc["edges"]) + list(sc["seeds"])}
    out: dict = {}
    for _seg in ADAPTER_V019.segmente:
        for _ki in (_seg.boden, _seg.decke):
            _e = _idx.get(int(_ki.kid))
            if _e is not None:
                out[int(_ki.kid)] = ([b for b, _ in _e.wicks],
                                     list(_e.schlaf_windows))
    return out


_W_VOR = _waende(scan)


def _h1(tr) -> float:
    """H1-Box: Trades mit Einstieg VOR der dynamischen Kalenderkante."""
    return sum(t.r for t in tr if t.entry_bar < BOX_END)


def _p9(tr) -> float:
    """P9_BODEN_RECLAIM (arretierter Anker +23.435111 R)."""
    return sum(t.r for t in tr if P9A <= t.bar <= P9B)


def _h2(tr) -> float:
    """H2-Bereich: Trades mit Einstieg AB der dynamischen Kalenderkante."""
    return sum(t.r for t in tr if t.entry_bar >= BOX_END)


def _n1(tr) -> int:
    return sum(1 for t in tr if t.entry_bar < BOX_END)


def _n2(tr) -> int:
    return sum(1 for t in tr if t.entry_bar >= BOX_END)


print("=" * 116)
print("E-34n/9  ZP-5-VARIANTEN (read-only)")
print("=" * 116)
print(f"  H1/H2-Partition = Einstieg vs. dynamische Kalenderkante "
      f"box_end={BOX_END} (arretierte Semantik).")
print(f"  Gating-Beleg: len(V015.segmente)={len(ADAPTER_V015.segmente)} | "
      f"len(V019.segmente)={len(ADAPTER_V019.segmente)} | "
      f"P9 {P9A}..{P9B} | A1/A2 {AUTO_A}..{AUTO_B}")
print(f"{'Variante':<10} {'n':>3} {'Summe R':>12} {'H1 n/R':>18} "
      f"{'H2 n/R':>18} {'P9 n/R':>18}  {'V19-Delta-R':>12}")
_base, _sc_base = _lauf(patched, ADAPTER_V019)
_bb = {(t.bar, t.kid) for t in _base}
print(f"{'ZP-4':<10} {len(_base):>3} {sum(t.r for t in _base):>+12.6f} "
      f"{_n1(_base):>3}/{_h1(_base):>+13.6f} "
      f"{_n2(_base):>3}/{_h2(_base):>+13.6f} "
      f"{sum(1 for t in _base if P9A <= t.bar <= P9B):>3}"
      f"/{_p9(_base):>+13.6f}   (Referenz)")
_V18, _sc_v18 = _lauf(patched, ADAPTER_V015)
print(f"{'V018':<10} {len(_V18):>3} {sum(t.r for t in _V18):>+12.6f} "
      f"{_n1(_V18):>3}/{_h1(_V18):>+13.6f} "
      f"{_n2(_V18):>3}/{_h2(_V18):>+13.6f} "
      f"{sum(1 for t in _V18 if P9A <= t.bar <= P9B):>3}"
      f"/{_p9(_V18):>+13.6f}   (Gegenprobe)")
for _name, _sl, _ou, _sw in (("A (Spec)", False, False, False),
                             ("B (+lit)", True, False, False),
                             ("C (+UNTEN)", True, True, False),
                             ("D (+sweep)", True, True, True)):
    _tr, _sc = _lauf(patched.replace(_ANK, _ANK + "\n" + _zp5(_sl, _ou, _sw)),
                     ADAPTER_V019)
    _nur = [t for t in _tr if (t.bar, t.kid) not in _bb]
    _weg = [t for t in _base if (t.bar, t.kid) not in {(x.bar, x.kid)
                                                       for x in _tr}]
    _delta = sum(t.r for t in _tr) - sum(t.r for t in _base)
    print(f"{_name:<10} {len(_tr):>3} {sum(t.r for t in _tr):>+12.6f} "
          f"{_n1(_tr):>3}/{_h1(_tr):>+13.6f} "
          f"{_n2(_tr):>3}/{_h2(_tr):>+13.6f} "
          f"{sum(1 for t in _tr if P9A <= t.bar <= P9B):>3}"
          f"/{_p9(_tr):>+13.6f}   {_delta:>+12.6f}")
    for t in sorted(_weg, key=lambda x: x.bar):
        print(f"      WEG {t.bar:>5} {ts.iloc[t.bar].strftime('%d.%m. %H:%M')}"
              f" K{int(t.kid):<3} {t.richtung:<5} e_bar={t.entry_bar:>5} "
              f"r={t.r:+.6f} {t.stufe}")
    for t in sorted(_nur, key=lambda x: x.bar):
        print(f"      NEU {t.bar:>5} {ts.iloc[t.bar].strftime('%d.%m. %H:%M')}"
              f" K{int(t.kid):<3} {t.richtung:<5} e_bar={t.entry_bar:>5} "
              f"r={t.r:+.6f} {t.stufe}")
    _w = _waende(_sc)
    for _kid in sorted(_w):
        _alt_d, _alt_s = _W_VOR[_kid]
        _neu_d, _neu_s = _w[_kid]
        if _alt_d == _neu_d and _alt_s == _neu_s:
            continue
        _zu = [b for b in _neu_d if b not in _alt_d]
        print(f"      KANTE K{_kid:<3} Dochte +{_zu if _zu else '[]'}"
              f"  Schlaf {_alt_s} -> {_neu_s if _neu_s else '[]'}")
print("\n  Soll ZP-4/V019: 23 / +82.614385  (H1 8 / +38.919584 | "
      "H2 15 / +43.694801 | P9 +23.435111)")
print("  Soll V018     : 17 / +65.835576  (H1 8 / +38.919584 | "
      "H2  9 / +26.915992)")
print("ENDE E-34n/9")
