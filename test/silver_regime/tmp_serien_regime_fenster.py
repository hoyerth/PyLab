"""Read-only: Serien-zentrierte Regime-Charakteristik + kausales Makro-Trendmass je Trade.
Teil 1: Fuer alle max. Verlustserien >= 4 (S1/S2): Markt im Serien-Fenster + Vorfeld.
Teil 2: Fuer JEDEN Trade (kausal, nur Bars VOR Signalzeit): close/SMA20, close/SMA50,
        ret5d/ret10d, KER5d -> Kontrast Serien-Verluste vs. Winner vs. restliche Verluste.
Report: test/tmp_serien_regime_fenster.txt
"""
import sys, re, glob
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding="utf-8")
import duckdb
import pandas as pd
import numpy as np

# ---------- Daten ----------
con = duckdb.connect("data/market_data.duckdb", read_only=True)
df = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close
    FROM ohlcv_bars WHERE symbol='SILVER' AND timeframe='M15'
      AND time >= '2024-11-15' AND time < '2026-09-01' ORDER BY t
""").df()
df["t"] = pd.to_datetime(df["t"], utc=True)
df = df.set_index("t")

# ---------- Trade-Stream (Zeit = Signalzeit aus Monatsberichten) ----------
def parse_monatsdatei(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)", line)
        if m:
            out.append(dict(nr=int(m.group(1)), ph=int(m.group(2)),
                            dt=datetime(int(m.group(5)), int(m.group(4)), int(m.group(3)),
                                        int(m.group(6)), int(m.group(7))),
                            direction=m.group(8), entry=float(m.group(9)), r=float(m.group(10))))
    return out

trades = []
for fenster, jahr in [("S1", 2026), ("S2", 2025)]:
    for f in sorted(glob.glob(f"test/tmp_{fenster}_monatslauf_{jahr}-*.txt")):
        for t in parse_monatsdatei(f):
            t["fenster"] = fenster
            trades.append(t)
trades.sort(key=lambda t: t["dt"])

# SMA-Spalten auf Tages-Closes (kausal aufgebaut)
daily = df["close"].resample("D").last().dropna()
sma20 = daily.rolling(20).mean()
sma50 = daily.rolling(50).mean()
# Tages-Returns
dret = daily.pct_change()

def trendmass(trade_dt):
    """Kausal: nutzt nur Bars mit t < signal_dt (strikt). Liefert dict."""
    t0 = pd.Timestamp(trade_dt, tz="UTC")
    before = df[df.index < t0]
    if len(before) < 20:
        return None
    c_last = before["close"].iloc[-1]
    d_before = daily[daily.index < t0]
    if len(d_before) < 50:
        return None
    c_day = d_before.iloc[-1]
    sma20v = sma20.loc[d_before.index[-1]]
    sma50v = sma50.loc[d_before.index[-1]]
    # ret5d/ret10d ueber Tages-Closes
    r5 = (d_before.iloc[-1] / d_before.iloc[-6] - 1) * 100 if len(d_before) >= 6 else np.nan
    r10 = (d_before.iloc[-1] / d_before.iloc[-11] - 1) * 100 if len(d_before) >= 11 else np.nan
    # KER5d (Tages-Closes)
    seg = d_before.iloc[-6:]
    ker5 = abs(seg.iloc[-1] / seg.iloc[0] - 1) / max(seg.pct_change().abs().sum(), 1e-9)
    return dict(c_sma20=c_last / sma20v if not np.isnan(sma20v) else np.nan,
                c_sma50=c_last / sma50v,
                ret5d=r5, ret10d=r10, ker5d=ker5,
                ueber_sma20=1 if c_last > sma20v else 0,
                ueber_sma50=1 if c_last > sma50v else 0)

for t in trades:
    t["tm"] = trendmass(t["dt"])

# ---------- Serien erkennnen ----------
def find_serien(tr, minlen=4):
    serien = []
    i = 0
    while i < len(tr):
        if tr[i]["r"] < 0:
            j = i
            while j + 1 < len(tr) and tr[j + 1]["r"] < 0:
                j += 1
            if j - i + 1 >= minlen:
                serien.append(tr[i:j + 1])
            i = j + 1
        else:
            i += 1
    return serien

lines = []
def emit(s=""):
    lines.append(s)

emit("=" * 118)
emit("SERIEN-ZENTRIERTE REGIME-CHARAKTERISTIK + KAUALES MAKRO-TRENDMASS (SILVER M15, UTC)")
emit("=" * 118)

# ---------- Teil 1: Serien-Fenster ----------
emit("\nTEIL 1: MARKT IM SERIEN-FENSTER (M15-Close vom 1. Signal bis letzter Signal + Kontext)")
emit(f"{'Serie':<14}{'Fenster (UTC)':<32}{'Ret%':>7}{'MaxDD%':>8}{'KER_d':>7}{'Vola_d%':>8} | {'Kontext vor Serie':<28} | n SumR")
emit("-" * 118)
for fenster in ["S1", "S2"]:
    tr = [t for t in trades if t["fenster"] == fenster]
    for seg in find_serien(tr):
        d0, d1 = seg[0]["dt"], seg[-1]["dt"]
        fen = df[(df.index >= pd.Timestamp(d0, tz="UTC")) & (df.index <= pd.Timestamp(d1, tz="UTC"))]
        if len(fen) < 10:
            continue
        ret = (fen["close"].iloc[-1] / fen["close"].iloc[0] - 1) * 100
        maxdd = ((fen["close"] / fen["close"].cummax()) - 1).min() * 100
        # KER & Vola auf Tagesbasis im Fenster
        dl = fen["close"].resample("D").last().dropna()
        ker = abs(dl.iloc[-1] / dl.iloc[0] - 1) / max(dl.pct_change().abs().sum(), 1e-9) if len(dl) > 1 else np.nan
        dhl = (fen["high"].resample("D").max() - fen["low"].resample("D").min()) / fen["close"].resample("D").last()
        vola = dhl.mean() * 100
        # Kontext: 5 Tage VOR Serie
        t5 = pd.Timestamp(d0, tz="UTC") - pd.Timedelta(days=5)
        ctx = df[(df.index >= t5) & (df.index < pd.Timestamp(d0, tz="UTC"))]
        ctxret = (ctx["close"].iloc[-1] / ctx["close"].iloc[0] - 1) * 100 if len(ctx) > 10 else np.nan
        dirs = {}
        for t in seg:
            dirs[t["direction"]] = dirs.get(t["direction"], 0) + 1
        name = f"{fenster} T{seg[0]['nr']}-T{seg[-1]['nr']}"
        sumr = sum(t["r"] for t in seg)
        emit(f"{name:<14}{d0:%d.%m %H:%M}..{d1:%d.%m %H:%M}  {ret:>+6.2f}% {maxdd:>+7.2f}% "
             f"{ker:>6.2f} {vola:>7.2f}% | 5d-Vorlauf {ctxret:>+6.2f}% ({dirs})  | {len(seg):>2} {sumr:>+6.2f}R")

# ---------- Teil 2: Kausales Makro-Trendmass je Trade ----------
emit("\n" + "=" * 118)
emit("TEIL 2: KAUALES MAKRO-TRENDMASS JE TRADE (nur Bars VOR Signalzeit)")
emit("=" * 118)
for fenster in ["S1", "S2"]:
    tr = [t for t in trades if t["fenster"] == fenster and t["tm"]]
    serien_ids = set()
    for seg in find_serien([t for t in trades if t["fenster"] == fenster]):
        for t in seg:
            serien_ids.add(t["nr"])
    g_w = [t for t in tr if t["r"] > 0]
    g_l_all = [t for t in tr if t["r"] < 0 and t["nr"] not in serien_ids]
    g_l_ser = [t for t in tr if t["r"] < 0 and t["nr"] in serien_ids]
    emit(f"\n{fenster}: Winner n={len(g_w)} | Einzel-Verluste n={len(g_l_all)} | Serien-Verluste n={len(g_l_ser)}")
    emit(f"  {'Mass':<12}{'Winner':>10}{'Einzel-L':>12}{'Serien-L':>12}  | Interpretation")
    def med(x, k):
        v = [t["tm"][k] for t in x if t["tm"] and not np.isnan(t["tm"][k])]
        return np.median(v) if v else np.nan
    def u20(x):
        v = [t["tm"]["ueber_sma20"] for t in x if t["tm"]]
        return 100 * np.mean(v) if v else np.nan
    def u50(x):
        v = [t["tm"]["ueber_sma50"] for t in x if t["tm"]]
        return 100 * np.mean(v) if v else np.nan
    emit(f"  {'close/SMA20':<12}{med(g_w,'c_sma20'):>10.4f}{med(g_l_all,'c_sma20'):>12.4f}{med(g_l_ser,'c_sma20'):>12.4f}  | >1 = ueber SMA20")
    emit(f"  {'close/SMA50':<12}{med(g_w,'c_sma50'):>10.4f}{med(g_l_all,'c_sma50'):>12.4f}{med(g_l_ser,'c_sma50'):>12.4f}  | >1 = ueber SMA50")
    emit(f"  {'ret5d %':<12}{med(g_w,'ret5d'):>+10.2f}{med(g_l_all,'ret5d'):>+12.2f}{med(g_l_ser,'ret5d'):>+12.2f}  | 5-Tages-Return vor Signal")
    emit(f"  {'ret10d %':<12}{med(g_w,'ret10d'):>+10.2f}{med(g_l_all,'ret10d'):>+12.2f}{med(g_l_ser,'ret10d'):>+12.2f}  | 10-Tages-Return vor Signal")
    emit(f"  {'KER5d':<12}{med(g_w,'ker5d'):>10.3f}{med(g_l_all,'ker5d'):>12.3f}{med(g_l_ser,'ker5d'):>12.3f}  | Trend-Effizienz letzte 5 Tage")
    emit(f"  {'ueber SMA20%':<12}{u20(g_w):>10.1f}{u20(g_l_all):>12.1f}{u20(g_l_ser):>12.1f}  | Anteil Trades ueber SMA20")
    emit(f"  {'ueber SMA50%':<12}{u50(g_w):>10.1f}{u50(g_l_all):>12.1f}{u50(g_l_ser):>12.1f}  | Anteil Trades ueber SMA50")
    # Richtungs-Kontrast: LONG-Trades in Abwärtslage
    emit("\n  Detail: LONG-Trades (Sollten in Up-Regime liegen):")
    for grpname, grp in [("Winner-LONG", [t for t in g_w if t["direction"] == "LONG"]),
                          ("Serien-LONG", [t for t in g_l_ser if t["direction"] == "LONG"]),
                          ("Einzel-LONG-Verl.", [t for t in g_l_all if t["direction"] == "LONG"])]:
        if not grp:
            continue
        emit(f"    {grpname:<18} n={len(grp):>3} | ret5d-Median {med(grp,'ret5d'):>+6.2f}% | "
             f"close/SMA20 {med(grp,'c_sma20'):.4f} | ueber SMA20 {u20(grp):.0f}% | ueber SMA50 {u50(grp):.0f}%")
    emit("\n  Detail: SHORT-Trades (Sollten in Down-Regime liegen):")
    for grpname, grp in [("Winner-SHORT", [t for t in g_w if t["direction"] == "SHORT"]),
                          ("Serien-SHORT", [t for t in g_l_ser if t["direction"] == "SHORT"]),
                          ("Einzel-SHORT-Verl.", [t for t in g_l_all if t["direction"] == "SHORT"])]:
        if not grp:
            continue
        emit(f"    {grpname:<18} n={len(grp):>3} | ret5d-Median {med(grp,'ret5d'):>+6.2f}% | "
             f"close/SMA20 {med(grp,'c_sma20'):.4f} | ueber SMA20 {u20(grp):.0f}% | ueber SMA50 {u50(grp):.0f}%")

with open("test/tmp_serien_regime_fenster.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
print(f"\n-> Report: test/tmp_serien_regime_fenster.txt ({len(lines)} Zeilen)")
