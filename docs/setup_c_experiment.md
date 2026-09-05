# Setup C: Trendfolge, Sägezahn-Expansion & Ausbruchs-Engine

> **Status:** Schritte 1–3 + 4a abgeschlossen (B1–B4 §2.5, C1–C5 §2.7, D1–D5 §2.9, 05.09.2026); 274R-Artefakt eliminiert; F4+Zeit-Exit schlägt Stufen-Trailing in 16/18 Zellen; Schritt 4b-Design arretiert (G1–G5 in §2.10, 05.09.2026) — 1-Close-CONFIRMED-Test zur Einstiegs-Reparatur; Code-Entwurf `test/tmp_setup_c_1close.py` folgt — Baseline unverändert.
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

---

## 3. Explorations- und Prüfplan

1. **Schritt 1 (Statische Move-Analyse):** Untersuchung aller MoveData-Objekte der Baseline über AUG, S1 und S2 auf Ausbruchs-MFE/MAE. — **abgeschlossen** (Befunde in §2.5-Bezug, Details `test/tmp_setup_c_schritt1_mfe_mae_verteilung.txt`).
2. **Schritt 2 (Replay-Skript `test/tmp_setup_c_audit.py`):** Rein lesende Erfassung der Signale gegen DuckDB für alle drei Einstiegs-Arme. — **abgeschlossen** (F4–F8 + D4, Befunde B1–B4 in §2.5, Reports `test/tmp_setup_c_audit_{AUG,S1,S2}.txt`).
3. **Schritt 3 (A/B-Auswertung Trailing):** Vergleich von festem Dollar-Puffer ($0.15\text{ USD}$) gegen dynamische 7er-ATR — **abgeschlossen** (F9–F11, DV1–DV6 in §2.6; Ausführung AUG → S1/S2, Verifikationsanker bestanden, Befunde C1–C5 in §2.7, Reports `test/tmp_setup_c_trailing_{AUG,S1,S2}.txt`). **Fazit:** Stufen-Trailing regime-kontingent — S1 +30,14R (VAR_B) vs. KEIN_TRAILING −43,08R, aber S2 +6,57R (bestes Trailing) vs. KEIN_TRAILING +274,48R.
4. **Schritt 4 (Prüfbericht):** Vorlage der Ergebnisse vor jeglicher Produktions-Integration — in Vorbereitung; übergibt §2.9-Implikationen (F4+Zeit-Exit 48/96 als Exit-Empfehlung, RAW-Cluster-A als Setup-Kern, CONFIRMED-Einstiegsdefizit → 4b) als Entscheidungsvorlagen.
5. **Schritt 4a (Zeit-Exit-Matrix `test/tmp_setup_c_zeitexit.py`):** Bereinigung des 274R-Artefakts — **abgeschlossen** (E1–E5 + Datenvertrag in §2.8; Lauf AUG/S1/S2, Verifikationsanker bestanden, Befunde D1–D5 in §2.9, Reports `test/tmp_setup_c_zeitexit_{AUG,S1,S2}.txt`). **Fazit:** 274R-Phantom eliminiert; `F4 + Zeit-Exit (48/96)` schlägt die Stufen-Ratsche in 16/18 Zellen; RAW-Cluster A = stabiler Setup-Kern.
6. **Schritt 4b (1-Close-CONFIRMED `test/tmp_setup_c_1close.py`):** Einstiegs-Reparatur für das C4/D4-Defizit — **Design arretiert** (G1–G5 + Datenvertrag in §2.10); Code-Entwurf folgt zur Durchsicht (ohne Ausführung). Zweistufig: 4b-Kern (A/B auf F3-Population) → Whipsaw-Scan nur falls S1 positiv überrascht. Danach finale Überführung in Schritt 4 (Prüfbericht).

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
