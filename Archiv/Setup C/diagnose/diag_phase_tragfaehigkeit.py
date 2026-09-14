"""Wegwerf-Diagnose: Tragfaehigkeit der Phasen-/Balance-Erkennung.

Prueft die Hypothese "unsere Methode erkennt Balance/Plateau nicht" mit vier
reinen MESSUNGEN (keine Strategie, keine Optimierung, kein Trade-Simulator):

  A) Wie viele Pivots definieren eine "Phase" ueberhaupt, und wie lang ist sie?
     -> Wenn 4-6 Pivots ueber 46+ Bars eine Kante definieren, ist die Linie
        an sehr wenige Punkte gefittet.

  B) TIGHTNESS-Test: Ist der Phasen-Range (U-L) enger als ein ZUFALLSFENSTER
     gleicher Laenge? Als Perzentil des Zufalls-Null.
     -> Perzentil ~50% = die "Balance" ist von Rauschen nicht unterscheidbar.

  C) EXPANSION-Test: Ist der Move NACH dem Bruch groesser als der
     Balance-Range davor (move_range / balance_range)?
     -> Verhaeltnis ~1 = kein Ausbruch/Expansion-Effekt vorhanden.

  D) FOLLOW-THROUGH-Test: Ist der Vorwaerts-Ertrag NACH dem Bruch (in
     Bruchrichtung, in ATR-Einheiten) besser als bei ZUFALLSEINSTIEG?
     -> Permutations-Null ueber alle Bars: wenn der Bruch nicht schlaegt,
        traegt die Phase keine Information.

Zeitbasis: BKZ ueber ``load_data`` (time AT TIME ZONE 'UTC').

Aufruf (Projekt-Root):
    .venv\\Scripts\\python.exe -X utf8 test/diag_phase_tragfaehigkeit.py
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.market_segmentation import (  # noqa: E402
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)

_MONATE: Tuple[Tuple[str, str, str], ...] = (
    ("MAI26", "2026-05-01", "2026-06-01"),
    ("JUN26", "2026-06-01", "2026-07-01"),
    ("JUL26", "2026-07-01", "2026-08-01"),
    ("AUG26", "2026-08-01", "2026-09-01"),
)

_HORIZONTE: Tuple[int, ...] = (48, 96)
_ATR_N: int = 20
_N_PERM: int = 20000
_RNG: np.random.Generator = np.random.default_rng(20260914)


def _atr(df: pd.DataFrame, n: int = _ATR_N) -> np.ndarray:
    """ATR-Proxy: rollierender Mittelwert der Bar-Spanne (high-low)."""
    spanne: np.ndarray = (df["high"] - df["low"]).to_numpy(dtype=float)
    return (
        pd.Series(spanne).rolling(n, min_periods=n).mean().to_numpy(dtype=float)
    )


def _phasen_statistik(
    df: pd.DataFrame, sr: SegmentResult, atr: np.ndarray
) -> pd.DataFrame:
    """Je Bruch-Phase: Laenge, Pivot-Zahl, Range in ATR, Expansion."""
    rows: List[Dict[str, float]] = []
    ts_arr: np.ndarray = df["ts"].values
    high: np.ndarray = df["high"].to_numpy(dtype=float)
    low: np.ndarray = df["low"].to_numpy(dtype=float)
    n: int = len(df)
    for p in sr.phases:
        if p.brk_idx is None or p.U_final is None or p.L_final is None:
            continue
        i0: int = int(np.searchsorted(ts_arr, np.datetime64(p.start), "left"))
        i1: int = int(p.brk_idx)
        if i1 <= i0:
            continue
        laenge: int = i1 - i0 + 1
        atr_med: float = float(np.nanmedian(atr[i0 : i1 + 1]))
        if not np.isfinite(atr_med) or atr_med <= 0.0:
            continue
        bal_range: float = float(p.U_final - p.L_final)
        # Move nach dem Bruch: bis Horizont-Ende oder Datenende
        j1: int = min(i1 + 1 + 96, n - 1)
        if j1 > i1:
            move_range: float = float(
                high[i1 + 1 : j1 + 1].max() - low[i1 + 1 : j1 + 1].min()
            )
        else:
            move_range = float("nan")
        rows.append(
            {
                "phase": len(rows) + 1,
                "laenge_bars": float(laenge),
                "n_h_pivots": float(len(p.h_prices)),
                "n_l_pivots": float(len(p.l_prices)),
                "n_pivots": float(len(p.h_prices) + len(p.l_prices)),
                "atr": atr_med,
                "bal_range": bal_range,
                "bal_range_atr": bal_range / atr_med,
                "move_range_atr": move_range / atr_med,
                "expansion": move_range / bal_range if bal_range > 0 else np.nan,
                "brk_dir": 1.0 if p.break_dir == "up" else -1.0,
                "brk_idx": float(i1),
            }
        )
    return pd.DataFrame(rows)


def _tightness_perzentil(
    df: pd.DataFrame, st: pd.DataFrame, atr: np.ndarray
) -> np.ndarray:
    """Perzentil des Phasen-Range gegen Zufallsfenster gleicher Laenge.

    Returns:
        Array der Perzentile (0..100). ~50 = nicht von Rauschen zu trennen.
    """
    high: np.ndarray = df["high"].to_numpy(dtype=float)
    low: np.ndarray = df["low"].to_numpy(dtype=float)
    n: int = len(df)
    out: List[float] = []
    for _, r in st.iterrows():
        L: int = int(r["laenge_bars"])
        if L + 1 >= n:
            out.append(float("nan"))
            continue
        # Null: Range ueber alle Fenster der Laenge L (vektorisiert)
        idx: int = 0
        starts: np.ndarray = np.arange(0, n - L)
        # rollierender max/min ueber Fenster [s, s+L-1]
        roll_max: np.ndarray = (
            pd.Series(high).rolling(L).max().to_numpy(dtype=float)
        )
        roll_min: np.ndarray = (
            pd.Series(low).rolling(L).min().to_numpy(dtype=float)
        )
        ranges: np.ndarray = roll_max - roll_min
        ranges = ranges[np.isfinite(ranges)]
        if len(ranges) == 0:
            out.append(float("nan"))
            continue
        pct: float = float((ranges < r["bal_range"]).mean() * 100.0)
        out.append(pct)
        del idx, starts
    return np.array(out, dtype=float)


def _follow_through(
    df: pd.DataFrame, st: pd.DataFrame, atr: np.ndarray, horizont: int
) -> Tuple[float, float, float]:
    """Vorwaerts-Ertrag nach Bruch vs. Zufallseinstieg (in ATR, richtungsneutral).

    Returns:
        (mean_r_breakout, mean_abs_random, p_wert_einseitig)
    """
    close: np.ndarray = df["close"].to_numpy(dtype=float)
    open_: np.ndarray = df["open"].to_numpy(dtype=float)
    n: int = len(df)
    r_b: List[float] = []
    for _, r in st.iterrows():
        b: int = int(r["brk_idx"])
        d: float = float(r["brk_dir"])
        e: int = b + 2  # Entry Open(trigger+1) konsistent zum Kern
        x: int = e + horizont
        if x >= n:
            continue
        a: float = float(atr[e])
        if not np.isfinite(a) or a <= 0.0:
            continue
        r_b.append(d * (close[x] - open_[e]) / a)
    r_break: np.ndarray = np.array(r_b, dtype=float)

    # Null: Zufallsbar + Zufallsrichtung, identisches Horizont-Fenster
    gueltig: np.ndarray = np.arange(_ATR_N + 1, n - horizont - 1)
    gueltig = gueltig[np.isfinite(atr[gueltig]) & (atr[gueltig] > 0.0)]
    if len(gueltig) == 0 or len(r_break) == 0:
        return float("nan"), float("nan"), float("nan")
    picks: np.ndarray = _RNG.choice(gueltig, size=_N_PERM, replace=True)
    dirs: np.ndarray = _RNG.choice([-1.0, 1.0], size=_N_PERM)
    null: np.ndarray = (
        dirs * (close[picks + horizont] - open_[picks]) / atr[picks]
    )
    mean_b: float = float(r_break.mean())
    p_wert: float = float((null >= mean_b).mean())
    return mean_b, float(np.abs(null).mean()), p_wert


def main() -> int:
    for symbol in ("SILVER", "Brent"):
        print("=" * 108)
        print(f"SYMBOL: {symbol} M15")
        print("=" * 108)
        alle_st: List[pd.DataFrame] = []
        for label, start, ende in _MONATE:
            cfg = replace(
                SegmentConfig(), symbol=symbol, timeframe="M15",
                start=start, ende=ende,
            )
            df = load_data(
                cfg.db_path, cfg.start, cfg.ende, cfg.symbol, cfg.timeframe
            )
            sr = segmentiere_markt(df, cfg)
            atr = _atr(df)
            st = _phasen_statistik(df, sr, atr)
            st["monat"] = label
            st["pct"] = _tightness_perzentil(df, st, atr)
            alle_st.append(st)
            n_brk = int(st.shape[0])
            print(
                f"  {label}: Bars={len(df):5d}  Phasen(ges.)={len(sr.phases):3d}  "
                f"Bruch-Phasen={n_brk:3d}"
            )
        st = pd.concat(alle_st, ignore_index=True)

        print()
        print("--- A) PHASEN-STRUKTUR (Bruch-Phasen, alle 4 Monate) ---")
        print(
            f"  n={len(st)}  Laenge [Bars]: median={st['laenge_bars'].median():.0f} "
            f"min={st['laenge_bars'].min():.0f} max={st['laenge_bars'].max():.0f}"
            f"  (= {st['laenge_bars'].median() * 15 / 60 / 24:.1f} Tage median)"
        )
        print(
            f"  Pivots je Phase: median={st['n_pivots'].median():.0f} "
            f"min={st['n_pivots'].min():.0f} max={st['n_pivots'].max():.0f}"
            f"  | davon H median={st['n_h_pivots'].median():.0f}"
            f" L median={st['n_l_pivots'].median():.0f}"
        )
        print(
            f"  Balance-Range: median={st['bal_range_atr'].median():.2f} ATR "
            f"(min={st['bal_range_atr'].min():.2f}, max={st['bal_range_atr'].max():.2f})"
        )

        print()
        print("--- B) TIGHTNESS: ist die 'Balance' enger als Zufall? ---")
        pct = st["pct"].dropna()
        print(
            f"  Range-Perzentil gegen Zufallsfenster gleicher Laenge: "
            f"median={pct.median():.1f}%  mean={pct.mean():.1f}%"
        )
        print(
            f"  Anteil Phasen, die enger sind als 75% aller Zufallsfenster: "
            f"{(pct < 25.0).mean() * 100:.1f}%  "
            f"(enger als 50%: {(pct < 50.0).mean() * 100:.1f}%)"
        )
        print("  => Perzentil ~50% bedeutet: nicht von Rauschen unterscheidbar.")

        print()
        print("--- C) EXPANSION: Move nach dem Bruch / Balance-Range ---")
        exp_ = st["expansion"].replace([np.inf, -np.inf], np.nan).dropna()
        print(
            f"  Verhaeltnis: median={exp_.median():.2f}  mean={exp_.mean():.2f}  "
            f"Anteil <1.0: {(exp_ < 1.0).mean() * 100:.1f}%"
        )
        print("  => ~1.0 bedeutet: der 'Ausbruch' expandiert nicht.")

        print()
        print("--- D) FOLLOW-THROUGH: Bruch vs. Zufallseinstieg (ATR-normiert) ---")
        for h in _HORIZONTE:
            mb, mabs, pw = _follow_through(df, st, atr, h)
            print(
                f"  N={h:3d}: mean Bruch={mb:+.3f} ATR   "
                f"|Zufall|={mabs:.3f} ATR   p(einseitig)={pw:.3f}"
            )
        print("  => p<0.05 waere ein Signal; p~0.5 = kein Informationsgehalt.")
        print()

    st.to_csv(
        _ROOT / "test" / "setup_c" / "diag_phasen_struktur.csv",
        index=False,
        encoding="utf-8",
    )
    print("CSV: test/setup_c/diag_phasen_struktur.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
