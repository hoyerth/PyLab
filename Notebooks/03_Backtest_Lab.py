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

    # backtest_lab-Module (Logik liegt nicht im Notebook)
    from backtest_lab.ui_state import load_state, save_state
    from backtest_lab.ui import (
        render_order_params,
        render_complexity,
        render_order_params_with_usd,
        render_checkbox_table,
        selected_checkbox_ids,
    )
    from backtest_lab.complexity import (
        bar_counts_for,
        estimate_complexity,
        go_allowed,
        load_complexity_config,
    )
    from backtest_lab.db import (
        DB_ANALYTICS,
        DB_BACKTEST,
        DB_MARKET,
        available_date_range,
        connect_backtest,
        delete_backtest_runs,
        enrich_signal_ranges,
        get_backtest_runs,
        get_backtest_trades,
        get_last_signal_runs,
        get_signal_run_batches,
        get_signal_runs,
        get_signal_runs_for_batch,
    )
    from backtest_lab.naming import build_backtest_run_name
    from backtest_lab.runner import BacktestJob, run_backtests_parallel
    from backtest_lab.types import order_params_json
    from backtest_lab import run_ui
    # Dev-Reload: der laufende Marimo-Kernel cached importierte Module.
    # Ohne Reload wuerde eine alte Version (z. B. ohne neuen Lauf-Status)
    # verwendet.
    import importlib
    run_ui = importlib.reload(run_ui)

    state = load_state()

    # Datumsspanne der OHLCV-Daten + Komplexitaets-Config
    DATE_MIN, DATE_MAX = available_date_range(DB_MARKET)
    COMPLEXITY_CFG = load_complexity_config()

    mo.md("## 📊 Backtest Lab v1 — VectorBT-Backtests auf Signal-Lab-Signalen")
    return (
        COMPLEXITY_CFG,
        DATE_MAX,
        DATE_MIN,
        DB_ANALYTICS,
        DB_BACKTEST,
        DB_MARKET,
        BacktestJob,
        bar_counts_for,
        build_backtest_run_name,
        connect_backtest,
        delete_backtest_runs,
        dt,
        enrich_signal_ranges,
        estimate_complexity,
        get_backtest_runs,
        get_backtest_trades,
        get_last_signal_runs,
        get_signal_run_batches,
        get_signal_runs,
        get_signal_runs_for_batch,
        go_allowed,
        load_state,
        mo,
        order_params_json,
        render_checkbox_table,
        render_complexity,
        render_order_params,
        render_order_params_with_usd,
        run_backtests_parallel,
        run_ui,
        save_state,
        selected_checkbox_ids,
        state,
        threading,
    )


@app.cell(hide_code=True)
def _(mo):
    # ==========================================
    # 1a. RUN-NEU-LADEN-BUTTON (eigene Zelle!)
    # ==========================================
    # marimo-Regel: Der `.value`-Zugriff ist in der Zelle, die das Element
    # erzeugt, VERBOTEN (RuntimeError). Der Button wird daher hier erzeugt
    # und in Zelle 1 via `btn_reload_runs.value` gelesen (reaktiver Trigger).
    btn_reload_runs = mo.ui.button(
        label="🔄 Runs neu laden", on_click=lambda _v: None
    )
    return btn_reload_runs


@app.cell(hide_code=True)
def _(DB_ANALYTICS, btn_reload_runs, get_signal_run_batches, mo):
    # ==========================================
    # 1b. RUN-QUELLE: letzter Lauf | alle Runs | einzelner Batch
    # ==========================================
    # marimo-Regel: `.value`-Zugriff ist in der erzeugenden Zelle verboten -
    # das Dropdown wird hier NUR erzeugt, gelesen wird es in Zelle 1
    # (RUN-AUSWAHL) via `dd_run_source.value`.
    # Klick auf "Runs neu laden" re-runt diese Zelle -> Batch-Liste frisch.
    _reload = btn_reload_runs.value

    _batches = get_signal_run_batches(db_path=DB_ANALYTICS)
    _opts: dict[str, str] = {"🕐 Letzter Signal-Lab-Lauf": "__last__"}
    if not _batches.empty:
        _opts["🗂 Alle Runs (Historie)"] = "__all__"
        for _row in _batches.itertuples():
            _opts[str(_row.label)] = str(_row.ts)
    else:
        _opts["🗂 Alle Runs (keine Historie)"] = "__all__"

    dd_run_source = mo.ui.dropdown(
        options=_opts,
        value="🕐 Letzter Signal-Lab-Lauf",
        label="Run-Quelle (Backtest-Basis)",
    )
    return dd_run_source


