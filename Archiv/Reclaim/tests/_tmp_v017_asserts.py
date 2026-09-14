# -*- coding: utf-8 -*-
"""READ-ONLY Gegenprobe: Renderer-Kopf (nur Asserts, kein Plot) je Modus.

Belegt, dass die Sollwert-Umstellung auf ``RendererKonfiguration`` (Z. 465-506)
die versiegelten Modi V01/V014/V015/V016 UNVERAENDERT laesst und der neue
Modus V017 gegen die gemessenen Sollwerte haelt.

Es wird KEINE PNG erzeugt: der Kopf endet vor dem Plot-Abschnitt. Geschrieben
wird nichts -- die Protokollklasse liegt im Plot-Teil.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
P_SEALED = ROOT / "test" / "tmp_kanten_engine_replay.py"
CAND = ROOT / "test" / "_tmp_engine_v017cand.py"

B_BASIS = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        return float(np.mean(px)) if px else self.basis"""
V017 = """        if self.ist_prim_anker:
            return self.basis
        px = [p for b, p in self.wicks if b + 2 <= k]
        if px:
            return float(min(px) if self.seite == "OBEN" else max(px))
        return float(self.wicks[0][1])"""

src = P_SEALED.read_text(encoding="utf-8")
assert src.count(B_BASIS) == 1
CAND.write_text(src.replace(B_BASIS, V017), encoding="utf-8", newline="")

R_SRC = RENDERER.read_text(encoding="utf-8")
MARKER = "# ---------------------------------------------------------------- Plot"
HEAD = R_SRC.split(MARKER)[0]
assert "import matplotlib" not in HEAD
_HOLD: List[object] = []


def run(mode: str, engine: pathlib.Path | None) -> Dict:
    """Renderer-Kopf scharf ausfuehren -- mit aktiven FAIL-LOUD-Asserts."""
    mod = types.ModuleType(f"asserts_{mode}_{engine.stem if engine else 'std'}")
    mod.__file__ = str(RENDERER)
    sys.modules[mod.__name__] = mod
    ns: Dict = mod.__dict__
    argv = ["t", "--mode", mode, "--probe-praefix", "probe_",
            "--protokoll-nach", "test/_tmp_probe_asserts.txt"]
    if engine is not None:
        argv += ["--engine", str(engine.relative_to(ROOT)).replace("\\", "/")]
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = argv
    try:
        exec(compile(HEAD, "<renderer_head_asserts>", "exec"), ns)
    finally:
        _HOLD.append(sys.stdout)
        sys.stdout = old_out
        sys.argv = old_argv
    return ns


LAEUFE = [("V01", None), ("V014", None), ("V015", None), ("V016", None),
          ("V017", CAND)]
fehler = 0
print("=" * 92)
print("ASSERT-PARITAET: Renderer-Kopf je Modus (kein Plot, keine PNG)")
print("=" * 92)
for mode, eng in LAEUFE:
    lbl = f"{mode} (Engine {eng.name})" if eng else f"{mode} (arretierte Engine)"
    try:
        ns = run(mode, eng)
    except AssertionError as exc:
        fehler += 1
        print(f"FAIL  {lbl:38s} AssertionError: {exc}")
        continue
    V0, VB, V1 = ns["V0"], ns["V1_basis"], ns["V1"]
    h1 = ns["h1_1"]
    print(f"OK    {lbl:38s} V0 {len(V0):2d}/{sum(t.r for t in V0):+9.6f} | "
          f"RB {len(VB):2d}/{sum(t.r for t in VB):+9.6f} | "
          f"V1 {len(V1):2d}/{sum(t.r for t in V1):+9.6f} | "
          f"H1 {len(h1)}/{sum(t.r for t in h1):+9.6f} | "
          f"NW {ns['NIVEAUWECHSEL']:3d}")
print("=" * 92)
print(f"Engine-SHA im Kopf: {ns['ENGINE_SHA'][:16]}... ({ns['ENGINE_NAME']})")
CAND.unlink(missing_ok=True)
print("Ergebnis:", "ALLE OK" if fehler == 0 else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
