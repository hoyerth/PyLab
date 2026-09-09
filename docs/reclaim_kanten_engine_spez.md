# Spezifikation: Kausale Standalone-Kanten-Engine (Setup B, SILVER M15)

Status: **ARRETIERT / SPEZIFIKATION V2 (Standalone-Kausal-Engine, Modus B)**
Datum: 2026-09-06 (V1: Commit `c66457b`) — Nachtrag V2: 2026-09-06
       (Kanten-Audit K20/K9/K14: Modus-A-Null-Befund arretiert, §8.3)
Bezug: `docs/reclaim_historie_index.md` (Commit `b197011`),
       `docs/reclaim_snapshot_spez.md` (Commit `dc1e2b0`, falsifiziert),
       `docs/Archiv/RECLAIM.md` (v0.1–v0.4, archiviert),
       `test/SESSION_HANDOFF.md` (Lookahead-Bereinigung 31.08.),
       `scripts/phasen_volumen_profil.py` (Baseline v0.4.0, bleibt byte-identisch)

**V2-Nachtrag (arretierte Befunde des Kanten-Audits, 2026-09-06):**
Modus A (V1: Balance-VWAP-Trigger, symmetrische Admission, P2-Herkunfts-Gate)
ist als **statistischer Null-Befund arretiert** (§8.3). Modus B (V2) führt ein:
Extremum-Ratchet-Admission (Toleranz 0,10 %; Sweep 0,05/0,10/0,15 %),
Touch-Zuordnung **vor** dem SwingFilter, kausale Cluster-Geburt
(Distanz ≤ 0,30 USD; rollierende Grace-Periode 96 Bars; Zwischenschwung ≤ 1,5 %;
Sweep 1,5/2,0 %), Body-Reclaim-Reaktivierung SCHLAFEND→AKTIV ohne Docht-Zwang.
Trigger prüfen ausschließlich `anker_extremum`; `balance_vwap` dient nur als
TP1-Richtwert. Die 2-Body-Bruchlogik (V1) ist trace-verifiziert intakt und
bleibt unverändert.

---

## 1. Zweck & Einordnung

Die Engine ist eine **phasenfreie, sequentielle Standalone-Engine**: Rollierende
Kanten sind die einzige Kantenquelle, die Engine erzeugt ihre **eigenen** Signale
aus der eigenen Kantenstruktur. Sie ist weder ein Filter auf Baseline-Kandidaten
noch ein Post-Phase-Snapshot.

### 1.1 Abgrenzung zu falsifizierten Vorgängern (Pflichtlektüre)

| Strang | Was es war | Warum es falsifiziert/verworfen wurde | Was diese Engine anders macht |
|---|---|---|---|
| **EdgeStore v0.1–v0.4** (02.–03.09., Archiv RECLAIM.md Z. 19–80) | Kanten-Auswahl **ersetzte** die laufende Zone innerhalb des phasengebundenen Baseline-Loops | v0.3: S1+S2 = 277,89R < 292,14R-Ziel; E2/E3-Entfallen-Listen **+76,85R/+25,05R** (eliminierte größte Gewinner); c_sym0 = Curve-Fitting | **Standalone**: erzeugt eigene Kanten UND eigene Signale, kein Eingriff in Baseline-Loop, keine Phasen-Segmentierung als Rahmen |
| **Snapshot-Engine** (06.09., Spez `dc1e2b0`, Schritt-0-Replay ausgeführt) | Post-Phase-Sweeps an **eingefrorenen** Zonen vollendeter Phasen, eine aktive Kante, 192-Bars-Cap | S1 PF 1,07; S2 PF 0,45 (Summe −14,95R) — Gate klar verfehlt | **Lebende Kanten**: Balance verschiebt sich mit neuen bestätigten Touches; Kante lebt über Phasenwechsel weiter; 2-Body-Schalter deaktiviert erst bei echter Trendexpansion |
| **Modus-A-Kanten-Engine V1** (06.09., Spez `c66457b`, Harness `test/tmp_kanten_engine_replay.py`, Schritt-0-Replay ausgeführt) | Balance-VWAP-Trigger, symmetrische Admission, SwingFilter-Herkunfts-Gate P2 (Fall d), ±0,15-Touch-Band ohne Cluster-/Ratchet-Regeln | AUG-Smoke PF 2,29 (+13,39R, nur Referenz); **S1/S2-Matrix 8/8 verfehlt** (PF 0,98–1,20 < 1,30, §8.3): S1 0,44/1,18/1,20/1,13, S2 1,01/0,98/1,14/1,01 (mt 1/5/20/60); Ursachen: K9-Gravity-Falle (Balance-Verwässerung nach innen), P2-Betriebsblindheit (K20: 1 statt 4 Touches; Re-Tests 0,003–0,099 USD verworfen), Makro-Wand-Fragmentierung (63,6–63,7 über 3 Kanten) | **Modus B (V2)**: Extremum-Ratchet-Admission, Touch vor SwingFilter, kausale Cluster-Geburt, Body-Reclaim-Reaktivierung; Trigger gegen `anker_extremum`, VWAP nur TP1-Richtwert (§4.1/§6.1) |
| **Baseline v0.4.0** (+297,14R, frozen) | Intra-Phase-Reclaim gegen laufende Volume-Zone | **Nicht falsifiziert** — aber Tuning-Restbias: SESSION_HANDOFF Z. 145: TOL/VA_PCT/MIN_MOUNTAIN_PCT/VALLEY_REL/MIN_ESTABLISH/SL_PCT/TP2_PUFFER_PCT/ANTEIL_TP1 „noch auf den LOOKAHEAD-Code optimiert" | Kanten-Parameter werden **kausal** gesetzt und im Replay als Sensitivität gemessen, nicht aus der Lookahead-Ära geerbt |

### 1.2 Hypothesen (zu testen, nicht vorausgesetzt)

- **H1:** Eine Standalone-Engine mit lebenden, über Phasenwechsel hinweg
  balancierten Kanten erzeugt eine andere (bessere?) Signalpopulation als die
  Intra-Phase-Baseline und die Post-Phase-Snapshot-Engine.
- **H2:** Reclaims an reifen Typ-B-Kanten (≥ 3 bestätigte Touches) mit sofortigem
  k+1-Open-Einstieg schlagen den 2-Bar-Bestätigungs-Aufschub.
