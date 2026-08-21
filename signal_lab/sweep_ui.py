# signal_lab/sweep_ui.py
"""Zellenübergreifender Lauf-Status für Sweeps (Fortschritt + Abbruch).

Ein kleines Modul-Dict als Single Source of Truth für die Fortschrittsanzeige
im Notebook. Ein Hintergrund-Thread aktualisiert den Status; die UI-Zelle
liest ihn über `mo.ui.refresh` periodisch neu.
"""
import threading
from typing import Any, Dict, List

_state: Dict[str, Any] = {
    "running": False,
    "done": 0,
    "total": 0,
    "current": "",
    "cancelled": False,
    "error": None,
    "ids": [],
    "last_summary": None,  # gesetzte Zusammenfassung nach Laufende
    "message": "",          # kurze Statusmeldung für die UI
    "message_kind": "",     # "spinner" | "ok" | "err" | "info"
}
_lock = threading.Lock()


def get_state() -> Dict[str, Any]:
    """Liefert den aktuellen Lauf-Status (flache Kopie, thread-sicher)."""
    with _lock:
        return dict(_state)


def set_message(msg: str, kind: str = "info") -> None:
    """Setzt eine kurze Statusmeldung (wird in der Fortschritts-Zelle angezeigt)."""
    with _lock:
        _state["message"] = str(msg)
        _state["message_kind"] = str(kind)


def reset(total: int) -> None:
    """Bereitet einen neuen Lauf vor (total = erwartete Anzahl Runs)."""
    with _lock:
        _state.update(
            running=True, done=0, total=int(total), current="",
            cancelled=False, error=None, ids=[], last_summary=None,
            message="", message_kind="",
            _thread=None,
        )


def progress(done: int, total: int, current: str) -> None:
    """Callback des Runners: aktualisiert Fortschritt + aktuellen Run-Namen."""
    with _lock:
        _state["done"] = int(done)
        _state["total"] = int(total)
        _state["current"] = str(current)


def cancel() -> None:
    """Setzt das Abbruch-Flag (vom Stopp-Button aufgerufen)."""
    with _lock:
        _state["cancelled"] = True


def is_cancelled() -> bool:
    """Wird vom Runner als cancel_callback aufgerufen."""
    with _lock:
        return bool(_state["cancelled"])


def set_thread(t) -> None:
    """Merkt den laufenden Worker-Thread (für is_alive-Check)."""
    with _lock:
        _state["_thread"] = t


def is_alive() -> bool:
    """True, wenn der Worker-Thread des Laufs noch lebt.

    Bei True, aber toter Thread, hängt der Zustand (z. B. nach Kernel-
    Neustart oder Absturz) -> UI kann den Zustand bereinigen.
    """
    with _lock:
        t = _state.get("_thread")
        return bool(t is not None and t.is_alive())


def finish(ids: List[str], summary: Dict[str, Any] = None) -> None:
    """Schließt den Lauf ab (normal oder abgebrochen)."""
    with _lock:
        _state["running"] = False
        _state["current"] = ""
        _state["ids"] = list(ids)
        _state["last_summary"] = summary
        _state["_thread"] = None


def fail(err: str) -> None:
    """Markiert den Lauf als fehlgeschlagen."""
    with _lock:
        _state["running"] = False
        _state["current"] = ""
        _state["error"] = str(err)
        _state["_thread"] = None
