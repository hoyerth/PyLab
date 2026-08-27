"""
Signal Lab v2: Interaktives Marimo-Notebook für Indikator-Massentests und Quick-Look.
Pfad: Notebooks/02_Signal_Lab.py
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import datetime as dt
    import importlib
    from pathlib import Path
    import sys
    import threading
    import marimo as mo

    PROJ_ROOT = (
        Path(__file__).resolve().parent.parent
        if "__file__" in locals()
        else Path.cwd()
    )
    if str(PROJ_ROOT) not in sys.path:
        sys.path.append(str(PROJ_ROOT))

    from algos.signal_service import DuckDBSignalService
    from signal_lab import sweep_ui
    from signal_lab.naming import build_run_name
    from signal_lab.run_definition import (
        available_date_range,
        available_symbols,
        available_timeframes,
        build_run_definition,
        favorite_symbols,
    )
    from signal_lab.ui_state import load_state, save_state

    sweep_ui = importlib.reload(sweep_ui)
    from signal_lab.sweep_runner import run_sweep_sequential

    DB_MARKET = PROJ_ROOT / "data" / "market_data.duckdb"
    DB_ANALYTICS = PROJ_ROOT / "data" / "analytics_data.duckdb"
    DB_APP = PROJ_ROOT / "data" / "app_data.duckdb"

    state = load_state()

    FAV = favorite_symbols(DB_APP)
    SYMBOLS = available_symbols(DB_MARKET, favorite_symbols=FAV)
    TIMEFRAMES = available_timeframes(DB_MARKET)
    DATE_MIN, DATE_MAX = available_date_range(DB_MARKET)
    MA_TYPES = ["EHMA", "TEMA", "DEMA", "EMA", "SMA"]

    service = DuckDBSignalService(db_path=DB_ANALYTICS)

    mo.md("## 🧪 Signal Lab v2 — Massentests")
    return (
        DATE_MAX,
        DATE_MIN,
        DB_ANALYTICS,
        DB_APP,
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


@app.cell(hide_code=True)
def _(FAV, SYMBOLS, TIMEFRAMES, mo, state):
    # ==========================================
    # 1. SYMBOLE & TIMEFRAMES (Mehrfachauswahl)
    # ==========================================
    sym_options = {}
    for s in SYMBOLS:
        sym_options[f"⭐ {s}" if s in FAV else s] = s

    _saved = [s.replace("⭐ ", "") for s in state.get("symbols", [])]
    _saved = [s for s in _saved if s in SYMBOLS]
    _init_labels = [label for label, sym in sym_options.items() if sym in _saved]

    sel_symbols = mo.ui.multiselect(
        sym_options,
        value=_init_labels
        or (
            [f"⭐ {SYMBOLS[0]}" if SYMBOLS[0] in FAV else SYMBOLS[0]]
            if SYMBOLS
            else []
        ),
        label="Symbole",
    )
    sel_tfs = mo.ui.multiselect(
        TIMEFRAMES,
        value=[t for t in state.get("timeframes", []) if t in TIMEFRAMES]
        or (["M1"] if "M1" in TIMEFRAMES else [TIMEFRAMES[0]]),
        label="Timeframes",
    )
    mo.hstack([sel_symbols, sel_tfs], widths=[1, 1])
    return sel_symbols, sel_tfs, sym_options


@app.cell(hide_code=True)
def _(mo, state):
    # ==========================================
    # 2a. INDIKATOR-AUSWAHL
    # ==========================================
    dd_indicator = mo.ui.dropdown(
        ["JumpIndicator", "MAIndicator"],
        value=state.get("active_indicator", "JumpIndicator"),
        label="Indikator-Typ",
    )
    mo.vstack([
        mo.md("**Indikator-Auswahl**"),
        dd_indicator,
    ])
    return (dd_indicator,)


@app.cell(hide_code=True)
def _(MA_TYPES, dd_indicator, mo, state):
    # ==========================================
    # 2b. DYNAMISCHE PARAMETER-RANGES
    # ==========================================
    if dd_indicator.value == "MAIndicator":
        dd_ma_type = mo.ui.dropdown(
            MA_TYPES,
            value=state.get("ma", {}).get("ma_type", "EHMA"),
            label="MA-Typ",
        )
        ma = state.get(
            "ma",
            {
                "period": {"min": 4, "step": 2, "max": 16},
                "smoothing": {"min": 6, "step": 2, "max": 14},
                "alpha_factor": {"min": 2.0, "step": 1.0, "max": 4.0},
            },
        )
        ma_p_min = mo.ui.number(
            1, 200, 1, value=ma.get("period", {}).get("min", 4), label="period min"
        )
        ma_p_step = mo.ui.number(
            1, 50, 1, value=ma.get("period", {}).get("step", 2), label="period step"
        )
        ma_p_max = mo.ui.number(
            1, 500, 1, value=ma.get("period", {}).get("max", 16), label="period max"
        )

        ma_s_min = mo.ui.number(
            1, 200, 1, value=ma.get("smoothing", {}).get("min", 6), label="smoothing min"
        )
        ma_s_step = mo.ui.number(
            1, 50, 1, value=ma.get("smoothing", {}).get("step", 2), label="smoothing step"
        )
        ma_s_max = mo.ui.number(
            1, 300, 1, value=ma.get("smoothing", {}).get("max", 14), label="smoothing max"
        )

        ma_a_min = mo.ui.number(
            0.1, 10.0, 0.5, value=ma.get("alpha_factor", {}).get("min", 2.0), label="alpha min"
        )
        ma_a_step = mo.ui.number(
            0.1, 5.0, 0.5, value=ma.get("alpha_factor", {}).get("step", 1.0), label="alpha step"
        )
        ma_a_max = mo.ui.number(
            0.1, 20.0, 0.5, value=ma.get("alpha_factor", {}).get("max", 4.0), label="alpha max"
        )

        row_p = mo.hstack([ma_p_min, ma_p_step, ma_p_max])
        row_s = mo.hstack([ma_s_min, ma_s_step, ma_s_max])
        row_a = mo.hstack([ma_a_min, ma_a_step, ma_a_max])

        params_view = mo.vstack([
            mo.md("**MA-Parameter-Ranges**"),
            dd_ma_type,
            mo.md("`period`"),
            row_p,
            mo.md("`smoothing`"),
            row_s,
            mo.md("`alpha_factor`"),
            row_a,
        ])

        jump_grid = None
        jump_prox_min = None
        jump_prox_step = None
        jump_prox_max = None
    else:
        jump = state.get("jump", {})
        grid_saved = jump.get("grid_interval", 0.50)
        grid_valid = round(float(grid_saved) / 0.05) * 0.05

        jump_grid = mo.ui.number(
            0.05,
            1000.0,
            0.05,
            value=grid_valid if grid_valid >= 0.05 else 0.50,
            label="Grid Intervall ($)",
        )

        prox_cfg = jump.get("proximity_buffer", {})
        init_prox_min = (
            prox_cfg.get("min", 0.075)
            if isinstance(prox_cfg, dict)
            else 0.075
        )
        init_prox_step = (
            prox_cfg.get("step", 0.050)
            if isinstance(prox_cfg, dict)
            else 0.050
        )
        init_prox_max = (
            prox_cfg.get("max", 0.075)
            if isinstance(prox_cfg, dict)
            else 0.075
        )

        jump_prox_min = mo.ui.number(
            0.000,
            10.000,
            0.001,
            value=round(float(init_prox_min), 3),
            label="Proximity min ($)",
        )
        jump_prox_step = mo.ui.number(
            0.005,
            5.000,
            0.005,
            value=round(float(init_prox_step), 3),
            label="Puffer step ($)",
        )
        jump_prox_max = mo.ui.number(
            0.000,
            20.000,
            0.001,
            value=round(float(init_prox_max), 3),
            label="Proximity max ($)",
        )
        row_jump_prox = mo.hstack([jump_prox_min, jump_prox_step, jump_prox_max])

        params_view = mo.vstack([
            mo.md("**Jump-Parameter (Grid & Proximity-Puffer)**"),
            jump_grid,
            mo.md("`proximity_buffer`"),
            row_jump_prox,
        ])

        dd_ma_type = None
        ma_p_min = None
        ma_p_step = None
        ma_p_max = None
        ma_s_min = None
        ma_s_step = None
        ma_s_max = None
        ma_a_min = None
        ma_a_step = None
        ma_a_max = None

    params_view
    return (
        dd_ma_type,
        jump_grid,
        jump_prox_max,
        jump_prox_min,
        jump_prox_step,
        ma_a_max,
        ma_a_min,
        ma_a_step,
        ma_p_max,
        ma_p_min,
        ma_p_step,
        ma_s_max,
        ma_s_min,
        ma_s_step,
        params_view,
    )


@app.cell(hide_code=True)
def _(DATE_MAX, DATE_MIN, TIMEFRAMES, dt, mo, state):
    # ==========================================
    # 3. STRATEGIE, DATUMSBEREICH, HTF-OPTIONEN
    # ==========================================
    _strat_raw = state.get("strategy", "grid")
    _strat_key = _strat_raw if _strat_raw in ("grid", "random") else "grid"
    dd_strategy = mo.ui.dropdown(
        {"grid": "Grid (vollständiges Kreuzprodukt)", "random": "Random (Stichprobe)"},
        value=_strat_key,
        label="Strategie",
    )
    num_sample = mo.ui.number(
        1,
        10000,
        1,
        value=state.get("random_sample", 50),
        label="Stichproben-Größe (random)",
    )

    dmin = DATE_MIN.date() if DATE_MIN is not None else None
    dmax = DATE_MAX.date() if DATE_MAX is not None else None
    _dr = state.get("date_range") or {}

    def _pdate(s, default):
        if s:
            try:
                return dt.date.fromisoformat(str(s))
            except ValueError:
                pass
        return default

    date_from = mo.ui.date(
        dmin, dmax, value=_pdate(_dr.get("from"), dmin), label="Von (Kalender)"
    )
    date_to = mo.ui.date(
        dmin, dmax, value=_pdate(_dr.get("to"), dmax), label="Bis (Kalender)"
    )
    txt_from = mo.ui.text(
        value=_dr.get("from") or "",
        label="Von (manuell JJJJ-MM-TT)",
        full_width=True,
    )
    txt_to = mo.ui.text(
        value=_dr.get("to") or "",
        label="Bis (manuell JJJJ-MM-TT)",
        full_width=True,
    )

    def resolve_date(txt, picker, default=None):
        s = (txt or "").strip()
        if s:
            try:
                d = dt.date.fromisoformat(s)
            except ValueError:
                d = None
            if d is not None:
                if dmin is not None and d < dmin:
                    d = dmin
                if dmax is not None and d > dmax:
                    d = dmax
                return d
        return picker.value or default

    sw_htf = mo.ui.switch(
        value=bool(state.get("htf_exact_time", False)),
        label="HTF-Exact-Time (Logik auf kleinerem TF)",
    )
    dd_small_tf = mo.ui.dropdown(
        TIMEFRAMES,
        value=state.get("htf_small_tf", "M15"),
        label="Kleiner TF für Exact-Time",
    )

    sw_delete = mo.ui.switch(
        value=bool(state.get("sweep_delete_existing", True)),
        label="Update-Modus: vor dem Lauf vorhandene Runs/Signale für gewählte Symbole/TFs löschen",
    )

    def _on_free_tag(v):
        state["free_tag"] = v

    txt_free_tag = mo.ui.text(
        value=state.get("free_tag", ""),
        label="Freier Tag (optional, z. B. 'v2' oder 'Q3')",
        on_change=_on_free_tag,
    )

    mo.vstack([
        mo.md("**Strategie / Datumsbereich / HTF**"),
        mo.hstack([dd_strategy, num_sample]),
        mo.hstack([date_from, date_to]),
        mo.hstack([txt_from, txt_to]),
        mo.hstack([sw_htf, dd_small_tf]),
        sw_delete,
        txt_free_tag,
    ])
    return (
        date_from,
        date_to,
        dd_small_tf,
        dd_strategy,
        num_sample,
        resolve_date,
        sw_delete,
        sw_htf,
        txt_free_tag,
        txt_from,
        txt_to,
    )


@app.cell(hide_code=True)
def _():
    # ==========================================
    # 4a. STATE-SETUP (Modul-Singleton)
    # ==========================================
    from signal_lab.ui_state import get_marimo_states

    _st = get_marimo_states()
    go_state = _st["go_state"]
    set_go_state = _st["set_go_state"]
    save_msg = _st["save_msg"]
    set_save_msg = _st["set_save_msg"]
    refresh_ctl = _st["refresh_ctl"]
    return go_state, refresh_ctl, save_msg, set_go_state, set_save_msg


@app.cell(hide_code=True)
def _(
    DB_APP,
    SYMBOLS,
    build_run_definition,
    build_run_name,
    date_from,
    date_to,
    dd_indicator,
    dd_ma_type,
    dd_small_tf,
    dd_strategy,
    dt,
    jump_grid,
    jump_prox_max,
    jump_prox_min,
    jump_prox_step,
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
    resolve_date,
    save_state,
    sel_symbols,
    sel_tfs,
    set_go_state,
    set_save_msg,
    state,
    sw_htf,
    sweep_ui,
    sym_options,
    txt_free_tag,
    txt_from,
    txt_to,
):
    # ==========================================
    # 4. RUN-DEFINITION, RUN-ZÄHLER, GO + SAVE
    # ==========================================
    import duckdb

    symbols = [sym_options.get(l, l.replace("⭐ ", "")) for l in sel_symbols.value]
    symbols = [s for s in symbols if s in SYMBOLS] or ["SILVER"]
    tfs = list(sel_tfs.value) or ["M1"]

    point_val = 0.001
    try:
        con_app = duckdb.connect(str(DB_APP), read_only=True)
        try:
            row = con_app.execute(
                "SELECT point FROM broker_symbols WHERE symbol = ?", [symbols[0]]
            ).fetchone()
            if row and row[0] is not None:
                point_val = float(row[0])
        finally:
            con_app.close()
    except Exception:
        pass

    if dd_indicator.value == "MAIndicator":
        p_min = ma_p_min.value if ma_p_min is not None else 4
        p_step = ma_p_step.value if ma_p_step is not None else 2
        p_max = ma_p_max.value if ma_p_max is not None else 16
        s_min = ma_s_min.value if ma_s_min is not None else 6
        s_step = ma_s_step.value if ma_s_step is not None else 2
        s_max = ma_s_max.value if ma_s_max is not None else 14
        a_min = ma_a_min.value if ma_a_min is not None else 2.0
        a_step = ma_a_step.value if ma_a_step is not None else 1.0
        a_max = ma_a_max.value if ma_a_max is not None else 4.0
        m_type = dd_ma_type.value if dd_ma_type is not None else "EHMA"

        ranges = {
            "period": {"min": p_min, "step": p_step, "max": p_max},
            "smoothing": {"min": s_min, "step": s_step, "max": s_max},
            "alpha_factor": {"min": a_min, "step": a_step, "max": a_max},
        }
        fixed_params = {
            "indicator_name": "MAIndicator",
            "ma_type": m_type,
        }
    else:
        prox_min = jump_prox_min.value if jump_prox_min is not None else 0.075
        prox_step = jump_prox_step.value if jump_prox_step is not None else 0.050
        prox_max = jump_prox_max.value if jump_prox_max is not None else 0.075
        grid_val = jump_grid.value if jump_grid is not None else 0.50

        ranges = {
            "proximity_buffer": {
                "min": prox_min,
                "step": prox_step,
                "max": prox_max,
            },
        }
        fixed_params = {
            "indicator_name": "JumpIndicator",
            "grid_interval": float(grid_val),
            "point_size": point_val,
        }

    date_from_val = resolve_date(txt_from.value, date_from)
    date_to_val = resolve_date(txt_to.value, date_to)

    definition = build_run_definition(
        symbols=symbols,
        timeframes=tfs,
        ranges=ranges,
        date_from=date_from_val.isoformat() if date_from_val else None,
        date_to=date_to_val.isoformat() if date_to_val else None,
        strategy=dd_strategy.value,
        sample_size=int(num_sample.value or 50),
        htf_exact_time=bool(sw_htf.value),
        htf_small_tf=dd_small_tf.value or "M15",
        fixed_params=fixed_params,
    )

    n_runs = definition.count_runs()
    preview_params = definition.param_space[0] if definition.param_space else {}
    run_name_preview = build_run_name(
        dd_indicator.value, preview_params, symbols[0], tfs[0]
    )

    saved_override = state.get("run_name_override", "")
    if dd_indicator.value == "JumpIndicator" and (
        "ehma" in saved_override.lower()
        or "tema" in saved_override.lower()
        or "dema" in saved_override.lower()
    ):
        initial_name_val = run_name_preview
    elif dd_indicator.value == "MAIndicator" and "jump" in saved_override.lower():
        initial_name_val = run_name_preview
    else:
        initial_name_val = saved_override or run_name_preview

    def _on_name_change(v):
        state["run_name_override"] = v

    txt_override = mo.ui.text(
        value=initial_name_val,
        label="Run-Name (manuell änderbar)",
        full_width=True,
        on_change=_on_name_change,
    )

    def _save_state(_value=None):
        state["symbols"] = [
            sym_options.get(l, l.replace("⭐ ", "")) for l in sel_symbols.value
        ]
        state["timeframes"] = list(sel_tfs.value)
        state["active_indicator"] = dd_indicator.value
        if dd_indicator.value == "MAIndicator" and ma_p_min is not None:
            state["ma"] = {
                "ma_type": dd_ma_type.value,
                "period": {
                    "min": ma_p_min.value,
                    "step": ma_p_step.value,
                    "max": ma_p_max.value,
                },
                "smoothing": {
                    "min": ma_s_min.value,
                    "step": ma_s_step.value,
                    "max": ma_s_max.value,
                },
                "alpha_factor": {
                    "min": ma_a_min.value,
                    "step": ma_a_step.value,
                    "max": ma_a_max.value,
                },
            }
        elif jump_grid is not None and jump_prox_min is not None:
            state["jump"] = {
                "grid_interval": float(jump_grid.value),
                "proximity_buffer": {
                    "min": jump_prox_min.value,
                    "step": jump_prox_step.value,
                    "max": jump_prox_max.value,
                },
            }
        _fd = resolve_date(txt_from.value, date_from)
        _td = resolve_date(txt_to.value, date_to)
        state["date_range"] = {
            "from": _fd.isoformat() if _fd else None,
            "to": _td.isoformat() if _td else None,
        }
        state["run_name_override"] = txt_override.value
        state["free_tag"] = txt_free_tag.value
        state["strategy"] = dd_strategy.value
        state["random_sample"] = int(num_sample.value or 50)
        state["htf_exact_time"] = bool(sw_htf.value)
        state["htf_small_tf"] = dd_small_tf.value or "M15"
        save_state(state)
        set_save_msg(f"Stand gespeichert ({dt.datetime.now().strftime('%H:%M:%S')})")

    def _on_go(_value):
        if sweep_ui.get_state()["running"] and not sweep_ui.is_alive():
            sweep_ui.finish([], None)
            sweep_ui.set_message("", "")
        set_go_state("confirm")

    btn_go = mo.ui.button(
        label=f"🚀 GO — Massentest starten ({n_runs} Runs)",
        on_click=_on_go,
    )
    btn_save = mo.ui.button(label="💾 Stand speichern", on_click=_save_state)

    mo.vstack([
        mo.md(
            f"**Run-Zähler:** {n_runs} Läufe = {len(symbols)} Symbole × {len(tfs)} TFs × {len(definition.param_space)} Parameter-Sets"
        ),
        txt_override,
        mo.md(f"_Beispiel-Name:_ `{run_name_preview}`"),
        mo.hstack([btn_go, btn_save]),
    ])
    return definition, n_runs, symbols, tfs, txt_override


@app.cell(hide_code=True)
def _(
    DB_ANALYTICS,
    DB_MARKET,
    definition,
    dt,
    go_state,
    mo,
    n_runs,
    run_sweep_sequential,
    save_state,
    service,
    set_go_state,
    set_save_msg,
    state,
    sw_delete,
    sweep_ui,
    symbols,
    tfs,
    threading,
    txt_free_tag,
    txt_override,
):
    # ==========================================
    # 5. SICHERHEITSABFRAGE + SWEEP-START (Thread)
    # ==========================================
    import duckdb as _ddb

    def _start_sweep(_value=None):
        if go_state() != "confirm" or sweep_ui.get_state()["running"]:
            return
        sweep_ui.reset(definition.count_runs())
        sweep_ui.set_message("🕒 Massentest gestartet …", "spinner")
        set_save_msg(f"🕒 Massentest läuft – {definition.count_runs()} Runs")
        state["symbols"] = list(definition.symbols)
        state["timeframes"] = list(definition.timeframes)
        state["run_name_override"] = txt_override.value
        state["free_tag"] = txt_free_tag.value
        save_state(state)

        def _worker():
            try:
                deleted = 0
                if bool(sw_delete.value):
                    deleted = service.delete_runs(
                        symbols=list(definition.symbols),
                        timeframes=list(definition.timeframes),
                    )
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
                _n_runs_db = _con.execute(
                    "SELECT COUNT(*) FROM indicator_runs"
                ).fetchone()[0]
                _n_events = _con.execute(
                    "SELECT COUNT(*) FROM signal_events"
                ).fetchone()[0]
                _con.close()

                summary = {
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "runs": len(ids),
                    "runs_db": _n_runs_db,
                    "events_db": _n_events,
                    "symbols": list(definition.symbols),
                    "timeframes": list(definition.timeframes),
                    "n_params": len(definition.param_space),
                    "deleted": deleted,
                    "cancelled": sweep_ui.is_cancelled(),
                }
                state["last_sweep"] = summary
                save_state(state)
                sweep_ui.finish(ids, summary)
                if sweep_ui.is_cancelled():
                    sweep_ui.set_message(
                        f"⏹ Abgebrochen – {len(ids)} Runs verarbeitet", "info"
                    )
                else:
                    sweep_ui.set_message(
                        f"✅ Massentest fertig – {len(ids)} Runs neu berechnet "
                        f"({_n_runs_db} Runs gesamt)",
                        "ok",
                    )
            except Exception as e:
                sweep_ui.fail(str(e))
                sweep_ui.set_message(f"❌ Fehler: {e}", "err")

        _t = threading.Thread(target=_worker, daemon=True)
        sweep_ui.set_thread(_t)
        _t.start()
        set_go_state("idle")

    def _cancel(_value=None):
        set_go_state("idle")
        sweep_ui.set_message("", "")

    btn_confirm = mo.ui.button(
        label="✅ Ja, starten", kind="danger", on_click=_start_sweep
    )
    btn_cancel = mo.ui.button(label="Nein, abbrechen", on_click=_cancel)

    if not definition.param_space or not symbols or not tfs:
        if go_state() == "confirm":
            set_go_state("idle")
        _out = mo.vstack([
            mo.md(
                "⚠️ **Keine gültige Konfiguration** – der Massentest kann nicht starten."
            ),
            mo.md(
                "Bitte mindestens ein Symbol, einen Timeframe und gültige Parameter-Ranges wählen."
            ),
        ])
    elif go_state() == "confirm" and not sweep_ui.get_state()["running"]:
        _confirm_text = (
            f"**Sweep starten?**\n\n"
            f"- {n_runs} Läufe · {len(definition.param_space)} Parameter-Sets\n"
            f"- Symbole: {symbols}\n"
            f"- TFs: {tfs}\n"
            f"- Datum: {definition.date_from or 'von Anfang'} → {definition.date_to or 'bis Ende'}\n"
            f"- Run-Name: `{txt_override.value}`\n\n"
        )
        if bool(sw_delete.value):
            _confirm_text += (
                f"⚠️ **Update-Modus:** Vorhandene Runs + Signale für {len(symbols)} Symbol(e) "
                f"· {len(tfs)} TF(s) werden **gelöscht** und neu berechnet.\n\n"
            )
        _confirm_text += "_Wiederholte Läufe ersetzen also den Datenbestand der betroffenen Symbole/TFs (Update des Zeitraums)._"

        _out = mo.vstack([
            mo.md(_confirm_text),
            mo.hstack([btn_confirm, btn_cancel]),
        ])
    else:
        _out = mo.md("")

    _out
    return btn_confirm, btn_cancel


@app.cell(hide_code=True)
def _(mo, refresh_ctl, save_msg, sweep_ui):
    # ==========================================
    # 6. FORTSCHRITT + ABBRUCH + STATUSMELDUNG (live)
    # ==========================================
    _ = refresh_ctl.value
    _st = sweep_ui.get_state()

    def _on_stop(_value):
        sweep_ui.cancel()
        if not sweep_ui.is_alive():
            sweep_ui.finish([], None)
            sweep_ui.set_message("⏹ Abgebrochen – Lauf war nicht mehr aktiv", "info")

    _btn_stop = mo.ui.button(label="⏹ Stopp", kind="warn", on_click=_on_stop)
    _save_el = mo.md(f"💾 {save_msg()}") if save_msg() else mo.md("")

    _msg = _st.get("message") or ""
    _kind = _st.get("message_kind") or ""
    if _msg:
        if _kind == "spinner":
            _msg_el = mo.hstack([
                mo.Html(
                    '<style>@keyframes _spin {to { transform: rotate(360deg); }}</style>'
                    '<span style="display:inline-block;width:16px;height:16px;border:3px solid #94a3b8;'
                    'border-top-color:#22c55e;border-radius:50%;animation:_spin 0.8s linear infinite;"></span>'
                ),
                mo.md(f"**{_msg}**"),
            ])
        elif _kind == "ok":
            _msg_el = mo.md(f"✅ {_msg}")
        elif _kind == "err":
            _msg_el = mo.md(f"❌ {_msg}")
        else:
            _msg_el = mo.md(f"ℹ️ {_msg}")
    else:
        _msg_el = mo.md("")

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
        _lines = [
            mo.md(f"**Letzter Sweep** ({_s['timestamp']}) — {_txt}"),
            mo.md(
                f"- {_s['runs']} Runs verarbeitet ({_s['n_params']} Parameter-Sets)"
                f" · Symbole {_s['symbols']} · TFs {_s['timeframes']}"
            ),
            mo.md(
                f"- Analytics-DB: **{_s['runs_db']} Runs**, **{_s['events_db']} Events**"
            ),
        ]
        if _s.get("deleted"):
            _lines.append(mo.md(f"- ♻️ Update-Modus: {_s['deleted']} alte Runs gelöscht"))
        _out = mo.vstack(_lines)
    else:
        _out = mo.md("_Noch kein Lauf – Konfiguration wählen und GO drücken._")

    _ls = _st.get("last_summary") or {}
    _last_ts = _ls.get("timestamp", "") or ""
    if _st["running"]:
        _refresh_el = mo.hstack([
            refresh_ctl,
            mo.md(
                f"🕒 läuft … · letzter Lauf-Ende: **{_last_ts}**"
                if _last_ts
                else "🕒 läuft …"
            ),
        ])
    elif _last_ts:
        _refresh_el = mo.md(f"✅ Letzter Lauf beendet: **{_last_ts}**")
    else:
        _refresh_el = mo.md("")
    mo.vstack([_refresh_el, _save_el, _msg_el, _out])
    return


@app.cell(hide_code=True)
def _(mo, save_state, set_save_msg, state):
    # ==========================================
    # 7. QUICK LOOK (Chart-Schnellsicht, §7)
    # ==========================================
    from signal_lab.quick_look import render_quick_look

    ql = state.get("quick_look", {})
    txt_symbol_tf = mo.ui.text(
        value=ql.get("symbol_tf", "SILVER:M1"),
        label="Symbol:TF (z. B. SILVER:M1, GOLD:H1)",
        full_width=True,
    )
    overlay = ql.get("overlay_tfs", ["H1", "H4"])
    sel_overlay = mo.ui.multiselect(
        ["M15", "M30", "H1", "H4", "D1"],
        value=[t for t in overlay if t in ["M15", "M30", "H1", "H4", "D1"]],
        label="HTF-Overlay (max. 3, höhere TFs - nur für MA)",
        max_selections=3,
    )
    ql_slider = mo.ui.slider(
        start=0,
        stop=20000,
        step=50,
        value=20000,
        label="Fenster (rechts = aktuell · links = ältere Daten)",
    )

    def _save_ql(_value=None):
        state.setdefault("quick_look", {})["symbol_tf"] = txt_symbol_tf.value
        state["quick_look"]["overlay_tfs"] = list(sel_overlay.value)
        save_state(state)
        set_save_msg(f"Quick Look gespeichert ({txt_symbol_tf.value})")

    btn_ql_save = mo.ui.button(label="💾 Quick Look merken", on_click=_save_ql)

    mo.vstack([
        mo.md("**Quick Look** — Chart-Fenster zur visuellen Signalkontrolle"),
        txt_symbol_tf,
        sel_overlay,
        btn_ql_save,
    ])
    return ql_slider, render_quick_look, sel_overlay, txt_symbol_tf


@app.cell(hide_code=True)
def _(
    DB_MARKET,
    dd_indicator,
    dd_ma_type,
    jump_grid,
    jump_prox_min,
    ma_a_min,
    ma_p_min,
    ma_s_min,
    mo,
    ql_slider,
    render_quick_look,
    sel_overlay,
    state,
    txt_symbol_tf,
):
    # ==========================================
    # 8. QUICK LOOK — CHART-RENDER (reaktiv)
    # ==========================================
    _OFFSET_MAX = 20000
    _offset = _OFFSET_MAX - int(ql_slider.value)

    if dd_indicator.value == "JumpIndicator":
        ind_params = {
            "grid_interval": float(
                jump_grid.value if jump_grid is not None else 0.50
            ),
            "proximity_buffer": float(
                jump_prox_min.value if jump_prox_min is not None else 0.075
            ),
        }
    else:
        ind_params = {
            "ma_type": dd_ma_type.value if dd_ma_type is not None else "EHMA",
            "period": int(ma_p_min.value if ma_p_min is not None else 6),
            "smoothing": int(ma_s_min.value if ma_s_min is not None else 10),
            "alpha_factor": float(ma_a_min.value if ma_a_min is not None else 3.0),
        }

    _chart = render_quick_look(
        symbol_tf=txt_symbol_tf.value,
        db_market=DB_MARKET,
        overlay_tfs=list(sel_overlay.value),
        window_bars=1000,
        warmup_bars=200,
        end_offset_bars=_offset,
        tz_offset_hours=2,
        indicator_name=dd_indicator.value,
        indicator_params=ind_params,
        width=1200,
        height=520,
        scale_width=55,
    )
    mo.vstack([ql_slider, _chart])
    return


if __name__ == "__main__":
    app.run()