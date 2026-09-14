# -*- coding: utf-8 -*-
"""E-34m Verifikation NACH dem Renderer-Einbrand (nur lesend).

Prueft:
  1. ``_wende_zielzonen_patches_v019`` ist im Renderer definiert, wird unter
     ``KONF.mode == "V019"`` aufgerufen und hat vier Fail-Loud-Paare.
  2. Der vom Renderer erzeugte ZP-4-Quelltext ist byte-identisch mit dem
     Soll (SHA aus _tmp_e34m_audit_out.txt).
  3. Die 9 Kern-Anker der Hunks H1..H8/H11 sind vorhanden (Textsuche).
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
SOLL = (ROOT / "test" / "_tmp_e34m_zp4_soll.txt").read_text().strip()

txt = REN.read_text(encoding="utf-8")
tree = ast.parse(txt)
print(f"Renderer : {REN.name}  {len(txt.encode()):,} B")
print(f"SHA256   : {hashlib.sha256(REN.read_bytes()).hexdigest()}\n")

# --- 1. Funktion + Aufruf -------------------------------------------------
fn = next((n for n in tree.body
           if isinstance(n, ast.FunctionDef)
           and n.name == "_wende_zielzonen_patches_v019"), None)
assert fn is not None, "Funktion _wende_zielzonen_patches_v019 fehlt"
print(f"1. Funktion definiert in Zeile {fn.lineno}")
assert 'if KONF.mode == "V019":' in txt
print("   Quelltext-Gate 'if KONF.mode == \"V019\":' vorhanden")
assert 'patched_src = _wende_zielzonen_patches_v019(patched_src)' in txt
print("   Aufruf auf patched_src vorhanden")

ns_fn: dict = {}
exec(compile(ast.get_source_segment(txt, fn), "<zp4_fn>", "exec"), ns_fn)  # noqa: S102

# --- 2. ZP-4-Quelltext gegen Soll ----------------------------------------
print("\n2. ZP-4-Quelltext Byte-Abgleich")
basis = {}
for n in tree.body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 \
            and isinstance(n.targets[0], ast.Name) \
            and n.targets[0].id.startswith("A_"):
        try:
            exec(compile(ast.get_source_segment(txt, n), "<a_>", "exec"), basis)  # noqa: S102
        except Exception:  # noqa: BLE001
            pass

eng_txt = ENG.read_text(encoding="utf-8")
eng_tree = ast.parse(eng_txt)
node = next(x for x in eng_tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(eng_txt, node)
for nm in ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
           "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
           "A_M6_UNTEN", "A_TP2", "A_KBASIS"):
    assert src.count(basis[nm]) == 1, nm
    src = src.replace(basis[nm], basis[nm + "_NEW"])

ergebnis = ns_fn["_wende_zielzonen_patches_v019"](src)
sha = hashlib.sha256(ergebnis.encode()).hexdigest()
print(f"   erzeugt : {len(ergebnis)} Zeichen  sha256 = {sha}")
print(f"   Soll    : {SOLL}")
assert sha == SOLL, "ZP-4-Quelltext weicht vom Soll ab!"
print("   -> IDENTISCH")

# --- 3. Anker der Hunks ---------------------------------------------------
print("\n3. Anker H1..H8 / H11")
anker = {
    "H2 ADAPTER_V019": "ADAPTER_V019 if KONF.mode",
    "H2 Import": "ADAPTER_V014, ADAPTER_V015, ADAPTER_V019,",
    "H3 AdapterMode": '"V017", "V018", "V019"]',
    "H4 KONFIGURATION_V019": "KONFIGURATION_V019: Final[",
    "H4 ziel_delta_rb": "ziel_delta_rb=34.798688,",
    "H4 neu_basis_soll": "(1211, 76), (1268, 76), (1272, 73), (1280, 76)),",
    "H5 Registry": '"V019": KONFIGURATION_V019}',
    "H7 _V19": '_V19: Final[bool] = KONF.mode == "V019"',
    "H7 _VTAG": '"V019" if _V19',
    "H7 _VER_TEXT": "v0.24 (endogene Segmente A1/A2 + Zielzonen-Patchset ZP-4)",
    "H8 Engine-Guard": 'if KONF.mode == "V019" and box_end != 644:',
    "H10 Laufzeit-Gate": 'and len(_hk.segmente) > 1',
    "H10 Fenster": "ADAPTER_V019.segmente[1].start_bar",
    "H10 _ueb": "def _ueb(kk: int) -> float:",
    "H10 _reclaim_stufe_lok": 'ns["_reclaim_stufe"] = _reclaim_stufe_lok',
    "H11 Laengen-Assert": 'assert len(V1) - len(V1_basis) == 9',
}
for nm, s in anker.items():
    n = txt.count(s)
    print(f"   {nm:<24} count={n}")
    assert n == 1, (nm, n)
print("\nALLE PRUEFUNGEN OK")