@app.cell(hide_code=True)
def _(
    DB_ANALYTICS,
    btn_reload_runs,
    dd_run_source,
    enrich_signal_ranges,
    get_last_signal_runs,
    get_signal_runs,
    get_signal_runs_for_batch,
    mo,
    render_checkbox_table,
    state,
):
    # ==========================================
    # 1. RUN-AUSWAHL (letzter Lauf | alle Runs | einzelner Batch)
    # ==========================================
    # Reaktiver Trigger: Klick auf "Runs neu laden" erhoeht den Button-Wert
    # -> diese Zelle re-runt und liest die Liste frisch aus analytics_data.
    _reload = btn_reload_runs.value

    # Run-Quelle aus dem Dropdown (Zelle 1b): "__last__" = letzter Lauf,
    # "__all__" = alle Runs, sonst ISO-Zeitstempel eines einzelnen Batches.
    _src = dd_run_source.value
    if _src == "__last__":
        runs_df = get_last_signal_runs(db_path=DB_ANALYTICS)
        _src_label = "letzten Signal-Lab-Lauf"
    elif _src == "__all__":
        runs_df = get_signal_runs(db_path=DB_ANALYTICS)
        _src_label = "allen Signal-Lab-Runs"
    else:
        runs_df = get_signal_runs_for_batch(_src, db_path=DB_ANALYTICS)
        _src_label = f"Lauf-Batch {_src}"

    # Abgedeckten Signal-Zeitraum je Run ergaenzen (MIN/MAX der Events)
    # -> Spalten signal_from/signal_to in der Auswahl-Tabelle.
    runs_df = enrich_signal_ranges(runs_df, DB_ANALYTICS)

    # Gespeicherte Auswahl wiederherstellen (run_ids)
    _saved_rids = state.get("selected_run_ids", []) or []

    # Bugfix 2: High-Contrast-Tabelle (schwarz auf weiss, Cursorzeile
    # invertiert) statt mo.ui.table (Canvas-Highlight nicht per CSS fixbar).
    _sel_container, run_cbs, run_ids, _sel_detail_btns = render_checkbox_table(
        runs_df,
        display_cols=[
            "run_name", "symbol", "timeframe",
            "signal_from", "signal_to", "created_at",
        ],
        initial_selected=_saved_rids,
        label="Signal-Run-Auswahl (ankreuzen = Backtest-Basis)",
        empty_hint="_Keine Signal-Runs gefunden - zuerst einen Signal-Lab-Lauf ausführen._",
    )

    mo.vstack([
        mo.hstack([
            btn_reload_runs,
            dd_run_source,
            mo.md(f"_{len(runs_df)} Run(s) im {_src_label}_"),
        ]),
        _sel_container,
    ])
    return run_cbs, run_ids, runs_df


@app.cell(hide_code=True)
def _(DATE_MAX, DATE_MIN, build_backtest_run_name, dt, mo, render_order_params, state):
    # ==========================================
    # 2. ORDER-PARAMETER ELEMENTE ERZEUGEN (Rendering in Zelle 2b!)
    # ==========================================
    # marimo-Regel: Die erzeugende Zelle darf die Elemente NICHT via .value
    # lesen. Da die $-Badges (Bugfix 3) live aus den Eingabewerten rechnen,
    # muessen die Eingabefelder in einer ANDEREN Zelle (2b) gerendert werden
    # (dort ist der .value-Zugriff erlaubt). Diese Zelle erzeugt die
    # Elemente und rendert nur die Run-Name-Felder.
    params_ui = render_order_params(state, DATE_MIN, DATE_MAX)

    def _on_name_change(v):
        state["run_name_manual"] = True
        state["run_name_override"] = v

    def _on_free_tag(v):
        state["free_tag"] = v

    # Run-Name DIREKT als Text vorbelegen: letzter eigener Text aus dem State
    # oder ein frischer Vorschlag im BT_-Schema (aus den State-Defaults, ohne
    # .value-Zugriff auf UI-Elemente - in der erzeugenden Zelle verboten).
    _order = state.get("order") or {}
    _suggested = build_backtest_run_name(
        float(_order.get("spread_pct", 0.15)),
        float(_order.get("stop_loss_pct", 0.2))
        if _order.get("stop_loss_pct") is not None else None,
        float(_order.get("take_profit_pct", 2.0))
        if _order.get("take_profit_pct") is not None else None,
        float(_order.get("position_size_pct", 1.0)),
        dt.datetime.now(),
        leverage=float(_order.get("leverage", 1000.0)),
    )
    # Bugfix 7 (Run-Name): Bei automatischem Namen (run_name_manual=False)
    # IMMER frisch aus den aktuellen Order-Parametern vorschlagen - ein stale
    # Override (z. B. alter SL-Wert im Namen) wird NICHT weiterverwendet.
    _initial_name = (
        (state.get("run_name_override") or _suggested)
        if state.get("run_name_manual")
        else _suggested
    )
    txt_override = mo.ui.text(
        value=_initial_name,
        label="Run-Name (vorbelegt – direkt editierbar; End/Tab = Cursor ans Ende)",
        full_width=True,
        on_change=_on_name_change,
    )
    txt_free_tag = mo.ui.text(
        value=state.get("free_tag", ""),
        label="Freier Tag (optional, an den Namen angehängt)",
        full_width=True,
        on_change=_on_free_tag,
    )

    mo.vstack([
        # Größeres Eingabefeld fuer Run-Name/Free-Tag (global fuer Text-Inputs
        # dieses Notebooks; marimo bietet keinen nativen Feld-Groessen-Parameter).
        mo.Html(
            '<style>input[data-testid="marimo-plugin-text-input"]'
            '{padding:9px 11px;font-size:1.05em;}</style>'
        ),
        mo.md("**Run-Name**"),
        txt_override,
        txt_free_tag,
    ])
    return params_ui, txt_free_tag, txt_override


