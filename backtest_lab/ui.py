# backtest_lab/ui.py
"""Schlanke UI-Zellen fuer das Backtest Lab (marimo).

Button-/State-Pattern exakt wie im gefixten Signal Lab
(Modul-Singleton-States, exportierte Buttons,
`return btn_confirm, btn_cancel`, weakref-sicher, Session-ID, CRLF).

Umsetzungsstand:
- Schritt 4 (fertig): `render_run_selection` - Checkbox-Tabelle der
  Run-Auswahl (nur letzter Signal-Lab-Lauf, Mehrfachauswahl).
- Schritt 5 (fertig): `render_order_params` - Eingabefelder fuer Spread,
  SL/TP, Position-Sizing und Datumsbereich; `render_complexity` -
  Komplexitaets-/RAM-Anzeige vor dem Lauf.

TODO (Umsetzungsschritte 6-8):
- Backtest-Runner-Anbindung (Schritt 6)
- Naming-UI (Schritt 7)
- Persistenz-Button + Sicherheitsabfrage + Fortschritt/Stop (Schritt 8)
"""
import datetime as dt
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from backtest_lab import db as _db
from backtest_lab.types import OrderConfig, make_order_config
from backtest_lab.ui_state import get_marimo_states

# Spalten, die in der Run-Auswahl-Tabelle angezeigt werden (run_id bleibt
# im Wert erhalten, wird aber versteckt -> `.value` liefert die run_ids).
# signal_from/signal_to werden von `db.enrich_signal_ranges` ergaenzt
# (abgedeckter Signal-Zeitraum des Runs); fehlen sie (z. B. Test-DBs),
# werden sie einfach nicht angezeigt.
_DISPLAY_COLUMNS: list[str] = [
    "run_name", "symbol", "timeframe", "created_at",
    "signal_from", "signal_to",
]
_HIDDEN_COLUMNS: list[str] = ["run_id"]


def _format_created_at(series: pd.Series) -> pd.Series:
    """Formatiert created_at als Anzeige-Zeit (Europe/Budapest).

    Delegiert an die oeffentliche Anzeige-Dublette ``backtest_lab.db.to_display_bp``
    (S4: zentrale Stelle). Rechenbasis bleibt die BKZ (naive UTC); die
    BP-Projektion ist reine Darstellung (docs/ZEITBASIS_KANON.md).
    """
    return _db.to_display_bp(series)


def render_run_selection(
    runs_df: Optional[pd.DataFrame],
    initial_selection: Optional[list[int]] = None,
    page_size: int = 10,
    label: str = "Signal-Run-Auswahl (letzter Signal-Lab-Lauf)",
) -> Any:  # mo.ui.table | mo.md (marimo lazy import, kein Import-Zyklus)
    """Baut die Checkbox-Tabelle fuer die Run-Auswahl (Schritt 4).

    Zeigt ausschliesslich die Runs des letzten Signal-Lab-Laufs (keine
    Historie - die Abfrage macht `db.get_last_signal_runs`). Jede Zeile
    hat eine Checkbox am Anfang (marimo `selection="multi"`); die
    Mehrfachauswahl erlaubt spaeter z. B. mehrere Runs in einem Backtest.

    Args:
        runs_df: Ergebnis von `db.get_last_signal_runs(...)`. Leer/None
            ergibt einen Hinweistext statt einer Tabelle.
        initial_selection: Zeilen-Indizes, die vorausgewaehlt sein sollen.
        page_size: Zeilen pro Seite.
        label: Ueberschrift der Tabelle.

    Returns:
        `mo.ui.table` (selection="multi") oder `mo.md`-Hinweis bei
        leerem Ergebnis. Aus den gewaehlten Zeilen liefert
        `selected_run_ids(table)` die zugehoerigen run_ids.
    """
    import marimo as mo

    if runs_df is None or runs_df.empty:
        return mo.md(
            "_Keine Signal-Runs im letzten Lauf gefunden - "
            "zuerst einen Signal-Lab-Lauf ausfuehren._"
        )

    if "run_id" not in runs_df.columns:
        raise ValueError("runs_df benoetigt die Spalte 'run_id' (db.get_last_signal_runs).")

    # Nur vorhandene Spalten anzeigen (signal_from/signal_to koennen fehlen,
    # z. B. ohne `enrich_signal_ranges` oder in Test-DBs).
    _disp = [c for c in _DISPLAY_COLUMNS if c in runs_df.columns]
    view: pd.DataFrame = runs_df[_disp + ["run_id"]].copy()
    view["created_at"] = _format_created_at(view["created_at"])

    return mo.ui.table(
        view,
        selection="multi",
        initial_selection=list(initial_selection) if initial_selection else [],
        page_size=page_size,
        label=label,
        hidden_columns=_HIDDEN_COLUMNS,
        show_column_summaries=False,
    )


