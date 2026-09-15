"""
VOLUMENPROFIL-NESTER (scripts/volume_profile_nests.py)
=======================================================
Nester als EIGENE OBJEKTE ueber Fenstergrenzen hinweg.

Warum
-----
Ein Volumenknoten richtet sich nicht nach dem Kalender: er wird an einem Tag
angesammelt und am naechsten weiter gehandelt. Die Fenster-Ebene (Tagesprofil)
zerlegt ihn deshalb an der Tagesgrenze in zwei Berge - jeder mit eigenem,
halbem Volumen. Diese Schicht erkennt den Knoten als GANZES und gibt ihm EINEN
POC/VAL/VAH.

Drei Begriffe (sauber getrennt)
-------------------------------
    BERG       Ergebnis der Berg-Erkennung IN EINEM Fenster. Traegt zwei
               Preisbaender: das ZUTEILUNGSBAND (Tal zu Tal, lueckenlose
               Tiling der Preisspanne) und den KERN (Value Area des Berges).
    KETTE      Berge AUFEINANDERFOLGENDER Fenster, deren KERNE sich im Preis
               ueberlappen UND deren POCs hoechstens ``link_level_atr``
               auseinanderliegen = derselbe Knoten ueber die Zeit. Sie ist
               ausschliesslich das BAR-VERZEICHNIS dieses Knotens.
    NEST       Ein ZUSAMMENHAENGENDER Lauf von Bars (Instanz). EIN Territorium
               traegt GENAU EINEN solchen Lauf: ist der Lauf unterbrochen (der
               Preis hat den Knoten zwischenzeitlich verlassen), entstehen
               ZWEI Territorien mit je EINEM Nest - die Rueckkehr auf ein
               Level ist ein NEUES Nest, nicht der Wiederbesuch des alten.

Ablauf
------
 1) ZUTEILUNG (je Fenster): Jeder Bar wird ueber seinen CLOSE dem Berg
    zugeordnet, in dessen ZUTEILUNGSBAND er schliesst. Die Baender benachbarter
    Berge tilen die Preisspanne des Fensters lueckenlos - jeder Bar gehoert
    damit genau EINEM Berg (kein Bar in zwei Nestern).
 2) KETTENBILDUNG (ueber die Zeit): Berge aufeinanderfolgender Fenster werden
    gepaart, wenn sich ihre KERNE (Value Areas) im Preis ueberlappen UND ihre
    POCs hoechstens ``link_level_atr`` (Default 2,0 ATR) auseinanderliegen.
    Gepaart wird guenstigst nach Ueberlappungsgroesse, jeder Berg hoechstens
    einmal - die Ketten sind damit ueberschneidungsfrei und deterministisch.
    Innerhalb EINES Fensters wird nie gepaart: zwei Berge desselben Profils
    sind per Konstruktion zwei Knoten.
 3) LAUF/INSTANZ: Die zugeordneten Bars einer Kette werden auf ZUSAMMENHANG im
    Bar-Index geprueft (K5: Primaerschluessel). Jeder zusammenhaengende Lauf
    ist eine Instanz, jedes Loch trennt zwei. Handelsfreie Zeiten liegen
    ausserhalb der BKZ-Achse und trennen daher NICHT - es gibt deshalb keinen
    Zeitluecken-Parameter.
    EIN TERRITORIUM TRAEGT GENAU EINEN LAUF: liefert eine Kette mehrere Laeufe,
    war der Preis zwischenzeitlich weg - das sind getrennte Knoten (auch bei
    gleichem Level), nicht der Wiederbesuch eines Territoriums. Damit sind die
    Nester kausal nacheinander geordnet (Rueckkehr erzeugt ein NEUES Nest).
 4) LEVEL: Jede Instanz bekommt ihr EIGENES Profil aus ihren eigenen Bars
    (``build_volume_profile``, unveraendert) und daraus POC/VAL/VAH
    (``va_for_mountain`` mit dem Gipfel als Berg). Der ATR einer Instanz ist
    der ATR IHRER Lebensdauer.
 5) RASTER: Damit die Level ueber Instanzen VERGLEICHBAR sind, bekommt jede
    Instanz denselben PREISSCHRITT (``schritt_atr`` * Bezugs-ATR). Da
    ``build_volume_profile`` seine Kanten selbst aus der Spanne bildet, wird
    die Bin-Anzahl daraus abgeleitet (``num_bins ~ Spannweite / Schritt``):
    die eingefrorene Funktion bleibt unberuehrt und die Bin-Breite ist
    trotzdem ueberall gleich. Der Bezugs-ATR ist der MEDIAN der Fenster-ATRs
    (robust gegen einzelne Ausreissertage) - NICHT der ATR der Instanz, sonst
    haetten verschiedene Instanzen verschiedene Raster.

Mindestgroesse
--------------
Laeufe unter ``min_bars`` Bars oder unter ``min_anteil_pct`` des groessten
Laufvolumens sind FLIMMER-Laeufe (kurze Ausfluege ueber die Talgrenze). Sie
bleiben als Zeile erhalten (``zu_klein``), gehen aber NICHT in die Statistik
ein - so ist kalibrierbar, wie viele es wirklich gibt.

Rand
----
Die Erkennung laeuft ueber einen GEPOLSTERTEN Zeitraum (``pad_tage`` davor und
danach). Instanzen, die den GELADENEN Rand beruehren, sind ``angeschnitten``:
sie koennen weiterlaufen, wir wissen es nur nicht. Sie gehen ebenfalls nicht in
die Statistik ein. Damit haengt die Datenqualitaet nicht an der exakten
Pad-Groesse - der Pad muss nur gross genug sein, und was uebrig bleibt, wird
ehrlich markiert.

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Alle Grenzen und Zuordnungen laufen ausschliesslich auf der BKZ-Achse
(tz-naiv). Der Bar-Index ist der Primaerschluessel jeder Bar-Aussage (K5); es
gibt keine Zeitzonen-Projektion (K2) und keine Bar-Konstante (K6).

Aufruf (aus dem Orchestrator):
    from scripts.volume_profile_nests import NestParameter, finde_nester
    ergebnis = finde_nester(profile, df, par, NestParameter())
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from scripts.volume_profile_core import (
    FensterProfil,
    PocKonsens,
    ProfilParameter,
    atr_einfach,
    build_volume_profile,
    filtere_volumen,
    smooth_vol,
    va_for_mountain,
)


# =============================================================================
# 1) PARAMETER
# =============================================================================


@dataclass(frozen=True, slots=True)
class NestParameter:
    """Parameter der Nest-Erkennung (alle extern konfigurierbar).

    Attributes:
        schritt_atr: Preisschritt des gemeinsamen RASTERS als Vielfaches des
            Bezugs-ATR (Default 0,25 = vier Bins je ATR). Er bestimmt die
            Aufloesung aller Instanzprofile und damit die Vergleichbarkeit der
            Level ueber Nester hinweg.
        link_toleranz_atr: Zusaetzliche Toleranz beim Paaren zweier Kerne, als
            Vielfaches des Bezugs-ATR (Default 0,0 = strenger Schnitt; zwei
            Kerne gehoeren nur zusammen, wenn sie sich wirklich ueberlappen).
        link_level_atr: Hoechster POC-ABSTAND zweier Berge, die noch gepaart
            werden duerfen, als Vielfaches des Bezugs-ATR (Default 2,0). Die
            reine Kern-Ueberlappung genuegt NICHT: laufen zwei Berge ueber
            verschiedene LEVEL, ist das keine Fortsetzung desselben Knotens,
            sondern eine Rueckkehr oder ein anderer Knoten - sonst entstehen
            Sammelobjekte mit einem POC ueber mehrere ATR (Empirie September
            2026: Kette mit POC-Spanne 7,4 ATR). 0 = nur identische POCs.
        min_bars: Mindestzahl Bars einer Instanz (Default 8 = rund zwei
            Stunden M15). Darunter ist der Lauf ein Flimmer-Lauf.
        min_anteil_pct: Mindestvolumen einer Instanz in Prozent des groessten
            Laufs (Default 4,0 - analog ``min_mountain_pct`` des Kerns).
        konsens_k: Rasterschritte (wie ``schritt_atr``), ueber die die
            POC-Unsicherheit einer Instanz gemessen wird. Die Unsicherheit ist
            hier eine AUFLOESUNGS-Unsicherheit (Bin-Breite), keine
            Bin-Anzahl-Unsicherheit wie im Fenster.
        konsens_smooth: Glaettungsfenster der Konsensmessung.
        streu_toleranz_atr: Toleranz fuer ``eindeutig`` in ATR der Instanz.
    """

    schritt_atr: float = 0.25
    link_toleranz_atr: float = 0.0
    link_level_atr: float = 2.0
    min_bars: int = 8
    min_anteil_pct: float = 4.0
    konsens_k: Tuple[float, ...] = (0.15, 0.25, 0.40)
    konsens_smooth: Tuple[int, ...] = (1, 3, 5, 9)
    streu_toleranz_atr: float = 1.0


# =============================================================================
# 2) DATENVERTRAEGE
# =============================================================================


@dataclass(frozen=True, slots=True)
class Bergband:
    """Ein Berg EINES Fensters mit seinen beiden Preisbaendern.

    Attributes:
        window_index: Position des Fensters in der zeitlich sortierten Liste.
        label: Fensterlabel.
        window_kind: Fensterart.
        fenster_bar_start: Erster Bar-Index des Fensters.
        fenster_bar_ende: Letzter Bar-Index des Fensters.
        rank: Rang des Berges im Fenster (0 = groesstes Volumen).
        zuteilung_unten: Untere Kante des ZUTEILUNGSBANDES (Tal zu Tal).
        zuteilung_oben: Obere Kante des Zuteilungsbandes.
        val: Untere Kante des KERNS (Berg-Value-Area).
        vah: Obere Kante des Kerns.
        poc: POC des Berges.
        vol: Volumen des Bergabschnitts.
    """

    window_index: int
    label: str
    window_kind: str
    fenster_bar_start: int
    fenster_bar_ende: int
    rank: int
    zuteilung_unten: float
    zuteilung_oben: float
    val: float
    vah: float
    poc: float
    vol: float


@dataclass(frozen=True, slots=True)
class Territorium:
    """EIN Lauf einer Kette gepaarter Berge: der Knoten als Zone ueber die Zeit.

    Jedes Territorium traegt GENAU EINEN zusammenhaengenden Lauf (Instanz) -
    die Kette wird also beim ersten Loch im Bar-Index geteilt, und jede Teilkette
    wird ein eigenes Territorium (K5, Bar-Index = Primaerschluessel). Report und
    Speicher fuehren beide Ebenen deshalb 1:1.

    Attributes:
        id: Laufende Nummer (0-basiert) = Position in der ZEIT (nach
            ``bar_start``); deckt sich mit der Reportreihenfolge.
        unten: Untere Kante des Territoriums (min der Zuteilungsbaender).
        oben: Obere Kante des Territoriums (max der Zuteilungsbaender).
        kern_unten: Untere Kante der Kernvereinigung (min der Berg-VALs).
        kern_oben: Obere Kante der Kernvereinigung (max der Berg-VAHs).
        n_berge: Anzahl gepaarter Berge.
        n_fenster: Anzahl beteiligter Fenster.
        labels: Fensterlabels in Zeitfolge.
        bar_start: Erster Bar-Index des Territoriums.
        bar_ende: Letzter Bar-Index des Territoriums.
        verschmolzen: True, wenn mehr als ein Fenster beteiligt ist (der
            Knoten reicht ueber eine Fenstergrenze - das ist der Fall, fuer den
            diese Schicht existiert).
    """

    id: int
    unten: float
    oben: float
    kern_unten: float
    kern_oben: float
    n_berge: int
    n_fenster: int
    labels: Tuple[str, ...]
    bar_start: int
    bar_ende: int
    verschmolzen: bool

    @property
    def breite(self) -> float:
        """Breite des Territoriums in Preiseinheiten."""
        return float(self.oben - self.unten)


@dataclass(frozen=True, slots=True)
class NestInstanz:
    """Ein Nest: EIN zusammenhaengender Lauf von Bars innerhalb eines Territoriums.

    Attributes:
        id: Laufende Nummer (0-basiert, nach ``bar_start``).
        territorium_id: Zugehoeriges Territorium.
        rang: Reihenfolge der Instanz innerhalb ihres Territoriums. Da ein
            Territorium genau EINEN Lauf traegt, ist das IMMER 0; das Feld
            bleibt fuer den Speicher-/TSV-Vertrag erhalten.
        bar_start: Erster Bar-Index der Instanz.
        bar_ende: Letzter Bar-Index der Instanz.
        ts_start: Erster BKZ-Zeitstempel (tz-naiv).
        ts_ende: Letzter BKZ-Zeitstempel.
        n_bars: Anzahl Bars der Instanz.
        n_fenster: Anzahl beteiligter Fenster (1 = nicht verschmolzen).
        poc: Point of Control der Instanz (Gipfel des eigenen Profils).
        val: Untere Kante der Instanz-Value-Area.
        vah: Obere Kante der Instanz-Value-Area.
        vol: Volumen der Instanz (Rohprofil der eigenen Bars).
        atr: ATR der eigenen Lebensdauer (Bezugsgroesse aller ATR-Breiten).
        raster_bins: Bin-Anzahl des gemeinsamen Rasters fuer diese Instanz.
        raster_schritt: Tatsaechliche Bin-Breite in Preiseinheiten.
        zu_klein: True = Flimmer-Lauf (geht nicht in die Statistik ein).
        angeschnitten: True = beruehrt den geladenen Rand (kann weiterlaufen).
        konsens: POC-Unsicherheit ueber die Rasterschritte (Aufholoesung).
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
    vol: float
    atr: float
    raster_bins: int
    raster_schritt: float
    zu_klein: bool
    angeschnitten: bool
    konsens: PocKonsens = field(default_factory=PocKonsens)

    @property
    def breite(self) -> float:
        """Breite der Instanz-Value-Area in Preiseinheiten."""
        return float(self.vah - self.val)

    @property
    def breite_atr(self) -> float:
        """Breite der Instanz-Value-Area in ATR ihrer Lebensdauer."""
        if not (np.isfinite(self.atr) and self.atr > 0.0):
            return float("nan")
        return float(self.breite / self.atr)

    @property
    def gueltig(self) -> bool:
        """True, wenn die Instanz als Nest zaehlt (nicht flimmern/angeschnitten)."""
        return not (self.zu_klein or self.angeschnitten)

    @property
    def dauer_stunden(self) -> float:
        """Lebensdauer in Stunden (BKZ)."""
        return float((self.ts_ende - self.ts_start).total_seconds() / 3600.0)


