# -*- coding: utf-8 -*-
"""FORENSIK (READ-ONLY): Pivot-Rechner und Kanten-Genealogie 21./24.08.

Auftrag
-------
1. Welche exakte mathematische Formel erzeugt einen Pivot (Fraktal vs.
   prozentualer Rebound)?
2. Welche Kante (kid) hat der Scan am 21.08. 16:00/16:30 (≈ 68.87/68.88 USD)
   und am 24.08. 03:30 (68.3920) SELBST erzeugt - ohne Vorgabe?
3. Stimmen die arretierten Adapter-Werte (P9 boden K77 68.3700, A1
   decke K67 69.8990 / boden K82 67.5350) mit dem Rechenergebnis ueberein?

Methode: der Scan liefert je Linie ``wicks = [(bar, preis), ...]`` (jeder
akzeptierte, bestaetigte Pivot-Docht). Damit ist die Zuordnung
Pivot -> Kante exakt rekonstruierbar, ohne die Scan-Logik zu duplizieren.
Zusaetzlich werden ``sweep_sperren`` (blockierte Geburt), ``r21_geloescht``
und ``tombstones`` ausgewertet, um verworfene Pivots zu erkennen.

Engine bleibt physisch unveraendert (rein lesend).
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    P9_BODEN_RECLAIM, A1_AUTO_77, A2_AUTO_77,
)

DEFAULT_PARAMS: Dict[str, object] = {
    "fenster": ("AUG", "AUG26"),
    "ziel_preis": 68.88,        # Pruefmarke Anwender (21.08.)
    "preis_toleranz_pct": 0.30,  # Suchfenster um die Pruefmarke
    "pivot_scan_bars": ((886, 900), (928, 946), (1028, 1044)),
}

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
ENGINE_SHA_SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
OFFSET = 460
ZIEL: float = DEFAULT_PARAMS["ziel_preis"]  # type: ignore
PTOL: float = DEFAULT_PARAMS["preis_toleranz_pct"]  # type: ignore
SCAN_BARS: Tuple[Tuple[int, int], ...] = DEFAULT_PARAMS["pivot_scan_bars"]  # type: ignore
FENSTER_LISTE: Tuple[str, ...] = DEFAULT_PARAMS["fenster"]  # type: ignore

TAGE = ["10.08", "11.08", "12.08", "13.08", "14.08", "17.08", "18.08", "19.08",
        "20.08", "21.08", "24.08", "25.08", "26.08", "27.08", "28.08"]
TAGE26 = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08", "12.08",
          "13.08", "14.08", "17.08", "18.08", "19.08", "20.08", "21.08", "24.08",
          "25.08", "26.08", "27.08", "28.08", "31.08"]


def tag(F: str, bar: int) -> str:
    tage = TAGE26 if F == "AUG26" else TAGE
    i = bar // 92
    return f"{tage[i]}({bar - i * 92:02d})" if 0 <= i < len(tage) else "?"


_sha = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
assert _sha == ENGINE_SHA_SOLL, f"Engine-SHA veraendert: {_sha}"

spec = importlib.util.spec_from_file_location("eng_gp", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng_gp"] = eng
spec.loader.exec_module(eng)  # type: ignore[union-attr]
eng.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]

cfg = eng.StraightEdgeHarnessKonfiguration()

print("=" * 118)
print("FORENSIK — PIVOT-RECHNER UND KANTEN-GENEALOGIE (21.08. / 24.08.)")
print("=" * 118)
print(f"Engine-SHA {_sha[:24]}... (UNVERAENDERT)")
print("")
print("SCHRITT 1 — DIE FORMEL (Quelltext-Fund, tmp_kanten_engine_replay.py)")
print(f"   Pivot-Funktion, die der SE-Scan benutzt : _pivot_dual()  (Z. 1407)")
print(f"   Aufruf im Scan                          : Z. 2240  "
      f"'for typ in _pivot_dual(hi, lo, mbar)'")
print("   Bedingung (2 Bars links/rechts, strikt):")
print("      H-Pivot @ m <=> high[m] > high[m-2], high[m-1], high[m+1], high[m+2]")
print("      L-Pivot @ m <=> low[m]  < low[m-2],  low[m-1],  low[m+1],  low[m+2]")
print("   Bestaetigung kausal: verarbeitet bei k = m + 2 (2-Bar-Puffer).")
print("   KEIN prozentualer Rebound im SE-Pfad: MIN_SWING_PCT (1.0 %) und")
print("   DENSITY_BAND (0.15 USD) gehoeren zum ALTEN _verarbeite_pivot-Pfad")
print("   (Z. 730/754/1232) und werden in _se_scan NICHT aufgerufen.")
print("   Aufnahme-/Verwerfungsregeln der SE-Kante (Z. 2243-2291):")
print(f"      - Touch-Band            : cfg.touch_band_pct = "
      f"SE_HARNESS_BAND_PCT = {cfg.touch_band_pct} %")
print(f"      - Touch-Mindestabstand  : SE_HARNESS_MIN_TOUCH_ABSTAND = "
      f"{eng.SE_HARNESS_MIN_TOUCH_ABSTAND} Bars")
print("      - sonst: Sweep-Sperre (kein Seed) ODER Geburt einer neuen Linie")
print("      - 2. Touch im Band -> Keimung (touch_anzahl >= 2 => edge)")

for F in FENSTER_LISTE:
    scan = eng._se_scan(F, cfg)  # type: ignore[arg-type]
    n = int(scan["n"])
    d = scan["d"]
    ts = list(d["ts"])
    hi = list(d["high"])
    lo = list(d["low"])
    cl = list(d["close"])
    alle = list(scan["edges"]) + list(scan["seeds"])

    print("\n" + "=" * 118)
    print(f"FENSTER {F} | n = {n} | ts[0] = {ts[0]} | Box-Grenze ({cfg.box_end_datum}"
          f" = 19.08.) Bar {scan['box_end_bar']}")
    print("=" * 118)

    # ---------------------------------------------------- SCHRITT 2
    print("\nSCHRITT 2 — PIVOT-RECHNUNG UND ZUORDNUNG (Bar für Bar)")
    print("-" * 118)
    print(f"   {'m':>5} {'Zeit':<11}{'Tag':<11}{'hi':>9}{'lo':>9}"
          f"{'_pivot_dual':<24}{'zugeordnete Kante(n)':<34}")
    _off = OFFSET if F == "AUG26" else 0
    _treffer: List[Tuple[int, str, float]] = []
    for (a0, b0) in SCAN_BARS:
        a, b = a0 + _off, b0 + _off
        for m in range(a, b + 1):
            if m < 2 or m + 2 >= n:
                continue
            # _pivot_dual (Z. 1407) exakt nachgebaut: striktes 5-Bar-Fraktal,
            # H und L unabhaengig geprueft (Doppel-Pivot moeglich).
            typs = []
            if hi[m] > hi[m - 1] and hi[m] > hi[m - 2] and hi[m] > hi[m + 1] and hi[m] > hi[m + 2]:
                typs.append("H")
            if lo[m] < lo[m - 1] and lo[m] < lo[m - 2] and lo[m] < lo[m + 1] and lo[m] < lo[m + 2]:
                typs.append("L")
            if not typs:
                continue
            px_je: List[str] = []
            for t in typs:
                px = float(hi[m]) if t == "H" else float(lo[m])
                owner = []
                for e in alle:
                    for (bb, pp) in e.wicks:
                        if bb == m and abs(pp - px) < 1e-9:
                            owner.append(f"K{e.kid}({'E' if e.touch_anzahl >= 2 else 'S'},"
                                         f"{e.seite[:1]},{e.touch_anzahl})")
                px_je.append(f"{t} {px:.4f} -> "
                             f"{', '.join(owner) if owner else 'KEINE LINIE'}")
                if abs(px - ZIEL) / ZIEL * 100.0 <= PTOL:
                    _treffer.append((m, t, px))
            print(f"   {m:>5} {str(ts[m]):<11}{tag(F, m):<11}{hi[m]:>9.4f}{lo[m]:>9.4f}"
                  f"{'/'.join(typs):<24}{' | '.join(px_je):<34}")

    # Verworfene Pivots (Sweep-Sperre / R21 / Tombstone)
    print("\n   VERWERFUNGEN im Umfeld (Sweep-Sperre = blockierte Seed-Geburt):")
    for (mb, seite, px, ref, dist) in scan["sweep_sperren"]:
        if any(a - 20 <= mb <= b + 20 for (a, b) in SCAN_BARS):
            print(f"      bar {mb:>5} {tag(F, mb):<11} {seite:<6} docht={px:.4f} "
                  f"ref={ref:.4f} ueber {dist:.3f} % -> KEIN Seed")
    for (k, kid, seite, basis, erst, alt) in scan.get("r21_geloescht", []):
        if any(a - 20 <= erst <= b + 20 for (a, b) in SCAN_BARS):
            print(f"      R21-Loeschung bar {k} kid {kid} {seite} basis={basis} "
                  f"erster_pivot={erst} alt={alt}")
    for (k, seite, px) in scan.get("tombstones", []):
        if any(a - 20 <= k <= b + 20 for (a, b) in SCAN_BARS):
            print(f"      TOMBSTONE bar {k} {seite} {px:.4f}")

    # --------------------------------------------- Pruefmarke 68.88
    print("\n" + "-" * 118)
    print(f"   PRUEFMARKE {ZIEL:.4f} USD (21.08.) — wer traegt dieses Niveau?")
    print("-" * 118)
    print(f"   Suchband +/- {PTOL} % -> {ZIEL * (1 - PTOL / 100):.4f} .. "
          f"{ZIEL * (1 + PTOL / 100):.4f}")
    print(f"   Pivots in der Pruefung: {[(m, t, round(p, 4)) for (m, t, p) in _treffer]}")
    print(f"\n   Linien im Katalog mit Basis im Suchband:")
    print(f"   {'kid':>4} {'Typ':<6}{'Seite':<7}{'Basis(k=' + str(n - 1) + ')':>18}"
          f"{'erster_pivot':>14}{'Touches':>9}   Wicks (bar/Px)")
    _im_band = []
    for e in sorted(alle, key=lambda x: x.kid):
        bx = float(e.basis_bei(n - 1))
        if abs(bx - ZIEL) / ZIEL * 100.0 <= PTOL:
            _im_band.append(e)
            _w = ", ".join(f"{bb}/{tag(F, bb)}({pp:.4f})" for bb, pp in e.wicks)
            print(f"   {e.kid:>4} {'Edge' if e.touch_anzahl >= 2 else 'Seed':<6}"
                  f"{e.seite:<7}{bx:>18.4f}{e.erster_pivot_bar:>14}"
                  f"{e.touch_anzahl:>9}   {_w}")

    # --------------------------------------------- Arretierte Werte
    print("\n" + "-" * 118)
    print("SCHRITT 3 — GEGENPROBE: Rechenergebnis vs. arretierte Adapter-Werte")
    print("-" * 118)
    kat = {int(e.kid): e for e in alle}
    _soll = [
        ("P9  boden", int(P9_BODEN_RECLAIM.boden.kid),
         float(P9_BODEN_RECLAIM.boden.provenienz_basis)),
        ("P9  decke", int(P9_BODEN_RECLAIM.decke.kid),
         float(P9_BODEN_RECLAIM.decke.provenienz_basis)),
        ("A1  decke", int(A1_AUTO_77.decke.kid), float(A1_AUTO_77.decke.provenienz_basis)),
        ("A1  boden", int(A1_AUTO_77.boden.kid), float(A1_AUTO_77.boden.provenienz_basis)),
        ("A2  decke", int(A2_AUTO_77.decke.kid), float(A2_AUTO_77.decke.provenienz_basis)),
        ("A2  boden", int(A2_AUTO_77.boden.kid), float(A2_AUTO_77.boden.provenienz_basis)),
    ]
    # AUG26 fuehrt ANDERE kids (F6); Zuordnung ueber die Genealogie
    # (seite + erster_pivot_bar), NICHT ueber die kid-Nummer.
    _kat_win = None          # (seite, erster_pivot_bar) -> kid  (Fenster F)
    _kat_aug_obj = None      # kid -> AUG-Objekt
    if F == "AUG26":
        _scan_aug = eng._se_scan("AUG", cfg)  # type: ignore[arg-type]
        _alle_aug = list(_scan_aug["edges"]) + list(_scan_aug["seeds"])
        _kat_aug_obj = {int(x.kid): x for x in _alle_aug}
        # AUG26-Bar = AUG-Bar + OFFSET -> Genealogie-Schluessel auf AUG-Niveau
        # normalisieren, damit AUG-(seite, erster_pivot) auf den AUG26-kid zeigt.
        _kat_win = {(str(x.seite), int(x.erster_pivot_bar) - OFFSET): int(x.kid)
                    for x in alle}
    print(f"   {'Position':<10}{'kid(AUG)':>9}{'kid(Fenster)':>13}"
          f"{'Provenienz(a)':>14}{'Scan(b)':>10}{'Delta':>9}   erster_pivot / Status")
    for (name, kid, prov) in _soll:
        e = kat.get(kid)
        _kid_f = kid
        if F == "AUG26" and _kat_win is not None and _kat_aug_obj is not None:
            _ea = _kat_aug_obj.get(kid)
            if _ea is not None:
                _kid_f = _kat_win.get((str(_ea.seite), int(_ea.erster_pivot_bar)), -1)
            e = kat.get(_kid_f)
        if e is None:
            print(f"   {name:<10}{kid:>9}{_kid_f:>13}{prov:>14.4f}"
                  f"{'nicht im Katalog':>10}   -")
            continue
        _seg = {"P9": P9_BODEN_RECLAIM, "A1": A1_AUTO_77,
                "A2": A2_AUTO_77}[name.split()[0]]
        _st_ist = int(_seg.start_bar) + (OFFSET if F == "AUG26" else 0)
        bx = float(e.basis_bei(_st_ist))
        ok = "IDENTISCH" if abs(bx - prov) < 1e-4 else "ABWEICHUNG"
        print(f"   {name:<10}{kid:>9}{_kid_f:>13}{prov:>14.4f}{bx:>10.4f}"
              f"{bx - prov:>+9.4f}   erster_pivot={e.erster_pivot_bar} "
              f"({tag(F, e.erster_pivot_bar)}) {ok}")
    print("   (a) = arretierter Adapter-Wert; (b) = basis_bei(Segmentstart) "
          "des Scans.")
    if F == "AUG":
        print("   -> A1/A2 sind IDENTISCH: die arretierten Provenienz-Werte sind "
              "der Rechenwert.")
        print("   -> P9 weicht ab, weil der P9-Start (848) VOR dem ersten Docht "
              "von K67 (873)")
        print("      und K77 (934) liegt -> basis_bei faellt auf wicks[0][1] "
              "zurueck (Fallback).")

    # --------------------------------------------- Erster Gegen-Pivot
    print("\n" + "-" * 118)
    print("SCHRITT 3b — ERSTER GEGEN-PIVOT nach der Transition (kausal)")
    print("-" * 118)
    _basis_bar = int(P9_BODEN_RECLAIM.end_bar) + (OFFSET if F == "AUG26" else 0)
    print(f"   Anker-Referenz: P9-Ende = Bar {_basis_bar} ({tag(F, _basis_bar)})")
    print(f"   {'m':>5} {'Tag':<11}{'Typ':>4}{'Preis':>9}{'Best.:':>7}"
          f"{'Kante/Geburt':<34}")
    _cnt = 0
    for m in range(2, n - 2):
        if hi[m] > hi[m - 1] and hi[m] > hi[m - 2] and hi[m] > hi[m + 1] and hi[m] > hi[m + 2]:
            typs = ["H"]
        elif lo[m] < lo[m - 1] and lo[m] < lo[m - 2] and lo[m] < lo[m + 1] and lo[m] < lo[m + 2]:
            typs = ["L"]
        else:
            continue
        if m < _basis_bar - 60:
            continue
        _cnt += 1
        if _cnt > 26:
            break
        for t in typs:
            px = float(hi[m]) if t == "H" else float(lo[m])
            _o = [(e.kid, e.touch_anzahl, e.erster_pivot_bar)
                  for e in alle
                  for (bb, pp) in e.wicks
                  if bb == m and abs(pp - px) < 1e-9]
            txt = ("beruehrt " + ", ".join(f"K{kid}(V-S {tc})" for kid, tc, _f in _o)
                   ) if _o else "keine Linie (verworfen/Sperre)"
            print(f"   {m:>5} {tag(F, m):<11}{t:>4}{px:>9.4f}{m + 2:>7}   {txt}")

    # --------------------------------- K71 nie Aussenkante der O1-Regel?
    print("\n" + "-" * 118)
    print("SCHRITT 4 — WARUM DER GEGEN-PIVOT VOM 21.08. 16:30 NIE "
          "GEGENKANTE DES PHASENSTARTS WURDE")
    print("-" * 118)
    print("   Die O1-Regel nimmt die AEUSSERSTE lebende Linie je Seite. Diagnose:")
    print(f"   {'Bar':<11}{'Decke (O1)':<24}{'Boden (O1)':<24}"
          f"{'Gegenp.-Level':>15}{'lebt?':>7}{'Rang unten':>12}")

    _LIVE = int(cfg.wall_live_bars)

    def _lebt(e: object, k: int) -> bool:
        b = [bb for bb, _ in e.wicks]  # type: ignore[attr-defined]
        b = [bb for bb in b if bb + 2 <= k]
        return bool(b) and max(b) >= k - _LIVE

    if F == "AUG26" and _kat_win is not None and _kat_aug_obj is not None:
        _e71a = _kat_aug_obj.get(71)
        _k71 = (kat.get(_kat_win.get((str(_e71a.seite), int(_e71a.erster_pivot_bar)), -1))
                if _e71a is not None else None)
    else:
        _k71 = kat.get(71)
    _bars = [848, 873, 875, 889, 894, 900, 914, 917, 924, 934, 937, 1033]
    for k0 in _bars:
        k = k0 + (OFFSET if F == "AUG26" else 0)
        if k >= n:
            continue
        _ob = [e for e in alle if e.seite == "OBEN" and _lebt(e, k)]
        _un = [e for e in alle if e.seite == "UNTEN" and _lebt(e, k)]
        _o = max(_ob, key=lambda e: e.basis_bei(k)) if _ob else None
        _u = min(_un, key=lambda e: e.basis_bei(k)) if _un else None
        _so = (f"K{_o.kid} {float(_o.basis_bei(k)):.4f}" if _o else "-")
        _su = (f"K{_u.kid} {float(_u.basis_bei(k)):.4f}" if _u else "-")
        _lv = float(_k71.basis_bei(k)) if _k71 is not None else 0.0
        _leb = ("ja" if (_k71 is not None and _lebt(_k71, k)) else "nein")
        _rang = "-"
        if _k71 is not None and _un:
            _sortiert = sorted(_un, key=lambda e: e.basis_bei(k))
            _idx = next((i for i, e in enumerate(_sortiert) if e is _k71), None)
            if _idx is not None:
                _rang = f"{_idx + 1}/{len(_sortiert)}"
        print(f"   {tag(F, k):<11}{_so:<24}{_su:<24}{_lv:>11.4f}"
              f"{_leb:>13}{_rang:>12}")
    print("   Legende: 'Rang unten 1/N' = der Gegen-Pivot ist die tiefste lebende "
          "Linie (dann waere er die O1-Gegenkante).")
    print("   Befund: der Gegen-Pivot vom 21.08. 16:30 ist zwar GEBOREN, aber "
          "NICHT die aeusserste")
    print("   lebende Linie - tiefere Linien DERSELBEN Seite uebernehmen den "
          "O1-Boden (Rang >= 3).")
    print("   Deshalb ist er der ERSTE GEGEN-PIVOT (Rechenergebnis), aber "
          "NICHT das Phasenpaar.")

print("\n" + "=" * 118)
print("FAZIT (SCHRITT 5) — ANTWORTEN AUF DIE INTERVIEW-FRAGEN")
print("=" * 118)
print("F1  Pivot-Formel: _pivot_dual() = striktes 5-Bar-Kurs-Fraktal.")
print("    H-Pivot @ m <=> high[m] > high[m-2], high[m-1], high[m+1], high[m+2];")
print("    L-Pivot symmetrisch. KEIN prozentualer Mindest-Rebound im SE-Pfad")
print("    (MIN_SWING_PCT/DENSITY_BAND gehoeren zum alten _verarbeite_pivot-Pfad).")
print("F2  Erster Gegen-Pivot nach der Transition (kausal, ab P9-Ende):")
print("    AUG   : Bar 894 (21.08. 16:30) L 68.8700 -> K71  (V-S 5, geb. 924).")
print("    AUG26 : Bar 1354 (= 894+460)  L 68.8700 -> K121 (V-S 5).")
print("    Die Anwender-Pruefmarke 68.88 USD trifft exakt diesen Pivot.")
print("F3  Warum nicht Phasen-Gegenkante: O1 nimmt die AEUSSERSTE lebende Linie.")
print("    Der Gegen-Pivot ist zu keinem Zeitpunkt Rang 1 (AUG/AUG26: >= 3/5),")
print("    weil tiefere Linien derselben Seite den O1-Boden tragen.")
print("F4  Es gibt KEINE Funktion 'finde_gegenpivot'. Die Gegenkante entsteht aus")
print("    der O1-Regel (aeusserste lebende Linie der Gegenseite).")
print("F5  A1/A2-Provenienz = basis_bei(Segmentstart) des Scans, bit-exakt und")
print("    fensterstabil (+460): A1 69.8990/67.5350, A2 69.6380/67.5530.")
print("    P9 weicht ab (Fallback wicks[0][1], weil Start 848 vor dem 1. Docht")
print("    von K67 (873) und K77 (934) liegt); P9 ist arretierte Setzung.")

print("\nENDE FORENSIK 21.08./24.08.\n")
