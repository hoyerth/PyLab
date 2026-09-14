"""
SETUP C - SCHRITT 3: TRAILING-ARCHITEKTUR A/B (test/tmp_setup_c_trailing.py)
================================================================================
Status: Entwurf zur Durchsicht (05.09.2026) - KEINE Ausfuehrung/Kompilierung.
Doku: docs/setup_c_experiment.md (F4-F8, D4, Befunde B1-B4; Schritt 3 F9-F11,
      Datenvertrag DV1-DV6).
Baseline: scripts/phasen_volumen_profil.py (v0.4.0-frozen) - UNVERAENDERT.
Arbeitsmodus: isoliertes, rein lesendes Replay (DuckDB read_only via
      tmp_setup_c_audit.py), keine Produktions-Integration, keine Charts.

Zweck
-----
Simuliert fuer die drei Einstiegs-Arme (RAW / CONFIRMED / RETEST) aus
tmp_setup_c_audit.py das Stufen-Trailing auf F4-Basis und vergleicht:
  VAR_A_FIXED  : fester Puffer 0.15 USD unter/ueber bestaetigten Pivot-Stufen
  VAR_B_ATR    : dynamischer Puffer max(1.5 * ATR_7, Floor 0.15 USD)
Ziel: Wiedergewinnung des durch den breiten F4-Stop komprimierten R:R (B2).

Arretierte Beschluesse (Doku §2.4 + Schritt-3-Protokoll)
--------------------------------------------------------
F4   Struktureller Initial-Stop (aus Schritt 2 uebernommen, unveraendert).
F9   Trailing-Trigger: F4-Stop bleibt starr, bis eine bestaetigte STUFE die
     Einstiegsseite ueberschreitet (DV1: stufe > entry, nicht nacktes Pivot).
F10  VAR_B-Puffer: buffer = max(atr_mult * ATR_7, buffer_floor 0.15 USD),
     Default atr_mult = 1.5 (Sensitivitaeten 1.0 / 2.0).
F11  Exit-Execution differenziert: F4-Initial-Stop INTRABAR (low<=stop bzw.
     high>=stop); Trailing-Stufe CLOSE-basiert (close jenseits des Stops).
     Sensitivitaet: trailing_exit = INTRABAR.

Kausalitaet (DV2)
-----------------
- Pivot bei Bar p (Lookback n=2) ist erst nach CLOSE von Bar p+2 bestaetigt
  (find_pivots-Bedingung lo[p+2] > lo[p] / hi[p+2] < hi[p]). Eine Stop-
  Aenderung ist daher erst ab Bar p+3 wirksam (im Loop: Auswertung der
  Bestaetigung an Bar k = p+2 NACH dem Exit-Check von Bar k; neuer Stop
  gilt ab Bar k+1).
- ATR fuer den Puffer einer Stufe wird an der Bestaetigungs-Bar k = p+2
  abgegriffen (ATR ueber Bars <= k) - kein Lookahead.
- ATR_n = SMA(TrueRange, n); TrueRange = max(high-low, |high-prev_close|,
  |low-prev_close|).

Exit-Semantik (DV3)
-------------------
Aktiver Stop = F4-Initial-Stop  -> INTRABAR wirksam.
Aktiver Stop = nachgezogene Stufe -> CLOSE-basiert wirksam (Default).
Sobald der Stop auf eine Stufe > F4-Level gewandert ist, ist der F4-Stop
obsolet (locked-in): Ein intrabarer Dip unter das alte F4-Level bei Close
ueber der aktiven Stufe ist KEIN Exit.

Hinweis: Die Simulation ist ein zustandsbehafteter Ratschen-Prozess (der
Stop haengt vom bisherigen Pfad ab) und nutzt daher - wie die Baseline-
Aufloesung _aufloesen(TRAILING_PCT) - eine sequentielle Bar-Schleife je
Signal. Keine Lookahead-Freiheit wird dadurch verletzt (alle Entscheidungen
nutzen nur abgeschlossene Bars).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

TEST_DIR: Path = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

import tmp_setup_c_audit as audit  # noqa: E402  (reine Wiederverwendung der Signal-Erfassung)

# ==============================================================================
# 1) TYPALIASSE & DATENVERTRAEGE (DV4 - freigegeben)
# ==============================================================================

ArmName = Literal["RAW", "CONFIRMED", "RETEST"]
DirName = Literal["up", "down"]
TrailingModus = Literal["VAR_A_FIXED", "VAR_B_ATR", "KEIN_TRAILING"]
TrailingTrigger = Literal["STUFE_UEBER_ENTRY", "STUFE_UEBER_INITIAL"]
TrailingExitArt = Literal["CLOSE", "INTRABAR"]

ExitGrund = Literal[
    "INITIAL_SL_INTRABAR",     # F11: F4-Stop intrabar beruehrt
    "TRAILING_SL_CLOSE",       # F11: Trailing-Stufe, Close jenseits des Stops
    "TRAILING_SL_INTRABAR",    # F11-Sensitivitaet: Trailing-Stufe intrabar
    "DATEN_ENDE",              # Kein Exit bis Datenende -> Close der letzten Bar
]


@dataclass(frozen=True, slots=True)
class TrailingConfig:
    """Konfiguration fuer die Trailing-Simulation (Setup C Schritt 3, F9-F11).

    Defaults = arretierte Beschluesse; Sensitivitaeten durch Abweichen:
      - F9-Sensitivitaet (Option A):  trailing_trigger = "STUFE_UEBER_INITIAL"
      - F10-Sensitivitaeten:           atr_mult in (1.0, 2.0)
      - F11-Sensitivitaet:             trailing_exit = "INTRABAR"
    """

    fenster: Literal["AUG", "S1", "S2"] = "AUG"
    symbol: str = "SILVER"
    timeframe: str = "M15"

    # Pivot-Stufen (F9)
    pivot_lookback: int = 2                  # Baseline find_pivots
    # Aktivierung: F9-Default = Stufe (nach Puffer) muss > entry liegen.
    # Option A (Sensitivitaet): Nachzug sobald Stufe > F4-Initial-Stop.
    trailing_trigger: TrailingTrigger = "STUFE_UEBER_ENTRY"

    # Puffer (F10)
    fixed_buffer: float = 0.15               # USD: Variante A
    atr_period: int = 7                      # ATR-Periode Variante B
    atr_mult: float = 1.5                    # F10-Default; Sensitivitaeten 1.0/2.0
    buffer_floor: float = 0.15               # USD: Floor von Variante B (= fixed)

    # Exit-Execution (F11)
    trailing_exit: TrailingExitArt = "CLOSE"  # Default close-basiert

    # Baseline-Referenz
    sl_pct_ref: float = 0.45                 # 0.45%-Referenz (r_ref-Basis)


@dataclass(slots=True)
class TrailingResult:
    """Ergebnis eines getrailten Signals (ein Objekt je Signal x Modus)."""

    arm: ArmName
    phase: int
    dir: DirName
    modus: TrailingModus
    trigger: TrailingTrigger
    entry_idx: int
    entry_ts: pd.Timestamp
    entry_preis: float

    # Stop-Architektur
    f4_initial_stop: float
    sl_usd: float                            # Initial-Risiko in USD
    exit_idx: int
    exit_ts: pd.Timestamp
    exit_preis: float
    exit_grund: ExitGrund

    # R-Multiples (F4-Basis und 0.45%-Referenz)
    r_f4: float
    r_ref: float

    # Stufen-Metriken (F9)
    trailing_start_idx: int = -1             # erste Bar mit Stop-Nachzug (-1 = nie)
    n_stufen_nachgezogen: int = 0
    max_stufen_level: float = float("nan")   # Long: hoechster / Short: tiefster Stand
    n_pivots_geprueft: int = 0               # bestaetigte Pivots in der Trailing-Zone
    exit_offset_bars: int = 0                # exit_idx - entry_idx


# ==============================================================================
# 2) HILFSFUNKTIONEN (vektorisiert, kausal)
# ==============================================================================


def _pivot_stufen(d: pd.DataFrame, lookback: int) -> Tuple[np.ndarray, np.ndarray]:
    """Berechnet Pivot-Hochs/-Tiefs (Baseline-find_pivots-Semantik).

    Args:
        d: OHLCV-DataFrame (Spalten high/low vorhanden).
        lookback: Pivot-Lookback n (Bestaetigung nach n Folge-Bars).

    Returns:
        Tuple aus (pivot_hi, pivot_lo): np.ndarray mit pivot-Wert an der
        Pivot-Bar und NaN sonst. Kausalitaet: Ein Eintrag an Position p ist
        erst nach Close von Bar p+lookback verfuegbar (im Replay wird er an
        Bar k = p+lookback abgegriffen).
    """
    h: np.ndarray = d["high"].values.astype(float)
    l: np.ndarray = d["low"].values.astype(float)
    hs = pd.Series(h)
    ls = pd.Series(l)
    is_hi: pd.Series = (hs == hs.rolling(2 * lookback + 1, center=True,
                                         min_periods=1).max()) & (
        hs.shift(lookback) < h) & (hs.shift(-lookback) < h)
    is_lo: pd.Series = (ls == ls.rolling(2 * lookback + 1, center=True,
                                         min_periods=1).min()) & (
        ls.shift(lookback) > l) & (ls.shift(-lookback) > l)
    hi_np: np.ndarray = is_hi.to_numpy().copy()
    lo_np: np.ndarray = is_lo.to_numpy().copy()
    if lookback > 0:
        hi_np[:lookback] = False
        hi_np[-lookback:] = False
        lo_np[:lookback] = False
        lo_np[-lookback:] = False
    pivot_hi: np.ndarray = np.where(hi_np, h, np.nan)
    pivot_lo: np.ndarray = np.where(lo_np, l, np.nan)
    return pivot_hi, pivot_lo


def _atr_reihe(d: pd.DataFrame, period: int) -> np.ndarray:
    """Berechnet ATR (SMA der TrueRange) strikt kausal je Bar.

    Args:
        d: OHLCV-DataFrame (Spalten high/low/close vorhanden).
        period: ATR-Periode.

    Returns:
        np.ndarray: ATR-Wert je Bar (NaN fuer die ersten period-1 Bars).
    """
    h: np.ndarray = d["high"].values.astype(float)
    l: np.ndarray = d["low"].values.astype(float)
    c: np.ndarray = d["close"].values.astype(float)
    prev: np.ndarray = np.empty_like(c)
    prev[0] = c[0]
    prev[1:] = c[:-1]
    tr: np.ndarray = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    return pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy()


def _signale_fenster(fenster: str) -> Tuple[pd.DataFrame, List[audit.AuditSignal]]:
    """Erfasst alle SIGNAL-Signale eines Fensters ueber die Schritt-2-Funktionen.

    Args:
        fenster: AUG | S1 | S2.

    Returns:
        Tuple aus (df, Liste der AuditSignale mit status SIGNAL und sl_usd > 0).
    """
    cfg = audit.AuditConfig(fenster=fenster)
    start, ende = audit.FENSTER_DEFS[fenster]
    sr = audit.resegmentiere(start, ende)
    df: pd.DataFrame = sr.df
    min_phase_candles: int = int(sr.ns["MIN_PHASE_CANDLES"])
    vol_bed, vol_ref = audit._volumen_bestaetigt(df, cfg)
    echte = [p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None]
    alle: List[audit.AuditSignal] = []
    for nr, p in enumerate(echte, start=1):
        alle.append(audit.erfasse_confirmed(df, p, nr, cfg))
        alle.extend(audit.erfasse_raw(df, p, nr, cfg, vol_bed, vol_ref, min_phase_candles))
        alle.append(audit.erfasse_retest(df, p, nr, cfg))
    sigs = [s for s in alle
            if s.status == "SIGNAL" and s.entry_idx >= 0
            and np.isfinite(s.sl_usd) and s.sl_usd > 0.0]
    return df, sigs


# ==============================================================================
# 3) SIMULATIONSKERN (zustandsbehaftete Ratsche, kausal)
# ==============================================================================


def _puffer_wert(atr_arr: np.ndarray, cfg: TrailingConfig,
                 modus: TrailingModus, k: int) -> float:
    """Berechnet den Puffer fuer eine Stufe an Bestaetigungs-Bar k (F10).

    Args:
        atr_arr: ATR-Reihe ueber das gesamte df.
        cfg: TrailingConfig.
        modus: VAR_A_FIXED oder VAR_B_ATR.
        k: Bestaetigungs-Bar (ATR ueber Bars <= k, kausal).

    Returns:
        Pufferwert in USD.
    """
    if modus == "VAR_B_ATR":
        a = atr_arr[k]
        if np.isfinite(a):
            return max(cfg.atr_mult * float(a), cfg.buffer_floor)
        return cfg.buffer_floor
    return cfg.fixed_buffer


def _aktiv_stufe(stufe: float, entry: float, f4_stop: float,
                 trigger: TrailingTrigger, up: bool) -> bool:
    """Aktivierungs-Bedingung der Stufe (DV1/F9).

    Args:
        stufe: Stufe = Pivot +/- Puffer.
        entry: Einstiegspreis.
        f4_stop: F4-Initial-Stop.
        trigger: STUFE_UEBER_ENTRY (Default) oder STUFE_UEBER_INITIAL (Option A).
        up: True fuer Long.

    Returns:
        True, wenn die Stufe die Aktivierungsschwelle ueberschreitet.
    """
    if up:
        return stufe > entry if trigger == "STUFE_UEBER_ENTRY" else stufe > f4_stop
    return stufe < entry if trigger == "STUFE_UEBER_ENTRY" else stufe < f4_stop


def simuliere_signal(df: pd.DataFrame, sig: audit.AuditSignal,
                     cfg: TrailingConfig, modus: TrailingModus,
                     pivot_hi: np.ndarray, pivot_lo: np.ndarray,
                     atr_arr: np.ndarray) -> TrailingResult:
    """Simuliert das Stufen-Trailing fuer ein AuditSignal.

    Zustandsbehaftete Ratsche (F9-F11, DV1-DV6): Bar fuer Bar ab dem Einstieg.
    Exit zuerst gegen den aktiven Stop pruefen, danach Pivot-Bestaetigung an
    Bar k = p + lookback verarbeiten (neuer Stop gilt ab Bar k+1).

    Args:
        df: OHLCV-DataFrame.
        sig: AuditSignal (status SIGNAL, sl_usd > 0).
        cfg: TrailingConfig.
        modus: VAR_A_FIXED / VAR_B_ATR / KEIN_TRAILING (Referenz).
        pivot_hi: Pivot-Hoch-Array (NaN ausserhalb).
        pivot_lo: Pivot-Tief-Array (NaN ausserhalb).
        atr_arr: ATR-Reihe.

    Returns:
        TrailingResult.
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
    lb: int = cfg.pivot_lookback

    stop: float = f4_stop
    stop_art: Literal["INITIAL", "TRAILING"] = "INITIAL"
    exit_grund: ExitGrund = "DATEN_ENDE"
    exit_price: float = float(close[n - 1])
    exit_idx: int = n - 1
    trailing_start_idx: int = -1
    n_stufen: int = 0
    max_stufe: float = float("nan")
    n_geprueft: int = 0

    for k in range(e, n):
        # --- 1) Exit gegen den aktiven Stop --------------------------------
        if stop_art == "INITIAL":
            # F11: F4-Initial-Stop intrabar wirksam
            if (up and low[k] <= stop) or ((not up) and high[k] >= stop):
                exit_price, exit_idx, exit_grund = float(stop), k, "INITIAL_SL_INTRABAR"
                break
        else:
            if cfg.trailing_exit == "CLOSE":
                if (up and close[k] < stop) or ((not up) and close[k] > stop):
                    exit_price, exit_idx, exit_grund = float(close[k]), k, "TRAILING_SL_CLOSE"
                    break
            else:
                if (up and low[k] <= stop) or ((not up) and high[k] >= stop):
                    exit_price, exit_idx, exit_grund = float(stop), k, "TRAILING_SL_INTRABAR"
                    break

        # --- 2) Pivot-Bestaetigung an Bar k (p = k - lookback) -------------
        if modus == "KEIN_TRAILING":
            continue
        p: int = k - lb
        if p >= e:
            if up:
                pv: float = float(pivot_lo[p]) if not np.isnan(pivot_lo[p]) else float("nan")
                if np.isfinite(pv):
                    n_geprueft += 1
                    stufe: float = pv - _puffer_wert(atr_arr, cfg, modus, k)
                    if stop_art == "INITIAL":
                        if _aktiv_stufe(stufe, entry, f4_stop, cfg.trailing_trigger, up):
                            stop_art = "TRAILING"
                            stop = stufe
                            trailing_start_idx = k + 1
                            n_stufen = 1
                            max_stufe = stufe
                    else:
                        if stufe > stop:
                            stop = stufe
                            n_stufen += 1
                            max_stufe = stufe
            else:
                pv = float(pivot_hi[p]) if not np.isnan(pivot_hi[p]) else float("nan")
                if np.isfinite(pv):
                    n_geprueft += 1
                    stufe = pv + _puffer_wert(atr_arr, cfg, modus, k)
                    if stop_art == "INITIAL":
                        if _aktiv_stufe(stufe, entry, f4_stop, cfg.trailing_trigger, up):
                            stop_art = "TRAILING"
                            stop = stufe
                            trailing_start_idx = k + 1
                            n_stufen = 1
                            max_stufe = stufe
                    else:
                        if stufe < stop:
                            stop = stufe
                            n_stufen += 1
                            max_stufe = stufe

    # --- R-Multiples -------------------------------------------------------
    if up:
        r_f4: float = (exit_price - entry) / sl_usd
    else:
        r_f4 = (entry - exit_price) / sl_usd
    r_ref_base: float = entry * cfg.sl_pct_ref / 100.0
    r_ref: float = (exit_price - entry) / r_ref_base if up else (entry - exit_price) / r_ref_base

    return TrailingResult(
        arm=sig.arm, phase=sig.phase, dir=sig.dir, modus=modus,
        trigger=cfg.trailing_trigger,
        entry_idx=e, entry_ts=df["ts"].iloc[e], entry_preis=entry,
        f4_initial_stop=f4_stop, sl_usd=sl_usd,
        exit_idx=exit_idx, exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=exit_price, exit_grund=exit_grund,
        r_f4=float(r_f4), r_ref=float(r_ref),
        trailing_start_idx=trailing_start_idx,
        n_stufen_nachgezogen=n_stufen,
        max_stufen_level=max_stufe,
        n_pivots_geprueft=n_geprueft,
        exit_offset_bars=exit_idx - e,
    )


