# Setup C: Trendfolge, Sägezahn-Expansion & Ausbruchs-Engine

> **Status:** Schritte 1–4b + Schritt 4 abgeschlossen (B1–B4 §2.5, C1–C5 §2.7, D1–D5 §2.9, H1–H4 §2.11, W1–W4 §2.12, Produktions-Blueprint §2.13, 05.09.2026); 274R-Artefakt eliminiert; F4+Zeit-Exit schlägt Stufen-Trailing in 16/18 Zellen; 1-Close-Vorteil Whipsaw-korrigiert (S1 N48 +18,2R → Netto +1,8R); **Schritt 4 abgeschlossen — Entscheidungsvorlage arretiert (Phase-1-Kern RAW-A + F4 + Zeit-Exit 48/96 + Suppression; Regime-Schalter = Stufe-5-Validierungs-Rückstellung) — Übergabe an Entwicklungsphase (`scripts/setup_c_profil.py`)** — **Entwicklungs-Schritt 1 verankert (§2.14: Acceptance-Gates L1/L2 + Architektur-Beschlüsse)** — **Phase 1 abgeschlossen & produktionsreif (§2.15: L1/L2-Gate bitgenau bestanden über AUG/S1/S2, Abnahmeprotokoll; `scripts/market_segmentation.py` + `scripts/setup_c_profil.py` committet)** — **Einheiten-Bereinigung D4-Ratchet (05.09.2026): µs/ns-Bug in `_kanten_reihe` beseitigt (statische Kante → zeitlich gültige Ratchet-Stufenfunktion); §2.13-D/§2.14/§2.15 re-arretiert — L1-F3/CONFIRMED/RETEST bitgenau unverändert, RAW-Split & L2 korrigiert (S1 N48 +22,81R / N96 +27,87R, n=38; S2 N48 +0,31R / N96 +0,98R, n=3; AUG erstmals n=2: +3,64R / −0,87R statt Vakuum)** — Baseline unverändert.
> **Bezug:** `scripts/setup_c_profil.py` (neu anzulegen) auf Infrastruktur-Basis von `scripts/phasen_volumen_profil.py` (v0.4.0-baseline-frozen, unverändert).

---

## 1. Ausgangslage & Motivation

Während Setup B (Reclaim / Fakeout) auf die Bestätigung von Fehlausbrüchen an den Value-Area-Grenzen spezialisiert ist (+297,14R / 411 Trades / PF 2,33), erleidet es in anhaltenden Trend- und Expansionsphasen systematische Verlustserien (z. B. Phase 102 in S1 mit 7 konsekutiven Verlusten und -6,01R). Setup A (Counter / Ping-Pong) scheiterte an den Akzeptanzkriterien (PF 1,39 / +22,79R), weil antizipatives Kanten-Fading im Expansionsregime versagt.

**Setup C (Trendfolge / Sägezahn-Expansion)** monetarisiert genau diese Ausbruchs- und Driftphasen:
* Erfassung von Kanten-Ausbrüchen und dynamischer Value-Area-Migration.
* Schutz vor Whipsaws durch Trennung von Ausbruchs-Typen (Raw mit Volumen, Confirmed 2-Close, Retest von außen).
* Gewinnsicherung durch Stufen-Trailing (Pivot-Stufen / dynamischer ATR-Puffer) statt prozentualem Trailing.

---

## 2. Parameter & Datenverträge

### 2.1 `TrendConfig` (Verbindlicher Datenvertrag)

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True, slots=True)
class TrendConfig:
    """Verbindliche Konfiguration für Setup C (Trendfolge & Sägezahn-Expansion)."""
    symbol: str = "SILVER"
    timeframe: Literal["M15", "M5", "M10", "M30", "H1"] = "M15"
    start: str = "2026-08-10"
    ende: str = "2026-08-28"

    # Phasen-Segmentierung (Infrastruktur Baseline v0.4.x unverändert)
    min_candles: int = 46
    min_phase_candles: int = 46
    min_establish: int = 4
    pivot_lookback: int = 2
    va_pct: float = 0.93
    tol: float = 0.34
    density_band: float = 0.15

    # Setup C: Einstiegs-Matrix
    entry_mode: Literal["BREAKOUT_RAW", "BREAKOUT_CONFIRMED", "RETEST_OUTSIDE"] = "BREAKOUT_CONFIRMED"
    raw_vol_mult: float = 1.5           # tick_volume >= 1.5x SMA20(tick_volume)
    retest_band: float = 0.15           # USD: Toleranzband um Kante für Retest
    retest_timeout_bars: int = 16       # M15-Bars: Retest-Gültigkeit nach Bruch (F7)

    # Setup C: Trailing & Risiko-Management
    sl_pct: float = 0.45                # Fester Initial-SL relativ zum Einstieg
    trailing_mode: Literal["PIVOT_STUFE", "VALUE_AREA"] = "PIVOT_STUFE"
    buffer_mode: Literal["FIXED_USD", "DYNAMIC_ATR"] = "DYNAMIC_ATR"
    fixed_buffer: float = 0.15          # USD: Fester Puffer unter Stufe
    atr_period: int = 7                 # Kurze ATR für rasche Expansion / Liquidation

    # Setup C: Adaptives Tightening
    ema_period: int = 20
    ema_slope_threshold: float = 0.001  # Schwellenwert für EMA-Abflachung
