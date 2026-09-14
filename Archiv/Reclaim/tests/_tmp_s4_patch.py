# -*- coding: utf-8 -*-
"""S4 -- Byte-praeziser Umbau der Peripherie auf den Zeitbasis-Kanon.

Weg A (Anwender-Freigabe 2026-09-11): radikaler Schnitt.
  * SQL projiziert BKZ: ``"time" AT TIME ZONE 'UTC' AS time``.
  * ``tz_offset_hours`` wird ERSATZLOS aus allen Signaturen entfernt
    (kein Deprecated-Workaround).
  * ``.timestamp()`` auf tz-naive Werte -> naive Epoch-Division.
  * ``backtest_lab/ui.py`` delegiert die Anzeige-Dublette.

Verfahren: Jede Ersetzung ist eindeutig (Fail-Loud ueber Soll-Trefferzahl).
Zeilenenden werden pro Treffer automatisch erkannt (CRLF/LF, auch gemischt).
Kein Schreibvorgang bei fehlgeschlagener Vorbedingung.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

# (Datei, [(old, new, erwartete_Treffer), ...])
EDITS: list[tuple[str, list[tuple[str, str, int]]]] = []

# =========================================================== algos/chart_engine.py
EDITS.append(("algos/chart_engine.py", [
    (
        """    limit: int,
    tz_offset_hours: int = 0,
    db_path: Path = DEFAULT_DB_PATH,""",
        """    limit: int,
    db_path: Path = DEFAULT_DB_PATH,""",
        1,
    ),
    (
        """    \"\"\"Lädt historische OHLCV-Kerzen aus der DuckDB-Datenbank.\"\"\"
    fetch_limit = int(limit) + int(end_offset_bars) + int(warmup_bars)
    query = f\"\"\"
        SELECT "time", open, high, low, close, tick_volume AS volume
        FROM (""",
        """    \"\"\"Lädt historische OHLCV-Kerzen aus der DuckDB-Datenbank.

    Zeitbasis (docs/ZEITBASIS_KANON.md): Die Spalte ``time`` wird als
    Broker-Kerzen-Zeit (BKZ = ``time AT TIME ZONE 'UTC'``) projiziert und
    tz-naiv zurueckgegeben -- die einzige Rechenbasis. Ein Offset-Parameter
    existiert bewusst nicht mehr.
    \"\"\"
    fetch_limit = int(limit) + int(end_offset_bars) + int(warmup_bars)
    query = f\"\"\"
        SELECT "time" AT TIME ZONE 'UTC' AS time,
               open, high, low, close, tick_volume AS volume
        FROM (""",
        1,
    ),
    (
        """    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)

    df["time"] = df["time"].astype("datetime64[ns]")""",
        """    # BKZ-Kanon: die SQL liefert bereits naive Broker-Kerzen-Zeit
    # (`time AT TIME ZONE 'UTC'`) -- kein Offset, keine Projektion mehr.
    df["time"] = df["time"].astype("datetime64[ns]")""",
        1,
    ),
]))

# =========================================================== algos/chart_plugins.py
EDITS.append(("algos/chart_plugins.py", [
    (
        """from algos.signal_events import SignalEvent


def build_candles_payload(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], int, float]:""",
        """from algos.signal_events import SignalEvent

# Epoch-Nullpunkt fuer die naive BKZ->Sekunden-Rechnung (kein OS-TZ-Lookup).
_EPOCH = pd.Timestamp("1970-01-01")


