"""Repariert die Spalte URSPRUNG in Archiv/Reclaim/MANIFEST.sha256.

Ursache: Im Archivierungswerkzeug war das Tupel beim Aufbau des Herkunfts-Dicts
vertauscht, wodurch jede Zeile '-' statt des Ursprungspfades erhielt.

Rekonstruktion:
  * tests/                 -> aus dem Phase-1-Manifest (tests/MANIFEST.sha256),
                              das je Datei den urspruenglichen test/-Pfad fuehrt
  * tests/v019_aug_staging/ -> test/archiv/v019_aug_staging/
  * tests/reclaim_*.py/andere -> test/archiv/reclaim_*  bzw. test/archiv/reclaim/
  * docs/, scripts/, artefakte/ -> harte Zuordnung aus `git show --name-status HEAD`
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

def _finde_root() -> Path:
    """Projektwurzel = oberstes Verzeichnis mit ``.git``."""
    hier = Path(__file__).resolve().parent
    for kandidat in [hier, *hier.parents]:
        if (kandidat / ".git").exists():
            return kandidat
    return hier


ROOT = _finde_root()
ZIEL = ROOT / "Archiv" / "Reclaim"

DOCS = {
    "RECLAIM.md": "docs/Archiv/RECLAIM.md",
    "reclaim_avwap_roadmap.md": "docs/reclaim_avwap_roadmap.md",
    "reclaim_historie_index.md": "docs/reclaim_historie_index.md",
    "reclaim_kanten_engine_spez.md": "docs/reclaim_kanten_engine_spez.md",
    "reclaim_live_lateriz_befund.md": "docs/reclaim_live_lateriz_befund.md",
    "reclaim_makro_persistenz_design.md": "docs/Archiv/reclaim_makro_persistenz_design.md",
    "reclaim_signal_loop_design.md": "docs/Archiv/reclaim_signal_loop_design.md",
    "reclaim_snapshot_spez.md": "docs/reclaim_snapshot_spez.md",
    "reclaim_v04_mentor_vorlage.md": "docs/Archiv/reclaim_v04_mentor_vorlage.md",
    "session_checkpoint_kanten_engine_v3_2026-09-06.md": "docs/session_checkpoint_kanten_engine_v3_2026-09-06.md",
    "session_checkpoint_kanten_engine_v3_2026-09-08.md": "docs/session_checkpoint_kanten_engine_v3_2026-09-08.md",
    "session_checkpoint_kanten_engine_v3_2026-09-08_teil2.md": "docs/session_checkpoint_kanten_engine_v3_2026-09-08_teil2.md",
}

SCRIPTS = {
    "reclaim_live_kernel.py": "scripts/reclaim_live_kernel.py",
    "_tmp_archiviere_reclaim.py": "test/_tmp_archiviere_reclaim.py",
    "_tmp_archiviere_reclaim2.py": "test/_tmp_archiviere_reclaim2.py",
    "_tmp_archiviere_reclaim3.py": "test/_tmp_archiviere_reclaim3.py",
    "_tmp_reclaim_manifest_fix.py": "test/_tmp_reclaim_manifest_fix.py",
    "_tmp_archiviere_reclaim2_out.txt": "test/_tmp_archiviere_reclaim2_out.txt",
    "_tmp_archiviere_reclaim3_out.txt": "test/_tmp_archiviere_reclaim3_out.txt",
    "_tmp_reclaim_commitmsg.txt": "test/_tmp_reclaim_commitmsg.txt",
    "_tmp_reclaim_commitmsg2.txt": "test/_tmp_reclaim_commitmsg2.txt",
}


def sha256(p: Path) -> str:
    """SHA256-Hexdigest einer Datei."""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dateien(p: Path) -> list[Path]:
    """Rekursive Dateiliste."""
    return sorted(x for x in p.rglob("*") if x.is_file())


def lade_phase1() -> dict[str, str]:
    """Liest das Phase-1-Manifest und bildet Restpfad -> urspruenglicher test/-Pfad."""
    quelle = ZIEL / "tests" / "MANIFEST.sha256"
    karte: dict[str, str] = {}
    for zeile in quelle.read_text(encoding="utf-8", errors="replace").splitlines():
        if not re.match(r"^[0-9a-f]{64}\s", zeile):
            continue
        teile = zeile.split(None, 2)
        if len(teile) < 3:
            continue
        pfad = teile[2].strip().replace("\\", "/")
        if pfad.startswith("test/"):
            karte[pfad[len("test/"):]] = pfad
    return karte


def urspung(rel_pfad: str, karte: dict[str, str]) -> str:
    """Bestimmt den Ursprungspfad (vor Phase 2) fuer einen Archivpfad."""
    if rel_pfad.startswith("tests/setup_b/"):
        return "test/archiv/" + rel_pfad[len("tests/setup_b/"):]
    if rel_pfad.startswith("tests/v019_aug_staging/"):
        return "test/archiv/v019_aug_staging/" + rel_pfad[len("tests/v019_aug_staging/"):]
    if rel_pfad == "tests/MANIFEST.sha256":
        return "test/archiv/reclaim/MANIFEST.sha256"
    if rel_pfad.startswith("tests/"):
        rest = rel_pfad[len("tests/"):]
        if rest in karte:
            return karte[rest]
        if Path(rest).name.startswith("reclaim_"):
            return "test/archiv/" + rest
        return "test/archiv/reclaim/" + rest
    if rel_pfad.startswith("docs/"):
        return DOCS.get(rel_pfad[len("docs/"):], "-")
    if rel_pfad.startswith("scripts/"):
        return SCRIPTS.get(rel_pfad[len("scripts/"):], "-")
    if rel_pfad.startswith("artefakte/"):
        return "docs/artefakte/aug_p11/" + rel_pfad[len("artefakte/"):]
    return "-"


def main() -> int:
    """Schreibt MANIFEST.sha256 und MANIFEST_ENTFERNT.sha256 neu."""
    karte = lade_phase1()
    print(f"Phase-1-Manifest gelesen: {len(karte)} Ursprungspfade")

    herkunft = {p.relative_to(ZIEL).as_posix(): urspung(p.relative_to(ZIEL).as_posix(), karte)
                for p in dateien(ZIEL)}
    print(f"Archivpfade klassifiziert: {len(herkunft)}")

    offen = sorted(p for p, u in herkunft.items() if u == "-" and not Path(p).name.startswith(("MANIFEST", "README")))
    print(f"Nicht zuordenbar: {len(offen)}")
    for p in offen[:10]:
        print(f"  OFFEN {p}")

    zeilen = ["# SHA256  GROESSE  PFAD  URSPRUNG", ""]
    for f in sorted(dateien(ZIEL)):
        rel_pfad = f.relative_to(ROOT).as_posix()
        if f.parent == ZIEL and f.name.startswith("MANIFEST"):
            continue
        zeilen.append(f"{sha256(f)}  {f.stat().st_size}  {rel_pfad}  {herkunft.get(f.relative_to(ZIEL).as_posix(), '-')}")
    (ZIEL / "MANIFEST.sha256").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"MANIFEST.sha256 geschrieben: {len(zeilen) - 2} Eintraege")

    alt = ZIEL / "MANIFEST_ENTFERNT.sha256"
    zeilen2 = ["# SHA256  GROESSE  PFAD  URSPRUNG  (entfernt 2026-09-14)", ""]
    for zeile in alt.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[0-9a-f]{64}\s", zeile):
            continue
        teile = zeile.split()
        if len(teile) < 3:
            continue
        digest, groesse, pfad = teile[0], teile[1], teile[2]
        if pfad.startswith("test/trash/"):
            ursp = pfad
        else:
            rest = pfad[len("Archiv/Reclaim/"):] if pfad.startswith("Archiv/Reclaim/") else pfad
            ursp = urspung(rest, karte)
        zeilen2.append(f"{digest}  {groesse}  {pfad}  {ursp}")
    alt.write_text("\n".join(zeilen2) + "\n", encoding="utf-8")
    print(f"MANIFEST_ENTFERNT.sha256 geschrieben: {len(zeilen2) - 2} Eintraege")

    st = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True)
    print("git status:", st.stdout.strip() or "(leer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
