# backtest_lab/runner.py
"""Backtest-Runner (vectorbt 1.1.0).

Engine-Entscheidung: STUFE A (vectorbt 1.1.0) - gefallen per Smoke-Test,
siehe `BacktestLab_UMSETZUNG.md` Abschnitt A / ERGEBNIS ENGINE-SMOKE-TEST.

Verbindliches Aufruf-Schema fuer `vbt.Portfolio.from_signals` (v1.1.0):
- Signale um 1 Bar shiften (Signal bei Bar T -> Entry am Open von T+1)
- `price=open_` zusammen mit `open`/`high`/`low`
- `sl_stop`/`tp_stop` mit `stop_entry_price=StopEntryPrice.FillPrice`
- `upon_opposite_entry` = `OppositeEntryMode.Reverse` (Gegensignal/Reversal)
  bei `reentry_same_bar=True` (Default) bzw. `OppositeEntryMode.Close`
  (nur Exit, neuer Trade erst beim naechsten Finding) bei False
- `slippage=spread_pct/2` (symmetrisch auf Entry+Exit)
- Records: `pf.trades.records`; `direction` 0=Long/1=Short;
  `status=0` (offen am Ende) wird verworfen
- vectorbt wird LAZY importiert (siehe `_get_vbt`) - der ~4-5 s teure
  Import passiert erst beim ersten Backtest, nicht beim Notebook-Start.

Sizing (API-Erkenntnis v1.1.0, in Tests verifiziert):
- `SizeType.Percent` unterstuetzt KEIN Position-Reversal in `from_signals`
  (ValueError: "SizeType.Percent does not support position reversal").
- Daher: **`SizeType.Value`** mit `size = init_cash * position_size_pct/100`
  (fester Notional-Wert pro Trade = fester %-Wert des Startkapitals).
  `init_cash` kommt aus `OrderConfig.equity` (Default 10 000 $, siehe UI).
  Funktioniert mit Reversal + SL/TP + Slippage (Variante A verifiziert).
"""
import multiprocessing as mp
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

import numpy as np
import pandas as pd

from backtest_lab.db import (
    DB_ANALYTICS,
    DB_BACKTEST,
    DB_MARKET,
    connect_backtest,
    load_ohlcv,
    load_signal_events,
    save_backtest_run,
)
from backtest_lab.naming import build_backtest_run_name
from backtest_lab.types import (
    BacktestRunRecord,
    OrderConfig,
    order_params_json,
    run_id_from_config,
)

# Spalten der Trades-DataFrames (ohne run_id - wird von save_backtest_run gesetzt).
# `exit_reason` (Bugfix 8): "sl" (Stop-Loss-Fill) / "tp" (Take-Profit-Fill) /
# "signal" (Gegensignal/Reversal) / "gap" (SL uebersprungen, Fill hinter dem
# Stop -> Verlust > SL-Cap). vectorbt liefert KEIN exit_reason-Feld, daher
# Preisvergleich (exit_price vs. SL/TP-Preis, Toleranz = Slippage).
TRADES_COLUMNS: list[str] = [
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "direction",
    "pnl",
    "r_multiple",
    "exit_reason",
]

# Startkapital als Fallback, wenn weder `init_cash` noch `OrderConfig.equity`
# gesetzt sind (abwaertskompatibel; die UI liefert equity aus den Order-Param.).
DEFAULT_INIT_CASH: float = 100_000.0

# Bugfix 7 (Performance): Bei <= 2 Jobs wird IN-PROCESS gerechnet statt einen
# Multiprocessing-Pool zu spawnen. Auf Windows kostet jeder spawn ~3-5 s
# (Modul-Re-Import + pandas/duckdb je Worker); ein einzelner Run (z. B. 1 Job,
# M30 ueber 10 Wochen) braucht so nur noch den einmaligen vectorbt-Lazy-Import
# (~4-5 s) statt zusaetzlich n Worker-Spawns. Multiprocessing lohnt erst,
# wenn mehrere Jobs den Spawn-Overhead amortisieren.
_LOCAL_EXEC_MAX_JOBS: int = 2

# Lazy-Import fuer vectorbt (ca. 4-5 s Importzeit!): Der schwere Import
# passiert erst beim ersten tatsaechlichen Backtest (GO), nicht mehr beim
# Laden des Notebooks / der Import-Zelle (Zelle 0) -> deutlich schnellere
# Zellen-Startzeit.
_VBT = None


def _get_vbt():
    """Importiert vectorbt beim ersten Aufruf (lazy, singletonsicher).

    Returns:
        Das vectorbt-Modul (nach dem ersten Aufruf gecacht).
    """
    global _VBT
    if _VBT is None:
        import vectorbt as vbt

        _VBT = vbt
    return _VBT


# ---------------------------------------------------------------------------
# Datenaufbereitung (vektorisiert, keine Loops)
# ---------------------------------------------------------------------------

