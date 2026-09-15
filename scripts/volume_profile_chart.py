"""
VOLUMENPROFIL-CHART (scripts/volume_profile_chart.py)
======================================================
Darstellung der gerechneten Volumenprofile beliebiger Fensterarten. Reines
Ausgabemodul: es liest den Vertrag ``FensterProfil`` (Kern + Fenster) und
zeichnet - es rechnet keine Level und bildet keine Fenster.

Zwei Ausgaben
-------------
1) ZONEN-CHART   Kerzen (open/close mit high/low-Docht) ueber der Bar-Achse,
                 je Fenster das Rechteck der Zonen-Value-Area (94 %) und die
                 POC-Linie.
                 Ist der POC unsicher (``poc_streu_atr`` > Toleranz), wird das
                 POC-Band der Konsens-Parametersaetze schraffiert und die
                 POC-Linie gestrichelt in der Warnfarbe gezeichnet.
                 Zusaetzlich werden die POCs der uebrigen Segmente gestrichelt
                 dargestellt - die Segment-Erkennung bleibt damit sichtbar.
                 Der Hauptband-Rechteckrahmen ist dabei nur noch KONTUR: die
                 Aussage tragen die getrennten Bereiche je Segment (siehe
                 unten), sonst wuerde eine durchgehende Flaeche die Trennung
                 wieder zudecken.
2) PROFIL-GRID   je Fenster ein horizontales Volumenprofil, farblich nach
                 Segment (Berg) getrennt, mit Hauptband, dem eigenen Bereich je
                 Segment, POC, POC-Band und Zweitgipfel-Niveau. Das ist die
                 Sichtpruefung der Erkennung.

Bereiche statt eines Bandes
---------------------------
Ein durchgehendes Band (die Huelle ueber ALLE Segmente) ist meist
breiter als der Move, den es beschreiben soll, und verdeckt die Trennung der
Volumen-Nester. Deshalb zeichnet ``ChartStil.bereiche_zeichnen`` (Default) je
Segment dessen EIGENEN Bereich ``[VAL .. VAH]`` als eigene Flaeche in der
Segmentfarbe und vermasst jede Luecke zwischen zwei benachbarten Bereichen mit
ihrer Breite in ATR (``L <ATR>``). Die Luecke bleibt dabei LEER - dort laufen
die schnellen Moves, und das ist die Aussage.

Das HAUPTBAND ist die Zonen-Value-Area ab POC (``ChartStil.modus`` = ``zone``,
dem einzigen Modus); die Huelle der Segment-Value-Areas wird im Kern nur noch
als Kennzahl gefuehrt (``huellen_abdeckung``) und nicht mehr gezeichnet.

Wie weit ein Bereich reicht, entscheidet ``va_pct`` im Kern (Anteil des
BERGVOLUMENS). Das Chart rechnet das nicht nach; es traegt die Zahl ueber
``ChartStil.bereich_va_pct`` in Titel, Statistikblock und Legende, damit eine
Ausgabe ohne Blick in den Report lesbar bleibt (Default 0,7 = 70 %).

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Alle Zeitangaben sind BKZ (tz-naiv). Die X-Achse des Zonen-Charts ist der
Bar-Index (K5: Primaerschluessel), die Tick-Beschriftung sitzt GENAU auf den
BKZ-Tagesgrenzen (00:00 je Tag, dynamisch aus der Zeitachse abgeleitet, K6) -
der Achsenwechsel ist damit mit dem Tageswechsel synchronisiert. Es findet
keine Zeitzonen-Projektion statt (K2).

Aufruf (aus einem Orchestrator):
    from scripts.volume_profile_chart import ChartStil, zeichne_zonen_chart
    zeichne_zonen_chart(df, profile, ChartStil(), out_png)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from scripts.volume_profile_core import (  # noqa: E402
    Band,
    FensterProfil,
    band_von,
    zerlege_bereiche,
)
from scripts.volume_profile_nests import NestInstanz  # noqa: E402

# Kurzname und Ueberschrift des Hauptbandes (es gibt nur eine Engine und nur
# EIN Hauptband - die Zonen-Value-Area; siehe volume_profile_core.MODI).
_KURZ_MODUS: Dict[str, str] = {
    "zone": "Zonen-Value-Area (94 %)",
}
_TITEL_MODUS: Dict[str, str] = {"zone": "ZONEN"}

# Farben (bewusst identisch zur archivierten Referenz
# ``scripts/archiv/volume_zone_profil.py`` gehalten, damit Sichtpruefungen der
# Tages-Balancen und der Zonen-VA dieselbe Farbsprache sprechen)
_COL_ZONE: str = "#1565c0"    # Hauptband (Zonen-VA)
_COL_POC: str = "#0d47a1"     # POC eindeutig
_COL_POC_U: str = "#c62828"   # POC uneindeutig (+ Konsensband)
_COL_NEST: str = "#e65100"    # POC weiterer Segmente
_COL_NEST_OBJ: str = "#00695c"  # NEST ueber Fenstergrenzen (eigenes Objekt)
_COL_NEST_RAND: str = "#8e24aa"  # Nest endet am Zeitraumrand (angeschnitten)
# Kerzen: dieselbe Farbsprache wie ``algos/chart_engine.py`` (Marktansicht der
# Anwendung) - auf = gruen, ab = rot. BEWUSSTE Abweichung von der archivierten
# Referenz ``scripts/archiv/volume_zone_profil.py``: dort lief der Preis als
# grauer high/low-Linienzug (``_COL_PREIS`` = ``#bbbbbb``). Die Sichtpruefung
# verlangt Kerzen (open/close mit Docht) - die Linie ist damit ersetzt.
_COL_KERZE_AUF: str = "#26a69a"  # Kerze auf (close >= open)
_COL_KERZE_AB: str = "#ef5350"   # Kerze ab (close < open)
_COL_LOB2: str = "#2e7d32"    # Zweitgipfel-Niveau
_COL_OHNE_NEST: str = "#dcdcdc"

_PALETTE_NEST: Tuple[str, ...] = (
    "#1565c0", "#e65100", "#2e7d32", "#6a1b9a", "#00838f",
)


@dataclass(frozen=True, slots=True)
class ChartStil:
    """Darstellungsparameter der beiden PNG-Ausgaben.

    Attributes:
        dpi: Aufloesung der Ausgabe.
        titel_symbol: Symbol fuer Titel/Achsenbeschriftung.
        titel_timeframe: Timeframe fuer den Titel.
        zeitraum: Zeitraumtext (z. B. ``2026-08-01 .. 2026-09-01``).
        max_profile: Obergrenze der im Profil-Grid gezeigten Fenster. 0
            (Default) = ALLE Fenster des Testzeitraums zeigen; es gibt keinen
            eigenen 4h-/Intraday-Grafikmodus.
        seiten_max: Hoechstzahl Panels je PNG-Seite (0 = keine Teilung). Da
            immer der GANZE Testzeitraum gezeigt wird, wird bei mehr Fenstern
            seitenweise ausgegeben (``..._profile_s1.png``, ``..._s2.png``,
            ...) - nichts wird weggelassen, nur aufgeteilt.
        ncols_grid: Spalten des Profil-Grids.
        max_label_zeichen: Auf diese Laenge werden Fensterlabels im
            Zonen-Chart gekuerzt (verhindert Ueberlappung).
        max_xticks: Hoechstzahl der beschrifteten Ticks auf der X-Achse des
            Zonen-Charts. Die Ticks sitzen IMMER auf den BKZ-Tagesgrenzen
            (00:00 je Tag, dynamisch abgeleitet) - bei vielen Tagen wird nur
            die Beschriftung ausgeduennt, nie der Bezug zum Tageswechsel
            aufgegeben. Alle Tagesgrenzen erhalten zusaetzlich eine duenne
            Hilfslinie, damit der Tageswechsel im Preisverlauf sichtbar ist.
        bereiche_zeichnen: True (Default) = jedes Segment bekommt seinen
            EIGENEN Bereich ``[VAL .. VAH]`` als eigene Flaeche in der
            Segmentfarbe; das Hauptband wird dann nur noch als Kontur gefuehrt
            und die Luecken zwischen zwei Bereichen werden mit ihrer Breite in
            ATR beschriftet. Damit ist sichtbar, was sonst im durchgehenden
            Band verschwindet: getrennte Volumen-Nester und die schnellen Moves
            dazwischen. False = alte Ansicht (Hauptband als Flaeche, je
            Segment nur die POC-Linien).
        parameter_txt: Zusatz fuer Titel/Achsenkopf. Traegt die vom Default
            abweichenden profilbildenden Parameter (z. B. ``va_pct=0.93``),
            damit eine Ausgabe ohne Blick in die Datei zuordenbar ist.
        bereich_va_pct: Value-Area-Anteil des Bergvolumens, der die Weite der
            Bereiche je Segment bestimmt (Informationswert fuer die Legende -
            im Chart wird nichts gerechnet, die Bereiche kommen aus dem Kern).
            Damit ist auch ohne Parameterzusatz lesbar, wie breit ein Bereich
            angelegt ist (Default 0,7 = 70 % des Bergvolumens).
        modus: Hauptband der Zeichnung (``zone``, einziges Hauptband). Der
            Namen wird gegen den Kern geprueft; ein unbekannter Wert scheitert
            dort fail-loud.
    """

    dpi: int = 300
    titel_symbol: str = ""
    titel_timeframe: str = ""
    zeitraum: str = ""
    max_profile: int = 0
    seiten_max: int = 96
    ncols_grid: int = 4
    max_label_zeichen: int = 24
    max_xticks: int = 14
    bereiche_zeichnen: bool = True
    bereich_va_pct: float = 0.7
    parameter_txt: str = ""
    modus: str = "zone"

    @property
    def bereich_va_txt(self) -> str:
        """Kurztext der Bereichsweite fuer Legende und Titel (z. B. ``VA 70 %``).

        Returns:
            Text mit dem Value-Area-Anteil in Prozent.
        """
        return f"VA {self.bereich_va_pct * 100:.0f} %"


def _band(p: FensterProfil, stil: ChartStil) -> Band:
    """Liefert das Hauptband eines Fensters im Stil-Modus.

    Args:
        p: Fensterprofil.
        stil: Darstellungsparameter (liefert ``modus``).

    Returns:
        ``Band`` des Modus; ohne Profil sind alle Kanten ``nan``.
    """
    return band_von(p.segmentierung, stil.modus)


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


def _stamm(stil: ChartStil) -> str:
    """Bildet den Titel-Kopf der Abbildungen.

    Args:
        stil: Darstellungsparameter.

    Returns:
        Titeltext aus Symbol, Timeframe, Zeitraum und Parameterzusatz.
    """
    teile = [t for t in (stil.titel_symbol, stil.titel_timeframe) if t]
    kopf = " ".join(teile)
    if stil.zeitraum:
        kopf = f"{kopf} | {stil.zeitraum}" if kopf else stil.zeitraum
    if stil.parameter_txt:
        kopf = f"{kopf} | {stil.parameter_txt}" if kopf else stil.parameter_txt
    return kopf


def _bereich_farben(n: int) -> List[str]:
    """Liefert je Bereich (Rang) eine feste Farbe aus der Segment-Palette.

    Args:
        n: Anzahl der Bereiche.

    Returns:
        Farbliste in Rangfolge (0 = groesstes Segment).
    """
    return [_PALETTE_NEST[i % len(_PALETTE_NEST)] for i in range(max(0, n))]


def _tagesgrenzen_indizes(df: pd.DataFrame, max_ticks: int = 14) -> np.ndarray:
    """Liefert die Bar-Indizes der BKZ-Tagesgrenzen (je erster Bar eines Tages).

    Die Grenzen werden DYNAMISCH aus der BKZ-Achse abgeleitet (Kanon K6: keine
    Bar-Konstante, kein ``searchsorted`` auf einer Zeitzonen-Projektion). Damit
    faellt jeder X-Achsen-Tick exakt mit dem Wechsel auf einen neuen Tag
    zusammen - die Beschriftung ist mit dem Tageswechsel synchronisiert und
    nicht mehr an einen beliebigen Bar-Schritt gebunden.

    Bei vielen Tagen wird ausgeduennt; die verbleibenden Ticks liegen aber
    IMMER auf einer Tagesgrenze (der erste Tag ist stets dabei).

    Args:
        df: Bars (Spalte ``ts`` = BKZ, tz-naiv, aufsteigend sortiert).
        max_ticks: Hoechstzahl der Achsen-Ticks (<= 0 = nicht ausduennen).

    Returns:
        Aufsteigende Bar-Indizes; leer nur bei leerem DataFrame.
    """
    if df.empty:
        return np.zeros(0, dtype=int)
    ts: pd.Series = df["ts"]
    tage: pd.Series = ts.dt.normalize()
    # Erster Bar eines Tages: Tagesdatum wechselt gegenueber dem Vorgaenger-Bar
    # (der erste Bar der Achse ist per NaT-Vergleich ebenfalls ein Wechsel).
    indizes: np.ndarray = np.flatnonzero(tage.ne(tage.shift(1)).to_numpy())
    if indizes.size == 0:
        indizes = np.array([0], dtype=int)
    if max_ticks > 0 and indizes.size > max_ticks:
        schritt: int = int(np.ceil(indizes.size / max_ticks))
        ausgeduennt: np.ndarray = indizes[::schritt]
        # Letzten Tageswechsel mitnehmen, wenn er nicht direkt am Vorgaenger klebt
        if ausgeduennt.size > 1 and indizes[-1] - ausgeduennt[-1] > 1:
            ausgeduennt = np.append(ausgeduennt, indizes[-1])
        indizes = ausgeduennt
    return indizes.astype(int)


def _tagesgrenzen_labels(df: pd.DataFrame, indizes: np.ndarray) -> List[str]:
    """Beschriftet die Tagesgrenz-Ticks (Datum, ohne Uhrzeit).

    Da die Ticks per Konstruktion genau auf dem Tagesanfang liegen, genuegt das
    Datum; die Uhrzeit waere in jeder Zeile dieselbe (00:00 BKZ).

    Args:
        df: Bars mit Spalte ``ts`` (BKZ, tz-naiv).
        indizes: Bar-Indizes der Tagesgrenzen.

    Returns:
        Beschriftungen in Reihenfolge der Indizes.
    """
    ts: pd.Series = df["ts"]
    return [ts.iloc[int(i)].strftime("%a %d.%m.") for i in indizes]


# =============================================================================
# 1) ZONEN-CHART
# =============================================================================


def _kerzen_farben(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Liefert je Bar die Kerzenfarbe (auf/ab) als Vektor.

    Args:
        open_: Open-Reihe der Bars.
        close: Close-Reihe der Bars.

    Returns:
        String-Array mit ``_COL_KERZE_AUF`` (close >= open) bzw.
        ``_COL_KERZE_AB`` (close < open).
    """
    return np.where(close >= open_, _COL_KERZE_AUF, _COL_KERZE_AB)


