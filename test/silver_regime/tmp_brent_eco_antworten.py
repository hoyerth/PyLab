"""Wirtschaftliche Auswertung BRENT M15 (Reclaim-Baseline) fuer User-Frage.

Konvention (User): Risiko 300 USD je Trade (1R = 300 USD), Startkapital 10.000
USD S1, KEINE Kosten, fixe Positionsgroesse (kein Zinseszinseffekt), wie in
docs/Archiv 'Symbole Testlaeufe.md' (dort 1R = 100 USD; hier x3).

Fragen:
  1) Max. Verlustserie (laengste Folge aufeinanderfolgender Verlusttrades)
     in Anzahl Trades / Summe R / USD bei 300 USD je Trade.
  2) Endstand S1 in USD bei Startkapital 10.000 USD.

Quelle: reproduzierte Trade-Logs test/stats_trades_Brent_{AUG,S1,S2}.txt
(bitgenau: AUG 22Tr/-3.02R, S1 231Tr/+134.83R, S2 231Tr/+212.85R).
"""
from __future__ import annotations

from pathlib import Path

TEST = Path(__file__).resolve().parent
RISK_USD = 300.0
START_CAP = 10_000.0

FILES = {
    "AUG": TEST / "stats_trades_Brent_AUG.txt",
    "S1": TEST / "stats_trades_Brent_S1.txt",
    "S2": TEST / "stats_trades_Brent_S2.txt",
}


def parse(path: Path) -> list[float]:
    """Liest R_Result je Trade in Handelsreihenfolge (Spalte 9, '|'-separiert)."""
    out: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line or "Trade_Nr" in line or "----" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 9:
            continue
        try:
            int(parts[0])
            r = float(parts[8])
        except ValueError:
            continue
        out.append(r)
    return out


def analyse(label: str, rs: list[float], cap: float | None = None) -> None:
    n = len(rs)
    losses = [r for r in rs if r < 0]
    wins = [r for r in rs if r > 0]
    sum_r = sum(rs)
    # laengste Verlustserie (r < 0)
    best_len = best_sum = 0
    cur_len = cur_sum = 0
    for r in rs:
        if r < 0:
            cur_len += 1
            cur_sum += r
            if cur_len > best_len or (cur_len == best_len and cur_sum < best_sum):
                best_len, best_sum = cur_len, cur_sum
        else:
            cur_len = cur_sum = 0
    # Worst-Case-Geldbetrag der Serie (nur SL-Volllverluste = -1R => -300 USD;
    # reale Serie kann Teilverluste enthalten => Summe R * 300).
    # Equity-Verlauf bei fixem Risiko 300 USD/Trade
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    min_eq = 0.0
    dd_start = None
    for i, r in enumerate(rs):
        eq += r * RISK_USD
        min_eq = min(min_eq, eq)
        if eq > peak:
            peak = eq
            dd_start = None
        else:
            if dd_start is None:
                dd_start = i
            dd = eq - peak
            if dd < max_dd:
                max_dd = dd
    print(f"=== {label} ===")
    print(f"  Trades {n} | Gewinn {len(wins)} / Verlust {len(losses)} | "
          f"WR {len(wins)/n*100:.1f}% | Summe R {sum_r:+.2f}R")
    print(f"  Max. Verlustserie: {best_len} Trades, Summe {best_sum:+.2f}R "
          f"(= {best_sum*RISK_USD:+,.0f} USD bei {RISK_USD:.0f} USD/Trade)")
    if cap is not None:
        end = cap + sum_r * RISK_USD
        min_equity = cap + min_eq
        print(f"  Startkapital {cap:,.0f} USD + fix {RISK_USD:.0f} USD/Trade:")
        print(f"    Endstand      : {end:+,.2f} USD")
        print(f"    Tiefstand     : {min_equity:+,.2f} USD (kum. {min_eq:+,.2f} USD)")
        print(f"    Max Drawdown  : {max_dd:,.2f} USD (kum. Equity, Peak-basiert)")
    print()


for name, path in FILES.items():
    rs = parse(path)
    analyse(name, rs, cap=START_CAP if name == "S1" else None)

# Chronologische Kombination S2(2025) + S1(2026): realer Handelsverlauf
rs_s2 = parse(FILES["S2"])
rs_s1 = parse(FILES["S1"])
combined = rs_s2 + rs_s1
analyse("S2+S1 chronologisch (2025 dann 2026)", combined, cap=START_CAP)

# Kontrolle
print("Kontrollen:", {k: f"{sum(parse(v)):+.2f}R / {len(parse(v))} Tr"
                       for k, v in FILES.items()})