@app.cell(hide_code=True)
def _(mo, params_ui, render_order_params_with_usd):
    # ==========================================
    # 2b. ORDER-PARAMETER ANZEIGE + $-WERTE INLINE (Bugfix 3)
    # ==========================================
    # Reaktiv: liest die Order-Parameter-Eingaben (Zelle 2) via .value und
    # rechnet sie in Dollar um. Die $-Werte stehen DIREKT NEBEN den
    # Eingabefeldern (Badges), nicht in einer eigenen Box/Zelle.
    mo.vstack([
        render_order_params_with_usd(params_ui),
        mo.Html(
            '<style>'
            # High-Contrast-Tabellen (Bugfix 2): schwarz auf weiss,
            # Cursorzeile invertiert (schwarz + weisser Text).
            '.bt-table-wrap{max-height:480px;overflow:auto;border:1px solid #94a3b8;'
            'border-radius:8px;background:#fff;margin-top:4px;}'
            '.bt-select-table{border-collapse:collapse;width:100%;background:#fff;'
            'color:#000;font-size:13px;}'
            '.bt-select-table th{background:#f1f5f9;color:#000;text-align:left;'
            'padding:6px 10px;border-bottom:2px solid #94a3b8;position:sticky;'
            'top:0;z-index:2;white-space:nowrap;}'
            '.bt-select-table td{padding:5px 10px;border-bottom:1px solid #e2e8f0;'
            'color:#000;white-space:nowrap;}'
            '.bt-select-table td.bt-cb{width:28px;text-align:center;}'
            '.bt-select-table th.bt-cb{width:28px;}'
            '.bt-select-table tbody tr:hover td{background:#000 !important;'
            'color:#fff !important;}'
            '.bt-select-table tbody tr:hover td.bt-cb{background:#000 !important;}'
            '.bt-select-table input[type=checkbox]{width:15px;height:15px;'
            'accent-color:#000;cursor:pointer;}'
            '</style>'
        ),
    ])
    return


@app.cell(hide_code=True)
def _():
    # ==========================================
    # 3a. STATE-SETUP (Modul-Singleton - STABIL ueber Re-Runs)
    # ==========================================
    # Die State-Objekte kommen aus backtest_lab.ui_state.get_marimo_states().
    # marimo matcht State-Konsumenten per Objekt-Identitaet (globals[ref]
    # is state). Wuerde diese Zelle bei jedem Re-Run (z. B. Start oder
    # 'Run all') NEUE mo.state()-Objekte erzeugen, zeigten die Dialog-
    # Buttons in Zelle 4 auf verwaiste States -> tote Buttons. Das Modul-
    # Singleton liefert IMMER dieselben Instanzen -> Klicks funktionieren.
    from backtest_lab.ui_state import get_marimo_states
    _st = get_marimo_states()
    go_state = _st["go_state"]
    set_go_state = _st["set_go_state"]
    save_msg = _st["save_msg"]
    set_save_msg = _st["set_save_msg"]
    refresh_ctl = _st["refresh_ctl"]
    # Bugfix 4: Loesch-Dialog + Reload-Trigger der Backtest-Run-Verwaltung
    del_state = _st["del_state"]
    set_del_state = _st["set_del_state"]
    bt_ctl = _st["bt_ctl"]
    set_bt_ctl = _st["set_bt_ctl"]
    # Bugfix 5 (Checkbox-Reaktivitaet): Zaehler fuer Checkbox-Klicks der
    # Auswahl-Tabellen. Zelle 3 und 6b lesen `sel_ctl()` -> Re-Run bei
    # jedem Klick -> GO-/Loesch-Button aktualisiert sich.
    sel_ctl = _st["sel_ctl"]
    set_sel_ctl = _st["set_sel_ctl"]
    # Trade-Detail (Klick auf einen Backtest-Run, Zelle 6c): run_id des
    # Runs, dessen Einzeltrades angezeigt werden sollen ("" = keine
    # Auswahl). Wird von den 👁-Buttons in render_checkbox_table gesetzt
    # (ui.py); Zelle 6c liest `detail_rid()` -> Re-Run bei jedem Klick.
    detail_rid = _st["detail_rid"]
    set_detail_rid = _st["set_detail_rid"]
    return (
        bt_ctl,
        del_state,
        detail_rid,
        go_state,
        refresh_ctl,
        save_msg,
        sel_ctl,
        set_bt_ctl,
        set_del_state,
        set_detail_rid,
        set_go_state,
        set_save_msg,
        set_sel_ctl,
    )


