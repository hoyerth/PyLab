"""
Orchestrator für Massentests (sequenziell + Multiprocessing).
Pfad: signal_lab/sweep_runner.py
"""

from datetime import datetime
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import duckdb
import pandas as pd

from algos.base_indicator import BaseIndicator
from algos.jump_indicator import JumpIndicator
from algos.ma_indicator import MAIndicator
from algos.signal_events import IndicatorResult, SignalEvent
from algos.signal_service import DuckDBSignalService
from signal_lab.naming import build_run_name
from signal_lab.run_definition import RunDefinition


def create_indicator(indicator_name: str, params: Dict[str, Any]) -> BaseIndicator:
    """Instanziiert den gewünschten Indikator typsicher anhand des Namens."""
    clean_name: str = indicator_name.strip().lower()
    clean_params: Dict[str, Any] = {
        k: v for k, v in params.items() if k != "indicator_name"
    }

    if "jump" in clean_name:
        return JumpIndicator(**clean_params)
    elif "ma" in clean_name:
        return MAIndicator(**clean_params)
    else:
        raise ValueError(f"Unbekannter Indikator-Typ: {indicator_name}")


def load_market_data(
    symbol: str,
    timeframe: str,
    db_path: Union[str, Path],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tz_offset_hours: int = 2,
    limit: int = 2_000_000,
) -> pd.DataFrame:
    """Lädt OHLCV für Symbol/TF, optional begrenzt auf einen Datumsbereich.

    Konvention: naive Brokerzeit (wie im Chart Inspector).
    """
    con: Optional[duckdb.DuckDBPyConnection] = None
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        q: str = f"""
            SELECT "time", open, high, low, close, tick_volume AS volume, spread
            FROM ohlcv_bars
            WHERE LOWER(symbol) = LOWER('{symbol}')
              AND LOWER(timeframe) = LOWER('{timeframe}')
              AND "time" IS NOT NULL
        """
        params_list: List[str] = []
        if date_from:
            q += ' AND "time" >= CAST(? AS TIMESTAMP)'
            params_list.append(date_from)
        if date_to:
            q += ' AND "time" <= CAST(? AS TIMESTAMP)'
            params_list.append(date_to)
        q += " ORDER BY \"time\" ASC LIMIT " + str(int(limit))
        df: pd.DataFrame = con.execute(q, params_list).df().copy()
    finally:
        if con is not None:
            con.close()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "spread",
            ]
        )

    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)
    df["time"] = df["time"].astype("datetime64[ns]")

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = df[col].astype("float64")
    if "spread" in df.columns:
        df["spread"] = df["spread"].fillna(0).astype("int64")

    return df


def _apply_htf_exact_time(
    result: IndicatorResult,
    small_df: Optional[pd.DataFrame],
    source_tf: str,
    indicator_name: str,
    params: Dict[str, Any],
) -> None:
    """Ersetzt die Event-Zeitpunkte durch den exakten Zeitpunkt auf dem kleineren TF."""
    if small_df is None or small_df.empty or len(small_df) < 2:
        return

    small_ind: BaseIndicator = create_indicator(indicator_name, params)
    small_res: IndicatorResult = small_ind.compute(
        small_df, symbol=result.symbol, timeframe=source_tf
    )
    small_events: List[SignalEvent] = list(small_res.events)
    if not small_events:
        return

    big_times = result.df["time"].values
    if len(big_times) >= 2:
        delta: pd.Timedelta = pd.Timedelta(big_times[1] - big_times[0])
    else:
        delta = pd.Timedelta(hours=1)

    small_events.sort(key=lambda e: e.time)
    small_times: List[pd.Timestamp] = [e.time for e in small_events]

    for ev in result.events:
        win_start: pd.Timestamp = ev.time
        win_end: pd.Timestamp = ev.time + delta
        import bisect

        i: int = bisect.bisect_left(small_times, win_start)
        if i < len(small_times) and small_times[i] < win_end:
            ev.time = small_times[i]
    result.source_tf = source_tf


def _finalize_result(
    result: IndicatorResult, warmup_bars: int
) -> IndicatorResult:
    """Filtert Events am Warmup-Cut und reduziert df für den Pickle-Transfer."""
    if warmup_bars > 0 and len(result.df) > warmup_bars:
        cut: pd.Timestamp = result.df["time"].iloc[warmup_bars]
        result.events = [e for e in result.events if e.time >= cut]
    result.df = result.df.iloc[:1].copy()
    return result


