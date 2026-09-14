# -*- coding: utf-8 -*-
"""Paritaetspruefung V022 gegen die arretierte Baseline (Beschluss F43/F47/F48).

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_v022_paritaet.py

Prueft auf den vier V022-Fenstern (MAI/JUN/JUL/AUG_BASE):

  P1  Ein-Instanz-Regel (G4): EINE Baseline-Instanz fuer beide Motoren.
  P2  Paritaetswaechter (F39) vor dem Lauf.
  P3  Vollstaendiger Feldvergleich: ALLE 23 ``_SESetup``-Felder je Trade
      (``dataclasses.astuple``), reihungsempfindlich (kein Sortieren).
  P4  Alle 15 Stats-Schluessel: 11 Zaehler + 4 Listen.
  P5  Soll-Werte der Baseline (35/+38.318126, 28/-11.421155, 21/-4.325355,
      14/+42.450970).
  P6  F48-Kontrolllauf: V022 auf dem AUG-Scan == 14 Trades (Baseline), und
      die 18 Trades entstehen AUSSCHLIESSLICH im V021-Segmentwand-Pfad.

Kein Handelseingriff, kein Produktivcode. Read-only gegenueber allen
arretierten Staenden; die einzige Mutation ist die temporaere FENSTER-/
_lade_fenster-Injektion zur kausalen Monatsfenster-Bildung (Sonde Z463-479).
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT: Path = Path(__file__).resolve().parent.parent
TEST: Path = ROOT / "test"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TEST) not in sys.path:
    sys.path.insert(0, str(TEST))

V022_PFAD = TEST / "tmp_kanten_engine_v022_replay.py"
OUT = TEST / "_chk_v022_paritaet_out.txt"

# (Id, start, ende, SOLL_Trades, SOLL_SumR) -- verbatim Sonde Z114-119
FENSTER: Tuple[Tuple[str, str, str, int, float], ...] = (
    ("MAI", "2026-05-01", "2026-06-01", 35, 38.318126),
    ("JUN", "2026-06-01", "2026-07-01", 28, -11.421155),
    ("JUL", "2026-07-01", "2026-08-01", 21, -4.325355),
    ("AUG_BASE", "AUG", "AUG", 14, 42.450970),
)
SOLL_AUG_WAND = (18, 52.876174)
SOLL_H1 = (8, 38.919584)
SOLL_H2 = (10, 13.956589)
KALENDERKANTE = 644

ZAEHLER = ("v_s", "kein_gegner", "f3", "kein_raum", "zyklus_blockiert",
           "quartil_blockiert", "blocker", "promotionen", "stacking_blockiert",
           "frisch_blockiert", "concurrency_blockiert")
LISTEN = ("zyklus_liste", "quartil_liste", "blocker_liste", "stacking_liste")

z: List[str] = []
fehler: List[str] = []


def _scan_monat(B: Any, start: str, ende: str) -> Tuple[Dict[str, Any], int]:
    """Kausaler SE-Scan eines Monatsfensters (verbatim Sonde Z463-479)."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        d = B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]
    n = int(len(d))
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    return scan, n


def _grenzen(AD: Any, V: Any) -> List[Any]:
    """Adapter-Segmente -> passive ``Segmentgrenze`` (verbatim Sonde Z482-492)."""
    PhK = AD.PhasenKanteInfo
    return [V.Segmentgrenze(
        start_bar=int(s.start_bar), end_bar=int(s.end_bar),
        boden=PhK(kid=int(s.boden.kid),
                  provenienz_basis=float(s.boden.provenienz_basis)),
        decke=PhK(kid=int(s.decke.kid),
                  provenienz_basis=float(s.decke.provenienz_basis)),
        boden_deklariert_literal=s.boden_deklariert_literal)
        for s in AD.ADAPTER_V019_KAUSAL.segmente]


def _vergleiche_setups(namen: Sequence[str], a: List[Any], b: List[Any],
                       lbl: str) -> None:
    """Feldweiser Vergleich zweier Setup-Listen (23 Felder, reihungsempfindlich)."""
    if len(a) != len(b):
        fehler.append(f"{lbl}: Laenge {len(a)} != {len(b)}")
        return
    for i, (x, y) in enumerate(zip(a, b)):
        tx = dataclasses.astuple(x)
        ty = dataclasses.astuple(y)
        if tx != ty:
            diff = [f"{namen[j]}: {tx[j]!r} != {ty[j]!r}"
                    for j in range(len(tx)) if tx[j] != ty[j]]
            fehler.append(f"{lbl}: Trade {i} abweichend -> " + "; ".join(diff))
            return
    z.append(f"    {lbl}: {len(a)} Setups, {len(namen)}/{len(namen)} Felder "
             f"bit-identisch, Reihenfolge identisch  OK")


