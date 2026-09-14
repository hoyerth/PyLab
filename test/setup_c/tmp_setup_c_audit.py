"""
SETUP C - SCHRITT 2: RE-SEGMENTIERUNG & SIGNAL-REPLAY (test/tmp_setup_c_audit.py)
================================================================================
Status: Schritt-2-Audit (Replay) | Doku: docs/setup_c_experiment.md (F4-F8 arretiert)
Baseline: scripts/phasen_volumen_profil.py (v0.4.0-frozen) - Produktion UNVERAENDERT.
Arbeitsmodus: rein lesend (DuckDB read_only), keine Trade-Simulation, keine Charts
(gehoert zu Schritt 3), keine Produktions-Integration.

Zweck
-----
Erfasst fuer die drei Einstiegs-Arme (BREAKOUT_RAW, BREAKOUT_CONFIRMED,
RETEST_OUTSIDE) je echte 2-Close-Bruch-Phase (F3) den kausalen Einstiegspunkt,
den strukturellen Initial-Stop (F4) und misst die Folgebewegung in MFE/MAE ueber
die Fenster 12/24/48 M15-Bars (individuelle R-Basis = sl_usd; Referenzspalten in
0.45%-R zur Schritt-1-Kompatibilitaet).

Arretierte Beschluesse (Doku §2.4)
----------------------------------
F4  Struktureller Stop:  LONG  stop = min(low_struktur, kante) - 0.15 USD
                         SHORT stop = max(high_struktur, kante) + 0.15 USD
                         Arm 2: low_struktur = min(low[brk_idx], low[brk_idx+1])
                         Arm 1: low_struktur = low[trigger_idx]
                         0.45%-SL bleibt reine Referenzspalte.
F5  Volumen-Basis Arm 1: tick_volume[r] >= 1.5 * SMA20(tick_volume).shift(1)
                         (strikt kausal, keine Selbstinklusion; r<20 -> kein Trigger)
F6  Execution Arm 3:     Einstieg = open[k+1] nach Retest-Bestaetigungs-Close
                         (keine Limit-Order am Band; Sensitivitaet: close[k])
F7  Retest-Timeout:      k in (brk_idx, brk_idx + 16] M15-Bars
F8  Invalidierung:       Preis darf seit Bruch den F4-Stop nie unterschreiten;
                         verletzte Faelle als VERWORFEN_STOP_VERLETZT gezaehlt.

Methodik (bitgenaue Re-Segmentierung)
-------------------------------------
Die Phasen-Segmentierung wird NICHT neu implementiert, sondern als Quelltext-
Slice der eingefrorenen Arbeitskopie test/tmp_phasen_volumen_profil_symbol.py
(Zeilen vom `from __future__` bis unmittelbar vor Abschnitt 5) per exec in einem
frischen Namespace ausgefuehrt (identisch zum etablierten Schritt-1-Muster).
CLI-Overrides --start/--ende der Arbeitskopie steuern das Fenster.

D1 (Default): RAW-Kantenreferenz = zeitlich rekonstruierte Kante aus U_hist/L_hist
              (letzter Eintrag mit ts <= ts_r), sonst U_final/L_final.
D2 (Default): KEIN_CLOSE_SCHUTZ -> weitersuchen bis Timeout.
D3 (Praezi.): Status KEIN_DURCHSTOSS fuer RAW-Phasen ohne Kantenkontakt vor dem
              Bruch (Ergaenzung zur Status-Liste aus der Freigabe).
D4 (Review-Korrektur 05.09.): RAW-Kantenreferenz strikt kausal NUR aus
              U_hist/L_hist (hist-protokollierte Kante). U_final/L_final nutzen
              die Gesamt-Phasenhistorie (bis brk_idx) und sind fuer fruehere
              Bars Lookahead -> Scan erst ab dem ersten hist-Eintrag. Fehlt die
              Kante der Scan-Richtung: Status KEINE_KANTE (kein Fallback auf die
              gegenueberliegende Kante, der Phantom-Signale erzeugen wuerde).
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# ==============================================================================
# 1) KONFIGURATION & DATENVERTRAEGE
# ==============================================================================

TEST_DIR: Path = Path(__file__).resolve().parent
ARBEITSKOPIE: Path = TEST_DIR / "tmp_phasen_volumen_profil_symbol.py"

# Referenzfenster (start, ende) - Ende exklusiv (Baseline load_data-Konvention)
FENSTER_DEFS: Dict[str, Tuple[str, str]] = {
    "AUG": ("2026-08-10", "2026-08-28"),
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

# Baseline-Verankerung (Doku-Commit F4-F8; Arbeitskopie ist bitgenau zur frozen
# Baseline scripts/phasen_volumen_profil.py v0.4.0)
BASELINE_REF: str = "docs/setup_c_experiment.md c48c9c7 (F4-F8) + Baseline v0.4.0-frozen"

ArmName = Literal["RAW", "CONFIRMED", "RETEST"]
DirName = Literal["up", "down"]
AuditStatus = Literal[
    "SIGNAL",
    "VERWORFEN_STOP_VERLETZT",
    "TIMEOUT",
    "KEIN_CLOSE_SCHUTZ",
    "KEIN_VOLUMEN",
    "KEIN_DURCHSTOSS",
    "KEINE_KANTE",
    "DATEN_ENDE",
]

MESS_FENSTER: Tuple[int, ...] = (12, 24, 48)


@dataclass(frozen=True, slots=True)
class AuditConfig:
    """Konfiguration des Replay-Audits (Setup C Schritt 2, F4-F8)."""

    fenster: str = "AUG"
    symbol: str = "SILVER"
    timeframe: str = "M15"
    # F5: Volumen-Basis Arm 1 (Vor-Bar-SMA, strikt kausal)
    raw_vol_mult: float = 1.5
    sma_vol_period: int = 20
    # F6: Retest-Kontaktband um die gebrochene Kante (USD)
    retest_band: float = 0.15
    # F7: Retest-Gültigkeit nach dem 2-Close-Bruch (M15-Bars)
    retest_timeout_bars: int = 16
    # F4: Puffer unter Struktur/Kante (USD)
    stop_puffer: float = 0.15
    # Referenz-SL der Baseline (0.45 %) - nur Referenzspalte, Produktion unberuehrt
    sl_pct_ref: float = 0.45


@dataclass(slots=True)
class AuditSignal:
    """Ein erfasstes Signal/Audit-Ergebnis je (Phase, Arm, Richtung)."""

    arm: ArmName
    fenster: str
    phase: int                     # Phasen-Nummer (1-basiert, wie Bruch-Matrix)
    dir: DirName
    kante: float                   # Referenzkante des Signals
    brk_idx: int                   # 1. Close des 2-Close-Bruchs (Baseline brk_idx)
    trigger_idx: int               # Arm-spezifische Trigger-Bar (-1 ohne Signal)
    entry_idx: int                 # Einstiegs-Bar open[trigger+1] / open[brk_idx+2] (-1 ohne Signal)
    entry_ts: Optional[pd.Timestamp] = None
    entry_preis: float = float("nan")
    # F5 / Diagnose (Arm 1)
    vol_bestaetigt: Optional[bool] = None
    vol_ref: Optional[float] = None   # 1.5 * SMA20(shift1) zum Triggerzeitpunkt
    vorlauf_bars: Optional[int] = None  # brk_idx - trigger_idx (RAW)
    entry_alt: Optional[float] = None   # F6-Sensitivitaet: close[k] (RETEST)
    # F4: Stop-Architektur
    stop_level: float = float("nan")
    sl_usd: float = float("nan")
    sl_pct: float = float("nan")
    sl_R_ref: float = float("nan")   # sl_usd / (entry*sl_pct_ref) - R-Kompression
    # Messfenster (R-Basis = sl_usd; NaN wenn unbestimmbar)
    mfe_r_12: float = float("nan")
    mae_r_12: float = float("nan")
    mfe_r_24: float = float("nan")
    mae_r_24: float = float("nan")
    mfe_r_48: float = float("nan")
    mae_r_48: float = float("nan")
    mfe_usd_48: float = float("nan")
    mae_usd_48: float = float("nan")
    voll_12: bool = False
    voll_24: bool = False
    voll_48: bool = False
    # F8 / Status
    status: AuditStatus = "SIGNAL"
    frueh_kollaps_ref: bool = False   # MAE in ersten 4 Bars >= 1.0R (0.45%-Referenz)
    frueh_kollaps_stop: bool = False  # MAE in ersten 4 Bars >= sl_usd (F4-Stop)


@dataclass(slots=True)
class SegmentResult:
    """Ergebnis der bitgenauen Re-Segmentierung (exec-Slice)."""

    df: pd.DataFrame
    phases: List[Any]                # PhaseData-Objekte aus dem Slice-Namespace
    ns: Dict[str, Any]
    slice_zeilen: int = 0


# ==============================================================================
# 2) BITGENAUE RE-SEGMENTIERUNG (exec-Slice der Arbeitskopie)
# ==============================================================================


def _slice_segmentierung() -> Tuple[str, int]:
    """Extrahiert den ausfuehrbaren Segmentierungs-Kern aus der Arbeitskopie.

    Schneidet vom Quelltext der Arbeitskopie den Bereich vom `from __future__`
    bis unmittelbar vor dem Abschnitt ``# 5) CANDLE-STATISTIK`` heraus. Dieser
    Kern enthaelt Imports, Datenvertraege, Konstanten inkl. CLI-Overrides,
    load_data, Pivot- und Schnittmengen-Logik sowie die komplette
    Phasen-Segmentierung inkl. Datenende-Finalize (Regel 7).

    Returns:
        Tuple aus (Slice-Quelltext, Anzahl extrahierter Zeilen).
    """
    zeilen: List[str] = ARBEITSKOPIE.read_text(encoding="utf-8").splitlines()
    start: int = 0
    ende: int = len(zeilen)
    for i, z in enumerate(zeilen):
        if z.startswith("from __future__"):
            start = i
            break
    for i, z in enumerate(zeilen):
        if z.startswith("# 5) CANDLE-STATISTIK"):
            ende = i
            break
    if ende <= start:
        raise RuntimeError(f"Slice-Grenzen ungueltig (start={start}, ende={ende})")
    return "\n".join(zeilen[start:ende]), ende - start


def resegmentiere(start: str, ende: str) -> SegmentResult:
    """Fuehrt die bitgenaue Re-Segmentierung fuer ein Zeitfenster aus.

    Args:
        start: Start-Datum (YYYY-MM-DD, inklusive).
        ende: End-Datum (YYYY-MM-DD, exklusive).

    Returns:
        SegmentResult mit df, phases und dem Namespace des exec-Slices.

    Raises:
        FileNotFoundError: Wenn die Arbeitskopie nicht existiert.
        RuntimeError: Wenn der Segmentierungs-Slice fehlschlaeagt.
    """
    if not ARBEITSKOPIE.exists():
        raise FileNotFoundError(f"Arbeitskopie fehlt: {ARBEITSKOPIE}")
    code, n_zeilen = _slice_segmentierung()
    # Ein echtes Modul in sys.modules registrieren: Die Dataclasses der
    # Arbeitskopie nutzen slots=True, und der Dataclass-Decorator von Python 3.10+
    # prueft sys.modules[cls.__module__]. Ohne Registrierung schluege der
    # exec-Slice mit 'NoneType' object has no attribute '__dict__' fehl.
    ns_mod_name: str = "tmp_setup_c_audit_baseline_slice"
    ns_mod = types.ModuleType(ns_mod_name)
    ns_mod.__file__ = str(ARBEITSKOPIE)
    # CLI-Overrides der Arbeitskopie (--start/--ende) ansprechen; das Fenster-
    # Label (AUG/S1/S2) und DB-Pfad ergeben sich daraus automatisch.
    argv_alt = list(sys.argv)
    sys.argv = ["tmp_setup_c_audit.py", f"--start={start}", f"--ende={ende}"]
    sys.modules[ns_mod_name] = ns_mod
    try:
        exec(compile(code, str(ARBEITSKOPIE), "exec"), ns_mod.__dict__)  # noqa: S102
    except Exception as exc:  # pragma: no cover - Fehler waeren Baseline-Drift
        raise RuntimeError(f"Segmentierungs-Slice fehlgeschlagen: {exc}") from exc
    finally:
        sys.argv = argv_alt
        sys.modules.pop(ns_mod_name, None)
    return SegmentResult(df=ns_mod.__dict__["df"], phases=ns_mod.__dict__["phases"],
                         ns=ns_mod.__dict__, slice_zeilen=n_zeilen)


# ==============================================================================
# 3) HILFSFUNKTIONEN (vektorisiert)
# ==============================================================================


def _kanten_reihe(
    ts_arr: np.ndarray,
    hist: Sequence[Tuple[pd.Timestamp, float]],
    fallback: float,
) -> np.ndarray:
    """Rekonstruiert die zeitlich gueltige Kante je Zeitstempel (D1).

    Args:
        ts_arr: datetime64[ns]-Array der Ziel-Zeitstempel.
        hist: U_hist/L_hist der Phase [(ts, value), ...] - aufsteigend.
        fallback: Kante falls hist vor dem Zielzeitpunkt noch keinen Eintrag hat.

    Returns:
        np.ndarray der Kantenwerte je Zeitstempel (Stufenfunktion).
    """
    if not hist:
        return np.full(len(ts_arr), fallback, dtype=float)
    hist_ts = np.array([t.value for t, _ in hist], dtype="int64")
    hist_val = np.array([v for _, v in hist], dtype=float)
    pos = np.searchsorted(hist_ts, ts_arr.astype("int64"), side="right") - 1
    out = np.where(pos >= 0, hist_val[np.clip(pos, 0, len(hist_val) - 1)], fallback)
    return out.astype(float)


def _volumen_bestaetigt(
    df: pd.DataFrame, cfg: AuditConfig
) -> Tuple[np.ndarray, np.ndarray]:
    """Berechnet die F5-Volumenbedingung strikt kausal (keine Selbstinklusion).

    Args:
        df: OHLCV-DataFrame der Baseline (tick_volume vorhanden).
        cfg: AuditConfig mit raw_vol_mult und sma_vol_period.

    Returns:
        Tuple aus (bool-Array Bedingung, float-Array 1.5*SMA20(shift1)).
    """
    tv: np.ndarray = df["tick_volume"].values.astype(float)
    sma: np.ndarray = (
        pd.Series(tv).rolling(cfg.sma_vol_period, min_periods=cfg.sma_vol_period)
        .mean().shift(1).values.astype(float)
    )
    ref: np.ndarray = cfg.raw_vol_mult * sma
    bed: np.ndarray = np.where(np.isnan(ref), False, tv >= ref)
    return bed, ref


def _phase_start_idx(df: pd.DataFrame, p: Any) -> int:
    """Ermittelt den df-Index des Phasenstart-Zeitstempels.

    Args:
        df: OHLCV-DataFrame (idx-Spalte vorhanden).
        p: PhaseData-Objekt aus dem Segmentierungs-Slice.

    Returns:
        Zeilen-Index des Phasenbeginns in df.
    """
    ts_val: np.datetime64 = np.datetime64(p.start)
    pos: int = int(np.searchsorted(df["ts"].values, ts_val, side="left"))
    return int(df["idx"].iloc[pos])


def _messe_fenster(
    df: pd.DataFrame,
    s: AuditSignal,
    cfg: AuditConfig,
) -> None:
    """Berechnet MFE/MAE fuer die Fenster 4/12/24/48 ab entry_idx (in-place).

    Args:
        df: OHLCV-DataFrame.
        s: AuditSignal mit gesetztem entry_idx und dir (wird befuellt).
        cfg: AuditConfig (fuer die 0.45%-Referenz-R-Basis).
    """
    n: int = len(df)
    if s.entry_idx < 0 or s.entry_idx >= n or s.status != "SIGNAL":
        return
    e: int = s.entry_idx
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    up: bool = s.dir == "up"
    entry: float = float(df["open"].values[e])
    s.entry_preis = entry
    sl_usd = s.sl_usd
    r_ref: float = entry * cfg.sl_pct_ref / 100.0
    s.sl_R_ref = sl_usd / r_ref if r_ref > 0.0 else float("nan")
    s.sl_pct = sl_usd / entry * 100.0 if entry > 0.0 else float("nan")

    # Früh-Kollaps ueber die ersten 4 Bars (konsistent Schritt-1-Definition)
    if e + 4 <= n:
        if up:
            mae_4 = entry - float(np.min(low[e : e + 4]))
        else:
            mae_4 = float(np.max(high[e : e + 4])) - entry
        s.frueh_kollaps_ref = mae_4 >= r_ref
        s.frueh_kollaps_stop = mae_4 >= sl_usd if sl_usd > 0.0 else False

    # Fenster 12/24/48: laufende Extremwerte ab entry (vektorisiert)
    max_bars: int = MESS_FENSTER[-1]
    seg_len: int = min(n - e, max_bars)
    if seg_len > 0:
        run_hi: np.ndarray = np.maximum.accumulate(high[e : e + seg_len])
        run_lo: np.ndarray = np.minimum.accumulate(low[e : e + seg_len])
    for fenster in MESS_FENSTER:
        voll = e + fenster <= n
        if seg_len < fenster:
            setattr(s, f"voll_{fenster}", False)
            continue
        k: int = fenster - 1
        if up:
            mfe_usd = float(run_hi[k] - entry)
            mae_usd = float(entry - run_lo[k])
        else:
            mfe_usd = float(entry - run_lo[k])
            mae_usd = float(run_hi[k] - entry)
        setattr(s, f"mfe_r_{fenster}", mfe_usd / sl_usd if sl_usd > 0.0 else float("nan"))
        setattr(s, f"mae_r_{fenster}", mae_usd / sl_usd if sl_usd > 0.0 else float("nan"))
        setattr(s, f"voll_{fenster}", voll)
    if seg_len >= MESS_FENSTER[-1]:
        if up:
            s.mfe_usd_48 = float(run_hi[MESS_FENSTER[-1] - 1] - entry)
            s.mae_usd_48 = float(entry - run_lo[MESS_FENSTER[-1] - 1])
        else:
            s.mfe_usd_48 = float(entry - run_lo[MESS_FENSTER[-1] - 1])
            s.mae_usd_48 = float(run_hi[MESS_FENSTER[-1] - 1] - entry)


# ==============================================================================
# 4) DIE DREI ARME
# ==============================================================================


def _stop_f4(
    df: pd.DataFrame,
    lo_struktur_idx: int,
    hi_struktur_idx: int,
    kante: float,
    dir: DirName,
    cfg: AuditConfig,
) -> float:
    """Berechnet den strukturellen F4-Stop aus Kerzenstruktur und Kante.

    Args:
        df: OHLCV-DataFrame.
        lo_struktur_idx: erste Struktur-Bar (niedriger Index).
        hi_struktur_idx: zweite Struktur-Bar (nur Arm 2: brk_idx+1).
        kante: Referenzkante.
        dir: Signalrichtung.
        cfg: AuditConfig (stop_puffer).

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