@dataclass(frozen=True, slots=True)
class NestErgebnis:
    """Ergebnis der Nest-Erkennung ueber den ganzen Zeitraum.

    Attributes:
        territorien: Ketten (Knoten als Zone).
        instanzen: Nester (zusammenhaengende Laeufe), nach ``bar_start``.
        berge: Alle beteiligten Berge (Zuteilungsnachweis).
        atr_bezug: Bezugs-ATR des Rasters (Median der Fenster-ATRs).
        schritt: Preisschritt des Rasters in Preiseinheiten.
        n_laeufe_roh: Anzahl Laeufe VOR der Mindestgroessenpruefung.
    """

    territorien: Tuple[Territorium, ...] = ()
    instanzen: Tuple[NestInstanz, ...] = ()
    berge: Tuple[Bergband, ...] = ()
    atr_bezug: float = float("nan")
    schritt: float = float("nan")
    n_laeufe_roh: int = 0

    @property
    def n_territorien(self) -> int:
        """Anzahl Territorien (Knoten)."""
        return len(self.territorien)

    @property
    def n_instanzen(self) -> int:
        """Anzahl aller Instanzen (inkl. Flimmer und angeschnittene)."""
        return len(self.instanzen)

    @property
    def nester(self) -> Tuple[NestInstanz, ...]:
        """Nur die zaehlenden Nester (nicht flimmern/angeschnitten)."""
        return tuple(i for i in self.instanzen if i.gueltig)

    @property
    def n_verschmolzen(self) -> int:
        """Anzahl Territorien, die ueber eine Fenstergrenze reichen."""
        return sum(1 for t in self.territorien if t.verschmolzen)

    @property
    def n_zu_klein(self) -> int:
        """Anzahl Flimmer-Laeufe (ausserhalb der Statistik)."""
        return sum(1 for i in self.instanzen if i.zu_klein)

    @property
    def n_angeschnitten(self) -> int:
        """Anzahl angeschnittener Instanzen (ausserhalb der Statistik)."""
        return sum(1 for i in self.instanzen if i.angeschnitten)

    @property
    def n_mehrfach(self) -> int:
        """Anzahl Territorien mit mehr als EINER Instanz - strukturell IMMER 0.

        Ein Territorium traegt per Konstruktion genau einen Lauf (Rueckkehr
        erzeugt ein neues Territorium). Die Kennzahl bleibt als Kontrolle
        bestehen: ein Wert ungleich 0 waere ein Fehler in der Aufteilung.
        """
        zaehler: Dict[int, int] = {}
        for i in self.instanzen:
            if i.gueltig:
                zaehler[i.territorium_id] = zaehler.get(i.territorium_id, 0) + 1
        return sum(1 for n in zaehler.values() if n > 1)


