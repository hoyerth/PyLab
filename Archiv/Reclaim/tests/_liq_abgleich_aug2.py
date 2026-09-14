# -*- coding: utf-8 -*-
"""READ-ONLY Abgleich v2: AUG-Liq-Linien (Seiten-Fix) gegen Rohdaten + Engine."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
START, ENDE, TOL = "2026-08-10", "2026-08-28", 0.10

SPEZ: Tuple[Tuple[str, str, float, Tuple[str, ...]], ...] = (
    ("upper 66.46      ", "OBEN", 66.46, ("11.08 03:45", "18.08 03:00")),
    ("lower 63.67      ", "UNTEN", 63.67, ("10.08 07:30", "18.08 17:30")),
    ("lower minor 64.20", "UNTEN", 64.20, ("11.08 08:30", "14.08 02:30")),
    ("Upper1 69.90     ", "OBEN", 69.90, ("21.08 10:30", "21.08 13:15",
                                          "21.08 18:45", "24.08 15:00",
                                          "25.08 02:00")),
    ("Upper2 69.62     ", "OBEN", 69.62, ("26.08 04:30", "27.08 03:45",
                                          "27.08 19:00")),
    ("Lower1 68.88     ", "UNTEN", 68.88, ("21.08 16:30",)),
    ("Lower2 68.40     ", "UNTEN", 68.40, ("24.08 03:30", "24.08 17:45",
                                           "24.08 20:00")),
    ("Lower3 67.60     ", "UNTEN", 67.60, ("25.08 04:45", "25.08 11:00",
                                           "25.08 15:00", "26.08 17:00",
                                           "27.08 15:45")),
)


def _lade(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _clusters(idx: np.ndarray, gap: int = 4) -> List[Tuple[int, int]]:
    if len(idx) == 0:
        return []
    out, s, p = [], int(idx[0]), int(idx[0])
    for x in idx[1:]:
        if x - p > gap:
            out.append((s, p))
            s = int(x)
        p = int(x)
    out.append((s, p))
    return out


def main() -> None:
    R = _lade("run_lab_liq2", ROOT / "test" / "run_lab.py")
    B = R._load("basis_liq2", R.BASELINE_PFAD)
    V = R._load("v020_liq2", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()

    B.FENSTER["LAB"] = (START, ENDE)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)

    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    alle = list(scan["edges"]) + list(scan["seeds"])

    for lab, seite, preis, zeiten in SPEZ:
        arr = hi if seite == "OBEN" else lo
        mk = "H" if seite == "OBEN" else "L"
        idx = np.where(np.abs(arr - preis) <= TOL)[0]
        print(f"### {lab} {seite} {preis:.2f} | Roh-Treffer(|{mk}-p|<= {TOL}): "
              f"{len(idx)}")
        for a, b in _clusters(idx):
            print(f"    Cluster Bar {a:4d}..{b:4d}  "
                  f"{str(ts[a])[:10]}..{str(ts[b])[:10]}  "
                  f"({b - a + 1} Bars)")
        print("    Vorgabezeiten:")
        for z in zeiten:
            tag, hm = z.split(" ")
            dd, mm = tag.split(".")
            b = int(np.searchsorted(ts, np.datetime64(f"2026-{mm}-{dd}T{hm}")))
            ext = arr[b] if 0 <= b < n else float("nan")
            print(f"      {z} -> Bar {b:4d} {str(ts[b])[:16]} "
                  f"{mk} {ext:.4f} (d={ext - preis:+.4f})")
        tref = [e for e in alle
                if str(e.seite) == seite
                and abs(float(e.basis) - preis) <= 0.30]
        print(f"    Engine-Kanten (|basis-p|<=0.30): {len(tref)}")
        for e in sorted(tref, key=lambda x: float(x.basis)):
            wv = [(int(bb), float(pp)) for bb, pp in e.wicks]
            ws = " ".join(f"{bb}@{pp:.3f}" for bb, pp in sorted(wv)[:9])
            print(f"      K{int(e.kid):3d} basis={float(e.basis):.4f} "
                  f"n_wicks={len(e.wicks)} status={e.status} "
                  f"prim={e.ist_prim_anker} | {ws}")
        print()


if __name__ == "__main__":
    main()
