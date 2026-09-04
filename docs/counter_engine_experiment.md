# Setup A: Counter-Engine (Ping-Pong) Experiment

> **Status:** Initialisierung (04.09.2026) — keine Testläufe, kein Sandboxing.
> **Bezug:** `scripts/counter_engine_profil.py` (neu) auf Infrastruktur-Basis von `scripts/phasen_volumen_profil.py` (v0.4.0-baseline-frozen, unverändert).

---

## 1. Ausgangslage & Motivation

Die Produktions-Baseline (Setup B / Reclaim, `scripts/phasen_volumen_profil.py`) handelt die **Bestätigung eines Fehlausbruchs** (Candle schließt nach Durchstich wieder innerhalb der Zone) und erzielt auf SILVER M15 über S1+S2 **+297,14R / 411 Trades (PF 2,33, R/Trade +0,723)**. Der Edge entsteht nachweislich durch **Topf-B-Dominanz** (§8.20/§8.21): Winner erreichen zu 92 % das TP2 (Gegenseite) und expandieren — Alpha entsteht durch Laufenlassen.

**Setup A (Counter-Engine / Ping-Pong)** ist die **antizipative Ergänzung**: Statt auf die Rückkehr *in* die Zone zu warten, wird bereits **am Kontakt mit der Kante (VAH/VAL)** in Mean-Reversion-Richtung gehandelt — der Markt *soll* von der Kante zur Gegenseite „ping-pongen". Abgrenzung zu Setup B:

| Dimension | Setup B (Reclaim, Produktion) | Setup A (Counter / Ping-Pong, dieses Experiment) |
|---|---|---|
| Einstiegs-Trigger | Fehlausbruch: Durchstich + Schluss zurück in der Zone | Kanten-Kontakt (Touch) mit/ohne Rejection-Kerze |
| Richtung | Gegen den Ausbruch (Reclaim) | Mit der Mean-Reversion (Kante → POC → Gegenseite) |
| TP1 (50 %) | POC (Fair Value) | POC (Fair Value) |
| TP2 (50 %) | Gegenseite minus 0,20 % Puffer | Gegenseite minus 0,20 % Puffer |
| Rest-SL nach TP1 | KEIN SL-Nachzug (Baseline-Invariante) | **Break-Even** (Derisking am Fair Value) |
| Risiko-Profil | Runner-Expansion (Topf B) | Absorptions-/Touch-Limitierung (Setup C) |

**Motivation:** Wenn die Value-Area-Geometrie eine echte Marktkante ist (fraktal über TF und Asset belegt, §8.24–§8.27), dann sollte ein **antizipativer Einstieg direkt an der Kante** bei disziplinierter Auswahl (Rejection, Touch-Limit) ein eigenständiges, stabileres R-Profil liefern — mit früherem Derisking (Break-even nach TP1) als die Reclaim-Engine.

---

## 2. Hypothesen

1. **Einstiegs-Disziplin:** *Candle Rejection* (Kante berührt, Schlusskurs verweigert die Seite: `close < vah` bei Short / `close > val` bei Long) liefert ein höheres kumuliertes R als *Direct Touch* (jeder Kantenkontakt), weil Momentum-Ausbrüche durch die Schlusskurs-Verweigerung gefiltert werden.
2. **Liquiditäts-Absorptionsfilter (Setup-C-Disziplin):** Die Begrenzung auf **Touch 1 und Touch 2** (`MAX_TOUCH_COUNT = 2`) schützt vor ausbrechenden Spät-Touches: Eine mehrfach getestete Kante verliert ihre Rejektions-Kraft (Absorption durch Gegenseite), erst recht nach Touch 3+.
3. **50 % POC-Derisking:** Die Teil-Realisation am Fair Value (POC) **mit Break-even-Nachzug der Restposition** erhöht die Systemstabilität: Die Gewinn-Hälfte sichert den Trade ab, die Rest-Hälfte läuft risikofrei zur Gegenseite — im Gegensatz zum vollen R-Risiko der Reclaim-Engine bis zum TP2.

**Testdesign (später, nach Freigabe):** AUG → S1/S2 auf SILVER M15, Modus-Vergleich `DIRECT_TOUCH` vs. `CANDLE_REJECTION`, Touch-Count-Sweep, Break-even-Vergleich gegen die Baseline-Invariante „KEIN SL-NACHZUG".

