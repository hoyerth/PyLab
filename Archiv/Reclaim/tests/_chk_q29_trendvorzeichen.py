# -*- coding: utf-8 -*-
"""READ-ONLY: Q29 unter Trend-Vorzeichen -- Analyse + empirischer Beweis.

These des Anwenders: Im baerischen Trend kehrt sich das Ungleichgewicht um
(LONG passiert, SHORT gesperrt) -- dieselbe Mechanik, nur gespiegelt.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
pd.set_option("display.width", 220)

con = duckdb.connect(str(ROOT / "data" / "market_data.duckdb"), read_only=True)
mn, mx, n = con.execute(
    "SELECT min(time), max(time), count(*) FROM ohlcv_bars "
    "WHERE symbol='SILVER' AND timeframe='M15'").fetchone()
print(f"M15-Range: {mn} .. {mx}  n={n}")

df = con.execute(
    "SELECT date_trunc('month', time AT TIME ZONE 'UTC') AS mon, "
    "first(close ORDER BY time) AS o, last(close ORDER BY time) AS c, "
    "min(low) AS lo, max(high) AS hi, count(*) AS n "
    "FROM ohlcv_bars WHERE symbol='SILVER' AND timeframe='M15' "
    "GROUP BY 1 ORDER BY 1").fetchdf()
df["chg%"] = ((df.c - df.o) / df.o * 100).round(2)
df["range"] = (df.hi - df.lo).round(2)
print(df.to_string())
con.close()

print("=" * 74)
print("ANALYTISCHER BEWEIS (Vorzeichen-Symmetrie der Q29-Formel)")
print("=" * 74)
print("  dist_SHORT(k) = (ex_hi - hi[k]) / (ex_hi - ex_lo) * 100")
print("  dist_LONG(k)  = (lo[k] - ex_lo) / (ex_hi - ex_lo) * 100")
print("  ex_hi = max(hi[:k+1])  [frisch im Up-Trend]")
print("  ex_lo = min(lo[:k+1])  [frisch im Down-Trend]")
print()
print("  UP-Trend:   ex_hi frisch -> dist_SHORT klein -> SHORT passiert")
print("              ex_lo veraltet -> dist_LONG gross  -> LONG  gesperrt")
print("  DOWN-Trend: ex_lo frisch -> dist_LONG klein  -> LONG  passiert")
print("              ex_hi veraltet -> dist_SHORT gross -> SHORT gesperrt")
print()
print("  => Q29 ist KEIN Long-Blocker, sondern ein ANTITREND-Filter:")
print("     es handelt IMMER gegen den laufenden Trend (am Range-Extrem).")
print("=" * 74)
