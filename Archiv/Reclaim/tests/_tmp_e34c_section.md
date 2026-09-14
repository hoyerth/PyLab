## Phase 2 / E-34c (2026-09-11, t) — Bar-1172-Audit: **die E-33-Diagnose war am Symptom richtig und an der Ursache falsch** — nicht Hook-1, sondern die `pos`-Semantik in `_kandidat`

### Q0 · Auftrag

Anwender-Leitfragen: (1) Plateau-Kanon bestaetigen, (2) Trade 1172 rein lesend
aufdecken, (3) Freigabe Schritt 1. Umgesetzt: **Lese-Audit** ueber einen neuen,
optionalen Trace (`--trace <bar>` in `_tmp_e34_auto.py`, rein lesend, keine
Logikaenderung) plus gezielte Reproduktionsrechnung.

**Fidelity-Kontrolle:** die Parametrisierung aus E-34b ist **ergebnisneutral** —
`_tmp_e34_auto_MIN48_out.txt` hat **unveraendert** denselben SHA256 wie in
E-34 §O2 (`a862222e7bb461f0f9bd2accc815fc1fae808eb8d99edce7cb495b5eda118b4d`).

### Q1 · Korrigendum zu E-34 §O7.2 — der 1075-Delta hat NICHTS mit `poc_start` zu tun

