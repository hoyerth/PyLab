# Konzept: Signal Lab v2 – Massentests & Konfluenz-Pipeline

## 1. Vision

Massenhafte, reproduzierbare Indikator-Tests auf einer einheitlichen Engine. Der
Start erfolgt mit dem MA-Indikator, die Architektur ist aber von Beginn an auf
**beliebig viele Indikatoren ausgelegt** (jeder Indikator in einer eigenen
Signal-Lab-Zelle). Ziel ist es, **sich gegenseitig ergänzende Signale** zu
finden, deren gemeinsames Auftreten später per ML als **%-Konfluenz-Hinweis am
Livekurs** genutzt wird.

## 2. Leitprinzipien

- **Single Source of Truth bleibt:** `compute() → IndicatorResult → SignalEvents`
  (RAM für visuell, DuckDB für Analytics) wird nicht angefasst.
- **Klick statt Tippen:** Symbole, Timeframes und Parameter-Ranges werden über
  UI-Elemente gesetzt, nicht per Code.
- **Reproduzierbarkeit:** Jeder Lauf bekommt einen **prägnanten Namen** mit
  Zeitstempel + Parameter-Kurzform → spätere Auswertung ohne Rückfragen.
- **Skalierbarkeit:** Neue Indikatoren werden als parallele Zellen ergänzt,
  ohne die bestehende Pipeline zu verändern.
- **Vektorisierung:** Die Berechnungslogik ist **immer vektorisiert** (NumPy/
  pandas-Serien, keine Zeilen-Schleifen) und wird von Anfang an **auf VectorBT
  abgestimmt** – d. h. Input/Output-Formate (OHLCV-Spalten, Signalfolgen,
  Zeitindex) sind kompatibel mit VectorBT-Signalen (`[1, -1, 0]`), damit
  Massentests später nahtlos in Backtests übergehen. Ausnahme: Pine-Script-
  getreue 1:1-Rekursionen (z. B. EMA/HMA), die nur als gekapselte Hilfs-
  funktion erlaubt sind.
- **Schlanke Notebooks:** Längere Logikzeilen werden in **Python-Dateien im
  Projekt** ausgelagert – mit sinnvollen Ordnern und sprechenden Namen
  (z. B. `algos/` für Indikatoren, `algos/chart_plugins.py` für Rendering,
  neu z. B. `signal_lab/` für UI+Orchestrierung). Das Notebook enthält nur
  UI-Definition, Aufrufe und Anzeige – nie die Logik selbst.
- **Trennung:** Statistik/ML gehört in ein eigenes Notebook – Signal Lab bleibt
  reine Test- und Datenerzeugungs-Plattform.

## 3. UI-Konzept Signal Lab (einfach, eine Bildschirmseite)

Layout von oben nach unten, bewusst ohne Tabellen-Overkill:

```
┌───────────────────────────────────────────────────────────────────────┐
│  KONFIGURATION                                                        │
│  [🟢 SILVER] [⭐ GOLD] [BTCUSD] ...   <- Favoriten-Symbole (Buttons)   │
│  [M1] [M5] [M15] [M30] [H1] [H4] [D1] ...  <- verfügbare TF (Buttons)  │
│                                                                       │
│  MA-Parameter-Ranges        │  VectorBT-Parameter-Ranges             │
│  ma_type: [EHMA▾]           │  spread:  min/step/max                  │
│  period:  min/step/max      │  SL (%):  min/step/max                  │
│  smoothing: min/step/max    │  TP (%):  min/step/max                  │
│  alpha_factor: min/step/max │  Position/Größe:  min/step/max          │
│                              │  Fees/Slippage:  min/step/max           │
│                                                                       │
│  Datumsbereich:  [Von ▾]  bis  [Bis ▾]   (aus verfügbaren Kerzen)     │
│                                                                       │
│  Run-Name (optional übersteuerbar)                                    │
│  [EHMA_p6_s10_a3_SILVER_M30_20260821_1435  ✏️]                        │
│                                                                       │
│  [ 🚀 GO — Massentest starten ] (X Runs)  <- Sicherheitsabfrage vor Ausf.│
│                                                                       │
│  QUICK LOOK (Schnell-Sicht, Chart aus dem Inspector)                  │
│  [ Symbol:TF  ─ SILVER:M30 ─ ]   <- Eingabezelle direkt über Grafik  │
│  [ ──────────── Chart mit Signalen ──────────── ]                     │
│     M30-Signale + höhere TFs (H1/H4/D1) farbcodiert                   │
└───────────────────────────────────────────────────────────────────────┘
```

- **Symbole:** kommen aus `app_data.broker_symbols` (is_favorite = ⭐),
  Klick = Auswahl (Mehrfachauswahl möglich).
- **Timeframes:** werden aus den tatsächlich in `market_data` vorhandenen
  Symbol/TF-Kombinationen gefiltert (kein Leerlauf bei fehlenden Daten).
