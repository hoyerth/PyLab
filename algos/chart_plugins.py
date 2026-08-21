"""
Payload-Builder für Lightweight Charts Overlays und Marker.
Pfad: algos/chart_plugins.py
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from algos.signal_events import SignalEvent


def build_candles_payload(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], int, float]:
    """Erzeugt das Kerzen-Payload für Lightweight Charts inkl. automatischer Präzision."""
    if df.empty:
        return [], 2, 0.01

    # Vektorisierte Epoch-Konvertierung (robust gegen ns-/us-Auflösung)
    time_sec = df["time"].values.astype("datetime64[s]").astype("int64")
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    candles = [
        {"time": int(t), "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        for t, o, h, l, c in zip(time_sec, opens, highs, lows, closes)
    ]

    # Automatische Nachkommastellen & minMove ermitteln
    spreads = (df["high"] - df["low"]).abs()
    min_diff = spreads[spreads > 0].min() if not spreads[spreads > 0].empty else 0.01

    if min_diff < 0.001:
        precision = 4
        min_move = 0.0001
    elif min_diff < 0.01:
        precision = 3
        min_move = 0.001
    elif min_diff < 0.1:
        precision = 2
        min_move = 0.01
    else:
        precision = 2
        min_move = 0.01

    return candles, precision, min_move


def build_day_separators_payload(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Erzeugt vertikale Tageswechsel-Linien."""
    if df.empty or len(df) < 2:
        return []

    separators = []
    times = pd.to_datetime(df["time"])
    day_changes = times.dt.date != times.dt.date.shift(1)

    # Erste Kerze überspringen
    day_change_indices = np.where(day_changes)[0]
    for idx in day_change_indices:
        if idx == 0:
            continue
        t_sec = int(times.iloc[idx].timestamp())
        separators.append({
            "time": t_sec,
            "color": "rgba(255, 255, 255, 0.18)",
            "width": 1,
            "dash": [4, 4],
        })

    return separators


def _segments_to_payload(
        segments: List[Tuple[pd.DataFrame, str]],
        col_name: str,
        line_width: int,
        min_segment_len: int
) -> List[Dict[str, Any]]:
    """Konvertiert (df, color)-Segmente in das Canvas-Polyline-Payload (vektorisiert)."""
    payload = []
    for seg_df, color in segments:
        if len(seg_df) < min_segment_len:
            continue
        # Robust gegen ns-/us-Auflösung
        seg_times = seg_df["time"].values.astype("datetime64[s]").astype("int64")
        seg_vals = seg_df[col_name].values
        pts = [{"time": int(t), "value": float(v)} for t, v in zip(seg_times, seg_vals)]
        payload.append({"color": color, "width": line_width, "data": pts})
    return payload


def build_ma_lines_payload(
        df: pd.DataFrame,
        ma_indicator: Optional[Any] = None,
        min_segment_len: int = 3
) -> List[Dict[str, Any]]:
    """Erzeugt farbsegmentierte Linien für den MA-Verlauf (Legacy-Pfad mit Instanz)."""
    if ma_indicator is None or df.empty:
        return []

    col_name = f"ma_{ma_indicator.ma_type.lower()}_{ma_indicator.period}"
    if col_name not in df.columns:
        return []

    segments = ma_indicator.get_segments(df, col_name)
    return _segments_to_payload(segments, col_name, ma_indicator.line_width, min_segment_len)


