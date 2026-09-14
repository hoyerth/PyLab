# -*- coding: utf-8 -*-
"""READ-ONLY Sichtpruefung EXT (2026-08-03 .. 2026-09-12) -- H20.33-Vorlauf.

Zweck:
    Makro-Ueberblick 01.08.-11.09.2026 mit der arretierten V019-Engine:
    Kerzen, LEBENDER Kanten-Baum L_s(k) (zweistufig: zarte graue
    Lebensspanne + volle Farbe waehrend ``_lebt(e, k)``), engine-native
    Trades, die fuenf Event-Anker A-E sowie die V019-Adapter-Segmente --
    ab Bar 1288 bewusst kahl.

Abgrenzung (ADDITIV, keine Mutation):
    * Engine   test/tmp_kanten_engine_replay.py      SHA 53f28e1b...
    * Renderer test/tmp_png_aug_sichttest.py         SHA 500b5576...
    * Adapter  backtest_lab/phasen_regime_adapter.py SHA 770eda2c...
    Das ZP-Patchset des arretierten Renderers wird NICHT nachgebaut --
    gezeichnet werden die ENGINE-NATIVEN Trades (``_se_trades`` ungepatcht).
    Das ist bewusst und im Titel ausgewiesen.

Layout (drei Zeilen): Preis/Kanten oben, Kanten-Dichte mittig,
Tick-Aktivitaet unten. Y-Achse global auf die EXT-Spanne verriegelt.

Aufruf:
    .venv\\Scripts\\python.exe test\\tmp_png_ext_sichttest.py
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Final, List, Tuple

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE_PATH: Final[Path] = ROOT / "test" / "tmp_kanten_engine_replay.py"
ENGINE_SHA_SOLL: Final[str] = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
FENSTER: Final[str] = "EXT"
FENSTER_START: Final[str] = "2026-08-03"
FENSTER_ENDE: Final[str] = "2026-09-12"
V019_SEGMENT_ENDE: Final[int] = 1287          # letztes Adapter-Bar (A2_AUTO_77)
DPI: Final[int] = 300

# Anker: (kuerzel, von_bar, bis_bar, beschriftung). Bar-Werte sind die in
# H20.32/H20.33 notarisierten Event-Fenster (BKZ).
ANKER: Final[Tuple[Tuple[str, int, int, str], ...]] = (
    ("A", 836, 864, "14.08. Sweep/Expansion"),
    ("B", 1076, 1160, "18./19.08. Vakuum-Bruch"),
    ("C", 1780, 1820, "28.08. Exhaustion-Spike"),
    ("D", 1972, 2088, "01.-02.09. Kaskade"),
    ("E", 2598, 2718, "10.-11.09. Kaskade"),
)

C_UP: Final[str] = "#3d8f6d"
C_DN: Final[str] = "#c05656"
C_OBEN: Final[str] = "#d62728"
C_UNTEN: Final[str] = "#2ca02c"
C_KANTE_HIST: Final[str] = "#7f7f7f"
C_ANKER: Final[str] = "#8e44ad"

OUT_UEBERSICHT: Final[Path] = ROOT / "test" / "ext_sichttest_uebersicht.png"
OUT_KARTE: Final[Path] = ROOT / "test" / "ext_sichttest_kantenkarte.png"
OUT_PROTOKOLL: Final[Path] = ROOT / "test" / "ext_sichttest_out.txt"


def _lade_engine():
    """Laedt die arretierte Engine ohne Seiteneffekte (SHA wird geprueft)."""
    sha = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if sha != ENGINE_SHA_SOLL:
        raise SystemExit(f"Fremd-Engine: {sha[:16]}... (Soll "
                         f"{ENGINE_SHA_SOLL[:16]}...).")
    spec = importlib.util.spec_from_loader("ke_ext", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(ENGINE_PATH)
    sys.modules["ke_ext"] = mod
    exec(compile(ENGINE_PATH.read_text(encoding="utf-8"),
                 str(ENGINE_PATH), "exec"), mod.__dict__)
    return mod


def _edge_profil(e, xs: np.ndarray, wall_live: int
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """Kausale Kantenlinie, zweistufig (L_s(k) + Lebensspanne).

    Args:
        e: Kante (Engine ``_SEEdgeH``).
        xs: Bar-Array der Zeichnung.
        wall_live: ``cfg.wall_live_bars`` (Liveness-Fenster, 96).

    Returns:
        ``(y_lebend, y_spanne)``. ``y_lebend`` ist ``basis_bei(k)`` genau
        dann, wenn ``_lebt(e, k)`` und der level-definierende Pivot bestaetigt
        ist (``pivot_bar + 2 <= k``); sonst NaN. ``y_spanne`` traegt die
        Linie von der ersten Bestaetigung bis zum Verfall (grau, zart).
    """
    bs = np.array([b for b, _ in e.wicks], dtype=float)
    px = np.array([p for _, p in e.wicks], dtype=float)
    order = np.argsort(bs, kind="stable")
    bs, px = bs[order], px[order]

    if e.ist_prim_anker:
        basis = np.full(len(xs), float(e.basis), dtype=float)
        j_conf = np.full(len(xs), 1, dtype=int)      # Anker: definiert
    else:
        cmin = np.minimum.accumulate(px)
        cmax = np.maximum.accumulate(px)
        j_conf = np.searchsorted(bs, xs - 2.0, side="right")
        basis = np.full(len(xs), np.nan, dtype=float)
        m = j_conf >= 1
        vals = (cmin[j_conf[m] - 1] if e.seite == "OBEN"
                else cmax[j_conf[m] - 1])
        basis[m] = vals

    j_raw = np.searchsorted(bs, xs, side="right")
    last = np.where(j_raw >= 1,
                    bs[np.clip(j_raw - 1, 0, len(bs) - 1)], -1e18)
    lebend = (j_raw >= 1) & (last >= xs - wall_live) & (j_conf >= 1)
    y_lebend = np.where(lebend, basis, np.nan)
    y_spanne = np.where((j_conf >= 1) & (xs >= bs[0]), basis, np.nan)
    return y_lebend, y_spanne


def _zeichne_kerzen(ax, x: np.ndarray, op, hi, lo, cl) -> None:
    """Kerzen (Docht + Korpus) im uebergebenen Indexfenster."""
    from matplotlib.patches import Rectangle
    up = cl >= op
    ax.vlines(x, lo, hi, color=np.where(up, C_UP, C_DN), lw=0.5, zorder=2)
    bl = np.minimum(op, cl)
    bh = np.where(np.abs(cl - op) < 1e-9, 0.004, np.abs(cl - op))
    for xi, b0, hh, u in zip(x, bl, bh, up):
        ax.add_patch(Rectangle((xi - 0.30, b0), 0.60, hh,
                               facecolor=C_UP if u else C_DN,
                               edgecolor=C_UP if u else C_DN, lw=0.3,
                               zorder=3))


def _zeichne_anker(ax, y0: float, y1: float) -> None:
    """Anker A-E: halbtransparentes Band + Startlinie + 90-Grad-Label."""
    for kurz, b0, b1, txt in ANKER:
        ax.axvspan(b0, b1, color=C_ANKER, alpha=0.12, zorder=1)
        ax.axvline(b0, color=C_ANKER, lw=1.3, ls="-", alpha=0.85, zorder=4)
        ax.text(b0 + 3, y1, f"{kurz}: {txt}", fontsize=9.5, rotation=90,
                va="top", ha="left", color="#6c3483", weight="bold", zorder=12)


def _zeichne_segmente(ax, y0: float, y1: float) -> List[str]:
    """V019-Adapter-Zonen bis Bar 1287; ab 1288 ehrlicher Kahl-Hinweis."""
    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    zeilen: List[str] = []
    for s in ad.ADAPTER_V019_KAUSAL.segmente:
        ax.axvspan(s.start_bar, s.end_bar, color="#f1c40f", alpha=0.09,
                   zorder=0)
        ax.text((s.start_bar + s.end_bar) / 2, y1,
                f"{s.phasen_id} AKTIV", fontsize=9.5, ha="center", va="top",
                color="#7d6608", weight="bold", zorder=11)
        zeilen.append(f"SEGMENT {s.phasen_id}: {s.start_bar}..{s.end_bar}")
    ax.axvline(V019_SEGMENT_ENDE, color="#7f8c8d", lw=1.5, ls=":", zorder=4)
    ax.text(V019_SEGMENT_ENDE + 6, y0, "Kein V019-Adapter-Segment "
            "(Ende V019-Definition)", fontsize=9, va="bottom",
            color="#566573", zorder=12)
    zeilen.append(f"SEGMENT-GRENZE: kein Segment ab Bar {V019_SEGMENT_ENDE + 1}")
    return zeilen


def _zeichne_trades(ax, setups) -> None:
    """Engine-native V019-Trades (Kreise, Richtung = Farbe, SL-TP2-Range)."""
    for t in setups:
        col = C_OBEN if t.richtung == "SHORT" else C_UNTEN
        ax.plot(t.bar, t.basis, "o", ms=8.5, color=col, zorder=9,
                mec="#1a1a1a", mew=0.7, mfc=col)
        ax.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.0,
                alpha=0.45, ls=":", zorder=6)
        ax.annotate(f"K{t.kid} {t.r:+.2f}R\\nbar {t.bar}", (t.bar, t.basis),
                    textcoords="offset points", xytext=(0, 16), ha="center",
                    fontsize=7.2, color=col, zorder=10,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white",
                              alpha=0.82, ec=col, lw=0.5))


def _zeichne_kanten(ax, edges, n: int, wall_live: int,
                    mit_historie: bool = True) -> None:
    """Kanten zweistufig: zarte graue Lebensspanne + volle Farbe bei L_s(k)."""
    for e in sorted(edges, key=lambda x: (x.seite, x.basis)):
        bf = int(min(b for b, _ in e.wicks))
        bl = int(max(b for b, _ in e.wicks))
        x0, x1 = max(0, bf - 20), min(n - 1, bl + 20)
        if x1 <= x0:
            continue
        xs = np.arange(x0, x1 + 1, dtype=float)
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        ls = "-" if e.seite == "OBEN" else "--"
        y_lebt, y_spanne = _edge_profil(e, xs, wall_live)
        if mit_historie:
            ax.plot(xs, y_spanne, color=C_KANTE_HIST, lw=0.8, ls=":",
                    alpha=0.18, zorder=4)
        ax.plot(xs, y_lebt, color=col, lw=1.2, ls=ls, alpha=0.80, zorder=5)
        _y = y_lebt[~np.isnan(y_lebt)]
        if len(_y):
            ax.annotate(f"K{e.kid}", (xs[~np.isnan(y_lebt)][0], _y[0]),
                        fontsize=6.4, color=col, zorder=8)


def _kanten_dichte(edges, n: int, wall_live: int
                   ) -> Tuple[np.ndarray, np.ndarray]:
    """Anzahl lebender Kanten je Bar und Seite (effizient via searchsorted)."""
    idx = np.arange(n, dtype=float)
    oben = np.zeros(n, dtype=float)
    unten = np.zeros(n, dtype=float)
    for e in edges:
        bs = np.sort(np.array([b for b, _ in e.wicks], dtype=float))
        j = np.searchsorted(bs, idx, side="right")
        last = np.where(j >= 1, bs[np.clip(j - 1, 0, len(bs) - 1)], -1e18)
        lebt = (j >= 1) & (last >= idx - wall_live)
        (oben if e.seite == "OBEN" else unten)[lebt] += 1.0
    return oben, unten


def _protokoll(scan, setups, stats, box_nativ: int) -> List[str]:
    """Kurzprotokoll (Terminal + Datei); kein Bezug auf Filterlogik."""
    n = int(scan["n"])
    return [
        f"FENSTER {FENSTER} [{FENSTER_START} .. {FENSTER_ENDE}] n={n}",
        f"BOX-Kalenderkante nativ (19.08.): Bar {box_nativ}",
        f"KANTEN: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds | "
        f"Tombstones {len(scan['tombstones'])} | "
        f"R21 {len(scan['r21_geloescht'])}",
        f"TRADES (engine-nativ, ohne ZP-Patch): {len(setups)} | "
        f"Summe R {sum(t.r for t in setups):+.6f}",
        f"STATS: {stats}",
        "ANKER: " + " | ".join(f"{k} {a}-{b}" for k, a, b, _ in ANKER),
        f"V019-ADAPTER-SEGMENTE bis Bar {V019_SEGMENT_ENDE}; "
        f"ab {V019_SEGMENT_ENDE + 1} bewusst kahl.",
    ]


def main() -> None:
    """Erzeugt Uebersicht + Kantenkarte + Protokoll (read-only, Agg)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    engine = _lade_engine()
    engine.FENSTER[FENSTER] = (FENSTER_START, FENSTER_ENDE)      # type: ignore
    cfg = engine.StraightEdgeHarnessKonfiguration()
    scan = engine._se_scan(FENSTER, cfg)                        # type: ignore
    n = int(scan["n"])
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    if "tick_volume" in d.columns:
        vol = d["tick_volume"].to_numpy(dtype=float)
    else:
        vol = np.zeros(n)
    box_nativ = int(scan["box_end_bar"])
    scan["box_end_bar"] = n          # Voll-Lauf (nativ, ohne ZP-Patchset)
    setups, stats = engine._se_trades(scan, cfg)                # type: ignore

    idx = np.arange(n)
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    y0, y1 = float(lo.min()), float(hi.max())     # global verriegelt
    wall_live = int(cfg.wall_live_bars)
    ticks = np.linspace(0, n - 1, 15).astype(int)
    tl = [str(np.datetime64(ts[i], "D")) for i in ticks]

    # ------------------------------------------------ 01 Uebersicht (Makro)
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(36, 16), sharex=True,
        gridspec_kw={"height_ratios": [5.0, 1.4, 1.0], "hspace": 0.05})
    _zeichne_segmente(ax1, y0, y1)
    _zeichne_anker(ax1, y0, y1)
    _zeichne_kerzen(ax1, idx, op, hi, lo, cl)
    _zeichne_kanten(ax1, scan["edges"], n, wall_live, True)
    _zeichne_trades(ax1, setups)
    ax1.axvline(box_nativ, color="black", lw=1.2, ls=":", alpha=0.7, zorder=4)
    ax1.set_ylim(y0, y1)
    ax1.set_title(
        f"EXT SICHTTEST -- GESAMT (Bars 0..{n - 1}, "
        f"{FENSTER_START}..{FENSTER_ENDE}) | V019-Engine (arretiert) | "
        f"engine-native Trades {len(setups)} / "
        f"{sum(t.r for t in setups):+.4f} R | Kernfenster-Guard aufgehoben",
        fontsize=15)
    ax1.legend(handles=[
        Line2D([0], [0], color=C_OBEN, lw=1.2, label="OBEN-Kante (lebend)"),
        Line2D([0], [0], color=C_UNTEN, ls="--", lw=1.2,
               label="UNTEN-Kante (lebend)"),
        Line2D([0], [0], color=C_KANTE_HIST, ls=":", lw=0.9,
               label="Kante (Lebensspanne, verfallen)"),
        Line2D([0], [0], marker="o", color="w", mfc=C_OBEN, label="SHORT-Trade"),
        Line2D([0], [0], marker="o", color="w", mfc=C_UNTEN, label="LONG-Trade"),
        Line2D([0], [0], color=C_ANKER, alpha=0.5, lw=6, label="Event-Anker A-E"),
    ], loc="upper left", fontsize=11, framealpha=0.92)

    oben, unten = _kanten_dichte(scan["edges"], n, wall_live)
    ax2.plot(idx, oben, color=C_OBEN, lw=1.1, label="lebende OBEN-Kanten")
    ax2.plot(idx, unten, color=C_UNTEN, lw=1.1, label="lebende UNTEN-Kanten")
    for _k, _b0, _b1, _ in ANKER:
        ax2.axvspan(_b0, _b1, color=C_ANKER, alpha=0.12, zorder=1)
    ax2.set_ylabel("Kanten-Dichte", fontsize=11)
    ax2.legend(loc="upper left", fontsize=10, framealpha=0.9)
    ax2.grid(alpha=0.25)

    ax3.bar(idx, vol, width=0.9, color="#8899aa", alpha=0.8)
    for _k, _b0, _b1, _ in ANKER:
        ax3.axvspan(_b0, _b1, color=C_ANKER, alpha=0.12, zorder=1)
    ax3.set_ylabel("Tick-Aktivitaet", fontsize=11)
    ax3.set_xticks(ticks)
    ax3.set_xticklabels(tl, fontsize=10)
    ax3.set_xlim(-5, n + 5)
    ax3.grid(alpha=0.25)

    fig.subplots_adjust(left=0.033, right=0.997, top=0.955, bottom=0.045)
    fig.savefig(OUT_UEBERSICHT, dpi=DPI)
    plt.close(fig)

    # ------------------------------------------- 02 Kantenkarte (ohne Trades)
    fig2, axk = plt.subplots(figsize=(36, 12))
    _zeichne_segmente(axk, y0, y1)
    _zeichne_anker(axk, y0, y1)
    axk.plot(idx, cl, color="#1f3b57", lw=0.7, alpha=0.85, zorder=3)
    _zeichne_kanten(axk, scan["edges"], n, wall_live, True)
    axk.set_ylim(y0, y1)
    axk.set_xticks(ticks)
    axk.set_xticklabels(tl, fontsize=10)
    axk.set_xlim(-5, n + 5)
    axk.set_title(f"EXT SICHTTEST -- KANTENKARTE (Bars 0..{n - 1}) | "
                  f"lebender Kanten-Baum L_s(k) | Anker A-E", fontsize=15)
    fig2.subplots_adjust(left=0.033, right=0.997, top=0.94, bottom=0.06)
    fig2.savefig(OUT_KARTE, dpi=DPI)
    plt.close(fig2)

    zeilen = _protokoll(scan, setups, stats, box_nativ)
    OUT_PROTOKOLL.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    for z in zeilen:
        print(z)
    print(f"\nPNG: {OUT_UEBERSICHT}")
    print(f"PNG: {OUT_KARTE}")
    print(f"TXT: {OUT_PROTOKOLL}")


if __name__ == "__main__":
    main()
