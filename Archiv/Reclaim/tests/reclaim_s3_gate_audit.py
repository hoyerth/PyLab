# test/reclaim_s3_gate_audit.py
"""S3-v2 Gate-Audit (REINE DIAGNOSE - keine Gate-Logik in reclaim_s3_signals.py).

Fragen (Mentor-Review 02.09.):
  Q1) "Frische" in Option A: edge_gap beider Kanten oder nur active-Status?
  Q2) Breakout-Sperre (B): ganze Richtung X Bars ODER nur die gebrochene Kante?
  Q3) Akzeptanzfall 66.28: beide Seiten aktiv am 17./18.08? Korridor-Spread?

Liefert:
  * AUG-Detailzustand an den Gewinner-Bars (S3: 17.08 18:30, 18.08 02:30;
    Baseline-Referenz: 18:45 / 02:15) und an den 5 P5-Loser-Bars.
  * Je Fenster (AUG/S1/S2) Signal-Verteilung: two_sided, Spread-Bucket,
    Frische (gap_up/gap_dn) und Summe-R-Wirkung der Gate-A-Varianten.
  * Gate-B Quantifizierung: "letzter 2-Close-Bruch auf der Signal-Seite
    innerhalb X Bars, ohne Q6-Reaktivierung danach" - blockierte Signale
    und Summe R je X in {24,48,96,192} (Seiten-Ebene und Kanten-Ebene).

Kausalitaet: Korridor- und Transition-Zustaende werden inline im Store-Build
(ueber on_bar-Hook) je Bar erfasst - exakt der Entscheidungszustand von S3.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

X_VALUES: List[int] = [24, 48, 96, 192]


def track_corridor(df: pd.DataFrame) -> Tuple[res.EdgeStore, dict]:
    """Store-Build; je Bar k den Korridor-Zustand (nach Bar k) erfassen."""
    n = len(df)
    up_px = np.full(n, np.nan)
    up_id = np.full(n, -1)
    up_gap = np.full(n, -1)
    up_tch = np.full(n, -1)
    dn_px = np.full(n, np.nan)
    dn_id = np.full(n, -1)
    dn_gap = np.full(n, -1)
    dn_tch = np.full(n, -1)
    close = df["close"].values.astype(float)

    def hook(k: int, store: res.EdgeStore) -> None:
        up, dn = store.corridor(close[k])
        if up is not None:
            up_px[k], up_id[k] = up.price, up.edge_id
            up_gap[k], up_tch[k] = k - up.last_touch_bar, up.n_touches
        if dn is not None:
            dn_px[k], dn_id[k] = dn.price, dn.edge_id
            dn_gap[k], dn_tch[k] = k - dn.last_touch_bar, dn.n_touches

    store = res.EdgeStore().build(df, on_bar=hook)
    return store, {
        "up_px": up_px, "up_id": up_id, "up_gap": up_gap, "up_tch": up_tch,
        "dn_px": dn_px, "dn_id": dn_id, "dn_gap": dn_gap, "dn_tch": dn_tch,
    }


def corridor_state(track: dict, k: int) -> str:
    up_px, up_id, up_gap, up_tch = (track["up_px"][k], track["up_id"][k],
                                    track["up_gap"][k], track["up_tch"][k])
    dn_px, dn_id, dn_gap, dn_tch = (track["dn_px"][k], track["dn_id"][k],
                                    track["dn_gap"][k], track["dn_tch"][k])
    up_s = f"U {up_px:.3f}(id{int(up_id)},T{int(up_tch)},gap{int(up_gap)})" \
        if up_px == up_px else "U ---"
    dn_s = f"D {dn_px:.3f}(id{int(dn_id)},T{int(dn_tch)},gap{int(dn_gap)})" \
        if dn_px == dn_px else "D ---"
    spread = (up_px - dn_px) / dn_px * 100.0 if up_px == up_px and dn_px == dn_px else np.nan
    sp_s = f"{spread:.2f}%" if spread == spread else "n/a"
    both = "2-seitig" if up_px == up_px and dn_px == dn_px else "1-seitig"
    return f"{both} | {up_s} | {dn_s} | Spread {sp_s}"


def recent_break_side(store: res.EdgeStore, k: int, side: str, x: int,
                      ) -> Tuple[bool, Optional[int], Optional[int]]:
    """Letzter 'sleep' eines Levels der Seite `side` in (k-x, k], ohne
    spaetere 'reactivate' dieses Levels vor k -> (gebrochen, sleep_iter,
    edge_id). Seiten-Ebene: Momentum in Richtung des Bruchs."""
    best_iter: Optional[int] = None
    best_id: Optional[int] = None
    for t in store.transitions:
        if t["event"] != "sleep" or t["iter"] > k or t["iter"] <= k - x:
            continue
        lev = next((l for l in store.levels if l.edge_id == t["edge_id"]), None)
        if lev is None or lev.side != side:
            continue
        # Reaktivierung dieses Levels nach dem Sleep vor k?
        rea = [u for u in store.transitions
               if u["edge_id"] == t["edge_id"] and u["event"] == "reactivate"
               and t["iter"] < u["iter"] <= k]
        if rea:
            continue  # Fehlausbruch verifiziert -> nicht als Momentum werten
        if best_iter is None or t["iter"] > best_iter:
            best_iter, best_id = t["iter"], t["edge_id"]
    return (best_iter is not None), best_iter, best_id


def analyze(name: str, start: str, ende: str) -> None:
    t0 = time.time()
    df = res.load_data(res.DB_PATH, start, ende)
    ts_idx = {t: i for i, t in enumerate(df["ts"])}

    # v1-Referenz (ohne Gates - reine Diagnose der Roh-Signale)
    sigs, store, _blocked = s3.simulate(df, use_gate_a=False, use_gate_b=False)
    track_store, track = track_corridor(df)
    sig_map_ts = {s.ts: i for i, s in enumerate(sigs)}

    print(f"\n{'#' * 100}")
    print(f"# {name} ({start} - {ende}, {len(df)} Bars): "
          f"{len(sigs)} S3-Signale | Summe R "
          f"{sum(s.trade.r_mult for s in sigs if s.trade):+.2f}")
    print(f"# Zeit: {time.time() - t0:.1f}s")
    print(f"{'#' * 100}")

    # ---------- Gate-A Verteilungen (Signal-Ebene, Zustand an Bar k) ----------
    rows: List[Dict[str, float]] = []
    for s in sigs:
        k = s.bar
        up_px, dn_px = track["up_px"][k], track["dn_px"][k]
        spread = (up_px - dn_px) / dn_px * 100.0 if (up_px == up_px and dn_px == dn_px) else np.nan
        gap_up = int(track["up_gap"][k]) if track["up_gap"][k] >= 0 else np.nan
        gap_dn = int(track["dn_gap"][k]) if track["dn_gap"][k] >= 0 else np.nan
        rows.append({
            "s": s,
            "two": s.two_sided,
            "spread": spread,
            "gap_up": gap_up,
            "gap_dn": gap_dn,
        })

    def _variant(label: str, pred) -> None:
        sel = [r for r in rows if pred(r)]
        dec = [r["s"] for r in sel if r["s"].trade and r["s"].trade.resultat != "NEUTRAL"]
        w = sum(1 for r in sel if r["s"].trade and r["s"].trade.resultat == "GEWONNEN")
        sr = sum(r["s"].trade.r_mult for r in sel if r["s"].trade)
        wr = 100.0 * w / len(dec) if dec else 0.0
        print(f"  Gate-A [{label:>34}]: n={len(sel):4d} | WR {wr:3.0f}% | Summe R {sr:+8.2f}")

    print("\n[Gate A - Varianten (Summe-R-Wirkung)]")
    _variant("alle Signale (v1)", lambda r: True)
    _variant("A0 two_sided", lambda r: r["two"])
    for sp_thr in (0.5, 1.0, 1.5):
        _variant(f"A1 two_sided & spread>={sp_thr}%", lambda r, t=sp_thr:
                 r["two"] and r["spread"] == r["spread"] and r["spread"] >= t)
        for gap in (96, 288):
            _variant(f"A2 two_sided & spread>={sp_thr}% & gap<{gap} bd.",
                     lambda r, t=sp_thr, g=gap: r["two"]
                     and r["spread"] == r["spread"] and r["spread"] >= t
                     and r["gap_up"] == r["gap_up"] and r["gap_up"] < g
                     and r["gap_dn"] == r["gap_dn"] and r["gap_dn"] < g)

    # ---------- Gate B Quantifizierung ----------
    print("\n[Gate B - 2-Close-Bruch auf Signal-Seite innerhalb X Bars, ohne "
          "Q6-Reaktivierung danach]")
    print(f"  {'X':>5} | {'blockiert':>9} {'SummeR block.':>13} | "
          f"{'verbleibend':>11} {'SummeR verbl.':>13} | {'SummeR gesamt':>14}")
    side_of = {"SHORT": "UPPER", "LONG": "LOWER"}
    for x in X_VALUES:
        blocked_r = 0.0
        blocked_n = 0
        for r in rows:
            s = r["s"]
            brk, it, eid = recent_break_side(store, s.bar, side_of[s.typ], x)
            if brk:
                blocked_n += 1
                blocked_r += s.trade.r_mult if s.trade else 0.0
        rem_r = sum(r["s"].trade.r_mult for r in rows if r["s"].trade) - blocked_r
        tot_r = sum(r["s"].trade.r_mult for r in rows if r["s"].trade)
        print(f"  {x:5d} | {blocked_n:9d} {blocked_r:+13.2f} | "
              f"{len(rows) - blocked_n:11d} {rem_r:+13.2f} | {tot_r:+14.2f}")

    # Kanten-Ebene: gebrochene Kante = genau die gehandelte?
    edge_hit = {x: 0 for x in X_VALUES}
    for r in rows:
        s = r["s"]
        for x in X_VALUES:
            brk, it, eid = recent_break_side(store, s.bar, side_of[s.typ], x)
            if brk and eid == s.edge_id:
                edge_hit[x] += 1
    print(f"  davon auf der GENAU gehandelten Kante (Kanten-Ebene): "
          f"{ {x: edge_hit[x] for x in X_VALUES} }")

    # ---------- AUG-Detail (nur wenn Fenster AUG) ----------
    if name == "AUG":
        print("\n[AUG-Detail: Gewinner-/P5-Bars]")
        stamps = {
            "S3-Winner 17.08 18:30": "2026-08-17 18:30",
            "S3-Winner 18.08 02:30": "2026-08-18 02:30",
            "Base-Winner 17.08 18:45": "2026-08-17 18:45",
            "Base-Winner 18.08 02:15": "2026-08-18 02:15",
            "P5-Loser 14.08 08:45": "2026-08-14 08:45",
            "P5-Loser 14.08 11:45": "2026-08-14 11:45",
            "P5-Loser 14.08 14:45": "2026-08-14 14:45",
            "P5-Loser 17.08 03:45": "2026-08-17 03:45",
            "P5-Loser 17.08 07:30": "2026-08-17 07:30",
        }
        for label, ts_s in stamps.items():
            ts = pd.Timestamp(ts_s)
            if ts not in ts_idx:
                continue
            k = ts_idx[ts]
            sig_i = sig_map_ts.get(ts)
            sig_txt = ""
            if sig_i is not None:
                s = sigs[sig_i]
                sig_txt = (f" | S3-Sig: {s.typ} {s.trade.resultat if s.trade else '?'} "
                           f"{s.trade.r_mult:+.2f}R" if s.trade else "")
            print(f"  {label:24s}: {corridor_state(track, k)}{sig_txt}")


def main() -> None:
    for name, start, ende in WINDOWS:
        analyze(name, start, ende)


if __name__ == "__main__":
    main()