def _build_signal_arrays(
    events: pd.DataFrame,
    bars: pd.DataFrame,
    signal_type: str = "swing_change",
) -> Tuple[np.ndarray, np.ndarray]:
    """Erzeugt Long-/Short-Entry-Arrays (bool, len=bars) aus Signal-Events.

    Timing (lookahead-frei): Signal bei Bar-Close T -> Entry am Open von T+1
    (Arrays werden um 1 Bar geshiftet). Signale, deren Zeit nicht exakt auf
    einer Bar-Zeit liegt, werden uebersprungen (Wanduhr-Garantie: Signal-Zeit
    ist exakt eine Bar-Zeit, in Schritt 3 verifiziert).

    Args:
        events: Signal-Events aus `db.load_signal_events` (Spalten `time`,
            `signal_type`, `direction`).
        bars: OHLCV-Bars aus `db.load_ohlcv` (Spalte `time`, naive UTC).
        signal_type: Nur Events dieses Typs werden beruecksichtigt.

    Returns:
        (long_entries, short_entries) - bool-Arrays der Laenge len(bars),
        bereits um 1 Bar geshiftet (Entry am Open der Folge-Bar).
    """
    n = len(bars)
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    if events is None or events.empty or bars.empty:
        return long_sig, short_sig

    ev = events
    if signal_type:
        ev = ev[ev["signal_type"] == signal_type]
    if ev.empty:
        return long_sig, short_sig

    # Exakte Zeit-Zuordnung Signal-Bar -> Bar-Index (naive UTC auf beiden Seiten)
    bar_times = pd.Index(bars["time"].astype("datetime64[us]"))
    ev_times = pd.to_datetime(ev["time"]).astype("datetime64[us]")
    pos = bar_times.get_indexer(ev_times)
    mask = pos >= 0
    dirs = ev["direction"].to_numpy()[mask]
    idx = pos[mask]

    long_pos = idx[dirs > 0]
    short_pos = idx[dirs < 0]
    if len(long_pos):
        long_sig[long_pos] = True
    if len(short_pos):
        short_sig[short_pos] = True

    # Shift um 1 Bar: Signal bei T -> Entry am Open von T+1
    long_entries = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    long_entries[1:] = long_sig[:-1]
    short_entries[1:] = short_sig[:-1]
    return long_entries, short_entries


def _initial_sl_price(entry_price: float, direction: int, stop_loss_pct: Optional[float]) -> Optional[float]:
    """Initialer Stop-Loss-Preis aus Entry-Preis und SL-Prozentsatz.

    Long: initial_sl = entry * (1 - sl/100)  (SL unterhalb des Entries)
    Short: initial_sl = entry * (1 + sl/100) (SL oberhalb des Entries)

    Args:
        entry_price: Entry-Fill-Preis.
        direction: +1 Long / -1 Short.
        stop_loss_pct: SL in Prozent (None = kein fixer SL).

    Returns:
        Stop-Loss-Preis oder None (kein fixer SL).
    """
    if stop_loss_pct is None:
        return None
    factor = 1 - stop_loss_pct / 100 if direction > 0 else 1 + stop_loss_pct / 100
    return float(entry_price) * factor


def _r_multiple(
    entry_price: float,
    exit_price: float,
    direction: int,
    stop_loss_pct: Optional[float],
) -> Optional[float]:
    """R-Multiple (Definition verbindlich aus Umsetzungsdokument Abschnitt A, Punkt 3):

    `r_multiple = (exit_price - entry_price) / (entry_price - initial_sl_price) * direction`

    Ohne fixen Stop-Loss: `None`.

    Hinweis zur Vorzeichen-Konvention (Formel wird WOERTLICH nach Spezifikation
    umgesetzt): Der Quotient (exit-entry)/(entry-initial_sl) ist bereits fuer
    Long UND Short selbst-signierend (Gewinn = positiv). Die Multiplikation mit
    `direction` fuehrt daher bei Short-Gewinn-Trades zu einem NEGATIVEN
    R-Multiple. Diese Vorzeichen-Konvention stammt aus der Spezifikation und
    wird hier nicht stillschweigend veraendert (siehe Diskussion in
    `BacktestLab_UMSETZUNG.md`).
    """
    if stop_loss_pct is None:
        return None
    initial_sl = _initial_sl_price(entry_price, direction, stop_loss_pct)
    if initial_sl is None or entry_price == initial_sl:
        return None
    return (exit_price - entry_price) / (entry_price - initial_sl) * direction


