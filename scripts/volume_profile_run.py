"""
VOLUMENPROFIL-LAUF (scripts/volume_profile_run.py)
====================================================
Orchestrator: verbindet Daten -> Fenster -> Rechenkern -> Speicher -> Chart.
Dieses Modul enthaelt selbst KEINE Volumenlogik, KEINE Fensterbildung und
KEINE Zeichenroutine - es steuert nur die vier Bausteine:

    scripts.market_segmentation        Bars laden (BKZ-Garantie)
    scripts.volume_profile_windows     Fenster schneiden (day/week/h12/h4/h1/m30)
    scripts.volume_profile_core        POC/VAL/VAH + Segmente + POC-Streuung
    scripts.volume_profile_store       Laufzeit-Speicher (RAM) je Parametersatz
    scripts.volume_profile_chart       PNG-Ausgaben

Zwei Ebenen je Fenster
----------------------
    SEGMENTE   Berge/Nester aus ``find_mountains`` - die bewaehrte
               Segment-Erkennung, bleibt unveraendert erhalten.
    BAND       das Hauptband des Fensters: entweder die ZONEN-VA
               (symmetrische Value Area ab dem globalen POC, ``va_zone_pct`` =
               0,94 des Gesamtvolumens) oder das BALANCE-BAND (Huelle der
               Segment-Value-Areas, ``val_huelle .. vah_huelle``).

Modus (es gibt nur EINE Engine)
-------------------------------
BEIDE Baender werden immer mitgerechnet (sie stecken im Vertrag
``Segmentierung``); ``modus`` waehlt nur, welches Band als Hauptband gemeldet,
gehalten und gezeichnet wird:

    --modus=zone       Zonen-VA ab POC (Default)
    --modus=balance    Huelle der Segment-VAs - mit ``--window=day`` ist das
                       exakt der fruehere Tages-Balancen-Modus (POC/VAH/VAL
                       je Kalendertag).

Speicher
--------
Es gibt KEINE Datenbankablage der Profile. Die Profile werden zur Laufzeit
gehalten (``ProfilSpeicher``): ein Profil ist an seinen Parametersatz gebunden
und wird bei Parameteraenderung sofort ungueltig - eine Dateiablage waere dann
Altbestand, der stillschweigend weiterverwendet werden koennte.

Vergeben wird der Laufzeitspeicher vom prozessweiten Halter
(``volume_profile_store.HALTER``): ``hole_oder_anlegen`` liefert bei gleichem
Parametersatz denselben Speicher zurueck (nichts wird doppelt gerechnet), bei
geaendertem Parametersatz einen neuen. Damit steht der Live-Einsatz auf
derselben Mechanik wie der CLI-Lauf.

Mindest-Bars
------------
``min_bars`` wird standardmaessig AUS Fensterart und Timeframe ABGELEITET
(``min_bars_fuer``): gefordert ist ein Anteil ``min_abdeckung`` (Default 0,5)
der nominalen Fensterdauer. Damit wird auf jedem Timeframe dieselbe Groesse
untersucht (M15/day -> 48 Bars, H1/day -> 12 Bars, M15/h4 -> 8 Bars).

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Zeit kommt ausschliesslich als BKZ aus ``load_data`` (``time AT TIME ZONE
'UTC'``, tz-naiv) und wird als solche gehalten und beschriftet. Die
Fenstergrenzen werden dynamisch per ``searchsorted`` gebildet (K6); es gibt
keine Zeitzonen-Projektion (K2) und kein nacktes ``SELECT time`` (K4).

Aufruf (Projekt-Wurzel):
    python -m scripts.volume_profile_run
    python -m scripts.volume_profile_run --window=week --symbol=SILVER ^
        --timeframe=M15 --start=2026-06-01 --ende=2026-09-01
    python -m scripts.volume_profile_run --window=h4 --vol_quantil=0.05
    python -m scripts.volume_profile_run --window=day --modus=balance
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
)
from scripts.volume_profile_store import (  # noqa: E402
    HALTER,
    NestZeile,
    ProfilZeile,
)
from scripts.volume_profile_windows import (  # noqa: E402
    FENSTER_ARTEN,
    FensterSpec,
    baue_fenster,
    min_bars_fuer,
)

_ROOT: Path = Path(__file__).resolve().parent.parent


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
        min_bars: Mindestzahl Bars je Fenster. ``None`` (Default) = ABLEITEN
            aus Fensterart und Timeframe (siehe ``min_abdeckung``) - damit
            wird auf jedem Timeframe dieselbe Groesse untersucht.
        min_abdeckung: Anteil der nominalen Fensterdauer, der mindestens durch
            Bars belegt sein muss (Default 0,5 = halbes Fenster).
        num_bins: Anzahl Preis-Bins des Profils (Baseline ``NUM_BINS``).
        smooth_win: Glaettungsfenster des Volumens (Baseline ``SMOOTH_WIN``).
        modus: Hauptband des Laufs: ``zone`` (Zonen-VA ab POC, Default) oder
            ``balance`` (Huelle der Segment-VAs). Beide Baender werden immer
            mitgerechnet; der Modus wirkt nur auf Meldung, Speicherzeile und
            Zeichnung. ``balance`` + ``window_kind="day"`` = Tages-Balancen.
        va_pct: Value-Area-Anteil des Berg-Volumens (Baseline ``VA_PCT``).
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
    start: str = "2026-08-01"
    ende: str = "2026-09-01"
    db_path: Path = _ROOT / "data" / "market_data.duckdb"

    # --- Fenster ------------------------------------------------------------
    window_kind: str = "day"
    min_bars: Optional[int] = None
    min_abdeckung: float = 0.5

    # --- Volumenprofil (Baseline-Defaults + Zonen-VA) -----------------------
    num_bins: int = 60
    smooth_win: int = 3
    modus: str = "zone"
    va_pct: float = 0.93
    valley_rel: float = 0.15
    min_mountain_pct: float = 4.0
    va_zone_pct: float = 0.94
    vol_min: float = 0.0
    vol_quantil: float = 0.0

    # --- POC-Unsicherheit ---------------------------------------------------
    konsens_bins: Tuple[int, ...] = (30, 60, 120, 240)
    konsens_smooth: Tuple[int, ...] = (1, 3, 5, 9)
    streu_toleranz_atr: float = 1.0

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


def hauptband(p: FensterProfil, config: VolumeProfilConfig) -> Band:
    """Liefert das Hauptband eines Fensters im gewaehlten Modus.

    Es wird nur AUSGEWAEHLT, nicht gerechnet: beide Baender stecken bereits im
    Vertrag ``Segmentierung`` (``zone`` und ``val_huelle/vah_huelle``).

    Args:
        p: Fensterprofil.
        config: Laufkonfiguration (liefert ``modus``).

    Returns:
        ``Band`` des Modus; ohne Profil sind alle Kanten ``nan``.
    """
    return band_von(p.segmentierung, config.modus)


def effektive_min_bars(config: VolumeProfilConfig) -> int:
    """Liefert die wirksame Mindest-Bars-Zahl eines Laufs.

    Ist ``config.min_bars`` gesetzt, gilt dieser Wert. Sonst wird er aus
    Fensterart und Timeframe abgeleitet (``min_bars_fuer``): gefordert ist der
    Anteil ``min_abdeckung`` der NOMINALEN Fensterdauer, damit auf jedem
    Timeframe dieselbe Groesse untersucht wird.

    Args:
        config: Laufkonfiguration.

    Returns:
        Mindestzahl Bars je Fenster.
    """
    if config.min_bars is not None:
        return int(config.min_bars)
    return min_bars_fuer(config.window_kind, config.timeframe, config.min_abdeckung)


def rechne_fensterprofile(
    df: pd.DataFrame, config: VolumeProfilConfig
) -> Tuple[List[FensterProfil], int]:
    """Rechnet je Zeitfenster ein Volumenprofil.

    Fenster unter der wirksamen Mindest-Bars-Zahl werden uebersprungen (kurze/
    randstaendige Bloecke, z. B. Freitag-Nachmittag im H4-Raster). Die Zahl
    wird aus Fensterart und Timeframe abgeleitet, sofern ``min_bars`` nicht
    ausdruecklich gesetzt ist (``effektive_min_bars``).

    Args:
        df: Bars des Gesamtfensters (BKZ).
        config: Laufkonfiguration.

    Returns:
        ``(profile, n_verworfen)`` - chronologische Liste der ausgewerteten
        Fenster und Anzahl der wegen ``min_bars`` verworfenen Fenster.
    """
    par = _profil_parameter(config)
    kons = _konsens_parameter(config)
    min_bars = effektive_min_bars(config)
    spec = FensterSpec(art=config.window_kind, min_bars=min_bars)
    fenster = baue_fenster(df, spec)

    profile: List[FensterProfil] = []
    n_verworfen = 0
    for f in fenster:
        if f.n_bars < min_bars:
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


def report_text(
    config: VolumeProfilConfig, profile: Sequence[FensterProfil], n_verworfen: int
) -> str:
    """Baut den TXT-Report des Laufs.

    Args:
        config: Laufkonfiguration.
        profile: Fensterprofile.
        n_verworfen: Anzahl wegen ``min_bars`` verworfener Fenster.

    Returns:
        Reporttext als String.
    """
    gueltig = [p for p in profile if p.gueltig]
    band_leer = band_von(None, config.modus)
    band_name = band_leer.name
    titel = (
        "VOLUMENPROFILE - FENSTERWEISE (POC / ZONEN-VA 94 % / SEGMENTE)"
        if config.modus == "zone"
        else "VOLUMENPROFILE - FENSTERWEISE (POC / BALANCE-BAND / SEGMENTE)"
    )
    linie = "=" * 130
    txt: List[str] = [
        linie,
        titel,
        f"Hauptband: {config.modus} = {band_name}",
        f"Abdeckung: {band_leer.abdeckung_name}",
    ]
    if band_leer.abdeckung_ist_huelle:
        txt.append(
            "  ACHTUNG: das Band ist die Huelle der Segment-Value-Areas. "
            "Zwischen den Bergen liegende Bereiche gehoeren zu keinem Berg und "
            "tragen kein Volumen dieses Bandes - die Abdeckung ist deshalb "
            "NICHT zusammenhaengend (sie sagt nur, wie viel Volumen zwischen "
            "kleinster Berg-VAL und groesster Berg-VAH liegt)."
        )
    txt += [
        f"Instrument: {config.symbol} {config.timeframe} | Zeitraum: "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"Fensterart: {config.window_kind} | min_bars={effektive_min_bars(config)}"
        f"{'' if config.min_bars is not None else f' (abgeleitet, min_abdeckung={config.min_abdeckung})'}"
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
        f"Volumenfilter: vol_min={config.vol_min} vol_quantil={config.vol_quantil} "
        f"(wirkt auf das Profil, nicht auf die Zahl der Berge)",
        f"POC-Unsicherheit: Toleranz={config.streu_toleranz_atr} ATR ueber "
        f"bins={list(config.konsens_bins)} x smooth={list(config.konsens_smooth)}",
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
    if gueltig:
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
            if band_leer.abdeckung_ist_huelle:
                txt.append(
                    "    (aus dem ROHPROFIL zwischen kleinster Berg-VAL und "
                    "groesster Berg-VAH; die Luecken zwischen den Berg-Value-"
                    "Areas liegen mit im Bereich und tragen kein Volumen "
                    "dieses Bandes - der Wert ist NICHT zusammenhaengend)"
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
    rolle = "ZONE" if config.modus == "zone" else "BALANCE"
    rolle_txt = (
        "ZONE = Zonen-Value-Area ab POC"
        if config.modus == "zone"
        else "BALANCE = Huelle der Segment-Value-Areas"
    )
    kopf: List[str] = [
        f"# volume_profile Level - {config.symbol} {config.timeframe} | "
        f"{config.start} .. {config.ende} (ende-exklusiv, BKZ)",
        f"# Fensterart={config.window_kind} min_bars={effektive_min_bars(config)} "
        f"bins={config.num_bins} "
        f"smooth={config.smooth_win} va_pct={config.va_pct} "
        f"va_zone_pct={config.va_zone_pct} modus={config.modus}",
        f"# rolle: {rolle_txt} | SEGMENT = einzelner Volumen-Berg",
        f"# Segmentzahl-Treiber: valley_rel={config.valley_rel} (groesser = mehr "
        f"Berge/POCs, kleiner = weniger); min_mountain_pct="
        f"{config.min_mountain_pct} verwirft nur kleine Berge",
        f"# va_abdeckung: {band_von(None, config.modus).abdeckung_name}"
        + (
            " (Luecken zwischen den Berg-VAs gehoeren keinem Berg)"
            if config.modus == "balance"
            else ""
        ),
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


def _datei_stamm(config: VolumeProfilConfig) -> str:
    """Dateiname-Stamm der Ausgaben (ohne Endung).

    Args:
        config: Laufkonfiguration.

    Returns:
        Stamm wie
        ``volume_profile_SILVER_M15_day_zone_2026-08-01_2026-09-01``.
    """
    sym = "".join(ch for ch in config.symbol.upper() if ch.isalnum())
    return (
        f"volume_profile_{sym}_{config.timeframe}_{config.window_kind}_"
        f"{config.modus}_{config.start}_{config.ende}"
    )


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
                     "grid_max_profile", "grid_seiten_max"):
            felder[key] = int(val)
        elif key in ("va_pct", "valley_rel", "min_mountain_pct", "va_zone_pct",
                     "vol_min", "vol_quantil", "streu_toleranz_atr",
                     "min_abdeckung"):
            felder[key] = float(val)
        elif key in ("konsens_bins", "konsens_smooth"):
            felder[key] = tuple(
                int(t) for t in val.replace(";", ",").split(",") if t.strip()
            )
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
    if config.start >= config.ende:
        raise SystemExit(
            f"Leerer Zeitraum: start={config.start} muss < ende={config.ende} sein."
        )


def _store_parameter(config: VolumeProfilConfig) -> Dict[str, object]:
    """Bildet die Parameter, die in die ``run_id`` des Speichers eingehen.

    ``modus`` gehoert bewusst NICHT dazu: gehalten werden immer BEIDE Baender
    (``val``/``vah`` = Zonen-VA, ``val_huelle``/``vah_huelle`` =
    Balance-Huelle). Der Modus ist reine Auswahl bei Meldung und Zeichnung und
    darf deshalb keinen zweiten Speicher mit identischen Zahlen anlegen.

    Args:
        config: Laufkonfiguration.

    Returns:
        Parameterdict (Volumenparameter + Fensterart + Konsens + Zeitraum).
    """
    return {
        **asdict(_profil_parameter(config)),
        "window_kind": config.window_kind,
        "min_bars": effektive_min_bars(config),
        "konsens_bins": list(config.konsens_bins),
        "konsens_smooth": list(config.konsens_smooth),
        "streu_toleranz_atr": config.streu_toleranz_atr,
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
    speicher = HALTER.hole_oder_anlegen(
        config.symbol, config.timeframe, config.window_kind, store_params
    )
    n_gehalten = speicher.merke(zeilen, nests)
    stand = speicher.zaehle()
    halter_stand = HALTER.zaehle()
    speicher_zeile = (
        f"Laufzeitspeicher: run_id={speicher.run_id}, "
        f"{n_gehalten} Profile, {stand['nests']} Segmente gehalten, "
        f"{speicher.speicher_mb():.2f} MB | Halter: "
        f"{len(HALTER)} Parametersatz/Parametersaetze, "
        f"{halter_stand['profiles']} Profile gesamt, "
        f"{HALTER.speicher_mb():.2f} MB"
    )

    # --- Ausgabe -----------------------------------------------------------
    config.out_dir.mkdir(parents=True, exist_ok=True)
    stamm = _datei_stamm(config)
    (config.out_dir / f"{stamm}.txt").write_text(
        report_text(config, profile, n_verworfen), encoding="utf-8"
    )
    (config.out_dir / f"{stamm}_levels.tsv").write_text(
        tsv_levels(config, profile), encoding="utf-8"
    )
    stil = ChartStil(
        dpi=config.dpi,
        titel_symbol=config.symbol,
        titel_timeframe=config.timeframe,
        zeitraum=f"{config.start} .. {config.ende} (ende-exkl., BKZ)",
        max_profile=config.grid_max_profile,
        seiten_max=config.grid_seiten_max,
        modus=config.modus,
    )
    p_zone, p_grids = zeichne_alles(
        df, profile, stil, config.out_dir / stamm
    )

    gueltig = [p for p in profile if p.gueltig]
    n_unsicher = sum(1 for p in gueltig if not p.konsens.eindeutig)
    print(
        f"Fensterart {config.window_kind} | Modus {config.modus}: "
        f"{len(gueltig)} Profile aus "
        f"{len(profile)} ausgewerteten Fenstern ({n_verworfen} verworfen, "
        f"min_bars={effektive_min_bars(config)}) | POC unsicher: {n_unsicher}"
    )
    if speicher_zeile:
        print(speicher_zeile)
    print(f"Ausgabe: {config.out_dir / (stamm + '.txt')}")
    print(f"         {config.out_dir / (stamm + '_levels.tsv')}")
    if p_zone:
        print(f"         {p_zone}")
    for g in p_grids:
        print(f"         {g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
