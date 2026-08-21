import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import sys
    import threading
    import datetime as dt
    from pathlib import Path
    import marimo as mo

    PROJ_ROOT = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path.cwd()
    if str(PROJ_ROOT) not in sys.path:
        sys.path.append(str(PROJ_ROOT))

    # signal_lab-Module (Logik liegt nicht im Notebook)
    from signal_lab.ui_state import load_state, save_state
    from signal_lab.run_definition import (
        available_symbols,
        available_timeframes,
        available_date_range,
        build_run_definition,
        favorite_symbols,
    )
    from signal_lab.naming import build_run_name
    from signal_lab.sweep_runner import run_sweep_sequential
    from signal_lab import sweep_ui
    from algos.signal_service import DuckDBSignalService

    DB_MARKET = PROJ_ROOT / "data" / "market_data.duckdb"
    DB_ANALYTICS = PROJ_ROOT / "data" / "analytics_data.duckdb"
    DB_APP = PROJ_ROOT / "data" / "app_data.duckdb"

    state = load_state()

    # Verfügbare Symbole (Favoriten zuerst) & TFs & Datumsspanne
    FAV = favorite_symbols(DB_APP)
    SYMBOLS = available_symbols(DB_MARKET, favorite_symbols=FAV)
    TIMEFRAMES = available_timeframes(DB_MARKET)
    DATE_MIN, DATE_MAX = available_date_range(DB_MARKET)
    MA_TYPES = ["EHMA", "TEMA", "DEMA", "EMA", "SMA"]

    service = DuckDBSignalService(db_path=DB_ANALYTICS)

    mo.md("## 🧪 Signal Lab v2 — Massentests & Konfluenz-Pipeline")
    return (
        DATE_MAX,
        DATE_MIN,
        DB_ANALYTICS,
        DB_MARKET,
        FAV,
        MA_TYPES,
        SYMBOLS,
        TIMEFRAMES,
        build_run_definition,
        build_run_name,
        dt,
        mo,
        run_sweep_sequential,
        save_state,
        service,
        state,
        sweep_ui,
        threading,
    )


@app.cell
def _(FAV, SYMBOLS, TIMEFRAMES, mo, state):
    # ==========================================
    # 1. SYMBOLE & TIMEFRAMES (Mehrfachauswahl)
    # ==========================================
    sym_options = {}
    for s in SYMBOLS:
        sym_options[f"⭐ {s}" if s in FAV else s] = s

    sel_symbols = mo.ui.multiselect(
        sym_options,
        value=[s for s in state["symbols"] if s in SYMBOLS],
        label="Symbole",
    )
    sel_tfs = mo.ui.multiselect(
        TIMEFRAMES,
        value=[t for t in state["timeframes"] if t in TIMEFRAMES],
        label="Timeframes",
    )
    mo.hstack([sel_symbols, sel_tfs], widths=[1, 1])
    return sel_symbols, sel_tfs


