# -*- coding: utf-8 -*-
"""Byte-treuer Handoff-Append H20.8-H20.12 (Schritt 1, notariell).

Konvention (H20.x): CRLF ausschliesslich, byte-level Schreibvorgang,
``count("\\n") == count("\\r\\n")`` als Pflicht-Assert.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HANDOFF = Path("test/SESSION_HANDOFF.md")
FRAGMENT = Path("test/_tmp_h20_s3_append.txt")
SHA_VOR = "bf71ec5fa26d212aa3bc5e93c9d88e3dc282293c173d42f10180bf8f0e1be4e0"

vor = HANDOFF.read_bytes()
sha_vor = hashlib.sha256(vor).hexdigest()
print(f"VOR   {len(vor):>7} B  SHA256 {sha_vor}")
assert sha_vor == SHA_VOR, "Handoff-SHA weicht vom notariellen Anker ab!"

roh = FRAGMENT.read_text(encoding="utf-8")
frag = roh.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
print(f"FRAG  {len(frag):>7} B  (CRLF normalisiert, "
      f"Zeilen {frag.count(b'\r\n')})")
assert frag.count(b"\n") == frag.count(b"\r\n"), "Fragment enthaelt nackte LF!"

neu = vor + frag
HANDOFF.write_bytes(neu)

# ---- Nachkontrolle (byte-level) -------------------------------------------
ist = HANDOFF.read_bytes()
sha_ist = hashlib.sha256(ist).hexdigest()
print(f"NACH  {len(ist):>7} B  SHA256 {sha_ist}")
assert ist[:len(vor)] == vor, "Praefix wurde veraendert!"
assert ist[len(vor):] == frag, "Anhang weicht vom Fragment ab!"
assert ist.count(b"\n") == ist.count(b"\r\n"), "nackte LF im Ergebnis!"
assert ist.count(b"\r\n") == vor.count(b"\r\n") + frag.count(b"\r\n")
assert ist.endswith(b"\r\n")
print(f"DELTA +{len(ist) - len(vor)} B / "
      f"+{ist.count(b'\r\n') - vor.count(b'\r\n')} Zeilen CRLF")
print("OK  byte-treu angehaengt, Praefix unberuehrt, keine nackte LF.")
