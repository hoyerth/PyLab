# algos/chart_engine.py
"""
Zentrales Rendering- und Chart-Engine-Modul für Lightweight Charts.
Pfad: algos/chart_engine.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
import marimo as mo
import numpy as np
import pandas as pd

from algos.grid_indicator import GridIndicator
from algos.ma_indicator import (
    DEFAULT_BEAR_COLOR,
    DEFAULT_BULL_COLOR,
    DEFAULT_LINE_WIDTH,
    MAIndicator,
)

__all__ = ["load_candles", "show_chart"]

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
    """Lädt historische OHLCV-Kerzen aus der DuckDB-Datenbank ohne Locks."""
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
    con = None
    try:
        con = duckdb.connect(database=str(db_path), read_only=True)
        df = con.execute(query).df().copy()
    finally:
        if con is not None:
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


# =============================================================================
# 2. ZENTRALE SHOW-FUNKTION
# =============================================================================
def show_chart(
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        ma_indicator: Optional[MAIndicator] = None,
        grid_indicator: Optional[GridIndicator] = None,
        show_day_separators: bool = True,
        show_signals: bool = True,
        visible_bars: int = 350,
        width: int = 1200,
        height: int = 550,
        scale_width: int = 55,
        bg_color: str = "#060B14",
        text_color: str = "#CBD5E1",
) -> Any:
    """Rendert Lightweight Charts mit flüssig mitlaufenden Dual-Circles."""
    if df.empty:
        return mo.md("**Keine Daten vorhanden.**")

    # 1. Kerzendaten
    time_sec = (df["time"].astype("int64") // 10 ** 9).values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    candles_data = [
        {"time": int(t), "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        for t, o, h, l, c in zip(time_sec, opens, highs, lows, closes)
    ]

    sample_price = float(closes[-1])
    precision = 5 if sample_price < 10 else (3 if sample_price < 1000 else 2)
    min_move = 1 / (10 ** precision)

    # 2. Moving Averages
    lines_payload = []
    if ma_indicator is not None:
        ma_cols = [
            c for c in df.columns
            if c.startswith("ma_") and not c.endswith("_bull") and not c.endswith("_bear")
        ]
        width_line = getattr(ma_indicator, "line_width", DEFAULT_LINE_WIDTH)
        for col in ma_cols:
            segments = ma_indicator.get_segments(df, col)
            for seg_df, color in segments:
                if len(seg_df) < 2:
                    continue
                seg_times = (seg_df["time"].astype("int64") // 10 ** 9).values
                seg_vals = seg_df[col].values
                seg_data = [
                    {"time": int(t), "value": float(v)}
                    for t, v in zip(seg_times, seg_vals)
                ]
                lines_payload.append({
                    "data": seg_data,
                    "color": color,
                    "width": width_line,
                    "style": 0,
                })

    # 3. Tagestrennlinien
    if show_day_separators:
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
            pad = max((row["day_high"] - row["day_low"]) * 0.08, row["day_high"] * 0.002)
            t_sec = int(pd.Timestamp(row["day_start"]).timestamp())
            lines_payload.append({
                "data": [
                    {"time": t_sec, "value": float(row["day_low"] - pad)},
                    {"time": t_sec, "value": float(row["day_high"] + pad)},
                ],
                "color": "rgba(66, 153, 225, 0.75)",
                "width": 1,
                "style": 2,
            })

    # 4. Gridlines & Dual Hit Circles
    hit_circles_payload = []
    if grid_indicator is not None:
        grid_res = grid_indicator.calculate(df)
        t_first = int(time_sec[0])
        t_last = int(time_sec[-1])

        for gl in grid_res.get("lines", []):
            lines_payload.append({
                "data": [
                    {"time": t_first, "value": float(gl["price"])},
                    {"time": t_last, "value": float(gl["price"])},
                ],
                "color": gl["color"],
                "width": gl["width"],
                "style": 0,
            })

        for h in grid_res.get("hit_circles", []):
            t_h = int(pd.Timestamp(h["time"]).timestamp())
            hit_circles_payload.append({
                "time": t_h,
                "price": float(h["price"]),
                "color": h.get("color", "#FF00FF"),
            })

    # 5. MA Signale
    candle_markers_payload = []
    if show_signals and ma_indicator is not None and "signal" in df.columns:
        signals = df[df["signal"] != 0]
        bull_c = getattr(ma_indicator, "bull_color", DEFAULT_BULL_COLOR)
        bear_c = getattr(ma_indicator, "bear_color", DEFAULT_BEAR_COLOR)

        for row in signals.itertuples(index=False):
            is_buy = (row.signal == 1)
            candle_markers_payload.append({
                "time": int(pd.Timestamp(row.time).timestamp()),
                "position": "belowBar" if is_buy else "aboveBar",
                "color": bull_c if is_buy else bear_c,
                "shape": "arrowUp" if is_buy else "arrowDown",
                "size": 1,
            })

    # 6. JSON Data Packs
    candles_json = json.dumps(candles_data)
    lines_json = json.dumps(lines_payload)
    hit_circles_json = json.dumps(hit_circles_payload)
    candle_markers_json = json.dumps(candle_markers_payload)

    from_time = int(time_sec[-visible_bars]) if len(time_sec) > visible_bars else int(time_sec[0])
    to_time = int(time_sec[-1])

    # 7. HTML Payload
    raw_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{
            width: 100%; height: 100%; overflow: hidden;
            background-color: {bg_color};
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, sans-serif;
        }}
        #chart-wrapper {{
            position: relative; width: 100%; height: 100%;
        }}
        #chart-container {{
            width: 100%; height: 100%; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
        }}
        #overlay-canvas {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 10;
        }}
        #watermark {{
            position: absolute; top: 10px; left: 12px; font-size: 13px; font-weight: 600;
            color: {text_color}; z-index: 20; pointer-events: none; user-select: none;
            background: rgba(6, 11, 20, 0.75); padding: 3px 8px; border-radius: 4px;
            border: 1px solid rgba(255, 255, 255, 0.12);
        }}
    </style>
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
</head>
<body>
    <div id="chart-wrapper">
        <div id="watermark">{symbol} · {timeframe}</div>
        <div id="chart-container"></div>
        <canvas id="overlay-canvas"></canvas>
    </div>

    <script>
        const container = document.getElementById('chart-container');
        const canvas = document.getElementById('overlay-canvas');
        const ctx = canvas.getContext('2d');

        const chart = LightweightCharts.createChart(container, {{
            layout: {{
                background: {{ type: 'solid', color: '{bg_color}' }},
                textColor: '{text_color}',
                fontSize: 12,
            }},
            grid: {{
                vertLines: {{ color: 'rgba(255, 255, 255, 0.07)' }},
                horzLines: {{ color: 'rgba(255, 255, 255, 0.07)' }},
            }},
            rightPriceScale: {{
                visible: true,
                borderVisible: true,
                borderColor: '#4A5568',
                autoScale: true,
                minimumWidth: {scale_width},
                scaleMargins: {{ top: 0.08, bottom: 0.08 }},
                textColor: '{text_color}',
                drawTicks: true,
                entireTextOnly: false,
            }},
            leftPriceScale: {{ visible: false }},
            timeScale: {{
                visible: true,
                borderVisible: true,
                borderColor: '#4A5568',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 8,
            }},
            crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
        }});

        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            priceScaleId: 'right',
            priceLineVisible: false,
            lastValueVisible: false,
            priceFormat: {{
                type: 'price',
                precision: {precision},
                minMove: {min_move},
            }},
        }});
        candleSeries.setData({candles_json});

        // Grid- und MA-Linien
        const linesData = {lines_json};
        linesData.forEach(item => {{
            const lineSeries = chart.addLineSeries({{
                color: item.color,
                lineWidth: item.width,
                lineStyle: item.style,
                priceScaleId: 'right',
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
                priceFormat: {{
                    type: 'price',
                    precision: {precision},
                    minMove: {min_move},
                }},
            }});
            lineSeries.setData(item.data);
        }});

        // Signal-Pfeile
        const candleMarkers = {candle_markers_json};
        if (candleMarkers.length > 0) {{
            candleMarkers.sort((a, b) => a.time - b.time);
            candleSeries.setMarkers(candleMarkers);
        }}

        // Circles Rendering
        const hitCircles = {hit_circles_json};
        let isRenderPending = false;

        function renderCircles() {{
            isRenderPending = false;
            const dpr = window.devicePixelRatio || 1;
            const w = container.clientWidth;
            const h = container.clientHeight;

            if (w === 0 || h === 0) return;

            if (canvas.width !== w * dpr || canvas.height !== h * dpr) {{
                canvas.width = w * dpr;
                canvas.height = h * dpr;
                canvas.style.width = w + 'px';
                canvas.style.height = h + 'px';
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            }}

            ctx.clearRect(0, 0, w, h);

            const timeScale = chart.timeScale();

            hitCircles.forEach(pt => {{
                const x = timeScale.timeToCoordinate(pt.time);
                const y = candleSeries.priceToCoordinate(pt.price);

                if (x !== null && y !== null && x >= 0 && x <= w && y >= 0 && y <= h) {{
                    ctx.beginPath();
                    ctx.arc(x, y, 4, 0, Math.PI * 2);
                    ctx.fillStyle = pt.color;
                    ctx.fill();
                    ctx.lineWidth = 1.2;
                    ctx.strokeStyle = '#060B14';
                    ctx.stroke();
                }}
            }});
        }}

        function requestCircleRender() {{
            if (!isRenderPending) {{
                isRenderPending = true;
                requestAnimationFrame(renderCircles);
            }}
        }}

        chart.timeScale().subscribeVisibleLogicalRangeChange(requestCircleRender);
        chart.timeScale().subscribeVisibleTimeRangeChange(requestCircleRender);

        container.addEventListener('pointermove', requestCircleRender);
        container.addEventListener('pointerdown', requestCircleRender);
        container.addEventListener('wheel', requestCircleRender, {{ passive: true }});
        window.addEventListener('mouseup', requestCircleRender);

        chart.timeScale().setVisibleRange({{
            from: {from_time},
            to: {to_time}
        }});

        function resizeChart() {{
            const w = container.clientWidth;
            const h = container.clientHeight;
            if (w > 50 && h > 50) {{
                chart.applyOptions({{ width: w, height: h }});
                requestCircleRender();
            }}
        }}

        window.addEventListener('resize', resizeChart);

        // Mehrstufige Initialisierung, bis Preisskala Koordinaten liefert
        setTimeout(requestCircleRender, 50);
        setTimeout(requestCircleRender, 150);
        setTimeout(requestCircleRender, 300);
    </script>
</body>
</html>
"""

    return mo.iframe(
        raw_html,
        width="100%",
        height=f"{height}px",
    )