@app.cell(hide_code=True)
def _(
    COMPLEXITY_CFG,
    DB_MARKET,
    bar_counts_for,
    dt,
    estimate_complexity,
    go_allowed,
    mo,
    params_ui,
    run_cbs,
    run_ids,
    run_ui,
    runs_df,
    save_state,
    sel_ctl,
    selected_checkbox_ids,
    set_go_state,
    set_save_msg,
    state,
    txt_free_tag,
    txt_override,
):
    # ==========================================
    # 3. RUN-ZÄHLER, KOMPLEXITÄT, GO + SAVE
    # ==========================================
    # UI-Trigger kommen aus der isolierten Setup-Zelle "3a. STATE-SETUP".
    # Hier KEINE mo.state()-Aufrufe: jeder Re-Run dieser Zelle (Parameter-
    # Änderung!) würde neue State-Objekte erzeugen und Werte zurücksetzen.

    # Bugfix 5 (Checkbox-Reaktivitaet): sel_ctl LESEN -> Re-Run dieser Zelle
    # bei jedem Checkbox-Klick der Run-Auswahl (die Checkboxen liegen in
    # Listen ohne marimo-Binding; der on_change-Bump in render_checkbox_table
    # erhoeht sel_ctl -> nur so aktualisiert sich der GO-Button live).
    _sel = sel_ctl()

    sel_runs = selected_checkbox_ids(run_cbs, run_ids)
    selected = runs_df[runs_df["run_id"].isin(sel_runs)] if sel_runs else runs_df.iloc[0:0]

    # OrderConfig aus den UI-Werten (validiert; Fehler -> Hinweis)
    try:
        order_cfg = params_ui.to_order_config()
        _cfg_err = None
    except ValueError as _e:
        order_cfg = None
        _cfg_err = str(_e)

    d_from, d_to = params_ui.resolve_dates()
    d_from_s = d_from.isoformat() if d_from else None
    d_to_s = d_to.isoformat() if d_to else None

    # Komplexität: Kreuzprodukt (Symbole/TFs der Auswahl x 1 Param-Set)
    if selected.empty or order_cfg is None:
        report = None
    else:
        _syms = sorted({str(r["symbol"]) for _, r in selected.iterrows()})
        _tfs = sorted({str(r["timeframe"]) for _, r in selected.iterrows()})
        _counts = bar_counts_for(
            _syms, _tfs, date_from=d_from_s, date_to=d_to_s, db_path=DB_MARKET
        )
        report = estimate_complexity(_counts, 1, COMPLEXITY_CFG)

    n_jobs = int(len(selected)) if order_cfg is not None else 0
    _go_ok = (
        go_allowed(report)
        and order_cfg is not None
        and _cfg_err is None
        and n_jobs > 0
    )

    def _on_go(_value):
        """Klick auf GO: hängenden Lauf-Zustand bereinigen, dann Dialog."""
        # Fall: running=True, aber der Worker-Thread ist tot (z. B. nach
        # Kernel-Neustart, Crash oder hängendem mp.Pool). Dann blockiert
        # Zelle 4 den Dialog (`not running`-Bedingung) -> GO scheint tot.
        if run_ui.get_state()["running"] and not run_ui.is_alive():
            run_ui.finish([], None)
            run_ui.set_message("", "")
        set_go_state("confirm")

    btn_go = mo.ui.button(
        label=f"🚀 GO — Backtest starten ({n_jobs} Run(s))",
        on_click=_on_go,
        disabled=not _go_ok,
    )

    def _save_state(_value=None):
        state["selected_run_ids"] = sel_runs
        try:
            state["order"] = params_ui.to_state()["order"]
            state["date_range"] = params_ui.to_state()["date_range"]
        except ValueError:
            set_save_msg("⚠️ Ungültige Parameter – Stand nicht gespeichert")
            return
        state["run_name_override"] = txt_override.value
        state["free_tag"] = txt_free_tag.value
        save_state(state)
        set_save_msg(
            f"Stand gespeichert ({dt.datetime.now().strftime('%H:%M:%S')})"
        )

    btn_save = mo.ui.button(label="💾 Stand speichern", on_click=_save_state)

    mo.vstack([
        mo.md(
            f"**Auswahl:** {n_jobs} Backtest(s) aus {len(sel_runs)} "
            f"Signal-Run(s) · Datum {d_from_s or 'von Anfang'} → "
            f"{d_to_s or 'bis Ende'}"
        ),
        render_complexity(report, COMPLEXITY_CFG),
        mo.md(f"⚠️ **Ungültige Parameter:** {_cfg_err}") if _cfg_err else mo.md(""),
        mo.hstack([btn_go, btn_save]),
    ])
    return (
        btn_go,
        btn_save,
        d_from_s,
        d_to_s,
        n_jobs,
        order_cfg,
        selected,
    )


