# -*- coding: utf-8 -*-
"""S3.3 Fix -- fehlende schliessende Klammer der KONFIGURATION_V018 nachtragen.

Ursache: der replace_all-Schritt im Renderer-Patch hatte in der NEU-Fassung
(Literale im Patch-Skript) die Zeile ')' mitentfernt. Diese Datei stellt den
Soll-Zustand byte-exakt wieder her und verifiziert Eindeutigkeit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent / "tmp_png_aug_sichttest.py"

old = ('    niveauwechsel_baseline=205,\n\n\n_KONFIGURATIONEN = '
       '{"V01": KONFIGURATION_V01,')
new = ('    niveauwechsel_baseline=205,\n)\n\n_KONFIGURATIONEN = '
       '{"V01": KONFIGURATION_V01,')

raw = P.read_bytes()
assert raw.count(b"\r\n") == 0, "kein LF-File"
t = raw.decode("utf-8")
n = t.count(old)
assert n == 1, f"{n} Treffer"
P.write_bytes(t.replace(old, new).encode("utf-8"))
assert P.read_bytes().count(b"\r\n") == 0
print("Fix OK -- Klammer restauriert.")