def _zeichne_kerzen(ax: plt.Axes, df: pd.DataFrame, breite: float = 0.7) -> int:
    """Zeichnet OHLC-Kerzen vektorisiert in eine Achse (Docht + Koerper).

    Es wird KEIN Loop ueber die Bars gefahren: Docht (``vlines``) und Koerper
    (``bar``) gehen jeweils als ganze Reihe an matplotlib. Ein Doji
    (``open == close``) bekommt eine Mindest-Koerperhoehe von 1/10000 der
    Achsenspanne, sonst waere er unsichtbar. Rot/ gruen folgen
    ``algos/chart_engine.py`` (auf = ``#26a69a``, ab = ``#ef5350``).

    Hinweis: Die ``idx``-Spalte ist der Bar-Index (Primaerschluessel, K5) und
    laeuft in 1er-Schritten - die Kerzenbreite ist deshalb in Achsen-Einheiten
    anzugeben, nicht in Zeit.

    Args:
        ax: Ziel-Achse.
        df: Bars (Spalten ``idx/open/high/low/close``).
        breite: Kerzenbreite in Einheiten der X-Achse (1.0 = volle Bar-Breite).

    Returns:
        Anzahl gezeichneter Kerzen (0 bei leerem Input).
    """
    if df.empty:
        return 0
    x: np.ndarray = df["idx"].to_numpy(dtype=float)
    o: np.ndarray = df["open"].to_numpy(dtype=float)
    h: np.ndarray = df["high"].to_numpy(dtype=float)
    l: np.ndarray = df["low"].to_numpy(dtype=float)
    c: np.ndarray = df["close"].to_numpy(dtype=float)
    farben = _kerzen_farben(o, c)
    # Docht zuerst (zorder 1), Koerper darueber (zorder 2) - die Bänder und
    # POC-Linien der Profile liegen mit zorder >= 3 darueber, bleiben aber
    # durchscheinend, damit die Kerzen an jeder Stelle lesbar bleiben.
    ax.vlines(x, l, h, color=list(farben), lw=0.45, zorder=1)
    spanne: float = float(np.nanmax(h) - np.nanmin(l)) if h.size else 0.0
    minimum: float = spanne * 1e-4 if spanne > 0.0 else 0.0
    unten: np.ndarray = np.minimum(o, c)
    hoehe: np.ndarray = np.maximum(np.abs(c - o), minimum)
    ax.bar(
        x, hoehe, bottom=unten, width=breite, color=list(farben),
        edgecolor="none", linewidth=0.0, zorder=2,
    )
    return int(x.size)


