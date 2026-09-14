# -*- coding: utf-8 -*-
"""E-23 OFFLINE-MATRIX (read-only, kein Engine-Lauf) -- POC/TP1/STOP-Szenarien.

Haelt die **Trade-Auswahl fest** (die 54 H2-Trades aus ``LEGACY_CTRL``) und
spielt je Szenario NUR den Trade-Aufloeser durch. Damit ist die Messung
selektions-invariant und in < 1 s verfuegbar -- sie beantwortet VOR jedem
Engine-Lauf, ob ein Fix ueberhaupt etwas bewegt.

Aufgeloest wird mit der ENGINE-EIGENEN Funktion ``_c_loese_trade``
(identische TP1/TP2/SL-Halb-Logik). Die SL-Neubildung ist eine
Approximation: ``sl = cluster_ext + 0.05`` -> ``cluster_ext = sl - 0.05``.

Szenarien:
  LEGACY          Kontrolle -- muss die Detail-Ausgabe reproduzieren
  POC_W480/W960   poc_start = k - 480 / k - 960, PHASE_RANGE, tp1 = poc
  POC_SPLIT       poc_start = 17.692 (Split), PHASE_RANGE, tp1 = poc
  TP1_MID         tp1 = Mittelband (boden + decke) / 2 (Ziel-poc bleibt)
  POC_W960_MID    poc_start = k - 960 + tp1 = Mittelband
  STOP_ATR15      sl = max(sl_legacy, entry + 1.5 * ATR14[k])
  STOP_ATR15_W960 STOP_ATR15 + poc_start = k - 960
  STOP_PCT1       sl = max(sl_legacy, entry * 1.01)  (1 % Mindestabstand)
  STOP_PCT1_W960  STOP_PCT1 + poc_start = k - 960

Dual-Ausweis (Beschluss 4): R / USD-Bewegung / ATR14-normierter Ertrag.
"""
from __future__ import annotations

import importlib.util
import pickle
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
d = scan["d"]
n = scan["n"]
op = d["open"].to_numpy(float)
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
SPLIT = 17692
BODEN, DECKE = 45.7890, 47.1221            # Segment K408/K409 (S2)
MID = (BODEN + DECKE) / 2.0

# ATR14 (kausal), true range auf der BKZ-Reihe
_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])   # Index i = Bar i


def atr14(k: int) -> float:
    a, b = max(0, k - 14 + 1), k + 1
    return float(_tr[a:b].mean()) if b - a > 0 else float("nan")


# ------------------------------------------------ 54 H2-Trades aus Detail
TXT = (ROOT / "test" / "_tmp_s2_e20_poc_out.txt").read_text(encoding="utf-8")
seg = TXT.split("D  H2-EINZELTRADES")[1]
leg_block = seg.split("PHASE_RANGE: H2")[0]
PAT = re.compile(
    r"^\s+entry\s+(\d+)\s+bar\s+(\d+)\s+(SHORT|LONG)\s+K(\d+)\s+R\s+"
    r"([+-][\d.]+)\s+tp2\s+([\d.]+)\s+poc\s+([\d.]+)\s+sl\s+([\d.]+)")
TRADES: List[Dict] = []
for ln in leg_block.splitlines():
    m = PAT.match(ln)
    if m:
        TRADES.append({
            "entry_bar": int(m.group(1)), "k": int(m.group(2)),
            "richtung": m.group(3), "kid": int(m.group(4)),
            "r_legacy": float(m.group(5)), "tp2": float(m.group(6)),
            "poc_legacy": float(m.group(7)), "sl_legacy": float(m.group(8)),
        })

print(f"H2-Trades (festgehalten): {len(TRADES)}")
print(f"Segment-Range: boden {BODEN:.4f} / decke {DECKE:.4f} "
      f"-> Mittelband {MID:.4f}")
print(f"ATR14 am 1. Signal-Bar (k={TRADES[0]['k']}): {atr14(TRADES[0]['k']):.4f} USD")
print("")

