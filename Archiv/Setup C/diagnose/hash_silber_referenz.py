"""Wegwerf-Hashprobe: Silber-Referenzartefakte gegen das Backup vergleichen."""
from __future__ import annotations

import hashlib
from pathlib import Path

_ROOT: Path = Path(__file__).resolve().parent.parent
_REP: Path = _ROOT / "reports" / "setup_c"
_BAK: Path = _ROOT / "test" / "setup_c" / "silber_backup"

for name in (
    "setup_c_trades_JUL26.tsv",
    "setup_c_trades_MAI26.tsv",
    "setup_c_JUL26.txt",
    "setup_c_ab_trailing_trades_JUL26.tsv",
):
    a = hashlib.sha256((_REP / name).read_bytes()).hexdigest()
    b = hashlib.sha256((_BAK / name).read_bytes()).hexdigest()
    print(f"{name}: {'IDENTISCH' if a == b else 'ABWEICHUNG'}  {a[:16]}")
