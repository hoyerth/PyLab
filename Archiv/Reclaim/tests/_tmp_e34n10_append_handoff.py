# -*- coding: utf-8 -*-
"""Append 'E-34n/10' an test/SESSION_HANDOFF.md (Vorbedingung: SHA 3e2e8d4f...).

Arretiert (a) den Nachweis zum Retest-Bar 1172 (26.08. 17:00, K82), (b) die
Ursache der Additivitaet von Variante D (P1-Bestaetigungs-Lag +2), (c) das
P9-Gate fuer die OBEN-Symmetrie, sowie (d) die Anwender-Entscheidung:
Variante D ist verbindlicher Standard, Freigabe fuer Schritt 1+2 erteilt.
Bewusst ASCII-only.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"
VORBEDINGUNG = "3e2e8d4f6008ab041abfc9aeabb06e807a20ec094a2b1b70953449ef8b55d16e"

roh = HANDOFF.read_bytes()
ist = hashlib.sha256(roh).hexdigest()
print("Vorbedingung SHA256:", VORBEDINGUNG)
print("aktuell           :", ist)
if ist != VORBEDINGUNG:
    print("ABBRUCH: Vorbedingung nicht erfuellt.")
    sys.exit(1)

ABSCHNITT = """
## Phase 2 / E-34n/10 (2026-09-11, ac) - RETEST BAR 1172 (26.08. 17:00, K82): Nachweis, Additivitaets-Ursache, ENTSCHEIDUNG Variante D

Auftrag (Anwender, nach E-34n/9): Klaerung, ob **Bar 1172 (26.08. 17:00 BKZ)**
an *derselben* Kante K82 liegt und dort ein Reclaim entsteht; dazu die
Revisionspruefung von Variante D (warum bleibt `K62@1075` in D erhalten,
waehrend er in B entfaellt?) sowie das Kanten-Audit "nur Bar 1075" und die
Pruefung der OBEN-Symmetrie gegen das P9-Gate. **Rein lesend** (Engine,
Renderer, Adapter unveraendert; ZP-5 nur als Quelltext-Injektion in die
deepkopierte Scan-Kopie, 18 fail-loud Sonden).

### Z1 - Ist 1172 dieselbe Kante? JA - und der Reclaim ist kausal bestaetigt

* **Segmentzugehoerigkeit (gemessen):** 1072-1075 in A1 (1033..1173): **True**;
  1172 in A1: **True**; 1173 (Entry-Bar) in A1: **True**. A1-Boden = **K82**,
  mithin exakt dieselbe deklarierte Segmentwand wie 1072-1075. (A2 beginnt erst
  1174; K82 ist dort ebenfalls Boden, der Uebergang ist nahtlos.)
* **Geometrie Bar 1172 (BKZ 26.08. 17:00, 67.8750 / 67.9420 / 67.4940 /
  67.5980):** Low 67.4940 durchstoesst `basis_bei(1172) = 67.5530` um
  **+0.0873 %** (positives Durchstich-Vorzeichen), Close 67.5980 **>** Basis
  67.5530 -> **`STUFE_1_IN_BAR`**. Entry = Open von Bar 1173 = 67.5890,
  `tp2` = K67-Decke, **r = +5.502241 R**.
* **Deterministischer Trade:** `K82@1172`, `entry_bar = 1173`,
  STUFE_1_IN_BAR - identisch in Variante B und D (E-34n/9 gemessen).
* **Im arretierten ZP-4-Stand passierte an 1172 NICHTS:** Trace
  `WAND_UNREICHT(73) INNEN_TC_OK(62) KANDIDAT(62) RAUM_LONG_ORDNUNG(62)`
  -> K82 war im Pool, aber **schlafend** (`schlaf_windows [(1074, 1174)]`,
  `ist_aktiv_bei(1172) = False`) und mit **`touch_conf(1172) = 2`** unter dem
  Gate `min_touches_handelbar = 3`; der Kandidat war K62, der an
  `RAUM_LONG_ORDNUNG` scheiterte. Der Reclaim an 1172 war also vorhanden, aber
  nicht handelbar.
* **Nach ZP-5:** `schlaf_windows = []` (Segmentwand schlaeft nicht in ihrem
  eigenen Segment) und `touch_conf(1172) = 3` (B: 6) -> K82 wird Wand-Kandidat
  -> **TRADE**.
* **Bedeutung:** Der Einstieg liegt am **Retest**, nicht am Erstkontakt. Die
  institutionelle Sequenz ist damit messbar: akkumulieren/sweepen (1072-1075)
  -> warten -> Retest + Reclaim an 1172 -> Entry 1173. Q3/Q17 blieb unberuehrt.

### Z2 - WARUM Variante D additiv ist: der P1-Bestaetigungs-Lag (+2)

Kern der B/D-Differenz ist **nicht** die Docht-Registrierung, sondern die
kausalen Zugriffsfunktionen der Kante:

```python
def touch_conf(self, k):  # Anzahl Dochte mit  b + 2 <= k
    return sum(1 for b, _ in self.wicks if b + 2 <= k)
```

Ein Docht an Bar `b` zaehlt **erst ab Bar b+2** als bestaetigt (P1: Pivot-Bar+2).
Daraus folgt exakt:

| Variante | K82-Dochte | `tc(1075)` | Kandidat an 1075 | Ergebnis |
|---|---|---|---|---|
| ZP-4 | 1031, 1056, 1172, 1259 | 2 | K62 (`INNEN_TC_OK(62)`) | `K62@1075` **TRADE** |
| B | + 1072, 1073, 1074, 1075 | **4** | **K82** (`INNEN_TC_OK(82)`) | K82 -> `RAUM_LONG_ORDNUNG(82)` -> **Bar verloren** |
| D | + **nur 1075** | **2** | K62 (`INNEN_TC_OK(62)`) | `K62@1075` **TRADE** |

In Variante D ist der Durchstich-Docht 1075 im Moment **seines eigenen Bars**
noch unbestaetigt (1075 + 2 = 1077 > 1075) - die Wand ist dort noch nicht
"reif", K62 behaelt den Trade. Ab Bar 1077 ist 1075 bestaetigt; an **1172**
greift die dann reife Wand (`tc = 3`) und uebernimmt den Retest-Trade.

**Damit ist D strukturell additiv:** der neue Docht wirkt nur *vorwaerts*
(Retest), nie rueckwaerts (eigener Bar). B dagegen "bewaffnet" den Sweep-Bar
rueckwaerts mit 1072/1073 und nimmt K62 den Trade weg. Zusaetzlich gemessen:
in B entsteht an 1074 sogar ein neuer Kandidat **K82** (`STUFE0_KEIN_RECLAIM`),
in D nicht.

### Z3 - Kanten-Audit "nur 1075": die Bandgrenze entscheidet

Mit der am Segmentanfang eingefrorenen Wandbasis `b0 = basis_bei(1033) =
67.5350` und `touch_band_pct = 0.12`:

| Bar | Low | d(b0) % | > Band (0.12) ? | <= 0.80 % ? | Docht in D |
|---|---|---|---|---|---|
| 1072 | 67.4880 | +0.0696 | **False** (Band-Rauschen) | True | nein |
| 1073 | 67.4620 | +0.1081 | **False** (Band-Rauschen) | True | nein |
| 1074 | 67.4550 | **+0.1185** | **False** (0.0015 pp unter der Grenze) | True | nein |
| **1075** | **67.4200** | **+0.1703** | **True** | True | **ja** |

Nur 1075 ist ein *echter* Durchstich (`d > touch_band_pct`) und zugleich
`<= max_sweep_ueberdehnung_pct = 0.80` (Zone). 1072-1074 liegen **im Band** und
sind damit Touch-Rauschen, kein Sweep - genau die Definition, die der Anwender
als "mathematische Definition eines echten Sweeps" benannt hat.

**Sensitivitaets-Warnung (fail-loud dokumentiert):** 1074 liegt mit 0.1185 %
nur **1,25 % unter** der Bandgrenze 0.12. Wird `touch_band_pct` jemals auf
z. B. 0.11 gesenkt, wird 1074 zum Docht; dann zaehlt er an 1075 (1074+2 = 1076
> 1075 -> nein) zwar noch nicht, aber 1072/1073 wuerden nach einer weiteren
Absenkung die Additivitaet von D kippen. Die Additivitaet von D haengt also
an der Bandbreite 0.12 - nicht an einer Zusatzannahme, aber auch nicht an
einem grossen Sicherheitsabstand.

### Z4 - OBEN-Symmetrie und P9-Gate (gemessen)

| Variante | K67.wicks | K77.wicks | P9-Trades (848..1020) |
|---|---|---|---|
| ZP-4 | 873, 881, 904, 980, 1020 | 934, 991, 1000, 1157, 1208, 1227 | 5 / +23.435111 |
| B | 873, 881, 904, 980, 1020 | 934, 991, 1000, 1157, 1208, 1227 | **5 / +23.435111** |
| D | 873, 881, 904, 980, 1020 | 934, 991, 1000, 1157, 1208, 1227 | **5 / +23.435111** |

* Nur in Variante **A** entstand der P9-Decken-Docht **K67@882** (und
  K77-Dochte 997/999/1001/1002) - dort driftete P9 auf 8 / +34.731159.
* Mit dem Literal-Gate (`boden_deklariert_literal is not None -> continue`,
  wirkt fuer P9BODEN_RECLAIM, Literal 68.4000) bleiben **K67 und K77 in B und D
  bit-identisch zum ZP-4-Stand** und **P9 exakt arretiert** (5 / +23.435111).