def _exit_reason(
    entry_price: float,
    exit_price: float,
    direction: int,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    spread_pct: float,
) -> str:
    """Exit-Grund eines Trades: "sl" / "tp" / "signal" / "gap" (Bugfix 8).

    vectorbt 1.1.0 liefert in `pf.trades.records` KEIN `exit_reason`-Feld.
    Der Exit-Grund wird daher ueber den Exit-Preis bestimmt:

    - "sl": Exit-Fill am SL-Preis (inkl. Slippage-Toleranz) - normaler
      Stop-Loss, Verlust ~ SL-Cap (z. B. 500 $ bei 0.5 % / Hebel 1000).
    - "gap": Exit liegt JENSEITS des SL-Niveaus (ausserhalb Toleranz) - der
      Stop wurde zwischen zwei Bars UEBERSPRUNGEN (Fill am Open/naechsten
      Kurs hinter dem Stop). Verlust > SL-Cap. Ursache: vbt prueft Stops
      erst ab der Bar NACH dem Entry - wird der SL schon in der Entry-Bar
      erreicht, fuellt vbt erst am Open der Folge-Bar (der bereits weiter
      gelaufen ist). Echte Wochenend-/Pausen-Gaps sind selten.
    - "tp": Exit-Fill am TP-Preis (inkl. Toleranz).
    - "signal": Gegensignal/Reversal-Exit am Open (kein SL/TP beruehrt).

    Toleranz: max(0.1 %, 2 x Slippage) der Preisbasis - Slippage ist
    `spread_pct/200` (symmetrisch auf Entry+Exit), der Stop-Fill darf also
    um maximal diesen Betrag vom Zielpreis abweichen.

    Args:
        entry_price: Entry-Fill-Preis.
        exit_price: Exit-Fill-Preis.
        direction: +1 Long / -1 Short.
        stop_loss_pct: SL in Prozent (None = kein SL).
        take_profit_pct: TP in Prozent (None = kein TP).
        spread_pct: Spread in Prozent (fuer die Slippage-Toleranz).

    Returns:
        "sl", "tp", "gap" oder "signal".
    """
    tol = max(0.001, spread_pct / 200.0 * 2.0)
    if stop_loss_pct is not None:
        sl_price = _initial_sl_price(entry_price, direction, stop_loss_pct)
        if sl_price is not None:
            # Normaler SL-Fill: Exit am SL-Preis (inkl. Slippage-Toleranz)
            if abs(exit_price - sl_price) / entry_price <= tol:
                return "sl"
            # Gap (Bugfix 8): Exit liegt JENSEITS des SL-Niveaus - der Stop
            # wurde uebersprungen (Fill am Open/naechsten Kurs hinter dem
            # Stop), Verlust > SL-Cap. Long: Exit unterhalb des SL; Short:
            # Exit oberhalb des SL.
            if direction > 0 and exit_price < sl_price:
                return "gap"
            if direction < 0 and exit_price > sl_price:
                return "gap"
    if take_profit_pct is not None:
        factor = 1 + take_profit_pct / 100 if direction > 0 else 1 - take_profit_pct / 100
        tp_price = float(entry_price) * factor
        if abs(exit_price - tp_price) / entry_price <= tol:
            return "tp"
    return "signal"


# ---------------------------------------------------------------------------
# Metriken (deterministisch, aus den GESCHLOSSENEN Trades berechnet)
# ---------------------------------------------------------------------------