- **H3:** 60-Tage-Kanten sind OOS tragfähig — gegen die archivierte
  Patrick-Selektivität („Alter ≥ 96 Bars nützlichste" ≈ 1 Tag). Deshalb wird
  `max_tage` **gescannt** (1/5/20/60), nicht als Dogma gesetzt.

---

## 2. System-Architektur (4 isolierte Module, `scripts/reclaim_kanten_engine.py`)

| Modul | Verantwortung | Kern-Regeln |
|---|---|---|
| **KantenSpeicher** | Container: Kanten-Historie, Zustände, 60-Tage-Verfall, Volumen im Band | Rollierende Lebensdauer ab letztem Touch; Zustandsautomat AKTIV/SCHLAFEND/VERFALLEN; lokales Kantenvolumen (±0,15 USD-Band) kumulieren |
| **SwingFilter** | Herkunfts-/Amplitudenprüfung von Anläufen | Touch zählt nur, wenn Anlauf von **Gegenkante** stammt ODER Amplitude **≥ 1,0 %**; sonst Zwischenwelle → ignoriert (kein Zähler, keine Verschiebung) |
| **KantenBalancierung** | Balance-Linie ab 2. Touch; 2-Body-Bruch-Logik | 1. Touch = Docht-Extremum; ab 2. Touch Balance über alle bestätigten Touches (Formel: **offen**, siehe §7.1); 2 konsekutive Kerzenkörper jenseits der Kante → SCHLAFEND |
| **ReclaimEngine** | Signal-Scan + Risiko | Sweep an aktiver Typ-B-Kante → Entry k+1-Open; SL 0,45 %; Mindest-Spread ≥ 1,5 % zur Gegenkante; Cooldown 12 |

**V2-Hinweis (Modus B):** Die Modul-Verantwortlichkeiten bleiben, die Semantik
wird gemäß §4.1/§6.1 geändert: SwingFilter blockiert **nur noch Geburten**
(nie Touches an bestehenden Kanten); KantenSpeicher führt `anker_extremum`
(Ratchet) und Cluster-Merkposten (`ZonenMerkposten`, §5.1);
KantenBalancierung verwaltet `balance_vwap` als TP1-Richtwert.

---

## 3. Kausalitäts-Architektur (Kern der Spezifikation)

### 3.1 Zweistufige Bestätigungs-Logik

1. **Kanten-Touch-Bestätigung (2-Bar-Puffer):** Ein Pivot-Extremum an Bar j wird
   erst bei Iteration `j + PIVOT_LOOKBACK` (= j+2) sichtbar und als Touch
   verbucht (`gueltig_ab_bar = bar_index + 2`). Gilt für Geburt, Touch-Zählung,
   Balance-Verschiebung, Reaktivierung. Schützt die Kanten-Struktur vor
   Lookahead.
2. **Reclaim-Einstieg (0-Bar, k+1-Open):** An einer **bereits existierenden,
   aktiven Typ-B-Kante** reagiert der Detektor unmittelbar: Bar k vollendet den
   Sweep (Docht-Durchstich), Einstieg am Open von k+1. Die Kante existierte vor
   Bar k aus bestätigten Touches — kein Lookahead, keine Lateriz.

### 3.2 Verbote (arretierte Wunden, dürfen nicht zurückkehren)

- **KEIN finales Zonen-Screening** (früher filterte die finale Phase-Volume-Zone
  Kandidaten → +250,80R-Lookahead-Artefakt; SESSION_HANDOFF Z. 37–43).
- **KEINE Phasen-Segmentierung / 4b-Datenende-Kappung** (Lateriz-Wunde,
  `docs/reclaim_live_lateriz_befund.md`).
- **KEIN Phasen-Ende-Wissen** — die Engine ist phasenfrei und kennt nur
  bestätigte Pivots, Kanten und den aktuellen Bar k.

---

## 4. Regelwerk

### 4.0 V1-Parameter (Modus A — arretiert als Null-Befund, §8.3)

| Regel | Parameter | Wert / Mechanik | Institutionelle Begründung |
|---|---|---|---|
| Lebensdauer | `max_tage` | 60 Kalendertage ab letztem Touch (**scanbar**: 1/5/20/60) | Liquiditätspools über Monatsgrenzen; aber 60 ist Hypothese (H3) |
| Kanten-Genese | — | 1. Touch: Docht-Extremum; ab 2. Touch: Balance über alle bestätigten Touches | Start am Wendepunkt, dann Konsensbereich |
| Balance-Formel | — | VWAP vs. Schnittmenge (**offen**, §7.1) | Volumen-Konsistenz vs. Einfachheit |
| Klassifikation | `MIN_TOUCHES_B = 3` | Typ A: < 3 Touches (gesperrt); Typ B: ≥ 3 (handelbar) | 3-Punkt-Bestätigung |
| Zwischenwellen | `MIN_SWING_PCT = 1.0` | Ignoriert, außer Gegenkanten-Ursprung oder Amplitude ≥ 1,0 % | Kein Over-Segmenting |
| Deaktivierung | `OUTSIDE_BODIES = 2` | 2 konsekutive M15-Kerzenkörper jenseits → SCHLAFEND | Echte Trendexpansion ≠ Failed Breakout |
| Reaktivierung | — | Neuer bestätigter Pivot an schlafender Kante → AKTIV | Erneuter Liquiditätstest |
| Einstieg | — | Open k+1 nach Sweep an Typ-B-Kante (Bar k) | Kausal, nach feststehendem Close |
| Stop-Loss | `SL_PCT = 0.45` | Fix 0,45 % vom Einstieg | Kein Puffer (Chance-Risiko) |
| Mindest-Spread | `MIN_SPREAD_PCT = 1.5` | ≥ 1,5 % Abstand zur Gegenkante | Chop-Ausschluss |
| Cooldown | `COOLDOWN_BARS = 12` | Je Richtung, Reset je Kante | Verhindert Alarm-Serien (Baseline-DNA) |
| Staffelung | — | Nach lokalem Kantenvolumen (±0,15-Band) | Höchste Kapitalbindung zuerst |
| Touch-Band | `DENSITY_BAND = 0.15` | Touch = |preis − balance| ≤ 0,15 USD | Baseline-Konstante |
| Pivot-Lookback | `PIVOT_LOOKBACK = 2` | Bestätigung nach 2 Bars | Kausalitäts-Puffer (§3.1) |

### 4.1 V2-Regelwerk (Modus B, arretiert nach Kanten-Audit 2026-09-06)

Ersetzt die V1-Semantik für **Kanten-Genese, SwingFilter, Reaktivierung und
Trigger**. V1-Zeilen oben sind damit nur noch Modus-A-Referenz (A/B-Schalter
im Harness, §8.1). Die 2-Body-Bruchlogik (`OUTSIDE_BODIES = 2`) und
`max_tage`-Verfall bleiben unverändert (trace-verifiziert intakt).

| Regel | Parameter | Wert / Mechanik | Institutionelle Begründung |
|---|---|---|---|
| Admission (Ratchet, **zuerst**) | Toleranz `0,10 %` (**Sweep**: 0,05/0,10/0,15) | Asymmetrisch am **laufenden Extremum**: OBEN: Pivot nur zulässig, wenn `high ≥ anker_extremum·(1−Tol)` (am/außerhalb, Ratchet nach außen, nie nach innen); UNTEN symmetrisch (`low ≤ anker_extremum·(1+Tol)`); Innen-Pivots (tiefer als Toleranz) werden **verworfen**: kein Touch, kein Lebensdauer-Reset, keine Reaktivierung | Anti-Gravity: K9-Verwässerung (Balance 66.459→66.364 durch Lower Highs) stoppte verfrühte Shorts/Stops |
| Touch-Mapping (**danach**, vor SwingFilter) | `DENSITY_BAND = 0.15` USD | Nur für **admissions-zulässige** Pivots: Zuordnung zur nächsten Kante derselben Seite mit \|preis − anker_extremum\| ≤ `DENSITY_BAND` zählt **zwingend als Touch** — unabhängig von Amplitude/Herkunft (kein P2-Fall-d); anker_extremum ratchet nur nach außen | Re-Tests sind geometrische Orderbuch-Ereignisse; sie dürfen nicht von Makro-Schwüngen abhängen (K20-Trace: 0,003–0,099-USD-Re-Tests wurden verworfen) |
| SwingFilter (Geburten) | `MIN_SWING_PCT = 1.0` | Filtert **nur noch Geburten**: ohne Touch-Zuordnung zählt ein Pivot nur bei Gegenkanten-Ursprung ODER Amplitude ≥ 1,0 % | Kein Over-Segmenting bei Neugeburten; nie Unterdrückung von Re-Tests |
| Cluster-Geburt | `CLUSTER_DISTANZ = 0.30` USD; Grace 96 Bars; Schwung ≤ 1,5 % (**Sweep** 1,5/2,0) | Herrenlose Zone: ≥ 2 Zonen-Retests derselben Seite, Distanz ≤ 0,30 USD zum laufenden Zonen-Extremum, Abstand aufeinanderfolgender Retests ≤ 96 Bars (rollierend), Zwischenschwung ≤ X % über dem Zonen-Extremum → **Geburt am 2. bestätigten Retest am äußersten Extremum** (Ratchet); Retest 1 = Touch 1 | Kausal löst das 10.08.-Dilemma (63.6–63.7: 5 Tiefs über 22-Bar-Takt werden EINE Kante, statt Fragmentierung über 3 Kanten); 96-Bars = Over-Night-Fähigkeit (H3-Granularität); Schwung-Hürde verhindert Fusion unabhängiger Tiefs |
| Balance-VWAP | — | `balance_vwap` = VWAP der akzeptierten Touches (**reiner TP1-Richtwert**) | Kein Trigger-/Admissions-Referenz mehr (§6.1) |
| Reaktivierung | — | SCHLAFEND → AKTIV durch **Body-Reclaim ohne Docht-Zwang**: OBEN (gebrochen nach oben): `close[k] < anker_extremum` (Schluss zurück unter die Obergrenze); UNTEN (gebrochen nach unten): `close[k] > anker_extremum` (Schluss zurück über die Untergrenze); eine Kerze genügt, kein 2-Body-Erfordernis (§6.1) | K11-Betriebsblindheit: nach Reclaim (Bar 399/400 über Balance) blieb K11 bis Docht-Touch 406 unnötig SCHLAFEND |

---

## 5. Datenverträge

### 5.0 V1-Datenverträge (Modus A, arretiert — Referenz für den A/B-Schalter)

```python
from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd

KantenSeite = Literal["OBEN", "UNTEN"]
KantenZustand = Literal["AKTIV", "SCHLAFEND", "VERFALLEN"]
KantenRolle = Literal["TYP_A_AUFBAU", "TYP_B_HANDELBAR"]
SignalRichtung = Literal["SHORT", "LONG"]


@dataclass(frozen=True, slots=True)
class KausalerPivotPunkt:
    bar_index: int
    zeitstempel: pd.Timestamp
    preis: float
    volumen: float
    gueltig_ab_bar: int  # bar_index + 2 (Kausaler Puffer)


@dataclass(frozen=True, slots=True)
class TouchPunkt(KausalerPivotPunkt):
    ist_gegenkanten_ursprung: bool
    amplitude_pct: float


@dataclass(slots=True)
class KausaleKante:
    kanten_id: int
    seite: KantenSeite
    basis_preis: float          # 1. Touch: Docht; ab 2.: Balance
    balance_preis: float
    geburts_ts: pd.Timestamp
    letzter_touch_ts: pd.Timestamp
    bestaetigte_touches: List[TouchPunkt]
    volumen_im_band: float      # kumuliertes Volumen im ±0,15-Band
    zustand: KantenZustand = "AKTIV"
    konsekutive_outside_bodies: int = 0

    @property
    def touch_anzahl(self) -> int:
        return len(self.bestaetigte_touches)

    @property
    def rolle(self) -> KantenRolle:
        return "TYP_B_HANDELBAR" if self.touch_anzahl >= 3 else "TYP_A_AUFBAU"

    @property
    def ist_handelbar(self) -> bool:
        return self.rolle == "TYP_B_HANDELBAR" and self.zustand == "AKTIV"

    def ist_abgelaufen(self, aktueller_ts: pd.Timestamp, max_tage: int) -> bool:
        return (aktueller_ts - self.letzter_touch_ts) > pd.Timedelta(days=max_tage)


@dataclass(frozen=True, slots=True)
class ReclaimSignalAuftrag:
    signal_id: int
    kanten_id: int
    richtung: SignalRichtung
    signal_bar: int            # Sweep-Bar k
    entry_bar: int             # k + 1
    entry_zeit: pd.Timestamp
    entry_preis: float         # open[k+1]
    stop_loss_preis: float     # entry * (1 ± 0,0045)
    tp1_poc_oder_balance: float  # Ziel: Balance der Kante / POC (offen, §7.2)
    spread_gegenkante_pct: float
```

### 5.1 V2-Datenverträge (Modus B, arretiert)

```python
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple
import pandas as pd

KantenSeite = Literal["OBEN", "UNTEN"]
KantenStatus = Literal["AKTIV", "SCHLAFEND", "VERFALLEN"]


@dataclass(slots=True)
class ZonenMerkposten:
    """Unbestaetigte Cluster-Akkumulation VOR der Kanten-Geburt (herrenlose Zone).

    Wird beim 1. Zonen-Retest einer herrenlosen Zone angelegt; Geburt erst beim
    2. Retest innerhalb der Grace-Periode und unterhalb der Schwung-Huerde
    (kausale Cluster-Geburt, §4.1). Verfaellt, wenn kein Retest im Takt folgt.
    """

    seite: KantenSeite
    erst_bar: int
    letzter_bar: int
    anker_extremum: float          # laufendes Extremum (Ratchet: nach aussen)
    zwischen_extremum: float       # Zwischenschwung-Referenz (Gegenseite)
    retest_bars: List[int] = field(default_factory=list)
    retest_preise: List[float] = field(default_factory=list)

    def ist_abgelaufen(self, aktueller_bar: int, max_grace_bars: int = 96) -> bool:
        return (aktueller_bar - self.letzter_bar) > max_grace_bars

    def zwischenschwung_ueberschritten(
        self, max_schwung_pct: float = 1.5
    ) -> bool:
        if self.seite == "UNTEN":
            diff = self.zwischen_extremum - self.anker_extremum
        else:
            diff = self.anker_extremum - self.zwischen_extremum
        return (diff / self.anker_extremum * 100.0) > max_schwung_pct


@dataclass(slots=True)
class KausaleKanteV2:
    """Modus-B-Kante: Trigger-/Admissions-Referenz ist anker_extremum.

    balance_vwap dient ausschliesslich als TP1-Richtwert (§6.1). Admission
    asymmetrisch am laufenden Extremum (Ratchet, Toleranz 0,10 %, §4.1);
    Innen-Pivots zaehlen nicht als Touch.
    """

    kanten_id: int
    seite: KantenSeite
    anker_extremum: float          # Ratchet: max(Highs) bei OBEN, min(Lows) bei UNTEN
    balance_vwap: float            # reiner TP1-Richtwert (kein Trigger)
    geburts_bar: int
    letzter_touch_bar: int
    touch_bars: List[int] = field(default_factory=list)
    touch_preise: List[float] = field(default_factory=list)
    touch_volumina: List[float] = field(default_factory=list)
    status: KantenStatus = "AKTIV"
    outside_body_count: int = 0

    @property
    def touch_anzahl(self) -> int:
        return len(self.touch_bars)

    @property
    def ist_typ_b(self) -> bool:
        return self.touch_anzahl >= 3
```

---

## 6. Signal-Regeln (ReclaimEngine)

### 6.0 V1-Trigger (Modus A, arretiert — Referenz für den A/B-Schalter)

An einer aktiven Typ-B-Kante (Richtung abhängig von der Seite):

- **SHORT (obere Kante U):** `high[k] > U` (Sweep über U) UND Reclaim-Bestätigung:
  `close[k] ≤ U` (in_bar) bzw. `close[k] > U` und `close[k+1] ≤ U` (next_bar).
  Entry = `open[k+1]` bzw. `open[k+2]`. SL = `entry · (1,0045)`.
- **LONG (untere Kante L):** symmetrisch: `low[k] < L` UND `close[k] ≥ L`
  (in_bar) bzw. `close[k+1] ≥ L` (next_bar). Entry = `open[k+1]`/`open[k+2]`.
  SL = `entry · (0,9955)`.
- **Gates:** Kante `ist_handelbar`; `spread_gegenkante_pct ≥ 1,5 %`;
  Cooldown 12 je Richtung; Entry-Seite konsistent zur Balance
  (SHORT: entry > Balance-Ziel, LONG: entry < Balance-Ziel).
- **Auflösung (Replay):** Baseline-`_aufloesen`-Semantik (SL 0,45 %,
  TP1/Target, Split 25/75, kein Nachzug, kein Trailing) — Port in den Harness.

### 6.1 V2-Trigger-Semantik (Modus B, arretiert)

Referenz für Sweep, Reclaim, Admission und Reaktivierung ist **ausschließlich
`anker_extremum`** (KausaleKanteV2, §5.1). `balance_vwap` dient nur als
TP1-Richtwert (Ziel der 25%-Hälfte) und beeinflusst weder Trigger noch
Admission noch Cooldown.

- **SHORT (obere Kante U):** Sweep = `high[k] > anker_extremum`. Reclaim =
  `close[k] ≤ anker_extremum` (in_bar) bzw. `close[k+1] ≤ anker_extremum`
  (next_bar). Entry `open[k+1]`/`open[k+2]`. SL = `entry · (1,0045)`.
- **LONG (untere Kante L):** Sweep = `low[k] < anker_extremum`. Reclaim =
  `close[k] ≥ anker_extremum` (in_bar) bzw. `close[k+1] ≥ anker_extremum`
  (next_bar). Entry `open[k+1]`/`open[k+2]`. SL = `entry · (0,9955)`.
- **TP1 (25%-Hälfte):** `balance_vwap` der Einstiegs-Kante (Richtwert);
  TP2 = Gegenkanten-Semantik wie V1 (§6.0, Baseline-DNA).
- **Admission:** Ein Pivot zählt nur als Touch, wenn sein Extremum am/außerhalb
  des laufenden `anker_extremum` liegt (Ratchet, Toleranz 0,10 % §4.1).
  Innen-Pivots: kein Zähler, kein Lebensdauer-Reset, keine Reaktivierung.
- **Reaktivierung SCHLAFEND→AKTIV:** per **Close-/Body-Reclaim** ohne Docht-
  Zwang — OBEN (gebrochen nach oben): `close[k] < anker_extremum`; UNTEN
  (gebrochen nach unten): `close[k] > anker_extremum` (eine Kerze genügt; kein
  2-Body-Erfordernis, da die Kante bereits als Typ-B etabliert war).
- **Gates (unverändert):** `ist_typ_b`, `spread_gegenkante_pct ≥ 1,5 %`,
  Cooldown 12 je Kante; Entry-Seite konsistent zu `anker_extremum`
  (SHORT: entry > anker_extremum, LONG: entry < anker_extremum).

---

## 7. Offene Design-Punkte (Entscheidung vor Modul-Implementierung)

> **V2-Entscheidungen (2026-09-06, Modus B):** Punkte 1–4 sind für Modus B
> **entschieden**: (1) VWAP, aber nur als `balance_vwap`-TP1-Richtwert (§6.1);
> (2) TP1 = `balance_vwap`, TP2 = Gegenkanten-Semantik (§6.0/§6.1);
> (3) in_bar **und** next_bar werden beide beibehalten und im Replay als Split
> berichtet; (4) Cooldown je Kante (wie Baseline je Phase). Die Liste bleibt
> als Referenz für Modus A stehen.

1. **Balance-Formel:** VWAP (`Σ P·V / Σ V` über bestätigte Touches) — konsistent
   zur Volumen-Hierarchie — vs. einfache Schnittmenge/arithmetisches Mittel.
   Empfehlung: **VWAP** (die Staffelung nutzt ohnehin lokales Volumen).
2. **Take-Profit-Ziel:** Balance der getroffenen Kante (Mean-Reversion zur
   eigenen Kante) vs. POC/Volumen-Schwerpunkt vs. Gegenseite (Box).
   Empfehlung: **Gegenseiten-Ansatz** (wie Baseline TP2), TP1 = Balance/POC.
3. **Reclaim-Bestätigungs-Semantik:** in_bar (close[k] zurück) vs. next_bar
   (close[k+1]) — beide in §6 spezifiziert; im Replay als Split berichten.
4. **Cooldown-Reset:** je Kante (wie Baseline je Phase) vs. global je Richtung.

### 7.1 Statisch-Kausale Reclaim-Engine V3 (Konzept-Entwurf, Audit 2026-09-06)

> **Status:** V3-Entscheidungen **arretiert 2026-09-08** (E1–E5):
> - **F1 — Doppel-Pivot:** H==L-Umkehrbar registriert **beidseitig** (Touch auf
>   beiden Seiten); die P1-Regel „H gewinnt bei H==L" ist für V3 aufgehoben.
> - **F2 — Touchband-Präzisierung (2026-09-08, Nachtrag `touch_band_pct`):**
>   Kanten-Touchband/Level-Matching ist **relativ** `touch_band_pct = 0,23`
>   (Formel `|extremum − basis| / basis × 100 ≤ 0,23`; ≈ ±0,15 USD bei
>   ~65 USD, symbol-unabhängig skaliert — gegen Zersplitterung der 66,46-Decke);
>   der **Signal-Reclaim** (B) verlangt dagegen den **echten Docht-Durchstich**
>   der Linie (high > basis bzw. low < basis) — bloßer Bandkontakt triggert
>   nicht.
> - **F3 — Re-Trigger:** neue Freigabe nur bei **neuestem bestätigtem Touch mit
>   `pivot_bar > letzter_signal_bar`** UND **max. 1 offene Position je Kante**
>   (kein Stacking, kein starrer Bar-Cooldown). **Durchsetzung: §7.2 Teil 4**
>   (Entry-Zeit-Lesart `entry_bar <= exit_final_bar`, Stacking-Gate arretiert).
> - **Genese (E3):** Pivot-Geburt ohne Amplitudenzwang, Level-Matching
>   `touch_band_pct = 0,23` (relativ).
> - **C-Gate (E5):** je Fenster genau 1 Durchlauf (kein `max_tage`-Grid),
>   Bestehenskriterium wie §8.2, Verankerung in §8.4.
> Das formale Freigabe-Gate für den **Harness-Einbau** (§9, Schritt 3/4) steht
> noch aus — kein Modul-Code vor Freigabe. Die V3-Soll-Kanten-Arretierung bleibt
> maßgeblich: Upper 5/5, Lower-Main 7/7 (via F1), Lower-Minor 4/4 (via F2).
>
> **Nachtrag 2026-09-08 (Straight-Edge-Revision, Mentor-Freigabe E1–E5):**
> Die U2-Akzeptanz der Phase-0b-Tabelle (§7.1 F: „5/3, U2 arretiert
> akzeptiert") ist **vollständig revidiert** — sie war die Zielverfehlung
> (39 Kanten, PF 0,88). Verbindlich bleibt die obige Soll-Arretierung
> 5/7/4. Die Korrektur-Genese und -Ausführung (Cluster-Keimung ≥ 2 Dochte,
> Außenkanten-Prinzip, Histogramm-POC, Box-Phase als Eichmaßstab) ist in
> **§7.2** arretiert.

**Arretierungs-Befunde (Pflichtlektüre, Basis für V3):**

1. **Ebene 1 — Geometrie (Kanten können nicht verharren):** `basis_preis` war im
   Harness ein **schreib-only-Feld** (nur Z. 202/533/892 gesetzt, nie gelesen).
   Die Trigger-/Admissions-/Bruch-Referenz war immer eine **mutierende** Größe:
   - Modus A: `_update_balance` (Z. 442/444/523) → VWAP-Drift nach innen.
   - Modus B: `anker_extremum`-Ratchet (Z. 954/956) + `_b_ratchet_erlaubt`
     (Z. 935) → Verschiebung nach außen **und** Verwerfen legitimer innerer
     Re-Tests.
   - 2-Body-Bruch (Z. 564–569) lief gegen die wandernde `_ref_preis`-Referenz
     statt gegen ein fixes Niveau.
   Konsequenz: Eine Kante konnte nie auf einem festen Preis verharren; die
   menschlich sichtbaren Soll-Kanten (66.46/63.67/64.20) sind strukturell
   nicht abbildbar.
2. **Ebene 2 — Trigger/Ausführung (`_pruefe_und_erzeuge`, Z. 683–800):** Das
   Gate-Design erzwang ein Korridor-VWAP-Modell, das zwei **unabhängige**
   Marktvariablen verknüpfte:
   - 96/97 bestätigte Reclaims im AUG scheiterten an `spread_zu_eng`
     (Gegenkanten-Balance < 1,5 %) — der Trade hing an zwei gleichzeitig
     aktiven, dynamischen Balances.
   - 12-Bar-Cooldown (Z. 774) sperrte legitime Mehrfach-Reclaims an derselben
     Wand (Bars 237 vs. 249 am 12.08.).
   - Gegenkante musste **handelbare** Typ-B sein (Z. 734) → kein Trade, wenn die
     Gegenseite schläft.
   - TP1 = POC/Balance der Einstiegsseite (Z. 750/1133) ist bei statischer Box
     dysfunktional (Ziel läge unter dem Entry → sofortiger TP1-Volltreffer).
   - Reaktivierungs-Lücke (Z. 516–524): SCHLAFENDE Kanten wurden nur durch Pivot
     im Band der **gedrifteten** Balance reaktiviert, nie durch Kontakt am
     **festen** Level → dauerhafte Isolation.

**V3-Architektur — Entkopplung Geometrie (Einstiegskante) von Ausführung
(Kursziel):**

**A. Statische Kante (Geometrie):**
- `basis_preis` ist der **einzige, unverrückbare Anker** (fester institutioneller
  Preis; z. B. 66.46 / 63.67 / 64.20). **Keine** VWAP-Drift, **kein** Ratchet,
  **kein** POC. `balance_preis`/`anker_extremum` entfallen als Referenzen.
- Status nur **AKTIV/SCHLAFEND** (kein `VERFALLEN`, kein Zeitverfall): Statische
  Linien erlöschen nicht durch Zeit, sondern persistieren als Marktgedächtnis
  und werden per Docht-Touch am fixen `basis_preis` reaktiviert.
- SCHLAFEND ausschließlich durch **2 konsekutive Kerzenkörper vollständig
  jenseits** des fixen `basis_preis` (2-Body-Semantik bleibt, aber gegen
  `basis_preis` statt `_ref_preis`).
- **Touch-Registrierung (Zählung/Klassifikation, relativ):** Ein bestätigter
  Pivot-Docht im **`touch_band_pct`-Band (0,23 %) um `basis_preis`** zählt als
  Touch und schaltet eine SCHLAFENDE Kante sofort AKTIV (Reaktivierung;
  Heilung der Reaktivierungs-Lücke Z. 516–524). Relative Formel (symbol-
  unabhängig):
  `|extremum_preis − basis_preis| / basis_preis × 100 ≤ touch_band_pct`
  (≈ ±0,15 USD bei ~65 USD). Eine Reduktion würde die 5 Touches der 66,46-Decke
  über 3 Kanten zersplittern (E3-Korrektur).
- **Doppel-Pivot (F1, arretiert):** Eine Umkehrbar mit H==L gleichzeitig
  (z. B. Bar 386 am 14.08.: low 63.663 tiefstes **und** high 64.077 höchstes
  der Umgebung) registriert **beidseitig**: Das Extremum zählt als Touch an der
  OBEN-Kante (Hoch) **und** an der UNTEN-Kante (Tief). Die P1-Regel „H gewinnt
  bei H==L" ist für V3 **aufgehoben** (A/B-Harness-Zeile 408 bleibt für die
  Regressionsanker A/B unangetastet; V3 nutzt eine eigene Pivot-Prüfung).
- Touch-Mindestabstand `min_bar_abstand = 3` (verhindert Doppelzählung derselben
  Bewegung; keine 12-Bar-Signal-Sperre mehr, siehe E).
- **Touchband vs. Signal-Durchstich (F2-Präzisierung):** Das
  `touch_band_pct`-Band (0,23 %) wirkt **nur** auf Touch-Zählung, Reaktivierung
  und Level-Matching der Genese. Für den **Signal-Reclaim** (B) zählt
  ausschließlich der **echte Docht-Durchstich** der Linie (`high[k] > basis`
  bzw. `low[k] < basis`) — ein bloßer Bandkontakt ohne Durchstich erzeugt
  **kein** Signal.

**B. Einstieg (starke Kante, Typ B):**
- Einstiegskante: **AKTIV** und **≥ 3 bestätigte Touches** (`ist_handelbar_typ_b`).
- Trigger **in_bar primär**: Sweep = Docht **durchbricht** `basis_preis`; Reclaim =
  Close schließt in **derselben** Bar zurück. Entry = `open[k+1]`.
- **next_bar sekundär** (Fallback für verspätete Rückeroberung, bleibt im Harness
  als Split berichtet).
- **Signal-Freigabe (F3, arretiert):** Eine Kante feuert nach einem Trade erst
  wieder, wenn ein **neuer bestätigter Touch** vorliegt, dessen `pivot_bar`
  **größer** als `letzter_signal_bar` der Kante ist (`letzter_signal_bar` wird
  bei jeder Signal-Erzeugung auf die Entscheidungs-Bar gesetzt). Zusätzlich gilt
  **max. 1 offene Position je Kante** (kein Stacking; **durchgesetzt seit §7.2 Teil 4**,
  Entry-Zeit-Lesart `kandidat_entry_bar <= max(exit1_bar, exit2_bar)`). Kein starrer
  Bar-Cooldown; legitime Mehrfach-Reclaims mit Touch-Abstand > 3 (237 vs. 249)
  bleiben erlaubt.
- **Stop-Loss strukturell:** jenseits des **Sweep-Extremums + 0,05 USD Puffer**
  (institutioneller Invalidierungspunkt: erneuter Schlusskurs-Bruch des
  Docht-Extremums = Trendexpansion, kein Reclaim). Fixer 0,45 % nur noch als
  historischer Modus-A/B-Vergleichspunkt.

**C. Kursziel (passive Gegenkante, Typ A):**
- Gegenkante = reiner **passiver Liquiditätsmagnet**; weder Handelbarkeit noch
  Status AKTIV erforderlich (Decke 66.46 und Boden 63.67 sind unabhängige
  Marktvariablen — die Verknüpfung über gleichzeitige Aktivität war der
  Konstruktionsfehler von Ebene 2).
- Qualifikation: **≥ 2 bestätigte Touches** (`ist_kursziel_typ_a`), korrekte
  Seite (SHORT: Ziel-Basis < Einstiegs-Basis), **Distanz Basis-zu-Basis
  ≥ 1,5 %** (Mindest-Raum bleibt Pflicht).
- **SCHLAFEND vollwertig zulässig** (institutionelles Gedächtnis: Breakout-Stops
  und unbediente Limit-Orders liegen dort). Tie-Break bei identischer Distanz:
  AKTIV vor SCHLAFEND.
- A/B-Punkt: Gegenkante mit ≥ 2 vs. ≥ 3 Touches.

**D. Zwei-Stufen-Projektion (TP, arretiert):**
- **TP1** = nächstgelegene qualifizierte Gegenkante (Beispiel Short 66.46 →
  Minor 64.20, Distanz ≈ 3,4 %).
- **TP2** = dahinterliegende (Beispiel → Makro 63.67, Distanz ≈ 4,2 %).
- Positionsaufteilung **50/50 arretiert** (50 % De-Risking an TP1, 50 % laufen
  auf die Makro-Wand); **25/75** als A/B-Sensitivitäts-Variante.
- Fallback: existiert nur **eine** qualifizierte Kante → 100 % auf diese
  (TP1 = TP2); existiert **keine** Kante mit ≥ 1,5 % → kein Trade (mangels Raum).

**E. Entfallene Gates (Arretierung):**
- `spread_zu_eng` gegen dynamische Gegenkanten-Balance **entfällt** (ersetzt durch
  statische Distanz-Prüfung Basis-zu-Basis ≥ 1,5 % in D/C).
- Gegenkanten-Handelbarkeits-/Typ-B-Pflicht **entfällt** (C).
- 12-Bar-Cooldown **entfällt**; Bremsen = Touch-Mindestabstand 3 (A) +
  Signal-Freigabe-Regel F3 (B). `poc_seite`/`crv`-Gate **entfällt** (kein POC
  in V3).

**F. Kanten-Genese (V3, arretiert 2026-09-08 — asymmetrische Geburts-Sperre +
Dominanz-Matching, Nachtrag nach Phase-0-Befund):**

Phase-0-Befund (`test/tmp_v3_genese_audit.py`): Die unbeschränkte Pivot-Geburt
erzeugte 56 Kanten (43 Typ B) auf 1288 Bars — Retail-Chop. Ursachen: Sub-Wellen
derselben Wand gebaren eigene Kanten (K5 63.618 vs. K8 63.797 = 0,281 %; K20
66.459 vs. K18 66.223 = 0,355 %), und Nearest-Preis-Matching zog Touches von der
Hauptwand ab (Bar 249 → K18 statt K20).

- **Geburt ohne Amplitudenzwang, aber mit asymmetrischer Geburts-Sperre
  (`geburts_sperr_pct = 0,50`):** Ein bestätigter Pivot (2-Bar-Puffer) gebiert
  nur, wenn **keine** bestehende Kante gleicher Seite im 0,50-%-Nahbereich
  liegt — **ODER** der neue Pivot das **äußere Extremum** der Zone bildet
  (OBEN: `preis > basis_bestehend`; UNTEN: `preis < basis_bestehend`).
  Range-Expansion/echtes Wand-Extremum wird **nie** unterdrückt (K20 66.459
  darf trotz K18 66.223 bei 0,355 % gebären). **Innere Pivots** im
  0,50-%-Nahbereich (OBEN: `preis ≤ basis_bestehend`; UNTEN:
  `preis ≥ basis_bestehend`) sind **Zwischenwellen**: kein Touch, keine Geburt
  — außer sie liegen im 0,23-%-Touchband einer bestehenden Kante (→ regulärer
  Touch). Verifikation der Reihenfolge in den M15-Rohdaten (silver_m15):
  Bar 101 high ≈ 66.22 (K18-Vorstufe) → Bar 107 high ≈ 66.46 (K20, äußeres
  Extrem = eigentliche Decke).
- **Touch-Matching (Dominanz, arretiert; U1-Fix 2026-09-08):** Liegt ein
  Pivot-Docht im 0,23-%-Band mehrerer Kanten derselben Seite, gewinnt die
  **dominante Kante**: höchste `touch_anzahl`; **bei Gleichstand das äußere
  Extremum** (OBEN: höhere Basis; UNTEN: tiefere Basis). Der naive Tie-Break
  „ältere Kante gewinnt" ist als **Retail-FIFO-Fehler arretiert** (Phase-0b-Befund
  U1) — institutionelle Liquidität liegt an den Außenkanten. Korrektur: K12
  (66.223, Junior) verliert Bar 237/249 an K14 (66.459, äußere Decke) →
  UPPER erwartet 5/5 (107/237/249/529/536).