def _epoch_sec(ts: Any) -> int:
    \"\"\"BKZ-Zeitstempel -> Unix-Sekunden (rein naiv, ohne OS-Zeitzone).

    Kanon (docs/ZEITBASIS_KANON.md): Rechenbasis ist die Broker-Kerzen-Zeit
    (BKZ). Die Epoche entsteht ausschliesslich durch Subtraktion des
    Epoch-Nullpunkts; ``Timestamp.timestamp()`` wuerde den tz-naiven Wert je
    nach Laufzeitumgebung aufloesen. Ein tz-aware Wert (falls je uebergeben)
    wird zuvor auf UTC normiert und tz-naiv gestellt.
    \"\"\"
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return int((t - _EPOCH) // pd.Timedelta(seconds=1))


def build_candles_payload(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], int, float]:""",
        1,
    ),
    (
        "        t_sec = int(times.iloc[idx].timestamp())",
        "        t_sec = _epoch_sec(times.iloc[idx])",
        1,
    ),
    (
        '        t_sec = int(pd.Timestamp(hc["time"]).timestamp())',
        '        t_sec = _epoch_sec(hc["time"])',
        1,
    ),
    (
        '        t_sec = int(pd.Timestamp(row["time"]).timestamp())',
        '        t_sec = _epoch_sec(row["time"])',
        1,
    ),
    (
        """        if not meta_tf and e.signal_type == "swing_change":
            style["color"] = bull_color if e.direction >= 0 else bear_color
        t_sec = int(pd.Timestamp(e.time).timestamp())""",
        """        if not meta_tf and e.signal_type == "swing_change":
            style["color"] = bull_color if e.direction >= 0 else bear_color
        t_sec = _epoch_sec(e.time)""",
        1,
    ),
    (
        """        if e.signal_type in ["circle_yellow", "circle_fuchsia"]:
            color = time_circle_color if e.signal_type == "circle_yellow" else circle_color
            t_sec = int(pd.Timestamp(e.time).timestamp())""",
        """        if e.signal_type in ["circle_yellow", "circle_fuchsia"]:
            color = time_circle_color if e.signal_type == "circle_yellow" else circle_color
            t_sec = _epoch_sec(e.time)""",
        1,
    ),
]))

# =========================================================== signal_lab/quick_look.py
EDITS.append(("signal_lab/quick_look.py", [
    (
        """    t_from: pd.Timestamp,
    t_to: pd.Timestamp,
    tz_offset_hours: int = 2,
) -> pd.DataFrame:
    \"\"\"Lädt OHLCV für Symbol/TF im Zeitbereich [t_from, t_to] (naive Brokerzeit).\"\"\"""",
        """    t_from: pd.Timestamp,
    t_to: pd.Timestamp,
) -> pd.DataFrame:
    \"\"\"Lädt OHLCV für Symbol/TF im Zeitbereich [t_from, t_to] (BKZ, tz-naiv).\"\"\"""",
        1,
    ),
    (
        """            SELECT "time", open, high, low, close, tick_volume AS volume
            FROM ohlcv_bars
            WHERE LOWER(symbol)=LOWER('{symbol}')
              AND LOWER(timeframe)=LOWER('{timeframe}')
              AND "time" IS NOT NULL
              AND "time" >= CAST(? AS TIMESTAMP)
              AND "time" <= CAST(? AS TIMESTAMP)
            ORDER BY "time" ASC""",
        """            SELECT "time" AT TIME ZONE 'UTC' AS time,
                   open, high, low, close, tick_volume AS volume
            FROM ohlcv_bars
            WHERE LOWER(symbol)=LOWER('{symbol}')
              AND LOWER(timeframe)=LOWER('{timeframe}')
              AND "time" IS NOT NULL
              AND "time" >= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'
              AND "time" <= CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'
            ORDER BY "time" ASC""",
        1,
    ),
    (
        """        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)
    df["time"] = df["time"].astype("datetime64[ns]")""",
        """        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    # BKZ-Kanon: die SQL liefert bereits naive Broker-Kerzen-Zeit.
    df["time"] = df["time"].astype("datetime64[ns]")""",
        1,
    ),
    (
        """    end_offset_bars: int = 0,
    tz_offset_hours: int = 2,
    indicator_name: str = "JumpIndicator",
    indicator_params: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, List[IndicatorResult]]:""",
        """    end_offset_bars: int = 0,
    indicator_name: str = "JumpIndicator",
    indicator_params: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, List[IndicatorResult]]:""",
        1,
    ),
    (
        """        limit=window_bars,
        tz_offset_hours=tz_offset_hours,
        end_offset_bars=end_offset_bars,""",
        """        limit=window_bars,
        end_offset_bars=end_offset_bars,""",
        1,
    ),
    (
        "            hdf = _load_tf_range(db_market, symbol, htf, t_first, t_last, tz_offset_hours)",
        "            hdf = _load_tf_range(db_market, symbol, htf, t_first, t_last)",
        1,
    ),
    (
        """    end_offset_bars: int = 0,
    tz_offset_hours: int = 2,
    indicator_name: str = "JumpIndicator",
    indicator_params: Optional[Dict[str, Any]] = None,
    **chart_kwargs: Any,""",
        """    end_offset_bars: int = 0,
    indicator_name: str = "JumpIndicator",
    indicator_params: Optional[Dict[str, Any]] = None,
    **chart_kwargs: Any,""",
        1,
    ),
    (
        """        end_offset_bars=end_offset_bars,
        tz_offset_hours=tz_offset_hours,
        indicator_name=indicator_name,""",
        """        end_offset_bars=end_offset_bars,
        indicator_name=indicator_name,""",
        1,
    ),
]))

