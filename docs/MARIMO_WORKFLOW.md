# MARIMO-ENTWICKLUNGS-WORKFLOW (PyLab)

> Ziel: **Kein stilles Überschreiben** der Notebook-Datei durch den marimo-Server.
> Quelle der Wahrheit ist die Datei auf der Platte (PyCharm / Continue / Skripte).

---

## 1. Wer schreibt wann was? (Architektur-Prinzip)

| Quelle | Darf schreiben | Wann |
|---|---|---|
| **PyCharm / Continue / Skripte** | ✅ Notebook-Datei + `signal_lab/*.py` | jederzeit (Single Source of Truth) |
| **marimo-Server (Browser)** | ✅ nur bei **manuellem** `Ctrl+S` | nur wenn du im Browser Zellstruktur/UI änderst |
| **marimo-Server (Autosave)** | ❌ deaktiviert | – |
| **marimo-Server (--watch)** | ❌ entfernt | – |

**Eingebaute Schutzschichten (bereits aktiv):**
1. `start_marimo.ps1` startet **ohne `--watch`** → Server beobachtet die Datei nicht, reserialisiert sie nie von selbst (Grund: marimo Issue #8421)
2. `.marimo.toml` → `[save] autosave = "off"` → Browser schreibt nur bei explizitem Speichern
3. `.marimo.toml` → `[runtime] auto_reload = "autorun"` → Änderungen an `signal_lab/*.py` werden automatisch in den Kernel übernommen

---

## 2. Schritt-für-Schritt: Die 3 Anwendungsfälle

### Fall A: Logik ändern (`signal_lab/*.py`) – HÄUFIGSTER FALL

> z. B. `sweep_ui.py`, `run_definition.py`, `sweep_runner.py` ändern

1. **Server kann weiterlaufen** (nicht stoppen!)
2. Datei in PyCharm bearbeiten → `Ctrl+S`
3. marimo lädt **automatisch** nach (`auto_reload = "autorun"`)
4. Nur betroffene Zellen werden im Browser re-run – kurz warten
5. Fertig – kein Neustart, kein Tab-Schließen nötig

### Fall B: Notebook-Datei ändern (`Notebooks/02_Signal_Lab.py`) – ZELLSTRUKTUR

> z. B. Zellen umbauen, `@app.cell`-Attribute ändern, neue Zelle einfügen

⚠️ **WICHTIG:** Der laufende Server hat den alten Dateistand im Speicher.
Wenn du jetzt im Browser speicherst, überschreibt er deine Änderung!

**Ablauf (sicher):**
1. **Browser-Tab schließen** (Session beenden) – optional: `stop_marimo.ps1`
2. Datei in PyCharm / Continue / per Skript ändern → `Ctrl+S`
3. **CRLF beachten!** Notebook-Dateien nur mit `newline=""` schreiben (Python-Skript), nie mit Edit-Tools, die LF erzwingen
4. Syntax-Check: `.venv\Scripts\python.exe -m py_compile Notebooks/02_Signal_Lab.py`
5. Server neu starten:
   - `stop_marimo.ps1` (falls nicht schon gestoppt)
   - `start_marimo.ps1`
6. Fertig – Browser zeigt den neuen Stand

### Fall C: UI-Design im Browser (Widgets, Layout)

> Zellen direkt im marimo-Editor anpassen

1. Im Browser editieren
2. **`Ctrl+S` drücken** (Autosave ist OFF – ohne Speichern geht nichts auf die Platte!)
3. Datei auf Platte ist jetzt aktuell – mit PyCharm weiterarbeiten

---

## 3. Manuelle Einstellungen (einmalig, durch dich)

### 3.1 PyCharm: automatisches Speichern beim App-Wechsel deaktivieren

PyCharm speichert standardmäßig beim Verlassen des Fensters – das kann mit
einem offenen marimo-Browser kollidieren (Platte → Browser-Re-Run → Konflikt).

```
File → Settings → Appearance & Behavior → System Settings
  ☐ "Save files when switching to a different application"   (ABWÄHLEN)
  ☐ "Save files automatically if the application is idle"    (optional abwählen)
```

Danach speichert PyCharm nur noch bei `Ctrl+S` – volle Kontrolle.

### 3.2 Firefox: Tab-Handling

- **Alte Tabs schließen** (Session-ID-Problem: ein alter Tab mit abgelaufener
  Session verursacht `ValueError: Invalid session id` im Server-Log und
  Klicks werden verworfen → Buttons wirken tot)
- Nach externen Änderungen: Tab schließen, Server neu starten (Fall B)

### 3.3 Sicherheitsnetz: PyCharm Local History

Falls doch etwas überschrieben wird:

```
Rechtsklick auf Datei → Local History → Show History → älteren Stand wiederherstellen
```

---

## 4. Kurz-Referenz (Cheat-Sheet)

| Situation | Aktion |
|---|---|
| Logik in `signal_lab/*.py` geändert | nur `Ctrl+S` in PyCharm – läuft automatisch nach |
| Notebook-Datei extern geändert | Tab schließen → `stop_marimo.ps1` → `start_marimo.ps1` |
| Im Browser editiert | `Ctrl+S` (sonst geht nichts auf die Platte) |
| Buttons reagieren nicht | Firefox-Tab komplett schließen → Server neu starten |
| Weiß nicht, ob Datei korrekt ist | `git diff Notebooks/02_Signal_Lab.py` + `py_compile` |
| Datei wurde überschrieben | PyCharm → Local History → wiederherstellen |

---

## 5. Hinweise zur externen Analyse (geprüft)

| Behauptung aus der Analyse | Bewertung |
|---|---|
| marimo erzwingt Zwei-Wege-Sync / überschreibt Dateien | **Teilweise:** nur mit `--watch` (entfernt) oder Autosave (jetzt OFF). Server ist jetzt passiv |
| `marimo run` schreibt nichts zurück | ✅ korrekt, **aber:** Buttons/Slider sind im App-Modus NICHT interaktiv → fürs Signal Lab ungeeignet, nur als statischer View |
| Autosave auf "Off" stellen | ✅ umgesetzt (`[save] autosave = "off"`) |
| `importlib.reload()` in Setup-Zellen | ❌ unnötig – `auto_reload = "autorun"` macht das automatisch und reaktiv |
| PyCharm "Save files when switching to a different application" abwählen | ✅ sinnvoll – siehe Schritt 3.1 |
| Local History als Rettung | ✅ sinnvoll – siehe Schritt 3.3 |
| `plt.close('all')` in Plot-Zellen | ✅ optional sinnvoll (verhindert gecachte Figuren) |
