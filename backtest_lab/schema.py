# backtest_lab/schema.py
"""Tabellen-DDL fuer `backtest_data.duckdb` (v1).

Schema-Abgleich: `BacktestRunRecord` in `types.py` (1:1).

Hinweise:
- `run_id` = deterministischer SHA-256-Hash (`run_id_from_config`), kein
  uuid4 (Bugfix 3: identische Konfiguration -> Overwrite statt Duplikate).
- `params_json` als JSON-Typ (wie `analytics_data.indicator_runs.params_json`).
- `backtest_trades` referenziert `backtest_runs` per FK.
"""
from pathlib import Path
from typing import Union

import duckdb

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL_BACKTEST_RUNS: str = """
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id            VARCHAR PRIMARY KEY,
    signal_run_id     VARCHAR NOT NULL,
    run_name          VARCHAR,
    symbol            VARCHAR NOT NULL,
    timeframe         VARCHAR NOT NULL,
    params_json       JSON,
    date_from         TIMESTAMPTZ,
    date_to           TIMESTAMPTZ,
    net_profit        DOUBLE,
    win_rate          DOUBLE,
    profit_factor     DOUBLE,
    max_drawdown_pct  DOUBLE,
    max_drawdown      DOUBLE,
    sl_count          INTEGER,
    sharpe_ratio      DOUBLE,
    trade_count       INTEGER,
    avg_trade_pnl     DOUBLE,
    expectancy        DOUBLE,
    max_win           DOUBLE,
    created_at        TIMESTAMPTZ DEFAULT now()
)
"""

# Bugfix 6 (Max Win): Migration fuer bereits angelegte Datenbanken, deren
# `backtest_runs` noch keine `max_win`-Spalte hat. DuckDB ignoriert das
# `IF NOT EXISTS`-Idempotenz-Muster - die Spalte wird nur ergaenzt, wenn
# sie fehlt.
DDL_BACKTEST_RUNS_MIGRATE_MAX_WIN: str = """
ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS max_win DOUBLE
"""

# Bugfix 8 (Max Drawdown $ + SL-Count): Migration fuer bestehende DBs -
# neue Spalten in `backtest_runs` nachtragen (idempotent).
DDL_BACKTEST_RUNS_MIGRATE_BUGFIX8: str = """
ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS max_drawdown DOUBLE;
ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS sl_count INTEGER
"""

DDL_BACKTEST_TRADES: str = """
CREATE TABLE IF NOT EXISTS backtest_trades (
    run_id        VARCHAR NOT NULL,
    entry_time    TIMESTAMPTZ,
    exit_time     TIMESTAMPTZ,
    entry_price   DOUBLE,
    exit_price    DOUBLE,
    direction     INTEGER,
    pnl           DOUBLE,
    r_multiple    DOUBLE,
    exit_reason   VARCHAR,
    FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id)
)
"""

# Bugfix 8 (Exit-Grund): Migration - `exit_reason`-Spalte nachtragen.
DDL_BACKTEST_TRADES_MIGRATE_EXIT_REASON: str = """
ALTER TABLE backtest_trades ADD COLUMN IF NOT EXISTS exit_reason VARCHAR
"""


def init_backtest_schema(db_path: Union[str, Path]) -> None:
    """Legt das v1-Schema idempotent an (CREATE TABLE IF NOT EXISTS).

    Fuehrt zusaetzlich die Bugfix-6-Migration (`max_win`-Spalte) aus,
    damit bestehende `backtest_data.duckdb`-Dateien die neue Spalte
    erhalten, ohne die Tabelle neu anlegen zu muessen.

    Args:
        db_path: Pfad zur `backtest_data.duckdb` (erzeugt die Datei, wenn
            sie nicht existiert).

    Example:
        >>> init_backtest_schema("data/backtest_data.duckdb")
    """
    con = duckdb.connect(str(db_path))
    try:
        con.execute(DDL_BACKTEST_RUNS)
        con.execute(DDL_BACKTEST_RUNS_MIGRATE_MAX_WIN)
        con.execute(DDL_BACKTEST_RUNS_MIGRATE_BUGFIX8)
        con.execute(DDL_BACKTEST_TRADES)
        con.execute(DDL_BACKTEST_TRADES_MIGRATE_EXIT_REASON)
    finally:
        con.close()
