# -*- coding: utf-8 -*-
"""READ-ONLY Diagnose Mai/Juni/Juli (Modus A): Trades, cumR, Geometrie-Check.

Prueft u. a. die Richtungs-Konsistenz (SHORT: SL > entry > TP2;
LONG: SL < entry < TP2) und liefert die cumR-Kurve je Monat.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

PROTOKOLL = ROOT / "test" / "_chk_mai_juli_diag_out.txt"

MONATE = (("MAI", "2026-05-01", "2026-06-01"),
          ("JUN", "2026-06-01", "2026-07-01"),
          ("JUL", "2026-07-01", "2026-08-01"))


def _lade(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main() -> None:
    import copy

    R = _lade("run_lab_diag", ROOT / "test" / "run_lab.py")
    B = R._load("basis_diag", R.BASELINE_PFAD)
    V = R._load("v020_diag", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    z: List[str] = []
    z.append("DIAGNOSE MAI/JUN/JUL (Modus A, Morphing-Baseline, box_end=n)")
    z.append("")
    gesamt = 0.0
    for lab, start, ende in MONATE:
        d = R._lade_fenster(B, start, ende)
        ts = d["ts"].to_numpy().astype("datetime64[ns]")
        n = len(d)
        original = B._lade_fenster
        B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
        try:
            scan = B._se_scan("LAB", cfg)
        finally:
            B._lade_fenster = original  # type: ignore
        scan = copy.deepcopy(scan)
        scan["box_end_bar"] = int(n)
        eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
        tr, _st = eng._se_trades_v020(scan, cfg)
        tr = sorted(list(tr), key=lambda x: int(x.entry_bar))

        z.append(f"===== {lab}: {start} .. {ende} (exkl.) | n={n} =====")
        z.append(f"  {ts[0]} .. {ts[-1]}")
        z.append(f"  edges={len(scan['edges'])} seeds={len(scan['seeds'])} "
                 f"r21={len(scan.get('r21_geloescht', []))} "
                 f"tomb={len(scan.get('tombstones', []))}")
        z.append(f"  {'#':>3s} {'KID':>4s} {'Richt':5s} {'entry_bar':>9s} "
                 f"{'entry':>9s} {'SL':>9s} {'TP2':>9s} {'bar?':>5s} "
                 f"{'R':>10s} {'cumR':>11s} {'geom':>5s} {'stufe':16s}")
        cum = 0.0
        n_fehler = 0
        for i, t in enumerate(tr, 1):
            cum += float(t.r)
            seite = str(t.richtung)
            e = float(t.entry)
            sl = float(t.sl)
            tp = float(t.tp2)
            if seite == "SHORT":
                ok = (sl > e > tp)
            else:
                ok = (sl < e < tp)
            if not ok:
                n_fehler += 1
            z.append(
                f"  {i:3d} {int(t.kid):4d} {seite:5s} {int(t.entry_bar):9d} "
                f"{e:9.4f} {sl:9.4f} {tp:9.4f} {int(t.bar):5d} "
                f"{float(t.r):+10.6f} {cum:+11.6f} "
                f"{'OK' if ok else 'FEHL':>5s} {str(t.stufe):16s}")
        z.append(f"  -> {len(tr)} Trades | SumR {cum:+.6f} | "
                 f"Geometrie-Fehler {n_fehler}")
        z.append("")
        gesamt += cum
    z.append(f"GESAMT MAI+JUN+JUL: {gesamt:+.6f} R")

    PROTOKOLL.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    for zl in z:
        print(zl)
    print(f"\n-> {PROTOKOLL}")


if __name__ == "__main__":
    main()
