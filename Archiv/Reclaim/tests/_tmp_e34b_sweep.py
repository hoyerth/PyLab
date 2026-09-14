# -*- coding: utf-8 -*-
"""E-34b (read-only) -- Klippenkarte des MIN_BARS-Parameters.

Fuehrt `_tmp_e34_auto.py` fuer jeden Wert 0..130 aus und protokolliert
Nettosumme, H1/H2/ZIEL, Segmentzahl und die Segmentgrenzen.  Ergebnis ist
eine Karte der Stabilitaetsplateaus und der Klippen.

Aufruf: python test/_tmp_e34b_sweep.py [lo] [hi]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
SKRIPT = ROOT / "test" / "_tmp_e34_auto.py"
OUT = ROOT / "test" / "_tmp_e34b_klippenkarte_out.txt"

_ZEILE = re.compile(r"^\s+(gesamt|H1|H2|ZIEL)\s+(\d+)\s+([+-][\d.]+)",
                    re.MULTILINE)
_SEG = re.compile(r"^\s+A(\d+)\s+(\d+)\.\.(\d+)\s+\(\s*(\d+) Bars\)\s+"
                  r"decke K(\d+)\s+[\d.]+\s+boden K(\d+)", re.MULTILINE)


def lauf(min_bars: int) -> str:
    """Ein Lauf mit `MIN<n>`; gibt den kombinierten Text zurueck.

    Args:
        min_bars: Mindestsegmentlaenge in Bars.

    Returns:
        Die stdout-Ausgabe des Einzellaufs.
    """
    r = subprocess.run([PY, str(SKRIPT), f"MIN{min_bars}"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout or ""


def main() -> None:
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 130
    vor: str = ""
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("=" * 118 + "\n")
        fh.write(f"E-34b KLIPPENKARTE MIN_BARS = {lo}..{hi}   (AUG, n = 1288)\n")
        fh.write("=" * 118 + "\n")
        fh.write(f"{'MIN':>4} {'n':>4} {'H1 R':>12} {'H2 R':>12} {'ZIEL R':>12}"
                 f" {'Sg':>3}  SEGMENTGRENZEN\n")
        fh.write("-" * 118 + "\n")
        for m in range(lo, hi + 1):
            txt = lauf(m)
            werte = {k: (int(a), float(b))
                     for (k, a, b) in _ZEILE.findall(txt)}
            if "gesamt" not in werte:
                fh.write(f"{m:>4}  -- kein Ergebnis --\n")
                continue
            n_ges, r_ges = werte["gesamt"]
            segs = [(int(b), int(c), int(d), int(e), int(f))
                    for (_a, b, c, d, e, f) in _SEG.findall(txt)]
            sig = " ".join(f"{a}..{b}" for (a, b, _c, _d, _e) in segs)
            marke = ""
            if vor and sig != vor:
                marke = "   <<< KLIPPE"
            vor = sig
            fh.write(
                f"{m:>4} {n_ges:>4} {werte.get('H1', (0, 0.0))[1]:>+12.6f}"
                f" {werte.get('H2', (0, 0.0))[1]:>+12.6f}"
                f" {werte.get('ZIEL', (0, 0.0))[1]:>+12.6f}"
                f" {len(segs):>3}  {sig}{marke}\n")
            fh.flush()
    print("geschrieben: " + str(OUT))


if __name__ == "__main__":
    main()