@app.cell
def _(MA_TYPES, mo, state):
    # ==========================================
    # 2. MA-PARAMETER-RANGES (min/step/max)
    # ==========================================
    dd_ma_type = mo.ui.dropdown(MA_TYPES, value=state["ma"]["ma_type"], label="MA-Typ")

    ma = state["ma"]
    # period
    ma_p_min = mo.ui.number(1, 200, 1, value=ma["period"]["min"], label="period min")
    ma_p_step = mo.ui.number(1, 50, 1, value=ma["period"]["step"], label="period step")
    ma_p_max = mo.ui.number(1, 500, 1, value=ma["period"]["max"], label="period max")
    # smoothing
    ma_s_min = mo.ui.number(1, 200, 1, value=ma["smoothing"]["min"], label="smoothing min")
    ma_s_step = mo.ui.number(1, 50, 1, value=ma["smoothing"]["step"], label="smoothing step")
    ma_s_max = mo.ui.number(1, 300, 1, value=ma["smoothing"]["max"], label="smoothing max")
    # alpha_factor
    ma_a_min = mo.ui.number(0.1, 10.0, 0.5, value=ma["alpha_factor"]["min"], label="alpha min")
    ma_a_step = mo.ui.number(0.1, 5.0, 0.5, value=ma["alpha_factor"]["step"], label="alpha step")
    ma_a_max = mo.ui.number(0.1, 20.0, 0.5, value=ma["alpha_factor"]["max"], label="alpha max")

    row_p = mo.hstack([ma_p_min, ma_p_step, ma_p_max])
    row_s = mo.hstack([ma_s_min, ma_s_step, ma_s_max])
    row_a = mo.hstack([ma_a_min, ma_a_step, ma_a_max])
    mo.vstack([
        mo.md("**MA-Parameter-Ranges** (min / step / max)"),
        dd_ma_type,
        mo.md("`period`"), row_p,
        mo.md("`smoothing`"), row_s,
        mo.md("`alpha_factor`"), row_a,
    ])
    return (
        dd_ma_type,
        ma_a_max,
        ma_a_min,
        ma_a_step,
        ma_p_max,
        ma_p_min,
        ma_p_step,
        ma_s_max,
        ma_s_min,
        ma_s_step,
    )


@app.cell
def _(mo, state):
    # ==========================================
    # 3. VECTORBT-RANGES (sichtbar, aber deaktiviert)
    # ==========================================
    vbt = state["vectorbt"]
    rows = []
    for name in ["spread", "sl_pct", "tp_pct", "position", "fees"]:
        cfg = vbt[name]
        f1 = mo.ui.text(value=str(cfg["min"]), disabled=True, label=f"{name} min")
        f2 = mo.ui.text(value=str(cfg["step"]), disabled=True, label=f"{name} step")
        f3 = mo.ui.text(value=str(cfg["max"]), disabled=True, label=f"{name} max")
        rows.append(mo.hstack([f1, f2, f3]))
    mo.vstack([
        mo.md("**VectorBT-Parameter-Ranges** — 🔒 _deaktiviert, Backtest-Modul folgt später_"),
        *rows,
    ])
    return


@app.cell
def _(DATE_MAX, DATE_MIN, TIMEFRAMES, mo, state):
    # ==========================================
    # 4. STRATEGIE, DATUMSBEREICH, HTF-OPTIONEN, RUN-NAME
    # ==========================================
    dd_strategy = mo.ui.dropdown(
        {"grid": "Grid (vollständiges Kreuzprodukt)", "random": "Random (Stichprobe)"},
        value=state["strategy"],
        label="Strategie",
    )
    num_sample = mo.ui.number(1, 10000, 1, value=state["random_sample"], label="Stichproben-Größe (random)")

    dmin = DATE_MIN.date() if DATE_MIN is not None else None
    dmax = DATE_MAX.date() if DATE_MAX is not None else None
    date_from = mo.ui.date(dmin, dmax, value=dmin, label="Von")
    date_to = mo.ui.date(dmin, dmax, value=dmax, label="Bis")

    sw_htf = mo.ui.switch(value=bool(state.get("htf_exact_time", False)),
                          label="HTF-Exact-Time (Logik auf kleinerem TF)")
    dd_small_tf = mo.ui.dropdown(
        TIMEFRAMES, value=state.get("htf_small_tf", "M15"), label="Kleiner TF für Exact-Time"
    )

    txt_override = mo.ui.text(value=state.get("run_name_override", ""),
                              label="Run-Name-Override (optional, leer = automatisch)")
    txt_free_tag = mo.ui.text(value=state.get("free_tag", ""),
                              label="Freier Tag (optional, wird angehängt)")

    mo.vstack([
        mo.md("**Strategie / Datumsbereich / HTF / Run-Name**"),
        mo.hstack([dd_strategy, num_sample]),
        mo.hstack([date_from, date_to]),
        mo.hstack([sw_htf, dd_small_tf]),
        txt_override,
        txt_free_tag,
    ])
    return (
        date_from,
        date_to,
        dd_small_tf,
        dd_strategy,
        num_sample,
        sw_htf,
        txt_free_tag,
        txt_override,
    )


