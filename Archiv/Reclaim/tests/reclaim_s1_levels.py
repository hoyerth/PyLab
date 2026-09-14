# test/reclaim_s1_levels.py
"""Listet alle Level des AUG-Stores sortiert nach Preis (Diagnose)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

df = res.load_data(res.DB_PATH, "2026-08-10", "2026-08-28")
store = res.EdgeStore().build(df)

levs = sorted(store.levels, key=lambda x: x.price)
print(f"Levels: {len(levs)} | erzeugt {store.n_created} | Touches {store.n_touch_events}")
print(f"{'id':>3} {'Side':5s} {'Status':9s} {'Px':>7} {'nT':>2} {'nInd':>3}  birth                  last")
for lev in levs:
    b = lev.birth_ts.strftime("%d.%m %H:%M") if lev.birth_ts else "?"
    lt = lev.last_touch_ts.strftime("%d.%m %H:%M") if lev.last_touch_ts else "?"
    types = {}
    for t in lev.touches:
        types[t.touch_type] = types.get(t.touch_type, 0) + 1
    print(f"{lev.edge_id:>3} {lev.side:5s} {lev.status:9s} {lev.price:7.3f} "
          f"{lev.n_touches:2d} {lev.n_independent:2d}  {b}  {lt}  {types}")
