"""Teilschritt 1b.1: Nachweis der Reife-Bindung im Adapter (read-only).

Prueft, dass ``AUTO_VERSCHMELZUNG_SCHWELLE`` beim Import fail-loud an die
Reife-SSoT gebunden ist. Negative Faelle werden durch temporaeres Rebinding
des Modul-Globals erzeugt -- Engine, Adapter-Datei und Renderer bleiben
unberuehrt.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest_lab import phasen_regime_adapter as pra  # noqa: E402

ok = True

print("--- 1) Import-Arretierung ---")
print(f"  AUTO_VERSCHMELZUNG_SCHWELLE = {pra.AUTO_VERSCHMELZUNG_SCHWELLE}")
print(f"  PLATEAU_REFERENZ_BARS       = {pra.PLATEAU_REFERENZ_BARS}")
print(f"  Plateau                     = "
      f"[{pra.PLATEAU_MIN_BARS}, {pra.PLATEAU_MAX_BARS}]")
if pra.AUTO_VERSCHMELZUNG_SCHWELLE != pra.PLATEAU_REFERENZ_BARS:
    ok = False
    print("  [FAIL] Schwelle != Plateaumitte")
else:
    print("  [OK ] Schwelle == Plateaumitte")

print("--- 2) Segmentnamen tragen die Schwelle ---")
for seg in pra.AKTIVE_SEGMENTE_V019:
    print(f"  {seg.phasen_id:<12} {seg.start_bar}..{seg.end_bar}")
if pra.AKTIVE_SEGMENTE_V019[1].phasen_id.endswith(
        f"_{pra.AUTO_VERSCHMELZUNG_SCHWELLE}"):
    print("  [OK ] A1-Name endet auf die gebundene Schwelle")
else:
    ok = False
    print("  [FAIL] A1-Name passt nicht zur Schwelle")

print("--- 3) Fail-Loud-Stresstest (Rebinding, kein Dateieingriff) ---")
# Erwartet wird (a) "akzeptiert", (b) Plateaugrenzen-Bruch oder
# (c) Mismatch zur Plateaumitte -- je nach Wert. 41/114 liegen IM Plateau,
# sind aber nicht die Referenz 77 -> es MUSS Guard (c) greifen.
_orig = pra.AUTO_VERSCHMELZUNG_SCHWELLE
FAELLE = (
    (40, "stop", "ausserhalb des Plateaus"),
    (41, "stop", "Mismatch"),
    (77, "akzeptiert", None),
    (114, "stop", "Mismatch"),
    (115, "stop", "ausserhalb des Plateaus"),
    (50, "stop", "Mismatch"),
    (200, "stop", "ausserhalb des Plateaus"),
)
for wert, erwartet, marke in FAELLE:
    pra.AUTO_VERSCHMELZUNG_SCHWELLE = wert
    try:
        pra._verifiziere_reife_bindung()
        urteil, text = "akzeptiert", ""
    except ValueError as exc:
        urteil, text = "stop", str(exc)
    hit = (urteil == erwartet and (marke is None or marke in text))
    ok = ok and hit
    kurz = f"{urteil}: {text[:44]}..." if text else urteil
    print(f"  Schwelle {wert:>4}: erwartet {erwartet:<10} -> {kurz:<58} "
          f"{'OK' if hit else 'MISMATCH'}")
pra.AUTO_VERSCHMELZUNG_SCHWELLE = _orig

print(f"\nGESAMT: {'OK' if ok else 'FEHLER'}")
raise SystemExit(0 if ok else 1)
