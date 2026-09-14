# -*- coding: utf-8 -*-
"""FORENSIK: (1) DB-Zeittyp/Session-TZ vs. Wanduhr  (2) Lookahead Bar 564.

Read-only. Keine Engine-Aenderung.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

import duckdb                                            # noqa: E402
import numpy as np                                       # noqa: E402
import pandas as pd                                      # noqa: E402

con = duckdb.connect(str(ROOT / "data" / "market_data.duckdb"), read_only=True)
print("=" * 100)
print("1) DB-ZEITTYP & SESSION-ZEITZONE")
print("=" * 100)
print(con.execute("DESCRIBE ohlcv_bars").fetchdf().to_string(index=False))
print()
print("current_setting timezone:",
      con.execute("SELECT current_setting('TimeZone')").fetchone())
print()
for expr, label in (("time", "SELECT time (roh)"),
                    ("time AT TIME ZONE 'UTC'", "AT TIME ZONE 'UTC'"),
                    ("time AT TIME ZONE 'Europe/Berlin'",
                     "AT TIME ZONE 'Europe/Berlin'")):
    q = (f"SELECT {expr} AS v FROM ohlcv_bars "
         "WHERE symbol='SILVER' AND timeframe='M15' "
         "AND time = TIMESTAMPTZ '2026-08-18 03:15:00+02:00'")
    r = con.execute(q).fetchone()
    print(f"  {label:30s} -> {r[0]!r}")
con.close()

print()
print("=" * 100)
print("2) LOOKAHEAD-AUDIT BAR 564 (SHORT, K20, Entry 565, +15,93 R)")
print("=" * 100)
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_loader("ke_audit", loader=None)
mod = importlib.util.module_from_spec(spec)              # type: ignore[arg-type]
mod.__file__ = str(P)
sys.modules["ke_audit"] = mod
exec(compile(P.read_text(encoding="utf-8"), str(P), "exec"), mod.__dict__)

cfg = mod.StraightEdgeHarnessKonfiguration()
sc = mod._se_scan("AUG", cfg)
sc["box_end_bar"] = sc["n"]
tr, st = mod._se_trades(sc, cfg)
t564 = [t for t in tr if t.bar == 564][0]
print(f"  Setup: bar={t564.bar} K{t564.kid} {t564.richtung} "
      f"reclaim={t564.reclaim_bar} entry={t564.entry_bar} "
      f"E={t564.entry:.3f} SL={t564.sl:.3f} POC/TP1={t564.poc:.3f} "
      f"TP2={t564.tp2:.3f} R={t564.r:+.2f}")

d = sc["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
n = sc["n"]

# Welche Kanten existieren bei k=564 (Pivot+2 <= k+1) und welche Gegenkante
# wuerde _gegenkante liefern?
print()
print("  UNTEN-Kanten bei k=564 (Pivot+2 <= 565), sortiert nach basis_bei(564):")
alle = list(sc["edges"]) + list(sc["seeds"])
for e in sorted([e for e in alle if e.seite == "UNTEN"],
                key=lambda x: x.basis_bei(564)):
    ok_exist = e.erster_pivot_bar + 2 <= 565
    ok_touch = e.touch_conf(564) >= 2
    ok_anker = e.ist_prim_anker and 564 >= e.promoviert_ab_bar
    mark = "IM POOL" if (ok_exist and (ok_touch or ok_anker)) else "-"
    print(f"    K{e.kid:3d} basis_bei(564)={e.basis_bei(564):7.3f} "
          f"geburts_bar={e.geburts_bar:4d} erster_pivot={e.erster_pivot_bar:4d} "
          f"touch_conf(564)={e.touch_conf(564)} anker={e.ist_prim_anker} "
          f"promo_ab={e.promoviert_ab_bar} -> {mark}")

# Was waere die Gegenkante gewesen?
geg = None
pool = [e for e in alle if e.seite == "UNTEN"
        and e.erster_pivot_bar + 2 <= 564 + 1
        and ((e.ist_prim_anker and 564 >= e.promoviert_ab_bar)
             or e.touch_conf(564) >= 2)]
if pool:
    geg = min(pool, key=lambda e: e.basis_bei(564))
print()
print(f"  _gegenkante(564) -> K{geg.kid} basis_bei(564)={geg.basis_bei(564):.3f}"
      if geg else "  _gegenkante(564) -> None")

# TP2 = gegen_basis; ist sie zum Entry-Zeitpunkt bekannt?
print()
print(f"  TP2 im Trade = {t564.tp2:.3f}  (gegen_basis bei k=564)")
# Wann wurde die TP2-Kante geboren / erster Pivot?
for e in alle:
    if e.seite == "UNTEN" and abs(e.basis_bei(564) - t564.tp2) < 1e-9:
        print(f"  TP2-Kante = K{e.kid}: geburts_bar={e.geburts_bar} "
              f"erster_pivot_bar={e.erster_pivot_bar} "
              f"wicks={e.wicks[:6]}{'...' if len(e.wicks) > 6 else ''}")
        print(f"    -> Pivot+2 = {e.erster_pivot_bar + 2} "
              f"(bestaetigt {'VOR' if e.erster_pivot_bar + 2 <= 565 else 'NACH'}"
              f" dem Entry-Bar 565)")

# --- TATSAECHLICHER Exit-Pfad -------------------------------------------
print()
print("  Exit-Pfad ab Entry 565 (TP1-Anteil 25%, TP2 75%):")
print(f"    SL={t564.sl:.3f} TP1={t564.poc:.3f} TP2={t564.tp2:.3f}")
ex1 = t564.exit1_bar
print(f"    exit1_bar={ex1} exit2_bar={t564.exit2_bar} "
      f"grund1={t564.grund1} resultat={t564.resultat}")
for i in range(565, min(600, n)):
    mark = ""
    if hi[i] >= t564.poc:
        mark += " TP1-beruehrt"
    if lo[i] <= t564.sl:
        mark += " SL-beruehrt"
    if lo[i] <= t564.tp2:
        mark += " TP2-beruehrt"
    if mark:
        print(f"    bar {i:4d} h={hi[i]:.3f} l={lo[i]:.3f} c={cl[i]:.3f}{mark}")
        if i > (t564.exit2_bar or i) + 2:
            break
print(f"    Fenster-Ende n={n}")

# --- PRAEFIX-TRUNKATION: kausaler Nachweis -------------------------------
print()
print("  PRAEFIX-TRUNKATION (Goldstandard): Scan nur bis Bar 566, "
      "dann Trade-Bar 564 pruefen.")
sc2 = mod._se_scan("AUG", cfg, )
# _se_scan nimmt kein max_bar -> manuell kappen
for key in ("d",):
    sc2[key] = sc2[key].iloc[:567].reset_index(drop=True)
sc2["n"] = 567
sc2["box_end_bar"] = 567
# Kanten auf die bei Bar 566 bekannte Informationsmenge kappen
for e in list(sc2["edges"]) + list(sc2["seeds"]):
    e.wicks = [(b, p) for b, p in e.wicks if b + 2 <= 566]
tr2, st2 = mod._se_trades(sc2, cfg)
m2 = [t for t in tr2 if t.bar == 564]
if m2:
    t2 = m2[0]
    print(f"    gekappt: bar={t2.bar} E={t2.entry:.3f} SL={t2.sl:.3f} "
          f"TP1={t2.poc:.3f} TP2={t2.tp2:.3f} R={t2.r:+.2f}")
    print(f"    Delta zu Voll-Lauf: TP2 {t2.tp2 - t564.tp2:+.3f} | "
          f"SL {t2.sl - t564.sl:+.3f} | TP1 {t2.poc - t564.poc:+.3f} | "
          f"R {t2.r - t564.r:+.2f}")
else:
    print("    Trade 564 existiert im gekappten Lauf NICHT")
