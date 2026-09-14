# -*- coding: utf-8 -*-
"""Byte-treuer Append H20.52 an test/SESSION_HANDOFF.md (CRLF-exklusiv).

Read-only gegenueber Engine/Adapter/Renderer; schreibt NUR den Handoff.
Prueft die Praefix-Byte-Identitaet gegen den arretierten Kopfanker
(Zustand nach dem H20.51-Append, Commit 32bd1cd).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
APPEND = Path("test/_tmp_h20_52_append.txt")

SOLL_BYTES = 744422
SOLL_SHA = "cb704062d17ed64e1f04df986b7ff47c823a45034d215632baa20c3262ee9ef5"

vor = HANDOFF.read_bytes()
assert len(vor) == SOLL_BYTES, f"Handoff-Bytes: {len(vor)} != {SOLL_BYTES}"
assert hashlib.sha256(vor).hexdigest() == SOLL_SHA, "Handoff-SHA veraendert"
assert vor.count(b"\n") == vor.count(b"\r\n"), "Handoff enthaelt nackte LF"

txt = APPEND.read_text(encoding="utf-8")
txt = re.sub(r"\r\n|\r|\n", "\r\n", txt)
if not txt.endswith("\r\n"):
    txt += "\r\n"
neu_bytes = txt.encode("utf-8")

nach = vor + neu_bytes
HANDOFF.write_bytes(nach)

# ---------------------------------------------------------------- Kontrollen
kopf = HANDOFF.read_bytes()[: len(vor)]
assert kopf == vor, "Praefix-Byte-Identitaet verletzt"
assert nach.count(b"\n") == nach.count(b"\r\n"), "CRLF-Exklusivitaet verletzt"
assert nach.count(b"\r\n") == vor.count(b"\r\n") + txt.count("\r\n")

print(f"Vorher : {len(vor):>7} B  {SOLL_SHA[:24]}...  "
      f"{vor.count(bytes([13, 10]))} CRLF")
print(f"Append : {len(neu_bytes):>7} B  {txt.count(chr(13) + chr(10))} CRLF")
print(f"Nachher: {len(nach):>7} B  {hashlib.sha256(nach).hexdigest()}")
print(f"         {nach.count(bytes([13, 10]))} CRLF  "
      f"(LF gesamt {nach.count(bytes([10]))})")
print("ALLE PRUEFUNGEN OK")
