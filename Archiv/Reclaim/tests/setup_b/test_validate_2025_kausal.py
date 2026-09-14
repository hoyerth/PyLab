# test/test_validate_2025_kausal.py
"""2-Sample-Validierung (Sample 2: 2025-01-01..2025-12-01) der Kandidaten aus
der kausalen Re-Optimierung (Sample 1: 2026-02-05..2026-08-28).

Kandidaten (aus test_sweep_kausal_reopt.py --summary-only):
  - Default       : rcand=0 / bounce=2 / crv=1.0 / CD=12  -> Baseline +197.26R (S1)
  - CD=8          : +219.14R / 226 Sig (S1)
  - CD=14         : +212.15R / 195 Sig / 46% WR (S1)
  - rcand=30      : +144.31R / 113 Sig / 46% WR / avg +1.28 (S1)

Dumps: scripts/results_kausal_2025_<name>.txt
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "phasen_volumen_profil.py"
TXT = ROOT / "scripts" / "phasen_volumen_profil.txt"
OUT_DIR = ROOT / "scripts"
START, ENDE = "2025-01-01", "2025-12-01"

CANDIDATES = [
    ("cd08",    ["--cooldown=8"]),
    ("cd14",    ["--cooldown=14"]),
    ("rcand30", ["--reclaim-candles=30"]),
]


def main():
    print(f"=== 2-SAMPLE-VALIDIERUNG | Sample 2: {START}..{ENDE} ===")
    for name, extra in CANDIDATES:
        r = subprocess.run(
            [sys.executable, str(SRC), f"--start={START}", f"--ende={ENDE}", *extra],
            capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(f"FEHLER {name}: {r.stderr[-800:]}")
            continue
        dump = OUT_DIR / f"results_kausal_2025_{name}.txt"
        if TXT.exists():
            TXT.replace(dump)
        stats = [ln.strip() for ln in r.stdout.splitlines()
                 if ln.strip().startswith(("  Signale:", "  Trefferquote:", "  Summe R:"))]
        print(f"--- {name} ({' '.join(extra)}) ---")
        for s in stats:
            print(f"  {s}")
    print("\n=== FERTIG ===")


if __name__ == "__main__":
    main()
