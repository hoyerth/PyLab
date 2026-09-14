# -*- coding: utf-8 -*-
"""Gegenprobe E-34n/15: der angehaengte Abschnitt == ABSCHNITT des Skripts.

Vergleicht binaer (CRLF-Normalisierung des Skript-Literals) und prueft:
* Zeilen/CRLF-Zaehlung,
* ASCII-Reinheit des Anhangs,
* Vorhandensein der fuenf Fragen (D8) und der Artefakt-Anker (D9),
* dass die drei arretierten Dateien unveraendert sind.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OFFSET = 352405

spec = importlib.util.spec_from_file_location(
    "_ap", ROOT / "test" / "_tmp_e34n15_append.py")
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)                       # main() wird nicht gerufen

handoff = (ROOT / "test" / "SESSION_HANDOFF.md").read_bytes()
kopf, anhang = handoff[:OFFSET], handoff[OFFSET:]
soll = ap.ABSCHNITT.replace("\n", "\r\n").encode("utf-8")
print("Anhang  :", len(anhang), "B   entspricht ABSCHNITT:",
      anhang == soll)
assert anhang == soll, "Anhang weicht vom Skript-Abschnitt ab"
print("Handoff :", len(handoff), "B  CRLF", handoff.count(b"\r\n"),
      " LF", handoff.count(b"\n"))
assert handoff.count(b"\r\n") == handoff.count(b"\n")
print("SHA256  :", hashlib.sha256(handoff).hexdigest())
print("ASCII   :", not any(ord(c) > 127 for c in
                           anhang.decode("utf-8")), "(Anhang)")
_text = anhang.decode("utf-8")
for _marke in ("### D8 - ENTSCHEIDUNGSFRAGEN FUER MORGEN",
               "**(1) Kausalitaets-Arretierung.**",
               "**(5) Wiedervorlage aus E-34n/14.**",
               "D9 - Artefakt-Anker E-34n/15",
               "_chk_v019_kausal_vergleich.py",
               "b417d4493a1b422b7d5da0079235046b84cc199d2eccb9a3d2d7215ab48bae6c"):
    assert _marke in _text, _marke
print("Marken D8/D9: OK (6/6)")

ANKER = {"test/tmp_kanten_engine_replay.py":
         "4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a",
         "backtest_lab/phasen_regime_adapter.py":
         "4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83",
         "test/tmp_png_aug_sichttest.py":
         "7dab7a300e69c4ffae230b1cb547da508dae8a3801cb6a2fed2f63c5bc6d7a28"}
for _p, _soll in ANKER.items():
    _ist = hashlib.sha256((ROOT / _p).read_bytes()).hexdigest()
    print(f"  {_p:<40} {'OK ' if _ist == _soll else 'ABW'} {_ist[:24]}...")
    assert _ist == _soll, _p
print("ALLE PRUEFUNGEN OK")