def erfasse_confirmed(df: pd.DataFrame, p: Any, nr: int, cfg: AuditConfig) -> AuditSignal:
    """Arm 2: BREAKOUT_CONFIRMED - Einstieg open[brk_idx+2] (F2/F4).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (echter 2-Close-Bruch).
        nr: Phasennummer (1-basiert).
        cfg: AuditConfig.

    Returns:
        AuditSignal (SIGNAL oder DATEN_ENDE).
    """
    b: int = int(p.brk_idx)
    n: int = len(df)
    s = AuditSignal(
        arm="CONFIRMED", fenster=cfg.fenster, phase=nr,
        dir=p.break_dir, kante=float(p.brk_kante), brk_idx=b,
        trigger_idx=b, entry_idx=-1, status="SIGNAL",
    )
    if b + 2 >= n:
        s.status = "DATEN_ENDE"
        return s
    s.entry_idx = b + 2
    s.entry_ts = df["ts"].iloc[b + 2]
    s.stop_level = _stop_f4(df, b, b + 1, float(p.brk_kante), s.dir, cfg)
    if s.dir == "up":
        s.sl_usd = float(df["open"].values[b + 2]) - s.stop_level
    else:
        s.sl_usd = s.stop_level - float(df["open"].values[b + 2])
    _messe_fenster(df, s, cfg)
    return s


