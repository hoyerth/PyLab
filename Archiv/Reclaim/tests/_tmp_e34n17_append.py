# -*- coding: utf-8 -*-
"""Append E-34n/17 (Stufe 3) an test/SESSION_HANDOFF.md.

ASCII-only, CRLF-erhaltend, mit Vorab-SHA-Assert auf den E-34n/16-Stand.
"""
import hashlib

P = r"F:\Python\PyLab\test\SESSION_HANDOFF.md"
PRE_SHA = "12fb5eb57e541e0d9525bd824c06b2d6b892b219be1612bfb6ab25995aa18f34"
PRE_BYTES = 377721

SECTION = """
## Phase 2 / E-34n/17 (2026-09-12, ag) - STUFE 3: KALENDERKANTE PARAMETRISIERT (Engine-Erstoeffnung, Neu-Arretierung)

Auftrag (Anwender, Ausfuehrung der Entscheidungsfragen aus E-34n/16):
Das Datums-Literal der Kalenderkante in der Kern-Engine wird durch ein
typisiertes Dataclass-Feld ersetzt; der V019-Renderer-Guard wird von einer
reinen Bar-Pruefung auf einen Zero-Trust-Anker (Soll-Bar + Engine-SHA)
harmonisiert.

Bindende Anwender-Antworten (Interview E-34n/16):

 1. **Anker der V019-Identitaetspruefung:** BEIDES -- (a) deterministischer
    Soll-Bar des AUG-Fensters (644), (b) urkundlicher ENGINE_SHA. Eine
    Pruefung gegen dieselbe ``searchsorted``-Formel waere tautologisch
    (Befund B1) und ist unzulaessig.
 2. **V017/V018-Guards:** unberuehrt; der neue Teilpfad ist strikt in
    ``if KONF.mode == "V019"`` gekapselt (Befund B2: der V017-Rueckweg
    fuehrt ``_tmp_backup_engine_pre_v018.py`` ohne ``box_end_datum``).
 3. **V018-PNGs:** bleiben eingefroren, KEIN Neu-Rendern. V018 ist
    historisch an Engine ``4a576a76...`` gebunden; zum Reproduzieren dient
    der Rueckweg ``--engine test/_tmp_backup_engine_pre_v018.py``.
 4. **V019-Neuarretierung:** JA. Der Produktionssatz wird mit dem neuen
    Engine-SHA neu erzeugt; die fuenf SHA256 werden verbindlich
    dokumentiert.

Regeln: keine UI-/Regressionstests, kein Paragraph 75; Engine-Erstoeffnung
als minimalinvasiver Einzeiler mit neuem SHA-Anker.

### G17.1 - Vorbedingung und Anker

Vorbedingung: Handoff-SHA
`12fb5eb57e541e0d9525bd824c06b2d6b892b219be1612bfb6ab25995aa18f34`
(377.721 B / 6.688 Zeilen CRLF, aus E-34n/16) - vor dem Append binaer
verglichen.

| Anker | vor Stufe 3 | nach Stufe 3 |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` | 196.649 B / `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` | 197.093 B / `df92aab57ccded613611b613b6890cc61d49852e123afbd2531c4ead36f60e3c` |
| `test/tmp_png_aug_sichttest.py` | 118.127 B / `cb302fc7ea80bdf5b30a0de829265587bcceb157cc855c3c776ac2722d15b416` | 119.081 B / `6844f3ab4e6ff9ea6152c8e6035727434b13fbd628609a6f01ca2f843a8eaaad` |

Erstoeffnung der Engine nach dem Praezedenzverfahren Paragraph 73
(V017 -> V018, `4a356765...` -> `4a576a76...`). Die Engine war zuvor ueber
alle Generationen V01..V019 byte-unberuehrt.

### G17.2 - Phase 1: Engine-Patch (box_end_datum)

Neues Feld als LETZTES Feld von `StraightEdgeHarnessKonfiguration`
(kollisionsfrei; die Klasse wird ausschliesslich zero-arg konstruiert -
Engine Z. 2840/3022, Renderer Z. 576):

```python
box_end_datum: str = "2026-08-19"
```

Genau EINE funktionale Zeile in `_se_scan`:

```diff
-    box_end_bar = int(np.searchsorted(ts_arr, np.datetime64("2026-08-19")))
+    box_end_bar = int(np.searchsorted(ts_arr, np.datetime64(cfg.box_end_datum)))
```

`box_end_bar` wird in `_se_scan` nur berechnet und zurueckgegeben, NICHT im
Scan-Loop konsumiert -> die Scan-Ergebnisse sind von der Quelle unabhaengig.
Der Default haelt jeden historischen Aufruf byte-identisch (AUG = 644).
Diff: +444 B (Feld + 6 Kommentarzeilen + Zeilenaustausch).

### G17.3 - Phase 2: Renderer-Guard harmonisiert

Der frueher alleinige Guard `if KONF.mode == "V019" and box_end != 644`
war eine reine Engine-Identitaetspruefung. Er ist nach der Parametrisierung
nicht mehr selbsttragend (B1). Neuer, gekapselter V019-Block:

```python
_V019_BOX_END_SOLL: Final[int] = 644
_V019_ENGINE_SHA_SOLL: Final[str] = (
    "df92aab57ccded613611b613b6890cc61d49852e123afbd2531c4ead36f60e3c")
if KONF.mode == "V019":
    if box_end != _V019_BOX_END_SOLL:  # deterministischer Soll-Bar
        raise SystemExit(...)
    if ENGINE_SHA != _V019_ENGINE_SHA_SOLL:  # Zero-Trust-Identitaet
        raise SystemExit(...)
```

Der dynamische ``searchsorted``-Abgleich wurde BEWUSST NICHT eingebaut (B1
tautologisch). V017 (`!= 640`) und V018 (`!= 644`) blieben wortgleich.
Diff: +954 B.

### G17.4 - Phase 3: Bit-Identitaets-Gegenprobe (PNG-frei)

`test/_chk_e34n17_engine.py`: `box_end_datum = '2026-08-19'`,
`box_end_bar = 644` (Soll 644), `n = 1288` (Soll 1288), Kanten 59 edges +
14 seeds -> **OK**.

`test/_chk_v019_dual_kausal.py` erneut, gegen die neue Engine:
**GESAMT: OK** - V1_kausal 23 / +85.57715036556571, H1 8 / +38.919584,
H2 15 / +46.657566; Batch-Kontrolle 24 / +88.116626; entfernt genau
`[(1211, 76)]`; Mengengleichheit mit Harness-B; gemeinsame Trades
R-bit-identisch. Die Zahlen sind durch die Engine-Parametrisierung
**bit-identisch** geblieben.

### G17.5 - Phase 4: Fuenf-PNG-Neuarretierung (V019, Engine df92aab5...)

| PNG | Bytes | SHA256 | vorher (E-34n/16) |
|---|---|---|---|
| `test/aug_sichttest_v019_01_gesamt.png` | 2.159.206 | `4a07f1a2a2ac085820ed955f87427b2327b2b97ae48c4c96d8a9c258a1d04116` | 2.158.471 |
| `test/aug_sichttest_v019_02_h1_box.png` | 896.312 | `7189fa55f0c940855bc3bfa7c94e493f06652c5fd977869651ef4c38afa0ca2f` | 896.312 (**identisch**) |
| `test/aug_sichttest_v019_03_h2_phasen.png` | 1.797.180 | `5ff48be72756357fa7dfdb69136726c4587a17d8a31ef629a3c7a9371bd67560` | 1.796.954 |
| `test/aug_sichttest_v019_04_p9_regime.png` | 1.196.202 | `407dadca1ccd14425d9f1f8f0a1002ad234ad9d1f601e0d0fbbd5a1fdf5d799e` | 1.195.846 |
| `test/aug_sichttest_v019_05_kantenkarte.png` | 2.152.787 | `6eced28c95cb7b07c2126d13a2f3d2a2f2a8df22eca2175f254f6faba45bde1a` | 2.152.133 |
| Protokoll `test/tmp_png_aug_sichttest_v019_out.txt` | 5.334 | `32940f42506c106f6b2fd4c3c699975422308969022c80e9756f457fa17889e` | `be93e559...` |

**Panel 02 ist byte-identisch** (`7189fa55...` unveraendert) - Beleg der
Paragraph-71.2-Invariante. Panels 01/03/04/05 aendern sich ausschliesslich
durch die neue ``ENGINE_SHA[:16]``-Zeile im Legendentext (`_zeilen_extra`,
Z. 1774; Aufrufe 1884/2053/2257/2357). Die Trades und alle Sollwerte sind
bit-identisch. **V018 wurde bewusst NICHT neu gerendert** (eingefroren).

### G17.6 - Fail-Loud-Kontrollen

**Negativkontrolle A** (Rueckweg-Engine, box_end 640):
`--mode V019 --engine test/_tmp_backup_engine_pre_v018.py` -> exit 1,
`Modus V019 erfordert den AUG-Soll-Bar 644, geladen wurde box_end=640
(_tmp_backup_engine_pre_v018.py 4a3567659990586c...)`.

**Negativkontrolle B** (Fremd-SHA, box_end 644): Kopie der neuen Engine mit
einem angehaengten Kommentar (SHA `2f175c9e...`) -> exit 1,
`Modus V019 erfordert die Stufe-3-Engine (E-34n/17) SHA df92aab57ccded61...,
geladen wurde 2f175c9e8b227e28...`. Damit ist B1 widerlegt: der SHA-Anker
erkennt eine Fremd-Engine TROTZ box_end 644 (nicht tautologisch).
Die Kopie wurde nach der Kontrolle geloescht.

**Positivkontrolle V017** (Rueckweg-B2): `--mode V017 --engine
test/_tmp_backup_engine_pre_v018.py --probe-praefix _tmp_e34n17_probe_v017_`
-> **exit 0**; box_end=640, V1_aktiv (V017) 17 / +65.835576 R, Delta
+18.019879. Der V017-Pfad ist unberuehrt. Probe-PNGs danach geloescht,
Protokoll `test/_tmp_e34n17_probe_v017_out.txt` (5.087 B /
`c6fd43b740fc89c86df53def857ccc32feed231eed47a618b3965c761bde1482`)
bleibt als Nachweis.

### G17.7 - Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/_tmp_e34n17_patch_engine.py` | 2.168 | `135eac5fda488da71dbe829cee05b7e57a6e9578ac949d25c1dd491962318d10` |
| `test/_tmp_e34n17_patch_renderer_guard.py` | 2.934 | `2fcf043100d70b74f430106e2b940ca0dd638e2d55bd86c827762231ed614bc1` |
| `test/_chk_e34n17_engine.py` | 966 | `787d7eeafe9816c802705301ce69429626b2a1a3ea8bab4801970030ffaebf9a` |
| `test/_tmp_e34n17_probe_v017_out.txt` | 5.087 | `c6fd43b740fc89c86df53def857ccc32feed231eed47a618b3965c761bde1482` |

### G17.8 - Konsequenzen und offene Punkte

**Sperrwirkung:** Jede weitere Engine-Aenderung (Stufen 4/5) entwertet den
Pin `_V019_ENGINE_SHA_SOLL` und verlangt eine Neu-Arretierung (Re-Pin +
PNG-Neuberechnung). Das ist die gewollte Zero-Trust-Folge des Anker-Pins.

**Soll-Bar 644** ist AUG-spezifisch und fuer V019 als Literal gekapselt. Ein
Zweitfenster (S1/S2) muesste einen eigenen Soll-Bar (und ggf. eine
Zweitfenster-Kennung) erhalten -- Gegenstand der spaeteren Stufen, hier
bewusst NICHT vorweggenommen.

**Offene Frage (Spiegelspez):** Paragraph 73 dokumentiert die Engine-
Migration V017 -> V018 als Addendum v0.23. Die jetzige Erstoeffnung
(Stufe 3) ist bisher NUR in diesem Handoff beurkundet. Soll sie zusaetzlich
als eigenes Spiegelspez-Addendum (Engine-Parametrisierung `box_end_datum`,
V019-Guard-Anker) festgeschrieben werden?

Unveraendert offen aus E-34n/16: Stufe 4a/4b (R_realisiert; Cap >= 3),
Stufe 5 (ZP-5-Refaktor + Paragraph 75), Zweitfenster S1/S2; aus E-34n/14:
Q1 Bilanzierung (a)/(b) und Q2 Schranke.
"""


def main() -> None:
    b = open(P, "rb").read()
    assert len(b) == PRE_BYTES, ("Pre-Bytes", len(b))
    h = hashlib.sha256(b).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = SECTION.replace("\r\n", "\n").replace("\n", "\r\n")
    assert txt.isascii(), "SECTION nicht ASCII"
    if not txt.endswith("\r\n"):
        txt += "\r\n"
    with open(P, "ab") as f:
        f.write(txt.encode("ascii"))

    nb = open(P, "rb").read()
    print("pre  bytes", len(b), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(b))


if __name__ == "__main__":
    main()
