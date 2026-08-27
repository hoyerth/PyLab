# Gesamtfach- und Statistik-Konzept: Stat_Lab & Quantitative Level-Mechanik (SignalLab v2)

---

## 1. Leitphilosophie, System-Architektur & Datenfluss

### Leitphilosophie & Grundprinzip ("Von Ast zu Ast")
* **Marktmodell:** Der Markt bewegt sich in diskreten Schwüngen zwischen institutionellen Preislevels. Die Engine bewertet jeden Absprung von einem Level, jede Annäherung, jedes Verharren und jeden Durchbruch rein datengetrieben.
* **Level-Existenz:** Institutionelle Level sind keine Prämisse – Level sind die Matrix, in der gehandelt wird; erst die statistische Untersuchung zeigt gegebenenfalls tatsächliches institutionelles Interesse an spezifischen Levels.
* **These:** Ich kann prinzipiell und idealisiert an jedem Level auf einen Jump wetten, Gewinnwahrscheinlichkeit 50%. Ich möchte Gründe für eine höhere Wahrscheinlichkeit für eine Richtung finden.
* **Korrektur der Baseline-These (Spread-Drag):** 
  Die idealisierte Annahme einer 50%-Gewinnwahrscheinlichkeit an einem äquidistanten Grid gilt nur in einem theoretischen Markt ohne Transaktionskosten. In der Realität führt der Spread (Kauf zum Ask, Verkauf zum Bid) dazu, dass der Stop-Loss mathematisch näher am Ausführungspreis liegt als das Target. 
  Die `Stat_Lab` Engine evaluiert Signale daher immer gegen eine **Spread-bereinigte Baseline** (< 50%), um echten Edge von statistischem Rauschen zu unterscheiden.
* **Kein Trend-Hinterherrennen:** Es wird eine Crossingwahrscheinlichkeit für jede Linienannäherung ermittelt, aber kein Stop-Hunting betrieben.
* **Iterativer Optimierungszyklus:** 
  * Ergebnisse der statistischen Auswertungen fließen direkt in die nächste Version der Signal-Engine ein (Setzen dynamischer Wahrscheinlichkeiten für die aktuelle Bewegung).
  * Nach Abschluss der statistischen Optimierungszyklen werden die Daten im Machine Learning (ML) finalisiert.
  * Zielsystem: Automatisierte Adaption und Selbstoptimierung von Statistik und ML über die Reallaufzeit.
* **Prämissen:**
  * Stat_Lab soll zunächst nicht handeln und nicht optimieren. Es soll ausschließlich feststellen, ob das beobachtete Level-Verhalten statistisch existiert, unter welchen Bedingungen es auftritt und ob daraus eine robuste Wahrscheinlichkeitsaussage entsteht. Erst danach kommen Signaloptimierung, ML und Backtesting.
  * Das Resultat der quantitativen Untersuchung kann auch die vollständige Invalidität des gesamten Ansatzes sein (Schutz vor Bestätigungsfehlern).
  * Der Gesamtprozess dient als universelles Template für weitere Tradingkonzepte und Indikatoren.
  * Fokus auf schnelle Zwischenergebnisse ohne vorzeitigen Aufbau von Plattform-Overhead.
  * **Striktes Verbot von impliziten Lookaheads:** 
    Es ist absolut verboten, unbewusst zukünftige Datenpunkte ($t > t_0$) in die Feature-Berechnung oder Signal-Genese einfließen zu lassen. Jedes Feature muss zum Zeitpunkt der Signalentstehung kausal und deterministisch im Live-Betrieb verfügbar sein. Lookahead-Daten sind ausschließlich zur Erfassung des nachfolgenden Pfads (Target-Labeling: MFE, MAE, Target-Klassen über das 200-Bar-Fenster) zugelassen.
* **Kausalitäts- & As-Of-Garantie (Anti-Lookahead-Prinzip):**
  * Sämtliche aggregierten Zähler, Verweildauern und Zustandswerte werden strikt als "As-Of"-Zeitreihen berechnet ($t \le t_0$). Es fließen zu keinem Zeitpunkt zukünftige Bars ($t > t_0$) in die Feature-Berechnung ein.
* **Statistischer Schutz vor Data-Mining, Multiple Testing & p-Hacking:**
  * **Effektstärke vor Signifikanz:** Screening-Entscheidungen beruhen primär auf Effektstärken (Cramérs $V$, Cohen's $d$, Cliff's Delta) und praktischer Relevanz (Mindest-Edge gegenüber Baseline ausgedrückt in Spread-Einheiten: $\text{Edge} \ge 2.0 \times \text{Spread}$), nicht auf bloßen p-Werten, da bei Millionen Bars statistisch fast jede Konfiguration signifikant wird.
  * Zur Abwehr von p-Hacking beim kombinatorischen Screening werden Signifikanzniveaus zwingend über False Discovery Rate (FDR via Benjamini-Hochberg) oder Bonferroni-Korrektur adjustiert.
  * Daten-Partitionierung erfolgt vor jedem Screening strikt in Train-, Validation- und ein unberührtes Holdout-Set (Out-of-Sample).
* **Limitationen der Datenquelle & Datenqualitäts-Strategie (Broker-CFD vs. COMEX-Futures):**
  * Da Marktdaten auf MT5-Bid-Kursen eines Brokers basieren, können unternehmensspezifisches Repricing, abweichende Spreads und Slippage gegenüber den echten COMEX-Futures-Strikes Abweichungen erzeugen. Dies wird als methodische Limitation dokumentiert.
  * **Plausibilitäts-Audit:** Vor jeder Analyse wird ein strikter Datenkonsistenz-Check durchgeführt:
    * $\text{high} \ge \max(\text{open}, \text{close})$ und $\text{low} \le \min(\text{open}, \text{close})$.
    * Keine Null-Volumen-Bars während regulärer Handelszeiten.
    * Spread-Filter: $\text{spread} \le 3 \times \text{Median-Spread}$ zur Filterung technischer Ausreißer (wobei der Median-Spread strikt rollierend/historisch bis $t_0$ berechnet wird).
  * **Rollover-konsistentes Level-Tracking:** Stille CFD-Rollover-Sprünge werden via `is_rollover_event` markiert. Level-Preise werden entweder über Rollover-Sprünge hinweg adaptiv fortgeschrieben oder die betroffenen Zeitfenster werden vollständig aus der statistischen Analyse ausgeschlossen, um künstliche Datenpflege-Artefakte und Schein-Levels zu verhindern.

