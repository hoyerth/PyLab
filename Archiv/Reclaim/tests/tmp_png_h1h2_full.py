# -*- coding: utf-8 -*-
"""READ-ONLY: AUG H1+H2 FULL (Bars 0..1288) -- Stand `_p9` scharf (Teil 9).

Ein Chart ueber den GESAMTEN Zeitraum:
  H1 = Box-Phase 10.08.-18.08. (bars < 644)   -- Trades gefuellt
  H2 = Expansion ab 19.08.   (bars >= 644)    -- Trades hohl

Die Trades werden im VOLL-LAUF gerechnet (`box_end_bar = n`), weil das die
arretierte Kennzahl-Basis aus §7.2 Teil 7/9 ist (14 Trades / +40,45 R).
Kein Engine-Eingriff, nur lesende Auswertung des Scan-Objekts.

Arretiert: geloeschte R21-Kanten werden NICHT als Linien gezeichnet
("geloescht heisst: tot und im Chart unsichtbar"); ihre Tombstone-Baender
erscheinen als dezente graue Horizontale.

Aufruf: .venv\\Scripts\\python.exe test\\tmp_png_h1h2_full.py
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


engine = load("ke_png_h1h2", P)
cfg = engine.StraightEdgeHarnessKonfiguration()

# --- `_p9`-Stand belegen (Datenvertrag §7.2 Teil 9) -----------------------
assert cfg.retest_zyklus_referenz == "ENTRY", cfg.retest_zyklus_referenz
assert cfg.stacking_gate_aktiv is False, cfg.stacking_gate_aktiv
assert cfg.sweep_mindestdurchstich_pct == 0.0, cfg.sweep_mindestdurchstich_pct
assert cfg.retest_zyklus_bars == 12, cfg.retest_zyklus_bars

scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n                      # Voll-Lauf = arretierte Basis
setups, stats = engine._se_trades(scan, cfg)

r_sum = sum(t.r for t in setups)
assert len(setups) == 14 and round(r_sum, 2) == 40.45, (len(setups), r_sum)
assert stats.get("stacking_blockiert", 0) == 0, stats.get("stacking_blockiert")

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402
import numpy as np                               # noqa: E402
import pandas as pd                              # noqa: E402
from matplotlib.lines import Line2D              # noqa: E402

d = scan["d"]
ts = pd.to_datetime(d["ts"])
hi = d["high"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
idx = np.arange(n)
out = ROOT / "test" / "kanten_engine_trades_AUG_H1H2_FULL.png"
prio_kids = {t.kid for t in setups}
tombs = scan.get("tombstones") or []

fig, (ax1, axs) = plt.subplots(
    2, 1, figsize=(20, 13),
    gridspec_kw={"height_ratios": [4.0, 1.35], "hspace": 0.10})

# --- Hintergrund: H1 / H2 -------------------------------------------------
ax1.axvspan(0, box_end, color="gray", alpha=0.10, zorder=0)
ax1.axvspan(box_end, n, color="#1f77b4", alpha=0.05, zorder=0)
ax1.axvline(box_end, color="black", lw=1.5, ls=":", alpha=0.85, zorder=2)
ax1.text(6, hi.max() * 0.9995, "H1  BOX 10.08.-18.08. (bars < 644)",
         fontsize=10.5, va="top", color="#444444")
ax1.text(n - 8, hi.max() * 0.9995, "H2  EXPANSION ab 19.08.",
         fontsize=10.5, va="top", ha="right", color="#1f77b4")

# --- Tombstone-Baender (geloeschte Kanten: BAND, keine Linie) -------------
for tk, _tseite, tp in tombs:
    ax1.plot([tk, n - 1], [tp, tp], color="gray", lw=0.8, ls=":",
             alpha=0.30, zorder=1)

# --- Preis ---------------------------------------------------------------
ax1.plot(idx, cl, color="#1f77b4", lw=0.9, alpha=0.95, zorder=3)

# --- Lebende Kanten ueber die VOLLE Lebensdauer --------------------------
for e in sorted(scan["edges"], key=lambda x: (x.seite, x.basis)):
    col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
    ls = "-" if e.seite == "OBEN" else "--"
    lw = 2.0 if e.kid in prio_kids else 1.0
    al = 0.85 if e.kid in prio_kids else 0.45
    b_first = min(b for b, _ in e.wicks)
    b_last = max(b for b, _ in e.wicks)
    x0 = max(0, b_first - 20)
    x1 = min(n - 1, b_last + 20)
    if x1 <= x0:
        continue
    ax1.plot(np.arange(x0, x1 + 1), np.full(x1 - x0 + 1, e.basis),
             color=col, lw=lw, ls=ls, alpha=al, zorder=4)
    ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], ".",
             ms=3.0, color=col, alpha=0.75, zorder=5)
    ax1.text(x0 + 2, e.basis, f"K{e.kid}", fontsize=6.5, color=col,
             va="center", zorder=7)

# --- Seeds (offen, < 2 Touches) ------------------------------------------
for e in scan["seeds"]:
    col = "#d62728" if e.seite == "OBEN" else "#2ca02c"
    ax1.plot([b for b, _ in e.wicks], [p for _, p in e.wicks], "x", ms=5,
             color=col, alpha=0.6, zorder=5)
    ax1.text(e.wicks[0][0] + 2, e.basis, f"s{e.kid}", fontsize=6,
             color=col, va="center", zorder=7)

# --- Sweep-Sperren --------------------------------------------------------
for (b, _se, px, _ref, _dd) in scan["sweep_sperren"]:
    ax1.plot(b, px, "x", ms=8, color="red", zorder=6, mec="black", mew=0.3)

# --- Staffel-Neugeburten in H2 (Dreiecke) --------------------------------
geb_h2 = [e for e in list(scan["edges"]) + list(scan["seeds"])
          if e.geburts_bar >= box_end]
for e in geb_h2:
    ax1.plot(e.geburts_bar, e.basis, "^", ms=6, color="#ff7f0e",
             zorder=7, mec="black", mew=0.35)

# --- Trades: H1 gefuellt / H2 hohl ---------------------------------------
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
                 xytext=(0, 15 if t.richtung == "SHORT" else -23),
                 ha="center", fontsize=8, color=col, zorder=9,
                 bbox=dict(boxstyle="round,pad=0.15", fc="white", alpha=0.78,
                           ec=col, lw=0.5))

# --- Achsen ---------------------------------------------------------------
ticks = np.linspace(0, n - 1, 13).astype(int)
ax1.set_xticks(ticks)
ax1.set_xticklabels([ts.iloc[i].strftime("%d.%m %H:%M") for i in ticks],
                    fontsize=8)
ax1.set_title(
    f"V3-STRAIGHT-EDGE-HARNESS AUG H1+H2 FULL (0..{n}) | SE_BAND "
    f"{scan['band_pct']:.3f}% | `_p9` scharf: B2-Entry-Ref (v=12) + "
    f"Stacking-Gate aus + Sweep entkoppelt | "
    f"{len(scan['edges'])} Kanten | {len(setups)} Trades / {r_sum:+.2f} R",
    fontsize=12)
ax1.set_xlim(-5, n + 5)
ax1.grid(alpha=0.15, ls=":")

# --- Statistik-Panel: DAUERHAFT ZENTRIERT (Sichtpruefungs-Konvention) -----
# Verankert 2026-09-09 (Anwender-Vorgabe): Statistik steht mittig im Panel,
# Legende oben links im Chart. Gilt fuer ALLE Sichtpruefungs-Grafiken.
axs.axis("off")
r21 = scan.get("r21_geloescht") or []
gel = [r for r in r21 if r[1] >= 0]
gesp = [r for r in r21 if r[1] < 0]
box_tr = [t for t in setups if t.bar < box_end]
h2_tr = [t for t in setups if t.bar >= box_end]
sh_b = [t for t in box_tr if t.richtung == "SHORT"]
lg_b = [t for t in box_tr if t.richtung == "LONG"]
sh_h = [t for t in h2_tr if t.richtung == "SHORT"]
lg_h = [t for t in h2_tr if t.richtung == "LONG"]
z = [
    f"ARRETIERT `_p9` (Teil 9): retest_zyklus_referenz=ENTRY | "
    f"retest_zyklus_bars=12 | stacking_gate_aktiv=False | "
    f"sweep_mindestdurchstich_pct=0.0",
    f"Kanten: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds "
    f"= {len(scan['edges']) + len(scan['seeds'])} lebend | "
    f"R21: {len(gel)} geloescht / {len(gesp)} Geburten gesperrt | "
    f"{len(tombs)} Tombstones (als Baender, nicht als Linien)",
    f"H1  (BOX, bars < {box_end}) : {len(box_tr):2d} Trades / "
    f"{sum(t.r for t in box_tr):+7.2f} R   "
    f"SHORT {len(sh_b)}/{sum(t.r for t in sh_b):+.2f} | "
    f"LONG {len(lg_b)}/{sum(t.r for t in lg_b):+.2f}",
    f"H2  (EXP, bars >= {box_end}): {len(h2_tr):2d} Trades / "
    f"{sum(t.r for t in h2_tr):+7.2f} R   "
    f"SHORT {len(sh_h)}/{sum(t.r for t in sh_h):+.2f} | "
    f"LONG {len(lg_h)}/{sum(t.r for t in lg_h):+.2f}",
    f"GESAMT (Voll-Lauf, arretierte Basis): {len(setups)} Trades / "
    f"{r_sum:+.2f} R | Stacking {stats.get('stacking_blockiert')} | "
    f"Zyklus {stats.get('zyklus_blockiert')} | "
    f"Quartil {stats.get('quartil_blockiert')} | "
    f"Blocker {stats.get('blocker')} | R21 {len(gel)}",
    f"H2-Neugeburten: {len(geb_h2)} (Dreiecke) | "
    f"davon gehandelt: {sum(1 for e in geb_h2 if e.kid in prio_kids)} | "
    f"Promovierte Primaer-Anker: {stats.get('promotionen')}",
]
axs.text(0.5, 0.97, "\n".join(z), fontsize=10.5, va="top", ha="center",
         family="monospace", transform=axs.transAxes)

leg = [
    Line2D([0], [0], color="#d62728", lw=1.6, label="OBEN-Kante (SE)"),
    Line2D([0], [0], color="#2ca02c", ls="--", lw=1.6,
           label="UNTEN-Kante (SE)"),
    Line2D([0], [0], marker="o", color="w", mfc="#d62728", ms=8,
           label="SHORT-Trade (gefuellt = H1, hohl = H2)"),
    Line2D([0], [0], marker="o", color="w", mfc="#2ca02c", ms=8,
           label="LONG-Trade (gefuellt = H1, hohl = H2)"),
    Line2D([0], [0], marker="^", color="w", mfc="#ff7f0e", ms=7,
           label="H2-Neugeburt (Staffel)"),
    Line2D([0], [0], marker="x", color="w", mfc="red", ms=7,
           label="Sweep-Sperre"),
    Line2D([0], [0], marker="x", color="w", mfc="gray", ms=6,
           label="Seed (< 2 Touches)"),
    Line2D([0], [0], color="gray", ls=":", lw=1.0,
           label="Tombstone-Band (R21, Neugeburt gesperrt)"),
]
ax1.legend(handles=leg, loc="upper left", fontsize=9, ncol=2,
           framealpha=0.92)

fig.subplots_adjust(left=0.045, right=0.99, top=0.955, bottom=0.07)
fig.savefig(out, dpi=300)
plt.close(fig)
print(f"PNG geschrieben: {out}")
print(f"  n={n} | box_end={box_end} | Kanten "
      f"{len(scan['edges'])} edges + {len(scan['seeds'])} seeds")
print(f"  H1: {len(box_tr)} Trades / {sum(t.r for t in box_tr):+.2f} R | "
      f"H2: {len(h2_tr)} Trades / {sum(t.r for t in h2_tr):+.2f} R")
print(f"  GESAMT: {len(setups)} Trades / {r_sum:+.2f} R | "
      f"Stacking {stats.get('stacking_blockiert')} | "
      f"Zyklus {stats.get('zyklus_blockiert')}")
