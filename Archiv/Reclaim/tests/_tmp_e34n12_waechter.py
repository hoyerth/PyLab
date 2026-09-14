# -*- coding: utf-8 -*-
"""E-34n/12 — Geometrie-Waechter: welcher Assert-Satz ist TRAGEND? (read-only)

Prueft, welche Bars ueberhaupt in die Zaehlung `touch_conf(1075)` eingehen.
`touch_conf(k)` zaehlt Dochte mit `b + 2 <= k` -> fuer k = 1075 sind das
alle Dochte bis Bar **1073**. Ein Docht an 1074 oder 1075 erhoeht
`touch_conf(1075)` NICHT.

Daraus folgt fuer den Waechter: tragend sind 1072 UND 1073, nicht 1074.
Der Entwurf des Anwenders (nur 1073/1074/1075) hat eine Luecke bei 1072.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import ADAPTER_V019  # noqa: E402

ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"

spec = importlib.util.spec_from_loader("ke_e34n12", loader=None)
eng = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
eng.__file__ = str(ENG)
sys.modules["ke_e34n12"] = eng
exec(compile(ENG.read_text(encoding="utf-8"), str(ENG), "exec"), eng.__dict__)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
assert int(scan["box_end_bar"]) == 644
LOW = scan["d"]["low"].to_numpy(dtype=float)

SEG = ADAPTER_V019.segmente
A1 = SEG[1]
S0, S1 = int(A1.start_bar), int(A1.end_bar)
K82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
           if int(e.kid) == int(A1.boden.kid))

BAND = cfg.touch_band_pct
UEB = cfg.max_sweep_ueberdehnung_pct
K1152 = 1075

print("=" * 118)
print("E-34n/12  GEOMETRIE-WAECHTER: welche Bars sind TRAGEND? — read-only")
print("=" * 118)
print(f"Engine   {ENG.name} | A1 {S0}..{S1} | Segmentwand K{K82.kid} "
      f"| Band {BAND} | Ueberdehnung (cfg) {UEB}")
print(f"K82-Basisdaten: wicks={[b for b, _ in K82.wicks]} | statische .basis="
      f"{float(K82.basis):.4f}")

B0S = float(K82.basis_bei(S0))
print(f"\nb0 = basis_bei(seg.start_bar={S0}) = {B0S:.4f}   <- TRAGENDE Wahl")

print("\n" + "=" * 118)
print("1) ZAEHLWEITE von touch_conf(k) = Dochte mit b + 2 <= k")
print("=" * 118)
for _k in (1075, 1076, 1077):
    print(f"  touch_conf({_k}) zaehlt Dochte bis Bar {_k - 2}  ->  "
          f"{[b for b, _ in K82.wicks if b + 2 <= _k]}")
print("  Folgerung: ein Docht an 1074/1075 erhoeht touch_conf(1075) NICHT;")
print("             tragend sind ausschliesslich Dochte an <= 1073.")

print("\n" + "=" * 118)
print("2) ABSTANDS-MATRIX je b0-Kandidat (d %; tragend markiert)")
print("=" * 118)
KAND = (("(a) basis_bei(seg.start_bar)", B0S),
        ("(b) statische .basis", float(K82.basis)),
        ("(c) basis_bei(1072)", float(K82.basis_bei(1072))))
print(f"  {'b0':>10} {'Kennung':<26} " + " ".join(
    f"{f'bar{b}':>13}" for b in (1072, 1073, 1074, 1075)))
for _lab, _b0 in KAND:
    _z = []
    for _b in (1072, 1073, 1074, 1075):
        _d = (_b0 - float(LOW[_b])) / _b0 * 100.0
        _trag = "tragend" if _b + 2 <= 1075 else "neutral"
        _mk = "D" if _d > BAND else "r"
        _z.append(f"{_d:>8.4f}{_mk}/{_trag[:4]}")
    print(f"  {_b0:>10.4f} {_lab:<26} " + " ".join(_z))

print("\n" + "=" * 118)
print("3) WAECHTER-VERDIKT: Entwurf (ohne 1072)  vs  korrigiert (mit 1072)")
print("=" * 118)
print("  Entwurf: 1073<=Band  UND  1074<=Band  UND  1075>Band")
print("  Korrig.: 1072<=Band  UND  1073<=Band  UND  1074<=Band  UND  1075>Band")
for _lab, _b0 in KAND:
    _d = {b: (_b0 - float(LOW[b])) / _b0 * 100.0 for b in (1072, 1073, 1074, 1075)}
    _entwurf = (_d[1073] <= BAND) and (_d[1074] <= BAND) and (_d[1075] > BAND)
    _korr = (_d[1072] <= BAND) and (_d[1073] <= BAND) and (_d[1074] <= BAND) \
        and (_d[1075] > BAND)
    _mech = sum(1 for b in (1072, 1073, 1074) if _d[b] > BAND)
    print(f"\n  {_lab:<26} b0={_b0:.4f}")
    print(f"    d(1072)={_d[1072]:+.4f} d(1073)={_d[1073]:+.4f} "
          f"d(1074)={_d[1074]:+.4f} d(1075)={_d[1075]:+.4f}")
    print(f"    zusaetzliche vorzeitige Dochte (b+2<=1075): {_mech}"
          f"  -> touch_conf(1075) = 2 + {_mech} = {2 + _mech}")
    print(f"    Entwurf : {'PASS' if _entwurf else 'FAIL'}"
          f"   (fehlgeschlagen fuer 1072: "
          f"{'ja' if not _korr and _entwurf else 'nein'})")
    print(f"    Korrig. : {'PASS' if _korr else 'FAIL'}"
          f"   -> Realitaet: {'Variante D (additiv)' if _korr else 'KOLLAPS auf B'}")

print("\n" + "=" * 118)
print("4) SCHWELLEN: ab welchem b0 kippt welcher Bar?")
print("=" * 118)
for _b in (1072, 1073, 1074):
    _lo = float(LOW[_b])
    _bs = _lo / (1.0 - BAND / 100.0)
    _trag = "TRAGEND" if _b + 2 <= 1075 else "neutral"
    print(f"  bar {_b}: Docht ab b0 > {_bs:.5f}  ({_trag}; "
          f"Abstand zu b0={B0S:.4f}: {_bs - B0S:+.5f} USD)")
print("\nENDE E-34n/12")
