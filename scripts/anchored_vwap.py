"""
scripts/anchored_vwap.py - Zustandslose AVWAP-Berechnung (Setup C, Pfad A)
==========================================================================
Status: NEU (Freigabe-Gate erteilt 06.09.2026) - entkoppeltes Hilfsmodul.

Zweck
-----
Berechnet den volumengewichteten Durchschnittspreis ab einem frei waehlbaren
Anker-Index (Anchored VWAP) vollstaendig vektorisiert und zustandslos.  Die
Interpretation (Kontakt/Rejection/Einstieg) liegt bewusst NICHT hier, sondern
in der Engine/den Zwischentests (Consumer-Disziplin): dieses Modul liefert
ausschliesslich den float64-Vektor ``avwap[k]`` fuer ``k in [0, n)``.

Anchor-Semantik (inklusive, verbindlich):
  - Bar ``k = anchor_idx`` gehoert zur AVWAP-Positionierung (inklusive
    Ausbruchs-Bar bei der Pfad-A-Nutzung: Anker ``b = brk_idx``).
  - Fuer ``k < anchor_idx`` ist ``avwap[k] = NaN`` (kein Rueckblick).
  - Ab ``k >= anchor_idx`` kumuliert der Vektor strikt kausal ueber alle
    Bars ``[anchor_idx .. k]`` (kein Fenster-Reset an Phasengrenzen - die
    Ankerwahl bestimmt die Bezugsbasis).

Null-Volumen-Schutz (wasserdicht):
  - Beitraege fliessen nur fuer endliche, strikt positive Volumina
    (``V_k > 0``); NaN/negativ/null tragen weder zum Zaehler noch zum
    Nenner bei.
  - Solange der kumulierte Nenner ``<= 0`` ist, bleibt ``avwap[k] = NaN``
    (erste positive Volumen-Bar nach dem Anker initialisiert die Kette).
  - Die kumulative Kette wird durch Null-/NaN-Volumen-Bars nie verseucht:
    eine Bar mit ``V_k == 0`` veraendert das Verhaeltnis nicht (Zaehler und
    Nenner addieren 0), eine NaN-Bar kann den Vektor nicht vergiften.

Formel (je Bar ``k >= anchor_idx``):
    avwap[k] = sum_{j=anchor_idx..k} (preis_j * V_j) / sum_{j=anchor_idx..k} V_j

    preis_j: "typisch" = (high + low + close) / 3 (Standard)
             "close"   = close_j
             "open"    = open_j

Wichtig: Die Funktion ist rein lesend bzgl. ``df`` (defensive Kopie nur der
benoetigten Spalten als NumPy-Sicht; keine Mutation des Frames).

Vektorisierungs-Regel (Agents.md): keine Schleifen in der Berechnung.
"""
from __future__ import annotations

from typing import Literal, Union

import numpy as np
import pandas as pd

#: Erlaubte Preis-Basis der AVWAP-Berechnung (extern konfigurierbar).
PreisModus = Literal["typisch", "close", "open"]

_EPS: float = 1e-12


def _preis_vektor(
    df: pd.DataFrame,
    preis_modus: Union[PreisModus, str] = "typisch",
) -> np.ndarray:
    """Extrahiert den Preis-Vektor je Preis-Modus (float64, Kopie).

    Args:
        df: OHLCV-Frame (Spalten ``open/high/low/close`` vorhanden).
        preis_modus: "typisch" = (H+L+C)/3, sonst "close" oder "open".

    Returns:
        float64-``np.ndarray`` der Laenge ``len(df)``.

    Raises:
        ValueError: Bei unbekanntem ``preis_modus``.
    """
    if preis_modus == "typisch":
        high: np.ndarray = df["high"].to_numpy(dtype=float)
        low: np.ndarray = df["low"].to_numpy(dtype=float)
        close: np.ndarray = df["close"].to_numpy(dtype=float)
        return (high + low + close) / 3.0
    if preis_modus == "close":
        return df["close"].to_numpy(dtype=float)
    if preis_modus == "open":
        return df["open"].to_numpy(dtype=float)
    raise ValueError(
        f"Unbekannter preis_modus={preis_modus!r}; erlaubt: 'typisch', 'close', 'open'"
    )


def berechne_avwap_vektor(
    df: pd.DataFrame,
    anchor_idx: int,
    preis_modus: Union[PreisModus, str] = "typisch",
    volumen_spalte: str = "tick_volume",
) -> np.ndarray:
    """Berechnet den Anchored-VWAP-Vektor ab ``anchor_idx`` (inklusive).

    Rein vektorisiert (kumulative Summen ueber ``np.cumsum``), keine Schleife.
    AVWAP an Bar ``k`` nutzt ausschliesslich Bars ``[anchor_idx .. k]``
    (strikt kausal). Bars vor dem Anker sowie Bars ohne positives Volumen
    liefern ``NaN`` bzw. tragen nichts bei (Null-Volumen-Schutz wasserdicht).

    Args:
        df: OHLCV-Frame mit aufsteigender ``ts`` und den Spalten
            ``open/high/low/close`` sowie ``volumen_spalte``.
        anchor_idx: Inklusiver Start-Index der Positionierung (Bar
            ``anchor_idx`` gehoert zur AVWAP-Basis). Wird auf
            ``[0, n-1]`` geklemmt; ``anchor_idx >= n`` ergibt All-NaN.
        preis_modus: Preis-Basis (Standard "typisch" = (H+L+C)/3).
        volumen_spalte: Name der Volumen-Spalte im Frame (Standard
            ``tick_volume``).

    Returns:
        float64-``np.ndarray`` der Laenge ``n = len(df)`` mit
        ``avwap[k] = NaN`` fuer ``k < anchor_idx`` oder kumuliertem
        Volumen ``<= 0``, sonst dem kumulativen Volumen-Preis-Mittel.

    Raises:
        KeyError: Wenn ``volumen_spalte`` oder OHLC-Spalten fehlen.
        ValueError: Bei unbekanntem ``preis_modus``.
    """
    n: int = len(df)
    if n == 0:
        return np.empty(0, dtype=np.float64)

    b: int = int(anchor_idx)
    if b < 0:
        b = 0
    if b >= n:
        return np.full(n, np.nan, dtype=np.float64)

    vol: np.ndarray = df[volumen_spalte].to_numpy(dtype=float)
    preis: np.ndarray = _preis_vektor(df, preis_modus)

    # Volumen-Beitraege: nur endlich und strikt positiv (Null-Volumen-Schutz).
    vol_ok: np.ndarray = np.isfinite(vol) & (vol > 0.0)
    vol_c: np.ndarray = np.where(vol_ok, vol, 0.0)
    # Preis * V nur fuer aktive Bars (verhindert NaN-Verseuchung des Zaehlers).
    pv_c: np.ndarray = np.where(vol_ok, preis * vol, 0.0)

    # Anker-Maske: Beitraege erst ab Bar b (inklusive).
    idx_arr: np.ndarray = np.arange(n, dtype=np.int64)
    ab_anker: np.ndarray = idx_arr >= b

    cum_pv: np.ndarray = np.cumsum(np.where(ab_anker, pv_c, 0.0))
    cum_v: np.ndarray = np.cumsum(np.where(ab_anker, vol_c, 0.0))

    out: np.ndarray = np.full(n, np.nan, dtype=np.float64)
    gueltig: np.ndarray = ab_anker & (cum_v > _EPS)
    out[gueltig] = cum_pv[gueltig] / cum_v[gueltig]
    return out