def selected_run_ids(table) -> list[str]:
    """Extrahiert die gewaehlten `run_id`s aus der Run-Auswahl-Tabelle.

    Args:
        table: Das von `render_run_selection` gelieferte `mo.ui.table`.

    Returns:
        Liste der ausgewaehlten run_ids (leer bei keiner Auswahl).
    """
    if table is None or getattr(table, "value", None) is None:
        return []
    sel = table.value
    if not isinstance(sel, pd.DataFrame) or sel.empty:
        return []
    if "run_id" not in sel.columns:
        raise ValueError("Auswahl enthaelt keine run_id-Spalte (hidden_columns ok).")
    return [str(v) for v in sel["run_id"].tolist()]


def render_usd_values(params_ui) -> Any:
    """Read-only-Box mit den $-Werten der Order-Parameter (Bugfix 1).

    Neben Spread (%), Position-Sizing (%), SL (%) und TP (%) zeigt diese
    Box die konkreten Dollar-Werte - live aus den UI-Eingaben berechnet.
    Darf NUR in einer Zelle aufgerufen werden, die `params_ui` NICHT
    selbst erzeugt (marimo-Regel: kein `.value`-Zugriff in der
    erzeugenden Zelle).

    Umrechnungen (auf Basis Notional = Equity x Hebel x Size-%):
        Notional $    = equity * leverage * position_size_pct / 100
        Margin $      = equity * position_size_pct / 100   (eingesetztes Kapital)
        Spread $      = Notional $ * spread_pct / 100      (je Trade)
        SL-Risiko $   = Notional $ * stop_loss_pct / 100   (nur bei aktivem SL)
        TP-Chance $   = Notional $ * take_profit_pct / 100 (nur bei aktivem TP)

    Args:
        params_ui: `OrderParamsUI` aus `render_order_params`.

    Returns:
        `mo.Html`-Box (read-only, gebordert).
    """
    import marimo as mo

    def _f(v: float) -> str:
        return f"{v:,.2f}"

    equity = float(params_ui.num_equity.value or 0.0)
    pos_pct = float(params_ui.num_size.value or 0.0)
    spread_pct = float(params_ui.num_spread.value or 0.0)
    lev = float(params_ui.num_leverage.value or 1.0)

    notional = equity * lev * pos_pct / 100.0
    margin = equity * pos_pct / 100.0
    spread_usd = notional * spread_pct / 100.0
    sl_pct = float(params_ui.num_sl.value or 0.0)
    tp_pct = float(params_ui.num_tp.value or 0.0)
    sl_usd = notional * sl_pct / 100.0 if params_ui.sw_sl.value else None
    tp_usd = notional * tp_pct / 100.0 if params_ui.sw_tp.value else None

    def _row(label: str, value: str, hint: str = "") -> str:
        return (
            f"<tr><td style='padding:2px 10px 2px 0;color:#94a3b8;'>"
            f"{label}</td><td style='text-align:right;font-variant-numeric:tabular-nums;'>"
            f"<b>{value}</b></td>"
            f"{f'<td style=&quot;padding:2px 0 2px 8px;color:#64748b;font-size:11px;&quot;>{hint}</td>' if hint else '<td></td>'}"
            f"</tr>"
        )

    rows = "".join([
        _row("Equity", f"{_f(equity)} $"),
        _row("Hebel", f"{lev:g}"),
        _row("Position (Notional)", f"{_f(notional)} $", f"{pos_pct:g} % Kapital x Hebel"),
        _row("Margin (eingesetzt)", f"{_f(margin)} $"),
        _row("Spread (je Trade)", f"{_f(spread_usd)} $", f"{spread_pct:g} %"),
        _row("SL-Risiko", f"{_f(sl_usd)} $" if sl_usd is not None else "–", f"Exit bei {sl_pct:g} % Kursbewegung" if sl_usd is not None else "SL aus"),
        _row("TP-Chance", f"{_f(tp_usd)} $" if tp_usd is not None else "–", f"Exit bei {tp_pct:g} % Kursbewegung" if tp_usd is not None else "TP aus"),
    ])
    return mo.Html(
        "<div style='border:1px solid #334155;border-radius:8px;padding:10px 12px;"
        "min-width:280px;background:#0f172a;'>"
        "<div style='font-weight:600;margin-bottom:4px;'>💵 $-Werte (read-only)</div>"
        f"<table style='border-collapse:collapse;font-size:13px;'>{rows}</table>"
        "</div>"
    )


