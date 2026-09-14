"""Read-only: Monats-Regime-Kontrast SILVER (M15, UTC) vs. Strategie-R.
Laedt SILVER M15 2024-12..2026-09, aggregiert pro Kalendermonat (UTC) Markt-Metriken
und verknuepft sie mit dem Strategie-Ergebnis des Monats (aus Monatslauf-Berichten).
Report: test/tmp_monats_regime_kontrast.txt
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import duckdb
import pandas as pd
import numpy as np

con = duckdb.connect("data/market_data.duckdb", read_only=True)

# --- 1) M15 SILVER laden (UTC normalisiert) ---
df = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close
    FROM ohlcv_bars
    WHERE symbol = 'SILVER' AND timeframe = 'M15'
      AND time >= '2024-12-01' AND time < '2026-09-01'
    ORDER BY t
""").df()
df["t"] = pd.to_datetime(df["t"], utc=True)
df = df.set_index("t")
print(f"M15 SILVER geladen: {len(df)} Bars  {df.index[0]} .. {df.index[-1]}")

# --- 2) Strategie-Monats-R aus den Monatsberichten ---
def monats_r(fenster, jahr):
    import glob, re
    out = {}
    for f in sorted(glob.glob(f"test/tmp_{fenster}_monatslauf_{jahr}-*.txt")):
        m = re.search(r"(\d{4})-(\d{2})\.txt$", f)
        if not m:
            continue
        mon = f"{m.group(1)}-{m.group(2)}"
        s = open(f, encoding="utf-8").read()
        mm = re.search(r"SumR ([+-][\d.]+)R", s)
        nm = re.search(r"Trades (\d+) ", s)
        out[mon] = (float(mm.group(1)) if mm else np.nan, int(nm.group(1)) if nm else 0)
    return out

strat = {}
strat.update(monats_r("S1", 2026))
strat.update(monats_r("S2", 2025))

# --- 3) Monats-Aggregation (UTC) ---
g = df.groupby(df.index.to_period("M"))
rows = []
for mon, sub in g:
    sub = sub.dropna()
    if len(sub) < 100:
        continue
    c0, c1 = sub["close"].iloc[0], sub["close"].iloc[-1]
    ret = (c1 / c0 - 1) * 100
    # Tages-Closes (UTC-Tag)
    daily = sub["close"].resample("D").last().dropna()
    dr = daily.pct_change().dropna() * 100
    ker = abs(daily.iloc[-1] / daily.iloc[0] - 1) / (daily.pct_change().abs().sum())
    # 4h-Closes
    h4 = sub["close"].resample("4h").last().dropna()
    ker4 = abs(h4.iloc[-1] / h4.iloc[0] - 1) / (h4.pct_change().abs().sum()) if len(h4) > 5 else np.nan
    # Range
    dhl = (sub["high"].resample("D").max() - sub["low"].resample("D").min()) / sub["close"].resample("D").last() * 100
    dhl = dhl.dropna()
    # max Run/DD auf M15-close
    cc = sub["close"]
    run = (cc / cc.cummax() - 1).min() * 100       # negativ = DD
    dd = (cc / cc.cummin() - 1).max() * 100          # positiv = Run
    # Trend-Tage (|daily ret| > 1%)
    big = dr[dr.abs() > 1.0]
    rows.append({
        "Monat": str(mon), "Ret%": ret, "KER_d": ker, "KER_4h": ker4,
        "ATR_d%": dr.abs().mean(), "Range_d%": dhl.mean(),
        "MaxDD%": run, "MaxRun%": dd, "BigTage": len(big),
        "nTage": len(dr) + 1, "|d|>1%_Anteil": len(big) / max(len(dr), 1) * 100,
    })

reg = pd.DataFrame(rows).set_index("Monat")