```

### 2.2 Signal-Definition & Einstiegsmodi

| Modus | Richtung | Trigger-Bedingung | Bestätigung |
|---|---|---|---|
| BREAKOUT_RAW | LONG / SHORT | Kanten-Durchstich ($hi \ge U$ bzw. $lo \le L$) | $tick\_volume \ge 1,5 \times \text{SMA}_{20}(tick\_volume)$ der Vor-Bars |
| BREAKOUT_CONFIRMED | LONG / SHORT | 2 konsekutive M15-Closes jenseits $h\_ref + TOL$ bzw. $l\_ref - TOL$ | Entspricht der Baseline-Phasenabbruchlogik |
| RETEST_OUTSIDE | LONG / SHORT | Kante bereits gebrochen; Pullback berührt Kante $\pm RETEST\_BAND$ innerhalb $RETEST\_TIMEOUT\_BARS$ (F7); Kurs hat seit Bruch den Stop-Level nie unterschritten (F8) | M15-Close verteidigt die Ausbruchsseite (Close bleibt außerhalb); Einstieg = open[k+1] (F6) |

### 2.3 Trailing-Hierarchie & Exit

- Initial-Stop: $SL\_PCT = 0,45\%$ relativ zum Einstiegspreis.
- Stufen-Trailing (Primär): Stop wandert sukzessive unter das jeweils letzte bestätigte Pivot-Tief (LONG) bzw. über das letzte Pivot-Hoch (SHORT), abzüglich des Puffers ($DENSITY\_BAND$ oder dynamische ATR).
- Adaptives Tightening (Sekundär): Flacht der EMA 20 ab (Steigung unterschreitet Schwellenwert), wird der Stop aggressiver an das Tief der Vor-Bar herangezogen, ohne die Position vorzeitig per Market-Order aufzulösen.
- Vollausstieg: Ausschließlich bei M15-Schlusskurs jenseits des aktuellen Trailing-Levels.

### 2.4 Audit-Beschlüsse für Schritt 2 (Replay, F4–F8 arretiert)

| ID | Thema | Beschluss |
|---|---|---|
| F4 | Initial-Stop Arm 1 & 2 | **Struktureller Stop** statt 0,45 %-SL: LONG `stop = min(low_struktur, brk_kante) − 0.15 USD`; SHORT gespiegelt. Arm 2 nutzt Tiefs beider Bestätigungs-Closes (`low[j]`, `low[j+1]`), Arm 1 das Tief der Bruchkerze `low[j]`. 0,45 %-SL bleibt reine **Referenzspalte**. Mess-Spalten: SL-Abstand in USD / % / R. Sensitivität: Kerzen-Variante ohne Kanten-Anker. |
| F5 | Volumen-Basis Arm 1 | Strikt kausal auf Vor-Bars: `tick_volume[j] >= 1.5 * SMA20(tick_volume).shift(1)`. Keine Selbstinklusion. Randfall `j < 20` → kein Trigger (separat ausweisen). |
| F6 | Execution Arm 3 | Einstieg = `open[k+1]` (Bar nach Retest-Bestätigungs-Close). **Keine** Limit-Order am Band. Sensitivität: `entry = close[k]`. |
| F7 | Retest-Timeout Arm 3 | `retest_timeout_bars = 16` (M15-Bars, 4 Handelsstunden). Kontakt muss in `k ∈ (brk_idx, brk_idx+16]` erfolgen; danach verfällt die Kante als Setup-C-Level. Sensitivität: 8/12/24. |
| F8 | Invalidierung vor Retest | Signal **ungültig**, wenn seit Bruch eine Bar (inkl. k) das Stop-Level unterschreitet (LONG `min(low) < stop`; SHORT `max(high) > stop`). Nicht still verwerfen → Kategorie `VERWORFEN_STOP_VERLETZT` (diagnostisch für Stop-Architektur). Grenzfall: Bandkontakt bis Unterkante erlaubt, echtes Unterschreiten verwirft. |
| D4 | Review-Korrektur 05.09. (RAW-Lookahead) | RAW-Kantenreferenz **strikt kausal** nur aus `U_hist`/`L_hist` (hist-protokollierte Kante). `U_final`/`L_final` nutzen die Gesamt-Phasenhistorie (bis `brk_idx`) und wären für frühere Bars Lookahead → Scan erst ab erstem hist-Eintrag. Fehlt die Kante der Scan-Richtung → `KEINE_KANTE` (kein Fallback auf die gegenüberliegende Kante, der Phantom-Signale erzeugte). |

### 2.5 Schritt-2-Befunde (Replay-Audit, 05.09.2026)

Ausführung: `test/tmp_setup_c_audit.py` (bitgenaue Re-Segmentierung per exec-Slice, DuckDB read-only). Verifikationsanker **bitgenau bestanden** (AUG 11 / S1 138 / S2 61 CONFIRMED-Signale, Früh-Kollaps-Referenz identisch zu Schritt 1: 36,4 % / 55,1 % / 37,7 %). Reports: `test/tmp_setup_c_audit_{AUG,S1,S2}.txt`.

**B1 — F4-Stop eliminiert den Früh-Shakeout (MAE ≥ 1R in ≤ 4 Bars):**

| Fenster | 0,45 %-Ref (CONFIRMED) | F4-Stop (CONFIRMED) | RAW 0,45 % → F4 | RETEST 0,45 % → F4 |
|---|---|---|---|---|
| S1 | 55,1 % | **5,8 %** | 52,7 % → 24,5 % | 44,1 % → 35,6 % |
| AUG | 36,4 % | **0,0 %** | 50,0 % → 30,0 % | 33,3 % → 33,3 % |
| S2 | 37,7 % | **0,0 %** | 30,8 % → 15,4 % | 33,3 % → 16,7 % |

Die institutionelle Stop-Räumung unterhalb der Ausbruchsstruktur wird durch die Kantenbindung (Kante ∪ Kerzentief ± 0,15) weitgehend abgefangen.

**B2 — R-Kompression durch breiten F4-Stop (Mentor-Warnung bestätigt):** `sl_R_ref` = F4-Abstand / 0,45 %-Referenz. S1 CONFIRMED median **2,80×** (max 10,2×), S2 median 3,14×; RAW S1 1,81×, RETEST S1 1,33×. Folge auf R-Basis (= sl_usd): S1 CONFIRMED MFE median @48 nur 1,13R (vs. 2,97R in Schritt 1 auf 0,45 %-Basis). Der strukturelle Stop erkauft das Überleben mit **halbiertem R:R** — zentrale Rechtfertigung für Schritt 3 (Stufen-Trailing).

**B3 — Signal-Ökonomie der Arme:**
- **CONFIRMED:** 138/138 Signale, engster Früh-Kollaps, aber breitester Stop (S1 MFE @48 median 1,13R, ≥2R@48 29,0 %).
- **RAW:** S1 nur 110/138 (56× KEIN_VOLUMEN, 110 Richtungs-Hälften ohne etablierte Kante → KEIN_DURCHSTOSS/KEINE_KANTE). Beste R-Ausbeute bei F4-Basis: S1 MFE @48 median **2,21R**, ≥2R@48 52,7 %.
- **RETEST:** S1 nur 59/138 (73× TIMEOUT, 5× VERWORFEN_STOP_VERLETZT, 1× KEIN_CLOSE_SCHUTZ). Der Retest bleibt in **53 % der Brüche aus** (16-Bar-Timeout). Wo er kommt: engster Stop (1,33×) und höchste Qualität (S1 MFE @48 median 2,99R, ≥2R 62,7 %), aber stark selektiv.

**B4 — RAW-Vorlauf-Verteilung** (`vorlauf_bars = brk_idx − trigger_idx`, Beleg aus `test/tmp_setup_c_vorlauf.py`): S1 median 8 Bars, aber bimodal: 23× Vorlauf 0 + 12× Vorlauf 1 (= 32 % triggern ≤1 Bar vor dem 2-Close-Bruch) neben langen Ausreißern (bis 454). AUG median 14 (Spanne 6–136). S2 median **91** (bis 3646) — im Range-Jahr ist der RAW-Trigger oft ein früher Ausbruchsversuch, der erst viel später bestätigt wird (oder die Phase bricht zwischenzeitlich in die andere Richtung). Der Vorlauf 0-Fall (RAW-Trigger exakt an der Bruchbar, Einstieg open[brk_idx+1]) ist der dichteste legitime RAW-Einstieg.

**Implikation für Schritt 3:** Der F4-Stop entschärft den 55-%-Shakeout, aber das R:R auf F4-Basis ist zu flach für einen statischen Exit. Die Energie läuft nach (Schritt 1), daher muss das Stufen-/Pivot-Trailing das R:R verdichten. RETEST als qualitativ stärkstes, aber seltenes Signal (43 %) vs. CONFIRMED als Volumen-Signal mit engem Stop sind die beiden Pole der A/B-Trailing-Auswertung.

### 2.6 Schritt-3-Beschlüsse (Trailing-Architektur A/B, F9–F11 + DV1–DV6 arretiert)

| ID | Thema | Beschluss |
|---|---|---|
| F9 | Trailing-Trigger | F4-Initial-Stop bleibt **starr**, bis eine bestätigte Stufe die Einstiegsseite überschreitet. **DV1:** Aktivierung an der **Stufe** (nach Puffer), nicht am nackten Pivot — LONG `pivot_low − Puffer > entry`, SHORT gespiegelt. Kein Nachziehen unter den Einstieg. Option A (Sensitivität): Nachzug ab Stufe > F4-Initial-Stop. |
| F10 | ATR-Puffer Variante B | `buffer = max(atr_mult × ATR₇, buffer_floor)` mit `atr_mult = 1.5` (Default), `buffer_floor = fixed_buffer = 0.15 USD`. Sensitivitäten: 1,0× / 2,0×. Begründung: 1,0× = ATR-Schrumpfungsfalle, 2,0× = Impuls-Überschwingen; Floor vererbt Robustheit der Fix-Variante. |
| F11 | Exit-Execution | **Differenziert:** F4-Initial-Stop **intrabar** (`low ≤ stop` / `high ≥ stop`); Trailing-Stufe **close-basiert** (Vollausstieg erst bei M15-Close jenseits des Stops). Sensitivität: Trailing intrabar. |
| DV2 | Kausalitäts-Laufzeit | Pivot bei Bar `p` ist nach Close von `p+2` bestätigt; Stop-Änderung wirksam ab Bar `p+3` (Exit-Check von `k=p+2` zuerst, neuer Stop ab `k+1`). ATR für den Puffer wird an der Bestätigungs-Bar `k=p+2` abgegriffen (ATR über Bars ≤ k). `ATR_n = SMA(TrueRange, n)`, `TR = max(H−L, \|H−Cₚᵣₑᵥ\|, \|L−Cₚᵣₑᵥ\|)`. |
| DV3 | Stop-Ablösung / Locked-in | Sobald der Stop auf eine Stufe > F4-Level gewandert ist, ist der F4-Stop obsolet. Intrabar-Dip unter das alte F4-Level bei Close über der aktiven Stufe = **kein Exit**. |
| DV4 | Datenvertrag | `TrailingConfig` + `TrailingResult` (siehe `test/tmp_setup_c_trailing.py` §1): Felder `trailing_trigger` (Default `STUFE_UEBER_ENTRY`), `trailing_exit` (Default `CLOSE`), `buffer_floor`; `ExitGrund` inkl. `TRAILING_SL_INTRABAR`. |
| DV5 | Sensitivitäten | F9-Option A (`STUFE_UEBER_INITIAL`), F10 (`atr_mult` 1,0/2,0), F11 (`trailing_exit=INTRABAR`) — je als Vergleichsspalte im Report. |
| DV6 | Kontroll-Benchmark | Modus `KEIN_TRAILING` (nur F4-Stop intrabar, Exit bei Datenende) als 7. Lauf im Report — belegt die R:R-Wiedergewinnung gegenüber dem Status quo. Auswertungs-Anker: `sum(r_f4)`, `mean`, WR, PF, `n(INITIAL_SL_INTRABAR)` vs. `n(TRAILING_SL_CLOSE)`. |

### 2.7 Schritt-3-Befunde (Trailing A/B-Simulation, 05.09.2026)

Ausführung: `test/tmp_setup_c_trailing.py` (bar-genaue Ratsche auf Schritt-2-Signalen; NaN-Fix `_agg_block` inkludiert). Verifikationsanker **bestanden**: Signalzahlen deckungsgleich (AUG 11/10/3, S1 138/110/59, S2 61/78/18), KEIN_TRAILING-Spalte ausschließlich `INITIAL_SL_INTRABAR` + `DATEN_ENDE`. Reports: `test/tmp_setup_c_trailing_{AUG,S1,S2}.txt`. **Kernfrage:** Gewinnt das Stufen-Trailing das durch B2 komprimierte R:R auf F4-Basis gegenüber KEIN_TRAILING zurück?

**Vergleichstabelle `sum(r_f4)` (F4-R-Basis; AUG/S1/S2 gesamt):**

| Lauf (Modus / Sensitivität) | AUG | S1 | S2 |
|---|---|---|---|
| VAR_A_FIXED (Default, close) | +7,17 | +8,96 | +0,63 |
| VAR_B_ATR mult=1,5 (Default, close) | +6,38 | **+30,14** | −2,42 |
| SENS: Option-A (Stufe > Initial) | +8,59 | +20,65 | −4,62 |
| SENS: Trailing intrabar | **+9,27** | −12,77 | +6,57 |
| SENS: ATR mult=1,0 | +5,61 | +20,63 | +1,10 |
| SENS: ATR mult=2,0 | +2,18 | +28,52 | −2,76 |
| **REF: KEIN_TRAILING** | +4,49 | **−43,08** | **+274,48** |

**C1 — KEIN_TRAILING dominiert S2 massiv (Trend 2025):** Status quo erzielt in S2 **+274,48R** (CONFIRMED +159,20R / mean +2,61R / PF 4,18; RAW +82,30R; RETEST +32,97R), getragen von `DATEN_ENDE`-Läufern (CONFIRMED 11/61, RAW 6/78, RETEST 2/18) mit mittlerer Haltedauer 1048/551/361 Bars bei extrem niedriger WR (CONFIRMED 18,0 %). Die R-Verteilung ist Power-Law-artig: wenige Megaläufer tragen alles, der F4-Stop begrenzt die Verlierer auf −1R. **Jede** getrailte Variante kappt diese Verteilung: bestes Trailing in S2 nur +6,57R (VAR_A intrabar) = −97,6 % gegenüber KEIN_TRAILING.

**C2 — Trailing dreht S1 (Stop-Räumungs-Regime 2026):** KEIN_TRAILING in S1 **−43,08R** (CONFIRMED −44,30R, RAW +23,89R, RETEST −22,67R; WR 3,4–8,7 %) — die breiten F4-Stops werden systematisch geräumt, nur 12/138 CONFIRMED erreichen Datenende. Beste Trailing-Varianten drehen das Vorzeichen: VAR_B mult=1,5 **+30,14R**, mult=2,0 +28,52R, Option-A +20,65R. Die Stufen aktivieren (CONFIRMED 40–46 %) und sichern nach der Erst-Rally, statt den −1R-Kollaps der späteren Stop-Räumung zu erleiden.

**C3 — Kein konsistenter Sieger (Regime-Kontingenz):** Keine der 6 Varianten schlägt KEIN_TRAILING in beiden Regimen. VAR_A-FIXED (close) ist die regime-stabilste Trailing-Wahl (AUG +7,17 / S1 +8,96 / S2 +0,63 — nie stark negativ, aber nie groß positiv). VAR_B_ATR ist nur in S1 überlegen (größerer Puffer = mehr Atem = fängt den Nachlauf), dreht aber in S2 ins Negative (−2,42 / −2,76). Die R:R-Frage aus B2 ist **durch Exit-Architektur allein nicht lösbar** — sie ist regime-kontingent.

**C4 — CONFIRMED in S1 strukturell defizitär (Einstiegs-Problem):** Unter **jeder** Trailing-Variante bleibt CONFIRMED in S1 negativ (−14,4 bis −22,7R), auch wo RAW (+28,5 bis +55,0R) und RETEST stark positiv sind. Der späte 2-Close-Bestätigungs-Einstieg in ein Regime ohne Nachlauf nach Bestätigung lässt sich durch Exit-Architektur nicht retten — der Hebel liegt beim Einstiegs-Timing, nicht beim Stop.

**C5 — F11-Sensitivität intrabar ist S1-Gift:** TRAILING_SL_INTRABAR ist in S1 der schlechteste Lauf (−12,77R; RETEST −18,65R, CONFIRMED −22,59R), aber in AUG (+9,27R) und S2 (+6,57R) jeweils der beste. Intrabare Auslösung von Trailing-Stufen beendet Positionen bei intrabaren Dips, die die CLOSE-basierte Default-Semantik (DV3) verteidigen würde — im Shakeout-Regime S1 genau die falschen Exits. Die **CLOSE-basierte Ausführung (F11-Default) ist die regime-stabilere Wahl.**

**Implikation für Schritt 4 (Prüfbericht):**
1. **Mess-Artefakt-Verdacht S2:** KEIN_TRAILING profitiert von `DATEN_ENDE`-Exits (offene Positionen am Fensterende werden zum letzten Close bewertet, Haltedauer bis >1000 Bars). Für einen produktionsnahen Vergleich braucht es einen definierten Zeit-/Ziel-Exit statt des Datenende-Benchmarks (die @48-Messung aus Schritt 2 ist die konservative Referenz: S1 CONFIRMED median 1,13R).
2. **Regime-Filter vor Exit-Design:** Der S1/S2-Gegensatz (beide SILVER M15, 2025 vs. 2026: −43R vs. +274R beim identischen Status quo) ist so extrem, dass eine Regime-Klassifikation (EMA-Slope-Tightening, §2.1 `ema_slope_threshold`) Voraussetzung für jede Exit-Entscheidung ist — Stufen-Trailing im Stop-Räumungs-Regime, Laufenlassen im Trend-Regime.
3. **CONFIRMED-Einstieg separat prüfen:** Arm 1 verliert in S1 unabhängig vom Exit — Einstiegs-Varianten (1-Close-Bestätigung, Nähe-Kante-Filter) sind vor Produktions-Integration zu testen.
4. **Optionale Folgeläufe (Schritt 4a):** VAR_A-FIXED mit definiertem Zeitexit (48/96 Bars) und ohne DATEN_ENDE-Aufblähung als sauberer 1:1-Vergleich gegen die @48-MFE-Referenz aus Schritt 2.

### 2.8 Schritt-4a-Beschlüsse (Zeit-Exit-Matrix mit Rechts-Zensierung, E1–E5 arretiert)

| ID | Thema | Beschluss |
|---|---|---|
| E1 | Zeit-Exit-Horizonte | Feste M15-Horizont-Matrix `N ∈ {24, 48, 96}` Bars als **terminale Exit-Regel** (Close der Exit-Bar). 24 (6h) = fängt schnelle S1-Reversals vor dem Liquiditätsabzug; 48 (12h) = primärer Referenzanker, direkt kompatibel zur MFE@48-Matrix aus Schritt 1/2 (B2/B3-Bezug); 96 (24h) = gibt starken S2-Trendphasen Raum, kappt aber das endlose Mitschleppen. |
| E2 | Rechts-Zensierung | Signal mit `entry_idx + N > len(df)` erreicht den Zeit-Exit gar nicht → Status `RECHTS_ZENSIERT`, **strikt aus der Performance-Berechnung isoliert** (r_f4/r_ref = NaN) und separat ausgewiesen. Verhindert relatives Rest-Artefakt durch Datenende-Close. |
| E3 | RAW-Cluster-Segmentierung | RAW-Signale nach Vorlauf `vorlauf = brk_idx − trigger_idx` trennen: **Cluster A** (`vorlauf ≤ 1`, `cluster_a_max_vorlauf=1`) = frische Ausbrüche unmittelbar an der Kante, CONFIRMED-kompatibel; **Cluster B** (`vorlauf > 1`, in S2 median 91 bis 3646 Bars) = separate Population (Range-Akkumulation/Fading, kein Trendfolge-Setup). Getrennte Auswertung, keine Vermischung. |
| E4 | Arm-Fokus | **Primär RAW** (einziger Arm mit Vor-Bruch-Einstieg, S1 MFE@48 median 2,21R); CONFIRMED (Negativ-Kontrolle für C4-Einstiegs-These) und RETEST (Qualitäts-Arm, Zeit-Exit nur als Cap) als Referenz-Spalten. |
| E5 | Exit-Matrix & Modus-Architektur | Matrix `{24, 48, 96}` × `{KEIN_TRAILING, VAR_A_FIXED}`; F4-Initial-Stop **intrabar** (F11 unverändert), VAR_A-FIXED-Trailing **close-basiert** (C5: CLOSE ist regime-stabiler), Puffer 0,15 USD. `KEIN_TRAILING + Zeit-Exit` = produktionsnahes Pendant zum 274R-`DATEN_ENDE`-Benchmark aus C1 (buy-and-hold mit hartem Zeithorizont statt offenem Ende). |

**Datenvertrag (freigegeben, wird in `test/tmp_setup_c_zeitexit.py` §1 umgesetzt):** `ZeitexitConfig` (frozen, slots): `fenster`, `symbol`, `timeframe`, `zeit_horizonte: tuple[int, ...] = (24, 48, 96)`, `cluster_a_max_vorlauf: int = 1`, `fixed_buffer: float = 0.15`, `sl_pct_ref: float = 0.45`. `ZeitexitResult` (slots): `arm`, `raw_cluster: RawCluster` (`CLUSTER_A_ENG`/`CLUSTER_B_WEIT`/`NICHT_RAW`), `phase`, `dir`, `horizont_bars`, `modus`, `entry_idx`/`entry_ts`/`entry_preis`, `f4_initial_stop`, `sl_usd`, `exit_idx`/`exit_ts`/`exit_preis`, `exit_grund`, `haltezeit_bars`, `r_f4`/`r_ref` (**NaN bei RECHTS_ZENSIERT**). `ExitGrund`: `INITIAL_SL_INTRABAR`, `TRAILING_SL_CLOSE`, `ZEIT_EXIT_CLOSE`, `RECHTS_ZENSIERT`.

### 2.9 Schritt-4a-Befunde (Zeit-Exit-Matrix, 05.09.2026)

Ausführung: `test/tmp_setup_c_zeitexit.py` (bar-genaue Ratsche auf Schritt-2-Signalen mit terminalem Zeit-Exit; Rechts-Zensierung E2; RAW-Cluster E3). Verifikationsanker **bestanden**: Signalzahlen deckungsgleich (AUG 11/10/3, S1 138/110/59 mit CLUSTER_A=35/CLUSTER_B=75, S2 61/78/18 mit CLUSTER_A=5/CLUSTER_B=73); `RECHTS_ZENSIERT` korrekt isoliert (S2: 2 Signale = 1 CONFIRMED + 1 RAW_A; S1/AUG: 0). Reports: `test/tmp_setup_c_zeitexit_{AUG,S1,S2}.txt`. **Kernfrage:** Wie groß ist das Setup-C-Ergebnis unter produktionsnahem Zeit-Exit statt DATEN_ENDE?

**Vergleichstabelle GESAMT `sum(r_f4)` (F4-R-Basis; KT = KEIN_TRAILING, VA = VAR_A_FIXED):**

| Fenster | N=24 KT / VA | N=48 KT / VA | N=96 KT / VA | Schritt-3 offen (DATEN_ENDE) KT / VA |
|---|---|---|---|---|
| AUG | +13,89 / +13,81 | +14,57 / +12,87 | +6,46 / +7,17 | +4,49 / +7,17 |
| S1 | +2,62 / +0,69 | **+49,25** / +21,92 | **+46,33** / +8,35 | −43,08 / +8,96 |
| S2 | +4,28 / +3,30 | +2,02 / +5,03 | **+8,67** / +2,19 | **+274,48** / +0,63 |

**D1 — Das 274R-Phantom ist geplatzt (S2 schrumpft auf +2R bis +9R):** Mit terminalem Horizont statt unendlichem `DATEN_ENDE` fällt S2 von **+274,48R auf +2,02R bis +8,67R** (−96 bis −99 %). Nur 2 von 157 S2-Signalen waren tatsächlich rechts-zensiert (beide isoliert) — das Artefakt kam fast vollständig aus den *gewerteten* offenen Läufern (Haltedauer bis 1048 Bars = verstecktes Buy-and-Hold im Silber-Bullenmarkt 2025, WR 3–18 %). Institutionelle Realität statt Retail-Wunschdenken: Der Zeit-Exit erzwingt die Kapital-Freisetzung, die der offene Benchmark nie leistete.

**D2 — Entzauberung des Stufen-Trailing (F4 + Zeit-Exit schlägt die Ratsche):** In **16 von 18 Matrix-Zellen** übertrifft `KEIN_TRAILING + Zeit-Exit` das VAR_A-Stufen-Trailing (Ausnahmen: S2 N=48, AUG N=96). Der Mechanismus: Ein Stufen-Stop unter kurzfristigen Pivot-Tiefs schneidet systematisch Trades ab, die nach dem ersten Impuls gesund konsolidieren. Der harte Zeit-Exit (48/96) in Kombination mit dem weiten F4-Strukturstop gibt der echten Expansion den Sauerstoff. **S1 kehrt das Schritt-3-Bild vollständig:** KEIN_TRAILING mit offenem Ende war −43R (weil die WR 3–8 %-Positionen bis zum eventualen −1R-Stop weiterliefen); mit N=48 ist es **+49,25R** und schlägt das beste Schritt-3-Trailing (VAR_B +30,14R). Das Trailing kostet in S1 bis zu **38R** (N=96: +46,33R vs. +8,35R). Die arretierte Ratsche (F9–F11) erweist sich unter sauberem Benchmark als **Performanz-Bremse**, nicht als R:R-Retter.

**D3 — RAW-Cluster-Segmentierung trennt Regime-Populationen (E3 bestätigt, aber nicht als Filter):**

| RAW `sum(r_f4)` (KT) | N=24 | N=48 | N=96 | n |
|---|---|---|---|---|
| S1 CLUSTER_A (≤1 Bar) | +16,09 | **+20,85** | +18,11 | 35 (mean 0,46–0,60R, WR 40–54 %) |
| S1 CLUSTER_B (>1 Bar) | +12,45 | +31,78 | **+36,02** | 75 (mean 0,17–0,48R, WR 21–33 %) |
| S2 CLUSTER_A | −0,45 | +0,39 | +1,92 | 5 (1 zensiert) |
| S2 CLUSTER_B | −3,21 | **−12,10** | **−12,49** | 73 |
| AUG (nur B) | +6,01 | +5,37 | +3,20 | 10 |

**Cluster A ist der Fels in der Brandung:** In S1 über alle Horizonte stabil positiv (+16 bis +21R, nie unter 0,46R mean) — der natürliche Kern von Setup C (frische Ausbrüche ≤ 1 Bar vor dem 2-Close-Bruch). **Cluster B ist extrem regime-toxisch in S2** (−12R bei N=48/96 = der eigentliche S2-Verlierer), aber in S1 der **größte Einzelgewinner** (+36R bei N=96). Die Trennung ist diagnostisch wertvoll, aber nicht als pauschaler Filter nutzbar — sie separiert *regime-abhängige Verhaltensweisen* (Range-Akkumulation vs. Momentum-Drift), nicht gut/schlecht.

**D4 — C4 für CONFIRMED bestätigt (Einstiegs-Defizit S1, nicht Exit):**

| CONFIRMED `sum(r_f4)` | N=24 | N=48 | N=96 |
|---|---|---|---|
| S1 KT | −9,30 | −8,56 | −7,32 |
| S1 VA | −10,40 | −18,20 | −21,19 |
| S2 KT | +4,54 | +6,94 | **+13,15** |
| AUG KT (N=48) | | +3,42 | |

S1 CONFIRMED bleibt unter **jeder** Exit-Architektur negativ (KT −7,3 bis −9,3R; Trailing verschärft auf −18 bis −21R, weil es die wenigen Läufer vorzeitig kappt). Der späte 2-Close-Einstieg kauft in S1 die Erschöpfung am Hoch/Tief von b+2 — ein reines Einstiegs-Timing-Defizit. In S2 (Trend) ist derselbe Arm dagegen positiv (+4,5 bis +13,2R), sobald er nicht unbegrenzt weiterträgt.

**D5 — RETEST als selektiver Qualitätsanker:**

| RETEST `sum(r_f4)` | N=24 | N=48 | N=96 |
|---|---|---|---|
| S1 KT | −16,61 | **+5,18** | −0,47 |
| S2 KT | +3,40 | +6,79 | +6,09 |
| AUG KT | +5,56 | +5,78 | +5,07 |

RETEST ist in S2 (+3,4 bis +6,8R) und AUG (+5,1 bis +5,8R) über alle Horizonte positiv, in S1 nur bei N=48 (+5,18R) — konsistent zur Schritt-2-Qualität (engster Stop, höchste MFE@48). Der Zeit-Exit wirkt dort als reiner Cap (RETEST-Haltedauern liegen meist < 48 Bars) und schadet nicht.

**Implikation für Schritt 4 (Prüfbericht):**
1. **Exit-Architektur vereinfacht sich:** `F4-Stop (intrabar) + terminaler Zeit-Exit (48/96)` ist die regime-stabilste und gleichzeitig einfachste Exit-Regel — die Stufen-Ratsche (F9–F11) ist unter sauberem Benchmark nicht mehr erste Wahl. Kandidaten für die Produktions-Empfehlung: S1/AUG N=48, S2 N=96 (KT jeweils +8,7R bis +49,3R).
2. **RAW-Cluster A ist der Setup-Kern** (stabil positiv über alle Fenster/Horizonte); RAW-Cluster B nur mit Regime-Filter bespielbar.
3. **CONFIRMED braucht Einstiegs-Reparatur** (1-Close-Variante o. Ä.) vor jeder Produktions-Integration — unabhängig vom Exit (4b).
4. **N=24 (6h) ist überall nur Mittelmaß** — der kurze Horizont schneidet die nachlaufende Energie ab (Bestätigung der Schritt-1-Δ48−12-Befunde); 48/96 sind die produktionsrelevanten Horizonte.
5. **Regime-Klassifikation (EMA-Slope, §2.1) bleibt Voraussetzung**, um zwischen S1-artigem (Stop-Räumung, N=48) und S2-artigem (Trend, N=96, Cluster-B-Drift) Verhalten zu unterscheiden.

### 2.10 Schritt-4b-Beschlüsse (1-Close-Variante für CONFIRMED, G1–G5 arretiert)

| ID | Thema | Beschluss |
|---|---|---|
| G1 | 1-Close-Einstieg | Einstieg = `open[j+1]` direkt nach dem **ersten** Durchbruchs-Close jenseits `h_ref + TOL` bzw. `l_ref − TOL` (Bruchkerze `j`). Spart genau eine M15-Kerze Spread/Preisexkursion gegenüber dem 2-Close-Einstieg `open[b+2]` (b+2 = j+1 der 2-Close-Konvention). Hypothese: Der 2-Close-Filter kauft an b+2 die Erschöpfung (Retail steigt an b+1 ein, während Institutionen Liquidität abziehen). |
| G2 | Kausaler Struktur-Stop | **RAW-analog:** `stop = min(low[j], kante) − 0.15 USD` (Long; SHORT `max(high[j], kante) + 0.15`) — nur die eine Bruchkerze `j`. Einzige kausal zulässige Variante: `low[j+1]` existiert am Entscheidungszeitpunkt `open[j+1]` noch nicht (2-Close-F4-Konstruktion `min(low[b], low[b+1])` wäre Lookahead). |
| G3 | Exit-Konstante | Best-Practice aus D2: `KEIN_TRAILING` (F4 intrabar) + terminaler Zeit-Exit, Horizonte **N = 48 und 96**. N=24 gestrichen (D-Befund: Mittelmaß); **kein Stufen-Trailing** (D2: Performanz-Bremse in 16/18 Zellen). Exit konstant halten, nur Einstieg variieren. |
| G4 | Referenz & Verzerrungs-Kontrolle | **2-Close-CONFIRMED unter identischem Exit als Referenzspalte** (gleiche Population, gleiche Exit-Regel, einzig `entry_idx` um 1 Bar verschoben → Delta kausal dem Timing zuschreibbar). Zusätzlich `sum r_ref` (0,45 %-Basis, unabhängig vom Stop-Schema) und **SL-Delta-Spalte** `sl_delta_ratio = sl_usd_1close / sl_usd_2close` — beweist, ob ein Performanz-Zuwachs aus echtem Timing-Vorteil oder nur aus kleinerem R-Nenner resultiert. |
| G5 | Zweistufige Auswertung (Whipsaw-Bias) | **Stufe 1 (4b-Kern):** reiner A/B-Timing-Vergleich auf der F3-Population (echte 2-Close-Brüche) — beantwortet „Bringt 1 Bar früher bei echten Brüchen einen Vorteil?". **Stufe 2 (Whipsaw-Scan):** NUR falls Stufe 1 in S1 positiv überrascht — Gegenrechnen der 1-Close-Fehlausbrüche (Piercings, die nie eine 2. Bestätigungskerze bekamen → Fakeout/Trap), bevor eine Produktions-Empfehlung auf 1-Close fußt. Ohne Stufe 2 wäre die F3-Stichprobe survivorship-verzerrt (fehlende Whipsaws begünstigen 1-Close). |

**Datenvertrag (freigegeben, wird in `test/tmp_setup_c_1close.py` §1 umgesetzt):** `OneCloseConfig` (frozen, slots): `fenster`, `symbol`, `timeframe`, `zeit_horizonte: tuple[int, ...] = (48, 96)`, `fixed_buffer: float = 0.15`, `sl_pct_ref: float = 0.45`. `EntryTyp = Literal["CONFIRMED_1CLOSE", "CONFIRMED_2CLOSE"]`. `OneCloseResult` (slots): `entry_typ`, `phase`, `dir`, `horizont_bars`, `entry_idx`/`entry_ts`/`entry_preis`, `f4_initial_stop`, `sl_usd`, `exit_idx`/`exit_ts`/`exit_preis`, `exit_grund` (`INITIAL_SL_INTRABAR`/`ZEIT_EXIT_CLOSE`/`RECHTS_ZENSIERT`), `haltezeit_bars`, `r_f4`, `r_ref`, `sl_delta_ratio` (nur 1-Close befüllt). Exit-Semantik und Rechts-Zensierung identisch zu Schritt 4a (E2: Stop-Vorrang an der Exit-Bar, Zensierte strikt isoliert).

### 2.11 Schritt-4b-Stufe-1-Befunde (1-Close vs. 2-Close A/B, 05.09.2026)

Ausführung: `test/tmp_setup_c_1close.py` (gepaarte A/B-Simulation auf der F3-Population; Einstieg 1-Close `open[b+1]` vs. 2-Close `open[b+2]`; identischer Exit F4 intrabar + Zeit-Exit 48/96; Rechts-Zensierung E2; SL-Delta/r_ref-Kontrolle G4). Verifikationsanker **bestanden**: gepaarte Paare deckungsgleich (AUG 11 / S1 138 / S2 61; S2 je Zelle 1 `RECHTS_ZENSIERT` isoliert → 60 gewertet). Reports: `test/tmp_setup_c_1close_{AUG,S1,S2}.txt`. **Kernfrage:** Bringt der 1-Close-Einstieg bei echten 2-Close-Brüchen einen echten Timing-Vorteil?

**H1 — SL-Delta minimal (kein Scheingewinn-Mechanismus):** Der 1-Close-Stop (G2: nur Bruchkerze `j`) ist nur **3–8 % enger** als der 2-Close-Stop: `sl_delta_ratio` median AUG **0,919** / S1 **0,922** / S2 **0,967** (p25 0,77–0,86, p75 1,03–1,08). Ein r_f4-Zuwachs kann also nicht aus systematisch kleinerem R-Nenner stammen — `sum r_ref` (0,45 %-Basis) bleibt die neutrale Währung.

**H2 — S1-Delta massiv (echter Timing-Vorteil):**

| Fenster | N | 1-Close r_f4 (r_ref) | 2-Close r_f4 (r_ref) | Δ r_f4 | Δ r_ref |
|---|---|---|---|---|---|
| S1 | 48 | **+18,22** (+46,95) | −8,56 (+0,50) | +26,78 | **+46,44** |
| S1 | 96 | **+28,31** (+15,61) | −7,32 (−36,47) | +35,64 | **+52,08** |
| S2 | 48 | **+11,93** (+36,32) | +6,94 (+19,48) | +4,99 | +16,84 |
| S2 | 96 | **+16,60** (+52,54) | +13,15 (+38,53) | +3,45 | +14,01 |
| AUG | 48 | **+5,42** (+9,85) | +3,42 (+6,45) | +2,00 | +3,39 |
| AUG | 96 | **+0,65** (−1,92) | −1,80 (−7,46) | +2,46 | +5,55 |

**H3 — 1-Close schlägt 2-Close in 6/6 Zellen (auch r_ref):** Die G1-Hypothese (2-Close kauft an b+2 die Banken-Liquiditätserschöpfung) ist bestätigt — in **allen sechs Zellen** gewinnt 1-Close auf r_f4- **und** r_ref-Basis. Der S1-Einstiegs-Defekt aus C4/D4 (2-Close S1 −8,6R/−7,3R) ist damit **rehabilitiert**: 1-Close dreht S1 auf **+18,2R (N=48)** bzw. **+28,3R (N=96)**. Die positive r_ref-Differenz (bis **+52,08R** in S1 N=96) belegt: Es ist die um eine Bar frühere Exekution, nicht der engere Stop. S2/AUG folgen qualitativ (AUG N=96 bleibt 1-Close schwach positiv bei negativer 2-Close-Referenz −1,80R).

**H4 — G5-Stufe-2-Bedingung ist eingetreten (Whipsaw-Scan wird Pflicht):** Die Vorbedingung aus G5 („S1 positiv überrascht") ist erfüllt. Vor jeder Produktions-Empfehlung auf 1-Close-Basis müssen die **1-Close-Fehlausbrüche** gegengerechnet werden (Piercings, die nie eine 2. Bestätigungskerze bekamen → Fakeout/Trap): Die F3-Stichprobe von Stufe 1 enthält ausschließlich echte Brüche und ist damit survivorship-verzerrt zu Gunsten von 1-Close. Nächster Schritt: `test/tmp_setup_c_whipsaw.py` (Stufe 2) mit **kausaler Kantenreferenz** aus der Baseline-Schleife (`h_ref = max(U_j, birth_h)` / `l_ref = min(L_j, birth_l)`, Z. 715–722 in `test/tmp_phasen_volumen_profil_symbol.py`) — Design-Fragen F1–F3 (Whipsaw-Definition, Abwicklung, Mehrfach-Trigger/Cooldown) sind zu beantworten, dann Code-Entwurf zur Freigabe.

### 2.12 Schritt-4b-Stufe-2-Befunde (Whipsaw-Scan & Netto, 05.09.2026)

Ausführung: `test/tmp_setup_c_whipsaw.py` (F1-Negativ-Spiegel `close[j+1] ≤ kante(j)+TOL` gegen dieselbe kausal rekonstruierte Kante aus `U_hist`/`L_hist`; Sub-Typen `RETRACE`/`TOL_BAND`; F2 volle Simulation `KEIN_TRAILING` 48/96 mit G2-Stop und E2-Zensierung — kein pauschales −1R; F3 phasenlokale Open-Position-Suppression + Sensitivitätslauf „ohne Suppression"; Scope = F3-Bruchphasen der Stufe-1-Population, Bruchrichtung). Verifikationsanker **bitgenau bestanden** (AUG 11 == 11, S1 138 == 138, S2 61 == 61, jeweils `[OK]`); Stufe-1-Referenzblöcke identisch zum 4b-Stufe-1-Report (Drift-Nachweis über den gemeinsamen `oneclose`-Codepfad). Reports: `test/tmp_setup_c_whipsaw_{AUG,S1,S2}.txt`. **Kernfrage:** Überlebt der 1-Close-Vorteil aus Stufe 1 (H3) die Gegenrechnung der Fehlausbrüche?

**Vergleichstabelle NETTO (sum r_f4 | sum r_ref; akzeptierte Whipsaws nach F3-Suppression):**

| Fenster | N | Stufe-1 1-Close | Whipsaw | **NETTO 1-Close** | 2-Close-Referenz | ohne Suppression (NETTO) |
|---|---|---|---|---|---|---|
| S1 | 48 | +18,22 (+46,95) | −16,40 (−40,93) | **+1,83 (+6,01)** | −8,56 (+0,50) | −20,08 (−38,01) |
| S1 | 96 | +28,31 (+15,61) | −8,98 (−26,36) | **+19,33 (−10,75)** | −7,32 (−36,47) | +4,75 (−40,40) |
| S2 | 48 | +11,93 (+36,32) | +2,10 (+7,87) | **+14,03 (+44,19)** | +6,94 (+19,48) | +17,52 (+57,93) |
| S2 | 96 | +16,60 (+52,54) | +4,12 (+11,93) | **+20,72 (+64,47)** | +13,15 (+38,53) | +22,78 (+75,40) |
| AUG | 48 | +5,42 (+9,85) | −3,00 (−5,66) | **+2,42 (+4,19)** | +3,42 (+6,45) | +2,42 (+4,19) |
| AUG | 96 | +0,65 (−1,92) | −3,00 (−5,66) | **−2,35 (−7,58)** | −1,80 (−7,46) | −2,35 (−7,58) |

**W1 — Verifikationsanker bitgenau:** Der Phasenmengen-Filter greift exakt: gescannte F3-Phasen == Stufe-1-Paare (AUG 11 / S1 138 / S2 61, `[OK]`). Whipsaw-Kandidaten (Roh): AUG 3, S1 79, S2 105. Nach F3-Suppression akzeptiert: AUG 3 (0 supprimiert), S1 **53** (26 supprimiert), S2 42 @48 / 36 @96 (63/69 supprimiert). AUG-Whipsaws enden alle sofort am Stop (Haltedauer 14 Bars, 0 ZEIT_EXIT) → identisch über beide Horizonte.

**W2 — Kanten-Erosion: Der Markt frisst 90 % des Stufe-1-Vorteils:** In S1 (Shakeout-Regime 2026) bleiben von **+18,22R (N=48)** nach Gegenrechnung der 53 akzeptierten Whipsaws nur **+1,83R Netto** (r_ref +6,01) — die Fehlausbrüche (−16,40R) zehren 90 % der Brutto-Kante auf. Bei **N=96** bleibt das r_f4-Netto +19,33R komfortabel, **aber** das r_ref-Netto kippt auf **−10,75** — auf neutraler 0,45 %-Dollar-Basis (F4-Stop ≈ 2,8× Referenz, B2) überlebt die Kante bei N=96 nicht. **Ohne phasenlokale Suppression stürzt S1 komplett ab:** N48 **−20,08R** (r_ref −38,01), N96 +4,75R (r_ref −40,40). Die F3-Suppression (26/79 = 33 % supprimiert) ist kein Schönheitsfilter, sondern **überlebensnotwendig** — unkontrolliertes Nachkaufen von Intrabar-Spikes an derselben Range-Kante ist Kontenruin.

**W3 — TOL_BAND-Forensik (49/53):** In S1 sind 49 der 53 akzeptierten Whipsaws **TOL_BAND** (Folge-Close bleibt *oberhalb* der Kante, verfehlt nur die TOL-Schwelle von 0,34 USD an j+1), nur 4 RETRACE. Mechanik: Der Markt sticht kurz über die Kante, um Ausbruchs-Buy-Stops abzugrasen; die Liquidität reicht nicht für einen Trend, der Move stagniert direkt an der Kante. Die TOL_BAND-Whipsaws erzeugen die Hauptverluste (N48: −12,40R von −16,40R). Der 2-Close-Filter (Stufe-1-Referenz) rettet hier **53× das Konto** vor teuren Fehlsignalen — die reale Versicherungsfunktion des 2-Close-Filters im Shakeout-Regime.

**W4 — S2-Trend-Robustheit (F2 empirisch bestätigt):** In S2 (Trend 2025) sind die Whipsaws **positiv** (+2,10R N48 / +4,12R N96; sogar ohne Suppression +5,59/+6,18R): Kurzfristige Fehlausbrüche werden im echten Trend sofort absorbiert und laufen in Trendrichtung weiter (Haltedauer 41/71 Bars, WR 40–44 %). Ein pauschaler −1R-Abzug hätte S2 um −42/−36R verstümmelt. Netto S2: **+14,03R (N48) / +20,72R (N96)** — 1-Close ist im Trend-Regime klar überlegen.

**Implikation für Schritt 4 (Prüfbericht):**
1. **Keine pauschale 1-Close-Produktions-Empfehlung:** Der 2-Close-Filter hat im Shakeout-Regime eine reale Versicherungsfunktion (vermeidet 53–79 Fehlsignale), kostet aber im Trend-Regime die frühe Exekution.
2. **Regime-Klassifikation (EMA-Slope, §2.1) wird der zentrale Produktions-Schalter:** Trend-Regime → 1-Close (S2-artig, Netto bis +20,7R); Shakeout-Regime → 2-Close bzw. RAW-Cluster-A (S1-artig). D-Implikation 5 jetzt mit Whipsaw-korrigierter Evidenz hinterlegt.
3. **Phasenlokale Open-Position-Suppression ist Pflicht-Bestandteil** jeder 1-Close-Umsetzung (S1 ohne Suppression: −20,1R).
4. **TOL_BAND-Dominanz als Regime-Indikator:** Ein hoher TOL_BAND-Anteil an Fehlausbrüchen (49/53) misst Stop-Räumung/fehlende Trend-Liquidität an der Kante.

### 2.13 Schritt-4-Prüfbericht & Entscheidungsvorlage (Produktions-Blueprint `setup_c_profil.py`, 05.09.2026)

**Gesamturteil:** Setup C ist als eigenständiges Modul `scripts/setup_c_profil.py` produktionsreif — **in einer abgespeckten Phase-1-Architektur ohne Regime-Schalter**. Die Evidenzkette (B1–B4, C1–C5, D1–D5, H1–H4, W1–W4) erlaubt eine vollständige, arretierbare Blueprint mit vier tragenden Säulen. Der Regime-Schalter wird als **Validierungs-Rückstellung (Stufe 5 / Pre-Production-Gate)** deklariert, nicht als arretierte Komponente.

**A. Die vier tragenden Säulen der Produktions-Blueprint**

| Säule | Entscheidung | Evidenz | Status |
|---|---|---|---|
| **1. Einstiegs-Matrix** | Primär **RAW-Cluster A** (Vorlauf ≤ 1, kausale Kante aus `U_hist`/`L_hist`, Volumen `shift(1)`); **RAW-Cluster B** zurückgestellt; **RETEST** optional; **1-Close** und **2-Close-CONFIRMED** nicht in Phase 1 | D3 (Ratchet-bereinigt 05.09.2026, §2.13-D): RAW-A S1 **+22,81R @48** (38 T, mean 0,60R, WR 50 %, PF 2,34, r_ref +71,77), N96 +27,87R; S2 +0,31/+0,98 (n=3, nie stark negativ); AUG n=2 (+3,64/−0,87); D4/C4: 2-Close S1 strukturell negativ; W2: 1-Close-Netto nur mit Suppression | arretiert (Phase 1) |
| **2. Stop-/Exit-Architektur** | **F4-Struktur-Stop intrabar** (`min(Struktur, Kante) − 0.15`) + **terminaler Zeit-Exit** N=48 (S1/AUG) bzw. N=96 (S2); **kein Stufen-Trailing**; `RECHTS_ZENSIERT` strikt isoliert | B1: F4 eliminiert 55 % Früh-Shakeout; D2: F4+Zeit-Exit schlägt Ratsche in **16/18 Zellen** (Trailing kostet bis 38R); D1: 274R-Phantom geplatzt; E2 | arretiert |
| **3. Risikoschutz** | **Phasenlokale Open-Position-Suppression** (obligatorisch); F4-Stop begrenzt Verlierer auf −1R | W2: ohne Suppression S1 N48 **−20,08R** (Kontenruin durch Adjazenz-Pyramidisierung) | arretiert (Pflicht) |
| **4. Validierungs-Gates** | Regime-Klassifikation = **Stufe-5-Arbeitspaket**, nicht Phase 1; Schwellenwert nicht vorschnell arretieren | D3/W4: S1-vs-S2-Kontrast extrem (RAW-B S1 +36R vs. S2 −12R; Whipsaws S1 −16R vs. S2 +4R) — aber nur 2 Fenster-Jahre | **Validierungs-Rückstellung** |

**B. Einstiegs-Matrix im Detail (Phase-1-Entscheidungen)**

| Arm / Variante | Phase 1 | Begründung (Evidenz) |
|---|---|---|
| **RAW Cluster A** (Vorlauf ≤ 1) | **PRODUKTION** | Der „Fels": D3 (Ratchet-bereinigt 05.09.2026, §2.13-D) S1 +22,81R @48 / +27,87R @96 (n=38), mean 0,60–0,73R, WR 40–50 % über die Horizonte; S2 +0,31/+0,98 (n=3), AUG +3,64/−0,87 (n=2) — Niedrigfrequenz, nie stark negativ. Frische Ausbrüche ≤ 1 Bar vor dem 2-Close-Bruch = dichtester legitimer Einstieg (B4). |
| RAW Cluster B (Vorlauf > 1) | **zurückgestellt** | Regime-toxisch S2 (−12,10/−12,49R @48/96 = der eigentliche S2-Verlierer), aber S1-Größtgewinner (+36R @96). Nur mit Regime-Filter (Stufe 5) bespielbar. |
| 1-Close-CONFIRMED | **zurückgestellt** | W2: S1-Netto N48 +1,83R (90 % Erosion), N96 r_ref −10,75; nur mit Pflicht-Suppression. Im Trend-Regime stark (S2 Netto +14,0/+20,7R) → **Stufe-5-Kandidat für den Trend-Zweig**. |
| 2-Close-CONFIRMED | **verworfen** | C4/D4: S1 unter jeder Exit-Architektur negativ (−7,3 bis −9,3R KT); kauft an b+2 die Erschöpfung. Als Negativ-Kontrolle dokumentiert. |
| RETEST_OUTSIDE | **optional** | D5: S1 +5,18R (nur N48), S2 +6,79/+6,09, AUG +5,78/+5,07 — positiv aber selektiv (n klein: AUG 3/S1 59/S2 18); Zeit-Exit als Cap schadet nicht. Qualitäts-Arm für zweite Ausbaustufe. |

**C. Was geht in Produktion, was wird verworfen, was muss validiert werden**

**→ In Produktion (Phase 1, ohne Regime-Schalter):**
1. **RAW-Cluster-A-Einstieg** (Vorlauf ≤ 1, kausale Kantenreferenz D4, F5-Volumen `shift(1)`).
2. **F4-Struktur-Stop intrabar** (Puffer 0,15 USD) — verlustbegrenzend auf −1R.
3. **Terminaler Zeit-Exit** N=48 (S1/AUG-Betrieb) / N=96 (Trend-Betrieb) mit **Rechts-Zensierung E2** (strikt isoliert, r=NaN).
4. **Phasenlokale Open-Position-Suppression** als Pflicht-Schutzschicht.
5. **0,45 %-SL nur als Mess-Referenz** (r_ref-Spalte), nie als Produktions-Stop.

**→ Verworfen (mit Evidenz begründet):**
- **Stufen-Trailing-Ratsche (F9–F11/VAR_A/VAR_B):** D2 — Performanz-Bremse in 16/18 Zellen; kostet in S1 bis 38R.
- **2-Close-CONFIRMED:** C4/D4 — S1 strukturell defizitär (Einstiegs-Timing).
- **1-Close ohne Suppression:** W2 — S1 N48 −20,08R.
- **Offener `DATEN_ENDE`-Exit:** C1/D1 — 274R-Phantom (verstecktes Buy-and-Hold).
- **Trailing-Exit intrabar:** C5 — S1-Gift (−12,77R).
- **Zeit-Exit N=24:** D-Befund — überall Mittelmaß, kappt nachlaufende Energie.
- **Pauschaler −1R-Whipsaw-Abzug:** W4 — verstümmelt S2 (−42/−36R), ignoriert echte Überlebens-/Partizipationsfälle.

**→ Zu validieren (Stufe 5 / Pre-Production-Gate, eigenständiges Arbeitspaket):**
1. **Regime-Klassifikation als Produktions-Schalter:** Notwendigkeit durch D3/W4 belegt (S1-Shakeout vs. S2-Trend). Konkrete Implementierung (**EMA20-Slope vs. ADX vs. Phasen-Volatilität**) und Schwellenwert-Kalibrierung **out-of-sample** — `ema_slope_threshold = 0.001` aus §2.1 ist eine Hypothese, kein kalibrierter Filter (Overfitting-Risiko auf 2 Fenster-Jahre). Ziel: Trend-Regime → 1-Close/RAW-B-Zweig; Shakeout-Regime → RAW-A/2-Close-Schutz.
2. **Parameter-Robustheit:** Zeit-Exit-Übergang 48↔96, TOL=0,34, Puffer=0,15 — Sensitivitätsgitter auf frischen Daten.
3. **Out-of-Sample-Validierung:** neues Datenfenster nach 2026-08-28 (Papier-/Forward-Test) vor Live-Schaltung.

**D. Konsolidierte Referenzzahlen der Phase-1-Basislinie** (RAW-Cluster A, KT + Zeit-Exit, F4-R-Basis; **nach Einheiten-Bereinigung D4-Ratchet µs/ns, 05.09.2026** — zuvor lief der searchsorted-Vergleich in `_kanten_reihe` durch den `datetime64[us]`-vs-`ns`-Mismatch auf −1 = statische Kante statt zeitlich gültiger Ratchet)

| Fenster | N=48 sum r_f4 (r_ref) | N=96 sum r_f4 (r_ref) | n | mean/WR/PF @48 |
|---|---|---|---|---|
| S1 | **+22,81** (+71,77) | **+27,87** | 38 | 0,60R / 50 % / 2,34 |
| S2 | +0,31 (+1,50) | +0,98 (+3,56) | 3 (1 zens.) | Niedrigfrequenz, nie stark negativ |
| AUG | +3,64 (+8,59) | −0,87 (−1,86) | 2 | Niedrigfrequenz (N96: Shakeout-/Whipsaw-Risiko langer Haltezeiten im Sommer-Rauschen) |

**Zum Vergleich (GESAMT aller Arme, KT):** AUG N48 +14,57R, S1 N48 +49,25R, S2 N48 +2,02R / N96 +8,67R (D1-Tabelle) — die Gesamt-Summe ist durch RAW-B (S1) bzw. die Arm-Mischung getragen; Phase-1-Kern bleibt konservativ RAW-A.

**E. Formale Übergabe**

§2.13 schließt die **Explorations- und Prüfphase Setup C** ab. Damit ist die Entscheidungsvorlage für die Entwicklungsphase `scripts/setup_c_profil.py` vollständig: Phase-1-Kern (RAW-A + F4 + Zeit-Exit 48/96 + Suppression) als arretierte Architektur, Regime-Schalter als nachgelagertes Stufe-5-Arbeitspaket. Die Produktions-Baseline `scripts/phasen_volumen_profil.py` bleibt unverändert (+297,14R, v0.4.0-frozen).

### 2.14 Entwicklungs-Schritt 1: Acceptance-Gates L1/L2 & Architektur-Beschlüsse (05.09.2026)

**A. Zweistufiges Acceptance-Gate (verbindlich für die Entwicklungsphase)**

Die Verifikation des Shared-Utility `scripts/market_segmentation.py` und des Profil-Skripts `scripts/setup_c_profil.py` erfolgt ausschließlich gegen die nachfolgend arretierten Soll-Werte. Quelle: Reports `test/tmp_setup_c_zeitexit_{AUG,S1,S2}.txt` (Schritt 4a; Produktions-Exit-Konfiguration `KEIN_TRAILING` = F4 intrabar + terminaler Zeit-Exit, vgl. §2.13-C). Alle Verifikationsanker der Schritte 2–4a wurden bitgenau bestanden.

**Einheiten-Bereinigung D4-Ratchet (µs/ns, 05.09.2026):** Die Soll-Werte wurden nach dem Fix des Einheiten-Vergleichs in `_kanten_reihe` (`scripts/setup_c_profil.py`) **neu arretiert** — zuvor lief `searchsorted` durch den Mismatch `datetime64[us]` (Ziel-Array aus DuckDB) vs. `ns` (`pd.Timestamp.value` der Historie) auf Position −1 (statische Kante = erster hist-Wert statt zeitlich gültiger Ratchet-Stufenfunktion). Neue Quelle: Reports `reports/setup_c/setup_c_{AUG,S1,S2}.txt` (Wiederholungslauf `python -m scripts.setup_c_profil --fenster=ALLE`, 05.09.2026). **L1-Anker F3/CONFIRMED/RETEST sind bitgenau unverändert**; geändert haben sich der RAW-Gesamt-Split (A/B) und sämtliche L2-Kennzahlen (AUG weist erstmals n=2 Cluster-A-Trades statt Vakuum auf).

**L1 – Pipeline-Anker (Struktur/Selektion, zählende Verifikation):** Die Signal-Population des Replays muss die arretierten Zahlen reproduzieren, bevor irgendeine R-Performance gemessen wird.

| Fenster | F3-Brüche | CONFIRMED | RAW gesamt (A / B) | RETEST |
|---|---|---|---|---|
| AUG | 11 | 11 | 10 (2 / 8) | 3 |
| S1 | 138 | 138 | 105 (38 / 67) | 59 |
| S2 | 61 | 61 | 76 (3 / 73) | 18 |

**L2 – RAW-Cluster A (Σr_f4, Σr_ref, Exit-Verteilung, Haltedauer):** Der Produktions-Kern (§2.13: RAW-A Vorlauf ≤ 1, F4 intrabar, Zeit-Exit, ohne Trailing) muss je Horizont die folgenden Kennzahlen reproduzieren.

Horizont N=48 (S1/AUG-Betrieb):

| Fenster | n (zensiert) | Σr_f4 | Σr_ref | Exit F4 / ZEIT | Haltedauer Ø |
|---|---|---|---|---|---|
| S1 | 38 (0) | **+22,81** | **+71,77** | 15 / 23 | 35 |
| AUG | 2 (0) | +3,64 | +8,59 | 0 / 2 | 48 |
| S2 | 3 (1) | +0,31 | +1,50 | 1 / 1 | 32 |

Horizont N=96 (Trend-Betrieb):

| Fenster | n (zensiert) | Σr_f4 | Σr_ref | Exit F4 / ZEIT | Haltedauer Ø |
|---|---|---|---|---|---|
| S1 | 38 (0) | **+27,87** | **+55,17** | 20 / 18 | 60 |
| AUG | 2 (0) | −0,87 | −1,86 | 1 / 1 | 89 |
| S2 | 3 (1) | +0,98 | +3,56 | 1 / 1 | 56 |

**Toleranz:** Ziel **bitgenau**; harte Fail-Obergrenze **±0,05R** je Σr-Spalte (Σr_f4 und Σr_ref). Zensierte Positionen (`RECHTS_ZENSIERT`, §2.8/E2) bleiben strikt isoliert (r=NaN) und zählen weder in n noch in Σr – identisch zur Schritt-4a-Referenz.

**B. Architektur-Beschlüsse Entwicklungsphase (arretiert)**

1. **Shared-Utility `scripts/market_segmentation.py` (Domain-Name, keine Setup-C-Spezifik):** Die Baseline `scripts/phasen_volumen_profil.py` ist **nicht importierbar** – kein `__main__`-Guard, 2.432 Zeilen (ein Import liefe die gesamte Datei durch). Sie ist funktionsbasiert zerlegbar: `load_data` (Z. 320), `find_pivots` (Z. 343), Dataclasses `PhaseData`/`MoveData` (Z. 97–170). ⇒ **Mechanische Extraktion** der linearen Phasen-Hauptschleife in `def`-Wrapper; Konstanten als frozen `SegmentConfig`; **kein `exec()` in Produktion**.
2. **Profil-Skript `scripts/setup_c_profil.py`:** Implementiert den arretierten Phase-1-Kern (§2.13-C): RAW-Cluster A (Vorlauf ≤ 1) + F4-Stop intrabar (Puffer 0,15 USD) + terminaler Zeit-Exit 48/96 + phasenlokale Open-Position-Suppression; 0,45 %-SL ausschließlich als r_ref-Messung (nie Produktions-Stop).
3. **Ausgabeordner `reports/setup_c/`:** Konfigurierbarer Default in der jeweiligen Config. Phase 1 = **Text-Export only** (Console + `.txt` + maschinenlesbarer Trade-Block); Charts nachgelagert.

### 2.15 Entwicklungs-Schritt 4: Phase-1-Abnahmeprotokoll L1/L2 (Gate bitgenau bestanden; Re-Arretierung nach Einheiten-Bereinigung D4-Ratchet, 05.09.2026)

**A. Ausführung**

Formaler Validierungslauf des Produktionskerns nach statischer Freigabe des finalen Quelltexts (keine Ausführung während der Entwurfs-/Review-Phase):

```
python -m scripts.setup_c_profil --fenster=ALLE
```

Pipeline: `load_data` (DuckDB `read_only`) → `segmentiere_markt` (`scripts/market_segmentation.py`, Shared-Utility) → Signal-Erfassung RAW-A (`_erfasse_raw`, D4-kausal: nur `U_hist`/`L_hist`, Scan ab erstem hist-Eintrag, kein Kreuz-Fallback) → Simulationskern F4 intrabar + terminaler Zeit-Exit 48/96 (`_simuliere_kern`, E1/E2, Stop-Vorrang) → phasenlokale F3-Suppression Key `(phase, dir)` → Aggregation (`_agg_block`, E2: Zensierte strikt isoliert) → Text-/TSV-Export `reports/setup_c/`.

**Anlass der Re-Arretierung (Einheiten-Bereinigung D4-Ratchet, µs/ns):** Diagnose `test/tmp_diag_kanten_delta.txt` wies nach, dass `_kanten_reihe` Ziel-Zeitstempel aus `df["ts"].values` (`datetime64[us]`) unnormalisiert gegen die ns-basierte `pd.Timestamp.value`-Historie verglich → `searchsorted` lieferte durchgehend −1 → die Kante fror auf dem ersten hist-Wert ein (statische Kante) statt als zeitlich gültige Ratchet-Stufenfunktion zu laufen. Nach dem Fix (beidseitige ns-Normalisierung in `_kanten_reihe`) wurde der formale Wiederholungslauf ausgeführt:

```
python -m scripts.setup_c_profil --fenster=ALLE
```

Ergebnis: L1-F3/CONFIRMED/RETEST **bitgenau invariant**; RAW-Gesamt/A-B-Split und L2-Kennzahlen re-arretiert (AUG weist mit n=2 erstmals Cluster-A-Trades statt des bisher dokumentierten Vakuums auf — Niedrigfrequenz analog S2 n=3, keine Gate-Mapping-Verbiegung).

**B. L1-Pipeline-Anker — Soll vs. Ist (bitgenau)**

| Fenster | F3-Brüche Soll / Ist | CONFIRMED Soll / Ist | RAW gesamt (A/B) Soll / Ist | RETEST Soll / Ist | Ergebnis |
|---|---|---|---|---|---|
| AUG | 11 / 11 | 11 / 11 | 10 (2/8) / 10 (2/8) | 3 / 3 | ✅ bitgenau |
| S1 | 138 / 138 | 138 / 138 | 105 (38/67) / 105 (38/67) | 59 / 59 | ✅ bitgenau |
| S2 | 61 / 61 | 61 / 61 | 76 (3/73) / 76 (3/73) | 18 / 18 | ✅ bitgenau |

**C. L2 RAW-Cluster A — Soll vs. Ist (Null-Delta, ±0,05R-Toleranz eingehalten)**

Horizont N=48 (S1/AUG-Betrieb):

| Fenster | n (zensiert) Soll / Ist | Σr_f4 Soll / Ist | Σr_ref Soll / Ist | Exit F4/ZEIT Soll / Ist | HD Ø Soll / Ist | Δ |
|---|---|---|---|---|---|---|
| S1 | 38 (0) / 38 (0) | **+22,81** / **+22,81** | **+71,77** / **+71,77** | 15/23 / 15/23 | 35 / 35 | 0,00R |
| AUG | 2 (0) / 2 (0) | +3,64 / +3,64 | +8,59 / +8,59 | 0/2 / 0/2 | 48 / 48 | 0,00R |
| S2 | 3 (1) / 3 (1) | +0,31 / +0,31 | +1,50 / +1,50 | 1/1 / 1/1 | 32 / 32 | 0,00R |

Horizont N=96 (Trend-Betrieb):

| Fenster | n (zensiert) Soll / Ist | Σr_f4 Soll / Ist | Σr_ref Soll / Ist | Exit F4/ZEIT Soll / Ist | HD Ø Soll / Ist | Δ |
|---|---|---|---|---|---|---|
| S1 | 38 (0) / 38 (0) | **+27,87** / **+27,87** | **+55,17** / **+55,17** | 20/18 / 20/18 | 60 / 60 | 0,00R |
| AUG | 2 (0) / 2 (0) | −0,87 / −0,87 | −1,86 / −1,86 | 1/1 / 1/1 | 89 / 89 | 0,00R |
| S2 | 3 (1) / 3 (1) | +0,98 / +0,98 | +3,56 / +3,56 | 1/1 / 1/1 | 56 / 56 | 0,00R |

Zensierte Positionen (`RECHTS_ZENSIERT`, S2 je Horizont 1) strikt isoliert (r=NaN), zählen weder in n_gewertet noch in Σr — identisch zur Schritt-4a-Referenz (§2.8/E2). Harte Fail-Obergrenze **±0,05R** je Σr-Spalte: **Null-Delta unterschreitet die Toleranz.** AUG (n=2, 0 zensiert) ist unter der korrigierten Ratchet kein Vakuum mehr; die Niedrigfrequenz-Lage (analog S2 n=3) wird dokumentiert, das Gate-Mapping bleibt unverbogen.

**D. Suppression-Nachweis (F3, Key `(phase, dir)`)**

`n_supprimiert = 0` in allen Fenstern/Horizonten (AUG/S1/S2, N=48/N=96). Da `_erfasse_raw` je (Phase, Richtung) maximal EIN Signal liefert, ist die phasenlokale Suppression für die RAW-A-Population ein **striktes No-op** — kein Cross-Richtungs-Eingriff (up/down derselben Phase bleiben unabhängig handelbar). Produktions-Default (`suppression_phasenlokal=True`) und L2-Referenzzeile (`False`, §2.14-Sollwerte) sind in jedem Block **wertidentisch** (Σr_f4, Σr_ref, Exit-Verteilung, HD Ø) — die Produktion setzt bitgenau auf den arretierten Soll-Werten auf.

**E. Artefakte, Commits & Baseline**

- Reports (generiert, bewusst **nicht versioniert** — deterministisch reproduzierbar): `reports/setup_c/setup_c_{AUG,S1,S2}.txt` + `setup_c_trades_{AUG,S1,S2}.tsv`
- Commits (3, atomar, Reihenfolge): ① `feat` `scripts/market_segmentation.py` (Shared-Utility), ② `feat` `scripts/setup_c_profil.py` (Phase-1-Kern), ③ `docs` §2.15/§3/§4 (Gate-Abschluss)
- **Nachbereinigung 05.09.2026 (Einheiten-Bereinigung D4-Ratchet, µs/ns):** atomarer Fix-Commit `scripts/setup_c_profil.py` (ns-Normalisierung in `_kanten_reihe` + Text-Anker/Docstring) + `docs/setup_c_experiment.md` (§2.13-D/§2.14/§2.15/Header/§3/§4) — Reports `reports/setup_c/setup_c_{AUG,S1,S2}.txt/.tsv` erneut überschrieben (unversioniert, deterministisch).
- Produktions-Baseline `scripts/phasen_volumen_profil.py` (+297,14R, v0.4.0-frozen): **unverändert**
- Stufe-5-Roadmap (Regime-Klassifikation, Parameter-Robustheit, OOS-Validierung, §2.13-C): eigenständige Folge-Session

### 2.16 Stufe 5: Regime-Klassifikation & Out-of-Sample-Validierung (In-Sample-Kalibrierung abgeschlossen; Freeze versiegelt; OOS-Zonen 2024 & ZSTRESS abgenommen — Stufe 5 ABGESCHLOSSEN, 05.09.2026)

**Status:** In-Sample-Kalibrierung abgeschlossen (V2-Bereinigung auf 4 responsive
Parameter), **Schwellen-Freeze versiegelt** am 05.09.2026
(`test/regime_schwellen_freezed.json`, sha256 der S1/S2-Roh-Zustaende). **Beide
OOS-Zonen per One-Shot ausgewertet und abgenommen — Stufe 5 ABGESCHLOSSEN
(05.09.2026, §2.16-F):** Zone 2024 (Fassung-1-Formalbefund a=True b=False c=True →
„NICHT BESTANDEN"; Mentor-Abnahme wegen +11,10R Netto-Alpha, §2.16-F.2/F.3) und Zone
ZSTRESS (Fassung 2: a=True b'=True c=True → BESTANDEN, +7,24R Netto-Alpha,
§2.16-F.6). **Kriterien-Fassung 2 (ΣΔ_TREND ≥ 0,0R je Zone statt Positivität jedes
Einzelabschnitts) ist für ZSTRESS und alle künftigen Forward-OOS-Läufe arretiert**
(§2.16-F.4); die Fassung-1-Kriterien bleiben für den Zone-2024-Befund maßgeblich
(duale Ausweisung). **Stufe-5-Abschluss: `scripts/regime_filter.py` als `feat`-Commit,
dieses Dokument als `docs`-Commit (§2.16-F.6)**; der Phase-1-Kern
`scripts/setup_c_profil.py` (Commit `29e7d03`, nach D4-Ratchet-Re-Arretierung §2.14/
§2.15) und die Produktions-Baseline `scripts/phasen_volumen_profil.py` (+297,14R,
v0.4.0-frozen) bleiben unverändert. Verbleibend: ausschließlich der Forward-OOS-
Meilenstein nach dem SILVER-Daten-Update (§2.16-B) als einmaliger Blind-Test unter
Fassung 2.

#### A. Architektur-Doktrin & Anti-Kontaminations-Regeln

1. **Plateau-Doktrin (kein Curve-Fitting):** Schwellenwerte werden NICHT als isolierte Punkt-Optima
   kalibriert. Jede Schwelle wird über eine definierte Sweep-Spanne als Response-Kurve ausgewertet;
   robust ist ausschließlich ein breites Plateau stabiler Ergebnisse. Kippt die Performance bei einer
   Parametervariation von ±10–20 % von profitabel auf ruinös (steile Klippe), gilt der Kandidat als
   verworfen — unabhängig von der Höhe des Punkt-Optimums.
2. **One-Shot-Holdout-Regel:** Jede OOS-Zone wird exakt EINMAL ausgewertet. Wird eine Zone zur
   Nachkalibrierung herangezogen, verliert sie ihren OOS-Status unwiderruflich und muss durch eine
   weitere, unberührte Zone ersetzt werden (sonst verdecktes In-Sample-Tuning).
3. **Drei-Schichten-Architektur:** (1) **Zustands-Schätzer** mit Struktur-/Volatilitätsmetriken
   (Option B, primär) + Preis-Momentum-Benchmark (Option A, vergleichend); (2) **Entscheidungs-Gate**
   (Option C) mit Hysterese/Totzone; (3) **Validierung** gegen die OOS-Zonen. Keine Vermischung der
   Schichten.
4. **Modul-Isolation:** Sämtliche Klassifikations- und Gate-Logik wird ausschließlich im separaten
   Modul `scripts/regime_filter.py` implementiert. `scripts/setup_c_profil.py` bleibt byte-identisch
   unberührt; Integration erst nach bestandenem Gate-Test als optionaler Parameter (Default `None` =
   identischer Phase-1-Pfad).
5. **Kausalität:** Alle Regime-Metriken werden je Phase ausschließlich aus Daten bis zum
   Phasen-Ende/`brk_idx` berechnet (kein Lookahead über die Phasengrenze hinaus) — analog zur
   D4-Kantenreferenz der Signal-Erfassung.
6. **Daten-Grenze:** Daten vor 2017-03 sind wegen unzureichender M15-Liquiditätsdichte
   (18–25 Bars/Monat, Scan-Beleg 05.09.2026) formal von der Mikrostruktur-/Regime-Analyse
   ausgeschlossen. Erst ab 2017-03 liegt kontinuierliche M15-Dichte vor (~1.750–2.120 Bars/Monat).

#### B. OOS-Zonen (bereinigt, Ende-exklusiv gemäß `load_data`-Konvention)

| Zone | Zeitraum | Status | Reinheit / Befund |
|---|---|---|---|
| In-Sample-Referenz | S1: 2026-02-05 .. 2026-08-28; S2: 2025-01-01 .. 2025-12-01 | arretiert (Phase-1-Gate §2.15) | Kalibrierungs-Basis der Phase-1-Populationen |
| **Historischer Makro-Holdout** | **2024-01-01 .. 2024-12-31** | **abgenommen (05.09.2026, §2.16-F)** | **Clean-Befund 05.09.2026:** Volle M15-Dichte (1.831–2.119 Bars/Monat); Volltext-Prüfung über `docs/`, `test/`, SESSION-Dateien ergab **keine** Strategie-/Tuning-Berührung 2024-01..11. Einzige Ausnahme: 2024-12-Warmup-Zeile im Monats-Regime-Kontrast (nur Tages-Indikatoren für S2-Start, 0 Trades) — für den Ganzjahres-Holdout irrelevant. SILVER_LONG-Stresstest (QS-8.1) lief 2025-02-05..2026-08-29, nicht über 2024. **One-Shot-Ergebnis 05.09.2026:** Gated +9,05R vs. B48 −2,05R (Primär-Delta +11,10R; B96 −2,62R; 41 Phasen: 21 TREND / 20 SHAKEOUT / 0 UNKLAR); Formalbefund a=True b=False c=True (4/10 TREND-Blöcke verletzt); **per Mentor-Abnahme akzeptiert** (Trendfolge-Varianz in 1–2-Trade-Abschnitten; keine Nachkalibrierung, §2.16-F). |
| Stress-Holdout | 2025-12-01 .. 2026-02-05 | **abgenommen (05.09.2026, §2.16-F.6)** | Unberührter Stress (Squeeze/Flash-Crash, winterlich dünn; lückenlos an S1-Start anschließend, Ende-exklusiv). **One-Shot-Ergebnis 05.09.2026:** 53 Phasen: 28 TREND / 18 SHAKEOUT / 7 UNKLAR (UNKLAR griff 7× in der Jahreswechsel-Liquidität — qualitativer Schalter bestätigt); Gated +3,34R vs. B48 −3,90R (Primär-Delta +7,24R; B96 −5,00R); Fassung 2: a=True b'=True c=True → **BESTANDEN** (tiefster Block −2,00R); Zonen-Hash `187fdb99…` (§2.16-F.6). |
| Forward-OOS | nach 2026-08-28 | **Meilenstein nach SILVER-Daten-Update** | Scan-Beleg 05.09.2026: `max(ts)=2026-08-28 22:45`, **0 Bars** im Sept. 2026 für SILVER M15. Keine Auswertung auf leerem Fenster. Erst nach DB-Refresh (SILVER ≥ 04.09.2026) als einmaliger Blind-Test scharf. |

#### C. Typisierte Datenverträge (Implementierungsstand `scripts/regime_filter.py`; Schwellen VERSIEGELT)

**V2-Bereinigung (Mentor-Beschluss, Occam's Razor nach 1D-Response):** `spread_atr`
und `konsolidierung_bars` sind ersatzlos aus dem Trend-Score entfernt (tote Schwellen,
Sättigungsbereich ~95 %, Sweep-Spanne < 1,0R in beiden Fenstern). Kalibrierbar sind
exakt 4 Schwellen; die Roh-Metriken bleiben im `RegimeState` erhalten (NaN-Doktrin
bzw. Kaltstart-Grenze), nur ihre Schwellen-Scores entfallen. **Freeze 05.09.2026:**
Die 4 Plateau-Zentren sind in `test/regime_schwellen_freezed.json` versiegelt
(sha256-States S1/S2 als forensische Härtung S4; OOS bricht bei Abweichung hart ab).

```python
from dataclasses import dataclass
from typing import Literal, Tuple

