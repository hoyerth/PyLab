# -*- coding: utf-8 -*-
"""E-25 (read-only, offline) -- Regime-ZUSTANDSAUTOMAT: Pfad A / Pfad B pruefen.

Beantwortet die drei Leitfragen messgestuetzt:

Q1  Re-Entry-Schwelle: 2 konsekutive Closes zurueck unter das gebrochene Dach
    -- feuert das ueberhaupt, wann, und was haette es bewirkt?
Q2  Balance-Reife: >= 3 bestaetigte Pivots (touch_conf >= 3) im 480er-Fenster
    mit Spanne < 1.5 * ATR960 -- findet das die in §12 genannten neuen
    Konsolidierungen (K408/K409 -> K494/K493 -> K547/K484)?
Q3  Nebenprodukt: ATR960-Groessenordnung gegen typische Konsolidierungsbretten.

Zustandsautomat (Vorwaerts-Simulation, kausal, kein Lookahead):
    BALANCE            -> Reclaims beidseitig erlaubt
    EXPANSION_OBEN     -> 2 Closes > frozen_decke  -> SHORT verboten
    EXPANSION_UNTEN    -> 2 Closes < frozen_boden  -> LONG verboten
Rueckkehr Pfad A: 2 konsekutive Closes zurueck im alten Band.
Rueckkehr Pfad B: neue Balance deklariert (Kriterium Q2) -> Niveau neu einfrieren.
"""
from __future__ import annotations

import importlib.util
import pickle
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

OUT = ROOT / "test" / "_tmp_e25_state_machine_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg = eng.StraightEdgeHarnessKonfiguration()

scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
d = scan["d"]
op = d["open"].to_numpy(float)
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].to_numpy()
N = scan["n"]
SPLIT = 17692
alle = list(scan["edges"]) + list(scan["seeds"])
_ob = [e for e in alle if e.seite == "OBEN"]
_un = [e for e in alle if e.seite == "UNTEN"]

_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])


def atr(k: int, w: int) -> float:
    a, b = max(0, k - w + 1), k + 1
    return float(_tr[a:b].mean())


def exists(e, k: int) -> bool:
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


def pivots_im_fenster(k: int, lb: int = 480, min_touch: int = 3
                      ) -> List[Tuple[int, str, float]]:
    """Bestaetigte Pivots mit touch_conf >= min_touch im Lookback-Fenster."""
    a = max(0, k - lb)
    out = []
    for e in alle:
        pb = e.erster_pivot_bar
        if a <= pb <= k and exists(e, k) and e.touch_conf(k) >= min_touch:
            out.append((e.kid, e.seite, float(e.basis_bei(k))))
    return out


print("=" * 100)
print("E-25 REGIME-ZUSTANDSAUTOMAT -- Pfad A / Pfad B (S2, Split 17692)")
print("=" * 100)

# ---------------------------------------------------------------- ATR960
print("")
print("Q3  ATR-Groessenordnungen (USD)")
print("-" * 100)
for k in (SPLIT, SPLIT + 480, 18824, 20000, 21552):
    a14, a480, a960 = atr(k, 14), atr(k, 480), atr(k, 960)
    print(f"   k {k:>6} ({np.datetime64(ts[k], 'm')})  ATR14 {a14:>8.4f}  "
          f"ATR480 {a480:>8.4f}  ATR960 {a960:>8.4f}  "
          f"1.5*ATR960 {1.5 * a960:>8.4f}")
print("")
print("   >> Vergleich: Split-Konsolidierung K408/K409 = 1.3331 USD;")
print("      H2-Spanne 10.9950 USD; typische 96-Bar-Range ~0.7-0.9 USD.")

# ---------------------------------------------------- Q1: Pfad A (Re-Entry)
print("")
print("Q1  PFAD A -- Rueckkehr unter das gebrochene Dach K408 = 47.1221")
print("-" * 100)
DECKE0 = 47.1221
_BR = None
for k in range(SPLIT, N):
    if cl[k] > DECKE0 and cl[k - 1] > DECKE0:
        _BR = k
        break
print(f"   Erstbruch (2 Closes > {DECKE0}): Bar {_BR} "
      f"({np.datetime64(ts[_BR], 'm')})")
