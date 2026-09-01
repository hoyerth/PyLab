# scripts/init_backtest_db.py
"""Initialisiert das v1-Schema in `data/backtest_data.duckdb`.

Tabellen (idempotent, CREATE TABLE IF NOT EXISTS):
  - backtest_runs   (1 Zeile pro Lauf: Metadaten, Params, aggregierte Metriken)
  - backtest_trades (N Zeilen pro Lauf: Einzelne Order-Ausfuehrungen, FK auf runs)

Ausfuehrung:
    .venv\\Scripts\\python.exe scripts\\init_backtest_db.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtest_lab.schema import init_backtest_schema  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"
DB_BACKTEST = DATA_DIR / "backtest_data.duckdb"


def main() -> None:
    """Erzeugt `data/backtest_data.duckdb` mit dem v1-Schema."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_backtest_schema(DB_BACKTEST)
    print(f"Schema initialisiert: {DB_BACKTEST}")


if __name__ == "__main__":
    main()
