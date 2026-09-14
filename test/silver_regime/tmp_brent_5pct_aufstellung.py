"""Aufstellung BRENT M15 mit 5%-Einsatz auf 10.000 USD Start (je Fenster).

Zwei Varianten:
  A) FIX:  5% von 10.000 = 500 USD Risiko je Trade (kein Zinseszins).
  B) COMP: 5% des laufenden Equities je Trade (Zinseszins, Money-Management).

Quelle: reproduzierte Trade-Logs test/stats_trades_Brent_{AUG,S1,S2}.txt.
"""
from __future__ import annotations

from pathlib import Path

TEST = Path(__file__).resolve().parent
START = 10_000.0
PCT = 0.05
FILES = {"AUG": "stats_trades_Brent_AUG.txt",
         "S1": "stats_trades_Brent_S1.txt",
         "S2": "stats_trades_Brent_S2.txt"}


def parse(fname: str) -> list[float]:
    out = []
    path = TEST / fname
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line or "Trade_Nr" in line or "----" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 9:
            continue
        try:
            int(parts[0])
            out.append(float(parts[8]))
        except ValueError:
            continue
    return out


def streak(rs: list[float]) -> tuple[int, float]:
    best_len = best_sum = cur_len = cur_sum = 0
    for r in rs:
        if r < 0:
            cur_len += 1
            cur_sum += r
            if cur_len > best_len or (cur_len == best_len and cur_sum < best_sum):
                best_len, best_sum = cur_len, cur_sum
        else:
            cur_len = cur_sum = 0
    return best_len, best_sum


def equity_curve(rs: list[float], mode: str) -> tuple[list[float], list[float]]:
    eq, dd = [], []
    if mode == "fix":
        e = START
        for r in rs:
            e += r * 500.0
            eq.append(e)
    else:
        e = START
        for r in rs:
            e *= 1.0 + PCT * r
            eq.append(e)
    peak = START
    for e in eq:
        peak = max(peak, e)
        dd.append(e - peak)
    return eq, dd


def report(label: str, rs: list[float]) -> None:
    n = len(rs)
    wins = sum(1 for r in rs if r > 0)
    sum_r = sum(rs)
    bl, bs = streak(rs)
    print(f"### {label}  ({n} Trades | WR {wins/n*100:.1f}% | Summe R {sum_r:+.2f}R "
          f"| max. Verlustserie {bl} Tr / {bs:+.2f}R)")
    for mode, mname in [("fix", "FIX 500 USD/Trade (5% von 10k)"),
                        ("comp", "COMPOUND 5% vom laufenden Equity")]:
        eq, dd = equity_curve(rs, mode)
        end = eq[-1]
        peak = START
        for e in eq:
            peak = max(peak, e)
        max_dd = min(dd)
        min_eq = min(eq)
        pct_dd = max_dd / peak * 100.0
        print(f"  [{mname}]")
        print(f"    Endstand {end:>12,.2f} USD | Gewinn {end-START:>+12,.2f} USD "
              f"| Rendite {((end-START)/START)*100:>+8.2f} %")
        print(f"    Tiefstand {min_eq:>12,.2f} USD | Max-DD {max_dd:>+12,.2f} USD "
              f"({pct_dd:.2f} % vom Peak {peak:,.2f})")
    print()


for key in ("AUG", "S1", "S2"):
    rs = parse(FILES[key])
    report(key, rs)

# Chronologische Kombination S2(2025) dann S1(2026) als Zusatz
rs = parse(FILES["S2"]) + parse(FILES["S1"])
report("S2+S1 chronologisch (2025 -> 2026)", rs)