def zeichne_zonen_chart(
    df: pd.DataFrame,
    profile: Sequence[FensterProfil],
    stil: ChartStil,
    out_png: Path,
    nur_gueltige: bool = True,
    nester: Optional[Sequence[NestInstanz]] = None,
) -> None:
    """Zeichnet Kerzen, die getrennten Bereiche je Segment und das Hauptband.

    Der Preisverlauf steht als OHLC-Kerze auf der Bar-Achse (auf/ab in der
    Farbsprache der Anwendung, siehe ``_zeichne_kerzen``); je Fenster wird das
    Rechteck ``[VAL .. VAH]`` der 94 %-Zonen-Klammer und die
    POC-Linie gezeichnet; die POCs der uebrigen Segmente gestrichelt. Bei
    unsicherem POC (``streu_atr`` > Toleranz) wird zusaetzlich das POC-Band der
    Konsens-Parametersaetze schraffiert - die Unsicherheit ist sichtbar statt
    verborgen.

    Mit ``stil.bereiche_zeichnen`` (Default) bekommt JEDES Segment seinen
    EIGENEN Bereich ``[VAL .. VAH]`` als eigene Flaeche in der Segmentfarbe,
    das Hauptband wird nur noch als Kontur gefuehrt und jede Luecke zwischen
    zwei benachbarten Bereichen wird mit ihrer Breite in ATR beschriftet. Damit
    ist die Trennung der Volumen-Nester sichtbar - und der schnelle Move
    dazwischen bleibt als leerer Streifen stehen, statt im durchgehenden Band
    unterzugehen.

    Ueber die Fenster gelegt werden die NESTER (``nester``): sie sind die
    zusammenhaengenden Laeufe eines Knotens ueber die Fenstergrenze hinweg und
    tragen deshalb ein durchgehendes Band ``[VAL .. VAH]`` mit ihrer eigenen
    POC-Linie. Ein Nest am Zeitraumrand (``angeschnitten``) wird mit einem
    violetten Randmarker gekennzeichnet - es kann weiterlaufen.

    Args:
        df: Bars des Gesamtfensters (Spalten ``idx/open/high/low/close/ts``).
        profile: Fensterprofile (Vertrag ``FensterProfil``).
        stil: Darstellungsparameter.
        out_png: Zielpfad der PNG-Datei.
        nur_gueltige: True = nur Fenster mit Profil zeichnen.
        nester: Nester ueber Fenstergrenzen (nur zaehlende werden gezeichnet);
            None = ohne Nest-Ebene.
    """
    zeigen: List[FensterProfil] = [
        p for p in profile if (p.gueltig or not nur_gueltige)
    ]
    if not zeigen:
        return

    fig, ax = plt.subplots(figsize=(17, 11))
    # Preis als Kerze (open/close mit high/low-Docht) - vektorisiert, siehe
    # ``_zeichne_kerzen``; die Profile liegen mit zorder >= 3 darueber.
    _zeichne_kerzen(ax, df)

    n_nest: int = 0
    n_unsicher: int = 0
    n_bereiche: int = 0
    n_luecken: int = 0
    n_nestobjekte: int = 0
    n_nest_rand: int = 0
    nest_breiten_atr: List[float] = []
    breiten_atr: List[float] = []
    bereich_breiten_atr: List[float] = []
    anteile_aussen: List[float] = []
    for p in zeigen:
        seg = p.segmentierung
        band = _band(p, stil)
        if seg is None or not (np.isfinite(band.val) and np.isfinite(band.vah)):
            continue
        x0, x1 = int(p.bar_start), int(p.bar_ende)
        if stil.bereiche_zeichnen:
            # Hauptband nur als KONTUR: die Aussage tragen die Bereiche. Die
            # Kontur zeigt weiter, wo die Zonen-Klammer bzw. die Segment-Huelle
            # liegt - als Flaeche wuerde sie die Trennung wieder zudecken.
            ax.add_patch(
                Rectangle(
                    (x0, band.val), max(1, x1 - x0),
                    max(band.vah - band.val, 1e-9),
                    facecolor="none", edgecolor=_COL_ZONE, ls=(0, (5, 3)),
                    alpha=0.85, lw=0.9, zorder=2,
                )
            )
        else:
            ax.add_patch(
                Rectangle(
                    (x0, band.val), max(1, x1 - x0),
                    max(band.vah - band.val, 1e-9),
                    facecolor=_COL_ZONE, edgecolor=_COL_ZONE,
                    alpha=0.12, lw=0.8, zorder=2,
                )
            )
        if np.isfinite(p.atr) and p.atr > 0:
            breiten_atr.append(band.breite / p.atr)
        if p.konsens.eindeutig:
            ax.plot([x0, x1], [band.poc, band.poc], color=_COL_POC, lw=1.4,
                    zorder=5)
            ax.annotate(
                f"{p.label[:stil.max_label_zeichen]}\nPOC {band.poc:.3f}",
                (x0, band.poc), xytext=(x0 + 0.5, band.poc + 0.02 * abs(band.poc)),
                fontsize=5.0, color=_COL_POC, va="bottom", zorder=6,
            )
        else:
            n_unsicher += 1
            if np.isfinite(p.konsens.poc_min) and np.isfinite(p.konsens.poc_max):
                ax.add_patch(
                    Rectangle(
                        (x0, p.konsens.poc_min), max(1, x1 - x0),
                        max(p.konsens.poc_max - p.konsens.poc_min, 1e-9),
                        facecolor=_COL_POC_U, edgecolor="none",
                        alpha=0.22, zorder=3,
                    )
                )
            ax.plot([x0, x1], [band.poc, band.poc], color=_COL_POC_U, lw=1.2,
                    ls=(0, (2, 2)), zorder=5)
            ax.annotate(
                f"{p.label[:stil.max_label_zeichen]}\nPOC {band.poc:.3f} ? "
                f"({_fmt(p.konsens.streu_atr, '.2f')} ATR)",
                (x0, band.poc), xytext=(x0 + 0.5, band.poc + 0.02 * abs(band.poc)),
                fontsize=5.0, color=_COL_POC_U, va="bottom", zorder=6,
            )
        for nest in seg.nester[1:]:
            ax.plot([x0, x1], [nest.poc, nest.poc], color=_COL_NEST, lw=0.7,
                    ls=(0, (4, 3)), zorder=4)
            n_nest += 1

        # --- getrennte Bereiche je Segment + Luecken dazwischen -------------
        if stil.bereiche_zeichnen:
            sep = zerlege_bereiche(seg, p.atr)
            farben = _bereich_farben(sep.n_bereiche)
            for b in sep.bereiche:
                farbe = farben[b.rank]
                # Zwei Patches je Bereich: erst die Fuellung (leicht), dann die
                # Kante in voller Deckkraft - die Trennung soll scharf lesbar
                # sein, nicht in der Fuellung untergehen.
                ax.add_patch(
                    Rectangle(
                        (x0, b.val), max(1, x1 - x0), max(b.breite, 1e-9),
                        facecolor=farbe, edgecolor="none", alpha=0.20, zorder=3,
                    )
                )
                ax.add_patch(
                    Rectangle(
                        (x0, b.val), max(1, x1 - x0), max(b.breite, 1e-9),
                        facecolor="none", edgecolor=farbe, lw=1.0, zorder=4,
                    )
                )
            n_bereiche += sep.n_bereiche
            n_luecken += sep.n_luecken
            bereich_breiten_atr.extend(
                b.breite_atr for b in sep.bereiche if np.isfinite(b.breite_atr)
            )
            if np.isfinite(sep.anteil_ausserhalb):
                anteile_aussen.append(sep.anteil_ausserhalb)
            # Die Luecke bleibt LEER (kein Volumen) und wird nur vermasst: sie
            # ist der schnelle Move zwischen zwei Nestern.
            for luecke in sep.luecken:
                if luecke.breite <= 0.0 or not np.isfinite(luecke.breite_atr):
                    continue
                xm = x0 + 0.35 * max(1, x1 - x0)
                ax.plot(
                    [xm, xm], [luecke.unten, luecke.oben], color="#616161",
                    lw=0.6, ls=(0, (1, 2)), zorder=5,
                )
                ax.annotate(
                    f"L {luecke.breite_atr:.2f}", (xm, (luecke.unten + luecke.oben) / 2),
                    xytext=(-1.5, 0), textcoords="offset points", fontsize=4.0,
                    color="#616161", rotation=90, va="center", ha="right",
                    zorder=6,
                )

    # --- Nester ueber Fenstergrenzen (die eigentlichen Knoten) --------------
    # Sie liegen UEBER den Fenstern: EIN Band VAL..VAH mit EINER POC-Linie ueber
    # die ganze Lebensdauer des Laufs - genau das, was die Fenster-Ebene an der
    # Grenze zerschneidet. Nur zaehlende Nester (nicht flimmern/angeschnitten)
    # werden gezeichnet; ein Randnest bekommt nur seinen Marker.
    nest_gezeichnet: List[NestInstanz] = []
    for i in (nester or ()):
        if not np.isfinite(i.poc) or not np.isfinite(i.val) or not np.isfinite(i.vah):
            continue
        a, b = int(i.bar_start), int(i.bar_ende)
        if i.angeschnitten:
            n_nest_rand += 1
            ax.plot(
                [a, a], [i.val, i.vah], color=_COL_NEST_RAND, lw=1.0,
                ls=(0, (1, 1)), zorder=8,
            )
            ax.annotate(
                f"N{i.id} Rand", (a, i.vah), xytext=(2, 3),
                textcoords="offset points", fontsize=4.5,
                color=_COL_NEST_RAND, va="bottom", ha="left", zorder=9,
            )
        if not i.gueltig:
            continue
        nest_gezeichnet.append(i)
        n_nestobjekte += 1
        if np.isfinite(i.breite_atr):
            nest_breiten_atr.append(float(i.breite_atr))
        ax.add_patch(
            Rectangle(
                (a, i.val), max(1, b - a), max(i.vah - i.val, 1e-9),
                facecolor=_COL_NEST_OBJ, edgecolor=_COL_NEST_OBJ,
                alpha=0.10, lw=0.9, zorder=3,
            )
        )
        ax.plot([a, b], [i.poc, i.poc], color=_COL_NEST_OBJ, lw=1.8, zorder=7)
        ax.annotate(
            f"N{i.id} POC {i.poc:.3f}"
            f"{'' if i.n_fenster < 2 else f' ({i.n_fenster} Fenster)'}",
            (a, i.poc), xytext=(2, -6), textcoords="offset points",
            fontsize=5.0, color=_COL_NEST_OBJ, va="top", ha="left", zorder=9,
        )

    # X-Achse: Ticks GENAU auf den BKZ-Tagesgrenzen (00:00 je Tag), dynamisch
    # aus der Zeitachse abgeleitet. ALLE Tagesgrenzen bekommen eine duenne
    # Hilfslinie (der Tageswechsel ist damit im Preisverlauf sichtbar), die
    # Beschriftung wird ausgeduennt - sitzt aber immer auf einem Tageswechsel.
    for g in _tagesgrenzen_indizes(df, max_ticks=0):
        ax.axvline(int(g), color="#9e9e9e", lw=0.4, alpha=0.30, zorder=0)
    ticks = _tagesgrenzen_indizes(df, max_ticks=stil.max_xticks)
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        _tagesgrenzen_labels(df, ticks), rotation=45, ha="right", fontsize=8,
    )
    ax.set_xlabel(
        "BKZ-Tagesgrenzen (00:00) | Bar-Index (K5: Primaerschluessel)", fontsize=8.5
    )
    ax.set_xlim(int(zeigen[0].bar_start) - 1, int(zeigen[-1].bar_ende) + 1)
    ax.set_ylabel(f"Preis ({stil.titel_symbol or 'Preis'})")
    ax.grid(alpha=0.3)
    art = zeigen[0].window_kind
    # Die Bereichsweite steht im Titel, nicht nur in der Legende: eine Ausgabe
    # ohne Parameterzusatz (Default-Lauf) muss trotzdem erkennen lassen, wie
    # breit die Bereiche angelegt sind (va_pct der eigenen Segment-VA).
    bereich_txt = f" | Bereiche: je Segment eigene {stil.bereich_va_txt}" if stil.bereiche_zeichnen else ""
    nest_txt = (
        f" | Nester: {n_nestobjekte}" if nest_gezeichnet else ""
    )
    ax.set_title(
        f"VOLUMENPROFILE - {_TITEL_MODUS.get(stil.modus, stil.modus.upper())} | "
        f"{_stamm(stil)} | Fensterart={art} | "
        f"Bars {int(zeigen[0].bar_start)}..{int(zeigen[-1].bar_ende)}"
        f"{bereich_txt}{nest_txt}"
    )
    stat: List[str] = [
        f"Fenster: {len(zeigen)} | mit Profil {sum(1 for p in zeigen if p.gueltig)}",
        f"Segmente gezeichnet: {sum(p.segmentierung.n_segmente for p in zeigen if p.gueltig)} "
        f"(+{n_nest} weitere POCs)",
        f"POC eindeutig: {len(zeigen) - n_unsicher} | unsicher: {n_unsicher}",
    ]
    if breiten_atr:
        stat.append(
            f"Bandbreite ({stil.modus}): median {np.median(breiten_atr):.2f} ATR"
        )
    if stil.bereiche_zeichnen and bereich_breiten_atr:
        stat.append(
            f"Bereiche ({stil.bereich_va_txt} je Segment): {n_bereiche} "
            f"(median {np.median(bereich_breiten_atr):.2f} ATR breit) | "
            f"Luecken: {n_luecken}"
        )
        if anteile_aussen:
            stat.append(
                f"Volumen ausserhalb der Bereiche: median "
                f"{np.median(anteile_aussen):.3f} (Luecken + Bergflanken)"
            )
    st = [p.konsens.streu_atr for p in zeigen if np.isfinite(p.konsens.streu_atr)]
    if st:
        stat.append(f"POC-Streuung: median {np.median(st):.2f} ATR")
    if nest_gezeichnet:
        stat.append(
            f"Nester (ueber Fenstergrenzen): {n_nestobjekte} gezeichnet | "
            f"Breite median {np.median(nest_breiten_atr):.2f} ATR"
            if nest_breiten_atr
            else f"Nester (ueber Fenstergrenzen): {n_nestobjekte} gezeichnet"
        )
    if n_nest_rand:
        stat.append(f"davon am Zeitraumrand (angeschnitten): {n_nest_rand}")
    ax.text(
        0.5, 0.99, "\n".join(stat), transform=ax.transAxes, fontsize=7.5,
        va="top", ha="center", family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf6e3",
                  edgecolor="gray", alpha=0.94),
        zorder=20,
    )
    handles: List[Line2D] = [
        Line2D(
            [0], [0], color=_COL_ZONE, lw=6,
            alpha=(0.0 if stil.bereiche_zeichnen else 0.3),
            label=f"{_KURZ_MODUS[stil.modus]} "
                  f"({'Kontur' if stil.bereiche_zeichnen else 'VAL..VAH'})",
        ),
        Line2D([0], [0], color=_COL_POC, lw=1.4, label="POC (groesstes Segment)"),
        Line2D([0], [0], color=_COL_POC_U, lw=1.2, ls=(0, (2, 2)),
               label="POC unsicher + Band der Konsens-Parametersaetze"),
        Line2D([0], [0], color=_COL_NEST, lw=0.7, ls=(0, (4, 3)),
               label="POC weiterer Segmente"),
        Line2D([0], [0], color=_COL_KERZE_AUF, lw=5,
               label="Kerze auf (close >= open)"),
        Line2D([0], [0], color=_COL_KERZE_AB, lw=5,
               label="Kerze ab (close < open)"),
    ]
    if stil.bereiche_zeichnen:
        for rang, farbe in enumerate(_bereich_farben(3)):
            handles.insert(
                1 + rang,
                Line2D([0], [0], color=farbe, lw=6, alpha=0.45,
                       label=f"Bereich Segment {rang} "
                             f"(eigene {stil.bereich_va_txt}, VAL..VAH)"),
            )
        handles.append(
            Line2D([0], [0], color="#616161", lw=0.6, ls=(0, (1, 2)),
                   label="Luecke 'L <ATR>' = schneller Move zwischen zwei "
                         "Bereichen (kein Volumen)")
        )
    if nest_gezeichnet:
        handles.append(
            Line2D([0], [0], color=_COL_NEST_OBJ, lw=1.8,
                   label="Nest (zusammenhaengender Lauf ueber die "
                         "Fenstergrenze: EIN POC, EIN VAL..VAH)")
        )
    if n_nest_rand:
        handles.append(
            Line2D([0], [0], color=_COL_NEST_RAND, lw=1.0, ls=(0, (1, 1)),
                   label="Nest am Zeitraumrand 'Nm Rand' (angeschnitten)")
        )
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_png, dpi=stil.dpi)
    plt.close(fig)


