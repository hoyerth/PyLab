"""Kurzer Check: BRENT-M15-Daten verfuegbar? (Q: User-Economic-Frage)

Nur DB-Abfragen, keine Engine-Laeufe.
"""
import duckdb

con = duckdb.connect("data/market_data.duckdb", read_only=True)
try:
    print("Symbole:", con.execute("SELECT DISTINCT symbol FROM ohlcv_bars").fetchall())
    for name, a, b in [("AUG", "2026-08-10", "2026-08-28"),
                       ("S1", "2026-02-05", "2026-08-28"),
                       ("S2", "2025-01-01", "2025-12-01")]:
        row = con.execute(
            f"SELECT count(*) AS n FROM ohlcv_bars "
            f"WHERE symbol='BRENT' AND timeframe='M15' "
            f"AND time AT TIME ZONE 'UTC' >= DATE '{a}' "
            f"AND time AT TIME ZONE 'UTC' < DATE '{b}'"
        ).fetchone()
        print(f"BRENT M15 {name} ({a}..{b}): {row[0]} Bars")
finally:
    con.close()
