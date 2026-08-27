# backtest_lab/ui_state.py
"""Persistenz des UI-Stands als JSON-Datei (letzter Stand, keine DB).

Analog zu `signal_lab/ui_state.py`:
- Atomarer Save (tmp + rename) nach `data/backtest_ui_state.json`.
- Defaults fuer Order-Parameter + Datumsbereich (Schritt 5).
- Modul-Singleton fuer marimo-State-Objekte (stabil ueber Zell-Re-Runs,
  verhindert tote Buttons - siehe Signal-Lab-Fix).
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

STATE_FILE: Path = (
    Path(__file__).resolve().parent.parent / "data" / "backtest_ui_state.json"
)

# ---------------------------------------------------------------------------
# Lazy-Marimo-States (Singleton ueber Zell-Re-Runs hinweg)
# ---------------------------------------------------------------------------
# KRITISCH fuer marimo-Buttons: marimo matcht State-Konsumenten per Objekt-
# Identitaet (globals[ref] is state). Dieses Modul-Singleton garantiert
# STABILE Objekte ueber alle Zell-Re-Runs (Pattern aus dem gefixten Signal Lab).
_marimo_states: Dict[str, Any] = {}


def get_marimo_states() -> Dict[str, Any]:
    """Liefert die marimo-State-Objekte (einmal erzeugt, danach stabil).

    Aufruf NUR innerhalb einer marimo-Zelle (Kernel-Kontext), da mo.state()
    und mo.ui.refresh() den Kontext fuer UI-IDs benoetigen. Beim ersten
    Aufruf werden die Objekte erzeugt und gecacht; jeder weitere Aufruf
    gibt dieselben Instanzen zurueck.
    """
    global _marimo_states
    if not _marimo_states:
        import marimo as mo

        go_state, set_go_state = mo.state("idle", allow_self_loops=True)
        save_msg, set_save_msg = mo.state("", allow_self_loops=False)
        refresh_ctl = mo.ui.refresh(
            default_interval="0.5s", label="Live-Aktualisierung (0.5s)"
        )
        # Bugfix 4: Loesch-Dialog fuer Backtest-Runs + Reload-Trigger
        del_state, set_del_state = mo.state("idle", allow_self_loops=True)
        bt_ctl, set_bt_ctl = mo.state(0, allow_self_loops=True)
        # Bugfix 5 (Checkbox-Reaktivitaet): Die Checkboxen der Auswahl-
        # Tabellen (render_checkbox_table) liegen in PYTHON-LISTEN - marimo
        # re-runt Zellen nur ueber an GLOBALE NAMEN gebundene Elemente
        # (bindings -> referring_cells). Listenelemente haben KEIN Binding,
        # ein Klick wuerde den GO-/Loesch-Button nie aktualisieren. Fix:
        # Jede Checkbox bekommt `on_change`, das diesen Zaehler erhoeht.
        # Die konsumierenden Zellen (Zelle 3 / 6b) lesen `sel_ctl()` ->
        # Re-Run bei jedem Klick -> lesen die aktuellen Checkbox-Werte.
        sel_ctl, set_sel_ctl = mo.state(0, allow_self_loops=False)
        # Trade-Detail (Klick auf einen Backtest-Run): run_id des Runs,
        # dessen Einzeltrades die Detail-Zelle (Notebook 6c) anzeigen soll.
        # "" = keine Auswahl. Wird von den 👁-Buttons in render_checkbox_table
        # (ui.py, ohne Global-Name-Binding) gesetzt - die Detail-Zelle liest
        # `detail_rid()` und re-runt dadurch bei jedem Klick.
        detail_rid, set_detail_rid = mo.state("", allow_self_loops=True)
        _marimo_states = {
            "go_state": go_state,
            "set_go_state": set_go_state,
            "save_msg": save_msg,
            "set_save_msg": set_save_msg,
            "refresh_ctl": refresh_ctl,
            "del_state": del_state,
            "set_del_state": set_del_state,
            "bt_ctl": bt_ctl,
            "set_bt_ctl": set_bt_ctl,
            "sel_ctl": sel_ctl,
            "set_sel_ctl": set_sel_ctl,
            "detail_rid": detail_rid,
            "set_detail_rid": set_detail_rid,
        }
    return _marimo_states


def default_state() -> Dict[str, Any]:
    """Sinnvolle Defaults fuer das Backtest Lab (Order-Parameter, Datumsbereich).

    Vorgaben (siehe Anforderung):
    - equity (Kapital): 10_000 $
    - spread: 0.15 %
    - SL fix: 0.2 % / TP fix: 2.0 %
    - reentry_same_bar: True (Gegensignal schliesst + neuer Entry in
      derselben Bar, `upon_opposite_entry=Reverse`)

    Hinweis: `stop_loss_pct`/`take_profit_pct` = None bedeutet "deaktiviert"
    (kein SL/TP). Der Datumsbereich wird separat persistiert (Schritt 5).
    """
    return {
        "symbols": ["SILVER"],
        "timeframes": ["M30"],
        "order": {
            "spread_pct": 0.15,
            "stop_loss_pct": 0.2,
            "take_profit_pct": 2.0,
            "position_size_pct": 1.0,
            "equity": 10_000.0,
            "leverage": 1000.0,
            "reentry_same_bar": True,
        },
        "date_range": {"from": None, "to": None},
        "run_name_override": "",
        "free_tag": "",
        # Bugfix 7 (Run-Name): True = der Benutzer hat den Run-Namen MANUELL
        # editiert -> dieser Name wird beim GO verwendet. False = automatisch:
        # der Runner baut den Namen aus der LIVE-Config (SL/TP/Spread/Size),
        # damit Konfigurationsaenderungen (z. B. SL) immer einen aktuellen,
        # eigenstaendigen Run-Namen ergeben (kein stale Name mehr).
        "run_name_manual": False,
    }


def load_state(state_file: Any = None) -> Dict[str, Any]:
    """Liest den gespeicherten UI-Stand. Fallback: Defaults.

    Args:
        state_file: Alternativer Pfad (fuer Tests). Default: `data/backtest_ui_state.json`.

    Returns:
        Gemergtes State-Dict (Defaults mit gespeicherten Werten).
    """
    path = Path(state_file) if state_file else STATE_FILE
    if not path.exists():
        return default_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        # Defaults mit gespeicherten Werten mergen (neue Felder ergaenzen)
        merged = default_state()
        for k, v in stored.items():
            if k in merged and isinstance(v, dict) and isinstance(merged[k], dict):
                merged[k].update(v)
            else:
                merged[k] = v
        return merged
    except Exception:
        return default_state()


def save_state(state: Dict[str, Any], state_file: Any = None) -> None:
    """Schreibt den UI-Stand atomar (tmp + rename).

    Args:
        state: UI-State-Dict (aus `load_state` bzw. UI-Elementen).
        state_file: Alternativer Pfad (fuer Tests). Default: `data/backtest_ui_state.json`.
    """
    path = Path(state_file) if state_file else STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
