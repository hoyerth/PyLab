# test/reclaim_tol_sweep_diag.py
"""Sweep-Diagnose Design-Frage (i): Relative Bruch-Toleranz (REIN diagnostisch).

Mentor-Arretierung 02.09.: Matching-Band (EDGE_TOL, statisch) vs. Bruch-Band
muessen entkoppelt werden. Dieses Skript testet das dynamische Bruch-Band
    tol_k = a * range_ref_k          (a = Multiplikator)
    range_ref = (high - low).rolling(200, min_periods=20).mean().shift(1)
KONZEPTUELL OHNE reclaim_edge_store.py zu modifizieren: Eine runtime-Subklasse
ueberschreibt NUR `_check_break` + `build` (Range-Referenz-Vorberechnung);
`res.EdgeStore` wird im Modul ersetzt, damit `s3.simulate` die Subklasse nutzt.

Sweep:  a in {0.0, 0.4, 0.65, 1.0}
  * a = 0.0 -> heutiges ABSOLUTES Band (tol = EDGE_TOL = 0.15 konstant) als
    Sanity-Check: muss die Band-Referenz exakt reproduzieren
    (AUG +30.65R/32, S1 -52.96R/454, S2 -50.19R/643).
  * a > 0.0 -> dynamisches Band tol_k = a * range_ref_k (NaN-Fallback edge_tol).

Je a und Fenster: S3-v1 (keine Gates, Cooldown 8) -> Sig/Summe R/WR +
Store-Diagnose (n_sleeping, n_reactivated) als Bruch-Haeufigkeits-Indikator.

Aufruf:  python test/reclaim_tol_sweep_diag.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

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
MULTS: List[float] = [0.0, 0.4, 0.65, 1.0]
RANGE_WINDOW: int = 200
RANGE_MINP: int = 20


def make_range_tol_store(tol_mult: float):
    """Subklasse mit dynamischem Bruch-Band (nur _check_break ueberschrieben).

    tol_mult <= 0 : absolutes Band wie aktuell (tol = edge_tol konstant).
    tol_mult >  0 : tol_k = tol_mult * range_ref_k, kausal (shift 1).
    """
    class _RangeTolStore(res.EdgeStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.tol_mult = float(tol_mult)
            self._range_ref: Optional[np.ndarray] = None

        def build(self, df: pd.DataFrame,
                  record_bars: Optional[set] = None,
                  on_bar=None) -> "res.EdgeStore":
            rng = df["high"].to_numpy(dtype=float) - df["low"].to_numpy(dtype=float)
            self._range_ref = (
                pd.Series(rng)
                .rolling(RANGE_WINDOW, min_periods=RANGE_MINP)
                .mean()
                .shift(1)
                .to_numpy(dtype=float)
            )
            return super().build(df, record_bars=record_bars, on_bar=on_bar)

        def _check_break(self, k: int) -> None:
            """Kopie der Band-Bruch-Logik mit dynamischer Toleranz."""
            if k < 2 or not self._watch or self.df is None:
                return
            c_before = float(self.df["close"].iloc[k - 2])
            c_prev = float(self.df["close"].iloc[k - 1])
            c_now = float(self.df["close"].iloc[k])
            if self.tol_mult <= 0:
                tol = float(self.edge_tol)
            else:
                ref = float(self._range_ref[k]) if self._range_ref is not None else np.nan
                tol = self.tol_mult * ref if np.isfinite(ref) else float(self.edge_tol)
            for lev in list(self._watch):
                p = float(lev.price)
                up_break = (c_before <= p + tol and c_prev > p + tol
                            and c_now > p + tol)
                dn_break = (c_before >= p - tol and c_prev < p - tol
                            and c_now < p - tol)
                if up_break or dn_break:
                    self._set_sleeping(lev, k)

    return _RangeTolStore


def run_sweep() -> None:
    refs = {  # Band-Referenz (v1, Cooldown 8) fuer Sanity-Check a=0
        "AUG": (32, 30.65),
        "S1": (454, -52.96),
        "S2": (643, -50.19),
    }
    print("Sweep: relative Bruch-Toleranz tol_k = a * roll.mean Range (200/shift1)")
    print(f"       a=0 -> absolutes Band (EDGE_TOL {res.EDGE_TOL}) = Sanity-Check\n")
    for name, start, ende in WINDOWS:
        t0 = time.time()
        df = res.load_data(res.DB_PATH, start, ende)
        print(f"[{name}] {len(df)} Bars (Ladezeit {time.time() - t0:.1f}s)")
        print(f"  {'a':>5} | {'Sig':>5} | {'WR':>4} | {'Summe R':>9} | "
              f"{'sleeps':>7} | {'reactiv':>7} | Sanity-Status")
        for a in MULTS:
            cls = make_range_tol_store(a)
            res.EdgeStore = cls  # s3.simulate nutzt die Subklasse (nur Diagnose)
            t1 = time.time()
            sigs, store, blocked = s3.simulate(
                df, cooldown_bars=8, use_gate_a=False, use_gate_b=False)
            n = len(sigs)
            wins = sum(1 for s in sigs if s.trade and s.trade.resultat == "GEWONNEN")
            decided = sum(1 for s in sigs if s.trade and s.trade.resultat != "NEUTRAL")
            wr = 100.0 * wins / decided if decided else 0.0
            sr = sum(s.trade.r_mult for s in sigs if s.trade)
            sanity = ""
            if a == 0.0:
                ref_n, ref_r = refs[name]
                ok_n = n == ref_n
                ok_r = abs(sr - ref_r) < 0.01
                sanity = ("OK" if ok_n and ok_r
                          else f"*** ABWEICHUNG (Ref {ref_n}/{ref_r:+.2f}R) ***")
            print(f"  {a:5.2f} | {n:5d} | {wr:3.0f}% | {sr:+9.2f} | "
                  f"{store.n_sleeping:7d} | {store.n_reactivated:7d} | {sanity}"
                  f"  ({time.time() - t1:.1f}s)")
        print()
    # res.EdgeStore bleibt am Prozessende in der letzten Subklasse - unkritisch,
    # da dieses Skript ein eigenstaendiger Diagnose-Prozess ist.


if __name__ == "__main__":
    run_sweep()
