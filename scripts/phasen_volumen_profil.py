"""
SILVER M15: RANGE-PHASEN NACH VOLUME-PROFIL (POC/VAH/VAL + Multi-Mountain).

BASIS = tmp_phasen_move_m15.py (Backup bleibt erhalten). NEU: Die
Phasen-Grenzen werden durch das VOLUME-PROFIL je Phase definiert:

- Jede M15-Bar verteilt ihr tick_volume proportional ueber ihren
  High-Low-Bereich auf Preis-Bins (Standard-Volume-Profile).
- Das Histogramm wird geglaettet und in "BERGE" (Mountain) zerlegt:
  getrennt durch Taeller, die tiefer als VALLEY_REL des kleineren
  Nachbar-Peaks liegen. Nur signifikante Berge (>= MIN_MOUNTAIN_PCT
  des dominierenden Volumens) zaehlen.
- Jeder Berg bekommt seinen eigenen POC/VAH/VAL (VA_PCT-Value-Area).
- ZONEN-MODELL (Variante A, "Huelle"):
    OBEN  = hoechste VAH aller signifikanten Berge
    UNTEN = tiefste  VAL aller signifikanten Berge
    MITTE = POC des volumenstaerksten Bergs
    Zwischen-Berge erscheinen als Sub-POC/Sub-VAH/Sub-VAL (gestrichelt).
- Die bisherigen Schnittmengen-Linien bleiben als "REAKTIONS-Extreme"
  (dick gestrichelt) erhalten - sie zeigen die getesteten Rander,
  waehrend die Volume-Zone zeigt, WO DAS GELD WIRKLICH LIEGT.
- VA_PCT ist bewusst als Parameter herausgezogen (70 = Standard, 85/90 =
  breitere Value-Area) - wird spaeter getestet.
- SETUP B (RECLAIM/FAKEOUT) nach Patrick Nill (P1): Eine Bar sticht kurz
  ueber VAH (oder unter VAL) aus und schliesst wieder innerhalb der Zone
  (oder die Folge-Bar bestaetigt den Reclaim). Einstieg nach Bestaetigung.
  TRADE-MANAGEMENT (User-Vorgabe):
    - SL bei Entry = SL_PCT (0.45%) vom Einstiegspreis
    - TP1 = POC (Fair Value, 50% der Position)
    - KEIN SL-NACHZUG: Die Restcharge (50%) behaelt den Einstiegs-SL und
      laeuft zum TP2 = anderes Box-Ende (innen TP2_PUFFER_PCT 0.20%).
    - Alle Trades werden VOLLSTAENDIG aufgeloest (bis Datenende,
      sonst Close zum letzten Kurs).
  Die Zone wird KAUSAL bis zur Signal-Bar berechnet (laufendes
  Volume-Profil, kein Lookahead).

Die Phasen-SEGMENTIERUNG (Etablierung/Ausbruch/Moves) bleibt zunaechst
die kausale Schnittmengen-Logik aus dem Backup-Skript - erst die
GRENZEN/Darstellung werden durch das Volume-Profil bestimmt.

KAUSALITAET / KEIN LOOKAHEAD:
- Pivot-Bestaetigung nachlaufend (Lag PIVOT_LOOKBACK).
- Geburtszone nur mit bestaetigten Pivots (cutoff am Phasenstart).
- Kausales Signal-Screening bar fuer bar ueber laufende Volume-Zone (keine finale Phasen-Huellkurve als Filter).
- Regel-7-Finalize (letzter Grenz-Kontakt) ist POST-HOC am Datenende.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

# ==============================================================================
# TYPIFIZIERTE DATENVERTRAEGE (Strikte Nutzung von Type Hints)
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
    # Makro-Persistenz (Signal-Loop-Design v0.1): Schatten-Felder - Defaults
    # = Baseline-Verhalten (kein Einfluss auf _aufloesen/Exits/SL).
    edge_decision: Optional["ActiveEdgeDecision"] = None  # Kanten-Entscheidung (Audit)
    macro_active: bool = False                            # True = Signal an Tier-2-Kante


# ==============================================================================
# PARAMETER
# ==============================================================================

OUT_PNG: Path = Path(__file__).resolve().parent / "phasen_volumen_profil.png"
DB_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"

TOL: float = 0.34
TOL_TOUCH: float = 0.15
MIN_TOUCHES: int = 3
MIN_CANDLES: int = 46
MIN_PHASE_CANDLES: int = 46
MIN_CLUSTER: int = 2
MIN_ESTABLISH: int = 4
DENSITY_BAND: float = 0.15
MIN_SPREAD_PCT: float = 1.5
ERWEITERUNG_PCT: float = 1.0
SHIFT_TOL: float = 0.05
GRENZ_KONTAKT_TOL: float = 0.0
FENSTER_PIVOTS: int = 100
PIVOT_LOOKBACK: int = 2

VA_PCT: float = 0.93
NUM_BINS: int = 60
SMOOTH_WIN: int = 3
VALLEY_REL: float = 0.15
MIN_MOUNTAIN_PCT: float = 4.0
MIN_RECLAIM_CANDLES: int = 0
MIN_RECLAIM_BOUNCE: int = 2
MIN_RECLAIM_CRV: float = 1.0
MIN_SIGNAL_ABSTAND_BARS: int = 12
SL_PCT: float = 0.45
TP2_PUFFER_PCT: float = 0.20

ANTEIL_TP1: float = 25.0
TRAILING_PCT: float = 0.0
START: str = "2026-08-10"
ENDE: str = "2026-08-28"

for _a in sys.argv[1:]:
    if _a.startswith("--sl-pct="):
        SL_PCT = float(_a.split("=", 1)[1])
        print(f"==> SL_PCT ueberschrieben: {SL_PCT}")
    if _a.startswith("--va-pct="):
        VA_PCT = float(_a.split("=", 1)[1])
        print(f"==> VA_PCT ueberschrieben: {VA_PCT}")
    if _a.startswith("--mountain-pct="):
        MIN_MOUNTAIN_PCT = float(_a.split("=", 1)[1])
        print(f"==> MIN_MOUNTAIN_PCT ueberschrieben: {MIN_MOUNTAIN_PCT}")
    if _a.startswith("--valley-rel="):
        VALLEY_REL = float(_a.split("=", 1)[1])
        print(f"==> VALLEY_REL ueberschrieben: {VALLEY_REL}")
    if _a.startswith("--establish="):
        MIN_ESTABLISH = int(_a.split("=", 1)[1])
        print(f"==> MIN_ESTABLISH ueberschrieben: {MIN_ESTABLISH}")
    if _a.startswith("--tol="):
        TOL = float(_a.split("=", 1)[1])
        print(f"==> TOL ueberschrieben: {TOL}")
    if _a.startswith("--reclaim-candles="):
        MIN_RECLAIM_CANDLES = int(_a.split("=", 1)[1])
        print(f"==> MIN_RECLAIM_CANDLES ueberschrieben: {MIN_RECLAIM_CANDLES}")
    if _a.startswith("--start="):
        START = _a.split("=", 1)[1]
        print(f"==> START ueberschrieben: {START}")
    if _a.startswith("--ende="):
        ENDE = _a.split("=", 1)[1]
        print(f"==> ENDE ueberschrieben: {ENDE}")
    if _a.startswith("--bounce="):
        MIN_RECLAIM_BOUNCE = int(_a.split("=", 1)[1])
        print(f"==> MIN_RECLAIM_BOUNCE ueberschrieben: {MIN_RECLAIM_BOUNCE}")
    if _a.startswith("--crv="):
        MIN_RECLAIM_CRV = float(_a.split("=", 1)[1])
        print(f"==> MIN_RECLAIM_CRV ueberschrieben: {MIN_RECLAIM_CRV}")
    if _a.startswith("--cooldown="):
        MIN_SIGNAL_ABSTAND_BARS = int(_a.split("=", 1)[1])
        print(f"==> MIN_SIGNAL_ABSTAND_BARS ueberschrieben: {MIN_SIGNAL_ABSTAND_BARS}")
    if _a.startswith("--anteil-tp1="):
        ANTEIL_TP1 = float(_a.split("=", 1)[1])
        print(f"==> ANTEIL_TP1 ueberschrieben: {ANTEIL_TP1}")
    if _a.startswith("--tp2-puffer="):
        TP2_PUFFER_PCT = float(_a.split("=", 1)[1])
        print(f"==> TP2_PUFFER_PCT ueberschrieben: {TP2_PUFFER_PCT}")
    if _a == "--sl-nachzug=0":
        print("==> SL-Nachzug wurde konsequent entfernt (kein Effekt mehr)")
    if _a == "--sl-be=1":
        print("==> SL-Breakeven wurde konsequent entfernt (kein Effekt mehr)")
    if _a.startswith("--trailing="):
        TRAILING_PCT = float(_a.split("=", 1)[1])
        print(f"==> TRAILING_PCT ueberschrieben: {TRAILING_PCT}")

# ==============================================================================
# FENSTER-LABEL & STANDARD-ARTEFAKTE (Default-Ausgaben JEDES Laufs)
# ==============================================================================

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
TEST_DIR: Path = ROOT_DIR / "test"


def fenster_label(start: str, ende: str) -> str:
    """Kompaktes Fenster-Label fuer die Standard-Dateinamen.

    Args:
        start: Start-Datum (YYYY-MM-DD) des geladenen Fensters.
        ende: End-Datum (YYYY-MM-DD) des geladenen Fensters.

    Returns:
        "AUG" / "S1" / "S2" fuer die bekannten Referenzfenster, sonst ein
        datumsbasiertes Fallback-Label (YYYYMMDD_YYYYMMDD).
    """
    if start == "2026-08-10" and ende == "2026-08-28":
        return "AUG"
    if start == "2026-02-05" and ende == "2026-08-28":
        return "S1"
    if start == "2025-01-01" and ende == "2025-12-01":
        return "S2"
    return f"{start[:10].replace('-', '')}_{ende[:10].replace('-', '')}"


FENSTER_LABEL: str = fenster_label(START, ENDE)
STATS_TXT_DEFAULT: Path = TEST_DIR / f"stats_trades_{FENSTER_LABEL}.txt"
CHART_PNG_DEFAULT: Path = TEST_DIR / f"phasen_volumen_profil_{FENSTER_LABEL}.png"

# ==============================================================================
# 1) DATEN EINLESEN (Strikt DuckDB)
# ==============================================================================

def load_data(db_path: Path, start: str, ende: str) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB-Datei nicht gefunden: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    d = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
    con.close()
    d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    d["idx"] = np.arange(len(d))
    return d

df = load_data(DB_PATH, START, ENDE)

# ==============================================================================
# 2) PIVOTS
# ==============================================================================

def find_pivots(d: pd.DataFrame, n: int = PIVOT_LOOKBACK) -> pd.DataFrame:
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

piv = find_pivots(df.reset_index(drop=True), n=PIVOT_LOOKBACK).sort_values("ts").reset_index(drop=True)
print(f"Pivots (Lookback {PIVOT_LOOKBACK}): {len(piv)} | Candles: {len(df)}")

# ==============================================================================
# 3) SCHNITTMENGEN-LINIE
# ==============================================================================

def level_schnittmenge(
    prices: List[float] | np.ndarray,
    target_typ: Literal["H", "L"] = "H",
    band: float = DENSITY_BAND,
    min_cluster: int = MIN_CLUSTER,
    erweiterung_pct: float = ERWEITERUNG_PCT,
) -> Optional[float]:
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
    if level is None or not len(prices):
        return 0
    return int(np.sum(np.abs(np.array(prices, dtype=float) - level) <= band))


def _linie(prices: List[float], typ: Literal["H", "L"]) -> Optional[float]:
    if not prices:
        return None
    w = prices if len(prices) <= FENSTER_PIVOTS else prices[-FENSTER_PIVOTS:]
    return level_schnittmenge(w, typ)


def _final_level(schnitt: Optional[float], birth: Optional[float], typ: Literal["H", "L"]) -> Optional[float]:
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
    if schnitt is None:
        return birth
    if birth is None or conf_ts is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _birth_level(birth: Optional[pd.DataFrame], typ: Literal["H", "L"]) -> Optional[float]:
    if birth is None or len(birth) == 0:
        return None
    prices = birth.loc[birth["typ"] == typ, "price"].values.astype(float)
    if not len(prices):
        return None
    d = np.array([np.sum(np.abs(prices - x) <= DENSITY_BAND) for x in prices])
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

# ==============================================================================
# 3b) VOLUME-PROFIL BERECHNUNG
# ==============================================================================

def build_volume_profile(sub: pd.DataFrame, num_bins: int = NUM_BINS) -> Optional[VolumeProfileData]:
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
    if win <= 1 or len(vol) < win:
        return vol.astype(float)
    return np.convolve(vol, np.ones(win) / win, mode="same")


def find_mountains(
    vol_s: np.ndarray,
    min_pct: float = MIN_MOUNTAIN_PCT,
    valley_rel: float = VALLEY_REL,
) -> List[Tuple[int, int, int]]:
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


def compute_volume_zone(sub: pd.DataFrame) -> Optional[VolumeZone]:
    prof = build_volume_profile(sub)
    if prof is None:
        return None
    vol_s = smooth_vol(prof.vol)
    mountains = find_mountains(vol_s)
    if not mountains:
        return None
    dominant_peak = mountains[0][1]
    peaks: List[MountainPeak] = []
    for m in mountains:
        va = va_for_mountain(vol_s, prof.edges, m, dominant_peak)
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

# ==============================================================================
# 4) PHASEN-SEGMENTIERUNG
# ==============================================================================

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
        birth_h = _birth_level(birth, "H")
        birth_l = _birth_level(birth, "L")
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
                if U_conf_ts is None and birth_h is not None and abs(pv - birth_h) <= DENSITY_BAND:
                    U_conf_ts = t_prev
            else:
                pv = float(df["low"].iloc[j - PIVOT_LOOKBACK])
                l_acc.append(pv)
                l_ts.append(t_prev)
                if L_conf_ts is None and birth_l is not None and abs(pv - birth_l) <= DENSITY_BAND:
                    L_conf_ts = t_prev

        U = _linie(h_acc, "H")
        L = _linie(l_acc, "L")

        if est_idx is None and U is not None and L is not None and n_touches(h_acc, U) + n_touches(l_acc, L) >= MIN_ESTABLISH:
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

    U_final = _final_level_bestaetigt(_linie(h_acc, "H"), birth_h, "H", U_conf_ts)
    L_final = _final_level_bestaetigt(_linie(l_acc, "L"), birth_l, "L", L_conf_ts)

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
        U_final=_final_level_bestaetigt(_linie(h_clean, "H"), birth_h, "H", U_conf_ts),
        L_final=_final_level_bestaetigt(_linie(l_clean, "L"), birth_l, "L", L_conf_ts),
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

# 4b) Datenende-Finalize (Regel 7, D1-Variante)
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
        p_last.U_final = _final_level_bestaetigt(_linie(p_last.h_prices, "H"), p_last.birth_h, "H", p_last.U_conf_ts)
        p_last.L_final = _final_level_bestaetigt(_linie(p_last.l_prices, "L"), p_last.birth_l, "L", p_last.L_conf_ts)
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

# ==============================================================================
# 5) CANDLE-STATISTIK & VOLUME-ZONEN JE PHASE
# ==============================================================================

for p in phases:
    mask = (df["ts"] >= p.start) & (df["ts"] <= p.ende)
    p.n_candles = int(mask.sum())
    p.handels_h = p.n_candles * 15.0 / 60.0
    p.i_start = int(df.loc[mask, "idx"].min()) if p.n_candles else 0
    p.i_ende = int(df.loc[mask, "idx"].max()) if p.n_candles else 0
    p.touches_h = len(p.h_prices)
    p.touches_l = len(p.l_prices)
    p.close_h = n_touches(p.h_prices, p.U_final)
    p.close_l = n_touches(p.l_prices, p.L_final)
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
    vz = compute_volume_zone(sub)
    if vz is not None:
        p.vol_zone = vz
        p.U_zone = vz.U_zone
        p.L_zone = vz.L_zone
        p.POC = vz.POC
        p.n_berge = vz.n_mountains
        p.zone_breite = vz.U_zone - vz.L_zone

# ==============================================================================
# 5b) UEBERSICHT & VERIFIKATION
# ==============================================================================

_erwartet = [
    {"start": "2026-08-21 05:00", "ende": "2026-08-25 02:00", "U": 69.914, "L": 68.370},
    {"start": "2026-08-25 04:30", "ende": "2026-08-25 15:45", "U": 68.220, "L": 67.544},
]
print("\n=== VERIFIKATION (Referenz 21.08.-Sicht) ===")
_fmt = lambda t: t.strftime("%Y-%m-%d %H:%M")
_relevant = [p for p in phases if p.start >= pd.Timestamp("2026-08-21 00:00")]
for k, p in enumerate(_relevant[:2]):
    e = _erwartet[k]
    ok = (
        _fmt(p.start) == e["start"]
        and _fmt(p.ende) == e["ende"]
        and p.U_final is not None
        and abs(p.U_final - e["U"]) < 0.01
        and p.L_final is not None
        and abs(p.L_final - e["L"]) < 0.01
    )
    print(
        f"Phase {k+1} (ab 21.08): {'OK ' if ok else 'ABWEICHUNG'} "
        f"{_fmt(p.start)} -> {_fmt(p.ende)} "
        f"| OBEN {p.U_final:.3f} (erw. {e['U']}) | UNTEN {p.L_final:.3f} (erw. {e['L']})"
    )
print(f"RESULTAT: {len(phases)} Phasen gesamt, {len(_relevant)} ab 21.08. (Referenz-Abgleich oben)")

# ==============================================================================
# 5c) SETUP B: RECLAIM/FAKEOUT-SIGNALE (Reiner Realtime-Modus ohne Lookahead)
# ==============================================================================

def _laufende_zone(df: pd.DataFrame, p: PhaseData, k: int) -> Optional[VolumeZone]:
    return compute_volume_zone(df.iloc[p.i_start : k + 1])


def _bounce_nr(
    h_prices: List[float],
    h_ts: List[pd.Timestamp],
    l_prices: List[float],
    l_ts: List[pd.Timestamp],
    ts_k: pd.Timestamp,
    U: float,
    L: float,
) -> Tuple[int, int]:
    n_h = 1 + sum(1 for pr, t in zip(h_prices, h_ts) if t <= ts_k and abs(pr - U) <= DENSITY_BAND)
    n_l = 1 + sum(1 for pr, t in zip(l_prices, l_ts) if t <= ts_k and abs(pr - L) <= DENSITY_BAND)
    return n_h, n_l


def _aufloesen(
    df: pd.DataFrame,
    s: ReclaimSignal,
    sl_pct: Optional[float] = None,
    anteil_tp1: float = ANTEIL_TP1,
    trailing_pct: float = TRAILING_PCT,
) -> TradeResolution:
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


def _cooldown_ok(k: int,
                 richtung: Literal["SHORT", "LONG"],
                 dec: Optional["ActiveEdgeDecision"],
                 last_bar_t1: Dict[Literal["SHORT", "LONG"], int],
                 last_bar_t2: Dict[Literal["SHORT", "LONG"], int],
                 cooldown_bars: int) -> bool:
    """D2-asym-Cooldown-Check (Signal-Loop-Design v0.4).

    Asymmetrische Cooldown-Invariante (Mentor-Freigabe 03.09.):
      * Tier 1 (dec is None ODER tier == 1) prueft NUR last_bar_t1 - ein
        spekulatives Tier-2-Antestat kontaminiert die Baseline-Kette nicht.
      * Tier 2 prueft last_bar_t2 UND last_bar_t1: Ein Tier-1-Signal
        (Baseline-DNA) sperrt ein direkt folgendes Tier-2-Signal
        (k - last_bar_t1 < cooldown_bars), nie umgekehrt.

    Args:
        k: aktueller Bar-Index.
        richtung: Signalrichtung ("SHORT"/"LONG").
        dec: Kanten-Entscheidung des Kandidaten (None = Baseline-Modus).
        last_bar_t1: letzte Tier-1-Signal-Bar je Richtung.
        last_bar_t2: letzte Tier-2-Signal-Bar je Richtung.
        cooldown_bars: Mindestabstand (MIN_SIGNAL_ABSTAND_BARS).

    Returns:
        True, wenn der Cooldown eingehalten ist.
    """
    if dec is None or dec.tier == 1:
        return k - last_bar_t1[richtung] >= cooldown_bars
    return (k - last_bar_t2[richtung] >= cooldown_bars
            and k - last_bar_t1[richtung] >= cooldown_bars)


def _cooldown_set(k: int,
                  richtung: Literal["SHORT", "LONG"],
                  dec: Optional["ActiveEdgeDecision"],
                  last_bar_t1: Dict[Literal["SHORT", "LONG"], int],
                  last_bar_t2: Dict[Literal["SHORT", "LONG"], int]) -> None:
    """D2-asym-Cooldown-Setzen (Signal-Loop-Design v0.4).

    Tier 1 setzt last_bar_t1, Tier 2 setzt last_bar_t2. Ein Tier-2-Signal
    blockiert die Baseline/Tier-1-Kette NIE (Asymmetrie).

    Args:
        k: aktueller Bar-Index.
        richtung: Signalrichtung ("SHORT"/"LONG").
        dec: Kanten-Entscheidung des ausgeloesten Signals (None = Baseline).
        last_bar_t1: letzte Tier-1-Signal-Bar je Richtung.
        last_bar_t2: letzte Tier-2-Signal-Bar je Richtung.
    """
    if dec is None or dec.tier == 1:
        last_bar_t1[richtung] = k
    else:
        last_bar_t2[richtung] = k


def find_reclaim_signals(
    df: pd.DataFrame,
    p: PhaseData,
    min_candles: int = MIN_RECLAIM_CANDLES,
    min_bounce: int = MIN_RECLAIM_BOUNCE,
    min_crv: float = MIN_RECLAIM_CRV,
    cooldown_bars: int = MIN_SIGNAL_ABSTAND_BARS,
    st_u: Optional["MacroLineState"] = None,
    st_l: Optional["MacroLineState"] = None,
) -> List[ReclaimSignal]:
    """Setup-B-Signale (Reclaim/Fakeout) - reiner Echtzeit-Modus ohne Lookahead.

    Makro-Persistenz (Signal-Loop-Design v0.1-v0.4, E1-E5 + D2-asym):
    Optional koennen die MacroLineState-Objekte der Seiten injiziert werden
    (Zustand NACH Phase p-1, inkl. R4-Boundary). Dann ersetzt die operative
    Kanten-Auswahl (resolve_active_edge) die implizite U_zone/L_zone-Wahl:
      * Tier 1 = U_zone/L_zone, sofern die lokale Pivot-Dichte sie traegt (E2);
      * Tier 2 = distanzbegrenzter Makro-Anker (E3/E5) mit v0.4-Kanten-
        Kapselung (nur abriegelnde Anker verdrängen);
      * Penetrations-Gate NUR auf Tier 2 (E4, Mentor §9.3);
      * kein Intra-Phase-Bounce fuer Tier 2 (Mentor §9.4);
      * D2-asym-Cooldown (v0.4): getrennte Zaehler last_bar_t1/last_bar_t2
        (Tier 1 sperrt Tier 2, nie umgekehrt).
    Default st_u/st_l = None -> exakt Baseline-Verhalten (bitgenau; _dec_u/
    _dec_l sind None -> _cooldown_ok/_cooldown_set arbeiten auf last_bar_t1
    = gemeinsame Baseline-Kette).
    """
    sigs: List[ReclaimSignal] = []
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values
    op = df["open"].values
    ts = df["ts"].values
    last_bar_t1: Dict[Literal["SHORT", "LONG"], int] = {
        "SHORT": -10**9, "LONG": -10**9}
    last_bar_t2: Dict[Literal["SHORT", "LONG"], int] = {
        "SHORT": -10**9, "LONG": -10**9}
    tp2_puffer = TP2_PUFFER_PCT / 100.0
    sl_p = SL_PCT / 100.0

    # Makro-Persistenz-Init (nur wenn States injiziert; sonst Baseline bitgenau)
    _makro = st_u is not None or st_l is not None
    _range_arr: Optional[np.ndarray] = None
    if _makro:
        try:
            from macro_persistence import resolve_active_edge
        except ImportError as _e:  # pragma: no cover
            raise RuntimeError(
                "macro_persistence.py erforderlich fuer Makro-Kanten-Auswahl"
            ) from _e
        _range_arr = (df["high"] - df["low"]).rolling(
            200, min_periods=20).mean().shift(1).to_numpy(dtype=float)

    # Kausale Schleife bar fuer bar (kein Lookahead ueber finale Phasen-Huellkurve)
    for k in range(p.i_start, p.i_ende):
        if k - p.i_start + 1 < min_candles:
            continue
        vz = _laufende_zone(df, p, k)
        if vz is None:
            continue
        U, L, POC = vz.U_zone, vz.L_zone, vz.POC

        ts_k = pd.Timestamp(ts[k])

        # --- Operative Kanten-Auswahl (E1-E5): Baseline bitgenau, Makro-Pfad
        #     nur mit injizierten MacroLineState-Objekten (je Seite unabhaengig).
        if _makro:
            _rr = (float(_range_arr[k])
                   if _range_arr is not None and np.isfinite(_range_arr[k])
                   else None)
            _cur = float(cl[k])
            if st_u is not None:
                _dec_u = resolve_active_edge(
                    st=st_u, lokal_kante=U,
                    phasen_prices=p.h_prices, phasen_ts=p.h_ts, ts_k=ts_k,
                    current_price=_cur, extreme=float(hi[k]),
                    range_ref=_rr, level_schnittmenge=level_schnittmenge,
                )
                U_eff = (_dec_u.edge_price if _dec_u is not None
                         and _dec_u.penetriert else None)
            else:
                _dec_u = None
                U_eff = U if hi[k] > U else None
            if st_l is not None:
                _dec_l = resolve_active_edge(
                    st=st_l, lokal_kante=L,
                    phasen_prices=p.l_prices, phasen_ts=p.l_ts, ts_k=ts_k,
                    current_price=_cur, extreme=float(lo[k]),
                    range_ref=_rr, level_schnittmenge=level_schnittmenge,
                )
                L_eff = (_dec_l.edge_price if _dec_l is not None
                         and _dec_l.penetriert else None)
            else:
                _dec_l = None
                L_eff = L if lo[k] < L else None
        else:
            _dec_u = _dec_l = None
            # Baseline exakt wie bisher: Kandidat = Durchstich ohne Obergrenze
            U_eff = U if hi[k] > U else None
            L_eff = L if lo[k] < L else None

        if U_eff is None and L_eff is None:
            continue

        # Bounce-Zaehlung gegen die effektiven Kanten (Fallback = lokale Kante,
        # wenn die Gegenseite in diesem Bar kein Kandidat ist - wie Baseline).
        nb_h, nb_l = _bounce_nr(
            p.h_prices, p.h_ts, p.l_prices, p.l_ts, ts_k,
            U_eff if U_eff is not None else U,
            L_eff if L_eff is not None else L,
        )

        if U_eff is not None:
            if cl[k] <= U_eff:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            # A3-Bounds-Guard (v0.4.x): Ausfuehrungs-Bar k+2 muss im Phasen-
            # Kontext existieren (k+2 <= p.i_ende), sonst op[k+2]-IndexError
            # am Datenende (Variante 1: kein Signal ohne Ausfuehrungs-Bar).
            elif k + 2 <= p.i_ende and cl[k + 1] <= U_eff:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            # Mentor §9.4: Tier-2-Signale brauchen keinen Intra-Phase-Bounce
            # (Legitimation durch ev >= 2 Phasen); Tier 1 behaelt min_bounce.
            _bounce_ok = (nb_h >= min_bounce
                          or (_dec_u is not None and _dec_u.tier == 2))
            if (
                reclaim is not None
                and e_bar is not None
                and e_bar <= p.i_ende
                and e_preis > POC
                and _bounce_ok
                and _cooldown_ok(k, "SHORT", _dec_u, last_bar_t1,
                                 last_bar_t2, cooldown_bars)
            ):
                sl = e_preis * (1.0 + sl_p)
                tp1 = POC
                tp2 = L * (1.0 + tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    _cooldown_set(k, "SHORT", _dec_u, last_bar_t1,
                                  last_bar_t2)
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
                        edge_decision=_dec_u,
                        macro_active=(_dec_u is not None and _dec_u.tier == 2),
                    )
                    sig.trade = _aufloesen(df, sig)
                    sigs.append(sig)

        if L_eff is not None:
            if cl[k] >= L_eff:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            # A3-Bounds-Guard (v0.4.x): symmetrisch zum SHORT-Zweig -
            # Ausfuehrungs-Bar k+2 muss im Phasen-Kontext existieren.
            elif k + 2 <= p.i_ende and cl[k + 1] >= L_eff:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            # Mentor §9.4: Tier-2-Signale ohne Intra-Phase-Bounce-Huerde
            _bounce_ok = (nb_l >= min_bounce
                          or (_dec_l is not None and _dec_l.tier == 2))
            if (
                reclaim is not None
                and e_bar is not None
                and e_bar <= p.i_ende
                and e_preis < POC
                and _bounce_ok
                and _cooldown_ok(k, "LONG", _dec_l, last_bar_t1,
                                 last_bar_t2, cooldown_bars)
            ):
                sl = e_preis * (1.0 - sl_p)
                tp1 = POC
                tp2 = U * (1.0 - tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    _cooldown_set(k, "LONG", _dec_l, last_bar_t1,
                                  last_bar_t2)
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
                        edge_decision=_dec_l,
                        macro_active=(_dec_l is not None and _dec_l.tier == 2),
                    )
                    sig.trade = _aufloesen(df, sig)
                    sigs.append(sig)
    return sigs


reclaim_signals: List[ReclaimSignal] = []
# ==============================================================================
# 5d) MAKRO-LIVE-HOOK (Signal-Loop-Design v0.1, Schritt 3)
#     Aktivierung NUR via CLI-Flag:  python ... --macro-live
#     Default: aus -> exakt Baseline (bitgenau).
#
#     Kausalitaets-Axiom (Mentor, nicht verhandelbar): Die Reihenfolge ist
#       Boundary(p-1) -> Scan(p) -> Touches(p)
#     Wer Touches aus Phase p in den State einspeist, BEVOR die Signale fuer
#     Phase p gescannt werden, begeht Lookahead-Betrug (der Algorithmus
#     wuesste bei Bar 10 bereits, welches Extremum der Markt bei Bar 80
#     antestet). Scope-Trennung: --macro-live initialisiert ausschliesslich
#     st_u/st_l und reicht sie an find_reclaim_signals weiter - keine
#     globalen Variablen, keine Phasen-Zuschnitte.
#
#     Fuer den Delta-Report (Schritt 4) wird zusaetzlich ein Baseline-
#     Kontrolllauf durchgefuehrt (ohne States) - rein lesend, nur zur
#     Differenz-Anzeige.
# ==============================================================================
_macro_live = "--macro-live" in sys.argv

if _macro_live:
    try:
        from macro_persistence import (  # noqa: F401
            MacroLineState,
            MacroTouch,
            PhaseBoundaryEvent,
            on_phase_boundary,
            update_touch,
        )
    except ImportError as _e:
        raise RuntimeError(
            "macro_persistence.py erforderlich fuer --macro-live"
        ) from _e

    st_u = MacroLineState(side="UPPER")
    st_l = MacroLineState(side="LOWER")

    # Baseline-Kontrolllauf (rein lesend, nur fuer den Delta-Report)
    _baseline_sigs: List[ReclaimSignal] = []
    for _pi_b, _p_b in enumerate(phases, 1):
        for _s_b in find_reclaim_signals(df, _p_b):
            _s_b.phase = _pi_b
            _baseline_sigs.append(_s_b)

    for _pi, _p in enumerate(phases, 1):
        # 1) Boundary(p-1) in den State (R4, selektives Loeschen)
        if _pi > 1:
            _prev = phases[_pi - 2]
            if _prev.break_dir is not None and _prev.brk_idx is not None:
                _ev = PhaseBoundaryEvent(
                    ts=df["ts"].iloc[_prev.brk_idx],
                    break_dir=_prev.break_dir,
                    broken_level=_prev.brk_kante,
                    ended_phase_id=_pi - 2,
                )
                on_phase_boundary(st_u, _ev)
                on_phase_boundary(st_l, _ev)
        # 2) Scan(p) mit Makro-Sicht (Tier 2 fuehrt in jungen Phasen)
        for _s in find_reclaim_signals(df, _p, st_u=st_u, st_l=st_l):
            _s.phase = _pi
            reclaim_signals.append(_s)
        # 3) Touches(p) NACH dem Scan in den State (Evidenz fuer Folge-Phasen)
        for _t, _x in zip(_p.h_ts, _p.h_prices):
            update_touch(st_u, MacroTouch(_t, float(_x), "UPPER", _pi - 1),
                         level_schnittmenge)
        for _t, _x in zip(_p.l_ts, _p.l_prices):
            update_touch(st_l, MacroTouch(_t, float(_x), "LOWER", _pi - 1),
                         level_schnittmenge)

    # Kausale Sortierung der Macro-Live-Signale
    reclaim_signals.sort(key=lambda s: s.ts)

    # --- Delta-Report (Konsolenausgabe, kein Datei-Eingriff) ---
    _bset = {(s.typ, s.bar, s.einstieg_bar) for s in _baseline_sigs}
    _mset = {(s.typ, s.bar, s.einstieg_bar) for s in reclaim_signals}
    _entfallen = [s for s in _baseline_sigs
                  if (s.typ, s.bar, s.einstieg_bar) not in _mset]
    _neu = [s for s in reclaim_signals
            if (s.typ, s.bar, s.einstieg_bar) not in _bset]
    print("\n" + "=" * 118)
    print("DELTA-REPORT --macro-live (Baseline vs. Makro-Live, AUG)")
    print("=" * 118)
    print(f"  Baseline-Signale: {len(_baseline_sigs)} | "
          f"Macro-Live-Signale: {len(reclaim_signals)}")
    print(f"  Entfallen: {len(_entfallen)} | Neu: {len(_neu)} | "
          f"Identisch: {len(_bset & _mset)}")
    if _entfallen:
        print("\n  ENTALLENE Signale (Baseline, nicht in Macro-Live):")
        for s in _entfallen:
            assert s.trade is not None
            print(f"    P{s.phase:2d} {s.ts:%a %d.%m %H:%M} {s.typ:5s} "
                  f"Ein {s.einstieg_preis:.3f} | {s.trade.resultat} "
                  f"{s.trade.r_mult:+.2f}R | Bo {s.bounce_nr} | "
                  f"U_zone {s.U_laufend:.3f}")
    if _neu:
        print("\n  NEUE Signale (nur Macro-Live):")
        for s in _neu:
            assert s.trade is not None
            _ed = s.edge_decision
            _tier_txt = (f"Tier {_ed.tier} @ {_ed.edge_price:.3f}"
                         if _ed is not None else "?")
            _ev_txt = (_ed.anchor.kurz() if _ed is not None
                       and _ed.anchor is not None else "")
            print(f"    P{s.phase:2d} {s.ts:%a %d.%m %H:%M} {s.typ:5s} "
                  f"Ein {s.einstieg_preis:.3f} | {s.trade.resultat} "
                  f"{s.trade.r_mult:+.2f}R | {_tier_txt} | {_ev_txt}")
    print("=" * 118)

else:
    for _pi, _p in enumerate(phases, 1):
        for _s in find_reclaim_signals(df, _p):
            _s.phase = _pi
            reclaim_signals.append(_s)
    reclaim_signals.sort(key=lambda s: s.ts)

_n_win = sum(1 for s in reclaim_signals if s.trade and s.trade.resultat == "GEWONNEN")
_n_loss = sum(1 for s in reclaim_signals if s.trade and s.trade.resultat == "VERLOREN")
_n_neu = sum(1 for s in reclaim_signals if s.trade and s.trade.resultat == "NEUTRAL")
_n_tp1 = sum(1 for s in reclaim_signals if s.trade and s.trade.tp1_hit)
_n_tp2 = sum(1 for s in reclaim_signals if s.trade and s.trade.tp2_hit)
_n_sl1 = sum(1 for s in reclaim_signals if s.trade and s.trade.sl_hit1)
_n_sl2 = sum(1 for s in reclaim_signals if s.trade and s.trade.sl_hit2)
_n_trail = sum(1 for s in reclaim_signals if s.trade and s.trade.grund1 == "TRAIL")

# ==============================================================================
# 6) KONSOLENAUSGABE
# ==============================================================================

pd.set_option("display.width", 230)
print("\n=== PHASEN (VOLUME-PROFIL: POC/VAH/VAL-Zonen) ===")
for i_p, p in enumerate(phases, 1):
    u_str = f"{p.U_final:.3f}" if p.U_final is not None else "N/A"
    l_str = f"{p.L_final:.3f}" if p.L_final is not None else "N/A"
    ok = " [HANDELBAR]" if p.handelbar else ""
    print(
        f"Phase {i_p}: {p.start:%a %d.%m %H:%M} -> {p.ende:%a %d.%m %H:%M} "
        f"({p.handels_h:.1f}h, {p.n_candles}C){ok} "
        f"| Pivots: {p.touches_h}H/{p.touches_l}L"
    )
    vz = p.vol_zone
    if vz is not None:
        print(
            f"    VOLUME-ZONE: OBEN {vz.U_zone:.3f} | MITTE(POC) {vz.POC:.3f} | UNTEN {vz.L_zone:.3f} "
            f"| Breite {p.zone_breite:.3f} | {p.n_berge} Berg(e)"
        )
        for j_m, pk in enumerate(vz.peaks, 1):
            print(
                f"      Berg {j_m}: POC {pk.poc:.3f} | VAL {pk.val:.3f} | VAH {pk.vah:.3f} "
                f"| Vol {pk.vol:.0f} | Peak-Anteil {pk.peak_share_pct:.0f}%"
            )
    else:
        print("    VOLUME-ZONE: keine (zu wenig Daten)")
    print(f"    REAKTIONS-Extreme (Schnittmengen): OBEN {u_str} | UNTEN {l_str} (dick gestrichelt im Chart)")
    if p.U_hist:
        dev_u = " -> ".join(f"{t:%a %H:%M} {v:.3f}" for t, v in p.U_hist)
        print(f"    OBEN-Entwicklung ({p.n_U_shifts} Verschiebungen): {dev_u}")
    if p.L_hist:
        dev_l = " -> ".join(f"{t:%a %H:%M} {v:.3f}" for t, v in p.L_hist)
        print(f"    UNTEN-Entwicklung ({p.n_L_shifts} Verschiebungen): {dev_l}")
    if p.U_proj_val is not None:
        _c = p.U_conf_ts
        z = f"bestaetigt {_c:%a %H:%M}" if _c is not None else "NIE bestaetigt (Projektion)"
        print(f"    OBEN-Geburtszone {p.U_proj_val:.3f}: {z}")
    if p.L_proj_val is not None:
        _c = p.L_conf_ts
        z = f"bestaetigt {_c:%a %H:%M}" if _c is not None else "NIE bestaetigt (Projektion)"
        print(f"    UNTEN-Geburtszone {p.L_proj_val:.3f}: {z}")

print("\n=== MOVES (Phasenwechsel) ===")
for m in moves:
    d_min = (m.bis_ts - m.von_ts).total_seconds() / 60.0
    pr_diff = (m.bis_pr - m.von_pr) if m.von_pr is not None else 0.0
    pr_str = f"{m.von_pr:.3f}" if m.von_pr is not None else "N/A"
    print(
        f"{'UP  ' if m.dir=='up' else 'DOWN'} {m.von_ts:%a %H:%M} ({pr_str}) "
        f"-> {m.bis_ts:%a %H:%M} ({m.bis_pr:.3f})  "
        f"{pr_diff:+.3f} USD in {d_min:.0f} min"
    )

_trail_txt = f" | TRAILING {TRAILING_PCT:.2f}%" if TRAILING_PCT > 0 else ""
_nach_txt = "SL bleibt am Entry (kein Nachzug)"
_ant_txt = (
    f"{ANTEIL_TP1:.0f}/{100-ANTEIL_TP1:.0f}"
    if 0 < ANTEIL_TP1 < 100
    else ("100/0" if ANTEIL_TP1 >= 100 else "0/100")
)
print(
    f"\n=== SETUP B: RECLAIM-SIGNALE (SL {SL_PCT:.1f}% Entry; {_nach_txt}; "
    f"TP2=Box-Ende innen 0.15%; Split {_ant_txt}{_trail_txt}; alle aufgeloest) ==="
)
if not reclaim_signals:
    print("  keine Signale")
for s in reclaim_signals:
    assert s.trade is not None
    typ_str = "SHORT" if s.typ == "SHORT" else "LONG "
    print(
        f"  P{s.phase:2d} {s.ts:%a %d.%m %H:%M} {typ_str} Rec {s.reclaim:8s} "
        f"Ein {s.einstieg_preis:.3f} | SL {s.sl:.3f} | TP1 {s.tp1:.3f} | TP2 {s.tp2:.3f} "
        f"| CRV {s.crv:.2f} | Bo {s.bounce_nr} | H1 {s.trade.exit1:.3f} ({s.trade.grund1}) {s.trade.r1:+.2f}R | "
        f"H2 {s.trade.exit2:.3f} ({s.trade.grund2}) {s.trade.r2:+.2f}R | {s.trade.resultat} {s.trade.r_mult:+.2f}R"
    )

print(f"\n=== STATISTIK SETUP B (SL {SL_PCT:.1f}% Entry; {_nach_txt}; Split {_ant_txt}{_trail_txt}) ===")
print(f"  Signale: {len(reclaim_signals)} | GEWONNEN {_n_win} | VERLOREN {_n_loss} | NEUTRAL {_n_neu}")
if _n_win + _n_loss > 0:
    print(f"  Trefferquote: {100.0*_n_win/(_n_win+_n_loss):.0f}% (nur entschiedene)")
_s = sum(s.trade.r_mult for s in reclaim_signals if s.trade) if reclaim_signals else 0.0
print(
    f"  Summe R: {_s:+.2f} | avg R: {(_s/len(reclaim_signals) if reclaim_signals else 0):+.2f} "
    f"| max R: {max(s.trade.r_mult for s in reclaim_signals if s.trade):+.2f} "
    f"| min R: {min(s.trade.r_mult for s in reclaim_signals if s.trade):+.2f}"
)
print(
    f"  TP1(POC) erreicht: {_n_tp1}/{len(reclaim_signals)} | TP2(Box-Ende) erreicht: {_n_tp2} "
    f"| SL Haelfte1: {_n_sl1} | SL Haelfte2: {_n_sl2} | TRAIL-Exit: {_n_trail}"
)

print(
    "\n=== HANDELBARE RANGES (Filter: >= %d Touches je Grenze, >= %d Candles, Breite >= %.1f%%) ==="
    % (MIN_TOUCHES, MIN_CANDLES, MIN_SPREAD_PCT)
)
ranges = [p for p in phases if p.handelbar]
for i_r, p in enumerate(ranges, 1):
    print(f"\nRange {i_r}: {p.start:%a %d.%m %H:%M} -> {p.ende:%a %d.%m %H:%M}  ({p.handels_h:.1f}h)")
    vz = p.vol_zone
    if vz is not None:
        print(
            f"    VOLUME-ZONE OBEN  {vz.U_zone:.3f} | MITTE(POC) {vz.POC:.3f} | UNTEN {vz.L_zone:.3f} "
            f"| Breite {p.zone_breite:.3f} | {p.n_berge} Berg(e)"
        )
        for j_p, pk in enumerate(vz.peaks, 1):
            print(
                f"      Berg {j_p}: POC {pk.poc:.3f} | VAL {pk.val:.3f} | VAH {pk.vah:.3f} "
                f"| Peak-Anteil {pk.peak_share_pct:.0f}%"
            )
    print(f"    REAKTIONS-Extreme (Schnittmengen): OBEN {p.U_final:.3f} | UNTEN {p.L_final:.3f}")

# ==============================================================================
# 6a) STATISTIK-PAKET & TEXTFILE
# ==============================================================================

_n_calls = sum(1 for s in reclaim_signals if s.typ == "LONG")
_n_sells = sum(1 for s in reclaim_signals if s.typ == "SHORT")
_decided = _n_win + _n_loss
_winrate = 100.0 * _n_win / _decided if _decided else 0.0
_avg_crv = sum(s.crv for s in reclaim_signals) / len(reclaim_signals) if reclaim_signals else 0.0
_sum_r = sum(s.trade.r_mult for s in reclaim_signals if s.trade)
_gewinn_pct = _sum_r * SL_PCT
_stat_lines = [
    f"STATISTIK {START} - {ENDE}",
    f"# CALLS (LONG):  {_n_calls:2d}   # SELLS (SHORT): {_n_sells:2d}",
    f"WINRATE:  {_winrate:.0f}%  ({_n_win}W/{_n_loss}L/{_n_neu}N)",
    f"avg CRV:  {_avg_crv:.2f}",
    f"Summe R:  {_sum_r:+.2f}",
    f"Gesamtgewinn: {_gewinn_pct:+.2f}% (Risiko {SL_PCT:.2f}%/Trade)",
]

OUT_TXT = OUT_PNG.with_suffix(".txt")
_fmt_ts = lambda t: t.strftime("%Y-%m-%d %H:%M")
with open(OUT_TXT, "w", encoding="utf-8") as _f:
    _f.write("\n".join(_stat_lines) + "\n\n")
    _f.write("=== SETUP B: RECLAIM-SIGNALE (alle Trades) ===\n")
    _f.write(
        f"Parameter: SL_PCT={SL_PCT} | "
        f"TP2_PUFFER_PCT={TP2_PUFFER_PCT} | Split {_ant_txt} | "
        f"TRAILING_PCT={TRAILING_PCT} | "
        f"MIN_RECLAIM_BOUNCE={MIN_RECLAIM_BOUNCE} | MIN_RECLAIM_CRV={MIN_RECLAIM_CRV} | "
        f"Cooldown={MIN_SIGNAL_ABSTAND_BARS} Bars | KEIN SL-NACHZUG\n"
    )
    _f.write(
        "Nr | Phase | Signal-Bar(ts)      | Typ   | Reclaim  | EntryBar | Entry   | SL      | TP1     | TP2     | "
        "CRV   | CRV2  | Bo | Exit1   | Grund | R1    | Exit2   | Grund | R2    | R-mult | Resultat\n"
    )
    for _i, s in enumerate(reclaim_signals, 1):
        assert s.trade is not None
        _f.write(
            f"{_i:2d} | P{s.phase:<2d} | {_fmt_ts(s.ts)} | {s.typ:5s} | {s.reclaim:8s} | "
            f"{s.einstieg_bar:8d} | {s.einstieg_preis:.3f} | {s.sl:.3f} | {s.tp1:.3f} | {s.tp2:.3f} | "
            f"{s.crv:.2f} | {s.crv2:.2f} | {s.bounce_nr:2d} | "
            f"{s.trade.exit1:.3f} | {s.trade.grund1:5s} | {s.trade.r1:+.2f} | "
            f"{s.trade.exit2:.3f} | {s.trade.grund2:5s} | {s.trade.r2:+.2f} | {s.trade.r_mult:+.2f} | {s.trade.resultat}\n"
        )
    if not reclaim_signals:
        _f.write("(keine Signale)\n")

print(f"Trades-Textfile gespeichert: {OUT_TXT}")

# ==============================================================================
# 7) CHART
# ==============================================================================

fig, ax = plt.subplots(figsize=(17, 9))
idx = df["idx"].values
ax.plot(idx, df["high"], color="#bbb", lw=0.5)
ax.plot(idx, df["low"], color="#bbb", lw=0.5)

colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
for i_p, p in enumerate(phases):
    c = colors[i_p % len(colors)]
    ax.axvspan(p.i_start, p.i_ende, color=c, alpha=0.07)
    vz = p.vol_zone
    if vz is None:
        continue

    ax.hlines(vz.U_zone, p.i_start, p.i_ende, color="#1a7d1a", lw=2.4, alpha=0.95)
    ax.hlines(vz.L_zone, p.i_start, p.i_ende, color="#c00000", lw=2.4, alpha=0.95)
    ax.hlines(vz.POC, p.i_start, p.i_ende, color="#e07b00", lw=1.8, ls="-.")
    ax.text(p.i_start + 2, vz.U_zone + 0.10, f"OBEN(VAH) {vz.U_zone:.2f}",
            fontsize=8, color="#1a7d1a", fontweight="bold", va="bottom")
    ax.text(p.i_start + 2, vz.L_zone - 0.10, f"UNTEN(VAL) {vz.L_zone:.2f}",
            fontsize=8, color="#c00000", fontweight="bold", va="top")
    ax.text(p.i_start + 2, vz.POC + 0.10, f"POC {vz.POC:.2f}",
            fontsize=8, color="#e07b00", fontweight="bold", va="bottom")

    for j_pk, pk in enumerate(vz.peaks, 1):
        if j_pk == 1 and vz.n_mountains == 1:
            continue
        ax.hlines(pk.vah, p.i_start, p.i_ende, color="#2ca02c", lw=1.0, ls=":", alpha=0.75)
        ax.hlines(pk.val, p.i_start, p.i_ende, color="#d62728", lw=1.0, ls=":", alpha=0.75)
        ax.hlines(pk.poc, p.i_start, p.i_ende, color="#e07b00", lw=0.9, ls=":", alpha=0.75)

    if p.U_final is not None:
        ax.hlines(p.U_final, p.i_start, p.i_ende, color="k", lw=1.6, ls="--", alpha=0.55)
        ax.text(p.i_start + 2, p.U_final + 0.28, f"REAKTION OBEN {p.U_final:.2f}",
                fontsize=7.5, color="k", alpha=0.8, fontweight="bold", va="bottom")
    if p.L_final is not None:
        ax.hlines(p.L_final, p.i_start, p.i_ende, color="k", lw=1.6, ls="--", alpha=0.55)
        ax.text(p.i_start + 2, p.L_final - 0.28, f"REAKTION UNTEN {p.L_final:.2f}",
                fontsize=7.5, color="k", alpha=0.8, fontweight="bold", va="top")

for s in reclaim_signals:
    x = s.bar
    assert s.trade is not None
    if s.typ == "SHORT":
        y = float(df["high"].iloc[x])
        ax.scatter(x, y, marker="v", s=85, color="#c00000", zorder=6,
                   edgecolor="w", linewidths=0.5)
        txt = f"REC S {s.einstieg_preis:.2f} CRV {s.crv:.1f}"
    else:
        y = float(df["low"].iloc[x])
        ax.scatter(x, y, marker="^", s=85, color="#1a7d1a", zorder=6,
                   edgecolor="w", linewidths=0.5)
        txt = f"REC L {s.einstieg_preis:.2f} CRV {s.crv:.1f}"
    if s.trade.resultat == "GEWONNEN":
        txt += " WIN"
    elif s.trade.resultat == "VERLOREN":
        txt += " LOSS"
    ax.annotate(txt, (x, y),
                xytext=(x, y + (0.45 if s.typ == "SHORT" else -0.45)),
                fontsize=7.5, ha="center",
                color="#c00000" if s.typ == "SHORT" else "#1a7d1a",
                fontweight="bold")

for m in moves:
    ix = df["idx"][df["ts"] == m.von_ts].iloc[0] if (df["ts"] == m.von_ts).any() else np.nan
    iy = df["idx"][df["ts"] == m.bis_ts].iloc[0] if (df["ts"] == m.bis_ts).any() else np.nan
    if np.isnan(ix) or np.isnan(iy):
        continue
    ax.annotate("", xy=(iy, m.bis_pr), xytext=(ix, m.von_pr),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.2, connectionstyle="arc3,rad=0.0"))

step = max(8, len(df) // 16)
ticks = np.arange(0, len(df), step)
ax.set_xticks(ticks)
ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks], rotation=45, ha="right", fontsize=8)
ax.set_xlim(-1, len(df))
ax.set_title(f"SILVER M15 {START} - {ENDE} - VOLUME-PROFIL-ZONEN (VA_PCT {VA_PCT:.0f}%) + "
             f"SETUP B RECLAIM-SIGNALE (Pfeil = Fakeout, Ziel POC)")
ax.set_ylabel("USD")
ax.grid(alpha=0.3)

legend_elements = [
    Line2D([0], [0], color="#1a7d1a", lw=2.4, label="OBEN (VAH-Zone)"),
    Line2D([0], [0], color="#c00000", lw=2.4, label="UNTEN (VAL-Zone)"),
    Line2D([0], [0], color="#e07b00", lw=1.8, ls="-.", label="MITTE (POC)"),
    Line2D([0], [0], color="#2ca02c", lw=1.0, ls=":", label="Sub-Berg VAH"),
    Line2D([0], [0], color="#d62728", lw=1.0, ls=":", label="Sub-Berg VAL"),
    Line2D([0], [0], color="k", lw=1.6, ls="--", label="REAKTIONS-Extreme (Schnittmengen)"),
    Line2D([0], [0], marker="v", color="w", markerfacecolor="#c00000", ms=8,
           label="Setup B: Reclaim SHORT"),
    Line2D([0], [0], marker="^", color="w", markerfacecolor="#1a7d1a", ms=8,
           label="Setup B: Reclaim LONG"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=8, framealpha=0.9)

ax.text(0.28, 0.985, "\n".join(_stat_lines), transform=ax.transAxes,
        fontsize=8, va="top", ha="left", family="monospace",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#fdf6e3",
                  edgecolor="gray", alpha=0.95))

fig.tight_layout()
fig.savefig(OUT_PNG, dpi=130)
print(f"\nChart gespeichert: {OUT_PNG}")
# ==============================================================================
# 7c) BENCHMARK-SET USER-IDEALLINIEN AUG (rein lesend, KEIN Signal-Einfluss)
#     Aktivierung NUR via CLI-Flag:  python ... --benchmark
#     Default: aus -> Baseline-Zahlen/Phasen/Chart exakt unveraendert.
#     Massstab: 8 manuelle Makro-Range-Linien (User 02.09.). Report misst,
#     wie nah U_final/L_final der Phasen diesen Idealen kommen (Delta-Klasse).
# ==============================================================================

@dataclass(frozen=True, slots=True)
class UserMacroLine:
    """Unveraenderliche Benchmark-Linie (finale Range-Grenze, post-hoc)."""
    side: Literal["UPPER", "LOWER"]
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    price: float
    name: str


USER_LINES_AUG: tuple[UserMacroLine, ...] = (
    UserMacroLine("UPPER", pd.Timestamp("2026-08-11 03:45"), pd.Timestamp("2026-08-18 03:00"), 66.45, "R1_U"),
    UserMacroLine("LOWER", pd.Timestamp("2026-08-11 08:30"), pd.Timestamp("2026-08-13 21:15"), 62.24, "R1_L"),
    UserMacroLine("UPPER", pd.Timestamp("2026-08-20 02:15"), pd.Timestamp("2026-08-20 07:00"), 67.26, "R2_U"),
    UserMacroLine("LOWER", pd.Timestamp("2026-08-20 14:00"), pd.Timestamp("2026-08-20 14:15"), 65.66, "R2_L"),
    UserMacroLine("UPPER", pd.Timestamp("2026-08-21 10:45"), pd.Timestamp("2026-08-25 02:00"), 69.90, "R3_U"),
    UserMacroLine("LOWER", pd.Timestamp("2026-08-24 03:30"), pd.Timestamp("2026-08-24 20:00"), 68.40, "R3_L"),
    UserMacroLine("UPPER", pd.Timestamp("2026-08-26 04:30"), pd.Timestamp("2026-08-27 18:45"), 69.58, "R4_U"),
    UserMacroLine("LOWER", pd.Timestamp("2026-08-25 04:30"), pd.Timestamp("2026-08-26 15:45"), 67.65, "R4_L"),
)

BENCHMARK_TOL: float = 0.15      # Match-Schwelle (konsistent DENSITY_BAND/TOL_TOUCH)
BENCHMARK_TOL_EXACT: float = 0.06  # "centgenau"-Stufe fuer den Report

# Referenzlinien-Farben (User-Schema, test/tmp_reclaim_user_ranges.py):
# GELB  = UPPER (obere Range-Grenze), OCKER = LOWER (untere Range-Grenze).
REF_COL_UPPER: str = "#EAB308"   # gelb
REF_COL_LOWER: str = "#B8860B"   # ocker

# Mindestbreite (in Bars) fuer Referenzlinien-Segmente im Chart. Sehr kurze
# User-Fenster (z. B. R2_L 20.8 14:00-14:15 = 2 M15-Bars) wuerden sonst als
# unsichtbarer Punkt verschwinden - das Segment wird zentriert auf diese
# Breite verbreitert (User-Vorgabe 03.09.: "Mindestbreite +/-3 Bars").
REF_LINE_MIN_BARS: int = 7


def benchmark_report(
    phases: List["PhaseData"],
    df: pd.DataFrame,
    lines: tuple[UserMacroLine, ...] = USER_LINES_AUG,
    tol: float = BENCHMARK_TOL,
) -> str:
    """Rein lesender Abgleich der Phasen-Niveaus (U_final/L_final) gegen die
    User-Ideallinien. 0.0% Einfluss auf Phasenbildung/Signale/Exits/SL.

    Treffer-Klassen je Linie:
      VOLL       = Baseline-Niveau <= tol UND zeitliche Ueberlappung der
                   tragenden Phase mit dem User-Intervall.
      PREIS-ONLY = Niveau <= tol, aber beste Preis-Phase ueberlappt zeitlich
                   nicht (Linie existiert im Datensatz, nur ausserhalb).
      KEIN       = kein Niveau <= tol (zeigt naechste Distanz).

    Returns:
        Mehrzeiliger Report (Konsolen-/Textausgabe).
    """
    if len(df) == 0:
        return "benchmark: leere Daten"
    ts_lo = df["ts"].min()
    ts_hi = df["ts"].max()
    out: List[str] = [
        "\n" + "=" * 100,
        "BENCHMARK USER-IDEALLINIEN AUG (rein lesend, kein Signal-Einfluss)",
        "=" * 100,
    ]
    n_voll = n_preis = n_kein = 0
    for ul in lines:
        # zeitlich im Datensatz?
        in_window = ul.end_ts >= ts_lo and ul.start_ts <= ts_hi
        best: list = []   # (distanz, phase, niveau)
        for p in phases:
            v = p.U_final if ul.side == "UPPER" else p.L_final
            if v is None:
                continue
            best.append((abs(v - ul.price), p, float(v)))
        if not best:
            out.append(f"{ul.name:5s} {ul.side:5s} {ul.price:6.2f}  "
                       f"[{ul.start_ts:%d.%m %H:%M}-{ul.end_ts:%d.%m %H:%M}]  "
                       f"KEIN Niveau in Phasen")
            n_kein += 1
            continue
        best.sort(key=lambda x: x[0])
        d0, p0, v0 = best[0]
        # zeitliche Ueberlappung der besten Phase
        ueberlapp = p0.start <= ul.end_ts and p0.ende >= ul.start_ts
        if d0 <= tol:
            if ueberlapp and in_window:
                klasse = "VOLL"
                n_voll += 1
            else:
                klasse = "PREIS-ONLY"
                n_preis += 1
        else:
            klasse = "KEIN"
            n_kein += 1
        d_txt = f"d={d0:.3f}"
        if d0 <= BENCHMARK_TOL_EXACT:
            d_txt += " (centgenau)"
        elif d0 <= tol:
            d_txt += " (Match)"
        z_klasse = "VOLL" if klasse == "VOLL" else (
            "PREIS-ONLY" if klasse == "PREIS-ONLY" else "KEIN")
        out.append(
            f"{ul.name:5s} {ul.side:5s} {ul.price:6.2f}  "
            f"[{ul.start_ts:%d.%m %H:%M}-{ul.end_ts:%d.%m %H:%M}]  "
            f"-> Phase {p0.start:%d.%m}-{p0.ende:%d.%m} {ul.side[:1]} {v0:.3f}  "
            f"{d_txt}  [{z_klasse}]"
        )
    out.append("=" * 100)
    out.append(f"RESULTAT: {n_voll} VOLL | {n_preis} PREIS-ONLY | {n_kein} KEIN "
               f"(von {len(lines)} Linien, Tol {tol:.2f})")
    out.append("=" * 100)
    return "\n".join(out)


if "--benchmark" in sys.argv:
    print(benchmark_report(phases, df))

# ==============================================================================
# 7d) MACRO-PERSISTENZ-SPIEGEL (rein lesend, KEIN Signal-/Exit-/Trade-Einfluss)
#     Aktivierung NUR via CLI-Flag:  python ... --macro
#     Default: aus -> Baseline-Zahlen/Phasen/Chart exakt unveraendert.
#     Passiver Beobachter (Design v0.2, Freigabe 02.09.): replayt die
#     Phasen-Events (Touches + R4-Boundary) durch MacroLineState und zeigt
#     je Phase den eingefrorenen Anker-Zustand VOR den Touches (global +
#     distanzbegrenzt ueber Faktoren der kausalen Range-Referenz). Kein
#     Eingriff in find_reclaim_signals/Exits/SL - nur Konsolen-Report.
# ==============================================================================
if "--macro" in sys.argv:
    try:
        from macro_persistence import macro_report
    except ImportError:
        print("==> macro_persistence.py nicht importierbar (erwartet in scripts/)")
    else:
        # Kausale Range-Referenz wie vol_ref (200er-Fenster, shift 1):
        # Faktor-Kandidaten 4x/8x/12x dienen NUR dem Report - keine
        # fest verdrahtete Schwelle (Kalibrierung erst im Signal-Loop).
        _macro_dist_ref = (df["high"] - df["low"]).rolling(
            200, min_periods=20).mean().shift(1)
        print(macro_report(phases, df, level_schnittmenge, _macro_dist_ref))

# ==============================================================================
# 7e) STANDARD-ARTEFAKTE (verbindliche Standard-Ausgaben JEDES Durchlaufs)
#     Default (ohne Sonderflags) werden bei jedem Lauf synchron erzeugt:
#       1. test/stats_trades_<FENSTER>.txt           Statistik- & Trade-Log
#       2. test/phasen_volumen_profil_<FENSTER>.png  Standard-Chart
#     Der .txt-Pfad ist optional via --stats-txt=... ueberschreibbar.
#     Zusaetzlich bleiben die Legacy-Ausgaben des Hauptskripts aktiv
#     (scripts/phasen_volumen_profil.png/.txt, Abschnitte 6a/7).
#
#     Inhalt des Standard-Charts (rein lesend, KEIN Eingriff in Signal-,
#     Kanten- oder Orderlogik - Rendering manipuliert keinen Zustand):
#       * Phasen-Kanten Tier 1 (U_zone/L_zone je Phase) und Tier 2
#         (distanzbegrenzte Makro-Anker als gestrichelte Linien + Ring)
#       * Reclaim-Signale: Dreiecke, gefuellt = in_bar / offen = next_bar
#       * AUG-Referenz: exakte historische User-Ideallinien (R1_U..R4_L)
#         als Overlay fuer das August-Fenster (benchmark_lines)
#       * im --macro-live-Lauf zusaetzlich Baseline-Kontroll-Kreise (o)
#     Alle Kennzahlen werden AUSSCHLIESSLICH aus den bereits berechneten
#     Trade-Ergebnissen abgeleitet (s.trade.resultat / s.trade.r_mult) -
#     keine abweichenden Formeln, keine neuen Heuristiken.
# ==============================================================================

@dataclass(frozen=True, slots=True)
class SignalMarkerStil:
    """Rein darstellendes Marker-Styling eines Reclaim-Signals.

    Enthaelt KEINE Logik und keinen Zustands-Zugriff - dient ausschliesslich
    der Chart-Darstellung (Rendering manipuliert den Berechnungszustand nie).
    """
    marker: str          # "v" = SHORT (unten) / "^" = LONG (oben)
    farbe: str           # Richtungsfarbe (rot = SHORT / gruen = LONG)
    gefuellt: bool       # True = in_bar (gefuellt), False = next_bar (offen)
    groesse: float       # Punktgroesse (matplotlib s)


def signal_marker_stil(s: ReclaimSignal) -> SignalMarkerStil:
    """Marker-Stil eines Reclaim-Signals (Richtung + Entry-Typ).

    Args:
        s: Reclaim-Signal (rein lesend).

    Returns:
        SignalMarkerStil mit Marker-Form, Richtungsfarbe, Fuell-Status
        (in_bar gefuellt / next_bar offen) und Groesse.
    """
    if s.typ == "SHORT":
        return SignalMarkerStil(marker="v", farbe="#c00000",
                                gefuellt=s.reclaim == "in_bar", groesse=60.0)
    return SignalMarkerStil(marker="^", farbe="#1a7d1a",
                            gefuellt=s.reclaim == "in_bar", groesse=60.0)


def _stats_kennzahlen(signals: List[ReclaimSignal]) -> Dict[str, object]:
    """Aggregiert die Statistik-Kennzahlen eines Signal-/Trade-Satzes.

    Ableitung ausschliesslich aus den bestehenden Trade-Ergebnissen:
    resultat-Klassen GEWONNEN/VERLOREN/NEUTRAL + r_mult der vorhandenen
    Aufloesung (keine abweichenden R-Formeln). Win-Rate = Gewinntrades /
    Gesamttrades * 100 (Spezifikation Schritt 1).

    Args:
        signals: aufgeloeste Reclaim-Signale eines Modus (s.trade != None).

    Returns:
        Dict mit den Kennzahlen (n, long, short, win, loss, neutral,
        winrate_pct, sum_r, avg_win, avg_loss, brutto_gewinn,
        brutto_verlust, profit_faktor). profit_faktor = None bedeutet
        "kein Verlust-Trade" (unendlich).
    """
    n = len(signals)
    n_long = sum(1 for s in signals if s.typ == "LONG")
    n_short = n - n_long
    wins: List[float] = []
    losses: List[float] = []
    sum_r = 0.0
    for s in signals:
        assert s.trade is not None
        sum_r += s.trade.r_mult
        if s.trade.resultat == "GEWONNEN":
            wins.append(s.trade.r_mult)
        elif s.trade.resultat == "VERLOREN":
            losses.append(s.trade.r_mult)
    n_win = len(wins)
    n_loss = len(losses)
    n_neutral = n - n_win - n_loss
    winrate_pct = 100.0 * n_win / n if n else 0.0
    avg_win = sum(wins) / n_win if n_win else 0.0
    avg_loss = sum(losses) / n_loss if n_loss else 0.0
    brutto_gewinn = sum(wins)
    brutto_verlust = abs(sum(losses))
    if brutto_verlust > 0.0:
        profit_faktor: Optional[float] = brutto_gewinn / brutto_verlust
    elif brutto_gewinn > 0.0:
        profit_faktor = None          # unendlich (kein Verlust-Trade)
    else:
        profit_faktor = 0.0
    return {
        "n": n, "long": n_long, "short": n_short,
        "win": n_win, "loss": n_loss, "neutral": n_neutral,
        "winrate_pct": winrate_pct, "sum_r": sum_r,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "brutto_gewinn": brutto_gewinn, "brutto_verlust": brutto_verlust,
        "profit_faktor": profit_faktor,
    }


def _trade_log_rows(
    signals: List[ReclaimSignal],
) -> List[Tuple[int, int, int, int, str, str, float, int, float, float]]:
    """Baut die Trade-Log-Zeilen eines Modus (Handelsreihenfolge = ts).

    Zeilen-Tupel: (Trade_Nr, Phase_ID, Bar_Signal, Bar_Entry, Type,
    Direction, Entry_Price, Tier, R_Result, Cumulative_R). Cumulative_R
    ist die fortlaufende R-Summe ueber die sortierte Handelsreihenfolge.
    Tier = s.edge_decision.tier; Baseline-Signale ohne Kanten-Entscheidung
    sind per Konstruktion Tier 1 (lokale Volume-Kante).
    """
    rows: List[Tuple[int, int, int, int, str, str, float, int, float, float]] = []
    cum = 0.0
    for nr, s in enumerate(sorted(signals, key=lambda x: (x.ts, x.bar)), 1):
        assert s.trade is not None
        tier = s.edge_decision.tier if s.edge_decision is not None else 1
        r = s.trade.r_mult
        cum += r
        rows.append((nr, s.phase, s.bar, s.einstieg_bar, s.reclaim,
                     s.typ, s.einstieg_preis, tier, r, cum))
    return rows


def export_stats_trades(
    ziel_datei: Path,
    fenster: str,
    start: str,
    ende: str,
    baseline_signals: List[ReclaimSignal],
    macro_signals: Optional[List[ReclaimSignal]] = None,
    referenz_lines: Optional[Sequence[UserMacroLine]] = None,
) -> str:
    """Schreibt den vollstaendigen Statistik- & Trade-Report eines Fensters.

    Datei-Aufbau je Abschnitt (Modus):
      Kopfbereich mit Fenster/Modus + Kennzahlen (Signale/Trades gesamt,
      Long/Short, Win-Rate, Summe R, Avg Win, Avg Loss, Profit-Faktor),
      danach der tabellarische Trade-Log (alle ausgefuhrten Trades mit
      kumulierter R-Spalte).

    Args:
        ziel_datei: Ausgabe-Pfad der .txt-Datei (z. B. test/stats_trades_AUG.txt).
        fenster: Fenster-Label (AUG, S1, S2) fuer den Kopfbereich.
        start: Start-Datum des Fensters (Anzeige).
        ende: End-Datum des Fensters (Anzeige).
        baseline_signals: Signale/Trades des Baseline-Laufs.
        macro_signals: optional Signale/Trades des --macro-live-Laufs
            (v0.4.x); None -> nur Baseline-Abschnitt.
        referenz_lines: optional Referenzlinien (USER_LINES_AUG) - werden
            als fester Textblock (GELB = UPPER / OCKER = LOWER) in den
            Report geschrieben; None -> kein Block (S1/S2 ohne Set).

    Returns:
        Kompakte Konsolen-Zusammenfassung (mehrzeilig).
    """
    _modi: List[Tuple[str, str, List[ReclaimSignal]]] = [
        ("Baseline", "Baseline (Standardlauf ohne Makro-Flag)", baseline_signals),
    ]
    if macro_signals is not None:
        _modi.append((
            "Macro-Live",
            "--macro-live (Stand v0.4.x: OVERRUN_TOL=0.075, D2-asym, A3/B3)",
            macro_signals,
        ))

    _w_nr, _w_ph, _w_sig, _w_ent = 8, 8, 10, 9
    _w_typ, _w_dir, _w_pr, _w_tier = 10, 9, 11, 6
    _w_r, _w_cum = 8, 12
    _header = (
        f"{'Trade_Nr':>{_w_nr}} | {'Phase_ID':>{_w_ph}} | "
        f"{'Bar_Signal':>{_w_sig}} | {'Bar_Entry':>{_w_ent}} | "
        f"{'Type':>{_w_typ}} | {'Direction':>{_w_dir}} | "
        f"{'Entry_Price':>{_w_pr}} | {'Tier':>{_w_tier}} | "
        f"{'R_Result':>{_w_r}} | {'Cumulative_R':>{_w_cum}}"
    )

    def _abschnitt(modus_txt: str,
                   sigs: List[ReclaimSignal]) -> List[str]:
        """Ein Modus-Abschnitt: Kopfbereich (Kennzahlen) + Trade-Log."""
        k = _stats_kennzahlen(signals=sigs)
        pf_txt: str
        if k["profit_faktor"] is None:
            pf_txt = "unendl. (kein Verlust-Trade)"
        else:
            pf_txt = f"{float(k['profit_faktor']):.2f}"
        out = [
            "-" * 118,
            f"Fenster: {fenster}  ({start} - {ende})  |  Modus: {modus_txt}",
            "-" * 118,
            f"Signale/Trades gesamt : {k['n']}",
            f"Long / Short          : {k['long']} / {k['short']}",
            f"Win-Rate              : {float(k['winrate_pct']):.1f}%  "
            f"({k['win']} Gewinn / {k['loss']} Verlust / {k['neutral']} Neutral)",
            f"Summe R (kumuliert)   : {float(k['sum_r']):+.2f}",
            f"Avg Win (R)           : {float(k['avg_win']):+.2f}  "
            f"(ueber {k['win']} Gewinntrades)",
            f"Avg Loss (R)          : {float(k['avg_loss']):+.2f}  "
            f"(ueber {k['loss']} Verlusttrades)",
            f"Profit-Faktor         : {pf_txt}  "
            f"(Brutto-Gewinn-R {float(k['brutto_gewinn']):+.2f} / "
            f"Brutto-Verlust-R {-float(k['brutto_verlust']):+.2f})",
            "",
            f"TRADE-LOG ({k['n']} Trades; R_Result und Cumulative_R in R; "
            f"Cumulative_R fortlaufend in Handelsreihenfolge)",
        ]
        if sigs:
            out.append(_header)
            for (nr, ph, sig_bar, ent_bar, typ, direc, preis,
                 tier, r, cum) in _trade_log_rows(sigs):
                out.append(
                    f"{nr:>{_w_nr}d} | {ph:>{_w_ph}d} | {sig_bar:>{_w_sig}d} | "
                    f"{ent_bar:>{_w_ent}d} | {typ:>{_w_typ}s} | "
                    f"{direc:>{_w_dir}s} | {preis:>{_w_pr}.3f} | "
                    f"{('Tier ' + str(tier)):>{_w_tier}s} | "
                    f"{r:+{_w_r}.2f} | {cum:+{_w_cum}.2f}"
                )
        else:
            out.append("(keine Signale)")
        return out

    zeilen: List[str] = [
        "=" * 118,
        f"STATS & TRADE-REPORT | Fenster: {fenster}  ({start} - {ende})",
        "=" * 118,
        "Vergleich: Baseline (Standardlauf ohne Makro-Flag) vs. "
        "--macro-live (v0.4.x).",
    ]
    if referenz_lines:
        zeilen.append("")
        zeilen.append("-" * 118)
        zeilen.append("REFERENZLINIEN AUG (User-Ideallinien - finale Range-"
                      "Struktur, post-hoc)")
        zeilen.append("GELB  (#EAB308) = UPPER (obere Range-Grenze)")
        zeilen.append("OCKER (#B8860B) = LOWER (untere Range-Grenze)")
        zeilen.append(f"{'Name':<5s} {'Farbe':<5s} {'Preis':>7s}  "
                      f"Gueltig von            bis")
        for _ul in referenz_lines:
            _col = "GELB" if _ul.side == "UPPER" else "OCKER"
            zeilen.append(
                f"{_ul.name:<5s} {_col:<5s} {_ul.price:>7.2f}  "
                f"{_ul.start_ts:%Y-%m-%d %H:%M}  -  {_ul.end_ts:%Y-%m-%d %H:%M}"
            )
        zeilen.append("-" * 118)
    for _kurz, _txt, _sigs in _modi:
        zeilen.extend(_abschnitt(_txt, _sigs))
        zeilen.append("")
    zeilen.append("=" * 118)

    with open(ziel_datei, "w", encoding="utf-8") as _f:
        _f.write("\n".join(zeilen) + "\n")

    # Kompakte Konsolen-Zusammenfassung
    _sum: List[str] = [f"[STATS-EXPORT] Datei: {ziel_datei}"]
    for _kurz, _txt, _sigs in _modi:
        _k = _stats_kennzahlen(_sigs)
        _pf = ("unendl." if _k["profit_faktor"] is None
               else f"{float(_k['profit_faktor']):.2f}")
        _sum.append(
            f"[STATS-EXPORT] {fenster} | {_kurz:10s} | "
            f"n={_k['n']:3d} | Long {_k['long']:3d} / Short {_k['short']:3d} | "
            f"WR {float(_k['winrate_pct']):5.1f}% | SumR {float(_k['sum_r']):+8.2f}R | "
            f"AvgW {float(_k['avg_win']):+5.2f}R | AvgL {float(_k['avg_loss']):+5.2f}R | "
            f"PF {_pf}"
        )
    return "\n".join(_sum)


def render_standard_chart(
    ziel_png: Path,
    fenster: str,
    start: str,
    ende: str,
    df: pd.DataFrame,
    phases: List[PhaseData],
    moves: List[MoveData],
    signals: List[ReclaimSignal],
    baseline_signals: Optional[List[ReclaimSignal]] = None,
    benchmark_lines: Optional[Sequence[UserMacroLine]] = None,
    stat_lines: Optional[List[str]] = None,
    modus_txt: str = "",
) -> str:
    """Erzeugt den Standard-Chart zur visuellen Kontrolle (rein lesend).

    Rendering-Trennung: Die Funktion liest ausschliesslich aus df/phases/
    moves/signals - sie manipuliert KEINEN Berechnungszustand (keine Mutation
    von Phasen-, Signal- oder Trade-Objekten).

    Layout wie Hauptskript-Chart (Abschnitt 7): High/Low-Balken, Phasen-
    Hintergrund (axvspan), Volume-Zonen (Tier-1-Kanten U_zone/L_zone/POC +
    Sub-Berge), Reaktions-Extreme, Moves-Pfeile. Zusaetzlich:
      * Tier-2-Kanten: distanzbegrenzte Makro-Anker (edge_decision.tier==2)
        als lila gestrichelte Linien ueber ihre Nutzungs-Spanne.
      * Reclaim-Signale (signals): Dreiecke (SHORT unten / LONG oben),
        gefuellt = in_bar, offen = next_bar; Tier-2-Signale mit Ring.
      * baseline_signals (optional, --macro-live): offene Kreise als
        Baseline-Kontrolllage (Differenz-Sicht: nur Kreis = entfallen,
        nur Dreieck = neu).
      * benchmark_lines (optional, AUG): exakte historische Referenz-
        Musterlinien (USER_LINES_AUG: R1_U..R4_L) als Overlay -
        GELB #EAB308 = UPPER / OCKER #B8860B = LOWER (User-Schema).
      * stat_lines (optional): Statistik-Box im Chart.

    Args:
        ziel_png: Ausgabe-Pfad der PNG-Datei
            (Default test/phasen_volumen_profil_<FENSTER>.png).
        fenster: Fenster-Label (AUG/S1/S2) fuer den Titel.
        start: Start-Datum des Fensters (Titel).
        ende: End-Datum des Fensters (Titel).
        df: OHLCV-DataFrame der Baseline (Spalten idx/ts/high/low/...).
        phases: Baseline-Phasen (Volume-Zonen fuer die Darstellung).
        moves: Phasenwechsel (Pfeile wie Hauptskript).
        signals: aktive Modus-Signale des Laufs (Dreiecke; Stil nach
            signal_marker_stil + Tier-2-Ring).
        baseline_signals: optional Baseline-Kontroll-Signale (offene Kreise),
            z. B. _baseline_sigs im --macro-live-Lauf.
        benchmark_lines: optional User-Ideallinien fuer das AUG-Overlay
            (USER_LINES_AUG); None fuer Nicht-August-Fenster.
        stat_lines: optional Statistik-Zeilen (Box oben links).
        modus_txt: Modus-Kennung fuer den Titel (z. B. "Baseline").

    Returns:
        Konsolen-Hinweis (Datei + Signal-Zaehlungen).
    """
    fig, ax = plt.subplots(figsize=(17, 9))
    idx = df["idx"].values
    ax.plot(idx, df["high"], color="#bbb", lw=0.5)
    ax.plot(idx, df["low"], color="#bbb", lw=0.5)

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for i_p, p in enumerate(phases):
        c = colors[i_p % len(colors)]
        ax.axvspan(p.i_start, p.i_ende, color=c, alpha=0.07)
        vz = p.vol_zone
        if vz is None:
            continue

        ax.hlines(vz.U_zone, p.i_start, p.i_ende, color="#1a7d1a", lw=2.4, alpha=0.95)
        ax.hlines(vz.L_zone, p.i_start, p.i_ende, color="#c00000", lw=2.4, alpha=0.95)
        ax.hlines(vz.POC, p.i_start, p.i_ende, color="#e07b00", lw=1.8, ls="-.")
        ax.text(p.i_start + 2, vz.U_zone + 0.10, f"OBEN(VAH) {vz.U_zone:.2f}",
                fontsize=8, color="#1a7d1a", fontweight="bold", va="bottom")
        ax.text(p.i_start + 2, vz.L_zone - 0.10, f"UNTEN(VAL) {vz.L_zone:.2f}",
                fontsize=8, color="#c00000", fontweight="bold", va="top")
        ax.text(p.i_start + 2, vz.POC + 0.10, f"POC {vz.POC:.2f}",
                fontsize=8, color="#e07b00", fontweight="bold", va="bottom")

        for j_pk, pk in enumerate(vz.peaks, 1):
            if j_pk == 1 and vz.n_mountains == 1:
                continue
            ax.hlines(pk.vah, p.i_start, p.i_ende, color="#2ca02c", lw=1.0, ls=":", alpha=0.75)
            ax.hlines(pk.val, p.i_start, p.i_ende, color="#d62728", lw=1.0, ls=":", alpha=0.75)
            ax.hlines(pk.poc, p.i_start, p.i_ende, color="#e07b00", lw=0.9, ls=":", alpha=0.75)

        if p.U_final is not None:
            ax.hlines(p.U_final, p.i_start, p.i_ende, color="k", lw=1.6, ls="--", alpha=0.55)
            ax.text(p.i_start + 2, p.U_final + 0.28, f"REAKTION OBEN {p.U_final:.2f}",
                    fontsize=7.5, color="k", alpha=0.8, fontweight="bold", va="bottom")
        if p.L_final is not None:
            ax.hlines(p.L_final, p.i_start, p.i_ende, color="k", lw=1.6, ls="--", alpha=0.55)
            ax.text(p.i_start + 2, p.L_final - 0.28, f"REAKTION UNTEN {p.L_final:.2f}",
                    fontsize=7.5, color="k", alpha=0.8, fontweight="bold", va="top")

    for m in moves:
        ix = df["idx"][df["ts"] == m.von_ts].iloc[0] if (df["ts"] == m.von_ts).any() else np.nan
        iy = df["idx"][df["ts"] == m.bis_ts].iloc[0] if (df["ts"] == m.bis_ts).any() else np.nan
        if np.isnan(ix) or np.isnan(iy):
            continue
        ax.annotate("", xy=(iy, m.bis_pr), xytext=(ix, m.von_pr),
                    arrowprops=dict(arrowstyle="->", color="k", lw=2.2,
                                    connectionstyle="arc3,rad=0.0"))

    # Tier-2-Kanten: distanzbegrenzte Makro-Anker als Linien-Segmente
    _t2_spans: Dict[float, List[int]] = {}
    for s in signals:
        _ed = s.edge_decision
        if _ed is not None and _ed.tier == 2:
            _t2_spans.setdefault(float(_ed.edge_price), []).append(int(s.bar))
    for _price, _bars in _t2_spans.items():
        _x0, _x1 = min(_bars), max(_bars)
        ax.hlines(_price, _x0, _x1, color="#7b1fa2", lw=1.2, ls="--",
                  alpha=0.9, zorder=4)
        ax.text(_x0, _price + 0.05, f"T2 {_price:.3f}", fontsize=7,
                color="#7b1fa2", fontweight="bold", va="bottom")

    # Baseline-Kontrolllage: offene Kreise (zuerst -> Dreiecke liegen darueber)
    if baseline_signals is not None:
        for s in baseline_signals:
            x = s.bar
            if s.typ == "SHORT":
                y = float(df["high"].iloc[x])
                col = "#c00000"
            else:
                y = float(df["low"].iloc[x])
                col = "#1a7d1a"
            ax.scatter(x, y, marker="o", s=26, facecolors="none",
                       edgecolors=col, linewidths=0.9, zorder=5)

    # Aktive Modus-Signale: Dreiecke (SHORT unten / LONG oben), gefuellt =
    # in_bar / offen = next_bar; Tier-2-Signale zusaetzlich mit Ring.
    for s in signals:
        x = int(s.bar)
        if s.typ == "SHORT":
            y = float(df["high"].iloc[x])
        else:
            y = float(df["low"].iloc[x])
        stil = signal_marker_stil(s)
        if stil.gefuellt:
            ax.scatter(x, y, marker=stil.marker, s=stil.groesse,
                       color=stil.farbe, zorder=6, edgecolor="w",
                       linewidths=0.4)
        else:
            ax.scatter(x, y, marker=stil.marker, s=stil.groesse,
                       facecolors="none", edgecolors=stil.farbe,
                       linewidths=1.0, zorder=6)
        if s.edge_decision is not None and s.edge_decision.tier == 2:
            ax.scatter(x, y, marker="o", s=stil.groesse + 70,
                       facecolors="none", edgecolors="#7b1fa2",
                       linewidths=1.1, zorder=5)

    # AUG-Referenz-Musterlinien: exakte User-Ideallinien (R1_U..R4_L)
    ts_arr = df["ts"].to_numpy()
    if benchmark_lines is not None:
        for ul in benchmark_lines:
            if ul.end_ts < df["ts"].min() or ul.start_ts > df["ts"].max():
                continue
            x0 = int(np.searchsorted(ts_arr, np.datetime64(ul.start_ts),
                                     side="left"))
            x1 = int(np.searchsorted(ts_arr, np.datetime64(ul.end_ts),
                                     side="right")) - 1
            x0 = max(0, min(x0, len(df) - 1))
            x1 = max(0, min(x1, len(df) - 1))
            if x1 < x0:
                continue
            # Mindestbreite: Segmente < REF_LINE_MIN_BARS (z. B. R2_L mit nur
            # 2 Bars) wuerden als Punkt verschwinden -> zentriert verbreitern.
            if x1 - x0 + 1 < REF_LINE_MIN_BARS:
                _cx = (x0 + x1) / 2.0
                _half = (REF_LINE_MIN_BARS - 1) / 2.0
                x0 = int(round(_cx - _half))
                x1 = int(round(_cx + _half))
                x0 = max(0, min(x0, len(df) - 1))
                x1 = max(0, min(x1, len(df) - 1))
            if x1 < x0:
                continue
            ax.hlines(ul.price, x0, x1,
                      color=REF_COL_UPPER if ul.side == "UPPER"
                      else REF_COL_LOWER,
                      lw=2.0, alpha=0.95, zorder=3)
            ax.text(x0, ul.price + 0.07, ul.name, fontsize=7.5,
                    color=REF_COL_UPPER if ul.side == "UPPER"
                    else REF_COL_LOWER,
                    fontweight="bold", va="bottom")

    step = max(8, len(df) // 16)
    ticks = np.arange(0, len(df), step)
    ax.set_xticks(ticks)
    ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M")
                        for t in ticks], rotation=45, ha="right", fontsize=8)
    ax.set_xlim(-1, len(df))
    _modus_ttl = f" | Modus {modus_txt}" if modus_txt else ""
    _aug_ttl = " | AUG-Referenz-Overlay" if benchmark_lines is not None else ""
    ax.set_title(f"SILVER M15 {start} - {ende} | Fenster {fenster}"
                 f"{_modus_ttl} | STANDARD-CHART: Tier-1/2-Kanten, "
                 f"Reclaims in_bar/next_bar{_aug_ttl}")
    ax.set_ylabel("USD")
    ax.grid(alpha=0.3)

    legend_elements: List[Line2D] = [
        Line2D([0], [0], color="#1a7d1a", lw=2.4, label="Tier-1 Kante OBEN (VAH)"),
        Line2D([0], [0], color="#c00000", lw=2.4, label="Tier-1 Kante UNTEN (VAL)"),
        Line2D([0], [0], color="#e07b00", lw=1.8, ls="-.", label="MITTE (POC)"),
        Line2D([0], [0], color="#2ca02c", lw=1.0, ls=":", label="Sub-Berg VAH"),
        Line2D([0], [0], color="#d62728", lw=1.0, ls=":", label="Sub-Berg VAL"),
        Line2D([0], [0], color="k", lw=1.6, ls="--", label="REAKTIONS-Extreme"),
        Line2D([0], [0], marker="v", color="w", mfc="#c00000", ms=8,
               label="Reclaim SHORT in_bar"),
        Line2D([0], [0], marker="v", color="w", mfc="none", mec="#c00000", ms=8,
               label="Reclaim SHORT next_bar"),
        Line2D([0], [0], marker="^", color="w", mfc="#1a7d1a", ms=8,
               label="Reclaim LONG in_bar"),
        Line2D([0], [0], marker="^", color="w", mfc="none", mec="#1a7d1a", ms=8,
               label="Reclaim LONG next_bar"),
    ]
    if baseline_signals is not None:
        legend_elements.append(
            Line2D([0], [0], marker="o", color="w", mfc="none", mec="#c00000",
                   ms=7, label="Baseline SHORT (o)"))
        legend_elements.append(
            Line2D([0], [0], marker="o", color="w", mfc="none", mec="#1a7d1a",
                   ms=7, label="Baseline LONG (o)"))
    if _t2_spans:
        legend_elements.append(
            Line2D([0], [0], color="#7b1fa2", lw=1.2, ls="--",
                   label="Tier-2 Makro-Kante"))
        legend_elements.append(
            Line2D([0], [0], marker="o", color="w", mfc="none", mec="#7b1fa2",
                   ms=10, label="Tier-2 Signal (Ring)"))
    if benchmark_lines is not None:
        if any(ul.side == "UPPER" for ul in benchmark_lines):
            legend_elements.append(
                Line2D([0], [0], color=REF_COL_UPPER, lw=2.0,
                       label="AUG-Referenzlinie UPPER (gelb)"))
        if any(ul.side == "LOWER" for ul in benchmark_lines):
            legend_elements.append(
                Line2D([0], [0], color=REF_COL_LOWER, lw=2.0,
                       label="AUG-Referenzlinie LOWER (ocker)"))
    ax.legend(handles=legend_elements, loc="upper left", fontsize=7.5,
              framealpha=0.95)

    if stat_lines:
        ax.text(0.30, 0.985, "\n".join(stat_lines), transform=ax.transAxes,
                fontsize=7.5, va="top", ha="left", family="monospace",
                bbox=dict(boxstyle="round,pad=0.45", facecolor="#fdf6e3",
                          edgecolor="gray", alpha=0.95))

    fig.tight_layout()
    fig.savefig(ziel_png, dpi=130)
    plt.close(fig)

    n_t2 = len(_t2_spans)
    n_bench = len(benchmark_lines) if benchmark_lines is not None else 0
    n_b = len(baseline_signals) if baseline_signals is not None else 0
    return (f"[STANDARD-CHART] Datei: {ziel_png} | Fenster {fenster} | "
            f"Signale {len(signals)} (Dreiecke) | Baseline-Overlay {n_b} (o) "
            f"| Tier-2-Kanten {n_t2} | AUG-Referenzlinien {n_bench}")


# ==============================================================================
# 7f) DEFAULT-ERZEUGUNG DER STANDARD-ARTEFAKTE (jeder Lauf, ohne Sonderflags)
#     .txt-Pfad optional via --stats-txt=... ueberschreibbar; der Standard-
#     Chart heisst immer test/phasen_volumen_profil_<FENSTER>.png.
# ==============================================================================

def _label_aus_stem(stem: str) -> str:
    """Extrahiert das Fenster-Label aus einem Datei-Stem.

    Args:
        stem: Dateiname ohne Endung (z. B. stats_trades_AUG).

    Returns:
        Fenster-Label (z. B. AUG); unbekannte Stems bleiben unveraendert.
    """
    for _prefix in ("stats_trades_", "stats_", "phasen_volumen_profil_"):
        if stem.startswith(_prefix):
            return stem[len(_prefix):]
    return stem


_stats_txt_args = [a for a in sys.argv if a.startswith("--stats-txt=")]
if _stats_txt_args:
    _stats_txt_path = Path(_stats_txt_args[0].split("=", 1)[1])
    _fenster_label = _label_aus_stem(_stats_txt_path.stem)
else:
    _stats_txt_path = STATS_TXT_DEFAULT
    _fenster_label = FENSTER_LABEL

_chart_png = TEST_DIR / f"phasen_volumen_profil_{_fenster_label}.png"
_bench_lines: Optional[tuple[UserMacroLine, ...]] = (
    USER_LINES_AUG if _fenster_label == "AUG" else None
)

if _macro_live:
    _stats_summary = export_stats_trades(
        ziel_datei=_stats_txt_path,
        fenster=_fenster_label,
        start=START,
        ende=ENDE,
        baseline_signals=_baseline_sigs,
        macro_signals=reclaim_signals,
        referenz_lines=_bench_lines,
    )
    _chart_hinweis = render_standard_chart(
        ziel_png=_chart_png,
        fenster=_fenster_label,
        start=START,
        ende=ENDE,
        df=df,
        phases=phases,
        moves=moves,
        signals=reclaim_signals,
        baseline_signals=_baseline_sigs,
        benchmark_lines=_bench_lines,
        stat_lines=_stat_lines,
        modus_txt="--macro-live",
    )
else:
    _stats_summary = export_stats_trades(
        ziel_datei=_stats_txt_path,
        fenster=_fenster_label,
        start=START,
        ende=ENDE,
        baseline_signals=reclaim_signals,
        referenz_lines=_bench_lines,
    )
    _chart_hinweis = render_standard_chart(
        ziel_png=_chart_png,
        fenster=_fenster_label,
        start=START,
        ende=ENDE,
        df=df,
        phases=phases,
        moves=moves,
        signals=reclaim_signals,
        baseline_signals=None,
        benchmark_lines=_bench_lines,
        stat_lines=_stat_lines,
        modus_txt="Baseline",
    )
print("\n" + _stats_summary)
print("\n" + _chart_hinweis)
