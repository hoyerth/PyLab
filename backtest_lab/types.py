# backtest_lab/types.py
"""Typisierte Datenvertraege fuer das Backtest Lab.

Die Dataclasses sind der verbindliche Vertrag zwischen UI, Runner und DB.
`BacktestRunRecord` ist der 1:1-Abgleich zum DDL in `schema.py`.
"""
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


def new_run_id() -> str:
    """Frische UID pro Backtest-Lauf (uuid4, ohne Bindestriche).

    Nur noch fuer Tests/Fallback: Der Produktivpfad nutzt
    `run_id_from_config` (deterministisch) - identische Konfiguration
    ergibt dieselbe run_id und wird damit UEBERSCHRIEBEN (keine
    endlosen Duplikate, siehe `save_backtest_run`).
    """
    return uuid.uuid4().hex


def run_id_from_config(
    signal_run_id: str,
    symbol: str,
    timeframe: str,
    params_json: str,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> str:
    """Deterministische run_id aus der Backtest-Konfiguration (sha256).

    Idempotenz-Kern (Bugfix 3): 1:1 identische Konfiguration =
    (Signal-Run + Symbol + TF + Order-Parameter + Datumsbereich) ergibt
    IMMER dieselbe run_id. `save_backtest_run` loescht daraufhin den
    vorhandenen Lauf inkl. Trades und schreibt den neuen - es entstehen
    keine endlosen Kopien mehr.

    Args:
        signal_run_id: FK auf `analytics_data.indicator_runs.run_id`.
        symbol / timeframe: Symbol + TF des Signal-Runs.
        params_json: Serialisierte Order-Parameter (`order_params_json`).
        date_from / date_to: Normalisierte UTC-datetime (None = kein Filter).

    Returns:
        SHA-256-Hexdigest (32 Zeichen, gleiche Laenge wie uuid4-hex).
    """
    key = "|".join([
        str(signal_run_id),
        str(symbol),
        str(timeframe),
        str(params_json),
        date_from.isoformat() if date_from is not None else "",
        date_to.isoformat() if date_to is not None else "",
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OrderConfig:
    """Validierte Order-Parameter fuer den Runner.

    Attributes:
        spread_pct: Spread in Prozent der Preisbasis (z. B. 0.15 = 0.15 %).
            Wird halbiert als Slippage an die Engine gegeben.
        stop_loss_pct: Fester Stop-Loss in Prozent KURSBEWEGUNG (Preis-Distanz
            vom Entry-Fill, z. B. 0.5 = 0.5 % Preisbewegung gegen die Position;
            None = kein SL). NICHT als % des Positionswerts zu verstehen - der
            $-Betrag ergibt sich erst aus Position x Kursbewegung.
        take_profit_pct: Fester Take-Profit in Prozent KURSBEWEGUNG (Preis-Distanz
            vom Entry-Fill, z. B. 2.0 = Exit, sobald der Kurs 2 % zugunsten der
            Position gelaufen ist; None = kein TP).
        position_size_pct: Positionsgroesse in Prozent des Kapitals.
        leverage: CFD-Hebel (Vervielfachung des Notional). Vorgabe 1000.
            Das eingesetzte Notional = `equity * leverage * position_size_pct/100`
            (z. B. 10.000 $ x 1000 x 1 % = 100.000 $). Der $-Gewinn bei x %
            Kursbewegung = Notional * x/100 (bei 2 % = 2.000 $).
        equity: Startkapital/Equity in USD (Default 10_000 $) - Basis des
            Value-Sizings (`size = equity * leverage * position_size_pct/100`),
            der Margin (equity * position_size_pct/100) und der Equity-Kurve
            fuer max_drawdown_pct.
        reentry_same_bar: True = Gegensignal schliesst + neuer (gegenlaeufiger)
            Entry in derselben Bar (`upon_opposite_entry=Reverse`). False =
            Gegensignal schliesst nur; neuer Trade erst beim naechsten frischen
            Finding (`upon_opposite_entry=Close`).
    """

    spread_pct: float
    stop_loss_pct: Optional[float]
    take_profit_pct: Optional[float]
    position_size_pct: float
    equity: float = 10_000.0
    leverage: float = 1000.0
    reentry_same_bar: bool = True


def make_order_config(
    spread_pct: float,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    position_size_pct: float,
    equity: float = 10_000.0,
    leverage: float = 1000.0,
    reentry_same_bar: bool = True,
) -> OrderConfig:
    """Validierte OrderConfig aus UI-Werten (Schritt 5).

    Args:
        spread_pct: Spread in Prozent (> 0, <= 10).
        stop_loss_pct: Stop-Loss in Prozent (None = kein SL).
        take_profit_pct: Take-Profit in Prozent (None = kein TP).
        position_size_pct: Positionsgroesse in Prozent des Kapitals (0..100).
        equity: Startkapital/Equity in USD (> 0, Default 10_000 $).
        leverage: CFD-Hebel (> 0, <= 10_000, Vorgabe 1000). Vervielfacht das
            Notional: `equity * leverage * position_size_pct/100`.
        reentry_same_bar: True = Gegensignal schliesst + neuer Entry in
            derselben Bar (`upon_opposite_entry=Reverse`); False = nur Exit,
            neuer Trade erst beim naechsten frischen Finding
            (`upon_opposite_entry=Close`).

    Returns:
        Validiertes `OrderConfig`-Objekt.

    Raises:
        ValueError: Bei ungueltigen Werten (werden in der UI als Meldung
            angezeigt statt stiller Fehlschlag).
    """
    spread_pct = float(spread_pct)
    if not 0 < spread_pct <= 10:
        raise ValueError("Spread muss zwischen 0 und 10 % liegen.")
    if stop_loss_pct is not None and float(stop_loss_pct) <= 0:
        raise ValueError("Stop-Loss muss > 0 sein (oder deaktiviert).")
    if take_profit_pct is not None and float(take_profit_pct) <= 0:
        raise ValueError("Take-Profit muss > 0 sein (oder deaktiviert).")
    position_size_pct = float(position_size_pct)
    if not 0 < position_size_pct <= 100:
        raise ValueError("Position-Sizing muss zwischen 0 und 100 % liegen.")
    equity = float(equity)
    if equity <= 0:
        raise ValueError("Equity/Kapital muss > 0 sein.")
    leverage = float(leverage)
    if not 0 < leverage <= 10_000:
        raise ValueError("Hebel muss zwischen 0 und 10 000 liegen.")
    return OrderConfig(
        spread_pct=spread_pct,
        stop_loss_pct=float(stop_loss_pct) if stop_loss_pct is not None else None,
        take_profit_pct=float(take_profit_pct) if take_profit_pct is not None else None,
        position_size_pct=position_size_pct,
        equity=equity,
        leverage=leverage,
        reentry_same_bar=bool(reentry_same_bar),
    )


def order_params_json(config: OrderConfig) -> str:
    """Serialisiert die Order-Parameter als JSON-String (fuer params_json).

    Args:
        config: Validiertes OrderConfig.

    Returns:
        JSON-String (z. B. `{"spread_pct": 0.15, "stop_loss_pct": 0.2, ...}`).

    Example:
        >>> order_params_json(make_order_config(0.15, 0.2, 2.0, 1.0))
        '{"spread_pct": 0.15, "stop_loss_pct": 0.2, "take_profit_pct": 2.0, "position_size_pct": 1.0, "equity": 10000.0}'
    """
    return json.dumps(asdict(config), ensure_ascii=False)


@dataclass(frozen=True)
class BacktestRunRecord:
    """Metadaten + Gesamtergebnis eines Backtest-Laufs (1 Zeile in backtest_runs).

    run_id ist DETERMINISTISCH (`run_id_from_config`): identische
    Konfiguration ergibt dieselbe run_id und wird beim Speichern
    ueberschrieben (keine endlosen Duplikate). Der Signal-Bezug bleibt
    ueber `signal_run_id` -> `analytics_data.indicator_runs.run_id`
    erhalten.

    Attributes:
        params_json: Volles Order-Parameter-Set als JSON-String.
        date_from/date_to: Gewaehlter Backtest-Zeitraum (UTC-aware).
        r_multiple-Formel: (Exit-Entry) / (Entry-InitialSL) * direction.
    """

    run_id: str
    signal_run_id: str
    run_name: str
    symbol: str
    timeframe: str
    params_json: str
    date_from: datetime
    date_to: datetime
    net_profit: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trade_count: int
    avg_trade_pnl: float
    expectancy: float
    created_at: datetime
    # Bugfix 6 (Max Win): Bester Einzeltrade-PnL des Runs ($). Default 0.0,
    # damit bestehende Konstruktoren (Tests) ohne Anpassung funktionieren.
    max_win: float = 0.0
    # Bugfix 8 (Max Drawdown in $): Absoluter Peak-to-Trough der Equity-Kurve
    # in USD. Der %-Wert (`max_drawdown_pct`) wirkt bei kleinen Equities
    # irrefuehrend (73 % = 7 300 $ bei 10 000 $) - die UI-Tabelle zeigt
    # `max_drawdown` ($). Default 0.0 fuer bestehende Konstruktoren.
    max_drawdown: float = 0.0
    # Bugfix 8 (SL-Count): Anzahl der Exits, die ueber den Stop-Loss
    # geschlossen wurden (exit_reason == "sl"). Default 0.
    sl_count: int = 0


@dataclass(frozen=True)
class BacktestTradeRecord:
    """Ein einzelner Trade (1 Zeile in backtest_trades).

    Attributes:
        run_id: FK auf `backtest_runs.run_id`.
        entry_time/exit_time: UTC-aware Zeitstempel.
        direction: +1 Long, -1 Short.
        r_multiple: (Exit-Entry)/(Entry-InitialSL)*direction; None ohne SL.
    """

    run_id: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: int
    pnl: float
    r_multiple: Optional[float]
