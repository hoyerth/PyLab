# -*- coding: utf-8 -*-
"""Post-Commit-Nachkontrolle H20.53.

Verankert NICHT auf den Arbeitsbaum, sondern auf die GIT-OBJEKTE des neuen
Commits 58fb44b sowie dessen Elterncommits 6923b40.

Geprueft wird:
  (A) Der neue HEAD-Blob (LF) entspricht -- auf Arbeitsbaum-Konvention
      gebracht -- VOLLSTAENDIG der Arbeitsdatei (nicht nur als Praefix).
  (B) Der Eltern-Blob (a0f9ec09...) ist BYTE-IDENTISCHES PRAEFIX der
      Arbeitsdatei (= Zustand vor dem Append).
  (C) Arbeitsdatei-SHA256 == d0e7ad8407f0a1cb..., Laenge == 803493.
  (D) Reiner Anhang: 387 Zeilen, ausschliesslich INSERT am Dateiende,
      CRLF-exklusiv.
  (E) Commit-Metadaten: 1 Datei geaendert, 387 Insertions, 0 Deletions.
"""
from __future__ import annotations

import difflib
import hashlib
import subprocess
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
REL = "test/SESSION_HANDOFF.md"

NEW_COMMIT = "58fb44b"
PARENT_COMMIT = "6923b40"

SOLL_SHA = "d0e7ad8407f0a1cba7f539a1c25f059378a2d9de214244d8c9183984126fd1ab"
SOLL_BYTES = 803493
SOLL_ALT_BYTES = 783840
SOLL_ZEILEN_ALT = 13726
SOLL_ZEILEN_NEU = 14113
SOLL_CRLF = 13726 + 387


def blob_bytes(rev: str) -> bytes:
    ref = f"{rev}:{REL}"
    oid = subprocess.run(["git", "rev-parse", ref],
                         capture_output=True, check=True).stdout.decode().strip()
    data = subprocess.run(["git", "cat-file", "blob", oid],
                          capture_output=True, check=True).stdout
    return oid, data


neu_oid, NEU_BLOB = blob_bytes(NEW_COMMIT)
alt_oid, ALT_BLOB = blob_bytes(PARENT_COMMIT)
NEU = HANDOFF.read_bytes()

print(f"Commit NEU    : {NEW_COMMIT}  Blob {neu_oid}")
print(f"Commit ALT    : {PARENT_COMMIT}  Blob {alt_oid}")
print()

# --- (C) Arbeitsdatei-Arrest --------------------------------------------
sha = hashlib.sha256(NEU).hexdigest()
print(f"Arbeitsdatei  : {len(NEU)} B  SHA256 {sha}")
assert sha == SOLL_SHA, f"Arbeitsdatei-SHA abweichend: {sha}"
assert len(NEU) == SOLL_BYTES, f"Arbeitsdatei-Laenge abweichend: {len(NEU)}"
print("(C) Arbeitsdatei-Arrest (SHA256 + Laenge): OK")

# --- Blob-Rekonstruktion ------------------------------------------------
assert b"\r" not in NEU_BLOB and b"\r" not in ALT_BLOB, "Blob enthaelt CR"
NEU_ALT = NEU_BLOB.replace(b"\n", b"\r\n")
ALT_ALT = ALT_BLOB.replace(b"\n", b"\r\n")
print(f"HEAD-Blob     : {len(NEU_BLOB)} B (LF) -> {len(NEU_ALT)} B (CRLF)")
print(f"Eltern-Blob   : {len(ALT_BLOB)} B (LF) -> {len(ALT_ALT)} B (CRLF)")
assert len(ALT_ALT) == SOLL_ALT_BYTES, f"Eltern-CRLF-Laenge: {len(ALT_ALT)}"
assert len(NEU_ALT) == SOLL_BYTES, f"HEAD-CRLF-Laenge: {len(NEU_ALT)}"

# --- (A) Vollstaendige Identitaet ---------------------------------------
assert NEU == NEU_ALT, "HEAD-Blob != Arbeitsdatei (nicht nur Praefix!)"
print("(A) Vollstaendige Blob<->Arbeitsdatei-Identitaet: OK")

# --- (B) Praefix-Identitaet gegen Eltern-Objekt --------------------------
assert NEU[: len(ALT_ALT)] == ALT_ALT, "Eltern-Blob ist KEIN Praefix"
print("(B) Praefix-Byte-Identitaet zum Eltern-Blob: OK")

# --- (D) Reiner Anhang --------------------------------------------------
diff = NEU[len(ALT_ALT):]
crlf = diff.count(b"\r\n")
lf = diff.count(b"\n")
print(f"Append        : {len(diff)} B  CRLF {crlf}  nackte LF {lf - crlf}")
assert lf == crlf, "Append nicht CRLF-exklusiv"
assert NEU.count(b"\n") == NEU.count(b"\r\n"), "Arbeitsdatei nicht CRLF-exklusiv"
assert NEU.count(b"\n") == SOLL_CRLF, f"CRLF-Zahl: {NEU.count(b'\n')}"

alt_l = ALT_ALT.decode("utf-8").splitlines()
neu_l = NEU.decode("utf-8").splitlines()
assert len(alt_l) == SOLL_ZEILEN_ALT, f"Alt-Zeilen: {len(alt_l)}"
assert len(neu_l) == SOLL_ZEILEN_NEU, f"Neu-Zeilen: {len(neu_l)}"
print(f"Zeilen        : {len(alt_l)} -> {len(neu_l)} (+{len(neu_l) - len(alt_l)})")

sm = difflib.SequenceMatcher(a=alt_l, b=neu_l, autojunk=False)
nicht_append = [op for op in sm.get_opcodes()
                if op[0] not in ("equal", "insert")
                or (op[0] == "insert" and op[1] != len(alt_l))]
assert not nicht_append, f"NICHT-APPEND-Operationen: {nicht_append}"
print("(D) Diff ausschliesslich INSERT am Dateiende -- reiner Anhang: OK")

# --- (E) Commit-Metadaten ----------------------------------------------
numstat = subprocess.run(
    ["git", "show", "--numstat", "--format=%H", "-1", NEW_COMMIT],
    capture_output=True, check=True).stdout.decode().strip().splitlines()
print("git show --numstat:")
for z in numstat:
    print("   " + z)
felder = [z for z in numstat if "\t" in z]
assert len(felder) == 1, f"mehr als eine Datei im Commit: {felder}"
ins, del_, pfad = felder[0].split("\t")
assert (ins, del_) == ("387", "0"), f"Numstat: {ins}/{del_}"
assert pfad == REL, f"Pfad: {pfad}"
print("(E) Commit-Metadaten (1 Datei, 387/0, richtiger Pfad): OK")

print()
print("ALLE POST-COMMIT-NACHKONTROLLEN OK")
