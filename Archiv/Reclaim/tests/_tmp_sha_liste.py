# -*- coding: utf-8 -*-
"""SHA256-Uebersicht der S2-/V-D-/E-20-Artefakte."""
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

FS = [
    "test/tmp_kanten_engine_replay.py",
    "test/tmp_png_aug_sichttest.py",
    "test/_tmp_vd_vertrag_entwurf.py",
    "test/_tmp_s2_scan_cache.pkl",
    "test/_tmp_s2_segment_kandidaten.py",
    "test/_tmp_s2_segment_kandidaten_out.txt",
    "test/_tmp_s2_baseline_ref.py",
    "test/_tmp_s2_baseline_ref_out.txt",
    "test/_tmp_s2_vd_stresstest.py",
    "test/_tmp_s2_vd_stresstest_out.txt",
    "test/_tmp_s2_vd_detail.py",
    "test/_tmp_s2_vd_detail_out.txt",
    "test/_tmp_s2_vd_risiko.py",
    "test/_tmp_s2_e20_poc.py",
    "test/_tmp_s2_e20_poc_out.txt",
    "test/_tmp_s2_e20_poc_stdout.txt",
    "test/_tmp_s2_e20_poc_stderr.txt",
    "test/_tmp_e20_poc_diagnose.py",
    "test/_tmp_sha_liste.py",
    "test/SESSION_HANDOFF.md",
    "reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md",
]
for f in FS:
    if os.path.exists(f):
        b = open(f, "rb").read()
        print(f"{hashlib.sha256(b).hexdigest()}  {len(b):>8}  {f}")
    else:
        print(f"{'MISSING':<64}  {'-':>8}  {f}")