# ==============================================================================
# 4) AGGREGATION & REPORT
# ==============================================================================


def _agg_block(results: Sequence[TrailingResult]) -> Dict[str, Any]:
    """Aggregiert TrailingResults zu Kennzahlen (sum/mean r_f4, WR, PF)."""
    out: Dict[str, Any] = {
        "n": len(results),
        "sum_r_f4": 0.0, "mean_r_f4": float("nan"), "median_r_f4": float("nan"),
        "wr": float("nan"), "pf": float("inf"),
        "sum_r_ref": 0.0,
        "n_init": 0, "n_trail_close": 0, "n_trail_intra": 0, "n_ende": 0,
        "n_trailing_aktiv": 0, "mean_stufen": 0.0,
        "mean_offset": 0.0, "n_geprueft": 0,
    }
    if not results:
        return out
    rs: List[float] = []
    for r in results:
        rs.append(r.r_f4)
        out["sum_r_ref"] += r.r_ref
        if r.exit_grund == "INITIAL_SL_INTRABAR":
            out["n_init"] += 1
        elif r.exit_grund == "TRAILING_SL_CLOSE":
            out["n_trail_close"] += 1
        elif r.exit_grund == "TRAILING_SL_INTRABAR":
            out["n_trail_intra"] += 1
        else:
            out["n_ende"] += 1
        if r.trailing_start_idx >= 0:
            out["n_trailing_aktiv"] += 1
            out["mean_stufen"] += r.n_stufen_nachgezogen
        out["n_geprueft"] += r.n_pivots_geprueft
        out["mean_offset"] += r.exit_offset_bars
    arr: np.ndarray = np.array(rs, dtype=float)
    out["sum_r_f4"] = float(arr.sum())
    out["mean_r_f4"] = float(arr.mean())
    out["median_r_f4"] = float(np.median(arr))
    out["wr"] = float(np.mean(arr > 0.0) * 100.0)
    pos: float = float(arr[arr > 0.0].sum())
    neg: float = float(-arr[arr < 0.0].sum())
    out["pf"] = pos / neg if neg > 0.0 else float("inf")
    n_akt: int = out["n_trailing_aktiv"]
    out["mean_stufen"] = out["mean_stufen"] / n_akt if n_akt else float("nan")
    out["mean_offset"] = out["mean_offset"] / len(results) if results else float("nan")
    return out


