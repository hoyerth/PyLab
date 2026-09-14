# -*- coding: utf-8 -*-
"""DIAGNOSE `_p9`: Diskrepanz RAM-Verifikation (box_end_bar = n) vs. offizieller
Lauf (box_end_bar = 644, Box < 19.08).

Read-only. Aendert die Engine NICHT. Vergleicht den gepatchten Stand unter
zwei Box-Definitionen und listet die Trade-Bars auf.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


def main() -> int:
    src = P.read_text(encoding="utf-8")
    mod = load("p9_diag", src)
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    n = sc["n"]
    box = sc["box_end_bar"]
    print("=" * 100)
    print("DIAGNOSE `_p9` -- Box-Grenze vs. Voll-Lauf (gepatchter Stand)")
    print("=" * 100)
    print(f"  n = {n} | box_end_bar (offiziell) = {box} | Box = bars < {box}")

    for label, be in (("VOLL-LAUF  box_end_bar = n", n),
                      (f"OFFIZIELL box_end_bar = {box}", box)):
        sc2 = mod._se_scan("AUG", cfg)   # FRISCHER Scan (Mutations-Falle!)
        sc2["box_end_bar"] = be
        tr, st = mod._se_trades(sc2, cfg)
        r = sum(t.r for t in tr)
        print("")
        print(f"  --- {label} ---")
        print(f"      Trades {len(tr):2d} | Summe {r:+7.2f} R | "
              f"Stacking {st.get('stacking_blockiert', 0)} | "
              f"Zyklus {st.get('zyklus_blockiert', 0)} | "
              f"R21 {st.get('r21_blockiert', st.get('tombstone', '?'))}")
        for t in sorted(tr, key=lambda x: x.bar):
            flag = "  <== AUSSERHALB DER BOX" if t.bar >= box else ""
            print(f"      bar {t.bar:4d} {t.richtung:5s} K{t.kid:3d} "
                  f"entry={t.entry_bar:4d} {t.r:+7.2f}R{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