RegimeName = Literal["TREND", "SHAKEOUT", "UNKLAR"]
FensterName = Literal["AUG", "S1", "S2"]


@dataclass(frozen=True, slots=True)
class RegimeMetricConfig:
    """Feste mathematische Lookbacks/Perioden der Regime-Messung (B primaer).

    Traegt ausschliesslich Berechnungs-Parameter. Schwellenwerte leben NICHT
    hier, sondern in RegimeSchwellen (versiegelt) / RegimeSweepConfig-Spannen.
    """

    # Struktur-/Volatilitaetsmetriken (Option B - Primaer)
    konsolidierung_min_bars: int = 46  # Untergrenze (deckungsgleich MIN_PHASE_CANDLES)
    tol_band_messfenster_bars: int = 16  # TOLBAND-Quote-Fenster (F7-Semantik)
    atr_periode: int = 14  # ATR-Basis fuer Spread-Normalisierung
    durchstoss_fenster_bars: int = 46  # Dichte-Fenster
    tol: float = 0.34  # 2-Close-Toleranz (muss == SegmentConfig.tol der Segmentierung)

    # Benchmark-Arm (Option A - vergleichend)
    ema_periode: int = 20
    adx_periode: int = 14
    ema_slope_lookback: int = 5  # Slope-Differenz ueber m Bars (m * ATR_k-Norm)


