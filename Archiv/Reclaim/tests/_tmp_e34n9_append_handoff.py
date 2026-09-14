# -*- coding: utf-8 -*-
"""Append 'E-34n' an test/SESSION_HANDOFF.md (Vorbedingung: SHA 87143575...).

Rein additiv: haengt den Forensik-Abschnitt E-34n/1..9 (Kantenlaeufer-Docht,
ZP-5) an das Handoff an. Bewusst ASCII-only, um Encoding-Mojibake zu vermeiden.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"
VORBEDINGUNG = "8714357542b21d8ffcf258c2e1bc4b4eeacf4a8d113ff113736018c6f9fa707e"

roh = HANDOFF.read_bytes()
ist = hashlib.sha256(roh).hexdigest()
print("Vorbedingung SHA256:", VORBEDINGUNG)
print("aktuell           :", ist)
if ist != VORBEDINGUNG:
    print("ABBRUCH: Vorbedingung nicht erfuellt.")
    sys.exit(1)

ABSCHNITT = """
## Phase 2 / E-34n (2026-09-11, ab) - FORENSIK: Kantenlaeufer-Docht (ZP-5) -- Root Cause, Blast-Radius, Variantenwahl

Auftrag (Anwender-Vorgabe E-34n): Warum handelt der Kantenlaeufer an der
A1-Segmentwand `K82` (Bars 1072-1075) nicht? Dazu die Vorgabe, ZP-5
("Kantenlaeufer-Docht") zu spezifizieren. Die Forensik ist **rein lesend**:
Engine (`test/tmp_kanten_engine_replay.py`) und Renderer
(`test/tmp_png_aug_sichttest.py`) wurden NICHT veraendert; ZP-5 wurde nur als
Quelltext-Injektion in das jeweils deepkopierte Scan-Objekt angewandt.

**Verbindliche Anwender-Entscheidungen (E-34n, Textblock-Vorgabe):**
1. Geltungsbereich strikt nur **deklarierte Segmentwand** (`seg.boden.kid` /
   `seg.decke.kid`).
2. **Symmetrisch OBEN und UNTEN.**
3. Reclaim-Trigger: **Q3/Q17 (Non-Expansion) unangetastet** -- kein Messerfang
   an 1072-1074; Einstieg erst am kausalen Reclaim.
4. Basis-Bilanz: nur `wicks` + `touch_conf`; `.basis` (statisch) unberuehrt.
5. **Keine** Promotion (`ist_prim_anker` unberuehrt).
6. Arretierung sofort in diesem Handoff + Commit.
Zeitbasis durchgaengig BKZ (`time AT TIME ZONE 'UTC'`), Bar = Primaerschluessel.

### Y1 - Root Cause (E-34n/7, der entscheidende Befund)

`_kandidat`-Pool-Dump bei Bar 1072 (LONG), `dist` in %:

| pos | Kante | dist % | touch_conf | Anmerkung |
|---|---|---|---|---|
| 0 | K48 | -7.8479 | 2 | dormanter Crash-Extrem (`_lebt=False`) |
| 1 | K3 | -7.1800 | 3 | dormante Linie |
| 2 | K17 | -2.7934 | 13 | dormante Linie |
| 3 | **K82** | +0.0962 | 2 | **Segmentwand A1** -- wird nicht pos 0 |
| 4 | K62 | +0.4352 | 4 | wurde Signal-Linie |

**Kette:** dormante Linien belegen POS 0-2 -> die Wand-Regel
`if pos == 0: return e` faellt fuer K82 weg -> K82 gilt als *innere* Linie ->
`touch_conf = 2 < min_touches_handelbar = 3` -> `continue` -> K62 (tc=4)
handelt. Der Kantenlaeufer-Docht am A1-Boden ist damit ein
**Pool-Ordnungs-Artefakt**, kein Signal-Artefakt.

Zusatzbefunde: `K82.ist_aktiv_bei(1072) = True`, **`ist_aktiv_bei(1075) = False`**
(`schlaf_windows = [(1074, 1174)]`); Hook 1 gibt bei 1072-1078 nichts frei
(`FREIGABE = None`, E-34n/6). `K82` statische `.basis` = **67.5455**;
`basis_bei(1072/1075)` ist ein **laufendes Extremum** = 67.5350 -> 67.5530 ->
67.6000. `touch_band_pct = 0.12`.

