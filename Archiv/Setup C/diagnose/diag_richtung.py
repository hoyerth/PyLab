"""Wegwerf-Diagnose v4: Ist die RICHTUNG nach Kompression vorhersagbar?

Befundlage bis hierher:
  v2 (fair): UNSER Detektor erzeugt Phasen, die NICHT enger sind als
             Zufallsfenster (Perzentil ~46-49%) -> Balance wird nicht erkannt.
  v3:        Der MARKT hat die Struktur aber sehr wohl: Spearman
             (compression, expansion) ~ -0.24..-0.32, in ALLEN 8 Monat x
             Symbol-Zellen mit gleichem Vorzeichen, engste 10% -> +1.7..+3.5
             ATR mehr Expansion (p<0.001).
             => Kompression sagt die GROESSE, nicht die RICHTUNG.

v4 isoliert die entscheidende Frage: Ist die Richtung ueberhaupt
vorhersagbar, wenn man einen PERFEKTEN Kompressions-Detektor unterstellt
(d. h. voellig unabhaengig von unserer Segmentierung)?

Getestete Richtungsregeln nach Kompressions-Eintritt (engste 10-20%):
  MOM   Richtung = Vorzeichen des letzten Bar-Returns
  ANTI  Richtung = Gegenrichtung (Mean-Reversion)
  DRIFT Richtung = Vorzeichen des Drifts der letzten 20 Bars
Jeweils Vorwaerts-Ertrag (Open t+1 -> Close t+H), ATR-normiert, SIGNED.
Verglichen gegen das unbedingte Null-Drift derselben Bars (Permutation).

Zeitbasis: BKZ ueber ``load_data`` (time AT TIME ZONE 'UTC').

Aufruf (Projekt-Root):
    .venv\\Scripts\\python.exe -X utf8 test/diag_richtung.py
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

from scripts.market_segmentation import SegmentConfig, load_data  # noqa: E402

_MONATE: Tuple[Tuple[str, str, str], ...] = (
    ("MAI26", "2026-05-01", "2026-06-01"),
    ("JUN26", "2026-06-01", "2026-07-01"),
    ("JUL26", "2026-07-01", "2026-08-01"),
    ("AUG26", "2026-08-01", "2026-09-01"),
)
_RV_KURZ, _RV_LANG, _ATR_N = 10, 96, 20
_HORIZONTE: Tuple[int, ...] = (48, 96)
_QUANTILE: float = 0.10


def _merkmale(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"].astype(float)
    logret = np.log(close).diff()
    rv_k = logret.rolling(_RV_KURZ, min_periods=_RV_KURZ).std()
    rv_l = logret.rolling(_RV_LANG, min_periods=_RV_LANG).std()
    atr = (df["high"] - df["low"]).astype(float).rolling(
        _ATR_N, min_periods=_ATR_N
    ).mean()
    return pd.DataFrame(
        {
            "compression": rv_k / rv_l,
            "atr": atr,
            "close": close,
            "open": df["open"].astype(float),
            "ret1": close.diff(),
            "drift20": close.diff(20),
        }
    )


def _vorwaerts(m: pd.DataFrame, h: int) -> pd.Series:
    """(close[t+h] - open[t+1]) / atr[t]  (Einstieg am Open der Folge-Bar)."""
    return (m["close"].shift(-h) - m["open"].shift(-1)) / m["atr"]


def main() -> int:
    for symbol in ("SILVER", "Brent"):
        print("=" * 104)
        print(f"SYMBOL: {symbol} M15")
        print("=" * 104)
        teile: List[pd.DataFrame] = []
        for label, start, ende in _MONATE:
            cfg = replace(
                SegmentConfig(), symbol=symbol, timeframe="M15",
                start=start, ende=ende,
            )
            df = load_data(
                cfg.db_path, cfg.start, cfg.ende, cfg.symbol, cfg.timeframe
            )
            m = _merkmale(df)
            m["monat"] = label
            teile.append(m)
            del df
        mm = pd.concat(teile, ignore_index=True).replace(
            [np.inf, -np.inf], np.nan
        )

        for h in _HORIZONTE:
            sub = mm.dropna(
                subset=["compression", "ret1", "drift20", f"atr"]
            ).copy()
            sub["fwd"] = _vorwaerts(sub, h)
            sub = sub.dropna(subset=["fwd"])
            thr = float(sub["compression"].quantile(_QUANTILE))
            eng = sub[sub["compression"] <= thr]
            print()
            print(
                f"--- N={h} | Kompressions-Eintritte (engste {_QUANTILE:.0%}): "
                f"n={len(eng)} von {len(sub)} ---"
            )
            # Richtungsregeln
            regeln: Dict[str, np.ndarray] = {
                "MOM  ": np.where(eng["ret1"].to_numpy() >= 0, 1.0, -1.0),
                "ANTI ": np.where(eng["ret1"].to_numpy() >= 0, -1.0, 1.0),
                "DRIFT": np.where(eng["drift20"].to_numpy() >= 0, 1.0, -1.0),
            }
            fwd = eng["fwd"].to_numpy(dtype=float)
            rng = np.random.default_rng(20260914)
            for name, sgn in regeln.items():
                r = sgn * fwd
                se = float(r.std(ddof=1) / np.sqrt(len(r)))
                t = float(r.mean() / se) if se > 0 else float("nan")
                # Null: gleiche (Bar, H)-Fenster, Zufallsrichtung
                draws = np.array(
                    [float((rng.choice([-1.0, 1.0], size=len(r)) * fwd).mean())
                     for _ in range(2000)]
                )
                p = float((draws >= r.mean()).mean())
                print(
                    f"  {name}: mean={r.mean():+7.3f} ATR  median={np.median(r):+7.3f}"
                    f"  t={t:+5.2f}  p(einseitig)={p:.3f}"
                )
            # Unbedingter Drift derselben Monate (Referenz)
            allfwd = sub["fwd"].to_numpy(dtype=float)
            print(
                f"  REF (unbedingt, alle Bars): mean={allfwd.mean():+7.3f} ATR  "
                f"sd={allfwd.std():.2f}"
            )

        print()
        print("--- Monats-Breakdown MOM-Regel, N=96 (Stabilitaet?) ---")
        for label, start, ende in _MONATE:
            cfg = replace(
                SegmentConfig(), symbol=symbol, timeframe="M15",
                start=start, ende=ende,
            )
            df = load_data(
                cfg.db_path, cfg.start, cfg.ende, cfg.symbol, cfg.timeframe
            )
            m = _merkmale(df)
            m["fwd"] = _vorwaerts(m, 96)
            m = m.dropna(subset=["compression", "ret1", "fwd"])
            thr = float(m["compression"].quantile(_QUANTILE))
            e = m[m["compression"] <= thr]
            if e.empty:
                continue
            s = np.where(e["ret1"].to_numpy() >= 0, 1.0, -1.0)
            r = s * e["fwd"].to_numpy(dtype=float)
            print(
                f"  {label}: n={len(r):3d}  MOM mean={r.mean():+7.3f} ATR  "
                f"Winrate={(r > 0).mean() * 100:5.1f}%"
            )
            del df
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
