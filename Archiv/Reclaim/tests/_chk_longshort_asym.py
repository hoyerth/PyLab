# -*- coding: utf-8 -*-
"""READ-ONLY: Long/Short-Asymmetrie im V019-Motor (EXT).

Frage des Anwenders: Warum fast nur SHORTs und kaum LONGs -- auch in einem
permanenten Aufwaertstrend mit genuegend Bodenkanten?

Methode: engine-nativer Scan + Trade-Lauf auf EXT, dann
  1. Richtungsverteilung der Trades,
  2. Richtungsverteilung der blockierenden Gates (Q29 Quartil, Zyklus, M6),
  3. Nachbau der Q29-Formel ``_im_aussenquartil`` ueber ALLE Bars:
     Pass-Rate LONG vs. SHORT,
  4. Anker-Analyse: wo liegt ``ex_lo`` bzw. ``ex_hi`` (Fenster-Extremum)?
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ENGINE_PATH = ROOT / "test" / "tmp_kanten_engine_replay.py"
SHA_SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

sha = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
assert sha == SHA_SOLL, f"Fremd-Engine {sha[:16]}"
spec = importlib.util.spec_from_loader("ke_asym", loader=None)
eng = importlib.util.module_from_spec(spec)
eng.__file__ = str(ENGINE_PATH)
sys.modules["ke_asym"] = eng
exec(compile(ENGINE_PATH.read_text(encoding="utf-8"), str(ENGINE_PATH),
             "exec"), eng.__dict__)

eng.FENSTER["EXT"] = ("2026-08-03", "2026-09-12")
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("EXT", cfg)
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
scan["box_end_bar"] = n
setups, stats = eng._se_trades(scan, cfg)

print("=" * 74)
print("1) TRADES nach Richtung")
cnt = Counter(s.richtung for s in setups)
for r in ("SHORT", "LONG"):
    rr = [s for s in setups if s.richtung == r]
    print(f"   {r:6s}: {cnt.get(r,0):3d} Trades | Summe R "
          f"{sum(s.r for s in rr):+.6f}")

print("=" * 74)
print("2) BLOCKIERENDE GATES nach Richtung (aus stats-Listen)")


def _dir(s: str) -> str:
    if " LONG " in s:
        return "LONG"
    if " SHORT " in s:
        return "SHORT"
    return "?"


for key in ("quartil_liste", "zyklus_liste", "blocker_liste"):
    lst = stats.get(key) or []
    c = Counter(_dir(x) for x in lst)
    print(f"   {key:16s}: gesamt {len(lst):4d} | SHORT {c.get('SHORT',0):4d} | "
          f"LONG {c.get('LONG',0):4d}")
print(f"   {'quartil_blockiert':16s}: {stats.get('quartil_blockiert')}"
      f"   {'blocker':16s}: {stats.get('blocker')}"
      f"   {'zyklus_blockiert':16s}: {stats.get('zyklus_blockiert')}")

print("=" * 74)
print("3) Q29-Nachbau: Pass-Rate je Richtung ueber ALLE Bars")
q = float(cfg.quartil_distanz_pct)
ex_hi = np.maximum.accumulate(hi)
ex_lo = np.minimum.accumulate(lo)
spanne = ex_hi - ex_lo
with np.errstate(divide="ignore", invalid="ignore"):
    d_short = np.where(spanne > 0, (ex_hi - hi) / spanne * 100.0, 0.0)
    d_long = np.where(spanne > 0, (lo - ex_lo) / spanne * 100.0, 0.0)
pass_short = int(np.sum(d_short <= q))
pass_long = int(np.sum(d_long <= q))
print(f"   Q29-Grenze quartil_distanz_pct = {q:.1f} %")
print(f"   SHORT passierbar: {pass_short:5d} / {n} Bars = "
      f"{pass_short/n*100:5.1f} %")
print(f"   LONG  passierbar: {pass_long:5d} / {n} Bars = "
      f"{pass_long/n*100:5.1f} %")
print(f"   Median distanz SHORT {np.median(d_short):6.2f} % | "
      f"LONG {np.median(d_long):6.2f} %")

print("=" * 74)
print("4) Anker der Q29-Formel (Fenster-Extrema)")
b_hi = int(np.argmax(ex_hi))
b_lo = int(np.argmin(ex_lo))
print(f"   EX_LO (Fenster-Tief) = {ex_lo[-1]:.4f} erreicht bei Bar {b_lo} "
      f"(von {n})")
print(f"   EX_HI (Fenster-Hoch) = {ex_hi[-1]:.4f} erreicht bei Bar {b_hi} "
      f"(von {n})")
print(f"   Preis am Ende: close[-1] = {d['close'].iloc[-1]:.4f}")
print(f"   -> lo[k] liegt im Trend weit ueber ex_lo: "
      f"Median (lo - ex_lo)/spanne = {np.median(d_long):.2f} % > {q} %")

print("=" * 74)
print("5) Prioritaet im Motor: for richtung in ('SHORT','LONG') + Entry-Dedup")
dupes = 0
bars_seen = set()
for s in sorted(setups, key=lambda x: x.entry_bar):
    if s.entry_bar in bars_seen:
        dupes += 1
    bars_seen.add(s.entry_bar)
print(f"   Entry-Bars doppelt belegt: {dupes} (Dedup laesst nur den ERSTEN zu)")
print(f"   Loop-Reihenfolge: SHORT zuerst -> gleicher Entry-Bar: SHORT gewinnt")
print("=" * 74)
