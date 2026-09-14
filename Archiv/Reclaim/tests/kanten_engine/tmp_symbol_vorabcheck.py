"""Vorab-Check: SYMBOL M15 Verfuegbarkeit + Preisstruktur je Fenster (AUG/S1/S2).

Rein lesend auf data/market_data.duckdb. Generisch: --symbol=Cocoa (Default).
"""
from __future__ import annotations

import sys

import duckdb
import pandas as pd

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "Cocoa"
DB = r"data/market_data.duckdb"
FENSTER = {
    "AUG": ("2026-08-10", "2026-08-28"),
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

con = duckdb.connect(DB, read_only=True)

print(f"=== {SYMBOL} M15 je Fenster: Preisstruktur ===")
rows = []
for name, (a, b) in FENSTER.items():
    r = con.execute(
        f"""
        SELECT count(*) AS n,
               min(close) AS cmin, max(close) AS cmax,
               min(low) AS lmin, max(high) AS hmax,
               avg(close) AS cavg,
               avg(high-low) AS range_avg,
               median(high-low) AS range_med,
               stddev(close) AS cstd,
               count(*) FILTER (WHERE tick_volume > 0) AS n_tv,
               avg(tick_volume) AS tv_avg
        FROM ohlcv_bars
        WHERE symbol='{SYMBOL}' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{a}'
          AND time AT TIME ZONE 'UTC' <  DATE '{b}'
        """
    ).fetchdf().to_dict("records")[0]
    r["fenster"] = name
    rows.append(r)
print(pd.DataFrame(rows).to_string(index=False))

print(f"\n=== ATR-Referenz (M15) je Fenster: {SYMBOL} vs SILVER ===")
print(
    con.execute(
        """
        WITH x AS (
          SELECT symbol,
                 CASE
                   WHEN time AT TIME ZONE 'UTC' >= DATE '2026-08-10'
                        AND time AT TIME ZONE 'UTC' < DATE '2026-08-28' THEN 'AUG'
                   WHEN time AT TIME ZONE 'UTC' >= DATE '2026-02-05'
                        AND time AT TIME ZONE 'UTC' < DATE '2026-08-28' THEN 'S1'
                   WHEN time AT TIME ZONE 'UTC' >= DATE '2025-01-01'
                        AND time AT TIME ZONE 'UTC' < DATE '2025-12-01' THEN 'S2'
                   ELSE 'X' END AS fenster,
                 high, low, close
          FROM ohlcv_bars
          WHERE timeframe='M15' AND symbol IN ('SILVER', ?)
        )
        SELECT symbol, fenster, count(*) AS n,
               avg(high-low) AS range_avg, median(high-low) AS range_med,
               avg(close) AS price_avg
        FROM x WHERE fenster <> 'X'
        GROUP BY symbol, fenster ORDER BY symbol, fenster
        """
    , [SYMBOL]).fetchdf().to_string(index=False)
)

con.close()