def erfasse_raw(df: pd.DataFrame, p: Any, nr: int, cfg: AuditConfig,
                vol_bed: np.ndarray, vol_ref: np.ndarray,
                min_phase_candles: int) -> List[AuditSignal]:
    """Arm 1: BREAKOUT_RAW - Volumen-Durchstoss VOR dem 2-Close-Bruch (F5/F4).

    Scannt den Bereich [Phasenstart+MIN_PHASE_CANDLES, brk_idx] nach dem ersten
    Kanten-Durchstoss (high >= obere Kante bzw. low <= untere Kante) mit
    erfuellter F5-Volumenbedingung. Beide Richtungen werden unabhaengig erfasst
    (ein up- und/oder ein down-Signal je Phase moeglich).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt.
        nr: Phasennummer (1-basiert).
        cfg: AuditConfig.
        vol_bed: bool-Array F5-Bedingung ueber ganz df.
        vol_ref: float-Array 1.5*SMA20(shift1) ueber ganz df.
        min_phase_candles: MIN_PHASE_CANDLES der Baseline (untere Scan-Grenze).

    Returns:
        Liste mit 0..2 AuditSignal-Objekten.
    """
    n: int = len(df)
    b: int = int(p.brk_idx)
    start_idx: int = _phase_start_idx(df, p)
    # Die Segmentierung testet 2-Close-Brueche erst ab (j-i) >= MIN_PHASE_CANDLES
    # (Baseline-Konstante). Diese Grenze ist damit auch die frueheste Bar, an der
    # ein etablierter RAW-Durchstoss einer Kante auftreten kann.
    scan_lo: int = start_idx + min_phase_candles
    scan_hi: int = b  # inklusive Bruchbar
    if scan_lo > scan_hi:
        # Phase zu kurz fuer einen Scan (Sonderfall) -> kein RAW-Signal
        return [
            AuditSignal(
                arm="RAW", fenster=cfg.fenster, phase=nr, dir=p.break_dir,
                kante=float(p.brk_kante), brk_idx=b, trigger_idx=-1,
                entry_idx=-1, status="KEIN_DURCHSTOSS",
            )
        ]
    rng: np.ndarray = np.arange(scan_lo, scan_hi + 1)
    ergebnis: List[AuditSignal] = []

    for dir in ("up", "down"):
        # Kausal dokumentierte Kante: NUR die hist-protokollierten Kanten sind zu
        # frueheren Zeitpunkten bekannt. U_final/L_final nutzen die GESAMTE
        # Phasenhistorie (bis brk_idx) -> fuer Bars vor dem ersten hist-Eintrag
        # NICHT kausal (Lookahead-Vermeidung). Fehlt eine hist fuer die
        # Scan-Richtung, existiert keine etablierte Kante dieser Richtung ->
        # kein RAW-Scan (KEINE_KANTE). Dadurch entfaellt auch der fruehere
        # fehlerhafte Fallback auf die GEGENUEBERLIEGENDE Kante (brk_kante bei
        # down-Bruch waere die untere, nicht die obere Kante).
        hist: Sequence[Tuple[pd.Timestamp, float]] = (
            list(p.U_hist) if dir == "up" else list(p.L_hist)
        )
        if not hist:
            ergebnis.append(AuditSignal(
                arm="RAW", fenster=cfg.fenster, phase=nr, dir=dir,
                kante=float("nan"), brk_idx=b, trigger_idx=-1,
                entry_idx=-1, status="KEINE_KANTE",
            ))
            continue
        erster_hist_idx: int = int(np.searchsorted(
            df["ts"].values, np.datetime64(hist[0][0]), side="left"
        ))
        scan_lo_dir: int = max(scan_lo, erster_hist_idx)
        if scan_lo_dir > scan_hi:
            # Fenster zwischen fruehester etablierter Kante und Bruch ist leer
            ergebnis.append(AuditSignal(
                arm="RAW", fenster=cfg.fenster, phase=nr, dir=dir,
                kante=float("nan"), brk_idx=b, trigger_idx=-1,
                entry_idx=-1, status="KEIN_DURCHSTOSS",
            ))
            continue
        rng_dir: np.ndarray = np.arange(scan_lo_dir, scan_hi + 1)
        ts_rng_dir: np.ndarray = df["ts"].values[rng_dir]
        # Ab scan_lo_dir (>= erster hist-Eintrag) liefert searchsorted(side="right")
        # je Bar die kausal gueltige Kantenstufe (letzter Eintrag mit ts <= ts_r).
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
        s = AuditSignal(
            arm="RAW", fenster=cfg.fenster, phase=nr, dir=dir,
            kante=float(kante_r[erste - scan_lo_dir]) if erste is not None
            else float(hist[0][1]),
            brk_idx=b, trigger_idx=erste if erste is not None else -1,
            entry_idx=-1, status="SIGNAL",
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
        s.vol_ref = float(vol_ref[erste])
        s.stop_level = _stop_f4(
            df, erste, erste, float(kante_r[erste - scan_lo_dir]), dir, cfg
        )
        if dir == "up":
            s.sl_usd = float(df["open"].values[s.entry_idx]) - s.stop_level
        else:
            s.sl_usd = s.stop_level - float(df["open"].values[s.entry_idx])
        _messe_fenster(df, s, cfg)
        ergebnis.append(s)
    return ergebnis


def erfasse_retest(df: pd.DataFrame, p: Any, nr: int, cfg: AuditConfig) -> AuditSignal:
    """Arm 3: RETEST_OUTSIDE - Pullback an die gebrochene Kante (F6/F7/F8).

    Sucht im Fenster (brk_idx, brk_idx+16] den ersten Kontakt mit Band
    [kante-0.15, kante+0.15], dessen M15-Close die Ausbruchsseite verteidigt.
    Einstieg = open[k+1] (F6). Faelle mit Stop-Verletzung seit dem Bruch werden
    als VERWORFEN_STOP_VERLETZT gezaehlt (F8).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt.
        nr: Phasennummer.
        cfg: AuditConfig.

    Returns:
        AuditSignal (SIGNAL oder Status-Kategorie).
    """
    n: int = len(df)
    b: int = int(p.brk_idx)
    up: bool = p.break_dir == "up"
    kante: float = float(p.brk_kante)
    lo: int = b + 1
    hi: int = min(b + cfg.retest_timeout_bars, n - 2)  # k+1 muss existieren
    s = AuditSignal(
        arm="RETEST", fenster=cfg.fenster, phase=nr, dir=p.break_dir,
        kante=kante, brk_idx=b, trigger_idx=-1, entry_idx=-1,
    )
    if hi < lo:
        s.status = "DATEN_ENDE"
        return s
    # F4-Stop: Struktur = beide Bestaetigungs-Closes der Phase (wie Arm 2)
    stop: float = _stop_f4(df, b, b + 1, kante, p.break_dir, cfg)
    s.stop_level = stop
    high: np.ndarray = df["high"].values
    low: np.ndarray = df["low"].values
    close: np.ndarray = df["close"].values
    # F8: laufendes Extrem seit Bruch (inkl. Retest-Bar k)
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
        s.entry_alt = float(close[erste_k])  # F6-Sensitivitaet
        if up:
            s.sl_usd = float(df["open"].values[s.entry_idx]) - stop
        else:
            s.sl_usd = stop - float(df["open"].values[s.entry_idx])
        _messe_fenster(df, s, cfg)
        return s
    if hatte_kontakt:
        # Kontakt ja, aber nie mit Close-Verteidigung (D2: bis Timeout gesucht)
        s.status = "KEIN_CLOSE_SCHUTZ"
        return s
    s.status = "VERWORFEN_STOP_VERLETZT" if bool(verletzt.any()) else "TIMEOUT"
    return s


# ==============================================================================
# 5) STATISTIK & REPORT
# ==============================================================================


def _agg_zeile(signale: Sequence[AuditSignal], fenster: int) -> Dict[str, Any]:
    """Aggregiert eine MFE/MAE-Statistikzeile fuer ein Messfenster.

    Args:
        signale: SIGNAL-Signale.
        fenster: Messfenster in Bars (12/24/48).

    Returns:
        Dict mit n, medianR, >=1R/>=2R/>=3R, MAE medianR/p90R/maxR (R-Basis sl_usd).
    """
    out: Dict[str, Any] = {
        "n": 0, "mfe_med": float("nan"), "ge_1r": 0.0, "ge_2r": 0.0, "ge_3r": 0.0,
        "mae_med": float("nan"), "mae_p90": float("nan"), "mae_max": float("nan"),
    }
    mfe: List[float] = []
    mae: List[float] = []
    for s in signale:
        if s.status != "SIGNAL":
            continue
        voll = getattr(s, f"voll_{fenster}")
        if not voll:
            continue
        m = float(getattr(s, f"mfe_r_{fenster}"))
        a = float(getattr(s, f"mae_r_{fenster}"))
        if not np.isnan(m):
            mfe.append(m)
            mae.append(a)
    if not mfe:
        return out
    arr_mfe: np.ndarray = np.array(mfe)
    arr_mae: np.ndarray = np.array(mae)
    out["n"] = len(arr_mfe)
    out["mfe_med"] = float(np.median(arr_mfe))
    out["ge_1r"] = float(np.mean(arr_mfe >= 1.0) * 100.0)
    out["ge_2r"] = float(np.mean(arr_mfe >= 2.0) * 100.0)
    out["ge_3r"] = float(np.mean(arr_mfe >= 3.0) * 100.0)
    out["mae_med"] = float(np.median(arr_mae))
    out["mae_p90"] = float(np.percentile(arr_mae, 90))
    out["mae_max"] = float(np.max(arr_mae))
    return out


def _fmt_agg(agg: Dict[str, Any]) -> str:
    """Formatiert eine Aggregatzeile im Schritt-1-konsistenten Textformat."""
    if not agg["n"]:
        return f"{'':>5} {'-':>7} {'-':>6} {'-':>5} {'-':>5} {'-':>5} | {'-':>7} {'-':>6} {'-':>6}"
    return (
        f"{agg['n']:>5} {agg['mfe_med']:>7.2f} {agg['ge_1r']:>5.1f}% "
        f"{agg['ge_2r']:>4.1f}% {agg['ge_3r']:>4.1f}% | "
        f"{agg['mae_med']:>7.2f} {agg['mae_p90']:>5.2f} {agg['mae_max']:>6.2f}"
    )


def _status_zeile(signale: Sequence[AuditSignal]) -> str:
    """Zaehlt Status-Kategorien je Arm."""
    z: Dict[str, int] = {}
    for s in signale:
        z[s.status] = z.get(s.status, 0) + 1
    order: List[str] = ["SIGNAL", "VERWORFEN_STOP_VERLETZT", "TIMEOUT",
                        "KEIN_CLOSE_SCHUTZ", "KEIN_VOLUMEN", "KEIN_DURCHSTOSS",
                        "KEINE_KANTE", "DATEN_ENDE"]
    teile = [f"{k}={z.get(k, 0)}" for k in order if z.get(k, 0)]
    return " | ".join(teile)


def _sl_verteilung(signale: Sequence[AuditSignal]) -> str:
    """Verteilung der SL-Abstaende (USD / % / R_ref) - Runaway-/Gap-Diagnose."""
    usd: List[float] = []
    pct: List[float] = []
    rref: List[float] = []
    for s in signale:
        if s.status == "SIGNAL" and not np.isnan(s.sl_usd) and s.sl_usd > 0.0:
            usd.append(s.sl_usd)
            pct.append(s.sl_pct)
            rref.append(s.sl_R_ref)
    if not usd:
        return "  (keine SIGNAL-Faelle)"
    u = np.array(usd)
    p = np.array(pct)
    rr = np.array(rref)
    def q(a: np.ndarray) -> str:
        return (f"p25={np.percentile(a,25):.3f} med={np.median(a):.3f} "
                f"p75={np.percentile(a,75):.3f} max={np.max(a):.3f}")
    return (
        f"  USD : {q(u)}\n"
        f"  PCT%: {q(p)}\n"
        f"  R_ref (0.45%): {q(rr)}   <-- R-Kompression (Kanten-Gap) je >1.0"
    )


def _frueh_kollaps(signale: Sequence[AuditSignal]) -> str:
    """Frueh-Kollaps-Hit-Rate: F4-Stop vs. 0.45%-Referenz (erste 4 Bars)."""
    n_ref = sum(1 for s in signale if s.status == "SIGNAL" and s.entry_idx >= 0)
    n_ref_ok = sum(1 for s in signale if s.status == "SIGNAL" and s.frueh_kollaps_ref)
    n_stop_ok = sum(1 for s in signale if s.status == "SIGNAL" and s.frueh_kollaps_stop)
    if not n_ref:
        return "  (keine SIGNAL-Faelle)"
    return (
        f"  0.45%-Referenz : {100.0 * n_ref_ok / n_ref:.1f}%  (MAE@4 >= 1.0R_ref)\n"
        f"  F4-Stop        : {100.0 * n_stop_ok / n_ref:.1f}%  (MAE@4 >= sl_usd)"
    )


def report_fenster(sr: SegmentResult, cfg: AuditConfig) -> Tuple[List[AuditSignal], str]:
    """Erfasst alle Signale eines Fensters und baut den Reporttext.

    Args:
        sr: SegmentResult der Re-Segmentierung.
        cfg: AuditConfig.

    Returns:
        Tuple aus (alle AuditSignale, Reporttext).
    """
    df: pd.DataFrame = sr.df
    n: int = len(df)
    min_phase_candles: int = int(sr.ns["MIN_PHASE_CANDLES"])
    vol_bed, vol_ref = _volumen_bestaetigt(df, cfg)
    echte: List[Any] = [p for p in sr.phases
                        if p.break_dir is not None and p.brk_idx is not None]
    alle: List[AuditSignal] = []
    for nr, p in enumerate(echte, start=1):
        alle.append(erfasse_confirmed(df, p, nr, cfg))
        alle.extend(erfasse_raw(df, p, nr, cfg, vol_bed, vol_ref, min_phase_candles))
        alle.append(erfasse_retest(df, p, nr, cfg))

    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - SCHRITT 2: RE-SEGMENTIERUNG & SIGNAL-REPLAY (tmp_setup_c_audit.py)",
        f"Fenster: {cfg.fenster} | Symbol: {cfg.symbol} {cfg.timeframe} | "
        f"Datum: 2026-09-05 | Baseline: {BASELINE_REF}",
        "F4 struktureller Stop | F5 Volumen SMA20(shift1) | F6 open[k+1] | "
        "F7 Timeout 16 | F8 Verwerfen bei Stop-Verletzung",
        linie,
        f"df-Bars: {n} | Phasen gesamt: {len(sr.phases)} | echte 2-Close-Brueche (F3): {len(echte)}",
        "",
    ]
    for arm in ("CONFIRMED", "RAW", "RETEST"):
        sig = [s for s in alle if s.arm == arm]
        txt.append(linie)
        txt.append(f"ARM {arm}  (n={len(sig)} Objekte)")
        txt.append("  Status: " + _status_zeile(sig))
        txt.append("  SL-Abstand (SIGNAL):")
        txt.append(_sl_verteilung(sig))
        txt.append("  Frueh-Kollaps (erste 4 Bars):")
        txt.append(_frueh_kollaps(sig))
        for fenster in MESS_FENSTER:
            txt.append(f"  MFE/MAE Fenster {fenster:>2} (R = sl_usd, nur volle Fenster):")
            txt.append("    Grp     n   medianR   >=1R   >=2R   >=3R | MAE med   p90    max")
            for dir in ("up", "down"):
                agg = _agg_zeile([s for s in sig if s.dir == dir], fenster)
                txt.append(f"    {dir:<5} {_fmt_agg(agg)}")
            agg_all = _agg_zeile(sig, fenster)
            txt.append(f"    alle  {_fmt_agg(agg_all)}")
        txt.append("")
        # Detailzeilen nur fuer AUG (kleines Fenster) und nur SIGNAL-Faelle
        if cfg.fenster == "AUG":
            txt.append("  Detail (AUG, SIGNAL-Faelle je Phase):")
            txt.append("    Ph  Arm        Dir  trigger_ts           entry      stop      sl_usd  sl_R_ref")
            for s in sorted(sig, key=lambda x: (x.phase, x.arm)):
                if s.status != "SIGNAL":
                    continue
                ts = s.entry_ts.strftime("%Y-%m-%d %H:%M") if s.entry_ts is not None else "-"
                txt.append(
                    f"    {s.phase:>3} {s.arm:<9} {s.dir:<4} {ts}  "
                    f"{s.entry_preis:>8.3f} {s.stop_level:>8.3f} "
                    f"{s.sl_usd:>7.3f} {s.sl_R_ref:>7.2f}"
                )
        txt.append("")
    # Verifikationsanker Arm 2 (muss F3 entsprechen, abzueglich DATEN_ENDE)
    conf_signal = sum(1 for s in alle if s.arm == "CONFIRMED" and s.status == "SIGNAL")
    conf_ende = sum(1 for s in alle if s.arm == "CONFIRMED" and s.status == "DATEN_ENDE")
    txt.append(linie)
    txt.append(
        f"VERIFIKATIONSANKER: CONFIRMED SIGNAL={conf_signal} DATEN_ENDE={conf_ende} "
        f"(erwartet: F3-Brueche {len(echte)}, DATEN_ENDE nur bei brk_idx=n-2)"
    )
    txt.append(linie)
    return alle, "\n".join(txt)


# ==============================================================================
# 6) MAIN
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt das Replay-Audit fuer ein Fenster aus.

    Args:
        argv: Kommandozeilen-Argumente (Default: sys.argv[1:]).

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].upper()
    if fenster not in FENSTER_DEFS:
        raise SystemExit(f"Unbekanntes Fenster: {fenster} (AUG|S1|S2)")
    cfg = AuditConfig(fenster=fenster)
    start, ende = FENSTER_DEFS[fenster]
    print(f"Re-Segmentierung {cfg.symbol} {cfg.timeframe} {start}..{ende} ...")
    sr = resegmentiere(start, ende)
    alle, text = report_fenster(sr, cfg)
    out: Path = TEST_DIR / f"tmp_setup_c_audit_{fenster}.txt"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nReport geschrieben: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
