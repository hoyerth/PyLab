# signal_lab/ui_state.py
"""Persistenz des UI-Stands als JSON-Datei (letzter Stand, keine DB)."""
import json
import tempfile
import os
from pathlib import Path
from typing import Any, Dict

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "ui_state.json"

# ---------------------------------------------------------------------------
# Lazy-Marimo-States (Singleton ueber Zell-Re-Runs hinweg)
# ---------------------------------------------------------------------------
# KRITISCH fuer marimo-Buttons: marimo matcht State-Konsumenten per Objekt-
# Identitaet (globals[ref] is state). Wuerde die Setup-Zelle (4a) bei jedem
# Re-Run ein NEUES mo.state() erzeugen, zeigten die Buttons/Closures auf
# verwaiste State-Objekte -> tote Buttons (Dialog bleibt, Klick bewirkt
# nichts). Dieses Modul-Singleton garantiert STABILE Objekte ueber alle
# Zell-Re-Runs (z. B. mehrfacher Lauf der Setup-Zelle beim Notebook-Start).
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
        _marimo_states = {
            "go_state": go_state,
            "set_go_state": set_go_state,
            "save_msg": save_msg,
            "set_save_msg": set_save_msg,
            "refresh_ctl": refresh_ctl,
        }
    return _marimo_states


def default_state() -> Dict[str, Any]:
    """Sinnvolle Defaults für das Signal Lab.

    Hinweis: VectorBT/Order-Testing ist bewusst NICHT enthalten – das kommt
    in ein separates Notebook/Modul (siehe Anweisung des Benutzers).
    """
    return {
        "symbols": ["SILVER"],
        "timeframes": ["M30"],
        "ma": {
            "ma_type": "EHMA",
            "period": {"min": 4, "step": 2, "max": 16},
            "smoothing": {"min": 6, "step": 2, "max": 14},
            "alpha_factor": {"min": 2.0, "step": 1.0, "max": 4.0},
        },
        "date_range": {"from": None, "to": None},
        "run_name_override": "",
        "free_tag": "",
        "strategy": "grid",
        "random_sample": 50,
        "quick_look": {"symbol_tf": "SILVER:M30", "overlay_tfs": ["H1", "H4"]},
        "htf_small_tf": "M15",
        "htf_exact_time": False,
    }


def load_state() -> Dict[str, Any]:
    """Liest den gespeicherten UI-Stand. Fallback: Defaults."""
    if not STATE_FILE.exists():
        return default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
        # Defaults mit gespeicherten Werten mergen (neue Felder ergänzen)
        merged = default_state()
        for k, v in stored.items():
            if k in merged and isinstance(v, dict) and isinstance(merged[k], dict):
                merged[k].update(v)
            else:
                merged[k] = v
        return merged
    except Exception:
        return default_state()


def save_state(state: Dict[str, Any]) -> None:
    """Schreibt den UI-Stand atomar (tmp + rename)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATE_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