- **Phase-0b-Arretierung (Ist-Tabelle, 2026-09-08, `test/tmp_v3_genese_audit.py`):
  U1-Fix aktiv → 39 Kanten (OBEN 20, UNTEN 19), 33 Typ B, 63 verworfenen
  Ring-Pivots (0,23–0,50 %).**

  | Soll-Ebene | Soll | Ist (vor U1-Fix) | Erwartung nach U1-Fix |
  |---|---|---|---|
  | UPPER 66.46 | 5 | 3 (237/249 an Junior K12) | **5** (K14 = 107/237/249/529/536) |
  | LOWER-MAIN 63.67 | 7 | 5 | **5** (U2, arretiert akzeptiert) |
  | LOWER-MINOR 64.20 | 4 | 3 | **3** (U2, arretiert akzeptiert) |

  **U2 — Zonen-Nominal vs. kausale Dochte (arretiert akzeptiert, keine
  Zonen-Glättung):** Die menschliche Soll-Zählung (7/7, 4/4) fasst Zonen um
  runde Nominale (63.70, 64.20) ±0,15 USD zusammen; die deterministische Engine
  verankert kausal an konkreten Dochtspitzen. Dass die Engine die Unterseiten-
  Liquidität über K5 (63.797, dist 0,199 % zum Anker 63.67) und K4 (64.071,
  dist 0,201 % zum Anker 64.20) abdeckt, ist **Marktrealität auf Tick-Ebene,
  kein Fehler**. Kein künstliches Verschmelzen/Zusammenziehen von Kanten im Ring
  (Overfitting-Wunde von Modus A/B). **Validierung ausschließlich über das
  Benchmark-Gate §8.4 (PF ≥ 1,30 & ΣR > 0 auf S1 und S2)** — die Soll-Tabelle
  ist Diagnose, nicht Ziel.
- **Junior-Edge-Politik:** Innere Vorläufer (z. B. K18/K12), die VOR dem äußeren
  Extrem geboren wurden, bleiben **bestehen** (keine künstliche Fusion per
  Code-Automatik — Mutationsrisiko). Sie verlieren über das Dominanz-Matching
  alle Überlappungs-Touches. Erreicht ein Junior im Schatten der Hauptwand
  eigenständig ≥ 3 Touches, wird im Replay beobachtet, ob er legitimer
  Zwischen-Widerstand oder Störsignal ist.
- **Touch-Band (Zählung) bleibt relativ `touch_band_pct` 0,23 %** (F2); die
  0,23–0,50-%-Ringzone ist **Zwischenwelle ohne Touch** (P1c). **Bekannte
  Konsequenz (transparent dokumentiert):** Die menschliche Soll-Zählung der
  63.67-Wand enthält Ring-Kontakte — Bar 52 (low ≈ 63.797) liegt 0,281 % über
  der K5-Basis 63.618 und damit **außerhalb** des 0,23-%-Bandes (Oberkante
  63.764), aber innerhalb des menschlichen ±0,15-USD-Fensters um den nominalen
  Anker 63.67 (bis 63.82). Phase 0b weist Ring-Ereignisse je Soll-Ebene
  **separat** aus, damit die Abweichung quantifiziert und die Zähl-Regel
  (Band vs. Zone) datenbasiert entschieden werden kann.
- **Selbstfilternde Schwellen:** 1-Touch-Kanten bleiben harmlos; ≥ 2 Touches =
  Kursziel (Typ A), ≥ 3 = Einstieg (Typ B).
- **Soll/Ist-Verifikation:** Das Genese-Audit (in `test/`, read-only) gleicht
  frei geborene Kanten gegen die 3 Soll-Ebenen (66.46/63.67/64.20) auf
  **`touch_band_pct`-Level-Äquivalenz** ab — Geburten können um bis zu 0,23 %
  vom Soll-Anker abweichen und vor dem Soll-Fensterstart liegen.
- **Chart (D1, arretiert):** Das Genese-Audit rendert zusätzlich
  `test/kanten_engine_genese_AUG.png` (matplotlib Agg, 300 dpi, 18×11):
  Panel 1 = Close + Soll-Ebenen (66.46/63.67/64.20) als Linien + geborene
  Kanten mit ≥ 2 Touches (OBEN durchgezogen/rot, UNTEN gestrichelt/grün) +
  Touch-Eichpunkte + Bar-386-Markierung (Doppel-Pivot F1) + Box 10.08–18.08;
  Panel 2 = Statistik (Kantenzahl, Typ-B-Anteil, Soll/Ist je Ebene).

**Datenvertrag Genese (arretiert):**

```python
from dataclasses import dataclass, field
from typing import List, Literal, Optional
import pandas as pd

KantenSeite = Literal["OBEN", "UNTEN"]


@dataclass(frozen=True, slots=True)
class AsymmetrischeGeneseRegeln:
    touch_band_pct: float = 0.23        # Toleranz für Touch-Zuordnung (~0.15 USD)
    geburts_sperr_pct: float = 0.50     # Sperre nur für innere Sub-Levels
    min_bar_abstand: int = 3            # Zeitfilter zwischen Touches


def darf_kante_geboren_werden(
    seite: KantenSeite,
    neuer_preis: float,
    bestehende_kanten: List["StatischeKanteC"],
    regeln: AsymmetrischeGeneseRegeln,
) -> bool:
    """Asymmetrisch: Äußeres Extremum darf immer gebären; innere Pivots
    werden innerhalb geburts_sperr_pct geblockt (Zwischenwelle)."""
    for kante in bestehende_kanten:
        if kante.seite != seite:
            continue
        dist_pct = (abs(neuer_preis - kante.basis_preis)
                    / kante.basis_preis * 100.0)
        if dist_pct <= regeln.geburts_sperr_pct:
            if seite == "OBEN" and neuer_preis <= kante.basis_preis:
                return False  # innerer Pivot unter bestehender Kante -> blockiert
            if seite == "UNTEN" and neuer_preis >= kante.basis_preis:
                return False  # innerer Pivot über bestehender Kante -> blockiert
    return True


@dataclass(frozen=True, slots=True)
class KantenDominanzVergleich:
    """Dominanz-Matching mit U1-Fix: etablierte Kante gewinnt, bei
    Gleichstand das äußere Extremum (institutionelle Liquidität)."""

    seite: KantenSeite

    def waehle_dominante_kante(
        self,
        kante_a_basis: float,
        kante_a_touches: int,
        kante_b_basis: float,
        kante_b_touches: int,
    ) -> Literal["A", "B"]:
        """Etablierte Kante gewinnt; bei Gleichstand stets das äußere Extremum."""
        if kante_a_touches != kante_b_touches:
            return "A" if kante_a_touches > kante_b_touches else "B"
        # Tie-Break: äußeres Extremum hat institutionellen Vorrang
        if self.seite == "OBEN":
            return "A" if kante_a_basis > kante_b_basis else "B"
        else:
            return "A" if kante_a_basis < kante_b_basis else "B"
```

**V3-Datenverträge (Basis, arretiert):**

```python
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple
import pandas as pd

KantenSeite = Literal["OBEN", "UNTEN"]
KantenStatus = Literal["AKTIV", "SCHLAFEND"]
SignalRichtung = Literal["SHORT", "LONG"]


@dataclass(frozen=True, slots=True)
class ModusCKonfiguration:
    touch_band_pct: float = 0.23   # relatives Band (~0.15 USD bei ~65 USD)
    min_touch_bar_abstand: int = 3 # Touch-Mindestabstand (A)
    min_signal_bar_abstand: int = 3  # (Diagnose; aktive Bremse ist F3)
    tp_mindist_pct: float = 1.5    # Mindest-Raum Basis-zu-Basis (C/D)
    sl_buffer_usd: float = 0.05    # struktureller SL-Puffer (B)
    tp1_anteil_pct: float = 50.0   # Zwei-Stufen-Split (D)
    erlaube_next_bar: bool = True  # next_bar als separater Split (G2)


@dataclass(slots=True)
class StatischeKanteC:
    """V3-Kante (User-Freigabe 2026-09-08).

    basis_preis ist der einzige, unverrückbare Anker. Status nur AKTIV/
    SCHLAFEND (kein VERFALLEN, kein Zeitverfall). Touch = bestätigter Pivot-
    Docht im touch_band_pct-Band (0,23 %); SCHLAFEND = 2 konsekutive Körper
    vollständig jenseits basis_preis; Reaktivierung per Docht-Touch im Band
    (F2). letzter_signal_bar sperrt Re-Trigger ohne neuen Touch (F3).
    """

    kanten_id: int
    seite: KantenSeite
    basis_preis: float          # Unverrückbarer Fixpreis
    geburts_bar: int
    letzter_touch_bar: int = -1000
    letzter_signal_bar: int = -1000
    touch_bars: List[int] = field(default_factory=list)
    outside_body_count: int = 0
    status: KantenStatus = "AKTIV"

    @property
    def touch_anzahl(self) -> int:
        return len(self.touch_bars)

    @property
    def neuester_touch_bar(self) -> int:
        """Höchste pivot_bar aller bestätigten Touches (-1000 wenn keine)."""
        return self.touch_bars[-1] if self.touch_bars else -1000

    @property
    def ist_handelbar_typ_b(self) -> bool:
        """Zwingend >= 3 Touches für den Einstieg (nur AKTIV)."""
        return self.touch_anzahl >= 3 and self.status == "AKTIV"

    @property
    def ist_gueltiges_kursziel_typ_a(self) -> bool:
        """Mindestens 2 Touches als passives Kursziel (auch SCHLAFEND)."""
        return self.touch_anzahl >= 2

    def ist_im_touch_band(
        self, extremum_preis: float, cfg: ModusCKonfiguration
    ) -> bool:
        """Relatives Touch-Band: |p - basis| / basis * 100 <= touch_band_pct."""
        diff_pct = (
            abs(extremum_preis - self.basis_preis) / self.basis_preis * 100.0
        )
        return diff_pct <= cfg.touch_band_pct


@dataclass(frozen=True, slots=True)
class ModusCSignal:
    bar_index: int              # Entscheidungs-Bar k (Reclaim in Bar k)
    zeitstempel: pd.Timestamp
    kanten_id: int
    richtung: SignalRichtung
    basis_preis: float
    sweep_preis: float          # high[k] bzw. low[k] (Docht-Durchstich)
    trigger_preis: float        # close[k] (Reclaim-Schluss)
    entry_preis: float          # open[k+1] (in_bar) bzw. open[k+2] (next_bar)
    stop_loss: float            # Sweep-Docht ± sl_buffer_usd (strukturell)
    tp1_preis: float            # Nächste Gegenkante >= tp_mindist_pct
    tp2_preis: Optional[float]  # Übergeordnete Kante dahinter
    tp1_anteil_pct: float = 50.0
```

**Offene Restpunkte (explizit, blockieren die Freigabe nicht):**
1. ~~**Zeitverfall:**~~ **Entschieden 2026-09-08 (E5):** Kante lebt unbegrenzt bis
   2-Body-Bruch; `max_tage`-Verfall entfällt in V3. C-Gate ohne
   `max_tage`-Grid: je Fenster (AUG/S1/S2) genau 1 Durchlauf, Kriterium §8.2
   (§8.4). H3-Zeitscan (1/5/20/60) betrifft nur noch die A/B-Regressionsanker.
2. ~~**Re-Trigger-Semantik:**~~ **Arretiert 2026-09-08 (F3/E4):** neue Freigabe
   nur bei neuestem bestätigtem Touch mit `pivot_bar > letzter_signal_bar` +
   max. 1 offene Position je Kante; kein starrer Bar-Cooldown (B). **Durchsetzung:
   §7.2 Teil 4** (Gate im Harness aktiv, Entry-Zeit-Lesart).
3. **A/B-Katalog V3 (weiter offen):** Gegenkante ≥ 2/≥ 3 Touches, Split
   50/50 vs. 25/75, SL-Puffer 0,05 USD fest vs. konfigurierbar. Defaults
   arretiert: Gegenkante ≥ 2, Split 50/50, SL-Puffer 0,05 fest.
4. ~~**Soll/Ist-Genese-Verifikation:**~~ **Arretiert 2026-09-08 (Phase 0b):**
   U1-Fix (äußeres Extrem bei Gleichstand) → UPPER erwartet **5/5**; U2
   (Zonen-Nominal vs. kausale Dochte) als kausale Eigenschaft **akzeptiert** —
   Validierung über das Gate §8.4, nicht über die Soll-Strichzählung.
5. ~~**Ring-Zähl-Regel:**~~ **Arretiert 2026-09-08 (U2-Akzeptanz):** Die
   0,23–0,50-%-Ringzone bleibt „Zwischenwelle ohne Touch" (P1c). Ring-Kontakte
   der menschlichen Soll-Zählung (Main Bar 30/63, Minor Bar 320) werden
   **verworfen und nicht nachgezählt** — keine Zonen-Glättung, kein Overfitting
   an runde Nominale. Das Audit weist sie weiterhin separat aus (Diagnose).

### 7.2 Straight-Edge-Revision (Korrektur der V3-Genese & -Ausführung, arretiert
2026-09-08, Mentor-Freigabe E1–E5)

> **Status:** Diese Revision **ersetzt** die U2-Akzeptanz aus §7.1 F (Commit
> `61a0c29`). Die Phase-0b-Tabelle (39 Kanten, 33 Typ B, 63 Ring) bleibt nur
> als **historischer Zielverfehlungs-Befund** stehen. Verbindlich sind die
> Soll-Kanten der August-Box: **UPPER 5/5, LOWER-MAIN 7/7 (via F1),
> LOWER-MINOR 4/4** — gemessen in der Box-Phase (10.08.–18.08.).

**1. Falsifikations-Befund (knallhart, Basis dieser Revision):**

Der AUG-C-Lauf (`test/tmp_kanten_engine_replay.py --modus C`) erzeugte
**39 Kanten** (OBEN 20/UNTEN 19, 33 Typ B, 63 Ring-Verwerfungen) → **66 Trades,
53 Verluste, −6,41 R, PF 0,88** (`kanten_liste_AUG_mC.txt`). Ursachen:

- **Singulärer Docht zeugt eine Kante:** Das Crash-Tief Bar 7 (63.464) und die
  Crash-Tiefs des 10.08. (62.967/64.071) verankerten Kanten an transienten
  Spitzen statt an der fast-durchgehenden geraden Begrenzung.
