# signal_lab/quick_look.py
"""Quick Look: Chart-Schnellsicht (Wrapper um chart_engine, §7).

Zeigt ein begrenztes Fenster (wie Chart Inspector) mit MA-Signalen und
optionalen HTF-Signalen (Multi-TF-Overlay, farbcodiert + versetzt).
Die HTF-Signale werden auf den Auslösezeitpunkt des kleinen TF angenähert.
"""
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from algos.ma_indicator import MAIndicator
from algos.signal_events import IndicatorResult, SignalEvent, extract_events_numpy


def parse_symbol_tf(text: str) -> Tuple[str, str]:
    """Parst 'SYMBOL:TF' (z. B. 'SILVER:M30'). Fallback: ('SILVER', 'M30')."""
    if not text or ":" not in text:
        return "SILVER", "M30"
    symbol, tf = text.strip().split(":", 1)
    return symbol.strip().upper(), tf.strip().upper()


def _load_tf_range(
    db_path,
    symbol: str,
    timeframe: str,
    t_from: pd.Timestamp,
    t_to: pd.Timestamp,
    tz_offset_hours: int = 2,
) -> pd.DataFrame:
    """Lädt OHLCV für Symbol/TF im Zeitbereich [t_from, t_to] (naive Brokerzeit)."""
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        q = f"""
            SELECT "time", open, high, low, close, tick_volume AS volume
            FROM ohlcv_bars
            WHERE LOWER(symbol)=LOWER('{symbol}')
              AND LOWER(timeframe)=LOWER('{timeframe}')
              AND "time" IS NOT NULL
              AND "time" >= CAST(? AS TIMESTAMP)
              AND "time" <= CAST(? AS TIMESTAMP)
            ORDER BY "time" ASC
        """
        df = con.execute(q, [t_from, t_to]).df().copy()
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


def _approx_htf_to_small(
    htf_events: List[SignalEvent],
    small_times: np.ndarray,
    htf_tf: str,
    htf_delta: pd.Timedelta,
) -> List[SignalEvent]:
    """Projiziert HTF-Signale auf den Auslösezeitpunkt des kleinen TF.

    Approximation: Das HTF-Signal entsteht am Close des HTF-Bars. Der
    zugehörige kleine-TF-Bar ist der letzte kleine-TF-Bar im HTF-Intervall.
    """
    out = []
    # datetime64-Arithmetik für searchsorted (Timestamps sind nicht direkt sortierbar)
    small_ns = np.asarray(small_times, dtype="datetime64[ns]")
    for ev in htf_events:
        # Geschätzter HTF-Close = Bar-Start + HTF-Delta
        close_est = np.datetime64(pd.Timestamp(ev.time) + htf_delta)
        # Nächster kleiner-TF-Bar <= close_est
        idx = int(np.searchsorted(small_ns, close_est, side="right")) - 1
        if idx < 0:
            continue
        out.append(SignalEvent(
            time=small_times[idx],
            signal_type=ev.signal_type,
            direction=ev.direction,
            price=ev.price,
            strength=ev.strength,
            meta={**ev.meta, "tf": htf_tf, "stack": True},
        ))
    return out


def _tf_delta(tf: str) -> pd.Timedelta:
    """Naive TF-Dauer (nur für die HTF-Annäherung)."""
    tf = tf.upper()
    if tf.startswith("M"):
        return pd.Timedelta(minutes=int(tf[1:]))
    if tf.startswith("H"):
        return pd.Timedelta(hours=int(tf[1:]))
    if tf == "D1":
        return pd.Timedelta(days=1)
    if tf == "W1":
        return pd.Timedelta(weeks=1)
    if tf == "MN1":
        return pd.Timedelta(days=30)
    return pd.Timedelta(hours=1)


