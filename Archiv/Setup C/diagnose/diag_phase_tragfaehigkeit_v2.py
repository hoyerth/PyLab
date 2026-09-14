"""Wegwerf-Diagnose v2: Fairer Tightness-Test + sauberer Follow-Through-Null.

Korrigiert zwei methodische Fehler aus v1:

  (1) TIGHTNESS war voreingenommen. v1 verglich den DICHTE-LINIEN-Range
      (U_final-L_final, liegt INNERHALB der Extreme) gegen den rohen
      max-min-Range eines Zufallsfensters. Das ist fast tautologisch.
      v2 vergleicht Aepfel mit Aepfeln: roher max(high)-min(low) des
      Phasenfensters gegen Zufallsfenster gleicher Laenge.

  (2) FOLLOW-THROUGH-Null war missverstaendlich ausgewiesen (mean|Null|
      gegen mean signed Bruch). v2 zeigt den signed-Null (per Symmetrie ~0)
      samt Standardfehler und t-Statistik.

Ergaenzt: absolute Schwellen vs. ATR (Skalierungs-Befund), Monats-Breakdown.

Aufruf (Projekt-Root):
    .venv\\Scripts\\python.exe -X utf8 test/diag_phase_tragfaehigkeit_v2.py
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


def _atr(df: pd.DataFrame, n: int = _ATR_N) -> np.ndarray:
    spanne: np.ndarray = (df["high"] - df["low"]).to_numpy(dtype=float)
    return pd.Series(spanne).rolling(n, min_periods=n).mean().to_numpy(dtype=float)


def _phasen(df, sr, atr, label: str) -> pd.DataFrame:
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
        L: int = i1 - i0 + 1
        atr_med: float = float(np.nanmedian(atr[i0 : i1 + 1]))
        if not np.isfinite(atr_med) or atr_med <= 0.0:
            continue
        j1: int = min(i1 + 1 + 96, n - 1)
        move_range: float = (
            float(high[i1 + 1 : j1 + 1].max() - low[i1 + 1 : j1 + 1].min())
            if j1 > i1
            else np.nan
        )
        rows.append(
            {
                "monat": label,
                "laenge_bars": float(L),
                "n_pivots": float(len(p.h_prices) + len(p.l_prices)),
                "atr_abs": atr_med,
                # FAIR: roher Range des Phasenfensters (Aepfel mit Aepfeln)
                "raw_range": float(high[i0 : i1 + 1].max() - low[i0 : i1 + 1].min()),
                "raw_range_atr": float(
                    (high[i0 : i1 + 1].max() - low[i0 : i1 + 1].min()) / atr_med
                ),
                "bal_range": float(p.U_final - p.L_final),
                "bal_range_atr": float((p.U_final - p.L_final) / atr_med),
                "move_range_atr": move_range / atr_med,
                "brk_dir": 1.0 if p.break_dir == "up" else -1.0,
                "brk_idx": float(i1),
                "start_idx": float(i0),
            }
        )
    return pd.DataFrame(rows)


def _fair_tightness(df: pd.DataFrame, st: pd.DataFrame) -> np.ndarray:
    """Perzentil des ROHEN Phasen-Range gegen Zufallsfenster gleicher Laenge."""
    high: np.ndarray = df["high"].to_numpy(dtype=float)
    low: np.ndarray = df["low"].to_numpy(dtype=float)
    n: int = len(df)
    roll_max: np.ndarray = pd.Series(high).rolling(1).max().to_numpy(dtype=float)
    roll_min: np.ndarray = pd.Series(low).rolling(1).min().to_numpy(dtype=float)
    out: List[float] = []
    for _, r in st.iterrows():
        L: int = int(r["laenge_bars"])
        if L >= n:
            out.append(float("nan"))
            continue
        rm: np.ndarray = (
            pd.Series(high).rolling(L).max().to_numpy(dtype=float)
            - pd.Series(low).rolling(L).min().to_numpy(dtype=float)
        )
        rm = rm[np.isfinite(rm)]
        if len(rm) == 0:
            out.append(float("nan"))
            continue
        out.append(float((rm < r["raw_range"]).mean() * 100.0))
    del roll_max, roll_min
    return np.array(out, dtype=float)


def _follow_through(
    df: pd.DataFrame, st: pd.DataFrame, atr: np.ndarray, h: int
) -> Dict[str, float]:
    close: np.ndarray = df["close"].to_numpy(dtype=float)
    open_: np.ndarray = df["open"].to_numpy(dtype=float)
    n: int = len(df)
    rs: List[float] = []
    for _, r in st.iterrows():
        b: int = int(r["brk_idx"])
        e: int = b + 2
        x: int = e + h
        if x >= n:
            continue
        a: float = float(atr[e])
        if not np.isfinite(a) or a <= 0.0:
            continue
        rs.append(float(r["brk_dir"]) * (close[x] - open_[e]) / a)
    rb: np.ndarray = np.array(rs, dtype=float)
    if len(rb) == 0:
        return {"n": 0.0}
    # Signed-Null: dieselben (Bar, Horizont)-Fenster, Richtung zufaellig
    gueltig: np.ndarray = np.arange(_ATR_N + 1, n - h - 1)
    gueltig = gueltig[np.isfinite(atr[gueltig]) & (atr[gueltig] > 0.0)]
    rng = np.random.default_rng(20260914)
    picks: np.ndarray = rng.choice(gueltig, size=_N_PERM, replace=True)
    dirs: np.ndarray = rng.choice([-1.0, 1.0], size=_N_PERM)
    null: np.ndarray = dirs * (close[picks + h] - open_[picks]) / atr[picks]
    se: float = float(rb.std(ddof=1) / np.sqrt(len(rb))) if len(rb) > 1 else np.nan
    return {
        "n": float(len(rb)),
        "mean_brk": float(rb.mean()),
        "median_brk": float(np.median(rb)),
        "se": se,
        "t": float(rb.mean() / se) if se and np.isfinite(se) and se > 0 else np.nan,
        "p": float((null >= rb.mean()).mean()),
        "null_mean": float(null.mean()),
        "null_sd": float(null.std()),
    }


def main() -> int:
    gesamt: List[pd.DataFrame] = []
    for symbol in ("SILVER", "Brent"):
        print("=" * 108)
        print(f"SYMBOL: {symbol} M15")
        print("=" * 108)
        teile: List[pd.DataFrame] = []
        atr_by_monat: Dict[str, float] = {}
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
            st = _phasen(df, sr, atr, label)
            if st.empty:
                continue
            st["pct_fair"] = _fair_tightness(df, st)
            teile.append(st)
            atr_by_monat[label] = float(np.nanmedian(atr))
        st = pd.concat(teile, ignore_index=True)
        st["symbol"] = symbol
        gesamt.append(st)

        tol: float = 0.34
        atr_med: float = st["atr_abs"].median()
        print()
        print("--- SKALIERUNG: absolute Schwellen vs. ATR ---")
        print(
            f"  ATR(20) absolut: median={atr_med:.4f}   "
            f"| TOL=0.34 entspricht {tol / atr_med:.2f} ATR   "
            f"| density_band=0.15 = {0.15 / atr_med:.2f} ATR"
        )
        print(
            f"  Median-Preisniveau (close): "
            f"{st['raw_range'].median():.3f} Range-Einheit (Symbol-Einheiten)"
        )

        print()
        print("--- B*) FAIRER TIGHTNESS-Test: roher Phasen-Range vs. Zufall ---")
        pf = st["pct_fair"].dropna()
        print(
            f"  Perzentil: median={pf.median():.1f}%  mean={pf.mean():.1f}%"
        )
        print(
            f"  Anteil Phasen mit Range < 50% aller Zufallsfenster: "
            f"{(pf < 50.0).mean() * 100:.1f}%   (< 25%: {(pf < 25.0).mean() * 100:.1f}%)"
        )

        print()
        print("--- C) EXPANSION (unveraendert) ---")
        exp_ = (st["move_range_atr"] / st["bal_range_atr"]).replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        print(f"  Move-Range/Balance-Range: median={exp_.median():.2f}")

        print()
        print("--- D) FOLLOW-THROUGH mit sauberem Null ---")
        for h in _HORIZONTE:
            rr = _pooled_follow_through(symbol, st, h)
            print(
                f"  N={h:3d}: n={int(rr['n']):3d}  mean Bruch={rr['mean_brk']:+.3f} ATR  "
                f"(median={rr['median_brk']:+.3f})  t={rr['t']:+.2f}  "
                f"p={rr['p']:.3f}  |  Null mean={rr['null_mean']:+.3f} sd={rr['null_sd']:.2f}"
            )
        print()
        print("  Monats-Breakdown (mean Bruch je N, ATR-normiert):")
        for label, start, ende in _MONATE:
            sm = st[st["monat"] == label]
            if sm.empty:
                continue
            cfg = replace(
                SegmentConfig(), symbol=symbol, timeframe="M15",
                start=start, ende=ende,
            )
            dfm = load_data(
                cfg.db_path, cfg.start, cfg.ende, cfg.symbol, cfg.timeframe
            )
            atm = _atr(dfm)
            zeile: str = f"    {label}: "
            for h in _HORIZONTE:
                r = _ft_ein_df(dfm, sm, atm, h)
                zeile += f"N{h}={r[0]:+.3f} (n={r[1]:2d})  "
            print(zeile)
        print()

    pd.concat(gesamt, ignore_index=True).to_csv(
        _ROOT / "test" / "setup_c" / "diag_phasen_struktur_v2.csv",
        index=False, encoding="utf-8",
    )
    print("CSV: test/setup_c/diag_phasen_struktur_v2.csv")
    return 0


def _ft_ein_df(df, st, atr, h) -> Tuple[float, int]:
    close: np.ndarray = df["close"].to_numpy(dtype=float)
    open_: np.ndarray = df["open"].to_numpy(dtype=float)
    n: int = len(df)
    rs: List[float] = []
    for _, r in st.iterrows():
        b, e, x = int(r["brk_idx"]), int(r["brk_idx"]) + 2, int(r["brk_idx"]) + 2 + h
        if x >= n:
            continue
        a = float(atr[e])
        if not np.isfinite(a) or a <= 0.0:
            continue
        rs.append(float(r["brk_dir"]) * (close[x] - open_[e]) / a)
    arr = np.array(rs, dtype=float)
    return (float(arr.mean()) if len(arr) else float("nan"), int(len(arr)))


def _pooled_follow_through(symbol: str, st: pd.DataFrame, h: int) -> Dict[str, float]:
    """Follow-Through gepoolt ueber alle Monate, mit echtem Permutationstest.

    Null: ALLE Bars (aus allen Monaten), Zufallsrichtung, identisches
    Horizont-Fenster, ATR-normiert. Der p-Wert ist der Anteil der
    Null-Ziehungen >= dem beobachteten Bruch-Mittel.
    """
    alle: List[float] = []
    null_pool: List[np.ndarray] = []
    rng = np.random.default_rng(20260914)
    for label, start, ende in _MONATE:
        sm = st[st["monat"] == label]
        cfg = replace(
            SegmentConfig(), symbol=symbol, timeframe="M15", start=start, ende=ende
        )
        dfm = load_data(cfg.db_path, cfg.start, cfg.ende, cfg.symbol, cfg.timeframe)
        atm = _atr(dfm)
        close = dfm["close"].to_numpy(dtype=float)
        open_ = dfm["open"].to_numpy(dtype=float)
        n = len(dfm)
        # Beobachtung: Bruch-Einstiege dieses Monats
        for _, r in sm.iterrows():
            e, x = int(r["brk_idx"]) + 2, int(r["brk_idx"]) + 2 + h
            if x >= n:
                continue
            a = float(atm[e])
            if not np.isfinite(a) or a <= 0.0:
                continue
            alle.append(float(r["brk_dir"]) * (close[x] - open_[e]) / a)
        # Null: alle gueltigen Bars, Zufallsrichtung
        g = np.arange(_ATR_N + 1, n - h - 1)
        g = g[np.isfinite(atm[g]) & (atm[g] > 0.0)]
        if len(g) == 0:
            continue
        dirs = rng.choice([-1.0, 1.0], size=len(g))
        null_pool.append(dirs * (close[g + h] - open_[g]) / atm[g])
    rb = np.array(alle, dtype=float)
    if len(rb) == 0 or not null_pool:
        return {"n": 0.0, "mean_brk": np.nan, "median_brk": np.nan,
                "t": np.nan, "p": np.nan, "null_mean": np.nan, "null_sd": np.nan}
    se = float(rb.std(ddof=1) / np.sqrt(len(rb)))
    null_all = np.concatenate(null_pool)
    return {
        "n": float(len(rb)),
        "mean_brk": float(rb.mean()),
        "median_brk": float(np.median(rb)),
        "t": float(rb.mean() / se) if se > 0 else np.nan,
        "p": float((null_all >= rb.mean()).mean()),
        "null_mean": float(null_all.mean()),
        "null_sd": float(null_all.std()),
    }


if __name__ == "__main__":
    raise SystemExit(main())
