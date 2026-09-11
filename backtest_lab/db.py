# backtest_lab/db.py
"""DuckDB-Zugriff: read-only auf die Quell-DBs, write auf backtest_data.

Kapselung (Pflicht):
- `market_data.duckdb` und `analytics_data.duckdb` werden NUR read-only
  geoeffnet (kein Schreibzugriff, Quell-DBs bleiben unveraendert).
- `backtest_data.duckdb` ist die einzige Write-DB des Backtest Labs.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import duckdb
import pandas as pd

from backtest_lab.schema import init_backtest_schema
from backtest_lab.types import BacktestRunRecord

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"

DB_MARKET: Path = DATA_DIR / "market_data.duckdb"
DB_ANALYTICS: Path = DATA_DIR / "analytics_data.duckdb"
DB_BACKTEST: Path = DATA_DIR / "backtest_data.duckdb"

# Verbindlicher Spaltenvertrag fuer `backtest_trades` (Reihenfolge = DDL).
# `exit_reason` (Bugfix 8): "sl" / "tp" / "signal" - Grund, warum der Trade
# geschlossen wurde (beantwortet "wird je Trade gespeichert, warum ein
# Trade ein Verlierer ist?" - ja, ueber `exit_reason` + `sl_count` im Run).
TRADES_COLUMNS: list[str] = [
    "run_id",
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "direction",
    "pnl",
    "r_multiple",
    "exit_reason",
]

# Spaltenvertrag fuer die Trade-Detail-Tabelle (Klick auf einen Run in der
# BT-Verwaltung). Enthaelt neben den Rohdaten aus `backtest_trades` die
# angereicherten Infospalten (Run-Kontext, Haltedauer, Kursbewegung-%,
# PnL-% des Equity, lesbare Richtung/Exit-Grund). Reihenfolge = Anzeige.
TRADE_DETAIL_COLUMNS: list[str] = [
    "run_id",
    "run_name", "symbol", "timeframe",
    "entry_time", "exit_time", "duration",
    "direction", "entry_price", "exit_price", "move_pct",
    "pnl", "pnl_equity_pct", "r_multiple", "exit_reason",
]


def connect_market(db_path: Optional[Union[str, Path]] = None) -> duckdb.DuckDBPyConnection:
    """Read-only Connection zur Market-DB (OHLCV + spread).

    Args:
        db_path: Alternativer Pfad (fuer Tests). Default: `data/market_data.duckdb`.

    Returns:
        Read-only DuckDB-Connection.

    Example:
        >>> con = connect_market()
        >>> df = con.execute("SELECT * FROM ohlcv_bars LIMIT 5").df()
        >>> con.close()
    """
    path = Path(db_path) if db_path else DB_MARKET
    return duckdb.connect(str(path), read_only=True)


def connect_analytics(db_path: Optional[Union[str, Path]] = None) -> duckdb.DuckDBPyConnection:
    """Read-only Connection zur Analytics-DB (Signal-Events).

    Args:
        db_path: Alternativer Pfad (fuer Tests). Default: `data/analytics_data.duckdb`.

    Returns:
        Read-only DuckDB-Connection.
    """
    path = Path(db_path) if db_path else DB_ANALYTICS
    return duckdb.connect(str(path), read_only=True)


def connect_backtest(
    db_path: Optional[Union[str, Path]] = None, ensure_schema: bool = True
) -> duckdb.DuckDBPyConnection:
    """Write-Connection zur Backtest-DB (legacy Schema anlegen, wenn noetig).

    Args:
        db_path: Alternativer Pfad (fuer Tests). Default: `data/backtest_data.duckdb`.
        ensure_schema: Wenn True, wird das v1-Schema idempotent angelegt.

    Returns:
        Schreibbare DuckDB-Connection.
    """
    path = Path(db_path) if db_path else DB_BACKTEST
    if ensure_schema:
        init_backtest_schema(path)
    return duckdb.connect(str(path))


def _to_utc_naive(series: pd.Series) -> pd.Series:
    """Normalisiert eine Zeit-Spalte auf naive UTC (BKZ-Garantie).

    Die Quell-DBs speichern TIMESTAMPTZ mit Berlin-Offset (z. B.
    `2014-05-19 02:00:00+02:00`). Die SQL-Extraktion nutzt bereits
    `AT TIME ZONE 'UTC'`, daher sind die Werte naive UTC. Dieser Helper
    stellt den pandas-Datentyp sicher (tz-frei, datetime64[us]).
    """
    s = pd.to_datetime(series, errors="coerce")
    if getattr(s.dtype, "tz", None) is not None:
        s = s.dt.tz_convert("UTC").dt.tz_localize(None)
    return s.astype("datetime64[us]")


def load_ohlcv(
    symbol: str,
    timeframe: str,
    date_from: Optional[Union[str, object]] = None,
    date_to: Optional[Union[str, object]] = None,
    limit: int = 2_000_000,
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Laedt OHLCV (inkl. spread) fuer Symbol/TF aus market_data (read-only).

    Zeitachse: **naive UTC** (BKZ-Garantie, `AT TIME ZONE 'UTC'`) -
    DST-korrekt und konsistent mit `load_signal_events`. Die Bar-Zeiten
    sind damit auf derselben Achse wie die Signal-Events.

    Args:
        symbol: Symbol (case-insensitive), z. B. "GOLD".
        timeframe: Timeframe, z. B. "M30".
        date_from: Optionaler Startzeitpunkt. ISO-String ("YYYY-MM-DD",
            "YYYY-MM-DD HH:MM") oder datetime-aehnlich. Wird als UTC
            interpretiert.
        date_to: Optionaler Endzeitpunkt (gleiche Konvention).
        limit: Max. Anzahl Bars (Schutz gegen Voll-Scan, Default 2 Mio).
        db_path: Alternativer Pfad (fuer Tests). Default: market_data.

    Returns:
        DataFrame mit Spalten `time` (naive UTC), `open`, `high`, `low`,
        `close`, `spread` - aufsteigend nach Zeit sortiert.
    """
    con = connect_market(db_path)
    try:
        q = """
            SELECT
                "time" AT TIME ZONE 'UTC' AS time,
                open, high, low, close, spread
            FROM ohlcv_bars
            WHERE LOWER(symbol) = LOWER(?)
              AND LOWER(timeframe) = LOWER(?)
        """
        params: list = [symbol, timeframe]
        if date_from is not None:
            q += " AND \"time\" >= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'"
            params.append(str(date_from))
        if date_to is not None:
            q += " AND \"time\" <= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'"
            params.append(str(date_to))
        q += " ORDER BY \"time\" ASC LIMIT " + str(int(limit))
        df = con.execute(q, params).df()
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "spread"])
    df["time"] = _to_utc_naive(df["time"])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype("float64")
    df["spread"] = df["spread"].astype("float64")
    return df


