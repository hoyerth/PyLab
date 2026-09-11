# -*- coding: utf-8 -*-
"""scripts/reclaim_live_kernel.py -- Zustandsloser Reclaim-Kernel (Setup B, SILVER M15).

1:1-Port der arretierten Frozen-Pipeline ``scripts/phasen_volumen_profil.py``
(Commit 691bf56; Reclaim-Baseline v0.4.0-frozen, Baseline-Pfad) fuer den
M15-Live-Runner (TradingEngine_Reclaim_SILVER_M15).

Scope (K4, arretiert):
    * Reine Berechnung - KEIN Chart, KEIN Report, KEINE CLI-Argumente,
      KEIN ``--macro-live``-Pfad, KEIN AUG-Referenz-/print-Block (frozen
      Z. 844-866), KEINE Datei-Artefakte.
    * Import ohne Seiteneffekte (kein ``__main__``-Block, kein Modul-Level-
      Lauf) - im Gegensatz zur frozen Quelle, deren Import den kompletten
      AUG-Lauf ausfuehrt (Seiteneffekt-Falle).
    * Modulkonstanten = 1:1-Spiegel der frozen Quelle (Zeilennachweise in
      den Kommentaren). L1-Assert praeft die Identitaet.
    * Makro-Schatten-Felder ``edge_decision``/``macro_active`` (frozen
      Z. 188-191) entfallen: Der Kernel ist strikt Baseline (K4).
    * D2-asym-Cooldown wird nur in seiner Baseline-Auspraegung benoetigt
      (dec ist immer None -> Kette last_bar_t1).

M15-Spezifik (BKZ-Invariante):
    * Die Segmentierung arbeitet auf 15-Minuten-Bars (frozen Z. 640:
      ``PIVOT_LOOKBACK * 15`` Minuten). Der Kernel ist daher an SILVER M15
      gebunden; ein Timeframe-Wechsel erfordert eine erneute Spezifikation.

Datenvertrag:
    * ``df`` muss die Spalten ``ts`` (tz-naive datetime64[ns]),
      ``open/high/low/close/tick_volume`` und ``idx = np.arange(len(df))``
      enthalten. ``normalisiere_fenster()`` stellt den Vertrag sicher
      (exakt identisch zur frozen ``load_data``-Nachbereitung, Z. 333-334).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

# ==============================================================================
# MODULKONSTANTEN (1:1-Spiegel frozen `scripts/phasen_volumen_profil.py`, Z. 201-229)
# ==============================================================================

TOL: float = 0.34                    # frozen Z. 201
TOL_TOUCH: float = 0.15              # frozen Z. 202
MIN_TOUCHES: int = 3                 # frozen Z. 203
MIN_CANDLES: int = 46                # frozen Z. 204
MIN_PHASE_CANDLES: int = 46          # frozen Z. 205
MIN_CLUSTER: int = 2                 # frozen Z. 206
MIN_ESTABLISH: int = 4               # frozen Z. 207
DENSITY_BAND: float = 0.15           # frozen Z. 208
MIN_SPREAD_PCT: float = 1.5          # frozen Z. 209
ERWEITERUNG_PCT: float = 1.0         # frozen Z. 210
SHIFT_TOL: float = 0.05              # frozen Z. 211
GRENZ_KONTAKT_TOL: float = 0.0       # frozen Z. 212
FENSTER_PIVOTS: int = 100            # frozen Z. 213
PIVOT_LOOKBACK: int = 2              # frozen Z. 214

VA_PCT: float = 0.93                 # frozen Z. 216
NUM_BINS: int = 60                   # frozen Z. 217
SMOOTH_WIN: int = 3                  # frozen Z. 218
VALLEY_REL: float = 0.15             # frozen Z. 219
MIN_MOUNTAIN_PCT: float = 4.0        # frozen Z. 220
MIN_RECLAIM_CANDLES: int = 0         # frozen Z. 221
MIN_RECLAIM_BOUNCE: int = 2          # frozen Z. 222
MIN_RECLAIM_CRV: float = 1.0         # frozen Z. 223
MIN_SIGNAL_ABSTAND_BARS: int = 12    # frozen Z. 224
SL_PCT: float = 0.45                 # frozen Z. 225
TP2_PUFFER_PCT: float = 0.20         # frozen Z. 226

ANTEIL_TP1: float = 25.0             # frozen Z. 228
TRAILING_PCT: float = 0.0            # frozen Z. 229

# ==============================================================================
# TYPIFIZIERTE DATENVERTRAEGE (Kopie frozen Z. 67-187; Makro-Felder entfallen)
# ==============================================================================


@dataclass(slots=True)
class VolumeProfileData:
    centers: np.ndarray
    edges: np.ndarray
    vol: np.ndarray
    pmin: float
    pmax: float


@dataclass(slots=True)
class MountainPeak:
    poc: float
    val: float
    vah: float
    vol: float
    peak_share_pct: float


@dataclass(slots=True)
class VolumeZone:
    profile: VolumeProfileData
    mountains: List[Tuple[int, int, int]]
    peaks: List[MountainPeak]
    U_zone: float
    L_zone: float
    POC: float
    n_mountains: int


@dataclass(slots=True)
class PhaseData:
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
    n_candles: int = 0
    handels_h: float = 0.0
    i_start: int = 0
    i_ende: int = 0
    touches_h: int = 0
    touches_l: int = 0
    close_h: int = 0
    close_l: int = 0
    spread: float = 0.0
    spread_pct: float = 0.0
    handelbar: bool = False
    U_init: Optional[float] = None
    L_init: Optional[float] = None
    n_U_shifts: int = 0
    n_L_shifts: int = 0
    U_proj_val: Optional[float] = None
    L_proj_val: Optional[float] = None
    vol_zone: Optional[VolumeZone] = None
    U_zone: Optional[float] = None
    L_zone: Optional[float] = None
    POC: Optional[float] = None
    n_berge: int = 0
    zone_breite: float = 0.0


@dataclass(slots=True)
class MoveData:
    dir: Literal["up", "down"]
    von_ts: pd.Timestamp
    von_pr: Optional[float]
    bis_ts: pd.Timestamp
    bis_pr: float


@dataclass(slots=True)
class TradeResolution:
    r1: float
    r2: float
    exit1: float
    exit2: float
    grund1: str
    grund2: str
    pnl: float
    r_mult: float
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"]
    tp1_hit: bool
    tp2_hit: bool
    sl_hit1: bool
    sl_hit2: bool
    sl_init: float


@dataclass(slots=True)
class ReclaimSignal:
    """Setup-B-Signal (Baseline). Makro-Schatten-Felder der frozen Quelle
    entfallen (K4); identische Feldreihenfolge wie frozen Z. 170-187."""
    typ: Literal["SHORT", "LONG"]
    bar: int
    ts: pd.Timestamp
    reclaim: Literal["in_bar", "next_bar"]
    einstieg_bar: int
    einstieg_preis: float
    U_laufend: float
    L_laufend: float
    POC: float
    tp1: float
    tp2: float
    sl: float
    crv: float
    crv2: float
    bounce_nr: int
    phase: int = 0
    trade: Optional[TradeResolution] = None


# ==============================================================================
# PIPELINE-FUNKTIONEN (1:1-Port frozen; optionale Parameter mit None-Default
# loesen auf die Modulkonstanten auf -> Default-Pfad ist bitgenau zur frozen
# Quelle. `density_band`-Override erreicht auch die Segmentierungs-Schicht,
# `num_bins/va_pct/min_mountain_pct/valley_rel` die Volume-Zonen-Schicht.)
# ==============================================================================


def normalisiere_fenster(df: pd.DataFrame) -> pd.DataFrame:
    """Stellt den Datenvertrag her (frozen load_data-Nachbereitung, Z. 333-334).

    Args:
        df: OHLCV-Fenster mit Spalten ``ts/open/high/low/close/tick_volume``.

    Returns:
        Nach ts sortierte Kopie mit tz-naivem ``ts`` und ``idx = np.arange(len)``.
    """
    d = df.copy()
    if d["ts"].dt.tz is not None:
        d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    d = d.sort_values("ts").reset_index(drop=True)
    d["idx"] = np.arange(len(d))
    return d


def find_pivots(d: pd.DataFrame, n: int = PIVOT_LOOKBACK) -> pd.DataFrame:
    """Pivot-Detektion (frozen Z. 343-359, unveraendert).

    Args:
        d: OHLC-Fenster.
        n: Pivot-Lookback.

    Returns:
        DataFrame mit ts/price/typ der bestaetigten Pivot-Bars.
    """
    h: np.ndarray = d["high"].values
    l: np.ndarray = d["low"].values
    hi = pd.Series(h)
    lo = pd.Series(l)
    is_hi = (hi == hi.rolling(2 * n + 1, center=True, min_periods=1).max()) & (hi.shift(n) < h) & (hi.shift(-n) < h)
    is_lo = (lo == lo.rolling(2 * n + 1, center=True, min_periods=1).min()) & (lo.shift(n) > l) & (lo.shift(-n) > l)
    is_hi[:n] = False
    is_hi[-n:] = False
    is_lo[:n] = False
    is_lo[-n:] = False
    piv_df = pd.DataFrame({
        "ts": d["ts"],
        "price": np.where(is_hi, h, np.where(is_lo, l, np.nan)),
        "typ": np.where(is_hi, "H", np.where(is_lo, "L", "")),
    })
    return piv_df[piv_df["typ"] != ""].copy()


def level_schnittmenge(
    prices: List[float] | np.ndarray,
    target_typ: Literal["H", "L"] = "H",
    band: float = DENSITY_BAND,
    min_cluster: int = MIN_CLUSTER,
    erweiterung_pct: float = ERWEITERUNG_PCT,
) -> Optional[float]:
    """Schnittmengen-Linie (frozen Z. 368-402, unveraendert)."""
    arr = np.array(prices, dtype=float)
    if not len(arr):
        return None
    d = np.array([np.sum(np.abs(arr - x) <= band) for x in arr])
    m = d >= min_cluster
    if not m.any():
        return float(np.max(arr)) if target_typ == "H" else float(np.min(arr))
    sel = arr[m]
    ext = float(np.max(sel)) if target_typ == "H" else float(np.min(sel))
    kern = sel[np.abs(sel - ext) <= band]
    if not len(kern):
        kern = sel
    if target_typ == "H":
        kante = float(np.min(kern))
        pool = sel[sel >= kante - band]
        pool = pool[pool <= kante * (1 + erweiterung_pct / 100.0)]
    else:
        kante = float(np.max(kern))
        pool = sel[sel <= kante + band]
        pool = pool[pool >= kante * (1 - erweiterung_pct / 100.0)]
    if not len(pool):
        pool = kern
    if len(pool) > 1:
        if target_typ == "H":
            pool = pool[pool != np.max(pool)]
        else:
            pool = pool[pool != np.min(pool)]
    return float(np.mean(pool)) if len(pool) else float(np.mean(kern))


def n_touches(prices: List[float] | np.ndarray, level: Optional[float], band: float = DENSITY_BAND) -> int:
    """Touch-Zaehlung (frozen Z. 405-408, unveraendert)."""
    if level is None or not len(prices):
        return 0
    return int(np.sum(np.abs(np.array(prices, dtype=float) - level) <= band))


def _linie(prices: List[float], typ: Literal["H", "L"], band: Optional[float] = None) -> Optional[float]:
    """Laufende Schnittmengen-Linie ueber dem Pivot-Fenster (frozen Z. 411-415).

    Args:
        prices: Preise (H- oder L-Touches).
        typ: "H" oder "L".
        band: Density-Band; None -> Modulkonstante DENSITY_BAND.
    """
    if not prices:
        return None
    w = prices if len(prices) <= FENSTER_PIVOTS else prices[-FENSTER_PIVOTS:]
    return level_schnittmenge(w, typ, band=DENSITY_BAND if band is None else band)


def _final_level(schnitt: Optional[float], birth: Optional[float], typ: Literal["H", "L"]) -> Optional[float]:
    """Final-Level (frozen Z. 418-423, unveraendert)."""
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
    """Final-Level mit Bestaetigungs-Gate (frozen Z. 426-436, unveraendert)."""
    if schnitt is None:
        return birth
    if birth is None or conf_ts is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _birth_level(birth: Optional[pd.DataFrame], typ: Literal["H", "L"], band: Optional[float] = None) -> Optional[float]:
    """Geburtszonen-Niveau (frozen Z. 439-449; band-Override erlaubt)."""
    if birth is None or len(birth) == 0:
        return None
    prices = birth.loc[birth["typ"] == typ, "price"].values.astype(float)
    if not len(prices):
        return None
    band_eff = DENSITY_BAND if band is None else band
    d = np.array([np.sum(np.abs(prices - x) <= band_eff) for x in prices])
    sel = prices[d >= MIN_CLUSTER]
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
    tol: float = 0.0,
) -> Tuple[Optional[pd.Timestamp], Optional[float], Optional[Literal["H", "L"]]]:
    """Letzter Grenz-Kontakt vor dem Datenende (frozen Z. 452-472, unveraendert)."""
    best_ts: Optional[pd.Timestamp] = None
    best_pr: Optional[float] = None
    best_typ: Optional[Literal["H", "L"]] = None
    if U_final is not None:
        for ts, pr in zip(h_ts, h_prices):
            if pr >= U_final - tol and (best_ts is None or ts > best_ts):
                best_ts, best_pr, best_typ = ts, pr, "H"
    if L_final is not None:
        for ts, pr in zip(l_ts, l_prices):
            if pr <= L_final + tol and (best_ts is None or ts > best_ts):
                best_ts, best_pr, best_typ = ts, pr, "L"
    return best_ts, best_pr, best_typ


# --- Volume-Profil ----------------------------------------------------------


def build_volume_profile(sub: pd.DataFrame, num_bins: int = NUM_BINS) -> Optional[VolumeProfileData]:
    """Volumen-Profil (frozen Z. 478-507, unveraendert)."""
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
        lo_b = int(np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, num_bins - 1))
        hi_b = int(np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, num_bins - 1))
        if lo_b == hi_b:
            vol[lo_b] += v
        else:
            ov = np.array([
                max(0.0, min(hi, edges[b + 1]) - max(lo, edges[b]))
                for b in range(lo_b, hi_b + 1)
            ])
            tot = ov.sum()
            if tot > 0:
                vol[lo_b:hi_b + 1] += v * ov / tot
    return VolumeProfileData(centers=centers, edges=edges, vol=vol, pmin=pmin, pmax=pmax)


def smooth_vol(vol: np.ndarray, win: int = SMOOTH_WIN) -> np.ndarray:
    """Glättung (frozen Z. 510-513, unveraendert)."""
    if win <= 1 or len(vol) < win:
        return vol.astype(float)
    return np.convolve(vol, np.ones(win) / win, mode="same")


def find_mountains(
    vol_s: np.ndarray,
    min_pct: float = MIN_MOUNTAIN_PCT,
    valley_rel: float = VALLEY_REL,
) -> List[Tuple[int, int, int]]:
    """Berg-Detektion (frozen Z. 516-545, unveraendert)."""
    n = len(vol_s)
    if n < 3:
        return []
    mountains: List[Tuple[int, int, int]] = []
    start = 0
    for i in range(1, n - 1):
        if vol_s[i] <= vol_s[i - 1] and vol_s[i] < vol_s[i + 1]:
            left_peak = float(np.max(vol_s[start:i + 1]))
            right_peak = float(np.max(vol_s[i:n]))
            threshold = min(left_peak, right_peak) * valley_rel
            if vol_s[i] < threshold:
                p_idx = start + int(np.argmax(vol_s[start:i + 1]))
                if vol_s[start:i + 1].max() > 0:
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
    va_pct: float = VA_PCT,
) -> MountainPeak:
    """Value-Area je Berg (frozen Z. 548-581, unveraendert)."""
    s, p, e = mountain
    poc = float((edges[p] + edges[p + 1]) / 2)
    total = float(vol_s[s:e + 1].sum())
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
    sub: pd.DataFrame,
    *,
    num_bins: Optional[int] = None,
    va_pct: Optional[float] = None,
    min_mountain_pct: Optional[float] = None,
    valley_rel: Optional[float] = None,
) -> Optional[VolumeZone]:
    """Volume-Zone einer Teilmenge (frozen Z. 584-608).

    Args:
        sub: OHLCV-Teilfenster der Phase.
        num_bins/va_pct/min_mountain_pct/valley_rel: Optionale Overrides;
            None -> jeweilige Modulkonstante (frozen-identisch).
    """
    prof = build_volume_profile(sub, num_bins=NUM_BINS if num_bins is None else num_bins)
    if prof is None:
        return None
    vol_s = smooth_vol(prof.vol)
    mountains = find_mountains(
        vol_s,
        min_pct=MIN_MOUNTAIN_PCT if min_mountain_pct is None else min_mountain_pct,
        valley_rel=VALLEY_REL if valley_rel is None else valley_rel,
    )
    if not mountains:
        return None
    dominant_peak = mountains[0][1]
    peaks: List[MountainPeak] = []
    for m in mountains:
        va = va_for_mountain(vol_s, prof.edges, m, dominant_peak,
                             va_pct=VA_PCT if va_pct is None else va_pct)
        peaks.append(va)
    U_zone = max(p.vah for p in peaks)
    L_zone = min(p.val for p in peaks)
    POC = peaks[0].poc
    return VolumeZone(
        profile=prof,
        mountains=mountains,
        peaks=peaks,
        U_zone=U_zone,
        L_zone=L_zone,
        POC=POC,
        n_mountains=len(peaks),
    )


# --- Phasen-Segmentierung ---------------------------------------------------


def segmentiere_phasen(
    df: pd.DataFrame,
    *,
    density_band: Optional[float] = None,
    num_bins: Optional[int] = None,
    va_pct: Optional[float] = None,
    min_mountain_pct: Optional[float] = None,
    valley_rel: Optional[float] = None,
) -> List[PhaseData]:
    """Phasen-Segmentierung (frozen Z. 614-838, gekapselt in eine Funktion).

    K1 (Rechtsrand provisorisch): Die letzte Phase ist mit
    ``PIVOT_LOOKBACK=2`` erst 2 Bars nach ihrem letzten Pivot bestaetigt -
    der Live-Aufrufer kennzeichnet sie als provisorisch.

    Args:
        df: Normalisiertes Fenster (Spalten ts/open/high/low/close/
            tick_volume/idx, ts tz-naiv, idx=np.arange).
        density_band: Optionaler Override (None -> DENSITY_BAND).
        num_bins/va_pct/min_mountain_pct/valley_rel: Optionale Overrides
            der Volume-Zonen-Schicht (None -> Modulkonstante).

    Returns:
        Liste der Phasen (PhaseData) inkl. Statistik und Volume-Zonen.
    """
    band = DENSITY_BAND if density_band is None else density_band
    piv = find_pivots(df, n=PIVOT_LOOKBACK).sort_values("ts").reset_index(drop=True)
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
            cutoff_birth = df["ts"].iloc[i] - pd.Timedelta(minutes=PIVOT_LOOKBACK * 15)
            birth = piv[(piv["ts"] > prev_ende_ts) & (piv["ts"] <= cutoff_birth)]
            birth_h = _birth_level(birth, "H", band=band)
            birth_l = _birth_level(birth, "L", band=band)
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
                    if U_conf_ts is None and birth_h is not None and abs(pv - birth_h) <= band:
                        U_conf_ts = t_prev
                else:
                    pv = float(df["low"].iloc[j - PIVOT_LOOKBACK])
                    l_acc.append(pv)
                    l_ts.append(t_prev)
                    if L_conf_ts is None and birth_l is not None and abs(pv - birth_l) <= band:
                        L_conf_ts = t_prev

            U = _linie(h_acc, "H", band=band)
            L = _linie(l_acc, "L", band=band)

            if est_idx is None and U is not None and L is not None and n_touches(h_acc, U, band) + n_touches(l_acc, L, band) >= MIN_ESTABLISH:
                est_idx = j

            if est_idx is not None:
                U_applied = _final_level(U, birth_h, "H")
                L_applied = _final_level(L, birth_l, "L")
                if U_applied is not None and (last_U is None or abs(U_applied - last_U) > SHIFT_TOL):
                    hist_U.append((ts, U_applied))
                    last_U = U_applied
                if L_applied is not None and (last_L is None or abs(L_applied - last_L) > SHIFT_TOL):
                    hist_L.append((ts, L_applied))
                    last_L = L_applied

            if est_idx is not None and (j - i) >= MIN_PHASE_CANDLES and j + 1 < n:
                h_ref = U if U is not None else None
                l_ref = L if L is not None else None
                if birth_h is not None:
                    h_ref = max(h_ref, birth_h) if h_ref is not None else birth_h
                if birth_l is not None:
                    l_ref = min(l_ref, birth_l) if l_ref is not None else birth_l
                if h_ref is not None and row["close"] > h_ref + TOL and df["close"].iloc[j + 1] > h_ref + TOL:
                    brk_idx, brk_dir, brk_kante = j, "up", h_ref
                    break
                if l_ref is not None and row["close"] < l_ref - TOL and df["close"].iloc[j + 1] < l_ref - TOL:
                    brk_idx, brk_dir, brk_kante = j, "down", l_ref
                    break
            j += 1

        U_final = _final_level_bestaetigt(_linie(h_acc, "H", band=band), birth_h, "H", U_conf_ts)
        L_final = _final_level_bestaetigt(_linie(l_acc, "L", band=band), birth_l, "L", L_conf_ts)

        if brk_idx is None:
            ende_ts = df["ts"].iloc[n - 1]
            phases.append(PhaseData(
                start=df["ts"].iloc[i], ende=ende_ts,
                U_final=U_final, L_final=L_final,
                h_prices=h_acc, l_prices=l_acc,
                h_ts=list(h_ts), l_ts=list(l_ts),
                birth_h=birth_h, birth_l=birth_l,
                U_conf_ts=U_conf_ts, L_conf_ts=L_conf_ts,
                U_ts=h_ts[-1] if h_ts else None, L_ts=l_ts[-1] if l_ts else None,
                U_hist=hist_U, L_hist=hist_L,
                break_dir=None, brk_idx=None, brk_kante=None,
            ))
            break

        if brk_dir == "down":
            t_arr = np.array([abs(x - U_final) <= TOL_TOUCH and t >= phasen_start
                              for x, t in zip(h_acc, h_ts)]) if h_acc else np.array([], dtype=bool)
            if t_arr.any():
                k_touch = int(np.where(t_arr)[0][-1])
                ende_ts, ende_pr = h_ts[k_touch], h_acc[k_touch]
            else:
                ende_ts, ende_pr = df["ts"].iloc[i], None
            moves.append(MoveData(
                dir="down", von_ts=ende_ts, von_pr=ende_pr,
                bis_ts=df["ts"].iloc[brk_idx], bis_pr=float(df["low"].iloc[brk_idx]),
            ))
        else:
            t_arr = np.array([abs(x - L_final) <= TOL_TOUCH and t >= phasen_start
                              for x, t in zip(l_acc, l_ts)]) if l_acc else np.array([], dtype=bool)
            if t_arr.any():
                k_touch = int(np.where(t_arr)[0][-1])
                ende_ts, ende_pr = l_ts[k_touch], l_acc[k_touch]
            else:
                ende_ts, ende_pr = df["ts"].iloc[i], None
            moves.append(MoveData(
                dir="up", von_ts=ende_ts, von_pr=ende_pr,
                bis_ts=df["ts"].iloc[brk_idx], bis_pr=float(df["high"].iloc[brk_idx]),
            ))

        h_clean = [p for p, t in zip(h_acc, h_ts) if t <= ende_ts]
        l_clean = [p for p, t in zip(l_acc, l_ts) if t <= ende_ts]
        h_clean_ts = [t for t, p in zip(h_ts, h_acc) if t <= ende_ts]
        l_clean_ts = [t for t, p in zip(l_ts, l_acc) if t <= ende_ts]
        phases.append(PhaseData(
            start=df["ts"].iloc[i], ende=ende_ts,
            U_final=_final_level_bestaetigt(_linie(h_clean, "H", band=band), birth_h, "H", U_conf_ts),
            L_final=_final_level_bestaetigt(_linie(l_clean, "L", band=band), birth_l, "L", L_conf_ts),
            h_prices=h_clean, l_prices=l_clean,
            h_ts=h_clean_ts, l_ts=l_clean_ts,
            birth_h=birth_h, birth_l=birth_l,
            U_conf_ts=U_conf_ts, L_conf_ts=L_conf_ts,
            U_ts=h_ts[len(h_clean) - 1] if h_clean else None,
            L_ts=l_ts[len(l_clean) - 1] if l_clean else None,
            U_hist=hist_U, L_hist=hist_L,
            break_dir=brk_dir, brk_idx=brk_idx, brk_kante=brk_kante,
        ))
        prev_ende_ts = ende_ts
        i = brk_idx

    # 4b) Datenende-Finalize (frozen Z. 763-797, Regel 7 D1-Variante)
    if phases and phases[-1].break_dir is None:
        p_last = phases[-1]
        t_last, pr_last, typ_last = _last_grenz_kontakt(
            p_last.h_prices, p_last.h_ts, p_last.l_prices, p_last.l_ts,
            p_last.U_final, p_last.L_final, GRENZ_KONTAKT_TOL,
        )
        if t_last is not None and t_last < p_last.ende:
            h_ok = [k for k, t in enumerate(p_last.h_ts) if t <= t_last]
            l_ok = [k for k, t in enumerate(p_last.l_ts) if t <= t_last]
            p_last.h_prices = [p_last.h_prices[k] for k in h_ok]
            p_last.h_ts = [p_last.h_ts[k] for k in h_ok]
            p_last.l_prices = [p_last.l_prices[k] for k in l_ok]
            p_last.l_ts = [p_last.l_ts[k] for k in l_ok]
            p_last.ende = t_last
            p_last.U_final = _final_level_bestaetigt(_linie(p_last.h_prices, "H", band=band), p_last.birth_h, "H", p_last.U_conf_ts)
            p_last.L_final = _final_level_bestaetigt(_linie(p_last.l_prices, "L", band=band), p_last.birth_l, "L", p_last.L_conf_ts)
            p_last.U_ts = p_last.h_ts[-1] if p_last.h_ts else None
            p_last.L_ts = p_last.l_ts[-1] if p_last.l_ts else None
            p_last.U_hist = [(t, v) for t, v in p_last.U_hist if t <= t_last]
            p_last.L_hist = [(t, v) for t, v in p_last.L_hist if t <= t_last]

            sub = df[df["ts"] > t_last]
            if len(sub) and typ_last == "H" and pr_last is not None:
                k_min = sub["low"].idxmin()
                moves.append(MoveData(
                    dir="down", von_ts=t_last, von_pr=float(pr_last),
                    bis_ts=sub.loc[k_min, "ts"], bis_pr=float(sub.loc[k_min, "low"]),
                ))
            elif len(sub) and typ_last == "L" and pr_last is not None:
                k_max = sub["high"].idxmax()
                moves.append(MoveData(
                    dir="up", von_ts=t_last, von_pr=float(pr_last),
                    bis_ts=sub.loc[k_max, "ts"], bis_pr=float(sub.loc[k_max, "high"]),
                ))

    # 5) Candle-Statistik & Volume-Zonen je Phase (frozen Z. 803-838)
    for p in phases:
        mask = (df["ts"] >= p.start) & (df["ts"] <= p.ende)
        p.n_candles = int(mask.sum())
        p.handels_h = p.n_candles * 15.0 / 60.0
        p.i_start = int(df.loc[mask, "idx"].min()) if p.n_candles else 0
        p.i_ende = int(df.loc[mask, "idx"].max()) if p.n_candles else 0
        p.touches_h = len(p.h_prices)
        p.touches_l = len(p.l_prices)
        p.close_h = n_touches(p.h_prices, p.U_final, band)
        p.close_l = n_touches(p.l_prices, p.L_final, band)
        p.spread = (p.U_final - p.L_final) if (p.U_final is not None and p.L_final is not None) else 0.0
        p.spread_pct = (p.spread / p.L_final * 100.0) if p.L_final else 0.0
        p.handelbar = (
            p.touches_h >= MIN_TOUCHES
            and p.touches_l >= MIN_TOUCHES
            and p.n_candles >= MIN_CANDLES
            and p.spread_pct >= MIN_SPREAD_PCT
        )
        p.U_init = p.U_hist[0][1] if p.U_hist else p.U_final
        p.L_init = p.L_hist[0][1] if p.L_hist else p.L_final
        p.n_U_shifts = len(p.U_hist) - 1 if len(p.U_hist) > 1 else 0
        p.n_L_shifts = len(p.L_hist) - 1 if len(p.L_hist) > 1 else 0
        p.U_proj_val = (p.birth_h if (p.birth_h is not None and p.U_final is not None
                                      and abs(p.U_final - p.birth_h) < 1e-9) else None)
        p.L_proj_val = (p.birth_l if (p.birth_l is not None and p.L_final is not None
                                      and abs(p.L_final - p.birth_l) < 1e-9) else None)

        sub = df[mask]
        vz = compute_volume_zone(
            sub,
            num_bins=num_bins,
            va_pct=va_pct,
            min_mountain_pct=min_mountain_pct,
            valley_rel=valley_rel,
        )
        if vz is not None:
            p.vol_zone = vz
            p.U_zone = vz.U_zone
            p.L_zone = vz.L_zone
            p.POC = vz.POC
            p.n_berge = vz.n_mountains
            p.zone_breite = vz.U_zone - vz.L_zone

    return phases


# --- Signal-Scan (Reclaim/Fakeout) ------------------------------------------


def _laufende_zone(
    df: pd.DataFrame,
    p: PhaseData,
    k: int,
    *,
    num_bins: Optional[int] = None,
    va_pct: Optional[float] = None,
    min_mountain_pct: Optional[float] = None,
    valley_rel: Optional[float] = None,
) -> Optional[VolumeZone]:
    """Laufende Volume-Zone bis Bar k (frozen Z. 872-873)."""
    return compute_volume_zone(
        df.iloc[p.i_start: k + 1],
        num_bins=num_bins,
        va_pct=va_pct,
        min_mountain_pct=min_mountain_pct,
        valley_rel=valley_rel,
    )


def _bounce_nr(
    h_prices: List[float],
    h_ts: List[pd.Timestamp],
    l_prices: List[float],
    l_ts: List[pd.Timestamp],
    ts_k: pd.Timestamp,
    U: float,
    L: float,
    band: Optional[float] = None,
) -> Tuple[int, int]:
    """Bounce-Zaehlung (frozen Z. 876-887; band-Override erlaubt)."""
    band_eff = DENSITY_BAND if band is None else band
    n_h = 1 + sum(1 for pr, t in zip(h_prices, h_ts) if t <= ts_k and abs(pr - U) <= band_eff)
    n_l = 1 + sum(1 for pr, t in zip(l_prices, l_ts) if t <= ts_k and abs(pr - L) <= band_eff)
    return n_h, n_l


def _aufloesen(
    df: pd.DataFrame,
    s: ReclaimSignal,
    sl_pct: Optional[float] = None,
    anteil_tp1: float = ANTEIL_TP1,
    trailing_pct: float = TRAILING_PCT,
) -> TradeResolution:
    """Trade-Aufloesung (frozen Z. 890-997, unveraendert uebernommen)."""
    if sl_pct is None:
        sl_pct = SL_PCT
    e_bar = s.einstieg_bar
    entry = s.einstieg_preis
    typ = s.typ
    tp1, tp2 = s.tp1, s.tp2
    p = sl_pct / 100.0
    sl_init = entry * (1.0 + p) if typ == "SHORT" else entry * (1.0 - p)

    hi = df["high"].values[e_bar:]
    lo = df["low"].values[e_bar:]
    cl = df["close"].values[e_bar:]
    n_bars = len(hi)
    risk = abs(sl_init - entry)
    if risk <= 0:
        risk = 1e-9

    def _first(mask: np.ndarray) -> int:
        return int(np.argmax(mask)) if mask.any() else n_bars

    def _r(exit_price: float) -> float:
        return (entry - exit_price) / risk if typ == "SHORT" else (exit_price - entry) / risk

    if trailing_pct > 0:
        tr = trailing_pct / 100.0
        sl_val = sl_init
        ext = entry
        grund = "ENDE"
        exit_pr = float(cl[-1])
        for k2 in range(n_bars):
            if typ == "SHORT":
                if hi[k2] >= sl_val:
                    exit_pr, grund = float(sl_val), "TRAIL"
                    break
                ext = max(ext, float(hi[k2]))
                sl_val = max(sl_val, ext * (1.0 + tr))
            else:
                if lo[k2] <= sl_val:
                    exit_pr, grund = float(sl_val), "TRAIL"
                    break
                ext = min(ext, float(lo[k2]))
                sl_val = min(sl_val, ext * (1.0 - tr))
        r = _r(exit_pr)
        res_tag: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"] = (
            "GEWONNEN" if r > 1e-9 else ("VERLOREN" if r < -1e-9 else "NEUTRAL")
        )
        return TradeResolution(
            r1=r, r2=r, exit1=exit_pr, exit2=exit_pr,
            grund1=grund, grund2=grund,
            pnl=r * risk, r_mult=r, resultat=res_tag,
            tp1_hit=False, tp2_hit=False,
            sl_hit1=grund == "TRAIL", sl_hit2=grund == "TRAIL",
            sl_init=sl_init,
        )

    if typ == "SHORT":
        t1 = _first(lo <= tp1)
        t2 = _first(lo <= tp2)
        t_sl_i = _first(hi >= sl_init)
    else:
        t1 = _first(hi >= tp1)
        t2 = _first(hi >= tp2)
        t_sl_i = _first(lo <= sl_init)

    # Haelfte 1: TP1 (POC)
    if t1 < t_sl_i:
        r1, ex1, g1 = _r(tp1), tp1, "TP1"
    elif t_sl_i < t1:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    elif t_sl_i < n_bars:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    else:
        r1, ex1, g1 = _r(float(cl[-1])), float(cl[-1]), "ENDE"

    # Haelfte 2: TP2 (Box-Ende)
    sl2 = sl_init
    t_sl2 = t_sl_i
    if t2 < t_sl2:
        r2, ex2, g2 = _r(tp2), tp2, "TP2"
    elif t_sl2 < n_bars:
        r2, ex2, g2 = _r(sl2), sl2, "SL"
    else:
        r2, ex2, g2 = _r(float(cl[-1])), float(cl[-1]), "ENDE"

    _w1 = anteil_tp1 / 100.0
    _w2 = 1.0 - _w1
    if _w2 <= 0:
        r2, g2 = 0.0, "-"
    r_mult = _w1 * r1 + _w2 * r2
    pnl = r_mult * risk
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"] = (
        "GEWONNEN" if r_mult > 1e-9 else ("VERLOREN" if r_mult < -1e-9 else "NEUTRAL")
    )
    return TradeResolution(
        r1=r1, r2=r2, exit1=ex1, exit2=ex2,
        grund1=g1, grund2=g2,
        pnl=pnl, r_mult=r_mult, resultat=resultat,
        tp1_hit=g1 == "TP1", tp2_hit=g2 == "TP2",
        sl_hit1=g1 == "SL", sl_hit2=g2 == "SL",
        sl_init=sl_init,
    )


def _cooldown_ok(
    k: int,
    richtung: Literal["SHORT", "LONG"],
    last_bar_t1: Dict[Literal["SHORT", "LONG"], int],
    cooldown_bars: int,
) -> bool:
    """Cooldown-Check (frozen Z. 1000-1029, Baseline-Auspraegung).

    Der Kernel kennt kein Tier-2 (kein Makro-Pfad), daher nur die
    last_bar_t1-Kette - bitgenau zur frozen Baseline (dort dec=None).
    """
    return k - last_bar_t1[richtung] >= cooldown_bars


def _cooldown_set(
    k: int,
    richtung: Literal["SHORT", "LONG"],
    last_bar_t1: Dict[Literal["SHORT", "LONG"], int],
) -> None:
    """Cooldown-Setzen (frozen Z. 1032-1052, Baseline-Auspraegung)."""
    last_bar_t1[richtung] = k


def find_reclaim_signals(
    df: pd.DataFrame,
    p: PhaseData,
    min_candles: int = MIN_RECLAIM_CANDLES,
    min_bounce: int = MIN_RECLAIM_BOUNCE,
    min_crv: float = MIN_RECLAIM_CRV,
    cooldown_bars: int = MIN_SIGNAL_ABSTAND_BARS,
    sl_pct: Optional[float] = None,
    density_band: Optional[float] = None,
    num_bins: Optional[int] = None,
    va_pct: Optional[float] = None,
    min_mountain_pct: Optional[float] = None,
    valley_rel: Optional[float] = None,
) -> List[ReclaimSignal]:
    """Setup-B-Signale (Reclaim/Fakeout) - reiner Echtzeit-Modus (frozen
    Z. 1055-1272, Baseline-Pfad ohne Makro-Kanten-Auswahl).

    Args:
        df: Normalisiertes Fenster.
        p: Phase, in der gescannt wird.
        min_candles: Mindest-Candles ab Phasenstart (MIN_RECLAIM_CANDLES).
        min_bounce: Mindest-Bounce-Zahl (MIN_RECLAIM_BOUNCE).
        min_crv: Mindest-CRV (MIN_RECLAIM_CRV).
        cooldown_bars: Mindestabstand (MIN_SIGNAL_ABSTAND_BARS).
        sl_pct: Optionaler SL-Override (None -> SL_PCT).
        density_band: Optionaler Density-Override (None -> DENSITY_BAND).
        num_bins/va_pct/min_mountain_pct/valley_rel: Optionale Overrides
            der laufenden Volume-Zone (None -> Modulkonstante).

    Returns:
        Liste der Reclaim-Signale (inkl. aufgeloestem Trade fuer L1; die
        externe Live-Sicht nutzt KernelSignalOutput ohne Backtest).
    """
    band_eff = DENSITY_BAND if density_band is None else density_band
    sl_eff = SL_PCT if sl_pct is None else sl_pct
    sigs: List[ReclaimSignal] = []
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values
    op = df["open"].values
    ts = df["ts"].values
    last_bar_t1: Dict[Literal["SHORT", "LONG"], int] = {
        "SHORT": -10**9, "LONG": -10**9}
    tp2_puffer = TP2_PUFFER_PCT / 100.0
    sl_p = sl_eff / 100.0

    # Kausale Schleife bar fuer bar (kein Lookahead ueber finale Phasen-Huellkurve)
    for k in range(p.i_start, p.i_ende):
        if k - p.i_start + 1 < min_candles:
            continue
        vz = _laufende_zone(
            df, p, k,
            num_bins=num_bins,
            va_pct=va_pct,
            min_mountain_pct=min_mountain_pct,
            valley_rel=valley_rel,
        )
        if vz is None:
            continue
        U, L, POC = vz.U_zone, vz.L_zone, vz.POC

        ts_k = pd.Timestamp(ts[k])

        # Baseline: Kandidat = Durchstich ohne Obergrenze (frozen Z. 1150-1154)
        U_eff = U if hi[k] > U else None
        L_eff = L if lo[k] < L else None

        if U_eff is None and L_eff is None:
            continue

        nb_h, nb_l = _bounce_nr(
            p.h_prices, p.h_ts, p.l_prices, p.l_ts, ts_k,
            U_eff if U_eff is not None else U,
            L_eff if L_eff is not None else L,
            band=band_eff,
        )

        if U_eff is not None:
            if cl[k] <= U_eff:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= p.i_ende and cl[k + 1] <= U_eff:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if (
                reclaim is not None
                and e_bar is not None
                and e_bar <= p.i_ende
                and e_preis > POC
                and nb_h >= min_bounce
                and _cooldown_ok(k, "SHORT", last_bar_t1, cooldown_bars)
            ):
                sl = e_preis * (1.0 + sl_p)
                tp1 = POC
                tp2 = L * (1.0 + tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    _cooldown_set(k, "SHORT", last_bar_t1)
                    sig = ReclaimSignal(
                        typ="SHORT",
                        bar=int(k),
                        ts=ts_k,
                        reclaim=reclaim,  # type: ignore
                        einstieg_bar=int(e_bar),
                        einstieg_preis=e_preis,
                        U_laufend=U_eff,
                        L_laufend=L,
                        POC=POC,
                        tp1=tp1,
                        tp2=tp2,
                        sl=sl,
                        crv=crv,
                        crv2=crv2,
                        bounce_nr=nb_h,
                    )
                    sig.trade = _aufloesen(df, sig, sl_pct=sl_eff)
                    sigs.append(sig)

        if L_eff is not None:
            if cl[k] >= L_eff:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= p.i_ende and cl[k + 1] >= L_eff:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if (
                reclaim is not None
                and e_bar is not None
                and e_bar <= p.i_ende
                and e_preis < POC
                and nb_l >= min_bounce
                and _cooldown_ok(k, "LONG", last_bar_t1, cooldown_bars)
            ):
                sl = e_preis * (1.0 - sl_p)
                tp1 = POC
                tp2 = U * (1.0 - tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    _cooldown_set(k, "LONG", last_bar_t1)
                    sig = ReclaimSignal(
                        typ="LONG",
                        bar=int(k),
                        ts=ts_k,
                        reclaim=reclaim,  # type: ignore
                        einstieg_bar=int(e_bar),
                        einstieg_preis=e_preis,
                        U_laufend=U,
                        L_laufend=L_eff,
                        POC=POC,
                        tp1=tp1,
                        tp2=tp2,
                        sl=sl,
                        crv=crv,
                        crv2=crv2,
                        bounce_nr=nb_l,
                    )
                    sig.trade = _aufloesen(df, sig, sl_pct=sl_eff)
                    sigs.append(sig)
    return sigs


# ==============================================================================
# KONFIGURATION & ERGEBNIS-VERTRAEGE (E1, K9, K10)
# ==============================================================================


@dataclass(frozen=True, slots=True)
class KernelConfig:
    """Duenner Override fuer Multi-Asset-Adaptierbare Parameter.

    Alle Felder mit None-Default loesen auf die jeweilige Modulkonstante
    auf (frozen-identisch). ``symbol/timeframe/history_bars`` sind rein
    informativ fuer den Live-Aufrufer (Job-Kontext); die Kernel-Berechnung
    selbst ist strikt SILVER-M15-gebunden (Segmentierung nutzt 15-min-Bars).
    """
    symbol: str = "SILVER"
    timeframe: str = "M15"
    history_bars: int = 1500
    sl_pct: Optional[float] = None          # None -> SL_PCT (Modulkonstante)
    va_pct: Optional[float] = None          # None -> VA_PCT
    min_mountain_pct: Optional[float] = None  # None -> MIN_MOUNTAIN_PCT
    valley_rel: Optional[float] = None      # None -> VALLEY_REL
    density_band: Optional[float] = None    # None -> DENSITY_BAND
    min_reclaim_crv: Optional[float] = None  # None -> MIN_RECLAIM_CRV
    cooldown_bars: Optional[int] = None     # None -> MIN_SIGNAL_ABSTAND_BARS


@dataclass(frozen=True, slots=True)
class KernelSignalOutput:
    """Externe Live-Sicht eines Signals (K10): KEIN Backtest, KEINE
    Phasen-Interna. ``phase_id`` ist 1-basiert, ``einstieg_bar`` ist der
    idx-Wert im analysierten Fenster."""
    typ: Literal["SHORT", "LONG"]
    ts: pd.Timestamp
    reclaim: Literal["in_bar", "next_bar"]
    einstieg_bar: int
    einstieg_preis: float
    sl: float
    tp1: float
    tp2: float
    crv: float
    crv2: float
    bounce_nr: int
    phase_id: int
    U_laufend: float
    L_laufend: float
    POC: float


@dataclass(frozen=True, slots=True)
class KernelLaufErgebnis:
    """Volles Ergebnis eines Kernel-Laufs.

    ``phasen``/``signale`` sind die vollstaendigen internen Objekte
    (Signale inkl. Trade-Aufloesung - fuer L1-Abgleich und Backtest-Referenz).
    ``signal_ausgabe`` ist die externe Live-Sicht (ohne Backtest).
    """
    phasen: List[PhaseData]
    signale: List[ReclaimSignal]
    signal_ausgabe: List[KernelSignalOutput]


def _zu_signal_ausgabe(s: ReclaimSignal) -> KernelSignalOutput:
    """Projiziert ein internes Signal auf die externe Live-Sicht (K10)."""
    return KernelSignalOutput(
        typ=s.typ,
        ts=s.ts,
        reclaim=s.reclaim,
        einstieg_bar=s.einstieg_bar,
        einstieg_preis=s.einstieg_preis,
        sl=s.sl,
        tp1=s.tp1,
        tp2=s.tp2,
        crv=s.crv,
        crv2=s.crv2,
        bounce_nr=s.bounce_nr,
        phase_id=s.phase,
        U_laufend=s.U_laufend,
        L_laufend=s.L_laufend,
        POC=s.POC,
    )


def berechne_reclaim_signale(
    df: pd.DataFrame,
    config: Optional[KernelConfig] = None,
) -> KernelLaufErgebnis:
    """Zustandsloser Kernel-Einstiegspunkt (E1): Segmentierung + Signal-Scan.

    Args:
        df: OHLCV-Fenster (ts/open/high/low/close/tick_volume). Wird intern
            ueber ``normalisiere_fenster`` auf den Datenvertrag gebracht.
        config: Optionaler Override (None -> alle Modulkonstanten,
            exakt frozen-Defaults).

    Returns:
        KernelLaufErgebnis mit Phasen, internen Signalen (inkl. Trade) und
        externer Signal-Ausgabe.
    """
    if config is None:
        config = KernelConfig()
    d = normalisiere_fenster(df)

    phasen = segmentiere_phasen(
        d,
        density_band=config.density_band,
        num_bins=None,  # NUM_BINS ist nicht ueber KernelConfig fuehrbar (K9)
        va_pct=config.va_pct,
        min_mountain_pct=config.min_mountain_pct,
        valley_rel=config.valley_rel,
    )

    signale: List[ReclaimSignal] = []
    for _pi, _p in enumerate(phasen, 1):
        for _s in find_reclaim_signals(
            d,
            _p,
            min_crv=MIN_RECLAIM_CRV if config.min_reclaim_crv is None else config.min_reclaim_crv,
            cooldown_bars=MIN_SIGNAL_ABSTAND_BARS if config.cooldown_bars is None else config.cooldown_bars,
            sl_pct=config.sl_pct,
            density_band=config.density_band,
            va_pct=config.va_pct,
            min_mountain_pct=config.min_mountain_pct,
            valley_rel=config.valley_rel,
        ):
            _s.phase = _pi
            signale.append(_s)
    signale.sort(key=lambda s: s.ts)

    return KernelLaufErgebnis(
        phasen=phasen,
        signale=signale,
        signal_ausgabe=[_zu_signal_ausgabe(s) for s in signale],
    )
