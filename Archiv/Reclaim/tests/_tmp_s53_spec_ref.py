# -*- coding: utf-8 -*-
"""Stufe 5.3: Regelbestand-Zeile der Spiegelspez um §75 ergaenzen (LF erhalten)."""
from __future__ import annotations

from pathlib import Path

P = Path(__file__).resolve().parent.parent / "reports" / \
    "h2_phasenregime" / "H2_PHASENREGIME_ADAPTER_SPEZ.md"
s = P.read_text(encoding="utf-8")
alt = "§73 + **§74**. **Errata:**"
neu = "§73 + **§74** + **§75**. **Errata:**"
assert s.count(alt) == 1, s.count(alt)
P.write_text(s.replace(alt, neu, 1), encoding="utf-8", newline="")
print("OK  Regelbestand um §75 ergaenzt")
