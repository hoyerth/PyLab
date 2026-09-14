# -*- coding: utf-8 -*-
"""Stufe 4 / Phase 1: TROCKENLAUF (read-only, keine Dateimodifikation).

Zwei Messungen:
  A) Schenkel-Dekomposition des kausalen 23er-Satzes (r1/r2/grund1/grund2)
     -> Kandidaten fuer R_realisiert (b) und R_untergrenze (a).
  B) Kanten-Ereignis-Regel als In-Memory-Variante: die zeitbasierte
     12-Bar-Sperre wird durch "Re-Entry nur nach frischem bestaetigtem
     Touch/Sweep" ersetzt. Welche August-Trades fallen weg, wie reagiert H1?

Es wird NICHTS geschrieben; die Engine-Datei bleibt unberuehrt.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019_KAUSAL  # noqa: E402


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
        "h_stufe4", ROOT / "test" / "_chk_v019_kausal_vergleich.py")
    H = importlib.util.module_from_spec(_spec)
    sys.modules["h_stufe4"] = H
    _spec.loader.exec_module(H)  # type: ignore[union-attr]
finally:
    sys.stdout = _stdout

cfg = H.cfg
scan = H.scan

# ============================================================ A) Schenkel
_ORIG = H.engine._c_loese_trade
REC: List[Dict] = []


def _rec(*a, **k):
    res = _ORIG(*a, **k)
    REC.append({
        "e_bar": int(a[3]), "richtung": a[5],
        "rm": float(res.r_mult), "r1": float(res.r1), "r2": float(res.r2),
        "g1": res.grund1, "g2": res.grund2,
        "x1": int(res.exit1_bar), "x2": int(res.exit2_bar),
    })
    return res


H.ns["_c_loese_trade"] = _rec
D_SET, D_STATS = H._lauf(ADAPTER_V019_KAUSAL)
H.ns["_c_loese_trade"] = _ORIG

_n = len(D_SET)
_r = sum(float(t.r) for t in D_SET)
print("=" * 100)
print("STUFE 4 / PHASE 1 -- TROCKENLAUF (read-only)")
print("=" * 100)
print(f"\nKausaler Satz: {_n} Trades / {_r:+.6f} R")

# Records den Setups zuordnen (Schluessel: entry_bar, Richtung, Exits, rm)
_idx: Dict[Tuple, List[Dict]] = {}
for rec in REC:
    _idx.setdefault((rec["e_bar"], rec["richtung"]), []).append(rec)

LEGS: List[Dict] = []
_missing = 0
for t in D_SET:
    _cand = _idx.get((int(t.entry_bar), t.richtung), [])
    _hit = [c for c in _cand
            if c["x1"] == int(t.exit1_bar) and c["x2"] == int(t.exit2_bar)
            and abs(c["rm"] - float(t.r)) < 1e-9]
    if not _hit:
        _missing += 1
        continue
    LEGS.append({"bar": int(t.bar), "entry_bar": int(t.entry_bar),
                 "kid": int(t.kid), "richtung": t.richtung,
                 "r": float(t.r), **{k: _hit[0][k] for k in
                                     ("r1", "r2", "g1", "g2", "x1", "x2")}})

print(f"\nZuordnung Schenkel: {len(LEGS)}/{_n} "
      f"({_missing} ohne Treffer)")


def _fmt(v: float) -> str:
    return f"{v:+.6f}"


# --- Kandidaten-Metriken --------------------------------------------------
W = cfg.tp1_anteil_pct / 100.0
print(f"\nGewichte: w1 = {W:.4f} (tp1_anteil_pct = {cfg.tp1_anteil_pct}), "
      f"w2 = {1.0 - W:.4f}")

_brutto = sum(x["r"] for x in LEGS)
_b = sum((0.0 if x["g1"] == "ENDE" else W * x["r1"])
         + (0.0 if x["g2"] == "ENDE" else (1.0 - W) * x["r2"])
         for x in LEGS)
_a_set = [x for x in LEGS if x["g1"] != "ENDE" and x["g2"] != "ENDE"]
_a = sum(W * x["r1"] + (1.0 - W) * x["r2"] for x in _a_set)

print(f"\nKandidaten:")
print(f"  R_brutto (heutiger Sollwert)      : {_fmt(_brutto)}")
print(f"  R_realisiert (b) [ENDE-Schenkel=0]: {_fmt(_b)}   "
      f"({len(LEGS)} Trades, {sum(1 for x in LEGS if 'ENDE' in (x['g1'], x['g2']))} mit ENDE)")
print(f"  R_untergrenze (a) [ENDE-Trades raus]: {_fmt(_a)}   "
      f"({len(_a_set)} Trades)")
print(f"  Vormerkung E-34n/14: (b) +78.216484  (a) +78.127525")

# --- Alle Trades mit ENDE-Schenkel ---------------------------------------
print(f"\nTrades mit ENDE-Schenkel:")
_hdr = (f"  {'Bar':>5} {'Entry':>6} {'Kante':>6} {'Richt':>6} "
        f"{'grund1':>7} {'r1':>10} {'grund2':>7} {'r2':>10} {'r':>11}")
print(_hdr)
for x in sorted([y for y in LEGS if "ENDE" in (y["g1"], y["g2"])],
                key=lambda z: z["bar"]):
    print(f"  {x['bar']:>5} {x['entry_bar']:>6} {'K%d' % x['kid']:>6} "
          f"{x['richtung']:>6} {x['g1']:>7} {x['r1']:>+10.5f} "
          f"{x['g2']:>7} {x['r2']:>+10.5f} {x['r']:>+11.5f}")
print(f"\n  Rand-Trades (E-34n/14: 1075, 1172, 1272, 1280) explizit:")
for _bar in (1075, 1172, 1272, 1280):
    _m = [x for x in LEGS if x["bar"] == _bar]
    print(f"    Bar {_bar}: "
          + ("nicht im kausalen Satz" if not _m else
             ", ".join(f"K{x['kid']} {x['richtung']} "
                       f"({x['g1']} {x['r1']:+.5f} | {x['g2']} {x['r2']:+.5f})"
                       for x in _m)))

# ============================================================ B) Kanten-Regel
print("\n" + "=" * 100)
print("B) KANTEN-EREIGNIS-REGEL (In-Memory-Variante, zeitbasierte 12-Bar-Sperre -> frischer Touch)")
print("=" * 100)

# Ist-Code der Sperre (Zeilen ~2618-2629) durch Frische-Regel ersetzen:
_ALT = (
    '            _vor_zeit = letzter_trade.get(kd.kid)\n'
    '            if (_vor_zeit is not None\n'
    '                    and entry_bar - _vor_zeit.entry_bar\n'
    '                    < cfg.retest_zyklus_bars):\n'
    '                stats["zyklus_blockiert"] += 1\n'
    '                zyklus_liste.append(\n'
    '                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "\n'
    '                    f"basis={kd.basis_bei(k):.3f} -> ZYKLUS-SPERRE "\n'
    '                    f"(letzter Sweep Bar {kd.letzter_sweep_bar}, "\n'
    '                    f"Abstand {k - kd.letzter_sweep_bar} "\n'
    '                    f"< {cfg.retest_zyklus_bars})")\n'
    '                continue\n'
)
_NEU = (
    '            _vor_ereignis = letzter_trade.get(kd.kid)\n'
    '            if _vor_ereignis is not None:\n'
    '                _neu_touch = [b for b, _p in kd.wicks\n'
    '                              if b + 2 <= k and b > _vor_ereignis.bar]\n'
    '                if not _neu_touch:\n'
    '                    stats["zyklus_blockiert"] += 1\n'
    '                    continue\n'
)
assert H.patched_src.count(_ALT) == 1, H.patched_src.count(_ALT)
_src_neu = H.patched_src.replace(_ALT, _NEU, 1)


def _lauf_variante(quelle: str, hook):
    H.ns["_hook"] = hook
    exec(compile(quelle, "<variante>", "exec"), H.ns)  # noqa: S102
    setups, st = H.ns["_se_trades"](H.copy.deepcopy(scan), cfg)
    return list(setups), dict(st)


E_SET, E_STATS = _lauf_variante(_src_neu, ADAPTER_V019_KAUSAL)
_en, _er = len(E_SET), sum(float(t.r) for t in E_SET)
_h1 = [t for t in E_SET if int(t.entry_bar) < 644]
_h2 = [t for t in E_SET if int(t.entry_bar) >= 644]
print(f"\n{'Lauf':<34}{'n':>4}{'R':>14}{'H1':>16}{'H2':>16}")
print(f"{'Ist (12-Bar-Sperre)':<34}{_n:>4}{_r:>+14.6f}"
      f"{len([t for t in D_SET if int(t.entry_bar) < 644]):>8d}"
      f"{sum(float(t.r) for t in D_SET if int(t.entry_bar) < 644):>+16.6f}"
      f"{len([t for t in D_SET if int(t.entry_bar) >= 644]):>8d}")
print(f"{'Variante (frischer Touch)':<34}{_en:>4}{_er:>+14.6f}"
      f"{len(_h1):>8d}{sum(float(t.r) for t in _h1):>+16.6f}"
      f"{len(_h2):>8d}")

_kD = {H._key(t) for t in D_SET}
_kE = {H._key(t) for t in E_SET}
print(f"\nEntfallen ggue. Ist:")
for t in sorted([x for x in D_SET if H._key(x) not in _kE],
                key=lambda z: int(z.bar)):
    print(f"  bar {int(t.bar):>5} entry {int(t.entry_bar):>5} {t.richtung:<6} "
          f"K{int(t.kid):<4} R {float(t.r):>+10.5f}")
print(f"\nNeu ggue. Ist:")
for t in sorted([x for x in E_SET if H._key(x) not in _kD],
                key=lambda z: int(z.bar)):
    print(f"  bar {int(t.bar):>5} entry {int(t.entry_bar):>5} {t.richtung:<6} "
          f"K{int(t.kid):<4} R {float(t.r):>+10.5f}")

# ============================================================ C) Concurrency
print("\n" + "=" * 100)
print("C) CONCURRENCY / KLUMPENRISIKO (offene Positionen je Richtung)")
print("=" * 100)


def _concurrency(trades, label: str) -> None:
    """Max. gleichzeitig offene Positionen je Richtung (Haltedauer inkl.)."""
    print(f"\n  [{label}]")
    for _richt in ("SHORT", "LONG"):
        _ints = []
        for t in trades:
            if t.richtung != _richt:
                continue
            _start = int(t.entry_bar)
            _ende = max(int(getattr(t, "exit1_bar", -1)),
                        int(getattr(t, "exit2_bar", -1)))
            if _ende < _start:
                _ende = _start
            _ints.append((_start, _ende, int(t.bar), int(t.kid)))
        _maxc = 0
        _wo = None
        for _b in range(0, 1289):
            _off = sum(1 for x in _ints if x[0] <= _b <= x[1])
            if _off > _maxc:
                _maxc = _off
                _wo = _b
        print(f"    {_richt:<6} Trades {len(_ints):>2} | max. gleichzeitig "
              f"offen = {_maxc}"
              + (f" (Bar {_wo})" if _wo is not None else ""))
        for x in sorted(_ints):
            _d = sum(1 for y in _ints if not (y[1] < x[0] or y[0] > x[1]))
            if _d >= 3:
                print(f"        Bar {x[2]:>5} K{x[3]:<4} entry {x[0]:>5} "
                      f"exit {x[1]:>5} -> {_d} gleichzeitig")


_concurrency(D_SET, "Ist (23, kausal)")
_concurrency(E_SET, "Variante (frischer Touch)")

print("\nTROCKENLAUF ENDE (keine Datei geschrieben).")
