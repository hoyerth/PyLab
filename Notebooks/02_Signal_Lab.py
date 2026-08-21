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
    # Dev-Reload: der laufende Marimo-Kernel cached importierte Module.
    # Ohne Reload wuerde eine alte Version (z. B. ohne set_message) verwendet.
    import importlib
    sweep_ui = importlib.reload(sweep_ui)
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

    mo.md("## 🧪 Signal Lab v2 — Massentests")
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


@app.cell(hide_code=True)
def _(FAV, SYMBOLS, TIMEFRAMES, mo, state):
    # ==========================================
    # 1. SYMBOLE & TIMEFRAMES (Mehrfachauswahl)
    # ==========================================
    # Optionen als {Label → Roh-Symbol}; Favoriten bekommen ⭐.
    # WICHTIG: mo.ui.multiselect verlangt im `value` die Option-Keys (Labels),
    # `.value` liefert beim Lesen ebenfalls die Labels zurück → Rück-Mapping nötig.
    sym_options = {}
    for s in SYMBOLS:
        sym_options[f"⭐ {s}" if s in FAV else s] = s

    # State kann Roh-Symbole ODER bereits Labels enthalten (Alt-Daten) → normalisieren
    _saved = [s.replace("⭐ ", "") for s in state["symbols"]]
    _saved = [s for s in _saved if s in SYMBOLS]
    _init_labels = [label for label, sym in sym_options.items() if sym in _saved]

    sel_symbols = mo.ui.multiselect(
        sym_options,
        value=_init_labels,
        label="Symbole",
    )
    sel_tfs = mo.ui.multiselect(
        TIMEFRAMES,
        value=[t for t in state["timeframes"] if t in TIMEFRAMES],
        label="Timeframes",
    )
    mo.hstack([sel_symbols, sel_tfs], widths=[1, 1])
    return sel_symbols, sel_tfs, sym_options


@app.cell(hide_code=True)
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


