# -*- coding: utf-8 -*-
"""DD-Episoden-Exploration S1 (READ-ONLY; Schritte 1-3 des Mentor-Plans).

Ziel: Kausale Zuordnung der DD-Episoden zu Phasen/Marktregime, rein lesend.
  * Schritt 1 (Episoden-Mapping): Trades T119-T126 (Episode 2) und T132-T153
    (Episode 1) aus stats_trades_MAKRO_S1.txt -> Phase_ID + globale Bar-Indizes.
  * Schritt 2 (Regime-Analyse): M15-Kurse aus market_data.duckdb in den
    Episoden-Fenstern; Metriken (Netto-Bewegung, Richtungseffizienz, Volatilitaet,
    Tages-Schluesse) zur Charakterisierung Chop vs. Trend vs. Kompression.
  * Schritt 3 (Signal-Cluster-Audit): Verteilung der Verlusttrades auf Phasen
    (gehaeuft in wenigen Phasen vs. gleichmaessig verteilt).

Keine Engine-Laeufe, keine Datei-Schreibzugriffe auf Produktion (I3/I4).
Quellen: test/stats_trades_MAKRO_S1.txt, test/tmp_S1_monatslauf.log
         (Phasen-Tableau des S1-Komplettlaufs), data/market_data.duckdb.
Ausgabe: test/tmp_dd_episode_report.txt
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

DB = Path("data/market_data.duckdb")
TRADE_LOG = Path("test/stats_trades_MAKRO_S1.txt")
PHASE_LOG = Path("test/tmp_S1_monatslauf.log")
OUT = Path("test/tmp_dd_episode_report.txt")

EP1 = (132, 153)   # Episode 1: Peak T132 (+4.16R) -> Tief T153
EP2 = (119, 126)   # Episode 2: 7 Verluste T120-T126 (nach T119-Win)


# ---------------------------------------------------------------- Phase-Tableau aus Komplettlauf-Log
def parse_phase_table(lines: list[str]) -> dict[int, dict]:
    """Parsed 'Phase N: ... -> ... (Dh, XC) [MARKER] | ...' Zeilen."""
    pat = re.compile(
        r"^Phase (\d+): \w+ (\d{2}\.\d{2}) (\d{2}:\d{2}) -> \w+ (\d{2}\.\d{2}) (\d{2}:\d{2}) "
        r"\(([\d.]+)h, (\d+)C\)(.*)$"
    )
    out: dict[int, dict] = {}
    for l in lines:
        m = pat.match(l.strip())
        if not m:
            continue
        pid = int(m.group(1))
        d1, t1, d2, t2 = m.group(2), m.group(3), m.group(4), m.group(5)
        dd1, mm1 = map(int, d1.split("."))
        dd2, mm2 = map(int, d2.split("."))
        h1, mi1 = map(int, t1.split(":"))
        h2, mi2 = map(int, t2.split(":"))
        rest = m.group(8)
        out[pid] = {
            "start": datetime(2026, mm1, dd1, h1, mi1),
            "ende": datetime(2026, mm2, dd2, h2, mi2),
            "dauer_h": float(m.group(6)),
            "bars": int(m.group(7)),
            "marker": rest.strip(),
        }
    return out


# ---------------------------------------------------------------- Trade-Log (globaler Phase_ID)
def parse_trade_log(path: Path) -> list[dict]:
    rows = []
    for l in path.read_text(encoding="utf-8").splitlines():
        parts = l.split("|")
        if len(parts) < 10:
            continue
        try:
            nr = int(parts[0].strip())
        except ValueError:
            continue
        rows.append({
            "nr": nr,
            "phase": int(parts[1].strip()),
            "bar_sig": int(parts[2].strip()),
            "bar_entry": int(parts[3].strip()),
            "typ": parts[4].strip(),
            "dir": parts[5].strip(),
            "entry": float(parts[6].strip()),
            "tier": int(parts[7].strip().replace("Tier ", "")),
            "r": float(parts[8].strip()),
        })
    return rows


# ---------------------------------------------------------------- DB-Bars (identische load_data-Query)
con = duckdb.connect(str(DB), read_only=True)
df = con.execute("""
    SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= DATE '2026-02-05'
      AND time AT TIME ZONE 'UTC' <  DATE '2026-08-29'
    ORDER BY time