@dataclass(frozen=True, slots=True)
class RegimeSweepConfig:
    """Sweep-Spannen (min, max, step) fuer Response-Kurven (Plateau-Doktrin).

    Stand 05.09.2026 (V2-Bereinigung): Nur die 4 nachweislich responsiven
    Schwellen werden gesweept; spread_atr/konsolidierung_bars sind ersatzlos
    entfernt (keine 1D-Response -> tote Schwellen, Occam's Razor).
    """

    ema_slope: Tuple[float, float, float] = (0.02, 0.12, 0.01)      # TREND-Momentum
    ema_slope_max: Tuple[float, float, float] = (-0.08, 0.02, 0.01)  # SHAKE-Kollaps
    adx_schwelle: Tuple[float, float, float] = (15.0, 35.0, 2.5)    # TREND-Staerke
    tol_band_quote: Tuple[float, float, float] = (0.40, 0.80, 0.05) # SHAKE-Stuetze


@dataclass(frozen=True, slots=True)
class RegimeSchwellen:
    """VERSIEGELTE Schwellen (Freeze 05.09.2026, Plateau-Zentrum, nie Peak).

    Die vier Zentren wurden ueber den In-Sample-Sweep (S1+S2, 1D-Response,
    Plateau-Doktrin §2.16-A.1) kalibriert und kryptografisch versiegelt
    (test/regime_schwellen_freezed.json + sha256 der S1/S2-Roh-Zustaende).
    Ab jetzt unveraenderlich; jeder OOS-Lauf bricht bei Hash-Abweichung hart ab.
    """

    ema_slope_min: float = 0.07     # TREND-Momentum (Plateau n=11, Sequenz [0..10])
    ema_slope_max: float = -0.03    # SHAKE-Kollaps  (Plateau n=11, Sequenz [0..10])
    adx_schwelle_min: float = 25.0  # TREND-Staerke  (Plateau n=9,  Sequenz [0..8])
    tol_band_quote_max: float = 0.60  # SHAKE-Stuetze (Plateau n=9,  Sequenz [0..8])