# =============================================================================
# 3) ZUTEILUNG UND KETTEN
# =============================================================================


def _berge_eines_fensters(p: FensterProfil, window_index: int) -> List[Bergband]:
    """Bildet die Bergbaender eines Fensters aus seiner Segmentierung.

    Die Zuteilungsbaender sind Tal zu Tal (``bin_start`` bis ``bin_ende``) und
    tilen die Preisspanne des Fensters lueckenlos; der Kern ist die
    Berg-Value-Area (``nest.val``/``nest.vah``).

    Args:
        p: Fensterprofil.
        window_index: Position in der zeitlich sortierten Fensterliste.

    Returns:
        Bergbaender in der Rangfolge der Segmente (0 = groesstes).
    """
    seg = p.segmentierung
    if seg is None:
        return []
    edges = seg.profile.edges
    out: List[Bergband] = []
    for rank, (m, nest) in enumerate(zip(seg.mountains, seg.nester)):
        s, _peak, e = m
        unten = float(edges[s])
        oben = float(edges[min(e + 1, edges.size - 1)])
        if not (np.isfinite(unten) and np.isfinite(oben)) or oben <= unten:
            continue
        out.append(
            Bergband(
                window_index=window_index, label=p.label,
                window_kind=p.window_kind,
                fenster_bar_start=int(p.bar_start),
                fenster_bar_ende=int(p.bar_ende), rank=rank,
                zuteilung_unten=unten, zuteilung_oben=oben,
                val=float(nest.val), vah=float(nest.vah), poc=float(nest.poc),
                vol=float(nest.vol),
            )
        )
    return out