if _BR is not None:
    _re = None
    for k in range(_BR + 1, N):
        if cl[k] < DECKE0 and cl[k - 1] < DECKE0:
            _re = k
            break
    if _re is None:
        print(f"   Pfad A: KEINE 2 konsekutiven Closes < {DECKE0} bis n -- "
              f"Verbot bleibt bis Fensterende bestehen.")
    else:
        print(f"   Pfad A feuert bei Bar {_re} ({np.datetime64(ts[_re], 'm')})"
              f"  -> {_re - _BR} Bars nach dem Bruch")
    # Eindringtiefe-Variante: unter das Mittelband
    MID = (45.7890 + 47.1221) / 2.0
    _re2 = None
    for k in range(_BR + 1, N):
        if cl[k] < MID and cl[k - 1] < MID:
            _re2 = k
            break
    print(f"   Variante 'unter Mittelband {MID:.4f}': "
          + (f"Bar {_re2} ({np.datetime64(ts[_re2], 'm')})" if _re2
             else "KEINE Rueckkehr"))
    # Wie oft liegen 2 Closes zurueck im Band (Zaehlung)
    treffer = [k for k in range(_BR + 1, N)
               if cl[k] < DECKE0 and cl[k - 1] < DECKE0]
    print(f"   Bars mit 2 Closes < {DECKE0} nach dem Bruch: {len(treffer)}")
    if treffer:
        print(f"      erste 5: {treffer[:5]}   letzte 5: {treffer[-5:]}")

# ------------------------------------------- Q2: Pfad B (neue Balance)
print("")
print("Q2  PFAD B -- neue Balance: >= 3 Pivots (touch>=3), 480er-Fenster,")
print("     Spanne < 1.5 * ATR960")
print("-" * 100)
LB = 480
MINP = 3
_deklariert: List[Tuple[int, float, float, float, int]] = []
for k in range(SPLIT, N, 1):
    pv = pivots_im_fenster(k, LB, MINP)
    if len(pv) < MINP:
        continue
    seiten = {s for _k, s, _b in pv}
    if len(seiten) < 2:
        continue
    bs = [b for _k, _s, b in pv]
    spanne = max(bs) - min(bs)
    if spanne >= 1.5 * atr(k, 960):
        continue
    decke, boden = max(bs), min(bs)
    if not _deklariert or abs(_deklariert[-1][1] - decke) > 1e-9:
        _deklariert.append((k, decke, boden, spanne, len(pv)))

print(f"   Deklarationen (neue decke != alte): {len(_deklariert) - 1 if _deklariert else 0}")
print(f"{'Bar':>7}{'Datum':>18}{'Decke':>10}{'Boden':>10}{'Spanne':>9}"
      f"{'1.5*ATR960':>12}{'Pivots':>8}")
for k, dk, bk, sp, npv in _deklariert[:14]:
    print(f"{k:>7}{str(np.datetime64(ts[k], 'm')):>18}{dk:>10.4f}{bk:>10.4f}"
          f"{sp:>9.4f}{1.5 * atr(k, 960):>12.4f}{npv:>8}")
print("")
print("   Referenz §12 (unabhaengige Segmentaufloesung, Lookback 960):")
print("      17692 K408 47.1221 / K409 45.7890")
print("      18172 K436 48.6289 / K424 47.3247")
print("      18652 K494 52.4444 / K493 50.4759")
print("      19612 K429 48.3972 / K404 46.7691")
print("      20572 K547 54.2750 / K484 51.4427")
print("      21623 K561 56.4050 / K514 53.4280")

# --------------------------------------------- Q2b: Kalibrierungs-Schleife
print("")
print("Q2b KALIBRIERUNG des Balance-Kriteriums (Spanne < m * ATR960)")
print("-" * 100)
print(f"{'m':>5}{'Dekl':>6}   Deckes (erste 6, USD)")
for m in (1.5, 3.0, 5.0, 10.0, 20.0):
    dekl: List[Tuple[int, float, float]] = []
    for k in range(SPLIT, N):
        pv = pivots_im_fenster(k, LB, MINP)
        if len(pv) < MINP or len({s for _k, s, _b in pv}) < 2:
            continue
        bs = [b for _k, _s, b in pv]
        if max(bs) - min(bs) >= m * atr(k, 960):
            continue
        if not dekl or abs(dekl[-1][1] - max(bs)) > 1e-9:
            dekl.append((k, max(bs), min(bs)))
    ds = ", ".join(f"K@{k}:{d:.4f}/{b:.4f}" for k, d, b in dekl[:6])
    print(f"{m:>5.1f}{len(dekl):>6}   {ds}")

