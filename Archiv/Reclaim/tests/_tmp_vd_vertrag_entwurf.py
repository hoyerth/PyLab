# -*- coding: utf-8 -*-
"""V-D DATENVERTRAG -- ENTWURF (NICHT ausgefuehrt, NICHT arretiert).

Reine Wertedomaene. Kein Engine-Import, keine Seiteneffekte, kein I/O.
Der bestehende Adapter (``backtest_lab/phasen_regime_adapter.py``) bleibt
UNVERAENDERT (SHA 0f3f8765...); dieser Entwurf ist rein additiv.

Zweck
-----
Traegt die vier Phase-0-Befunde:

* B1 ``box_end_bar`` ist auf ein August-Datum gebrannt (S2/H2 = 0 Bars).
* B2 S1s H2-Schenkel ist kalendarisch identisch mit AUG (Index-Offset).
* B3 die Adapter-Niveaus sind ABSOLUTE Preise (2025: 28.29..56.53 -> leer).
* B4 ``kid`` ist ein fensterlokaler Auto-Increment (Surrogatschluessel).

Zweigleisige Adressierung
-------------------------
* Ebene 1 (AUG, ARRETIERT): Bindung ueber ``kind="kid"`` + absolute
  Provenienz-Niveaus. Unveraendertes Bestandsrecht.
* Ebene 2 (generisch, S1/S2): Bindung ueber ``kind="rolle"`` -- die Kante
  wird per SEMANTISCHER ROLLE im kausalen Scan aufgeloest, nie per Zaehler.

Gemeinsame Wahrheit
-------------------
Die Rollenaufloesung MUSS fuer die **AUSSEN-Grenze** dieselbe Sortier- und
Existenz-Semantik nutzen wie der Engine-Pool
(``pool.sort(key=basis_bei(k), reverse=(seite=="OBEN"))``). Genau die
Abweichung davon hat den M6/Hook-1-Bandkonflikt erzeugt (0.12 % vs. 0.75 %).
Deshalb: EINE Resolver-Funktion, Fail-Loud-Validierung.

Fuer die **INNENraenge** ist diese Semantik dagegen semantisch falsch
(Phase 1.2) -- siehe ``RangModus``.

Stand v0.24 (Ratifiziert 2026-09-11, vier Punkte)
-------------------------------------------------
1. **Zielmechanismus (1.1):** ``GEGENKANTE_RELATIV`` bindet auf die
   **phaseneigene** Gegenkante (``GegenkantenWahl.PHASE_EIGEN``), nicht auf
   die Engine-Makrowand. Messlage: ``SEG_BODEN`` 17 Trades / +65.504879 R
   (99.50 % der Baseline) gegen ``MAKRO_ENGINE`` 18 Trades / +51.255680 R.
2. **Ranking (1.2):** Innenraenge sortieren nach ``NAEHE`` zum Signalpreis
   (``RangModus.NAEHE``), nicht nach absoluter Basishoehe.
3. **Kausalitaet (2.1):** ``KantenSicht`` kapselt den Pre-Birth-Lookahead
   (``basis_bei`` faellt vor der Pivot-Bestaetigung auf ``wicks[0][1]``
   zurueck). Kein Engine-Eingriff -- die Engine bleibt bei SHA
   ``4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a``.
4. **Sleep-Bypass (2.2):** ``RECLAIM_AT_OPENING`` filtert nur Kausalitaet,
   nie den Schlafstatus -- das Ereignis folgt dem Bruch (K82: Fenster
   (1074, 1174), Reclaim Bar 1075).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Mapping, Optional, Sequence, Tuple

__all__ = [
    "KantenRolle", "NiveauModus", "GegenkantenWahl", "RangModus",
    "SchliessModus", "OeffnungsModus", "PhasenDynamikModus",
    "KantenReferenz", "KantenSicht", "KantenKat", "KantenSichtKat",
    "SchliessKriterium", "OeffnungsTrigger", "SegmentVD",
    "PhasenDynamikErgebnis", "VDAdapterEntwurf",
]

# Kantenkatalog am Bar k: (kid, seite, kausale_basis_bei_k)
KantenKat = Sequence[Tuple[int, str, float]]


@dataclass(frozen=True, slots=True)
class KantenSicht:
    """Kausale Sicht auf EINE Kante am Bar k (Adapter-Kapselung, Phase 2.1).

    Die Engine liefert ``basis_bei(k)`` AUCH vor der Bestaetigung des
    level-definierenden Pivots; der Rueckfall auf ``wicks[0][1]`` projiziert
    dabei den ERSTEN Docht (= Zukunft) in die Historie. Nachgewiesen in
    ``test/_tmp_gegenkante_probe.py``::

        K77.erster_pivot_bar = 934  (Geburt 991)
        existiert(K77, 903)  = False
        K77.basis_bei(903)   = 68.3920   <-- Zukunfts-Docht

    Genau der Trade ``(903, SHORT)`` war in der ``SEG_BODEN``-Messung (Z2)
    von diesem Wert abhaengig. Eine Engine-Korrektur wuerde die Arretierung
    ``4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a``
    brechen (Entscheidung 2026-09-11, Frage 3: **Adapter-seitig, kein V019**).

    Die Sicht ist ein **Bar-Schnappschuss**: ``basis`` ist ``basis_bei(k)``
    fuer genau dieses ``k``. Der Adapter baut den Katalog je Bar neu.

    Args:
        kid: Kanten-ID.
        seite: ``"OBEN"`` oder ``"UNTEN"``.
        basis: ``basis_bei(k)`` der Engine am Bar k (vor Bestaetigung
            ungueltig -- siehe ``basis_kausal``).
        erster_pivot_bar: Level-definierender Pivot (Engine-Semantik).
        erster_docht_bar: Bar des ersten Dochts (``wicks[0][0]``) -- Herkunft
            des Engine-Rueckfalls, rein dokumentarisch.
        erster_docht_preis: Preis des ersten Dochts (``wicks[0][1]``) --
            identisch zum Engine-Rueckfall.
    """

    kid: int
    seite: str
    basis: float
    erster_pivot_bar: int
    erster_docht_bar: Optional[int] = None
    erster_docht_preis: Optional[float] = None

    def kausal_existent(self, k: int) -> bool:
        """Existenz exakt wie ``_se_trades::_existiert`` (Pivot + 2 <= k + 1).

        Args:
            k: Signal-Bar.

        Returns:
            True gdw. der Pivot am Bar k bestaetigt ist.
        """
        return self.erster_pivot_bar + 2 <= k + 1

    def basis_kausal(self, k: int) -> Optional[float]:
        """``basis_bei(k)`` -- oder ``None`` VOR der Pivot-Bestaetigung.

        Damit ist der Pre-Birth-Lookahead strukturell ausgeschlossen: statt
        des Zukunfts-Dochts liefert der Adapter ``None``. Der Aufrufer MUSS
        den ``None``-Fall als "Kante nicht adressierbar" behandeln
        (fail-loud), nicht als 0.0 und nicht als Fallback-Preis.

        Args:
            k: Signal-Bar.

        Returns:
            Kausale Basis oder None.
        """
        if not self.kausal_existent(k):
            return None
        return float(self.basis)


# Kantenkatalog mit kausaler Existenz-Vorbedingung (Phase 2.1)
KantenSichtKat = Sequence[KantenSicht]


# =============================================================================
# 1  ADRESSIERUNG
# =============================================================================


class KantenRolle(Enum):
    """Semantische Rolle einer Kante im kausalen Scan.

    Zwei Familien -- bewusst getrennt, weil sie unterschiedliche Aufloeser
    brauchen:

    RANGFAMILIE (Bar-Rang im sortierten Pool, ``hook_1``-aufloesbar):

    * ``AUSSEN_OBEN``   = hoechste existierende OBEN-Basis (Rang 0).
    * ``INNEN_OBEN_1``  = zweithoechste existierende OBEN-Basis (Rang 1).
    * ``AUSSEN_UNTEN``  = tiefste existierende UNTEN-Basis (Rang 0).
    * ``INNEN_UNTEN_1`` = zweittiefste existierende UNTEN-Basis (Rang 1).

    Das ist exakt die Reihenfolge, die ``_kandidat`` intern als ``pos``
    vergibt -- bewusst identisch, damit Hook 1a/1b und der Rollenbegriff
    nicht desynchronisieren koennen.

    EINSCHRAENKUNG (Phase 1.2, ratifiziert 2026-09-11): Rang 0
    (``AUSSEN_*``) ist unter beiden Sortiersemantiken identisch (die
    aeusserste Wand ist zugleich die am weitesten entfernte) -- deshalb war
    die Rangfamilie fuer die Aussengrenze reproduzierbar (Beweis 1: R0 == R1
    bit-identisch). Fuer die **Innenraenge** gilt die Engine-Sortierung
    (``RangModus.ABSOLUT``) NICHT: eine "Naehe"-Rangfolge
    (``RangModus.NAEHE``) beschreibt die relevante Innenwand der
    Handelszone, nicht die naechste Makro-Kante. K82 besetzt in H2 die
    Raenge 10/11 und ist damit ueber die Rangfamilie ohnehin NICHT
    adressierbar (111/267 Bars nicht existent) -- fuer diese Wand ist die
    Ereignisfamilie zustaendig.

    EREIGNISFAMILIE (kein Rang -- ``hook_4``-aufloesbar, braucht Marktdaten):

    * ``RECLAIM_AT_OPENING`` = die Kante, an der am Oeffnungs-Bar ``k`` ein
      Reclaim ``>= 1`` stattfindet. Gemessen: AUG-Bar 1075, K82,
      ``STUFE_1_IN_BAR`` (Monatstief 67.4200). K82 besetzt in H2 die Raenge
      10/11 und ist damit ueber die Rangfamilie NICHT adressierbar -- der
      Rangbegriff ist hier strukturell unzulaessig.
    """

    AUSSEN_OBEN = "AUSSEN_OBEN"
    INNEN_OBEN_1 = "INNEN_OBEN_1"
    AUSSEN_UNTEN = "AUSSEN_UNTEN"
    INNEN_UNTEN_1 = "INNEN_UNTEN_1"
    RECLAIM_AT_OPENING = "RECLAIM_AT_OPENING"

    @property
    def ist_rang(self) -> bool:
        """True gdw. die Rolle ueber einen Bar-Rang aufloesbar ist."""
        return self is not KantenRolle.RECLAIM_AT_OPENING

    @property
    def seite(self) -> str:
        """Engine-Seite der Rolle (``"OBEN"`` / ``"UNTEN"``).

        Raises:
            ValueError: Fuer ``RECLAIM_AT_OPENING`` ist die Seite nicht
                statisch festgelegt (der Reclaim kann beidseitig sein).
        """
        if not self.ist_rang:
            raise ValueError(
                "RECLAIM_AT_OPENING hat keine statische Seite -- "
                "seitengebunden ueber hook_4 aufloesen.")
        return ("OBEN" if self in (KantenRolle.AUSSEN_OBEN,
                                   KantenRolle.INNEN_OBEN_1) else "UNTEN")

    @property
    def rang(self) -> Optional[int]:
        """Position in der aussen-nach-innen-Sortierung (0 = aussen).

        Returns:
            Rang 0/1 fuer die Rangfamilie, ``None`` fuer die Ereignisfamilie.
        """
        if not self.ist_rang:
            return None
        return 0 if self in (KantenRolle.AUSSEN_OBEN,
                             KantenRolle.AUSSEN_UNTEN) else 1


class NiveauModus(Enum):
    """Herkunft der Phasen-Niveaus (TP2-Basis).

    * ``PROVENIENZ_ABSOLUT``  Ebene 1 (AUG, arretiert): Literal aus v0.4
      (z. B. 67.6355). NICHT fensteruebertragbar -- in S2 mathematisch leer
      (S2-Spanne 28.29..56.53 liegt vollstaendig darunter).
    * ``GEGENKANTE_RELATIV``  Ebene 2 (S1/S2): Niveau = kausale Gegenkante
      ``basis_bei(k)`` zum Signal-Bar.

    VERWORFEN (2026-09-11, Phase 2.1): ``PROVENIENZ_SKALIERT``. Zwei harte
    Gruende -- (a) LOOKAHEAD: der vorgeschlagene Nenner (70.0000 / 62.5480)
    stammt aus H2 (Bars 881 / 673 > box_end 644); (b) DIMENSION: ein
    Range-VERHAELTNIS (1.9564) auf ein absolutes Niveau multipliziert
    ergibt 132.32 -- strukturell sinnlos. Skalierbar waere nur eine
    DISTANZ (``Level = Referenz + Distanz * Faktor``), nicht ein Level.
    Ausserdem vergleicht ein Verhaeltnis 644-Bar-Box gegen ~19.000-Bar-Box
    Dauer gegen Volatilitaet.

    RATIFIZIERT (2026-09-11, Frage 1): ``GEGENKANTE_RELATIV`` ist der
    Ebene-2-Default -- **aber** der Phasen-Override wirkt nur, wenn die
    Gegenkante die **phaseneigene** Wand ist (``GegenkantenWahl.PHASE_EIGEN``).
    Die Engine-``_gegenkante`` (Q5/Q14) waehlt dagegen die aeusserste
    MAKROWAND (``GegenkantenWahl.MAKRO_ENGINE``) -- gemessen: **-14.579896 R**
    (18 Trades / +51.255680). Die phaseneigene Gegenkante ueber kausales
    ``basis_bei(k)`` liefert **+65.504879 R** (17 Trades, 99.50 % der
    Baseline) ohne jedes Preis-Literal.
    """

    PROVENIENZ_ABSOLUT = "PROVENIENZ_ABSOLUT"
    GEGENKANTE_RELATIV = "GEGENKANTE_RELATIV"


class GegenkantenWahl(Enum):
    """Auswahl der Gegenkante (TP2-Anker) -- Phase 1.1, ratifiziert 2026-09-11.

    Der Begriff ``GEGENKANTE_RELATIV`` allein war unterbestimmt: die Engine
    loest ihn ueber ``_gegenkante`` (Q5/Q14) als **aeusserste Gegenwand** auf.
    Genau das ist der von der Mentor-Kritik adressierte Fehler -- nicht das
    Prinzip "relativ", sondern die *Wahl*.

    * ``PHASE_EIGEN`` (**RATIFIZIERT**, Ebene-2-Default): TP2-Anker ist die
      deklarierte Gegenwand der AKTIVEN Konsolidierung -- fuer SHORT
      ``SegmentVD.boden``, fuer LONG ``SegmentVD.decke``, kausal aufgeloest
      ueber ``basis_bei(k)``. Fuer P9 gemessen: ``boden.kid = K77``,
      ``basis_bei = 68.3920``; das ist zugleich exakt die Provenienz der
      arretierten Phase (``ziel_preis_short = 68.3700``) -- die Phase zielte
      die ganze Zeit auf ihre EIGENE Gegenkante, nicht auf die Makrowand.
    * ``MAKRO_ENGINE`` (VERWORFEN, nur Diagnose): repliziert
      ``_se_trades::_gegenkante`` (aeusserste ``>= 2``-Touch-Linie der
      Gegenseite, SCHLAFEND zulaessig). Messlage AUG: ``K48 62.5770``,
      **-14.579896 R** gegen Baseline. Fuer Ebene-2-Segmente
      (``erwarteter_start_bar is None``) wird diese Wahl von
      :meth:`VDAdapterEntwurf.verifiziere` **hart abgelehnt** (fail-loud).
    """

    PHASE_EIGEN = "PHASE_EIGEN"
    MAKRO_ENGINE = "MAKRO_ENGINE"


class RangModus(Enum):
    """Sortiersemantik der Rangfamilie -- Phase 1.2, ratifiziert 2026-09-11.

    * ``ABSOLUT``  = ``pool.sort(key=basis_bei(k), reverse=(seite == "OBEN"))``
      -- die Engine-Semantik. Fuer ``AUSSEN_*`` korrekt (Rang 0 = aeusserste
      Wand). Fuer ``INNEN_*`` **semantisch falsch**: der UNTEN-Pool aufsteigend
      sortiert macht Rang 1 zur naechs-tieferen MAKRO-Kante (gemessen:
      K49 62.8590 statt einer Innenwand der Handelszone).
    * ``NAEHE`` (**RATIFIZIERT**, Ebene-2-Default) = Rang nach
      ``|basis - referenz_preis|`` mit ``referenz_preis = sweep_px``. Eine
      Innenlinie ist durch ihre **relative Naehe zur Handelszone** definiert,
      nicht durch ihre absolute Hoehe im Chart. Tie-Break: kleinerer Preis.
    """

    ABSOLUT = "ABSOLUT"
    NAEHE = "NAEHE"


@dataclass(frozen=True, slots=True)
class KantenReferenz:
    """Verweis auf eine Phasengrenzkante -- Kid (E1) ODER Rolle (E2).

    Args:
        kind: ``"kid"`` (arretierte August-Referenz) oder ``"rolle"``
            (fensteruebertragbar). Genau eines der beiden Felder ist gesetzt.
        kid: Kanten-ID aus dem arretierten AUG-Scan.
        rolle: Semantische Rolle, je Bar kausal neu aufgeloest.
        provenienz_basis: v0.4-Niveau -- NUR fuer ``PROVENIENZ_ABSOLUT``.
            Bei ``"rolle"`` bewusst ``None`` (es gibt keine Provenienz).
    """

    kind: str = "kid"
    kid: Optional[int] = None
    rolle: Optional[KantenRolle] = None
    provenienz_basis: Optional[float] = None

    def ist_rolle(self) -> bool:
        """True gdw. die Referenz fensteruebertragbar (Ebene 2) ist."""
        return self.kind == "rolle"


# =============================================================================
# 2  SCHLIESS- UND OEFFNUNGSKRITERIUM
# =============================================================================


class SchliessModus(Enum):
    """Schliess-Kriterium der Phase (Hybrid = Option C)."""

    STRUKTUR_BRUCH = "STRUKTUR_BRUCH"
    INAKTIVITAETS_TIMEOUT = "INAKTIVITAETS_TIMEOUT"
    HYBRID = "HYBRID"


@dataclass(frozen=True, slots=True)
class SchliessKriterium:
    """Deterministisches Ende eines endogenen Phasenfensters.

    Uebernimmt die ENGINE-EIGENE Struktur-Semantik (Z. 2284-2292:
    ``min(op[k-1], cl[k-1]) > basis and min(op[k], cl[k]) > basis``) und
    ergaenzt sie um einen expliziten Puffer sowie einen Inaktivitaets-Timeout.
    Kein neuer Mechanismus -- die Uebertragung einer arretierten Q-Semantik.

    Definition (erstes Ereignis gewinnt, halboffenes Fenster
    ``[oeffnung, schliessung)``, kausal je Signal-Bar, niemals rueckwirkend):

    * STRUKTUR_BRUCH: ``bruch_bars`` konsekutive Voll-Bars ausserhalb der
      Phasenrange. OBEN: ``min(op, cl) > decke_basis * (1 + puffer)``;
      UNTEN: ``max(op, cl) < boden_basis * (1 - puffer)``.
    * INAKTIVITAETS_TIMEOUT: ``timeout_bars`` Bars ohne bestaetigten Touch
      auf EINER der beiden deklarierten Grenzkanten (Q25-Schwelle).

    Args:
        modus: Zu pruefender Zweig.
        bruch_bars: Konsekutive Voll-Bars fuer den Struktur-Bruch (>= 2).
        puffer_pct: EIGENER Puffer in Prozent. Bewusst NICHT
            ``tombstone_band_pct`` (0.3) zweckentfremdet.
        timeout_bars: Inaktivitaets-Schwelle; Default = ``wall_live_bars``.
    """

    modus: SchliessModus = SchliessModus.HYBRID
    bruch_bars: int = 2
    puffer_pct: float = 0.0
    timeout_bars: int = 96


class OeffnungsModus(Enum):
    """Endogener Oeffnungs-Trigger (Fenster endogen, Niveaus deklariert)."""

    RECLAIM_GEGEN_GRENZKANTE = "RECLAIM_GEGEN_GRENZKANTE"
    RECLAIM_NACH_RANGE_BRUCH = "RECLAIM_NACH_RANGE_BRUCH"


@dataclass(frozen=True, slots=True)
class OeffnungsTrigger:
    """Kausaler Oeffnungs-Trigger des Phasenfensters.

    Gemessenes AUG-Verhalten (Phase 3 / Schritt 1, Lauf iv-A): erster Bar
    ``k >= vorgaenger_ende + 1`` mit ``_reclaim_stufe(side, k, basis) >= 1``
    gegen die deklarierte Grenzkante, OHNE ``_existiert``-Gate -> Bar 1075
    (K82, ``STUFE_1_IN_BAR``, Monatstief 67.4200).

    Args:
        modus: Trigger-Variante.
        min_reclaim_stufe: Mindeststufe (1 = ``STUFE_1_IN_BAR``).
        braucht_exists_gate: ``True`` macht den Trigger strenger; gemessen
            liefert das fuer K82 ein LEERES Fenster (K82 schlaeft
            1074..1173) -- daher Default ``False``.
        ignoriere_schlafstatus: **Sleep-Bypass (Phase 2.2, ratifiziert
            2026-09-11).** Ein Reclaim am Boden ist per Definition ein
            Ereignis NACH dem Bruch. Das Schlaf-Fenster ist die FOLGE des
            Bruchs (K82: Sweep-Bar 1072 -> Fenster ``(1074, 1174)``); der
            Reclaim faellt genau 1 Bar nach dem Einschlafen (Bar 1075).
            Filtert der Detektor ueber ``ist_aktiv_bei``, sperrt er exakt
            das Fakeout-Muster, das er fangen soll. Deshalb gilt fuer die
            ERFOLGSFAMILIE ``RECLAIM_AT_OPENING``: **Ereignis schlaegt
            Status** -- gefiltert wird nur die KAUSALITAET
            (``KantenSicht.kausal_existent``), nie der Schlafstatus.
            ``False`` stellt das Bestandsverhalten (Engine-``_existiert``)
            wieder her und liefert fuer K82 ein leeres Fenster.
        range_bruch_bestaetigung: Nur fuer ``RECLAIM_NACH_RANGE_BRUCH``:
            konsekutive Voll-Bars ausserhalb der Vorgaenger-Range.
    """

    modus: OeffnungsModus = OeffnungsModus.RECLAIM_GEGEN_GRENZKANTE
    min_reclaim_stufe: int = 1
    braucht_exists_gate: bool = False
    ignoriere_schlafstatus: bool = True
    range_bruch_bestaetigung: int = 2


# =============================================================================
# 3  SEGMENT UND ERGEBNIS
# =============================================================================


@dataclass(frozen=True, slots=True)
class SegmentVD:
    """Endogenes Phasensegment (Ebene 2) -- additiv zur arretierten Ebene 1.

    Args:
        phasen_id: Bezeichner, z. B. ``"P10_DYN"``.
        decke: Obere Grenzkante (Referenz oder Rolle).
        boden: Untere Grenzkante (Referenz oder Rolle). Fuer P10 gemessen:
            die Decke ist ``AUSSEN_OBEN`` (K67, Rang 0 auf allen 267
            H2-Bars -- replikationsfaehig); der Boden ist
            ``RECLAIM_AT_OPENING`` (K82, Rang 10/11 -- NICHT
            rangadressierbar).
        niveau_modus: Herkunft der TP2-Niveaus. Default Ebene 2 =
            ``GEGENKANTE_RELATIV``.
        gegenkante_wahl: WELCHE Gegenkante den TP2-Anker bildet (Phase 1.1).
            Default ``PHASE_EIGEN`` = die eigene Gegenwand der aktiven
            Konsolidierung (SHORT -> ``boden``, LONG -> ``decke``), kausal
            ueber ``basis_bei(k)``. ``MAKRO_ENGINE`` ist die verworfene
            Engine-Semantik (aeusserste Wand) und fuer endogene Segmente
            verboten (fail-loud in ``verifiziere``).
        ziel_anteil: Anteil bis zur kausalen Gegenkante (1.0 = volle
            Distanz). Das Ziel wird IMMER gegen die Gegenkante geklemmt:
            SHORT ``max(ziel, gegenkante)``, LONG ``min(ziel, gegenkante)``.
        rang_modus: Sortiersemantik der Rangfamilie (Phase 1.2). Default
            ``NAEHE`` (Abstand zum Signalpreis); ``ABSOLUT`` ist die
            Engine-Semantik und nur fuer ``AUSSEN_*`` korrekt.
        schliess: Schliess-Kriterium (Hybrid).
        oeffnung: Oeffnungs-Trigger.
        erwarteter_start_bar: ``None`` = vollstaendig endogen (Ebene 2).
            Ein gesetzter Wert ist AUG-Provenienz und darf fuer S1/S2 NICHT
            verwendet werden (B4).
        seite_kid_band_pct: Freigabeband fuer ``hook_1_freigabe_kid``.
            ``None`` = Bestandsverhalten (``touch_band_pct``). Loest den
            gemessenen M6/Hook-1-Konflikt (0.12 % vs. 0.75 %).
    """

    phasen_id: str
    decke: KantenReferenz
    boden: KantenReferenz
    niveau_modus: NiveauModus = NiveauModus.GEGENKANTE_RELATIV
    gegenkante_wahl: GegenkantenWahl = GegenkantenWahl.PHASE_EIGEN
    rang_modus: RangModus = RangModus.NAEHE
    ziel_anteil: float = 1.0
    schliess: SchliessKriterium = SchliessKriterium()
    oeffnung: OeffnungsTrigger = OeffnungsTrigger()
    erwarteter_start_bar: Optional[int] = None
    seite_kid_band_pct: Optional[float] = None


class PhasenDynamikModus(Enum):
    """Zustand des endogenen Phasenfensters am Bar k."""

    GESCHLOSSEN = "GESCHLOSSEN"
    OFFEN = "OFFEN"


@dataclass(frozen=True, slots=True)
class PhasenDynamikErgebnis:
    """Rueckgabe von ``hook_4_phasen_dynamik``.

    Args:
        modus: Fensterzustand am Bar k.
        phasen_id: Gesetzt gdw. ``modus is OFFEN``.
        oeffnung_bar: Kausal ermittelter Oeffnungs-Bar.
        schliessung_bar: Kausal ermittelter Schliess-Bar (None = offen).
        decke_kid: Am Bar k aufgeloeste Decken-Kante.
        boden_kid: Am Bar k aufgeloeste Boden-Kante.
        ziel_preis: TP2-Niveau (None unter ``GEGENKANTE_RELATIV``).
    """

    modus: PhasenDynamikModus
    phasen_id: Optional[str] = None
    oeffnung_bar: Optional[int] = None
    schliessung_bar: Optional[int] = None
    decke_kid: Optional[int] = None
    boden_kid: Optional[int] = None
    ziel_preis: Optional[float] = None


# =============================================================================
# 4  ADAPTER-ENTWURF (reine Wertedomaene)
# =============================================================================


@dataclass(frozen=True, slots=True)
class VDAdapterEntwurf:
    """Duck-typisierter Adapter fuer V-D (Ebene 2). NICHT arretiert.

    Konsumiert vom bestehenden Engine-Patch ueber die bereits vorhandenen
    Rueckgrat-Namen (``aktive_phase_bei``, ``hook_1_freigabe_kid``,
    ``hook_2_ziel``, ``angewandte_basis``) plus den neuen
    ``hook_4_phasen_dynamik``. Die Engine bleibt bei SHA 4a576a76...

    Args:
        start_scope_bar: Erstes Bar, ab dem Regime-Logik greift.
        segmente: Endogene Segmente (Ebene 2).
        seiten_aktiv: Optionales Seitenfilter je Segment (Default: beide).
    """

    start_scope_bar: int
    segmente: Tuple[SegmentVD, ...] = ()
    seiten_aktiv: Dict[str, Tuple[str, ...]] = field(default_factory=dict)

    # ------------------------------------------------------- Source of Truth
    @staticmethod
    def sortiere_seite_kanten(kanten: KantenKat,
                              seite: str) -> Sequence[Tuple[int, float]]:
        """Sortiert existierende Seitenkanten exakt wie der Engine-Pool.

        Single Source of Truth: ``reverse=(seite == "OBEN")`` -- identisch zu
        ``_se_trades::_kandidat``. Jede Abweichung reproduziert den
        Bandkonflikt zwischen M6 (0.75 %) und Hook 1 (0.12 %).

        Args:
            kanten: ``(kid, seite, basis)``-Tupel der EXISTIERENDEN Kanten.
            seite: ``"OBEN"`` oder ``"UNTEN"``.

        Returns:
            ``(kid, basis)`` absteigend (OBEN) bzw. aufsteigend (UNTEN).
        """
        gef = [(int(kid), float(basis)) for (kid, s, basis) in kanten
               if s == seite]
        gef.sort(key=lambda t: t[1], reverse=(seite == "OBEN"))
        return gef

    @classmethod
    def aufloese_rolle(cls, rolle: KantenRolle,
                       kanten: KantenKat) -> Optional[Tuple[int, float]]:
        """Loest eine RANGROLLE kausal in ``(kid, basis)`` auf.

        Args:
            rolle: Zielrolle (muss zur Rangfamilie gehoeren).
            kanten: ``(kid, seite, basis)`` der existierenden Kanten am Bar k.

        Returns:
            ``(kid, basis)`` oder None, wenn die Rolle unbesetzt ist.

        Raises:
            ValueError: ``RECLAIM_AT_OPENING`` -- die Ereignisfamilie ist
                rangfrei und wird ueber ``hook_4_phasen_dynamik`` mit
                Marktdaten aufgeloest, nicht hier.
        """
        if not rolle.ist_rang:
            raise ValueError(
                f"{rolle.value} ist keine Rangrolle -- Aufloesung erfordert "
                f"Marktdaten und gehoert in hook_4_phasen_dynamik.")
        rang = rolle.rang
        assert rang is not None
        gef = cls.sortiere_seite_kanten(kanten, rolle.seite)
        return gef[rang] if len(gef) > rang else None

    @classmethod
    def aufloese_referenz(cls, ref: KantenReferenz,
                          kanten: KantenKat) -> Optional[Tuple[int, float]]:
        """Loest Kid- ODER Rollenreferenz einheitlich auf.

        Args:
            ref: Kantenreferenz (Ebene 1 oder Ebene 2).
            kanten: Kantenkatalog am Bar k.

        Returns:
            ``(kid, basis)`` oder None.

        Raises:
            ValueError: Referenz ist weder Kid noch Rolle.
        """
        if ref.ist_rolle():
            assert ref.rolle is not None
            return cls.aufloese_rolle(ref.rolle, kanten)
        if ref.kid is not None:
            for (kid, _s, basis) in kanten:
                if int(kid) == int(ref.kid):
                    return (int(kid), float(basis))
            return None
        raise ValueError("KantenReferenz ohne kid und ohne rolle.")

    # ===================================================== KAUSAL-GEHAERTET
    # Die folgenden Aufloeser sind die Ebene-2-Pfade (S1/S2). Sie sind
    # ADDITIV zu den Engine-identischen Methoden oben und unterscheiden sich
    # in genau zwei Punkten:
    #   (2.1) Existenz-Vorbedingung -- kein Pre-Birth-Lookahead.
    #   (1.2) Sortiersemantik -- NAEHE statt ABSOLUT fuer die Innenraenge.

    @staticmethod
    def filtere_kausal(sichten: KantenSichtKat, k: int
                       ) -> Sequence[KantenSicht]:
        """Entfernt Kanten, deren Pivot am Bar k nicht bestaetigt ist (2.1).

        Untergrenze ist exakt ``_se_trades::_existiert``
        (``erster_pivot_bar + 2 <= k + 1``). Damit ist der Pre-Birth-
        Lookahead des Engine-Rueckfalls (``wicks[0][1]``) strukturell
        ausgeschlossen: der Adapter kennt den Zukunfts-Docht nicht.

        Args:
            sichten: Kantenkatalog (``KantenSicht``) am Bar k.
            k: Signal-Bar.

        Returns:
            Nur die kausal bestaetigten Kanten (Reihenfolge erhalten).
        """
        return [e for e in sichten if e.kausal_existent(k)]

    @staticmethod
    def sortiere_nach_naehe(sichten: KantenSichtKat, seite: str,
                            referenz_preis: float
                            ) -> Sequence[Tuple[int, float]]:
        """Rangfolge nach Abstand zum Signalpreis (Phase 1.2, NAEHE).

        Eine Innenlinie ist durch ihre **relative Naehe zur Handelszone**
        definiert, nicht durch ihre absolute Hoehe im Chart. Genau daran
        scheiterte ``INNEN_UNTEN_1`` unter ``RangModus.ABSOLUT``: der Rang 1
        landete auf der Makro-Kante K49 (62.8590) statt auf einer Innenwand.

        Args:
            sichten: Kantenkatalog am Bar k.
            seite: ``"OBEN"`` oder ``"UNTEN"``.
            referenz_preis: ``sweep_px`` des Signal-Bars.

        Returns:
            ``(kid, basis)`` aufsteigend nach ``|basis - referenz|``;
            Tie-Break deterministisch: kleinerer Preis zuerst.
        """
        gef = [(int(e.kid), float(e.basis)) for e in sichten
               if e.seite == seite]
        gef.sort(key=lambda t: (abs(t[1] - float(referenz_preis)), t[1]))
        return gef

    @classmethod
    def aufloese_rolle_kausal(cls, rolle: KantenRolle,
                              sichten: KantenSichtKat, k: int,
                              referenz_preis: Optional[float] = None,
                              rang_modus: RangModus = RangModus.NAEHE,
                              ) -> Optional[Tuple[int, float]]:
        """Loest eine RANGROLLE kausal-gehaertet auf (Phase 1.2 + 2.1).

        Args:
            rolle: Zielrolle (muss zur Rangfamilie gehoeren).
            sichten: Kantenkatalog am Bar k.
            k: Signal-Bar.
            referenz_preis: ``sweep_px`` -- Pflicht bei ``NAEHE``.
            rang_modus: ``NAEHE`` (Default, Ebene 2) oder ``ABSOLUT``
                (Engine-Ordnung, nur fuer ``AUSSEN_*`` korrekt).

        Returns:
            ``(kid, basis)`` oder None, wenn die Rolle unbesetzt ist.

        Raises:
            ValueError: Ereignisfamilie oder ``NAEHE`` ohne ``referenz_preis``.
        """
        if not rolle.ist_rang:
            raise ValueError(
                f"{rolle.value} ist keine Rangrolle -- siehe "
                f"aufloese_reclaim_at_opening.")
        if rang_modus is RangModus.NAEHE and referenz_preis is None:
            raise ValueError("RangModus.NAEHE verlangt referenz_preis.")
        kausal = cls.filtere_kausal(sichten, k)
        if rang_modus is RangModus.NAEHE:
            gef = cls.sortiere_nach_naehe(kausal, rolle.seite,
                                          float(referenz_preis))
        else:
            gef = cls.sortiere_seite_kanten(
                [(e.kid, e.seite, e.basis) for e in kausal], rolle.seite)
        rang = rolle.rang
        assert rang is not None
        return gef[rang] if len(gef) > rang else None

    @classmethod
    def aufloese_referenz_kausal(cls, ref: KantenReferenz,
                                 sichten: KantenSichtKat, k: int,
                                 referenz_preis: Optional[float] = None,
                                 rang_modus: RangModus = RangModus.NAEHE,
                                 ) -> Optional[Tuple[int, float]]:
        """Kid-/Rollenreferenz kausal-gehaertet (Phase 2.1 + 1.2).

        Kid-Referenzen werden ebenfalls gegen ``kausal_existent(k)`` geprueft
        -- eine Kante, die es am Bar k noch nicht gibt, ist keine gueltige
        Referenz (auch nicht als Literal-Quelle).

        Args:
            ref: Kantenreferenz (Ebene 1 oder Ebene 2).
            sichten: Kantenkatalog am Bar k.
            k: Signal-Bar.
            referenz_preis: ``sweep_px`` (nur fuer Rollenpfad relevant).
            rang_modus: Sortiersemantik des Rollenpfads.

        Returns:
            ``(kid, basis)`` oder None.

        Raises:
            ValueError: Referenz ist weder Kid noch Rolle.
        """
        if ref.ist_rolle():
            assert ref.rolle is not None
            return cls.aufloese_rolle_kausal(ref.rolle, sichten, k,
                                             referenz_preis, rang_modus)
        if ref.kid is not None:
            for e in cls.filtere_kausal(sichten, k):
                if int(e.kid) == int(ref.kid):
                    return (int(e.kid), float(e.basis))
            return None
        raise ValueError("KantenReferenz ohne kid und ohne rolle.")

    def gegenkante_basis(self, seg: SegmentVD, richtung: str,
                         sichten: KantenSichtKat, k: int,
                         referenz_preis: Optional[float] = None
                         ) -> Optional[float]:
        """Kausale Gegenkante des Segments (Phase 1.1, ratifiziert).

        ``PHASE_EIGEN``: fuer SHORT ist die Gegenkante der **Boden** des
        Segments, fuer LONG die **Decke** -- die eigene Wand der aktiven
        Konsolidierung, kausal via ``basis_bei(k)``. Genau das tat P9 bereits
        (``boden.kid = K77`` == ``ziel_preis_short`` Provenienz 68.3700).

        ``MAKRO_ENGINE``: repliziert ``_se_trades::_gegenkante`` (aeusserste
        Touch-Linie der Gegenseite) -- nur fuer die Diagnose, -14.579896 R.

        Args:
            seg: Segment (liefert ``gegenkante_wahl``/``rang_modus``).
            richtung: ``"SHORT"`` oder ``"LONG"``.
            sichten: Kantenkatalog am Bar k.
            k: Signal-Bar.
            referenz_preis: ``sweep_px`` (nur fuer ``NAEHE``-Rollen).

        Returns:
            Kausale Gegenkanten-Basis oder None.

        Raises:
            ValueError: Unbekannte Richtung.
        """
        if richtung not in ("SHORT", "LONG"):
            raise ValueError(f"Unbekannte Richtung: {richtung!r}")
        kausal = self.filtere_kausal(sichten, k)
        if seg.gegenkante_wahl is GegenkantenWahl.MAKRO_ENGINE:
            seite = "OBEN" if richtung == "LONG" else "UNTEN"
            preise = [float(e.basis) for e in kausal if e.seite == seite]
            if not preise:
                return None
            return max(preise) if seite == "OBEN" else min(preise)
        ref = seg.boden if richtung == "SHORT" else seg.decke
        aufg = self.aufloese_referenz_kausal(ref, kausal, k,
                                             referenz_preis, seg.rang_modus)
        return None if aufg is None else float(aufg[1])

    def ziel_preis_kausal(self, seg: SegmentVD, richtung: str,
                          sichten: KantenSichtKat, k: int,
                          referenz_preis: Optional[float] = None
                          ) -> Optional[float]:
        """TP2-Niveau endogen + kausal (Phase 1.1 + 2.1).

        Reihenfolge: beide Grenzen kausal aufloesen (None -> None), dann die
        phaseneigene Gegenkante bilden, dann :meth:`ziel_preis` (mit Clamping
        gegen die Gegenkante) anwenden. Kein Preis-Literal, kein
        Engine-Rueckfall.

        Args:
            seg: Segment.
            richtung: ``"SHORT"`` oder ``"LONG"``.
            sichten: Kantenkatalog am Bar k.
            k: Signal-Bar.
            referenz_preis: ``sweep_px``.

        Returns:
            Geklemmtes TP2-Niveau oder None, wenn eine Grenze fehlt.
        """
        kausal = self.filtere_kausal(sichten, k)
        decke = self.aufloese_referenz_kausal(seg.decke, kausal, k,
                                              referenz_preis, seg.rang_modus)
        boden = self.aufloese_referenz_kausal(seg.boden, kausal, k,
                                              referenz_preis, seg.rang_modus)
        if decke is None or boden is None:
            return None
        gegen = self.gegenkante_basis(seg, richtung, kausal, k,
                                      referenz_preis)
        return self.ziel_preis(seg, richtung, decke[1], boden[1], gegen)

    @staticmethod
    def aufloese_reclaim_at_opening(
        k: int,
        marktdaten: Mapping[str, object],
        sichten: KantenSichtKat,
        parameter: Optional[Mapping[str, float]] = None,
    ) -> Optional[Tuple[int, float, str, str]]:
        """Loest die EREIGNISROLLE ``RECLAIM_AT_OPENING`` auf (Phase 2.2).

        Semantik = Stufe 1 der Engine-Hierarchie ``_reclaim_stufe``
        (``STUFE_1_IN_BAR``), aber mit **Sleep-Bypass**:

        * Gefiltert wird NUR ``KantenSicht.kausal_existent(k)`` (Kausalitaet),
          **nie** ``ist_aktiv_bei``/Schlafstatus. Ein Reclaim am Boden ist
          ein Ereignis NACH dem Bruch; das Schlaf-Fenster ist dessen Folge
          (K82: Sweep 1072 -> Fenster (1074, 1174); Reclaim genau Bar 1075).
          Der Detektor darf nicht genau das Fakeout-Muster aussperren, das er
          fangen soll.
        * UNTEN: ``lo[k] < basis`` und ``cl[k] >= basis``.
        * OBEN : ``hi[k] > basis`` und ``cl[k] <= basis``.
        * Durchstich-Fenster ``min_durch < dist <= max_ueber`` in Prozent.
        * Tie-Break: **tiefster Durchstich** (entschiedenster Reclaim) zuerst.

        Args:
            k: Signal-Bar.
            marktdaten: Mapping mit ``"high"``/``"low"``/``"close"``
                (indexierbar per ``k``). Engine liefert nur Kontext, der
                Adapter bleibt in der reinen Wertedomaene.
            sichten: Kantenkatalog (``KantenSicht``) am Bar k.
            parameter: ``sweep_mindestdurchstich_pct`` (Default 0.0),
                ``max_sweep_ueberdehnung_pct`` (Default 0.6) -- identisch zu
                ``StraightEdgeHarnessKonfiguration``.

        Returns:
            ``(kid, basis, seite, stufe_name)`` oder None (kein Reclaim).
        """
        hi = marktdaten["high"]
        lo = marktdaten["low"]
        cl = marktdaten["close"]        # type: ignore[index]
        p = parameter or {}
        min_durch = float(p.get("sweep_mindestdurchstich_pct", 0.0))
        max_ueber = float(p.get("max_sweep_ueberdehnung_pct", 0.6))

        treffer: list[Tuple[float, int, float, str]] = []
        for e in sichten:
            if not e.kausal_existent(k):
                continue
            basis = float(e.basis)
            if basis <= 0.0:
                continue
            if e.seite == "UNTEN":
                if not (lo[k] < basis and cl[k] >= basis):   # type: ignore
                    continue
                dist = (basis - float(lo[k])) / basis * 100.0
            elif e.seite == "OBEN":
                if not (hi[k] > basis and cl[k] <= basis):   # type: ignore
                    continue
                dist = (float(hi[k]) - basis) / basis * 100.0
            else:
                continue
            if min_durch < dist <= max_ueber:
                treffer.append((dist, int(e.kid), basis, e.seite))
        if not treffer:
            return None
        treffer.sort(key=lambda t: -t[0])       # tiefster Durchstich zuerst
        dist, kid, basis, seite = treffer[0]
        return (kid, basis, seite, "STUFE_1_IN_BAR")

    # ------------------------------------------------------------- Validierung
    def verifiziere(self, kanten: KantenKat) -> None:
        """Fail-Loud-Pruefung des gesamten Vertrags.

        Erzwingt: Fenster nicht leer, Puffer nicht negativ, Bruch >= 2 Bars,
        Timeout > 0, Zielanteil in (0, 1], Band > 0 wenn gesetzt, und -- im
        Rollenmodus -- dass jede deklarierte Rolle am Start-Bar aufloesbar ist.

        Args:
            kanten: Kantenkatalog am erwarteten Start-Bar.

        Raises:
            ValueError: Verletzte Invariante.
        """
        for seg in self.segmente:
            if seg.schliess.bruch_bars < 2:
                raise ValueError(
                    f"{seg.phasen_id}: bruch_bars < 2 "
                    f"({seg.schliess.bruch_bars}).")
            if seg.schliess.puffer_pct < 0.0:
                raise ValueError(
                    f"{seg.phasen_id}: puffer_pct < 0 "
                    f"({seg.schliess.puffer_pct}).")
            if seg.schliess.timeout_bars <= 0:
                raise ValueError(
                    f"{seg.phasen_id}: timeout_bars <= 0 "
                    f"({seg.schliess.timeout_bars}).")
            if not (0.0 < seg.ziel_anteil <= 1.0):
                raise ValueError(
                    f"{seg.phasen_id}: ziel_anteil ausserhalb (0, 1] "
                    f"({seg.ziel_anteil}).")
            # Phase 1.1 (Ratifiziert 2026-09-11): Ebene-2-Segmente
            # (endogen, erwarteter_start_bar is None) duerfen NICHT die
            # verworfene MAKRO-Engine-Gegenkante verwenden.
            if (seg.niveau_modus is NiveauModus.GEGENKANTE_RELATIV
                    and seg.gegenkante_wahl is GegenkantenWahl.MAKRO_ENGINE
                    and seg.erwarteter_start_bar is None):
                raise ValueError(
                    f"{seg.phasen_id}: endogenes Ebene-2-Segment darf NICHT "
                    f"GegenkantenWahl.MAKRO_ENGINE nutzen -- gemessen "
                    f"-14.579896 R (K48 62.5770 gegen Baseline). "
                    f"Ratifiziert ist GegenkantenWahl.PHASE_EIGEN.")
            # Phase 2.2 (Ratifiziert): Die Erfolgsfamilie RECLAIM_AT_OPENING
            # lebt von der Durchlaessigkeit des Schlafstatus.
            if not seg.oeffnung.ignoriere_schlafstatus \
                    and not seg.oeffnung.braucht_exists_gate:
                raise ValueError(
                    f"{seg.phasen_id}: oeffnung ignoriert den Schlafstatus "
                    f"nicht UND verlangt kein exists-Gate -- das ist "
                    f"inkonsistent (weder Ereignis- noch Statuspfad).")
            if seg.seite_kid_band_pct is not None \
                    and seg.seite_kid_band_pct <= 0.0:
                raise ValueError(
                    f"{seg.phasen_id}: seite_kid_band_pct <= 0 "
                    f"({seg.seite_kid_band_pct}).")
            if seg.oeffnung.min_reclaim_stufe < 1:
                raise ValueError(
                    f"{seg.phasen_id}: min_reclaim_stufe < 1 "
                    f"({seg.oeffnung.min_reclaim_stufe}).")
            # Provenienz-Gebot: E1 verlangt Literal, E2 verlangt Rollen.
            for name, ref in (("decke", seg.decke), ("boden", seg.boden)):
                if ref.ist_rolle():
                    if ref.rolle is None:
                        raise ValueError(
                            f"{seg.phasen_id}.{name}: kind='rolle' ohne rolle.")
                    if ref.provenienz_basis is not None:
                        raise ValueError(
                            f"{seg.phasen_id}.{name}: Rollenreferenz darf "
                            f"KEINE provenienz_basis tragen.")
                else:
                    if ref.kid is None:
                        raise ValueError(
                            f"{seg.phasen_id}.{name}: kind='kid' ohne kid.")
                    if seg.erwarteter_start_bar is not None \
                            and ref.provenienz_basis is None \
                            and seg.niveau_modus is \
                            NiveauModus.PROVENIENZ_ABSOLUT:
                        raise ValueError(
                            f"{seg.phasen_id}.{name}: "
                            f"PROVENIENZ_ABSOLUT verlangt provenienz_basis.")

    def verifiziere_rollen_gegen_scan(self, kanten_pro_bar: KantenKat,
                                      bar: int) -> None:
        """Prueft, dass jede Rollenreferenz am Bar ``bar`` aufloesbar ist.

        Args:
            kanten_pro_bar: Kantenkatalog am Bar ``bar``.
            bar: Pruef-Bar (i. d. R. der endogene Oeffnungs-Bar).

        Raises:
            ValueError: Rolle unbesetzt oder Kid fehlt im Katalog.
        """
        for seg in self.segmente:
            for name, ref in (("decke", seg.decke), ("boden", seg.boden)):
                if self.aufloese_referenz(ref, kanten_pro_bar) is None:
                    raise ValueError(
                        f"{seg.phasen_id}.{name} bei Bar {bar} nicht "
                        f"aufloesbar (kind={ref.kind}, kid={ref.kid}, "
                        f"rolle={ref.rolle}).")

    # -------------------------------------------------------------- Ziele
    def ziel_preis(self, seg: SegmentVD, richtung: str,
                   decke_basis: float, boden_basis: float,
                   gegenkante_basis: Optional[float]) -> Optional[float]:
        """Berechnet das TP2-Niveau nach ``SegmentVD.niveau_modus``.

        Das Ergebnis wird IMMER gegen die kausale Gegenkante geklemmt --
        das Ziel darf niemals jenseits der Liquiditaetsgrenze der
        Gegenwand liegen (Anwender-Freigabe 2026-09-11):

        * SHORT: ``tp2 = max(ziel, gegenkante)``  (nicht unter der Wand).
        * LONG : ``tp2 = min(ziel, gegenkante)``  (nicht ueber der Wand).

        Args:
            seg: Segment mit dem gewaehlten Niveau-Modus.
            richtung: ``"SHORT"`` oder ``"LONG"``.
            decke_basis: Kausale Decken-Basis am Signal-Bar.
            boden_basis: Kausale Boden-Basis am Signal-Bar.
            gegenkante_basis: Kausale Gegenkante (Pflichanker fuer Ebene 2).

        Returns:
            Geklemmtes TP2-Niveau oder None (keine Bestimmung moeglich).

        Raises:
            ValueError: Unbekannte Richtung oder ``GEGENKANTE_RELATIV``
                ohne ``gegenkante_basis`` (fail-loud statt stiller None).
        """
        if richtung not in ("SHORT", "LONG"):
            raise ValueError(f"Unbekannte Richtung: {richtung!r}")

        if seg.niveau_modus is NiveauModus.PROVENIENZ_ABSOLUT:
            roh = seg.decke.provenienz_basis
            if roh is None:
                raise ValueError(
                    f"{seg.phasen_id}: PROVENIENZ_ABSOLUT ohne "
                    f"provenienz_basis.")
        else:                                    # GEGENKANTE_RELATIV
            if gegenkante_basis is None:
                raise ValueError(
                    f"{seg.phasen_id}: GEGENKANTE_RELATIV ohne "
                    f"gegenkante_basis.")
            breite = abs(decke_basis - boden_basis) * float(seg.ziel_anteil)
            roh = (gegenkante_basis if seg.ziel_anteil >= 1.0
                   else (gegenkante_basis + breite * (1.0 - seg.ziel_anteil)
                         * (1.0 if richtung == "SHORT" else -1.0)))

        if gegenkante_basis is None:
            return float(roh)
        if richtung == "SHORT":
            return float(max(roh, gegenkante_basis))
        return float(min(roh, gegenkante_basis))
