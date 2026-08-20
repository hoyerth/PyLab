import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell
def _():
    # ==========================================
    # 0. GLOBALE KONSTANTEN & KONFIGURATION
    # ========================================== 
    SYMBOL = "SILVER"
    TIMEFRAME = "M30"
    LIMIT = 3000
    TZ_OFFSET_HOURS = 2

    # ==========================================
    # 1. SETUP & IMPORTE
    # ==========================================
    import sys
    import importlib
    from pathlib import Path
    import marimo as mo

    PROJ_ROOT = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path.cwd()
    if str(PROJ_ROOT) not in sys.path:
        sys.path.append(str(PROJ_ROOT))

    # Module zuerst als Modulobjekte importieren
    import algos.chart_engine
    import algos.ma_indicator
    import algos.grid_indicator

    # Erzwingt das Neuladen des Codes von der Festplatte bei jeder Zellenausführung
    importlib.reload(algos.chart_engine)
    importlib.reload(algos.ma_indicator)
    importlib.reload(algos.grid_indicator)

    # Klassen / Funktionen aus den frisch geladenen Modulen bereitstellen
    from algos.chart_engine import load_candles, show_chart
    from algos.ma_indicator import MAIndicator
    from algos.grid_indicator import GridIndicator

    # ==========================================
    # 2. DATEN LADEN
    # ==========================================
    df_base = load_candles(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        limit=LIMIT,
        tz_offset_hours=TZ_OFFSET_HOURS,
    )

    mo.md(f"✅ **Daten geladen:** {len(df_base)} Kerzen für {SYMBOL} ({TIMEFRAME}, Limit={LIMIT}).")
    return GridIndicator, MAIndicator, SYMBOL, TIMEFRAME, df_base, show_chart


@app.cell
def _(GridIndicator, MAIndicator, SYMBOL, TIMEFRAME, df_base, show_chart):
    # ==========================================
    # 1. HIER INDIKATOREN & SIGNALE DEFINIEREN
    # ==========================================
    df_calc = df_base.copy()

    # 1) MA-Instanz erstellen & berechnen
    ma = MAIndicator(
        ma_type="TEMA",
        period=17,
        smoothing=5,
        alpha_factor=3.0,
    )
    df_calc = ma.apply(df_calc, generate_signals=True)

    # 2) GridIndicator instanziieren
    grid = GridIndicator({
        "step_size": 0.50,
        "steps_around": 4,
        "custom_levels": [64.30, 63.70],
        "visit_pct": 0.05,
        "grid_line_width": 1,
        "custom_line_width": 2,
        "line_color": "rgba(41, 121, 255, 0.85)",
        "use_time_filter": True,
        "time_window_mins": 5,
        "show_lines": True,
        "show_circles": True,
    })

    # 3. Chart anzeigen
    show_chart(
        df=df_calc,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        ma_indicator=ma,
        grid_indicator=grid,
        show_day_separators=True,
        show_signals=True,
        visible_bars=350,
        width=1200,
        height=550,
        scale_width=55,
    )
    return


if __name__ == "__main__":
    app.run()
