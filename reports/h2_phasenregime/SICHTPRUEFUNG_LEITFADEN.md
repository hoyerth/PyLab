# Sichtprüfungs-Leitfaden — AUG-Sichttest (V01 + V014)

**Status:** Arbeitsmittel für die **manuelle** Sichtprüfung durch den Anwender.
**Nicht normativ.** Normative Quelle bleibt die Spez

`reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md`

mit §54 (v0.13 Darstellungsregeln), §55 (Konsolidat S1–S10), §66 (v0.16
Norm-Amendment), §67 (v0.17 Arretierung V014) und §69 (v0.19 Q29-Forensik +
Phasenboden-Regel G4).

**Verhältnis zu §67.9:** Dieses Dokument **verbraucht den v0.18-Slot nicht**. Der
ist laut §67.9 für das *Ergebnis* der visuellen Abnahme reserviert. Der Leitfaden
ist das davorliegende Hilfsmittel. **Ergebnisse** der Prüfung werden als
**v0.18-Amendment** in die Spez eingetragen, nicht hier.

**Stand der Vorlage:** `HEAD == origin/master == b319105` · Arbeitsbaum clean
(bis auf diese neue Datei).

---

## 1. Zweck

Die fünf PNGs je Modus sind **arretiert** (byte-fixiert). Die Sichtprüfung
beantwortet genau zwei Fragen:

1. **Stimmt das Bild mit den Regeln überein?** (§54 + §66 + Erfahrungswissen §69)
2. **Stimmt das Bild mit den Zahlen überein?** (Baselines, Quartett,
   Niveau-Override, Norm-Zitate)

Sie ist **kein** Regressionstest und **kein** UI-Test. Sie ist die einzige
Instanz, die über die **visuelle Abnahme** entscheidet.

## 2. Geprüfte Sätze

| Modus | Präfix | Satz | Protokoll | Rolle |
|---|---|---|---|---|
| `V01` | `aug_sichttest_` | 5 PNG | `test/tmp_png_aug_sichttest_out.txt` | arretierte v0.1-Baseline (K73-Umweg) |
| `V014` | `aug_sichttest_v014_` | 5 PNG | `test/tmp_png_aug_sichttest_v014_out.txt` | P9 mit K67-Niveau-Override 69,8700 |

**Priorität der Prüfung:** **V014 zuerst** (der neue, noch nicht abgenommene
Satz). Danach **V01** als Regressionsgegenprobe (Bit-Identität).

## 3. Reproduktion (falls die Dateien fehlen)

```
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe test\tmp_png_aug_sichttest.py
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe test\tmp_png_aug_sichttest.py --mode V01
```

Gegenprobe **ohne** Berührung der arretierten Dateien:

```
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe test\tmp_png_aug_sichttest.py --probe-praefix probe_v014_
```

`V014` ist **Default**. Es gibt **keinen** Abschalter für die Asserts
(Fail-Loud, §66.5 / E4). Jede Abweichung endet mit Exit-Code ≠ 0.

## 4. Artefakt-Register (verifiziert am 2026-09-10, alle Hashes bestätigt)

### 4.1 Satz V014 (Prüfgegenstand)

| # | Datei | Bytes | SHA256 |
|---|---|---|---|
| 01 | `aug_sichttest_v014_01_gesamt.png` | 2.049.763 | `25d388e6…83a34117` |
| 02 | `aug_sichttest_v014_02_h1_box.png` | 899.249 | `d9f35876…1b7cbb04` |
| 03 | `aug_sichttest_v014_03_h2_phasen.png` | 1.695.409 | `a055b243…cdd01fc7` |
| 04 | `aug_sichttest_v014_04_p9_regime.png` | 1.151.700 | `1f13a7f7…a981118c` |
| 05 | `aug_sichttest_v014_05_kantenkarte.png` | 2.063.329 | `7b022907…be4f7fbbd3` |

Protokoll: `test/tmp_png_aug_sichttest_v014_out.txt` — 5.363 B, 83 Zeilen,
SHA256 `f1c06678a13a244d…6525013d`.

### 4.2 Satz V01 (arretierte Referenz)

