"""READ-ONLY: Mentor-Schritt 1+2 (Option b+a) — Bar-Obduktion Phase 5/132 + Zyklus-Bilanz.
Schritt 1 (Option b): Fuer Phase 5 (S2, T42-T54) und Phase 132 (S1, T183-T189) je Signal:
  Flush-Charakter (Netto 4h/8h), KER, Body-Dominanz, Volumen-Ratio, Entry-Lage in 24h/72h-Range,
  Abstand zum 24h-Tief, Zeit seit Phasenstart. Nur Bars VOR Signal (strikt kausal).
Schritt 2 (Option a): Ueber ALLE Phasen (S1+S2) mit >=4 aufeinanderfolgenden Verlusten INNERHALB
  einer Phase: Streak-R, Turn-Fenster (restliche Trades derselben Phase), Zyklus-Netto,
  Drift-Geschwindigkeit (%/Tag ueber Streak-Fenster) -> ueberkompensierend?
Report: test/tmp_zyklus_obduktion.txt
"""
import sys, re, glob
sys.stdout.reconfigure(encoding="utf-8")
import duckdb
import pandas as pd
import numpy as np

con = duckdb.connect("data/market_data.duckdb", read_only=True)
df_all = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS t, open, high, low, close, tick_volume FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND ((time >= '2025-01-01' AND time < '2025-12-01') OR (time >= '2026-02-05' AND time < '2026-08-29'))
    ORDER BY t
