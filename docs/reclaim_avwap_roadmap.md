# AVWAP-Integration in der Reclaim-Engine (Setup B) — Roadmap

Status: **Spezifikation / Planung** (kein Produktionscode, keine Baseline-Änderung)
Datum: 2026-09-06
Bezug: `docs/Archiv/RECLAIM.md` (Konzept), `scripts/phasen_volumen_profil.py`
       (frozen v0.4.0, byte-identisch unangetastet), `scripts/anchored_vwap.py`
       (Freigabe 06.09.2026, L1 bitgenau: `test/tmp_anchored_vwap_l1.py`)

---

## 1. Ausgangslage & Zweck

Die Reclaim-Engine (Setup B) handelt Liquiditäts-Sweeps an Phasen-Kanten mit
Rückkehr zur Value Area (Mean-Reversion Richtung POC). Das zustandslose
AVWAP-Modul `scripts/anchored_vwap.py` soll perspektivisch in **zwei
Schatten-Szenarien** evaluiert werden — ohne Eingriff in die arretierte
Baseline-Logik (`find_reclaim_signals`, `_aufloesen`) und ohne In-Sample-Tuning.

## 2. Architektur-Beschlüsse (F1–F5, 06.09.2026)

- **F1 (Zieldatei):** Diese Roadmap als lebende Spezifikation im `docs/`-Root.
- **F2 (Gate-Anker):** **Phasen-AVWAP ab `p.i_start`** (Index der Phase;
  `PhaseData.start` ist Timestamp — `berechne_avwap_vektor` benötigt den Index).
  Der 1-Bar-Sweep-AVWAP ist verworfen: Bei `in_bar` degeneriert er zu
  `(H+L+C)/3` (reine Bar-Geometrie, keine institutionelle Aussagekraft).
- **F3 (Gate-Wirkung):** **Reiner Schatten-Filter.** Kein Eingriff in die
  Signal-Entstehung; Gate-Status wird annotiert, Netto-Alpha-Effekt isoliert
  gemessen (A/B gegen die unveränderte Baseline).
- **F4 (Ziel):** **Separates Schatten-TP1** neben dem arretierten 25/75-Split
  (`ANTEIL_TP1 = 25.0`, `tp1 = POC`, `tp2 = Box-Gegenseite`).
- **F5 (Testplattform):** Hauptskript `scripts/phasen_volumen_profil.py`
  (frozen v0.4.0). Der S3-Kantenspeicher-Strang (`test/reclaim_s3_signals.py`,
  historisch negativ S1 −73,90R / S2 −47,17R) ist **keine** Plattform.

## 3. Gate-Definition (Variante 1, Schatten)

- **Anker:** `p.i_start` (inklusiv). AVWAP kumuliert über `[p.i_start .. s]`.
- **Signal-Close-Bar s** (Gate-Entscheidungszeitpunkt, strikt kausal):
  - `in_bar`:  s = k   (Penetration `lo[k] < L` bzw. `hi[k] > U` UND Reclaim-
    Close `cl[k] >= L_eff` / `cl[k] <= U_eff` in derselben Bar)
  - `next_bar`: s = k+1 (Reclaim-Close erst in der Folge-Bar)
- **Einstieg** (unverändert Baseline): `open[s+1]` (`in_bar`) bzw.
  `open[s+2]` (`next_bar`); Einstieg nur bei `e_preis < POC` (LONG) bzw.
  `> POC` (SHORT).
- **Gate-Regeln** (Wert eingefroren zum Entscheidungszeitpunkt, kein
  Lookahead):
  - LONG  PASS ⇔ `close[s] > phasen_avwap[s]`
  - SHORT PASS ⇔ `close[s] < phasen_avwap[s]`
  - sonst FAIL; `UNDEFINIERT`, wenn `phasen_avwap[s]` nicht endlich
    (defensiv; bei SILVER `tick_volume > 0` praktisch nicht erwartet).
