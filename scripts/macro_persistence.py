# scripts/macro_persistence.py
"""Makro-Persistenz-Modul (Design v0.2, freigegeben 02.09.2026) - passiver Spiegel.
Signal-Loop-Erweiterung v0.4 (Mentor-Freigabe 03.09.2026): Kanten-Kapselung
(a_sym) + Ueberrannt-Filter mit overrun_tol = 0.5 x PENETRATION_TOL = 0.075
(mid) in resolve_active_edge - siehe docs/reclaim_signal_loop_design.md v0.4.
Haertung v0.4.x (Pfad A, Mentor-Freigabe 03.09.2026): B3 - resolve_active_edge
ohne side-Parameter (st.side = Single Source of Truth), update_touch erzwingt
t.side == st.side (ValueError); Type-Safety - MacroPhase-Protocol + frozen
SideSnapshot/PhaseSnapshot statt impliziter Dicts (siehe Design-Doku §3).

REIN LESENDES Beobachter-Modul: kein Eingriff in Phasen, Signale, Exits
oder Trades der Baseline. Es kapselt den phasen-uebergreifenden
Linien-Zustand (MacroLineState) als produktives, wiederverwendbares Modul
- extrahiert aus dem validierten Prototyp test/tmp_makro_state_proto.py
(dieser bleibt als Validierungs-Artefakt unangetastet).

Kernidee (Design v0.2):
  * MacroTouch      : kausal bestaetigter H/L-Pivot einer Phase (n=2)
  * MacroZone       : Preis-Zone einer Seite mit Phasen-Evidenz
  * MacroLineState  : persistenter Zonen-Pool JE Seite
  * update_touch    : Zone matchen/erzeugen; Zentrum = Remove-Tail-
                      Schnittmenge (R1)
  * on_phase_boundary: R4-Praezisierung - UP-Bruch durch B loescht UPPER-
                      Zonen mit center <= B, DOWN-Bruch loescht LOWER-Zonen
                      mit center >= B; Gegenseite persistiert (left_behind)
  * best_macro_anchor    : global bester Makro-Kandidat (R2-Tie-Break)
  * best_local_macro_anchor: distanzbegrenzte Anker-Abfrage (Mentor-Pflicht:
                      abs(center - current_price) <= max_dist)
  * macro_report   : passiver Spiegel-Report ueber ein Phasen-Fenster

Kausalitaets-Schutz (Arretierung 02.09.2026): Alle Anker-Abfragen liefern
frozen MacroAnchorInfo-Kopien bzw. SOFORT eingefrorene Texte/Werte - nie
Live-Referenzen auf mutable MacroZone-Objekte (der Snapshot-Mutations-Bug
der fruehen 3-Fenster-Diagnose ist damit konstruktiv ausgeschlossen).

Dieses Modul ist dependency-frei (nur pandas/dataclasses). Die
Baseline-Funktion level_schnittmenge wird injiziert (kein Zirkular-Import).

Aufruf (im Hauptskript):
    python scripts/tmp_phasen_volumen_profil.py --macro [--start=... --ende=...]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional, Protocol, Sequence

import numpy as np
import pandas as pd

# Typ-Alias: injizierte Baseline-Schnittmengen-Funktion
LevelSchnittmenge = Callable[
    [list[float] | np.ndarray, str, float, int, float], Optional[float]
]

Side = Literal["UPPER", "LOWER"]
BreakDir = Literal["up", "down"]

# Parameter (Design §7 - komplett, minimal)
MIN_ZONE_EVIDENCE: int = 2      # einziger neuer Kern-Parameter (v0.2)
DENSITY_BAND: float = 0.15      # Baseline (geerbt; nur fuer Zonen-Matching)
PENETRATION_TOL: float = 0.15   # = DENSITY_BAND (Signal-Loop E4, Wiederverwendung)
OVERRUN_TOL: float = 0.075      # v0.4 mid: 0.5 x PENETRATION_TOL (Mentor 03.09.)
MACRO_DIST_FACTOR: float = 12.0  # Signal-Loop E5: max_dist = Faktor x range_ref
_MIN_CLUSTER: int = 2           # Baseline MIN_CLUSTER (Remove-Tail-Replay)
_ERWEITERUNG_PCT: float = 1.0   # Baseline ERWEITERUNG_PCT (Remove-Tail-Replay)
MAX_PIVOTS_PER_ZONE: int = 100  # Baseline FENSTER_PIVOTS (Ring-Puffer)


# ============================================================================
# Datenvertrag (Design §4)
# ============================================================================

@dataclass(frozen=True, slots=True)
class MacroTouch:
    """Ein kausal bestaetigter Pivot-Test einer Seite (n=2, ts + 2 Bars)."""
    ts: pd.Timestamp
    price: float
    side: Side
    phase_id: int


@dataclass(slots=True)
class MacroZone:
    """Preis-Zone einer Seite mit Phasen-Evidenz (Cluster, band-breit)."""
    side: Side
    center: float
    prices: list[float] = field(default_factory=list)
    phases_tested: set[int] = field(default_factory=set)
    first_ts: Optional[pd.Timestamp] = None
    last_ts: Optional[pd.Timestamp] = None
    birth_phase: int = -1

    @property
    def evidence(self) -> int:
        """Anzahl verschiedener Phasen mit >= 1 Touch in der Zone."""
        return len(self.phases_tested)

    def kurz(self) -> str:
        return (f"{self.center:7.3f} ev{self.evidence} "
                f"{sorted(self.phases_tested)} n={len(self.prices)} "
                f"[{self.first_ts:%d.%m %H:%M}-{self.last_ts:%d.%m %H:%M}]")


@dataclass(frozen=True, slots=True)
class PhaseBoundaryEvent:
    """Kausales Phasenende (2-Close-Bruch), B = durchbrochene Kante."""
    ts: pd.Timestamp
    break_dir: BreakDir
    broken_level: Optional[float]
    ended_phase_id: int


@dataclass(slots=True)
class MacroLineState:
    """Persistenter, phasen-uebergreifender Linien-Zustand JE Seite."""
    side: Side
    zones: list[MacroZone] = field(default_factory=list)
    status: Literal["none", "standing", "left_behind"] = "none"
    last_break_ts: Optional[pd.Timestamp] = None

    def zone_kurz(self) -> str:
        if not self.zones:
            return "(leer)"
        return " | ".join(z.kurz() for z in sorted(
            self.zones, key=lambda z: z.center))


@dataclass(frozen=True, slots=True)
class MacroAnchorInfo:
    """Frozen Werte-Kopie einer MacroZone (Kausalitaets-Schutz: keine
    Live-Referenz auf den mutablen Zonen-Pool)."""
    center: float
    evidence: int
    phases_tested: tuple[int, ...]
    n_prices: int
    first_ts: Optional[pd.Timestamp]
    last_ts: Optional[pd.Timestamp]

    @classmethod
    def from_zone(cls, z: MacroZone) -> "MacroAnchorInfo":
        return cls(
            center=float(z.center),
            evidence=z.evidence,
            phases_tested=tuple(sorted(z.phases_tested)),
            n_prices=len(z.prices),
            first_ts=z.first_ts,
            last_ts=z.last_ts,
        )

    def kurz(self) -> str:
        if self.last_ts is None:
            ts_txt = ""
        else:
            ts_txt = f" [{self.first_ts:%d.%m %H:%M}-{self.last_ts:%d.%m %H:%M}]"
        return (f"{self.center:7.3f} ev{self.evidence} "
                f"{list(self.phases_tested)} n={self.n_prices}{ts_txt}")


class MacroPhase(Protocol):
    """Strukturelles Minimal-Profil einer Baseline-Phase (PhaseData).

    Nur die Attribute, die macro_replay/macro_report vom Phasen-Objekt
    lesen. Die volle PhaseData-Klasse bleibt Eigentum des Hauptskripts -
    dieses Modul bleibt dependency-frei (kein PhaseData-Import noetig).
    """
    start: pd.Timestamp
    ende: pd.Timestamp
    h_prices: list[float]
    h_ts: list[pd.Timestamp]
    l_prices: list[float]
    l_ts: list[pd.Timestamp]
    break_dir: Optional[BreakDir]
    brk_idx: Optional[int]
    brk_kante: Optional[float]


@dataclass(frozen=True, slots=True)
class SideSnapshot:
    """Eingefrorener Seiten-Zustand VOR den Phasen-Touches (Kausalitaets-
    Schutz: NUR immutable Werte/frozen Kopien - nie Live-Zonen-Referenzen).

    v0.4.x: ersetzt das implizite _phase_snapshot_texts-Dict (Type-Safety).
    """
    side: Side
    status: Literal["none", "standing", "left_behind"]
    n_zones: int
    zones_txt: str
    anchor_global: Optional[MacroAnchorInfo]
    d_global: Optional[float]
    anchor_local: dict[str, Optional[MacroAnchorInfo]]
    d_local: dict[str, Optional[float]]


@dataclass(frozen=True, slots=True)
class PhaseSnapshot:
    """Eingefrorener Phasen-Snapshot (Rahmen-Daten + je Seite ein
    SideSnapshot). v0.4.x: ersetzt das implizite macro_replay-Dict.
    """
    phase_idx: int
    start: pd.Timestamp
    ende: pd.Timestamp
    break_dir: Optional[BreakDir]
    brk_kante: Optional[float]
    current_price: float
    range_ref: Optional[float]
    upper: SideSnapshot
    lower: SideSnapshot


# ============================================================================
# Kern-Mechanik (Design §6)
# ============================================================================

def _recompute_center(zone: MacroZone,
                      level_schnittmenge: LevelSchnittmenge) -> None:
    """Zentrum = Remove-Tail-Schnittmenge ueber alle Zonen-Pivots (R1)."""
    typ = "H" if zone.side == "UPPER" else "L"
    c = level_schnittmenge(
        zone.prices, typ, DENSITY_BAND, _MIN_CLUSTER, _ERWEITERUNG_PCT,
    )
    if c is not None:
        zone.center = float(c)


def update_touch(st: MacroLineState, t: MacroTouch,
                 level_schnittmenge: LevelSchnittmenge) -> None:
    """Kausale Pivot-Verarbeitung: Zone matchen/erzeugen, Evidenz pflegen.

    B3-Invariante (v0.4.x, hart): t.side MUSS st.side entsprechen - ein
    falschseitiger Touch wird abgelehnt (ValueError) und kann den Ledger
    nicht still korrumpieren (kein zweiter Seiten-Kanal).
    """
    if t.side != st.side:
        raise ValueError(
            f"Touch side mismatch: t.side={t.side} != st.side={st.side}"
        )
    best: Optional[MacroZone] = None
    best_d = float("inf")
    for z in st.zones:
        d = abs(t.price - z.center)
        if d <= DENSITY_BAND and d < best_d:
            best, best_d = z, d
    if best is None:
        best = MacroZone(
            side=st.side, center=t.price, prices=[t.price],
            phases_tested={t.phase_id},
            first_ts=t.ts, last_ts=t.ts, birth_phase=t.phase_id,
        )
        st.zones.append(best)
    else:
        best.prices.append(t.price)
        if len(best.prices) > MAX_PIVOTS_PER_ZONE:      # Ring-Puffer (Baseline)
            best.prices.pop(0)
        best.phases_tested.add(t.phase_id)
        if best.first_ts is None or t.ts < best.first_ts:
            best.first_ts = t.ts
        best.last_ts = t.ts
        _recompute_center(best, level_schnittmenge)


def on_phase_boundary(st: MacroLineState, ev: PhaseBoundaryEvent) -> None:
    """R4-Praezisierung: nur durchschrittene Zonen der Bruch-Seite loeschen."""
    st.last_break_ts = ev.ts
    if ev.broken_level is None:
        return
    B = float(ev.broken_level)
    if st.side == "UPPER" and ev.break_dir == "up":
        st.zones = [z for z in st.zones if z.center > B]
        st.status = "standing"
    elif st.side == "LOWER" and ev.break_dir == "down":
        st.zones = [z for z in st.zones if z.center < B]
        st.status = "standing"
    elif st.side == "UPPER" and ev.break_dir == "down":
        st.status = "left_behind"      # Gegenseite persistiert
    elif st.side == "LOWER" and ev.break_dir == "up":
        st.status = "left_behind"      # Gegenseite persistiert


# ============================================================================
# Anker-Abfragen (Kausalitaets-Schutz: frozen Kopien)
# ============================================================================

def _pick_anchor(kandidaten: list[MacroZone], side: Side) -> Optional[MacroZone]:
    """R2-Tie-Break: max Evidenz, dann juengster last_ts, dann Richtung
    (UPPER: hoeheres Zentrum / LOWER: tieferes Zentrum)."""
    if not kandidaten:
        return None
    return max(
        kandidaten,
        key=lambda z: (z.evidence, z.last_ts or pd.Timestamp.min,
                       z.center if side == "UPPER" else -z.center),
    )


def best_macro_anchor(st: MacroLineState) -> Optional[MacroAnchorInfo]:
    """Global bester Makro-Kandidat (Evidenz >= MIN_ZONE_EVIDENCE; R2).

    Returns frozen MacroAnchorInfo-Kopie (nie Live-Referenz) oder None.
    """
    kandidaten = [z for z in st.zones if z.evidence >= MIN_ZONE_EVIDENCE]
    anch = _pick_anchor(kandidaten, st.side)
    return MacroAnchorInfo.from_zone(anch) if anch is not None else None


def best_local_macro_anchor(st: MacroLineState,
                            current_price: float,
                            max_dist: float,
                            side_tol: float = PENETRATION_TOL,
                            ) -> Optional[MacroAnchorInfo]:
    """Distanz- UND seitenbegrenzte Anker-Abfrage (Mentor-Pflicht, 02.09.2026).

    Ein Market Maker interessiert sich nicht fuer ein historisches
    High-Volume-Cluster meilenweit ausserhalb des aktuellen Handelsbereichs
    - solche Niveaus sind Makro-Targets fuer Mehrmonats-Trends, aber keine
    Kanten fuer M15-Reclaims. Daher:

      1. Kandidaten = |zone.center - current_price| <= max_dist
      2. Evidenz >= MIN_ZONE_EVIDENCE
      3. E5-Seiten-Konsistenz (v0.3): UPPER-Resistance muss UEBER dem Markt
         liegen, LOWER-Support UNTER dem Markt. Eine durchschrittene Zone
         (Preis weit jenseits) ist kein Reclaim-Setup mehr - sie hat ihre
         Rolle als Resistance/Support verloren (hoechstens Rollen-Tausch).
      4. R2-Tie-Break (max Evidenz, juengster last_ts, Richtung)

    E5-Seiten-Konsistenz (formal, v0.3):
        UPPER:  center >  current_price - side_tol
        LOWER:  center <  current_price + side_tol
    side_tol = PENETRATION_TOL (Wiederverwendung, kein neuer Freiheitsgrad).
    Die Toleranz ist das geometrische Dual von E4: Fuer jeden E4-passierenden
    UPPER-Bar gilt high <= edge + tol und damit close <= high -> edge >=
    close - tol. Der Filter entfernt also KEINEN E4-validierten Kandidaten,
    sondern nur Anker, die um mehr als tol UNTER dem Close liegen (vom Markt
    ueberrundet - z. B. P7: 65.994 vs. close 67.129). Ein striktes
    center > close wuerde dagegen next_bar-Tier-2-Reclaims toeten, deren
    Close bis zu tol ueber der Kante liegt (AUG 17.08 17:45 +6.90R).
    Der P5-Schutz bleibt intakt: Anker 66.364 > close 63.9 (weit ueber dem
    Markt) -> Kandidat.

    Args:
        st: Zonen-Pool der Seite (traegt die Seiten-Orientierung).
        current_price: aktueller Marktpreis (kausal, z. B. Close am
            Phasenstart / Signal-Bar).
        max_dist: maximale absolute Distanz zum Marktpreis.
        side_tol: Toleranz fuer die Seiten-Konsistenz (Default
            PENETRATION_TOL = DENSITY_BAND).

    Returns:
        Frozen MacroAnchorInfo-Kopie oder None (kein Kandidat in Reichweite
        bzw. kein seiten-konsistenter Kandidat ueber/unter dem Markt).
    """
    kandidaten = [
        z for z in st.zones
        if abs(z.center - current_price) <= max_dist
        and z.evidence >= MIN_ZONE_EVIDENCE
        and (
            (st.side == "UPPER" and z.center > current_price - side_tol)
            or (st.side == "LOWER" and z.center < current_price + side_tol)
        )
    ]
    anch = _pick_anchor(kandidaten, st.side)
    return MacroAnchorInfo.from_zone(anch) if anch is not None else None


# ============================================================================
# Operative Kanten-Auswahl (Signal-Loop-Design v0.4, E1-E5 + Kanten-Kapselung)
# ============================================================================

@dataclass(frozen=True, slots=True)
class ActiveEdgeDecision:
    """Unveraenderliche Kanten-Entscheidung fuer einen Signal-Bar (kausal).

    Ersetzt die implizite Kanten-Wahl (U_zone/L_zone) durch eine explizite,
    protokollierbare Entscheidung mit Tier-Herkunft und Penetrations-Status
    (Design docs/reclaim_signal_loop_design.md §3).
    """
    side: Side
    edge_price: float                    # operative Kante (Ausfuehrung)
    tier: Literal[1, 2]                  # 1 = Volume-Kante, 2 = Makro-Anker
    anchor: Optional[MacroAnchorInfo]    # Tier-2 frozen Kopie (nur tier==2)
    lokal_kante: float                   # U_zone/L_zone (Tier-1-Wert)
    bestaetigt: bool                     # Tier-1-Etablierung durch Pivot-Dichte (E2)
    penetriert: bool                     # Bar beruehrt Kante (E4-Semantik)
    bounces: int                         # Pivot-Tests <= DENSITY_BAND um edge (bis ts_k)
    current_price: float                 # kausaler Referenzpreis (Close Bar k)
    range_ref: Optional[float]           # kausale Range-Referenz (E5), fuer Audit


def _anchor_verdraengt_erlaubt(*, side: Side,
                               center: float,
                               lokal_kante: float,
                               current_price: float,
                               kapsel_tol: float,
                               overrun_tol: Optional[float]) -> bool:
    """Kanten-Kapselung v0.4 (D1-mid, Mentor 03.09.): Anker als Verdraenger?

    Ein Tier-2-Anker darf die unbestätigte lokale Volume-Kante nur
    verdrängen, wenn er die Bewegung in Signalrichtung ABRIEGELT - nicht,
    wenn er bereits überrannt ist (Typ "ueberrannt": Markt steht jenseits
    der Zone) oder signifikant hinter der lokalen Kante liegt.

      (a) Kanten-Kapselung (a_sym, wie LOWER-Lesart):
              center >= lokal_kante - kapsel_tol      (UPPER wie LOWER)
          Ein Anker, der um mehr als kapsel_tol UNTER der lokalen Kante
          liegt, ist kein Widerstand vor der Auktion (die atmende
          U_zone/L_zone ist bereits an ihm vorbeigezogen).

      (b) Ueberrannt-Filter (mid, overrun_tol = 0.5 x PENETRATION_TOL):
              UPPER: verwerfe wenn current_price >  center + overrun_tol
              LOWER: verwerfe wenn current_price <  center - overrun_tol
          Eine Zone, deren Marktpreis die Kante um mehr als die
          Pufferzone durchschritten hat, hat ihre Support-/Resistance-
          Rolle verloren (Reclaim = Stops an der Linie, kein Fade einer
          gebrochenen Linie). Institutional Fades schiessen 5-8 Cents
          uebers Level - overrun_tol 0.075 = 0.5 x DENSITY_BAND ist der
          kausal begruendete Puffer (kein neuer Freiheitsgrad).

    Der P5-Schutz-Anker 66.364 bleibt Verdraenger (66.364 >= 64.155-0.15
    und close 63.9 <= 66.364+0.075 -> abriegelnd). Die S2-stale-Anker
    P39/P49 (1.2-1.3 unter dem Markt, unterhalb der lokalen L_zone) und
    P7-ueberrannt (29.525, close 29.416 < 29.525-0.075) scheitern -> der
    E3-Fallback fuehrt die lokale Kante (Baseline-DNA).

    Args:
        side: Seite des Ankers.
        center: Anker-Zentrum (anch.center).
        lokal_kante: laufende lokale Volume-Kante (U_zone/L_zone).
        current_price: kausaler Referenzpreis (Close Bar k).
        kapsel_tol: Toleranz der Kanten-Kapselung (Default = penetration_tol).
        overrun_tol: Toleranz des Ueberrannt-Filters; None deaktiviert (b).

    Returns:
        True, wenn der Anker die lokale Kante verdrängen darf.
    """
    # (a) Kanten-Kapselung (a_sym)
    if center < lokal_kante - kapsel_tol:
        return False
    # (b) Ueberrannt-Filter (mid)
    if overrun_tol is not None:
        if side == "UPPER" and current_price > center + overrun_tol:
            return False
        if side == "LOWER" and current_price < center - overrun_tol:
            return False
    return True


def resolve_active_edge(
    *,
    st: MacroLineState,           # st.side = SSoT (B3, kein side-Argument)
    lokal_kante: float,
    phasen_prices: list[float],
    phasen_ts: list[pd.Timestamp],
    ts_k: pd.Timestamp,
    current_price: float,
    extreme: float,
    range_ref: Optional[float],
    level_schnittmenge: LevelSchnittmenge,
    max_dist_factor: float = MACRO_DIST_FACTOR,
    penetration_tol: float = PENETRATION_TOL,
    overrun_tol: Optional[float] = OVERRUN_TOL,
) -> Optional[ActiveEdgeDecision]:
    """Operative Kanten-Auswahl fuer einen Signal-Bar (E2-E6, v0.4).

    B3 (v0.4.x): Die Seiten-Orientierung kommt AUSSCHLIESSLICH aus st.side
    (Single Source of Truth) - es gibt keinen zweiten Seiten-Kanal:
      * E2:  typ = "H" if st.side == "UPPER" else "L"
      * E4:  Penetration UPPER edge < extreme <= edge+tol, LOWER symmetrisch
      * E5:  best_local_macro_anchor liest st.side (unveraendert)
      * E6:  _anchor_verdraengt_erlaubt(side=st.side, ...)

    Institutionelle Semantik (Signal-Loop-Design v0.1-v0.4, Mentor-Freigabe):
      * E2  Tier-1-Bestaetigung: Die lokale Pivot-Dichte (_linie, MIN_CLUSTER
           = 2) muss die Volume-Kante (U_zone/L_zone) tragen
           (|linie - lokal_kante| <= DENSITY_BAND). Sonst ist die Kante
           "weich" (volumetrisch verzogen, atmet ohne Struktur).
      * E3  Umschalt-Mechanik: Tier 1 fuehrt, wenn lokal bestaetigt; sonst
           uebernimmt Tier 2 = best_local_macro_anchor(st, current_price,
           max_dist). v0.4-Kanten-Kapselung (D1): Der gewaehlte Anker muss
           die Bewegung abriegeln (_anchor_verdraengt_erlaubt) - sonst wird
           er verworfen und der E3-Fallback fuehrt. E3-Fallback (v0.2):
           Kein Kandidat in Reichweite -> NICHT None (Arbeitsverweigerung),
           sondern Tier 1 mit der unbestätigten lokalen Kante (tier=1,
           bestaetigt=False) - kein Makro-Konflikt = die lokale Auktion
           fuehrt (Baseline-DNA).
      * E4  Penetrations-Gate NUR auf Tier 2 (Mentor §9.3): Tier 1 bleibt
           unberuehrt (Durchstich wie Baseline, keine Obergrenze). Tier 2 als
           diskrete Makro-Linie braucht zwingend Cent-Penetration
           (|extreme - edge| <= penetration_tol).
      * E5  max_dist = max_dist_factor x range_ref ist reine Kandidaten-
           Vorauswahl (kein Signal-Gate).

    Args:
        st: MacroLineState der Seite (Zustand NACH Phase p-1, inkl. R4);
            st.side traegt die Seiten-Orientierung (SSoT, B3).
        lokal_kante: U_zone (UPPER) bzw. L_zone (LOWER) der laufenden Volume-
            Zone an Bar k (Tier-1-Kante).
        phasen_prices: p.h_prices (UPPER) bzw. p.l_prices (LOWER) - VOLL;
            intern kausal bis ts_k gefiltert (kein Lookahead).
        phasen_ts: zugehoerige Zeitstempel.
        ts_k: aktueller Bar-Zeitstempel (kausal).
        current_price: Close an Bar k (Referenz fuer die Distanz-Abfrage).
        extreme: high[k] (UPPER) bzw. low[k] (LOWER) - Penetrations-Test.
        range_ref: kausale Range-Referenz (rolling 200, shift 1) an Bar k;
            None -> kein Tier 2 (keine Distanz-Schranke verfuegbar).
        level_schnittmenge: injizierte Baseline-Schnittmengen-Funktion.
        max_dist_factor: Faktor fuer max_dist (Default MACRO_DIST_FACTOR).
        penetration_tol: Toleranz fuer die Tier-2-Penetration (Default
            PENETRATION_TOL = DENSITY_BAND) UND fuer die Kanten-Kapselung.
        overrun_tol: Toleranz des Ueberrannt-Filters (Default OVERRUN_TOL =
            0.5 x PENETRATION_TOL = 0.075, mid). None deaktiviert den
            Ueberrannt-Filter (dann nur Kanten-Kapselung a_sym).

    Returns:
        ActiveEdgeDecision (frozen). Im Makro-Pfad NIE None (v0.2-Fallback:
        ohne bestaetigte lokale Kante UND ohne Tier-2-Anker wird die lokale
        Kante als Tier 1 gehandelt). Der Optional-Typ bleibt fuer den
        Null-Einfluss-Pfad (Konsument ohne injizierte States) erhalten.
    """
    # Kausal: nur Pivots bis ts_k (Pivot-Lag ist bereits in p.h_ts enthalten)
    prices_k = [float(pr) for pr, t in zip(phasen_prices, phasen_ts)
                if t <= ts_k]
    typ = "H" if st.side == "UPPER" else "L"

    # --- E2: Tier-1-Bestaetigung (lokale Pivot-Dichte traegt Volume-Kante?) ---
    linie: Optional[float] = None
    if prices_k:
        linie = level_schnittmenge(prices_k, typ, DENSITY_BAND,
                                   _MIN_CLUSTER, _ERWEITERUNG_PCT)
    bestaetigt = (linie is not None
                  and abs(float(linie) - lokal_kante) <= DENSITY_BAND)

    if bestaetigt:
        edge = float(lokal_kante)
        tier: Literal[1, 2] = 1
        anch: Optional[MacroAnchorInfo] = None
    else:
        # --- E3/E5: Tier 2 = distanzbegrenzter Makro-Anker ---
        anch = None
        if range_ref is not None and range_ref > 0:
            md = max_dist_factor * float(range_ref)
            anch = best_local_macro_anchor(st, current_price, md)
        # --- v0.4 Kanten-Kapselung (D1-mid): Nur abriegelnde Anker
        #     verdrängen die lokale Kante; sonst E3-Fallback (Tier 1). ---
        if (anch is not None
                and not _anchor_verdraengt_erlaubt(
                    side=st.side, center=anch.center,
                    lokal_kante=float(lokal_kante),
                    current_price=current_price,
                    kapsel_tol=penetration_tol,
                    overrun_tol=overrun_tol,
                )):
            anch = None
        if anch is not None:
            edge = anch.center
            tier = 2
        else:
            # --- E3-Fallback (v0.2): kein Makro-Konflikt -> lokale Auktion fuehrt.
            # Kein uebergeordnetes Level in Reichweite = der Markt laeuft frei;
            # die unbestätigte lokale Kante wird als Tier 1 gehandelt (Baseline-
            # DNA), NICHT geschwiegen. bestaetigt bleibt False als eindeutige
            # Fallback-Kennzeichnung (tier=1 ∧ bestaetigt=False). Der P5-Schutz
            # bleibt intakt: Dort existiert der Anker 66.364 (anch is not None),
            # der Fallback greift nicht, die Konter-Bars scheitern am E4-Gate.
            edge = float(lokal_kante)
            tier = 1

    # Bounces gegen die operative Kante (Semantik wie Baseline _bounce_nr:
    # 1 = aktueller Touch + Pivots <= DENSITY_BAND bis ts_k)
    bounces = 1 + sum(1 for pr in prices_k if abs(pr - edge) <= DENSITY_BAND)

    # --- E4: Penetration (nur Tier 2 begrenzt; Tier 1 unberuehrt) ---
    if tier == 1:
        penetriert = (extreme > edge) if st.side == "UPPER" else (extreme < edge)
    else:
        if st.side == "UPPER":
            penetriert = edge < extreme <= edge + penetration_tol
        else:
            penetriert = edge - penetration_tol <= extreme < edge

    return ActiveEdgeDecision(
        side=st.side, edge_price=edge, tier=tier, anchor=anch,
        lokal_kante=float(lokal_kante), bestaetigt=bestaetigt,
        penetriert=penetriert, bounces=bounces,
        current_price=current_price, range_ref=range_ref,
    )


# ============================================================================
# Kausales Replay + Spiegel-Report
# ============================================================================

def _zone_age_bars(z: MacroZone, ref_ts: pd.Timestamp) -> int:
    if z.first_ts is None:
        return 0
    return int((ref_ts - z.first_ts).total_seconds() // 900)


def _phase_snapshot_texts(st: MacroLineState,
                          current_price: float,
                          range_ref: Optional[float],
                          factors: tuple[float, ...]) -> SideSnapshot:
    """Sofort eingefrorener Seiten-Snapshot VOR Phasen-Touches.

    Liefert NUR immutable Werte/frozen Kopien (SideSnapshot) - nie
    Referenzen auf mutierbare Zonen (Kausalitaets-Schutz).
    """
    zones_txt = st.zone_kurz()
    anch_g = best_macro_anchor(st)
    lokal: dict[str, Optional[MacroAnchorInfo]] = {}
    d_lokal: dict[str, Optional[float]] = {}
    if range_ref is not None and range_ref > 0:
        for f in factors:
            md = f * float(range_ref)
            a = best_local_macro_anchor(st, current_price, md)
            lokal[f"{f:g}x"] = a
            d_lokal[f"{f:g}x"] = (abs(a.center - current_price)
                                  if a is not None else None)
    d_g = (abs(anch_g.center - current_price)
           if anch_g is not None else None)
    return SideSnapshot(
        side=st.side,
        status=st.status,
        n_zones=len(st.zones),
        zones_txt=zones_txt,
        anchor_global=anch_g,            # frozen Kopie
        d_global=d_g,
        anchor_local=lokal,              # frozen Kopien
        d_local=d_lokal,
    )


def macro_replay(phases: Sequence[MacroPhase],
                 df: pd.DataFrame,
                 level_schnittmenge: LevelSchnittmenge,
                 dist_ref: Optional[pd.Series] = None,
                 factors: tuple[float, ...] = (4.0, 8.0, 12.0),
                 ) -> tuple[MacroLineState, MacroLineState, list[PhaseSnapshot]]:
    """Kausales Phasen-Replay (passiver Spiegel) ueber ein Fenster.

    Fuer jede Phase (in Replay-Reihenfolge):
      1. Anker-Snapshot VOR den Touches der Phase (frozen, sofort
         eingefroren - nie Live-Referenzen).
      2. update_touch fuer alle kausal bestaetigten H-/L-Pivots.
      3. on_phase_boundary am Phasenende (R4, selektives Loeschen).

    Args:
        phases: Baseline-Phasen (strukturell MacroPhase: PhaseData,
            sortiert, kausal finalisiert).
        df: OHLCV-DataFrame der Baseline (Spalte "ts").
        level_schnittmenge: Baseline-Schnittmengen-Funktion (injiziert).
        dist_ref: kausale Range-Referenz ((high-low).rolling(200,min_periods
            =20).mean().shift(1)) - optional, nur fuer lokale Anker.
        factors: Distanz-Faktoren x range_ref fuer die lokalen Anker.

    Returns:
        (state_upper, state_lower, phasen_snapshots): Zwei Zonen-Pools nach
        dem vollstaendigen Replay und je Phase ein eingefrorener Snapshot
        (PhaseSnapshot, v0.4.x - keine impliziten Dicts mehr).
    """
    st_u = MacroLineState(side="UPPER")
    st_l = MacroLineState(side="LOWER")
    snapshots: list[PhaseSnapshot] = []
    ts_arr = df["ts"].to_numpy()
    close_arr = df["close"].to_numpy()
    range_arr = dist_ref.to_numpy() if dist_ref is not None else None

    for i_p, p in enumerate(phases):
        # Kausaler "aktueller Preis" am Phasenstart: Close des Start-Bars
        pos = int(np.searchsorted(ts_arr, p.start, side="left"))
        pos = min(pos, len(ts_arr) - 1)
        current_price = float(close_arr[pos])
        range_ref = (float(range_arr[pos])
                     if range_arr is not None and np.isfinite(range_arr[pos])
                     else None)

        # --- 1) Snapshot VOR den Touches (frozen) ---
        snap_u = _phase_snapshot_texts(st_u, current_price, range_ref, factors)
        snap_l = _phase_snapshot_texts(st_l, current_price, range_ref, factors)
        snapshots.append(PhaseSnapshot(
            phase_idx=i_p,
            start=p.start, ende=p.ende,
            break_dir=p.break_dir, brk_kante=p.brk_kante,
            current_price=current_price,
            range_ref=range_ref,
            upper=snap_u, lower=snap_l,
        ))

        # --- 2) Touches (kausal bestaetigte Pivots) ---
        for t, x in zip(p.h_ts, p.h_prices):
            update_touch(st_u, MacroTouch(t, float(x), "UPPER", i_p),
                         level_schnittmenge)
        for t, x in zip(p.l_ts, p.l_prices):
            update_touch(st_l, MacroTouch(t, float(x), "LOWER", i_p),
                         level_schnittmenge)

        # --- 3) Boundary (R4) ---
        if p.break_dir is not None and p.brk_idx is not None:
            brk_ts = df["ts"].iloc[p.brk_idx]
            ev = PhaseBoundaryEvent(
                ts=brk_ts, break_dir=p.break_dir,
                broken_level=p.brk_kante, ended_phase_id=i_p,
            )
            on_phase_boundary(st_u, ev)
            on_phase_boundary(st_l, ev)

    return st_u, st_l, snapshots


def _state_stats(st: MacroLineState) -> dict[int | str, int]:
    """Evidenz-Historie des Zonen-Pools (Schluessel 1/2/3 = int, '4+' = str)."""
    ev_hist: dict[int | str, int] = {1: 0, 2: 0, 3: 0, "4+": 0}
    for z in st.zones:
        e = z.evidence
        if e >= 4:
            ev_hist["4+"] += 1
        elif e in ev_hist:
            ev_hist[e] += 1
    return ev_hist


def macro_report(phases: Sequence[MacroPhase],
                 df: pd.DataFrame,
                 level_schnittmenge: LevelSchnittmenge,
                 dist_ref: Optional[pd.Series] = None,
                 factors: tuple[float, ...] = (4.0, 8.0, 12.0),
                 ) -> str:
    """Passiver Spiegel-Report (rein lesend, kein Signal-Einfluss).

    Zeigt je Phase die eingefrorenen Anker-Snapshots VOR den Touches:
    globaler Makro-Anker und distanzbegrenzte lokale Anker (Faktoren der
    kausalen rollierenden Range). Am Ende die Zonen-Bilanz des Fensters.

    Args:
        phases: Baseline-Phasen (PhaseData).
        df: OHLCV-DataFrame der Baseline.
        level_schnittmenge: injizierte Baseline-Funktion.
        dist_ref: kausale Range-Referenz (optional).
        factors: Distanz-Faktoren fuer die lokalen Anker.

    Returns:
        Mehrzeiliger Report (Konsolen-/Textausgabe).
    """
    if not len(df):
        return "macro: leere Daten"
    st_u, st_l, snaps = macro_replay(
        phases, df, level_schnittmenge, dist_ref, factors)
    out: list[str] = [
        "\n" + "=" * 118,
        "MACRO-PERSISTENZ-SPIEGEL (rein lesend, kein Signal-Einfluss)",
        "=" * 118,
        f"Fenster {df['ts'].min():%d.%m.%Y %H:%M} -> "
        f"{df['ts'].max():%d.%m.%Y %H:%M} | {len(phases)} Phasen | "
        f"{len(df)} Bars | MIN_ZONE_EVIDENCE {MIN_ZONE_EVIDENCE}",
    ]

    fakt_txt = (f" ({', '.join(f'{f:g}x' for f in factors)} "
                f"von range_ref {dist_ref.name if dist_ref is not None else 'n/a'})"
                if dist_ref is not None else "")
    for s in snaps:
        ph = f"P{s.phase_idx + 1}"
        brk = s.break_dir
        brk_txt = (f"{brk.upper()}-Bruch B={s.brk_kante:.3f}"
                   if brk is not None and s.brk_kante is not None
                   else "kein Bruch/Datenende")
        rng = (f"range_ref={s.range_ref:.3f}"
               if s.range_ref is not None else "range_ref=n/a")
        out.append(f"\n{ph} {s.start:%d.%m %H:%M}->{s.ende:%d.%m %H:%M}"
                   f" | close@Start {s.current_price:.3f} | {rng} | {brk_txt}")
        for side, sn in (("UPPER", s.upper), ("LOWER", s.lower)):
            if sn.n_zones == 0:
                out.append(f"  [{side} {sn.status}] (leer)")
                continue
            ag = sn.anchor_global
            ag_txt = (f"d={sn.d_global:.3f}" if ag is not None else "---")
            lok_txts: list[str] = []
            for f_key in sn.anchor_local:
                a = sn.anchor_local[f_key]
                if a is None:
                    lok_txts.append(f"{f_key}: --")
                else:
                    lok_txts.append(f"{f_key}: {a.kurz()} "
                                    f"(d={sn.d_local[f_key]:.3f})")
            lok_str = "  ".join(lok_txts) if lok_txts else "(kein range_ref)"
            g_kurz = ag.kurz() if ag is not None else "(kein ev>=" \
                f"{MIN_ZONE_EVIDENCE})"
            out.append(f"  [{side} {sn.status}] {sn.n_zones} Zonen | "
                       f"global {g_kurz} {ag_txt}")
            out.append(f"       lokal {lok_str}")
            out.append(f"       Ledger: {sn.zones_txt}")

    # --- Bilanz ---
    out.append("\n" + "-" * 118)
    out.append("ZONEN-BILANZ (nach Replay)")
    out.append("-" * 118)
    for st in (st_u, st_l):
        ev_hist = _state_stats(st)
        alters: list[int] = []
        if phases:
            ref = phases[-1].ende
            alters = [_zone_age_bars(z, ref) for z in st.zones]
        max_alt = max(alters) if alters else 0
        out.append(f"[{st.side}] am Ende {len(st.zones):3d} Zonen | "
                   f"Evidenz: ev1 {ev_hist[1]} | ev2 {ev_hist[2]} | "
                   f"ev3 {ev_hist[3]} | ev4+ {ev_hist['4+']} | "
                   f"max Alter {max_alt} B | Status {st.status}")
    out.append("=" * 118)
    out.append("HINWEIS: reiner Spiegel - kein Signal-/Exit-/Trade-Eingriff. "
               "Anker-Snapshots sind frozen Kopien (Kausalitaets-Schutz).")
    out.append("=" * 118)
    return "\n".join(out)