@app.cell(hide_code=True)
def _(DATE_MAX, DATE_MIN, TIMEFRAMES, dt, mo, state):
    # ==========================================
    # 3. STRATEGIE, DATUMSBEREICH, HTF-OPTIONEN
    # ==========================================
    # State kann den Key ODER bereits das Label enthalten (Alt-Daten) → normalisieren
    _strat_raw = state["strategy"]
    _strat_key = _strat_raw if _strat_raw in ("grid", "random") else "grid"
    dd_strategy = mo.ui.dropdown(
        {"grid": "Grid (vollständiges Kreuzprodukt)", "random": "Random (Stichprobe)"},
        value=_strat_key,
        label="Strategie",
    )
    num_sample = mo.ui.number(1, 10000, 1, value=state["random_sample"], label="Stichproben-Größe (random)")

    dmin = DATE_MIN.date() if DATE_MIN is not None else None
    dmax = DATE_MAX.date() if DATE_MAX is not None else None
    _dr = state.get("date_range") or {}

    def _pdate(s, default):
        """ISO-String -> date, sonst default."""
        if s:
            try:
                return dt.date.fromisoformat(str(s))
            except ValueError:
                pass
        return default

    # Datum: Kalender-Picker + manuelles Textfeld (JJJJ-MM-TT) je Grenze.
    # Die manuelle Eingabe erlaubt auch Jahreszahlen, die der Picker schwer erreicht.
    date_from = mo.ui.date(dmin, dmax, value=_pdate(_dr.get("from"), dmin), label="Von (Kalender)")
    date_to = mo.ui.date(dmin, dmax, value=_pdate(_dr.get("to"), dmax), label="Bis (Kalender)")
    txt_from = mo.ui.text(value=_dr.get("from") or "", label="Von (manuell JJJJ-MM-TT)", full_width=True)
    txt_to = mo.ui.text(value=_dr.get("to") or "", label="Bis (manuell JJJJ-MM-TT)", full_width=True)

    def resolve_date(txt, picker, default=None):
        """Manuelle Eingabe gewinnt; sonst Kalenderwert; sonst default."""
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

    sw_htf = mo.ui.switch(value=bool(state.get("htf_exact_time", False)),
                          label="HTF-Exact-Time (Logik auf kleinerem TF)")
    dd_small_tf = mo.ui.dropdown(
        TIMEFRAMES, value=state.get("htf_small_tf", "M15"), label="Kleiner TF für Exact-Time"
    )

    sw_delete = mo.ui.switch(
        value=bool(state.get("sweep_delete_existing", True)),
        label="Update-Modus: vor dem Lauf vorhandene Runs/Signale für gewählte Symbole/TFs löschen",
    )

    def _on_free_tag(v):
        state["free_tag"] = v

    txt_free_tag = mo.ui.text(value=state.get("free_tag", ""),
                              label="Freier Tag (optional, wird an den Run-Namen angehängt, z. B. 'v2' oder 'Q3')",
                              on_change=_on_free_tag)

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
    # 4a. STATE-SETUP (Modul-Singleton - STABIL ueber Re-Runs)
    # ==========================================
    # Die State-Objekte kommen aus signal_lab.ui_state.get_marimo_states().
    # marimo matcht State-Konsumenten per Objekt-Identitaet (globals[ref]
    # is state). Wuerde diese Zelle bei jedem Re-Run (z. B. Start oder
    # 'Run all') NEUE mo.state()-Objekte erzeugen, zeigten die Dialog-
    # Buttons in Zelle 5 auf verwaiste States -> tote Buttons. Das Modul-
    # Singleton liefert IMMER dieselben Instanzen -> Klicks funktionieren.
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
    SYMBOLS,
    build_run_definition,
    build_run_name,
    date_from,
    date_to,
    dd_ma_type,
    dd_small_tf,
    dd_strategy,
    dt,
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
    # UI-Trigger kommen aus der isolierten Setup-Zelle "4a. STATE-SETUP".
    # Hier KEINE mo.state() aufrufe: jeder Re-Run dieser Zelle (Parameter-
    # Änderung!) würde neue State-Objekte erzeugen und die Werte zurücksetzen.

    ranges_ma = {
        "period": {"min": ma_p_min.value, "step": ma_p_step.value, "max": ma_p_max.value},
        "smoothing": {"min": ma_s_min.value, "step": ma_s_step.value, "max": ma_s_max.value},
        "alpha_factor": {"min": ma_a_min.value, "step": ma_a_step.value, "max": ma_a_max.value},
    }
    # Labels → Roh-Symbole (multiselect liefert Keys/Labels zurück)
    symbols = [sym_options.get(l, l.replace("⭐ ", "")) for l in sel_symbols.value]
    symbols = [s for s in symbols if s in SYMBOLS] or ["SILVER"]
    tfs = list(sel_tfs.value) or ["M30"]

    # Manuelle Datumseingabe gewinnt vor dem Kalenderwert
    date_from_val = resolve_date(txt_from.value, date_from)
    date_to_val = resolve_date(txt_to.value, date_to)

    definition = build_run_definition(
        symbols=symbols,
        timeframes=tfs,
        ranges=ranges_ma,
        date_from=date_from_val.isoformat() if date_from_val else None,
        date_to=date_to_val.isoformat() if date_to_val else None,
        strategy=dd_strategy.value,
        sample_size=int(num_sample.value or 50),
        htf_exact_time=bool(sw_htf.value),
        htf_small_tf=dd_small_tf.value or "M15",
        fixed_params={"ma_type": dd_ma_type.value},
    )

    n_runs = definition.count_runs()
    preview_params = definition.param_space[0] if definition.param_space else {}
    run_name_preview = build_run_name("MAIndicator", preview_params, symbols[0], tfs[0])

    # Run-Name: automatische Vorgabe (Beispiel aus erster Param-Kombination),
    # manuell änderbar. on_change sichert jede Eingabe sofort in state,
    # damit ein Zellen-Update den manuellen Text nicht überschreibt.
    def _on_name_change(v):
        state["run_name_override"] = v

    txt_override = mo.ui.text(
        value=state.get("run_name_override") or run_name_preview,
        label="Run-Name (manuell änderbar)",
        full_width=True,
        on_change=_on_name_change,
    )

    def _save_state(_value=None):
        state["symbols"] = [sym_options.get(l, l.replace("⭐ ", "")) for l in sel_symbols.value]
        state["timeframes"] = list(sel_tfs.value)
        state["ma"] = {
            "ma_type": dd_ma_type.value,
            "period": {"min": ma_p_min.value, "step": ma_p_step.value, "max": ma_p_max.value},
            "smoothing": {"min": ma_s_min.value, "step": ma_s_step.value, "max": ma_s_max.value},
            "alpha_factor": {"min": ma_a_min.value, "step": ma_a_step.value, "max": ma_a_max.value},
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
        set_save_msg(
            f"Stand gespeichert ({dt.datetime.now().strftime('%H:%M:%S')})"
        )

    def _on_go(_value):
        """Klick auf GO: hängenden Lauf-Zustand bereinigen, dann Dialog."""
        # Fall: running=True, aber der Worker-Thread ist tot (z. B. nach
        # Kernel-Neustart, Crash oder hängendem mp.Pool). Dann blockiert
        # Zelle 5 den Dialog (`not running`-Bedingung) -> GO scheint tot.
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
        mo.md(f"**Run-Zähler:** {n_runs} Läufe = {len(symbols)} Symbole × {len(tfs)} TFs × {len(definition.param_space)} Parameter-Sets"),
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
        """Startet den Sweep in einem Hintergrund-Thread (UI bleibt reaktiv)."""
        # Guard: Die Buttons existieren IMMER (auch bei geschlossenem Dialog).
        # Start nur, wenn der Dialog wirklich bestaetigt ist und kein Lauf aktiv.
        if go_state() != "confirm" or sweep_ui.get_state()["running"]:
            return
        sweep_ui.reset(definition.count_runs())
        sweep_ui.set_message("🕒 Massentest gestartet …", "spinner")
        # WICHTIG: save_msg-Trigger -> Zelle 6 re-runt SOFORT und rendert
        # den Refresh-Timer (nur bei running=True), der den Fortschritt pollt.
        set_save_msg(
            f"🕒 Massentest läuft – {definition.count_runs()} Runs"
        )
        # UI-Stand sichern (spätestens beim GO-Start)
        state["symbols"] = list(definition.symbols)
        state["timeframes"] = list(definition.timeframes)
        state["run_name_override"] = txt_override.value
        state["free_tag"] = txt_free_tag.value
        save_state(state)

        def _worker():
            try:
                deleted = 0
                if bool(sw_delete.value):
                    # Update-Modus: vorhandene Runs + Signale der gewählten
                    # Symbole/TFs löschen, damit der Zeitraum überschrieben wird.
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
                        f"({_n_runs_db} Runs gesamt)", "ok"
                    )
            except Exception as e:
                sweep_ui.fail(str(e))
                sweep_ui.set_message(f"❌ Fehler: {e}", "err")

        _t = threading.Thread(target=_worker, daemon=True)
        sweep_ui.set_thread(_t)
        _t.start()
        set_go_state("idle")  # Dialog schließen (state-Trigger)

    def _cancel(_value=None):
        """Abbrechen: Dialog schließen und Spinner-Meldung zurücksetzen."""
        set_go_state("idle")
        sweep_ui.set_message("", "")

    # ------------------------------------------------------------------
    # Buttons IMMER instanziieren (nicht nur im Dialog-Zweig!):
    # 1) IDProvider vergibt pro Zellen-Run deterministische IDs an fester
    #    Position -> IDs bleiben ueber Re-Runs stabil.
    # 2) `return btn_confirm, btn_cancel` EXPORTIERT die Buttons -> sie
    #    liegen als starke Referenzen in den Globals. Die marimo-Registry
    #    haelt nur WEAKREFS (registry.py: weakref.ref); ohne Export koennte
    #    der Garbage Collector die Buttons einsammeln -> Klick findet das
    #    Element nicht mehr -> tote Buttons.
    # 3) Export registriert auch die Event-Bindings (bound_names) fuer den
    #    Event-Dispatcher.
    # ------------------------------------------------------------------
    btn_confirm = mo.ui.button(label="✅ Ja, starten", kind="danger", on_click=_start_sweep)
    btn_cancel = mo.ui.button(label="Nein, abbrechen", on_click=_cancel)

    # --- Validierungs-Hinweis statt stillem Fehlschlag ---
    if not definition.param_space or not symbols or not tfs:
        if go_state() == "confirm":
            set_go_state("idle")
        _out = mo.vstack([
            mo.md("⚠️ **Keine gültige Konfiguration** – der Massentest kann nicht starten."),
            mo.md("Bitte mindestens ein Symbol, einen Timeframe und gültige MA-Ranges wählen."),
        ])
    # --- Sicherheitsabfrage (Modal-Ersatz): erst bestätigen, dann starten ---
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

        _out = mo.vstack([mo.md(_confirm_text), mo.hstack([btn_confirm, btn_cancel])])
    else:
        _out = mo.md("")
    # WICHTIG: `_out` muss die LETZTE Top-Level-Expression der Zelle sein.
    # marimo zeigt nur die letzte Expression einer Zelle an; ein if/elif/else-
    # Block als letztes Statement erzeugt KEINEN Output (Dialog bliebe unsichtbar).
    _out
    return btn_confirm, btn_cancel