### End-to-End Datenfluss


```

[ DuckDB: data/market_data.duckdb (ohlcv_bars) ]
├── Timeframe: M1 (Brokerzeit: MT5 EET -> normalisiert auf UTC via additive Offsets)
└── Spalten: symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume
│
├──► [ JumpIndicator.compute() ] (algos/jump_indicator.py) ──► IndicatorResult (Events) ──┐
│                                                                                         │
└──► [ MAIndicator.compute() ]   (algos/ma_indicator.py)   ──► IndicatorResult (Events) ──┤
│
▼
[ DuckDB: analytics_data.duckdb ] (Persistierung via DuckDBSignalService) ◄───────────────────────┘
└── Composite Primary Key: (run_id, time, signal_type, price)
│
▼
[ Stat_Lab Transformation Engine ] (Notebook: Stat_Lab / stat_data.duckdb)
├── Kausalitäts-Check (As-Of t_0, kein Lookahead)
├── Plausibilitäts-Check (OHLC-Integrität, Spread-Outlier, Rollover-Ausschluss)
├── Zweistufige Level-Trennung (Analyse-Grid vs. Handels-Grid)
├── Forward-Path-Tracking (MFE / MAE über N = 200 M1-Bars via Decision Tree)
├── Microstructure-Metriken & Zeit-/Event-Klassifikation (inkl. DST-Korrektur)
├── Stateful Tracking (Liniengänger, Verweildauer an/über/unter Level, Ping-Pong)
├── Confluence Join (MA-Status, Hybrides Volume Profile, Diskrete Makro-Regimes)
└── Kombinatorisches Hypothesen-Screening & Ranking (FDR, Effektstärke, Spread-Edge)
│
▼
[ DuckDB: stat_data.duckdb ] (Typisierte Feature- & Target-Matrix)
│
├──► [ Automatisierter Signifikanz- & Analyse-Report ] (Effektstärken, Chi², KS-Test, Power-Analyse)
├──► [ ML Confluence Engine (04_ml_lab.py) ] (XGBoost / LightGBM, SHAP, Boruta, PDPs, Lasso Baseline)
├──► [ PyTrader Live-Ergebnisindikator ] (Entscheidungsunterstützung, z. B. M15-Darstellung auf M1-Basis)
└──► [ Export nach analytics_data.duckdb ] ──► [ Backtest Lab (03_backtest_lab.py) ]

```

---

## 2. Datenbank-Schema & Metadaten-Basis

### A. Metadaten-Tabelle (`data/app_data.duckdb` $\to$ `broker_symbols`)
Speichert Instrumenten-Metadaten zur punktgenauen Preisrekonstruktion:

```sql
CREATE TABLE broker_symbols (
    symbol        VARCHAR PRIMARY KEY,
    path          VARCHAR,
    is_favorite   BOOLEAN DEFAULT (CAST('f' AS BOOLEAN)),
    updated_at    TIMESTAMP DEFAULT (current_timestamp),
    point         DOUBLE,     -- MT5-Point (min. Preisinkrement, z. B. GOLD: 0.01, SILVER: 0.001)
    digits        INTEGER     -- MT5-Digits (Nachkommastellen, z. B. GOLD: 2, SILVER: 3)
);

```

### B. Marktdaten-Tabelle (`data/market_data.duckdb` $\to$ `ohlcv_bars`)

| Spalte | Datentyp | Beschreibung |
| --- | --- | --- |
| `symbol` | `VARCHAR NOT NULL` | Ticker-Symbol (z. B. `SILVER`, `GOLD`) |
| `timeframe` | `VARCHAR NOT NULL` | Bar-Intervall (Basis: `M1`) |
| `time` | `TIMESTAMPTZ NOT NULL` | Kerzen-Eröffnungszeit (UTC-normalisiert aus MT5 EET) |
| `open` | `DOUBLE NOT NULL` | Eröffnungskurs (Bid) |
| `high` | `DOUBLE NOT NULL` | Höchstkurs (Bid) |
| `low` | `DOUBLE NOT NULL` | Tiefstkurs (Bid) |
| `close` | `DOUBLE NOT NULL` | Schlusskurs (Bid) |
| `tick_volume` | `BIGINT` | Tick-Anzahl im Bar (Expliziter Liquiditäts-Proxy, kein echtes Börsenvolumen) |
| `spread` | `INTEGER` | Nativer Broker-Spread im Bar (in Punkten) |
| `real_volume` | `BIGINT` | Reales Börsenvolumen (sofern verfügbar) |
| `created_at` | `TIMESTAMP` | Import-Zeitstempel |
| **Primary Key** | `(symbol, timeframe, time)` | Eindeutiger Identifikator |

---

## 3. Institutionelle Marktstruktur, Level-Genese & Zeit-Mechanik

### A. Zweistufige Level-Systematik: Analyse-Grid vs. Handels-Grid

Das System unterscheidet formal zwischen zwei interagierenden Level-Hierarchien:

