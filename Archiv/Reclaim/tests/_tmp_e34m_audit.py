# -*- coding: utf-8 -*-
"""E-34m Trockenlauf: Audit der ZP-4-Anker VOR dem Renderer-Einbrand.

Quellen (nur lesend):
  * Engine ``test/tmp_kanten_engine_replay.py`` -> Quelltext von ``_se_trades``
  * Renderer ``test/tmp_png_aug_sichttest.py``  -> Basis-13-Patches (Z. 549..621)
  * Messskript ``test/_tmp_e34_auto.py``        -> ZP-4-Regeln (Z. 381..405)

Prueft:
  A) Basis-13-Anker je genau 1x.
  B) ZP-4-Anker je genau 1x im Basis-13-gepatchten Quelltext.
  C) Der ZP-4-Quelltext aus den Renderer-Regeln == der aus den e34_auto-Regeln.
  D) Der vierfach gepatchte Quelltext kompiliert.
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
AUT = ROOT / "test" / "_tmp_e34_auto.py"

BASE_NAMEN = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_OBEN",
              "A_M6_UNTEN", "A_M6_BASIS", "A_M6_BASIS_K", "A_M6_RET",
              "A_M6_SORT", "A_M6_SORT2", "A_TP2", "A_KBASIS")
ZP4_NAMEN = ("A_UEB1", "A_VC", "A_M6L", "A_SB")


def _block(pfad: Path, von: int, bis: int, ns_name: str) -> dict:
    """Fuehrt die reinen String-Zuweisungen der Zeilen ``von..bis`` aus."""
    txt = pfad.read_text(encoding="utf-8")
    block = "\n".join(txt.split("\n")[von - 1:bis])
    ns: dict = {}
    exec(compile(block, f"<{ns_name}>", "exec"), ns)  # noqa: S102
    return ns


def _se_trades_src(pfad: Path) -> str:
    txt = pfad.read_text(encoding="utf-8")
    tree = ast.parse(txt)
    node = next(x for x in tree.body
                if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
    seg = ast.get_source_segment(txt, node)
    assert seg is not None
    return seg


rb = _block(REN, 549, 621, "renderer_basis13")
ra = _block(AUT, 381, 405, "e34_auto_zp4")
src = _se_trades_src(ENG)

print(f"Engine   : {ENG.name}  SHA "
      f"{hashlib.sha256(ENG.read_bytes()).hexdigest()}")
print(f"_se_trades: {len(src)} Zeichen\n")

# --- A) Basis-13 ----------------------------------------------------------
print("A. BASIS-13-Anker (Renderer-Regeln gegen die Engine)")
basis = [("A_KANTEN", "A_KANTEN"), ("A_LOOP", "A_LOOP"), ("A_POOL", "A_POOL"),
         ("A_DIST", "A_DIST"), ("A_M6_OBEN", "A_M6_OBEN"),
         ("A_M6_UNTEN", "A_M6_UNTEN"), ("A_M6_BASIS", "A_M6_BASIS"),
         ("A_M6_BASIS_K", "A_M6_BASIS_K"), ("A_M6_RET", "A_M6_RET"),
         ("A_M6_SORT", "A_M6_SORT"), ("A_M6_SORT2", "A_M6_SORT2"),
         ("A_TP2", "A_TP2"), ("A_KBASIS", "A_KBASIS")]
for nm, _k in basis:
    n = src.count(rb[nm])
    print(f"   {nm:<12} count={n}")
    assert n == 1, (nm, n)

gepatcht = (src.replace(rb["A_KANTEN"], rb["A_KANTEN_NEW"])
               .replace(rb["A_LOOP"], rb["A_LOOP_NEW"])
               .replace(rb["A_POOL"], rb["A_POOL_NEW"])
               .replace(rb["A_DIST"], rb["A_DIST_NEW"])
               .replace(rb["A_M6_BASIS_K"], rb["A_M6_BASIS_K_NEW"])
               .replace(rb["A_M6_BASIS"], rb["A_M6_BASIS_NEW"])
               .replace(rb["A_M6_RET"], rb["A_M6_RET_NEW"])
               .replace(rb["A_M6_SORT"], rb["A_M6_SORT_NEW"])
               .replace(rb["A_M6_SORT2"], rb["A_M6_SORT2_NEW"])
               .replace(rb["A_M6_OBEN"], rb["A_M6_OBEN_NEW"])
               .replace(rb["A_M6_UNTEN"], rb["A_M6_UNTEN_NEW"])
               .replace(rb["A_TP2"], rb["A_TP2_NEW"])
               .replace(rb["A_KBASIS"], rb["A_KBASIS_NEW"]))
print(f"   -> Basis-13 angewandt: {len(gepatcht)} Zeichen\n")

# --- B) ZP-4 --------------------------------------------------------------
print("B. ZP-4-Anker (Quelle _tmp_e34_auto.py, Z. 381..405)")
for nm in ZP4_NAMEN:
    n = gepatcht.count(ra[nm])
    print(f"   {nm:<8} count={n}")
    assert n == 1, (nm, n)

# --- C) Gleichheit der beiden Regelquellen --------------------------------
a = gepatcht
for nm in ZP4_NAMEN:
    a = a.replace(ra[nm], ra[nm + "_NEW"])
print(f"\nC. ZP-4-Quelltext (e34_auto-Regeln): {len(a)} Zeichen")
print(f"   sha256 = {hashlib.sha256(a.encode()).hexdigest()}")

# --- D) Kompilierbarkeit --------------------------------------------------
print("\nD. Kompilierbarkeit des vierfach gepatchten Quelltexts")
compile(a, "<zp4_vorschau>", "exec")
print("   compile(): OK")
(ROOT / "test" / "_tmp_e34m_zp4_soll.txt").write_text(
    hashlib.sha256(a.encode()).hexdigest() + "\n", encoding="utf-8")