@app.cell(hide_code=True)
def _(
    DB_ANALYTICS,
    DB_BACKTEST,
    DB_MARKET,
    BacktestJob,
    connect_backtest,
    d_from_s,
    d_to_s,
    dt,
    go_state,
    mo,
    n_jobs,
    order_cfg,
    order_params_json,
    params_ui,
    run_backtests_parallel,
    run_ui,
    save_state,
    selected,
    bt_ctl,
    set_bt_ctl,
    set_go_state,
    set_save_msg,
    state,
    threading,
    txt_free_tag,
    txt_override,
):
    # ==========================================
    # 4. SICHERHEITSABFRAGE + BACKTEST-START (Thread)
    # ==========================================

    def _start_run(_value=None):
        """Startet die Backtests in einem Hintergrund-Thread (UI bleibt reaktiv)."""
        # Guard: Die Buttons existieren IMMER (auch bei geschlossenem Dialog).
        # Start nur, wenn der Dialog wirklich bestaetigt ist und kein Lauf aktiv.
        if go_state() != "confirm" or run_ui.get_state()["running"]:
            return
        run_ui.reset(n_jobs)
        run_ui.set_message("🕒 Backtest gestartet …", "spinner")
        # WICHTIG: save_msg-Trigger -> Zelle 5 re-runt SOFORT und rendert
        # den Refresh-Timer (nur bei running=True), der den Fortschritt pollt.
        set_save_msg(f"🕒 Backtest läuft – {n_jobs} Run(s)")
        # UI-Stand sichern (spätestens beim GO-Start; Order/Datum validiert,
        # da GO nur mit gueltigem order_cfg freigegeben ist).
        try:
            state["order"] = params_ui.to_state()["order"]
            state["date_range"] = params_ui.to_state()["date_range"]
        except ValueError:
            pass  # ungueltige Zwischeneingaben nicht persistieren
        state["selected_run_ids"] = [str(r.run_id) for r in selected.itertuples()]
        # Bugfix 7 (Run-Name): Nur manuell editierte Namen verwenden. Sonst
        # laesst man den Runner den Namen aus der LIVE-Config bauen -> der
        # Run-Name folgt der Konfiguration (z. B. SL-Aenderung) -> eigen-
        # staendiger Run mit korrektem Namen in der backtest_runs-Tabelle.
        if state.get("run_name_manual"):
            state["run_name_override"] = txt_override.value.strip()
        else:
            state["run_name_override"] = ""
        state["run_name_manual"] = bool(state.get("run_name_manual"))
        state["free_tag"] = txt_free_tag.value
        save_state(state)

        _name_override = state["run_name_override"] or None
        jobs = [
            BacktestJob(
                signal_run_id=str(row["run_id"]),
                symbol=str(row["symbol"]),
                timeframe=str(row["timeframe"]),
                order_config=order_cfg,
                date_from=d_from_s,
                date_to=d_to_s,
                free_tag=txt_free_tag.value.strip(),
                run_name_override=_name_override,
            )
            for _, row in selected.iterrows()
        ]

        def _worker():
            try:
                ids = run_backtests_parallel(
                    jobs,
                    n_workers=None,  # CPU-Kerne
                    db_market=DB_MARKET,
                    db_analytics=DB_ANALYTICS,
                    db_backtest=DB_BACKTEST,
                    progress_callback=run_ui.progress,
                    cancel_callback=run_ui.is_cancelled,
                )
                _con = connect_backtest(DB_BACKTEST, ensure_schema=False)
                _n_runs_db = _con.execute(
                    "SELECT COUNT(*) FROM backtest_runs"
                ).fetchone()[0]
                _n_trades_db = _con.execute(
                    "SELECT COUNT(*) FROM backtest_trades"
                ).fetchone()[0]
                _con.close()

                summary = {
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "runs": len(ids),
                    "runs_db": _n_runs_db,
                    "trades_db": _n_trades_db,
                    # BacktestJob ist eine (frozen) Dataclass -> Attribut-
                    # Zugriff, NICHT subscription (r["symbol"] wuerfe
                    # TypeError: 'BacktestJob' object is not subscriptable).
                    "symbols": sorted({str(r.symbol) for r in jobs}),
                    "timeframes": sorted({str(r.timeframe) for r in jobs}),
                    "order": order_params_json(order_cfg),
                    "date_from": d_from_s,
                    "date_to": d_to_s,
                    "cancelled": run_ui.is_cancelled(),
                }
                state["last_backtest"] = summary
                save_state(state)
                run_ui.finish(ids, summary)
                # Verwaltungs-Tabelle (Zelle 6b) frisch laden lassen
                set_bt_ctl(bt_ctl() + 1)
                if run_ui.is_cancelled():
                    run_ui.set_message(
                        f"⏹ Abgebrochen – {len(ids)} Run(s) gespeichert", "info"
                    )
                else:
                    run_ui.set_message(
                        f"✅ Backtest fertig – {len(ids)} Run(s) neu berechnet "
                        f"({_n_runs_db} Runs, {_n_trades_db} Trades gesamt)", "ok"
                    )
            except Exception as e:
                run_ui.fail(str(e))
                run_ui.set_message(f"❌ Fehler: {e}", "err")

        _t = threading.Thread(target=_worker, daemon=True)
        run_ui.set_thread(_t)
        _t.start()
        set_go_state("idle")  # Dialog schließen (state-Trigger)

    def _cancel(_value=None):
        """Abbrechen: Dialog schließen und Spinner-Meldung zurücksetzen."""
        set_go_state("idle")
        run_ui.set_message("", "")

    # ------------------------------------------------------------------
    # Buttons IMMER instanziieren (nicht nur im Dialog-Zweig!):
    # 1) IDProvider vergibt pro Zellen-Run deterministische IDs an fester
    #    Position -> IDs bleiben ueber Re-Runs stabil.
    # 2) `return btn_confirm, btn_cancel` EXPORTIERT die Buttons -> sie
    #    liegen als starke Referenzen in den Globals. Die marimo-Registry
    #    haelt nur WEAKREFS (registry.py: weakref.ref); ohne Export koennte
    #    der Garbage Collector die Buttons einsammeln -> tote Buttons.
    # 3) Export registriert auch die Event-Bindings (bound_names) fuer den
    #    Event-Dispatcher.
    # ------------------------------------------------------------------
    btn_confirm = mo.ui.button(label="✅ Ja, starten", kind="danger", on_click=_start_run)
    btn_cancel = mo.ui.button(label="Nein, abbrechen", on_click=_cancel)

    # --- Validierungs-Hinweis statt stillem Fehlschlag ---
    if n_jobs == 0 or order_cfg is None:
        if go_state() == "confirm":
            set_go_state("idle")
        _out = mo.vstack([
            mo.md("⚠️ **Keine gültige Auswahl** – der Backtest kann nicht starten."),
            mo.md(
                "Bitte mindestens einen Signal-Run ankreuzen und gültige "
                "Order-Parameter wählen (Spread, Size; SL/TP optional)."
            ),
        ])
    # --- Sicherheitsabfrage (Modal-Ersatz): erst bestätigen, dann starten ---
    elif go_state() == "confirm" and not run_ui.get_state()["running"]:
        _syms = sorted({str(r["symbol"]) for _, r in selected.iterrows()})
        _tfs = sorted({str(r["timeframe"]) for _, r in selected.iterrows()})
        if state.get("run_name_manual"):
            _run_name_disp = f"`{txt_override.value}`"
        else:
            _run_name_disp = "_(automatisch aus der aktuellen Konfiguration)_"
        _confirm_text = (
            f"**Backtest starten?**\n\n"
            f"- {n_jobs} Lauf/Läufe auf Basis der gewählten Signal-Runs\n"
            f"- Symbole: {_syms}\n"
            f"- TFs: {_tfs}\n"
            f"- Datum: {d_from_s or 'von Anfang'} → {d_to_s or 'bis Ende'}\n"
            f"- Order: Spread {order_cfg.spread_pct} % · SL "
            f"{order_cfg.stop_loss_pct} % · TP {order_cfg.take_profit_pct} % · "
            f"Size {order_cfg.position_size_pct} % · Hebel {order_cfg.leverage:g} · "
            f"Equity {order_cfg.equity:,.0f} $ · "
            f"Re-Entry gleiche Bar: "
            f"{'EIN (Exit + neuer Entry)' if order_cfg.reentry_same_bar else 'AUS (nur Exit)'}\n"
            f"  _SL/TP = % Kursbewegung (Preis-Distanz vom Entry), nicht % "
            f"des Positionswerts._\n"
            f"- Run-Name: {_run_name_disp}\n\n"
            f"_Idempotent: Ein bereits vorhandener Backtest mit 1:1 identischer "
            f"Konfiguration (Signal-Run + Order + Datum) wird überschrieben – "
            f"keine endlosen Duplikate._"
        )
        _out = mo.vstack([mo.md(_confirm_text), mo.hstack([btn_confirm, btn_cancel])])
    else:
        _out = mo.md("")
    # WICHTIG: `_out` muss die LETZTE Top-Level-Expression der Zelle sein.
    # marimo zeigt nur die letzte Expression einer Zelle an; ein if/elif/else-
    # Block als letztes Statement erzeugt KEINEN Output (Dialog bliebe unsichtbar).
    _out
    return btn_cancel, btn_confirm