1. **Analyse-Grid (Dichtes Strike-Raster, z. B. $0.05\$$ bei Silber / $12.50\$$ bei Gold):**
* *Zweck:* Dient der reinen mikrostrukturellen Hypothesenprüfung (Gamma-Hedging, Orderbuch-Absorption, Liniengänger, Sweeps, Intrabar-Rejections).
* *Metriken:* `bars_hugging_level`, `penetration_depth`, `level_elasticity`, `crossing_type`.


2. **Handels-Grid (Weites Makro-Raster, z. B. $0.50\$$ bzw. $1.00\$$ bei Silber / $25.00\$$ bzw. $100.00\$$ bei Gold):**
* *Zweck:* Definiert übergeordnete Swing-Ziele, finale Target-Exkursionen ($L_{\text{target}}$) und Portfolio-Handelsentscheidungen.
* *Zusammenspiel:* Reaktionen am dichten Analyse-Grid dienen als früher Konfluenz-Trigger für den Start einer Ausdehnung zum nächsten weiten Handels-Level.



### B. Ursachen fester Preis-Levels & Strike-Dynamik

* **Option Strikes & Dealer Gamma Hedging (COMEX):**
* Silber-Optionen (SI) notieren standardmäßig in $0.05$-Schritten.
* Gold-Optionen (GC) notieren standardmäßig in $12.50$- bzw. $25.00$-Schritten (Achtel bzw. Viertel von $100\$$).
* Market Maker sichern ihre Gamma- und Delta-Risiken dynamisch an diesen Strikes ab, wodurch dichte Liquiditätswände und Pinning-Effekte entstehen.


* **Historische Varianz & Change-Point-Detection:**
* Bei massiven Veränderungen des absoluten Preises oder der impliziten Volatilität verschiebt sich die Liquidität in breitere Strike-Intervalle (z. B. von $0.025\$$ auf $0.05\$$ bei Silber).
* Die Analyse nutzt Change-Point-Detection im Walk-Forward-Verfahren, um dynamisch zu erkennen, wann ein Level-Raster seine Gültigkeit verliert.



### C. Ursachen zeitlicher Taktungen, Session-Grenzen & Marktlücken

* **Exakte UTC-Session-Definitionen:**
* `ASIA`: 00:00 UTC – 07:00 UTC (Tokyo / Singapur Hauptliquidität).
* `LONDON_PRE`: 07:00 UTC – 08:00 UTC (Vorbörse Europa).
* `LONDON_MAIN`: 08:00 UTC – 13:30 UTC (Europäischer Interbankenhandel).
* `NY_CASH_OPEN`: 13:30 UTC – 15:00 UTC (US-Futures & Kassamarkt-Eröffnung).
* `NY_AFTERNOON`: 15:00 UTC – 21:00 UTC (US-Nachmittag bis Kassa-Close).


* **TWAP/VWAP-Ausführungsfenster:**
* Institutionelle Großaufträge (Zentralbanken, Fonds) werden via TWAP über diskrete Zeitblöcke (15, 30, 60 Minuten) abgewickelt. Neue Tranchen starten exakt um `:00`, `:15`, `:30` oder `:45`.


* **Fixing-Phasen (Institutionelle Calendar-Integration):**
* LBMA Gold Price Auction: 10:30 UTC und 15:00 UTC.
* LBMA Silver Price Auction: 12:00 UTC (13:00 Londoner Zeit).
* Phasenspezifische Analyse: Pre-Fixing-Phase (30 Minuten vor Fixing), Core-Fixing, Post-Fixing-Phase (15 Minuten nach Fixing).
* COMEX Settlement Window: Täglich 19:25–19:30 Uhr DE (13:25–13:30 New York / 18:25–18:30 UTC) mit konzentriertem Volumeneinschuss zur Kursfestlegung.


* **Varianz- und Volatilitätsphasen um Stundengrenzen:**
* Auffällig häufiges Erreichen von Levels zur halben oder vollen Stunde.
* Fiese Bewegungen 5 Minuten vor bis 10 Minuten nach dem Stundenwechsel.
* *Liquidity Sweeps & Stop Runs:* 5 Minuten vor dem Stundenwechsel sammeln Algorithmen gezielt Stops ab, um Liquidität für die Folgetranche zu beschaffen.
* *Spread-Ausweitung:* Market Maker passen Quotes um den Stundenwechsel an, was zu weiten Spreads und Fehlausbruchsdochten führt.


* **Ausschlusszeiten & Feiertage (Dünne Liquidität):**
* Wochenend-Gaps (Freitag 21:00 UTC bis Sonntag 22:00 UTC) und US/UK-Feiertage (Thanksgiving, Weihnachten, Neujahr, Bank Holidays) werden als Sonderregime isoliert oder ausgeschlossen, um Spread- und Volumenverzerrungen zu verhindern.


* **Kritischer Pfad: DST-Offset-Kalender:**
* Dynamische Korrektur der 2–3-wöchigen Zeitverschiebung zwischen US- (EDT) und Europa-Sommerzeit (CEST/EEST) zur fehlerfreien zeitlichen Zuordnung aller Events.



### D. Makroökonomische Events & Exogene Makro-Regimes (Zweistufige Integration)

* **Wirtschaftsdaten (US-Release-Kalender):**
* 13:30 UTC (14:30 DE / 08:30 NY): NFP, CPI, PPI, Retail Sales – Liquiditätsentzug 2 Minuten vor Release, gefolgt von Spikes, doppelten Richtungswechseln und Spread-Explosionen.
* 14:45 UTC (15:45 DE / 09:45 NY): S&P Global Einkaufsmanagerindizes (PMI) – 15-Minuten-Verzögerungseffekt.
* 15:00 UTC (16:00 DE / 10:00 NY): ISM, Verbrauchervertrauen.


