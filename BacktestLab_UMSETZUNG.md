# Konzept: Backtest Lab (Notebook `03_Backtest_Lab.py`)

VectorBT-Backtests & Order-Strategien auf Basis der Signal-Lab-Daten.

---

## A. Entscheidungs-Log (Session 2026-08-22) - Review eingearbeitet

Die folgenden Punkte sind Ergebnis des Architektur-Reviews und gelten
verbindlich fuer v1. Sie sind in den Abschnitten 2-8 und in der
Schritt-fuer-Schritt-Anleitung umgesetzt:

1. **`backtest_runs`-Tabelle ist Pflicht:** Laeufe mit 0 Trades, Metadaten
   und Parameter-JSON gehoeren dorthin. **Kein Loeschen von Verlierer-Runs**
   (Survivorship Bias - das ML-Lab braucht zwingend negative Beispiele,
   Klasse 0, fuer XGBoost/RandomForest).

2. **`run_id` = deterministischer Hash (`run_id_from_config`, SHA-256).**
   KORREKTUR gegenueber der urspruenglichen uuid4-Planung (Bugfix 3):
   1:1 identische Konfiguration (Signal-Run + Symbol + TF + Order-Parameter
   + Datumsbereich) ergibt IMMER dieselbe run_id - `save_backtest_run`
   loescht daraufhin Trades und ersetzt den Run per `INSERT OR REPLACE`
   (keine endlosen Duplikate bei Re-Runs, natuerliche "Refresh"-Semantik).
   Andere Konfiguration -> eigene run_id (kein Konflikt). Der Signal-Bezug
   bleibt ueber die FK-Spalte `signal_run_id` ->
   `analytics_data.indicator_runs.run_id` erhalten. Anders als im Signal Lab
   gibt es kein `INSERT OR IGNORE` mit veraltetem `created_at` - der
   Overwrite schreibt `created_at`/`run_name` immer frisch.

3. **R-Multiple (definiert):**
   `r_multiple = (exit_price - entry_price) / (entry_price - initial_sl_price) * direction`.
   Ohne fixen Stop-Loss: `NULL`. `initial_sl_price` ergibt sich aus
   `entry_price` und `stop_loss_pct`.

4. **Spread -> Slippage:** Slippage wird symmetrisch auf Entry UND Exit
   angewendet. Parameter `spread_pct` wird daher halbiert an die Engine
   gegeben: `slippage = spread_pct / 2`.

5. **Timing-Modell v1 (lookahead-frei):**
   - Entry: Signal bei Bar-Close T -> Entry am **Open von Bar T+1**.
   - SL/TP: intrabar-Pruefung (Low/High der gehaltenen Bars).
   - Gegensignal: Exit UND neuer gegensaetzlicher Entry am **Open
     derselben Folge-Bar** (Exit- und Entry-Preis identisch = Open).
   - Kollision SL/TP mit Gegensignal in derselben Bar: **SL/TP gewinnt**
     (intrabar vor Bar-Close-Reversal).
   - Gleich-Richtungs-Signal bei offener Position: **kein Effekt**
     (v1: kein Stacking).
   - Offene Position am `date_to`-Ende: **verwerfen** (kein Trade-Record,
     nicht in Metriken).

6. **Run-Auswahl "letzter Signal-Lab-Lauf":** Identifikation ueber den
   Zeitstempel im `run_name` (`_JJJJMMTT_HHMM`). `MAX(created_at)` ist
   ungeeignet, weil Re-Runs dank `INSERT OR IGNORE` im Signal Lab den
   alten `created_at` behalten. Fallback bei `run_name_override` (kein
   Zeitstempel im Namen): `MAX(created_at)`.

7. **Engine-Entscheidung (2-stufig, per Smoke-Test):**
   - Stufe A: `vectorbt 1.1.0` in `test/test.py` verifizieren
     (Kompatibilitaet mit pandas 3.0.5 / numpy 2.5.2 ist NICHT
     garantiert). Eingesetzt: `Portfolio.from_signals` mit getrennten
     Arrays `entries` / `short_entries` (Long/Short) sowie `sl_stop`,
     `tp_stop`, `slippage`.
   - Stufe B (Fallback): eigene **rein numpy-vektorisierte Engine**
     (kein Numba, kein vectorbt) - fuer v1 ausreichend und
     abhaengigkeitsfrei.
   - Die Entscheidung faellt durch den Smoke-Test, BEVOR `runner.py`
     geschrieben wird.

### ERGEBNIS ENGINE-SMOKE-TEST (2026-08-22): STUFE A GEWAEHLT