@app.cell
def _(
    build_run_definition,
    build_run_name,
    date_from,
    date_to,
    dd_ma_type,
    dd_small_tf,
    dd_strategy,
    ma_a_max,
    ma_a_min,
    ma_a_step,
    ma_p_max,
    ma_p_min,
    ma_p_step,
    ma_s_max,
    ma_s_min,
    ma_s_step,
    mo,
    num_sample,
    save_state,
    sel_symbols,
    sel_tfs,
    state,
    sw_htf,
    txt_free_tag,
    txt_override,
):
    # ==========================================
    # 5. RUN-DEFINITION, RUN-ZÄHLER, GO + SAVE
    # ==========================================
    ranges_ma = {
        "period": {"min": ma_p_min.value, "step": ma_p_step.value, "max": ma_p_max.value},
        "smoothing": {"min": ma_s_min.value, "step": ma_s_step.value, "max": ma_s_max.value},
        "alpha_factor": {"min": ma_a_min.value, "step": ma_a_step.value, "max": ma_a_max.value},
    }
    symbols = list(sel_symbols.value) or ["SILVER"]
    tfs = list(sel_tfs.value) or ["M30"]

    definition = build_run_definition(
        symbols=symbols,
        timeframes=tfs,
        ranges=ranges_ma,
        date_from=date_from.value.isoformat() if date_from.value else None,
        date_to=date_to.value.isoformat() if date_to.value else None,
        strategy=dd_strategy.value,
        sample_size=int(num_sample.value or 50),
        htf_exact_time=bool(sw_htf.value),
        htf_small_tf=dd_small_tf.value or "M15",
        fixed_params={"ma_type": dd_ma_type.value},
    )

    n_runs = definition.count_runs()
    preview_params = definition.param_space[0] if definition.param_space else {}
    run_name_preview = build_run_name("MAIndicator", preview_params, symbols[0], tfs[0])

    def _save_state():
        state["symbols"] = list(sel_symbols.value)
        state["timeframes"] = list(sel_tfs.value)
        state["ma"] = {
            "ma_type": dd_ma_type.value,
            "period": {"min": ma_p_min.value, "step": ma_p_step.value, "max": ma_p_max.value},
            "smoothing": {"min": ma_s_min.value, "step": ma_s_step.value, "max": ma_s_max.value},
            "alpha_factor": {"min": ma_a_min.value, "step": ma_a_step.value, "max": ma_a_max.value},
        }
        state["date_range"] = {
            "from": date_from.value.isoformat() if date_from.value else None,
            "to": date_to.value.isoformat() if date_to.value else None,
        }
        state["run_name_override"] = txt_override.value
        state["free_tag"] = txt_free_tag.value
        state["strategy"] = dd_strategy.value
        state["random_sample"] = int(num_sample.value or 50)
        state["htf_exact_time"] = bool(sw_htf.value)
        state["htf_small_tf"] = dd_small_tf.value or "M15"
        save_state(state)

    btn_go = mo.ui.button(label=f"🚀 GO — Massentest starten ({n_runs} Runs)", value=False)
    btn_save = mo.ui.button(label="💾 Stand speichern", on_click=_save_state)

    mo.vstack([
        mo.md(f"**Run-Zähler:** {n_runs} Läufe = {len(symbols)} Symbole × {len(tfs)} TFs × {len(definition.param_space)} Parameter-Sets"),
        mo.md(f"_Beispiel-Name:_ `{run_name_preview}`"),
        mo.hstack([btn_go, btn_save]),
    ])
    return btn_go, btn_save, definition, n_runs, run_name_preview, symbols, tfs


