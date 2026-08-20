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

    TZ_OFFSET_HOURS = 2
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
        TZ_OFFSET_HOURS,
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
def _(DB_APP_DATA, close_conn, mo, open_conn):
    # ==========================================
    # 1 · SYMBOL-AUSWAHL & FAVORITEN (app_data.duckdb)
    # ==========================================
    def get_symbols_data():
        con = open_conn(DB_APP_DATA, read_only=True)
        try:
            rows = con.execute(
                "SELECT symbol, path, is_favorite FROM broker_symbols ORDER BY symbol ASC"
            ).fetchall()
            return [
                {
                    "symbol": str(r[0]),
                    "path": str(r[1]) if r[1] else "",
                    "is_favorite": bool(r[2]),
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
                for s in symbols:
                    con.execute(
                        """
                        INSERT INTO broker_symbols (symbol, path, is_favorite)
                        VALUES (?, ?, FALSE)
                        ON CONFLICT (symbol) DO UPDATE SET path = EXCLUDED.path, updated_at = now()
                        """,
                        [s.name, getattr(s, "path", "")],
                    )
            finally:
                close_conn(con)
            return {"ok": True, "msg": f"{len(symbols)} Symbole von MT5 übernommen."}
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass

    symbols_data = get_symbols_data()
    all_syms = [s["symbol"] for s in symbols_data]
    default_sym = "SILVER" if "SILVER" in all_syms else (all_syms[0] if all_syms else None)

    # Suchfeld für die Symbol-Suche
    suchfeld = mo.ui.text(
        label="🔍 Symbol suchen",
        placeholder="z.B. SIL, Gold, BTC...",
    )

    sym_sync_btn = mo.ui.button(label="🔄 Symbole von MT5 laden", on_click=lambda _v: sync_symbols_from_mt5())

    mo.vstack([
        mo.md("## 1 · Symbol-Auswahl & Favoriten"),
        suchfeld,
        sym_sync_btn,
    ])
    return (
        all_syms,
        default_sym,
        get_favorite_symbols,
        set_favorite,
        suchfeld,
        sym_sync_btn,
        toggle_favorite,
    )


@app.cell(hide_code=True)
def _(all_syms, mo, set_favorite, suchfeld):
    # ==========================================
    # 1b · SUCHTREFFER & ALS FAVORIT MARKIEREN
    # ==========================================
    such = suchfeld.value.strip().upper()
    if such:
        treffer = [s for s in all_syms if such in s.upper()]
    else:
        treffer = all_syms[:100]

    treffer_dd = mo.ui.dropdown(
        options=treffer if treffer else ["— keine Treffer —"],
        value=(treffer[0] if treffer else "— keine Treffer —"),
        label=f"Suchtreffer ({len(treffer)})",
    )
    fav_btn = mo.ui.button(
        label="⭐ Als Favorit markieren",
        on_click=lambda _v: set_favorite(treffer_dd.value, True),
        disabled=not treffer,
    )

    mo.vstack([
        mo.md(f"**Suchergebnis:** {such if such else '(leer – zeige erste 100 Symbole)'}"),
        treffer_dd,
        fav_btn,
    ])
    return (fav_btn,)


@app.cell(hide_code=True)
def _(
    all_syms,
    default_sym,
    fav_btn,
    get_favorite_symbols,
    mo,
    suchfeld,
    toggle_favorite,
):
    # ==========================================
    # 1c · SYMBOL-DROPDOWN: Favoriten zuerst, dann alphabetisch
    # ==========================================
    _ = fav_btn.value  # Re-Run nach Favorit-Änderung (Sortierung aktualisieren)
    _ = suchfeld.value

    favorites = get_favorite_symbols()
    non_fav = [s for s in all_syms if s not in favorites]
    fav_opts = {f"⭐ {s}": s for s in favorites}
    rest_opts = {s: s for s in non_fav}
    # value muss der Label-Key sein, nicht der Symbolwert (marimo validiert gegen Keys)
    default_label = (
        (f"⭐ {default_sym}" if default_sym in favorites else default_sym)
        if default_sym in all_syms
        else None
    )
    symbol_dd = mo.ui.dropdown(
        options={**fav_opts, **rest_opts},
        value=default_label,
        label="Symbol (⭐ Favoriten zuerst)",
    )
    sym_fav_btn = mo.ui.button(
        label="⭐ Favorit togglen",
        on_click=lambda _v: toggle_favorite(symbol_dd.value),
    )

    mo.vstack([
        symbol_dd,
        sym_fav_btn,
    ])
    return sym_fav_btn, symbol_dd


@app.cell(hide_code=True)
def _(fav_btn, get_favorite_symbols, mo, sym_fav_btn, sym_sync_btn):
    # ==========================================
    # 1d · STATUS: Favoriten & Meldungen
    # ==========================================
    favs = get_favorite_symbols()
    fav_str = ", ".join(favs) if favs else "—"

    def fmt_fav(v):
        if v is None or v == 0:
            return "—"
        if isinstance(v, dict):
            return v.get("msg", str(v))
        return str(v)

    mo.vstack([
        mo.md(f"**⭐ Favoriten ({len(favs)}):** {fav_str}"),
        mo.md(f"**Favorit setzen:** {fmt_fav(fav_btn.value)}"),
        mo.md(f"**Toggle:** {fmt_fav(sym_fav_btn.value)}"),
        mo.md(f"**Symbol-Sync:** {fmt_fav(sym_sync_btn.value)}"),
    ])
    return


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
                            rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, 5_000)
                            mode = "UPDATE"
                        else:
                            rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, 10_000_000)
                            mode = "VOLLIMPORT"
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
                        results.append({"Symbol": symbol, "TF": tf, "Modus": mode, "Kerzen": len(df), "Detail": ""})
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
def _(DB_MARKET_DATA, close_conn, mo, open_conn, pd, sync_btn):
    # ==========================================
    # 4 · MARKTDATEN-SERVICES (market_data.duckdb)
    # ==========================================
    _ = sync_btn  # Re-Run nach jedem Sync, damit die Tabelle aktuell bleibt

    def get_available_pairs():
        con = open_conn(DB_MARKET_DATA, read_only=True)
        try:
            rows = con.execute("""
                SELECT symbol, timeframe, COUNT(*) AS bars, MIN(time) AS t_min, MAX(time) AS t_max
                FROM ohlcv_bars
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """).fetchall()
            return pd.DataFrame(rows, columns=["Symbol", "TF", "Kerzen", "von", "bis"])
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

    compact_btn = mo.ui.button(label="🗜️ Alle duckdb-Dateien kompaktieren", on_click=lambda _v: compact_all_databases())

    mo.vstack([
        mo.md("## 5 · Kompaktierung (alle duckdb-Dateien)"),
        mo.md("**Hinweis:** Benötigt exklusiven Zugriff – alle DB-Connections sind geschlossen. Bei market_data (~1,3 GB) dauert der Vorgang einige Minuten und benötigt ~1,3 GB freien Speicherplatz."),
        compact_btn,
    ])
    return (compact_btn,)


@app.cell(hide_code=True)
def _(compact_btn, mo):
    # ==========================================
    # 5b · STATUS: Kompaktierung
    # ==========================================
    compact_val = compact_btn.value
    if isinstance(compact_val, dict) and compact_val.get("df") is not None:
        compact_body = mo.ui.table(compact_val["df"], page_size=15)
        msg = compact_val.get("msg", "—")
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
    TZ_OFFSET_HOURS,
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
            tz_offset_hours=TZ_OFFSET_HOURS,
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