def render_order_params_with_usd(params_ui) -> Any:
    """Rendert die Order-Parameter mit INLINE-$-Werten (Bugfix 3).

    Bugfix 3 (User): Die $-Werte sollen DIREKT NEBEN den Eingabefeldern
    stehen, nicht in einer eigenen Box/Zelle. Diese Funktion rendert daher
    jedes Eingabefeld zusammen mit einem kleinen $-Badge daneben
    (live aus den aktuellen Werten berechnet).

    marimo-Regel: Darf NUR in einer Zelle aufgerufen werden, die
    `params_ui` NICHT selbst erzeugt (kein `.value`-Zugriff in der
    erzeugenden Zelle) - das Notebook ruft sie in Zelle 2b auf.

    Umrechnungen (Notional = Equity x Hebel x Size-%):
        Notional $  = equity * leverage * position_size_pct / 100
        Margin $    = equity * position_size_pct / 100    (eingesetztes Kapital)
        Spread $    = Notional $ * spread_pct / 100       (je Trade)
        SL-Risiko $ = Notional $ * stop_loss_pct / 100    (bei aktivem SL)
        TP-Chance $ = Notional $ * take_profit_pct / 100  (bei aktivem TP)

    Args:
        params_ui: `OrderParamsUI` aus `render_order_params`.

    Returns:
        `mo.vstack` mit allen Eingabefeldern + $-Badges + Datumsbereich.
    """
    import marimo as mo

    def _f(v: float) -> str:
        return f"{v:,.2f}"

    equity = float(params_ui.num_equity.value or 0.0)
    pos_pct = float(params_ui.num_size.value or 0.0)
    spread_pct = float(params_ui.num_spread.value or 0.0)
    lev = float(params_ui.num_leverage.value or 1.0)

    notional = equity * lev * pos_pct / 100.0
    margin = equity * pos_pct / 100.0
    spread_usd = notional * spread_pct / 100.0
    sl_pct = float(params_ui.num_sl.value or 0.0)
    tp_pct = float(params_ui.num_tp.value or 0.0)
    sl_usd = notional * sl_pct / 100.0 if params_ui.sw_sl.value else None
    tp_usd = notional * tp_pct / 100.0 if params_ui.sw_tp.value else None

    def _badge(txt: str) -> Any:
        return mo.Html(
            "<span style='white-space:nowrap;font-size:12px;color:#16a34a;"
            "font-weight:600;padding:4px 8px;border:1px solid #16a34a55;"
            "border-radius:6px;background:#16a34a11;align-self:center;'>"
            f"{txt}</span>"
        )

    return mo.vstack([
        mo.md("**Order-Parameter**"),
        mo.Html(
            "<div style='font-size:12px;color:#94a3b8;margin-bottom:4px;'>"
            "SL/TP sind **% Kursbewegung** (Preis-Distanz vom Entry) – NICHT % des "
            "Positionswerts. Der $-Betrag ergibt sich aus Notional × Kursbewegung "
            "(Notional = Equity × Hebel × Size).</div>"
        ),
        mo.hstack([params_ui.num_equity, _badge("Startkapital")]),
        mo.hstack([params_ui.num_leverage, _badge(f"Hebel {lev:g} → {notional:,.2f} $ Notional")]),
        mo.hstack([params_ui.num_spread, _badge(f"= {spread_usd:,.2f} $ je Trade")]),
        mo.hstack([params_ui.num_size,
                   _badge(f"= {notional:,.2f} $ Notional (Margin {margin:,.2f} $)")]),
        mo.hstack([params_ui.sw_sl, params_ui.num_sl,
                   _badge(f"Exit bei {sl_pct:g} % Kursbewegung → {sl_usd:,.2f} $ Risiko" if sl_usd is not None else "SL aus")]),
        mo.hstack([params_ui.sw_tp, params_ui.num_tp,
                   _badge(f"Exit bei {tp_pct:g} % Kursbewegung → {tp_usd:,.2f} $ Chance" if tp_usd is not None else "TP aus")]),
        params_ui.sw_reentry,
        mo.md("**Datumsbereich** (manuelle Eingabe gewinnt vor dem Kalender)"),
        mo.hstack([params_ui.date_from, params_ui.date_to]),
        mo.hstack([params_ui.txt_from, params_ui.txt_to]),
    ])