@app.cell(hide_code=True)
def _(
    DB_BACKTEST,
    connect_backtest,
    mo,
    refresh_ctl,
    run_ui,
    save_msg,
):
    # ==========================================
    # 5. FORTSCHRITT + ABBRUCH + STATUSMELDUNG + ERGEBNIS (live)
    # ==========================================
    import pandas as pd

    # Refresh-Trigger LESEN: erst dadurch re-runt diese Zelle alle 0.5s.
    # (Der Timer laeuft, weil refresh_ctl unten im Output gerendert wird.)
    _ = refresh_ctl.value
    _st = run_ui.get_state()

    def _on_stop(_value):
        run_ui.cancel()
        if not run_ui.is_alive():
            # Hängender Zustand: running=True, aber kein Thread -> aufräumen
            run_ui.finish([], None)
            run_ui.set_message("⏹ Abgebrochen – Lauf war nicht mehr aktiv", "info")

    _btn_stop = mo.ui.button(label="⏹ Stopp", kind="warn", on_click=_on_stop)

    # Statusmeldung "Stand gespeichert" (state-basiert, sofort sichtbar)
    _save_el = mo.md(f"💾 {save_msg()}") if save_msg() else mo.md("")

    # Statusmeldung (Start, fertig, gespeichert, Fehler) – mit Spinner wenn nötig
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
            mo.md(f"**Letzter Backtest** ({_s['timestamp']}) — {_txt}"),
            mo.md(
                f"- {_s['runs']} Run(s) verarbeitet · Symbole {_s['symbols']} · "
                f"TFs {_s['timeframes']}"
            ),
            mo.md(
                f"- Order: `{_s.get('order', '')}` · Datum "
                f"{_s.get('date_from') or 'von Anfang'} → {_s.get('date_to') or 'bis Ende'}"
            ),
            mo.md(f"- Backtest-DB: **{_s['runs_db']} Runs**, **{_s['trades_db']} Trades**"),
        ]
        # Ergebnistabelle der neuen Runs (direkt aus backtest_data)
        try:
            _con = connect_backtest(DB_BACKTEST, ensure_schema=False)
            _runs_res = _con.execute(
                "SELECT run_name, symbol, timeframe, trade_count, net_profit, "
                "win_rate, profit_factor, created_at "
                "FROM backtest_runs ORDER BY created_at DESC LIMIT 10"
            ).df()
            _con.close()
            if not _runs_res.empty:
                # tz-aware -> lesbarer String (Berliner Wanduhrzeit)
                _runs_res["created_at"] = (
                    pd.to_datetime(_runs_res["created_at"])
                    .dt.tz_convert("Europe/Budapest")
                    .dt.strftime("%Y-%m-%d %H:%M")
                )
                _lines.append(mo.md("**Neueste Backtest-Runs:**"))
                _tbl = mo.ui.table(
                    _runs_res,
                    page_size=5,
                    show_column_summaries=False,
                    label="backtest_runs (letzte 10)",
                )
                _lines.append(_tbl)
        except Exception:
            pass
        _out = mo.vstack(_lines)
    else:
        _out = mo.md("_Noch kein Lauf – Signal-Run ankreuzen, Parameter wählen und GO drücken._")
    # Live-Aktualisierung: Timer NUR während eines Laufs rendern.
    # Sonst tickt er permanent -> globale Ausführen-Schaltfläche bleibt gelb
    # und es laufen ständig Prozesse. Nach Lauf-Ende stoppt der Timer.
    _ls = _st.get("last_summary") or {}
    _last_ts = _ls.get("timestamp", "") or ""
    if _st["running"]:
        _refresh_el = mo.hstack([
            refresh_ctl,
            mo.md(f"🕒 läuft … · letzter Lauf-Ende: **{_last_ts}**" if _last_ts else "🕒 läuft …"),
        ])
    elif _last_ts:
        # Ende des letzten Laufs (Sekunden-Genauigkeit) als Rückmeldung
        _refresh_el = mo.md(f"✅ Letzter Lauf beendet: **{_last_ts}**")
    else:
        _refresh_el = mo.md("")
    mo.vstack([_refresh_el, _save_el, _msg_el, _out])
    return


@app.cell(hide_code=True)
def _(mo):
    # ==========================================
    # 5a. BACKTEST-RUN-NEU-LADEN-BUTTON (eigene Zelle!)
    # ==========================================
    # marimo-Regel: Der `.value`-Zugriff ist in der Zelle, die das Element
    # erzeugt, VERBOTEN. Der Button wird daher hier erzeugt und in Zelle 6a
    # via `btn_reload_btruns.value` gelesen (reaktiver Trigger).
    btn_reload_btruns = mo.ui.button(
        label="🔄 Backtest-Runs neu laden", on_click=lambda _v: None
    )
    return btn_reload_btruns


