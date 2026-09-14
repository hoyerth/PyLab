# -*- coding: utf-8 -*-
"""Stufe 5.3, Phase 4: §75 in die Spiegelspez + H19 in den Handoff.

Zeilenenden werden erhalten (Spez = LF, Handoff = CRLF).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEZ = ROOT / "reports" / "h2_phasenregime" / "H2_PHASENREGIME_ADAPTER_SPEZ.md"
HAND = ROOT / "test" / "SESSION_HANDOFF.md"

S75 = """
---

## Addendum v0.24 / §75 — Kausalitaets-Trennung, Datenkante, Concurrency und ZP-5-Vorlauf

### §75.0 Geltung und Abgrenzung

Dieser Paragraph ist der geschlossene Regelwerk-Vorgang zu Stufe 5
(ZP-5-Refaktor, E-34n/19). Er normiert vier bereits im Code arretierte
Sachverhalte und schliesst die in §74.9 als offen ausgewiesenen Punkte:
(1) Kausalitaets-Trennung, (2) Datenkante (Zeitbasis), (3) Concurrency-
Schranke, (4) ZP-5-Vorlauf und Master-Kapselung. Er beschreibt die arretierte
v0.24; er aendert KEINE Engine-Funktion und KEINEN Sollwert.

### §75.1 Kausalitaets-Trennung (ein Vertrag, zwei Wahrheiten)

- **V1_kausal ist der Primaersatz.** 23 Trades / **+85.577150 R**
  (H1 8/+38.919584 | H2 15/+46.657566). LIVE-faehig, weil saemtliche
  Segment-Etiketten ausschliesslich aus der Vergangenheit abgeleitet werden
  (Bestaetigungsbar `a + min_bars - 1`).
- **V1_batch bleibt Hindsight.** 24 Trades / +88.116626 R (H1 8/+38.919584 |
  H2 16/+49.197042). NICHT handelbar; dient nur als Provenienz-/Dampfungs-
  Ausweis der rueckwirkenden Hysterese (MIN_BARS = 77).
- Die Differenz ist EXAKT ein Artefakt-Trade: **bar 1211 entry 1214 SHORT
  K76 +2.53948 R**. Er existiert nur, weil das Batch-Etikett „rueckwaerts“
  verschmilzt.
- **Keine parallelen Pruefwelten:** der kausale Lauf zieht sein Fenster aus
  `ADAPTER_V019_KAUSAL`, der Batch-Lauf aus `ADAPTER_V019`. Beide laufen
  ueber dieselbe Segmentmaschine und denselben Renderer-Pfad.
- **Darstellung:** Hindsight-Artefakte werden nur gedaempft gezeichnet
  (§54.4); gehandelt wird ausschliesslich der kausale Satz.

### §75.2 Datenkante (Zeitbasis-Kanon)

- Einzige Rechenbasis ist die **Broker-Kerzen-Zeit (BKZ)** =
  `time AT TIME ZONE 'UTC'` (docs/ZEITBASIS_KANON.md).
- **`box_end` ist KEINE Bar-Konstante**, sondern die dynamische Kalenderkante
  `searchsorted(ts_bkz, \"2026-08-19\")` (AUG = **644**).
- Der Grenztrade K1@640 (r = -1.000000) partitioniert nach H1 (8 Trades),
  nicht nach H2.
- Keine Europe/Berlin- oder Europe/Budapest-Projektion in `WHERE`,
  `searchsorted`, `floor` oder Auswertungslogik; die Anzeige-Dublette ist
  reine Beschriftung.

### §75.3 Concurrency-Schranke

- `max_gleichzeitig_je_richtung = 3` (0 = aus), symmetrisch fuer LONG/SHORT.
- Die Schranke greift im **Regel-Loop** UND im **G4-Reclaim-Pfad** (der
  frueher direkt an `setups` hing); der G4-Bypass ist geschlossen.
