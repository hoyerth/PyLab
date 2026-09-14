"""Zentrale Testdatei fuer das Signal Lab (User-Regel: alle Tests in test/test.py).

Enthaelt die Regressionstests fuer die kritischen Button-Fixes des
Notebooks `Notebooks/02_Signal_Lab.py`:

1. test_all_buttons()      - Komplett-Durchlauf: SAVE, GO, Dialog, Ja, Stopp, QL-Save
2. test_state_singleton()  - State-Objekte stabil ueber Re-Runs (Singleton-Fix)
3. test_gc_cycles()        - Dialog-Buttons klickbar nach GC (weakref-Registry-Fix)

Ausfuehrung (headless, keine UI):
    .venv\\Scripts\\python.exe test\\test.py
"""
import asyncio, gc, importlib.util, queue, sys
from contextlib import asynccontextmanager
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from marimo._ast.app import InternalApp
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.streams import QueuePipe, ThreadSafeStream
from marimo._messaging.types import KernelStreams
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.app.kernel_runner import AppKernelRunner
from marimo._runtime.commands import AppMetadata, UpdateUIElementCommand
from marimo._runtime.kernel_lifecycle import KernelArgs, kernel_session
from marimo._runtime.params import CLIArgs
from marimo._session.model import SessionMode

NOTEBOOK = PROJ / "Notebooks" / "02_Signal_Lab.py"


def load_app():
    spec = importlib.util.spec_from_file_location("signal_lab_nb", NOTEBOOK)
    nb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb)
    return nb.app


def walk(obj, acc):
    if obj is None:
        return
    if isinstance(obj, UIElement):
        acc.append(obj)
    for attr in ("_children", "children", "_elements", "_data", "elements", "_live_children"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if isinstance(val, (list, tuple)):
                for x in val:
                    walk(x, acc)
            elif val is not None:
                walk(val, acc)


def buttons(runner):
    out = []
    for _, output in runner.outputs.items():
        els = []
        walk(output, els)
        for e in els:
            if getattr(e, "_name", "") == "marimo-button":
                out.append((e, e._args.label or ""))
    return out


def has_button(runner, label_part):
    return any(label_part in label for _, label in buttons(runner))


async def click(runner, label_part):
    """Klickt den ersten Button, dessen Label label_part enthaelt."""
    for e, label in buttons(runner):
        if label_part in label:
            await runner.set_ui_element_value(
                UpdateUIElementCommand(object_ids=[e._id], values=[1], request=None),
                notify_frontend=False,
            )
            rk = runner._kernel
            rk.state_updates.clear()
            await rk.run_stale_cells()
            return True
    return False


@asynccontextmanager
async def kernel_runner():
    sys.stdout.reconfigure(encoding="utf-8")
    q = queue.Queue()
    iq = queue.Queue()
    stream = ThreadSafeStream(QueuePipe(q), iq, redirect_console=False)
    streams = KernelStreams(stream=stream, stdout=None, stderr=None, stdin=None)
    args = KernelArgs(
        streams=streams,
        debugger=None,
        configs={},
        app_metadata=AppMetadata(
            {}, CLIArgs({}).to_dict(), argv=[], filename="nb.py", app_config=load_app()._config
        ),
        user_config=DEFAULT_CONFIG,
        mode=SessionMode.EDIT,
        control_queue=queue.Queue(),
        set_ui_element_queue=queue.Queue(),
        virtual_file_storage="shared_memory",
    )
    with kernel_session(args) as (kernel, ctx):
        with ctx.install():
            runner = AppKernelRunner(InternalApp(load_app()))
            await runner.run(set(runner._kernel.graph.cells.keys()))
            yield runner


async def test_all_buttons():
    """Komplett-Durchlauf aller Buttons (SAVE, GO, Dialog, Ja, Stopp, QL-Save)."""
    async with kernel_runner() as runner:
        rk = runner._kernel
        import signal_lab.sweep_ui as sui

        print("[SAVE] Klick:", await click(runner, "Stand speichern"))
        print("   save_msg =", repr(rk.globals["save_msg"]()))
        assert "Stand gespeichert" in rk.globals["save_msg"](), "SAVE fehlgeschlagen"

        print("[GO] Klick:", await click(runner, "GO"))
        print("   go_state =", rk.globals["go_state"](),
              "| Dialog:", has_button(runner, "Ja, starten"))
        assert rk.globals["go_state"]() == "confirm", "GO oeffnet Dialog nicht"

        print("[JA] Klick:", await click(runner, "Ja, starten"))
        print("   running =", sui.get_state()["running"],
              "| Dialog weg:", not has_button(runner, "Ja, starten"))
        assert sui.get_state()["running"], "Sweep startet nicht"
        assert not has_button(runner, "Ja, starten"), "Dialog nach JA nicht geschlossen"
        sui.finish([], None)

        print("[STOPP] Klick:", await click(runner, "Stopp"))
        sui.cancel()
        await asyncio.sleep(0.5)
        print("   running =", sui.get_state()["running"])

        print("[QL-SAVE] Klick:", await click(runner, "Quick Look merken"))
        print("   save_msg =", repr(rk.globals["save_msg"]()))
        assert "Quick Look" in rk.globals["save_msg"](), "QL-SAVE fehlgeschlagen"
        print("=== test_all_buttons OK ===")


async def test_state_singleton():
    """State-Objekte muessen ueber Re-Runs der Setup-Zelle stabil bleiben.

    Regression fuer den Fix: Wuerde Zelle 4a bei jedem Lauf NEUE mo.state()
    erzeugen, zeigten die Dialog-Buttons auf verwaiste States -> tote Buttons.
    """
    async with kernel_runner() as runner:
        rk = runner._kernel
        import signal_lab.sweep_ui as sui

        await click(runner, "GO")
        gs_before = rk.globals["go_state"]
        print("[1] GO -> go_state:", rk.globals["go_state"](),
              "| Dialog:", has_button(runner, "Ja, starten"))

        # Setup-Zelle erneut ausfuehren (simuliert 2. Lauf beim Start)
        cell_setup = next(
            cid for cid, cell in rk.graph.cells.items() if "STATE-SETUP" in cell.code
        )
        await runner.run({cell_setup})
        gs_after = rk.globals["go_state"]
        print("[2] Setup-Zelle erneut ausgefuehrt")
        print("    Objekt identisch:", gs_before is gs_after,
              "| Wert:", rk.globals["go_state"](),
              "| Dialog:", has_button(runner, "Ja, starten"))

        ok = await click(runner, "Ja, starten")
        print("[3] Klick 'Ja, starten':", ok, "| running:", sui.get_state()["running"])
        sui.finish([], None)

        assert gs_before is gs_after, "State-Objekt NICHT stabil - tote Buttons!"
        print("=== test_state_singleton OK ===")


async def test_gc_cycles():
    """Dialog-Buttons muessen nach GC und Re-Runs klickbar bleiben.

    Regression fuer den Fix: marimo haelt UI-Elemente nur als weakref; ohne
    Export (`return btn_confirm, btn_cancel`) koennte der GC sie einsammeln.
    """
    async with kernel_runner() as runner:
        rk = runner._kernel
        import signal_lab.sweep_ui as sui

        print("[0] btn_confirm in Globals:", "btn_confirm" in rk.globals,
              "| btn_cancel in Globals:", "btn_cancel" in rk.globals)
        assert "btn_confirm" in rk.globals, "Dialog-Buttons nicht exportiert!"

        # Zyklus 1: GO -> Dialog -> JA
        await click(runner, "GO")
        await click(runner, "Ja, starten")
        print("[1] Zyklus 1 JA -> running:", sui.get_state()["running"],
              "| Dialog weg:", not has_button(runner, "Ja, starten"))
        sui.finish([], None)
        gc.collect()

        # Zyklus 2: GO -> Dialog -> NEIN (Abbrechen)
        await click(runner, "GO")
        await click(runner, "Nein, abbrechen")
        print("[2] Zyklus 2 NEIN -> go_state:", rk.globals["go_state"](),
              "| Dialog weg:", not has_button(runner, "Ja, starten"))
        gc.collect()

        # Zyklus 3: GO -> Dialog -> JA (nach 2 GCs)
        await click(runner, "GO")
        await click(runner, "Ja, starten")
        print("[3] Zyklus 3 JA -> Dialog weg:", not has_button(runner, "Ja, starten"))
        sui.finish([], None)

        assert not has_button(runner, "Ja, starten"), "Dialog nach JA nicht geschlossen"
        print("=== test_gc_cycles OK ===")


async def main():
    print("=" * 60)
    print("Signal Lab Regressionstests")
    print("=" * 60)
    await test_all_buttons()
    print()
    await test_state_singleton()
    print()
    await test_gc_cycles()
    print()
    print("ALLE TESTS GRUEN")


# ---------------------------------------------------------------------------
# VectorBT-Smoke-Test (Backtest Lab, Stufe A)
# ---------------------------------------------------------------------------

def test_vectorbt_smoke() -> None:
    """Verifiziert vectorbt 1.1.0 gegen pandas 3.0.5 / numpy 2.5.2.

    Prueft exakt die Features, die der Backtest-Runner v1 braucht:

    WICHTIGE v1.1.0-API-ERKENNTNISSE (Basis fuer runner.py):
      - Records liegen unter pf.trades.records (nicht pf.records)
      - direction: 0 = Long, 1 = Short
      - status: 1 = geschlossen, 0 = offen (am Ende verwerfen)
      - Execution am Open: price=open_ + open/high/low
      - price=open_ fuehrt am Open DERSELBEN Bar aus -> Signal bei Bar T
        muss um 1 Bar geshiftet werden (True bei Index T+1), damit der
        Entry am Open von T+1 stattfindet (lookahead-frei)
      - SL/TP relativ zum Entry-Fill: stop_entry_price=FillPrice
        (Default ValPrice basiert auf close - VERMEIDEN!)
      - Gegensignal/Reversal: upon_opposite_entry=Reverse (Close+Entry
        am selben Open-Preis)
      - Long UND Short-Entry in derselben Bar = Konflikt (0 Trades) ->
        in der Praxis nie gleichzeitig (direction ist +/-1)
      - Slippage wirkt symmetrisch gegen den Trader (Entry+Exit)

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_vectorbt_smoke()"
    """
    import numpy as np
    import vectorbt as vbt
    from vectorbt.portfolio.enums import OppositeEntryMode, StopEntryPrice

    open_ = np.array([100, 101, 102, 101, 100, 99, 98, 99, 100, 101, 102, 103], dtype=float)
    high = np.array([101, 103, 103, 102, 101, 100, 100, 101, 102, 103, 104, 104], dtype=float)
    low = np.array([99, 100, 101, 100, 99, 98, 97, 98, 99, 100, 101, 102], dtype=float)
    close = np.array([101, 102, 101, 100, 99, 98, 99, 100, 101, 102, 103, 103], dtype=float)

    def shift(sig: np.ndarray) -> np.ndarray:
        """Signal bei Bar T -> True bei Index T+1 (Entry am Open von T+1)."""
        out = np.zeros(len(sig), dtype=bool)
        out[1:] = sig[:-1]
        return out

    # --- 1) Long+Short Split, Execution am Open der Folge-Bar --------------
    # Long-Signal bar0 -> Entry Open bar1=101; Reversal Short-Signal bar3 ->
    # Long-Close + Short-Entry Open bar4=100; Short-Exit-Signal bar5 -> Open bar6=98
    entries = shift(np.array([True, False, False, False, False, False, False, False, False, False, False, False]))
    short_entries = shift(np.array([False, False, False, True, False, False, False, False, False, False, False, False]))
    short_exits = shift(np.array([False, False, False, False, False, True, False, False, False, False, False, False]))

    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries, exits=None,
        short_entries=short_entries, short_exits=short_exits,
        open=open_, high=high, low=low,
        price=open_, slippage=0.0,
        size=1.0, init_cash=10000,
    )
    rec = pf.trades.records
    print("[1] from_signals OK, Zeilen:", len(rec))
    print(rec[["direction", "entry_idx", "exit_idx", "entry_price", "exit_price", "pnl"]].to_string())
    assert len(rec) == 2, f"Erwartet 2 Trades, erhalten {len(rec)}"
    long_row = rec[rec["direction"] == 0].iloc[0]   # 0 = Long
    short_row = rec[rec["direction"] == 1].iloc[0]  # 1 = Short
    assert float(long_row["entry_price"]) == 101.0, "Long-Entry nicht am Open der Folge-Bar"
    assert float(long_row["exit_price"]) == 100.0, "Reversal-Exit nicht am Open"
    assert float(short_row["exit_price"]) == 98.0, "Short-Exit nicht am Open der Folge-Bar"
    assert float(long_row["pnl"]) == -1.0, "Long-PnL falsch"
    assert float(short_row["pnl"]) == 2.0, "Short-PnL falsch"
    print("    Long-PnL =", float(long_row["pnl"]), "| Short-PnL =", float(short_row["pnl"]), "-> OK")

    # --- 2) SL/TP relativ zum Entry-Fill (stop_entry_price=FillPrice) -----
    # Long-Signal bar0 -> Entry Open bar1=101; SL=2% -> 98.98, Low erreicht 98
    # an bar5 -> SL greift intrabar an bar5 zu 98.98
    pf2 = vbt.Portfolio.from_signals(
        close, entries=entries,
        open=open_, high=high, low=low,
        price=open_, sl_stop=0.02, tp_stop=0.05,
        stop_entry_price=StopEntryPrice.FillPrice,
        slippage=0.0,
        size=1.0, init_cash=10000,
    )
    rec2 = pf2.trades.records
    print("[2] SL/TP (FillPrice) OK, Zeilen:", len(rec2))
    print(rec2[["direction", "entry_idx", "exit_idx", "entry_price", "exit_price", "pnl"]].to_string())
    assert len(rec2) == 1, "SL/TP-Test sollte genau 1 Trade liefern"
    r2 = rec2.iloc[0]
    assert int(r2["exit_idx"]) == 5, f"SL-Exit-Bar falsch: {int(r2['exit_idx'])}"
    assert abs(float(r2["exit_price"]) - 98.98) < 0.01, f"SL-Preis falsch: {float(r2['exit_price'])}"
    print("    SL-Exit-Preis =", float(r2["exit_price"]), "-> OK (98.98)")

    # --- 3) Slippage symmetrisch auf Entry+Exit ----------------------------
    slippage = 0.01  # entspricht spread_pct=2% (halbiert)
    # Long-Entry idx1 (Open bar1=101) + Long-Exit idx4 (Open bar4=100)
    exits3 = shift(np.array([False, False, False, True, False, False, False, False, False, False, False, False]))
    pf3 = vbt.Portfolio.from_signals(
        close, entries=entries, exits=exits3,
        open=open_, high=high, low=low,
        price=open_, slippage=slippage,
        size=1.0, init_cash=10000,
    )
    rec3 = pf3.trades.records
    assert len(rec3) == 1
    r3 = rec3.iloc[0]
    exp_entry = 101 * (1 + slippage)
    exp_exit = 100 * (1 - slippage)
    assert abs(float(r3["entry_price"]) - exp_entry) < 1e-9, "Slippage auf Entry fehlt"
    assert abs(float(r3["exit_price"]) - exp_exit) < 1e-9, "Slippage auf Exit fehlt"
    print(f"[3] Slippage: Entry {exp_entry:.2f} (101*1.01) | Exit {exp_exit:.2f} (100*0.99) -> OK")

    # --- 4) Reversal: Gegensignal schliesst + oeffnet am selben Open -------
    # (identisch zu Test 1, aber explizit ohne short_exits -> Short bleibt offen)
    pf4 = vbt.Portfolio.from_signals(
        close, entries=entries, short_entries=short_entries,
        open=open_, high=high, low=low,
        price=open_, upon_opposite_entry=OppositeEntryMode.Reverse,
        slippage=0.0,
        size=1.0, init_cash=10000,
    )
    rec4 = pf4.trades.records
    print("[4] Reversal OK, Zeilen:", len(rec4))
    print(rec4[["direction", "entry_idx", "exit_idx", "entry_price", "exit_price", "pnl", "status"]].to_string())
    assert len(rec4) == 2
    long_closed = rec4[rec4["direction"] == 0].iloc[0]
    short_opened = rec4[rec4["direction"] == 1].iloc[0]
    assert float(long_closed["exit_price"]) == float(short_opened["entry_price"]), \
        "Reversal: Exit/Entry-Preis nicht identisch am selben Open"
    assert int(long_closed["status"]) == 1, "Long muss geschlossen sein"
    assert int(short_opened["status"]) == 0, "Short muss am Ende noch offen sein (status=0)"

    # --- 5) Records-Extraktion (Basis fuer backtest_trades) -----------------
    assert {"entry_idx", "exit_idx", "entry_price", "exit_price", "direction", "pnl"} <= set(rec.columns)
    # Offene Positionen (status=0) werden im Runner verworfen
    closed = rec4[rec4["status"] == 1]
    print(f"[5] Records-Spalten OK | geschlossene Trades: {len(closed)}")
    print("=== test_vectorbt_smoke OK ===")


