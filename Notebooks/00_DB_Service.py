import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    # ==========================================
    # SETUP: Pfade, Importe & Konstanten
    # ==========================================
    import sys
    from pathlib import Path
    import marimo as mo
    import duckdb
    import pandas as pd

    PROJ_ROOT = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path.cwd()
    if str(PROJ_ROOT) not in sys.path:
        sys.path.append(str(PROJ_ROOT))

    DATA_DIR = PROJ_ROOT / "data"
    DB_MARKET_DATA = DATA_DIR / "market_data.duckdb"
    DB_APP_DATA = DATA_DIR / "app_data.duckdb"

    SYMBOLS = ["SILVER", "GOLD", "BTCUSD"]
    TF_LIST = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M10", "M5", "M2", "M1"]
    ALL_TIMEFRAMES = "ALLE Timeframes"

    WINDOW_BARS = 500
    WARMUP = 200
    OFFSET_MAX = 20000
    return (
        ALL_TIMEFRAMES,
        DATA_DIR,
        DB_APP_DATA,
        DB_MARKET_DATA,
        OFFSET_MAX,
        Path,
        SYMBOLS,
        TF_LIST,
        WARMUP,
        WINDOW_BARS,
        duckdb,
        mo,
        pd,
    )


@app.cell(hide_code=True)
def _(duckdb):
    # ==========================================
    # DB-VERBINDUNGS-HELFER
    # ==========================================
    def open_conn(db_path, read_only=False):
        return duckdb.connect(str(db_path), read_only=read_only)

    def close_conn(con):
        try:
            if con is not None:
                con.close()
        except Exception:
            pass

    return close_conn, open_conn


@app.cell(hide_code=True)
def _(DB_APP_DATA, close_conn, open_conn):
    # ==========================================
    # 1 · SYMBOL-FUNKTIONEN (app_data.duckdb)
    # ==========================================
    def ensure_broker_symbols_schema(con):
        """Idempotente Migration: broker_symbols um point (DOUBLE) + digits (INTEGER) ergaenzen.

        DuckDB: `ADD COLUMN IF NOT EXISTS` ist idempotent - funktioniert auf
        Bestands-DBs (640 Zeilen) wie auf frischen, ohne Rebuild.
        """
        con.execute("ALTER TABLE broker_symbols ADD COLUMN IF NOT EXISTS point DOUBLE")
        con.execute("ALTER TABLE broker_symbols ADD COLUMN IF NOT EXISTS digits INTEGER")

    def get_symbols_data():
        con = open_conn(DB_APP_DATA, read_only=True)
        try:
            rows = con.execute(
                "SELECT symbol, path, is_favorite, point, digits "
                "FROM broker_symbols ORDER BY symbol ASC"
            ).fetchall()
            return [
                {
                    "symbol": str(r[0]),
                    "path": str(r[1]) if r[1] else "",
                    "is_favorite": bool(r[2]),
                    "point": float(r[3]) if r[3] is not None else None,
                    "digits": int(r[4]) if r[4] is not None else None,
                }
                for r in rows
            ]
        finally:
            close_conn(con)

    def get_favorite_symbols():
        con = open_conn(DB_APP_DATA, read_only=True)
        try:
            rows = con.execute(
                "SELECT symbol FROM broker_symbols WHERE is_favorite = TRUE ORDER BY symbol ASC"
            ).fetchall()
            return [str(r[0]) for r in rows]
        finally:
            close_conn(con)

    def set_favorite(symbol, fav):
        """Setzt das Favoriten-Flag eines Symbols (True=⭐, False=kein Favorit)."""
        con = open_conn(DB_APP_DATA)
        try:
            ensure_broker_symbols_schema(con)
            con.execute(
                """
                INSERT INTO broker_symbols (symbol, path, is_favorite)
                VALUES (?, '', ?)
                ON CONFLICT (symbol) DO UPDATE SET is_favorite = ?, updated_at = now()
                """,
                [symbol, fav, fav],
            )
            return {"ok": True, "msg": f"'{symbol}' ist jetzt {'⭐ Favorit' if fav else 'kein Favorit'}."}
        finally:
            close_conn(con)

    def toggle_favorite(symbol):
        con = open_conn(DB_APP_DATA)
        try:
            current = con.execute(
                "SELECT is_favorite FROM broker_symbols WHERE symbol = ?", [symbol]
            ).fetchone()
            new_state = not bool(current[0]) if current else True
            return set_favorite(symbol, new_state)
        finally:
            close_conn(con)

    def sync_symbols_from_mt5():
        import MetaTrader5 as mt5
        try:
            if not mt5.initialize():
                return {"ok": False, "msg": f"MT5 nicht verfügbar (Fehlercode {mt5.last_error()}). Nutze DB-Stand."}
            symbols = mt5.symbols_get()
            if not symbols:
                return {"ok": False, "msg": "MT5 liefert keine Symbole. Nutze DB-Stand."}
            con = open_conn(DB_APP_DATA)
            try:
                ensure_broker_symbols_schema(con)
                for s in symbols:
                    con.execute(
                        """
                        INSERT INTO broker_symbols (symbol, path, is_favorite, point, digits)
                        VALUES (?, ?, FALSE, ?, ?)
                        ON CONFLICT (symbol) DO UPDATE SET
                            path = EXCLUDED.path,
                            point = EXCLUDED.point,
                            digits = EXCLUDED.digits,
                            updated_at = now()
                        """,
                        [s.name, getattr(s, "path", ""),
                         getattr(s, "point", None), getattr(s, "digits", None)],
                    )
            finally:
                close_conn(con)
            return {"ok": True, "msg": f"{len(symbols)} Symbole von MT5 übernommen."}
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass

    return (
        ensure_broker_symbols_schema,
        get_favorite_symbols,
        get_symbols_data,
        set_favorite,
        sync_symbols_from_mt5,
        toggle_favorite,
    )