# =============================================================================
# 2) PROFIL-GRID
# =============================================================================


def _zeichne_grid_seite(
    zeigen: Sequence[FensterProfil],
    stil: ChartStil,
    out_png: Path,
    seite: int = 1,
    n_seiten: int = 1,
    gesamt: Optional[int] = None,
    nester: Optional[Sequence[NestInstanz]] = None,
) -> None:
    """Zeichnet EINE Seite des Profil-Grids in eine PNG-Datei.

    Args:
        zeigen: Fensterprofile dieser Seite (nur gueltige).
        stil: Darstellungsparameter.
        out_png: Zielpfad der PNG-Datei dieser Seite.
        seite: Laufende Seitennummer (1-basiert, nur fuer den Titel).
        n_seiten: Gesamtzahl der Seiten (nur fuer den Titel).
        gesamt: Gesamtzahl gezeichneter Fenster (nur fuer den Titel).
        nester: Nester ueber Fenstergrenzen; je Panel werden die Level der
            Nester ueberlagert, die dieses Fenster beruehren (None = ohne).
    """
    if not zeigen:
        return
    n: int = len(zeigen)
    ncols: int = max(1, min(stil.ncols_grid, n))
    nrows: int = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(17.0, 3.1 * nrows), squeeze=False
    )

    for k, p in enumerate(zeigen):
        ax = axes[k // ncols][k % ncols]
        seg = p.segmentierung
        band = _band(p, stil)
        if seg is None or not (np.isfinite(band.val) and np.isfinite(band.vah)):
            ax.axis("off")
            continue
        prof = seg.profile
        centers = prof.centers
        vol = prof.vol
        vmax = float(vol.max()) if vol.size and vol.max() > 0 else 1.0
        bw = float(centers[1] - centers[0]) if centers.size > 1 else 1.0

        farben = np.array([_COL_OHNE_NEST] * centers.size, dtype=object)
        for i, (s, _pk, e) in enumerate(seg.mountains):
            farben[s : e + 1] = _PALETTE_NEST[i % len(_PALETTE_NEST)]
        ax.barh(centers, vol / vmax, height=bw * 0.86, color=list(farben), lw=0.0)

        ax.axhspan(band.val, band.vah, color=_COL_ZONE, alpha=0.10, zorder=0)
        # Getrennter Bereich je Segment: die Value Area des jeweiligen Berges
        # als eigene Flaeche. So ist im Panel sichtbar, wie eng der Bereich um
        # den Gipfel liegt und wo die Luecke zum Nachbarn beginnt.
        if stil.bereiche_zeichnen:
            for i, nest in enumerate(seg.nester):
                ax.axhspan(
                    nest.val, nest.vah,
                    color=_PALETTE_NEST[i % len(_PALETTE_NEST)],
                    alpha=0.16, zorder=0,
                )
        if (
            np.isfinite(p.konsens.poc_min)
            and np.isfinite(p.konsens.poc_max)
            and p.konsens.poc_max > p.konsens.poc_min
        ):
            ax.axhspan(p.konsens.poc_min, p.konsens.poc_max, color=_COL_POC_U,
                       alpha=0.18, zorder=1)
        ax.axhline(
            band.poc, color=(_COL_POC if p.konsens.eindeutig else _COL_POC_U),
            lw=1.3, ls=("-" if p.konsens.eindeutig else (0, (2, 2))), zorder=5,
        )
        for nest in seg.nester[1:]:
            ax.axhline(nest.poc, color=_COL_NEST, lw=0.7, ls=(0, (4, 3)), zorder=4)
        # Nester ueber Fenstergrenzen: die Level des Laufs, der DIESES Fenster
        # beruehrt - sie liegen ueber dem Fensterprofil und zeigen, dass der
        # Knoten nicht am Tageswechsel endet.
        beruehrte: List[NestInstanz] = [
            i for i in (nester or ())
            if i.gueltig and i.bar_ende >= int(p.bar_start)
            and i.bar_start <= int(p.bar_ende)
        ]
        for i in beruehrte:
            ax.axhspan(i.val, i.vah, color=_COL_NEST_OBJ, alpha=0.12, zorder=0)
            ax.axhline(i.poc, color=_COL_NEST_OBJ, lw=1.0, zorder=6)
        if beruehrte:
            ax.annotate(
                "Nest " + ", ".join(
                    f"N{i.id} {i.poc:.3f}" for i in beruehrte[:3]
                )
                + ("" if len(beruehrte) <= 3 else f" +{len(beruehrte) - 3}"),
                (0.02, 0.02), xycoords="axes fraction", fontsize=4.5,
                color=_COL_NEST_OBJ, va="bottom", ha="left", zorder=9,
            )
        if seg.lobe2_bin >= 0:
            lvl = float(
                (prof.edges[seg.lobe2_bin] + prof.edges[seg.lobe2_bin + 1]) / 2
            )
            ax.axhline(lvl, color=_COL_LOB2, lw=0.8, ls=(0, (1, 2)), zorder=3)

        ax.set_xlim(0.0, 1.12)
        ax.set_ylim(prof.pmin, prof.pmax)
        ax.tick_params(labelsize=6.0)
        ax.grid(alpha=0.25, axis="x")
        band_atr = band.breite / p.atr if p.atr > 0 else float("nan")
        band_txt = f"Band ({stil.modus})"
        # Anteil des Profilvolumens ausserhalb aller Bereiche: die Strecke
        # zwischen den Nestern (schnelle Moves) samt Bergflanken.
        sep_txt = ""
        if stil.bereiche_zeichnen:
            sep = zerlege_bereiche(seg, p.atr)
            if np.isfinite(sep.anteil_ausserhalb):
                sep_txt = f"ausserh. {sep.anteil_ausserhalb:.2f} | "
        ax.set_title(
            f"{p.label} | POC {band.poc:.3f}"
            f"{'' if p.konsens.eindeutig else '  SPANNE ' + _fmt(p.konsens.streu_atr, '.2f') + ' ATR'}\n"
            f"lobe2 {_fmt(seg.lobe2_ratio, '.2f')} | Segmente {seg.n_segmente} | "
            f"{sep_txt}"
            f"{band_txt} "
            f"{'-' if not np.isfinite(band_atr) else f'{band_atr:.1f}'} ATR | "
            f"Bars {p.bar_start}..{p.bar_ende}",
            fontsize=6.5,
            color=("#1b1b1b" if p.konsens.eindeutig else _COL_POC_U),
        )
        if k % ncols == 0:
            ax.set_ylabel(f"Preis ({stil.titel_symbol or 'Preis'})", fontsize=7.0)
    for k in range(n, nrows * ncols):
        axes[k // ncols][k % ncols].axis("off")

    n_unsicher = sum(1 for p in zeigen if not p.konsens.eindeutig)
    seiten_txt = "" if n_seiten <= 1 else f" | Seite {seite}/{n_seiten}"
    gesamt_txt = "" if gesamt is None or n_seiten <= 1 else f" (gesamt {gesamt})"
    fig.suptitle(
        f"FENSTERPROFILE (rel. Volumen, Maximum = 1) | {_stamm(stil)} | "
        f"Fensterart={zeigen[0].window_kind} | Fenster {n}{gesamt_txt}"
        f"{seiten_txt} | POC unsicher {n_unsicher}",
        fontsize=9.5, y=0.999,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color=_PALETTE_NEST[0], lw=6, label="Segment 0 (POC-Segment)"),
            Line2D([0], [0], color=_PALETTE_NEST[1], lw=6, label="Segment 1"),
            Line2D([0], [0], color=_PALETTE_NEST[2], lw=6, label="Segment 2"),
            Line2D([0], [0], color=_COL_OHNE_NEST, lw=6, label="keinem Segment zugeordnet"),
            Line2D([0], [0], color=_PALETTE_NEST[0], lw=6, alpha=0.16,
                   label=f"Bereich je Segment (eigene {stil.bereich_va_txt}, VAL..VAH)"),
            Line2D([0], [0], color=_COL_ZONE, lw=6, alpha=0.3,
                   label=f"{_KURZ_MODUS[stil.modus]} (Hauptband)"),
            Line2D([0], [0], color=_COL_POC, lw=1.3, label="POC"),
            Line2D([0], [0], color=_COL_POC_U, lw=1.3, ls=(0, (2, 2)),
                   label="POC unsicher"),
            Line2D([0], [0], color=_COL_POC_U, lw=6, alpha=0.18,
                   label="POC-Band (Konsens-Parametersaetze)"),
            Line2D([0], [0], color=_COL_LOB2, lw=0.8, ls=(0, (1, 2)),
                   label="Zweitgipfel-Niveau"),
            Line2D([0], [0], color=_COL_NEST_OBJ, lw=1.0,
                   label="Nest ueber Fenstergrenzen (POC, VAL..VAH dieses "
                         "Fensters)"),
        ],
        loc="lower center", ncol=11, fontsize=7.0, framealpha=0.9,
    )
    fig.tight_layout(rect=(0.0, 0.02, 1.0, 0.985))
    fig.savefig(out_png, dpi=stil.dpi)
    plt.close(fig)


