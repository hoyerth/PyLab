# signal_lab/sweep_runner.py
"""Orchestrator für Massentests (sequenziell + Multiprocessing).

Persistierung nach Chunk-Ende in DuckDB (vermeidet Write-Locks).
"""
import multiprocessing as mp
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from algos.ma_indicator import MAIndicator
from algos.signal_events import IndicatorResult, SignalEvent
from algos.signal_service import DuckDBSignalService
from signal_lab.naming import build_run_name
from signal_lab.run_definition import RunDefinition

# ---------------------------------------------------------------------------
# Daten laden (einmalig je Symbol x TF, Datumsfilter)
# ---------------------------------------------------------------------------

def load_market_data(
    symbol: str,
    timeframe: str,
    db_path,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tz_offset_hours: int = 2,
    limit: int = 2_000_000,
) -> pd.DataFrame:
    """Lädt OHLCV für Symbol/TF, optional begrenzt auf einen Datumsbereich.

    Konvention: naive Brokerzeit (wie im Chart Inspector). date_from/date_to
    als ISO-String 'YYYY-MM-DD' oder 'YYYY-MM-DD HH:MM'.
    """
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        q = f"""
            SELECT "time", open, high, low, close, tick_volume AS volume
            FROM ohlcv_bars
            WHERE LOWER(symbol)=LOWER('{symbol}')
              AND LOWER(timeframe)=LOWER('{timeframe}')
              AND "time" IS NOT NULL
        """
        params = []
        if date_from:
            q += " AND \"time\" >= CAST(? AS TIMESTAMP)"
            params.append(date_from)
        if date_to:
            q += " AND \"time\" <= CAST(? AS TIMESTAMP)"
            params.append(date_to)
        q += " ORDER BY \"time\" ASC LIMIT " + str(int(limit))
        df = con.execute(q, params).df().copy()
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)
    df["time"] = df["time"].astype("datetime64[ns]")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype("float64")
    return df


# ---------------------------------------------------------------------------
# HTF-Exact-Time: Logik auf kleinerem TF, exakter Auslösezeitpunkt
# ---------------------------------------------------------------------------

def _apply_htf_exact_time(
    result: IndicatorResult,
    small_df: pd.DataFrame,
    source_tf: str,
    period: int,
    smoothing: int,
    alpha_factor: float,
    ma_type: str,
) -> None:
    """Ersetzt die Swing-Change-Zeitpunkte durch den exakten Zeitpunkt auf
    dem kleineren TF (Annäherung: kleinste TF-Signalzeit im HTF-Bar-Fenster)."""
    if small_df is None or small_df.empty or len(small_df) < 2:
        return
    small_ma = MAIndicator(ma_type=ma_type, period=period, smoothing=smoothing, alpha_factor=alpha_factor)
    small_res = small_ma.compute(small_df, symbol=result.symbol, timeframe=source_tf)
    small_events = [e for e in small_res.events if e.signal_type == "swing_change"]
    if not small_events:
        return

    # Big-TF-Bar-Delta (naiv): Differenz zwischen zwei aufeinanderfolgenden Bars
    big_times = result.df["time"].values
    if len(big_times) >= 2:
        delta = pd.Timedelta(big_times[1] - big_times[0])
    else:
        delta = pd.Timedelta(hours=1)

    # Nach Zeit sortierte kleine Events
    small_events.sort(key=lambda e: e.time)
    small_times = [e.time for e in small_events]

    for ev in result.events:
        if ev.signal_type != "swing_change":
            continue
        win_start = ev.time
        win_end = ev.time + delta
        # Kleinste TF-Signalzeit im Fenster [win_start, win_end)
        import bisect
        i = bisect.bisect_left(small_times, win_start)
        if i < len(small_times) and small_times[i] < win_end:
            ev.time = small_times[i]
    result.source_tf = source_tf


# ---------------------------------------------------------------------------
# Slim-Result: Events warmup-gefiltert, df auf Mini-Größe reduziert (Pickle-schonend)
# ---------------------------------------------------------------------------

def _finalize_result(result: IndicatorResult, warmup_bars: int) -> IndicatorResult:
    """Filtert Events am Warmup-Cut und reduziert df für den Pickle-Transfer."""
    if warmup_bars > 0 and len(result.df) > warmup_bars:
        cut = result.df["time"].iloc[warmup_bars]
        result.events = [e for e in result.events if e.time >= cut]
    result.df = result.df.iloc[:1].copy()  # nur 1 Zeile behalten (für store_result)
    return result


# ---------------------------------------------------------------------------
# Sequenzieller Sweep
# ---------------------------------------------------------------------------