def _compute_metrics(trades: pd.DataFrame, init_cash: float) -> dict:
    """Run-Level-Metriken aus der Trades-Tabelle (nur geschlossene Trades).

    Definitionen (dokumentiert, deterministisch pruefbar):
        net_profit       = Summe(pnl)
        win_rate         = Gewinne / Trades
        profit_factor    = Bruttogewinn / |Bruttoverlust| (inf, wenn keine
                           Verluste; 0.0 bei 0 Trades)
        max_drawdown_pct = max Peak-to-Trough auf der Equity-Kurve
                           (init_cash + Cumsum der PnL) in Prozent
        max_drawdown     = derselbe Peak-to-Trough in USD ($) - Bugfix 8:
                           Der %-Wert wirkt bei kleinen Equities irrefuehrend
                           (z. B. 73 % = 7 300 $ bei 10 000 $ Startkapital),
                           die Tabelle zeigt daher den $-Betrag.
        sl_count         = Anzahl der Exits via Stop-Loss (Bugfix 8)
                           (Zeilen mit exit_reason == "sl")
        sharpe_ratio     = mean(pnl)/std(pnl)*sqrt(n) (Per-Trade; 0.0 bei n<2)
        trade_count      = Anzahl geschlossener Trades
        avg_trade_pnl    = net_profit / trade_count
        expectancy       = win_rate * avg_win - (1-win_rate) * avg_loss
        max_win          = bester Einzeltrade-PnL in $ (max(pnl); 0.0 bei
                           keinem Trade) - Bugfix 6

    Args:
        trades: DataFrame mit Spalte `pnl` (GESCHLOSSENE Trades).
        init_cash: Startkapital (fuer die Equity-Kurve).

    Returns:
        Dict mit den 9 Run-Level-Metriken (Float/Int, DB-kompatibel).
    """
    n = len(trades)
    if n == 0:
        return {
            "net_profit": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown": 0.0,
            "sl_count": 0,
            "sharpe_ratio": 0.0,
            "trade_count": 0,
            "avg_trade_pnl": 0.0,
            "expectancy": 0.0,
            "max_win": 0.0,
        }

    pnl = trades["pnl"].to_numpy(dtype=float)
    wins = pnl > 0
    losses = pnl < 0
    n_win = int(wins.sum())
    n_loss = n - n_win

    net_profit = float(pnl.sum())
    win_rate = n_win / n
    gross_profit = float(pnl[wins].sum())
    gross_loss = float(-pnl[losses].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    avg_trade_pnl = net_profit / n
    avg_win = float(pnl[wins].mean()) if n_win else 0.0
    avg_loss = float(-pnl[losses].mean()) if n_loss else 0.0
    expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss

    std = float(pnl.std(ddof=1)) if n >= 2 else 0.0
    sharpe_ratio = float(pnl.mean()) / std * np.sqrt(n) if n >= 2 and std > 0 else 0.0

    equity = init_cash + np.concatenate(([0.0], np.cumsum(pnl)))
    running_max = np.maximum.accumulate(equity)
    dd = np.where(running_max > 0, (running_max - equity) / running_max, 0.0)
    max_drawdown_pct = float(dd.max()) * 100.0
    # Bugfix 8: absoluter Peak-to-Trough in $ (fuer die Tabellen-Anzeige)
    max_drawdown = float(np.max(running_max - equity))
    # Bugfix 8: Anzahl der Exits via Stop-Loss (sl_count in backtest_runs)
    if "exit_reason" in trades.columns:
        sl_count = int((trades["exit_reason"] == "sl").sum())
    else:
        sl_count = 0

    return {
        "net_profit": net_profit,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct,
        "max_drawdown": max_drawdown,
        "sl_count": sl_count,
        "sharpe_ratio": sharpe_ratio,
        "trade_count": n,
        "avg_trade_pnl": avg_trade_pnl,
        "expectancy": expectancy,
        "max_win": float(pnl.max()),
    }


# ---------------------------------------------------------------------------
# Records -> Trades-DataFrame + RunRecord
# ---------------------------------------------------------------------------

# Schwellenwert fuer einen ECHTEN Zeit-Gap (Bugfix 8): Liegt zwischen Exit-Bar
# und der Bar davor mehr als 1 Stunde, war der Markt geschlossen (taegliche
# Handelspause 23:00-0:00 Uhr oder Wochenende). Bei M30 ist die Pause ~90 min,
# das Wochenende ~25 h; normale M30-/H1-Bars liegen bei 30/60 min.
GAP_MIN_DELTA: pd.Timedelta = pd.Timedelta(hours=1)


def _classify_exit(
    entry_price: float,
    exit_price: float,
    direction: int,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    spread_pct: float,
    bars: pd.DataFrame,
    exit_idx: int,
) -> tuple[float, str]:
    """Klassifiziert den Exit-Grund und korrigiert SL-Ueberspruenge (Bugfix 8).

    vectorbt prueft Stops erst ab der Bar NACH dem Entry. Wird der SL-Preis
    schon in der Entry-Bar erreicht oder oeffnet die Folge-Bar jenseits des
    Niveaus, fuellt vbt am Open der Folge-Bar -> Verlust > SL-Cap.

    CFD-Praxis (User-Spezifikation): Orders werden DIREKT am Preis ausgefuehrt,
    es gibt kein Slippage -> der SL wird zum SL-Preis geschlossen (Hard Exit,
    Verlust = SL-Risiko, z. B. 500 $ bei SL 0.5 % / Hebel 1000). Einzige
    Ausnahme: ein ECHTER Zeit-Gap (Handelspause 23-0 Uhr oder Wochenende,
    Bar-Abstand > `GAP_MIN_DELTA`) - dort bleibt der Gap-Fill (exit_reason
    "gap", Verlust > SL-Cap).

    Args:
        entry_price: Entry-Fill-Preis.
        exit_price: Exit-Fill-Preis (vbt).
        direction: +1 Long / -1 Short.
        stop_loss_pct: SL in Prozent (None = kein SL).
        take_profit_pct: TP in Prozent (None = kein TP).
        spread_pct: Spread in Prozent (fuer die Slippage-Toleranz).
        bars: OHLCV-Bars (Spalte `time`, naive UTC) - fuer den Zeit-Gap-Check.
        exit_idx: Bar-Index des Exits in `bars`.

    Returns:
        (exit_price_final, exit_reason) - exit_price_final ist bei einem
        SL-Hard-Exit der SL-Preis, sonst der vbt-Fill-Preis.
    """
    sl_price = _initial_sl_price(entry_price, direction, stop_loss_pct)
    if sl_price is not None:
        beyond = (direction > 0 and exit_price < sl_price) or (
            direction < 0 and exit_price > sl_price
        )
        if beyond:
            # Echter Zeit-Gap (Handelspause/Wochenende)? -> Gap-Fill behalten
            if exit_idx > 0 and len(bars) > exit_idx:
                delta = pd.Timestamp(bars["time"].iloc[exit_idx]) - pd.Timestamp(
                    bars["time"].iloc[exit_idx - 1]
                )
                if delta > GAP_MIN_DELTA:
                    return exit_price, "gap"
            # Kein Zeit-Gap: Hard Exit am SL-Preis (CFD, kein Slippage)
            return sl_price, "sl"
    return exit_price, _exit_reason(
        entry_price, exit_price, direction,
        stop_loss_pct, take_profit_pct, spread_pct,
    )


def _correct_pnl(
    pnl: float,
    entry_price: float,
    exit_price_orig: float,
    exit_price_final: float,
    direction: int,
) -> float:
    """Skaliert den PnL eines Trades auf einen korrigierten Exit-Preis.

    Anteile = pnl / ((Exit_orig - Entry) * direction). Der korrigierte PnL
    ergibt sich aus DENSELBEN Anteilen am neuen Exit-Preis (SL-Hard-Exit:
    PnL = SL-Risiko, z. B. -500 $).

    Args:
        pnl: Original-PnL aus vectorbt.
        entry_price / exit_price_orig / exit_price_final: Preise.
        direction: +1 Long / -1 Short.

    Returns:
        Korrigierter PnL (unveraendert, wenn exit_price_final == exit_price_orig).
    """
    if exit_price_final == exit_price_orig:
        return pnl
    denom = (exit_price_orig - entry_price) * direction
    if denom == 0:
        return pnl
    shares = pnl / denom
    return (exit_price_final - entry_price) * direction * shares


def _records_to_trades(
    records: pd.DataFrame,
    bars: pd.DataFrame,
    order_config: OrderConfig,
) -> pd.DataFrame:
    """Mappt vectorbt-Trade-Records (geschlossen) auf die `backtest_trades`-Form.

    Args:
        records: `pf.trades.records` (NUR status==1, bereits gefiltert).
        bars: OHLCV-Bars (Spalte `time` fuer entry_time/exit_time).
        order_config: Order-Parameter (fuer den R-Multiple).

    Returns:
        DataFrame mit `TRADES_COLUMNS` (ohne run_id).
    """
    if records is None or records.empty:
        return pd.DataFrame(columns=TRADES_COLUMNS)

    rec = records.copy()
    times = bars["time"].to_numpy()
    entry_idx = rec["entry_idx"].to_numpy(dtype=int)
    exit_idx = rec["exit_idx"].to_numpy(dtype=int)

    # direction: vbt 0=Long, 1=Short -> +1 / -1
    vbt_dir = rec["direction"].to_numpy(dtype=int)
    direction = np.where(vbt_dir == 0, 1, -1)
    entry_price = rec["entry_price"].to_numpy(dtype=float)
    exit_price = rec["exit_price"].to_numpy(dtype=float)
    pnl = rec["pnl"].to_numpy(dtype=float)

    # Bugfix 8 (SL-Hard-Exit): Klassifiziert jeden Exit ueber
    # `_classify_exit` - "gap" NUR bei echtem Zeit-Gap (Handelspause/
    # Wochenende), sonst Hard Exit am SL-Preis ("sl", PnL = SL-Risiko),
    # weil CFD-Orders direkt am Preis ohne Slippage ausgefuehrt werden.
    outcomes = [
        _classify_exit(
            float(ep), float(xp), int(d),
            order_config.stop_loss_pct, order_config.take_profit_pct,
            order_config.spread_pct, bars, int(xi),
        )
        for ep, xp, d, xi in zip(entry_price, exit_price, direction, exit_idx)
    ]
    exit_price_final = [o[0] for o in outcomes]
    exit_reason = [o[1] for o in outcomes]
    pnl_final = [
        _correct_pnl(float(p), float(ep), float(xp), float(xf), int(d))
        for p, ep, xp, xf, d in zip(pnl, entry_price, exit_price, exit_price_final, direction)
    ]
    r_mult = [
        _r_multiple(float(ep), float(xf), int(d), order_config.stop_loss_pct)
        for ep, xf, d in zip(entry_price, exit_price_final, direction)
    ]

    return pd.DataFrame({
        "entry_time": pd.to_datetime(times[entry_idx], utc=True),
        "exit_time": pd.to_datetime(times[exit_idx], utc=True),
        "entry_price": entry_price,
        "exit_price": exit_price_final,
        "direction": direction,
        "pnl": pnl_final,
        "r_multiple": r_mult,
        "exit_reason": exit_reason,
    })


def _to_utc_datetime(value) -> Optional[datetime]:
    """Wandelt date/ISO-String/datetime in tz-aware UTC-datetime (Mitternacht).

    Args:
        value: `datetime.date`, ISO-String ("YYYY-MM-DD") oder datetime.

    Returns:
        tz-aware UTC-datetime oder None.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Einzelner Backtest
# ---------------------------------------------------------------------------

def run_backtest(
    signal_run_id: str,
    symbol: str,
    timeframe: str,
    order_config: OrderConfig,
    date_from: Optional[object] = None,
    date_to: Optional[object] = None,
    signal_type: str = "swing_change",
    init_cash: Optional[float] = None,
    free_tag: str = "",
    run_name_override: Optional[str] = None,
    db_market: Optional[object] = None,
    db_analytics: Optional[object] = None,
) -> Tuple[BacktestRunRecord, pd.DataFrame]:
    """Fuehrt einen einzelnen Backtest-Lauf aus (reine Berechnung, kein DB-Write).

    Timing (lookahead-frei): Signal bei Bar-Close T -> Entry am Open von T+1.
    Exits: SL/TP (intrabar, `stop_entry_price=FillPrice`), Gegensignal
    (bei `reentry_same_bar=True`: Reversal am Open derselben Folge-Bar,
    `upon_opposite_entry=Reverse`; bei False: nur Exit, `upon_opposite_entry=
    Close`). Offene Positionen am `date_to`-Ende (status=0) werden verworfen.

    Args:
        signal_run_id: FK auf `analytics_data.indicator_runs.run_id`.
        symbol: Symbol (z. B. "SILVER") - identisch zum Signal-Run.
        timeframe: Timeframe (z. B. "M30") - identisch zum Signal-Run.
        order_config: Validiertes Order-Parameter-Set (inkl. `equity`).
        date_from / date_to: Backtest-Zeitraum (date, ISO-String oder
            datetime, naive UTC-Interpretation).
        signal_type: Signaltyp der Entries (Default "swing_change").
        init_cash: Startkapital fuer das Value-Sizing. None = `order_config.equity`
            (Default; die UI liefert equity aus den Order-Parametern).
        free_tag: Optionaler Textanhang an den Run-Namen.
        run_name_override: Optionaler fester Run-Name (kein Zeitstempel).
        db_market / db_analytics: Alternativ-Pfade (fuer Tests).

    Returns:
        (BacktestRunRecord, trades_df) - trades_df ist leer, wenn kein
        geschlossener Trade entstand (0-Trades-Run wird trotzdem erzeugt).

    Raises:
        ValueError: Bei fehlenden/inkonsistenten Eingaben.
    """
    if init_cash is None:
        init_cash = order_config.equity

    bars = load_ohlcv(symbol, timeframe, date_from=date_from, date_to=date_to, db_path=db_market)
    events = load_signal_events(signal_run_id, signal_type=signal_type, db_path=db_analytics)

    created_at = datetime.now(timezone.utc)
    # Deterministische run_id aus der Konfiguration (Bugfix 3): identische
    # Konfiguration -> gleiche run_id -> `save_backtest_run` ueberschreibt
    # den vorhandenen Lauf (keine endlosen Duplikate).
    date_from_dt = _to_utc_datetime(date_from)
    date_to_dt = _to_utc_datetime(date_to)
    run_id = run_id_from_config(
        signal_run_id, symbol, timeframe,
        order_params_json(order_config), date_from_dt, date_to_dt,
    )
    run_name = run_name_override or build_backtest_run_name(
        order_config.spread_pct,
        order_config.stop_loss_pct,
        order_config.take_profit_pct,
        order_config.position_size_pct,
        created_at,
        free_tag,
        leverage=order_config.leverage,
    )

    if bars.empty:
        # Kein Handel moeglich (keine Bars im Zeitraum) -> 0-Trades-Run
        trades = pd.DataFrame(columns=TRADES_COLUMNS)
        metrics = _compute_metrics(trades, init_cash)
        record = _build_record(
            run_id, signal_run_id, run_name, symbol, timeframe,
            order_config, date_from_dt, date_to_dt, metrics, created_at,
        )
        return record, trades

    long_entries, short_entries = _build_signal_arrays(events, bars, signal_type)

    sl_stop = order_config.stop_loss_pct / 100.0 if order_config.stop_loss_pct is not None else None
    tp_stop = order_config.take_profit_pct / 100.0 if order_config.take_profit_pct is not None else None
    # WICHTIG (Bugfix 7 / TP-Definition): sl_stop/tp_stop sind in vectorbt
    # BRUCHTEILE DER KURSBEWEGUNG relativ zum Entry-Fill (mit
    # stop_entry_price=FillPrice): tp_stop=0.02 -> Exit, sobald der Kurs 2 %
    # zugunsten der Position gelaufen ist (TP-Preis = Fill x 1.02 fuer Long).
    # Das ist KEIN % des Positionswerts - der $-PnL ergibt sich erst aus
    # Position x Kursbewegung.
    # spread_pct in Prozent -> Slippage als Dezimalbruch, halbiert (symmetrisch)
    slippage = order_config.spread_pct / 200.0

    # CFD-Hebel (Bugfix 7): Notional = equity * leverage * position_size_pct/100.
    # vectorbt kappt bei `SizeType.Value` die Anteile auf `init_cash` -> die
    # Engine-Kaufkraft muss `equity * leverage` sein (nur so skaliert der
    # PnL mit dem Hebel; verifiziert: size=100k + init_cash=10M -> 1000 Anteile
    # -> 2 % Move = 2000 $). Die Metriken rechnen weiter auf dem echten Equity
    # (init_cash) -> max_drawdown_pct bleibt am realen Kapital orientiert.
    buying_power = init_cash * order_config.leverage
    size_value = buying_power * order_config.position_size_pct / 100.0

    vbt = _get_vbt()
    enums = vbt.portfolio.enums

    # Gegensignal-Verhalten (Checkbox "Re-Entry gleiche Bar"):
    #  True  = Reverse -> Gegensignal schliesst alten Trade UND oeffnet den
    #          neuen (gegenlaeufigen) Entry in derselben Bar.
    #  False = Close   -> Gegensignal schliesst nur; neuer Trade erst beim
    #          naechsten frischen Finding.
    upon_opposite = (
        enums.OppositeEntryMode.Reverse
        if order_config.reentry_same_bar
        else enums.OppositeEntryMode.Close
    )

    pf = vbt.Portfolio.from_signals(
        bars["close"].to_numpy(),
        entries=long_entries,
        short_entries=short_entries,
        open=bars["open"].to_numpy(),
        high=bars["high"].to_numpy(),
        low=bars["low"].to_numpy(),
        price=bars["open"].to_numpy(),
        slippage=slippage,
        size_type=enums.SizeType.Value,
        size=size_value,
        # Engine-Kaufkraft = Equity * Hebel (sonst kappt vectorbt das Notional
        # auf init_cash und der Hebel haette keine Wirkung).
        init_cash=buying_power,
        sl_stop=sl_stop,
        tp_stop=tp_stop,
        stop_entry_price=enums.StopEntryPrice.FillPrice,
        upon_opposite_entry=upon_opposite,
    )

    records = pf.trades.records
    closed = records[records["status"] == 1] if records is not None and not records.empty else records
    trades = _records_to_trades(closed, bars, order_config)
    # Metriken auf Basis des ECHTEN Equity (init_cash, ungehebelt): die
    # Equity-Kurve fuer max_drawdown_pct soll am realen Kapital gemessen
    # werden, nicht an der (Hebel-)Kaufkraft.
    metrics = _compute_metrics(trades, init_cash)
    record = _build_record(
        run_id, signal_run_id, run_name, symbol, timeframe,
        order_config, date_from_dt, date_to_dt, metrics, created_at,
    )
    return record, trades


def _build_record(
    run_id: str,
    signal_run_id: str,
    run_name: str,
    symbol: str,
    timeframe: str,
    order_config: OrderConfig,
    date_from: Optional[object],
    date_to: Optional[object],
    metrics: dict,
    created_at: datetime,
) -> BacktestRunRecord:
    """Baut den `BacktestRunRecord` (1:1 zum DDL)."""
    return BacktestRunRecord(
        run_id=run_id,
        signal_run_id=signal_run_id,
        run_name=run_name,
        symbol=symbol,
        timeframe=timeframe,
        params_json=order_params_json(order_config),
        date_from=_to_utc_datetime(date_from),
        date_to=_to_utc_datetime(date_to),
        net_profit=float(metrics["net_profit"]),
        win_rate=float(metrics["win_rate"]),
        profit_factor=float(metrics["profit_factor"]),
        max_drawdown_pct=float(metrics["max_drawdown_pct"]),
        max_drawdown=float(metrics.get("max_drawdown", 0.0)),
        sl_count=int(metrics.get("sl_count", 0)),
        sharpe_ratio=float(metrics["sharpe_ratio"]),
        trade_count=int(metrics["trade_count"]),
        avg_trade_pnl=float(metrics["avg_trade_pnl"]),
        expectancy=float(metrics["expectancy"]),
        created_at=created_at,
        max_win=float(metrics.get("max_win", 0.0)),
    )


def run_and_save_backtest(
    signal_run_id: str,
    symbol: str,
    timeframe: str,
    order_config: OrderConfig,
    date_from: Optional[object] = None,
    date_to: Optional[object] = None,
    signal_type: str = "swing_change",
    init_cash: Optional[float] = None,
    free_tag: str = "",
    run_name_override: Optional[str] = None,
    db_market: Optional[object] = None,
    db_analytics: Optional[object] = None,
    db_backtest: Optional[object] = None,
) -> str:
    """Fuehrt einen Backtest aus und persistiert ihn in `backtest_data`.

    Args:
        (Parameter wie `run_backtest`.)
        db_backtest: Pfad zur Backtest-DB (Default: `data/backtest_data.duckdb`).

    Returns:
        run_id des persistierten Laufs.
    """
    record, trades = run_backtest(
        signal_run_id=signal_run_id,
        symbol=symbol,
        timeframe=timeframe,
        order_config=order_config,
        date_from=date_from,
        date_to=date_to,
        signal_type=signal_type,
        init_cash=init_cash,
        free_tag=free_tag,
        run_name_override=run_name_override,
        db_market=db_market,
        db_analytics=db_analytics,
    )
    con = connect_backtest(db_backtest, ensure_schema=True)
    try:
        save_backtest_run(con, record, trades)
    finally:
        con.close()
    return record.run_id


# ---------------------------------------------------------------------------
# Paralleler Backtest (Multiprocessing, Chunking-Muster aus dem Signal Lab)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BacktestJob:
    """Ein einzelner Backtest-Job (fuer Einzel- und Parallel-Lauf).

    Attributes:
        signal_run_id: FK auf `analytics_data.indicator_runs.run_id`.
        symbol / timeframe: Symbol + TF des Signal-Runs.
        order_config: Validiertes Order-Parameter-Set.
        date_from / date_to: Backtest-Zeitraum (ISO-String, naive UTC).
        free_tag: Optionaler Textanhang an den Run-Namen.
        run_name_override: Optionaler fester Run-Name.
    """

    signal_run_id: str
    symbol: str
    timeframe: str
    order_config: OrderConfig
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    free_tag: str = ""
    run_name_override: Optional[str] = None


_WORKER: dict = {}


def _init_worker(db_market: str, db_analytics: str, init_cash: Optional[float]) -> None:
    """Initialisiert die Worker-Globals (spawn-sicher, Windows)."""
    _WORKER["db_market"] = db_market
    _WORKER["db_analytics"] = db_analytics
    _WORKER["init_cash"] = init_cash
    _WORKER["bars_cache"] = {}


def _worker_backtest_job(job: BacktestJob) -> tuple:
    """Berechnet EINEN einzelnen Backtest-Job (fuer parallele Fortschrittsanzeige).

    OHLCV wird je (symbol, timeframe, date_from, date_to) im Worker gecacht
    (mehrere Order-Parameter-Sets auf denselben Daten - kein erneutes Laden).

    Hinweis (Bugfix 2): Die Parallelschleife nutzt `imap_unordered` mit
    chunksize=1 ueber diese Funktion - der Fortschrittsbalken erhaelt damit
    NACH JEDEM fertigen Job einen Zwischenwert (vorher: nur nach ganzen
    Chunks, bei wenigen Jobs sprang der Balken 0% -> 100%).
    """
    record, trades = run_backtest(
        signal_run_id=job.signal_run_id,
        symbol=job.symbol,
        timeframe=job.timeframe,
        order_config=job.order_config,
        date_from=job.date_from,
        date_to=job.date_to,
        init_cash=_WORKER["init_cash"],
        free_tag=job.free_tag,
        run_name_override=job.run_name_override,
        db_market=_WORKER["db_market"],
        db_analytics=_WORKER["db_analytics"],
    )
    return record, trades


def run_backtests_parallel(
    jobs: list,
    n_workers: Optional[int] = None,
    init_cash: Optional[float] = None,
    db_market: Optional[object] = None,
    db_analytics: Optional[object] = None,
    db_backtest: Optional[object] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> list:
    """Fuehrt mehrere Backtest-Jobs parallel aus und persistiert die Ergebnisse.

    Chunking-Muster aus dem Signal Lab (`run_sweep_parallel`): Die Worker
    rechnen (jeder laedt seine Daten read-only), die Persistierung erfolgt
    im Parent nach jedem fertigen Job (vermeidet Write-Locks auf
    `backtest_data`). `imap_unordered` + chunksize=1 liefert die Ergebnisse
    in Fertigstellungs-Reihenfolge -> der Progress-Callback feuert NACH
    JEDEM JOB (echte Zwischenwerte im Fortschrittsbalken).

    Args:
        jobs: Liste von `BacktestJob`.
        n_workers: Anzahl Worker (Default: CPU-Kerne).
        init_cash: Startkapital fuer das Value-Sizing. None = je Job
            `order_config.equity` (Default; die UI liefert equity aus den
            Order-Parametern - alle Jobs teilen sich i. d. R. ein Config-Set).
        db_market / db_analytics / db_backtest: Alternativ-Pfade (fuer Tests).
        progress_callback: Callback(done, total, run_name) nach jedem Run.
        cancel_callback: Liefert True -> Abbruch nach dem aktuellen Job
            (bereits persistierte Runs bleiben in der DB).

    Returns:
        Liste der persistierten run_ids (in Fertigstellungs-Reihenfolge).
    """
    jobs = list(jobs)
    if not jobs:
        return []
    n_workers = max(1, n_workers or (os.cpu_count() or 1))

    run_ids: list = []
    total = len(jobs)
    done = 0

    # Bugfix 7 (Performance): Bei wenigen Jobs keinen Pool spawnen - die
    # Worker-Reihenfolge + Progress-Callback bleibt identisch (imap_unordered
    # liefert ohnehin in Fertigstellungs-Reihenfolge = hier sequenziell).
    # Der vectorbt-Lazy-Import passiert dann genau EINMAL im Hauptprozess
    # und wird fuer Folge-Runs derselben Session gecacht (_VBT).
    if len(jobs) <= _LOCAL_EXEC_MAX_JOBS:
        _init_worker(
            str(db_market or DB_MARKET), str(db_analytics or DB_ANALYTICS), init_cash
        )
        for job in jobs:
            if cancel_callback and cancel_callback():
                break  # Abbruch: weitere Jobs nicht mehr persistieren
            record, trades = _worker_backtest_job(job)
            con = connect_backtest(db_backtest, ensure_schema=True)
            try:
                save_backtest_run(con, record, trades)
            finally:
                con.close()
            run_ids.append(record.run_id)
            done += 1
            if progress_callback:
                progress_callback(done, total, record.run_name)
        if progress_callback:
            progress_callback(done, total, "")
        return run_ids

    ctx = mp.get_context("spawn")
    with ctx.Pool(
        processes=n_workers,
        initializer=_init_worker,
        initargs=(str(db_market or DB_MARKET), str(db_analytics or DB_ANALYTICS), init_cash),
    ) as pool:
        for record, trades in pool.imap_unordered(_worker_backtest_job, jobs, chunksize=1):
            if cancel_callback and cancel_callback():
                break  # Abbruch: weitere Jobs nicht mehr persistieren
            con = connect_backtest(db_backtest, ensure_schema=True)
            try:
                save_backtest_run(con, record, trades)
            finally:
                con.close()
            run_ids.append(record.run_id)
            done += 1
            if progress_callback:
                progress_callback(done, total, record.run_name)
    if progress_callback:
        progress_callback(done, total, "")
    return run_ids
