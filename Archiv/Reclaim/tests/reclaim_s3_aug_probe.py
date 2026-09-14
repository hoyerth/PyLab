# test/reclaim_s3_aug_probe.py
"""S3-v2 AUG-Probe (Schritt 1, REINE DIAGNOSE - keine Gate-Implementierung).

Verifiziert die geplante Struktur-Sperre (Gate B) + Range-Gate (Gate A) an
den 43 S3-v1-AUG-Signalen, BEVOR Code in store/signals geaendert wird.

Gate-B-Bedingung (SHORT an UPPER-Kante `up`, Freigabe-Text):
    lb = letzter 2-Close-Bruch einer UPPER-Kante UNTERHALB von up.price,
         der an Bar k noch nicht durch Q6-Reaktivierung als Fehlausbruch
         verifiziert wurde (d.h. Level an k im Bruch-Zustand sleeping).
    zulaessig = (lb is None) or (up.birth_bar < lb)
    -> Kante muss VOR dem letzten Bruch darunter geboren sein (echte,
       historische Struktur statt Treppenstufe der Expansionswelle).
    LONG gespiegelt an LOWER-Kante `dn`: Bruch einer LOWER-Kante OBERHALB
    von dn.price.

Gate-A-Bedingung: two_sided (up & dn existieren) UND
    (up.price - dn.price) / dn.price * 100.0 >= MIN_CORRIDOR_SPREAD_PCT.

Die Bruch-Zustaende werden kausal im on_bar-Hook (State nach Bar k) aus
store.transitions rekonstruiert - identisch zum geplanten Live-Tracking
via EdgeLevel.last_sleep_bar.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402
import reclaim_s3_signals as s3  # noqa: E402

START, ENDE = "2026-08-10", "2026-08-28"
MIN_CORRIDOR_SPREAD_PCT: float = 1.0


def last_valid_break_at(
    store: res.EdgeStore, k: int, side: str,
    price_ref: float, below: bool,
) -> Optional[Tuple[int, int, float]]:
    """Letzter gueltiger 2-Close-Bruch (sleep) an Bar k.

    Args:
        store: EdgeStore im Zustand NACH Bar k (on_bar-Hook).
        k: Entscheidungs-Bar.
        side: "UPPER" oder "LOWER".
        price_ref: Preis der gehandelten Kante.
        below: True -> Kante muss UNTER price_ref liegen (SHORT-Fall);
               False -> Kante muss UEBER price_ref liegen (LONG-Fall).
    Returns:
        (sleep_iter, edge_id, price) des letzten gueltigen Bruchs oder None.
    """
    best: Optional[Tuple[int, int, float]] = None
    for lev in store.levels:
        if lev.side != side:
            continue
        if below and not (lev.price < price_ref):
            continue
        if not below and not (lev.price > price_ref):
            continue
        # letzte sleep-Transition dieses Levels mit iter <= k
        sleeps = [t["iter"] for t in store.transitions
                  if t["edge_id"] == lev.edge_id and t["event"] == "sleep"
                  and t["iter"] <= k]
        if not sleeps:
            continue
        last_sleep = max(sleeps)
        # Q6-Reaktivierung nach dem Sleep und vor k? -> Fehlausbruch verifiziert
        rea = any(t["edge_id"] == lev.edge_id and t["event"] == "reactivate"
                  and last_sleep < t["iter"] <= k for t in store.transitions)
        if rea:
            continue
        if best is None or last_sleep > best[0]:
            best = (last_sleep, lev.edge_id, lev.price)
    return best


def main() -> None:
    df = res.load_data(res.DB_PATH, START, ENDE)
    ts_idx = {t: i for i, t in enumerate(df["ts"])}
    # v1-Referenz (ohne Gates - reine Diagnose der Roh-Signale)
    sigs, _store_ref, _blocked = s3.simulate(df, use_gate_a=False,
                                             use_gate_b=False)
    sig_by_bar: Dict[int, object] = {s.bar: s for s in sigs}
    record = set(sig_by_bar.keys())

    store = res.EdgeStore()
    detail: Dict[int, dict] = {}

    def hook(k: int, st: res.EdgeStore) -> None:
        if k not in record:
            return
        s = sig_by_bar[k]
        up, dn = st.corridor(float(df["close"].iloc[k]))
        edge = next((l for l in st.levels if l.edge_id == s.edge_id), None)
        if edge is None:
            return
        # Gate A
        two_sided = up is not None and dn is not None
        spread = ((up.price - dn.price) / dn.price * 100.0
                  if two_sided else float("nan"))
        gate_a = two_sided and spread >= MIN_CORRIDOR_SPREAD_PCT
        # Gate B
        if s.typ == "SHORT":
            lb = last_valid_break_at(st, k, "UPPER", edge.price, below=True)
            gate_b = (lb is None) or (edge.birth_bar < lb[0])
        else:
            lb = last_valid_break_at(st, k, "LOWER", edge.price, below=False)
            gate_b = (lb is None) or (edge.birth_bar < lb[0])
        detail[k] = {
            "s": s, "two_sided": two_sided, "spread": spread,
            "gate_a": gate_a, "gate_b": gate_b,
            "edge": edge, "lb": lb,
        }

    store.build(df, record_bars=set(), on_bar=hook)

    print(f"AUG-Probe: {len(sigs)} S3-v1-Signale | "
          f"Gate A (2-seitig, Spread>={MIN_CORRIDOR_SPREAD_PCT}%) + "
          f"Gate B (Struktur-Sperre)")
    print(f"{'ts':<16} {'Typ':5s} {'R':>7s} | {'Kante':>8s} id= birth"
          f"{'alter':>5s} | {'letzterBruch':>22s} | {'GateA':>5s} {'GateB':>5s} "
          f"{'Entscheid':>8s}")
    hdr_done = False
    n_pass = n_block_a = n_block_b = 0
    sum_pass = sum_block = 0.0
    for k in sorted(detail):
        d = detail[k]
        s = d["s"]
        edge = d["edge"]
        age = k - edge.birth_bar
        lb_txt = "keiner"
        if d["lb"] is not None:
            lb_iter, lb_id, lb_px = d["lb"]
            lb_txt = f"iter {lb_iter} ({df['ts'].iloc[lb_iter]:%d.%m %H:%M} id{lb_id} {lb_px:.3f})"
        ok = d["gate_a"] and d["gate_b"]
        dec = "PASS" if ok else ("block A" if not d["gate_a"] else "block B")
        if ok:
            n_pass += 1
            sum_pass += s.trade.r_mult if s.trade else 0.0
        else:
            sum_block += s.trade.r_mult if s.trade else 0.0
            if not d["gate_a"]:
                n_block_a += 1
            else:
                n_block_b += 1
        r_txt = f"{s.trade.r_mult:+6.2f}" if s.trade else "?"
        if not hdr_done:
            hdr_done = True
        print(f"{s.ts:%d.%m %H:%M} {s.typ:5s} {r_txt:>7s} | "
              f"{edge.price:8.3f} {edge.edge_id:3d} {edge.birth_ts:%d.%m %H:%M} "
              f"{age:5d} | {lb_txt:>22s} | "
              f"{'A' if d['gate_a'] else '-':>5s} {'B' if d['gate_b'] else '-':>5s} "
              f"{dec:>8s}")

    print(f"\nErgebnis: {n_pass}/{len(sigs)} PASS | Summe R PASS {sum_pass:+.2f} | "
          f"blockiert {n_block_a} (A) + {n_block_b} (B) | "
          f"Summe R blockiert {sum_block:+.2f}")

    # Gewinner-Check (wirtschaftlich, +-2 Bars, Kante 66.38-66.39)
    print("\nGewinner-Check (wirtschaftlich, Kante ~66.386/66.388):")
    for s in sigs:
        if not (pd.Timestamp("2026-08-17 18:00") <= s.ts
                <= pd.Timestamp("2026-08-18 03:00")):
            continue
        d = detail.get(s.bar)
        if d is None:
            continue
        ok = d["gate_a"] and d["gate_b"]
        print(f"  {s.ts:%d.%m %H:%M} {s.typ} Kante {s.edge_price:.3f} id={s.edge_id} "
              f"R {s.trade.r_mult:+.2f} -> {'PASS' if ok else 'BLOCKED'}")


if __name__ == "__main__":
    main()
