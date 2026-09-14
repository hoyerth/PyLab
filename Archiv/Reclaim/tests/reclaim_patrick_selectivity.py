# test/reclaim_patrick_selectivity.py
"""Patrick-Selektivitäts-Audit fuer Setup B (REIN diagnostisch, post-hoc).

Mentor-Direktive 02.09.: Der Kantenspeicher (historisches Gedaechtnis,
Volumen-Gewichtung, Touch-Zaehlung) ist massgeschneidert fuer Setup B - aber
die Aktivierung ist zu lax im Vergleich zu Patricks realen Regeln:
  * 3-Touch-Regel:  Patrick ruehrt eine Zone vor dem 3. Punkt nicht an.
                     Unser Store aktiviert bereits nach 2 Pivots (oder 1
                     High-Volume-Touch) -> Signale an 1-2-Touch-Kanten.
  * Mehrtages-Zonen: Eine Kante, die erst 8 Bars alt ist, existiert fuer
                     Patrick nicht. Mindestalter 1 Handelstag (96 M15-Bars).
  * Session-Filter:  Keine Trades 22:50-00:10 (Wanduhr), kein Einstieg
                     unmittelbar vor Session-Ende.

Fragen (Mentor):
  1. Was passiert mit S3-Signalen, wenn Kante >= 1 Handelstag (>= 96 Bars)
     alt UND edge_touches >= 3 vor Signalabgabe gefordert wird?
  2. Wie veraendern sich R-Performance und Signalanzahl bei Mindestalter
     >= 48 bzw. >= 96 Bars und n_touches >= 3?
  3. Stundenhitogramm (Wanduhr-Invariante): Wo liegen die Signale ueber den
     Tag, wo die Gewinner/Verlierer? Traegt eine Session-Sperre (22:50-00:10)?

Basis: S3-v1 (Band-Store, keine Gates, Cooldown 8) - aktuelle Referenz.
Alter = s.bar - level.birth_bar (kausal, Bar-Differenz). edge_touches ist der
Touch-Stand ZUM Signalzeitpunkt (im on_bar-Hook erfasst, kein Lookahead).
WICHTIG: post-hoc Filterung respektiert den Cooldown nicht (ein gefiltertes
Signal haette ein Folgesignal frueher erlaubt) - die Filter-Kette ist eine
Selektivitaets-Obergrenze; Inline-Validierung folgt erst bei positivem Befund.

Aufruf:  python test/reclaim_patrick_selectivity.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402
import reclaim_s3_signals as s3  # noqa: E402

WINDOWS: List[Tuple[str, str, str]] = [
    ("AUG", "2026-08-10", "2026-08-28"),
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]

# Session-Sperre (Wanduhr-Invariante: ts-Stunde IST Berlin-Wanduhr, MT5-Epoch)
BLOCK_START_MIN: int = 22 * 60 + 50   # 22:50
BLOCK_END_MIN: int = 0 * 60 + 10      # 00:10 (naechster Tag)


def _stats(sigs: List[s3.S3Signal]) -> Tuple[int, float, int]:
    n = len(sigs)
    decided = [s for s in sigs if s.trade and s.trade.resultat != "NEUTRAL"]
    wins = [s for s in sigs if s.trade and s.trade.resultat == "GEWONNEN"]
    sr = sum(s.trade.r_mult for s in sigs if s.trade)
    wr = (100.0 * len(wins) / len(decided)) if decided else 0.0
    return n, sr, wr


def _minute(s: s3.S3Signal) -> int:
    return s.ts.hour * 60 + s.ts.minute


def _session_ok(s: s3.S3Signal) -> bool:
    mm = _minute(s)
    return not (mm >= BLOCK_START_MIN or mm < BLOCK_END_MIN)


def audit_window(name: str, start: str, ende: str) -> Dict[str, Tuple[int, float, int]]:
    t0 = time.time()
    df = res.load_data(res.DB_PATH, start, ende)
    sigs, store, _ = s3.simulate(df, cooldown_bars=8,
                                 use_gate_a=False, use_gate_b=False)
    levels = {lv.edge_id: lv for lv in store.levels}
    # Alter je Signal (kausal: Geburts-Bar der Kante)
    ages: Dict[int, int] = {}
    for s in sigs:
        lev = levels.get(s.edge_id)
        ages[id(s)] = s.bar - lev.birth_bar if lev is not None else -1

    print(f"\n[{name}] {len(df)} Bars | S3-v1 {len(sigs)} Signale | "
          f"Store {len(store.levels)} Level ({(time.time() - t0):.0f}s sim)")

    # --- 1) Stundenhitogramm (Wanduhr) ---
    print("\n  Stundenhitogramm (Wanduhr; Sperre 22:50-00:10 als Bereich):")
    hour_r: Dict[int, List[float]] = {}
    for s in sigs:
        if s.trade:
            hour_r.setdefault(s.ts.hour, []).append(s.trade.r_mult)
    for h in range(24):
        rl = hour_r.get(h, [])
        if not rl:
            print(f"    {h:02d}:00    0 Sig")
            continue
        sr_h = sum(rl)
        n_h = len(rl)
        blocked = (h * 60) >= BLOCK_START_MIN or (h * 60 + 59) < BLOCK_END_MIN
        mk = "BLOCK" if blocked else "     "
        # Balken nur bei nennenswertem Betrag; Vorzeichen getrennt
        bar = "#" * int(min(35, max(0.0, sr_h * 1.5)))
        neg = "." * int(min(35, max(0.0, -sr_h * 1.5)))
        print(f"    {h:02d}:00  [{mk}] n={n_h:3d} | Summe R {sr_h:+7.2f} | {bar}{neg}")

    # --- 2) Alters- und Touch-Buckets ---
    def _age(s: s3.S3Signal) -> int:
        return ages[id(s)]

    age_b: Dict[str, List[s3.S3Signal]] = {"<24": [], "24-47": [], "48-95": [],
                                           "96-287": [], ">=288": []}
    touch_b: Dict[str, List[s3.S3Signal]] = {"T=1": [], "T=2": [], "T=3": [],
                                             "T=4-5": [], "T>=6": []}
    for s in sigs:
        a = max(0, _age(s))
        age_b["<24" if a < 24 else "24-47" if a < 48 else "48-95"
              if a < 96 else "96-287" if a < 288 else ">=288"].append(s)
        t = s.edge_touches
        touch_b["T=1" if t <= 1 else "T=2" if t == 2 else "T=3"
                if t == 3 else "T=4-5" if t <= 5 else "T>=6"].append(s)
    print("\n  Alter-Buckets (Bars seit Geburt der Kante):")
    for lbl in ("<24", "24-47", "48-95", "96-287", ">=288"):
        n_g, sr_g, wr_g = _stats(age_b[lbl])
        if n_g:
            print(f"    Alter {lbl:>6}: n={n_g:3d} | WR {wr_g:3.0f}% | Summe R {sr_g:+7.2f}")
    print("  Touch-Buckets (edge_touches zum Signalzeitpunkt):")
    for lbl in ("T=1", "T=2", "T=3", "T=4-5", "T>=6"):
        n_g, sr_g, wr_g = _stats(touch_b[lbl])
        if n_g:
            print(f"    {lbl:>6}: n={n_g:3d} | WR {wr_g:3.0f}% | Summe R {sr_g:+7.2f}")

    # --- 3) 2D age x touches ---
    print("\n  2D Alter x Touches (n | Summe R | WR):")
    for rlbl, rf in (("t<3", lambda s: s.edge_touches < 3),
                     ("t>=3", lambda s: s.edge_touches >= 3)):
        cells = []
        for albl in ("age<48", "age48-95", "age>=96"):
            lo, hi = (0, 48) if albl == "age<48" else (48, 96) if albl == "age48-95" else (96, 10**9)
            grp = [s for s in sigs if rf(s) and lo <= max(0, _age(s)) < hi]
            n_g, sr_g, wr_g = _stats(grp)
            cells.append(f"{albl}: n={n_g:3d} R={sr_g:+6.1f} WR={wr_g:3.0f}%")
        print(f"    {rlbl:>5}: " + " | ".join(cells))

    # --- 4) Patrick-Filter-Kette ---
    variants = [
        ("alle (v1-Referenz)", lambda s: True),
        ("Alter>=48", lambda s: max(0, _age(s)) >= 48),
        ("Alter>=96", lambda s: max(0, _age(s)) >= 96),
        ("Touches>=3", lambda s: s.edge_touches >= 3),
        ("T>=3 & Alter>=48", lambda s: s.edge_touches >= 3 and max(0, _age(s)) >= 48),
        ("T>=3 & Alter>=96", lambda s: s.edge_touches >= 3 and max(0, _age(s)) >= 96),
        ("+ Session-Block raus", lambda s: s.edge_touches >= 3
            and max(0, _age(s)) >= 96 and _session_ok(s)),
    ]
    results: Dict[str, Tuple[int, float, int]] = {}
    print("\n  Patrick-Filter-Kette (post-hoc, Cooldown nicht neu verdrahtet):")
    for lbl, f in variants:
        grp = [s for s in sigs if f(s)]
        n_g, sr_g, wr_g = _stats(grp)
        results[lbl] = (n_g, sr_g, wr_g)
        print(f"    {lbl:>22}: n={n_g:4d} | WR {wr_g:3.0f}% | Summe R {sr_g:+8.2f}")
    return results


def main() -> None:
    all_res: Dict[str, Dict[str, Tuple[int, float, int]]] = {}
    for name, start, ende in WINDOWS:
        all_res[name] = audit_window(name, start, ende)
    print("\n" + "=" * 96)
    print("KREUZ-MATRIX (n / Summe R / WR je Fenster)")
    variants = list(all_res["AUG"].keys())
    hdr = "  Variante" + "".join(f" | {w[0]:>22}" for w in WINDOWS) + " | Saldo"
    print(hdr)
    for v in variants:
        row = f"  {v:>22}"
        tot = 0.0
        for w in WINDOWS:
            n_g, sr_g, wr_g = all_res[w[0]][v]
            row += f" | {n_g:4d}/{sr_g:+7.1f}R/{wr_g:2.0f}%"
            tot += sr_g
        print(f"{row} | {tot:+8.1f}R")
    # Referenz-Baseline (Ziel) als Fussnote
    print("\n  Baseline-Ziele: AUG +24.97R (27) | S1 +197.26R (201) | "
          "S2 +99.88R/+110.79R (210/240)")


if __name__ == "__main__":
    main()