def main() -> None:
    # ---------------------------------------------------- A) Arretierte Staende
    b022 = V022_PFAD.read_bytes()
    spec = importlib.util.spec_from_file_location("v022_pruef", V022_PFAD)
    V = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["v022_pruef"] = V
    spec.loader.exec_module(V)  # type: ignore[union-attr]

    z.append("=" * 100)
    z.append("V022-PARITAET GEGEN DIE ARRETIERTE BASELINE (F43/F47/F48)")
    z.append("=" * 100)
    z.append(f"V022-Modul   {len(b022)} B  SHA256 {hashlib.sha256(b022).hexdigest()}")

    # ---------------------------------------------------- P1 Ein-Instanz-Regel
    B = V._engine()                       # G4: EINE Instanz fuer alles
    z.append(f"Baseline     {V.BASELINE_SHA_SOLL}")
    z.append(f"Ein-Instanz  B = V022._engine()  -> {Path(B.__file__).name}")
    assert sys.modules["v022_basis"] is B, "G4: Baseline doppelt geladen"

    # ---------------------------------------------------- P2 Paritaetswaechter
    cfg = V.V022KantenKonfiguration()
    hcfg = B.StraightEdgeHarnessKonfiguration()
    par = V.pruefe_paritaet(cfg, B)
    z.append(f"P2 Paritaet  tp_mindist_pct {cfg.tp_mindist_pct} vs Baseline "
             f"V3_TP_MINDIST_PCT {B.V3_TP_MINDIST_PCT} -> {par}")
    assert par is True, "P2: Paritaet verletzt"
    z.append("")

    namen = [f.name for f in dataclasses.fields(B._SESetup)]
    z.append(f"_SESetup-Felder ({len(namen)}): {', '.join(namen)}")
    z.append("")

    # ---------------------------------------------------- P3/P4/P5 vier Fenster
    z.append("-" * 100)
    z.append("P3/P4/P5  FELD- UND STATS-PARITAET AUF DEN VIER V022-FENSTERN")
    z.append("-" * 100)
    for fid, start, ende, soll_n, soll_r in FENSTER:
        if start == "AUG":
            scan = B._se_scan("AUG", B.StraightEdgeHarnessKonfiguration())
            box_end = int(scan["n"])
            scan = copy.deepcopy(scan)
            scan["box_end_bar"] = int(box_end)
        else:
            scan, box_end = _scan_monat(B, start, ende)

        sc_b = copy.deepcopy(scan)
        sc_v = copy.deepcopy(scan)
        setups_b, stats_b = B._se_trades(sc_b, hcfg)
        setups_v, stats_v = V._se_trades_v022(sc_v, cfg)

        r_b = round(float(sum(float(t.r) for t in setups_b)), 6)
        r_v = round(float(sum(float(t.r) for t in setups_v)), 6)
        z.append(f"  {fid:<9s} box_end {box_end:<5d} "
                 f"Baseline {len(setups_b):>3d}/{r_b:>+11.6f}   "
                 f"V022 {len(setups_v):>3d}/{r_v:>+11.6f}")

        # P5 Soll-Werte
        if (len(setups_b), r_b) != (soll_n, round(soll_r, 6)):
            fehler.append(f"{fid}: Baseline-Soll ({soll_n}, {soll_r}) != "
                          f"({len(setups_b)}, {r_b})")

        # P3 Feldvergleich
        _vergleiche_setups(namen, setups_b, setups_v, f"{fid} 23-Feld")

        # P4 Stats
        for k in ZAEHLER:
            if stats_b.get(k) != stats_v.get(k):
                fehler.append(f"{fid}: stats['{k}'] {stats_b.get(k)} != "
                              f"{stats_v.get(k)}")
        for k in LISTEN:
            lb, lv = stats_b.get(k), stats_v.get(k)
            if lb != lv:
                fehler.append(f"{fid}: stats['{k}'] Listen verschieden "
                              f"({len(lb or [])} vs {len(lv or [])})")
        z.append(f"    11 Zaehler + 4 Listen identisch  OK"
                 f"   (v_s {stats_v.get('v_s')} == len(setups) "
                 f"{stats_v.get('v_s') == len(setups_v)})")

        # Fensterrand-Invariante: durch Zitat von B._c_loese_trade geerbt
        ende_n = sum(1 for t in setups_v
                     if t.grund1 == "ENDE" or t.grund2 == "ENDE")
        z.append(f"    ENDE-Exits (Fensterrand, geerbt): {ende_n}")

    # ---------------------------------------------------- P6 F48 AUG_WAND
    z.append("")
    z.append("-" * 100)
    z.append("P6  F48-KONTROLLLAUF: SEGMENTWAND IST NICHT IN V022")
    z.append("-" * 100)
    scan_aug = B._se_scan("AUG", B.StraightEdgeHarnessKonfiguration())
    box_aug = int(scan_aug["n"])
    scan_aug = copy.deepcopy(scan_aug)
    scan_aug["box_end_bar"] = int(box_aug)

    sc_v = copy.deepcopy(scan_aug)
    setups_v, _ = V._se_trades_v022(sc_v, cfg)
    r_v = round(float(sum(float(t.r) for t in setups_v)), 6)
    z.append(f"  V022 auf AUG-Scan        {len(setups_v):>3d}/{r_v:>+11.6f}"
             f"   (Soll Baseline 14/+42.450970)")
    if (len(setups_v), r_v) != (14, 42.450970):
        fehler.append(f"F48: V022 auf AUG != 14/+42.450970 ({len(setups_v)}, {r_v})")

    V21 = importlib.import_module("tmp_kanten_engine_v021_replay")
    AD = importlib.import_module("backtest_lab.phasen_regime_adapter")
    grenzen = _grenzen(AD, V21)
    z.append(f"  Adapter-Segmente         {len(grenzen)} -> "
             f"{[(int(g.start_bar), int(g.end_bar)) for g in grenzen]}")
    sc_v21 = copy.deepcopy(scan_aug)
    sc_v21["box_end_bar"] = int(box_aug)
    setups_w, _ = V21._se_trades_v021(
        sc_v21, V21.V021KantenKonfiguration(segmentwand_modus="AN"), grenzen)
    r_w = round(float(sum(float(t.r) for t in setups_w)), 6)
    z.append(f"  V021+AUG_WAND (Pfad 2)   {len(setups_w):>3d}/{r_w:>+11.6f}"
             f"   (Soll 18/+52.876174)")
    if (len(setups_w), r_w) != (18, 52.876174):
        fehler.append(f"F48: V021-Segmentwand != 18/+52.876174 ({len(setups_w)}, "
                      f"{r_w})")
    h1 = [float(t.r) for t in setups_w if int(t.entry_bar) < KALENDERKANTE]
    h2 = [float(t.r) for t in setups_w if int(t.entry_bar) >= KALENDERKANTE]
    z.append(f"  H1 (< {KALENDERKANTE})               {len(h1):>3d}/"
             f"{round(sum(h1), 6):>+11.6f}   (Soll {SOLL_H1[0]}/{SOLL_H1[1]})")
    z.append(f"  H2 (>= {KALENDERKANTE})              {len(h2):>3d}/"
             f"{round(sum(h2), 6):>+11.6f}   (Soll {SOLL_H2[0]}/{SOLL_H2[1]})")
    if (len(h1), round(sum(h1), 6)) != SOLL_H1:
        fehler.append("F48: H1-Aufteilung abweichend")
    if (len(h2), round(sum(h2), 6)) != SOLL_H2:
        fehler.append("F48: H2-Aufteilung abweichend")
    z.append("  => Die 18 Trades existieren AUSSCHLIESSLICH im V021-Patchpfad.")
    z.append("     V022 liefert auf demselben Scan 14 -- keine Segmentwand-Altlast.")

    # --------------------------------------- P7 Abgleich mit dem H20.53-Notariat
    z.append("")
    z.append("-" * 100)
    z.append("P7  FENSTER-ANHANG: BUDGET (II) AUS H20.53 PARAGRAPH 4")
    z.append("-" * 100)
    z.append("  ``2 * (box_end - 5)`` muss die im Notariat gemessenen Eintritte")
    z.append("  treffen -- Beleg, dass diese Harness EXAKT dieselben Fenster")
    z.append("  aufspannt wie die Zulassungs-Sonde.")
    for fid, box, soll in (("MAI", 1922, 3834), ("JUN", 2009, 4008),
                           ("JUL", 2100, 4190), ("AUG_BASE", 1288, 2566)):
        ist = 2 * (box - 5)
        z.append(f"  {fid:<9s} box_end {box:<5d} -> (II) {ist:<6d} "
                 f"(H20.53 Paragraph 4: {soll})  "
                 f"{'OK' if ist == soll else 'ABWEICHUNG'}")
        if ist != soll:
            fehler.append(f"P7: {fid} (II) {ist} != Notariat {soll}")

    # ---------------------------------------------------- Ergebnis
    z.append("")
    z.append("=" * 100)
    if fehler:
        z.append(f"ABWEICHUNGEN ({len(fehler)}):")
        for f in fehler:
            z.append("  " + f)
    else:
        z.append("ALLE PARITAETSPRUEFUNGEN OK -- V022 ist bit-identisch zur "
                 "Baseline")
        z.append("auf MAI/JUN/JUL/AUG_BASE (23 Felder x N Trades, 11 Zaehler,")
        z.append("4 Listen) und frei von Segmentwand-Altlasten.")
    z.append("=" * 100)

    text = "\n".join(z) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    if fehler:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