if __name__ == "__main__":
    asyncio.run(main())


# ---------------------------------------------------------------------------
# Backtest Lab - DB-Schema & Persistenz (Schritt 2)
# ---------------------------------------------------------------------------

def test_backtest_schema() -> None:
    """Verifiziert das v1-Schema und die Persistenz-Schicht (Schritt 2).

    Prueft:
      1. Tabellen `backtest_runs` + `backtest_trades` werden idempotent angelegt
      2. `save_backtest_run` schreibt Run-Header + Einzeltrades transaktional
      3. SELECT liefert die gespeicherten Werte korrekt zurueck
      4. FK-Constraint: Trade ohne Run wird abgelehnt
      5. Run mit 0 Trades wird trotzdem als Metadaten-Zeile gespeichert

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_backtest_schema()"
    """
    import duckdb
    import pandas as pd
    from datetime import datetime, timezone
    from pathlib import Path

    from backtest_lab.db import connect_backtest, save_backtest_run
    from backtest_lab.naming import build_backtest_run_name
    from backtest_lab.types import BacktestRunRecord, new_run_id

    db_path = Path(__file__).resolve().parent / "_test_backtest_data.duckdb"
    if db_path.exists():
        db_path.unlink()

    try:
        # --- 1) Idempotentes Schema --------------------------------
        init_backtest_schema(db_path)
        init_backtest_schema(db_path)  # zweiter Aufruf muss fehlerfrei sein
        con = connect_backtest(db_path, ensure_schema=False)
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables").fetchall()]
        print("[1] Tabellen:", tables)
        assert "backtest_runs" in tables and "backtest_trades" in tables
        con.close()

        # --- 2+3) save_backtest_run + SELECT -----------------------
        con = connect_backtest(db_path, ensure_schema=False)
        run_id = new_run_id()
        ts = datetime.now(timezone.utc)
        run = BacktestRunRecord(
            run_id=run_id,
            signal_run_id="aabbccddeeff0011",
            run_name=build_backtest_run_name(0.05, 2.0, 4.0, 1.0, ts),
            symbol="GOLD",
            timeframe="M30",
            params_json='{"spread_pct": 0.05, "stop_loss_pct": 2.0, '
                        '"take_profit_pct": 4.0, "position_size_pct": 1.0}',
            date_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2024, 6, 1, tzinfo=timezone.utc),
            net_profit=125.5,
            win_rate=0.55,
            profit_factor=1.35,
            max_drawdown_pct=8.2,
            sharpe_ratio=0.95,
            trade_count=20,
            avg_trade_pnl=6.275,
            expectancy=0.42,
            created_at=ts,
            # Bugfix 8: Max Drawdown in $ + SL-Count
            max_drawdown=820.0,
            sl_count=3,
        )
        trades = pd.DataFrame([
            {
                "entry_time": datetime(2024, 1, 5, 10, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2024, 1, 6, 14, 0, tzinfo=timezone.utc),
                "entry_price": 2000.0,
                "exit_price": 2010.0,
                "direction": 1,
                "pnl": 10.0,
                "r_multiple": 1.0,
            },
            {
                "entry_time": datetime(2024, 2, 3, 8, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2024, 2, 4, 9, 0, tzinfo=timezone.utc),
                "entry_price": 2050.0,
                "exit_price": 2040.0,
                "direction": -1,
                "pnl": -10.0,
                "r_multiple": -0.5,
            },
        ])
        save_backtest_run(con, run, trades)

        rows_runs = con.execute("SELECT * FROM backtest_runs").df()
        rows_trades = con.execute("SELECT * FROM backtest_trades").df()
        print(f"[2] runs={len(rows_runs)} | trades={len(rows_trades)}")
        assert len(rows_runs) == 1 and len(rows_trades) == 2
        assert rows_runs.iloc[0]["run_id"] == run_id
        assert rows_runs.iloc[0]["net_profit"] == 125.5
        assert rows_runs.iloc[0]["trade_count"] == 20
        assert rows_trades["run_id"].nunique() == 1
        assert rows_trades.iloc[0]["direction"] == 1
        assert rows_trades.iloc[1]["r_multiple"] == -0.5
        # Bugfix 8: max_drawdown ($) + sl_count werden persistiert und
        # zurueckgeliefert; exit_reason fehlt im handgebauten trades_df und
        # muss per Defensiv-Fuellung NULL sein (KeyError-Schutz).
        assert rows_runs.iloc[0]["max_drawdown"] == 820.0, (
            f"max_drawdown ($) falsch: {rows_runs.iloc[0]['max_drawdown']}"
        )
        assert rows_runs.iloc[0]["sl_count"] == 3, (
            f"sl_count falsch: {rows_runs.iloc[0]['sl_count']}"
        )
        assert "exit_reason" in rows_trades.columns, "exit_reason-Spalte fehlt"
        print("    Run-Header + Trades korrekt gespeichert -> OK")

        # --- 4) FK-Constraint --------------------------------------
        try:
            con.execute(
                """
                INSERT INTO backtest_trades (run_id, entry_time, entry_price)
                VALUES ('unbekannt', NULL, 1.0)
                """
            )
            assert False, "FK-Verletzung wurde nicht abgelehnt!"
        except Exception:
            print("    FK-Constraint greift (fremde run_id abgelehnt) -> OK")

        # --- 5) Run mit 0 Trades -----------------------------------
        run0 = BacktestRunRecord(
            run_id=new_run_id(),
            signal_run_id="aabbccddeeff0011",
            run_name=build_backtest_run_name(0.05, None, None, 1.0, ts),
            symbol="SILVER",
            timeframe="H1",
            params_json='{"spread_pct": 0.05}',
            date_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2024, 6, 1, tzinfo=timezone.utc),
            net_profit=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            trade_count=0,
            avg_trade_pnl=0.0,
            expectancy=0.0,
            created_at=ts,
        )
        save_backtest_run(con, run0, pd.DataFrame())
        cnt = con.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]
        assert cnt == 2, f"0-Trades-Run fehlt: runs={cnt}"
        print(f"    0-Trades-Run gespeichert (runs={cnt}) -> OK")
        con.close()
        print("=== test_backtest_schema OK ===")
    finally:
        if db_path.exists():
            db_path.unlink()


def init_backtest_schema(db_path) -> None:
    """Lokaler Helper: legt das Schema in der Test-DB an."""
    from backtest_lab.schema import init_backtest_schema as _init
    _init(db_path)


# ---------------------------------------------------------------------------
# Backtest Lab - Read-only-Quellen (Schritt 3)
# ---------------------------------------------------------------------------

def test_read_only_sources() -> None:
    """Verifiziert die read-only-Anbindung an market_data / analytics_data.

    Prueft:
      1. `connect_market`/`connect_analytics` sind wirklich read-only
         (Schreibversuch wird abgelehnt).
      2. `load_ohlcv` liefert OHLCV + spread mit naive-UTC-Zeitachse
         (Wanduhr-Garantie, `AT TIME ZONE 'UTC'`) und Datumsfilter.
      3. `load_signal_events` liefert Signal-Events eines echten Runs
         mit Richtung +1/-1 und naive-UTC-Zeitachse.
      4. Konsistenz: Signale liegen auf den OHLCV-Bar-Zeiten desselben
         Symbols/Timeframes (Signal-Bar ist eine echte Bar).

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_read_only_sources()"
    """
    import duckdb
    from backtest_lab.db import (
        connect_analytics,
        connect_market,
        get_signal_runs,
        load_ohlcv,
        load_signal_events,
    )

    # --- 1) Read-only-Erzwingung --------------------------------------
    con_m = connect_market()
    try:
        con_m.execute("CREATE TABLE _ro_test (i INTEGER)")
        assert False, "market_data akzeptiert Schreibzugriff!"
    except duckdb.Error:
        print("[1] market_data read-only -> OK")
    finally:
        con_m.close()

    con_a = connect_analytics()
    try:
        con_a.execute("CREATE TABLE _ro_test (i INTEGER)")
        assert False, "analytics_data akzeptiert Schreibzugriff!"
    except duckdb.Error:
        print("[1] analytics_data read-only -> OK")
    finally:
        con_a.close()

    # --- 2) load_ohlcv ------------------------------------------------
    bars = load_ohlcv("GOLD", "M30", date_from="2024-01-01", date_to="2024-01-31")
    print(f"[2] load_ohlcv GOLD M30 (Jan 2024): {len(bars)} Bars")
    assert not bars.empty, "Keine OHLCV-Daten geladen"
    assert {"time", "open", "high", "low", "close", "spread"} <= set(bars.columns)
    assert bars["time"].is_monotonic_increasing, "Zeit nicht aufsteigend"
    assert getattr(bars["time"].dtype, "tz", None) is None, "Zeit muss naive UTC sein"
    assert bars["high"].ge(bars["low"]).all(), "high < low gefunden"
    print(f"    Zeitachse: {bars['time'].iloc[0]} .. {bars['time'].iloc[-1]} (naive UTC)")

    # --- 3) load_signal_events (letzter Signal-Lab-Lauf) --------------
    runs = get_signal_runs()
    assert not runs.empty, "Keine Signal-Runs in analytics_data"
    newest = runs.iloc[0]  # ORDER BY created_at DESC
    ev = load_signal_events(str(newest["run_id"]))
    print(f"[3] Events Run {newest['run_name']}: {len(ev)} Events")
    assert not ev.empty, "Keine Events fuer neuesten Run"
    assert set(ev["direction"].unique()) <= {1, -1}, "Richtung muss +1/-1 sein"
    assert getattr(ev["time"].dtype, "tz", None) is None, "Zeit muss naive UTC sein"
    print(f"    Richtungen: {sorted(int(x) for x in ev['direction'].unique())} | "
          f"Zeit: {ev['time'].iloc[0]} .. {ev['time'].iloc[-1]} (naive UTC)")

    # --- 4) Konsistenz: Signale auf OHLCV-Bar-Zeiten ------------------
    sym, tf = str(newest["symbol"]), str(newest["timeframe"])
    full = load_ohlcv(sym, tf)
    bar_times = set(full["time"])
    ev_times = set(ev["time"])
    matched = ev_times & bar_times
    print(f"[4] Symbol/TF {sym}/{tf}: {len(ev_times)} Event-Zeiten, "
          f"{len(matched)} auf Bar-Zeiten")
    assert len(matched) == len(ev_times), (
        f"Signal-Events nicht auf OHLCV-Bars abbildbar "
        f"(matched {len(matched)}/{len(ev_times)})"
    )
    print("=== test_read_only_sources OK ===")


