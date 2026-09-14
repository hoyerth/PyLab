"""Stufe 2b-0: normatives Regelwerk 54.4 + 55.1 in der Spiegelspez.

Ascii-only Einfuegung (keine Umlaute), Anker sind ASCII. Die Datei wird als
UTF-8 gelesen/geschrieben; Zeilenenden bleiben LF.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "reports" / "h2_phasenregime" / "H2_PHASENREGIME_ADAPTER_SPEZ.md"
src = P.read_text(encoding="utf-8")

AN57 = "## 55. Konsolidat: vom Anwender gesetzte Standards"
AN58 = "## 56. Status (v0.13)"

SEC_544 = """### 54.4 Hindsight-Artefakt-Marker (neu, v0.24 / Stufe 2b)

**Ausnahme zu Regel 10.** Ein Trade, der nur durch die rueckwirkende
Etikettierung der Batch-Zusammenfassung existiert (Hysterese), ist live nicht
handelbar. Er darf im Chart weder verschwiegen noch als vollwertige Position
gelesen werden. Deshalb:

15. **Dritter Marker-Stil `hindsight`** in `mark_trades`:
    Kreis **ohne Fuellung** (`mfc="none"`), Rand `mec="#7f7f7f"`, `mew=1.4`,
    `ms=9.0`, Z-Order 12 (ueber den aktiven Markern). Damit bleibt die
    Ausnahme zu Regel 10 auf dieses eine Element begrenzt.
16. **Strichlinie nur an der Trade-Spanne** (`[t.tp2, t.sl]`, `ls="--"`);
    am Einzelmarker ist `ls` wirkungslos (ein Punkt hat keine Linie).
17. **Annotation** am Marker: `K<kid>@<bar> HINDSIGHT (+x.xx R)`, grau,
    Rahmen `#7f7f7f`, gestrichelt.
18. **Legende** (nur Panels 01, 03, 05):
    `Hindsight-Artefakt - K76@1211, +2.5395 R, Hysterese 77 (nicht handelbar)`.
    Panels 02 (H1-Box) und 04 (P9-Regime) fuehren den Marker nicht --
    Bar 1211 liegt ausserhalb beider Fenster.
19. **Kein Zaehlwert.** Hindsight-Artefakte sind NICHT Teil von `V1`/`R1`;
    sie werden separat als `V1_batch` bilanziert und im Protokoll als
    "NICHT handelbar" ausgewiesen.
20. **Kausaler Primaersatz.** Ab v0.24/Stufe 2b ist `V1` der kausale Satz
    (Fenster aus `ADAPTER_V019_KAUSAL`); die Quartil-Herkunft `_q0` folgt dem
    kausal aktiven Segment (1174..1249 -> A1, ab 1250 -> A2).

---

"""

SEC_551 = """### 55.1 Fortschreibung v0.24 / V019 (Stufe 2b, 2026-09-11)

| # | Standard | Inhalt | Quelle |
|---|---|---|---|
| S11 | **Kausalitaet ist die Primaerwahrheit** | `V1` = kausaler Satz (23 Trades / +85.577150 R, H2 15 / +46.657566). Der Batch-Satz (24 / +88.116626, H2 16 / +49.197042) bleibt als `V1_batch` dokumentiert, ist aber **nicht** handelbar. H1 ist in beiden invariant (8 / +38.919584). | E-34n/15 D6, `ADAPTER_V019_KAUSAL` |
| S12 | **Hysterese-Artefakt sichtbar, nicht gezaehlt** | K76@1211 wird als ungefuellter grauer Kreis gezeichnet (54.4), zaehlt aber weder in `V1` noch in `R1`. | 54.4, `KONFIGURATION_V019.neu_basis_soll_hindsight` |
| S13 | **Fail-Loud beidseitig** | Der Renderer fuehrt beide Laeufe (`V1_kausal`, `V1_batch`) und prueft beide mit `< 1e-6`. Der Scan-Abgleich laeuft fuer `ADAPTER_V019` **und** `ADAPTER_V019_KAUSAL`. | 54.4 Regel 19/20, `tmp_png_aug_sichttest.py` |

"""

assert src.count(AN57) == 1, src.count(AN57)
assert src.count(AN58) == 1, src.count(AN58)
assert "54.4 Hindsight" not in src, "bereits gepatcht"

out = src.replace(AN57, SEC_544 + AN57)
out = out.replace(AN58, SEC_551 + AN58)
assert out != src
P.write_text(out, encoding="utf-8", newline="\n")

_b = P.read_bytes()
print(f"OK  {P.name}: {len(src):,} -> {len(out):,} Zeichen")
print(f"CRLF={_b.count(chr(13).encode())}  LF={_b.count(chr(10).encode())}")
print(f"SHA256 neu: {hashlib.sha256(_b).hexdigest()}")
