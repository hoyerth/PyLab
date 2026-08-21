# scripts/migrate_analytics_db.py
"""Idempotente Schema-Migration für analytics_data.duckdb.

Fügt hinzu:
  indicator_runs.run_name   (sprechender Run-Name)
  signal_events.source_tf   (Herkunfts-TF des Signals)
  signal_events.signal_time (exakter Auslösezeitpunkt auf kleinerem TF)
"""
from pathlib import Path
import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_ANALYTICS = DATA_DIR / "analytics_data.duckdb"


def migrate():
    con = duckdb.connect(str(DB_ANALYTICS))
    try:
        con.execute("ALTER TABLE indicator_runs ADD COLUMN IF NOT EXISTS run_name VARCHAR;")
        con.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS source_tf VARCHAR;")
        con.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS signal_time TIMESTAMPTZ;")
        print("Migration OK: run_name, source_tf, signal_time vorhanden.")
    finally:
        con.close()


if __name__ == "__main__":
    migrate()
