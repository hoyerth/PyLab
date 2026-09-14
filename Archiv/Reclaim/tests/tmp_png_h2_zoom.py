# -*- coding: utf-8 -*-
"""READ-ONLY: H2-Zoom-Chart AUG (Bars 630..1288) -- _p8-Stand.

Zoom auf die Staffel-Neugeburten. Tombstone-Baender werden als dezente
horizontale Markierungen gezeigt (KEINE geloeschten Kanten-Linien: die
bleiben laut Arretierung unsichtbar).
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


engine = load("ke_png2", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n
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
X0 = 630
idx = np.arange(n)
out = ROOT / "test" / "kanten_engine_trades_AUG_H2_zoom.png"
prio_kids = {t.kid for t in setups}

fig, (ax1, axs) = plt.subplots(
    2, 1, figsize=(20, 13),
    gridspec_kw={"height_ratios": [4.0, 1.35], "hspace": 0.10})

ax1.axvspan(box_end, n, color="#1f77b4", alpha=0.05, zorder=0)
ax1.axvline(box_end, color="black", lw=1.4, ls=":", alpha=0.8, zorder=2)

# --- Tombstone-Baender (dezente graue Horizontale, NUR H2) ----------------
tombs = scan.get("tombstones") or []
for tk, tseite, tp in tombs:
    if tk < X0:
        continue
    ax1.plot([X0, n - 1], [tp, tp], color="gray", lw=0.8, ls=":",
             alpha=0.35, zorder=1)

ax1.plot(idx, cl, color="#1f77b4", lw=1.0, alpha=0.95, zorder=3)

# --- Kanten, die in H2 leben ---------------------------------------------
for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
    if max(b for b, _ in e.wicks) < X0:
        continue
    col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
    ls = "-" if e.seite == "OBEN" else "--"
    lw = 2.2 if e.kid in prio_kids else 1.1
    al = 0.9 if e.kid in prio_kids else 0.5
    b_first = min(b for b, _ in e.wicks)
    b_last = max(b for b, _ in e.wicks)
    x0 = max(X0, b_first - 20)
    x1 = min(n - 1, b_last + 20)
    if x1 <= x0:
        continue
    ax1.plot(np.arange(x0, x1 + 1), np.full(x1 - x0 + 1, e.basis),
             color=col, lw=lw, ls=ls, alpha=al, zorder=4)
    ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], ".",
             ms=4.0, color=col, alpha=0.85, zorder=5)
    ax1.text(x0 + 2, e.basis, f"K{e.kid}", fontsize=8, color=col,
             va="center", zorder=7)

for e in scan["seeds"]:
    if max(b for b, _ in e.wicks) < X0:
        continue
    col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
    ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], "x", ms=6,
             color=col, alpha=0.65, zorder=5)
    ax1.text(e.wicks[0][0] + 2, e.basis, f"s{e.kid}", fontsize=7, color=col,
             va="center", zorder=7)

for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
    if b >= X0:
        ax1.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black", mew=0.3)

# --- H2-Neugeburten als Dreiecke ------------------------------------------
geb_h2 = [e for e in list(scan["edges"]) + list(scan["seeds"])
          if e.geburts_bar >= box_end]
for e in geb_h2:
    ax1.plot(e.geburts_bar, e.basis, "^", ms=7, color="#ff7f0e", zorder=7,
             mec="black", mew=0.4)

# --- H2-Trades ------------------------------------------------------------
for t in setups:
    if t.bar < X0:
        continue
    col = "#d62728" if t.richtung == "SHORT" else "#2ca02c"
    ax1.plot(t.bar, t.basis, "o", ms=11, color=col, zorder=9, mec="black",
             mew=0.8)
    ax1.plot([t.bar, t.bar], [t.tp2, t.sl], color=col, lw=1.3, alpha=0.55,
             ls=":", zorder=6)
    ax1.annotate(f"K{t.kid} {t.r:+.2f}R\nbar {t.bar} entry {t.entry_bar}",
                 (t.bar, t.basis), textcoords="offset points",
                 xytext=(0, 18 if t.richtung == "SHORT" else -26),
                 ha="center", fontsize=9, color=col, zorder=10,
                 bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.85,
                           ec=col, lw=0.6))

# --- Achsen ---------------------------------------------------------------
ticks = np.linspace(X0, n - 1, 12).astype(int)
ax1.set_xticks(ticks)
ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in ticks],
                    fontsize=9)
ax1.set_title(
    f"AUG H2-ZOOM (Bars {X0}..{n}) | `_p9` scharf: B2 + Gate aus | "
    f"H2-Neugeburten {len(geb_h2)} (Dreiecke) | H2-Trades "
    f"{sum(1 for t in setups if t.bar >= X0)} / "
    f"{sum(t.r for t in setups if t.bar >= X0):+.2f} R",
    fontsize=12)
ax1.set_xlim(X0 - 3, n + 5)
ax1.grid(alpha=0.15, ls=":")

# --- Panel ----------------------------------------------------------------
axs.axis("off")
h2_tr = [t for t in setups if t.bar >= box_end]
sh = [t for t in h2_tr if t.richtung == "SHORT"]
lg = [t for t in h2_tr if t.richtung == "LONG"]
tom_h2 = [t for t in tombs if t[0] >= X0]
z = [
    f"H2-Neugeburten: {len(geb_h2)} | OBEN "
    f"{sum(1 for e in geb_h2 if e.seite == 'OBEN')} / UNTEN "
    f"{sum(1 for e in geb_h2 if e.seite == 'UNTEN')} | "
    f"davon gehandelt: {sum(1 for e in geb_h2 if e.kid in prio_kids)}",
    f"H2-Trades: {len(h2_tr)} / {sum(t.r for t in h2_tr):+.2f} R   "
    f"SHORT {len(sh)}/{sum(t.r for t in sh):+.2f} R  (K16 716, K51 760, "
    f"K59 853)  |  LONG {len(lg)}/{sum(t.r for t in lg):+.2f} R  "
    f"(K3 650, K45 679)",
    f"Tombstone-Baender ab Bar {X0}: {len(tom_h2)} (gepunktete graue Linien) "
    f"| R21-Loeschungen in H2: "
    f"{sum(1 for r in (scan.get('r21_geloescht') or []) if r[0] >= X0 and r[1] >= 0)}"
    f" | gesperrte Geburten: "
    f"{sum(1 for r in (scan.get('r21_geloescht') or []) if r[0] >= X0 and r[1] < 0)}",
    "Staffel-Lesart: Neugeburten im Expansionsteil sind Liquiditaets-Etappen "
    "-> blinde SHORTs zahlen Lehrgeld (K51/K59).",
]
axs.text(0.5, 0.97, "\n".join(z), fontsize=10.5, va="top", ha="center",
         family="monospace", transform=axs.transAxes)

leg = [
    Line2D([0], [0], color="#d62728", lw=1.8, label="OBEN-Kante"),
    Line2D([0], [0], color="#2ca02c", ls="--", lw=1.8, label="UNTEN-Kante"),
    Line2D([0], [0], marker="^", color="w", mfc="#ff7f0e", ms=8,
           label="H2-Neugeburt"),
    Line2D([0], [0], marker="o", color="w", mfc="#d62728", ms=9,
           label="SHORT-Trade (H2)"),
    Line2D([0], [0], marker="o", color="w", mfc="#2ca02c", ms=9,
           label="LONG-Trade (H2)"),
    Line2D([0], [0], color="gray", ls=":", lw=1.0,
           label="Tombstone-Band (Neugeburt gesperrt)"),
    Line2D([0], [0], marker="x", color="w", mfc="red", ms=7,
           label="Sweep-Sperre"),
]
ax1.legend(handles=leg, loc="upper left", fontsize=9, ncol=2,
           framealpha=0.92)

fig.subplots_adjust(left=0.045, right=0.99, top=0.955, bottom=0.07)
fig.savefig(out, dpi=300)
plt.close(fig)
print(f"PNG geschrieben: {out}")
print(f"  H2-Neugeburten gezeichnet: {len(geb_h2)}")
print(f"  H2-Trades: {len(h2_tr)} / {sum(t.r for t in h2_tr):+.2f} R")