print("")
print("Q2c SENSITIVITAET: min_touch / min_pivots (m = 10.0)")
print("-" * 100)
for mt in (2, 3, 4):
    for mp in (2, 3, 4):
        dekl = []
        for k in range(SPLIT, N):
            pv = pivots_im_fenster(k, LB, mt)
            if len(pv) < mp or len({s for _k, s, _b in pv}) < 2:
                continue
            bs = [b for _k, _s, b in pv]
            if max(bs) - min(bs) >= 10.0 * atr(k, 960):
                continue
            if not dekl or abs(dekl[-1][1] - max(bs)) > 1e-9:
                dekl.append((k, max(bs), min(bs)))
        print(f"   min_touch {mt}  min_pivots {mp}  -> {len(dekl):>3} "
              f"Deklarationen  erste 3: "
              f"{[(k, round(d, 4)) for k, d, _b in dekl[:3]]}")

print("")
print("Q1b PFAD-A-VARIANTEN (wie oft ist die Rueckkehr-Bedingung erfuellt?)")
print("-" * 100)
_mid = (45.7890 + 47.1221) / 2.0
for lbl, cond in (
        ("2 Closes < Decke (Spec)", lambda k: cl[k] < DECKE0 and cl[k - 1] < DECKE0),
        ("3 Closes < Decke", lambda k: all(cl[k - i] < DECKE0 for i in range(3))),
        ("2 Closes < Mittelband", lambda k: cl[k] < _mid and cl[k - 1] < _mid),
        ("1 Close < Mittelband", lambda k: cl[k] < _mid),
        ("2 Closes < Boden 45.7890", lambda k: cl[k] < 45.7890 and cl[k - 1] < 45.7890)):
    hits = [k for k in range(_BR + 1, N) if cond(k)]
    erster = hits[0] if hits else None
    print(f"   {lbl:<26} Treffer {len(hits):>5}   erster "
          f"{erster if erster else '--'}"
          f"{' (' + str(np.datetime64(ts[erster], 'm')) + ')' if erster else ''}")

# ------------------------------------- Zustandsautomat + 54-Trade-Evaluation
print("")
print("Q1+Q2  ZUSTANDSAUTOMAT (Vorwaerts, kausal) + Wirkung auf die 54 Trades")
print("-" * 100)
BAL, EXPO, EXPU = "BALANCE", "EXPANSION_OBEN", "EXPANSION_UNTEN"
_deckeliste = {k: (dk, bk) for k, dk, bk, _s, _n in _deklariert}
hist: List[Tuple[int, str, float, float]] = []
_zustand_bei: Dict[int, str] = {}
zustand = BAL
decke, boden = DECKE0, 45.7890
for k in range(SPLIT, N):
    if k in _deckeliste and k > SPLIT:
        neu = _deckeliste[k]
        if (abs(neu[0] - decke) > 1e-9 or abs(neu[1] - boden) > 1e-9):
            if zustand is not BAL:
                hist.append((k, f"{zustand}->BALANCE(NEW)", neu[0], neu[1]))
            else:
                hist.append((k, "BALANCE->BALANCE(NEW)", neu[0], neu[1]))
            decke, boden = neu
        zustand = BAL
    _zustand_bei[k] = zustand
    if zustand is BAL:
        if cl[k] > decke and cl[k - 1] > decke:
            zustand = EXPO
        elif cl[k] < boden and cl[k - 1] < boden:
            zustand = EXPU
    elif zustand is EXPO:
        if cl[k] < decke and cl[k - 1] < decke:
            zustand = BAL
    elif zustand is EXPU:
        if cl[k] > boden and cl[k - 1] > boden:
            zustand = BAL

print(f"   Zustandswechsel: {len(hist)}")
print(f"{'Bar':>7}{'Datum':>18}  {'Wechsel':<34}{'Decke':>10}{'Boden':>10}")
for k, txt, dk, bk in hist[:20]:
    print(f"{k:>7}{str(np.datetime64(ts[k], 'm')):>18}  {txt:<34}{dk:>10.4f}{bk:>10.4f}")
print("")
from collections import Counter
_zaehl = Counter(_zustand_bei.values())
print(f"   Bar-Verteilung H2: {dict(_zaehl)}")

# Trades auswerten
TXT = (ROOT / "test" / "_tmp_s2_e20_poc_out.txt").read_text(encoding="utf-8")
blk = TXT.split("D  H2-EINZELTRADES")[1].split("PHASE_RANGE: H2")[0]
PAT = re.compile(
    r"^\s+entry\s+(\d+)\s+bar\s+(\d+)\s+(SHORT|LONG)\s+K(\d+)\s+R\s+"
    r"([+-][\d.]+)\s+tp2\s+([\d.]+)\s+poc\s+([\d.]+)\s+sl\s+([\d.]+)")