# Strategie-R anfuegen
reg["StratR"] = [strat.get(m, (np.nan, 0))[0] for m in reg.index]
reg["nTr"] = [strat.get(m, (0, 0))[1] for m in reg.index]
# Fenster zuordnen
reg["Fenster"] = ["S2" if m.startswith("2025") else "S1" for m in reg.index]

lines = []
def emit(s=""):
    lines.append(s)

emit("=" * 116)
emit("MONATS-REGIME-KONTRAST SILVER (M15 UTC) | Markt-Metriken vs. Strategie-R | S2=2025, S1=2026")
emit("=" * 116)
emit("KER_d = Trend-Effizienz auf Tages-Closes (0..1, hoch = Trend) | Ret% = Monats-Rendite close/close")
emit("MaxDD%/MaxRun% = groesster M15-close-Rueckschlag/Anstieg im Monat | BigTage = |Tagesret|>1%")
emit("")
emit(f"{'Monat':<8}{'Ret%':>7}{'KER_d':>7}{'KER4h':>7}{'ATR_d%':>7}{'Range%':>7}{'MaxDD%':>8}{'MaxRun%':>9}{'Big':>4}{'|d|>1%':>7} | {'StratR':>8}{'nTr':>4} {'Fenster'}")
emit("-" * 116)

def fmt(v, nd=2):
    return " " * 6 if pd.isna(v) else f"{v:>{7 if nd==2 else 8}.{nd}f}"

for mon, r in reg.iterrows():
    emit(f"{mon:<8}{fmt(r['Ret%'])}{fmt(r['KER_d'])}{fmt(r['KER_4h'])}{fmt(r['ATR_d%'])}"
         f"{fmt(r['Range_d%'])}{fmt(r['MaxDD%'])}{fmt(r['MaxRun%'])}{r['BigTage']:>4}{r['|d|>1%_Anteil']:>6.1f}% | "
         f"{r['StratR']:>+8.2f}R{r['nTr']:>4} {r['Fenster']}")

# --- 4) Kontrast Gruppen ---
emit("\n" + "=" * 116)
emit("KONTRAST: Problem-Monate vs. gute Monate")
emit("=" * 116)
problem = ["2025-02", "2025-07", "2026-06"]   # S2-Feb 17er, S2-Jul 13er, S1-Jun 7er+Kaskade
gut = ["2025-03", "2025-09", "2025-10", "2026-05", "2026-08"]  # Top-Monate
for grp, liste in [("PROBLEM (S2 Feb, S2 Jul, S1 Jun)", problem), ("GUT (Top-Monate)", gut)]:
    sub = reg.loc[liste]
    emit(f"\n{grp}:")
    emit(f"  Ret%     : Mittel {sub['Ret%'].mean():+.2f}  (Spanne {sub['Ret%'].min():+.2f}..{sub['Ret%'].max():+.2f})")
    emit(f"  KER_d    : Mittel {sub['KER_d'].mean():.3f}  (Spanne {sub['KER_d'].min():.3f}..{sub['KER_d'].max():.3f})")
    emit(f"  KER_4h   : Mittel {sub['KER_4h'].mean():.3f}  (Spanne {sub['KER_4h'].min():.3f}..{sub['KER_4h'].max():.3f})")
    emit(f"  ATR_d%   : Mittel {sub['ATR_d%'].mean():.3f}")
    emit(f"  Range_d% : Mittel {sub['Range_d%'].mean():.3f}")
    emit(f"  MaxDD%   : Mittel {sub['MaxDD%'].mean():.2f}")
    emit(f"  MaxRun%  : Mittel {sub['MaxRun%'].mean():.2f}")
    emit(f"  BigTage  : Mittel {sub['BigTage'].mean():.1f}  (|d|>1%: {sub['|d|>1%_Anteil'].mean():.1f}%)")
    emit(f"  StratR   : Mittel {sub['StratR'].mean():+.2f}R")

with open("test/tmp_monats_regime_kontrast.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
print(f"\n-> Report: test/tmp_monats_regime_kontrast.txt ({len(lines)} Zeilen)")
