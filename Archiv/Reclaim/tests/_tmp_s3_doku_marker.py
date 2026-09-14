# -*- coding: utf-8 -*-
"""S3.4 -- Additive Inline-Marker ('historisch ueberholt') an 5 Doku-Stellen.

Regel (Anwender-Freigabe 2026-09-11): Die Marker werden ADDITIV als eigene
HTML-Kommentarzeile UEBER die betroffene Stelle gesetzt. Historische Texte
werden NICHT veraendert (Archiv-Doktrin; vgl. docs/ZEITBASIS_KANON.md).

Zeilenverschiebung: Die vom Anwender genannten Zeilen 2903/2919/2922 der
Kanten-Spez stammen aus dem Vor-S1-Stand (Commit c34151d). Das S1-Kopf-Erratum
(Commit 8826639) hat den Text um exakt +12 Zeilen verschoben -> aktuell
2915/2931/2934. Die Marker werden inhaltsverankert (count==1) gesetzt, nicht
ueber nackte Zeilennummern.

Datei-Kodierung: alle drei Zieldateien sind LF (CRLF == 0) -- wird verifiziert.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

MARKER = "<!-- \u26a0\ufe0f historisch \u00fcberholt: siehe docs/ZEITBASIS_KANON.md -->"

# (Datei, eindeutiger Anker, Beschreibung der Stelle)
ZIELE = [
    ("docs/reclaim_kanten_engine_spez.md",
     "zu lesen; die Berlin-Wanduhr liegt 2 h darueber.",
     "Kanten-Spez ~L2915 (ex 2903): 'Spez-Zeiten als UTC-Projektion zu lesen'"),
    ("docs/reclaim_kanten_engine_spez.md",
     "Mitternacht hinaus. `640` = **19.08. 00:00** ist die korrekte "
     "Wanduhr-Grenze.",
     "Kanten-Spez ~L2931 (ex 2919): '640 = korrekte Wanduhr-Grenze'"),
    ("docs/reclaim_kanten_engine_spez.md",
     "innerhalb, bei Wanduhr-Lesart ausserhalb der Box). Der **Voll-Lauf",
     "Kanten-Spez ~L2934 (ex 2922): Box-Effekt/Ausschluss-Trade"),
    ("docs/session_checkpoint_kanten_engine_v3_2026-09-08.md",
     "- Wanduhr-Invariante: MT5-Epochs Berlin-encoded; SQL nutzt strikt",
     "Checkpoint 09-08: falsche 'Wanduhr-Invariante'"),
    ("docs/session_checkpoint_kanten_engine_v3_2026-09-08_teil2.md",
     "## 8. Daten-Anker (AUG, M15, Wanduhr)",
     "Checkpoint 09-08 teil2: SS8-Ueberschrift mit verbotenem Term"),
]


def main() -> int:
    # Vorpruefung: alle Anker eindeutig + LF.
    for p, anker, _b in ZIELE:
        raw = (ROOT / p).read_bytes()
        assert raw.count(b"\r\n") == 0, f"{p}: kein LF-File"
        n = raw.decode("utf-8").count(anker)
        assert n == 1, f"{p}: {n} Treffer fuer {anker[:50]!r}"

    gesetzt = 0
    for p, anker, besch in ZIELE:
        f = ROOT / p
        t = f.read_text(encoding="utf-8")
        # Idempotent: Marker unmittelbar ueber dem Anker -> bereits gesetzt.
        if (MARKER + "\n" + anker) in t:
            print(f"--  {p}  (bereits gesetzt)  <- {besch}")
            continue
        t = t.replace(anker, MARKER + "\n" + anker, 1)
        f.write_text(t, encoding="utf-8", newline="\n")
        assert (f.read_bytes().count(b"\r\n") == 0), f"{p}: CRLF nach Patch!"
        print(f"OK  {p}  <- {besch}")
        gesetzt += 1
    print(f"\n{gesetzt} neue Inline-Marker gesetzt "
          f"(von {len(ZIELE)} Zielstellen).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