@app.cell(hide_code=True)
def _(mo):
    # ==========================================
    # 1b · FAVORITEN-UI: STATE-TRIGGER
    # ==========================================
    # allow_self_loops=True ist NOTWENDIG: Die UI-Zelle (1c) erzeugt die
    # Buttons/Suchfeld UND liest dieselben States. on_click/on_change-
    # Handler laufen im Execution-Context der ERZEUGER-Zelle; ohne
    # allow_self_loops wuerde marimo genau diese Zelle vom State-Re-Run
    # ausschliessen ("no self-loops") -> Suche und Toggle waeren tot.
    fav_refresh, set_fav_refresh = mo.state(0, allow_self_loops=True)
    search_q, set_search_q = mo.state("", allow_self_loops=True)
    last_msg, set_last_msg = mo.state("", allow_self_loops=True)
    # Merkt die zuletzt gewaehlte Symbol-Auswahl (Wert, nicht Label), damit
    # ein Re-Run (z. B. nach Suche/Toggle) das Dropdown nicht auf den
    # Default zuruecksetzt. Kein Re-Run noetig, wenn sich nur die Auswahl
    # aendert -> allow_self_loops=False.
    sel_sym, set_sel_sym = mo.state("", allow_self_loops=False)
    return (
        fav_refresh,
        last_msg,
        search_q,
        sel_sym,
        set_fav_refresh,
        set_last_msg,
        set_search_q,
        set_sel_sym,
    )


