# -*- coding: utf-8 -*-
"""READ-ONLY: v0.4-Phasen P9/P11/P12 im Detail -- Grenzen, atmende Levels
(U_hist/L_hist), Pivot-Touches und Abgleich mit der H2-Zielvorgabe.

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

# Bar-Index je Zeitstempel
idx_von_ts = {ts: i for i, ts in enumerate(df["ts"])}
hi = df["high"].to_numpy(dtype=float)
lo = df["low"].to_numpy(dtype=float)

print("=" * 122)
print("1) PHASENGRENZEN mit Bar-Index (AUG, Berlin-Wanduhr)")
print("=" * 122)
print(f"{'P':>2s} {'Start-Zeit':17s} {'Bar':>5s} {'Ende-Zeit':17s} {'Bar':>5s} "
      f"{'brk_idx':>7s} {'brk_kante':>10s}")
for i, p in enumerate(phases, 1):
    bs = idx_von_ts.get(p.start)
    be = idx_von_ts.get(p.ende)
    print(f"{i:2d} {p.start.strftime('%d.%m. %H:%M'):17s} {bs if bs is not None else -1:5d} "
          f"{p.ende.strftime('%d.%m. %H:%M'):17s} {be if be is not None else -1:5d} "
          f"{str(p.brk_idx):>7s} "
          f"{(f'{p.brk_kante:10.3f}' if p.brk_kante is not None else '      None')}")

print("\n" + "=" * 122)
print("2) H2-ZIEL-TOUCHS: in welcher v0.4-Phase liegen sie? (Berlin-Wanduhr)")
print("=" * 122)
ZIEL = [
    ("Upper1", "OBEN", 69.90, ["21.08. 10:30", "21.08. 13:15", "21.08. 18:45",
                               "24.08. 15:00", "25.08. 02:00"]),
    ("Upper2", "OBEN", 69.62, ["26.08. 04:30", "27.08. 03:45", "27.08. 19:00"]),
    ("Lower1", "UNTEN", 68.88, ["21.08. 16:30"]),
    ("Lower2", "UNTEN", 68.40, ["24.08. 03:30", "24.08. 17:45", "24.08. 20:00"]),
    ("Lower3", "UNTEN", 67.60, ["25.08. 04:45", "25.08. 11:00", "25.08. 15:00",
                                "26.08. 17:00", "27.08. 15:45"]),
]
idx_zeit = {ts.strftime("%d.%m. %H:%M"): i for i, ts in enumerate(df["ts"])}
for name, seite, level, zeiten in ZIEL:
    print(f"\n{name} (Ziel {level:.2f}, {seite})")
    for z in zeiten:
        b = idx_zeit.get(z)
        if b is None:
            print(f"   {z}  NICHT VORHANDEN")
            continue
        ph = next((k for k, p in enumerate(phases, 1)
                   if p.start <= df["ts"].iloc[b] <= p.ende), None)
        px = hi[b] if seite == "OBEN" else lo[b]
        print(f"   {z}  bar {b:4d}  Docht {px:8.3f}  -> Phase P{ph}")

print("\n" + "=" * 122)
print("3) ATMENDE LEVELS: U_hist/L_hist der Phasen P8-P12")
print("=" * 122)
for i, p in enumerate(phases, 1):
    if i < 8:
        continue
    print(f"\n--- P{i}: {p.start.strftime('%d.%m. %H:%M')} -> "
          f"{p.ende.strftime('%d.%m. %H:%M')} | U_final={p.U_final} "
          f"L_final={p.L_final}")
    print(f"    U_hist ({len(p.U_hist)}):")
    for t, v in p.U_hist:
        print(f"      {t.strftime('%d.%m. %H:%M')}  {v:.3f}")
    print(f"    L_hist ({len(p.L_hist)}):")
    for t, v in p.L_hist:
        print(f"      {t.strftime('%d.%m. %H:%M')}  {v:.3f}")

print("\n" + "=" * 122)
print("4) PIVOT-TOUCHES der Phasen P9/P11/P12 (h_prices/l_prices)")
print("=" * 122)
for i, p in enumerate(phases, 1):
    if i not in (8, 9, 10, 11, 12):
        continue
    print(f"\n--- P{i} ({p.start.strftime('%d.%m.')} - {p.ende.strftime('%d.%m.')})")
    print("    H-Touches:")
    for t, v in zip(p.h_ts, p.h_prices):
        print(f"      {t.strftime('%d.%m. %H:%M')}  {v:.3f}")
    print("    L-Touches:")
    for t, v in zip(p.l_ts, p.l_prices):
        print(f"      {t.strftime('%d.%m. %H:%M')}  {v:.3f}")
