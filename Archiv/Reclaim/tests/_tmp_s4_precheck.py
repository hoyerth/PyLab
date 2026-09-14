# -*- coding: utf-8 -*-
"""S4-Vorpruefung: Rueckgabeformat/TZ der BKZ-Projektion in DuckDB (read-only)."""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import duckdb

con = duckdb.connect("data/market_data.duckdb", read_only=True)
q = """
    SELECT "time" AT TIME ZONE 'UTC' AS time,
           open, high, low, close, tick_volume AS volume
    FROM (
        SELECT "time", open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE LOWER(symbol) = LOWER('SILVER')
          AND LOWER(timeframe) = LOWER('M15')
          AND "time" IS NOT NULL
        ORDER BY "time" DESC
        LIMIT 5
    ) sub
    ORDER BY "time" ASC;
"""
df = con.execute(q).df()
print("dtypes:\n", df.dtypes)
print("tz attr:", getattr(df["time"].dtype, "tz", None))
print("values:", [str(x) for x in df["time"].tolist()])
r = con.execute(
    'SELECT MIN("time" AT TIME ZONE \'UTC\'), MAX("time" AT TIME ZONE \'UTC\') '
    'FROM ohlcv_bars'
).fetchone()
print("minmax:", r, type(r[0]))
# Filter-Variante mit AT TIME ZONE 'UTC' (Kanon analog db.py)
q2 = """
    SELECT count(*) FROM ohlcv_bars
    WHERE LOWER(symbol)=LOWER('SILVER') AND LOWER(timeframe)=LOWER('M15')
      AND "time" >= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'
      AND "time" <= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'
"""
print("filter count:", con.execute(q2, ["2026-08-19 00:00", "2026-08-19 01:00"]).fetchone())
con.close()