- **Bindetest (maschinell):** T1 — der 4. gleichzeitige Trade wird bei Cap 3
  blockiert, kein Ueberlapp/andere Richtung zaehlen nicht; T3 — Cap 2
  entfernt end-to-end `bar 981 entry 982 SHORT K73 +2.69549` (22 / +82.881663).
- Auf AUG ist Cap 3 **inert** (`concurrency_blockiert == 0`). Belegt ist die
  Wirksamkeit der Schranke, nicht die optimale Hoehe; diese ist erst im
  Zweitfenster S1/S2 belastbar.

### §75.4 ZP-5-Vorlauf und Master-Kapselung (Stufe 5, E-34n/19)

- Der Kantenlaeufer-Durchstich **ZP-5(D)** (E-34n/10+11) ist ab Stufe 5
  **kein Quelltext-Patch** im `_se_trades`-Rumpf mehr, sondern die
  eigenstaendige, zustandsfreie Renderer-Funktion
  `erweitere_segmentwand_dochte(...)`.
- **Signatur (6 Argumente, keine impliziten Modul-Globals):**
  `(scan_copy: dict, hook: PhasenRegimeAdapter,
  cfg: StraightEdgeHarnessKonfiguration, hi: np.ndarray, lo: np.ndarray,
  ueb_fn: Callable[[int], float]) -> None`.
- **Ausfuehrung ausschliesslich in `_lauf()`** auf der laufeigenen
  `deepcopy` (`sc_copy`) unmittelbar VOR `engine._se_trades()`. Das
  Master-Objekt `scan` wird NIE mutiert; `verifiziere_gegen_scan()` und der
  ZP-5-Geometriewaechter bleiben stabil.
- **Doppel-Gatung:** Quelltext-Stufe `KONF.mode == \"V019\"` UND Laufzeit-Gate
  `len(hook.segmente) > 1`. V0 und V1_basis (DEFAULT_ADAPTER, 1 Segment)
  bleiben inert.
- **Invarianten:** `b0 = basis_bei(seg.start_bar)` ist TRAGEND (nicht die
  statische `.basis`); untere Schwelle `cfg.touch_band_pct`, obere Schwelle
  `ueb_fn` (segment-lokale 0.80) — kein Literal; P9 ist ueber sein
  Boden-Literal ausgenommen.
- **ZP-Patchset = VIER Regeln** (`A_UEB1`/`A_VC`/`A_M6L`/`A_SB`). Der
  frueher fuenfte Eintrag `A_KL_DOCHT` ist geloescht.
- **Bit-Identitaets-Gate (Stufe 5.2):** Inline-`A_KL_DOCHT` gegen
  Vorlauf-Funktion = 100 % identisch auf **Objekt-Ebene** (wicks +
  schlaf_windows + status je kid) und **Trade-Ebene** (23 / +85.577150 R,
  saemtliche `r/r1/r2/grund1/grund2`, stats, Endzustand) -> Extraktion
  zulaessig.
- **Byte-Identitaet (Stufe 5.3):** die fuenf V019-PNGs und das Lauf-Protokoll
  bleiben SHA256-identisch zu E-34n/18 (§75.6) -> reiner Refaktor, kein
  Alpha- oder Darstellungseingriff.

### §75.5 Realwert-Kennzahlen (b)/(a)

- `R_realisiert (b)` = **+75.677008 R** (ENDE-Schenkel genullt);
  `R_untergrenze (a)` = **+75.588050 R** (19 Trades, ENDE entfernt).
- `_SESetup` traegt `grund2: str` und `r1/r2: float` (abwaertskompatibel;
  Defaults `\"\"`/`0.0`).
- Die 78.2er-Zahlen aus E-34n/16 waren **Batch-Vormerkungen** fuer den
  24er-Satz; massgeblich im kausalen Satz sind (b)/(a).