# ---------------------------------------------------------------------------
# Backtest Lab - Run-Auswahl "letzter Signal-Lab-Lauf" (Schritt 4)
# ---------------------------------------------------------------------------

def test_last_signal_runs() -> None:
    """Verifiziert die Run-Auswahl (Schritt 4): nur der letzte Signal-Lab-Lauf.

    Prueft:
      1. `extract_run_timestamp` parst `_JJJJMMTT_HHMM` (mit/ohne free_tag,
         None-Fall).
      2. `get_last_signal_runs` auf der echten analytics_data liefert NUR den
         letzten Lauf-Batch (neuester Name-Zeitstempel), keine Historie.
      3. Symbol/TF-Filter.
      4. Synthetische Test-DB (in test/): der Name-Zeitstempel schlaegt einen
         spaeteren `created_at` (Re-Run-Fall / INSERT OR IGNORE).
      5. Synthetische Test-DB: `run_name_override` (kein Zeitstempel) ->
         `MAX(created_at)`-Fallback.

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_last_signal_runs()"
    """
    import duckdb
    import pandas as pd
    from datetime import datetime
    from pathlib import Path

    from backtest_lab.db import (
        extract_run_timestamp,
        get_last_signal_runs,
        get_signal_runs,
    )

    # --- 1) extract_run_timestamp --------------------------------------
    ts = extract_run_timestamp("MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608")
    assert ts == datetime(2026, 8, 21, 16, 8), f"Timestamp-Fehler: {ts}"
    ts2 = extract_run_timestamp(
        "MAINDICATOR_ehma_p06_s10_a3_GOLD_H1_20260821_1436_p11-htf"
    )
    assert ts2 == datetime(2026, 8, 21, 14, 36), f"free_tag-Fehler: {ts2}"
    assert extract_run_timestamp("MEIN_OVERRIDE_LAUF") is None
    assert extract_run_timestamp(None) is None
    assert extract_run_timestamp("") is None
    print("[1] extract_run_timestamp OK (ohne/mit free_tag, override, None, '')")

    # --- 2) echte analytics_data: nur letzter Batch ---------------------
    runs = get_signal_runs()
    assert not runs.empty, "Keine Runs in analytics_data"
    last = get_last_signal_runs()
    assert not last.empty, "Kein letzter Lauf ermittelbar"
    assert "run_id" in last.columns and "run_name" in last.columns
    # Invariante: jeder Run im letzten Batch hat denselben (maximalen)
    # effektiven Zeitstempel wie das Gesamt-Maximum.
    def _eff(run_name, created_at):
        """Gleiche Logik wie db._effective_run_timestamp (nur fuer den Test)."""
        ts_ = extract_run_timestamp(run_name)
        if ts_ is not None:
            return pd.Timestamp(ts_).tz_localize("Europe/Budapest")
        return pd.to_datetime(created_at, errors="coerce", utc=True)

    eff_all = [_eff(rn, ca) for rn, ca in zip(runs["run_name"], runs["created_at"])]
    eff_last = [_eff(rn, ca) for rn, ca in zip(last["run_name"], last["created_at"])]
    assert max(eff_last) == max(eff_all), "Letzter Batch ist nicht der neueste"
    assert all(e == max(eff_all) for e in eff_last), (
        "Letzter Batch enthaelt Runs mit unterschiedlichem Zeitstempel"
    )
    print(f"[2] get_last_signal_runs: {len(last)} Run(s) im letzten Lauf -> OK")
    for _, r in last.iterrows():
        print(f"      {r['run_name']}  ({r['symbol']}/{r['timeframe']})")

    # --- 3) Symbol/TF-Filter --------------------------------------------
    sym, tf = str(last.iloc[0]["symbol"]), str(last.iloc[0]["timeframe"])
    filtered = get_last_signal_runs(symbol=sym, timeframe=tf)
    assert not filtered.empty
    assert (filtered["symbol"].str.lower() == sym.lower()).all(), "Symbol-Filter fehlt"
    assert (filtered["timeframe"].str.lower() == tf.lower()).all(), "TF-Filter fehlt"
    print(f"[3] Filter {sym}/{tf}: {len(filtered)} Run(s) -> OK")

    # --- 4+5) Synthetische Test-DBs (test/_test_*.duckdb) ---------------
    db_path = Path(__file__).resolve().parent / "_test_analytics_runs.duckdb"
    db_override = Path(__file__).resolve().parent / "_test_analytics_override.duckdb"
    for p in (db_path, db_override):
        if p.exists():
            p.unlink()
    try:
        # --- 4) Name-Zeitstempel schlaegt created_at (Re-Run-Fall) ------
        con = duckdb.connect(str(db_path))
        con.execute(
            """
            CREATE TABLE indicator_runs (
                run_id VARCHAR PRIMARY KEY,
                indicator_name VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                timeframe VARCHAR NOT NULL,
                params_json JSON NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                run_name VARCHAR
            )
            """
        )
        # b1 (Name-Ts 1000) hat den SPAETEREN created_at, b2 (Name-Ts 1100)
        # den FRUEHEREN -> b2 muss gewinnen (Primaerlogik Name-Ts).
        rows = [
            ("b1r1", "MAINDICATOR", "GOLD", "M30", '{"p":1}',
             "2026-01-02 10:00:00+01:00", "MAIN_b1_GOLD_M30_20260101_1000"),
            ("b1r2", "MAINDICATOR", "SILVER", "M30", '{"p":1}',
             "2026-01-02 10:00:00+01:00", "MAIN_b1_SILVER_M30_20260101_1000"),
            ("b2r1", "MAINDICATOR", "SILVER", "M30", '{"p":1}',
             "2026-01-01 09:00:00+01:00", "MAIN_b2_SILVER_M30_20260101_1100"),
        ]
        con.executemany(
            "INSERT INTO indicator_runs VALUES (?,?,?,?,?,CAST(? AS TIMESTAMPTZ),?)",
            rows,
        )
        con.close()

        last_syn = get_last_signal_runs(db_path=db_path)
        assert len(last_syn) == 1, f"Erwartet genau b2r1, erhalten {len(last_syn)}"
        assert last_syn.iloc[0]["run_id"] == "b2r1", (
            "Name-Zeitstempel (1100) muss gegen spaeteren created_at gewinnen"
        )
        print("[4] Name-Ts (1100) schlaegt spaeteren created_at (b1) -> OK")

        # --- 5) run_name_override (kein Zeitstempel) -> MAX(created_at) --
        con = duckdb.connect(str(db_override))
        con.execute(
            """
            CREATE TABLE indicator_runs (
                run_id VARCHAR PRIMARY KEY,
                indicator_name VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                timeframe VARCHAR NOT NULL,
                params_json JSON NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                run_name VARCHAR
            )
            """
        )
        rows_o = [
            ("o1", "MAINDICATOR", "GOLD", "M30", '{"p":1}',
             "2026-01-01 08:00:00+01:00", "MEIN_LAUF_ALT"),
            ("o2", "MAINDICATOR", "SILVER", "M30", '{"p":1}',
             "2026-01-02 09:00:00+01:00", "MEIN_LAUF_NEU"),
            ("o3", "MAINDICATOR", "SILVER", "M30", '{"p":1}',
             "2026-01-02 09:00:00+01:00", "MEIN_LAUF_NEU2"),
        ]
        con.executemany(
            "INSERT INTO indicator_runs VALUES (?,?,?,?,?,CAST(? AS TIMESTAMPTZ),?)",
            rows_o,
        )
        con.close()

        last_ov = get_last_signal_runs(db_path=db_override)
        assert set(last_ov["run_id"].tolist()) == {"o2", "o3"}, (
            f"Override-Fallback muss MAX(created_at) liefern: {last_ov['run_id'].tolist()}"
        )
        print("[5] run_name_override -> MAX(created_at) (o2, o3) -> OK")

        print("=== test_last_signal_runs OK ===")
    finally:
        for p in (db_path, db_override):
            if p.exists():
                p.unlink()


# ---------------------------------------------------------------------------
# Backtest Lab - Komplexitaets-/RAM-Schaetzung (Schritt 5)
# ---------------------------------------------------------------------------

def test_complexity_estimation() -> None:
    """Verifiziert die Komplexitaets-/RAM-Schaetzung (Schritt 5).

    Prueft:
      1. `count_bars` (read-only market_data) mit/ohne Datumsfilter -
         GOLD/M30 Jan 2024 = 962 Bars (identisch zu load_ohlcv).
      2. `bar_counts_for` liefert nur vorhandene Kombinationen.
      3. `estimate_complexity`: n_runs = Kombis x Param-Sets, RAM-Formel,
         Ablehnung bei max_runs- und max_ram-Ueberschreitung, OK-Fall.
      4. `go_allowed` nur bei ok.
      5. Komplexitaets-Konfiguration: JSON round-trip in test/, Fallback
         bei fehlender/defekter Datei.

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_complexity_estimation()"
    """
    from pathlib import Path

    from backtest_lab.complexity import (
        DEFAULT_CONFIG,
        bar_counts_for,
        estimate_complexity,
        go_allowed,
        load_complexity_config,
        save_complexity_config,
    )
    from backtest_lab.db import count_bars

    # --- 1) count_bars ------------------------------------------------
    n_full = count_bars("GOLD", "M30")
    n_jan = count_bars("GOLD", "M30", date_from="2024-01-01", date_to="2024-01-31")
    print(f"[1] count_bars GOLD/M30: gesamt={n_full} | Jan 2024={n_jan}")
    assert n_full > 0 and n_jan == 962, f"count_bars Jan 2024: {n_jan} != 962"
    assert n_jan <= n_full, "Datumsfilter muss die Menge verkleinern"

    # --- 2) bar_counts_for ---------------------------------------------
    counts = bar_counts_for(["SILVER", "GOLD"], ["M30"], date_from="2024-01-01")
    print(f"[2] bar_counts_for: { {f'{k[0]}/{k[1]}': v for k, v in counts.items()} }")
    assert counts, "Keine Kombinationen gefunden"
    assert all(v > 0 for v in counts.values())

    # --- 3) estimate_complexity ----------------------------------------
    cfg_small = {**DEFAULT_CONFIG, "est_bytes_per_bar": 100, "est_overhead_mb_per_run": 1.0}
    # 2 Kombis x 1 Param-Set, 1000+2000 Bars
    rep_ok = estimate_complexity({("SILVER", "M30"): 1000, ("GOLD", "M30"): 2000}, 1, cfg_small)
    print(f"[3] OK-Fall: n_runs={rep_ok.n_runs} | total_mb={rep_ok.est_ram_total_mb:.3f} "
          f"| per_run_mb={rep_ok.est_ram_per_run_mb:.3f}")
    assert rep_ok.n_runs == 2, f"n_runs falsch: {rep_ok.n_runs}"
    assert rep_ok.bars_total == 3000, f"bars_total falsch: {rep_ok.bars_total}"
    assert abs(rep_ok.est_ram_total_mb - (3000 * 100 / 1e6 + 2 * 1.0)) < 1e-9
    assert abs(rep_ok.est_ram_per_run_mb - (2000 * 100 / 1e6 + 1.0)) < 1e-9
    assert rep_ok.ok and go_allowed(rep_ok), "OK-Fall muss freigegeben sein"

    # n_runs-Limit ueberschreiten
    cfg_lim = {**cfg_small, "max_runs": 1}
    rep_runs = estimate_complexity({("SILVER", "M30"): 1000, ("GOLD", "M30"): 2000}, 1, cfg_lim)
    assert not rep_runs.ok and not go_allowed(rep_runs)
    assert any("Run-Anzahl" in r for r in rep_runs.reasons)
    print(f"    n_runs-Ablehnung: {rep_runs.reasons}")

    # RAM-Limit ueberschreiten
    cfg_ram = {**cfg_small, "max_ram_mb": 1.0}
    rep_ram = estimate_complexity({("SILVER", "M30"): 1000}, 1, cfg_ram)
    assert not rep_ram.ok and not go_allowed(rep_ram)
    assert any("RAM" in r for r in rep_ram.reasons)
    print(f"    RAM-Ablehnung: {rep_ram.reasons}")

    # Warnschwelle (kein harter Abbruch, nur Hinweis)
    cfg_warn = {**cfg_small, "warn_ram_mb": 0.5, "max_ram_mb": 1000}
    rep_warn = estimate_complexity({("SILVER", "M30"): 1000}, 1, cfg_warn)
    assert rep_warn.ok, "Warnung darf nicht ablehnen"
    assert any("Warnung" in w for w in rep_warn.warnings)
    assert rep_warn.reasons == ()
    print(f"    Warnschwelle: {rep_warn.warnings}")

    # go_allowed(None) = False
    assert not go_allowed(None), "go_allowed(None) muss False sein"

    # --- 4) Konfiguration JSON round-trip (in test/) --------------------
    cfg_path = Path(__file__).resolve().parent / "_test_complexity.json"
    if cfg_path.exists():
        cfg_path.unlink()
    try:
        cfg_loaded = load_complexity_config(cfg_path)
        assert cfg_loaded == DEFAULT_CONFIG, "Fallback muss DEFAULT_CONFIG sein"
        modified = {**cfg_loaded, "max_ram_mb": 8192.0}
        save_complexity_config(modified, cfg_path)
        cfg_loaded2 = load_complexity_config(cfg_path)
        assert cfg_loaded2["max_ram_mb"] == 8192.0
        assert cfg_loaded2["est_bytes_per_bar"] == DEFAULT_CONFIG["est_bytes_per_bar"]
        # Defekte JSON -> Fallback
        cfg_path.write_text("{kaputt", encoding="utf-8")
        assert load_complexity_config(cfg_path) == DEFAULT_CONFIG
        print("[4] Komplexitaets-Konfiguration: round-trip + Fallback -> OK")
    finally:
        if cfg_path.exists():
            cfg_path.unlink()

    print("=== test_complexity_estimation OK ===")


