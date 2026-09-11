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
- Ignoriere Docs/ und Docs/archiv/ — **einzige Ausnahme: `docs/ZEITBASIS_KANON.md`** (verbindliche SSoT der Zeitbasis, immer zuerst lesen).
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
**Zeitbasis-Kanon (Invariante, bindend — SSoT: `docs/ZEITBASIS_KANON.md`):**
- **Broker-Kerzen-Zeit (BKZ) = `time AT TIME ZONE 'UTC'`** ist die **einzige Rechenbasis** — für Fenster, Kalendergrenzen, Achsen, Tabellen, Labels und Bar-Zuordnung. Extrakionsmuster strikt wie im Kanon (§K4).
- **`Europe/Berlin` / `Europe/Budapest` sind reine Anzeige-Dubletten** — **nie** Rechenbasis, **nie** in `WHERE`/`searchsorted`/`floor`/`resample`. Keine Zeitzonen-Projektion in Auswertungs- oder Display-Logik.
- **Der Begriff „Wanduhr" ist projektweit verboten** (historisch doppelt belegt: rohe Kerzenzeit *und* Berlin-Projektion). Ebenso verboten: nacktes `SELECT time` (DuckDB-Session-TZ = `Europe/Budapest` ⇒ maschinenabhängig).
- **Kalendergrenzen werden dynamisch abgeleitet**, nie als Bar-Konstante hartcodiert: `searchsorted(ts_bkz, "<datum>")`. AUG: `"2026-08-19"` ⇒ Bar **644**.
- **Der Bar-Index ist der Primärschlüssel** jeder Aussage; Zeitstempel sind nachrangig. Dreispaltige Konvention: `Bar | Broker-Kerzen-Zeit (BKZ) | Anzeige (+02:00)`.
- **Eine Zeitbasis pro Datei.** Migrationsmatrix (V017 → V018), Verbotsliste und Prüfkriterien: `docs/ZEITBASIS_KANON.md` — **verbindlich, dort zuerst lesen**.

**Darstellungs-Garantie (Invariante, FIX für alle Sichtprüfungs-Grafiken):**
Spiegelspez: `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` §54 (Regelwerk) und §55 (Konsolidat der anwendersetigen Standards).
- **Preis am Label:** Jedes Kanten-Label trägt den **kausalen** Preis `basis_bei(k)` — Format `K<kid> <preis>` (Seeds `s<kid> <preis>`). Die statische Provenienz `e.basis` wird **nie** als Linienniveau oder Labelpreis gezeichnet.
- **Preiswechsel:** Ändert sich der Preis entlang der Linie → Label `K<kid> <v_start> -> <v_ende> *` (fett, Rahmen `#b8860b`) plus Kleintext an jedem Wechselpunkt an Grenzkanten/Detailpanel.
- **Norm bleibt Zitat (Option (b)):** Abweichende v0.4-Provenienz-Norm wird **angehängt, nicht ersetzt** (`… * Norm 67.6355`); Norm-Quelle ist ausschließlich der Adapter, kein Hardcoding.
- **Linien kausal** (`basis_bei(k)` je Bar, Treppe, maskiert vor Pivot + 2), **Kerzen** überall, **Trade-Kreise immer farbig gefüllt** (`mfc=col`), **X-Achse = Bar-Zeit ohne Offset**, **Sperr-Marker violett** (`x` = Q29, `^` = M6, am sperrenden Bar), **Statistik mittig**, **Legende oben links**, **Titel** `Bars 0..1287`.

meter_schema` / `default_params` muss **direkt auf Klassenebene unter dem Header-Docstring am Dateianfang** platziert werden, damit Eingaben und Defaults wie in PineScript sofort manuell anpassbar sind.