# ---------------------------------------------------------------------------
# Bugfix 4: Verwaltung bestehender Backtest-Runs (Tabelle + Loeschen)
# ---------------------------------------------------------------------------
# Bugfix 8: Spalten-Anordnung laut User:
#   - `sl_count` (SL-Exits) DIREKT hinter `trade_count` (Trades)
#   - `net_profit_pct` (Gewinn in % des Equity) direkt hinter `net_profit`
#   - `worst_trade` = groesster Einzelverlust in $ (min pnl) - beantwortet
#     "was war der schlimmste Einzeltrade" getrennt vom Equity-Drawdown
#   - `max_drawdown` ($) = kumulativer Equity-Drawdown (nicht Einzelverlust)
_BT_DISPLAY_COLUMNS: list[str] = [
    "run_name", "symbol", "timeframe",
    "trade_count", "sl_count",
    "net_profit", "net_profit_pct",
    "win_rate", "max_win", "worst_trade", "max_drawdown",
    "created_at",
]


def _bump_selection(_value: Any = None) -> None:
    """on_change-Handler fuer Auswahl-Checkboxen (Bugfix 5: Reaktivitaet).

    marimo re-runt Zellen NUR ueber an GLOBALE NAMEN gebundene UI-Elemente
    (Registry-Bindings -> referring_cells). Die Checkboxen von
    `render_checkbox_table` liegen in PYTHON-LISTEN und haben daher KEIN
    Binding - ein Klick wuerde den GO-/Loesch-Button nie aktualisieren.
    Dieser Handler erhoeht den Modul-State-Zaehler `sel_ctl`
    (get_marimo_states); die konsumierenden Zellen (Zelle 3 / 6b im
    Notebook) lesen `sel_ctl()` und re-runen dadurch bei jedem Klick,
    um die aktuellen Checkbox-Werte auszuwerten.

    Args:
        _value: Neuer Checkbox-Wert (wird nicht benoetigt, nur Bump).
    """
    get_marimo_states()["set_sel_ctl"](lambda v: int(v) + 1)


def _select_detail(run_id: str) -> None:
    """on_click-Handler der 👁-Detail-Buttons (Trade-Detail-Ansicht).

    Setzt den Modul-State `detail_rid` (get_marimo_states) auf die run_id
    des angeklickten Runs. Die Detail-Zelle im Notebook (6c) liest
    `detail_rid()` -> marimo re-runt sie bei jedem Klick und zeigt die
    Einzeltrades (gleiches Muster wie `_bump_selection`/`sel_ctl`).

    Args:
        run_id: run_id des Runs, dessen Trades angezeigt werden sollen.
    """
    get_marimo_states()["set_detail_rid"](str(run_id))