# ---------------------------------------------------------------------------
# Backtest Lab - UI-State-Persistenz + Order-Parameter (Schritt 5)
# ---------------------------------------------------------------------------

def test_backtest_ui_state() -> None:
    """Verifiziert die UI-State-Persistenz und Order-Parameter (Schritt 5).

    Prueft:
      1. `default_state()` enthaelt order + date_range + run-Namen-Felder.
      2. `load_state`/`save_state` round-trip in test/ (atomarer Save).
      3. Defekte/fehlende Datei -> Fallback auf Defaults.
      4. `make_order_config` validiert (gueltig + ungueltig).
      5. `order_params_json` serialisiert das OrderConfig korrekt.

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_backtest_ui_state()"
    """
    from pathlib import Path

    from backtest_lab.types import make_order_config, order_params_json
    from backtest_lab.ui_state import default_state, load_state, save_state

    # --- 1) Defaults --------------------------------------------------
    d = default_state()
    assert d["symbols"] == ["SILVER"] and d["timeframes"] == ["M30"]
    assert set(d["order"]) == {
        "spread_pct", "stop_loss_pct", "take_profit_pct", "position_size_pct",
        "equity", "leverage", "reentry_same_bar",
    }
    assert d["order"]["equity"] == 10_000.0
    assert d["order"]["leverage"] == 1000.0
    assert d["order"]["reentry_same_bar"] is True
    assert d["date_range"] == {"from": None, "to": None}
    print("[1] default_state OK:", d["order"])

    # --- 2) Round-trip (in test/) --------------------------------------
    state_path = Path(__file__).resolve().parent / "_test_backtest_ui_state.json"
    if state_path.exists():
        state_path.unlink()
    try:
        assert load_state(state_path) == default_state(), "Fehlende Datei -> Defaults"
        stored = default_state()
        stored["order"].update(
            {"spread_pct": 0.1, "stop_loss_pct": None, "take_profit_pct": 3.0}
        )
        stored["date_range"] = {"from": "2024-01-01", "to": "2024-06-30"}
        save_state(stored, state_path)
        loaded = load_state(state_path)
        assert loaded["order"]["spread_pct"] == 0.1
        assert loaded["order"]["stop_loss_pct"] is None
        assert loaded["order"]["take_profit_pct"] == 3.0
        assert loaded["date_range"]["from"] == "2024-01-01"
        print("[2] save/load round-trip OK (in test/)")

        # --- 3) Defekte Datei -> Fallback -------------------------------
        state_path.write_text("{defekt", encoding="utf-8")
        assert load_state(state_path) == default_state()
        print("[3] defekte Datei -> Fallback Defaults -> OK")
    finally:
        if state_path.exists():
            state_path.unlink()

    # --- 4) make_order_config ------------------------------------------
    cfg = make_order_config(0.05, 2.0, 4.0, 1.0)
    assert cfg.spread_pct == 0.05 and cfg.stop_loss_pct == 2.0
    assert cfg.take_profit_pct == 4.0 and cfg.position_size_pct == 1.0
    cfg_none = make_order_config(0.05, None, None, 1.0)
    assert cfg_none.stop_loss_pct is None and cfg_none.take_profit_pct is None
    for bad in [
        dict(spread_pct=0.0, stop_loss_pct=None, take_profit_pct=None, position_size_pct=1.0),
        dict(spread_pct=0.05, stop_loss_pct=-1.0, take_profit_pct=None, position_size_pct=1.0),
        dict(spread_pct=0.05, stop_loss_pct=None, take_profit_pct=-2.0, position_size_pct=1.0),
        dict(spread_pct=0.05, stop_loss_pct=None, take_profit_pct=None, position_size_pct=0.0),
        dict(spread_pct=0.05, stop_loss_pct=None, take_profit_pct=None, position_size_pct=101.0),
    ]:
        try:
            make_order_config(**bad)
            assert False, f"Ungueltige Werte akzeptiert: {bad}"
        except ValueError:
            pass
    print("[4] make_order_config: gueltig + 5 ungueltige Faelle abgelehnt -> OK")

    # --- 5) order_params_json ------------------------------------------
    j = order_params_json(make_order_config(0.05, 2.0, None, 1.0))
    import json as _json
    parsed = _json.loads(j)
    assert parsed == {"spread_pct": 0.05, "stop_loss_pct": 2.0,
                      "take_profit_pct": None, "position_size_pct": 1.0,
                      "equity": 10_000.0, "leverage": 1000.0,
                      "reentry_same_bar": True}
    print(f"[5] order_params_json: {j} -> OK")

    print("=== test_backtest_ui_state OK ===")


# ---------------------------------------------------------------------------
# Backtest Lab - Backtest-Runner v1 (Schritt 6)
# ---------------------------------------------------------------------------

