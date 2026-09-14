# -*- coding: utf-8 -*-
"""E-27 (read-only, offline) -- Q29-LOKALISIERUNG: globales vs. lokales Quartil.

Aufruf:  python test/_tmp_e27_q29_lokal.py <modus> <lookback>
         modus  = s2 | aug
         lookback = 0 (global) | 960 | 480

Ein Lauf pro Prozess (die volle `_se_trades`-Kaskade ist teuer). Schreibt
`_tmp_e27_q29_lokal_<modus>_<lookback>_out.txt`.

Eingriff (ausschliesslich die Q29-Referenz, keine Logikaenderung):

    ex_hi = float(np.max(hi[:k + 1]))   ->  hi[_a29:k + 1]
    ex_lo = float(np.min(lo[:k + 1]))   ->  lo[_a29:k + 1]

mit `_a29 = 0` (global) bzw. `k-LB+1` (lokaler Lookback).
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import pickle
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
SPLIT = 17692
MODE = (sys.argv[1] if len(sys.argv) > 1 else "s2").lower()
Q29_LB_INI = int(sys.argv[2]) if len(sys.argv) > 2 else 0
OUT = ROOT / "test" / f"_tmp_e27_q29_lokal_{MODE}_{Q29_LB_INI}_out.txt"
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

spec = importlib.util.spec_from_file_location("eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg = eng.StraightEdgeHarnessKonfiguration()

t0 = time.time()
if MODE == "s2":
    scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
    box_orig = scan["box_end_bar"]
    # S2: der Cache traegt die Partition (17692). Fuer die H2-Auswertung laeuft
    # der Harness bis zum Fensterende n (box_end_bar = n).
    scan["box_end_bar"] = scan["n"]
    TITEL = "S2"
else:
    # AUG: `box_end_bar` BLEIBT UNVERAENDERT -- er ist die Box-Grenze
    # (2026-08-19). Ein Ueberschreiben auf n wuerde den Referenzlauf
    # verfaelschen.
    scan = eng._se_scan("AUG", cfg)
    box_orig = scan["box_end_bar"]
    TITEL = "AUG"
N = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].to_numpy()
t_lade = time.time() - t0

# ------------------------------------------------------------ AST-Extraktion
quelle = ENGINE_P.read_text(encoding="utf-8")
baum = ast.parse(quelle)
knoten = next(n for n in ast.walk(baum)
              if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
zeilen = quelle.split("\n")
SRC = "\n".join(zeilen[knoten.lineno - 1:knoten.end_lineno])
_n_stat = len(re.findall(r'stats\["(\w+)"\] \+= 1', SRC))
SRC = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', SRC)

ERS = [
    ("""        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])""",
     """        for richtung in ("SHORT", "LONG"):
            _CUR[0] = k
            _CUR[1] = richtung
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])"""),
    ("""        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))""",
     """        _a29 = _LB0(k)
        ex_hi = float(np.max(hi[_a29:k + 1]))
        ex_lo = float(np.min(lo[_a29:k + 1]))"""),
    ("""            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue""",
     """            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                _hit(_CUR, "kaskade_leer")
                continue
            _hit(_CUR, "kandidat")"""),
    ("""            if stufe_n == 0:
                continue""",
     """            if stufe_n == 0:
                _hit(_CUR, "stufe0")
                continue"""),
    ("""            letzter_trade[kd.kid] = setup
            setups.append(setup)""",
     """            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")"""),
]
for alt, neu in ERS:
    assert alt in SRC, "Ankertext fehlt:\n" + alt[:90]
    SRC = SRC.replace(alt, neu, 1)

Q29_LB: List[int] = [Q29_LB_INI]


def _lb0(k: int) -> int:
    return 0 if Q29_LB[0] <= 0 else max(0, k - Q29_LB[0] + 1)


HITS: List[Tuple[int, str, str]] = []
ns: Dict = dict(eng.__dict__)
ns["_CUR"] = [0, "?"]
ns["_LB0"] = _lb0


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
exec(compile(SRC, str(ENGINE_P) + "<q29>", "exec"), ns)  # noqa: S102
fn = ns["_se_trades"]

# --------------------------------------------------------------- Kennzahlen
_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])


def atr14(k: int) -> float:
    return float(_tr[max(0, k - 13):k + 1].mean())


def kz(ss: List) -> Dict[str, float]:
    if not ss:
        return {"n": 0, "R": 0.0, "R_adj": 0.0, "USD": 0.0, "USDn": 0.0,
                "ATRn": 0.0, "Qstop": 0.0}
    r = [float(s.r) for s in ss]
    usd = [float(s.r) * abs(float(s.sl) - float(s.entry)) for s in ss]
    at = [u / atr14(int(s.bar)) for u, s in zip(usd, ss)]
    rmax = max([0.0] + [x for x in r if x > 0])
    nstop = sum(1 for x in r if x <= -1.0 + 1e-9)
    return {"n": len(ss), "R": sum(r), "R_adj": sum(r) - rmax, "USD": sum(usd),
            "USDn": sum(usd) / len(ss), "ATRn": sum(at) / len(ss),
            "Qstop": nstop / len(ss)}