def _ordne_bars_zu(
    df: pd.DataFrame, berge: Sequence[Bergband]
) -> Dict[int, np.ndarray]:
    """Ordnet jedem Berg eines Fensters seine Bars ueber den CLOSE zu.

    Die Zuteilungsbaender tilen die Preisspanne des Fensters; die Zuordnung
    laeuft deshalb ueber die unteren Kanten (sortiert) per ``searchsorted`` -
    jeder Bar faellt in genau EIN Band. Der Close ist der Zuteilungspreis: ein
    Breakout-Bar beendet den Lauf, statt zwei Nester zu verbinden.

    Args:
        df: Bars des Gesamtzeitraums (BKZ).
        berge: Bergbaender GENAU EINES Fensters.

    Returns:
        ``{berg_index_in_berge: bar_indizes}``; leere Zuordnungen fehlen.
    """
    if not berge:
        return {}
    unten = np.array([b.zuteilung_unten for b in berge], dtype=float)
    reihenfolge = np.argsort(unten, kind="stable")
    kanten = unten[reihenfolge]
    i0 = int(berge[0].fenster_bar_start)
    i1 = int(berge[0].fenster_bar_ende)
    closes = df["close"].to_numpy(dtype=float)[i0 : i1 + 1]
    pos = np.searchsorted(kanten, closes, side="right") - 1
    pos = np.clip(pos, 0, kanten.size - 1)
    # Position in der Preissortierung -> Index in ``berge``
    zuordnung = reihenfolge[pos]
    bar_indizes = np.arange(i0, i1 + 1, dtype=int)
    out: Dict[int, np.ndarray] = {}
    for k in np.unique(zuordnung):
        out[int(k)] = bar_indizes[zuordnung == k]
    return out


