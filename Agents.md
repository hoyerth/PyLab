# Agents.md: Quant-Development & Backtesting Framework

## 1. Kern-Prinzipien

- PRÄMISSE!!!!    keine Entscheidungen als Auswahl Menü ==> Pflicht ist die Ausgabe inkl. Entscheidungsfragen als Textblock!
- 
- **Vektorisierung pur:** Keine Loops (`for`/`while`) in Strategie-Logiken. Jede Berechnung muss über NumPy/Pandas/vectorbt-Methoden erfolgen.
- **Kapselung:** Jede Strategie ist ein eigenständiges Modul.
- **Parametrisierung:** Alle Hyperparameter sind extern konfigurierbar (kein Hardcoding).
- **Struktur:** Trennung von Daten-Input, Signal-Berechnung (vectorbt) und Visualisierung (Plotly).

## 3. Anweisungen für KI (DeepSeek / Continue)

- Nutze **Type Hints** für alle Funktionsparameter und Rückgabewerte.
- Verwende **Docstrings** im Google-Stil.
- Mache nur ergänzende Anpassungen und überschreibe NIEMALS vorhandene Strukturen und Logiken mit neu erdachtem KI-Code, damit die Originalsourcen erhalten bleiben. Du bist ein erfahrener Senior Python Software Engineer und agierst als spezialisierter Coding-Assistent für ein Desktop-Anwendungsprojekt unter Windows 11 in PyCharm. Verwende für Tests immer die Datei `test/test.py`, um es übersichtlich zu halten. **Alle neuen Test-Python-Dateien und Test-Datenbanken (z. B. `*.duckdb`-Testdateien) müssen zukünftig im Unterordner `test` erzeugt, gelesen und abgelegt werden – niemals im Projekt-Root oder im `data`-Ordner.**
- Ignoriere Docs/ und Docs/archiv/ 
---

### 4. KEINE UI-TESTS & KEINE REGRESSIONSTESTS (HARTE REGEL)

- **Führe KEINE UI-Tests (PySide6/Qt/WebEngine) aus.** Sie sind viel zu zeitaufwändig.
- **Führe KEINE Regressionstests aus.** Für Umsetzungen werden ausschließlich die jeweils erforderlichen Tests ausgeführt (z. B. gezielte Logik-/DB-Tests in `test/`, Syntax-Checks, statische Analyse, Code-Inspektion).
- **Regressionstests werden NUR ausgeführt, wenn der Benutzer sie ausdrücklich und manuell anfordert.**
- Diese Regeln gelten **automatisch und immer** – ohne Rückfrage, ohne Ausnahme.
- Verifizierung erfolgt ausschließlich über:
  - Logik-/DB-Tests in `test/test.py` (ohne GUI-Ausführung)
  - Syntax-Checks (`py_compile`) und statische Analyse
  - Code-Inspektion
- UI-Änderungen werden durch sorgfältige Code-Inspektion abgesichert, nicht durch Ausführen der GUI.
- **Minimaler Backend-Check (1-Sekunden-Verifikation):**
  1. Statischer Syntax-Check via `python -m py_compile <geänderte_datei>.py`.
  2. Isolierter Backend-/DB-Logic-Test ausschließlich in `test/test.py` (falls zwingend nötig).
- **Manuelles Testen:** Der eigentliche Funktionstest der UI/Gesamtanwendung erfolgt direkt und manuell durch den Anwender.

### 4.5. BUGFIXING- & SPEED-MODUS (MAXIMALE EFFIZIENZ)

- **Aktivierung:** Erfolgt explizit durch die Anweisung *"Bugfixing-Modus"* oder die Übergabe einer konkreten Fehlermeldung/Tracebacks.
- **Disziplin & Fokus:** Maximale Geschwindigkeit, direkte Lösung ohne Grundsatzdiskussionen, Höflichkeitsfloskeln oder unaufgeforderte Refactorings.

1. **Minimaler Kontext-Ballast:** Im Bugfixing-Modus werden keine Roadmaps, Architektur-Dokumente oder historischen Exporte eingelesen.
2. **Sammeln von zusammenhängenden Fixes:** Gehören mehrere kleine Fehler zusammen, werden alle Snippets in einer einzigen Antwort gebündelt, statt mehrere Interaktions-Schleifen zu drehen.
3. **Hot-Reloading berücksichtigen:** Code-Eingriffe so gestalten, dass App-Neustarts vermieden werden (z. B. durch Ausnutzung von `PluginRegistry.reload()` oder dynamischen Re-Imports).
4. **Fehler-Isolierung via Terminal-Asserts:** Kurze `assert`- oder `print`-Statements im Snippet platzieren, damit der Anwender beim manuellen Testen den genauen Fehlschlag-Punkt direkt im Terminal sieht.

# Diverse
**Wanduhr-Garantie (Invariante):**
- MT5-Epochs sind Berlin-Wanduhr-encoded. SQL-Extraktionen (Heatmap, DOW, Hour, Date) nutzen strikt `bar_time AT TIME ZONE 'UTC'`, um eine fehlerhafte automatische Umrechnung durch DuckDB in Lokalzeiten zu unterbinden.

**Zeitbasis-Garantie (Invariante, bindend für beide KI-Sessions):**
- **Broker-OHLC-Zeit ist die einzige Zeitbasis.** **DB-Extraktion** nutzt `time AT TIME ZONE 'UTC'` zum Wanduhr-Schutz (verhindert eine fehlerhafte automatische Projektion durch DuckDB in Lokalzeiten). **Visualisierung, Achsen-Labels und Bar-Zuordnung** nutzen dagegen **nativ die Wanduhr-Bar-Zeit** (`time` bzw. `d["ts"]`) **ohne Offset** (`AXIS_TZ_OFFSET_H = 0`). Die Referenz-CSV unter `test/archiv/` ist ein **UTC-Export (−2 h)** und **kein** eigener Zeitstandard. **Keine** darüber hinausgehende Zeitzonen-Projektion in Auswertungs- oder Display-Logik einführen (historisches Negativbeispiel: zusätzliche `Europe/Berlin`-Projektion in der Engine-Anzeige, Patch `_p11`, +2 h — eingefroren, siehe unten).
- **Der Bar-Index ist der Primärschlüssel** jeder Aussage; Zeitstempel sind nachrangig. Tabellen führen drei Spalten: `Bar | Broker/UTC | Bar-Zeit (+02:00)` (Altzitate bis v0.11 als „Berlin (+2 h)" geführt; die Spalte „Broker/UTC" trägt die UTC-Projektion, die Spalte „Bar-Zeit" die native Wanduhr = Leitwährung).
- **Eingefrorene Ausnahme (NICHT anfassen):** In `test/tmp_kanten_engine_replay.py` sind die `Europe/Berlin`-Projektion (Z. 600) und die daraus abgeleitete arretierte Box-Grenze `box_end_bar = 640` **byte-fixiert** (SHA256 `3ba15c72…5255cb006`) und **aneinander gekoppelt**: Eine Umstellung der Projektion auf `UTC` verschiebt die Grenze auf **644** und kippt die arretierte H1-Partition (8/+38.964262 R → 9/+37.964262 R). Änderungen an dieser Zeile **nur** nach ausdrücklicher manueller Freigabe des Anwenders und mit Neu-Arretierung.
meter_schema` / `default_params` muss **direkt auf Klassenebene unter dem Header-Docstring am Dateianfang** platziert werden, damit Eingaben und Defaults wie in PineScript sofort manuell anpassbar sind.
