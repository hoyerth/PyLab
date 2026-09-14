# -*- coding: utf-8 -*-
"""READ-ONLY-Mikroskop: K82 an Bar 1172 im PRODUKTIONSPATCH (AST + Adapter).

Beantwortet exakt: welchen Wert liefert _existiert/_kandidat/M6/Q29/Stufe,
wenn das Schlaf-Fenster von K82 im RAM geloescht wird -- und ob die Mutation
ueberhaupt ankommt.
"""
from __future__ import annotations

import copy
import dataclasses
import pathlib
import sys
import types
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]

mod = types.ModuleType("explo_mikro")
mod.__file__ = str(RENDERER)
sys.modules[mod.__name__] = mod
ns: Dict = mod.__dict__
_old = sys.argv
sys.argv = ["t", "--mode", "V017", "--probe-praefix", "_explo_",
            "--protokoll-nach", "test/_tmp_explo_out.txt"]
exec(compile(HEAD, "<head_mikro>", "exec"), ns)
sys.argv = _old

PNS: Dict = ns["ns"]
scan0 = ns["scan"]
cfg0 = ns["cfg"]
adapter = ns["adapter"]
PATCHED = ns["patched_src"]

print("=" * 100)
print("MIKROSKOP K82 @ Bar 1172 (Produktionspatch)")
print("=" * 100)

# 1) Liegt K82 in scan["edges"] oder scan["seeds"]?
for coll in ("edges", "seeds"):
    ids = [e.kid for e in scan0[coll]]
    print(f"scan['{coll}']: {len(ids)} Objekte | K82 dabei: {82 in ids} "
          f"| K60: {60 in ids} | K85: {85 in ids} | K62: {62 in ids}")

e82 = next(e for e in scan0["edges"] + scan0["seeds"] if e.kid == 82)
print(f"\nK82 ist_aktiv_bei(1172) = {e82.ist_aktiv_bei(1172)} | "
      f"schlaf_windows = {e82.schlaf_windows} | "
      f"erster_pivot_bar = {e82.erster_pivot_bar} | touch_conf(1172) = "
      f"{e82.touch_conf(1172)} | basis_bei(1172) = {e82.basis_bei(1172):.4f}")

# 2) Adapter-Sicht: angewandte Basis / Freigabe
hook = adapter
print("\n--- Adapter (V017) an Bar 1172 ---")
print(f"angewandte_basis(1172, 82, {e82.basis_bei(1172):.4f}) = "
      f"{hook.angewandte_basis(1172, 82, e82.basis_bei(1172)):.4f}")
print(f"freigabe_kid(1172, sweep=67.4940, LONG) = "
      f"{hook.hook_1_freigabe_kid(1172, 67.4940, 'LONG', [])}")
h2 = hook.hook_2_ziel(1172, "LONG")
print(f"hook_2_ziel(1172, LONG) = modus {h2.modus} | ziel {h2.ziel_preis}")
h2s = hook.hook_2_ziel(1259, "LONG")
print(f"hook_2_ziel(1259, LONG) = modus {h2s.modus} | ziel {h2s.ziel_preis}")

# 3) Variantenmatrix: welcher Einzelhebel oeffnet Bar 1172?
print("\n--- Variantenmatrix (je 1 Hebel) ---")


def lauf(scan_obj: Dict, cfg_obj) -> List:
    PNS["_hook"] = adapter
    exec(compile(PATCHED, "<se_trades_mikro>", "exec"), PNS)
    setups, _st = PNS["_se_trades"](copy.deepcopy(scan_obj), cfg_obj)
    return setups


def mut(clear_k82: bool = False, drop_k85: bool = False) -> Dict:
    sc = copy.deepcopy(scan0)
    for c in ("edges", "seeds"):
        for e in sc[c]:
            if e.kid == 82 and clear_k82:
                e.schlaf_windows.clear()
        if drop_k85:
            sc[c] = [e for e in sc[c] if e.kid != 85]
    return sc


def probe(name: str, scan_obj: Dict, cfg_obj) -> None:
    got = lauf(scan_obj, cfg_obj)
    h2 = [t for t in got if t.entry_bar >= 1020]
    print(f"\n{name}")
    print(f"    gesamt {len(got)} | R1 {sum(t.r for t in got):+.6f} | "
          f"ab 1020: {[(t.kid, t.bar, t.entry_bar, round(t.r, 4)) for t in h2]}")

    # Kontrolle der Mutation
    e82b = next(e for e in scan_obj["edges"] + scan_obj["seeds"] if e.kid == 82)
    ids = [e.kid for e in scan_obj["edges"] + scan_obj["seeds"]]
    print(f"    [mut] K82.schlaf_windows={e82b.schlaf_windows} | "
          f"K85 im Pool: {85 in ids}")


probe("V0  Ist", scan0, cfg0)
probe("V1  Q29=200 (aus)", scan0,
      dataclasses.replace(cfg0, quartil_distanz_pct=200.0))
probe("V2  Q29=200 + K82 wach", mut(clear_k82=True),
      dataclasses.replace(cfg0, quartil_distanz_pct=200.0))
probe("V3  Q29=200 + K82 wach + ohne K85", mut(clear_k82=True, drop_k85=True),
      dataclasses.replace(cfg0, quartil_distanz_pct=200.0))
probe("V4  V3 + touches>=2", mut(clear_k82=True, drop_k85=True),
      dataclasses.replace(cfg0, quartil_distanz_pct=200.0,
                          min_touches_handelbar=2))
probe("V5  nur K82 wach (Q29 scharf)", mut(clear_k82=True), cfg0)
print("\n" + "=" * 100)
