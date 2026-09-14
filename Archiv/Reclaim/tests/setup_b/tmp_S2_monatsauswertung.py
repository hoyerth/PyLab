# -*- coding: utf-8 -*-
"""S2-Monatsauswertung: Baseline-Lauf 2025-01-01..2025-12-01 -> je Monat
eine txt (Statistik + Trades) und eine HiRes-Zoom-PNG (Standard-Chart-Logik).

Rein lesend (I3/I4): keine Aenderung an scripts/. exec-Import der vollen
Baseline-Engine (Cut nach reclaim_signals.sort) reproduziert den Lauf bitgenau
(210 Signale, +99.88R -> gegen test/tmp_S2_monatslauf_trades.txt verifiziert).

Je Monat (Signal-Zeit UTC, Gruppierung nach Kalendermonat):
  - test/tmp_S2_monatslauf_YYYY-MM.txt  : Monats-Statistik + Trade-Liste
  - test/tmp_S2_monatslauf_YYYY-MM.png  : HiRes-Zoom (figsize 24x13, dpi 300)
    x-Achse auf Monatsbereich [Monatserster, naechster Monatserster) begrenzt;
    Zeichenlogik = Kopie von render_standard_chart (scripts/, Z. 2090-2347) mit
    zusaetzlichem xlim-Parameter (keine Mutation, reine Lese-Darstellung).
"""
from __future__ import annotations

import io
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path("test")
BASELINE_S2 = 99.88
WIN_REF = 672

# ---------------------------------------------------------------- exec-Import
src = io.open("scripts/phasen_volumen_profil.py", encoding="utf-8").read()
_marker = "reclaim_signals.sort(key=lambda s: s.ts)"
_cut = src.rindex(_marker) + len(_marker)
sys.argv = ["phasen_volumen_profil.py", "--start=2025-01-01", "--ende=2025-12-01"]
_mod = types.ModuleType("pvp_s2_monate")
_mod.__file__ = str(Path("scripts/phasen_volumen_profil.py").resolve())
sys.modules["pvp_s2_monate"] = _mod
ns = _mod.__dict__
with redirect_stdout(io.StringIO()):
    exec(compile(src[:_cut], "phasen_volumen_profil.py", "exec"), ns)  # noqa: S102

df = ns["df"]
phases = ns["phases"]
sigs: list = ns["reclaim_signals"]
tsa = df["ts"].values
print(f"df S2: {len(df)} Bars | Phasen {len(phases)} | Signale {len(sigs)}")

# ---------------------------------------------------------------- Log-Parsing + Mapping
log_txt = io.open("test/tmp_S2_monatslauf_trades.txt", encoding="utf-8").read()
log_txt = log_txt.split("Modus: --macro-live")[0]
trades: list[dict] = []
_in = False
for l in log_txt.splitlines():
    if l.startswith("TRADE-LOG"):
        _in = True
        continue
    if not _in or "|" not in l:
        continue
    p = [x.strip() for x in l.split("|")]
    if len(p) < 9 or not p[0].isdigit():
        continue
    bar = int(p[2])
    trades.append({"nr": int(p[0]), "phase": int(p[1]), "bar": bar,
                   "ts": pd.Timestamp(tsa[bar]), "dir": p[5],
                   "entry": float(p[6]), "r": float(p[8])})
s_sum = sum(t["r"] for t in trades)
assert len(trades) == 210 and abs(s_sum - BASELINE_S2) < 0.10, (len(trades), s_sum)
sig_by_bar = {s.bar: s for s in sigs}
mm = sum(1 for t in trades
         if t["bar"] in sig_by_bar and sig_by_bar[t["bar"]].typ == t["dir"]
         and abs(sig_by_bar[t["bar"]].einstieg_preis - t["entry"]) < 1e-6
         and sig_by_bar[t["bar"]].phase == t["phase"])
print(f"Mapping Log->Signal: {mm}/210 | Summe R {s_sum:+.2f}R")

# ---------------------------------------------------------------- Monatsgruppierung
months = sorted({t["ts"].strftime("%Y-%m") for t in trades})
print(f"Monate: {months}")

