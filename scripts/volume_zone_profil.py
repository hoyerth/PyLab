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
Reine LEVEL-ERMITTLUNG und Darstellung. Es wird NICHT gehandelt, kein Signal
erzeugt, keine Strategie simuliert. Das Skript legt die Datenbasis fuer die
spaetere statistische Untersuchung von Spruengen zwischen Volumen-Leveln
(Tages-TSV ``*_levels.tsv`` mit POC/VAL/VAH je Nest).

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
    volume_zone_<SYMBOL>_<TF>_<start>_<ende>.png    Chart (POC/VAH/VAL)
    volume_zone_<SYMBOL>_<TF>_<start>_<ende>.txt    Report (Tages-Tabelle)
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
            verworfen, nicht interpoliert).
        dpi: Aufloesung der PNG-Ausgabe.
        chart_limit_tage: Nur die letzten N Tage zeichnen (0 = alle).
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
    min_bars_pro_tag: int = 40

    # --- Ausgabe ------------------------------------------------------------
    dpi: int = 300
    chart_limit_tage: int = 0
    report_dir: Path = (
        Path(__file__).resolve().parent.parent / "test" / "VolumeZone" / "reports"
    )


# =============================================================================
# 2) DATENVERTRAEGE (aus der Baseline herueberkopiert)
# =============================================================================


@dataclass(slots=True)
class VolumeProfileData:
    """Rohes Volumenprofil eines Zeitraums (Baseline-Datenvertrag)."""

    centers: np.ndarray
    edges: np.ndarray
    vol: np.ndarray
    pmin: float
    pmax: float


@dataclass(slots=True)
class MountainPeak:
    """Ein Volumen-Berg ("Nest") mit eigener Value Area (Baseline-Vertrag)."""

    poc: float
    val: float
    vah: float
    vol: float
    peak_share_pct: float


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


# =============================================================================
# 3) VOLUMEN-LOGIK (aus scripts/phasen_volumen_profil.py herueberkopiert,
#    Baseline-Zeilen 478-608; nur die Schwellen sind parametrisiert worden,
#    die Algorithmik ist unveraendert)
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
        va_pct: Value-Area-Anteil.

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
    )


def compute_volume_zone(
    sub: pd.DataFrame, config: VolumeZoneConfig
) -> Optional[VolumeZone]:
    """Volumen-Zone eines Zeitraums (Baseline Z. 584-608).

    Args:
        sub: OHLCV-Bars des Zeitraums.
        config: Konfiguration (Bins, Glaettung, VA-Anteil, Tal-/Berg-Schwellen).

    Returns:
        ``VolumeZone`` oder ``None``, wenn kein Profil/Berg gefunden wurde.
    """
    prof = build_volume_profile(sub, config.num_bins)
    if prof is None:
        return None
    vol_s = smooth_vol(prof.vol, config.smooth_win)
    mountains = find_mountains(vol_s, config.min_mountain_pct, config.valley_rel)
    if not mountains:
        return None
    dominant_peak = mountains[0][1]
    peaks: List[MountainPeak] = []
    for m in mountains:
        peaks.append(va_for_mountain(vol_s, prof.edges, m, dominant_peak, config.va_pct))
    return VolumeZone(
        profile=prof,
        mountains=mountains,
        peaks=peaks,
        U_zone=max(p.vah for p in peaks),
        L_zone=min(p.val for p in peaks),
        POC=peaks[0].poc,
        n_mountains=len(peaks),
    )


# =============================================================================
# 4) TAGES-SEGMENTIERUNG (BKZ, Kanon K6: dynamische Kalendergrenzen)
# =============================================================================