TR = []
for ln in blk.splitlines():
    m = PAT.match(ln)
    if m:
        TR.append({"entry_bar": int(m.group(1)), "k": int(m.group(2)),
                   "richtung": m.group(3), "kid": int(m.group(4)),
                   "r": float(m.group(5)), "tp2": float(m.group(6)),
                   "poc": float(m.group(7)), "sl": float(m.group(8))})

erlaubt, verboten = [], []
for t in TR:
    z = _zustand_bei.get(t["k"], BAL)
    ok = (z is BAL) or (z is EXPO and t["richtung"] == "LONG") \
        or (z is EXPU and t["richtung"] == "SHORT")
    (erlaubt if ok else verboten).append((t, z))

print("")
print(f"   Trades ERLAUBT : {len(erlaubt)}   TRADES VERBOTEN: {len(verboten)}")
if erlaubt:
    _u = [t["r"] * abs(t["sl"] - float(op[t["entry_bar"]])) for t, _z in erlaubt]
    _r = [t["r"] for t, _z in erlaubt]
    _a = [u / atr(t["k"], 14) for u, (t, _z) in zip(_u, erlaubt)]
    ges = sum(_r)
    rmax = max([0.0] + [x for x in _r if x > 0])
    ns = sum(1 for x in _r if x <= -1.0 + 1e-9)
    print(f"      R {ges:+.6f}  R_adj {ges - rmax:+.6f}  "
          f"USD {sum(_u):+.4f}  USD/Tr {sum(_u) / len(erlaubt):+.4f}  "
          f"ATR/Tr {sum(_a) / len(erlaubt):+.4f}  "
          f"N_stop {ns}  Q_stop {ns / len(erlaubt):.3f}")
    for t, z in erlaubt:
        print(f"         k {t['k']:>6} {t['richtung']:<5} K{t['kid']:<4} "
              f"R {t['r']:>+10.6f}  Zustand {z}")
print("")
print(f"   Verbots-Gruende: {dict(Counter(z for _t, z in verboten))}")

# ================================================= Q2d: Vergleichs-Automaten
print("")
print("Q2d  KALIBRIERTE DEKLARATIONSQUELLEN -- Vergleich Zustand / Wirkung")
print("-" * 100)


def _paar_pivot(k: int, mt: int, mp: int, m: float):
    """Balance-Paar aus bestaetigten Pivots (Pfad-B-Spec, kalibriertes m)."""
    pv = pivots_im_fenster(k, LB, mt)
    if len(pv) < mp or len({s for _k, s, _b in pv}) < 2:
        return None
    bs = [b for _k, _s, b in pv]
    if max(bs) - min(bs) >= m * atr(k, 960):
        return None
    return max(bs), min(bs)


def _paar_l960(k: int):
    """§12-Verfahren: aeusserste lebende Kante im 960er-Fenster."""
    kausal = [e for e in alle if e.erster_pivot_bar + 2 <= k + 1]
    a = max(0, k - 960 + 1)
    hl, ll = float(hi[a:k + 1].max()), float(lo[a:k + 1].min())
    ob = un = None
    for e in kausal:
        bars = [b for b, _ in e.wicks if b <= k]
        if not bars or max(bars) < k - cfg.wall_live_bars:
            continue
        if not (ll <= e.basis <= hl):
            continue
        if e.seite == "OBEN":
            if ob is None or e.basis > ob.basis:
                ob = e
        elif e.seite == "UNTEN":
            if un is None or e.basis < un.basis:
                un = e
    if ob is None or un is None:
        return None
    return float(ob.basis), float(un.basis)


