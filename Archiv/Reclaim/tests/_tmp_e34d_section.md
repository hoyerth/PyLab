## Phase 2 / E-34d (2026-09-11, u) — Kandidaten-Gate: **(a) global reisst das H1-Gate, (a) segment-lokal haelt es bit-identisch (+4,645353 R) — und Trade 1172 ist mit +7,12112 R gemessen**

### R0 · Auftrag und H1-Gate (Anwender-Frage 2)

Anwender-Gate: **jede Variante wird verworfen, die H1 (8 Trades /
+38,919584 R) auch nur um eine Nachkommastelle veraendert.** Ich trage das
Gate mit und habe es **angewandt**. Alle Varianten sind als Schalter in
`_tmp_e34_auto.py` implementiert (`--poola`, `--poolalok`, `--seglast`) und
einzeln messbar; jede ist ein **isolierter** Eingriff.

### R1 · Schritt 1 — die drei Kandidaten gegen das H1-Gate

| Variante | n | gesamt R | **H1 R** | H2 R | ZIEL n/R | `Q_stop` | `USD/Trade` | Gate |
|---|---|---|---|---|---|---|---|---|
| **MIN48 (Basis)** | 23 | +82,614385 | **8 / +38,919584** | +43,694801 | 6 / +16,778809 | 0,217 | +0,9819 | — |
| (a) **global** `--poola` | 26 | +86,448049 | **9 / +38,493863** | +47,954187 | 7 / +21,424162 | 0,231 | +0,8704 | **VERWORFEN** |
| (a) **lokal** `--poolalok` | 24 | **+87,259738** | **8 / +38,919584** | **+48,340154** | 7 / **+21,424162** | 0,250 | +0,9522 | **gehalten** |
| (c) `--seglast` | 22 | +72,578657 | **8 / +38,919584** | +33,659073 | 5 / +6,743081 | 0,227 | +0,9232 | gehalten, **ergebnis-schlecht** |

**(a) global — Gate-Verletzung exakt:** H1 erhaelt **einen** neuen Trade
(Umbau: 8 → 9), Summe **−0,425721** (neuer H1-Trade Bar **252 / K28 /
−0,42572**); zusaetzlich ein neuer H2-Trade (Bar **710 / K43 / −0,38597**).
Damit ist (a) in globaler Form **erledigt** — nicht wegen der Meinung, sondern
wegen des Gates.

**(a) lokal — Gate gehalten:** H1 **bit-identisch** (8 / +38,919584,
`Q_stop` 0,125 unveraendert). Segmentgrenzen **unveraendert** (A1 1033..1123
K67/K82, A2 1124..1173 K73/K85, A3 1174..1287 K73/K82) — der Eingriff wirkt
nur auf die Rangfolge, **nicht** auf die Etiketten.
**Was (a) lokal aendert:**

| | Trade | Wirkung |
|---|---|---|
| **neu** | **1172 / 1173 LONG K82** | **+7,12112 R** |
| neu | 1120 / 1121 SHORT K75 | −1,00000 R |
| **entfaellt** | **1075 / 1077 LONG K62** | **−1,47577 R** |
| Netto | | **+4,645353 R** |

**(c) `--seglast` — Gate gehalten, Ergebnis schlechter:** H1 bit-identisch,
aber H2 **−10,035728 R** und ZIEL 5 / +6,743081. Ursache exakt zerlegt (siehe
§R3).

### R2 · Schritt 2 — Trade 1172 (26.08. 17:00 LONG) gemessen

Unter `--poolalok` wird an Bar 1172 **K82** zum Kandidaten (Trace-Beleg:
`KANDIDAT = K82 wirksam=67.5530`), und es entsteht genau der dritte avisierte
Trade:

```
bar 1172  entry 1173  LONG  K82  R +7.12112  (H2, ZIEL)
```