def build_quick_look_result(
    symbol: str,
    timeframe: str,
    db_market,
    overlay_tfs: List[str] = None,
    window_bars: int = 1000,
    warmup_bars: int = 200,
    end_offset_bars: int = 0,
    tz_offset_hours: int = 2,
    ma_params: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, List[IndicatorResult]]:
    """Berechnet Fenster-Daten + MA-Result (+ HTF-Overlay-Results).

    Rückgabe: (df_base, results) für `show_chart`.
    - df_base: kleines TF-Fenster (+ Warmup) – wie Chart Inspector.
    - results[0]: MA-Result auf dem kleinen TF.
    - results[1:]: HTF-Overlay-Results (nur Events, plot_meta leer).
    """
    from algos.chart_engine import load_candles

    overlay_tfs = [t for t in (overlay_tfs or []) if t and t != timeframe]

    df_base = load_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=window_bars,
        tz_offset_hours=tz_offset_hours,
        end_offset_bars=end_offset_bars,
        warmup_bars=warmup_bars,
        db_path=db_market,
    )
    if df_base.empty or len(df_base) < 2:
        return df_base, []

    params = dict(ma_params or {"ma_type": "EHMA", "period": 6, "smoothing": 10, "alpha_factor": 3.0})
    ma = MAIndicator(**params)
    ma_res = ma.compute(df_base, symbol=symbol, timeframe=timeframe)

    results: List[IndicatorResult] = [ma_res]
    if not overlay_tfs:
        return df_base, results

    # Zeitbereich des kleinen TF (inkl. Warmup) für HTF-Daten
    small_times = df_base["time"].values
    t_first = pd.Timestamp(small_times[0])
    t_last = pd.Timestamp(small_times[-1])

    for htf in overlay_tfs:
        hdf = _load_tf_range(db_market, symbol, htf, t_first, t_last, tz_offset_hours)
        if hdf.empty or len(hdf) < 3:
            continue
        hma = MAIndicator(**params)
        hres = hma.compute(hdf, symbol=symbol, timeframe=htf)
        if not hres.events:
            continue
        delta = _tf_delta(htf)
        approx_events = _approx_htf_to_small(hres.events, small_times, htf, delta)
        if not approx_events:
            continue
        # Nur Events im sichtbaren Fenster (ohne Warmup) behalten
        cut = df_base["time"].iloc[min(warmup_bars, len(df_base) - 1)]
        approx_events = [e for e in approx_events if e.time >= cut]
        results.append(IndicatorResult(
            symbol=symbol,
            timeframe=htf,
            indicator_name="MAIndicator_HTF",
            params=dict(params, _htf_tf=htf),
            df=hdf,
            events=approx_events,
            plot_meta={},  # keine MA-Linien zeichnen (fremde Zeitskala)
        ))
    return df_base, results


def render_quick_look(
    symbol_tf: str,
    db_market,
    overlay_tfs: List[str] = None,
    window_bars: int = 1000,
    warmup_bars: int = 200,
    end_offset_bars: int = 0,
    tz_offset_hours: int = 2,
    ma_params: Optional[Dict[str, Any]] = None,
    **chart_kwargs,
) -> Any:
    """Komfort-Funktion: rendert den Quick Look direkt als Marimo-HTML.

    symbol_tf: 'SYMBOL:TF' (Eingabezelle über der Grafik).
    Rückgabe: show_chart(...) – fertiges Marimo-iframe.
    """
    from algos.chart_engine import show_chart

    symbol, timeframe = parse_symbol_tf(symbol_tf)
    df_base, results = build_quick_look_result(
        symbol, timeframe, db_market,
        overlay_tfs=overlay_tfs,
        window_bars=window_bars,
        warmup_bars=warmup_bars,
        end_offset_bars=end_offset_bars,
        tz_offset_hours=tz_offset_hours,
        ma_params=ma_params,
    )
    if df_base.empty or len(df_base) < 2:
        import marimo as mo
        return mo.md(f"**Keine Daten für {symbol} {timeframe}**")

    warmup = min(int(warmup_bars), max(0, len(df_base) - 1))
    return show_chart(
        df=df_base,
        symbol=symbol,
        timeframe=timeframe,
        results=results,
        show_day_separators=True,
        show_signals=True,
        min_segment_len=3,
        warmup_bars=warmup,
        visible_bars=window_bars,
        **chart_kwargs,
    )