- **Erst-Extrem-Verankerung statt Linien-Mitte:** Die Kante erbte die *erste*
  Dochtspitze; das spätere Docht-Cluster der Wand (63.60–63.80) konnte sich
  nicht zu einer Linie bündeln.
- **0,5-%-Ring-Sperre friert Wand-Dochte ein:** Bars 30/63 (Main) und 320
  (Minor) sind zugehörige Wand-Dochte, wurden aber als „innere Zwischenwellen"
  gegen die falsche (zu tiefe) Nachbarkante verworfen.
- Folge: 16 Zwischenkanten im 4,4-%-Niemandsland (63.67–66.46), die nach 3
  Berührungen als vollwertige Typ-B-Range-Grenzen handelten und
  Trendbewegungen mitten im Niemandsland fadeten.

**2. Regel 1 — Cluster-Keimung (≥ 2 Dochte im Band):**

- Eine Kante entsteht **niemals aus einem singulären Docht**. Ein einzelner
  bestätigter Pivot-Docht (2-Bar-Puffer, F1-dual) ist ein reines
  **Markierungs-Ereignis** (Seed). Transiente Tiefs (63.464/62.967/64.071)
  bleiben ohne Kante, bis ein **zweiter bestätigter Pivot-Docht** im
  Toleranzband liegt.
- **Einheitliches relatives Band (E2, kein Retail-Ebenen-Tuning):**
  `SE_BAND_PCT ≈ 0,11–0,12 %` (≈ ±0,075 USD bei ~65 USD). Das Audit scannt
  {0,11 / 0,115 / 0,12}; arretierter Default nach Audit-Abnahme.
- **Basis-Preis = Mittel der akzeptierten Cluster-Dochte** (selbst-lokalisierende
  Linie; läuft mit jedem akzeptierten Touch deterministisch mit; kausal, kein
  Blick über Bar k). Kein Verankern an der ersten Spitze.
- Touch-Mindestabstand `min_bar_abstand = 3` (gleiche Bewegung zählt nicht
  doppelt).
- **Konsequenz Unterseite (E2, institutionelle Staffelung):** Die Unterkante
  der Box besteht aus **zwei versetzten Ebenen** — 63.62 (Tiefs 10.08.) und
  63.70/63.79 (nach dem Bruch 14.08.). Das Audit bildet beide ab; die
  Soll-Zählung 7/7 (Main) ist die menschliche Zonen-Zählung um 63.67 ±0,15.

**3. Regel 2 — Begrenzungs-Hierarchie (`RANGE_AUSSENGRENZE` vs. `ZWISCHEN_LEVEL`):**

- Jede Kante trägt eine Rolle. **Handelbar für Reclaim-Einstiege ist
  ausschließlich die äußerste aktive Kante der Seite in der aktuellen
  Balance-Phase** (OBEN: höchste aktive OBEN-Basis; UNTEN: tiefste aktive
  UNTEN-Basis). Alle inneren Zwischenlevels (z. B. Minor 64.20/64.22 als
  Kursziel ja, als Einstieg nein) sind **vollständig stummgeschaltet**.
- **Zwei-Linien-Modell Minor (E1, voll freigegeben):** Die Minor-Zone wird als
  **zwei** UNTEN-Linien abgebildet — **dominant 64.22** (Dochte 126/316/320/361,
  = Soll-Minor 4/4) und **Junior 64.31** (130/162/368). Junior wird per
  Regel 2 als `ZWISCHEN_LEVEL` markiert und für Einstiege stummgeschaltet —
  Abbild der realen Orderbuch-Staffelung, ohne Dochte künstlich zu verleugnen.
- Dominanz/Tie-Break bei Überlappung bleibt U1 (höchste `touch_anzahl`, bei
  Gleichstand das äußere Extremum).

**4. Regel 3 — Echter Volumen-Histogramm-POC als TP1 (Baseline v0.4.0):**

- **Nachweis (Referenz `scripts/phasen_volumen_profil.py` Z. 477–605):** Die
  Baseline v0.4.0 kannte **keinen Kanten-VWAP**. `build_volume_profile` zerlegt
  die Spanne in `NUM_BINS = 60` Preis-Bins, verteilt `tick_volume` proportional
  über die High-Low-Spanne, glättet mit `smooth_vol(win=3)` und bestimmt
  `POC = peaks[0].poc` des dominanten Bergs (`MIN_MOUNTAIN_PCT 4,0`,
  `VALLEY_REL 0,15`).
- Der synthetische Kanten-VWAP `(bal·v_ein + gegen·v_geg) / v_sum` aus dem
  Harness (Modi A/B) **entfällt** für Modus C.
- **Kausales Histogramm-Fenster (E3, Option A+C kombiniert):** TP1 = POC des
  60-Bin-Volumenprofils über **alle Bars seit Beginn der aktuellen
  Balance-Phase bis zur Entscheidungs-Bar k**, **begrenzt auf den Preisraum
  zwischen Einstiegskante und Zielkante**. Kein Blick über Bar k hinaus.
- TP2 = äußere Gegenkante; Split **50/50** (arretiert).

**5. Scope AUG (E4):**

- **Eichmaßstab = Box-Phase 10.08.–18.08.** (dort liegen die 3 Soll-Kanten und
  die erwarteten 6–9 echten Range-Reclaim-Setups).
- Nach dem **Makro-Bruch am 19.08.** (Regimewechsel Richtung ~70 USD) muss die
  Engine durch den 2-Body-Schutz **sauber schlafen gehen** und **keine
  Fehlsignale** im neuen Regime erzeugen (Verifikation sekundär).

**6. Freigabe & Reihenfolge (E5):**

- Diese Arretierung ist der verbindliche Anhang des Übergabedokuments.
- **Schritt A (vorliegend):** Spezifikations-Update (U2-Revokation, §7.2).
- **Schritt B:** Read-Only-Audit `test/tmp_v3_straight_edge_audit.py` — kausaler
  AUG-Scan zum Nachweis, dass die 39 Kanten auf die institutionellen
  Begrenzungslinien kollabieren (Upper ~66.42/66.46; Unterkante Staffelung
  63.62/63.70–63.79; Minor dominant 64.22 + Junior 64.31) und die Trade-Zahl in
  der Box auf ca. 6–9 echte Range-Setups schrumpft (mit PNG).
- **Schritt C:** Erst nach formaler Abnahme der Audit-Ergebnisse erfolgt der
  Umbau von `_replay_c` im Harness.

**Datenvertrag Straight-Edge (arretiert):**

```python
from dataclasses import dataclass, field
from typing import List, Literal
import pandas as pd

KantenSeite = Literal["OBEN", "UNTEN"]
KantenRolle = Literal["RANGE_AUSSENGRENZE", "ZWISCHEN_LEVEL"]


@dataclass(slots=True)
class StraightEdgeKante:
    kanten_id: int
    seite: KantenSeite
    basis_preis: float                    # Fester horizontaler Preisanker
    geburts_bar: int
    touch_bars: List[int] = field(default_factory=list)
    rolle: KantenRolle = "ZWISCHEN_LEVEL"
    status: Literal["AKTIV", "SCHLAFEND"] = "AKTIV"

    @property
    def touch_anzahl(self) -> int:
        return len(self.touch_bars)

    @property
    def ist_aktive_aussengrenze(self) -> bool:
        """Handelsberechtigt für Reclaim-Einstiege nur reife Außenwände."""
        return (
            self.rolle == "RANGE_AUSSENGRENZE"
            and self.touch_anzahl >= 3
            and self.status == "AKTIV"
        )


@dataclass(frozen=True, slots=True)
class HistogrammPocPlan:
    poc_preis: float
    spanne_von: float
    spanne_bis: float
    anzahl_bars: int
    gesamt_volumen: float
```

**Nachtrag (Sweep-Immunität / Anti-Spike-Filter, arretiert 2026-09-08):**

> **Kernregel (bindend):** **Dochtspitzen von Reclaims bilden NIEMALS eine neue
> Linie.** Ein Reclaim-Docht jenseits einer aktiven Range-Grenze ist ein
> Überdehnungs-Phänomen (Failed Breakout / Liquidity-Sweep) der **existierenden**
> Kante und darf nicht als Basis für ein neues Preislevel missbraucht werden.
> Smart Money lässt den Preis gezielt 20–30 Cents über die verteidigte Decke
> schießen (Stop-Run), um Buy-Stops abzufischen; fällt der Kurs zurück, ist die
> Decke **bestätigt** — keine Range-Verlagerung, keine Phantom-Linie.

**Falsifikations-Befund (Datenverifikation M15, Wanduhr):**

Am 12.08. stach der Markt zweimal über die 66,46-Decke (Bar 107 H 66.459,
Close 66.311 — level-definierender Test, **kein** Reclaim):

- **Bar 229** (11:15) H **66.776**, C 66.471 (noch über der Decke) → Reclaim
  erst in **Bar 230** (C 66.419). Überdehnung +0,478 % über Seed 107.
- **Bar 242** (14:30) H **66.663**, L 65.598 (F1-Doppel-Pivot), C 66.480;
  **Bar 243** bildet das zweite Top (H **66.528**), **Bar 244** (H **66.662**,
  nur +0.001 USD unter dem Sweep-Extrem 66.663) bricht mit
  C 66.090 zurück = **M15-Doppeltop-Fakeout über 3 Kerzen** (Distribution über
  30–45 min).

Der Algorithmus hatte diese Dochtspitzen als eigenständige Linien gespeichert
(**K33** Seed 229 / basis 66.776, später via 777/781 am 20.08 gekeimt; **K36**
Seed 242 / basis 66.663). **K33 und K36 entfallen ersatzlos** — die
Soll-Zonen-Abdeckung (UPPER 5/5, MAIN 7/7, MIN-D 4/4 bei Band 0.12) hängt
nicht an ihnen.

**Drei IDE-Lücken-Korrekturen (arretiert):**

1. **Lücke A — Reclaim-Grace-Fenster:** `reclaim_grace_bars = 2`. Ein starrer
   In-Bar-Schluss (`close[k] ≤ grenze`) versagt: Bar 229/242 schlossen beide
   noch oberhalb (66.471/66.480). Der Reclaim zählt, wenn **k, k+1 ODER k+2**
   zurück jenseits der Referenz schließt (Verteilungsprozess dauert 2–3 Kerzen).
2. **Lücke B — Referenz-Universum inkl. Singleton-Seeds:**
   `referenz_modus = "inkl_seeds"`. Bei Bar 229/242 existiert die 66,46-Decke
   erst als **Singleton-Seed** (Bar 107, Keimung erst mit Bar 529). Ein Filter
   nur auf gekeimte Kanten wäre blind (äußerste OBEN-Referenz wäre 66.046 →
   Bar 229 läge +1,10 % → kein Sweep → K33 entstünde trotzdem). Referenz ist
   die **äußerste gespeicherte Linie der Seite inkl. Seeds** (Orderbuch-Anker
   ab Bar 107).
3. **Lücke C — In-Band-Vorrang:** Ein Docht im regulären
   `touch_band_pct`-Band (0,12 %) ist **primär regulärer Touch/Reclaim-
   Kandidat**, nie Sweep-Sperre (sonst bräche man Soll-Touches und Trigger,
   z. B. Bar 565 H 66.536 vs. K23-Basis 66.499 = +0,056 %).

**Arretierter Gültigkeitskorridor der Überdehnung:** `max_sweep_ueberdehnung_pct
= 0,60 %` — gültig für den Korridor **[0,478; 0,625] %** (Bar 229 +0,478 % muss
als Sweep erkannt werden; Bar 107 +0,356 % über Seed 101/66.223 bleibt
No-Reclaim = regulärer Decken-Test). Werte unter 0,478 % ließen K33 entstehen,
Werte über 0,625 % könnten echte Trendausbrüche verschlucken.

**Weitere Arretierungen (Schritt-A-Übergabe):**

- **`touch_band_pct = 0.12`** (arretierter Default; einzige Band-Stufe des
  Schritt-B-Audits mit UPPER 5/5, MAIN 7/7, MIN-D 4/4). Als Parameter für
  spätere Sweet-Spot-Sweeps vorbereitet.
- **Reife-Schwelle strikt V-S (`min_touches_handelbar = 3`).** Keine Aufweichung
  auf V-2 als Default (V-2 bleibt nur Sensitivitäts-Diagnose: im Audit 7
  Box-Setups vs. 3–4 bei V-S — die Frühtrades 22/60/223 wären Phantom-Früh-
  Struktur an unreifen Außenlinien).
- **Minor-Linie:** Freie Keimung akzeptiert — dominant ~64.21
  ({126,316,361,406}), Junior ~64.33 ({130,162,172,320,346,368,372}). Junior
  bleibt gemäß Regel 2 `ZWISCHEN_LEVEL` und für Reclaim-Einstiege
  **vollständig stumm** (Kursziel ja, Einstieg nein).
- **Kanten-Inflation Niemandsland (70 Audit-Kanten):** Vorerst elegant über
  Regel 2 (`RANGE_AUSSENGRENZE` — nur die äußerste Linie handelt Einstiege)
  gelöst. Ein ordentlicher Distanz-/Makro-Schwung-Filter gegen
  Niemandsland-Kanten ist der **nächste Baustein nach Schritt C** (explizit
  offen, blockiert nicht).
- **Kausalität:** Sweep-Sperre strikt kausal (Daten bis k+2 — kein Blick über
  den Reclaim-Grace-Horizont hinaus); Histogramm-POC wie §7.2 Regel 3
  (60 Bins, Balance-Beginn bis k, Preisraum Einstiegskante→Gegenkante).

**Scope (E4):** In der Box greift die Sweep-Regel OBEN-seitig (Bars 229/242).
UNTEN-seitig liegt die äußerste Referenz beim transienten Crash-Seed 62.967
(Bar 14) — kein Box-Docht unterschreitet sie; Soll-Lower-Touches (30–386) und
die Staffelung K6/K10 bleiben unberührt. Post-Box (20.08) können 777/781 als
**frisches Innen-Level** unter der 20.08-Spitze neu entstehen (post-box
sekundär, E4).

**Datenvertrag Sweep-Immunität (arretiert):**

```python
from dataclasses import dataclass
from typing import List, Literal
import pandas as pd

KantenSeite = Literal["OBEN", "UNTEN"]


@dataclass(frozen=True, slots=True)
class SweepImmunitaetKonfiguration:
    touch_band_pct: float = 0.12               # In-Band-Toleranz (Vorrang)
    max_sweep_ueberdehnung_pct: float = 0.60   # Korridor [0.478; 0.625] %
    reclaim_grace_bars: int = 2                # Reclaim-Schluss k, k+1 ODER k+2
    referenz_modus: Literal["inkl_seeds", "nur_gekeimte"] = "inkl_seeds"


def ist_sweep_einer_bestehenden_referenz(
    seite: KantenSeite,
    bar_k: int,
    pivot_preis: float,
    cl: List[float],
    aeusserste_referenz_basis: float,
    cfg: SweepImmunitaetKonfiguration,
) -> bool:
    """Kausal: Docht außerhalb des Touch-Bands, aber innerhalb der
    Sweep-Toleranz; Reclaim-Schluss innerhalb k..k+2 zurück jenseits."""
    basis: float = aeusserste_referenz_basis
    # 1. In-Band-Vorrang: normales Touch-Band -> KEIN Sweep-Sperrfall
    dist_pct: float = abs(pivot_preis - basis) / basis * 100.0
    if dist_pct <= cfg.touch_band_pct:
        return False
    # 2. Überdehnung gegen die äußerste Referenz (inkl. Seeds)
    if seite == "OBEN":
        if not (pivot_preis > basis
                and dist_pct <= cfg.max_sweep_ueberdehnung_pct):
            return False
        for step in range(cfg.reclaim_grace_bars + 1):
            target_bar: int = bar_k + step
            if target_bar < len(cl) and cl[target_bar] <= basis:
                return True
    else:
        if not (pivot_preis < basis
                and dist_pct <= cfg.max_sweep_ueberdehnung_pct):
            return False
        for step in range(cfg.reclaim_grace_bars + 1):
            target_bar: int = bar_k + step
            if target_bar < len(cl) and cl[target_bar] >= basis:
                return True
    return False
```

**Freigabe-Reihenfolge (aktualisiert, Stand nach Schritt C + Sichtpruefung):**
Schritt A = Docs-Only-Commit (Sweep-Immunitaet, arretiert). Schritt B/C wurden
ausgefuehrt (SE-Harness `--modus C`, `test/tmp_kanten_engine_replay.py`); die
Sichtpruefung des AUG-PNG fuehrte zu diesem Nachtrag (dreistufige
Reclaim-Hierarchie). Verbindlich ab hier ist der folgende Abschnitt.

---

### Nachtrag 2026-09-08 (Dreistufige Reclaim-Hierarchie & Sweep-Immunitaet,
arretiert nach Sichtpruefung des AUG-Harness-Laufs)

> **DOKUMENTATION: DREISTUFIGE RECLAIM-HIERARCHIE & SWEEP-IMMUNITÄT (MODUS C / V3)**

**1. Primär-Anker & Unverrückbare Grundlinie:**

- Die Oberkante bei **66,459 USD** wird kausal am **11.08. um 03:45 Uhr
  (Bar 107)** als höchster Peak eroeffnet. Sie steht ab diesem Zeitpunkt als
  feste geometrische Grundlinie im Speicher.
- Nachfolgende Spitzen (wie Bar 229 bei 66,776 USD oder Bar 242 bei
  66,663 USD) verschieben oder mitteln diese Grundlinie **nicht**. Sie sind
  temporäre Liquiditäts-Sweeps (False Breakouts).

**2. Dreistufige Reclaim-Hierarchie (Timing & Execution):**

- **Stufe 1 — In-Bar (`STUFE_1_IN_BAR`):**
  - *Bedingung:* Bar *k* sticht über/unter die Basis und schliesst in
    derselben Kerze zurück (`Close <= Basis` bei OBEN bzw.
    `Close >= Basis` bei UNTEN).
  - *Execution:* Entry am Open von Bar *k+1*.
- **Stufe 2 — Kerze 2 (`STUFE_2_KERZE_2`):**
  - *Bedingung:* Bar *k* sticht durch und schliesst ausserhalb; Bar *k+1*
    expandiert nicht weiter und schliesst zurück jenseits der Basis
    (`Close <= Basis` bei OBEN).
  - *Execution:* Entry am Open von Bar *k+2* (z. B. Sweep Bar 229 → Reclaim
    Bar 230 → Entry Open Bar 231).