def render_checkbox_table(
    df: Optional[pd.DataFrame],
    display_cols: list[str],
    id_col: str = "run_id",
    initial_selected: Optional[list] = None,
    page_size: int = 50,
    label: str = "",
    empty_hint: str = "_Keine Einträge vorhanden._",
    show_detail: bool = False,
    detail_tooltip: str = "Einzeltrades anzeigen",
) -> tuple[Any, list, list, list]:
    """High-Contrast-HTML-Tabelle mit Checkboxen (Bugfix 2: schwarz auf weiss).

    Ersatz fuer `mo.ui.table`: Die marimo-Tabelle rendert auf einem Canvas
    (Glide Data Grid), dessen Cursor-/Auswahlzeilen-Farben im Frontend
    fest verdrahtet und per CSS NICHT aenderbar sind ("Cursorzeile nicht
    lesbar"). Diese Tabelle ist reines HTML/CSS -> volle Kontrolle:
      - Tabellenhintergrund WEISS, Text SCHWARZ (schwarz auf weiss)
      - Cursorzeile (Hover) wird INVERTIERT (schwarz + weisser Text) ->
        immer eindeutig und lesbar
      - native Checkbox pro Zeile fuer die Mehrfachauswahl

    Mit `show_detail=True` kommt pro Zeile eine kompakte 👁-Spalte
    ("Trades") hinzu: Klick auf den Button (NICHT die Checkbox) setzt den
    Modul-State `detail_rid` -> die Trade-Detail-Zelle im Notebook zeigt
    die Einzeltrades des Runs (neuester zuerst, sortier-/filterbar).

    Args:
        df: Datenrahmen (leer/None -> Hinweistext).
        display_cols: Anzuzeigende Spalten (in dieser Reihenfolge).
        id_col: Spalte mit den IDs (Default "run_id").
        initial_selected: IDs, die vorausgewaehlt sein sollen.
        page_size: Max. angezeigte Zeilen (BT-Runs koennen viele sein).
        label: Ueberschrift.
        empty_hint: Text bei leerem Datenrahmen.
        show_detail: Wenn True, wird je Zeile ein 👁-Button gerendert,
            der `detail_rid` auf die Zeilen-ID setzt (Trade-Detail).
        detail_tooltip: Tooltip der 👁-Buttons.

    Returns:
        (container, checkboxes, ids, detail_buttons) - container wird
        gerendert; die Auswahl liest man mit
        `selected_checkbox_ids(checkboxes, ids)`. `detail_buttons` ist
        eine Liste der 👁-Buttons (leer bei `show_detail=False`) - die
        konsumierende Zelle sollte sie EXPORTIEREN (starke Referenz,
        sonst kann der GC sie einsammeln, weakref-Registry).

    Reaktivitaet (Bugfix 5): Die Checkboxen liegen in einer PYTHON-LISTE
    und haben damit KEIN marimo-Global-Name-Binding (Klick allein wuerde
    keine abhaengige Zelle re-runen). Jede Checkbox erhoeht daher per
    `on_change` den Modul-State-Zaehler `sel_ctl` (`get_marimo_states`);
    konsumierende Zellen muessen `sel_ctl()` LESEN, damit sie bei jedem
    Klick re-runen und die aktuellen Werte auswerten (siehe Notebook
    Zelle 3 / 6b). Die 👁-Buttons setzen analog `detail_rid` (gleiches
    Muster).
    """
    import marimo as mo

    if df is None or df.empty or id_col not in df.columns:
        return mo.md(empty_hint), [], [], []

    view = df.copy()
    if "created_at" in view.columns:
        view["created_at"] = _format_created_at(view["created_at"])

    cols = [c for c in display_cols if c in view.columns]
    initial = set(str(i) for i in (initial_selected or []))

    checkboxes: list = []
    ids: list = []
    detail_buttons: list = []
    rows_html: list = []
    for _, row in view.head(int(page_size)).iterrows():
        rid = str(row[id_col])
        # Bugfix 5 (Reaktivitaet): `on_change`-Bump - Checkboxen in Listen
        # haben kein Global-Name-Binding (marimo re-runt sonst nichts).
        cb = mo.ui.checkbox(
            value=rid in initial, label="", on_change=_bump_selection
        )
        checkboxes.append(cb)
        ids.append(rid)
        if show_detail:
            # Detail-Button (Trade-Detail): setzt `detail_rid` via Modul-
            # State - die Detail-Zelle (Notebook 6c) liest den State und
            # re-runt dadurch bei jedem Klick.
            btn = mo.ui.button(
                label="👁",
                tooltip=detail_tooltip,
                on_click=lambda _v, r=rid: _select_detail(r),
            )
            detail_buttons.append(btn)
            cells = f"<td class='bt-detail'>{btn}</td>"
        else:
            cells = ""
        cells += "".join(
            f"<td>{row[c]}</td>" if row[c] is not None else "<td></td>"
            for c in cols
        )
        rows_html.append(f"<tr><td class='bt-cb'>{cb}</td>{cells}</tr>")

    head = "".join(f"<th>{_bt_col_title(c)}</th>" for c in cols)
    if show_detail:
        head = f"<th class='bt-detail' title='{detail_tooltip}'>Trades</th>" + head
    table = (
        "<div class='bt-table-wrap'>"
        f"<table class='bt-select-table'>"
        f"<thead><tr><th class='bt-cb'>&nbsp;</th>{head}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
        "</div>"
    )
    # Bugfix 6 (Cursorzeile): Die Styles werden SELBST mitgerendert (nicht
    # mehr nur im Style-Block der Notebook-Zelle 2b). Nur so ist garantiert,
    # dass die Hover-Zeile (Cursorbalken) IMMER schwarz mit WEISSEM Text
    # erscheint - unabhaengig davon, ob/wo die Notebook-Zelle gerendert
    # wurde. Ohne diesen Block wuerde die Zeile weiss mit schwarzem Text
    # bleiben (unlesbar, "schwarze Schrift gegen weissen Cursorbalken").
    # Zusaetzlich wird die (schwarze) Checkbox in der Hover-Zeile invertiert,
    # damit sie auf schwarzem Grund sichtbar bleibt. Der 👁-Detail-Button
    # wird ebenfalls invertiert (bleibt in der schwarzen Cursorzeile lesbar).
    _style = (
        "<style>"
        ".bt-table-wrap{max-height:480px;overflow:auto;border:1px solid #94a3b8;"
        "border-radius:8px;background:#fff;margin-top:4px;}"
        ".bt-select-table{border-collapse:collapse;width:100%;background:#fff;"
        "color:#000;font-size:13px;}"
        ".bt-select-table th{background:#f1f5f9;color:#000;text-align:left;"
        "padding:6px 10px;border-bottom:2px solid #94a3b8;position:sticky;"
        "top:0;z-index:2;white-space:nowrap;}"
        ".bt-select-table td{padding:5px 10px;border-bottom:1px solid #e2e8f0;"
        "color:#000;white-space:nowrap;}"
        ".bt-select-table td.bt-cb{width:28px;text-align:center;}"
        ".bt-select-table th.bt-cb{width:28px;}"
        ".bt-select-table th.bt-detail{width:52px;text-align:center;}"
        ".bt-select-table td.bt-detail{width:52px;text-align:center;}"
        ".bt-select-table td.bt-detail button{width:30px;height:26px;padding:0;"
        "border:1px solid #cbd5e1;border-radius:5px;background:#f8fafc;color:#000;"
        "font-size:13px;line-height:1;cursor:pointer;}"
        ".bt-select-table td.bt-detail button:hover{border-color:#000;}"
        ".bt-select-table tbody tr:hover td{background:#000 !important;"
        "color:#fff !important;}"
        ".bt-select-table tbody tr:hover td.bt-cb{background:#000 !important;}"
        ".bt-select-table tbody tr:hover td.bt-detail{background:#000 !important;}"
        ".bt-select-table tbody tr:hover td.bt-cb marimo-ui-element{"
        "filter:invert(1);}"
        ".bt-select-table tbody tr:hover td.bt-detail marimo-ui-element{"
        "filter:invert(1);}"
        ".bt-select-table input[type=checkbox]{width:15px;height:15px;"
        "accent-color:#000;cursor:pointer;}"
        "</style>"
    )
    container = mo.vstack([
        mo.md(f"**{label}** ({len(ids)} Einträge)") if label else mo.md(""),
        mo.Html(_style + table),
    ])
    return container, checkboxes, ids, detail_buttons