### §75.6 Artefakte (SHA256; `test/` = gitignored → urkundlich)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` (UNVERAENDERT) | 200.433 | `53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006` |
| `test/tmp_png_aug_sichttest.py` (Stufe 5.3) | 123.343 | `500b55762001d6667af3d977324c81eb4ecbceacc2fa0d8b62c36c7e383250e0` |
| `test/_chk_v019_kausal_vergleich.py` (synchron) | 14.828 | `f260d252befba5774af4a996b3a36466bff4710e18162aa63c30c4ddaf96c276` |
| `test/_chk_v019_zp5_extrahieren.py` (5.2-Beleg) | 10.208 | `034748264bf77e6155bdbf3ca1194f6660af8bb2b4541c517c9f0073c425dd02` |
| `test/aug_sichttest_v019_01_gesamt.png` | 2.159.332 | `0f8ac94b07cb10199f380012915174301f88441fde0b81f32f3d73c38d710ed3` |
| `test/aug_sichttest_v019_02_h1_box.png` | 896.312 | `7189fa55f0c940855bc3bfa7c94e493f06652c5fd977869651ef4c38afa0ca2f` |
| `test/aug_sichttest_v019_03_h2_phasen.png` | 1.797.691 | `881230f2cde0e92ee920944e084d3453fd9af20164109af0a5f9b12abc23b7b8` |
| `test/aug_sichttest_v019_04_p9_regime.png` | 1.196.384 | `c0fb552afac5e0321c484010914fc8a799544abc79f1d17a5f10bd9e26dacfe2` |
| `test/aug_sichttest_v019_05_kantenkarte.png` | 2.152.873 | `743f06cb88a72f7af1093dcffee6727ba5b5b8ea45c73545549eadaa523cbbbc` |
| `test/tmp_png_aug_sichttest_v019_out.txt` | 5.462 | `e1314950ef6479b594fe194a4902621d8a4aae49e61a19afbf3bd8951cf8a6f7` |

Alle fuenf PNGs und das Protokoll sind **byte-identisch zu E-34n/18** (vgl.
Handoff H18.9). Der Renderer-Lauf endete mit exit 0; alle Fail-Loud-Asserts
bestanden.
"""

H19 = """## Phase 3 / E-34n/19 (2026-09-12, ag) - STUFE 5 ARRETIERT (5.1-5.3): ZP-5-VORLAUF EXTRAHIERT, §75 NORM

Auftrag (Anwender): Stufe 5 in drei Schritten -- 5.1 Audit der strukturellen
Koppelung, 5.2 isolierter Bit-Identitaets-Trockenlauf, 5.3 scharfer Einbrand
(Extraktion + §75 + Neubeurkundung) in EINEM geschlossenen Vorgang.

Bindende Anwender-Antworten (Interview):
 1. Gate-Freigabe: 100 % Bit-Identitaet -> Extraktion zulaessig, sonst
    verworfen.
 2. Signatur (2a): 6 Argumente, `ueb_fn` EXPLIZIT uebergeben -- keine
    impliziten Modul-Globals.
 3. Harness im selben Zug synchron (keine parallelen Pruefwelten).
 4. §75 + Handoff in EINEM Commit (Code und Regelwerk untrennbar).

### H19.1 - Vorbedingung und Anker

Vorbedingung: Handoff-SHA (E-34n/18)
`10f70934b506f03ee24fe245c4197d0886bfdd8491e9c4333ea546f752ab135f`
(397.384 B / 7.068 Zeilen CRLF) - vor dem Append binaer geprueft.

| Anker | vor Stufe 5 | nach Stufe 5 |
|---|---|---|
| `test/tmp_png_aug_sichttest.py` | 120.955 B / `341253edb402f45b651c7b829a6fd2d939a4e5e1c68bd9199a6a5141931aa1f1` | 123.343 B / `500b55762001d6667af3d977324c81eb4ecbceacc2fa0d8b62c36c7e383250e0` |
| `test/tmp_kanten_engine_replay.py` | 200.433 B / `53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006` | **UNVERAENDERT** |