**Der geometrisch als zulaessig vorhergesagte Pfad (E-34c §Q3) ist damit
bestaetigt und beziffert: +7,12112 R.** Alle **drei** avisierten Trades sind
damit rechnerisch erfasst — aber **nie gleichzeitig**: `--poolalok` **tauscht**
den 25.08.-Trade (1075 / K62 / +1,47577) gegen den 26.08.-17:00-Trade
(1172 / K82 / +7,12112). **Beide zusammen sind mit Kandidat (a) nicht
erreichbar** — der Filter macht K82 an Bar 1075 zur Aussenwand (`pos 0`), wo
die Geometrie scheitert.

### R3 · Zerlegung der (c)-Wirkung (Trade 1122, bit-exakt reproduziert)

`--seglast` veraendert die Etiketten der Kette: A1 wird von **(K67, K82)** zu
**(K78, K85)**. Damit aendert sich fuer den SHORT an Bar 1122 der
PHASE-Zielpreis `tp2` von **67,5530** (K82) auf **67,4200** (K85). Nachgerechnet
mit den Engine-Funktionen (`_reclaim_stufe`, `berechne_kausalen_histogramm_poc`,
`_c_loese_trade`) bei identischem `sl 69,7590 / entry 69,5720`:

| `tp2` | `poc` | R |
|---|---|---|
| 67,5530 (K82, Basis) | 67,6051 | **+10,65742** ≈ Basiswert +10,75247 |
| 67,4200 (K85, seglast) | 67,4754 | **+2,19251** = Variantenwert **exakt** |

Der Reproduktionswert der zweiten Zeile ist **bit-identisch** zum
`--seglast`-Lauf (`+2.19251`) — die Ursache ist damit **vollstaendig** das
geaenderte Boden-Etikett. **Verdikt: (c) ist zu verwerfen** (H1-neutral, aber
erheblicher Ertragsverlust). Der Nebenbefund "Etiketten sind am Start
eingefroren" (E-34c §Q2b) bleibt **dokumentiert**, aber **nicht geaendert**.

### R4 · Kritik am vorgeschlagenen `filtere_aktive_pool_kandidaten`

Der Entwurf ist **nicht implementierbar wie benannt** — er verwechselt zwei
verschiedene Praedikate:

- `KantenKandidat.ist_aktiv` = `_SEEdgeH.ist_aktiv_bei(k)` = **Schlaf-Fenster**
  (`schlaf_windows`). Das ist **nicht** der E-34c-Befund.
- Der tatsaechliche Defekt betrifft `_lebt(e, k)` = **Marktpraesenz**
  (letzter Kontakt innerhalb `wall_live_bars`) **zusammen mit** `dist < 0`
  (Linie liegt jenseits des Sweeps).

Ein Filter auf `ist_aktiv` haette an Bar 1172 **nichts** bewirkt. Zweitens: die
Felder `abstand_atr` und `touch_conf` werden vom Filter **nicht** konsumiert —
sie sind spekulativ. Hausregel (kein neuer Strukturaufbau ohne Bedarf): der
Kontrakt ist auf die **zwei** benoetigten Praedikate zu reduzieren, und
`parameter_schema` / `default_params` gehoeren auf Klassenebene unter den
Header-Docstring.

### R5 · Plateau-Standard (Anwender-Frage 3)

**Entscheidend ist: die Wahl ist PnL-frei.** Jeder Wert in [41, 114] liefert
**bit-identisch** +82,614385 R (§P2). Die Frage ist damit **rein
Verteidigbarkeit**, nicht Ertrag.

- **48** = Reife-Strenge, **7 Bars** ueber der unteren Klippe.
- **77** = Plateaumitte, **36 / 38 Bars** Abstand zu beiden Klippen (41 / 115).

**Empfehlung: das Intervall [41, 114] als SSoT arretieren und 77 als
Referenzwert fuehren**, 48 als dokumentierte strenge Alternative. Begruendung:
ein Wert, der 1,75 h von der Abrisskante entfernt liegt, ist gegen
datensatzspezifisches Rauschen schlechter geschuetzt als die Mitte — und die
Mitte kostet **nichts**. Die institutionelle 12-h-Erzaehlung bleibt
**verworfen** (E-34b §P3).

