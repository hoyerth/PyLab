# -*- coding: utf-8 -*-
"""READ-ONLY: OHLC-Vermessung an den vom Anwender benannten Marken."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_ohlc", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
d = scan["d"]
ts = d["ts"].tolist()
hi, lo = d["high"].tolist(), d["low"].tolist()
op, cl = d["open"].tolist(), d["close"].tolist()
n = scan["n"]


def zeige(bars, titel):
    print(f"--- {titel} ---")
    print("  bar   ts(engine)            open     high     low      close")
    for b in bars:
        if 0 <= b < n:
            print(f"  {b:4d}  {ts[b]}  {op[b]:.4f}  {hi[b]:.4f}  "
                  f"{lo[b]:.4f}  {cl[b]:.4f}")
    print()


# K73-Touches (engine-Pivots) und die 1:1-Marken derselben Uhrzeit
zeige([1112, 1113, 1114, 1115, 1121, 1122, 1123],
      "K73-Kandidat 26.8.: bar 1114 (ts 04:30) vs Pivot 1122 (ts 06:30)")
zeige([1202, 1203, 1204, 1210, 1211, 1212],
      "K73-Kandidat 27.8. 3:45: bar 1203 (ts 03:45) vs Pivot 1211 (ts 05:45)")
zeige([1263, 1264, 1265, 1271, 1272, 1273],
      "K73-Kandidat 27.8. 19:00: bar 1264 (ts 19:00) vs Pivot 1272 (ts 21:00)")

# K82-Touches
zeige([1030, 1031, 1032, 1055, 1056, 1057], "K82 Pivots 1031 / 1056")
zeige([1063, 1064, 1071, 1072, 1073, 1075],
      "K82-Kandidat 25.8. 15:00-15:45: bar 1064/1067 (ts 15:00/15:45) und "
      "bar 1072 (ts 17:00)")
zeige([1163, 1164, 1171, 1172, 1173], "K82 26.8. 17:00: bar 1164 vs Pivot 1172")
zeige([1250, 1251, 1258, 1259, 1260], "K82 27.8. 15:45: bar 1251 vs Pivot 1259")

print("--- Kandidaten fuer das Zielniveau 69.62 (K73) und 67.6 (K82) ---")
k73 = [69.7150, 69.6380, 69.6840, 69.7090, 69.6110, 69.7140]
print("  K73 alle wicks           :", k73)
print("  K73 letzte 3             :", k73[-3:], "mean",
      sum(k73[-3:]) / 3)
print("  K73 letzte 3 ohne 1211   :", [k73[3], k73[5]], "mean",
      sum([k73[3], k73[5]]) / 2)
print("  K73 min(letzte 3)        :", min(k73[-3:]))
print("  K73 min(letzte 3) gerundet:", round(min(k73[-3:]), 2))
print("  K73 min(letzte 3) auf 0.02:", round(min(k73[-3:]) * 50) / 50)
k82 = [67.5350, 67.5530, 67.4940, 67.6000]
print("  K82 alle wicks           :", k82, "| mean", sum(k82) / 4,
      "| letzter", k82[-1], "| max", max(k82))
sys.exit(0)
