# algos/chart_plugins.py
"""
Plugin- und Payload-Builder für Chart-Elemente (MAs, Grid, Separators, Markers).
Pfad: algos/chart_plugins.py
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


def build_candles_payload(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], int, float]:
    """Wandelt OHLCV in Lightweight-Charts-Candle-Format um und ermittelt Precision."""
    time_sec = (df["time"].astype("int64") // 10**9).values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    candles = [
        {"time": int(t), "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        for t, o, h, l, c in zip(time_sec, opens, highs, lows, closes)
    ]

    sample_price = float(closes[-1])
    precision = 5 if sample_price < 10 else (3 if sample_price < 1000 else 2)
    min_move = 1 / (10 ** precision)

    return candles, precision, min_move


def build_ma_lines_payload(df: pd.DataFrame, ma_indicator: Any) -> List[Dict[str, Any]]:
    """Erzeugt Liniendaten-Payload für Moving Averages."""
    if ma_indicator is None:
        return []

    lines = []
    ma_cols = [
        c for c in df.columns
        if c.startswith("ma_") and not c.endswith("_bull") and not c.endswith("_bear")
    ]
    width_line = getattr(ma_indicator, "line_width", 2)

    for col in ma_cols:
        segments = ma_indicator.get_segments(df, col)
        for seg_df, color in segments:
            if len(seg_df) < 2:
                continue
            seg_times = (seg_df["time"].astype("int64") // 10**9).values
            seg_vals = seg_df[col].values
            lines.append({
                "data": [{"time": int(t), "value": float(v)} for t, v in zip(seg_times, seg_vals)],
                "color": color,
                "width": width_line,
                "style": 0,
            })
    return lines


def build_day_separators_payload(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Erzeugt vertikale Tagestrennlinien."""
    times = df["time"]
    dates = times.dt.date
    daily_extrema = df.groupby(dates).agg(
        day_start=("time", "first"),
        day_low=("low", "min"),
        day_high=("high", "max"),
    )
    lines = []
    first_date = dates.iloc[0]
    for d, row in daily_extrema.iterrows():
        if d == first_date:
            continue
        pad = max((row["day_high"] - row["day_low"]) * 0.08, row["day_high"] * 0.002)
        t_sec = int(pd.Timestamp(row["day_start"]).timestamp())
        lines.append({
            "data": [
                {"time": t_sec, "value": float(row["day_low"] - pad)},
                {"time": t_sec, "value": float(row["day_high"] + pad)},
            ],
            "color": "rgba(66, 153, 225, 0.75)",
            "width": 1,
            "style": 2,
        })
    return lines


def build_grid_payload(
    df: pd.DataFrame,
    grid_indicator: Any,
    t_first: int,
    t_last: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Erzeugt Grid-Linien und Hit-Circles (X, Y)."""
    if grid_indicator is None:
        return [], []

    grid_res = grid_indicator.calculate(df)
    lines = [
        {
            "data": [{"time": t_first, "value": float(gl["price"])}, {"time": t_last, "value": float(gl["price"])}],
            "color": gl["color"],
            "width": gl["width"],
            "style": 0,
        }
        for gl in grid_res.get("lines", [])
    ]

    hit_circles = [
        {
            "time": int(pd.Timestamp(h["time"]).timestamp()),
            "price": float(h["price"]),
            "color": h.get("color", "#FF00FF"),
        }
        for h in grid_res.get("hit_circles", [])
    ]
    return lines, hit_circles


def build_signal_markers_payload(df: pd.DataFrame, ma_indicator: Any) -> List[Dict[str, Any]]:
    """Erzeugt Arrow-Marker für Handelssignale."""
    if ma_indicator is None or "signal" not in df.columns:
        return []

    signals = df[df["signal"] != 0]
    bull_c = getattr(ma_indicator, "bull_color", "#26a69a")
    bear_c = getattr(ma_indicator, "bear_color", "#ef5350")

    markers = []
    for row in signals.itertuples(index=False):
        is_buy = (row.signal == 1)
        markers.append({
            "time": int(pd.Timestamp(row.time).timestamp()),
            "position": "belowBar" if is_buy else "aboveBar",
            "color": bull_c if is_buy else bear_c,
            "shape": "arrowUp" if is_buy else "arrowDown",
            "size": 1,
        })
    return markers