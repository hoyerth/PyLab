# -*- coding: utf-8 -*-
"""Read-only: Zeilenbereich einer Datei ausgeben (1-basiert, inklusiv)."""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

p = pathlib.Path(sys.argv[1])
a = int(sys.argv[2])
b = int(sys.argv[3])
lines = p.read_text(encoding="utf-8").split("\n")
for i in range(a - 1, min(b, len(lines))):
    print(f"{i + 1:>5}| {lines[i]}")
