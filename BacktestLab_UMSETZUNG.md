# Konzept: Backtest Lab (Notebook `03_Backtest_Lab.py`)

VectorBT-Backtests & Order-Strategien auf Basis der Signal-Lab-Daten.

---

## 0. Voraussetzungen / Abhaengigkeiten (wichtig!)

- **Signal-Qualitaet ist Pflicht:** Jedes `swing_change`-Signal wird ein Entry.
  Die Signale muessen im Signal Lab bereits **realistisch und sinnvoll** gesetzt
  sein - das Backtest Lab uebernimmt sie 1:1, es korrigiert keine Signale.
- **Richtung Long/Short:** Long/Short ergibt sich aus `signal_events.direction`
  (+1 = Long, -1 = Short). **Voraussetzung: `direction` im Signal Lab ist
  korrekt gepflegt** (falls dort vergessen, wird es hier zuerst ergaenzt).
- **Technische Basis:** Das Notebook wird auf der technischen Grundlage von
  `02_Signal_Lab.py` erstellt. Alle dort geloesten Probleme und Fallstricke
  (Button-Export, State-Singleton, weakref-Registry, Session-ID, CRLF) sind
  hier bereits geloest - kein erneutes Bugfixing.

---

## 1. Datenhaltung (3 getrennte DuckDBs)

- **`market_data.duckdb`** (read-only): OHLCV-Preise, `ohlcv_bars`
  (hat bereits eine `spread`-Spalte).
- **`analytics_data.duckdb`** (read-only): Signal-Events
  (`swing_change`, Indikator-Zustaende) - Quelle der Entries.
- **`backtest_data.duckdb`** (write): Trade-Records (Order-Ausfuehrungen,
  Entry/Exit-Preise, PnL, Returns). Das Datenvolumen waechst bei Sweeps
  um Zehnerpotenzen schneller als in analytics_data.

**Modularitaet:** Das Backtest-Notebook liest `market_data` und
`analytics_data` ausschliesslich read-only und schreibt aggregierte
Backtest-Ergebnisse isoliert in `backtest_data`.

---

## 2. Architektur-Schema

```
[market_data.duckdb] (OHLCV + spread)
        |
        v
[analytics_data.duckdb] (Signals: run_id, symbol, tf, timestamp, direction)
        |
        v
[Backtest Runner (VectorBT / Numba Chunk Engine)]
   |-- Parameter-Space:
   |     - Spread / Slippage (% der Preisbasis)
   |     - Stop-Loss / Take-Profit (fix)
   |     - Position-Sizing / Margin (fester %-Wert)
   |     - Datumsbereich (separat waehlbar)
   |
   v
[backtest_data.duckdb]
   |-- backtest_runs (run_id, signal_run_id, params, sharpe, winrate,
   |                 maxDD, profit_factor, ...)
   `-- backtest_trades (trade-liste: entry/exit-time, entry/exit-price,
                       pnl, r_multiple)