- **Stufe 3 — Kerze 3 (`STUFE_3_KERZE_3` / Linienläufer & Doppeltops):**
  - *Bedingung:* Bar *k+1* verharrt knapp jenseits der Linie, aber Bar *k+2*
    vollendet den Reclaim-Schluss (`Close <= Basis` bei OBEN), ohne dass das
    Sweep-Extremum von Bar *k* überboten wurde.
  - *Execution:* Entry am Open von Bar *k+3* (z. B. Sweep Bar 242 →
    Zwischenbar 243 → Reclaim Bar 244 → Entry Open Bar 245).
- *Audit-Status:* Stufe 3 ist als temporäre Option aktiv und wird in
  späteren Out-of-Sample-Läufen (S1/S2) isoliert auf Entbehrlichkeit geprüft.

**3. Automatische Sweep-Immunität (Anti-Spike-Garantie):**

- Jeder Docht, der über Stufe 1, Stufe 2 oder Stufe 3 zu einem Reclaim
  führt, wird als Sweep der bestehenden Basis markiert.
- Seine Dochtspitze ist für Kanten-Neugeburten **kategorisch gesperrt**.
  K33 und K36 entfallen ersatzlos.

**4. Stop-Loss & Kursziele:**

- **Stop-Loss:** strukturell am Extremum des Sweep-Docht-Clusters
  ± 0,05 USD. (Auch bei weiterem Sweep wie Bar 242 voll zulässig, da das
  Chance-Risiko-Verhältnis > 2:1 bleibt.)
- **TP1:** kausaler Binned-Histogramm-POC (60 Bins, `t <= SignalBar`)
  zwischen Einstiegskante und Gegenkante (50 % Split).
- **TP2:** äussere Gegenkante (50 % Split; Status AKTIV oder SCHLAFEND
  zulässig, sofern >= 2 Touches und >= 1,5 % Distanz).

**Datenvertrag Reclaim-Trigger (arretiert, Ausweisung im Trade-Report):**

```python
KantenSeite = Literal["OBEN", "UNTEN"]
KantenRolle = Literal["RANGE_AUSSENGRENZE", "ZWISCHEN_LEVEL"]
ReclaimStufe = Literal["STUFE_1_IN_BAR", "STUFE_2_KERZE_2",
                      "STUFE_3_KERZE_3"]

@dataclass(frozen=True, slots=True)
class ReclaimTriggerKonfiguration:
    basis_preis: float              # Unverrückbare Grundlinie (66.459 ab Bar 107)
    seite: KantenSeite
    sl_buffer_usd: float = 0.05
    max_ueberdehnung_pct: float = 0.60   # Sweep-Schranke jenseits der Basis
    touch_band_pct: float = 0.12         # In-Band-Vorrang

@dataclass(frozen=True, slots=True)
class ReclaimSignalEvent:
    signal_bar: int                 # Bar des Reclaim-Schlusses
    sweep_bar: int                  # Ursprünglicher Durchstich-Bar k
    entry_bar: int                  # Ausführungs-Bar (signal_bar + 1)
    entry_preis: float              # Open des Folge-Bars
    stop_loss: float                # Sweep-Extremum +/- sl_buffer_usd
    tp1_poc: float                  # Kausales Binned-Histogramm (60 Bins)
    tp2_kante: float                # Äussere Gegenkante
    stufe: ReclaimStufe             # STUFE_1 / STUFE_2 / STUFE_3
    is_sweep_gesperrt: bool = True  # Sweep-Immunität für diesen Docht
```

**Ausweisung (Frage 1):** Jeder Trade im Report und Datenvertrag führt die
Reclaim-Stufe transparent (`STUFE_1_IN_BAR` an Open *k+1*,
`STUFE_2_KERZE_2` an Open *k+2*, `STUFE_3_KERZE_3` an Open *k+3*).

**Sweep-Immunität über alle Stufen (Frage 2):** Jeder Docht, der über eine
der drei Stufen einen Reclaim vollendet, aktiviert die Sweep-Sperre; seine
Dochtspitze ist für die Neugeburt von Kanten gesperrt (Anti-Spike-Garantie).

---

### Nachtrag 2026-09-09 (Block 2/3 & M6: Retest-Zyklus, Aussenquartil,
Innenlevel-Blocker — arretiert)

> **Status:** Arretiert nach Mentoren-Freigabe B23-1…B23-6 (Block 2/3) und
> F1–F4 (M6). Messbasis: AUG-Lauf `--modus C` auf
> `test/tmp_kanten_engine_replay.py`. Vorher 6 Trades / +21,13 R (mit
> unberechtigtem SHORT 223), nachher **5 Trades / +23,13 R**
> (Ablehnungen: Blocker=3, Zyklus=4, Quartil=20).
>
> **TEILWEISE SUPERSEDED (2026-09-09, Teil 3):** Die M0-Arretierung
> `retest_zyklus_bars = 24` und die Hilfsentscheidung **F1/Option A** sind
> durch den Nachtrag "Teil 3" revoziert (neuer Wert **12**, Zyklus-Zaehler
> **3**). Die uebrigen Arretierungen dieses Nachtrags (M2, M6, B23-3/4/5,
> M1/M1b) bleiben unveraendert gueltig. Die Kennzahlen dieses Abschnitts
> bleiben als **Phase 1** historisch stehen (H3-Transparenzgebot).

**Ausgangsbefund (Anlass der Arretierung):** Der SHORT 223 an der Innenkante
K15 (66,046) war unberechtigt — der Markt stach nur bis 66,146 (+0,151 %) und
schloss 0,010 USD unter der Basis, waehrend die kausal seit Bar 109
existierende Aussenwand K20 (66,459) unerreicht blieb. Ein Fade im Schatten
einer intakten Aussenwand ist institutionell unbegruendet (kein Liquidity-Sweep
der verteidigten Decke). Ferner zaehlte der Algo 229 faelschlich als 3. Touch
(Events @229 = {107, 228}; der 3. Kontakt folgt erst @242), und der
Retest-Zyklus war nur unvollstaendig abgebildet.

**Arretierte Parameter (Block 2/3 & M6):**

| Kennung | Parameter | Wert | Regel / Begruendung |
|---|---|---|---|
| M0 | `retest_zyklus_bars` | ~~**24** (6 h)~~ → **12** (3 h), revoziert in Teil 3 | Ersetzt Q8/F2-Vollrisiko: dieselbe Kante ist nach einem genommenen Sweep erst nach einem neuen Liquiditaetszyklus wieder handelbar. Gueltiger Wertebereich siehe Teil 3 (Plateau `[3; 15]`). |
| M2 | `quartil_distanz_pct` | **25,0** (Prozent-Konvention, nicht 0,25) | Q29 Niemandsland-Sperre: nur das aeussere Quartil der kausalen Spanne 0…k handelt. |
| M6 | `max_seed_distanz_pct` | **0,75** (wiederverwendet) | Schlagdistanz des Innenlevel-Blockers (Q9b-Sicherheitsnetz, unveraendert). |
| M6 | Blocker-Quelle | nur `_existiert`-Linien (AKTIV) | F3: schlafende/dormante Linien sperren nicht. |
| B23-4 | `max_schwung_bars` | **ersatzlos entfallen** | Der Zyklus (M0) uebernimmt die Sperre; kein zweiter, paralleler Zeitparameter. |

**1. M0 — Retest-Zyklus ersetzt Q8/F2 (`retest_zyklus_bars = 24` → 12,
revoziert in Teil 3):** Nach
einem genommenen Trade an Kante X gilt `k - kd.letzter_sweep_bar < 12` als
Zyklus-Sperre (kein Vollrisiko-Re-Trigger im selben Liquiditaetszyklus).
Fortschreibung **nur bei tatsaechlich genommenem Trade** (B23-5) — ein
abgewiesener Kontakt setzt die Uhr nicht zurueck.

**2. M1/M1b — Kausalitaets-Haertung:** `_gegenkante` nutzt dieselbe
Existenz-Semantik wie `_kandidat` (`erster_pivot_bar + 2 <= k + 1`), bewusst
ohne AKTIV-Gate (Q5/Q14: schlafende Gegenkanten erlaubt), mit
Anker-Ausnahme. M1b: `ist_prim_anker` wirkt erst ab `promoviert_ab_bar` —
kein Lookahead durch einen noch nicht promovierten Anker.

**3. M2 — Aussenquartil-Sperre (Q29):** Distanz des Sweep-Extremums zum
laufenden kausalen Range-Extrem `0…k`, normiert auf die Spanne;
handelbar nur `<= 25 %`. Sperrt Fades mitten in der Range (Niemandsland).

**4. M3 — Dedup je Entry-Bar (B23-3):** `getradete_entry_bars` verhindert
Doppel-Trades auf derselben Ausfuehrungs-Bar.

**5. M4 — Report-Ausweisung:** Eigene Sektionen fuer Zyklus-, Quartil- und
Blocker-Sperren; `Ablehnungen:` fuehrt `Blocker`, `Zyklus`, `Quartil`.

**6. M6 — Innenlevel-Blocker (F1–F4):** Blocker ist die **aeusserste
existierende** Linie derselben Seite, die vom Sweep-Extremum **nicht erreicht**
wurde und deren Abstand zur Kandidatenbasis `<= 0,75 %` ist. Entscheidend ist
die aeusserste Linie: eine naehere Innenlinie darf die Sperre nicht ausloesen,
wenn die Aussenwand selbst erreicht wurde (sonst wuerde der Kern-Gewinner
LONG 398 an K5 eliminiert). Basis ist kausal `basis_bei(k)`, **nicht** der
Report-End-Mittelwert. ~~**F1 = Option A:** die E3-Stufe (Bar 245) wird
zurueckgenommen — sie kollidiert mit der Pivot-Zaehlung E2 und mit M0
(244 − 229 = 15 < 24).~~ **F1/Option A ist vollstaendig revoziert (Teil 3,
2026-09-09):** Die E3-Stufe (Bar 245) ist mit `retest_zyklus_bars = 12`
zugelassen; die damalige Begruendung entfaellt, weil die Kollision
ausschliesslich gegen den alten M0-Wert 24 bestand. **F2** =
`max_seed_distanz_pct = 0,75` wiederverwendet. **F3** = nur
`_existiert`-Linien sperren. **F4** = Go fuer den Einbau.

**Verifikation (AUG, Modus C, Phase 1 mit `retest_zyklus_bars = 24`):**
5 Trades / +23,13 R — SHORT 229 (+6,92),
LONG 398 (+5,66), SHORT 529 (+8,41), SHORT 564 (+3,14), LONG 639 (−1,00).
Phase 2 (`retest_zyklus_bars = 12`): 6 Trades / +27,08 R, Zyklus=3 (Teil 3).
Blocker-Sperren: 223/224/225 (K15 → unerreichte Wand K20 66,459).
`test/tmp_v3_straight_edge_harness_AUG.txt`,
`test/kanten_engine_trades_AUG_mC.png`.

**Datenvertrag Block 2/3 & M6 (arretiert):**

```python
from dataclasses import dataclass
from typing import Literal, Optional
import numpy as np

SignalRichtung = Literal["SHORT", "LONG"]
KantenSeite = Literal["OBEN", "UNTEN"]


@dataclass(frozen=True, slots=True)
class Block23Konfiguration:
    retest_zyklus_bars: int = 24          # M0: neuer Liquiditaetszyklus (6 h)
    quartil_distanz_pct: float = 25.0     # M2: nur aeusseres Quartil handelt
    max_seed_distanz_pct: float = 0.75    # M6: Schlagdistanz Innenlevel-Blocker


def im_aussenquartil(richtung: SignalRichtung, k: int, sweep_px: float,
                     hi: np.ndarray, lo: np.ndarray,
                     cfg: Block23Konfiguration) -> bool:
    """M2/Q29: Einstieg nur an der aeusseren lebenden Wand (kausale Spanne 0..k)."""
    ex_hi = float(np.max(hi[:k + 1]))
    ex_lo = float(np.min(lo[:k + 1]))
    spanne = ex_hi - ex_lo
    if spanne <= 0.0:
        return True
    distanz = ((ex_hi - sweep_px) if richtung == "SHORT"
               else (sweep_px - ex_lo)) / spanne * 100.0
    return distanz <= cfg.quartil_distanz_pct


def blockiert_durch_aussenkante(richtung: SignalRichtung, k: int,
                                basis_k: float, sweep_px: float,
                                seite_edges: dict[KantenSeite, list],
                                existiert, cfg: Block23Konfiguration):
    """M6: Blocker = AEUSSERSTE _existiert-Linie jenseits des Sweeps (<= 0.75 %)."""
    seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
    aussen: Optional[object] = None
    for e in seite_edges[seite]:
        if not existiert(e, k):
            continue
        b = e.basis_bei(k)
        if seite == "OBEN":
            if b <= sweep_px:
                continue                      # erreicht -> kein Blocker
            if aussen is None or b > aussen.basis_bei(k):
                aussen = e
        else:
            if b >= sweep_px:
                continue
            if aussen is None or b < aussen.basis_bei(k):
                aussen = e
    if aussen is None:
        return None
    b = aussen.basis_bei(k)
    dist = ((b - basis_k) if seite == "OBEN" else (basis_k - b)) / basis_k * 100.0
    return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None
```

---

### Nachtrag 2026-09-09 (Teil 2) — Institutionelle Re-Test-Sequenz 229 → 242/244

> **Status:** Mentor-Freigabe 2026-09-09: **Bar 245 wird als eigenstaendiger
> zweiter Trade an K20 zugelassen** (Regelpraezisierung). Die Absenkung
> `retest_zyklus_bars` 24 → 12 ist **nicht arretiert**, sondern als
> **Parameter-Reihentest** vorgemerkt (Pruefhypothese). Kein Code-Eingriff vor
> Abschluss der Parameterreihe auf S1/S2.
>
> **AKTUALISIERT (2026-09-09, Teil 3):** Der Reihentest ist auf AUG
> abgeschlossen; `retest_zyklus_bars = 12` ist als **AUG-arretierter
> Arbeitswert unter S1/S2-Vorbehalt** gesetzt (Plateau `[3; 15]`). Die
> Curve-Fitting-Warnung in Punkt 4 bleibt inhaltlich bestehen — der
> S1/S2-Vorbehalt ist wegen des Alt-C-Routing-Blockers derzeit nicht
> messbar (siehe Teil 3, Abschnitt 9).

**1. Die Sequenz (M15-Rohdaten, Wanduhr, verifiziert):**

| Bar | Zeit (12.08.) | O | H | L | C | Ereignis |
|---|---|---|---|---|---|---|
| 229 | 11:15 | 66,509 | **66,776** | 66,462 | 66,471 | 1. Sweep ueber K20 (66,459); Close noch > Basis |
| 230 | 11:30 | 66,470 | 66,510 | 66,410 | **66,419** | Reclaim (Stufe 2) → Entry `open[231]` |
| 231 | 11:45 | **66,424** | 66,472 | 66,319 | 66,394 | Einstieg; SL 66,826 (= 66,776 + 0,05) |
| 232–241 | — | — | — | — | — | Rueckgang, **ohne** TP1/POC 63,676 zu erreichen |
| 242 | 14:30 | 66,425 | **66,663** | **65,598** | 66,480 | 2. Sweep (+0,307 %); tiefstes Low des Zwischenlaufs |
| 243 | 14:45 | 66,483 | 66,528 | 66,146 | 66,523 | Non-Expansion (66,528 ≤ 66,663 + 0,01) |
| 244 | 15:00 | 66,525 | 66,662 | 66,053 | **66,090** | **Reclaim-Close 0,369 USD unter der Basis** |
| 245 | 15:15 | **66,092** | 66,251 | 65,783 | 65,902 | Einstieg (freigegeben) |

**2. Warum Bar 245 ein eigenstaendiges Setup ist (kein Duplikat):**

- Der Abstand betraegt **13 Bars = 3 h 15 min** — der Markt hat die Decke nach
  einem vollstaendigen Zwischenzyklus erneut getestet.
- Der erste Reclaim (Bar 230) schloss nur **0,040 USD** unter der Basis
  (66,419) — kaum Rueckeroberung. Der zweite (Bar 244) schloss **0,369 USD**
  unter der Basis (66,090) — deutlich ueberzeugender. Die zweite Ausloesung ist
  damit der aussagekraeftigere Test der Decke.
- **Entscheidend:** TP1/POC 63,676 wurde erst in **Bar 386** erreicht. Bei
  Bar 245 lief die 229er-Position also **noch im Vollrisiko** — die
  De-Risk-Bedingung der frueheren F2/Q11-Regel war **nicht** erfuellt. Die
  M0-Zyklus-Sperre (24) blockiert folglich ein Setup, das nach der
  De-Risk-Semantik zulaessig gewesen waere.

**3. Kennzahlen des freigegebenen Trades (read-only gemessen):**

| | Trade 229 | Trade 245 |
|---|---|---|
| Kante | K20 (66,459) | K20 (66,459) |
| Entry | `open[231]` = 66,424 | `open[245]` = 66,092 |
| SL (Cluster-Extrem + 0,05) | 66,826 (Extrem 66,776) | 66,713 (Extrem 66,663) |
| Risiko | 0,402 USD | 0,621 USD |
| TP1 / TP2 | 63,676 / 63,605 | 63,676 / 63,605 (identisch) |
| Ergebnis | +6,92 R | **+3,95 R** |

Hinweis zum Risiko-Unterschied: Der SL folgt dem jeweiligen Sweep-Cluster
(66,776 vs. 66,663, Q6/Q10), der Entry liegt 0,332 USD tiefer — daraus
resultiert der um 54 % groessere Risikoabstand. Die Gegenkante ist in beiden
Faellen identisch.

**4. Parameter-Reihentest (Phase 1; ueberholt durch Teil 3):**

Read-only gemessen (AUG, Modus C, je Variante frischer Scan — der Scan mutiert
`letzter_sweep_bar`, ein geteilter Scan verfaelscht das Ergebnis):

| `retest_zyklus_bars` | Trades | Summe R | Zyklus-Sperren | K20-Trades |
|---|---|---|---|---|
| **24 (Status quo)** | 5 | +23,13 | 4 | [231] |
| 20 | 5 | +23,13 | 4 | [231] |
| 16 | 5 | +23,13 | 4 | [231] |
| **12 (AUG-arretiert, Teil 3)** | 6 | **+27,08** | 3 | [231, **245**] |
| 8 | 6 | +27,08 | 3 | [231, 245] |
| 4 | 6 | +27,08 | 3 | [231, 245] |
| 0 | 7 | +26,08 | 0 | [231, 245] |

- Die Schwelle zwischen „245 gesperrt" und „245 frei" liegt **zwischen 13 und
  14 Bars** (Signal-Bar 242 wird ab `v >= 14` gesperrt; bei `v = 13` feuert
  Bar 242 noch). Exakte Grenzkarte `0…24` in Teil 3.
