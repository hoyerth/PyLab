# -*- coding: utf-8 -*-
"""E-34n/5 — "Jede der 4 Bars als Long-Reclaim": read-only Gegenrechnung.

Der Anwender sieht im Fenster 1072..1075 vier aufeinanderfolgende Tests der
Kante K82 und haelt jeden fuer einen moeglichen Long-Reclaim. Hier wird
gemessen, was jede der vier Bars als eigenstaendiger Long ergeben haette —
mit der Engine-eigenen Trade-Aufloesung (POC + _c_loese_trade), nicht mit
einer Naeherung.

Annahmen (transparent):
  * Entry  = open[reclaim_bar + 1]   (Stufe-1-in-Bar = Entry am Folgebaren)
  * SL     = min(low[k : reclaim_bar + 1]) - sl_buffer_usd   (Engine-Regel)
  * POC    = berechne_kausalen_histogramm_poc(d, 0, k, basis, ziel, num_bins)
  * TP2    = Segmentziel (A1/A2) des Adapters
Kein Schreiben; Ausgabe stdout.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019  # noqa: E402

spec = importlib.util.spec_from_loader("ke_e34n5", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ROOT / "test" / "tmp_kanten_engine_replay.py")
sys.modules["ke_e34n5"] = eng
exec(compile((ROOT / "test" / "tmp_kanten_engine_replay.py").read_text(
    encoding="utf-8"), "k", "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
d = scan["d"]
ts = d["ts"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
k82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
           if int(e.kid) == 82)
SEG = ADAPTER_V019.segmente
seg_a1 = SEG[1]
ZIEL_A1 = float(seg_a1.ziel_preis_long)


def _zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m. %H:%M")


print("=" * 116)
print("E-34n/5  DIE VIER BARS 1072..1075 ALS EIGENSTAENDIGER LONG (read-only)")
print("=" * 116)
print(f"K82 statische basis={float(k82.basis):.4f} | "
      f"A1-Segmentziel (LONG)={ZIEL_A1:.4f} | "
      f"sl_buffer={cfg.sl_buffer_usd} | tp1_anteil={cfg.tp1_anteil_pct}%")
print(f"{'bar':>5} {'BKZ':>12} {'basis_bei':>9} {'dist%':>6} {'Stufe':>6} "
      f"{'e_bar':>6} {'entry':>8} {'sl':>8} {'risk':>6} {'poc':>8} "
      f"{'g1':>5} {'g2':>5} {'r':>9}")

for k in (1072, 1073, 1074, 1075):
    b = float(k82.basis_bei(k))
    dist = (b - lo[k]) / b * 100.0
    st_n, st_nm = eng._reclaim_stufe("UNTEN", k, b, hi, lo, cl, cfg)
    # Erzwungener In-Bar-Reclaim (Hypothese des Anwenders)
    st_n_eff = st_n if st_n > 0 else 1
    e_bar = k + st_n_eff
    entry = float(op[e_bar])
    rb = e_bar - 1
    sl = float(lo[k:rb + 1].min()) - cfg.sl_buffer_usd
    poc = eng.berechne_kausalen_histogramm_poc(
        d, 0, k, b, ZIEL_A1, cfg.num_bins)
    tr = eng._c_loese_trade(hi, lo, cl, e_bar, entry, "LONG", sl, poc,
                            ZIEL_A1, cfg.tp1_anteil_pct)
    print(f"{k:>5} {_zeit(k):>12} {b:>9.4f} {dist:>6.3f} "
          f"{str(st_n) + '/' + ('INBAR' if st_n_eff == 1 else str(st_n_eff)):>6} "
          f"{e_bar:>6} {entry:>8.4f} {sl:>8.4f} {abs(sl - entry):>6.4f} "
          f"{poc:>8.4f} {tr.grund1:>5} {tr.grund2:>5} {tr.r_mult:>+9.4f}")

print("\n" + "=" * 116)
print("REALER LAUF: Ein-Eintrag-Dedup (entry_bar) und 12-Bar-Zyklus")
print("=" * 116)
print("  K62@1075 -> Stufe 2 (KERZE_2) -> entry_bar = 1077 (real: r=+1.4758)")
print("  1072..1074 wuerden alle auf entry_bar 1073/1074/1075 zeigen;")
print("  die Engine hat sie nie erreicht, weil _kandidat bei 1072..1074")
print("  den AUSSEN-Blocker K85/K82 (unerreichte Aussenwand) bediente.")
print("  K82.letzter_sweep_bar bleibt 1056 -> F3-Frische sperrt 1072..1074")
print("  zusaetzlich.")
print("\nENDE E-34n/5")