```

- **Keine vollstaendigen Equity-Kurven pro Run in der DB** (Explosion der
  DB-Groesse). Im Sweep werden nur Run-Level-Metriken gespeichert:
  `net_profit, win_rate, profit_factor, max_drawdown_pct, sharpe_ratio,
  trade_count, avg_trade_pnl, expectancy`.
- **ALLE Trades werden gespeichert** (`backtest_trades`) - nur so sind
  Equity-Curve-Berechnung und statistische Analysen im spaeteren
  Statistik-/ML-Notebook moeglich.
- **Chunking / Worker:** Genau wie im Signal Lab (`run_sweep_parallel`):
  Parameter-Chunks ueber Multiprocessing an Numba/VBT uebergeben, nicht
  alle Kombinationen in eine einzige Matrix kippen.

---

## 3. Order-Modell v1 (CFD, nur Spread)

- **CFD-Modell:** Es gibt NUR den Spread (keine Fees, keine Commission).
- **Spread als Parameter in %** der Preisbasis (Default z. B. 0.05 %).
- **Exits v1:**
  - Stop-Loss (fix, in % oder Pips/Points)
  - Take-Profit (fix)
  - Gegensignal (Reversal-Exit)
- **Session-Cut / Time-Exit:** Nur als Session-Cut geplant (spaeter).
- **Implementierung v1:** `vbt.Portfolio.from_signals` mit `sl_stop`,
  `tp_stop`, `slippage`. Fuer extrem komplexe MT5-spezifische Order-Typen
  (FIFO, Pending-Limit mit Spread-Filter) spaeter: VBT-Custom-Numba-Callbacks
  oder eigener schlanker Numba-JIT-Loop (`@njit`), der Signallisten
  abarbeitet.

**Bewusst NICHT in v1 (stehen in der Vision):** Trailing-Stop,
Breakeven-Regeln, ATR-Multiples (ATR kommt komplett NICHT),
Max-Holding-Time (nur Session-Cut), dynamischer Spread aus Signalen,
Multi-Signal-Entries.

---

## 4. UI

- **Symbol + TF:** wie im Signal Lab (Mehrfachauswahl aus vorhandenen Daten).
- **Run-Auswahl (analytics):** Nur die Runs aus dem **letzten Signal-Lab-Lauf**
  (keine Historie). Tabelle mit Checkbox am Anfang. Fuer umfassende
  Statistik gibt es spaeter das data/ml-Notebook.
- **Order-Parameter v1:**
  - Spread (%)
  - Stop-Loss fix (% / Pips/Points)
  - Take-Profit fix
  - Position-Sizing / Margin (fester %-Wert)
  - Datumsbereich (separat waehlbar, wichtig zur Komplexitaets-
    Einschraenkung - nicht immer alles ab 2013)
- **Komplexitaets-Anzeige vor dem Lauf:** Anzahl Runs + RAM-Verbrauch.
  Ablehnung (Button ausgrauen + Meldung), wenn Ressourcen nicht ausreichen.
- **Persistenz:** aktuelles Parameter-Set als JSON (Auto oder per Button),
  eigene Datei `data/backtest_ui_state.json` (analog Signal Lab).
  Auch der Datumsbereich wird mitpersistiert.
- **Button-/State-Pattern:** exakt wie im gefixten Signal Lab
  (Modul-Singleton-States in `backtest_lab/`, exportierte Buttons,
  `return btn_confirm, btn_cancel`, weakref-sicher). Kein erneutes
  stundenlanges Bugfixing.

---

## 5. Run & Naming

- **Feste Benamungsvorgabe + individueller Textanhang** (wie Signal Lab).
- **Komplexitaets-Anzeige** wie in UI (Anzahl Runs + RAM, Ablehnung bei
  Ueberschreitung).
- **Schwellwert / RAM-Schaetzung als JSON** (konfigurierbar).
- **Schaetzung = volles Parameter-Kreuzprodukt** (realistisch, nicht
  beliebig skalierbar).

### Namensschema (Entscheid: Option A - kurzer Backtest-Name)

Signal-Run-Namen sind bereits lang (z. B.
`MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608`, 52 Zeichen).
Deshalb bleibt der Backtest-Run-Name **kurz**:

```
BT_{sp}{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_{JJJJMMTT_HHMM}
```

Beispiel: `BT_sp005_sl2_tp4_sz1_20260821_2030`

- Der volle Signal-Name wird NICHT in `backtest_runs` gespeichert, sondern
  per JOIN ueber `signal_run_id` (FK) aus `analytics_data` geholt.
- **UI zeigt zwei getrennte Zeilen:**
  - Signal: `MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608`
  - Backtest: `BT_sp005_sl2_tp4_sz1_20260821_2030`
- Vorteile: kurze Spalte, keine Duplikate, Signal-Name immer konsistent
  aus der Quelle.

---

## 6. DB-Schema `backtest_data.duckdb` (v1)

### `backtest_runs`

```
run_id            VARCHAR PRIMARY KEY   -- Hash (wie Signal Lab)
signal_run_id     VARCHAR FK            -- -> analytics_data.indicator_runs.run_id
run_name          VARCHAR               -- kurzer Name: BT_... (Option A)
symbol            VARCHAR
timeframe         VARCHAR
params_json       VARCHAR               -- volles Order-Parameter-Set
date_from         TIMESTAMPTZ           -- gewaehlter Backtest-Zeitraum
date_to           TIMESTAMPTZ
net_profit        DOUBLE
win_rate          DOUBLE
profit_factor     DOUBLE
max_drawdown_pct  DOUBLE
sharpe_ratio      DOUBLE
trade_count       INTEGER
avg_trade_pnl     DOUBLE
expectancy        DOUBLE
created_at        TIMESTAMPTZ
```

### `backtest_trades` (ALLE Trades speichern)

```
run_id        VARCHAR FK   -- -> backtest_runs.run_id
entry_time    TIMESTAMPTZ
exit_time     TIMESTAMPTZ
entry_price   DOUBLE
exit_price    DOUBLE
direction     INTEGER      -- +1 Long / -1 Short
pnl           DOUBLE
r_multiple    DOUBLE
```

Hinweis: Einige Felder sind in v1 noch nicht in allen Details verstanden
(z. B. R-Multiple-Definition) - sie werden bei der Umsetzung praezisiert.

---

## 7. Vision / Spaeter (bewusst NICHT in v1)

- **Equity-Curve on the fly:** Spaeter beliebige Trading-Runs zur Ansicht
  auswaehlen. Die Equity-Curve wird **als eigener, leichter Algo** nach dem
  Run berechnet (cumsum der Trade-PnL) - technisch sauber, da nur Trades
  summiert werden, dadurch blitzschnell (ms-Bereich). Keine gespeicherten
  Kurven in der DB noetig.
- **HTF-Signale (source_tf):** Backtest ueber mehrere Timeframes bzw.
  HTF-Signale beruecksichtigen (z. B. `source_tf='M15'`-Events).
- **Kombination mehrerer Signal-Runs** in einem Backtest (Buendelung).
- **Trailing-Stop / Breakeven-Regeln** als Exit-Modifikatoren.
- **Session-Cut / Time-Exit** (z. B. Session-Close als Exit).
- **Dynamischer Spread aus Signalen** (z. B. aus `ohlcv_bars.spread`),
  statt nur fester Parameter.
- **Multi-Signal-Entries:** mehrere Signale auswaehlen mit zeitlicher Range
  (valide fuer die letzten x Bars / x Stunden etc.).
- **Gerade-Exit mit eigenen Bedingungen** (z. B. naechster Pivot an der
  HMA-4-Linie).
- **Position Stacking, Trailing-Stops.**
- **Extern in Python definierte Bedingungen** fuer Entry/Exit.
- **Sets/Profile:** Speichern aller Parameter als benannte Profile.

---

## 8. Bekannte Grenzen (v1)

- Nur ein Signal-Run pro Backtest (Kombi erst in Vision).
- Nur same-TF-Signale (HTF-Signale erst in Vision).
- Nur CFD-Spread (keine Fees/Commission, kein ATR, kein Trailing).
- Run-Auswahl nur aus dem letzten Signal-Lab-Lauf.
- RAM-Schaetzung = volles Kreuzprodukt (nicht beliebig skalierbar).

---

## 9. Naechste Schritte (Schlagworte)

Projekt-Struktur `backtest_lab/` (Module analog Signal Lab) -> DB-Schema
Migration `backtest_data.duckdb` (backtest_runs + backtest_trades) ->
UI-Zellen (schlank) -> Run-Auswahl (letzter Lauf) -> Order-Parameter ->
Komplexitaets-/RAM-Schaetzung (JSON-Schwellwert) -> Backtest-Runner
(vbt.Portfolio.from_signals, Chunking/Parallel wie Signal Lab) ->
Naming (Option A) -> Persistenz (backtest_ui_state.json) ->
Sicherheitsabfrage + Fortschritt + Stop (gefixtes Signal-Lab-Pattern) ->
End-to-End-Abnahme -> (danach: Equity-Curve on the fly, Multi-Run,
Multi-TF, Trailing, Profile, Statistik-Notebook inkl. Konfluenz/ML).

---

**Hinweis:** Statistik/ML, Equity-Curve-Anzeige, Multi-Run/Multi-TF,
Trailing/BE, Profile sind bewusst NICHT Teil von v1 und werden in einem
spaeteren Schritt ergaenzt.

---

# Schritt-fuer-Schritt-Anleitung zur Umsetzung (v1)

Die folgenden Schritte bauen aufeinander auf. Reihenfolge einhalten –
jeder Schritt liefert die Grundlage fuer den naechsten. Analogien zum
bereits gefixten Signal Lab (`02_Signal_Lab.py`) sind gekennzeichnet.

## Schritt 1: Projekt-Struktur `backtest_lab/` anlegen

- Modul-Paket `backtest_lab/` im Projekt erstellen (analog `signal_lab/`).
- Geplante Module:
  - `db.py` – DuckDB-Zugriff (read-only auf `market_data` / `analytics_data`, write auf `backtest_data`)
  - `schema.py` – Tabellen-DDL fuer `backtest_data.duckdb`
  - `runner.py` – Backtest-Runner (VectorBT / Numba-Chunk-Engine)
  - `naming.py` – Namensschema Option A (kurzer Backtest-Name)
  - `ui.py` – UI-Zellen (schlank), Buttons, State
- Verifikation: `python -m py_compile backtest_lab/*.py`

## Schritt 2: DB-Schema `backtest_data.duckdb` migrieren

- Migration anlegen (analog Signal-Lab-Migration), Tabellen:
  - `backtest_runs` (run_id PK, signal_run_id FK, run_name, symbol,
    timeframe, params_json, date_from, date_to, net_profit, win_rate,
    profit_factor, max_drawdown_pct, sharpe_ratio, trade_count,
    avg_trade_pnl, expectancy, created_at)
  - `backtest_trades` (run_id FK, entry_time, exit_time, entry_price,
    exit_price, direction, pnl, r_multiple)
- R-Multiple-Definition bei der Umsetzung praezisieren (in v1 noch offen).
- Verifikation: DB-Test in `test/test.py` – Tabellen anlegen, INSERT + SELECT pruefen.

## Schritt 3: Read-only-Anbindung an die Quell-DBs

- `market_data.duckdb` (read-only): `ohlcv_bars` lesen (OHLCV + `spread`).
- `analytics_data.duckdb` (read-only): Signal-Events lesen
  (`run_id`, `symbol`, `tf`, `timestamp`, `direction`).
- Verbindungen bewusst **read-only** oeffnen (kein Schreibzugriff).
- Verifikation: Lese-Test in `test/test.py` – Signal-Events eines Runs
  laden und Richtung (`+1`/`-1`) prüfen.

## Schritt 4: Run-Auswahl (nur letzter Signal-Lab-Lauf)

- Query: nur Runs aus dem letzten Signal-Lab-Lauf anzeigen (keine Historie).
- UI: Tabelle mit Checkbox am Anfang der Zeile, Mehrfachauswahl
  (analog Signal Lab).
- Verifikation: Code-Inspektion + DB-Test der Query.

## Schritt 5: Order-Parameter UI (v1)

- Eingabefelder:
  - Spread (%) – Default z. B. 0.05 %
  - Stop-Loss fix (% oder Pips/Points)
  - Take-Profit fix
  - Position-Sizing / Margin (fester %-Wert)
  - Datumsbereich (separat waehlbar, nicht immer alles ab 2013)
- Komplexitaets-Anzeige vor dem Lauf: Anzahl Runs + RAM-Verbrauch.
  Ablehnung (Button ausgrauen + Meldung), wenn Ressourcen nicht reichen.
- Schwellwert / RAM-Schaetzung als JSON konfigurierbar.
- Schaetzung = volles Parameter-Kreuzprodukt (realistisch).
- Persistenz: Parameter-Set als JSON (Auto oder per Button) in
  `data/backtest_ui_state.json`, inkl. Datumsbereich.
- Button-/State-Pattern exakt wie im gefixten Signal Lab
  (Modul-Singleton-States, exportierte Buttons, `return btn_confirm, btn_cancel`,
  weakref-sicher, Session-ID, CRLF).

## Schritt 6: Backtest-Runner (v1)

- Implementierung: `vbt.Portfolio.from_signals` mit
  `sl_stop`, `tp_stop`, `slippage` (CFD-Modell, nur Spread, keine Fees/Commission).
- Exits v1: Stop-Loss (fix), Take-Profit (fix), Gegensignal (Reversal-Exit).
- Chunking / Worker: `run_sweep_parallel`-Muster aus dem Signal Lab
  uebernehmen – Parameter-Chunks per Multiprocessing an VBT/Numba,
  nicht alle Kombinationen in eine einzige Matrix.
- Pro Run nur Run-Level-Metriken ablegen:
  `net_profit, win_rate, profit_factor, max_drawdown_pct, sharpe_ratio,
  trade_count, avg_trade_pnl, expectancy`.
- **ALLE Trades** in `backtest_trades` speichern (Grundlage fuer spaetere
  Equity-Curve-Berechnung und Statistik).
- Bewusst NICHT in v1: Trailing-Stop, Breakeven, ATR, Max-Holding-Time,
  dynamischer Spread, Multi-Signal-Entries, Equity-Kurven in der DB.
- Verifikation: Logik-Test in `test/test.py` mit kleinem Datensatz –
  Entry/Exit-Preise, PnL und Metriken plausibel pruefen.

## Schritt 7: Naming (Option A – kurzer Backtest-Name)

- Namensschema: `BT_{sp}{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_{JJJJMMTT_HHMM}`
  (Beispiel: `BT_sp005_sl2_tp4_sz1_20260821_2030`).
- Signal-Name NICHT in `backtest_runs` duplizieren – per JOIN ueber
  `signal_run_id` (FK) aus `analytics_data` holen.
- UI zeigt zwei getrennte Zeilen: Signal-Name (lang, aus Quelle) +
  Backtest-Name (kurz).
- Feste Benamungsvorgabe + individueller Textanhang (wie Signal Lab).

## Schritt 8: Persistenz & Sicherheitsabfrage

- `backtest_ui_state.json` (Auto-Save oder per Button) analog Signal Lab.
- Sicherheitsabfrage vor dem Lauf (Anzahl Runs, RAM, Zeitraum).
- Fortschritts-Anzeige + Stop-Button (gefixtes Signal-Lab-Pattern
  uebernehmen – kein erneutes Bugfixing).

## Schritt 9: End-to-End-Abnahme

- Kompletter Durchlauf: Signal-Lab-Lauf -> Run-Auswahl -> Parameter setzen ->
  Komplexitaets-Check -> Backtest starten -> `backtest_runs` +
  `backtest_trades` in `backtest_data.duckdb` pruefen.
- Stichproben: Trades gegen bekannte Signale plausibilisieren
  (Richtung, Zeitpunkt, SL/TP).
- Modulare Kapselung pruefen: `market_data` und `analytics_data`
  bleiben unveraendert (read-only).

## Danach (bewusst NICHT in v1)

- Equity-Curve on the fly (cumsum der Trade-PnL, kein DB-Speicher)
- Multi-Run / Multi-TF (HTF-Signale), Kombination mehrerer Signal-Runs
- Trailing-Stop / Breakeven, Session-Cut / Time-Exit
- Dynamischer Spread, Multi-Signal-Entries, gerade Exits
- Profile (benannte Parameter-Sets), Statistik-/ML-Notebook