def _bt_col_title(col: str) -> str:
    """Lesbarer Spaltentitel fuer die Checkbox-Tabelle (von/bis)."""
    return {
        "run_name": "Run-Name",
        "symbol": "Symbol",
        "timeframe": "TF",
        "created_at": "Erstellt",
        "trade_count": "Trades",
        "sl_count": "SL-Exits",
        "net_profit": "Netto-$",
        "net_profit_pct": "Gewinn %",
        "win_rate": "Winrate",
        "max_win": "Max Win $",
        "worst_trade": "Worst Trade $",
        "max_drawdown": "Max Equity-DD $",
        "signal_from": "Signale von",
        "signal_to": "Signale bis",
    }.get(col, col.replace("_", " ").capitalize())


def selected_checkbox_ids(checkboxes: list, ids: list) -> list[str]:
    """Liefert die IDs der angehakten Checkboxen.

    Args:
        checkboxes: Liste der `mo.ui.checkbox` aus `render_checkbox_table`.
        ids: Zuordnung IDs (gleiche Reihenfolge).

    Returns:
        Liste der ausgewaehlten IDs (leer bei keiner Auswahl).
    """
    return [str(rid) for cb, rid in zip(checkboxes, ids) if cb.value]


# ---------------------------------------------------------------------------
# Schritt 5: Order-Parameter UI (v1)
# ---------------------------------------------------------------------------


