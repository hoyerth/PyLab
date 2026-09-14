# -*- coding: utf-8 -*-
"""Schritt 2 (READ-ONLY): Datenbestand SILVER/M15 fuer AUG26 (01.-31.08.2026).

Zeitbasis strikt BKZ = ``time AT TIME ZONE 'UTC'`` (docs/ZEITBASIS_KANON.md).
Monatsende exklusiv: [2026-08-01 00:00, 2026-09-01 00:00).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "market_data.duckdb"
con = duckdb.connect(str(DB), read_only=True)

print("=" * 96)
print("SCHRITT 2 -- DATENBESTAND AUG26 (SILVER M15, BKZ = time AT TIME ZONE 'UTC')")
print("=" * 96)

print("\n[0] Spaltentypen / Session-Zeitzone")
for _row in con.execute("DESCRIBE ohlcv_bars").fetchall():
    if _row[0] in ("time", "symbol", "timeframe"):
        print(f"    {_row[0]:<10} {_row[1]}")
print("    Session-TZ :", con.execute("SELECT current_setting('TimeZone')").fetchone()[0])

print("\n[1] Monatsumfang [2026-08-01, 2026-09-01) -- BKZ")
row = con.execute("""
    SELECT min(time AT TIME ZONE 'UTC'),
           max(time AT TIME ZONE 'UTC'),
           count(*)
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= TIMESTAMP '2026-08-01 00:00:00'
      AND time AT TIME ZONE 'UTC' <  TIMESTAMP '2026-09-01 00:00:00'
""").fetchone()
print(f"    min = {row[0]}")
print(f"    max = {row[1]}")
print(f"    n   = {row[2]}")

print("\n[2] Sicht-Vergleich (nacktes time vs. BKZ) -- nur zur Kontrolle")
row2 = con.execute("""
    SELECT count(*)
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time >= TIMESTAMP '2026-08-01 00:00:00'
      AND time <  TIMESTAMP '2026-09-01 00:00:00'
""").fetchone()
print(f"    n(nackt, Session-TZ) = {row2[0]}   (Kanon verbietet diese Basis)")

print("\n[3] Kerzen je Kalendertag (BKZ) + Wochenend-Luecken")
rows = con.execute("""
    SELECT CAST(time AT TIME ZONE 'UTC' AS DATE) AS tag, count(*)
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= TIMESTAMP '2026-08-01 00:00:00'
      AND time AT TIME ZONE 'UTC' <  TIMESTAMP '2026-09-01 00:00:00'
    GROUP BY 1 ORDER BY 1
""").fetchall()
tot = 0
for tag, cnt in rows:
    wd = tag.strftime("%a")
    mark = "  <- Wochenende" if wd in ("Sat", "Sun") else ""
    print(f"    {tag} {wd}  {cnt:>4}{mark}")
    tot += cnt
print(f"    Tage mit Daten: {len(rows)} | Summe: {tot}")

print("\n[4] Sub-Fenster: bisheriger AUG-Lauf (10.08.) vs. Monatsbeginn")
row4 = con.execute("""
    SELECT count(*) FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= TIMESTAMP '2026-08-01 00:00:00'
      AND time AT TIME ZONE 'UTC' <  TIMESTAMP '2026-08-10 00:00:00'
""").fetchone()
print(f"    01.08. .. 09.08. (bisher ausgelassener Monatsbeginn) = {row4[0]} Bars")

print("\n[5] Erste/letzte Kerzen des Monats (BKZ) + Rohpreise")
for label, q in (("erste 3", "ORDER BY time ASC LIMIT 3"),
                 ("letzte 3", "ORDER BY time DESC LIMIT 3")):
    rr = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= TIMESTAMP '2026-08-01 00:00:00'
          AND time AT TIME ZONE 'UTC' <  TIMESTAMP '2026-09-01 00:00:00'
        {q}
    """).fetchall()
    print(f"    {label}:")
    for r in rr:
        print(f"      {r[0]}  O {r[1]:.4f}  H {r[2]:.4f}  "
              f"L {r[3]:.4f}  C {r[4]:.4f}")

con.close()
print("\nENDE SCHRITT 2")