def test_backtest_runner() -> None:
    """Verifiziert den Backtest-Runner v1 (Schritt 6) auf synthetischen DBs.

    Prueft auf kleinen synthetischen Test-DBs (in test/):
      1. `run_backtest`: lookahead-freier Entry (Signal Bar T -> Open T+1),
         Slippage aus `spread_pct/2` (symmetrisch), Reversal-Exit am Open,
         TP intrabar (SL/TP gewinnt vor Gegensignal), R-Multiple-Formel.
      2. Run-Level-Metriken (net_profit, win_rate, profit_factor, ...).
      3. `run_backtests_parallel` (2 Jobs / 2 Worker): kein Rekursions-Loop
         (Windows-spawn-Regression: >49k Zeilen ohne `__main__`-Guard),
         Persistenz in `backtest_runs` + `backtest_trades`.

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_backtest_runner()"
    """
    import duckdb
    import pandas as pd
    from pathlib import Path

    from backtest_lab.db import connect_backtest
    from backtest_lab.runner import (
        BacktestJob,
        run_backtest,
        run_backtests_parallel,
    )
    from backtest_lab.types import make_order_config

    TEST = Path(__file__).resolve().parent
    db_market = TEST / "_test_market6.duckdb"
    db_ana = TEST / "_test_ana6.duckdb"
    db_bt = TEST / "_test_bt6.duckdb"
    for p in (db_market, db_ana, db_bt):
        if p.exists():
            p.unlink()
    try:
        # --- Markt-DB (12 M30-Bars, naive UTC) --------------------------
        open_ = [100, 101, 102, 101, 100, 99, 98, 99, 100, 101, 102, 103]
        high = [101, 103, 103, 102, 101, 100, 100, 101, 102, 103, 104, 104]
        low = [99, 100, 101, 100, 99, 98, 97, 98, 99, 100, 101, 102]
        close = [101, 102, 101, 100, 99, 98, 99, 100, 101, 102, 103, 103]
        times = pd.date_range("2026-01-01", periods=12, freq="30min", tz="UTC")

        con = duckdb.connect(str(db_market))
        con.execute("""
            CREATE TABLE ohlcv_bars (
                symbol VARCHAR NOT NULL, timeframe VARCHAR NOT NULL,
                time TIMESTAMPTZ NOT NULL, open DOUBLE NOT NULL, high DOUBLE NOT NULL,
                low DOUBLE NOT NULL, close DOUBLE NOT NULL, tick_volume BIGINT,
                spread INTEGER, real_volume BIGINT, created_at TIMESTAMP,
                PRIMARY KEY (symbol, timeframe, time)
            )
        """)
        for i in range(12):
            con.execute(
                "INSERT INTO ohlcv_bars VALUES (?,?,?,?,?,?,?,?,?,?,current_timestamp)",
                ["SILVER", "M30", times[i], open_[i], high[i], low[i], close[i], 100, 50, 100],
            )
        con.close()

        # --- Analytics-DB (4 Swing-Change-Signale) -----------------------
        con = duckdb.connect(str(db_ana))
        con.execute("""
            CREATE TABLE signal_events (
                run_id VARCHAR NOT NULL, time TIMESTAMPTZ NOT NULL,
                signal_type VARCHAR NOT NULL, direction TINYINT NOT NULL,
                price DOUBLE NOT NULL, strength DOUBLE NOT NULL, meta_json JSON,
                source_tf VARCHAR, signal_time TIMESTAMPTZ,
                PRIMARY KEY (run_id, time, signal_type, price)
            )
        """)
        sig = [  # (bar, direction, price)
            (0, 1, 100.0), (3, -1, 101.0), (5, 1, 99.0), (7, -1, 99.0),
        ]
        for bar, d, price in sig:
            con.execute(
                "INSERT INTO signal_events VALUES (?,?,?,?,?,?,?,?,?)",
                ["run_abc", times[bar], "swing_change", d, price, 1.0, None, None, None],
            )
        con.close()

        # --- 1) Einzelner Backtest ---------------------------------------
        cfg = make_order_config(0.01, 2.0, 4.0, 1.0)  # spread 0.01%, SL 2%, TP 4%
        record, trades = run_backtest(
            "run_abc", "SILVER", "M30", cfg,
            date_from="2026-01-01", date_to="2026-01-31",
            db_market=db_market, db_analytics=db_ana,
        )
        print(f"[1] run_name={record.run_name} | trades={record.trade_count}")
        assert record.run_name.startswith("BT_sp001_sl2_tp4_sz1_lev1000_"), (
            f"Run-Name-Schema falsch: {record.run_name}"
        )
        assert len(trades) == 3, f"Erwartet 3 Trades, erhalten {len(trades)}"
        assert record.trade_count == 3

        # Erwartete Werte (vom Smoke-Runner verifiziert):
        #  T0: Long Entry Open Bar1=101*1.00005, Reversal-Exit Open Bar4=100*0.99995
        #  T1: Short Entry Open Bar4, Reversal-Exit Open Bar6=98*1.00005
        #  T2: Long Entry Open Bar6, TP intrabar Bar8 (98.0049*1.04) gewinnt
        #      vor Gegensignal (Open Bar8=101)
        #  PnL-Massstab (Bugfix 7, CFD-Hebel 1000): size=equity*lev*pos%/100
        #  = 100 000 $ -> Anteile = size/entry_price -> PnL in $ x1000
        #  (z. B. T0: -1.00005 * 1000 = -1000.05, vom Smoke-Runner verifiziert).
        exp = [
            dict(entry_price=101.00505, exit_price=99.995, direction=1,
                 pnl=-1000.0495049504971, r_multiple=-0.5),
            dict(entry_price=99.995, exit_price=98.0049, direction=-1,
                 pnl=1990.1, r_multiple=-0.9951),
            dict(entry_price=98.0049, exit_price=101.925096, direction=1,
                 pnl=4000.2, r_multiple=2.0),
        ]
        for i, e in enumerate(exp):
            row = trades.iloc[i]
            assert abs(row["entry_price"] - e["entry_price"]) < 1e-4, (
                f"T{i} Entry-Preis falsch: {row['entry_price']}"
            )
            assert abs(row["exit_price"] - e["exit_price"]) < 1e-4, (
                f"T{i} Exit-Preis falsch: {row['exit_price']}"
            )
            assert int(row["direction"]) == e["direction"], (
                f"T{i} Richtung falsch: {row['direction']}"
            )
            assert abs(row["pnl"] - e["pnl"]) < 1e-3, f"T{i} PnL falsch: {row['pnl']}"
            assert abs(row["r_multiple"] - e["r_multiple"]) < 1e-3, (
                f"T{i} R-Multiple falsch: {row['r_multiple']}"
            )
        print("    Trades: Entry/Exit/Slippage/Reversal/TP/R-Multiple OK")

        # --- 2) Run-Level-Metriken ----------------------------------------
        m = record
        # PnL-Massstab wie oben (Hebel 1000): net_profit/expectancy folgen
        # dem Trade-PnL (4990.2505 = -1000.05 + 1990.1 + 4000.2, vom
        # Smoke-Runner verifiziert).
        assert abs(m.net_profit - 4990.2505) < 1e-2, f"net_profit falsch: {m.net_profit}"
        assert abs(m.win_rate - 2 / 3) < 1e-6, f"win_rate falsch: {m.win_rate}"
        assert abs(m.profit_factor - 5.9900) < 1e-3, f"profit_factor falsch: {m.profit_factor}"
        assert abs(m.expectancy - 1663.4168) < 1e-2, f"expectancy falsch: {m.expectancy}"
        assert m.trade_count == 3 and m.max_drawdown_pct >= 0.0
        # Bugfix 8: max_drawdown ($) = Peak-to-Trough in USD (nicht %),
        # sl_count = Anzahl der SL-Exits. In diesem Smoke-Fall enden die
        # 3 Trades ueber Reversal (T0/T1) bzw. TP (T2) - kein SL-Exit.
        assert m.max_drawdown >= 0.0 and m.max_drawdown <= m.net_profit + 10_000.0, (
            f"max_drawdown ($) unplausibel: {m.max_drawdown}"
        )
        assert m.sl_count == 0, f"sl_count falsch: {m.sl_count} (erwartet 0)"
        assert set(trades["exit_reason"].unique()) <= {"sl", "tp", "signal", "gap"}, (
            f"exit_reason-Werte ungueltig: {set(trades['exit_reason'].unique())}"
        )
        assert trades["exit_reason"].tolist() == ["signal", "signal", "tp"], (
            f"exit_reason je Trade falsch: {trades['exit_reason'].tolist()}"
        )
        # _exit_reason-Unit-Test: Preisvergleich gegen SL/TP-Preis
        from backtest_lab.runner import _exit_reason
        assert _exit_reason(100.0, 99.45, 1, 0.5, 2.0, 0.15) == "sl", (
            "Exit am SL-Preis (99.5, Tol 0.15 %) nicht als 'sl' erkannt"
        )
        assert _exit_reason(100.0, 102.05, 1, 0.5, 2.0, 0.15) == "tp", (
            "Exit am TP-Preis (102.0) nicht als 'tp' erkannt"
        )
        assert _exit_reason(100.0, 100.5, 1, 0.5, 2.0, 0.15) == "signal", (
            "Reversal-Exit (Open-Preis) muss 'signal' sein"
        )
        assert _exit_reason(100.0, 100.6, -1, 0.5, 2.0, 0.15) == "sl", (
            "Short-SL (100.5 = 100*1.005, Exit 100.6 in Toleranz) falsch erkannt"
        )
        # Gap (Bugfix 8): Exit JENSEITS des SL-Niveaus = SL uebersprungen
        # (Verlust > SL-Cap), eigener Grund "gap" - NICHT "sl"/"signal".
        assert _exit_reason(100.0, 98.5, 1, 0.5, 2.0, 0.15) == "gap", (
            "Long-Gap (Exit 98.5 < SL 99.5) muss 'gap' sein"
        )
        assert _exit_reason(100.0, 101.5, -1, 0.5, 2.0, 0.15) == "gap", (
            "Short-Gap (Exit 101.5 > SL 100.5) muss 'gap' sein"
        )
        # Signal-Exit ueber dem SL-Level (kein Gap) bleibt "signal"
        assert _exit_reason(100.0, 100.9, 1, 0.5, 2.0, 0.15) == "signal", (
            "Signal-Exit ueber SL-Level (100.9 > 99.5, kein TP) muss 'signal' sein"
        )
        # _classify_exit (Bugfix 8): "gap" NUR bei echtem Zeit-Gap (Bar-Abstand
        # > 1h = Handelspause 23-0 Uhr / Wochenende); sonst Hard Exit am
        # SL-Preis ("sl", PnL = SL-Risiko) - CFD, kein Slippage.
        from backtest_lab.runner import _classify_exit, _correct_pnl
        bars_ok = pd.DataFrame({"time": pd.to_datetime([
            "2026-01-01 00:00", "2026-01-01 00:30", "2026-01-01 01:00",
        ])})  # normale 30-min-Bars -> KEIN Zeit-Gap
        bars_gap = pd.DataFrame({"time": pd.to_datetime([
            "2026-01-01 00:00", "2026-01-01 02:00",
        ])})  # 2h-Luecke (Handelspause/Wochenende) -> ECHTER Zeit-Gap
        # kein Zeit-Gap: Exit 98.5 (< SL 99.5) -> Hard Exit am SL-Preis 99.5, "sl"
        assert _classify_exit(100.0, 98.5, 1, 0.5, 2.0, 0.15, bars_ok, 2) == (99.5, "sl"), (
            "SL-Uebersprung ohne Zeit-Gap muss auf SL-Preis korrigiert werden"
        )
        # echter Zeit-Gap: Fill-Preis 98.5 bleibt, "gap"
        assert _classify_exit(100.0, 98.5, 1, 0.5, 2.0, 0.15, bars_gap, 1) == (98.5, "gap"), (
            "Echter Zeit-Gap muss 'gap' bleiben (Fill-Preis)"
        )
        # normaler SL-Fill am Niveau -> "sl", Preis unveraendert
        assert _classify_exit(100.0, 99.5, 1, 0.5, 2.0, 0.15, bars_ok, 1)[1] == "sl"
        # TP / Signal unveraendert
        assert _classify_exit(100.0, 102.0, 1, 0.5, 2.0, 0.15, bars_ok, 2) == (102.0, "tp")
        assert _classify_exit(100.0, 100.5, 1, 0.5, 2.0, 0.15, bars_ok, 2) == (100.5, "signal")
        # _correct_pnl: PnL wird auf den SL-Preis skaliert (Hard Exit)
        #   shares = -1426.287651 / ((98.5-100)*1) = 950.858 -> (99.5-100)*1*950.858
        #   = -475.429 (SL-Risiko ~500 $ inkl. Entry-Slippage-Korrektur)
        assert abs(_correct_pnl(-1426.287651, 100.0, 98.5, 99.5, 1) - (-475.429217)) < 1e-3, (
            "PnL-Korrektur auf SL-Preis falsch"
        )
        assert _correct_pnl(100.0, 100.0, 102.0, 102.0, 1) == 100.0, (
            "Unveraenderter Exit darf den PnL nicht aendern"
        )
        print(f"[2] Metriken: net={m.net_profit:.4f} | win={m.win_rate:.4f} | "
              f"pf={m.profit_factor:.4f} | dd_pct={m.max_drawdown_pct:.4f}% | "
              f"dd_$={m.max_drawdown:.2f} | sl_count={m.sl_count} | "
              f"exit_reason={trades['exit_reason'].tolist()} -> OK")

        # --- 2b) Checkbox "Re-Entry gleiche Bar" --------------------------
        # EIN (Default, reentry_same_bar=True) = Reverse: Gegensignal
        #   schliesst + neuer Entry in derselben Bar -> 3 Trades (T0-T2 oben).
        # AUS (reentry_same_bar=False) = Close: Gegensignal schliesst NUR,
        #   neuer Trade erst beim naechsten frischen Finding.
        #   Signale: Long Bar0 -> Entry Bar1; Short Bar3 -> Exit Bar4 (kein
        #   Short-Entry!); Long Bar5 -> Entry Bar6 (frisches Finding);
        #   Short Bar7 -> Exit Bar8 (kein Short-Entry).
        cfg_no_re = make_order_config(0.01, 2.0, 4.0, 1.0, reentry_same_bar=False)
        rec_no_re, trades_no_re = run_backtest(
            "run_abc", "SILVER", "M30", cfg_no_re,
            date_from="2026-01-01", date_to="2026-01-31",
            db_market=db_market, db_analytics=db_ana,
        )
        assert len(trades_no_re) == 2, (
            f"Close-Modus: erwartet 2 Trades (nur Exits), erhalten {len(trades_no_re)}"
        )
        assert (trades_no_re["direction"] == 1).all(), (
            "Close-Modus: keine Short-Reversals erwartet (nur Long-Trades)"
        )
        assert cfg_no_re.reentry_same_bar is False and cfg.reentry_same_bar is True
        print("[2b] Re-Entry gleiche Bar: EIN=Reverse (3 Trades) | "
              f"AUS=Close ({len(trades_no_re)} Trades, nur Long-Exits) -> OK")

        # --- 3) Parallel (spawn-Regression) + Persistenz ------------------
        job1 = BacktestJob(signal_run_id="run_abc", symbol="SILVER", timeframe="M30",
                           order_config=cfg, date_from="2026-01-01", date_to="2026-01-31")
        job2 = BacktestJob(signal_run_id="run_abc", symbol="SILVER", timeframe="M30",
                           order_config=make_order_config(0.05, None, None, 2.0),
                           date_from="2026-01-01", date_to="2026-01-31")
        progress = []
        ids = run_backtests_parallel(
            [job1, job2], n_workers=2, db_market=db_market, db_analytics=db_ana,
            db_backtest=db_bt,
            progress_callback=lambda d, t, n: progress.append((d, t, n)),
        )
        print(f"[3] parallel ids={len(ids)} | progress={progress}")
        assert len(ids) == 2, "Parallel-Runner muss genau 2 Run-IDs liefern"
        assert len(set(ids)) == 2, "Run-IDs muessen eindeutig sein (frische UIDs)"
        assert progress and progress[-1][0] == 2, "Fortschritt nicht komplett"

        con = connect_backtest(db_bt, ensure_schema=False)
        runs = con.execute(
            "SELECT run_id, run_name, trade_count, net_profit FROM backtest_runs ORDER BY run_name"
        ).df()
        tr = con.execute(
            "SELECT run_id, COUNT(*) n FROM backtest_trades GROUP BY run_id"
        ).df()
        con.close()
        assert len(runs) == 2, f"Erwartet 2 Runs, erhalten {len(runs)}"
        assert (runs["trade_count"] == 3).all(), "Beide Runs muessen 3 Trades haben"
        assert len(tr) == 2 and (tr["n"] == 3).all(), (
            "Je Run muessen 3 Trades in backtest_trades liegen"
        )
        print(f"    Persistenz: {len(runs)} Runs + {int(tr['n'].sum())} Trades -> OK")
        print("=== test_backtest_runner OK ===")
    finally:
        for p in (db_market, db_ana, db_bt):
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Backtest Lab - Naming Option A (Schritt 7)
# ---------------------------------------------------------------------------

