"""
SETUP A: COUNTER-ENGINE (PING-PONG) — KANTEN-REVERSION STATT RECLAIM
=====================================================================
Abgrenzung zur Produktions-Baseline (Setup B / Reclaim, SILVER M15,
+297,14R / 411 Trades / PF 2,33 — v0.4.0-baseline-frozen, UNVERÄNDERT):

  Setup B  : wartet auf den FEHLAUSBRUCH (Durchstich + Schluss zurück in
             der Zone) und handelt die Rückkehr.
  Setup A  : handelt ANTIZIPATIV am Kanten-Kontakt (VAH/VAL) in
             Mean-Reversion-Richtung — "Ping-Pong" Kante -> POC -> Gegenseite.

INFRASTRUKTUR-BASIS (aus scripts/phasen_volumen_profil.py übernommen):
  - Phasen-SEGMENTIERUNG unverändert (MIN_CANDLES=46, VA_PCT=0.93,
    kausale Schnittmengen-Logik, Etablierung/Ausbruch/Moves, Regel-7-Finalize).
  - Volume-Zone (Volume-Profile, Multi-Mountain, POC/VAH/VAL) unverändert.
  - Kausalität: laufende Zone je Signal-Bar (kein Lookahead über die
    finale Phasen-Hülle), Pivot-Bestätigung nachlaufend.

SETUP-A-LOGIK (NEU):
  - Touch-Tracking: barweise Zähler touches_vah / touches_val gegen die
    Zonenkante (U_zone/L_zone) innerhalb der aktiven Phase.
    F1 (arretiert): Touch + Ziel-Geometrie laufen gegen den Snapshot der
    VOR-Bar (vz_prev = Zone bis k-1) — die Signal-Bar verschiebt ihre
    eigene Kante nicht ("Kante flieht vor eigenem Touch" ist eliminiert).
    F3 (arretiert): Outside-Bar (high >= vah UND low <= val in derselben
    Bar) wird verworfen (continue, Zähler unverändert) — gleichzeitig an
    VAH und VAL zu triggern ist ein mechanisches Backtest-Artefakt
    (kein Hedge, keine Doppelzählung).
  - Signal nur wenn Zählerstand <= MAX_TOUCH_COUNT (Touch 1+2; Absorption
    ab Touch 3 wird verworfen — Setup-C-Disziplin).
  - Einstiegs-Modi:
      DIRECT_TOUCH      : SHORT high >= vah  |  LONG low <= val
      CANDLE_REJECTION  : SHORT high >= vah UND close < vah
                        | LONG  low  <= val UND close > val
    (Default CANDLE_REJECTION, Hypothese 1: Schlusskurs-Verweigerung filtert
    Momentum-Ausbrüche.)
  - Einstieg = Open der Folge-Bar (k+1), Bounds-Guard k+1 <= Phasenende.
  - Gültigkeit: SHORT nur wenn entry > POC; LONG nur wenn entry < POC.
  - Cooldown 12 Bars (MIN_SIGNAL_ABSTAND_BARS) je Richtung getrennt.

TRADE-MANAGEMENT (2 Hälften):
  - Hälfte 1 (50 %, ANTEIL_TP1): TP1 = POC exakt.
      Stop: SL_PCT = 0,45 % relativ zum Einstieg.
  - Hälfte 2 (50 %): TP2 = Gegenseite abzüglich 0,20 % Puffer
      (SHORT: val*(1+puffer); LONG: vah*(1-puffer)).
      Stop: sl_init (SL_PCT relativ zum Einstieg) — solange USE_BE=False
      (F2/F6-Default: KEIN BE-Nachzug, Runner-Philosophie wie Setup B,
      Baseline-Invariante); bei USE_BE=True Break-even (entry), sobald
      Hälfte 1 TP1 erreicht hat.
  - Break-even-Semantik (USE_BE=True): BE-Stop für Hälfte 2 wirkt ab der
    Bar NACH der TP1-Bar (t1+1). Wird TP1 nie erreicht (voller SL), behält
    Hälfte 2 in BEIDEN Varianten sl_init. TP1 und TP2 in derselben Bar =>
    beide Hälften gewinnen. USE_BE=False: Hälfte 2 läuft nach TP1 ungestoppt
    bis TP2 / sl_init / ENDE (kein BE-Nachzug, A/B-Hebel F2/F6).
  - Intrabar-Konvention wie Baseline: Ziele werden unabhängig über
    [einstieg_bar .. Datenende] per erster-erreicht-Maske aufgelöst;
    unaufgelöste Reste schließen am letzten Close (ENDE).

DIESE DATEI: Initialisierung (04.09.2026). Keine Testläufe in scripts/.
Testläufe erfolgen ausschließlich über In-Memory-Wrapper in test/tmp_*.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

# ==============================================================================
# DEFAULT-PARAMETER (PineScript-Stil, direkt manuell anpassbar)
# ==============================================================================

SYMBOL: str = "SILVER"
TIMEFRAME: str = "M15"
START: str = "2026-08-10"
ENDE: str = "2026-08-28"

# --- Phasen-Segmentierung (UNVERÄNDERT gegenüber Baseline v0.4.x) ---
MIN_CANDLES: int = 46          # Phasen-Mindestlänge (M15 = 11,5 h Balance)
MIN_PHASE_CANDLES: int = 46    # Abbruch-Reife (2-Close-Bruch erst danach)
MIN_ESTABLISH: int = 4         # Etablierung: Touch-Summe beider Grenzen
PIVOT_LOOKBACK: int = 2        # Pivot-Bestätigung (M15 = 30 min)
VA_PCT: float = 0.93           # Value-Area-Resonanzkante (§8.23)
NUM_BINS: int = 60
SMOOTH_WIN: int = 3
VALLEY_REL: float = 0.15
MIN_MOUNTAIN_PCT: float = 4.0
MIN_CLUSTER: int = 2
MIN_TOUCHES: int = 3           # handelbare Phase: Touches je Grenze
MIN_SPREAD_PCT: float = 1.5    # Spread-Gate (relativ)
DENSITY_BAND: float = 0.15     # USD Touch-/Cluster-Band (SILVER-Kalibrierung)
TOL: float = 0.34              # USD 2-Close-Bruch-Toleranz
TOL_TOUCH: float = 0.15        # USD Touch-Toleranz Phasen-Ende
SHIFT_TOL: float = 0.05        # USD Kanten-Verschiebungs-Schwelle
GRENZ_KONTAKT_TOL: float = 0.0 # Regel-7-Finalize
FENSTER_PIVOTS: int = 100      # Schnittmengen-Fenster

# --- Setup A: Signal-Logik ---
MAX_TOUCH_COUNT: int = 2       # Liquiditäts-Absorptionsfilter (Touch 1+2)
ENTRY_MODE: Literal["DIRECT_TOUCH", "CANDLE_REJECTION"] = "CANDLE_REJECTION"
MIN_ZONE_CANDLES: int = 30     # Mindest-Bars der laufenden Zone vor Signal-Scan
MIN_SIGNAL_ABSTAND_BARS: int = 12  # Cooldown (M15 = 3 h), je Richtung

# --- Setup A: Trade-Management ---
SL_PCT: float = 0.45           # Stop relativ zum Einstieg
ANTEIL_TP1: float = 50.0       # 50 % am POC (Derisking), Rest 50 %
TP2_PUFFER_PCT: float = 0.20   # TP2 = Gegenseite abzüglich Puffer
USE_BE: bool = False           # F2/F6: False = KEIN BE-Nachzug (Default,
                               # Runner wie Baseline/Setup B); True = BE
                               # nach TP1 (Kontroll-Arm, Status quo)

# ==============================================================================
# DATENVERTRÄGE (Typisierung, slots)
# ==============================================================================


@dataclass(frozen=True, slots=True)
class CounterConfig:
    """Verbindlicher Datenvertrag der Counter-Engine (Setup A / Ping-Pong).

    Spiegelt die Default-Parameter oben 1:1; dient der Selbst-Dokumentation
    und der typsicheren Übergabe an spätere In-Memory-Testwrapper
    (test/tmp_*). Die Modul-Konstanten bleiben die Quelle der Wahrheit.
    """
    symbol: str = SYMBOL
    timeframe: str = TIMEFRAME
    start: str = START
    ende: str = ENDE
    # Segmentierung (unverändert)
    min_candles: int = MIN_CANDLES
    min_phase_candles: int = MIN_PHASE_CANDLES
    min_establish: int = MIN_ESTABLISH
    pivot_lookback: int = PIVOT_LOOKBACK
    va_pct: float = VA_PCT
    min_touches: int = MIN_TOUCHES
    min_spread_pct: float = MIN_SPREAD_PCT
    density_band: float = DENSITY_BAND
    tol: float = TOL
    tol_touch: float = TOL_TOUCH
    shift_tol: float = SHIFT_TOL
    # Setup A
    max_touch_count: int = MAX_TOUCH_COUNT
    entry_mode: Literal["DIRECT_TOUCH", "CANDLE_REJECTION"] = ENTRY_MODE
    min_zone_candles: int = MIN_ZONE_CANDLES
    sl_pct: float = SL_PCT
    anteil_tp1: float = ANTEIL_TP1
    tp2_puffer_pct: float = TP2_PUFFER_PCT
    min_signal_abstand_bars: int = MIN_SIGNAL_ABSTAND_BARS
    use_be: bool = USE_BE  # F6-Default: False = KEIN BE-Nachzug (Runner)


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
class CounterSignal:
    """Setup-A-Signal (Ping-Pong an VAH/VAL)."""
    typ: Literal["SHORT", "LONG"]
    mode: Literal["DIRECT_TOUCH", "CANDLE_REJECTION"]
    bar: int
    ts: pd.Timestamp
    einstieg_bar: int
    einstieg_preis: float
    vah: float                    # laufende U_zone (Kante)
    val: float                    # laufende L_zone (Kante)
    poc: float                    # laufender POC
    touches_vah: int              # Zählerstand inkl. aktuellem Touch
    touches_val: int
    tp1: float
    tp2: float
    sl: float
    crv: float                    # |tp1-entry| / risk (Info, kein Filter)
    crv2: float                   # |tp2-entry| / risk (Info, kein Filter)
    use_be: bool = USE_BE         # F2/F6: Abrechnungsvariante des Trades
                                  # (True = BE-Nachzug, False = Runner)
    phase: int = 0
    trade: Optional[TradeResolution] = None


# ==============================================================================
# PFADE & LABEL
# ==============================================================================

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
TEST_DIR: Path = ROOT_DIR / "test"
DB_PATH: Path = ROOT_DIR / "data" / "market_data.duckdb"
OUT_PNG: Path = Path(__file__).resolve().parent / "counter_engine_profil.png"


def fenster_label(start: str, ende: str) -> str:
    """Kompaktes Fenster-Label für Artefakt-Dateinamen (AUG/S1/S2/Fallback)."""
    if start == "2026-08-10" and ende == "2026-08-28":
        return "AUG"
    if start == "2026-02-05" and ende == "2026-08-28":
        return "S1"
    if start == "2025-01-01" and ende == "2025-12-01":
        return "S2"
    return f"{start[:10].replace('-', '')}_{ende[:10].replace('-', '')}"


FENSTER_LABEL: str = fenster_label(START, ENDE)
STATS_TXT_DEFAULT: Path = TEST_DIR / f"stats_counter_{FENSTER_LABEL}.txt"
CHART_PNG_DEFAULT: Path = TEST_DIR / f"phasen_counter_{FENSTER_LABEL}.png"

# --- CLI-Overrides (vor Funktionsdefinitionen, damit Defaults greifen) ---
for _a in sys.argv[1:]:
    if _a.startswith("--symbol="):
        SYMBOL = _a.split("=", 1)[1]
        print(f"==> SYMBOL ueberschrieben: {SYMBOL}")
    if _a.startswith("--start="):
        START = _a.split("=", 1)[1]
        print(f"==> START ueberschrieben: {START}")
    if _a.startswith("--ende="):
        ENDE = _a.split("=", 1)[1]
        print(f"==> ENDE ueberschrieben: {ENDE}")
    if _a.startswith("--va-pct="):
        VA_PCT = float(_a.split("=", 1)[1])
        print(f"==> VA_PCT ueberschrieben: {VA_PCT}")
    if _a.startswith("--max-touch="):
        MAX_TOUCH_COUNT = int(_a.split("=", 1)[1])
        print(f"==> MAX_TOUCH_COUNT ueberschrieben: {MAX_TOUCH_COUNT}")
    if _a.startswith("--entry-mode="):
        ENTRY_MODE = _a.split("=", 1)[1]  # type: ignore
        assert ENTRY_MODE in ("DIRECT_TOUCH", "CANDLE_REJECTION")
        print(f"==> ENTRY_MODE ueberschrieben: {ENTRY_MODE}")
    if _a.startswith("--sl-pct="):
        SL_PCT = float(_a.split("=", 1)[1])
        print(f"==> SL_PCT ueberschrieben: {SL_PCT}")
    if _a.startswith("--anteil-tp1="):
        ANTEIL_TP1 = float(_a.split("=", 1)[1])
        print(f"==> ANTEIL_TP1 ueberschrieben: {ANTEIL_TP1}")
    if _a.startswith("--tp2-puffer="):
        TP2_PUFFER_PCT = float(_a.split("=", 1)[1])
        print(f"==> TP2_PUFFER_PCT ueberschrieben: {TP2_PUFFER_PCT}")
    if _a.startswith("--cooldown="):
        MIN_SIGNAL_ABSTAND_BARS = int(_a.split("=", 1)[1])
        print(f"==> MIN_SIGNAL_ABSTAND_BARS ueberschrieben: {MIN_SIGNAL_ABSTAND_BARS}")
    if _a.startswith("--min-zone-candles="):
        MIN_ZONE_CANDLES = int(_a.split("=", 1)[1])
        print(f"==> MIN_ZONE_CANDLES ueberschrieben: {MIN_ZONE_CANDLES}")
    if _a.startswith("--be-nachzug="):
        _be_val: str = _a.split("=", 1)[1].lower()
        USE_BE = _be_val in ("true", "1", "yes")
        print(f"==> USE_BE (--be-nachzug) ueberschrieben: {USE_BE}")

FENSTER_LABEL = fenster_label(START, ENDE)
STATS_TXT_DEFAULT = TEST_DIR / f"stats_counter_{FENSTER_LABEL}.txt"
CHART_PNG_DEFAULT = TEST_DIR / f"phasen_counter_{FENSTER_LABEL}.png"

# ==============================================================================
# 1) DATEN EINLESEN (Strikt DuckDB)
# ==============================================================================


def load_data(db_path: Path, start: str, ende: str) -> pd.DataFrame:
    """Lädt OHLCV-Bars für SYMBOL/TIMEFRAME im Fenster (UTC, Ende exklusiv)."""
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB-Datei nicht gefunden: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    d = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='{SYMBOL}' AND timeframe='{TIMEFRAME}'
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
    """Nachlaufende Pivot-Bestätigung (Lag n) über High/Low."""
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
# 3) SCHNITTMENGEN-LINIE & LEVEL-HELPER
# ==============================================================================


def level_schnittmenge(
    prices: List[float] | np.ndarray,
    target_typ: Literal["H", "L"] = "H",
    band: float = DENSITY_BAND,
    min_cluster: int = MIN_CLUSTER,
    erweiterung_pct: float = 1.0,
) -> Optional[float]:
    """Kausal geclusterte Schnittmengen-Kante (wie Baseline v0.4.x)."""
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
    """Anzahl der Preise innerhalb des Bands um das Level."""
    if level is None or not len(prices):
        return 0
    return int(np.sum(np.abs(np.array(prices, dtype=float) - level) <= band))


def _linie(prices: List[float], typ: Literal["H", "L"]) -> Optional[float]:
    """Schnittmengen-Linie über das (begrenzte) Preis-Fenster."""
    if not prices:
        return None
    w = prices if len(prices) <= FENSTER_PIVOTS else prices[-FENSTER_PIVOTS:]
    return level_schnittmenge(w, typ)


def _final_level(schnitt: Optional[float], birth: Optional[float], typ: Literal["H", "L"]) -> Optional[float]:
    """Vereinigt Schnittmenge mit Geburtszone (nach außen)."""
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
    """Wie _final_level, aber Geburtszone nur bei bestätigtem Pivot."""
    if schnitt is None:
        return birth
    if birth is None or conf_ts is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _birth_level(birth: Optional[pd.DataFrame], typ: Literal["H", "L"]) -> Optional[float]:
    """Geburtszonen-Level aus bestätigten Pivots zwischen den Phasen."""
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
    """Letzter Grenz-Kontakt (Regel-7-Finalize)."""
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
# 3b) VOLUME-PROFIL & VOLUME-ZONE (Multi-Mountain)
# ==============================================================================


def build_volume_profile(sub: pd.DataFrame, num_bins: int = NUM_BINS) -> Optional[VolumeProfileData]:
    """Verteilt tick_volume proportional über die High-Low-Spanne je Bar."""
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
    """Gleitender Durchschnitt über das Volumen-Histogramm."""
    if win <= 1 or len(vol) < win:
        return vol.astype(float)
    return np.convolve(vol, np.ones(win) / win, mode="same")


def find_mountains(
    vol_s: np.ndarray,
    min_pct: float = MIN_MOUNTAIN_PCT,
    valley_rel: float = VALLEY_REL,
) -> List[Tuple[int, int, int]]:
    """Zerlegt das geglättete Profil in Berge (Täler tiefer als valley_rel)."""
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
    """Value-Area (POC/VAH/VAL) eines Bergs per Volumen-Expansion."""
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
    """Volume-Zone: U_zone = höchste VAH, L_zone = tiefste VAL, POC = dominanter Berg."""
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


def _laufende_zone(df: pd.DataFrame, p: PhaseData, k: int) -> Optional[VolumeZone]:
    """Kausale laufende Zone bis einschließlich Bar k (kein Lookahead)."""
    return compute_volume_zone(df.iloc[p.i_start: k + 1])

# ==============================================================================
# 4) PHASEN-SEGMENTIERUNG (UNVERÄNDERTE Baseline-Logik v0.4.x)
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

# --- Regel-7-Finalize (letzter Grenz-Kontakt) ---
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
# 6) SETUP A: COUNTER-SIGNALE (Ping-Pong an VAH/VAL)
# ==============================================================================


def find_counter_signals(
    df: pd.DataFrame,
    p: PhaseData,
    entry_mode: Literal["DIRECT_TOUCH", "CANDLE_REJECTION"] = ENTRY_MODE,
    max_touch: int = MAX_TOUCH_COUNT,
    cooldown_bars: int = MIN_SIGNAL_ABSTAND_BARS,
    min_zone_candles: int = MIN_ZONE_CANDLES,
    use_be: bool = USE_BE,
) -> List[CounterSignal]:
    """Scannt Setup-A-Signale bar für bar (kausal, drift-stabile Zone).

    Touch-Tracking: touches_vah / touches_val zählen barweise die Berührungen
    der Zonenkante innerhalb der Phase. F1 (Entscheid A): Touch UND
    Ziel-Geometrie werden gegen den Snapshot der VOR-Bar evaluiert
    (vz_prev = _laufende_zone(df, p, k-1), Zone bis k-1) — die Signal-Bar k
    kann ihre eigene Kante nicht mehr durch ihr Volumen verschieben
    (drift-stabiler Zähler). F3 (Entscheid A): Eine Outside-Bar (high >= vah
    UND low <= val in derselben Bar) wird verworfen (continue, Zähler
    unverändert) — ein gleichzeitiges SHORT+LONG-Triggersignal wäre ein
    Hedge-Artefakt mechanischer Backtests. Ein Signal ist nur zulässig,
    solange der Zählerstand (inklusive des aktuellen Touch) <= max_touch
    ist — Touch 3+ gilt als Absorption (Setup-C-Disziplin).

    Args:
        df: OHLCV-Frame mit idx-Spalte.
        p: PhaseData mit i_start/i_ende.
        entry_mode: DIRECT_TOUCH (jeder Kontakt) oder CANDLE_REJECTION
            (Kontakt + Schlusskurs verweigert die Seite).
        max_touch: MAX_TOUCH_COUNT (Absorptionsfilter).
        cooldown_bars: Mindestabstand gleichgerichteter Signale (Bars).
        min_zone_candles: Mindest-Bars der laufenden Zone vor dem Scan.
        use_be: True = BE-Nachzug nach TP1 (Kontroll-Arm, Status quo);
            False = KEIN BE-Nachzug (F2/F6-Default, Runner-Philosophie).

    Returns:
        Liste der CounterSignals (trade bereits aufgelöst).
    """
    sigs: List[CounterSignal] = []
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values
    op = df["open"].values
    ts = df["ts"].values
    last_bar: Dict[Literal["SHORT", "LONG"], int] = {
        "SHORT": -10**9, "LONG": -10**9}
    sl_p = SL_PCT / 100.0
    tp2_puffer = TP2_PUFFER_PCT / 100.0
    touches_vah: int = 0
    touches_val: int = 0

    for k in range(p.i_start, p.i_ende):
        # F1 (Entscheid A): drift-stabiler Touch gegen die Kante der VOR-Bar.
        # vz_prev = _laufende_zone(df, p, k-1) ist der Snapshot VOR der
        # Signal-Bar k; Bar k kann ihre eigene Kante nicht mehr verschieben
        # ("Kante flieht vor eigenem Touch"). Touch UND Ziel-Geometrie
        # (POC/TP1/TP2/entry>poc) stammen aus DEMSELBEN Snapshot ->
        # deterministische, kausal geschlossene RR-Geometrie.
        if k - 1 < p.i_start:
            continue
        if k - p.i_start < min_zone_candles:
            continue
        vz = _laufende_zone(df, p, k - 1)
        if vz is None:
            continue
        vah, val, poc = vz.U_zone, vz.L_zone, vz.POC
        if vah is None or val is None or poc is None:
            continue
        ts_k = pd.Timestamp(ts[k])

        touch_vah = bool(hi[k] >= vah)
        touch_val = bool(lo[k] <= val)

        # F3 (Entscheid A): Outside-Bar verwerfen. Berührt Bar k BEIDE Kanten
        # des vz_prev-Snapshots (high >= vah UND low <= val), ist das eine
        # Volatilitäts-Expansion — gleichzeitig an VAH und VAL zu triggern
        # wäre ein Artefakt mechanischer Backtests (die SHORT- und LONG-
        # Blöcke würden sonst unabhängig feuern -> Hedge-Artefakt +
        # Doppelzählung). Beide Seiten verwerfen; die Absorptionszähler
        # bleiben unverändert.
        if touch_vah and touch_val:
            continue

        if touch_vah:
            touches_vah += 1
        if touch_val:
            touches_val += 1

        # ---- SHORT an VAH ----
        if touch_vah and touches_vah <= max_touch:
            if entry_mode == "DIRECT_TOUCH" or cl[k] < vah:
                if k + 1 <= p.i_ende and k - last_bar["SHORT"] >= cooldown_bars:
                    e_bar, e_preis = k + 1, float(op[k + 1])
                    if e_preis > poc:  # TP1 (POC) liegt unter dem Einstieg
                        sl = e_preis * (1.0 + sl_p)
                        tp1 = poc
                        tp2 = val * (1.0 + tp2_puffer)
                        risk = abs(sl - e_preis)
                        crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                        crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                        if e_preis > tp2:  # strukturelle RR-Geometrie
                            last_bar["SHORT"] = k
                            sig = CounterSignal(
                                typ="SHORT",
                                mode=entry_mode,
                                bar=int(k),
                                ts=ts_k,
                                einstieg_bar=int(e_bar),
                                einstieg_preis=e_preis,
                                vah=vah, val=val, poc=poc,
                                touches_vah=touches_vah,
                                touches_val=touches_val,
                                tp1=tp1, tp2=tp2, sl=sl,
                                crv=float(crv) if not np.isnan(crv) else 0.0,
                                crv2=float(crv2) if not np.isnan(crv2) else 0.0,
                                use_be=use_be,
                            )
                            sig.trade = _aufloesen_counter(df, sig, use_be=use_be)
                            sigs.append(sig)

        # ---- LONG an VAL ----
        if touch_val and touches_val <= max_touch:
            if entry_mode == "DIRECT_TOUCH" or cl[k] > val:
                if k + 1 <= p.i_ende and k - last_bar["LONG"] >= cooldown_bars:
                    e_bar, e_preis = k + 1, float(op[k + 1])
                    if e_preis < poc:  # TP1 (POC) liegt über dem Einstieg
                        sl = e_preis * (1.0 - sl_p)
                        tp1 = poc
                        tp2 = vah * (1.0 - tp2_puffer)
                        risk = abs(sl - e_preis)
                        crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                        crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                        if e_preis < tp2:  # strukturelle RR-Geometrie
                            last_bar["LONG"] = k
                            sig = CounterSignal(
                                typ="LONG",
                                mode=entry_mode,
                                bar=int(k),
                                ts=ts_k,
                                einstieg_bar=int(e_bar),
                                einstieg_preis=e_preis,
                                vah=vah, val=val, poc=poc,
                                touches_vah=touches_vah,
                                touches_val=touches_val,
                                tp1=tp1, tp2=tp2, sl=sl,
                                crv=float(crv) if not np.isnan(crv) else 0.0,
                                crv2=float(crv2) if not np.isnan(crv2) else 0.0,
                                use_be=use_be,
                            )
                            sig.trade = _aufloesen_counter(df, sig, use_be=use_be)
                            sigs.append(sig)
    return sigs


def _aufloesen_counter(
    df: pd.DataFrame,
    s: CounterSignal,
    use_be: bool = USE_BE,
) -> TradeResolution:
    """Löst ein Setup-A-Signal in 2 Hälften auf (TP1 + Hälfte 2).

    Hälfte 1 (ANTEIL_TP1 %): TP1 = POC; Stop sl_init (SL_PCT relativ).
    Hälfte 2 (Rest): TP2 = Gegenseite ∓ TP2_PUFFER_PCT.
      - use_be=False (F2/F6-Default): Stop bleibt sl_init — Hälfte 2 läuft
        nach TP1 ungestoppt bis TP2 / sl_init / ENDE (Runner-Philosophie
        wie Setup B, Baseline-Invariante).
      - use_be=True: Stop = Break-even (entry) sobald Hälfte 1 TP1 erreicht
        hat (wirkt ab Bar t1+1); vorher sl_init.
    Wird TP1 nie erreicht (voller SL), behält Hälfte 2 in BEIDEN Varianten
    sl_init. TP1 und TP2 in derselben Bar => beide Hälften gewinnen.
    Unaufgelöste Reste schließen am letzten Close (ENDE).

    Intrabar-Konvention: Ziele werden unabhängig über [einstieg_bar ..
    Datenende] per erster-erreicht-Maske aufgelöst (Baseline-Semantik).

    Args:
        df: OHLCV-Frame.
        s: CounterSignal mit einstieg_bar/einstieg_preis/tp1/tp2.
        use_be: True = BE-Nachzug nach TP1 (Kontroll-Arm, Status quo);
            False = KEIN BE-Nachzug (F2/F6-Default, Runner-Philosophie).

    Returns:
        TradeResolution (r1/r2/resultat/Flags).
    """
    e_bar = s.einstieg_bar
    entry = s.einstieg_preis
    typ = s.typ
    tp1, tp2 = s.tp1, s.tp2
    p = SL_PCT / 100.0
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

    if typ == "SHORT":
        t1 = _first(lo <= tp1)
        t2 = _first(lo <= tp2)
        t_sl0 = _first(hi >= sl_init)
    else:
        t1 = _first(hi >= tp1)
        t2 = _first(hi >= tp2)
        t_sl0 = _first(lo <= sl_init)

    # ---- Hälfte 1: TP1 (POC) vs. SL_init ----
    if t1 < t_sl0:
        r1, ex1, g1 = _r(tp1), tp1, "TP1"
    elif t_sl0 < n_bars:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    else:
        r1, ex1, g1 = _r(float(cl[-1])), float(cl[-1]), "ENDE"

    # ---- Hälfte 2: TP2 (Gegenseite) vs. Break-even / SL_init ----
    tp1_hit = (g1 == "TP1")
    if tp1_hit and use_be:
        # F2/F6-Kontroll-Arm (use_be=True): BE-Stop wirkt ab der Bar NACH
        # der TP1-Bar (t1+1).
        if t2 <= t1:
            # TP1 und TP2 in derselben Bar erreicht -> Rest gewinnt TP2.
            r2, ex2, g2 = _r(tp2), tp2, "TP2"
        else:
            if typ == "SHORT":
                t_be = _first(np.concatenate([np.zeros(t1 + 1, dtype=bool),
                                              hi[t1 + 1:] >= entry]))
            else:
                t_be = _first(np.concatenate([np.zeros(t1 + 1, dtype=bool),
                                              lo[t1 + 1:] <= entry]))
            if t2 < t_be:
                r2, ex2, g2 = _r(tp2), tp2, "TP2"
            elif t_be < n_bars:
                r2, ex2, g2 = 0.0, entry, "BE"
            else:
                r2, ex2, g2 = _r(float(cl[-1])), float(cl[-1]), "ENDE"
    else:
        # F2/F6-Default (use_be=False, Runner-Philosophie) ODER TP1 nie
        # erreicht: Hälfte 2 behält sl_init und läuft bis TP2 / SL / ENDE.
        if t2 < t_sl0:
            r2, ex2, g2 = _r(tp2), tp2, "TP2"
        elif t_sl0 < n_bars:
            r2, ex2, g2 = -1.0, sl_init, "SL"
        else:
            r2, ex2, g2 = _r(float(cl[-1])), float(cl[-1]), "ENDE"

    _w1 = ANTEIL_TP1 / 100.0
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


# --- Signal-Sammlung über alle Phasen (kausal, wie Baseline) ---
counter_signals: List[CounterSignal] = []
for _pi, _p in enumerate(phases, 1):
    for _s in find_counter_signals(df, _p):
        _s.phase = _pi
        counter_signals.append(_s)
counter_signals.sort(key=lambda s: s.ts)

# ==============================================================================
# 7) STATISTIK & KONSOLEN-AUSGABE
# ==============================================================================

_n_calls = sum(1 for s in counter_signals if s.typ == "LONG")
_n_sells = sum(1 for s in counter_signals if s.typ == "SHORT")
_n_win = sum(1 for s in counter_signals if s.trade and s.trade.resultat == "GEWONNEN")
_n_loss = sum(1 for s in counter_signals if s.trade and s.trade.resultat == "VERLOREN")
_n_neu = sum(1 for s in counter_signals if s.trade and s.trade.resultat == "NEUTRAL")
_n_tp1 = sum(1 for s in counter_signals if s.trade and s.trade.tp1_hit)
_n_tp2 = sum(1 for s in counter_signals if s.trade and s.trade.tp2_hit)
_n_sl1 = sum(1 for s in counter_signals if s.trade and s.trade.sl_hit1)
_n_sl2 = sum(1 for s in counter_signals if s.trade and s.trade.sl_hit2)
_n_be = sum(1 for s in counter_signals if s.trade and s.trade.grund2 == "BE")
_decided = _n_win + _n_loss
_winrate = 100.0 * _n_win / _decided if _decided else 0.0
_sum_r = sum(s.trade.r_mult for s in counter_signals if s.trade)
_gewinn_pct = _sum_r * SL_PCT
_gross_w = sum(s.trade.r_mult for s in counter_signals
               if s.trade and s.trade.resultat == "GEWONNEN")
_gross_l = sum(abs(s.trade.r_mult) for s in counter_signals
               if s.trade and s.trade.resultat == "VERLOREN")
_pf = (_gross_w / _gross_l) if _gross_l else float("inf")

print("\n" + "=" * 110)
print(f"SETUP A (COUNTER/PING-PONG) {SYMBOL} {TIMEFRAME} {START} - {ENDE}")
print(f"Entry-Mode: {ENTRY_MODE} | MAX_TOUCH_COUNT: {MAX_TOUCH_COUNT} | "
      f"Cooldown: {MIN_SIGNAL_ABSTAND_BARS} | TP1 {ANTEIL_TP1:.0f}% @ POC | "
      f"BE-Nachzug: {'AN (Kontroll-Arm)' if USE_BE else 'AUS (F6-Default, Runner)'}")
print("=" * 110)
print(f"Phasen gesamt: {len(phases)} | handelbar: "
      f"{sum(1 for p in phases if p.handelbar)} | Moves: {len(moves)}")
print(f"Counter-Signale: {len(counter_signals)} "
      f"({_n_sells} SHORT / {_n_calls} LONG) | Trades aufgeloest: "
      f"{sum(1 for s in counter_signals if s.trade)}")
print(f"Win-Rate: {_winrate:.1f}% ({_n_win}W/{_n_loss}L/{_n_neu}N)")
print(f"Summe R: {_sum_r:+.2f} | Gesamtgewinn {_gewinn_pct:+.2f}% "
      f"(Risiko {SL_PCT:.2f}%/Trade)")
print(f"Profit-Faktor: {_pf:.2f} (grossW {_gross_w:+.2f} / grossL {_gross_l:.2f})")
print(f"TP1-Hit: {_n_tp1}/{len(counter_signals)} | TP2-Hit: {_n_tp2}/{len(counter_signals)} "
      f"| SL1: {_n_sl1} | SL2: {_n_sl2} | BE-Exit: {_n_be}")

_ant_txt = (f"{ANTEIL_TP1:.0f}/{100 - ANTEIL_TP1:.0f}"
            if 0 < ANTEIL_TP1 < 100 else ("100/0" if ANTEIL_TP1 >= 100 else "0/100"))
_out_lines = [
    "=" * 110,
    f"STATS & TRADE-REPORT | SETUP A COUNTER-ENGINE | Fenster: {FENSTER_LABEL}  "
    f"({START} - {ENDE})",
    f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME} | VA_PCT: {VA_PCT} | "
    f"MIN_CANDLES: {MIN_CANDLES}",
    f"Entry-Mode: {ENTRY_MODE} | MAX_TOUCH_COUNT: {MAX_TOUCH_COUNT} | "
    f"MIN_ZONE_CANDLES: {MIN_ZONE_CANDLES}",
    f"Trade-Management: SL_PCT={SL_PCT} | Split {_ant_txt} (TP1=POC) | "
    f"TP2_PUFFER_PCT={TP2_PUFFER_PCT} | Cooldown={MIN_SIGNAL_ABSTAND_BARS} Bars",
    f"BE-Variante (F2/F6): {'BE-Nachzug nach TP1 (Kontroll-Arm, Status quo)' if USE_BE else 'KEIN BE-Nachzug (Default, Runner-Philosophie)'}",
    "=" * 110,
    f"Phasen gesamt: {len(phases)} | handelbar: "
    f"{sum(1 for p in phases if p.handelbar)}",
    f"Signale/Trades gesamt : {len(counter_signals)}",
    f"Long / Short          : {_n_calls} / {_n_sells}",
    f"Win-Rate              : {_winrate:.1f}%  ({_n_win} Gewinn / {_n_loss} Verlust / {_n_neu} Neutral)",
    f"Summe R (kumuliert)   : {_sum_r:+.2f}",
    f"Avg Win (R)           : {(_gross_w / _n_win) if _n_win else 0:+.2f}  (ueber {_n_win} Gewinntrades)",
    f"Avg Loss (R)          : {(-_gross_l / _n_loss) if _n_loss else 0:+.2f}  (ueber {_n_loss} Verlusttrades)",
    f"Profit-Faktor         : {_pf:.2f}  (Brutto-Gewinn-R {_gross_w:+.2f} / Brutto-Verlust-R {-_gross_l:.2f})",
    f"TP1-Hit               : {_n_tp1}/{len(counter_signals)} ({100.0*_n_tp1/len(counter_signals) if counter_signals else 0:.1f}%)",
    f"TP2-Hit               : {_n_tp2}/{len(counter_signals)} ({100.0*_n_tp2/len(counter_signals) if counter_signals else 0:.1f}%)",
    f"BE-Exit (Haelfte 2)   : {_n_be}",
    "",
    "TRADE-LOG (alle Trades; R-mult = gewichtete 2-Haelfte)",
    "Nr | Ph | Signal-Bar(ts)      | Typ  | Mode | Tch | EntryBar | Entry   | POC     | VAH     | VAL     | "
    "TP1     | TP2     | Exit1  | G1 | R1    | Exit2  | G2 | R2    | R-mult | Resultat",
    "-" * 110,
]

_fmt = lambda t: t.strftime("%Y-%m-%d %H:%M")
for _i, s in enumerate(counter_signals, 1):
    assert s.trade is not None
    _tr = s.trade
    _out_lines.append(
        f"{_i:2d} | P{s.phase:<2d} | {_fmt(s.ts)} | {s.typ:5s} | {s.mode[:4]:4s} | "
        f"{s.touches_vah if s.typ == 'SHORT' else s.touches_val:3d} | "
        f"{s.einstieg_bar:8d} | {s.einstieg_preis:7.3f} | {s.poc:7.3f} | "
        f"{s.vah:7.3f} | {s.val:7.3f} | {s.tp1:7.3f} | {s.tp2:7.3f} | "
        f"{_tr.exit1:7.3f} | {_tr.grund1:4s} | {_tr.r1:+5.2f} | "
        f"{_tr.exit2:7.3f} | {_tr.grund2:4s} | {_tr.r2:+5.2f} | "
        f"{_tr.r_mult:+6.2f} | {_tr.resultat}"
    )
if not counter_signals:
    _out_lines.append("(keine Signale)")
_out_lines.append("=" * 110)
_out_lines.append(f"Bezug Setup B (SILVER M15 Baseline AUG): +24,97R / 27 Tr / PF 2,83")

_stats_txt_path = STATS_TXT_DEFAULT
_for_args = [a for a in sys.argv if a.startswith("--stats-txt=")]
if _for_args:
    _stats_txt_path = Path(_for_args[0].split("=", 1)[1])
with open(_stats_txt_path, "w", encoding="utf-8") as _f:
    _f.write("\n".join(_out_lines) + "\n")
print(f"\nStats geschrieben: {_stats_txt_path}")

# ==============================================================================
# 8) CHART (optional, --chart)
# ==============================================================================
if "--chart" in sys.argv:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _chart_png = CHART_PNG_DEFAULT
    for _ca in [a for a in sys.argv if a.startswith("--chart=")]:
        _chart_png = Path(_ca.split("=", 1)[1])

    fig, ax = plt.subplots(figsize=(17, 9))
    ax.plot(df["idx"], df["close"], lw=0.6, color="#333333")
    for _p in phases:
        if _p.U_final is not None:
            ax.axhline(_p.U_final, color="#c00000", lw=1.0, ls="--", alpha=0.6)
        if _p.L_final is not None:
            ax.axhline(_p.L_final, color="#1a7d1a", lw=1.0, ls="--", alpha=0.6)
        if _p.POC is not None:
            ax.axhline(_p.POC, color="#e07b00", lw=0.8, ls="-.", alpha=0.5)
    for _s in counter_signals:
        _mk = "^" if _s.typ == "LONG" else "v"
        _mc = "#1a7d1a" if _s.typ == "LONG" else "#c00000"
        ax.scatter([_s.einstieg_bar], [_s.einstieg_preis], marker=_mk,
                   color=_mc, s=40, zorder=5)
        if _s.trade is not None:
            ax.annotate(f"{_s.trade.r_mult:+.1f}", (_s.einstieg_bar, _s.einstieg_preis),
                        textcoords="offset points", xytext=(0, 6), fontsize=6)
    step = max(8, len(df) // 16)
    ticks = np.arange(0, len(df), step)
    ax.set_xticks(ticks)
    ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
                       rotation=45, ha="right", fontsize=8)
    ax.set_xlim(-1, len(df))
    ax.set_title(f"SETUP A COUNTER-ENGINE {SYMBOL} M15 {START} - {ENDE} "
                 f"(VA {VA_PCT:.0f}%, {ENTRY_MODE}, MaxTouch {MAX_TOUCH_COUNT})")
    ax.set_ylabel("USD")
    ax.grid(alpha=0.3)
    legend_elements = [
        Line2D([0], [0], color="#c00000", lw=1.0, ls="--", label="OBEN (U_final)"),
        Line2D([0], [0], color="#1a7d1a", lw=1.0, ls="--", label="UNTEN (L_final)"),
        Line2D([0], [0], color="#e07b00", lw=0.8, ls="-.", label="POC"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#1a7d1a", ms=8, label="LONG (VAL-Ping)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="#c00000", ms=8, label="SHORT (VAH-Ping)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(_chart_png, dpi=130)
    print(f"Chart gespeichert: {_chart_png}")

print("\nFERTIG")
