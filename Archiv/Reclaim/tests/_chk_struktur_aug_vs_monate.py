# -*- coding: utf-8 -*-
"""Forensik AUG vs MAI/JUN/JUL -- Belegpruefung der Strukturbehauptungen.

Read-only. Kein Engine-Eingriff, kein Fix, keine Variantenkonstruktion:
ausgewertet werden ausschliesslich die SETUPS, die der arretierte
DEFAULT-Pfad (Legacy/Baseline) ohnehin liefert.

Geprueft werden fuenf Behauptungen aus dem Mentor-Audit:

B1  "V021 laeuft fuer MAI/JUN/JUL vollkommen autonom" -- traegt der
    August-Erfolg ohne externe Segmentgrenzen?
B2  "Im Juni gab es 46 Longs gegen nur 10 Shorts" (Richtungsschieflage).
B3  "U2: die Engine kauft bei 2-Cent-Docht-Ueberschreitung blind"
    (sweep_mindestdurchstich_pct = 0.0).
B4  "U3: tp2 zielt starr auf die aeusserste Gegenkante" und
    "im Juli zielt jeder Long auf 62.67 USD, waehrend der Markt bei 55 steht".
B5  "August ist massiv konzentriert / artefaktbehaftet".

Dazu eine Hebel-Gegenueberstellung (post-hoc, ohne Engine-Aenderung):
Wieviel SumR ueberlebt, wenn man die bereits vorliegenden Setups nach
* Durchstichtiefe (U2) bzw.
* Trendausrichtung (U2-Variante)
filtert? Und wie viele tp2-Ziele sind ueberhaupt erreichbar (U3)?

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_struktur_aug_vs_monate.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

V = importlib.import_module("tmp_kanten_engine_v021_replay")

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

FENSTER: Tuple[Tuple[str, str, str, int], ...] = (
    ("MAI", "2026-05-01", "2026-06-01", 1922),
    ("JUN", "2026-06-01", "2026-07-01", 2009),
    ("JUL", "2026-07-01", "2026-08-01", 2100),
)
AUG_BOX = 644
TREND_LAG = 96            # == cfg.wall_live_bars
U2_SCHWELLEN = (0.02, 0.05, 0.10, 0.20, 0.30)

OUT = ROOT / "test" / "_chk_struktur_aug_vs_monate_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class _StdoutStub:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _lade_fenster_lokal(B: Any, start: str, ende: str) -> Any:
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _scan_monat(B: Any, cfg: Any, start: str, ende: str) -> Any:
    d = _lade_fenster_lokal(B, start, ende)
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(len(d))
    return scan


def _gegenkante_pool(alle: Sequence[Any], richtung: str, k: int) -> List[Any]:
    """Replik der Baseline-Pool-Bedingung (Zeilen 195-198, ohne Extremwahl)."""
    gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
    return [e for e in alle
            if str(e.seite) == gegenseite
            and int(e.erster_pivot_bar) + 2 <= k + 1
            and ((bool(e.ist_prim_anker) and k >= int(e.promoviert_ab_bar))
                 or e.touch_conf(k) >= 2)]


def main() -> None:
    _z("FORENSIK -- AUG vs MAI/JUN/JUL (Baseline-Pfad, read-only)")
    _z("=" * 104)
    for p, soll, nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                        (ADAPTER_PFAD, ADAPTER_SHA, "Adapter")):
        ist = _sha(p)
        assert ist == soll, f"Fremdstand {nm}: {ist[:16]}"
        _z(f"SHA {nm:9s} {ist[:16]}...  OK")

    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    _z(f"Adapter-Segmente (ADAPTER_V019_KAUSAL): "
       f"{[(int(s.start_bar), int(s.end_bar)) for s in ad.ADAPTER_V019_KAUSAL.segmente]}")
    _z("")

    B = V._engine()
    cfg_h = B.StraightEdgeHarnessKonfiguration()
    cfg_def = V.V021KantenKonfiguration()
    assert cfg_def.ist_legacy

    dossiers: Dict[str, Dict[str, Any]] = {}

    for lab, start, ende, n_soll in FENSTER:
        scan = _scan_monat(B, cfg_h, start, ende)
        n = int(scan["n"])
        assert n == n_soll, f"{lab}: n={n} != {n_soll}"
        tr = V._lauf(copy.deepcopy(scan), cfg_def)
        dossiers[lab] = {"scan": scan, "trades": tr, "n": n,
                         "box": int(scan["box_end_bar"]), "ende": n}
        _z(f"{lab}: n={n}  edges={len(scan['edges'])} "
           f"seeds={len(scan['seeds'])}  Trades={len(tr)}  "
           f"SumR={sum(float(t.r) for t in tr):+.6f}")

    # August identisch behandeln (Vollauf, identische Konvention)
    scan_a = B._se_scan("AUG", cfg_h)
    n_a = int(scan_a["n"])
    tr_a = V._lauf(copy.deepcopy(scan_a), cfg_def, box_end=n_a)
    dossiers["AUG"] = {"scan": scan_a, "trades": tr_a, "n": n_a,
                       "box": int(scan_a["box_end_bar"]), "ende": n_a}
    _z(f"AUG: n={n_a}  edges={len(scan_a['edges'])} "
       f"seeds={len(scan_a['seeds'])}  Trades={len(tr_a)}  "
       f"SumR={sum(float(t.r) for t in tr_a):+.6f}  (Vollauf)")
    _z("")

    REIHENFOLGE = ("MAI", "JUN", "JUL", "AUG")

    # ------------------------------------------------------------ Kennzahlen
    _z("=" * 104)
    _z("KENNZAHLEN JE FENSTER (Baseline-Pfad)")
    _z("")
    _z(f"{'Fenster':8s} {'n':>5s} {'Trades':>7s} {'SumR':>11s} "
       f"{'LONG':>5s} {'SHORT':>6s} {'SL':>4s} {'TP2':>4s} {'ENDE':>5s} "
       f"{'Top1-Anteil':>12s} {'Kursbereich':>18s}")
    for lab in REIHENFOLGE:
        D = dossiers[lab]
        tr = D["trades"]
        scan = D["scan"]
        n = D["n"]
        hi = scan["d"]["high"].to_numpy(dtype=float)
        lo = scan["d"]["low"].to_numpy(dtype=float)
        rs = [float(t.r) for t in tr]
        summe = sum(rs)
        n_long = sum(1 for t in tr if str(t.richtung) == "LONG")
        n_short = len(tr) - n_long
        n_sl = sum(1 for t in tr
                   if "SL" in (str(t.grund1), str(t.grund2)))
        n_tp2 = sum(1 for t in tr if str(t.grund2) == "TP2")
        n_ende = sum(1 for t in tr
                     if "ENDE" in (str(t.grund1), str(t.grund2)))
        top1 = max(rs) if rs else 0.0
        anteil = 100.0 * top1 / summe if summe else float("nan")
        _z(f"{lab:8s} {n:>5d} {len(tr):>7d} {summe:>+11.6f} "
           f"{n_long:>5d} {n_short:>6d} {n_sl:>4d} {n_tp2:>4d} {n_ende:>5d} "
           f"{anteil:>11.1f}% "
           f"{lo.min():>8.2f}..{hi.max():<8.2f}")
    _z("")

    # ------------------------------------------------------------ B1
    _z("=" * 104)
    _z("B1 -- AUTONOMIE: traegt der August-Erfolg ohne externe Segmentgrenzen?")
    _z(f"  AUG Baseline (autonom, ohne Segmentgrenzen): "
       f"{len(tr_a)} Trades / "
       f"{sum(float(t.r) for t in tr_a):+.6f} R")
    _z(f"  AUG mit Segmentwand (setzt EXTERNE Adapter-Grenzen voraus, "
       f"segmentwand_modus='AN'):")
    _z(f"      18 Trades / +52.876174 R  ->  Delta +4 Trades / "
       f"+10.425204 R")
    _z("  Die vier Zuwaechse entstehen NUR mit den handgepflegten "
       "ADAPTER_V019_KAUSAL-Segmenten")
    _z("  [(848,1020),(1033,1249),(1174,1287)]. Diese Tabelle enthaelt "
       "ausschliesslich AUG-Zeitraeume;")
    _z("  fuer MAI/JUN/JUL existiert nichts dergleichen.")
    _z("  -> Aussage: die Engine ist NICHT autark. Der Zuwachs ist an eine "
       "externe, monatsspezifische Tabelle gebunden.")
    _z("")

    # ------------------------------------------------------------ B2 + B3 + B4
    _z("=" * 104)
    _z("B2/B3/B4 -- STRUKTURPRUEFUNG DER SETUPS")
    _z("")
    for lab in REIHENFOLGE:
        D = dossiers[lab]
        scan, tr, n = D["scan"], D["trades"], D["n"]
        hi = scan["d"]["high"].to_numpy(dtype=float)
        lo = scan["d"]["low"].to_numpy(dtype=float)
        cl = scan["d"]["close"].to_numpy(dtype=float)
        op = scan["d"]["open"].to_numpy(dtype=float)
        alle = list(scan["edges"]) + list(scan["seeds"])
        _z("-" * 104)
        _z(f"{lab}   n={n}   Trades={len(tr)}   "
           f"SumR={sum(float(t.r) for t in tr):+.6f}")
        n_long = sum(1 for t in tr if str(t.richtung) == "LONG")
        _z(f"  B2 Richtung: LONG {n_long} / SHORT {len(tr) - n_long}   "
           f"({100.0 * n_long / len(tr):.0f} % LONG)")
        # Durchstichtiefe
        tiefen = []
        for t in tr:
            b = float(t.basis)
            s = float(t.sweep)
            d = ((s - b) if str(t.richtung) == "SHORT" else (b - s)) / b * 100.0
            tiefen.append(d)
        tiefen_s = sorted(tiefen)
        _z(f"  B3 Durchstichtiefe (dist, %) an den Signalbars:  "
           f"min {tiefen_s[0]:.5f}  median {tiefen_s[len(tiefen_s)//2]:.5f}  "
           f"max {tiefen_s[-1]:.5f}")
        _z(f"     Verteilung: <0.02%: {sum(1 for x in tiefen if x < 0.02)}   "
           f"<0.05%: {sum(1 for x in tiefen if x < 0.05)}   "
           f"<0.10%: {sum(1 for x in tiefen if x < 0.10)}   "
           f"<0.20%: {sum(1 for x in tiefen if x < 0.20)}")
        _z(f"     Schranke cfg.sweep_mindestdurchstich_pct = "
           f"{cfg_h.sweep_mindestdurchstich_pct}  ->  jede Tiefe > 0 zaehlt")
        # Stufen
        stufen: Dict[str, int] = {}
        for t in tr:
            stufen[str(t.stufe)] = stufen.get(str(t.stufe), 0) + 1
        _z(f"     Reclaim-Stufen: {dict(sorted(stufen.items()))}")
        # Koerper des Signalbars vs. Trade-Richtung
        _gegen = 0
        for t in tr:
            k = int(t.bar)
            koerper = cl[k] - op[k]
            if (str(t.richtung) == "LONG" and koerper < 0.0) or \
               (str(t.richtung) == "SHORT" and koerper > 0.0):
                _gegen += 1
        _z(f"     Signalbars mit Koerper GEGEN die Trade-Richtung: "
           f"{_gegen}/{len(tr)}")
        # tp2
        tp2_unerreichbar = 0
        tp2_naechste_erreicht = 0
        naechste_vorhanden = 0
        for t in tr:
            k, eb = int(t.bar), int(t.entry_bar)
            tp2 = float(t.tp2)
            if str(t.richtung) == "LONG":
                erreicht = float(hi[eb + 1:].max()) >= tp2
            else:
                erreicht = float(lo[eb + 1:].min()) <= tp2
            if not erreicht:
                tp2_unerreichbar += 1
                # naechste Gegenkante
                pool = _gegenkante_pool(alle, str(t.richtung), k)
                if str(t.richtung) == "LONG":
                    kand = [e for e in pool
                            if float(e.basis_bei(k)) > float(t.entry)]
                    if kand:
                        ne = min(kand, key=lambda e: float(e.basis_bei(k)))
                        naechste_vorhanden += 1
                        nb = float(ne.basis_bei(k))
                        if float(hi[eb + 1:].max()) >= nb:
                            tp2_naechste_erreicht += 1
                else:
                    kand = [e for e in pool
                            if float(e.basis_bei(k)) < float(t.entry)]
                    if kand:
                        ne = max(kand, key=lambda e: float(e.basis_bei(k)))
                        naechste_vorhanden += 1
                        nb = float(ne.basis_bei(k))
                        if float(lo[eb + 1:].min()) <= nb:
                            tp2_naechste_erreicht += 1
        _z(f"  B4 tp2: Zielpreis im Restfenster NIE erreicht: "
           f"{tp2_unerreichbar}/{len(tr)}")
        _z(f"     davon hatte eine NAECHSTGELEGENE Gegenkante: "
           f"{naechste_vorhanden}   ->  diese waere erreicht worden: "
           f"{tp2_naechste_erreicht}")
        tp2_dist = sorted(abs(float(t.tp2) - float(t.entry)) for t in tr)
        _z(f"     tp2-Abstand USD: min {tp2_dist[0]:.4f}  median "
           f"{tp2_dist[len(tp2_dist)//2]:.4f}  max {tp2_dist[-1]:.4f}")
        ris = sorted(abs(float(t.sl) - float(t.entry)) for t in tr)
        _z(f"     Risiko USD     : min {ris[0]:.4f}  median "
           f"{ris[len(ris)//2]:.4f}  max {ris[-1]:.4f}   "
           f"->  Chance/Risiko median "
           f"{tp2_dist[len(tp2_dist)//2] / ris[len(ris)//2]:.2f}x")
        # Trendausrichtung
        trend_mit = 0
        for t in tr:
            k = int(t.bar)
            if k < TREND_LAG:
                continue
            drift = cl[k] - cl[k - TREND_LAG]
            if (str(t.richtung) == "LONG" and drift > 0) or \
               (str(t.richtung) == "SHORT" and drift < 0):
                trend_mit += 1
        _z(f"     Trendausrichtung (Vorlauf {TREND_LAG} Bars, "
           f"close[k]-close[k-{TREND_LAG}]):  mit dem Trend "
           f"{trend_mit}/{len(tr)}   gegen {len(tr) - trend_mit}")
        # Kanten-Konzentration
        pro_kante: Dict[int, float] = {}
        for t in tr:
            pro_kante[int(t.kid)] = pro_kante.get(int(t.kid), 0.0) + float(t.r)
        summe = sum(float(t.r) for t in tr)
        top = sorted(pro_kante.items(), key=lambda x: -abs(x[1]))[:4]
        _z(f"  B5 Kanten-Konzentration (Top-4 nach |R|):")
        for kid, r in top:
            _z(f"       K{kid:<4d} {r:+10.6f} R   "
               f"({100.0 * r / summe if summe else 0.0:+7.1f} % des SumR)")
        n_k20 = sum(1 for t in tr if int(t.kid) in pro_kante)
        _z(f"     Kanten mit Trades: {len(pro_kante)} von "
           f"{len(scan['edges']) + len(scan['seeds'])} Linien")
        _z("")

    # ------------------------------------------------------------ Hebel
    _z("=" * 104)
    _z("HEBEL-GEGENUEBERSTELLUNG (post-hoc auf den vorhandenen Setups)")
    _z("  Kein Engine-Eingriff: gefiltert werden die bereits erzeugten Trades.")
    _z("")
    for lab in REIHENFOLGE:
        D = dossiers[lab]
        scan, tr = D["scan"], D["trades"]
        cl = scan["d"]["close"].to_numpy(dtype=float)
        summe = sum(float(t.r) for t in tr)
        _z("-" * 104)
        _z(f"{lab}   Ausgang: {len(tr)} Trades / {summe:+.6f} R")
        _z(f"  U2-Hebel -- Mindest-Durchstichtiefe:")
        for schw in U2_SCHWELLEN:
            behalten = []
            for t in tr:
                b, s = float(t.basis), float(t.sweep)
                d = ((s - b) if str(t.richtung) == "SHORT"
                     else (b - s)) / b * 100.0
                if d >= schw:
                    behalten.append(t)
            rs = sum(float(t.r) for t in behalten)
            _z(f"     >= {schw:5.2f} %  ->  {len(behalten):3d} Trades / "
               f"{rs:+10.6f} R   (entfernt {len(tr) - len(behalten):3d} / "
               f"{summe - rs:+10.6f} R)")
        _z(f"  U2b-Hebel -- Trendausrichtung (Vorlauf {TREND_LAG} Bars):")
        mit, gegen = [], []
        for t in tr:
            k = int(t.bar)
            if k < TREND_LAG:
                gegen.append(t)
                continue
            drift = cl[k] - cl[k - TREND_LAG]
            (mit if ((str(t.richtung) == "LONG" and drift > 0)
                     or (str(t.richtung) == "SHORT" and drift < 0))
             else gegen).append(t)
        _z(f"     mit dem Trend : {len(mit):3d} Trades / "
           f"{sum(float(t.r) for t in mit):+10.6f} R")
        _z(f"     gegen den Trend: {len(gegen):3d} Trades / "
           f"{sum(float(t.r) for t in gegen):+10.6f} R")
        _z(f"  U3-Hebel -- Zielpreis in der Naehe statt am Extremum:")
        nah = []
        hi_l = scan["d"]["high"].to_numpy(dtype=float)
        lo_l = scan["d"]["low"].to_numpy(dtype=float)
        for t in tr:
            eb = int(t.entry_bar)
            tp2 = float(t.tp2)
            if str(t.richtung) == "LONG":
                erreicht = float(hi_l[eb + 1:].max()) >= tp2
            else:
                erreicht = float(lo_l[eb + 1:].min()) <= tp2
            if erreicht:
                nah.append(t)
        _z(f"     Setups, deren tp2 im Restfenster ueberhaupt erreichbar "
           f"war: {len(nah):3d} / {len(tr)}")
        _z(f"     SumR dieser Setups: "
           f"{sum(float(t.r) for t in nah):+10.6f} R  "
           f"(nicht: SumR der tp2-Treffer)")
        _z("")

    _z("=" * 104)
    _z("BEFUNDE (Kurzfassung)")
    _z("  B1  Autonomie: WIDERLEGT fuer den Zuwachs. Die 18/+52.876174 sind an")
    _z("      die externe AUG-Tabelle ADAPTER_V019_KAUSAL gebunden. Ohne sie")
    _z("      bleiben 14/+42.450970 (AUG) -- und fuer MAI/JUN/JUL gibt es")
    _z("      ueberhaupt keine Grenzen (segmentwand_modus='AN' -> ValueError).")
    _z("  B2/B3/B4/B5: siehe Tabellen oben.")
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