def run_sweep_sequential(
    definition: RunDefinition,
    db_market: Union[str, Path],
    service: DuckDBSignalService,
    warmup_bars: int = 200,
    tz_offset_hours: int = 2,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    free_tag: str = "",
    timestamp: Optional[datetime] = None,
    run_name_override: str = "",
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> List[str]:
    """Führt den Sweep sequenziell aus; liefert die persistierten run_ids."""
    ts: datetime = timestamp or datetime.now()
    run_ids: List[str] = []
    total: int = definition.count_runs()
    done: int = 0

    def _cancelled() -> bool:
        return bool(cancel_callback and cancel_callback())

    for symbol in definition.symbols:
        if _cancelled():
            break
        for tf in definition.timeframes:
            if _cancelled():
                break
            df: pd.DataFrame = load_market_data(
                symbol,
                tf,
                db_market,
                definition.date_from,
                definition.date_to,
                tz_offset_hours,
            )

            small_df: Optional[pd.DataFrame] = None
            if definition.htf_exact_time and definition.htf_small_tf != tf:
                small_df = load_market_data(
                    symbol,
                    definition.htf_small_tf,
                    db_market,
                    definition.date_from,
                    definition.date_to,
                    tz_offset_hours,
                )

            for params in definition.param_space:
                if _cancelled():
                    break

                ind_name: str = str(
                    params.get("indicator_name", "MAIndicator")
                )
                if run_name_override:
                    run_name: str = run_name_override
                else:
                    run_name = build_run_name(
                        ind_name, params, symbol, tf, ts, free_tag
                    )

                if progress_callback:
                    progress_callback(done, total, run_name)

                ind_instance: BaseIndicator = create_indicator(ind_name, params)
                result: IndicatorResult = ind_instance.compute(
                    df, symbol=symbol, timeframe=tf
                )
                result.run_name = run_name

                if definition.htf_exact_time and small_df is not None:
                    _apply_htf_exact_time(
                        result,
                        small_df,
                        definition.htf_small_tf,
                        ind_name,
                        params,
                    )

                slim: IndicatorResult = _finalize_result(result, warmup_bars)
                run_id: str = service.store_result(
                    slim,
                    warmup_bars=0,
                    source_tf=getattr(slim, "source_tf", None),
                )
                run_ids.append(run_id)
                done += 1

    if progress_callback:
        progress_callback(done, total, "")
    return run_ids


_WORKER: Dict[str, Any] = {}


def _init_worker(
    symbol: str,
    tf: str,
    df: pd.DataFrame,
    warmup_bars: int,
    htf_exact_time: bool,
    htf_small_tf: str,
    small_df: Optional[pd.DataFrame],
    free_tag: str,
    ts_iso: str,
    run_name_override: str,
) -> None:
    """Initialisiert den Worker-Prozess mit geteiltem Datenbestand."""
    _WORKER["symbol"] = symbol
    _WORKER["tf"] = tf
    _WORKER["df"] = df
    _WORKER["warmup_bars"] = warmup_bars
    _WORKER["htf_exact_time"] = htf_exact_time
    _WORKER["htf_small_tf"] = htf_small_tf
    _WORKER["small_df"] = small_df
    _WORKER["free_tag"] = free_tag
    _WORKER["ts"] = datetime.fromisoformat(ts_iso)
    _WORKER["run_name_override"] = run_name_override


def _worker_chunk(
    params_chunk: List[Dict[str, Any]],
) -> List[IndicatorResult]:
    """Berechnet einen ganzen Chunk im RAM und liefert die (slim) Results zurück."""
    symbol: str = _WORKER["symbol"]
    tf: str = _WORKER["tf"]
    df: pd.DataFrame = _WORKER["df"]
    ts: datetime = _WORKER["ts"]
    free_tag: str = _WORKER["free_tag"]
    override: str = _WORKER["run_name_override"]

    out: List[IndicatorResult] = []
    for params in params_chunk:
        ind_name: str = str(params.get("indicator_name", "MAIndicator"))
        ind_instance: BaseIndicator = create_indicator(ind_name, params)
        result: IndicatorResult = ind_instance.compute(
            df, symbol=symbol, timeframe=tf
        )

        result.run_name = (
            override
            if override
            else build_run_name(ind_name, params, symbol, tf, ts, free_tag)
        )

        if _WORKER["htf_exact_time"] and _WORKER["small_df"] is not None:
            _apply_htf_exact_time(
                result,
                _WORKER["small_df"],
                _WORKER["htf_small_tf"],
                ind_name,
                params,
            )
        out.append(_finalize_result(result, _WORKER["warmup_bars"]))
    return out


def run_sweep_parallel(
    definition: RunDefinition,
    db_market: Union[str, Path],
    service: DuckDBSignalService,
    warmup_bars: int = 200,
    tz_offset_hours: int = 2,
    n_workers: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    free_tag: str = "",
    timestamp: Optional[datetime] = None,
    run_name_override: str = "",
) -> List[str]:
    """Paralleler Sweep: Chunking der Parameter-Sets, Persistierung nach Chunk-Ende."""
    workers_count: int = n_workers or max(1, os.cpu_count() or 1)
    ts: datetime = timestamp or datetime.now()
    run_ids: List[str] = []
    total: int = definition.count_runs()
    done: int = 0

    sets: List[Dict[str, Any]] = definition.param_space
    chunks: List[List[Dict[str, Any]]] = [
        sets[i::workers_count] for i in range(workers_count)
    ]
    chunks = [c for c in chunks if c]

    for symbol in definition.symbols:
        for tf in definition.timeframes:
            df: pd.DataFrame = load_market_data(
                symbol,
                tf,
                db_market,
                definition.date_from,
                definition.date_to,
                tz_offset_hours,
            )
            small_df: Optional[pd.DataFrame] = None
            if definition.htf_exact_time and definition.htf_small_tf != tf:
                small_df = load_market_data(
                    symbol,
                    definition.htf_small_tf,
                    db_market,
                    definition.date_from,
                    definition.date_to,
                    tz_offset_hours,
                )

            ctx = mp.get_context("spawn")
            with ctx.Pool(
                processes=len(chunks),
                initializer=_init_worker,
                initargs=(
                    symbol,
                    tf,
                    df,
                    warmup_bars,
                    definition.htf_exact_time,
                    definition.htf_small_tf,
                    small_df,
                    free_tag,
                    ts.isoformat(),
                    run_name_override,
                ),
            ) as pool:
                for chunk_results in pool.imap(_worker_chunk, chunks):
                    for result in chunk_results:
                        run_id: str = service.store_result(
                            result,
                            warmup_bars=0,
                            source_tf=getattr(result, "source_tf", None),
                        )
                        run_ids.append(run_id)
                        done += 1
                        if progress_callback:
                            progress_callback(
                                done,
                                total,
                                getattr(result, "indicator_name", ""),
                            )

    if progress_callback:
        progress_callback(done, total, "")
    return run_ids