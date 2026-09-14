# -*- coding: utf-8 -*-
"""READ-ONLY Sichtpruefung AUGUST 2026 -- exakt die MAI/JUN/JUL-Logik (V020).

Auftrag (Nutzer)
----------------
"gib mir august 2026 mit der gleichen logik aus, die du fuer mai bis juli
genutzt hast, das sollte die ganz aktuelle engine sein, mit den gerade
erkannten problemen"

Gleiche Logik wie ``test/_render_mai_jun_jul.py``
-------------------------------------------------
* Motor: ``V020KantenEngine(hook=None, wertedomaene=None)`` -> Modus A
  (``_se_trades_v020``). Das ist der aktuell projizierte Stand inkl. der
  erkannten Probleme (S2/S3/S4-Entkernung, korrekte Docht-Alterung).
* Darstellung identisch: Kerzen, getradete Kanten + GEGENKANTEN (Traeger von
  ``tp2``), Touches, farbige Trade-Kreise am ``entry_bar``, gestrichelte
  SL-TP2-Range, ENDE-Ringe (magenta), cumR-Treppenpanel, Statistik mittig,
  Legende oben links, X-Achse = BAR-ZEIT OHNE OFFSET (BKZ).

AUG-Besonderheit (zwei zulaessige Lesarten, BEIDE ausgegeben)
-------------------------------------------------------------
* ``AUG_BOX``  : Fenster 2026-08-10..2026-08-28, ``box_end_bar`` = 644
  (Kalenderkante 2026-08-19, Kanon K6). AUG-native Konfiguration (H1/H2).
* ``AUG_VOLL`` : identisches Fenster, ``box_end_bar`` = n = 1288 (Vollauf,
  genau die MAI/JUN/JUL-Konvention).

WICHTIG (H20.50): Der Trade-Loop mutiert die Kanten in-place. Daher laeuft
JEDER Trade-Durchlauf auf einer eigenen ``copy.deepcopy(scan)``.

ADDITIV -- Motoren/Adapter/Handoff byte-identisch (SHA-Guard).

Aufruf:
    .venv\\Scripts\\python.exe test/_render_aug_sichttest.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
EXT_REND_PFAD = ROOT / "test" / "tmp_png_ext_sichttest_v2.py"
GK_PFAD = ROOT / "test" / "_chk_mai_juli_gegenkante.py"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

START, ENDE, ENDTAG = "2026-08-10", "2026-08-28", "2026-08-27"
BOX_DATUM = "2026-08-19"

# Selbstkontrolle (fail-loud): erwartete (n, SumR) je Lesart.
SOLL: Dict[str, Tuple[int, float]] = {
    "AUG_BOX": (14, 27.327383),      # box_end_bar = 644
    "AUG_VOLL": (29, 23.389914),     # box_end_bar = n = 1288
}

C_LONG, C_SHORT = "#2ca02c", "#d62728"
C_KANTE = "#7f7f7f"
C_GEG = "#a0522d"
C_ENDE = "#d500f9"
C_TOUCH_OBEN, C_TOUCH_UNTEN = "#8b0000", "#004d00"
C_CUMR = "#1f4e79"
C_BOX = "#111111"

OUT_PROTOKOLL = ROOT / "test" / "render_aug_sichttest_out.txt"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _assert_shas() -> None:
    for p, soll in ((BASELINE_PFAD, BASELINE_SHA_SOLL),
                    (V020_PFAD, V020_SHA_SOLL),
                    (ADAPTER_PFAD, ADAPTER_SHA_SOLL)):
        ist = _sha(p)
        assert ist == soll, (
            f"Fremdstand {p.name}: {ist[:16]}... != {soll[:16]}...")


class _StdoutStub:
    """fd-freier stdout-Ersatz (Module haengen beim Import stdout um)."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _lade(name: str, p: Path) -> Any:
    real = sys.stdout
    try:
        sys.stdout = _StdoutStub()  # type: ignore[assignment]
        spec = importlib.util.spec_from_loader(name, loader=None)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        mod.__file__ = str(p)
        sys.modules[name] = mod
        exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"),
             mod.__dict__)
    finally:
        sys.stdout = real
    return mod