### Y2 - Der Fall K82 (E-34n/3, 3b, 4, 5)

Bars 1072-1075 (25.08. 15:00-15:45) testen K82 viermal; Lows
67.4880 / 67.4620 / 67.4550 / **67.4200**. Nur 1075 ist ein P1-Pivot
(`_pivot_dual`) -- und liegt mit **0,197 % ausserhalb `touch_band_pct = 0.12`**
-> **kein** Docht. `sweep_sperren` im Fenster 1040-1120 = **0** (Referenz ist
die aeusserste Linie K54 66.5680). Stattdessen entsteht **neuer Seed K85**
(Basis 67.4200, Pivot 1075). `K82.ist_prim_anker = False`, `promoviert_ab = -1`.

Exakte Reclaim-Tabelle (`basis_bei` = 67.5530 konstant):

| Bar | dist % | Close >= Basis? | Stufe |
|---|---|---|---|
| 1072 | 0.096 | nein (67.5010) | 0 |
| 1073 | 0.135 | nein (67.4700) | 0 |
| 1074 | 0.145 | nein (67.5330) | 0 |
| **1075** | 0.197 | **ja (67.6780)** | **1 IN-BAR** |

K62 (`basis_bei` = 67.7830) hat dagegen 1075 Stufe 2 und 1076/1077/1078 je
Stufe 1 -- deshalb blieb bisher K62 der Traeger.

Vier-Bar-Gegenrechnung (frei erfundenes Gegenmodell, Entry = Open Folgebalken,
SL = Serientief - 0.05): 1072 **+0.4716 (SL)** / 1073 **+14.7230** /
1074 +6.6110 / 1075 +2.2801 = **Summe +24.086 R** gegen real +1.4758 R.
**Das ist NICHT realisiert** (Q3/Q17 bleiben unangetastet) und dient nur als
Beleg der Sperrwirkung -- bewusst kein Messerfang.

### Y3 - ZP-5-Regel (Spezifikation des Anwenders)

* Nur deklarierte **Segmentwaende** (`seg.boden.kid` / `seg.decke.kid`),
  **symmetrisch** OBEN und UNTEN.
* Ein Bar `b` im Segment (`start_bar <= b <= end_bar`,
  `b >= erster_pivot_bar + 2`), dessen Extrem die **eingefrorene** Wandbasis
  `_b0 = basis_bei(seg.start_bar)` nach aussen durchstoesst, mit
  `0 < d <= 0.80 %`, wird als **Docht** registriert (`wicks` + `touch_conf`),
  sofern `b` noch kein Docht ist.
* `schlaf_windows` der Wand, die **ihr eigenes Segment** ueberlappen, werden
  aufgehoben (Segmentwand schlaeft nicht in ihrem eigenen Segment).
* `.basis` (statisch) und `ist_prim_anker` unberuehrt; keine Promotion.
* **Zweistufiges Gating:** Laufzeit-Stufe `len(hook.segmente) > 1`
  (gemessen: `len(V015.segmente) = 1`, `len(V019.segmente) = 3`) UND
  Quelltext-Stufe `mode == "V019"`.

### Y4 - Varianten und Messergebnis (E-34n/9, alle Werte gemessen)

Partition **arretiert**: H1 = `entry_bar < box_end` mit `box_end = 644`
(dynamische Kalenderkante, `searchsorted`), H2 = `entry_bar >= 644`.
P9 = `P9_BODEN_RECLAIM` (Bars 848..1020).

