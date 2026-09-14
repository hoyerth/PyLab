# -*- coding: utf-8 -*-
"""S4-Helfer: zeigt Zeilen mit exakter EOL-Markierung (read-only)."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
f = sys.argv[1]
rngs = [tuple(int(x) for x in r.split(":")) for r in sys.argv[2:]]
raw = Path(f).read_bytes()
lines = raw.split(b"\n")
print("##########", f, "lines", len(lines))
for a, z in rngs:
    print(f"--- {a}..{z} ---")
    for i in range(a - 1, min(z, len(lines))):
        ln = lines[i]
        eol = "CRLF" if ln.endswith(b"\r") else "LF"
        txt = ln.decode("utf-8", errors="replace").rstrip("\r")
        print(f"{i+1:4} [{eol}] {txt}")
