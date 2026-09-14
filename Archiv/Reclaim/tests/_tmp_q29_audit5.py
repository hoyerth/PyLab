# -*- coding: utf-8 -*-
"""READ-ONLY Q29-Audit v5: was leistet ein PHASEN-LOKALES Quartil (Option B)?

Probe: dieselbe Sperrlogik, aber der Bezugsbereich ist nicht die
Gesamtspanne 0..k (global), sondern
  (a) gleitendes Fenster der letzten N Bars,
  (b) der H2-Bereich ab bar 640,
  (c) die jeweils laufende Phase (PHASEN-Fenster aus dem Renderer).
Keine Engine-Aenderung, keine Datei wird geschrieben.
"""
from __future__ import annotations

import copy
import dataclasses
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

sys.argv = ["tmp_q29_audit5"]
voll = REN.read_text(encoding="utf-8")
_i = voll.index("import matplotlib")
mod = {"__name__": "renderer_q29audit5", "__file__": str(REN)}
sys.modules[mod["__name__"]] = type(sys)("renderer_q29audit5")
exec(compile(voll[:voll.rindex("\n", 0, _i) + 1], str(REN), "exec"), mod)

engine, ns, cfg, scan = mod["engine"], mod["ns"], mod["cfg"], mod["scan"]
DEFAULT_ADAPTER, box_end = mod["DEFAULT_ADAPTER"], mod["box_end"]
V1_basis = mod["V1_basis"]

A_HI = "        ex_hi = float(np.max(hi[:k + 1]))"
A_LO = "        ex_lo = float(np.min(lo[:k + 1]))"
psrc = mod["patched_src"]
assert psrc.count(A_HI) == 1 and psrc.count(A_LO) == 1

PHASEN = [(620, 673), (715, 792), (802, 840), (848, 1020), (1030, 1075),
          (1082, 1134), (1171, 1272)]


def _ph_start(k: int) -> int:
    """Letzter Phasenbeginn <= k (sonst 0) -- als Quelltext-Fragment."""
    s = 0
    for a, b in PHASEN:
        if a <= k:
            s = a
    return s


VARIANTEN = {
    "global 0..k (IST)":
        (A_HI, A_LO),
    "Fenster 100 Bars":
        ("        ex_hi = float(np.max(hi[max(0, k - 99):k + 1]))",
         "        ex_lo = float(np.min(lo[max(0, k - 99):k + 1]))"),
    "Fenster 250 Bars":
        ("        ex_hi = float(np.max(hi[max(0, k - 249):k + 1]))",
         "        ex_lo = float(np.min(lo[max(0, k - 249):k + 1]))"),
    "ab Bar 640 (H2)":
        ("        ex_hi = float(np.max(hi[max(0, min(640, k)):k + 1]))",
         "        ex_lo = float(np.min(lo[max(0, min(640, k)):k + 1]))"),
    "Phase (PHASEN-Fenster)":
        ("        _ps = _PHSTART[k]\n"
         "        ex_hi = float(np.max(hi[_ps:k + 1]))",
         "        ex_lo = float(np.min(lo[_ps:k + 1]))"),
}

_GATE_RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+"
                      r"basis=[\d.]+\s+sweep=([\d.]+)")


def lauf(hi_zeile: str, lo_zeile: str) -> tuple:
    src = (psrc.replace(A_HI, hi_zeile, 1).replace(A_LO, lo_zeile, 1))
    _ns = dict(engine.__dict__)
    _ns["_hook"] = DEFAULT_ADAPTER
    _ns["_Hook2ZielModus"] = mod["Hook2ZielModus"]
    _ns["_PHSTART"] = [_ph_start(k) for k in range(scan["n"])]
    exec(compile(src, "<se_trades_phase>", "exec"), _ns)
    _orig = engine._se_trades
    engine._se_trades = _ns["_se_trades"]
    try:
        V, st = engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = _orig
    return V, st


print("=== M) Q29-BEZUGSRAUM: GLOBAL vs. PHASEN-LOKAL (Adapter-Lauf v0.1) ===")
print(f"  Referenz IST: {len(V1_basis)} Trades / "
      f"{sum(t.r for t in V1_basis):+.6f} R  "
      f"| H2 {sum(1 for t in V1_basis if t.entry_bar >= box_end)}/"
      f"{sum(t.r for t in V1_basis if t.entry_bar >= box_end):+.6f} R")
kopf = (f"  {'Variante':24s} {'Trades':>6} {'R':>13} {'Sperren':>8} "
        f"{'H2-Tr':>6} {'H2-R':>12}")
print(kopf)
for name, (hz, lz) in VARIANTEN.items():
    V, st = lauf(hz, lz)
    h2 = [t for t in V if t.entry_bar >= box_end]
    print(f"  {name:24s} {len(V):6d} {sum(t.r for t in V):+13.6f} "
          f"{st['quartil_blockiert']:8d} {len(h2):6d} "
          f"{sum(t.r for t in h2):+12.6f}")

print("\n=== N) DETAIL Phase-Fenster-P9 (848..1020) ===")
V, st = lauf(*VARIANTEN["Phase (PHASEN-Fenster)"])
b = sorted(t.bar for t in V)
print(f"  Trades gesamt {len(V)}: {b}")
print(f"  P9-Fenster: "
      + " | ".join(f"K{t.kid}@{t.bar} {t.r:+.4f}"
                   for t in sorted(V, key=lambda x: x.bar)
                   if 848 <= t.bar <= 1020))
g = [m.group(1) for m in _GATE_RE.finditer("\n".join(st["quartil_liste"]))]
print(f"  Q29-Sperren: {st['quartil_blockiert']}")