def build_ma_lines_from_result(
        df: pd.DataFrame,
        plot_meta: Optional[Dict[str, Any]] = None,
        min_segment_len: int = 3
) -> List[Dict[str, Any]]:
    """Erzeugt farbsegmentierte MA-Linien direkt aus IndicatorResult.plot_meta.

    Nutzt ausschließlich die normalisierten Metadaten (col_name, Farben,
    Line-Width) — OHNE Indikator-Instanz. Damit bleibt der results-Pfad
    vollständig von den Indikator-Klassen entkoppelt.
    """
    if df.empty or not plot_meta:
        return []

    col_name = plot_meta.get("col_name")
    if not col_name or col_name not in df.columns:
        return []

    bull_color = plot_meta.get("bull_color", "#089981")
    bear_color = plot_meta.get("bear_color", "#F23645")
    line_width = int(plot_meta.get("line_width", 2))

    vals = df[col_name].to_numpy()
    valid_mask = ~np.isnan(vals)
    if not np.any(valid_mask):
        return []

    df_valid = df.loc[valid_mask]
    if len(df_valid) < 2:
        return []

    diffs = np.diff(df_valid[col_name].to_numpy())
    is_bull = np.concatenate([[diffs[0] >= 0], diffs >= 0])

    # In bull/bear-Segmente aufteilen (gleiche Logik wie MAIndicator.get_segments)
    segments = []
    start_idx = 0
    n = len(df_valid)
    for i in range(1, n):
        if is_bull[i] != is_bull[i - 1]:
            segments.append((df_valid.iloc[start_idx:i + 1],
                             bull_color if is_bull[start_idx] else bear_color))
            start_idx = i
    if start_idx < n - 1:
        segments.append((df_valid.iloc[start_idx:n],
                         bull_color if is_bull[start_idx] else bear_color))

    return _segments_to_payload(segments, col_name, line_width, min_segment_len)


def build_grid_payload(
        df: pd.DataFrame,
        grid_indicator: Optional[Any] = None,
        t_first: Optional[int] = None,
        t_last: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Legacy-Fallback: Berechnet Grid-Linien und Hit-Circles direkt aus dem Indicator."""
    if grid_indicator is None or df.empty:
        return [], []

    res = grid_indicator.calculate(df)
    lines = res.get("lines", [])
    hit_circles = []

    for hc in res.get("hit_circles", []):
        t_sec = int(pd.Timestamp(hc["time"]).timestamp())
        hit_circles.append({
            "time": t_sec,
            "price": float(hc["price"]),
            "color": hc["color"],
        })

    return lines, hit_circles


def build_signal_markers_payload(
        df: pd.DataFrame,
        ma_indicator: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Legacy-Fallback: Baut Signal-Marker direkt aus der 'signal'-Spalte."""
    if ma_indicator is None or df.empty or "signal" not in df.columns:
        return []

    markers = []
    signals_df = df[df["signal"] != 0]

    for _, row in signals_df.iterrows():
        t_sec = int(pd.Timestamp(row["time"]).timestamp())
        is_buy = (row["signal"] == 1)
        markers.append({
            "time": t_sec,
            "position": "belowBar" if is_buy else "aboveBar",
            "color": ma_indicator.bull_color if is_buy else ma_indicator.bear_color,
            "shape": "arrowUp" if is_buy else "arrowDown",
            "size": 1,
        })

    return markers


# =====================================================================
# EVENT-BASIERTE BUILDER (Single Source of Truth)
# =====================================================================

def build_signal_markers_from_events(
        events: List[SignalEvent],
        bull_color: str = "#089981",
        bear_color: str = "#F23645"
) -> List[Dict[str, Any]]:
    """Erzeugt Pfeil-Marker direkt aus den normalisierten SignalEvents."""
    markers = []
    for e in events:
        if e.signal_type == "swing_change":
            is_buy = (e.direction == 1)
            t_sec = int(pd.Timestamp(e.time).timestamp())
            markers.append({
                "time": t_sec,
                "position": "belowBar" if is_buy else "aboveBar",
                "color": bull_color if is_buy else bear_color,
                "shape": "arrowUp" if is_buy else "arrowDown",
                "size": 1,
            })
    return markers


def build_hit_circles_from_events(
        events: List[SignalEvent],
        time_circle_color: str = "#FFEB3B",
        circle_color: str = "#FF00FF"
) -> List[Dict[str, Any]]:
    """Erzeugt Canvas-Hit-Circles direkt aus den normalisierten Events."""
    circles = []
    for e in events:
        if e.signal_type in ["circle_yellow", "circle_fuchsia"]:
            color = time_circle_color if e.signal_type == "circle_yellow" else circle_color
            t_sec = int(pd.Timestamp(e.time).timestamp())
            circles.append({
                "time": t_sec,
                "price": float(e.price),
                "color": color,
            })
    return circles