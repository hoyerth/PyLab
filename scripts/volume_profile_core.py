"""
VOLUMENPROFIL-KERN (scripts/volume_profile_core.py)
====================================================
Reine Rechenlogik zur Ermittlung von Volumenprofilen und ihren Leveln.
Kein Datei-I/O, keine Datenbank, kein Plot, keine Zeitfenster-Logik - dieses
Modul kennt nur Bars und Parameter.

Zwei Ebenen werden getrennt berechnet und BEIDE ausgegeben:

  1) SEGMENTE (Berge/"Nester") - Ergebnis der Berg-Zerlegung
     ``find_mountains``. Jeder Berg traegt seinen eigenen POC/VAL/VAH.
     Das ist die Segment-Erkennung, die sich in der Sichtpruefung bewaehrt
     hat und unveraendert weiterlaeuft.

  2) ZONEN-VALUE-AREA ab POC - ``va_von_poc``
     Vom globalen POC des Profils wird der Wertbereich symmetrisch nach
     aussen erweitert, bis ``va_zone_pct`` des Gesamtvolumens erfasst sind
     (Default 0,94). Das ist die Zonen-Klammer: sie soll moeglichst viele
     Wendepunkte treffen und ist breiter als eine 70%-Value-Area.

Wichtig - Semantik der beiden Schwellen:
  ``va_pct``       Anteil des BERGVOLUMENS fuer die Value Area EINES Berges
                   (Baseline-Wert 0,93, unveraendert). Fuer die Separation ist
                   das der wirksame Hebel: ein kleinerer Wert (z. B. 0,70)
                   schneidet enger um den Gipfel und trennt benachbarte Nester
                   deutlicher, weil Bergraender nicht mehr in die Nachbarzone
                   reichen.
  ``va_zone_pct``  Anteil des GESAMTVOLUMENS fuer die Zonen-Value-Area ab dem
                   globalen POC (Default 0,94).
Beide werden getrennt gefuehrt; kein Wert wird stillschweigend wiederverwendet.

Separation (getrennte Bereiche statt eines Bandes)
--------------------------------------------------
Das Hauptband ist EIN zusammenhaengender Preisbereich und damit meist breiter
als der Move, den es beschreiben soll - genau deshalb ist der fruehere
Huell-Modus ``balance`` entfernt. Die Separation zerlegt das Ergebnis
zusaetzlich in den EIGENEN Bereich je Segment (``Bereich`` = dessen
``[VAL .. VAH]``) und in die ``Luecke`` zwischen zwei benachbarten Bereichen -
dort laufen die schnellen Moves. Es wird dabei nichts neu gerechnet
(``zerlege_bereiche`` nutzt die Value Areas der bereits erkannten Segmente);
``Separierung.anteil_ausserhalb`` ist das Mass der Isolation.

Abgrenzung zur eingefrorenen Baseline
-------------------------------------
``build_volume_profile`` / ``smooth_vol`` / ``find_mountains`` /
``va_for_mountain`` sind VERBATIM aus ``scripts/phasen_volumen_profil.py``
(v0.4.0-baseline-frozen, Z. 478-608) uebernommen - identische Algorithmik,
identische Defaults. Die Baseline selbst bleibt byte-identisch unberuehrt.
``va_von_poc`` / ``volumenfilter`` / ``zweitgipfel`` sind Zusatzfunktionen
dieses Projekts und aendern die Baseline-Logik nicht.

Volumenfilter
-------------
Der Filter greift VOR dem Profilbau auf die Bars des jeweiligen Fensters:
  ``vol_min``      absolute Untergrenze des ``tick_volume`` einer Bar
  ``vol_quantil``  zusaetzlich das unterste q-Quantil der Bar-Volumina des
                   Fensters (relativ, gegen Ausreisser-arme Illiquiditaet)
Gefilterte Bars gehen nicht ins Profil ein; die Anzahl wird mitberichtet.

Hauptband (nur noch ``zone``)
-----------------------------
Es gibt genau EIN Hauptband: ``Segmentierung.zone`` (Zonen-VA ab POC, Anteil am
Gesamtvolumen). Der fruehere Modus ``balance`` (Huelle der Segment-Value-Areas)
ist aus der Auswertung ENTFERNT: die Huelle deckte die Luecken zwischen den
Nestern zu und war genau das, was die Separation aufloest.

Die Huellkanten werden im Kern weitergefuehrt
(``Segmentierung.val_huelle``/``vah_huelle`` = min/max der Berg-VAL/VAH) und
ihre Deckung als Kennzahl berechnet (``huellen_abdeckung``) - damit bleibt die
Bitgleichheit zum archivierten Tages-Balancen-Lauf pruefbar, ohne dass daraus
ein Auswertungsmodus wird.

Aufruf (aus einem Orchestrator, kein CLI in diesem Modul):
    from scripts.volume_profile_core import ProfilParameter, compute_segmentierung
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# =============================================================================
# 1) PARAMETER
# =============================================================================


@dataclass(frozen=True, slots=True)
class ProfilParameter:
    """Volumenparameter eines Profils (Werte der eingefrorenen Baseline).

    Attributes:
        num_bins: Anzahl Preis-Bins des Histogramms (Baseline ``NUM_BINS``).
        smooth_win: Glaettungsfenster des Volumens (Baseline ``SMOOTH_WIN``).
        va_pct: Anteil des BERGVOLUMENS fuer die Value Area eines einzelnen
            Berges (Baseline ``VA_PCT``).
        valley_rel: Relativer Tal-Schwellwert zur Berg-Trennung
            (Baseline ``VALLEY_REL``).
        min_mountain_pct: Mindest-Volumenanteil eines Berges am groessten Berg
            in Prozent (Baseline ``MIN_MOUNTAIN_PCT``).
        va_zone_pct: Anteil des GESAMTVOLUMENS fuer die Zonen-Value-Area ab dem
            globalen POC (Default 0,94 - breiter als die uebliche 70%-VA, damit
            moeglichst viele Wendepunkte im Band liegen).
        lobe_fenster: Bins links/rechts des Gipfels, die bei der
            Zweitgipfel-Suche ausgeblendet werden (Unsicherheits-Diagnose).
        lobe2_schwelle: Ab dieser Zweitgipfel-Ratio gilt das Profil als
            strukturell zweilappig (reine Diagnose).
        vol_min: Absolute Untergrenze des ``tick_volume`` einer Bar (0 = aus).
        vol_quantil: Anteil der volumenaermsten Bars des Fensters, der
            zusaetzlich verworfen wird (0 = aus).
    """

    num_bins: int = 60
    smooth_win: int = 3
    va_pct: float = 0.93
    valley_rel: float = 0.15
    min_mountain_pct: float = 4.0
    va_zone_pct: float = 0.94
    lobe_fenster: int = 3
    lobe2_schwelle: float = 0.95
    vol_min: float = 0.0
    vol_quantil: float = 0.0


@dataclass(frozen=True, slots=True)
class KonsensParameter:
    """Parametersaetze zur Messung der POC-Unsicherheit.

    Der POC ist nicht der belastbare Punkt des Profils, sondern das Niveau-Band:
    er wandert mit Bin-Anzahl und Glaettung. Deshalb wird jedes Fensterprofil
    zusaetzlich mit mehreren ``(num_bins, smooth_win)``-Kombinationen gerechnet;
    die Spanne der POCs ist das direkte Unsicherheitsmass.

    Empirie (5 Symbole x 4 Monate x M15, 434 Tage): POC-Spanne median 0,73 ATR;
    von 32 Tagen mit > 2 ATR Verschiebung erfasst die Spanne bei Toleranz
    1,0 ATR alle 32, die reine Zweitgipfel-Ratio nur 19.

    Attributes:
        konsens_bins: Bin-Anzahlen der Konsensmessung (leer = Messung aus).
        konsens_smooth: Glaettungsfenster der Konsensmessung (leer = Messung aus).
        streu_toleranz_atr: Bis zu dieser POC-Spanne (in ATR) gilt der POC als
            eindeutig.
    """

    konsens_bins: Tuple[int, ...] = (30, 60, 120, 240)
    konsens_smooth: Tuple[int, ...] = (1, 3, 5, 9)
    streu_toleranz_atr: float = 1.0


@dataclass(slots=True)
class PocKonsens:
    """Ergebnis der POC-Streuungsmessung eines Fensters.

    Attributes:
        poc_min: Kleinster POC ueber die Konsens-Parametersaetze.
        poc_max: Groesster POC ueber die Konsens-Parametersaetze.
        streu_atr: Spanne ``poc_max - poc_min`` in ATR (nan = nicht messbar).
        eindeutig: True, wenn ``streu_atr <= streu_toleranz_atr``.
        n_saetze: Anzahl tatsaechlich gerechneter Parametersaetze.
    """

    poc_min: float = float("nan")
    poc_max: float = float("nan")
    streu_atr: float = float("nan")
    eindeutig: bool = False
    n_saetze: int = 0


# =============================================================================
# 2) DATENVERTRAEGE
# =============================================================================


@dataclass(slots=True)
class VolumeProfileData:
    """Rohes Volumenprofil eines Zeitraums (Baseline-Datenvertrag).

    Attributes:
        centers: Bin-Mitten in Preiseinheiten.
        edges: Bin-Kanten (Laenge ``num_bins + 1``).
        vol: Volumen je Bin.
        pmin: Tiefster Preis des Profils.
        pmax: Hoechster Preis des Profils.
    """

    centers: np.ndarray
    edges: np.ndarray
    vol: np.ndarray
    pmin: float
    pmax: float


@dataclass(slots=True)
class MountainPeak:
    """Ein Volumen-Berg ("Segment"/"Nest") mit eigener Value Area.

    Attributes:
        poc: Point of Control des Berges.
        val: Untere Kante der Berg-Value-Area.
        vah: Obere Kante der Berg-Value-Area.
        vol: Gesamtvolumen des Bergabschnitts.
        peak_share_pct: Gipfelvolumen relativ zum groessten Berg (Prozent).
        bin_start: Erster Bin des Berges.
        bin_gipfel: Gipfel-Bin.
        bin_ende: Letzter Bin des Berges.
    """

    poc: float
    val: float
    vah: float
    vol: float
    peak_share_pct: float
    bin_start: int = -1
    bin_gipfel: int = -1
    bin_ende: int = -1


@dataclass(slots=True)
class ValueArea:
    """Ergebnis einer Value-Area-Berechnung (Level + Abdeckung).

    Attributes:
        poc: Bezugs-POC.
        val: Untere Kante.
        vah: Obere Kante.
        abdeckung: Tatsaechlich erfasster Volumenanteil (0..1).
        bin_lo: Unterer Bin-Index.
        bin_hi: Oberer Bin-Index.
    """

    poc: float
    val: float
    vah: float
    abdeckung: float
    bin_lo: int
    bin_hi: int


@dataclass(slots=True)
class Segmentierung:
    """Vollstaendiges Ergebnis eines Profils (Berge + Zonen-Value-Area).

    Attributes:
        profile: Rohes Profil (Bins/Volumen/Raender).
        vol_glatt: Geglaettete Volumenreihe (Bezugsreihe aller Level).
        mountains: Berge mit ihren Gipfel-Bins.
        nester: Berge als ``MountainPeak`` (nach Volumen absteigend).
        zone: Zonen-Value-Area ab dem globalen POC (``va_zone_pct``).
        val_huelle: Untere Kante der Berg-Huelle (min der Berg-VALs).
        vah_huelle: Obere Kante der Berg-Huelle (max der Berg-VAHs).
        poc: Globaler POC (Gipfel des groessten Berges).
        lobe2_ratio: Zweitgipfel/Gipfel des Profils (nan = unbestimmt).
        lobe2_bin: Bin des Zweitgipfels (-1 = unbestimmt).
        n_bars_gefiltert: Anzahl Bars, die der Volumenfilter VOR dem
            Profilbau entfernt hat (0 = kein Filter aktiv/keine Wirkung).
    """

    profile: VolumeProfileData
    vol_glatt: np.ndarray
    mountains: List[Tuple[int, int, int]] = field(default_factory=list)
    nester: List[MountainPeak] = field(default_factory=list)
    zone: Optional[ValueArea] = None
    val_huelle: float = float("nan")
    vah_huelle: float = float("nan")
    poc: float = float("nan")
    lobe2_ratio: float = float("nan")
    lobe2_bin: int = -1
    n_bars_gefiltert: int = 0

    @property
    def n_segmente(self) -> int:
        """Anzahl erkannter Segmente (Berge)."""
        return len(self.nester)


@dataclass(slots=True)
class FensterProfil:
    """Ergebnis-Vertrag: EIN Zeitfenster -> EIN Volumenprofil.

    Verklammert die Fensteridentitaet (Label/Bar-Grenzen/Zeitstempel) mit dem
    Rechenergebnis (``Segmentierung`` + ``PocKonsens`` + ATR). Diesen Vertrag
    teilen Orchestrator, Speicher und Chart - er kennt selbst keine
    Fensterbildung und keine Persistenz.

    Attributes:
        label: Eindeutiges Fensterlabel (z. B. ``2026-08-03 04``).
        window_kind: Fensterart (``day``/``week``/``h12``/``h4``/...).
        bar_start: Erster Bar-Index im Fenster.
        bar_ende: Letzter Bar-Index im Fenster (inklusiv).
        ts_start: Erster BKZ-Zeitstempel.
        ts_ende: Letzter BKZ-Zeitstempel.
        n_bars: Anzahl Bars im Fenster.
        vol_summe: Summe des ``tick_volume`` im Fenster (ungefiltert).
        atr: Mittlere Bar-Spanne des Fensters.
        segmentierung: Vollstaendiges Profilergebnis (None = kein Profil).
        konsens: POC-Streuungsmessung ueber die Konsens-Parametersaetze.
    """

    label: str
    window_kind: str
    bar_start: int
    bar_ende: int
    ts_start: Any
    ts_ende: Any
    n_bars: int
    vol_summe: float = float("nan")
    atr: float = float("nan")
    segmentierung: Optional[Segmentierung] = None
    konsens: PocKonsens = field(default_factory=PocKonsens)

    @property
    def gueltig(self) -> bool:
        """True, wenn ein Profil mit mindestens einem Segment vorliegt."""
        return self.segmentierung is not None


# --- Hauptband --------------------------------------------------------------
# Es gibt nur EIN Hauptband (``zone``). Der fruehere Modus ``balance`` ist
# entfernt; seine Kennzahl (Deckung der Berg-Huelle) liefert
# ``huellen_abdeckung``. ``MODI`` bleibt als Tupel bestehen, damit ``band_von``
# weiterhin fail-loud gegen unbekannte Namen prueft.
MODI: Tuple[str, ...] = ("zone",)

_MODUS_NAME: Dict[str, str] = {
    "zone": "Zonen-VA (Anteil am Gesamtvolumen)",
}


@dataclass(frozen=True, slots=True)
class Band:
    """Das Hauptband eines Fensters (POC + untere/obere Kante + Abdeckung).

    ``zone`` ist der symmetrische Wertbereich ab dem globalen POC, der
    ``va_zone_pct`` (Default 0,94) des Gesamtvolumens erfasst. Er ist breiter
    als eine uebliche 70 %-Value-Area und trifft damit mehr Wendepunkte; die
    Nester selbst traegt die Separation (``Bereich`` je Segment).

    Attributes:
        poc: Point of Control des Fensters (Gipfel des groessten Segmentes).
        val: Untere Kante des Bandes.
        vah: Obere Kante des Bandes.
        abdeckung: Anteil des GESAMTVOLUMENS, der zwischen ``val`` und ``vah``
            liegt (0..1; nan, wenn nicht bestimmbar).
        modus: ``zone`` (einziges Hauptband).
        name: Lesbarer Name des Modus.
    """

    poc: float
    val: float
    vah: float
    abdeckung: float
    modus: str
    name: str

    @property
    def breite(self) -> float:
        """Breite des Bandes in Preiseinheiten (nan bei unbestimmtem Band)."""
        if not (np.isfinite(self.val) and np.isfinite(self.vah)):
            return float("nan")
        return float(self.vah - self.val)

    @property
    def abdeckung_name(self) -> str:
        """Benennung der Abdeckung (Report/Chart/Titel).

        Returns:
            ``"Band-Abdeckung (Anteil am Gesamtvolumen)"``.
        """
        return "Band-Abdeckung (Anteil am Gesamtvolumen)"


def huellen_abdeckung(seg: Optional[Segmentierung]) -> float:
    """Deckung der Berg-HUELLE im Rohprofil (Kern-Kennzahl, kein Modus).

    Die Huelle ist ``[min der Berg-VAL .. max der Berg-VAH]``. Zwischen den
    einzelnen Berg-Value-Areas liegen Luecken, die zu keinem Berg gehoeren und
    kein Volumen dieses Bandes tragen - die Deckung ist deshalb NICHT
    zusammenhaengend (typisch ~0,93-0,99) und NICHT vergleichbar mit der
    aufgesammelten Value Area des Hauptbandes.

    Die Kennzahl bleibt im Kern, weil sie die Bitgleichheit zum archivierten
    Tages-Balancen-Lauf traegt (``val_huelle``/``vah_huelle`` waren dessen
    Band). Sie ist ausdruecklich KEINE Auswertungsgroesse mehr.

    Args:
        seg: Profilergebnis; None = kein Profil.

    Returns:
        Anteil des Profilvolumens zwischen den Huellkanten (nan, wenn nicht
        bestimmbar).
    """
    if seg is None:
        return float("nan")
    val, vah = float(seg.val_huelle), float(seg.vah_huelle)
    prof = seg.profile
    if not (np.isfinite(val) and np.isfinite(vah)):
        return float("nan")
    gesamt = float(prof.vol.sum())
    if gesamt <= 0.0:
        return float("nan")
    drin = (prof.centers >= val) & (prof.centers <= vah)
    return float(prof.vol[drin].sum() / gesamt)


def band_von(seg: Optional[Segmentierung], modus: str = "zone") -> Band:
    """Liefert das Hauptband einer Segmentierung.

    Es gibt nur ein Hauptband (``zone``): die Zonen-Value-Area ab dem globalen
    POC. Der ``modus``-Parameter bleibt, damit ein unbekannter Name fail-loud
    scheitert (statt still ein falsches Band zu liefern).

    Args:
        seg: Profilergebnis; None = kein Profil (Rueckgabe bleibt nan).
        modus: ``zone`` (einziges Hauptband).

    Returns:
        ``Band`` mit POC/Kanten/Abdeckung; bei fehlendem Profil alle Kanten
        ``nan``.

    Raises:
        ValueError: Bei unbekanntem Modus.
    """
    if modus not in _MODUS_NAME:
        raise ValueError(f"Unbekannter Modus {modus!r}. Erlaubt: {sorted(MODI)}")
    nan = float("nan")
    if seg is None:
        return Band(nan, nan, nan, nan, modus, _MODUS_NAME[modus])
    z = seg.zone
    if z is None:
        return Band(seg.poc, nan, nan, nan, modus, _MODUS_NAME[modus])
    return Band(
        poc=float(z.poc), val=float(z.val), vah=float(z.vah),
        abdeckung=float(z.abdeckung), modus=modus, name=_MODUS_NAME[modus],
    )


# =============================================================================
# 3) VOLUMENFILTER
# =============================================================================


def filtere_volumen(
    sub: pd.DataFrame, vol_min: float = 0.0, vol_quantil: float = 0.0
) -> Tuple[pd.DataFrame, int]:
    """Filtert Bars anhand ihres ``tick_volume`` vor dem Profilbau.

    Es werden nur Bars ENTFERNT - die Reihenfolge der verbleibenden Bars bleibt
    erhalten, damit Bar-Indizes des Aufrufers weiter stimmen (der Aufrufer
    arbeitet mit den Zeilenindizes des Fensters).

    Args:
        sub: Bars des Fensters (Spalte ``tick_volume``).
        vol_min: Absolute Untergrenze des Bar-Volumens (0 = kein Filter).
        vol_quantil: Anteil der volumenaermsten Bars, der verworfen wird
            (0 = kein Filter; 0,05 = unterste 5 % des Fensters).

    Returns:
        ``(gefilterte_bars, n_entfernt)``. Bei leerem Ergebnis wird der
        ungefilterte Bestand zurueckgegeben (Schutz vor leerem Profil).
    """
    if sub.empty or (vol_min <= 0.0 and vol_quantil <= 0.0):
        return sub, 0
    vol = sub["tick_volume"].to_numpy(dtype=float)
    maske = np.ones(vol.size, dtype=bool)
    if vol_min > 0.0:
        maske &= vol >= vol_min
    if vol_quantil > 0.0:
        q = float(np.clip(vol_quantil, 0.0, 1.0))
        schwelle = float(np.quantile(vol, q))
        maske &= vol > schwelle
    if not maske.any():
        return sub, 0
    return sub.loc[maske], int((~maske).sum())


# =============================================================================
# 4) VOLUMEN-LOGIK (verbatim aus scripts/phasen_volumen_profil.py, Z. 478-608)
# =============================================================================


def build_volume_profile(
    sub: pd.DataFrame, num_bins: int = 60
) -> Optional[VolumeProfileData]:
    """Baut das Volumenprofil eines Zeitraums (Baseline Z. 478-507).

    Das ``tick_volume`` jeder Kerze wird anteilig auf die von ihrer Spanne
    ``[low, high]`` ueberdeckten Bins verteilt (Ueberdeckungsgewichtung, keine
    Gleichverteilung).

    Args:
        sub: OHLCV-Bars (Spalten ``low/high/tick_volume``).
        num_bins: Anzahl der Preis-Bins.

    Returns:
        ``VolumeProfileData`` oder ``None`` bei leerer/eindimensionaler Spanne.
    """
    if sub.empty:
        return None
    pmin = float(sub["low"].min())
    pmax = float(sub["high"].max())
    if pmax <= pmin:
        return None
    edges = np.linspace(pmin, pmax, num_bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(num_bins)

    lows = sub["low"].values.astype(float)
    highs = sub["high"].values.astype(float)
    vols = sub["tick_volume"].values.astype(float)
    for lo, hi, v in zip(lows, highs, vols):
        if hi <= lo or v <= 0:
            continue
        lo_b = int(
            np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, num_bins - 1)
        )
        hi_b = int(
            np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, num_bins - 1)
        )
        if lo_b == hi_b:
            vol[lo_b] += v
        else:
            ov = np.array(
                [
                    max(0.0, min(hi, edges[b + 1]) - max(lo, edges[b]))
                    for b in range(lo_b, hi_b + 1)
                ]
            )
            tot = ov.sum()
            if tot > 0:
                vol[lo_b : hi_b + 1] += v * ov / tot
    return VolumeProfileData(
        centers=centers, edges=edges, vol=vol, pmin=pmin, pmax=pmax
    )


def smooth_vol(vol: np.ndarray, win: int = 3) -> np.ndarray:
    """Glaettet die Volumenreihe mit einem gleitenden Mittel (Baseline Z. 510-513).

    Args:
        vol: Rohe Volumenreihe.
        win: Fensterbreite (<= 1 oder zu kurz = unveraendert).

    Returns:
        Geglaettete Reihe als float64-Array.
    """
    if win <= 1 or len(vol) < win:
        return vol.astype(float)
    return np.convolve(vol, np.ones(win) / win, mode="same")


def find_mountains(
    vol_s: np.ndarray,
    min_pct: float = 4.0,
    valley_rel: float = 0.15,
) -> List[Tuple[int, int, int]]:
    """Zerlegt das geglaettete Profil in Volumen-Berge (Baseline Z. 516-545).

    Ein Berg ist ein zusammenhaengender Abschnitt zwischen zwei Taelern; als
    Talschwelle dient ``valley_rel`` relativ zum kleineren der beiden
    angrenzenden Gipfel. Berge unter ``min_pct`` des groessten Berges werden
    verworfen. Rueckgabe absteigend nach Gipfel-Volumen.

    Args:
        vol_s: Geglaettete Volumenreihe.
        min_pct: Mindestanteil am groessten Berg (Prozent).
        valley_rel: Relativer Tal-Schwellwert.

    Returns:
        Liste ``(start_bin, gipfel_bin, ende_bin)``, absteigend nach Volumen.
    """
    n = len(vol_s)
    if n < 3:
        return []
    mountains: List[Tuple[int, int, int]] = []
    start = 0
    for i in range(1, n - 1):
        if vol_s[i] <= vol_s[i - 1] and vol_s[i] < vol_s[i + 1]:
            left_peak = float(np.max(vol_s[start : i + 1]))
            right_peak = float(np.max(vol_s[i:n]))
            threshold = min(left_peak, right_peak) * valley_rel
            if vol_s[i] < threshold:
                p_idx = start + int(np.argmax(vol_s[start : i + 1]))
                if vol_s[start : i + 1].max() > 0:
                    mountains.append((start, p_idx, i))
                start = i
    p_idx = start + int(np.argmax(vol_s[start:n]))
    if vol_s[start:n].max() > 0:
        mountains.append((start, p_idx, n - 1))

    if not mountains:
        return []
    max_vol = max(vol_s[p] for _, p, _ in mountains)
    mountains = [m for m in mountains if vol_s[m[1]] >= max_vol * min_pct / 100.0]
    mountains.sort(key=lambda m: -vol_s[m[1]])
    return mountains


def va_for_mountain(
    vol_s: np.ndarray,
    edges: np.ndarray,
    mountain: Tuple[int, int, int],
    dominant_peak: Optional[int],
    va_pct: float = 0.93,
) -> MountainPeak:
    """Value Area eines Berges (Baseline Z. 548-581).

    Vom Gipfel nach aussen wird jeweils die groessere Nachbarseite
    aufgenommen, bis ``va_pct`` des Berg-Volumens erreicht ist.

    Args:
        vol_s: Geglaettete Volumenreihe.
        edges: Bin-Kanten des Profils.
        mountain: ``(start_bin, gipfel_bin, ende_bin)``.
        dominant_peak: Gipfel-Bin des groessten Berges (fuer ``peak_share_pct``).
        va_pct: Value-Area-Anteil des Bergvolumens.

    Returns:
        ``MountainPeak`` mit POC/VAL/VAH in Preis-Einheiten.
    """
    s, p, e = mountain
    poc = float((edges[p] + edges[p + 1]) / 2)
    total = float(vol_s[s : e + 1].sum())
    target = total * va_pct
    lo, hi = p, p
    acc = float(vol_s[p])
    while acc < target and (lo > s or hi < e):
        down = float(vol_s[lo - 1]) if lo > s else -1.0
        up = float(vol_s[hi + 1]) if hi < e else -1.0
        if down >= up and down >= 0:
            lo -= 1
            acc += down
        elif up >= 0:
            hi += 1
            acc += up
        else:
            break
    share = 100.0
    if dominant_peak is not None and vol_s[dominant_peak] > 0:
        share = float(vol_s[p] / vol_s[dominant_peak] * 100.0)
    return MountainPeak(
        poc=poc,
        val=float(edges[lo]),
        vah=float(edges[hi + 1]),
        vol=total,
        peak_share_pct=share,
        bin_start=s,
        bin_gipfel=p,
        bin_ende=e,
    )


# =============================================================================
# 5) ZUSATZ: ZONEN-VALUE-AREA AB POC (94 %) UND ZWEIGIPFEL-DIAGNOSE
# =============================================================================


def va_von_poc(
    vol_s: np.ndarray,
    edges: np.ndarray,
    poc_bin: int,
    va_pct: float = 0.94,
) -> ValueArea:
    """Value Area ab einem POC ueber das GESAMTE Profil (Zonen-Klammer).

    Ausgehend vom POC-Bin wird der Bereich schrittweise nach aussen erweitert.
    Bei jedem Schritt wird die Seite aufgenommen, deren Nachbarbin das groessere
    Volumen traegt, bis ``va_pct`` des Gesamtvolumens erfasst sind.

    Diese Berechnung ist bewusst NICHT identisch mit ``va_for_mountain``:
    dort gilt der Anteil nur fuer das Volumen EINES Berges, hier fuer das
    Volumen des ganzen Profils. Ein hoeherer Anteil (0,94 statt der ueblichen
    0,70) ergibt ein breiteres Band und trifft damit mehr Wendepunkte.

    Args:
        vol_s: Geglaettete Volumenreihe.
        edges: Bin-Kanten des Profils.
        poc_bin: Bin-Index des Bezugs-POC.
        va_pct: Anteil des Gesamtvolumens (0,94 = breite Zonen-Klammer).

    Returns:
        ``ValueArea`` mit POC/VAL/VAH, tatsaechlicher Abdeckung und Bin-Grenzen.
    """
    n: int = int(vol_s.size)
    if n == 0 or not 0 <= poc_bin < n:
        return ValueArea(float("nan"), float("nan"), float("nan"), 0.0, -1, -1)
    gesamt: float = float(vol_s.sum())
    if gesamt <= 0.0:
        return ValueArea(float("nan"), float("nan"), float("nan"), 0.0, -1, -1)
    pct = float(np.clip(va_pct, 0.0, 1.0))
    ziel: float = gesamt * pct
    lo = hi = int(poc_bin)
    acc: float = float(vol_s[lo])
    while acc < ziel and (lo > 0 or hi < n - 1):
        down = float(vol_s[lo - 1]) if lo > 0 else -1.0
        up = float(vol_s[hi + 1]) if hi < n - 1 else -1.0
        if down >= up and down >= 0.0:
            lo -= 1
            acc += down
        elif up >= 0.0:
            hi += 1
            acc += up
        else:
            break
    poc = float((edges[int(poc_bin)] + edges[int(poc_bin) + 1]) / 2)
    return ValueArea(
        poc=poc,
        val=float(edges[lo]),
        vah=float(edges[hi + 1]),
        abdeckung=float(acc / gesamt),
        bin_lo=int(lo),
        bin_hi=int(hi),
    )


def zweitgipfel(vol_s: np.ndarray, fenster: int) -> Tuple[float, int]:
    """Sucht den zweitgroessten Gipfel ausserhalb eines Fensters um den Gipfel.

    Die Profile sind empirisch zweilappig (Median Zweitgipfel/Gipfel = 0,81
    ueber 434 Tag/Symbol/Monat-Zellen, M15). Liegen beide Lappen praktisch
    gleichauf, ist der POC ein Muenzwurf der Aufloesung: bei Ratio >= 0,95
    kippt er an 77,8 % der Tage, bei < 0,85 nur an 4,8 %.

    Args:
        vol_s: Geglaettete Volumenreihe.
        fenster: Anzahl Bins links/rechts des Gipfels, die ausgeblendet werden
            (verhindert, dass die Schulter des eigenen Gipfels zaehlt).

    Returns:
        ``(ratio, bin_index)`` mit ``ratio = Zweitgipfel/Gipfel``; bei zu
        kurzer Reihe oder Gipfelvolumen 0 ``(nan, -1)``.
    """
    n: int = int(vol_s.size)
    if n < 3 * max(1, fenster):
        return float("nan"), -1
    p: int = int(np.argmax(vol_s))
    gipfel: float = float(vol_s[p])
    if gipfel <= 0.0:
        return float("nan"), -1
    maske = np.ones(n, dtype=bool)
    maske[max(0, p - fenster) : p + fenster + 1] = False
    if not maske.any():
        return float("nan"), -1
    indizes = np.flatnonzero(maske)
    b: int = int(indizes[np.argmax(vol_s[maske])])
    return float(vol_s[b] / gipfel), b


# =============================================================================
# 6) SEPARATION: EIGENER BEREICH JE SEGMENT + LUECKE DAZWISCHEN
# =============================================================================
#
# Das Hauptband (``zone``) ist EIN zusammenhaengender Preisbereich. Damit
# verschwindet die Trennung zwischen den Volumen-Nestern: der Bereich ist meist
# breiter als der Move, den er beschreiben soll.
#
# Deshalb wird hier zusaetzlich ZERLEGT (nichts wird neu gerechnet): jedes
# Segment traegt seinen EIGENEN Bereich ``[VAL .. VAH]``, und was zwischen zwei
# Bereichen liegt, gehoert zu keinem Segment (``Luecke``) - dort laufen die
# schnellen Moves. Die Luecken sind damit nicht mehr "im Band versteckt",
# sondern ausgewiesen.


@dataclass(frozen=True, slots=True)
class Bereich:
    """Der eigene Preisbereich EINES Segmentes (seine Value Area).

    Attributes:
        rank: Rang des Segmentes im Fenster (0 = groesstes).
        poc: Point of Control des Segmentes.
        val: Untere Kante des Bereiches.
        vah: Obere Kante des Bereiches.
        vol: Volumen des Segmentabschnitts (Bins des Berges).
        breite: Breite ``vah - val`` in Preiseinheiten.
        breite_atr: Breite in ATR (nan, wenn keine ATR vorliegt).
    """

    rank: int
    poc: float
    val: float
    vah: float
    vol: float
    breite: float
    breite_atr: float


@dataclass(frozen=True, slots=True)
class Luecke:
    """Preisbereich zwischen ZWEI benachbarten Bereichen (der schnelle Move).

    Die Luecke traegt kein Volumen EINES Segmentes - sie ist die Distanz, die
    der Preis zwischen zwei Nestern zuruecklegt. ``unten``/``oben`` sind die
    zugewandten Kanten der beiden Bereiche.

    Attributes:
        rank_unten: Rang des unteren Bereiches.
        rank_oben: Rang des oberen Bereiches.
        unten: Obere Kante des unteren Bereiches (dessen VAH).
        oben: Untere Kante des oberen Bereiches (dessen VAL).
        breite: ``oben - unten`` in Preiseinheiten (<= 0 = Bereiche beruehren
            sich oder ueberlappen sich um den gemeinsamen Rand-Bin).
        breite_atr: Breite in ATR (nan, wenn keine ATR vorliegt).
    """

    rank_unten: int
    rank_oben: int
    unten: float
    oben: float
    breite: float
    breite_atr: float

    @property
    def ueberlappung(self) -> bool:
        """True, wenn sich die beiden Bereiche beruehren/ueberlappen (breite<=0).

        Returns:
            True bei ``breite <= 0``.
        """
        return self.breite <= 0.0


@dataclass(frozen=True, slots=True)
class Separierung:
    """Zerlegung eines Fensters in getrennte Bereiche samt Luecken.

    ``anteil_ausserhalb`` ist das direkte Mass der Isolation: der Anteil des
    PROFILVOLUMENS, der ausserhalb ALLER Segment-Value-Areas liegt. Das umfasst
    BEIDES - die Zwischenraeume zwischen zwei Bereichen (dort laufen die
    schnellen Moves) UND die Flanken der Berge, die die Value Area nicht mehr
    erfasst (``1 - va_pct`` je Berg). Ein hoher Wert heisst: das Fenster besteht
    ueberwiegend aus Strecke zwischen den Bereichen; ein Wert nahe 0 heisst:
    die Bereiche decken das Profil praktisch lueckenlos ab.

    Attributes:
        bereiche: Bereiche in Rangfolge (0 = groesstes); die Luecken werden
            ueber die nach Preis sortierte Kopie gebildet.
        luecken: Luecken zwischen je zwei benachbarten Bereichen (n-1 Stueck).
        atr: Bar-Spanne des Fensters, auf die sich alle ATR-Werte beziehen.
        vol_gesamt: Gesamtvolumen des Rohlprofils (Bezugsgroesse der Anteile).
        vol_in_bereichen: Volumen der Bins, die in MINDESTENS einem Bereich
            liegen (Schnittmenge wird nicht doppelt gezaehlt).
    """

    bereiche: Tuple[Bereich, ...] = ()
    luecken: Tuple[Luecke, ...] = ()
    atr: float = float("nan")
    vol_gesamt: float = float("nan")
    vol_in_bereichen: float = float("nan")

    @property
    def n_bereiche(self) -> int:
        """Anzahl getrennter Bereiche (Segmente)."""
        return len(self.bereiche)

    @property
    def n_luecken(self) -> int:
        """Anzahl Luecken (Bereiche - 1, mindestens 0)."""
        return len(self.luecken)

    @property
    def anteil_bereiche(self) -> float:
        """Anteil des Profilvolumens, der in den Bereichen liegt (0..1)."""
        if not np.isfinite(self.vol_gesamt) or self.vol_gesamt <= 0.0:
            return float("nan")
        return float(self.vol_in_bereichen / self.vol_gesamt)

    @property
    def anteil_ausserhalb(self) -> float:
        """Anteil des Profilvolumens ausserhalb ALLER Bereiche (0..1).

        Enthaelt die Zwischenraeume (schnelle Moves zwischen den Nestern) UND
        die Bergflanken ausserhalb der jeweiligen Value Area.
        """
        a = self.anteil_bereiche
        if not np.isfinite(a):
            return float("nan")
        return float(max(0.0, 1.0 - a))

    @property
    def breite_bereiche_atr(self) -> float:
        """Summe der Bereichsbreiten in ATR (nan, wenn keine ATR vorliegt)."""
        if not np.isfinite(self.atr) or self.atr <= 0.0:
            return float("nan")
        return float(sum(b.breite for b in self.bereiche) / self.atr)

    @property
    def breite_luecken_atr(self) -> float:
        """Summe der Lueckenbreiten in ATR (nan, wenn keine ATR vorliegt).

        Ueberlappende Bereiche (breite <= 0) gehen mit 0 ein - die Summe ist
        damit die tatsaechlich freie Strecke zwischen den Bereichen.
        """
        if not np.isfinite(self.atr) or self.atr <= 0.0:
            return float("nan")
        return float(sum(max(0.0, l.breite) for l in self.luecken) / self.atr)


def zerlege_bereiche(
    seg: Optional[Segmentierung], atr: float = float("nan")
) -> Separierung:
    """Zerlegt eine Segmentierung in getrennte Bereiche und Luecken.

    Es wird NICHTS neu gerechnet: die Bereiche sind die Value Areas der bereits
    erkannten Segmente (``nester``), die Luecken deren Zwischenraeume. Die
    Sortierung erfolgt nach Preis (aufsteigend), damit die Zwischenraeume
    benachbarter Bereiche eindeutig sind - der Rang des Segmentes bleibt im
    Bereich erhalten.

    Args:
        seg: Profilergebnis; None = kein Profil (Rueckgabe bleibt leer).
        atr: Bar-Spanne des Fensters; nan = keine ATR-Bezugsgroesse.

    Returns:
        ``Separierung`` mit Bereichen, Luecken und Volumenanteilen.
    """
    if seg is None or not seg.nester:
        return Separierung()
    prof = seg.profile
    vol_gesamt = float(prof.vol.sum())
    a = float(atr) if atr is not None else float("nan")
    fa = a if (np.isfinite(a) and a > 0.0) else float("nan")

    bereiche: List[Bereich] = [
        Bereich(
            rank=i,
            poc=float(nest.poc),
            val=float(nest.val),
            vah=float(nest.vah),
            vol=float(nest.vol),
            breite=float(nest.vah - nest.val),
            breite_atr=float((nest.vah - nest.val) / fa)
            if np.isfinite(fa) else float("nan"),
        )
        for i, nest in enumerate(seg.nester)
    ]
    nach_preis: List[Bereich] = sorted(
        bereiche, key=lambda b: (b.val, b.vah, b.rank)
    )

    luecken: List[Luecke] = []
    for unten_b, oben_b in zip(nach_preis[:-1], nach_preis[1:]):
        breite = float(oben_b.val - unten_b.vah)
        luecken.append(
            Luecke(
                rank_unten=int(unten_b.rank),
                rank_oben=int(oben_b.rank),
                unten=float(unten_b.vah),
                oben=float(oben_b.val),
                breite=breite,
                breite_atr=float(breite / fa) if np.isfinite(fa) else float("nan"),
            )
        )

    # Volumen in den Bereichen: Bins, die in mindestens EINEM Bereich liegen
    # (Schnittmengen zaehlen nur einmal - der Anteil bleibt damit ehrlich).
    drin = np.zeros(prof.centers.size, dtype=bool)
    for b in bereiche:
        drin |= (prof.centers >= b.val) & (prof.centers <= b.vah)
    vol_drin = float(prof.vol[drin].sum()) if prof.vol.size else 0.0

    return Separierung(
        bereiche=tuple(bereiche),
        luecken=tuple(luecken),
        atr=a,
        vol_gesamt=vol_gesamt,
        vol_in_bereichen=vol_drin,
    )


# =============================================================================
# 7) ZUSAMMENFASSUNG: EIN PROFIL -> ALLE LEVEL
# =============================================================================


def compute_segmentierung(
    sub: pd.DataFrame,
    par: ProfilParameter,
    mit_volumenfilter: bool = True,
) -> Optional[Segmentierung]:
    """Rechnet aus den Bars eines Fensters die Segmente und die Zonen-VA.

    Reihenfolge: Volumenfilter -> Profil -> Glaettung -> Bergzerlegung
    (Segmente) -> Berg-Value-Areas (Anteil je Berg) -> Zonen-Value-Area ab
    globalem POC (Anteil am Gesamtvolumen).

    Args:
        sub: OHLCV-Bars eines Fensters (Spalten ``low/high/tick_volume``).
        par: Volumenparameter (Bins, Glaettung, Anteile, Filter).
        mit_volumenfilter: False = Filter aus (fuer den Baseline-Vergleich).

    Returns:
        ``Segmentierung`` oder ``None``, wenn kein Profil/Berg entsteht.
    """
    bars = sub
    n_gefiltert: int = 0
    if mit_volumenfilter:
        bars, n_gefiltert = filtere_volumen(sub, par.vol_min, par.vol_quantil)
    prof = build_volume_profile(bars, par.num_bins)
    if prof is None:
        return None
    vol_s = smooth_vol(prof.vol, par.smooth_win)
    mountains = find_mountains(vol_s, par.min_mountain_pct, par.valley_rel)
    if not mountains:
        return None
    dominant_peak = mountains[0][1]
    nester: List[MountainPeak] = [
        va_for_mountain(vol_s, prof.edges, m, dominant_peak, par.va_pct)
        for m in mountains
    ]
    # Zonen-Klammer (94 %) ab dem globalen POC
    zone = va_von_poc(vol_s, prof.edges, dominant_peak, par.va_zone_pct)
    lobe2_ratio, lobe2_bin = zweitgipfel(vol_s, par.lobe_fenster)
    return Segmentierung(
        profile=prof,
        vol_glatt=vol_s,
        mountains=mountains,
        nester=nester,
        zone=zone,
        val_huelle=min(p.val for p in nester),
        vah_huelle=max(p.vah for p in nester),
        poc=nester[0].poc,
        lobe2_ratio=lobe2_ratio,
        lobe2_bin=lobe2_bin,
        n_bars_gefiltert=int(n_gefiltert),
    )


def mit_parameter(par: ProfilParameter, **overrides: object) -> ProfilParameter:
    """Erzeugt eine Parameterkopie mit ueberschriebenen Feldern.

    Args:
        par: Ausgangsparameter.
        **overrides: Zu ersetzende Felder.

    Returns:
        Neue ``ProfilParameter``-Instanz.
    """
    from dataclasses import replace

    return replace(par, **overrides)  # type: ignore[arg-type]


# =============================================================================
# 8) POC-UNSICHERHEIT (Konsens ueber Parametersaetze) UND FENSTER-KENNZAHLEN
# =============================================================================


def atr_einfach(sub: pd.DataFrame) -> float:
    """Mittlere Bar-Spanne ``high - low`` eines Fensters.

    Args:
        sub: Bars (Spalten ``high``/``low``).

    Returns:
        Mittlere Spanne; ``nan`` bei leerem Input.
    """
    if sub.empty:
        return float("nan")
    return float(
        np.mean(
            sub["high"].to_numpy(dtype=float) - sub["low"].to_numpy(dtype=float)
        )
    )


def poc_konsens(
    sub: pd.DataFrame,
    par: ProfilParameter,
    kons: KonsensParameter,
    atr: Optional[float] = None,
) -> PocKonsens:
    """Misst die POC-Spanne eines Fensters ueber mehrere Parametersaetze.

    Das Fensterprofil wird je ``(num_bins, smooth_win)``-Kombination der
    Konsensparameter erneut gerechnet; die Referenzwerte ``par.num_bins`` /
    ``par.smooth_win`` sind immer enthalten, damit der gemeldete POC im Band
    liegt. ``streu_atr = (poc_max - poc_min) / atr`` ist das direkte Mass der
    POC-Unsicherheit; ``eindeutig`` vergleicht es mit der Toleranz.

    Args:
        sub: Bars des Fensters (OHLCV).
        par: Referenz-Volumenparameter (Bins/Glaettung/VALogik/Filter).
        kons: Konsensparameter (Bins/Smooth-Saetze, Toleranz).
        atr: Bar-Spanne des Fensters; None = selbst aus ``sub`` rechnen.

    Returns:
        ``PocKonsens``. Bei deaktivierter Messung (leere Saetze), fehlendem
        Profil oder ``atr <= 0`` bleiben die Werte ``nan`` und
        ``eindeutig = False``.
    """
    if not kons.konsens_bins or not kons.konsens_smooth:
        return PocKonsens()
    a: float = float(atr) if atr is not None else atr_einfach(sub)
    kombis = {
        (int(b), int(s)) for b in kons.konsens_bins for s in kons.konsens_smooth
    }
    kombis.add((int(par.num_bins), int(par.smooth_win)))
    pocs: List[float] = []
    for b, s in sorted(kombis):
        seg = compute_segmentierung(sub, mit_parameter(par, num_bins=b, smooth_win=s))
        if seg is not None and np.isfinite(seg.poc):
            pocs.append(float(seg.poc))
    if not pocs:
        return PocKonsens()
    p_min = float(min(pocs))
    p_max = float(max(pocs))
    streu = float("nan")
    if np.isfinite(a) and a > 0.0:
        streu = float((p_max - p_min) / a)
    eindeutig = bool(np.isfinite(streu) and streu <= kons.streu_toleranz_atr)
    return PocKonsens(
        poc_min=p_min, poc_max=p_max, streu_atr=streu, eindeutig=eindeutig,
        n_saetze=len(pocs),
    )


def profil_mit_kennzahlen(
    sub: pd.DataFrame,
    par: ProfilParameter,
    kons: Optional[KonsensParameter] = None,
) -> Tuple[Optional[Segmentierung], PocKonsens, float]:
    """Rechnet Segmentierung, POC-Konsens und ATR eines Fensters zusammen.

    Args:
        sub: Bars des Fensters (OHLCV).
        par: Volumenparameter.
        kons: Konsensparameter; None = Konsensmessung aus.

    Returns:
        ``(segmentierung, konsens, atr)``. ``segmentierung`` ist ``None``, wenn
        kein Profil entsteht; ``konsens`` bleibt dann leer.
    """
    atr = atr_einfach(sub)
    seg = compute_segmentierung(sub, par)
    k = poc_konsens(sub, par, kons, atr) if (kons and seg is not None) else PocKonsens()
    return seg, k, atr