### H19.2 - Phase 5.1: Struktureller Befund

ZP-5 war kein kontinuierlicher Schleifencode, sondern ein einmalig wirkender
Block am Anfang von `_se_trades`, der die Kantenobjekte (`wicks`,
`schlaf_windows`, `status`) mutiert. Diese Mutation ueberlebte nur, weil der
Renderer-Harness in `_lauf()` vor jedem Lauf ein isoliertes `copy.deepcopy`
zieht. Eine globale Vorab-Ausfuehrung auf dem Master-Scan haette das
Master-Objekt vergiftet und die Scan-Verifikation gebrochen. Ergebnis: die
Funktion muss INNERHALB von `_lauf()` auf der deepcopy laufen.

### H19.3 - Phase 5.2: Bit-Identitaets-Trockenlauf (read-only)

`test/_chk_v019_zp5_extrahieren.py` (10.208 B /
`034748264bf77e6155bdbf3ca1194f6660af8bb2b4541c517c9f0073c425dd02`)
verglich zwei Wege auf je eigenen deepcopy-Instanzen (ADAPTER_V019_KAUSAL):
A = arretierter Inline-Patch `A_KL_DOCHT`, B = Vorlauf-Funktion.

| Ebene | Ergebnis |
|---|---|
| OBJEKT: wicks + schlaf_windows + status je kid (73 Kanten, 297 Wicks) | **0 Abweichungen** |
| ERGEBNIS: A | 23 / +85.577150 R |
| ERGEBNIS: B (auf Patchset OHNE ZP-5) | 23 / +85.577150 R |
| Trade-Signaturen (`bar/kid/r/r1/r2/grund1/grund2`) | **bit-identisch** |
| Engine-`stats` + Endzustand der Kanten | **identisch** |

Verdikt: `GESAMT: OK` -> Extraktion ist bit-identisch, Einbrand freigegeben.

### H19.4 - Phase 5.3: Einbrand (Renderer)

`test/_tmp_s53_patch.py` (6.465 B), 3 assert-gesicherte Ersetzungen:

 1. Paar 5 (`A_KL_DOCHT`, ~53 Quelltextzeilen) aus
    `_wende_zielzonen_patches_v019()` geloescht -> Patchset = 4 ZP-4-Regeln.
 2. Docstring auf den 4-Regel-Stand harmonisiert.
 3. `erweitere_segmentwand_dochte()` mit 6-Argument-Signatur und Type Hints
    verankert; `_lauf()` ruft sie auf `sc_copy` VOR `engine._se_trades()`
    (Gate: `KONF.mode == \"V019\" and len(hook.segmente) > 1`).

`py_compile` OK.

### H19.5 - Harness-Synchronisation

`test/_chk_v019_kausal_vergleich.py` laedt die Vorlauf-Funktion jetzt
ebenfalls per AST aus dem Renderer (`from __future__ import annotations` wird
vorangestellt) und ruft DIESELBE Funktion in `_lauf()` auf. Ergebnis
unveraendert:

| Lauf | n | R |
|---|---|---|
| A arretiert (Kontrolle) | 24 | +88.116626 |
| B kausal | 23 | +85.577150 |
| C kausal + ZP-5-Fenster alt | 23 | +85.577150 |

### H19.6 - Verifikationslauf und Byte-Identitaet

`python test/tmp_png_aug_sichttest.py --mode V019` -> **exit 0**, alle
Fail-Loud-Asserts bestanden. Protokoll unveraendert:

```
Baseline V0    : 14 Trades / +42.450970 R  (H1 8/+38.919584 | H2 6/+3.531386)
V1_basis (v0.1): 14 Trades / +47.815697 R
V1_kausal (LIVE, primaer): 23 Trades / +85.577150 R  (H1 8/+38.919584 | H2 15/+46.657566)
V1_batch (HINDSIGHT)     : 24 Trades / +88.116626 R  (H1 8/+38.919584 | H2 16/+49.197042)
```