# ---------------------------------------------------------- Szenario-Defs
SCEN: Dict[str, Dict] = {
    "LEGACY":         {"poc_start": None, "tp1": "poc", "sl": "legacy"},
    "POC_W480":       {"poc_start": "w480", "tp1": "poc", "sl": "legacy"},
    "POC_W960":       {"poc_start": "w960", "tp1": "poc", "sl": "legacy"},
    "POC_SPLIT":      {"poc_start": "split", "tp1": "poc", "sl": "legacy"},
    "TP1_MID":        {"poc_start": None, "tp1": "mid", "sl": "legacy"},
    "POC_W960_MID":   {"poc_start": "w960", "tp1": "mid", "sl": "legacy"},
    "STOP_ATR15":     {"poc_start": None, "tp1": "poc", "sl": "atr15"},
    "STOP_ATR15_W960": {"poc_start": "w960", "tp1": "poc", "sl": "atr15"},
    "STOP_PCT1":      {"poc_start": None, "tp1": "poc", "sl": "pct1"},
    "STOP_PCT1_W960": {"poc_start": "w960", "tp1": "poc", "sl": "pct1"},
    "STOP_ATR30":     {"poc_start": None, "tp1": "poc", "sl": "atr30"},
    "STOP_ATR50":     {"poc_start": None, "tp1": "poc", "sl": "atr50"},
    "STOP_ATR50_W960": {"poc_start": "w960", "tp1": "poc", "sl": "atr50"},
}
_MULT = {"atr15": 1.5, "atr30": 3.0, "atr50": 5.0}


def poc_start_of(modus: str, k: int) -> int:
    if modus == "w480":
        return max(0, k - 480)
    if modus == "w960":
        return max(0, k - 960)
    if modus == "split":
        return SPLIT
    return 0


def metrik(zeilen: List[Dict]) -> Dict[str, float]:
    n_ = len(zeilen)
    if n_ == 0:
        return {"N": 0}
    r = [z["r"] for z in zeilen]
    ges = float(sum(r))
    rmax = max([0.0] + [x for x in r if x > 0.0])
    nstop = sum(1 for x in r if x <= -1.0 + 1e-9)
    usd = float(sum(z["usd"] for z in zeilen))
    ratr = float(sum(z["r_atr"] for z in zeilen))
    return {"N": n_, "R": ges, "R_max": rmax, "R_adj": ges - rmax,
            "N_stop": nstop, "Q_stop": nstop / n_,
            "USD": usd, "ATR": ratr,
            "EV_adj": (ges - rmax) / n_, "USD_tr": usd / n_, "ATR_tr": ratr / n_}


RES: Dict[str, Dict[str, float]] = {}
DETAIL: Dict[str, List[Dict]] = {}
for name, p in SCEN.items():
    zeilen: List[Dict] = []
    abgelehnt = 0
    for t in TRADES:
        k, eb = t["k"], t["entry_bar"]
        entry = float(op[eb])
        atr = atr14(k)
        # ---- SL -------------------------------------------------------
        if p["sl"] in _MULT:
            _m = _MULT[p["sl"]] * atr
            sl = (max(t["sl_legacy"], entry + _m) if t["richtung"] == "SHORT"
                  else min(t["sl_legacy"], entry - _m))
        elif p["sl"] == "pct1":
            sl = max(t["sl_legacy"], entry * 1.01) if t["richtung"] == "SHORT" \
                 else min(t["sl_legacy"], entry * 0.99)
        else:
            sl = t["sl_legacy"]
        # ---- POC ------------------------------------------------------
        if p["poc_start"] is None:
            poc = t["poc_legacy"]
        else:
            ps = poc_start_of(p["poc_start"], k)
            poc = eng.berechne_kausalen_histogramm_poc(
                d, ps, k, BODEN, DECKE, cfg.num_bins)
        # ---- TP1 ------------------------------------------------------
        tp1 = MID if p["tp1"] == "mid" else poc
        tp2 = t["tp2"]
        # ---- Zulaessigkeit (unveraendert hart) -------------------------
        if t["richtung"] == "SHORT":
            ok = sl > entry > tp1 > tp2
        else:
            ok = sl < entry < tp1 < tp2
        if not ok:
            abgelehnt += 1
            continue
        tr = eng._c_loese_trade(hi, lo, cl, eb, entry, t["richtung"], sl,
                                tp1, tp2, cfg.tp1_anteil_pct)
        # USD = R * risk ist exakt der Stueck-PnL (R ist auf risk normiert).
        risk = abs(sl - entry)
        usd = float(tr.r_mult) * risk
        ratr = usd / atr if atr and not np.isnan(atr) else float("nan")
        zeilen.append({"eb": eb, "k": k, "kid": t["kid"], "r": tr.r_mult,
                       "tp1": tp1, "sl": sl, "usd": usd, "r_atr": ratr,
                       "risk": abs(sl - entry), "atr": atr})
    DETAIL[name] = zeilen
    m = metrik(zeilen)
    m["abgelehnt"] = abgelehnt
    RES[name] = m