@app.cell(hide_code=True)
def _(mo, refresh_ctl, save_msg, sweep_ui):
    # ==========================================
    # 6. FORTSCHRITT + ABBRUCH + STATUSMELDUNG (live)
    # ==========================================
    # Refresh-Trigger LESEN: erst dadurch re-runt diese Zelle alle 0.5s.
    # (Der Timer laeuft, weil refresh_ctl unten im Output gerendert wird.)
    _ = refresh_ctl.value
    _st = sweep_ui.get_state()
    def _on_stop(_value):
        sweep_ui.cancel()
        if not sweep_ui.is_alive():
            # Hängender Zustand: running=True, aber kein Thread -> aufräumen
            sweep_ui.finish([], None)
            sweep_ui.set_message("⏹ Abgebrochen – Lauf war nicht mehr aktiv", "info")

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
            mo.md(f"**Letzter Sweep** ({_s['timestamp']}) — {_txt}"),
            mo.md(
                f"- {_s['runs']} Runs verarbeitet ({_s['n_params']} Parameter-Sets)"
                f" · Symbole {_s['symbols']} · TFs {_s['timeframes']}"
            ),
            mo.md(f"- Analytics-DB: **{_s['runs_db']} Runs**, **{_s['events_db']} Events**"),
        ]
        if _s.get("deleted"):
            _lines.append(mo.md(f"- ♻️ Update-Modus: {_s['deleted']} alte Runs gelöscht"))
        _out = mo.vstack(_lines)
    else:
        _out = mo.md("_Noch kein Lauf – Konfiguration wählen und GO drücken._")
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
def _(mo, save_state, set_save_msg, state):
    # ==========================================
    # 7. QUICK LOOK (Chart-Schnellsicht, §7)
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

    def _save_ql(_value=None):
        state.setdefault("quick_look", {})["symbol_tf"] = txt_symbol_tf.value
        state["quick_look"]["overlay_tfs"] = list(sel_overlay.value)
        save_state(state)
        # Sichtbare Rückmeldung über die Statuszeile (Zelle 6)
        set_save_msg(
            f"Quick Look gespeichert ({txt_symbol_tf.value})"
        )

    btn_ql_save = mo.ui.button(label="💾 Quick Look merken", on_click=_save_ql)

    mo.vstack([
        mo.md("**Quick Look** — Chart-Fenster wie im Chart Inspector, "
              "mit M30-Signalen + HTF-Signalen (farbcodiert, versetzt)"),
        txt_symbol_tf,
        sel_overlay,
        btn_ql_save,
    ])
    return ql_slider, render_quick_look, sel_overlay, txt_symbol_tf


@app.cell(hide_code=True)
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
    # 8. QUICK LOOK — CHART-RENDER (reaktiv)
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
