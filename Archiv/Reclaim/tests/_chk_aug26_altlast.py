# -*- coding: utf-8 -*-
"""H20.18 (READ-ONLY): Whole-August AUG26 -- Altlast-Test der E-34 Paragraph-O1-Regel.

Fragestellung des Anwenders
---------------------------
"Wenn wir den ganzen August 2026 abfahren, muessten wir unsere erforschten
Bereiche automatisch genauso finden -- WENN wir keine alten Kanten
mitschleppen und Balance-Phasen sicher als aktiv / nicht aktiv erkennen."

Dieses Skript ist rein lesend. Die Engine (``tmp_kanten_engine_replay.py``)
bleibt physisch unberuehrt; das AUG26-Fenster wird nur zur Laufzeit in
``engine.FENSTER`` ergaenzt.

Drei Katalog-Varianten (identische Regel, nur der Linien-Vorrat aendert sich)
-----------------------------------------------------------------------------
    V_full   : edges + seeds (Fensterende-Singletons)      -- Baseline
    V_noseed : nur edges  (keine Singleton-Altlast am Ende)
    V_kausal : nur edges mit ``geburts_bar <= k``  (strikt kausal)

Die Regel (Port 1:1 aus ``_chk_kantenwechsel_o1.py`` / ``_tmp_e34_auto.py``)::

    lebt(e, k) : letzter BESTAETIGTER Docht b (b+2<=k) erfuellt b >= k - 96
    decke(k)   : OBEN-Linie mit max basis_bei(k) unter den lebenden
    boden(k)   : UNTEN-Linie mit min basis_bei(k) unter den lebenden

Messungen
---------
A. Divergenz der Varianten: erster Bar, an dem ``ecken(k)`` abweicht --
   plus Gesamtzahl abweichender Bars.  (Beweist/entlarvt Lookahead.)
B. Aktiv / Inaktiv: Bars ohne gueltiges Paar (eine Seite None) = Luecke.
C. Segmentgrenzen je Verschmelzungsschwelle fuer jede Variante (START = 0,
   KEIN Anker -- "keine alten Kanten mitschleppen").
D. Abgleich mit dem arretierten AUG-Stand, um +460 verschoben.
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

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
ENGINE_SHA_SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

AUG26_FENSTER = ("2026-08-03", "2026-09-01")
OFFSET = 460                                    # alt-AUG -> AUG26 (H20.1)
SCHWELLEN = (41, 48, 60, 77, 114)
SCHWELLE_REF = 77

# Arretierte AUG-Grenzen (Adapter V019) -> AUG26-Koordinaten
AUG_REF: Tuple[Tuple[int, int, str], ...] = (
    (848, 1020, "P9"),          # +460 -> 1308..1480
    (1033, 1173, "A1"),         # +460 -> 1493..1633
    (1174, 1287, "A2"),         # +460 -> 1634..1747
)

TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08",
        "12.08", "13.08", "14.08", "17.08", "18.08", "19.08", "20.08",
        "21.08", "24.08", "25.08", "26.08", "27.08", "28.08", "31.08"]

VARIANTEN = ("V_full", "V_noseed", "V_kausal")


def tag(bar: int) -> str:
    """Trading-Day-Kuerzel + Minute aus dem Bar-Index (92 Bars je Tag)."""
    i = bar // 92
    return f"{TAGE[i]}({bar - i * 92:02d})" if 0 <= i < len(TAGE) else "?"


def _ueberlapp(a0: int, a1: int, b0: int, b1: int) -> int:
    """Schnittmenge zweier inklusiver Intervalle in Bars."""
    return max(0, min(a1, b1) - max(a0, b0) + 1)


# ============================================================ Engine laden
_sha_ist = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
assert _sha_ist == ENGINE_SHA_SOLL, f"Engine-SHA veraendert: {_sha_ist}"

_spec = importlib.util.spec_from_file_location("engine_alt", ENGINE_P)
engine = importlib.util.module_from_spec(_spec)
sys.modules["engine_alt"] = engine
_spec.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = AUG26_FENSTER  # type: ignore[index]

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
BOX = int(scan["box_end_bar"])
scan["box_end_bar"] = n

D = scan["d"]
TS = list(D["ts"])
EDGES = list(scan["edges"])
SEEDS = list(scan["seeds"])
LIVE = int(cfg.wall_live_bars)
BAND = float(cfg.touch_band_pct)


def _lebt_kausal(e: object, k: int) -> bool:
    """Streng kausal: nur BESTAETIGTE Dochte (b + 2 <= k)."""
    b = [bb for bb, _ in e.wicks]  # type: ignore[attr-defined]
    b = [bb for bb in b if bb + 2 <= k]
    return bool(b) and max(b) >= k - LIVE


def _katalog(var: str) -> List[object]:
    """Linien-Vorrat je Variante."""
    if var == "V_full":
        return EDGES + SEEDS
    if var == "V_noseed":
        return list(EDGES)
    return list(EDGES)                     # V_kausal filtert je Bar


def _katalog_k(var: str, k: int) -> List[object]:
    """Linien-Vorrat bei Bar k -- V_kausal schneidet die Zukunft ab."""
    if var == "V_kausal":
        return [e for e in EDGES if int(e.geburts_bar) <= k]  # type: ignore[attr-defined]
    return _katalog(var)


def _ecken(var: str, k: int) -> Tuple[Optional[int], Optional[int]]:
    """(decke_kid, boden_kid) = aeusserste lebende Linien, kausal."""
    oben: List[object] = []
    unten: List[object] = []
    for e in _katalog_k(var, k):
        if not _lebt_kausal(e, k):
            continue
        (oben if e.seite == "OBEN" else unten).append(e)  # type: ignore[attr-defined]
    o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
    u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
    return (int(o.kid) if o else None), (int(u.kid) if u else None)  # type: ignore[attr-defined]


def _reihe(var: str) -> List[Tuple[Optional[int], Optional[int]]]:
    """Ecken-Reihe ueber alle Bars (Index = Bar)."""
    return [(_ecken(var, k) if k >= 2 else (None, None)) for k in range(n)]


# ==================================================================== MAIN
print("=" * 116)
print(f"H20.18 -- WHOLE-AUGUST AUG26 | AL TLAST-TEST DER O1-REGEL | n = {n} "
      f"| box_end(nativ) = Bar {BOX}")
print("=" * 116)
print(f"Engine-SHA {_sha_ist[:24]}... (UNVERAENDERT)")
print(f"Katalog: {len(EDGES)} edges + {len(SEEDS)} seeds = {len(EDGES) + len(SEEDS)} "
      f"Linien | lebt: letzter bestaetigter Docht b+2<=k, b >= k-{LIVE} | "
      f"Band {BAND} %")
print(f"Fenster {AUG26_FENSTER[0]}..{AUG26_FENSTER[1]} (endexklusiv) | "
      f"ts[0] = {TS[0]} | ts[-1] = {TS[-1]}")

REIHEN: Dict[str, List[Tuple[Optional[int], Optional[int]]]] = {
    var: _reihe(var) for var in VARIANTEN
}

# ------------------------------------------------------------ A. Divergenz
print("\n" + "-" * 116)
print("A. KATALOG-DIVERGENZ (entlarvt Lookahead / Altlast)")
print("-" * 116)
for var in ("V_noseed", "V_kausal"):
    diff = [k for k in range(n) if REIHEN[var][k] != REIHEN["V_full"][k]]
    print(f"   V_full  vs. {var:<8}: {len(diff):>4} abweichende Bars"
          + (f" | erster {diff[0]} ({tag(diff[0])})" if diff else " -> IDENTISCH"))
    for k in diff[:12]:
        print(f"        Bar {k:>5} {tag(k):<10} full={REIHEN['V_full'][k]} "
              f"| {var}={REIHEN[var][k]}")
    if len(diff) > 12:
        print(f"        ... (+{len(diff) - 12} weitere)")

# ------------------------------------------------ B. Aktiv / Inaktiv
print("\n" + "-" * 116)
print("B. BALANCE AKTIV / INAKTIV -- Bars ohne gueltiges Paar (eine Seite None)")
print("-" * 116)
for var in VARIANTEN:
    luecken_bars = [k for k in range(2, n)
                    if REIHEN[var][k][0] is None or REIHEN[var][k][1] is None]
    bloecke: List[Tuple[int, int]] = []
    for k in luecken_bars:
        if bloecke and bloecke[-1][1] + 1 == k:
            bloecke[-1] = (bloecke[-1][0], k)
        else:
            bloecke.append((k, k))
    anteil = 100.0 * len(luecken_bars) / (n - 2)
    print(f"   {var:<9}: {len(luecken_bars):>4} inaktive Bars ({anteil:5.1f} %) "
          f"in {len(bloecke)} Block/Luecken")
    for (a, b) in bloecke[:20]:
        print(f"        {a:>5}..{b:<5} ({b - a + 1:>4} Bars)  {tag(a)}..{tag(b)}")
    if len(bloecke) > 20:
        print(f"        ... (+{len(bloecke) - 20} weitere)")

# ------------------------------------------------ C. Segmentgrenzen
def _wechsel(var: str) -> List[Tuple[int, Optional[int], Optional[int]]]:
    """Umschaltpunkte des Paares, kausal."""
    out: List[Tuple[int, Optional[int], Optional[int]]] = []
    vor: Optional[Tuple[Optional[int], Optional[int]]] = None
    for k in range(2, n):
        cur = REIHEN[var][k]
        if cur == (None, None):
            continue
        if vor is not None and cur == vor:
            continue
        vor = cur
        out.append((k, cur[0], cur[1]))
    return out


def _roh_bilden(wechsel: List[Tuple[int, Optional[int], Optional[int]]],
                start: int) -> List[List[int]]:
    """Rohe Segmente (Start = Wechselbar, Ende = naechster Wechsel - 1)."""
    roh: List[List[int]] = []
    for (k, ko, ku) in wechsel:
        if k < start or ko is None or ku is None:
            continue
        if roh:
            roh[-1][1] = k - 1
        roh.append([k, n - 1, ko, ku])
    return roh


def _zusammenfassen(segs: List[List[int]], min_bars: int,
                    kat: Dict[int, object]) -> List[List[int]]:
    """Verschmelzen: zu kurz ODER beide Grenzniveaus <= BAND gleich."""
    def _nah(p: List[int], s: List[int]) -> bool:
        ko1, ko2 = kat[p[2]].basis_bei(p[0]), kat[s[2]].basis_bei(s[0])
        ku1, ku2 = kat[p[3]].basis_bei(p[0]), kat[s[3]].basis_bei(s[0])
        return (abs(ko2 - ko1) / ko1 * 100.0 <= BAND
                and abs(ku2 - ku1) / ku1 * 100.0 <= BAND)

    out: List[List[int]] = []
    for s in segs:
        if out and ((s[1] - s[0] + 1) < min_bars or _nah(out[-1], s)):
            out[-1][1] = s[1]
        else:
            out.append(list(s))
    return out


KAT: Dict[int, object] = {int(e.kid): e for e in EDGES + SEEDS}

print("\n" + "-" * 116)
print("C. SEGMENTE je Schwelle (START = 0, KEIN Anker) -- je Variante")
print("-" * 116)
SEGS_JE: Dict[str, Dict[int, List[List[int]]]] = {}
for var in VARIANTEN:
    wechsel = _wechsel(var)
    print(f"\n   {var} -- {len(wechsel)} Umschaltpunkte, "
          f"{len(_roh_bilden(wechsel, 0))} Rohsegmente")
    SEGS_JE[var] = {}
    for S in SCHWELLEN:
        segs = _zusammenfassen(_roh_bilden(wechsel, 0), S, KAT)
        SEGS_JE[var][S] = segs
        print(f"      Schwelle {S:>3}: {len(segs):>2} Segmente -> "
              f"{[(s[0], s[1]) for s in segs]}")
    segs = SEGS_JE[var][SCHWELLE_REF]
    for i, (a, b, ko, ku) in enumerate(segs, 1):
        print(f"         S{i:<2} {a:>5}..{b:<5} ({b - a + 1:>4}) "
              f"{tag(a)}..{tag(b)}  K{ko} {KAT[ko].basis_bei(a):.4f} / "
              f"K{ku} {KAT[ku].basis_bei(a):.4f}")

# ------------------------------------------------ D. Abgleich +460
print("\n" + "-" * 116)
print("D. ABGLEICH mit dem arretierten AUG-Stand (+460)")
print("-" * 116)
print(f"   {'Soll':<20}{'V_full':<26}{'V_noseed':<26}{'V_kausal':<26}")
for (a0, b0, nm) in AUG_REF:
    a1, b1 = a0 + OFFSET, b0 + OFFSET
    zeile = f"   {f'{nm} {a1}..{b1}':<20}"
    for var in VARIANTEN:
        segs = SEGS_JE[var][SCHWELLE_REF]
        hit = [s for s in segs
               if s[0] <= a1 <= s[1] or s[0] <= b1 <= s[1]
               or (a1 <= s[0] and s[1] <= b1)]
        if hit:
            s = hit[0]
            mark = "=" if (s[0] == a1 and s[1] == b1) else "~"
            zeile += f"{mark}{s[0]}..{s[1]:<20}"
        else:
            zeile += f"{'NICHT gefunden':<26}"
    print(zeile)

print("\n   Grenzen-Delta je Variante (naechste Regelgrenze zur Sollgrenze):")
for var in VARIANTEN:
    grenzen = [s[0] for s in SEGS_JE[var][SCHWELLE_REF]]
    teile = []
    for (a0, _b0, nm) in AUG_REF:
        a1 = a0 + OFFSET
        d = min((abs(g - a1) for g in grenzen), default=10 ** 9)
        teile.append(f"{nm} {d:+d}")
    print(f"   {var:<9}: {' | '.join(teile)}  | Grenzen {grenzen}")

# ------------------------------------------------ E. Seeds am Fensterende
print("\n" + "-" * 116)
print("E. FENSTERENDE-SINGLETONS (seeds) -- wo liegen sie?")
print("-" * 116)
for e in sorted(SEEDS, key=lambda x: int(x.basis)):
    wis = e.wicks if isinstance(e.wicks, list) else list(e.wicks)
    b0 = wis[0][0] if wis else -1
    print(f"   K{int(e.kid):<4} {e.seite:<5} basis={float(e.basis):9.4f} "
          f"geburts_bar={int(e.geburts_bar):>5} ({tag(int(e.geburts_bar))}) "
          f"erster_docht={int(b0):>5} n_dochte={len(wis)}")

print("\nENDE H20.18 (Altlast-Test AUG26)\n")
