# -*- coding: utf-8 -*-
"""Append E-34n/18 (Stufe 4: 4a+4b) an test/SESSION_HANDOFF.md.

ASCII-only, CRLF-erhaltend, mit Vorab-SHA-Assert auf den E-34n/17-Stand.
"""
import hashlib

P = r"F:\Python\PyLab\test\SESSION_HANDOFF.md"
PRE_SHA = "51cb4b99a57ce6a4ff48c6135d61b5154525dd229c0ad3bf27989cfdba44cbc9"
PRE_BYTES = 386419

SECTION = """
## Phase 2 / E-34n/18 (2026-09-12, ag) - STUFE 4 ARRETIERT (4a+4b): REALWERT-KENNZAHLEN, CONCURRENCY-SCHRANKE, G4-BYPASS GESCHLOSSEN

Auftrag (Anwender): Stufe 4 als BATCH -- Realwert-Metrik aus den
`_SESetup`-Schenkeln (4a) und Concurrency-Schranke Cap >= 3 je Richtung
(4b) in EINEM Engine-Patch, danach ein Re-Pin und eine PNG-Neuarretierung.

Bindende Anwender-Antworten (Interview):
 1. Batch (4a+4b) mit genau EINEM Engine-SHA und EINER PNG-Arretierung.
 2. `_SESetup`-Erweiterung freigegeben (`grund2`/`r1`/`r2`, abwaertskompatibel).
 3. 78.2er-Werte sind VORMERKUNGEN (24er-Batch) -> erst gegen die gemessene
    kausale Dekomposition pruefen. 4a-Regel: keine Optimierung von Verlierern.
 4b-Regel: (2a) Kanten-Ereignis-Regel FALLEN LASSEN; (3b) Cap >= 3 nur mit
    synthetischem Bindetest.

### H18.1 - Vorbedingung und Anker

Vorbedingung: Handoff-SHA
`51cb4b99a57ce6a4ff48c6135d61b5154525dd229c0ad3bf27989cfdba44cbc9`
(386.419 B / 6.856 Zeilen CRLF, aus E-34n/17) - vor dem Append binaer
verglichen.

| Anker | vor Stufe 4 | nach Stufe 4 |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` | 197.093 B / `df92aab57ccded613611b613b6890cc61d49852e123afbd2531c4ead36f60e3c` | 200.433 B / `53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006` |
| `test/tmp_png_aug_sichttest.py` | 119.081 B / `6844f3ab4e6ff9ea6152c8e6035727434b13fbd628609a6f01ca2f843a8eaaad` | 120.955 B / `341253edb402f45b651c7b829a6fd2d939a4e5e1c68bd9199a6a5141931aa1f1` |

### H18.2 - Phase 1: Trockenlauf (read-only) - Schenkel-Dekomposition

`test/_chk_v019_stufe4_trockenlauf.py`, kausaler 23er-Satz, Zuordnung 23/23,
`w1 = w2 = 0.5` (`tp1_anteil_pct = 50.0`):

| Metrik | gemessen (kausal) | Vormerkung | Delta |
|---|---|---|---|
| `R_brutto` | **+85.577150** | - | - |
| `R_realisiert (b)` | **+75.677008** | +78.216484 | **-2.539476** |
| `R_untergrenze (a)` | **+75.588050** (19) | +78.127525 | **-2.539476** |

Die Differenz ist EXAKT der Hindsight-Trade (Punkt 3 der Antworten belegt):
`75.677008 + 2.539476 = 78.216484`. Die 78.2er-Zahl war eine **Batch-
Vormerkung** (24er-Satz); im kausalen Satz gilt 75.677008/75.588050.

**Vier ENDE-Trades (exakte Schenkel):**

| Bar | Entry | Kante | Richt. | grund1 | r1 | grund2 | r2 | r |
|---|---|---|---|---|---|---|---|---|
| 1075 | 1077 | K62 | LONG | TP1 | +0.02171 | ENDE | +2.92982 | +1.47577 |
| 1172 | 1173 | K82 | LONG | TP1 | +0.15621 | ENDE | **+10.84828** | +5.50224 |
| 1272 | 1273 | K73 | SHORT | ENDE | +1.25468 | ENDE | +1.25468 | +1.25468 |
| 1280 | 1281 | K76 | SHORT | ENDE | +1.75641 | ENDE | +1.75641 | +1.75641 |

Der Mentor-Hinweis (K82@1172 mit +10.8483 offener zweiter Haelfte) ist
exakt bestaetigt.

### H18.3 - Phase 1: Kanten-Ereignis-Regel - WIDERLEGT, fallen gelassen

In-Memory-Variante (12-Bar-Sperre ersetzt durch "frischer bestaetigter
Touch"):

| Lauf | n | R | H1 | H2 |
|---|---|---|---|---|
| **Ist** (12-Bar-Sperre) | 23 | +85.577150 | 8 / +38.919584 | 15 |
| Variante (frischer Touch) | 20 | **+50.662485** | 6 / **+9.764486** | 14 |

Entfallen: `242 K20 +3.92512`, `529 K20 +8.35994`, `564 K20 +15.87003`,
`1020 K67 +3.00316`, `1280 K76 +1.75641`. Neu: `531 K20 -1.00000`,
`771 K51 -1.00000`.

**Verdikt (Anwender-Entscheid 2a):** Der Ersatz vernichtet -34.914 R und
bricht H1 um 29.155 R ein (K20-Trendfolge stirbt). Die arretierte 12-Bar-
Sperre (`cfg.retest_zyklus_bars = 12`) bleibt UNANGETASTET. Kein Herumbasteln
an Varianten (2b/2c). Es wurde KEINE dieser Varianten im Produktivcode
verankert.

### H18.4 - Phase 1: Concurrency-Messung

Maximal gleichzeitig offene Positionen je Richtung (Ist-Satz):
SHORT 16 Trades -> **max 3** (Bar 982: K67@903, K67@980, K73@981, alle
Exit 991); LONG 7 -> max 2. **Cap >= 3 ist auf AUG inert** -> ohne
Negativtest eine tote Behauptung (Anwender-Entscheid 3b: Bindetest).

### H18.5 - Phase 2: Engine-Patch (6 Anker + G4-Nachtrag)

`_append`-Skript `_tmp_e34n17_patch_engine_stufe4.py` (6 assert-gesicherte
Anker):

 1. `max_gleichzeitig_je_richtung: int = 3` (letztes Config-Feld; 0 = aus).
 2. `_SESetup`: `grund2: str = ""`, `r1: float = 0.0`, `r2: float = 0.0`
    (am Ende, kollisionsfrei) + neuer Helfer
    `_konkurrenz_aktiv(setups, richtung, entry_bar, exit1_bar, exit2_bar) -> int`.
 3. `stats["concurrency_blockiert"] = 0`.
 4. Guard im Regel-Loop: `_offen = _konkurrenz_aktiv(...)`;
    `if _offen > cfg.max_gleichzeitig_je_richtung: stats[...] += 1; continue`.
 5. Durchreichung `grund2/r1/r2` an der Regel-Konstruktion.
 6. Durchreichung an der G4-Konstruktion.

**G4-Bypass geschlossen** (`_tmp_e34n17_patch_engine_g4cap.py`): Der
G4-Reclaim hing direkt an `setups` und umging die Schranke. Der Guard ist
jetzt identisch im G4-Pfad. Auf AUG folgenlos (einzelner LONG in P9).

**Zwischenfall (transparent):** Der C6-Anker endete auf
`int(_tr_g4.exit2_bar)))` -- das `int(...)` trug einen Klammerabschluss bei.
Die woertliche Ersetzung erzeugte dadurch eine Klammer zu viel
(`SyntaxError`). Beim Reparieren zerstoerte ein Textmodus-Schreibvorgang die
CRLF; binaer wiederhergestellt. Endstand geprueft: 4.663 CRLF, `py_compile`
OK. **Lehre:** Klammerbilanz vor dem Schreiben pruefen.

Zwei Engine-SHA-Staende in dieser Stufe:
`da195c91...` (4a+4b, ohne G4) -> `53f28e1b...` (mit G4-Nachtrag, FINAL).
Der Zwischenstand wurde nie gerendert.

### H18.6 - Phase 2: Bindetest der Schranke (T1/T2/T3)

`test/_chk_v019_cap_bindetest.py`:

| Test | Inhalt | Ergebnis |
|---|---|---|
| **T1 Einheit** | echter 4. Trade: 3 synthetisch offene + Kandidat | `_konkurrenz_aktiv == 4` -> Cap 3 blockiert. Gegenproben: kein Ueberlapp = 1, andere Richtung = 1 |
| **T2 Positiv** | AUG, Default-Cap 3 | 23 / +85.577150, `concurrency_blockiert == 0` (inert) |
| **T3 Negativ** | AUG, Cap 2 (End-to-End) | `concurrency_blockiert == 1`, 22 / +82.881663 -> blockiert `bar 981 entry 982 SHORT K73 +2.69549` |

Damit ist die Schranke NICHT mehr unbelegt: sie greift bei der 3. Position
unter Cap 2 und bei der 4. unter Cap 3, bleibt unter Cap 3 aber inert.

### H18.7 - Phase 2/3: R_realisiert end-to-end (ohne Instrumentierung)

`test/_chk_v019_r_realisiert.py` liest `grund1/grund2/r1/r2` direkt aus den
`_SESetup`-Objekten (kein String-Filter, kein Monkeypatch -- die Option
"verifiziere OHNE"):

| Kennzahl | Ist | Soll |
|---|---|---|
| `R_brutto` | +85.577150 | +85.577150 |
| `R_realisiert (b)` | +75.677008 | +75.677008 |
| `R_untergrenze (a)` | +75.588050 | +75.588050 |
| (a)-Menge | 19 | 19 |
| ENDE-Trades | 4 | 4 |

`test/_chk_v019_dual_kausal.py`: **GESAMT: OK** (23 / +85.577150, H1
8 / +38.919584, entfernt genau `[(1211, 76)]`).
`test/_chk_e34n17_engine.py`: `box_end_bar = 644`, `n = 1288`, 59 edges +
14 seeds.

### H18.8 - Phase 3: Renderer-Synchronisation (Re-Pin + Reporting)

`_tmp_e34n17_patch_renderer_stufe4.py` (6 Anker):

 1. Re-Pin `_V019_ENGINE_SHA_SOLL` -> `53f28e1b...` (Zero-Trust-Anker).
 2. Neue Felder `ziel_r_realisiert`, `ziel_r_untergrenze`,
    `ziel_trades_untergrenze` (Defaults 0.0/0.0/0 -> V01..V018 inert) + Doku.
 3. `KONFIGURATION_V019`: 75.677008 / 75.588050 / 19.
 4. Harte Fail-Loud-Asserts (`< 1e-6`) im V019-Zweig, typisiert aus den
    `_SESetup`-Feldern.
 5. Protokollzeile.

Der Re-Pin schuetzt sich selbst: Zwischen Engine-Nachtrag und Re-Pin brach
`--mode V019` korrekt mit exit 1 ab
(`erfordert SHA df92aab57ccded61..., geladen wurde da195c918dd7ae01...`).

### H18.9 - Phase 4: PNG-Neuarretierung (V019, Engine 53f28e1b...)

| PNG | Bytes | SHA256 | vorher (E-34n/17) |
|---|---|---|---|
| `test/aug_sichttest_v019_01_gesamt.png` | 2.159.332 | `0f8ac94b07cb10199f380012915174301f88441fde0b81f32f3d73c38d710ed3` | 2.159.206 |
| `test/aug_sichttest_v019_02_h1_box.png` | 896.312 | `7189fa55f0c940855bc3bfa7c94e493f06652c5fd977869651ef4c38afa0ca2f` | 896.312 (**identisch**) |
| `test/aug_sichttest_v019_03_h2_phasen.png` | 1.797.691 | `881230f2cde0e92ee920944e084d3453fd9af20164109af0a5f9b12abc23b7b8` | 1.797.180 |
| `test/aug_sichttest_v019_04_p9_regime.png` | 1.196.384 | `c0fb552afac5e0321c484010914fc8a799544abc79f1d17a5f10bd9e26dacfe2` | 1.196.202 |
| `test/aug_sichttest_v019_05_kantenkarte.png` | 2.152.873 | `743f06cb88a72f7af1093dcffee6727ba5b5b8ea45c73545549eadaa523cbbbc` | 2.152.787 |
| Protokoll `test/tmp_png_aug_sichttest_v019_out.txt` | 5.462 | `e1314950ef6479b594fe194a4902621d8a4aae49e61a19afbf3bd8951cf8a6f7` | `32940f42...` |

**Panel 02 ist byte-identisch** (`7189fa55...`). Panels 01/03/04/05 aendern
sich ausschliesslich ueber die neue `ENGINE_SHA[:16]`-Zeile. Trades und
Sollwerte bit-identisch. Lauf exit 0, alle Asserts bestanden.

**Protokollzeilen (neu):**

```
V1_kausal (LIVE, primaer): 23 Trades / +85.577150 R  (H1 8/+38.919584 | H2 15/+46.657566)  <- PRIMAER (live-faehig)
V1_batch (HINDSIGHT)     : 24 Trades / +88.116626 R  (H1 8/+38.919584 | H2 16/+49.197042)  <- NICHT handelbar
  Hindsight-Delta: +2.539476 R aus 1 Artefakt-Trade(s) -- Hysterese 77, nicht handelbar
R_realisiert   : brutto +85.577150 R | (b) +75.677008 R (ENDE-Schenkel genullt) | (a) +75.588050 R (19 Trades, ENDE entfernt)
```

### H18.10 - Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/_tmp_e34n17_patch_engine_stufe4.py` | 7.290 | `959d566b5fa8b363fe06dec9dba8dae4289c010bd7ac452d4b68844666436fa3` |
| `test/_tmp_e34n17_patch_engine_g4cap.py` | 2.551 | `5e0d1ee6eebb0bc061b2d4cdc638cc28949984d896d13ef840a7eeb30c757d05` |
| `test/_tmp_e34n17_patch_renderer_stufe4.py` | 5.319 | `bb9574eeb0afa14ecaef50e6d889886a08b4972343cafe751a8868df98499f87` |
| `test/_chk_v019_stufe4_trockenlauf.py` | 9.828 | `c69fe2f7962a33c06c4339003165fff8ea6dd140d70e9382a299a1720bf048af` |
| `test/_chk_v019_cap_bindetest.py` | 5.101 | `5054d3f69b1d04d3ef829d88e10f8eee8154be6567b91644abeda2e866a96c03` |
| `test/_chk_v019_r_realisiert.py` | 3.485 | `852f66cf25f3714dcc07dc929409cee9cbd7a5375814fcc1e55587cff3e956d3` |

### H18.11 - Konsequenzen und offene Punkte

**Sperrwirkung geschaerft:** Der Pin `_V019_ENGINE_SHA_SOLL` steht jetzt auf
`53f28e1b...`. Stufe 5 (ZP-5-Refaktor) aendert die Engine -> Re-Pin + PNG-
Neuberechnung zwingend.

**Cap-Inertheit auf AUG:** Die Schranke bindet im August nie. Ihre Wirkung
ist durch T3 (Cap 2) und T1 (4. Trade) maschinell belegt, aber die Aussage
"Cap >= 3 ist die richtige Schwelle" ist erst im Zweitfenster (S1/S2)
belastbar. Bis dahin: dokumentierte Sicherung, kein Wirkungsnachweis.

**Offener Verweis:** Abschnitt 54.4 Regel 15-20 und 55.1 (S11-S13) stehen in
der Spiegelspez (E-34n/17); die Realwert-Kennzahlen (b)/(a) sind dort noch
NICHT normiert -- Gegenstand des geschlossenen Paragraph-75-Vorgangs nach
Stufe 5 (Anwender-Entscheid A aus E-34n/16).

Unveraendert offen: Stufe 5 (ZP-5-Refaktor + Paragraph 75), Zweitfenster
S1/S2; aus E-34n/14: Q1 Bilanzierung (a)/(b) und Q2 Schranke.
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
