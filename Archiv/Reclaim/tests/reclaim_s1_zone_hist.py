# test/reclaim_s1_zone_hist.py
"""Touch-Historie der 66.2-66.6-Zone (kausaler Stand 18.08 03:00)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

df = res.load_data(res.DB_PATH, "2026-08-10", "2026-08-28")
cut_ts = pd.Timestamp("2026-08-18 03:00")
k_cut = int(df.index[df["ts"] <= cut_ts][-1])
store = res.EdgeStore().build(df.iloc[: k_cut + 1].copy())

for lev in store.levels:
    if 66.0 <= lev.price <= 66.8:
        print(f"\nLevel id={lev.edge_id} {lev.side} px={lev.price:.3f} status={lev.status} "
              f"(T={lev.n_touches})")
        for t in lev.touches:
            print(f"   {t.ts:%d.%m %H:%M} {t.kind} @ {t.price:.3f} vol={t.tick_volume:6.0f} "
                  f"rel={t.rel_volume:4.2f} type={t.touch_type}")
