"""Teilschritt 1b.2: Rekonstruktions-Nachweis der endogenen Segmentbildung.

Weist nach, dass die arretierte Regel ``zusammenfassen(roh, 77)`` bar- UND
kantenidentisch exakt die Adapter-Segmente ``A1_AUTO_77`` / ``A2_AUTO_77``
erzeugt -- und dass die Klippen 40 / 115 das Strukturverhalten aendern.

Verfahren (Weg b, E-34n/15 §D4 / Freigabe):
    Die vier Kernfunktionen ``_lebt_kausal``, ``ecken``, ``_nah`` und
    ``zusammenfassen`` werden per ``ast.get_source_segment`` WORTSETZLICH aus
    ``test/_tmp_e34_auto.py`` gelesen und in einen leeren Namespace
    kompiliert. Die Quelldatei wird NICHT veraendert; der Berichts-/
    Engine-Teil des Skripts (Modul-Ebene) wird nie ausgefuehrt.

Der Treiber (Wechselpunkte sammeln, Rohsegmente bauen) ist reine
Verrohrung; die REGEL selbst ist ausschliesslich der extrahierte Code.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    A1_AUTO_77, A2_AUTO_77, AUTO_VERSCHMELZUNG_SCHWELLE, P9_BODEN_RECLAIM,
    PLATEAU_MAX_BARS, PLATEAU_MIN_BARS, PLATEAU_REFERENZ_BARS,
    PhasenKanteInfo, PhasenSegmentEintrag,
)

E34 = ROOT / "test" / "_tmp_e34_auto.py"
ENGINE = ROOT / "test" / "tmp_kanten_engine_replay.py"

ok = True
FUNKTIONEN = ("_lebt_kausal", "ecken", "_nah", "zusammenfassen")

print("=" * 96)
print("1b.2  REKONSTRUKTION DER ENDOGENEN SEGMENTBILDUNG (read-only)")
print("=" * 96)
print(f"Quelle : {E34.name}  {E34.stat().st_size:,} B  "
      f"SHA256 {hashlib.sha256(E34.read_bytes()).hexdigest()[:24]}...")

# --- AST-Extraktion (wortsetzlich, ohne Modul-Seiteneffekte) ----------------
_quelle = E34.read_text(encoding="utf-8")
_tree = ast.parse(_quelle)
_ns: Dict[str, object] = {
    "Dict": Dict, "List": List, "Optional": Optional, "Tuple": Tuple,
}
gefunden = []
for _node in _tree.body:
    if isinstance(_node, ast.FunctionDef) and _node.name in FUNKTIONEN:
        _src = ast.get_source_segment(_quelle, _node)
        assert _src is not None, _node.name
        assert _src in _quelle, f"{_node.name}: Segment nicht wortgleich"
        exec(compile(_src, f"<extract:{_node.name}>", "exec"), _ns)  # noqa: S102
        gefunden.append(_node.name)
fehlend = [f for f in FUNKTIONEN if f not in gefunden]
if fehlend:
    ok = False
    print(f"  [FAIL] nicht extrahiert: {fehlend}")
else:
    print(f"  [OK ] extrahiert (wortgleich): {', '.join(gefunden)}")

# Der einzige Modul-Global der Regel ist ``SEG_LAST`` (Default False, da kein
# ``--seglast`` auf der Kommandozeile); arretierter Zustand.
_ns["SEG_LAST"] = False

# --- Engine-Scan (nur Datenbeschaffung, kein Renderer/Plot) -----------------
_spec = importlib.util.spec_from_file_location("eng", ENGINE)
eng = importlib.util.module_from_spec(_spec)
sys.modules["eng"] = eng
_spec.loader.exec_module(eng)  # type: ignore[union-attr]
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n
alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {e.kid: e for e in alle}
_ns["alle"] = alle
_ns["katalog"] = katalog
_ns["LIVE"] = cfg.wall_live_bars
_ns["BAND"] = cfg.touch_band_pct

START = P9_BODEN_RECLAIM.end_bar + 1          # = 1021, abgeleitet (kein Literal)
print(f"  n = {n} | LIVE = {_ns['LIVE']} | BAND = {_ns['BAND']} % | "
      f"START = {START} (P9.end_bar + 1)")

# --- Treiber: Wechselpunkte + Rohsegmente (Verrohrung) ----------------------
_ecken = _ns["ecken"]
_zusammen = _ns["zusammenfassen"]


def _rohsegmente() -> List[List[int]]:
    """Rohsegmente [a, b, decke_kid, boden_kid] aus der extrahierten Regel."""
    wechsel: List[Tuple[int, Optional[int], Optional[int]]] = []
    vor: Tuple[Optional[int], Optional[int]] = (None, None)
    for _k in range(2, n):
        _cur = _ecken(_k)  # type: ignore[operator]
        if _cur != vor:
            wechsel.append((_k, _cur[0], _cur[1]))
            vor = _cur
    roh: List[List[int]] = []
    for (_k, _ko, _ku) in wechsel:
        if _k < START or _ko is None or _ku is None:
            continue
        if roh:
            roh[-1][1] = _k - 1
        roh.append([_k, n - 1, _ko, _ku])
    return roh


roh = _rohsegmente()
print(f"\n  Rohsegmente ({len(roh)}):")
for (a, b, ko, ku) in roh:
    print(f"    {a:>5}..{b:<5} ({b - a + 1:>4} Bars)  K{ko}/K{ku}")


def _rekonstruiere(schwelle: int) -> List[PhasenSegmentEintrag]:
    """Adapter-Eintraege aus ``zusammenfassen(roh, schwelle)`` bauen."""
    segs = _zusammen([list(s) for s in roh], schwelle)  # type: ignore[operator]
    out: List[PhasenSegmentEintrag] = []
    for _i, (a, b, ko, ku) in enumerate(segs):
        _o, _u = katalog[ko], katalog[ku]
        out.append(PhasenSegmentEintrag(
            phasen_id=f"A{_i + 1}",
            start_bar=int(a), end_bar=int(b),
            decke=PhasenKanteInfo(kid=int(ko),
                                  provenienz_basis=float(_o.basis_bei(a))),
            boden=PhasenKanteInfo(kid=int(ku),
                                  provenienz_basis=float(_u.basis_bei(a))),
            ziel_preis_short=float(_u.basis_bei(a)),
            ziel_preis_long=float(_o.basis_bei(a))))
    return out


def _struktur(segs: List[PhasenSegmentEintrag]) -> List[Tuple[int, int, int, int]]:
    return [(s.start_bar, s.end_bar, s.decke.kid, s.boden.kid) for s in segs]


# --- 1) Identitaet bei der arretierten Schwelle -----------------------------
print("\n" + "-" * 96)
print(f"2) IDENTITAET bei AUTO_VERSCHMELZUNG_SCHWELLE = "
      f"{AUTO_VERSCHMELZUNG_SCHWELLE}")
print("-" * 96)
recon = _rekonstruiere(AUTO_VERSCHMELZUNG_SCHWELLE)
soll = [
    dataclasses.replace(A1_AUTO_77, phasen_id="A1"),
    dataclasses.replace(A2_AUTO_77, phasen_id="A2"),
]
if len(recon) != len(soll):
    ok = False
    print(f"  [FAIL] Segmentzahl {len(recon)} != {len(soll)}")
for _i, (_r, _s) in enumerate(zip(recon, soll)):
    gleich = (_r == _s)
    ok = ok and gleich
    print(f"  A{_i + 1}: {_r.start_bar}..{_r.end_bar} K{_r.decke.kid}/K{_r.boden.kid}"
          f"  <-> Adapter {_s.start_bar}..{_s.end_bar} "
          f"K{_s.decke.kid}/K{_s.boden.kid}   {'IDENTISCH' if gleich else 'ABWEICHUNG'}")
    if not gleich:
        for _f in dataclasses.fields(_r):
            _a = getattr(_r, _f.name)
            _b = getattr(_s, _f.name)
            if _a != _b:
                print(f"      Feld {_f.name}: recon={_a!r} adapter={_b!r}")
print(f"  -> bar- UND kantenidentisch: {'JA' if ok else 'NEIN'}")

# Gegenprobe: Provenienz-Basen exakt die kausale Basis am Segmentstart
print("\n  Provenienz-Gegenprobe (Basis am Segmentstart, Abweichung 0.0 %):")
for _s in (A1_AUTO_77, A2_AUTO_77):
    for _k, _seite in ((_s.decke, "OBEN"), (_s.boden, "UNTEN")):
        _ist = float(katalog[_k.kid].basis_bei(_s.start_bar))
        _pct = abs(_ist - _k.provenienz_basis) / _k.provenienz_basis * 100.0
        _hit = _pct < 1e-9
        ok = ok and _hit
        print(f"    {_s.phasen_id:<12} K{_k.kid:<3} {_seite:<5} "
              f"provenienz={_k.provenienz_basis:.4f} ist={_ist:.4f} "
              f"({_pct:.6f} %)  {'OK' if _hit else 'ABWEICHUNG'}")

# --- 3) Klippen- und Plateaukontrollen --------------------------------------
print("\n" + "-" * 96)
print("3) SCHWELLEN-STRESS (Struktur) / Klippen bei 40 -> 41 und 114 -> 115")
print("-" * 96)
ERWARTET = {
    40: ("Klippe1", None),
    41: ("3 Segmente", [(1033, 1123, 67, 82), (1124, 1173, 73, 85),
                        (1174, 1287, 73, 82)]),
    77: ("2 Segmente (arretiert)", [(1033, 1173, 67, 82), (1174, 1287, 73, 82)]),
    114: ("2 Segmente", [(1033, 1173, 67, 82), (1174, 1287, 73, 82)]),
    115: ("1 Segment (Klippe2)", [(1033, 1287, 67, 82)]),
}
strukturen: Dict[int, list] = {}
for wert in (40, 41, 77, 114, 115):
    st = _struktur(_rekonstruiere(wert))
    strukturen[wert] = st
    label, soll_st = ERWARTET[wert]
    print(f"  MIN {wert:>3}: {len(st)} Segment(e)  {st}   [{label}]")
    if soll_st is not None and st != soll_st:
        ok = False
        print(f"           [FAIL] erwartet {soll_st}")

print("\n  Klippen-Kontrollen:")
paare = ((40, 41), (114, 115))
for _a, _b in paare:
    wechsel = strukturen[_a] != strukturen[_b]
    ok = ok and wechsel
    print(f"    {_a} -> {_b}: Strukturwechsel = {wechsel} "
          f"({'OK' if wechsel else 'FAIL'})")
# Plateau-Invarianz der STRUKTUR ist NICHT gefordert (41..48 = 3 Segmente);
# gefordert ist, dass 77 und 114 dieselbe Struktur liefern.
_same = strukturen[77] == strukturen[114]
ok = ok and _same
print(f"    77 == 114 (Struktur): {_same} ({'OK' if _same else 'FAIL'})")

# --- 4) SSoT-Konsistenz -----------------------------------------------------
print("\n" + "-" * 96)
print("4) SSoT-KONSISTENZ")
print("-" * 96)
_sso = (AUTO_VERSCHMELZUNG_SCHWELLE == PLATEAU_REFERENZ_BARS
        and PLATEAU_MIN_BARS <= AUTO_VERSCHMELZUNG_SCHWELLE
        <= PLATEAU_MAX_BARS)
ok = ok and _sso
print(f"  Schwelle {AUTO_VERSCHMELZUNG_SCHWELLE} in "
      f"[{PLATEAU_MIN_BARS}, {PLATEAU_MAX_BARS}], == Referenz: "
      f"{'OK' if _sso else 'FAIL'}")

print(f"\nGESAMT: {'OK' if ok else 'FEHLER'}")
raise SystemExit(0 if ok else 1)
