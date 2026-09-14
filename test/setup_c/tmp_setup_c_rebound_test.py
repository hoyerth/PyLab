"""
SETUP C - REBOUND ZWISCHENTEST AUG (test/tmp_setup_c_rebound_test.py)
======================================================================
Status: FREIGEGEBEN (G-3, 06.09.2026) - isolierter, diagnostischer
        Zwischentest, KEINE Produktions-Aenderung.
Doku:   docs/setup_c_experiment.md (Paragraf 5.2 Trailing-Baseline,
        Paragraf 5.3 Reversal/phasenloser Raum).
Baseline: scripts/setup_c_profil.py / scripts/setup_c_chart.py -
        BYTE-IDENTISCH UNANGETASTET (nur lesende Importe).
Arbeitsmodus: isoliertes, rein lesendes Replay (DuckDB read_only via
      scripts.market_segmentation.load_data). Ausgabe unter reports/setup_c/.

Zweck
-----
Diagnostischer Zwischentest OHNE Einstiegsfilter: Prueft fuer das Fenster
AUG, ob nach Phasenabschluss (2-Close-Bruch) tragfaehige Gegenbewegungen
(Rebound-Moves) existieren, bevor restriktive Einstiegsfilter nachgeschaltet
werden. Der Rebound-Fade steigt BLIND gegen den Breakout auf derselben Bar,
auf der der CONFIRMED-Trend-Arm kauft/verkauft - der direkte Konflikt ist
gewollt und wird im 300-dpi-PNG sichtbar.

Arretierte Modell-Details (Freigabe F-1/F-2, Mentor-Urteil 06.09.2026)
----------------------------------------------------------------------
1) Einstieg: open[brk_idx + 2] = erste Kerze NACH vollstaendiger
   2-Close-Bestaetigung (kein Lookahead auf Close 2; b+1 waere ein
   1-Close-Handel). Deckungsgleich zur CONFIRMED-Einstiegs-Konvention
   (b+2): Rebound-Fade und Trend-Entry stehen spiegelbildlich auf
   derselben Bar.
2) Richtung: Fade kontraer zum Bruch - Up-Bruch -> SHORT ("down"),
   Down-Bruch -> LONG ("up").
3) Initial-Stop (Option B mit Option A als Cap; arretierte Deckelung):
     SHORT: stop = min(max(high[b], high[b+1]) + stop_puffer,
                       entry + max_range_mult * Range)
     LONG:  stop = max(min(low[b],  low[b+1])  - stop_puffer,
                       entry - max_range_mult * Range)
     Range = U_final - L_final der Basis-Phase.
   Cap garantiert einen gueltigen Stop bei Gap-Opens ueber das
   Bruchkerzen-Extremum (sonst SL_UEBERSCHRITTEN, sl_usd <= 0).
4) Trade-Management: VOLLSTAENDIG indikatorgefuehrt ueber das bestehende
   Dynamic Trailing Variante B (EMA-20-Slope-Ratchet) - Defaults bewusst
   UNVERAENDERT (mindest_gewinn_r = 0.0, Crash-Sicherung N=300), damit der
   dokumentierte Sofort-Ratchet-Kollaps (SWING-Audit 2, §5.3) auch hier
   unverschleiert sichtbar bleibt. KEIN Lockout, KEINE Filter.
5) E2-Semantik strikt: Ueberlebt ein Trade das Datenende ohne Stop und
   ohne erreichte Crash-Schranke -> RECHTS_ZENSIERT, r_f4/r_ref = NaN
   (strikt aus Performance isoliert, keine Glattstellung zum letzten Close).
   DATEN_ENDE ist ein reiner Phasen-Status (b+2 > n-1), KEIN Exit-Grund.

Ausgabe (reports/setup_c/, deterministisch reproduzierbar)
-----------------------------------------------------------
    setup_c_rebound_AUG.txt                 Status-Triage + Aggregat + Detail
    setup_c_rebound_trades_AUG.tsv          Trade-Block (maschinenlesbar)
    setup_c_rebound_AUG.png                 300 dpi (Phasen, Bruch-Marker,
                                            CONFIRMED-Referenz, Rebound-Pfeile,
                                            gestrichelter Trailing-Pfad)

Aufruf (Projekt-Root):
    python test/tmp_setup_c_rebound_test.py [--fenster=AUG] [--dpi=300]
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from scripts.market_segmentation import (  # noqa: E402
    PhaseData,
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)
from scripts.setup_c_profil import (  # noqa: E402
    FENSTER_DEFS,
    _agg_block,
    _block_text,
    _fmt,
    berechne_ema_slope_vektoren,
)

_REPORT_DIR: Path = PROJECT_ROOT / "reports" / "setup_c"

# ---------------------------------------------------------------------------
# Chart-Farben (Konsistent zu setup_c_chart.py)
# ---------------------------------------------------------------------------
_COL_EMA: str = "#1565c0"
_COL_UP: str = "#1a7d1a"      # Entry LONG  (^)
_COL_DOWN: str = "#c00000"    # Entry SHORT (v)
_COL_SL: str = "#c00000"      # Exit Initial-Stop intrabar (x rot)
_COL_TR: str = "#e65100"      # Exit EMA-Trailing-Stop intrabar (x orange)
_COL_CRASH: str = "#6a1b9a"   # Exit Crash-Sicherung (x lila)
_COL_ZENS: str = "#777777"    # Exit rechts-zensiert E2 (x grau)
_COL_REF: str = "#888888"     # CONFIRMED-Referenz-Pfeil (grau)
_COL_BR_KANTE: str = "#6a0dad"

# =============================================================================
# 1) DATENVERTRAEGE (Freigabe G-1/G-3)
# =============================================================================

ReboundDir = Literal["up", "down"]  # Fade: Up-Bruch -> "down", Down-Bruch -> "up"
ReboundExitGrund = Literal[
    "INITIAL_SL_INTRABAR",   # F4-Initial-Stop (Bruchkerzen-Anker) intrabar
    "TRAILING_SL_INTRABAR",  # Variante-B-Ratchet nachgezogen, intrabar
    "CRASH_HORIZONT_CLOSE",  # Notfall-Schranke e+300, Close
    "RECHTS_ZENSIERT",       # E2: bis Datenende ueberlebt, r = NaN
]

ReboundPhaseStatus = Literal[
    "TRADE",                 # Einstieg platziert (open[b+2] existiert, sl_usd > 0)
    "RANGE_DEGENERIERT",     # Range = U_final - L_final nicht endlich > 0
    "SL_UEBERSCHRITTEN",     # Gap: entry >= stop (SHORT) / entry <= stop (LONG)
    "DATEN_ENDE",            # b+2 > n-1: kein Folge-Open
]


@dataclass(frozen=True, slots=True)
class ReboundConfig:
    """Konfiguration fuer den diagnostischen Rebound-Zwischentest (AUG).

    Defaults = arretierte Modell-Details (F-1/F-2); Aenderungen nur als
    dokumentierte Sensitivitaeten (nicht fuer den Freigabe-Lauf).
    """

    fenster: Literal["AUG"] = "AUG"
    symbol: str = "SILVER"
    timeframe: Literal["M15"] = "M15"
    ema_periode: int = 20
    mindest_gewinn_r: float = 0.0
    notfall_horizont_bars: int = 300
    stop_puffer: float = 0.15
    max_range_mult: float = 1.0
    sl_pct_ref: float = 0.45


@dataclass(slots=True)
class ReboundTradeResult:
    """Simulierter Rebound-Trade (duck-typt in AggBlock/_agg_block).

    RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2); exit_*/haltezeit dokumentieren
    das Datenende transparenzhalber (keine Glattstellung).
    """

    phase: int
    dir: ReboundDir
    brk_idx: int
    entry_idx: int
    entry_ts: pd.Timestamp
    entry_preis: float
    initial_stop: float
    sl_usd: float
    exit_idx: int
    exit_ts: pd.Timestamp
    exit_preis: float
    exit_grund: ReboundExitGrund
    haltezeit_bars: int
    r_f4: float
    r_ref: float
    # Ratchet-Punkte (Bar-Index, Stop) NACH einem Nachzug; Start implizit
    # (entry_idx, initial_stop). NUR bei Nachzug gefuellt (sonst None).
    trailing_pfad: Optional[Tuple[Tuple[int, float], ...]] = None


@dataclass(slots=True)
class ReboundPhaseDiagnose:
    """Diagnose-Objekt je echter Bruch-Phase (vollstaendige Populationstriage)."""

    phase: int
    brk_idx: int
    brk_dir: Literal["up", "down"]
    status: ReboundPhaseStatus
    trade: Optional[ReboundTradeResult] = None


# =============================================================================
# 2) ERFASSUNG & SIMULATION
# =============================================================================


def _erfasse_und_simuliere_phase(
    df: pd.DataFrame,
    p: PhaseData,
    nr: int,
    cfg: ReboundConfig,
    ema_arr: np.ndarray,
    slope_arr: np.ndarray,
) -> ReboundPhaseDiagnose:
    """Prueft Einstiegsvoraussetzungen und simuliert den Rebound-Fade.

    Kausalitaet (1:1-Adaption der Phase-1/E1-E2-Reihe und des arretierten
    EMA-Slope-Trailing-Kerns, §5.2): Bar fuer Bar ab Einstieg
    ``e = brk_idx + 2`` bis ``min(e+N, Datenende)`` mit N = Notfall-Schranke
    300. Reihenfolge je Bar:
      1) Stop intrabar mit dem AKTUELLEN Stop-Niveau (initial =
         Bruchkerzen-Deckelung, danach Ratchet) - VORRANG, auch auf der
         Entry-Bar.
      2) Crash-Sicherung am Close der Bar e+N (CRASH_HORIZONT_CLOSE).
      3) Variante-B-Ratchet: Slope-Kipp in die Schutzrichtung -> Stop auf
         das Extremum DIESER Kerze; Monotonie-Pflicht (nie Risiko
         vergroessern); optionales Gewinnschwellen-Gate.
    Ueberlebt der Trade das Datenende -> RECHTS_ZENSIERT (E2, r = NaN).

    Args:
        df: OHLCV-DataFrame.
        p: PhaseData-Objekt (echter 2-Close-Bruch).
        nr: Phasennummer (1-basiert, deckungsgleich KernelTrade.phase).
        cfg: ReboundConfig.
        ema_arr: Kausaler Close-EMA-Vektor ueber df (len(df); ungenutzt im
            Kern, nur fuer die Vertrags-Paritaet vorgehalten).
        slope_arr: Kausaler 1-Bar-Slope-Vektor ueber df (len(df)).

    Returns:
        ReboundPhaseDiagnose (TRADE mit Trade oder Diagnose-Status).
    """
    assert p.brk_idx is not None and p.break_dir is not None
    b: int = int(p.brk_idx)
    n: int = len(df)
    rev_dir: ReboundDir = "down" if p.break_dir == "up" else "up"

    # --- Range der Basis-Phase (Stop-Cap) -----------------------------------
    if p.U_final is None or p.L_final is None:
        return ReboundPhaseDiagnose(nr, b, p.break_dir, "RANGE_DEGENERIERT")
    range_breite: float = float(p.U_final) - float(p.L_final)
    if not (np.isfinite(range_breite) and range_breite > 0.0):
        return ReboundPhaseDiagnose(nr, b, p.break_dir, "RANGE_DEGENERIERT")

    # --- Einstieg open[b+2] (erste Kerze NACH 2-Close-Bestaetigung) ----------
    e: int = b + 2
    if e >= n:
        return ReboundPhaseDiagnose(nr, b, p.break_dir, "DATEN_ENDE")

    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    open_arr: np.ndarray = df["open"].values.astype(float)
    close: np.ndarray = df["close"].values.astype(float)
    entry: float = float(open_arr[e])

    # --- Initial-Stop: Bruchkerzen-Anker (B) mit Range-Cap (A) --------------
    if rev_dir == "down":  # SHORT-Fade (Up-Bruch): Stop oberhalb
        bruch_extrem: float = float(max(high[b], high[b + 1]))
        ungeckelt: float = bruch_extrem + cfg.stop_puffer
        stop_level: float = min(
            ungeckelt, entry + cfg.max_range_mult * range_breite
        )
        sl_usd: float = stop_level - entry
    else:  # LONG-Fade (Down-Bruch): Stop unterhalb
        bruch_extrem = float(min(low[b], low[b + 1]))
        ungeckelt = bruch_extrem - cfg.stop_puffer
        stop_level = max(
            ungeckelt, entry - cfg.max_range_mult * range_breite
        )
        sl_usd = entry - stop_level

    if not (np.isfinite(sl_usd) and sl_usd > 0.0):
        return ReboundPhaseDiagnose(nr, b, p.break_dir, "SL_UEBERSCHRITTEN")

    # --- Simulation (Variante B, Defaults unveraendert) ----------------------
    letzte_bar: int = n - 1
    ziel_bar: int = e + cfg.notfall_horizont_bars
    loop_ende: int = min(ziel_bar, letzte_bar)

    exit_grund: ReboundExitGrund = "RECHTS_ZENSIERT"  # Default: Datenende
    exit_idx: int = letzte_bar
    exit_preis: float = float(close[letzte_bar])
    akt_sl: float = float(stop_level)
    pfad: List[Tuple[int, float]] = []

    for k in range(e, loop_ende + 1):
        # 1) Stop intrabar mit aktuellem Niveau (Vorrang vor Crash-Schranke)
        if (rev_dir == "up" and low[k] <= akt_sl) or (
            rev_dir == "down" and high[k] >= akt_sl
        ):
            exit_preis, exit_idx = float(akt_sl), k
            exit_grund = (
                "INITIAL_SL_INTRABAR"
                if akt_sl == stop_level
                else "TRAILING_SL_INTRABAR"
            )
            break
        # 2) Crash-Sicherung am Close der Notfall-Bar (terminal)
        if k == ziel_bar:
            exit_preis, exit_idx, exit_grund = (
                float(close[k]), k, "CRASH_HORIZONT_CLOSE"
            )
            break
        # 3) Variante-B-Ratchet (Monotonie: nie Risiko vergroessern)
        slope_k: float = float(slope_arr[k])
        ratchet_ok: bool = cfg.mindest_gewinn_r <= 0.0
        if not ratchet_ok:
            fl_r: float = (
                (close[k] - entry) / sl_usd
                if rev_dir == "up"
                else (entry - close[k]) / sl_usd
            )
            ratchet_ok = fl_r >= cfg.mindest_gewinn_r
        if ratchet_ok and (
            (rev_dir == "up" and slope_k <= 0.0)
            or (rev_dir == "down" and slope_k >= 0.0)
        ):
            neuer_sl: float = float(low[k] if rev_dir == "up" else high[k])
            if (rev_dir == "up" and neuer_sl > akt_sl) or (
                rev_dir == "down" and neuer_sl < akt_sl
            ):
                akt_sl = neuer_sl
                pfad.append((k, akt_sl))

    haltezeit: int = exit_idx - e
    zensiert: bool = exit_grund == "RECHTS_ZENSIERT"
    if zensiert:
        r_f4: float = float("nan")
        r_ref: float = float("nan")
    else:
        diff: float = (
            (exit_preis - entry)
            if rev_dir == "up"
            else (entry - exit_preis)
        )
        r_f4 = diff / sl_usd
        r_ref_basis: float = entry * cfg.sl_pct_ref / 100.0
        r_ref = diff / r_ref_basis

    trade: ReboundTradeResult = ReboundTradeResult(
        phase=nr,
        dir=rev_dir,
        brk_idx=b,
        entry_idx=e,
        entry_ts=df["ts"].iloc[e],
        entry_preis=entry,
        initial_stop=float(stop_level),
        sl_usd=float(sl_usd),
        exit_idx=exit_idx,
        exit_ts=df["ts"].iloc[exit_idx],
        exit_preis=float(exit_preis),
        exit_grund=exit_grund,
        haltezeit_bars=haltezeit,
        r_f4=float(r_f4),
        r_ref=float(r_ref),
        trailing_pfad=tuple(pfad) if pfad else None,
    )
    return ReboundPhaseDiagnose(nr, b, p.break_dir, "TRADE", trade)


# =============================================================================
# 3) AGGREGATION & REPORT (duck-typt in die Produktions-Helfer)
# =============================================================================

_STATUS_REIHENFOLGE: Tuple[ReboundPhaseStatus, ...] = (
    "TRADE",
    "RANGE_DEGENERIERT",
    "SL_UEBERSCHRITTEN",
    "DATEN_ENDE",
)


def _trade_zeile(t: ReboundTradeResult) -> str:
    """Eine lesbare Trade-Zeile fuer den Textreport (forensisch)."""
    return (
        f"P{t.phase:>3} {str(t.dir):4s} b={t.brk_idx:>5} e={t.entry_idx:>5} "
        f"{str(t.entry_ts):>16} {t.entry_preis:>8.3f} {t.initial_stop:>8.3f} "
        f"{t.sl_usd:>7.3f} x={t.exit_idx:>5} {t.exit_grund:<22} "
        f"{t.haltezeit_bars:>4} {_fmt(t.r_f4):>8}"
    )


def _rebound_tsv(trades: Sequence[ReboundTradeResult], fenster: str) -> str:
    """Maschinenlesbarer Trade-Block (TSV) fuer den Rebound-Zwischentest.

    Args:
        trades: Simulierte Rebound-Trades.
        fenster: Fenster-Label (AUG).

    Returns:
        TSV-Text (Kommentarzeilen + Header + Datenzeilen).
    """
    kopf: List[str] = [
        f"# setup_c REBOUND Zwischentest (isolierter Audit) - Fenster: {fenster}",
        "# Modell: Fade kontraer zum 2-Close-Bruch | open[brk_idx+2] | "
        "Bruchkerzen-Stop + Range-Cap | EMA-Slope-Trailing Variante B",
        "# RECHTS_ZENSIERT: r_f4/r_ref = NaN (E2, strikt isoliert)",
    ]
    header: str = (
        "phase\tdir\tbrk_idx\tentry_idx\tentry_ts\tentry_preis\t"
        "initial_stop\tsl_usd\texit_idx\texit_ts\texit_preis\t"
        "exit_grund\thaltezeit_bars\tr_f4\tr_ref"
    )
    zeilen: List[str] = [*kopf, header]
    for t in sorted(trades, key=lambda x: (x.entry_idx, x.phase, x.dir)):
        zeilen.append(
            f"{t.phase}\t{t.dir}\t{t.brk_idx}\t{t.entry_idx}\t"
            f"{t.entry_ts}\t{t.entry_preis:.5f}\t{t.initial_stop:.5f}\t"
            f"{t.sl_usd:.5f}\t{t.exit_idx}\t{t.exit_ts}\t{t.exit_preis:.5f}\t"
            f"{t.exit_grund}\t{t.haltezeit_bars}\t{_fmt(t.r_f4)}\t{_fmt(t.r_ref)}"
        )
    return "\n".join(zeilen)


# =============================================================================
# 4) CHART (300 dpi; Phasen, Bruch-Marker, Referenz, Trades, Stop-Pfad)
# =============================================================================


def _chart_stat_zeilen(cfg: ReboundConfig, trades: Sequence[ReboundTradeResult]) -> List[str]:
    """Kompakte Statistik-Zeilen fuer die Chart-Box (AggBlock-basiert)."""
    agg = _agg_block(trades)
    n_gew: int = agg.n_gewertet
    n_win: int = int(round(agg.wr * n_gew / 100.0)) if n_gew else 0
    n_loss: int = n_gew - n_win
    exit_teile: List[str] = [
        f"INITIAL_SL_INTRABAR={agg.n_init}",
    ]
    if agg.n_trailing:
        exit_teile.append(f"TRAILING_SL_INTRABAR={agg.n_trailing}")
    if agg.n_crash:
        exit_teile.append(f"CRASH_HORIZONT_CLOSE={agg.n_crash}")
    exit_teile.append(f"RECHTS_ZENSIERT={agg.n_zensiert}")
    return [
        "SETUP C REBOUND-ZWISCHENTEST | "
        f"Fenster {cfg.fenster} | EMA-Slope-Trailing (Variante B)",
        f"Modell: open[brk_idx+2] Fade | Stop: Bruchkerze+Cap | N={cfg.notfall_horizont_bars}",
        f"Trades: n={agg.n_kandidaten}  gewertet={n_gew}  zensiert={agg.n_zensiert}",
        f"Summe R (r_f4): {agg.sum_r_f4:+.2f}R   "
        f"Summe r_ref: {agg.sum_r_ref:+.2f}R",
        f"Mean R: {_fmt(agg.mean_r_f4)}   Median R: {_fmt(agg.median_r_f4)}",
        f"Winrate: {_fmt(agg.wr, '.1f')}%  ({n_win}W/{n_loss}L)",
        f"Profit Faktor: {_fmt(agg.pf)}",
        "Exit: " + " | ".join(exit_teile),
        f"mittl. Haltedauer: {_fmt(agg.mean_offset, '.0f')} Bars",
    ]


def _zeichne_rebound_aug(
    df: pd.DataFrame,
    sr: SegmentResult,
    diagnosen: Sequence[ReboundPhaseDiagnose],
    cfg: ReboundConfig,
    out_png: Path,
    dpi: int,
) -> None:
    """Rendert den Rebound-Chart (300 dpi, Single-Panel, Produktions-Konvention).

    Inhalte: Preis (high/low), EMA(Close)-Overlay, Phasen-Hintergruende
    (Span [start, ende] mit ``side='right'-1`` wie setup_c_chart.py),
    Bruch-Marker an ``brk_idx`` (lila gestrichelt), graue CONFIRMED-Referenz-
    Pfeile an Bar ``b+2`` (gleiche Bar wie der Rebound-Entry = spiegelbildlicher
    Konflikt), Rebound-Entry-Pfeile (farbig), Exit-Marker (x, Exit-Farbe),
    Trailing-Stop-Pfad (orange Stufenlinie, NUR Stop-Niveaus - kein Sprung zum
    Exit-Preis), Statistik-Box oben mittig.

    Args:
        df: OHLCV-DataFrame.
        sr: SegmentResult.
        diagnosen: ReboundPhaseDiagnosen (alle echten Brueche, Triage).
        cfg: ReboundConfig.
        out_png: Zielpfad der PNG-Datei.
        dpi: Aufloesung (Default 300).
    """
    idx: np.ndarray = df["idx"].values.astype(int)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: pd.Series = df["close"]
    ts_arr: np.ndarray = df["ts"].values

    fig, ax1 = plt.subplots(figsize=(17, 11))
    # --- Preis (high/low-Linien wie Produktions-Chart) ----------------------
    ax1.plot(idx, high, color="#bbbbbb", lw=0.5, zorder=1)
    ax1.plot(idx, low, color="#bbbbbb", lw=0.5, zorder=1)

    # --- EMA(Close) als blaue Overlay-Linie ---------------------------------
    ema: np.ndarray = (
        close.ewm(
            span=cfg.ema_periode, adjust=False, min_periods=cfg.ema_periode
        )
        .mean()
        .to_numpy(dtype=float, copy=True)
    )
    ax1.plot(idx, ema, color=_COL_EMA, lw=1.0, zorder=2,
             label=f"EMA({cfg.ema_periode}) (Close)")

    # --- Phasen-Hintergruende (Span [start, ende], side='right'-1) ----------
    for p in sr.phases:
        i0: int = int(np.searchsorted(ts_arr, np.datetime64(p.start), side="left"))
        i1: int = int(np.searchsorted(ts_arr, np.datetime64(p.ende), side="right")) - 1
        if i1 < i0:
            continue
        ax1.axvspan(i0, i1, color="#1f77b4", alpha=0.06, zorder=0)

    trades: List[ReboundTradeResult] = [
        d.trade for d in diagnosen if d.trade is not None
    ]
    exit_grunde: set = {str(t.exit_grund) for t in trades}

    # --- Diagnosen: Bruch-Marker + CONFIRMED-Referenz + Rebound-Trades -------
    for d in diagnosen:
        b: int = d.brk_idx
        ax1.axvline(b, color=_COL_BR_KANTE, linestyle=":", alpha=0.7,
                    linewidth=1.0, zorder=2)
        # Grauer CONFIRMED-Referenz-Pfeil an Bar b+2 (Richtung = Bruchrichtung)
        e_ref: int = b + 2
        if e_ref < len(df):
            if d.brk_dir == "up":
                ax1.scatter(e_ref, float(low[e_ref]) - 0.06, marker="^",
                            color=_COL_REF, s=42, zorder=4)
            else:
                ax1.scatter(e_ref, float(high[e_ref]) + 0.06, marker="v",
                            color=_COL_REF, s=42, zorder=4)

        if d.trade is None:
            continue
        t: ReboundTradeResult = d.trade
        e: int = int(t.entry_idx)
        x_ex: int = int(t.exit_idx)
        up: bool = t.dir == "up"
        grund: str = str(t.exit_grund)
        zensiert: bool = grund == "RECHTS_ZENSIERT"

        # Ergebnis-Farbe (zensiert neutral, sonst grün/rot)
        if zensiert:
            col_res: str = "#999999"
        else:
            col_res = "#2ca02c" if float(t.r_f4) >= 0.0 else "#d62728"
        if grund == "INITIAL_SL_INTRABAR":
            col_ex: str = _COL_SL
        elif grund == "TRAILING_SL_INTRABAR":
            col_ex = _COL_TR
        elif grund == "CRASH_HORIZONT_CLOSE":
            col_ex = _COL_CRASH
        else:
            col_ex = _COL_ZENS

        # Trailing-Stop-Pfad (orange Stufenlinie, NUR Stop-Niveaus)
        if t.trailing_pfad:
            p_x: List[int] = [e] + [int(k) for k, _ in t.trailing_pfad]
            p_y: List[float] = [float(t.initial_stop)] + [
                float(sl) for _, sl in t.trailing_pfad
            ]
            ax1.plot(p_x, p_y, drawstyle="steps-post", color=_COL_TR,
                     lw=1.2, alpha=0.9, zorder=2)
        else:
            ax1.hlines(float(t.initial_stop), e, x_ex, colors=_COL_TR,
                       linestyles="--", lw=1.0, alpha=0.7, zorder=2)

        # Verbindungslinie Entry -> Exit (Ergebnis-Farbe, dezent)
        ax1.plot([e, x_ex], [float(t.entry_preis), float(t.exit_preis)],
                 color=col_res, lw=0.7, alpha=0.45, zorder=3)
        # Entry-Marker + Beschriftung
        label_r: str = f"{t.r_f4:+.2f}R" if np.isfinite(float(t.r_f4)) else "ZENS"
        if up:
            ax1.scatter(e, float(t.entry_preis), marker="^", s=90,
                        color=_COL_UP, edgecolor="w", linewidths=0.5, zorder=6)
            ax1.annotate(f"P{t.phase} L {float(t.entry_preis):.2f}",
                         (e, float(t.entry_preis)),
                         xytext=(e + 2, float(t.entry_preis) + 0.30),
                         fontsize=7, color=_COL_UP, fontweight="bold", va="bottom")
        else:
            ax1.scatter(e, float(t.entry_preis), marker="v", s=90,
                        color=_COL_DOWN, edgecolor="w", linewidths=0.5, zorder=6)
            ax1.annotate(f"P{t.phase} S {float(t.entry_preis):.2f}",
                         (e, float(t.entry_preis)),
                         xytext=(e + 2, float(t.entry_preis) - 0.30),
                         fontsize=7, color=_COL_DOWN, fontweight="bold", va="top")
        # Exit-Marker + Beschriftung
        ax1.scatter(x_ex, float(t.exit_preis), marker="x", s=70, color=col_ex, zorder=7)
        ax1.annotate(
            f"{grund} {label_r}",
            (x_ex, float(t.exit_preis)),
            xytext=(x_ex - 2, float(t.exit_preis) + (0.32 if up else -0.32)),
            fontsize=6.2, color=col_ex, ha="right",
            va="bottom" if up else "top",
        )

    # --- Achsen / Titel / Statistik-Box / Legende ----------------------------
    step: int = max(16, int(len(df)) // 14)
    ticks: np.ndarray = np.arange(0, int(len(df)), step)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels(
        [df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
        rotation=45, ha="right", fontsize=8,
    )
    ax1.set_xlim(-1, int(len(df)))
    ax1.set_ylabel("USD")
    ax1.grid(alpha=0.3)
    start, ende = FENSTER_DEFS[cfg.fenster]
    ax1.set_title(
        f"SETUP C | {cfg.fenster} | REBOUND-ZWISCHENTEST (Fade open[brk_idx+2]) | "
        f"EMA-Slope-Trailing Variante B | Crash-Sicherung "
        f"N={cfg.notfall_horizont_bars} | {start} .. {ende} (ende-exkl.)"
    )
    stat_text: str = "\n".join(_chart_stat_zeilen(cfg, trades))
    ax1.text(
        0.5, 0.99, stat_text, transform=ax1.transAxes, fontsize=7.5,
        va="top", ha="center", family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf6e3",
                  edgecolor="gray", alpha=0.94),
        zorder=20,
    )

    legende: List[Line2D] = [
        Line2D([0], [0], color=_COL_EMA, lw=1.6, label=f"EMA({cfg.ema_periode}) (Close)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=_COL_UP, ms=9,
               label="Rebound LONG (Fade down-Bruch)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor=_COL_DOWN, ms=9,
               label="Rebound SHORT (Fade up-Bruch)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=_COL_REF, ms=7,
               label="CONFIRMED-Referenz (Trend, b+2)"),
        Line2D([0], [0], marker="x", color=_COL_SL, ms=7, ls="",
               label="Exit Initial-Stop intrabar"),
        Line2D([0], [0], marker="x", color=_COL_ZENS, ms=7, ls="",
               label="Exit rechts-zensiert (E2)"),
        Line2D([0], [0], color="#2ca02c", lw=1.6, label="Trade positiv (R>0)"),
        Line2D([0], [0], color="#d62728", lw=1.6, label="Trade negativ (R<0)"),
    ]
    if "TRAILING_SL_INTRABAR" in exit_grunde:
        legende.append(
            Line2D([0], [0], marker="x", color=_COL_TR, ms=7, ls="",
                   label="Exit EMA-Trailing-Stop (TR)")
        )
    if "CRASH_HORIZONT_CLOSE" in exit_grunde:
        legende.append(
            Line2D([0], [0], marker="x", color=_COL_CRASH, ms=7, ls="",
                   label="Exit Crash-Sicherung (CRASH)")
        )
    legende.append(
        Line2D([0], [0], color=_COL_TR, lw=1.6, ls="--",
               label="EMA-Trailing-Stop-Pfad (Ratchet)")
    )
    ax1.legend(handles=legende, loc="upper left", fontsize=7.5, framealpha=0.9)

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


# =============================================================================
# 5) RUNNER (AUG)
# =============================================================================


def run_rebound_audit(fenster: str = "AUG", dpi: int = 300) -> str:
    """Fuehrt den Rebound-Zwischentest fuer AUG aus (Report + TSV + PNG).

    Laedt AUG strikt lesend (DuckDB read_only), segmentiert, berechnet die
    kausalen EMA/Slope-Vektoren und simuliert je echter Bruch-Phase genau
    einen Rebound-Fade (open[brk_idx+2]). Auswertung: Status-Triage
    (ReboundPhaseStatus), Aggregation der Trades ueber die Produktions-Helfer
    (_agg_block/_block_text; E2 strikt isoliert) und 300-dpi-Chart.

    Args:
        fenster: AUG (einziger freigegebener Scope, F-2).
        dpi: PNG-Aufloesung.

    Returns:
        Reporttext (wird zusaetzlich als setup_c_rebound_AUG.txt geschrieben;
        Baseline-Artefakte bleiben byte-identisch unberuehrt).
    """
    if fenster != "AUG":
        raise SystemExit(
            f"Scope strikt auf AUG begrenzt (F-2); ungueltig: {fenster}"
        )
    start, ende = FENSTER_DEFS[fenster]
    seg_cfg: SegmentConfig = SegmentConfig(start=start, ende=ende)
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)

    cfg: ReboundConfig = ReboundConfig(fenster=fenster)  # type: ignore[arg-type]
    ema_arr, slope_arr = berechne_ema_slope_vektoren(df, cfg.ema_periode)
    echte: List[PhaseData] = [
        p for p in sr.phases if p.break_dir is not None and p.brk_idx is not None
    ]
    diagnosen: List[ReboundPhaseDiagnose] = [
        _erfasse_und_simuliere_phase(df, p, nr, cfg, ema_arr, slope_arr)
        for nr, p in enumerate(echte, start=1)
    ]

    # Status-Triage
    status_cnt: Dict[str, int] = {s: 0 for s in _STATUS_REIHENFOLGE}
    for d in diagnosen:
        status_cnt[str(d.status)] += 1

    trades: List[ReboundTradeResult] = [
        d.trade for d in diagnosen if d.trade is not None
    ]
    agg = _agg_block(trades)

    linie: str = "=" * 120
    txt: List[str] = [
        linie,
        "SETUP C - REBOUND-ZWISCHENTEST AUG (test/tmp_setup_c_rebound_test.py)",
        f"Fenster: {fenster} | Symbol: SILVER M15 | df-Bars: {len(df)} | "
        f"Segmente: {len(sr.phases)} | echte F3-Brueche: {len(echte)}",
        f"Modell: Fade kontraer zum 2-Close-Bruch (up->SHORT / down->LONG) | "
        f"Einstieg open[brk_idx+2] (KEIN Filter)",
        f"Stop: Bruchkerzen-Extremum +-{cfg.stop_puffer} gedeckelt auf "
        f"{cfg.max_range_mult}x Range (U_final-L_final) | "
        f"Trailing: EMA({cfg.ema_periode})-Slope Variante B | "
        f"mindest_gewinn_r={cfg.mindest_gewinn_r} | Crash-Sicherung "
        f"N={cfg.notfall_horizont_bars}",
        linie,
        "",
        "STATUS-TRIAGE (je echter Bruch-Phase genau 1 Kandidat):",
    ]
    for s in _STATUS_REIHENFOLGE:
        txt.append(f"  {s:<22}: {status_cnt[s]:>4}")
    txt.append("")
    txt.append(linie)
    txt.append(
        f"REBOUND-TRADES  |  Crash-Sicherung N = {cfg.notfall_horizont_bars}  "
        "(terminal; kein Zeit-Exit 48/96 - reines Trailing-Modell)"
    )
    txt.extend(_block_text("    REBOUND", agg))
    txt.append("")

    if trades:
        txt.append(linie)
        txt.append("TRADE-DETAIL (forensisch; phase dir brk entry ts "
                   "entry stop sl_usd exit_idx exit_grund haltezeit r_f4):")
        txt.append(
            "  " + f"{'Ph':>4} {'Dir':<4} {'Brk':>5} {'EIdx':>5} {'EntryTS':>16} "
            f"{'Entry':>8} {'Stop':>8} {'SL$':>7} {'XIdx':>5} "
            f"{'ExitGrund':<22} {'Hold':>4} {'r_f4':>8}"
        )
        for t in sorted(trades, key=lambda x: (x.entry_idx, x.phase, x.dir)):
            txt.append("  " + _trade_zeile(t))
        txt.append("")

    txt.append(linie)

    text: str = "\n".join(txt)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_txt: Path = _REPORT_DIR / f"setup_c_rebound_{fenster}.txt"
    out_txt.write_text(text, encoding="utf-8")
    out_tsv: Path = _REPORT_DIR / f"setup_c_rebound_trades_{fenster}.tsv"
    out_tsv.write_text(_rebound_tsv(trades, fenster), encoding="utf-8")
    out_png: Path = _REPORT_DIR / f"setup_c_rebound_{fenster}.png"
    _zeichne_rebound_aug(df, sr, diagnosen, cfg, out_png, dpi)
    return text


# =============================================================================
# 6) MAIN
# =============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: fuehrt den Rebound-Zwischentest (AUG) aus.

    Args:
        argv: Kommandozeilen-Argumente (Default: sys.argv[1:]).

    Returns:
        Exit-Code 0 bei Erfolg.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    fenster: str = "AUG"
    dpi: int = 300
    for a in args:
        if a.startswith("--fenster="):
            fenster = a.split("=", 1)[1].upper()
        elif a.startswith("--dpi="):
            dpi = int(a.split("=", 1)[1])
    if fenster != "AUG":
        raise SystemExit(
            f"Scope strikt auf AUG begrenzt (F-2); ungueltig: {fenster}"
        )
    text = run_rebound_audit(fenster, dpi)
    print(text)
    print(
        f"\nReport: {_REPORT_DIR / f'setup_c_rebound_{fenster}.txt'}\n"
        f"TSV:    {_REPORT_DIR / f'setup_c_rebound_trades_{fenster}.tsv'}\n"
        f"PNG:    {_REPORT_DIR / f'setup_c_rebound_{fenster}.png'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