def _automat(paar_fun, label: str) -> Dict[int, str]:
    """Vorwaerts-Automat; Neu-Deklaration setzt stets auf BALANCE zurueck."""
    zustand = BAL
    decke, boden = DECKE0, 45.7890
    zk: Dict[int, str] = {}
    new_dekl = 0
    for k in range(SPLIT, N):
        p = paar_fun(k)
        if p is not None and (abs(p[0] - decke) > 1e-9
                              or abs(p[1] - boden) > 1e-9):
            decke, boden = p
            zustand = BAL
            new_dekl += 1
        zk[k] = zustand
        if zustand is BAL:
            if cl[k] > decke and cl[k - 1] > decke:
                zustand = EXPO
            elif cl[k] < boden and cl[k - 1] < boden:
                zustand = EXPU
        elif zustand is EXPO:
            if cl[k] < decke and cl[k - 1] < decke:
                zustand = BAL
        elif zustand is EXPU:
            if cl[k] > boden and cl[k - 1] > boden:
                zustand = BAL
    erl, ver = [], []
    for t in TR:
        z = zk.get(t["k"], BAL)
        ok = (z is BAL) or (z is EXPO and t["richtung"] == "LONG") \
            or (z is EXPU and t["richtung"] == "SHORT")
        (erl if ok else ver).append((t, z))
    _zv = dict(Counter(zk.values()))
    r = [_t["r"] for _t, _z in erl]
    u = [_t["r"] * abs(_t["sl"] - float(op[_t["entry_bar"]]))
         for _t, _z in erl]
    _at = [uu / atr(_t["k"], 14) for uu, (_t, _z) in zip(u, erl)]
    print(f"   [{label}]")
    print(f"      Neu-Deklarationen {new_dekl}   Zustaende {_zv}")
    if erl:
        ges = sum(r)
        rmax = max([0.0] + [x for x in r if x > 0])
        ns = sum(1 for x in r if x <= -1.0 + 1e-9)
        print(f"      ERLAUBT {len(erl):>3} / VERBOTEN {len(ver):>3}   "
              f"R {ges:+.6f}  R_adj {ges - rmax:+.6f}  "
              f"USD/Tr {sum(u) / len(erl):+.4f}  "
              f"ATR/Tr {sum(_at) / len(erl):+.4f}  "
              f"Q_stop {ns / len(erl):.3f}")
    else:
        print(f"      ERLAUBT   0 / VERBOTEN {len(ver):>3}   <-- NOT-AUS")
    _gw = [(_t["k"], _t["r"]) for _t, _z in ver if _t["r"] > 0]
    print(f"      getoetete Gewinner (R>0): {len(_gw)}"
          + (f"  {_gw}" if _gw else "  --"))
    return zk


# Referenz OHNE GATE (alle 54, gleiche Risikobasis)
_r0 = [t["r"] for t in TR]
_u0 = [t["r"] * abs(t["sl"] - float(op[t["entry_bar"]])) for t in TR]
_a0 = [uu / atr(t["k"], 14) for uu, t in zip(_u0, TR)]
_g0 = sum(_r0)
_r0max = max([0.0] + [x for x in _r0 if x > 0])
_n0 = sum(1 for x in _r0 if x <= -1.0 + 1e-9)
print(f"   [OHNE GATE, alle {len(TR)}]")
print(f"      R {_g0:+.6f}  R_adj {_g0 - _r0max:+.6f}  "
      f"USD/Tr {sum(_u0) / len(TR):+.4f}  ATR/Tr {sum(_a0) / len(TR):+.4f}  "
      f"N_stop {_n0}  Q_stop {_n0 / len(TR):.3f}")
print(f"      Gewinner (R>0): "
      f"{[(t['k'], round(t['r'], 6)) for t in TR if t['r'] > 0]}")
print(f"      USD gesamt {sum(_u0):+.4f}   Avg-Risiko "
      f"{sum(abs(t['sl'] - float(op[t['entry_bar']])) for t in TR) / len(TR):.4f}")


_automat(lambda k: _paar_pivot(k, 3, 3, 10.0), "PIVOT m=10 (touch>=3 piv>=3)")
_automat(lambda k: _paar_pivot(k, 3, 3, 20.0), "PIVOT m=20 (touch>=3 piv>=3)")
_automat(_paar_l960, "L960-SEG (aeusserste Kante, §12-Verfahren)")

print("")
print("Q2e  L960-PAAR-ZEITREIHE (Stichprobe, Schritt 480) -- Soll: §12-Kette")
print("-" * 100)
print(f"   {'Bar':>7}{'Datum':<13}{'Decke':>10}{'Boden':>10}{'Band':>9}"
      f"{'close':>9}  Position")
for _k in range(SPLIT, N, 480):
    _p = _paar_l960(_k)
    if _p is None:
        print(f"   {_k:>7}{str(np.datetime64(ts[_k], 'D')):<13}{'--':>10}")
        continue
    _dk, _bk = _p
    _pos = "INNEN" if _bk < cl[_k] < _dk else "AUSSEN"
    print(f"   {_k:>7}{str(np.datetime64(ts[_k], 'D')):<13}{_dk:>10.4f}"
          f"{_bk:>10.4f}{_dk - _bk:>9.4f}{cl[_k]:>9.4f}  {_pos}")

_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
