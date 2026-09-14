# -*- coding: utf-8 -*-
"""Phase 1: V019-Artefakte einfrieren (Kopie + MANIFEST.sha256).

Originale bleiben unberuehrt in test/ -- bestehende Pruefskripte zeigen
weiterhin auf sie. Kopiert wird nach test/archiv/v019_aug_staging/,
flach (ohne Unterordner), Namen unveraendert.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "test" / "archiv" / "v019_aug_staging"
DST.mkdir(parents=True, exist_ok=True)

# --- Auswahl: V019-Artefakte + Kernquellen + Beleg-Dokumente --------------
PATTERNS = [
    "test/aug_sichttest_v019_*.png",
    "test/tmp_png_aug_sichttest_v019_out.txt",
    "test/_chk_v019_*.py",
    "test/_chk_v019_*_out.txt",
    "test/_tmp_e34m_v019_lauf_out.txt",
    "test/_tmp_s53_*.py",
    "test/_tmp_s53_commit_msg.txt",
    "test/_chk_s1_2026*.py",
    "test/_chk_s1_2026*_out.txt",
    "test/_chk_s1_2026_aug_kontrolle.txt",
    "test/_chk_aug26_daten*.py",
    "test/_chk_aug26_daten*_out.txt",
    "test/tmp_png_aug_sichttest.py",
    "test/tmp_kanten_engine_replay.py",
    "test/_tmp_e34_auto.py",
    "test/_tmp_e34_endogen.py",
    "test/_tmp_backup_engine_pre_v017.py",
    "test/_tmp_backup_engine_pre_v018.py",
    "test/_tmp_backup_renderer_pre_v017.py",
    "test/_tmp_backup_renderer_pre_zp5.py",
    "backtest_lab/phasen_regime_adapter.py",
    "reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md",
    "test/SESSION_HANDOFF.md",
]

files: list[Path] = []
for pat in PATTERNS:
    files.extend(sorted(ROOT.glob(pat)))

seen: set[Path] = set()
uniq: list[Path] = []
for f in files:
    if f.is_file() and f not in seen:
        seen.add(f)
        uniq.append(f)

print(f"Archiv-Ziel : {DST}")
print(f"Dateien     : {len(uniq)}")
print("-" * 92)

zeilen: list[str] = []
for src in uniq:
    rel = src.relative_to(ROOT).as_posix()
    dst = DST / src.name
    shutil.copy2(src, dst)
    b = dst.read_bytes()
    sha = hashlib.sha256(b).hexdigest()
    zeilen.append(f"{sha}  {len(b):>9}  {rel}")
    print(f"  {len(b):>9}  {sha[:16]}...  {rel}")

zeilen.sort(key=lambda z: z.split("  ")[2])
man = DST / "MANIFEST.sha256"
man.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")

mbytes = man.read_bytes()
print("-" * 92)
print(f"MANIFEST    : {man.relative_to(ROOT).as_posix()}  "
      f"({len(zeilen)} Eintraege, {len(mbytes)} B)")
print(f"MANIFEST-SHA: {hashlib.sha256(mbytes).hexdigest()}")
print("Originale   : unberuehrt (Kopie, kein Move)")
print("\nENDE PHASE 1")
