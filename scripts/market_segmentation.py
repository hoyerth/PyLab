"""
Markt-Segmentierung: Phasen-Etablierung, 2-Close-Ausbruch & Moves.

Extraktions-Modul der kausalen Segmentierungs-Logik aus der eingefrorenen
Produktions-Baseline `scripts/phasen_volumen_profil.py` (v0.4.0-baseline-frozen,
+297,14R) - Abschnitt 4/4b (Z. 610-797). 1:1-Uebernahme ohne funktionale
Veraenderung: Saemtliche Toleranzen, Lookbacks und Schwellenwerte sind
unveraendert und werden ausschliesslich ueber `SegmentConfig` transportiert
(keine losen Modul-Globals).

Bewusst AUSGELASSEN (Setup-B-Ballast, Abschnitt 5 der Baseline): Candle-
Statistik, Volume-Zonen, `handelbar`-Filter sowie alle davon abgeleiteten
`PhaseData`-Felder (Gruppe B/C, Entscheidung F1 aus §2.14).

KAUSALITAET (unveraendert aus der Baseline):
- Pivot-Bestaetigung nachlaufend (Lag `pivot_lookback`).
- Geburtszone nur mit bestaetigten Pivots (cutoff am Phasenstart).
- Kausale Linien-Etablierung bar fuer bar (kein Lookahead ueber die finale
  Phasen-Huellkurve).
- Regel-7-Finalize (letzter Grenz-Kontakt) ist POST-HOC am Datenende.

Datenherkunft: DuckDB `read_only=True` (Wanduhr-Garantie: `time AT TIME ZONE
'UTC'`, keine stille Lokalzeit-Konvertierung).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

__all__ = [
    "SegmentConfig",
    "SegmentResult",
    "PhaseData",
    "MoveData",
    "load_data",
    "find_pivots",
    "segmentiere_markt",
]


@dataclass(frozen=True, slots=True)
class SegmentConfig:
    """Segmentierungs-Konfiguration (frozen, verbindlicher Datenvertrag).

    Alle Defaults entsprechen 1:1 den Modul-Konstanten der eingefrorenen
    Baseline (``scripts/phasen_volumen_profil.py`` Z. 199-214). Keine dieser
    Groessen darf ohne sofortigen L1-Gate-Bruch (§2.14) veraendert werden.

    Attributes:
        db_path: DuckDB-Datei (Default = zentrale Produktions-DB unter
            ``data/market_data.duckdb``, aufgeloest relativ zu diesem Modul).
        start: Fenster-Start (ISO-Datum, inklusive).
        ende: Fenster-Ende (ISO-Datum, exklusive).
        tol: 2-Close-Ausbruchs-Toleranz (Baseline ``TOL``).
        tol_touch: Touch-Toleranz fuer Move-Ende (Baseline ``TOL_TOUCH``).
        min_cluster: Min. Dichte-Kluster in Schnittmengen-Linie (``MIN_CLUSTER``).
        min_establish: Min. Touches bis Phasen-Etablierung (``MIN_ESTABLISH``).
        min_phase_candles: Min. Phasenlaenge ab Start (``MIN_PHASE_CANDLES``).
        density_band: Dichte-Band fuer Linien/Touches (``DENSITY_BAND``).
        erweiterung_pct: Erweiterungs-Pool in Schnittmengen-Linie
            (``ERWEITERUNG_PCT``, Prozent).
        shift_tol: Min. Kanten-Shift fuer Hist-Protokollierung (``SHIFT_TOL``).
        grenz_kontakt_tol: Toleranz letzter Grenz-Kontakt (``GRENZ_KONTAKT_TOL``).
        fenster_pivots: Max. Pivot-Fenster in ``_linie`` (``FENSTER_PIVOTS``).
        pivot_lookback: Pivot-Bestaetigungs-Lag (``PIVOT_LOOKBACK``).
    """

    db_path: Path = (
        Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
    )
    start: str = "2026-08-10"
    ende: str = "2026-08-28"

    # --- Segmentierung (Baseline Z. 201-214) ---
    tol: float = 0.34
    tol_touch: float = 0.15
    min_cluster: int = 2
    min_establish: int = 4
    min_phase_candles: int = 46
    density_band: float = 0.15
    erweiterung_pct: float = 1.0
    shift_tol: float = 0.05
    grenz_kontakt_tol: float = 0.0
    fenster_pivots: int = 100
    pivot_lookback: int = 2


@dataclass(slots=True)
class PhaseData:
    """Eine segmentierte Markt-Phase (19 Kernfelder, Gruppe A).

    Feldreihenfolge und Typdefinitionen exakt aus Baseline Z. 98-116; alle
    Felder ohne Default-Werte (rein positional), wie in der Baseline.
    Gruppe B/C (Candle-Statistik, Volume-Zonen) ist bewusst NICHT uebernommen
    (Setup-B-Ballast, Entscheidung F1 in §2.14).

    Kausalitaet: ``break_dir``/``brk_idx``/``brk_kante`` beschreiben den
    2-Close-Ausbruch; ``U_hist``/``L_hist`` protokollieren Kanten-Shifts mit
    Zeitstempel (kausale Kantenreihe fuer Replay ohne Lookahead).
    """

    start: pd.Timestamp
    ende: pd.Timestamp
    U_final: Optional[float]
    L_final: Optional[float]
    h_prices: List[float]
    l_prices: List[float]
    h_ts: List[pd.Timestamp]
    l_ts: List[pd.Timestamp]
    birth_h: Optional[float]
    birth_l: Optional[float]
    U_conf_ts: Optional[pd.Timestamp]
    L_conf_ts: Optional[pd.Timestamp]
    U_ts: Optional[pd.Timestamp]
    L_ts: Optional[pd.Timestamp]
    U_hist: List[Tuple[pd.Timestamp, float]]
    L_hist: List[Tuple[pd.Timestamp, float]]
    break_dir: Optional[Literal["up", "down"]]
    brk_idx: Optional[int]
    brk_kante: Optional[float]


@dataclass(slots=True)
class MoveData:
    """Gegenbewegung zwischen letztem Grenz-Kontakt und Phasen-Ausbruch."""

    dir: Literal["up", "down"]
    von_ts: pd.Timestamp
    von_pr: Optional[float]
    bis_ts: pd.Timestamp
    bis_pr: float


@dataclass(slots=True)
class SegmentResult:
    """Ergebnis der Markt-Segmentierung.

    Attributes:
        df: OHLCV-Bars (defensive Kopie) inkl. ergaenzter ``is_pivot``-Spalte.
        phases: Segmentierte Phasen (chronologisch).
        moves: Moves (Gegenbewegungen an Phasen-Uebergaengen).
    """

    df: pd.DataFrame
    phases: List[PhaseData]
    moves: List[MoveData]


# =============================================================================
# 1) DATEN EINLESEN (Strikt DuckDB, verbatim aus Baseline Z. 320-335)
# =============================================================================


def load_data(db_path: Path, start: str, ende: str) -> pd.DataFrame:
    """Liest OHLCV-Bars strikt aus DuckDB (``read_only=True``).

    SQL und Zeitbehandlung 1:1 aus der Baseline (Z. 320-335):
    ``time AT TIME ZONE 'UTC'`` (Wanduhr-Garantie), Entnaivisierung nach UTC,
    numerische ``idx``-Spalte. Symbol/Timeframe sind wie in der Baseline fest
    auf ``SILVER``/``M15`` verdrahtet (keine funktionale Verwässerung).

    Args:
        db_path: Pfad zur DuckDB-Datei.
        start: Fenster-Start (ISO-Datum, inklusive).
        ende: Fenster-Ende (ISO-Datum, exklusive).

    Returns:
        DataFrame mit Spalten ``ts/open/high/low/close/tick_volume/idx``,
        aufsteigend nach Zeit sortiert, ``ts`` tz-naiv (UTC).

    Raises:
        FileNotFoundError: Wenn ``db_path`` nicht existiert.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB-Datei nicht gefunden: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    d = con.execute(
        f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
        """
    ).fetchdf()
    con.close()
    d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    d["idx"] = np.arange(len(d))
    return d


# =============================================================================
# 2) PIVOTS (verbatim aus Baseline Z. 343-359)
# =============================================================================


def find_pivots(d: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    """Findet nachlaufend bestaetigte Swing-Pivots (Lag ``n``).

    Args:
        d: OHLCV-Bars (Spalten ``ts/high/low``).
        n: Pivot-Bestaetigungs-Lookback (Baseline-Default ``PIVOT_LOOKBACK``).

    Returns:
        DataFrame mit Spalten ``ts/price/typ`` (typ = ``"H"``/``"L"``),
        nur bestaetigte Pivot-Bars.
    """
    h: np.ndarray = d["high"].values
    l: np.ndarray = d["low"].values
    hi = pd.Series(h)
    lo = pd.Series(l)
    is_hi = (hi == hi.rolling(2 * n + 1, center=True, min_periods=1).max()) & (
        hi.shift(n) < h
    ) & (hi.shift(-n) < h)
    is_lo = (lo == lo.rolling(2 * n + 1, center=True, min_periods=1).min()) & (
        lo.shift(n) > l
    ) & (lo.shift(-n) > l)
    is_hi[:n] = False
    is_hi[-n:] = False
    is_lo[:n] = False
    is_lo[-n:] = False
    piv_df = pd.DataFrame(
        {
            "ts": d["ts"],
            "price": np.where(is_hi, h, np.where(is_lo, l, np.nan)),
            "typ": np.where(is_hi, "H", np.where(is_lo, "L", "")),
        }
    )
    return piv_df[piv_df["typ"] != ""].copy()


# =============================================================================
# 3) PRIVATE HILFSROUTINEN (Schnittmengen-Linie, verbatim aus Baseline Z. 368-472)
#    Alle Schwellenwerte kommen ausschliesslich aus `SegmentConfig`.
# =============================================================================


def _level_schnittmenge(
    prices: List[float] | np.ndarray,
    target_typ: Literal["H", "L"],
    config: SegmentConfig,
) -> Optional[float]:
    """Berechnet die Schnittmengen-Linie (verbatim Baseline Z. 368-402).

    Args:
        prices: Preis-Treffer (Highs fuer ``"H"``, Lows fuer ``"L"``).
        target_typ: Zielrichtung der Kante.
        config: Segmentierungs-Konfiguration.

    Returns:
        Linien-Level oder ``None`` bei leerer Eingabe.
    """
    arr = np.array(prices, dtype=float)
    if not len(arr):
        return None
    d = np.array([np.sum(np.abs(arr - x) <= config.density_band) for x in arr])
    m = d >= config.min_cluster
    if not m.any():
        return float(np.max(arr)) if target_typ == "H" else float(np.min(arr))
    sel = arr[m]
    ext = float(np.max(sel)) if target_typ == "H" else float(np.min(sel))
    kern = sel[np.abs(sel - ext) <= config.density_band]
    if not len(kern):
        kern = sel
    if target_typ == "H":
        kante = float(np.min(kern))
        pool = sel[sel >= kante - config.density_band]
        pool = pool[pool <= kante * (1 + config.erweiterung_pct / 100.0)]
    else:
        kante = float(np.max(kern))
        pool = sel[sel <= kante + config.density_band]
        pool = pool[pool >= kante * (1 - config.erweiterung_pct / 100.0)]
    if not len(pool):
        pool = kern
    if len(pool) > 1:
        if target_typ == "H":
            pool = pool[pool != np.max(pool)]
        else:
            pool = pool[pool != np.min(pool)]
    return float(np.mean(pool)) if len(pool) else float(np.mean(kern))


def _n_touches(
    prices: List[float] | np.ndarray,
    level: Optional[float],
    config: SegmentConfig,
) -> int:
    """Zaehlt Preise innerhalb des Dichte-Bands um ein Level.

    Args:
        prices: Preis-Treffer.
        level: Referenz-Level (``None`` ergibt 0).
        config: Segmentierungs-Konfiguration.

    Returns:
        Anzahl der Touches.
    """
    if level is None or not len(prices):
        return 0
    return int(
        np.sum(np.abs(np.array(prices, dtype=float) - level) <= config.density_band)
    )


def _linie(
    prices: List[float],
    typ: Literal["H", "L"],
    config: SegmentConfig,
) -> Optional[float]:
    """Schnittmengen-Linie ueber max. ``fenster_pivots`` Preisen.

    Args:
        prices: Preis-Treffer (Highs/Lows).
        typ: Zielrichtung.
        config: Segmentierungs-Konfiguration.

    Returns:
        Linien-Level oder ``None`` bei leerer Eingabe.
    """
    if not prices:
        return None
    w = prices if len(prices) <= config.fenster_pivots else prices[-config.fenster_pivots :]
    return _level_schnittmenge(w, typ, config)


def _final_level(
    schnitt: Optional[float],
    birth: Optional[float],
    typ: Literal["H", "L"],
) -> Optional[float]:
    """Kombiniert Schnittmengen-Linie mit Geburts-Level (Baseline Z. 418-423).

    Args:
        schnitt: Schnittmengen-Linie (oder ``None``).
        birth: Geburts-Level (oder ``None``).
        typ: Richtung (``"H"`` = Maximum, ``"L"`` = Minimum).

    Returns:
        Angewandtes Level.
    """
    if schnitt is None:
        return birth
    if birth is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _final_level_bestaetigt(
    schnitt: Optional[float],
    birth: Optional[float],
    typ: Literal["H", "L"],
    conf_ts: Optional[pd.Timestamp],
) -> Optional[float]:
    """Wie ``_final_level``, aber Geburts-Level nur bei Dichte-Bestaetigung.

    Args:
        schnitt: Schnittmengen-Linie (oder ``None``).
        birth: Geburts-Level (oder ``None``).
        typ: Richtung (``"H"`` = Maximum, ``"L"`` = Minimum).
        conf_ts: Zeitstempel der Dichte-Bestaetigung (oder ``None``).

    Returns:
        Angewandtes Level.
    """
    if schnitt is None:
        return birth
    if birth is None or conf_ts is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _birth_level(
    birth: Optional[pd.DataFrame],
    typ: Literal["H", "L"],
    config: SegmentConfig,
) -> Optional[float]:
    """Geburts-Level aus bestaetigten Pivots zwischen Vor-Phase und Cutoff.

    Args:
        birth: Pivot-Subset der Geburtszone (oder ``None``).
        typ: Richtung (``"H"`` = Maximum, ``"L"`` = Minimum).
        config: Segmentierungs-Konfiguration.

    Returns:
        Geburts-Level oder ``None``.
    """
    if birth is None or len(birth) == 0:
        return None
    prices = birth.loc[birth["typ"] == typ, "price"].values.astype(float)
    if not len(prices):
        return None
    d = np.array([np.sum(np.abs(prices - x) <= config.density_band) for x in prices])
    sel = prices[d >= config.min_cluster]
    if not len(sel):
        return None
    return float(np.max(sel)) if typ == "H" else float(np.min(sel))


def _last_grenz_kontakt(
    h_prices: List[float],
    h_ts: List[pd.Timestamp],
    l_prices: List[float],
    l_ts: List[pd.Timestamp],
    U_final: Optional[float],
    L_final: Optional[float],
    config: SegmentConfig,
) -> Tuple[Optional[pd.Timestamp], Optional[float], Optional[Literal["H", "L"]]]:
    """Findet den letzten Grenz-Kontakt der Phase (Baseline Z. 452-472).

    Args:
        h_prices: High-Treffer.
        h_ts: Zeitstempel der High-Treffer.
        l_prices: Low-Treffer.
        l_ts: Zeitstempel der Low-Treffer.
        U_final: Obere Kante (oder ``None``).
        L_final: Untere Kante (oder ``None``).
        config: Segmentierungs-Konfiguration.

    Returns:
        (ts, preis, typ) des letzten Kontakts; ``(None, None, None)`` wenn
        keine Kante gesetzt ist.
    """
    best_ts: Optional[pd.Timestamp] = None
    best_pr: Optional[float] = None
    best_typ: Optional[Literal["H", "L"]] = None
    if U_final is not None:
        for ts, pr in zip(h_ts, h_prices):
            if pr >= U_final - config.grenz_kontakt_tol and (
                best_ts is None or ts > best_ts
            ):
                best_ts, best_pr, best_typ = ts, pr, "H"
    if L_final is not None:
        for ts, pr in zip(l_ts, l_prices):
            if pr <= L_final + config.grenz_kontakt_tol and (
                best_ts is None or ts > best_ts
            ):
                best_ts, best_pr, best_typ = ts, pr, "L"
    return best_ts, best_pr, best_typ


# =============================================================================
# 4) PHASEN-SEGMENTIERUNG (verbatim Baseline Z. 610-797)
# =============================================================================


def segmentiere_markt(df: pd.DataFrame, config: SegmentConfig) -> SegmentResult:
    """Segmentiert OHLCV-Bars kausal in Phasen und Moves.

    Die Schleife ist eine 1:1-Uebernahme der Baseline Z. 610-797. Lokale
    ALL-CAPS-Aliase sind bewusst aus ``config`` gebunden (keine Modul-Globals),
    damit der Koerper wortgleich zur Baseline bleibt und bitgenau geprueft
    werden kann.

    Args:
        df: OHLCV-Bars aus ``load_data()`` (Spalten
            ``ts/open/high/low/close/tick_volume/idx``, aufsteigend sortiert).
        config: Segmentierungs-Konfiguration.

    Returns:
        ``SegmentResult`` mit defensiver df-Kopie (inkl. ``is_pivot``-Spalte),
        chronologischen Phasen und Moves.
    """
    # Konfiguration lokal binden (Schleife bleibt wortgleich zu Z. 610-797).
    TOL: float = config.tol
    TOL_TOUCH: float = config.tol_touch
    DENSITY_BAND: float = config.density_band
    MIN_ESTABLISH: int = config.min_establish
    MIN_PHASE_CANDLES: int = config.min_phase_candles
    SHIFT_TOL: float = config.shift_tol
    PIVOT_LOOKBACK: int = config.pivot_lookback

    # Defensive Kopie: die is_pivot-Spalte wird ergaenzt, ohne das df des
    # Aufrufers zu mutieren (bitgenau-neutral, Werte bleiben identisch).
    df = df.copy()

    piv: pd.DataFrame = (
        find_pivots(df.reset_index(drop=True), n=PIVOT_LOOKBACK)
        .sort_values("ts")
        .reset_index(drop=True)
    )

    piv_typ: Dict[pd.Timestamp, str] = dict(zip(piv["ts"], piv["typ"]))
    df["is_pivot"] = df["ts"].isin(piv_typ)

    phases: List[PhaseData] = []
    moves: List[MoveData] = []
    i: int = 0
    n: int = len(df)
    prev_ende_ts: Optional[pd.Timestamp] = None

    while i < n:
        h_acc: List[float] = []
        l_acc: List[float] = []
        h_ts: List[pd.Timestamp] = []
        l_ts: List[pd.Timestamp] = []
        est_idx: Optional[int] = None
        brk_idx: Optional[int] = None
        brk_dir: Optional[Literal["up", "down"]] = None
        brk_kante: Optional[float] = None
        hist_U: List[Tuple[pd.Timestamp, float]] = []
        hist_L: List[Tuple[pd.Timestamp, float]] = []
        last_U: Optional[float] = None
        last_L: Optional[float] = None
        U_conf_ts: Optional[pd.Timestamp] = None
        L_conf_ts: Optional[pd.Timestamp] = None

        if prev_ende_ts is not None:
            cutoff_birth = df["ts"].iloc[i] - pd.Timedelta(
                minutes=PIVOT_LOOKBACK * 15
            )
            birth = piv[(piv["ts"] > prev_ende_ts) & (piv["ts"] <= cutoff_birth)]
            birth_h = _birth_level(birth, "H", config)
            birth_l = _birth_level(birth, "L", config)
        else:
            birth_h = birth_l = None

        phasen_start = df["ts"].iloc[i]
        j = i
        while j < n:
            row = df.iloc[j]
            ts = row["ts"]
            if j - PIVOT_LOOKBACK >= 0 and df["is_pivot"].iloc[j - PIVOT_LOOKBACK]:
                t_prev = df["ts"].iloc[j - PIVOT_LOOKBACK]
                if t_prev < phasen_start:
                    pass
                elif piv_typ[t_prev] == "H":
                    pv = float(df["high"].iloc[j - PIVOT_LOOKBACK])
                    h_acc.append(pv)
                    h_ts.append(t_prev)
                    if (
                        U_conf_ts is None
                        and birth_h is not None
                        and abs(pv - birth_h) <= DENSITY_BAND
                    ):
                        U_conf_ts = t_prev
                else:
                    pv = float(df["low"].iloc[j - PIVOT_LOOKBACK])
                    l_acc.append(pv)
                    l_ts.append(t_prev)
                    if (
                        L_conf_ts is None
                        and birth_l is not None
                        and abs(pv - birth_l) <= DENSITY_BAND
                    ):
                        L_conf_ts = t_prev

            U = _linie(h_acc, "H", config)
            L = _linie(l_acc, "L", config)

            if (
                est_idx is None
                and U is not None
                and L is not None
                and _n_touches(h_acc, U, config) + _n_touches(l_acc, L, config)
                >= MIN_ESTABLISH
            ):
                est_idx = j

            if est_idx is not None:
                U_applied = _final_level(U, birth_h, "H")
                L_applied = _final_level(L, birth_l, "L")
                if U_applied is not None and (
                    last_U is None or abs(U_applied - last_U) > SHIFT_TOL
                ):
                    hist_U.append((ts, U_applied))
                    last_U = U_applied
                if L_applied is not None and (
                    last_L is None or abs(L_applied - last_L) > SHIFT_TOL
                ):
                    hist_L.append((ts, L_applied))
                    last_L = L_applied

            if (
                est_idx is not None
                and (j - i) >= MIN_PHASE_CANDLES
                and j + 1 < n
            ):
                h_ref = U if U is not None else None
                l_ref = L if L is not None else None
                if birth_h is not None:
                    h_ref = (
                        max(h_ref, birth_h) if h_ref is not None else birth_h
                    )
                if birth_l is not None:
                    l_ref = (
                        min(l_ref, birth_l) if l_ref is not None else birth_l
                    )
                if (
                    h_ref is not None
                    and row["close"] > h_ref + TOL
                    and df["close"].iloc[j + 1] > h_ref + TOL
                ):
                    brk_idx, brk_dir, brk_kante = j, "up", h_ref
                    break
                if (
                    l_ref is not None
                    and row["close"] < l_ref - TOL
                    and df["close"].iloc[j + 1] < l_ref - TOL
                ):
                    brk_idx, brk_dir, brk_kante = j, "down", l_ref
                    break
            j += 1

        U_final = _final_level_bestaetigt(
            _linie(h_acc, "H", config), birth_h, "H", U_conf_ts
        )
        L_final = _final_level_bestaetigt(
            _linie(l_acc, "L", config), birth_l, "L", L_conf_ts
        )

        if brk_idx is None:
            ende_ts = df["ts"].iloc[n - 1]
            phases.append(
                PhaseData(
                    start=df["ts"].iloc[i],
                    ende=ende_ts,
                    U_final=U_final,
                    L_final=L_final,
                    h_prices=h_acc,
                    l_prices=l_acc,
                    h_ts=list(h_ts),
                    l_ts=list(l_ts),
                    birth_h=birth_h,
                    birth_l=birth_l,
                    U_conf_ts=U_conf_ts,
                    L_conf_ts=L_conf_ts,
                    U_ts=h_ts[-1] if h_ts else None,
                    L_ts=l_ts[-1] if l_ts else None,
                    U_hist=hist_U,
                    L_hist=hist_L,
                    break_dir=None,
                    brk_idx=None,
                    brk_kante=None,
                )
            )
            break

        if brk_dir == "down":
            t_arr = (
                np.array(
                    [
                        abs(x - U_final) <= TOL_TOUCH and t >= phasen_start
                        for x, t in zip(h_acc, h_ts)
                    ]
                )
                if h_acc
                else np.array([], dtype=bool)
            )
            if t_arr.any():
                k_touch = int(np.where(t_arr)[0][-1])
                ende_ts, ende_pr = h_ts[k_touch], h_acc[k_touch]
            else:
                ende_ts, ende_pr = df["ts"].iloc[i], None
            moves.append(
                MoveData(
                    dir="down",
                    von_ts=ende_ts,
                    von_pr=ende_pr,
                    bis_ts=df["ts"].iloc[brk_idx],
                    bis_pr=float(df["low"].iloc[brk_idx]),
                )
            )
        else:
            t_arr = (
                np.array(
                    [
                        abs(x - L_final) <= TOL_TOUCH and t >= phasen_start
                        for x, t in zip(l_acc, l_ts)
                    ]
                )
                if l_acc
                else np.array([], dtype=bool)
            )
            if t_arr.any():
                k_touch = int(np.where(t_arr)[0][-1])
                ende_ts, ende_pr = l_ts[k_touch], l_acc[k_touch]
            else:
                ende_ts, ende_pr = df["ts"].iloc[i], None
            moves.append(
                MoveData(
                    dir="up",
                    von_ts=ende_ts,
                    von_pr=ende_pr,
                    bis_ts=df["ts"].iloc[brk_idx],
                    bis_pr=float(df["high"].iloc[brk_idx]),
                )
            )

        h_clean = [p for p, t in zip(h_acc, h_ts) if t <= ende_ts]
        l_clean = [p for p, t in zip(l_acc, l_ts) if t <= ende_ts]
        h_clean_ts = [t for t, p in zip(h_ts, h_acc) if t <= ende_ts]
        l_clean_ts = [t for t, p in zip(l_ts, l_acc) if t <= ende_ts]
        phases.append(
            PhaseData(
                start=df["ts"].iloc[i],
                ende=ende_ts,
                U_final=_final_level_bestaetigt(
                    _linie(h_clean, "H", config), birth_h, "H", U_conf_ts
                ),
                L_final=_final_level_bestaetigt(
                    _linie(l_clean, "L", config), birth_l, "L", L_conf_ts
                ),
                h_prices=h_clean,
                l_prices=l_clean,
                h_ts=h_clean_ts,
                l_ts=l_clean_ts,
                birth_h=birth_h,
                birth_l=birth_l,
                U_conf_ts=U_conf_ts,
                L_conf_ts=L_conf_ts,
                U_ts=h_ts[len(h_clean) - 1] if h_clean else None,
                L_ts=l_ts[len(l_clean) - 1] if l_clean else None,
                U_hist=hist_U,
                L_hist=hist_L,
                break_dir=brk_dir,
                brk_idx=brk_idx,
                brk_kante=brk_kante,
            )
        )
        prev_ende_ts = ende_ts
        i = brk_idx

    # 4b) Datenende-Finalize (Regel 7, D1-Variante, verbatim Z. 763-797)
    if phases and phases[-1].break_dir is None:
        p_last = phases[-1]
        t_last, pr_last, typ_last = _last_grenz_kontakt(
            p_last.h_prices,
            p_last.h_ts,
            p_last.l_prices,
            p_last.l_ts,
            p_last.U_final,
            p_last.L_final,
            config,
        )
        if t_last is not None and t_last < p_last.ende:
            h_ok = [k for k, t in enumerate(p_last.h_ts) if t <= t_last]
            l_ok = [k for k, t in enumerate(p_last.l_ts) if t <= t_last]
            p_last.h_prices = [p_last.h_prices[k] for k in h_ok]
            p_last.h_ts = [p_last.h_ts[k] for k in h_ok]
            p_last.l_prices = [p_last.l_prices[k] for k in l_ok]
            p_last.l_ts = [p_last.l_ts[k] for k in l_ok]
            p_last.ende = t_last
            p_last.U_final = _final_level_bestaetigt(
                _linie(p_last.h_prices, "H", config),
                p_last.birth_h,
                "H",
                p_last.U_conf_ts,
            )
            p_last.L_final = _final_level_bestaetigt(
                _linie(p_last.l_prices, "L", config),
                p_last.birth_l,
                "L",
                p_last.L_conf_ts,
            )
            p_last.U_ts = p_last.h_ts[-1] if p_last.h_ts else None
            p_last.L_ts = p_last.l_ts[-1] if p_last.l_ts else None
            p_last.U_hist = [(t, v) for t, v in p_last.U_hist if t <= t_last]
            p_last.L_hist = [(t, v) for t, v in p_last.L_hist if t <= t_last]

            sub = df[df["ts"] > t_last]
            if len(sub) and typ_last == "H" and pr_last is not None:
                k_min = sub["low"].idxmin()
                moves.append(
                    MoveData(
                        dir="down",
                        von_ts=t_last,
                        von_pr=float(pr_last),
                        bis_ts=sub.loc[k_min, "ts"],
                        bis_pr=float(sub.loc[k_min, "low"]),
                    )
                )
            elif len(sub) and typ_last == "L" and pr_last is not None:
                k_max = sub["high"].idxmax()
                moves.append(
                    MoveData(
                        dir="up",
                        von_ts=t_last,
                        von_pr=float(pr_last),
                        bis_ts=sub.loc[k_max, "ts"],
                        bis_pr=float(sub.loc[k_max, "high"]),
                    )
                )

    return SegmentResult(df=df, phases=phases, moves=moves)