def zeichne_profil_grid(
    profile: Sequence[FensterProfil],
    stil: ChartStil,
    out_png: Path,
    nester: Optional[Sequence[NestInstanz]] = None,
) -> List[Path]:
    """Zeichnet je Fenster das Volumenprofil als eigenes Panel.

    Das relative Volumen (Maximum = 1) wird horizontal aufgetragen; die Bins
    sind nach Segmentzugehoerigkeit eingefaerbt. Damit ist direkt pruefbar, ob
    die Berg-Zerlegung plausibel ist. Zonen-VA-Band, POC (gestrichelt bei
    Unsicherheit), POC-Band und Zweitgipfel-Niveau werden ueberlagert.

    Gezeigt wird der GANZE Testzeitraum (``max_profile=0``). Ergibt das mehr
    Panels als ``stil.seiten_max``, wird seitenweise ausgegeben
    (``<stamm>_s1.png``, ``<stamm>_s2.png``, ...) - es wird nichts weggelassen.

    Args:
        profile: Fensterprofile (nur gueltige werden gezeichnet).
        stil: Darstellungsparameter.
        out_png: Zielpfad der PNG-Datei (bei mehreren Seiten Namensstamm).
        nester: Nester ueber Fenstergrenzen; die Level der Nester, die ein
            Panel beruehren, werden dort ueberlagert (None = ohne).

    Returns:
        Liste der tatsaechlich geschriebenen PNG-Pfade (leer, wenn nichts zu
        zeichnen war).
    """
    zeigen: List[FensterProfil] = [p for p in profile if p.gueltig]
    if stil.max_profile > 0:
        zeigen = zeigen[-stil.max_profile :]
    if not zeigen:
        return []

    bloecke: List[List[FensterProfil]]
    if stil.seiten_max > 0 and len(zeigen) > stil.seiten_max:
        bloecke = [
            list(zeigen[i : i + stil.seiten_max])
            for i in range(0, len(zeigen), stil.seiten_max)
        ]
    else:
        bloecke = [list(zeigen)]

    pfade: List[Path] = []
    if len(bloecke) == 1:
        _zeichne_grid_seite(bloecke[0], stil, out_png, nester=nester)
        return [out_png]
    for i, block in enumerate(bloecke, start=1):
        p = out_png.with_name(f"{out_png.stem}_s{i}{out_png.suffix}")
        _zeichne_grid_seite(block, stil, p, seite=i, n_seiten=len(bloecke),
                            gesamt=len(zeigen), nester=nester)
        pfade.append(p)
    return pfade


