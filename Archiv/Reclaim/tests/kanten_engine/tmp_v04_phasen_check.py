# -*- coding: utf-8 -*-
"""READ-ONLY: v0.4.0-Phasensegmentierung auf AUG gegen die H2-Zielvorgabe.

Fragen:
  1) Wie erkennt v0.4 den Beginn einer neuen Phase?
  2) Wo liegen die Phasengrenzen relativ zu 21.08. 10:30?
  3) Welche U_final/L_final liefert das v0.4-Levelling (_level_schnittmenge)?

Kein Schreiben, keine Aenderung an scripts/.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import market_segmentation as ms  # noqa: E402

cfg = ms.SegmentConfig()
df = ms.load_data(cfg.db_path, cfg.start, cfg.ende)
res = ms.segmentiere_markt(df, cfg)
phases = res.phases
moves = res.moves

print("=" * 126)
print(f"v0.4.0-PHASENSEGMENTIERUNG AUG | n={len(df)} Bars | "
      f"Konfig: TOL={cfg.tol} TOL_TOUCH={cfg.tol_touch} "
      f"DENSITY_BAND={cfg.density_band} MIN_ESTABLISH={cfg.min_establish} "
      f"MIN_PHASE_CANDLES={cfg.min_phase_candles}")
print(f"   MIN_CLUSTER={cfg.min_cluster} ERWEITERUNG_PCT={cfg.erweiterung_pct} "
      f"FENSTER_PIVOTS={cfg.fenster_pivots} SHIFT_TOL={cfg.shift_tol}")
print("=" * 126)

print(f"\nPhasen: {len(phases)} | Moves: {len(moves)}")
print(f"\n{'P':>2s} {'Start':17s} {'Ende':17s} {'U_final':>9s} {'L_final':>9s} "
      f"{'brk':>6s} {'brk_kante':>10s} {'nH':>3s} {'nL':>3s} "
      f"{'birth_h':>9s} {'birth_l':>9s}")
for i, p in enumerate(phases, 1):
    print(f"{i:2d} {p.start.strftime('%d.%m. %H:%M'):17s} "
          f"{p.ende.strftime('%d.%m. %H:%M'):17s} "
          f"{(f'{p.U_final:9.3f}' if p.U_final is not None else '     None')} "
          f"{(f'{p.L_final:9.3f}' if p.L_final is not None else '     None')} "
          f"{str(p.brk_idx):>6s} "
          f"{(f'{p.brk_kante:10.3f}' if p.brk_kante is not None else '      None')} "
          f"{len(p.h_prices):3d} {len(p.l_prices):3d} "
          f"{(f'{p.birth_h:9.3f}' if p.birth_h is not None else '     None')} "
          f"{(f'{p.birth_l:9.3f}' if p.birth_l is not None else '     None')}")

print("\n" + "=" * 126)
print("PHASENGRENZEN vs. H2-Zielvorgabe (21.08. 10:30)")
print("=" * 126)
for i, p in enumerate(phases, 1):
    tag = ""
    if p.start.strftime("%d.%m.") == "21.08.":
        tag = "  <== Kandidat fuer 21.08."
    print(f"  P{i:2d}  {p.start.strftime('%a %d.%m. %H:%M')} -> "
          f"{p.ende.strftime('%a %d.%m. %H:%M')}   U={p.U_final}  L={p.L_final}{tag}")

print("\n" + "=" * 126)
print("U_final/L_final: v0.4-Levelling vs. H2-Ziel-Level")
print("=" * 126)
ZIEL = [("Upper1", 69.90), ("Upper2", 69.62), ("Lower1", 68.88),
        ("Lower2", 68.40), ("Lower3", 67.60)]
niveaus = []
for i, p in enumerate(phases, 1):
    if p.U_final is not None:
        niveaus.append((abs(p.U_final - 0), p.U_final, f"P{i} U_final"))
    if p.L_final is not None:
        niveaus.append((0, p.L_final, f"P{i} L_final"))
for name, ziel in ZIEL:
    kand = sorted(niveaus, key=lambda x: abs(x[1] - ziel))[:2]
    print(f"  {name:7s} Ziel {ziel:7.2f} | naechste v0.4-Niveaus: "
          + " | ".join(f"{lab}={val:.3f} ({val - ziel:+.3f})"
                       for _, val, lab in kand))