`vectorbt 1.1.0` laeuft stabil mit pandas 3.0.5 / numpy 2.5.2. Alle 5
Smoke-Tests in `test/test.py` (`test_vectorbt_smoke`) sind gruen. Die
eigene numpy-Engine (Stufe B) wird NICHT benoetigt.

**API-Erkenntnisse v1.1.0 (verbindlich fuer `runner.py`):**

- **Records:** `pf.trades.records` (NICHT `pf.records`).
- **direction-Spalte:** `0` = Long, `1` = Short.
- **status-Spalte:** `1` = geschlossen, `0` = offen (am Ende verwerfen).
- **Execution am Open:** `price=open_` MUSS gesetzt werden - und zwar
  fuehrt es am Open DERSELBEN Bar aus. Lookahead-freier Entry:
  Signal bei Bar T -> `entries[T+1]=True` (Arrays um 1 Bar shiften).
- **SL/TP relativ zum Entry-Fill:** `stop_entry_price=StopEntryPrice.FillPrice`
  ist PFLICHT. Ohne diesen Parameter basiert der Stop auf `val_price`
  (Default = Close) - dann ist "SL 2%" nicht 2% unter dem Entry, sondern
  unter dem Bar-Close (verifiziert: Stop 98.98 wurde ohne FillPrice zu
  99.96 falsch berechnet).
- **Reversal:** `upon_opposite_entry=OppositeEntryMode.Reverse` -
  schliesst die offene Position und oeffnet die Gegenseite am selben
  Open-Preis (Exit-/Entry-Preis identisch).
- **Konflikt Long+Short in derselben Bar:** ergibt 0 Trades. In der
  Praxis nie relevant, da `direction` pro Signal entweder +1 oder -1 ist.
- **Slippage:** wirkt symmetrisch gegen den Trader (Entry kauft teurer /
  verkauft billiger, Exit umgekehrt). `spread_pct/2` als Slippage
  verifiziert.
- **Size:** Default `init_cash=100` kappt `size` auf All-in. Fuer
  deterministische Groessen `size_type=SizeType.Amount` + ausreichend
  `init_cash` verwenden. `position_size_pct` aus der UI wird im Runner
  auf `SizeType.Percent` (size = pct/100) abgebildet.
- **Offene Position am Ende:** erscheint als Trade mit `status=0` und
  wird im Runner verworfen (kein Trade-Record).

8. **Spaeter (Vision):** zeitgenauere Entries ueber niedrigeren TF
   (analog `_apply_htf_exact_time` im Signal Lab). v1 bleibt beim
   naechsten Bar-Open.

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
[Backtest Runner (vectorbt 1.1.0 - Engine-Entscheidung gefallen)]
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
  Engine-Eingabe: `slippage = spread_pct / 2` (symmetrisch auf Entry+Exit).
- **Exits v1:**
  - Stop-Loss (fix, in % oder Pips/Points) - intrabar
  - Take-Profit (fix) - intrabar
  - Gegensignal (Reversal-Exit): Exit + neuer Gegensatz-Entry am Open
    derselben Folge-Bar (Exit-/Entry-Preis identisch = Open)
- **Prioritaeten in einer Bar:** SL/TP (intrabar) vor Gegensignal
  (Bar-Close-Signal -> Exit erst am naechsten Open).
- **Timing (lookahead-frei):** Signal bei Bar-Close T -> Entry am Open von
  Bar T+1. Offene Positionen am Ende des Datumsbereichs (`date_to`) werden
  verworfen (kein Trade-Record).
- **Gleich-Richtungs-Signal bei offener Position:** kein Effekt (v1:
  kein Stacking).
- **Session-Cut / Time-Exit:** Nur als Session-Cut geplant (spaeter).
- **Implementierung v1:** `vectorbt 1.1.0` via `vbt.Portfolio.from_signals`
  (Engine-Entscheidung gefallen, siehe Abschnitt A). Aufruf-Schema:
  `price=open_`, `stop_entry_price=FillPrice`,
  `upon_opposite_entry=Reverse`, `slippage=spread_pct/2`, Signale um
  1 Bar shiften. Fuer extrem komplexe MT5-spezifische Order-Typen
  (FIFO, Pending-Limit mit Spread-Filter) spaeter: VBT-Custom-Numba-Callbacks
  oder Numba-JIT-Loop (`@njit`).

**Bewusst NICHT in v1 (stehen in der Vision):** Trailing-Stop,
Breakeven-Regeln, ATR-Multiples (ATR kommt komplett NICHT),
Max-Holding-Time (nur Session-Cut), dynamischer Spread aus Signalen,
Multi-Signal-Entries.