- **Parameter-Ranges:** je Parameter `min / step / max` → erzeugt einen
  Parameter-Raum als Kreuzprodukt (Grid) oder Stichprobe (Random Search).
- **Datumsbereich:** Dropdown/Datepicker, begrenzt auf die in der DB
  verfügbare Spanne; Warmup wird automatisch vorgehalten.
- **GO-Button:** Sicherheitsabfrage (Modal: „X Läufe · Y Parameter-Kombis ·
  Symbol/TF … wirklich starten?"), plus Abbruch während des Laufs.
- **Run-Zähler neben dem GO-Button:** Live wird die Anzahl der Runs angezeigt,
  die sich aus den aktuellen Kombis ergeben (Symbole × TFs × Parameter-Raum).
  Der Zähler aktualisiert sich bei jeder Änderung an der Konfiguration und
  macht vor dem Start sofort klar, wie groß der Sweep wird.
- **Quick Look:** siehe §7 – das Chart-Ausgabefenster liegt unterhalb der
  Konfiguration, nutzt das bewährte Rendering aus dem Chart Inspector und
  dient dem schnellen visuellen Eindruck vor/neben dem Massentest.

## 4. Run-Orchestrierung (Logik, noch keine Umsetzung)

Die gesamte Orchestrierung liegt **nicht im Notebook**, sondern in
Projekt-Modulen (z. B. `signal_lab/`): `run_definition`, `sweep_runner`,
`naming`, `ui_state` – das Notebook ruft nur noch auf. Die Ausgaben sind
**von Anfang an VectorBT-kompatibel** (Signalfolgen als `[1, -1, 0]` mit
UTC-Zeitindex, OHLCV im VectorBT-Format), damit der spätere Backtest-Anschluss
ohne Umbau möglich ist.

1. Aus den UI-Auswahlen wird eine **Run-Definition** gebaut:
   - Symbole × Timeframes × Parameter-Raum × Datumsbereich
2. Pro Kombination:
   - `compute(df)` → `IndicatorResult`
   - optional später: VectorBT-Backtest mit spread/SL/TP/Position
   - Events + Backtest-Ergebnis → **Batch** in `analytics_data`
3. Jede Kombination erhält eine `run_id` (Hash) **und** einen sprechenden
   `run_name` (siehe §5). Identische Wiederholung bleibt idempotent
   (bestehender Composite-PK).
4. Fortschrittsanzeige (läuft/fertig/fehlgeschlagen) während des Sweeps.

**Parallele Verarbeitung (Empfehlung):**
- **Multiprocessing auf Batch-Ebene** (Chunking der Parameter-Sets über die
  CPU-Kerne): die Parameter-Sets werden in Chunks aufgeteilt, jeder Worker
  berechnet seinen Chunk vollständig im RAM.
- **Persistierung nach Chunk-Ende** in DuckDB (nicht pro Einzel-Run): so
  werden DB-Write-Locks vermieden und der I/O-Overhead minimiert.
- Sequenzieller Modus (mit Fortschrittsanzeige) bleibt als Fallback für
  Debugging/kleine Sweeps.

## 5. Run-Namensschema (Vorgabefunktion)

Formatvorschlag (sortierbar, eindeutig, kompakt):

```
{INDIKATOR}_{PARAM-KURZ}_{SYMBOL}_{TF}_{JJJJMMTT}_{HHMM}
```

Beispiele:
- `EHMA_p06_s10_a3.0_SILVER_M30_20260821_1435`
- `EHMA_p12_s10_a2.0_GOLD_H1_20260821_1435`

Regeln:
- Parameter-Kurzform folgt festem Schema (z. B. `p{period}_s{smoothing}_a{alpha}`).
- Zeitstempel = Start des Runs (lokal), damit Läufe chronologisch sortierbar sind.
- Der Name ist **standardmäßig vorgegeben**, kann im UI aber übersteuert und
  mit einem freien Tag (z. B. „batch-01-swing") ergänzt werden.
- `run_name` wird in `indicator_runs` gespeichert (neue Spalte), `run_id`
  bleibt der technische Hash.

**HTF-Läufe mit exaktem Auslösezeitpunkt:**
- Bei einem Run auf einem höheren TF (z. B. H1) kann die Indikator-Logik
  zusätzlich auf dem kleineren TF (z. B. M15) ausgeführt werden.
- Das Ergebnis wird mit dem **exakten Auslösezeitpunkt** im Signal gespeichert
  (siehe §7 und §9) – nicht nur mit dem HTF-Bar-Zeitstempel.
- Die spätere Statistik muss damit umgehen können: pro Signal sind der
  „große" TF (Run-TF) und der exakte Zeitpunkt auf dem kleinen TF bekannt.

## 6. Mehrere Indikatoren / Zellen

- Jeder Indikator bekommt eine **eigene Zelle** mit eigenem Parameter-Block.
- Die UI-Felder (Symbole/TF/Datum/VectorBT) sind **geteilt** (gemeinsamer
  Konfigurations-Kontext), die Indikator-Ranges sind **pro Zelle**.
- Alle Zellen erzeugen weiterhin normalisierte `SignalEvent`s → Konfluenz
  und ML können sie direkt gemeinsam auswerten.

## 7. Schnell-Sicht: Chart-Ausgabefenster (Quick Look)

Das Chart-Rendering aus dem **Chart Inspector** wird im Signal Lab als
**Ausgabefenster wiederverwendet** – rein visuell, **nur Charts und Signale**,
keine Parameter-Tabellen, keine Statistik. So bekommt man vor/neben dem
Massentest sofort einen Eindruck, wie die gewählten Einstellungen im Chart
aussehen.

**Eingabezelle direkt über der Grafik**
- Eine kompakte Zelle unmittelbar über dem Chart mit Eingabeformat
  `Symbol:TF` (z. B. `SILVER:M30`, `GOLD:H1`).
- Die in der Konfiguration gewählten Symbol/TF-Buttons übernehmen den Wert;
  eine manuelle Eingabe überschreibt ihn **nur für die Chart-Sicht**
  (der Massentest nutzt weiterhin die Konfiguration).
- Eingabe mit Enter/Auswahl → Chart rendert sofort.

**Verschiedene Zeichendarstellungen je Indikator (Marker-Shapes)**
- Jeder Indikator-/Signaltyp erhält eine **eigene Zeichendarstellung** in der
  Chart-Auswahl, damit sich die Signale verschiedener Indikatoren klar
  unterscheiden lassen:
  - `swing_change` (MA) → Pfeile ▲/▼
  - `circle_yellow` / `circle_fuchsia` (Grid) → Kreise (gelb / fuchsia)
  - zukünftige Indikatoren → z. B. Dreiecke, Kreuz ✕, Quadrat ■, Diamant ◆,
    X-Marker, Balken
- Das Mapping `Signaltyp → Shape/Farbe` wird **einmalig zentral definiert**
  (Styling-Registry in `plot_meta`) und von Chart-Engine und späterer
  Live-Anzeige gemeinsam genutzt.

**Signale höherer Timeframes im Chart (Multi-TF-Overlay)**
- Idee: Im Chart eines TF (z. B. M30) werden zusätzlich die **Signale
  höherer Timeframes** (H1, H4, D1) angezeigt – so sieht man sofort, ob
  der Trend „von oben" bestätigt wird.
- **Anzeige zum Auslösezeitpunkt:** HTF-Signale werden möglichst **genau zum
  Auslösezeitpunkt auf dem kleineren TF** platziert – nicht nur am HTF-Bar-
  Anfang. Exakt ist das nicht möglich (der HTF-Bar kennt keinen Intra-Bar-
  Zeitstempel), aber die Annäherung ist gut: z. B. der kleinere-TF-Bar, in
  dem der HTF-Close/High/Low erreicht wurde (Kursdurchbruch).
- **Automatische Farbvariation:** Je höher der TF, desto intensiver/anderer
  Farbton – z. B. M30 = hell, H1 = mittel, H4 = dunkel, D1 = kräftig
  (fest definierte TF-Farbpalette, automatisch zugewiesen).
- Darstellung: Höhere-TF-Signale erscheinen **versetzt über/unter** den
  M30-Signalen (separater Marker-Slot bzw. Y-Versatz), sodass beide Ebenen
  gleichzeitig sichtbar sind.
- **Konfluenz sofort sichtbar:** Wenn mehrere TFs in dieselbe Richtung
  signalisieren, „stapeln" sich die Marker → schneller Eindruck der
  Multi-TF-Stärke. Genau diese Gleichzeitigkeit ist später ein zentrales
  ML-/%-Konfluenz-Merkmal.

**Grafik-Begrenzung wie im Chart Inspector:**
- Die Quick-Look-Grafik ist **genauso gestaltet und begrenzt wie im Chart
  Inspector**: sichtbares Fenster (z. B. 1000 Kerzen) + Warmup, Scrolling
  per Slider – **keine 10k-Kerzen-Gesamtansicht**.
- Auch die Multi-TF-Daten werden nur für das sichtbare Fenster (+ Warmup)
  geladen und angezeigt.

## 8. Konfluenz & ML (später, eigenes Notebook)

- **Konfluenz ist bewusst erst ein Thema des späteren Statistik-Notebooks.**
  Das Signal Lab bereitet nur die Daten vor (exakte Zeitpunkte, HTF-Referenz),
  wertet aber selbst keine Konfluenz aus.
- **Konfluenz-Zähler:** pro Zeitpunkt, wie viele Indikatoren gleichzeitig in
  dieselbe Richtung signalisieren (z. B. 2 von 3) → **%-Confluence**.
- **ML-Modul (separates Notebook):** trainiert auf `signal_events` (+ Labels/
  Ergebnisse), erkennt Muster der sich ergänzenden Signale und liefert am
  **Livekurs** Hinweise inkl. Konfluenz-Prozentsatz.
- Signal Lab liefert dafür nur die **sauberen, benannten Daten** – keine
  Auswertung im selben Notebook.

## 9. Datenmodell-Erweiterung (Vorschlag)

- `indicator_runs` + Spalte `run_name VARCHAR` (sprechender Name).
- `signal_events` + Spalte `source_tf VARCHAR` (der TF, aus dem das Signal
  stammt – z. B. `H1`) sowie `signal_time` (exakter Auslösezeitpunkt auf dem
  kleineren TF, wenn HTF-Logik auf kleinem TF gelaufen ist). Die Statistik
  kann damit präzise auswerten: „H1-Signal, ausgelöst exakt am 14.08. 10:47".
- Optional Tabelle `run_sweeps` (Batch-Metadaten: gewählte Ranges, Zeitstempel,
  Anzahl Läufe) für spätere Nachvollziehbarkeit kompletter Sweeps.
- Optional Tabelle `backtest_results` (pro Run: spread/SL/TP/Größe/Equity-
  Kennzahlen), sobald VectorBT integriert wird.

## 10. Bewertung

**Stärken**
- Baut auf bewährter, getesteter Engine auf (kein Bruch der bestehenden Pfade).
- UI senkt die Hemmschwelle für Massentests massiv (Klick statt Skript).
- Sprechende Run-Namen machen tausende Läufe später auswertbar.
- Mehrfach-Indikator-Konzept ist architektonisch vorbereitet (parallele Zellen,
  gemeinsame Events).
- Quick Look macht die Auswahl sofort visuell prüfbar (Chart + Signale direkt
  im Signal Lab); Multi-TF-Overlay liefert den Konfluenz-Eindruck schon vor
  dem Massentest.
- Vektorisierte, VectorBT-abgestimmte Logik in Projekt-Modulen → Notebook
  bleibt schlank, Backtest-Anschluss ist ohne Umbau vorbereitet, Logik ist
  testbar und wiederverwendbar.

**Schwächen / Risiken**
- Parameter-Raum wächst exponentiell (Symbole × TF × Ranges) → Gefahr von
  Laufzeiten im Stundenbereich; **Grid vs. Random**-Strategie muss wählbar sein.
- VectorBT-Parameter (spread/SL/TP) benötigen ein Backtest-Modul; bis dahin
  sind diese Ranges wirkungslos → UI sollte sie zunächst „deaktiviert" zeigen.
- Konfluenz über mehrere Indikatoren braucht eine gemeinsame Zeitachse
  (Resampling auf einheitliches TF-Raster) – offener Designpunkt.
- DB-Schema braucht eine Migration (run_name); bestehende `analytics_data`
  muss sauber erweitert werden.
- Multi-TF-Overlay: Marker-Stapelung kann bei vielen TFs unübersichtlich
  werden → TF-Auswahl für das Overlay begrenzen (z. B. max. 3 höhere TFs,
  nur „bestätigende" Signale).
- Quick Look lädt zusätzliche Daten (mehrere TFs) → für die Chart-Sicht
  gezielt begrenzen (Fenster, nicht Gesamthistorie).

**Offene Entscheidungen**
- Grid-Search, Random-Search oder beides (Umschalter)?
- Parallele Verarbeitung: **Empfehlung getroffen** – Multiprocessing auf
  Batch-Ebene (Chunking über CPU-Kerne), Persistierung nach Chunk-Ende in
  DuckDB (vermeidet DB-Write-Locks); sequenziell als Fallback.
- Konfluenz-Definition: wird erst im Statistik-Notebook festgelegt (gleicher
  Bar vs. kumulatives Fenster) – Signal Lab liefert dafür die präzisen
  Zeitpunkte (exakter Auslösezeitpunkt auf kleinerem TF).

## 11. Letzte Einstellungen merken (Persistenz des aktuellen Stands)

- **Alle UI-Felder und Toggle-Buttons** merken sich den letzten Stand:
  - ausgewählte Symbole & Favoriten
  - gewählte Timeframes
  - MA-Parameter-Ranges (min/step/max je Parameter + ma_type)
  - VectorBT-Parameter-Ranges (auch wenn aktuell deaktiviert)
  - Datumsbereich (Von/Bis)
  - übersteuerter Run-Name / freier Tag
  - Optionen wie Grid/Random-Umschalter (sobald vorhanden)
  - Quick Look: zuletzt eingegebenes `Symbol:TF` + gewählte Overlay-TFs
    (höhere Timeframes, sobald Multi-TF-Overlay existiert)
- **Speicherung:** bewusst einfach – **eine JSON-Datei im Projekt**
  (z. B. `data/ui_state.json`). Kein DB-Zugriff, keine Migration, sofort
  einsatzbereit, versionierbar. (Eine DB-Tabelle ist bewusst nicht nötig.)
- **Verhalten:**
  - Beim Öffnen des Signal Lab werden alle Felder mit dem gespeicherten Stand
    vorbelegt (kein Reset beim Neustart)
  - Der Stand wird bei jeder Änderung bzw. spätestens beim GO-Start aktualisiert
- **Presets / Profile kommen später** (z. B. „Batch-01 Swing", „Scalping M1",
  „Trend H1"): benannte, wiederherstellbare Gesamt-Konfigurationen.
  - **Jetzt:** nur der aktuelle Stand wird gemerkt – kein Profil-Management,
    kein UI dafür.
- Bewusst minimal: ein kleiner Persistenz-Speicher, kein Migrationsaufwand.

## 12. Nächste Schritte (Schlagworte, bewusst ohne Anleitung)

Projekt-Struktur (`signal_lab/`-Module) → UI-Zellen (schlank, nur Aufrufe) →
Run-Zähler (Kombis) → Run-Definition → Orchestrator (Multiprocessing/Chunks) →
Namensschema → Schema-Migration (run_name, source_tf/signal_time) →
UI-State-Persistenz (JSON-Datei) → Fortschrittsanzeige → Sicherheitsabfrage →
Quick Look (Symbol:TF-Zelle, Marker-Shapes-Registry, Multi-TF-Overlay mit
Auslösezeitpunkt-Annäherung, Fensterbegrenzung wie Inspector) →
VectorBT-Abstimmung (Signalfolge-Format verifizieren) →
(danach: Presets/Profile, Backtest-Modul, Statistik-Notebook inkl. Konfluenz,
ML-Konfluenz).

---

# Schritt-für-Schritt-Anleitung: Signal Lab v2

**Geltungsbereich:** Umsetzung des Konzepts (UI, Run-Orchestrierung,
Persistenz, Quick Look). **Nicht enthalten:** Statistik/ML-Notebook,
Presets/Profile, VectorBT-Backtest-Modul (kommen später).

> **Wichtige Anweisung (21.08.2026):** VectorBT & Order-Testing gehören in ein
> **separates Notebook** (nicht in `02_signal_lab.py`). Das Signal Lab bleibt
> reine Test-/Datenerzeugungs-Plattform. Die (ehemals deaktivierten)
> VectorBT-Ranges wurden aus UI und `ui_state` entfernt.

**Fortschritt (Stand 2026-08-21):**
- Phase 0 ✔ (Bestand, Composite-PK) · Phase 1 ✔ (`signal_lab/`) ·
  Phase 2 ✔ (Migration run_name/source_tf/signal_time) ·
  Phase 3 ✔ (UI-State-JSON) · Phase 5 ✔ (Run-Definition/Zähler) ·
  Phase 6 ✔ (Run-Namensschema) · Phase 7 ✔ (Sweep sequenziell + parallel,
  idempotent, HTF-Exact-Time)
- **Phase 4 ✔ (UI-Zellen):** `02_signal_lab.py` schlank umgebaut –
  Symbol-/TF-Multiselect, MA-Ranges, Strategie/Datum/HTF/Run-Name,
  Run-Zähler + GO/Stand-speichern, Sweep-Ausführung mit `last_sweep`-
  Persistenz, Quick-Look-Platzhalter. **VectorBT-Ranges entfernt**
  (kommt in separates Notebook).
  `build_run_definition(..., fixed_params={"ma_type": ...})` ergänzt.
- **Phase 8 ✔ (Sicherheit + Fortschritt + Abbruch):** `sweep_ui.py`
  (thread-sicherer Lauf-Status) + GO→Bestätigungsdialog („X Läufe …
  wirklich starten?"), Sweep im Hintergrund-Thread (UI bleibt reaktiv),
  Live-Fortschrittsbalken + aktueller Run-Name über `mo.ui.refresh`,
  Stopp-Button (`cancel_callback` im Runner → bereits persistierte Runs
  bleiben idempotent in der DB, Rest wird verworfen).
- **Phase 9 ✔ (Quick Look):** `signal_lab/quick_look.py` (Wrapper um
  chart_engine) + Marker-Shapes-Registry in `chart_plugins.py`
  (Signaltyp → Shape/Farbe, TF-Farbpalette, Stacking-Versatz). UI-Zellen:
  `Symbol:TF`-Eingabe, HTF-Overlay-Multiselect (max. 3), Fenster-Slider,
  M30-Signale + H1/H4-Signale zum Auslösezeitpunkt angenähert (letzter
  kleiner-TF-Bar im HTF-Intervall), farbcodiert + versetzt gestapelt.
  Getestet: 68 M30-Events + 32 H1 + 8 H4, Marker-Farben korrekt.
- **Phase 10 ✔ (VectorBT-Abstimmung):** `to_events_frame()` liefert UTC-
  Index + direction `[1,-1,0]`; OHLCV-Spalten `open/high/low/close` auf
  UTC-Index → Events 1:1 als VectorBT-Signal interpretierbar (63 Long/63
  Short im Test). **Hinweis:** Verifikation nur – das VectorBT/Order-Testing
  selbst folgt in einem separaten Notebook.
- **Phase 11 ✔ (End-to-End-Abnahme):** Echter Sweep gegen `market_data`/
  `analytics_data`: 2 Runs, 14.002 Events, 2. Sweep idempotent,
  `run_name` gefüllt (`…_20260821_1436_p11-abnahme`). HTF-Exact-Time:
  H1-Run mit M15-Logik → 17 Events mit `source_tf='M15'` + `signal_time`.
  Quick Look gegen echte DB: 75 M30- + 26 H1- + 12 H4-Signale.
  Notebook lädt fehlerfrei (HTTP 200).
- **Bekannte Grenzen:** Grid vs. Random wählbar; VectorBT/Order-Testing in
  separatem Notebook (folgt); Konfluenz/Statistik/ML bewusst im separaten
  Notebook; Presets/Profile folgen später.

**Reihenfolge = Abhängigkeiten:** Jeder Schritt baut auf dem vorherigen auf.
Nach jedem Schritt: Zwischentest, bevor der nächste beginnt.

---

## Phase 0 · Vorbereitung (Bestand prüfen)

1. **Bestand sichten:** `algos/` (base_indicator, signal_events, signal_service,
   ma_indicator, grid_indicator, chart_engine, chart_plugins), Notebooks
   `01_Chart_Inspector.py`, `02_signal_lab.py`, Datenbanken in `data/`.
2. **Sicherstellen, dass der aktuelle Stand läuft:** `01_Chart_Inspector`
   und `02_signal_lab` importieren ohne Fehler; `analytics_data.duckdb`
   hat das Composite-PK-Schema (`run_id, time, signal_type, price`).
3. **Merk-Punkt:** Der vorhandene Pfad
   `compute() → IndicatorResult → SignalEvents` wird **nicht verändert**;
   das Signal Lab wird als neue Schicht darüber gebaut.

**Abnahme:** Beide bestehenden Notebooks laufen unverändert.

---

## Phase 1 · Projekt-Struktur für das Signal Lab

1. Neuen Ordner `signal_lab/` im Projekt anlegen.
2. Module vorbereiten (zunächst leere Gerüste mit Docstring + Signatur):
   - `signal_lab/__init__.py`
   - `signal_lab/ui_state.py`        → Persistenz des UI-Stands (JSON)
   - `signal_lab/run_definition.py`  → Run-Definition aus UI-Auswahl
   - `signal_lab/naming.py`          → Run-Namensschema (§5)
   - `signal_lab/sweep_runner.py`    → Orchestrator (sequenziell/parallel)
   - `signal_lab/quick_look.py`      → Chart-Schnellsicht (Wrapper um chart_engine)
3. `sys.path`-Einbindung wie in den bestehenden Notebooks (PROJ_ROOT).

**Regel:** Das Notebook importiert nur aus `signal_lab/` – keine lange Logik
in Zellen.

**Abnahme:** `import signal_lab` funktioniert ohne Fehler (leere Gerüste).

---

## Phase 2 · Schema-Migration in `analytics_data.duckdb`

1. Migrationsskript ergänzen (z. B. `scripts/migrate_analytics_db.py`):
   - `ALTER TABLE indicator_runs ADD COLUMN IF NOT EXISTS run_name VARCHAR;`
   - `ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS source_tf VARCHAR;`
   - `ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS signal_time TIMESTAMPTZ;`
2. Skript ist **idempotent** (IF NOT EXISTS) – beliebig oft ausführbar.
3. Danach vorhandene Zeilen prüfen (Spalten dürfen NULL sein für Alt-Daten).

**Abnahme:** `duckdb_constraints()`/`information_schema` zeigen die neuen
Spalten; Bestandsdaten sind unverändert.

---

## Phase 3 · UI-State-Persistenz (JSON-Datei)

1. In `signal_lab/ui_state.py`:
   - `load_state() -> dict`  (liest `data/ui_state.json`; leeres dict, wenn Datei fehlt)
   - `save_state(state: dict)`  (schreibt atomar: erst `.tmp`, dann rename)
   - `default_state()`  (sinnvolle Defaults: z. B. SILVER, M30, MA-Defaults)
2. Alle UI-Felder, die gemerkt werden sollen (§11):
   Symbole, TFs, MA-Ranges (+ma_type), VectorBT-Ranges, Datumsbereich,
   Run-Name-Override, Grid/Random-Umschalter, Quick-Look `Symbol:TF`.
3. Schreiben bei jeder Änderung bzw. spätestens beim GO-Start.

**Abnahme:** Nach Neustart des Notebooks sind alle Felder mit dem letzten
Stand vorbelegt. Kein DB-Zugriff, keine Migration.

---

## Phase 4 · UI-Zellen im Notebook (schlank)

Neues/Migriertes Notebook `02_signal_lab.py` – Zellen-Aufbau:

1. **Setup-Zelle:** Imports aus `signal_lab/`, Konstanten, `load_state()`.
2. **Symbol-Buttons:** Favoriten aus `app_data.broker_symbols` (⭐ zuerst);
   Mehrfachauswahl; onClick → State speichern.
3. **TF-Buttons:** verfügbare TFs aus `market_data` (vorhandene Kombis);
   Mehrfachauswahl.
4. **MA-Parameter-Ranges:** je Parameter `min/step/max` (numerische Felder),
   `ma_type` als Dropdown.
5. **VectorBT-Ranges:** sichtbar, aber **deaktiviert** (bis Backtest-Modul
   existiert) – Tooltip „folgt später".
6. **Datumsbereich:** Von/Bis aus verfügbarer Spanne (aus `market_data`).
7. **Run-Name:** automatisch generiert (Phase 6), überschreibbares Feld.
8. **GO-Button + Run-Zähler:** siehe Phase 5.
9. **Quick Look:** siehe Phase 9.

**Regel:** Jede Zelle = UI-Element + 1 Aufruf in `signal_lab/`. Keine Logik.

**Abnahme:** Alle UI-Elemente erscheinen; Werte kommen aus dem gespeicherten
State (Phase 3).

---

## Phase 5 · Run-Definition & Run-Zähler

1. In `signal_lab/run_definition.py`:
   - `build_run_definition(ui_values) -> RunDefinition`
   - `RunDefinition` (dataclass): Symbole, TFs, Parameter-Raum, Datumsbereich,
     Strategie (grid/random), Sample-Größe bei random.
   - `count_runs(def) -> int`  = len(Symbole) × len(TFs) × len(Parameter-Sets)
2. Parameter-Raum erzeugen:
   - grid: `itertools.product` über alle Range-Werte (`np.arange(min, max+step, step)`)
   - random: Stichprobe (Seed fixieren → reproduzierbar)
3. **Run-Zähler im UI:** neben dem GO-Button live anzeigen; aktualisiert sich
   bei jeder Änderung an den Konfigurations-Controls.

**Abnahme:** Zähler zeigt die korrekte Kombi-Anzahl; ändert sich die Auswahl,
ändert sich die Zahl sofort.

---

## Phase 6 · Run-Namensschema

1. In `signal_lab/naming.py`:
   - `build_run_name(indicator, params, symbol, tf, timestamp) -> str`
   - Format: `{INDIKATOR}_{PARAM-KURZ}_{SYMBOL}_{TF}_{JJJJMMTT}_{HHMM}`
   - Parameter-Kurzform je Indikator fest (MA: `p06_s10_a3.0`)
   - `build_run_id(...) -> str` (SHA256-Hash, wie in `signal_service`)
2. Zeitstempel = Run-Start (lokal), pro Lauf einmal erzeugt.
3. UI: Name wird automatisch befüllt, ist überschreibbar; optionaler freier
   Tag wird angehängt (`_batch-01`).

**Abnahme:** Zwei Läufe mit gleichen Parametern, aber unterschiedlichem Start
haben eindeutige, sortierbare Namen.

---

## Phase 7 · Orchestrator (sweep_runner)

1. In `signal_lab/sweep_runner.py`:
   - **sequenziell zuerst** (Basis): `run_sweep_sequential(def, worker) -> list[RunResult]`
     - pro Kombination: Daten laden (geteilter Datensatz cachen), `compute()`,
       Events + run_name/id erzeugen, Ergebnis sammeln
   - **Datenladung einmalig:** OHLCV für Symbol×TF×Datum nur einmal laden und
     an alle Parameter-Kombis durchreichen (statt pro Run neu).
2. Worker-Funktion: `worker(params, df, symbol, tf) -> IndicatorResult`
   – reine Berechnung ohne DB.
3. **Persistierung:** erst **nach Chunk-Ende** in `analytics_data` schreiben
   (`DuckDBSignalService.store_result` pro Result – idempotent).
4. Fortschrittsanzeige: fertig/gesamt + laufende Kombination (Callback).
5. **Parallel (danach):**
   - `multiprocessing.Pool` über die Parameter-Sets
   - Chunking: z. B. `chunks = [sets[i::n_workers] for i in range(n_workers)]`
   - Worker berechnet Chunk komplett im RAM → liefert Liste zurück
   - **Persistierung nach Chunk-Ende** im Hauptprozess (vermeidet
     DB-Write-Locks); pro Worker nur EIN Ergebnis-Transfer
   - Windows: Schutzblock `if __name__ == "__main__":` beachten (spawn)

**Abnahme:** Sequenzieller Sweep liefert dieselben Events wie ein manueller
Einzel-Run; paralleler Sweep liefert identische Ergebnisse bei kürzerer Zeit;
DB enthält nach dem Sweep die erwartete Anzahl Runs (idempotent).

---

## Phase 8 · Sicherheitsabfrage & Fortschrittsanzeige

1. **GO-Button:** onClick → Bestätigung anzeigen:
   „X Runs · Y Parameter-Sets · Symbole [… ] · TFs [… ] – starten?"
   → Abbrechen / Bestätigen. Erst nach Bestätigung startet der Sweep.
2. **Fortschritt:** während des Laufs Fortschrittsbalken / Statuszeile
   (fertig/gesamt, aktueller Run-Name), live aus dem Runner-Callback.
3. **Abbruch:** Button „Stopp" während des Laufs; nach Abbruch werden die
   bereits fertig berechneten Chunks persistiert, der Rest verworfen.
4. Der Run-Zähler (Phase 5) erscheint in der Sicherheitsabfrage als Summe.

**Abnahme:** Ohne Bestätigung startet nichts; während des Laufs sieht man
Fortschritt und kann abbrechen; danach sind nur fertige Runs in der DB.

---

## Phase 9 · Quick Look (Chart-Ausgabefenster)

1. **Eingabezelle über der Grafik:** Textfeld `Symbol:TF`
   (z. B. `SILVER:M30`); Buttons übernehmen den Wert, manuelle Eingabe
   überschreibt nur die Chart-Sicht. Enter → sofort rendern.
2. **Fensterbegrenzung wie Chart Inspector:** `load_candles(...)` mit
   limit (z. B. 1000) + warmup + Slider-Scrolling – **keine 10k-Ansicht**.
3. **Marker-Shapes-Registry:** zentrales Mapping `Signaltyp → Shape/Farbe`
   in `algos/` (plot_meta-basiert), gemeinsam genutzt von Chart-Engine und
   Quick Look: swing_change=▲/▼, circle_yellow/circle_fuchsia=Kreise, ...
4. **Multi-TF-Overlay:**
   - höhere TFs (max. 3, wählbar) zusätzlich laden (nur Fenster+Warmup)
   - Signale der höheren TFs **zum Auslösezeitpunkt** annähern: den
     kleineren-TF-Bar markieren, in dem der HTF-Close/High/Low erreicht wurde
   - Farbvariation je TF (feste Palette), Marker versetzt über/unter
   - **HTF-Logik auf kleinerem TF (exakter Zeitpunkt):** optionaler Modus –
     Logik läuft auf kleinem TF, das Signal speichert `signal_time` (exakt)
     + `source_tf` (HTF) für die spätere Statistik
5. **Signal-Anzeige:** nur Events (Pfeile/Kreise) + MA/Grid-Overlays aus dem
   bestehenden Rendering – keine Parameter-/Statistiktabellen.

**Abnahme:** Quick Look zeigt ein Fenster wie im Chart Inspector, mit
M30-Signalen + HTF-Signalen farbcodiert; `Symbol:TF`-Eingabe wechselt sofort
die Ansicht; HTF-Signale liegen (genähert) am Auslösezeitpunkt.

---

## Phase 10 · VectorBT-Abstimmung verifizieren

1. Sicherstellen, dass die Signalfolge aus `to_events_frame()` als
   **VectorBT-kompatibel** gilt:
   - Zeitindex = UTC (`TIMESTAMPTZ`), OHLCV-Spaltennamen `open/high/low/close`
   - Richtung als `[1, -1, 0]` (direction)
2. Kleiner Verifikationstest: Events-Frame → `vbt.Signal.from_signals`
   (oder manuelle Signalfolge) ohne Fehler aufsetzbar.
3. Ergebnis festhalten (z. B. kurzer Test in `scripts/`), damit der
   Backtest-Anschluss später ohne Umbau klappt.

**Abnahme:** Die erzeugten Events lassen sich 1:1 als VectorBT-Signal
interpretieren.

---

## Phase 11 · End-to-End-Abnahme

1. Kompletten Flow durchspielen:
   - UI öffnen → letzter Stand ist vorbelegt
   - Auswahl ändern → Run-Zähler aktualisiert sich
   - GO → Sicherheitsabfrage → Sweep startet → Fortschritt sichtbar
   - Quick Look zeigt die Charts mit Signalen (inkl. HTF-Overlay)
2. Daten prüfen: `indicator_runs.run_name` gefüllt, `signal_events` mit
   `source_tf`/`signal_time` (bei HTF-Run), keine Duplikate bei Wiederholung.
3. Bekannte Grenzen dokumentieren (Grid vs. Random, VectorBT-Ranges noch
   deaktiviert, Konfluenz folgt im Statistik-Notebook).

**Abnahme:** Das Signal Lab ist eigenständig nutzbar und liefert saubere,
benannte, idempotente Daten für die spätere Statistik.

---

**Hinweis:** Statistik/ML, Presets/Profile und das VectorBT-Backtest-Modul
sind bewusst **nicht** Teil dieser Anleitung und werden in einem späteren
Schritt ergänzt.
