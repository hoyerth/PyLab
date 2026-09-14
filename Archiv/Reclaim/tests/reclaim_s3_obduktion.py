# test/reclaim_s3_obduktion.py
"""S3-v1 Trade-Obduktion + Resonanz-Voranalyse (REINE DIAGNOSE - kein Fix).

Fragen (Mentor-Review 02.09.):
  Q1) Verlust-Charakteristik S1/S2: Laufen die Fehlschläge sofort nach Entry
      ungebremst in den SL (klassischer Trend-Run) oder pendeln sie erst um
      den Entry (TP1-Touch vor SL)?
  Q3) Resonanz-Definition (first cut): Wie frisch ist der letzte Touch der
      GEGENUEBERLIEGENDEN Korridor-Kante bei Signal-Bar k (opp_gap)?
      SHORT an up -> opp = dn; LONG an dn -> opp = up. Welches N trennt?

Zusaetzlich (Plan-Schritt 1):
  * Trend-Staerke-Proxi: laufende Serie aufeinanderfolgender Closes jenseits
    des Rolling-VP-POC an der Signal-Bar (gegen die Fade-Richtung).
  * Aufloesungs-Shape je Verlierer: (SL,SL) direkt | (TP1,SL) oszilliert |
    (TP1,ENDE)/(ENDE,ENDE) = Fenster-Ende-Artefakt.

Kausalitaet: identische Store-Zustaende wie S3 (on_bar-Hook im Build).
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402
import reclaim_s3_signals as s3  # noqa: E402

WINDOWS: List[Tuple[str, str, str]] = [
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]

GAP_BUCKETS: List[Tuple[str, int]] = [
    ("opp_gap<12", 12), ("12-23", 24), ("24-47", 48), ("48-95", 96),
    ("96-191", 192), ("192-383", 384), (">=384", -1),
]


def _gap_bucket(gap: int) -> str:
    for name, hi in GAP_BUCKETS:
        if hi < 0:
            return name
        if gap < hi:
            return name
    return ">=384"


def track_corridor(df: pd.DataFrame) -> dict:
    """Store-Build; je Bar k up/dn-Korridor (gap/id/praesenz) erfassen."""
    n = len(df)
    up_id = np.full(n, -1)
    up_gap = np.full(n, -1)
    dn_id = np.full(n, -1)
    dn_gap = np.full(n, -1)
    close = df["close"].values.astype(float)

    def hook(k: int, store: res.EdgeStore) -> None:
        up, dn = store.corridor(close[k])
        if up is not None:
            up_id[k], up_gap[k] = up.edge_id, k - up.last_touch_bar
        if dn is not None:
            dn_id[k], dn_gap[k] = dn.edge_id, k - dn.last_touch_bar

    res.EdgeStore().build(df, on_bar=hook)
    return {"up_id": up_id, "up_gap": up_gap, "dn_id": dn_id, "dn_gap": dn_gap}


def poc_streak(cl: np.ndarray, k: int, poc: float, typ: str) -> int:
    """Laufende Serie von Closes jenseits des POC an Bar k (Fade-Gegenrichtung).

    SHORT (Fade nach unten): Closes > poc = bullischer Drang gegen den Fade.
    LONG  (Fade nach oben):  Closes < poc = baerischer Drang gegen den Fade.
    """
    n = 0
    j = k
    while j >= 0:
        if (typ == "SHORT" and cl[j] > poc) or (typ == "LONG" and cl[j] < poc):
            n += 1
            j -= 1
        else:
            break
        if n > 500:
            break
    return n


def _shape(s: s3.S3Signal) -> str:
    g1, g2 = s.trade.grund1, s.trade.grund2
    if s.trade.resultat == "GEWONNEN":
        return "Gewinn"
    if g1 == "SL":
        return "SL-SL (direkt, kein TP1)"
    if g1 == "TP1" and g2 == "SL":
        return "TP1->SL (oszilliert)"
    if g1 == "TP1" and g2 == "ENDE":
        return "TP1->ENDE (Fenster-Ende)"
    if g1 == "ENDE":
        return "ENDE-ENDE (Fenster-Ende)"
    return f"{g1}-{g2}"


def analyze(name: str, start: str, ende: str) -> None:
    t0 = time.time()
    df = res.load_data(res.DB_PATH, start, ende)
    cl = df["close"].values.astype(float)
    print(f"\n{'#' * 100}\n# {name} ({start} - {ende}, {len(df)} Bars)"
          f"\n{'#' * 100}")

    sigs, store, _blk = s3.simulate(df, use_gate_a=False, use_gate_b=False)
    track = track_corridor(df)
    sigs = [s for s in sigs if s.trade is not None]
    sum_r = sum(s.trade.r_mult for s in sigs)
    wins = [s for s in sigs if s.trade.resultat == "GEWONNEN"]
    print(f"v1-Signale {len(sigs)} | WR {100.0 * len(wins) / len(sigs):.0f}% | "
          f"Summe R {sum_r:+.2f}  ({time.time() - t0:.1f}s)")

    # ---------- Q1: Verlust-Shapes ----------
    print("\n[Q1 Verlust-Aufloesung (Shape je Verlierer)]")
    shapes: Dict[str, List[s3.S3Signal]] = {}
    for s in sigs:
        if s.trade.resultat == "VERLOREN":
            shapes.setdefault(_shape(s), []).append(s)
    tot_loss = 0
    for sh, g in sorted(shapes.items(), key=lambda kv: -len(kv[1])):
        r = sum(x.trade.r_mult for x in g)
        tot_loss += r
        # Bars bis SL: SL-SL -> exit1_bar (= exit2_bar); TP1->SL -> exit2_bar
        sl_bars = [((x.trade.exit1_bar if x.trade.grund1 == "SL"
                     else x.trade.exit2_bar) - x.einstieg_bar)
                   for x in g if "SL" in (x.trade.grund1, x.trade.grund2)]
        sl_txt = (f" | Bars->SL avg {np.mean(sl_bars):5.1f} "
                  f"med {np.median(sl_bars):4.0f}" if sl_bars else "")
        print(f"  {sh:34s}: n={len(g):4d} | Summe R {r:+9.2f} | avg "
              f"{r / len(g):+5.2f}R{sl_txt}")
    print(f"  Verlierer gesamt: {sum(len(v) for v in shapes.values())} | "
          f"Summe R {tot_loss:+.2f}")

    # TP1-Touch vor SL unter allen Verlierern
    losers = [s for s in sigs if s.trade.resultat == "VERLOREN"]
    tp1_first = [s for s in losers if s.trade.grund1 == "TP1"]
    print(f"  davon mit TP1-Teilrealisierung vor SL: {len(tp1_first)} "
          f"({100.0 * len(tp1_first) / len(losers):.0f}% aller Verlierer)")

    # ---------- Trend-Staerke-Proxi (POC-Streak) ----------
    print("\n[Trend-Proxi: laufende POC-Gegen-Serie an Signal-Bar]")
    rows: List[Tuple[str, s3.S3Signal]] = []
    for s in sigs:
        rows.append((_streak_bucket(poc_streak(cl, s.bar, s.poc, s.typ)), s))

    def _tab(sel: List[s3.S3Signal], label: str) -> None:
        w = sum(1 for x in sel if x.trade.resultat == "GEWONNEN")
        r = sum(x.trade.r_mult for x in sel)
        print(f"  {label:18s}: n={len(sel):4d} | WR {100.0 * w / len(sel):3.0f}%"
              f" | Summe R {r:+8.2f}")

    for b in ["Streak=1", "2-3", "4-7", "8-15", "16-31", ">=32"]:
        sel = [s for lb, s in rows if lb == b]
        _tab(sel, b)

    # ---------- Q3: Resonanz first cut (opp_gap) ----------
    print("\n[Q3 Resonanz-Voranalyse: Frische der GEGENUEBERLIEGENDEN Kante]")
    print("  (nur 2-seitige Signale; SHORT->dn_gap, LONG->up_gap an Bar k)")
    opp_gap_of: Dict[int, int] = {}
    mismatch = 0
    for s in sigs:
        k = s.bar
        if s.typ == "SHORT":
            opp_gap = int(track["dn_gap"][k])
            traded_ok = (int(track["up_id"][k]) == s.edge_id)
        else:
            opp_gap = int(track["up_gap"][k])
            traded_ok = (int(track["dn_id"][k]) == s.edge_id)
        if not traded_ok:
            mismatch += 1
        if opp_gap >= 0:
            opp_gap_of[s.bar] = opp_gap  # 2-seitig (je Bar eindeutig)
    if mismatch:
        print(f"  ACHTUNG: {mismatch} Signale mit Korridor-Abweichung (track vs. Signal)")

    opp_rows: List[Tuple[str, s3.S3Signal]] = [
        (_gap_bucket(opp_gap_of[s.bar]), s) for s in sigs if s.bar in opp_gap_of
    ]

    for b in [x[0] for x in GAP_BUCKETS]:
        sel = [s for lb, s in opp_rows if lb == b]
        if sel:
            _tab(sel, b)

    # Summe-R-Wirkung eines Resonanz-Schnitts (nur 2-seitige Signale)
    print("\n  Resonanz-Schnitt (Summe R je opp_gap-Schwelle N):")
    base2 = sum(s.trade.r_mult for s in sigs if s.bar in opp_gap_of)
    n_two = sum(1 for s in sigs if s.bar in opp_gap_of)
    for n in (12, 24, 48, 96, 192):
        keep = [s for s in sigs if s.bar in opp_gap_of and opp_gap_of[s.bar] < n]
        block = [s for s in sigs if s.bar in opp_gap_of and opp_gap_of[s.bar] >= n]
        keep_r = sum(s.trade.r_mult for s in keep)
        block_r = sum(s.trade.r_mult for s in block)
        w = sum(1 for s in keep if s.trade.resultat == "GEWONNEN")
        print(f"    opp_gap<{n:3d}: behalten n={len(keep):4d} | "
              f"WR {100.0 * w / len(keep):3.0f}% | Summe R {keep_r:+8.2f} | "
              f"blockiert n={len(block):4d} | entgangene R {block_r:+8.2f}")
    print(f"    (v1 2-seitig gesamt: {n_two} Signale | Summe R {base2:+.2f} | "
          f"1-seitig ausgeklammert: {len(sigs) - n_two})")
    print(f"  Zeit gesamt: {time.time() - t0:.1f}s")


def _streak_bucket(n: int) -> str:
    if n == 1:
        return "Streak=1"
    if n <= 3:
        return "2-3"
    if n <= 7:
        return "4-7"
    if n <= 15:
        return "8-15"
    if n <= 31:
        return "16-31"
    return ">=32"


def main() -> None:
    for name, start, ende in WINDOWS:
        analyze(name, start, ende)


if __name__ == "__main__":
    main()