""").fetchdf()
con.close()
df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
ts_arr = df["ts"].to_numpy()
cl = df["close"].to_numpy()

phases = parse_phase_table(PHASE_LOG.read_text(encoding="utf-16").splitlines())
trades = parse_trade_log(TRADE_LOG)
by_nr = {t["nr"]: t for t in trades}
assert len(trades) == 201 and len(phases) > 100


# ---------------------------------------------------------------- Helfer
def regimestats(a: datetime, b: datetime) -> dict:
    """Regime-Metriken fuer M15-Fenster [a,b)."""
    m = (df["ts"] >= a) & (df["ts"] < b)
    sub = df[m]
    c = sub["close"].to_numpy()
    dif = np_diff = None
    import numpy as np
    dif = np.abs(np.diff(c))
    de = abs(c[-1] - c[0]) / dif.sum() if dif.sum() > 0 else 0.0
    net = (c[-1] - c[0]) / c[0] * 100.0
    rng = (sub["high"].to_numpy() - sub["low"].to_numpy())
    n_up = int((np.diff(c) > 0).sum())
    return {
        "bars": len(sub),
        "von": sub["ts"].iloc[0], "bis": sub["ts"].iloc[-1],
        "erst": c[0], "letzt": c[-1], "net_pct": net,
        "high": sub["high"].max(), "low": sub["low"].min(),
        "de": de, "up_pct": n_up / max(len(c) - 1, 1) * 100.0,
        "mean_abs": float(np.mean(np.abs(np.diff(c)) / c[:-1] * 100.0)),
        "max_bar_pct": float(np.max(np.abs(np.diff(c)) / c[:-1] * 100.0)),
        "sl_uberfahr": int((rng / sub["close"].to_numpy() * 100.0 >= 0.45).sum()),
    }


def phasen_im_fenster(a: datetime, b: datetime):
    """Phase_IDs, die [a,b) schneiden (Zeitbereich + OBEN/UNTEN fehlt hier)."""
    ids = sorted(pid for pid, p in phases.items()
                 if p["start"] < b and p["ende"] > a)
    return ids


def fmt_ts(t) -> str:
    return t.strftime("%d.%m. %H:%M")


out: list[str] = []
def o(*a): out.append(" ".join(str(x) for x in a))

o("=" * 100)
o("DD-EPISODEN-EXPLORATION S1 (READ-ONLY; Schritte 1-3)")
o("=" * 100)

# ---------------------------------------------------------------- Schritt 1: Episoden-Mapping
for label, (lo, hi) in (("EPISODE 2 (T119-T126, Verlustserie)", EP2),
                        ("EPISODE 1 (T132-T153, MaxDD)", EP1)):
    sel = [by_nr[n] for n in range(lo, hi + 1)]
    o("")
    o("-" * 100)
    o(f"SCHRITT 1 | {label}")
    o(f"{'Nr':>4} {'Phase':>5} {'BarSig':>6} {'BarEnt':>6} {'Zeit (UTC)':<14} {'Dir':<5} "
      f"{'Entry':>8} {'R':>7}")
    for t in sel:
        ts = ts_arr[t["bar_entry"]]
        o(f"{t['nr']:>4} {t['phase']:>5} {t['bar_sig']:>6} {t['bar_entry']:>6} "
          f"{fmt_ts(pd.Timestamp(ts)):<14} {t['dir']:<5} {t['entry']:>8.3f} {t['r']:>+7.2f}")
    phase_ids = sorted({t["phase"] for t in sel})
    o(f"  -> {len(sel)} Trades ueber {len(phase_ids)} verschiedene Phase_IDs: {phase_ids}")
    for pid in phase_ids:
        sub = [t for t in sel if t["phase"] == pid]
        p = phases.get(pid)
        if p:
            o(f"     Phase {pid}: {fmt_ts(p['start'])} -> {fmt_ts(p['ende'])} "
              f"({p['dauer_h']}h, {p['bars']}C) {p['marker']}  | {len(sub)} Trades: "
              + ", ".join(f"T{t['nr']} {t['dir']} {t['r']:+.2f}" for t in sub))
    nv = sum(1 for t in sel if t["r"] < 0)
    # Cluster-Mass: Verlusttrades je Phase
    o("  CLUSTER-AUDIT (Schritt 3): Verlusttrades je Phase:")
    for pid in phase_ids:
        sub = [t for t in sel if t["phase"] == pid and t["r"] < 0]
        if sub:
            o(f"     Phase {pid}: {len(sub)} Verlierer -> "
              + ", ".join(f"T{t['nr']} ({t['r']:+.2f}R)" for t in sub))

# ---------------------------------------------------------------- Schritt 2: Regime-Analyse
o("")
o("-" * 100)
o("SCHRITT 2 | REGIME-ANALYSE (M15, UTC; read-only)")
fenster = {
    "EP2-Fenster 03.06.-11.06.": (datetime(2026, 6, 3), datetime(2026, 6, 11)),
    "A: 16.06.-23.06. (Run-up/Peak T132)": (datetime(2026, 6, 16), datetime(2026, 6, 23)),
    "B: 23.06.-01.07. (SL-Cluster 1)": (datetime(2026, 6, 23), datetime(2026, 7, 1)),
    "C: 01.07.-10.07. (SL-Cluster 2)": (datetime(2026, 7, 1), datetime(2026, 7, 10)),
    "EP1 gesamt 16.06.-10.07.": (datetime(2026, 6, 16), datetime(2026, 7, 10)),
}
o(f"{'Fenster':<28} {'Bars':>5} {'Netto%':>7} {'DirEff':>7} {'Up%':>6} {'mean|d|':>7} "
  f"{'maxBar%':>7} {'High':>7} {'Low':>7} {'SL-Ueberfahr':>12}")
for name, (a, b) in fenster.items():
    s = regimestats(a, b)
    pids = phasen_im_fenster(a, b)
    o(f"{name:<28} {s['bars']:>5} {s['net_pct']:>+6.2f}% {s['de']:>6.2f} {s['up_pct']:>5.1f}% "
      f"{s['mean_abs']:>6.3f}% {s['max_bar_pct']:>6.2f}% {s['high']:>7.3f} {s['low']:>7.3f} "
      f"{s['sl_uberfahr']:>12}  | Phasen {pids}")
    # Tages-Schluesse als kompakte Sequenz
    sub = df[(df["ts"] >= a) & (df["ts"] < b)].copy()
    sub["tag"] = sub["ts"].dt.date
    daily = sub.groupby("tag")["close"].last()
    seq = " ".join(f"{d.strftime('%d.%m')}:{v:.1f}" for d, v in daily.items())
    o(f"{'':<28} Tages-Schluesse: {seq}")
o("")
o("Legende: DirEff (Richtungseffizienz) = |Netto|/Summe|Bar-Bewegung|; nahe 1 = Trend,")
o("nahe 0 = reiner Chop. SL-Ueberfahr = M15-Bars mit Spanne >= 0.45% (SL-Abstand).")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print(f"OK -> {OUT} ({len(out)} Zeilen)")
print("Phasen im Tableau:", len(phases), "| Trades:", len(trades))
