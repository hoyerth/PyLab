# Setup C: Trendfolge, Sägezahn-Expansion & Ausbruchs-Engine

> **Status:** Schritt 1 abgeschlossen; Schritt-2-Design spezifiziert (05.09.2026, Beschlüsse F4–F8) — keine Testläufe, kein Sandboxing.
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

---

## 3. Explorations- und Prüfplan

1. **Schritt 1 (Statische Move-Analyse):** Untersuchung aller MoveData-Objekte der Baseline über AUG, S1 und S2 auf Ausbruchs-MFE/MAE.
2. **Schritt 2 (Replay-Skript `test/tmp_setup_c_audit.py`):** Rein lesende Erfassung der Signale gegen DuckDB für alle drei Einstiegs-Arme.
3. **Schritt 3 (A/B-Auswertung Trailing):** Vergleich von festem Dollar-Puffer ($0.15\text{ USD}$) gegen dynamische 7er-ATR.
4. **Schritt 4 (Prüfbericht):** Vorlage der Ergebnisse vor jeglicher Produktions-Integration.

---

## 4. Tracking-Log

| Datum | Ereignis | Status |
|---|---|---|
| 04.09.2026 | Initialisierung Dokument docs/setup_c_experiment.md | abgeschlossen |
| 04.09.2026 | Schritt 1: statische MFE/MAE-Analyse der Baseline-Moves (F1–F3 arretiert); AUG 11 / S1 138 / S2 61 Brüche; Kernbefund: 55,1 % Früh-Shakeout S1, Energie läuft nach (Δ48−12: S1 +1,44R, S2 +1,24R) | abgeschlossen |
| 05.09.2026 | Beschlüsse F4–F6 (struktureller Stop, Volumen shift(1), Execution open[k+1]) | arretiert |
| 05.09.2026 | Beschlüsse F7–F8 (Retest-Timeout 16 Bars, Invalidierung vor Retest → verwerfen) | arretiert |
| 05.09.2026 | Schritt 2: Replay-Design spezifiziert (Doku §2.4); Code-Entwurf tmp_setup_c_audit.py zur Freigabe | in Arbeit |
