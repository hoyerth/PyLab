# -*- coding: utf-8 -*-
"""E-34g (read-only) -- Toleranz-/Provenienz-Nachweis fuer die V019-Segmente.

Berechnet fuer die vier beteiligten Kanten (K67, K73, K77, K82) die kausale
Basis ``basis_bei(k)`` an mehreren Audit-Bars und die prozentuale Abweichung
zu den in der V019-Spezifikation vorgesehenen ``provenienz_basis``-Werten.
Zweck: Beleg, dass die Fail-Loud-Pruefung ``verifiziere_gegen_scan`` mit der
1-%-Toleranz (Default ``provenienz_toleranz_pct``) fuer A1/A2 traegt.

Kein Schreibzugriff auf ``backtest_lab/`` oder die Engine -- rein lesend.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUT = ROOT / "test" / "_tmp_e34g_toleranz_out.txt"
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

# (phasen_id, kante, rolle, kid, provenienz_basis, segment_start)
KANTEN = [
    ("P9", "decke", 67, 69.9140, 848),
    ("P9", "boden", 77, 68.3700, 848),
    ("A1_AUTO_77", "decke", 67, 69.8990, 1033),
    ("A1_AUTO_77", "boden", 82, 67.5350, 1033),
    ("A2_AUTO_77", "decke", 73, 69.6380, 1174),
    ("A2_AUTO_77", "boden", 82, 67.5530, 1174),
]
REF_BARS = [848, 980, 1021, 1033, 1174, 1259, 1287]

print("=" * 108)
print("E-34g TOLERANZ-/PROVENIENZ-NACHWEIS (read-only, Engine unberuehrt)")
print("=" * 108)
print(f"Engine: {ENGINE_P.name}  box_end(AUG)={scan['box_end_bar']}  n={scan['n']}")

print("\n--- basis_bei(k) je Kante an den Audit-Bars ---")
kopf = "kid | " + " | ".join(f"{b:>9d}" for b in REF_BARS)
print(kopf)
print("-" * len(kopf))
for kid in (67, 73, 77, 82):
    e = katalog[kid]
    werte = " | ".join(f"{float(e.basis_bei(b)):9.4f}" for b in REF_BARS)
    print(f"K{kid:<3d}| {werte}")

print("\n--- Abweichung provenienz_basis (Spec) vs basis_bei(REF) ---")
print(f"{'Phase':<11}{'Rolle':<7}{'Kante':<6}{'prov_basis':>11}"
      f"{'seite':>7}" + "".join(f"{'dev%@'+str(b):>12}" for b in REF_BARS))
for pid, rolle, kid, prov, _start in KANTEN:
    e = katalog[kid]
    zeile = f"{pid:<11}{rolle:<7}{'K'+str(kid):<6}{prov:>11.4f}{e.seite:>7}"
    for b in REF_BARS:
        basis = float(e.basis_bei(b))
        dev = abs(basis - prov) / prov * 100.0
        zeile += f"{dev:>12.4f}"
    print(zeile)

print("\n--- Traegt die 1-%-Toleranz? (max. Abweichung ueber alle REF_BARS) ---")
alles_ok = True
for pid, rolle, kid, prov, _start in KANTEN:
    e = katalog[kid]
    devs = {b: abs(float(e.basis_bei(b)) - prov) / prov * 100.0
            for b in REF_BARS}
    bmax = max(devs, key=devs.get)
    ok = devs[bmax] <= 1.0
    alles_ok = alles_ok and ok
    print(f"  {pid:<11}{rolle:<7}K{kid:<4d} max {devs[bmax]:.4f} % "
          f"(an Bar {bmax}) -> {'OK' if ok else 'REISST 1-%-TOLERANZ'}")

print("\n--- K82-Doppelrolle: zwei Segmente, zwei Provenienz-Werte ---")
e82 = katalog[82]
for start, prov in ((1033, 67.5350), (1174, 67.5530)):
    print(f"  A@{start}: prov {prov:.4f}  basis_bei({start}) "
          f"{float(e82.basis_bei(start)):.4f}  "
          f"dev {abs(float(e82.basis_bei(start)) - prov) / prov * 100.0:.4f} %")
print(f"  Differenz der beiden Provenienz-Werte: "
      f"{abs(67.5530 - 67.5350) * 100:.2f} Cent "
      f"(Konta-Hinweis: entscheidet dist<0 vs dist>=0)")

print("\n--- Endgueltigkeit: verifiziere_gegen_scan mit 1-%-Default ---")
from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, P9_BODEN_RECLAIM, PhasenKanteInfo, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)

A1 = PhasenSegmentEintrag(
    phasen_id="A1_AUTO_77", start_bar=1033, end_bar=1173,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.8990),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5350),
    ziel_preis_short=67.5350, ziel_preis_long=69.8990)
A2 = PhasenSegmentEintrag(
    phasen_id="A2_AUTO_77", start_bar=1174, end_bar=1287,
    decke=PhasenKanteInfo(kid=73, provenienz_basis=69.6380),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5530),
    ziel_preis_short=67.5530, ziel_preis_long=69.6380)
V019_ENTWURF = PhasenRegimeAdapter(
    segmente=(P9_BODEN_RECLAIM, A1, A2))

for ref in (848, 980, 1259):
    kanten = [(e.kid, e.seite, float(e.basis_bei(ref)))
              for e in list(scan["edges"]) + list(scan["seeds"])]
    try:
        V019_ENTWURF.verifiziere_gegen_scan(kanten)
        print(f"  REF-Bar {ref:>4}: verifiziere_gegen_scan OK")
    except ValueError as exc:
        print(f"  REF-Bar {ref:>4}: FEHLER {exc}")

for label, fn in (("verifiziere_niveau_overrides",
                   V019_ENTWURF.verifiziere_niveau_overrides),
                  ("verifiziere_boden_literale",
                   V019_ENTWURF.verifiziere_boden_literale)):
    try:
        fn()
        print(f"  {label:<30} OK")
    except ValueError as exc:
        print(f"  {label:<30} FEHLER {exc}")

print("\n--- Inertheit-Isolation: DEFAULT/V014/V015 unveraendert ---")
print(f"  DEFAULT_ADAPTER Soll: () .. bleibt P9-only-Konstante (unberuehrt)")
print(f"  ADAPTER_V015 segmente: {[s.phasen_id for s in ADAPTER_V015.segmente]}")
print(f"  V019-Entwurf segmente: {[s.phasen_id for s in V019_ENTWURF.segmente]}")

print(f"\n  1-%-Toleranz ueber alle Kanten/Ref-Bars: "
      f"{'OK' if alles_ok else 'NICHT OK'}")
print("\nENDE E-34g")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
