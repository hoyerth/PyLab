# -*- coding: utf-8 -*-
"""E-34f (read-only) -- Audit der V019-Spezifikation gegen den Adapter.

Prueft die vorgelegte V019-Segmentliste mit den EIGENEN Fail-Loud-Pruefern
des Adapters (``verifiziere_gegen_scan``, ``verifiziere_niveau_overrides``,
``verifiziere_boden_literale``) und vergleicht zwei Fassungen:

  A) Anwender-Fassung  (P9 als ``(77, 67)`` im Feldauftrag decke/boden)
  B) Audit-Fassung     (P9 aus ``P9_BODEN_RECLAIM`` uebernommen)

Zusaetzlich: Abgleich der Sollwerte gegen die gemessene MIN77-Ausgabe.

Kein Schreibzugriff auf ``backtest_lab/`` -- rein lesend.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    P9_BODEN_RECLAIM, PhasenKanteInfo, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUT = ROOT / "test" / "_tmp_e34f_audit_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

spec = importlib.util.spec_from_file_location("eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
katalog = {e.kid: e for e in list(scan["edges"]) + list(scan["seeds"])}


def kanten_tupel(ref_bar: int) -> List[Tuple[int, str, float]]:
    """(kid, seite, basis_bei(ref_bar)) -- Eingabe fuer den Scan-Abgleich."""
    return [(e.kid, e.seite, float(e.basis_bei(ref_bar)))
            for e in list(scan["edges"]) + list(scan["seeds"])]


def pruefe(name: str, segmente: Tuple[PhasenSegmentEintrag, ...]) -> bool:
    """Laesst alle Fail-Loud-Pruefer laufen; True gdw. alles besteht."""
    ad = PhasenRegimeAdapter(segmente=segmente)
    print(f"\n--- {name} ---")
    ok = True
    for label, fn in (("verifiziere_gegen_scan",
                       lambda: ad.verifiziere_gegen_scan(kanten_tupel(848))),
                      ("verifiziere_niveau_overrides",
                       ad.verifiziere_niveau_overrides),
                      ("verifiziere_boden_literale",
                       ad.verifiziere_boden_literale)):
        try:
            fn()
            print(f"   {label:<30} OK")
        except ValueError as exc:
            ok = False
            print(f"   {label:<30} FEHLER: {exc}")
    return ok


# ---------------------------------------------------------------- A) Anwender
ANWENDER: Tuple[PhasenSegmentEintrag, ...] = (
    PhasenSegmentEintrag(
        phasen_id="P9_BODEN_RECLAIM", start_bar=848, end_bar=1020,
        decke=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
        boden=PhasenKanteInfo(kid=67, provenienz_basis=69.9140),
        ziel_preis_short=68.3700, ziel_preis_long=69.9140),
    PhasenSegmentEintrag(
        phasen_id="A1_AUTO_77", start_bar=1033, end_bar=1173,
        decke=PhasenKanteInfo(kid=67, provenienz_basis=69.8990),
        boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5350),
        ziel_preis_short=67.5350, ziel_preis_long=69.8990),
    PhasenSegmentEintrag(
        phasen_id="A2_AUTO_77", start_bar=1174, end_bar=1287,
        decke=PhasenKanteInfo(kid=73, provenienz_basis=69.6380),
        boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5530),
        ziel_preis_short=67.5530, ziel_preis_long=69.6380),
)

# ---------------------------------------------------------------- B) Audit
A1 = PhasenSegmentEintrag(
    phasen_id="A1_AUTO_77", start_bar=1033, end_bar=1173,
    decke=PhasenKanteInfo(kid=67,
                          provenienz_basis=float(katalog[67].basis_bei(1033))),
    boden=PhasenKanteInfo(kid=82,
                          provenienz_basis=float(katalog[82].basis_bei(1033))),
    ziel_preis_short=float(katalog[82].basis_bei(1033)),
    ziel_preis_long=float(katalog[67].basis_bei(1033)))
A2 = PhasenSegmentEintrag(
    phasen_id="A2_AUTO_77", start_bar=1174, end_bar=1287,
    decke=PhasenKanteInfo(kid=73,
                          provenienz_basis=float(katalog[73].basis_bei(1174))),
    boden=PhasenKanteInfo(kid=82,
                          provenienz_basis=float(katalog[82].basis_bei(1174))),
    ziel_preis_short=float(katalog[82].basis_bei(1174)),
    ziel_preis_long=float(katalog[73].basis_bei(1174)))
AUDIT: Tuple[PhasenSegmentEintrag, ...] = (P9_BODEN_RECLAIM, A1, A2)

print("=" * 100)
print("E-34f AUDIT DER V019-SPEZIFIKATION GEGEN DIE ADAPTER-PRUEFER (read-only)")
print("=" * 100)
print(f"Adapter: backtest_lab/phasen_regime_adapter.py (unveraendert)")
print(f"Engine : {ENGINE_P.name}")

_b1 = pruefe("A) Anwender-Fassung (P9 als 77/67)", ANWENDER)
_b2 = pruefe("B) Audit-Fassung (P9 = P9_BODEN_RECLAIM)", AUDIT)

print("\n" + "=" * 100)
print("SEGMENT-DATEN (Audit-Fassung)")
print("=" * 100)
print(f"{'phasen_id':<18}{'start':>7}{'ende':>7}{'decke':>8}{'boden':>8}"
      f"{'ziel_short':>12}{'ziel_long':>12}{'override':>10}{'literal':>10}")
for s in AUDIT:
    print(f"{s.phasen_id:<18}{s.start_bar:>7}{s.end_bar:>7}"
          f"{'K' + str(s.decke.kid):>8}{'K' + str(s.boden.kid):>8}"
          f"{s.ziel_preis_short:>12.4f}{s.ziel_preis_long:>12.4f}"
          f"{str(s.decke.niveau_override):>10}"
          f"{str(s.boden_deklariert_literal):>10}")

print("\n" + "=" * 100)
print("SOLLWERT-ABGLEICH")
print("=" * 100)
ad = PhasenRegimeAdapter(segmente=AUDIT)
luecken = [(k, ad.hook_2_ziel(k, 'SHORT').modus.value)
           for k in (1021, 1032, 1033, 1173, 1174, 1287, 1288)]
print("   hook_2_ziel-Modus an den Nahtstellen:")
for k, m in luecken:
    print(f"      bar {k:>5}: {m}")
print(f"   aktive Phasen (Anzahl): "
      f"{sum(1 for k in range(1021, 1288) if ad.aktive_phase_bei(k) is not None)}"
      f" / 267")
print(f"\n   Ergebnis A) bestanden: {_b1}")
print(f"   Ergebnis B) bestanden: {_b2}")

print("\nENDE E-34f")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