* **Börsen-Eröffnungen:**
* 07:00 UTC (09:00 DE / 08:00 London): Europa-Kassastart & Londoner Interbankenhandel.
* 13:30 UTC (14:30 DE): Eröffnung der COMEX-Futures-Hauptsession.
* 14:30 UTC (15:30 DE / 09:30 NY): US-Kassaeröffnung (NYSE/Nasdaq) – maximale Volatilitätsausschläge in den ersten 15 Minuten bis 14:45 UTC.


* **Notenbank-Entscheide:**
* 19:00 UTC (20:00 DE / 14:00 NY): US-Zinsentscheid (FOMC Statement).
* 19:30 UTC (20:30 DE / 14:30 NY): FOMC-Pressekonferenz – erratische Richtungswechsel typischerweise ab Minute 10 bis 20.


* **Korrektur gegen Autokorrelations-Falle (Diskrete Makro-Zustände):**
* Makrodaten (DXY, 10Y TIPS, VIX, Zinsstruktur) dürfen nicht als hochfrequente M1-Features eingebunden werden, um künstliche Stichprobenaufblähung und Autokorrelation zu vermeiden.
* *Modellierung:* Transformation in niedrig-dimensionale diskrete Regime-Zustände:
* `vix_regime`: `'LOW'` ($<15$), `'NORMAL'` ($15–25$), `'ELEVATED'` ($>25$).
* `yield_curve_regime`: `'INVERTED'` ($<0$), `'FLAT'` ($0–50\text{bp}$), `'STEEP'` ($>50\text{bp}$).
* `dxy_trend_regime`: `'BULLISH'`, `'BEARISH'`, `'NEUTRAL'` (auf Basis übergeordneter H4/D1-Mittelwerte).





---

## 4. Quantifizierter Feature-Katalog (`stat_data.duckdb`)

### A. Statische & Dynamische Grid-Geometrie (Zweistufige Zuordnung)

* `level_price` (`float`): Absoluter Basispreis des Niveaus.
* `grid_layer` (`str`): `'MICRO_STRIKE'` ($0.05\$$ / $12.50\$$) vs. `'MACRO_TRADE'` ($0.50\$$ / $100.00$).
* `level_type` (`str`): `'MAJOR_ROUND'` (z. B. $1.00\$$ / $50.00\$$) oder `'INTERMEDIATE_GRID'` (z. B. $0.05\$$ / $12.50\$$).
* `distance_to_level_open` (`float`): Distanz von `open` zum Level.
* `distance_to_level_close` (`float`): Distanz von `close` zum Level.
* `distance_nearest_untouched` (`float`): Minimaler Abstand zum nächsten unberührten Level (`abs(low - Level)` bzw. `abs(high - Level)`).
* `penetration_depth` (`float`): Maximale Überdehnung über das Level hinaus (`high - Level` bei Long-Sweeps, `Level - low` bei Short-Sweeps).
* `reentry_delta` (`float`): Distanz, mit der der Bar nach einer Penetration wieder innerhalb schließt.
* `level_density_100` (`int`): Anzahl relevanter Preislevel im Bereich $\pm 1.00\$$ um den aktuellen Kurs (Liquiditätsdichte-Metrik).
* `level_respect_ratio` (`float`): Anteil historischer Tests ohne Penetration.
* `level_elasticity_bars` (`int`): Bars bis zur Kursrückkehr nach einer Penetration.
* `touch_interval_bars` (`int`): Zeitspanne zwischen den letzten zwei Berührungen desselben Levels.

### B. Stateful Touch-Historie, Ping-Pong & Versuchs-Zähler (Strikt As-Of $t_0$, Lookahead-Schutz)

* **Lookahead-Audit für SQL/Windowing:** Alle Aggregationen in DuckDB nutzen zwingend `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` bezogen auf $t_0$, um Zukunfts-Zählungen auszuschließen.
* `touch_count_total` (`int`): Historische Berührungen dieses Levels strikt bis $t_0$ (Kausalität garantiert).
* `touch_count_session` (`int`): Berührungen in der aktuellen Handelssitzung bis $t_0$.
* `attempt_number_up` (`int`): Sequenznummer steigender Anläufe von unten nach oben gegen das Level bis $t_0$.
* `attempt_number_down` (`int`): Sequenznummer fallender Anläufe von oben nach unten gegen das Level bis $t_0$.
* `ping_pong_state` (`bool`): Oszillation unmittelbar zwischen zwei benachbarten Grid-Levels ohne Ausbruch bis $t_0$.
* `bars_since_last_touch` (`int`): Anzahl Bars seit dem letzten Kontakt mit diesem Level.
* `bars_above_level_before_reversal` (`int`): Anzahl Bars, die der Kurs jenseits des Levels schloss, bevor der Richtungswechsel erfolgte.

### C. Liniengänger, Crossing-Klassifikation & Verweildauer (Inkl. Orbit-Zonen außerhalb des Proximas)

* `bars_hugging_level` (`int`): Anzahl aufeinanderfolgender M1-Bars ($k \ge 4$), die der Kurs unmittelbar auf/an der Linie mäandert ("Liniengänger").
* `bars_dwelling_above` (`int`): Verweildauer (Anzahl Bars) oberhalb des Levels in der 50%-Orbit-Zone außerhalb des Proximity-Buffers ($0.025\$$ bei Silber).
* `bars_dwelling_below` (`int`): Verweildauer (Anzahl Bars) unterhalb des Levels in der 50%-Orbit-Zone außerhalb des Proximity-Buffers ($0.025\$$ bei Silber).
* `crossing_type` (`str`): Klassifikation der Anlauf- und Durchstichdynamik:
* `'FROM_OTHER_LEVEL'`: Direkter Schwung aus der Bewegung vom benachbarten Grid-Level kommend.
* `'FROM_MIDPOINT'`: Impuls entsteht erst in der 50%-Mitte der Spanne zwischen zwei Levels.
* `'FROM_HUGGER'`: Kurs verweilt $X$ Kerzen an der Linie, bevor der Durchbruch erfolgt.
* `'FROM_MOMENTUM_HUGGER'` (**Wichtigster Typ**): Aus der Bewegung kommend, mäandert $\ge 4$ Bars an der Linie und bricht dann dynamisch durch.
* `'CROSS_CONTINUE'`: Durchstich mit unmittelbarer Weiterbewegung zum Folgelevel.
* `'CROSS_AND_HUG'`: Durchstich mit sofortigem Verharren/Mäandern auf dem neuen Niveau.