---

## 4. UI

- **Symbol + TF:** wie im Signal Lab (Mehrfachauswahl aus vorhandenen Daten).
- **Run-Auswahl (analytics):** Nur die Runs aus dem **letzten Signal-Lab-Lauf**
  (keine Historie). Identifikation ueber den Zeitstempel im `run_name`
  (`_JJJJMMTT_HHMM`); Fallback bei `run_name_override`: `MAX(created_at)`.
  Tabelle mit Checkbox am Anfang. Fuer umfassende
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
run_id            VARCHAR PRIMARY KEY   -- deterministischer SHA-256-Hash (run_id_from_config)
signal_run_id     VARCHAR FK            -- -> analytics_data.indicator_runs.run_id
run_name          VARCHAR               -- kurzer Name: BT_... (Option A)
symbol            VARCHAR
timeframe         VARCHAR
params_json       JSON                  -- volles Order-Parameter-Set
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

### Python-Dataclass (verbindlich, voller DDL-Abgleich)

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BacktestRunRecord:
    """Metadaten + Gesamtergebnis eines Backtest-Laufs (1 Zeile).

    run_id ist DETERMINISTISCH (run_id_from_config, SHA-256): identische
    Konfiguration ergibt dieselbe run_id und wird beim Speichern
    ueberschrieben (keine endlosen Duplikate, Bugfix 3).
    """

    run_id: str
    signal_run_id: str
    run_name: str
    symbol: str
    timeframe: str
    params_json: str
    date_from: datetime
    date_to: datetime
    net_profit: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trade_count: int
    avg_trade_pnl: float
    expectancy: float
    created_at: datetime
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

Hinweis: R-Multiple-Definition ist geklaert (siehe Abschnitt A, Punkt 3):
`(Exit-Entry) / (Entry-InitialSL) * direction`, ohne fixen SL: `NULL`.

---

## 7. Vision / Spaeter (bewusst NICHT in v1)

- **Aufräumen und Optimieren:** Alles Vektorisiert?  Logik in externe py Dateien;  UI kompakt zusammen
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
- Identifikation "letzter Lauf" ueber run_name-Zeitstempel: Sweeps in
  derselben Minute verschmelzen; bei `run_name_override` (kein Zeitstempel)
  greift der `MAX(created_at)`-Fallback.
- Offene Positionen am `date_to`-Ende werden verworfen (kein Trade-Record).
- Re-Runs mit 1:1 identischer Konfiguration UEBERSCHREIBEN den vorhandenen
  Run (deterministische run_id + `INSERT OR REPLACE`, Bugfix 3) - keine
  endlosen Duplikate. Andere Konfiguration -> separater Run.
- Entry immer am naechsten Bar-Open (zeitgenauere Entries via niedrigerem
  TF erst in Vision).

---

## 9. Naechste Schritte (Schlagworte)

Projekt-Struktur `backtest_lab/` (Module analog Signal Lab) -> DB-Schema
Migration `backtest_data.duckdb` (backtest_runs + backtest_trades) ->
UI-Zellen (schlank) -> Run-Auswahl (letzter Lauf) -> Order-Parameter ->
Komplexitaets-/RAM-Schaetzung (JSON-Schwellwert) -> Backtest-Runner
(vectorbt 1.1.0 - Engine-Entscheidung gefallen,
Chunking/Parallel wie Signal Lab) ->
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
  - `types.py` – Dataclasses (`BacktestRunRecord`, `OrderConfig`, ...)
  - `db.py` – DuckDB-Zugriff (read-only auf `market_data` / `analytics_data`, write auf `backtest_data`)
  - `schema.py` – Tabellen-DDL fuer `backtest_data.duckdb`
  - `runner.py` – Backtest-Runner (vectorbt 1.1.0 - Engine-Entscheidung gefallen)
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
- R-Multiple-Definition (geklaert): `(Exit-Entry) / (Entry-InitialSL) * direction`,
  ohne fixen SL: `NULL`.
- `run_id` = deterministischer SHA-256-Hash (`run_id_from_config`),
  `params_json` vom Typ JSON.
- Verifikation: DB-Test in `test/test.py` – Tabellen anlegen, INSERT + SELECT pruefen.

## Schritt 3: Read-only-Anbindung an die Quell-DBs

- `market_data.duckdb` (read-only): `ohlcv_bars` lesen (OHLCV + `spread`).
- `analytics_data.duckdb` (read-only): Signal-Events lesen
  (`run_id`, `symbol`, `tf`, `timestamp`, `direction`).
