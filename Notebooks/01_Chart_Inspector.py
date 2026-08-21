import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    # ==========================================
    # 0. GLOBALE KONSTANTEN & KONFIGURATION
    # ========================================== 
    SYMBOL = "SILVER"
    TIMEFRAME = "M30"
    WINDOW_BARS = 1000         # Größe des sichtbaren Fensters (Kerzen)
    WARMUP = 200               # MA-Warmup links vom Fenster (nur Berechnung)
    TZ_OFFSET_HOURS = 2
    OFFSET_MAX = 20000         # Max. Scroll-Offset in Bars (Slider-Range)

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

    # Expliziter DB-Pfad (unabhängig vom chart_engine-Modul-Default)
    DB_MARKET_DATA = PROJ_ROOT / "data" / "market_data.duckdb"

    # Module zuerst als Modulobjekte importieren
    import algos.chart_engine
    import algos.chart_plugins
    import algos.ma_indicator
    import algos.grid_indicator

    # Erzwingt das Neuladen des Codes von der Festplatte bei jeder Zellenausführung
    # REIHENFOLGE WICHTIG: chart_plugins VOR chart_engine laden,
    # da chart_engine dessen Funktionen beim Reload frisch importiert.
    importlib.reload(algos.chart_plugins)
    importlib.reload(algos.chart_engine)
    importlib.reload(algos.ma_indicator)
    importlib.reload(algos.grid_indicator)

    # Klassen / Funktionen aus den frisch geladenen Modulen bereitstellen
    from algos.chart_engine import load_candles, show_chart
    from algos.ma_indicator import MAIndicator
    from algos.grid_indicator import GridIndicator

    # UI-Control: Fenster über die Zeitreihe verschieben
    # Slider GANZ RECHTS = neueste Daten (Offset 0), nach LINKS schieben
    # = Rolling in die Vergangenheit (Offset steigt). Wie eine Scrollbar.
    fenster = mo.ui.slider(
        start=0,
        stop=OFFSET_MAX,
        step=50,
        value=OFFSET_MAX,
        label="Fenster (rechts = aktuell · nach links schieben = ältere Daten)",
    )

    # WICHTIG: UI-Elemente müssen im Zellen-Output stehen, sonst werden sie
    # nicht gerendert. Der Slider wird in Zelle 3 (über der Grafik) angezeigt.
    mo.md(f"**Konfiguration:** {SYMBOL} {TIMEFRAME} · Fenster {WINDOW_BARS} Bars · Warmup {WARMUP} Bars")
    return (
        DB_MARKET_DATA,
        GridIndicator,
        MAIndicator,
        OFFSET_MAX,
        SYMBOL,
        TIMEFRAME,
        TZ_OFFSET_HOURS,
        WARMUP,
        WINDOW_BARS,
        fenster,
        load_candles,
        mo,
        show_chart,
    )


@app.cell(hide_code=True)
def _(
    DB_MARKET_DATA,
    OFFSET_MAX,
    SYMBOL,
    TIMEFRAME,
    TZ_OFFSET_HOURS,
    WARMUP,
    WINDOW_BARS,
    fenster,
    load_candles,
    mo,
):
    # ==========================================
    # 2. DATEN LADEN (Fenster + Warmup, reaktiv)
    # ==========================================
    # Slider ganz rechts = Offset 0 (neueste Daten); nach links schieben
    # erhöht den Offset (Rolling in die Vergangenheit).
    offset = OFFSET_MAX - int(fenster.value)

    df_base = load_candles(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        limit=WINDOW_BARS,
        tz_offset_hours=TZ_OFFSET_HOURS,
        end_offset_bars=offset,
        warmup_bars=WARMUP,
        db_path=DB_MARKET_DATA,
    )

    if len(df_base) <= 1:
        mo.md(f"**Keine Daten für Offset {offset}** – vor dem Datenanfang.")
    else:
        eff_warmup = min(WARMUP, len(df_base) - 1)
        t_first = df_base["time"].iloc[eff_warmup]
        t_last = df_base["time"].iloc[-1]
        mo.md(
            f"**Fenster:** {len(df_base) - eff_warmup} Kerzen "
            f"**{t_first} → {t_last}** "
            f"(Offset {offset} Bars vom Ende)"
        )
    return (df_base,)


@app.cell(hide_code=True)
def _(
    GridIndicator,
    MAIndicator,
    SYMBOL,
    TIMEFRAME,
    WARMUP,
    WINDOW_BARS,
    df_base,
    fenster,
    mo,
    show_chart,
):
    # ==========================================
    # 3. INDIKATOREN & SIGNALE + CHART
    # ==========================================
    df_calc = df_base.copy()

    # 1) MA-Instanz erstellen & berechnen
    ma = MAIndicator(
        ma_type="EHMA",
        period=6,
        smoothing=10,
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

    # 3. Chart anzeigen (Warmup links abgeschnitten, Fenster komplett sichtbar)
    #    Slider direkt über der Grafik (UI-Elemente müssen im Output stehen).
    chart = show_chart(
        df=df_calc,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        ma_indicator=ma,
        grid_indicator=grid,
        show_day_separators=True,
        show_signals=True,
        min_segment_len=3,
        warmup_bars=WARMUP,
        visible_bars=WINDOW_BARS,
        width=1200,
        height=550,
        scale_width=55,
    )
    mo.vstack([fenster, chart])
    return


if __name__ == "__main__":
    app.run()
