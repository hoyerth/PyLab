"""Aggregiert SYMBOL M15 Kennzahlen aus den stats_trades-Reports (finale Laeufe)."""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent
SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "Cocoa"
SL = {"Coffee": {"AUG": 0.005363, "S1": 0.004481, "S2": 0.004502},
      "Cocoa": {"AUG": 0.006718, "S1": 0.007005, "S2": 0.006133},
      "Brent": {"AUG": 0.002968, "S1": 0.004536, "S2": 0.002190}}[SYMBOL]
BARS = {"Coffee": {"AUG": 490, "S1": 4852, "S2": 7893},
        "Cocoa": {"AUG": 490, "S1": 4852, "S2": 7893},
        "Brent": {"AUG": 1200, "S1": 12351, "S2": 20087}}[SYMBOL]
PH = {"Coffee": {"AUG": 6, "S1": 54, "S2": 37},
      "Cocoa": {"AUG": 4, "S1": 54, "S2": 28},
      "Brent": {"AUG": 11, "S1": 134, "S2": 54}}[SYMBOL]
PHHB = {"Coffee": {"AUG": 2, "S1": 17, "S2": 18},
        "Cocoa": {"AUG": 2, "S1": 24, "S2": 20},
        "Brent": {"AUG": 3, "S1": 42, "S2": 28}}[SYMBOL]


def read_trades(fenster: str) -> list:
    rows = []
    for l in (TEST / f"stats_trades_{SYMBOL}_{fenster}.txt").read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in l.split("|")]
        if len(parts) != 10:
            continue
        try:
            r = float(parts[8].rstrip("R"))
            entry = float(parts[6])
            direction = parts[5]
        except ValueError:
            continue
        rows.append({"r": r, "entry": entry, "dir": direction})
    return rows


def stats(fenster: str, rows: list) -> dict:
    rs = [t["r"] for t in rows]
    w = [x for x in rs if x > 0]
    l = [x for x in rs if x < 0]
    n = len(rs)
    gw, gl = sum(w), -sum(l)
    pf = gw / gl if gl else float("inf")
    sl = SL[fenster]
    return {
        "fenster": fenster, "bars": BARS[fenster], "ph": PH[fenster],
        "phhb": PHHB[fenster], "n": n,
        "long": sum(1 for t in rows if t["dir"] == "LONG"),
        "short": sum(1 for t in rows if t["dir"] == "SHORT"),
        "wr": len(w) / n * 100.0,
        "sumr": sum(rs), "pf": pf,
        "avgw": (sum(w) / len(w)) if w else 0.0,
        "avgl": (sum(l) / len(l)) if l else 0.0,
        "kurs": sum(rs) * sl / n * 100.0,
    }


all_rows = {}
for f in ("AUG", "S1", "S2"):
    all_rows[f] = read_trades(f)
    s = stats(f, all_rows[f])
    print(f"{s['fenster']}: Bars {s['bars']} Ph {s['ph']}({s['phhb']}) | n={s['n']} "
          f"L {s['long']}/S {s['short']} | WR={s['wr']:.1f}% SumR={s['sumr']:+.2f} "
          f"PF={s['pf']:.2f} AvgW={s['avgw']:+.2f} AvgL={s['avgl']:+.2f} Kurs%/Tr={s['kurs']:+.3f}")

rs = [t["r"] for t in all_rows["S1"] + all_rows["S2"]]
w = [x for x in rs if x > 0]
l = [x for x in rs if x < 0]
gw, gl = sum(w), -sum(l)
pf = gw / gl if gl else float("inf")
kurs = (sum(t["r"] for t in all_rows["S1"]) * SL["S1"]
        + sum(t["r"] for t in all_rows["S2"]) * SL["S2"]) / len(rs) * 100.0
print(f"S1+S2: n={len(rs)} WR={len(w)/len(rs)*100:.1f}% SumR={sum(rs):+.2f} PF={pf:.2f} "
      f"AvgW={sum(w)/len(w):+.2f} AvgL={sum(l)/len(l):+.2f} Kurs%/Tr(gew)={kurs:+.3f}")