@dataclass
class OrderParamsUI:
    """Gebündelte marimo-Eingabeelemente der Order-Parameter (Schritt 5).

    Attributes:
        num_equity: `mo.ui.number` - Startkapital/Equity in USD (Default 10 000 $).
        num_spread: `mo.ui.number` - Spread in Prozent (0.15 = 0.15 %).
        sw_sl / num_sl: Switch + Zahl - Stop-Loss fix in Prozent (Switch aus
            = kein SL, `stop_loss_pct=None`).
        sw_tp / num_tp: Switch + Zahl - Take-Profit fix in Prozent.
        num_size: `mo.ui.number` - Position-Sizing in Prozent des Kapitals.
        date_from / date_to: `mo.ui.date` - Kalender-Picker (UI-Grenzen).
        txt_from / txt_to: `mo.ui.text` - manuelle JJJJ-MM-TT-Eingabe
            (gewinnt vor dem Kalenderwert, wie im Signal Lab).
    """

    num_equity: Any
    num_spread: Any
    sw_sl: Any
    num_sl: Any
    sw_tp: Any
    num_tp: Any
    num_size: Any
    num_leverage: Any
    sw_reentry: Any
    date_from: Any
    date_to: Any
    txt_from: Any
    txt_to: Any
    _date_min: Any = None
    _date_max: Any = None

    def _resolve_date(self, txt, picker) -> Optional[dt.date]:
        """Manuelle Eingabe gewinnt; sonst Kalenderwert; innerhalb der Grenzen."""
        s = (txt.value or "").strip()
        d: Optional[dt.date] = None
        if s:
            try:
                d = dt.date.fromisoformat(s)
            except ValueError:
                d = None
        if d is None:
            d = picker.value
        if d is not None:
            if self._date_min is not None and d < self._date_min:
                d = self._date_min
            if self._date_max is not None and d > self._date_max:
                d = self._date_max
        return d

    def resolve_dates(self) -> tuple[Optional[dt.date], Optional[dt.date]]:
        """Gewaehlter Datumsbereich (manuell > Kalender)."""
        return self._resolve_date(self.txt_from, self.date_from), self._resolve_date(
            self.txt_to, self.date_to
        )

    def to_order_config(self) -> OrderConfig:
        """Baut die validierte OrderConfig aus den aktuellen UI-Werten.

        Raises:
            ValueError: Bei ungueltigen Eingaben (UI zeigt die Meldung).
        """
        sl = float(self.num_sl.value) if self.sw_sl.value else None
        tp = float(self.num_tp.value) if self.sw_tp.value else None
        return make_order_config(
            spread_pct=float(self.num_spread.value),
            stop_loss_pct=sl,
            take_profit_pct=tp,
            position_size_pct=float(self.num_size.value),
            equity=float(self.num_equity.value),
            leverage=float(self.num_leverage.value),
            reentry_same_bar=bool(self.sw_reentry.value),
        )

    def to_state(self) -> dict:
        """Aktueller Stand als State-Dict (fuer Persistenz, Schritt 5).

        Liefert `order` (spread/SL/TP/Size/equity/leverage/reentry_same_bar,
        None = deaktiviert) und `date_range` (ISO-Strings). Symbol/TF-Auswahl
        wird separat im Notebook-State gefuehrt.
        """
        cfg = self.to_order_config()
        d_from, d_to = self.resolve_dates()
        return {
            "order": {
                "spread_pct": cfg.spread_pct,
                "stop_loss_pct": cfg.stop_loss_pct,
                "take_profit_pct": cfg.take_profit_pct,
                "position_size_pct": cfg.position_size_pct,
                "equity": cfg.equity,
                "leverage": cfg.leverage,
                "reentry_same_bar": cfg.reentry_same_bar,
            },
            "date_range": {
                "from": d_from.isoformat() if d_from else None,
                "to": d_to.isoformat() if d_to else None,
            },
        }


