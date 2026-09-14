"""READ-ONLY Vorabcheck (Mentor-Frage 2): Swing-Struktur VOR jedem Signal.
Phase 5 (S2, T42-T54) und Phase 132 (S1, T183-T189).
Frage: Hatte der Turn (T54/T188) ein hoeheres Zwischentief (bzw. SHORT: niedrigeres
Zwischenhoch) ausgebildet, waehrend die Serien-Verluste in frische Extrema kauften?
Nur Bars VOR Signalzeit (strikt kausal). Report: test/tmp_struktur_vorabcheck.txt
"""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
import duckdb
import pandas as pd
import numpy as np

con = duckdb.connect("data/market_data.duckdb", read_only=True)

# ---------- M15 SILVER UTC ----------
df_s2 = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15' AND time >= '2025-01-01' AND time < '2025-12-01' ORDER BY t
""").df()
df_s1 = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15' AND time >= '2026-02-05' AND time < '2026-08-29' ORDER BY t
""").df()
for d in (df_s2, df_s1):
    d["t"] = pd.to_datetime(d["t"], utc=True)
df_s2 = df_s2.set_index("t")
df_s1 = df_s1.set_index("t")

# ---------- Trade-Cluster (Zeit, Entry aus Monatsberichten) ----------
def cluster_aus_monats(datei, lo, hi):
    tr = {}
    for line in open(datei, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)", line)
        if m:
            nr = int(m.group(1))
            if lo <= nr <= hi:
                tr[nr] = dict(dt=pd.Timestamp(datetime := __import__("datetime").datetime(
                    int(m.group(5)), int(m.group(4)), int(m.group(3)), int(m.group(6)), int(m.group(7))), tz="UTC"),
                    direction=m.group(8), entry=float(m.group(9)), r=float(m.group(10)))
    return tr

c5 = cluster_aus_monats("test/tmp_S2_monatslauf_2025-02.txt", 42, 54)   # Phase 5 (plus T42-44 in Ph5)
c132 = cluster_aus_monats("test/tmp_S1_monatslauf_2026-08.txt", 183, 189)

def pivot_lows(sub, k=2):
    """Fraktal-Pivot-Tiefs: Bar low < k Bars links/rechts. Liefert Liste (idx_ts, low)."""
    lo = sub["low"].to_numpy()
    ts = sub.index.to_numpy()
    out = []
    for i in range(k, len(lo) - k):
        if lo[i] == min(lo[i - k:i + k + 1]):
            out.append((ts[i], lo[i]))
    return out

def analyse(tr, df, fensterlabel):
    lines = []
    lines.append("=" * 110)
    lines.append(fensterlabel)
    lines.append("=" * 110)
    lines.append(f"{'Nr':>4} {'Zeit UTC':<16} {'Dir':<5} {'Entry':>8} {'R':>7} | "
                 f"{'letzte 2 Pivot-Lows':<40} {'Struktur':<22} {'Entry vs letztem Low':<18}")
    for nr in sorted(tr):
        t = tr[nr]
        t0 = t["dt"]
        sub = df[df.index < t0]
        if len(sub) < 200:
            continue
        sub = sub.iloc[-200:]                      # letzte 200 Bars (50h) vor Signal
        pl = pivot_lows(sub, 2)
        if len(pl) >= 2:
            (tsA, lowA), (tsB, lowB) = pl[-2], pl[-1]   # A = aelter, B = juenger
            # fuer LONG: ist B > A = Higher Low?  fuer SHORT: High-Struktur analog
            if t["direction"] == "LONG":
                hoeher = lowB > lowA
                struktur = "HIGHER-LOW (bullisch)" if hoeher else "LOWER-LOW (baerisch)"
                vs = t["entry"] - lowB
            else:
                hoeher = lowB < lowA   # SHORT-Fall: betrachte Pivot-Hochs stattdessen
                struktur = "LOWER-LOW (bestaetigt)" if not hoeher else "HIGHER-LOW (Umkehr?)"
                vs = lowB - t["entry"]
            zeitB = pd.Timestamp(tsB).strftime("%d.%m %H:%M")
            zeitA = pd.Timestamp(tsA).strftime("%d.%m %H:%M")
            abstand_pct = vs / t["entry"] * 100 if t["entry"] else 0
            mark = "  <-- frischeres Extrem" if (t["direction"] == "LONG" and t["entry"] <= lowB * 1.001) or (t["direction"] == "SHORT" and t["entry"] >= lowB * 0.999) else ""
            lines.append(f"{nr:>4} {t['dt']:%d.%m %H:%M} {t['direction']:<5} {t['entry']:>8.3f} {t['r']:>+7.2f} | "
                         f"L1 {lowA:.3f} ({zeitA}) -> L2 {lowB:.3f} ({zeitB}) | {struktur:<22} "
                         f"{vs:>+8.3f} ({abstand_pct:+.2f}%){mark}")
        else:
            lines.append(f"{nr:>4} {t['dt']:%d.%m %H:%M} {t['direction']:<5} {t['entry']:>8.3f} {t['r']:>+7.2f} | "
                         f"nicht genug Pivots ({len(pl)})")
    return lines

out = []
out += analyse(c5, df_s2, "PHASE 5 (S2 Feb 2025): T42-T53 Serien-LONGs vs. T54 Turn (+14.05R)")
out += analyse(c132, df_s1, "PHASE 132 (S1 Aug 2026): T183-T187 Serien-SHORTs vs. T188/T189 Turns")

# Zusatz: auch SHORT-Pivot-Hochs fuer Phase 132 (frische Hochs?)
out.append("\n" + "=" * 110)
out.append("PHASE 132 ZUSATZ: Pivot-HOCHs vor jedem Signal (SHORT fragt: neues Hoch?)")
out.append("=" * 110)
def pivot_highs(sub, k=2):
    hi = sub["high"].to_numpy()
    ts = sub.index.to_numpy()
    outl = []
    for i in range(k, len(hi) - k):
        if hi[i] == max(hi[i - k:i + k + 1]):
            outl.append((ts[i], hi[i]))
    return outl

for nr in sorted(c132):
    t = c132[nr]
    sub = df_s1[df_s1.index < t["dt"]].iloc[-200:]
    ph = pivot_highs(sub, 2)
    if len(ph) >= 2:
        (tsA, hA), (tsB, hB) = ph[-2], ph[-1]
        neues_hoch = hB > hA
        struktur = "NEUES HOCH (weiter up)" if neues_hoch else "LOWER-HIGH (Umkehr-Vorbereitung)"
        out.append(f"T{nr:>3} {t['dt']:%d.%m %H:%M} Entry {t['entry']:>7.3f} {t['r']:>+6.2f}R | "
                   f"H1 {hA:.3f} ({pd.Timestamp(tsA):%d.%m %H:%M}) -> H2 {hB:.3f} ({pd.Timestamp(tsB):%d.%m %H:%M}) | {struktur}")

with open("test/tmp_struktur_vorabcheck.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out))
print(f"\n-> test/tmp_struktur_vorabcheck.txt")
