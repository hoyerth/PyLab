# -*- coding: utf-8 -*-
"""READ-ONLY: Vollzeitraum-Chart AUG (Bars 0..1288, inkl. H2) -- _p8-Stand.

Das offizielle Harness-PNG (_zeichne_se_png) beschneidet die Kanten bei
Box-Ende + 20 Bars. Fuer die H2-Arbeit wird hier ein Vollzeitraum-Chart
gezeichnet (kein Engine-Eingriff, nur lesende Auswertung des Scan-Objekts).

Arretiert (Mentor): geloeschte R21-Kanten werden NICHT gezeichnet
("geloescht heisst: tot und im Chart unsichtbar").
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_png", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n                      # Vollzeitraum-Trades (9)
setups, stats = engine._se_trades(scan, cfg)

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402
import numpy as np                               # noqa: E402
import pandas as pd                              # noqa: E402
from matplotlib.lines import Line2D              # noqa: E402

d = scan["d"]
ts = pd.to_datetime(d["ts"])
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
idx = np.arange(n)
out = ROOT / "test" / "kanten_engine_trades_AUG_H2_voll.png"

# Eingangs-/Gegenkanten der Trades (dicker zeichnen)
prio_kids = {t.kid for t in setups}

fig, (ax1, axs) = plt.subplots(
    2, 1, figsize=(20, 13),
    gridspec_kw={"height_ratios": [4.0, 1.35], "hspace": 0.10})

# --- Hintergrund: Box / H2 -------------------------------------------------
ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=0)
ax1.axvspan(box_end, n, color="#1f77b4", alpha=0.05, zorder=0)
ax1.axvline(box_end, color="black", lw=1.4, ls=":", alpha=0.8, zorder=2)
ax1.text(box_end + 6, hi.max() * 0.999, "H2 ab 19.08.", fontsize=10,
         va="top", color="#1f77b4")
ax1.text(6, hi.max() * 0.999, "BOX 10.08.-18.08.", fontsize=10, va="top",
         color="#555555")

# --- Preis ----------------------------------------------------------------
ax1.plot(idx, cl, color="#1f77b4", lw=0.9, alpha=0.95, zorder=3)

# --- Alle lebenden Kanten ueber ihre VOLLE Lebensdauer --------------------
for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
    col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
    ls = "-" if e.seite == "OBEN" else "--"
    lw = 2.0 if e.kid in prio_kids else 1.0
    al = 0.85 if e.kid in prio_kids else 0.45
    b_first = min(b for b, _ in e.wicks)
    b_last = max(b for b, _ in e.wicks)
    x0 = max(0, b_first - 20)
    x1 = min(n - 1, b_last + 20)
    ax1.plot(np.arange(x0, x1 + 1), np.full(x1 - x0 + 1, e.basis),
             color=col, lw=lw, ls=ls, alpha=al, zorder=4)
    # Eichpunkte (Dochte)
    ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], ".",
             ms=3.0, color=col, alpha=0.75, zorder=5)
    # Beschriftung am linken Linienanfang
    ax1.text(x0 + 2, e.basis, f"K{e.kid}", fontsize=6.5, color=col,
             va="center", zorder=7)

# --- Seeds (offen, < 2 Touches) -------------------------------------------
for e in scan["seeds"]:
    col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
    ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], "x", ms=5,
             color=col, alpha=0.6, zorder=5)
    ax1.text(e.wicks[0][0] + 2, e.basis, f"s{e.kid}", fontsize=6,
             color=col, va="center", zorder=7)

# --- Sweep-Sperren ---------------------------------------------------------
for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
    ax1.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black", mew=0.3)

# --- Trades (Entry, SL-TP2-Range, Label) ----------------------------------
for t in setups:
    col = "#d62728" if t.richtung == "SHORT" else "#2ca02c"
    in_box = t.bar < box_end
    ax1.plot(t.bar, t.basis, "o", ms=9 if in_box else 10,
             color=col, zorder=8, mec="black", mew=0.6,
             mfc=col if in_box else "white")
    ax1.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.2, alpha=0.5,
             ls=":", zorder=6)
    ax1.annotate(f"K{t.kid} {t.r:+.2f}R\nbar {t.bar}",
                 (t.bar, t.basis), textcoords="offset points",
                 xytext=(0, 14 if t.richtung == "SHORT" else -22),
                 ha="center", fontsize=8, color=col, zorder=9,
                 bbox=dict(boxstyle="round,pad=0.15", fc="white", alpha=0.75,
                           ec=col, lw=0.5))

# --- H2-Staffel-Neugeburten markieren -------------------------------------
geb_h2 = [e for e in list(scan["edges"]) + list(scan["seeds"])
          if e.geburts_bar >= box_end]
for e in geb_h2:
    ax1.plot(e.geburts_bar, e.basis, "^", ms=5, color="#ff7f0e",
             zorder=7, mec="black", mew=0.3)

# --- Achsen ---------------------------------------------------------------
ticks = np.linspace(0, n - 1, 13).astype(int)
ax1.set_xticks(ticks)
ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in ticks],
                    fontsize=8, rotation=0)
ax1.set_title(
    f"V3-STRAIGHT-EDGE-HARNESS AUG VOLLZEITRAUM (0..{n}) | SE_BAND "
    f"{scan['band_pct']:.3f}% | `_p9` scharf: B2 + Gate aus | "
    f"{len(scan['edges'])} Kanten "
    f"({sum(1 for r in (scan.get('r21_geloescht') or []) if r[1] >= 0)} "
    f"geloescht) | "
    f"{len(setups)} Trades / {sum(t.r for t in setups):+.2f} R", fontsize=12)
ax1.set_xlim(-5, n + 5)
ax1.grid(alpha=0.15, ls=":")

# --- Statistik-Panel ------------------------------------------------------
axs.axis("off")
r21 = scan.get("r21_geloescht") or []
gel = [r for r in r21 if r[1] >= 0]
gesp = [r for r in r21 if r[1] < 0]
box_tr = [t for t in setups if t.bar < box_end]
h2_tr = [t for t in setups if t.bar >= box_end]
z = [
    f"Kanten: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds "
    f"= {len(scan['edges']) + len(scan['seeds'])} lebend "
    f"(93 orig - {len(gel)} R21 - {len(gesp)} gesperrte Geburten)",
    f"R21: {len(gel)} geloescht | {len(gesp)} Geburten gesperrt | "
    f"{len(scan.get('tombstones') or [])} Tombstones (nicht gezeichnet)",
    f"BOX : {len(box_tr)} Trades / {sum(t.r for t in box_tr):+.2f} R",
    f"H2  : {len(h2_tr)} Trades / {sum(t.r for t in h2_tr):+.2f} R   "
    f"(SHORT {sum(1 for t in h2_tr if t.richtung == 'SHORT')} / "
    f"{sum(t.r for t in h2_tr if t.richtung == 'SHORT'):+.2f} R | LONG "
    f"{sum(1 for t in h2_tr if t.richtung == 'LONG')} / "
    f"{sum(t.r for t in h2_tr if t.richtung == 'LONG'):+.2f} R)",
    f"GESAMT: {len(setups)} Trades / {sum(t.r for t in setups):+.2f} R | "
    f"Stacking {stats.get('stacking_blockiert')} | "
    f"Zyklus {stats.get('zyklus_blockiert')} | "
    f"Quartil {stats.get('quartil_blockiert')} | "
    f"Blocker {stats.get('blocker')}",
    f"H2-Neugeburten: {len(geb_h2)} (Dreiecke) | "
    f"davon gehandelt: {sum(1 for e in geb_h2 if e.kid in prio_kids)}",
]
axs.text(0.5, 0.97, "\n".join(z), fontsize=10.5, va="top", ha="center",
         family="monospace", transform=axs.transAxes)

leg = [
    Line2D([0], [0], color="#d62728", lw=1.6, label="OBEN-Kante (SE)"),
    Line2D([0], [0], color="#2ca02c", ls="--", lw=1.6,
           label="UNTEN-Kante (SE)"),
    Line2D([0], [0], marker="o", color="w", mfc="#d62728", ms=8,
           label="SHORT-Trade (gefuellt = Box)"),
    Line2D([0], [0], marker="o", color="w", mfc="#2ca02c", ms=8,
           label="LONG-Trade (gefuellt = Box)"),
    Line2D([0], [0], marker="^", color="w", mfc="#ff7f0e", ms=7,
           label="H2-Neugeburt (Staffel)"),
    Line2D([0], [0], marker="x", color="w", mfc="red", ms=7,
           label="Sweep-Sperre"),
    Line2D([0], [0], marker="x", color="w", mfc="gray", ms=6,
           label="Seed (< 2 Touches)"),
]
ax1.legend(handles=leg, loc="upper left", fontsize=9, ncol=2,
           framealpha=0.92)

fig.subplots_adjust(left=0.045, right=0.99, top=0.955, bottom=0.07)
fig.savefig(out, dpi=300)
plt.close(fig)
print(f"PNG geschrieben: {out}")
print(f"  Kanten gezeichnet: {len(scan['edges'])} edges + "
      f"{len(scan['seeds'])} seeds")
print(f"  Trades: {len(setups)} / {sum(t.r for t in setups):+.2f} R")
