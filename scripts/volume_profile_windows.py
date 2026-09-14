"""
VOLUMENPROFIL-FENSTER (scripts/volume_profile_windows.py)
==========================================================
Zerlegt die BKZ-Zeitachse in die Zeitfenster, fuer die je ein Volumenprofil
gerechnet wird. Kein I/O, kein Plot, keine Volume-Logik - dieses Modul
liefert nur Fensterdefinitionen (Bar-Grenzen + Label).

Unterstuetzte Fensterarten
--------------------------
    day     BKZ-Kalendertag 00:00 - 23:59 (Handelssession des Brokers)
    week    ISO-Woche, Montag 00:00 bis Sonntag 23:59 (BKZ)
    h12     12-Stunden-Block, Anker 00:00 BKZ  -> [00:00-12:00), [12:00-24:00)
    h4      4-Stunden-Block,  Anker 00:00 BKZ  -> 6 Bloecke je Tag
    h1      1-Stunden-Block,  Anker 00:00 BKZ
    m30     30-Minuten-Block, Anker 00:00 BKZ

Mehrere Profile je Tag sind damit ausdruecklich moeglich (h12 -> 2, h4 -> 6,
h1 -> 24): jeder Block ist ein eigenes Fenster mit eigenem Profil.

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Alle Grenzen liegen auf der BKZ-Achse (``time AT TIME ZONE 'UTC'``, tz-naiv).
Es findet KEINE Projektion auf ``Europe/Berlin``/``Europe/Budapest`` statt
(K2), und es wird kein Terminologie-Verbot verletzt (K3). Die Grenzen werden
dynamisch per ``searchsorted`` gegen die BKZ-Zeitstempel gebildet (K6) -
niemals als Bar-Konstante hartcodiert.

Aufruf (aus einem Orchestrator):
    from scripts.volume_profile_windows import FensterSpec, baue_fenster
    fenster = baue_fenster(df, FensterSpec(art="h4"))
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Erlaubte Fensterarten -> (Blocklaenge in Stunden fuer Intraday, None sonst)
FENSTER_ARTEN: Dict[str, float] = {
    "day": 24.0,
    "week": 0.0,
    "h12": 12.0,
    "h4": 4.0,
    "h1": 1.0,
    "m30": 0.5,
}

# Nominale Dauer je Fensterart in Stunden (Basis der Mindest-Bars-Ableitung).
# ``week`` = 7 Tage, ``day`` = 24 h; die Intraday-Arten sind ihre Blocklaenge.
FENSTER_STUNDEN: Dict[str, float] = {
    "day": 24.0,
    "week": 168.0,
    "h12": 12.0,
    "h4": 4.0,
    "h1": 1.0,
    "m30": 0.5,
}

# Dauer je Timeframe-Einheit in Stunden (fuer ``min_bars_fuer``).
_TF_EINHEIT_STUNDEN: Dict[str, float] = {
    "M": 1.0 / 60.0,  # Minute
    "H": 1.0,         # Stunde
    "D": 24.0,        # Tag
    "W": 168.0,       # Woche
}

# Wochentag-Abstand zum Wochenanfang (Montag) im ISO-Kalender
_WOCHEN_TAG_OFFSET: Dict[str, int] = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6,
}


@dataclass(frozen=True, slots=True)
class FensterSpec:
    """Beschreibung der zu bildenden Zeitfenster.

    Attributes:
        art: Fensterart aus ``FENSTER_ARTEN`` (Default ``day``).
        min_bars: Mindestzahl Bars, damit ein Fenster als auswertbar gilt.
        label_format: strftime-Format fuer das Fensterlabel. Enthaelt es
            keine Stunde, wird bei Intraday-Arten automatisch ``%H``
            angehaengt, damit Labels eindeutig bleiben.
    """

    art: str = "day"
    min_bars: int = 40
    label_format: str = "%Y-%m-%d"


@dataclass(frozen=True, slots=True)
class Fenster:
    """Ein Zeitfenster auf der BKZ-Achse.

    Attributes:
        label: Eindeutiges Label (z. B. ``2026-08-03`` oder ``2026-08-03 04``).
        art: Fensterart.
        bar_start: Erster Bar-Index im Fenster-DataFrame.
        bar_ende: Letzter Bar-Index (inklusiv).
        ts_start: Erster BKZ-Zeitstempel des Fensters.
        ts_ende: Letzter BKZ-Zeitstempel des Fensters.
        n_bars: Anzahl Bars im Fenster.
    """

    label: str
    art: str
    bar_start: int
    bar_ende: int
    ts_start: pd.Timestamp
    ts_ende: pd.Timestamp
    n_bars: int


def _fenster_label(ts: pd.Timestamp, spec: FensterSpec) -> str:
    """Bildet das Label eines Fensters.

    Args:
        ts: Fenster-Start (BKZ).
        spec: Fensterspezifikation.

    Returns:
        Eindeutiges Label; bei Intraday-Arten mit Stunde.
    """
    fmt = spec.label_format
    if spec.art != "day" and spec.art != "week" and "%H" not in fmt:
        fmt = fmt + " %H"
    return ts.strftime(fmt)


def _grenzen(spec: FensterSpec, t_start: pd.Timestamp, t_ende: pd.Timestamp) -> List[pd.Timestamp]:
    """Erzeugt die Fenster-Startzeitpunkte auf der BKZ-Achse.

    Args:
        spec: Fensterspezifikation.
        t_start: Beginn der BKZ-Achse (erster Bar).
        t_ende: Ende der BKZ-Achse (letzter Bar).

    Returns:
        Aufsteigende Liste der Fenster-Startzeitpunkte.
    """
    if spec.art == "week":
        # Montag 00:00 BKZ: Tagesbeginn minus Wochentagsabstand.
        tag0 = t_start.normalize()
        offset = _WOCHEN_TAG_OFFSET[tag0.day_name()]
        erster = tag0 - pd.Timedelta(days=offset)
        return list(pd.date_range(erster, t_ende, freq="7D"))

    stunden = FENSTER_ARTEN[spec.art]
    if spec.art == "day":
        return list(pd.date_range(t_start.normalize(), t_ende, freq="D"))

    block = pd.Timedelta(hours=stunden)
    # Anker 00:00 BKZ: ab Tagesbeginn in Blocklaengen fortschreiten.
    erster = t_start.normalize()
    return list(pd.date_range(erster, t_ende, freq=block))


def baue_fenster(df: pd.DataFrame, spec: FensterSpec) -> List[Fenster]:
    """Zerlegt das Fenster-DataFrame in die Zeitfenster der Spezifikation.

    Die Bar-Grenzen werden dynamisch per ``searchsorted`` auf der BKZ-Achse
    bestimmt (Kanon K6). Leere Fenster (z. B. Wochenende, handelsfreie
    Bloecke) entfallen.

    Args:
        df: Bars mit Spalte ``ts`` (BKZ, tz-naiv, aufsteigend sortiert).
        spec: Fensterspezifikation.

    Returns:
        Chronologische Liste ``Fenster``. Die Mindest-Bars-Pruefung erfolgt
        NICHT hier (die Fenster werden vollstaendig geliefert, damit der
        Aufrufer Verwurf und Auswertung getrennt berichten kann).

    Raises:
        ValueError: Bei leerem DataFrame oder unbekannter Fensterart.
    """
    if spec.art not in FENSTER_ARTEN:
        raise ValueError(
            f"Unbekannte Fensterart {spec.art!r}. Erlaubt: "
            f"{sorted(FENSTER_ARTEN)}"
        )
    if df.empty:
        raise ValueError("Leerer DataFrame - keine Fenster bildbar.")

    ts: np.ndarray = df["ts"].values.astype("datetime64[ns]")
    t_start = pd.Timestamp(ts[0])
    t_ende = pd.Timestamp(ts[-1])
    out: List[Fenster] = []

    for start in _grenzen(spec, t_start, t_ende):
        if spec.art == "week":
            ende = start + pd.Timedelta(days=7)
        elif spec.art == "day":
            ende = start + pd.Timedelta(days=1)
        else:
            ende = start + pd.Timedelta(hours=FENSTER_ARTEN[spec.art])
        i0 = int(np.searchsorted(ts, np.datetime64(start), side="left"))
        i1 = int(np.searchsorted(ts, np.datetime64(ende), side="left")) - 1

        if i1 < i0:
            continue  # kein Bar in diesem Block (z. B. Wochenende)
        out.append(
            Fenster(
                label=_fenster_label(start, spec),
                art=spec.art,
                bar_start=i0,
                bar_ende=i1,
                ts_start=pd.Timestamp(ts[i0]),
                ts_ende=pd.Timestamp(ts[i1]),
                n_bars=int(i1 - i0 + 1),
            )
        )
    return out


def fenster_arten() -> Tuple[str, ...]:
    """Liefert die unterstuetzten Fensterarten.

    Returns:
        Alphabetisch sortierte Namen der Fensterarten.
    """
    return tuple(sorted(FENSTER_ARTEN))


def timeframe_stunden(timeframe: str) -> float:
    """Rechnet einen Timeframe-Namen in seine Dauer in Stunden um.

    Erwartet die Schreibweise ``<Einheit><Zahl>`` oder ``<Zahl><Einheit>`` mit
    Einheit ``M`` (Minute), ``H`` (Stunde), ``D`` (Tag) oder ``W`` (Woche),
    z. B. ``M15`` = 0,25 h, ``H4`` = 4 h, ``D1`` = 24 h.

    Args:
        timeframe: Timeframe-Name (z. B. ``M15``).

    Returns:
        Dauer in Stunden.

    Raises:
        ValueError: Bei unbekanntem Timeframe.
    """
    tf = str(timeframe).strip().upper()
    if not tf:
        raise ValueError("timeframe darf nicht leer sein.")
    einheit = tf[0]
    zahl_txt = tf[1:] if einheit in _TF_EINHEIT_STUNDEN else tf[:-1]
    einheit = einheit if einheit in _TF_EINHEIT_STUNDEN else tf[-1]
    try:
        zahl = float(zahl_txt)
    except ValueError as exc:
        raise ValueError(f"Timeframe nicht lesbar: {timeframe!r}") from exc
    if zahl <= 0:
        raise ValueError(f"Timeframe-Zahl muss > 0 sein: {timeframe!r}")
    return zahl * _TF_EINHEIT_STUNDEN[einheit]


def min_bars_fuer(
    art: str,
    timeframe: str,
    min_abdeckung: float = 0.5,
    minimum: int = 3,
) -> int:
    """Leitet die Mindest-Bars eines Fensters aus Fensterart und Timeframe ab.

    Damit wird ueber alle Timeframes hinweg IMMER dieselbe Groesse untersucht:
    gefordert ist ein Anteil ``min_abdeckung`` der NOMINALEN Dauer des Fensters
    (day = 24 h, week = 168 h, h4 = 4 h, ...), nicht eine feste Bar-Anzahl.

        M15, day  -> 24 h * 0,5 / 0,25 h = 48 Bars
        H1,  day  -> 24 h * 0,5 / 1 h    = 12 Bars
        M15, h4   ->  4 h * 0,5 / 0,25 h =  8 Bars

    Args:
        art: Fensterart aus ``FENSTER_ARTEN``.
        timeframe: Timeframe-Name (z. B. ``M15``).
        min_abdeckung: Geforderter Anteil der nominalen Fensterdauer (0..1).
        minimum: Absolute Untergrenze (ein Profil braucht >= 3 Bins).

    Returns:
        Mindestzahl Bars.

    Raises:
        ValueError: Bei unbekannter Fensterart oder unzulaessigem Anteil.
    """
    if art not in FENSTER_STUNDEN:
        raise ValueError(
            f"Unbekannte Fensterart {art!r}. Erlaubt: {sorted(FENSTER_STUNDEN)}"
        )
    if not 0.0 < min_abdeckung <= 1.0:
        raise ValueError(
            f"min_abdeckung muss im Intervall (0, 1] liegen: {min_abdeckung!r}"
        )
    dauer_fenster = FENSTER_STUNDEN[art]
    dauer_bar = timeframe_stunden(timeframe)
    return max(int(minimum), int(np.ceil(dauer_fenster * min_abdeckung / dauer_bar)))
