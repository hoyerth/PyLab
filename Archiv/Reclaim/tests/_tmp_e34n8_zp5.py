# -*- coding: utf-8 -*-
"""E-34n/8 — ZP-5 (Kantenlaeufer-Docht auf Segmentwaenden): read-only Messung.

Vergleicht im selben Prozess:
  (a) V019 mit ZP-4   = heute arretierter Stand (23 Trades / +82.614385 R)
  (b) V019 mit ZP-4+ZP-5 (Kantenlaeufer-Docht)

ZP-5 wird NICHT in die Engine/den Renderer geschrieben, sondern nur hier
als Quelltext-Injektion in das deepkopierte Scan-Objekt angewandt.

Regel (Spezifikation des Anwenders, E-34n):
  * Nur deklarierte SEGMENTWAENDE (seg.boden / seg.decke).
  * Ein Bar b im Segment, dessen Extrem die eingefrorene Wandbasis
    ueber die Basis hinaus durchstoesst und <= 0.80 % Ueberdehnung bleibt,
    wird als Docht registriert (wicks + touch_conf), sofern b noch kein
    Docht ist und b >= erster_pivot_bar + 2.
  * .basis (statisch) und ist_prim_anker bleiben unberuehrt.
  * Schlaf-Fenster, die das Segment der Wand ueberlappen, werden fuer die
    Wand aufgehoben (Segmentwand schlaeft nicht in ihrem eigenen Segment).
  * Q3/Q17 (Non-Expansion) bleibt unangetastet.
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
    _s, _new = RENNS[_nm], RENNS[_nm + "_NEW"]
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)
patched = RENNS["_wende_zielzonen_patches_v019"](patched)

# --- ZP-5-Anker: der seite_edges-Block in _se_trades -----------------------
_ANK = ('    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\n'
        '        "OBEN": [e for e in alle if e.seite == "OBEN"],\n'
        '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}')
assert patched.count(_ANK) == 1, patched.count(_ANK)

_ZP5 = """    # --- ZP-5 (nur V019): Kantenlaeufer-Docht auf deklarierten Segmentwaenden
    _kl_hook = globals().get("_hook")
    if _kl_hook is not None and len(getattr(_kl_hook, "segmente", ())) > 1:
        _kl_idx = {int(e.kid): e for e in alle}
        for _seg in _kl_hook.segmente:
            for _ki, _kl_seite in ((_seg.boden, "UNTEN"),
                                   (_seg.decke, "OBEN")):
                _ek = _kl_idx.get(int(_ki.kid))
                if _ek is None:
                    continue
                _s0, _s1 = int(_seg.start_bar), int(_seg.end_bar)
                _b0 = float(_ek.basis_bei(_s0))
                _have = {b for b, _ in _ek.wicks}
                for _kb in range(max(_s0, _ek.erster_pivot_bar + 2), _s1 + 1):
                    _ext = (float(lo[_kb]) if _kl_seite == "UNTEN"
                            else float(hi[_kb]))
                    _dkl = ((_b0 - _ext) if _kl_seite == "UNTEN"
                            else (_ext - _b0)) / _b0 * 100.0
                    if 0.0 < _dkl <= 0.80 and _kb not in _have:
                        _ek.wicks.append((_kb, _ext))
                        _have.add(_kb)
                if _ek.schlaf_windows:
                    _ek.schlaf_windows = [
                        _w for _w in _ek.schlaf_windows
                        if not (_w[0] < _s1
                                and (_w[1] is None or _w[1] > _s0))]
                _ek.status = "AKTIV"