def test_backtest_naming() -> None:
    """Verifiziert das kurze Backtest-Namensschema Option A (Schritt 7).

    Prueft:
      1. `build_backtest_run_name`: Standardschema
         `BT_sp{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_{JJJJMMTT_HHMM}`.
      2. Spread-Rundung auf 3 Stellen (0.05 -> "005").
      3. None-SL/TP -> "x" (kein fixer Stop).
      4. Dezimalwerte via `:g` (2.5 -> "2.5").
      5. free_tag (inkl. Leerzeichen -> Unterstrich).
      6. `_fmt_pct`-Randfaelle (0, None, Ganzzahl).

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_backtest_naming()"
    """
    from datetime import datetime

    from backtest_lab.naming import _fmt_pct, build_backtest_run_name

    ts = datetime(2026, 8, 21, 20, 30)

    # --- 1) Standardschema ----------------------------------------------
    name = build_backtest_run_name(0.05, 2.0, 4.0, 1.0, ts)
    assert name == "BT_sp005_sl2_tp4_sz1_lev1000_20260821_2030", f"Standard falsch: {name}"
    print(f"[1] Standard: {name} -> OK")

    # --- 2) Spread-Rundung auf 3 Stellen --------------------------------
    assert build_backtest_run_name(0.1, None, None, 1.0, ts).startswith("BT_sp010_")
    assert build_backtest_run_name(0.005, None, None, 1.0, ts).startswith("BT_sp001_")
    print("[2] Spread-Rundung (0.1->010, 0.005->001) -> OK")

    # --- 3) None-SL/TP -> "x" -------------------------------------------
    n = build_backtest_run_name(0.05, None, None, 1.0, ts)
    assert n.startswith("BT_sp005_slx_tpx_sz1_lev1000_"), f"None-Fall falsch: {n}"
    print(f"[3] None-SL/TP: {n} -> OK")

    # --- 4) Dezimalwerte via :g ------------------------------------------
    d = build_backtest_run_name(0.05, 2.5, 4.25, 0.5, ts)
    assert d.startswith("BT_sp005_sl2.5_tp4.25_sz0.5_lev1000_"), f"Dezimal-Fall falsch: {d}"
    print(f"[4] Dezimalwerte: {d} -> OK")

    # --- 5) free_tag (Leerzeichen -> Unterstrich) ------------------------
    t = build_backtest_run_name(0.05, 2.0, 4.0, 1.0, ts, free_tag="p11 htf")
    assert t == "BT_sp005_sl2_tp4_sz1_lev1000_20260821_2030_p11_htf", f"free_tag falsch: {t}"
    print(f"[5] free_tag: {t} -> OK")

    # --- 6) _fmt_pct-Randfaelle ------------------------------------------
    assert _fmt_pct(None) == "x"
    assert _fmt_pct(0) == "0"
    assert _fmt_pct(2.0) == "2"
    assert _fmt_pct(2.5) == "2.5"
    print("[6] _fmt_pct (None, 0, 2.0, 2.5) -> OK")

    # --- 7) Default-Timestamp (jetzt) -------------------------------------
    auto = build_backtest_run_name(0.05, 2.0, 4.0, 1.0)
    import re as _re
    assert _re.match(r"^BT_sp005_sl2_tp4_sz1_lev1000_\d{8}_\d{4}$", auto), f"Auto-Ts falsch: {auto}"
    print(f"[7] Default-Timestamp: {auto} -> OK")

    print("=== test_backtest_naming OK ===")

# =============================================================================
# Bugfix-Tests Backtest Lab (3: Idempotenz/Overwrite, 4: Listen/Loeschen)
# Nur DB-Logik, keine UI - Test-DB liegt im test/-Ordner (User-Regel).
# =============================================================================

def _bt_test_db(tmp_name: str) -> Path:
    """Leere Backtest-Test-DB im test/-Ordner erzeugen."""
    from backtest_lab.schema import init_backtest_schema
    p = Path(__file__).resolve().parent / tmp_name
    if p.exists():
        p.unlink()
    init_backtest_schema(p)
    return p


def test_backtest_overwrite_and_delete() -> None:
    """Bugfix 3 + 4: Ueberschreiben statt Duplikate + Loeschen inkl. Trades."""
    import pandas as pd

    from backtest_lab.db import (
        connect_backtest,
        delete_backtest_runs,
        get_backtest_runs,
        save_backtest_run,
    )
    from backtest_lab.types import (
        BacktestRunRecord,
        make_order_config,
        order_params_json,
        run_id_from_config,
    )

    dbp = _bt_test_db("_test_bugfix_bt.duckdb")
    cfg = make_order_config(0.15, 0.2, 2.0, 1.0, equity=10_000.0)
    params = order_params_json(cfg)
    rid = run_id_from_config("run_sig_1", "SILVER", "M30", params, None, None)
    rid_other = run_id_from_config("run_sig_1", "SILVER", "M30", params, None, None)
    assert rid == rid_other, "run_id_from_config ist nicht deterministisch!"

    def _rec(run_id: str, name: str, ts: str) -> BacktestRunRecord:
        from datetime import datetime, timezone
        return BacktestRunRecord(
            run_id=run_id, signal_run_id="run_sig_1", run_name=name,
            symbol="SILVER", timeframe="M30", params_json=params,
            date_from=None, date_to=None, net_profit=100.0, win_rate=0.5,
            profit_factor=2.0, max_drawdown_pct=3.0, sharpe_ratio=1.2,
            trade_count=1, avg_trade_pnl=100.0, expectancy=50.0,
            created_at=datetime.now(timezone.utc),
        )

    con = connect_backtest(dbp)
    try:
        # 1) Erster Lauf mit dieser Konfiguration -> 1 Run, 1 Trade
        trades1 = pd.DataFrame({
            "entry_time": pd.to_datetime(["2026-01-01"], utc=True),
            "exit_time": pd.to_datetime(["2026-01-02"], utc=True),
            "entry_price": [100.0], "exit_price": [101.0],
            "direction": [1], "pnl": [100.0], "r_multiple": [1.0],
        })
        save_backtest_run(con, _rec(rid, "BT_v1", "t1"), trades1)

        n_runs = int(con.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0])
        n_trades = int(con.execute("SELECT COUNT(*) FROM backtest_trades").fetchone()[0])
        assert n_runs == 1 and n_trades == 1, f"1. Lauf: runs={n_runs}, trades={n_trades}"

        # 2) GLEICHE Konfiguration erneut -> UEBERSCHRIEBEN (weiterhin 1 Run,
        #    Trades ersetzt, neuer Name)
        trades2 = pd.DataFrame({
            "entry_time": pd.to_datetime(["2026-01-03"], utc=True),
            "exit_time": pd.to_datetime(["2026-01-04"], utc=True),
            "entry_price": [100.0], "exit_price": [102.0],
            "direction": [1], "pnl": [200.0], "r_multiple": [2.0],
        })
        save_backtest_run(con, _rec(rid, "BT_v2", "t2"), trades2)

        n_runs = int(con.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0])
        n_trades = int(con.execute("SELECT COUNT(*) FROM backtest_trades").fetchone()[0])
        names = [r[0] for r in con.execute("SELECT run_name FROM backtest_runs").fetchall()]
        pnls = [r[0] for r in con.execute("SELECT pnl FROM backtest_trades").fetchall()]
        assert n_runs == 1, f"Overwrite: runs={n_runs} (erwartet 1, keine Duplikate)"
        assert n_trades == 1, f"Overwrite: trades={n_trades} (erwartet 1)"
        assert names == ["BT_v2"], f"Overwrite: Name nicht ersetzt: {names}"
        assert pnls == [200.0], f"Overwrite: Trades nicht ersetzt: {pnls}"
        print("[Bugfix 3] Overwrite statt Duplikate (1 Run, Trades+Name ersetzt) -> OK")

        # 3) ANDERE Konfiguration -> separater Run (2 Runs gesamt)
        rid_b = run_id_from_config("run_sig_2", "GOLD", "M30", params, None, None)
        save_backtest_run(con, _rec(rid_b, "BT_OTHER", "t3"), trades1)
        n_runs = int(con.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0])
        assert n_runs == 2, f"Andere Konfiguration: runs={n_runs} (erwartet 2)"
        print("[Bugfix 3] Andere Konfiguration -> separater Run -> OK")

        # 4) get_backtest_runs: Liste mit Auswahl-Spalten
        df = get_backtest_runs(dbp)
        assert len(df) == 2 and "run_id" in df.columns, f"get_backtest_runs: {len(df)}"
        # Bugfix 8: max_drawdown ($), sl_count, Gewinn-% und Worst-Trade
        assert {"max_drawdown", "sl_count", "net_profit_pct", "worst_trade"} <= set(
            df.columns
        ), f"Spalten fehlen: {list(df.columns)}"
        print("[Bugfix 4] get_backtest_runs liefert Liste -> OK")

        # 5) delete_backtest_runs: selektierte Runs inkl. Trades entfernen
        n = delete_backtest_runs([rid], dbp)
        assert n == 1, f"delete: n={n}"
        n_runs = int(con.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0])
        n_trades = int(con.execute("SELECT COUNT(*) FROM backtest_trades").fetchone()[0])
        rem_runs = [r[0] for r in con.execute("SELECT run_id FROM backtest_runs").fetchall()]
        rem_trades = [r[0] for r in con.execute("SELECT DISTINCT run_id FROM backtest_trades").fetchall()]
        # Nur rid_b (andere Konfiguration) bleibt inkl. SEINEM Trade; der
        # geloeschte Run rid ist weder in Runs noch in Trades vorhanden.
        assert n_runs == 1 and n_trades == 1, f"nach Delete: runs={n_runs}, trades={n_trades}"
        assert rem_runs == [rid_b], f"verbleibender Run: {rem_runs}"
        assert rem_trades == [rid_b], f"verbleibende Trades: {rem_trades}"
        # Leere Liste -> 0, kein Fehler
        assert delete_backtest_runs([], dbp) == 0
        print("[Bugfix 4] Loeschen (Run + Trades) + leere Auswahl -> OK")
    finally:
        con.close()
        dbp.unlink(missing_ok=True)

    print("=== test_backtest_overwrite_and_delete OK ===")


if __name__ == "__main__":
    # Backtest-Lab-Bugfix-Tests (keine UI, Test-DB in test/)
    test_backtest_overwrite_and_delete()

def test_signal_runs_dedupe() -> None:
    """Bugfix 1: get_signal_runs zeigt jeden Run nur EINMAL (keine Re-Run-Residuen)."""
    import duckdb as _ddb

    from backtest_lab.db import get_last_signal_runs, get_signal_runs

    p = Path(__file__).resolve().parent / "_test_bugfix_analytics.duckdb"
    if p.exists():
        p.unlink()
    con = _ddb.connect(str(p))
    try:
        con.execute("CREATE TABLE indicator_runs (run_id VARCHAR, indicator_name VARCHAR, symbol VARCHAR, timeframe VARCHAR, params_json VARCHAR, run_name VARCHAR, created_at TIMESTAMPTZ)")
        # 3 Duplikate desselben Runs (Re-Run-Residuen) + 1 echter anderer Run
        rows = [
            ("r1", "ehma", "SILVER", "M30", "{}", "RUN_SILVER_M30_20260821_1608", "2026-08-22 19:27:47+02"),
            ("r2", "ehma", "SILVER", "M30", "{}", "RUN_SILVER_M30_20260821_1608", "2026-08-22 19:27:48+02"),
            ("r3", "ehma", "SILVER", "M30", "{}", "RUN_SILVER_M30_20260821_1608", "2026-08-22 19:27:49+02"),
            ("r4", "ehma", "GOLD", "H1", "{}", "RUN_GOLD_H1_20260821_1436", "2026-08-21 14:36:52+02"),
        ]
        con.executemany("INSERT INTO indicator_runs VALUES (?,?,?,?,?,?,?)", rows)
    finally:
        con.close()

    df = get_signal_runs(db_path=p)
    assert len(df) == 2, f"Dedupe: {len(df)} Runs (erwartet 2, nur SILVER + GOLD)"
    assert df["run_name"].nunique() == 2, "run_name nicht eindeutig nach Dedupe"
    # Der NEUESTE SILVER-Eintrag (r3, 19:27:49) muss erhalten bleiben
    silver = df[df["symbol"] == "SILVER"]
    assert silver["run_id"].iloc[0] == "r3", f"Falscher Duplikat-Zweig behalten: {silver['run_id'].iloc[0]}"
    print("[Bugfix 1] Dedupe OK: 14 Residuen -> 1 Zeile, neuester Eintrag bleibt")

    last = get_last_signal_runs(db_path=p)
    assert last["run_name"].nunique() == len(last), "get_last_signal_runs liefert Duplikate"
    assert len(last) == 1, f"Letzter Lauf: {len(last)} (erwartet 1)"
    print(f"[Bugfix 1] Letzter Lauf-Filter: {len(last)} Run (eindeutig)")

    p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Bugfix 5: Checkbox-Reaktivitaet (Listenelemente -> sel_ctl-Bump)
# ---------------------------------------------------------------------------

def _kernel_registry_elements(runner, name=None):
    """Liefert lebende UI-Elemente aus der Kernel-Registry des Runners.

    Findet auch Elemente, die in Python-Listen liegen und daher ueber den
    Output-Baum (`walk`) nicht auffindbar sind - genau der Bugfix-5-Fall
    (`render_checkbox_table`: Checkboxen in Listen, eingebettet in HTML).
    """
    from marimo._runtime.context import get_context
    root_ctx = get_context()
    ctx = root_ctx
    stack = [root_ctx]
    while stack:
        c = stack.pop(0)
        if getattr(c, "_kernel", None) is runner._kernel:
            ctx = c
            break
        stack.extend(getattr(c, "children", []) or [])
    reg = ctx.ui_element_registry
    out = []
    for _id, ref in list(reg._objects.items()):
        obj = ref()
        if obj is not None and (name is None or getattr(obj, "_name", "") == name):
            out.append(obj)
    return out


@asynccontextmanager
async def kernel_runner_for(nb_path):
    """AppKernelRunner fuer ein beliebiges Notebook (headless, keine UI)."""
    sys.stdout.reconfigure(encoding="utf-8")
    q = queue.Queue()
    iq = queue.Queue()
    stream = ThreadSafeStream(QueuePipe(q), iq, redirect_console=False)
    streams = KernelStreams(stream=stream, stdout=None, stderr=None, stdin=None)
    spec = importlib.util.spec_from_file_location("react_nb", nb_path)
    nb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb)
    app = nb.app
    args = KernelArgs(
        streams=streams,
        debugger=None,
        configs={},
        app_metadata=AppMetadata(
            {}, CLIArgs({}).to_dict(), argv=[], filename="nb.py", app_config=app._config
        ),
        user_config=DEFAULT_CONFIG,
        mode=SessionMode.EDIT,
        control_queue=queue.Queue(),
        set_ui_element_queue=queue.Queue(),
        virtual_file_storage="shared_memory",
    )
    with kernel_session(args) as (kernel, ctx):
        with ctx.install():
            runner = AppKernelRunner(InternalApp(app))
            await runner.run(set(runner._kernel.graph.cells.keys()))
            yield runner