KOPF = (f"{'Szenario':<17}{'N':>4}{'ablehn':>7}{'R':>13}{'R_adj':>13}"
        f"{'Nstop':>6}{'Q_stop':>8}{'USD':>11}{'USD/Tr':>9}{'ATR/Tr':>9}")
print("=" * len(KOPF))
print("E-23 OFFLINE-MATRIX (54 H2-Trades festgehalten; Aufloeser = Engine)")
print("=" * len(KOPF))
print(KOPF)
print("-" * len(KOPF))
for name in SCEN:
    m = RES[name]
    print(f"{name:<17}{m['N']:>4}{m['abgelehnt']:>7}{m['R']:>+13.6f}"
          f"{m['R_adj']:>+13.6f}{m['N_stop']:>6}{m['Q_stop']:>8.3f}"
          f"{m['USD']:>+11.2f}{m['USD_tr']:>+9.4f}{m['ATR_tr']:>+9.4f}")
print("")

print("Kontrolle LEGACY gegen Detail-Ausgabe:")
dl = sum(t["r_legacy"] for t in TRADES)
print(f"   Detail-Summe (Datei)  = {dl:+.6f}   Offline LEGACY = "
      f"{RES['LEGACY']['R']:+.6f}   "
      f"{'OK' if abs(dl - RES['LEGACY']['R']) < 1e-6 else 'ABWEICHUNG'}")
print("")

_TP2 = {t["entry_bar"]: t["tp2"] for t in TRADES}
print("TP1-Abstand zum Ziel (tp2) je poc_start (Median/Min/Max, USD):")
for name in ("LEGACY", "POC_W480", "POC_W960", "POC_SPLIT", "TP1_MID"):
    z = DETAIL[name]
    if not z:
        continue
    dst = sorted(abs(x["tp1"] - _TP2[x["eb"]]) for x in z)
    print(f"   {name:<10} {np.median(dst):>8.4f}  {min(dst):>8.4f}  {max(dst):>8.4f}")
print("")

print("Risiko-Verteilung LEGACY vs. STOP_ATR15 vs. STOP_PCT1 (USD):")
for name in ("LEGACY", "STOP_ATR15", "STOP_PCT1"):
    rk = sorted(x["risk"] for x in DETAIL[name])
    if rk:
        print(f"   {name:<12} min {rk[0]:>7.4f}  Median {np.median(rk):>7.4f}  "
              f"max {rk[-1]:>7.4f}")

# ------------------------------------------------ E-23 Erratum-Nachweis
print("")
print("E-23 Erratum (Prazision): R-Skalierung des Ausreissers entry 18825")
e25 = [t for t in TRADES if t["entry_bar"] == 18825][0]
entry = float(op[18825])
mv = entry - e25["tp2"]
for pct in (0.45, 1.0, 2.0):
    risk = entry * pct / 100.0
    print(f"   risk {risk:.6f} USD ({pct:.2f} %)  ->  R = {mv / risk:.6f}")
print(f"   tatsaechlich risk {e25['sl_legacy'] - entry:.6f} -> "
      f"R = {mv / (e25['sl_legacy'] - entry):.6f}")
