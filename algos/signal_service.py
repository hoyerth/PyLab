# algos/signal_service.py
from abc import ABC, abstractmethod
from typing import List, Optional
import hashlib
import json
from pathlib import Path
import duckdb
import pandas as pd
from algos.signal_events import IndicatorResult

DEFAULT_ANALYTICS_DB = Path(__file__).resolve().parent.parent / "data" / "analytics_data.duckdb"


class SignalService(ABC):
    @abstractmethod
    def store_result(self, result: IndicatorResult, warmup_bars: int = 0) -> Optional[str]:
        pass

    @abstractmethod
    def get_events(self, symbol: str = None, timeframe: str = None, signal_types: list = None) -> pd.DataFrame:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class MemorySignalService(SignalService):
    """RAM-Repository für visuelle Notebooks."""

    def __init__(self):
        self._results: List[IndicatorResult] = []

    def store_result(self, result: IndicatorResult, warmup_bars: int = 0) -> None:
        self._results.append(result)

    def get_events(self, symbol: str = None, timeframe: str = None, signal_types: list = None) -> pd.DataFrame:
        if not self._results:
            return pd.DataFrame()

        df_all = pd.concat([r.to_events_frame() for r in self._results], ignore_index=True)
        if df_all.empty:
            return df_all

        if symbol:
            df_all = df_all[df_all["symbol"] == symbol]
        if timeframe:
            df_all = df_all[df_all["timeframe"] == timeframe]
        if signal_types:
            df_all = df_all[df_all["signal_type"].isin(signal_types)]

        return df_all.sort_values("time").reset_index(drop=True)

    def clear(self) -> None:
        self._results.clear()


class DuckDBSignalService(SignalService):
    """Persistiert Runs und Events idempotent in analytics_data.duckdb."""

    def __init__(self, db_path: Path = DEFAULT_ANALYTICS_DB):
        self.db_path = str(db_path)

    def _generate_run_id(self, r: IndicatorResult) -> str:
        key = f"{r.indicator_name}_{r.symbol}_{r.timeframe}_{json.dumps(r.params, sort_keys=True)}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def store_result(self, result: IndicatorResult, warmup_bars: int = 0) -> str:
        events_df = result.to_events_frame()
        run_id = self._generate_run_id(result)

        # Warmup-Cutoff
        if warmup_bars > 0 and len(result.df) > warmup_bars:
            valid_start = pd.Timestamp(result.df["time"].iloc[warmup_bars])
            if valid_start.tz is None:
                valid_start = valid_start.tz_localize("UTC")
            events_df = events_df[events_df["time"] >= valid_start].copy()

        events_df["run_id"] = run_id
        params_str = json.dumps(result.params)

        con = duckdb.connect(self.db_path)
        try:
            # Idempotenter Run-Insert
            con.execute("""
                INSERT OR IGNORE INTO indicator_runs (run_id, indicator_name, symbol, timeframe, params_json)
                VALUES (?, ?, ?, ?, ?)
            """, [run_id, result.indicator_name, result.symbol, result.timeframe, params_str])

            # Idempotenter Batch-Insert der Events (ON CONFLICT DO NOTHING durch Primary Key)
            if not events_df.empty:
                con.register("df_events_temp", events_df)
                con.execute("""
                    INSERT OR IGNORE INTO signal_events (run_id, time, signal_type, direction, price, strength, meta_json)
                    SELECT run_id, "time", signal_type, direction, price, strength, meta_json
                    FROM df_events_temp
                """)
                con.unregister("df_events_temp")
        finally:
            con.close()
        return run_id

    def get_events(self, symbol: str = None, timeframe: str = None, signal_types: list = None) -> pd.DataFrame:
        con = duckdb.connect(self.db_path, read_only=True)
        try:
            query = """
                SELECT r.symbol, r.timeframe, r.indicator_name, e.run_id, e.time, 
                       e.signal_type, e.direction, e.price, e.strength, e.meta_json
                FROM signal_events e
                JOIN indicator_runs r USING (run_id)
                WHERE 1=1
            """
            params = []
            if symbol:
                query += " AND r.symbol = ?"
                params.append(symbol)
            if timeframe:
                query += " AND r.timeframe = ?"
                params.append(timeframe)
            if signal_types:
                query += f" AND e.signal_type IN ({','.join(['?'] * len(signal_types))})"
                params.extend(signal_types)

            query += " ORDER BY e.time ASC"
            return con.execute(query, params).df()
        finally:
            con.close()

    def clear(self) -> None:
        con = duckdb.connect(self.db_path)
        try:
            con.execute("DELETE FROM signal_events; DELETE FROM indicator_runs;")
        finally:
            con.close()