def _aug_scan(B: Any, V: Any, cfg: Any, kcfg: Any, box: int
              ) -> Tuple[Dict[str, Any], List[Any], int, Any]:
    """Scan + Modus-A-Trades des AUG-Fensters mit erzwungenem ``box_end_bar``."""
    B.FENSTER["LAB"] = (START, ENDE)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(box)
    # frischer Motor + frische Kopie je Lauf (Trade-Loop mutiert in-place)
    eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    tr, _st = eng._se_trades_v020(copy.deepcopy(scan), cfg)
    tr = sorted(list(tr), key=lambda x: int(x.entry_bar))
    return scan, tr, n, d


def _marker_trades(ax: Any, trades: Sequence[Any]) -> None:
    """Kreise (mfc=col) am entry_bar, SL-TP2-Range, Label, ENDE-Ring."""
    for i, t in enumerate(trades):
        x = int(t.entry_bar)
        short = str(t.richtung) == "SHORT"
        col = C_SHORT if short else C_LONG
        ax.plot([x, x], [float(t.sl), float(t.tp2)], color=col, lw=1.1,
                alpha=0.45, ls=":", zorder=6)
        ax.plot(x, float(t.entry), "o", ms=9.5, color=col, mec="#1a1a1a",
                mew=0.9, mfc=col, zorder=12)
        if str(t.grund1) == "ENDE" or str(t.grund2) == "ENDE":
            ax.plot(x, float(t.entry), "o", ms=16.0, mfc="none", mec=C_ENDE,
                    mew=1.7, zorder=13)
        stag = 26 * (i % 2)
        dy = (-18 - stag) if short else (18 + stag)
        ax.annotate(f"K{t.kid} {float(t.entry):.4f}\n{float(t.r):+.2f}R "
                    f"sig {int(t.bar)}", (x, float(t.entry)),
                    textcoords="offset points", xytext=(0, dy), ha="center",
                    va="top" if short else "bottom", fontsize=7.0,
                    color=col, zorder=11,
                    bbox=dict(boxstyle="round,pad=0.16", fc="white",
                              alpha=0.88, ec=col, lw=0.6))


