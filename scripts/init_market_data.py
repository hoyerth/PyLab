# scripts/init_market_data.py
"""Initialisiert eine LEERE `data/market_data.duckdb` mit dem ohlcv_bars-Schema.

Zweck: Frischer Neuaufbau der Market-DB (z. B. nach Umbennenung der alten DB
in `market_data_Origin.duckdb`). Das Schema ist identisch zum Original
(PRIMARY KEY (symbol, timeframe, time)), damit `INSERT OR REPLACE` im
db_service.py (Notebooks/00_DB_Service.py) korrekt funktioniert.

Idempotent: CREATE TABLE IF NOT EXISTS - kann bedenkenlos mehrfach laufen.

Ausfuehrung:
    .venv\\Scripts\\python.exe scripts\\init_market_data.py
"""
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_MARKET = DATA_DIR / "market_data.duckdb"

DDL_OHLCV_BARS = """
CREATE TABLE IF NOT EXISTS ohlcv_bars (
    symbol       VARCHAR                NOT NULL,
    timeframe    VARCHAR                NOT NULL,
    time         TIMESTAMP WITH TIME ZONE NOT NULL,
    open         DOUBLE                 NOT NULL,
    high         DOUBLE                 NOT NULL,
    low          DOUBLE                 NOT NULL,
    close        DOUBLE                 NOT NULL,
    tick_volume  BIGINT,
    spread       INTEGER,
    real_volume  BIGINT,
    created_at   TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (symbol, timeframe, time)
)
"""


def main() -> None:
    """Erzeugt `data/market_data.duckdb` (leer) mit dem ohlcv_bars-Schema."""
    if DB_MARKET.exists():
        print(f"WARNUNG: {DB_MARKET} existiert bereits - wird NICHT ueberschrieben.")
        print("Bitte Datei erst entfernen/umbenennen, dann erneut ausfuehren.")
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_MARKET))
    try:
        con.execute(DDL_OHLCV_BARS)
    finally:
        con.close()
    # Verifikation
    con = duckdb.connect(str(DB_MARKET), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM ohlcv_bars").fetchone()[0]
        cols = [r[0] for r in con.execute("DESCRIBE ohlcv_bars").fetchall()]
    finally:
        con.close()
    print(f"Neu angelegt: {DB_MARKET}")
    print(f"Tabellen: ohlcv_bars | Zeilen: {n}")
    print(f"Spalten: {', '.join(cols)}")


if __name__ == "__main__":
    main()
