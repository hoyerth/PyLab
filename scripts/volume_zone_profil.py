"""
VOLUME ZONE - TAGES-BALANCEN (scripts/volume_zone_profil.py)
==============================================================
Findet und zeigt Volumen-Balancen ("Nester") auf Tagesbasis: je
Broker-Kerzen-Zeit-Kalendertag wird ein Volumenprofil gerechnet und daraus
Point of Control (POC), Value Area High (VAH) und Value Area Low (VAL)
abgeleitet.

    Balance  = Tages-Zone  [VAL_gesamt .. VAH_gesamt] ueber alle Nester
    Nest     = einzelner Volumen-Berg (MountainPeak) mit eigenem POC/VAL/VAH

Die Volumen-Logik ist aus der eingefrorenen Produktions-Baseline
``scripts/phasen_volumen_profil.py`` (v0.4.0-baseline-frozen) HERUEBERKOPIERT
und auf einen eigenstaendigen, voll parametrisierten Ablauf angepasst:
``build_volume_profile`` / ``smooth_vol`` / ``find_mountains`` /
``va_for_mountain`` / ``compute_volume_zone`` rechnen unveraendert (identische
Algorithmik und Defaults: NUM_BINS 60, SMOOTH_WIN 3, VA_PCT 0,93,
VALLEY_REL 0,15, MIN_MOUNTAIN_PCT 4,0). Die Baseline selbst bleibt
byte-identisch unberuehrt.

Abgrenzung
----------
Einzige Aufgabe: **Volumenprofile sicher erkennen und darstellen**. Es wird
NICHT gehandelt, kein Signal erzeugt, keine Strategie simuliert und keine
Sprung-/Fortsetzungsstatistik gerechnet. Ausgegeben werden die Level
(POC/VAL/VAH je Balance und je Nest) und die Sichtpruefung der Profile.

Erkennungs-Sicherheit
---------------------
Ein Tagesprofil entsteht an JEDEM Handelstag des Fensters (100 % Trefferquote
ueber 5 Symbole x 4 Monate x M15, 434 Tage). Belastbar ist aber nicht der
Punkt POC, sondern das Niveau-Band: der POC wandert je nach Bin-Anzahl und
Glaettung. Gemessen, indem das Tagesprofil ueber die ``konsens_*``-Saetze
mehrfach gerechnet und die POC-Spanne (``poc_streu_atr``) gebildet wird:

    POC-Spanne median 0,73 ATR; > 1 ATR an 31 % der Tage
    Tage mit > 2 ATR POC-Verschiebung: 32 von 434 (7,4 %)

Ein Vergleich der Erkennungskriterien gegen einen disjunkten Pruefsatz
(bins 45/90/180/360 x smooth 2/4/7) zeigt, dass die Spanne das direkte Mass
ist und besser trifft als ein Struktur-Proxy:

    Kriterium                     erkennt von 32 Flips > 2 ATR   Fehlalarme
    Zweitgipfel/Gipfel >= 0,95    19   (59 %)                     39
    POC-Spanne > 0,5 ATR          32   (100 %)                   283
    POC-Spanne > 1,0 ATR          32   (100 %)                   102

Deshalb ist ``poc_eindeutig`` ueber ``streu_toleranz_atr`` definiert; die
Zwei-Lappen-Ratio (``lobe2``) bleibt als Ursachen-Diagnose im Report, und die
Tagesprofile sind zusaetzlich zweilappig: Median Zweitgipfel/Gipfel 0,81.
Im Chart/Profil-Grid wird die Unsicherheit als Band gezeichnet. Die
Baseline-Algorithmik selbst bleibt unangetastet.

Zeitbasis (docs/ZEITBASIS_KANON.md, verbindlich)
------------------------------------------------
Ausschliesslich BKZ = ``time AT TIME ZONE 'UTC'`` (K1). Die Tagesgrenzen
werden dynamisch per ``searchsorted`` auf der BKZ-Achse abgeleitet (K6),
niemals als Bar-Konstante hartcodiert. Es gibt keine Projektion auf
``Europe/Berlin``/``Europe/Budapest`` (K2); der Begriff "Wanduhr" ist
projektweit verboten (K3). Nacktes ``SELECT time`` kommt nicht vor (K4) -
das Einlesen laeuft ueber ``scripts.market_segmentation.load_data``
(BKZ-Garantie, sowie Symbol-/Timeframe-Validierung).

Aufruf (Projekt-Root, Namespace-Package):
    python -m scripts.volume_zone_profil
    python -m scripts.volume_zone_profil --symbol=Brent --timeframe=M15 ^
        --start=2026-05-01 --ende=2026-06-01

Ausgabe (nach ``test/VolumeZone/reports/``):
    volume_zone_<SYMBOL>_<TF>_<start>_<ende>.png          Zonen-Chart (POC/VAH/VAL)
    volume_zone_<SYMBOL>_<TF>_<start>_<ende>_profile.png  Tagesprofil-Grid
    volume_zone_<SYMBOL>_<TF>_<start>_<ende>.txt          Report (Tages-Tabelle)
    volume_zone_<SYMBOL>_<TF>_<start>_<ende>_levels.tsv   maschinenlesbar

Alle Parameter sind als Defaults am Klassenkopf von ``VolumeZoneConfig``
vorbelegt und koennen per CLI ueberschrieben werden.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

# Direktaufruf (``python scripts/volume_zone_profil.py``) legt nur ``scripts/``
# auf den Modulpfad -> der Namespace-Import ``scripts.*`` scheitert. Der Guard
# stellt die Projekt-Wurzel voran und macht BEIDE Aufrufarten gueltig; beim
# ``-m``-Aufruf ist ``__package__`` gesetzt und der Guard ist inaktiv.
if __package__ in (None, ""):
    _projekt_root: Path = Path(__file__).resolve().parent.parent
    if str(_projekt_root) not in sys.path:
        sys.path.insert(0, str(_projekt_root))

from scripts.market_segmentation import load_data  # noqa: E402
from scripts.volume_profile_core import (  # noqa: E402
    MountainPeak,
    ProfilParameter,
    VolumeProfileData,
    build_volume_profile,
    compute_segmentierung,
    find_mountains,
    smooth_vol,
    va_for_mountain,
    zweitgipfel,
)
from scripts.volume_profile_windows import (  # noqa: E402
    FensterSpec,
    baue_fenster,
    min_bars_fuer,
)


# =============================================================================
# 1) KONFIGURATION (alle Parameter mit Defaults, direkt am Dateianfang)
# =============================================================================


@dataclass(frozen=True, slots=True)
class VolumeZoneConfig:
    """Vollstaendige Parametrisierung des Volume-Zone-Laufs.

    Alle Felder sind mit Defaults vorbelegt; der Ablauf ist damit ohne jedes
    Argument lauffaehig. Ueberschrieben wird ueber die CLI (siehe ``main``).

    Die Volumen-Parameter entsprechen 1:1 den Modul-Konstanten der
    eingefrorenen Baseline (``phasen_volumen_profil.py`` Z. 216-220) und
    duerfen nur als dokumentierte Sensitivitaet geaendert werden.

    Attributes:
        symbol: DB-Symbol (Default ``SILVER``).
        timeframe: Kerzen-Timeframe (Default ``M15``).
        start: Fenster-Start als ISO-Datum, inklusive (BKZ).
        ende: Fenster-Ende als ISO-Datum, exklusiv (BKZ).
        db_path: DuckDB-Datei (Default = zentrale Produktions-DB).
        num_bins: Anzahl Preis-Bins des Volumenprofils (Baseline ``NUM_BINS``).
        smooth_win: Glaettungsfenster des Volumens (Baseline ``SMOOTH_WIN``).
        va_pct: Value-Area-Anteil des Berg-Volumens (Baseline ``VA_PCT``).
        valley_rel: Relativer Tal-Schwellwert zur Berg-Trennung
            (Baseline ``VALLEY_REL``).
        min_mountain_pct: Mindest-Volumenanteil eines Berges am groessten
            Berg in Prozent (Baseline ``MIN_MOUNTAIN_PCT``).
        min_bars_pro_tag: Mindestzahl Bars, damit ein Kalendertag als
            auswertbare Balance gilt (kurze/randstaendige Tage werden
            verworfen, nicht interpoliert). ``None`` (Default) = ABLEITEN aus
            Fensterart (``day``) und Timeframe ueber
            ``volume_profile_windows.min_bars_fuer`` - damit wird auf jedem
            Timeframe dieselbe Groesse untersucht (M15 -> 48 Bars,
            H1 -> 12 Bars) statt einer festen Bar-Anzahl.
        lobe_fenster: Bins links/rechts des Gipfels, die bei der Suche nach
            dem Zweitgipfel ausgeblendet werden (Zwei-Lappen-Diagnose).
        lobe2_schwelle: Ab dieser Zweitgipfel-Ratio (Zweitgipfel/Gipfel) gilt
            der Tag als strukturell zweilappig. Reine Diagnose/Erklaerung -
            der POC-Status (``poc_eindeutig``) wird aus der Streuung bestimmt.
        konsens_bins: Bin-Anzahlen fuer die Streuungsmessung. Je Kombination
            mit ``konsens_smooth`` wird das Tagesprofil erneut gerechnet; die
            Spanne der POCs ist das Unsicherheitsmass. Die Referenzwerte
            ``num_bins``/``smooth_win`` werden immer mitgerechnet. Ein leeres
            Tupel schaltet die Konsensrechnung ab (Streuung = 0).
        konsens_smooth: Glaettungsfenster fuer die Streuungsmessung.
        streu_toleranz_atr: Bis zu dieser POC-Spanne (in ATR) gilt der POC als
            eindeutig. Empirie (5 Symbole x 4 Monate x M15, 434 Tage): die
            Streuung ist im Median 0,73 ATR; von 32 Tagen mit >2 ATR
            POC-Verschiebung erkennt die Spanne bei Toleranz 1,0 ATR alle 32,
            der reine Zweitgipfel-Proxy (``lobe2``) nur 19.
        dpi: Aufloesung der PNG-Ausgabe.
        chart_limit_tage: Nur die letzten N Tage zeichnen (0 = alle).
        grid_max_tage: Obergrenze fuer die Anzahl der Tagesprofile im
            Profil-Grid (0 = alle). Verhindert uebergrosse PNGs bei langen
            Fenstern; es werden die letzten N Tage gezeigt.
        report_dir: Ausgabeordner (Default ``test/VolumeZone/reports``).
    """

    # --- Datenzugriff -------------------------------------------------------
    symbol: str = "SILVER"
    timeframe: str = "M15"
    start: str = "2026-08-01"
    ende: str = "2026-09-01"
    db_path: Path = (
        Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
    )

    # --- Volumenprofil (Baseline-Defaults, unveraendert) --------------------
    num_bins: int = 60
    smooth_win: int = 3
    va_pct: float = 0.93
    valley_rel: float = 0.15
    min_mountain_pct: float = 4.0

    # --- Tages-Segmentierung ------------------------------------------------
    min_bars_pro_tag: Optional[int] = None

    # --- POC-Eindeutigkeit (Zusatz-Kennzahl; die Baseline-Algorithmik der
    #     Volumenfunktionen bleibt unveraendert, hier wird nur gemessen) -----
    lobe_fenster: int = 3
    lobe2_schwelle: float = 0.95
    konsens_bins: Tuple[int, ...] = (30, 60, 120, 240)
    konsens_smooth: Tuple[int, ...] = (1, 3, 5, 9)
    streu_toleranz_atr: float = 1.0

    # --- Ausgabe ------------------------------------------------------------
    dpi: int = 300
    chart_limit_tage: int = 0
    grid_max_tage: int = 24
    report_dir: Path = (
        Path(__file__).resolve().parent.parent / "test" / "VolumeZone" / "reports"
    )


# =============================================================================
# 2) DATENVERTRAEGE (aus der Baseline herueberkopiert)
# =============================================================================


@dataclass(slots=True)
class VolumeZone:
    """Volumen-Zone eines Zeitraums (Baseline-Vertrag)."""

    profile: VolumeProfileData
    mountains: List[Tuple[int, int, int]]
    peaks: List[MountainPeak]
    U_zone: float
    L_zone: float
    POC: float
    n_mountains: int


@dataclass(slots=True)
class TagesBalance:
    """Eine Tages-Balance (Kalendertag in BKZ) mit ihren Nestern.

    Attributes:
        tag: Kalendertag (BKZ, tagesgenau).
        bar_start: Erster Bar-Index des Tages im Fenster-DataFrame.
        bar_ende: Letzter Bar-Index des Tages (inklusiv).
        n_bars: Anzahl Bars des Tages.
        gueltig: True = genug Bars und ein Profil vorhanden.
        poc: Point of Control des dominanten Berges.
        val: Untere Kante der Gesamt-Zone (Minimum der Berg-VALs).
        vah: Obere Kante der Gesamt-Zone (Maximum der Berg-VAHs).
        nester: Alle Berge des Tages (nach Volumen absteigend).
        zone: Vollstaendige Volumen-Zone (None bei ungueltigem Tag).
        atr: Mittlere Bar-Spanne des Tages (Skalierungsreferenz).
        poc_streu_atr: Spanne (max-min) des POC ueber die Konsens-
            Parametersaetze, in ATR. Direktes Unsicherheitsmass des POC.
        poc_min: Kleinster POC ueber die Konsens-Parametersaetze.
        poc_max: Groesster POC ueber die Konsens-Parametersaetze.
        lobe2_ratio: Volumen des zweitgroessten Gipfels geteilt durch das des
            groessten Gipfels desselben Tagesprofils. 1,0 = zwei gleich
            grosse Gipfel ("Zwei-Lappen-Tag"), nan = nicht bestimmbar.
            Reine Struktur-Diagnose/Erklaerung.
        lobe2_bin: Bin-Index des Zweitgipfels (-1 = unbestimmt).
        poc_eindeutig: True, wenn ``poc_streu_atr <= streu_toleranz_atr``.
            Nur dann ist der POC gegenueber Aufloesung/Glaettung stabil;
            sonst wandert er bei Parameterwechsel um mehr als die Toleranz.
    """

    tag: pd.Timestamp
    bar_start: int
    bar_ende: int
    n_bars: int
    gueltig: bool
    poc: float
    val: float
    vah: float
    nester: List[MountainPeak]
    zone: Optional[VolumeZone]
    atr: float
    poc_streu_atr: float
    poc_min: float
    poc_max: float
    lobe2_ratio: float
    lobe2_bin: int
    poc_eindeutig: bool


# =============================================================================
# 3) VOLUMEN-LOGIK (gemeinsamer Rechenkern scripts/volume_profile_core.py)
# =============================================================================
# Die Volumenfunktionen sind NICHT mehr in dieser Datei dupliziert: sie liegen
# einmalig im Rechenkern und werden oben importiert
# (``build_volume_profile`` / ``smooth_vol`` / ``find_mountains`` /
# ``va_for_mountain`` / ``zweitgipfel``; verbatim aus der eingefrorenen
# Baseline ``scripts/phasen_volumen_profil.py`` Z. 478-608). Die frueheren
# Kopien hier waren bitgleich - es gibt jetzt nur EINE Volumenlogik im Projekt.
#
# Hier bleibt ausschliesslich der Zonen-Vertrag DIESER Datei: die Balance-Zone
# ist die HUELLE der Segment-Value-Areas (``L_zone`` = min der Berg-VALs,
# ``U_zone`` = max der Berg-VAHs) und damit NICHT die 94 %-Zonen-VA ab POC des
# Rechenkerns. Dieser Modus (Tages-Balancen) bleibt unveraendert erhalten.


# ``smooth_vol`` / ``find_mountains`` / ``va_for_mountain`` / ``zweitgipfel``
# stammen unveraendert aus dem Rechenkern (oben importiert) - die frueheren
# Kopien hier waren bitgleich und sind entfallen.


def _profil_parameter(config: VolumeZoneConfig) -> ProfilParameter:
    """Bildet die Kernparameter aus der Volume-Zone-Konfiguration.

    Der Volumenfilter des Rechenkerns bleibt AUS (``vol_min``/``vol_quantil``
    = 0), weil die Tages-Balancen der Baseline ungefiltert rechnen - so bleibt
    das Ergebnis bitgleich zum bisherigen Ablauf.

    Args:
        config: Volume-Zone-Konfiguration.

    Returns:
        ``ProfilParameter`` fuer den Rechenkern.
    """
    return ProfilParameter(
        num_bins=config.num_bins,
        smooth_win=config.smooth_win,
        va_pct=config.va_pct,
        valley_rel=config.valley_rel,
        min_mountain_pct=config.min_mountain_pct,
        vol_min=0.0,
        vol_quantil=0.0,
    )


def compute_volume_zone(
    sub: pd.DataFrame, config: VolumeZoneConfig
) -> Optional[VolumeZone]:
    """Volumen-Zone eines Zeitraums (Baseline Z. 584-608) ueber den Rechenkern.

    Die Level kommen unveraendert aus ``compute_segmentierung``:
    ``POC`` = Gipfel des groessten Berges, ``L_zone``/``U_zone`` = HUELLE der
    Berg-Value-Areas (min VAL / max VAH, identisch zu ``val_huelle`` /
    ``vah_huelle``). Das ist der Tages-Balancen-Modus - NICHT die 94 %-Zonen-VA
    ab POC (die liefert ``Segmentierung.zone``).

    Args:
        sub: OHLCV-Bars des Zeitraums.
        config: Konfiguration (Bins, Glaettung, VA-Anteil, Tal-/Berg-Schwellen).

    Returns:
        ``VolumeZone`` oder ``None``, wenn kein Profil/Berg gefunden wurde.
    """
    seg = compute_segmentierung(sub, _profil_parameter(config))
    if seg is None:
        return None
    return VolumeZone(
        profile=seg.profile,
        mountains=seg.mountains,
        peaks=seg.nester,
        U_zone=seg.vah_huelle,
        L_zone=seg.val_huelle,
        POC=seg.poc,
        n_mountains=seg.n_segmente,
    )


# =============================================================================
# 3b) ZUSATZ-KENNZAHL (nicht Teil der Baseline): Zwei-Lappen-Diagnose
# =============================================================================
# ``zweitgipfel`` stammt unveraendert aus dem Rechenkern (oben importiert).


# =============================================================================
# 4) TAGES-SEGMENTIERUNG (BKZ, Kanon K6: dynamische Kalendergrenzen)
# =============================================================================


def effektive_min_bars(config: VolumeZoneConfig) -> int:
    """Liefert die wirksame Mindest-Bars-Zahl je Kalendertag.

    Ist ``config.min_bars_pro_tag`` gesetzt, gilt dieser Wert. Sonst wird er
    aus Fensterart (``day``) und Timeframe abgeleitet (``min_bars_fuer``):
    gefordert ist ein Anteil der nominalen Fensterdauer, damit auf jedem
    Timeframe dieselbe Groesse untersucht wird.

    Args:
        config: Volume-Zone-Konfiguration.

    Returns:
        Mindestzahl Bars je Kalendertag.
    """
    if config.min_bars_pro_tag is not None:
        return int(config.min_bars_pro_tag)
    return min_bars_fuer("day", config.timeframe)


def _kalendertage(df: pd.DataFrame, config: VolumeZoneConfig) -> List[Tuple[pd.Timestamp, int, int]]:
    """Zerlegt das Fenster in BKZ-Kalendertage ``(tag, erster_bar, letzter_bar)``.

    Nutzt die Fensterbildung des gemeinsamen Moduls
    ``scripts.volume_profile_windows`` (``FensterSpec(art="day")``): die Grenzen
    werden dort dynamisch per ``searchsorted`` auf der BKZ-Achse abgeleitet
    (Kanon K6) - keine Bar-Konstante, keine Zeitzonen-Projektion. Tage ohne
    Bars (z. B. Wochenende) entfallen.

    ``min_bars`` wird hier auf 1 gesetzt, damit ALLE Kalendertage geliefert
    werden: die Verwerfung nach ``min_bars_pro_tag`` erfolgt bewusst erst in
    ``berechne_tages_balancen``, damit der Report sie transparent ausweist.

    Args:
        df: Fenster-Bars mit ``ts`` (BKZ, tz-naiv, aufsteigend).
        config: Konfiguration (start/ende).

    Returns:
        Liste ``(tag, bar_start, bar_ende)`` mit ``bar_ende`` inklusiv.
    """
    fenster = baue_fenster(df, FensterSpec(art="day", min_bars=1))
    return [
        (f.ts_start.normalize(), f.bar_start, f.bar_ende) for f in fenster
    ]


def _poc_je_tag(
    df: pd.DataFrame,
    tage: Sequence[Tuple[pd.Timestamp, int, int]],
    config: VolumeZoneConfig,
    **overrides: object,
) -> np.ndarray:
    """POC je Kalendertag fuer EINEN Parametersatz (Konsensbaustein).

    Die Tagesgrenzen haengen nur von ``start``/``ende`` ab, nicht von Bins oder
    Glaettung - deshalb sind die Ergebnisvektoren der Parametersaetze
    positionsgleich und direkt vergleichbar.

    Args:
        df: Fenster-Bars (OHLCV, BKZ).
        tage: Tagesgrenzen aus ``_kalendertage``.
        config: Konfiguration.
        **overrides: Parameterueberschreibungen (z. B. ``num_bins=120``).

    Returns:
        Array ``poc`` je Tag; ``nan``, wenn der Tag nicht auswertbar ist.
    """
    cfg: VolumeZoneConfig = replace(config, **overrides) if overrides else config
    out = np.full(len(tage), np.nan, dtype=float)
    min_bars = effektive_min_bars(cfg)
    for i, (_tag, i0, i1) in enumerate(tage):
        if i1 - i0 + 1 < min_bars:
            continue
        zone = compute_volume_zone(df.iloc[i0 : i1 + 1], cfg)
        if zone is not None:
            out[i] = zone.POC
    return out


def _poc_konsens(
    df: pd.DataFrame,
    tage: Sequence[Tuple[pd.Timestamp, int, int]],
    config: VolumeZoneConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    """POC-Spanne je Tag ueber die Konsens-Parametersaetze.

    Die Spanne (max - min) ist das direkte Unsicherheitsmass des POC: sie
    misst genau die Verschiebung, die ein anderer Bin-/Glaettungsansatz
    erzeugt. Empirie (5 Symbole x 4 Monate, 434 Tage, M15): Median 0,73 ATR;
    Tage mit > 2 ATR Verschiebung werden damit vollstaendig erfasst, waehrend
    die reine Zwei-Lappen-Ratio nur 59 % davon findet.

    Args:
        df: Fenster-Bars (OHLCV, BKZ).
        tage: Tagesgrenzen aus ``_kalendertage``.
        config: Konfiguration.

    Returns:
        ``(poc_min, poc_max)`` je Tag; bei abgeschalteter Konsensrechnung
        (leeres ``konsens_bins``/``konsens_smooth``) beide ``nan``.
    """
    if not config.konsens_bins or not config.konsens_smooth:
        n = len(tage)
        return np.full(n, np.nan), np.full(n, np.nan)
    # Referenzwerte immer mitrechnen, damit die gemeldete POC im Band liegt.
    kombis = {(int(b), int(s)) for b in config.konsens_bins for s in config.konsens_smooth}
    kombis.add((int(config.num_bins), int(config.smooth_win)))
    mat = np.vstack(
        [
            _poc_je_tag(df, tage, config, num_bins=b, smooth_win=s)
            for b, s in sorted(kombis)
        ]
    )
    ok = np.isfinite(mat).any(axis=0)
    poc_min = np.full(len(tage), np.nan, dtype=float)
    poc_max = np.full(len(tage), np.nan, dtype=float)
    poc_min[ok] = np.nanmin(mat[:, ok], axis=0)
    poc_max[ok] = np.nanmax(mat[:, ok], axis=0)
    return poc_min, poc_max


def berechne_tages_balancen(
    df: pd.DataFrame, config: VolumeZoneConfig
) -> List[TagesBalance]:
    """Rechnet je BKZ-Kalendertag eine Balance samt ihrer Nester.

    Die gemeldeten Level (POC/VAL/VAH) stammen unveraendert aus dem
    Referenz-Parametersatz (``num_bins``/``smooth_win``/``va_pct``/...).
    Zusaetzlich wird je Tag gemessen, wie weit der POC ueber die
    Konsens-Parametersaetze wandert (``poc_streu_atr``) und woran das liegt
    (``lobe2_ratio``).

    Args:
        df: Fenster-Bars (OHLCV, BKZ).
        config: Konfiguration.

    Returns:
        Chronologische Liste ``TagesBalance`` (auch ungueltige Tage, damit die
        Report-Tabelle die Verwerfungen transparent ausweist).
    """
    high: np.ndarray = df["high"].to_numpy(dtype=float)
    low: np.ndarray = df["low"].to_numpy(dtype=float)
    tage = _kalendertage(df, config)
    poc_min_a, poc_max_a = _poc_konsens(df, tage, config)
    min_bars = effektive_min_bars(config)

    out: List[TagesBalance] = []
    for i, (tag, i0, i1) in enumerate(tage):
        n_bars = i1 - i0 + 1
        atr = float(np.mean(high[i0 : i1 + 1] - low[i0 : i1 + 1]))
        zone: Optional[VolumeZone] = None
        if n_bars >= min_bars:
            zone = compute_volume_zone(df.iloc[i0 : i1 + 1], config)
        if zone is None:
            out.append(
                TagesBalance(
                    tag=tag, bar_start=i0, bar_ende=i1, n_bars=n_bars,
                    gueltig=False, poc=float("nan"), val=float("nan"),
                    vah=float("nan"), nester=[], zone=None, atr=atr,
                    poc_streu_atr=float("nan"), poc_min=float("nan"),
                    poc_max=float("nan"), lobe2_ratio=float("nan"),
                    lobe2_bin=-1, poc_eindeutig=False,
                )
            )
            continue
        # Struktur-Diagnose auf derselben geglaetteten Reihe, die die
        # Baseline-Algorithmik intern verwendet (kein Eingriff in
        # find_mountains/va_for_mountain).
        vol_s = smooth_vol(zone.profile.vol, config.smooth_win)
        lobe2_ratio, lobe2_bin = zweitgipfel(vol_s, config.lobe_fenster)
        # Unsicherheit: Spanne des POC ueber die Konsens-Parametersaetze
        pmin_d, pmax_d = poc_min_a[i], poc_max_a[i]
        streu_atr = float("nan")
        if atr > 0 and np.isfinite(pmin_d) and np.isfinite(pmax_d):
            streu_atr = float((pmax_d - pmin_d) / atr)
        poc_eindeutig = bool(
            np.isfinite(streu_atr) and streu_atr <= config.streu_toleranz_atr
        )
        out.append(
            TagesBalance(
                tag=tag, bar_start=i0, bar_ende=i1, n_bars=n_bars,
                gueltig=True, poc=zone.POC, val=zone.L_zone, vah=zone.U_zone,
                nester=zone.peaks, zone=zone, atr=atr,
                poc_streu_atr=streu_atr,
                poc_min=float(pmin_d), poc_max=float(pmax_d),
                lobe2_ratio=lobe2_ratio, lobe2_bin=lobe2_bin,
                poc_eindeutig=poc_eindeutig,
            )
        )
    return out


# =============================================================================
# 5) AUSGABE (TXT-Report, TSV-Level, PNG-Chart)
# =============================================================================

_COL_BALANCE: str = "#1565c0"   # VAH/VAL-Rahmen der Tages-Balance
_COL_POC: str = "#0d47a1"       # POC (dominantes Nest), POC eindeutig
_COL_POC_U: str = "#c62828"     # POC uneindeutig (zwei gleichwertige Gipfel)
_COL_NEST: str = "#e65100"      # POC der uebrigen Nester
_COL_PREIS: str = "#bbbbbb"     # Preis (high/low-Linien)
_COL_LOB2: str = "#2e7d32"      # Zweitgipfel-Marke (Niveau des zweiten Lappens)


def _datei_stamm(config: VolumeZoneConfig) -> str:
    """Dateiname-Stamm der Ausgaben (ohne Endung).

    Args:
        config: Konfiguration.

    Returns:
        Stamm wie ``volume_zone_SILVER_M15_2026-08-01_2026-09-01``.
    """
    sym = "".join(ch for ch in config.symbol.upper() if ch.isalnum())
    return f"volume_zone_{sym}_{config.timeframe}_{config.start}_{config.ende}"


def _fmt(v: float, f: str = ".3f") -> str:
    """Formatiert eine Zahl; NaN/inf -> ``-``.

    Args:
        v: Wert.
        f: Format-String.

    Returns:
        Formatierter String.
    """
    if v is None or not np.isfinite(float(v)):
        return "-"
    return f"{float(v):{f}}"


def report_text(config: VolumeZoneConfig, balancen: Sequence[TagesBalance]) -> str:
    """Baut den TXT-Report (Kopfzeile, Tages-Tabelle, Zusammenfassung).

    Args:
        config: Konfiguration.
        balancen: Tages-Balancen des Fensters.

    Returns:
        Reporttext.
    """
    gueltig = [b for b in balancen if b.gueltig]
    linie = "=" * 118
    txt: List[str] = [
        linie,
        "VOLUME ZONE - TAGES-BALANCEN (POC / VAH / VAL)",
        f"Instrument: {config.symbol} {config.timeframe} | Zeitraum: "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"Profil: bins={config.num_bins} smooth={config.smooth_win} "
        f"va_pct={config.va_pct} valley_rel={config.valley_rel} "
        f"min_mountain_pct={config.min_mountain_pct} "
        f"min_bars/tag={effektive_min_bars(config)}"
        f"{'' if config.min_bars_pro_tag is not None else ' (abgeleitet aus Timeframe)'}",
        f"POC-Eindeutigkeit: Toleranz={config.streu_toleranz_atr} ATR ueber "
        f"Konsens-Saetze bins={list(config.konsens_bins)} x "
        f"smooth={list(config.konsens_smooth)} "
        f"(Streu = POC-Spanne in ATR; lobe2 = Zweitgipfel/Gipfel als Ursache)",
        "Volumen-Logik: herueberkopiert aus scripts/phasen_volumen_profil.py "
        "(eingefrorene Baseline, unveraenderte Algorithmik)",
        linie,
        f"Kalendertage im Fenster: {len(balancen)} | auswertbar: {len(gueltig)} | "
        f"verworfen: {len(balancen) - len(gueltig)}",
        "",
        "TAGES-BALANCEN (BKZ, Bar-Indizes aus dem Fenster-DataFrame):",
        "  Tag        | bars  |   POC     VAL     VAH   | Breite | B/ATR | "
        "Nester | lobe2 | Streu | POC eindeutig | POC der Nester (absteigend)",
        "  " + "-" * 118,
    ]
    if not gueltig:
        txt.append("  (keine auswertbare Tages-Balance - min_bars/tag senken?)")
    for b in balancen:
        if not b.gueltig:
            txt.append(
                f"  {b.tag:%Y-%m-%d} | {b.n_bars:5d} | "
                f"{'(verworfen: zu wenige Bars oder kein Profil)':>42}"
            )
            continue
        breite = b.vah - b.val
        b_atr = breite / b.atr if b.atr > 0 else float("nan")
        nester_txt = "; ".join(f"{p.poc:.3f}" for p in b.nester)
        flag = "ja" if b.poc_eindeutig else "NEIN"
        txt.append(
            f"  {b.tag:%Y-%m-%d} | {b.n_bars:5d} | {b.poc:8.3f} {b.val:8.3f} "
            f"{b.vah:8.3f} | {breite:6.3f} | {_fmt(b_atr, '.2f'):>5} | "
            f"{len(b.nester):6d} | {_fmt(b.lobe2_ratio, '.3f'):>5} | "
            f"{_fmt(b.poc_streu_atr, '.2f'):>5} | {flag:>13} | {nester_txt}"
        )
    txt.append("")
    if gueltig:
        b_atrs = np.array(
            [(b.vah - b.val) / b.atr for b in gueltig if b.atr > 0], dtype=float
        )
        nester_counts = np.array([len(b.nester) for b in gueltig], dtype=float)
        txt.append("ZUSAMMENFASSUNG:")
        txt.append(
            f"  Tages-Zone (VAH-VAL): median={np.median([b.vah - b.val for b in gueltig]):.3f}"
            f"  |  in ATR: median={np.median(b_atrs):.2f} "
            f"min={b_atrs.min():.2f} max={b_atrs.max():.2f}"
        )
        txt.append(
            f"  Nester je Tag: median={np.median(nester_counts):.0f} "
            f"min={nester_counts.min():.0f} max={nester_counts.max():.0f} "
            f"| Summe={int(nester_counts.sum())}"
        )
        n_eind = int(sum(1 for b in gueltig if b.poc_eindeutig))
        l2 = np.array(
            [b.lobe2_ratio for b in gueltig if np.isfinite(b.lobe2_ratio)], dtype=float
        )
        st = np.array(
            [b.poc_streu_atr for b in gueltig if np.isfinite(b.poc_streu_atr)],
            dtype=float,
        )
        txt.append(
            f"  POC eindeutig: {n_eind} von {len(gueltig)} Tagen "
            f"({100.0 * n_eind / len(gueltig):.1f} %) | unsicher: "
            f"{len(gueltig) - n_eind} (Streu > {config.streu_toleranz_atr} ATR)"
        )
        if st.size:
            txt.append(
                f"  POC-Streuung ueber die Parametersaetze: median={np.median(st):.2f} "
                f"p90={np.percentile(st, 90):.2f} max={st.max():.2f} ATR "
                f"(Anteil Tage > 0,5 ATR: {100.0 * np.mean(st > 0.5):.1f} %)"
            )
        if l2.size:
            txt.append(
                f"  lobe2 (Zweitgipfel/Gipfel): median={np.median(l2):.3f} "
                f"p90={np.percentile(l2, 90):.3f} max={l2.max():.3f}"
            )
    txt.append(linie)
    return "\n".join(txt) + "\n"


def levels_tsv(config: VolumeZoneConfig, balancen: Sequence[TagesBalance]) -> str:
    """Maschinenlesbarer Level-Block (ein Nest je Zeile).

    Je Tag eine BALANCE-Zeile (Gesamt-Zone) und je Nest eine NEST-Zeile mit
    POC/VAL/VAH. Tagesbezogene Felder (``atr``, ``lobe2``, ``poc_eindeutig``)
    stehen auf jeder Zeile des Tages, damit der Block ohne Join auswertbar ist.

    Args:
        config: Konfiguration.
        balancen: Tages-Balancen.

    Returns:
        TSV-Text (Kommentarzeilen + Header + Datenzeilen).
    """
    kopf: List[str] = [
        f"# volume_zone Level-Block - {config.symbol} {config.timeframe} | "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"# Profil: bins={config.num_bins} smooth={config.smooth_win} "
        f"va_pct={config.va_pct} valley_rel={config.valley_rel} "
        f"min_mountain_pct={config.min_mountain_pct}",
        "# rolle: BALANCE = Tages-Gesamtzone | NEST = einzelner Volumen-Berg",
        "# rank: 0 = dominantestes Nest des Tages (POC der Balance)",
        "# atr: mittlere Bar-Spanne (high-low) des Tages",
        "# poc_streu: Spanne des POC ueber die Konsens-Parametersaetze, in ATR",
        "#            (direktes Unsicherheitsmass; 0 = Konsensrechnung aus)",
        "# poc_min/poc_max: POC-Band in Preiseinheiten",
        "# lobe2: Zweitgipfel/Gipfel des Tagesprofils (1,0 = zwei gleich grosse",
        "#        Gipfel -> strukturell zweilappig)",
        "# poc_eindeutig: 1 = poc_streu <= streu_toleranz_atr",
        "tag\tbar_start\tbar_ende\tn_bars\tatr\tpoc_streu\tpoc_min\tpoc_max\t"
        "lobe2\tpoc_eindeutig\trolle\trank\tpoc\tval\tvah\tbreite\tvol\t"
        "peak_share_pct",
    ]
    zeilen: List[str] = list(kopf)
    for b in balancen:
        if not b.gueltig:
            continue
        lobe = f"{b.lobe2_ratio:.4f}" if np.isfinite(b.lobe2_ratio) else "nan"
        streu = f"{b.poc_streu_atr:.4f}" if np.isfinite(b.poc_streu_atr) else "nan"
        pmin = f"{b.poc_min:.5f}" if np.isfinite(b.poc_min) else "nan"
        pmax = f"{b.poc_max:.5f}" if np.isfinite(b.poc_max) else "nan"
        flag = "1" if b.poc_eindeutig else "0"
        basis = (
            f"{b.tag:%Y-%m-%d}\t{b.bar_start}\t{b.bar_ende}\t{b.n_bars}\t"
            f"{b.atr:.5f}\t{streu}\t{pmin}\t{pmax}\t{lobe}\t{flag}"
        )
        zeilen.append(
            f"{basis}\tBALANCE\t-1\t{b.poc:.5f}\t{b.val:.5f}\t{b.vah:.5f}\t"
            f"{b.vah - b.val:.5f}\t\t"
        )
        for rank, p in enumerate(b.nester):
            zeilen.append(
                f"{basis}\tNEST\t{rank}\t{p.poc:.5f}\t{p.val:.5f}\t"
                f"{p.vah:.5f}\t{p.vah - p.val:.5f}\t{p.vol:.1f}\t"
                f"{p.peak_share_pct:.2f}"
            )
    return "\n".join(zeilen) + "\n"


def zeichne_chart(
    config: VolumeZoneConfig,
    df: pd.DataFrame,
    balancen: Sequence[TagesBalance],
    out_png: Path,
) -> None:
    """Zeichnet Preis + Tages-Balancen (VAH/VAL-Rahmen, POC-Linien, Nester).

    X-Achse ist der Bar-Index (Kanon K5: Bar-Index ist Primaerschluessel), die
    Tick-Beschriftung zeigt die BKZ ohne Offset. Gueltige Tage erhalten einen
    Rahmen ``[VAL .. VAH]`` mit POC-Linie; die POCs der uebrigen Nester werden
    gestrichelt gezeichnet. Bei ``poc_eindeutig = False`` wird zusaetzlich das
    POC-Band ``[poc_min .. poc_max]`` der Konsens-Parametersaetze schraffiert -
    die Unsicherheit ist damit sichtbar, statt stillschweigend verborgen.

    Args:
        config: Konfiguration.
        df: Fenster-Bars (OHLCV, BKZ).
        balancen: Tages-Balancen.
        out_png: Zielpfad der PNG-Datei.
    """
    idx: np.ndarray = df["idx"].to_numpy(dtype=int)
    high: np.ndarray = df["high"].to_numpy(dtype=float)
    low: np.ndarray = df["low"].to_numpy(dtype=float)

    tage_zeigen: List[TagesBalance] = list(balancen)
    if config.chart_limit_tage > 0:
        tage_zeigen = tage_zeigen[-config.chart_limit_tage :]
    i_min: int = tage_zeigen[0].bar_start if tage_zeigen else 0
    i_max: int = tage_zeigen[-1].bar_ende if tage_zeigen else len(df) - 1

    fig, ax = plt.subplots(figsize=(17, 11))
    ax.plot(idx, high, color=_COL_PREIS, lw=0.5, zorder=1)
    ax.plot(idx, low, color=_COL_PREIS, lw=0.5, zorder=1)

    n_nester: int = 0
    n_unsicher: int = 0
    for b in tage_zeigen:
        if not b.gueltig:
            continue
        x0, x1 = b.bar_start, b.bar_ende
        # Gesamt-Zone der Tages-Balance (VAH/VAL-Rahmen)
        ax.add_patch(
            Rectangle(
                (x0, b.val), max(1, x1 - x0), b.vah - b.val,
                facecolor=_COL_BALANCE, edgecolor=_COL_BALANCE,
                alpha=0.12, lw=1.0, zorder=2,
            )
        )
        # POC der Balance (dominantes Nest) - rot gepunktet, wenn uneindeutig
        if b.poc_eindeutig:
            ax.plot([x0, x1], [b.poc, b.poc], color=_COL_POC, lw=1.6, zorder=5)
            ax.annotate(
                f"{b.tag:%d.%m} POC {b.poc:.3f}",
                (x0, b.poc), xytext=(x0 + 1, b.poc + 0.02),
                fontsize=6.0, color=_COL_POC, va="bottom", zorder=6,
            )
        else:
            n_unsicher += 1
            # Unsicherheitsband der Konsens-Parametersaetze
            if np.isfinite(b.poc_min) and np.isfinite(b.poc_max):
                ax.add_patch(
                    Rectangle(
                        (x0, b.poc_min), max(1, x1 - x0),
                        max(b.poc_max - b.poc_min, 1e-9),
                        facecolor=_COL_POC_U, edgecolor="none",
                        alpha=0.22, zorder=3,
                    )
                )
            ax.plot([x0, x1], [b.poc, b.poc], color=_COL_POC_U, lw=1.4,
                    ls=(0, (2, 2)), zorder=5)
            ax.annotate(
                f"{b.tag:%d.%m} POC {b.poc:.3f} ? "
                f"(Streu {_fmt(b.poc_streu_atr, '.2f')} ATR)",
                (x0, b.poc), xytext=(x0 + 1, b.poc + 0.02),
                fontsize=6.0, color=_COL_POC_U, va="bottom", zorder=6,
            )
        # POCs der uebrigen Nester
        for p in b.nester[1:]:
            ax.plot(
                [x0, x1], [p.poc, p.poc], color=_COL_NEST, lw=0.8,
                ls=(0, (4, 3)), zorder=4,
            )
            n_nester += 1

    step = max(16, len(df) // 14)
    ticks = np.arange(0, len(df), step)
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
        rotation=45, ha="right", fontsize=8,
    )
    ax.set_xlim(i_min - 1, i_max + 1)
    ax.set_ylabel(f"Preis ({config.symbol})")
    ax.grid(alpha=0.3)
    ax.set_title(
        f"VOLUME ZONE | {config.symbol} {config.timeframe} | Tages-Balancen "
        f"(VAH/VAL + POC) | {config.start} .. {config.ende} (ende-exkl.) | "
        f"bins={config.num_bins} va_pct={config.va_pct} | "
        f"Bars {i_min}..{i_max}"
    )
    gueltig = [b for b in tage_zeigen if b.gueltig]
    n_eind = sum(1 for b in gueltig if b.poc_eindeutig)
    stat: List[str] = [
        f"Tage gezeigt: {len(tage_zeigen)} (auswertbar {len(gueltig)})",
        f"Nester gezeichnet: {len(gueltig) + n_nester}",
        f"POC eindeutig: {n_eind} | unsicher: {len(gueltig) - n_eind} "
        f"(Toleranz {config.streu_toleranz_atr} ATR)",
    ]
    if gueltig:
        b_atr = np.array(
            [(b.vah - b.val) / b.atr for b in gueltig if b.atr > 0], dtype=float
        )
        st = np.array(
            [b.poc_streu_atr for b in gueltig if np.isfinite(b.poc_streu_atr)],
            dtype=float,
        )
        stat.append(f"Zonenbreite: median {np.median(b_atr):.2f} ATR")
        stat.append(
            f"Nester/Tag: median {np.median([len(b.nester) for b in gueltig]):.0f}"
        )
        if st.size:
            stat.append(f"POC-Streuung: median {np.median(st):.2f} ATR")
    ax.text(
        0.5, 0.99, "\n".join(stat), transform=ax.transAxes, fontsize=7.5,
        va="top", ha="center", family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf6e3",
                  edgecolor="gray", alpha=0.94),
        zorder=20,
    )
    ax.legend(
        handles=[
            Line2D([0], [0], color=_COL_BALANCE, lw=6, alpha=0.3,
                   label="Tages-Balance (VAH..VAL)"),
            Line2D([0], [0], color=_COL_POC, lw=1.6, label="POC (dominantes Nest)"),
            Line2D([0], [0], color=_COL_POC_U, lw=1.4, ls=(0, (2, 2)),
                   label="POC uneindeutig + Band der Konsens-Parametersaetze"),
            Line2D([0], [0], color=_COL_NEST, lw=0.8, ls=(0, (4, 3)),
                   label="POC weiterer Nester"),
            Line2D([0], [0], color=_COL_PREIS, lw=1.0, label="Preis (high/low)"),
        ],
        loc="upper left", fontsize=7.5, framealpha=0.9,
    )
    fig.tight_layout()
    fig.savefig(out_png, dpi=config.dpi)
    plt.close(fig)


# =============================================================================
# 5b) PROFILE-GRID (Sichtpruefung der Erkennung)
# =============================================================================


_PALETTE_NEST: Tuple[str, ...] = (
    "#1565c0",  # Nest 0 (dominant)
    "#e65100",  # Nest 1
    "#2e7d32",  # Nest 2
    "#6a1b9a",  # Nest 3
    "#00838f",  # Nest 4
)
_COL_OHNE_NEST: str = "#dcdcdc"


def zeichne_profil_grid(
    config: VolumeZoneConfig,
    balancen: Sequence[TagesBalance],
    out_png: Path,
) -> None:
    """Zeichnet je Kalendertag das Volumenprofil als eigenes Panel.

    Das ist die Sichtpruefung der Erkennung: je Tag ein horizontaler
    Volumen-Histogramm (relativ auf das Tagesmaximum normiert, damit die Form
    vergleichbar ist), farblich nach Nest getrennt, mit Value-Area-Band,
    POC-Linie und Zweitgipfel-Marke. Die Nester sind die von
    ``find_mountains`` gelieferten Berge - ihre Einfaerbung zeigt direkt,
    ob die Zerlegung plausibel ist.

    Args:
        config: Konfiguration.
        balancen: Tages-Balancen (ungueltige Tage werden ausgelassen).
        out_png: Zielpfad der PNG-Datei.
    """
    tage_zeigen: List[TagesBalance] = [b for b in balancen if b.gueltig]
    if config.chart_limit_tage > 0:
        tage_zeigen = tage_zeigen[-config.chart_limit_tage :]
    if config.grid_max_tage > 0:
        tage_zeigen = tage_zeigen[-config.grid_max_tage :]
    if not tage_zeigen:
        return

    n: int = len(tage_zeigen)
    ncols: int = min(4, n)
    nrows: int = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(17.0, 3.1 * nrows), squeeze=False)

    for k, b in enumerate(tage_zeigen):
        ax = axes[k // ncols][k % ncols]
        zone = b.zone
        if zone is None:
            ax.axis("off")
            continue
        prof = zone.profile
        centers = prof.centers
        vol = prof.vol
        vmax = float(vol.max()) if vol.size and vol.max() > 0 else 1.0
        bw = float(centers[1] - centers[0]) if centers.size > 1 else 1.0

        # Farbe je Bin: Nest-Zugehoerigkeit aus der Baseline-Zerlegung
        farben = np.array([_COL_OHNE_NEST] * centers.size, dtype=object)
        for i, (s, _p, e) in enumerate(zone.mountains):
            farben[s : e + 1] = _PALETTE_NEST[i % len(_PALETTE_NEST)]
        ax.barh(centers, vol / vmax, height=bw * 0.86, color=list(farben), lw=0.0)

        # Value-Area-Band der Tages-Gesamtzone
        ax.axhspan(b.val, b.vah, color=_COL_BALANCE, alpha=0.10, zorder=0)

        # POC (dominantes Nest) - rot gepunktet plus Unsicherheitsband,
        # wenn der POC ueber die Parametersaetze wandert
        if np.isfinite(b.poc_min) and np.isfinite(b.poc_max) and b.poc_max > b.poc_min:
            ax.axhspan(b.poc_min, b.poc_max, color=_COL_POC_U, alpha=0.18, zorder=1)
        poc_farbe = _COL_POC if b.poc_eindeutig else _COL_POC_U
        poc_stil = "-" if b.poc_eindeutig else (0, (2, 2))
        ax.axhline(b.poc, color=poc_farbe, lw=1.3, ls=poc_stil, zorder=5)
        for p in b.nester[1:]:
            ax.axhline(p.poc, color=_COL_NEST, lw=0.7, ls=(0, (4, 3)), zorder=4)
        # Zweitgipfel-Marke (Niveau des zweiten Lappens)
        if b.lobe2_bin >= 0:
            lvl = float((prof.edges[b.lobe2_bin] + prof.edges[b.lobe2_bin + 1]) / 2)
            ax.axhline(lvl, color=_COL_LOB2, lw=0.8, ls=(0, (1, 2)), zorder=3)

        ax.set_xlim(0.0, 1.12)
        ax.set_ylim(prof.pmin, prof.pmax)
        ax.tick_params(labelsize=6.0)
        ax.grid(alpha=0.25, axis="x")
        ax.set_title(
            f"{b.tag:%a %d.%m} | POC {b.poc:.3f}"
            f"{'' if b.poc_eindeutig else '  POC-SPANNE ' + _fmt(b.poc_streu_atr, '.2f') + ' ATR'}\n"
            f"lobe2 {_fmt(b.lobe2_ratio, '.2f')} | Nester {len(b.nester)} | "
            f"Zone {(b.vah - b.val) / b.atr if b.atr > 0 else float('nan'):.1f} ATR"
            f" | Bars {b.bar_start}..{b.bar_ende}",
            fontsize=6.5,
            color=("#1b1b1b" if b.poc_eindeutig else _COL_POC_U),
        )
        if k % ncols == 0:
            ax.set_ylabel(f"Preis ({config.symbol})", fontsize=7.0)
    # Leere Restpanels ausblenden
    for k in range(n, nrows * ncols):
        axes[k // ncols][k % ncols].axis("off")

    n_unsicher = sum(1 for b in tage_zeigen if not b.poc_eindeutig)
    fig.suptitle(
        f"TAGESPROFILE (rel. Volumen, Maximum = 1) | {config.symbol} "
        f"{config.timeframe} | {config.start} .. {config.ende} (ende-exkl., BKZ) | "
        f"bins={config.num_bins} smooth={config.smooth_win} "
        f"va_pct={config.va_pct} valley_rel={config.valley_rel} | "
        f"Tage {n} | POC uneindeutig {n_unsicher}",
        fontsize=9.5, y=0.999,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color=_PALETTE_NEST[0], lw=6, label="Nest 0 (POC-Nest)"),
            Line2D([0], [0], color=_PALETTE_NEST[1], lw=6, label="Nest 1"),
            Line2D([0], [0], color=_PALETTE_NEST[2], lw=6, label="Nest 2"),
            Line2D([0], [0], color=_COL_OHNE_NEST, lw=6, label="keinem Nest zugeordnet"),
            Line2D([0], [0], color=_COL_BALANCE, lw=6, alpha=0.3, label="Value Area (VAL..VAH)"),
            Line2D([0], [0], color=_COL_POC, lw=1.3, label="POC"),
            Line2D([0], [0], color=_COL_POC_U, lw=1.3, ls=(0, (2, 2)),
                   label="POC uneindeutig"),
            Line2D([0], [0], color=_COL_POC_U, lw=6, alpha=0.18,
                   label="POC-Band (Konsens-Parametersaetze)"),
            Line2D([0], [0], color=_COL_LOB2, lw=0.8, ls=(0, (1, 2)),
                   label="Zweitgipfel-Niveau"),
        ],
        loc="lower center", ncol=9, fontsize=7.0, framealpha=0.9,
    )
    fig.tight_layout(rect=(0.0, 0.02, 1.0, 0.985))
    fig.savefig(out_png, dpi=config.dpi)
    plt.close(fig)


# =============================================================================
# 6) MAIN
# =============================================================================


def _parse_cli(args: Sequence[str], config: VolumeZoneConfig) -> VolumeZoneConfig:
    """Ueberschreibt Defaults aus ``--key=value``-Argumenten.

    Args:
        args: Argumentliste ohne Programmnamen.
        config: Startkonfiguration (Defaults).

    Returns:
        Angepasste Konfiguration.
    """
    felder: Dict[str, object] = {}
    for a in args:
        if not a.startswith("--") or "=" not in a:
            continue
        key, val = a[2:].split("=", 1)
        key = key.strip().replace("-", "_")
        val = val.strip()
        if key in ("symbol", "timeframe", "start", "ende"):
            felder[key] = val
        elif key in ("num_bins", "smooth_win", "min_bars_pro_tag", "dpi",
                     "chart_limit_tage", "grid_max_tage", "lobe_fenster"):
            felder[key] = int(val)
        elif key in ("va_pct", "valley_rel", "min_mountain_pct", "lobe2_schwelle",
                     "streu_toleranz_atr"):
            felder[key] = float(val)
        elif key in ("konsens_bins", "konsens_smooth"):
            felder[key] = tuple(
                int(t) for t in val.replace(";", ",").split(",") if t.strip()
            )
        elif key in ("db_path", "report_dir"):
            felder[key] = Path(val)
        else:
            raise SystemExit(f"Unbekanntes Argument: --{key}")
    return replace(config, **felder)  # type: ignore[arg-type]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: findet Tages-Balancen und schreibt Report/TSV/Charts.

    Alle Parameter sind per Default vorbelegt; die CLI ueberschreibt sie
    einzeln (siehe ``VolumeZoneConfig``).

    Args:
        argv: Argumentliste (Default: ``sys.argv[1:]``).

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    config = _parse_cli(args, VolumeZoneConfig())

    if config.num_bins < 3:
        raise SystemExit("num_bins muss >= 3 sein.")
    if config.smooth_win < 1:
        raise SystemExit("smooth_win muss >= 1 sein.")
    if config.lobe_fenster < 1:
        raise SystemExit("lobe_fenster muss >= 1 sein.")
    if not 0.0 < config.va_pct < 1.0:
        raise SystemExit("va_pct muss im offenen Intervall (0, 1) liegen.")
    if not 0.0 < config.lobe2_schwelle <= 1.0:
        raise SystemExit("lobe2_schwelle muss im Intervall (0, 1] liegen.")
    if config.streu_toleranz_atr < 0.0:
        raise SystemExit("streu_toleranz_atr muss >= 0 sein.")
    if config.start >= config.ende:
        raise SystemExit(
            f"Leerer Zeitraum: start={config.start} muss < ende={config.ende} sein."
        )

    df: pd.DataFrame = load_data(
        config.db_path, config.start, config.ende, config.symbol, config.timeframe
    )
    if df.empty:
        raise SystemExit(
            f"Keine Bars fuer {config.symbol} {config.timeframe} "
            f"in {config.start} .. {config.ende}."
        )

    balancen = berechne_tages_balancen(df, config)

    # Stolperfalle sichtbar machen: liegen auf dem gewaehlten Timeframe
    # weniger Bars je Kalendertag vor als min_bars verlangt, wird alles
    # verworfen.
    if balancen and not any(b.gueltig for b in balancen):
        bars_je_tag = sorted({b.n_bars for b in balancen})
        print(
            f"WARNUNG: kein auswertbarer Kalendertag. Beobachtete Bars/Tag: "
            f"{bars_je_tag} - alle unter min_bars/tag="
            f"{effektive_min_bars(config)}. Zeitfenster verkleinern "
            f"(--min_bars_pro_tag=<...>) oder einen feineren Timeframe waehlen.\n"
        )

    config.report_dir.mkdir(parents=True, exist_ok=True)
    stamm = _datei_stamm(config)
    text = report_text(config, balancen)
    (config.report_dir / f"{stamm}.txt").write_text(text, encoding="utf-8")
    (config.report_dir / f"{stamm}_levels.tsv").write_text(
        levels_tsv(config, balancen), encoding="utf-8"
    )
    zeichne_chart(config, df, balancen, config.report_dir / f"{stamm}.png")
    zeichne_profil_grid(
        config, balancen, config.report_dir / f"{stamm}_profile.png"
    )

    print(text)
    print(
        f"Ausgabe: {config.report_dir / (stamm + '.png')}\n"
        f"         {config.report_dir / (stamm + '_profile.png')}\n"
        f"         {config.report_dir / (stamm + '.txt')}\n"
        f"         {config.report_dir / (stamm + '_levels.tsv')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