Die Engine setzt **`poc_start = 0`** (Zeile 2393, Balance-Beginn), **nicht** den
Segmentstart. Die in E-34 §O7.2 gegebene Erklaerung ("`poc_start =
segment.start_bar`") ist **falsch** und wird hiermit zurueckgezogen.

Die gemessene Ursache ist die **unterschiedliche Segment-DECKE** (= anderes
Ziel `tp2`):

| Variante | Segment @1075 | decke | `tp2` | poc | R |
|---|---|---|---|---|---|
| E-33 `Z_1012_LOKAL` | P10 (1021..1170) | **K73** | **69,6380** | 67,8294 | **+1,99054** |
| E-34 MIN48 | A1 (1033..1123) | **K67** | **69,8990** | 67,8359 | **+1,47577** |

Beide Pfade sind geometrisch gueltig (`sl 67,3700 < entry 67,8260 < poc < tp2`);
die Differenz von **−0,51477 R** entsteht vollstaendig aus dem hoeheren Ziel
(69,8990 statt 69,6380). Nachgerechnet mit `_c_loese_trade` der Engine,
bit-identisch reproduziert.

### Q2 · Bar 1172 — Markt- und Kantenbefund (AUG, MIN48, endogen)

Markt: `hi 67,9420 · lo 67,4940 · cl 67,5980` (Bar 1172),
`op[1173] = 67,5890`, `op[1174] = 67,9060`.
Aktives Segment: **A2 = 1124..1173 (decke K73, boden K85)**.

| Kante | wirksam | existiert | lebt | etabliert | `touch_conf` | letzter **bestaetigter** Docht | rohe Dochte ≥ 1050 |
|---|---|---|---|---|---|---|---|
| K73 | 69,6380 | True | True | True | 4 | 1122 | 1122, 1211, 1272 |
| **K85** | 67,4200 | True | **False** | True | **1** | 1075 | **1075** |
| **K82** | 67,5530 | True | **True** | True | **2** | 1056 | 1056, **1172**, 1259 |
| K62 | 67,7830 | True | False | True | 4 | 1063 | 1052, 1063, 1176, 1256 |
| K60 | 67,9750 | True | True | True | 4 | 1165 | 1165, 1183, 1193, 1244 |

**Die drei Antworten des Audits:**

1. **Welcher Status lag fuer K82/K85 an Bar 1172 vor?**
   K85 = *existierend, aber schlafend* (`lebt=False`, **1** bestaetigter Docht);
   K82 = *existierend und lebend*, aber nur **2** bestaetigte Dochte.

2. **Bleibt K82 im Pool, wenn K85 freigegeben wird? — JA.**
   `hook_1_freigabe_kid` liefert fuer (1172, LONG) `seite_kid =
   seg.boden.kid = 85`. Der Pool-Filter entfernt **K85** — und K85 ist
   **ueberhaupt nicht im Pool** (kein `touch_conf >= 2`, kein Primaer-Anker).
   Der Filter ist an diesem Bar ein **No-op**. Der Pool ist vor und nach dem
   Filter **identisch** (`K17 K3 K48 K60 K62 K66 K68 K71 K72 K77 K79 K82 K86`).

3. **Warum feuerte 1172 trotzdem nicht? — `pos`-Semantik, nicht Hook-1.**
   Die Kaskade in `_kandidat` sortiert den Pool **inklusive der schlafenden
   Aussenlinien** und zaehlt sie im Positionsindex mit:

   | pos | Kante | basis | `dist` % | Cascade-Verhalten |
   |---|---|---|---|---|
   | 0 | K48 | 62,5770 | −7,9 | `dist < 0`, `not _lebt` → `continue` |
   | 1 | K3 | 62,9670 | −7,2 | `dist < 0`, `not _lebt` → `continue` |
   | 2 | K17 | 65,6540 | −2,8 | `dist < 0`, `not _lebt` → `continue` |
   | **3** | **K82** | **67,5530** | **+0,0873** | `pos != 0` ⇒ **Innenlinie** ⇒ `touch_conf 2 < 3` → `continue` |
   | 4 | **K62** | **67,7830** | +0,4264 | `pos != 0`, `touch_conf 4 >= 3` → **KANDIDAT** |

   K62 → Stufe 2 (`cl[1173] >= basis`) → `entry_bar 1174`,
   `sl 67,4440 · entry 67,9060 · poc 67,8294 · tp2 69,6380`
   → **`entry > poc`** → **`kein_raum`** (einziger Ablehnungsgrund des Bars).

**Damit ist die E-33-§M5-Diagnose zu korrigieren.** Sie lautete: "K82 wird vom
Hook-1 als sweep-bildende Wand aus dem Pool entfernt". Das galt fuer die
**manuelle** P12-Setzung (boden K82). Unter der **endogenen** Segmentierung ist
der Boden **K85**; die Freigabe trifft eine schlafende Linie, K82 **bleibt** im
Pool — und scheitert erst am **V-S-≥-3-Gate fuer Innenlinien**. Der Defekt ist
die **`pos`-Indexierung ueber schlafende Pool-Mitglieder**, nicht der Hook.

**SHORT bei 1172:** `kd = None` — `hi 67,9420` erreicht keine lebende OBEN-Wand
(K73 lebend, 69,6380); die Kaskade endet mit "lebende Wand nicht erreicht".

### Q2b · Wurzelmechanismus — die Wand kann ihren eigenen Sweep-Docht nicht mitzaehlen

Der entscheidende Messwert steht in der rechten Spalte von §Q2: **K82 hat einen
rohen Docht auf Bar 1172 — genau dem Sweep-Bar selbst** (`lo 67,4940 <
67,5530`). Dieser Docht ist zum Zeitpunkt der Entscheidung **noch nicht
bestaetigt** (Pivot-Kausalitaet `b + 2 <= k`); er zaehlt erst ab Bar **1174**.

Damit gilt an Bar 1172 exakt:

```
K82 ist nach der ENGINE-Lebendigkeit praesent   (_lebt: roher Docht 1172 >= 1076)
K82 hat aber nur touch_conf = 2                 (1056 war der letzte bestaetigte)
V-S-Gate fuer Innenlinien verlangt >= 3         (min_touches_handelbar)
=> die Wand scheitert um GENAU EINEN Touch
```

**Der Mechanismus ist strukturell, nicht datenspezifisch:** an dem Bar, an dem
eine Linie gesweept wird, kann sie ihren eigenen sweep-bildenden Docht nicht in
`touch_conf` verbuchen. Als **Aussenlinie** (`pos == 0`) ist das irrelevant —
dort greift Q1 "die Wand handelt". Genau in diese Rolle kommt K82 aber nicht,
weil der Positionsindex durch schlafende Pool-Mitglieder verschoben ist (§Q2
Punkt 3). **Zwei Mechanismen greifen also ineinander:** die `pos`-Verschiebung
degradiert K82 zur Innenlinie, und das V-S-≥-3-Gate verlangt dann einen Touch,
den K82 an seinem eigenen Sweep-Bar nicht haben kann.

**Zweite Naht — die Segment-Etiketten sind am Start eingefroren:**
die Rohgrenzen lauten `1124 (K73,K85) → 1172 (K73,K60) → 1174 (K73,K82)`.
`zusammenfassen` verlaengert beim Verschmelzen nur `out[-1][1]` (das Ende);
Decke/Boden bleiben vom **ersten** Teilstueck. A2 (1124..1173) traegt daher das
Etikett **(K73, K85)** aus dem Stueck 1124..1171, obwohl ihre letzten beiden
Bars zum Rohabschnitt (K73, K60) gehoeren.

**Dritte Naht — zwei Lebendigkeits-Definitionen:** die endogene Regel nutzt
`_lebt_kausal` (**nur bestaetigte** Dochte, `b + 2 <= k`), die Engine nutzt
`_lebt` (**rohe** Dochte, Zeile 2421). An Bar 1172 sind sie uneins: K82 ist
nach der Engine lebendig (roher Docht 1172) und nach der Regel nicht (letzter
bestaetigter Docht 1056). Dieselbe 2-Bar-Kausalitaet, die §Q2b oben zum
Umkippen bringt.

Der Boden K85 ist uebrigens **nicht** gesweept worden: `lo[1172] = 67,4940`
liegt **7,4 Cent ueber** K85 (67,4200). Die Deutung "der Markt hat die
Liquiditaet tiefer abgegriffen" trifft fuer diesen Bar **nicht** zu.

### Q3 · Gegenprobe: der K82-Pfad waere gueltig (rein rechnerisch)

Wird K82 als Kandidat gesetzt (Q1-Semantik: "die erreichte Aussenwand
handelt"), ergibt die Engine-Rechnung:

| Pfad | `kd` | Stufe | `entry_bar` | `sl` | `entry` | `poc` | `tp2` | Geometrie |
|---|---|---|---|---|---|---|---|---|
| Ist (K62) | K62 | 2 | 1174 | 67,4440 | **67,9060** | **67,8294** | 69,6380 | `entry > poc` → **`kein_raum`** |
| Gegenprobe (K82) | K82 | **1** | **1173** | 67,4440 | **67,5890** | **67,6051** | 69,6380 | **`sl < entry < poc < tp2` erfuellt** |

Der K82-Pfad ist also **geometrisch zulaessig** — Bar 1172 ist **nicht** durch
fehlenden Raum blockiert, sondern durch die Kandidatenwahl. **R ist bewusst
nicht berechnet** (dafuer waere ein Variantenlauf noetig, der nicht freigegeben
ist).

### Q4 · Plateau-Kanon — bestaetigt, mit einer Einschraenkung

Die Formulierung "Reifeschwelle ≥ 41 Bars (≈ 10,25 h), Standard 48 innerhalb des
stabilen Plateaus [41, 114]" ist als **Beschreibung** korrekt und wird
getragen. **Nicht** getragen wird das Wort *konservativ* im Sinne von
Robustheit: `48` liegt **nur 7 Bars (≈ 1,75 h) ueber der unteren Klippe**. Ein
Plateau-Mittelwert (≈ **77**) haette maximalen Abstand zu **beiden** Klippen
(41 und 115). Wer 48 waehlt, waehlt Reife-Strenge, nicht Klippen-Sicherheit.

**Zwingende Einschraenkung:** das Plateau **[41, 114] ist AUG-spezifisch** (es
entsteht aus dem konkreten Rohsegment 1077..1116 = 40 Bars). Eine
Verallgemeinerung verlangt S2 — ausdruecklich **nicht** gefahren
(Anwender-Vorgabe).

### Q5 · Bewertung des vorgeschlagenen `PhasenReifeKonfiguration`-Vertrags

Kein Einbrand, nur Pruefung (Schritt 3 bleibt **unspezifiziert** bis Freigabe):

1. `Final` **zusammen mit** `@dataclass(frozen=True)` ist redundant — `frozen`
   genuegt; `Final` in Dataclass-Feldern verunsichert nur den Typpruefer.
2. **41/114** sind **empirische AUG-Messwerte**, keine Regel. Sie gehoeren als
   dokumentierte Konstanten in den Adapter (analog `BENCHMARK_V014_H2_R`,
   `QUARTETT_V014_BARS`) — mit Herkunftsanker (Klippenkarte
   `7bfa4ec9…`, §P5).
3. Hausregel: `parameter_schema` / `default_params` gehoeren **direkt auf
   Klassenebene unter den Header-Docstring** (PineScript-Analogie).
4. **Semantik-Falle in `validiere_dauer`:** validiert wird eine
   **Segmentlaenge**, gesteuert wird aber eine **Verschmelzungsschwelle**. Ein
   gueltiges 45-Bar-Segment kann aus 40+5 verschmolzenen Bars entstehen. Die
   beiden Groessen duerfen nicht in einem Feld vermischt werden.

### Q6 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34_auto.py` (mit `--trace`) | 20.378 | `ccf9e90e6bbe91f249c2a438273b8b9f7f6462fc51001d9942e7f8528c9fc686` |
| `_tmp_e34_auto_MIN48_trace1172_out.txt` | 14.527 | `8a9e59d8a06416486a43749181aea11754efb7c8577ada0acf576da5bf486890` |
| `_tmp_e34_auto_MIN48_out.txt` (Kontrolle, unveraendert) | 4.373 | `a862222e7bb461f0f9bd2accc815fc1fae808eb8d99edce7cb495b5eda118b4d` |

### Q7 · Offene Entscheidungen (Textblock)

1. **Plateau-Kanon:** Fassung "Reifeschwelle ≥ 41 Bars, Standard 48 innerhalb
   [41, 114]" — mit der Korrektur, dass `48` **nicht** klippen-konservativ ist
   (7 Bars Abstand). Alternativ einen mittleren Wert (≈ 77) als Standard.
2. **Trade 1172:** die Ursache ist jetzt exakt lokalisiert (§Q2b: die Wand kann
   an ihrem eigenen Sweep-Bar den sweep-bildenden Docht nicht mitzaehlen, und
   die `pos`-Verschiebung zwingt sie in das V-S-≥-3-Gate). Soll ein
   **Variantenlauf** (nur AUG, kein Einbrand) pruefen, was die Gueltigmachung
   des K82-Pfads fuer H1/H2/ZIEL bedeutet? Der Pfad ist **geometrisch
   zulassig** (§Q3), die PnL-Wirkung ist **ungemessen**.
3. **Zielrichtung der Korrektur — drei Kandidaten, bewusst nicht praejudiziert:**
   (a) `pos` nur ueber **lebende** Pool-Mitglieder zaehlen;
   (b) die Sweep-Bar-Kausalitaet im `touch_conf`-Gate beruecksichtigen
       (der aktuelle Bar als +1);
   (c) die Segment-Etiketten beim Verschmelzen aus dem **letzten** Teilstueck
       nehmen.
   Kein Kandidat ist gemessen. Jeder wirkt **nicht** zielzonen-lokal.
4. **Hinweis zur Vorsicht:** alle drei Kandidaten wirken an **jedem** Bar mit
   schlafenden Aussenlinien und beruehren potenziell auch H1 — vor jedem Lauf
   ist die H1-Invarianz zu pruefen.
5. **V019-Vertrag:** bleibt bis zur Freigabe **unspezifiziert**; die
   Konstruktionshinweise aus Q5 sind Vorbedingungen.
6. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.**
