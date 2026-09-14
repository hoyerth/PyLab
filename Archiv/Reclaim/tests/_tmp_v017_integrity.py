# -*- coding: utf-8 -*-
"""READ-ONLY Integritaets-Report nach dem V017-Probe-Lauf."""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
R = pathlib.Path(__file__).resolve().parent.parent


def h(p: pathlib.Path):
    b = p.read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


print("--- arretierte Quellen (Soll: unveraendert) ---")
for p in (r"test\tmp_kanten_engine_replay.py",
          r"backtest_lab\phasen_regime_adapter.py"):
    s, n = h(R / p)
    print(f"  {s[:16]}  {n:>9,} B  {p}")
print("--- Backups (Phase A-4 Schritt 1) ---")
for p in (r"test\_tmp_backup_engine_pre_v017.py",
          r"test\_tmp_backup_renderer_pre_v017.py"):
    s, n = h(R / p)
    print(f"  {s[:16]}  {n:>9,} B  {p}")
print("--- Renderer (geaendert) ---")
s, n = h(R / "test" / "tmp_png_aug_sichttest.py")
print(f"  {s[:16]}  {n:>9,} B  test/tmp_png_aug_sichttest.py")
print("--- Wegwerf-Engine (Probe) ---")
s, n = h(R / "test" / "_tmp_engine_v017cand.py")
print(f"  {s[:16]}  {n:>9,} B  test/_tmp_engine_v017cand.py")
print("--- versiegelte PNG-Saetze (Block 01) ---")
for m in ("", "v014_", "v015_", "v016_", "v017_"):
    f = R / "test" / f"aug_sichttest_{m}01_gesamt.png"
    if not f.exists():
        print(f"  {f.name:44s} -- existiert noch nicht (Engine nicht "
              f"eingebrannt)")
        continue
    st = f.stat()
    mt = datetime.datetime.fromtimestamp(st.st_mtime)
    print(f"  {f.name:44s} {st.st_size:>10,} B  {mt:%Y-%m-%d %H:%M}")
print("--- Probe-Satz V017 bei PROBE_PRAEFIX 'probe_v017_' ---")
for nm in ("01_gesamt", "02_h1_box", "03_h2_phasen", "04_p9_regime",
           "05_kantenkarte"):
    f = R / "test" / ("probe_v017_aug_sichttest_v017_" + nm + ".png")
    s, _ = h(f)
    print(f"  {f.name:50s} {f.stat().st_size:>10,} B  {s[:16]}")
print("--- Protokoll ---")
f = R / "test" / "_tmp_probe_v017_out.txt"
s, n = h(f)
print(f"  {s[:16]}  {n:>9,} B  test/_tmp_probe_v017_out.txt")