@app.cell(hide_code=True)
def _(
    fav_refresh,
    get_favorite_symbols,
    get_symbols_data,
    last_msg,
    mo,
    search_q,
    sel_sym,
    set_fav_refresh,
    set_favorite,
    set_last_msg,
    set_search_q,
    set_sel_sym,
    sync_symbols_from_mt5,
    toggle_favorite,
):
    # ==========================================
    # 1c · KOMPLETTE FAVORITEN-UI (eine Zelle)
    # ==========================================
    _ = fav_refresh()   # State-Trigger: Re-Run nach Toggle/Markieren → sofort aktuell
    query = search_q()  # Suchbegriff (Suchfeld on_change → State)
    meldung = last_msg()

    # Symbole + Favoriten (frisch aus der DB, damit Sync sofort sichtbar wird)
    syms_data = get_symbols_data()
    all_syms = [s["symbol"] for s in syms_data]
    favorites = get_favorite_symbols()
    default_sym = "SILVER" if "SILVER" in all_syms else (all_syms[0] if all_syms else None)

    # Aktuelle Auswahl: gespeicherte Symbol-Auswahl bevorzugen, sonst Default.
    # So springt das Dropdown nach einem Re-Run (Suche/Toggle) nicht zurueck.
    current_sym = sel_sym() if sel_sym() in all_syms else default_sym

    # Haupt-Dropdown: ⭐-Favoriten zuerst, Rest alphabetisch
    non_fav = [s for s in all_syms if s not in favorites]
    fav_opts = {f"⭐ {s}": s for s in favorites}
    rest_opts = {s: s for s in non_fav}
    opts = {**fav_opts, **rest_opts}

    def _label_for(sym):
        if sym is None:
            return None
        return f"⭐ {sym}" if sym in favorites else sym

    def _on_symbol_change(v):
        # v ist der Symbol-WERT (nicht das Label), z. B. "GOLD"
        set_sel_sym(v)

    symbol_dd = mo.ui.dropdown(
        options=opts,
        value=_label_for(current_sym),
        label="Symbol (⭐ Favoriten zuerst)",
        on_change=_on_symbol_change,
    )

    # Suchfeld (on_change → State, damit alles in einer Zelle bleiben kann)
    def _on_search(v):
        set_search_q(v)

    suchfeld = mo.ui.text(
        value=query,
        label="🔍 Symbol suchen",
        placeholder="z.B. SIL, Gold, BTC...",
        on_change=_on_search,
    )

    # Suchtreffer
    such = (query or "").strip().upper()
    treffer = [s for s in all_syms if such in s.upper()] if such else all_syms[:100]
    treffer_dd = mo.ui.dropdown(
        options=treffer if treffer else ["— keine Treffer —"],
        value=(treffer[0] if treffer else "— keine Treffer —"),
        label=f"Suchtreffer ({len(treffer)})",
    )

    def _on_mark(_v):
        r = set_favorite(treffer_dd.value, True)
        set_last_msg(r.get("msg", ""))
        set_fav_refresh(fav_refresh() + 1)
        return r

    mark_btn = mo.ui.button(
        label="⭐ Als Favorit markieren",
        on_click=_on_mark,
        disabled=not treffer,
    )

    def _on_toggle(_v):
        r = (
            toggle_favorite(symbol_dd.value)
            if symbol_dd.value
            else {"ok": False, "msg": "Kein Symbol gewählt."}
        )
        set_last_msg(r.get("msg", ""))
        set_fav_refresh(fav_refresh() + 1)
        return r

    toggle_btn = mo.ui.button(
        label="⭐ Favorit togglen",
        on_click=_on_toggle,
    )

    def _on_sync(_v):
        r = sync_symbols_from_mt5()
        set_last_msg(r.get("msg", ""))
        set_fav_refresh(fav_refresh() + 1)
        return r

    fav_sync_btn = mo.ui.button(
        label="🔄 Symbole von MT5 laden",
        on_click=_on_sync,
    )

    fav_str = ", ".join(favorites) if favorites else "—"
    mo.vstack([
        mo.md("## 1 · Symbol-Auswahl & Favoriten"),
        mo.md(f"**⭐ Favoriten ({len(favorites)}):** {fav_str}"),
        suchfeld,
        treffer_dd,
        mark_btn,
        symbol_dd,
        toggle_btn,
        fav_sync_btn,
        mo.md(f"**Letzte Aktion:** {meldung}") if meldung else mo.md(""),
    ])
    return (symbol_dd,)


