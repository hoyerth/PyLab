# -*- coding: utf-8 -*-
"""Korrektur 2 am E-34n/15-Append: letzten Umlaut im Anhang beseitigen.

Der Abschnitt ist per Konvention ASCII-only. Nach der ersten Korrektur
(Klaerung) verblieb ``Nachträge``. Byte-genaue Ersetzung nur im Anhang.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
VORHER_SHA = "4ca34421e2692863817481015dc594f0edc715843b09137a4831c30478607a9d"
OFFSET = 352405                    # Beginn des E-34n/15-Abschnitts

vorher = HANDOFF.read_bytes()
assert hashlib.sha256(vorher).hexdigest() == VORHER_SHA, "Vorbedingung"
kopf, anhang = vorher[:OFFSET], vorher[OFFSET:]
alt = "Nachtr\u00e4ge".encode("utf-8")
assert anhang.count(alt) == 1, anhang.count(alt)
neu = kopf + anhang.replace(alt, b"Nachtraege", 1)
HANDOFF.write_bytes(neu)
nachher = HANDOFF.read_bytes()
print("OK  bytes", len(nachher))
print("neuer SHA256", hashlib.sha256(nachher).hexdigest())
print("nicht-ASCII im Anhang",
      [hex(ord(c)) for c in sorted({c for c in nachher.decode("utf-8")[OFFSET:]
                                    if ord(c) > 127})])