- Verbindungen bewusst **read-only** oeffnen (kein Schreibzugriff).
- Verifikation: Lese-Test in `test/test.py` – Signal-Events eines Runs
  laden und Richtung (`+1`/`-1`) prüfen.

### ERGEBNIS SCHRITT 3 (2026-08-22): UMGESETZT + VERIFIZIERT

Funktionen in `backtest_lab/db.py` (alle read-only):
- `connect_market()` / `connect_analytics()` – read-only-Connections
- `load_ohlcv(symbol, timeframe, date_from, date_to, limit)` –
  OHLCV + `spread`, optional Datumsfilter
- `load_signal_events(run_id, signal_type)` – Signal-Events eines Runs
  (direction +1/-1, price, strength, source_tf, signal_time)
- `get_signal_runs(symbol, timeframe)` – Run-Metadaten (fuer Schritt 4)

**WICHTIG - Zeitkonvention (Wanduhr-Garantie):** Beide Quellen speichern
TIMESTAMPTZ mit Berlin-Offset. Alle Extraktionen nutzen
`"time" AT TIME ZONE 'UTC'` und normalisieren auf **naive UTC**.
Damit sind Signal-Events und OHLCV-Bars auf derselben DST-korrekten
Zeitachse (Signal-Bar = echte Bar, abbildbar auf `open/high/low/close`).

**DuckDB-Syntax-Hinweis:** Der Datumsfilter lautet
`CAST(? AS TIMESTAMP) AT TIME ZONE 'UTC'` (AT TIME ZONE AUSSERHALB des
CAST - `CAST(? AS TIMESTAMP AT TIME ZONE ...)` ist ein Parser-Fehler).

Verifikation (`test_read_only_sources`, gruen):
- Schreibversuch auf market/analytics wird abgelehnt (read-only erzwungen)
- `load_ohlcv("GOLD","M30", Jan 2024)` -> 962 Bars, naive UTC, sortiert
- `load_signal_events(letzter Run SILVER/M30)` -> 237 Events, Richtung
  +1/-1, naive UTC
- **Alle 237 Signal-Zeiten liegen exakt auf SILVER/M30-Bar-Zeiten**
  (Konsistenz Signal<->OHLCV bewiesen)

## Schritt 4: Run-Auswahl (nur letzter Signal-Lab-Lauf)

- Query: nur Runs aus dem letzten Signal-Lab-Lauf anzeigen (keine Historie).
- UI: Tabelle mit Checkbox am Anfang der Zeile, Mehrfachauswahl
  (analog Signal Lab).
- Verifikation: Code-Inspektion + DB-Test der Query.

### ERGEBNIS SCHRITT 4 (2026-08-22): UMGESETZT + VERIFIZIERT

Funktionen (in `backtest_lab/db.py`, read-only):
- `extract_run_timestamp(run_name)` – parst den Lauf-Zeitstempel
  `_JJJJMMTT_HHMM` aus dem Signal-Lab-Run-Namen (letztes Vorkommen, auch
  hinter freiem Tag, z. B. `..._20260821_1436_p11-htf`); `None` bei
  `run_name_override` ohne Zeitstempel.
- `_effective_run_timestamp(run_name, created_at)` – bevorzugt den
  Name-Zeitstempel (tz-korrekt als Berliner Wanduhrzeit normalisiert,
  `tz_localize("Europe/Budapest")` = Wanduhr-Garantie), Fallback pro Run
  auf `created_at`.
- `get_last_signal_runs(symbol=None, timeframe=None, db_path=None)` –
  liefert NUR die Runs des letzten Lauf-Batches (gleicher maximaler
  effektiver Zeitstempel), keine Historie.

UI (in `backtest_lab/ui.py`):
- `render_run_selection(runs_df, initial_selection, page_size, label)` –
  marimo-Checkbox-Tabelle (`mo.ui.table`, `selection="multi"`): Checkbox
  am Zeilenanfang, Mehrfachauswahl. `run_id` ist versteckt
  (`hidden_columns`), bleibt aber im `.value` erhalten.
- `selected_run_ids(table)` – extrahiert die gewaehlten `run_id`s.

Verifikation (`test_last_signal_runs` in `test/test.py`, gruen):
- `extract_run_timestamp`: mit/ohne free_tag, Override, None, ""
- echte analytics_data: nur der letzte Batch (neuester Name-Ts) wird
  geliefert (SILVER/M30-Lauf `..._20260821_1608`), keine Historie
- Symbol/TF-Filter wirkt korrekt
- synthetische Test-DB (test/): Name-Ts (1100) schlaegt spaeteren
  `created_at` (Re-Run-Fall / `INSERT OR IGNORE`)
