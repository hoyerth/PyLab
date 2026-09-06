"""
SETUP C - CHART-REPORT (scripts/setup_c_chart.py)
==================================================
Erzeugt fuer den Phase-1-Baseline-Kern (RAW-Cluster A, F4 intrabar +
terminaler Zeit-Exit 48/96, suppression_phasenlokal=True) je Fenster und
Zeit-Horizont eine PNG-Datei (300 dpi) mit:

  - Preis (high/low-Linien) + dezenten Phasen-Hintergruenden
  - EMA(Close)-Linie (blau, Projektkonvention Periode 20, kausal wie
    ``regime_filter.berechne_zeitreihen_indikatoren``)
  - Entry-/Exit-Markern je Trade (F4-Stop intrabar / Zeit-Exit /
    rechts-zensiert)
  - Statistik-Box (oben mittig) inkl. Winrate, PF, max. Gewinn-/Verlustserie,
    max. Drawdown (R)

Ohne separates CRV-Panel: Der Preis-Chart (inkl. EMA-Overlay, Phasen,
Trade-Marker) fuellt das gesamte Bild (Single-Panel).

sowie je Fenster eine TXT-Datei mit Statistik-Header (beide Horizonte) und
allen Trades inkl. Zeitstempeln (entry_ts/exit_ts). Bei Teil-Laeufen
(``--n=`` mit nur einem Horizont) wird ein separater TXT
``setup_c_chart_{FENSTER}_N{N}.txt`` geschrieben; der kombinierte
``setup_c_chart_{FENSTER}.txt`` bleibt dann unangetastet.

Referenz der simulierten Trades: ``scripts.setup_c_profil`` (KernelTrade,
unveraendert importiert; kein Eingriff in den Produktionskern). Rendering
adaptiert aus ``scripts/phasen_volumen_profil.py`` (matplotlib Agg,
monospace Statistik-Textbox, Phasen-Spans).

Aufruf (Projekt-Root, Namespace-Package):
    python scripts/setup_c_chart.py [--fenster=AUG|S1|S2|ALLE] [--n=48,96]
                                    [--ema=20] [--dpi=300]
    python scripts/setup_c_chart.py --fenster=AUG --ema-trailing

    --n=      Komma-Liste der Zeit-Horizonte (48|96), Default "48,96".
              Beispiel "nur AUG N48": --fenster=AUG --n=48
    --ema=    EMA-Periode fuer die Close-EMA-Overlay-Linie (Default 20).
    --ema-trailing
              EMA-Slope-Trailing-Chart (Variante B, §5.2): genau EIN Lauf
              je Fenster mit Crash-Sicherung (N=300); Stop-Pfade (Ratchet)
              als orange Stufenlinie, Exit-Typen TR/CRASH farblich getrennt.
              Ausgabe ``setup_c_chart_{FENSTER}_EMATRAIL.png`` (+ TXT).

Ausgabe (unversioniert, deterministisch reproduzierbar):
    reports/setup_c/setup_c_chart_{FENSTER}_N{N}.png
    reports/setup_c/setup_c_chart_{FENSTER}.txt        (Voll-Lauf 48+96)
    reports/setup_c/setup_c_chart_{FENSTER}_N{N}.txt   (Teil-Lauf, nur N)
    reports/setup_c/setup_c_chart_{FENSTER}_EMATRAIL.png/.txt  (--ema-trailing)
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from scripts.market_segmentation import SegmentResult, load_data, segmentiere_markt
from scripts.setup_c_profil import (
    EMASlopeTrailingConfig,
    FENSTER_DEFS,
    KernelTrade,
    SetupCSignal,
    TrendConfig,
    _erfasse_signale,
    _kern_lauefe,
)

# ---------------------------------------------------------------------------
# 1) PFADE & FARBEN
# ---------------------------------------------------------------------------

_PROJEKT_ROOT: Path = Path(__file__).resolve().parent.parent
_REPORT_DIR: Path = _PROJEKT_ROOT / "reports" / "setup_c"

_COL_PHASEN: Tuple[str, ...] = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
)
# EMA-Overlay (Projektkonvention Periode 20, kausal ewm(span, adjust=False),
# identische Semantik wie regime_filter.RegimeMetricConfig.ema_periode).
_EMA_DEFAULT_PERIODE: int = 20
_COL_EMA: str = "#1565c0"   # Close-EMA-Linie (blau, satt auf weiss/Phaesen-Spans)
_EMA_LW: float = 1.0
_COL_UP: str = "#1a7d1a"     # Entry LONG  (^)
_COL_DOWN: str = "#c00000"   # Entry SHORT (v)
_COL_SL: str = "#c00000"     # Exit F4-Stop intrabar      (x rot)
_COL_ZEIT: str = "#1f77b4"   # Exit Zeit-Exit am Close     (x blau)
_COL_ZENS: str = "#777777"   # Exit rechts-zensiert        (x grau)
_COL_TR: str = "#e65100"     # Exit EMA-Trailing-Stop      (x orange)
_COL_CRASH: str = "#6a1b9a"  # Exit Crash-Sicherung        (x lila)


# ---------------------------------------------------------------------------
# 2) STATISTIK (inkl. Serien & Drawdown)
# ---------------------------------------------------------------------------


def _gewertet(trades: Sequence[KernelTrade]) -> List[KernelTrade]:
    """Trades ohne RECHTS_ZENSIERT (E2: strikt isoliert, r=NaN)."""
    return [
        t
        for t in trades
        if t.exit_grund != "RECHTS_ZENSIERT" and np.isfinite(float(t.r_f4))
    ]


def _chronologisch(trades: Sequence[KernelTrade]) -> List[KernelTrade]:
    """Gewertete Trades in Exit-Reihenfolge (Basis fuer Serien/Drawdown)."""
    return sorted(
        _gewertet(trades), key=lambda t: (int(t.exit_idx), int(t.phase), str(t.dir))
    )


def _statistik(trades: Sequence[KernelTrade]) -> Dict[str, object]:
    """Liefert die Statistik-Kennzahlen eines Laufs (kein dict-Schlupf).

    Args:
        trades: Aktivierte KernelTrades eines (Fenster, Horizont)-Laufs.

    Returns:
        Typisiertes Kennzahlen-Dict (Summe R, WR, PF, Serien, Drawdown ...).
    """
    gew: List[KernelTrade] = _gewertet(trades)
    zens: int = sum(1 for t in trades if t.exit_grund == "RECHTS_ZENSIERT")
    rs: np.ndarray = np.array([float(t.r_f4) for t in gew], dtype=float)

    out: Dict[str, object] = {
        "n_kandidaten": len(trades),
        "n_zensiert": zens,
        "n_gewertet": int(len(rs)),
    }
    if len(rs) == 0:
        out.update(
            {
                "sum_r": 0.0,
                "sum_ref": 0.0,
                "mean": float("nan"),
                "median": float("nan"),
                "wr": 0.0,
                "pf": float("inf"),
                "bester": float("nan"),
                "schlechtester": float("nan"),
                "n_init": 0,
                "n_zeit": 0,
                "n_trailing": 0,
                "n_crash": 0,
                "hd_mean": float("nan"),
                "max_gewinn_serie": (0, 0.0),
                "max_verlust_serie": (0, 0.0),
                "max_drawdown_r": 0.0,
            }
        )
        return out

    pos: float = float(rs[rs > 0.0].sum())
    neg: float = float(-rs[rs < 0.0].sum())
    chron: List[KernelTrade] = _chronologisch(trades)
    cum: np.ndarray = np.cumsum(np.array([float(t.r_f4) for t in chron]))
    peak: np.ndarray = np.maximum.accumulate(cum)
    dd: np.ndarray = cum - peak  # <= 0

    # laengste Gewinn-/Verlustserie (Exit-Reihenfolge)
    best_w_len, best_w_sum = 0, 0.0
    best_l_len, best_l_sum = 0, 0.0
    cur_w_len, cur_w_sum = 0, 0.0
    cur_l_len, cur_l_sum = 0, 0.0
    for t in chron:
        r: float = float(t.r_f4)
        if r > 0.0:
            cur_w_len += 1
            cur_w_sum += r
            cur_l_len, cur_l_sum = 0, 0.0
            if cur_w_len > best_w_len:
                best_w_len, best_w_sum = cur_w_len, cur_w_sum
        elif r < 0.0:
            cur_l_len += 1
            cur_l_sum += r
            cur_w_len, cur_w_sum = 0, 0.0
            if cur_l_len > best_l_len:
                best_l_len, best_l_sum = cur_l_len, cur_l_sum
        else:  # r == 0: bricht beide Serien
            cur_w_len, cur_w_sum = 0, 0.0
            cur_l_len, cur_l_sum = 0, 0.0

    n_init: int = sum(1 for t in gew if t.exit_grund == "INITIAL_SL_INTRABAR")
    n_zeit: int = sum(1 for t in gew if t.exit_grund == "ZEIT_EXIT_CLOSE")
    n_trailing: int = sum(1 for t in gew if t.exit_grund == "TRAILING_SL_INTRABAR")
    n_crash: int = sum(1 for t in gew if t.exit_grund == "CRASH_HORIZONT_CLOSE")
    hds: List[int] = [int(t.haltezeit_bars) for t in gew]
    out.update(
        {
            "sum_r": float(rs.sum()),
            "sum_ref": float(sum(float(t.r_ref) for t in gew)),
            "mean": float(rs.mean()),
            "median": float(np.median(rs)),
            "wr": float(np.mean(rs > 0.0) * 100.0),
            "pf": float(pos / neg) if neg > 0.0 else float("inf"),
            "bester": float(rs.max()),
            "schlechtester": float(rs.min()),
            "n_init": n_init,
            "n_zeit": n_zeit,
            "n_trailing": n_trailing,
            "n_crash": n_crash,
            "hd_mean": float(np.mean(hds)) if hds else float("nan"),
            "max_gewinn_serie": (best_w_len, best_w_sum),
            "max_verlust_serie": (best_l_len, best_l_sum),
            "max_drawdown_r": float(dd.min()) if len(dd) else 0.0,
        }
    )
    return out


def _stat_zeilen(
    fenster: str,
    start: str,
    ende: str,
    horizont: int,
    trades: Sequence[KernelTrade],
    kennung: Optional[str] = None,
) -> List[str]:
    """Formatiert die Statistik-Zeilen (Textbox / TXT-Header, ASCII).

    Args:
        fenster: Fenster-Kennung (AUG|S1|S2).
        start: Fenster-Start (ISO-String).
        ende: Fenster-Ende exklusiv (ISO-String).
        horizont: Zeit-Horizont N (Basis: 48/96; Trailing: Crash-N).
        trades: Aktivierte KernelTrades eines Laufs.
        kennung: Optionale erste Zeile (z. B. EMA-Slope-Trailing). ``None``
            = Baseline-Standard (RAW-A).
    """
    s: Dict[str, object] = _statistik(trades)
    n_gew: int = int(s["n_gewertet"])
    n_win: int = int(round(float(s["wr"]) * n_gew / 100.0))
    n_loss: int = n_gew - n_win
    g_len, g_sum = s["max_gewinn_serie"]  # type: ignore[misc]
    l_len, l_sum = s["max_verlust_serie"]  # type: ignore[misc]

    def _fmt(v: object, f: str = ".2f") -> str:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "-"
        return f"{v:{f}}"

    if kennung is None:
        zeile0: str = f"SETUP C RAW-A BASELINE | Fenster {fenster} | N={horizont}"
    else:
        zeile0 = f"{kennung} | Fenster {fenster} | N={horizont}"

    exit_teile: List[str] = [
        f"INITIAL_SL_INTRABAR={int(s['n_init'])}",
        f"ZEIT_EXIT_CLOSE={int(s['n_zeit'])}",
    ]
    if int(s["n_trailing"]) > 0:
        exit_teile.append(f"TRAILING_SL_INTRABAR={int(s['n_trailing'])}")
    if int(s["n_crash"]) > 0:
        exit_teile.append(f"CRASH_HORIZONT_CLOSE={int(s['n_crash'])}")

    return [
        zeile0,
        f"Zeitraum: {start} .. {ende}  (ende-exklusiv)",
        f"Trades: n={int(s['n_kandidaten'])}  gewertet={n_gew}  "
        f"zensiert={int(s['n_zensiert'])}",
        f"Summe R (r_f4): {float(s['sum_r']):+.2f}R   "
        f"Summe r_ref: {float(s['sum_ref']):+.2f}R",
        f"Mean R: {_fmt(s['mean'])}   Median R: {_fmt(s['median'])}",
        f"Winrate: {float(s['wr']):.1f}%  ({n_win}W/{n_loss}L)",
        f"Profit Faktor: {_fmt(s['pf'])}",
        f"Bester Trade: {float(s['bester']):+.2f}R   "
        f"Schlechtester: {float(s['schlechtester']):+.2f}R",
        f"Max Gewinnserie: {g_len} (Summe {g_sum:+.2f}R)",
        f"Max Verlustserie: {l_len} (Summe {l_sum:+.2f}R)",
        f"Max Drawdown (R-Kurve): {float(s['max_drawdown_r']):+.2f}R",
        "Exit: " + " | ".join(exit_teile),
        f"mittl. Haltedauer: {_fmt(s['hd_mean'], '.0f')} Bars",
    ]


# ---------------------------------------------------------------------------
# 3) CHART (300 dpi, adaptiert aus phasen_volumen_profil.py)
# ---------------------------------------------------------------------------


def _zeichne_fenster_horizont(
    fenster: str,
    start: str,
    ende: str,
    horizont: int,
    df: pd.DataFrame,
    sr: SegmentResult,
    trades: Sequence[KernelTrade],
    out_png: Path,
    dpi: int,
    ema_periode: int = _EMA_DEFAULT_PERIODE,
    trailing_modus: bool = False,
) -> None:
    """Zeichnet Preis + EMA(Close) + Entry/Exit-Marker + Statistik-Box.

    Single-Panel (kein CRV-Unterpanel): Der Preis-Chart mit allen Overlays
    fuellt das gesamte Bild.

    Im Trailing-Modus (``trailing_modus=True``, EMA-Slope-Trailing Variante B)
    werden zusaetzlich die nachgezogenen Stop-Pfade (``KernelTrade.trailing_pfad``)
    als orange Stufenlinie gezeichnet und die Exit-Typen TRAILING_SL_INTRABAR /
    CRASH_HORIZONT_CLOSE farblich getrennt dargestellt.

    Die EMA-Linie ist ein reines Chart-Overlay (visuelle Regime-Referenz,
    kausal ``ewm(span=ema_periode, adjust=False, min_periods=ema_periode)``,
    identisch zur Semantik in ``regime_filter``). Sie geht NICHT in die
    simulierten Trades ein (diese kommen unveraendert aus dem Kernel).
    """
    idx: np.ndarray = df["idx"].values.astype(int)
    high: np.ndarray = df["high"].values.astype(float)
    low: np.ndarray = df["low"].values.astype(float)
    close: pd.Series = df["close"]

    fig, ax1 = plt.subplots(figsize=(17, 11))
    # --- Preis (high/low-Linien wie Reclaim-Chart) -------------------------
    ax1.plot(idx, high, color="#bbbbbb", lw=0.5, zorder=1)
    ax1.plot(idx, low, color="#bbbbbb", lw=0.5, zorder=1)

    # --- EMA(Close) als blaue Overlay-Linie (Regime-Referenz) --------------
    ema: np.ndarray = (
        close.ewm(
            span=ema_periode, adjust=False, min_periods=ema_periode
        )
        .mean()
        .to_numpy(dtype=float, copy=True)
    )
    ax1.plot(
        idx,
        ema,
        color=_COL_EMA,
        lw=_EMA_LW,
        zorder=2,
        label=f"EMA({ema_periode}) (Close)",
    )

    # --- Phasen-Hintergruende (dezent, Segmentierung) ----------------------
    ts_arr: np.ndarray = df["ts"].values
    for i_p, p in enumerate(sr.phases):
        i0: int = int(np.searchsorted(ts_arr, np.datetime64(p.start), side="left"))
        i1: int = int(np.searchsorted(ts_arr, np.datetime64(p.ende), side="right")) - 1
        if i1 < i0:
            continue
        ax1.axvspan(
            i0, i1, color=_COL_PHASEN[i_p % len(_COL_PHASEN)], alpha=0.07, zorder=0
        )

    # --- Trades: Entry/Exit-Marker + Verbindungslinie ----------------------
    legende: List[Line2D] = []
    exit_grunde_vorhanden: set = set()
    for t in sorted(trades, key=lambda x: (int(x.entry_idx), int(x.phase), str(x.dir))):
        e: int = int(t.entry_idx)
        x_ex: int = int(t.exit_idx)
        up: bool = t.dir == "up"
        grund: str = str(t.exit_grund)
        exit_grunde_vorhanden.add(grund)
        if grund == "RECHTS_ZENSIERT":
            col_res: str = "#999999"
            col_ex: str = _COL_ZENS
            grund_kurz: str = "ZENS"
        else:
            col_res = "#2ca02c" if float(t.r_f4) >= 0.0 else "#d62728"
            if grund == "INITIAL_SL_INTRABAR":
                col_ex, grund_kurz = _COL_SL, "SL"
            elif grund == "ZEIT_EXIT_CLOSE":
                col_ex, grund_kurz = _COL_ZEIT, "ZEIT"
            elif grund == "TRAILING_SL_INTRABAR":
                col_ex, grund_kurz = _COL_TR, "TR"
            elif grund == "CRASH_HORIZONT_CLOSE":
                col_ex, grund_kurz = _COL_CRASH, "CRASH"
            else:  # Fallback (sollte nicht auftreten)
                col_ex, grund_kurz = _COL_SL, "SL"

        # EMA-Trailing-Stop-Pfad (Variante B): Stufenlinie ab Initial-Stop
        if trailing_modus and t.trailing_pfad:
            p_x: List[int] = [e] + [int(k) for k, _ in t.trailing_pfad]
            p_y: List[float] = [float(t.f4_initial_stop)] + [
                float(sl) for _, sl in t.trailing_pfad
            ]
            ax1.plot(
                p_x,
                p_y,
                drawstyle="steps-post",
                color=_COL_TR,
                lw=1.1,
                alpha=0.85,
                zorder=2,
            )

        # Verbindungslinie Entry -> Exit (Ergebnis-Farbe, dezent)
        ax1.plot(
            [e, x_ex],
            [float(t.entry_preis), float(t.exit_preis)],
            color=col_res,
            lw=0.7,
            alpha=0.45,
            zorder=3,
        )
        # Entry-Marker
        if up:
            ax1.scatter(
                e,
                float(t.entry_preis),
                marker="^",
                s=75,
                color=_COL_UP,
                edgecolor="w",
                linewidths=0.5,
                zorder=6,
            )
            ax1.annotate(
                f"P{t.phase} L {float(t.entry_preis):.2f}",
                (e, float(t.entry_preis)),
                xytext=(e + 2, float(t.entry_preis) + 0.28),
                fontsize=6.5,
                color=_COL_UP,
                fontweight="bold",
                va="bottom",
            )
        else:
            ax1.scatter(
                e,
                float(t.entry_preis),
                marker="v",
                s=75,
                color=_COL_DOWN,
                edgecolor="w",
                linewidths=0.5,
                zorder=6,
            )
            ax1.annotate(
                f"P{t.phase} S {float(t.entry_preis):.2f}",
                (e, float(t.entry_preis)),
                xytext=(e + 2, float(t.entry_preis) - 0.28),
                fontsize=6.5,
                color=_COL_DOWN,
                fontweight="bold",
                va="top",
            )
        # Exit-Marker
        ax1.scatter(
            x_ex,
            float(t.exit_preis),
            marker="x",
            s=60,
            color=col_ex,
            zorder=7,
        )
        ax1.annotate(
            f"{grund_kurz} {float(t.r_f4):+.2f}R" if np.isfinite(float(t.r_f4)) else grund_kurz,
            (x_ex, float(t.exit_preis)),
            xytext=(x_ex - 2, float(t.exit_preis) + (0.30 if up else -0.30)),
            fontsize=6.0,
            color=col_ex,
            ha="right",
            va="bottom" if up else "top",
        )

    # --- Achsen / Titel / Statistik-Box (oben mittig) ----------------------
    step: int = max(16, int(len(df)) // 14)
    ticks: np.ndarray = np.arange(0, int(len(df)), step)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels(
        [df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    ax1.set_xlim(-1, int(len(df)))
    ax1.set_ylabel("USD")
    ax1.grid(alpha=0.3)
    if trailing_modus:
        ax1.set_title(
            f"SETUP C | {fenster} | EMA-Slope-Trailing (Variante B) | "
            f"Crash-Sicherung N={horizont} | {start} .. {ende} (ende-exkl.) | "
            f"F4 intrabar + EMA{ema_periode}-Ratchet"
        )
        stat_kennung: Optional[str] = "SETUP C EMA-SLOPE-TRAILING (Variante B)"
    else:
        ax1.set_title(
            f"SETUP C | {fenster} | RAW-Cluster A Baseline | Horizont N={horizont} "
            f"| {start} .. {ende} (ende-exkl.) | F4 intrabar + Zeit-Exit"
        )
        stat_kennung = None

    stat_text: str = "\n".join(
        _stat_zeilen(fenster, start, ende, horizont, trades, stat_kennung)
    )
    ax1.text(
        0.5,
        0.99,
        stat_text,
        transform=ax1.transAxes,
        fontsize=7.5,
        va="top",
        ha="center",
        family="monospace",
        bbox=dict(
            boxstyle="round,pad=0.4",
            facecolor="#fdf6e3",
            edgecolor="gray",
            alpha=0.94,
        ),
        zorder=20,
    )

    legende = [
        Line2D([0], [0], color=_COL_EMA, lw=1.6,
               label=f"EMA({ema_periode}) (Close)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=_COL_UP, ms=8,
               label="Entry LONG (RAW-A)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor=_COL_DOWN, ms=8,
               label="Entry SHORT (RAW-A)"),
        Line2D([0], [0], marker="x", color=_COL_SL, ms=7, ls="",
               label="Exit F4-Stop intrabar"),
        Line2D([0], [0], marker="x", color=_COL_ZEIT, ms=7, ls="",
               label="Exit Zeit-Exit Close"),
        Line2D([0], [0], marker="x", color=_COL_ZENS, ms=7, ls="",
               label="Exit rechts-zensiert (E2)"),
        Line2D([0], [0], color="#2ca02c", lw=1.6, label="Trade positiv (R>0)"),
        Line2D([0], [0], color="#d62728", lw=1.6, label="Trade negativ (R<0)"),
    ]
    if "TRAILING_SL_INTRABAR" in exit_grunde_vorhanden:
        legende.append(
            Line2D([0], [0], marker="x", color=_COL_TR, ms=7, ls="",
                   label="Exit EMA-Trailing-Stop (TR)")
        )
    if "CRASH_HORIZONT_CLOSE" in exit_grunde_vorhanden:
        legende.append(
            Line2D([0], [0], marker="x", color=_COL_CRASH, ms=7, ls="",
                   label="Exit Crash-Sicherung (CRASH)")
        )
    if trailing_modus and any(t.trailing_pfad for t in trades):
        legende.append(
            Line2D([0], [0], color=_COL_TR, lw=1.6, ls="-",
                   label="EMA-Trailing-Stop-Pfad (Ratchet)")
        )
    ax1.legend(handles=legende, loc="upper left", fontsize=7.5, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4) TXT (Statistik-Header + alle Trades inkl. Zeitstempel)
# ---------------------------------------------------------------------------


def _trade_zeile(t: KernelTrade) -> str:
    """Eine Trade-Zeile fuer die TXT (alle Spalten inkl. Timestamps)."""
    r_f4: str = f"{float(t.r_f4):+.2f}" if np.isfinite(float(t.r_f4)) else "-"
    r_ref: str = f"{float(t.r_ref):+.2f}" if np.isfinite(float(t.r_ref)) else "-"
    return (
        f"{t.horizont_bars:3d} | P{t.phase:<3d} | {str(t.dir):4s} | "
        f"{t.entry_ts.strftime('%Y-%m-%d %H:%M')} | {float(t.entry_preis):8.3f} | "
        f"{t.exit_ts.strftime('%Y-%m-%d %H:%M')} | {float(t.exit_preis):8.3f} | "
        f"{t.exit_grund:22s} | {int(t.haltezeit_bars):4d} | {r_f4:>7s} | {r_ref:>7s}"
    )


def _schreibe_txt(
    fenster: str,
    start: str,
    ende: str,
    laeufe: Dict[int, Sequence[KernelTrade]],
    out_txt: Path,
    kennung: Optional[str] = None,
) -> None:
    """Schreibt Statistik-Header (je Horizont aus ``laeufe``) + alle Trades.

    Args:
        fenster: Fenster-Kennung (AUG|S1|S2) fuer den Header.
        start: Fenster-Start (ISO-String).
        ende: Fenster-Ende exklusiv (ISO-String).
        laeufe: Mapping Horizont -> Trades (z. B. {48: ..., 96: ...} fuer
            den Voll-Lauf oder {48: ...} fuer einen Teil-Lauf).
        out_txt: Zielpfad der TXT-Datei.
        kennung: Optionale Statistik-Kennung (z. B. EMA-Slope-Trailing);
            ``None`` = Baseline-Standard.
    """
    zeilen: List[str] = []
    for horizont, trades in laeufe.items():
        zeilen.append("=" * 108)
        zeilen.extend(
            _stat_zeilen(fenster, start, ende, horizont, trades, kennung)
        )
        zeilen.append("=" * 108)
        zeilen.append("")
    zeilen.append("ALLE TRADES (chronologisch je Horizont, inkl. Zeitstempel):")
    zeilen.append(
        "  N | Phase | Dir  | Entry-TS          |   Entry | "
        "Exit-TS           |    Exit | Exit-Grund        |   HD |   r_f4 |  r_ref"
    )
    zeilen.append("-" * 108)
    for horizont, trades in laeufe.items():
        trades_sorted = sorted(
            list(trades),
            key=lambda x: (int(x.entry_idx), int(x.phase), str(x.dir)),
        )
        for t in trades_sorted:
            zeilen.append(_trade_zeile(t))
        if not trades_sorted:
            zeilen.append(f"{horizont:3d} | (keine Trades)")
    out_txt.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 5) REPORT-LAUF (je Fenster: beide Horizonte)
# ---------------------------------------------------------------------------


def _lauf_fenster(
    fenster: str,
    dpi: int,
    horizonte: Sequence[int] = (48, 96),
    ema_periode: int = _EMA_DEFAULT_PERIODE,
    ema_trailing: bool = False,
) -> None:
    """Chart-/TXT-Lauf fuer ein Fenster (AUG|S1|S2) und Horizont-Selektion.

    Args:
        fenster: Fenster-Kennung (AUG|S1|S2).
        dpi: Aufloesung der PNG-Ausgabe.
        horizonte: Zu simulierende Zeit-Horizonte (48/96). Teil-Laeufe
            schreiben einen separaten TXT ``..._N{H}.txt``; nur der
            Voll-Lauf (48+96) aktualisiert den kombinierten TXT.
        ema_periode: Periode der Close-EMA-Overlay-Linie im Chart.
        ema_trailing: True = EMA-Slope-Trailing-Chart (Variante B, §5.2):
            genau EIN Lauf mit Crash-Sicherung (N=notfall), Dateinamen
            ``setup_c_chart_{fenster}_EMATRAIL.png`` (+ TXT). Der
            Baseline-Pfad bleibt unveraendert.
    """
    start, ende = FENSTER_DEFS[fenster]
    cfg: TrendConfig = TrendConfig()
    seg_cfg = replace(cfg.segment, db_path=cfg.db_path, start=start, ende=ende)
    df: pd.DataFrame = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
    sr: SegmentResult = segmentiere_markt(df, seg_cfg)
    signale: List[SetupCSignal] = _erfasse_signale(sr, cfg)

    _REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # --- EMA-Slope-Trailing (A/B, §5.2): genau EIN Lauf (Crash-N) ----------
    if ema_trailing:
        cfg_t: TrendConfig = TrendConfig(
            ema_trailing=EMASlopeTrailingConfig(aktiviert=True)
        )
        tc: EMASlopeTrailingConfig = cfg_t.ema_trailing
        notfall: int = tc.notfall_horizont_bars
        trades, n_supp = _kern_lauefe(df, signale, cfg_t, notfall)
        if n_supp != 0:
            raise RuntimeError(
                f"{fenster}: Trailing-Suppression nicht No-op ({n_supp})."
            )
        out_png: Path = _REPORT_DIR / f"setup_c_chart_{fenster}_EMATRAIL.png"
        _zeichne_fenster_horizont(
            fenster, start, ende, notfall, df, sr, trades, out_png, dpi,
            tc.ema_periode, trailing_modus=True,
        )
        print(f"PNG  {out_png.name}  (n={len(trades)})")
        out_txt: Path = _REPORT_DIR / f"setup_c_chart_{fenster}_EMATRAIL.txt"
        _schreibe_txt(
            fenster, start, ende, {notfall: trades}, out_txt,
            kennung="SETUP C EMA-SLOPE-TRAILING (Variante B)",
        )
        print(f"TXT  {out_txt.name}")
        return

    laeufe: Dict[int, List[KernelTrade]] = {}
    for horizont in horizonte:
        trades, n_supp = _kern_lauefe(df, signale, cfg, horizont)
        if n_supp != 0:
            raise RuntimeError(
                f"{fenster}: RAW-A-Suppression nicht No-op ({n_supp})."
            )
        laeufe[horizont] = trades
        out_png: Path = _REPORT_DIR / f"setup_c_chart_{fenster}_N{horizont}.png"
        _zeichne_fenster_horizont(
            fenster, start, ende, horizont, df, sr, trades, out_png, dpi,
            ema_periode,
        )
        print(f"PNG  {out_png.name}  (n={len(trades)})")
    if set(horizonte) == {48, 96}:
        # Voll-Lauf: kombinierter TXT (beide Horizonte, wie bisher).
        out_txt: Path = _REPORT_DIR / f"setup_c_chart_{fenster}.txt"
    else:
        # Teil-Lauf: separater TXT, der kombinierte bleibt unangetastet.
        h_kenn: str = "_".join(str(h) for h in horizonte)
        out_txt = _REPORT_DIR / f"setup_c_chart_{fenster}_N{h_kenn}.txt"
    _schreibe_txt(fenster, start, ende, laeufe, out_txt)
    print(f"TXT  {out_txt.name}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: erzeugt Charts + TXT fuer AUG/S1/S2 (Baseline RAW-A, 48/96).

    Optionen (siehe Modul-Docstring):
        --fenster=AUG|S1|S2|ALLE   (Default ALLE)
        --n=48|96|48,96            Horizont-Selektion (Default 48,96)
        --ema=20                   Periode der Close-EMA-Overlay-Linie
        --dpi=300                  PNG-Aufloesung
        --ema-trailing             EMA-Slope-Trailing-Chart (Variante B)
    """
    args: List[str] = list(sys.argv[1:] if argv is None else argv)
    fenster_arg: str = "ALLE"
    dpi: int = 300
    horizont_arg: str = "48,96"
    ema_periode: int = _EMA_DEFAULT_PERIODE
    ema_trailing: bool = False
    for a in args:
        if a.startswith("--fenster="):
            fenster_arg = a.split("=", 1)[1].upper()
        elif a.startswith("--dpi="):
            dpi = int(a.split("=", 1)[1])
        elif a.startswith("--n="):
            horizont_arg = a.split("=", 1)[1]
        elif a.startswith("--ema="):
            ema_periode = int(a.split("=", 1)[1])
        elif a == "--ema-trailing":
            ema_trailing = True
    if ema_periode <= 0:
        raise SystemExit(f"Ungueltige EMA-Periode: {ema_periode} (> 0 noetig)")
    if fenster_arg == "ALLE":
        fenster_list: List[str] = ["AUG", "S1", "S2"]
    elif fenster_arg in ("AUG", "S1", "S2"):
        fenster_list = [fenster_arg]
    else:
        raise SystemExit(
            f"Unbekanntes Fenster: {fenster_arg} (AUG|S1|S2|ALLE)"
        )

    if ema_trailing:
        # Trailing-Chart: genau ein Lauf je Fenster (--n wird ignoriert).
        for f in fenster_list:
            print(f"=== Fenster {f} | EMA-Slope-Trailing (Variante B) ===")
            _lauf_fenster(f, dpi, ema_trailing=True, ema_periode=ema_periode)
        print(f"\nFertig. Ausgabeordner: {_REPORT_DIR}")
        return 0

    # Horizont-Selektion (Reihenfolge der Angabe bleibt erhalten, dedupliziert).
    horizonte: List[int] = []
    for teil in horizont_arg.split(","):
        teil = teil.strip()
        if not teil:
            continue
        h: int = int(teil)
        if h not in (48, 96):
            raise SystemExit(
                f"Unbekannter Horizont: {h} (erlaubt: 48|96, Komma-Liste)"
            )
        if h not in horizonte:
            horizonte.append(h)
    if not horizonte:
        horizonte = [48, 96]

    for f in fenster_list:
        print(f"=== Fenster {f} | Horizonte {horizonte} | EMA({ema_periode}) ===")
        _lauf_fenster(f, dpi, horizonte, ema_periode)
    print(f"\nFertig. Ausgabeordner: {_REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