**Alle fuenf PNGs UND das Protokoll sind SHA256-identisch zu E-34n/18**
(vgl. H18.9). Die in H18.11 erwartete „SHA-Zeilenänderung“ ist
gegenstandslos: die Engine wurde NICHT angefasst, und die PNGs tragen nur
`ENGINE_SHA[:16]` (unveraendert `53f28e1b...`). Ergebnis ist ein reiner
Refaktor ohne jede sichtbare Aenderung.

### H19.7 - Normierung §75

`reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` wurde um
`Addendum v0.24 / §75` ergaenzt (§75.0..§75.6): Kausalitaets-Trennung,
Datenkante, Concurrency, ZP-5-Vorlauf/Master-Kapselung, Realwert-Kennzahlen
(b)/(a), Artefakte. Damit ist der in §74.9 offen ausgewiesene
Paragraph-75-Vorgang geschlossen.

### H19.8 - Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/tmp_png_aug_sichttest.py` | 123.343 | `500b55762001d6667af3d977324c81eb4ecbceacc2fa0d8b62c36c7e383250e0` |
| `test/_chk_v019_kausal_vergleich.py` | 14.828 | `f260d252befba5774af4a996b3a36466bff4710e18162aa63c30c4ddaf96c276` |
| `test/_chk_v019_zp5_extrahieren.py` | 10.208 | `034748264bf77e6155bdbf3ca1194f6660af8bb2b4541c517c9f0073c425dd02` |
| `test/_tmp_s53_patch.py` | 6.465 | `460a93a44a19aa07c9493175d8c48bf5fb83d367ee1dbc920c177a7e4f8ec7ec` |
| `test/tmp_kanten_engine_replay.py` (unveraendert) | 200.433 | `53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006` |

PNG-/Protokoll-SHA256 siehe §75.6 (byte-identisch zu H18.9).

### H19.9 - Konsequenzen und offene Punkte

**Re-Pin entfaellt:** Die Engine ist unveraendert (`53f28e1b...`). Die
H18.11-Prognose „Stufe 5 aendert die Engine -> Re-Pin zwingend“ ist damit
gegenstandslos; der Pin bleibt gueltig. Best-Case eingetreten: reiner
Refaktor, PNGs byte-identisch.

**Konsumiertes Artefakt:** `test/_chk_v019_zp5_extrahieren.py` las Paar 5
noch aus dem Renderer-Patchset. Nach dem Einbrand existiert `A_KL_DOCHT`
nicht mehr, der Trockenlauf-Beleg ist damit historisch konsumiert und wird
NICHT nachgefuehrt (kein Parallelpfad). Der synchrone Pfad ist der Harness
H19.5.

**Offen:** Zweitfenster S1/S2 (Concurrency-Hoehe belastbar, Kausalitaets-
Robustheit); aus E-34n/14: Q1 Bilanzierung (a)/(b) und Q2 Schranke.
"""

# --- Spez: LF, anhaengen
spez_txt = SPEZ.read_text(encoding="utf-8")
assert "## Addendum v0.24 / §75" not in spez_txt, "§75 schon vorhanden"
SPEZ.write_text(spez_txt + S75, encoding="utf-8", newline="")

# --- Handoff: CRLF, anhaengen
hand_txt = HAND.read_text(encoding="utf-8")
assert "E-34n/19" not in hand_txt, "H19 schon vorhanden"
hand_new = hand_txt.rstrip("\r\n") + "\r\n\r\n" + \
    H19.replace("\n", "\r\n").rstrip("\r\n") + "\r\n"
HAND.write_text(hand_new, encoding="utf-8", newline="")

print("OK  §75 an Spiegelspez angehaengt")
print("OK  H19 an Handoff angehaengt")
