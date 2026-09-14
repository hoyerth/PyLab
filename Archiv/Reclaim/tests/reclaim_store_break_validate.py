# test/reclaim_store_break_validate.py
"""Store-Reparatur-Validierung (b) + (d) - rein diagnostisch.

Nach dem Fix (Transition-Gate + Chronologie + Q6-Guard) wird gemessen:
  (b) Bruch-Klassifikation: je sleep-Event die Richtung (up/dn) und ob sie
      gegen die Seed-Seite laeuft (Flip = Rollen-Tausch-Bruch, alt nie erkannt).
      Zusaetzlich Same-Iter-Hazard-Zaehler (reactivate mit last_sleep_bar >= j
      sollte 0 sein).
  (d) Delta-Lauf S3 auf dem reparierten Fundament: v1/v2-Matrix je Fenster.

Aufruf:  python test/reclaim_store_break_validate.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402
import reclaim_s3_signals as s3  # noqa: E402

WINDOWS: List[Tuple[str, str, str]] = [
    ("AUG", "2026-08-10", "2026-08-28"),
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]


def classify_breaks(name: str, start: str, ende: str) -> None:
    t0 = time.time()
    df = res.load_data(res.DB_PATH, start, ende)
    close = df["close"].values.astype(float)

    # on_bar-Hook: nichts (nur reiner Store-Build); Breaks in transitions
    store = res.EdgeStore().build(df)
    levels = {lv.edge_id: lv for lv in store.levels}

    cnt: Counter = Counter()
    flips: Counter = Counter()
    # Band-Klassifikation (muss der _check_break-Logik entsprechen: tol=0.15)
    tol = float(res.EDGE_TOL)
    same_iter_react = 0
    for t in store.transitions:
        if t["event"] != "sleep":
            continue
        k = int(t["iter"])
        lev = levels[int(t["edge_id"])]
        p = float(t["price"])
        if k < 2:
            cnt["kein_ref (k<2)"] += 1
            continue
        c_b = float(close[k - 2]); c_p = float(close[k - 1]); c_n = float(close[k])
        up = c_p > p + tol and c_n > p + tol and c_b <= p + tol
        dn = c_p < p - tol and c_n < p - tol and c_b >= p - tol
        if up and dn:  # theoretisch unmoeglich, aber absichern
            cnt["up_und_dn"] += 1
        elif up:
            cnt["up_break"] += 1
            if lev.side == "LOWER":
                flips["LOWER + up (als Resistance gebrochen)"] += 1
        elif dn:
            cnt["dn_break"] += 1
            if lev.side == "UPPER":
                flips["UPPER + dn (als Support gebrochen)"] += 1
        else:
            cnt["keine_richtung"] += 1

    # Q6-Guard: reactivate muss einen strikt FRUEHEREN sleep referenzieren
    # (sequentiell aus der Transitions-Historie, nicht Endzustand last_sleep_bar)
    last_sleep_iter: dict = {}  # edge_id -> letzter sleep-iter VOR diesem Event
    same_iter_react = 0
    for t in store.transitions:
        eid = int(t["edge_id"])
        if t["event"] == "sleep":
            last_sleep_iter[eid] = int(t["iter"])
        elif t["event"] == "reactivate":
            j = int(t["touch_bar"])
            s = last_sleep_iter.get(eid, -10**9)
            if s >= j:
                same_iter_react += 1

    print(f"\n[{name}] Store-Breaks: {sum(cnt.values())} sleep-Events "
          f"({time.time() - t0:.1f}s)")
    for c, n in cnt.most_common():
        print(f"    {c:22s}: {n:5d}")
    print(f"    Rollen-Tausch-Brueche (NEU erkannt):")
    for c, n in flips.most_common():
        print(f"      {c:38s}: {n:5d}")
    print(f"    Q6-Guard-Verletzungen (reactivate last_sleep>=j): {same_iter_react}")
    print(f"    Store: {len(store.levels)} Level | created {store.n_created} | "
          f"reactivated {store.n_reactivated} | sleeping {store.n_sleeping}")


def matrix_run(name: str, start: str, ende: str) -> None:
    df = res.load_data(res.DB_PATH, start, ende)
    print(f"\n[{name} | {len(df)} Bars] S3-Delta-Matrix (reparierter Store):")
    for label, ga, gb in (("v1 (keine Gates)", False, False),
                          ("nur B (Struktur)", False, True),
                          ("nur A (Spread)", True, False),
                          ("A+B", True, True)):
        sigs, store, blocked = s3.simulate(df, use_gate_a=ga, use_gate_b=gb)
        n = len(sigs)
        w = sum(1 for s in sigs if s.trade and s.trade.resultat == "GEWONNEN")
        r = sum(s.trade.r_mult for s in sigs if s.trade)
        b_n = len(blocked)
        b_r = sum(s.trade.r_mult for _, s in blocked if s.trade)
        wr = 100.0 * w / n if n else 0.0
        print(f"    {label:18s}: Sig {n:4d} | WR {wr:3.0f}% | Summe R {r:+8.2f} | "
              f"blockiert {b_n:4d} (entg. R {b_r:+8.2f})")


def main() -> None:
    t_all = time.time()
    for name, start, ende in WINDOWS:
        classify_breaks(name, start, ende)
    for name, start, ende in WINDOWS:
        matrix_run(name, start, ende)
    print(f"\nGesamtzeit: {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
