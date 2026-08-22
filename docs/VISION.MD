# Vision: Quantitative Trading & ML Confluence Platform

Eine modulare, hochperformante End-to-End-Architektur – von der mathematischen Signal-Entwicklung über vektorisierte Massentests und Machine-Learning-Konfluenzen bis hin zur hochverfügbaren Live-Order-Ausführung via MetaTrader 5.

---

## 1. Leitphilosophie & Kernarchitektur

* **Single Source of Truth:** Jeder Indikator implementiert den `BaseIndicator`-Contract und erzeugt ein `IndicatorResult` mit normalisierten `SignalEvent`s.


* **Entkoppelte Speicherpfade:**
* Visuelle Sessions nutzen den `MemorySignalService` (reiner RAM, kein DB-Overhead).


* Massentests und Analytics persistieren idempotent via `DuckDBSignalService` in `analytics_data.duckdb` (Composite Primary Key: `run_id, time, signal_type, price`).




* **Strikte Vektorisierung & VectorBT-Kompatibilität:** Signal-Pipelines und Indikator-Berechnungen nutzen NumPy/Pandas auf UTC-Basis (`[1, -1, 0]`), um direkt ohne Transformation in Backtests überzugehen.


* **Separation of Concerns:** Trennung von Signal-Erzeugung (zustandslos), Portfolio/Backtesting (State Machine), Modellierung (ML) und Order-Ausführung (Tick-basiert).



---

## 2. Die 4-Stufen-Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. SIGNAL LAB (Research & Signal-Erzeugung)                                 │
│    • 01_Chart_Inspector.py (Visuelle RAM-Prüfung)                          │
│    • 02_signal_lab.py (UI-gestützte Parameter-Sweeps)                       │
│    • Speichert normalisierte SignalEvents idempotent in DuckDB               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Liest SignalEvents & OHLCV)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. BACKTEST & ORDER LAB (Simulation & Execution Engine)                     │
│    • 03_backtest_lab.py (VectorBT Integration)                              │
│    • Multi-TF Execution (z.B. Entry H1/M30 Swing → Exit HMA 7 Pivot)         │
│    • Order-Logik: Trailing Stops, Order Swarms, Stacking & Risk Rules       │
│    • Speichert Trade-Ergebnisse & Kennzahlen (P&L, Sharpe, MaxDD)           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Liest Signale + Trade-Labels)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. ML CONFLUENCE ENGINE (Mustererkennung & Signal-Fusion)                   │
│    • 04_ml_lab.py (XGBoost / LightGBM)                                      │
│    • SHAP-Analyse zur Erkennung der profitabelsten Signal-Interaktionen     │
│    • Extraktion klarer Wenn-Dann-Regeln & Konfluenz-Scores (z.B. 78%)       │
│    • Modell-Export (ONNX / Joblib)                                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Exportiertes ML-Modell)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. LIVE TRADING & ORDER-COCKPIT (24/7 Execution & Monitoring)               │
│    • Headless Python Worker / Daemon auf Cloud-VPS                          │
│    • MLConfluenceIndicator berechnet Live-Wahrscheinlichkeit               │
│    • MT5-Schnittstelle: Swarm-Orders, Pyramidisierung & Trailing Stops     │
│    • Marimo Web-Dashboard / Desktop UI als Leitstand                        │
└─────────────────────────────────────────────────────────────────────────────┘