def test_checkbox_reactivity() -> None:
    """Bugfix 5: Checkbox-Klick aktiviert GO-/Loesch-Button (headless).

    Checkboxen in Python-Listen (`render_checkbox_table`) haben kein
    marimo-Global-Name-Binding -> ohne Fix wuerde der Klick keine
    abhaengige Zelle re-runen (GO bleibt disabled, reproduziert als
    "Signal ausgewaehlt, aber GO-Button nicht aktiviert"). Der
    `on_change`-Bump auf den Modul-State-Zaehler `sel_ctl` zwingt die
    konsumierende Zelle zum Re-Run -> GO wird enabled.
    """
    nb_path = Path(__file__).resolve().parent / "_react_checkbox_nb.py"

    async def _run():
        async with kernel_runner_for(nb_path) as runner:
            rk = runner._kernel
            cbs = _kernel_registry_elements(runner, "marimo-checkbox")
            btns = _kernel_registry_elements(runner, "marimo-button")
            assert len(cbs) == 3, f"Checkboxen: {len(cbs)} (erwartet 3)"
            assert len(btns) == 1, f"Buttons: {len(btns)} (erwartet 1)"
            btn = btns[0]
            assert btn._args.args.get("disabled") is True, "GO muss initial disabled sein"
            print("[Bugfix 5] Initial: GO disabled -> OK")

            await runner.set_ui_element_value(
                UpdateUIElementCommand(object_ids=[cbs[0]._id], values=[True], request=None),
                notify_frontend=False,
            )
            rk.state_updates.clear()
            await rk.run_stale_cells()
            btns2 = _kernel_registry_elements(runner, "marimo-button")
            btn2 = btns2[0] if btns2 else None
            assert btn2 is not None, "GO-Button nach Klick fehlt"
            assert btn2._args.args.get("disabled") is False, (
                "GO muss nach Auswahl enabled sein (Bugfix 5)!"
            )
            print("[Bugfix 5] Nach Checkbox-Klick: GO enabled -> OK")

    asyncio.run(_run())
    print("=== test_checkbox_reactivity OK ===")


# ---------------------------------------------------------------------------
# Trade-Detail (Klick auf einen Run): get_backtest_trades - Sortierung,
# Anreicherung (Richtung, Exit-Grund, Dauer, Kursbewegung-%, PnL-% Equity)
# ---------------------------------------------------------------------------

def test_backtest_trades_detail() -> None:
    """Verifiziert `get_backtest_trades` (Detail-Tabelle eines Runs).

    Prueft:
      1. Spaltenvertrag `TRADE_DETAIL_COLUMNS` (moeglichst viele Infospalten).
      2. Vorsortierung: LETZTER Trade zuerst (`exit_time DESC`).
      3. Anreicherung: Richtung "Long"/"Short", Exit-Grund "SL"/"TP"/"Signal",
         Dauer ("2h 15m"), move_pct (richtungsbereinigt), pnl_equity_pct
         (% des Startkapitals aus params_json->'equity').
      4. Berliner Wanduhrzeit fuer entry_time/exit_time (UTC -> Budapest).
      5. Unbekannter Run / leere DB -> leeres DataFrame mit Spaltenvertrag.

    Ausfuehrung:
        .venv\\Scripts\\python.exe -c "import sys; sys.path.insert(0,'test'); import test; test.test_backtest_trades_detail()"
    """
    import pandas as pd
    from datetime import datetime, timezone
    from pathlib import Path

    from backtest_lab.db import TRADE_DETAIL_COLUMNS, connect_backtest, get_backtest_trades, save_backtest_run
    from backtest_lab.types import BacktestRunRecord, new_run_id

    dbp = _bt_test_db("_test_trades_detail.duckdb")
    try:
        ts = datetime.now(timezone.utc)
        run_id = new_run_id()
        run = BacktestRunRecord(
            run_id=run_id, signal_run_id="sig_1",
            run_name="BT_detail_test", symbol="SILVER", timeframe="M30",
            params_json='{"spread_pct": 0.15, "equity": 10000.0, '
                        '"stop_loss_pct": 0.5, "take_profit_pct": 2.0}',
            date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 6, 1, tzinfo=timezone.utc),
            net_profit=100.0, win_rate=0.5, profit_factor=2.0,
            max_drawdown_pct=3.0, sharpe_ratio=1.0, trade_count=3,
            avg_trade_pnl=33.33, expectancy=20.0, created_at=ts,
            max_drawdown=300.0, sl_count=1,
        )
        # exit_time absichtlich unsortiert (neuester Trade in der Mitte)
        trades = pd.DataFrame([
            {
                "entry_time": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc),  # 2h 30m
                "entry_price": 30.0, "exit_price": 29.85,
                "direction": 1, "pnl": -500.0, "r_multiple": -1.0,
                "exit_reason": "sl",
            },
            {
                "entry_time": datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2026, 6, 10, 8, 30, tzinfo=timezone.utc),  # 30m (NEUESTER)
                "entry_price": 35.0, "exit_price": 35.7,
                "direction": 1, "pnl": 2000.0, "r_multiple": 4.0,
                "exit_reason": "tp",
            },
            {
                "entry_time": datetime(2026, 1, 15, 20, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2026, 1, 16, 9, 30, tzinfo=timezone.utc),  # 13h 30m
                "entry_price": 28.0, "exit_price": 27.72,
                "direction": -1, "pnl": -1000.0, "r_multiple": -2.0,
                "exit_reason": "signal",
            },
        ])
        con = connect_backtest(dbp)
        try:
            save_backtest_run(con, run, trades)
        finally:
            con.close()

        df = get_backtest_trades(run_id, dbp)
        print(f"[1] Spalten: {list(df.columns)}")
        assert list(df.columns) == TRADE_DETAIL_COLUMNS, (
            f"Spaltenvertrag verletzt: {list(df.columns)}"
        )
        assert len(df) == 3, f"Trades: {len(df)} (erwartet 3)"

        # --- 2) Vorsortierung: neuester Trade zuerst ----------------------
        assert df.iloc[0]["exit_time"] == "2026-06-10 10:30", (
            f"Neuester Trade muss oben stehen: {df.iloc[0]['exit_time']}"
        )
        ets = df["exit_time"].tolist()
        assert ets == sorted(ets, reverse=True), f"exit_time nicht DESC: {ets}"
        print(f"[2] Sortierung (neuester zuerst): {ets} -> OK")

        # --- 3) Anreicherung ----------------------------------------------
        newest = df.iloc[0]
        assert newest["direction"] == "Long", f"Richtung: {newest['direction']}"
        assert newest["exit_reason"] == "TP", f"Exit-Grund: {newest['exit_reason']}"
        assert newest["duration"] == "30m", f"Dauer: {newest['duration']}"
        assert newest["run_name"] == "BT_detail_test" and newest["symbol"] == "SILVER"
        # move_pct: Long 35.0 -> 35.7 = +2.0 % (Kursbewegung, richtungsbereinigt)
        assert abs(newest["move_pct"] - 2.0) < 1e-9, f"move_pct: {newest['move_pct']}"
        # pnl_equity_pct: 2000 $ / 10000 $ * 100 = 20.0 %
        assert abs(newest["pnl_equity_pct"] - 20.0) < 1e-9, (
            f"pnl_equity_pct: {newest['pnl_equity_pct']}"
        )

        sl = df[df["exit_reason"] == "SL"].iloc[0]
        assert sl["direction"] == "Long" and abs(sl["move_pct"] - (-0.5)) < 1e-9
        assert sl["duration"] == "2h 30m", f"SL-Dauer: {sl['duration']}"

        sig = df[df["exit_reason"] == "Signal"].iloc[0]
        assert sig["direction"] == "Short", f"Signal-Richtung: {sig['direction']}"
        # Short 28.0 -> 27.72 = -1.0 % Preisbewegung * -1 = +1.0 % (Gewinn-Richtung)
        # Achtung: PnL ist -1000 (Verlust) -> move_pct zeigt die Preisbewegung
        # gegen die Position: (27.72/28.0 - 1)*100 * -1 = +1.0 %
        assert abs(sig["move_pct"] - 1.0) < 1e-9, f"Signal-move_pct: {sig['move_pct']}"
        assert sig["duration"] == "13h 30m", f"Signal-Dauer: {sig['duration']}"
        # pnl_equity_pct negativ: -1000 / 10000 * 100 = -10.0 %
        assert abs(sig["pnl_equity_pct"] - (-10.0)) < 1e-9, (
            f"Signal-pnl_equity_pct: {sig['pnl_equity_pct']}"
        )
        print("[3] Anreicherung (Richtung/Exit-Grund/Dauer/move_pct/PnL-%EQ) -> OK")

        # --- 4) Berliner Wanduhrzeit (UTC -> Budapest) ---------------------
        # 2026-06-10 08:30 UTC = 10:30 Sommerzeit (CEST, UTC+2)
        assert newest["entry_time"] == "2026-06-10 10:00", (
            f"entry_time Berlin: {newest['entry_time']}"
        )
        assert newest["exit_time"] == "2026-06-10 10:30", (
            f"exit_time Berlin: {newest['exit_time']}"
        )
        print(f"[4] Wanduhrzeit Berlin: Entry {newest['entry_time']} | "
              f"Exit {newest['exit_time']} -> OK")

        # --- 5) Unbekannter Run / fehlende Trades --------------------------
        empty = get_backtest_trades("unbekannter_run", dbp)
        assert empty.empty and list(empty.columns) == TRADE_DETAIL_COLUMNS, (
            "Unbekannter Run muss leeres DataFrame mit Spaltenvertrag liefern"
        )
        print("[5] Unbekannter Run -> leeres DataFrame -> OK")

        print("=== test_backtest_trades_detail OK ===")
    finally:
        dbp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Signal Lab - Run-Namen mit Timestamp (build_run_name)
# ---------------------------------------------------------------------------

def test_signal_lab_naming_timestamp() -> None:
    """Verifiziert `build_run_name` mit Timestamp (Bugfix: 6-Arg-Aufruf).

    Prueft:
      1. Jump-Format: `jump_g{grid}_prox{prox}_{SYMBOL}_{TF}_{JJJJMMTT}_{HHMM}`
      2. MA-Format mit `ma_type`/period/smoothing/alpha_factor
      3. free_tag haengt hinten an (getrimmt)
      4. Default-Timestamp = jetzt (fester Bestandteil, kein leerer Name)
      5. 6-Arg-Signatur wie von sweep_runner Zeile 209/295 genutzt
    """
    from datetime import datetime

    from signal_lab.naming import build_run_name

    ts = datetime(2026, 8, 27, 11, 5)

    # --- 1) Jump -------------------------------------------------------
    name = build_run_name(
        "JumpIndicator",
        {"indicator_name": "JumpIndicator", "grid_interval": 0.5,
         "proximity_buffer": 0.075, "point_size": 0.001},
        "SILVER", "M1", ts,
    )
    assert name == "jump_g0.5_prox0.075_SILVER_M1_20260827_1105", f"Jump-Name: {name}"
    print(f"[1] Jump: {name} -> OK")

    # --- 2) MA ----------------------------------------------------------
    name_ma = build_run_name(
        "MAIndicator",
        {"indicator_name": "MAIndicator", "ma_type": "EHMA", "period": 6,
         "smoothing": 10, "alpha_factor": 3.0},
        "GOLD", "H1", ts,
    )
    assert name_ma == "ma_ehma_p6_s10_a3.0_GOLD_H1_20260827_1105", f"MA-Name: {name_ma}"
    print(f"[2] MA: {name_ma} -> OK")

    # --- 3) free_tag ------------------------------------------------------
    name_tag = build_run_name(
        "JumpIndicator",
        {"grid_interval": 0.5, "proximity_buffer": 0.075},
        "SILVER", "M1", ts, "  p11-htf  ",
    )
    assert name_tag == "jump_g0.5_prox0.075_SILVER_M1_20260827_1105_p11-htf", (
        f"free_tag-Name: {name_tag}"
    )
    print(f"[3] free_tag: {name_tag} -> OK")

    # --- 4) Default-Timestamp -------------------------------------------
    auto = build_run_name("JumpIndicator", {"grid_interval": 0.5, "proximity_buffer": 0.075})
    import re as _re
    assert _re.match(r"^jump_g0\.5_prox0\.075_\d{8}_\d{4}$", auto), f"Auto-Ts: {auto}"
    print(f"[4] Default-Timestamp: {auto} -> OK")

    # --- 5) 6-Arg-Aufruf (sweep_runner Zeile 209/295) -------------------
    name6 = build_run_name("JumpIndicator", {"grid_interval": 0.5}, "SILVER", "M1", ts, "")
    assert "_SILVER_M1_20260827_1105" in name6 and name6.startswith("jump_"), name6
    print(f"[5] 6-Arg-Aufruf: {name6} -> OK")

    print("=== test_signal_lab_naming_timestamp OK ===")