- synthetische Test-DB: `run_name_override` (kein Zeitstempel) ->
  `MAX(created_at)`-Fallback (alle Runs mit Max-Created_at)

**Hinweis:** Sweeps in derselben Minute verschmelzen weiterhin
(Zeitstempel hat Minuten-Granularitaet) - bekannte Grenze, siehe Abschnitt 8.

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

### ERGEBNIS SCHRITT 5 (2026-08-22): UMGESETZT + VERIFIZIERT

Neue Module/Funktionen:

- **`backtest_lab/ui_state.py`** (analog `signal_lab/ui_state.py`):
  - `default_state()` – Order-Parameter (spread 0.05 %, SL 2 %, TP 4 %,
    Size 1 %) + `date_range` + Run-Namen-Felder.
  - `load_state()` / `save_state()` – atomarer Save (tmp + rename) nach
    `data/backtest_ui_state.json`, Fallback auf Defaults bei
    fehlender/defekter Datei.
  - `get_marimo_states()` – Modul-Singleton (go_state, save_msg,
    refresh_ctl) stabil ueber Zell-Re-Runs (Signal-Lab-Fix-Pattern).
- **`backtest_lab/complexity.py`** (RAM-Schaetzung, JSON-Schwellwert):
  - `DEFAULT_CONFIG` / `load_complexity_config()` / `save_complexity_config()`
    – `data/backtest_complexity.json`: `max_ram_mb` (4096), `max_runs`
    (10000), `warn_ram_mb` (2048), `est_bytes_per_bar` (200),
    `est_overhead_mb_per_run` (5.0).
  - `bar_counts_for()` – echte Bar-Zahlen je (Symbol, TF) via read-only
    COUNT (nur vorhandene Kombinationen).
  - `estimate_complexity()` – `ComplexityReport`: n_runs (Kreuzprodukt),
    RAM total/per-Run, `ok`, blockierende `reasons` + nicht-blockierende
    `warnings`.
  - `go_allowed()` – True nur bei `ok` (GO-Button ausgrauen).
- **`backtest_lab/db.py`** (read-only, Schritt-5-Ergaenzung):
  - `count_bars(symbol, tf, date_from, date_to)` – COUNT mit demselben
    naive-UTC-Datumsfilter wie `load_ohlcv` (Wanduhr-Garantie).
  - `available_date_range()` – min/max der OHLCV-Zeitachse (naive UTC)
    als Grenzen der Kalender-Picker.
- **`backtest_lab/types.py`**:
  - `make_order_config()` – validierte `OrderConfig` aus UI-Werten
    (Spread 0..10 %, SL/TP > 0 oder None, Size 0..100 %); `ValueError`
    statt stiller Fehlschlag.
  - `order_params_json()` – `params_json` fuer `backtest_runs`.
- **`backtest_lab/ui.py`** (Schritt-5-Ergaenzung):
  - `render_order_params(defaults, date_min, date_max)` – `OrderParamsUI`
    mit `mo.ui.number/switch/date/text` (Spread, SL/TP-Switch+Zahl,
    Position-Sizing, Kalender-Picker + manuelle JJJJ-MM-TT-Eingabe).
  - `OrderParamsUI.to_order_config()` / `resolve_dates()` / `to_state()`
    (Datumsaufloesung: manuell > Kalender, innerhalb der Grenzen).
  - `render_complexity(report, config)` – Anzeige Anzahl Runs + RAM,
    Warn-/Ablehnungs-Meldungen vor dem Lauf.

Verifikation (gruen, in `test/test.py`):

- `test_complexity_estimation`:
  - `count_bars("GOLD","M30", Jan 2024)` = 962 (identisch zu `load_ohlcv`)
  - `bar_counts_for(["SILVER","GOLD"],["M30"])` -> nur vorhandene Kombis
  - RAM-Formel, n_runs-Limit-Ablehnung, RAM-Limit-Ablehnung,
    Warnschwelle (nicht blockierend), `go_allowed(None)=False`
  - Komplexitaets-Config JSON round-trip + Fallback (in `test/`)
- `test_backtest_ui_state`:
  - Defaults, save/load round-trip in `test/`, defekte Datei -> Fallback
  - `make_order_config`: gueltig + 5 ungueltige Faelle abgelehnt
  - `order_params_json` Serialisierung
- Regression gruen: `test_last_signal_runs`, `test_backtest_schema`,
  `test_read_only_sources`, `py_compile` aller geaenderten Dateien.

