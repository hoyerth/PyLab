# -*- coding: utf-8 -*-
"""E-29 -- BREAK-EVEN / TRAILING-STUDIE (pfadgenau, read-only).

Liest die in E-29 gesicherten Setup-Geometrien (`_tmp_e29_setups_*.pkl`) und
simuliert die Schluss-Logik von `_c_loese_trade` (Engine Z. 1596-1647) erneut
-- zusaetzlich aber mit einem STUFENLOSEN STOP-MANAGEMENT:

    Sobald die guenstige Exkursion (MFE) den Schwellwert x erreicht hat,
    wird der Stop auf Einstand (Break-Even) gezogen -- wirksam ab dem
    FOLGEBAR (kein Intrabar-Look-ahead).

Beide Haelften laufen unabhaengig (TP1 = POC, TP2 = Gegenkante), teilen aber
denselben Stop. Bei Gleichstand im selben Bar gewinnt der STOP (pessimistisch,
identisch zur Engine: `t1 < t_sl` ist strikt).

Aufruf: python test/_tmp_e29_be.py <s2|aug> <bins>
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

MODE = (sys.argv[1] if len(sys.argv) > 1 else "s2").lower()
BINS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
SPLIT = 17692

if MODE == "s2":
    scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
else:
    scan = eng._se_scan("AUG", eng.StraightEdgeHarnessKonfiguration())
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)

SETUPS = pickle.loads(
    (ROOT / "test" / f"_tmp_e29_setups_{MODE}_b{BINS}.pkl").read_bytes())

_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])


def atr14(k: int) -> float:
    return float(_tr[max(0, k - 13):k + 1].mean())


def sim_halb(entry: float, risk: float, sl: float, ziel: float,
             e_bar: int, short: bool, be_x: Optional[float],
             trail_x: Optional[float]) -> Tuple[float, int, str]:
    """Eine Halb-Position. be_x = MFE-Schwelle fuer Stop auf Einstand;
    trail_x = Abstand des Nachzieh-Stops unter/ueber dem MFE-Extrem."""
    nb = len(hi) - e_bar
    stop = sl
    armed = False
    mfe = 0.0
    for m in range(nb):
        h, l = float(hi[e_bar + m]), float(lo[e_bar + m])
        if short:
            hit_sl = h >= stop
            hit_tp = l <= ziel
        else:
            hit_sl = l <= stop
            hit_tp = h >= ziel
        if hit_sl:                       # Gleichstand -> Stop gewinnt
            r = ((entry - stop) if short else (stop - entry)) / risk
            return r, e_bar + m, ("SL" if not armed else "BE")
        if hit_tp:
            r = ((entry - ziel) if short else (ziel - entry)) / risk
            return r, e_bar + m, "TP"
        # Bar geschlossen -> MFE fortschreiben (erst danach scharf schalten)
        exk = ((entry - l) if short else (h - entry)) / risk
        mfe = max(mfe, exk)
        if be_x is not None and not armed and mfe >= be_x:
            armed = True
            stop = entry
        if trail_x is not None and armed:
            neu = (entry - 0.0) if short else entry
            kandidat = ((mfe - trail_x) * risk)
            if short:
                kandidat = entry - kandidat
                stop = min(stop, kandidat) if armed else kandidat
            else:
                kandidat = entry + kandidat
                stop = max(stop, kandidat) if armed else kandidat
    r = ((entry - float(cl[-1])) if short else (float(cl[-1]) - entry)) / risk
    return r, e_bar + nb - 1, "ENDE"


def studie(be_x: Optional[float], trail_x: Optional[float] = None) -> Dict:
    rl: List[float] = []
    usd: List[float] = []
    n_stop = 0
    geaendert = 0
    for s in SETUPS:
        e_bar = int(s["entry_bar"])
        entry = float(s["entry"])
        risk = abs(float(s["sl"]) - entry) or 1e-9
        short = s["richtung"] == "SHORT"
        r1, _, _ = sim_halb(entry, risk, float(s["sl"]), float(s["poc"]),
                            e_bar, short, be_x, trail_x)
        r2, _, _ = sim_halb(entry, risk, float(s["sl"]), float(s["tp2"]),
                            e_bar, short, be_x, trail_x)
        rm = 0.5 * r1 + 0.5 * r2
        rl.append(rm)
        usd.append(rm * risk)
        if abs(rm - float(s["r"])) > 1e-9:
            geaendert += 1
        if rm <= -1.0 + 1e-9:
            n_stop += 1
    sat = [u / atr14(int(s["bar"])) for u, s in zip(usd, SETUPS)]
    return {"R": sum(rl), "USDn": sum(usd) / len(usd), "ATRn": sum(sat) / len(sat),
            "Qstop": n_stop / len(rl), "geaendert": geaendert, "n": len(rl),
            "USD": sum(usd)}


print("=" * 100)
print(f"E-29 BREAK-EVEN-STUDIE -- {MODE.upper()}  b{BINS}  n = {len(SETUPS)}")
print("=" * 100)
print(f"{'Variante':<26}{'R gesamt':>13}{'USD/Tr':>9}{'ATR/Tr':>9}"
      f"{'Q_stop':>8}{'geaendert':>10}{'Gew%':>7}")
print("-" * 100)


def zeile(name: str, e: Dict) -> None:
    print(f"{name:<26}{e['R']:>+13.6f}{e['USDn']:>+9.4f}{e['ATRn']:>+9.4f}"
          f"{e['Qstop']:>8.3f}{e['geaendert']:>10}{0.0:>7.1f}")


basis = studie(None)
zeile("BASIS (arretiert, kein BE)", basis)
for x in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
    zeile(f"BE-Stop ab +{x:.2f} R", studie(x))
for x in (1.0, 2.0):
    for t in (0.5, 1.0):
        zeile(f"BE +{x:.2f} R + Trail {t:.1f} R", studie(x, t))
print("")
print("Hinweis: 'geaendert' = Trades, deren R sich durch die Mechanik bewegt.")
print("         Q_stop = Anteil mit r <= -1 (beide Haelften am Stop).")
print("         Die Simulation nutzt ausschliesslich die gespeicherte Geometrie")
print("         (entry/sl/poc/tp2/entry_bar) -- keine Engine-Aenderung.")
