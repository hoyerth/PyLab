# -*- coding: utf-8 -*-
"""AUG26: V0-Trades gegen die Transitionszonen (7.8. / 19.-21.8. / 28.8.)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("engine_t", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_t"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = scan["n"]
scan["box_end_bar"] = n
ts = list(scan["d"]["ts"])
S, st = engine._se_trades(scan, cfg)

# Transitionszonen (Trading-Day-Index * 92)
TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08",
        "12.08", "13.08", "14.08", "17.08", "18.08", "19.08", "20.08",
        "21.08", "24.08", "25.08", "26.08", "27.08", "28.08", "31.08"]


def tag(bar: int) -> str:
    i = bar // 92
    return f"{TAGE[i]} ({bar - i * 92:02d})" if i < len(TAGE) else "?"


ZONEN = [("7.8.-Transition", 368, 476),
         ("19.-21.8.-Transition", 1104, 1479),
         ("28.8.-Transition", 1748, 1904)]

print("=" * 100)
print("V0-TRADES GEGEN DIE TRANSITIONSZONEN (AUG26, n = 1932)")
print("=" * 100)
print(f"  {'#':<3}{'Entry':>6}{'Datum':<14}{'Richt':<7}{'Kid':>5}"
      f"{'R':>10}  {'Exit-Grund':<10}Zone")
for i, t in enumerate(sorted(S, key=lambda x: int(x.entry_bar)), 1):
    eb = int(t.entry_bar)
    z = next((nm for nm, a, b in ZONEN if a <= eb <= b), "-")
    print(f"  {i:<3}{eb:>6}{tag(eb):<14}{t.richtung:<7}K{int(t.kid):<4}"
          f"{float(t.r):>+10.4f}  {t.grund1 + '/' + t.grund2:<10}{z}")

print("\n" + "-" * 100)
print("BILANZ JE ZONE")
print("-" * 100)
for nm, a, b in [(f"ZONE {z} [{a}..{b}]", a, b) for z, a, b in ZONEN]:
    zs = [t for t in S if a <= int(t.entry_bar) <= b]
    print(f"  {nm:<34} {len(zs):>2} Trades  "
          f"Summe {sum(float(t.r) for t in zs):>+10.4f}  "
          f"Treffer {sum(1 for t in zs if float(t.r) > 0)}/{len(zs)}")
innen = [t for t in S if not any(a <= int(t.entry_bar) <= b
                                for _, a, b in ZONEN)]
print(f"  {'AUSSERHALB aller Transitionszonen':<34} {len(innen):>2} Trades  "
      f"Summe {sum(float(t.r) for t in innen):>+10.4f}  "
      f"Treffer {sum(1 for t in innen if float(t.r) > 0)}/{len(innen)}")
print(f"  {'GESAMT':<34} {len(S):>2} Trades  "
      f"Summe {sum(float(t.r) for t in S):>+10.4f}")

print("\n" + "-" * 100)
print("AB WELCHEM BAR WIRD DIE LOGIK TRAGFAEHIG? (kumulativ ab Entry 552 = 11.08.)")
print("-" * 100)
for schwelle in (200, 385, 476, 552, 644, 830, 1104):
    k = [t for t in S if int(t.entry_bar) >= schwelle]
    print(f"  ab Bar {schwelle:>5} ({tag(schwelle):<12}): "
          f"{len(k):>2} Trades  {sum(float(t.r) for t in k):>+10.4f}")

print("\n" + "-" * 100)
print("KOMBINATION: ab Schwelle UND ausserhalb aller Transitionszonen")
print("-" * 100)
for schwelle in (200, 385, 476, 552, 644):
    k = [t for t in S if int(t.entry_bar) >= schwelle
         and not any(a <= int(t.entry_bar) <= b for _, a, b in ZONEN)]
    tr = sum(1 for t in k if float(t.r) > 0)
    print(f"  ab Bar {schwelle:>5} ({tag(schwelle):<12}): {len(k):>2} Trades  "
          f"{sum(float(t.r) for t in k):>+10.4f}  "
          f"Treffer {tr}/{len(k)} "
          f"({100.0 * tr / len(k) if k else 0:.0f} %)")
print("\n" + "-" * 100)
print("VARIANTE: 7.8.-Zone bis Bar 552 gestreckt (Anwender-These 'ab 11.08.')")
print("-" * 100)
ZONEN2 = [("7.8.-Transition (gestreckt)", 368, 551),
          ("19.-21.8.-Transition", 1104, 1479),
          ("28.8.-Transition", 1748, 1904)]
zz = [t for t in S if any(a <= int(t.entry_bar) <= b for _, a, b in ZONEN2)]
aa = [t for t in S if not any(a <= int(t.entry_bar) <= b
                             for _, a, b in ZONEN2)]
print(f"  in Zonen      : {len(zz):>2} Trades  "
      f"{sum(float(t.r) for t in zz):>+10.4f}  "
      f"Treffer {sum(1 for t in zz if float(t.r) > 0)}/{len(zz)}")
print(f"  ausserhalb    : {len(aa):>2} Trades  "
      f"{sum(float(t.r) for t in aa):>+10.4f}  "
      f"Treffer {sum(1 for t in aa if float(t.r) > 0)}/{len(aa)}")
print(f"  SL-Trades in Zonen     : "
      f"{sum(1 for t in zz if float(t.r) <= -0.999)}/{len(zz)}")
print(f"  SL-Trades ausserhalb   : "
      f"{sum(1 for t in aa if float(t.r) <= -0.999)}/{len(aa)}")
print("ENDE")
