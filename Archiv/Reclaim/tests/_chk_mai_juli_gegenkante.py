# -*- coding: utf-8 -*-
"""READ-ONLY Tiefendiagnose Mai/Juni/Juli -- Gegenkanten-Identitaet + R-Physik.

Frage
-----
Warum ist ``tp2`` (= ``gegen_basis``) ueber einen ganzen Monat konstant, und
wie entstehen R-Multiples von +51 R bei einem Stop von 0.216 USD?

Vorgehen
--------
1. Fenster laden (Kanons K1/K4), kausaler SE-Scan, ``box_end_bar = n``
   (Modus A, ``hook=None``) -- exakt wie ``_chk_mai_juli_diag.py``.
2. ``_gegenkante`` wird NICHT gepatcht, sondern aus dem identischen Pool
   (``scan['edges'] + scan['seeds']``) deterministisch nachgerechnet --
   ``basis_bei``/``erster_pivot_bar``/``promoviert_ab_bar``/``ist_prim_anker``
   werden vom Trade-Loop NICHT mutiert, die Attribution ist daher exakt.
3. Je Trade: kausaler Risiko-Betrag ``|sl - entry|``, R-Zerlegung (r1/r2),
   Gegenkanten-Identitaet, Abstand TP2, Konzentration des SumR.

Read-only: DB nur lesend; Motoren/Descriptor bleiben byte-identisch.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

PROTOKOLL = ROOT / "test" / "_chk_mai_juli_gegenkante_out.txt"

MONATE = (("MAI", "2026-05-01", "2026-06-01"),
          ("JUN", "2026-06-01", "2026-07-01"),
          ("JUL", "2026-07-01", "2026-08-01"))


def _lade(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _gegenkanten_pool(alle: List[Any], kk: int, richtung: str) -> List[Any]:
    """Richtungsfremder Kantenpool -- VERBATIM die Engine-Semantik (Q5/Q14/Q18).

    EINZIGE Quelle der Poolbildung (F16: keine Funktionsverdopplung).
    ``_gegenkante_extern`` (EXTREMUM) und ``_naechste_kante_extern``
    (DIAGNOSTIK) unterscheiden sich AUSSCHLIESSLICH in der Auswahl aus diesem
    Pool, niemals in seiner Bildung.

    Args:
        alle: ``edges + seeds`` des Scans (wie im Motor).
        kk: Signal-Bar.
        richtung: Signalrichtung.

    Returns:
        Pool der Gegenkanten (SCHLAFENDE zulaessig, Q5/Q14); ``[]`` wenn kein
        Gegner existiert.
    """
    gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
    return [e for e in alle
            if str(e.seite) == gegenseite
            and int(e.erster_pivot_bar) + 2 <= kk + 1
            and ((bool(e.ist_prim_anker) and kk >= int(e.promoviert_ab_bar))
                 or int(e.touch_conf(kk)) >= 2)]


def _halbkanten_pool(alle: List[Any], kk: int, richtung: str, basis: float
                     ) -> List[Any]:
    """Zulaessigkeits-Halbraum der Engine (Befund D) -- genau ``kein_raum``.

    ``tmp_kanten_engine_replay.py`` laesst einen Trade nur zu, wenn die
    gewaehlte Gegenkante AUF DER ABGEWANDTEN SEITE der getradeten Kante liegt
    (Zeilen 2677-2692):

        SHORT   ``gegen_basis < basis``   (Ziel unter der getradeten Oberkante)
        LONG    ``gegen_basis > basis``   (Ziel ueber der getradeten Unterkante)

    Andernfalls zaehlt der Motor ``kein_raum`` und verwirft das Setup. Der
    ``tp2`` (EXTREMUM) erfuellt diese Bedingung per Konstruktion.

    Befund D (K1-Korrektur der Diagnostik): Die NAEECHSTE Gegenkante ist die
    naechstgelegene Kante INNERHALB dieses Halbraums, nicht das globale
    ``min``/``max`` des Pools. Ein reiner Spiegel kann eine Kante waehlen, die
    diesseits der getradeten Basis liegt -- ein Niveau, das die Engine als
    Ziel niemals zuliesse (``kein_raum``). Die Diagnostik wuerde dann eine
    Erreichbarkeit berichten, die es im Vertrag nicht gibt.

    ``_gegenkanten_pool`` bleibt die EINZIGE Quelle der Poolbildung (F16);
    hier wird ausschliesslich der Zulaessigkeits-Halbraum aufgesetzt.

    Args:
        alle: ``edges + seeds`` des Scans (wie im Motor).
        kk: Signal-Bar.
        richtung: Signalrichtung.
        basis: ``basis_bei(kk)`` der GETRADETEN Kante (``t.basis``).

    Returns:
        Der halbraum-gefilterte Kantenpool; ``[]`` wenn kein Gegner im
        Halbraum liegt (dann sind die abgeleiteten Kennzahlen ``nan``).
    """
    pool = _gegenkanten_pool(alle, kk, richtung)
    if str(richtung) == "SHORT":
        return [e for e in pool if float(e.basis_bei(kk)) < float(basis)]
    return [e for e in pool if float(e.basis_bei(kk)) > float(basis)]


def _gegenkante_extern(alle: List[Any], kk: int, richtung: str
                       ) -> Tuple[Optional[Any], List[Any]]:
    """Exakte Nachrechnung der Engine-Auswahl ``_gegenkante`` (EXTREMUM).

    Das ist die ARRETIERTE Zielwahl: ``tp2`` ist die aeusserste Gegenkante
    (``max`` bei OBEN, ``min`` bei UNTEN). Sie bleibt handelswirksam
    unangetastet (H20.52 Paragraph 1, F1-Klausel).

    Args:
        alle: ``edges + seeds`` des Scans (wie im Motor).
        kk: Signal-Bar.
        richtung: Signalrichtung.

    Returns:
        ``(gewaehlte_kante, pool)``; ``(None, [])`` wenn kein Gegner.
    """
    pool = _gegenkanten_pool(alle, kk, richtung)
    if not pool:
        return None, []
    gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
    if gegenseite == "OBEN":
        return max(pool, key=lambda e: float(e.basis_bei(kk))), pool
    return min(pool, key=lambda e: float(e.basis_bei(kk))), pool


def _naechste_kante_extern(alle: List[Any], kk: int, richtung: str, basis: float
                           ) -> Tuple[Optional[Any], List[Any]]:
    """DIAGNOSTIK (F14/F5): naechstgelegene ZULAESSIGE Gegenkante.

    Nur zur Beobachtung der Gegenliquiditaet (H20.52 Paragraph 11). KEINE
    Handelswirkung: ``tp2`` bleibt das Extremum.

    Der Unterschied zu ``_gegenkante_extern`` ist ausschliesslich die
    Auswahlrichtung (Befund B) -- angewandt auf den ZULAESSIGKEITS-HALBRAUM
    (Befund D, ``_halbkanten_pool``), nicht auf den nackten Pool:

        Seite  EXTREMUM (Pool)    NAECHSTE (Halbraum)
        OBEN   max(basis)         min(basis)  mit  basis > t.basis
        UNTEN  min(basis)         max(basis)  mit  basis < t.basis

    Die Halbraum-Bedingung ist keine Zutat der Diagnostik, sondern die
    Zulassungsregel des Motors selbst (``kein_raum``, Zeilen 2677-2692). Ohne
    sie waehlt der reine Spiegel mitunter eine Kante diesseits der getradeten
    Basis und berichtet eine Erreichbarkeit, die der Vertrag nie zulaesst.
    Genau daraus entstand die Abweichung zu F3 (``_chk_u3_spec_beleg.py``):
    F3 filtert ``basis_bei(k) > t.basis`` (LONG) bzw. ``< t.basis`` (SHORT)
    und liefert die Ordnungsquote 8/35, 4/28, 9/21 -- diese Funktion
    reproduziert sie nun bit-identisch.

    Referenz-Bar ist der SIGNAL-Bar ``kk`` -- nicht der Entry-Bar (H20.52
    Paragraph 11, Praezisierung K1). Der Motor waehlt die Gegenkante im
    Trade-Loop am Signal-Bar ``t.bar``.

    Args:
        alle: ``edges + seeds`` des Scans (wie im Motor).
        kk: Signal-Bar.
        richtung: Signalrichtung.
        basis: ``basis_bei(kk)`` der getradeten Kante (``t.basis``).

    Returns:
        ``(naechste_kante, pool)``; ``(None, [])`` wenn kein Gegner im
        Zulaessigkeits-Halbraum -- dann sind die abgeleiteten Kennzahlen
        ``float("nan")``, niemals 0.0.
    """
    pool = _halbkanten_pool(alle, kk, richtung, basis)
    if not pool:
        return None, []
    gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
    if gegenseite == "OBEN":
        return min(pool, key=lambda e: float(e.basis_bei(kk))), pool
    return max(pool, key=lambda e: float(e.basis_bei(kk))), pool


def ordnung_poc_erfuellt(t: Any, ziel_preis: float) -> bool:
    """Ordnungsbedingung ``sl < entry < poc < ziel`` (LONG) bzw. gespiegelt.

    Die Engine prueft diese Bedingung als HARTE Voraussetzung; gegen das
    Extremum (``t.tp2``) ist sie daher per Konstruktion IMMER erfuellt
    (Befund C -- 84 x True, keine Information). Informativ ist allein der
    Test gegen die NAECHSTE Gegenkante: er zeigt, ob das nahe Ziel den POC
    ueberhaupt schneidet (H20.52 Paragraph 4, POC-Kopplung).

    Args:
        t: ``_SESetup`` (liest ``sl``, ``entry``, ``poc``, ``richtung``).
        ziel_preis: Zu pruefender Zielpreis (z. B. naechste Gegenkante).

    Returns:
        True gdw. die Ordnung mit diesem Zielpreis haelt.
    """
    sl, entry, poc = float(t.sl), float(t.entry), float(t.poc)
    ziel = float(ziel_preis)
    if str(t.richtung) == "SHORT":
        return sl > entry > poc > ziel
    return sl < entry < poc < ziel


def main() -> None:
    import copy

    R = _lade("run_lab_gk", ROOT / "test" / "run_lab.py")
    B = R._load("basis_gk", R.BASELINE_PFAD)
    V = R._load("v020_gk", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    z: List[str] = []
    z.append("TIEFENDIAGNOSE MAI/JUN/JUL -- Gegenkanten-Identitaet + R-Physik")
    z.append("(Modus A, hook=None, box_end=n, touch_band_pct="
             f"{kcfg.touch_band_pct:.2f}, sl_buffer_usd={cfg.sl_buffer_usd:.2f})")
    z.append("")
    gesamt = 0.0
    for lab, start, ende in MONATE:
        d = R._lade_fenster(B, start, ende)
        n = len(d)
        original = B._lade_fenster
        B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
        try:
            scan = B._se_scan("LAB", cfg)
        finally:
            B._lade_fenster = original  # type: ignore
        scan = copy.deepcopy(scan)
        scan["box_end_bar"] = int(n)
        eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
        tr, _st = eng._se_trades_v020(scan, cfg)
        tr = sorted(list(tr), key=lambda x: int(x.entry_bar))
        alle = list(scan["edges"]) + list(scan["seeds"])

        z.append(f"===== {lab}: {start} .. {ende} (exkl.) | n={n} =====")
        z.append(f"  {'#':>3s} {'KID':>4s} {'Richt':5s} {'k':>5s} "
                 f"{'basis':>8s} {'entry':>8s} {'SL':>8s} {'risk':>6s} "
                 f"{'TP1=poc':>8s} {'TP2':>8s} {'r1':>9s} {'r2':>9s} "
                 f"{'R':>10s} | {'GEgKID':>6s} {'Seite':5s} {'prim':>4s} "
                 f"{'wicks':>5s} {'basis_bei':>9s} {'basis_feld':>10s} "
                 f"{'pool':>4s}")
        cum = 0.0
        rows = []
        for i, t in enumerate(tr, 1):
            cum += float(t.r)
            k = int(t.bar)
            richtung = str(t.richtung)
            geg, pool = _gegenkante_extern(alle, k, richtung)
            gk = int(geg.kid) if geg is not None else -1
            gseite = str(geg.seite) if geg is not None else "-"
            gprim = "JA" if (geg is not None and geg.ist_prim_anker) else "nein"
            gw = int(len(geg.wicks)) if geg is not None else 0
            gbb = float(geg.basis_bei(k)) if geg is not None else float("nan")
            gbf = float(geg.basis) if geg is not None else float("nan")
            risk = abs(float(t.sl) - float(t.entry))
            rows.append((i, int(t.kid), richtung, k, float(t.basis),
                         float(t.entry), float(t.sl), risk, float(t.poc),
                         float(t.tp2), float(t.r1), float(t.r2), float(t.r),
                         gk, gseite, gprim, gw, gbb, gbf, len(pool)))
            z.append(
                f"  {i:3d} {int(t.kid):4d} {richtung:5s} {k:5d} "
                f"{float(t.basis):8.4f} {float(t.entry):8.4f} "
                f"{float(t.sl):8.4f} {risk:6.3f} "
                f"{float(t.poc):8.4f} {float(t.tp2):8.4f} "
                f"{float(t.r1):+9.3f} {float(t.r2):+9.3f} {float(t.r):+10.3f}"
                f" | {gk:6d} {gseite:5s} {gprim:>4s} {gw:5d} {gbb:9.4f} "
                f"{gbf:10.4f} {len(pool):4d}")
            # Engine-Invariante verifizieren (nicht nur behaupten)
            if richtung == "SHORT":
                assert float(t.sl) > float(t.entry) > float(t.poc) > float(t.tp2)
            else:
                assert float(t.sl) < float(t.entry) < float(t.poc) < float(t.tp2)
            if geg is not None:
                assert abs(gbb - float(t.tp2)) < 1e-9, (t.kid, gbb, t.tp2)
        # --- Aggregat ------------------------------------------------------
        tp2_werte = sorted({round(r[9], 4) for r in rows})
        risks = [r[7] for r in rows]
        bester = max(rows, key=lambda r: r[12])
        z.append("")
        z.append(f"  distinct TP2-Werte ({len(tp2_werte)}): "
                 + ", ".join(f"{v:.4f}" for v in tp2_werte))
        z.append(f"  risk USD: min {min(risks):.4f} | median "
                 f"{float(np.median(risks)):.4f} | max {max(risks):.4f}")
        z.append(f"  SumR {cum:+.6f} | bester Trade #{bester[0]} "
                 f"K{bester[1]} {bester[12]:+.6f} R | "
                 f"SumR ohne diesen Trade {cum - bester[12]:+.6f} R")
        for r in rows:
            if r[12] > 5.0:
                z.append(f"    GROSS-R: #{r[0]:3d} K{r[1]:3d} {r[2]:5s} "
                         f"risk={r[7]:.4f} R={r[12]:+.4f} "
                         f"(r1={r[10]:+.2f} r2={r[11]:+.2f}) "
                         f"exit1_bar->{int(tr[r[0]-1].exit1_bar)} "
                         f"grund1={tr[r[0]-1].grund1} "
                         f"grund2={tr[r[0]-1].grund2}")
        z.append("")
        gesamt += cum
    z.append(f"GESAMT MAI+JUN+JUL: {gesamt:+.6f} R")

    PROTOKOLL.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    for zl in z:
        print(zl)
    print(f"\n-> {PROTOKOLL}")


if __name__ == "__main__":
    main()
