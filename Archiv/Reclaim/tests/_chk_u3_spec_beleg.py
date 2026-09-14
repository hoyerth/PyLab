# -*- coding: utf-8 -*-
"""U3-Spezifikationsbeleg -- NAECHSTE Gegenkante, CRV-Klammer, ATR-Lage.

Read-only Reconnaissance fuer die U3-Spezifikation (I3). KEIN Engine-Eingriff,
keine Variantenkonstruktion im Motor: ausgewertet werden die Setups des
arretierten DEFAULT-Pfades, danach wird jeder Trade einzeln mit dem NEUEN
Zielpreis nachgerechnet (reine Funktion ``_c_loese_trade``).

Beantwortet werden vier offene Spezifikationsfragen:

F1  Gibt es ueberhaupt einen ATR? (Grundlage der Klammer 0.50 * ATR)
F2  Wie gross ist ATR(14) M15 kausal -- bindet 0.50*ATR oder 1.5*|entry-sl|?
F3  Wieviel CRV bietet die NAECHSTE Gegenkante? (Verteilung)
F4  Was kostet/ertraegt der Wechsel Extremum -> Naechste je Fenster?
    (Einzeltrade-Nachrechnung; Mengengeruest bleibt unveraendert)

ACHTUNG zur Aussagekraft: das Mengengeruest (welche Setups ueberhaupt
entstehen) bleibt das der Baseline. Nur die Aufloesung JE TRADE wird mit
dem neuen Zielpreis wiederholt. Die Zahlen sind deshalb eine
ERSTE-ORDNUNG-Schaetzung, keine vollstaendige Simulation.

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_u3_spec_beleg.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

V = importlib.import_module("tmp_kanten_engine_v021_replay")

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")

FENSTER: Tuple[Tuple[str, str, str], ...] = (
    ("MAI", "2026-05-01", "2026-06-01"),
    ("JUN", "2026-06-01", "2026-07-01"),
    ("JUL", "2026-07-01", "2026-08-01"),
)
CRV_STUFEN = (1.0, 1.5, 2.0, 3.0)

OUT = ROOT / "test" / "_chk_u3_spec_beleg_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _atr_wilder(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray,
                periode: int) -> np.ndarray:
    """Kausaler ATR (Wilder) -- nur zur Groessenordnung, nicht im Motor."""
    n = len(cl)
    tr = np.empty(n, dtype=float)
    tr[0] = hi[0] - lo[0]
    for i in range(1, n):
        a = hi[i] - lo[i]
        b = abs(hi[i] - cl[i - 1])
        c = abs(lo[i] - cl[i - 1])
        tr[i] = max(a, b, c)
    atr = np.full(n, np.nan, dtype=float)
    if n <= periode:
        return atr
    atr[periode] = float(np.mean(tr[1:periode + 1]))
    for i in range(periode + 1, n):
        atr[i] = (atr[i - 1] * (periode - 1) + tr[i]) / periode
    return atr


def main() -> None:
    _z("U3-SPEZIFIKATIONSBELEG (read-only, Baseline-Pfad)")
    _z("=" * 100)
    ist = _sha(BASELINE_PFAD)
    assert ist == BASELINE_SHA, f"Fremdstand Baseline: {ist[:16]}"
    _z(f"SHA Baseline  {ist[:16]}...  OK")
    _z("")

    B = V._engine()
    cfg_h = B.StraightEdgeHarnessKonfiguration()
    cfg_def = V.V021KantenKonfiguration()

    # ------------------------------------------------------------ F1
    _z("F1 -- Existiert ein ATR in der Engine?")
    quell = BASELINE_PFAD.read_text(encoding="utf-8")
    import re as _re
    treffer = [ln.strip() for ln in quell.splitlines()
               if _re.search(r"\bATR\b|\batr\b", ln)
               and "matrix" not in ln.lower()]
    _z(f"  Zeilen mit 'ATR'/'atr' (ohne --matrix-Kontext): {len(treffer)}")
    for ln in treffer[:6]:
        _z(f"     {ln[:96]}")
    _z("  -> ERGEBNIS: Es gibt KEINE ATR-Berechnung. 'atr_periode' ist ein")
    _z("     deklariertes, aber unbenutztes Vertragsfeld (H20.51 Paragraph 10).")
    _z("     Die Klammer '0.50 * ATR' ist damit derzeit NICHT implementierbar;")
    _z("     sie verlangt ein neues, kausales ATR -- offene Vorfrage (H20.51")
    _z("     Paragraph 13 F3, bisher unbeantwortet).")
    _z("")

    dossiers: Dict[str, Dict[str, Any]] = {}
    for lab, start, ende in FENSTER:
        B.FENSTER["LAB"] = (start, ende)
        try:
            d = B._lade_fenster("LAB")
        finally:
            del B.FENSTER["LAB"]
        o = B._lade_fenster
        B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
        try:
            scan = B._se_scan("LAB", cfg_h)
        finally:
            B._lade_fenster = o  # type: ignore
        scan = copy.deepcopy(scan)
        scan["box_end_bar"] = int(len(d))
        tr = V._lauf(copy.deepcopy(scan), cfg_def)
        dossiers[lab] = {"scan": scan, "trades": tr, "n": int(scan["n"])}

    # ------------------------------------------------------------ F2
    _z("=" * 100)
    _z("F2 -- Groessenordnung ATR(14) M15, kausal (nur Referenz)")
    _z(f"  {'Fenster':8s} {'ATR min':>9s} {'ATR med':>9s} {'ATR max':>9s}   "
       f"{'0.50*ATR med':>13s}   {'1.5*Risiko med':>15s}   bindet")
    for lab, start, ende in FENSTER:
        scan = dossiers[lab]["scan"]
        hi = scan["d"]["high"].to_numpy(dtype=float)
        lo = scan["d"]["low"].to_numpy(dtype=float)
        cl = scan["d"]["close"].to_numpy(dtype=float)
        atr = _atr_wilder(hi, lo, cl, 14)
        gueltig = atr[~np.isnan(atr)]
        tr = dossiers[lab]["trades"]
        med_atr = float(np.median(gueltig))
        med_risk = float(np.median([abs(float(t.sl) - float(t.entry))
                                    for t in tr]))
        a = 0.5 * med_atr
        b = 1.5 * med_risk
        bindet = "1.5*Risiko" if b > a else "0.50*ATR"
        _z(f"  {lab:8s} {gueltig.min():>9.4f} {med_atr:>9.4f} "
           f"{gueltig.max():>9.4f}   {a:>13.4f}   {b:>15.4f}   {bindet}")
    _z("")

    # ------------------------------------------------------------ F3
    _z("=" * 100)
    _z("F3/F4 -- NAECHSTE Gegenkante: CRV-Verteilung und Nachrechnung")
    _z("")
    for lab, start, ende in FENSTER:
        D = dossiers[lab]
        scan, tr = D["scan"], D["trades"]
        hi = scan["d"]["high"].to_numpy(dtype=float)
        lo = scan["d"]["low"].to_numpy(dtype=float)
        cl = scan["d"]["close"].to_numpy(dtype=float)
        alle = list(scan["edges"]) + list(scan["seeds"])
        _z("-" * 100)
        _z(f"{lab}   n={scan['n']}   Trades={len(tr)}   "
           f"SumR={sum(float(t.r) for t in tr):+.6f}")

        crv_liste: List[float] = []
        nah_vorhanden = 0
        nah_ordnung_ok = 0
        poc_ok_nah = 0
        sum_neu = 0.0
        sum_alt = 0.0
        crv_pass: Dict[float, List[float]] = {c: [] for c in CRV_STUFEN}
        verworfen: List[str] = []
        d_pool_leer = 0

        for t in tr:
            k, eb = int(t.bar), int(t.entry_bar)
            richtung = str(t.richtung)
            sum_alt += float(t.r)
            gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
            pool = [e for e in alle
                    if str(e.seite) == gegenseite
                    and int(e.erster_pivot_bar) + 2 <= k + 1
                    and ((bool(e.ist_prim_anker) and k >= int(e.promoviert_ab_bar))
                         or e.touch_conf(k) >= 2)]
            if not pool:
                d_pool_leer += 1
                verworfen.append(f"K{int(t.kid)}@{k}: kein Pool")
                continue
            basis = float(t.basis)
            if richtung == "LONG":
                kand = [e for e in pool if float(e.basis_bei(k)) > basis]
                ne = (min(kand, key=lambda e: float(e.basis_bei(k)))
                      if kand else None)
            else:
                kand = [e for e in pool if float(e.basis_bei(k)) < basis]
                ne = (max(kand, key=lambda e: float(e.basis_bei(k)))
                      if kand else None)
            if ne is None:
                d_pool_leer += 1
                verworfen.append(f"K{int(t.kid)}@{k}: keine Kante in Richtung")
                continue
            nah_vorhanden += 1
            nb = float(ne.basis_bei(k))
            entry = float(t.entry)
            sl = float(t.sl)
            risk = abs(sl - entry)
            dist = abs(nb - entry)
            crv = dist / risk if risk > 0 else float("nan")
            crv_liste.append(crv)
            # Ordnungsbedingung sl < entry < poc < tp2 (LONG) bzw. gespiegelt
            poc = float(t.poc)
            if richtung == "LONG":
                ok_ord = sl < entry < poc < nb
            else:
                ok_ord = nb < poc < entry < sl
            if ok_ord:
                nah_ordnung_ok += 1
                poc_ok_nah += 1
            for c in CRV_STUFEN:
                if crv >= c and ok_ord:
                    crv_pass[c].append(float(t.r))
        _z(f"  Trades mit NAECHSTER Gegenkante im Pool: {nah_vorhanden}/"
           f"{len(tr)}   (Pool leer/richtungslos: {d_pool_leer})")
        if crv_liste:
            cl_s = sorted(crv_liste)
            _z(f"  CRV der naechsten Kante (dist/|entry-sl|):  "
               f"min {cl_s[0]:.2f}  median {cl_s[len(cl_s)//2]:.2f}  "
               f"max {cl_s[-1]:.2f}   (n={len(cl_s)})")
            _z(f"     CRV < 1.0: {sum(1 for x in crv_liste if x < 1.0)}   "
               f"< 1.5: {sum(1 for x in crv_liste if x < 1.5)}   "
               f"< 2.0: {sum(1 for x in crv_liste if x < 2.0)}")
        _z(f"  Ordnung sl-entry-poc-tp2 mit der NAECHSTEN Kante erfuellt: "
           f"{nah_ordnung_ok}/{nah_vorhanden}")
        _z(f"  -> POC-Raum-Check ('unter < poc < ober') bleibt damit bei "
           f"{nah_ordnung_ok} Setups erfuellt (unveraendert uebernommen).")
        _z(f"  SumR ALT (Extremum, Bestand): {sum_alt:+12.6f}")
        _z(f"  Durchsatz der CRV-Klammer (nur gefiltert, gleiche R-Werte):")
        for c in CRV_STUFEN:
            rs = crv_pass[c]
            _z(f"     CRV >= {c:3.1f}  ->  {len(rs):3d}/{len(tr)} Trades / "
               f"{sum(rs):+10.6f} R")
        if verworfen:
            _z(f"  Ohne Kante in Handelsrichtung ({len(verworfen)}): "
               f"{', '.join(verworfen[:6])}")
        _z("")

    _z("=" * 100)
    _z("F4b -- ECHTE Nachrechnung: jeder Trade mit dem NAECHSTEN Ziel neu")
    _z("  aufgeloest (reine Baseline-Funktion _c_loese_trade; sl/entry/poc")
    _z("  unveraendert, nur tp2 ersetzt). Trennt Gating von Wirkung.")
    _z("")

    def _aufloesen(sel: Sequence[Any], crv_min: float, ordnung: bool
                   ) -> Tuple[int, float, int, int, int]:
        n_ok = 0
        s = 0.0
        n_tp2 = n_sl = n_ende = 0
        for t in sel:
            k, eb = int(t.bar), int(t.entry_bar)
            richtung = str(t.richtung)
            gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
            pool = [e for e in scan_l["alle"]
                    if str(e.seite) == gegenseite
                    and int(e.erster_pivot_bar) + 2 <= k + 1
                    and ((bool(e.ist_prim_anker)
                          and k >= int(e.promoviert_ab_bar))
                         or e.touch_conf(k) >= 2)]
            basis = float(t.basis)
            if richtung == "LONG":
                kand = [e for e in pool if float(e.basis_bei(k)) > basis]
                ne = (min(kand, key=lambda e: float(e.basis_bei(k)))
                      if kand else None)
            else:
                kand = [e for e in pool if float(e.basis_bei(k)) < basis]
                ne = (max(kand, key=lambda e: float(e.basis_bei(k)))
                      if kand else None)
            if ne is None:
                continue
            nb = float(ne.basis_bei(k))
            entry, sl, poc = float(t.entry), float(t.sl), float(t.poc)
            risk = abs(sl - entry)
            if risk <= 0 or abs(nb - entry) / risk < crv_min:
                continue
            if ordnung:
                if richtung == "LONG":
                    if not (sl < entry < poc < nb):
                        continue
                else:
                    if not (nb < poc < entry < sl):
                        continue
            neu = B._c_loese_trade(scan_l["hi"], scan_l["lo"], scan_l["cl"],
                                   eb, entry, richtung, sl, poc, nb,
                                   cfg_h.tp1_anteil_pct)
            n_ok += 1
            s += float(neu.r_mult)
            if "TP2" in (str(neu.grund1), str(neu.grund2)):
                n_tp2 += 1
            if "SL" in (str(neu.grund1), str(neu.grund2)):
                n_sl += 1
            if "ENDE" in (str(neu.grund1), str(neu.grund2)):
                n_ende += 1
        return n_ok, s, n_tp2, n_sl, n_ende

    _z(f"  {'Fenster':8s} {'Variante':26s} {'Trades':>7s} {'SumR':>12s} "
       f"{'TP2':>4s} {'SL':>4s} {'ENDE':>5s}")
    for lab, start, ende in FENSTER:
        D = dossiers[lab]
        scan, tr = D["scan"], D["trades"]
        scan_l = {"alle": list(scan["edges"]) + list(scan["seeds"]),
                  "hi": scan["d"]["high"].to_numpy(dtype=float),
                  "lo": scan["d"]["low"].to_numpy(dtype=float),
                  "cl": scan["d"]["close"].to_numpy(dtype=float)}
        for nm, crv, ordn in (("NAECHSTE pur", 0.0, False),
                              ("NAECHSTE + Ordnung", 0.0, True),
                              ("NAECHSTE + ORD + CRV 1.0", 1.0, True),
                              ("NAECHSTE + ORD + CRV 1.5", 1.5, True),
                              ("NAECHSTE + ORD + CRV 2.0", 2.0, True)):
            n_ok, s, n_tp2, n_sl, n_ende = _aufloesen(tr, crv, ordn)
            _z(f"  {lab:8s} {nm:26s} {n_ok:>7d} {s:>+12.6f} "
               f"{n_tp2:>4d} {n_sl:>4d} {n_ende:>5d}")
        _z(f"  {lab:8s} {'EXTREMUM (Bestand)':26s} {len(tr):>7d} "
           f"{sum(float(t.r) for t in tr):>+12.6f} "
           f"{sum(1 for t in tr if str(t.grund2) == 'TP2'):>4d} "
           f"{sum(1 for t in tr if 'SL' in (str(t.grund1), str(t.grund2))):>4d} "
           f"{sum(1 for t in tr if 'ENDE' in (str(t.grund1), str(t.grund2))):>5d}")
        _z("")

    _z("=" * 100)
    _z("F4c -- ALTERNATIVE: GEDECKELTES Extremum (Bestandsziel, nur begrenzt)")
    _z("  tp2 bleibt die aeusserste Gegenkante, wird aber auf einen")
    _z("  Hoechstabstand gedeckelt: tp2 = entry +/- min(dist_extrem, KAP).")
    _z("  Ordnungsbedingung (poc < tp2) wird geprueft, sonst faellt das Setup.")
    _z("")
    _z(f"  {'Fenster':8s} {'Deckel':22s} {'Trades':>7s} {'SumR':>12s} "
       f"{'TP2':>4s} {'SL':>4s} {'ENDE':>5s}")
    for lab, start, ende in FENSTER:
        D = dossiers[lab]
        scan, tr = D["scan"], D["trades"]
        hi = scan["d"]["high"].to_numpy(dtype=float)
        lo = scan["d"]["low"].to_numpy(dtype=float)
        cl = scan["d"]["close"].to_numpy(dtype=float)
        atr = _atr_wilder(hi, lo, cl, 14)

        def _deckel(sel: Sequence[Any], art: str, kap: float
                    ) -> Tuple[int, float, int, int, int]:
            n_ok = 0
            s = 0.0
            n_tp2 = n_sl = n_ende = 0
            for t in sel:
                eb, k = int(t.entry_bar), int(t.bar)
                richtung = str(t.richtung)
                entry, sl, poc = float(t.entry), float(t.sl), float(t.poc)
                risk = abs(sl - entry)
                if risk <= 0:
                    continue
                grenze = (kap * risk) if art == "R" else (kap * float(atr[k]))
                if not np.isfinite(grenze) or grenze <= 0.0:
                    continue
                dtp = abs(float(t.tp2) - entry)
                benutzt = min(dtp, grenze)
                tp2n = entry + benutzt if richtung == "LONG" else entry - benutzt
                if richtung == "LONG":
                    if not (sl < entry < poc < tp2n):
                        continue
                else:
                    if not (tp2n < poc < entry < sl):
                        continue
                neu = B._c_loese_trade(hi, lo, cl, eb, entry, richtung, sl,
                                       poc, tp2n, cfg_h.tp1_anteil_pct)
                n_ok += 1
                s += float(neu.r_mult)
                if "TP2" in (str(neu.grund1), str(neu.grund2)):
                    n_tp2 += 1
                if "SL" in (str(neu.grund1), str(neu.grund2)):
                    n_sl += 1
                if "ENDE" in (str(neu.grund1), str(neu.grund2)):
                    n_ende += 1
            return n_ok, s, n_tp2, n_sl, n_ende

        for art, kap in (("R", 1.5), ("R", 2.0), ("R", 3.0), ("R", 5.0),
                         ("ATR", 1.0), ("ATR", 2.0), ("ATR", 3.0)):
            n_ok, s, n_tp2, n_sl, n_ende = _deckel(tr, art, kap)
            _z(f"  {lab:8s} {'Deckel ' + str(kap) + ' x ' + art:22s} "
               f"{n_ok:>7d} {s:>+12.6f} {n_tp2:>4d} {n_sl:>4d} {n_ende:>5d}")
        _z(f"  {lab:8s} {'EXTREMUM (Bestand)':22s} {len(tr):>7d} "
           f"{sum(float(t.r) for t in tr):>+12.6f} "
           f"{sum(1 for t in tr if str(t.grund2) == 'TP2'):>4d} "
           f"{sum(1 for t in tr if 'SL' in (str(t.grund1), str(t.grund2))):>4d} "
           f"{sum(1 for t in tr if 'ENDE' in (str(t.grund1), str(t.grund2))):>5d}")
        _z("")

    _z("=" * 100)
    _z("SPEZIFIKATIONS-KONSEQUENZEN (Kurzfassung)")
    _z("  S1  '0.50 * ATR' ist ohne neues, kausales ATR nicht darstellbar.")
    _z("      Entweder ATR(14) M15 kausal in den Scan aufnehmen (Empfehlung:")
    _z("      scan['atr'], einmal, kausal) oder die Klammer auf 1.5*|entry-sl|")
    _z("      reduzieren. Beides ist eine Freigabeentscheidung.")
    _z("  S2  Der POC wird ueber [Basis, Gegenbasis] berechnet. Wandert die")
    _z("      Gegenbasis naeher, wird das Band schmaler -> der POC-Raum-Check")
    _z("      kann haeufiger scheitern. Zahlen siehe F3 ('Ordnung erfuellt').")
    _z("  S3  Der Ordnungstest 'sl < entry < poc < tp2' ist im Bestand eine")
    _z("      HARTE Bedingung; die naechste Kante muss sie ebenfalls erfuellen,")
    _z("      sonst faellt das Setup (nicht: Kante tauschen).")
    _z("")
    _z(f"PROTOKOLL: {OUT}")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        _Z.append(f"\nABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}")
    OUT.write_text("\n".join(_Z) + "\n", encoding="utf-8", newline="\n")
    print(f"\nFehler={_fehler}")
