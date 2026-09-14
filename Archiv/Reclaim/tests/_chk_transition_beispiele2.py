# -*- coding: utf-8 -*-
"""READ-ONLY Empirie v2: Unterschied 14.08. (ERWEITERUNG) vs. 19.08. (echtes Verlassen).

LOOKAHEAD-FIX gegenueber v1: Kanten, deren ``geburts_bar`` NACH dem Pruef-Bar liegt,
duerfen NICHT erscheinen. v1 listete sie ueber den ``basis_bei``-Fallback
(``wicks[0][1]``) mit -> ungueltig. v2 filtert hart auf ``geburts_bar <= k`` UND
``min(wick-bar) <= k``.

Hypothese des Anwenders:
  1) 14.08. = Erweiterung, weil eine HISTORISCHE Kante aus der VORHERIGEN Balance
     bei 63.7 (10.08. 15:00) existierte und LEBEND blieb.
  2) 19.08. 01:00-08:00 = Verlassen der UNTERKANTE OHNE vorhergehende Gegenkante
     -> leerer Raum unter der gebrochenen Grenze.

Kein Patch, kein Einbrand. Engine-SHA hart geprueft.
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
_sha = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
assert _sha == ENGINE_SHA_SOLL, f"Engine-SHA veraendert: {_sha}"

_spec = importlib.util.spec_from_file_location("engine_bt2", ENGINE_P)
engine = importlib.util.module_from_spec(_spec)
sys.modules["engine_bt2"] = engine
_spec.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]

cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = int(scan["n"])
D = scan["d"]
TS = list(D["ts"])
op = D["open"].to_numpy(dtype=float)
hi = D["high"].to_numpy(dtype=float)
lo = D["low"].to_numpy(dtype=float)
cl = D["close"].to_numpy(dtype=float)

EDGES: List[object] = list(scan["edges"])
SEEDS: List[object] = list(scan["seeds"])
ALLE = EDGES + SEEDS
LIVE = int(cfg.wall_live_bars)

TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08",
        "12.08", "13.08", "14.08", "17.08", "18.08", "19.08", "20.08",
        "21.08", "24.08", "25.08", "26.08", "27.08", "28.08", "31.08"]


def kind(e: object) -> str:
    return "S" if e in SEEDS else "E"  # type: ignore[operator]


def bekannt(e: object, k: int) -> bool:
    """Kante ist bei Bar k BEKANNT: Geburt <= k UND mind. ein Docht <= k."""
    if int(e.geburts_bar) > k:  # type: ignore[attr-defined]
        return False
    return any(b <= k for b, _ in e.wicks)  # type: ignore[attr-defined]


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def basis(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def info(e: object, k: int) -> str:
    w = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    letzter = max(w) if w else -1
    tc = sum(1 for b, _ in e.wicks if b + 2 <= k)  # type: ignore[attr-defined]
    return (f"{kind(e)}K{int(e.kid):<4}{e.seite[0]} @{basis(e,k):>8.4f} "
            f"geb{int(e.geburts_bar):>4} piv{int(e.erster_pivot_bar):>4} w{len(e.wicks):>2} "
            f"tc{tc:>2} letztd{letzter:>4} age{k-int(e.erster_pivot_bar):>4} "
            f"{'prim' if e.ist_prim_anker else 'norm'} {e.status:<9} leb={'J' if lebt(e,k) else '-'}")


print("=" * 132)
print(f"TAGES-OHLC (Bars 00:00-22:45) | n={n}")
print("=" * 132)
for i, t in enumerate(TAGE):
    b0, b1 = 92 * i, min(92 * i + 91, n - 1)
    if b0 >= n:
        break
    print(f"  {t} Bars {b0:>4}..{b1:<4} O{op[b0]:>8.4f} H{hi[b0:b1+1].max():>8.4f} "
          f"L{lo[b0:b1+1].min():>8.4f} C{cl[b1]:>8.4f}")

# ------------------------------------------------------------------ Fall A
print("\n" + "=" * 132)
print("FALL A) 14.08. -- Erweiterung? Historische Kante bei ~63.7 (10.08. 15:00)")
print("=" * 132)
print("  Kandidaten im Band 63.4..64.0, BEKANNT bei Bar 890 (14.08. 15:30), OHNE Lookahead:")
for e in sorted(ALLE, key=lambda x: basis(x, 890)):
    if not bekannt(e, 890):
        continue
    if 63.4 <= basis(e, 890) <= 64.05:
        print("   " + info(e, 890))

print("\n  Detail: die mutmassliche historische Kante (Geburt exakt 10.08 15:00 = Bar 520):")
for e in ALLE:
    if int(e.geburts_bar) in (512, 520) and e.seite == "UNTEN":  # type: ignore[attr-defined]
        print("   " + info(e, 890))
        print(f"        wicks(=alle Dochte): {[(b, round(p,4)) for b, p in e.wicks]}")

print("\n  Untere definierende Grenze der Balance am 14.08. (aeusserste LEBENDE UNTEN-Kante):")
for k in (828, 860, 890, 893, 900, 919):
    un = sorted([basis(e, k) for e in ALLE if bekannt(e, k) and lebt(e, k) and e.seite == "UNTEN"])
    ob = sorted([basis(e, k) for e in ALLE if bekannt(e, k) and lebt(e, k) and e.seite == "OBEN"])
    print(f"   Bar {k:>4} {TS[k]}  Low={lo[k]:.4f}  lebUNTEN_min={un[0]:.4f}({len(un)})  "
          f"lebOBEN_max={ob[-1]:.4f}({len(ob)})  UNTERGRENZE_gebrochen={'JA' if lo[k] < un[0] else 'nein'}")

# ------------------------------------------------------------------ Fall B
print("\n" + "=" * 132)
print("FALL B) 19.08. 01:00-08:00 -- Verlassen der Unterkante (Bar 1108..1136)")
print("=" * 132)
print("  LEBENDE UNTEN-Kanten je Bar, aufsteigend (naechstgelegene unten zuerst):")
for k in (1104, 1108, 1109, 1110, 1116, 1117, 1132, 1136):
    un = sorted([(basis(e, k), e) for e in ALLE if bekannt(e, k) and lebt(e, k) and e.seite == "UNTEN"])
    txt = " | ".join(f"{kind(e)}K{int(e.kid)}@{b:.4f}(age{k-int(e.erster_pivot_bar)})" for b, e in un[:6])
    unterm = [b for b, _e in un if b < lo[k]]
    print(f"   Bar {k:>4} {TS[k]} Lo={lo[k]:.4f} Cl={cl[k]:.4f} lebUNTEN=[{txt}]")
    print(f"        -> lebende Kanten UNTER dem Tief: {len(unterm)}"
          + (f" (tiefste {min(unterm):.4f}, Abst. {(lo[k]-min(unterm))/lo[k]*100:.2f}%)" if unterm else " (VAKUUM)"))

print("\n  VAKUUM-CHECK: niedrigste LEBENDE Unterkante bei Bar 1108 und ihr Abstand zum Close:")
k = 1108
un = sorted([(basis(e, k), e) for e in ALLE if bekannt(e, k) and lebt(e, k) and e.seite == "UNTEN"])
for b, e in un:
    print(f"   {kind(e)}K{int(e.kid):<4} @{b:>8.4f}  Abstand Close {cl[k]:.4f} -> {(cl[k]-b)/b*100:+.2f}%")
print("   Nicht-lebende Unterkanten unterhalb 63.0 (Existenz, aber tot = nicht praesent):")
for e in sorted(ALLE, key=lambda x: basis(x, k)):
    if e.seite == "UNTEN" and bekannt(e, k) and basis(e, k) < 63.0:
        print("   " + info(e, k))

# ------------------------------------------------------------------ Vergleich
print("\n" + "=" * 132)
print("DIREKTER VERGLEICH DER BEIDEN FAELLE")
print("=" * 132)
for name, k0, k1, richtung in (("14.08.", 886, 900, "OBEN"), ("19.08.", 1104, 1136, "UNTEN")):
    print(f"\n  {name} Richtung {richtung}:")
    for k in range(k0, k1 + 1):
        al = [e for e in ALLE if bekannt(e, k) and lebt(e, k)]
        oben = sorted([basis(e, k) for e in al if e.seite == "OBEN"])
        unten = sorted([basis(e, k) for e in al if e.seite == "UNTEN"])
        o = oben[-1] if oben else float("nan")
        u = unten[0] if unten else float("nan")
        durch_ob = hi[k] > o
        durch_un = lo[k] < u
        if durch_ob or durch_un:
            print(f"   Bar {k:>4} {TS[k]} H={hi[k]:.4f} L={lo[k]:.4f} C={cl[k]:.4f} | "
                  f"OBENmax={o:.4f}{' <== DURCH' if durch_ob else ''} "
                  f"UNTENmin={u:.4f}{' <== DURCH' if durch_un else ''}")

print("\nENDE v2\n")
