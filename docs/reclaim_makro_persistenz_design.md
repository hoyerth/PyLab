# Makro-Persistenz-Modell — Formale Design-Skizze v0.2 (FREIGEGEBEN für Prototyp)

> **Status:** v0.2 — **R1–R5 durch User/Mentor entschieden (02.09.2026), Freigabe
> für die Prototyp-Phase** (`test/tmp_makro_state_proto.py`, reiner Beobachter).
> Prototyp validiert (P5-Start-Anker 66.364 ev2, d=0.086) und **3-Fenster-Diagnose
> bestanden** (AUG-Regression grün: R1_U 352→0, keine Regression früh-stabiler
> Linien; Zonen-Bilanz kein Leck) — §12 Schritt 1–3 abgeschlossen.
> **Passiver `--macro`-Spiegel implementiert & verifiziert** (§12 Schritt 4:
> `scripts/macro_persistence.py` + additiver Hook, Null-Einfluss 27/+24.97R,
> distanzbegrenzte Anker-Abfrage, frozen Kopien).
> **Keine Implementierung im Hauptskript vor Validierung des Prototyps** (Mentor-Vorgabe).
> **Architekturentscheidung (User/Mentor, 02.09.):** Der EdgeStore wird NUR noch
> als Hilfsmodul für Touch-Zählung/Archiv genutzt. **Signal-Logik = kausale
> Schnittmengen-Linie der Baseline** (`U_final`/`L_final` bzw. laufende `_linie`).
> Der Store archiviert, die Baseline führt.
> **Einbauort (nach Freigabe):** `scripts/phasen_volumen_profil.py` (als
> phasen-übergreifender Zustand an der Phasen-Schleife); Prototyp/Validierung
> zuerst in `test/` per exec-Import.

### Entscheidungen R1–R5 (arretiert, 02.09.)