def stat_zeilen(grp):
    n = len(grp)
    w = [t for t in grp if t["r"] > 0]
    l = [t for t in grp if t["r"] < 0]
    nl = sum(1 for t in grp if t["r"] == 0)
    sumr = sum(t["r"] for t in grp)
    wr = len(w) / n * 100 if n else 0
    avgw = sum(t["r"] for t in w) / len(w) if w else 0
    avgl = sum(t["r"] for t in l) / len(l) if l else 0
    pf = (sum(t["r"] for t in w) / abs(sum(t["r"] for t in l))
          if l and abs(sum(t["r"] for t in l)) > 1e-9 else float("inf"))
    nlong = sum(1 for t in grp if t["dir"] == "LONG")
    nshort = n - nlong - nl
    voll = sum(1 for t in grp if t["r"] <= -0.99)
    return (f"Monat: {grp[0]['ts']:%Y-%m} | Trades {n} (Long {nlong}/Short {nshort}) | "
            f"WR {wr:.1f}% | SumR {sumr:+.2f}R | AvgW {avgw:+.2f}R | "
            f"AvgL {avgl:+.2f}R | PF {pf:.2f} | Voll-SL {voll}")

for m in months:
    grp = [t for t in trades if t["ts"].strftime("%Y-%m") == m]
    grp.sort(key=lambda x: x["ts"])
    lines = []
    lines.append("=" * 100)
    lines.append(f"S2-MONATSBERICHT {m} | Baseline phasen_volumen_profil.py | "
                 f"Fenster 2025-01-01..2025-12-01 | Gesamt +99.88R")
    lines.append("=" * 100)
    lines.append(stat_zeilen(grp))
    lines.append("-" * 100)
    lines.append(f"{'#':>3} {'Ph':>3} {'Zeit (UTC)':<17} {'Dir':<5} {'Entry':>8} "
                 f"{'R':>7} {'Kante U':>8} {'Kante L':>8} {'POC':>8}")
    lines.append("-" * 100)
    for t in grp:
        s = sig_by_bar[t["bar"]]
        lines.append(f"{t['nr']:>3} {t['phase']:>3} {t['ts']:%d.%m.%Y %H:%M} "
                     f"{t['dir']:<5} {t['entry']:>8.3f} {t['r']:>+7.2f} "
                     f"{s.U_laufend:>8.3f} {s.L_laufend:>8.3f} {s.POC:>8.3f}")
    out_txt = OUT_DIR / f"tmp_S2_monatslauf_{m}.txt"
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[MONAT] {m}: {len(grp)} Trades -> {out_txt.name}")