### D. Zeit-, Session- & Mikrostruktur (UTC-Referenz)

* `minute_of_hour` (`int` [0–59]): Exakte Minute des Trigger-Events.
* `quarter_of_hour` (`int` [0, 15, 30, 45]): 15-Minuten-Intervall.
* `session_id` (`str`): `'ASIA'`, `'LONDON_PRE'`, `'LONDON_MAIN'`, `'NY_CASH_OPEN'`, `'NY_AFTERNOON'`.
* `is_macro_news_window` (`bool`): Event fällt in Release-Zeiten (13:30, 14:45, 15:00 UTC).
* `is_fixing_window` (`bool`): Event fällt in LBMA-Fixings (10:30, 12:00, 15:00 UTC).
* `fixing_phase` (`str`): `'PRE_FIXING'`, `'CORE_FIXING'`, `'POST_FIXING'`, `'NONE'`.
* `is_settlement_window` (`bool`): Event fällt in COMEX-Settlement (18:25–18:30 UTC / 19:25–19:30 DE).
* `is_hour_turn_window` (`bool`): Event fällt in Minute :55 bis :10.
* `is_holiday_or_gap` (`bool`): Markierung für Feiertage oder Wochenend-Randzeiten.
* `is_rollover_event` (`bool`): Markierung für sprunghafte CFD-Rollover-Anpassungen (Ausschlussfilter).
* `spread_points` (`int`): Nativer MT5-Spread aus der Datenbank.
* `spread_volatility` (`float`): Rollierende Standardabweichung normiert auf den Mittelwert (strikt historisch berechnet):

$$\text{spread\_volatility} = \frac{\text{stddev}(\text{spread\_points}, 20)}{\text{mean}(\text{spread\_points}, 20)}$$


* `spread_pct` (`float`): Relative Geld-/Brief-Spanne:

$$\text{spread\_pct} = \frac{\text{spread} \times \text{point}}{\text{close}} \times 100$$


* `ask_close_reconstructed` (`float`): Exakter Ask-Schlusskurs:

$$\text{ask\_close} = \text{close} + (\text{spread} \times \text{point})$$


* **Lookahead-Audit für statistische Baselines:** Schwellenwerte wie der `Median-Spread` dürfen niemals global über den Gesamtdatensatz gebildet werden, sondern ausschließlich rollierend über ein historisches Fenster (z. B. 1.440 M1-Bars) bis $t_0$.

### E. Bar-Dynamik, Price Action & Mean-Reversion

* **Lookahead-Audit für Bar-Close vs. Intrabar-Open:**
* Signale und zugehörige Kerzen-Features (wie `CLV`, `bar_range_vs_atr`) gelten erst mit dem offiziellen `bar_close` der M1-Kerze $t_0$ als bestätigt. Ein Intrabar-Signal vor Kerzenende darf keine Features nutzen, die den finalen `close` von $t_0$ erfordern.


* `atr_60` (`float`): M1 Wilder's RMA über 60 Perioden (1 Stunde Basis-Volatilität bis $t_0$).
* `bar_range_vs_atr` (`float`): Kerzenspanne normiert auf ATR ($Range / ATR_{60}$).
* `wick_to_body_ratio` (`float`): Verhältnis des Rejection-Dochts zur Kerzen-Gesamtspanne.
* `close_location_value` (`float` [-1.0, +1.0]): Relative Lage des Close:

$$\text{CLV} = \frac{(Close - Low) - (High - Close)}{High - Low}$$


* `mean_reversion_stretch` (`float`): Abstand des Close vom rollierenden Mittelwert ($Close - SMA_{20}$) als Z-Score (strikt mit `center=False` berechnet, kein Vorwärts-Shift).

### F. Volumen, Absorption & Hybrides Volume Profile

* **Lookahead-Audit für Session-Profile:**
* Das Session-Volumenprofil für $t_0$ aggregiert strikt vom Kerzenstempel `session_start` bis exakt $t_0$. Das Einbeziehen des vollständigen Tagesvolumens des gesamten Handelstages vor Abschluss des Tages ist strikt untersagt.


* `tick_volume` (`int`): M1 Tick-Volumen (Liquiditäts-Proxy).
* `relative_volume` (`float`): $Volume / SMA(Volume, 20)$ (historisches Fenster).
* `volume_per_range` (`float`): $Volume / (High - Low)$ (Absorptionseffizienz).
* `near_volume_node` (`str`): Relevanz externer Halte- und Swingpunkte (`'POC'`, `'VAH'`, `'VAL'`, `'LVN'`, `'NONE'`).
* `distance_to_volume_node` (`float`): Minimaler Abstand zum nächsten Volumenknoten.
* **Hybride Confluence-Berechnung:**

$$\text{VolumeConfluence} = 0.6 \times \text{POC}_{\text{Session}}(t \le t_0) + 0.3 \times \text{POC}_{\text{PriorDay}} + 0.1 \times \text{LVN}_{\text{5Days}}$$



### G. Indikator- & Diskrete Makro-Regimes (Post-Run Join)