def _fmt_zahl(v: Any, fmt: str = ".2f") -> str:
    return "-" if (v is None or (isinstance(v, float) and not np.isfinite(v))) else f"{v:{fmt}}"


def _block_text(titel: str, agg: Dict[str, Any]) -> List[str]:
    """Formatiert einen Aggregationsblock."""
    t = f"{titel}  (n={agg['n']})"
    lines: List[str] = [t, "  " + "-" * max(2, len(t) - 2)]
    if not agg["n"]:
        lines.append("  (keine Signale)")
        return lines
    lines.append(
        f"  sum r_f4={agg['sum_r_f4']:>9.2f}  mean r_f4={_fmt_zahl(agg['mean_r_f4']):>7}  "
        f"median={_fmt_zahl(agg['median_r_f4']):>7}  WR={_fmt_zahl(agg['wr'], '.1f')}%  "
        f"PF={_fmt_zahl(agg['pf'])}"
    )
    lines.append(f"  sum r_ref (0.45%-Basis) = {agg['sum_r_ref']:.2f}")
    lines.append(
        f"  Exit: INITIAL_SL_INTRABAR={agg['n_init']} | TRAILING_SL_CLOSE={agg['n_trail_close']} "
        f"| TRAILING_SL_INTRABAR={agg['n_trail_intra']} | DATEN_ENDE={agg['n_ende']}"
    )
    lines.append(
        f"  Trailing aktiv: {agg['n_trailing_aktiv']} ({100.0*agg['n_trailing_aktiv']/agg['n']:.1f}%)  "
        f"| Stufen-Nachzuege (nur aktiv, mittel)={_fmt_zahl(agg['mean_stufen'])}  "
        f"| Pivots geprueft gesamt={agg['n_geprueft']}  | mittl. Haltedauer={_fmt_zahl(agg['mean_offset'], '.0f')} Bars"
    )
    return lines


