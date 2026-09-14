# test/reclaim_scale_diag.py
"""Diagnose: Skalen-Diskrepanz der absoluten Bruch-Toleranz (Design-Frage i).

Befund (Band-Bruch, 02.09.): EDGE_TOL=0.15 ist absolut. S2 (2025, mean ~37.7,
mittlere Bar-Range ~0.097) hat eine ca. 4x kleinere Range als S1 (2026, mean
~71.7, Range ~0.377) -> das Hysterese-Band [p-tol, p+tol] ist auf S2 relativ
4x breiter -> haelt Stale-Level am Leben -> Overtrading (643 Sig, -23.1R).

Frage: Welche RELATIVE Toleranz (Vielfaches der rollierenden Bar-Range) waere
ueber AUG/S1/S2 skalen-aquivalent? Vor jeder Implementierung messen:
  1. Verteilung der Bar-Range (high-low) je Fenster + Verhaeltnis zu 0.15.
  2. Rollierende mittlere Bar-Range (200er-Fenster, shift 1 - kausal) als
     Kandidaten-Bezug: Quantile je Fenster.
  3. Was waere tol_rel = a * roll_mean_range fuer a in {0.5, 1.0, 1.5, 2.0}
     in USD -> Vergleich mit dem heutigen absoluten 0.15.
  4. Welcher Bruchteil der Bars hat range < EDGE_TOL (Band dominiert den
     Bar-Koerper komplett) - Indikator fuer Ueber-Elastizitaet.

Rein diagnostisch, KEINE Implementierung. Aufruf:
  python test/reclaim_scale_diag.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

WINDOWS: List[Tuple[str, str, str]] = [
    ("AUG", "2026-08-10", "2026-08-28"),
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]
TOL_ABS: float = 0.15
MULT: List[float] = [0.5, 1.0, 1.5, 2.0]


def _q(x: np.ndarray, p: float) -> float:
    return float(np.nanpercentile(x, p)) if len(x) else float("nan")


def analyse(name: str, start: str, ende: str) -> None:
    df = res.load_data(res.DB_PATH, start, ende)
    hi = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    cl = df["close"].values.astype(float)
    rng = hi - lo
    body = np.abs(cl - df["open"].values.astype(float))

    # kausale rollierende mittlere Bar-Range (200er, shift 1)
    s = pd.Series(rng)
    roll_mean = s.rolling(200, min_periods=20).mean().shift(1).to_numpy()

    print(f"\n[{name}] Bars {len(df)} | close mean {cl.mean():.1f} | "
          f"close median {np.median(cl):.1f}")
    print(f"  Bar-Range (H-L):   mean {rng.mean():.4f} | median {np.median(rng):.4f} | "
          f"p90 {_q(rng, 90):.4f} | p10 {_q(rng, 10):.4f}")
    print(f"  Bar-Body (|C-O|):  mean {body.mean():.4f} | median {np.median(body):.4f}")

    # Verhaeltnis Range zu absolutem TOL: range < TOL = Band groesser als Bar-Koerper
    frac_lt_tol = float(np.mean(rng < TOL_ABS))
    frac_lt_2tol = float(np.mean(rng < 2 * TOL_ABS))
    print(f"  Anteil Bars mit Range < EDGE_TOL({TOL_ABS}):  {frac_lt_tol * 100:5.1f}%")
    print(f"  Anteil Bars mit Range < 2*EDGE_TOL({2 * TOL_ABS}): {frac_lt_2tol * 100:5.1f}%")

    # rollierende mittlere Range als Bezug
    rm = roll_mean[~np.isnan(roll_mean)]
    print(f"  Roll. mean Range (200, shift1): mean {rm.mean():.4f} | "
          f"median {np.median(rm):.4f} | p10 {_q(rm, 10):.4f} | p90 {_q(rm, 90):.4f}")

    # heutige absolute Toleranz relativ zur rollierenden Range
    rel_now = TOL_ABS / roll_mean
    rel_now_v = rel_now[~np.isnan(rel_now)]
    print(f"  EDGE_TOL 0.15 / roll.mean Range: mean {np.mean(rel_now_v):.2f}x | "
          f"median {np.median(rel_now_v):.2f}x | p10 {_q(rel_now_v, 10):.2f}x | "
          f"p90 {_q(rel_now_v, 90):.2f}x")

    # Kandidaten tol_rel = a * roll.mean Range -> USD (mediane Perspektive)
    med_rm = float(np.median(rm))
    for a in MULT:
        print(f"    a={a:4.1f} -> tol USD (median) {a * med_rm:.4f} | "
              f"p10 {a * _q(rm, 10):.4f} | p90 {a * _q(rm, 90):.4f} | "
              f"vs 0.15 = {0.15 / (a * med_rm):5.2f}x")

    # ATR-analog (Wilder 14 auf Bar-Range als naechster Kandidat)
    # einfacher: EWMA der Range mit alpha=1/14, kausal
    ew = pd.Series(rng).ewm(alpha=1 / 14, min_periods=14).mean().shift(1).to_numpy()
    ewv = ew[~np.isnan(ew)]
    print(f"  EWMA Range (alpha=1/14, shift1): mean {ewv.mean():.4f} | "
          f"median {np.median(ewv):.4f} | p90 {_q(ewv, 90):.4f}")


def main() -> None:
    for name, start, ende in WINDOWS:
        analyse(name, start, ende)


if __name__ == "__main__":
    main()