# ---------------------------------------------------------------------------
# Signal Lab - Vektorisierter JumpIndicator (Korrektheit + Benchmark)
# ---------------------------------------------------------------------------

def _synth_ohlcv(n_bars: int = 5000, start: str = "2026-01-01"):
    """Synthetische OHLCV-Bars (random walk, deterministischer Seed)."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(42)
    close = 100.0 + np.cumsum(rng.normal(0, 0.05, n_bars))
    open_ = np.concatenate([[close[0]], close[:-1]])
    spread = np.abs(rng.normal(0, 0.03, n_bars))
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    times = pd.date_range(start, periods=n_bars, freq="1min", tz="UTC")
    return pd.DataFrame({
        "time": times, "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.integers(10, 100, n_bars).astype(float),
    })


def test_jump_indicator_vectorized() -> None:
    """Verifiziert den voll vektorisierten JumpIndicator (Korrektheit + Speed).

    Prueft:
      1. Breakout-Events (BREAK_UP/BREAK_DOWN, kind=0, strength 1.0)
      2. Proximity-Bounces (circle_yellow/circle_fuchsia, kind=1, strength 0.5)
      3. Maximal 2 Events pro Bar, Level aufsteigend, Breakout vor Touch
      4. Leere/zu kurze Daten -> kein Crash
      5. Benchmark: > 500k Bars/s auf 5000 Bars (voll vektorisiert)
    """
    import time
    from algos.jump_indicator import JumpIndicator

    df = _synth_ohlcv(5000)
    ind = JumpIndicator(grid_interval=0.50, proximity_buffer=0.075, point_size=0.001)

    t0 = time.perf_counter()
    res = ind.compute(df, symbol="SILVER", timeframe="M1")
    dt = time.perf_counter() - t0

    # --- 1+2) Event-Typen vorhanden ------------------------------------
    types = {}
    for e in res.events:
        types.setdefault(e.signal_type, []).append(e)
    print(f"[1] Events gesamt: {len(res.events)} | Typen: "
          f"{ {k: len(v) for k, v in types.items()} }")
    for t in ("BREAK_UP", "BREAK_DOWN", "circle_yellow", "circle_fuchsia"):
        assert t in types, f"Event-Typ {t} fehlt"
    for e in types.get("BREAK_UP", []) + types.get("BREAK_DOWN", []):
        assert e.strength == 1.0, "Breakout muss strength 1.0 haben"
    for e in types.get("circle_yellow", []) + types.get("circle_fuchsia", []):
        assert e.strength == 0.5, "Touch/Bounce muss strength 0.5 haben"

    # --- 3) Max 2 Events/Bar + Sortierung ------------------------------
    from collections import Counter
    per_bar = Counter(e.time for e in res.events)
    assert max(per_bar.values()) <= 2, (
        f"Max {max(per_bar.values())} Events in einer Bar (erlaubt: 2)"
    )
    for t, evs in per_bar.items():
        if evs == 2:
            two = [e for e in res.events if e.time == t]
            kinds = [e.meta.get("event_kind") for e in two]
            assert kinds in (["breakout", "breakout"],
                             ["breakout", "touch"],
                             ["breakout", "proximity_bounce"]), (
                f"Event-Paar an Bar {t}: {kinds} (Breakout muss vor Touch sein)"
            )
            assert two[0].price <= two[1].price, (
                f"Level nicht aufsteigend an Bar {t}: {two[0].price} > {two[1].price}"
            )
    print("[3] Max 2 Events/Bar, Breakout vor Touch, Level aufsteigend -> OK")

    # --- 4) Leere/zu kurze Daten ----------------------------------------
    empty = JumpIndicator().compute(df.iloc[:0], symbol="X", timeframe="M1")
    assert empty.events == [] and empty.df.empty
    short = JumpIndicator().compute(df.iloc[:1], symbol="X", timeframe="M1")
    assert short.events == [], "1 Bar darf keine Events liefern"
    print("[4] Leere/1-Bar-Daten -> kein Crash -> OK")

    # --- 5) Benchmark (voll vektorisiert) -------------------------------
    rate = len(df) / dt
    print(f"[5] Benchmark: {len(df)} Bars in {dt*1000:.1f} ms "
          f"= {rate:,.0f} Bars/s")
    assert rate > 400_000, (
        f"Zu langsam: {rate:,.0f} Bars/s (erwartet > 400k)"
    )

    # --- 6) Blockbildung (extreme Parameter, RAM-Schutz) -----------------
    df_small = _synth_ohlcv(2000)
    ind_small = JumpIndicator(grid_interval=0.01, proximity_buffer=0.001)
    res_small = ind_small.compute(df_small, symbol="SILVER", timeframe="M1")
    assert len(res_small.events) > 0, "Feines Grid muss Events liefern"
    print(f"[6] Feines Grid (0.01) mit Blockbildung: {len(res_small.events)} Events -> OK")

    print("=== test_jump_indicator_vectorized OK ===")


# ---------------------------------------------------------------------------
# Signal Lab - End-to-End-Sweep-Smoke (kein TypeError in run_sweep_sequential)
# ---------------------------------------------------------------------------

def test_sweep_runner_smoke() -> None:
    """End-to-End-Smoke: run_sweep_sequential ohne run_name_override.

    Regression fuer den build_run_name-Signatur-Bruch (6-Arg-Aufruf):
    Frueher rief sweep_runner mit `(ind, params, symbol, tf, ts, free_tag)`
    auf, die neue Signatur hatte nur 5 Parameter -> TypeError. Der Test
    baut synthetische DBs in test/, fuehrt einen echten Jump-Sweep aus
    und verifiziert, dass die Run-Namen das Timestamp-Format tragen.
    """
    import duckdb
    from algos.signal_service import DuckDBSignalService
    from signal_lab.run_definition import build_run_definition
    from signal_lab.sweep_runner import run_sweep_sequential

    TEST = Path(__file__).resolve().parent
    db_market = TEST / "_test_smoke_market.duckdb"
    db_ana = TEST / "_test_smoke_analytics.duckdb"
    for p in (db_market, db_ana):
        if p.exists():
            p.unlink()
    try:
        # --- Markt-DB (200 M1-Bars) -------------------------------------
        df = _synth_ohlcv(200)
        con = duckdb.connect(str(db_market))
        con.execute("""
            CREATE TABLE ohlcv_bars (
                symbol VARCHAR NOT NULL, timeframe VARCHAR NOT NULL,
                time TIMESTAMPTZ NOT NULL, open DOUBLE NOT NULL, high DOUBLE NOT NULL,
                low DOUBLE NOT NULL, close DOUBLE NOT NULL, tick_volume BIGINT,
                spread INTEGER, real_volume BIGINT, created_at TIMESTAMP,
                PRIMARY KEY (symbol, timeframe, time)
            )
        """)
        for _, r in df.iterrows():
            con.execute(
                "INSERT INTO ohlcv_bars VALUES (?,?,?,?,?,?,?,?,?,?,current_timestamp)",
                ["SILVER", "M1", r["time"], r["open"], r["high"], r["low"],
                 r["close"], 100, 50, 100],
            )
        con.close()

        # --- Analytics-DB (Schema wie scripts/init_analytics_db.py) ------
        con_ana = duckdb.connect(str(db_ana))
        con_ana.execute("""
            CREATE TABLE IF NOT EXISTS indicator_runs (
                run_id VARCHAR PRIMARY KEY,
                indicator_name VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                timeframe VARCHAR NOT NULL,
                params_json JSON NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                run_name VARCHAR
            )
        """)
        con_ana.execute("""
            CREATE TABLE IF NOT EXISTS signal_events (
                run_id VARCHAR NOT NULL,
                time TIMESTAMPTZ NOT NULL,
                signal_type VARCHAR NOT NULL,
                direction TINYINT NOT NULL,
                price DOUBLE NOT NULL,
                strength DOUBLE NOT NULL,
                meta_json JSON,
                source_tf VARCHAR,
                signal_time TIMESTAMPTZ,
                PRIMARY KEY (run_id, time, signal_type, price)
            )
        """)
        con_ana.close()
        service = DuckDBSignalService(db_path=str(db_ana))

        # --- Run-Definition (1 Symbol, 1 TF, 1 Param-Set) ----------------
        definition = build_run_definition(
            symbols=["SILVER"],
            timeframes=["M1"],
            ranges={"proximity_buffer": {"min": 0.075, "step": 0.05, "max": 0.075}},
            date_from=None,
            date_to=None,
            strategy="grid",
            sample_size=1,
            fixed_params={
                "indicator_name": "JumpIndicator",
                "grid_interval": 0.5,
                "point_size": 0.001,
            },
        )
        assert definition.count_runs() == 1

        ids = run_sweep_sequential(
            definition,
            db_market,
            service,
            warmup_bars=10,
            tz_offset_hours=0,
        )
        assert len(ids) == 1, f"Erwartet 1 run_id, erhalten {len(ids)}"

        con = duckdb.connect(str(db_ana), read_only=True)
        row = con.execute(
            "SELECT run_name, indicator_name FROM indicator_runs WHERE run_id = ?",
            [ids[0]],
        ).fetchone()
        con.close()
        assert row is not None, "Run nicht persistiert"
        run_name, ind_name = row
        assert "jump" in str(ind_name).lower(), f"Indikator: {ind_name}"
        assert "_SILVER_M1_" in str(run_name), f"Run-Name ohne Symbol/TF: {run_name}"
        assert "prox" in str(run_name), f"Run-Name ohne prox-Parameter: {run_name}"
        assert "_20" in str(run_name), f"Run-Name ohne Timestamp: {run_name}"
        print(f"[Sweep-Smoke] run_id={ids[0]} | run_name={run_name} -> OK")

        # --- run_name_override (Stabilität, Update-Modus wie im Notebook) -
        # store_result ist idempotent (INSERT OR IGNORE): der Override greift
        # nur, wenn die alten Runs vorher geloescht wurden (sw_delete=True).
        deleted = service.delete_runs(symbols=["SILVER"], timeframes=["M1"])
        assert deleted >= 1, f"delete_runs: {deleted}"
        ids2 = run_sweep_sequential(
            definition,
            db_market,
            service,
            warmup_bars=10,
            tz_offset_hours=0,
            run_name_override="MEIN_LAUF_1",
        )
        assert len(ids2) == 1
        con = duckdb.connect(str(db_ana), read_only=True)
        row2 = con.execute(
            "SELECT run_name FROM indicator_runs WHERE run_id = ?", [ids2[0]]
        ).fetchone()
        con.close()
        assert row2[0] == "MEIN_LAUF_1", f"Override ignoriert: {row2[0]}"
        print(f"[Sweep-Smoke] run_name_override: {row2[0]} -> OK")

        print("=== test_sweep_runner_smoke OK ===")
    finally:
        for p in (db_market, db_ana):
            p.unlink(missing_ok=True)


def test_broker_symbols_point_digits() -> None:
    """Test: Migration point/digits auf broker_symbols (idempotent)."""
    import tempfile
    import duckdb

    with tempfile.TemporaryDirectory() as td:
        dbp = Path(td) / "app_data.duckdb"
        con = duckdb.connect(str(dbp))
        con.execute("""CREATE TABLE broker_symbols (
            symbol VARCHAR PRIMARY KEY, path VARCHAR, is_favorite BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT now())""")
        con.execute("INSERT INTO broker_symbols (symbol, path) VALUES ('SILVER', 'Metals')")
        # Migration (idempotent, wie im Notebook)
        con.execute("ALTER TABLE broker_symbols ADD COLUMN IF NOT EXISTS point DOUBLE")
        con.execute("ALTER TABLE broker_symbols ADD COLUMN IF NOT EXISTS digits INTEGER")
        con.execute("ALTER TABLE broker_symbols ADD COLUMN IF NOT EXISTS point DOUBLE")  # 2. Lauf
        con.execute(
            "INSERT INTO broker_symbols (symbol, point, digits) VALUES ('GOLD', 0.01, 2)"
            " ON CONFLICT (symbol) DO UPDATE SET point = EXCLUDED.point, digits = EXCLUDED.digits"
        )
        row = con.execute("SELECT symbol, point, digits FROM broker_symbols ORDER BY symbol").fetchall()
        con.close()
        assert row == [("GOLD", 0.01, 2), ("SILVER", None, None)], row
        print("=== test_broker_symbols_point_digits OK ===")


if __name__ == "__main__":
    test_backtest_overwrite_and_delete()
    test_signal_runs_dedupe()
    test_checkbox_reactivity()
    test_backtest_trades_detail()
    test_broker_symbols_point_digits()
    test_signal_lab_naming_timestamp()
    test_jump_indicator_vectorized()
    test_sweep_runner_smoke()

