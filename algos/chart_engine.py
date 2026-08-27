"""Zentrales Rendering- und Chart-Engine-Modul für Lightweight Charts.

Pfad: algos/chart_engine.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
import marimo as mo
import pandas as pd

from algos.chart_plugins import (
    build_candles_payload,
    build_day_separators_payload,
    build_grid_payload,
    build_hit_circles_from_events,
    build_ma_lines_from_result,
    build_ma_lines_payload,
    build_signal_markers_from_events,
    build_signal_markers_payload,
)
from algos.grid_indicator import GridIndicator
from algos.ma_indicator import MAIndicator
from algos.signal_events import IndicatorResult, SignalEvent

__all__ = ["load_candles", "show_chart"]

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
)

LIGHTWEIGHT_CHARTS_PATH = (
    Path(__file__).resolve().parent.parent
    / "js"
    / "lightweight-charts.standalone.production.js"
)
CDN_SCRIPT_URL = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"
_cached_lwc_js: Optional[str] = None


def _load_lightweight_charts_script() -> str:
    """Liefert das Lightweight-Charts-Script-Tag."""
    global _cached_lwc_js
    if _cached_lwc_js is not None:
        return _cached_lwc_js

    script_tag = ""
    if LIGHTWEIGHT_CHARTS_PATH.is_file():
        try:
            js = LIGHTWEIGHT_CHARTS_PATH.read_text(encoding="utf-8")
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
    end_offset_bars: int = 0,
    warmup_bars: int = 0,
) -> pd.DataFrame:
    """Lädt historische OHLCV-Kerzen aus der DuckDB-Datenbank."""
    fetch_limit = int(limit) + int(end_offset_bars) + int(warmup_bars)
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
            LIMIT {fetch_limit}
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
        return pd.DataFrame(
            columns=["time", "open", "high", "low", "close", "volume"]
        )

    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)

    df["time"] = df["time"].astype("datetime64[ns]")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype("float64")

    if end_offset_bars > 0:
        df = df.iloc[:-int(end_offset_bars)]
    df = df.tail(int(limit) + int(warmup_bars)).reset_index(drop=True)

    return df


def show_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    ma_indicator: Optional[MAIndicator] = None,
    grid_indicator: Optional[GridIndicator] = None,
    results: Optional[List[IndicatorResult]] = None,
    show_day_separators: bool = True,
    show_signals: bool = True,
    min_segment_len: int = 3,
    warmup_bars: int = 0,
    visible_bars: int = 350,
    width: int = 1200,
    height: int = 550,
    scale_width: int = 55,
    bg_color: str = "#060B14",
    text_color: str = "#CBD5E1",
) -> Any:
    """Rendert den Chart mit Kerzen, Indikatoren, Markern und Canvas-Overlays."""
    if df.empty:
        return mo.md("**Keine Daten vorhanden.**")

    warmup = min(int(warmup_bars), max(0, len(df) - 1))
    calc_df = df.iloc[warmup:]
    if len(calc_df) < 2:
        return mo.md(f"**Fenster nicht verfügbar** – Offset vor Datenanfang.")

    candles, precision, min_move = build_candles_payload(calc_df)
    t_first, t_last = candles[0]["time"], candles[-1]["time"]

    all_events: List[SignalEvent] = []
    grid_lines: List[Dict[str, Any]] = []
    ma_plot_metas: List[Dict[str, Any]] = []
    grid_plot_meta: Optional[Dict[str, Any]] = None
    if results:
        for r in results:
            all_events.extend(r.events)
            rmeta = r.plot_meta or {}
            rtype = rmeta.get("type")
            if rtype == "grid":
                grid_lines = rmeta.get("lines", [])
                grid_plot_meta = rmeta
            elif rtype == "ma":
                ma_plot_metas.append(rmeta)

    day_separators = (
        build_day_separators_payload(calc_df) if show_day_separators else []
    )

    if results:
        ma_lines = []
        for mp in ma_plot_metas:
            ma_lines.extend(build_ma_lines_from_result(df, mp, min_segment_len))

        ma_colors = ma_plot_metas[0] if ma_plot_metas else {}
        arrow_events = [
            e
            for e in all_events
            if e.signal_type not in ("circle_yellow", "circle_fuchsia")
        ]
        markers = (
            build_signal_markers_from_events(
                arrow_events,
                bull_color=ma_colors.get("bull_color", "#089981"),
                bear_color=ma_colors.get("bear_color", "#F23645"),
            )
            if show_signals
            else []
        )
        hit_circles = build_hit_circles_from_events(
            all_events,
            time_circle_color=(grid_plot_meta or {}).get(
                "time_circle_color", "#FFEB3B"
            ),
            circle_color=(grid_plot_meta or {}).get(
                "circle_color", "#FF00FF"
            ),
        )
    else:
        ma_lines = build_ma_lines_payload(df, ma_indicator, min_segment_len)
        grid_lines, hit_circles = build_grid_payload(
            df, grid_indicator, t_first, t_last
        )
        markers = (
            build_signal_markers_payload(df, ma_indicator)
            if show_signals
            else []
        )

    markers = [m for m in markers if m["time"] >= t_first]
    hit_circles = [c for c in hit_circles if c["time"] >= t_first]

    candle_times_sec = [c["time"] for c in candles]
    _diffs = [b - a for a, b in zip(candle_times_sec, candle_times_sec[1:])]
    bar_spacing = int(sorted(_diffs)[len(_diffs) // 2]) if _diffs else 1800

    # Nur MA-Marker auf T+1 verschieben; geometrische Jump-Marker bleiben exakt auf Bar T
    if markers and candles:
        time_to_idx = {t: i for i, t in enumerate(candle_times_sec)}
        is_ma_run = bool(ma_plot_metas)
        if is_ma_run:
            shifted = []
            for m in markers:
                i = time_to_idx.get(m["time"])
                if i is not None and i + 1 < len(candle_times_sec):
                    m_copy = dict(m)
                    m_copy["time"] = candle_times_sec[i + 1]
                    shifted.append(m_copy)
            markers = shifted

    from_time = (
        candles[-visible_bars]["time"]
        if len(candles) > visible_bars
        else t_first
    )

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

        const markersData = {json.dumps(markers)};
        if (markersData.length > 0) {{
            markersData.sort((a, b) => a.time - b.time);
            candleSeries.setMarkers(markersData);
        }}

        const maLines = {json.dumps(ma_lines)};
        const gridLines = {json.dumps(grid_lines)};
        const daySeparators = {json.dumps(day_separators)};
        const hitCircles = {json.dumps(hit_circles)};
        const barSpacing = {bar_spacing};
        let isRenderPending = false;

        function renderOverlay() {{
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

            for (const gl of gridLines) {{
                const y = candleSeries.priceToCoordinate(gl.price);
                if (y !== null && y >= 0 && y <= h) {{
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(w, y);
                    ctx.lineWidth = gl.width;
                    ctx.strokeStyle = gl.color;
                    ctx.stroke();
                }}
            }}

            for (const ds of daySeparators) {{
                const x = timeScale.timeToCoordinate(ds.time);
                if (x === null || x < 0 || x > w) continue;
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, h);
                ctx.lineWidth = ds.width;
                ctx.strokeStyle = ds.color;
                ctx.setLineDash(ds.dash || [4, 4]);
                ctx.stroke();
            }}
            ctx.setLineDash([]);

            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            for (const seg of maLines) {{
                ctx.beginPath();
                ctx.lineWidth = seg.width;
                ctx.strokeStyle = seg.color;
                let penDown = false;
                for (const pt of seg.data) {{
                    const px = timeScale.timeToCoordinate(pt.time);
                    const py = candleSeries.priceToCoordinate(pt.value);
                    if (px !== null && py !== null) {{
                        if (penDown) {{
                            ctx.lineTo(px, py);
                        }} else {{
                            ctx.moveTo(px, py);
                            penDown = true;
                        }}
                    }} else {{
                        penDown = false;
                    }}
                }}
                if (penDown) ctx.stroke();
            }}

            const maxHitGap = barSpacing * 1.5;
            const hitsByPrice = {{}};
            for (const pt of hitCircles) {{
                const x = timeScale.timeToCoordinate(pt.time);
                const y = candleSeries.priceToCoordinate(pt.price);
                if (x !== null && y !== null && x >= 0 && x <= w && y >= 0 && y <= h) {{
                    const key = String(pt.price);
                    (hitsByPrice[key] = hitsByPrice[key] || []).push({{time: pt.time, x: x, y: y, color: pt.color}});
                }}
            }}
            for (const key in hitsByPrice) {{
                const pts = hitsByPrice[key].sort((a, b) => a.time - b.time);
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = pts[0].color;
                ctx.globalAlpha = 0.55;
                ctx.beginPath();
                for (let i = 0; i < pts.length; i++) {{
                    if (i === 0) {{
                        ctx.moveTo(pts[i].x, pts[i].y);
                    }} else if (pts[i].time - pts[i - 1].time <= maxHitGap) {{
                        ctx.lineTo(pts[i].x, pts[i].y);
                    }} else {{
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(pts[i].x, pts[i].y);
                    }}
                }}
                ctx.stroke();
                ctx.globalAlpha = 1.0;
                for (const p of pts) {{
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
                    ctx.fillStyle = p.color;
                    ctx.fill();
                    ctx.lineWidth = 1.2;
                    ctx.strokeStyle = '#060B14';
                    ctx.stroke();
                }}
            }}
        }}

        function requestOverlayRender() {{
            if (!isRenderPending) {{
                isRenderPending = true;
                requestAnimationFrame(renderOverlay);
            }}
        }}

        chart.timeScale().subscribeVisibleLogicalRangeChange(requestOverlayRender);
        chart.timeScale().subscribeVisibleTimeRangeChange(requestOverlayRender);
        container.addEventListener('pointermove', requestOverlayRender);
        container.addEventListener('pointerdown', requestOverlayRender);
        container.addEventListener('wheel', requestOverlayRender, {{ passive: true }});
        window.addEventListener('mouseup', requestOverlayRender);

        chart.timeScale().setVisibleRange({{ from: {from_time}, to: {t_last} }});

        function resizeChart() {{
            const w = container.clientWidth, h = container.clientHeight;
            if (w > 50 && h > 50) {{
                chart.applyOptions({{ width: w, height: h }});
                requestOverlayRender();
            }}
        }}
        window.addEventListener('resize', resizeChart);
        setTimeout(requestOverlayRender, 60);
        setTimeout(requestOverlayRender, 200);
    </script>
</body>
</html>
"""

    raw_html = raw_html.replace(
        '<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>',
        lwc_script,
    )

    return mo.iframe(raw_html, width="100%", height=f"{height}px")