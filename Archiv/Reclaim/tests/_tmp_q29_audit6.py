# -*- coding: utf-8 -*-
"""READ-ONLY: Klaerung 991 vs. 1002 + Papier-Rechnung des Bar-1002-Setups.

Fragestellungen:
  Q-A  Wird Bar 1002 frei, wenn Bar 991 unterdrueckt wird?
  Q-B  Welchen Verlauf/R hat das Bar-1002-Setup bei Entry an Bar 1003?
  Q-C  Warum entsteht 1002 im Q29-aus-Lauf NICHT (welches Gate greift)?
  Q-D  Toetet die Bindung an 'pivot + 2' wirklich den 991-Artefakt-Trade?

Es werden ausschliesslich In-Memory-Quelltextvarianten ausgefuehrt; auf der
Platte wird NICHTS geaendert.
"""
from __future__ import annotations

import copy
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

sys.argv = ["tmp_q29_audit6"]
voll = REN.read_text(encoding="utf-8")
_i = voll.index("import matplotlib")
mod = {"__name__": "q29a6", "__file__": str(REN)}
sys.modules[mod["__name__"]] = type(sys)("q29a6")
exec(compile(voll[:voll.rindex("\n", 0, _i) + 1], str(REN), "exec"), mod)

engine, ns, cfg, scan = mod["engine"], mod["ns"], mod["cfg"], mod["scan"]
ADAPTER, box_end = mod["DEFAULT_ADAPTER"], mod["box_end"]
V1_basis = mod["V1_basis"]
base_src = mod["patched_src"]

d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
n = scan["n"]

PHASEN = [(620, 673), (715, 792), (802, 840), (848, 1020), (1030, 1075),
          (1082, 1134), (1171, 1272)]
PHSTART = []
for k in range(n):
    s = 0
    for a, _b in PHASEN:
        if a <= k:
            s = a
    PHSTART.append(s)


def _lauf(src: str, tr: list | None = None):
    """Ein Engine-Lauf auf In-Memory-Quelltext; Platte bleibt unberuehrt."""
    _ns = dict(engine.__dict__)
    _ns["_hook"] = ADAPTER
    _ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
    _ns["_PHSTART"] = PHSTART
    if tr is not None:
        _ns["_TR"] = tr
    exec(compile(src, "<v>", "exec"), _ns)
    orig = engine._se_trades
    engine._se_trades = _ns["_se_trades"]
    try:
        return engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = orig


def zeig(tag, V, st=None):
    h2 = [t for t in V if t.entry_bar >= box_end]
    print(f"  {tag:28s}: {len(V):2d} / {sum(t.r for t in V):+10.6f} R | "
          f"H2 {len(h2):2d}/{sum(t.r for t in h2):+10.6f} R")
    _s = {t.bar: t for t in V}
    print("      " + " | ".join(
        f"{b}: " + (f"K{_s[b].kid} {_s[b].r:+.4f}" if b in _s else "-")
        for b in (991, 1002)))
    if st is not None:
        print(f"      Gates: blocker {st['blocker']} quartil "
              f"{st['quartil_blockiert']} zyklus {st['zyklus_blockiert']} "
              f"kein_raum {st['kein_raum']} f3 {st['f3']}")
    return _s


print("=== Q-D) KANDIDAT-/KENNZAHLEN 988..1006 ===")
print(f"  touch_band {cfg.touch_band_pct} | min_touches_handelbar "
      f"{cfg.min_touches_handelbar} | min_wall_alter_bars "
      f"{cfg.min_wall_alter_bars} | retest_zyklus {cfg.retest_zyklus_bars} | "
      f"sl_buffer {cfg.sl_buffer_usd} | tp1_anteil {cfg.tp1_anteil_pct}")
by_kid = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}
for kid in (77, 79, 60):
    e = by_kid[kid]
    print(f"  K{kid}: piv1 {e.erster_pivot_bar} geb {e.geburts_bar} "
          f"wicks {[(b, round(p, 3)) for b, p in e.wicks]}")