@app.cell
def _(
    DB_ANALYTICS,
    DB_MARKET,
    btn_go,
    definition,
    dt,
    mo,
    n_runs,
    run_sweep_sequential,
    save_state,
    service,
    state,
    sweep_ui,
    symbols,
    threading,
    tfs,
    txt_free_tag,
    txt_override,
):
    # ==========================================
    # 6. SICHERHEITSABFRAGE + SWEEP-START (Thread)
    # ==========================================
    import duckdb as _ddb

    def _start_sweep():
        """Startet den Sweep in einem Hintergrund-Thread (UI bleibt reaktiv)."""
        sweep_ui.reset(definition.count_runs())
        # UI-Stand sichern (spätestens beim GO-Start)
        state["symbols"] = list(definition.symbols)
        state["timeframes"] = list(definition.timeframes)
        state["run_name_override"] = txt_override.value
        state["free_tag"] = txt_free_tag.value
        save_state(state)

        def _worker():
            try:
                ids = run_sweep_sequential(
                    definition,
                    DB_MARKET,
                    service,
                    warmup_bars=200,
                    tz_offset_hours=2,
                    free_tag=txt_free_tag.value.strip(),
                    run_name_override=txt_override.value.strip(),
                    progress_callback=sweep_ui.progress,
                    cancel_callback=sweep_ui.is_cancelled,
                )
                _con = _ddb.connect(str(DB_ANALYTICS), read_only=True)
                _n_runs_db = _con.execute("SELECT COUNT(*) FROM indicator_runs").fetchone()[0]
                _n_events = _con.execute("SELECT COUNT(*) FROM signal_events").fetchone()[0]
                _con.close()

                summary = {
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "runs": len(ids),
                    "runs_db": _n_runs_db,
                    "events_db": _n_events,
                    "symbols": list(definition.symbols),
                    "timeframes": list(definition.timeframes),
                    "n_params": len(definition.param_space),
                    "cancelled": sweep_ui.is_cancelled(),
                }
                state["last_sweep"] = summary
                save_state(state)
                sweep_ui.finish(ids, summary)
            except Exception as e:
                sweep_ui.fail(str(e))

        threading.Thread(target=_worker, daemon=True).start()
        btn_go.value = False  # Dialog schließen

    # --- Sicherheitsabfrage (Modal-Ersatz): erst bestätigen, dann starten ---
    if btn_go.value and not sweep_ui.get_state()["running"]:
        _confirm_text = (
            f"**Sweep starten?**\n\n"
            f"- {n_runs} Läufe · {len(definition.param_space)} Parameter-Sets\n"
            f"- Symbole: {symbols}\n"
            f"- TFs: {tfs}\n"
            f"- Datum: {definition.date_from or 'von Anfang'} → {definition.date_to or 'bis Ende'}\n\n"
            f"_Bereits vorhandene Runs bleiben idempotent erhalten._"
        )
        _btn_confirm = mo.ui.button(label="✅ Ja, starten", kind="danger", on_click=_start_sweep)
        _btn_cancel = mo.ui.button(label="Nein, abbrechen",
                                   on_click=lambda: setattr(btn_go, "value", False))
        mo.vstack([mo.md(_confirm_text), mo.hstack([_btn_confirm, _btn_cancel])])
    else:
        mo.md("")
    return


