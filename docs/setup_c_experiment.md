# Setup C: Trendfolge, Sägezahn-Expansion & Ausbruchs-Engine

> **Status:** Schritt 1 + 2 + 3 abgeschlossen (Befunde C1–C5 in §2.7, 05.09.2026); Schritt-3-Fazit: Stufen-Trailing regime-kontingent — kein konsistenter Sieger über KEIN_TRAILING; Übergang Schritt 4 (Prüfbericht) in Vorbereitung — Baseline unverändert.
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

---

## 3. Explorations- und Prüfplan

1. **Schritt 1 (Statische Move-Analyse):** Untersuchung aller MoveData-Objekte der Baseline über AUG, S1 und S2 auf Ausbruchs-MFE/MAE. — **abgeschlossen** (Befunde in §2.5-Bezug, Details `test/tmp_setup_c_schritt1_mfe_mae_verteilung.txt`).
2. **Schritt 2 (Replay-Skript `test/tmp_setup_c_audit.py`):** Rein lesende Erfassung der Signale gegen DuckDB für alle drei Einstiegs-Arme. — **abgeschlossen** (F4–F8 + D4, Befunde B1–B4 in §2.5, Reports `test/tmp_setup_c_audit_{AUG,S1,S2}.txt`).
3. **Schritt 3 (A/B-Auswertung Trailing):** Vergleich von festem Dollar-Puffer ($0.15\text{ USD}$) gegen dynamische 7er-ATR — **abgeschlossen** (F9–F11, DV1–DV6 in §2.6; Ausführung AUG → S1/S2, Verifikationsanker bestanden, Befunde C1–C5 in §2.7, Reports `test/tmp_setup_c_trailing_{AUG,S1,S2}.txt`). **Fazit:** Stufen-Trailing regime-kontingent — S1 +30,14R (VAR_B) vs. KEIN_TRAILING −43,08R, aber S2 +6,57R (bestes Trailing) vs. KEIN_TRAILING +274,48R.
4. **Schritt 4 (Prüfbericht):** Vorlage der Ergebnisse vor jeglicher Produktions-Integration — offen; übergibt §2.7-Implikationen (Mess-Artefakt DATEN_ENDE, Regime-Filter, CONFIRMED-Einstiegsproblem) als Entscheidungsvorlagen.

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
