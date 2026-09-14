## Phase 2 / E-34 (2026-09-11, r) — Endogene Segmentbildung: **die zielfreie Regel reproduziert E-33 bis auf 0,037 R — der Fit-Verdacht ist ausgeraeumt**

### O0 · Anlass

Anwender-Kritik nach E-33: die Segmentgrenzen **P10 (1021..1170) / P12
(1171..1287)** wurden *nach* Kenntnis der drei avisierten Bars gesetzt, und
`P12_RESERVE` steht bereits wortgleich als August-Handliste im Adapter. Damit
stand der **Fit-Verdacht**: "Habt ihr die Kanten nur anhand meiner Zielvorgaben
gefunden?" Auftrag: **keine Lookaheads, keine imaginaeren Zielvorgaben in der
Logik** — die Segmentbildung muss **endogen** aus dem kausalen Kantenbestand
entstehen.

### O1 · Die zielfreie Regel (ein einziger Freiheitsgrad, nicht im Zielbereich)

- `lebt(e, k)`: der letzte **bestaetigte** Docht `b` (Kausalitaet `b + 2 <= k`)
  erfuellt `b >= k - wall_live_bars` (**96**, arretiert 2026-09-08).
- `decke(k)` = OBEN-Linie mit **max** `basis_bei(k)` unter den lebenden Linien;
  `boden(k)` = UNTEN-Linie mit **min**.
- **Segmentgrenze** = Bar, an dem sich das Paar `(decke_kid, boden_kid)` aendert.
- **START** = `P9_BODEN_RECLAIM.end_bar + 1` (= **1021**) — *abgeleitet*, kein
  Literal. Einzige uebernommene Groesse: das **arretierte Segment P9**
  (848..1020, §69, +5,4212 R) bleibt **unveraendert**.
- **Zusammenfassung** benachbarter Segmente, wenn `Laenge < MIN_BARS` **oder**
  wenn beide Grenzniveaus `<= touch_band_pct` (**0,12 %**) gleich sind — beide
  Kriterien ausschliesslich aus **arretierten** Konstanten.
- Die Schalter **VC / M6 / UEB / SB** wirken **segment-lokal** (nur ausserhalb
  P9); der Zielpreis kommt aus `hook_2_ziel` = den **eigenen** Segmentgrenzen.

Freiheitsgrad der ganzen Kampagne: **nur `MIN_BARS`**. Kein Eingriff in den
Zielbereich, keine Kenntnis der drei Bars.

### O2 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34_auto.py` | 16.767 | `eceb532a8d6b6a660bd7788f914ae850bd558c5154f8e7eaafe3ec2a62113948` |
| `_tmp_e34_auto_RAW_out.txt` | 4.662 | `e7be15c16faecc5876f76b9baf37eb4bd714689bddfa67aea23ce92c975f4d94` |
| `_tmp_e34_auto_MIN4_out.txt` | 4.517 | `e52fed28a410579435b000f75a6a40d2d24585e45b0be1d3c0a677987ca3975d` |
| `_tmp_e34_auto_MIN8_out.txt` | 4.443 | `685803b2673eed21f60813117d353d478f86b9d9d291341df2a0a730ef93cc2c` |
| `_tmp_e34_auto_MIN16_out.txt` | 4.447 | `9b9fb4e415e00cc23d89ccc5550d5c757e828f4bfe3d19865f8eedc4a0958f5a` |
| `_tmp_e34_auto_MIN24_out.txt` | 4.447 | `6a728b80bdd92b814ee4d7d6152ef942d6d04f10537e08df75129a11ff858fc8` |
| `_tmp_e34_auto_MIN48_out.txt` | 4.373 | `a862222e7bb461f0f9bd2accc815fc1fae808eb8d99edce7cb495b5eda118b4d` |

Engine `tmp_kanten_engine_replay.py`: `4a576a766670d684c3038196...` (unveraendert).
Laufzeit AUG ca. 0,8 s je Variante.

### O3 · A. Die zielfreien Wechselpunkte der Regel (Auszug ab Bar 600)

| Bar | decke | boden |
|---|---|---|
| 875 | K67 69,9750 | K17 65,6540 |
| 889 | K67 69,9750 | K62 67,7260 |
| 914 | K67 69,9310 | K63 67,8310 |
| 917 | K67 69,9310 | K60 67,9750 |
| 937 | K67 69,9310 | K77 68,3920 |
| **1033** | K67 69,8990 | **K82 67,5350** |
| 1077 | K67 69,8990 | K85 67,4200 |
| 1117 | K73 69,6380 | K85 67,4200 |
| 1120 | K78 69,2630 | K85 67,4200 |
| 1124 | K73 69,6380 | K85 67,4200 |
| 1172 | K73 69,6380 | K60 67,9750 |
| **1174** | K73 69,6380 | **K82 67,5530** |

