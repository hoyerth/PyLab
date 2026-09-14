# -*- coding: utf-8 -*-
"""READ-ONLY: AUG-Liq-Linien vs. Baseline-V0 vs. V020-A (inkl. Schlaf-Status).

KEINE Dokumentation. Motoren byte-identisch. Jeder Trade-Lauf auf frischer
``copy.deepcopy(scan)`` (H20.50: Loop mutiert in-place).
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
START, ENDE, TOL = "2026-08-10", "2026-08-28", 0.10

# (Name, Seite, Preis, Anker-Zeiten aus Anwender-Vorgabe)
LINIEN: Tuple[Tuple[str, str, float, Tuple[str, ...]], ...] = (
    ("upper 66.46", "OBEN", 66.46, ("11.08 03:45", "18.08 03:00")),
    ("lower 63.67", "UNTEN", 63.67, ("10.08 07:30", "18.08 17:30")),
    ("lower-min 64.20", "UNTEN", 64.20, ("11.08 08:30", "14.08 02:30")),
    ("Upper1 69.90", "OBEN", 69.90, ("21.08 10:30", "21.08 13:15",
                                     "21.08 18:45", "24.08 15:00",
                                     "25.08 02:00")),
    ("Upper2 69.62", "OBEN", 69.62, ("26.08 04:30", "27.08 03:45",
                                     "27.08 19:00")),
    ("Lower1 68.88", "UNTEN", 68.88, ("21.08 16:30",)),
    ("Lower2 68.40", "UNTEN", 68.40, ("24.08 03:30", "24.08 17:45",
                                      "24.08 20:00")),
    ("Lower3 67.60", "UNTEN", 67.60, ("25.08 04:45", "25.08 11:00",
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


def _anker_bars(ts: np.ndarray, zeiten: Sequence[str]) -> List[int]:
    out = []
    for z in zeiten:
        tag, hm = z.split(" ")
        dd, mm = tag.split(".")
        out.append(int(np.searchsorted(
            ts, np.datetime64(f"2026-{mm}-{dd}T{hm}"))))
    return out


def main() -> None:
    R = _lade("run_lab_ll", ROOT / "test" / "run_lab.py")
    B = R._load("basis_ll", R.BASELINE_PFAD)
    V = R._load("v020_ll", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    B.FENSTER["LAB"] = (START, ENDE)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    box = int(np.searchsorted(ts, np.datetime64("2026-08-19")))

    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan0 = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan0 = copy.deepcopy(scan0)
    alle = list(scan0["edges"]) + list(scan0["seeds"])
    kid_idx = {int(e.kid): e for e in alle}

    print(f"AUG n={n} box={box} edges={len(scan0['edges'])} "
          f"seeds={len(scan0['seeds'])}")
    print()

    # ---------- 1) Liq-Linien vs. Engine-Kanten (mit Schlaf-Status) --------
    print("=" * 96)
    print("1) ANWENDER-LIQ-LINIEN  ->  Engine-Kante(n), Schlaf-Status, "
          "Niveau-Drift")
    print("=" * 96)
    for lab, seite, preis, zeiten in LINIEN:
        arr = hi if seite == "OBEN" else lo
        abars = _anker_bars(ts, zeiten)
        rausch = np.where(np.abs(arr - preis) <= TOL)[0]
        print(f"\n{lab}  ({seite}, Vorgabe {preis:.2f}) | "
              f"Roh-Touches(+-{TOL}): {len(rausch)} | "
              f"Vorgabe-Anker-Bars: {abars}")
        kands: List[Tuple[int, int, Any]] = []
        for e in alle:
            if str(e.seite) != seite:
                continue
            nah = [b for b, p in e.wicks if abs(float(p) - preis) <= 0.30]
            if nah:
                kands.append((len(nah), int(e.kid), e))
        for cnt, kid, e in sorted(kands, reverse=True):
            eb = float(e.basis)
            bb = float(e.basis_bei(n - 1))
            nah = sorted(b for b, p in e.wicks
                         if abs(float(p) - preis) <= 0.30)
            schlaf = getattr(e, "schlaf_windows", [])
            print(f"    K{kid:3d} wicks_nahe={cnt:2d} gesamt={len(e.wicks):2d} "
                  f"e.basis={eb:.4f} (d={eb - preis:+.4f}) "
                  f"basis_bei(ende)={bb:.4f} (d={bb - preis:+.4f}) "
                  f"status={e.status} prim={int(bool(e.ist_prim_anker))} "
                  f"schlaf={schlaf}")
            print(f"         Bars: {nah}")

    # ---------- 2) Status-Uebersicht Major-Kanten -------------------------
    print()
    print("=" * 96)
    print("2) SCHLAF-STATUS der Major-Kanten (>=4 Wicks)")
    print("=" * 96)
    major = [e for e in alle if len(e.wicks) >= 4]
    n_schlaf = sum(1 for e in major if e.status == "SCHLAFEND")
    print(f"  Major (>=4 Wicks): {len(major)} | davon SCHLAFEND: {n_schlaf}")
    for e in sorted(major, key=lambda x: -len(x.wicks)):
        sw = getattr(e, "schlaf_windows", [])
        print(f"  K{int(e.kid):3d} {e.seite:5s} wicks={len(e.wicks):2d} "
              f"basis={float(e.basis):8.4f} status={e.status:10s} "
              f"prim={int(bool(e.ist_prim_anker))} schlaf={sw}")

    # ---------- 3) Trades: Baseline vs V020 ------------------------------
    print()
    print("=" * 96)
    print("3) TRADES  Baseline(_se_trades)  vs  V020-A(_se_trades_v020)")
    print("=" * 96)
    for boxname, boxval in (("BOX=644", box), ("VOLL=n", n)):
        sc = copy.deepcopy(scan0)
        sc["box_end_bar"] = int(boxval)
        tb, _ = B._se_trades(copy.deepcopy(sc), cfg)
        tb = sorted(list(tb), key=lambda x: int(x.entry_bar))
        sc2 = copy.deepcopy(scan0)
        sc2["box_end_bar"] = int(boxval)
        eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
        tv, _ = eng._se_trades_v020(copy.deepcopy(sc2), cfg)
        tv = sorted(list(tv), key=lambda x: int(x.entry_bar))
        print(f"\n--- {boxname} ---")
        for nm, tr in (("BASELINE-V0", tb), ("V020-A    ", tv)):
            rr = [float(t.r) for t in tr]
            h1 = [float(t.r) for t in tr if int(t.entry_bar) < box]
            h2 = [float(t.r) for t in tr if int(t.entry_bar) >= box]
            print(f"  {nm}: n={len(tr):3d} SumR={sum(rr):+10.6f} | "
                  f"H1 {len(h1)}/{sum(h1):+10.6f} | "
                  f"H2 {len(h2)}/{sum(h2):+10.6f}")
            print(f"     Trades: "
                  + ", ".join(f"K{int(t.kid)}@{int(t.entry_bar)}"
                              f"({float(t.r):+.1f})" for t in tr))
        # Welche Anwender-Linie wird bedient?
        print("  Linien-Bedienung (Trade-Kanten vs. Anwender-Linien):")
        for lab, seite, preis, _z in LINIEN:
            b_hit = [t for t in tb
                     if str(t.richtung) == ("SHORT" if seite == "OBEN"
                                            else "LONG")
                     and abs(float(kid_idx[int(t.kid)].basis) - preis) <= 0.35]
            v_hit = [t for t in tv
                     if str(t.richtung) == ("SHORT" if seite == "OBEN"
                                            else "LONG")
                     and abs(float(kid_idx[int(t.kid)].basis) - preis) <= 0.35]
            print(f"    {lab:15s} V0={len(b_hit):2d} Trades "
                  f"{sum(float(t.r) for t in b_hit):+9.3f}R | "
                  f"V020={len(v_hit):2d} Trades "
                  f"{sum(float(t.r) for t in v_hit):+9.3f}R")


if __name__ == "__main__":
    main()
