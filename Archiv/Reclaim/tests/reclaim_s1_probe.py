# test/reclaim_s1_probe.py
"""Probe: Preisverlauf 11.-18.08 im Bereich 63-67 (Diagnose Bruch 66.28?)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
import reclaim_edge_store as res  # noqa: E402

df = res.load_data(res.DB_PATH, "2026-08-10", "2026-08-28")

lo, hi = "2026-08-11 00:00", "2026-08-19 00:00"
mask = (df["ts"] >= lo) & (df["ts"] < hi)
sub = df[mask]
print("Datumzeit (UTC)       High    Low   Close   | >66.0  >66.2  >66.45")
for _, r in sub.iterrows():
    flags = ""
    for px in (66.0, 66.2, 66.45):
        flags += "  X " if r["close"] > px else "  . "
    print(f"{r['ts']:%d.%m %H:%M}  {r['high']:6.3f} {r['low']:6.3f} {r['close']:6.3f} |{flags}")

# Hoechste Closes je Tag
print("\nMax High / letzter Close je Tag:")
for day, g in df.groupby(df["ts"].dt.date):
    if day >= pd.Timestamp(lo).date() and day < pd.Timestamp(hi).date():
        print(f"  {day}: high_max={g['high'].max():.3f} close_max={g['close'].max():.3f}")
