# test/test_sweep_cap.py
"""Sweep der Box-Lebensdauer-Caps auf Sample 1 (kausal, 02.09.2026).

Testet die Kombination aus
  - MAX_ARME_PRO_BOX    (max. Phasen/Arme pro Box, 0=aus)
  - MAX_BOX_SPAN_DAYS   (max. Kalenderspanne einer Box in Tagen, 0=aus)
auf der v6-Segmentierung (STRICT_OUTSIDE=False = alle Kanten des Kandidaten).

Modus entspricht der Handoff-Referenztabelle: AB_REIFE=False (Signale ab
Box-Beginn, ohne Reife-Untergrenze) - vgl. Schritt-1-Ergebnis +217.44R fuer
arme=8/span=14 als Anker zur Selbst-Verifikation.

Vergleichswerte (S1 2026-02-05..2026-08-28):
  Baseline (Phasen)            : 201 Sig / 44% / +197.26R
  v6 uncapped (arme=0, span=0) : 218 Sig / 33% / +204.21R
  v6 + Cap(8/14)               : 221 Sig / 34% / +217.44R

Aufruf (alle Kombinationen = kartesisches Produkt):
  python test/test_sweep_cap.py --start=2026-02-05 --ende=2026-08-28 \
      --arme=0,6,8,10,12 --span=14            # Arme-Sweep bei fester Spanne
  python test/test_sweep_cap.py --start=2026-02-05 --ende=2026-08-28 \
      --arme=8 --span=0,10,18,21              # Spannen-Sweep bei fester Arme-Zahl
"""
from __future__ import annotations

import contextlib
import io
import itertools
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_kausal_box_reife as kbr  # noqa: E402  (Prototyp-Funktionen)

START = "2026-08-10"
ENDE = "2026-08-28"
ARME_LIST = [8]
SPAN_LIST = [14]
_FORCE = "--force" in sys.argv  # VOR load_ns sichern (load_ns ueberschreibt argv)

for _a in sys.argv[1:]:
    if _a.startswith("--start="):
        START = _a.split("=", 1)[1]
    if _a.startswith("--ende="):
        ENDE = _a.split("=", 1)[1]
    if _a.startswith("--arme="):
        ARME_LIST = [int(x) for x in _a.split("=", 1)[1].split(",")]
    if _a.startswith("--span="):
        SPAN_LIST = [float(x) for x in _a.split("=", 1)[1].split(",")]


def _quiet() -> contextlib.AbstractContextManager:
    """Unterdrueckt stdout (build_boxes/run_boxes sind sehr gespraechig)."""
    return contextlib.redirect_stdout(io.StringIO())


def _run_combo(ns: dict, phases, arme: int, span: float) -> tuple:
    """Eine Cap-Kombination: Boxen bauen + Signale sammeln (ab_reife=False).

    Rueckgabe: (arme, span, n_sig, n_win, n_loss, sum_r).
    """
    t0 = time.perf_counter()
    with _quiet():
        boxes = kbr.build_boxes(phases, kbr.TOL_KANTE, kbr.MIN_WEITE_PCT,
                                max_arme=arme, max_span_days=span)
        sigs = kbr.run_boxes(ns["df"], boxes, ab_reife=False)
    n, w, l, r = kbr.sig_stats(sigs)
    dt = time.perf_counter() - t0
    return arme, span, n, w, l, r, dt


def main() -> None:
    """Fuehrt den Sweep aus und gibt eine sortierte Tabelle aus."""
    print(f"=== Cap-Sweep | v6 | AB_REIFE=False | {START}..{ENDE} ===")
    print(f"    Grid: arme={ARME_LIST} | span={SPAN_LIST}")
    kbr.STRICT_OUTSIDE = False  # v6-Modus (wie Handoff-Schritt-1)
    ns = kbr.load_ns(START, ENDE)
    kbr.ns = ns  # run_boxes nutzt Modul-globales ns
    df = ns["df"]
    if len(df) > kbr.MAX_BARS_DEFAULT:
        # Sweep selbst entscheidet (bewusst, kein versehentlicher S2-Lauf)
        if not (_FORCE or "2025" in START):
            print(f"ABBRUCH: {len(df)} Bars > MAX_BARS_DEFAULT "
                  f"({kbr.MAX_BARS_DEFAULT}). Fuer S1/S2 --force anhaengen "
                  f"(S2 ~6-10 min je Kombination!).")
            sys.exit(2)
    phases = ns["phases"]

    results = []
    for arme, span in itertools.product(ARME_LIST, SPAN_LIST):
        a, s, n, w, l, r, dt = _run_combo(ns, phases, arme, span)
        wr = 100.0 * w / (w + l) if w + l else 0.0
        avg = r / n if n else 0.0
        cap_txt = ("uncapped" if (a == 0 and s == 0) else
                   f"arme={a:>2}/span={s:>5.2f}")
        print(f"  {cap_txt:<22}: {n:3d} Sig | {w:3d}W/{l:3d}L | "
              f"{wr:3.0f}% | {r:+8.2f}R | avg {avg:+.2f} | {dt:4.0f}s")
        results.append((a, s, n, w, l, r))

    print("\n--- SORTIERT (Summe R absteigend) ---")
    for a, s, n, w, l, r in sorted(results, key=lambda x: -x[5]):
        wr = 100.0 * w / (w + l) if w + l else 0.0
        avg = r / n if n else 0.0
        print(f"  arme={a:>2} span={s:>5.2f}: {n:3d} Sig | {w:3d}W/{l:3d}L | "
              f"{wr:3.0f}% | {r:+8.2f}R | avg {avg:+.2f}")


if __name__ == "__main__":
    main()
