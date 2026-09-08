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
>   (kein Stacking, kein starrer Bar-Cooldown).
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
  **max. 1 offene Position je Kante** (kein Stacking). Kein starrer
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
   max. 1 offene Position je Kante; kein starrer Bar-Cooldown (B).
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

- **Nachtrag 2026-09-08 (Straight-Edge, §7.2):** Die Default-Konfiguration von
  Modus C wird durch §7.2 ersetzt (Cluster-Keimung ≥ 2 Dochte,
  `SE_BAND_PCT ≈ 0,11–0,12 %`, Außenkanten-Prinzip, Histogramm-POC als TP1,
  Box-Phase 10.08.–18.08. als AUG-Eichmaßstab). Das C-Gate selbst bleibt
  unverändert: je Fenster genau 1 Durchlauf.
- **Je Fenster genau 1 Durchlauf** (AUG, S1, S2) mit fester Default-Konfiguration
  (§7.1: `touch_band_pct` 0,23, Abstand ≥ 3, Gegenkante ≥ 2, Split 50/50,
  SL-Puffer 0,05 USD fest). Keine `max_tage`-Sensitivitätsmatrix für C.
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