**Hinweis:** Der GO-Button wird im Notebook ueber `complexity.go_allowed()`
+ `mo.ui.button(disabled=...)` abgelehnt (Schritt 8/9, Notebook-Erstellung).

## Schritt 6: Backtest-Runner (v1)

- **Engine-Entscheidung GEFALLEN:** Stufe A - `vectorbt 1.1.0` (Smoke-Test
  gruen, siehe Abschnitt A/Ergebnis). Stufe B (numpy-Engine) wird nicht
  benoetigt.
- Aufruf-Schema (verbindlich, siehe Abschnitt A/API-Erkenntnisse):
  - Signale um 1 Bar shiften (Signal bei Bar T -> Entry am Open von T+1)
  - `price=open_`, `open`/`high`/`low` uebergeben
  - `sl_stop`/`tp_stop` mit `stop_entry_price=StopEntryPrice.FillPrice`
  - `upon_opposite_entry=OppositeEntryMode.Reverse` (Gegensignal/Reversal)
  - `slippage=spread_pct/2`
  - `size` via `SizeType.Percent` (position_size_pct/100), `init_cash`
    ausreichend hoch
  - Records: `pf.trades.records`; `direction` 0=Long/1=Short;
    `status=0` (offen) am Ende verwerfen
- Exits v1: Stop-Loss (fix), Take-Profit (fix) - intrabar; Gegensignal
  (Exit + neuer Gegensatz-Entry am Open derselben Folge-Bar).
- Timing: Signal Bar-Close T -> Entry am Open von Bar T+1 (lookahead-frei).
  Offene Positionen am `date_to`-Ende werden verworfen.
- `run_id` = deterministischer Hash (`run_id_from_config`); `signal_run_id`
  als FK auf den Signal-Run. Re-Run identischer Konfiguration ersetzt den
  vorhandenen Run (DELETE Trades + `INSERT OR REPLACE`, Bugfix 3).
- Chunking / Worker: `run_sweep_parallel`-Muster aus dem Signal Lab
  uebernehmen – Parameter-Chunks per Multiprocessing an VBT,
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

### ERGEBNIS SCHRITT 6 (2026-08-22): UMGESETZT + VERIFIZIERT

Modul **`backtest_lab/runner.py`** (Engine: vectorbt 1.1.0, Stufe A):

- `_build_signal_arrays()` – Signal-Events auf Bar-Indizes gemappt und um
  1 Bar geshiftet (Signal Bar T -> Entry am Open von T+1, lookahead-frei).
  Zeit-Zuordnung exakt (naive UTC beidseitig, Wanduhr-Garantie).
- `run_backtest()` – einzelner Lauf (reine Berechnung, kein DB-Write):
  - `vbt.Portfolio.from_signals` mit `price=open_` + `open/high/low`
  - `sl_stop`/`tp_stop` mit `stop_entry_price=StopEntryPrice.FillPrice`
  - `upon_opposite_entry=OppositeEntryMode.Reverse` (Gegensignal/Reversal)
  - `slippage = spread_pct/200` (symmetrisch auf Entry+Exit)
  - `SizeType.Value` mit `size = init_cash * position_size_pct/100`
    (SizeType.Percent unterstuetzt KEIN Reversal in v1.1.0 – verifiziert)
  - offene Positionen (`status=0`) werden verworfen
  - `_records_to_trades()` – vbt-Records (`direction` 0/1, `entry_idx`,
    `exit_idx`) auf `backtest_trades`-Form mit R-Multiple (Formel aus
    Abschnitt A, Punkt 3: `(exit-entry)/(entry-initial_sl)*direction`)
- `_compute_metrics()` – deterministische Run-Level-Metriken aus den
  GESCHLOSSENEN Trades: `net_profit, win_rate, profit_factor,
  max_drawdown_pct, sharpe_ratio, trade_count, avg_trade_pnl, expectancy`.
- `run_and_save_backtest()` – Lauf + Persistenz in `backtest_data.duckdb`.
- `run_backtests_parallel()` – Chunking-Muster aus dem Signal Lab
  (`run_sweep_parallel`): Multiprocessing (`spawn`, Windows-sicher) mit
  Worker-Init (`_init_worker`) und OHLCV-Cache pro Worker; Persistierung
  im Parent nach Chunk-Ende (keine Write-Locks). `progress_callback` +
  `cancel_callback` (Abbruch nach Chunk).