| Frage | Entscheidung | Kurzbegründung |
|---|---|---|
| R1 Zentrum | **Remove-Tail-Schnittmenge** (Baseline-DNA) | Gewichteter Mittelwert verschmiert die Liquiditätskante; MM verteidigen die Akkumulationsgrenze, nicht den Schwerpunkt |
| R2 Tie-Break | **`last_ts` (Aktualität) schlägt Richtung** | Jüngste Bestätigung = aktuellstes Orderbuch; statische Richtungspriorität fadet in expandierenden Märkten (AUG-Beleg: Z1 66.046 vs. Z3 66.364, beide Evidenz 2 → `last_ts` wählt 66.364, d=0.086 ✓) |
| R3 Altersgrenze | **In v1 weglassen** | 1-Phasen-Zonen sind inert und schadfrei; weniger State-Management |
| R4 Bruch-Seite | **R4-Präzisierung: selektives Löschen** — UP-Bruch durch Niveau B löscht UPPER-Zonen mit `center ≤ B`, DOWN-Bruch löscht LOWER-Zonen mit `center ≥ B` | Pauschales Leeren würde ungetestete höhere Zonen (P2-Evidenz 66.459) bei einem lokalen Bruch (P3, B=65.181) vernichten → 352-B-Ziel unerreichbar (Retail-Fehler „unten gebrochen ⇒ oben existiert kein Markt") |
| R5 Tier-2-Geltung | **Umschalten auf Tier 1 nach lokaler Bestätigung; Tier 2 wandert in den Schatten** | Verfeinerte lokale Kante übernimmt die Ausführung; Makro-Anker bleibt als Trend-/Target-Referenz |

---

## 1. Zweck und Abgrenzung

Die Baseline berechnet ihre Linien **phasen-lokal**: `h_acc`/`l_acc` starten bei
jedem Phasenbeginn bei `[]`. Das ist kausal sauber, aber **ohne Gedächtnis** über
die Phasengrenze. Die P5-Drift-Analyse (`test/tmp_p5_drift_ursache.py`) zeigt die
Folge: Nach einem Breakdown (P4-Ende 12.08, Drop auf 63.7) ist die Makro-Oberlinie
(≈66.45, vom User als R1_U bestätigt) für die neue Phase **unsichtbar**, bis
INNERHALB der Phase ein 2. Test in der 66.4x-Zone bestätigt ist → 352 Bars
Blindheit (17.08 19:00). Genau in dieser Zone entstanden aber die P5-Gewinner.

Das **Makro-Persistenz-Modell** führt einen kompakten, kausal gepflegten
**phasen-übergreifenden Linien-Zustand** (`MacroLineState`) ein, der an der
Phasengrenze die *nicht gebrochene* Seite weiterträgt — ohne die Baseline-Phasen-
logik, Signale oder Exits zu verändern.

**Nicht in diesem Dokument:** Signal-Loop-Design (Reclaim-Mechanik,
`MIN_LINE_BOUNCES`), Exit/TP. Das ist der Folgeschritt nach Freigabe dieses Modells.

---

## 2. Empirische Anker (AUG, aus der P5-Drift-Analyse)

| Befund | Zahl | Konsequenz |
|---|---|---|
| P5-U stabilisiert sich erst beim 2. 66.4x-Test | 352 B (17.08 19:00) | Dichte-Schwelle MIN_CLUSTER=2 ist die Schranke, kein Band-Problem |
| Band-Sensitivität | 0.05/0.08 → 385 B; 0.40 → Niveau 66.046 | Bandbreite ist NICHT die Stellschraube |
| Naive Phasen-Kumulation (P1..P5) | Linie 66.58–66.66 ab P5-Start (max. +0.195 über 66.468) | Roh-Kumulation **overshootet** durch P4-Spike-Zone |
| R1_U-Anker | **66.459 (P2, 11.08 03:45)** — exakt User-Fenster-Start | Die 66.45-Linie ist real, multi-phasig getestet |
| P4-Spike-Zone | 66.776 (12.08 11:15) + 66.663 (12.08 14:30), **beide P4, gleicher Tag** | 2 Touches in EINER Phase = keine unabhängige Bestätigung |

**Kernschluss:** Die 66.45-Zone hat Evidenz aus **zwei verschiedenen Phasen**
(66.459 in P2, 66.364 in P4) — sie ist strukturell persistent. Die 66.66/66.78-
Zone hat Evidenz aus **einer einzigen Phase** (P4, gleicher Tag) — sie ist ein
Spike-Paar (Stop-Fischen), das die Linie bei Roh-Kumulation künstlich anhebt.
Der Diskriminator ist also **nicht** die Touch-Zahl und **nicht** das Band,
sondern die **Anzahl verschiedener Phasen, in denen eine Zone getestet wurde**.

---

## 3. Kernidee: Phasen-Evidenz statt Roh-Kumulation

```
ALT (naiv):   Pool aller historischen Pivots  →  Schnittmenge
              → Spike-Paar (1 Phase) zieht Linie nach oben (Overshoot)

NEU:          Zonen-Pool je Seite, Evidenz = Menge der getesteten Phasen
              → eine Zone ist erst ab Evidenz in ≥ 2 Phasen ein
                "Makro-Level" (unabhängig wiederholt getestet)
              → 1-Phasen-Spike-Zonen sind inert (kein operatives Level)
              → Bruch-Seite wird geleert, Gegenseite (left behind) persistiert
```

Eigenschaften, die das Modell erben muss (Baseline-DNA, Anti-Overfit):
- `DENSITY_BAND` (0.15) bleibt die Zonen-Breite.
- Die Schnittmengen-Mechanik (dichte Cluster, Remove-Tail) bleibt für das
  Zonen-Zentrum erhalten — nur die *Kandidaten-Auswahl* wird evidenzbasiert.
- **Kein neuer Zeit-Decay-Parameter** (Begründung §6.2).

---

## 4. Datenvertrag (Python, strikte Type Hints, keine impliziten Dicts)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

Side = Literal["UPPER", "LOWER"]


@dataclass(frozen=True, slots=True)
class MacroTouch:
    """Ein kausal bestaetigter Pivot-Test einer Seite (n=2, ts + 2 Bars)."""
    ts: pd.Timestamp            # Bestaetigungszeitpunkt (kausal, UTC-naiv)
    price: float                # Pivot-Preis
    side: Side
    phase_id: int               # 0-basierte Baseline-Phase, der der Touch
                                # kausal angehoert (waehrend der Phase bekannt)
    tick_volume: float = 0.0    # Volumen am Pivot-Bar (v1 ungenutzt, Vertrag)


@dataclass(slots=True)
class MacroZone:
    """Preis-Zone einer Seite mit Phasen-Evidenz (Cluster, band-breit)."""
    side: Side
    center: float               # Zentrum = Schnittmenge der Zonen-Pivots
                                # (Remove-Tail-Regel, wie Baseline level_schnittmenge)
    prices: list[float] = field(default_factory=list)
    phases_tested: set[int] = field(default_factory=set)   # EVIDENZ
    first_ts: pd.Timestamp | None = None
    last_ts: pd.Timestamp | None = None
    birth_phase: int = -1

    @property
    def evidence(self) -> int:
        """Anzahl verschiedener Phasen mit >= 1 Touch in der Zone."""
        return len(self.phases_tested)


@dataclass(slots=True)
class PhaseBoundaryEvent:
    """Kausales Phasenende (2-Close-Bruch), wie von der Baseline erkannt."""
    ts: pd.Timestamp
    break_dir: Literal["up", "down"]    # up -> UPPER gebrochen, down -> LOWER
    broken_level: float | None          # B = durchbrochene Kante (Baseline brk_kante)
    left_level: float | None            # gegenueberliegende Linie (left behind)
    ended_phase_id: int


@dataclass(slots=True)
class MacroLineState:
    """Persistenter, phasen-uebergreifender Linien-Zustand JE Seite."""
    side: Side
    zones: list[MacroZone] = field(default_factory=list)
    status: Literal["none", "standing", "left_behind"] = "none"
    last_break_ts: pd.Timestamp | None = None
```

**Funktionen (Signatur-Vertrag):**

```python
def update_touch(st: MacroLineState, t: MacroTouch) -> None:
    """Kausale Pivot-Verarbeitung: Zone matchen/erzeugen, Evidenz pflegen."""

def on_phase_boundary(st: MacroLineState, ev: PhaseBoundaryEvent) -> None:
    """Kausale Phasen-Uebergabe (Bruch-Seite leeren, Gegenseite persistieren)."""

def operative_level(st: MacroLineState,
                    local_line: float | None,
                    side: Side) -> float | None:
    """Zweistufige operative Linie (Tier 1 lokal, Tier 2 Makro-Anker)."""
```

---

## 5. Invarianten

1. **Kausalität:** `MacroTouch.ts` ist erst ab `ts + 2 Bars` (Pivot-Lag)
   verarbeitbar; `phase_id` wird erst zugewiesen, wenn die Phase kausal läuft.
   Kein Lookahead über Phasen-Ende hinaus.
2. **Zonen-Disjunktion:** Je Seite sind zwei Zonen disjunkt bzgl. ihrer Zentren:
   `|center_a - center_b| > DENSITY_BAND` für alle `a != b`. Ein neuer Touch
   matcht genau die Zone mit minimalem `|price - center| <= DENSITY_BAND`;
   sonst neue Zone.
3. **Evidenz-Monotonie:** `phases_tested` einer Zone wächst nur (additiv), wird
   nie reduziert — außer die Zone wird durch ein Bruch-Ereignis entfernt.
4. **Bruch-Seite leert sich:** `on_phase_boundary` mit `break_dir="down"`
   (LOWER gebrochen) leert `zones` der LOWER-Seite; `"up"` leert UPPER. Die
   Gegenseite bleibt vollständig erhalten (`status="left_behind"`).
5. **Kein impliziter Zustand:** Alle Übergänge laufen ausschließlich über die
   drei Vertrags-Funktionen; keine versteckten Modul-Globals.
6. **Baseline-Null-Einfluss:** Im reinen Beobachtungsmodus (exec-Import) darf
   `MacroLineState` keine Phasen-/Signal-/Exit-Entscheidung verändern.

---

## 6. Mechanismen

### 6.1 Zonen-Bildung & Pflege (kausal)

- **Match:** `update_touch` sucht die Zone mit `|price - center| <= DENSITY_BAND`
  (nächstes Zentrum). Match → `prices.append`, `phases_tested.add(phase_id)`,
  `last_ts = ts`, Zentrum neu (Schnittmenge über `prices`, Remove-Tail-Regel der
  Baseline: bei >1 Pool-Mitglied wird das Maximum (UPPER) bzw. Minimum (LOWER)
  entfernt, dann Mittelwert).
- **Neuanlage:** Kein Match → neue `MacroZone` (`birth_phase = phase_id`,
  Evidenz `{phase_id}`). Eine 1-Phasen-Zone ist **inert** (kein operatives
  Level, §6.3) — exakt das heutige Baseline-Verhalten für isolierte Pivots
  (66.206/66.538-Ignoranz), nur jetzt explizit modelliert.
- **Grenze des Pools:** Je Zone max. `FENSTER_PIVOTS` (100) Pivots (Ring-
  Puffer, wie Baseline-Fenster). Kein weiterer Speicher-Parameter.

### 6.2 Decay & Gewichtung — Position: EREIGNISbasiert, kein Bar-Decay in v1

**Entscheidung:** Der Alterungs-Mechanismus ist **ereignisbasiert über
Phasen-Grenzen** — nicht zeitbasiert über Bars. Begründung:

- Die P5-Zahlen: P4→P5-Grenze liegt ~148 Bars (12.08 14:30 → 14.08 03:00)
  zurück. Mit einer Bar-Halbwertszeit (Store-Kalibrierung 2880) wäre der Zerfall
  nur `2^(-148/2880) ≈ 0.965` — praktisch wirkungslos. Die Informationsstruktur
  ändert sich aber durch das **Ereignis** „2-Close-Bruch + neue Balance"
  (deckungsgleich mit Baseline-Phasenlogik und Generation-Audit M2/M3).
- Ein zusätzlicher Zeit-Decay wäre ein weiterer Parameter ohne empirischen
  Hebel (Band-Sweep hat gezeigt: die Schranke ist chronologisch/strukturell,
  nicht spektral). **Anti-Overfit-Gebot (User §6):** schlank halten.

**Konsequenz (operativ, nicht als Gewicht):** Zonen altern über die
**Evidenz-Priorität** (§6.5): Eine Zone ohne Touch in der aktuellen oder
unmittelbar vorherigen Phase verliert die operative Führung an die frischere
Zone; eine 1-Phasen-Zone, die mehrere Phasen lang nicht erneut getestet wird,
bleibt inert und wird bei einem Bruch der Seite entfernt. Ein expliziter
`MAX_ZONE_AGE_PHASES`-Aufräum-Parameter ist als Option notiert, in v1 aber
**nicht** vorgesehen (Review-Punkt R3, §11).

### 6.3 Spike-Isolation — Position: Zentrum + Phasen-Evidenz statt Ausreißer

Drei ineinandergreifende Schutzschichten:

1. **Remove-Tail-Regel (geerbt):** Das Zonen-Zentrum ist die Schnittmenge ohne
   den Extrem-Pivot (bei UPPER ohne das Maximum). Ein einzelner Ausreißer
   (66.776) verschiebt das Zentrum nicht.
2. **Phasen-Evidenz-Schwelle:** Eine Zone wird erst ab `evidence >= 2`
   (getestet in ≥ 2 verschiedenen Phasen) zum **Makro-Level-Kandidaten**.
   Das P4-Spike-Paar (66.663/66.776, beide P4, gleicher Tag) bleibt damit
   **dauerhaft inert**, solange keine spätere Phase die 66.7er-Zone erneut
   testet. Genau das verhindert den Overshoot der naiven Kumulation.
3. **Operative Zonen-Wahl:** Liegen mehrere Makro-Kandidaten vor, gewinnt die
   Zone mit **maximaler Evidenz**, Tie-Break: jüngster `last_ts`, dann (UPPER:
   höchstes Zentrum / LOWER: tiefstes Zentrum).

**Worked Check (P5-Start, 14.08 03:00, kausal):** UPPER-Zonen aus P2/P4:
- Zone A ≈ 66.41: Pivots 66.459 (P2), 66.364 (P4) → **Evidenz {P2, P4} = 2**,
  Zentrum nach Remove-Tail = **66.364** (Max 66.459 wird entfernt).
- Zone B ≈ 66.72: Pivots 66.663, 66.776 (P4) → **Evidenz {P4} = 1 → inert**.
→ Makro-Kandidaten (Evidenz ≥ 2): A (66.364, letzter Test 12.08 13:15) und die
66.046-Zone (66.046 P2 + 66.048 P4, letzter Test 12.08 09:00). R2-Tie-Break
(`last_ts`) wählt **A = 66.364** → d = |66.364 − 66.45| = **0.086 ≤ TOL 0.15
schon bei P5-Start** (statt nach 352 Bars). Die P4-Spikes heben die Linie NICHT
an (Overshoot gelöst).

### 6.4 Kausale Übergabe an der Phasengrenze

Regel (symmetrisch, **R4-Präzisierung** — nur durchschrittene Zonen löschen):

| Phasenende | Gebrochene Seite | Aktion (B = durchbrochene Kante) | Gegenseite | Aktion |
|---|---|---|---|---|
| UP-Bruch (2 Closes > B+TOL) | UPPER | **UPPER-Zonen mit `center <= B` leeren** | LOWER | **persistiert**, `status="left_behind"` |
| DOWN-Bruch (2 Closes < B−TOL) | LOWER | **LOWER-Zonen mit `center >= B` leeren** | UPPER | **persistiert**, `status="left_behind"` |

Begründung: Ein 2-Close-Bruch der Seiten-Linie ist die Baseline-Definition für
„diese Seite ist ungültig" — die neue Phase baut die Seite aus frischen Pivots
neu auf (exakt heutiges Verhalten). **Aber** der Bruch absorbiert ausschließlich
die Liquidität bis zur durchbrochenen Kante B; das Orderbuch darüber/darunter
bleibt intakt. Deshalb werden NUR Zonen mit `center <= B` (UP) bzw. `center >= B`
(DOWN) gelöscht — Zonen jenseits von B sind nicht durchschritten und bleiben als
Anker erhalten.

**Arretiertes Gegenbeispiel (AUG, P2/P3/P4):** P3 bricht nach oben durch B =
65.181 (Move-Hoch 65.786). Ein pauschales Leeren der UPPER-Seite würde die
P2-Zone 66.459 vernichten, obwohl der Preis sie nie erreicht hat. In P4 wird die
Zone bei 66.364 erneut getestet (Evidenz {P2, P4}) und steht damit zum P5-Start
als Anker 66.364 bereit (d = 0.086 zu R1_U). Die R4-Präzisierung erhält genau
diese Evidenz-Kette; das pauschale Leeren wäre der Retail-Fehler „Ein Widerstand
bricht unten, also existiert oben kein Markt mehr".

Die Gegenseite wurde **nicht** gebrochen, sondern nur verlassen (left behind);
genau dort liegt das Makro-Gedächtnis, das der Baseline heute fehlt (P5-
Oberlinie). Durchschrittene Level sind deskriptiv; tiefe Alt-Zonen (z. B. R1_L
62.24) re-formieren sich bei Erreichen aus frischen Pivots oder bleiben
Archiv-Referenz.

**Übergabewert:** Es wird **kein Skalar**, sondern der **kompakte Zonen-Zustand**
(§4) übergeben — Zentrum + Evidenz + Zeitstempel. Die Gegenseiten-Zonen können
damit durch frische Touches der neuen Phase **refinert** werden (P5-Touches
66.538/66.399/66.536 treten in die 66.4x-Zone ein → Evidenz {P2, P4, P5}, Zentrum
konvergiert auf ≈ 66.47 = P5-U_final).

### 6.5 Operative Linie (zweistufig) & Signal-Anschluss

```
U_op(k) = Tier 1, falls lokal bestaetigt:
              Schnittmenge der Phasen-lokalen h_acc (Baseline-Status quo,
              MIN_CLUSTER=2, >= 1 lokale Phase)
          sonst Tier 2 (Makro-Anker):
              bestes Makro-Level aus MacroLineState (§6.3 Punkt 3),
              sofern der Preis es kausal erreichen kann (Anker oberhalb
              des Preises fuer SHORT / unterhalb fuer LONG)
```

- **Tier 1 = lokal** reproduziert die Baseline exakt, sobald die Phase genug
  eigene Tests hat (kein Verhalten verändert).
- **Tier 2 = Makro-Anker** schließt genau die Lücke der frühen Phase: Vor der
  lokalen Bestätigung steht die phasen-übergreifende Zone als Anker bereit
  (P5: 66.41 ab Phasenstart statt 352-B-Blindheit).
- Der **Signal-Loop** (Reclaim gegen `U_op`/`L_op`, Bounce-Zählung,
  `MIN_LINE_BOUNCES`) ist ein eigenes Design-Dokument (Folgeschritt) und wird
  hier nur über die Schnittstelle `operative_level(...)` angebunden.

---

## 7. Parameter (komplett, minimal)

| Parameter | Wert | Herkunft |
|---|---|---|
| `DENSITY_BAND` | 0.15 | Baseline (unverändert) |
| `MIN_CLUSTER` | 2 | Baseline (unverändert, für Tier 1) |
| `MIN_ZONE_EVIDENCE` | 2 (Phasen) | **NEU** — einziger neuer Kern-Parameter |
| `FENSTER_PIVOTS` | 100 | Baseline (Ring-Puffer je Zone) |
| `MAX_ZONE_AGE_PHASES` | (entfällt in v1) | Review-Punkt R3 |

Kein Zeit-Decay, kein Halbwertszeit-Parameter, keine Gewichtskaskade.
Der EdgeStore bleibt als eigenständiges Modul (Touch-Zählung) unverändert.

---

## 8. Erwartetes Verhalten im Worked Example P5 (AUG)

| Kausaler Zeitpunkt | Baseline heute | Mit MacroLineState (erwartet) |
|---|---|---|
| P5-Start (14.08 03:00) | U unsichtbar (lokal leer) | Tier 2 = Zone A ≈ 66.36–66.41 (Evidenz P2+P4), **d≈0.04 zu R1_U** |
| 17.08 03:15 (66.206) | ignoriert (isoliert) | ignoriert (1-Phasen-Zone, inert) |
| 17.08 17:15 (66.538) | ignoriert (isoliert) | **Refinement** von Zone A (Evidenz {P2,P4,P5}) |
| 17.08 19:00 (66.399) | **erst jetzt** Sprung auf 66.399 | Zone A-Zentrum ≈ 66.44 |
| 18.08 03:15 (66.536) | 66.468 | Zone A-Zentrum ≈ 66.47 (= P5-U_final) |
| P5-Ende (DOWN-Bruch) | U weg (Reset) | UPPER persistiert (left_behind), LOWER geleert |

Die 66.663/66.776-Spikes (P4) bleiben in allen Zeilen **inert** — kein Overshoot.

---

## 9. Validierungsplan (nach Freigabe, in `test/`)

1. **Referenz-Identität:** exec-Import-Baseline; `MacroLineState` als reiner
   Beobachter → AUG/S1/S2-Signalzahlen exakt unverändert (Null-Einfluss).
2. **Stabilisierungs-Metrik** (erweitert `tmp_kausal_linie_stabilisierung.py`):
   Für jede User-Linie die Bar-Zahl bis `|U_op − Linie| ≤ 0.15` ab Phasenstart:
   Ziel R1_U: 352 B → **0 B**; R2_U/R2_L/R3_U/R4_U bleiben früh (Regression).
3. **Benchmark-Report** (`--benchmark`): 6/8 VOLL müssen erhalten bleiben;
   R4_L-Semantik unverändert (PREIS-ONLY akzeptiert).
4. **Spike-Abwehr-Test:** Synthetischer Einzel-Spike (1 Phase) darf die Linie
   nicht > 0.15 verschieben; 2-Phasen-Evidenz muss die Linie etablieren.
5. **3-Fenster-Konsistenz:** Modell nur dort wirksam, wo eine Gegenseiten-Zone
   kausal existiert (keine Phantom-Level in S1/S2-Trends).

---

## 10. Anti-Overfit-Check (User-Leitplanke §6)

- Genau **ein** neuer Kern-Parameter (`MIN_ZONE_EVIDENCE = 2`).
- Kein Bar-Decay, keine Gewichtskaskade, kein Session-/Grid-Zusatz.
- Alle anderen Größen sind geerbte Baseline-Parameter.
- Der Evidenz-Diskriminator ist **semantisch** (unabhängige Wiederholung über
  Phasen = institutionelle Bestätigung), nicht numerisch gefittet.

---

## 11. Review-Entscheidungen R1–R5 (ALLE ENTSCHIEDEN, 02.09. — siehe Kopf-Tabelle)

- **R1 (Zentrum):** **Remove-Tail-Schnittmenge** (Baseline-DNA) — gewichteter
  Mittelwert verschmiert die Liquiditätskante.
- **R2 (Tie-Break):** **`last_ts` (Aktualität) schlägt Richtung** — AUG-Beleg:
  Z1 66.046 vs. Z3 66.364 (beide Evidenz 2) → `last_ts` wählt korrekt 66.364.
- **R3 (Alters-Grenze):** **In v1 weglassen** (1-Phasen-Zonen inert/schadfrei);
  `MAX_ZONE_AGE_PHASES` bleibt dokumentierte Option.
- **R4 (Bruch-Seite):** **R4-Präzisierung** — selektiv löschen: UP-Bruch durch
  B entfernt UPPER-Zonen mit `center <= B`; DOWN-Bruch entfernt LOWER-Zonen mit
  `center >= B`. Pauschales Leeren ist widerlegt (P3-Gegenbeispiel, §6.4).
- **R5 (Tier-2-Geltung):** **Umschalten auf Tier 1 nach lokaler Bestätigung;
  Tier 2 wandert in den Schatten** (Trend-/Target-Referenz).

## 12. Implementierungsreihenfolge (Prototyp-Phase AKTIV)

1. **Prototyp `test/tmp_makro_state_proto.py`** (exec-Import, reiner Beobachter)
   — Dataclasses aus §4, Update/Übergabe aus §6, Validierung §9 auf AUG. **✓
   ERLEDIGT (02.09.):** Validierung 1: P5-Start-Anker 66.364 ev2 [P2,P4],
   d=0.086 ≤ 0.15 → 0 B statt 352 B. Validierung 2: P4-Spike 66.663 ev1 inert,
   nie gewählt; legitime ev2 erst nach P5-Retests; Entfernung nach echtem
   P7-UP-Bruch (67.201) korrekt.
2. **Review der Trace-Ausgabe gegen §8 (Worked Example)** durch User/Mentor.
   **✓ ERLEDIGT (02.09.):** R1–R5 freigegeben, Design v0.2 arretiert.
3. **3-Fenster-Lauf (§9.5)** + Stabilisierungs-Metrik (§9.2, alle User-Linien).
   **✓ ERLEDIGT (02.09., `test/tmp_makro_3fenster.py`, reiner Beobachter) —
   BESTANDEN:** (a) Zonen-Bilanz kein Leck (S1 ~90 % Entsorgung beidseitig;
   S2-LOWER akkumuliert 81 wegen UP-Dominanz 47/14 — R4-Seiten-Asymmetrie,
   absolut klein, Design-Notiz); (b) S2-LOWER älteste Zone = ganzes Fenster
   (31756 B), Cluttering nur ev1 (inert), ev≥2-Rest = gewünschter Makro-Schatz;
   (c) **AUG-Regression grün:** R1_U 352→0 (Anker 66.364 ev2, d=0.086), früh-
   stabile Linien R2_U 41/R2_L 6/R3_U 33/R4_U 44 B unverändert, frische Level
   (R3_U kein Anker, R3_L/R4_L d=4.6/3.8) korrekt ohne Eingriff.
4. **Passiver Spiegel im Hauptskript hinter `--macro` (rein lesend).**
   **✓ ERLEDIGT (02.09., User-Freigabe):** NEU `scripts/macro_persistence.py`
   (produktive Extraktion, dependency-frei) + additiver Hook ans Dateiende.
   **`best_local_macro_anchor(st, current_price, max_dist)`** (Mentor-Pflicht:
   `abs(center − current_price) ≤ max_dist`, Evidenz ≥ 2, R2) + **frozen
   `MacroAnchorInfo`**-Kopien (Kausalitäts-Schutz). Report-Faktoren 4×/8×/12×
   der kausalen Range-Referenz NUR informativ (keine feste Schwelle).
   Verifiziert: Null-Einfluss (27 Sig/+24.97R exakt), P5-Anker 66.364 ev2,
   Zonen-Bilanz deckungsgleich mit 3-Fenster-Diagnose.
5. **Signal-Loop-Design-Dokument** (Folgeschritt, NACH Freigabe): operative
   Linie Tier1/Tier2 (`operative_level`, `MIN_LINE_BOUNCES`), empirische
   Distanz-Kalibrierung der lokalen Anker-Abfrage, Inline-Hook in
   `find_reclaim_signals` (bar-genau). Der passive Spiegel bleibt Referenz.
