# -*- coding: utf-8 -*-
"""READ-ONLY: Endgueltiger Abgleich H2-Zielvorgabe <-> v0.4-Phasenpivots.

Zeigt je Ziel-Touch: bar, UTC-Projektions-Label (v0.4-Konvention),
Berlin-Wanduhr-Label, und den naechsten v0.4-Pivot (beide Konventionen).
Ausserdem: der 2-Close-Ausbruch, der Phase P9 startete.

Kein Schreiben, keine Aenderung an scripts/.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import market_segmentation as ms  # noqa: E402

cfg = ms.SegmentConfig()
df = ms.load_data(cfg.db_path, cfg.start, cfg.ende)
res = ms.segmentiere_markt(df, cfg)
phases = res.phases
hi = df["high"].to_numpy(dtype=float)
lo = df["low"].to_numpy(dtype=float)
op = df["open"].to_numpy(dtype=float)
cl = df["close"].to_numpy(dtype=float)
ts = df["ts"]

# v0.4-Zeitstempel sind UTC-Projektion -> Berlin = +2 h
def berlin(t):
    return t + __import__("pandas").Timedelta(hours=2)

idx_utc = {t.strftime("%d.%m. %H:%M"): i for i, t in enumerate(ts)}
idx_berlin = {berlin(t).strftime("%d.%m. %H:%M"): i for i, t in enumerate(ts)}

alle_piv = []
for pi, p in enumerate(phases, 1):
    for t, v in zip(p.h_ts, p.h_prices):
        alle_piv.append((t, v, "H", pi))
    for t, v in zip(p.l_ts, p.l_prices):
        alle_piv.append((t, v, "L", pi))

ZIEL = [
    ("Upper1", "H", 69.90, ["21.08. 10:30", "21.08. 13:15", "21.08. 18:45",
                            "24.08. 15:00", "25.08. 02:00"]),
    ("Upper2", "H", 69.62, ["26.08. 04:30", "27.08. 03:45", "27.08. 19:00"]),
    ("Lower1", "L", 68.88, ["21.08. 16:30"]),
    ("Lower2", "L", 68.40, ["24.08. 03:30", "24.08. 17:45", "24.08. 20:00"]),
    ("Lower3", "L", 67.60, ["25.08. 04:45", "25.08. 11:00", "25.08. 15:00",
                            "26.08. 17:00", "27.08. 15:45"]),
]

print("=" * 128)
print("H2-ZIEL-TOUCHS <-> v0.4-PHASENPIVOTS (nur Pivot-Treffer gelistet)")
print("=" * 128)
for name, seite, level, zeiten in ZIEL:
    print(f"\n### {name}  Ziel {level:.2f} ({seite})")
    print(f"  {'Ziel-Zeit':16s} | {'Treffer?':8s} | {'v0.4-Pivot':16s} "
          f"{'bar':>5s} {'Preis':>8s} {'Phase':>6s} {'dZiel':>7s} "
          f"{'Berlin':16s}")
    for z in zeiten:
        b = idx_utc.get(z)
        if b is None:
            print(f"  {z:16s} | nicht vorhanden")
            continue
        pv = next((x for x in alle_piv if x[0] == ts.iloc[b] and x[2] == seite),
                  None)
        px = hi[b] if seite == "H" else lo[b]
        if pv:
            print(f"  {z:16s} | PIVOT    | {pv[0].strftime('%d.%m. %H:%M'):16s} "
                  f"{b:5d} {px:8.3f} P{pv[3]:<4d} {px - level:+7.3f} "
                  f"{berlin(ts.iloc[b]).strftime('%d.%m. %H:%M'):16s}")
        else:
            print(f"  {z:16s} | KEIN Piv | {'-':16s} {b:5d} {px:8.3f} "
                  f"{'-':>6s} {px - level:+7.3f} "
                  f"{berlin(ts.iloc[b]).strftime('%d.%m. %H:%M'):16s}")

print("\n" + "=" * 128)
print("AUSBRUCH, der Phase P9 startete (2-Close ueber h_ref = 68.320 + TOL 0.34)")
print("=" * 128)
print(f"{'bar':>5s} {'UTC-Proj':17s} {'Berlin':17s} {'open':>8s} {'close':>8s} "
      f"{'high':>8s} {'ueber 68.660?':>14s}")
for b in range(844, 856):
    print(f"{b:5d} {ts.iloc[b].strftime('%d.%m. %H:%M'):17s} "
          f"{berlin(ts.iloc[b]).strftime('%d.%m. %H:%M'):17s} "
          f"{op[b]:8.3f} {cl[b]:8.3f} {hi[b]:8.3f} "
          f"{'JA' if cl[b] > 68.660 else 'nein':>14s}")

print("\n" + "=" * 128)
print("PHASE P9: U_final/L_final vs. H2-Ziel-Level")
print("=" * 128)
p9 = phases[8]
print(f"  P9 {p9.start.strftime('%d.%m. %H:%M')} -> {p9.ende.strftime('%d.%m. %H:%M')}"
      f"  (UTC-Proj) | U_final={p9.U_final:.4f} | L_final={p9.L_final:.4f}")
print(f"  H-Touches in P9: {len(p9.h_prices)} | L-Touches: {len(p9.l_prices)}")
print(f"  Ziel Upper1 69.90  -> Delta zu U_final: {p9.U_final - 69.90:+.4f}")
print(f"  Ziel Lower1 68.88  -> Delta zu L_hist[0] ("
      f"{p9.L_hist[0][1]:.3f}): {p9.L_hist[0][1] - 68.88:+.4f}")
print(f"  Ziel Lower2 68.40  -> Delta zu L_hist[-1] ("
      f"{p9.L_hist[-1][1]:.3f}): {p9.L_hist[-1][1] - 68.40:+.4f}")