# =========================================================== signal_lab/run_definition.py
EDITS.append(("signal_lab/run_definition.py", [
    (
        """def available_date_range(db_path, tz_offset_hours: int = 2):
    \"\"\"Verfügbare Datumsspanne in market_data (naive Brokerzeit).

    Liefert (min_date, max_date) als pandas.Timestamp (Datum) oder (None, None),
    wenn keine Daten vorhanden sind. Konvention wie im Chart Inspector:
    Brokerzeit wird als naive Zeit geführt (DB-TZ entfernt, Offset abgezogen).
    \"\"\"""",
        """def available_date_range(db_path):
    \"\"\"Verfügbare Datumsspanne in market_data (BKZ, tz-naiv).

    Liefert (min_date, max_date) als pandas.Timestamp (Datum) oder (None, None),
    wenn keine Daten vorhanden sind. Rechenbasis ist die Broker-Kerzen-Zeit
    (BKZ = ``time AT TIME ZONE 'UTC'``, docs/ZEITBASIS_KANON.md); ein
    Offset-Parameter existiert bewusst nicht mehr.
    \"\"\"""",
        1,
    ),
    (
        """            'SELECT MIN("time"), MAX("time") FROM ohlcv_bars WHERE "time" IS NOT NULL'
        ).fetchone()
    finally:
        con.close()
    if not row or row[0] is None or row[1] is None:
        return None, None
    import pandas as pd
    # DuckDB liefert je nach Treiber naive oder tz-aware datetimes – beides normalisieren
    t_min = row[0] if not hasattr(row[0], "tz_localize") else row[0].tz_localize(None)
    t_max = row[1] if not hasattr(row[1], "tz_localize") else row[1].tz_localize(None)
    t_min = pd.Timestamp(t_min)
    t_max = pd.Timestamp(t_max)
    if t_min.tzinfo is not None:
        t_min = t_min.tz_localize(None)
        t_max = t_max.tz_localize(None)
    if tz_offset_hours != 0:
        t_min = t_min - pd.Timedelta(hours=tz_offset_hours)
        t_max = t_max - pd.Timedelta(hours=tz_offset_hours)
    return t_min, t_max""",
        """            'SELECT MIN("time" AT TIME ZONE \\'UTC\\'), '
            'MAX("time" AT TIME ZONE \\'UTC\\') '
            'FROM ohlcv_bars WHERE "time" IS NOT NULL'
        ).fetchone()
    finally:
        con.close()
    if not row or row[0] is None or row[1] is None:
        return None, None
    import pandas as pd
    # BKZ-Kanon: die SQL projiziert bereits naive Broker-Kerzen-Zeit.
    return pd.Timestamp(row[0]), pd.Timestamp(row[1])""",
        1,
    ),
]))