print("=" * 104)
print(f"E-27 Q29-LOKALISIERUNG -- {TITEL}  Variante "
      f"{'GLOBAL (0..k)' if Q29_LB_INI == 0 else f'LOKAL {Q29_LB_INI}'}")
print("=" * 104)
print(f"Engine   : {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"_se_trades Zeilen {knoten.lineno}..{knoten.end_lineno}  |  "
      f"n {N}  box_end_bar {box_orig} -> Laufgrenze {scan['box_end_bar']}  |  "
      f"Ladezeit {t_lade:.1f}s")
print(f"Instrumentierung: {_n_stat} × stats-Hook, Q29-Referenzzeilen ersetzt, "
      f"Marker kandidat/stufe0/SETUP, _CUR-Richtungszeiger")

t1 = time.time()
setups, stats = fn(scan, cfg)
t_lauf = time.time() - t1
print(f"Laufzeit _se_trades: {t_lauf:.1f}s   Setups {len(setups)}")

alle_s = list(setups)
h1 = [s for s in alle_s if int(s.bar) < SPLIT]
h2 = [s for s in alle_s if int(s.bar) >= SPLIT]
ka, k1, k2 = kz(alle_s), kz(h1), kz(h2)
print("")
print(f"   gesamt : n {ka['n']:>4}  R {ka['R']:+.6f}  R_adj {ka['R_adj']:+.6f}"
      f"  USD {ka['USD']:+.4f}  USD/Tr {ka['USDn']:+.4f}"
      f"  ATR/Tr {ka['ATRn']:+.4f}  Q_stop {ka['Qstop']:.3f}")
print(f"   H1     : n {k1['n']:>4}  R {k1['R']:+.6f}  R_adj {k1['R_adj']:+.6f}"
      f"  USD/Tr {k1['USDn']:+.4f}  ATR/Tr {k1['ATRn']:+.4f}"
      f"  Q_stop {k1['Qstop']:.3f}")
print(f"   H2     : n {k2['n']:>4}  R {k2['R']:+.6f}  R_adj {k2['R_adj']:+.6f}"
      f"  USD/Tr {k2['USDn']:+.4f}  ATR/Tr {k2['ATRn']:+.4f}"
      f"  Q_stop {k2['Qstop']:.3f}")
print(f"   LONG   : n {sum(1 for s in alle_s if s.richtung == 'LONG'):>4}"
      f"   SHORT: n {sum(1 for s in alle_s if s.richtung == 'SHORT'):>4}")

print("")
print("   Q29-TRICHTER (Kandidaten / Q29-Sperre / weiter / SETUP):")
print(f"   {'Haelfte':<7}{'Richtung':<8}{'Kand.':>7}{'Q29':>7}{'weiter':>8}"
      f"{'Anteil':>8}{'SETUP':>7}")
for hname, a, b in (("H1", 0, SPLIT), ("H2", SPLIT, N)):
    for richtung in ("SHORT", "LONG"):
        cand = sum(1 for (kk, r, key) in HITS
                   if r == richtung and a <= kk < b and key == "kandidat")
        q29 = sum(1 for (kk, r, key) in HITS
                  if r == richtung and a <= kk < b and key == "quartil_blockiert")
        st = sum(1 for (kk, r, key) in HITS
                 if r == richtung and a <= kk < b and key == "SETUP")
        durch = cand - q29
        print(f"   {hname:<7}{richtung:<8}{cand:>7}{q29:>7}{durch:>8}"
              f"{(durch / cand * 100.0) if cand else 0.0:>7.1f}%{st:>7}")

print("")
print("   TRADE-LISTE (Bar, Datum, Richtung, Kante, R, entry, sl, poc, tp2):")
for s in sorted(alle_s, key=lambda x: int(x.bar)):
    print(f"      {int(s.bar):>6} {str(np.datetime64(ts[int(s.bar)], 'm')):<17}"
          f"{s.richtung:<6}K{int(s.kid):<4} R {float(s.r):>+10.5f}  "
          f"e {float(s.entry):>8.4f}  sl {float(s.sl):>8.4f}  "
          f"poc {float(s.poc):>8.4f}  tp2 {float(s.tp2):>8.4f}")

print("")
print(f"ENDE {TITEL} LB={Q29_LB_INI}   Gesamtlaufzeit {time.time() - t0:.1f}s")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
