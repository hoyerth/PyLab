"""
SETUP C - PHASE-1-PRODUKTIONSKERN (scripts/setup_c_profil.py)
================================================================
Implementiert den arretierten Phase-1-Kern aus §2.13/§2.14 des Lastenhefts
``docs/setup_c_experiment.md`` auf der Modul-Basis
``scripts/market_segmentation.py`` (KEIN ``exec()``-Slice, KEINE
Produktions-Baseline-Veränderung):

    RAW-Cluster A (Vorlauf <= 1) + F4-Stop intrabar (Puffer 0,15 USD)
    + terminaler Zeit-Exit 48/96 + phasenlokale Open-Position-Suppression
    (Pflicht-Schutzschicht, §2.13-C/§2.13-1.4).

0,45 %-SL bleibt ausschliesslich r_ref-Messung, nie Produktions-Stop.

Verifikation (§2.14/§2.15, zweistufiges Gate; re-arretiert nach
Einheiten-Bereinigung D4-Ratchet, 05.09.2026)
---------------------------------------
L1  Pipeline-Anker (Populationen): CONFIRMED / RAW gesamt (A/B) / RETEST je
    Fenster AUG/S1/S2. F3/CONFIRMED/RETEST sind bitgenau invariant; der
    RAW-Split folgt der Ratchet-Korrektur (AUG 10 (2/8), S1 105 (38/67),
    S2 76 (3/73)).
L2  RAW-Cluster A unter Zeit-Exit N=48/N=96: Summen r_f4/r_ref, Exit-
    Verteilung, Haltedauer, Rechts-Zensierung (E2) - bitgenau gegen die am
    05.09.2026 neu arretierten Soll-Werte (§2.14-A; Referenz = Report
    ``KEIN_TRAILING``). Anlass: µs/ns-Einheiten-Bug in ``_kanten_reihe``
    (statische Kante statt D4-Ratchet-Stufenfunktion), Fix dort dokumentiert.

Der L2-Referenzlauf der Explorationsphase war suppression-frei (Reports
``tmp_setup_c_zeitexit_*.txt``, Schritt 4a). Die Produktion schaltet die
phasenlokale Suppression als Pflicht-Schutzschicht hinzu (Whipsaw-Beschluss
F3, §2.12). ``TrendConfig.suppression_phasenlokal`` steuert beide Modi:
``False`` reproduziert die §2.14-Soll-Werte (Gate-Lauf), ``True`` ist der
Produktions-Default und weist das Delta als n_supprimiert aus (zusaetzlich
druckt der Report die suppression-freie L2-Referenzzeile).

F3-Suppression (arretierte Semantik, §2.13-C: "aktiver Trade in DERSELBEN
Richtung derselben Phase"): Der Suppression-Key ist (phase, dir). Da
``_erfasse_raw`` je (Phase, Richtung) maximal EIN Signal liefert, ist die
Suppression fuer die RAW-A-Population ein striktes No-op (n_supprimiert=0);
die Produktion reproduziert damit die arretierte L2-Referenz bitgenau.
Kein Cross-Richtungs-Eingriff (up/down derselben Phase sind unabhaengige,
gleichzeitig handelbare Setups).

Kausalitaet (unveraendert aus der Baseline/den Referenz-Reports):
- F4-Stop intrabar mit VORRANG vor dem Zeit-Exit an derselben Bar.
- Zeit-Exit ausschliesslich am Close der Exit-Bar entry+N.
- Rechts-Zensierung (E2): ueberlebt ein Trade das Datenende ohne Stop und
  ohne erreichten Horizont -> RECHTS_ZENSIERT, r = NaN, strikt isoliert.
- RAW-Kantenreferenz strikt kausal aus U_hist/L_hist (D4, kein Lookahead,
  KEINE_KANTE bei fehlender Kante, kein Kreuz-Fallback).
- F5-Volumen strikt kausal: tick_volume >= 1.5 * SMA20(tick_volume).shift(1).

Ausgabe (Phase 1 = Text-Export only, §2.14-B3): Console + ``.txt``-Report +
maschinenlesbarer Trade-Block (``.tsv``) unter ``reports/setup_c/``.
Aufruf (Projekt-Root, Namespace-Package ohne __init__.py):
    python -m scripts.setup_c_profil --fenster=AUG|S1|S2|ALLE [--ohne-suppression]
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from scripts.market_segmentation import (
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)

__all__ = [
    "TrendConfig",
    "SetupCSignal",
    "KernelTrade",
    "AggBlock",
    "bericht_fenster",
    "main",
]

# =============================================================================
# 1) FENSTER & KONFIGURATION (Datenvertrag)
# =============================================================================

# Referenzfenster (start, ende) - Ende exklusiv (load_data-Konvention)
FENSTER_DEFS: Dict[str, Tuple[str, str]] = {
    "AUG": ("2026-08-10", "2026-08-28"),
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

ArmName = Literal["RAW", "CONFIRMED", "RETEST"]
DirName = Literal["up", "down"]
RawCluster = Literal["CLUSTER_A_ENG", "CLUSTER_B_WEIT", "NICHT_RAW"]
ExitGrund = Literal[
    "INITIAL_SL_INTRABAR",  # F4-Stop intrabar (Vorrang vor Zeit-Exit)
    "ZEIT_EXIT_CLOSE",      # Horizont N erreicht, Close der Exit-Bar e+N
    "RECHTS_ZENSIERT",      # E2: bis Datenende ueberlebt, Horizont nicht abgelaufen
]
SignalStatus = Literal[
    "SIGNAL",
    "VERWORFEN_STOP_VERLETZT",
    "TIMEOUT",
    "KEIN_CLOSE_SCHUTZ",
    "KEIN_VOLUMEN",
    "KEIN_DURCHSTOSS",
    "KEINE_KANTE",
    "DATEN_ENDE",
]


@dataclass(frozen=True, slots=True)
class TrendConfig:
    """Phase-1-Konfiguration fuer Setup C (verbindlicher Datenvertrag).

    Defaults = arretierte Beschluesse (§2.13-C, F4-F8, E1-E3/E5-KEIN_TRAILING,
    Whipsaw-F3). Aenderungen nur als dokumentierte Sensitivitaeten.

    Attributes:
        fenster: Referenzfenster (AUG|S1|S2), bestimmt start/ende via
            ``FENSTER_DEFS``.
        symbol: Symbol (fest SILVER wie Baseline).
        timeframe: Timeframe (fest M15 wie Baseline).
        db_path: DuckDB-Datei (Default = zentrale Produktions-DB).
        suppression_phasenlokal: Phasenlokale Open-Position-Suppression
            (Produktion Pflicht; Key = (phase, dir), F3). ``False`` =
            L2-Referenzmodus fuer das §2.14-Gate.
        cluster_a_max_vorlauf: RAW-Cluster-A-Schwelle (Vorlauf <= 1 Bar vor
            dem 2-Close-Bruch), E3.
        zeit_horizonte: Terminale Zeit-Exit-Horizonte (Close e+N), E1;
            Phase-1-Betrieb 48/96.
        stop_puffer: F4-Puffer unter Struktur/Kante (USD), F4.
        raw_vol_mult: F5-Volumen-Multiplikator (1.5x SMA20).
        sma_vol_period: F5-SMA-Periode (20).
        retest_band: Retest-Kontaktband um die gebrochene Kante (USD), F6.
        retest_timeout_bars: Retest-Guetigkeit nach dem 2-Close-Bruch, F7.
        sl_pct_ref: 0,45 %-Referenz-SL (ausschliesslich r_ref-Messung).
        segment: Segmentierungs-Konfiguration (Defaults = Baseline exakt);
            start/ende/db_path werden je Fenster ueberschrieben.
        report_dir: Ausgabeordner (Phase 1 = Text-Export only).
    """

    fenster: Literal["AUG", "S1", "S2"] = "AUG"
    symbol: str = "SILVER"
    timeframe: Literal["M15"] = "M15"
    db_path: Path = (
        Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
    )

    # Produktions-Schutzschicht (Whipsaw-F3, §2.12/§2.13)
    suppression_phasenlokal: bool = True

    # E3: RAW-Cluster A (frische Ausbrueche an der Kante)
    cluster_a_max_vorlauf: int = 1

    # E1: terminale Zeit-Exit-Horizonte (Phase 1: 48 = S1/AUG, 96 = Trend)
    zeit_horizonte: Tuple[int, ...] = (48, 96)

    # F4: struktureller Stop (intrabar, Puffer USD)
    stop_puffer: float = 0.15
    # F5: Volumen-Basis RAW (strikt kausal, shift(1))
    raw_vol_mult: float = 1.5
    sma_vol_period: int = 20
    # F6/F7: Retest-Kontakt (nur L1-Population, nicht Phase-1-Produktion)
    retest_band: float = 0.15
    retest_timeout_bars: int = 16
    # 0,45 %-SL: reine r_ref-Messung (nie Produktions-Stop)
    sl_pct_ref: float = 0.45

    # Segmentierungs-Konfiguration (Baseline-Konstanten, unveraendert)
    segment: SegmentConfig = field(default_factory=SegmentConfig)

    # Phase 1 = Text-Export only (§2.14-B3)
    report_dir: Path = (
        Path(__file__).resolve().parent.parent / "reports" / "setup_c"
    )


@dataclass(slots=True)
class SetupCSignal:
    """Erfasstes Signal eines Arms (F4-F8, D4) - Zwischenstand vor Simulation.

    Populationen (L1) zaehlen SIGNAL mit gueltigem SL; RAW-Signale tragen
    ``vorlauf_bars`` fuer die Cluster-A/B-Trennung (E3).
    """

    arm: ArmName
    phase: int
    dir: DirName
    kante: float
    brk_idx: int
    trigger_idx: int
    entry_idx: int
    entry_ts: Optional[pd.Timestamp]
    entry_preis: float
    stop_level: float
    sl_usd: float
    vorlauf_bars: Optional[int]
    vol_bestaetigt: Optional[bool]
    status: SignalStatus


@dataclass(slots=True)
class KernelTrade:
    """Simulierter Phase-1-Trade (RAW-A, F4 + Zeit-Exit, KEIN_TRAILING).

    RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2), exit_* dokumentiert das Datenende.
    """

    phase: int
    dir: DirName
    horizont_bars: int
    entry_idx: int
    entry_ts: pd.Timestamp
    entry_preis: float
    f4_initial_stop: float
    sl_usd: float
    exit_idx: int
    exit_ts: pd.Timestamp
    exit_preis: float
    exit_grund: ExitGrund
    haltezeit_bars: int
    r_f4: float
    r_ref: float


@dataclass(slots=True)
class AggBlock:
    """Aggregationsblock (E2: Zensierte strikt isoliert; kein dict)."""

    n_kandidaten: int = 0
    n_supprimiert: int = 0
    n_aktiv: int = 0
    n_zensiert: int = 0
    n_gewertet: int = 0
    sum_r_f4: float = 0.0
    sum_r_ref: float = 0.0
    mean_r_f4: float = float("nan")
    median_r_f4: float = float("nan")
    wr: float = float("nan")
    pf: float = float("inf")
    n_init: int = 0
    n_zeit: int = 0
    mean_offset: float = float("nan")


# =============================================================================
# 2) HILFSFUNKTIONEN (verbatim aus test/tmp_setup_c_audit.py, D1/D4/F5)
# =============================================================================


def _volumen_bestaetigt(
    df: pd.DataFrame, cfg: TrendConfig
) -> Tuple[np.ndarray, np.ndarray]:
    """F5-Volumenbedingung strikt kausal (keine Selbstinklusion).

    Args:
        df: OHLCV-DataFrame (tick_volume vorhanden).
        cfg: TrendConfig (raw_vol_mult, sma_vol_period).

    Returns:
        (bool-Array Bedingung, float-Array 1.5*SMA20(shift1)).
    """
    tv: np.ndarray = df["tick_volume"].values.astype(float)
    sma: np.ndarray = (
        pd.Series(tv)
        .rolling(cfg.sma_vol_period, min_periods=cfg.sma_vol_period)
        .mean()
        .shift(1)
        .values.astype(float)
    )
    ref: np.ndarray = cfg.raw_vol_mult * sma
    bed: np.ndarray = np.where(np.isnan(ref), False, tv >= ref)
    return bed, ref


def _kanten_reihe(
    ts_arr: np.ndarray,
    hist: Sequence[Tuple[pd.Timestamp, float]],
    fallback: float,
) -> np.ndarray:
    """Zeitlich gueltige Kante je Zeitstempel (D1/D4, Stufenfunktion).

    Args:
        ts_arr: datetime64-Array der Ziel-Zeitstempel (us ODER ns; wird fuer
            den searchsorted-Vergleich einheiten-bereinigt auf ns normiert).
        hist: U_hist/L_hist der Phase [(ts, value), ...] - aufsteigend.
        fallback: Kante, falls hist vor dem Zielzeitpunkt noch leer ist.
            D4: strikt der erste hist-Wert der EIGENEN Scan-Richtung
            (nie U_final/L_final, nie die gegenueberliegende Kante).

    Returns:
        Kantenwerte je Zeitstempel.
    """
    if not hist:
        return np.full(len(ts_arr), fallback, dtype=float)
    hist_ts = np.array([t.value for t, _ in hist], dtype="int64")
    hist_val = np.array([v for _, v in hist], dtype=float)
    # Einheiten-Bereinigung D4-Ratchet: hist_ts liegt in ns
    # (pd.Timestamp.value), ts_arr aus df["ts"].values kann datetime64[us]
    # sein (DuckDB/pandas >= 2.x) -> ohne Normalisierung auf ns wuerde
    # searchsorted alle Positionen auf -1 stellen (statische Kante = erster
    # hist-Wert statt zeitlich gueltiger Ratchet-Stufenfunktion).
    ts_ns = ts_arr.astype("datetime64[ns]").astype("int64")
    pos = np.searchsorted(hist_ts, ts_ns, side="right") - 1
    out = np.where(pos >= 0, hist_val[np.clip(pos, 0, len(hist_val) - 1)], fallback)
    return out.astype(float)


def _phase_start_idx(df: pd.DataFrame, start_ts: pd.Timestamp) -> int:
    """df-Index des Phasenstart-Zeitstempels (idx-Spalte vorhanden).

    Args:
        df: OHLCV-DataFrame (ts, idx).
        start_ts: Phasenstart-Zeitstempel (``p.start``).

    Returns:
        Zeilen-Index des Phasenbeginns in df.
    """
    ts_val: np.datetime64 = np.datetime64(start_ts)
    pos: int = int(np.searchsorted(df["ts"].values, ts_val, side="left"))
    return int(df["idx"].iloc[pos])


def _stop_f4(
    df: pd.DataFrame,
    lo_struktur_idx: int,
    hi_struktur_idx: int,
    kante: float,
    dir: DirName,
    cfg: TrendConfig,
) -> float:
    """Struktureller F4-Stop aus Kerzenstruktur und Kante.

    Args:
        df: OHLCV-DataFrame.
        lo_struktur_idx: erste Struktur-Bar (niedriger Index).
        hi_struktur_idx: zweite Struktur-Bar (Arm 2: brk_idx+1).
        kante: Referenzkante.
        dir: Signalrichtung.
        cfg: TrendConfig (stop_puffer).

    Returns:
        Stop-Level (Preis).
    """
    if dir == "up":
        struktur = float(
            np.min(df["low"].values[lo_struktur_idx : hi_struktur_idx + 1])
        )
        return min(struktur, kante) - cfg.stop_puffer
    struktur = float(
        np.max(df["high"].values[lo_struktur_idx : hi_struktur_idx + 1])
    )
    return max(struktur, kante) + cfg.stop_puffer


# =============================================================================
# 3) SIGNAL-ERFASSUNG (drei Arme; verbatim Logik, L1-Populationen)
# =============================================================================


def _erfasse_confirmed(
    df: pd.DataFrame, p: PhaseData, nr: int, cfg: TrendConfig
) -> SetupCSignal:
    """Arm 2: BREAKOUT_CONFIRMED - Einstieg open[brk_idx+2] (F2/F4).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (echter 2-Close-Bruch).
        nr: Phasennummer (1-basiert).
        cfg: TrendConfig.

    Returns:
        SetupCSignal (SIGNAL oder DATEN_ENDE).
    """
    assert p.brk_idx is not None and p.break_dir is not None
    assert p.brk_kante is not None
    b: int = int(p.brk_idx)
    n: int = len(df)
    s = SetupCSignal(
        arm="CONFIRMED", phase=nr, dir=p.break_dir,
        kante=float(p.brk_kante), brk_idx=b, trigger_idx=b, entry_idx=-1,
        entry_ts=None, entry_preis=float("nan"),
        stop_level=float("nan"), sl_usd=float("nan"),
        vorlauf_bars=None, vol_bestaetigt=None, status="SIGNAL",
    )
    if b + 2 >= n:
        s.status = "DATEN_ENDE"
        return s
    s.entry_idx = b + 2
    s.entry_ts = df["ts"].iloc[b + 2]
    s.stop_level = _stop_f4(df, b, b + 1, s.kante, s.dir, cfg)
    s.entry_preis = float(df["open"].values[b + 2])
    if s.dir == "up":
        s.sl_usd = s.entry_preis - s.stop_level
    else:
        s.sl_usd = s.stop_level - s.entry_preis
    return s


def _erfasse_raw(
    df: pd.DataFrame,
    p: PhaseData,
    nr: int,
    cfg: TrendConfig,
    vol_bed: np.ndarray,
    min_phase_candles: int,
) -> List[SetupCSignal]:
    """Arm 1: BREAKOUT_RAW - Volumen-Durchstoss VOR dem 2-Close-Bruch (F5/F4).

    Scannt [Phasenstart+MIN_PHASE_CANDLES, brk_idx] nach dem ersten
    Kanten-Durchstoss (high >= obere / low <= untere Kante) mit F5-Volumen.
    Beide Richtungen unabhaengig (D4: Kante strikt kausal aus U_hist/L_hist;
    Scan erst ab dem ersten hist-Eintrag der Richtung; leere hist =
    KEINE_KANTE, kein Kreuz-Fallback). Status-Kategorien inkl. Diagnose
    (KEINE_KANTE, KEIN_DURCHSTOSS, KEIN_VOLUMEN, DATEN_ENDE) - identisch zur
    Audit-Referenz ``tmp_setup_c_audit.erfasse_raw``.

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt.
        nr: Phasennummer (1-basiert).
        cfg: TrendConfig.
        vol_bed: bool-Array F5-Bedingung ueber ganz df.
        min_phase_candles: SegmentConfig.min_phase_candles (Scan-Untergrenze).

    Returns:
        Liste mit 0..2 SetupCSignal-Objekten.
    """
    assert p.brk_idx is not None and p.break_dir is not None
    n: int = len(df)
    b: int = int(p.brk_idx)
    start_idx: int = _phase_start_idx(df, p.start)
    scan_lo: int = start_idx + min_phase_candles
    scan_hi: int = b  # inklusive Bruchbar
    ergebnis: List[SetupCSignal] = []

    def _leer(status: SignalStatus, dir: DirName, kante: float) -> SetupCSignal:
        return SetupCSignal(
            arm="RAW", phase=nr, dir=dir, kante=kante,
            brk_idx=b, trigger_idx=-1, entry_idx=-1,
            entry_ts=None, entry_preis=float("nan"),
            stop_level=float("nan"), sl_usd=float("nan"),
            vorlauf_bars=None, vol_bestaetigt=None, status=status,
        )

    if scan_lo > scan_hi:
        # Phase zu kurz fuer einen Scan -> ein Signal in Bruchrichtung
        return [_leer("KEIN_DURCHSTOSS", p.break_dir, float(p.brk_kante))]

    for dir in ("up", "down"):
        hist: Sequence[Tuple[pd.Timestamp, float]] = (
            list(p.U_hist) if dir == "up" else list(p.L_hist)
        )
        if not hist:
            ergebnis.append(_leer("KEINE_KANTE", dir, float("nan")))
            continue
        erster_hist_idx: int = int(
            np.searchsorted(
                df["ts"].values, np.datetime64(hist[0][0]), side="left"
            )
        )
        scan_lo_dir: int = max(scan_lo, erster_hist_idx)
        if scan_lo_dir > scan_hi:
            ergebnis.append(_leer("KEIN_DURCHSTOSS", dir, float("nan")))
            continue
        rng_dir: np.ndarray = np.arange(scan_lo_dir, scan_hi + 1)
        ts_rng_dir: np.ndarray = df["ts"].values[rng_dir]
        kante_r: np.ndarray = _kanten_reihe(
            ts_rng_dir, hist, float(hist[0][1])
        )
        if dir == "up":
            durchstoss: np.ndarray = df["high"].values[rng_dir] >= kante_r
        else:
            durchstoss = df["low"].values[rng_dir] <= kante_r
        treffer: np.ndarray = durchstoss & vol_bed[rng_dir]
        erste: Optional[int] = None
        if treffer.any():
            erste = scan_lo_dir + int(np.flatnonzero(treffer)[0])
        s = SetupCSignal(
            arm="RAW", phase=nr, dir=dir,
            kante=float(kante_r[erste - scan_lo_dir])
            if erste is not None
            else float(hist[0][1]),
            brk_idx=b, trigger_idx=erste if erste is not None else -1,
            entry_idx=-1, entry_ts=None, entry_preis=float("nan"),
            stop_level=float("nan"), sl_usd=float("nan"),
            vorlauf_bars=None, vol_bestaetigt=None, status="SIGNAL",
        )
        if erste is None:
            s.status = "KEIN_VOLUMEN" if durchstoss.any() else "KEIN_DURCHSTOSS"
            s.vol_bestaetigt = False
            ergebnis.append(s)
            continue
        s.entry_idx = erste + 1
        if s.entry_idx >= n:
            s.status = "DATEN_ENDE"
            ergebnis.append(s)
            continue
        s.entry_ts = df["ts"].iloc[s.entry_idx]
        s.vorlauf_bars = b - erste
        s.vol_bestaetigt = True
        s.stop_level = _stop_f4(
            df, erste, erste, float(kante_r[erste - scan_lo_dir]), dir, cfg
        )
        s.entry_preis = float(df["open"].values[s.entry_idx])
        if dir == "up":
            s.sl_usd = s.entry_preis - s.stop_level
        else:
            s.sl_usd = s.stop_level - s.entry_preis
        ergebnis.append(s)
    return ergebnis


def _erfasse_retest(
    df: pd.DataFrame, p: PhaseData, nr: int, cfg: TrendConfig
) -> SetupCSignal:
    """Arm 3: RETEST_OUTSIDE - Pullback an die gebrochene Kante (F6/F7/F8).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt.
        nr: Phasennummer.
        cfg: TrendConfig.

    Returns:
        SetupCSignal (SIGNAL oder Status-Kategorie).
    """
    assert p.brk_idx is not None and p.break_dir is not None
    assert p.brk_kante is not None
    n: int = len(df)
    b: int = int(p.brk_idx)
    up: bool = p.break_dir == "up"
    kante: float = float(p.brk_kante)
    lo: int = b + 1
    hi: int = min(b + cfg.retest_timeout_bars, n - 2)  # k+1 muss existieren
    s = SetupCSignal(
        arm="RETEST", phase=nr, dir=p.break_dir,
        kante=kante, brk_idx=b, trigger_idx=-1, entry_idx=-1,
        entry_ts=None, entry_preis=float("nan"),
        stop_level=float("nan"), sl_usd=float("nan"),
        vorlauf_bars=None, vol_bestaetigt=None, status="SIGNAL",
    )
    if hi < lo:
        s.status = "DATEN_ENDE"
        return s
    stop: float = _stop_f4(df, b, b + 1, kante, s.dir, cfg)
    s.stop_level = stop
    high: np.ndarray = df["high"].values
    low: np.ndarray = df["low"].values
    close: np.ndarray = df["close"].values
    if up:
        run_min: np.ndarray = np.minimum.accumulate(low[lo : hi + 1])
        verletzt: np.ndarray = run_min < stop
        kontakt: np.ndarray = (low[lo : hi + 1] >= kante - cfg.retest_band) & (
            low[lo : hi + 1] <= kante + cfg.retest_band
        )
        verteidigt: np.ndarray = close[lo : hi + 1] > kante
    else:
        run_max: np.ndarray = np.maximum.accumulate(high[lo : hi + 1])
        verletzt = run_max > stop
        kontakt = (high[lo : hi + 1] >= kante - cfg.retest_band) & (
            high[lo : hi + 1] <= kante + cfg.retest_band
        )
        verteidigt = close[lo : hi + 1] < kante
    kandidaten: np.ndarray = kontakt & verteidigt
    hatte_kontakt: bool = bool(kontakt.any())
    if kandidaten.any():
        erste_k: int = lo + int(np.flatnonzero(kandidaten)[0])
        rel: int = erste_k - lo
        if verletzt[rel]:
            s.status = "VERWORFEN_STOP_VERLETZT"
            return s
        s.trigger_idx = erste_k
        s.entry_idx = erste_k + 1
        s.entry_ts = df["ts"].iloc[s.entry_idx]
        s.entry_preis = float(df["open"].values[s.entry_idx])
        if up:
            s.sl_usd = s.entry_preis - stop
        else:
            s.sl_usd = stop - s.entry_preis
        return s
    if hatte_kontakt:
        s.status = "KEIN_CLOSE_SCHUTZ"
        return s
    s.status = "VERWORFEN_STOP_VERLETZT" if bool(verletzt.any()) else "TIMEOUT"
    return s


def _erfasse_signale(
    sr: SegmentResult, cfg: TrendConfig
) -> List[SetupCSignal]:
    """Erfasst alle Signale eines Fensters ueber die drei Arme (L1).

    Args:
        sr: SegmentResult aus market_segmentation.segmentiere_markt.
        cfg: TrendConfig.

    Returns:
        Alle SetupCSignal-Objekte je echter 2-Close-Bruch-Phase.
    """
    df: pd.DataFrame = sr.df
    vol_bed, _ = _volumen_bestaetigt(df, cfg)
    min_phase_candles: int = cfg.segment.min_phase_candles
    echte: List[PhaseData] = [
        p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    ]
    alle: List[SetupCSignal] = []
    for nr, p in enumerate(echte, start=1):
        alle.append(_erfasse_confirmed(df, p, nr, cfg))
        alle.extend(_erfasse_raw(df, p, nr, cfg, vol_bed, min_phase_candles))
        alle.append(_erfasse_retest(df, p, nr, cfg))
    return alle


def _population(
    signale: Sequence[SetupCSignal], arm: ArmName
) -> List[SetupCSignal]:
    """SIGNAL-Population eines Arms (entry_idx >= 0, sl_usd endlich > 0).

    Args:
        signale: Alle erfassten Signale.
        arm: Armname.

    Returns:
        Gueltige SIGNAL-Signale des Arms.
    """
    return [
        s
        for s in signale
        if s.arm == arm and s.status == "SIGNAL" and s.entry_idx >= 0
        and np.isfinite(s.sl_usd) and s.sl_usd > 0.0
    ]


# =============================================================================
# 4) SIMULATIONSKERN (Phase 1: F4 intrabar + terminaler Zeit-Exit, KEIN_TRAILING)
# =============================================================================


def _simuliere_kern(
    df: pd.DataFrame,
    sig: SetupCSignal,
    cfg: TrendConfig,
    horizont: int,
) -> KernelTrade:
    """Simuliert ein RAW-A-Signal unter F4 + Zeit-Exit (E1/E2/E5-KT).

    Bar fuer Bar ab Einstieg bis min(entry+N, Datenende). Reihenfolge je Bar:
      1) F4-Stop intrabar - VORRANG vor dem Zeit-Exit (Mentor-Urteil).
      2) Zeit-Exit am Close, sobald k == entry_idx + N.
    Ueberlebt der Trade das Datenende ohne Stop und ohne erreichten Horizont
    (entry+N > n-1), gilt er als RECHTS_ZENSIERT (E2, r = NaN).

    Args:
        df: OHLCV-DataFrame.
        sig: SetupCSignal (SIGNAL, sl_usd > 0).
        cfg: TrendConfig.
        horizont: Zeit-Horizont N in Bars (48/96).

    Returns:
        KernelTrade.
    """
    n: int = len(df)
    e: int = int(sig.entry_idx)
    up: bool = sig.dir == "up"
    entry: float = float(df["open"].values[e])
    f4_stop: float = float(sig.stop_level)
    sl_usd: float = float(sig.sl_usd)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)

    ziel_bar: int = e + horizont
    letzte_bar: int = n - 1
    loop_ende: int = min(ziel_bar, letzte_bar)

    exit_grund: ExitGrund = "RECHTS_ZENSIERT"  # Default, falls Loop ohne Break
    exit_idx: int = letzte_bar
    exit_preis: float = float(close[letzte_bar])

    for k in range(e, loop_ende + 1):
        # 1) F4-Initial-Stop intrabar (Vorrang vor Zeit-Exit)
        if (up and low[k] <= f4_stop) or ((not up) and high[k] >= f4_stop):
            exit_preis, exit_idx, exit_grund = float(f4_stop), k, "INITIAL_SL_INTRABAR"
            break
        # 2) Terminaler Zeit-Exit am Close der Exit-Bar
        if k == ziel_bar:
            exit_preis, exit_idx, exit_grund = float(close[k]), k, "ZEIT_EXIT_CLOSE"
            break

    haltezeit: int = exit_idx - e
    zensiert: bool = exit_grund == "RECHTS_ZENSIERT"
    if zensiert:
        r_f4: float = float("nan")
        r_ref: float = float("nan")
    else:
        if up:
            r_f4 = (exit_preis - entry) / sl_usd
        else:
            r_f4 = (entry - exit_preis) / sl_usd
        r_ref_base: float = entry * cfg.sl_pct_ref / 100.0
        r_ref = (
            (exit_preis - entry) / r_ref_base
            if up
            else (entry - exit_preis) / r_ref_base
        )

    return KernelTrade(
        phase=sig.phase, dir=sig.dir, horizont_bars=horizont,
        entry_idx=e, entry_ts=df["ts"].iloc[e], entry_preis=entry,
        f4_initial_stop=f4_stop, sl_usd=sl_usd,
        exit_idx=exit_idx, exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=float(exit_preis), exit_grund=exit_grund,
        haltezeit_bars=haltezeit, r_f4=float(r_f4), r_ref=float(r_ref),
    )


def _kern_lauefe(
    df: pd.DataFrame,
    signale: Sequence[SetupCSignal],
    cfg: TrendConfig,
    horizont: int,
) -> Tuple[List[KernelTrade], int]:
    """RAW-A-Produktionslauf (E3 + F3-Suppression, Key = (phase, dir)).

    Kandidaten = RAW-Signale mit vorlauf <= ``cluster_a_max_vorlauf``
    (Cluster A). Suppression (F3, §2.12/§2.13-C: "aktiver Trade in DERSELBEN
    Richtung derselben Phase"): Ein Kandidat wird nur dann verworfen, wenn in
    derselben (phase, dir) eine fruehere RAW-A-Position noch offen ist
    (entry_idx <= exit_idx). Da ``_erfasse_raw`` je (Phase, Richtung) maximal
    EIN Signal liefert, ist die Suppression fuer RAW-A ein No-op
    (n_supprimiert = 0) und die Produktion reproduziert die arretierte
    L2-Referenz bitgenau. Kein Cross-Richtungs-Eingriff (up/down derselben
    Phase sind unabhaengige, gleichzeitig handelbare Setups).

    Args:
        df: OHLCV-DataFrame.
        signale: Alle erfassten Signale.
        cfg: TrendConfig.
        horizont: Zeit-Horizont N in Bars.

    Returns:
        (aktivierte KernelTrades, n_supprimiert).
    """
    kandidaten: List[SetupCSignal] = [
        s
        for s in signale
        if s.arm == "RAW" and s.status == "SIGNAL" and s.entry_idx >= 0
        and np.isfinite(s.sl_usd) and s.sl_usd > 0.0
        and s.vorlauf_bars is not None
        and s.vorlauf_bars <= cfg.cluster_a_max_vorlauf
    ]
    kandidaten.sort(key=lambda s: (s.phase, s.dir, s.entry_idx))

    trades: List[KernelTrade] = []
    if not cfg.suppression_phasenlokal:
        for sig in kandidaten:
            trades.append(_simuliere_kern(df, sig, cfg, horizont))
        return trades, 0

    n_supprimiert: int = 0
    # F3: Key = (Phase, Richtung) - explizit typisiert (kein implizites dict)
    offen_bis: Dict[Tuple[int, DirName], int] = {}
    for sig in kandidaten:
        key: Tuple[int, DirName] = (sig.phase, sig.dir)
        if sig.entry_idx <= offen_bis.get(key, -1):
            n_supprimiert += 1
            continue
        trade: KernelTrade = _simuliere_kern(df, sig, cfg, horizont)
        trades.append(trade)
        offen_bis[key] = int(trade.exit_idx)
    return trades, n_supprimiert


# =============================================================================
# 5) AGGREGATION (E2: Zensierte strikt isoliert)
# =============================================================================


def _agg_block(trades: Sequence[KernelTrade], n_supprimiert: int = 0) -> AggBlock:
    """Aggregiert KernelTrades (Zensierte strikt aus Performance isoliert).

    Args:
        trades: Aktivierte KernelTrades eines Laufs.
        n_supprimiert: Durch F3-Suppression verworfen (Diagnose).

    Returns:
        AggBlock.
    """
    agg: AggBlock = AggBlock(
        n_kandidaten=len(trades) + n_supprimiert,
        n_supprimiert=n_supprimiert,
        n_aktiv=len(trades),
    )
    if not trades:
        return agg
    rs: List[float] = []
    offsets: List[int] = []
    for r in trades:
        if r.exit_grund == "RECHTS_ZENSIERT":
            agg.n_zensiert += 1
            continue
        if r.exit_grund == "INITIAL_SL_INTRABAR":
            agg.n_init += 1
        else:
            agg.n_zeit += 1
        rs.append(float(r.r_f4))
        agg.sum_r_ref += float(r.r_ref)
        offsets.append(r.haltezeit_bars)
    n_gew: int = len(rs)
    agg.n_gewertet = n_gew
    if not n_gew:
        return agg
    arr: np.ndarray = np.array(rs, dtype=float)
    agg.sum_r_f4 = float(arr.sum())
    agg.mean_r_f4 = float(arr.mean())
    agg.median_r_f4 = float(np.median(arr))
    agg.wr = float(np.mean(arr > 0.0) * 100.0)
    pos: float = float(arr[arr > 0.0].sum())
    neg: float = float(-arr[arr < 0.0].sum())
    agg.pf = pos / neg if neg > 0.0 else float("inf")
    agg.mean_offset = float(np.mean(offsets)) if offsets else float("nan")
    return agg


def _fmt(v: object, fmt: str = ".2f") -> str:
    """Formatiert Zahlen (NaN/None -> '-').

    Args:
        v: Wert.
        fmt: Format-String.

    Returns:
        Formatierter String.
    """
    if v is None:
        return "-"
    if isinstance(v, (float, np.floating)) and not np.isfinite(float(v)):
        return "-"
    return f"{v:{fmt}}"


# =============================================================================
# 6) REPORT (Text + maschinenlesbarer Trade-Block, reports/setup_c/)
# =============================================================================


def _block_text(titel: str, agg: AggBlock) -> List[str]:
    """Formatiert einen Aggregationsblock fuer eine Gruppe.

    Args:
        titel: Blocktitel.
        agg: Aggregationsergebnis.

    Returns:
        Textzeilen.
    """
    t = (
        f"{titel}  (n={agg.n_kandidaten}, supprimiert={agg.n_supprimiert}, "
        f"aktiv={agg.n_aktiv}, zensiert={agg.n_zensiert}, gewertet={agg.n_gewertet})"
    )
    lines: List[str] = [t, "  " + "-" * max(2, len(t) - 2)]
    if not agg.n_gewertet:
        lines.append("  (keine gewerteten Trades - nur RECHTS_ZENSIERT)")
        return lines
    lines.append(
        f"  sum r_f4={agg.sum_r_f4:>9.2f}  mean r_f4={_fmt(agg.mean_r_f4):>7}  "
        f"median={_fmt(agg.median_r_f4):>7}  WR={_fmt(agg.wr, '.1f')}%  "
        f"PF={_fmt(agg.pf)}"
    )
    lines.append(f"  sum r_ref (0.45%-Basis) = {agg.sum_r_ref:.2f}")
    lines.append(
        f"  Exit: INITIAL_SL_INTRABAR={agg.n_init} | ZEIT_EXIT_CLOSE={agg.n_zeit} "
        f"| RECHTS_ZENSIERT={agg.n_zensiert}"
    )
    lines.append(f"  mittl. Haltedauer (gewertet) = {_fmt(agg.mean_offset, '.0f')} Bars")
    return lines


def _trade_block_tsv(
    trades: Sequence[KernelTrade], fenster: str, cfg: TrendConfig
) -> str:
    """Maschinenlesbarer Trade-Block (TSV) je Fenster ueber alle Horizonte.

    Args:
        trades: Aktivierte RAW-A-KernelTrades (alle Horizonte).
        fenster: Fenster-Label.
        cfg: TrendConfig (fuer Metadatenzeilen).

    Returns:
        TSV-Text (Kommentarzeilen + Header + Datenzeilen).
    """
    kopf: List[str] = [
        f"# setup_c Phase-1-Kern (RAW-A + F4 intrabar + Zeit-Exit) - Fenster: {fenster}",
        f"# suppression_phasenlokal: {cfg.suppression_phasenlokal} | "
        f"cluster_a_max_vorlauf: {cfg.cluster_a_max_vorlauf} | "
        f"stop_puffer: {cfg.stop_puffer} | sl_pct_ref: {cfg.sl_pct_ref}",
        "# RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2, strikt isoliert)",
    ]
    header: str = (
        "horizont\tphase\tdir\tentry_idx\tentry_ts\tentry_preis\t"
        "f4_initial_stop\tsl_usd\texit_idx\texit_ts\texit_preis\t"
        "exit_grund\thaltezeit_bars\tr_f4\tr_ref"
    )
    zeilen: List[str] = [*kopf, header]
    for t in sorted(trades, key=lambda x: (x.horizont_bars, x.phase, x.entry_idx)):
        zeilen.append(
            f"{t.horizont_bars}\t{t.phase}\t{t.dir}\t{t.entry_idx}\t"
            f"{t.entry_ts}\t{t.entry_preis:.5f}\t{t.f4_initial_stop:.5f}\t"
            f"{t.sl_usd:.5f}\t{t.exit_idx}\t{t.exit_ts}\t{t.exit_preis:.5f}\t"
            f"{t.exit_grund}\t{t.haltezeit_bars}\t{_fmt(t.r_f4)}\t{_fmt(t.r_ref)}"
        )
    return "\n".join(zeilen)


def bericht_fenster(fenster: str, cfg: TrendConfig) -> str:
    """Baut den Phase-1-Report fuer ein Fenster (L1 + L2, Text + TSV).

    Args:
        fenster: AUG | S1 | S2.
        cfg: TrendConfig.

    Returns:
        Reporttext (wird zusaetzlich nach reports/setup_c/ geschrieben).
    """
    start, ende = FENSTER_DEFS[fenster]
    seg_cfg: SegmentConfig = replace(
        cfg.segment, db_path=cfg.db_path, start=start, ende=ende
    )
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)
    signale: List[SetupCSignal] = _erfasse_signale(sr, cfg)

    # --- L1: Pipeline-Anker (Populationen) ----------------------------------
    n_f3: int = sum(
        1 for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    )
    pop_conf: int = len(_population(signale, "CONFIRMED"))
    pop_raw: List[SetupCSignal] = _population(signale, "RAW")
    pop_a: int = sum(
        1
        for s in pop_raw
        if s.vorlauf_bars is not None and s.vorlauf_bars <= cfg.cluster_a_max_vorlauf
    )
    pop_b: int = len(pop_raw) - pop_a
    pop_retest: int = len(_population(signale, "RETEST"))

    # --- L2: RAW-A-Kern je Horizont ------------------------------------------
    laeufe: Dict[int, Tuple[List[KernelTrade], int]] = {}
    for horizont in cfg.zeit_horizonte:
        laeufe[horizont] = _kern_lauefe(df, signale, cfg, horizont)

    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - PHASE-1-PRODUKTIONSKERN (setup_c_profil.py)",
        f"Fenster: {fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | "
        f"Segmente: {len(sr.phases)} | F3-Brueche: {n_f3}",
        f"Kern: RAW-A (Vorlauf<={cfg.cluster_a_max_vorlauf}) + F4 intrabar "
        f"(Puffer {cfg.stop_puffer}) + Zeit-Exit {cfg.zeit_horizonte} + "
        f"Suppression={cfg.suppression_phasenlokal} | r_ref: 0.45%-SL",
        linie,
        "",
        "L1 PIPELINE-ANKER (Populationen, SIGNAL & sl_usd>0):",
        f"  F3-Brueche      : {n_f3}",
        f"  CONFIRMED       : {pop_conf}",
        f"  RAW gesamt      : {len(pop_raw)}  (CLUSTER_A={pop_a}, CLUSTER_B={pop_b})",
        f"  RETEST          : {pop_retest}",
        "",
    ]

    for horizont in cfg.zeit_horizonte:
        trades, n_supp = laeufe[horizont]
        agg = _agg_block(trades, n_supp)
        txt.append(linie)
        txt.append(
            f"L2 RAW-CLUSTER A  |  Horizont N = {horizont}  "
            f"(Close der Bar entry+{horizont})"
        )
        txt.extend(_block_text("    RAW-CLUSTER-A", agg))
        txt.append("")

    # Referenzzeile (Suppression aus = §2.14-L2-Sollwerte)
    if cfg.suppression_phasenlokal:
        cfg_ref: TrendConfig = replace(cfg, suppression_phasenlokal=False)
        txt.append(linie)
        txt.append("L2-REFERENZ (suppression_phasenlokal=False = §2.14-Sollwerte):")
        for horizont in cfg_ref.zeit_horizonte:
            trades_ref, n_supp_ref = _kern_lauefe(df, signale, cfg_ref, horizont)
            agg_ref = _agg_block(trades_ref, n_supp_ref)
            txt.extend(_block_text(f"    N={horizont}", agg_ref))
        txt.append("")

    txt.append(linie)
    txt.append("VERIFIKATIONSANKER (erwartet, §2.14 nach Einheiten-Bereinigung D4-Ratchet):")
    txt.append(
        f"  L1: AUG 11/11/10(2/8)/3 | S1 138/138/105(38/67)/59 | "
        f"S2 61/61/76(3/73)/18  ->  aktuelles Fenster {fenster}: "
        f"{n_f3}/{pop_conf}/{len(pop_raw)}({pop_a}/{pop_b})/{pop_retest}"
    )
    txt.append(linie)

    # --- Export (Text + TSV) --------------------------------------------------
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    out_txt: Path = cfg.report_dir / f"setup_c_{fenster}.txt"
    out_txt.write_text("\n".join(txt), encoding="utf-8")
    alle_trades: List[KernelTrade] = []
    for horizont in cfg.zeit_horizonte:
        alle_trades.extend(laeufe[horizont][0])
    out_tsv: Path = cfg.report_dir / f"setup_c_trades_{fenster}.tsv"
    out_tsv.write_text(_trade_block_tsv(alle_trades, fenster, cfg), encoding="utf-8")
    return "\n".join(txt)


# =============================================================================
# 7) MAIN
# =============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den Phase-1-Report fuer Fenster aus.

    Args:
        argv: Kommandozeilen-Argumente (Default: sys.argv[1:]).

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    suppression: bool = True
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].upper()
        elif a == "--ohne-suppression":
            suppression = False
    if fenster == "ALLE":
        fenster_list: List[str] = ["AUG", "S1", "S2"]
    elif fenster in ("AUG", "S1", "S2"):
        fenster_list = [fenster]
    else:
        raise SystemExit(f"Unbekanntes Fenster: {fenster} (AUG|S1|S2|ALLE)")
    cfg = TrendConfig(suppression_phasenlokal=suppression)
    for f in fenster_list:
        text = bericht_fenster(f, cfg)
        print(text)
        print(f"\nReport geschrieben: {cfg.report_dir / f'setup_c_{f}.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
