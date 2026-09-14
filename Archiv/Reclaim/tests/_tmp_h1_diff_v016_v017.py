# -*- coding: utf-8 -*-
"""READ-ONLY: H1-Box V016 vs V017 im direkten Vergleich (Backup-Engine)."""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = ROOT / "test" / "tmp_png_aug_sichttest.py"
HEAD = RENDERER.read_text(encoding="utf-8").split(
    "# ---------------------------------------------------------------- Plot")[0]
_HOLD: List[object] = []


def lauf(mode: str, engine: str | None) -> Dict:
    mod = types.ModuleType(f"h1diff_{mode}")
    mod.__file__ = str(RENDERER)
    sys.modules[mod.__name__] = mod
    ns: Dict = mod.__dict__
    argv = ["t", "--mode", mode, "--probe-praefix", "_h1_",
            "--protokoll-nach", "test/_tmp_h1_out.txt"]
    if engine:
        argv += ["--engine", engine]
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = argv
    try:
        exec(compile(HEAD, "<head_h1diff>", "exec"), ns)
    finally:
        _HOLD.append(sys.stdout)
        sys.stdout = old_out
        sys.argv = old_argv
    return ns


def zeige(lbl: str, ns: Dict) -> set:
    h1 = ns["h1_1"]
    print(f"--- {lbl}: {len(h1)} Trades / {sum(t.r for t in h1):+.6f} R ---")
    for t in sorted(h1, key=lambda x: x.bar):
        print(f"  K{t.kid:<3} signal {t.bar:<4} entry {t.entry_bar:<4} "
              f"{t.richtung:<5} {t.stufe:<14} entry {t.entry:.4f} "
              f"sl {t.sl:.4f} tp2 {t.tp2:.4f} r {t.r:+.6f}")
    return {(t.bar, t.kid) for t in h1}


A = zeige("V016 (Backup-Engine ea2f72a8)", lauf(
    "V016", "test/_tmp_backup_engine_pre_v017.py"))
print()
B = zeige("V017 (eingebrannte Engine 4a356765)", lauf("V017", None))

print("\n--- Mengendifferenz H1 ---")
print(f"  nur V016: {sorted(A - B)}")
print(f"  nur V017: {sorted(B - A)}")
print(f"  gemeinsam: {len(A & B)}")