@app.cell(hide_code=True)
def _(
    DB_BACKTEST,
    btn_reload_btruns,
    bt_ctl,
    get_backtest_runs,
    mo,
    render_checkbox_table,
):
    # ==========================================
    # 6a. BACKTEST-RUN-VERWALTUNG (Tabelle aus backtest_data) - Bugfix 4
    # ==========================================
    # Reaktive Trigger: "Neu laden"-Button (Klick) + bt_ctl-Zaehler (nach
    # Backtest-Ende oder Loeschung) -> Zelle re-runt und liest die Runs
    # frisch aus backtest_data.
    # WICHTIG (Bugfix 4): Der bt_ctl-Wert MUSS verwendet werden, sonst
    # entfernt marimo die (scheinbar tote) State-Read-Instruktion per
    # Dead-Code-Elimination und die Tabelle aktualisiert sich nie.
    _reload = btn_reload_btruns.value
    _bt = int(bt_ctl())

    bt_runs_df = get_backtest_runs(DB_BACKTEST)
    if not bt_runs_df.empty:
        bt_runs_df = bt_runs_df.copy()
        bt_runs_df["net_profit"] = bt_runs_df["net_profit"].fillna(0.0).map(
            lambda v: f"{v:,.2f}"
        )
        bt_runs_df["win_rate"] = bt_runs_df["win_rate"].fillna(0.0).map(
            lambda v: f"{v*100:.1f} %"
        )
        # Bugfix 6/8: Max Win ($), Max Drawdown ($), Worst Trade ($),
        # Gewinn-% und SL-Exits in der Tabelle.
        # - max_drawdown ($) = KUMULATIVER Equity-Drawdown (Peak-to-Trough
        #   der Equity-Kurve), NICHT der groesste Einzelverlust - der steht
        #   separat in `worst_trade` (min pnl). Bei SL 0.5 % und Hebel 1000
        #   ist der Einzelverlust ~500 $ (+ Slippage/Gaps); der kumulative
        #   Drawdown summiert sich ueber viele SL-Treffer (z. B. 8 545 $
        #   = 73 % vom Peak 11 708 $ auf 3 163 $).
        # - net_profit_pct = net_profit / equity * 100 (Gewinn in % des
        #   Startkapitals, z. B. 1 113 $ von 10 000 $ = 11,1 %).
        bt_runs_df["max_win"] = bt_runs_df["max_win"].fillna(0.0).map(
            lambda v: f"{v:,.2f}"
        )
        if "worst_trade" in bt_runs_df.columns:
            bt_runs_df["worst_trade"] = bt_runs_df["worst_trade"].fillna(0.0).map(
                lambda v: f"{v:,.2f}"
            )
        bt_runs_df["max_drawdown"] = bt_runs_df["max_drawdown"].fillna(0.0).map(
            lambda v: f"{v:,.2f}"
        )
        if "sl_count" in bt_runs_df.columns:
            bt_runs_df["sl_count"] = bt_runs_df["sl_count"].fillna(0).astype(int)
        if "net_profit_pct" in bt_runs_df.columns:
            bt_runs_df["net_profit_pct"] = bt_runs_df["net_profit_pct"].fillna(0.0).map(
                lambda v: f"{v:.1f} %"
            )

    _bt_container, bt_cbs, bt_ids, bt_detail_btns = render_checkbox_table(
        bt_runs_df,
        display_cols=[
            "run_name", "symbol", "timeframe",
            "trade_count", "sl_count",
            "net_profit", "net_profit_pct",
            "win_rate", "max_win", "worst_trade", "max_drawdown",
            "created_at",
        ],
        page_size=50,
        label="Backtest-Runs (aus backtest_data)",
        empty_hint="_Keine Backtest-Runs vorhanden - noch keinen Backtest ausgeführt oder alle gelöscht._",
        show_detail=True,
        detail_tooltip="Einzeltrades dieses Runs anzeigen (neuester zuerst)",
    )

    mo.vstack([
        mo.hstack([
            btn_reload_btruns,
            mo.md(
                f"_{len(bt_runs_df)} Backtest-Run(s) · "
                f"Aktualisierung #{_bt}_"
            ),
        ]),
        _bt_container,
    ])
    return bt_cbs, bt_ids, bt_detail_btns, bt_runs_df


