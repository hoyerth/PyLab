# -*- coding: utf-8 -*-
"""Korrektur am E-34n/15-Append: Umlaut im Abschnittsfeld beseitigen.

Der Abschnitt ist per Konvention ASCII-only; ``Klärung`` ist als einziger
Nicht-ASCII-Rest durchgegangen. Byte-genaue Ersetzung im bereits
angehaengten Handoff + Gegenprobe.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
VORHER_SHA = "e8cf618ca92cf7a8ec542804d37733aad1a1e87b03fe385a218d57784807b544"

vorher = HANDOFF.read_bytes()
assert hashlib.sha256(vorher).hexdigest() == VORHER_SHA, "Vorbedingung"
kopf = vorher[:352405]
anhang = vorher[352405:]
alt = "Kl\u00e4rung".encode("utf-8")
assert anhang.count(alt) == 1, anhang.count(alt)
neu = kopf + anhang.replace(alt, b"Klaerung", 1)
HANDOFF.write_bytes(neu)
nachher = HANDOFF.read_bytes()
print("OK  bytes", len(nachher))
print("neuer SHA256", hashlib.sha256(nachher).hexdigest())
print("nicht-ASCII im Anhang",
      sorted({c for c in nachher.decode("utf-8")[352405:] if ord(c) > 127}))