* Die OBEN-Haelfte der ZP-5-Regel ist damit eingebaut, aber im aktiven Fenster
  (1033..1287) **wirkungslos** - keine Decke (K67/K73) erzeugt dort einen
  Docht. Sie ist architektonisch symmetrisch, aber messbar neutral; das
  P9-Gate schuetzt sie gegen die einzige gemessene Fehlwirkung (K67@882).

### Z5 - ENTSCHEIDUNG (Anwender, verbindlich) und Freigabe

1. **Variante D ist verbindlicher Standard fuer ZP-5.**
   Begruendung (messungsgestuetzt): H1 8 / +38.919584 und P9 5 / +23.435111
   **bit-identisch** zum arretierten ZP-4-Stand; **rein additiv** (kein
   bestehender Trade entfaellt, `K62@1075 +1.475768` bleibt, `K82@1172
   +5.502241` kommt hinzu); registriert ausschliesslich den echten Durchstich
   `K82@1075`; V018-Gegenprobe unveraendert 17 / +65.835576.
   **Sollwerte D: 24 Trades / +88.116626 R (H1 8/+38.919584,
   H2 16/+49.197042, P9 5/+23.435111).**
2. **Retest-Einstieg `K82@1172` (entry_bar 1173, STUFE_1_IN_BAR) bestaetigt.**
   Kein Messerfang an 1072-1074; Q3/Q17 unangetastet.
3. **OBEN-Symmetrie wird eingebaut** (spiegelbildlich), geschuetzt durch das
   P9-Ausschluss-Gate; im aktiven Fenster messbar neutral.
4. **Freigabe erteilt:** Schritt 1 (Revisionspruefung D) und Schritt 2
   (Decken-Symmetrie/P9-Gate) sind **rein lesend** vorbereitet und in Z1-Z4
   belegt; es wurde nichts in Engine/Renderer/Adapter geschrieben.
5. **Schritt 3 (Datenvertrag)** wird als eigener Punkt gefuehrt: der Entwurf
   `SweepDurchstichKonfiguration` ist als *Dokumentation* tragfaehig, darf aber
   die Schwellen **nicht als zweite Konstante** fuehren - `touch_band_pct` und
   `max_sweep_ueberdehnung_pct` sind bereits `cfg`-Werte der Engine
   (Single Source of Truth, "kein Hardcoding"). Die ZP-5-Injektion liest sie
   deshalb zur Laufzeit (`if _dkl <= cfg.touch_band_pct: continue`).
6. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.** Keine UI-/Regressionstests.

### Z6 - Artefakt-Anker E-34n/10 (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34n10_retest.py` | 17.928 | `6731672c53f8ec99d3536d11f8dd143a0ddb30f92ebfb97859c42013064a52fc` |
| `_tmp_e34n10_out.txt` | 35.963 | `239c4c3a89dd9e37f149d92671cff38b8181cce05daefb3d16921ed69702c71a` |
| `_tmp_e34n10_console.txt` | 36.184 | `ab8a0fc90399fddf47f1d04aaa279485ef108f122604f64ae193dfea10ae7b0b` |

**Unveraenderte Anker:** Engine `test/tmp_kanten_engine_replay.py` 196.649 B /
`4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`; Renderer
`test/tmp_png_aug_sichttest.py` 104.221 B /
`eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148`; Adapter
`backtest_lab/phasen_regime_adapter.py` 30.663 B /
`4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83`.
ZP-4-Quelltext-Soll unveraendert `8a3b7070582b620d997c2adfc0bcf3f20e016a94ab97faa84e5143410ee63778`.

### Z7 - Naechster Schritt (nach Einbrand-Freigabe des Anwenders)

Einbrand **ZP-5(D)** als **additiver 14. Patch** (`A_KL_DOCHT`) neben den
13 Bestands-Patches, hinter demselben zweistufigen Gate wie ZP-4
(Laufzeit: `len(hook.segmente) > 1`; Quelltext: `mode == "V019"`):
Segmentwaende OBEN+UNTEN, `boden_deklariert_literal`-Segmente ausgenommen,
Docht nur bei `touch_band_pct < d <= 0.80 %`, `schlaf_windows` des eigenen
Segments aufgehoben; Schwellen aus `cfg` (nicht neu hartcodiert). Danach alle
Fail-Loud-Asserts neu messen: V1 23 -> 24, H1 8/+38.919584, H2 16/+49.197042,
P9 5/+23.435111, V018 17/+65.835576, 5 PNG-Groessen.
**Dieser Einbrand ist noch nicht freigegeben.**
"""

vorher = HANDOFF.read_text(encoding="utf-8")
if not vorher.endswith("\n"):
    vorher += "\n"
HANDOFF.write_text(vorher + ABSCHNITT, encoding="utf-8")

neu = HANDOFF.read_bytes()
print("neu SHA256:", hashlib.sha256(neu).hexdigest())
print("neu Bytes :", len(neu))
print("Zeilen    :", len(neu.decode("utf-8").splitlines()))
print("U+FFFD    :", neu.decode("utf-8").count("\\ufffd"))
