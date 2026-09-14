"""Reclaim-Archivierung Phase 2: Zusammenfuehrung aller Reclaim-Artefakte
nach ``Archiv/Reclaim/``.

Trockenlauf ist der Default. Ausfuehrung nur mit ``--scharf``.

Struktur (Ziel):
    Archiv/Reclaim/README.md
    Archiv/Reclaim/MANIFEST.sha256
    Archiv/Reclaim/MANIFEST_ENTFERNT.sha256
    Archiv/Reclaim/docs/       (Dokumente)
    Archiv/Reclaim/scripts/    (Produktiv-/Hilfsskripte)
    Archiv/Reclaim/tests/      (Testartefakte, 1:1-Herkunftsstruktur)
    Archiv/Reclaim/artefakte/  (Beweisstuecke, ``-text``-geschuetzt)

Schalter:
    --scharf        ausfuehren (sonst Trockenlauf)
    --ohne-png      PNG-Aufraeumung ueberspringen
    --ohne-trash    test/trash-Loeschung ueberspringen
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIEL = ROOT / "Archiv" / "Reclaim"
SCHARF = "--scharf" in sys.argv
OHNE_PNG = "--ohne-png" in sys.argv
OHNE_TRASH = "--ohne-trash" in sys.argv

bewegt: list[tuple[str, str, str, int]] = []
entfernt: list[tuple[Path, str, int]] = []
fehler: list[str] = []
log: list[str] = []


def rel(p: Path) -> str:
    """Pfad relativ zum Projektwurzelverzeichnis, POSIX-Schreibweise."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def sha256(p: Path) -> str:
    """SHA256-Hexdigest einer Datei (1-MiB-Chunks)."""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dateien(p: Path) -> list[Path]:
    """Rekursive Dateiliste (Verzeichnisse werden leer nicht gelistet)."""
    if p.is_file():
        return [p]
    return sorted(x for x in p.rglob("*") if x.is_file())


def bewege_tree(src: Path, dst: Path) -> None:
    """Verschiebt ein Verzeichnis als Ganzes nach ``dst``."""
    if not src.is_dir():
        fehler.append(f"QUELLE FEHLT : {rel(src)}")
        return
    if dst.exists():
        fehler.append(f"KOLLISION    : {rel(dst)}")
        return
    liste = dateien(src)
    if not SCHARF:
        for f in liste:
            bewegt.append((rel(f), rel(dst / f.relative_to(src)), "", -1))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    for f in liste:
        nf = dst / f.relative_to(src)
        bewegt.append((rel(f), rel(nf), sha256(nf), nf.stat().st_size))


def bewege_datei(src: Path, dst_dir: Path) -> None:
    """Verschiebt eine einzelne Datei nach ``dst_dir``."""
    if not src.is_file():
        fehler.append(f"QUELLE FEHLT : {rel(src)}")
        return
    dst = dst_dir / src.name
    if dst.exists():
        fehler.append(f"KOLLISION    : {rel(dst)}")
        return
    if not SCHARF:
        bewegt.append((rel(src), rel(dst), "", -1))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    bewegt.append((rel(src), rel(dst), sha256(dst), dst.stat().st_size))


def bewege_glob(muster: str, dst_dir: Path) -> int:
    """Verschiebt alle Treffer eines Glob-Musters; gibt die Anzahl zurueck."""
    treffer = sorted(ROOT.glob(muster))
    for t in treffer:
        if t.is_file():
            bewege_datei(t, dst_dir)
    return len([t for t in treffer if t.is_file()])


def loesche(p: Path) -> None:
    """Registriert und loescht eine Datei (bzw. ein Verzeichnis)."""
    if p.is_file():
        entfernt.append((p, sha256(p), p.stat().st_size))
        if SCHARF:
            p.unlink()
    elif p.is_dir():
        for f in dateien(p):
            entfernt.append((f, sha256(f), f.stat().st_size))
        if SCHARF:
            shutil.rmtree(p)