"""
patched_zp5 = patched.replace(_ANK, _ANK + "\n" + _ZP5)

spec = importlib.util.spec_from_loader("ke_e34n8", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n8"] = eng
exec(compile(src_datei, str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
ts = scan["d"]["ts"]
_kl82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
             if int(e.kid) == 82)

SEG = ADAPTER_V019.segmente
AUTO_A, AUTO_B = SEG[1].start_bar, SEG[-1].end_bar
P9A, P9B = SEG[0].start_bar, SEG[0].end_bar
print("=" * 116)
print("E-34n/8  ZP-5 KANTENLAEUFER-DOCHT  (read-only Messung)")
print("=" * 116)
print(f"A1 {SEG[1].start_bar}..{SEG[1].end_bar} Decke K{SEG[1].decke.kid} "
      f"({SEG[1].decke.provenienz_basis}) | "
      f"Boden K{SEG[1].boden.kid} ({SEG[1].boden.provenienz_basis})")
print(f"A2 {SEG[2].start_bar}..{SEG[2].end_bar} Decke K{SEG[2].decke.kid} "
      f"({SEG[2].decke.provenienz_basis}) | "
      f"Boden K{SEG[2].boden.kid} ({SEG[2].boden.provenienz_basis})")
print(f"K82 VORHER: wicks={[b for b, _ in _kl82.wicks]} "
      f"schlaf_windows={_kl82.schlaf_windows}")
print(f"  ist_aktiv_bei(1072/1075) = {_kl82.ist_aktiv_bei(1072)} / "
      f"{_kl82.ist_aktiv_bei(1075)}")

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
        _scan = copy.deepcopy(scan)
        res = eng._se_trades(_scan, cfg)
    finally:
        eng._se_trades = ORIG
    _k82 = next(e for e in list(_scan["edges"]) + list(_scan["seeds"])
                if int(e.kid) == 82)
    return res, _k82


(V19, st19), k82_alt = _lauf(patched, ADAPTER_V019)
(V19b, st19b), k82_neu = _lauf(patched_zp5, ADAPTER_V019)
(V18, _), _ = _lauf(patched_zp5, ADAPTER_V015)

print("\n" + "=" * 116)
print("K82 NACH ZP-5")
print("=" * 116)
print(f"  wicks        = {[b for b, _ in k82_neu.wicks]}")
print(f"  statische .basis = {float(k82_neu.basis):.4f} (vorher "
      f"{float(k82_alt.basis):.4f})")
print(f"  schlaf_windows   = {k82_neu.schlaf_windows}")
print(f"  ist_aktiv_bei(1072/1075/1173) = {k82_neu.ist_aktiv_bei(1072)} / "
      f"{k82_neu.ist_aktiv_bei(1075)} / {k82_neu.ist_aktiv_bei(1173)}")
for _b in (1056, 1072, 1073, 1074, 1075, 1076):
    print(f"    bar {_b}: touch_conf alt={k82_alt.touch_conf(_b)} "
          f"neu={k82_neu.touch_conf(_b)} | basis_bei neu="
          f"{k82_neu.basis_bei(_b):.4f}")

print("\n" + "=" * 116)
print("TRADE-VERGLEICH V019 (ZP-4)  vs  V019 (ZP-4+ZP-5)")
print("=" * 116)
_k19 = {(t.bar, t.kid) for t in V19}
_k19b = {(t.bar, t.kid) for t in V19b}
print(f"  V019 ZP-4   : {len(V19):>2} Trades / {sum(t.r for t in V19):+.6f} R")
print(f"  V019 ZP-4+5 : {len(V19b):>2} Trades / {sum(t.r for t in V19b):+.6f} R"
      f"   (Delta {sum(t.r for t in V19b) - sum(t.r for t in V19):+.6f} R)")
print(f"  V018        : {len(V18):>2} Trades / {sum(t.r for t in V18):+.6f} R")


def _zz(t) -> str:
    return (f"{t.bar:>5} {ts.iloc[t.bar].strftime('%d.%m. %H:%M')} "
            f"K{int(t.kid):<3} {t.richtung:<5} entry={t.entry:.4f} "
            f"sl={t.sl:.4f} poc={t.poc:.4f} tp2={t.tp2:.4f} "
            f"e_bar={t.entry_bar:>5} r={t.r:+.6f} stufe={t.stufe}")


print("\n  NUR in ZP-4 (entfaellt):")
for t in sorted(V19, key=lambda x: x.bar):
    if (t.bar, t.kid) not in _k19b:
        print("    " + _zz(t))
print("\n  NUR in ZP-4+ZP-5 (neu):")
for t in sorted(V19b, key=lambda x: x.bar):
    if (t.bar, t.kid) not in _k19:
        print("    " + _zz(t))
print("\n  GEAENDERT (gleicher bar/kid, andere Werte):")
_d19 = {(t.bar, t.kid): t for t in V19}
for t in sorted(V19b, key=lambda x: x.bar):
    a = _d19.get((t.bar, t.kid))
    if a is None:
        continue
    if (a.entry, a.sl, a.r, a.entry_bar) != (t.entry, t.sl, t.r, t.entry_bar):
        print("    ALT " + _zz(a))
        print("    NEU " + _zz(t))

print("\n" + "=" * 116)
print("GEGENPROBEN (Invarianz)")
print("=" * 116)
print(f"  V18 aus patched_zp5 : {len(V18)} Trades / "
      f"{sum(t.r for t in V18):+.6f} R  (Soll 17 / +65.835576)")
print("\nENDE E-34n/8")
