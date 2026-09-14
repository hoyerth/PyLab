# -*- coding: utf-8 -*-
"""Stufe 3 / Phase 3: Engine-Scan-Gegenprobe (PNG-frei, read-only)."""
import importlib.util
import sys
from pathlib import Path

ENGINE = Path(r"F:\Python\PyLab\test\tmp_kanten_engine_replay.py")

spec = importlib.util.spec_from_loader("ke_chk", loader=None)
mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
mod.__file__ = str(ENGINE)
sys.modules["ke_chk"] = mod
exec(compile(ENGINE.read_text(encoding="utf-8"), str(ENGINE), "exec"),
     mod.__dict__)

cfg = mod.StraightEdgeHarnessKonfiguration()
print("box_end_datum =", repr(cfg.box_end_datum))
scan = mod._se_scan("AUG", cfg)
print("box_end_bar   =", scan["box_end_bar"], "(soll 644)")
print("n             =", scan["n"], "(soll 1288)")
print("edges/seeds   =", len(scan["edges"]), len(scan["seeds"]))
assert scan["box_end_bar"] == 644, scan["box_end_bar"]
assert scan["n"] == 1288, scan["n"]
assert cfg.box_end_datum == "2026-08-19", cfg.box_end_datum
print("OK")
