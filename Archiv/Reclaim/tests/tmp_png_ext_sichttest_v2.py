# -*- coding: utf-8 -*-
"""READ-ONLY Sichtpruefung EXT v2 -- Kerzen + Kanten-TOUCHES + Anker-Zooms.

Gegenueber v1 (tmp_png_ext_sichttest.py) NEU:
    * Jeder bestaetigte KANTEN-TOUCH (``e.wicks``-Pivot) wird als Marker auf
      der Kante gezeichnet -- sichtbar, welche Dochte die Linie tragen.
    * Zoom-Panel JE ANKER (A..E) mit echten Kerzen, damit die Touch-Struktur
      an den Events lesbar wird.
    * Referenzzonen H1/H2 des ENGINE-nativen Fensters (box_end = 1104) sind
      schraffiert; zusaetzlich wird der ALTE V019-AUG-URSPRUNG (10.08.) als
      vertikale Linie markiert, um den Versatz zur alten PNG zu zeigen.

ADDITIV -- Engine/Renderer/Adapter bleiben byte-identisch (SHA-Guard).

Aufruf:
    .venv\\Scripts\\python.exe test\\tmp_png_ext_sichttest_v2.py
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
ALT_AUG_START: Final[str] = "2026-08-10"      # Alt-V019-AUG-Ursprung
V019_SEGMENT_ENDE: Final[int] = 1287

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
C_TOUCH_OBEN: Final[str] = "#8b0000"
C_TOUCH_UNTEN: Final[str] = "#004d00"

OUT_UEBERSICHT: Final[Path] = ROOT / "test" / "ext_sichttest_v2_uebersicht.png"
OUT_KARTE: Final[Path] = ROOT / "test" / "ext_sichttest_v2_kantenkarte.png"
OUT_ANKER_DIR: Final[Path] = ROOT / "test"
OUT_PROTOKOLL: Final[Path] = ROOT / "test" / "ext_sichttest_v2_out.txt"


def _lade_engine():
    """Laedt die arretierte Engine ohne Seiteneffekte (SHA wird geprueft)."""
    sha = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if sha != ENGINE_SHA_SOLL:
        raise SystemExit(f"Fremd-Engine: {sha[:16]}... (Soll "
                         f"{ENGINE_SHA_SOLL[:16]}...).")
    spec = importlib.util.spec_from_loader("ke_ext2", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(ENGINE_PATH)
    sys.modules["ke_ext2"] = mod
    exec(compile(ENGINE_PATH.read_text(encoding="utf-8"),
                 str(ENGINE_PATH), "exec"), mod.__dict__)
    return mod


def _edge_profil(e, xs: np.ndarray, wall_live: int
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """Kausale Kantenlinie, zweistufig (L_s(k) + Lebensspanne)."""
    bs = np.array([b for b, _ in e.wicks], dtype=float)
    px = np.array([p for _, p in e.wicks], dtype=float)
    order = np.argsort(bs, kind="stable")
    bs, px = bs[order], px[order]

    if e.ist_prim_anker:
        basis = np.full(len(xs), float(e.basis), dtype=float)
        j_conf = np.full(len(xs), 1, dtype=int)
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


def _zeichne_kerzen(ax, x0: int, x1: int, idx, op, hi, lo, cl,
                    breite: float = 0.60) -> None:
    """Kerzen (Docht + Korpus) im Bar-Fenster [x0, x1]."""
    from matplotlib.patches import Rectangle
    x = idx[x0:x1 + 1]
    o, h, l, c = op[x0:x1 + 1], hi[x0:x1 + 1], lo[x0:x1 + 1], cl[x0:x1 + 1]
    up = c >= o
    ax.vlines(x, l, h, color=np.where(up, C_UP, C_DN), lw=0.5, zorder=2)
    bl = np.minimum(o, c)
    bh = np.where(np.abs(c - o) < 1e-9, 0.004, np.abs(c - o))
    for xi, b0, hh, u in zip(x, bl, bh, up):
        ax.add_patch(Rectangle((xi - breite / 2, b0), breite, hh,
                               facecolor=C_UP if u else C_DN,
                               edgecolor=C_UP if u else C_DN, lw=0.3,
                               zorder=3))


def _zeichne_touches(ax, kanten, ms: float = 5.0,
                     nur_nummern: bool = False) -> int:
    """Bestätigte Kanten-TOUCHES (``e.wicks``) als Marker.

    OBEN-Kante -> Dreieck ''^'' (Docht von oben), UNTEN-Kante -> ''v''.
    Seeds (1 Touch) kleiner/grau, Edges kraeftig in Sektionsfarbe.
    """
    n_t = 0
    for e in kanten:
        seed = len(e.wicks) < 2
        col = (C_KANTE_HIST if seed
               else (C_TOUCH_OBEN if e.seite == "OBEN" else C_TOUCH_UNTEN))
        mk = ("^" if e.seite == "OBEN" else "v")
        for b, p in e.wicks:
            ax.plot(b, p, mk, ms=(ms * 0.75 if seed else ms), color=col,
                    mec="black", mew=0.4, mfc=col if not seed else "none",
                    zorder=9, alpha=0.9)
            n_t += 1
    return n_t


def _zeichne_anker(ax, y0: float, y1: float, x0: int, x1: int,
                   band: bool = True) -> None:
    """Anker A-E: Band + Startlinie + Label (nur sichtbare in [x0, x1])."""
    for kurz, b0, b1, txt in ANKER:
        if b1 < x0 or b0 > x1:
            continue
        if band:
            ax.axvspan(b0, b1, color=C_ANKER, alpha=0.12, zorder=1)
        ax.axvline(b0, color=C_ANKER, lw=1.3, ls="-", alpha=0.85, zorder=4)
        ax.text(b0 + max(1, (x1 - x0) // 300), y1, f"{kurz}: {txt}",
                fontsize=10, rotation=90, va="top", ha="left",
                color="#6c3483", weight="bold", zorder=12)


def _zeichne_zonen(ax, n: int, box_nativ: int, alt_aug: int,
                   y0: float, y1: float) -> None:
    """H1/H2-Referenzzonen + Alt-V019-AUG-Ursprung sichtbar machen."""
    ax.axvspan(0, box_nativ, facecolor="gray", alpha=0.06, hatch="//",
               edgecolor="gray", lw=0.0, zorder=0)
    ax.axvline(box_nativ, color="black", lw=1.3, ls=":", alpha=0.85, zorder=4)
    ax.text(box_nativ / 2, y0, f"H1 BOX (bars < {box_nativ})", fontsize=10,
            color="#444444", ha="center", va="bottom", zorder=12)
    ax.text(box_nativ + (n - box_nativ) / 2, y0,
            f"H2 EXPANSION (bars >= {box_nativ})", fontsize=10,
            color="#1f77b4", ha="center", va="bottom", zorder=12)
    ax.axvline(alt_aug, color="#ff7f0e", lw=1.8, ls="-.", alpha=0.9, zorder=5)
    ax.text(alt_aug + 4, y1, f"ALT-V019 AUG-URSPRUNG (10.08. = Bar {alt_aug})",
            fontsize=10, rotation=90, va="top", ha="left", color="#b35c00",
            weight="bold", zorder=13)


def _zeichne_kanten(ax, edges, n: int, wall_live: int,
                    mit_historie: bool = True, lw: float = 1.2) -> None:
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
        ax.plot(xs, y_lebt, color=col, lw=lw, ls=ls, alpha=0.80, zorder=5)
        _m = ~np.isnan(y_lebt)
        if _m.any():
            ax.annotate(f"K{e.kid}", (xs[_m][0], y_lebt[_m][0]), fontsize=6.6,
                        color=col, zorder=8)


def _zeichne_trades(ax, setups, x0: int, x1: int, fs: float = 7.0) -> None:
    """Engine-native V019-Trades (Kreise, Richtung = Farbe, SL-TP2-Range)."""
    for t in setups:
        if t.bar < x0 or t.bar > x1:
            continue
        col = C_OBEN if t.richtung == "SHORT" else C_UNTEN
        ax.plot(t.bar, t.basis, "o", ms=9.0, color=col, zorder=11,
                mec="#1a1a1a", mew=0.8, mfc=col)
        ax.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.1,
                alpha=0.5, ls=":", zorder=6)
        ax.annotate(f"K{t.kid} {t.r:+.2f}R\\nbar {t.bar}", (t.bar, t.basis),
                    textcoords="offset points", xytext=(0, 18), ha="center",
                    fontsize=fs, color=col, zorder=10,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white",
                              alpha=0.85, ec=col, lw=0.5))


def _protokoll(scan, setups, box_nativ: int, alt_aug: int,
               n_touches: int) -> List[str]:
    """Kurzprotokoll (Terminal + Datei)."""
    n = int(scan["n"])
    return [
        f"FENSTER {FENSTER} [{FENSTER_START} .. {FENSTER_ENDE}] n={n}",
        f"BOX-Kalenderkante nativ (19.08.): Bar {box_nativ} | "
        f"ALT-V019-AUG-URSPRUNG (10.08.): Bar {alt_aug} | "
        f"Versatz = {alt_aug} Bars",
        f"KANTEN: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds | "
        f"TOUCHES (gezeichnet) {n_touches} | Tombstones "
        f"{len(scan['tombstones'])} | R21 {len(scan['r21_geloescht'])}",
        f"TRADES (engine-nativ, ohne ZP-Patch): {len(setups)} | "
        f"Summe R {sum(t.r for t in setups):+.6f}",
        "ANKER: " + " | ".join(f"{k} {a}-{b}" for k, a, b, _ in ANKER),
        f"V019-ADAPTER-SEGMENTE bis Bar {V019_SEGMENT_ENDE}; "
        f"ab {V019_SEGMENT_ENDE + 1} bewusst kahl.",
        "HINWEIS: Fenster-Ursprung EXT = 03.08.; Alt-V019-PNG = 10.08. -> "
        "derselbe Kanten-Katalog erscheint um den Versatz verschoben.",
    ]


def main() -> None:
    """Erzeugt Uebersicht, Kantenkarte, Anker-Zooms, Protokoll (Agg)."""
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
    idx = np.arange(n)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    box_nativ = int(scan["box_end_bar"])
    alt_aug = int(np.searchsorted(ts, np.datetime64(ALT_AUG_START)))
    scan["box_end_bar"] = n
    setups, stats = engine._se_trades(scan, cfg)                # type: ignore

    kanten = list(scan["edges"]) + list(scan["seeds"])
    y0, y1 = float(lo.min()), float(hi.max())
    wall_live = int(cfg.wall_live_bars)
    n_touch = sum(len(e.wicks) for e in kanten)
    zeilen = _protokoll(scan, setups, box_nativ, alt_aug, n_touch)

    # ============================================================ 01 Uebersicht
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(36, 16), sharex=True,
        gridspec_kw={"height_ratios": [5.4, 1.0], "hspace": 0.05})
    _zeichne_zonen(ax1, n, box_nativ, alt_aug, y0, y1)
    _zeichne_anker(ax1, y0, y1, 0, n - 1, band=True)
    _zeichne_kerzen(ax1, 0, n - 1, idx, op, hi, lo, cl, breite=0.60)
    _zeichne_kanten(ax1, scan["edges"], n, wall_live, True)
    _zeichne_touches(ax1, kanten, ms=4.5)
    _zeichne_trades(ax1, setups, 0, n - 1)
    ax1.set_ylim(y0, y1)
    ax1.set_title(
        f"EXT SICHTTEST v2 -- GESAMT (Bars 0..{n - 1}, {FENSTER_START}.."
        f"{FENSTER_ENDE}) | Kerzen + Kanten-TOUCHES | V019-Engine (arretiert) "
        f"| engine-native Trades {len(setups)} / "
        f"{sum(t.r for t in setups):+.4f} R", fontsize=15)
    ax1.legend(handles=[
        Line2D([0], [0], color=C_OBEN, lw=1.2, label="OBEN-Kante (lebend)"),
        Line2D([0], [0], color=C_UNTEN, ls="--", lw=1.2,
               label="UNTEN-Kante (lebend)"),
        Line2D([0], [0], marker="^", color="w", mfc=C_TOUCH_OBEN, ms=8,
               label="Touch OBEN (bestaetigter Docht)"),
        Line2D([0], [0], marker="v", color="w", mfc=C_TOUCH_UNTEN, ms=8,
               label="Touch UNTEN"),
        Line2D([0], [0], marker="o", color="w", mfc=C_OBEN, label="SHORT-Trade"),
        Line2D([0], [0], marker="o", color="w", mfc=C_UNTEN, label="LONG-Trade"),
        Line2D([0], [0], color=C_ANKER, alpha=0.5, lw=6, label="Event-Anker A-E"),
        Line2D([0], [0], color="#ff7f0e", ls="-.", lw=1.8,
               label="Alt-V019 AUG-Ursprung"),
    ], loc="upper left", fontsize=10.5, framealpha=0.92)

    ax2.axis("off")
    ax2.text(0.5, 0.98, "\n".join(zeilen), fontsize=10, va="top", ha="center",
             family="monospace", transform=ax2.transAxes)
    ticks = np.linspace(0, n - 1, 15).astype(int)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in ticks],
                        fontsize=9)
    ax2.set_xlim(-5, n + 5)
    fig.subplots_adjust(left=0.033, right=0.997, top=0.950, bottom=0.045)
    fig.savefig(OUT_UEBERSICHT, dpi=300)
    plt.close(fig)

    # ========================================================= 02 Kantenkarte
    fig2, axk = plt.subplots(figsize=(36, 12))
    _zeichne_zonen(axk, n, box_nativ, alt_aug, y0, y1)
    _zeichne_anker(axk, y0, y1, 0, n - 1, band=True)
    _zeichne_kanten(axk, scan["edges"], n, wall_live, True)
    _zeichne_touches(axk, kanten, ms=5.5)
    axk.set_ylim(y0, y1)
    axk.set_xticks(ticks)
    axk.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in ticks],
                        fontsize=10)
    axk.set_xlim(-5, n + 5)
    axk.set_title(f"EXT SICHTTEST v2 -- KANTENKARTE (Bars 0..{n - 1}) | "
                  f"lebender Kanten-Baum L_s(k) + TOUCHES | Anker A-E",
                  fontsize=15)
    fig2.subplots_adjust(left=0.033, right=0.997, top=0.94, bottom=0.06)
    fig2.savefig(OUT_KARTE, dpi=300)
    plt.close(fig2)

    # ==================================================== 03+ ANKER-ZOOMS
    for kurz, b0, b1, txt in ANKER:
        x0 = max(0, b0 - 45)
        x1 = min(n - 1, b1 + 45)
        zy0 = float(lo[x0:x1 + 1].min())
        zy1 = float(hi[x0:x1 + 1].max())
        pad = (zy1 - zy0) * 0.10
        zy0, zy1 = zy0 - pad, zy1 + pad
        figz, axz = plt.subplots(figsize=(24, 11))
        _zeichne_anker(axz, zy0, zy1, x0, x1, band=True)
        axz.axvline(box_nativ, color="black", lw=1.2, ls=":", alpha=0.7,
                    zorder=4)
        _zeichne_kerzen(axz, x0, x1, idx, op, hi, lo, cl, breite=0.62)
        _zeichne_kanten(axz, scan["edges"], n, wall_live, True, lw=1.5)
        _zeichne_touches(axz, kanten, ms=9.0)
        _zeichne_trades(axz, setups, x0, x1, fs=9.0)
        _tz = np.linspace(x0, x1, 12).astype(int)
        axz.set_xticks(_tz)
        axz.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in _tz],
                            fontsize=10)
        axz.set_xlim(x0 - 1, x1 + 1)
        axz.set_ylim(zy0, zy1)
        axz.grid(alpha=0.25)
        axz.set_title(f"EXT v2 -- ANKER {kurz} ({txt}) | Bars {x0}..{x1} | "
                      f"Kerzen + Kanten + Touches", fontsize=14)
        pz = OUT_ANKER_DIR / f"ext_sichttest_v2_anker_{kurz}.png"
        figz.subplots_adjust(left=0.05, right=0.995, top=0.93, bottom=0.07)
        figz.savefig(pz, dpi=200)
        plt.close(figz)
        print(f"PNG: {pz}")

    OUT_PROTOKOLL.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    for z in zeilen:
        print(z)
    print(f"\nPNG: {OUT_UEBERSICHT}")
    print(f"PNG: {OUT_KARTE}")
    print(f"TXT: {OUT_PROTOKOLL}")


if __name__ == "__main__":
    main()
