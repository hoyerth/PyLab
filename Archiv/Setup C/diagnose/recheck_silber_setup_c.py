"""Wegwerf-Gegenprobe: Silber-Bitgenauigkeit nach dem Symbol/Timeframe-Umbau.

Vergleicht die Trade-Daten (alle Spalten ausser Kommentarzeilen) zweier
Setup-C-Laeufe gegen die vor dem Umbau gesicherten TSV-Dateien in
``test/setup_c/silber_backup``. Die Referenzartefakte unter
``reports/setup_c/`` werden NICHT ueberschrieben (eigener ``report_dir``).

Aufruf (Projekt-Root):
    .venv\\Scripts\\python.exe -X utf8 test/recheck_silber_setup_c.py
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.setup_c_profil import TrendConfig, bericht_fenster  # noqa: E402

_BACKUP: Path = _ROOT / "test" / "setup_c" / "silber_backup"
_TMP: Path = _ROOT / "test" / "setup_c" / "silber_recheck"


def _datenzeilen(pfad: Path) -> list[str]:
    """TSV-Datenzeilen ohne Kommentar- und Leerzeilen."""
    return [
        z
        for z in pfad.read_text(encoding="utf-8").splitlines()
        if z.strip() and not z.startswith("#")
    ]


def main() -> int:
    fehler: int = 0
    faelle = (
        ("JUL26", "2026-07-01", "2026-08-01", "setup_c_trades_JUL26.tsv"),
        ("MAI26", "2026-05-01", "2026-06-01", "setup_c_trades_MAI26.tsv"),
    )
    for label, start, ende, quelle in faelle:
        cfg = TrendConfig(
            fenster=label,
            start=start,
            ende=ende,
            report_dir=_TMP,
        )
        bericht_fenster(label, cfg)
        neu: Path = _TMP / f"setup_c_trades_{label}.tsv"
        alt: Path = _BACKUP / quelle
        a, b = _datenzeilen(alt), _datenzeilen(neu)
        gleich: bool = a == b
        print(f"[{label}] Zeilen alt={len(a)} neu={len(b)} -> "
              f"{'IDENTISCH' if gleich else 'ABWEICHUNG'}")
        if not gleich:
            fehler += 1
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"   Zeile {i}:\n     alt: {x}\n     neu: {y}")
                    break
        # Kennzahl-Anker (N48-Summe) aus dem TSV nachrechnen
        summe: float = sum(
            float(z.split("\t")[13])
            for z in b[1:]
            if z.split("\t")[0] == "48"
            and z.split("\t")[11] != "RECHTS_ZENSIERT"
        )
        print(f"   N48-Summe r_f4 = {summe:+.2f}R")
    print("ERGEBNIS:", "OK" if fehler == 0 else f"{fehler} Abweichung(en)")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