### R6 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34_auto.py` (Schalter `--poola`/`--poolalok`/`--seglast`) | 21.999 | `cc501c5e12432211dec14e1f191abf63db516b71361a0a8e40b388ec95b6587e` |
| `_tmp_e34_auto_MIN48_out.txt` (Basis, unveraendert) | 4.373 | `a862222e7bb461f0f9bd2accc815fc1fae808eb8d99edce7cb495b5eda118b4d` |
| `_tmp_e34_auto_MIN48_pa_out.txt` (a global) | 4.546 | `4b44374b10e4282f35be5f6bce96d1fd2a7bf82dcaef6bd9ff98cabf082e80ad` |
| `_tmp_e34_auto_MIN48_pal_out.txt` (a lokal) | 4.435 | `d53d907b48eee2746c8aa2f4e47b8db1f393593e1278f77880fdf5e3295f88c0` |
| `_tmp_e34_auto_MIN48_sl_out.txt` (c) | 4.311 | `261b61a435124deeb3a6052655a3856ea05850fdd2f0bdc4a3c55abaa827d2f0` |
| `_tmp_e34_auto_MIN48_trace1172_pal_out.txt` | 14.566 | `03538603307afe6183b1cfe98e05dbc0b9fffc4fa36022dcee0f3f3cc1810030` |

### R7 · Ehrliche Einschraenkungen

1. **Ein Datensatz (AUG).** Kein S2, kein OOS (Anwender-Vorgabe).
2. **`--poolalok` ist ein segment-lokaler Eingriff** — dasselbe Muster wie die
   E-33-`LOKAL`-Verdrahtung. Der H1-Erhalt ist nur **durch die Lokalisierung**
   erklaert; global ist die Aenderung H1-schaedlich (§R1).
3. **`Q_stop` 0,217 → 0,250 und `USD/Trade` +0,9819 → +0,9522 verschlechtern
   sich beide**, waehrend die Summe steigt — derselbe Pflichtmetrik-Konflikt
   wie in E-33 §M6.3 / §M7.4. Nach Phasen-1-D1/D2 sind **beide** Metriken
   fuehrend.
4. **Der neue Trade 1172 ueberkompensiert den Netto-Zuwachs:** er allein bringt
   **+7,12112 R**, waehrend der Netto-Zuwachs nur **+4,645353 R** betraegt — die
   Differenz von **−2,47577 R** stammt aus zwei *gegenlaeufigen* Posten
   (neuer Verlust 1120 / −1,00000 und entfallener Gewinn 1075 / −1,47577).
   Die Variante ruht damit auf **einem** Einzeltreffer, der zwei negative
   Nebeneffekte mitfinanzieren muss.
5. **Der Tausch ist erzwungen:** mit (a) ist immer nur **einer** der beiden
   Trades (1075 **oder** 1172) erreichbar.

### R8 · Offene Entscheidungen (Textblock)

1. **Kandidat (a) lokal tragen?** H1 bit-identisch, gesamt +87,259738
   (Δ +4,645353), aber `Q_stop` und `USD/Trade` verschlechtern sich und der
   Gewinn ist ein **Tausch** (1075 raus, 1172 rein). Ohne Freigabe kein
   Einbrand.
2. **Kandidat (b) (Sweep-Bar-Kausalitaet im Touch-Gate)**: ausdruecklich
   **nicht** gebaut. Der Mentor-Einwand (Aufweichung `b+2`) ist sachlich
   begruendet; ich empfehle, (b) **nicht** zu verfolgen, solange (a) lokal die
   Ursache ebenfalls trifft.
3. **Kandidat (c)**: **gemessen und verworfen** (§R3) — kein Handlungsbedarf
   ausser der Dokumentation.
4. **Plateau:** [41, 114] als SSoT, Referenzwert **77** (Empfehlung §R5) oder
   weiter **48**?
5. **Klaerung zum Kontrakt-Entwurf:** die `ist_aktiv`-Semantik ist zu
   korrigieren (Marktpraesenz `_lebt`, nicht Schlaf-Fenster) — erst danach
   kann ein V019-Vertrag spezifiziert werden. **V019 bleibt bis dahin
   unspezifiziert.**
6. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.**