**WICHTIG (Windows/spawn, Regression >49k Zeilen):** Der komplette
Standalone-Smoke-Test (`test/_smoke_runner.py`) steht hinter
`if __name__ == "__main__":`. Ohne diesen Guard wuerde jeder spawn-Worker
das Hauptmodul neu importieren und erneut `run_backtests_parallel`
starten -> rekursives Spawnen / Endlos-Loop. Die Regression ist in
`test/test.py` (`test_backtest_runner`) integriert.

Verifikation (`test_backtest_runner` in `test/test.py`, gruen):
- synthetische DBs in `test/` (12 M30-Bars SILVER + 4 Swing-Change-Signale)
- 3 geschlossene Trades mit exakten Entry/Exit-Preisen geprueft:
  - Long Entry Open Bar1=101 (inkl. Slippage 101.00505), Reversal-Exit
    Open Bar4=99.995
  - Short Entry Open Bar4=99.995, Reversal-Exit Open Bar6=98.0049
  - Long Entry Open Bar6=98.0049, **TP intrabar Bar8=101.925096 gewinnt
    vor Gegensignal** (SL/TP vor Reversal, wie spezifiziert)
- R-Multiple (0.5 / -0.9951 / 2.0) und PnL je Trade exakt geprueft
- **PnL-Massstab (Bugfix vom Test gefunden):** `SizeType.Value` mit
  `size = equity * position_size_pct/100 = 100 $` kauft Anteile
  `size/entry_price` (z. B. T0: 100/101.00505 = 0.99005 Anteile) ->
  Trade-PnL ist -1.00005 / 1.9901 / 4.0002 (nicht die 10x-Werte einer
  frueheren Erwartung). net_profit/expectancy folgen demselben Massstab.
- Metriken: net_profit 4.9903, win_rate 2/3, profit_factor 5.99,
  expectancy 1.6634, max_drawdown >= 0
- Parallel-Runner: 2 Jobs / 2 Worker -> 2 eindeutige Run-IDs
  (unterschiedliche Konfiguration -> unterschiedlicher Hash),
  Fortschritt komplett, **kein Rekursions-Loop**
- Persistenz: 2 Runs in `backtest_runs` + je 3 Trades in `backtest_trades`
- Regression gruen: `test_vectorbt_smoke`, `test_backtest_schema`

## Schritt 7: Naming (Option A – kurzer Backtest-Name)

- Namensschema: `BT_{sp}{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_{JJJJMMTT_HHMM}`
  (Beispiel: `BT_sp005_sl2_tp4_sz1_20260821_2030`).
- Signal-Name NICHT in `backtest_runs` duplizieren – per JOIN ueber
  `signal_run_id` (FK) aus `analytics_data` holen.
- UI zeigt zwei getrennte Zeilen: Signal-Name (lang, aus Quelle) +
  Backtest-Name (kurz).
- Feste Benamungsvorgabe + individueller Textanhang (wie Signal Lab).

### ERGEBNIS SCHRITT 7 (2026-08-22): UMGESETZT + VERIFIZIERT

Modul **`backtest_lab/naming.py`**:

- `_fmt_pct(pct)` – kompakte Prozentdarstellung via `:g` (2.0 -> "2",
  2.5 -> "2.5"); `None` -> "x" (kein fixer SL/TP).
- `build_backtest_run_name(spread_pct, stop_loss_pct, take_profit_pct,
  position_size_pct, timestamp, free_tag)` – Namensschema Option A:
  `BT_sp{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_{JJJJMMTT_HHMM}`,
  optionaler `free_tag` (Leerzeichen -> Unterstrich, wie Signal Lab).
- Signal-Name wird NICHT in `backtest_runs` dupliziert (per JOIN ueber
  `signal_run_id` aus `analytics_data`), siehe `naming.py`-Docstring.

**Bugfix (vom Test gefunden):** `int(round(spread_pct*100))` nutzte
Banker's Rounding (`round(0.5)` -> 0). Fix: round-half-up
`int(spread_pct*100 + 0.5)` – `0.005 %` ergibt jetzt `sp001` statt `sp000`.

Verifikation (`test_backtest_naming` in `test/test.py`, gruen):
- Standard: `BT_sp005_sl2_tp4_sz1_20260821_2030` exakt
- Spread-Rundung: `0.1`->`sp010`, `0.005`->`sp001` (round-half-up)
- `None`-SL/TP -> `slx`/`tpx`
- Dezimalwerte: `sl2.5`, `tp4.25`, `sz0.5`
- free_tag: `BT_..._p11_htf` (Leerzeichen -> Unterstrich)
- `_fmt_pct`-Randfaelle (None, 0, 2.0, 2.5)
- Default-Timestamp (jetzt) via Regex `BT_sp005_sl2_tp4_sz1_\d{8}_\d{4}`
- Regression gruen: `test_backtest_runner` (nutzt Namensschema mit
  `BT_sp001_sl2_tp4_sz1_...`), `test_backtest_ui_state` (nutzt
  `build_backtest_run_name`), `py_compile`

