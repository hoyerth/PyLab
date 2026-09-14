# -*- coding: utf-8 -*-
"""READ-ONLY: Exploration H2-Reststrecke ab P10-Einstieg (25.08. ~03:00).

Ziel: Ist-Zustand der Generation V017 im Fenster P10 (ab Bar 1021) bis
Datenende erheben -- Kantenlagen K73/K82, kausale Verlaeufe, Trades,
Sperren (Q29/M6) -- und die avisierten Sicht-Trades des Anwenders verorten.

Es wird NICHTS geschrieben und NICHTS geaendert; ausgefuehrt wird der
Renderer-Kopf (alles vor dem Plot-Teil), damit Scan/Patch/Asserts identisch
zum Produktionslauf sind. Keine PNG.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
_HOLD: List[object] = []

mod = types.ModuleType("explo_h2rest")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old_argv, _old_out = sys.argv, sys.stdout
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
try:
    exec(compile(HEAD, "<head_explo>", "exec"), ns)
finally:
    _HOLD.append(sys.stdout)
    sys.stdout = _old_out
    sys.argv = _old_argv

import pandas as pd  # noqa: E402

d = ns["scan"]["d"]
n = ns["n"]
ts = pd.to_datetime(d["ts"])
op = d["open"].to_numpy(dtype=float)
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
edges = ns["scan"]["edges"] + ns["scan"]["seeds"]
BY = {e.kid: e for e in edges}
V1 = ns["V1"]
st1 = ns["st1"]

BARS = {"1031": 1031, "1056": 1056, "1072": 1072, "1075": 1075, "1122": 1122,
        "1172": 1172, "1211": 1211, "1259": 1259, "1272": 1272}

print("=" * 104)
print("ZEITBASIS (Wanduhr ohne Offset) -- Abgleich der Anwendermarken")
print("=" * 104)
for lbl, b in sorted(BARS.items(), key=lambda kv: kv[1]):
    print(f"  Bar {b:<5} {ts.iloc[b]:%d.%m.%Y %H:%M}  "
          f"O {op[b]:.4f} H {hi[b]:.4f} L {lo[b]:.4f} C {cl[b]:.4f}")

print("\n" + "=" * 104)
print("RANDFENSTER: letzter Bar und P10-Beginn")
print("=" * 104)
print(f"  n={n} -> letzter Bar {n - 1} = {ts.iloc[n - 1]:%d.%m.%Y %H:%M}")
print(f"  P10 1030-1075 | P11 1082-1134 | P12 1171-1272 | Luecke ab 1273")
print(f"  box_end = {ns['box_end']}")

print("\n" + "=" * 104)
print("KANTENLAGE: K73 (Upper2/Decke) UND K82 (Lower3/Boden)")
print("=" * 104)
for kid in (73, 82):
    e = BY[kid]
    print(f"\n  K{kid}  seite={e.seite}  Provenienz e.basis={e.basis:.4f}  "
          f"prim_anker={e.ist_prim_anker}  geburt={e.geburts_bar}")
    print(f"       Wicks ({len(e.wicks)}):")
    for b, p in e.wicks:
        print(f"         Bar {b:<5} {ts.iloc[b]:%d.%m.%Y %H:%M}  "
              f"Preis {p:.4f}")
    print(f"       kausal basis_bei: "
          f"1021={e.basis_bei(1021):.4f}  1075={e.basis_bei(1075):.4f}  "
          f"1122={e.basis_bei(1122):.4f}  1259={e.basis_bei(1259):.4f}  "
          f"1287={e.basis_bei(n - 1):.4f}")

print("\n" + "=" * 104)
print("KANDIDATEN-NACHBARSCHAFT im Boden-/Deckenband (P10..P12)")
print("=" * 104)
for e in sorted(edges, key=lambda x: x.kid):
    if not (1010 <= max(b for b, _ in e.wicks)):
        continue
    if e.kid in (67, 73, 77, 82):
        mark = "  <== ZIEL"
    else:
        mark = ""
    print(f"  K{e.kid:<3} {e.seite:<5} basis {e.basis:.4f}  "
          f"kausal(1287) {e.basis_bei(n - 1):.4f}  "
          f"wicks {len(e.wicks)} @ {[b for b, _ in e.wicks]}{mark}")

print("\n" + "=" * 104)
print("TRADES V017 im Fenster ab Bar 1020")
print("=" * 104)
for t in sorted((x for x in V1 if x.bar >= 1020), key=lambda x: x.bar):
    print(f"  K{t.kid:<3} signal {t.bar:<5} {ts.iloc[t.bar]:%d.%m %H:%M}  "
          f"entry_bar {t.entry_bar:<5} {t.richtung:<5} {t.stufe:<14} "
          f"entry {t.entry:.4f} sl {t.sl:.4f} tp2 {t.tp2:.4f} r {t.r:+.6f}")

print("\n" + "=" * 104)
print("SPERREN (Q29 / M6) im Fenster ab Bar 1020")
print("=" * 104)
import re  # noqa: E402

RE = re.compile(r"bar\s+(\d+)\s+(SHORT|LONG)\s+K\s*(\d+)\s+basis=([\d.]+)"
                r"\s+sweep=([\d.]+)")
for lbl, key in (("Q29-Quartil", "quartil_liste"), ("M6-Aussenwand", "blocker_liste")):
    roh = list(st1.get(key) or [])
    treffer = []
    for s in roh:
        m = RE.search(s)
        if m and int(m.group(1)) >= 1020:
            treffer.append((int(m.group(1)), m.group(2), int(m.group(3)),
                            float(m.group(4)), float(m.group(5)), s))
    print(f"\n  {lbl}: {len(treffer)} Sperren ab Bar 1020 "
          f"(gesamt {len(roh)})")
    for b, r, k, basis, sw, org in sorted(treffer):
        print(f"    Bar {b:<5} {ts.iloc[b]:%d.%m %H:%M} {r:<5} K{k:<3} "
              f"basis={basis:.4f} sweep={sw:.4f}")
        print(f"        {org}")

print("\n" + "=" * 104)
print("TAGESPROFIL 25.-27.08. (Extraktion fuer die Sichtmarken)")
print("=" * 104)
maske = (ts >= "2026-08-25") & (ts < "2026-08-28")
idx = [i for i in range(n) if maske.iloc[i]]
print(f"  Bars {idx[0]}..{idx[-1]} ({len(idx)} Bars)")
print(f"  Hoch  {max(hi[idx]):.4f} @ Bar {idx[int(max(range(len(idx)), key=lambda j: hi[idx[j]]))]}"
      f"  |  Tief {min(lo[idx]):.4f} @ "
      f"Bar {idx[int(min(range(len(idx)), key=lambda j: lo[idx[j]]))]}")
for i in idx:
    if ts.iloc[i].strftime("%H:%M") in ("03:45", "04:30", "04:45", "11:00",
                                        "15:00", "15:45", "17:00", "19:00"):
        print(f"    Bar {i:<5} {ts.iloc[i]:%d.%m %H:%M} "
              f"O {op[i]:.4f} H {hi[i]:.4f} L {lo[i]:.4f} C {cl[i]:.4f}")
print("=" * 104)