| Variante | n | Summe R | H1 n/R | H2 n/R | P9 n/R | Delta R |
|---|---|---|---|---|---|---|
| ZP-4 (arretiert) | 23 | +82.614385 | 8/+38.919584 | 15/+43.694801 | 5/+23.435111 | Referenz |
| V018 (Gegenprobe) | 17 | +65.835576 | 8/+38.919584 | 9/+26.915992 | 5/+23.435111 | unveraendert |
| **A** (Spez wörtlich, alle Waende, OBEN+UNTEN) | **26** | **+97.936906** | 8/+38.919584 | 18/+59.017322 | **8/+34.731159** | **+15.322521** |
| **B** (+ Boden-Literal-Segmente ausgenommen) | **23** | **+86.640859** | 8/+38.919584 | 15/+47.721274 | 5/+23.435111 | **+4.026474** |
| C (= B + nur UNTEN) | 23 | +86.640859 | 8/+38.919584 | 15/+47.721274 | 5/+23.435111 | +4.026474 |
| **D** (= C + nur echter Durchstich `d > touch_band_pct`) | **24** | **+88.116626** | 8/+38.919584 | 16/+49.197042 | 5/+23.435111 | **+5.502241** |

**Trade-Deltas (jeweils gegen ZP-4):**

* **A:** WEG `K62@1075` (+1.475768, STUFE_2_KERZE_2); NEU `K77@999`
  (+4.165749), `K77@1000` (+4.892588), `K77@1001` (+2.237711) -- alle drei in
  **P9** -- sowie `K82@1172` (+5.502241, e_bar 1173, STUFE_1_IN_BAR).
* **B = C:** WEG `K62@1075`; NEU `K82@1172`.
* **D:** NEU `K82@1172` (kein Trade entfaellt).

**Kanten-Deltas (Docht-Registrierung, gemessen an der Scan-Kopie):**

| Variante | K67 | K77 | K82 | Schlaf-Fenster K82 |
|---|---|---|---|---|
| A | +[882] (P9-Decke) | +[997, 999, 1001, 1002] | +[1072, 1073, 1074, 1075] | `[(1074,1174)]` -> `[]` |
| B | - | - | +[1072, 1073, 1074, 1075] | `[(1074,1174)]` -> `[]` |
| C | - | - | +[1072, 1073, 1074, 1075] | `[(1074,1174)]` -> `[]` |
| D | - | - | +[1075] | `[(1074,1174)]` -> `[]` |

`K82.touch_conf(1075)` steigt 2 -> 4 (A/B/C) bzw. 2 -> 3 (D); das Gate
`min_touches_handelbar = 3` ist in allen Faellen erfuellt. `K82.basis` bleibt
in **allen** Varianten **67.5455** (Entscheidung 4 eingehalten).

**Wichtig:** Der ZP-5-Docht an A1s Decke (K67) und A2s Decke (K73) erzeugt im
aktiven Fenster (1033..1287) **keinen einzigen** Docht -- die OBEN-Symmetrie ist
derzeit wirkungslos, nur registrierend (K67@882 liegt in P9). C ist damit
zahlenmaessig identisch zu B, aber **strukturell asymmetrisch** -> ausgeschieden.

**Nicht realisierter Messerfang:** Bars 1072/1073/1074 erzeugen in **keiner**
Variante einen Trade (und in D nicht einmal einen Docht) -- Entscheidung 3 ist
damit messbar eingehalten.

**Gemessener Einstieg liegt NICHT an Bar 1075:** Der neue Trade lautet
`K82@1172` mit `entry_bar = 1173` (STUFE_1_IN_BAR) -- also am **Retest**
(26.08. 17:00), nicht am Erstkontakt. Die in Entscheidung 3 formulierte
Erwartung ("Einstieg am Reclaim-Bar 1075") trifft so nicht zu; Q3/Q17
unangetastet heisst: kein Einstieg an 1075. Siehe Y7.

### Y5 - Erratum zu E-34n/8: "H1-Verletzung" war ein Fehletikett

E-34n/8 meldete eine "H1-Verletzung" durch die neuen Trades bei 999/1000/1001
(und den Wegfall von K62@1075). Das ist **falsch etikettiert**: die arretierte
Partition ist `entry_bar < box_end = 644`, nicht `bar <= 1020`. Die neuen
Trades haben `entry_bar` 1000/1001/1002 bzw. 1173 und liegen damit **alle in
H2**. Gemessen: **H1 ist in allen Varianten A-D bit-identisch 8 / +38.919584**
(die H1-Box ist durch ZP-5 nicht beruehrt). Korrekt ist: **P9** ist die
betroffene Partition (nur in Variante A), und die A1/A2-Mehrheit liegt in H2.

