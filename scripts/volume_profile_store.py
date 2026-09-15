"""
VOLUMENPROFIL-SPEICHER (scripts/volume_profile_store.py)
=========================================================
Haltung der gerechneten Volumenprofile ZUR LAUFZEIT. Kein Rechenkern, kein
Plot, keine Datei - dieses Modul haelt und liefert nur.

Es gibt KEINE Datenbankablage der Profile
-----------------------------------------
Profile sind Laufzeitdaten. Ein Profil ist an seinen Parametersatz gebunden
(Symbol, Timeframe, Fensterart, Bins, Glaettung, Anteile, Filter) und wird bei
jeder Parameteraenderung sofort ungueltig - eine Dateiablage waere dann
Altbestand, der stillschweigend weiterverwendet werden koennte. Deshalb:

    ProfilSpeicher          haelt die Zeilen EINES Parametersatzes (RAM)
    ProfilSpeicherHalter    haelt mehrere Speicher, Schluessel = ``run_id``
    HALTER                  prozessweiter Standard-Halter fuer den Live-Einsatz

Eine Ablage der Profile in einer Datei oder Datenbank gibt es NICHT - auch
nicht als Archivvariante. Es gibt nur diese Laufzeit-Haltung.

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Gehalten werden ausschliesslich BKZ-Zeitstempel (``time AT TIME ZONE 'UTC'``,
tz-naiv) - sie werden unveraendert durchgereicht und nie projiziert (K2).
Zusaetzlich ist der Bar-Index der Primaerschluessel jeder Zeile (K5).

Idempotenz
----------
``run_id`` wird deterministisch aus Symbol, Timeframe, Fensterart und den
Volumenparametern gebildet. ``merke`` ERSETZT den Bestand desselben
``run_id`` vollstaendig - es entstehen keine Duplikate und keine sich
stapelnden Altstaende; ein geaenderter Parametersatz trifft einen NEUEN
Speicher und laesst den alten unberuehrt.

Drei Zeilenebenen
-----------------
    ProfilZeile     FENSTER-Ebene (Band des Hauptbandes, Kennzahlen des Fensters)
    NestZeile       SEGMENT-Ebene (ein Berg = ein Volumen-Nest IM Fenster)
    BereichZeile    BEREICH-Ebene (die eigene Value Area EINES Segmentes)
    LueckeZeile     Zwischenraum zweier benachbarter Bereiche (schneller Move)
    TerritoriumZeile  KNOTEN-Ebene (gepaarte Berge ueber Fenstergrenzen)
    NestObjektZeile   NEST-Ebene (ein zusammenhaengender Lauf = ein Nest)

Die Bereichs-/Luecken-Ebene entsteht aus ``zerlege_bereiche`` und ist die
Datengrundlage der Separation-Statistik: sie traegt die Bereiche als
Preisbaender (``val``/``vah``/``poc``/``breite`` - auch in ATR) und die Luecken
dazwischen.

Die Territoriums-/Nest-Ebene entsteht aus ``volume_profile_nests`` und ist die
Datengrundlage der Nest-Statistik: ein NETST ist ein zusammenhaengender Lauf
innerhalb eines Territoriums (Nest-Objekte tragen eigenen POC/VAL/VAH, ATR der
eigenen Lebensdauer, Volumen, Dauer und die POC-Unsicherheit). ``zu_klein``
(Flimmer-Lauf) und ``angeschnitten`` (beruehrt den geladenen Rand) kennzeichnen
Zeilen, die NICHT in die Statistik eingehen.

Alle Ebenen teilen sich ``run_id`` und damit den Parametersatz; ``merke``
ersetzt sie gemeinsam.

Aufruf (aus einem Orchestrator):
    from scripts.volume_profile_store import HALTER
    speicher = HALTER.hole_oder_anlegen(symbol, timeframe, window_kind, params)
    speicher.merke(zeilen, nest_zeilen, bereich_zeilen, luecke_zeilen,
                   territorium_zeilen, nestobjekt_zeilen)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence

# Vertragsversion der Zeilen/``run_id``-Bildung (bei Aenderungen erhoehen)
SCHEMA_VERSION: str = "1"


def _run_id(
    symbol: str, timeframe: str, window_kind: str, params: Dict[str, Any]
) -> str:
    """Bildet eine deterministische Lauf-Kennung.

    Args:
        symbol: Symbol.
        timeframe: Timeframe.
        window_kind: Fensterart.
        params: Volumenparameter (wird kanonisch serialisiert).

    Returns:
        Kurzer Hex-String; identische Parameter ergeben identische Kennung.
    """
    roh = json.dumps(
        {
            "v": SCHEMA_VERSION,
            "symbol": symbol.upper(),
            "timeframe": timeframe.upper(),
            "kind": window_kind,
            "params": params,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class ProfilZeile:
    """Eine Profilzeile (Fenster-Ebene) fuer den Speicher.

    Attributes:
        symbol: Symbol.
        timeframe: Timeframe.
        window_kind: Fensterart (``day``/``week``/``h12``/...).
        label: Fensterlabel.
        bar_start: Erster Bar-Index des Fensters.
        bar_ende: Letzter Bar-Index des Fensters.
        ts_start: Erster BKZ-Zeitstempel (tz-naiv).
        ts_ende: Letzter BKZ-Zeitstempel (tz-naiv).
        n_bars: Anzahl Bars im Fenster.
        n_bars_gefiltert: Anzahl durch den Volumenfilter entfernter Bars.
        vol_summe: Summe des ``tick_volume`` im Fenster (ungefiltert).
        atr: Mittlere Bar-Spanne des Fensters.
        poc: POC der Zonen-Value-Area (globaler POC).
        val: Untere Kante der Zonen-Value-Area (94 %).
        vah: Obere Kante der Zonen-Value-Area (94 %).
        va_zone_pct: Verwendeter Anteil der Zonen-Value-Area.
        va_abdeckung: Tatsaechlich erreichter Anteil.
        val_huelle: Untere Kante der Berg-Huelle (min der Segment-VALs).
        vah_huelle: Obere Kante der Berg-Huelle (max der Segment-VAHs).
        n_segmente: Anzahl erkannter Segmente.
        lobe2: Zweitgipfel/Gipfel (Diagnose).
        poc_streu_atr: POC-Spanne ueber die Konsensparametersaetze (ATR).
        poc_min: Kleinster POC der Konsensmessung.
        poc_max: Groesster POC der Konsensmessung.
        poc_eindeutig: True = POC stabil gegenueber Parameterwechsel.
    """

    symbol: str
    timeframe: str
    window_kind: str
    label: str
    bar_start: int
    bar_ende: int
    ts_start: Any
    ts_ende: Any
    n_bars: int
    n_bars_gefiltert: int = 0
    vol_summe: float = float("nan")
    atr: float = float("nan")
    poc: float = float("nan")
    val: float = float("nan")
    vah: float = float("nan")
    va_zone_pct: float = float("nan")
    va_abdeckung: float = float("nan")
    val_huelle: float = float("nan")
    vah_huelle: float = float("nan")
    n_segmente: int = 0
    lobe2: float = float("nan")
    poc_streu_atr: float = float("nan")
    poc_min: float = float("nan")
    poc_max: float = float("nan")
    poc_eindeutig: bool = False


@dataclass(slots=True)
class NestZeile:
    """Eine Segmentzeile (Nest-Ebene) fuer den Speicher.

    Das Segment traegt seine Fenstergrenzen selbst (``bar_start``/``bar_ende``),
    damit die Zuordnung zum Profil ohne Positionsannahme eindeutig ist. Symbol,
    Timeframe und Fensterart stammen aus dem Speicher-Kontext
    (``ProfilSpeicher``), nicht aus der Zeile.

    Attributes:
        bar_start: Erster Bar-Index des zugehoerigen Fensters.
        bar_ende: Letzter Bar-Index des zugehoerigen Fensters.
        rank: Rang des Segments (0 = groesstes).
        poc: POC des Segments.
        val: Untere Kante der Segment-Value-Area.
        vah: Obere Kante der Segment-Value-Area.
        vol: Volumen des Segmentabschnitts.
        peak_share_pct: Gipfelvolumen relativ zum groessten Segment.
        bin_start: Erster Bin des Segments.
        bin_gipfel: Gipfel-Bin.
        bin_ende: Letzter Bin des Segments.
    """

    bar_start: int
    bar_ende: int
    rank: int
    poc: float
    val: float
    vah: float
    vol: float
    peak_share_pct: float
    bin_start: int = -1
    bin_gipfel: int = -1
    bin_ende: int = -1


@dataclass(slots=True)
class BereichZeile:
    """Eine Bereichszeile (die eigene Value Area EINES Segmentes).

    Der Bereich ist die Value Area seines Segmentes (``zerlege_bereiche``):
    gleicher Rang, gleicher POC, gleiche Kanten wie das Nest - nur als
    handelbares Preisband mit Breite (absolut und in ATR). Damit ist die
    Separation auch programmatisch abfragbar (Luecken, Isolation, Breiten je
    Fenster), ohne den Kern neu zu rechnen. Symbol, Timeframe und Fensterart
    stammen aus dem Speicher-Kontext (``ProfilSpeicher``).

    Attributes:
        bar_start: Erster Bar-Index des zugehoerigen Fensters.
        bar_ende: Letzter Bar-Index des zugehoerigen Fensters.
        rank: Rang des Bereiches (= Rang des Segmentes, 0 = groesstes).
        poc: POC des Bereiches.
        val: Untere Kante (VAL).
        vah: Obere Kante (VAH).
        breite: ``vah - val`` in Preiseinheiten.
        vol: Volumen des Bereiches (= Volumen des Segmentes).
        breite_atr: Breite in ATR (``nan`` ohne ATR).
    """

    bar_start: int
    bar_ende: int
    rank: int
    poc: float
    val: float
    vah: float
    breite: float
    vol: float
    breite_atr: float = float("nan")


@dataclass(slots=True)
class LueckeZeile:
    """Eine Lueckenzeile (Zwischenraum zweier benachbarter Bereiche).

    Die Luecke traegt kein Volumen: hier laufen die schnellen Moves. Sie wird
    nach Preis geordnet gehalten (``rank_unten`` unter der Luecke,
    ``rank_oben`` darueber) und mit ihrer Breite in ATR vermessen.

    Attributes:
        bar_start: Erster Bar-Index des zugehoerigen Fensters.
        bar_ende: Letzter Bar-Index des zugehoerigen Fensters.
        rank_unten: Rang des Bereiches UNTER der Luecke.
        rank_oben: Rang des Bereiches UEBER der Luecke.
        unten: Obere Kante des unteren Bereiches.
        oben: Untere Kante des oberen Bereiches.
        breite: ``oben - unten`` (<= 0 = die Bereiche ueberlappen).
        breite_atr: Breite in ATR (``nan`` ohne ATR).
    """

    bar_start: int
    bar_ende: int
    rank_unten: int
    rank_oben: int
    unten: float
    oben: float
    breite: float
    breite_atr: float = float("nan")

    @property
    def ueberlappung(self) -> bool:
        """True, wenn sich die beiden Bereiche beruehren/ueberlappen.

        Returns:
            True bei ``breite <= 0`` (kein freier Raum zwischen den Bereichen).
        """
        return self.breite <= 0.0


@dataclass(slots=True)
class TerritoriumZeile:
    """Ein Territorium (Kette gepaarter Berge = ein Knoten ueber die Zeit).

    Das Territorium ist die ZONE des Knotens, nicht das Nest selbst: es kann
    mehrere Nester (Instanzen) tragen, wenn der Preis die Zone zwischenzeitlich
    verlassen hat. Symbol, Timeframe und Fensterart stammen aus dem
    Speicher-Kontext (``ProfilSpeicher``).

    Attributes:
        id: Laufende Nummer des Territoriums.
        unten: Untere Kante (min der Zuteilungsbaender).
        oben: Obere Kante (max der Zuteilungsbaender).
        kern_unten: Untere Kante der Kernvereinigung (min der Berg-VALs).
        kern_oben: Obere Kante der Kernvereinigung (max der Berg-VAHs).
        n_berge: Anzahl gepaarter Berge.
        n_fenster: Anzahl beteiligter Fenster.
        labels: Beteiligte Fensterlabels, mit ``+`` verbunden.
        bar_start: Erster Bar-Index des Territoriums.
        bar_ende: Letzter Bar-Index des Territoriums.
        verschmolzen: True = reicht ueber eine Fenstergrenze.
    """

    id: int
    unten: float
    oben: float
    kern_unten: float
    kern_oben: float
    n_berge: int
    n_fenster: int
    labels: str
    bar_start: int
    bar_ende: int
    verschmolzen: bool


@dataclass(slots=True)
class NestObjektZeile:
    """Ein Nest als EIGENES OBJEKT (zusammenhaengender Lauf im Territorium).

    Traegt die eigenen Level (POC/VAL/VAH aus dem Profil der eigenen Bars), den
    ATR der EIGENEN Lebensdauer und die POC-Unsicherheit ueber die
    Rasterschritte. ``zu_klein`` und ``angeschnitten`` kennzeichnen Zeilen, die
    nicht in die Statistik eingehen.

    Attributes:
        id: Laufende Nummer des Nestes.
        territorium_id: Zugehoeriges Territorium.
        rang: Reihenfolge im Territorium (0 = erstes).
        bar_start: Erster Bar-Index des Nestes.
        bar_ende: Letzter Bar-Index des Nestes.
        ts_start: Erster BKZ-Zeitstempel (tz-naiv).
        ts_ende: Letzter BKZ-Zeitstempel.
        n_bars: Anzahl Bars.
        n_fenster: Anzahl beteiligter Fenster (1 = nicht verschmolzen).
        poc: Point of Control des Nestes.
        val: Untere Kante der Nest-Value-Area.
        vah: Obere Kante der Nest-Value-Area.
        breite: ``vah - val`` in Preiseinheiten.
        breite_atr: Breite in ATR der eigenen Lebensdauer.
        vol: Volumen des Nestes.
        atr: ATR der eigenen Lebensdauer.
        raster_bins: Bin-Anzahl des gemeinsamen Rasters.
        raster_schritt: Tatsaechliche Bin-Breite in Preiseinheiten.
        zu_klein: True = Flimmer-Lauf (nicht in der Statistik).
        angeschnitten: True = beruehrt den geladenen Rand (nicht in der Statistik).
        poc_streu_atr: POC-Spanne ueber die Rasterschritte (ATR).
        poc_min: Kleinster POC der Konsensmessung.
        poc_max: Groesster POC der Konsensmessung.
        poc_eindeutig: True = POC stabil gegenueber dem Rasterschritt.
    """

    id: int
    territorium_id: int
    rang: int
    bar_start: int
    bar_ende: int
    ts_start: Any
    ts_ende: Any
    n_bars: int
    n_fenster: int
    poc: float
    val: float
    vah: float
    breite: float
    breite_atr: float
    vol: float
    atr: float
    raster_bins: int
    raster_schritt: float
    zu_klein: bool = False
    angeschnitten: bool = False
    poc_streu_atr: float = float("nan")
    poc_min: float = float("nan")
    poc_max: float = float("nan")
    poc_eindeutig: bool = False

    @property
    def gueltig(self) -> bool:
        """True, wenn das Nest in die Statistik eingeht.

        Returns:
            True, wenn es weder Flimmer-Lauf noch angeschnitten ist.
        """
        return not (self.zu_klein or self.angeschnitten)


# =============================================================================
# LAUFZEIT-SPEICHER (RAM)
# =============================================================================


class ProfilSpeicher:
    """Laufzeit-Speicher fuer Volumenprofile (RAM, ohne Datei).

    Die Profile werden NUR im Arbeitsspeicher gehalten. Das ist der Regelweg:
    ein Profil ist an seinen Parametersatz gebunden und wird bei jeder
    Parameteraenderung sofort ungueltig - eine Ablegung in einer Datei waere
    dann Altbestand, der stillschweigend weiterverwendet werden koennte.

    Der Speicher haelt die Zeilenvertraege ``ProfilZeile``/``NestZeile``,
    ``BereichZeile``/``LueckeZeile`` (Separation) sowie
    ``TerritoriumZeile``/``NestObjektZeile`` (Nester ueber Fenstergrenzen) und
    ist nach ``run_id`` gruppiert - identische Parameter treffen dieselbe
    Gruppe, ein erneutes ``merke`` ERSETZT sie (keine sich stapelnden
    Altstaende).

    Attributes:
        symbol: Symbol des Laufs.
        timeframe: Timeframe des Laufs.
        window_kind: Fensterart des Laufs.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        window_kind: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Legt den Laufzeitspeicher an.

        Args:
            symbol: Symbol des Laufs.
            timeframe: Timeframe des Laufs.
            window_kind: Fensterart des Laufs.
            params: Volumenparameter (gehen in die ``run_id`` ein).
        """
        self.symbol = str(symbol)
        self.timeframe = str(timeframe)
        self.window_kind = str(window_kind)
        self.params: Dict[str, Any] = dict(params or {})
        self.run_id = _run_id(symbol, timeframe, window_kind, self.params)
        self._profile: List[ProfilZeile] = []
        self._nester: List[NestZeile] = []
        self._bereiche: List[BereichZeile] = []
        self._luecken: List[LueckeZeile] = []
        self._territorien: List[TerritoriumZeile] = []
        self._nestobjekte: List[NestObjektZeile] = []

    def __enter__(self) -> "ProfilSpeicher":
        """Kontextmanager-Eintritt.

        Returns:
            Dieser Speicher.
        """
        return self

    def __exit__(self, *exc: object) -> None:
        """Kontextmanager-Austritt (RAM braucht nichts zu schliessen).

        Args:
            *exc: Ausnahmeinformationen (werden nicht unterdrueckt).
        """
        return None

    def merke(
        self,
        profile: Sequence[ProfilZeile],
        nests: Sequence[NestZeile],
        bereiche: Sequence[BereichZeile] = (),
        luecken: Sequence[LueckeZeile] = (),
        territorien: Sequence[TerritoriumZeile] = (),
        nestobjekte: Sequence[NestObjektZeile] = (),
    ) -> int:
        """Uebernimmt die Zeilen des Laufs in den Arbeitsspeicher.

        Ein erneuter Aufruf ersetzt den Bestand dieses ``run_id`` vollstaendig -
        damit kann kein vermischter Stand aus zwei Parameterlaeufen entstehen.
        Das gilt fuer ALLE Ebenen: werden keine Bereiche/Luecken/Territorien/
        Nester uebergeben, sind sie danach leer (kein Altbestand).

        Args:
            profile: Profilzeilen der Fenster.
            nests: Zu den Profilen gehoerende Segmentzeilen.
            bereiche: Bereiche (eigene Value Area je Segment).
            luecken: Zwischenraeume zweier benachbarter Bereiche.
            territorien: Territorien (Knoten ueber Fenstergrenzen).
            nestobjekte: Nester (zusammenhaengende Laeufe je Territorium).

        Returns:
            Anzahl uebernommener Profilzeilen.
        """
        self._profile = list(profile)
        self._nester = list(nests)
        self._bereiche = list(bereiche)
        self._luecken = list(luecken)
        self._territorien = list(territorien)
        self._nestobjekte = list(nestobjekte)
        return len(self._profile)

    def _fenster_mit_kind(self, window_kind: str) -> set:
        """Bar-Grenzen aller gehaltenen Fenster einer Fensterart.

        Segment-, Bereichs- und Lueckenzeilen tragen die Fensterart nicht
        selbst (sie stammt aus dem Speicher-Kontext) - der Filter laeuft
        deshalb ueber die Bar-Grenzen der Profilzeilen dieser Art.

        Args:
            window_kind: Fensterart-Filter.

        Returns:
            Menge von ``(bar_start, bar_ende)``-Tupeln.
        """
        return {(z.bar_start, z.bar_ende) for z in self.hole(window_kind)}

    def hole(self, window_kind: Optional[str] = None) -> List[ProfilZeile]:
        """Liefert die Profilzeilen (optional auf eine Fensterart gefiltert).

        Args:
            window_kind: Fensterart-Filter; None = alle.

        Returns:
            Liste der Profilzeilen in Einfuegereihenfolge.
        """
        if window_kind is None:
            return list(self._profile)
        return [z for z in self._profile if z.window_kind == window_kind]

    def hole_nester(
        self,
        window_kind: Optional[str] = None,
        bar_start: Optional[int] = None,
        bar_ende: Optional[int] = None,
    ) -> List[NestZeile]:
        """Liefert die Segmentzeilen mit optionalen Filtern.

        Args:
            window_kind: Fensterart-Filter; None = alle.
            bar_start: Nur Segmente dieses Fensters (None = alle).
            bar_ende: Nur Segmente dieses Fensters (None = alle).

        Returns:
            Gefilterte Liste der Segmentzeilen.
        """
        out = list(self._nester)
        if window_kind is not None:
            fenster = self._fenster_mit_kind(window_kind)
            out = [z for z in out if (z.bar_start, z.bar_ende) in fenster]
        if bar_start is not None:
            out = [z for z in out if z.bar_start == bar_start]
        if bar_ende is not None:
            out = [z for z in out if z.bar_ende == bar_ende]
        return out

    def hole_bereiche(
        self,
        window_kind: Optional[str] = None,
        bar_start: Optional[int] = None,
        bar_ende: Optional[int] = None,
        rank: Optional[int] = None,
    ) -> List[BereichZeile]:
        """Liefert die Bereichszeilen (eigene Value Area je Segment).

        Args:
            window_kind: Fensterart-Filter; None = alle.
            bar_start: Nur Bereiche dieses Fensters (None = alle).
            bar_ende: Nur Bereiche dieses Fensters (None = alle).
            rank: Nur Bereiche dieses Ranges (None = alle).

        Returns:
            Gefilterte Liste der Bereichszeilen.
        """
        out = list(self._bereiche)
        if window_kind is not None:
            fenster = self._fenster_mit_kind(window_kind)
            out = [z for z in out if (z.bar_start, z.bar_ende) in fenster]
        if bar_start is not None:
            out = [z for z in out if z.bar_start == bar_start]
        if bar_ende is not None:
            out = [z for z in out if z.bar_ende == bar_ende]
        if rank is not None:
            out = [z for z in out if z.rank == rank]
        return out

    def hole_luecken(
        self,
        window_kind: Optional[str] = None,
        bar_start: Optional[int] = None,
        bar_ende: Optional[int] = None,
        nur_offene: bool = False,
    ) -> List[LueckeZeile]:
        """Liefert die Lueckenzeilen (Zwischenraum zweier Bereiche).

        Args:
            window_kind: Fensterart-Filter; None = alle.
            bar_start: Nur Luecken dieses Fensters (None = alle).
            bar_ende: Nur Luecken dieses Fensters (None = alle).
            nur_offene: True = nur Luecken mit echtem Zwischenraum
                (``breite > 0``), also ohne Ueberlappung.

        Returns:
            Gefilterte Liste der Lueckenzeilen.
        """
        out = list(self._luecken)
        if window_kind is not None:
            fenster = self._fenster_mit_kind(window_kind)
            out = [z for z in out if (z.bar_start, z.bar_ende) in fenster]
        if bar_start is not None:
            out = [z for z in out if z.bar_start == bar_start]
        if bar_ende is not None:
            out = [z for z in out if z.bar_ende == bar_ende]
        if nur_offene:
            out = [z for z in out if not z.ueberlappung]
        return out

    def zaehle(self) -> Dict[str, int]:
        """Zaehlt die gehaltenen Zeilen.

        Returns:
            Dict mit ``profiles``, ``nests``, ``bereiche``, ``luecken``,
            ``territorien``, ``nestobjekte`` und ``runs`` (1, wenn Zeilen
            vorliegen).
        """
        return {
            "profiles": len(self._profile),
            "nests": len(self._nester),
            "bereiche": len(self._bereiche),
            "luecken": len(self._luecken),
            "territorien": len(self._territorien),
            "nestobjekte": len(self._nestobjekte),
            "runs": 1 if self._profile else 0,
        }

    def leeren(self) -> None:
        """Verwirft alle gehaltenen Zeilen (Parameterwechsel)."""
        self._profile = []
        self._nester = []
        self._bereiche = []
        self._luecken = []
        self._territorien = []
        self._nestobjekte = []

    def speicher_mb(self) -> float:
        """ Schaetzt den Speicherbedarf der gehaltenen Zeilen in MByte.

        Returns:
            Grobe Obergrenze in MByte (nur die Zeilenobjekte, ohne Overhead).
        """
        import sys

        gesamt = sum(sys.getsizeof(z) for z in self._profile)
        gesamt += sum(sys.getsizeof(z) for z in self._nester)
        gesamt += sum(sys.getsizeof(z) for z in self._bereiche)
        gesamt += sum(sys.getsizeof(z) for z in self._luecken)
        gesamt += sum(sys.getsizeof(z) for z in self._territorien)
        gesamt += sum(sys.getsizeof(z) for z in self._nestobjekte)
        return float(gesamt) / (1024.0 * 1024.0)


class ProfilSpeicherHalter:
    """Haelt MEHRERE Laufzeit-Speicher - einer je Parametersatz (``run_id``).

    Der Halter ist der Einstiegspunkt fuer den Live-Einsatz: eine Ansicht (oder
    ein Diagramm) holt sich ihren Speicher ueber ``hole_oder_anlegen`` und
    bekommt bei gleichem Parametersatz exakt denselben Speicher zurueck - ohne
    Neuberechnung und ohne dass ein Parameterwechsel den alten Stand ueberschreibt.

    Die Schluessel sind die ``run_id``-Werte, also deterministisch aus Symbol,
    Timeframe, Fensterart und Volumenparametern gebildet.

    Attributes:
        HALTER: Prozessweiter Standard-Halter (Bequemlichkeit fuer Live).
    """

    def __init__(self) -> None:
        """Legt einen leeren Halter an."""
        self._speicher: Dict[str, ProfilSpeicher] = {}
        self._reihenfolge: List[str] = []

    def _registriere(self, speicher: ProfilSpeicher) -> str:
        """Traegt einen Speicher ein (intern, ohne Rueckgabeobjekt).

        Args:
            speicher: Laufzeit-Speicher.

        Returns:
            Die ``run_id`` des Speichers.
        """
        if speicher.run_id not in self._speicher:
            self._reihenfolge.append(speicher.run_id)
        self._speicher[speicher.run_id] = speicher
        return speicher.run_id

    def register(self, speicher: ProfilSpeicher) -> str:
        """Traegt einen fertigen Speicher ein und ersetzt gleiche ``run_id``.

        Args:
            speicher: Laufzeit-Speicher.

        Returns:
            Die ``run_id`` des Speichers.
        """
        return self._registriere(speicher)

    def hole(self, run_id: str) -> Optional[ProfilSpeicher]:
        """Liefert den Speicher einer ``run_id``.

        Args:
            run_id: Kennung des Parametersatzes.

        Returns:
            Der Speicher oder None, wenn die Kennung unbekannt ist.
        """
        return self._speicher.get(run_id)

    def hole_oder_anlegen(
        self,
        symbol: str,
        timeframe: str,
        window_kind: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ProfilSpeicher:
        """Liefert den Speicher eines Parametersatzes oder legt ihn neu an.

        Args:
            symbol: Symbol.
            timeframe: Timeframe.
            window_kind: Fensterart.
            params: Volumenparameter (gehen in die ``run_id`` ein).

        Returns:
            Der vorhandene (inhaltlich unveraenderte) oder ein neuer, leerer
            Speicher.
        """
        rid = _run_id(symbol, timeframe, window_kind, dict(params or {}))
        vorhanden = self._speicher.get(rid)
        if vorhanden is not None:
            return vorhanden
        return self.hole(self._registriere(
            ProfilSpeicher(symbol, timeframe, window_kind, params or {})
        ))  # type: ignore[return-value]

    def neuester(self) -> Optional[ProfilSpeicher]:
        """Liefert den zuletzt eingetragenen Speicher.

        Returns:
            Der zuletzt eingetragene Speicher oder None (Halter leer).
        """
        if not self._reihenfolge:
            return None
        return self._speicher.get(self._reihenfolge[-1])

    def run_ids(self) -> List[str]:
        """Liefert die Kennungen in Eintragsreihenfolge.

        Returns:
            Liste der ``run_id``-Werte (aeltester zuerst).
        """
        return list(self._reihenfolge)

    def verwerfen(self, run_id: str) -> bool:
        """Entfernt den Speicher eines Parametersatzes.

        Args:
            run_id: Kennung des Parametersatzes.

        Returns:
            True, wenn ein Speicher entfernt wurde.
        """
        if run_id not in self._speicher:
            return False
        del self._speicher[run_id]
        self._reihenfolge.remove(run_id)
        return True

    def leeren(self) -> None:
        """Verwirft alle gehaltenen Speicher."""
        self._speicher.clear()
        self._reihenfolge.clear()

    def zaehle(self) -> Dict[str, int]:
        """Zaehlt die gehaltenen Speicher und ihre Zeilen.

        Returns:
            Dict mit ``speicher`` (Anzahl Parametersaetze), ``profiles``,
            ``nests``, ``bereiche`` und ``luecken`` (Summen ueber alle
            Speicher).
        """
        return {
            "speicher": len(self._speicher),
            "profiles": sum(s.zaehle()["profiles"] for s in self._speicher.values()),
            "nests": sum(s.zaehle()["nests"] for s in self._speicher.values()),
            "bereiche": sum(
                s.zaehle()["bereiche"] for s in self._speicher.values()
            ),
            "luecken": sum(s.zaehle()["luecken"] for s in self._speicher.values()),
        }

    def speicher_mb(self) -> float:
        """Summiert den Speicherbedarf aller gehaltenen Speicher.

        Returns:
            Grobe Obergrenze in MByte.
        """
        return float(sum(s.speicher_mb() for s in self._speicher.values()))

    def __len__(self) -> int:
        """Anzahl gehaltener Speicher."""
        return len(self._speicher)

    def __contains__(self, run_id: object) -> bool:
        """Prueft, ob eine ``run_id`` gehalten wird."""
        return run_id in self._speicher

    def __iter__(self) -> "Iterator[ProfilSpeicher]":
        """Iteriert die Speicher in Eintragsreihenfolge."""
        return iter(self._speicher[r] for r in self._reihenfolge)


# Prozessweiter Standard-Halter: im Live-Einsatz teilen sich Ansichten/Charts
# diesen Halter, damit ein Parametersatz nur EINMAL gerechnet wird.
HALTER: ProfilSpeicherHalter = ProfilSpeicherHalter()