@app.cell(hide_code=True)
def _(ALL_TIMEFRAMES, TF_LIST, mo):
    # ==========================================
    # 2 · TIMEFRAME-AUSWAHL (inkl. "ALLE Timeframes")
    # ==========================================
    tf_dd = mo.ui.dropdown(options=[ALL_TIMEFRAMES] + TF_LIST, value="M30", label="Timeframe")

    mo.vstack([
        mo.md("## 2 · Timeframe"),
        tf_dd,
    ])
    return (tf_dd,)


@app.cell(hide_code=True)
def _(
    ALL_TIMEFRAMES,
    DB_MARKET_DATA,
    SYMBOLS,
    TF_LIST,
    duckdb,
    mo,
    pd,
    symbol_dd,
    tf_dd,
):
    # ==========================================
    # 3 · MT5-POLLING & SYNC (market_data.duckdb)
    # ==========================================
    def _ensure_mt5():
        """Verbindet mit MT5; startet das Terminal automatisch, falls nötig."""
        import os
        import MetaTrader5 as mt5
        if mt5.initialize():
            return True
        for p in [
            r"F:\MetaTrader 5\terminal64.exe",
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
        ]:
            if os.path.exists(p) and mt5.initialize(path=p):
                return True
        return False

    def check_mt5_connection():
        import MetaTrader5 as mt5
        try:
            if not _ensure_mt5():
                return {"ok": False, "msg": f"❌ MT5 nicht erreichbar (Fehlercode {mt5.last_error()}). Bitte MT5-Terminal öffnen und einloggen."}
            acct = mt5.account_info()
            if acct is None:
                return {"ok": False, "msg": "❌ Kein Konto im MT5-Terminal eingeloggt."}
            missing = [s for s in SYMBOLS if not mt5.symbol_select(s, True)]
            msg = f"✅ Verbunden: {acct.company} | Server: {acct.server} | Login: {acct.login}"
            if missing:
                msg += f"\n⚠️ Symbole nicht aktivierbar: {', '.join(missing)}"
            return {"ok": True, "msg": msg}
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass

    def get_latest_timestamp(con, symbol, tf):
        res = con.execute(
            "SELECT MAX(time) FROM ohlcv_bars WHERE symbol = ? AND timeframe = ?",
            [symbol, tf],
        ).fetchone()
        return res[0] if res and res[0] is not None else None

    def sync_market_data(symbols, timeframes):
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta, timezone
        if not _ensure_mt5():
            return {"msg": f"❌ MT5 nicht erreichbar (Fehlercode {mt5.last_error()}). Bitte Terminal öffnen.", "results": []}
        results = []
        total_bars = 0
        try:
            for symbol in symbols:
                if not mt5.symbol_select(symbol, True):
                    results.append({"Symbol": symbol, "TF": "—", "Modus": "FEHLER", "Kerzen": 0, "Detail": "symbol_select fehlgeschlagen"})
                    continue
                con = duckdb.connect(str(DB_MARKET_DATA))
                try:
                    for tf in timeframes:
                        tf_mt5 = getattr(mt5, f"TIMEFRAME_{tf}")
                        last_time = get_latest_timestamp(con, symbol, tf)
                        if last_time is not None:
                            # UPDATE: Immer die letzten 365 Tage (alle Timeframes)
                            # per Range-Request holen. last_time dient NUR als
                            # Trigger - bewusst kein 5.000-Bars-Fenster, damit
                            # aeltere, unbemerkte Luecken additiv gefuellt werden
                            # und lange Pausen (>3 Tage bei M1) keine Luecken
                            # hinterlassen. INSERT OR REPLACE füllt per Upsert.
                            now_utc = datetime.now(timezone.utc)
                            date_from = now_utc - timedelta(days=365)
                            rates = mt5.copy_rates_range(symbol, tf_mt5, date_from, now_utc)
                            mode = "UPDATE"
                            detail = f"1 Jahr ({date_from:%Y-%m-%d} → {now_utc:%Y-%m-%d})"
                        else:
                            rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, 10_000_000)
                            mode = "VOLLIMPORT"
                            detail = "komplette Historie"
                        if rates is None:
                            results.append({"Symbol": symbol, "TF": tf, "Modus": "FEHLER", "Kerzen": 0, "Detail": str(mt5.last_error())})
                            continue
                        if len(rates) == 0:
                            results.append({"Symbol": symbol, "TF": tf, "Modus": "leer", "Kerzen": 0, "Detail": "keine Kerzen von MT5"})
                            continue
                        df = pd.DataFrame(rates)
                        df["symbol"] = symbol
                        df["timeframe"] = tf
                        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
                        df = df.drop_duplicates(subset=["time"], keep="last")
                        df = df[["symbol", "timeframe", "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
                        con.register("df_temp", df)
                        con.execute("""
                            INSERT OR REPLACE INTO ohlcv_bars (
                                symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume
                            )
                            SELECT symbol, timeframe, "time", open, high, low, close, tick_volume, spread, real_volume
                            FROM df_temp
                        """)
                        con.unregister("df_temp")
                        total_bars += len(df)
                        results.append({"Symbol": symbol, "TF": tf, "Modus": mode, "Kerzen": len(df), "Detail": detail})
                finally:
                    con.close()
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass
        return {"msg": f"✅ Fertig: {total_bars:,} Kerzen in {len(results)} Durchläufen verarbeitet.", "results": results}

    def selected_symbols():
        return [symbol_dd.value]

    def selected_timeframes():
        tf = tf_dd.value
        return TF_LIST if tf == ALL_TIMEFRAMES else [tf]

    conn_btn = mo.ui.button(label="🔗 MT5-Verbindung prüfen", on_click=lambda _v: check_mt5_connection())
    sync_btn = mo.ui.button(
        label="📥 Sync starten",
        on_click=lambda _v: sync_market_data(selected_symbols(), selected_timeframes()),
    )

    mo.vstack([
        mo.md("## 3 · MT5-Polling & Sync (market_data.duckdb)"),
        mo.md("**Hinweis:** Der Sync läuft blockierend. Zum Testen erst 1 Symbol + 1 TF wählen (z. B. SILVER / M30)."),
        mo.hstack([conn_btn, sync_btn]),
    ])
    return conn_btn, sync_btn


@app.cell(hide_code=True)
def _(conn_btn, mo, pd, sync_btn):
    # ==========================================
    # 3b · STATUS: MT5-Verbindung & Sync-Ergebnis
    # ==========================================
    def fmt_sync(v):
        if v is None or v == 0:
            return "—"
        if isinstance(v, dict):
            return v.get("msg", str(v))
        return str(v)

    sync_val = sync_btn.value
    if isinstance(sync_val, dict) and sync_val.get("results"):
        sync_body = mo.ui.table(pd.DataFrame(sync_val["results"]), page_size=15)
    else:
        sync_body = mo.md("_Noch kein Sync ausgeführt._")

    mo.vstack([
        mo.md(f"**MT5-Verbindung:** {fmt_sync(conn_btn.value)}"),
        mo.md(f"**Sync:** {fmt_sync(sync_val)}"),
        sync_body,
    ])
    return


@app.cell(hide_code=True)
def _(
    DB_MARKET_DATA,
    close_conn,
    mo,
    open_conn,
    pd,
    sync_btn,
):
    # ==========================================
    # 4 · MARKTDATEN-SERVICES (market_data.duckdb)
    # ==========================================
    _ = sync_btn  # Re-Run nach jedem Sync, damit die Tabelle aktuell bleibt

    def get_available_pairs():
        con = open_conn(DB_MARKET_DATA, read_only=True)
        try:
            rows = con.execute("""
                SELECT symbol, timeframe, COUNT(*) AS bars,
                       MIN(time AT TIME ZONE 'UTC') AS t_min,
                       MAX(time AT TIME ZONE 'UTC') AS t_max
                FROM ohlcv_bars
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """).fetchall()
            df = pd.DataFrame(rows, columns=["Symbol", "TF", "Kerzen", "von", "bis"])
            # BKZ-Kanon (docs/ZEITBASIS_KANON.md): die SQL projiziert bereits
            # die naive Broker-Kerzen-Zeit (kein Offset). to_datetime(...,
            # errors="coerce") schuetzt gegen leere DB (MIN/MAX = NULL ->
            # object-Spalten, .dt wuerde mit AttributeError scheitern).
            df["von"] = pd.to_datetime(df["von"], errors="coerce")
            df["bis"] = pd.to_datetime(df["bis"], errors="coerce")
            return df
        finally:
            close_conn(con)

    pairs_df = get_available_pairs()
    mo.vstack([
        mo.md("## 4 · Marktdaten-Services (market_data.duckdb)"),
        mo.md(f"**Verfügbare Paare:** {len(pairs_df)} Kombinationen · {pairs_df['Kerzen'].sum():,} Kerzen gesamt"),
        mo.ui.table(pairs_df, page_size=15),
    ])
    return


@app.cell(hide_code=True)
def _(DATA_DIR, Path, close_conn, duckdb, mo, open_conn, pd):
    # ==========================================
    # 5 · KOMPAKTIERUNG (alle duckdb-Dateien)
    # ==========================================
    def get_fragmentation(db_path):
        db_path = Path(db_path)
        if not db_path.exists():
            return {"Datei": db_path.name, "Größe MB": 0, "Bloat MB": 0, "Bloat %": 0}
        file_bytes = db_path.stat().st_size
        con = open_conn(db_path, read_only=True)
        try:
            res = con.execute("PRAGMA database_size;").fetchone()
        finally:
            close_conn(con)
        block_size, used_blocks = (res[2], res[4]) if res else (262144, 0)
        netto = used_blocks * block_size
        bloat = max(0, file_bytes - netto)
        return {
            "Datei": db_path.name,
            "Größe MB": round(file_bytes / (1024 ** 2), 1),
            "Bloat MB": round(bloat / (1024 ** 2), 1),
            "Bloat %": round(bloat / file_bytes * 100, 1) if file_bytes else 0,
        }

    def compact_database(db_path):
        db_path = Path(db_path).resolve()
        tmp_path = db_path.with_name(db_path.stem + ".compacted.duckdb")
        if tmp_path.exists():
            tmp_path.unlink()
        src_con = duckdb.connect(str(db_path))
        try:
            src_catalog = db_path.stem
            dst_sql = str(tmp_path).replace("\\", "/")
            src_con.execute(f"ATTACH '{dst_sql}' AS new_db")
            src_con.execute(f'COPY FROM DATABASE "{src_catalog}" TO new_db')
            src_con.execute("DETACH new_db")
        finally:
            src_con.close()
        db_path.unlink()
        tmp_path.rename(db_path)
        return get_fragmentation(db_path)

    def compact_all_databases():
        rows = []
        for db_file in sorted(DATA_DIR.glob("*.duckdb")):
            before = get_fragmentation(db_file)
            after = compact_database(db_file)
            rows.append({
                "Datei": db_file.name,
                "Größe vorher MB": before["Größe MB"],
                "Bloat vorher %": before["Bloat %"],
                "Größe nachher MB": after["Größe MB"],
                "Bloat nachher %": after["Bloat %"],
            })
        return {"msg": "✅ Kompaktierung abgeschlossen.", "df": pd.DataFrame(rows)}

    # run_button: Klick setzt .value=True → Zelle 5b läuft → zeigt Spinner
    # (sofortiges "läuft"-Feedback), Ergebnis erscheint nach Abschluss in 5b.
    compact_btn = mo.ui.run_button(label="🗜️ Alle duckdb-Dateien kompaktieren")

    mo.vstack([
        mo.md("## 5 · Kompaktierung (alle duckdb-Dateien)"),
        mo.md("**Hinweis:** Benötigt exklusiven Zugriff – alle DB-Connections sind geschlossen. Bei market_data (~1,3 GB) dauert der Vorgang einige Minuten und benötigt ~1,3 GB freien Speicherplatz."),
        compact_btn,
    ])
    return compact_all_databases, compact_btn


@app.cell(hide_code=True)
def _(compact_all_databases, compact_btn, mo):
    # ==========================================
    # 5b · STATUS: KOMPAKTIERUNG (Ausführung + Ergebnis)
    # ==========================================
    # .value wird hier (Zelle 5b) gelesen – NICHT in der Erzeuger-Zelle 5,
    # sonst RuntimeError. Klick → Zelle 5b läuft, Button zeigt Spinner.
    if compact_btn.value:
        compact_result = compact_all_databases()
    else:
        compact_result = None

    if compact_result is not None:
        compact_body = mo.ui.table(compact_result["df"], page_size=15)
        msg = compact_result["msg"]
    else:
        compact_body = mo.md("_Noch keine Kompaktierung ausgeführt._")
        msg = "—"

    mo.vstack([
        mo.md(f"**Kompaktierung:** {msg}"),
        compact_body,
    ])
    return


@app.cell(hide_code=True)
def _(OFFSET_MAX, mo):
    # ==========================================
    # 6a · FENSTER-SLIDER (eigene Zelle – .value erst in Zelle 6b lesen)
    # ==========================================
    fenster = mo.ui.slider(
        start=0,
        stop=OFFSET_MAX,
        step=50,
        value=OFFSET_MAX,
        label="Fenster (rechts = aktuell · nach links schieben = Vergangenheit)",
    )

    mo.md("**Chart-Fenster:** Mit dem Slider in die Vergangenheit scrollen.")
    return (fenster,)


@app.cell(hide_code=True)
def _(
    ALL_TIMEFRAMES,
    DB_MARKET_DATA,
    OFFSET_MAX,
    WARMUP,
    WINDOW_BARS,
    fenster,
    mo,
    symbol_dd,
    tf_dd,
):
    # ==========================================
    # 6b · CHART (Lightweight Charts, lokale Library)
    # ==========================================
    import importlib
    import algos.chart_plugins
    import algos.chart_engine
    # Reload-Reihenfolge: chart_plugins VOR chart_engine
    importlib.reload(algos.chart_plugins)
    importlib.reload(algos.chart_engine)
    from algos.chart_engine import load_candles, show_chart
    from algos.ma_indicator import MAIndicator

    if tf_dd.value == ALL_TIMEFRAMES:
        out = mo.md("**Chart:** Bitte einen einzelnen Timeframe wählen (nicht **ALLE Timeframes**).")
    else:
        offset = OFFSET_MAX - int(fenster.value)
        df = load_candles(
            symbol=symbol_dd.value,
            timeframe=tf_dd.value,
            limit=WINDOW_BARS,
            end_offset_bars=offset,
            warmup_bars=WARMUP,
            db_path=DB_MARKET_DATA,
        )
        if len(df) <= 1:
            out = mo.md(f"**Keine Daten für {symbol_dd.value} {tf_dd.value} bei Offset {offset}** – vor dem Datenanfang.")
        else:
            ma = MAIndicator(ma_type="EHMA", period=6, smoothing=10, alpha_factor=3.0)
            df = ma.apply(df, generate_signals=True)
            chart = show_chart(
                df=df,
                symbol=symbol_dd.value,
                timeframe=tf_dd.value,
                ma_indicator=ma,
                show_day_separators=True,
                show_signals=True,
                min_segment_len=3,
                warmup_bars=WARMUP,
                visible_bars=WINDOW_BARS,
                width=1200,
                height=500,
                scale_width=55,
            )
            out = mo.vstack([
                mo.md("## 6 · Chart"),
                fenster,
                chart,
            ])
    out
    return


if __name__ == "__main__":
    app.run()