def _ueberlappung(a: Bergband, b: Bergband) -> float:
    """Ueberlappung zweier KERNbaender in Preiseinheiten (<= 0 = keine).

    Args:
        a: Berg des vorherigen Fensters.
        b: Berg des aktuellen Fensters.

    Returns:
        ``min(a.vah, b.vah) - max(a.val, b.val)``.
    """
    return float(min(a.vah, b.vah) - max(a.val, b.val))


def _baue_ketten(
    fenster_berge: Sequence[Sequence[Bergband]],
    toleranz: float,
    level_toleranz: float = float("inf"),
) -> List[List[Tuple[int, int]]]:
    """Paart Berge aufeinanderfolgender Fenster zu Ketten.

    Gepaart wird nach Ueberlappung der KERNbaender, guenstigst zuerst (jeder
    Berg hoechstens einmal) - die Ketten sind damit ueberschneidungsfrei und
    deterministisch. Ein Berg ohne Partner beginnt eine neue Kette. Innerhalb
    EINES Fensters wird nie gepaart.

    ZUSAETZLICH muss der POC-Abstand der beiden Berge ``level_toleranz``
    einhalten: eine Kern-Ueberlappung allein sagt nichts ueber das LEVEL. Zwei
    Berge, deren POCs ATR-weit auseinanderliegen, sind verschiedene Knoten
    (oder eine Rueckkehr) - ohne diese Schranke entstuenden Sammelobjekte mit
    einem POC ueber die ganze Spanne.

    Args:
        fenster_berge: Berge je Fenster in Zeitfolge.
        toleranz: Zusaetzliche Ueberlappungstoleranz in Preiseinheiten.
        level_toleranz: Hoechster POC-Abstand in Preiseinheiten
            (``inf`` = keine Schranke).

    Returns:
        Ketten als Folgen von ``(fenster_index, berg_index)``.
    """
    ketten: List[List[Tuple[int, int]]] = []
    kette_von: Dict[Tuple[int, int], int] = {}
    for wi, berge in enumerate(fenster_berge):
        if not berge:
            continue
        vorher: Optional[Sequence[Bergband]] = None
        vorher_wi: int = -1
        for wj in range(wi - 1, -1, -1):
            if fenster_berge[wj]:
                vorher = fenster_berge[wj]
                vorher_wi = wj
                break
        paare: List[Tuple[float, int, int]] = []
        if vorher is not None:
            for j, b in enumerate(berge):
                for i, a in enumerate(vorher):
                    ueber = _ueberlappung(a, b)
                    if ueber <= toleranz:
                        continue
                    if abs(float(a.poc) - float(b.poc)) > level_toleranz:
                        continue
                    paare.append((ueber, i, j))
        # Groesste Ueberlappung zuerst; bei Gleichstand stabil nach Rang.
        paare.sort(key=lambda t: (-t[0], t[1], t[2]))
        belegt_vorher: set = set()
        belegt_jetzt: set = set()
        partner: Dict[int, int] = {}
        for _ueber, i, j in paare:
            if i in belegt_vorher or j in belegt_jetzt:
                continue
            belegt_vorher.add(i)
            belegt_jetzt.add(j)
            partner[j] = i
        for j, b in enumerate(berge):
            if j in partner:
                kid = kette_von[(vorher_wi, partner[j])]
                ketten[kid].append((wi, j))
            else:
                ketten.append([(wi, j)])
                kid = len(ketten) - 1
            kette_von[(wi, j)] = kid
    return ketten