### Y6 - Artefakt-Anker E-34n (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34n1_geometrie.py` | 12.292 | `3e978d375e554b764f530ae782b6ee26bdf8ce9ead06117a033a913b8ca3ee11` |
| `_tmp_e34n1_out.txt` | 15.529 | `27079075d928afa640a02a49e98a1c3e655d84461f56c258917a86e588204b59` |
| `_tmp_e34n2_trace.py` | 13.128 | `519296845db5cfc91af837952e61a1bdb07eb5a421ed63b4cccc0c70bc4d7be6` |
| `_tmp_e34n2_out.txt` | 97.047 | `069cc405c66472ebc81df9ac3f402ea489772c06c4e56b7df04cbf77ad521aab` |
| `_tmp_e34n2_count.py` | 622 | `683059dc5b87aa941c34a797b18621cb8b69f952a073baba1fcb5ebe0301ba54` |
| `_tmp_e34n2_console.txt` | 197.128 | `8b198e16f5509deb4b061fde820fdfad20a4470e1c7eef54c2b59e7705f63540` |
| `_tmp_e34n3_wicks.py` | 8.522 | `4d04d9e90a46bdf598b783f5db79622dc239019b851b18ef52d0be0c8650ce69` |
| `_tmp_e34n3_out.txt` | 56.585 | `8a0ada499269d64775b9a668e592964990c2941a565bef3bbde0010e5a41446e` |
| `_tmp_e34n3_console.txt` | 114.352 | `3a01bb85ad259629b748b1f116863cd294e09501133419fabe517837213d5a65` |
| `_tmp_e34n3b_sweep.py` | 2.552 | `ea49f4496e4ad200c5cd078af4fdc95869f4c7b7e5949ff3b80d6e162b418d6f` |
| `_tmp_e34n3b_out.txt` | 1.923 | `971340f955fa2d955c73ad3737f2cca4787f81ec376d1bd04d3672f479649f3e` |
| `_tmp_e34n4_cfg.py` | 3.737 | `78237f8c1c8e61ee7932b3ca86f9c4a0741c925028990a72f7bffdcb0247272b` |
| `_tmp_e34n4_out.txt` | 26.849 | `8070fc02c3816b7a45184b8295eb1e21823ea675cf31034a95993be8fb3ba6ec` |
| `_tmp_e34n5_vier.py` | 3.882 | `4ca3db9ea5be9058934842105c5620f14737cc32167ce21fe35dd8215819092f` |
| `_tmp_e34n5_out.txt` | 1.614 | `4867e2a3dad94e58c895b25d20dca1ffe2e7e6ee43be6dde5828b2a593eb3df7` |
| `_tmp_e34n6_hook1.py` | 2.375 | `298dd3afa086f4c814b96c2b75bbadecf10a32c8d0b3118d0e216aea0811306f` |
| `_tmp_e34n6_out.txt` | 4.165 | `dac3f7bcfc12b8ad3544919fb353be148c4ffe13e799fc1460f750b214419acc` |
| `_tmp_e34n7_pool.py` | 4.155 | `8aaa4534430ef83ab9be44abfa6d7df0c006ee737d90f1614cb71f1c61d2daa6` |
| `_tmp_e34n7_out.txt` | 16.928 | `c52cf1271640df676eb47c04d09bcf0062a6352f5aab94ef20e23d2a17ce7f3a` |
| `_tmp_e34n8_zp5.py` | 9.523 | `025507d8949df6ef4cb5e964217edf32d27f05db2146f2ffab54d2e4574f9d6d` |
| `_tmp_e34n8_out.txt` | 2.885 | `506b1acd8001fcfa59e5e6eb597dd52c1f0b2c1888f959b5a4dea7ba0a0d084c` |
| `_tmp_e34n9_varianten.py` | 10.640 | `e4234c6fd9e586e5b5c3872f76477c2f4e0c6dc1fa102ff5c33685d8235b5509` |
| `_tmp_e34n9_out.txt` | 2.637 | `1bf6fb40118496cd0ef8be4eee916c88e15e427af37630b6d2952237db65133c` |
| `_tmp_e34n9_append_handoff.py` | (dieser Lauf) | - |
| `_tmp_e34n_sichtpruefung.py` | 10.945 | `7a9a4acb78edb917209ef841f9d4ef77a2e4f0e488e33be6338a6a3840d52091` |