@dataclass(frozen=True, slots=True)
class RegimeGateConfig:
    """Hysterese- und Fallback-Parameter des Entscheidungs-Gates (Option C)."""

    hysterese_puffer: float = 0.05  # relative Hysterese um Regime-Grenze
    kaltstart_min_bars: int = 46  # unterhalb: immer UNKLAR (Kaltstart)
    fallback_horizont: int = 48  # UNKLAR/Kaltstart -> strikt N=48
    fallback_nur_raw_a: bool = True  # UNKLAR/Kaltstart -> nur RAW-Cluster A


@dataclass(slots=True)
class RegimeState:
    """Vollstaendiger, typisierter Metrik-Vektor einer Phase.

    Kein untypisiertes Auffangbecken (details:str entfaellt ersatzlos). Alle
    Rohwerte werden typisiert gefuehrt, damit Sweeps deterministisch und ohne
    String-Parsing auswertbar sind. regime/konfidenz sind abgeleitete Felder
    mit defensivem Default (UNKLAR = Konto-Verteidigung).

    Kausalitaet: Der Vektor ist zum Zeitpunkt ``brk_idx`` (2-Close-Bruch der
    Phase) vollstaendig feststehend - kein Lookahead ueber die Phasengrenze.
    """

    phase_nr: int  # 1-basiert ueber echte Bruch-Phasen (Join zu setup_c_profil)
    brk_idx: int  # Bar-Index des 2-Close-Bruchs (Zeitanker, kausal)
    phase_spread_usd: float  # U_brk - L_brk (kausal, USD)
    phase_spread_atr_ratio: float  # Spread / ATR (regime-normalisiert)
    durchstoss_dichte: float  # Breakout-Versuche pro Bar im Fenster
    tol_band_quote: float  # TOLBAND-Anteil an Fehlausbruechen (0..1)
    konsolidierung_bars: int  # Konsolidierungsdauer (Bars)

    # Benchmark-Arm (Option A - vergleichend)
    ema_slope: float  # EMA20-Slope (normalisiert)
    adx_val: float  # ADX(adx_periode)

    # Abgeleitete Klassifikation (Default: defensiv)
    regime: RegimeName = "UNKLAR"
    konfidenz: float = 0.0  # 0..1, Abstand zur Regime-Grenze (Hysterese)


@dataclass(slots=True)
class RegimeGate:
    """Aus RegimeState abgeleitete Freigaben (Laufzeit-Objekt, nicht frozen).

    Mapping (arretierte Logik §2.13-C / Stufe-5-Beschluss):
      TREND    -> RAW-Cluster B + 1-Close freigegeben, Ziel-Horizont 96
      SHAKEOUT -> nur RAW-A, Ziel-Horizont 48
      UNKLAR (inkl. Kaltstart) -> strikt N=48 und nur RAW-A (Konto-Verteidigung)
    """

    phase_nr: int  # Join-Schluessel zu RegimeState/setup_c_profil
    regime: RegimeName
    erlaube_raw_cluster_b: bool
    erlaube_one_close: bool
    ziel_horizont: int