def _laeufe(indizes: np.ndarray) -> List[Tuple[int, int]]:
    """Zerlegt Bar-Indizes in zusammenhaengende Laeufe.

    Zusammenhangend heisst ``index + 1`` (K5: Bar-Index als Primaerschluessel).
    Handelsfreie Zeiten liegen ausserhalb der BKZ-Achse und trennen daher
    nicht - es braucht keine Zeitluecken-Konvention.

    Args:
        indizes: Aufsteigende, eindeutige Bar-Indizes.

    Returns:
        Liste ``(erster_bar, letzter_bar)`` in aufsteigender Reihenfolge.
    """
    if indizes.size == 0:
        return []
    brueche = np.flatnonzero(np.diff(indizes) > 1)
    starts = np.concatenate(([0], brueche + 1))
    enden = np.concatenate((brueche, [indizes.size - 1]))
    return [
        (int(indizes[s]), int(indizes[e])) for s, e in zip(starts, enden)
    ]


# =============================================================================
# 4) LEVEL EINER INSTANZ
# =============================================================================


def _raster_bins(spanne: float, schritt: float) -> int:
    """Leitet die Bin-Anzahl aus Spannweite und gewuenschtem Preisschritt ab.

    Damit ist die Bin-Breite ueber alle Instanzen gleich, obwohl
    ``build_volume_profile`` seine Kanten selbst aus der Spanne bildet (die
    eingefrorene Funktion bleibt unberuehrt).

    Args:
        spanne: Preisspanne der Instanz.
        schritt: Gewuenschter Preisschritt.

    Returns:
        Bin-Anzahl (mindestens 3, damit ein Profil entstehen kann).
    """
    if not (np.isfinite(spanne) and spanne > 0.0):
        return 3
    if not (np.isfinite(schritt) and schritt > 0.0):
        return 60
    return max(3, int(round(spanne / schritt)))


def _poc_bei_bins(bars: pd.DataFrame, bins: int, smooth: int) -> float:
    """POC eines Bar-Satzes bei gegebener Bin-Anzahl.

    Args:
        bars: Bars (bereits volumenfiltert).
        bins: Bin-Anzahl.
        smooth: Glaettungsfenster.

    Returns:
        POC in Preiseinheiten; ``nan``, wenn kein Profil entsteht.
    """
    prof = build_volume_profile(bars, bins)
    if prof is None:
        return float("nan")
    vol_s = smooth_vol(prof.vol, smooth)
    if vol_s.size == 0 or float(vol_s.max()) <= 0.0:
        return float("nan")
    return float(
        (prof.edges[int(np.argmax(vol_s))] + prof.edges[int(np.argmax(vol_s)) + 1])
        / 2
    )


def _instanz_level(
    bars: pd.DataFrame,
    par: ProfilParameter,
    nest: NestParameter,
    atr_bezug: float,
    atr_lauf: float,
) -> Optional[Tuple[float, float, float, float, int, float, PocKonsens]]:
    """Rechnet POC/VAL/VAH eines Laufs auf dem gemeinsamen Raster.

    Es wird die EINGEFRORENE Volumenlogik verwendet (``build_volume_profile``
    und ``va_for_mountain``); nur die Bin-Anzahl kommt aus dem Rasterschritt.
    Der Berg ist hier das ganze Laufsprofil, die Value Area wird vom Gipfel aus
    nach aussen erweitert (``par.va_pct``).

    Args:
        bars: Bars des Laufs (ungefiltert).
        par: Volumenparameter des Laufs (Bins/Glaettung/Anteil/Filter).
        nest: Nest-Parameter (Rasterschritt, Konsenssaetze).
        atr_bezug: Bezugs-ATR des Rasters.
        atr_lauf: ATR der Instanz-Lebensdauer (Bezug der Streuung).

    Returns:
        ``(poc, val, vah, vol, raster_bins, raster_schritt, konsens)`` oder
        ``None``, wenn kein Profil entsteht.
    """
    gefiltert, _n = filtere_volumen(bars, par.vol_min, par.vol_quantil)
    if gefiltert.empty:
        return None
    spanne = float(gefiltert["high"].max() - gefiltert["low"].min())
    if not np.isfinite(spanne) or spanne <= 0.0:
        return None
    schritt = (
        float(nest.schritt_atr * atr_bezug)
        if np.isfinite(atr_bezug) and atr_bezug > 0.0
        else float("nan")
    )
    bins = _raster_bins(spanne, schritt)
    prof = build_volume_profile(gefiltert, bins)
    if prof is None:
        return None
    vol_s = smooth_vol(prof.vol, par.smooth_win)
    if vol_s.size == 0 or float(vol_s.max()) <= 0.0:
        return None
    gipfel = int(np.argmax(vol_s))
    nest_va = va_for_mountain(
        vol_s, prof.edges, (0, gipfel, bins - 1), gipfel, par.va_pct
    )
    vol_gesamt = float(prof.vol.sum())
    # POC-Unsicherheit: hier die AUFLOESUNG variieren (Rasterschritt), nicht die
    # Bin-Anzahl - das Raster ist die Bezugsgroesse dieser Schicht.
    saetze = sorted({float(k) for k in nest.konsens_k} | {float(nest.schritt_atr)})
    pocs: List[float] = []
    for k in saetze:
        for sm in nest.konsens_smooth or (par.smooth_win,):
            schritt_k = float(k * atr_bezug) if np.isfinite(atr_bezug) else float("nan")
            p = _poc_bei_bins(gefiltert, _raster_bins(spanne, schritt_k), int(sm))
            if np.isfinite(p):
                pocs.append(p)
    if pocs:
        p_min, p_max = float(min(pocs)), float(max(pocs))
        streu = (
            float((p_max - p_min) / atr_lauf)
            if np.isfinite(atr_lauf) and atr_lauf > 0.0
            else float("nan")
        )
        kons = PocKonsens(
            poc_min=p_min, poc_max=p_max, streu_atr=streu,
            eindeutig=bool(np.isfinite(streu) and streu <= nest.streu_toleranz_atr),
            n_saetze=len(pocs),
        )
    else:
        kons = PocKonsens()
    return (
        float(nest_va.poc), float(nest_va.val), float(nest_va.vah), vol_gesamt,
        int(bins), float(spanne / bins), kons,
    )


