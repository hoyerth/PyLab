# Setup C: Trendfolge, Sägezahn-Expansion & Ausbruchs-Engine

> **Status:** Initialisierung & Konzeption (04.09.2026) — keine Testläufe, kein Sandboxing.
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
| RETEST_OUTSIDE | LONG / SHORT | Kante bereits gebrochen; Pullback berührt Kante $\pm DENSITY\_BAND$ | M15-Close verteidigt die Ausbruchsseite (Close bleibt außerhalb) |

### 2.3 Trailing-Hierarchie & Exit

- Initial-Stop: $SL\_PCT = 0,45\%$ relativ zum Einstiegspreis.
- Stufen-Trailing (Primär): Stop wandert sukzessive unter das jeweils letzte bestätigte Pivot-Tief (LONG) bzw. über das letzte Pivot-Hoch (SHORT), abzüglich des Puffers ($DENSITY\_BAND$ oder dynamische ATR).
- Adaptives Tightening (Sekundär): Flacht der EMA 20 ab (Steigung unterschreitet Schwellenwert), wird der Stop aggressiver an das Tief der Vor-Bar herangezogen, ohne die Position vorzeitig per Market-Order aufzulösen.
- Vollausstieg: Ausschließlich bei M15-Schlusskurs jenseits des aktuellen Trailing-Levels.

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
| 04.09.2026 | Initialisierung Dokument docs/setup_c_experiment.md | |