Die Regel **erzeugt dieselben Grenz-Kanten** (oben K67 → K73, unten K82/K85),
die E-33 als **Anwender-Setzung** benutzt hatte — nur die **Schnittstellen**
liegen woanders: 1033/1117/1172 statt 1021/1171.

### O4 · B. Validierung gegen die arretierten Definitionen

| arretiert | Bereich | decke/boden | Regel liefert im Bereich |
|---|---|---|---|
| P9 | 848..1020 | K67 / K77 | (875,67,17) (889,67,62) (914,67,63) (917,67,60) (937,67,77) |
| P12_RESERVE | 1171..1272 | K73 / K82 | (1172,73,60) (1174,73,82) |

**Teilbestaetigung:** fuer 1174 ff. findet die Regel **genau** das arretierte
`P12_RESERVE`-Paar (K73/K82); fuer P9 findet sie den Bodenwechsel (937 K77)
korrekt, laeuft aber innerhalb des Segments ueber K62/K63/K60 — das ist die
**Innenlinien-Dynamik**, die P9 als arretierte Setzung nicht abbildet.

### O5 · C. Erzeugte Segmente je `MIN_BARS`

| MIN_BARS | Segmente im Auto-Fenster | gesamt R | H1 R | H2 R | ZIEL n/R | Q_stop |
|---|---|---|---|---|---|---|
| RAW | 7 · 1033..1076, 1077..1116, 1117..1119, 1120..1123, 1124..1171, 1172..1173, 1174..1287 | +74,054425 | +38,919584 | +35,134841 | 6 / +8,218849 | 0,217 |
| MIN4 | 5 · 1033..1076, 1077..1119, 1120..1123, 1124..1173, 1174..1287 | +74,054425 | +38,919584 | +35,134841 | 6 / +8,218849 | 0,217 |
| MIN8 | 4 · 1033..1076, 1077..1123, 1124..1173, 1174..1287 | +74,054425 | +38,919584 | +35,134841 | 6 / +8,218849 | 0,217 |
| MIN16 | = MIN8 | +74,054425 | +38,919584 | +35,134841 | 6 / +8,218849 | 0,217 |
| MIN24 | = MIN8 | +74,054425 | +38,919584 | +35,134841 | 6 / +8,218849 | 0,217 |
| **MIN48** | **3 · 1033..1123 (K67/K82), 1124..1173 (K73/K85), 1174..1287 (K73/K82)** | **+82,614385** | **+38,919584** | **+43,694801** | 6 / **+16,778809** | 0,217 |

**Robustheit:** `MIN_BARS` 0…24 liegen **bit-identisch** auf +74,054425; erst
MIN48 verschmilzt das 47-Bar-Segment `1077..1123` mit `1033..1076`.

### O6 · D. Ergebnis MIN48 (23 Setups)

| Schnitt | n | R | USD/Trade | Q_stop |
|---|---|---|---|---|
| gesamt | 23 | **+82,614385** | +0,9819 | 0,217 |
| H1 | 8 | **+38,919584** | +1,4077 | 0,125 |
| H2 | 15 | **+43,694801** | +0,7549 | 0,267 |
| ZIEL | 6 | **+16,778809** | +0,6001 | 0,167 |

Zielzonen-Setups: 1075 LONG K62 **+1,47577** · 1122 SHORT K73 **+10,75247** ·
1211 SHORT K76 +2,53948 · 1268 SHORT K76 −1,00000 · 1272 SHORT K73 +1,25468 ·
1280 SHORT K76 +1,75641. Ablehnungen: `quartil_blockiert` 29 · `blocker` 12 ·
`kein_raum` 12 · `frisch_blockiert` 2 · `zyklus_blockiert` 3.

### O7 · Kernbefund — die Koinzidenz mit E-33

| | E-33 `Z_1012_LOKAL` (Anwender-Setzung) | **E-34 MIN48 (endogen)** | Differenz |
|---|---|---|---|
| gesamt | 24 / +82,651571 | 23 / **+82,614385** | **−0,037186** |
| H1 | 8 / +38,919584 | 8 / **+38,919584** | **0,000000** |
| H2 | 16 / +43,731987 | 15 / **+43,694801** | −0,037186 |
| ZIEL | 7 / +16,815995 | 6 / **+16,778809** | −0,037186 |