- Bei `0` entsteht zusaetzlich ein **toxischer Trade** (Sweep 531 → Entry 533
  an K31, −1,00 R, nur 2 Bars nach dem 529er-Sweep) → die Sperre darf **nicht
  ersatzlos entfallen**. Exakt: toxisch fuer `v <= 2`, eliminiert ab `v >= 3`.
- **Curve-Fitting-Warnung (BESTEHT FORT):** Diese Zahlen sind auf AUG
  gemessen. Eine Arretierung von 12 allein auf AUG-Basis waere Optimierung auf
  ein einzelnes Fenster. Der Reihentest (12/16/20/24) ist **auf S1 und S2** zu
  wiederholen. Teil 3 setzt 12 daher ausdruecklich als **Arbeitswert unter
  S1/S2-Vorbehalt**; die Bestaetigung ist nach Behebung des Routing-Blockers
  (S1/S2 laufen derzeit im Alt-C ohne SE-Zaehler) nachzuholen.
- Zu pruefen bleibt, ob die M0-Sperre besser durch die **De-Risk-Semantik**
  (F2/Q11: Re-Trigger nur ohne offene Position ODER nach TP1) ersetzt wird —
  sie bildet den institutionellen Sachverhalt genauer ab als ein starrer
  Bar-Zaehler.

**Datenvertrag (vorgemerkt):**

```python
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True, slots=True)
class RetestParameterReihe:
    kandidaten_zyklus_bars: List[int] = field(
        default_factory=lambda: [12, 16, 20, 24])
    standard_zyklus_bars: int = 12        # AUG-arretiert (Teil 3); vorher 24
    test_zyklus_bars: int = 12            # freigegeben fuer Bar 245
    plateau_grenzen_bars: Tuple[int, int] = (3, 15)   # GATE-FREI (§7.2 Teil 4)
    # REVOZIERT in §7.2 Teil 4 (Befund A): Stacking-Verbot §7.1 B ist verbindlich.
    erlaube_parallele_exposition: bool = False
```

### Nachtrag 2026-09-09 (Teil 3) — Plateau-Analyse & Arretierung des Re-Test-Zyklus auf 12 Bars

> **Status:** **AUG-ARRETIERTER ARBEITSWERT UNTER S1/S2-VORBEHALT.**
> Mentor-Freigabe 2026-09-09 (H1–H6): `retest_zyklus_bars` 24 → **12**
> (3,0 Stunden = halbe Handelssitzung). F1/Option A **vollstaendig revoziert**.
> Messbasis: AUG-Lauf `--modus C` auf `test/tmp_kanten_engine_replay.py`,
> read-only Grenzkarte `v = 0…24`, je Variante frischer `_se_scan` (der Scan
> mutiert `letzter_sweep_bar`; ein geteilter Scan verfaelscht das Ergebnis).

**1. Anlass und Gegenstand:**

Der Reihentest aus Teil 2 ist auf AUG abgeschlossen. Gegenstand ist allein die
Wahl der Zyklus-Hoehe fuer `retest_zyklus_bars` — **nicht** die Re-Test-Sequenz
selbst (die bleibt wie in Teil 2 arretiert).

**2. Grenzkarte `retest_zyklus_bars` = 0…24 (AUG, Box-Loop 641, read-only):**

Der Scan ist ueber die gesamte Reihe invariant: `box_end = 644`,
`edges = 65` (OBEN 33/UNTEN 32), `seeds = 28`. Ebenfalls invariant ueber
**alle** Varianten: `Blocker = 3`, `Quartil = 20`, `F3 = 0`,
`kein_Gegner = 0`.

| `v`-Bereich | Trades | Netto-R | Zyklus-Sperren | K20-Setup | Verluste |
|---|---|---|---|---|---|
| **0–2** | 7 | +26,08 | 0–1 | Bar 242 | **2** (inkl. toxisch 531/533) |
| **3–13** | 6 | +27,08 | 3 | Bar 242 (`STUFE_3_KERZE_3`) | 1 |
| **14–15** | 6 | **+27,09** | 3 | Bar 244 (`STUFE_1_IN_BAR`) | 1 |
| **16–24** | 5 | +23,13 | 4 | keines | 1 |

**Distinkte Trade-Sets: 4.** Der einzige Unterschied zwischen den Varianten ist
genau ein Setup: `(bar 242, K20)` bzw. `(bar 244, K20)` — beide erzeugen
denselben Entry 245. (Die +0,01-R-Differenz bei `v = 14/15` stammt aus dem
SL-Cluster 66,712 statt 66,713.)

**3. Die drei exakten Schwellen (Korrektur gegenueber Teil 2):**

- **Untergrenze `v >= 3`:** Der toxische Trade (Sweep 531 → Entry 533 an K31,
  −1,00 R) existiert fuer `v <= 2` und ist ab `v >= 3` eliminiert. Bei `v = 2`
  sperrt die Regel nur Bar 530 (`Δ1 < 2`), nicht Bar 531 (`Δ2`).
- **Obergrenze `v <= 15`:** Das K20-Setup (Entry 245) feuert fuer `v <= 15` und
  ist ab `v >= 16` gesperrt. Bei `v = 16` faengt die Zyklus-Sperre den
  Signal-Bar 242 (`Δ13 < 16`).
- **Plateau: `[3; 15]`.** Innerhalb dieses Bereichs ist der Netto-Ertrag
  +27,08/+27,09 R bei 6 Trades konstant.

**Korrektur zu Teil 2:** Dort stand „Die Schwelle … liegt bei 12 Bars". Exakt
liegt sie **zwischen 13 und 14** (bei `v = 13` feuert Bar 242 noch). Die
toxische Untergrenze liegt exakt bei `v = 3`, nicht „unter 4".

**4. Pfad-Substitution (Praezisierung der Mechanik, H4):**

Entry 245 ist **doppelt verankert**, aber die beiden Pfade sind **gegenseitig
ausschliessend** — es handelt sich **nicht** um eine simultane
Dedup-Zusammenfuehrung:

| `v` | Bar 242 | Bar 244 | Ergebnis |
|---|---|---|---|
| 13 | feuert (`STUFE_3_KERZE_3`) | zyklus-gesperrt (Sweep 242, `Δ2 < 13`) | Entry 245 |
| 14–15 | zyklus-gesperrt (Sweep 229, `Δ13 < 14`) | feuert (`STUFE_1_IN_BAR`) | Entry 245 |

F3 (`k <= letzter_sweep_bar`) sperrt Bar 242 nicht selbst; bei `v = 13` bleibt
Bar 244 mit `Δ2` unterhalb der Sperre frei. Bei `v = 14` wird 242 gesperrt,
wodurch der Loop bis Bar 244 weiterlaeuft und dort ueber `STUFE_1_IN_BAR`
denselben Entry erzeugt. Das Dedup-Gate `getradete_entry_bars` (B23-3) bleibt
als generischer Sicherheitsgurt bestehen, wird hier aber **nicht** als
Begruendung herangezogen.

Institutionell ist das **robuster als ein Dedup**: Das
Reversal-Reclaim-Phaenomen ist ueber zwei unabhaengige Reclaim-Stufen
abgesichert und haengt nicht an einem Einzel-Bar.

**5. Institutionelle Begruendung des Zielwerts 12:**

- `v = 3` (45 min) waere Retail-Scalping — die Liquiditaet eines vorangegangenen
  Fehlausbruchs ist institutionell nicht absorbiert.
- `v = 15` (3 h 45 min) ist die Abbruchkante — eine Verzoegerung um einen
  einzigen M15-Bar kippt das Setup.
- **`v = 12` (3,0 Stunden)** entspricht einer halben Handelssitzung, liegt
  stabil im Plateau-Kern `[3; 15]` und gibt dem Markt Zeit, das vorherige Hoch
  zu verdauen, das Zwischen-Tief bei 65,598 USD (Bar 242) auszubilden und mit
  neuem Schwung die Decke anzutesten.

**6. Revokation F1/Option A (H1, vollstaendig und namentlich):**

> **F1/Option A wird vollumfaenglich revoziert.** Die fruehere
> Hilfsentscheidung — „die E3-Stufe (Bar 245) wird zurueckgenommen, sie
> kollidiert mit der Pivot-Zaehlung E2 und mit M0 (244 − 229 = 15 < 24)" —
> wird aufgehoben. **Die damalige Begruendung entfaellt durch die
> Neuarretierung des Re-Test-Zyklus auf 12 Bars:** Die Kollision bestand
> ausschliesslich gegen den alten M0-Wert 24. Die Pivot-Zaehlung E2 ist von
> der Zyklus-Hoehe unabhaengig und bleibt unberuehrt.

**7. Kennzahlen-Progression (H3, transparente Historie):**

| Stand | `retest_zyklus_bars` | Trades | Netto-R | Zyklus-Sperren | Verluste |
|---|---|---|---|---|---|
| **Phase 1** (Nachtrag Block 2/3 & M6) | 24 | 5 | +23,13 | 4 | 1 |
| **Phase 2** (dieser Nachtrag) | **12** | **6** | **+27,08** | **3** | 1 |

Die Phase-1-Werte bleiben im Dokument **erhalten** (Revisionssicherheit); sie
werden nicht ueberschrieben. Zusaetzlicher Trade in Phase 2: SHORT
`bar 242` → Entry 245, `STUFE_3_KERZE_3`, +3,95 R.

**8. Low-n-Transparenz (§8.2):**

`n = 6` entschiedene Trades in der Box ⇒ **PF nicht belastbar** (§8.2:
Warnung ab `n < 20`). Die Arretierung ist daher primaer eine
**Regelpraezisierung** (Zulassung der E3-Stufe), **kein** statistisch belegter
Edge. Eine Aussage ueber Erwartungswert oder Profit-Faktor ist daraus nicht
ableitbar.

**9. S1/S2-Vorbehalt (H2, ausdruecklich aufrechterhalten):**

Der in Teil 2 formulierte Vorbehalt bleibt **wortgleich bestehen** und wird
nicht wegdefiniert:

> Der Reihentest (12/16/20/24) ist **auf S1 und S2** zu wiederholen; erst
> danach Entscheidung.

Faktische Lage 2026-09-09: Die Messung auf S1/S2 ist **derzeit nicht
moeglich**. `main()` routet nur `fenster == "AUG"` in den SE-Harness
(`_replay_c_se_main`); S1/S2 laufen ueber `_lauf_c` → **Alt-C**
(`_replay_c`), in dem die SE-Symbole (`_se_scan`, `_se_trades`,
`blockiert_durch_aussenkante`, `basis_bei`, `_existiert`, `retest_zyklus`)
**0×** vorkommen. S1/S2 wuerden folglich eine andere Engine messen.
`retest_zyklus_bars = 12` ist damit ein **AUG-Arbeitswert**, keine
gate-konforme Endarretierung. Die Bestaetigung ist nach Behebung des
Routing-Blockers nachzuholen.

**10. Wirkung auf §8.4:**

Die Harness-Defaults in §8.4 werden auf `retest_zyklus_bars` **12** korrigiert
(1:1 zur Klassenebene `StraightEdgeHarnessKonfiguration`). Die
Gate-Semantik (§8.2: `PF >= 1,30` UND `Summe R > 0` auf S1 UND S2) bleibt
unveraendert; AUG bleibt reine Referenz.

**Datenvertrag Arretierungsstatus (arretiert):**

> **SUPERSEDED (2026-09-09, §7.2 Teil 4):** `ArretierungsStatusV3` beschreibt das
> **gate-freie** Modell (`plateau_grenzen = (3, 15)`). Ersetzt durch
> `ArretierungsStatusV4` in Teil 4, Abschnitt 16. Bleibt zur
> Revisionssicherheit stehen; **nicht** mehr maßgeblich.

```python
from dataclasses import dataclass
from typing import Literal, Tuple


@dataclass(frozen=True, slots=True)
class ArretierungsStatusV3:
    parameter_name: str = "retest_zyklus_bars"
    wert_alt: int = 24
    wert_neu: int = 12
    plateau_grenzen: Tuple[int, int] = (3, 15)
    untergrenze_toxisch_bars: int = 3
    obergrenze_entry245_entfaellt_bars: int = 15
    f1_option_a_revoziert: bool = True
    s1_s2_status: Literal["VORBEHALT_WEGEN_ROUTING_BLOCKER"] = (
        "VORBEHALT_WEGEN_ROUTING_BLOCKER")
    low_n_warnung_aktiv: bool = True
```

### Nachtrag 2026-09-09 (Teil 4) — Stacking-Verbot §7.1 B: Durchsetzung & Kennzahlen

> **Status: ARRETIERT (Mentor-Freigabe 2026-09-09, Fragen 1–3).**
> Dieser Nachtrag **hebt die Plateau-Begruendung aus Teil 3 auf**: das dort
> arretierte Plateau `[3; 15]` und die Kennzahl `+27,08 R` sind **gate-freie
> Artefakte** (Abschnitte 3–5). Arretiert bleiben: `retest_zyklus_bars = 12`
> als **institutioneller Arbeitswert** (neue Begruendung `v >= 7`), die
> Re-Test-Sequenz (Teil 2), `touch_band_pct` 0,12, M2/M6, B23-3/4/5.
> Revoziert werden: `plateau_grenzen_bars = (3, 15)` als
> Arretierungsgrundlage, `erlaube_parallele_exposition = True` (Z. 1366) und
> der Datenvertrag `ArretierungsStatusV3` (Z. 1512–1524) — ersetzt durch
> `ArretierungsStatusV4` (Abschnitt 16).

**1. Forensischer Befund: §7.1 B war arretiert, aber nie implementiert.**