```

---

## 3. Modul- und Ordnerstruktur

Die Architektur trennt UI-Definitionen strikt von der Berechnungs- und Ausführungslogik:

* **`../algos` (Indikator- & Chart-Engine)**
* `base_indicator.py`: Abstrakte Basisklasse (`BaseIndicator`).
* `signal_events.py`: Datenklassen (`SignalEvent`, `IndicatorResult`) und NumPy-Extraktoren.
* `signal_service.py`: `MemorySignalService` und `DuckDBSignalService`.
* `ma_indicator.py`, `grid_indicator.py`, etc.: Mathematische Berechnungen.
* `chart_engine.py` & `chart_plugins.py`: Lightweight-Charts-Rendering und Canvas-Overlays.

* **`../signal_lab` (Orchestrierung)**
* `sweep_runner.py`: Grid- und Random-Search Orchestrator.
* `naming.py`: Sprechende Run-Namen (`{INDIKATOR}_{PARAM}_{SYMBOL}_{TF}_{DATUM}`).
* `ui_state.py`: Persistierung der letzten UI-Auswahl via `../data/ui_state.json`.


* **`backtest/` (Order-Simulation)**
* `multi_tf_engine.py`: Resampling und Bar-Close-Synchronisation ohne Lookahead-Bias.
* `execution_rules.py`: If/Else-Regeln für Entries, Pivots und Exits in VectorBT.


* **`live/` (Produktivbetrieb)**
* `mt5_bridge.py`: Anbindung an MetaTrader 5 via Python-API.
* `order_manager.py`: Swarm Engine (Bracket/Limit-Cluster), Stacking Controller & Trailing Stops.
* `circuit_breaker.py`: Not-Aus-Logik und globales Risikomanagement.


* **Notebooks / Apps**
* `01_Chart_Inspector.py`: Schnelle visuelle Inspektion.
* `02_Signal_Lab.py`: Massentests & Signal-Generierung.
* `03_Backtest_Lab.py`: VectorBT-Backtests & Order-Strategien.
* `04_ml_lab.py`: ML-Training & Konfluenz-Analyse.
* `live_trader.py`: Standalone-Daemon / Web-Cockpit für den Cloud-Einsatz.

---

## 4. Signal-Interaktion & Multi-Timeframe-Konfluenz

* **Styling & Marker-Registry:**
* MA: `swing_change` $\rightarrow$ Pfeile ▲/▼
* Grid: `circle_yellow` / `circle_fuchsia` $\rightarrow$ Kreise
* Multi-TF: Signale übergeordneter Zeitebenen (H1, H4, D1) werden farbintensiver und versetzt gestapelt gerendert.
* **Lookahead-Schutz:**
* Zeitstempel höherer Timeframes werden erst zum Bar-Close (Bestätigung) für untergeordnete Timeframes freigegeben.
* **Toleranz-Fenster (Rolling Window):**
* Konfluenz bedeutet nicht zwingend Bar-Identität, sondern das Eintreffen mehrerer Signaltypen innerhalb eines definierten Zeitfensters ($N$ Bars).

---

## 5. Machine Learning & Live-Konfluenz-Indikator

1. **Feature-Zusammenführung:** Alle `signal_events` werden auf einer Zeitachse gemappt.
2. **Target-Labeling:** Backtest-Ergebnisse aus `03_backtest_lab` markieren erfolgreiche Setups (Win = 1, Loss = 0).
3. **Erklärbarkeit via SHAP:**
* Ermittlung, welche Indikator-Kombinationen den höchsten statistischen Edge liefern.
* Regel-Extraktion für transparente Handelsentscheidungen.

4. **Live-Indikator (`MLConfluenceIndicator`):**
* Bindet das trainierte Modell ein und berechnet live am Kurs einen prozentualen Konfluenz-Score ($0–100\%$).
* Löst bei Überschreiten eines Schwellenwerts (z. B. $\ge 75\%$) strukturierte Order-Befehle aus.

---

## 6. Live-Execution-Architektur (Cloud VPS)

* **24/7 Daemon:** Ein Python-Hintergrunddienst verwaltet Ticks, Signale und Orders unabhängig von Frontend-Abbrüchen.
* **Advanced Order Management:**
* **Order Swarms:** Dynamische Gitter aus Limit- und Stop-Orders um Schlüsselzonen.
* **Stacking:** Risikofreies Pyramidisieren ausschließlich in profitablen Phasen.
* **Dynamic Trailing:** Nachziehen des Stop-Loss entlang dynamischer Pivots oder Volatilitätsbänder.


* **Monitoring & Cockpit:** Das Marimo-Notebook kann per `marimo run` als abgesichertes Browser-Dashboard auf dem Server betrieben werden.

## 7. Vision BacktestLab 

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

# 8 Offene Punkte
- PushMode: Indikator-Einstellung per Button durch SignalLab und BacktestLab schicken und gleich die EquityCurce sehen