def zeichne_alles(
    df: pd.DataFrame,
    profile: Sequence[FensterProfil],
    stil: ChartStil,
    out_stamm: Path,
    nester: Optional[Sequence[NestInstanz]] = None,
) -> Tuple[Optional[Path], List[Path]]:
    """Zeichnet beide Ausgaben und liefert die tatsaechlich erzeugten Pfade.

    Args:
        df: Bars des Gesamtfensters.
        profile: Fensterprofile.
        stil: Darstellungsparameter.
        out_stamm: Zielpfad-Stamm; es entstehen ``<stamm>_zonen.png`` und
            ``<stamm>_profile.png`` (bzw. ``_s1``, ``_s2``, ... bei mehreren
            Seiten, siehe ``ChartStil.seiten_max``).
        nester: Nester ueber Fenstergrenzen (die eigentlichen Knoten); sie
            werden im Zonen-Chart als durchgehendes Band mit eigener POC-Linie
            gezeichnet und im Grid je Panel ueberlagert (None = ohne).

    Returns:
        ``(zonen_png, profil_pngs)``; ``zonen_png`` ist ``None`` und die Liste
        leer, wenn nichts gezeichnet werden konnte.
    """
    out_stamm.parent.mkdir(parents=True, exist_ok=True)
    p_zone = out_stamm.with_name(out_stamm.name + "_zonen.png")
    p_grid = out_stamm.with_name(out_stamm.name + "_profile.png")
    if not any(p.gueltig for p in profile):
        return None, []
    zeichne_zonen_chart(df, profile, stil, p_zone, nester=nester)
    return p_zone, zeichne_profil_grid(profile, stil, p_grid, nester=nester)