§7.1 B (Z. 453) und F3 (Z. 358–360) arretieren seit 2026-09-08 verbindlich
„max. 1 offene Position je Kante (kein Stacking)". Der Harness hat diese
Bedingung **nie geprueft**: `letzter_trade: Dict[int, _SESetup]` (Z. 2289)
wird bei Z. 2577 geschrieben, im gesamten Quelltext aber **kein einziges Mal
gelesen** (`letzter_trade[` = 1 Vorkommen = der Schreibzugriff). Der Kommentar
Z. 2267 („F2 — Einstieg nur ohne offene Position ODER nach De-Risking")
beschreibt damit **nicht ausgeführten Code**. Forensischer Nachweis:
`test/tmp_stacking_audit.txt` (read-only Audit 2026-09-09).

**2. Audit-Methode (read-only, kein Engine-Eingriff).**

Frischer `_se_scan("AUG", StraightEdgeHarnessKonfiguration())` je Variante
(der Scan mutiert `letzter_sweep_bar`; geteilte Scans verfaelschen das
Ergebnis). Zwei Laeufe: Box (`box_end_bar = 644`) und Voll
(`scan["box_end_bar"] = n = 1288`). Gate-Wirkung durch **In-Memory-Patch**
der Modulkopie — die Engine-Datei blieb unveraendert (185.290 B, CRLF 4.371,
kein BOM).

**3. Befund 1 — drei Stacking-Verletzungen im Gesamtfenster (Bars 0–1288).**

| Kante | T1 entry → exit_final | T1 R | T2 entry | T2 R | Ueberlappung | Phase |
|---|---|---|---|---|---|---|
| **K20** | 231 → 398 | **+6,92** | 245 | +3,95 | **154 Bars** | BOX |
| **K31** | 531 → 639 | **+8,41** | 567 | +3,14 | **73 Bars** | BOX |
| **K62** | 855 → 867 | −1,00 | 866 | −1,00 | **1 Bar** | POST |

**Box-Fenster (0–641): 2 Verletzungen — beide auf einem laufenden GEWINNER.**
Beide Lesarten (bis `exit1` / bis `exit2`) liefern im vorliegenden Datensatz
identische Blockierungen; die De-Risking-Lesart wird dennoch verworfen
(Abschnitt 7). Kantenuebergreifende Ueberlappung (nicht durch §7.1 B
verboten): K48 (681→733) parallel zu K16 (718→728), 15 Bars, gegenlaeufig.

**4. Befund 2 — die Box-Kennzahl +27,08 R ist ein Gate-Artefakt.**

| Phase | ohne Gate | mit Gate | Differenz |
|---|---|---|---|
| BOX (0–641) | n=6, **+27,08 R** | n=4, **+19,99 R** | **−7,09 R / −2 Trades** |
| POST (644–1287) | n=6, +2,03 R | n=5, +3,03 R | +1,00 R / −1 Trade |
| GESAMT | n=12, +29,11 R | n=9, **+23,02 R** | −6,09 R |

Gate-Blockierungen (v = 12): `k=242` und `k=244` (beide → Entry 245, K20),
`k=564` (→ 567, K31), `k=865` (→ 866, K62). **Wichtig:** Weil ein geblockter
Kandidat die Zyklus-Uhr nicht zuruecksetzt (B23-5), bleibt nach der Sperre von
Bar 242 der Alternativpfad Bar 244 offen (`Δ15 >= 12`) und laeuft ebenfalls in
das Gate — die Pfad-Substitution aus Teil 3 wird durch das Gate neutralisiert.

**5. Befund 3 — `retest_zyklus_bars` ist in der Box nicht identifizierbar.**

| v | ohne Gate: n / Netto-R | mit Gate: n / Netto-R |
|---|---|---|
| 0–2 | 7 / +26,08 | 4 / +19,99 |
| **3–13** | 6 / +27,08 | **4 / +19,99** |
| 14–15 | 6 / +27,09 | 4 / +19,99 |
| 16–24 | 5 / +23,13 | 4 / +19,99 |

**Mit Gate ist das Box-Ergebnis fuer alle `v ∈ [0; 24]` exakt konstant
(n=4 / +19,99 R).** Die drei in Teil 3 arretierten „exakten Schwellen"
(`v >= 3`, `v <= 15`, Sprung bei 14) existieren **nur gate-frei**. Das Plateau
`[3; 15]` ist damit als Arretierungsgrundlage **aufgehoben**.

**6. Befund 4 — Gate und Zyklus ueberlappen, sind aber nicht redundant.**

Gesamtfenster, Gate-Blockierungen je `v`:

| v | Blockierungen | betroffene Entries |
|---|---|---|
| 0–1 | 13 | K20@245(2×), K31@531/533/567, K3@653(2×), K48@681, K62@855/861(2×)/863/866 |
| 2 | 9 | K20@245(2×), K31@533/567, K3@653, K62@861(2×)/863/866 |
| 3–6 | 7 | K20@245(2×), K31@567, K62@861(2×)/863/866 |
| 7 | 6 | K20@245(2×), K31@567, K62@861/863/866 |
| 8–9 | 5 | K20@245(2×), K31@567, K62@863/866 |
| 10–12 | 4 | K20@245(2×), K31@567, K62@866 |
| 13 | 3 | K20@245(2×), K31@567 |
| 14–15 | 2 | K20@245, K31@567 |
| **16–24** | **1** | **K31@567** |

Das Gate wirkt auf die **Positions-Laufzeit**, der Zyklus auf den
**Signal-Abstand**: Das Gate faengt zusaetzlich K31@567 (das der Zyklus ab
`v >= 16` nicht mehr sieht), die K62-Kaskade (855/861/863/866) und die
Doppelpfade K20@245 / K3@653. Gesamtfenster mit Gate: `+21,02` (v 0–4) →
`+22,02` (v 5–6) → **`+23,02` (v >= 7, konstant)**.

**7. Arretierung A — Auslegung „offene Position" (Frage 1).**

Verbindlich: **`kandidat_entry_bar <= exit_final_bar`** mit
`exit_final_bar = max(exit1_bar, exit2_bar)`. Maßgeblich ist der
**Ausfuehrungszeitpunkt (Entry-Bar)**, nicht der Entscheidungs-Bar `k`: Ein
Reclaim ist ein Prozess, aber Exposure entsteht erst mit der Ausfuehrung. Ist
der Alt-Trade an Bar 244 geschlossen und der Neu-Trade geht an Bar 245 in den
Markt, existiert **zu keinem Zeitpunkt doppeltes Exposure**. Die
De-Risking-Lesart („frei ab TP1") wird **verworfen**: Die Restposition bindet
weiterhin Margin und Marktrisiko, solange ein Kontrakt an der Kante liegt.

**8. Arretierung B — Einbauposition des Gates.**

Das Gate greift **vor allen drei Seiteneffekten** des Trade-Pfads:

1. vor `getradete_entry_bars.add(entry_bar)` / Dedup-`continue` (Z. 2557–2559)
   → ein geblockter Bar belegt **keinen** globalen Slot;
2. vor `kd.letzter_sweep_bar = k` / `kd.letzter_signal_bar = k` (Z. 2560–2561)
   → ein geblockter Kandidat setzt die Kanten-Uhr **nicht** zurueck (B23-5);
3. vor `letzter_trade[kd.kid] = setup` (Z. 2577) → der Tracker wird **nicht**
   ueberschrieben (sonst entwaffnet die Sperre sich selbst).

Praktische Platzierung: **vor `_c_loese_trade` (Z. 2554)** — die Exit-Bars des
Vortrades liegen bereits in `letzter_trade[kid]` vor; `_c_loese_trade` ist
seiteneffektfrei. Die gemessenen Zahlen (+19,99 R / +23,02 R) sind mit beiden
Platzierungen identisch.

**9. Arretierung C — `v >= 7`, Arbeitswert 12 (Frage 2).**

Der Parameter `v` ist in der Box unter dem Gate **invariant** (`v ∈ [0; 24]`);
im Gesamtfenster verlangt das Optimum **`v >= 7`** (darunter +21,02/+22,02 R,
darueber konstant +23,02 R). Arretiert wird daher **nicht** ein Datenoptimum,
sondern: **Untergrenze `v >= 7`** (Abwehr von Rausch-Setups) und
**Arbeitswert `v = 12` = 3,0 Stunden** (halbe FX-/Rohstoff-Handelssitzung,
institutionelle Standardzeit). Teil 3 wird insoweit praezisiert: 12 ist
**institutionell motiviert**, nicht datenoptimal.

**9a. Zaehler-Praezisierung (Nachtrag Teil 5, reine Faktentreue).**

Nach der `_p7`-Scharfschaltung sind die Ablehnungs-Kategorien **nicht**
deckungsgleich mit dem Pre-Patch-Lauf: `zyklus_blockiert = 2` (nicht 3)
und `stacking_blockiert = 3` im AUG-Lauf. Ursache: Bar 244 (K20) war
pre-Patch zyklus-gesperrt (die Zyklus-Uhr stand auf Bar 242); post-Patch
wird **Bar 242 vom Stacking-Gate geblockt** und setzt die Kanten-Uhr nicht
mehr zurueck (Abschnitt 8, Punkt 2 / B23-5), daher laeuft Bar 244 durch und
wird selbst vom Gate gefangen. **Kategorie-Wechsel bei identisch
eliminiertem Trade.** Im Voll-Lauf (n = 1288): `stacking_blockiert = 4`
(zusaetzlich Bar 865, K62).

**10. Kennzahlen-Neufassung (ungeschminkt, Revisionssicherheit).**

| Stand | Gate | BOX | POST | GESAMT |
|---|---|---|---|---|
| Phase 1/2/3 (Teile 1–3) | **inaktiv** | n=6 / +27,08 R | n=6 / +2,03 R | n=12 / +29,11 R |
| **Teil 4 (arretiert)** | **aktiv** | **n=4 / +19,99 R** | **n=5 / +3,03 R** | **n=9 / +23,02 R** |

Die Zahlen der Teile 1–3 bleiben im Dokument **erhalten** und werden als
**gate-frei** gekennzeichnet; sie sind **keine** gueltige Kennzahl der
arretierten Engine.

**11. Low-n-Eskalation (§8.2).**

Die Box-Stichprobe sinkt auf **n = 4**, das Gesamtfenster auf **n = 9**.
Profit-Faktoren und Erwartungswerte sind damit **statistisch wertlos**
(§8.2: Warnung ab `n < 20`). Die Validitaet speist sich ausschliesslich aus
der **kausalen Marktstruktur** (Sweep → Non-Expansion → Reclaim) und aus der
Regelkonformitaet, **nicht** aus der R-Summe.

**12. Harness-Contract fuer `_p7` (Frage 2, freigegeben).**

```python
stats["stacking_blockiert"]: int = 0
stats["stacking_liste"]: List[str] = []
# Meldung:
# f"bar {k:4d} {richtung:5s} K{kd.kid:3d} -> STACKING-SPERRE "
# f"(Position Bar {vorheriger.entry_bar} offen bis {vorheriger.exit_final_bar})"
```

Eigene Report-Sektion: **`STACKING-GESPERRTE SETUPS (§7.1 B)`**.

**13. Revokationen (Frage 3, gebuendelt in diesem Commit).**

- **Befund A:** Z. 1366 `erlaube_parallele_exposition: bool = True` wird auf
  **`False`** gesetzt und ausdruecklich revoziert — der Widerspruch zu §7.1 B
  und F3 wird damit geschlossen.
- **Befund B:** Z. 1365 `plateau_grenzen_bars = (3, 15)` verliert den Status
  einer Arretierung (gate-frei, nur historische Messmarke).
- **Befund C:** Der Datenvertrag `ArretierungsStatusV3` (Z. 1512–1524) wird als
  **SUPERSEDED** markiert (Revisionssicherheit) und durch
  `ArretierungsStatusV4` ersetzt (Abschnitt 16).

**14. Wirkung auf §8.4.**

Die Harness-Defaults bleiben `retest_zyklus_bars = 12`; ergaenzt wird:
`stacking_gate_aktiv = True`, `max_offene_positionen_je_kante = 1`,
`v_minimum_gesamt = 7`. Die Gate-Semantik (§8.2: `PF >= 1,30` UND
`Summe R > 0` auf S1 UND S2) bleibt unveraendert; AUG bleibt Referenz.

**15. S1/S2-Vorbehalt (ausdruecklich aufrechterhalten).**

Der Routing-Blocker besteht fort (S1/S2 laufen ueber `_lauf_c` → Alt-C ohne
SE-Zaehler). Die Messung auf S1/S2 ist **weiterhin nicht moeglich**; `v = 12`
bleibt AUG-Arbeitswert unter Vorbehalt. Zusaetzlich offen: Der Stacking-Ban
muss auf S1/S2 mit demselben Gate gemessen werden (Teil der Routing-Aufgabe).

**16. Datenvertrag (arretiert).**

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class PositionstrackingEintrag:
    kanten_id: int
    entry_bar: int
    exit_final_bar: int  # max(exit1_bar, exit2_bar)

    def blockiert_entry(self, kandidaten_entry_bar: int) -> bool:
        \"\"\"Sperrt Folgetrades, solange der Vorgaenger im Markt aktiv ist.\"\"\"
        return kandidaten_entry_bar <= self.exit_final_bar


@dataclass(frozen=True, slots=True)
class ArretierungsStatusV4:
    stacking_verbot_aktiv: bool = True
    erlaube_parallele_exposition: bool = False  # Befund A: Vollrevokation Z. 1366
    v_minimum_gesamt: int = 7                   # untere Schranke Gesamtfenster
    v_arbeitswert_institutionell: int = 12      # 3,0 h Halbtagssitzung
    box_n_trades: int = 4                       # ungeschminkte Stichprobe
    box_netto_r: float = 19.99
    post_box_n_trades: int = 5
    post_box_netto_r: float = 3.03
    gesamt_n_trades: int = 9
    gesamt_netto_r: float = 23.02
    plateau_box_status: Literal["INVARIANT_0_BIS_24"] = "INVARIANT_0_BIS_24"
    low_n_warnung_eskalation: bool = True
```

**17. Folgearbeiten (nicht Teil dieses Commits).**

1. Patch `_p7`: Gate + Stats-/Report-Contract (§12, §8).
2. Routing-Generalisierung S1/S2 (`box_end_bar` parametrisieren, Typ-Adapter).
3. Neue Kennzahlen-Basis n=4/n=9 → Gate-Messung auf S1/S2 nachholen.
4. `--engine se|alt`-Schalter (Alt-C als Referenz isolieren).

### Nachtrag 2026-09-09 (Teil 5) — R21-Kantenbereinigung & Tombstone: Arretierung

> **Status: ARRETIERT (Mentor-Freigabe 2026-09-09, Fragen 1–3).**
> Dieser Nachtrag ergaenzt §7.2 um die **Bereinigungsregel R21**
> (Singleton-Verfall mit Tombstone-Sperre). Er **hebt nichts auf**: alle
> Arretierungen der Teile 1–4 bleiben in Kraft. Neu arretiert werden:
> `ruhezeit_roher_touch_bars = 192`, `tombstone_band_pct = 0.30`
> (eigenstaendig), Sperrdauer **unbegrenzt**, Loeschung **kausal sofort bei
> Bar k**. Die vier Revival-Kanten K1/K31/K51/K54 werden als Audit-Referenz
> **„Market-Memory"** festgeschrieben.

**1. Anlass und Gegenstand.**

Der Kanten-Bestand in AUG waechst auf **93 Kanten** (65 gekeimte edges mit
>= 2 Touches + 28 Seeds), von denen **78,5 %** nie als aeusserste Begrenzung
wirken. Forensische Grundlage (alle read-only, `test/`): `tmp_kanten_aufraeumen.txt`
(Inventar), `tmp_faenger.txt` (Kontakt-Verteilung), `tmp_loeschregeln*.txt`
(Regel-Vorstufen), `tmp_tombstone.txt` (Wiedergeburten), `tmp_deletion_attribution.txt`
(Einzel-Attribution), `tmp_r18_timeout.txt` und `tmp_r21_final.txt`
(Grenzkarte/Arretierung).

**2. Regeldefinition R21 (strikt kausal bis Bar k).**

Eine Linie wird geloescht, wenn ALLE fuenf Bedingungen erfuellt sind:

- (a) Alter seit `erster_pivot_bar` >= `wall_live_bars` (96);
- (b) `ist_prim_anker == False`;
- (c) `touch_conf(k) < 2` (bestaetigte Dochte mit `b + 2 <= k`);
- (d) `k - letzter_roher_touch >= 192`, mit
  `letzter_roher_touch = max(b for b, _ in wicks if b <= k)`;
- (e) die Linie war **nie** eine lebende Aussenlinie
  (`war_jemals_aussen`-Set ueber `kid`, kausal akkumuliert).

Die Loeschung erfolgt **in-place** in `cluster[seite]` bei Bar k (vor
`_se_trades`); im selben Schritt wird ein **Tombstone** `(k, seite, basis)`
gesetzt. Neugeburten werden gesperrt, wenn `|px - basis| / basis * 100 <= 0,30`
und dieselbe Seite.

**3. Messprotokoll (read-only, kein Engine-Eingriff).**

Frischer `_se_scan("AUG", ...)` je Variante (der Scan mutiert
`letzter_sweep_bar`, `cluster_hoch/tief`, `letzter_signal_bar`; geteilte Scans
verfaelschen das Ergebnis). Regel-Wirkung durch **In-Memory-Patch** der
Modulkopie; die Engine-Datei blieb unveraendert (186.660 B, CRLF, kein BOM).
Die Trade-Signatur wird ueber `(bar, richtung, entry_bar, R)` verglichen —
**nicht** ueber `kid` (die Loeschung verschiebt die kid-Nummerierung; ein
kid-basierter Vergleich lieferte in einem Vorlauf falsche Loeschzeitpunkte).

**4. Befund 1 — 78,5 % der Kanten sind nie die aeusserste Linie.**

Geprueft in drei Semantiken: O1 `_existiert` (bestaetigter Pivot),
O2 `_gegenkante`-Pool (Primaer-Anker ab Promotion ODER `touch_conf >= 2`),
O3 `_kandidat`-Pool (O2 + Alter >= `min_wall_alter_bars`). Ergebnis:
**73 von 93 (78,5 %) nie aeusserste**. Nur **20 Kanten** waren jemals
aeusserste: 0, 1, 2, 3, 5, 6, 8, 10, 12, 15, 16, 20, 43, 51, 54, 61, 62, 64,
68, 70.

**5. Befund 2 — 72,4 % aller Docht-Kontakte sind strategisch irrelevant.**

330 Docht-Kontakte gesamt: **91 (27,6 %)** an aeussersten, **239 (72,4 %)**
an nie-aeussersten Kanten. **47 Kanten** mit >= 2 Touches sind reine
Docht-Faenger (213 Dochte); Spitzenreiter K17 (13), K13 (10), K24/K69 (8).

**Institutionelle Konsequenz:** Reine Touch-Counts repraesentieren **keinen**
Edge — 72,4 % der Kontakte prallen an strategisch irrelevanten Kanten ab.
Geometrische Pivot-Kanten muessen begrifflich von institutionellen
Aussen-Liquiditaetspools getrennt bleiben; die „Touch-Qualitaet" als
Reifekriterium ist empirisch entlarvt.

**6. Befund 3 — „Aussenheit" ist transient.**

Dieselbe Linie kann innen sein und spaeter aussen werden (und umgekehrt). Eine
Regel „loesche alle nie-aeussersten" ist daher **nicht** kausal stabil: R9
(96 Bars nicht-aeusserste, 134 Loeschungen) zerstoert die Signatur
(2 Trades / −2,00 R). Der Schutz (e) ist deshalb unverzichtbar.

**7. Gescheiterte Regel-Vorstufen (R1–R17, Auswahl).**

| Regel | Umfang | Trades | Netto-R | Folgekanten | Urteil |
|---|---|---|---|---|---|
| R1 nie-outer+nie-genutzt | 53 | 9 | +23,02 | **30** | Signatur ok, Wiedergeburten |
| R2 nie-outer | 73 | 7 | +8,13 | 49 | zerstört |
| R3 nie `_kandidat` | 62 | 10 | +22,00 | 38 | Signatur abweichend |
| R4 nie kandidat/gegen/blocker | 60 | 9 | +23,02 | 36 | Wiedergeburten |
| R5 <= 1 Touch & kein Entry | 27 | 9 | +23,02 | **0** | zu wenig, kein Verfall |
| R6 nie kandidat+gegen | 61 | 9 | +23,02 | 37 | Wiedergeburten |
| R7 nur Aussenkanten materialisieren | — | 6 | +8,16 | — | zerstört |
| R8 Singleton-Timeout 96 | 51 | 8 | +17,77 | 10 | Revival-Schaden |
| R9 96 Bars nicht-aeusserste | 134 | 2 | −2,00 | 11 | zerstört |
| R11 < 3 Touches Timeout | 97 | 7 | +18,77 | 16 | Revival-Schaden |
| R12 Geburt an Range-Extrem | 274 | 3 | −3,00 | 0 | Kern zerstoert |
| R13 Geburt im aeusseren Quartil | 191 | 8 | +9,05 | 3 | zerstört |
| R15 ersetzt+dormant 96 | 76 | 7 | +17,28 | 12 | Revival-Schaden |
| R17 wie R15, 192 Bars | 46 | 8 | +24,02 | 4 | Revival-Schaden |

Zwei wiederkehrende Schaeden: **Wiedergeburten** (verwaiste Dochte erzeugen
identische Folgekanten) und **Revivals** (alte Linien werden nach > 100 Bars
reaktiviert und konsumiert).

**8. Befund 4 — Wiedergeburten sind der Folgekanten-Mechanismus (Tombstone-Beleg).**

R18 (dieselbe Regel ohne Tombstone, T = 96) loescht 40 Kanten, liefert
9 Trades / **+15,28 R** und **8 Folgekanten**. Jede dieser 8 Folgekanten liegt
in einem geloeschten Preisband:

| Folgekante | Tombstone-Treffer (<= 0,30 %) |
|---|---|
| UNTEN 209 / 65,049 | 177 / 65,009 |
| OBEN 376 / 64,708 | 224 / 64,552 · 271 / 64,738 |
| UNTEN 398 / 63,485 | 103 / 63,464 |
| UNTEN 479 / 65,414 | 200 / 65,400 · 351 / 65,494 · 387 / 65,293 |
| UNTEN 707 / 64,824 | 177 / 65,009 · 426 / 64,823 · 688 / 64,818 |
| OBEN 1001 / 68,699 | 938 / 68,673 |
| UNTEN 1124 / 69,084 | 982 / 69,043 |
| UNTEN 1234 / 68,233 | 924 / 68,037 · 1212 / 68,183 |

Mit Tombstone (±0,30 %): **0 Folgekanten**. Die Sperre ist damit kein Zusatz,
sondern **Bedingung der Regel**.

**9. Befund 5 — Revival-Kanten K1/K31/K51/K54 (Market-Memory, Audit-Referenz).**

Einzel-Attribution aller 40 R18-Loeschungen (deletion-at-birth, je Kante
einzeln): **33 harmlos, 4 schaedlich**. Schaedlich sind ausschliesslich Kanten,
die **nach** der Loeschung wieder Kontakt finden und danach konsumiert werden:

| Kante | Seite | Pivot | Touches | Außenlinie | Nutzung | Revival-Wirkung |
|---|---|---|---|---|---|---|
| K1 | UNTEN | 7 | 3 | ja | `_kandidat` + `_gegenkante` + Entry | Entry 529 verschoben |
| K31 | OBEN | 237 | 5 | nein | `_kandidat` + Entry | Entry 679 (+6,48 R) |
| K51 | UNTEN | 657 | 2 | ja | `_gegenkante` + Blocker | Exit 760 verschoben |
| K54 | OBEN | 736 | 2 | ja | `_kandidat` + Entry | Exit 760 verschoben |

**Institutionelle Lesart:** Liquiditaetspools werden nicht nach 24 Stunden
vergessen. Dass diese vier Linien nach > 100 Bars wieder angelaufen und
konsumiert wurden, belegt: **keine voreilige Loeschung ohne echten Verfall.**
Die vier Kanten sind als feste Audit-Referenz Teil dieser Spezifikation.

**10. Timeout-Grenzkarte (Tombstone ±0,30 %, AUG komplett, n = 1288).**

| T (Bars) | geloescht | Kanten | Trades | Netto-R | Signatur | Folgekanten |
|---|---|---|---|---|---|---|
| 96 | 26 | 55 | 8 | +16,28 | ABWEICHEND | 0 |
| 112 | 24 | 58 | 8 | +16,54 | ABWEICHEND | 0 |
| 128 | 21 | 62 | 8 | +16,54 | ABWEICHEND | 0 |
| **144** | 19 | 67 | 9 | +23,02 | IDENTISCH | 0 |
| **152** | 19 | 67 | 9 | +23,02 | IDENTISCH | 0 |
| **160** | **20** | 67 | 9 | +23,02 | IDENTISCH | 0 |
| **176** | 18 | 70 | 9 | +23,02 | IDENTISCH | 0 |
| **192** | **17** | 73 | 9 | +23,02 | IDENTISCH | 0 |
| 256 | 12 | 80 | 9 | +23,02 | IDENTISCH | 0 |

Ohne Tombstone steigen die Folgekanten (T = 160: 5, T = 192: 4, T = 256: 1) —
der Beleg aus Abschnitt 8.

**11. Arretierung A — `ruhezeit_roher_touch_bars = 192` (Frage 1).**

Das **Mengen-Optimum** liegt bei T = 160 (20 geloescht). Es wird **verworfen**:
es liegt nur **16 Bars** ueber der Identitaets-Unterkante T = 144 und damit in
der Naehe der Revival-Zonen. Arretiert wird **T = 192 = 48 Stunden = 2 volle
Handelstage** — eine institutionelle Zeitkonstante, die **tief im stabilen
Plateau** liegt (Identitaet ab 144, konstant bis 256). Der Verzicht auf drei
zusaetzlich loeschbare Kanten ist der Preis fuer Robustheit; die Kennzahl
bleibt mit **+23,02 R** identisch. **Merksatz:** kein Datenoptimum an der
Abbruchkante.

**12. Arretierung B — `tombstone_band_pct = 0.30` eigenstaendig, Sperre unbegrenzt (Frage 2).**

Band-Sensitivitaet bei T = 192: 0,20 % → 19 geloescht / 15 gesperrt / 0 Folge;
**0,30 % → 17 / 17 / 0**; 0,40 % → 17 / 17 / 0. Bei T = 96 liefert 0,20 % noch
**1 Rest-Folgekante**, 0,30 % bereits 0. Arretiert wird deshalb **±0,30 %** als
**kleinster Wert mit 0 Folgekanten** (= reale Docht-Rauschbreite der
Cluster-Bildung). Eine Kopplung an `max_seed_distanz_pct` (0,75 %) wird
ausdruecklich **verworfen**: 0,75 % bei Silber (~0,50 USD) erstickt legitime
Neuentwicklungen. Die Sperre gilt **unbegrenzt**: ein Niveau, an dem sich ein
Singleton nachweislich erschoepft hat, darf in derselben Marktphase nicht durch
einen zufaelligen Einzeldocht wiederauferstehen.

**Technischer Vorbehalt:** Die Sperrliste ist monoton wachsend und
pfadabhaengig (AUG: 30 Eintraege). Bedingung (e) `WAR_AUSSEN` bleibt als
Zweitnetz **zwingend** erhalten — ein Tombstone allein darf eine legitime
Neuentwicklung nicht dauerhaft ersticken.

**13. Arretierung C — Loeschung kausal sofort bei Bar k (Frage 3).**

Keine Sonderregel nach `box_end_bar`. Eine Engine, die live anders rechnet als
im Backtest, ist unbrauchbar. R21 prueft ausschliesslich Vergangenheitswissen
bis Bar k; der Vergleich Original vs. R21 ist damit ein echter
Kausalitaetsnachweis.

**14. Kennzahlen (ungeschminkt, Revisionssicherheit).**

| Stand | Kanten | Trades | Netto-R | BOX | POST |
|---|---|---|---|---|---|
| Original (Teil 4, arretiert) | 93 | 9 | +23,02 | n=4 / +19,99 | n=5 / +3,03 |
| **R21 arretiert (T = 192)** | **73** | **9** | **+23,02** | n=4 / +19,99 | n=5 / +3,03 |
| R18 ohne Tombstone (T = 96) | 66 | 9 | +15,28 | — | — |

R21 ist **signaturneutral**: identische Trades, identische R-Summe,
**0 Folgekanten**. Die Bereinigung betrifft ausschliesslich nie-aeusserste,
nie-konsumierte Singletons. Die Low-n-Eskalation aus Teil 4 (Abschnitt 11)
gilt unveraendert.

**15. Grenze der Aussage (kein 80-%-Versprechen).**

R21 entfernt **21,5 %** (T = 160) bzw. **18,3 %** (T = 192) des Bestands —
**nicht** 80 %. Die verbleibenden nie-aeussersten Kanten sind **nicht
risikofrei loeschbar**: R4/R6 (60/61 Kanten) erhalten die Signatur exakt,
erzeugen aber 36/37 Folgekanten; R2 (73) zerstoert die Signatur. Ursache sind
die Transienz der Aussenrolle (Abschnitt 6) und die Wiedergeburts-Mechanik
(Abschnitt 8).

**16. Datenvertrag (arretiert, Korrekturen 1–4 eingearbeitet).**

```python
@dataclass(frozen=True, slots=True)
class R21LoeschKonfiguration:
    wall_live_bars: int = 96
    ruhezeit_roher_touch_bars: int = 192      # institutioneller Standard (48 h)
    min_touch_conf: int = 2                   # darunter gilt als Singleton
    tombstone_band_pct: float = 0.30          # eigenstaendig, +/-0,30 %
    erlaube_loeschung_fuer_prim_anker: bool = False


@dataclass(frozen=True, slots=True)
class TombstoneEintrag:
    basis_preis: float
    band_pct: float = 0.30
    erzeugt_bar: int = 0

    def blockiert_preis(self, preis: float) -> bool:
        halbe_breite: float = self.basis_preis * (self.band_pct / 100.0)
        return (self.basis_preis - halbe_breite
                <= preis
                <= self.basis_preis + halbe_breite)


def pruefe_r21_kausal(kid: int, erster_pivot_bar: int,
                      wicks: List[Tuple[int, float]],
                      ist_prim_anker: bool, aktueller_bar: int,
                      war_jemals_aussen_ids: Set[int],
                      cfg: R21LoeschKonfiguration) -> bool:
    """Strikt kausal, ohne Zukunfts-Leak (5 Bedingungen)."""
    if ist_prim_anker or (kid in war_jemals_aussen_ids):
        return False
    if (aktueller_bar - erster_pivot_bar) < cfg.wall_live_bars:
        return False
    if sum(1 for b, _ in wicks
           if (b + 2) <= aktueller_bar) >= cfg.min_touch_conf:
        return False
    bisherige: List[int] = [b for b, _ in wicks if b <= aktueller_bar]
    if not bisherige:
        return False
    return (aktueller_bar - max(bisherige)) >= cfg.ruhezeit_roher_touch_bars
```

Verbindliche Praezisierungen (Korrekturen 1–4):

1. `letzter_roher_touch` ist ein **Bar-k-Derivat**, kein Objektfeld — der
   `_SEEdgeH` ist ein `@dataclass(slots=True)`.
2. `touch_conf` zaehlt **bestaetigte** Dochte (`b + 2 <= k`), nicht
   `len(wicks)`.
3. `war_jemals_aussen` ist ein **externes `Set[int]`** ueber `kid` — dynamische
   Attribute sind im `slots`-Dataclass unmoeglich (real aufgetretener
   `AttributeError`).
4. Loeschung **in-place** im Scan bei Bar k; Tombstone-Eintrag **im selben
   Schritt**.

**17. Wirkung auf §8.4 & Folgearbeiten.**

§8.4 wird ergaenzt: `r21_loeschung_aktiv = True`,
`ruhezeit_roher_touch_bars = 192`, `tombstone_band_pct = 0.30`,
`tombstone_sperre = unbegrenzt`, `erlaube_loeschung_fuer_prim_anker = False`.
Die Gate-Semantik (§8.2) und der S1/S2-Vorbehalt (Teil 4, Abschnitt 15) bleiben
unveraendert. Folgearbeiten (nicht Teil dieses Commits): (1) Patch `_p8`
(R21 + Tombstone im Scan), (2) Routing-Generalisierung S1/S2, (3) Kennzahlen-
Basis n=4/n=9 → Gate-Messung auf S1/S2 nachholen.

---

---

## 8. Gate & Schritt-0-Replay (verbindlich)

### 8.1 Replay-Harness (`test/tmp_kanten_engine_replay.py`, Schritt 0)

Kausal sequentieller Einzellauf je Fenster (AUG/S1/S2), nur Daten bis k.
Fenster exakt wie frozen (AUG 08-10…08-28; S1 02-05…08-28; S2 01-01…12-01).
Sensitivitäten: `max_tage ∈ {1, 5, 20, 60}`, Balance VWAP/Mittel,
Cooldown-Reset je Kante/global.

**A/B-Schalter (V2):** Der Harness führt beide Modi kausal-sequentiell:
- **Modus A** = V1-Semantik (Balance-VWAP-Trigger, P2-Gate, §4.0/§6.0) —
  arretiert als Null-Befund, dient nur als Kontroll-Lauf.
- **Modus B** = V2-Semantik (Extremum-Ratchet, Touch-vor-SwingFilter,
  Cluster-Geburt, Body-Reclaim-Reaktivierung, §4.1/§6.1).
- Sweep-Parameter für Modus B: Ratchet-Toleranz {0,05/0,10/0,15 %},
  Zwischenschwung {1,5/2,0 %} — als Sensitivitätsmatrix S1/S2.
- Report/PNG je Modus; Logging der Gate-Ablehnungen und Kanten-Lebenszyklen.

### 8.2 Benchmark-Gate

- **S1 UND S2** je: `PF ≥ 1,30` UND `Summe R > 0`.
- AUG nur Referenz (S1 ⊃ AUG).
- Low-n-Transparenz: `n < 20` entschiedene Trades → Warnung, PF nicht belastbar.
- **Abbruch:** Verfehlt ein Fenster das Gate, wird die Engine als statistischer
  Null-Befund arretiert — kein Parametertuning, kein Schwellwert-Schleifen.
- Baseline (+297,14R) ist **Kontext, nicht Schranke** (§1.1, Ebene-2-Bias).

### 8.3 Null-Befund-Arretierung Modus A (V1, Balance-VWAP-Engine)

Am 2026-09-06 nach Gate-Regel §8.2 arretiert — **kein Parametertuning, keine
Schwellwert-Schleife** (Abbruch-Regel angewandt). Messung: Schritt-0-Replay
`test/tmp_kanten_engine_replay.py`, Balance-VWAP, Matrix `max_tage
{1, 5, 20, 60}`:

| Fenster | mt1 | mt5 | mt20 | mt60 | Gate |
|---|---|---|---|---|---|
| S1 (02-05…08-28) | 34 Sig, −15,73R, PF 0,44 | 211 Sig, +27,63R, PF 1,18 | 327 Sig, +46,80R, PF 1,20 | 382 Sig, +37,49R, PF 1,13 | **verfehlt** (PF < 1,30) |
| S2 (01-01…12-01) | 21 Sig, +0,22R, PF 1,01 | 72 Sig, −1,25R, PF 0,98 | 120 Sig, +12,35R, PF 1,14 | 123 Sig, +1,28R, PF 1,01 | **verfehlt** (PF < 1,30) |
| AUG (Referenz) | — | — | — | 19 Sig, +13,39R, PF 2,29 | nur Referenz (S1 ⊃ AUG) |

**Diagnose (arretierte Ursachen):**
1. **Gravity-Falle (K9):** Symmetrische Admission um die laufende Balance ließ
   Lower Highs (66.364/66.330/66.288) als Touches durch → Balance verwässerte
   von 66.459 auf 66.364 nach innen → verfrühter Short (Bar 527) mit Stop
   (Bar 529). Counterfactual am Anker 66.459: sauberer Trigger ohne Stop.
2. **P2-Betriebsblindheit (K20):** SwingFilter-Herkunfts-Gate (Fall d) verwarf
   direkte Re-Tests im ±0,15-Band (Distanzen 0,003–0,099 USD) → K20 blieb bei
   1 statt 4 Touches → nie Typ B handelbar.
3. **Makro-Wand-Fragmentierung (63,6–63,7):** Wiederholte Tiefs des 10.08.
   (5× in 8,25 h) verteilten sich mangels Cluster-Regel über keine/mehrere
   Kanten; K20 (1 Touch), K21 (2 Touches) blieben Fragmente.
4. **SCHLAFEND-Asymmetrie (K11):** Nach Reclaim (Bar 399/400) über der Balance
   blieb die Kante bis zum nächsten Docht-Touch (Bar 406) unnötig SCHLAFEND —
   Rückweg-Treppe ohne Reaktivierungs-Semantik.

**Konsequenz:** Modus A wird nicht weiterverfolgt. Modus B (V2) wird im selben
Harness über den A/B-Schalter (§8.1) gegen dasselbe Gate (§8.2) gemessen;
Sweeps nur über die in §8.1 genannten V2-Parameter. Erneutes Verfehlen →
Null-Befund-Arretierung auch für Modus B.

### 8.4 Modus-C-Gate (V3, arretiert 2026-09-08, E5)

Da V3-Kanten **zeitlos** über den 2-Body-Bruch gesteuert werden, entfällt das
`max_tage`-Grid {1, 5, 20, 60} für Modus C. Es gilt:

- **Nachtrag 2026-09-08 (Straight-Edge, §7.2 + Sweep-Immunität):** Die
  Default-Konfiguration von Modus C wird durch §7.2 ersetzt (Cluster-Keimung
  ≥ 2 Dochte, **arretierter Default `SE_BAND_PCT`/`touch_band_pct = 0.12`**,
  Außenkanten-Prinzip Regel 2, Sweep-Docht-Sperre inkl. Singleton-Seeds,
  Histogramm-POC als TP1, Reife-Schwelle strikt V-S ≥ 3 Touches,
  Box-Phase 10.08.–18.08. als AUG-Eichmaßstab). Das C-Gate selbst bleibt
  unverändert: je Fenster genau 1 Durchlauf.
- **Je Fenster genau 1 Durchlauf** (AUG, S1, S2) mit fester Default-Konfiguration
  (§7.2: `touch_band_pct` **0,12**, Abstand ≥ 3, Gegenkante ≥ 2, Split 50/50,
  SL-Puffer 0,05 USD fest; **Block 2/3 + M6 + Teil 3:** `retest_zyklus_bars`
  **12** (AUG-arbeitswert unter S1/S2-Vorbehalt; Plateau `[3; 15]` ist
  **gate-frei** und seit §7.2 Teil 4 **aufgehoben** — Untergrenze `v >= 7`),
  **§7.2 Teil 4:** `stacking_gate_aktiv = True`, `max_offene_positionen_je_kante = 1`,
  `quartil_distanz_pct` 25,0, `max_seed_distanz_pct` 0,75,
  **§7.2 Teil 5:** `r21_loeschung_aktiv = True`,
  `ruhezeit_roher_touch_bars = 192`, `tombstone_band_pct = 0.30`,
  `tombstone_sperre = unbegrenzt`, `erlaube_loeschung_fuer_prim_anker = False`
  — 1:1 der
  Harness-Default `StraightEdgeHarnessKonfiguration`). Keine
  `max_tage`-Sensitivitätsmatrix für C.
- **Bestehenskriterium:** identisch zu §8.2 — `PF ≥ 1,30` UND `Summe R > 0` auf
  **S1 UND S2**; AUG bleibt reine Referenz (S1 ⊃ AUG).
- **`--modus ALLE`:** Vergleichstabelle zeigt **Modus A (mt=60)**, **Modus B
  (mt=60)** und **Modus C (statisch)** je Fenster — A/B als historische
  Regressionsanker unberührt, C autark.
- **Abbruch:** Verfehlt S1 oder S2 das Gate → V3 wird als statistischer
  Null-Befund arretiert (kein Parametertuning, keine Schwellwert-Schleife).

---

## 9. Umsetzungs-Reihenfolge (nach Freigabe)

0. **Arretiert 2026-09-06:** V2-Spezifikation (§4.1/§5.1/§6.1/§8.3) —
   Freigabe-Gate des Users vor der Harness-Änderung erteilt.
1. Replay-Harness `test/tmp_kanten_engine_replay.py`: Einbau des **A/B-Schalters**
   (§8.1) — Modus A (Kontroll-Lauf) vs. Modus B (V2); danach AUG-Smoke
   (K9/K14/K20-Verifikation) und S1/S2-Sensitivitätsmatrix → Gate-Messung (§8.2).
2. Erst bei bestandenem Gate: Module in `scripts/reclaim_kanten_engine.py`
   (KantenSpeicher → SwingFilter → KantenBalancierung → ReclaimEngine), je mit
   py_compile + gezieltem Logik-Test in `test/`.
3. `scripts/phasen_volumen_profil.py` bleibt **byte-identisch** (Siegel).

---

## 10. Referenzen

- `docs/reclaim_historie_index.md` (b197011) — Master-Index aller Reclaim-Dokus
- `docs/Archiv/RECLAIM.md` — v0.1–v0.4-Falsifikationen (Z. 19–80, 595–605, 627–673)
- `docs/reclaim_live_lateriz_befund.md` (b6bcfc6) — Rechtsrand-Lateriz
- `docs/reclaim_snapshot_spez.md` (dc1e2b0) + Schritt-0-Replay — Snapshot-Null
- `test/SESSION_HANDOFF.md` — Lookahead-Bereinigung (Z. 37–53), Tuning-Bias (Z. 145)
- `scripts/macro_persistence.py` — Kanten-Gedächtnis-Muster (809 Z., eingefroren)
- `scripts/phasen_volumen_profil.py` — Baseline v0.4.0 (+297,14R, byte-identisch)
