"""Wegwerf-Diagnose v3: Gibt es die Balance->Expansion-Struktur ueberhaupt?

v2 hat gezeigt: UNSERE Software erzeugt keine Phasen, die enger sind als
Zufallsfenster (faire Tightness-Perzentile ~46-49%). Das ist ein Detektor-
Befund. v3 stellt die tiefere, detektor-UNABHAENGIGE Frage:

    Existiert in SILVER/Brent M15 ueberhaupt eine verwertbare
    Kompression -> Expansion-Beziehung, die ein PERFEKTER Detektor
    ausnutzen koennte?

Definition hier bewusst NICHT ueber unsere Segmentierung, sondern rein
vektorisiert ueber realisierte Volatilitaet:

    compression(t) = rv_kurz(t) / rv_lang(t)      (rv = std der Log-Renditen)
    expansion(t)   = (max(high)-min(low)) ueber t+1..t+H  /  ATR(t)

Getestet:
  1) Quintil-Analyse: steigt die Expansion monoton mit abnehmender
     Compression? (Praemisse: eng -> weiter)
  2) Rangkorrelation compression vs. expansion.
  3) Dynamik: folgt auf die ENGSTEN 10% der Bars eine groessere Expansion
     als auf den Rest? (einseitiger Permutationstest)
  4) Kausalitaets-Check der Praemisse: ist der Effekt (falls vorhanden)
     gross genug, um nach Kosten/Stop ueberhaupt handelbar zu sein?

Zeitbasis: BKZ ueber ``load_data`` (time AT TIME ZONE 'UTC').

Aufruf (Projekt-Root):
    .venv\\Scripts\\python.exe -X utf8 test/diag_balance_struktur.py
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
_RV_KURZ: int = 10
_RV_LANG: int = 96
_ATR_N: int = 20
_HORIZONTE: Tuple[int, ...] = (48, 96)


def _merkmale(df: pd.DataFrame) -> pd.DataFrame:
    """Compression und Expansion je Bar (rein vektorisiert, kausal)."""
    close: pd.Series = df["close"].astype(float)
    logret: pd.Series = np.log(close).diff()
    rv_k: pd.Series = logret.rolling(_RV_KURZ, min_periods=_RV_KURZ).std()
    rv_l: pd.Series = logret.rolling(_RV_LANG, min_periods=_RV_LANG).std()
    compression: pd.Series = rv_k / rv_l
    spanne: pd.Series = (df["high"] - df["low"]).astype(float)
    atr: pd.Series = spanne.rolling(_ATR_N, min_periods=_ATR_N).mean()
    out = pd.DataFrame(
        {"compression": compression, "atr": atr, "close": close}
    )
    # Expansion: Range der NAECHSTEN H Bars, ATR-normiert
    high = pd.Series(df["high"].astype(float))
    low = pd.Series(df["low"].astype(float))
    for h in _HORIZONTE:
        fmax = high.shift(-1).rolling(h, min_periods=h).max().shift(-(h - 1))
        fmin = low.shift(-1).rolling(h, min_periods=h).min().shift(-(h - 1))
        out[f"exp_{h}"] = (fmax - fmin) / atr
    return out


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
        mm = pd.concat(teile, ignore_index=True)
        mm = mm.replace([np.inf, -np.inf], np.nan)
        print(f"  Rohbars: {len(mm)} (je Test sauber gefiltert)")

        print()
        print("--- 1) QUINTILE: Compression (eng->weit) vs. Expansion ---")
        for h in _HORIZONTE:
            sub = mm.dropna(subset=["compression", f"exp_{h}"])
            q = pd.qcut(sub["compression"], 5, labels=False)
            grp = sub.groupby(q)[f"exp_{h}"].mean()
            eng, weit = float(grp.loc[0]), float(grp.loc[4])
            print(
                f"  N={h:3d}: n={len(sub):5d} | Q1(engste Vol)={eng:6.2f} ATR | "
                f"Q2={grp.loc[1]:6.2f} Q3={grp.loc[2]:6.2f} "
                f"Q4={grp.loc[3]:6.2f} | Q5(weiteste)={weit:6.2f} ATR"
            )
            print(
                f"          Verhaeltnis Q1/Q5 = {eng / weit:.3f}  "
                f"(>1 = eng fuehrt zu weiter)   "
                f"Spearman(compression, exp) = "
                f"{sub['compression'].corr(sub[f'exp_{h}'], method='spearman'):+.3f}"
            )

        print()
        print("--- 2) EXTREMGRUPPE: engste 10% vs. Rest (Permutationstest) ---")
        rng = np.random.default_rng(20260914)
        for h in _HORIZONTE:
            sub = mm.dropna(subset=["compression", f"exp_{h}"])
            thr = float(sub["compression"].quantile(0.10))
            alle = sub[f"exp_{h}"].to_numpy(dtype=float)
            mask = (sub["compression"] <= thr).to_numpy()
            eng_v, rest_v = alle[mask], alle[~mask]
            n_e = len(eng_v)
            draws = np.array(
                [alle[rng.permutation(len(alle))[:n_e]].mean() for _ in range(2000)]
            )
            p = float((draws >= eng_v.mean()).mean())
            print(
                f"  N={h:3d}: engste10% mean={eng_v.mean():6.2f} ATR (n={n_e}) | "
                f"Rest mean={rest_v.mean():6.2f} ATR (n={len(rest_v)}) | "
                f"Diff={eng_v.mean() - rest_v.mean():+.2f} ATR | p={p:.3f}"
            )

        print()
        print("--- 3) STABILITAET ueber die Monate (Spearman comp/exp) ---")
        for h in _HORIZONTE:
            print(f"  N={h:3d}:", end="")
            for label, _, _ in _MONATE:
                sub = mm[mm["monat"] == label].dropna(
                    subset=["compression", f"exp_{h}"]
                )
                if len(sub) < 50:
                    print(f"   {label}=n/a", end="")
                    continue
                c = sub["compression"].corr(sub[f"exp_{h}"], method="spearman")
                print(f"   {label}={c:+.3f}", end="")
            print()

        print()
        print("--- 4) VERWERTBARKEIT: Expansion der engsten 10% ---")
        for h in _HORIZONTE:
            sub = mm.dropna(subset=["compression", f"exp_{h}"])
            thr = float(sub["compression"].quantile(0.10))
            eng_v = sub.loc[sub["compression"] <= thr, f"exp_{h}"].to_numpy(float)
            print(
                f"  N={h:3d}: median={np.median(eng_v):.2f} ATR  "
                f"mean={eng_v.mean():.2f} ATR  "
                f"25%-Quantil={np.percentile(eng_v, 25):.2f} ATR"
            )
        print("  (Ein Trade braucht >1R Brutto, um nach Stop zu tragen.)")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
