"""
STUFE 5 - SCHRITT 1: REIN LESENDER DUCKDB-SCAN (test/tmp_stufe5_db_scan.py)
===========================================================================
Status: Einmalige, strikt isolierte Freigabe (05.09.2026) - reine Daten-
Verfuegbarkeits-Analyse fuer die Stufe-5-OOS-Planung. KEIN Schreiben, KEINE
Strategieausfuehrung, KEINE Tests. DuckDB read_only=True.

Zweck
-----
Ermittelt fuer SILVER M15 in data/market_data.duckdb:
  1. Symbol/Timeframe-Uebersicht (min/max ts, Bar-Zahl).
  2. Monats-Bar-Zaehlung (Kontinuitaet / Datenluecken).
  3. Luecken-Analyse (groesste Abstaende zwischen aufeinanderfolgenden Bars).
Dient der Verifikation der OOS-Kandidaten-Zonen aus §2.16 (nach 2026-08-28,
Holdout-Luecke 2025-12-01..2026-02-05, historische Tiefe vor 2025-01-01).

Wanduhr-Garantie: SQL nutzt strikt `time AT TIME ZONE 'UTC'` (keine stille
Lokalzeit-Konvertierung, Invariante aus Agents.md).
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DB: Path = Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"

con = duckdb.connect(str(DB), read_only=True)

print("=" * 100)
print("STUFE 5 - SCHRITT 1: DUCKDB-SCAN (read_only=True)")
print(f"DB: {DB}")
print("=" * 100)

# --- 1) Symbol/Timeframe-Uebersicht ------------------------------------------
print("\n[1] SYMBOL / TIMEFRAME / N / MIN_TS / MAX_TS")
rows = con.execute(
    """
    SELECT symbol, timeframe, count(*) AS n,
           min(time AT TIME ZONE 'UTC') AS min_ts,
           max(time AT TIME ZONE 'UTC') AS max_ts
    FROM ohlcv_bars
    GROUP BY symbol, timeframe
    ORDER BY symbol, timeframe
    """
).fetchall()
for r in rows:
    print(f"  {r[0]:<8} {r[1]:<5} n={r[2]:>9}  {r[3]}  ..  {r[4]}")

# --- 2) Monats-Bar-Zaehlung SILVER M15 ----------------------------------------
print("\n[2] MONATS-BARS SILVER M15 (Kontinuitaet)")
rows = con.execute(
    """
    SELECT strftime(time AT TIME ZONE 'UTC', '%Y-%m') AS mon,
           count(*) AS n
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
    GROUP BY 1
    ORDER BY 1
    """
).fetchall()
for r in rows:
    print(f"  {r[0]}  n={r[1]:>7}")

# --- 3) Luecken-Analyse SILVER M15 --------------------------------------------
print("\n[3] GROESSTE LÜCKEN SILVER M15 (top 25, Minuten)")
con.execute(
    """
    CREATE TEMP VIEW sil_m15 AS
    SELECT time AT TIME ZONE 'UTC' AS ts
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
    """
)
rows = con.execute(
    """
    WITH diffs AS (
        SELECT ts,
               lead(ts) OVER (ORDER BY ts) AS next_ts
        FROM sil_m15
    )
    SELECT ts, next_ts,
           date_diff('minute', ts, next_ts) AS gap_min
    FROM diffs
    WHERE next_ts IS NOT NULL
    ORDER BY gap_min DESC
    LIMIT 25
    """
).fetchall()
for r in rows:
    print(f"  {r[0]}  ->  {r[1]}   gap={r[2]} min")

con.close()
print("\nScan abgeschlossen (read_only=True, kein Schreiben).")
