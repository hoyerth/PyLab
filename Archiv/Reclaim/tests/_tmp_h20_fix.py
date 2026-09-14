# -*- coding: utf-8 -*-
"""Korrigiert den Byte-Zahlendreher im H20-Artefakt-Anker (200.333 -> 200.433)."""
import hashlib
import pathlib

P = pathlib.Path(__file__).resolve().parent / "SESSION_HANDOFF.md"
b = P.read_bytes()
alt, neu = b"| 200.333 |", b"| 200.433 |"
assert b.count(alt) == 1, b.count(alt)
b = b.replace(alt, neu)
assert b.count(b"\n") == b.count(b"\r\n"), "nackte LF entstanden"
P.write_bytes(b)
print(len(b), hashlib.sha256(b).hexdigest())
