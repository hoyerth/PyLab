# Setup C: Trendfolge, Sägezahn-Expansion & Ausbruchs-Engine

> **Status:** Schritt 1 + Schritt 2 abgeschlossen (05.09.2026, F4–F8 umgesetzt, Audit-Läufe AUG/S1/S2 validiert); Schritt 3 (Trailing A/B) als nächster Schritt.
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

---

## 3. Explorations- und Prüfplan

1. **Schritt 1 (Statische Move-Analyse):** Untersuchung aller MoveData-Objekte der Baseline über AUG, S1 und S2 auf Ausbruchs-MFE/MAE. — **abgeschlossen** (Befunde in §2.5-Bezug, Details `test/tmp_setup_c_schritt1_mfe_mae_verteilung.txt`).
2. **Schritt 2 (Replay-Skript `test/tmp_setup_c_audit.py`):** Rein lesende Erfassung der Signale gegen DuckDB für alle drei Einstiegs-Arme. — **abgeschlossen** (F4–F8 + D4, Befunde B1–B4 in §2.5, Reports `test/tmp_setup_c_audit_{AUG,S1,S2}.txt`).
3. **Schritt 3 (A/B-Auswertung Trailing):** Vergleich von festem Dollar-Puffer ($0.15\text{ USD}$) gegen dynamische 7er-ATR — in Arbeit (R:R-Wiedergewinnung auf F4-Basis, B2).
4. **Schritt 4 (Prüfbericht):** Vorlage der Ergebnisse vor jeglicher Produktions-Integration.

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
| 05.09.2026 | Schritt 3 (Trailing A/B): offen — Pivot-Stufen-Trailing vs. ATR-Puffer zur R:R-Wiedergewinnung auf F4-Basis | in Arbeit |
