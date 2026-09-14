"""READ-ONLY: Orphaned-Turn-Obduktion — Was geschah nach dem Tod von Phase 7 (11.04.2025)?
Fenster: 01.04.2025 - 15.06.2025 (SILVER M15, UTC). Zeigt:
  1) Tages-Schluesse + SMA20/50 (D1, kausal) im Fenster
  2) M15-Pfad: Wo war der Turn fuer die Phase-7-Shorts? (Fall nach dem 11.04?)
  3) Warum dauerte die neue Phasen-Etablierung bis 02.06? (Balance-Zonen-Check)
  4) Kontrast: Phase 7 (Apr 2025) vs. Phase 132 (Aug 2026) Makro-Kontext
Report: test/tmp_orphaned_turn_ph7.txt
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import duckdb
import pandas as pd
import numpy as np

con = duckdb.connect("data/market_data.duckdb", read_only=True)

# ---------- SILVER M15 2025 (Jan-Jun) + 2026 (Jun-Sep) ----------
df25 = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15' AND time >= '2025-01-01' AND time < '2025-07-01' ORDER BY t
""").df()
df25["t"] = pd.to_datetime(df25["t"], utc=True)
df25 = df25.set_index("t")
df26 = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15' AND time >= '2026-06-01' AND time < '2026-09-01' ORDER BY t
""").df()
df26["t"] = pd.to_datetime(df26["t"], utc=True)
df26 = df26.set_index("t")

lines = []
def emit(s=""):
    lines.append(s)

emit("=" * 100)
emit("ORPHANED-TURN-OBDUKTION Phase 7 (S2 Apr 2025) vs. Phase 132 (S1 Aug 2026)")
emit("=" * 100)

# ---------- TEIL 1: Was geschah NACH Phasentod Phase 7 (11.04. 12:45) ----------
emit("\n" + "=" * 100)
emit("TEIL 1: SILVER Tages-Schluesse + Makro-SMA nach Phasentod (11.04.2025)")
emit("=" * 100)
daily = df25["close"].resample("D").last().dropna()
sma20 = daily.rolling(20).mean()
sma50 = daily.rolling(50).mean()
emit(f"{'Datum':<12}{'Close':>9}{'SMA20':>9}{'SMA50':>9}{'vs20%':>8}{'vs50%':>8} | Kommentar")
fenster = daily[(daily.index >= '2025-04-08') & (daily.index <= '2025-06-10')]
for d, c in fenster.items():
    s20 = sma20.loc[d] if d in sma20.index and not pd.isna(sma20.loc[d]) else np.nan
    s50 = sma50.loc[d] if d in sma50.index and not pd.isna(sma50.loc[d]) else np.nan
    vs20 = (c / s20 - 1) * 100 if not np.isnan(s20) else np.nan
    vs50 = (c / s50 - 1) * 100 if not np.isnan(s50) else np.nan
    kommentar = ""
    if d == pd.Timestamp('2025-04-11'): kommentar = "<-- Phasentod Phase 7"
    if d == pd.Timestamp('2025-06-02'): kommentar = "<-- Phase 8 Start"
    emit(f"{d:%d.%m.%Y:<12}{c:>9.3f}{s20:>9.3f}{s50:>9.3f}{vs20:>+8.2f}{vs50:>+8.2f} {kommentar}")

# ---------- TEIL 2: M15-Pfad nach Phasentod: Wann kam der Fall (Turn fuer Shorts)? ----------
emit("\n" + "=" * 100)
emit("TEIL 2: M15-Pfad 11.04.-30.04. (Wo war der Turn der Phase-7-Shorts?)")
emit("=" * 100)
seg = df25[(df25.index >= '2025-04-11 12:00') & (df25.index < '2025-05-01')]
# 6h-Samples
s6 = seg["close"].resample('6h').last().dropna()
prev = None
for ts, c in s6.items():
    emit(f"  {ts:%d.%m %H:%M}  close {c:>8.3f}")
emit(f"\n  April-Gesamt: {(daily.loc['2025-04-30']/daily.loc['2025-04-01']-1)*100:+.2f}%")
emit(f"  Phase-7-Fenster (04.-11.04): {(seg['close'].iloc[-1] if len(seg) else np.nan)}")

# ---------- TEIL 3: Warum 52 Tage keine Phase? (Balance-Zonen / Range-Bildung) ----------
emit("\n" + "=" * 100)
emit("TEIL 3: Monats-Ranges Apr/Mai 2025 (warum keine neue Phase?)")
emit("=" * 100)
for monat, d0, d1 in [("April 2025", '2025-04-01', '2025-05-01'), ("Mai 2025", '2025-05-01', '2025-06-01')]:
    m = df25[(df25.index >= d0) & (df25.index < d1)]
    hi, lo = m["high"].max(), m["low"].min()
    c0, c1 = m["close"].iloc[0], m["close"].iloc[-1]
    emit(f"  {monat}: High {hi:.3f} | Low {lo:.3f} | Range {hi-lo:.3f} ({(hi-lo)/lo*100:.1f}%) | "
         f"Close {c0:.3f}->{c1:.3f} ({(c1/c0-1)*100:+.1f}%)")
# Wochen-Zusammenfassung Apr-Mai
emit("\n  Wochen-Zusammenfassung (Mo-So close/close):")
w = daily.resample('W').last().dropna()
w_idx = [ts.tz_localize(None) for ts in w.index]
for i, ts in enumerate(w.index):
    if pd.Timestamp('2025-03-30') <= w_idx[i] <= pd.Timestamp('2025-06-02'):
        emit(f"    {ts:%d.%m}: close {w.loc[ts]:.3f}")

# ---------- TEIL 4: Kontrast Phase 132 (S1 Aug 2026) ----------
emit("\n" + "=" * 100)
emit("TEIL 4: KONTRAST Phase 132 (Aug 2026) — Makro-Kontext")
emit("=" * 100)
# Phase 132: T183-T187 SHORT-Verluste 14.-17.08, T188/T189 Turns 17./18.08
# Monats-Kontext August 2026
aug = df26[(df26.index >= '2026-08-01') & (df26.index < '2026-09-01')]
emit(f"  August 2026: High {aug['high'].max():.3f} | Low {aug['low'].min():.3f} | "
     f"Close {aug['close'].iloc[0]:.3f}->{aug['close'].iloc[-1]:.3f} "
     f"({(aug['close'].iloc[-1]/aug['close'].iloc[0]-1)*100:+.1f}%)")
# Phase-132-Fenster Tagespfad
p132 = df26[(df26.index >= '2026-08-12') & (df26.index < '2026-08-25')]
emit("  Tages-Schluesse 12.-25.08.2026:")
for d, c in p132["close"].resample("D").last().items():
    emit(f"    {d:%d.%m}: {c:.3f}")
# SMA-Kontext August 2026 (naechste 3 Monate davor fuer Makro-Lage)
d26 = df26["close"].resample("D").last().dropna()
s20_26 = d26.rolling(20).mean()
emit("\n  Makro-Lage Aug 2026 (vs SMA20 auf Tagesbasis, kausal):")
for d in pd.date_range('2026-08-14', '2026-08-19'):
    if d in d26.index:
        c = d26.loc[d]
        s = s20_26.loc[d] if d in s20_26.index else np.nan
        emit(f"    {d:%d.%m}: close {c:.3f} vs SMA20 {s:.3f} ({(c/s-1)*100 if not pd.isna(s) else 0:+.1f}%)")

# ---------- TEIL 5: Makro-Lage Phase 7 (Feb-Apr 2025) ----------
emit("\n" + "=" * 100)
emit("TEIL 5: MAKRO-LAGE Phase 7 — SILVER D1-Kontext Jan-Apr 2025")
emit("=" * 100)
d25 = df25["close"].resample("D").last().dropna()
sma50_25 = d25.rolling(50).mean()
emit("  Monats-Closes (close/close) und SMA50:")
for d in d25.index:
    if d.day in (1, 15, 28) and pd.Timestamp('2025-01-01') <= d.tz_localize(None) <= pd.Timestamp('2025-04-30'):
        s = sma50_25.loc[d] if d in sma50_25.index else np.nan
        emit(f"    {d:%d.%m.%Y}: close {d25.loc[d]:>7.3f} | SMA50 {s:>7.3f} | "
             f"{(d25.loc[d]/s-1)*100 if not pd.isna(s) else 0:+.1f}% vs SMA50")
emit("\n  Wo stand Phase 7 (April 2025) im groesseren Bild?")
emit("  2025: Jan +8.1%, Feb -0.6%, Maer +9.0%, Apr -4.2% (aus Monats-Kontrast)")
emit("  Phase 7 handelte 04.-11.04. bei ~29-31 USD (SHORT-Kaskade in steigende Kante U)")

with open("test/tmp_orphaned_turn_ph7.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
print(f"\n-> test/tmp_orphaned_turn_ph7.txt ({len(lines)} Zeilen)")
