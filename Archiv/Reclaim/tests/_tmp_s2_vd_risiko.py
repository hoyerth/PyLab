# -*- coding: utf-8 -*-
"""Risiko-Analyse der S2-H2-Trades (offline, kein Engine-Lauf).

Rekonstruiert SL/Risk aus dem Kanten-Engine-Idiom
``sl = max(hi[k:entry]) + sl_buffer_usd`` (SHORT) bzw. ``min(lo[...]) - buffer``
und ordnet jeder Zeile der Detail-Ausgabe ihr Risiko zu.
"""
from __future__ import annotations

import importlib.util
import pickle
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg = eng.StraightEdgeHarnessKonfiguration()

scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
op = d["open"].to_numpy(float)

PAT = re.compile(
    r"\s*(\d+)\s+(\d+)\s+(SHORT|LONG)\s+K(\d+)\s*\|\s*([\d.]+)\s*([+-][\d.]+)"
    r"\s*\|\s*([\d.]+)\s*([+-][\d.]+)\s*\|\s*([+-][\d.]+)")
rows = []
txt = (ROOT / "test" / "_tmp_s2_vd_detail_out.txt").read_text(encoding="utf-8")
for ln in txt.splitlines():
    m = PAT.match(ln)
    if m:
        rows.append((int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)),
                     float(m.group(5)), float(m.group(6)), float(m.group(7)),
                     float(m.group(8)), float(m.group(9))))

print(f"sl_buffer_usd   = {cfg.sl_buffer_usd}")
print(f"tp1_anteil_pct  = {cfg.tp1_anteil_pct}")
print(f"H2-Trades geparst = {len(rows)}")
print("")
hdr = (f"{'entry':>6}{'bar':>6}{'kid':>5}{'sl':>10}{'entry_px':>10}"
       f"{'risk':>10}{'risk%':>8}{'R_base':>10}{'R_vd':>11}{'tp2_dist':>10}")
print(hdr)
print("-" * len(hdr))
for (eb, k, ri, kid, tb, rb, tv, rv, dr) in sorted(rows, key=lambda r: -abs(r[7])):
    if ri == "SHORT":
        sl = float(hi[k:eb].max()) + cfg.sl_buffer_usd
    else:
        sl = float(lo[k:eb].min()) - cfg.sl_buffer_usd
    ep = float(op[eb])
    risk = abs(sl - ep)
    print(f"{eb:>6}{k:>6}{kid:>5}{sl:>10.4f}{ep:>10.4f}{risk:>10.5f}"
          f"{risk / ep * 100:>8.3f}{rb:>+10.4f}{rv:>+11.4f}{abs(ep - tv):>10.4f}")

print("")
klein = [r for r in rows if abs(float(op[r[0]]) -
                                (float(hi[r[1]:r[0]].max()) + cfg.sl_buffer_usd)
                                if r[2] == "SHORT" else 0.0) < 0.02]
print("Trades mit risk < 0.02 USD (degeneriert):")
for (eb, k, ri, kid, tb, rb, tv, rv, dr) in rows:
    if ri == "SHORT":
        sl = float(hi[k:eb].max()) + cfg.sl_buffer_usd
    else:
        sl = float(lo[k:eb].min()) - cfg.sl_buffer_usd
    ep = float(op[eb])
    if abs(sl - ep) < 0.02:
        print(f"   entry {eb} bar {k} K{kid} risk={abs(sl - ep):.5f} "
              f"R_base={rb:+.4f} R_vd={rv:+.4f}")
