# -*- coding: utf-8 -*-
"""Unabhaengige Nachkontrolle des H20.53-Appends gegen das GIT-OBJEKT.

Vergleicht den HEAD-Blob (Zustand vor dem Append) byteweise mit dem Praefix
der Arbeitsdatei. Damit ist die Praefix-Identitaet nicht nur gegen eine
im Skript gespeicherte Zahl, sondern gegen die Versionskontrolle belegt.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
REL = "test/SESSION_HANDOFF.md"

HEAD_BLOB = subprocess.run(["git", "rev-parse", f"HEAD:{REL}"],
                           capture_output=True, check=True).stdout.decode().strip()
BLOB = subprocess.run(["git", "cat-file", "blob", HEAD_BLOB],
                      capture_output=True, check=True).stdout
NEU = HANDOFF.read_bytes()

# WICHTIG: ``core.autocrlf`` speichert im Repo LF und materialisiert im
# Arbeitsbaum CRLF. Der Blob ist daher LF-only; fuer den Byte-Vergleich muss
# er auf die Arbeitsbaum-Konvention gebracht werden.
assert b"\r" not in BLOB, "Blob enthaelt CR -- Normalisierung unklar"
ALT = BLOB.replace(b"\n", b"\r\n")

print(f"HEAD-Blob      : {HEAD_BLOB}")
print(f"HEAD-Blob Bytes: {len(BLOB)} (LF-only) -> "
      f"Arbeitsbaum-Konvention {len(ALT)} B (CRLF)")
print(f"Arbeitsdatei   : {len(NEU)} B  SHA256 {hashlib.sha256(NEU).hexdigest()}")

assert NEU[: len(ALT)] == ALT, "PRAEFIX NICHT BYTE-IDENTISCH ZUM HEAD-BLOB"
print("Praefix-Byte-Identitaet zum HEAD-Blob: OK")

diff = NEU[len(ALT):]
print(f"Append-Teil    : {len(diff)} B  "
      f"CRLF {diff.count(bytes([13, 10]))}  "
      f"nackte LF {diff.count(bytes([10])) - diff.count(bytes([13, 10]))}")
assert diff.count(bytes([10])) == diff.count(bytes([13, 10]))
print("CRLF-Exklusivitaet: OK")

# Reiner Anhang: keine Aenderung/keine Loeschung im Altteil
import difflib
alt_l = ALT.decode("utf-8").splitlines()
neu_l = NEU.decode("utf-8").splitlines()
sm = difflib.SequenceMatcher(a=alt_l, b=neu_l, autojunk=False)
opcodes = sm.get_opcodes()
nicht_append = [op for op in opcodes if op[0] not in ("equal", "insert")
                or (op[0] == "insert" and op[1] != len(alt_l))]
print(f"Alt-Zeilen {len(alt_l)} -> Neu-Zeilen {len(neu_l)} "
      f"(Zuwachs {len(neu_l) - len(alt_l)})")
if nicht_append:
    print("NICHT-APPEND-Operationen gefunden:", nicht_append)
    raise SystemExit(1)
print("Diff-Operationen: ausschliesslich INSERT am Dateiende -- reiner Anhang OK")

# Ueberschriften des neuen Blocks
print()
print("Neue Ueberschriften:")
for z in neu_l[len(alt_l):]:
    if z.startswith("## ") or z.startswith("### "):
        print("  " + z)
print()
print("ALLE NACHKONTROLLEN OK")
