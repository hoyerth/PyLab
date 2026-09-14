# -*- coding: utf-8 -*-
"""READ-ONLY VORSCHAU-PNG: Ist-Regel vs. entkoppelte Regel (H1-Nachtrag).

Erzeugt ZWEI neue PNGs mit eigenstaendigem Dateinamen. Die arretierte
`test/kanten_engine_trades_AUG_mC.png` wird NICHT beruehrt (kein Overwrite).

  A) kanten_engine_trades_AUG_VORSCHAU_ist.png  -- Ist-Regeln (arretiert)
  B) kanten_engine_trades_AUG_VORSCHAU_neu.png  -- Vorschlag:
       Barriere 1: Sweep = reiner Durchstich (touch_band_pct nur Touch)
       Barriere 2: Stacking-Gate entfernt
       Zyklus-Uhr: Entry-Referenz, retest_zyklus_bars = 12

Engine-Aenderung nur im RAM (exec(compile())), Platte unveraendert.
"""
from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

G3O = ("        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
       "        if not (hi[k] > basis and band < dist_o\r\n"
       "                <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G3U = ("    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
       "    if not (lo[k] < basis and band < dist_u\r\n"
       "            <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G2 = ("            if dist <= cfg.touch_band_pct:\r\n"
      "                continue                        # Beruehrung/in-band (Schatten)\r\n")
G2S = ("            if cfg.touch_band_pct < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
       "                pool.append(e)\r\n")
GSTACK = "            _vor = letzter_trade.get(kd.kid)"
GCHECK = "            if k - kd.letzter_sweep_bar < cfg.retest_zyklus_bars:\r\n"
for nm, an in (("G3O", G3O), ("G3U", G3U), ("G2", G2), ("G2S", G2S),
               ("GCHECK", GCHECK)):
    assert SRC.count(an) == 1, f"Anker {nm}: {SRC.count(an)} Treffer"
assert SRC.count(GSTACK) == 1


def entferne_stacking(src: str) -> str:
    start = src.index(GSTACK)
    zeilenende = src.index("\r\n", start) + 2
    cpos = src.index("                    continue\r\n", zeilenende)
    cende = cpos + len("                    continue\r\n")
    return src.replace(src[start:cende],
                       "            # [RAM] Stacking-Gate deaktiviert\r\n"
                       "            _vor = letzter_trade.get(kd.kid)\r\n", 1)


def entkopple_band(src: str) -> str:
    s = src.replace(
        G3O, "        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
             "        if not (hi[k] > basis and 0.0 < dist_o\r\n"
             "                <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G3U, "    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
             "    if not (lo[k] < basis and 0.0 < dist_u\r\n"
             "            <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G2, "            if dist <= 0.0:\r\n"
            "                continue                        # nur Durchstich zaehlt\r\n", 1)
    s = s.replace(
        G2S, "            if 0.0 < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
             "                pool.append(e)\r\n", 1)
    return s


def entry_anker(src: str) -> str:
    return src.replace(
        GCHECK,
        "            _vor_zeit = letzter_trade.get(kd.kid)\r\n"
        "            if (_vor_zeit is not None and\r\n"
        "                    entry_bar - _vor_zeit.entry_bar\r\n"
        "                    < cfg.retest_zyklus_bars):\r\n", 1)


NEU_SRC = entry_anker(entkopple_band(entferne_stacking(SRC)))


def lauf(src: str, name: str):
    mod = load(name, src)
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = sc["n"]
    tr, st = mod._se_trades(sc, cfg)
    return mod, sc, tr, st


