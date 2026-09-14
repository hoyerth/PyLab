# test/reclaim_s1_smoke.py
"""S1-Smoke-Test: EdgeStore baut auf dem AUG-Fenster ohne Fehler."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

START, ENDE = "2026-08-10", "2026-08-28"

t0 = time.time()
df = res.load_data(res.DB_PATH, START, ENDE)
print(f"candles: {len(df)}  ({time.time() - t0:.1f}s load)")

t0 = time.time()
store = res.EdgeStore().build(df)
dt = time.time() - t0
cnt = store.status_counts()
print(f"build: {dt:.1f}s")
print(f"levels: {len(store.levels)} | cand/act/slp: {cnt}")
print(f"created {store.n_created} | touches {store.n_touch_events} "
      f"| activated {store.n_activated} | reactivated {store.n_reactivated} "
      f"| sleeping {store.n_sleeping}")

last_close = float(df["close"].iloc[-1])
up, dn = store.corridor(last_close)
print(f"last close: {last_close:.3f}")
print(f"corridor up: {up.price:.3f} touches={up.n_touches} n_ind={up.n_independent}" if up else "corridor up: None")
print(f"corridor dn: {dn.price:.3f} touches={dn.n_touches} n_ind={dn.n_independent}" if dn else "corridor dn: None")

# Top-Level nach Score (S2) und nach Touches
act = store.active_levels()
act.sort(key=lambda x: -x.score)
print(f"\nTop aktive Level nach Score ({len(act)}):")
for lev in act[:12]:
    print(f"  id={lev.edge_id:3d} {lev.side:5s} px={lev.price:7.3f} score={lev.score:7.2f} "
          f"touches={lev.n_touches:2d} n_ind={lev.n_independent:2d} "
          f"birth={lev.birth_ts:%d.%m %H:%M} last={lev.last_touch_ts:%d.%m %H:%M}")

act.sort(key=lambda x: -x.n_touches)
print(f"\nTop aktive Level nach Touches ({len(act)}):")
for lev in act[:12]:
    print(f"  id={lev.edge_id:3d} {lev.side:5s} px={lev.price:7.3f} score={lev.score:7.2f} "
          f"touches={lev.n_touches:2d} n_ind={lev.n_independent:2d} "
          f"birth={lev.birth_ts:%d.%m %H:%M} last={lev.last_touch_ts:%d.%m %H:%M}")
