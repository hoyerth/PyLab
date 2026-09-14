# -*- coding: utf-8 -*-
"""Archivierung aller Reclaim-Dateien und -Artefakte (Beschluss des Anwenders).

Ziel: ``test/archiv/reclaim/`` -- Struktur des Ursprungs bleibt erhalten
(``test/archiv/reclaim/<originaler Relativpfad>``), damit jede Bewegung
reversibel ist.

Sicherheit:
  * TROCKENLAUF als Vorgabe; ``--scharf`` fuehrt aus.
  * MANIFEST.sha256 mit SHA256 + Groesse + Ursprungspfad JE DATEI.
  * Eine Kollision mit einer bereits vorhandenen Zieldatei bricht ab.
  * NICHT angefasst werden: andere Themenbereiche (Setup C, Counter Engine,
    Makro/Brent, Silver/Regime, Zeitbasis), Infrastruktur (test.py,
    SESSION_HANDOFF.md) und die vorhandenen Ordner archiv/ und trash/.

Aufruf:
    .venv\\Scripts\\python.exe test\\_tmp_archiviere_reclaim.py
    .venv\\Scripts\\python.exe test\\_tmp_archiviere_reclaim.py --scharf
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
ZIEL = TEST / "archiv" / "reclaim"

# ---------------------------------------------------------------------------
# KEEP = bleibt liegen (andere Themen + Infrastruktur + bestehende Ablagen).
# Alles andere unter test/ gilt als Reclaim und wird archiviert.
# ---------------------------------------------------------------------------
KEEP = re.compile(
    r"(^test\.py$|^SESSION_HANDOFF\.md$|^CHECKPOINT_|^MERKER"
    r"|setup_c|setup-c|counter"
    r"|makro|macro_|_macro|brent|eco_"
    r"|silver|phasen_volumen|volumen_profil|schwellen|bruch_matrix"
    r"|regime_sonde|regime_actor|regime_z3|regime_gate|regime_karte"
    r"|phasen_regime|regime_schwellen"
    r"|zeitbasis|zeitkanon|zeitcheck"
    r"|duckdb|sqlite|\.db$|db_|_db_|init_\w*_db|migrate_"
    r"|marimo|_ui_|_ui\.)",
    re.I)

# Ordner unter test/, die NICHT durchlaufen werden.
SKIP_DIRS = {"archiv", "trash", "__pycache__", ".ipynb_checkpoints",
             "setup_c", "counter_engine", "silver_regime",
             "_ref_baseline_pre_ema"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def sammle() -> tuple[list[Path], list[Path]]:
    """(zu_archivieren, bleibt) -- jeweils Dateien unter test/."""
    arch, bleibt = [], []
    for p in sorted(TEST.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(TEST)
        if any(teil in SKIP_DIRS for teil in rel.parts[:-1]):
            continue
        if p.name.startswith("_tmp_archiviere_reclaim"):
            continue
        if KEEP.search(rel.as_posix()):
            bleibt.append(p)
        else:
            arch.append(p)
    return arch, bleibt


def main(scharf: bool) -> None:
    arch, bleibt = sammle()
    groesse = sum(p.stat().st_size for p in arch)

    print("=" * 100)
    print("ARCHIVIERUNG RECLAIM -> " + ZIEL.relative_to(ROOT).as_posix())
    print("=" * 100)
    print(f"Modus        : {'SCHARF (verschieben)' if scharf else 'TROCKENLAUF'}")
    print(f"Zu archivieren: {len(arch)} Dateien, {groesse:,} B")
    print(f"Bleibt liegen : {len(bleibt)} Dateien")

    print()
    print("-" * 100)
    print("BLEIBT (andere Themen / Infrastruktur) -- Kontrolle der Grenze")
    print("-" * 100)
    for p in bleibt:
        print(f"  {p.relative_to(TEST).as_posix()}")

    print()
    print("-" * 100)
    print("ZU ARCHIVIEREN -- Kontrolle der Grenze")
    print("-" * 100)
    for p in arch[:40]:
        print(f"  {p.relative_to(TEST).as_posix()}")
    if len(arch) > 40:
        print(f"  ... +{len(arch) - 40} weitere")

    if not scharf:
        print()
        print("TROCKENLAUF -- nichts veraendert. Mit --scharf ausfuehren.")
        return

    # --- Kollisionspruefung VOR jeder Bewegung ----------------------------
    kollisionen = [p for p in arch
                   if (ZIEL / p.relative_to(TEST)).exists()]
    if kollisionen:
        print()
        print("ABBRUCH: Zieldatei existiert bereits:")
        for p in kollisionen[:20]:
            print("  " + p.relative_to(TEST).as_posix())
        raise SystemExit(1)

    ZIEL.mkdir(parents=True, exist_ok=True)
    zeilen: list[str] = []
    bewegt = 0
    for p in arch:
        rel = p.relative_to(TEST)
        dst = ZIEL / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        h = sha256(p)
        groesse_p = p.stat().st_size
        shutil.move(str(p), str(dst))
        zeilen.append(f"{h}  {groesse_p:>10}  test/{rel.as_posix()}")
        bewegt += 1

    zeilen.sort(key=lambda z: z.split("  ", 2)[2])
    man = ZIEL / "MANIFEST.sha256"
    kopf = [
        "# Archivierung Reclaim -- Beschluss des Anwenders (Reclaim als",
        "# Handelsstrategie verworfen). Stand: siehe Git-/Dateidatum.",
        f"# Dateien: {bewegt}   Bytes: {groesse}",
        "# Format: SHA256  GROESSE  URSPRUNGSPFAD (test/...)",
        "# Rueckfuehrung: Datei von hier nach test/<Relativpfad> zurueck.",
    ]
    man.write_text("\n".join(kopf + zeilen) + "\n", encoding="utf-8",
                   newline="\n")

    mb = man.read_bytes()
    print()
    print("=" * 100)
    print(f"AUSGEFUEHRT: {bewegt} Dateien verschoben nach "
          f"{ZIEL.relative_to(ROOT).as_posix()}")
    print(f"MANIFEST    : {man.relative_to(ROOT).as_posix()}  "
          f"({len(zeilen)} Eintraege, {len(mb)} B, "
          f"SHA256 {hashlib.sha256(mb).hexdigest()[:16]}...)")
    print("=" * 100)


if __name__ == "__main__":
    main(scharf="--scharf" in sys.argv)