# =========================================================== signal_lab/sweep_runner.py
EDITS.append(("signal_lab/sweep_runner.py", [
    (
        """    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tz_offset_hours: int = 2,
    limit: int = 2_000_000,
) -> pd.DataFrame:
    \"\"\"Lädt OHLCV für Symbol/TF, optional begrenzt auf einen Datumsbereich.

    Konvention: naive Brokerzeit (wie im Chart Inspector).
    \"\"\"""",
        """    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 2_000_000,
) -> pd.DataFrame:
    \"\"\"Lädt OHLCV für Symbol/TF, optional begrenzt auf einen Datumsbereich.

    Zeitbasis: Broker-Kerzen-Zeit (BKZ = ``time AT TIME ZONE 'UTC'``, tz-naiv,
    docs/ZEITBASIS_KANON.md). Ein Offset-Parameter existiert bewusst nicht mehr.
    \"\"\"""",
        1,
    ),
    (
        """            SELECT "time", open, high, low, close, tick_volume AS volume, spread
            FROM ohlcv_bars""",
        """            SELECT "time" AT TIME ZONE 'UTC' AS time,
                   open, high, low, close, tick_volume AS volume, spread
            FROM ohlcv_bars""",
        1,
    ),
    (
        """            q += ' AND "time" >= CAST(? AS TIMESTAMP)'""",
        """            q += ' AND "time" >= CAST(? AS TIMESTAMP) AT TIME ZONE \\'UTC\\''""",
        1,
    ),
    (
        """            q += ' AND "time" <= CAST(? AS TIMESTAMP)'""",
        """            q += ' AND "time" <= CAST(? AS TIMESTAMP) AT TIME ZONE \\'UTC\\''""",
        1,
    ),
    (
        """    df["time"] = df["time"].dt.tz_localize(None)
    if tz_offset_hours != 0:
        df["time"] = df["time"] - pd.Timedelta(hours=tz_offset_hours)
    df["time"] = df["time"].astype("datetime64[ns]")""",
        """    # BKZ-Kanon: die SQL liefert bereits naive Broker-Kerzen-Zeit.
    df["time"] = df["time"].astype("datetime64[ns]")""",
        1,
    ),
    (
        """    warmup_bars: int = 200,
    tz_offset_hours: int = 2,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,""",
        """    warmup_bars: int = 200,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,""",
        1,
    ),
    (
        """            df: pd.DataFrame = load_market_data(
                symbol,
                tf,
                db_market,
                definition.date_from,
                definition.date_to,
                tz_offset_hours,
            )""",
        """            df: pd.DataFrame = load_market_data(
                symbol,
                tf,
                db_market,
                definition.date_from,
                definition.date_to,
            )""",
        2,
    ),
    (
        """                small_df = load_market_data(
                    symbol,
                    definition.htf_small_tf,
                    db_market,
                    definition.date_from,
                    definition.date_to,
                    tz_offset_hours,
                )""",
        """                small_df = load_market_data(
                    symbol,
                    definition.htf_small_tf,
                    db_market,
                    definition.date_from,
                    definition.date_to,
                )""",
        2,
    ),
    (
        """    warmup_bars: int = 200,
    tz_offset_hours: int = 2,
    n_workers: Optional[int] = None,""",
        """    warmup_bars: int = 200,
    n_workers: Optional[int] = None,""",
        1,
    ),
]))

# =========================================================== Notebooks/00_DB_Service.py
EDITS.append(("Notebooks/00_DB_Service.py", [
    ("    TZ_OFFSET_HOURS = 2\n", "", 1),
    ("        TZ_OFFSET_HOURS,\n", "", 1),
    ("    TZ_OFFSET_HOURS,\n", "", 2),
    (
        """                SELECT symbol, timeframe, COUNT(*) AS bars, MIN(time) AS t_min, MAX(time) AS t_max
                FROM ohlcv_bars""",
        """                SELECT symbol, timeframe, COUNT(*) AS bars,
                       MIN(time AT TIME ZONE 'UTC') AS t_min,
                       MAX(time AT TIME ZONE 'UTC') AS t_max
                FROM ohlcv_bars""",
        1,
    ),
    (
        """            # DB speichert die MT5-Serverzeit (UTC+2) als TIMESTAMPTZ; pandas
            # rendert sie in lokaler Zeit (+2). Für die Brokerzeit-Anzeige werden
            # das Suffix entfernt UND die 2 h abgezogen (identisch zum Chart).
            # to_datetime(..., utc=True): schuetzt gegen leere DB (MIN/MAX = NULL
            # -> object-Spalten, .dt wuerde mit AttributeError scheitern).
            df["von"] = pd.to_datetime(df["von"], errors="coerce", utc=True).dt.tz_localize(None) - pd.Timedelta(hours=TZ_OFFSET_HOURS)
            df["bis"] = pd.to_datetime(df["bis"], errors="coerce", utc=True).dt.tz_localize(None) - pd.Timedelta(hours=TZ_OFFSET_HOURS)""",
        """            # BKZ-Kanon (docs/ZEITBASIS_KANON.md): die SQL projiziert bereits
            # die naive Broker-Kerzen-Zeit (kein Offset). to_datetime(...,
            # errors="coerce") schuetzt gegen leere DB (MIN/MAX = NULL ->
            # object-Spalten, .dt wuerde mit AttributeError scheitern).
            df["von"] = pd.to_datetime(df["von"], errors="coerce")
            df["bis"] = pd.to_datetime(df["bis"], errors="coerce")""",
        1,
    ),
    ("            tz_offset_hours=TZ_OFFSET_HOURS,\n", "", 1),
]))

