"""Reclaim-Aufraeumung Phase 4 (Abschluss).

Weisung 2026-09-14:
  1) test/silver_regime/ ist Reclaim-Alt (Setup-B-/Phasenprofil-Linie) und geht
     komplett weg. Ausnahmen: die 3 Rohdaten-CSV und die elf Stufe-5-Regime-
     Dateien, die zur Regimefilter-Validierung von Setup C gehoeren.
  2) Nur die CSV behalten, die Generator-Skripte entfallen (in 3 Minuten neu
     geschrieben).
  3) Lose Dateien in test/ werden unversioniert archiviert.
  4) Keine Hash-Pflege mehr.

Trockenlauf ist der Default; Ausfuehrung mit ``--scharf``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SCHARF = "--scharf" in sys.argv
SELBST = Path(__file__).name


def _finde_root() -> Path:
    """Projektwurzel = oberstes Verzeichnis mit ``.git``."""
    hier = Path(__file__).resolve().parent
    for kandidat in [hier, *hier.parents]:
        if (kandidat / ".git").exists():
            return kandidat
    return hier


ROOT = _finde_root()

# --- 1) Retten: Rohdaten und Stufe-5-Regime ---------------------------------
CSV_NACH = [  # Rohdaten bleiben erhalten -> data/
    "silver_m15_ohlc_2025-01-01_2025-12-01.csv",
    "silver_m15_ohlc_2026-02-05_2026-08-28.csv",
    "silver_m15_ohlc_2026-08-10_2026-08-28.csv",
]
STUFE5 = [  # Regimefilter-/Stufe-5-Validierung (Setup-C-Naehe) -> test/setup_c/regime_stufe5/
    "tmp_regime_validation.py",
    "tmp_test_regime.py",
    "tmp_sanity_klassifikation.py",
    "tmp_stufe5_db_scan.py",
    "tmp_inspect_freezed.py",
    "regime_schwellen_freezed.json",
    "tmp_regime_freezed.txt",
    "tmp_regime_sweep.txt",
    "tmp_regime_sweep_freez_kandidaten.json",
    "tmp_regime_oos_2024.txt",
    "tmp_regime_oos_stress.txt",
]

# --- 2) Generator-Skripte im Reclaim-Archiv entfallen ------------------------
GENERATOREN = [
    "tmp_export_s1_s2_csv.py",
    "tmp_gen_S2_monatsauswertung.py",
    "tmp_gen_S2_wirtschaft.py",
    "tmp_S1_monatsauswertung.py",
    "tmp_S2_monatsauswertung.py",
    "tmp_S1_economic_backtest.py",
    "tmp_S1_leverage_backtest.py",
    "tmp_S2_economic_backtest.py",
    "tmp_S2_leverage_backtest.py",
]

# --- 3) Unversioniertes Archiv fuer lose Testdateien -------------------------
ZEITBASIS_ZIEL = "Archiv/Zeitbasis_Regime"
AUSGENOMMEN_LOSE = {"test.py", "SESSION_HANDOFF.md", "CHECKPOINT_2026-09-13_AUG26.md"}

bewegt: list[str] = []
geloescht: list[str] = []
log: list[str] = []


def rel(p: Path) -> str:
    """Pfad relativ zur Projektwurzel (POSIX)."""
    return p.relative_to(ROOT).as_posix()


def bewege(src: Path, dst: Path) -> None:
    """Verschiebt eine Datei."""
    if not src.is_file():
        log.append(f"  FEHLT      {rel(src)}")
        return
    if dst.exists():
        log.append(f"  KOLLISION  {rel(dst)}")
        return
    if SCHARF:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    bewegt.append(f"{rel(src)}  ->  {rel(dst)}")


def loesche(p: Path) -> None:
    """Loescht eine Datei."""
    if not p.is_file():
        log.append(f"  FEHLT      {rel(p)}")
        return
    if SCHARF:
        p.unlink()
    geloescht.append(rel(p))


def main() -> int:
    """Fuehrt die vier Schritte aus."""
    insel = ROOT / "test" / "silver_regime"
    log.append("SCHARF" if SCHARF else "TROCKENLAUF")

    log.append("")
    log.append("=== 1a) Rohdaten -> data/ ===")
    for n in CSV_NACH:
        bewege(insel / n, ROOT / "data" / n)

    log.append("")
    log.append("=== 1b) Stufe-5-Regime -> test/setup_c/regime_stufe5/ ===")
    for n in STUFE5:
        bewege(insel / n, ROOT / "test" / "setup_c" / "regime_stufe5" / n)

    log.append("")
    log.append("=== 1c) test/silver_regime/ Restbestand loeschen ===")
    rest = sorted(p for p in insel.rglob("*") if p.is_file()) if insel.exists() else []
    for p in rest:
        loesche(p)
    if SCHARF and insel.exists():
        for d in sorted((x for x in insel.rglob("*") if x.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        if not any(insel.iterdir()):
            insel.rmdir()
    log.append(f"  geloescht: {len(rest)} Dateien")

    log.append("")
    log.append("=== 2) Generator-Skripte im Reclaim-Archiv entfernen ===")
    for n in GENERATOREN:
        loesche(ROOT / "Archiv" / "Reclaim" / "tests" / "setup_b" / n)
    log.append(f"  geloescht: {len(GENERATOREN)} Dateien")

    log.append("")
    log.append("=== 3) Lose Testdateien -> Archiv/Zeitbasis_Regime/ ===")
    ziel = ROOT / ZEITBASIS_ZIEL
    lose = sorted(
        p for p in (ROOT / "test").iterdir()
        if p.is_file() and p.name.startswith(("_tmp_", "_chk_", "tmp_"))
        and p.name != SELBST
    )
    for p in lose:
        bewege(p, ziel / p.name)
    log.append(f"  verschoben: {len(lose)} Dateien")
    log.append(f"  ausgenommen: {', '.join(sorted(AUSGENOMMEN_LOSE))}")

    log.append("")
    log.append("=== Bilanz ===")
    log.append(f"bewegt    : {len(bewegt)}")
    log.append(f"geloescht : {len(geloescht)}")
    for z in bewegt:
        log.append(f"  MOVE  {z}")
    text = "\n".join(log)
    print(text)
    ausg = ROOT / "test" / "_phase4_out.txt"
    ausg.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
