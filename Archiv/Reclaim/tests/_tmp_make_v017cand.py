# -*- coding: utf-8 -*-
"""Erzeugt die Wegwerf-Engine fuer den V017-Probe-Lauf (§72.1).

Quelle: die arretierte Engine ``test/tmp_kanten_engine_replay.py``.
Aenderung: ``_SEEdgeH.basis_bei`` -> kausales Extremum der bestaetigten
Dochte + M6-Heilung (Rueckfall auf den ersten bekannten Docht).
Die arretierte Datei selbst wird NICHT angefasst.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
C = ROOT / "test" / "_tmp_engine_v017cand.py"

B = (
    "        if self.ist_prim_anker:\n"
    "            return self.basis\n"
    "        px = [p for b, p in self.wicks if b + 2 <= k]\n"
    "        return float(np.mean(px)) if px else self.basis"
)
V = (
    "        if self.ist_prim_anker:\n"
    "            return self.basis\n"
    "        px = [p for b, p in self.wicks if b + 2 <= k]\n"
    "        if px:\n"
    "            return float(min(px) if self.seite == \"OBEN\" else max(px))\n"
    "        return float(self.wicks[0][1])"
)

# Zeilenenden der Quelle erhalten (CRLF) -- sonst waere der Ein-Zeilen-Diff
# gegen die arretierte Engine nicht mehr als solcher nachvollziehbar.
src = P.open(encoding="utf-8", newline="").read()
_nl = "\r\n" if "\r\n" in src else "\n"
B = B.replace("\n", _nl)
V = V.replace("\n", _nl)
assert src.count(B) == 1, src.count(B)
neu = src.replace(B, V)
assert "np.mean(px)" not in neu
with C.open("w", encoding="utf-8", newline="") as fh:
    fh.write(neu)
print(f"Zeilenende der Quelle: {'CRLF' if _nl == chr(13) + chr(10) else 'LF'}")

print(f"Quelle (arretiert) : {hashlib.sha256(P.read_bytes()).hexdigest()}"
      f"  {P.stat().st_size:,} B")
print(f"Kandidat (Wegwerf) : {hashlib.sha256(C.read_bytes()).hexdigest()}"
      f"  {C.stat().st_size:,} B")