## Schritt 8: Persistenz & Sicherheitsabfrage

- `backtest_ui_state.json` (Auto-Save oder per Button) analog Signal Lab.
- Sicherheitsabfrage vor dem Lauf (Anzahl Runs, RAM, Zeitraum).
- Fortschritts-Anzeige + Stop-Button (gefixtes Signal-Lab-Pattern
  uebernehmen – kein erneutes Bugfixing).

### ERGEBNIS SCHRITT 8 (2026-08-22): UMGESETZT (Notebook erstellt, Verifikation statisch/Backend)

Neues Modul **`backtest_lab/run_ui.py`** (analog `signal_lab/sweep_ui.py`):
- Modul-Singleton `_state` (thread-sicher, `threading.Lock`) als Single
  Source of Truth fuer Fortschritt + Abbruch:
  `get_state()`, `reset(total)`, `progress(done,total,current)`,
  `cancel()`, `is_cancelled()`, `set_thread()`, `is_alive()`,
  `finish(ids, summary)`, `fail(err)`, `set_message(msg, kind)`.
- Das Notebook nutzt es als `progress_callback`/`cancel_callback` des
  Runners und pollt den Zustand ueber `mo.ui.refresh` (0.5s).

Notebook **`Notebooks/03_Backtest_Lab.py`** (7 Zellen, `marimo check` gruen):
1. Setup (Modul-Importe inkl. `importlib.reload`, State, Datumsspanne,
   Komplexitaets-Config)
2. **Run-Auswahl** – `render_run_selection` (Checkbox-Tabelle, nur letzter
   Signal-Lab-Lauf, Mehrfachauswahl) + "Runs neu laden"-Button; gespeicherte
   Auswahl wird per `initial_selection` wiederhergestellt.
3. **Order-Parameter** – `render_order_params` (Spread, SL/TP-Switch,
   Size, Kalender + manuelle JJJJ-MM-TT-Eingabe) + Run-Name-Override +
   free_tag (on_change sichert in state).
4. **Run-Zaehler, Komplexitaet, GO + SAVE** – Komplexitaets-/RAM-Check
   (`estimate_complexity` auf den gewaehlten Symbolen/TFs); GO-Button
   `disabled=not go_allowed(report)` (zusätzlich: keine Auswahl / ungueltige
   Parameter / 0 Runs blockieren); SAVE persistiert `backtest_ui_state.json`.
5. **Sicherheitsabfrage + Start** – Bestaetigungs-Dialog (Runs, Symbole,
   TFs, Datum, Order, Name) mit exportierten Buttons
   `return btn_confirm, btn_cancel` (weakref-sicher); `_start_run` baut pro
   gewaehltem Signal-Run einen `BacktestJob` und startet
   `run_backtests_parallel` im Hintergrund-Thread (UI bleibt reaktiv).
6. **Fortschritt + Stopp + Status + Ergebnis** – Refresh-Timer NUR waehrend
   des Laufs (sonst kein Dauer-Tick); Spinner, Fortschrittsbalken,
   Stop-Button (`run_ui.cancel()`); nach Laufende: Summary + Tabelle der
   letzten `backtest_runs` direkt aus der DB.
7. Zustands-Bereinigung: `run_ui.is_alive()`-Check im GO-Handler
   (haengender Zustand nach Kernel-Neustart/Crash wird aufgeraeumt).

Verifikation (statisch + Backend, KEINE UI-Ausfuehrung):
- `py_compile` aller geaenderten Dateien gruen
- `marimo check Notebooks/03_Backtest_Lab.py` gruen (exit 0)
- marimo-Compiler: alle Zell-Referenzen aufgeloest (keine Missing Refs
  ausser `__file__`, das per `"__file__" in locals()` abgesichert ist)
- `mo.ui.button(disabled=...)` in marimo 0.24.0 verifiziert (Signatur)
- Backend-Kern (`test_backtest_runner`, `test_backtest_schema`,
  `test_backtest_naming`, `test_backtest_ui_state`,
  `test_complexity_estimation`) gruen
- Bugfix waehrend der Erstellung: `selected.itertuples()` -> `r.run_id`
  (Namedtuple, kein `r["run_id"]`-Indexing)

**Hinweis:** Der manuelle Funktionstest der UI erfolgt durch den Anwender
(Regel: keine UI-/Regressionstests durch den Assistenten).

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