```

#### D. Gate-Mapping (defensiv, arretierte Logik)

| RegimeState.regime | erlaube_raw_cluster_b | erlaube_one_close | ziel_horizont | Begründung |
| --- | --- | --- | --- | --- |
| TREND | ✅ | ✅ | 96 | Trend-Regime: offensive Hebel (S2-Evidenz: 1-Close/RAW-B, W4/D3) |
| SHAKEOUT | ❌ | ❌ | 48 | Stop-Räumung: nur Phase-1-Kern RAW-A (S1-Schutz) |
| UNKLAR / Kaltstart | ❌ | ❌ | 48 | Defensiver Fallback: Konto-Verteidigung, kein Experiment |

Kaltstart-Definition: `konsolidierung_bars < RegimeGateConfig.kaltstart_min_bars` (46) oder nicht
ausreichende Historie für ATR/EMA/ADX → `RegimeState` wird mit `regime="UNKLAR"`, `konfidenz=0.0`
erzeugt. Das Gate erzwingt dann strikt `N=48` + RAW-A — identisch zum verifizierten Phase-1-Kern,
reduziert auf den konservativen Horizont.

#### E. Formel-Operationalisierung & Offene Punkte (Stand 05.09.2026)

**Status:** Metrik-Definitionen fixiert und in `scripts/regime_filter.py` implementiert
(Formel-Spezifikation + statische Code-Inspektion 05.09.2026). Alle ursprünglichen
Offenen Punkte sind aufgelöst: Punkt 3 (Klassifikationsregel) V2-bereinigt und mit den
Freeze-Schwellen versiegelt (§2.16-C/E.3), Punkt 4 (Response-Auswertung) abgeschlossen
(E.4). **OOS-Gate abgeschlossen (05.09.2026):** Zone 2024 abgenommen (§2.16-F.2/F.3),
Zone ZSTRESS unter Fassung 2 formell BESTANDEN (§2.16-F.6); Stufe 5 ABGESCHLOSSEN.
Verbleibend: ausschließlich der Forward-OOS-Meilenstein nach SILVER-Daten-Update
(§2.16-B, einmaliger Blind-Test unter Fassung 2).

1. **Metrik-Definitionen (fixiert & verankert):**
   - `phase_spread_usd = U_brk − L_brk` — **strikt kausal** über die D4-Stufenfunktion
     `_kanten_werte` (hist-Einträge ≤ `ts_brk`, Mechanik wie `_kanten_reihe`); **nicht**
     `U_final`/`L_final` (Regel-7-Finalize = Lookahead ersten Grades). Ein-Kanten-Kompression
     oder Spread ≤ 0 → `NaN` → Kaltstart `UNKLAR`.
   - `phase_spread_atr_ratio = phase_spread_usd / ATR₁₄[brk_idx]` (`NaN`, wenn ATR nicht endlich).
   - `durchstoss_dichte` = Kanten-Kontakt-Bars (`high_k ≥ U_k` ∨ `low_k ≤ L_k`, OR je Bar,
     **ohne** Volumen-Bedingung — F5 lebt im Einstiegs-Arm; hier zählt die Adjazenz-/Antast-
     Frequenz) im inklusiven Fenster `[brk_idx−45, brk_idx]`, geteilt durch 46.
   - `tol_band_quote` = Fakeout-Rate im inklusiven Fenster `[brk_idx−15, brk_idx]`; Versuch =
     Kanten-Durchstich; Fakeout = Zwei-Bar-Verdict (Eigen-Close ≤ Kante+TOL oder Eigen-Close >
     Kante+TOL und Folge-Close fällt zurück — gemessen an der Kante von Bar k, `k+1 ≤ brk_idx`
     kausal legal). `brk_idx` zählt als Versuch, nie als Fakeout. Nenner = 0 → Quote = 0.0.
   - `ema_slope = (EMA_k − EMA_{k−m}) / (m × ATR_k)`, `m = ema_slope_lookback = 5` —
     ATR-normalisiert (dimensionslos über SILVER-Preisniveaus).
   - Zusatzfelder `RegimeMetricConfig`: `tol: float = 0.34` (muss == `SegmentConfig.tol`),
     `ema_slope_lookback: int = 5` (§2.16-C synchron).
2. **Indikator-Approximationen (freigegeben 05.09.2026):**
   - ADX-Wilder-Glättung via `ewm(alpha=1/n, adjust=False)` — mathematisch äquivalent zur
     rekursiven Differenzengleichung `R_t = R_{t−1} + (X_t − R_{t−1})/n`; Initialwert-Differenz
     (kein SMA-Seed) nach ~50 Bars asymptotisch null → für Sweeps/Plateaus irrelevant.
   - `konsolidierung_bars = brk_idx − start_idx` (Index-Distanz der Liquiditätsakkumulation;
     Segmentierer erzwingt `≥ min_phase_candles = 46` → Kaltstart-Schutz konsistent).
3. **Klassifikationsregel (V2-Bereinigung 05.09.2026; Schwellen versiegelt):**
   `klassifiziere_regime` implementiert **gewichtete additive Scores** (ersetzt das
   alte min()-Margen-Modell) mit Totzone `±hysterese_puffer`:
   - `t = 0,65·S_oben(ema_slope, ema_slope_min, 0,20) + 0,35·S_oben(adx_val, adx_schwelle_min, 20)`
   - `k = 0,70·S_unten(ema_slope, ema_slope_max, 0,20) + 0,30·S_oben(tol_band_quote, tol_band_quote_max, 0,50)`
   - `s = t − k`; Null-Evidenz (`t ≤ EPS` UND `k ≤ EPS`) → strikt `UNKLAR` (kein
     Vorregime-Latch); Konfliktzone (`|s| < buffer` UND beide Evidenzen aktiv) →
     `UNKLAR` (Konten-Schutz); Totzone-Halten nur bei positiver Eigen-Evidenz des
     Vorregimes. Kaltstart/NaN → strikt `UNKLAR`/`konfidenz=0.0`.
   **Arretiert:** (a) Gate-Mapping `entscheide_gate` (§2.16-D), (b) die 4 Freeze-Schwellen
   (§2.16-C, `test/regime_schwellen_freezed.json`). Die Gewichte (0,65/0,35/0,70/0,30)
   sind fixe Modul-Konstanten (Mentor-Beschluss E-2/V2: kein Gewichte-Sweep).
4. **Response-Kurven-Auswertung (Status: ABGESCHLOSSEN 05.09.2026):** 1D-Response-Sweep
   über S1+S2 (`test/tmp_regime_validation.py --stufe=sweep`). Kriterien: Response ≥ 1,0R
   in mind. einem Fenster (Anti-Totfilter), S1/S2-Delta ≥ −0,5R je Punkt, S2-Trend-Anteil
   > 50 % (Anti-Total-Filter), Sequenz ≥ 3, Klippen-Regel > 30 %, CoV ≤ 0,5, Freeze =
   Plateau-Zentrum (nie Peak). **Ergebnis: 4/4 bestanden** (`ema_slope_min=0.07`,
   `ema_slope_max=−0.03`, `adx_schwelle_min=25.0`, `tol_band_quote_max=0.60`; Plateaus
   n=9–11, Δ ±1–3R); `spread_atr_min`/`konsolidierung_min` als tot eliminiert (V2).
   Sweep-Report: `test/tmp_regime_sweep.txt`; Siegel: `test/regime_schwellen_freezed.json`
   + `test/tmp_regime_freezed.txt` (sha256 S1 `e55b72e6…`, S2 `948a9c21…`).

#### F. OOS-Abnahmeprotokoll Zonen 2024 & ZSTRESS sowie Kriterien-Fassung 2 (arretiert 05.09.2026)

**F.1 Ausführung (One-Shot, Zone Z2024)**

Lauf: `python test/tmp_regime_validation.py --stufe=oos --zone=2024` → Protokoll
`test/tmp_regime_oos_2024.txt`. Siegel-Hashes unverändert (sha256 S1 `e55b72e6…`,
S2 `948a9c21…`; der OOS-Lauf bricht bei Abweichung hart ab), Freeze-Schwellen unberührt
(`ema_slope_min=0.07`, `ema_slope_max=−0.03`, `adx_schwelle_min=25.0`,
`tol_band_quote_max=0.60`). Zonen-Hash `40d91621…` (nur Doku, kein Soll).
Klassifikation der 41 Phasen: **TREND 21 (51 %), SHAKEOUT 20 (49 %), UNKLAR 0**.
Portfolio: TREND = RAW-A@96 (beide Richtungen) + RAW-B@96 (nur Bruchrichtung),
1-Close entfernt (Befund D/W2); SHAKEOUT/UNKLAR = strikt RAW-A@48.
Baselines B48/B96 = RAW-A.

**F.2 Formalbefund (Schicht 1 — Maßstab Fassung 1, unveränderlich)**

| Kennzahl | Wert |
|---|---|
| Gated Σr_f4 | **+9,05R** (n=22, init=13, zeit=9, hd=52, 0 zensiert; Σr_ref +11,65R) |
| B48 (Referenz) | −2,05R (Σr_ref −12,19R) |
| B96 (Sekundär-Baseline) | −2,62R |
| **Primär-Delta (gated − B48)** | **+11,10R** |

Abschnitts-Prüfung (10 TREND-Blöcke, 11 SHAKEOUT-Blöcke, 0 UNKLAR-Blöcke):
- (a) SHAKEOUT-Schutz (Δ ≥ −0,5R je Block): **erfüllt 11/11** — alle Δ = 0,00R.
  Präzisierung: (a) ist eine **No-Harm-Identität** (das Gate wählt in SHAKEOUT/UNKLAR
  exakt die B48-Baseline, Δ ≡ 0 konstruktionsbedingt), kein Diskriminator der
  Klassifikationsgüte. Die trennschärfere Schutz-Evidenz liegt beim B96-Vergleich:
  der 96er-Arm verlor ungefiltert −2,62R und wurde in 20/41 Phasen nicht eingesetzt.
- (b) TREND-Positivität (Δ > 0,0R je Block, Fassung 1): **verletzt 4/10** — TREND 8–10
  (−1,39R), TREND 23 (0,00R, **Null-Trade-Artefakt**: weder Gate noch B48 handelten),
  TREND 28–29 (−2,00R), TREND 36–37 (−2,00R). Stärkster Gewinner: TREND 12–13 (+9,97R).
- (c) Drawdown-Schranke (Δ ≥ −5,0R je Block): **erfüllt** — tiefster Block −2,00R.

**GESAMTURTEIL (Fassung 1, arretiert): `a=True b=False c=True` → „NICHT BESTANDEN".**
Dieser Befund wird nicht umgeschrieben (Audit-Trail).

**F.3 Mentor-Abnahme (Schicht 2 — ökonomisch/strukturell bestanden)**

Die Zone wird trotz der formalen (b)-Verletzung abgenommen. Begründung:
1. **Statistische Fehlspezifikation von Fassung-1-(b):** Einzelabschnitts-Positivität ist
   für ein Trendfolge-Setup mit Trefferquote 35–45 % kein Erwartungswert-Test. Blöcke aus
   1–2 Trades, die am F4-Stop enden (−2,00R), sind unvermeidbare Varianz, kein
   Filter-Versagen; das Wesen der Trendfolge ist die Überkompensation vieler kleiner
   Verluste durch massive Trendläufe (TREND 12–13: +9,97R).
2. **Makro-Alpha:** Der Filter drehte ein für beide ungefilterten Baselines negatives Jahr
   (B48 −2,05R, B96 −2,62R) auf **+9,05R** — Netto-Alpha **+11,10R**.
3. **Schutzfunktion:** 49 % der Phasen (20/41) als SHAKEOUT identifiziert; Drawdown-Deckel
   (c) mit maximal −2,00R nie berührt (Schranke −5,0R).
4. **Kein Curve-Fitting:** Keine Nachkalibrierung an 2024 (One-Shot-Doktrin §2.16-A.2);
   die versiegelten Schwellen bleiben unberührt. Zone Z2024 ist damit als OOS verbraucht.

Arretierte Status-Formel: **„Formal durch Kriterium (b) verletzt, aber ökonomisch und
strukturell bestanden (+11,10R Netto-Alpha, Schutzfunktion intakt)."**

**F.4 Kriterien-Fassung 2 (universelle Evaluations-Doktrin, VOR Öffnung ZSTRESS arretiert)**

Fassung-1-(b) (Δ > 0,0R je einzelnem TREND-Abschnitt) wird ersetzt durch das
**zonen-kumulierte Trend-Delta**:
- **(b')** `ΣΔ_TREND ≥ 0,0R` über die gesamte Zone (Summe über alle TREND-klassifizierten
  Phasen von `gated − B48`). Da SHAKEOUT/UNKLAR-Phasen konstruktionsbedingt Δ ≡ 0,00R
  beitragen (No-Harm-Identität, F.2), ist `ΣΔ_TREND` **deckungsgleich mit dem
  Primär-Delta** (gated − B48) der Zone — die gesamte Filter-Information liegt in den
  TREND-Phasen.
- **(a)** unverändert: SHAKEOUT/UNKLAR-Blöcke Δ ≥ −0,5R.
- **(c)** unverändert: kumuliertes Netto-Delta **je Einzelabschnitt** ≥ −5,0R (Tail-Deckel).
- **Keine Mindest-Trade-Schwelle:** Liegen keine TREND-Phasen vor, trägt die Schutzfunktion
  (a)/(c); der Stress-Test prüft das rechtzeitige Umschalten im Squeeze/Flash-Crash, nicht
  das Gesetz der großen Zahlen.

Geltungsbereich: **ZSTRESS und alle künftigen Forward-OOS-Läufe** (universell). Die
Änderung ist kein Goalpost-Moving, sondern die prospektive Korrektur einer statistisch
fehlspezifizierten Test-Einheit (Erwartungswert-Test auf 1–2-Trade-Blöcke), datiert und
begründet im §4 arretiert.

Transparenz-Vermerk (duale Ausweisung): Unter Fassung 2 hätte Zone 2024 (b') mit
`ΣΔ_TREND = +11,1R` **bestanden** (deckungsgleich mit dem Primär-Delta +11,10R; die Summe
der abschnittsweise gerundeten Deltas ergibt +11,11R — reine Anzeige-Rundung). Der
Formalbefund F.2 (Fassung 1) bleibt davon unberührt für den historischen One-Shot
maßgeblich.

**F.5 Harness-Synchronisation & Protokoll-Integrität (05.09.2026)**

Vor dem ZSTRESS-One-Shot wurde der Test-Harnisch `test/tmp_regime_validation.py` auf
die duale Kriterien-Auswertung synchronisiert: (i) **harte Zonen-Sperre** für
`--zone=2024` (ValueError vor jedem Dateizugriff; das versiegelte Audit-Artefakt
`test/tmp_regime_oos_2024.txt` bleibt byte-identisch, SHA-256
`d6aee21bdf7f02c44819310c7549ff49937ffecd480d90d42f0984980de40249`); (ii) die
Fassung-1-Block-Marker laufen als Audit-Spalte weiter (`Befund (Fassung 1)`);
(iii) Fassung 2 wird als Summary-Block ausgewiesen (`ΣΔ_TREND` als Roh-Float-Summe
über die TREND-Blöcke, Identitäts-Check `|ΣΔ_TREND − Primär-Delta| < 1e-6`, duale
Urteilszeilen). Syntax-Check (`py_compile`): fehlerfrei (Exit 0). Die
2024-Dokumentation (§2.16-F.2/F.3) bleibt unverändert; Fassung 2 ist ausschließlich
für ZSTRESS und künftige Forward-OOS-Läufe bindend.

**F.6 OOS-Blindtest Zone ZSTRESS — Befund & Gesamtabnahme Stufe 5 (arretiert 05.09.2026)**

Lauf: `python test/tmp_regime_validation.py --stufe=oos --zone=stress` → Protokoll
`test/tmp_regime_oos_stress.txt`. Siegel-Hashes unverändert (sha256 S1 `e55b72e6…`,
S2 `948a9c21…`), Freeze-Schwellen unberührt. **Zonen-Hash `187fdb99fa25a15b…`**
(sha256 der Roh-Zustände der Zone; erster 16-Zeichen-Fingerabdruck, voller Hash
deterministisch reproduzierbar — forensischer Fixpunkt der exakten Datenfolge).

| Kennzahl | Wert |
|---|---|
| Phasen | 53: TREND 28 (52,8 %), SHAKEOUT 18 (34,0 %), UNKLAR 7 (13,2 %) |
| Gated Σr_f4 | **+3,34R** (n=20, zensiert=0, init=16, zeit=4, hd=35; Σr_ref +0,71R) |
| B48 (Referenz) | −3,90R (Σr_ref −8,28R) |
| B96 (Sekundär-Baseline) | −5,00R |
| **Primär-Delta (gated − B48)** | **+7,24R** |

**No-Harm-Identität:** `ΣΔ_TREND` (Roh-Float-Summe über die 14 TREND-Blöcke) =
**+7,24R** ≡ Primär-Delta; `|ΣΔ_TREND − Primär-Delta| < 1e-6` → **erfüllt** (kein Leck
in SHAKEOUT/UNKLAR-Blöcken, §2.16-F.2).

**Qualitativer Schalter (Stress-Prüfung):** Der Filter entzog 47,2 % des Fensters den
Hebel (34,0 % SHAKEOUT + 13,2 % UNKLAR). Die 7 UNKLAR-Phasen in der dünnen
Jahreswechsel-Liquidität (Konflikt-/Totzone, §2.16-E.3) belegen den
Eigenschutz-Mechanismus bei widersprüchlichen Signalen — Kernzweck des Stresstests.

**Tail-Risiko-Kontrolle (c):** Tiefster Einzelblock **−2,00R** (Schranke ≥ −5,0R nie
berührt). Die 11 Fassung-1-(b)-Marker (−1R/−2R/±0R je 1–2-Trade-Block) sind die
dokumentierte Einzel-Block-Varianz; getragen wurde das Fenster von den TREND-Blöcken
44–47 (+7,43R) und 11–12 (+6,56R).

**Duale Urteils-Ausweisung:**
- `URTEIL FASSUNG 1 (Audit-Historie): a=True b=False c=True -> NICHT BESTANDEN`
  (historischer Maßstab; dokumentiert die Einzel-Block-Strenge, kein Widerspruch zur
  Fassung-2-Wertung).
- `GESAMTURTEIL FASSUNG 2 (Bindend ab ZSTRESS): a=True b'=True c=True -> BESTANDEN`

**Gesamtabnahme Stufe 5 (kumuliert über beide unberührten OOS-Zonen):**