**Unveraenderte Anker (Gegenprobe der Forensik):** Engine
`test/tmp_kanten_engine_replay.py` 196.649 B /
`4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`; Renderer
`test/tmp_png_aug_sichttest.py` 104.221 B /
`eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148`; Adapter
`backtest_lab/phasen_regime_adapter.py` 30.663 B /
`4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83`.

### Y7 - Offene Entscheidungen (Textblock)

1. **Variantenwahl ZP-5 (blockierend fuer den Einbrand).** Drei Varianten sind
   zulaessig, C ist ausgeschieden (asymmetrisch, Zahlen identisch zu B):
   * **A (Spez woertlich, +15.322521 R):** hoechster Ertrag, aber **P9-Anker
     driftet** (5/+23.435111 -> 8/+34.731159) und K77 wird im P9-Fenster
     gedochtet, obwohl P9 fuer seinen Boden ein **Literal** (`68.4000`)
     deklariert -- der Docht wird gegen die K77-Basis (68.3920) gerechnet.
   * **B (Spez + P9-Ausnahme, +4.026474 R):** symmetrisch, **P9 und H1 exakt
     arretiert**, liefert den Ziel-Trade `K82@1172`; Nachteil: der bestehende
     `K62@1075` (+1.475768) **entfaellt** (der Pool-Ordnungs-Effekt wirkt
     weiter und wechselt den Traeger).
   * **D (B + nur echter Durchstich `d > touch_band_pct`, +5.502241 R):**
     symmetrisch, P9 und H1 arretiert, **rein additiv** (kein bestehender Trade
     faellt weg), registriert nur den echten Durchstich `K82@1075`
     (Entscheidung 3 wahrt: kein kuenstlicher Docht an 1072-1074).
     Nachteil: fuehrt ein **zusaetzliches Kriterium** ein, das nicht in der
     gelieferten Spezifikation steht.
   **Empfehlung des Assistenten: D** (additiv, P9/H1 unberuehrt, kein
   Messerfang-Docht) -- falls die Spezifikation woertlich gelten soll und nur
   P9 ausgenommen wird, ist **B** die Wahl. **A** nur, wenn der P9-Anker
   bewusst neu arretiert werden soll.
   **Entscheidungsfrage:** Welche Variante soll eingebrannt werden?
2. **Einstiegsbar bestaetigen:** erwartet war ein Einstieg am Reclaim-Bar 1075;
   gemessen wird der Retest-Einstieg `K82@1172` (`entry_bar` 1173). Ist das die
   gewuenschte Semantik (kein Messerfang, Einstieg erst am Retest)?
3. **OBEN-Symmetrie ungeprueft:** im aktiven Fenster 1033..1287 erzeugt keine
   Decke (K67/K73) einen Docht. Die OBEN-Haelfte der Regel ist daher nur
   registrierend belegt (K67@882 in P9), nicht durch Trade-Wirkung. Soll OBEN
   trotzdem symmetrisch eingebrannt werden?
4. **Unveraendert offen (aus X7):** Renderer-Versionierung
   (`test/tmp_png_aug_sichttest.py` bleibt unversioniert, Arretierung nur ueber
   SHA-Anker) und `shade_phases` (Renderer Z. 1046) zeichnet weiterhin die
   Literal-Phasen statt A1/A2 (Kosmetik; Luecken 1135-1170 und 1273-1287
   erscheinen rot schraffiert, obwohl A1/A2 dort aktiv sind).
5. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.** Keine UI- und keine
   Regressionstests; Verifikation ausschliesslich ueber `py_compile`,
   gezielte Logik-Laeufe in `test/` und Code-Inspektion.
"""

vorher = HANDOFF.read_text(encoding="utf-8")
if not vorher.endswith("\n"):
    vorher += "\n"
HANDOFF.write_text(vorher + ABSCHNITT, encoding="utf-8")

neu = HANDOFF.read_bytes()
print("neu SHA256:", hashlib.sha256(neu).hexdigest())
print("neu Bytes :", len(neu))
print("Zeilen    :", len(neu.decode('utf-8').splitlines()))