* `ma_trend_alignment` (`int` [-1, 0, 1]): Status des HMA/MA zum Trigger-Zeitpunkt ($+1 = \text{Bullish}$, $-1 = \text{Bearish}$, $0 = \text{Neutral}$).
* `ma_signal_lead_lag_bars` (`int`): Versatz in Bars zwischen Jump-Event und MA-Swing-Signal.
* `vix_regime` (`str`): `'LOW'`, `'NORMAL'`, `'ELEVATED'`.
* `yield_curve_regime` (`str`): `'INVERTED'`, `'FLAT'`, `'STEEP'`.
* `dxy_trend_regime` (`str`): `'BULLISH'`, `'BEARISH'`, `'NEUTRAL'`.

---

## 5. Ground-Truth Target-Klassifikation & Pfadmetriken

Jedes Signal-Event startet ein Forward-Beobachtungsfenster von maximal $N = 200$ M1-Bars ($t_1 \dots t_{200}$).

### A. Eindeutige Definition von $L_{\text{target}}$ und $L_{\text{inval}}$

* **Ziellevel ($L_{\text{target}}$):**

$$L_{\text{target}} = L + (\text{direction} \times \text{grid\_interval})$$


* **Invalidierungslevel ($L_{\text{inval}}$):**

$$L_{\text{inval}} = L - (\text{direction} \times \text{grid\_interval})$$



(Alternativ: Re-Entry und Close jenseits von $L - (\text{direction} \times \text{proximity\_buffer})$).

### B. Deterministischer Decision-Tree (Überschneidungsfreie Zielklassen-Priorisierung)

Um Zielkonflikte (z. B. Sweep vor Target-Hit) innerhalb der 200 Bars eindeutig aufzulösen, gilt folgende strikte Auswertungsreihenfolge:

```
Start Bar t_1 bis t_200
│
├── 1. Wird L_inval berührt, BEVOR L_target erreicht wird?
│     └── JA ──► Liegt vorher ein Durchstich (penetration_depth > prox) vor?
│                 ├── JA  ──► TARGET_SWEEP_REVERSAL
│                 └── NEIN ──► TARGET_PINGPONG
│
├── 2. Wird L_target berührt, BEVOR L_inval berührt wird?
│     └── JA ──► TARGET_EXPANSION
│
└── 3. Nach 200 Bars weder L_target noch L_inval berührt?
      └── JA ──► TARGET_TIMEOUT

```

| Target-Klasse | Formales Kriterium | Strategischer Kontext |
| --- | --- | --- |
| **`TARGET_EXPANSION`** | Kurs erreicht $L_{\text{target}}$ innerhalb von 200 Bars, ohne vorher $L_{\text{inval}}$ zu touchieren. | Momentum Expansion zum nächsten Ast. |
| **`TARGET_PINGPONG`** | Kurs prallt vor Erreichen von $L_{\text{target}}$ ab und kehrt zu $L_{\text{inval}}$ / Ausgangszone zurück. | Mean-Reversion / Range-Oszillation. |
| **`TARGET_SWEEP_REVERSAL`** | Kurs sticht über Level/Puffer hinaus (`penetration_depth` $> \text{prox}$), scheitert am Folgelevel und läuft zu $L_{\text{inval}}$. | Liquidity Sweep / Gefakter Ausbruch. |
| **`TARGET_TIMEOUT`** | Nach $N = 200$ M1-Bars wurde weder $L_{\text{target}}$ noch $L_{\text{inval}}$ erreicht. | Trendlose Drift / Noise / Unentschlossener Markt. |

### C. Pfad- und Exkursions-Metriken

* **MFE (Absolut & ATR):** Maximaler Kursfortschritt in Signalrichtung innerhalb des 200-Bar-Fensters ($MFE / ATR_{200}$).
* **MAE (Absolut & ATR):** Maximaler Kursrücksetzer gegen die Signalrichtung innerhalb des 200-Bar-Fensters ($MAE / ATR_{200}$).
* **Time-to-Target ($\Delta t$):** Benötigte M1-Bars bis zum Erreichen des Ziels oder der Invalidierung.
* **Invalidierungs-Handhabung:** Im `Stat_Lab` führt ein Fehlausbruch strikt zur Erfassung von Invalidierung bzw. Sweep-Reversal. Im nachgelagerten `Backtest_Lab` werden Fehlausbrüche mit gezielten Stop-Loss- und Reverse-Cuts in profitables Trading überführt.

### D. Fixierte Execution-Preis-Regel (Kein Optimismus-Bias)

Zur Beseitigung jeglicher Willkür bei der Referenzpreiswahl wird die Ausführungsregel strikt vorab festgelegt:

* **Konservativer Referenzpreis:** Die Exkursionsmessung ($MFE / MAE$) startet **nicht** am Extremum der Triggerkerze und **nicht** am theoretischen Level-Preis, sondern exakt am **Schlusskurs der bestätigten Triggerkerze (`close[t_0]`) bzw. Eröffnungskurs der Folgekerze (`open[t_1]`)** zuzüglich des dokumentierten Spreads (`spread_points` zum Zeitpunkt $t_0$).

---

## 6. Analyseziele & Statistische Auswertungsdimensionen

1. **Differenzierte Level-Nutzung & Nullhypothesen:**
* $H_0(1)$: Die Verteilung der Target-Klassen ist unabhängig von der Session (ASIA, LONDON, NY).
* $H_0(2)$: Die Verteilung der Target-Klassen ist unabhängig vom Liniengänger-Status (`is_hugger`).
* $H_0(3)$: Die MFE/MAE-Verteilungen für `TARGET_EXPANSION` unterscheiden sich nicht von einer Random-Walk-Baseline.
* *Spread-Verhalten & Dead Zones:* Identifikation von Zeitfenstern mit untragbarer Spread-Belastung oder statistischem Zufallsverhalten.


