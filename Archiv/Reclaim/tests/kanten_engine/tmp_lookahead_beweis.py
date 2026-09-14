# -*- coding: utf-8 -*-
"""LOOKAHEAD-BEWEIS: Praefix-Trunkation fuer ALLE 14 Trades (Voll-Lauf).

Methode: Fuer jeden Trade wird der Scan NUR auf den bis zum Entry-Bar
verfuegbaren Daten neu aufgebaut. Die Kanten entstehen dann kausal (nur
bestaetigte Pivots, nur bis dahin erfolgte Promotionen). Ergeben sich fuer
SL / TP1 / TP2 / Entry identische Werte, ist die Trade-Konstruktion kausal.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_loader("ke_la", loader=None)
mod = importlib.util.module_from_spec(spec)              # type: ignore[arg-type]
mod.__file__ = str(P)
sys.modules["ke_la"] = mod
exec(compile(P.read_text(encoding="utf-8"), str(P), "exec"), mod.__dict__)

cfg = mod.StraightEdgeHarnessKonfiguration()
voll = mod._lade_fenster("AUG")

# Referenz: Voll-Lauf
sc = mod._se_scan("AUG", cfg)
sc["box_end_bar"] = sc["n"]
tr_ref, _ = mod._se_trades(sc, cfg)
tr_ref = sorted(tr_ref, key=lambda t: t.bar)

orig_lade = mod._lade_fenster
print("=" * 108)
print("PRAEFIX-TRUNKATION: Trade-Konstruktion kausal? (SL / TP1 / TP2 / Entry)")
print("=" * 108)
print(f"  {'Bar':>4s} {'K':>3s} {'Richt':5s} {'Entry':>4s} "
      f"{'E':>8s} {'SL':>8s} {'TP1':>8s} {'TP2':>8s}  Urteil")
alles_ok = True
for t in tr_ref:
    cut = t.entry_bar + 4            # Box-Rand muss k > 564 zulassen
    mod._lade_fenster = lambda f, _c=cut: voll.iloc[:_c].copy()  # type: ignore
    sc2 = mod._se_scan("AUG", cfg)
    sc2["box_end_bar"] = sc2["n"]    # Voll-Lauf-Semantik auch im Praefix
    tr2, _ = mod._se_trades(sc2, cfg)
    m = [x for x in tr2 if x.bar == t.bar and x.kid == t.kid]
    if not m:
        print(f"  {t.bar:4d} {t.kid:3d} {t.richtung:5s} {t.entry_bar:4d} "
              f"-> im Praefix NICHT vorhanden")
        alles_ok = False
        continue
    x = m[0]
    d = max(abs(x.entry - t.entry), abs(x.sl - t.sl),
            abs(x.poc - t.poc), abs(x.tp2 - t.tp2))
    ok = d < 1e-9
    alles_ok &= ok
    print(f"  {t.bar:4d} {t.kid:3d} {t.richtung:5s} {t.entry_bar:4d} "
          f"{x.entry:8.3f} {x.sl:8.3f} {x.poc:8.3f} {x.tp2:8.3f}  "
          f"{'KAUSAL (identisch)' if ok else f'ABWEICHUNG d={d:.4f}'}")
mod._lade_fenster = orig_lade                           # type: ignore
print()
print(f"  GESAMT: {'KEIN LOOKAHEAD in der Trade-Konstruktion' if alles_ok else 'ABWEICHUNGEN GEFUNDEN'}")

# --- Trailing-Check: gibt es Nachzug? -----------------------------------
print()
print("=" * 108)
print("TRAILING-CHECK: SL wird nach Entry nicht veraendert?")
print("=" * 108)
src = P.read_text(encoding="utf-8")
for begriff in ("trail", "nachzieh", "nachzug", "sl = ", "sl_neu",
                "breakeven", "break_even"):
    hits = [i + 1 for i, l in enumerate(src.splitlines())
            if begriff.lower() in l.lower()]
    print(f"  {begriff:12s}: {len(hits)} Treffer {hits[:8]}")
print()
print("  Exit-Mechanik Bar 564: exit1=582 (TP1, 25%), exit2=639 (SL der "
      "2. Haelfte? -> pruefen)")
t = [x for x in tr_ref if x.bar == 564][0]
print(f"    SL={t.sl:.3f} TP1={t.poc:.3f} TP2={t.tp2:.3f} | "
      f"exit1_bar={t.exit1_bar} exit2_bar={t.exit2_bar} grund1={t.grund1}")
