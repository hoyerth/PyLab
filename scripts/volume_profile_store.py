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

Die frueher hier vorhandene DuckDB-Ablage (``ProfilStore`` mit den Tabellen
``volume_profiles``/``volume_profile_nests``/``volume_profile_runs``) liegt als
Referenz in ``scripts/archiv/volume_profile_store_db.py`` und ist nicht mehr
Teil der Engine.

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

Aufruf (aus einem Orchestrator):
    from scripts.volume_profile_store import HALTER
    speicher = HALTER.hole_oder_anlegen(symbol, timeframe, window_kind, params)
    speicher.merke(zeilen, nest_zeilen)
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


# =============================================================================
# LAUFZEIT-SPEICHER (RAM)
# =============================================================================


class ProfilSpeicher:
    """Laufzeit-Speicher fuer Volumenprofile (RAM, ohne Datei).

    Die Profile werden NUR im Arbeitsspeicher gehalten. Das ist der Regelweg:
    ein Profil ist an seinen Parametersatz gebunden und wird bei jeder
    Parameteraenderung sofort ungueltig - eine Ablegung in einer Datei waere
    dann Altbestand, der stillschweigend weiterverwendet werden koennte.

    Der Speicher haelt die Zeilenvertraege ``ProfilZeile``/``NestZeile`` und
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
        self, profile: Sequence[ProfilZeile], nests: Sequence[NestZeile]
    ) -> int:
        """Uebernimmt die Profilzeilen des Laufs in den Arbeitsspeicher.

        Ein erneuter Aufruf ersetzt den Bestand dieses ``run_id`` vollstaendig -
        damit kann kein vermischter Stand aus zwei Parameterlaeufen entstehen.

        Args:
            profile: Profilzeilen der Fenster.
            nests: Zu den Profilen gehoerende Segmentzeilen.

        Returns:
            Anzahl uebernommener Profilzeilen.
        """
        self._profile = list(profile)
        self._nester = list(nests)
        return len(self._profile)

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
            out = [z for z in out if z.window_kind == window_kind]
        if bar_start is not None:
            out = [z for z in out if z.bar_start == bar_start]
        if bar_ende is not None:
            out = [z for z in out if z.bar_ende == bar_ende]
        return out

    def zaehle(self) -> Dict[str, int]:
        """Zaehlt die gehaltenen Zeilen.

        Returns:
            Dict mit ``profiles``, ``nests`` und ``runs`` (1, wenn Zeilen
            vorliegen).
        """
        return {
            "profiles": len(self._profile),
            "nests": len(self._nester),
            "runs": 1 if self._profile else 0,
        }

    def leeren(self) -> None:
        """Verwirft alle gehaltenen Zeilen (Parameterwechsel)."""
        self._profile = []
        self._nester = []

    def speicher_mb(self) -> float:
        """ Schaetzt den Speicherbedarf der gehaltenen Zeilen in MByte.

        Returns:
            Grobe Obergrenze in MByte (nur die Zeilenobjekte, ohne Overhead).
        """
        import sys

        gesamt = sum(sys.getsizeof(z) for z in self._profile)
        gesamt += sum(sys.getsizeof(z) for z in self._nester)
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
            Dict mit ``speicher`` (Anzahl Parametersaetze), ``profiles`` und
            ``nests`` (Summen ueber alle Speicher).
        """
        return {
            "speicher": len(self._speicher),
            "profiles": sum(s.zaehle()["profiles"] for s in self._speicher.values()),
            "nests": sum(s.zaehle()["nests"] for s in self._speicher.values()),
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
