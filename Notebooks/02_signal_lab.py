import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path
    from itertools import product
    import pandas as pd
    import marimo as mo

    PROJ_ROOT = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path.cwd()
    if str(PROJ_ROOT) not in sys.path:
        sys.path.append(str(PROJ_ROOT))

    from algos.chart_engine import load_candles
    from algos.ma_indicator import MAIndicator
    from algos.signal_service import DuckDBSignalService

    DB_MARKET = PROJ_ROOT / "data" / "market_data.duckdb"
    DB_ANALYTICS = PROJ_ROOT / "data" / "analytics_data.duckdb"

    service = DuckDBSignalService(db_path=DB_ANALYTICS)

    btn_start = mo.ui.button(label="🚀 Massentest (Parameter Sweep) starten", value=False)

    mo.vstack([
        mo.md("## 🧪 Signal Lab: Vektorisierte Massenberechnung"),
        btn_start
    ])
    return (
        DB_MARKET,
        MAIndicator,
        btn_start,
        load_candles,
        mo,
        product,
        service,
    )


@app.cell
def _(DB_MARKET, MAIndicator, btn_start, load_candles, mo, product, service):
    if not btn_start.value:
        out = mo.md("_Klicke auf den Button oben, um den Massentest zu starten._")
    else:
        SYMBOL = "SILVER"
        TIMEFRAME = "M30"
        df_raw = load_candles(
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            limit=10000,
            warmup_bars=200,
            db_path=DB_MARKET,
        )

        periods = [4, 6, 8, 12, 16]
        alphas = [2.0, 3.0, 4.0]

        run_ids = []
        for p, a in product(periods, alphas):
            ma = MAIndicator(ma_type="EHMA", period=p, smoothing=10, alpha_factor=a)
            res = ma.compute(df_raw, symbol=SYMBOL, timeframe=TIMEFRAME)
            run_id = service.store_result(res, warmup_bars=200)
            run_ids.append(run_id)

        events_summary = service.get_events(symbol=SYMBOL, timeframe=TIMEFRAME)
        out = mo.vstack([
            mo.md(
                f"**Fertig:** {len(run_ids)} Parameter-Sets verarbeitet "
                f"({len(events_summary)} Events in DB, Duplikate idempotent verhindert)."
            ),
            mo.ui.table(events_summary.head(50), page_size=15),
        ])
    out
    return


if __name__ == "__main__":
    app.run()