| Zone | Gated | B48 | B96 | Netto-Alpha (vs. B48) | Fassung-2-Status |
|---|---|---|---|---|---|
| 2024 (Makro-Holdout) | +9,05R | −2,05R | −2,62R | **+11,10R** | Mentor-Abnahme (§2.16-F.2/F.3) |
| ZSTRESS (Stress-Holdout) | +3,34R | −3,90R | −5,00R | **+7,24R** | **BESTANDEN** (a/b'/c) |
| **Summe** | +12,39R | −5,95R | −7,62R | **+18,34R** | **Stufe 5 ABGENOMMEN** |

**Arretierung:** Stufe 5 (Regime-Klassifikation `scripts/regime_filter.py` inkl.
4 Freeze-Schwellen, Gate-Mapping §2.16-D und Kriterien-Fassung 2) ist
**ABGESCHLOSSEN und ABGENOMMEN**. Die Produktions-Baseline
`scripts/phasen_volumen_profil.py` (+297,14R, v0.4.0-frozen) und der Phase-1-Kern
`scripts/setup_c_profil.py` (Commit `29e7d03`) bleiben unverändert; eine optionale
Integration des Regime-Gates in die Produktion erfolgt — falls beschlossen — als
eigenständiger Folgeschritt (Default `None` = identischer Phase-1-Pfad, §2.16-A.4).
Verbleibender Meilenstein: Forward-OOS nach dem SILVER-Daten-Update (§2.16-B) als
einmaliger Blind-Test unter Fassung 2.

### 2.17 Forward-OOS: Spezifikation & Ausführungsprotokoll (arretiert 05.09.2026 als Vorgriff; Ausführung ausstehend)

**Status:** Spezifikation arretiert. Der verbleibende Meilenstein (§2.16-B: Forward-OOS
nach SILVER-Daten-Update) ist als **einmaliger Blind-Test** definiert: eine einzige,
bis zur Ausführung unberührte Zone aus Daten, die nach dem Scan-Stand
2026-08-28 22:45 importiert werden. Es gelten ausschließlich die Kriterien
**Fassung 2** (§2.16-F.4) und die **One-Shot-Doktrin** (§2.16-A.2). Der Lauf wird
ausschließlich durch den manuellen Import-Vermerk des Anwenders ausgelöst — es
existiert kein automatischer Selbst-Entsiegeltest. **Ausführung blockiert**, bis der
Datenvertrag A (R1–R7) vollständig erfüllt ist.

#### A. Auslöser & Datenvertrag (Refresh-Kriterien R1–R7)

Referenz-Schnittstelle (unverändert, `scripts/market_segmentation.py::load_data`):
Tabelle `ohlcv_bars`, `symbol='SILVER'`, `timeframe='M15'`, Wanduhr-SQL
`time AT TIME ZONE 'UTC'`, Fenster Ende-exklusiv, Zugriff strikt
`duckdb.connect(..., read_only=True)`. Scan-Beleg 05.09.2026 (arretierte Referenz):
`max(ts) = 2026-08-28 22:45`, 0 Bars im September 2026.

Der Forward-OOS-Lauf darf **erst** entsiegelt werden, wenn **alle** harten
Kriterien erfüllt sind; die Prüfung erfolgt read-only als Bestandteil des Laufs
und wird vollständig ins Protokoll geschrieben. Der Lauf bricht bei Verletzung
einer harten Bedingung ab, **bevor** irgendeine Klassifikation ausgewertet wird.

| # | Kriterium | Schärfe |
|---|---|---|
| R1 | **Zeitzuwachs:** `max(ts) > 2026-08-28 22:45` | hart (sonst leeres Fenster) |
| R2 | **Mindest-Zonenlänge:** Zeitspanne Scan-Stand → neues `max(ts)` ≥ 3 Kalendermonate (frühester zulässiger Stichtag: 2026-11-28 22:45) **UND** Bar-Zuwachs nach dem Scan-Stand ≥ 5.200 M15-Bars (≈ 3 volle Monate bei dokumentierter Dichte 1.750–2.120 Bars/Monat, §2.16-A.6) | hart |
| R3 | **Monotonie:** `ts` strikt aufsteigend, keine Duplikat-Zeitstempel | hart |
| R4 | **Naht-Kontinuität:** erster Bar nach dem Scan-Stand ≤ 2026-08-28 23:00 (letzter alter Bar + 15 min); keine Lücke, keine Überlappung an der Naht | hart |
| R5 | **Schema-Identität:** Spalten `time/open/high/low/close/tick_volume`, `symbol`/`timeframe`-Selektion unverändert | hart |
| R6 | **Handelslücken:** keine fehlenden M15-Bars an Handelstagen (Wochenenden/Feiertage zulässig) | weich (Doku-Pflicht) |
| R7 | **Forensik:** `min(ts)/max(ts)/count` des Forward-Fensters + Zonen-Hash (sha256 der Roh-Zustände, Muster §2.16-F.6) ins Protokoll | hart |

**Erwartungsband:** Bei erfülltem R2 werden ≥ 20 Phasen im Fenster erwartet
(~20–30 bei mittlerer Phasen-Aktivität). Die Phasenanzahl wird ausgewiesen und
dokumentarisch eingeordnet, ist aber **keine eigenständige Bestehens-Hürde**
(Phasen-Dichte ist eine nicht steuerbare Marktgröße; die harte Absicherung
liefert R2).

#### B. Zonen-Definition & Lauf-Konfiguration

- **Fenster-Start:** 2026-08-28 00:00 UTC (inklusive) — lückenlos und
  überlappungsfrei anschließend an das arretierte In-Sample-Fenster S1
  (Ende exklusiv 2026-08-28, §2.16-B). **Reinheits-Vermerk:** Die am Scan-Stand
  05.09.2026 bereits vorhandenen Bars des 2026-08-28 (00:00–22:45) waren in
  **keinem** Kalibrierungs-, Sweep- oder OOS-Lauf enthalten (S1 endete exklusiv)
  und sind damit unberührter OOS-Bestandteil der Zone — sie werden nicht
  ausgeblendet, sondern transparent als Vorlauf-Stück ausgewiesen.
- **Fenster-Ende:** Letzter **vollständiger** Handelstag (00:00–23:45 UTC) vor
  `max(ts)` nach Refresh; Fenster Ende-exklusiv bis 00:00 UTC des Folgetags
  (`load_data`-Konvention). Angebrochene Handelstage werden ausgeschlossen
  (Rechts-Zensierung: keine unfertigen Phasen/Konsolidierungs-Ranges am
  Zonenende).
- **Methodik (identisch zu Z2024/ZSTRESS, Harness-Muster `_baue_cache`):**
  Segmentierung (`segmentiere_markt`) und Zeitreihen-Indikatoren
  (`berechne_zeitreihen_indikatoren`) laufen über den **gesamten Zonen-df ab
  Zonenstart**; unvollendete Randphasen ohne `brk_idx` werden verworfen
  (`ZENSIERT_UEBERGEHEN`, E2-konsistent). Zonen-Key im Harness: `ZFWD`;
  der `_WINDOWS`-Eintrag wird nach bestandener R-Prüfung arretiert.
- **Portfolio & Gate-Mapping (unverändert, §2.16-D/F.1):** TREND →
  RAW-A@96 (beide Richtungen) + RAW-B@96 (nur Bruchrichtung), 1-Close entfernt
  (Befund D/W2); SHAKEOUT/UNKLAR → strikt RAW-A@48. Baselines: B48/B96 = RAW-A
  (ungefiltert). Gated = regime-selektive Zusammenstellung.

#### C. Kausalitäts- & Integritäts-Doktrin

1. **Kausalitäts-Audit (bestanden, 05.09.2026):** Alle Regime-Metriken sind
   lookahead-frei bis exakt `brk_idx` — Indikator-Abgriff ausschließlich an
   `.iloc[b]` (ATR/EMA/EMA-Slope/ADX, rekursiv/rolling, kein `shift(-n)`),
   Kanten ausschließlich über die D4-Stufenfunktion aus `U_hist`/`L_hist`
   (`_kanten_werte`, ns/us-normalisiert, Mechanik identisch zu
   `_kanten_reihe`); kein Zugriff auf `U_final`/`L_final` (Regel-7-Finalize =
   Lookahead ersten Grades), kein Kreuz-Fallback. `tol_band_quote` prüft
   Folge-Closes strikt bis `close[brk_idx]` (`k+1 ≤ brk_idx`).
2. **Latch-Doktrin (arretiert):** `klassifiziere_regime` startet je Zone mit
   `letztes="UNKLAR"` — kein Transfer eines In-Sample- oder Vorzonen-Regimes
   in die Forward-Zone (identisch zu Z2024/ZSTRESS, §2.16-F). Kein Latch über
   die Zonengrenze.
3. **Anlauf-Effekt (begrenzt, dokumentiert):** Indikatoren laufen ab `df[0]`
   der Zone an (Wilder-Konvergenz ~50 Bars). Die erste Bruch-Phase endet
   frühestens bei `brk_idx ≥ 48` (Segmentierer: `min_phase_candles = 46` +
   Kaltstart-Garantie `kaltstart_min_bars = 46`) — der ADX-Warmup ist damit
   vor dem ersten `RegimeState` abgeschlossen, der Konvergenz-Resteffekt auf
   die ersten ~1–2 Phasen begrenzt. Bei erfülltem R2 bleibt der
   Anlauf-Anteil < 2 % der Zone (Mentor-Vorgabe erfüllt).
4. **Freeze-Integrität:** Der Lauf bricht bei Hash-Abweichung der versiegelten
   Schwellen hart ab (sha256 S1 `e55b72e6…`, S2 `948a9c21…`,
   `test/regime_schwellen_freezed.json` unverändert, §2.16-C/F.1).

#### D. Bewertung (Kriterien Fassung 2 — bindend, §2.16-F.4)

Der Formalbefund erfolgt **ausschließlich** nach Fassung 2 (für ZSTRESS und
alle künftigen Forward-OOS-Läufe arretiert; die Fassung-1-Block-Marker laufen
im Harness als Audit-Spalte weiter, sind aber **nicht** maßgeblich):

- **(a) SHAKEOUT/UNKLAR-Schutz:** je Einzelabschnitt Δ ≥ −0,5R. Präzisierung:
  (a) ist eine **No-Harm-Identität** — das Gate wählt in SHAKEOUT/UNKLAR exakt
  die B48-Baseline, Δ ≡ 0,00R konstruktionsbedingt (§2.16-F.2).
- **(b')** `ΣΔ_TREND ≥ 0,0R` zonen-kumulativ (Summe über alle
  TREND-klassifizierten Phasen von `gated − B48`). Wegen der No-Harm-Identität
  ist `ΣΔ_TREND` deckungsgleich mit dem Primär-Delta (`gated − B48`) der Zone;
  die gesamte Filter-Information liegt in den TREND-Phasen.
  **Vakuum-Regel:** Liegen keine TREND-Phasen vor, ist die leere Summe
  `0,0R ≥ 0,0R` → (b') erfüllt; der Stress-Test prüft dann das rechtzeitige
  Umschalten, nicht das Gesetz der großen Zahlen (§2.16-F.4).
- **(c) Tail-Deckel:** kumuliertes Netto-Delta **je Einzelabschnitt** ≥ −5,0R.
- **Gesamturteil:** `a ∧ b' ∧ c` → **BESTANDEN**; sonst **NICHT BESTANDEN**.
- **One-Shot:** exakt ein Lauf auf der Zone; kein zweiter Versuch, keine
  Nachkalibrierung, keine Nachbesserung am Filter (§2.16-A.2). Nach dem Lauf
  wird der Zonen-Key `ZFWD` im Harness hart gesperrt (ValueError vor jedem
  Dateizugriff, Muster Z2024, §2.16-F.5) — die Zone ist als OOS verbraucht.

#### E. Protokoll-, Dokumentations- & Reporting-Pflichten

Der Lauf (`python test/tmp_regime_validation.py --stufe=oos --zone=fwd`)
schreibt das Protokoll nach dem ZSTRESS-Muster (§2.16-F.6,
`test/tmp_regime_oos_stress.txt`) als `test/tmp_regime_oos_fwd.txt` mit
folgenden Pflicht-Inhalten:

1. **R-Prüfprotokoll** (R1–R7, read-only; harte Verletzung → Abbruch vor
   Klassifikation).
2. **Siegel-Hashes** unverändert + **Zonen-Hash** (sha256 der Roh-Zustände der
   Zone, erster 16-Zeichen-Fingerabdruck + voller Hash, deterministisch
   reproduzierbar — forensischer Fixpunkt der exakten Datenfolge).
3. **Kennzahlen-Tabelle:** Phasen (TREND/SHAKEOUT/UNKLAR), Gated `Σr_f4`
   (n, zensiert, init/zeit, hd; `Σr_ref`), B48, B96, **Primär-Delta
   (`gated − B48`)**.
4. **Fassung-2-Auswertung:** `ΣΔ_TREND` als Roh-Float-Summe über die
   TREND-Blöcke, Identitäts-Check `|ΣΔ_TREND − Primär-Delta| < 1e-6`
   (No-Harm-Leck-Prüfung), tiefster Einzelblock (Tail-Deckel (c)),
   Urteilszeile `FASSUNG 2 (BINDEND): a=… b'=… c=… -> BESTANDEN /
   NICHT BESTANDEN`; Fassung-1-Audit-Spalte läuft dokumentarisch mit.
5. **Forensik:** SHA-256 der Protokoll-Datei selbst (Muster §2.16-F.5).

Nach Ausführung wird der Befund als **§2.17-G** in dieses Dokument
eingetragen; die §2.16-B-Zeile (Forward-OOS) und §4 (Tracking-Log) erhalten
Status und Ergebnis. Die Protokoll-Datei bleibt unversioniert
(`test/`, gitignored; reproduzierbar). Die Produktions-Baseline
`scripts/phasen_volumen_profil.py` (+297,14R, v0.4.0-frozen) und der
Phase-1-Kern `scripts/setup_c_profil.py` (Commit `29e7d03`) bleiben in
jedem Fall unberührt.

#### F. Eskalationspfad & Folgeschritte

**Bei NICHT BESTANDEN:**
1. Die Zone ist als OOS **verbraucht** (One-Shot, unwiderruflich) — keine
   erneute Auswertung derselben Daten, keine Nachkalibrierung der versiegelten
   Schwellen (Curve-Fitting-Verbot, §2.16-A.1/A.2).
2. Der Regime-Filter wird **nicht** in die Produktions-Pipeline integriert;
   das System bleibt auf Phase-1-Stand (ungefilterte B48/B96-Referenz).
3. **Entscheidungsvorlage an den Anwender** (kein autonomes Re-Tuning), mit
   den strukturell zulässigen Optionen: (i) weiterer Forward-Zyklus mit einer
   **neuen**, nach weiterem Refresh unberührten Zone; (ii) Verwerfen des
   Regime-Ansatzes als Produktions-Kandidat; (iii) Belassen auf Phase-1-Stand.

**Bei BESTANDEN:**
1. **Abnahme** des Forward-OOS analog §2.16-F.6; Stufe 5 inkl. Forward-Meilenstein
   gilt als vollständig validiert.
2. Die optionale Integration des Regime-Gates in `scripts/setup_c_profil.py`
   wird als **eigenständiger, entkoppelter Folgeschritt** behandelt (§2.16-A.4:
   Default `None` = identischer Phase-1-Pfad; Integration erst nach bestandenem
   Gate-Test). **Kein automatisches Scharfschalten** — die Entscheidung über
   einen Produktions-Einsatz trifft der Anwender auf Basis der
   Entscheidungsvorlage.

---

## 3. Explorations- und Prüfplan

1. **Schritt 1 (Statische Move-Analyse):** Untersuchung aller MoveData-Objekte der Baseline über AUG, S1 und S2 auf Ausbruchs-MFE/MAE. — **abgeschlossen** (Befunde in §2.5-Bezug, Details `test/tmp_setup_c_schritt1_mfe_mae_verteilung.txt`).
2. **Schritt 2 (Replay-Skript `test/tmp_setup_c_audit.py`):** Rein lesende Erfassung der Signale gegen DuckDB für alle drei Einstiegs-Arme. — **abgeschlossen** (F4–F8 + D4, Befunde B1–B4 in §2.5, Reports `test/tmp_setup_c_audit_{AUG,S1,S2}.txt`).
3. **Schritt 3 (A/B-Auswertung Trailing):** Vergleich von festem Dollar-Puffer ($0.15\text{ USD}$) gegen dynamische 7er-ATR — **abgeschlossen** (F9–F11, DV1–DV6 in §2.6; Ausführung AUG → S1/S2, Verifikationsanker bestanden, Befunde C1–C5 in §2.7, Reports `test/tmp_setup_c_trailing_{AUG,S1,S2}.txt`). **Fazit:** Stufen-Trailing regime-kontingent — S1 +30,14R (VAR_B) vs. KEIN_TRAILING −43,08R, aber S2 +6,57R (bestes Trailing) vs. KEIN_TRAILING +274,48R.
4. **Schritt 4 (Prüfbericht & Entscheidungsvorlage):** Vorlage der Ergebnisse vor jeglicher Produktions-Integration — **abgeschlossen**; §2.13 arretiert die vollständige Produktions-Blueprint (Phase-1-Kern: RAW-Cluster-A + F4-Stop intrabar + Zeit-Exit 48/96 + phasenlokale Suppression; Regime-Klassifikation als Stufe-5-Validierungs-Rückstellung, nicht in Phase 1). **Übergabe an die Entwicklungsphase `scripts/setup_c_profil.py`.**
5. **Schritt 4a (Zeit-Exit-Matrix `test/tmp_setup_c_zeitexit.py`):** Bereinigung des 274R-Artefakts — **abgeschlossen** (E1–E5 + Datenvertrag in §2.8; Lauf AUG/S1/S2, Verifikationsanker bestanden, Befunde D1–D5 in §2.9, Reports `test/tmp_setup_c_zeitexit_{AUG,S1,S2}.txt`). **Fazit:** 274R-Phantom eliminiert; `F4 + Zeit-Exit (48/96)` schlägt die Stufen-Ratsche in 16/18 Zellen; RAW-Cluster A = stabiler Setup-Kern.
6. **Schritt 4b-Stufe 1 (1-Close-CONFIRMED `test/tmp_setup_c_1close.py`):** Einstiegs-Reparatur für das C4/D4-Defizit — **abgeschlossen** (G1–G5 + Datenvertrag in §2.10; Lauf AUG/S1/S2, Verifikationsanker bestanden, Befunde H1–H4 in §2.11, Reports `test/tmp_setup_c_1close_{AUG,S1,S2}.txt`). **Fazit Stufe 1:** 1-Close schlägt 2-Close in 6/6 Zellen (Δ r_ref bis +52R); S1-CONFIRMED rehabilitiert (−8,6R → +18,2R @48); SL-Delta nur 3–8 % → echter Timing-Vorteil. **G5-Stufe-2-Bedingung eingetreten.**
7. **Schritt 4b-Stufe 2 (Whipsaw-Scan `test/tmp_setup_c_whipsaw.py`):** Gegenrechnung der 1-Close-Fehlausbrüche (Survivorship-Korrektur) — **abgeschlossen** (F1–F3 + Scope ratifiziert, Datenvertrag `WhipsawConfig`/`WhipsawResult`; Entwurf freigegeben; Lauf AUG/S1/S2, Verifikationsanker bitgenau [OK], Befunde W1–W4 in §2.12, Reports `test/tmp_setup_c_whipsaw_{AUG,S1,S2}.txt`). **Fazit Stufe 2:** 1-Close-Netto überlebt nur mit phasenlokaler Suppression (S1 N48 +18,2R → Netto +1,8R; ohne Suppression −20,1R); r_ref-Netto kippt bei N96 (−10,8); TOL_BAND-Forensik 49/53; S2-Whipsaws positiv → Regime-Klassifikation als Produktions-Schalter.
8. **Entwicklungs-Schritte 1–4 (Phase-1-Implementierung `scripts/market_segmentation.py` + `scripts/setup_c_profil.py`):** — **abgeschlossen** (§2.14: Gates L1/L2 + Architektur-Beschlüsse; Shared-Utility als mechanische Extraktion der Baseline-Schleife, **kein `exec()` in Produktion**; Phase-1-Kern RAW-A + F4 intrabar + Zeit-Exit 48/96 + F3-Suppression `(phase, dir)`; Design-Review eliminierte D4-Kreuz-Fallback-/Lookahead-Risiko vor der ersten Ausführung; formaler Validierungslauf `python -m scripts.setup_c_profil --fenster=ALLE` — **L1/L2 bitgenau bestanden, Null-Delta**, Abnahmeprotokoll in §2.15). **Fazit:** Phase 1 produktionsreif; Übergabe an Stufe-5-Roadmap.
9. **Einheiten-Bereinigung D4-Ratchet (Nachbereinigung Phase 1, 05.09.2026):** — **abgeschlossen** (µs/ns-Bug in `_kanten_reihe` von `scripts/setup_c_profil.py` beseitigt — `searchsorted` lief durch `datetime64[us]`-vs-`ns`-Mismatch auf −1 = statische Kante statt zeitlich gültiger Ratchet; Diagnose `test/tmp_diag_kanten_delta.txt` inkl. Trade-Ebenen-Join und Cluster-Migration; Wiederholungslauf `python -m scripts.setup_c_profil --fenster=ALLE`; §2.13-D/§2.14/§2.15 re-arretiert, Header/§4 aktualisiert). **Fazit:** L1-F3/CONFIRMED/RETEST bitgenau invariant; RAW-Split und L2 korrigiert (S1 N48 +22,81R/N96 +27,87R, n=38; S2 +0,31/+0,98, n=3; AUG n=2 statt Vakuum: +3,64/−0,87R); Fix-Commit atomar.

---

**Abschluss (§3):** Alle Explorationsschritte 1–4b, der finale Prüfbericht (Schritt 4, §2.13) sowie die Entwicklungsphase (Schritte 1–4, §2.14/§2.15) sind **abgeschlossen**. Setup C ist als Phase-1-Kern arretiert, implementiert und **bitgenau gegen das L1/L2-Acceptance-Gate verifiziert** (§2.15) — nach der Einheiten-Bereinigung D4-Ratchet (µs/ns, 05.09.2026) erneut bitgenau bestanden und re-arretiert. Offene Punkte (Regime-Klassifikation, Parameter-Robustheit, Out-of-Sample-Validierung) sind als **Stufe-5 / Pre-Production-Gate** in §2.13-C deklariert — sie sind nachgelagerte Arbeitspakete in einer eigenständigen Folge-Session, keine Blocker für die Phase-1-Produktion.

---

## 4. Tracking-Log

| Datum | Ereignis | Status |
|---|---|---|
| 04.09.2026 | Initialisierung Dokument docs/setup_c_experiment.md | abgeschlossen |
| 04.09.2026 | Schritt 1: statische MFE/MAE-Analyse der Baseline-Moves (F1–F3 arretiert); AUG 11 / S1 138 / S2 61 Brüche; Kernbefund: 55,1 % Früh-Shakeout S1, Energie läuft nach (Δ48−12: S1 +1,44R, S2 +1,24R) | abgeschlossen |
| 05.09.2026 | Beschlüsse F4–F6 (struktureller Stop, Volumen shift(1), Execution open[k+1]) | arretiert |
| 05.09.2026 | Beschlüsse F7–F8 (Retest-Timeout 16 Bars, Invalidierung vor Retest → verwerfen) | arretiert |
| 05.09.2026 | Schritt 2: Replay-Design spezifiziert (Doku §2.4); Code-Entwurf tmp_setup_c_audit.py zur Freigabe | abgeschlossen |
| 05.09.2026 | Schritt 2: `test/tmp_setup_c_audit.py` erstellt; Review-Korrektur D4 (RAW-Kanten strikt kausal, KEINE_KANTE) + exec-Slice-Modulregistrierung; Audit-Läufe AUG/S1/S2 ausgeführt — Verifikationsanker bitgenau (11/138/61), Befunde B1–B4 in §2.5 | abgeschlossen |
| 05.09.2026 | Schritt 3 (Trailing A/B): offen — Pivot-Stufen-Trailing vs. ATR-Puffer zur R:R-Wiedergewinnung auf F4-Basis | arretiert |
| 05.09.2026 | Schritt 3: Beschlüsse F9–F11 (starr bis Stufe>Entry; ATR 1,5×+Floor; Exit differenziert intrabar/close) + Datenvertrag DV1–DV6 in §2.6; `test/tmp_setup_c_trailing.py` als Entwurf freigegeben | arretiert |
| 05.09.2026 | Schritt 3: NaN-Fix `_agg_block` (Stufen-Nachzüge/mittl. Haltedauer zeigten "-"); AUG-Kontrolllauf verifiziert; Gesamtlauf AUG/S1/S2 ausgeführt — Verifikationsanker bestanden (11/10/3, 138/110/59, 61/78/18); Befunde C1–C5 in §2.7 | abgeschlossen |
| 05.09.2026 | Schritt 4 (Prüfbericht): offen — §2.7-Implikationen zur Entscheidung (Regime-Filter vor Exit-Design; Mess-Artefakt DATEN_ENDE in S2; CONFIRMED-Einstiegsproblem S1) | offen |
| 05.09.2026 | Schritt 4a: Beschlüsse E1–E5 arretiert (Zeit-Exit-Matrix 24/48/96 als terminale Exit-Regel; Rechts-Zensierung `RECHTS_ZENSIERT` strikt isoliert; RAW-Cluster A ≤1 Bar / B >1 Bar getrennt; Arm-Fokus RAW mit CONFIRMED/RETEST-Referenz; Exit-Matrix `{24,48,96}` × `{KEIN_TRAILING, VAR_A_FIXED}`) + typisierter Datenvertrag `ZeitexitConfig`/`ZeitexitResult` in §2.8 | arretiert |
| 05.09.2026 | Schritt 4a: `test/tmp_setup_c_zeitexit.py` erstellt (KeyError-Fix REPORT_GRUPPE_KEY); Lauf AUG/S1/S2 ausgeführt — Verifikationsanker bestanden (11/10/3, 138/110/59 mit A=35/B=75, 61/78/18 mit A=5/B=73; RECHTS_ZENSIERT S2=2); Befunde D1–D5 in §2.9 (274R-Phantom → S2 +2R bis +9R; F4+Zeit-Exit schlägt Trailing in 16/18 Zellen; RAW-A stabil, RAW-B regime-toxisch S2; CONFIRMED S1-Defizit bestätigt; RETEST Qualitätsanker) | abgeschlossen |
| 05.09.2026 | Schritt 4 (Prüfbericht): in Vorbereitung — §2.9-Implikationen zur Entscheidung (Exit-Empfehlung F4+Zeit-Exit 48/96; RAW-Cluster-A-Kern; CONFIRMED-Einstiegsdefizit → 4b; Regime-Filter EMA-Slope) | offen |
| 05.09.2026 | Schritt 4b: Beschlüsse G1–G5 arretiert (1-Close-Einstieg open[j+1]; RAW-analoger kausaler Stop min(low[j], kante)−0,15; Exit-Konstante F4+Zeit-Exit 48/96 ohne Trailing; 2-Close-Referenz + SL-Delta/R_ref-Verzerrungs-Kontrolle; zweistufige Auswertung mit bedingtem Whipsaw-Scan) + typisierter Datenvertrag `OneCloseConfig`/`OneCloseResult` in §2.10 | arretiert |
| 05.09.2026 | Schritt 4b Stufe 1: `test/tmp_setup_c_1close.py` erstellt; Lauf AUG/S1/S2 ausgeführt — Verifikationsanker bestanden (Paare 11/138/61, S2 je Zelle 1× RECHTS_ZENSIERT isoliert); Befunde H1–H4 in §2.11 (SL-Delta 3–8 %; 1-Close gewinnt 6/6 Zellen auch r_ref, S1 Δ r_ref +46,44/+52,08; CONFIRMED S1 rehabilitiert −8,6R → +18,2R; G5-Stufe-2-Bedingung eingetreten) | abgeschlossen |
| 05.09.2026 | Schritt 4b Stufe 2: Design-Fragen F1–F3 ratifiziert (Negativ-Spiegel `close[j+1] ≤ kante(j)+TOL` + Sub-Typen RETRACE/TOL_BAND; volle Simulation statt pauschal −1R; phasenlokale Open-Position-Suppression) + Scope bestätigt (F3-Population, Bruchrichtung); Datenvertrag `WhipsawConfig`/`WhipsawResult`; Entwurf `test/tmp_setup_c_whipsaw.py` zur Durchsicht vorgelegt | arretiert |
| 05.09.2026 | Schritt 4b Stufe 2: `test/tmp_setup_c_whipsaw.py` freigegeben; Lauf AUG/S1/S2 ausgeführt — Verifikationsanker bitgenau (11/138/61 [OK]); Befunde W1–W4 in §2.12 (Kanten-Erosion S1 N48 +18,2R → Netto +1,8R; Suppression überlebensnotwendig, ohne −20,1R; TOL_BAND 49/53; S2-Whipsaws positiv → 1-Close trend-regime-tauglich) | abgeschlossen |
| 05.09.2026 | Schritt 4 (Prüfbericht & Entscheidungsvorlage): **abgeschlossen** — §2.13-Produktions-Blueprint arretiert (Phase-1-Kern RAW-A + F4 + Zeit-Exit 48/96 + Suppression; verworfen: Stufen-Ratsche, 2-Close-CONFIRMED, 1-Close ohne Suppression, DATEN_ENDE-Exit, N=24; Stufe-5-Rückstellung: Regime-Klassifikation, Parameter-Robustheit, OOS-Validierung); §3 formal abgeschlossen; **Übergabe an Entwicklungsphase `scripts/setup_c_profil.py`** | abgeschlossen |
| 05.09.2026 | Entwicklungs-Schritt 1: Acceptance-Gates L1/L2 + Architektur-Beschlüsse verbindlich in §2.14 verankert (zweistufiges Gate: L1 Pipeline-Anker, L2 RAW-A N=48/N=96; market_segmentation.py als Shared-Utility; reports/setup_c/; Toleranz ±0,05R, Ziel bitgenau) | abgeschlossen |
| 05.09.2026 | Entwicklungs-Schritt 2 (Design-Review `scripts/setup_c_profil.py`): D4-Kausalitätslücke im RAW-Scan entlarvt (Kreuz-Fallback `high >= L_final`, fehlende `scan_lo_dir`-Klemmung) + F3-Suppression auf Key `(phase, dir)` geschärft („derselben Richtung derselben Phase", §2.13-C) + Code-Hygiene (Literal M15, np.floating); finale Freigabe | abgeschlossen |
| 05.09.2026 | Entwicklungs-Schritt 3 (Validierungslauf): `python -m scripts.setup_c_profil --fenster=ALLE` — **L1/L2-Gate bitgenau bestanden über AUG/S1/S2** (Null-Delta; S1 N48 +20,85R / Σr_ref +72,88 / Exit 13/22 / HD 37; N96 +18,11R / +40,99 / 17/18 / 64; S2 N48 +0,39 / N96 +1,92, je 1 zensiert); `n_supprimiert = 0` (No-op-Beweis), Produktions-Default ≡ L2-Referenz; Reports `reports/setup_c/setup_c_{AUG,S1,S2}.txt/.tsv` | abgeschlossen |
| 05.09.2026 | Entwicklungs-Schritt 4 (Abschluss & Commit): §2.15-Abnahmeprotokoll L1/L2 verankert; Header/§3/§4 aktualisiert; 3 atomare Commits (`feat` market_segmentation.py, `feat` setup_c_profil.py, `docs` Gate-Abschluss) auf master gepusht; Reports unversioniert (reproduzierbar); Agents.md unangetastet; **Phase 1 produktionsreif** — Stufe-5-Roadmap (Regime-Klassifikation, Parameter-Robustheit, OOS) in eigenständiger Folge-Session | abgeschlossen |
| 05.09.2026 | **Einheiten-Bereinigung D4-Ratchet (µs/ns):** Bug in `_kanten_reihe` (`scripts/setup_c_profil.py`) beseitigt — `searchsorted` lief durch `datetime64[us]`-vs-`ns`-Mismatch auf −1 (statische Kante = erster hist-Wert statt zeitlich gültiger Ratchet); Diagnose `test/tmp_diag_kanten_delta.txt` (S1/S2, L1/L2 + Trade-Ebene, Cluster-Migration, ENTFALLEN/NEU-Marker); Wiederholungslauf `python -m scripts.setup_c_profil --fenster=ALLE`; §2.13-D/§2.14/§2.15 re-arretiert (S1 N48 +22,81R / r_ref +71,77 / Exit 15/23 / HD 35, N96 +27,87R / +55,17 / 20/18 / 60, n=38; S2 N48 +0,31 / +1,50, N96 +0,98 / +3,56, n=3, 1 zens.; AUG n=2: +3,64 / +8,59 @48, −0,87 / −1,86 @96 — Vakuum-Dokumentation entfällt); L1-F3/CONFIRMED/RETEST bitgenau unverändert; Header/§3/§4 aktualisiert; atomarer Fix-Commit | abgeschlossen |
| 05.09.2026 | Stufe 5: V2-Bereinigung + 1D-Response-Sweep S1+S2 — 4/4 Schwellen auf Plateau-Zentren (nie Peak) kalibriert (`ema_slope_min=0.07`, `ema_slope_max=−0.03`, `adx_schwelle_min=25.0`, `tol_band_quote_max=0.60`); `spread_atr`/`konsolidierung` als tot eliminiert (Occam's Razor); **Freeze versiegelt** (`test/regime_schwellen_freezed.json`, sha256 S1 `e55b72e6…` / S2 `948a9c21…`); §2.16-C/E verankert | abgeschlossen |
| 05.09.2026 | Stufe 5: **OOS-One-Shot Zone 2024** ausgeführt (`--stufe=oos --zone=2024`, Protokoll `test/tmp_regime_oos_2024.txt`) — 41 Phasen: 21 TREND / 20 SHAKEOUT / 0 UNKLAR; Gated **+9,05R** vs. B48 −2,05R (Primär-Delta **+11,10R**; B96 −2,62R); Formalbefund (Fassung 1): a=True b=False c=True → **NICHT BESTANDEN** (4/10 TREND-Blöcke: 2× −2,00R, 1× −1,39R, 1× ±0,00R Null-Trade) | abgeschlossen |
| 05.09.2026 | Stufe 5: **Mentor-Abnahme Zone 2024** (ökonomisch/strukturell bestanden: +11,10R Netto-Alpha, Schutzfunktion intakt, Drawdown-Deckel nie berührt; kein Curve-Fitting) + **Kriterien-Fassung 2 arretiert** (ΣΔ_TREND ≥ 0,0R je Zone ≡ Primär-Delta statt Einzelabschnitts-Positivität — Trendfolge-WR 35–45 %: 1–2-Trade-Blöcke = Varianz; gilt verbindlich für ZSTRESS und alle künftigen Forward-OOS-Läufe); §2.16-F neu, §2.16-Kopf/§2.16-B/§2.16-E synchronisiert; kein Commit (Stufe-5-Code untracked, docs modifiziert) | abgeschlossen |
| 05.09.2026 | Stufe 5: **OOS-One-Shot Zone ZSTRESS** ausgeführt (`--stufe=oos --zone=stress`, Protokoll `test/tmp_regime_oos_stress.txt`) — 53 Phasen: 28 TREND / 18 SHAKEOUT / 7 UNKLAR; Gated **+3,34R** vs. B48 −3,90R (Primär-Delta **+7,24R**; B96 −5,00R); Zonen-Hash `187fdb99…`; Identitäts-Check \|ΣΔ_TREND − Primär-Delta\| < 1e-6: True; Fassung 1: a=True b=False c=True → NICHT BESTANDEN (Audit), **Fassung 2: a=True b'=True c=True → BESTANDEN** | abgeschlossen |
| 05.09.2026 | Stufe 5: **Gesamtabnahme** — beide OOS-Zonen abgenommen (2024: +11,10R Mentor-Abnahme; ZSTRESS: +7,24R BESTANDEN; Summe **+18,34R** Netto-Alpha vs. B48); §2.16-F.6 neu, §2.16-Kopf/§2.16-B/§2.16-E/F.5 synchronisiert; **2 atomare Commits** (① `feat` `scripts/regime_filter.py`, ② `docs` `docs/setup_c_experiment.md`); test/ unversioniert; Baseline +297,14R unverändert | abgeschlossen |