for k in (991, 992, 997, 1002):
    print(f"    bar {k:4d} | " + " | ".join(
        f"K{kid} b={by_kid[kid].basis_bei(k):.4f} "
        f"tc={by_kid[kid].touch_conf(k)}" for kid in (60, 77, 79)))

A_KD = "            kd = _kandidat(richtung, k, sweep_px)"
A_Q = "        return distanz <= cfg.quartil_distanz_pct"

zeig("V1_basis (Referenz)", V1_basis)

print("\n=== Q-A) 991 UNTERDRUECKT (In-Memory, nur dieser Bar) ===")
SKIP = A_KD + "\n            if k == 991:\n                continue"
V_skip, st_skip = _lauf(base_src.replace(A_KD, SKIP, 1))
_s = zeig("991 unterdrueckt", V_skip, st_skip)
if 1002 in _s:
    t = _s[1002]
    print(f"      -> 1002: K{t.kid} {t.stufe} entry_bar {t.entry_bar} "
          f"entry {t.entry:.4f} sl {t.sl:.4f} poc {t.poc:.4f} "
          f"tp2 {t.tp2:.4f} R {t.r:+.6f} resultat {t.resultat} "
          f"exit {t.exit1_bar}/{t.exit2_bar}")

print("\n=== Q-C) GATE-TRACE DES Q29-AUS-LAUFS (988..1012) ===")
TRACE = A_KD + "\n            _TR.append((k, richtung, dict(stats), len(setups)))"
src_trace = base_src.replace(A_Q, "        return True", 1).replace(
    A_KD, TRACE, 1)
_tr_list: list = []
V_off, st_off = _lauf(src_trace, _tr_list)
zeig("Q29 aus (Kontrolle)", V_off, st_off)
TR = _tr_list
for i in range(1, len(TR)):
    k0, r0, s0, n0 = TR[i - 1]
    k1, r1, s1, n1 = TR[i]
    if not (988 <= k0 <= 1012):
        continue
    diffs = {key: (s0[key], s1[key]) for key in s1 if s1[key] != s0[key]}
    if diffs or n1 != n0:
        txt = ", ".join(f"{a}:{b[0]}->{b[1]}" for a, b in diffs.items())
        print(f"    bar {k0:4d} {r0:5s}: {txt or '-'}"
              f"{'   TRADE' if n1 != n0 else ''}")
        if n1 != n0:
            t = V_off[n1 - 1]
            print(f"        -> K{t.kid}@{t.bar} entry_bar {t.entry_bar} "
                  f"stufe {t.stufe} R {t.r:+.6f}")

print("\n=== Q-D2) Q29-PRAEDIKAT UNTER VERSCHIEDENEN BODEN-MODELLEN ===")
DECK = 69.8700
BODEN_STARR = 68.4000


def _boden_roh(k: int) -> float:
    return min(lo[848:k + 1])


def _boden_pivot2(k: int) -> float:
    return min(lo[848:max(849, k - 1)]) if k >= 851 else float(lo[848])


for lab, fn in (("statisch 68.4000", lambda k: BODEN_STARR),
                ("laufend roh 848..k", _boden_roh),
                ("laufend pivot+2", _boden_pivot2)):
    for k in (991, 1002):
        f = float(fn(k))
        sp = DECK - f
        dd = (lo[k] - f) / sp * 100.0
        print(f"  {lab:22s} bar {k:4d}: boden {f:8.4f} spanne {sp:6.4f} "
              f"distanz {dd:+8.3f} % | einseitig(<=25) "
              f"{'ERLAUBT ' if dd <= 25 else 'GEBLOCKT'} | zweiseitig(0..25) "
              f"{'ERLAUBT ' if 0.0 <= dd <= 25 else 'GEBLOCKT'}")