# =============================================================================
# 5) ERKENNUNG
# =============================================================================


def finde_nester(
    profile: Sequence[FensterProfil],
    df: pd.DataFrame,
    par: ProfilParameter,
    nest: Optional[NestParameter] = None,
) -> NestErgebnis:
    """Erkennt Nester als eigene Objekte ueber die Fenstergrenzen hinweg.

    Ablauf: Zuteilung der Bars je Fenster -> Kettenbildung ueber die Kerne ->
    Schnitt in zusammenhaengende Laeufe (Instanzen) -> Level je Instanz auf
    einem gemeinsamen Preisraster -> Mindestgroessen- und Randpruefung.

    Es wird NICHTS am Kern geaendert: die Berge kommen aus der eingefrorenen
    Berg-Erkennung, die Level aus ``build_volume_profile``/``va_for_mountain``.

    Args:
        profile: Fensterprofile des ZEITRAUMS (inkl. Polster, zeitlich beliebig).
        df: Bars des geladenen Zeitraums (BKZ; Spalten ``close/ts/high/low``).
        par: Volumenparameter des Laufs.
        nest: Nest-Parameter; None = Defaults.

    Returns:
        ``NestErgebnis`` mit Territorien, Instanzen und Bezugsgroessen.
    """
    np_par = nest or NestParameter()
    fenster = sorted(
        (p for p in profile if p.gueltig), key=lambda p: int(p.bar_start)
    )
    if not fenster or df.empty:
        return NestErgebnis()

    atr_werte = np.array(
        [p.atr for p in fenster if np.isfinite(p.atr) and p.atr > 0.0], dtype=float
    )
    atr_bezug = float(np.median(atr_werte)) if atr_werte.size else float("nan")
    schritt = (
        float(np_par.schritt_atr * atr_bezug)
        if np.isfinite(atr_bezug) and atr_bezug > 0.0
        else float("nan")
    )

    # 1) Berge je Fenster + Zuteilung der Bars
    fenster_berge: List[List[Bergband]] = []
    zuteilung: Dict[Tuple[int, int], np.ndarray] = {}
    for wi, p in enumerate(fenster):
        berge = _berge_eines_fensters(p, wi)
        fenster_berge.append(berge)
        for k, indizes in _ordne_bars_zu(df, berge).items():
            zuteilung[(wi, k)] = indizes

    # 2) Ketten
    toleranz = (
        float(np_par.link_toleranz_atr * atr_bezug)
        if np.isfinite(atr_bezug) and np_par.link_toleranz_atr > 0.0
        else 0.0
    )
    level_toleranz = (
        float(np_par.link_level_atr * atr_bezug)
        if np.isfinite(atr_bezug) and np_par.link_level_atr > 0.0
        else (
            0.0 if np.isfinite(atr_bezug) else float("inf")
        )
    )
    ketten = _baue_ketten(fenster_berge, toleranz, level_toleranz)

    # 3) Territorien: EIN Territorium je ZUSAMMENHAENGENDEM Lauf (K5).
    #    Ein Territorium traegt damit genau EINE Instanz (``NestInstanz.rang``
    #    ist immer 0). Die Kette dient nur noch der Zuordnung der Bars: liefert
    #    sie mehrere Laeufe, ist der Preis zwischenzeitlich weg gewesen - das
    #    sind getrennte Knoten (Rueckkehr), keine Wiederbesuche desselben
    #    Territoriums.
    territorien: List[Territorium] = []
    terr_ketten: Dict[int, List[Tuple[int, int]]] = {}
    terr_fenster: Dict[int, List[int]] = {}
    roh: List[Tuple[int, int, int, int]] = []  # (terr_id, a, b, n_fenster)
    for kette in ketten:
        if not kette:
            continue
        vorhanden = [(wi, j) for wi, j in kette if (wi, j) in zuteilung]
        if not vorhanden:
            continue
        alle = np.unique(np.concatenate([zuteilung[wi, j] for wi, j in vorhanden]))
        for a, b in _laeufe(alle):
            teil = [
                (wi, j) for wi, j in vorhanden
                if zuteilung[wi, j].size
                and int(zuteilung[wi, j][-1]) >= a and int(zuteilung[wi, j][0]) <= b
            ]
            if not teil:
                continue
            baender = [fenster_berge[wi][j] for wi, j in teil]
            wi_alle = sorted({wi for wi, _j in teil})
            n_fenster = int(
                sum(
                    1 for wi in wi_alle
                    if fenster[wi].bar_ende >= a and fenster[wi].bar_start <= b
                )
            )
            tid = len(territorien)
            terr_ketten[tid] = teil
            terr_fenster[tid] = wi_alle
            roh.append((tid, a, b, n_fenster))
            territorien.append(
                Territorium(
                    id=tid,
                    unten=float(min(x.zuteilung_unten for x in baender)),
                    oben=float(max(x.zuteilung_oben for x in baender)),
                    kern_unten=float(min(x.val for x in baender)),
                    kern_oben=float(max(x.vah for x in baender)),
                    n_berge=len(baender),
                    n_fenster=n_fenster,
                    labels=tuple(fenster[wi].label for wi in wi_alle),
                    bar_start=int(a),
                    bar_ende=int(b),
                    verschmolzen=bool(n_fenster > 1),
                )
            )
    # Rang je Territorium = Reihenfolge der Instanzen in der Zeit. Da ein
    # Territorium genau EINEN Lauf traegt, ist er immer 0 (Feld bleibt fuer
    # den Speichervertrag erhalten).
    # Die Territorien werden nach ihrem ersten Bar neu durchnummeriert: die
    # Id ist damit die Position in der ZEIT und deckt sich mit der Reihenfolge
    # im Report (Bar-Index = Primaerschluessel, K5).
    ordnung = sorted(
        range(len(territorien)), key=lambda t: (territorien[t].bar_start, t)
    )
    neu_id: Dict[int, int] = {alt: i for i, alt in enumerate(ordnung)}
    territorien = [
        replace(territorien[alt], id=neu_id[alt]) for alt in ordnung
    ]
    roh = [(neu_id[t], a, b, nf) for t, a, b, nf in roh if t in neu_id]
    roh.sort(key=lambda t: (t[1], t[0]))

    # 5) Level je Lauf (gemeinsames Raster, ATR der eigenen Lebensdauer)
    vorlaeufig: List[Dict[str, Any]] = []
    for tid, a, b, n_fenster in roh:
        sub = df.iloc[a : b + 1]
        atr_lauf = atr_einfach(sub)
        level = _instanz_level(sub, par, np_par, atr_bezug, atr_lauf)
        if level is None:
            continue
        poc, val, vah, vol, bins, bschritt, kons = level
        vorlaeufig.append(
            {
                "territorium_id": tid, "rang": 0,
                "bar_start": a, "bar_ende": b, "n_bars": int(b - a + 1),
                "n_fenster": n_fenster, "poc": poc, "val": val, "vah": vah,
                "vol": vol, "atr": atr_lauf, "raster_bins": bins,
                "raster_schritt": bschritt, "konsens": kons,
            }
        )

    # 6) Mindestgroesse und Rand
    max_vol = max((v["vol"] for v in vorlaeufig), default=float("nan"))
    grenze = (
        float(np_par.min_anteil_pct) / 100.0 * max_vol
        if np.isfinite(max_vol) and max_vol > 0.0
        else 0.0
    )
    letzter_bar = int(len(df) - 1)
    instanzen: List[NestInstanz] = []
    for i, v in enumerate(vorlaeufig):
        instanzen.append(
            NestInstanz(
                id=i,
                territorium_id=int(v["territorium_id"]),
                rang=int(v["rang"]),
                bar_start=int(v["bar_start"]),
                bar_ende=int(v["bar_ende"]),
                ts_start=pd.Timestamp(df["ts"].iloc[int(v["bar_start"])]),
                ts_ende=pd.Timestamp(df["ts"].iloc[int(v["bar_ende"])]),
                n_bars=int(v["n_bars"]),
                n_fenster=int(v["n_fenster"]),
                poc=float(v["poc"]),
                val=float(v["val"]),
                vah=float(v["vah"]),
                vol=float(v["vol"]),
                atr=float(v["atr"]),
                raster_bins=int(v["raster_bins"]),
                raster_schritt=float(v["raster_schritt"]),
                zu_klein=bool(
                    v["n_bars"] < np_par.min_bars or v["vol"] < grenze
                ),
                angeschnitten=bool(
                    int(v["bar_start"]) <= 0 or int(v["bar_ende"]) >= letzter_bar
                ),
                konsens=v["konsens"],
            )
        )

    berge = tuple(b for gruppe in fenster_berge for b in gruppe)
    return NestErgebnis(
        territorien=tuple(territorien),
        instanzen=tuple(instanzen),
        berge=berge,
        atr_bezug=atr_bezug,
        schritt=schritt,
        n_laeufe_roh=len(roh),
    )