def _kalendertage(df: pd.DataFrame, config: VolumeZoneConfig) -> List[Tuple[pd.Timestamp, int, int]]:
    """Zerlegt das Fenster in BKZ-Kalendertage ``(tag, erster_bar, letzter_bar)``.

    Die Grenzen werden dynamisch per ``searchsorted`` auf der BKZ-Achse
    abgeleitet (Kanon K6) - keine Bar-Konstante, keine Zeitzonen-Projektion.
    Tage ohne Bars (z. B. Wochenende) entfallen.

    Args:
        df: Fenster-Bars mit ``ts`` (BKZ, tz-naiv, aufsteigend).
        config: Konfiguration (start/ende).

    Returns:
        Liste ``(tag, bar_start, bar_ende)`` mit ``bar_ende`` inklusiv.
    """
    ts_ns: np.ndarray = df["ts"].values.astype("datetime64[ns]")
    tage = pd.date_range(
        pd.Timestamp(config.start), pd.Timestamp(config.ende), freq="D", inclusive="left"
    )
    out: List[Tuple[pd.Timestamp, int, int]] = []
    for tag in tage:
        i0 = int(np.searchsorted(ts_ns, np.datetime64(tag), side="left"))
        i1 = int(
            np.searchsorted(
                ts_ns, np.datetime64(tag + pd.Timedelta(days=1)), side="left"
            )
        ) - 1
        if i1 >= i0:
            out.append((tag, i0, i1))
    return out


def berechne_tages_balancen(
    df: pd.DataFrame, config: VolumeZoneConfig
) -> List[TagesBalance]:
    """Rechnet je BKZ-Kalendertag eine Balance samt ihrer Nester.

    Args:
        df: Fenster-Bars (OHLCV, BKZ).
        config: Konfiguration.

    Returns:
        Chronologische Liste ``TagesBalance`` (auch ungueltige Tage, damit die
        Report-Tabelle die Verwerfungen transparent ausweist).
    """
    high: np.ndarray = df["high"].to_numpy(dtype=float)
    low: np.ndarray = df["low"].to_numpy(dtype=float)
    out: List[TagesBalance] = []
    for tag, i0, i1 in _kalendertage(df, config):
        n_bars = i1 - i0 + 1
        atr = float(np.mean(high[i0 : i1 + 1] - low[i0 : i1 + 1]))
        zone: Optional[VolumeZone] = None
        if n_bars >= config.min_bars_pro_tag:
            zone = compute_volume_zone(df.iloc[i0 : i1 + 1], config)
        if zone is None:
            out.append(
                TagesBalance(
                    tag=tag, bar_start=i0, bar_ende=i1, n_bars=n_bars,
                    gueltig=False, poc=float("nan"), val=float("nan"),
                    vah=float("nan"), nester=[], zone=None, atr=atr,
                )
            )
            continue
        out.append(
            TagesBalance(
                tag=tag, bar_start=i0, bar_ende=i1, n_bars=n_bars,
                gueltig=True, poc=zone.POC, val=zone.L_zone, vah=zone.U_zone,
                nester=zone.peaks, zone=zone, atr=atr,
            )
        )
    return out


# =============================================================================
# 5) AUSGABE (TXT-Report, TSV-Level, PNG-Chart)
# =============================================================================