# =========================================================== Notebooks/01_Chart_Inspector.py
EDITS.append(("Notebooks/01_Chart_Inspector.py", [
    ("    TZ_OFFSET_HOURS = 2\n", "", 1),
    ("        TZ_OFFSET_HOURS,\n", "", 1),
    ("    TZ_OFFSET_HOURS,\n", "", 1),
    ("        tz_offset_hours=TZ_OFFSET_HOURS,\n", "", 1),
]))

# =========================================================== Notebooks/02_Signal_Lab.py
EDITS.append(("Notebooks/02_Signal_Lab.py", [
    ("                    tz_offset_hours=2,\n", "", 1),
    ("        tz_offset_hours=2,\n", "", 1),
]))

# =========================================================== backtest_lab/ui.py
EDITS.append(("backtest_lab/ui.py", [
    (
        """from backtest_lab.types import OrderConfig, make_order_config
from backtest_lab.ui_state import get_marimo_states""",
        """from backtest_lab import db as _db
from backtest_lab.types import OrderConfig, make_order_config
from backtest_lab.ui_state import get_marimo_states""",
        1,
    ),
    (
        """def _format_created_at(series: pd.Series) -> pd.Series:
    \"\"\"Formatiert created_at fuer die Anzeige (Lokalzeit, lesbar).

    Die Quell-DB liefert tz-aware Zeitstempel (Europe/Budapest = Berlin).
    Fuer die Tabelle reicht eine kompakte String-Darstellung.
    \"\"\"
    s = pd.to_datetime(series, errors="coerce")
    if getattr(s.dtype, "tz", None) is not None:
        s = s.dt.tz_convert("Europe/Budapest").dt.strftime("%Y-%m-%d %H:%M")
    else:
        s = s.dt.strftime("%Y-%m-%d %H:%M")
    return s.astype(str)""",
        """def _format_created_at(series: pd.Series) -> pd.Series:
    \"\"\"Formatiert created_at als Anzeige-Zeit (Europe/Budapest).

    Delegiert an ``backtest_lab.db._fmt_wallclock_series`` (S4: zentrale
    Anzeige-Dublette). Rechenbasis bleibt die BKZ (naive UTC); die
    BP-Projektion ist reine Darstellung (docs/ZEITBASIS_KANON.md).
    \"\"\"
    return _db._fmt_wallclock_series(series)""",
        1,
    ),
]))


def _apply(text: str, old: str, new: str, cnt: int, pfad: str, idx: int) -> str:
    """Ersetzt ``old``->``new`` mit automatischer EOL-Erkennung."""
    order = ("\r\n", "\n") if "\r\n" in text else ("\n", "\r\n")
    for eol in order:
        o = old.replace("\n", eol)
        n = new.replace("\n", eol)
        c = text.count(o)
        if c == cnt:
            return text.replace(o, n)
    raise AssertionError(
        f"{pfad} #{idx}: erwartet {cnt} Treffer fuer {old[:70]!r}")


def main() -> int:
    for pfad, edits in EDITS:
        p = ROOT / pfad
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        for i, (old, new, cnt) in enumerate(edits, 1):
            text = _apply(text, old, new, cnt, pfad, i)
        # Resttreffer-Kontrolle.
        assert "tz_offset_hours" not in text, f"{pfad}: tz_offset_hours verbleibt!"
        assert "TZ_OFFSET_HOURS" not in text, f"{pfad}: TZ_OFFSET_HOURS verbleibt!"
        assert ".tz_localize(None) -" not in text, f"{pfad}: Offset-Abzug verbleibt!"
        assert ".timestamp())" not in text, f"{pfad}: OS-TZ .timestamp() verbleibt!"
        p.write_bytes(text.encode("utf-8"))
        print(f"OK  {pfad}  ({len(edits)} Edits, {len(text.encode('utf-8')):,} B)")
    print(f"\nS4-Patch angewendet: {len(EDITS)} Dateien.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