---

## 3. Parameter & Datenverträge

### 3.1 `CounterConfig` (verbindlicher Datenvertrag, Klassenebene im Skript)

```python
@dataclass(frozen=True, slots=True)
class CounterConfig:
    """Verbindliche Konfiguration der Counter-Engine (Setup A / Ping-Pong)."""
    # --- Datenbasis ---
    symbol: str = "SILVER"
    timeframe: Literal["M15", "M5", "M10", "M30", "H1"] = "M15"
    start: str = "2026-08-10"
    ende: str = "2026-08-28"

    # --- Phasen-Segmentierung (UNVERÄNDERT, Infrastruktur-Basis v0.4.x) ---
    min_candles: int = 46            # Phasen-Mindestlänge (M15 = 11,5 h Balance)
    min_phase_candles: int = 46      # Abbruch-Reifeschwelle (2-Close-Bruch)
    min_establish: int = 4           # Etablierung: Touch-Summe beider Grenzen
    pivot_lookback: int = 2          # Pivot-Bestätigung (M15 = 30 min, nachlaufend)
    va_pct: float = 0.93             # Value-Area-Resonanzkante (§8.23, SILVER)
    num_bins: int = 60
    smooth_win: int = 3
    valley_rel: float = 0.15
    min_mountain_pct: float = 4.0
    min_cluster: int = 2
    min_touches: int = 3             # Handelbare Phase: Touches je Grenze (U_final/L_final)
    min_spread_pct: float = 1.5      # Spread-Gate (relativ, SILVER-Kalibrierung)
    density_band: float = 0.15       # USD-Touch-Band (Touch-/Cluster-Zählung)
    tol: float = 0.34                # USD: 2-Close-Bruch-Toleranz (Z. 692/695)
    tol_touch: float = 0.15          # USD: Touch-Toleranz beim Phasen-Ende
    shift_tol: float = 0.05          # USD: Kanten-Verschiebungs-Schwelle
    grenz_kontakt_tol: float = 0.0   # Regel-7-Finalize (letzter Grenz-Kontakt)
    fenster_pivots: int = 100        # Schnittmengen-Fenster

    # --- Setup A: Signal-Logik ---
    max_touch_count: int = 2         # Liquiditäts-Absorptionsfilter (Touch 1+2)
    entry_mode: Literal["DIRECT_TOUCH", "CANDLE_REJECTION"] = "CANDLE_REJECTION"
    min_zone_candles: int = 30       # Mindest-Bars der laufenden Zone vor Signal-Scan
    min_reclaim_bounce: int = 2      # (reserviert, Symmetrie zu Setup B)
    min_reclaim_crv: float = 1.0     # (reserviert, Symmetrie zu Setup B)

    # --- Setup A: Trade-Management ---
    sl_pct: float = 0.45             # Stop-Loss relativ zum Einstieg
    anteil_tp1: float = 50.0         # 50 % der Position am POC
    tp2_puffer_pct: float = 0.20     # TP2 = Gegenseite abzüglich 0,20 % Puffer
    min_signal_abstand_bars: int = 12  # Cooldown (M15 = 3 h), je Richtung getrennt
    use_be: bool = False             # F6-Default: KEIN BE-Nachzug (Runner)
```

### 3.2 Touch-Tracking (barweise, kausal, drift-stabil)

