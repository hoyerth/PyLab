# -*- coding: utf-8 -*-
"""Read-only: letzte N Zeilen einer Datei zeigen + Zeilenendungs-Statistik."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

p = pathlib.Path(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
b = p.read_bytes()
t = b.decode("utf-8")
lines = t.split("\n")
crlf = b.count(b"\r\n")
lf = b.count(b"\n")
print(f"# {p}  bytes={len(b)}  CRLF={crlf}  LF={lf}  lines={len(lines)}  "
      f"SHA256={hashlib.sha256(b).hexdigest()}")
print("#" + "-" * 100)
start = max(0, len(lines) - n)
for i, ln in enumerate(lines[start:], start=start + 1):
    print(f"{i:>5}| {ln}")
