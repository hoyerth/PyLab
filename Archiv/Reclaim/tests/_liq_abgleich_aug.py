# -*- coding: utf-8 -*-
"""READ-ONLY Abgleich: handverifizierte AUG-Liq-Linien gegen Rohdaten + Engine.

KEINE Dokumentation, kein Schreiben ausser stdout. Motoren byte-identisch.
Zeitbasis-Pruefung: BKZ (Kanon) vs. Anzeige (+02:00).
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

START, ENDE = "2026-08-10", "2026-08-28"
TOL = 0.08


def _lade(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


SPEZ: Tuple[Tuple[str, str, float, Tuple[str, ...]], ...] = (
    ("upper      ", "OBEN ", 66.46, ("11.08 03:45", "18.08 03:00")),
    ("lower      ", "UNTEN", 63.67, ("10.08 07:30", "18.08 17:30")),
    ("lower minor", "UNTEN", 64.20, ("11.08 08:30", "14.08 02:30")),
    ("Upper1     ", "OBEN ", 69.90, ("21.08 10:30", "21.08 13:15",
                                     "21.08 18:45", "24.08 15:00", "25.08 02:00")),
    ("Upper2     ", "OBEN ", 69.62, ("26.08 04:30", "27.08 03:45",
                                     "27.08 19:00")),
    ("Lower1     ", "UNTEN", 68.88, ("21.08 16:30",)),
    ("Lower2     ", "UNTEN", 68.40, ("24.08 03:30", "24.08 17:45",
                                     "24.08 20:00")),
    ("Lower3     ", "UNTEN", 67.60, ("25.08 04:45", "25.08 11:00",
                                     "25.08 15:00", "26.08 17:00",
                                     "27.08 15:45")),
)


def _ts_str(d: Dict[str, Any]) -> np.ndarray:
    return d["ts"].to_numpy().astype("datetime64[ns]")


def main() -> None:
    R = _lade("run_lab_liq", ROOT / "test" / "run_lab.py")
    B = R._load("basis_liq", R.BASELINE_PFAD)
    V = R._load("v020_liq", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    B.FENSTER["LAB"] = (START, ENDE)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    ts = _ts_str(d)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)

    print(f"AUG n={n} | ts[0]={ts[0]} ts[-1]={ts[-1]}")
    print(f"BKZ-Handelstage: {len(np.unique(ts.astype('datetime64[D]')))}")
    # Bar pro Tag
    tage = np.unique(ts.astype("datetime64[D]"))
    print(f"Bars/Tag ~ {n / len(tage):.1f}")
    print()

    # ---- Zeitbasis-Anker: 25.08 15:00 -> welcher Bar? -------------------
    print("=== ZEITBASIS-ANKER (Ihre Angabe: Lower3 bar 1072 = 25.08 15:00) ===")
    for label, offs in (("BKZ   ", 0), ("Anz+2 ", 2)):
        ziel = np.datetime64("2026-08-25T15:00") - np.timedelta64(offs, "h")
        b = int(np.searchsorted(ts, ziel))
        print(f"  {label}: 25.08 15:00 -> Bar {b}  (BKZ {ts[b]})  "
              f"O{op[b]:.4f} H{hi[b]:.4f} L{lo[b]:.4f} C{cl[b]:.4f}")
    print()

    # ---- Treffer je Preis ------------------------------------------------
    print("=== TREFFER JE PREIS (Rohdaten, |ext - preis| <= 0.08) ===")
    for lab, seite, preis, _t in SPEZ:
        arr = hi if seite == "OBEN" else lo
        idx = np.where(np.abs(arr - preis) <= TOL)[0]
        print(f"{lab} {seite} {preis:7.2f} : {len(idx)} Roh-Treffer")
        for b in idx:
            print(f"      Bar {b:4d}  BKZ {str(ts[b])[:16]}  "
                  f"H {hi[b]:.4f} L {lo[b]:.4f}")
        # Zusammenhaengende Cluster
        cl_ = []
        if len(idx):
            s = idx[0]
            p = idx[0]
            for x in idx[1:]:
                if x - p > 4:
                    cl_.append((s, p))
                    s = x
                p = x
            cl_.append((s, p))
        print(f"      Cluster: "
              + ", ".join(f"{str(ts[a])[:10]}..{str(ts[b])[:10]}"
                          for a, b in cl_))
    print()

    # ---- Engine-Kanten in der Naehe -------------------------------------
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    alle = list(scan["edges"]) + list(scan["seeds"])
    print("=== ENGINE-KANTEN nahe der Vorgabe (|e.basis - preis| <= 0.25) ===")
    for lab, seite, preis, _t in SPEZ:
        tref = [e for e in alle
                if str(e.seite) == seite and abs(float(e.basis) - preis) <= 0.25]
        print(f"{lab} {seite} {preis:7.2f} : {len(tref)} Kanten")
        for e in sorted(tref, key=lambda x: float(x.basis)):
            ws = sorted(b for b, _ in e.wicks)
            wstr = ",".join(str(b) for b in ws[:8])
            print(f"      K{int(e.kid):3d} basis={float(e.basis):.4f} "
                  f"wicks={len(e.wicks)} [{wstr}] "
                  f"erster_pivot={int(e.erster_pivot_bar)} "
                  f"prim={e.ist_prim_anker} stat={e.status}")
    print()

    # ---- Endpunkte: Vorgabezeit -> Bar -> Extrema -----------------------
    print("=== VORGABEZEIT -> BAR (BKZ-Annahme) + Extrema am Bar ===")
    for lab, seite, preis, zeiten in SPEZ:
        print(f"{lab} {seite} {preis:7.2f}")
        for z in zeiten:
            tag, hm = z.split(" ")
            dd, mm = tag.split(".")
            iso = f"2026-{mm}-{dd}T{hm}"
            b = int(np.searchsorted(ts, np.datetime64(iso)))
            if 0 <= b < n:
                ext = hi[b] if seite == "OBEN" else lo[b]
                print(f"      {iso} -> Bar {b:4d} BKZ {str(ts[b])[:16]} "
                      f"{('H' if seite == 'OBEN' else 'L')} {ext:.4f} "
                      f"(d={ext - preis:+.4f})")
            else:
                print(f"      {iso} -> ausserhalb")


if __name__ == "__main__":
    main()
