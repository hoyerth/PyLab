# -*- coding: utf-8 -*-
"""E-34n/11 — Spaltmass-Audit zu ZP-5(D): read-only, KEIN Schreibzugriff.

Frage (Anwender, Schritt 1): Wie stabil ist die Klassifikation der Bars
1072-1074 als "Band-Rauschen" gegenueber 1075 als "echter Durchstich"?

Geprueft werden DREI Kandidaten fuer die eingefrorene Wandbasis `_b0`:
  (a) basis_bei(seg.start_bar)  = 67.5350  (so in E-34n/9 implementiert)
  (b) statische .basis          = 67.5455  (Provenienz-Wert der Kante)
  (c) basis_bei(1072)           = 67.5530  (laufendes Extremum am Sweep-Tag)

Zusaetzlich: empirische Falsifikation -- ZP-5(D) mit (b) und (c) als `_b0`.
Erwartung bei Kollaps: 23 Trades / +86.640859 R (= Variante B), K62@1075 weg.
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
OUT = ROOT / "test" / "_tmp_e34n11_out.txt"
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

ren_txt = REN.read_text(encoding="utf-8")
RENNS: dict = {}
for _n in ast.parse(ren_txt).body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id.startswith("A_"):
        exec(compile(ast.get_source_segment(ren_txt, _n), "<a_>", "exec"),  # noqa: S102
             RENNS)
    if isinstance(_n, ast.FunctionDef) and _n.name == "_wende_zielzonen_patches_v019":
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

_ANK = ('    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\n'
        '        "OBEN": [e for e in alle if e.seite == "OBEN"],\n'
        '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}')
assert patched.count(_ANK) == 1

_B0_START = "                _b0 = float(_ek.basis_bei(_s0))"


def _zp5(b0_zeile: str, sweep_only: bool = True) -> str:
    """ZP-5(D) als Quelltext; `b0_zeile` legt die eingefrorene Basis fest."""
    g_sw = ('                    if _dkl <= cfg.touch_band_pct:\n'
            '                        continue\n') if sweep_only else ''
    return ("    # --- ZP-5(D): Kantenlaeufer-Durchstich auf Segmentwaenden\n"
            "    _kl_hook = globals().get(\"_hook\")\n"
            "    if _kl_hook is not None "
            "and len(getattr(_kl_hook, \"segmente\", ())) > 1:\n"
            "        _kl_idx = {int(e.kid): e for e in alle}\n"
            "        for _seg in _kl_hook.segmente:\n"
            "            if _seg.boden_deklariert_literal is not None:\n"
            "                continue\n"
            "            for _ki, _kl_seite in ((_seg.boden, \"UNTEN\"),\n"
            "                                   (_seg.decke, \"OBEN\")):\n"
            "                _ek = _kl_idx.get(int(_ki.kid))\n"
            "                if _ek is None:\n"
            "                    continue\n"
            "                _s0, _s1 = int(_seg.start_bar), int(_seg.end_bar)\n"
            + b0_zeile + "\n"
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


B0_QUELLEN = (
    ("(a) basis_bei(seg.start_bar)", _B0_START),
    ("(b) statische .basis", "                _b0 = float(_ek.basis)"),
    ("(c) basis_bei(1072)", "                _b0 = float(_ek.basis_bei(1072))"),
)

spec = importlib.util.spec_from_loader("ke_e34n11", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n11"] = eng
exec(compile(src_datei, str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
BOX_END = int(scan["box_end_bar"])
scan["box_end_bar"] = scan["n"]
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)

SEG = ADAPTER_V019.segmente
A1_ = SEG[1]
A2_ = SEG[2]
AUTO_A, AUTO_B = A1_.start_bar, A2_.end_bar
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
    exec(compile(quelle, "<se_e34n11>", "exec"), _ns)
    eng._se_trades = _ns["_se_trades"]
    try:
        _sc = copy.deepcopy(scan)
        res = eng._se_trades(_sc, cfg)
    finally:
        eng._se_trades = ORIG
    return res[0], _sc


def _kante(sc, kid: int):
    return next((e for e in list(sc["edges"]) + list(sc["seeds"])
                 if int(e.kid) == kid), None)


def _niveauwechsel(sc) -> int:
    """Sichtbare Niveauwechsel (maskiert, pivot_bar + 2 <= k) wie im Renderer."""
    _ges = 0
    for _e in list(sc["edges"]) + list(sc["seeds"]):
        _prev = None
        for _k in range(sc["n"]):
            if not any(_b + 2 <= _k for _b, _ in _e.wicks):
                continue
            _v = float(_e.basis_bei(_k))
            if _prev is not None and abs(_v - _prev) > 1e-12:
                _ges += 1
            _prev = _v
    return _ges


_BASIS, _scB = _lauf(patched, ADAPTER_V019)
_k82b = _kante(_scB, 82)
B0_START = float(_k82b.basis_bei(A1_.start_bar))
B0_STAT = float(_k82b.basis)
B0_1072 = float(_k82b.basis_bei(1072))

print("=" * 122)
print("E-34n/11  SPALT-MASS-AUDIT ZP-5(D) — read-only")
print("=" * 122)
print(f"ZP-4-Referenz : {len(_BASIS)} / {sum(t.r for t in _BASIS):+.6f} R "
      f"(Soll 23 / +82.614385)")
print(f"A1 {A1_.start_bar}..{A1_.end_bar} | K82 | Band "
      f"touch_band_pct={cfg.touch_band_pct} | Ueberdehnung "
      f"max_sweep_ueberdehnung_pct={cfg.max_sweep_ueberdehnung_pct}")
print(f"b0-Kandidaten : (a) {B0_START:.4f}  (b) {B0_STAT:.4f}  (c) {B0_1072:.4f}")
print(f"NIVEAUWECHSEL : ZP-4 {_niveauwechsel(_scB)}  "
      f"(arretiertes Soll 66)")

print("\n" + "=" * 122)
print("1) KLASSIFIKATION DER DURCHSTICHE je b0-Kandidat (Docht <=> Band < d <= 0.80)")
print("=" * 122)
print(f"    {'b0':>10} {'Kennung':<26} " + " ".join(
    f"{f'bar{b}':>10}" for b in (1072, 1073, 1074, 1075)))
for _lab, _b0 in (("(a) basis_bei(1033)", B0_START),
                  ("(b) statische .basis", B0_STAT),
                  ("(c) basis_bei(1072)", B0_1072)):
    _zelle = []
    for _b in (1072, 1073, 1074, 1075):
        _d = (_b0 - float(lo[_b])) / _b0 * 100.0
        _mark = "DOCHT" if cfg.touch_band_pct < _d <= 0.80 else "rausch"
        _zelle.append(f"{_d:>6.4f}{_mark:>4}")
    print(f"    {_b0:>10.4f} {_lab:<26} " + " ".join(_zelle))

print("\n" + "=" * 122)
print("2) SCHWELLEN b0*, ab denen 1074 bzw. 1073 zum Docht wird")
print("=" * 122)
for _b in (1074, 1073, 1072):
    _lo_b = float(lo[_b])
    _b0_stern = _lo_b / (1.0 - cfg.touch_band_pct / 100.0)
    print(f"    bar {_b}: Low {_lo_b:.4f} -> Docht ab b0 > {_b0_stern:.5f} "
          f"(Reserve ab (a): {_b0_stern - B0_START:+.5f} USD "
          f"= {(_b0_stern - B0_START) / B0_START * 100.0:+.5f} %)")
print("    Wirkung: 1074 allein kippt D NICHT (1074+2 = 1076 > 1075).")
print("             Erst ab b0 > 67.54310 (Docht 1073, 1073+2 = 1075 <= 1075)")
print("             steigt touch_conf(1075) auf 3 -> K82 wird Kandidat ->")
print("             Kollaps auf Variante B.")
print(f"    statische .basis {B0_STAT:.4f} liegt bereits "
      f"{B0_STAT - B0_START:+.4f} USD ueber (a).")

print("\n" + "=" * 122)
print("3) EMPIRISCHE FALSIFIKATION: ZP-5(D) mit fremder b0")
print("=" * 122)
_base_keys = {(t.bar, t.kid) for t in _BASIS}
for _lab, _zeile in (("(a) Spec (Referenz)", _B0_START),
                     ("(b) statische .basis", "                _b0 = float(_ek.basis)"),
                     ("(c) basis_bei(1072)", "                _b0 = float(_ek.basis_bei(1072))")):
    _tr, _sc = _lauf(patched.replace(_ANK, _ANK + "\n" + _zp5(_zeile)),
                     ADAPTER_V019)
    _k82 = _kante(_sc, 82)
    _weg = [t for t in _BASIS if (t.bar, t.kid) not in {(x.bar, x.kid)
                                                       for x in _tr}]
    _neu = [t for t in _tr if (t.bar, t.kid) not in _base_keys]
    print(f"\n    [{_lab}]  b0={float(_k82.basis_bei(A1_.start_bar)):.4f}"
          f" | K82-Dochte={[b for b, _ in _k82.wicks]}"
          f" | tc(1075)={_k82.touch_conf(1075)}")
    print(f"      Ergebnis: {len(_tr)} Trades / {sum(t.r for t in _tr):+.6f} R"
          f"  ->  {'KOLLAPS (Variante B)' if len(_tr) == 23 else 'additiv (Variante D)'}")
    print(f"      NIVEAUWECHSEL={_niveauwechsel(_sc)}  (Soll 66)")
    for t in _weg:
        print(f"      WEG bar {t.bar} K{int(t.kid)} r={t.r:+.6f}")
    for t in _neu:
        print(f"      NEU bar {t.bar} K{int(t.kid)} e_bar={t.entry_bar} "
              f"r={t.r:+.6f}")

print("\n" + "=" * 122)
print("4) SOLLWERTE")
print("=" * 122)
print("    ZP-4   : 23 / +82.614385")
print("    D (a)  : 24 / +88.116626   <- arretierter Standard")
print("    B      : 23 / +86.640859")
print("    V018   : 17 / +65.835576")
print("\nENDE E-34n/11")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