""").df()
df_all["t"] = pd.to_datetime(df_all["t"], utc=True)
df_all = df_all.set_index("t")

def parse_monatsdatei(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s+(LONG|SHORT)\s+([\d.]+)\s+([+-][\d.]+)", line)
        if m:
            out.append(dict(nr=int(m.group(1)), ph=int(m.group(2)),
                            dt=pd.Timestamp(datetime := __import__("datetime").datetime(
                                int(m.group(5)), int(m.group(4)), int(m.group(3)),
                                int(m.group(6)), int(m.group(7))), tz="UTC"),
                            direction=m.group(8), entry=float(m.group(9)), r=float(m.group(10))))
    return out

trades = []
for fenster, jahr in [("S1", 2026), ("S2", 2025)]:
    for f in sorted(glob.glob(f"test/tmp_{fenster}_monatslauf_{jahr}-*.txt")):
        for t in parse_monatsdatei(f):
            t["fenster"] = fenster
            trades.append(t)
trades.sort(key=lambda t: t["dt"])

def signalmetriken(t):
    """Kausal: Bars mit t < signalzeit. Liefert dict oder None."""
    t0 = t["dt"]
    sub = df_all[df_all.index < t0]
    if len(sub) < 300:
        return None
    c = sub["close"].to_numpy()
    hi = sub["high"].to_numpy()
    lo = sub["low"].to_numpy()
    vol = sub["tick_volume"].to_numpy()
    entry = t["entry"]
    m = {}
    # Entry-Lage in 24h (96) / 72h (288) Range
    for name, n in [("24h", 96), ("72h", 288)]:
        lo_n, hi_n = lo[-n:].min(), hi[-n:].max()
        m[f"range_{name}"] = (entry - lo_n) / max(hi_n - lo_n, 1e-9)
        m[f"abstand_low_{name}"] = (entry - lo_n) / entry * 100
    # Flush: Netto % ueber letzte 16/32 Bars (4h/8h) und KER
    for name, n in [("4h", 16), ("8h", 32)]:
        seg = c[-n - 1:]
        m[f"net_{name}"] = (seg[-1] / seg[0] - 1) * 100
    seg16 = c[-17:]
    m["ker16"] = abs(seg16[-1] / seg16[0] - 1) / max(np.abs(np.diff(seg16)).sum(), 1e-9)
    # Body-Dominanz der letzten 4 Bars (Richtung der Schluesse)
    b = sub.iloc[-4:]
    m["body_dom"] = abs(b["close"].sum() - b["open"].sum()) / max((b["high"] - b["low"]).sum(), 1e-9)
    # Volumen-Ratio letzte 16 vs. vorherige 48
    v16, v48 = vol[-16:].mean(), vol[-64:-16].mean()
    m["vol_ratio"] = v16 / max(v48, 1e-9)
    m["n_down_16"] = int((np.diff(c[-17:]) < 0).sum())
    return m

lines = []
def emit(s=""):
    lines.append(s)

emit("=" * 120)
emit("ZYKLUS-OBDUKTION S1/S2 (SILVER M15 UTC) | Schritt 1 (Bar-Obduktion) + Schritt 2 (Zyklus-Bilanz)")
emit("=" * 120)

# ---------------- SCHRITT 1 ----------------
emit("\n" + "=" * 120)
emit("SCHRITT 1 (Option b): BAR-OBDUKTION Phase 5 (S2) & Phase 132 (S1)")
emit("=" * 120)

def obduktion(titel, fenster, cluster_nrs):
    tr = [t for t in trades if t["fenster"] == fenster and t["nr"] in cluster_nrs]
    tr.sort(key=lambda t: t["dt"])
    emit(f"\n--- {titel} ---")
    emit(f"{'Nr':>4} {'Zeit':<12} {'Dir':<5} {'Entry':>8} {'R':>7} | "
         f"{'net4h%':>7}{'net8h%':>8}{'KER16':>6}{'BodyDom':>7}{'VolR':>5}{'nDown16':>7} | "
         f"{'Range24h':>8}{'AbstLow24h%':>10}{'Range72h':>8} | {'Ph-Alter h':>9}")
    for t in tr:
        m = signalmetriken(t)
        if not m:
            emit(f"{t['nr']:>4} {t['dt']:%d.%m %H:%M} {t['direction']:<5} {t['entry']:>8.3f} {t['r']:>+7.2f} | (keine Daten)")
            continue
        ph_alter = (t["dt"] - t["ph_start"]).total_seconds() / 3600 if t.get("ph_start") else float("nan")
        emit(f"{t['nr']:>4} {t['dt']:%d.%m %H:%M} {t['direction']:<5} {t['entry']:>8.3f} {t['r']:>+7.2f} | "
             f"{m['net_4h']:>+7.2f}{m['net_8h']:>+8.2f}{m['ker16']:>6.2f}{m['body_dom']:>7.2f}"
             f"{m['vol_ratio']:>5.2f}{m['n_down_16']:>7} | "
             f"{m['range_24h']:>8.2f}{m['abstand_low_24h']:>+10.2f}{m['range_72h']:>8.2f} | {ph_alter:>9.1f}")

# Phasenstart fuer Alter ermitteln
def lade_phasen(fenster, jahr, logpfad):
    t = open(logpfad, encoding="utf-16").read()
    out = {}
    pat = re.compile(r"^Phase (\d+): \w+ (\d{2})\.(\d{2}) (\d{2}):(\d{2}) -> ")
    for l in t.splitlines():
        m = pat.match(l.strip())
        if m:
            out[int(m.group(1))] = pd.Timestamp(datetime := __import__("datetime").datetime(
                jahr, int(m.group(3)), int(m.group(2)), int(m.group(4)), int(m.group(5))), tz="UTC")
    return out

ph1 = lade_phasen("S1", 2026, "test/tmp_S1_monatslauf.log")
ph2 = lade_phasen("S2", 2025, "test/tmp_S2_monatslauf.log")
for t in trades:
    t["ph_start"] = (ph1 if t["fenster"] == "S1" else ph2).get(t["ph"])

obduktion("Phase 5 (S2 Feb 2025): T42-T53 Serien-LONGs vs. T54 Turn (+14.05R)", "S2", set(range(42, 55)))
obduktion("Phase 132 (S1 Aug 2026): T183-T187 Serien-SHORTs vs. T188/T189 Turns", "S1", set(range(183, 190)))

# Gruppen-Kontrast Schritt 1
emit("\nGRUPPEN-KONTRAST (Mediane): Serien-Verluste vs. Turn-Winner")
for label, fen, loser_set, win_set in [("Phase 5 (S2)", "S2", set(range(42, 54)), {54}),
                                       ("Phase 132 (S1)", "S1", set(range(183, 188)), {188, 189})]:
    L = [signalmetriken(t) for t in trades if t["fenster"] == fen and t["nr"] in loser_set and signalmetriken(t)]
    W = [signalmetriken(t) for t in trades if t["fenster"] == fen and t["nr"] in win_set and signalmetriken(t)]
    def med(x, k):
        v = [m[k] for m in x if m and not np.isnan(m[k])]
        return np.median(v) if v else float("nan")
    emit(f"\n{label}: Verlierer n={len(L)} | Winner n={len(W)}")
    for k in ["net_4h", "net_8h", "ker16", "body_dom", "vol_ratio", "range_24h", "abstand_low_24h"]:
        emit(f"  {k:<16} L-Median {med(L, k):>+9.3f}  W-Median {med(W, k):>+9.3f}")

# ---------------- SCHRITT 2 ----------------
emit("\n" + "=" * 120)
emit("SCHRITT 2 (Option a): ZYKLUS-BILANZ ueber alle Phasen mit >=4 aufeinanderfolgenden Verlusten")
emit("=" * 120)
emit("Streak = >=4 Verluste INNERHALB einer Phase | Turn = restliche Trades DERSELBEN Phase nach Streak-Ende")
emit(f"{'Fen':<4}{'Phase':>5}{'Ph-Dauer d':>10} | {'Streak':<22}{'L-R':>7}{'n':>3} | {'Turn (gleiche Ph)':<34}{'Turn-R':>8}{'n':>3} | {'Zyklus':>8} | {'Drift%/d':>8} {'Ret%':>6} {'KER':>5} {'Komp?':>7}")

by_phase = {}
for t in trades:
    by_phase.setdefault((t["fenster"], t["ph"]), []).append(t)

zeilen = []
for (fen, ph), tr in sorted(by_phase.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    tr.sort(key=lambda t: t["dt"])
    # Streaks innerhalb der Phase
    i = 0
    while i < len(tr):
        if tr[i]["r"] < 0:
            j = i
            while j + 1 < len(tr) and tr[j + 1]["r"] < 0:
                j += 1
            n = j - i + 1
            if n >= 4:
                seg = tr[i:j + 1]
                d0, d1 = seg[0]["dt"], seg[-1]["dt"]
                dauer_d = (d1 - d0).total_seconds() / 86400
                drift = df_all[(df_all.index >= d0) & (df_all.index <= d1)]
                ret = (drift["close"].iloc[-1] / drift["close"].iloc[0] - 1) * 100 if len(drift) > 5 else float("nan")
                dl = drift["close"].resample("D").last().dropna()
                ker = abs(dl.iloc[-1] / dl.iloc[0] - 1) / max(dl.pct_change().abs().sum(), 1e-9) if len(dl) > 1 else float("nan")
                turn = tr[j + 1:]
                turn_r = sum(t["r"] for t in turn)
                streak_r = sum(t["r"] for t in seg)
                zyklus = streak_r + turn_r
                drift_pro_tag = ret / dauer_d if dauer_d > 0 else float("nan")
                komp = "JA" if turn_r > -streak_r else "nein"
                ph_dauer = (ph1 if fen == "S1" else ph2)
                # Phasendauer aus Tableau nicht direkt hier -> aus trade-Zeitspanne grob
                zeilen.append((fen, ph, seg, turn_r, streak_r, zyklus, drift_pro_tag, ret, ker, komp))
            i = j + 1
        else:
            i += 1

emit(f"{'Fen':<4}{'Phase':>5}{'Ph-Dauer d':>10} | {'Streak':<22}{'L-R':>7}{'n':>3} | {'Turn (gleiche Ph)':<34}{'Turn-R':>8}{'n':>3} | {'Zyklus':>8} | {'Drift%/d':>8} {'Ret%':>6} {'KER':>5} {'Komp?':>7}")
for (fen, ph, seg, turn_r, streak_r, zyklus, dpd, ret, ker, komp) in zeilen:
    t0, t1 = seg[0], seg[-1]
    dauer_d = (t1["dt"] - t0["dt"]).total_seconds() / 86400
    ph_dauer = None
    span = f"T{seg[0]['nr']}-T{seg[-1]['nr']} {t0['dt']:%d.%m}-{t1['dt']:%d.%m}"
    turnspan = ""
    # Turn-Beschreibung
    # (Turn-NRs sind die globalen Folgetrades der Phase)
    turn_t = [x for x in trades if x["fenster"] == fen and x["ph"] == ph and x["dt"] > t1["dt"]]
    if turn_t:
        turnspan = f"T{turn_t[0]['nr']}-T{turn_t[-1]['nr']} ({len(turn_t)} Tr)"
    else:
        turnspan = "(keine)"
    emit(f"{fen:<4}{ph:>5}{dauer_d:>10.2f} | {span:<22}{streak_r:>+7.2f}{len(seg):>3} | {turnspan:<34}{turn_r:>+8.2f}{len(turn_t):>3} | {zyklus:>+8.2f} | {dpd:>+8.3f} {ret:>+6.2f} {ker:>5.2f} {komp:>7}")

# Aggregat
emit("\nAGGREGAT:")
for fen in ["S1", "S2"]:
    zz = [z for z in zeilen if z[0] == fen]
    if zz:
        sum_l = sum(z[4] for z in zz)
        sum_t = sum(z[3] for z in zz)
        komp_n = sum(1 for z in zz if z[9] == "JA")
        emit(f"  {fen}: {len(zz)} Phasen mit >=4er-Streak | Streak-R gesamt {sum_l:+.2f}R | "
             f"Turn-R gesamt {sum_t:+.2f}R | ueberkompensierend: {komp_n}/{len(zz)}")

with open("test/tmp_zyklus_obduktion.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines[-80:]))
print(f"\n-> test/tmp_zyklus_obduktion.txt ({len(lines)} Zeilen)")