| # | Datei | Bytes | SHA256 |
|---|---|---|---|
| 01 | `aug_sichttest_01_gesamt.png` | 1.876.828 | `89ec7acd…c33b537a` |
| 02 | `aug_sichttest_02_h1_box.png` | 899.249 | `d9f35876…1b7cbb04` |
| 03 | `aug_sichttest_03_h2_phasen.png` | 1.520.409 | `d131deaf…b67307ff` |
| 04 | `aug_sichttest_04_p9_regime.png` | 881.262 | `91a85bae…620afbca4` |
| 05 | `aug_sichttest_05_kantenkarte.png` | 1.905.228 | `0b2b1463…a5cb69444` |

Protokoll: `test/tmp_png_aug_sichttest_out.txt` — 9.784 B, SHA256
`3bd99a781f4921a9…`. **Versiegelt**, darf nicht überschrieben werden.

### 4.3 STOPP-Kriterium

Weicht **eine** Byte-Größe oder ein SHA256 von der Tabelle ab, ist der
arretierte Satz **gebrochen**. Dann **nicht** weiterprüfen, sondern melden:
Engine-SHA (`3ba15c72…5255cb006`), Adapter-SHA (`50bd47c6…afd9b4eda`) und
Head-Commit gegenprüfen.

### 4.4 Harte Vorabprüfung (Pixelbeweis, §67.4)

`aug_sichttest_v014_02_h1_box.png` **muss** byte-identisch zu
`aug_sichttest_02_h1_box.png` sein — gleicher SHA256, beide **899.249 B**.
Daraus folgt die stärkste Einzelaussage des ganzen Sichttests:

> Der P9-lokale Niveau-Override berührt die H1-Box **pixelgenau nicht**.

---

## 5. Block A — Globale Konventionen (in **allen** Panels prüfen)

| # | Prüfpunkt | Soll | Quelle |
|---|---|---|---|
| A1 | Statistik | **mittig** im unteren Panel, Monospace, `ha="center"` | §54.3 R12 |
| A2 | Legende | **oben links**, zweispaltig | §54.3 R13 |
| A3 | Chart-Typ | **Kerzen** in allen Panels | §54.2 R8 |
| A4 | Titel | führt Bar-Grenzen als `Bars 0..1287` (n − 1) bzw. Fenstergrenzen | §54.2 R11 |
| A5 | X-Achse | **Bar-Zeit (Engine-Wanduhr, M15)**, **kein Offset** (`AXIS_TZ_OFFSET_H = 0`); Achsenlabel nennt „Bar-Index primaer" | §54.2 R9, S1 |
| A6 | Trade-Kreise | **immer farbig gefüllt** (rot = SHORT, grün = LONG); H1 klein/dünn, H2 groß/dick | §54.2 R10 |
| A7 | Kanten-Label | **jedes** Label trägt den **kausalen** Preis: `K<kid> <preis>` | §54.1 R1 |
| A8 | Preiswechsel | Label `K<kid> <v0> -> <v1> *`, **fett**, Rahmen `#b8860b` | §54.1 R2 |
| A9 | Norm-Zitat | angehängt, **nicht** ersetzt: `… * Norm <wert>` | §54.1 R3 |
| A10 | Linien | **kausal** (`basis_bei(k)`, Treppe), maskiert vor `pivot_bar + 2`; statische `e.basis` **nicht** als Linienniveau | §54.2 R6 |
| A11 | Sperr-Marker | violett `#8e44ad`: `x` = Q29-Quartil, `^` = M6-Außenwand; gesetzt am **sperrenden Bar** | §54.2 R7 |
| A12 | Tombstones | R21-gelöschte Kanten **ohne Linie**, nur gepunktetes Band | §32, §67 |

**Beabsichtigte Doppelbelegung (kein Fehler, aber prüfen):** In den Panels
existieren **zwei** `x`-Marker — **rot** = `scan["sweep_sperren"]` (Sweep-Sperre,
Altzitat §32) und **violett** = Q29-Quartilsperre (§54.2 R7). Beide sind in der
Legende getrennt ausgewiesen. Nur der **violette** Marker trägt die
Regelbedeutung aus §54.2.

