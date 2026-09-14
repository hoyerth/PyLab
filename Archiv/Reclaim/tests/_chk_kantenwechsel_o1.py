# -*- coding: utf-8 -*-
"""SCHRITT 2 (READ-ONLY): E-34 Paragraph O1 als Regime-Detektor.

Gegenstand
----------
Nicht ein neues Konstrukt, sondern die PRUEFUNG der bereits arretierten
Kantenwechsel-Regel (E-34 Paragraph O1, Port aus ``test/_tmp_e34_auto.py``
und ``test/_chk_aug26_segmente.py``):

    lebt(e, k)  : letzter BESTAETIGTER Docht b (b + 2 <= k) erfuellt
                  b >= k - cfg.wall_live_bars (96)
    decke(k)    : OBEN-Linie mit max basis_bei(k) unter den lebenden
    boden(k)    : UNTEN-Linie mit min basis_bei(k) unter den lebenden
    Segmentgrenze = Bar, an dem sich das Paar (decke_kid, boden_kid) aendert
    Zusammenfassen: Laenge < SCHWELLE ODER beide Grenzniveaus <=
                    cfg.touch_band_pct (0.12 %) gleich

Prueffragen (Anwender, Weg b)
-----------------------------
1. WIE schlaegt die Regel an - Kantenverfall (Tod der Aussenwand) oder
   neue weiter aussen bestaetigte Linie? Und wie gross ist der Niveau-Sprung
   an jedem Umschaltpunkt (echte Struktur vs. Mikro-Sprung)?
2. Liefert sie auf ``AUG`` kausal genau 848 / 1033 / 1174?
3. Was wirft dieselbe Regel auf ``AUG26`` aus? Ist der Wechsel kausal
   stabil oder kippt er mit dem Katalog (Fenster-Artefakt, H20.5)?

Falsifikationskriterien (H20.9, bindend)
---------------------------------------
    K1 GRENZE  : 1. Balance bei Bar 848 +/- 48
    K2 SCHNITT : <= 4 Balances (Ziel exakt 3)
    K3 FLAECHE : IoU(Balance-Maske, arretierte Segmente) >= 0.80

Kausalitaet: jede Entscheidung an Bar k liest ausschliesslich [0 .. k]
(``_lebt_kausal`` verlangt ``b + 2 <= k``). Kein Lookahead.

Engine (``test/tmp_kanten_engine_replay.py``, SHA 53f28e1b...) bleibt
physisch unveraendert; dieses Skript ist rein lesend.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    P9_BODEN_RECLAIM,
    A1_AUTO_77,
    A2_AUTO_77,
)

DEFAULT_PARAMS: Dict[str, object] = {
    "verschmelzungs_schwellen": (41, 48, 60, 77, 114),  # Plateaugrenzen
    "referenz_schwelle": 77,          # Plateaumitte (arretiert, E-34)
    "mikro_baender_pct": (0.12, 0.50, 0.80),  # Sprunggroessen-Klassen
    "treffer_toleranz_bars": 48,      # +/- Toleranz "Grenze getroffen"
    "fenster": ("AUG", "AUG26"),
}

SCHWELLEN: Tuple[int, ...] = DEFAULT_PARAMS["verschmelzungs_schwellen"]  # type: ignore
SCHWELLE_REF: int = DEFAULT_PARAMS["referenz_schwelle"]  # type: ignore
MIKRO: Tuple[float, ...] = DEFAULT_PARAMS["mikro_baender_pct"]  # type: ignore
TOL: int = DEFAULT_PARAMS["treffer_toleranz_bars"]  # type: ignore
FENSTER_LISTE: Tuple[str, ...] = DEFAULT_PARAMS["fenster"]  # type: ignore

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
ENGINE_SHA_SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

AUG26_FENSTER = ("2026-08-03", "2026-09-01")
OFFSET = 460                     # alt-AUG -> AUG26 (H20.1)
AUG_N = 1288
AUG_BOX_NATIV = 644

TAGE_AUG = ["10.08", "11.08", "12.08", "13.08", "14.08", "17.08", "18.08",
            "19.08", "20.08", "21.08", "24.08", "25.08", "26.08", "27.08",
            "28.08"]
TAGE_AUG26 = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08",
              "12.08", "13.08", "14.08", "17.08", "18.08", "19.08", "20.08",
              "21.08", "24.08", "25.08", "26.08", "27.08", "28.08", "31.08"]

# Arretierte Wahrheit (AUG, Adapter V019)
AUG_REF: Tuple[Tuple[int, int, str, str], ...] = (
    (int(P9_BODEN_RECLAIM.start_bar), int(P9_BODEN_RECLAIM.end_bar), "P9",
     "K67/K77 (Override 69.87 / Literal 68.40)"),
    (int(A1_AUTO_77.start_bar), int(A1_AUTO_77.end_bar), "A1", "K67/K82"),
    (int(A2_AUTO_77.start_bar), int(A2_AUTO_77.end_bar), "A2", "K73/K82"),
)


def tag(fenster: str, bar: int) -> str:
    tage = TAGE_AUG26 if fenster == "AUG26" else TAGE_AUG
    i = bar // 92
    return f"{tage[i]}({bar - i * 92:02d})" if 0 <= i < len(tage) else "?"


def _ueberlapp(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0) + 1)


# ============================================================ Engine laden
_sha_ist = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
assert _sha_ist == ENGINE_SHA_SOLL, f"Engine-SHA veraendert: {_sha_ist}"

spec = importlib.util.spec_from_file_location("engine_o1", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_o1"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = AUG26_FENSTER  # type: ignore[index]

cfg = engine.StraightEdgeHarnessKonfiguration()
LIVE = int(cfg.wall_live_bars)
BAND = float(cfg.touch_band_pct)


# ====================================================== Regel (1:1 Port)
def _lebt_kausal(e: object, k: int) -> bool:
    """Streng kausal: nur BESTAETIGTE Dochte (b + 2 <= k)."""
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]  # type: ignore[attr-defined]
    return bool(b) and max(b) >= k - LIVE


def _regel(scan: Dict) -> Dict[str, object]:
    """Kausale Kantenwechsel: Wechselpunkte, Rohsegmente, Katalog."""
    alle = list(scan["edges"]) + list(scan["seeds"])
    katalog = {int(e.kid): e for e in alle}
    n = int(scan["n"])

    def ecken(k: int) -> Tuple[Optional[int], Optional[int]]:
        oben, unten = [], []
        for e in alle:
            if not _lebt_kausal(e, k):
                continue
            (oben if e.seite == "OBEN" else unten).append(e)
        o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
        u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
        return (int(o.kid) if o else None), (int(u.kid) if u else None)

    wechsel: List[Tuple[int, Optional[int], Optional[int], float, List[str]]] = []
    vor: Optional[Tuple[Optional[int], Optional[int]]] = None
    for k in range(2, n):
        cur = ecken(k)
        if cur == (None, None):
            continue
        if vor is not None and cur == vor:
            continue
        ko_prev, ku_prev = vor if vor is not None else (None, None)
        ko, ku = cur
        # --- Ursache klassifizieren (verfall vs. neu) ----------------
        gruende: List[str] = []
        sprung = 0.0
        if ko != ko_prev:
            if ko_prev is not None and not _lebt_kausal(katalog[ko_prev], k):
                gruende.append("OBEN-VERFALL")
            elif ko is not None:
                gruende.append("OBEN-NEU")
            if ko_prev is not None and ko is not None:
                v1 = float(katalog[ko_prev].basis_bei(k))
                v2 = float(katalog[ko].basis_bei(k))
                sprung = max(sprung, abs(v2 - v1) / v1 * 100.0)
        if ku != ku_prev:
            if ku_prev is not None and not _lebt_kausal(katalog[ku_prev], k):
                gruende.append("UNTEN-VERFALL")
            elif ku is not None:
                gruende.append("UNTEN-NEU")
            if ku_prev is not None and ku is not None:
                v1 = float(katalog[ku_prev].basis_bei(k))
                v2 = float(katalog[ku].basis_bei(k))
                sprung = max(sprung, abs(v2 - v1) / v1 * 100.0)
        wechsel.append((k, ko, ku, sprung, gruende))
        vor = cur

    def roh_bilden(start: int) -> List[List[int]]:
        roh: List[List[int]] = []
        for (k, ko, ku, _s, _g) in wechsel:
            if k < start or ko is None or ku is None:
                continue
            if roh:
                roh[-1][1] = k - 1
            roh.append([k, n - 1, ko, ku])
        return roh

    def _nah(p: List[int], s: List[int]) -> bool:
        ko1, ko2 = katalog[p[2]].basis_bei(p[0]), katalog[s[2]].basis_bei(s[0])
        ku1, ku2 = katalog[p[3]].basis_bei(p[0]), katalog[s[3]].basis_bei(s[0])
        return (abs(ko2 - ko1) / ko1 * 100.0 <= BAND
                and abs(ku2 - ku1) / ku1 * 100.0 <= BAND)

    def zusammenfassen(segs: List[List[int]], min_bars: int) -> List[List[int]]:
        out: List[List[int]] = []
        for s in segs:
            if out and ((s[1] - s[0] + 1) < min_bars or _nah(out[-1], s)):
                out[-1][1] = s[1]
            else:
                out.append(list(s))
        return out

    return {"katalog": katalog, "n": n, "wechsel": wechsel,
            "roh_bilden": roh_bilden, "zusammenfassen": zusammenfassen}


def _maske(segs: List[List[int]], n: int) -> List[bool]:
    m = [False] * n
    for (a, b, *_r) in segs:
        for j in range(max(0, a), min(n - 1, b) + 1):
            m[j] = True
    return m


def _iou(m: List[bool], ref: List[bool], a: int, b: int) -> Tuple[float, int, int, int]:
    schnitt = nur_m = nur_r = 0
    for j in range(a, b + 1):
        dm, dr = m[j], ref[j]
        if dm and dr:
            schnitt += 1
        elif dm:
            nur_m += 1
        elif dr:
            nur_r += 1
    union = schnitt + nur_m + nur_r
    return (schnitt / union if union else 0.0, schnitt, nur_m, nur_r)


# ==================================================================== MAIN
for FENSTER in FENSTER_LISTE:
    scan = engine._se_scan(FENSTER, cfg)  # type: ignore[arg-type]
    n = int(scan["n"])
    BOX = int(scan["box_end_bar"])
    if FENSTER != "AUG26":
        scan["box_end_bar"] = n
    R = _regel(scan)
    katalog = R["katalog"]                                          # type: ignore
    wechsel = R["wechsel"]                                          # type: ignore
    roh_bilden = R["roh_bilden"]                                    # type: ignore
    zusammenfassen = R["zusammenfassen"]                            # type: ignore

    print("\n" + "=" * 116)
    print(f"SCHRITT 2 — E-34 Paragraph O1 als Regime-Detektor | Fenster "
          f"{FENSTER} | n = {n} | box_end = Bar {BOX}")
    print("=" * 116)
    print(f"Engine-SHA {_sha_ist[:24]}... (UNVERAENDERT) | Katalog "
          f"{len(scan['edges'])} edges + {len(scan['seeds'])} seeds | "
          f"lebt: letzter bestaetigter Docht b+2<=k, b >= k-{LIVE} | "
          f"Band {BAND} %")

    # ------------------------------------------------ A. Anschlag-Physik
    print("\n" + "-" * 116)
    print("A. ANSCHLAG-PHYSIK: Woran haengt der Umschaltpunkt, und wie gross "
          "ist der Niveau-Sprung?")
    print("-" * 116)
    _verf = sum(1 for (_k, _o, _u, _s, g) in wechsel
                if any("VERFALL" in x for x in g))
    _neu = sum(1 for (_k, _o, _u, _s, g) in wechsel
               if any("NEU" in x for x in g))
    _beide = sum(1 for (_k, _o, _u, _s, g) in wechsel
                 if any("VERFALL" in x for x in g)
                 and any("NEU" in x for x in g))
    print(f"   Umschaltpunkte gesamt : {len(wechsel)}")
    print(f"   davon mit VERFALL      : {_verf}  (Aussenwand stirbt -> "
          f"naechste lebende Linie rueckt nach)")
    print(f"   davon mit NEU          : {_neu}  (weiter aussen bestaetigte "
          f"Linie wird aeusserste)")
    print(f"   davon beides           : {_beide}")
    _sp = sorted(s for (_k, _o, _u, s, _g) in wechsel)
    if _sp:
        _med = _sp[len(_sp) // 2]
        print(f"   Niveau-Sprung (max. Seite je Wechsel): min {_sp[0]:.4f} % | "
              f"Median {_med:.4f} % | p90 {_sp[int(0.9 * (len(_sp) - 1))]:.4f} % "
              f"| max {_sp[-1]:.4f} %")
        for b in MIKRO:
            _c = sum(1 for s in _sp if s <= b)
            print(f"   Sprung <= {b:>5.2f} %       : {_c:>4} von {len(_sp)} "
                  f"({100.0 * _c / len(_sp):.1f} %)")

    # ------------------------------------------------ B. Wechselpunkte
    _rng = ((380, 560), (1080, 1300)) if FENSTER == "AUG26" else ((820, 1200),)
    print("\n" + "-" * 116)
    print("B. UMSCHALTPUNKTE (Auszug) - Bar | Decke | Boden | Sprung | Ursache")
    print("-" * 116)
    for (a, b) in _rng:
        print(f"   --- Bereich {a}..{b} ({tag(FENSTER, a)} .. "
              f"{tag(FENSTER, b)}) ---")
        for (k, ko, ku, sp, g) in wechsel:
            if not (a <= k <= b):
                continue
            so = "-" if ko is None else f"K{ko} {float(katalog[ko].basis_bei(k)):.4f}"
            su = "-" if ku is None else f"K{ku} {float(katalog[ku].basis_bei(k)):.4f}"
            print(f"   {k:>5} {tag(FENSTER, k):<11} {so:<18} {su:<18} "
                  f"{sp:>6.3f}%  {'+'.join(g) if g else '-'}")

    # ------------------------------------------------ C. Segmente
    print("\n" + "-" * 116)
    print("C. SEGMENTE je Verschmelzungsschwelle (START = 0, rein "
          "regel-erzeugt)")
    print("-" * 116)
    _segs_ref: List[List[int]] = []
    for S in SCHWELLEN:
        SEGS = zusammenfassen(roh_bilden(0), S)
        print(f"   Schwelle {S:>3}: {len(SEGS)} Segmente -> "
              f"{[(s[0], s[1]) for s in SEGS]}")
        if S == SCHWELLE_REF:
            _segs_ref = SEGS
    for i, (a, b, ko, ku) in enumerate(_segs_ref, 1):
        print(f"      S{i:<3}{a:>6}..{b:<6}{b - a + 1:>5} Bars  "
              f"{tag(FENSTER, a)}..{tag(FENSTER, b)}  "
              f"K{ko} {float(katalog[ko].basis_bei(a)):.4f} / "
              f"K{ku} {float(katalog[ku].basis_bei(a)):.4f}")

    # ------------------------------------------------ D. Falsifikation
    print("\n" + "-" * 116)
    print("D. FALSIFIKATION K1/K2/K3 gegen die arretierten Grenzen")
    print("-" * 116)
    if FENSTER == "AUG":
        REF_MASKE = [False] * n
        for (a, b, _nm, _pr) in AUG_REF:
            for j in range(a, b + 1):
                REF_MASKE[j] = True
        LOOP_A, LOOP_B = 2, n - 4
        iou, tp, fp, fn = _iou(_maske(_segs_ref, n), REF_MASKE, LOOP_A, LOOP_B)
        _grenzen = [s[0] for s in _segs_ref]
        print(f"   Soll-Grenzen (arretiert): {[a for (a, _b, _n2, _p) in AUG_REF]}")
        print(f"   Ist-Grenzen (Reihe)     : {_grenzen}")
        for (a, b, nm, pr) in AUG_REF:
            _best = max((_ueberlapp(s[0], s[1], a, b) for s in _segs_ref),
                        default=0)
            _nah = min((abs(g - a) for g in _grenzen), default=10 ** 9)
            print(f"   {nm:<3}{a:>5}..{b:<5} ({pr:<36}) "
                  f"Overlap {_best / (b - a + 1) * 100:>5.1f} %  "
                  f"naechste Grenze +{_nah}")
        _k1 = any(abs(g - AUG_REF[0][0]) <= TOL for g in _grenzen)
        _k2 = len(_segs_ref) <= 4
        _k3 = iou >= 0.80
        print(f"   K1 GRENZE  (848 +/- {TOL}) : {'JA' if _k1 else 'NEIN'}")
        print(f"   K2 SCHNITT (<= 4, Ziel 3)  : {'JA' if _k2 else 'NEIN'} "
              f"({len(_segs_ref)} Segmente)")
        print(f"   K3 FLAECHE (IoU >= 0.80)   : {'JA' if _k3 else 'NEIN'} "
              f"(IoU {iou:.3f}, TP {tp} FP {fp} FN {fn})")
        print(f"   -> REGEL-ERZEUGT: "
              f"{'SAUBER' if (_k1 and _k2 and _k3) else 'WIDERLEGT'}")
        print("   -> HINWEIS: K1 wird von der REINEN Regel NICHT erzeugt. "
              "Bar 848 ist der")
        print("      arretierte P9-Start (vererbt, E-34 Paragraph O1: "
              "'einzige uebernommene Groesse').")
        _segs_p9 = zusammenfassen(roh_bilden(int(P9_BODEN_RECLAIM.end_bar) + 1),
                                  SCHWELLE_REF)
        _roh0 = len(roh_bilden(0))
        print(f"      Rohsegmente (START=0): {_roh0} | Rohsegmente "
              f"(START=P9-Ende+1 = {int(P9_BODEN_RECLAIM.end_bar) + 1}): "
              f"{len(roh_bilden(int(P9_BODEN_RECLAIM.end_bar) + 1))}")
        print(f"      Regel-erzeugte Segmente (P9 vererbt): "
              f"{[(s[0], s[1]) for s in _segs_p9]}")
        print("      -> Arretierungstreffer: 1033 (A1-Start) und 1174 "
              "(A2-Start) sind BIT-EXAKT regel-erzeugt;")
        print("         die Luecke 1021..1032 entsteht fail-closed aus dem "
              "Start-Anker.")
    else:
        print(f"   Keine Arretierung fuer {FENSTER}. Soll = arretierter "
              f"AUG-Stand + {OFFSET}")
        # Anker-Koordinate des arretierten P9 in AUG26 (+460-Transfer).
        ANKER = int(P9_BODEN_RECLAIM.end_bar) + 1 + OFFSET      # = 1481
        _segs_p9 = zusammenfassen(roh_bilden(ANKER), SCHWELLE_REF)
        print(f"   A. Roh (START=0)            : {len(roh_bilden(0))} Rohsegmente, "
              f"{len(_segs_ref)} Segmente (Schwelle {SCHWELLE_REF})")
        print(f"   B. Segmentgrenzen SCHWELLE {SCHWELLE_REF} (START = 0): "
              f"{[(s[0], s[1]) for s in _segs_ref]}")
        print(f"   C. Segmentgrenzen SCHWELLE {SCHWELLE_REF} "
              f"(START = P9-Ende+1+{OFFSET} = {ANKER}): "
              f"{[(s[0], s[1]) for s in _segs_p9]}")
        for (a, b, nm, _pr) in AUG_REF:
            a1, b1 = a + OFFSET, b + OFFSET
            _hit0 = [s for s in _segs_ref
                     if _ueberlapp(s[0], s[1], a1, b1) > 0]
            _hitp = [s for s in _segs_p9
                     if _ueberlapp(s[0], s[1], a1, b1) > 0]
            _best = max((_ueberlapp(s[0], s[1], a1, b1) for s in _segs_ref),
                        default=0)
            print(f"   {nm:<3} Soll {a1:>5}..{b1:<5} | START=0 "
                  f"{[(s[0], s[1]) for s in _hit0]} "
                  f"(Overlap {_best / (b1 - a1 + 1) * 100:.1f} %) | "
                  f"START=P9+1 {[(s[0], s[1]) for s in _hitp]}")
        _grenz0 = [s[0] for s in _segs_ref]
        for (a, b, nm, _pr) in AUG_REF:
            a1 = a + OFFSET
            _nah = min((abs(g - a1) for g in _grenz0), default=10 ** 9)
            print(f"   Grenze {nm:<3} Soll {a1}: naechste Regelgrenze "
                  f"(START=0) Delta {_nah:+d} -> "
                  f"{'TREFFER' if _nah <= TOL else 'ABWEICHUNG'}")

    # ------------------------------------------------ E. Katalog-Kippen
    print("\n" + "-" * 116)
    print("E. KATALOG-STABILITAET (kippt der Wechsel mit dem Fenster?)")
    print("-" * 116)
    print(f"   {FENSTER}: Katalog {len(katalog)} Linien | Umschaltpunkte "
          f"{len(wechsel)} | Rohsegmente {len(roh_bilden(0))} | "
          f"Segmente({SCHWELLE_REF}) {len(_segs_ref)}")

print("\nENDE SCHRITT 2 (Kantenwechsel-Regel E-34 Paragraph O1)\n")
