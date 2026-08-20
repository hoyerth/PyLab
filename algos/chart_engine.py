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
import pandas as pd

from algos.grid_indicator import GridIndicator
from algos.ma_indicator import MAIndicator
from algos.chart_plugins import (
    build_candles_payload,
    build_day_separators_payload,
    build_grid_payload,
    build_ma_lines_payload,
    build_signal_markers_payload,
)

__all__ = ["load_candles", "show_chart"]

DEFAULT_DB_PATH = Path(r"F:\Python\PyTrader\data\market_data.duckdb")

# Lokale Kopie der Lightweight-Charts-Standalone-Library (Offline-Fähigkeit).
# Pfad: js/lightweight-charts.standalone.production.js (Version 4.1.3)
LIGHTWEIGHT_CHARTS_PATH = Path(__file__).resolve().parent.parent / "js" / "lightweight-charts.standalone.production.js"
CDN_SCRIPT_URL = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"
_cached_lwc_js: Optional[str] = None


def _load_lightweight_charts_script() -> str:
    """Liefert das Lightweight-Charts-Script-Tag.

    Bevorzugt wird die lokale Datei inline eingebettet (offline-fähig, kein
    CDN-Zugriff nötig). Ist sie nicht vorhanden, fällt der Code auf das CDN
    zurück. Das Ergebnis wird pro Prozess gecacht.
    """
    global _cached_lwc_js
    if _cached_lwc_js is not None:
        return _cached_lwc_js

    script_tag = ""
    if LIGHTWEIGHT_CHARTS_PATH.is_file():
        try:
            js = LIGHTWEIGHT_CHARTS_PATH.read_text(encoding="utf-8")
            # '</script' innerhalb des JS sicher escapen (kommt im Minified-Code
            # üblicherweise nicht vor, schützt aber gegen HTML-Tag-Injection).
            js = js.replace("</script", r"<\/script")
            script_tag = f"<script>{js}</script>"
        except OSError:
            pass

    if not script_tag:
        script_tag = f'<script src="{CDN_SCRIPT_URL}"></script>'

    _cached_lwc_js = script_tag
    return script_tag


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
    """Orchestrierungsfunktion für das Rendering."""
    if df.empty:
        return mo.md("**Keine Daten vorhanden.**")

    # 1. Daten über Plugins aufbereiten
    candles, precision, min_move = build_candles_payload(df)
    t_first, t_last = candles[0]["time"], candles[-1]["time"]

    lines = build_ma_lines_payload(df, ma_indicator)
    if show_day_separators:
        lines.extend(build_day_separators_payload(df))

    grid_lines, hit_circles = build_grid_payload(df, grid_indicator, t_first, t_last)
    lines.extend(grid_lines)

    markers = build_signal_markers_payload(df, ma_indicator) if show_signals else []
    from_time = candles[-visible_bars]["time"] if len(candles) > visible_bars else t_first

    # 2. Template zusammenbauen
    # Lokale Lightweight-Charts-Library inline einbetten (offline-fähig),
    # statt sie vom unpkg-CDN zu laden.
    lwc_script = _load_lightweight_charts_script()
    raw_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; background-color: {bg_color}; font-family: sans-serif; }}
        #chart-wrapper {{ position: relative; width: 100%; height: 100%; }}
        #chart-container {{ width: 100%; height: 100%; position: absolute; top: 0; left: 0; right: 0; bottom: 0; }}
        #overlay-canvas {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 10; }}
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
            layout: {{ background: {{ type: 'solid', color: '{bg_color}' }}, textColor: '{text_color}', fontSize: 12 }},
            grid: {{ vertLines: {{ color: 'rgba(255, 255, 255, 0.07)' }}, horzLines: {{ color: 'rgba(255, 255, 255, 0.07)' }} }},
            rightPriceScale: {{ visible: true, borderVisible: true, borderColor: '#4A5568', autoScale: true, minimumWidth: {scale_width}, scaleMargins: {{ top: 0.08, bottom: 0.08 }}, textColor: '{text_color}' }},
            leftPriceScale: {{ visible: false }},
            timeScale: {{ visible: true, borderVisible: true, borderColor: '#4A5568', timeVisible: true, rightOffset: 8 }},
            crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
        }});

        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            priceScaleId: 'right', priceLineVisible: false, lastValueVisible: false,
            priceFormat: {{ type: 'price', precision: {precision}, minMove: {min_move} }},
        }});
        candleSeries.setData({json.dumps(candles)});

        const linesData = {json.dumps(lines)};
        linesData.forEach(item => {{
            const ls = chart.addLineSeries({{
                color: item.color, lineWidth: item.width, lineStyle: item.style,
                priceScaleId: 'right', priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                priceFormat: {{ type: 'price', precision: {precision}, minMove: {min_move} }},
            }});
            ls.setData(item.data);
        }});

        const markersData = {json.dumps(markers)};
        if (markersData.length > 0) {{
            markersData.sort((a, b) => a.time - b.time);
            candleSeries.setMarkers(markersData);
        }}

        const hitCircles = {json.dumps(hit_circles)};
        let isRenderPending = false;

        function renderCircles() {{
            isRenderPending = false;
            const dpr = window.devicePixelRatio || 1;
            const w = container.clientWidth;
            const h = container.clientHeight;
            if (w === 0 || h === 0) return;

            if (canvas.width !== w * dpr || canvas.height !== h * dpr) {{
                canvas.width = w * dpr; canvas.height = h * dpr;
                canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
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

        chart.timeScale().setVisibleRange({{ from: {from_time}, to: {t_last} }});

        function resizeChart() {{
            const w = container.clientWidth, h = container.clientHeight;
            if (w > 50 && h > 50) {{
                chart.applyOptions({{ width: w, height: h }});
                requestCircleRender();
            }}
        }}
        window.addEventListener('resize', resizeChart);
        setTimeout(requestCircleRender, 60);
        setTimeout(requestCircleRender, 200);
    </script>
</body>
</html>
"""

    # CDN-Script-Tag durch lokal eingebettete Library ersetzen (offline-fähig).
    # Das Inline-JS enthält geschweifte Klammern und darf daher nicht direkt
    # in das f-string-Template eingesetzt werden.
    raw_html = raw_html.replace(
        '<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>',
        lwc_script,
    )

    return mo.iframe(raw_html, width="100%", height=f"{height}px")