---

## 6. Block B — Statistikblock des V014-Satzes (Wortlaut-Sollwerte)

Diese Zeilen stehen im Protokoll `tmp_png_aug_sichttest_v014_out.txt` und im
Statistikpanel. Jede Zahl ist einzeln abzuhaken.

```
  n=1288 | box_end=640 | Kanten 59 edges + 14 seeds
  Baseline V0    : 14 Trades / +40.445143 R  (H1 8/+38.964262 | H2 6/+1.480880)
  V1_basis (v0.1): 15 Trades / +46.866348 R
  V1_aktiv (V014) : 17 Trades / +61.250064 R  (H1 8/+38.964262 | H2 9/+22.285802)
  Quartett       : K67@903 +4.1198 | K67@980 +9.9877 | K73@981 +2.6943 | K67@1020 +3.0032 | Summe +19.804922 R
  Delta v0.14-v0.1: +14.383717 R  (Soll +14.383717)
  Referenz-Marker (entfallene V01-Trades): K73@980 +2.4119, K73@1020 +3.0093
  Sperr-Marker: Q29 x 57 | M6 ^ 23
  Preiswechsel-Linien (Label 'v0 -> v1 *'): 54
  Plateau-Label K67 (gerendert): K67 69.975 -> 69.870 (P9-Override) -> 69.946 *  Norm 69.9140
```

| # | Kennzahl | Soll |
|---|---|---|
| B1 | V0 (roh) | **14** / **+40,445143 R** (H1 8/+38,964262 · H2 6/+1,480880) |
| B2 | V1_basis (v0.1) | **15** / **+46,866348 R** |
| B3 | V1_aktiv (V014) | **17** / **+61,250064 R** |
| B4 | H1 | **8** / **+38,964262 R** — bit-identisch zu V01 |
| B5 | H2 | **9** / **+22,285802 R** |
| B6 | P9-Beitrag (Quartett) | **+19,804922 R** |
| B7 | Δ v0.14 − v0.1 | **+14,383717 R** |
| B8 | Kanten | **59 edges + 14 seeds** (73 lebend) |

**Kreuzprobe §69:** Die **57** Q29-Sperren im Protokoll sind **dieselbe Zahl**
wie in §69.2 (Adapterlauf). Die 32 H2-Einträge der Q29-Bar-Liste entsprechen
§69.2 (H2 = 32). ⇒ Die Darstellung ist an den forensischen Befund anschlussfähig.

---

## 7. Block C — Panel für Panel

### 7.1 Panel 01 — `_01_gesamt.png` (Bars 0..1287)

| # | Prüfpunkt |
|---|---|
| C01-1 | H1-Box grau hinterlegt, Grenze als gepunktete schwarze Vertikale bei **640** |
| C01-2 | Labels `H1 BOX (bars < 640)` links, `H2 EXPANSION (bars >= 640)` rechts |
| C01-3 | **17** Trade-Beschriftungen (`K<kid> <r>R` / `bar <b>`) |
| C01-4 | Alle 15 V01-Trades sichtbar, davon die **2 entfallenen** blass (siehe Block D) |
| C01-5 | Statistikzeile „PREIS AN DER LINIE (Pflicht)": **54** Preiswechsel-Linien, **4 von 4** Grenzkanten normabweichend |
| C01-6 | Statistikzeile „SPERR-MARKER": Q29 **57**, M6 **23** |
| C01-7 | Kein Label ohne Preis; kein Label mit `e.basis`-Wert |
| C01-8 | Lesbarkeit: Trade-Annotationsboxen überlappen in dichten Bereichen? (bekannter Kandidat, §CHECKPOINT 6b) |

### 7.2 Panel 02 — `_02_h1_box.png` (Bars 0..660)

| # | Prüfpunkt |
|---|---|
| C02-1 | Titel `Bars 0..660`, Sollwert im Titel `+38.964262 R` (6 Nachkommastellen) |
| C02-2 | **8** Trades, Trade-Detailzeile vollständig |
| C02-3 | **Keine** Override-Grenzlinie (848 liegt außerhalb des Fensters) — §66.3 |
| C02-4 | Legende **ohne** die drei V014-Zusatzeinträge (im V014-Modus: **mit**) |
| C02-5 | **Kernaussage:** Bild ist **byte-identisch** zum V01-Panel 02 (SHA256 + 899.249 B) |