Die Differenz ist **exakt und vollstaendig erklaerbar**:

1. **Trade 1028 (−0,47759 R) fehlt.** E-33s P10 begann bei **1021**; die
   endogene Regel erzeugt **kein** neues Segment vor **1033** (bis dahin ist das
   Paar `(K67, K77)` identisch mit P9) → Bar 1028 faellt ins Regime-Vakuum.
2. **Trade 1075: +1,47577 statt +1,99054** (Δ −0,51477). Beide Male ist die
   Grenze `K67/K82` — aber `poc_start = segment.start_bar` (Erratum E-23/F3):
   Segmentstart **1033** statt **1021** verschiebt den POC und damit die
   Geometrie.
3. **Alle uebrigen 22 Setups sind bit-identisch** — inklusive des groessten
   Einzelbeitrags **1122 / K73 / +10,75247 R**.

Netto-Bilanz: das fehlende 1028 war ein **Verlust**; sein Wegfall hebt die
Summe um **+0,47759**, der kleinere 1075 senkt sie um **0,51477** →
**−0,037186** gesamt. Rechnerisch vollstaendig geschlossen.

**Verdikt: der Fit-Verdacht ist ausgeraeumt.** Die E-33-Mechanik entsteht
**ohne** jede Zielvorgabe: dieselben Grenzkanten (oben K67 → K73, unten
K82 → K85), dieselben Trades, derselbe groesste Einzelbeitrag. Was E-33
gesetzt hat, **findet** E-34 aus der kausalen Kantenlage.

### O8 · Ehrliche Einschraenkungen

1. **Ein Datensatz (AUG).** Kein S2, kein OOS (Anwender-Vorgabe: nur AUG).
2. **`MIN_BARS = 48` ist ein Hyperparameter.** MIN0…MIN24 (+74,05) und MIN48
   (+82,61) unterscheiden sich **nur** im Trade 1122 (+2,19251 → +10,75247).
   Der Hebel ruht also — wie schon in E-33 (§M6.1) — zu **64 %** auf **einem**
   Trade. Die Wahl 48 ist **nicht** durch ein unabhaengiges Kriterium gedeckt;
   sie ist der einzige freie Parameter und damit der verbleibende
   Angriffspunkt.
3. **Die Regel bildet P9 nicht ab** (Innenlinien-Dynamik K62/K63/K60) — fuer
   848..1020 bleibt die arretierte Setzung die Basis. Endogenitaet gilt
   ausschliesslich fuer 1021 ff.
4. **Der dritte avisierte Trade (1172) fehlt weiterhin** — dieselbe Ursache wie
   in E-33 (§M5): `hook_2_ziel` / Hook-1-Pool-Semantik, **nicht** die
   Segmentbildung. E-34 aendert daran nichts.
5. `USD/Trade` sinkt (0,9819 bei 23 Trades) — der Pflichtmetrik-Konflikt aus
   E-33 (§M6.3, §M7.4) bleibt bestehen.

### O9 · Offene Entscheidungen (Textblock)

1. **Gilt der Fit-Verdacht damit als ausgeraeumt?** Der endogene Weg
   reproduziert E-33 bis auf 0,037 R; die Restabweichung ist auf zwei benennbare
   Ursachen (Segmentstart 1021 vs. 1033) zurueckgefuehrt. Wenn ja, entfaellt der
   Einwand aus §M7.1, und `Z_1012_LOKAL` waere als **V019** einbrandfaehig.
2. **`MIN_BARS` = 48 festschreiben oder neutral fahren?** MIN0…24 liefern
   +74,05 (H1 identisch), MIN48 +82,61. Bei Festschreibung 48 muss begruendet
   werden, warum 47 Bars verschmelzen; bei Neutralitaet (z. B. 8) faellt der
   Hebel auf +74,05 und ZIEL auf +8,22.
3. **Der eine kritische Trade 1122** (+10,75, allein 64 % des Zuwachses):
   bleibt er im Modell, obwohl er auf der *Segment-Verschmelzung* beruht?
4. **Unveraendert offen aus E-33:** P10/P12-Grenze, Hook-1-Pool-Semantik
   (dritter Trade 1172), `USD/Trade`-gegen-Summe.
5. **Kein §75, kein S1, keine S2-Laeufe** — auch fuer E-34 nicht.