@app.cell
def _(mo, sweep_ui):
    # ==========================================
    # 8. FORTSCHRITT + ABBRUCH (live)
    # ==========================================
    _refresh = mo.ui.refresh(default_interval="0.5s")
    _st = sweep_ui.get_state()
    _btn_stop = mo.ui.button(label="⏹ Stopp", kind="warn", on_click=sweep_ui.cancel)

    if _st["running"]:
        _pct = int(100 * _st["done"] / _st["total"]) if _st["total"] else 0
        _bar = mo.Html(
            f'<div style="width:100%;background:#1e293b;border-radius:6px;height:22px;position:relative;">'
            f'<div style="width:{_pct}%;background:#22c55e;height:22px;border-radius:6px;"></div>'
            f'<span style="position:absolute;inset:0;color:#fff;font-size:12px;line-height:22px;'
            f'text-align:center;">{_st["done"]}/{_st["total"]} · {_pct}%</span></div>'
        )
        _out = mo.vstack([
            mo.md(f"**Lauf läuft …** _({_st['current']})_"),
            _bar,
            _btn_stop,
        ])
    elif _st["error"]:
        _out = mo.vstack([
            mo.md(f"**Fehler:** {_st['error']}"),
            mo.md("_Bereits persistierte Runs bleiben in der DB._"),
        ])
    elif _st["last_summary"]:
        _s = _st["last_summary"]
        _txt = "**abgebrochen**" if _s.get("cancelled") else "**fertig**"
        _out = mo.vstack([
            mo.md(f"**Letzter Sweep** ({_s['timestamp']}) — {_txt}"),
            mo.md(
                f"- {_s['runs']} Runs verarbeitet ({_s['n_params']} Parameter-Sets)"
                f" · Symbole {_s['symbols']} · TFs {_s['timeframes']}"
            ),
            mo.md(f"- Analytics-DB: **{_s['runs_db']} Runs**, **{_s['events_db']} Events** (idempotent)"),
        ])
    else:
        _out = mo.md("_Noch kein Lauf – Konfiguration wählen und GO drücken._")
    mo.vstack([_refresh, _out])
    return


@app.cell
def _(DB_MARKET, mo, save_state, state):
    # ==========================================
    # 9. QUICK LOOK (Chart-Schnellsicht, §7)
    # ==========================================
    from signal_lab.quick_look import render_quick_look

    ql = state.get("quick_look", {})
    txt_symbol_tf = mo.ui.text(
        value=ql.get("symbol_tf", "SILVER:M30"),
        label="Symbol:TF (z. B. SILVER:M30, GOLD:H1)",
        full_width=True,
    )
    overlay = ql.get("overlay_tfs", ["H1", "H4"])
    sel_overlay = mo.ui.multiselect(
        ["M15", "M30", "H1", "H4", "D1"],
        value=[t for t in overlay if t in ["M15", "M30", "H1", "H4", "D1"]],
        label="HTF-Overlay (max. 3, höhere TFs)",
        max_selections=3,
    )
    ql_slider = mo.ui.slider(
        start=0,
        stop=20000,
        step=50,
        value=20000,
        label="Fenster (rechts = aktuell · links = ältere Daten)",
    )

    def _save_ql():
        state.setdefault("quick_look", {})["symbol_tf"] = txt_symbol_tf.value
        state["quick_look"]["overlay_tfs"] = list(sel_overlay.value)
        save_state(state)

    btn_ql_save = mo.ui.button(label="💾 Quick Look merken", on_click=_save_ql)

    mo.vstack([
        mo.md("**Quick Look** — Chart-Fenster wie im Chart Inspector, "
              "mit M30-Signalen + HTF-Signalen (farbcodiert, versetzt)"),
        txt_symbol_tf,
        sel_overlay,
        btn_ql_save,
    ])
    return ql_slider, render_quick_look, sel_overlay, txt_symbol_tf


@app.cell
def _(
    DB_MARKET,
    mo,
    ql_slider,
    render_quick_look,
    sel_overlay,
    state,
    txt_symbol_tf,
):
    # ==========================================
    # 10. QUICK LOOK — CHART-RENDER (reaktiv)
    # ==========================================
    _OFFSET_MAX = 20000
    _offset = _OFFSET_MAX - int(ql_slider.value)

    _chart = render_quick_look(
        symbol_tf=txt_symbol_tf.value,
        db_market=DB_MARKET,
        overlay_tfs=list(sel_overlay.value),
        window_bars=1000,
        warmup_bars=200,
        end_offset_bars=_offset,
        tz_offset_hours=2,
        ma_params={
            "ma_type": state["ma"].get("ma_type", "EHMA"),
            "period": int(state["ma"]["period"].get("min", 6)),
            "smoothing": int(state["ma"]["smoothing"].get("min", 10)),
            "alpha_factor": float(state["ma"]["alpha_factor"].get("min", 3.0)),
        },
        width=1200,
        height=520,
        scale_width=55,
    )
    mo.vstack([ql_slider, _chart])
    return


if __name__ == "__main__":
    app.run()
