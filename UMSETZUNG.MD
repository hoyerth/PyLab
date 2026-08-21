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