# ---------------------------------------------------------------- HiRes-Zoom-PNG je Monat
def render_monat_png(m: str, grp: list[dict]) -> Path:
    """Zoom-Chart fuer Kalendermonat m (xlim auf Monatsbereich), HiRes 24x13/300."""
    t_start = pd.Timestamp(m + "-01", tz=None)
    t_ende = (t_start + pd.offsets.MonthBegin(1))
    ts_arr = pd.to_datetime(df["ts"])
    x0 = int(np.searchsorted(ts_arr, t_start, side="left"))
    x1 = int(np.searchsorted(ts_arr, t_ende, side="left")) - 1
    x0 = max(0, x0); x1 = min(len(df) - 1, x1)
    if x1 < x0:
        raise RuntimeError(f"Monat {m}: leerer Bar-Bereich")

    fig, ax = plt.subplots(figsize=(24, 13))
    idx = df["idx"].values
    ax.plot(idx, df["high"], color="#bbb", lw=0.5, zorder=1)
    ax.plot(idx, df["low"], color="#bbb", lw=0.5, zorder=1)

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for i_p, p in enumerate(phases):
        c = colors[i_p % len(colors)]
        ax.axvspan(p.i_start, p.i_ende, color=c, alpha=0.07, zorder=0)
        vz = p.vol_zone
        if vz is None:
            continue
        ax.hlines(vz.U_zone, p.i_start, p.i_ende, color="#1a7d1a", lw=2.4, alpha=0.95, zorder=3)
        ax.hlines(vz.L_zone, p.i_start, p.i_ende, color="#c00000", lw=2.4, alpha=0.95, zorder=3)
        ax.hlines(vz.POC, p.i_start, p.i_ende, color="#e07b00", lw=1.8, ls="-.", zorder=3)
        ax.text(p.i_start + 2, vz.U_zone + 0.10, f"OBEN(VAH) {vz.U_zone:.2f}",
                fontsize=9, color="#1a7d1a", fontweight="bold", va="bottom")
        ax.text(p.i_start + 2, vz.L_zone - 0.10, f"UNTEN(VAL) {vz.L_zone:.2f}",
                fontsize=9, color="#c00000", fontweight="bold", va="top")
        ax.text(p.i_start + 2, vz.POC + 0.10, f"POC {vz.POC:.2f}",
                fontsize=9, color="#e07b00", fontweight="bold", va="bottom")
        for j_pk, pk in enumerate(vz.peaks, 1):
            if j_pk == 1 and vz.n_mountains == 1:
                continue
            ax.hlines(pk.vah, p.i_start, p.i_ende, color="#2ca02c", lw=1.0, ls=":", alpha=0.75)
            ax.hlines(pk.val, p.i_start, p.i_ende, color="#d62728", lw=1.0, ls=":", alpha=0.75)
            ax.hlines(pk.poc, p.i_start, p.i_ende, color="#e07b00", lw=0.9, ls=":", alpha=0.75)
        if p.U_final is not None:
            ax.hlines(p.U_final, p.i_start, p.i_ende, color="k", lw=1.6, ls="--", alpha=0.55)
            ax.text(p.i_start + 2, p.U_final + 0.28, f"REAKTION OBEN {p.U_final:.2f}",
                    fontsize=8.5, color="k", alpha=0.8, fontweight="bold", va="bottom")
        if p.L_final is not None:
            ax.hlines(p.L_final, p.i_start, p.i_ende, color="k", lw=1.6, ls="--", alpha=0.55)
            ax.text(p.i_start + 2, p.L_final - 0.28, f"REAKTION UNTEN {p.L_final:.2f}",
                    fontsize=8.5, color="k", alpha=0.8, fontweight="bold", va="top")

    # Signale im Monat (Dreieck: SHORT v unten/rot, LONG ^ oben/gruen; gefuellt = in_bar)
    n_in = n_nb = 0
    for s in sigs:
        if not (x0 <= s.bar <= x1):
            continue
        x = int(s.bar)
        if s.typ == "SHORT":
            y = float(df["high"].iloc[x]); col = "#c00000"; mk = "v"
        else:
            y = float(df["low"].iloc[x]); col = "#1a7d1a"; mk = "^"
        gef = s.reclaim == "in_bar"
        n_in += 1 if gef else 0
        n_nb += 0 if gef else 1
        if gef:
            ax.scatter(x, y, marker=mk, s=60, color=col, zorder=6, edgecolor="w", linewidths=0.4)
        else:
            ax.scatter(x, y, marker=mk, s=60, facecolors="none", edgecolors=col,
                       linewidths=1.0, zorder=6)

    # Statistik-Box (Monat)
    z = stat_zeilen(grp)
    ax.text(0.30, 0.985, z, transform=ax.transAxes, fontsize=10, va="top", ha="left",
            family="monospace", bbox=dict(boxstyle="round,pad=0.45", facecolor="#fdf6e3",
                                          edgecolor="gray", alpha=0.95))

    step = max(8, (x1 - x0) // 20)
    ticks = np.arange(x0, x1 + 1, step)
    ax.set_xticks(ticks)
    ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
                       rotation=45, ha="right", fontsize=9)
    ax.set_xlim(x0 - 1, x1 + 1)
    ax.set_title(f"SILVER M15 | S2-Baseline | Monat {m} | Trades {len(grp)} | "
                 f"{t_start:%d.%m.%Y} - {t_ende - pd.Timedelta(minutes=15):%d.%m.%Y} "
                 f"| in_bar {n_in} / next_bar {n_nb}", fontsize=14)
    ax.set_ylabel("USD")
    ax.grid(alpha=0.3)

    legend_elements = [
        Line2D([0], [0], color="#1a7d1a", lw=2.4, label="Tier-1 Kante OBEN (VAH)"),
        Line2D([0], [0], color="#c00000", lw=2.4, label="Tier-1 Kante UNTEN (VAL)"),
        Line2D([0], [0], color="#e07b00", lw=1.8, ls="-.", label="MITTE (POC)"),
        Line2D([0], [0], color="k", lw=1.6, ls="--", label="REAKTIONS-Extreme"),
        Line2D([0], [0], marker="v", color="w", mfc="#c00000", ms=9, label="Reclaim SHORT in_bar"),
        Line2D([0], [0], marker="v", color="w", mfc="none", mec="#c00000", ms=9,
               label="Reclaim SHORT next_bar"),
        Line2D([0], [0], marker="^", color="w", mfc="#1a7d1a", ms=9, label="Reclaim LONG in_bar"),
        Line2D([0], [0], marker="^", color="w", mfc="none", mec="#1a7d1a", ms=9,
               label="Reclaim LONG next_bar"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, framealpha=0.95)

    fig.tight_layout()
    out_png = OUT_DIR / f"tmp_S2_monatslauf_{m}.png"
    fig.savefig(out_png, dpi=300)
    plt.close(fig)
    return out_png

for m in months:
    grp = [t for t in trades if t["ts"].strftime("%Y-%m") == m]
    grp.sort(key=lambda x: x["ts"])
    out_png = render_monat_png(m, grp)
    print(f"[PNG] {m}: {out_png.name} ({round(out_png.stat().st_size/1024,1)} KB)")
