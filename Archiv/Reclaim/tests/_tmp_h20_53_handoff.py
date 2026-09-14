# -*- coding: utf-8 -*-
"""Byte-treuer Append H20.53 an test/SESSION_HANDOFF.md (CRLF-exklusiv).

Read-only gegenueber Motor/Adapter/Renderer; schreibt NUR den Handoff.
Prueft die Praefix-Byte-Identitaet gegen den arretierten Kopfanker
(Zustand nach dem H20.52b-Append, Commit 6923b40).

Abweichung zum H20.52b-Appender (dokumentiert, nicht still): das
Nachher-Kriterium ist hier zusaetzlich als ASSERT formuliert und der
geschriebene Inhalt wird von Platte zurueckgelesen. Der Append-Vorgang
selbst ist unveraendert.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
APPEND = Path("test/_tmp_h20_53_append.txt")

SOLL_BYTES = 783840
SOLL_SHA = "e7325e4399d52224b0598002552776b0fc0d30d2f456ec9a49c60f40bbb90df2"
SOLL_CRLF = 13726
CRLF = b"\r\n"

vor = HANDOFF.read_bytes()
assert len(vor) == SOLL_BYTES, f"Handoff-Bytes: {len(vor)} != {SOLL_BYTES}"
assert hashlib.sha256(vor).hexdigest() == SOLL_SHA, "Handoff-SHA veraendert"
assert vor.count(b"\n") == vor.count(CRLF), "Handoff enthaelt nackte LF"
assert vor.count(CRLF) == SOLL_CRLF, "Handoff-CRLF-Zahl veraendert"
assert vor.endswith(CRLF), "Handoff endet nicht auf CRLF"

txt = APPEND.read_bytes().decode("utf-8")
assert all(ord(c) < 128 for c in txt), "Append ist nicht rein ASCII"
txt = txt.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
if not txt.endswith("\r\n"):
    txt += "\r\n"
neu_bytes = txt.encode("utf-8")

nach = vor + neu_bytes
kontrolle = nach

# ---------------------------------------------------------------- Kontrollen
assert nach[: len(vor)] == vor, "Praefix-Byte-Identitaet verletzt"
assert nach.count(b"\n") == nach.count(CRLF), "CRLF-Exklusivitaet verletzt"
assert nach.count(CRLF) == vor.count(CRLF) + txt.count("\r\n"), \
    "CRLF-Zuwachs stimmt nicht"
assert len(nach) == len(vor) + len(neu_bytes), "Byte-Zuwachs inkonsistent"

HANDOFF.write_bytes(nach)

# ------------------------------------------- Nachkontrolle direkt von Platte
zurueck = HANDOFF.read_bytes()
assert zurueck == kontrolle, "Geschriebener Inhalt weicht vom berechneten ab"
assert zurueck[: len(vor)] == vor, "Praefix nach dem Schreiben verletzt"

print(f"Vorher : {len(vor):>7} B  {SOLL_SHA[:24]}...  "
      f"{vor.count(CRLF)} CRLF")
print(f"Append : {len(neu_bytes):>7} B  {txt.count(chr(13) + chr(10))} CRLF")
print(f"Nachher: {len(nach):>7} B  {hashlib.sha256(nach).hexdigest()}")
print(f"         {nach.count(CRLF)} CRLF  (LF gesamt {nach.count(bytes([10]))})")
print("ALLE PRUEFUNGEN OK")
