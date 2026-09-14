# -*- coding: utf-8 -*-
"""Byte-treuer Handoff-Append H20.13/H20.14 (Schritt 2, notariell)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HANDOFF = Path("test/SESSION_HANDOFF.md")
FRAGMENT = Path("test/_tmp_h20_13_append.txt")
SHA_VOR = "da0255a2eec8fbe4256f0401c605152043a9811c69904dba839c8b86bc8fd64f"

vor = HANDOFF.read_bytes()
sha_vor = hashlib.sha256(vor).hexdigest()
print(f"VOR   {len(vor):>7} B  SHA256 {sha_vor}")
assert sha_vor == SHA_VOR, "Handoff-SHA weicht vom Anker nach H20.8-H20.12 ab!"

roh = FRAGMENT.read_text(encoding="utf-8")
frag = roh.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
print(f"FRAG  {len(frag):>7} B  Zeilen {frag.count(b'\r\n')}")
assert frag.count(b"\n") == frag.count(b"\r\n"), "Fragment enthaelt nackte LF!"

neu = vor + frag
HANDOFF.write_bytes(neu)

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
print("OK  byte-treu angehaengt (H20.13/H20.14).")
