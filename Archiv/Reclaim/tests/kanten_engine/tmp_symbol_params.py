"""ATR-Skalierung SYMBOL vs SILVER (M15) - generische Parameterbestimmung.

Basis: SILVER-Baseline-Defaults (TOL 0.34 / TOL_TOUCH 0.15 / DENSITY_BAND 0.15 /
SHIFT_TOL 0.05 USD). USD-Schwellen werden je Fenster (VOLLFENSTER = identische
Grenzen wie der Engine-Lauf) ueber das ATR-Ratio SYMBOL/SILVER skaliert.
SL_PCT wird auf ~0.87 ATR des Assets gesetzt.
"""
from __future__ import annotations

import sys

import duckdb
import pandas as pd

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "Cocoa"
DB = r"data/market_data.duckdb"
FENSTER = {
    "AUG": ("2026-08-10", "2026-08-28"),
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}
TOL_B, TOL_TOUCH_B, DENSITY_BAND_B, SHIFT_TOL_B, SL_PCT_B = 0.34, 0.15, 0.15, 0.05, 0.45


def stats(symbol: str, a: str, b: str) -> dict:
    con = duckdb.connect(DB, read_only=True)
    try:
        r = con.execute(
            f"""
            SELECT count(*) AS n, avg(high-low) AS range_avg,
                   avg(close) AS price_avg
            FROM ohlcv_bars
            WHERE symbol='{symbol}' AND timeframe='M15'
              AND time AT TIME ZONE 'UTC' >= DATE '{a}'
              AND time AT TIME ZONE 'UTC' <  DATE '{b}'
            """
        ).fetchdf().to_dict("records")[0]
    finally:
        con.close()
    return r


rows = []
for name, (a, b) in FENSTER.items():
    sil = stats("SILVER", a, b)
    sym = stats(SYMBOL, a, b)
    ratio = sym["range_avg"] / sil["range_avg"] if sil["range_avg"] else float("nan")
    rows.append({
        "fenster": name,
        "sym_n": sym["n"],
        "sym_range_avg": sym["range_avg"],
        "sil_range_avg": sil["range_avg"],
        "ratio": ratio,
        "price_avg": sym["price_avg"],
        "range_pct": sym["range_avg"] / sym["price_avg"] * 100.0 if sym["price_avg"] else 0.0,
        "TOL": TOL_B * ratio,
        "TOL_TOUCH": TOL_TOUCH_B * ratio,
        "DENSITY_BAND": DENSITY_BAND_B * ratio,
        "SHIFT_TOL": SHIFT_TOL_B * ratio,
        "SL_PCT_087atr": 0.87 * sym["range_avg"] / sym["price_avg"] * 100.0 if sym["price_avg"] else 0.0,
        "SL_PCT_1R_SilverAeq": SL_PCT_B * ratio * (sil["price_avg"] / sym["price_avg"]),
    })
df = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(df.round(4).to_string(index=False))
print(f"\n--- CLI-Sets fuer {SYMBOL} ---")
for _, r in df.iterrows():
    print(
        f"{r['fenster']}: --tol={r['TOL']:.4f} --tol-touch={r['TOL_TOUCH']:.4f} "
        f"--density-band={r['DENSITY_BAND']:.4f} --shift-tol={r['SHIFT_TOL']:.4f} "
        f"--sl-pct={r['SL_PCT_087atr']:.4f}"
    )
