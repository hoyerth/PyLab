"""
VOLUMENPROFIL-LAUF (scripts/volume_profile_run.py)
====================================================
Orchestrator: verbindet Daten -> Fenster -> Rechenkern -> Speicher -> Chart.
Dieses Modul enthaelt selbst KEINE Volumenlogik, KEINE Fensterbildung und
KEINE Zeichenroutine - es steuert nur die vier Bausteine:

    scripts.market_segmentation        Bars laden (BKZ-Garantie)
    scripts.volume_profile_windows     Fenster schneiden (day/week/h12/h4/h1/m30)
    scripts.volume_profile_core        POC/VAL/VAH + Segmente + POC-Streuung
    scripts.volume_profile_nests       Nester ueber Fenstergrenzen (eigene Objekte)
    scripts.volume_profile_store       Laufzeit-Speicher (RAM) je Parametersatz
    scripts.volume_profile_chart       PNG-Ausgaben

Zwei Ebenen je Fenster
----------------------
    SEGMENTE   Berge/Nester aus ``find_mountains`` - die bewaehrte
               Segment-Erkennung, bleibt unveraendert erhalten.
    BAND       das Hauptband des Fensters: die ZONEN-VA (symmetrische Value
               Area ab dem globalen POC, ``va_zone_pct`` = 0,94 des
               Gesamtvolumens). Die Huelle der Segment-Value-Areas wird im Kern
               nur noch als Kennzahl gefuehrt (``huellen_abdeckung``), nicht
               mehr als Band - sie deckte die Luecken zwischen den Nestern zu.

Separation der Bereiche (dritte Ebene, zerlegend statt zusammenfassend)
----------------------------------------------------------------------
Ein durchgehendes Band ist meist breiter als der Move, den es beschreiben
soll: als zusammenfassendes Band ist es die HUELLE ueber alle Segmente und deckt
die Zwischenraeume mit zu. Deshalb wird zusaetzlich ZERLEGT (``zerlege_bereiche``,
im Kern; hier nur gemeldet):

    BEREICH    die Value Area EINES Segmentes ``[VAL .. VAH]`` - jedes Nest
               bekommt seinen eigenen Preisbereich (``va_pct``, Default 0,7).
    LUECKE     der Zwischenraum zweier benachbarter Bereiche. Dort traegt kein
               Segment Volumen: hier laufen die schnellen Moves.

``Separierung.anteil_ausserhalb`` ist das Mass der Isolation (Anteil des
Profilvolumens ausserhalb aller Bereiche). Kleineres ``va_pct`` (z. B. 0,70
statt der Baseline-Norm 0,93) schneidet die Bereiche enger um den Gipfel und
trennt benachbarte Nester deutlicher; Report, Chart und Konsolenzeile weisen
das aus.

Nester ueber Fenstergrenzen (vierte Ebene, verbindend)
-----------------------------------------------------
Ein Volumenknoten richtet sich nicht nach dem Kalender: die Fenster-Ebene
zerlegt ihn an der Tagesgrenze in zwei Berge. ``volume_profile_nests`` erkennt
den Knoten deshalb als GANZES und liefert eigene Objekte:

    TERRITORIUM  Kette gepaarter Berge (Kerne ueberlappen im Preis UND die
                 POCs liegen hoechstens ``nest_link_level_atr`` auseinander)
                 = der Knoten als Zone ueber die Zeit.
    NEST         EIN zusammenhaengender Lauf von Bars darin (Instanz) mit
                 eigenem POC/VAL/VAH, eigenem ATR und eigenem POC-Konsens.

EIN TERRITORIUM TRAEGT GENAU EINEN LAUF: liefert eine Kette mehrere Laeufe, war
der Preis zwischenzeitlich weg - das sind getrennte Knoten (auch bei gleichem
Level), nicht der Wiederbesuch eines Territoriums. Die Nester sind damit kausal
nacheinander geordnet, und die Territoriums-Id ist die Position in der ZEIT.
Die Level-Schranke verhindert Sammelobjekte: eine Kern-Ueberlappung allein sagt
nichts ueber das LEVEL (Empirie September 2026: Kette mit POC-Spanne 7,4 ATR).

Die Schicht rechnet NICHTS neu: die Berge kommen aus der eingefrorenen
Berg-Erkennung, die Level aus ``build_volume_profile``/``va_for_mountain``. Sie
wird hier nur ANGESTOSSEN (``finde_nester``), in Speicherzeilen uebersetzt
(``_nest_zeilen``) und gemeldet (Reportabschnitt + Konsolenzeile). Laeufe unter
``nest_min_bars``/``nest_min_anteil_pct`` (Flimmer) und Laeufe am geladenen Rand
(angeschnitten) bleiben als Zeile erhalten, gehen aber nicht in die Statistik
ein - so ist kalibrierbar, wie viele es wirklich gibt.

Dateiname und Parametrisierung
------------------------------
Ein Default-Lauf behaelt seinen Namen. Weicht ein profilbildender Parameter ab
(z. B. ``--va_pct=0.70``), wird er an Dateiname und Charttitel angehaengt -
ein Probierlauf ueberschreibt damit nicht stillschweigend den Default-Stand.

Modus (es gibt nur EINE Engine und nur EIN Hauptband)
-----------------------------------------------------
``--modus=zone`` ist der einzige gueltige Wert (Zonen-VA ab POC). Der frueher
zweite Wert ``balance`` (Huelle der Segment-Value-Areas) ist ENTFERNT: die
Huelle deckte die Luecken zwischen den Nestern zu und war genau das, was die
Separation (``Bereiche``/``Luecken``) aufloest. Der Schalter bleibt als
fail-loud-Pruefung bestehen - ein unbekannter Name scheitert, statt still ein
falsches Band zu melden. Die Huellkanten selbst werden im Kern weitergefuehrt
(``val_huelle``/``vah_huelle``) und ihre Deckung als Kennzahl berechnet
(``huellen_abdeckung``) - damit bleibt der Vergleich zum archivierten
Tages-Balancen-Lauf pruefbar, ohne dass daraus ein Auswertungsmodus wird.

Speicher
--------
Es gibt KEINE Datenbankablage der Profile. Die Profile werden zur Laufzeit
gehalten (``ProfilSpeicher``): ein Profil ist an seinen Parametersatz gebunden
und wird bei Parameteraenderung sofort ungueltig - eine Dateiablage waere dann
Altbestand, der stillschweigend weiterverwendet werden koennte.

Mit den Profilen werden auch die SEGMENTE, die BEREICHE (Value Area je Segment)
und die LUECKEN gehalten (``_bereich_zeilen``). Die Bereiche sind die
Datengrundlage der Separation-Statistik (Breiten absolut und in ATR, Volumen,
Lueckenlage) - sie werden nicht neu gerechnet, sondern aus ``zerlege_bereiche``
abgeleitet und unter derselben ``run_id`` gehalten.

Ebenso gehen die TERRITORIEN und NESTER der Fenstergrenzen-Schicht in denselben
Speicher (``_nest_zeilen``): Territorien als Zeilen, Nester als eigene Objekte
mit eigenem POC/VAL/VAH, ATR der Lebensdauer und POC-Konsens. Die
Nestparameter (Raster/Link/Mindestgroesse) formen diese Zeilen mit und gehoeren
deshalb in die ``run_id`` - ein Lauf mit anderem Raster ist ein anderer
Parametersatz.

Vergeben wird der Laufzeitspeicher vom prozessweiten Halter
(``volume_profile_store.HALTER``): ``hole_oder_anlegen`` liefert bei gleichem
Parametersatz denselben Speicher zurueck (nichts wird doppelt gerechnet), bei
geaendertem Parametersatz einen neuen. Damit steht der Live-Einsatz auf
derselben Mechanik wie der CLI-Lauf.

Mindest-Belegung und Verwurf
----------------------------
``effektive_min_bars`` leitet aus Fensterart und Timeframe eine Mindest-
BELEGUNG ab (``min_bars_fuer``: Anteil ``min_abdeckung``, Default 0,5, der
nominalen Fensterdauer - M15/day -> 48 Bars, H1/day -> 12, M15/h4 -> 8). Diese
Zahl ist eine KENNZAHL (Report/TSV/``run_id``) und wird NICHT standardmaessig
angewandt: unvollstaendige Fenster bleiben erhalten (``unvollstaendige_
verwerfen=False``). Angewandt wird eine Belegungsschwelle nur, wenn sie
ausdruecklich gesetzt ist (``--min_bars=...``) oder der Verwurf angeschaltet
wird (``--unvollstaendige_verwerfen=1``); Schwelle liefert
``wirksame_min_bars``. Im Default faellt damit kein Fenster weg - ein Tag,
dessen Daten mitten im Tag enden, bekommt sein Profil aus dem, was da ist.

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Zeit kommt ausschliesslich als BKZ aus ``load_data`` (``time AT TIME ZONE
'UTC'``, tz-naiv) und wird als solche gehalten und beschriftet. Die
Fenstergrenzen werden dynamisch per ``searchsorted`` gebildet (K6); es gibt
keine Zeitzonen-Projektion (K2) und kein nacktes ``SELECT time`` (K4).

Aufruf (Projekt-Wurzel) - Default ist September 2026 mit va_pct = 0,7:
    python -m scripts.volume_profile_run
    python -m scripts.volume_profile_run --va_pct=0.93       ^
        (Vergleich gegen die eingefrorene Baseline-Norm 0,93)
    python -m scripts.volume_profile_run --window=week --symbol=SILVER ^
        --timeframe=M15 --start=2026-06-01 --ende=2026-09-01
    python -m scripts.volume_profile_run --window=h4 --vol_quantil=0.05
    python -m scripts.volume_profile_run --window=day --min_bars=40 ^
        --unvollstaendige_verwerfen=1
    python -m scripts.volume_profile_run --nest_link_level_atr=0     ^
        (Gegenseite: nur identische POCs werden gepaart)
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Direktaufruf (``python scripts/volume_profile_run.py``) legt nur ``scripts/``
# auf den Modulpfad -> der Namespace-Import ``scripts.*`` scheitert. Der Guard
# stellt die Projekt-Wurzel voran; beim ``-m``-Aufruf ist er inaktiv.
if __package__ in (None, ""):
    _projekt_root: Path = Path(__file__).resolve().parent.parent
    if str(_projekt_root) not in sys.path:
        sys.path.insert(0, str(_projekt_root))

from scripts.market_segmentation import load_data  # noqa: E402
from scripts.volume_profile_chart import (  # noqa: E402
    ChartStil,
    zeichne_alles,
)
from scripts.volume_profile_core import (  # noqa: E402
    MODI,
    Band,
    FensterProfil,
    KonsensParameter,
    ProfilParameter,
    band_von,
    profil_mit_kennzahlen,
    zerlege_bereiche,
)
from scripts.volume_profile_nests import (  # noqa: E402
    NestErgebnis,
    NestInstanz,
    NestParameter,
    Territorium,
    finde_nester,
)
from scripts.volume_profile_store import (  # noqa: E402
    HALTER,
    BereichZeile,
    LueckeZeile,
    NestObjektZeile,
    NestZeile,
    ProfilZeile,
    TerritoriumZeile,
)
from scripts.volume_profile_windows import (  # noqa: E402
    FENSTER_ARTEN,
    FensterSpec,
    baue_fenster,
    min_bars_fuer,
)

_ROOT: Path = Path(__file__).resolve().parent.parent

# Schutzgrenze der Fensterauswertung: unter einer Bar gibt es kein Fenster,
# aus dem ein Profil entstehen koennte (es fehlt die Preisspanne). Das ist KEINE
# Belegungsanforderung - im Default wird deshalb NICHTS verworfen (die Schwelle
# ``MIN_BARS_HART`` = 1 Bar ist von jedem Fenster erfuellt); sie greift nur als
# unterste Kante, wenn nichts anderes gesagt ist.
MIN_BARS_HART: int = 1


# =============================================================================
# 1) KONFIGURATION (Defaults direkt am Dateianfang, per CLI ueberschreibbar)
# =============================================================================


@dataclass(frozen=True, slots=True)
class VolumeProfilConfig:
    """Vollstaendige Parametrisierung eines Volumenprofil-Laufs.

    Alle Felder sind vorbelegt; der Lauf ist ohne Argumente moeglich. Die
    Volumen-Defaults entsprechen der eingefrorenen Baseline
    (``phasen_volumen_profil.py`` Z. 216-220), zusaetzlich kommt die
    Zonen-Value-Area mit ``va_zone_pct`` (0,94) hinzu.

    Attributes:
        symbol: DB-Symbol (Default ``SILVER``).
        timeframe: Kerzen-Timeframe (Default ``M15``).
        start: Fenster-Start als ISO-Datum, inklusive (BKZ).
        ende: Fenster-Ende als ISO-Datum, exklusiv (BKZ).
        db_path: Marktdaten-DuckDB (Default = zentrale Produktions-DB).
        window_kind: Fensterart (``day``/``week``/``h12``/``h4``/``h1``/``m30``).
            Default ``day`` = echtes Tagesfenster (BKZ-Kalendertag 00:00 bis
            23:59, Handelssession des Brokers) - davon wird nur bei
            ausdruecklicher Angabe einer anderen Art abgewichen.
        min_bars: Mindestzahl Bars je Fenster. ``None`` (Default) = ABLEITEN
            aus Fensterart und Timeframe (siehe ``min_abdeckung``) - damit
            wird auf jedem Timeframe dieselbe Groesse untersucht. Die
            abgeleitete Zahl ist eine KENNZAHL (Mindest-Belegung); angewandt
            wird sie nur, wenn sie ausdruecklich gesetzt ist oder
            ``unvollstaendige_verwerfen`` gilt (``wirksame_min_bars``).
        min_abdeckung: Anteil der nominalen Fensterdauer, der fuer die
            abgeleitete Mindest-Belegung angenommen wird (Default 0,5 =
            halbes Fenster).
        unvollstaendige_verwerfen: False (Default) = Fenster werden NICHT
            verworfen, auch wenn sie die abgeleitete Mindest-Belegung nicht
            erreichen - ein unvollstaendiger Tag (Datenende mitten im Tag,
            Feiertag mit kurzer Session) bekommt trotzdem sein Profil; allein
            der Bar-Bestand begrenzt die Aussage, und das steht im Report.
            True = die abgeleitete Mindest-Belegung wird angewandt und duenne
            Fenster fallen weg. Ein ausdruecklich gesetztes ``min_bars``
            gewinnt in JEDEM Fall (es ist eine Ansage, keine Ableitung).
        num_bins: Anzahl Preis-Bins des Profils (Baseline ``NUM_BINS``).
        smooth_win: Glaettungsfenster des Volumens (Baseline ``SMOOTH_WIN``).
        modus: Hauptband des Laufs: ``zone`` (Zonen-VA ab POC, einziges
            Hauptband). Der Wert wird gegen ``MODI`` geprueft und scheitert
            fail-loud; der frueher zweite Wert ``balance`` ist entfernt.
        va_pct: Value-Area-Anteil des Berg-Volumens (Default 0,7). Er setzt die
            Weite des EIGENEN Bereiches je Segment: kleiner = enger um den
            Gipfel, groesserer Anteil des Profils bleibt in den Luecken
            (schnelle Moves). Die eingefrorene Baseline rechnete mit 0,93 -
            fuer den Vergleich laesst sich das per ``--va_pct=0.93`` setzen.
        valley_rel: Tal-Schwellwert zur Berg-Trennung (Baseline ``VALLEY_REL``).
        min_mountain_pct: Mindestanteil am groessten Berg (Baseline
            ``MIN_MOUNTAIN_PCT``).
        va_zone_pct: Anteil des GESAMTVOLUMENS fuer die Zonen-Value-Area ab POC.
        vol_min: Absolute Untergrenze des Bar-``tick_volume`` (0 = aus).
        vol_quantil: Anteil der volumenaermsten Bars, der verworfen wird
            (0 = aus).
        konsens_bins: Bin-Anzahlen der POC-Streuungsmessung (leer = aus).
        konsens_smooth: Glaettungsfenster der POC-Streuungsmessung.
        streu_toleranz_atr: Toleranz fuer ``poc_eindeutig`` in ATR.
        nest_schritt_atr: Preisschritt des gemeinsamen RASTERS der Nest-Level
            als Vielfaches des Bezugs-ATR (Median der Fenster-ATRs). Er macht
            die Level ueber die Nester hinweg vergleichbar (``schritt_atr`` in
            ``volume_profile_nests``).
        nest_link_toleranz_atr: Zusaetzliche Ueberlappungstoleranz beim Paaren
            zweier Berg-Kerne (0,0 = strenger Schnitt).
        nest_min_bars: Mindestzahl Bars eines Nest-Laufs; darunter ist der Lauf
            ein Flimmer-Lauf und geht nicht in die Statistik ein.
        nest_min_anteil_pct: Mindestvolumen eines Nest-Laufs in Prozent des
            groessten Laufs (Flimmer-Grenze, analog ``min_mountain_pct``).
        nest_konsens_k: Rasterschritte, ueber die die POC-Unsicherheit eines
            Nestes gemessen wird (Aufloesungs-Unsicherheit).
        nest_konsens_smooth: Glaettungsfenster der Nest-Konsensmessung.
        nest_streu_toleranz_atr: Toleranz fuer ``poc_eindeutig`` eines Nestes.
        nest_pad_tage: Kalendertage Polster vor/nach dem Zeitraum, ueber die
            die Nest-Erkennung zusaetzlich laeuft. Damit wird ein Knoten, der
            ueber die Zeitraumgrenze weitergeht, mit seinem GANZEN Volumen
            erkannt (statt an der Grenze abgeschnitten zu werden). Gemeldet und
            gehalten werden nur die Nester im Kernbereich; der Rest bleibt
            ``angeschnitten``. 0 = kein Polster (A/B-Gegenseite).
        out_dir: Zielordner fuer PNG/TXT/TSV.
        dpi: Aufloesung der PNG-Ausgabe.
        grid_max_profile: Obergrenze der Fenster im Profil-Grid. 0 (Default) =
            ALLE Fenster des Testzeitraums zeigen (es gibt keinen eigenen
            4h-/Intraday-Grafikmodus; eine Kuerzung nur per Ansage/CLI).
        grid_seiten_max: Hoechstzahl Panels je PNG-Seite. Da immer der ganze
            Testzeitraum gezeigt wird, wird bei mehr Fenstern seitenweise
            ausgegeben (``..._s1.png``, ``..._s2.png``, ...) - nichts wird
            weggelassen, nur aufgeteilt.
    """

    # --- Datenzugriff -------------------------------------------------------
    symbol: str = "SILVER"
    timeframe: str = "M15"
    # Untersuchungszeitraum: September 2026 (ende-exklusiv = Monatsfenster).
    # Das Monatsende bleibt als Grenze stehen, auch wenn die DB noch nicht so
    # weit reicht - leere Bloecke entfallen ohnehin, spaeter nachgeladene Bars
    # gehoeren damit automatisch dazu.
    start: str = "2026-09-01"
    ende: str = "2026-10-01"
    db_path: Path = _ROOT / "data" / "market_data.duckdb"

    # --- Fenster ------------------------------------------------------------
    # Default = ECHTES Tagesfenster: BKZ-Kalendertag 00:00 bis 23:59 (die
    # Handelssession des Brokers in Broker-Kerzen-Zeit). Nur wenn ausdruecklich
    # eine andere Fensterart angegeben wird (week/h12/h4/h1/m30), wird davon
    # abgewichen.
    window_kind: str = "day"
    min_bars: Optional[int] = None
    min_abdeckung: float = 0.5
    # Kein Verwurf unvollstaendiger Fenster (Default): ein Tag, dessen Daten
    # mitten im Tag enden, wird mit dem gerechnet, was da ist.
    unvollstaendige_verwerfen: bool = False

    # --- Volumenprofil (Default va_pct=0,7 = enger Bereich je Segment) ------
    num_bins: int = 60
    smooth_win: int = 3
    modus: str = "zone"
    va_pct: float = 0.7
    valley_rel: float = 0.15
    min_mountain_pct: float = 4.0
    va_zone_pct: float = 0.94
    vol_min: float = 0.0
    vol_quantil: float = 0.0

    # --- POC-Unsicherheit ---------------------------------------------------
    konsens_bins: Tuple[int, ...] = (30, 60, 120, 240)
    konsens_smooth: Tuple[int, ...] = (1, 3, 5, 9)
    streu_toleranz_atr: float = 1.0

    # --- Nester ueber Fenstergrenzen (eigene Schicht) ------------------------
    # Ein Volumenknoten richtet sich nicht nach dem Kalender: er wird an einem
    # Tag angesammelt und am naechsten weiter gehandelt. Die Fenster-Ebene
    # zerlegt ihn deshalb an der Tagesgrenze in zwei Berge; diese Schicht
    # erkennt ihn als GANZES (Kette gepaarter Berge -> Territorium) und schneidet
    # ihn in zusammenhaengende Laeufe (Instanzen = Nester).
    nest_schritt_atr: float = 0.25
    nest_link_toleranz_atr: float = 0.0
    # Level-Schranke: zwei Berge werden nur gepaart, wenn ihre POCs hoechstens
    # so viele ATR auseinanderliegen. Ohne sie verband die Kern-Ueberlappung
    # auch Berge auf verschiedenen LEVELN zu einem Sammelobjekt.
    nest_link_level_atr: float = 2.0
    nest_min_bars: int = 8
    nest_min_anteil_pct: float = 4.0
    nest_konsens_k: Tuple[float, ...] = (0.15, 0.25, 0.40)
    nest_konsens_smooth: Tuple[int, ...] = (1, 3, 5, 9)
    nest_streu_toleranz_atr: float = 1.0
    # Polster: die Erkennung laeuft ueber einen GEPOLSTERTEN Zeitraum (so viele
    # Kalendertage davor und danach), damit ein Knoten, der ueber die Grenze
    # weiterlaeuft, mit seinem GANZEN Volumen erkannt wird. Gemeldet, gehalten
    # und gezeichnet werden nur die Nester im geladenen Kernbereich; was am
    # geladenen Rand aufhoert, bleibt als ``angeschnitten`` markiert.
    # 0 = kein Polster (Gegenseite des A/B-Vergleichs).
    nest_pad_tage: int = 3

    # --- Ausgabe ------------------------------------------------------------
    out_dir: Path = _ROOT / "test" / "VolumeZone" / "reports"
    dpi: int = 300
    grid_max_profile: int = 0
    grid_seiten_max: int = 96


# =============================================================================
# 2) LAUF: Fenster -> Kern -> Vertrag
# =============================================================================


def _profil_parameter(config: VolumeProfilConfig) -> ProfilParameter:
    """Bildet die Kernparameter aus der Laufkonfiguration.

    Args:
        config: Laufkonfiguration.

    Returns:
        ``ProfilParameter`` fuer den Rechenkern.
    """
    return ProfilParameter(
        num_bins=config.num_bins,
        smooth_win=config.smooth_win,
        va_pct=config.va_pct,
        valley_rel=config.valley_rel,
        min_mountain_pct=config.min_mountain_pct,
        va_zone_pct=config.va_zone_pct,
        vol_min=config.vol_min,
        vol_quantil=config.vol_quantil,
    )


def _konsens_parameter(config: VolumeProfilConfig) -> Optional[KonsensParameter]:
    """Bildet die Konsensparameter (None = Streuungsmessung aus).

    Args:
        config: Laufkonfiguration.

    Returns:
        ``KonsensParameter`` oder ``None``, wenn eine Satzliste leer ist.
    """
    if not config.konsens_bins or not config.konsens_smooth:
        return None
    return KonsensParameter(
        konsens_bins=tuple(config.konsens_bins),
        konsens_smooth=tuple(config.konsens_smooth),
        streu_toleranz_atr=config.streu_toleranz_atr,
    )


def _nest_parameter(config: VolumeProfilConfig) -> NestParameter:
    """Bildet die Nestparameter aus der Laufkonfiguration.

    Die Werte stammen unveraendert aus der Konfiguration; es wird nichts
    abgeleitet oder mit anderen Parametern vermischt (der Bezugs-ATR des
    Rasters entsteht erst in ``finde_nester`` aus den Fenster-ATRs).

    Args:
        config: Laufkonfiguration.

    Returns:
        ``NestParameter`` fuer die Nest-Erkennung.
    """
    return NestParameter(
        schritt_atr=config.nest_schritt_atr,
        link_toleranz_atr=config.nest_link_toleranz_atr,
        link_level_atr=config.nest_link_level_atr,
        min_bars=config.nest_min_bars,
        min_anteil_pct=config.nest_min_anteil_pct,
        konsens_k=tuple(config.nest_konsens_k),
        konsens_smooth=tuple(config.nest_konsens_smooth),
        streu_toleranz_atr=config.nest_streu_toleranz_atr,
    )


def _pad_zeitraum(config: VolumeProfilConfig) -> Tuple[str, str]:
    """Bildet Start/Ende des gepolsterten Ladezeitraums (BKZ-Kalendertage).

    Das Polster wird in Kalendertagen auf die ISO-Daten des Zeitraums
    gerechnet - es verschiebt nur den LADEbereich, es findet keine
    Zeitzonen-Projektion statt (K2) und keine Bar-Konstante (K6).

    Args:
        config: Laufkonfiguration (``start``/``ende``/``nest_pad_tage``).

    Returns:
        ``(pad_start, pad_ende)`` als ISO-Daten (ende exklusiv wie ``ende``).
    """
    tage = int(config.nest_pad_tage)
    start = pd.Timestamp(config.start) - pd.Timedelta(days=tage)
    ende = pd.Timestamp(config.ende) + pd.Timedelta(days=tage)
    return start.strftime("%Y-%m-%d"), ende.strftime("%Y-%m-%d")


def _pad_txt(config: VolumeProfilConfig) -> str:
    """Kurztext des Polsters fuer Konsole und Report.

    Args:
        config: Laufkonfiguration.

    Returns:
        Text mit Polstertagen und geladenem Bereich; ``ohne Polster`` bei 0.
    """
    if int(config.nest_pad_tage) <= 0:
        return "ohne Polster (nur der geladene Zeitraum)"
    pad_start, pad_ende = _pad_zeitraum(config)
    return (
        f"Polster {int(config.nest_pad_tage)} Tage je Seite "
        f"(erkannt ueber {pad_start} .. {pad_ende}, gemeldet im Kern)"
    )


def _nester_im_kern(
    pad_ergebnis: NestErgebnis,
    pad_df: pd.DataFrame,
    kern_df: pd.DataFrame,
    kern_profile: Sequence[FensterProfil],
) -> NestErgebnis:
    """Schneidet ein auf dem Polster erkanntes Ergebnis auf den Kernbereich.

    Die ERKENNUNG laeuft ueber den gepolsterten Zeitraum (der Knoten wird mit
    seinem ganzen Volumen gesehen); GEMELDET wird nur, was im geladenen
    Zeitraum liegt. Die Zuordnung laeuft ueber die BKZ-Zeitstempel (nicht ueber
    den Bar-Index des Polsterrahmens), damit der Bar-Index wieder der des
    geladenen Zeitraums ist (K5).

    Die Level (POC/VAL/VAH, Volumen, ATR) bleiben die des Polsterlaufs: sie
    tragen das Volumen des GANZEN Knotens. Der gemeldete Bar-Bereich liegt
    dagegen IM geladenen Zeitraum; reicht der Lauf darueber hinaus (oder endet
    er am geladenen Rand), ist er ``angeschnitten`` - er kann weiterlaufen und
    geht deshalb nicht in die Statistik ein. ``n_bars`` zaehlt die Bars des
    gemeldeten Bereichs, ``vol`` das Volumen des ganzen Laufs.

    Args:
        pad_ergebnis: Ergebnis der Erkennung auf dem gepolsterten Zeitraum.
        pad_df: Bars des gepolsterten Zeitraums (BKZ).
        kern_df: Bars des geladenen Zeitraums (BKZ).
        kern_profile: Fensterprofile des geladenen Zeitraums.

    Returns:
        ``NestErgebnis`` in den Bar-Indizes des geladenen Zeitraums.
    """
    if not pad_ergebnis.instanzen or kern_df.empty:
        return NestErgebnis(
            atr_bezug=pad_ergebnis.atr_bezug, schritt=pad_ergebnis.schritt,
            n_laeufe_roh=pad_ergebnis.n_laeufe_roh,
        )
    kern_ts = kern_df["ts"].to_numpy(dtype="datetime64[ns]")
    pad_ts = pad_df["ts"].to_numpy(dtype="datetime64[ns]")
    letzter_kern = int(kern_ts.size - 1)
    # Kernbereich im POLSTERrahmen: daran wird erkannt, ob ein Lauf ueber den
    # geladenen Zeitraum hinausreicht (Pad-Indizes sind nicht Kern-Indizes).
    pad_i0 = int(np.searchsorted(pad_ts, kern_ts[0], side="left"))
    pad_i1 = int(np.searchsorted(pad_ts, kern_ts[-1], side="right")) - 1
    fenster = sorted(
        (p for p in kern_profile if p.gueltig), key=lambda p: int(p.bar_start)
    )

    def _fenster_im_bereich(a: int, b: int) -> int:
        return int(sum(1 for p in fenster if p.bar_ende >= a and p.bar_start <= b))

    instanzen: List[NestInstanz] = []
    terr_neu_id: Dict[int, int] = {}
    terr_alt: Dict[int, Territorium] = {}
    for i in pad_ergebnis.instanzen:
        t_start = max(pd.Timestamp(i.ts_start), pd.Timestamp(kern_ts[0]))
        t_ende = min(pd.Timestamp(i.ts_ende), pd.Timestamp(kern_ts[-1]))
        if t_start > t_ende:
            continue
        a = int(np.searchsorted(kern_ts, np.datetime64(t_start), side="left"))
        b = int(np.searchsorted(kern_ts, np.datetime64(t_ende), side="right")) - 1
        if b < a:
            continue
        # Angeschnitten heisst: der Lauf ist am geladenen Rand oder am
        # Polsterrand aufgeschnitten, kann also weiterlaufen.
        angeschnitten = bool(
            i.angeschnitten or i.bar_start < pad_i0 or i.bar_ende > pad_i1
            or a <= 0 or b >= letzter_kern
        )
        tid_alt = int(i.territorium_id)
        if tid_alt not in terr_neu_id:
            terr_neu_id[tid_alt] = len(terr_neu_id)
            quelle = next(
                (t for t in pad_ergebnis.territorien if int(t.id) == tid_alt), None
            )
            if quelle is not None:
                terr_alt[terr_neu_id[tid_alt]] = quelle
        instanzen.append(
            NestInstanz(
                id=len(instanzen), territorium_id=terr_neu_id[tid_alt],
                rang=int(i.rang), bar_start=a, bar_ende=b,
                ts_start=pd.Timestamp(kern_ts[a]), ts_ende=pd.Timestamp(kern_ts[b]),
                n_bars=int(b - a + 1), n_fenster=_fenster_im_bereich(a, b),
                poc=float(i.poc), val=float(i.val), vah=float(i.vah),
                vol=float(i.vol), atr=float(i.atr),
                raster_bins=int(i.raster_bins),
                raster_schritt=float(i.raster_schritt),
                zu_klein=bool(i.zu_klein), angeschnitten=angeschnitten,
                konsens=i.konsens,
            )
        )

    # Territorien: Kanten/Anzahl Berge kommen aus dem Polsterlauf, der
    # Bar-Bereich und die Fensterzahl aus den KERNnestern dieses Territoriums
    # (damit gilt wieder der Bar-Index des geladenen Zeitraums, K5).
    je_terr: Dict[int, List[NestInstanz]] = {}
    for i in instanzen:
        je_terr.setdefault(i.territorium_id, []).append(i)
    fertig: List[Territorium] = []
    for tid in sorted(je_terr):
        meine = je_terr[tid]
        a = min(i.bar_start for i in meine)
        b = max(i.bar_ende for i in meine)
        n_fenster = _fenster_im_bereich(a, b)
        quelle = terr_alt.get(tid)
        fertig.append(Territorium(
            id=tid,
            unten=float(quelle.unten) if quelle else float("nan"),
            oben=float(quelle.oben) if quelle else float("nan"),
            kern_unten=float(quelle.kern_unten) if quelle else float("nan"),
            kern_oben=float(quelle.kern_oben) if quelle else float("nan"),
            n_berge=int(quelle.n_berge) if quelle else 0,
            n_fenster=n_fenster,
            labels=tuple(quelle.labels) if quelle else (),
            bar_start=a, bar_ende=b, verschmolzen=bool(n_fenster > 1),
        ))
    return NestErgebnis(
        territorien=tuple(fertig), instanzen=tuple(instanzen),
        berge=pad_ergebnis.berge, atr_bezug=pad_ergebnis.atr_bezug,
        schritt=pad_ergebnis.schritt, n_laeufe_roh=pad_ergebnis.n_laeufe_roh,
    )


def hauptband(p: FensterProfil, config: VolumeProfilConfig) -> Band:
    """Liefert das Hauptband eines Fensters im gewaehlten Modus.

    Es wird nur AUSGEWAEHLT, nicht gerechnet: das Band steckt bereits im
    Vertrag ``Segmentierung`` (``zone``).

    Args:
        p: Fensterprofil.
        config: Laufkonfiguration (liefert ``modus``).

    Returns:
        ``Band`` des Modus; ohne Profil sind alle Kanten ``nan``.
    """
    return band_von(p.segmentierung, config.modus)


def nest_lauf(
    df: pd.DataFrame,
    profile: Sequence[FensterProfil],
    config: VolumeProfilConfig,
) -> NestErgebnis:
    """Erkennt die Nester ueber Fenstergrenzen - auf einem POLSTERRaum.

    Die Erkennung laeuft ueber den gepolsterten Zeitraum (``nest_pad_tage``
    davor und danach): ein Knoten, der vor dem Zeitraum beginnt oder danach
    weiterlaeuft, wird dann mit seinem GANZEN Volumen gesehen. Gemeldet und
    gehalten werden nur die Nester des geladenen Zeitraums (``_nester_im_kern``)
    - mit den Bar-Indizes DIESES Zeitraums (K5).

    Bei ``nest_pad_tage=0`` wird der geladene Zeitraum selbst durchsucht; das
    ist die Gegenseite des A/B-Vergleichs (dann fehlt das Volumen jenseits der
    Grenze, und Laeufe an der Grenze sind ``angeschnitten``).

    Args:
        df: Bars des geladenen Zeitraums (BKZ).
        profile: Fensterprofile des geladenen Zeitraums.
        config: Laufkonfiguration.

    Returns:
        ``NestErgebnis`` mit Territorien und Nestern des geladenen Zeitraums.
    """
    par = _profil_parameter(config)
    nest_par = _nest_parameter(config)
    if int(config.nest_pad_tage) <= 0:
        return finde_nester(profile, df, par, nest_par)
    pad_start, pad_ende = _pad_zeitraum(config)
    pad_df: pd.DataFrame = load_data(
        config.db_path, pad_start, pad_ende, config.symbol, config.timeframe
    )
    if pad_df.empty:
        return finde_nester(profile, df, par, nest_par)
    pad_profile, _n_verworfen = rechne_fensterprofile(pad_df, config)
    if not any(p.gueltig for p in pad_profile):
        return finde_nester(profile, df, par, nest_par)
    roh = finde_nester(pad_profile, pad_df, par, nest_par)
    return _nester_im_kern(roh, pad_df, df, profile)


def effektive_min_bars(config: VolumeProfilConfig) -> int:
    """Liefert die abgeleitete Mindest-BELEGUNG eines Laufs (Kennzahl).

    Ist ``config.min_bars`` gesetzt, gilt dieser Wert. Sonst wird er aus
    Fensterart und Timeframe abgeleitet (``min_bars_fuer``): gefordert ist der
    Anteil ``min_abdeckung`` der NOMINALEN Fensterdauer, damit auf jedem
    Timeframe dieselbe Groesse untersucht wird.

    Wichtig: Das ist die Kennzahl, die im Report/TSV und in der ``run_id``
    steht. Ob sie als Verwurfschwelle WIRKT, entscheidet ``wirksame_min_bars``
    - standardmaessig wird NICHT verworfen.

    Args:
        config: Laufkonfiguration.

    Returns:
        Mindest-Belegung in Bars je Fenster.
    """
    if config.min_bars is not None:
        return int(config.min_bars)
    return min_bars_fuer(config.window_kind, config.timeframe, config.min_abdeckung)


def wirksame_min_bars(config: VolumeProfilConfig) -> int:
    """Liefert die Schwelle, ab der ein Fenster TATSAECHLICH verworfen wird.

    Drei Faelle, in dieser Reihenfolge:

    1. ``min_bars`` ist ausdruecklich gesetzt -> es gilt (Ansage gewinnt immer;
       das traegt auch die Bitgleichheit zum archivierten Tages-Balancen-Lauf,
       der mit ``min_bars_pro_tag=40`` eingefroren ist).
    2. ``unvollstaendige_verwerfen=True`` -> die abgeleitete Mindest-Belegung
       gilt und duenne Fenster fallen weg.
    3. sonst (Default) -> nur die Schutzgrenze ``MIN_BARS_HART``: es wird NICHT
       verworfen, ein unvollstaendiger Tag bekommt sein Profil.

    Args:
        config: Laufkonfiguration.

    Returns:
        Schwelle in Bars je Fenster.
    """
    if config.min_bars is not None:
        return int(config.min_bars)
    if config.unvollstaendige_verwerfen:
        return effektive_min_bars(config)
    return MIN_BARS_HART


def verwurf_aktiv(config: VolumeProfilConfig) -> bool:
    """True, wenn Fenster unter einer Belegungsanforderung wegfallen.

    Args:
        config: Laufkonfiguration.

    Returns:
        True, wenn tatsaechlich verworfen wird.
    """
    return wirksame_min_bars(config) > MIN_BARS_HART


def rechne_fensterprofile(
    df: pd.DataFrame, config: VolumeProfilConfig
) -> Tuple[List[FensterProfil], int]:
    """Rechnet je Zeitfenster ein Volumenprofil.

    Verworfen wird nur, wenn eine Belegungsanforderung wirkt
    (``wirksame_min_bars``): bei ausdruecklich gesetztem ``min_bars`` oder mit
    ``unvollstaendige_verwerfen=True``. Im Default (beides nicht gesetzt)
    bleiben ALLE Fenster erhalten - ein unvollstaendiger Tag (Datenende mitten
    im Tag, kurze Feiertags-Session) wird mit dem gerechnet, was da ist; die
    Schwelle ist dann nur die Schutzgrenze ``MIN_BARS_HART`` (1 Bar), die jedes
    Fenster erfuellt.

    Args:
        df: Bars des Gesamtfensters (BKZ).
        config: Laufkonfiguration.

    Returns:
        ``(profile, n_verworfen)`` - chronologische Liste der ausgewerteten
        Fenster und Anzahl der wegen der Belegungsschwelle verworfenen Fenster
        (im Default 0).
    """
    par = _profil_parameter(config)
    kons = _konsens_parameter(config)
    min_belegung = effektive_min_bars(config)
    schwelle = wirksame_min_bars(config)
    spec = FensterSpec(art=config.window_kind, min_bars=min_belegung)
    fenster = baue_fenster(df, spec)

    profile: List[FensterProfil] = []
    n_verworfen = 0
    for f in fenster:
        if f.n_bars < schwelle:
            n_verworfen += 1
            continue
        sub = df.iloc[f.bar_start : f.bar_ende + 1]
        seg, k, atr = profil_mit_kennzahlen(sub, par, kons)
        profile.append(
            FensterProfil(
                label=f.label,
                window_kind=f.art,
                bar_start=f.bar_start,
                bar_ende=f.bar_ende,
                ts_start=f.ts_start,
                ts_ende=f.ts_ende,
                n_bars=f.n_bars,
                vol_summe=float(sub["tick_volume"].sum()),
                atr=atr,
                segmentierung=seg,
                konsens=k,
            )
        )
    return profile, n_verworfen


def _speicher_zeilen(
    profile: Sequence[FensterProfil], config: VolumeProfilConfig
) -> Tuple[List[ProfilZeile], List[NestZeile]]:
    """Uebersetzt Fensterprofile in Speicherzeilen (ohne I/O).

    Args:
        profile: Fensterprofile.
        config: Laufkonfiguration.

    Returns:
        ``(profilzeilen, nestzeilen)`` fuer ``ProfilSpeicher.merke``.
    """
    zeilen: List[ProfilZeile] = []
    nests: List[NestZeile] = []
    for p in profile:
        seg = p.segmentierung
        if seg is None or seg.zone is None:
            continue
        z = seg.zone
        zeilen.append(
            ProfilZeile(
                symbol=config.symbol, timeframe=config.timeframe,
                window_kind=p.window_kind, label=p.label,
                bar_start=int(p.bar_start), bar_ende=int(p.bar_ende),
                ts_start=p.ts_start, ts_ende=p.ts_ende, n_bars=int(p.n_bars),
                n_bars_gefiltert=int(seg.n_bars_gefiltert),
                vol_summe=float(p.vol_summe), atr=float(p.atr),
                poc=float(seg.poc), val=float(z.val), vah=float(z.vah),
                va_zone_pct=float(config.va_zone_pct),
                va_abdeckung=float(z.abdeckung),
                val_huelle=float(seg.val_huelle), vah_huelle=float(seg.vah_huelle),
                n_segmente=int(seg.n_segmente), lobe2=float(seg.lobe2_ratio),
                poc_streu_atr=float(p.konsens.streu_atr),
                poc_min=float(p.konsens.poc_min), poc_max=float(p.konsens.poc_max),
                poc_eindeutig=bool(p.konsens.eindeutig),
            )
        )
        for rank, nest in enumerate(seg.nester):
            nests.append(
                NestZeile(
                    bar_start=int(p.bar_start), bar_ende=int(p.bar_ende),
                    rank=rank, poc=float(nest.poc), val=float(nest.val),
                    vah=float(nest.vah), vol=float(nest.vol),
                    peak_share_pct=float(nest.peak_share_pct),
                    bin_start=int(nest.bin_start), bin_gipfel=int(nest.bin_gipfel),
                    bin_ende=int(nest.bin_ende),
                )
            )
    return zeilen, nests


def _bereich_zeilen(
    profile: Sequence[FensterProfil],
) -> Tuple[List[BereichZeile], List[LueckeZeile]]:
    """Uebersetzt die Separation der Fenster in Speicherzeilen (ohne I/O).

    Es wird nichts neu gerechnet: die Zeilen entstehen aus
    ``zerlege_bereiche`` (Value Area je erkanntem Segment + Zwischenraeume).
    Damit liegen die Bereiche als Preisbaender (``val``/``vah``/``poc``/
    ``breite``, auch in ATR) und die Luecken dazwischen im Laufzeitspeicher -
    die Grundlage der Separation-Statistik.

    Args:
        profile: Fensterprofile.

    Returns:
        ``(bereichzeilen, lueckezeilen)`` fuer ``ProfilSpeicher.merke``.
    """
    bereiche: List[BereichZeile] = []
    luecken: List[LueckeZeile] = []
    for p in profile:
        sep = zerlege_bereiche(p.segmentierung, p.atr)
        for b in sep.bereiche:
            bereiche.append(
                BereichZeile(
                    bar_start=int(p.bar_start), bar_ende=int(p.bar_ende),
                    rank=int(b.rank), poc=float(b.poc), val=float(b.val),
                    vah=float(b.vah), breite=float(b.breite),
                    vol=float(b.vol), breite_atr=float(b.breite_atr),
                )
            )
        for l in sep.luecken:
            luecken.append(
                LueckeZeile(
                    bar_start=int(p.bar_start), bar_ende=int(p.bar_ende),
                    rank_unten=int(l.rank_unten), rank_oben=int(l.rank_oben),
                    unten=float(l.unten), oben=float(l.oben),
                    breite=float(l.breite), breite_atr=float(l.breite_atr),
                )
            )
    return bereiche, luecken


def _nest_zeilen(
    ergebnis: NestErgebnis,
) -> Tuple[List[TerritoriumZeile], List[NestObjektZeile]]:
    """Uebersetzt die Nest-Erkennung in Speicherzeilen (ohne I/O).

    Es wird nichts neu gerechnet: die Zeilen entstehen unveraendert aus
    ``finde_nester`` (Territorien = Ketten gepaarter Berge, Instanzen =
    zusammenhaengende Laeufe mit eigenen Leveln). Die Kennzahl
    ``huellen_abdeckung`` des Kerns geht hier NICHT ein - sie ist keine
    Auswertungsgroesse, sondern nur der Vergleich zum archivierten Lauf.

    Args:
        ergebnis: Ergebnis der Nest-Erkennung.

    Returns:
        ``(territoriumzeilen, nestobjektzeilen)`` fuer
        ``ProfilSpeicher.merke``.
    """
    territorien: List[TerritoriumZeile] = [
        TerritoriumZeile(
            id=int(t.id), unten=float(t.unten), oben=float(t.oben),
            kern_unten=float(t.kern_unten), kern_oben=float(t.kern_oben),
            n_berge=int(t.n_berge), n_fenster=int(t.n_fenster),
            labels="+".join(t.labels), bar_start=int(t.bar_start),
            bar_ende=int(t.bar_ende), verschmolzen=bool(t.verschmolzen),
        )
        for t in ergebnis.territorien
    ]
    objekte: List[NestObjektZeile] = [
        NestObjektZeile(
            id=int(i.id), territorium_id=int(i.territorium_id),
            rang=int(i.rang), bar_start=int(i.bar_start),
            bar_ende=int(i.bar_ende), ts_start=i.ts_start, ts_ende=i.ts_ende,
            n_bars=int(i.n_bars), n_fenster=int(i.n_fenster),
            poc=float(i.poc), val=float(i.val), vah=float(i.vah),
            breite=float(i.breite), breite_atr=float(i.breite_atr),
            vol=float(i.vol), atr=float(i.atr),
            raster_bins=int(i.raster_bins),
            raster_schritt=float(i.raster_schritt),
            zu_klein=bool(i.zu_klein), angeschnitten=bool(i.angeschnitten),
            poc_streu_atr=float(i.konsens.streu_atr),
            poc_min=float(i.konsens.poc_min), poc_max=float(i.konsens.poc_max),
            poc_eindeutig=bool(i.konsens.eindeutig),
        )
        for i in ergebnis.instanzen
    ]
    return territorien, objekte


def _nest_text(ergebnis: NestErgebnis, config: VolumeProfilConfig) -> str:
    """Kurzzeile der Nest-Erkennung fuer die Konsole.

    Args:
        ergebnis: Ergebnis der Nest-Erkennung (Bar-Indizes des Zeitraums).
        config: Laufkonfiguration (liefert den Polstertext).

    Returns:
        Textzeile mit Territorien, Nestern und den ausgeschlossenen Laeufen.
    """
    grund = f" | {_pad_txt(config)}"
    if not ergebnis.instanzen:
        return (
            "Nester: keine erkannt (kein zusammenhaengender Lauf ueber die "
            f"Mindestgroesse){grund}"
        )
    dauer = [i.dauer_stunden for i in ergebnis.nester]
    breite = [i.breite_atr for i in ergebnis.nester if np.isfinite(i.breite_atr)]
    return (
        f"Nester: {len(ergebnis.nester)} Laeufe in "
        f"{ergebnis.n_territorien} Territorien "
        f"({ergebnis.n_verschmolzen} ueber Fenstergrenzen; 1 Territorium = "
        f"1 Lauf) | "
        f"ausgeschlossen: {ergebnis.n_zu_klein} zu klein, "
        f"{ergebnis.n_angeschnitten} am Rand | "
        f"Dauer median {np.median(dauer):.1f} h | "
        f"Breite median "
        f"{np.median(breite) if breite else float('nan'):.2f} ATR"
        f"{grund}"
    )


def _nest_abschnitt(
    ergebnis: NestErgebnis, config: VolumeProfilConfig
) -> List[str]:
    """Baut den Reportabschnitt "Nester ueber Fenstergrenzen".

    Args:
        ergebnis: Ergebnis der Nest-Erkennung (Bar-Indizes des Zeitraums).
        config: Laufkonfiguration (liefert den Polstertext).

    Returns:
        Zeilen des Abschnitts (ohne fuehrende Leerzeile).
    """
    zeilen: List[str] = [
        "NESTER UEBER FENSTERGRENZEN (zusammenhaengende Laeufe als eigene Objekte):",
        "  TERRITORIUM = Kette gepaarter Berge (Kerne ueberlappen im Preis UND",
        "  POC-Abstand <= Level-Toleranz) = der Knoten als Zone ueber die Zeit.",
        "  NEST (Instanz) = EIN zusammenhaengender Lauf von Bars darin. EIN",
        "  Territorium traegt GENAU EINEN Lauf (1:1); jedes Loch im Bar-Index",
        "  erzeugt ein NEUES Territorium - die Rueckkehr auf ein Level ist ein",
        "  neues Nest, kein Wiederbesuch. Die Id ist die Position in der ZEIT.",
        "  Level sind auf EINEM Raster gerechnet (gleicher Preisschritt ueber alle",
        "  Nester), ATR ist der der eigenen Lebensdauer.",
        f"  Erkennung: {_pad_txt(config)}.",
    ]
    if not ergebnis.instanzen:
        zeilen.append("")
        zeilen.append("  Keine Nester erkannt (kein Lauf erreicht die Mindestgroesse).")
        return zeilen
    atr_bezug = ergebnis.atr_bezug
    zeilen += [
        f"  Bezugs-ATR (Median der Fenster) = "
        f"{'-' if not np.isfinite(atr_bezug) else f'{atr_bezug:.5f}'} | "
        f"Rasterschritt = "
        f"{'-' if not np.isfinite(ergebnis.schritt) else f'{ergebnis.schritt:.5f}'} | "
        f"Laeufe roh = {ergebnis.n_laeufe_roh}",
        "  id   terr  rang  bars       BKZ von .. bis        nB  Fen  "
        "POC        VAL        VAH      Breite  B/ATR  Vol        Streu  eint",
        "  " + "-" * 126,
    ]
    for i in ergebnis.instanzen:
        marke = (
            "zu klein" if i.zu_klein
            else ("Rand" if i.angeschnitten else "ja")
        )
        zeilen.append(
            f"  {i.id:<4d} {i.territorium_id:<5d} {i.rang:<5d} "
            f"{i.bar_start:5d}..{i.bar_ende:<5d} "
            f"{i.ts_start:%Y-%m-%d %H:%M} .. {i.ts_ende:%m-%d %H:%M} "
            f"{i.n_bars:4d} {i.n_fenster:4d}  {i.poc:9.3f} {i.val:9.3f} "
            f"{i.vah:9.3f} {i.breite:7.3f} "
            f"{('-' if not np.isfinite(i.breite_atr) else f'{i.breite_atr:.2f}'):>6} "
            f"{i.vol:10.1f} "
            f"{('-' if not np.isfinite(i.konsens.streu_atr) else f'{i.konsens.streu_atr:.2f}'):>5} "
            f"{'ja' if i.konsens.eindeutig else 'NEIN':>5}  {marke}"
        )

    nester = ergebnis.nester
    zeilen.append("")
    zeilen.append("NESTER - ZUSAMMENFASSUNG:")
    zeilen.append(
        f"  Territorien: {ergebnis.n_territorien} (= Zahl der Nester, 1:1) | "
        f"davon ueber eine Fenstergrenze verschmolzen: "
        f"{ergebnis.n_verschmolzen} | Territorien mit mehr als einem Nest: "
        f"{ergebnis.n_mehrfach} (strukturell 0 - Kontrollwert)"
    )
    zeilen.append(
        f"  Laeufe roh: {ergebnis.n_laeufe_roh} | Nester (gueltig): "
        f"{len(nester)} | Flimmer-Laeufe: {ergebnis.n_zu_klein} | "
        f"angeschnitten (Rand): {ergebnis.n_angeschnitten}"
    )
    if nester:
        dauer = np.array([i.dauer_stunden for i in nester], dtype=float)
        bars = np.array([i.n_bars for i in nester], dtype=float)
        breite = np.array(
            [i.breite_atr for i in nester if np.isfinite(i.breite_atr)], dtype=float
        )
        n_eind = sum(1 for i in nester if i.konsens.eindeutig)
        zeilen.append(
            f"  Dauer: median={np.median(dauer):.1f} h p90="
            f"{np.percentile(dauer, 90):.1f} h max={dauer.max():.1f} h | "
            f"Bars je Nest: median={np.median(bars):.0f} max={bars.max():.0f}"
        )
        if breite.size:
            zeilen.append(
                f"  Nestbreite (eigene Value Area): median={np.median(breite):.2f} "
                f"ATR min={breite.min():.2f} max={breite.max():.2f} ATR"
            )
        zeilen.append(
            f"  POC eindeutig (gegenueber dem Rasterschritt): {n_eind} von "
            f"{len(nester)} ({100.0 * n_eind / len(nester):.1f} %)"
        )
    return zeilen


def _atr_liste(werte: Sequence[float]) -> str:
    """Formatiert ATR-Breiten als Kurzliste (``-`` fuer unbestimmt).

    Args:
        werte: Breiten in ATR.

    Returns:
        Mit ``+`` verbundene Werte mit einer Nachkommastelle; leer -> ``-``.
    """
    if not werte:
        return "-"
    return "+".join(
        "-" if not np.isfinite(w) else f"{w:.1f}" for w in werte
    )


def _separation_zeilen(
    config: VolumeProfilConfig, gueltig: Sequence[FensterProfil]
) -> List[str]:
    """Baut den Reportabschnitt "Separation der Bereiche".

    Er zerlegt jedes Fenster in die getrennten Bereiche je Segment und die
    Luecken dazwischen (``zerlege_bereiche``) - es wird nichts neu gerechnet,
    die Bereiche sind die Value Areas der bereits erkannten Segmente.

    Args:
        config: Laufkonfiguration (va_pct geht in die Bereichsweite ein).
        gueltig: Fenster mit Profil.

    Returns:
        Zeilen des Abschnitts (ohne fuehrende Leerzeile).
    """
    zeilen: List[str] = [
        "SEPARATION DER BEREICHE (je Segment seine eigene Value Area):",
        f"  Bereich = Value Area EINES Segmentes (VAL..VAH, Anteil va_pct="
        f"{config.va_pct:g} am Bergvolumen).",
        "  LUECKE  = Zwischenraum zweier benachbarter Bereiche - dort traegt "
        "kein Segment Volumen, dort laufen die schnellen Moves.",
        "  Label                | Ber | Bereichsbreiten ATR (Rang)  | Luecken | "
        "Lueckenbreiten ATR (Preis)  | Vol. in Ber | ausserhalb",
        "  " + "-" * 126,
    ]
    n_bereiche: List[float] = []
    breiten_alle: List[float] = []
    breiten_je_fenster: List[float] = []
    luecken_breiten: List[float] = []
    luecken_je_fenster: List[float] = []
    anteile: List[float] = []
    aussen: List[float] = []
    n_mit_luecke = 0
    for p in gueltig:
        sep = zerlege_bereiche(p.segmentierung, p.atr)
        offene = [l for l in sep.luecken if l.breite > 0.0]
        if offene:
            n_mit_luecke += 1
        n_bereiche.append(float(sep.n_bereiche))
        breiten_alle.extend(
            b.breite_atr for b in sep.bereiche if np.isfinite(b.breite_atr)
        )
        if np.isfinite(sep.breite_bereiche_atr):
            breiten_je_fenster.append(sep.breite_bereiche_atr)
        luecken_breiten.extend(
            l.breite_atr for l in offene if np.isfinite(l.breite_atr)
        )
        # Die Summe je Fenster wird nur fuer Fenster MIT Luecke gesammelt:
        # sonst stuenden lauter Nullen darin und der Median sagte nichts.
        if offene and np.isfinite(sep.breite_luecken_atr):
            luecken_je_fenster.append(sep.breite_luecken_atr)
        if np.isfinite(sep.anteil_bereiche):
            anteile.append(sep.anteil_bereiche)
        if np.isfinite(sep.anteil_ausserhalb):
            aussen.append(sep.anteil_ausserhalb)
        zeilen.append(
            f"  {p.label:<20} | {sep.n_bereiche:3d} | "
            f"{_atr_liste([b.breite_atr for b in sep.bereiche]):<26} | "
            f"{len(offene):7d} | "
            f"{_atr_liste([l.breite_atr for l in offene]):<26} | "
            f"{('-' if not np.isfinite(sep.anteil_bereiche) else f'{sep.anteil_bereiche:.3f}'):>11} | "
            f"{('-' if not np.isfinite(sep.anteil_ausserhalb) else f'{sep.anteil_ausserhalb:.3f}'):>9}"
        )

    n = len(gueltig)
    zeilen.append("")
    zeilen.append("SEPARATION - ZUSAMMENFASSUNG:")
    if n_bereiche:
        nb = np.array(n_bereiche, dtype=float)
        zeilen.append(
            f"  Bereiche je Fenster: median={np.median(nb):.0f} min={nb.min():.0f} "
            f"max={nb.max():.0f} | gesamt {int(nb.sum())}"
        )
        zeilen.append(
            f"  Fenster mit mehr als einem Bereich: {n_mit_luecke} von {n} "
            f"({100.0 * n_mit_luecke / max(1, n):.1f} %) - nur diese tragen "
            f"eine Luecke"
        )
    if breiten_alle:
        ba = np.array(breiten_alle, dtype=float)
        bf = np.array(breiten_je_fenster, dtype=float)
        zeilen.append(
            f"  Bereichsbreite: median={np.median(ba):.2f} ATR "
            f"min={ba.min():.2f} max={ba.max():.2f} | Summe je Fenster "
            f"median={np.median(bf):.2f} ATR"
        )
    if luecken_breiten:
        lb = np.array(luecken_breiten, dtype=float)
        lf = np.array(luecken_je_fenster, dtype=float)
        zeilen.append(
            f"  Lueckenbreite (nur Fenster mit >1 Bereich, {lb.size} Luecken): "
            f"median={np.median(lb):.2f} ATR min={lb.min():.2f} "
            f"max={lb.max():.2f} | Summe je Fenster median={np.median(lf):.2f} ATR"
        )
    if anteile:
        aa = np.array(anteile, dtype=float)
        au = np.array(aussen, dtype=float)
        zeilen.append(
            f"  Volumen in den Bereichen: median={np.median(aa):.4f} "
            f"min={aa.min():.4f} max={aa.max():.4f}"
        )
        zeilen.append(
            f"  Volumen ausserhalb (Luecken + Bergflanken 1-va_pct): "
            f"median={np.median(au):.4f} min={au.min():.4f} max={au.max():.4f}"
        )
        zeilen.append(
            "    Kleinerer Wert va_pct -> schmalere Bereiche und groesserer "
            "Anteil ausserhalb: das trennt benachbarte Nester deutlicher."
        )
    return zeilen


def report_text(
    config: VolumeProfilConfig,
    profile: Sequence[FensterProfil],
    n_verworfen: int,
    nester: Optional[NestErgebnis] = None,
) -> str:
    """Baut den TXT-Report des Laufs.

    Args:
        config: Laufkonfiguration.
        profile: Fensterprofile.
        n_verworfen: Anzahl wegen ``min_bars`` verworfener Fenster.
        nester: Ergebnis der Nest-Erkennung; None = kein Abschnitt (der Lauf
            wurde ohne diese Schicht gerechnet).

    Returns:
        Reporttext als String.
    """
    gueltig = [p for p in profile if p.gueltig]
    band_leer = band_von(None, config.modus)
    band_name = band_leer.name
    titel = "VOLUMENPROFILE - FENSTERWEISE (POC / ZONEN-VA 94 % / SEGMENTE)"
    linie = "=" * 130
    txt: List[str] = [
        linie,
        titel,
        f"Hauptband: {config.modus} = {band_name}",
        f"Abdeckung: {band_leer.abdeckung_name}",
    ]
    txt += [
        f"Instrument: {config.symbol} {config.timeframe} | Zeitraum: "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"Fensterart: {config.window_kind} | Mindest-Belegung "
        f"{effektive_min_bars(config)} Bars"
        f"{'' if config.min_bars is not None else f' (abgeleitet, min_abdeckung={config.min_abdeckung})'}"
        f" | Verwurf: {'an (Schwelle ' + str(wirksame_min_bars(config)) + ' Bars)' if verwurf_aktiv(config) else 'AUS - unvollstaendige Fenster bleiben'}"
        f" | Fenster gesamt {len(profile) + n_verworfen} | ausgewertet "
        f"{len(profile)} | verworfen {n_verworfen}",
        f"Profil: bins={config.num_bins} smooth={config.smooth_win} "
        f"va_pct={config.va_pct} (Berg-VA) va_zone_pct={config.va_zone_pct} "
        f"(Gesamt-VA ab POC) valley_rel={config.valley_rel} "
        f"min_mountain_pct={config.min_mountain_pct}",
        f"Segmentzahl-Treiber: valley_rel={config.valley_rel} (Talschwelle) - "
        f"groesser = mehr Berge/POCs, kleiner = weniger; "
        f"Gegenprobe min_mountain_pct={config.min_mountain_pct} "
        f"(verwirft nur kleine Berge)",
        f"Bereiche: JEDES Segment traegt seinen eigenen Bereich (VAL..VAH); "
        f"die Luecke zwischen zwei Bereichen traegt kein Volumen - dort laufen "
        f"die schnellen Moves. Bereichsweite ueber va_pct={config.va_pct:g}",
        f"Volumenfilter: vol_min={config.vol_min} vol_quantil={config.vol_quantil} "
        f"(wirkt auf das Profil, nicht auf die Zahl der Berge)",
        f"POC-Unsicherheit: Toleranz={config.streu_toleranz_atr} ATR ueber "
        f"bins={list(config.konsens_bins)} x smooth={list(config.konsens_smooth)}",
        f"Nester (ueber Fenstergrenzen): Raster={config.nest_schritt_atr} ATR | "
        f"Link-Toleranz={config.nest_link_toleranz_atr} ATR | "
        f"Level-Toleranz={config.nest_link_level_atr} ATR POC-Abstand | "
        f"Mindestgroesse "
        f"{config.nest_min_bars} Bars / {config.nest_min_anteil_pct} % | "
        f"Konsens k={list(config.nest_konsens_k)} x "
        f"smooth={list(config.nest_konsens_smooth)} | "
        f"Toleranz={config.nest_streu_toleranz_atr} ATR",
        f"Parameter (Abweichung vom Default): {_parameter_txt(config) or 'keine'}",
        linie,
        "",
        "FENSTER (BKZ, Bar-Indizes aus dem Gesamt-DataFrame):",
        "  Label                | bars  |   POC      VAL      VAH    | Breite | "
        "B/ATR | Seg | lobe2 | Streu | eindeutig",
        "  " + "-" * 126,
    ]
    for p in profile:
        seg = p.segmentierung
        band = hauptband(p, config)
        if seg is None or not (np.isfinite(band.val) and np.isfinite(band.vah)):
            txt.append(
                f"  {p.label:<20} | {p.n_bars:5d} | "
                f"{'(kein Profil - zu wenig Bars?)':>46}"
            )
            continue
        breite = band.breite
        b_atr = breite / p.atr if p.atr > 0 else float("nan")
        txt.append(
            f"  {p.label:<20} | {p.n_bars:5d} | {band.poc:8.3f} {band.val:8.3f} "
            f"{band.vah:8.3f} | {breite:6.3f} | "
            f"{('-' if not np.isfinite(b_atr) else f'{b_atr:.2f}'):>5} | "
            f"{seg.n_segmente:3d} | "
            f"{('-' if not np.isfinite(seg.lobe2_ratio) else f'{seg.lobe2_ratio:.3f}'):>5} | "
            f"{('-' if not np.isfinite(p.konsens.streu_atr) else f'{p.konsens.streu_atr:.2f}'):>5} | "
            f"{'ja' if p.konsens.eindeutig else 'NEIN':>7}"
        )
    txt.append("")
    if nester is not None:
        # Die Nest-Schicht liegt ueber den Fenstern (sie verbindet sie) - sie
        # wird deshalb auch gerechnet, wenn kein einzelnes Fenster gueltig war.
        txt += _nest_abschnitt(nester, config)
        txt.append("")
    if gueltig:
        txt += _separation_zeilen(config, gueltig)
        abdeck = np.array(
            [b.abdeckung for b in (hauptband(p, config) for p in gueltig)
             if np.isfinite(b.abdeckung)], dtype=float
        )
        seg_n = np.array([p.segmentierung.n_segmente for p in gueltig], dtype=float)
        st = np.array(
            [p.konsens.streu_atr for p in gueltig if np.isfinite(p.konsens.streu_atr)],
            dtype=float,
        )
        txt.append("ZUSAMMENFASSUNG:")
        txt.append(
            f"  Fenster mit Profil: {len(gueltig)} von {len(profile)} "
            f"({100.0 * len(gueltig) / max(1, len(profile)):.1f} %)"
        )
        txt.append(
            f"  Segmente je Fenster: median={np.median(seg_n):.0f} "
            f"min={seg_n.min():.0f} max={seg_n.max():.0f} "
            f"| Summe={int(seg_n.sum())}"
        )
        n_mehr = int((seg_n > 1).sum())
        txt.append(
            f"  Fenster mit mehr als 1 Segment: {n_mehr} von {len(gueltig)} "
            f"({100.0 * n_mehr / len(gueltig):.1f} %) - nur diese Fenster "
            f"tragen mehr als einen POC"
        )
        if abdeck.size:
            txt.append(
                f"  Abdeckung ({config.modus}): {band_leer.abdeckung_name} | "
                f"median={np.median(abdeck):.4f} "
                f"min={abdeck.min():.4f} max={abdeck.max():.4f}"
            )
        if st.size:
            n_eind = int(sum(1 for p in gueltig if p.konsens.eindeutig))
            txt.append(
                f"  POC eindeutig: {n_eind} von {len(gueltig)} "
                f"({100.0 * n_eind / len(gueltig):.1f} %) | Streuung "
                f"median={np.median(st):.2f} p90={np.percentile(st, 90):.2f} "
                f"max={st.max():.2f} ATR"
            )
    txt.append(linie)
    return "\n".join(txt) + "\n"


def tsv_levels(config: VolumeProfilConfig, profile: Sequence[FensterProfil]) -> str:
    """Maschinenlesbarer Level-Block (je Segment eine Zeile).

    Args:
        config: Laufkonfiguration.
        profile: Fensterprofile.

    Returns:
        TSV-Text (Kommentarzeilen, Header, Datenzeilen).
    """
    rolle = "ZONE"
    rolle_txt = "ZONE = Zonen-Value-Area ab POC"
    kopf: List[str] = [
        f"# volume_profile Level - {config.symbol} {config.timeframe} | "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"# Fensterart={config.window_kind} "
        f"mindest_belegung={effektive_min_bars(config)} "
        f"verwurf={'an:' + str(wirksame_min_bars(config)) if verwurf_aktiv(config) else 'aus'} "
        f"bins={config.num_bins} "
        f"smooth={config.smooth_win} va_pct={config.va_pct} "
        f"va_zone_pct={config.va_zone_pct} modus={config.modus}",
        f"# rolle: {rolle_txt} | SEGMENT = einzelner Volumen-Berg",
        f"# Segmentzahl-Treiber: valley_rel={config.valley_rel} (groesser = mehr "
        f"Berge/POCs, kleiner = weniger); min_mountain_pct="
        f"{config.min_mountain_pct} verwirft nur kleine Berge",
        f"# va_abdeckung: {band_von(None, config.modus).abdeckung_name}",
        "# atr: mittlere Bar-Spanne (high-low) des Fensters",
        "# poc_streu: POC-Spanne ueber die Konsens-Parametersaetze, in ATR",
        "label\twindow_kind\tbar_start\tbar_ende\tts_start\tts_ende\tn_bars\t"
        "n_bars_gefiltert\tvol_summe\tatr\tva_zone_pct\tva_abdeckung\t"
        "poc_streu\tpoc_min\tpoc_max\tpoc_eindeutig\tlobe2\trolle\trank\t"
        "poc\tval\tvah\tbreite\tvol\tpeak_share_pct",
    ]
    zeilen: List[str] = list(kopf)
    for p in profile:
        seg = p.segmentierung
        band = hauptband(p, config)
        if seg is None or not (np.isfinite(band.val) and np.isfinite(band.vah)):
            continue
        basis = (
            f"{p.label}\t{p.window_kind}\t{p.bar_start}\t{p.bar_ende}\t"
            f"{p.ts_start:%Y-%m-%d %H:%M:%S}\t{p.ts_ende:%Y-%m-%d %H:%M:%S}\t"
            f"{p.n_bars}\t{seg.n_bars_gefiltert}\t{p.vol_summe:.1f}\t"
            f"{p.atr:.5f}\t{config.va_zone_pct:.4f}\t{band.abdeckung:.6f}\t"
            f"{p.konsens.streu_atr:.4f}\t{p.konsens.poc_min:.5f}\t"
            f"{p.konsens.poc_max:.5f}\t{int(p.konsens.eindeutig)}\t"
            f"{seg.lobe2_ratio:.4f}"
        )
        zeilen.append(
            f"{basis}\t{rolle}\t-1\t{band.poc:.5f}\t{band.val:.5f}\t"
            f"{band.vah:.5f}\t{band.breite:.5f}\t\t"
        )
        for rank, nest in enumerate(seg.nester):
            zeilen.append(
                f"{basis}\tSEGMENT\t{rank}\t{nest.poc:.5f}\t{nest.val:.5f}\t"
                f"{nest.vah:.5f}\t{nest.vah - nest.val:.5f}\t{nest.vol:.1f}\t"
                f"{nest.peak_share_pct:.2f}"
            )
    return "\n".join(zeilen) + "\n"


def tsv_nester(config: VolumeProfilConfig, ergebnis: NestErgebnis) -> str:
    """Maschinenlesbarer Nest-Block (Territorien und Nester in EINEM Schema).

    Beide Ebenen stehen in derselben Tabelle (Spalte ``rolle``): ``TERRITORIUM``
    traegt die Zone des Knotens, ``NEST`` den zusammenhaengenden Lauf mit seinen
    eigenen Leveln. Nicht zutreffende Spalten bleiben leer - damit ist die Datei
    fuer eine spaetere statistische Auswertung direkt einlesbar, ohne zwei
    Blaetter verbinden zu muessen.

    Args:
        config: Laufkonfiguration.
        ergebnis: Ergebnis der Nest-Erkennung.

    Returns:
        TSV-Text (Kommentarzeilen, Header, Datenzeilen).
    """
    kopf: List[str] = [
        f"# volume_profile Nester - {config.symbol} {config.timeframe} | "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"# Fensterart={config.window_kind} modus={config.modus} | "
        f"Raster={config.nest_schritt_atr} ATR "
        f"link={config.nest_link_toleranz_atr} ATR "
        f"link_level={config.nest_link_level_atr} ATR "
        f"min_bars={config.nest_min_bars} "
        f"min_anteil_pct={config.nest_min_anteil_pct} | "
        f"Konsens k={list(config.nest_konsens_k)} x "
        f"smooth={list(config.nest_konsens_smooth)} "
        f"Toleranz={config.nest_streu_toleranz_atr} ATR | "
        f"Erkennung: {_pad_txt(config)}",
        "# rolle: TERRITORIUM = Kette gepaarter Berge (Knoten als Zone ueber die "
        "Zeit) | NEST = zusammenhaengender Lauf darin (eigenes POC/VAL/VAH). "
        "EIN Territorium traegt GENAU EINEN Lauf (1:1) - rang ist daher immer 0.",
        "# Paarung zweier Berge: Kerne ueberlappen im Preis UND POC-Abstand <= "
        "link_level (sonst waeren es zwei Knoten bzw. eine Rueckkehr).",
        "# bar_start/bar_ende/ts_start/ts_ende: Bereich des Knotens bzw. Laufs im "
        "geladenen Zeitraum (Bar-Index = Primaerschluessel, K5)",
        "# angeschnitten=1: Lauf endet am Zeitraumrand (kann weiterlaufen). "
        "zu_klein=1: Flimmer-Lauf. Beide gehen NICHT in die Statistik ein.",
        "# breite_atr: Value-Area-Breite in ATR der EIGENEN Lebensdauer | "
        "poc_streu: POC-Spanne ueber die Rasterschritte, in ATR",
    ]
    spalten: Tuple[str, ...] = (
        "rolle", "id", "territorium_id", "rang", "bar_start", "bar_ende",
        "ts_start", "ts_ende", "n_bars", "n_fenster", "poc", "val", "vah",
        "breite", "breite_atr", "vol", "atr", "raster_bins", "raster_schritt",
        "unten", "oben", "kern_unten", "kern_oben", "n_berge", "verschmolzen",
        "labels", "zu_klein", "angeschnitten", "poc_streu", "poc_min",
        "poc_max", "poc_eindeutig",
    )

    def _f(v: float) -> str:
        return "" if not np.isfinite(v) else f"{v:.5f}"

    def _zeile(werte: Dict[str, str]) -> str:
        zeile = "\t".join(werte.get(s, "") for s in spalten)
        # Selbstpruefung: die Spaltenzahl muss zum Kopf passen, sonst ist die
        # Datei fuer eine spaetere Auswertung stillschweigend verschoben.
        assert len(zeile.split("\t")) == len(spalten), "TSV-Spalten verschoben"
        return zeile

    zeilen: List[str] = list(kopf)
    zeilen.append("\t".join(spalten))
    for t in sorted(ergebnis.territorien, key=lambda x: int(x.bar_start)):
        zeilen.append(_zeile({
            "rolle": "TERRITORIUM", "id": str(t.id),
            "bar_start": str(t.bar_start), "bar_ende": str(t.bar_ende),
            "n_fenster": str(t.n_fenster),
            "unten": _f(t.unten), "oben": _f(t.oben),
            "kern_unten": _f(t.kern_unten), "kern_oben": _f(t.kern_oben),
            "n_berge": str(t.n_berge), "verschmolzen": str(int(t.verschmolzen)),
            "labels": "+".join(t.labels),
        }))
    for i in sorted(ergebnis.instanzen, key=lambda x: int(x.bar_start)):
        zeilen.append(_zeile({
            "rolle": "NEST", "id": str(i.id),
            "territorium_id": str(i.territorium_id), "rang": str(i.rang),
            "bar_start": str(i.bar_start), "bar_ende": str(i.bar_ende),
            "ts_start": f"{i.ts_start:%Y-%m-%d %H:%M:%S}",
            "ts_ende": f"{i.ts_ende:%Y-%m-%d %H:%M:%S}",
            "n_bars": str(i.n_bars), "n_fenster": str(i.n_fenster),
            "poc": f"{i.poc:.5f}", "val": f"{i.val:.5f}", "vah": f"{i.vah:.5f}",
            "breite": f"{i.breite:.5f}", "breite_atr": _f(i.breite_atr),
            "vol": f"{i.vol:.1f}", "atr": _f(i.atr),
            "raster_bins": str(i.raster_bins),
            "raster_schritt": _f(i.raster_schritt),
            "zu_klein": str(int(i.zu_klein)),
            "angeschnitten": str(int(i.angeschnitten)),
            "poc_streu": _f(i.konsens.streu_atr),
            "poc_min": _f(i.konsens.poc_min),
            "poc_max": _f(i.konsens.poc_max),
            "poc_eindeutig": str(int(i.konsens.eindeutig)),
        }))
    return "\n".join(zeilen) + "\n"


# Profilbildende Parameter, die bei Abweichung vom Default in Dateiname und
# Charttitel wandern: (Feldname, Kuerzel im Dateinamen).
_ABWEICHUNGS_FELDER: Tuple[Tuple[str, str], ...] = (
    ("va_pct", "va"),
    ("va_zone_pct", "vaz"),
    ("num_bins", "bins"),
    ("smooth_win", "sm"),
    ("valley_rel", "val"),
    ("min_mountain_pct", "mm"),
    ("vol_quantil", "vq"),
    ("vol_min", "vmin"),
)

# Dasselbe fuer die Nestparameter: sie aendern die Territorien-/Nestzeilen
# (Raster, Link, Mindestgroesse, Polster) und duerfen deshalb ebenso wenig
# stillschweigend denselben Dateinamen treffen.
_NEST_ABWEICHUNGS_FELDER: Tuple[Tuple[str, str], ...] = (
    ("nest_schritt_atr", "nstep"),
    ("nest_link_toleranz_atr", "nlink"),
    ("nest_link_level_atr", "nlev"),
    ("nest_min_bars", "nmin"),
    ("nest_min_anteil_pct", "nanteil"),
    ("nest_pad_tage", "npad"),
)


def _abweichende_parameter(config: VolumeProfilConfig) -> List[Tuple[str, object]]:
    """Listet die profilbildenden Parameter, die vom Default abweichen.

    Args:
        config: Laufkonfiguration.

    Returns:
        Liste ``(Feldname, Wert)`` in Reihenfolge von ``_ABWEICHUNGS_FELDER``.
    """
    default = VolumeProfilConfig()
    return [
        (feld, getattr(config, feld))
        for feld, _kurz in _ABWEICHUNGS_FELDER
        if getattr(config, feld) != getattr(default, feld)
    ]


def _nest_abweichende_parameter(
    config: VolumeProfilConfig,
) -> List[Tuple[str, object]]:
    """Listet die vom Default abweichenden NESTparameter.

    Args:
        config: Laufkonfiguration.

    Returns:
        Liste ``(Feldname, Wert)`` in Reihenfolge von
        ``_NEST_ABWEICHUNGS_FELDER``.
    """
    default = VolumeProfilConfig()
    return [
        (feld, getattr(config, feld))
        for feld, _kurz in _NEST_ABWEICHUNGS_FELDER
        if getattr(config, feld) != getattr(default, feld)
    ]


def _parameter_suffix(config: VolumeProfilConfig) -> str:
    """Kurzer Dateiname-Zusatz fuer abweichende profilbildende Parameter.

    Ein Default-Lauf behaelt damit seinen gewohnten Namen; ein Probierlauf
    (z. B. ``--va_pct=0.70`` oder ``--nest_pad_tage=0``) legt eine eigene Datei
    an, statt den Default-Stand zu ueberschreiben - beide Ausgaben bleiben
    vergleichbar.

    Args:
        config: Laufkonfiguration.

    Returns:
        Zusatz wie ``_va0.7`` oder ``""``.
    """
    default = VolumeProfilConfig()
    teile: List[str] = []
    for feld, kurz in _ABWEICHUNGS_FELDER + _NEST_ABWEICHUNGS_FELDER:
        wert = getattr(config, feld)
        if wert != getattr(default, feld):
            teile.append(f"{kurz}{wert:g}")
    return "_" + "_".join(teile) if teile else ""


def _datei_stamm(config: VolumeProfilConfig) -> str:
    """Dateiname-Stamm der Ausgaben (ohne Endung).

    Entspricht ein profilbildender Parameter NICHT dem Default, wird er
    angehaengt (``_parameter_suffix``) - damit ueberschreibt ein Probierlauf
    (z. B. ``--va_pct=0.70``) nicht stillschweigend die Ausgabe des Defaults.

    Args:
        config: Laufkonfiguration.

    Returns:
        Stamm wie
        ``volume_profile_SILVER_M15_day_zone_2026-08-01_2026-09-01`` bzw. mit
        Zusatz ``..._va0.7``.
    """
    sym = "".join(ch for ch in config.symbol.upper() if ch.isalnum())
    return (
        f"volume_profile_{sym}_{config.timeframe}_{config.window_kind}_"
        f"{config.modus}_{config.start}_{config.ende}{_parameter_suffix(config)}"
    )


def _parameter_txt(config: VolumeProfilConfig) -> str:
    """Lesbarer Parameterzusatz fuer Charttitel und Reportkopf.

    Args:
        config: Laufkonfiguration.

    Returns:
        Text wie ``va_pct=0.7`` oder ``""``, wenn alles auf Default steht.
    """
    abw = _abweichende_parameter(config)
    abw_nest = _nest_abweichende_parameter(config)
    teile = [f"{feld}={wert:g}" for feld, wert in abw]
    teile += [f"{feld}={wert:g}" for feld, wert in abw_nest]
    return " ".join(teile)


# =============================================================================
# 3) MAIN
# =============================================================================


def _parse_cli(
    args: Sequence[str], config: VolumeProfilConfig
) -> VolumeProfilConfig:
    """Ueberschreibt Defaults aus ``--key=value``-Argumenten.

    Args:
        args: Argumentliste ohne Programmnamen.
        config: Startkonfiguration (Defaults).

    Returns:
        Angepasste Konfiguration.

    Raises:
        SystemExit: Bei unbekanntem Argument.
    """
    felder: Dict[str, object] = {}
    for a in args:
        if not a.startswith("--") or "=" not in a:
            continue
        key, val = a[2:].split("=", 1)
        key = key.strip().replace("-", "_")
        val = val.strip()
        if key in ("symbol", "timeframe", "start", "ende", "window", "window_kind",
                   "modus"):
            felder["window_kind" if key.startswith("window") else key] = val
        elif key in ("num_bins", "smooth_win", "min_bars", "dpi",
                     "grid_max_profile", "grid_seiten_max", "nest_min_bars",
                     "nest_pad_tage"):
            felder[key] = int(val)
        elif key in ("va_pct", "valley_rel", "min_mountain_pct", "va_zone_pct",
                     "vol_min", "vol_quantil", "streu_toleranz_atr",
                     "min_abdeckung", "nest_schritt_atr",
                     "nest_link_toleranz_atr", "nest_link_level_atr",
                     "nest_min_anteil_pct",
                     "nest_streu_toleranz_atr"):
            felder[key] = float(val)
        elif key in ("konsens_bins", "konsens_smooth"):
            felder[key] = tuple(
                int(t) for t in val.replace(";", ",").split(",") if t.strip()
            )
        elif key in ("nest_konsens_k",):
            felder[key] = tuple(
                float(t) for t in val.replace(";", ",").split(",") if t.strip()
            )
        elif key in ("nest_konsens_smooth",):
            felder[key] = tuple(
                int(t) for t in val.replace(";", ",").split(",") if t.strip()
            )
        elif key in ("unvollstaendige_verwerfen",):
            felder[key] = val.lower() in ("1", "true", "ja", "yes", "an", "on")
        elif key in ("db_path", "out_dir"):
            felder[key] = Path(val)
        else:
            raise SystemExit(f"Unbekanntes Argument: --{key}")
    return replace(config, **felder)  # type: ignore[arg-type]


def _validiere(config: VolumeProfilConfig) -> None:
    """Prueft die Laufkonfiguration auf offensichtliche Fehler.

    Args:
        config: Laufkonfiguration.

    Raises:
        SystemExit: Bei ungueltiger Konfiguration.
    """
    if config.window_kind not in FENSTER_ARTEN:
        raise SystemExit(
            f"Unbekannte Fensterart {config.window_kind!r}. Erlaubt: "
            f"{sorted(FENSTER_ARTEN)}"
        )
    if config.num_bins < 3:
        raise SystemExit("num_bins muss >= 3 sein.")
    if config.smooth_win < 1:
        raise SystemExit("smooth_win muss >= 1 sein.")
    if config.min_bars is not None and config.min_bars < 1:
        raise SystemExit("min_bars muss >= 1 sein (oder None = ableiten).")
    if not 0.0 < config.min_abdeckung <= 1.0:
        raise SystemExit("min_abdeckung muss im Intervall (0, 1] liegen.")
    if config.modus not in MODI:
        raise SystemExit(
            f"Unbekannter Modus {config.modus!r}. Erlaubt: {list(MODI)}."
        )
    if not 0.0 < config.va_pct < 1.0:
        raise SystemExit("va_pct muss im offenen Intervall (0, 1) liegen.")
    if not 0.0 < config.va_zone_pct <= 1.0:
        raise SystemExit("va_zone_pct muss im Intervall (0, 1] liegen.")
    if not 0.0 <= config.vol_quantil < 1.0:
        raise SystemExit("vol_quantil muss im Intervall [0, 1) liegen.")
    if config.streu_toleranz_atr < 0.0:
        raise SystemExit("streu_toleranz_atr muss >= 0 sein.")
    if config.nest_schritt_atr <= 0.0:
        raise SystemExit("nest_schritt_atr muss > 0 sein (Rasterschritt).")
    if config.nest_link_toleranz_atr < 0.0:
        raise SystemExit("nest_link_toleranz_atr muss >= 0 sein.")
    if config.nest_link_level_atr < 0.0:
        raise SystemExit("nest_link_level_atr muss >= 0 sein (0 = nur gleiche POCs).")
    if config.nest_min_bars < 1:
        raise SystemExit("nest_min_bars muss >= 1 sein.")
    if config.nest_min_anteil_pct < 0.0:
        raise SystemExit("nest_min_anteil_pct muss >= 0 sein.")
    if not config.nest_konsens_k:
        raise SystemExit("nest_konsens_k darf nicht leer sein (Rasterschritte).")
    if config.nest_pad_tage < 0:
        raise SystemExit("nest_pad_tage muss >= 0 sein (0 = kein Polster).")
    if config.start >= config.ende:
        raise SystemExit(
            f"Leerer Zeitraum: start={config.start} muss < ende={config.ende} sein."
        )


def _store_parameter(config: VolumeProfilConfig) -> Dict[str, object]:
    """Bildet die Parameter, die in die ``run_id`` des Speichers eingehen.

    ``modus`` gehoert bewusst NICHT dazu: er ist reine Auswahl des Hauptbandes
    bei Meldung und Zeichnung (es gibt nur ``zone``) und darf deshalb keinen
    zweiten Speicher mit identischen Zahlen anlegen. Die HUELLKANTEN
    (``val_huelle``/``vah_huelle``) werden ohnehin in jeder Profilzeile
    gehalten.

    Args:
        config: Laufkonfiguration.

    Returns:
        Parameterdict (Volumenparameter + Fensterart + Verwurf + Konsens +
        Nestparameter + Zeitraum). ``min_bars`` ist die abgeleitete Belegung,
        ``min_bars_angewendet`` die tatsaechliche Verwurfschwelle - beide
        gehen ein, damit ein Lauf mit und ohne Verwurf nicht denselben
        Speicher trifft.
    """
    return {
        **asdict(_profil_parameter(config)),
        "window_kind": config.window_kind,
        "min_bars": effektive_min_bars(config),
        "min_bars_angewendet": wirksame_min_bars(config),
        "unvollstaendige_verwerfen": bool(config.unvollstaendige_verwerfen),
        "konsens_bins": list(config.konsens_bins),
        "konsens_smooth": list(config.konsens_smooth),
        "streu_toleranz_atr": config.streu_toleranz_atr,
        # Die Nestparameter formen die Territorien-/Nestzeilen mit: ein Lauf
        # mit anderem Raster/Link/Mindestgroesse ist ein anderer Parametersatz.
        "nest_schritt_atr": config.nest_schritt_atr,
        "nest_link_toleranz_atr": config.nest_link_toleranz_atr,
        "nest_link_level_atr": config.nest_link_level_atr,
        "nest_min_bars": config.nest_min_bars,
        "nest_min_anteil_pct": config.nest_min_anteil_pct,
        "nest_konsens_k": list(config.nest_konsens_k),
        "nest_konsens_smooth": list(config.nest_konsens_smooth),
        "nest_streu_toleranz_atr": config.nest_streu_toleranz_atr,
        "nest_pad_tage": int(config.nest_pad_tage),
        "timeframe": config.timeframe,
        "start": config.start,
        "ende": config.ende,
    }


def main(
    argv: Optional[Sequence[str]] = None,
    config: Optional[VolumeProfilConfig] = None,
) -> int:
    """CLI-Einstieg: rechnet Fensterprofile, haelt sie und zeichnet.

    Der Laufzeitspeicher wird ueber den prozessweiten Halter besorgt und mit
    den Zeilen dieses Laufs gefuellt - die Profile gelten nur fuer DIESEN
    Parametersatz und werden nirgends abgelegt (es gibt keine DB-Ablage).

    Args:
        argv: Argumentliste (Default: ``sys.argv[1:]``).
        config: Fertige Konfiguration; None = aus ``argv`` bilden.

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    if config is None:
        args = list(sys.argv[1:] if argv is None else argv)
        config = _parse_cli(args, VolumeProfilConfig())
    _validiere(config)

    df: pd.DataFrame = load_data(
        config.db_path, config.start, config.ende, config.symbol, config.timeframe
    )
    if df.empty:
        raise SystemExit(
            f"Keine Bars fuer {config.symbol} {config.timeframe} "
            f"in {config.start} .. {config.ende}."
        )

    profile, n_verworfen = rechne_fensterprofile(df, config)
    if not any(p.gueltig for p in profile):
        raise SystemExit(
            f"Kein Fenster ergab ein Profil. min_bars senken "
            f"(derzeit {effektive_min_bars(config)}, min_abdeckung="
            f"{config.min_abdeckung}), Zeitraum vergroessern oder einen "
            f"Intraday-Timeframe waehlen."
        )

    # --- Laufzeit-Speicher (kein Ablegen; Zuordnung ueber run_id) -----------
    store_params = _store_parameter(config)
    zeilen, nests = _speicher_zeilen(profile, config)
    # Bereiche und Luecken gehen mit in denselben Speicher: sie sind die
    # Datengrundlage der Separation-Statistik (gleicher Parametersatz, gleiche
    # run_id - va_pct steckt in den Parametern).
    bereich_zeilen, luecke_zeilen = _bereich_zeilen(profile)
    # Nester ueber Fenstergrenzen: die Schicht verbindet die Fenster (Kette
    # gepaarter Berge -> zusammenhaengender Lauf). Sie rechnet NICHTS neu, sie
    # benutzt die Berge der Fenster und die eingefrorene Volumenlogik.
    nest_ergebnis = nest_lauf(df, profile, config)
    territorium_zeilen, nestobjekt_zeilen = _nest_zeilen(nest_ergebnis)
    speicher = HALTER.hole_oder_anlegen(
        config.symbol, config.timeframe, config.window_kind, store_params
    )
    n_gehalten = speicher.merke(
        zeilen, nests, bereich_zeilen, luecke_zeilen,
        territorium_zeilen, nestobjekt_zeilen,
    )
    stand = speicher.zaehle()
    halter_stand = HALTER.zaehle()
    speicher_zeile = (
        f"Laufzeitspeicher: run_id={speicher.run_id}, "
        f"{n_gehalten} Profile, {stand['nests']} Segmente, "
        f"{stand['bereiche']} Bereiche, {stand['luecken']} Luecken, "
        f"{stand['territorien']} Territorien, "
        f"{stand['nestobjekte']} Nester gehalten, "
        f"{speicher.speicher_mb():.2f} MB | Halter: "
        f"{len(HALTER)} Parametersatz/Parametersaetze, "
        f"{halter_stand['profiles']} Profile gesamt, "
        f"{HALTER.speicher_mb():.2f} MB"
    )

    # --- Ausgabe -----------------------------------------------------------
    config.out_dir.mkdir(parents=True, exist_ok=True)
    stamm = _datei_stamm(config)
    (config.out_dir / f"{stamm}.txt").write_text(
        report_text(config, profile, n_verworfen, nest_ergebnis), encoding="utf-8"
    )
    (config.out_dir / f"{stamm}_levels.tsv").write_text(
        tsv_levels(config, profile), encoding="utf-8"
    )
    # Die Nester als eigene Tabelle (ein Schema, zwei Ebenen) - Grundlage einer
    # spaeteren statistischen Auswertung der Nester selbst.
    (config.out_dir / f"{stamm}_nester.tsv").write_text(
        tsv_nester(config, nest_ergebnis), encoding="utf-8"
    )
    stil = ChartStil(
        dpi=config.dpi,
        titel_symbol=config.symbol,
        titel_timeframe=config.timeframe,
        zeitraum=f"{config.start} .. {config.ende} (ende-exkl., BKZ)",
        max_profile=config.grid_max_profile,
        seiten_max=config.grid_seiten_max,
        # Bereichsweite kommt aus dem Kern (va_pct) - das Chart rechnet sie
        # nicht nach, muss sie aber benennen (Titel/Statistik/Legende).
        bereich_va_pct=config.va_pct,
        parameter_txt=_parameter_txt(config),
        modus=config.modus,
    )
    p_zone, p_grids = zeichne_alles(
        df, profile, stil, config.out_dir / stamm, nester=nest_ergebnis.instanzen
    )

    gueltig = [p for p in profile if p.gueltig]
    n_unsicher = sum(1 for p in gueltig if not p.konsens.eindeutig)
    # Der Verwurf-Status gehoert in die Konsole: die Zahl der ausgewerteten
    # Fenster ist ohne ihn nicht deutbar (Belegung vs. tatsaechliche Schwelle).
    verwurf_txt = (
        f"an (Schwelle {wirksame_min_bars(config)} Bars)"
        if verwurf_aktiv(config)
        else "AUS - unvollstaendige Fenster bleiben"
    )
    print(
        f"Fensterart {config.window_kind} | Modus {config.modus}: "
        f"{len(gueltig)} Profile aus "
        f"{len(profile)} ausgewerteten Fenstern ({n_verworfen} verworfen) | "
        f"Mindest-Belegung {effektive_min_bars(config)} Bars | "
        f"Verwurf {verwurf_txt} | POC unsicher: {n_unsicher}"
    )
    if speicher_zeile:
        print(speicher_zeile)
    print(_nest_text(nest_ergebnis, config))
    bereiche = [zerlege_bereiche(p.segmentierung, p.atr) for p in gueltig]
    if bereiche:
        n_b = [b.n_bereiche for b in bereiche]
        aussen = [b.anteil_ausserhalb for b in bereiche
                  if np.isfinite(b.anteil_ausserhalb)]
        b_atr = [b.breite_bereiche_atr for b in bereiche
                 if np.isfinite(b.breite_bereiche_atr)]
        print(
            f"Bereiche (je Segment eigene VA): median {np.median(n_b):.0f} je "
            f"Fenster ({int(sum(n_b))} gesamt) | Summe Bereichsbreiten je Fenster "
            f"median {np.median(b_atr) if b_atr else float('nan'):.2f} ATR | "
            f"Volumen ausserhalb (Luecken + Bergflanken) median "
            f"{np.median(aussen) if aussen else float('nan'):.3f}"
        )
    print(f"Ausgabe: {config.out_dir / (stamm + '.txt')}")
    print(f"         {config.out_dir / (stamm + '_levels.tsv')}")
    print(f"         {config.out_dir / (stamm + '_nester.tsv')}")
    if p_zone:
        print(f"         {p_zone}")
    for g in p_grids:
        print(f"         {g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