2. **Kombinatorisches Hypothesen-Screening, FDR-Kontrolle & Effektstärke-Filter:**
* Systematisches Durchrechnen aller Merkmalsvariationen zur Identifikation robuster Signal-Kombinationen.
* **Ökonomischer Relevanz-Filter:** Voraussetzung für die Meldung eines Edges ist ein Mindestvorteil gegenüber der Baseline von mindestens **$2.0 \times \text{Spread}$** in Kurseinheiten.
* **Effektstärke-Maße:** Primärbewertung über Cramérs $V$ für $\chi^2$-Tests, Cohen's $d$ für MFE/MAE-Mittelwertdifferenzen und Cliff's Delta für nicht-parametrische Verteilungen (Schutz vor p-Hacking bei großen Datenmengen).
* **Multiple-Testing-Korrektur:** False Discovery Rate (FDR) via Benjamini-Hochberg-Verfahren.
* **Power-Analyse:** Bestimmung der minimalen Fallzahl pro Kombination zur Vermeidung von Typ-II-Fehlern (False Negatives):

$$n_{\text{min}} = \frac{2 \cdot (Z_{1-\alpha/2} + Z_{1-\beta})^2 \cdot \sigma^2}{\delta^2}$$


* *Liniengänger-Konditionierung:* Führt langes Verweilen an einer Linie zu verlässlichen Folgeausbrüchen oder erhöht es die Richtungsentropie (Unentschlossenheit)?
* *Mäander-Ausbruch:* Analyse von Bewegungen, die aus dem Schwung kommen, $\ge 4$ Bars an der Linie verharren und dann durchstechen.


3. **Optimierung der Signalerzeugungs-Parameter (Walk-Forward-Methodik):**
* **Adaptiver Proximity-Buffer:**

$$\text{prox\_dynamic} = \max(\text{prox\_static}, 0.15 \times \text{ATR}_{60})$$



Gedeckelt bei $0.25 \times \text{ATR}_{60}$ zur Vermeidung von Über-Pufferung.
* **Regime-Multiplikatoren:** $1.0$ (Normal), $1.5$ (Hohe Volatilität), $0.7$ (Niedrige Volatilität).
* Rollierende Kalibrierung im 3-Monats-Fenster (Train) mit 1-Monat-Fixierung (Test) statt einmaligem In-Sample Curve-Fitting.
* Zyklische Optimierung von Invalidierungskriterien und Schnittregeln.


4. **Aggregationen & Zeittakte:**
* Aggregation des Tick-Volumens und Spreads je 15-Minuten-Intervall (`:00`, `:15`, `:30`, `:45`).
* Messung von MFE/MAE-Extrema in Abhängigkeit von Tageszeit und Event-Fenstern.


5. **Multi-Timeframe & Externe Confluence:**
* Prüfung, ob die synthetische Betrachtung höherer Timeframes (M15, H1 aus M1-Daten berechnet) einen statistischen Vorteil liefert.
* Einfluss von Swing-Punkten, Marktstruktur, Peaks und Volumenspitzen (POC/VAH/VAL/LVN) im Zusammenspiel mit den Grid-Levels.


6. **Regimewechsel-Erkennung:**
* Erkennung von Marktphasen, in denen statische Basisparameter (z. B. Levelabstände) ihre Gültigkeit verlieren, und Definition quantitativer Indikatoren für diese Übergänge.



---

## 7. Plattform-Architektur & Reporting (Fokus Stat_Lab)

### A. Technische Plattform-Bausteine & Performance-Optimierung

* **Notebooks & Datenbanken:** Analyse-Notebook `Stat_Lab` operiert auf der dedizierten Analysedatenbank `stat_data.duckdb`.
* **DuckDB-Performance & Speicher-Design:**
* Nutzung von Columnar Storage mit Partitionierung nach `symbol` und `year`.
* Sparse Speicherung (`float32` statt `float64`) und Chunking in Blöcken von 100.000 Bars zur Vermeidung von RAM-Überläufen.
* Parallelisierung der Feature-Generierung über Multi-Threading (`concurrent.futures`).


* **Architektonische Flexibilität:** Modulares Schema zur schnellen Erweiterung um neue Kriterien (z. B. Verweildauer-Metriken).
* **Zeitzonen-Standard:** Maßgebend ist die Brokerzeit aus MT5 in EET/EEST. Alle Sommer-/Winterzeit-Varianzen (USA vs. Europa) werden über additive UTC-Offsets normalisiert.
* **Pipeline-Export:** Validierte Signalreihen werden zur Simulation im VectorBT-basierten `Backtest_Lab` (`03_backtest_lab.py`) nach `analytics_data.duckdb` exportiert.

### B. Datenpartitionierung & Validierungs-Architektur (Dukascopy ab 2018)

* **Historische Partitionierung:**
* `Train`: 2018-01-01 bis 2022-12-31 (5 Jahre Basis-Training).
* `Validation`: 2023-01-01 bis 2023-12-31 (1 Jahr Modell-Auswahl & Hyperparameter-Tuning).
* `Holdout`: 2024-01-01 bis 2024-12-31 (1 Jahr strikt unberührtes Out-of-Sample Test-Set).


* **Regime-Stratifizierung:**
* Stratifizierte Stichprobenziehung nach Volatilitätsregimen (VIX $< 15$, $15 \le \text{VIX} < 25$, $\text{VIX} \ge 25$) zur Vermeidung von Regime-Bias.


* **Walk-Forward-Struktur:**
* Rollierend: Train $(t-36 \text{ bis } t-12 \text{ Monate})$, Validation $(t-12 \text{ bis } t-1 \text{ Monate})$, Test $(t \text{ aktueller Monat/Jahr})$.



### C. Reporting, Visualisierung & Statistische Tests

* **Statistisches Reporting:** Umfangreiches Auswertungsdokument auf Knopfdruck.
* **Explizite statistische Tests & Metriken im Report:**
* $\chi^2$-Test (Chi-Quadrat) gepaart mit Cramérs $V$ für kategoriale Häufigkeitsverteilungen der Zielklassen über Sessions und Wochentage.
* Kolmogorov-Smirnov-Test (KS-Test) und Cohen's $d$ zum Nachweis von signifikanten MFE/MAE-Verteilungsverschiebungen gegenüber der Spread-bereinigten Random-Walk-Baseline.