- **Institutionelle Lesart:** Ein Reclaim, der den volumengewichteten
  Phasen-Einstand nicht zurückerobert, ist ein schwacher Reclaim — die
  Absorption der unter/über der Kante gesammelten Liquidität ist nicht
  bestätigt (Schutz vor „ins fallende Messer greifen").

## 4. Schatten-TP1 (Variante 2)

- Der **Phasen-AVWAP zum Signal-Zeitpunkt** dient als dynamisches Zwischenziel
  **nur dann**, wenn er zwischen Einstiegspreis und statischem POC liegt:
  - LONG:  `e_preis < phasen_avwap[s] < POC`
  - SHORT: `POC < phasen_avwap[s] < e_preis`
- Liegt er außerhalb, bleibt das Schatten-Ziel leer (`None`) — der AVWAP
  **hinter** dem Einstieg ist als Ziel mathematisch unsinnig (Mentor-Korrektur).
- **Treffer-Semantik (K5):** Extremum-Parität zu `_aufloesen`
  (`_first(hi >= ziel)` LONG / `_first(lo <= ziel)` SHORT), nicht Close-basiert.
- **Messfrage:** Wie oft nimmt der AVWAP Teilgewinne ab, bevor der Trade vor
  dem POC dreht (d. h. Ziel berührt, POC nicht erreicht, SL nicht berührt)?
  Baseline-Exits (25/75, `tp1 = POC`, `tp2`, SL) bleiben **unangetastet**.

## 5. Typisierter Datenvertrag

```python
from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd

SignalRichtung = Literal["SHORT", "LONG"]
AVWAPGateStatus = Literal["PASS", "FAIL", "UNDEFINIERT"]

@dataclass(frozen=True, slots=True)
class ReclaimAVWAPMetrik:
    """Schatten-Metrik-Vertrag für die AVWAP-Erweiterung (Setup B).

    Reine Annotation; kein Eingriff in Signal-Erzeugung oder Trade-Resolution.
    """
    bar: int                        # Penetrations-Bar k (Code-Parität: lo[k]<L / hi[k]>U)
    reclaim: Literal["in_bar", "next_bar"]
    signal_bar: int                 # s = k (in_bar) bzw. k+1 (next_bar) — Gate-Close
    einstieg_bar: int               # k+1 (in_bar) bzw. k+2 (next_bar), Baseline
    richtung: SignalRichtung        # "SHORT" | "LONG" (Code-Konvention)
    e_preis: float                  # Einstiegspreis (open der Einstiegs-Bar)
    phasen_anker_idx: int           # p.i_start (Index; AVWAP-Anker inklusiv)
    phasen_avwap_signal: float      # AVWAP über [p.i_start..s], kausal, eingefroren
    gate_status: AVWAPGateStatus    # PASS/FAIL/UNDEFINIERT (K2-Richtungsregeln)
    tp1_statisch_poc: float         # Original-TP1 (POC), unverändert
    tp1_schatten_avwap: Optional[float]  # = phasen_avwap_signal nur bei Lage
                                          # zwischen e_preis und POC, sonst None
    tp2_statisch_box: float         # Original-TP2 (Box-Gegenseite), unangetastet
```

## 6. Evaluierung & Benchmark

| Fenster | Baseline v0.4.0 | Rolle |
|---|---|---|
| AUG (10.–28.08.2026) | 27 Sig., CD=12, +24,97R | Entwicklungs-/Sichtfenster (nicht Benchmark) |
| S1 | 201 Sig., +197,26R | Benchmark |
| S2 (2025) | 210 Sig., CD=12, +99,88R | Benchmark |
| **Frozen (OOS)** | **S1 + S2 (CD=12) = +297,14R** | **Referenz, unverändert** |

*Produktions-Default: `MIN_SIGNAL_ABSTAND_BARS = 12` (argv-überschreibbar).
Die CD=8-S2-Variante (240 Sig., +110,79R → OOS +308,05R) ist keine arretierte
Baseline; CD=8 wurde nur im verworfenen S3-Kantenspeicher-Strang geführt
(RECLAIM.md §0-Notiz) und ist für diese Roadmap (F5: Hauptskript) irrelevant.*

- **Hauptkriterium:** PASS-Subset verbessert Summe R / PF / WR gegenüber der
  ungefilterten Baseline **in beiden** Benchmark-Fenstern (S1 UND S2); AUG nur
  diagnostisch.
- **Schatten-TP1-Kriterium:** Anteil der Trades mit AVWAP-Treffer vor POC/SL
  („gerettete Teilgewinne") sowie deren R-Beitrag — bewertet, ob ein früherer
  25-%-Teilgewinn die End-R erhöht oder senkt.
- **Abbruch-Regel:** Kein belastbarer Netto-Beitrag in S1+S2 → Arretierung als
  Null-Befund in dieser Roadmap (analog §5.6 Setup C). Kein In-Sample-Tuning.

## 7. Erwartungssteuerung & Risiken

- **K3:** In balancierten Phasen liegt der Phasen-VWAP ≈ POC (Range-Mitte) —
  weit entfernt von den Kanten-Reclaim-Zonen. Die Gate-PASS-Quote wird klein
  sein; die PASS-Stichprobe kann für belastbare PF-Aussagen zu dünn sein.
  Primärmetrik ist die bedingte Folge-R, nicht die Trefferzahl.
- **K4 (Kausalitäts-Asymmetrie):** Baseline-POC ist phasen-vollständig;
  Schatten-AVWAP strikt kausal bis s. Bei frühen Phasen-Signalen ist der
  AVWAP noch nicht konvergiert — bei der Interpretation zu berücksichtigen.
- **VWAP-POC-Kollinearität:** In symmetrischen Profilen sind Phasen-VWAP und
  POC nahezu identisch (beide messen den Phasen-Durchschnittspreis) — der
  Zusatznutzen entsteht nur in schiefen/mehrgipfligen Profilen („2 Berge").
- **SILVER-Daten:** `tick_volume > 0` durchgehend (Q1-Befund); `real_volume`
  = 0 → keine Bid/Ask-Delta-Interpretation möglich.

## 8. Artefakte & Abgrenzung

- Produktionsmodule byte-identisch: `scripts/phasen_volumen_profil.py`,
  `scripts/anchored_vwap.py`.
- Erwarteter Test-Harness (nach Freigabe, in `test/`): Schatten-Anreicherung
  der Baseline-Signale, kein Eingriff in `find_reclaim_signals`/`_aufloesen`.
- Umsetzung erst nach separatem Freigabe-Gate dieser Roadmap.