@app.cell(hide_code=True)
def _(
    DB_BACKTEST,
    bt_cbs,
    bt_ctl,
    bt_ids,
    delete_backtest_runs,
    del_state,
    dt,
    mo,
    sel_ctl,
    selected_checkbox_ids,
    set_bt_ctl,
    set_del_state,
    set_save_msg,
):
    # ==========================================
    # 6b. BACKTEST-RUN-LÖSCHEN (Sicherheitsabfrage + DB-Löschung) - Bugfix 4
    # ==========================================
    # Bugfix 5 (Checkbox-Reaktivitaet): sel_ctl LESEN -> Re-Run bei jedem
    # Klick in der Verwaltungs-Tabelle -> Loesch-Button aktualisiert sich.
    _sel = sel_ctl()
    sel_bt_ids = selected_checkbox_ids(bt_cbs, bt_ids)

    def _on_del_click(_value):
        """Loesch-Dialog oeffnen (nur wenn Auswahl vorhanden)."""
        if sel_bt_ids:
            set_del_state("confirm")

    def _on_del_confirm(_value):
        """Sicherheitsabfrage bestaetigt: Runs inkl. Trades aus der DB loeschen."""
        try:
            n = delete_backtest_runs(sel_bt_ids, DB_BACKTEST)
            set_del_state("idle")
            set_bt_ctl(bt_ctl() + 1)  # Tabelle (Zelle 6a) frisch laden
            set_save_msg(
                f"🗑 {n} Backtest-Run(s) gelöscht "
                f"({dt.datetime.now().strftime('%H:%M:%S')})"
            )
        except Exception as _e:
            set_del_state("idle")
            set_save_msg(f"❌ Löschen fehlgeschlagen: {_e}")

    def _on_del_cancel(_value):
        """Loesch-Dialog abbrechen."""
        set_del_state("idle")

    btn_del = mo.ui.button(
        label=f"🗑 Löschen ({len(sel_bt_ids)})",
        kind="danger",
        on_click=_on_del_click,
        disabled=not sel_bt_ids,
    )
    btn_del_confirm = mo.ui.button(
        label="✅ Ja, löschen", kind="danger", on_click=_on_del_confirm
    )
    btn_del_cancel = mo.ui.button(label="Nein, abbrechen", on_click=_on_del_cancel)

    # --- Sicherheitsabfrage (Modal-Ersatz, gleiches Muster wie Zelle 4) ---
    if del_state() == "confirm" and sel_bt_ids:
        _out = mo.vstack([
            mo.md(
                f"**Backtest-Runs wirklich löschen?**\n\n"
                f"- **{len(sel_bt_ids)} Run(s)** werden unwiderruflich aus "
                f"`backtest_data.duckdb` entfernt (inkl. aller Trades).\n"
            ),
            mo.hstack([btn_del_confirm, btn_del_cancel]),
        ])
    else:
        if del_state() == "confirm":
            set_del_state("idle")  # Auswahl leer geworden -> Dialog schließen
        _out = mo.hstack([
            btn_del,
            mo.md(
                "_Runs in der Tabelle oben ankreuzen, um sie zu löschen._"
                if not sel_bt_ids else f"_{len(sel_bt_ids)} Run(s) markiert._"
            ),
        ])
    # WICHTIG: `_out` muss die LETZTE Top-Level-Expression der Zelle sein
    # (marimo zeigt nur die letzte Expression einer Zelle an).
    _out
    return btn_del, btn_del_cancel, btn_del_confirm


@app.cell(hide_code=True)
def _(DB_BACKTEST, bt_runs_df, get_backtest_trades, mo):
    # ==========================================
    # 6c. TRADE-DETAILS (Einzeltrades eines Runs) - Klick auf 👁
    # ==========================================
    # Klick auf den 👁-Button in der Run-Tabelle (Zelle 6a) setzt den
    # Modul-State `detail_rid` (gebunden in Zelle 3a) -> diese Zelle
    # re-runt und zeigt alle Einzeltrades des Runs (neuester zuerst).
    # Die Trades-Tabelle ist ein `mo.ui.table` (native Spaltensortierung
    # + Such-/Filterfeld).
    btn_detail_close = mo.ui.button(
        label="✖ Schließen", on_click=lambda _v: set_detail_rid("")
    )

    _rid = detail_rid()
    if not _rid:
        _out = mo.md(
            "_Klicke in der Run-Tabelle auf **👁** (Spalte „Trades“), um die "
            "Einzeltrades eines Runs anzuzeigen._"
        )
    else:
        _trades = get_backtest_trades(_rid, DB_BACKTEST)

        # Run-Kontext aus der Verwaltungs-Tabelle (Zelle 6a) fuer den Header
        _run_row = None
        if bt_runs_df is not None and not bt_runs_df.empty and "run_id" in bt_runs_df.columns:
            _m = bt_runs_df[bt_runs_df["run_id"].astype(str) == str(_rid)]
            if not _m.empty:
                _run_row = _m.iloc[0]

        if _run_row is not None:
            _header = mo.md(
                f"**Einzeltrades:** `{_run_row['run_name']}` · "
                f"{_run_row['symbol']} {_run_row['timeframe']} · "
                f"{_run_row['trade_count']} Trades · "
                f"Netto {_run_row['net_profit']} $"
            )
        else:
            _header = mo.md(f"**Einzeltrades** (Run `{_rid[:16]}…`)")

        if _trades is None or _trades.empty:
            _out = mo.vstack([
                _header,
                mo.md("_Dieser Run enthält keine Trades._"),
                btn_detail_close,
            ])
        else:
            _view = _trades.rename(columns={
                "run_name": "Run-Name",
                "symbol": "Symbol",
                "timeframe": "TF",
                "entry_time": "Entry (Berlin)",
                "exit_time": "Exit (Berlin)",
                "duration": "Dauer",
                "direction": "Richtung",
                "entry_price": "Entry-Preis",
                "exit_price": "Exit-Preis",
                "move_pct": "Kursbewegung %",
                "pnl": "PnL $",
                "pnl_equity_pct": "PnL % Equity",
                "r_multiple": "R-Multiple",
                "exit_reason": "Exit-Grund",
            })
            _tbl = mo.ui.table(
                _view,
                page_size=25,
                label=(
                    f"{len(_trades)} Einzeltrades – neuester zuerst "
                    f"(Spalten sortierbar, Suche filtert)"
                ),
                hidden_columns=["run_id"],
                show_column_summaries=False,
                show_search=True,
                max_height=520,
            )
            _out = mo.vstack([
                _header,
                mo.hstack([
                    btn_detail_close,
                    mo.md("_👁 eines anderen Runs klicken ersetzt diese Ansicht._"),
                ]),
                _tbl,
            ])
    # WICHTIG: `_out` muss die LETZTE Top-Level-Expression der Zelle sein.
    _out
    return btn_detail_close


if __name__ == "__main__":
    app.run()