* **Benutzer-Darstellung:** Einfache, zielführende Visualisierungen (Tabellen, Kennzahlen, CDF-Verteilungen, Boxplots; Verzicht auf 2D-Heatmaps).

---

## 8. Offene Punkte & Priorisierter Konkretisierungsbedarf

| Priorität | Themenfeld | Konkretisierungsbedarf | Status |
| --- | --- | --- | --- |
| **Hoch** | **Volume Profile Methode** | Dynamisches Session-Profil (M1) vs. Vortages-Fixpunkte; Validierung der Gewichte ($0.6 / 0.3 / 0.1$) im Walk-Forward. | Entscheidung vor Implementierung erforderlich. |
| **Hoch** | **Proximity-Buffer Dynamik** | Validierung von $\max(\text{prox\_static}, 0.15 \times \text{ATR}_{60})$ und Regime-Multiplikatoren im rollierenden 3-Monats-Fenster. | Kalibrierung im Walk-Forward. |
| **Hoch** | **Diskrete Makro-Regimes** | Festlegung der Schwellenwerte für VIX- und Yield-Curve-Regimes in DuckDB. | Klassifikation vor Feature-Generierung fixieren. |
| **Hoch** | **Holdout-Set Definition** | Finale Bestätigung der Partitionierung: 2018–2022 (Train), 2023 (Validation), 2024 (Holdout). | Datenaufteilung vor Screening fixieren. |
| **Mittel** | **Handels- & Risikoregeln** | Feinabstimmung von Fractional Kelly und Trailing-Stop-Offsets für den VectorBT-Export. | Für `03_backtest_lab.py` definieren. |
| **Mittel** | **Statistische Hypothesen** | Konkrete Festlegung der Mindest-Effektstärken ($d \ge 0.3$, $V \ge 0.15$) und Power-Parameter ($1-\beta = 0.80$). | Vor dem Screening definieren. |
| **Mittel** | **ML-Interpretierbarkeit** | Implementierung der SHAP-, Boruta- und PDP-Pipelines in `04_ml_lab.py`. | Im ML-Modul umsetzen. |
| **Niedrig** | **Operatives Monitoring** | Konfiguration der PSI-Drift-Schwellenwerte und Safety-Circuits für den Live-Daemon. | Für den Live-Betrieb vorbereiten. |

---

## 9. Roadmap & Future Scope (Post-Stat-Lab Phase)

### A. ML-Integration, Interpretierbarkeit & Feature-Selektion

* **Mustererkennung:** XGBoost / LightGBM in `04_ml_lab.py` mit strikter Begrenzung auf maximal 20 Kern-Features zur Vermeidung von Overfitting.
* **Baseline-Modell:** Lineares Modell (Lasso / ElasticNet) als Benchmark; komplexe ML-Modelle müssen eine statistisch signifikante Outperformance nachweisen.
* **Feature-Selektion:** Boruta-Algorithmus und Recursive Feature Elimination (RFE) mit Time-Series Cross-Validation.
* **Modell-Interpretierbarkeit:** SHAP-Werte zur Regel-Extraktion und Partial Dependence Plots (PDP) für die Top-10-Merkmale.
* **Trainings-Parameter:** Time-Series-CV mit rollierenden Fenstern, Early Stopping (Patience = 20), Shrinkage (Learning Rate $0.01 - 0.05$).

### B. Backtest- & Handelslogik (Backtest_Lab)

* **Signal-Ausführung:** Nur Signale mit $\text{Confidence-Score} \ge 0.65$.
* **Handelsfilter:** Keine Orders 5 Min. vor bis 10 Min. nach Makro-Releases; kein Handel in der letzten Handelsstunde vor Wochenend-Schluss (Freitag 20:00–21:00 UTC).
* **Order- & Risikomanagement:**
* Target: $L_{\text{target}}$ (Take-Profit).
* Stop-Loss: $L_{\text{inval}}$ bzw. $1.5 \times \text{Proximity-Buffer}$.
* Trailing-Stop: Aktivierung nach Erreichen von $50\%$ des Ziels (MFE-basiert).
* Positionsgrößen: Fractional Kelly ($25\%$ Kelly-Kriterium) mit Korrelations-Overlay (maximal $50\%$ Positionsgröße bei Signal-Korrelation $> 0.7$ zwischen Gold und Silber).


* **Backtest-Kennzahlen:** Sharpe Ratio (annualisiert), Maximum Drawdown (MDD), Profit Factor, Win Rate, Average Trade Duration, Monte-Carlo-Robustheitstest.

### C. Operative Umsetzung & Monitoring (Live-Betrieb)

* **Performance-Monitoring:** Tägliches P&L-Tracking mit Abweichungsanalyse (Soll vs. Ist) und monatlicher Walk-Forward-Validierung.
* **Drift-Erkennung:** Überwachung von Feature-Verteilungen via Population Stability Index (PSI).
* **Safety-Circuit (Not-Aus):** Automatische Deaktivierung des Algorithmus, wenn die Live-Performance um $> 2\sigma$ unter die Backtest-Erwartung fällt.
* **Audit-Logging:** Vollständiges Logging aller Entscheidungen (Signal, Filterung, Ausführung) und automatisierter wöchentlicher Performance-Report.
* **Live-Trading-Cockpit:** Einbettung der statistischen Confluence-Werte in den `MLConfluenceIndicator` und Integration als Ergebnisindikator in die PyTrader-App (Darstellung M15 auf M1-Berechnung).
* **Vollautomat (Traumziel):** Quantisierter Algorithmus zur vollautomatischen Order-Ausführung an validierten Schlüsselzonen via MT5.

```

