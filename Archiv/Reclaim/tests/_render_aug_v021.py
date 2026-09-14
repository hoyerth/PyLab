# -*- coding: utf-8 -*-
"""ADDITIVER Sichtpruefungs-Renderer AUG 2026 -- V021, Segmentwand "AN".

Schlank und eigenstaendig: importiert ``tmp_kanten_engine_v021_replay``
direkt. KEIN Eingriff in ``tmp_png_aug_sichttest.py`` (123 KB, Modul-Level
``argparse`` + Sollwert-Asserts auf den alten Stand) und KEIN Patchen.

Pruefgegenstand (Beschluss L1--L3):
    * Einzelbild, VOLLE BREITE, nur der AN-Lauf (kein Panel-Split).
    * Alle acht Anwender-Liquiditaetslinien als gestrichelte Horizontale
      (Referenzwahrheit, KEINE Engine-Kante).
    * Segmentwand-Ereignisse dezent: Segmentgrenzen als vertikale Linien,
      die ZP-5-Docht-Erweiterung als Marker am Bar.

Darstellungs-Garantie (Abschnitt 54/55): Kerzen ueberall; Trade-Kreise IMMER
farbig gefuellt (``mfc=col``); X-Achse = Bar-Zeit (BKZ) OHNE Offset;
Anwender-Linien nur als Referenz; Sperr-Marker violett; Statistik mittig;
Legende oben links; Titel ``Bars 0..1287``; gestrichelte SL-TP2-Range.

Anwender-Vorgabe (14.09.2026): KEINE Equity-/cumR-GRAFIK im PNG. Das Bild
besteht aus genau zwei Panels -- Kurs-Panel und Statistik-Tabelle. Die
cumR-Kennzahlen (Endstand, MaxDD, SL-Treffer) bleiben als ZAHLEN in der
Statistik; gezeichnet wird nur die Kurskurve mit Trades und Kanten.

Fail-Loud: das Skript bricht ab, wenn Legacy oder AN nicht bit-exakt sind.

Aufruf:
    python test/_render_aug_v021.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
import pandas as pd                                 # noqa: E402
from matplotlib.lines import Line2D                 # noqa: E402

V = importlib.import_module("tmp_kanten_engine_v021_replay")
AD = importlib.import_module("backtest_lab.phasen_regime_adapter")

BOX = 644
SOLL_LEGACY = (14, +42.450970)
SOLL_AN = (18, +52.876174)
SOLL_AN_H1 = (8, +38.919584)
SOLL_AN_H2 = (10, +13.956589)

C_UP, C_DN = "#a8d5ba", "#f2a5a5"
C_OBEN, C_UNTEN = "#d62728", "#2ca02c"
C_SHORT, C_LONG = "#d62728", "#2ca02c"
C_GATE, C_CHG, C_SEG = "#8e44ad", "#b8860b", "#7f7f7f"

# Anwender-Vorgaben (Referenzwahrheit, handverifiziert am 13.09.2026).
LINIEN: Tuple[Tuple[str, str, float], ...] = (
    ("upper 66.46", "OBEN", 66.46), ("lower 63.67", "UNTEN", 63.67),
    ("lower-min 64.20", "UNTEN", 64.20), ("Upper1 69.90", "OBEN", 69.90),
    ("Upper2 69.62", "OBEN", 69.62), ("Lower1 68.88", "UNTEN", 68.88),
    ("Lower2 68.40", "UNTEN", 68.40), ("Lower3 67.60", "UNTEN", 67.60),
)


def _grenzen(adapter: Any) -> List[Any]:
    """Adapter-Segmente -> passive ``Segmentgrenze`` (G4, reine Daten)."""
    PhK = AD.PhasenKanteInfo
    return [V.Segmentgrenze(
        start_bar=int(s.start_bar), end_bar=int(s.end_bar),
        boden=PhK(kid=int(s.boden.kid),
                  provenienz_basis=float(s.boden.provenienz_basis)),
        decke=PhK(kid=int(s.decke.kid),
                  provenienz_basis=float(s.decke.provenienz_basis)),
        boden_deklariert_literal=s.boden_deklariert_literal)
        for s in adapter.segmente]


def _kanten_y(e: Any, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """Kausale Treppe einer Kante: Stuetzstellen = bestaetigte Dochte + 2."""
    bars = sorted(b for b, _ in e.wicks)
    xs = [min(n - 1, b + 2) for b in bars]
    if not xs:
        return np.array([0]), np.array([float(e.basis)])
    ys = [float(e.basis_bei(x)) for x in xs]
    return np.array(xs, dtype=float), np.array(ys, dtype=float)


def main() -> None:
    B = V._engine()
    kcfg = B.StraightEdgeHarnessKonfiguration()
    scan = B._se_scan("AUG", kcfg)
    assert int(scan["box_end_bar"]) == BOX, scan["box_end_bar"]
    n = int(scan["n"])
    d = scan["d"]
    ts = pd.to_datetime(d["ts"])
    op = d["open"].to_numpy(dtype=float)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    alle = list(scan["edges"]) + list(scan["seeds"])
    idx = {int(e.kid): e for e in alle}

    grenzen = _grenzen(AD.ADAPTER_V019_KAUSAL)
    tr_leg = V._lauf(scan, V.V021KantenKonfiguration(), box_end=n)
    tr_an = V._lauf(scan, V.V021KantenKonfiguration(segmentwand_modus="AN"),
                    grenzen, box_end=n)
    tr_an = sorted(tr_an, key=lambda t: int(t.entry_bar))
    tr_leg = sorted(tr_leg, key=lambda t: int(t.entry_bar))

    # --- Fail-Loud: das Bild darf nie still falsch sein --------------------
    rl = sum(float(t.r) for t in tr_leg)
    ra = sum(float(t.r) for t in tr_an)
    h1 = [float(t.r) for t in tr_an if int(t.entry_bar) < BOX]
    h2 = [float(t.r) for t in tr_an if int(t.entry_bar) >= BOX]
    assert (len(tr_leg), round(rl, 6)) == SOLL_LEGACY, (len(tr_leg), rl)
    assert (len(tr_an), round(ra, 6)) == SOLL_AN, (len(tr_an), ra)
    assert (len(h1), round(sum(h1), 6)) == SOLL_AN_H1, (len(h1), sum(h1))
    assert (len(h2), round(sum(h2), 6)) == SOLL_AN_H2, (len(h2), sum(h2))
    print(f"SOLL OK: Legacy {len(tr_leg)}/{rl:+.6f} | AN {len(tr_an)}/"
          f"{ra:+.6f} | H1 {len(h1)}/{sum(h1):+.6f} | H2 {len(h2)}/"
          f"{sum(h2):+.6f}")

    # --- ZP-5-Wirkung vermessen (nur fuer die Marker, read-only) ----------
    import copy
    sc = copy.deepcopy(scan)
    wcfg = V._wirksame_cfg(V.V021KantenKonfiguration(segmentwand_modus="AN"))
    vor = {int(e.kid): len(e.wicks) for e in alle}
    V._SEGMENTGRENZEN = tuple(grenzen)
    try:
        ns = V._baue_ns(B, wcfg)
        ns["_SEG_SHIM"] = V._GrenzenShim(grenzen)
        ns["erweitere_segmentwand_dochte"](
            sc, ns["_SEG_SHIM"], wcfg, hi, lo, ns["_ueb"])
        zp5 = [(int(e.kid), b) for e in
               list(sc["edges"]) + list(sc["seeds"])
               for b, _ in e.wicks[vor[int(e.kid)]:]]
    finally:
        V._SEGMENTGRENZEN = ()
    print(f"ZP-5-Docht-Erweiterungen: {zp5}")

    # ===================== ZEICHNEN =====================================
    fig = plt.figure(figsize=(30.0, 15.0), dpi=100)
    # Anwender-Vorgabe: KEINE Equity-/cumR-Grafik im PNG. Das Bild besteht
    # nur aus dem Kurs-Panel (Kerzen/Trades/Kanten) und der Statistik-Tabelle.
    # Die cumR-Kennzahlen (Endstand, MaxDD) bleiben als ZAHLEN in der
    # Statistik erhalten -- es entfaellt ausschliesslich die Kurvendarstellung.
    gs = fig.add_gridspec(2, 1, height_ratios=[7.4, 1.9], hspace=0.10)
    ax = fig.add_subplot(gs[0])
    axs = fig.add_subplot(gs[1])

    # --- 1) Kerzen -------------------------------------------------------
    x = np.arange(n)
    up = cl >= op
    ax.vlines(x[up], op[up], cl[up], color=C_UP, lw=1.0, zorder=2)
    ax.vlines(x[~up], op[~up], cl[~up], color=C_DN, lw=1.0, zorder=2)
    ax.vlines(x[up], cl[up], hi[up], color=C_UP, lw=0.7, zorder=2)
    ax.vlines(x[up], lo[up], op[up], color=C_UP, lw=0.7, zorder=2)
    ax.vlines(x[~up], cl[~up], hi[~up], color=C_DN, lw=0.7, zorder=2)
    ax.vlines(x[~up], lo[~up], op[~up], color=C_DN, lw=0.7, zorder=2)

    # --- 2) Segmentgrenzen (dezent) -------------------------------------
    lo_a = min(lo.min(), min(p for _, _, p in LINIEN)) - 0.3
    hi_a = max(hi.max(), max(p for _, _, p in LINIEN)) + 0.9
    y_lab = lo_a + 0.25
    for i, g in enumerate(grenzen):
        for bnd, nm in ((int(g.start_bar), f"seg{i} ab"),
                        (int(g.end_bar), f"seg{i} bis")):
            ax.axvline(bnd, color=C_SEG, lw=0.9, ls="-.", alpha=0.45, zorder=3)
            ax.annotate(f"{nm} {bnd}", (bnd, y_lab), rotation=90, fontsize=7.5,
                        color=C_SEG, va="bottom", ha="right", alpha=0.9,
                        zorder=4)
    ax.text(0.5 * (grenzen[1].start_bar + grenzen[-1].end_bar), hi_a - 0.35,
            f"SEGMENTWAND-ZONE {grenzen[1].start_bar}..{grenzen[-1].end_bar}",
            fontsize=9, color=C_SEG, ha="center", weight="bold", zorder=4)

    # --- 3) ZP-5-Docht-Erweiterungen ------------------------------------
    for kid, bar in zp5:
        ax.plot(bar, hi[bar] + 0.06, "v", ms=8.0, color=C_CHG, zorder=11)
        ax.annotate(f"ZP-5 K{kid}", (bar, hi[bar] + 0.06),
                    textcoords="offset points", xytext=(0, 9), ha="center",
                    fontsize=7.5, color=C_CHG, weight="bold", zorder=12,
                    bbox=dict(boxstyle="round,pad=0.18", fc="#fdf6e3",
                              ec=C_CHG, lw=0.8))

    # --- 4) Anwender-Linien (Referenzwahrheit) ---------------------------
    for lab, seite, preis in LINIEN:
        col = C_OBEN if seite == "OBEN" else C_UNTEN
        ax.axhline(preis, color=col, lw=1.5, ls=(0, (7, 4)), alpha=0.42,
                   zorder=1)
        ax.annotate(f"Anwender {lab}", (n - 2, preis), ha="right", va="bottom",
                    fontsize=8, color=col, weight="bold", zorder=10,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white",
                              ec=col, lw=0.7, alpha=0.85))

    # --- 5) Engine-Kanten (Treppe, kausal) -------------------------------
    ggt = {int(t.kid) for t in tr_an} | {int(t.kid) for t in tr_leg}
    for e in alle:
        xs, ys = _kanten_y(e, n)
        col = C_OBEN if e.seite == "OBEN" else C_UNTEN
        handelnd = int(e.kid) in ggt
        ax.step(xs, ys, where="post", color=col,
                lw=2.2 if handelnd else 0.9,
                alpha=0.95 if handelnd else 0.28,
                ls="-" if e.status == "AKTIV" else (0, (5, 3)), zorder=5)
        if e.wicks:
            wb = np.array([b for b, _ in e.wicks], dtype=float)
            wp = np.array([p for _, p in e.wicks], dtype=float)
            ax.plot(wb, wp, "|", ms=7.0, color=col, alpha=0.5, zorder=6)
        if handelnd:
            ax.annotate(f"K{int(e.kid)}", (xs[-1], ys[-1]),
                        textcoords="offset points", xytext=(3, 4),
                        fontsize=8.5, color=col, weight="bold", zorder=11)

    # --- 6) Trades (Kreise gefuellt, SL-TP2-Range, Labels) ---------------
    for i, t in enumerate(tr_an):
        col = C_SHORT if str(t.richtung) == "SHORT" else C_LONG
        in_h1 = int(t.entry_bar) < BOX
        ax.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.1,
                alpha=0.45, ls=":", zorder=6)
        ax.plot(t.bar, t.basis, "o", ms=9.0 if in_h1 else 10.5, color=col,
                mec="#1a1a1a", mew=0.7 if in_h1 else 1.6, mfc=col, zorder=9)
        neu = all(abs(float(t.bar) - float(u.bar)) > 1e-9
                  or int(t.kid) != int(u.kid) for u in tr_leg)
        if neu:
            ax.plot(t.bar, t.basis, "o", ms=18.0, color=C_CHG, mfc="none",
                    mew=2.0, zorder=13)
            ax.annotate("NEU (ZP-5)", (t.bar, t.basis),
                        textcoords="offset points", xytext=(0, -40),
                        ha="center", fontsize=8, color=C_CHG, weight="bold",
                        zorder=14,
                        bbox=dict(boxstyle="round,pad=0.18", fc="#fdf6e3",
                                  ec=C_CHG, lw=0.9))
        dy = 20 if i % 2 == 0 else -26
        ax.annotate(f"K{int(t.kid)} {float(t.r):+.1f}R",
                    (t.bar, t.basis), textcoords="offset points",
                    xytext=(0, dy), ha="center", fontsize=7.8, color=col,
                    weight="bold", zorder=12,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white",
                              ec=col, lw=0.6, alpha=0.85))

    # --- 7) Sperr-Marker (violett) ---------------------------------------
    gestoppt = sum(1 for t in tr_an if abs(float(t.r) + 1.0) < 1e-9)
    ax.axvline(BOX, color=C_GATE, lw=1.4, ls="--", alpha=0.55, zorder=4)
    ax.annotate(f"H1|H2 Kalenderkante {BOX}", (BOX, lo_a + 0.6), rotation=90,
                fontsize=8.5, color=C_GATE, va="bottom", ha="right",
                weight="bold", zorder=12)

    # --- 8) Achsen / Titel ------------------------------------------------
    ticks = np.linspace(0, n - 1, 17).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in ticks],
                       fontsize=8)
    ax.set_xlim(-6, n + 6)
    ax.set_ylim(lo_a, hi_a)
    ax.grid(alpha=0.15, ls=":")
    ax.set_ylabel("Preis (USD)", fontsize=9, color="#555555")
    ax.set_xlabel("Bar-Zeit (BKZ, M15) | Bar-Index primaer", fontsize=8.5,
                  color="#555555")
    ax.set_title(
        f"V021 Segmentwand AN -- AUG 2026 | Bars 0..{n - 1} | "
        f"n={len(tr_an)} Trades {ra:+.6f} R | "
        f"H1 {len(h1)}/{sum(h1):+.6f} | H2 {len(h2)}/{sum(h2):+.6f}",
        fontsize=13, weight="bold")
    ax.legend(handles=[
        Line2D([], [], color=C_OBEN, lw=2.4, label="engine-Kante OBEN (Treppe)"),
        Line2D([], [], color=C_UNTEN, lw=2.4, label="engine-Kante UNTEN (Treppe)"),
        Line2D([], [], color=C_OBEN, lw=1.5, ls=(0, (7, 4)),
               label="Anwender-Linie (Referenz)"),
        Line2D([], [], color=C_SHORT, marker="o", lw=0, ms=9, mfc=C_SHORT,
               mec="#1a1a1a", label="SHORT (gefuellt)"),
        Line2D([], [], color=C_LONG, marker="o", lw=0, ms=9, mfc=C_LONG,
               mec="#1a1a1a", label="LONG (gefuellt)"),
        Line2D([], [], color=C_CHG, marker="o", lw=0, ms=13, mfc="none",
               mew=2.0, label="NEU durch Segmentwand"),
        Line2D([], [], color=C_CHG, marker="v", lw=0, ms=8,
               label="ZP-5 Docht-Erweiterung"),
        Line2D([], [], color=C_SEG, lw=1.2, ls="-.", label="Segmentgrenze"),
        Line2D([], [], color=C_GATE, lw=1.4, ls="--",
               label=f"H1|H2 Kalenderkante {BOX}"),
    ], loc="upper left", fontsize=9, ncol=2, framealpha=0.92)

    # --- 9) cumR-Treppe -- ENTFALLEN (Anwender-Vorgabe: keine Equity-Grafik)
    # Die Werte werden weiter berechnet, aber NICHT gezeichnet; sie gehen als
    # Zahlen in die Statistik-Tabelle ein (Endstand, MaxDD, SL-Treffer).
    cr = []
    s = 0.0
    for t in tr_an:
        s += float(t.r)
        cr.append(s)

    # --- 10) Statistik mittig --------------------------------------------
    zeilen: List[str] = []
    zeilen.append(f"{'#':>2} {'Bar':>5} {'BKZ':>17} {'Kante':>6} "
                  f"{'Richt':>5} {'Basis':>8} {'status':>9} {'R':>9}  Phase")
    for i, t in enumerate(tr_an, 1):
        e = idx[int(t.kid)]
        ph = "H1" if int(t.entry_bar) < BOX else "H2"
        neu = all(abs(float(t.bar) - float(u.bar)) > 1e-9
                  or int(t.kid) != int(u.kid) for u in tr_leg)
        zeilen.append(
            f"{i:>2} {int(t.bar):>5} "
            f"{ts.iloc[int(t.bar)].strftime('%d.%m %H:%M'):>17} "
            f"K{int(t.kid):<5} {str(t.richtung):>5} {float(e.basis):>8.4f} "
            f"{str(e.status):>9} {float(t.r):>+9.4f}  {ph}{' NEU' if neu else ''}")
    peak, maxdd = 0.0, 0.0
    for v in cr:
        peak = max(peak, v)
        maxdd = min(maxdd, v - peak)
    zeilen.append("")
    zeilen.append(
        f"SL-Treffer (-1.000 R): {gestoppt:2d} von {len(tr_an)} | "
        f"MaxDD {maxdd:+.4f} R | cumR-Endstand {ra:+.6f} R")
    zeilen.append(
        f"V021 Segmentwand AN  {len(tr_an):2d} Trades {ra:+.6f} R | "
        f"H1 {len(h1)}/{sum(h1):+.6f} | H2 {len(h2)}/{sum(h2):+.6f}"
        f"       ||       LEGACY {len(tr_leg):2d} Trades {rl:+.6f} R"
        f"       ||       Delta {len(tr_an) - len(tr_leg):+d} Trades "
        f"{ra - rl:+.6f} R")
    axs.axis("off")
    axs.text(0.5, 0.98, "\n".join(zeilen), fontsize=8.2, va="top", ha="center",
             family="monospace", transform=axs.transAxes)

    aus = ROOT / "test" / "render_aug_v021.png"
    fig.savefig(aus, dpi=100, bbox_inches="tight", facecolor="white")
    print(f"PNG -> {aus.name} ({aus.stat().st_size} B)")
    print(f"NEU gegenueber Legacy: " + ", ".join(
        f"K{int(t.kid)}@{int(t.entry_bar)}({float(t.r):+.2f})"
        for t in tr_an
        if all(abs(float(t.bar) - float(u.bar)) > 1e-9
               or int(t.kid) != int(u.kid) for u in tr_leg)))

    zeilen.insert(0, f"AUG VOLL n={n} box={BOX} | V021 AN {len(tr_an)}/"
                     f"{ra:+.6f} | Legacy {len(tr_leg)}/{rl:+.6f} | "
                     f"ZP-5 {zp5}")
    (ROOT / "test" / "render_aug_v021_out.txt").write_text(
        "\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"Protokoll -> render_aug_v021_out.txt")


if __name__ == "__main__":
    main()