def render_order_params(
    defaults: dict,
    date_min: Any = None,
    date_max: Any = None,
) -> OrderParamsUI:
    """Erzeugt die Order-Parameter-Eingaben (Schritt 5).

    Args:
        defaults: UI-State aus `backtest_lab.ui_state.load_state()` -
            erwartet `defaults["order"]` (spread_pct, stop_loss_pct,
            take_profit_pct, position_size_pct, equity) und
            `defaults["date_range"]`.
        date_min / date_max: Datumsspanne aus `db.available_date_range()`
            (naive UTC) als Grenzen der Kalender-Picker.

    Returns:
        `OrderParamsUI` mit den marimo-Elementen (`mo.ui.number/switch/date/text`).
    """
    import marimo as mo

    order: dict = defaults.get("order") or {}
    dr: dict = defaults.get("date_range") or {}

    num_equity = mo.ui.number(
        100.0, 100_000_000.0, 100.0,
        value=float(order.get("equity", 10_000.0)),
        label="Equity / Kapital ($)",
    )
    num_spread = mo.ui.number(
        0.001, 5.0, 0.005, value=float(order.get("spread_pct", 0.15)),
        label="Spread (%)",
    )
    sl = order.get("stop_loss_pct")
    sw_sl = mo.ui.switch(value=sl is not None, label="Stop-Loss aktiv")
    num_sl = mo.ui.number(
        0.05, 50.0, 0.05, value=float(sl) if sl is not None else 0.2,
        label="Stop-Loss (% Kursbewegung)",
    )
    tp = order.get("take_profit_pct")
    sw_tp = mo.ui.switch(value=tp is not None, label="Take-Profit aktiv")
    num_tp = mo.ui.number(
        0.05, 100.0, 0.05, value=float(tp) if tp is not None else 2.0,
        label="Take-Profit (% Kursbewegung)",
    )
    num_size = mo.ui.number(
        0.1, 100.0, 0.5, value=float(order.get("position_size_pct", 1.0)),
        label="Position-Sizing (% Kapital)",
    )
    num_leverage = mo.ui.number(
        1.0, 10_000.0, 100.0, value=float(order.get("leverage", 1000.0)),
        label="Hebel (CFD, Vorgabe 1000)",
    )
    sw_reentry = mo.ui.switch(
        value=bool(order.get("reentry_same_bar", True)),
        label="Re-Entry gleiche Bar: Gegensignal schließt alten Trade "
              "UND öffnet neuen Entry in derselben Bar",
    )

    dmin = date_min.date() if date_min is not None else None
    dmax = date_max.date() if date_max is not None else None

    def _pdate(s, default):
        if s:
            try:
                return dt.date.fromisoformat(str(s))
            except ValueError:
                pass
        return default

    date_from = mo.ui.date(
        dmin, dmax, value=_pdate(dr.get("from"), dmin), label="Von (Kalender)"
    )
    date_to = mo.ui.date(
        dmin, dmax, value=_pdate(dr.get("to"), dmax), label="Bis (Kalender)"
    )
    txt_from = mo.ui.text(
        value=dr.get("from") or "", label="Von (manuell JJJJ-MM-TT)"
    )
    txt_to = mo.ui.text(
        value=dr.get("to") or "", label="Bis (manuell JJJJ-MM-TT)"
    )

    return OrderParamsUI(
        num_equity=num_equity,
        num_spread=num_spread,
        sw_sl=sw_sl,
        num_sl=num_sl,
        sw_tp=sw_tp,
        num_tp=num_tp,
        num_size=num_size,
        num_leverage=num_leverage,
        sw_reentry=sw_reentry,
        date_from=date_from,
        date_to=date_to,
        txt_from=txt_from,
        txt_to=txt_to,
        _date_min=dmin,
        _date_max=dmax,
    )


def render_complexity(report: Any, config: dict) -> Any:
    """Komplexitaets-Anzeige vor dem Lauf (Anzahl Runs + RAM, Schritt 5).

    Zeigt die Schaetzung (volles Kreuzprodukt) und bei Ueberschreitung die
    Ablehnungs-/Warn-Gruende. Der GO-Button wird im Notebook ueber
    `complexity.go_allowed(report)` deaktiviert.

    Args:
        report: `ComplexityReport` aus `complexity.estimate_complexity`.
        config: Komplexitaets-Konfiguration (`complexity.load_complexity_config`).

    Returns:
        `mo.vstack` mit Anzahl Runs, RAM-Schaetzung und Status.
    """
    import marimo as mo

    if report is None:
        return mo.md("⚠️ _Keine Komplexitäts-Schätzung möglich - Symbol/TF-Auswahl prüfen._")

    lines = [
        mo.md(
            f"**Komplexitäts-Check:** {report.n_runs} Runs · geschätzt "
            f"**{report.est_ram_total_mb:,.0f} MB** (volles Kreuzprodukt · "
            f"~{report.est_ram_per_run_mb:,.0f} MB/Run)"
        ),
    ]
    if report.ok:
        lines.append(
            mo.md(
                f"✅ Ressourcen ausreichend "
                f"(Limit {report.max_ram_mb:,.0f} MB / {report.max_runs} Runs)"
            )
        )
        for warning in getattr(report, "warnings", ()):
            lines.append(mo.md(f"⚠️ {warning}"))
    else:
        for reason in report.reasons:
            lines.append(mo.md(f"❌ {reason}"))
        for warning in getattr(report, "warnings", ()):
            lines.append(mo.md(f"⚠️ {warning}"))
        lines.append(
            mo.md(
                "_Der Start wird abgelehnt, bis die Limits angepasst "
                "oder der Parameter-Raum verkleinert wird._"
            )
        )
    return mo.vstack(lines)