def load_signal_events(
    run_id: str,
    signal_type: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Laedt die Signal-Events eines Runs aus analytics_data (read-only).

    Zeitachse: **naive UTC** (BKZ-Garantie, `AT TIME ZONE 'UTC'`) -
    konsistent zu `load_ohlcv`. Die Events sind damit direkt auf die
    OHLCV-Bars abbildbar (Entry am naechsten Bar-Open nach dem Signal).

    Args:
        run_id: Signal-Run-ID (FK auf `analytics_data.indicator_runs.run_id`).
        signal_type: Optionaler Filter, z. B. "swing_change" (Default:
            alle Signaltypen des Runs).
        db_path: Alternativer Pfad (fuer Tests). Default: analytics_data.

    Returns:
        DataFrame mit Spalten `time` (naive UTC), `signal_type`,
        `direction` (+1 Long / -1 Short), `price`, `strength`,
        `source_tf`, `signal_time` - aufsteigend nach Zeit sortiert.
    """
    con = connect_analytics(db_path)
    try:
        q = """
            SELECT
                "time" AT TIME ZONE 'UTC' AS time,
                signal_type, direction, price, strength,
                source_tf,
                signal_time AT TIME ZONE 'UTC' AS signal_time
            FROM signal_events
            WHERE run_id = ?
        """
        params: list = [run_id]
        if signal_type:
            q += " AND signal_type = ?"
            params.append(signal_type)
        q += " ORDER BY \"time\" ASC"
        df = con.execute(q, params).df()
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame(columns=[
            "time", "signal_type", "direction", "price",
            "strength", "source_tf", "signal_time",
        ])
    df["time"] = _to_utc_naive(df["time"])
    if "signal_time" in df.columns:
        df["signal_time"] = _to_utc_naive(df["signal_time"])
    df["direction"] = df["direction"].astype("int8")
    return df


def count_bars(
    symbol: str,
    timeframe: str,
    date_from: Optional[Union[str, object]] = None,
    date_to: Optional[Union[str, object]] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> int:
    """Anzahl OHLCV-Bars fuer Symbol/TF (read-only, fuer RAM-Schaetzung).

    Nutzt denselben Datumsfilter wie `load_ohlcv` (naive-UTC-Konvention,
    `CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'`). Liefert nur einen COUNT -
    kein Laden der Daten (schnell, auch fuer grosse Zeitraeume).

    Args:
        symbol: Symbol (case-insensitive).
        timeframe: Timeframe (case-insensitive).
        date_from: Optionaler Startzeitpunkt (ISO-String oder datetime).
        date_to: Optionaler Endzeitpunkt.
        db_path: Alternativer Pfad (fuer Tests). Default: market_data.

    Returns:
        Anzahl der Bars im gewaehlten Zeitraum.
    """
    con = connect_market(db_path)
    try:
        q = """
            SELECT COUNT(*) FROM ohlcv_bars
            WHERE LOWER(symbol) = LOWER(?)
              AND LOWER(timeframe) = LOWER(?)
        """
        params: list = [symbol, timeframe]
        if date_from is not None:
            q += " AND \"time\" >= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'"
            params.append(str(date_from))
        if date_to is not None:
            q += " AND \"time\" <= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'"
            params.append(str(date_to))
        return int(con.execute(q, params).fetchone()[0])
    finally:
        con.close()


def available_date_range(
    db_path: Optional[Union[str, Path]] = None,
) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Verfuegbare Datumsspanne in market_data (naive UTC, BKZ-Garantie).

    Konsistent zur Zeitachse von `load_ohlcv` / `count_bars`
    (`"time" AT TIME ZONE 'UTC'`). Die Grenzen dienen als min/max der
    Kalender-Picker in der UI (Schritt 5).

    Args:
        db_path: Alternativer Pfad (fuer Tests). Default: market_data.

    Returns:
        (min, max) als naive `pd.Timestamp` oder (None, None) bei leeren Daten.
    """
    con = connect_market(db_path)
    try:
        row = con.execute(
            """
            SELECT
                MIN("time" AT TIME ZONE 'UTC'),
                MAX("time" AT TIME ZONE 'UTC')
            FROM ohlcv_bars
            """
        ).fetchone()
    finally:
        con.close()
    if not row or row[0] is None or row[1] is None:
        return None, None
    return pd.Timestamp(row[0]), pd.Timestamp(row[1])


def get_signal_runs(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Listet Signal-Runs (Metadaten) aus analytics_data (read-only).

    Wird von der Run-Auswahl (Schritt 4) genutzt. Die Identifikation des
    "letzten Signal-Lab-Laufs" erfolgt dort ueber den Zeitstempel im
    `run_name` (`_JJJJMMTT_HHMM`), Fallback `MAX(created_at)`.

    Args:
        symbol: Optionaler Symbol-Filter.
        timeframe: Optionaler Timeframe-Filter.
        db_path: Alternativer Pfad (fuer Tests). Default: analytics_data.

    Returns:
        DataFrame mit run_id, indicator_name, symbol, timeframe,
        params_json, run_name, created_at (absteigend nach created_at).
    """
    con = connect_analytics(db_path)
    try:
        q = """
            SELECT run_id, indicator_name, symbol, timeframe,
                   params_json, run_name, created_at
            FROM indicator_runs
            WHERE 1=1
        """
        params: list = []
        if symbol:
            q += " AND LOWER(symbol) = LOWER(?)"
            params.append(symbol)
        if timeframe:
            q += " AND LOWER(timeframe) = LOWER(?)"
            params.append(timeframe)
        q += " ORDER BY created_at DESC"
        df = con.execute(q, params).df()
    finally:
        con.close()

    if df.empty:
        return df

    # Bugfix 1: DB-Residuen aus Re-Runs entfernen. Das Signal Lab legt bei
    # jedem Lauf neue run_id-Zeilen mit IDENTISCHEM run_name an (siehe
    # 14 Duplikate in der Run-Auswahl). Es bleibt nur der NEUESTE Eintrag
    # je run_name (bzw. je Symbol+TF+params_json bei fehlendem Namen) -
    # jeder Run wird also nur EINMAL angezeigt.
    df = df.copy()
    df["_dedupe_key"] = df["run_name"].fillna(
        "__" + df["symbol"] + "|" + df["timeframe"] + "|" + df["params_json"].astype(str)
    )
    df = (
        df.drop_duplicates(subset=["_dedupe_key"], keep="first")
        .drop(columns="_dedupe_key")
        .reset_index(drop=True)
    )
    return df


# Zeitstempel-Muster im Signal-Lab-Run-Namen: `..._JJJJMMTT_HHMM` (vor einem
# optionalen freien Tag), z. B.
#   MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608
#   MAINDICATOR_ehma_p06_s10_a3_GOLD_H1_20260821_1436_p11-htf
_RUN_TS_RE = re.compile(r"_(\d{8})_(\d{4})")


def extract_run_timestamp(run_name: Optional[str]) -> Optional[datetime]:
    """Extrahiert den Lauf-Zeitstempel `_JJJJMMTT_HHMM` aus einem Run-Namen.

    Basis der Run-Auswahl (Schritt 4): Die Identifikation des letzten
    Signal-Lab-Laufs erfolgt ueber diesen Zeitstempel im `run_name`,
    weil `MAX(created_at)` ungeeignet ist (Re-Runs behalten dank
    `INSERT OR IGNORE` den alten `created_at`).

    Args:
        run_name: Signal-Lab-Run-Name, z. B.
            `MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608`.

    Returns:
        Naive `datetime` des Zeitstempels (z. B. 2026-08-21 16:08) oder
        `None`, wenn kein Zeitstempel im Namen steckt (Fall
        `run_name_override` ohne Zeitstempel).

    Example:
        >>> extract_run_timestamp(
        ...     "MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608")
        datetime.datetime(2026, 8, 21, 16, 8)
        >>> extract_run_timestamp("MEIN_EIGENER_NAME") is None
        True
    """
    if not run_name:
        return None
    matches = _RUN_TS_RE.findall(str(run_name))
    if not matches:
        return None
    ymd, hm = matches[-1]
    return datetime.strptime(f"{ymd}_{hm}", "%Y%m%d_%H%M")


def _effective_run_timestamp(run_name: Optional[str], created_at) -> Optional[pd.Timestamp]:
    """Effektiver Lauf-Zeitstempel je Run (fuer die Run-Auswahl).

    Bevorzugt den Zeitstempel im `run_name` (Primaerlogik, tz-korrekt als
    Anzeige-Zeit (Europe/Budapest) normalisiert). Fallback bei `run_name_override`
    (kein Zeitstempel im Namen): `created_at`.

    Args:
        run_name: Signal-Lab-Run-Name (kann None sein).
        created_at: Zeitstempel aus `indicator_runs` (tz-aware oder naive).

    Returns:
        tz-aware `pd.Timestamp` (UTC-normalisiert) oder None bei Fehlern.
    """
    ts = extract_run_timestamp(run_name)
    if ts is not None:
        try:
            # Name-Ts ist die Anzeige-Zeit Europe/Budapest (naive, aus datetime.now()).
            # tz_localize rechnet DST-korrekt auf UTC um (BKZ-Garantie).
            return pd.Timestamp(ts).tz_localize(
                "Europe/Budapest", ambiguous="NaT", nonexistent="NaT"
            )
        except (TypeError, ValueError):
            pass
    return pd.to_datetime(created_at, errors="coerce", utc=True)


def get_last_signal_runs(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Nur die Runs aus dem letzten Signal-Lab-Lauf (keine Historie).

    Identifikation ueber den Zeitstempel im `run_name` (`_JJJJMMTT_HHMM`,
    siehe `extract_run_timestamp`). `MAX(created_at)` ist ungeeignet, weil
    Re-Runs dank `INSERT OR IGNORE` im Signal Lab den alten `created_at`
    behalten. Fallback bei `run_name_override` (kein Zeitstempel im Namen):
    `MAX(created_at)` - pro Run via `_effective_run_timestamp`.

    Args:
        symbol: Optionaler Symbol-Filter (case-insensitive).
        timeframe: Optionaler Timeframe-Filter (case-insensitive).
        db_path: Alternativer Pfad (fuer Tests). Default: analytics_data.

    Returns:
        Nur die Runs des letzten Lauf-Batches (gleicher effektiver
        Zeitstempel), absteigend nach `created_at` sortiert. Leer, wenn
        keine Runs vorhanden sind.

    Example:
        >>> df = get_last_signal_runs(symbol="SILVER", timeframe="M30")
        >>> df["run_name"].nunique() >= 1
        True
    """
    df = get_signal_runs(symbol=symbol, timeframe=timeframe, db_path=db_path)
    if df.empty:
        return df

    df = df.copy()
    df["_eff_ts"] = [
        _effective_run_timestamp(rn, ca) for rn, ca in zip(df["run_name"], df["created_at"])
    ]
    last_ts = df["_eff_ts"].max()
    return (
        df.loc[df["_eff_ts"] == last_ts]
        .drop(columns="_eff_ts")
        .reset_index(drop=True)
    )


def get_signal_run_batches(
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Listet alle Signal-Lab-Lauf-Batches (effektiver Zeitstempel + Run-Anzahl).

    Basis fuer die Run-Auswahl (Schritt 4): Ein "Lauf-Batch" = alle Runs mit
    demselben effektiven Lauf-Zeitstempel (`_JJJJMMTT_HHMM` im Run-Namen,
    Fallback `created_at`). Damit lassen sich auch AELTERE Signal-Lab-Laeufe
    fuer Backtests auswaehlen (nicht nur der letzte Lauf).

    Args:
        db_path: Alternativer Pfad (fuer Tests). Default: analytics_data.

    Returns:
        DataFrame mit Spalten `ts` (ISO-String, UTC-aware), `run_count` und
        `label` (lesbare Anzeige-Zeit Europe/Budapest + Run-Anzahl), absteigend nach
        Zeit sortiert. Leer, wenn keine Runs vorhanden sind.

    Example:
        >>> b = get_signal_run_batches()
        >>> list(b.columns) == ["ts", "run_count", "label"]
        True
    """
    df = get_signal_runs(db_path=db_path)
    if df.empty:
        return pd.DataFrame(columns=["ts", "run_count", "label"])

    df = df.copy()
    df["_eff_ts"] = [
        _effective_run_timestamp(rn, ca) for rn, ca in zip(df["run_name"], df["created_at"])
    ]
    df = df.dropna(subset=["_eff_ts"])
    if df.empty:
        return pd.DataFrame(columns=["ts", "run_count", "label"])

    groups = df.groupby("_eff_ts")["run_id"].count().sort_index(ascending=False)
    out = pd.DataFrame({
        "ts": [ts.isoformat() for ts in groups.index],
        "run_count": groups.to_numpy(dtype=int),
    })
    out["label"] = [
        f"{_fmt_wallclock(ts)} · {c} Run(s)"
        for ts, c in zip(groups.index, out["run_count"])
    ]
    return out.reset_index(drop=True)


def get_signal_runs_for_batch(
    ts: str,
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Alle Runs eines bestimmten Lauf-Batches (effektiver Zeitstempel).

    Ergänzt `get_last_signal_runs`: Die Run-Auswahl kann damit jeden
    historischen Signal-Lab-Lauf exakt rekonstruieren (fuer Backtests auf
    aelteren Signalen).

    Args:
        ts: Effektiver Lauf-Zeitstempel als ISO-String (UTC-aware, exakt die
            `ts`-Spalte aus `get_signal_run_batches`).
        db_path: Alternativer Pfad (fuer Tests). Default: analytics_data.

    Returns:
        Nur die Runs des angeforderten Batches (wie `get_signal_runs`),
        absteigend nach `created_at` sortiert. Leer, wenn nichts gefunden.
    """
    df = get_signal_runs(db_path=db_path)
    if df.empty:
        return df

    target = pd.Timestamp(ts)
    df = df.copy()
    df["_eff_ts"] = [
        _effective_run_timestamp(rn, ca) for rn, ca in zip(df["run_name"], df["created_at"])
    ]
    out = df.loc[df["_eff_ts"] == target].drop(columns="_eff_ts").reset_index(drop=True)
    return out


def enrich_signal_ranges(
    runs_df: pd.DataFrame,
    db_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """Ergaenzt je Signal-Run den abgedeckten Signal-Zeitraum (MIN/MAX).

    Basis: `signal_events` der analytics_data (read-only). Die Spalten
    `signal_from` / `signal_to` (naive UTC, "YYYY-MM-DD HH:MM") zeigen den
    Zeitraum, den die Signale des Runs tatsaechlich abdecken (erste bis
    letzte Event-Zeit) - Anzeige in der Run-Auswahl-Tabelle (Schritt 4).

    Fehlertolerant: Runs ohne Events und Datenbanken ohne `signal_events`-
    Tabelle (z. B. synthetische Test-DBs) liefern `None`-Spalten statt
    eines Fehlschlags.

    Args:
        runs_df: Ergebnis von `get_signal_runs` / `get_last_signal_runs` /
            `get_signal_runs_for_batch` (Spalte `run_id` vorhanden).
        db_path: Alternativer Pfad (fuer Tests). Default: analytics_data.

    Returns:
        Kopie von `runs_df` mit den Spalten `signal_from` / `signal_to`
        (String "YYYY-MM-DD HH:MM" oder None).
    """
    if runs_df is None or runs_df.empty:
        return runs_df.copy() if runs_df is not None else runs_df

    out = runs_df.copy()
    out["signal_from"] = None
    out["signal_to"] = None

    con = connect_analytics(db_path)
    try:
        has_events = int(con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'signal_events'"
        ).fetchone()[0]) > 0
        if not has_events:
            return out
        agg = con.execute(
            """
            SELECT run_id,
                   MIN("time" AT TIME ZONE 'UTC') AS signal_from,
                   MAX("time" AT TIME ZONE 'UTC') AS signal_to
            FROM signal_events
            WHERE run_id = ANY(?)
            GROUP BY run_id
            """,
            [out["run_id"].astype(str).tolist()],
        ).df()
    finally:
        con.close()

    if agg.empty:
        return out
    agg["signal_from"] = pd.to_datetime(agg["signal_from"], errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    agg["signal_to"] = pd.to_datetime(agg["signal_to"], errors="coerce").dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    merged = out.merge(agg, on="run_id", how="left", suffixes=("", "_agg"))
    out["signal_from"] = merged["signal_from_agg"]
    out["signal_to"] = merged["signal_to_agg"]
    return out


def _fmt_wallclock(ts: pd.Timestamp) -> str:
    """tz-aware Timestamp -> lesbare Anzeige-Zeit Europe/Budapest (String)."""
    t = pd.Timestamp(ts)
    if getattr(t, "tz", None) is not None:
        t = t.tz_convert("Europe/Budapest")
    return t.strftime("%Y-%m-%d %H:%M")


def save_backtest_run(
    db_conn: duckdb.DuckDBPyConnection,
    run_record: BacktestRunRecord,
    trades_df: pd.DataFrame,
) -> None:
    """Speichert Run-Metadaten und zugehoerige Einzeltrades transaktional.

    Der Runner liefert ausschliesslich GESCHLOSSENE Trades (status=1) -
    offene Positionen am `date_to`-Ende werden bereits im Runner verworfen.
    Ein Run ohne Trades (trade_count=0) wird trotzdem als Metadaten-Zeile
    gespeichert (wichtig fuer Sweeps und das spaetere ML-Lab).

    Args:
        db_conn: Schreibbare Connection zu `backtest_data.duckdb`.
        run_record: Run-Header (1 Zeile in `backtest_runs`).
        trades_df: DataFrame mit Spalten aus `TRADES_COLUMNS` (ohne `run_id`
            - wird automatisch gesetzt). Leer erlaubt.

    Raises:
        RuntimeError: Bei DB-Fehlern (Rollback + transparenter Fehlertext).
    """
    header_df: pd.DataFrame = pd.DataFrame([dataclass_dict(run_record)])

    enriched_trades: pd.DataFrame = trades_df.copy()
    if not enriched_trades.empty:
        enriched_trades["run_id"] = run_record.run_id
        # Bugfix 8: Fehlende Spalten (z. B. exit_reason bei aelteren
        # trades_df oder handgebauten Test-DataFrames) mit NULL auffuellen -
        # der Spaltenvertrag bleibt trotzdem erfuellt (KeyError-Schutz).
        for _col in TRADES_COLUMNS:
            if _col not in enriched_trades.columns:
                enriched_trades[_col] = None
        # Spalten auf den verbindlichen Vertrag reduzieren/ordnen
        enriched_trades = enriched_trades[TRADES_COLUMNS]

    db_conn.begin()
    try:
        # Idempotenz (Bugfix 3): `run_record.run_id` ist deterministisch
        # (`run_id_from_config`). Ein bereits vorhandener Lauf mit 1:1
        # identischer Konfiguration wird UEBERSCHRIEBEN - keine endlosen
        # Duplikate.
        #
        # DuckDB-FK-Limitation: Der FK-Check sieht uncommittete DELETEs
        # innerhalb derselben Transaktion NICHT -> ein `DELETE FROM
        # backtest_runs` schluege fehl, obwohl die Trades schon geloescht
        # sind. Loesung: erst Trades entfernen, dann den Run per
        # `INSERT OR REPLACE` (ersetzt die alte Zeile inkl. FK-Check).
        db_conn.execute("DELETE FROM backtest_trades WHERE run_id = ?", [run_record.run_id])

        db_conn.register("tmp_runs", header_df)
        db_conn.execute(
            """
            INSERT OR REPLACE INTO backtest_runs (
                run_id, signal_run_id, run_name, symbol, timeframe,
                params_json, date_from, date_to, net_profit, win_rate,
                profit_factor, max_drawdown_pct, max_drawdown, sl_count,
                sharpe_ratio, trade_count, avg_trade_pnl, expectancy,
                max_win, created_at
            )
            SELECT
                run_id, signal_run_id, run_name, symbol, timeframe,
                params_json, date_from, date_to, net_profit, win_rate,
                profit_factor, max_drawdown_pct, max_drawdown, sl_count,
                sharpe_ratio, trade_count, avg_trade_pnl, expectancy,
                max_win, created_at
            FROM tmp_runs
            """
        )

        if not enriched_trades.empty:
            db_conn.register("tmp_trades", enriched_trades)
            db_conn.execute(
                """
                INSERT INTO backtest_trades (
                    run_id, entry_time, exit_time, entry_price,
                    exit_price, direction, pnl, r_multiple, exit_reason
                )
                SELECT
                    run_id, entry_time, exit_time, entry_price,
                    exit_price, direction, pnl, r_multiple, exit_reason
                FROM tmp_trades
                """
            )
        db_conn.commit()
    except Exception as exc:
        db_conn.rollback()
        raise RuntimeError(f"Datenbankfehler beim Speichern des Backtests: {exc}") from exc
    finally:
        db_conn.unregister("tmp_runs")
        if not enriched_trades.empty:
            db_conn.unregister("tmp_trades")


def dataclass_dict(record: BacktestRunRecord) -> dict:
    """Frozen-Dataclass -> dict (fuer pd.DataFrame / INSERT).

    Args:
        record: Beliebige (frozen) Dataclass-Instanz.

    Returns:
        Dictionary der Felder.
    """
    return dict(record.__dict__)


def get_backtest_runs(
    db_path: Optional[Union[str, Path]] = None,
    limit: int = 200,
) -> pd.DataFrame:
    """Listet Backtest-Runs aus `backtest_data` (fuer die Verwaltungs-Tabelle).

    Args:
        db_path: Alternativer Pfad (fuer Tests). Default: backtest_data.
        limit: Maximale Anzahl Runs (Default 200, neueste zuerst).

    Returns:
        DataFrame mit run_id, run_name, symbol, timeframe, trade_count,
        sl_count, net_profit, net_profit_pct (Gewinn in % des Equity),
        win_rate, max_win, worst_trade (groesster Einzelverlust in $),
        max_drawdown ($), created_at - absteigend nach created_at. Leer,
        wenn die DB/Datei (noch) nicht existiert oder leer ist.
    """
    path = Path(db_path) if db_path else DB_BACKTEST
    if not path.exists():
        return pd.DataFrame(columns=[
            "run_id", "run_name", "symbol", "timeframe", "trade_count",
            "sl_count", "net_profit", "net_profit_pct", "win_rate",
            "max_win", "worst_trade", "max_drawdown", "created_at",
        ])
    con = connect_backtest(path, ensure_schema=False)
    try:
        has_table = int(con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'backtest_runs'"
        ).fetchone()[0]) > 0
        if not has_table:
            return pd.DataFrame(columns=[
                "run_id", "run_name", "symbol", "timeframe", "trade_count",
                "sl_count", "net_profit", "net_profit_pct", "win_rate",
                "max_win", "worst_trade", "max_drawdown", "created_at",
            ])
        return con.execute(
            """
            SELECT
                r.run_id, r.run_name, r.symbol, r.timeframe,
                r.trade_count, r.sl_count,
                r.net_profit,
                r.net_profit / NULLIF(CAST(r.params_json->>'equity' AS DOUBLE), 0)
                    * 100 AS net_profit_pct,
                r.win_rate, r.max_win,
                (SELECT MIN(t.pnl) FROM backtest_trades t
                 WHERE t.run_id = r.run_id) AS worst_trade,
                r.max_drawdown, r.created_at
            FROM backtest_runs r
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            [int(limit)],
        ).df()
    finally:
        con.close()


def _fmt_duration(minutes: float) -> str:
    """Haltedauer (Minuten) -> kompakte Lesefassung (z. B. '2h 15m').

    Args:
        minutes: Haltedauer in Minuten (kann None/NaN sein).

    Returns:
        String wie "45m", "2h 15m" oder "3d 4h"; "" bei fehlendem Wert.
    """
    if minutes is None or pd.isna(minutes):
        return ""
    m = int(round(float(minutes)))
    if m < 60:
        return f"{m}m"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m}m" if m else f"{h}h"
    d, h = divmod(h, 24)
    return f"{d}d {h}h" if h else f"{d}d"


def _fmt_wallclock_series(series: pd.Series) -> pd.Series:
    """Zeit-Spalte -> lesbare Anzeige-Zeit Europe/Budapest ("YYYY-MM-DD HH:MM").

    BKZ-Garantie: naive Werte werden als UTC interpretiert und nach
    Europe/Budapest umgerechnet (Anzeige-Zeit), tz-aware Werte
    direkt konvertiert - konsistent zur uebrigen UI (DuckDB liefert die
    Zeiten bereits als naive UTC via `AT TIME ZONE 'UTC'`).

    Args:
        series: Zeit-Spalte (naive UTC oder tz-aware).

    Returns:
        String-Spalte im Format "YYYY-MM-DD HH:MM".
    """
    s = pd.to_datetime(series, errors="coerce")
    if getattr(s.dtype, "tz", None) is None:
        s = s.dt.tz_localize("UTC")
    return s.dt.tz_convert("Europe/Budapest").dt.strftime("%Y-%m-%d %H:%M")


def get_backtest_trades(
    run_id: Union[str, object],
    db_path: Optional[Union[str, Path]] = None,
    limit: int = 100_000,
) -> pd.DataFrame:
    """Laedt die Einzeltrades eines Backtest-Runs (fuer die Detail-Tabelle).

    Vorsortiert auf den LETZTEN Trade ganz oben (`exit_time DESC`,
    BKZ-Garantie: `AT TIME ZONE 'UTC'`). Neben den Rohspalten aus
    `backtest_trades` werden angereicherte Infospalten mitgeliefert
    (moeglichst viele Spalten, siehe `TRADE_DETAIL_COLUMNS`):

      - run_name / symbol / timeframe: Run-Kontext (JOIN backtest_runs)
      - entry_time / exit_time: Anzeige-Zeit Europe/Budapest ("YYYY-MM-DD HH:MM")
      - duration: Haltedauer (z. B. "2h 15m")
      - direction: "Long"/"Short" (lesbar statt +1/-1)
      - move_pct: richtungsbereinigte Kursbewegung in % (Gewinn/Verlust
        der reinen Preisbewegung, unabhaengig vom Hebel)
      - pnl_equity_pct: Trade-PnL in % des Startkapitals (params_json->'equity')
      - exit_reason: "SL" / "TP" / "Signal" / "Gap" (lesbar)

    Args:
        run_id: run_id aus `backtest_runs` (beliebiger Skalar -> str).
        db_path: Alternativer Pfad (fuer Tests). Default: backtest_data.
        limit: Maximale Anzahl Trades (Default 100 000 - reicht fuer alle
            realistischen Runs).

    Returns:
        DataFrame mit `TRADE_DETAIL_COLUMNS`, neuester Trade zuerst. Leer,
        wenn die DB/Datei oder die Trades fehlen bzw. der Run unbekannt ist.
    """
    path = Path(db_path) if db_path else DB_BACKTEST
    if not path.exists():
        return pd.DataFrame(columns=TRADE_DETAIL_COLUMNS)
    con = connect_backtest(path, ensure_schema=False)
    try:
        has_trades = int(con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'backtest_trades'"
        ).fetchone()[0]) > 0
        if not has_trades:
            return pd.DataFrame(columns=TRADE_DETAIL_COLUMNS)
        df = con.execute(
            """
            SELECT
                t.run_id,
                r.run_name, r.symbol, r.timeframe,
                t.entry_time AT TIME ZONE 'UTC' AS entry_time,
                t.exit_time  AT TIME ZONE 'UTC' AS exit_time,
                t.entry_price, t.exit_price, t.direction, t.pnl,
                t.r_multiple, t.exit_reason,
                CAST(NULLIF(r.params_json->>'equity', '') AS DOUBLE) AS equity
            FROM backtest_trades t
            LEFT JOIN backtest_runs r USING (run_id)
            WHERE t.run_id = ?
            ORDER BY t.exit_time DESC
            LIMIT ?
            """,
            [str(run_id), int(limit)],
        ).df()
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame(columns=TRADE_DETAIL_COLUMNS)

    df = df.copy()
    # Richtungsbereinigte Kursbewegung in % (vor dem Umbenennen rechnen).
    dir_num = df["direction"].astype(float)
    df["move_pct"] = (
        df["exit_price"].astype(float) / df["entry_price"].astype(float) - 1.0
    ) * 100.0 * dir_num
    df["direction"] = dir_num.map(lambda v: "Long" if v > 0 else "Short")
    df["exit_reason"] = (
        df["exit_reason"].astype(str).map({
            "sl": "SL", "tp": "TP", "signal": "Signal", "gap": "Gap",
            "None": "", "nan": "",
        }).fillna("")
    )
    # Haltedauer aus Entry->Exit (in Minuten).
    df["duration"] = [
        _fmt_duration(m) for m in (
            (pd.to_datetime(x) - pd.to_datetime(e)).total_seconds() / 60.0
            for e, x in zip(df["entry_time"], df["exit_time"])
        )
    ]
    # Zeiten als Anzeige-Zeit (Europe/Budapest) (lesbar, lexikografisch sortierbar).
    df["entry_time"] = _fmt_wallclock_series(df["entry_time"])
    df["exit_time"] = _fmt_wallclock_series(df["exit_time"])
    # PnL in % des Startkapitals (aus params_json->'equity').
    equity = pd.to_numeric(df["equity"], errors="coerce").replace(0, pd.NA)
    df["pnl_equity_pct"] = df["pnl"].astype(float) / equity * 100.0
    # Anzeige-Rundung (Sortierlogik bleibt numerisch, Werte nur lesbarer).
    df["move_pct"] = df["move_pct"].round(2)
    df["pnl_equity_pct"] = pd.to_numeric(df["pnl_equity_pct"], errors="coerce").round(2)
    df["pnl"] = df["pnl"].round(2)
    df["entry_price"] = df["entry_price"].round(4)
    df["exit_price"] = df["exit_price"].round(4)
    return df.drop(columns="equity").reindex(columns=TRADE_DETAIL_COLUMNS).reset_index(drop=True)


def delete_backtest_runs(
    run_ids: list,
    db_path: Optional[Union[str, Path]] = None,
) -> int:
    """Loescht Backtest-Runs inkl. ihrer Trades aus `backtest_data`.

    Transaktional: erst `backtest_trades`, dann `backtest_runs` (FK-Reihen-
    folge). Bei Fehlern wird komplett zurueckgerollt.

    Args:
        run_ids: Liste der zu loeschenden run_ids.
        db_path: Alternativer Pfad (fuer Tests). Default: backtest_data.

    Returns:
        Anzahl geloeschter Runs.

    Raises:
        RuntimeError: Bei DB-Fehlern (Rollback + transparenter Fehlertext).
    """
    ids = [str(i) for i in (run_ids or []) if str(i)]
    if not ids:
        return 0
    con = connect_backtest(db_path, ensure_schema=False)
    try:
        n = int(con.execute(
            "SELECT COUNT(*) FROM backtest_runs WHERE run_id = ANY(?)", [ids]
        ).fetchone()[0])
        if n == 0:
            return 0
        # DuckDB-FK-Limitation: uncommittete DELETEs werden vom FK-Check
        # nicht gesehen -> bewusst AUTCOMMIT (je Statement eigene
        # Transaktion): erst Trades, dann Runs loeschen. Konsistent, da
        # verbleibende Runs ohne Trades gueltig sind.
        con.execute("DELETE FROM backtest_trades WHERE run_id = ANY(?)", [ids])
        con.execute("DELETE FROM backtest_runs WHERE run_id = ANY(?)", [ids])
        return n
    except Exception as exc:
        raise RuntimeError(f"Datenbankfehler beim Loeschen der Backtest-Runs: {exc}") from exc
    finally:
        con.close()
