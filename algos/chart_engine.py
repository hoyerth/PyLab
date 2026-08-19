# algos/chart_engine.py
"""
Zentrales Rendering- und Chart-Engine-Modul für Lightweight Charts.
Pfad: algos/chart_engine.py
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
import numpy as np
import pandas as pd
from lightweight_charts import JupyterChart

from algos.grid_indicator import GridIndicator
from algos.ma_indicator import (
    DEFAULT_BEAR_COLOR,
    DEFAULT_BULL_COLOR,
    DEFAULT_LINE_WIDTH,
    MAIndicator,
)

# Standard-Pfad zur DuckDB Datenbank
DEFAULT_DB_PATH = Path(r"F:\Python\PyTrader\data\market_data.duckdb")


# =============================================================================
# 1. DATENLADEN
# =============================================================================
def load_candles(
        symbol: str,
        timeframe: str,
        limit: int,
        tz_offset_hours: int = 0,
        db_path: Path = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """Lädt historische OHLCV-Kerzen aus der DuckDB-Datenbank."""
    query = f"""
        SELECT "time", open, high, low, close, tick_volume AS volume
        FROM (
            SELECT "time", open, high, low, close, tick_volume
            FROM ohlcv_bars 
            WHERE LOWER(symbol) = LOWER('{symbol}') 
              AND LOWER(timeframe) = LOWER('{timeframe}')
              AND "time" IS NOT NULL 
              AND open IS NOT NULL AND high IS NOT NULL 
              AND low IS NOT NULL AND close IS NOT NULL
            ORDER BY "time" DESC
            LIMIT {limit}
        ) sub
        ORDER BY "time" ASC;
    """
    with duckdb.connect(database=str(db_path), read_only=True) as con:
        df = con.execute(query).df()

    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)

    df["time"] = df["time"].astype("datetime64[ns]")

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype("float64")

    return df


# =============================================================================
# 2. PLOT-SUBMODULE
# =============================================================================
def _plot_day_separators(chart: JupyterChart, df: pd.DataFrame) -> None:
    """Zeichnet vertikale gestrichelte Tagestrennlinien."""
    times = df["time"]
    dates = times.dt.date
    daily_extrema = df.groupby(dates).agg(
        day_start=("time", "first"),
        day_low=("low", "min"),
        day_high=("high", "max"),
    )
    first_date = dates.iloc[0]

    for d, row in daily_extrema.iterrows():
        if d == first_date:
            continue
        pad = (row["day_high"] - row["day_low"]) * 0.08
        pad = max(pad, row["day_high"] * 0.002)

        line = chart.create_line(
            color="rgba(41, 98, 255, 0.40)",
            width=1,
            style="dashed",
            price_line=False,
            price_label=False,
        )
        line.set(pd.DataFrame({
            "time": [row["day_start"], row["day_start"]],
            "value": [row["day_low"] - pad, row["day_high"] + pad],
        }))


def _plot_mas(chart: JupyterChart, df: pd.DataFrame, ma_indicator: Optional[MAIndicator]) -> None:
    """Zeichnet segmentierte MAs farbig nach Trendsteigung."""
    ma_cols = [
        c for c in df.columns
        if c.startswith("ma_") and not c.endswith("_bull") and not c.endswith("_bear")
    ]
    active_ind = (
        ma_indicator if ma_indicator is not None
        else MAIndicator(bull_color=DEFAULT_BULL_COLOR, bear_color=DEFAULT_BEAR_COLOR)
    )
    width = getattr(active_ind, "line_width", DEFAULT_LINE_WIDTH)

    for col in ma_cols:
        segments = active_ind.get_segments(df, col)
        for seg_df, color in segments:
            if len(seg_df) < 2:
                continue
            line = chart.create_line(color=color, width=width, price_line=False, price_label=False)
            line.set(pd.DataFrame({"time": seg_df["time"], "value": seg_df[col].astype(float)}))


def _plot_grid_and_hits(chart: JupyterChart, df: pd.DataFrame, grid_indicator: GridIndicator) -> None:
    """Zeichnet durchgehende Gridlines und bindet Hit-Circles exakt auf Level-Höhe ein."""
    grid_res = grid_indicator.calculate(df)

    t_first = df["time"].iloc[0]
    t_last = df["time"].iloc[-1]

    # 1. Gridlines durchgehend spannen (ohne Y-Achsen Labels)
    lines = grid_res.get("lines", [])
    if lines:
        for gl in lines:
            g_line = chart.create_line(
                color=gl["color"],
                width=gl["width"],
                price_line=False,
                price_label=False,
            )
            g_line.set(pd.DataFrame({
                "time": [t_first, t_last],
                "value": [gl["price"], gl["price"]]
            }))

    # 2. Hit Circles als High-Speed Trägerserie auf exakter Grid-Höhe
    hits = grid_res.get("hit_circles", [])
    if hits:
        hits_by_price = {}
        for h in hits:
            p = round(float(h["price"]), 6)
            hits_by_price.setdefault(p, []).append(h)

        for p_lvl, hit_list in hits_by_price.items():
            pts_df = pd.DataFrame(hit_list)
            pt_line = chart.create_line(
                color="rgba(0,0,0,0)",
                width=0,
                price_line=False,
                price_label=False,
            )
            pt_line.set(pd.DataFrame({
                "time": pts_df["time"],
                "value": p_lvl
            }))

            for row in pts_df.itertuples(index=False):
                pt_line.marker(
                    time=row.time,
                    position="inside",
                    shape="circle",
                    color=row.color,
                    text="",
                )


def _plot_signals(chart: JupyterChart, df: pd.DataFrame, ma_indicator: Optional[MAIndicator]) -> None:
    """Zeichnet Kauf-/Verkaufspfeile am Kerzenchart."""
    if "signal" in df.columns:
        signals = df[df["signal"] != 0]
        bull_c = getattr(ma_indicator, "bull_color", DEFAULT_BULL_COLOR) if ma_indicator else DEFAULT_BULL_COLOR
        bear_c = getattr(ma_indicator, "bear_color", DEFAULT_BEAR_COLOR) if ma_indicator else DEFAULT_BEAR_COLOR

        for row in signals.itertuples(index=False):
            chart.marker(
                time=row.time,
                position="below" if row.signal == 1 else "above",
                shape="arrow_up" if row.signal == 1 else "arrow_down",
                color=bull_c if row.signal == 1 else bear_c,
                text="",
            )


# =============================================================================
# 3. ZENTRALE SHOW-FUNKTION
# =============================================================================
def show_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    ma_indicator: Optional[MAIndicator] = None,
    grid_indicator: Optional[GridIndicator] = None,
    show_day_separators: bool = True,
    visible_bars: int = 350,
    width: int = 1200,
    height: int = 550,
    bg_color: str = "#060B14",       # Sehr dunkles Tiefblau (Midnight Navy)
    text_color: str = "#A0AEC0",     # Dezenter Kontrast
) -> Any:
    """Erstellt den fertigen Jupyter Lightweight Chart."""
    chart = JupyterChart(width=width, height=height)
    chart.layout(background_color=bg_color, text_color=text_color)
    chart.topbar.textbox("symbol_info", f"{symbol} · {timeframe}")

    # Basis-Kerzen
    chart.price_scale(
        auto_scale=True,
        mode="normal",
        scale_margin_top=0.06,
        scale_margin_bottom=0.06,
    )
    chart.price_line(label_visible=False, line_visible=False)
    chart.set(df[["time", "open", "high", "low", "close"]])

    if len(df) > visible_bars:
        chart.set_visible_range(df["time"].iloc[-visible_bars], df["time"].iloc[-1])

    # Module rendern
    if show_day_separators:
        _plot_day_separators(chart, df)

    _plot_mas(chart, df, ma_indicator)

    if grid_indicator is not None:
        _plot_grid_and_hits(chart, df, grid_indicator)

    _plot_signals(chart, df, ma_indicator)

    return chart.load()