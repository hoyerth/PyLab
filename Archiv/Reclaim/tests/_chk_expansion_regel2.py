# -*- coding: utf-8 -*-
"""READ-ONLY: 2-Body-Aussenbewegungen + Kissen/Vakuum + Halte-Test.

Verdichtung auf echte Ausbrueche (Regel A oder C feuert). Drei Achsen:
  * VORHER-Kissen: lebende Kante mit geburt <= k-2 im Bewegungsziel (kein
    Selbst-Beweis: in der Bewegung geborene Kanten zaehlen NICHT).
  * VAKUUM: kein Vorher-Kissen.
  * HALTE-TEST: kehrt der Close innerhalb von 6 Bars in den alten Korridor
    zurueck?  JA -> Erweiterung, NEIN -> Verlassen (Transition-Kandidat).

Kein Patch, kein Einbrand.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))
ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
assert hashlib.sha256(ENGINE_P.read_bytes()).hexdigest() == \
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"
_s = importlib.util.spec_from_file_location("eng6", ENGINE_P)
engine = importlib.util.module_from_spec(_s)
sys.modules["eng6"] = engine
_s.loader.exec_module(engine)  # type: ignore[union-attr]
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
E = list(scan["edges"])
S = list(scan["seeds"])
ALLE = E + S
LIVE = int(cfg.wall_live_bars)
TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08", "12.08",
        "13.08", "14.08", "17.08", "18.08", "19.08", "20.08", "21.08", "24.08",
        "25.08", "26.08", "27.08", "28.08", "31.08"]
VERLUSTE = (391, 433, 498, 533, 1222, 1315, 1812)
HOLD = 6


def tag(b: int) -> str:
    i = b // 92
    return f"{TAGE[i]}({b - i * 92:02d})" if 0 <= i < len(TAGE) else "?"


def lebt(e: object, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]  # type: ignore[attr-defined]
    return bool(bars) and max(bars) >= k - LIVE


def basis(e: object, k: int) -> float:
    return float(e.basis_bei(k))  # type: ignore[attr-defined]


def ecken(k: int, pool: List[object]) -> Tuple[Optional[float], Optional[float]]:
    ob = [basis(e, k) for e in pool if int(e.geburts_bar) <= k and lebt(e, k) and e.seite == "OBEN"]  # type: ignore[attr-defined]
    un = [basis(e, k) for e in pool if int(e.geburts_bar) <= k and lebt(e, k) and e.seite == "UNTEN"]  # type: ignore[attr-defined]
    return (max(ob) if ob else None, min(un) if un else None)


def vorher_kissen(k: int, richtung: str, extrem: float, band: float = 0.30) -> List[str]:
    out = []
    for e in ALLE:
        if int(e.geburts_bar) > k - 2 or not lebt(e, k):  # type: ignore[attr-defined]
            continue
        b = basis(e, k)
        if richtung == "AB" and e.seite == "UNTEN" and b <= extrem * (1 + band / 100):
            out.append(f"K{int(e.kid)}@{b:.4f}")
        if richtung == "AUF" and e.seite == "OBEN" and b >= extrem * (1 - band / 100):
            out.append(f"K{int(e.kid)}@{b:.4f}")
    return out


def selbst_kissen(k: int, richtung: str, extrem: float) -> List[str]:
    out = []
    for e in ALLE:
        gb = int(e.geburts_bar)  # type: ignore[attr-defined]
        if gb < k - 1 or gb > k:
            continue
        b = basis(e, k)
        if richtung == "AB" and e.seite == "UNTEN" and b <= extrem * 1.003:
            out.append(f"K{int(e.kid)}@{b:.4f}(geb{gb})")
        if richtung == "AUF" and e.seite == "OBEN" and b >= extrem * 0.997:
            out.append(f"K{int(e.kid)}@{b:.4f}(geb{gb})")
    return out


# ---- Ereignisse: A oder C feuert (2-Body-Aussenbewegung) ------------------
print("=" * 142)
print("EREIGNISSE (Regel A oder C) mit VORHER-Kissen, Selbst-Kissen und Halte-Test")
print(f"Korridor = {len(E)} edges + {len(S)} seeds (lebend, geburt<=k). HOLD={HOLD} Bars.")
print("=" * 142)
print(f"{'Bar':>5} {'Tag':<11} {'Ri':<3} {'Size%':>7} {'A':>1} {'C':>1} | "
      f"{'VorKiss':>7} {'Selbst':>6} {'halte6':>6} | Bewertung")
prev: Optional[Tuple[str, int]] = None
for k in range(3, n):
    for richtung in ("AUF", "AB"):
        o, u = ecken(k - 1, ALLE)
        ref = o if richtung == "AUF" else u
        if ref is None:
            continue
        ext = hi[k] if richtung == "AUF" else lo[k]
        if (richtung == "AUF" and ext <= ref) or (richtung == "AB" and ext >= ref):
            continue
        size = abs(ext - ref) / ref * 100.0
        if richtung == "AUF":
            a = size >= 0.60 and lo[k - 1] > ref and lo[k] > ref
            c = min(op[k - 1], cl[k - 1]) > ref and min(op[k], cl[k]) > ref
        else:
            a = size >= 0.60 and hi[k - 1] < ref and hi[k] < ref
            c = max(op[k - 1], cl[k - 1]) < ref and max(op[k], cl[k]) < ref
        if not (a or c):
            continue
        vk = vorher_kissen(k, richtung, ext)
        sk = selbst_kissen(k, richtung, ext)
        # Halte-Test: kehrt Close in den ALTEN Korridor zurueck?
        zurueck = None
        for j in range(k, min(k + HOLD + 1, n)):
            if richtung == "AB" and cl[j] > ref:
                zurueck = j
                break
            if richtung == "AUF" and cl[j] < ref:
                zurueck = j
                break
        halte = "JA" if zurueck is None else "NEIN"
        bew = "ERWEITERUNG" if zurueck is not None else "VERLASSEN"
        if not vk and zurueck is None:
            bew = "VERLASSEN/VAKUUM"
        mk = "  <== VERLUST-BAR" if k in VERLUSTE else ""
        print(f"{k:>5} {tag(k):<11} {richtung:<3} {size:>+7.3f} "
              f"{'A' if a else '-'} {'C' if c else '-'} | {len(vk):>7} {len(sk):>6} "
              f"{halte:>6} | {bew}  vk=[{','.join(vk)}]{mk}")

print("\n" + "=" * 142)
print("SPEZIAL: die vom Anwender genannten Faelle")
print("=" * 142)
for k, ri, lvl in ((840, "AB", None), (858, "AB", None), (1108, "AB", None), (1117, "AB", None)):
    pass
print(" 14.08. down-Moves 839/840/846/858: Vorher-Kissen je Bar")
for k in (839, 840, 846, 858, 892, 893):
    ext = lo[k] if k in (839, 840, 846, 858) else hi[k]
    ri = "AB" if k in (839, 840, 846, 858) else "AUF"
    print(f"   Bar {k:>4} {tag(k):<11} {ri} ext={ext:.4f} vorher={vorher_kissen(k, ri, ext)} "
          f"selbst={selbst_kissen(k, ri, ext)}")
print(" 19.08. down-Moves 1108/1109/1110/1117/1133:")
for k in (1108, 1109, 1110, 1116, 1117, 1133):
    ext = lo[k]
    print(f"   Bar {k:>4} {tag(k):<11} AB ext={ext:.4f} vorher={vorher_kissen(k, 'AB', ext)} "
          f"selbst={selbst_kissen(k, 'AB', ext)}")
