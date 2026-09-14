# -*- coding: utf-8 -*-
"""U3 -- Schwanzlast des Bestands (Extremum-Ziel): lebt der Monat von EINEM Trade?

Ergaenzt ``_chk_u3_spec_beleg.py`` (F4b/F4c) um die entscheidende Kennzahl:
Wie viel des Monats-SumR stammt aus dem groessten Einzeltrade? Wenn das
Ergebnis an einem Ausreisser haengt, ist jede Zielverkuerzung (NAECHSTE,
Deckel) strukturell ein Angriff auf genau diesen Ausreisser.

Read-only, Baseline-Pfad. Kein Engine-Eingriff.

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_u3_schwanz_last.py
"""
from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

V = importlib.import_module("tmp_kanten_engine_v021_replay")

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")

FENSTER: Tuple[Tuple[str, str, str], ...] = (
    ("MAI", "2026-05-01", "2026-06-01"),
    ("JUN", "2026-06-01", "2026-07-01"),
    ("JUL", "2026-07-01", "2026-08-01"),
    # AUG wird ueber den arretierten AUG-Scan direkt geladen (eigene Box).
)

OUT = ROOT / "test" / "_chk_u3_schwanz_last_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _fenster_scan(B: Any, lab: str, start: str, ende: str) -> Dict[str, Any]:
    """Fenster-Scan exakt wie in ``_chk_u3_spec_beleg`` (Monats-Schalter)."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    o = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = o  # type: ignore
    scan["box_end_bar"] = int(len(d))
    return scan


def main() -> None:
    _z("U3 -- SCHWANZLAST DES BESTANDS (Extremum-Ziel)")
    _z("=" * 100)
    ist = _sha(BASELINE_PFAD)
    _z(f"SHA Baseline  {ist[:16]}...  {'OK' if ist == BASELINE_SHA else 'ABWEICHUNG!'}")
    _z("")

    B = V._engine()
    kcfg = B.StraightEdgeHarnessKonfiguration()
    cfg_def = V.V021KantenKonfiguration()

    dossiers: Dict[str, Any] = {}
    for lab, start, ende in FENSTER:
        scan = _fenster_scan(B, lab, start, ende)
        tr = V._lauf(scan, cfg_def)
        dossiers[lab] = {"scan": scan, "tr": sorted(tr, key=lambda t: t.bar)}
    scan_aug = B._se_scan("AUG", kcfg)
    dossiers["AUG"] = {
        "scan": scan_aug,
        "tr": sorted(V._lauf(scan_aug, cfg_def, box_end=int(scan_aug["n"])),
                     key=lambda t: t.bar),
    }

    _z(f"{'Fenster':8s} {'Trades':>6s} {'SumR':>12s} {'Top-1-Trade':>13s} "
       f"{'Top-1 R':>10s} {'SumR ohne Top-1':>16s} {'R/Trade':>9s} "
       f"{'R/Tr o.T1':>10s} {'Top1-Anteil':>11s}")
    _z("-" * 100)
    ges = {"sum": 0.0, "ohne": 0.0, "n": 0}
    for lab in ("MAI", "JUN", "JUL", "AUG"):
        tr = dossiers[lab]["tr"]
        rs = [float(t.r) for t in tr]
        s = sum(rs)
        top = max(tr, key=lambda t: float(t.r))
        top_r = float(top.r)
        ohne = s - top_r
        n = len(tr)
        ges["sum"] += s
        ges["ohne"] += ohne
        ges["n"] += n
        _z(f"{lab:8s} {n:>6d} {s:>+12.6f} K{int(top.kid)}@{int(top.bar):<6d} "
           f"{top_r:>+10.4f} {ohne:>+16.6f} "
           f"{s / n if n else 0.0:>+9.4f} "
           f"{ohne / (n - 1) if n > 1 else 0.0:>+10.4f} "
           f"{(top_r / s * 100.0) if abs(s) > 1e-12 else float('nan'):>10.1f}%")
    _z("-" * 100)
    _z(f"{'SUMME':8s} {ges['n']:>6d} {ges['sum']:>+12.6f} {'':>13s} "
       f"{'':>10s} {ges['ohne']:>+16.6f} "
       f"{ges['sum'] / ges['n']:>+9.4f} "
       f"{ges['ohne'] / (ges['n'] - 4):>+10.4f}")
    _z("")

    # --- Gegenprobe: Verteilung der R-Werte je Fenster --------------------
    _z("R-Verteilung je Fenster (zeigt, ob der Rest ein Rauschen um 0 ist):")
    _z(f"{'Fenster':8s} {'>+5R':>5s} {'+1..+5':>7s} {'0..+1':>7s} "
       f"{'-1':>5s} {'<-1':>5s} {'SumR ohne alle >+5R':>21s}")
    _z("-" * 100)
    for lab in ("MAI", "JUN", "JUL", "AUG"):
        tr = dossiers[lab]["tr"]
        rs = [float(t.r) for t in tr]
        gross = [r for r in rs if r > 5.0]
        klein = sum(r for r in rs if r <= 5.0)
        _z(f"{lab:8s} {len(gross):>5d} "
           f"{sum(1 for r in rs if 1.0 < r <= 5.0):>7d} "
           f"{sum(1 for r in rs if 0.0 <= r <= 1.0):>7d} "
           f"{sum(1 for r in rs if abs(r + 1.0) < 1e-9):>5d} "
           f"{sum(1 for r in rs if r < -1.0 - 1e-9):>5d} "
           f"{klein:>+21.6f}")
    _z("")
    _z("Lesehilfe: 'SumR ohne alle >+5R' ist das Ergebnis, wenn man jeden")
    _z("Ausreisser-Trade streicht. Ist diese Zahl <= 0, traegt kein Monat")
    _z("eine breite Kante -- das Ergebnis haengt an einzelnen Treffern.")
    _z("")

    (OUT).write_text("\n".join(_Z) + "\n", encoding="utf-8")
    _z(f"PROTOKOLL: {OUT}")


if __name__ == "__main__":
    main()