### 7.3 Panel 03 — `_03_h2_phasen.png` (Bars 620..1287)

| # | Prüfpunkt |
|---|---|
| C03-1 | Phasen-Zonen: **grün = P9 AKTIV (848–1020)**, **grau = P12 RESERVE**, **rot schraffiert = Lücke (BLOCKIERT)** |
| C03-2 | Lücken genau: 641–847 · 1021–1029 · 1076–1081 · 1135–1170 · 1273–1287 |
| C03-3 | **9** H2-Trades; H2-Trade-Zeile vollständig (V014) |
| C03-4 | P9-Benchmark-Zeile nennt das **Quartett** (nicht das v0.1-Paar) |
| C03-5 | Park-Zeile: `K1@639, K3@650, K45@679, K16@715, K51@760 = 5 / +2.4809 R` |
| C03-6 | P10/P11/P12 als **nicht aktiv** ausgewiesen |
| C03-7 | Q29-Sperren im P9-Bereich sichtbar: **991, 992, 997, 998, 1002** (Teilmenge der 32 H2-Bars) |

### 7.4 Panel 04 — `_04_p9_regime.png` (Bars 820..1045)

| # | Prüfpunkt |
|---|---|
| C04-1 | Titel nennt `Niveau-Override 69.8700` und Ziel `68.3700` |
| C04-2 | Kanten **K67/K73/K76/K77/K82** hervorgehoben; `U_final 69.9140` / `L_final 68.3700` als Strichlinien |
| C04-3 | Override-Grenzlinien bei **848** und **1021** mit Kleintext — **kein** `axvspan` |
| C04-4 | Quartett-Zeile mit `stufe`, `entry`, `sl` für 903/980/981/1020 |
| C04-5 | Quartett-R-Zeile: `+4.1198 / +9.9877 / +2.6943 / +3.0032`, Summe `+19.804922` |
| C04-6 | Austritts-Zeile: Bar 1021 zurück auf 69,9513, ab 1022 = 69,9458 |
| C04-7 | X-Achse: 12 Ticks über 820..1045 (bekannter Kandidat: Tick-Dichte, CHECKPOINT 6a) |
| C04-8 | `K67`-Plateau: Linie starr auf **69.8700** ab Bar 875, Austritt 1021 |

### 7.5 Panel 05 — `_05_kantenkarte.png` (Bars 0..1287)

| # | Prüfpunkt |
|---|---|
| C05-1 | **59 edges + 14 seeds = 73** lebende Kanten |
| C05-2 | OBEN/UNTEN-Aufteilung, Sweep-Sperren, H2-Neugeburten (Dreiecke), Promotionen |
| C05-3 | R21-gelöschte Kanten **unsichtbar** (nur Tombstone-Bänder) |
| C05-4 | Lesart-Zeile nennt K67 (69,9140 / kausal 69,9458 @1259), K73 (69,5550 / kausal 69,6714 @1259), K77 als Boden |
| C05-5 | Seed-Legende (`Seed (< 2 Touches)`) vorhanden |

---

## 8. Block D — Die **neuen Anpassungen** (v0.16/§66 + v0.17/§67)

Dies ist der **Kern** des aktuellen Prüfauftrags: der V014-Satz zeigt die
P9-Override-Wirklichkeit.

