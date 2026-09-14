# -*- coding: utf-8 -*-
"""READ-ONLY: Bar -> Zeit-Mapping (Dreispaltig) fuer die Mentor-Darstellung."""
from __future__ import annotations

import duckdb

con = duckdb.connect("data/market_data.duckdb", read_only=True)
d = con.execute(
    """
    SELECT time AT TIME ZONE 'UTC'     AS bar_utc,
           time AT TIME ZONE 'Europe/Berlin' AS bar_anzeige,
           high, low
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= DATE '2026-08-10'
      AND time AT TIME ZONE 'UTC' <  DATE '2026-08-28'
    ORDER BY time
    """
).fetchdf()
con.close()
print("Bars:", len(d))
print(f"{'Bar':>4} | {'Broker/UTC':<19} | {'Bar-Zeit (+02:00)':<19} | H | L")
for b in (1020, 1021, 1023, 1024, 1031, 1075, 1122, 1171, 1200, 1272, 1287):
    r = d.iloc[b]
    print(f"{b:>4} | {str(r['bar_utc']):<19} | {str(r['bar_anzeige']):<19} | "
          f"{r['high']:.4f} | {r['low']:.4f}")