def ist_behalten_png(p: Path) -> bool:
    """Regel 'letzter Lauf' (Weisung 2026-09-14): AUG = v019, Mai-Juli = sichttest."""
    n = p.name
    if n.startswith("aug_sichttest_v019_"):
        return True
    if n.startswith("ext_sichttest_v2_"):
        return True
    if n in {"render_mai_sichttest.png", "render_jun_sichttest.png", "render_jul_sichttest.png"}:
        return True
    if p.parent.name == "artefakte":
        return True
    if n == "trades_AUG_mC_v40r.png":
        return True
    return False


def main() -> int:
    """Fuehrt alle Phasen aus und schreibt den Bericht."""
    if not SCHARF:
        log.append("TROCKENLAUF (kein Schreibzugriff). Ausfuehren mit --scharf")

    # --- P0: Zielordner -----------------------------------------------------
    if SCHARF:
        ZIEL.mkdir(parents=True, exist_ok=True)
    log.append("")
    log.append("=== P0 Zielstruktur ===")
    log.append(f"Ziel: {rel(ZIEL)}  existiert={'ja' if ZIEL.exists() else 'nein'}")

    # --- P1: test/archiv/reclaim (1118 Dateien) ----------------------------
    log.append("")
    log.append("=== P1 test/archiv/reclaim -> Archiv/Reclaim/tests ===")
    vor = len(dateien(ROOT / "test/archiv/reclaim"))
    bewege_tree(ROOT / "test/archiv/reclaim", ZIEL / "tests")
    log.append(f"Dateien bewegt: {vor}")

    # --- P2: losestehende reclaim_*.py in test/archiv/ ---------------------
    log.append("")
    log.append("=== P2 test/archiv/reclaim_*.py -> Archiv/Reclaim/tests ===")
    n = bewege_glob("test/archiv/reclaim_*.py", ZIEL / "tests")
    log.append(f"Dateien bewegt: {n}")

    # --- P3: v019_aug_staging (Kanten-Engine-v019-Staging) -----------------
    log.append("")
    log.append("=== P3 test/archiv/v019_aug_staging -> Archiv/Reclaim/tests/v019_aug_staging ===")
    fremd = [
        "H2_PHASENREGIME_ADAPTER_SPEZ.md",
        "phasen_regime_adapter.py",
        "SESSION_HANDOFF.md",
    ]
    for name in fremd:
        bewege_datei(ROOT / "test/archiv/v019_aug_staging" / name, ROOT / "test/archiv")
    vor = len(dateien(ROOT / "test/archiv/v019_aug_staging"))
    bewege_tree(ROOT / "test/archiv/v019_aug_staging", ZIEL / "tests" / "v019_aug_staging")
    log.append(f"Reclaim-Anteil bewegt: {vor} Dateien")
    log.append(f"Fremdbeigaben zurueck nach test/archiv/: {len(fremd)} ({', '.join(fremd)})")

    # --- P4: Dokumente ------------------------------------------------------
    log.append("")
    log.append("=== P4 Dokumente -> Archiv/Reclaim/docs ===")
    n = bewege_glob("docs/Archiv/reclaim/*.md", ZIEL / "docs")
    n += bewege_glob("docs/Archiv/RECLAIM.md", ZIEL / "docs")
    n += bewege_glob("docs/Archiv/reclaim_*.md", ZIEL / "docs")
    log.append(f"Dateien bewegt: {n}")

    # --- P5: Produktivskript ------------------------------------------------
    log.append("")
    log.append("=== P5 scripts/reclaim_live_kernel.py -> Archiv/Reclaim/scripts ===")
    bewege_datei(ROOT / "scripts/reclaim_live_kernel.py", ZIEL / "scripts")
    log.append("Dateien bewegt: 1")

    # --- P6: Beweisstuecke --------------------------------------------------
    log.append("")
    log.append("=== P6 docs/artefakte/aug_p11 -> Archiv/Reclaim/artefakte ===")
    vor = len(dateien(ROOT / "docs/artefakte/aug_p11"))
    bewege_tree(ROOT / "docs/artefakte/aug_p11", ZIEL / "artefakte")
    log.append(f"Dateien bewegt: {vor}")

    # --- P7: Archivierungswerkzeug -----------------------------------------
    log.append("")
    log.append("=== P7 test/_tmp_archiviere_reclaim.py -> Archiv/Reclaim/scripts ===")
    bewege_datei(ROOT / "test/_tmp_archiviere_reclaim.py", ZIEL / "scripts")
    log.append("Dateien bewegt: 1")

    # --- P8: PNG-Aufraeumung ------------------------------------------------
    log.append("")
    log.append("=== P8 PNG-Aufraeumung (Regel: letzter Lauf AUG=v019, Mai-Juli=sichttest) ===")
    behalten: list[tuple[str, Path, int]] = []
    kandidaten_weg: list[Path] = []
    gesehen: set[str] = set()
    if SCHARF:
        png_liste = sorted(p for p in dateien(ZIEL) if p.suffix.lower() == ".png")
    else:
        png_liste = []
        for q in (
            ROOT / "test/archiv/reclaim",
            ROOT / "test/archiv/v019_aug_staging",
            ROOT / "docs/artefakte/aug_p11",
        ):
            if q.exists():
                png_liste.extend(sorted(p for p in dateien(q) if p.suffix.lower() == ".png"))
    for p in png_liste:
        digest = sha256(p)
        if ist_behalten_png(p) and digest not in gesehen:
            gesehen.add(digest)
            behalten.append((digest, p, p.stat().st_size))
        else:
            kandidaten_weg.append(p)
    log.append(f"PNG gesamt         : {len(png_liste)}")
    log.append(f"PNG behalten       : {len(behalten)}")
    log.append(f"PNG entfernen      : {len(kandidaten_weg)}")
    for digest, p, groesse in sorted(behalten, key=lambda t: str(t[1])):
        log.append(f"  BEHALTEN {groesse:>10,} B  {digest[:16]}  {rel(p)}")
    if not OHNE_PNG:
        for p in kandidaten_weg:
            loesche(p)

    # --- P9: test/trash -----------------------------------------------------
    log.append("")
    log.append("=== P9 test/trash loeschen ===")
    trash = ROOT / "test/trash"
    if not OHNE_TRASH and trash.exists():
        anz = len(dateien(trash))
        groesse = sum(f.stat().st_size for f in dateien(trash))
        loesche(trash)
        log.append(f"Dateien entfernt: {anz} ({groesse:,} B)")
    else:
        log.append("uebersprungen")

    # --- P10: Manifeste -----------------------------------------------------
    log.append("")
    log.append("=== P10 Manifeste ===")
    if SCHARF:
        herkunft = {neu: alt for neu, alt, _, _ in bewegt}
        zeilen = ["# SHA256  GROESSE  PFAD  URSPRUNG", ""]
        for f in sorted(dateien(ZIEL)):
            if f.parent == ZIEL and f.name.startswith("MANIFEST"):
                continue
            neu = rel(f)
            zeilen.append(f"{sha256(f)}  {f.stat().st_size}  {neu}  {herkunft.get(neu, '-')}")
        (ZIEL / "MANIFEST.sha256").write_text("\n".join(zeilen) + "\n", encoding="utf-8")

        z2 = ["# SHA256  GROESSE  PFAD  (entfernt/dekonserviert 2026-09-14)", ""]
        for p, digest, groesse in sorted(entfernt, key=lambda t: rel(t[0])):
            z2.append(f"{digest}  {groesse}  {rel(p)}")
        (ZIEL / "MANIFEST_ENTFERNT.sha256").write_text("\n".join(z2) + "\n", encoding="utf-8")
        log.append(f"MANIFEST.sha256          : {len(zeilen) - 2} Eintraege")
        log.append(f"MANIFEST_ENTFERNT.sha256 : {len(entfernt)} Eintraege")
    else:
        log.append("(Trockenlauf: keine Manifeste geschrieben)")

    # --- Bericht ------------------------------------------------------------
    log.append("")
    log.append("=== Bilanz ===")
    log.append(f"bewegte Dateien  : {len([b for b in bewegt])}")
    log.append(f"entfernte Dateien: {len(entfernt)}")
    log.append(f"Fehler           : {len(fehler)}")
    for f in fehler:
        log.append(f"  {f}")

    text = "\n".join(log)
    print(text)
    ausgabe = ROOT / "test" / "_tmp_archiviere_reclaim2_out.txt"
    ausgabe.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