- **F1 (Entscheid A, umgesetzt):** `touches_vah` / `touches_val` werden innerhalb der aktiven Phase gegen den **Snapshot der VOR-Bar** evaluiert: `vz_prev = _laufende_zone(df, p, k-1)` (Volume-Zone bis einschließlich `k-1`, kein Lookahead über die finale Phasen-Hülle). Die Signal-Bar `k` kann ihre eigene Kante nicht mehr durch ihr Volumen verschieben („Kante flieht vor eigenem Touch" ist eliminiert).
- **Ziel-Geometrie aus demselben Snapshot:** POC/TP1/TP2 sowie die Gültigkeits- und RR-Bedingungen (`entry > poc`, `e_preis > tp2`) nutzen ebenfalls `vz_prev` → deterministische, kausal geschlossene RR-Geometrie (Interview-Antwort F5, arretiert).
- **Signal-Bedingung:** Zählerstand (inkl. aktuellem Touch) `<= MAX_TOUCH_COUNT` — Touch 1 und 2 sind handelbar, Touch 3+ wird als Absorption verworfen.

### 3.3 Signal-Definition (Setup A)

| Richtung | Kante | DIRECT_TOUCH | CANDLE_REJECTION | Gültigkeit |
|---|---|---|---|---|
| SHORT | VAH (`U_zone`) | `high >= vah` | `high >= vah und close < vah` | `touches_vah <= MAX_TOUCH_COUNT` |
| LONG | VAL (`L_zone`) | `low <= val` | `low <= val und close > val` | `touches_val <= MAX_TOUCH_COUNT` |

- Einstieg: **Open der Folge-Bar** (`k+1`), sofern `k+1 <= Phasenende` (A3-Bounds-Guard).
- Strukturelle Gültigkeit: SHORT nur wenn `entry > POC`; LONG nur wenn `entry < POC`.

### 3.4 Trade-Management (Auflösung, 2 Hälften)

| Hälfte | Anteil | Ziel | Stop | Exit-Grund |
|---|---|---|---|---|
| 1 | 50 % | TP1 = **POC** (exakt) | `SL = entry × (1 ± 0,45 %)` | `TP1` / `SL` / `ENDE` |
| 2 | 50 % | TP2 = **Gegenseite ∓ 0,20 % Puffer** (SHORT: `val × (1+0,002)`; LONG: `vah × (1−0,002)`) | **Break-even (`entry`)** sobald Hälfte 1 TP1 erreicht hat; vorher `SL_init` | `TP2` / `BE` / `SL` / `ENDE` |

- **Break-even-Semantik:** Wird TP1 erreicht (`t1 < t_SL`), gilt für die Restposition ab der TP1-Bar der Stop auf `entry` (r = 0 bei Berührung). Wird TP1 nicht erreicht (voller SL), behält Hälfte 2 den ursprünglichen `SL_init`.
- **Intrabar-Konvention (konsistent zur Baseline):** Jede Hälfte wird unabhängig über den Zeitraum `[einstieg_bar … Datenende]` simuliert; das zuerst erreichte Ziel gewinnt (`argmax`-Maske). Alle Trades werden vollständig aufgelöst (sonst Close zum letzten Kurs).

### 3.5 Datenverträge (aus der Baseline-Infrastruktur übernommen)

`VolumeProfileData`, `MountainPeak`, `VolumeZone`, `PhaseData`, `MoveData`, `TradeResolution` — unverändert; `CounterSignal` ersetzt `ReclaimSignal`:

```python
@dataclass(slots=True)
class CounterSignal:
    typ: Literal["SHORT", "LONG"]
    mode: Literal["DIRECT_TOUCH", "CANDLE_REJECTION"]
    bar: int
    ts: pd.Timestamp
    einstieg_bar: int
    einstieg_preis: float
    vah: float                # laufende U_zone (Kante)
    val: float                # laufende L_zone (Kante)
    poc: float                # laufender POC
    touches_vah: int          # Zählerstand inkl. aktuellem Touch
    touches_val: int
    tp1: float
    tp2: float
    sl: float
    use_be: bool = False              # Abrechnungsvariante (True = BE-Nachzug)
    phase: int = 0
    trade: Optional[TradeResolution] = None
```

---

## 4. Tracking-Log

| Datum | Ereignis | Commit/Status |
|---|---|---|
| 04.09.2026 | **Initialisierung Counter-Engine (Setup A / Ping-Pong):** Doku `docs/counter_engine_experiment.md` + Skript `scripts/counter_engine_profil.py` angelegt (Infrastruktur-Basis `phasen_volumen_profil.py` v0.4.x, Segmentierung unverändert). Setup-A-Logik: Touch-Tracking (VAH/VAL, `MAX_TOUCH_COUNT = 2`), Entry-Modi DIRECT_TOUCH/CANDLE_REJECTION, TP1 50 % am POC mit Break-even-Nachzug, TP2 50 % an der Gegenseite ∓ 0,20 %, Cooldown 12 Bars. Keine Testläufe (Initialisierung). | `scripts/counter_engine_profil.py` (neu), `docs/counter_engine_experiment.md` (neu), Produktions-Baseline unverändert |
| 03.09.2026 | **F1 (Kanten-Drift) umgesetzt (Schritt 1):** Signal-Scan in `find_counter_signals` auf `vz_prev = _laufende_zone(df, p, k-1)` umgestellt — Touch UND Ziel-Geometrie (POC/TP1/TP2/entry>poc/RR) aus dem Snapshot VOR der Signal-Bar; Guards `k-1 >= i_start` und `min_zone_candles` auf den vz_prev-Präfix. Interview-Antworten arretiert: **F5** = Geometrie-Bindung an vz_prev, **F6** = Default `--be-nachzug false` für den 1. Gesamtlauf (Revision des früheren Defaults, A/B-Protokoll-Pflicht). Checkpoint AUG (F1 isoliert, BE true): 8 Signale / −0,13R / PF 0,97 (Status quo: 9 / +4,69R / PF 2,56) — Zwischenstand, Gesamturteil erst nach Schritt 2+3. | Skript geändert, Baseline unverändert |
| 03.09.2026 | **F3 (Outside-Bar) umgesetzt (Schritt 2):** In `find_counter_signals` wird eine Outside-Bar (high ≥ vah UND low ≤ val gegen den vz_prev-Snapshot in derselben Bar) verworfen (`continue`, Absorptionszähler bleiben unverändert) — eliminiert das Hedge-Artefakt (SHORT+LONG-Block feuerten unabhängig) und die Doppelzählung. Checkpoint AUG (F1+F3, BE true): **8 Signale / −0,13R / PF 0,97 — bitidentisch zu F1 isoliert** → in AUG existiert kein Outside-Bar-Doppelfeuer unter dem vz_prev-Regime; F3 ist in diesem Fenster verhaltensneutral (Schutzwirkung ist fensterabhängig, Urteil erst im Gesamtlauf S1/S2 mit größerer Stichprobe). | Skript geändert, Baseline unverändert |
| 03.09.2026 | **F2/F6 `--be-nachzug` umgesetzt (Schritt 3):** Konstante `USE_BE: bool = False` (F6-Default = KEIN BE-Nachzug, Runner-Philosophie), CLI `--be-nachzug=true|false`, Parameter `use_be` durch `find_counter_signals` → `_aufloesen_counter` durchgereicht; Hälfte-2-Logik: `if tp1_hit and use_be` → BE ab t1+1 (Kontroll-Arm), sonst `sl_init` aktiv bis TP2/SL/ENDE. Konsolen-/Stats-Header drucken die aktive BE-Variante (A/B-Protokoll-Pflicht). **A/B AUG 2026 (F1+F3, 8 identische Signale):** BE=false **+0,31R / PF 1,06 / TP2 2/8** vs. BE=true **−0,13R / PF 0,97 / TP2 1/8** → Delta **+0,44R** zugunsten BE=false. Trade-2-Beleg des BE-Trugschlusses: Runner P3 LONG erreicht nach TP1 die Gegenseite (+0,95R durch BE abgeschnitten); Trade 4 zeigt die reale Versicherungswirkung (−0,50R gespart bei Dreher zum SL). n=8 = Rauschen; F2-Urteil erst im Gesamtlauf AUG+S1+S2. Commit `5f6f28d`. | Skript geändert, Baseline unverändert |
| 03.09.2026 | **Schritt 4 (Typ-Integrität & Datenverträge):** `CounterConfig` um `use_be: bool = USE_BE` ergänzt (F6-Default False); `CounterSignal` um Abrechnungs-Kennzeichen `use_be` erweitert (beide Signal-Konstruktoren setzen es explizit → DataFrame-Auswertungen der A/B-Arme ohne Lookup auf die Lauf-Konfiguration). Doku §3.1/§3.5 nachgezogen. Verifikation: A/B-Läufe reproduzieren bitidentisch (BE=false +0,31R / BE=true −0,13R) — Schritt 4 ist verhaltensneutral. Commit `5fd2eae`. | Skript geändert, Baseline unverändert |
| 03.09.2026 | **S1/S2-Evaluation (F7/F2, 4 Läufe):** S1 (2026-02-05..08-28): 71 Signale, bef **+6,59R/PF 1,17**, betr **+6,43R/PF 1,17**. S2 (2025-01-01..12-01): 52 Signale, bef **+16,20R/PF 1,87**, betr **+12,82R/PF 1,80**. **Konsolidiert S1+S2:** bef **+22,79R/123 Tr/PF 1,39/R-Tr +0,185** · betr **+19,25R/123 Tr/PF 1,36** → F2-Delta **+3,54R** zugunsten BE=false (Runner bestätigt, aber klein). **F7-Urteil: AKZEPTANZ VERFEHLT** (PF 1,39 < 1,5; Summe R +22,79R < +50R; S1>0 ✓, S2>0 ✓) → Setup A wird **nicht** als eigenständiges System weiterverfolgt. Dekonstruktion: Regime-System (S2-Range PF 1,87 vs. S1-Expansion PF 1,17 — widerlegt die S2-Zerreibungs-Erwartung), schmale Signal-Basis (123 vs. 411 Tr), R-Tr nur 26 % der Setup-B-Qualität. AUG-Submenge im S1-Lauf weicht vom isolierten AUG ab (Segmentierung hängt an Vorgeschichte, F7-arretiert) → S1/S2-Läufe sind die einzige Benchmark-Wahrheit. Prüfbericht `test/tmp_counter_engine_pruefbericht_s1s2.txt`. | Baseline unverändert (Setup A: Experiment abgeschlossen, verworfen) |

---

## 5. Session-Stand (04.09.2026) — Projektkontext

**Gesamtprojekt:** Quant-Entwicklung & Backtesting-Framework, `F:\Python\PyLab`, Windows 11. Datenbank `data/market_data.duckdb` (`ohlcv_bars`, Symbole `SILVER` + `GOLD`, M15 in S1/S2/AUG vollständig). Baseline `scripts/phasen_volumen_profil.py` = **v0.4.0-baseline-frozen** (Tag `47b5c89`), nie verändern.

**Arretierter Stand (Doku `docs/makro_swings_experiment.md`, „State of Truth", Commits bis `fd18d6f`):**
- **Setup B / Reclaim-Baseline (SILVER M15):** S1+S2 = **+297,14R / 411 Trades / PF 2,33 / R-Tr +0,723** (WR 39,7 %). Produktions-Sperre auf M15/VA_PCT 0,93/SILVER empirisch zementiert. Topf-B-Dominanz: 92 % TP2-Expansion der Winner; Alpha durch Laufenlassen bis TP2 (§8.20–§8.21).
- **Negativ-Kette §8.7–§8.19:** 11 Filterkandidaten (CRV2, Anker-Volumen-Ratio, Initialisierung, Gegenkanten-Distanz, Consecutive-Loss-Cap, Kanten-Drift, Kapitulation, Dichte-Caps u. a.) datenwiderlegt — kein statischer Signalfilter verbessert die Baseline.
- **Parameter-Audit §8.22/§8.23:** VA_PCT 0,93 = Kuppe (empfindlichster Hebel), geometrische Resonanzkante; Code-Defaults = Optimum.
- **Multi-Timeframe §8.24–§8.26:** Fraktale Edge über H1 (R/Tr +0,663), M5 (zeit-äquiv. +0,55), Sweet-Spot-Matrix S1+S2: **M15 (+0,723) > H1 (+0,663) > M10 (+0,609) > M30 (+0,356)** — M15 bleibt Produktions-Standard.
- **Cross-Asset GOLD §8.27 (QS-3):** ATR-Ratio-Skalierung statt Preisratio; SL_PCT-Vola-Skalierung nötig; VA_PCT-Kuppe auf GOLD bei **0,95** (asset-spezifische Resonanz, +0,02 verschoben): +196,06R / 420 Trades, aber nur 34,8 % der SILVER-Kursrendite/Trade → Produktion bleibt exklusiv SILVER.

**Jetziger Schritt (dieses Dokument):** Start des **Setup-A-Experiments (Counter-Engine / Ping-Pong)** als neues, eigenständiges Experiment neben der Setup-B-Produktion. Erste Implementierung rein dokumentarisch + Skript-Anlage; Testläufe (AUG → S1/S2) erst nach Freigabe in `test/tmp_*` mit In-Memory-Exec-Wrappern, ohne `scripts/`-Modifikation.
