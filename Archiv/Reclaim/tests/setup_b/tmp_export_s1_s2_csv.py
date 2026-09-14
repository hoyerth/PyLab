# -*- coding: utf-8 -*-
"""Exportiert SILVER M15-Referenz-Marktdaten (OHLC + tick_volume) fuer die
Baseline-Fenster S1 und S2 als CSV nach test/archiv/.

Query = bitgenau identisch mit `load_data()` in scripts/phasen_volumen_profil.py
(Z. 324-331): `time AT TIME ZONE 'UTC'` (Wanduhr-Garantie, keine lokale
Umrechnung), ohlcv_bars, symbol='SILVER', timeframe='M15', halboffenes Fenster
[date, date), ORDER BY time, danach tz_normalisiert (ts ohne tz, wie df im Skript).

Fenster:
  - S1: 2026-02-05 .. 2026-08-28  (stats_trades_MAKRO_S1.txt, 201 Baseline-Trades)
  - S2: 2025-01-01 .. 2025-12-01  (stats_trades_MAKRO_S2.txt, 210 Baseline-Trades)
Ausgabe (Konvention wie bestehende AUG-CSV):
  - test/archiv/silver_m15_ohlc_2026-02-05_2026-08-28.csv
  - test/archiv/silver_m15_ohlc_2025-01-01_2025-12-01.csv
Reine Lese-Extraktion (duckdb read_only), kein Produktivcode.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

DB = Path("data/market_data.duckdb")
OUT_DIR = Path("test/archiv")
FENSTER = [
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]


def load_data(db_path: Path, start: str, ende: str) -> pd.DataFrame:
    """Bitgenaue Kopie von load_data() (scripts/phasen_volumen_profil.py Z. 320-335)."""
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB-Datei nicht gefunden: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    d = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
    con.close()
    d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    return d


def main() -> None:
    for label, start, ende in FENSTER:
        df = load_data(DB, start, ende)
        out = OUT_DIR / f"silver_m15_ohlc_{start}_{ende}.csv"
        df.to_csv(out, index=False, date_format="%Y-%m-%d %H:%M:%S")
        # Kurz-Validierung
        t0, t1 = df["ts"].iloc[0], df["ts"].iloc[-1]
        n = len(df)
        nan_cols = [c for c in ["open", "high", "low", "close", "tick_volume"]
                    if int(df[c].isna().sum()) > 0]
        mono = bool(df["ts"].is_monotonic_increasing)
        print(f"[{label}] {start}..{ende}: {n} Bars | {t0:%Y-%m-%d %H:%M} .. "
              f"{t1:%Y-%m-%d %H:%M} | ts-monoton {mono} | NaN-Spalten {nan_cols or 'keine'}")
        print(f"        -> {out} ({round(out.stat().st_size/1024,1)} KB)")
        assert mono and not nan_cols and n > 0


if __name__ == "__main__":
    main()
