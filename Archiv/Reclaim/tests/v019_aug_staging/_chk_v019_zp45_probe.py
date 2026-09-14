# -*- coding: utf-8 -*-
"""READ-ONLY Probe (V019-Audit): ist der ZP-4-Anteil im Patchset unveraendert?

E-34m/X3 hat belegt: der Renderer erzeugte genau den ZP-4-Quelltext
(21.956 Zeichen, SHA256 ``8a3b7070...``).  Seit E-34n/10 sitzt ZP-5
(Kantenlaeufer-Durchstich) in DERSELBEN Funktion - das alte Soll muss also
nicht mehr passen.  Hier wird geprueft, ob das Paar (5) die einzige
Abweichung ist: Ruecknahme genau des fuenften Paares muss wieder das
ZP-4-Soll ergeben.
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path
from typing import Dict, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
SOLL = (ROOT / "test" / "_tmp_e34m_zp4_soll.txt").read_text().strip()

txt = REN.read_text(encoding="utf-8")
tree = ast.parse(txt)

basis: Dict[str, str] = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id.startswith("A_"):
        try:
            exec(compile(ast.get_source_segment(txt, _n), "<a_>", "exec"), basis)  # noqa: S102
        except Exception:  # noqa: BLE001
            pass

_fn = next(x for x in tree.body
           if isinstance(x, ast.FunctionDef)
           and x.name == "_wende_zielzonen_patches_v019")

# Paarliste (Name, alt, neu) direkt aus der Funktion lesen -- kein Hardcoding.
_paare: Tuple = ()
for _node in ast.walk(_fn):
    if isinstance(_node, ast.Assign) and isinstance(_node.targets[0], ast.Name) \
            and _node.targets[0].id == "paare":
        _paare = ast.literal_eval(_node.value)
assert len(_paare) == 5, len(_paare)
print(f"Paare in _wende_zielzonen_patches_v019: {len(_paare)} "
      f"-> {[p[0] for p in _paare]}")

ns_fn: Dict[str, object] = {}
exec(compile(ast.get_source_segment(txt, _fn), "<zp>", "exec"), ns_fn)  # noqa: S102

eng_txt = ENG.read_text(encoding="utf-8")
src = ast.get_source_segment(
    eng_txt, next(x for x in ast.parse(eng_txt).body
                  if isinstance(x, ast.FunctionDef) and x.name == "_se_trades"))
assert src is not None
_KETTE = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
for _nm in _KETTE:
    assert src.count(basis[_nm]) == 1, (_nm, src.count(basis[_nm]))
    src = src.replace(basis[_nm], basis[_nm + "_NEW"])

voll = ns_fn["_wende_zielzonen_patches_v019"](src)   # type: ignore[operator]
print(f"ZP-4+ZP-5: {len(voll)} Zeichen  sha256 = "
      f"{hashlib.sha256(voll.encode()).hexdigest()}")

_nm5, _alt5, _neu5 = _paare[4]
assert _nm5 == "A_KL_DOCHT", _nm5
assert voll.count(_neu5) == 1, voll.count(_neu5)
zurueck = voll.replace(_neu5, _alt5, 1)
sha4 = hashlib.sha256(zurueck.encode()).hexdigest()
print(f"ohne Paar (5): {len(zurueck)} Zeichen  sha256 = {sha4}")
print(f"ZP-4-Soll    : 21.956 Zeichen       sha256 = {SOLL}")
assert sha4 == SOLL, "ZP-4-Anteil weicht ab!"
print("-> ZP-4 ist BYTE-IDENTISCH geblieben; ZP-5 ist die einzige Zutat.")
print(f"   Zuwachs: {len(voll) - len(zurueck)} Zeichen "
      f"(= {_nm5}-Block)")