| # | Neuerung | Soll im Bild | Quelle |
|---|---|---|---|
| **D1** | **Plateau-Syntax** | Label **exakt** `K67 69.975 -> 69.870 (P9-Override) -> 69.946 *  Norm 69.9140` — fett, Rahmen `#b8860b`, gefolgt vom Norm-Zitat | §66.2 |
| **D2** | **`*`-Pflicht** bei Override-Linien | Das `*` ist gesetzt, **obwohl** nur 3 wirksame Stufen vorliegen (Unterscheidungsmerkmal „Übersteuerung") | §66.2 |
| **D3** | **Grenzlinien statt Fläche** | Zwei gestrichelte Vertikalen in `#b8860b` bei **848** und **1021** mit Kleintexten `Override P9 69.8700 ab Bar 848` / `P9-Override endet Bar 1020` — **kein** eingefärbtes `axvspan` | §66.3 |
| **D4** | **Referenz-Trades** | `K73@980 (+2.4119)` und `K73@1020 (+3.0093)` **blass**: gestrichelt, `mfc="none"`, grau, `alpha 0.45`, Textzusatz `(V01 entfaellt)` | §66.4 |
| **D5** | **Handelnde Trades** | Alle 17 des V014-Laufs bleiben **farbig gefüllt** (`mfc=col`) — Ausnahme gilt **nur** für Referenzmarker | §66.4 |
| **D6** | **Quartett vollständig** | `K67@903`, `K67@980`, `K73@981`, `K67@1020` — Quadrupel-Kontrolle `(67, 67, 73, 67)` | §67.5 |
| **D7** | **Norm-Katalog** | **4 von 4** Grenzkanten normabweichend: K67 `+0,0318` · K73 `+0,1164` · K77 `−0,0103` · K82 `−0,1082`; **Preiswechsel 54** Linien | §67.5 |
| **D8** | **Legende erweitert** | Im V014-Modus **3** Zusatzeinträge: Referenz-Trade, Override-Grenze 69,8700, Plateau-Label-Syntax | §66.5 |
| **D9** | **Protokolltrennung** | V014 schreibt in `…_v014_out.txt`; die V01-Datei bleibt **unberührt** | §66.5/E3 |
| **D10** | **H1-Pixelbeweis** | Panel 02 im V014 ist **bit-identisch** zum V01-Panel 02 | §67.4 |
| **D11** | **Kein Override in H1** | In Panel 02 ist **keine** Linie und **kein** Kleintext aus §66.3 zu sehen | §66.3 |

**Besonders scharfe Einzelprüfung (aus §66.2 hergeleitet):** Die native
Auflösung hätte `5` Stufen ergeben, wirksam sind **3** (875 / 1021 / 1022). Das
Endwert-Literal ist **69,9458** — **nicht** 69,9513. Das gerenderte Label muss
`-> 69.946` zeigen.

---

## 9. Block E — Belegstellen aus v0.19/§69 (Erfahrungswissen für den Prüfer)

Diese Punkte sind **nicht** als neue Darstellung zu erwarten — sie schärfen den
Blick und dienen als **Gegenprobe**, dass nichts Zusätzliches aktiviert wurde.

| # | Befund | Erwartung im Bild |
|---|---|---|
| E1 | **Q29 einseitig** (`distanz <= 25`), negative Distanz erlaubt | Sperr-Marker violett nur an den Bars der Engine-Liste: **57** gesamt, **32** in H2 |
| E2 | **M6-Außenwand** | `^`-Marker **23** gesamt (18 in H2: 643–732, 1122, 1272) |
| E3 | **Kanten-Knicken** ist rohe `np.mean`-Wirkung (Z. 2118 / 2201), **keine** Feinjustierung | **54 von 73** Linien tragen `v0 -> v1 *`; nur der Primär-Anker ist eingefroren |
| E4 | **Größter Knick K67** `69.8700 -> 69.9458` (Δ +0,0758) | Genau dieser Wert steht im Label; Δ > `sl_buffer_usd` 0,05 |
| E5 | Weitere Drifter **> 0,05** | K80 `−0,0625` · K61 `+0,0483` · K78 `−0,0440` |
| E6 | **K77** `68.3920 -> 68.3597` (Δ −0,0323, 6 Stufen) | Label `K77 68.392 -> 68.360 *  Norm 68.3700` |
| E7 | **P9-Boden** = 68,4000 (deklariert, K77) — **nicht** „äußerste Wand" | Im P9-Fenster sind die Tiefs **1000 → 68,2880** und **1002 → 68,3080**; ab 1003 kein Rückfall unter 68,40 |
| E8 | **Regel G4 ist NICHT aktiviert** | **Kein** Trade-Kreis bei Bar **1002**; keine Regel-Linie am Phasenboden |
| E9 | **P12_RESERVE bleibt inert** | **Kein** Trade-Kreis bei Bar **1259** (Papier-Befund +2,234280 R, §69.11) |
| E10 | **Norm-Referenzbar 1259** liegt außerhalb P9 | Die K67-Normaussage (`69,9458 vs 69,9140`) ist vom P9-Override unberührt — Darstellung korrekt |

**E8/E9 sind die wichtigsten Negativprüfungen des Laufs:** Sie beweisen optisch,
dass v0.19 **nur dokumentiert** und **nichts aktiviert** hat.

---

## 10. Block F — Abnahmebogen (auszufüllen)

Legende: **OK** = entspricht dem Soll · **ABW** = Abweichung (bitte Klasse nach
Abschnitt 10.1 nennen).

| Block | Umfang | Befund | Anmerkung |
|---|---|---|---|
| A1–A12 | Globale Konventionen | ☐ OK ☐ ABW | |
| B1–B8 | Statistik-Sollwerte | ☐ OK ☐ ABW | |
| C01-1…8 | Panel 01 gesamt | ☐ OK ☐ ABW | |
| C02-1…5 | Panel 02 H1-Box | ☐ OK ☐ ABW | |
| C03-1…7 | Panel 03 H2-Phasen | ☐ OK ☐ ABW | |
| C04-1…8 | Panel 04 P9-Regime | ☐ OK ☐ ABW | |
| C05-1…5 | Panel 05 Kantenkarte | ☐ OK ☐ ABW | |
| D1–D11 | Neue Anpassungen (§66/§67) | ☐ OK ☐ ABW | |
| E1–E10 | Gegenproben (§69) | ☐ OK ☐ ABW | |

**Gesamturteil V014:** ☐ angenommen ☐ angenommen mit Auflagen ☐ zurückgewiesen
**Gesamturteil V01:** ☐ angenommen ☐ angenommen mit Auflagen ☐ zurückgewiesen

Datum / Kürzel: ____________________

### 10.1 Klassifikation einer Abweichung

| Klasse | Gegenstand | Folge |
|---|---|---|
| **1 — Kosmetik** | Layout, Überlappung, Tick-Dichte, Label-Position | **v0.18-Amendment** der Darstellung; Baseline unberührt |
| **2 — Normverstoß** | §54/§66 nicht eingehalten (fehlender Preis, fehlendes `*`, Fläche statt Grenzlinie, ungefärbter Trade-Kreis) | **v0.18-Amendment** der Regeln + Renderer-Korrektur |
| **3 — Zahlenabweichung** | Baseline, Quartett, Δ, Norm-Zitat stimmen nicht | **STOPP.** Engine-/Adapter-Hash prüfen; mögliche Baseline-Gefährdung |

**Klasse 3 ist ein Alarm, nicht ein Schönheitsfehler.** Sie würde die in §67
arretierte Ertragsaussage berühren.

## 11. Bekannte Kandidaten (aus dem vorigen Sichttest, noch offen)

Aus `CHECKPOINT_2026-09-09.md` §6:

| Kandidat | Gegenstand | Betrifft |
|---|---|---|
| (a) | X-Achsen-Ticks in Panel 04 (12 Ticks über 820..1045) | C04-7 |
| (b) | Überlappung der Trade-Annotationsboxen in dichten Bereichen | C01-8 |
| (c) | Position der `P9 AKTIV` / `P12 RESERVE`-Labels am oberen Rand | C03-1 |

Diese drei sind **nicht** durch §66/§67 eingeführt und **nicht** durch §69
berührt. Sie bleiben offen und werden **nur** auf Anweisung angepasst.

## 12. Nicht-Ziele und Hygiene

- **Kein** Eingriff in Engine (`3ba15c72…5255cb006`), Adapter
  (`50bd47c6…afd9b4eda`) oder in den V01-Bildsatz.
- **Kein** `axvspan` für Override-Zonen. **Kein** Offset auf der X-Achse.
- **Kein** `poc_start`-Eingriff, **keine** `quartil_distanz_pct`-Änderung
  (§69.13).
- `test/` bleibt gitignored; **dieser Leitfaden und die Spez sind versioniert**.
- Ergebnisse gehören **nicht** in den Leitfaden, sondern als
  **v0.18-Amendment** in `H2_PHASENREGIME_ADAPTER_SPEZ.md`.

---

## 13. Offene Entscheidungsfragen (Antwort als Text erwartet)

1. **Reihenfolge:** Soll die Abnahme mit **V014** beginnen (neuer Satz, hier
   vorgeschlagen) oder zuerst die **V01-Regressionsgegenprobe** laufen?
2. **Zuschnitt:** Reicht die Abnahme über die in Block A–E gelisteten Punkte,
   oder sollen die drei **Alt-Kandidaten** (a/b/c, Abschnitt 11) mit in den
   Abnahmebogen aufgenommen werden — obwohl sie nicht Teil der neuen
   Anpassungen sind?
3. **P12-Beobachtung:** Soll der P12-Fall aus §69.11 (Bar 1259, +2,234280 R,
   regelkonform aber inert) als **eigener Prüfpunkt** im Bild verifiziert
   werden (Negativnachweis „kein Trade-Kreis bei 1259", E9) oder genügt die
   Dokumentation in §69.11?
4. **Bogen-Ablage:** Soll der ausgefüllte Abnahmebogen als **neue Datei**
   (z. B. `reports/h2_phasenregime/ABNAHME_V014_2026-09-10.md`) geführt oder
   direkt als **v0.18-Amendment** in die Spez eingetragen werden?
5. **Panel-04-Ticks:** Soll Kandidat (a) **vor** der Abnahme korrigiert werden
   (dann Neu-Arretierung des V014-Satzes mit neuen Hashes) oder **nach** der
   Abnahme als v0.18-Auflage?
6. **Doppelbelegung `x`:** Soll die rote `x`-Sweep-Sperre aus §32 als Altzitat
   bestehen bleiben, oder soll sie zur Schärfung von §54.2 R7 künftig anders
   gezeichnet werden (Änderung = Neu-Arretierung, daher nur auf Anweisung)?

---

## 14. Beschlusslage (2026-09-10) — die sechs Fragen aus Abschnitt 13 sind beantwortet

**Leitsatz (institutionell):** **Keine Neu-Arretierung vor der Abnahme.** Wer
wegen optischer Kosmetik mitten im Prüfprozess den Renderer neu anwirft,
vernichtet die arretierten SHA256-Hashes des V014-Satzes. Es gilt: **erst den
vorliegenden Stand unverändert abnehmen, Mängel als Auflagen protokollieren.**

| # | Gegenstand | Beschluss |
|---|---|---|
| 1 | Prüfungsreihenfolge | **V014 zuerst** (Prüfling der neuen Anforderungen); V01 nur als punktuelle Gegenprobe |
| 2 | Alt-Kandidaten (a/b/c) | **in den Bogen aufnehmen**, aber strikt als Kategorie **„Alt-Befunde (informativ / keine Abnahmeblockade)"** |
| 3 | P12-Negativnachweis Bar 1259 | **als eigener Bild-Prüfpunkt E9** führen (schließt die Beweiskette zu §69.11) |
| 4 | Ablage des Bogens | **eigene Datei** `reports/h2_phasenregime/ABNAHME_V014_2026-09-10.md`; nur das **finale Votum** wandert als arretierter Textblock in **v0.18** der Hauptspezifikation |
| 5 | Panel-04-Tick-Dichte | **Auflage nach der Abnahme** (keine Neu-Generierung, keine Hash-Entwertung) |
| 6 | Doppelbelegung Marker `x` | **Auflage für die nächste Renderer-Iteration**; im Leitfaden dokumentiert, keine Blockade der fachlichen Beurteilung |

### 14.1 Typisierter Datenvertrag des Abnahmeprozesses

```python
from dataclasses import dataclass
from typing import Final, Literal

@dataclass(frozen=True, slots=True)
class SichtpruefungEntscheidung:
    """Fixierte Verfahrensentscheidungen der Sichtprüfung (2026-09-10).

    Attributes:
        pruefungs_reihenfolge: Reihenfolge der Bildabnahme.
        alt_kandidaten_im_bogen: Alt-Kandidaten (a/b/c) im Bogen führen.
        p12_negativnachweis_als_bildpunkt: Bar 1259 als eigener Prüfpunkt E9.
        ablage_ort_bogen: Ort des Abnahmebogens.
        panel_04_ticks_behandlung: Umgang mit der Tick-Dichte in Panel 04.
        marker_doppelbelegung_x_behandlung: Umgang mit der `x`-Doppelbelegung.
        leitfaden_commit_status: Git-Status des Leitfadens.
    """
    pruefungs_reihenfolge: Literal["V014_ZUERST", "V01_GEGENPROBE_ZUERST"]
    alt_kandidaten_im_bogen: bool
    p12_negativnachweis_als_bildpunkt: bool
    ablage_ort_bogen: Literal["SEPARATE_DATEI", "DIREKT_IN_SPEZ"]
    panel_04_ticks_behandlung: Literal["AUFLAGE_NACH_ABNAHME",
                                       "SOFORT_NEU_ARRETIEREN"]
    marker_doppelbelegung_x_behandlung: Literal["AUFLAGE_NACH_ABNAHME",
                                                "SOFORT_NEU_ARRETIEREN"]
    leitfaden_commit_status: Literal["JETZT_COMMITTEN", "UNTRACKED_LASSEN"]


ENTSCHEIDUNG_2026_09_10: Final[SichtpruefungEntscheidung] = \
    SichtpruefungEntscheidung(
        pruefungs_reihenfolge="V014_ZUERST",
        alt_kandidaten_im_bogen=True,
        p12_negativnachweis_als_bildpunkt=True,
        ablage_ort_bogen="SEPARATE_DATEI",
        panel_04_ticks_behandlung="AUFLAGE_NACH_ABNAHME",
        marker_doppelbelegung_x_behandlung="AUFLAGE_NACH_ABNAHME",
        leitfaden_commit_status="JETZT_COMMITTEN",
    )
```

### 14.2 Auflagen-Register (Action Items, blockieren die Abnahme nicht)

| Nr. | Auflage | Betrifft | Wirkung |
|---|---|---|---|
| **A-1** | Tick-Dichte **Panel 04** (12 Ticks über 820..1045) prüfen/anpassen | C04-7 | nächste Renderer-Iteration; **Neu-Arretierung erst danach** |
| **A-2** | Doppelbelegung Marker `x` (rot = Sweep-Sperre §32 · violett = Q29 §54.2 R7) zur Schärfung von §54.2 R7 entzerren | A11, §11 | nächste Renderer-Iteration; **Neu-Arretierung erst danach** |
| **A-3** | Box-Überlappung in dichten Bereichen | C01-8 | Kosmetik, Klasse 1 |
| **A-4** | Position `P9 AKTIV` / `P12 RESERVE` am oberen Rand | C03-1 | Kosmetik, Klasse 1 |

**A-1 und A-2 sind Hash-relevant** (jede Zeichnungsänderung erzeugt neue PNGs) und
werden deshalb **ausschließlich nach** abgeschlossener Abnahme gebündelt
umgesetzt. A-3/A-4 sind layout-nah und ebenfalls nachgelagert.

### 14.3 Prozess-Trennung

1. **Leitfaden** (diese Datei): Regelwerk der Prüfung, versioniert.
2. **Abnahmebogen** (`ABNAHME_V014_2026-09-10.md`): dynamisches Arbeitsprotokoll
   mit Checkboxen, versioniert, wird beim Durchgang ausgefüllt.
3. **Spezifikation** (`H2_PHASENREGIME_ADAPTER_SPEZ.md`): nimmt **nur** das
   finale Votum als **v0.18-Amendment** auf — keine flüchtigen Checkboxen.

Die drei Ebenen bleiben getrennt. §67.9 ist damit gewahrt: v0.18 trägt das
**Ergebnis** der visuellen Abnahme, nicht ihren Arbeitsstand.
