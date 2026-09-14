# test/reclaim_s1_windows.py
"""S1-Statistik ueber die 3 Fenster (AUG/S1/S2) + Performance-Check."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

WINDOWS = [
    ("AUG", "2026-08-10", "2026-08-28"),
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]

for name, start, ende in WINDOWS:
    df = res.load_data(res.DB_PATH, start, ende)
    t0 = time.time()
    store = res.EdgeStore().build(df)
    dt = time.time() - t0
    cnt = store.status_counts()
    n_hi = sum(1 for lev in store.levels if lev.side == "UPPER")
    active_hi = sum(1 for lev in store.active_levels() if lev.side == "UPPER")
    # Verteilung der Touches (etabliert = >=3 Touches)
    multi = sum(1 for lev in store.levels if lev.n_touches >= 3)
    print(f"{name:4s} | candles {len(df):6d} | pivots ~ | levels {len(store.levels):4d} "
          f"(UPPER {n_hi}) | cand/act/slp {cnt['candidate']}/{cnt['active']}/{cnt['sleeping']} "
          f"| active-U {active_hi} | >=3T {multi} | react {store.n_reactivated} "
          f"| build {dt:5.1f}s")
