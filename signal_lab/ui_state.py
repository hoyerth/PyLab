# signal_lab/ui_state.py
"""Persistenz des UI-Stands als JSON-Datei (letzter Stand, keine DB)."""
import json
import tempfile
import os
from pathlib import Path
from typing import Any, Dict

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "ui_state.json"


def default_state() -> Dict[str, Any]:
    """Sinnvolle Defaults für das Signal Lab."""
    return {
        "symbols": ["SILVER"],
        "timeframes": ["M30"],
        "ma": {
            "ma_type": "EHMA",
            "period": {"min": 4, "step": 2, "max": 16},
            "smoothing": {"min": 6, "step": 2, "max": 14},
            "alpha_factor": {"min": 2.0, "step": 1.0, "max": 4.0},
        },
        "vectorbt": {
            "spread": {"min": 0.0, "step": 0.1, "max": 1.0},
            "sl_pct": {"min": 0.5, "step": 0.5, "max": 5.0},
            "tp_pct": {"min": 0.5, "step": 0.5, "max": 5.0},
            "position": {"min": 1.0, "step": 0.5, "max": 10.0},
            "fees": {"min": 0.0, "step": 0.01, "max": 0.1},
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