def run_sweep_sequential(
    definition: RunDefinition,
    db_market,
    service: DuckDBSignalService,
    warmup_bars: int = 200,
    tz_offset_hours: int = 2,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    free_tag: str = "",
    timestamp: datetime = None,
    run_name_override: str = "",
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> List[str]:
    """Führt den Sweep sequenziell aus; liefert die persistierten run_ids.

    run_name_override: wenn gesetzt, wird dieser Name (ohne Zeitstempel)
    für alle Runs verwendet; free_tag wird trotzdem angehängt.
    cancel_callback: liefert True, wenn der Lauf abgebrochen werden soll.
    Bereits persistierte Runs bleiben in der DB (idempotent), der Rest wird
    verworfen.
    """
    ts = timestamp or datetime.now()
    run_ids = []
    total = definition.count_runs()
    done = 0

    def _cancelled() -> bool:
        return bool(cancel_callback and cancel_callback())

    for symbol in definition.symbols:
        if _cancelled():
            break
        for tf in definition.timeframes:
            if _cancelled():
                break
            df = load_market_data(symbol, tf, db_market, definition.date_from, definition.date_to, tz_offset_hours)

            # Kleiner-TF-Daten für HTF-Exact-Time (nur einmal laden)
            small_df = None
            if definition.htf_exact_time and definition.htf_small_tf != tf:
                small_df = load_market_data(symbol, definition.htf_small_tf, db_market,
                                            definition.date_from, definition.date_to, tz_offset_hours)

            for params in definition.param_space:
                if _cancelled():
                    break
                if run_name_override:
                    run_name = run_name_override
                else:
                    run_name = build_run_name("MAIndicator", params, symbol, tf, ts, free_tag)
                if progress_callback:
                    progress_callback(done, total, run_name)

                ma = MAIndicator(**params)
                result = ma.compute(df, symbol=symbol, timeframe=tf)
                result.run_name = run_name
                if definition.htf_exact_time and small_df is not None:
                    _apply_htf_exact_time(result, small_df, definition.htf_small_tf,
                                          params.get("period", 6), params.get("smoothing", 10),
                                          params.get("alpha_factor", 3.0),
                                          params.get("ma_type", "EHMA"))
                slim = _finalize_result(result, warmup_bars)
                run_id = service.store_result(slim, warmup_bars=0,
                                              source_tf=getattr(slim, "source_tf", None))
                run_ids.append(run_id)
                done += 1
    if progress_callback:
        progress_callback(done, total, "")
    return run_ids


# ---------------------------------------------------------------------------
# Paralleler Sweep (Multiprocessing, Chunking über CPU-Kerne)
# ---------------------------------------------------------------------------

_WORKER = {}


def _init_worker(symbol, tf, df, warmup_bars, htf_exact_time, htf_small_tf, small_df, free_tag, ts_iso, run_name_override):
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


def _worker_chunk(params_chunk: List[Dict[str, Any]]) -> List[IndicatorResult]:
    """Berechnet einen ganzen Chunk im RAM und liefert die (slim) Results zurück."""
    symbol = _WORKER["symbol"]
    tf = _WORKER["tf"]
    df = _WORKER["df"]
    ts = _WORKER["ts"]
    free_tag = _WORKER["free_tag"]
    override = _WORKER["run_name_override"]
    out = []
    for params in params_chunk:
        ma = MAIndicator(**params)
        result = ma.compute(df, symbol=symbol, timeframe=tf)
        result.run_name = override if override else build_run_name("MAIndicator", params, symbol, tf, ts, free_tag)
        if _WORKER["htf_exact_time"] and _WORKER["small_df"] is not None:
            _apply_htf_exact_time(result, _WORKER["small_df"], _WORKER["htf_small_tf"],
                                  params.get("period", 6), params.get("smoothing", 10),
                                  params.get("alpha_factor", 3.0), params.get("ma_type", "EHMA"))
        out.append(_finalize_result(result, _WORKER["warmup_bars"]))
    return out


def run_sweep_parallel(
    definition: RunDefinition,
    db_market,
    service: DuckDBSignalService,
    warmup_bars: int = 200,
    tz_offset_hours: int = 2,
    n_workers: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    free_tag: str = "",
    timestamp: datetime = None,
    run_name_override: str = "",
) -> List[str]:
    """Paralleler Sweep: Chunking der Parameter-Sets, Persistierung nach Chunk-Ende."""
    n_workers = n_workers or max(1, os.cpu_count() or 1)
    ts = timestamp or datetime.now()
    run_ids = []
    total = definition.count_runs()
    done = 0

    # Parameter-Sets in Chunks aufteilen
    sets = definition.param_space
    chunks = [sets[i::n_workers] for i in range(n_workers)]
    chunks = [c for c in chunks if c]

    for symbol in definition.symbols:
        for tf in definition.timeframes:
            df = load_market_data(symbol, tf, db_market, definition.date_from, definition.date_to, tz_offset_hours)
            small_df = None
            if definition.htf_exact_time and definition.htf_small_tf != tf:
                small_df = load_market_data(symbol, definition.htf_small_tf, db_market,
                                            definition.date_from, definition.date_to, tz_offset_hours)

            ctx = mp.get_context("spawn")  # Windows-sicher
            with ctx.Pool(
                processes=len(chunks),
                initializer=_init_worker,
                initargs=(symbol, tf, df, warmup_bars, definition.htf_exact_time,
                          definition.htf_small_tf, small_df, free_tag, ts.isoformat(),
                          run_name_override),
            ) as pool:
                # Ergebnisse chunkweise verarbeiten -> Persistierung nach Chunk-Ende
                for chunk_results in pool.imap(_worker_chunk, chunks):
                    for result in chunk_results:
                        run_id = service.store_result(result, warmup_bars=0,
                                                      source_tf=getattr(result, "source_tf", None))
                        run_ids.append(run_id)
                        done += 1
                        if progress_callback:
                            progress_callback(done, total, getattr(result, "indicator_name", ""))
    if progress_callback:
        progress_callback(done, total, "")
    return run_ids
