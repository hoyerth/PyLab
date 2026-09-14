# -*- coding: utf-8 -*-
"""E-34h (read-only) -- Verifikation des V019-Einbrands in den Adapter.

Schritt 1: Der neue Block wurde angehaengt; hier laufen die Fail-Loud-Pruefer
           des Adapters gegen den ECHTEN Scan.
Schritt 2: Integritaets-Audit -- DEFAULT_ADAPTER, ADAPTER_V014, ADAPTER_V015
           und alle Bestandskonstanten muessen unveraendert sein.
Schritt 3: Die Datenbasis fuer die 9 Renderer-Erweiterungsstellen.

Es wird NICHTS geschrieben; nur der Adapter wird importiert.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ADAPTER_P = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
OUT = ROOT / "test" / "_tmp_e34h_einbrand_verify_out.txt"
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

from backtest_lab import phasen_regime_adapter as pra  # noqa: E402

fail = 0


def check(label: str, ok: bool) -> None:
    global fail
    if not ok:
        fail += 1
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")


b = ADAPTER_P.read_bytes()
print("=" * 100)
print("E-34h VERIFIKATION DES V019-EINBRANDS (read-only)")
print("=" * 100)
print(f"Adapter: {ADAPTER_P.name}  {len(b)} B  "
      f"SHA256 {hashlib.sha256(b).hexdigest()}")
print(f"Zeilen: {b.count(chr(10).encode())}  CRLF: {b.count(b'\\r\\n')}  "
      f"endet mit NL: {b.endswith(chr(10).encode())}")

print("\n--- Schritt 1: Konstruktion (Import hat die Fail-Loud-Pruefer "
      "bereits durchlaufen) ---")
check("ADAPTER_V019 existiert",
      hasattr(pra, "ADAPTER_V019"))
check("AKTIVE_SEGMENTE_V019 existiert",
      hasattr(pra, "AKTIVE_SEGMENTE_V019"))
check("Plateau-Konstanten 41/114/77",
      (pra.PLATEAU_MIN_BARS, pra.PLATEAU_MAX_BARS,
       pra.PLATEAU_REFERENZ_BARS) == (41, 114, 77))
check("P9 is P9_BODEN_RECLAIM (uebernommen, nicht neu)",
      pra.AKTIVE_SEGMENTE_V019[0] is pra.P9_BODEN_RECLAIM)
check("P9-Override 69.87 erhalten",
      pra.AKTIVE_SEGMENTE_V019[0].decke.niveau_override == 69.87)
check("P9-Boden-Literal 68.40 erhalten",
      pra.AKTIVE_SEGMENTE_V019[0].boden_deklariert_literal == 68.4000)
check("A1 ohne Boden-Literal (G4 inert)",
      pra.AKTIVE_SEGMENTE_V019[1].boden_deklariert_literal is None)
check("A2 ohne Boden-Literal (G4 inert)",
      pra.AKTIVE_SEGMENTE_V019[2].boden_deklariert_literal is None)
check("A1/A2 toleranz == 1.0",
      (pra.AKTIVE_SEGMENTE_V019[1].provenienz_toleranz_pct,
       pra.AKTIVE_SEGMENTE_V019[2].provenienz_toleranz_pct) == (1.0, 1.0))

print("\n--- Schritt 1b: Fail-Loud-Pruefer gegen den echten Scan ---")
spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
scan = eng._se_scan("AUG", eng.StraightEdgeHarnessKonfiguration())
for ref in (848, 980, 1259):
    kanten = [(e.kid, e.seite, float(e.basis_bei(ref)))
              for e in list(scan["edges"]) + list(scan["seeds"])]
    try:
        pra.ADAPTER_V019.verifiziere_gegen_scan(kanten)
        print(f"  [OK ] verifiziere_gegen_scan @REF {ref}")
    except ValueError as exc:
        fail += 1
        print(f"  [FAIL] verifiziere_gegen_scan @REF {ref}: {exc}")
try:
    pra.ADAPTER_V019.verifiziere_niveau_overrides()
    print("  [OK ] verifiziere_niveau_overrides")
except ValueError as exc:
    fail += 1
    print(f"  [FAIL] verifiziere_niveau_overrides: {exc}")
try:
    pra.ADAPTER_V019.verifiziere_boden_literale()
    print("  [OK ] verifiziere_boden_literale")
except ValueError as exc:
    fail += 1
    print(f"  [FAIL] verifiziere_boden_literale: {exc}")

print("\n--- Schritt 1c: Nahtstellen + aktive Phasen ---")
erwartet = {1020: "PHASE", 1021: "BLOCKIERT", 1032: "BLOCKIERT",
            1033: "PHASE", 1173: "PHASE", 1174: "PHASE",
            1287: "PHASE", 1288: "BLOCKIERT"}
for k, m in erwartet.items():
    got = pra.ADAPTER_V019.hook_2_ziel(k, "SHORT").modus.value
    ph = pra.ADAPTER_V019.aktive_phase_bei(k)
    check(f"bar {k}: {m}", got == m)
    print(f"        -> {got:<10} phase={ph.phasen_id if ph else None}")
akt = sum(1 for k in range(1021, 1288)
          if pra.ADAPTER_V019.aktive_phase_bei(k) is not None)
check(f"aktive Phasen 1021..1287 == 255/267 (ist {akt})", akt == 255)

print("\n--- Schritt 1d: Plateau-SSoT ---")
for d, ok in ((40, False), (41, True), (77, True), (114, True), (115, False)):
    check(f"d={d} -> ist_im_plateau={ok}",
          pra.PhasenReifeKonfiguration(d).ist_im_plateau() is ok)

print("\n--- Schritt 2: Integritaets-Audit (Altsatz unberuehrt) ---")
check("DEFAULT_ADAPTER == (P9,)",
      tuple(s.phasen_id for s in pra.DEFAULT_ADAPTER.segmente) == ("P9",))
check("AKTIVE_DEFAULT_SEGMENTE == (P9,)",
      pra.AKTIVE_DEFAULT_SEGMENTE == (pra.P9,))
check("ADAPTER_V014 == (P9_DIRECT_69_87,)",
      tuple(s.phasen_id for s in pra.ADAPTER_V014.segmente) == ("P9",)
      and pra.ADAPTER_V014.segmente[0] is pra.P9_DIRECT_69_87)
check("ADAPTER_V015 == (P9_BODEN_RECLAIM,)",
      pra.AKTIVE_SEGMENTE_V015 == (pra.P9_BODEN_RECLAIM,)
      and pra.ADAPTER_V015.segmente == (pra.P9_BODEN_RECLAIM,))
check("RESERVE_SEGMENTE == (P12_RESERVE,)",
      pra.RESERVE_SEGMENTE == (pra.P12_RESERVE,))
check("ADAPTER_V019.segmente == (P9_BODEN_RECLAIM, A1, A2)",
      tuple(s.phasen_id for s in pra.ADAPTER_V019.segmente)
      == ("P9", "A1_AUTO_77", "A2_AUTO_77"))
check("Benchmark-Konstanten unveraendert",
      (pra.BASELINE_V01_H2_R, pra.BENCHMARK_V014_H2_R,
       pra.BENCHMARK_V014_GESAMT_R, pra.BENCHMARK_V014_DELTA_R)
      == (7.902085, 22.285802, 61.250064, 14.383717))
check("QUARTETT_V014_BARS == (903, 980, 981, 1020)",
      pra.QUARTETT_V014_BARS == (903, 980, 981, 1020))
check("K67_OVERRIDE_69_87 == 69.87", pra.K67_OVERRIDE_69_87 == 69.87)
check("P9_BODEN_LITERAL == 68.4000", pra.P9_BODEN_LITERAL == 68.4000)
check("P9 / P9_DIRECT_69_87 / P12_RESERVE Rollen unveraendert",
      (pra.P9.decke.kid, pra.P9.boden.kid) == (67, 77)
      and (pra.P9_DIRECT_69_87.decke.niveau_override == 69.87)
      and (pra.P12_RESERVE.decke.kid, pra.P12_RESERVE.boden.kid) == (73, 82))

print("\n--- Schritt 3: Datenbasis fuer die 9 Renderer-Stellen ---")
print("  (1) AdapterMode: 'V019' ergaenzen")
print("  (2) Import: ADAPTER_V019")
print("  (3) _KONFIGURATIONEN['V019']")
print("  (4) KONFIGURATION_V019 anlegen")
print("  (5) Adapter-Wahl: V019-Zweig VOR der g4_aktiv-Kette")
print("  (6) _V19/_NEU/_VTAG/_VER_TEXT")
print("  (7) Engine-Guard: V019 -> box_end == 644")
print("  (8) assert len(V1)-len(V1_basis): V019-Zweig (23-14=9)")
print("  (9) neu_basis_soll / referenz_soll / quartett_r_soll: MESSEN")
print(f"\n  gemessene Sollwerte V019: gesamt "
      f"23 / +82.614385 | H1 8 / +38.919584 | H2 +43.694801 | "
      f"ZIEL 6 / +16.778809 | P9 +23.435111")

print(f"\nERGEBNIS: {'ALLE PRUEFUNGEN OK' if fail == 0 else str(fail) + ' FEHLER'}")
print("\nENDE E-34h")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