def _statblock(lab: str, n: int, box: int, split: int, trades: List[Any],
               tp2_werte: List[float], bad: bytes) -> List[str]:
    """Statistik inkl. H1/H2-Split an der Kalenderbox ``split`` (=644)."""
    rs = [float(t.r) for t in trades]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    summe = float(sum(rs))
    pf = (sum(pos) / abs(sum(neg))) if neg else float("inf")
    risiko = [abs(float(t.sl) - float(t.entry)) for t in trades]
    bester = max(trades, key=lambda t: float(t.r))
    h1 = [t for t in trades if int(t.entry_bar) < split]
    h2 = [t for t in trades if int(t.entry_bar) >= split]
    r_h1 = float(sum(float(t.r) for t in h1))
    r_h2 = float(sum(float(t.r) for t in h2))
    n_sl1 = sum(1 for t in trades if str(t.grund1) == "SL")
    n_sl2 = sum(1 for t in trades if str(t.grund2) == "SL")
    n_tp1 = sum(1 for t in trades if str(t.grund1) == "TP1")
    n_tp2 = sum(1 for t in trades if str(t.grund2) == "TP2")
    n_ende1 = sum(1 for t in trades if str(t.grund1) == "ENDE")
    n_ende2 = sum(1 for t in trades if str(t.grund2) == "ENDE")
    return [
        f"AUG  {START} .. {ENDTAG} (BKZ, ohne Offset)   |   "
        f"Bars 0..{n - 1}   |   box_end_bar = {box} "
        f"({'Box 2026-08-19' if box < n else 'Vollauf'})   |   "
        f"Modus A (hook=None, V020-Engine, akt. Stand)",
        f"Trades {len(trades)}   |   SumR {summe:+.6f} R   |   "
        f"Win-Rate {100.0 * len(pos) / len(rs):.2f} % ({len(pos)}/{len(neg)})"
        f"   |   Profit-Faktor {pf:.4f}",
        f"H1 (< {split}): {len(h1)} / {r_h1:+.6f} R   |   "
        f"H2 (>= {split}): {len(h2)} / {r_h2:+.6f} R",
        f"Risiko |sl-entry| USD:  min {min(risiko):.4f}   median "
        f"{float(np.median(risiko)):.4f}   max {max(risiko):.4f}   |   "
        f"TP2 distinct: {len(tp2_werte)} "
        f"({', '.join(f'{v:.4f}' for v in tp2_werte)})",
        f"Exits  1. Haelfte: TP1 {n_tp1} / SL {n_sl1} / ENDE {n_ende1}   |   "
        f"2. Haelfte: TP2 {n_tp2} / SL {n_sl2} / ENDE {n_ende2}   |   "
        f"magenta Ringe = ENDE-Glattstellung am Fensterrand "
        f"({sum(1 for t in trades if 'ENDE' in (str(t.grund1), str(t.grund2)))}"
        f" Trades betroffen)",
        f"KONZENTRATION: bester Trade K{int(bester.kid)} "
        f"({float(bester.r):+.6f} R, Risiko "
        f"{abs(float(bester.sl) - float(bester.entry)):.4f} USD) = "
        f"{100.0 * float(bester.r) / summe:.1f} % des SumR   ->   "
        f"SumR OHNE diesen Trade {summe - float(bester.r):+.6f} R",
        f"DATEI-SHA256: {hashlib.sha256(bad).hexdigest()[:16]}...   "
        f"(Basis/V020/Adapter byte-identisch arretiert)",
    ]


