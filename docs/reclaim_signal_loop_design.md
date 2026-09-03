# Signal-Loop-Design — Makro-Persistenz (Kanten-Auswahl im Reclaim-Loop)

> **Status:** v0.4 — **ARRETIERT (Mentor-Freigabe 03.09.2026), implementiert
> & 3-Fenster-validiert** (`scripts/macro_persistence.py` +
> `scripts/phasen_volumen_profil.py`).
> **v0.2-Änderung (02.09., nach OOS-Falsifikation):** E3-Fallback arretiert
> („kein Tier-2-Anker → Tier-1-Fallback statt `None`") — siehe §2/E3 + §2.1.
> **v0.3-Änderung (02.09., nach P7-Diagnose):** E5-Seiten-Konsistenz arretiert
> (UPPER-Anker muss über dem Markt liegen, LOWER darunter) — siehe §2/E5 + §2.2.
> **v0.4-Änderung (03.09., nach S2-Diagnose + D1/D2-Simulation, Mentor-
> Freigabe):** Kanten-Kapselung (D1-mid: a_sym + Überrannt-Filter mit
> `overrun_tol = 0.5 × PENETRATION_TOL = 0.075`) + asymmetrische Cooldown-
> Entkopplung (D2-asym: `last_bar_tier1`/`last_bar_tier2`) — siehe §2/E6 + §2.3.
> **Kommunikation:** Deutsch · **Code/Bezeichner:** Englisch.
> **Datei-Pfad:** `docs/reclaim_signal_loop_design.md`
> **Basis:** `docs/reclaim_makro_persistenz_design.md` (v0.2, FREIGEGEBEN) +
> `scripts/macro_persistence.py` (Spiegel, verifiziert).

---

## 1. Zweck & Abgrenzung

Das Makro-Persistenz-Modell (v0.2) führt einen phasen-übergreifenden
Linien-Zustand (`MacroLineState`) ein, der an der Phasengrenze die *nicht
gebrochene* Seite weiterträgt. Der passive `--macro`-Spiegel ist verifiziert
(Null-Einfluss 27/+24.97R, P5-Anker 66.364 ev2). Dieses Dokument spezifiziert
den **nächsten Schritt**: die operative Kanten-Auswahl im Signal-Loop
(`find_reclaim_signals`, Z. 964–1085), damit der Makro-Anker (Tier 2) genau
die Kausalitätslücke schließt, die in P5 zu 352-B-Blindheit und Trailing-
Konter-SHORTs führte.

**Nicht in diesem Dokument:**
- Änderungen an Phasen-Segmentierung, Exits (`_aufloesen`), SL/TP, Cooldown,
  CRV-Schwelle, POC-Filter — alle unverändert (Baseline-DNA).
- Der `--macro`-Spiegel (bleibt als Referenz/Report erhalten).

**Kern-Problem (institutionell):** Die Baseline feuert Reclaims gegen die
**laufende Volume-Zonen-Kante** `U_zone`/`L_zone` (VAH/VAL — „wo wurde
gehandelt?"). Diese Kanten **atmen** und können in einer jungen Phase
trailen (P5: 64.16 → 65.80), wodurch formale Bounces an einer wandernden
Kante entstehen. Die Makro-Persistenz baut auf der **Pivot-Schnittmengen-
Dichte** (`_linie`/`level_schnittmenge`) auf („wo wurde abgelehnt?"). Wer
beide vermischt, erzeugt Arbitrage-Rauschen. Die Auflösung ist eine klare
**zweistufige operative Kante** mit definierter Umschalt-Mechanik.

---

## 2. Architektur-Entscheidungen (arretiert, Freigabe 02.09.)

### E1 — Tier 1 bleibt die Volume-Zonen-Kante (minimal-invasiv)

**Tier 1 (lokal) = `U_zone`/`L_zone`** aus `compute_volume_zone(...)` —
exakt der Baseline-Status quo. Die Baseline funktioniert, weil VAH/VAL
atmen können; ein Wechsel auf `_linie` als Ausführungs-Kante würde die
Referenz (+24.97R AUG) zerschlagen (Mentor-Urteil).

### E2 — `_linie` (Pivot-Dichte) ist die Bestätigungs-Schwelle für Tier 1

Die laufende Pivot-Schnittmengen-Linie der Phase (MIN_CLUSTER=2-Semantik)
ist die **Deckungs-Instanz**: Eine Volume-Kante ist nur dann „etabliert",
wenn die Pivot-Dichte der Phase sie trägt.

**Tier-1-bestätigt** (formal):
```
tier1_bestaetigt(p, k, U_zone)  :=
    center = level_schnittmenge(p.h_prices bis ts_k, "H",
                                DENSITY_BAND, MIN_CLUSTER=2, 1.0)   # "_linie"
    center is not None  AND  |center - U_zone| <= DENSITY_BAND
```
Symmetrisch für LOWER mit `l_prices`/"L". Eine wandernde (trailing) Kante,
der die Pivot-Dichte nicht folgt, ist **nicht bestätigt** → Tier 2 greift.

### E3 — Umschalt-Mechanik (Tier 1 ⇄ Tier 2) + **Fallback (v0.2)**

```
operative Kante U_op(k) =
    Tier 1: U_zone(k),              falls tier1_bestaetigt(...)
    Tier 2: best_local_macro_anchor(state_u, current_price, max_dist),
                                    sonst, falls Anker in Reichweite
    Tier 1-Fallback: U_zone(k),     sonst (kein Anker) — NEU v0.2
```
- **Tier 1 übernimmt die Ausführung, sobald lokal bestätigt** (≥2-Pivot-
  Dichte trägt die Volume-Kante). Das ist exakt der institutionelle Standard:
  Vor dem 2. Test existiert lokal keine Akkumulation → das Makro-Gedächtnis
  (Tier 2) muss führen (Mentor-Urteil).
- **Tier 2 bleibt danach im Schatten** (Referenz im `ActiveEdgeDecision`,
  R5) — er blockiert nicht, er dokumentiert.
- **E3-Fallback (v0.2, ARRETIERT nach OOS-Falsifikation Σ −82.8R):** Ist
  **kein** Tier-2-Kandidat in `max_dist`-Reichweite (`anch is None`), wird
  **nicht geschwiegen**, sondern auf Tier 1 zurückgefallen:
  ```
  Wenn anch is None  ⇒  edge = lokal_kante, tier = 1, bestaetigt = False
  ```
  **Institutionelle Semantik (Mentor):** Kein übergeordneter Makro-Konflikt =
  der Markt läuft frei (keine alte Liquiditätswand im Weg) → die lokale
  Auktion (Tier 1 = `U_zone`/`L_zone`) führt unangefochten. Ein `None`
  (Schweigen) wäre Arbeitsverweigerung: Es bestraft das System dafür, dass
  Märkte dynamisch trenden und Liquiditätszonen atmen. Der OOS-Befund
  belegt: Beide Entfallen-Listen waren netto-GEWINNER (S1 +76.85R aus 28 G
  vs. 42 V, S2 +25.05R aus 12 G vs. 32 V) — der Filter selektierte einen
  wertvollen Baseline-Querschnitt weg (R-Asymmetrie: Gewinner +1.5…+17.8R
  vs. Verlierer −1R).
- **Fallback-Klassifikation (Datenvertrag):** `tier = 1` + `bestaetigt =
  False` ist der **eindeutige Schalter** für den Konsumenten:
  1. Keine künstliche 0.15-Penetrations-Hürde (E4 gilt NUR für diskrete
     Makro-Linien Tier 2 — Fallback = Tier 1 ⇒ reiner Durchstich wie Baseline).
  2. Baseline-Bounce-Hürde bleibt aktiv (`_bounce_ok = nb >= min_bounce`;
     die Tier-2-Ausnahme in `_bounce_ok` greift NICHT, weil `tier == 1`).
  3. Zustand vollständig transparent im Logging/Audit
     (`edge_decision.bestaetigt == False` ∧ `tier == 1` = Fallback).

### 2.1 P5-Schutz-Beweis (formal, v0.2)

Der P5-Schutz hängt **nicht** am `None`, sondern an der aktiven
Tier-2-Verdrängung MIT Penetrations-Gate:

```
P5-Konter-Bars (14.–17.08, Preis 63.9–65.9):
    anch = best_local_macro_anchor(st_u, close, 12 × range_ref)
         = 66.364 ev2 [P2,P4]      (|66.364 − 63.9| ≈ 2.46 ≤ 12×0.22 = 2.64)
    anch is NOT None  ⇒  Fallback greift hier NICHT  (Bedingung anch is None)
    edge = 66.364, tier = 2
    penetriert = (66.364 < hi[k] ≤ 66.364 + 0.15)?   NEIN (hi ≈ 64.x)
    ⇒ U_eff = None  ⇒  kein Signal  (P5-Falle geschlossen, unverändert)
```

**Korollar:** Der Fallback wird NUR in Zuständen aktiv, in denen v1 zu
`None` führte: (a) Cold-Start (kein ev≥2-Anker im State), (b) E2-Dichte-
Mismatch ohne Anker in 12×-Reichweite, (c) `range_ref = None` am
Datenanfang. In allen drei Fällen gibt es keinen Makro-Widerspruch zur
lokalen Auktion → Tier 1 muss handeln dürfen. Genau diese Fälle filterte
v1 fälschlich (AUG P2/P7/P9-Gewinner, S1/S2-Querschnitt).

### E4 — Penetrations-Gate (physische Berührung, nicht Distanz) — **NUR Tier 2**

**Das Signal-Gate ist die Penetration**, nicht die Startkurs-Distanz:
```
|extreme_k - edge_price| <= PENETRATION_TOL      # PENETRATION_TOL = DENSITY_BAND = 0.15
```
- SHORT: `U < hi[k] <= U + 0.15` (die Bar kitzelt die Kante von unten und
  stößt maximal 0.15 durch — Stops im Cent-Bereich werden liquidiert).
- LONG:  `L - 0.15 <= lo[k] < L`.
- Ein Durchschießen um 2$ (Breakout, kein Reclaim) erzeugt **kein** Signal.
- Der Rückschluss-Test bleibt unverändert (`cl[k] <= U` in_bar /
  `cl[k+1] <= U` next_bar — Baseline-Mechanik).

**Geltungsbereich (arretiert, Mentor §9.3 + v0.2-Fallback):** Das
Penetrations-Gate gilt **ausschließlich für Tier 2** (diskrete Makro-Linie
braucht Cent-Penetration als physischen Beleg). **Tier 1 — inklusive des
E3-Fallbacks (`bestaetigt = False`, `tier = 1`) — bleibt unberührt**
(reiner Durchstich `hi[k] > U` / `lo[k] < L` ohne Obergrenze, exakt
Baseline-DNA). Der Fallback darf keine künstliche 0.15-Hürde bekommen
(Mentor: die gilt nur für diskrete Makro-Linien, nicht für atmende
Volume-Kanten).

### E5 — `max_dist` = Kandidaten-Vorauswahl + **Seiten-Konsistenz (v0.3)**

```
max_dist = MACRO_DIST_FACTOR x range_ref(k)
range_ref(k) = (high-low).rolling(200, min_periods=20).mean().shift(1)   # kausal
MACRO_DIST_FACTOR = 12.0   (v1-Default, Review-Punkt)
```
Begründung: Market Maker interessieren sich nicht für Cluster meilenweit
außerhalb des Handelsbereichs (Mentor). Der P5-Spiegel zeigte: 66.364 lag
erst ab 12×range_ref in Reichweite (d=2.438 bei range_ref 0.220); ferne
Top-Zonen (63.818 ev3) blieben in allen AUG-Phasen außerhalb — korrekt.

**E5-Seiten-Konsistenz (v0.3, ARRETIERT nach P7-Diagnose):** Die
Kandidaten-Vorauswahl filtert zusätzlich auf den **Vektor** (nicht nur
radialen Abstand): Eine UPPER-Kante ist ein Widerstand, den der Kurs **von
unten** antestet — sie muss zwingend über dem aktuellen Markt liegen. Ein
LOWER-Anker (Support) darunter. Eine durchschrittene Zone (Preis weit
jenseits) hat ihre Rolle als Resistance/Support verloren — sie als
operative Kante zu erzwingen, ist markttechnischer Unsinn („keine
Resistance unter dem Geldkurs" — Mentor).

```
UPPER:  center >  current_price - side_tol     # side_tol = PENETRATION_TOL = 0.15
LOWER:  center <  current_price + side_tol
```

Die Toleranz `side_tol = PENETRATION_TOL` ist **kein neuer Freiheitsgrad**
(Wiederverwendung) und das **geometrische Dual von E4**: Für jeden
E4-passierenden UPPER-Bar gilt `high ≤ edge + tol`, also `close ≤ high ⇒
edge ≥ close − tol`. Der Filter entfernt damit **keinen einzigen**
E4-validierten Kandidaten, sondern nur Anker, die um mehr als `tol` UNTER
dem Close liegen (vom Markt überrundet). Ein striktes `center > close`
würde dagegen **next_bar-Tier-2-Reclaims töten**, deren Close bis zu `tol`
über der Kante liegt (AUG 17.08 17:45 +6.90R ist ein next_bar-Trade!).

### 2.2 P7-Beweis (formal, v0.3)

```
P7-Signal-Bar (20.08 02:00, close 67.129, U_zone 67.157):
    best_local_macro_anchor(st_u, 67.129, 12×0.219 = 2.63):
      Kandidaten radial: 66.579 ev2, 66.382 ev3, 66.206 ev2, 65.994 ev3, ...
      E5-Seiten-Konsistenz (UPPER, tol 0.15): center > 67.129 − 0.15 = 66.979?
        66.579 < 66.979 → verworfen; 66.382 < 66.979 → verworfen; ...
        → KEIN Kandidat über dem Markt
    ⇒ anch = None  ⇒  E3-Fallback  ⇒  edge = U_zone 67.157, tier = 1
    ⇒ P7-Gewinner (20.08 02:15 +4.26R) feuert wieder (Baseline-Verhalten)
```

**Gegenprobe P5 vs. P7:**
| Fall | Kurs | Anker | center vs. Markt | Folge |
|---|---|---|---|---|
| P5 (14.–17.08) | 63.92 | 66.364 | 66.364 > 63.92 (über dem Markt) | Kandidat → Tier 2 → E4-Schutz aktiv ✓ |
| P7 (20.08) | 67.13 | 65.994 | 65.994 < 67.13 (unter dem Markt) | verworfen → anch=None → E3-Fallback → U_zone ✓ |

**Korollar:** In neuen-Hoch-Territorium (alle Makro-UPPER-Zonen unter dem
Preis, z. B. P7 nach dem Ausbruch über 66.5) existiert definitionsgemäß
kein UPPER-Makro-Widerstand → Tier 2 schweigt → die lokale Auktion führt
(Tier 1 / Fallback). Das ist institutionell exakt richtig: freier Markt
ohne übergeordnete Liquiditätswand = lokale Kante handeln.

### E6 — Kanten-Kapselung (D1-mid) + Cooldown-Entkopplung (D2-asym), v0.4

**Ausgangslage (S2-Diagnose 02.09., wasserdicht):** Alle 7 entfallenen
S2-Gewinner sind LONG. Zwei Fehlerklassen:
- **Klasse A — Kanten-Verdrängung → E4-Fail (4/7):** Der Tier-2-Anker
  verdrängt die atmende lokale L_zone, obwohl die Bar die L_zone sauber
  penetriert, den Anker aber nicht erreicht (P7: Anker 29.525 liegt ÜBER
  dem Close 29.416 = überrannt; P39/P49: Anker 1.2–1.3 UNTER dem Markt =
  fern-left_behind).
- **Klasse B — Cooldown-Killer (5/7):** v0.3-NEU-Signale (4× Tier-2-Magnet
  des Januar-Ankers 29.706) belegen `last_bar["LONG"]` 1–9 Bars vor dem
  Baseline-Signal → Block über den gemeinsamen Cooldown.

**D1-mid — Kanten-Kapselung (Klasse A):** Ein Tier-2-Anker verdrängt die
unbestätigte lokale Kante nur, wenn er die Bewegung ABRIEGELT. Zwei
Bedingungen (im `resolve_active_edge`-E3-Zweig nach der Anker-Auswahl):

```
(a) Kanten-Kapselung (a_sym):   center >= lokal_kante - penetration_tol
    (UPPER wie LOWER: der Anker liegt nicht signifikant UNTER der lokalen
    Kante — die atmende Volume-Kante ist nicht an ihm vorbeigezogen)
(b) Überrannt-Filter (mid):     UPPER: current_price <= center + overrun_tol
                                LOWER: current_price >= center - overrun_tol
    overrun_tol = 0.5 x PENETRATION_TOL = 0.075
```

Scheitert der beste Anker → `anch = None` → E3-Fallback (lokale Kante als
Tier 1, Baseline-DNA). **Marktmechanik (Mentor-Urteil 03.09.):** Ein
Reclaim an einer echten Makro-Linie geschieht nicht centgenau im Vakuum —
institutionelle Fades schießen 5–8 Cents übers Level, bevor die Liquidität
absorbiert wird. Wer bei 0.001 $ Überschuss sofort „Trendbruch!" schreit,
wird von Market Makern bei jedem Stop-Run rasiert. `0.075 = 0.5 ×
DENSITY_BAND` ist der kausal begründete Puffer (kein neuer Freiheitsgrad).
Ein strikter Filter (`c_sym0`, tol=0.0) wäre Curve-Fitting: Er tötet den
AUG-Kern-Trade (Tier-2-Reclaim 66.364, +6.90R). Der P5-Schutz-Anker 66.364
bleibt Verdränger (66.364 ≥ 64.155−0.15 und close 63.9 ≤ 66.364+0.075).

**D2-asym — asymmetrische Cooldown-Entkopplung (Klasse B):** Getrennte
Zähler je Tier (in `find_reclaim_signals`):
```
Tier-1-Signal:  setzt last_bar_tier1;  sperrt Tier 2 für 12 Bars
                (Tier 2 prüft last_bar_tier2 UND last_bar_tier1)
Tier-2-Signal:  setzt last_bar_tier2;  sperrt Tier 1 NIE
```
Begründung (Mentor, „D2-asym ist Pflicht"): Tier-1-Baseline-Trades haben
Vorrang und dürfen nicht durch spekulative Tier-2-Antestate im Cooldown
verhungern — das stellt die Alpha-Basis des Gesamtsystems sicher.
Baseline-Isolation: Ohne injizierte States (`st_u/st_l = None`) ist die
Entscheidung immer `None` → `_cooldown_ok`/`_cooldown_set` arbeiten auf
`last_bar_tier1` = exakt die alte gemeinsame Kette (bitgenau).

### 2.3 P7/P26/P49-Beweis (formal, v0.4)

```
P7 (04.04 19:15, close 29.416, L_zone 29.359):
    Anker-Kandidat 29.525 ev2 (radial + E5 + ev>=2 erfüllt)
    (b) Überrannt: close 29.416 < 29.525 - 0.075 = 29.450  → verworfen
    ⇒ anch = None ⇒ E3-Fallback ⇒ edge = L_zone 29.359, tier = 1
    ⇒ Baseline-LONG-P7 (+9.39R am 09.04) feuert wieder ✓

P49 (05.11, close 47.19, L_zone 47.174):
    Anker-Kandidat 45.978 ev4 (fern-left_behind)
    (a) Kapselung: 45.978 < 47.174 - 0.15 = 47.024  → verworfen
    ⇒ anch = None ⇒ E3-Fallback ⇒ lokale L_zone 47.174 (Baseline) ✓

P26 (17.09, close 41.38, L_zone 41.359):
    Anker 41.373 ev2 liegt direkt an der Auktion, NICHT überrannt
    (close 41.38 >= 41.373 - 0.075), NICHT hinter der L_zone
    → Tier-2-Verbleib schadet nicht (Signal via E4 an der L_zone nahe)
    ⇒ P26 (+3.10R) ist zurück (6/7; nur P27 +2.01R fehlt, Anker 41.347
    klebt 0.024 über dem Close = kein signifikanter Überrannt-Fall,
    legitimer Kompromiss laut Mentor-Analyse)

AUG-P5-Schutz bleibt intakt: Anker 66.364 über dem Markt in
Bewegungsrichtung („riegelt die Konter-SHORTs ab") — der legitime
Verdrängungsfall (E6-Bedingungen erfüllt).
```

---

## 3. Typisierter Datenvertrag (keine impliziten Dicts)

```python
# scripts/macro_persistence.py (Erweiterung, nach Freigabe)
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass(frozen=True, slots=True)
class ActiveEdgeDecision:
    """Unveraenderliche Kanten-Entscheidung fuer einen Signal-Bar (kausal).

    Ersetzt die implizite Kanten-Wahl (U_zone/L_zone) durch eine explizite,
    protokollierbare Entscheidung mit Tier-Herkunft und Penetrations-Status.
    """
    side: Literal["UPPER", "LOWER"]
    edge_price: float                      # operative Kante (Ausfuehrung)
    tier: Literal[1, 2]                    # 1 = Volume-Kante (auch Fallback), 2 = Makro-Anker
    anchor: Optional[MacroAnchorInfo]      # Tier-2 frozen Kopie (Schatten), sonst None
    lokal_kante: Optional[float]           # U_zone/L_zone (Tier-1-Wert, falls vorhanden)
    bestaetigt: bool                       # Tier-1-Etablierung (E2);
                                           # False ∧ tier==1 = E3-Fallback (v0.2)
    penetriert: bool                       # |extreme - edge| <= PENETRATION_TOL (E4, nur Tier 2)
                                           # Tier 1/Fallback: reiner Durchstich extreme >/< edge
    bounces: int                           # Pivot-Tests <= DENSITY_BAND um edge (bis Bar k)
    current_price: float                   # kausaler Referenzpreis (Close Bar k)
    range_ref: Optional[float]             # kausale Range-Referenz (E5), fuer Audit
```

**Fallback-Zustands-Semantik (v0.2, eindeutig):**

| `tier` | `bestaetigt` | Bedeutung | Konsumenten-Regeln |
|---|---|---|---|
| 1 | True | Echter Tier-1 (Dichte trägt Kante) | Baseline (Durchstich, `min_bounce`) |
| 2 | False | Tier-2-Makro-Anker verdrängt | Penetrations-Gate E4, keine Bounce-Hürde (§9.4) |
| **1** | **False** | **E3-Fallback (kein Anker)** | **Baseline (Durchstich, `min_bounce`) — unterscheidbar im Audit** |

Die Entscheidungs-Regel im Code ist dann die **Negation** der v1-Logik:
```
if bestaetigt:
    tier = 1                      # echter Tier 1
elif anch is not None and _anchor_verdraengt_erlaubt(...):  # E6 (v0.4)
    edge = anch.center; tier = 2  # Tier 2 (E4-Gate greift)
else:
    edge = lokal_kante; tier = 1; bestaetigt bleibt False   # Fallback v0.2
```
v0.4-Kapselung: Auch ein radial/E5-legitimer Anker wird verworfen, wenn er
die Bewegung nicht abriegelt (E6 a/b) — dann führt der E3-Fallback die
lokale Kante (Klasse-A-Heilung, Baseline-DNA).

**Schnittstellen-Vertrag (Bar-Schleife) — v0.4.x-Härtung (03.09.2026):**

```python
# B3-Härtung (v0.4.x, 03.09.2026): Der Parameter `side` ist ENTFALLEN.
# st.side ist die alleinige autoritative Quelle (Single Source of Truth):
# E2-typ, E4-Penetration, E5-Seiten-Konsistenz und E6-Kapselung leiten
# sich aus st.side ab. Ein Aufrufer wählt den State pro Seite (st_u/st_l);
# eine Divergenz zwischen Parameter und State ist konstruktiv unmöglich.
def resolve_active_edge(
    *,
    st: MacroLineState,           # st.side = "UPPER"/"LOWER" (SSoT, B3)
    lokal_kante: float,           # U_zone (UPPER) / L_zone (LOWER) (Tier-1-Wert)
    phasen_prices: list[float],   # p.h_prices bzw. p.l_prices (VOLL; kausal bis ts_k)
    phasen_ts: list[pd.Timestamp],
    ts_k: pd.Timestamp,           # aktueller Bar (kausal)
    current_price: float,         # Close Bar k (Distanz/E5/Overrun)
    extreme: float,               # high[k] (UPPER) / low[k] (LOWER) (E4)
    range_ref: Optional[float],   # rolling 200, shift 1; None -> kein Tier 2
    level_schnittmenge: LevelSchnittmenge,       # injiziert (kein Zirkular-Import)
    max_dist_factor: float = MACRO_DIST_FACTOR,
    penetration_tol: float = PENETRATION_TOL,
    overrun_tol: Optional[float] = OVERRUN_TOL,
) -> Optional[ActiveEdgeDecision]:
    """Operative Kanten-Auswahl fuer einen Signal-Bar (E2-E6, v0.4).

    Die Seiten-Orientierung kommt AUSSCHLIESSLICH aus st.side:
      * E2:  typ = "H" if st.side == "UPPER" else "L"
      * E4:  Penetration UPPER edge < extreme <= edge+tol, LOWER symmetrisch
      * E5:  best_local_macro_anchor liest st.side (unveraendert)
      * E6:  _anchor_verdraengt_erlaubt(side=st.side, ...)
    Liefert IMMER eine Entscheidung (nie None im Makro-Pfad; E3-Fallback
    v0.2). Optional bleibt nur fuer den Null-Einfluss-Pfad (keine States).
    """
```

**B3-Invariante (v0.4.x-Härtung):** Die Kante `MacroLineState` ist
seiten-tragend (`st.side`). Es gibt **keinen** zweiten Seiten-Kanal. Jeder
Aufrufer injiziert den State der Seite, die er scannt (`st_u` für UPPER,
`st_l` für LOWER). `update_touch` erzwingt die Invariante hart:
`if t.side != st.side: raise ValueError(...)` — ein falschseitiger Touch
kann den Ledger nicht still korrumpieren.

**Erweiterte Signal-Signatur (kompatibel, Default = Baseline):**

```python
def find_reclaim_signals(
    df: pd.DataFrame,
    p: PhaseData,
    st_u: Optional[MacroLineState] = None,   # None -> exakt Baseline
    st_l: Optional[MacroLineState] = None,
    ...                                     # bestehende Parameter unveraendert
) -> List[ReclaimSignal]:
```

`ReclaimSignal` erhält zwei **zusätzliche Schatten-Felder** (Default None,
kein Einfluss auf `_aufloesen`):

```python
@dataclass(slots=True)
class ReclaimSignal:
    ...                                     # bestehende Felder unveraendert
    edge_decision: Optional[ActiveEdgeDecision] = None   # Schatten (Audit)
    macro_active: bool = False               # True = Tier-2-Signal (neue Signale)
```

---

## 4. Kausale Phasen-Integration (Hook in Z. 1088–1093)

**Reihenfolge-Problem:** Der `MacroLineState` muss beim Eintritt in Phase p
bereits den Zustand **nach Phase p−1** (inkl. R4-Boundary) tragen, damit die
Bar-Schleife ab Bar 0 den Makro-Anker kennt. Die Touches von p dürfen erst
**nach** dem Signal-Scan von p in den State (sonst Lookahead: ein Pivot bei
Bar k ist erst ab k+2 bestätigt, und die Signale von p laufen während p).

```
# Ersatz fuer Z. 1088-1093 (nach Freigabe):
_macro_u = MacroLineState(side="UPPER")
_macro_l = MacroLineState(side="LOWER")
reclaim_signals: List[ReclaimSignal] = []

for _pi, _p in enumerate(phases, 1):
    # 1) R4-Boundary der VORHERIGEN Phase (falls gebrochen) in den State
    if _pi > 1:
        _prev = phases[_pi - 2]
        if _prev.break_dir is not None and _prev.brk_idx is not None:
            _ev = PhaseBoundaryEvent(
                ts=df["ts"].iloc[_prev.brk_idx],
                break_dir=_prev.break_dir,
                broken_level=_prev.brk_kante,
                ended_phase_id=_pi - 2,
            )
            on_phase_boundary(_macro_u, _ev)
            on_phase_boundary(_macro_l, _ev)

    # 2) Signal-Scan der Phase mit Makro-Sicht (Tier 2 in jungen Phasen)
    for _s in find_reclaim_signals(df, _p, _macro_u, _macro_l):
        _s.phase = _pi
        reclaim_signals.append(_s)

    # 3) Touches der Phase NACH dem Scan in den State (Evidenz fuer Folge-Phasen)
    for _t, _x in zip(_p.h_ts, _p.h_prices):
        update_touch(_macro_u, MacroTouch(_t, float(_x), "UPPER", _pi - 1),
                     level_schnittmenge)
    for _t, _x in zip(_p.l_ts, _p.l_prices):
        update_touch(_macro_l, MacroTouch(_t, float(_x), "LOWER", _pi - 1),
                     level_schnittmenge)
```

**Kausalitäts-Invarianten:**
1. State beim Scan von p = Zustand nach Phase p−1 (Boundary p−1 eingerechnet,
   Touches von p **nicht**).
2. Bounce-Zählung innerhalb von p nutzt `p.h_prices`/`p.l_prices` bis `ts_k`
   (wie `_bounce_nr` heute) — gegen die **operative Kante**, nicht gegen U_zone.
3. `range_ref(k)` ist strikt kausal (rolling 200, shift 1) — identische
   Referenz wie `vol_ref`/Spiegel.

---

## 5. Kanten-Auswahl in der Bar-Schleife (Ersatz Z. 976–984)

Heutige Logik (Z. 973–984):
```python
vz = _laufende_zone(df, p, k)                    # U, L, POC
is_candidate = (hi[k] > U) or (lo[k] < L)        # ohne Obergrenze
nb_h, nb_l = _bounce_nr(p.h_prices, ..., U, L)   # Bounces gegen U_zone
```

Neue Logik (nur wenn `st_u`/`st_l` übergeben; sonst exakt heute):
```python
vz = _laufende_zone(df, p, k)
if vz is None: continue

# Kanten-Entscheidungen (E2-E6) — v0.2: dec ist NIE None im Makro-Pfad
# B3 (v0.4.x): der State trägt die Seite; kein side-Argument mehr.
dec_u = resolve_active_edge(st=st_u, lokal_kante=vz.U_zone, ...)
dec_l = resolve_active_edge(st=st_l, lokal_kante=vz.L_zone, ...)

# SHORT-Zweig: Signal-Freigabe = Penetration/Durchstich der operativen Kante
#   dec_u.tier == 1 (bestätigt ODER Fallback): U_eff = dec_u.edge_price bei
#     Durchstich hi[k] > edge (keine 0.15-Hürde) — Baseline-DNA.
#   dec_u.tier == 2: U_eff = dec_u.edge_price nur bei E4-Penetration
#     (|hi[k] - edge| <= 0.15).
if dec_u is not None and dec_u.penetriert and dec_u.edge_price < hi[k]:
    U_op = dec_u.edge_price
    # Rückschluss, POC-Filter, cooldown, CRV, TP1/TP2 wie bisher gegen U_op
    # bounce_nr = dec_u.bounces (gegen U_op)
    # Bounce-Hürde: tier==1 (auch Fallback) -> nb >= min_bounce;
    #               tier==2 -> keine Hürde (Mentor §9.4)
    _bounce_ok = (dec_u.bounces >= min_bounce) or (dec_u.tier == 2)
    # edge_decision=dec_u, macro_active=(dec_u.tier == 2)

# LONG-Zweig: symmetrisch mit dec_l
```

**Wichtige Design-Konsequenz:** `is_candidate` wird durch das
Penetrations-/Durchstich-Gate ersetzt. Tier-2-Kanten brauchen die
Cent-Penetration (E4); Tier 1 und der Fallback behalten den reinen
Baseline-Durchstich. Ein Bar, der eine Tier-2-Kante um mehr als 0.15
durchstößt (Breakout), erzeugt **kein** Reclaim-Signal — institutionell
korrekt (Reclaim = Stops an der Makro-Kante, kein Durchmarsch).

---

## 6. Parameter (komplett, minimal — Erweiterung zu v0.2 §7)

| Parameter | Wert | Herkunft |
|---|---|---|
| `DENSITY_BAND` | 0.15 | Baseline (unverändert) |
| `MIN_CLUSTER` | 2 | Baseline (Tier-1-Bestätigung E2) |
| `MIN_ZONE_EVIDENCE` | 2 (Phasen) | Makro-Persistenz v0.2 (unverändert) |
| `PENETRATION_TOL` | 0.15 = DENSITY_BAND | **NEU** (E4) — Wiederverwendung, kein neuer Freiheitsgrad; zugleich `kapsel_tol` der Kanten-Kapselung (E6a) |
| `OVERRUN_TOL` | 0.075 = 0.5 × PENETRATION_TOL | **NEU** (E6b/mid, v0.4) — Überrannt-Puffer, kausal abgeleitet (Fades 5–8 Cents), kein neuer Freiheitsgrad |
| `MACRO_DIST_FACTOR` | 12.0 | **NEU** (E5) — Review-Punkt, nur Tier-2-Vorauswahl |
| `MAX_PIVOTS_PER_ZONE` | 100 | Baseline (Ring-Puffer) |
| Cooldown D2-asym | `last_bar_t1`/`last_bar_t2` | **NEU** (v0.4) — getrennte Tier-Zähler, `MIN_SIGNAL_ABSTAND_BARS` unverändert |

**Anti-Overfit-Check:** `OVERRUN_TOL` ist ein Wiederverwendungs-Alias
(0.5 × `PENETRATION_TOL`) ohne eigenen Freiheitsgrad — die 0.075 ist die
kausal begründete Pufferzone (institutionelle Fades 5–8 Cents über dem
Level), keine optimierte Konstante. `MACRO_DIST_FACTOR` ist keine Signal-
Schwelle, sondern eine großzügige Regions-Vorauswahl (12×range_ref ≈ 2.6$
bei AUG) — sie selektiert Zonen, nicht Signale. Die D2-asym-Cooldowns
verändern keine Schwelle, nur die Zähler-Kopplung (Tier-1-Vorrang).
Kein Bar-Decay, keine Gewichtskaskade.

---

## 7. Erwartetes Verhalten im Worked Example P5 (AUG)

| Kausaler Zeitpunkt | Baseline heute | Mit operativer Kante (erwartet) |
|---|---|---|
| P5-Start (14.08 03:00) | U_zone trailt (64.16), Bounces formal | Tier 1 NICHT bestätigt → Tier 2 = 66.364 (Makro). Noch keine Penetration → kein Signal |
| 14.–16.08 (Preis 64–65.9) | Trailing-Konter-SHORTs an 64.x/65.x (5× −1R) | Keine Penetration von 66.364±0.15 → **keine Signale** (P5-Falle geschlossen) |
| 17.08 17:15 (66.538) | isolierter Pivot, ignoriert | Penetration von 66.364+0.15? 66.538 > 66.514 — Durchstich zu tief? Rückschluss? → Signal nur bei sauberem Reclaim + bounces ≥ 2 |
| 17.08 19:00 (66.399) | **jetzt** Sprung auf 66.399/66.468 | Penetration 66.399 ≤ 66.514, Rückschluss → **Reclaim gegen 66.364** (Tier 2), bounces gegen Makro-Kante |
| P5-Ende (DOWN-Bruch) | U weg (Reset) | UPPER persistiert (left_behind), LOWER geleert — State für P6 |

**Ziel-Metrik:** Die 5 P5-Konter-SHORTs (Akzeptanzfall 1) entfallen; die
Gewinner an der 66.4x-Zone bleiben (wirtschaftlich, 1–2 Bars versetzt —
wie im S3-Store, aber jetzt über die Baseline-Schnittmengen-Kante).

---

## 8. Validierungsplan (nach Freigabe, in `test/`)

1. **Null-Einfluss:** `find_reclaim_signals(df, p)` ohne `st_u`/`st_l`
   (Default None) → AUG exakt **27 Sig / +24.97R / 44 %** (unverändert).
2. **A/B-Isolation:** Lauf mit States (Tier-1/Tier-2-Kanten) über separates
   Test-Skript (`test/reclaim_signal_loop_ab.py`) — Vergleich Bar für Bar:
   welche Signale entfallen (P5-Konter?), welche kommen hinzu (66.4x-
   Reclaims?), welche bleiben identisch (Tier-1-bestätigte Phasen).
3. **Akzeptanzfälle:** (1) 5 P5-Konter-SHORTs entfallen; (2) Gewinner an
   66.28/66.4x bleiben (wirtschaftlich); (3) früh-stabile Phasen (R2_U/R3_U/
   R4_U) unverändert — dort ist Tier 1 bestätigt, Tier 2 greift nie.
4. **v0.2-Fallback-Regression (Kernziel des OOS-Fixes):** Die drei v1-
   Fehlfilter-Fälle müssen zurückkehren bzw. entfallen:
   - AUG **P2 11.08 +4.59R** (Cold-Start): muss wieder feuern (kein Anker
     in Phase 2 → Fallback Tier 1).
   - AUG **P7 20.08 +4.26R / P9 24.08 +2.96R** (E2-Dichte-Mismatch ohne
     Anker): müssen wieder feuern.
   - **P5-Konter bleiben entfallen** (Anker 66.364 existiert → kein
     Fallback → Schutz aktiv, §2.1-Beweis).
   - Erwartung: AUG von 21/+20.62R (v1) Richtung Baseline − nur die
     P5-Konter-Loser + den einen v1-Neu-Loser → idealerweise
     **> +24.97R** (Baseline ohne die 4 Konter-Loser).
   - **v0.2-IST (02.09.): AUG 23 Sig / +23.91R (Delta −1.06R)** — P2/P9
     zurück, P5-Konter eliminiert, ABER P7 +4.26R noch entfallen
     (Tier-2-Override durch überrundeten Anker 65.994 < close 67.13).
     → v0.3-E5-Seiten-Konsistenz nötig.
5. **v0.3-E5-Regression (Seiten-Konsistenz):**
   - **P7 20.08 02:15 +4.26R muss zurückkehren** (kein UPPER-Anker über
     67.13 → anch=None → E3-Fallback → U_zone 67.157).
   - **P5-Schutz unangetastet** (Anker 66.364 > close 63.9 → über dem
     Markt → Tier-2-Kandidat; 4 Konter-Loser bleiben eliminiert).
   - **Tier-2-next_bar-Gewinner 17.08 17:45 +6.90R bleibt** (Toleranz
     `center ≥ close − tol` statt strikt — Beweis §2.2: E4-Dual).
   - **v0.3-IST (02.09.): AUG 24 Sig / +28.17R (Delta +3.20R GEGENÜBER
     Baseline!)** — Entfallen 6 (4 P5-Konter-Loser + P5 18:45 +6.71R
     [ersetzt durch früheren Tier-2 17:45 +6.90R] + P7 19.08 21:45 −1R
     [ersetzt durch Tier-2 19.08 21:15 −1R]), Neu 3 (+6.90R Tier-2,
     −1R Tier-1 65.798, −1R Tier-2 66.382). **P2/P7/P9 alle zurück.**
6. **3-Fenster-OOS:** S1/S2 mit `--macro-live` + Fallback + E5: Erwartung
   **nahe Baseline** (die entfallenen Netto-Gewinner-Querschnitte kehren
   zurück), abzüglich der echten P5-ähnlichen Schutzfälle + neuer
   Tier-2-Trades. Ziel: kein −50R/−29R-Delta mehr; Rest-Delta muss aus
   nachweisbaren Schutz-/Anker-Wirkungen stammen (Audit der Entfallen-/
   Neu-Listen).
7. **Lookahead-Audit:** State beim Scan von p enthält keine Touches von p
   (Invariante §4.1); range_ref strikt shift(1).
8. **v0.4-IST (03.09., produktive scripts/-Läufe — exakt reproduziert):**
   | Fenster | Baseline | `--macro-live` v0.4 (mid_D2a) | Ziel | Status |
   |---|---|---|---|---|
   | AUG | 27 / +24.97R | **25 Sig / +34.87R** (Δ +9.90R) | ≈ +34.87R | ✓ P5 4/4, T2-66.364 +6.90R da |
   | S1 | 201 / +197.26R | **199 Sig / +199.65R** (Δ +2.40R) | +199.65R | ✓ |
   | S2 | 210 / +99.88R | **216 Sig / +93.70R** (Δ −6.17R) | +93.70R | ✓ 6/7 Gewinner zurück, nur P27 +2.01R entfallen |
   | **S1+S2** | +297.14R | **+293.35R** | ≥ +292.14R | ✓ Marge +1.21R |
   Bitgenauigkeit ohne Flag: **27 Sig / +24.97R / 44 %** (Null-Einfluss-Beweis).

---

## 9. Standard-Artefakte (verbindliche Default-Ausgaben der Pipeline)

> **Stand v0.4.x (03.09.):** Jeder produktive Durchlauf von
> `scripts/phasen_volumen_profil.py` erzeugt **ohne Sonderflags** zwei
> Standard-Artefakte unter `test/` — sie sind die verbindliche,
> reproduzierbare Ausgabe jedes Laufs (Referenz-Verankerung der
> §8-Zielzahlen). Die Legacy-Artefakte (`scripts/phasen_volumen_profil.png`
> bzw. `.txt`) bleiben daneben aktiv (Parallelbetrieb, getrackt).

| Artefakt | Default-Pfad | Inhalt |
|---|---|---|
| Statistik- & Trade-Report | `test/stats_trades_<FENSTER>.txt` | Kennzahlen-Kopf + vollständiger Trade-Log je Modus (§9.2) |
| Standard-Chart | `test/phasen_volumen_profil_<FENSTER>.png` | Preis-Chart mit Kanten, Reclaim-Signalen, Overlays (§9.3) |

### 9.1 Fenster-Label (Namens-Schlüssel)

`fenster_label(start, ende)` bildet die bekannten Referenzfenster auf
kompakte Labels ab: **AUG** (`2026-08-10`→`2026-08-28`), **S1**
(`2026-02-05`→`2026-08-28`), **S2** (`2025-01-01`→`2025-12-01`); unbekannte
Fenster erhalten ein datumsbasiertes Fallback-Label (`YYYYMMDD_YYYYMMDD`).
Das Label steckt in beiden Standard-Dateinamen — AUG/S1/S2-Läufe
überschreiben sich nie gegenseitig.

### 9.2 .txt-Report (`export_stats_trades`, rein lesend)

- **Aufbau:** Ein Abschnitt je Modus — der **Baseline**-Abschnitt läuft
  immer; mit `--macro-live` kommt der **Macro-Live**-Abschnitt hinzu
  (Kennung „Stand v0.4.x: OVERRUN_TOL=0.075, D2-asym, A3/B3").
- **Kopfbereich:** Fenster/Modus + Kennzahlen (`_stats_kennzahlen`):
  Signale/Trades gesamt, Long/Short, Win-Rate, Summe R, Avg Win, Avg Loss,
  Profit-Faktor (`unendl.` bei keinem Verlust-Trade). Ableitung strikt aus
  den bestehenden Trade-Ergebnissen (resultat + `r_mult` der Auflösung),
  keine abweichenden R-Formeln.
- **Trade-Log:** Tabellarisch je Trade: `Trade_Nr | Phase_ID | Bar_Signal |
  Bar_Entry | Type | Direction | Entry_Price | Tier | R_Result |
  Cumulative_R` — damit ist jeder Trade bar-genau auditierbar.
- **Override:** Der .txt-Pfad ist via `--stats-txt=<pfad>` überschreibbar;
  das Fenster-Label wird dann aus dem Datei-Stem abgeleitet
  (`_label_aus_stem`, z. B. `stats_trades_AUG` → `AUG`).
- **Verifikation:** Die §8-IST-Zeilen (AUG 25/+34.87R, S1 199/+199.65R,
  S2 216/+93.70R; Baseline bitgenau 27/+24.97R) sind in den Reports
  bitgenau reproduziert (Baseline- UND Macro-Live-Abschnitt).

### 9.3 Chart (`render_standard_chart`, rein lesend)

Layout wie der Hauptskript-Chart (Abschnitt 7): High/Low-Balken,
Phasen-Hintergrund (`axvspan`), Volume-Zonen (Tier-1-Kanten
`U_zone`/`L_zone`/`POC` + Sub-Berge), Reaktions-Extreme, Moves-Pfeile.
Zusätzlich im Standard-Chart:

- **Tier-2-Kanten:** distanzbegrenzte Makro-Anker (`edge_decision.tier ==
  2`) als **lila gestrichelte** Linien über ihre Nutzungs-Spanne.
- **Reclaim-Signale:** Dreiecke — SHORT unten (`v`, rot `#c00000`), LONG
  oben (`^`, grün `#1a7d1a`); **gefüllt = `in_bar`**, offen = `next_bar`;
  Tier-2-Signale zusätzlich mit Ring.
- **Baseline-Kontrolllage** (nur `--macro-live`): Baseline-Signale als
  **offene Kreise** — Differenz-Sicht: nur Kreis = entfallen, nur Dreieck
  = neu.
- **Benchmark-Overlay** (nur AUG): exakte historische Referenz-Musterlinien
  `USER_LINES_AUG` (`R1_U`..`R4_L`), Zeitfenster via `np.searchsorted`.
- **Statistik-Box** (`stat_lines`) oben links.
- **Rendering-Trennung:** `SignalMarkerStil` (frozen Dataclass) statt
  Ad-hoc-Plot-Dicts; die Funktion liest ausschließlich aus `df/phases/
  moves/signals` und manipuliert **keinen** Berechnungszustand.

### 9.4 Verifikation & Sichtprüfung (03.09.)

- `.txt`-Reports: `test/stats_trades_{AUG,S1,S2}.txt` — bitgenau gegen §8.
- `.png`-Charts: `test/phasen_volumen_profil_{AUG,S1,S2}.png` —
  Zähl-Kontrolle im Konsolen-Hinweis (AUG-Baseline: 27 Dreiecke, 0 Kreise;
  AUG-`--macro-live`: 25 Dreiecke + 27 Kreise, 3 Tier-2-Ringe, 8
  Referenz-Linien; S1/S2: 1 Modus-Abschnitt, keine Referenz-Linien).

---

## 10. Offene Review-Punkte (vor Implementierung)

1. **Tier-1-Bestätigung (E2):** Schwelle `|center - U_zone| <= DENSITY_BAND`
   ist der v1-Vorschlag. Alternativen: (a) direkter Dichte-Test ≥2 Pivots in
   0.15 um U_zone ohne `_linie`-Umweg; (b) `MIN_ESTABLISH`-Semantik
   (kombinierte Touches ≥4). Empfehlung: E2 wie spezifiziert — nutzt die
   validierte `_linie`-Mechanik, keine neue Zählung. **Mit v0.2-Fallback
   entschärft:** E2 entscheidet nur noch zwischen „echtem Tier 1" und
   „Tier 2/Fallback" — ein E2-Fehlurteil (Kante weich, aber kein Anker)
   führt nicht mehr zum Signalverlust, sondern zum Baseline-Fallback.
2. **`MACRO_DIST_FACTOR`:** 12× als Default (P5-Beleg: 66.364 erst ab 12× in
   Reichweite). Review: zu eng (verpasst späte Reclaims nach großem Move)
   oder zu weit (fremde Regionen)? Kalibrierung erst nach A/B-Lauf, nie vorab.
   **Mit v0.2-Fallback entschärft:** Ein zu enges `max_dist` führt nicht mehr
   zu `None`, sondern zum Tier-1-Fallback — die Region-Vorauswahl ist damit
   nur noch ein „Tier-2-Eingriffsradius", kein Signal-Gate.
   **Mit v0.3-E5 zusätzlich entschärft:** Auch ein zu weites `max_dist` ist
   unschädlich — die Seiten-Konsistenz verwirft Zonen jenseits des Markts
   (überrundete Resistance/Support), bevor sie als Kandidat schaden können.
3. **Penetrations-Gate auf Tier 1?** ~~Vorschlag~~ **ARRETIERT (Mentor §9.3 +
   v0.2):** Nur Tier 2 bekommt das `PENETRATION_TOL`-Gate. Tier 1 — inklusive
   des E3-Fallbacks — bleibt exakt Baseline (Durchstich ohne Obergrenze).
   Ein Gate auf Tier 1 würde auch bestätigte Phasen verändern = Baseline-
   Referenz zerschlagen; ein Gate auf den Fallback würde denselben
   Selektivitätsfehler reproduzieren, den der OOS-Befund falsifiziert hat.
4. **Bounce-Zählung gegen Makro-Kante:** `bounces` zählt Pivots ≤ 0.15 um
   die Makro-Kante (inkl. Pivots aus VOR-Phasen? Nein — nur Phase p bis
   ts_k, wie `_bounce_nr`). Die Evidenz ≥ 2 (Phasen) steckt bereits in der
   Tier-2-Auswahl; die Bounce-Schwelle MIN_RECLAIM_BOUNCE=2 bleibt die
   Intra-Phase-Reclaim-Reife. Review: reicht die Phasen-Evidenz allein
   (Makro-Zone ist ja schon ≥2-Phasen-getestet), oder braucht es zusätzlich
   ≥1 Intra-Phase-Test vor dem ersten Tier-2-Signal?
   **Mit v0.2-Fallback präzisiert:** Die Bounce-Hürde greift nur für
   `tier == 1` (bestätigt ODER Fallback); Tier 2 bleibt ausgenommen
   (Mentor §9.4). Der Fallback erbt damit automatisch die Baseline-
   Bounce-Reife — konsistent mit seiner „Tier-1-DNA".

---

## 11. Implementierungsreihenfolge (nach Freigabe)

> **Stand v0.4 (03.09.):** Schritte 1–5 sind für v0.2/v0.3 abgeschlossen.
> Für v0.4 folgten (alle ARRETIERT & implementiert):
> 6. `scripts/macro_persistence.py`: `OVERRUN_TOL`-Konstante, Helfer
>    `_anchor_verdraengt_erlaubt` (E6 a/b) + `overrun_tol`-Parameter in
>    `resolve_active_edge` (Filter im E3-Zweig → bei Scheitern E3-Fallback).
> 7. `scripts/phasen_volumen_profil.py`: `_cooldown_ok`/`_cooldown_set`
>    (D2-asym, `last_bar_t1`/`last_bar_t2`) in `find_reclaim_signals`;
>    Baseline-Pfad (keine States) bleibt bitgenau auf `last_bar_t1`.
> 8. Verifikations-/Benchmark-Lauf §8/8 — alle Zielzahlen exakt erreicht.
> 9. Standard-Artefakte (§9): `export_stats_trades` (`.txt`-Report) +
>    `render_standard_chart` (`.png`-Chart) + Default-Erzeugung Block 7f —
>    jeder Lauf ohne Sonderflags schreibt `test/stats_trades_<FENSTER>.txt`
>    und `test/phasen_volumen_profil_<FENSTER>.png` (Parallelbetrieb mit
>    den getrackten Legacy-Artefakten, `--stats-txt=`-Override).

1. **Review dieses Dokuments** durch User/Mentor (v0.3: E3-Fallback,
   E5-Seiten-Konsistenz, Entscheidungs-Tabelle §3, P5-/P7-Beweis §2.1/§2.2).
2. **`scripts/macro_persistence.py` anpassen (E3-Fallback + E5-Seiten):**
   In `resolve_active_edge` den `return None`-Zweig (bei `anch is None`)
   durch den Tier-1-Fallback ersetzen:
   `edge = lokal_kante, tier = 1, bestaetigt bleibt False, anchor = None`.
   In `best_local_macro_anchor` die E5-Seiten-Konsistenz ergänzen
   (`UPPER: center > price − tol`, `LOWER: center < price + tol`;
   `side_tol = PENETRATION_TOL`, Default-Parameter). Der
   `Optional[ActiveEdgeDecision]`-Rückgabetyp bleibt (Null-Einfluss-
   Pfad ohne States), aber im Makro-Pfad wird nie `None` zurückgegeben.
3. **`find_reclaim_signals` prüfen/anpassen:** Der Konsument (Z. 1038/1050)
   behandelt die Fallback-Decision automatisch korrekt (`tier == 1` →
   `_bounce_ok` Baseline, `penetriert` = Durchstich). Verifikation, dass
   der Fallback-Zustand im Delta-Report als eigener Typ erscheint
   (Audit-Transparenz, `bestaetigt=False` ∧ `tier=1`).
4. **Phasen-Schleife Z. 1088–1093:** Sequenz Boundary(p−1) → Scan(p) →
   Touches(p) in den State; aktivierbar NUR via neuem CLI-Flag
   (z. B. `--macro-live`), Default aus = Null-Einfluss.
5. **Validierung §8** in `test/` + Doku-Update (`docs/reclaim.md`).

---

## 12. Versions-Historie

| Version | Datum | Änderung |
|---|---|---|
| v0.1 | 02.09.2026 | Erster Entwurf E1–E5 (Tier 1/2, Penetrations-Gate, max_dist) |
| v0.2 | 02.09.2026 | **E3-Fallback arretiert** nach OOS-Falsifikation (Σ −82.8R): kein `None` bei fehlendem Tier-2-Anker → Tier-1-Fallback (`tier=1`, `bestaetigt=False`); P5-Schutz-Beweis §2.1; Entscheidungs-Tabelle §3; E4-Geltungsbereich präzisiert (NUR Tier 2); §8-Regression + §11-Reihenfolge angepasst |
| v0.3 | 02.09.2026 | **E5-Seiten-Konsistenz arretiert** nach P7-Diagnose: `best_local_macro_anchor` filtert auf Vektor statt nur Radius (UPPER `center > close − tol`, LOWER `center < close + tol`; `tol = PENETRATION_TOL` = E4-Dual, kein neuer Freiheitsgrad). P7 +4.26R kehrt zurück (überrundeter Anker 65.994 verworfen → Fallback → U_zone 67.157); P5-Schutz unangetastet; next_bar-Tier-2 +6.90R bleibt (Toleranz statt strikt). **AUG-IST: 24 Sig / +28.17R = Baseline +3.20R** |
| v0.4 | 03.09.2026 | **Kanten-Kapselung (D1-mid) + Cooldown-Entkopplung (D2-asym) arretiert & implementiert** nach S2-Diagnose (Klasse A: Anker-Verdrängung/E4-Fail; Klasse B: Cooldown-Killer). E6: `_anchor_verdraengt_erlaubt` (a_sym-Kapselung `center ≥ lokal_kante − tol` + Überrannt-Filter `overrun_tol = 0.5 × PENETRATION_TOL = 0.075`); D2-asym: `last_bar_t1`/`last_bar_t2` in `find_reclaim_signals` (Tier 1 sperrt Tier 2, nie umgekehrt). **IST (produktive Läufe): AUG 25/+34.87R (P5 4/4, T2-66.364 +6.90R), S1 199/+199.65R, S2 216/+93.70R (6/7), S1+S2 = +293.35R ≥ +292.14R; Baseline bitgenau 27/+24.97R.** c_sym0 (strikt tol=0.0) als Curve-Fitting verworfen (tötet AUG-T2-66.364); P27 +2.01R als legitimer Kompromiss akzeptiert. |
| v0.4.x | 03.09.2026 | **Härtung (Pfad A, Mentor-Freigabe) — Doku + Code synchron:** §3-Signatur `resolve_active_edge` ohne `side`-Parameter (B3: `st.side` = Single Source of Truth; E2-typ/E4-Penetration/E6-Kapselung leiten sich aus `st.side` ab); B3-Invariante hart erzwungen in `update_touch` (`raise ValueError` bei `t.side != st.side`); A3-Bounds-Guard `k + 2 <= p.i_ende` in beiden `next_bar`-Zweigen (kein IndexError am Datenende, Variante 1 — keine in_bar-Umdeutung); Type-Safety: `MacroPhase`-Protocol + frozen `SideSnapshot`/`PhaseSnapshot` statt impliziter Dicts. Null-Einfluss: Baseline bitgenau 27 Sig/+24.97R. |
| v0.4.x | 03.09.2026 | **Standard-Artefakte verankert (Referenz-Verankerung, Parallelbetrieb mit Legacy):** neuer Abschnitt §9 — jeder Pipeline-Lauf erzeugt ohne Sonderflags `test/stats_trades_<FENSTER>.txt` (Baseline- + optional Macro-Live-Abschnitt, `--stats-txt=`-Override) und `test/phasen_volumen_profil_<FENSTER>.png` (Tier-1/2-Kanten, Dreiecke gefüllt=`in_bar`/offen=`next_bar` + Tier-2-Ring, Baseline-Kreise bei `--macro-live`, AUG-Referenz-Overlay `USER_LINES_AUG`). `fenster_label` AUG/S1/S2/Fallback; Rendering strikt rein lesend (`SignalMarkerStil` frozen Dataclass). Verifiziert bitgenau gegen §8-IST; §9–§11 umnummeriert zu §10–§12. |