def zeichne(mod, scan, setups, out: Path, titel: str, box_only: bool):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    band = scan["band_pct"]
    box_end = scan["box_end_bar"]
    d = scan["d"]
    n = scan["n"]
    ts = pd.to_datetime(d["ts"])
    cl = d["close"].to_numpy(dtype=float)
    idx = np.arange(n)

    box_edges = [e for e in scan["edges"]
                 if any(b <= box_end - 1 for b, _ in e.wicks)]
    box_edges.sort(key=lambda e: e.basis)

    fig, (ax1, axs) = plt.subplots(
        2, 1, figsize=(18, 12),
        gridspec_kw={"height_ratios": [3.6, 1.6], "hspace": 0.12})

    ax1.plot(idx, cl, color="#1f77b4", lw=0.8, alpha=0.9, zorder=2)
    ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=1)
    ax1.axvline(box_end, color="black", lw=1.2, ls=":", alpha=0.7)
    for e in box_edges:
        col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
        ls = "-" if e.seite == "OBEN" else "--"
        b_first = min(b for b, _ in e.wicks if b <= box_end - 1)
        b_last = max(b for b, _ in e.wicks if b <= box_end - 1)
        x0, x1 = max(0, b_first - 20), min(n - 1, b_last + 20)
        ax1.plot(np.arange(x0, x1 + 1), np.full(x1 - x0 + 1, e.basis),
                 color=col, lw=1.2, ls=ls, alpha=0.5, zorder=3)
    for e in scan["seeds"]:
        if e.ist_prim_anker:
            ax1.axhline(e.basis, color="#d62728", lw=1.8, ls="-.",
                        alpha=0.85, zorder=5)
    for s in setups:
        col = "#d62728" if s.richtung == "SHORT" else "#2ca02c"
        ax1.plot(s.bar, s.basis, "o", ms=7, color=col, zorder=6, mec="black",
                 mew=0.4)
        ax1.plot([s.bar, s.bar], [s.tp2, s.sl], color=col, lw=1.0,
                 alpha=0.35, ls=":", zorder=4)
        # Entry-Pfeil und Exit-Marke (neu, fuer die Vorschau)
        ax1.annotate("", xy=(s.entry_bar, s.entry), xytext=(s.bar, s.basis),
                     arrowprops=dict(arrowstyle="->", color=col, lw=1.1,
                                     alpha=0.85), zorder=7)
        ax1.plot(s.entry_bar, s.entry, marker="v" if s.richtung == "SHORT"
                 else "^", ms=8, color=col, mec="black", mew=0.4, zorder=8)
        if s.exit2_bar < n:
            ax1.plot(s.exit2_bar, s.tp2 if s.r > 0 else s.sl, marker="s",
                     ms=5, color=col, alpha=0.8, mec="black", mew=0.3,
                     zorder=7)
    ticks = np.linspace(0, n - 1, 9).astype(int)
    ax1.set_xticks(ticks)
    ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m") for i in ticks],
                        fontsize=8)
    ax1.set_title(titel, fontsize=11)
    ax1.set_xlim(-5, n + 5)

    axs.axis("off")
    z = [f"SE-Kanten {len(scan['edges'])} (OBEN "
         f"{sum(1 for e in scan['edges'] if e.seite=='OBEN')}) | "
         f"Seeds {len(scan['seeds'])} | Sweep-Sperren "
         f"{len(scan['sweep_sperren'])}"]
    z.append(f"Trades: {len(setups)}")
    gew = sum(1 for s in setups if s.resultat == "GEWONNEN")
    verl = sum(1 for s in setups if s.resultat == "VERLOREN")
    sum_r = sum(s.r for s in setups)
    z.append(f"GEWONNEN {gew} | VERLOREN {verl} | Summe R {sum_r:+.2f}")
    k20 = [s for s in setups if s.kid == 20 and 200 < s.bar < 300]
    if k20:
        z.append("K20 12.08.: " + " | ".join(
            f"bar {s.bar} -> entry {s.entry_bar} {s.r:+.2f} R" for s in k20))
    axs.text(0.005, 0.97, "\n".join(z), fontsize=10, va="top",
             family="monospace", transform=axs.transAxes)
    leg = [Line2D([0], [0], color="#d62728", lw=1.2, label="OBEN-Kante (SE)"),
           Line2D([0], [0], color="#2ca02c", ls="--", lw=1.2,
                  label="UNTEN-Kante (SE)"),
           Line2D([0], [0], marker="o", color="w", mfc="#d62728",
                  label="SHORT-Setup"),
           Line2D([0], [0], marker="o", color="w", mfc="#2ca02c",
                  label="LONG-Setup"),
           Line2D([0], [0], marker="v", color="w", mfc="#d62728",
                  label="SHORT-Entry"),
           Line2D([0], [0], marker="^", color="w", mfc="#2ca02c",
                  label="LONG-Entry")]
    ax1.legend(handles=leg, loc="upper left", fontsize=8)
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return out


TITEL_IST = ("V3-STRAIGHT-EDGE-HARNESS AUG | IST-STAND (arretiert) | "
             "Stacking-Gate AKTIV | Sweep >= touch_band 0.12% | Zyklus-Uhr "
             "SWEEP-Ref v=12")
TITEL_NEU = ("V3-STRAIGHT-EDGE-HARNESS AUG | VORSCHAU (nicht arretiert) | "
             "Stacking AUS | Sweep = reiner Durchstich | Zyklus-Uhr ENTRY-Ref v=12")

print("=" * 120)
print("VORSCHAU-PNG: Ist-Regel vs. entkoppelte Regel")
print("=" * 120)
res = {}
for label, src, titel, datei in (
        ("IST ", SRC, TITEL_IST, "kanten_engine_trades_AUG_VORSCHAU_ist.png"),
        ("NEU ", NEU_SRC, TITEL_NEU, "kanten_engine_trades_AUG_VORSCHAU_neu.png")):
    mod, sc, tr, st = lauf(src, f"png_{label.strip().lower()}")
    out = ROOT / "test" / datei
    zeichne(mod, sc, tr, out, titel, box_only=False)
    res[label] = (tr, st)
    print(f"  {label} | Trades {len(tr):2d} | Netto-R {sum(t.r for t in tr):+7.2f} | "
          f"Zyklus {st.get('zyklus_blockiert', 0):2d} | "
          f"Stacking {st.get('stacking_blockiert', 0):2d} | -> {out.name}")

print("")
print("  K20-Pfade 12.08. (Vergleich):")
for label in res:
    tr, st = res[label]
    k20 = [t for t in tr if t.kid == 20 and 200 < t.bar < 300]
    print(f"    {label}: " + (" | ".join(
        f"bar {t.bar}->entry {t.entry_bar} {t.r:+.2f}R" for t in k20) or "-"))
print("")
print("  Arretierte Datei unberuehrt:",
      (ROOT / "test" / "kanten_engine_trades_AUG_mC.png").name)
