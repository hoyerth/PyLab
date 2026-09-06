# Befund: Inhärente Lateriz am Rechtsrand der Reclaim-Engine (Setup B)

Status: **ARRETIERT / PROJEKT-WEICHE**
Datum: 2026-09-06
Bezug: `scripts/phasen_volumen_profil.py` (frozen v0.4.0, Commit `691bf56`), `scripts/reclaim_live_kernel.py` (Commit `12658a1`)

---

## 1. Management Summary

Die Reclaim-Engine (Setup B) erzeugt in historischen Backtests hochprofitable Signale (+297,14R OOS), lässt sich jedoch nicht als verzögerungsfreier M15-Live-Alarm betreiben. Empirische Tests zeigen 0 frische Signale am Rechtsrand bei einem minimalen Erkennungs-Lag von 2 Bars (Median: 46,5 Bars). Ursache ist kein Implementierungsfehler, sondern die mathematische Konstruktion der Phasen-Segmentierung: Durch die Datenende-Kappung (Abschnitt 4b) liegt die Gegenwart am rechten Rand stets außerhalb der gescannten Phasen-Spanne. Der operative M15-Live-Runner wird gestoppt (Pfad A).

---

## 2. Empirische Evidenz

| Test-Szenario | Scans / Setup | Gemessene Latenz / Befund |
| :--- | :--- | :--- |
| **Trailing-Fenster (600 Bars)** | 138 Zyklen | **0 Signale** mit `einstieg_bar == len(df) - 1` |
| **Trailing-Fenster (600 Bars)** | 288 Zyklen | Min. Erst-Detektions-Lag: **419 Bars** (Linksrand-Artefakt) |
| **Wachsendes Fenster [0..M]** | 196 Zyklen | Min. Lag: **2 Bars** (30 min), **Median: 46,5 Bars** (>11 h) |
| **AUG-Komplettfenster** | Statisch (27 Sig.) | Letzter Entry liegt **285 min vor dem Datenende** |

---

## 3. Mathematische Herleitung der Lateriz-Kette

1. **Exklusive Scan-Schleife** (`reclaim_live_kernel.py`, Z. 1021; frozen Z. 1109):
   `find_reclaim_signals` iteriert strikt über `range(p.i_start, p.i_ende)`. Die Bar am Index `p.i_ende` wird niemals als Trigger-Bar gescannt.
2. **Datenende-Kappung (Regel 7 / 4b)** (`reclaim_live_kernel.py`, Z. 717–751; frozen Z. 763–797):
   Am rechten Rand durchläuft die letzte unfertige Phase die Funktion `_last_grenz_kontakt`. Wird ein Kantenkontakt bei `t_last` gefunden, wird `p.ende = t_last` gesetzt und alle Bars danach fallen aus der Phase heraus.
3. **Pivot-Nachlauf & Phasen-Reife** (frozen Z. 343–359 `find_pivots`, Z. 652–667 Pivot-Übernahme; Z. 685 `MIN_PHASE_CANDLES`):
   Pivots benötigen `PIVOT_LOOKBACK = 2` zur Bestätigung. Neue Phasen erfordern mindestens 46 Kerzen (`MIN_PHASE_CANDLES`). Frische Kursstäbe am rechten Rand können daher mathematisch keine aktive, bestätigte Phase bilden.

---

## 4. Kausalitätsvergleich: Backtest vs. Live-Rechtsrand

| Dimension | Backtest-Modus | Live-Rechtsrand-Modus |
| :--- | :--- | :--- |
| **Phasen-Status** | Vollständig abgeschlossen & bestätigt | Provisorisch, nachlaufend getrimmt |
| **Gegenwart ($len - 1$)** | Liegt tief im Inneren historischer Zonen | Liegt außerhalb von `p.i_ende` |
| **Reclaim-Trigger** | Retrospektiv erkannt nach Bestätigung | Erst nach 2–3 Folge-Bars sichtbar |
| **Ausführung** | Berechnet auf `open[k+1]` bzw. `open[k+2]` | Signalverzug macht Next-Bar-Open unmöglich |

---

## 5. Institutionelles Verdikt

Die Reclaim-Engine agiert bauartbedingt als **retrograder Range-Abschluss-Detektor** und nicht als proaktiver Execution-Trigger. Ein Live-Alarm mit 30 bis 45 Minuten Verzug zerstört die Mean-Reversion-Edge vollständig (Late-Fill-Problematik).

---

## 6. Arretierte Konsequenzen (Pfad A)

1. **Live-Runner gestoppt:** Die Komponenten 3–5 (`show_popup.py`, `run_reclaim_live.py`, `start_reclaim_live.bat`) werden nicht weiterverfolgt.
2. **Kernel bleibt erhalten:** `scripts/reclaim_live_kernel.py` verbleibt als deterministisches, L1-verifiziertes Modul im Repository für künftige Backtest- und Analyse-Zwecke.
3. **Research-Status:** Setup B verbleibt auf dem eingefrorenen Stand (+297,14R OOS).

---

## 7. Ausblick: Pfad B (Kanten-Snapshot-Engine)

Als separates Forschungsthema kann perspektivisch eine entkoppelte Snapshot-Engine evaluiert werden. Diese würde bestätigte Kanten historischer Phasen einfrieren und eingehende Live-Ticks ohne dynamische Neuberechnung der Gesamtphase überwachen. Dies erfordert eine eigenständige Spezifikation und berührt die Baseline nicht.