def _bericht_fenster(fenster: str) -> str:
    """Baut den Report fuer ein Fenster (alle Konfigurationen)."""
    df, sigs = _signale_fenster(fenster)
    pivot_hi, pivot_lo = _pivot_stufen(df, 2)
    atr_arr = _atr_reihe(df, 7)

    # Standard-Konfiguration + Sensitivitaeten (F9-Option A, F10 1.0/2.0, F11-intrabar)
    base = TrailingConfig(fenster=fenster)
    laufe: List[Tuple[str, TrailingConfig, TrailingModus]] = [
        ("VAR_A_FIXED (Default)", base, "VAR_A_FIXED"),
        ("VAR_B_ATR mult=1.5 (Default)", base, "VAR_B_ATR"),
        ("SENS: VAR_A Option-A (Stufe>Initial)", replace(base, trailing_trigger="STUFE_UEBER_INITIAL"), "VAR_A_FIXED"),
        ("SENS: VAR_A Trailing intrabar", replace(base, trailing_exit="INTRABAR"), "VAR_A_FIXED"),
        ("SENS: VAR_B ATR mult=1.0", replace(base, atr_mult=1.0), "VAR_B_ATR"),
        ("SENS: VAR_B ATR mult=2.0", replace(base, atr_mult=2.0), "VAR_B_ATR"),
        ("REF: KEIN_TRAILING (nur F4-Stop)", base, "KEIN_TRAILING"),
    ]

    linie = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - SCHRITT 3: TRAILING A/B SIMULATION (tmp_setup_c_trailing.py)",
        f"Fenster: {fenster} | Symbol: SILVER M15 | Datum: 2026-09-05 | Baseline: {audit.BASELINE_REF}",
        "F9 Stufe>Entry | F10 max(1.5xATR7,0.15) | F11 Initial intrabar / Trailing close | DV1-DV6",
        linie,
        f"df-Bars: {len(df)} | SIGNAL-Signale: CONFIRMED="
        f"{sum(1 for s in sigs if s.arm=='CONFIRMED')} RAW={sum(1 for s in sigs if s.arm=='RAW')} "
        f"RETEST={sum(1 for s in sigs if s.arm=='RETEST')}",
        "",
    ]

    rows: List[List[str]] = []

    for label, cfg, modus in laufe:
        by_arm: Dict[str, List[TrailingResult]] = {"CONFIRMED": [], "RAW": [], "RETEST": []}
        for s in sigs:
            res = simuliere_signal(df, s, cfg, modus, pivot_hi, pivot_lo, atr_arr)
            by_arm[s.arm].append(res)

        txt.append(linie)
        txt.append(f"LAUF: {label}  |  modus={modus} | trigger={cfg.trailing_trigger} | exit={cfg.trailing_exit}")
        ges_sum: float = 0.0
        for arm in ("CONFIRMED", "RAW", "RETEST"):
            agg = _agg_block(by_arm[arm])
            ges_sum += agg["sum_r_f4"]
            txt.extend(_block_text(f"  ARM {arm}", agg))
        ges_agg = _agg_block([r for lst in by_arm.values() for r in lst])
        txt.append(f"  GESAMT  (n={ges_agg['n']}) sum r_f4={ges_agg['sum_r_f4']:.2f} "
                   f"mean={_fmt_zahl(ges_agg['mean_r_f4'])} WR={_fmt_zahl(ges_agg['wr'], '.1f')}% "
                   f"PF={_fmt_zahl(ges_agg['pf'])}")
        rows.append([label,
                     f"{_agg_block(by_arm['CONFIRMED'])['sum_r_f4']:.2f}",
                     f"{_agg_block(by_arm['RAW'])['sum_r_f4']:.2f}",
                     f"{_agg_block(by_arm['RETEST'])['sum_r_f4']:.2f}",
                     f"{ges_sum:.2f}"])
        txt.append("")

    # Kompakte Vergleichstabelle
    txt.append(linie)
    txt.append("VERGLEICH  (sum r_f4 je Arm; F4-R-Basis)")
    txt.append("  Lauf                             CONFIRMED       RAW     RETEST   GESAMT")
    for row in rows:
        txt.append(f"  {row[0]:<32} {row[1]:>10} {row[2]:>10} {row[3]:>10} {row[4]:>12}")
    txt.append(linie)

    text: str = "\n".join(txt)
    out: Path = TEST_DIR / f"tmp_setup_c_trailing_{fenster}.txt"
    out.write_text(text, encoding="utf-8")
    return text


# ==============================================================================
# 5) MAIN
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt die Trailing-Simulation fuer Fenster aus.

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
    if fenster == "ALLE":
        fenster_list: List[str] = ["AUG", "S1", "S2"]
    elif fenster in ("AUG", "S1", "S2"):
        fenster_list = [fenster]
    else:
        raise SystemExit(f"Unbekanntes Fenster: {fenster} (AUG|S1|S2|ALLE)")
    for f in fenster_list:
        text = _bericht_fenster(f)
        print(text)
        print(f"\nReport geschrieben: {TEST_DIR / f'tmp_setup_c_trailing_{f}.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