def _zeichne(lab: str, start: str, endtag: str, n: int, box: int, split: int,
             scan: Dict[str, Any], trades: List[Any], d: Any, cfg: Any,
             ext: Any, G: Any, plt: Any, Line2D: Any, bad: bytes) -> List[str]:
    """Ein vollstaendiges AUG-PNG (identische Logik wie MAI/JUN/JUL)."""
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    idx = np.arange(n)
    op = d["open"].to_numpy(dtype=float)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    wall = int(cfg.wall_live_bars)

    alle = list(scan["edges"]) + list(scan["seeds"])
    kids_trade = {int(t.kid) for t in trades}
    kids_geg: set = set()
    for t in trades:
        geg, _pool = G._gegenkante_extern(alle, int(t.bar), str(t.richtung))
        if geg is not None:
            kids_geg.add(int(geg.kid))
    kanten = [e for e in alle if int(e.kid) in kids_trade]
    kanten_geg = [e for e in alle
                  if int(e.kid) in kids_geg and int(e.kid) not in kids_trade]

    tp2_werte = sorted({round(float(t.tp2), 4) for t in trades})
    y0, y1 = float(lo.min()), float(hi.max())
    cum = np.cumsum([float(t.r) for t in trades])
    xb = np.array([int(t.entry_bar) for t in trades], dtype=float)
    ist_r = round(float(sum(float(t.r) for t in trades)), 6)

    fig = plt.figure(figsize=(34, 20))
    gs = fig.add_gridspec(3, 1, height_ratios=[4.3, 1.25, 0.85], hspace=0.09)
    ax = fig.add_subplot(gs[0])
    axc = fig.add_subplot(gs[1])
    axs = fig.add_subplot(gs[2])

    ext._zeichne_kerzen(ax, 0, n - 1, idx, op, hi, lo, cl, breite=0.62)
    if box < n:
        ax.axvline(box, color=C_BOX, lw=1.3, ls=":", alpha=0.75, zorder=2)
        ax.annotate(f"Box-Ende 2026-08-19 (Bar {box})", (box, y1),
                    textcoords="offset points", xytext=(6, -14),
                    fontsize=10.0, color=C_BOX, weight="bold", zorder=15,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              alpha=0.9, ec=C_BOX, lw=0.7))
    if kanten_geg:
        ext._zeichne_kanten(ax, kanten_geg, n, wall, mit_historie=False,
                            lw=1.8)
    ext._zeichne_kanten(ax, kanten, n, wall, mit_historie=False, lw=1.2)
    ext._zeichne_touches(ax, kanten + kanten_geg, ms=5.0)
    _marker_trades(ax, trades)
    ax.set_xlim(-8, n + 8)
    _pad = (y1 - y0) * 0.07
    ax.set_ylim(y0 - _pad, y1 + _pad)
    ax.grid(alpha=0.20)
    ticks = np.linspace(0, n - 1, 16).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in ticks],
                       fontsize=9)
    ax.set_title(
        f"SICHTPRUEFUNG AUG -- {start}..{endtag} | {lab} | Kerzen + "
        f"handlungsrelevante Kanten + Gegenkanten (tp2) + Trades "
        f"(Bars 0..{n - 1}) | {len(trades)} Trades / {ist_r:+.4f} R",
        fontsize=15)
    ax.legend(handles=[
        Line2D([0], [0], marker="o", color="w", mfc=C_LONG, ms=10,
               label="LONG (entry, mfc=col)"),
        Line2D([0], [0], marker="o", color="w", mfc=C_SHORT, ms=10,
               label="SHORT (entry, mfc=col)"),
        Line2D([0], [0], marker="o", color="w", mfc="none", mec=C_ENDE,
               ms=12, mew=1.7, label="ENDE-Exit (Fensterrand)"),
        Line2D([0], [0], color=C_KANTE, lw=1.2, label="Kante (getradet)"),
        Line2D([0], [0], color=C_GEG, lw=1.8,
               label="GEGENKANTE (Traeger von tp2)"),
        Line2D([0], [0], marker="^", color="w", mfc=C_TOUCH_OBEN, ms=8,
               label="Touch OBEN"),
        Line2D([0], [0], marker="v", color="w", mfc=C_TOUCH_UNTEN, ms=8,
               label="Touch UNTEN"),
        Line2D([0], [0], color=C_LONG, ls=":", lw=1.4, label="SL-TP2-Range"),
    ], loc="upper left", fontsize=10.5, framealpha=0.92)

    axc.step(xb, cum, where="post", color=C_CUMR, lw=2.0, zorder=5)
    axc.axhline(0.0, color="black", lw=0.8, alpha=0.6)
    axc.plot(xb, cum, "o", ms=5.0, color=C_CUMR, mec="white", mew=0.7, zorder=6)
    j = int(np.argmax([float(t.r) for t in trades]))
    axc.axvline(xb[j], color=C_ENDE, lw=1.4, ls="--", alpha=0.85)
    axc.annotate(f"groesster Einzeltrade K{int(trades[j].kid)} "
                 f"{float(trades[j].r):+.4f} R", (xb[j], cum[j]),
                 textcoords="offset points", xytext=(10, -24), fontsize=10.5,
                 color=C_ENDE, weight="bold", zorder=8,
                 bbox=dict(boxstyle="round,pad=0.25", fc="#fdf0ff",
                           alpha=0.95, ec=C_ENDE, lw=0.8))
    axc.set_xlim(-8, n + 8)
    axc.set_ylabel("cumR", fontsize=11)
    axc.grid(alpha=0.25)
    axc.set_title(f"cumR-Verlauf AUG ({lab}) -- Endstand {ist_r:+.6f} R",
                  fontsize=12)
    axc.set_xticks(ticks)
    axc.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in ticks],
                        fontsize=9)

    zeilen = _statblock(lab, n, box, split, trades, tp2_werte, bad)
    axs.axis("off")
    axs.text(0.5, 0.98, "\n".join(zeilen), fontsize=10.5, va="top", ha="center",
             family="monospace", transform=axs.transAxes,
             bbox=dict(boxstyle="round,pad=0.5", fc="#f7f7f7", ec="#888888",
                       lw=0.8))

    out = ROOT / "test" / f"render_{lab.lower()}_sichttest.png"
    fig.subplots_adjust(left=0.032, right=0.997, top=0.945, bottom=0.030)
    fig.savefig(out, dpi=200)
    plt.close(fig)

    z = [f"===== {lab} | n={n} | box_end_bar={box} | "
         f"edges={len(scan['edges'])} seeds={len(scan['seeds'])} ====="]
    z.extend("  " + s for s in zeilen)
    z.append(f"  getradete Kids  : "
             f"{', '.join('K' + str(k) for k in sorted(kids_trade))}")
    z.append(f"  Gegenkanten-Kids: "
             f"{', '.join('K' + str(k) for k in sorted(kids_geg))}")
    z.append(f"  PNG: {out}")
    return z


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _assert_shas()
    R = _lade("run_lab_aug", ROOT / "test" / "run_lab.py")
    ext = _lade("ext_aug", EXT_REND_PFAD)
    G = _lade("gk_aug", GK_PFAD)
    B = R._load("basis_aug", BASELINE_PFAD)
    V = R._load("v020_aug", V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    B.FENSTER["LAB"] = (START, ENDE)
    try:
        d0 = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d0))
    ts0 = d0["ts"].to_numpy().astype("datetime64[ns]")
    box = int(np.searchsorted(ts0, np.datetime64(BOX_DATUM)))
    print(f"AUG: n={n} | box_end_bar({BOX_DATUM})={box}")

    z: List[str] = []
    z.append("SICHTPRUEFUNG AUGUST 2026 -- MAI/JUN/JUL-Logik (V020, Modus A)")
    z.append("Zeitbasis: BKZ = time AT TIME ZONE 'UTC' (Kanon K1/K4); "
             "X-Achse = Bar-Zeit ohne Offset.")
    z.append(f"Fenster {START}..{ENDE} (exkl.) | n={n} | "
             f"box_end_bar({BOX_DATUM})={box}")
    z.append(f"Modus A (hook=None) | touch_band_pct {kcfg.touch_band_pct:.2f} "
             f"| sl_buffer_usd {cfg.sl_buffer_usd:.2f} | "
             f"tp1_anteil_pct {cfg.tp1_anteil_pct:.0f}")
    z.append("")

    for lab, box_wert in (("AUG_BOX", box), ("AUG_VOLL", n)):
        scan, trades, nn, d = _aug_scan(B, V, cfg, kcfg, box_wert)
        soll_n, soll_r = SOLL[lab]
        ist_r = round(float(sum(float(t.r) for t in trades)), 6)
        assert (len(trades), ist_r) == (soll_n, round(soll_r, 6)), (
            f"{lab}: Soll ({soll_n}, {soll_r}) != Ist ({len(trades)}, {ist_r})")
        zeilen = _zeichne(lab, START, ENDTAG, nn, box_wert, box, scan, trades,
                          d, cfg, ext, G, plt, Line2D,
                          BASELINE_PFAD.read_bytes())
        z.extend(zeilen)
        z.append("")
        for s in zeilen:
            print(s)
        print("")

    OUT_PROTOKOLL.write_text("\n".join(z) + "\n", encoding="utf-8",
                             newline="\n")
    print(f"TXT: {OUT_PROTOKOLL}")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        OUT_PROTOKOLL.write_text(
            f"ABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}", encoding="utf-8")
    print(f"\nFehler={_fehler}")
