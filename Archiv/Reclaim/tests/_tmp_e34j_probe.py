# -*- coding: utf-8 -*-
"""read-only: Zeitstempel-/Backup-Probe fuer die H1-Frage."""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

print("--- Backup-/Pre-V018-Engines ---")
for pat in ("test/_tmp_backup*", "test/*pre_v018*", "test/*pre-v018*"):
    for f in sorted(glob.glob(pat)):
        print(" ", os.path.getsize(f), f)

print("\n--- Zeitbasis / SQL im Engine-Kopf ---")
L = open("test/tmp_kanten_engine_replay.py", encoding="utf-8").read().split("\n")
for i, l in enumerate(L):
    if re.search(r"TIME ZONE|AT TIME|SELECT|def _se_scan|['\"]ts['\"]|strftime|"
                 r"to_datetime|box_end|searchsorted|read_parquet|duckdb", l):
        print(f"{i+1:>5}: {l.rstrip()}")
