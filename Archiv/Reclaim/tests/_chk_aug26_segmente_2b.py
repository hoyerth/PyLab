# -*- coding: utf-8 -*-
"""Phase 2b: Repraesentativitaet der gefundenen Segmente + Archiv-Integritaet."""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("engine", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]
engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
ts = list(d["ts"])
katalog = {int(e.kid): e for e in list(scan["edges"]) + list(scan["seeds"])}

print("=" * 96)
print("PHASE 2b -- REPRAESENTATIVITAET DER SEGMENTGRENZEN (AUG26)")
print("=" * 96)
SEGS = [(14, 1396, 1, 3), (1397, 1633, 117, 127), (1634, 1931, 123, 132)]
print(f"   {'#':<3}{'Fenster':<16}{'Decke (fix)':<20}{'Boden (fix)':<20}"
      f"{'IST-Spanne im Fenster':<26}{'Decke/Boden daneben?'}")
for i, (a, b, ko, ku) in enumerate(SEGS, 1):
    vo = float(katalog[ko].basis_bei(a))
    vu = float(katalog[ku].basis_bei(a))
    ist_lo, ist_hi = float(lo[a:b + 1].min()), float(hi[a:b + 1].max())
    d_hi = (vo - ist_hi) / ist_hi * 100.0
    d_lo = (vu - ist_lo) / ist_lo * 100.0
    print(f"   {i:<3}{f'{a}..{b}':<16}{f'K{ko} {vo:.4f}':<20}"
          f"{f'K{ku} {vu:.4f}':<20}"
          f"{f'{ist_lo:.4f}..{ist_hi:.4f}':<26}"
          f"Decke {d_hi:+.2f}% / Boden {d_lo:+.2f}%")
print("\n   (Decke < 0 => Deckenniveau LIEGT UNTER dem Fenster-Hoch;")
print("    Boden > 0 => Bodenniveau LIEGT UEBER dem Fenster-Tief)")

# Wie viele Bars liegen ausserhalb [boden, decke]?
print("\n   Bars ausserhalb des jeweiligen [Boden, Decke]-Korridors:")
for i, (a, b, ko, ku) in enumerate(SEGS, 1):
    vo = float(katalog[ko].basis_bei(a))
    vu = float(katalog[ku].basis_bei(a))
    aus = int(((hi[a:b + 1] > vo) | (lo[a:b + 1] < vu)).sum())
    print(f"      Segment {i}: {aus:>4} von {b - a + 1:>4} Bars "
          f"({100.0 * aus / (b - a + 1):.1f} %)")

# ---------------------------------------------------------- Archiv-Integritaet
print("\n" + "=" * 96)
print("ARCHIV-INTEGRITAET (Originale unveraendert?)")
print("=" * 96)
man = ROOT / "test" / "archiv" / "v019_aug_staging" / "MANIFEST.sha256"
zeilen = [z for z in man.read_text(encoding="utf-8").splitlines() if z.strip()]
schlecht = 0
for z in zeilen:
    sha_soll, size_soll, rel = re.match(
        r"^([0-9a-f]{64})\s+(\d+)\s+(.+)$", z).groups()  # type: ignore[union-attr]
    b = (ROOT / rel).read_bytes()
    if hashlib.sha256(b).hexdigest() != sha_soll or len(b) != int(size_soll):
        print(f"   ABWEICHUNG {rel}")
        schlecht += 1
print(f"   {len(zeilen)} Originale geprueft | Abweichungen: {schlecht}")
print(f"   MANIFEST-SHA256: {hashlib.sha256(man.read_bytes()).hexdigest()}")
print("\nENDE PHASE 2b")
