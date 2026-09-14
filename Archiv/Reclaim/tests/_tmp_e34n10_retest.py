# -*- coding: utf-8 -*-
"""E-34n/10 — Der Retest an Bar 1172 (K82, A1-Boden): read-only Nachweis.

Fragen des Anwenders:
  (1) Was ist mit 26.08. 17:00 (Bar 1172)? Liegt an *derselben* Kante K82 und
      macht einen Reclaim?
  (2) Warum bleibt K62@1075 in Variante D erhalten, waehrend er in B entfaellt?
  (3) Kanten-Audit: warum wird nur Bar 1075 (nicht 1072-1074) in D zum Docht?
  (4) OBEN-Symmetrie: bleibt K67@882 durch das P9-Gate inaktiv?

Vorgehen: identisches AST-Geruest wie _tmp_e34n2_trace.py (Basis-13-Literale +
ZP-4-Funktion aus dem Renderer, NICHT importiert), danach 17 Entscheidungs-
Sonden + ein Pool-Dump. ZP-5 (Varianten B und D) wird NUR als Quelltext-
Injektion in das jeweilige deepkopierte Scan-Objekt angewandt.
Kein Schreiben in Adapter/Engine/Renderer.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
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
OUT = ROOT / "test" / "_tmp_e34n10_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

# ------------------------------------------------- Renderer-Regeln per AST
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
assert src is not None
_ORDER = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
patched = src
for _nm in _ORDER:
    _s, _new = RENNS[_nm], RENNS[_nm + "_NEW"]
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)
patched = RENNS["_wende_zielzonen_patches_v019"](patched)


def rep(s: str, old: str, new: str, n_erwartet: int = 1) -> str:
    _c = s.count(old)
    assert _c == n_erwartet, (old[:60], _c, n_erwartet)
    return s.replace(old, new)


# ---------------- Pool-Dump (E-34n/7, Anker verifiziert) ------------------
_ANK_POOL = ('        if _freigabe_kid is not None:\n'
             '            pool = [e for e in pool if e.kid != _freigabe_kid]')
patched = rep(
    patched, _ANK_POOL,
    _ANK_POOL + '\n'
    '        if 1065 <= k <= 1180:\n'
    '            _P.append((k, richtung,\n'
    '                       int(_freigabe_kid) if _freigabe_kid is not None '
    'else -1,\n'
    '                       [(int(e.kid), round(_dist(e), 6),\n'
    '                         int(e.touch_conf(k)), bool(_existiert(e, k)),\n'
    '                         bool(e.ist_aktiv_bei(k))) for e in pool]))')

# ---------------- 17 Entscheidungs-Sonden (E-34n/2) ----------------------
patched = rep(
    patched,
    '            # --- M6: Innenlevel-Blocker',
    '            _T.append((k, richtung, "KANDIDAT", int(kd.kid)))\n'
    '            # --- M6: Innenlevel-Blocker')
patched = rep(patched, 'stats["blocker"] += 1',
              'stats["blocker"] += 1; _T.append((k, richtung, "BLOCKER", '
              'int(kd.kid)))')
patched = rep(patched, 'stats["quartil_blockiert"] += 1',
              'stats["quartil_blockiert"] += 1; _T.append((k, richtung, '
              '"QUARTIL", int(kd.kid)))')
patched = rep(patched, 'stats["f3"] += 1',
              'stats["f3"] += 1; _T.append((k, richtung, "F3", int(kd.kid)))')
patched = rep(patched, 'stats["zyklus_blockiert"] += 1',
              'stats["zyklus_blockiert"] += 1; _T.append((k, richtung, '
              '"ZYKLUS", int(kd.kid)))')
patched = rep(patched, 'stats["kein_gegner"] += 1',
              'stats["kein_gegner"] += 1; _T.append((k, richtung, '
              '"KEIN_GEGNER", int(kd.kid)))')
patched = rep(patched, 'stats["frisch_blockiert"] += 1',
              'stats["frisch_blockiert"] += 1; _T.append((k, richtung, '
              '"FRISCH_JUNG", int(e.kid)))')
_RAUM = 'stats["kein_raum"] += 1'
_RAUM_TAGS = ("H2_BLOCKIERT", "RAUM_SHORT_UNTER", "RAUM_SHORT_MINDIST",
              "RAUM_LONG_UEBER", "RAUM_LONG_MINDIST", "RAUM_POC",
              "RAUM_SHORT_ORDNUNG", "RAUM_LONG_ORDNUNG", "RAUM_RISK")
_parts = patched.split(_RAUM)
assert len(_parts) == len(_RAUM_TAGS) + 1, (len(_parts), len(_RAUM_TAGS) + 1)
patched = _parts[0]
for _tag, _rest in zip(_RAUM_TAGS, _parts[1:]):
    patched += (f'_T.append((k, richtung, "{_tag}", int(kd.kid))); '
                f'{_RAUM}' + _rest)
assert patched.count(_RAUM) == len(_RAUM_TAGS)
patched = rep(
    patched,
    '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
    '                continue',
    '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
    '                _T.append((k, richtung, "DEDUP_ENTRY", int(kd.kid)))\n'
    '                continue')
patched = rep(
    patched,
    '            getradete_entry_bars.add(entry_bar)',
    '            _T.append((k, richtung, "TRADE", int(kd.kid)))\n'
    '            getradete_entry_bars.add(entry_bar)')
patched = rep(
    patched,
    '                getradete_entry_bars.add(_eb_g4)',
    '                _T.append((_k_g4, "LONG", "TRADE_G4", '
    'int(_spec_g4.boden_kid)))\n'
    '                getradete_entry_bars.add(_eb_g4)')
patched = rep(
    patched,
    '        if not pool:\n            return None\n        pool.sort(',
    '        if not pool:\n'
    '            _T.append((k, richtung, "POOL_LEER", -1))\n'
    '            return None\n        pool.sort(')
patched = rep(
    patched,
    '                    return None                 '
    '# lebende Wand nicht erreicht',
    '                    _T.append((k, richtung, "WAND_UNERREICHT", '
    'int(e.kid)))\n'
    '                    return None                 '
    '# lebende Wand nicht erreicht')
patched = rep(
    patched,
    '                return None                     '
    '# Ueberdehnung, kein Reclaim',
    '                _T.append((k, richtung, "UEBERDEHNUNG", int(e.kid)))\n'
    '                return None                     '
    '# Ueberdehnung, kein Reclaim')
patched = rep(
    patched,
    '            return e\n        return None',
    '            _T.append((k, richtung, "INNEN_TC_OK", int(e.kid)))\n'
    '            return e\n        return None')
patched = rep(
    patched,
    '            if stufe_n == 0:\n                continue',
    '            if stufe_n == 0:\n'
    '                _T.append((k, richtung, "STUFE0_KEIN_RECLAIM", '
    'int(kd.kid)))\n'
    '                continue')
# WAND_POS0-Sonde (Q1-Rueckgabe) zusaetzlich, damit pos==0 sichtbar wird.
patched = rep(
    patched,
    '            if pos == 0:\n                return e',
    '            if pos == 0:\n'
    '                _T.append((k, richtung, "WAND_POS0", int(e.kid)))\n'
    '                return e')
print("Alle 18 Sonden eingenaeht (fail-loud geprueft).")


# ---------------- ZP-5-Injektion (Varianten B und D) ---------------------
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


VARIANTEN = (("ZP-4 (Referenz)", None),
             ("B (+lit)", (True, False, False)),
             ("D (+sweep)", (True, True, True)))

spec = importlib.util.spec_from_loader("ke_e34n10", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n10"] = eng
exec(compile(src_datei, str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX_END = int(scan["box_end_bar"])
scan["box_end_bar"] = scan["n"]
ts = scan["d"]["ts"]
op = scan["d"]["open"].to_numpy(dtype=float)
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)
cl = scan["d"]["close"].to_numpy(dtype=float)

SEG = ADAPTER_V019.segmente
P9_ = SEG[0]
A1_, A2_ = SEG[1], SEG[2]
AUTO_A, AUTO_B = A1_.start_bar, A2_.end_bar
P9A, P9B = P9_.start_bar, P9_.end_bar
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
    _ns["_T"] = []
    _ns["_P"] = []
    _ns["_hook"] = hook
    _HOOK[0] = hook
    exec(compile(quelle, "<se_e34n10>", "exec"), _ns)
    eng._se_trades = _ns["_se_trades"]
    try:
        _sc = copy.deepcopy(scan)
        res = eng._se_trades(_sc, cfg)
    finally:
        eng._se_trades = ORIG
    return res[0], _ns["_T"], _ns["_P"], _sc


def _zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m. %H:%M")


def _kante(sc, kid: int):
    return next((e for e in list(sc["edges"]) + list(sc["seeds"])
                 if int(e.kid) == kid), None)


print("=" * 122)
print("E-34n/10  RETEST BAR 1172 (K82, A1-Boden) — read-only")
print("=" * 122)
print(f"Engine   {hashlib.sha256(ENG.read_bytes()).hexdigest()[:24]}...")
print(f"Renderer {hashlib.sha256(REN.read_bytes()).hexdigest()[:24]}...")
print(f"box_end={BOX_END} | P9 {P9A}..{P9B} (Boden K{P9_.boden.kid}, "
      f"Literal {P9_.boden_deklariert_literal}) | "
      f"A1 {A1_.start_bar}..{A1_.end_bar} (Boden K{A1_.boden.kid}, Decke "
      f"K{A1_.decke.kid}) | A2 {A2_.start_bar}..{A2_.end_bar} "
      f"(Boden K{A2_.boden.kid}, Decke K{A2_.decke.kid})")

_res = {}
for _name, _flags in VARIANTEN:
    _q = patched if _flags is None else patched.replace(
        _ANK, _ANK + "\n" + _zp5(*_flags))
    _tr, _T, _P, _sc = _lauf(_q, ADAPTER_V019)
    _res[_name] = (_tr, _T, _P, _sc)
    print(f"  {_name:<16} {len(_tr):>3} Trades / {sum(t.r for t in _tr):+.6f} R")

print("\n" + "=" * 122)
print("1) IST 1172 DIESELBE KANTE? — Segment-Zuordnung und K82-Zustand")
print("=" * 122)
for _name in _res:
    _tr, _T, _P, _sc = _res[_name]
    _k82 = _kante(_sc, 82)
    _k62 = _kante(_sc, 62)
    print(f"\n  [{_name}]")
    print(f"    Segmente A1 {A1_.start_bar}..{A1_.end_bar} / "
          f"A2 {A2_.start_bar}..{A2_.end_bar}  ->  "
          f"1072-1075 in A1: {A1_.start_bar <= 1075 <= A1_.end_bar} | "
          f"1172 in A1: {A1_.start_bar <= 1172 <= A1_.end_bar} | "
          f"1173 (Entry) in A1: {A1_.start_bar <= 1173 <= A1_.end_bar}")
    print(f"    K82.wicks        = {[b for b, _ in _k82.wicks]}")
    print(f"    K82.schlaf       = {_k82.schlaf_windows}")
    print(f"    K82.basis(stat)  = {float(_k82.basis):.4f} | "
          f"ist_prim_anker={_k82.ist_prim_anker} | "
          f"erster_pivot_bar={_k82.erster_pivot_bar}")
    print(f"    {'bar':>5} {'BKZ':>12} {'O':>8} {'H':>8} {'L':>8} {'C':>8} | "
          f"{'K82 basis_bei':>13} {'dist%':>8} {'tc':>2} {'aktiv':>5} | "
          f"{'K62 basis':>10} {'dist%':>8} {'tc':>2}")
    for _k in (1072, 1073, 1074, 1075, 1172, 1173, 1175):
        _b82 = float(_k82.basis_bei(_k))
        _d82 = (_b82 - float(lo[_k])) / _b82 * 100.0
        _b62 = float(_k62.basis_bei(_k))
        _d62 = (_b62 - float(lo[_k])) / _b62 * 100.0
        print(f"    {_k:>5} {_zeit(_k):>12} {op[_k]:>8.4f} {hi[_k]:>8.4f} "
              f"{lo[_k]:>8.4f} {cl[_k]:>8.4f} | {_b82:>13.4f} {_d82:>+8.4f} "
              f"{_k82.touch_conf(_k):>2} "
              f"{str(_k82.ist_aktiv_bei(_k)):>5} | {_b62:>10.4f} {_d62:>+8.4f} "
              f"{_k62.touch_conf(_k):>2}")

print("\n" + "=" * 122)
print("2) TRADE-BILANZ um 1075 und 1172  (Trace-Ereignisse je Bar)")
print("=" * 122)
for _name in _res:
    _tr, _T, _P, _sc = _res[_name]
    print(f"\n  [{_name}]")
    for _k in (1072, 1073, 1074, 1075, 1076, 1170, 1171, 1172, 1173):
        _ev = [f"{e}({kk})" for (_k2, _r, e, kk) in _T if _k2 == _k]
        _po = " | ".join(
            f"{r}: " + ", ".join(f"K{kid}{'' if ex else '!'}={d:+.4f}%"
                                 f"/tc{tc}{'/' if ak else '/SCHLAF'}"
                                 for (kid, d, tc, ex, ak) in pool)
            for (k2, r, fr, pool) in _P if k2 == _k)
        print(f"    {_k:>5} {_zeit(_k):>12} L{lo[_k]:.4f} | "
              f"{' '.join(_ev) if _ev else '(kein Kandidat)'}")
        if _po:
            print(f"          POOL {_po}")
    print("    Trades: " + ", ".join(
        f"K{int(t.kid)}@{t.bar}(e{t.entry_bar} {t.r:+.6f})"
        for t in sorted(_tr, key=lambda x: x.bar)))

print("\n" + "=" * 122)
print("3) WARUM NUR 1075? — Durchstich-Audit K82 (b0 = basis_bei(1033))")
print("=" * 122)
_tr, _T, _P, _sc = _res["D (+sweep)"]
_k82d = _kante(_sc, 82)
_b0 = float(_k82d.basis_bei(A1_.start_bar))
print(f"    b0 = basis_bei({A1_.start_bar}) = {_b0:.4f} | "
      f"touch_band_pct = {cfg.touch_band_pct}")
print(f"    {'bar':>5} {'L':>8} {'d(b0) %':>9} {'> Band?':>8} {'<=0.80?':>8} "
      f"{'Docht D':>8}")
for _k in range(1070, 1080):
    _d = (_b0 - float(lo[_k])) / _b0 * 100.0
    _in = any(b == _k for b, _ in _k82d.wicks)
    print(f"    {_k:>5} {lo[_k]:>8.4f} {_d:>+9.4f} "
          f"{str(_d > cfg.touch_band_pct):>8} {str(_d <= 0.80):>8} "
          f"{str(_in):>8}")
print("    -> Nur 1075 durchstoesst das Band und liegt zugleich <= 0.80 %.")

print("\n" + "=" * 122)
print("4) OBEN-SYMmetrie: bleibt K67@882 durch das P9-Gate inaktiv?")
print("=" * 122)
for _name in _res:
    _tr, _T, _P, _sc = _res[_name]
    _k67 = _kante(_sc, 67)
    _k77 = _kante(_sc, 77)
    print(f"  [{_name:<16}] K67.wicks={[b for b, _ in _k67.wicks]} | "
          f"K77.wicks={[b for b, _ in _k77.wicks]} | "
          f"Trades in P9 (848..1020): "
          f"{sum(1 for t in _tr if P9A <= t.bar <= P9B)} / "
          f"{sum(t.r for t in _tr if P9A <= t.bar <= P9B):+.6f} R")

print("\n" + "=" * 122)
print("5) SOLLWERTE")
print("=" * 122)
print("  ZP-4/V019: 23 / +82.614385 | V018: 17 / +65.835576 | "
      "B: 23 / +86.640859 | D: 24 / +88.116626")
print("\nENDE E-34n/10")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