_COL_BALANCE: str = "#1565c0"   # VAH/VAL-Rahmen der Tages-Balance
_COL_POC: str = "#0d47a1"       # POC (dominantes Nest)
_COL_NEST: str = "#e65100"      # POC der uebrigen Nester
_COL_PREIS: str = "#bbbbbb"     # Preis (high/low-Linien)


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
        f"min_bars/tag={config.min_bars_pro_tag}",
        "Volumen-Logik: herueberkopiert aus scripts/phasen_volumen_profil.py "
        "(eingefrorene Baseline, unveraenderte Algorithmik)",
        linie,
        f"Kalendertage im Fenster: {len(balancen)} | auswertbar: {len(gueltig)} | "
        f"verworfen: {len(balancen) - len(gueltig)}",
        "",
        "TAGES-BALANCEN (BKZ, Bar-Indizes aus dem Fenster-DataFrame):",
        "  Tag        | bars  |   POC     VAL     VAH   | Breite | Breite/ATR | "
        "Nester | POC der Nester (absteigend nach Volumen)",
        "  " + "-" * 114,
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
        txt.append(
            f"  {b.tag:%Y-%m-%d} | {b.n_bars:5d} | {b.poc:8.3f} {b.val:8.3f} "
            f"{b.vah:8.3f} | {breite:6.3f} | {_fmt(b_atr, '.2f'):>10} | "
            f"{len(b.nester):6d} | {nester_txt}"
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
    txt.append(linie)
    return "\n".join(txt) + "\n"


def levels_tsv(config: VolumeZoneConfig, balancen: Sequence[TagesBalance]) -> str:
    """Maschinenlesbarer Level-Block (ein Nest je Zeile) fuer die Spaeteranalyse.

    Der Block ist die Datenbasis fuer die statistische Untersuchung von
    Spruengen zwischen Volumen-Leveln: je Tag ein Balance-Satz, je Nest eine
    Zeile mit POC/VAL/VAH.

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
        "tag\tbar_start\tbar_ende\tn_bars\tatr\trolle\trank\t"
        "poc\tval\tvah\tbreite\tvol\tpeak_share_pct",
    ]
    zeilen: List[str] = list(kopf)
    for b in balancen:
        if not b.gueltig:
            continue
        zeilen.append(
            f"{b.tag:%Y-%m-%d}\t{b.bar_start}\t{b.bar_ende}\t{b.n_bars}\t"
            f"{b.atr:.5f}\tBALANCE\t-1\t{b.poc:.5f}\t{b.val:.5f}\t{b.vah:.5f}\t"
            f"{b.vah - b.val:.5f}\t\t"
        )
        for rank, p in enumerate(b.nester):
            zeilen.append(
                f"{b.tag:%Y-%m-%d}\t{b.bar_start}\t{b.bar_ende}\t{b.n_bars}\t"
                f"{b.atr:.5f}\tNEST\t{rank}\t{p.poc:.5f}\t{p.val:.5f}\t"
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
    gestrichelt gezeichnet.

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
        # POC der Balance (dominantes Nest)
        ax.plot(
            [x0, x1], [b.poc, b.poc], color=_COL_POC, lw=1.6, zorder=5
        )
        ax.annotate(
            f"{b.tag:%d.%m} POC {b.poc:.3f}",
            (x0, b.poc), xytext=(x0 + 1, b.poc + 0.02),
            fontsize=6.0, color=_COL_POC, va="bottom", zorder=6,
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
    stat: List[str] = [
        f"Tage gezeigt: {len(tage_zeigen)} (auswertbar {len(gueltig)})",
        f"Nester gezeichnet: {len(gueltig) + n_nester}",
    ]
    if gueltig:
        b_atr = np.array(
            [(b.vah - b.val) / b.atr for b in gueltig if b.atr > 0], dtype=float
        )
        stat.append(f"Zonenbreite: median {np.median(b_atr):.2f} ATR")
        stat.append(
            f"Nester/Tag: median {np.median([len(b.nester) for b in gueltig]):.0f}"
        )
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
                     "chart_limit_tage"):
            felder[key] = int(val)
        elif key in ("va_pct", "valley_rel", "min_mountain_pct"):
            felder[key] = float(val)
        elif key in ("db_path", "report_dir"):
            felder[key] = Path(val)
        else:
            raise SystemExit(f"Unbekanntes Argument: --{key}")
    return replace(config, **felder)  # type: ignore[arg-type]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: findet Tages-Balancen und schreibt Report/TSV/Chart.

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
    if not 0.0 < config.va_pct < 1.0:
        raise SystemExit("va_pct muss im offenen Intervall (0, 1) liegen.")
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

    config.report_dir.mkdir(parents=True, exist_ok=True)
    stamm = _datei_stamm(config)
    text = report_text(config, balancen)
    (config.report_dir / f"{stamm}.txt").write_text(text, encoding="utf-8")
    (config.report_dir / f"{stamm}_levels.tsv").write_text(
        levels_tsv(config, balancen), encoding="utf-8"
    )
    zeichne_chart(config, df, balancen, config.report_dir / f"{stamm}.png")

    print(text)
    print(
        f"Ausgabe: {config.report_dir / (stamm + '.png')}\n"
        f"         {config.report_dir / (stamm + '.txt')}\n"
        f"         {config.report_dir / (stamm + '_levels.tsv')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
