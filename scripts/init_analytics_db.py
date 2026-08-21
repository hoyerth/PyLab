# scripts/init_analytics_db.py
from pathlib import Path
import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_ANALYTICS = DATA_DIR / "analytics_data.duckdb"

def init_analytics_tables():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_ANALYTICS))
    try:
        # 1. Metadaten-Tabelle für Runs
        con.execute("""
            CREATE TABLE IF NOT EXISTS indicator_runs (
                run_id VARCHAR PRIMARY KEY,
                indicator_name VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                timeframe VARCHAR NOT NULL,
                params_json JSON NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """)

        # 2. Events-Tabelle mit Composite Primary Key zur absoluten Idempotenz
        con.execute("""
            CREATE TABLE IF NOT EXISTS signal_events (
                run_id VARCHAR NOT NULL,
                time TIMESTAMPTZ NOT NULL,
                signal_type VARCHAR NOT NULL,
                direction TINYINT NOT NULL,
                price DOUBLE NOT NULL,
                strength DOUBLE NOT NULL,
                meta_json JSON,
                PRIMARY KEY (run_id, time, signal_type, price)
            );
        """)
        print("Schema in analytics_data.duckdb erfolgreich initialisiert.")
    finally:
        con.close()

if __name__ == "__main__":
    init_analytics_tables()