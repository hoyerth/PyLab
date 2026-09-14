# -*- coding: utf-8 -*-
"""READ-ONLY Audit der Mentor-H2-Mustertrades (Bar 980 / Bar 1020).

Prueft die Mentor-Angaben gegen die Rohdaten-CSV und die arretierte
Engine-Mechanik (kein Schreiben, keine Engine-Aenderung):
  1. OHLC der Signal-Bars 980, 991, 1020, 1030 (Mentor-Behauptungen)
  2. Welche Kante liefert den Reclaim bei 980 / 1020? (K67 vs K73)
  3. Entry-Semantik: k+1 (Mentor) vs. k+stufe_n (Engine)
  4. SL: Kerzen-Extrem ohne Puffer (Mentor) vs. +sl_buffer_usd (Engine)
  5. TP: Lower2 68.40 (Mentor) vs. aeusserste Gegenkante (Engine)
  6. Zielerreichung / realisiertes R in beiden Lesarten
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
CSV = ROOT / "test" / "archiv" / "silver_m15_ohlc_2026-08-10_2026-08-28.csv"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_m", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = len(scan["d"])
scan["box_end_bar"] = n
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
ts = d["ts"]

# --- CSV-Gegenprobe --------------------------------------------------------
csv = pd.read_csv(CSV, encoding="utf-8-sig")
print("=" * 124)
print("0) CSV-GEGENPROBE: Bar-Index-Alignment Engine <-> Rohdaten")
print("=" * 124)
print(f"  CSV-Zeilen={len(csv)} | Engine-Bars={n} | Delta={len(csv) - n}")
same = bool(np.allclose(csv["close"].to_numpy(dtype=float)[:n], cl))
print(f"  close identisch (erste {n} CSV-Zeilen): {same}")
print(f"  CSV ts[0]={csv['ts'].iloc[0]} | Engine ts[0]={ts.iloc[0]} "
      f"(Differenz = 2 h Berlin)")
print(f"  CSV ts[980]={csv['ts'].iloc[980]} | Engine ts[980]={ts.iloc[980]}")

# --- Mentor-Behauptungen ---------------------------------------------------
print("\n" + "=" * 124)
print("1) OHLC-CHECK der Mentor-Behauptungen (Engine-Index = CSV-Index)")
print("=" * 124)
beh = [
    (980, 69.899, 69.450, 69.560, "Trade 1 Signal-Kerze"),
    (991, None, 68.348, None, "Trade 1 Ziel-Touch (Lower2)"),
    (1020, 69.924, 69.650, 69.710, "Trade 2 Signal-Kerze"),
    (1030, None, 68.220, None, "Trade 2 Ziel-Touch"),
]
print(f"  {'bar':>5s} {'Zeit (UTC/CSV)':17s} {'open':>8s} {'high':>8s} "
      f"{'low':>8s} {'close':>8s}   Mentor-Aussage / Abgleich")
for b, mh, ml, mc, label in beh:
    ch, clow, cc = hi[b], lo[b], cl[b]
    checks = []
    if mh is not None:
        checks.append(f"High {mh:.3f} {'OK' if abs(ch - mh) < 1e-6 else f'ABWEICHUNG (ist {ch:.3f})'}")
    if ml is not None:
        checks.append(f"Low {ml:.3f} {'OK' if abs(clow - ml) < 1e-6 else f'ABWEICHUNG (ist {clow:.3f})'}")
    if mc is not None:
        checks.append(f"Close {mc:.3f} {'OK' if abs(cc - mc) < 1e-6 else f'ABWEICHUNG (ist {cc:.3f})'}")
    print(f"  {b:5d} {csv['ts'].iloc[b]:17s} {op[b]:8.3f} {ch:8.3f} "
          f"{clow:8.3f} {cc:8.3f}   {label}")
    for c in checks:
        print(f"        -> {c}")

# --- Kanten-Basen an den Signal-Bars ---------------------------------------
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
print("\n" + "=" * 124)
print("2) KANTEN-BASIS an den Signal-Bars (V3 kausal, arretiert)")
print("=" * 124)
print(f"  {'bar':>5s} " + " ".join(f"{f'K{k}':>9s}" for k in (67, 73, 77, 79)))
for b in (980, 991, 1020, 1030):
    row = " ".join(f"{by_kid[k].basis_bei(b):9.4f}" if k in by_kid else
                   f"{'-':>9s}" for k in (67, 73, 77, 79))
    print(f"  {b:5d} {row}")

# --- Welche Kante liefert Reclaim? ----------------------------------------
print("\n" + "=" * 124)
print("3) RECLAIM-SIGNALE an/um Bar 980 und 1020 (arretierte V3-Basis)")
print("=" * 124)
for k in (980, 981, 982, 1020, 1021, 1022):
    for kid in (67, 73, 77):
        e = by_kid.get(kid)
        if e is None:
            continue
        basis = e.basis_bei(k)
        st, name = engine._reclaim_stufe(e.seite, k, basis, hi, lo, cl, cfg)
        if st:
            print(f"  bar {k} {csv['ts'].iloc[k]:17s} K{kid:<3d} {e.seite:5s} "
                  f"basis={basis:8.4f} high={hi[k]:8.4f} close={cl[k]:8.4f} "
                  f"-> stufe={st} {name:16s} entry_bar(Engine)={k + st}")

# --- Entry / SL / TP in beiden Lesarten -----------------------------------
print("\n" + "=" * 124)
print("4) TRADE-MECHANIK: Mentor-Lesart vs. arretierte Engine-Lesart")
print("=" * 124)


def sim(k: int, kid: int, stufe: int, ziel: float, puffer: float,
        entry_semantik: str) -> dict:
    e = by_kid[kid]
    basis = e.basis_bei(k)
    eb = k + 1 if entry_semantik == "k+1" else k + stufe
    entry = float(op[eb])
    rb = eb - 1
    cluster = float(np.max(hi[k:rb + 1]))
    sl = cluster + puffer
    risk = abs(sl - entry)
    ziel_r = (entry - ziel) / risk
    # Zielerreichung
    hit = np.where(lo[eb:] <= ziel)[0]
    ziel_bar = int(eb + hit[0]) if len(hit) else -1
    # SL vor Ziel?
    sl_hit = np.where(hi[eb:] >= sl)[0]
    sl_bar = int(eb + sl_hit[0]) if len(sl_hit) else -1
    erreicht = ziel_bar >= 0 and (sl_bar < 0 or ziel_bar < sl_bar)
    real_r = ziel_r if erreicht else (-1.0 if sl_bar >= 0 else
                                      (entry - cl[-1]) / risk)
    return {"basis": basis, "eb": eb, "entry": entry, "cluster": cluster,
            "sl": sl, "risk": risk, "ziel_r": ziel_r, "ziel_bar": ziel_bar,
            "sl_bar": sl_bar, "erreicht": erreicht, "real_r": real_r}


def _fmt(r: dict) -> str:
    return (f"eb={r['eb']} entry={r['entry']:.3f} sl={r['sl']:.3f} "
            f"risk={r['risk']:.3f} CRV={r['ziel_r']:.2f}R "
            f"real={r['real_r']:+.2f}R")


for label, kw in (
    ("Mentor: k+1, SL ohne Puffer", dict(puffer=0.0, entry_semantik="k+1")),
    ("Mentor: k+1, SL +0.05", dict(puffer=0.05, entry_semantik="k+1")),
    ("Engine: k+stufe, SL +0.05", dict(puffer=0.05, entry_semantik="k+st")),
):
    r1 = sim(980, 73, 2, 68.400, kw["puffer"], kw["entry_semantik"])
    r2 = sim(1020, 73, 1, 68.400, kw["puffer"], kw["entry_semantik"])
    print(f"  {label:26s} | T1: {_fmt(r1)}")
    print(f"  {'':26s} | T2: {_fmt(r2)}")

print("\n" + "=" * 124)
print("5) DETAIL JE VARIANTE (Ziel 68.40 / SL-Varianten / Exit)")
print("=" * 124)
for k, stufe, name in ((980, 2, "Trade 1"), (1020, 1, "Trade 2")):
    print(f"\n  --- {name}: Signal-Bar {k} ({csv['ts'].iloc[k]}) auf K73")
    for puffer in (0.0, 0.05):
        for es in ("k+1", "k+st"):
            r = sim(k, 73, stufe, 68.400, puffer, es)
            print(f"    {es:4s} / SL-Puffer {puffer:.2f}: eb={r['eb']} "
                  f"({csv['ts'].iloc[r['eb']]}) entry={r['entry']:.3f} "
                  f"cluster={r['cluster']:.3f} sl={r['sl']:.3f} "
                  f"risk={r['risk']:.3f} ({r['risk'] / r['entry'] * 100:.3f}%) "
                  f"CRV={r['ziel_r']:.2f} R | Ziel-Bar={r['ziel_bar']} "
                  f"SL-Bar={r['sl_bar']} erreicht={r['erreicht']} "
                  f"realR={r['real_r']:+.2f}")

print("\n" + "=" * 124)
print("6) ZWISCHENTIEFS 980..1020 (Roadmap zum Ziel 68.40)")
print("=" * 124)
for b in range(980, 1032):
    if lo[b] <= 68.400:
        print(f"  erster Touch <= 68.400: bar {b} ({csv['ts'].iloc[b]}) "
              f"low={lo[b]:.3f}")
        break
for b in range(1020, 1040):
    if lo[b] <= 68.400:
        print(f"  ab Bar 1020 erster Touch <= 68.400: bar {b} "
              f"({csv['ts'].iloc[b]}) low={lo[b]:.3f}")
        break
