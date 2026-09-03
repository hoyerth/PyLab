# Makro-Swings Experiment (Isolierte Schwunggrößen-Skalierung)

> **Kommunikation:** Deutsch · **Code/Bezeichner:** Englisch (Regel).
> **Anlage:** 2026-09-03 · **Status:** In Konzeption (Untersuchungsphase)
> **Referenz-Code:** `scripts/phasen_makro_swings.py`
> **Schutz-Axiom:** `docs/RECLAIM.md` und `docs/reclaim_signal_loop_design.md`
> bleiben **unveränderlich eingefroren** auf Stand v0.4.x (+293.35R OOS,
> S1+S2 kumuliert). Produktions-Baseline `scripts/phasen_volumen_profil.py`
> bleibt **unangetastet** (kein Diff, Working-Tree sauber).
> **Ziel:** Konsolidierung der 12 August-Phasen in Richtung der 4
> institutionellen Makro-Zonen (R1–R4) ohne Verlust der Signal-Asymmetrie.

**Arbeitsmodus (Mentor, 03.09.2026):** Strikt Untersuchungs-, Analyse- und
Dokumentationsmodus. Kein Sandbox-Lauf, keine Tests, kein Kompilieren, kein
Schreiben von Feature-Code oder Bugfixes — bis der Prüfbericht vorgelegt und
freigegeben ist. Dieses Dokument ist das **isolierte Tracking-Dokument für
alle Arbeiten an den Makro-Schwüngen**.

---

## 1. Schutz-Invarianten (verbindlich)

| # | Invariante |
|---|---|
| I1 | `scripts/phasen_volumen_profil.py` bleibt unverändert (Produktions-Baseline). |
| I2 | `docs/RECLAIM.md` (Session-State) und `docs/reclaim_signal_loop_design.md` (v0.4.x-Designvertrag) bleiben eingefroren. |
| I3 | Alle Experimente laufen ausschließlich gegen die isolierte Arbeitskopie `scripts/phasen_makro_swings.py` (eigene Artefakt-Pfade, Commit `bd40ad3`). |
| I4 | Testdateien/-DBs nur unter `test/`; Temp-Helper nach Nutzung löschen. |
| I5 | Quantitativer Vergleichs-Benchmark: v0.4.x-Referenzzahlen (§3), bitgenau. |

---

## 2. Problemdiagnose — Der Zerfall von R1 (Mentor-Urteil)

Die institutionelle Makro-Zone R1 (UPPER 66.45, 11.08. 03:45 → 18.08. 03:00)
sollte über ~7 Tage als **eine** Phase bestehen bleiben. Der Code zerlegt sie
jedoch in die Mini-Phasen 2, 3, 4 und 5 — insgesamt zerfällt das August-Fenster
in 12 Phasen statt in die 4 Makro-Zonen R1–R4.

### 2.1 Abbruch-Gleichungen im Code (`scripts/phasen_makro_swings.py`, Z. 685–698)

```text
Bruch UP:   close[j] > h_ref + TOL   UND   close[j+1] > h_ref + TOL
Bruch DOWN: close[j] < l_ref - TOL   UND   close[j+1] < l_ref - TOL
```

- **Statisches** `TOL = 0.34` USD (Z. 201).
- Zeitschranke: Abbruch-Check erst ab `(j - i) >= MIN_PHASE_CANDLES` (= 46
  Candles = 11.5 Stunden, Z. 205/685).
- Referenzkante: `h_ref = max(U, birth_h)` bzw. `l_ref = min(L, birth_l)`
  (Z. 688–691) — die Schnittmengen-Kante wird also nie unter das Geburts-Level
  abgesenkt.
- Abbruch erfordert **zwei aufeinanderfolgende M15-Closes** jenseits der
  Toleranz (Bestätigungs-Bar).

### 2.2 Anatomie des Zerfalls — Hypothese vs. Real-Befund

**Hypothese (Mentor-Urteil, vor Trace):** Die Code-Phase 2 starte am 11.08.
03:45 (= R1_U-Beginn) und breche am 12.08. durch zwei Closes über
66.45 + 0.34 = **66.79** nach oben; die Phasen 3/4 seien kurze
Zwischenkonsolidierungen, Phase 5 (14.08. 03:00) breche nach unten.

**Real-Befund (statische Trace-Analyse §4.2, bitgenau zur Produktion):**
Die Hypothese ist **teilweise widerlegt** — entscheidend für die Diagnose:

| Hypothese | Realität (Code-Segmentierung) |
|---|---|
| Phase 2 startet 11.08. 03:45 | **Keine** Code-Phase startet dort. Phase 2 = 10.08. 16:30 → Bruch 11.08. 07:15 (down, `l_ref`=65.567). |
| 12.08.-Abbruch durch 2 Closes über 66.79 | **Nein.** Der up-Bruch am 12.08. 08:30 (Phase-3-Ende) geschah an `h_ref`=**65.198** mit Closes 65.725/65.903 — der Markt stand 0.55–0.73 USD **unter** der institutionellen 66.45. |
| Phasen 3/4 = kurze Fragmente | Phase 3 lebte 97 Candles (24 h), Phase 4 sogar 162 Candles (40.5 h) — die 46er-Zeitschranke war längst gefallen. |
| Phase 5 bricht „bei Rückkehr nach oben" | Phase 5 (14.08. 03:00 → 18.08. 03:15) brach **down** am 18.08. 17:00 an `l_ref`=64.198 (Closes 63.789/63.649) — nach der 66.4-Rallye, nicht durch sie. |

**Konsequenz:** Die Fragmentierung von R1 ist **kein** Abbruch an der
Makro-Kante 66.45 (dort fand nie ein Bruch statt), sondern das Sterben
**lokaler Zwischen-Kanten** (65.198 / 64.336 / 64.198), die der Code
innerhalb der Makro-Balance als eigenständige Phasen etabliert. Die
Retail-Falle ist damit präziser: nicht „TOL zu eng an der Makro-Kante",
sondern „der Code erkennt die Makro-Balance nicht als Bezug — er misst
Ausbrüche an lokalen Schnittmengen, die die Makro-Bewegung (z. B. Anstieg
65.2 → 66.45) gar nicht abbilden".

### 2.3 Die Retail-Falle (Kernbefund, durch §4.2 präzisiert)

Der Algorithmus verwechselt **Absorption an der Kante** mit einem
**Trend-Ausbruch**. Bei institutioneller Liquiditätsjagd (Market Maker / Stop-
Fischen) wird der Kurs 40–60 Cents über die Kante geschoben, um Stops zu
triggern, bevor der Reversal einsetzt. Das starre Toleranzband von 0.34 USD
kapituliert genau in diesem Moment und beendet die Phase — obwohl die
Makro-Balance (R1) intakt bleibt.

**Präzisierung nach Trace (§4.2):** Im AUG-Befund kapitulierte das Band
nicht an der Makro-Kante 66.45 selbst (dort kein Bruch), sondern an **engen
lokalen Zwischen-Kanten** (65.198/64.336/64.198), die der Code innerhalb von
R1 als eigenständige Phasen etabliert. Die Bewegungsamplitude von 0.37–0.71
USD über diese lokalen Kanten ist die normale Makro-Balance-Bewegung — der
Bruch-Detektor hat keine Referenz auf die übergeordnete Zone.

---

## 3. Eingefrorene Referenz-Benchmarks (v0.4.x, Vergleichsbasis)

| Fenster | Zeitraum | Baseline (v0.4.x ohne Makro) | `--macro-live` v0.4.x |
|---|---|---|---|
| AUG | 2026-08-10 → 2026-08-28 | 27 Sig / +24.97R / 44.4 % | 25 Sig / **+34.87R** / 52 % |
| S1 | 2026-02-05 → 2026-08-28 | 201 Sig / +197.26R | 199 Sig / +199.65R |
| S2 | 2025-01-01 → 2025-12-01 | 210 Sig / +99.88R | 216 Sig / +93.70R |
| **S1+S2** | — | +297.14R | **+293.35R** (Ziel ≥ +292.14R erfüllt) |

Jede Hebel-Veränderung an den Abbruch-Faktoren muss gegen diese Zahlen
validiert werden; die Signal-Asymmetrie (AUG-P5-Schutz, S1/S2-Bilanz) darf
nicht verloren gehen.

---

## 4. Testaufbau / Explorationsplan (Step-by-Step)

1. **Dokumenten-Sicherung** (dieses Dokument, erledigt am 03.09.2026).
2. **Statische Trace-Analyse der Abbruchstellen in August:** tabellarische
   Erfassung der Bar-Indizes, Timestamps, Closes und Referenzkanten, an denen
   R1 in Phase 2, 3, 4 und 5 zerrissen wurde (reine Lese-Analyse an
   `scripts/phasen_makro_swings.py` + DuckDB-Daten, kein Lauf). → **Erledigt
   am 03.09.2026, siehe §4.2** (Freigabe: reines Lese-Skript
   `test/tmp_makro_swings_trace.py`, DuckDB read_only; Hilfsfunktionen per
   AST aus der Arbeitskopie extrahiert → bitgenau; Ergebnis deckungsgleich
   mit Produktions-Artefakt `test/tmp_macro_live_out.txt`).
3. **Modellierung der Makro-Abbruch-Hebel** (§5) als mathematische Spezifikation.
4. **Prüfbericht** vor jeglicher Code-Anpassung (Interview/Review mit Mentor).

---

## 4.2 Statische Trace-Analyse (AUG) — Abbruch-Matrix

**Trace-Skript:** `test/tmp_makro_swings_trace.py` (DuckDB read_only,
Fenster 2026-08-10 → 2026-08-28, 1288 Candles, 344 Pivots).
**Segmentierung:** 12 Phasen, 11 Abbrüche (Phase 12 endet am Datenende).
Phasen-Ende = letzter Touch der Gegenseite (TOL_TOUCH=0.15); Abbruch-Bar
j = erste Bar des 2-Close-Bruchs. Overshoot = `|close − ref| − TOL`
(positiv = über der Bruch-Schwelle). R1-Zeitfenster (11.08. 03:45 →
18.08. 03:00) umfasst das Ende von Phase 2 sowie die Phasen 3, 4, 5.

| Phase | Start (ts) | Ende (Touch) | Abbruch-Bar j | Abbruch-Zeit | Dir | Referenzpreis (ref) | close[j] | close[j+1] | Overshoot[j] | Overshoot[j+1] | R1-Bezug |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10.08 00:00 | 10.08 15:45 | 66 | 10.08 16:30 | up | 64.325 | 64.693 | 64.722 | +0.028 | +0.057 | — (vor R1) |
| **2** | **10.08 16:30** | **11.08 05:30** | **121** | **11.08 07:15** | **down** | **65.567** | 65.038 | 64.704 | +0.189 | +0.523 | R1-Start überdeckt |
| **3** | **11.08 07:15** | **11.08 21:15** | **218** | **12.08 08:30** | **up** | **65.198** | 65.725 | 65.903 | +0.187 | +0.365 | in R1 |
| **4** | **12.08 08:30** | **12.08 14:30** | **380** | **14.08 03:00** | **down** | **64.336** | 63.926 | 63.967 | +0.070 | +0.029 | in R1 |
| **5** | **14.08 03:00** | **18.08 03:15** | **620** | **18.08 17:00** | **down** | **64.198** | 63.789 | 63.649 | +0.069 | +0.209 | in R1 |
| 6 | 18.08 17:00 | 19.08 07:15 | 715 | 19.08 17:45 | up | 65.490 | 65.877 | 65.929 | +0.047 | +0.099 | — (R1-Ende) |
| 7 | 19.08 17:45 | 20.08 14:00 | 802 | 20.08 16:30 | up | 67.201 | 67.706 | 68.371 | +0.165 | +0.830 | — |
| 8 | 20.08 16:30 | 21.08 03:00 | 848 | 21.08 05:00 | up | 68.320 | 68.846 | 68.711 | +0.186 | +0.051 | — |
| 9 | 21.08 05:00 | 25.08 02:00 | 1030 | 25.08 04:30 | down | 68.370 | 67.653 | 67.743 | +0.377 | +0.287 | — (R3) |
| 10 | 25.08 04:30 | 25.08 15:45 | 1082 | 25.08 17:30 | up | 68.220 | 68.836 | 68.813 | +0.276 | +0.253 | — |
| 11 | 25.08 17:30 | 26.08 07:30 | 1171 | 26.08 16:45 | down | 68.495 | 67.877 | 67.598 | +0.278 | +0.557 | — |
| 12 | 26.08 16:45 | 27.08 22:45 | — | — | kein Break | — | — | — | — | — | Datenende |

### 4.2.1 Kernbefunde (R1-Fragmentierung, Phasen 2–5)

1. **Kein Bruch an der Makro-Kante 66.45.** Die drei R1-internen Abbrüche
   (Phasen 3/4/5) fanden an lokalen Kanten 65.198 / 64.336 / 64.198 statt.
   Der Markt bewegte sich innerhalb von R1 (66.45 … 64.24), ohne die
   Oberkante je mit 2 Closes zu überschreiten — die Fragmentierung entsteht
   **unterhalb** der institutionellen Makro-Zone.
2. **Kein Zeit-Hebel-Effekt:** Phase 3 lebte 97 Candles, Phase 4 sogar 162
   Candles, Phase 5 240 Candles. Die Schranke `MIN_PHASE_CANDLES=46` war in
   allen Fällen längst gefallen → eine reine Erhöhung der Mindestlaufzeit
   (Hebel 1) kann diese Abbrüche **nicht** verhindern.
3. **Overshoot-Verteilung:** Die Überschreitungen über die Bruch-Schwelle
   (`ref ± TOL`) liegen bei +0.03 … +0.53 (R1-relevant: 0.19/0.37, 0.07/0.03,
   0.07/0.21). Brutto über die lokale Kante: 0.37 … 0.71 USD. Das ist weder
   reines Rauschen (0.10) noch ein Makro-Impuls (1.50), sondern die
   **normale Bewegungsamplitude innerhalb von R1** — der Code behandelt die
   Makro-Balance-Bewegung als Phasenbruch, weil seine Referenz die enge
   lokale Kante ist.
4. **Diagnose-Schärfung (Retail-Falle präzisiert):** Nicht „TOL kapituliert
   an der Makro-Kante beim Stop-Run", sondern: Der Code **etabliert
   Zwischenkonsolidierungen innerhalb von R1 als eigenständige Phasen**
   (MIN_ESTABLISH=4 nach wenigen Touches erfüllt) und misst deren Bruch an
   der engen lokalen Schnittmenge. Die Makro-Balance (66.45/64.24) existiert
   im Segmentierungs-Gedächtnis nicht — genau die Lücke, die das
   Persistenz-Design (`docs/reclaim_makro_persistenz_design.md` §6.4)
   adressiert.
5. **Referenz für Hebel-Dimensionierung:** Ein Makro-TOL müsste die
   R1-Bewegungsamplitude (≥ 0.7 USD über lokale Zwischenkanten, bis 2.2 USD
   Range-Breite) absorbieren können, ohne echte Trendwechsel (z. B. der
   R1-Verlassen-Drop auf 63.7 am 18.08.) zu verschlucken.

---

## 5. Abbruch-Hebel-Kandidaten (Gegenüberstellung)

### Hebel 1 — Mindestlaufzeit `MIN_PHASE_CANDLES` (Z. 205, aktuell 46 = 11.5 h)
- **Idee:** Anhebung auf mehrtägige Basis (z. B. 96–192 Bars = 1–2 Tage), damit
  junge Zwischenkonsolidierungen (Phasen 3/4) gar nicht erst als eigenständige
  Phasen abgespalten werden.
- **Eingriffsort:** Z. 685 (`(j - i) >= MIN_PHASE_CANDLES`), rein parametrisch.
- **Risiko:** Phase 2 brach, obwohl die Zeitschranke (>46) gefallen war — die
  Erhöhung allein verhindert den 12.08.-Abbruch **nicht**, sie unterdrückt nur
  die Ultrakurz-Segmente und senkt die globale Segmentierungs-Auflösung.
  Außerdem verändert sie die Phasen-Zählung (Evidenz-Basis der Makro-
  Persistenz) fundamental.

### Hebel 2 — Dynamisches `TOL` an Makro-Volatilität gekoppelt (f × range_ref)
- **Idee:** Ersatz des statischen 0.34-USD-Bands durch eine
  volatilitätsproportionale Schwelle (z. B. `TOL = f × range_ref`, wobei
  `range_ref` ein robustes Range-/ATR-Maß der bisherigen Phase ist).
- **Eingriffsort:** Z. 692/695, Referenzgröße aus der bisherigen Phase
  (kausal, kein Lookahead).
- **Begründung:** Stop-Jagd (40–60 Cents) skaliert mit der Marktvolatilität;
  die Retail-Falle ist eine **Schwellenfrage** — genau hier liegt die
  Fehlstelle des starren Bands.

### Hebel 3 — Hystereseband aus der Value-Area-Breite (VAH/VAL)
- **Idee:** Ein Bruch gilt erst als Makro-Bruch, wenn der Preis die gesamte
  Value-Area-Hülle (VAH–VAL, ~70 %-Volumen-Balance) nachhaltig verlässt —
  Absorption fischt innerhalb/knapp außerhalb der VA, echte Trendwechsel
  durchmessen die Hülle.
- **Eingriffsort:** Abbruch-Bedingung Z. 685–698; VA-Bausteine existieren
  bereits (`build_volume_profile`, `compute_volume_zone`), werden aber erst
  **post-hoc** je fertiger Phase berechnet (Z. 830 ff.) — für den In-Loop-
  Check wäre eine kausale/rollierende VA der bisherigen Phase nötig
  (größter Umbau, konzeptionell sauberste Institutionen-Abbildung).

**Vorläufige Einordnung (IDE, aktualisiert nach Trace-Erkenntnissen §4.2):**

- **Hebel 1 ist empirisch widerlegt als R1-Lösung:** Die R1-internen Phasen
  3/4/5 lebten 97/162/240 Candles — alle weit über jeder denkbaren
  Mindestlaufzeit (96–192). Die Fragmentierung ist keine Zeitfrage.
- **Hebel 2/3 wirken nur, wenn die Referenzkante die Makro-Zone ist:** Ein
  größeres (dynamisches) TOL an der *lokalen* Kante 65.198 würde die Brüche
  zwar verschieben, aber die eigentliche Fehlklassifikation (Zwischen-Range
  = eigenständige Phase) nicht heilen. Der Bezug muss die übergeordnete
  Balance sein (R1: 66.45/64.24), sonst skaliert das Band nur die lokale
  Fehlmessung.
- **Konsequenz für die Hebel-Definition:** Die Hebel müssen gegen die
  **Phasen-Etablierung** (wann darf eine Zwischenkonsolidierung innerhalb
  einer bestehenden Makro-Balance überhaupt neue Kanten bekommen?) oder
  gegen die **Bruch-Referenz** (Bruch erst beim Verlassen der Makro-Balance,
  nicht der lokalen Schnittmenge) gerichtet sein — siehe §4.2.1 Punkt 4/5.
  Die quantitative Prüfung (Sweep) folgt nach Freigabe der Hebel-Spezifikation.

---

## 5.1 Das strukturelle Missverständnis & die Hierarchische Balance-Hülle (Mentor-Urteil)

### 5.1.1 Der Denkfehler der Baseline-Architektur

Die Engine löst **Zonen-Findung** und **Bruch-Erkennung** mit denselben zwei
Variablen (`U`, `L`). Sobald sich im Inneren einer Range für einige Stunden
ein lokales Pivot-Cluster bildet (z. B. 65.198), schrumpft die Phase ihre
Grenzen auf diese lokalen Pivots zusammen (`level_schnittmenge` = Dichte-
Zentrum, Remove-Tail). Läuft der Markt danach zurück zur eigentlichen
Makro-Grenze (66.45), misst die Engine einen „Trend-Ausbruch".

**Live-Evolutions-Beleg (Artefakt `test/tmp_macro_live_out.txt`, Phase 3):**
Die U-Kante wanderte real **nach unten** (Verengung):
`Tue 14:30 65.294 → Tue 16:15 65.221` (final 65.198). Die Etablierung erfolgte
mit enger Spanne U−L ≈ 0.995 USD, die Kante wurde dann auf das Innencluster
65.198 abgesenkt — und die Bewegung 65.725/65.903 (nur R1-Mitte!) löste den
Bruch gegen `h_ref = 65.198` aus. Ebenso Phase 2: etabliert mit U=65.847 /
L=65.695 (Spanne **0.15 USD**!), gebrochen durch den R1-Eintritts-Drop.

**Konsequenz für Hebel 2 (TOL):** Ein statisches oder dynamisches TOL auf die
lokale Zwischenkante 65.198 anzuwenden kuriert nur das Symptom. Gegen einen
Ausbruch bei 65.90 bräuchte es `TOL > 0.75` USD — bei einer lokalen Kante von
65.19 ist ein Puffer von 0.75 USD kein Schutzfilter mehr, sondern Willkür.

### 5.1.2 Die institutionelle Lösung: Bruch an den Extrema der Akkumulation

Ein Bruch darf **nicht** an einer beliebigen lokalen Pivot-Häufung gemessen
werden, sondern an den **Extrema der aktuellen Akkumulation**
(`max(h_acc)` / `min(l_acc)` der bisherigen Phase — kausal, kein Lookahead).
Solange der Markt innerhalb dieser Extrem-Spanne pendelt, handelt es sich um
**interne Liquidation**, nicht um einen Phasenwechsel.

```text
Aktuell (Z. 688-691):  h_ref = max(U_dichte, birth_h)      # Dichte-Zentrum (kann verengen)
                       l_ref = min(L_dichte, birth_l)
Ziel (Hülle):          h_ref = max(U_dichte, max(h_acc), birth_h)   # Rattensche Hülle
                       l_ref = min(L_dichte, min(l_acc), birth_l)
```

Damit wäre der R1-Verlauf **eine** Phase (66.45/64.24): Die Rallye 65.2 →
65.9 am 12.08. liegt unter `max(h_acc)` ≈ 66.4x der akkumulierten Phase →
kein up-Bruch. Der echte R1-Verlassen-Drop (14.08./18.08. unter 64.24−TOL)
bleibt als down-Bruch erhalten.

### 5.1.3 Antwort Leitfrage 1 — Spread-Untergrenze als Makro-Filter: **Ja**, als Etablierungs-Gate

Eine Phase soll erst als eigenständige Makro-Balance etabliert werden, wenn
ihre **aktuelle** Kanten-Spanne (`U − L` live) eine Mindestbreite erreicht.
Präzisierung:

1. **Der Filter existiert bereits, greift aber zu spät:** `MIN_SPREAD_PCT =
   1.5` (%) wird **nur post-hoc** als Handelbarkeits-Gate verwendet
   (Z. 813–819: `p.spread_pct >= MIN_SPREAD_PCT`), nachdem die Phase längst
   etabliert wurde, Kanten eingefroren und Brüche ausgelöst hat. Phase 3
   (Spanne 0.81 USD = 1.26 %) und Phase 2 (0.15–0.32 USD) wären als
   „nicht handelbar" markiert worden — aber erst **nach** ihrem zerstörerischen
   Bruch.
2. **Wirkort:** Die Schwelle muss auf die **Etablierung** (`est_idx`, Z. 672)
   wirken. Bis die live-Spanne die Mindestbreite erreicht, akkumuliert die
   Phase nur Pivots (keine Kanten-Fixierung, keine Bruch-Checks). Damit kann
   eine enge Zwischenkonsolidierung innerhalb von R1 **keine eigene Phase**
   werden — ihre Pivots bleiben Teil der übergeordneten Balance.
3. **Relativ statt absolut:** `MIN_SPREAD_PCT` (relativ) skaliert über die
   Preiszonen (S2 ≈ 30–50 USD, S1/AUG ≈ 65–70 USD). Eine absolute
   1.50-USD-Schwelle wäre bei 30 USD ≈ 5 % (zu restriktiv), bei 65 USD ≈
   2.3 %. Die relative Definition ist die saubere, vergleichbare Basis;
   die konkrete Höhe (1.5 %? 2 %?) ist Sweep-Kalibrierung.
4. **Trennschärfe AUG:** R1 = 2.21 USD (≈ 3.4 % bei 64.8). Die handelbaren
   Ranges aus dem Artefakt: 1.31–2.65 USD (1.9–4.2 %). Eine Schwelle um
   1.5 % würde Phase 2/3 (0.2–0.8 USD) ausschließen, Phase 4/5 (2.3 USD)
   zulassen — die echten R1-Verlassen-Brüche bleiben erhalten, nur die
   Mittel-Fragmentierung entfällt.
5. **Abgrenzung:** `MIN_SPREAD_PCT` darf **nicht** zugleich das
   Handelbarkeits-Gate anheben (dort ginge Signal-Selektion verloren). Es
   braucht getrennte Schwellen: Etablierungs-Spread (neu, z. B. eigenes
   `MIN_ESTABLISH_SPREAD_PCT`) vs. Handelbarkeits-Spread (bestehend).

### 5.1.4 Antwort Leitfrage 2 — Kanten-Evolution nach außen: **Ja**, als Ratschen-Hülle mit Spike-Schutz

Kanten dürfen während einer mehrtägigen Makro-Phase **nur nach außen**
expandieren (Highest-High / Lowest-Low der Pivots nachführen), **nie** auf
Innencluster verengen. Präzisierung:

1. **Bestandsaufnahme:** Eine Kanten-Entwicklung existiert bereits
   (`hist_U`/`hist_L`, Z. 678–683 mit `SHIFT_TOL=0.05`), ist aber eine
   Verfolgung des Dichte-Zentrums — und die **kann verengen** (Phase 3:
   U 65.294 → 65.198, live belegt). Genau die verengte Kante wird zur
   Bruch-Referenz.
2. **Eingriffsort:** Nicht die `U`/`L`-Definition selbst (sie bleibt für
   Phasen-Kanten/Signale erhalten), sondern die **Bruch-Referenz** in Z.
   688–691: `h_ref = max(U_dichte, laufendes max(h_acc), birth_h)` bzw.
   `l_ref = min(L_dichte, laufendes min(l_acc), birth_l)`. Die akkumulierten
   `h_acc`/`l_acc` sind kausal (Pivots seit Phasenstart); mit
   `PIVOT_LOOKBACK=2` ist ein neues Extrem beim 2-Close-Check bereits
   bestätigt.
3. **Spike-Schutz (aus Persistenz-Design §6.3):** Ein einzelner Ausreißer-
   Pivot (z. B. 66.776 in P4) darf die Hülle nicht dauerhaft aufblähen.
   Robustifizierung: Hüllen-Extrem erst nach **Bestätigung** (2. Pivot im
   `DENSITY_BAND`, analog `U_conf_ts`/`L_conf_ts`) oder als Quantil (oberes
   ~95 %-Extrem) statt rohem `max`. Spezifikations-Detail für den Sweep.
4. **Gegenprobe echte Brüche:** Der Trendwechsel nach unten (R1-Verlassen,
   14.08./18.08.) durchstößt die untere Hülle (`min(l_acc) ≈ 64.2`) um
   mehr als TOL → down-Bruch bleibt intakt. Die Hülle schluckt nur die
   **internen** Bewegungen, nicht die externen.
5. **Wechselwirkung mit Leitfrage 1:** Beide Hebel sind komplementär.
   Leitfrage 1 verhindert die **Geburt** enger Schein-Phasen; Leitfrage 2
   verhindert das **Verengen** etablierter Phasen auf Innencluster. Zusammen
   bilden sie die „Hierarchische Balance-Hülle": Etablierung erst ab
   Mindest-Spread, Bruch erst beim Verlassen der Extrem-Hülle.

---

## 5.2 Umsetzungs-Spezifikation: Hierarchische Balance-Hülle (Mentor-Realitätscheck, 03.09.2026)

**Mentor-Fallstrick 1 (relativer Spread):** Eine frische Phase startet mit
engem U/L. Wird `est_idx` erst ab `Spread ≥ 1.5 %` gesetzt, kann der Markt
vorher **unbegrenzt trenden**, ohne dass je ein Bruch-Check läuft (der
Bruch-Check Z. 685 hängt an `est_idx is not None`). Eine Phase könnte 5 USD
„weglaufen", solange L hinterherhinkt → **Not-Reißleine (Runaway-Guard) nötig**.

**Mentor-Fallstrick 2 (rohe Ratsche):** `max(h_acc)` wird durch einen
einzelnen Docht (P4-Spike 66.776) dauerhaft nach oben verzerrt → die
Ausbruchsschwelle wird durch Stop-Fischen unbrauchbar. → **Spike-Schutz
(Remove-Tail / 2-Touch-Bestätigung) ist Pflicht**.

### 5.2.1 Datenvertrag `MacroEnvelopeConfig` (frozen, in Arbeitskopie)

```python
@dataclass(frozen=True, slots=True)
class MacroEnvelopeConfig:
    """Konfiguration fuer die hierarchische Makro-Balance-Huelle."""
    # Etablierungs-Gate (Schicht 1)
    min_establish_spread_pct: float = 1.5   # relative Mindest-Spanne U-L (Sweep 1.0-2.5)
    min_establish_touches: int = 4          # Mindest-Pivots h+l (bestehend MIN_ESTABLISH)
    # Ratschen-Huelle (Schicht 2)
    envelope_spike_protection: bool = True  # Remove-Tail/2-Touch-Bestaetigung
    envelope_band: float = 0.15             # = DENSITY_BAND (Konsistenz-Zwang)
    envelope_min_touches: int = 2           # Bestaetigungs-Dichte fuer ein Huellen-Extrem
    # Not-Reissleine (Schicht 3, Runaway-Guard)
    runaway_factor: float = 2.0             # x min_establish_spread_pct (Sweep 1.5-3.0)
    runaway_min_candles: int = 12           # frueheste Schaerfung ab Phasenstart (3h)
    # Bruch
    tol_puffer: float = 0.34                # Restpuffer ueber Huelle (bestehend TOL)
```

**Verankerung:** Diese Parameter leben in der **Arbeitskopie**
`scripts/phasen_makro_swings.py`; die Produktions-Baseline
`phasen_volumen_profil.py` bleibt unberührt. Der Block ist nach Projektregel
direkt auf Klassenebene unter dem Header-Docstring am Dateianfang zu
platzieren (manuell justierbar wie PineScript-Inputs).

### 5.2.2 Schicht 1 — Etablierungs-Gate (Live-Spread, Z. 672)

**Heute:** `est_idx` wird gesetzt, sobald `U` und `L` existieren und
`n_touches(h_acc,U) + n_touches(l_acc,L) >= MIN_ESTABLISH` — **ohne**
Mindest-Spanne. Phase 2 etablierte sich mit U−L = 0.15 USD.

**Neu (Vertrag):**
```text
est_idx = j   gdw.   U != None  UND  L != None
                     UND  touches(h_acc,U) + touches(l_acc,L) >= min_establish_touches
                     UND  (U - L) / L * 100 >= min_establish_spread_pct
```
- Bis zur Etablierung akkumuliert die Phase **nur Pivots** — keine
  Kanten-Historie, keine Balance-Brüche (die laufen erst nach Etablierung).
- Damit kann eine enge Zwischenkonsolidierung innerhalb von R1 **nie** eine
  eigene Phase werden; ihre Pivots bleiben Teil der übergeordneten Balance.
- **Wichtig:** `MIN_SPREAD_PCT` (bestehend, 1.5 %) bleibt unangetastet als
  **post-hoc** Handelbarkeits-Gate (Z. 819) — getrennte Schwellen.

### 5.2.3 Schicht 2 — Ratschen-Hülle mit Remove-Tail (Bruch-Referenz, Z. 685–698)

**Zentrale Definition — bestätigtes Hüllen-Extrem (Spike-Schutz):**

```text
envelope_high(h_acc) = max{ p in h_acc : Dichte(p) >= envelope_min_touches }
envelope_low(l_acc)  = min{ p in l_acc : Dichte(p) >= envelope_min_touches }
Dichte(p)            = |{ q in acc : |q - p| <= envelope_band }|   (= DENSITY_BAND 0.15)
```

Ein **einzelner** Docht-Pivot (66.776 ohne zweiten Touch im Band) hat
Dichte = 1 < 2 → wird **verworfen** (Remove-Tail). Erst wenn ein zweiter
Test im `DENSITY_BAND` folgt, zieht das Extrem die Hülle auf. Das ist die
konsistente Übertragung des Spike-Schutzes aus `macro_persistence.py`
(Remove-Tail-Schnittmenge, Persistenz-Design §6.3: 66.776 bleibt inert, weil
die 66.7er-Zone nie in einer zweiten Phase getestet wird).

**Abgrenzung zur `level_schnittmenge` (wichtig, kein Copy-Paste):**
`level_schnittmenge` (Z. 368–402) entfernt bei UPPER **immer** das Maximum
aus dem Pool (Zentrums-Regel: konservative Unterkante des Dichte-Clusters).
Das ist für ein **Zentrum** korrekt, für eine **Hülle** jedoch falsch: Ein
**bestätigtes** Doppel-Extrem (z. B. 66.45/66.46) IST die echte Kante und
muss die Hülle definieren — würde man es immer streichen, läge die Hülle
unter der echten Kante und der erneute Test der Kante löste einen
Fehl-Bruch aus (Retail-Falle revisited). Die Hülle streicht **nur
unbestätigte** Spikes.

**Bruch-Referenz (Vertrag, Z. 688–691):**
```text
h_ref = max(U_dichte, birth_h, envelope_high(h_acc))   # falls vorhanden
l_ref = min(L_dichte, birth_l, envelope_low(l_acc))     # falls vorhanden
```
- `U_dichte`/`L_dichte` (bisherige U/L) bleiben als Untergrenze erhalten;
  die Hülle kann die Referenz nur **nach außen** erweitern (Ratschen-Charakter),
  nie nach innen verengen.
- Kausal: `h_acc`/`l_acc` enthalten nur Pivots seit Phasenstart
  (`t_prev >= phasen_start`, Z. 654–655); mit `PIVOT_LOOKBACK=2` ist ein
  neues Extrem beim 2-Close-Check längst bestätigt.
- **Ausführungs-Kanten für Reclaims bleiben unangetastet:** `U`/`L` und
  `U_final`/`L_final` (Z. 676–683, 700–701) werden **nicht** verändert —
  nur die Bruch-Referenz `h_ref`/`l_ref` in Z. 688–691.

**Wirkung auf R1:** Die Rallye 65.2 → 65.9 am 12.08. liegt unter der
bestätigten Hülle `envelope_high(h_acc)` (≈ 66.4x aus den Touches der
Gesamt-Akkumulation) → **kein** up-Bruch. Der echte R1-Verlassen-Drop
(14.08./18.08. unter `envelope_low` ≈ 64.2 − TOL) → down-Bruch bleibt.

### 5.2.4 Schicht 3 — Not-Reißleine (Runaway-Guard, Zustand „nicht etabliert")

**Zweck:** Verhindert den pathologischen Zustand „`est_idx` nie gesetzt →
Phase läuft unbegrenzt bis Datenende", wenn der Markt vor Erreichen des
Etablierungs-Spreads in einen echten Trend läuft.

**Formale Definition (kausal, 2-Close-bestätigt, erst nach Mindestlaufzeit):**
```text
Aktiv, falls:  est_idx is None  UND  (j - i) >= runaway_min_candles
Referenz:      p0 = close[i]                       (Close der Phasenstart-Bar, fixiert)
Schwelle:      runaway_tol = runaway_factor * p0 * min_establish_spread_pct / 100
               (Default: 2.0 x 1.5 % = 3.0 % von p0; bei 65 USD ≈ 1.95 USD)
Bruch UP:      close[j] > p0 + runaway_tol  UND  close[j+1] > p0 + runaway_tol
Bruch DOWN:    close[j] < p0 - runaway_tol  UND  close[j+1] < p0 - runaway_tol
```
- Wirkung identisch zum normalen Bruch: Move registrieren, Phase beenden,
  neue Phase bei `j` starten (`brk_dir`/`brk_kante` dokumentieren die
  Reißleine mit `brk_kante = p0 ± runaway_tol`).
- `runaway_min_candles = 12` (3 h) verhindert Ping-Pong direkt nach einem
  Bruch: Eine frische Phase bekommt ein Warmup-Fenster, in dem sie Pivots
  sammeln und eine Balance formen darf.
- **Sobald `est_idx` gesetzt ist, ist die Reißleine aus** — ab dann
  übernimmt die Balance-Hülle (Schicht 2); ein echter Ausbruch durchstößt
  die Hülle und endet die Phase normal.
- **Eigenschaft (gewollt):** In einem echten Trend ohne Balance segmentiert
  die Reißleine in ~`runaway_tol`-Schritten (3 %-Chunks). Das ist der
  dokumentierte Notfall-Modus — die Balance-Erkennung (Schichten 1+2) ist
  der Hauptpfad und verhindert das Chunking in Range-Regimen (R1-artig).

### 5.2.5 Umsetzungs-Vertrag (minimal-invasiv, in Arbeitskopie)

| # | Eingriff | Ort (heute) | Änderung |
|---|---|---|---|
| E1 | Config-Block `MacroEnvelopeConfig` + Helfer `_envelope_extrem(prices, typ)` | Dateianfang / nach Z. 214 | additiv, Defaults = heutiges Verhalten bis auf neue Schwellen |
| E2 | Etablierungs-Gate | Z. 672 | + `(U-L)/L*100 >= min_establish_spread_pct` |
| E3 | Bruch-Referenz | Z. 688–691 | `h_ref/l_ref` um `envelope_high/low` erweitern |
| E4 | Not-Reißleine | Z. 685–698 | neuer Zweig im Abbruch-Check (Zustand „nicht etabliert") |
| — | U/L, U_final/L_final, hist_U/hist_L, Touches, Phasen-Objekte, Signal-Pfade | — | **unverändert** |

**Verifikationspflicht nach Umsetzung (erst nach Freigabe):**
(1) `py_compile` der Arbeitskopie; (2) AUG-Lauf: R1 als **eine** Phase
(11.08. 03:45 → 18.08. 03:00) mit U≈66.45/L≈64.24 statt Phasen 2–5;
(3) Benchmark-Tabelle §3 unverändert (Produktion), Makro-Zahlen der
Arbeitskopie separat; (4) Trace-Matrix §4.2 als Kontrast.

---

## 5.3 Anpassungsvertrag (Rücknahme E4a, Harmonisierung Reißleine) — 03.09.2026

**Befund aus erstem Wurf (empirischer Audit, bitgenau):**
Die Hüllen-Bruchlogik (E4a) erzeugte eine 64.5h-Monsterphase (Phase 10,
258 Candles) mit 6 konsekutiven SHORT-Fehltrades (−6.00R, Trades 22–27)
gegen den Aufwärtstrend. Die rein phasen-lokale Hülle zerstört die
Signal-Asymmetrie der Reclaim-Engine: Die Signal-Engine ist auf **frische,
enge Phasen-Profile** kalibriert (Tier-1-Reclaim gegen die lokale Balance);
ein verwaschens Riesenprofil lädt wiederholt an der wandernden Oberkante
zum Fehl-SHORT. **Curve-Fitting-Bias erkannt und Notbremse gezogen:** Die
Makro-Konsolidierung darf nicht über die Segmentierung erzwungen werden.

**Reißleinen-Audit (Korrektur der Diagnose):** Die Not-Reißleine war im
ersten Wurf **nicht** der Fragmentierer der R1-Phase: Phase 3 lief real
155 Candles (normal-down-Bruch am 14.08 03:45, R1-Verlassen-Drop) und
Phase 4 (89 Candles, nie etabliert, Wochenend-Rebound 63.5 → 65.9) war der
**einzige** Reißleinen-Auslöser — dort funktionierte sie korrekt. Die
(15C)/(24C)-Log-Angaben sind Touch-Perioden, keine Lebensdauern. Trotzdem
wird die Reißleine aus **Konsistenzgründen** harmonisiert (siehe unten).

**Entscheidung & Weichenstellung:**
1. **E3 bleibt erhalten** (`MIN_ESTABLISH_SPREAD_PCT = 1.5`): eliminiert
   Mikrorauschen, verschmilzt die alten Phasen 2+3 erfolgreich zu einer
   107-Candle-Phase.
2. **`RUNAWAY_MIN_CANDLES` wird von 12 auf 46 angehoben**: vollständige
   Symmetrie zu `MIN_PHASE_CANDLES`; beide Bruch-Pfade („etabliert" →
   lokaler Bruch, „nicht etabliert" → Reißleine) nutzen dieselbe Zeitbasis.
3. **E4a (Ratschen-Hülle als Bruch-Referenz) wird vollständig
   zurückgenommen**: Der Bruch-Check erfolgt wieder kausal gegen die
   **lokale Schnittmenge** (`h_ref = max(U, birth_h)` bzw.
   `l_ref = min(L, birth_l)`) — wie in der Produktions-Baseline.
   Die Hilfsfunktion `envelope_level` und die zugehörigen Konstanten
   (`ENVELOPE_MIN_TOUCHES`) werden entfernt.
4. **Konsolidierung zu R1–R4 verbleibt exklusiv in
   `macro_persistence.py` (Tier 2)**: Die Phasen-Engine bleibt agil und
   reaktionsschnell (Tier 1); die übergeordneten Mehrtages-Level
   (66.45/64.24) liefert die Kanten-Persistenz als Makro-Gedächtnis —
   institutionelle Trennung von Regime und Ausführung.

**Minimal-invasiver Umbau (nach Freigabe, in `scripts/phasen_makro_swings.py`):**

| # | Eingriff | Ort | Änderung |
|---|---|---|---|
| R1 | `RUNAWAY_MIN_CANDLES: int = 12` → `46` | Konstanten-Block (nach E1) | Wert anpassen, Kommentar „Symmetrie zu MIN_PHASE_CANDLES" |
| R2 | E4a-Hüllen-Referenz entfernen | Bruch-Logik Z. ~736–743 (h_env/l_env-Zeilen) | `h_ref = max(U,birth_h)`, `l_ref = min(L,birth_l)` (Baseline-Verhalten) |
| R3 | `envelope_level()` + `ENVELOPE_MIN_TOUCHES` entfernen | nach `_linie` | additiv eingefügte Funktion + Konstante löschen |
| — | E3 (Etablierungs-Gate), E4b (Reißleine ab 46), U/L, U_final/L_final, Signal-Pfade | — | **bleiben unverändert** |

**Verifikationspflicht nach Umbau (erst nach Freigabe):**
(1) `py_compile` der Arbeitskopie; (2) AUG-Kontrolllauf: erwartet **12
Phasen** (Baseline-Struktur) ODER 11 (nur E3-Wirkung) — **keine**
Monsterphase; (3) Summe R ≥ Baseline-Niveau, keine 6er-Verlustserie;
(4) `git diff` Produktion leer.

---

## 5.4 Dokumenten-Fixierung: Spread-Entscheid & Tier-2-Übergabe — 03.09.2026

### 5.4.1 Spread-Entscheid: `MIN_ESTABLISH_SPREAD_PCT` bleibt verbindlich auf 1.5 % fixiert (2.0 % verworfen)

**Empirische Basis (Spread-Check S2/S1, Log-Inspektion der Baseline- und
`--macro-live`-Artefakte; Helper `test/tmp_spread_check.py`):**

| Kennzahl | S2 (2025) | S1 (2026) |
|---|---|---|
| Phasen gesamt / handelbar | 62 / 22 | 139 / 40 |
| Spread `(U−L)/L` — alle Phasen, Median | 1.34 % | 2.77 % |
| Spread — nur handelbare, Median | 3.45 % | — |
| Spread — nur handelbare, Minimum | 1.57 % | 1.60 % |
| Handelbare mit Spread < 2.0 % | **4** (Ph8 1.57 %, Ph19 1.67 %, Ph13 1.81 %, Ph48 1.95 %) | **8** (1.60–1.97 %) |
| Handelbare mit Spread ≥ 2.0 % | 18 | 32 |

**Bewertung einer Anhebung des Etablierungs-Gates auf 2.0 %:**
- S2 würde nicht abgewürgt (18/22 handelbare Phasen ≥ 2.0 %), aber ~18 %
  der handelbaren Phasen (4/22) würden unterdrückt — ausgerechnet im
  Low-Vol-Regime S2, dessen Bilanz ohnehin die schwächste ist.
- **Unsicherheitszone:** E3 wirkt auf den **Etablierungs**-Spread (live,
  enger als der finale Spread). Phasen mit finalem Spread ≥ 2.0 % können in
  der Etablierungsphase noch unter 2.0 % gelegen haben → die reale
  Unterdrückungswirkung liegt **über** der 4/22-Zählung.
- S1 ist strukturell ähnlich (8/40 = 20 % unter 2.0 %).

**Entscheid (verbindlich, arretiert):** `MIN_ESTABLISH_SPREAD_PCT = 1.5`
bleibt fixiert. Die Anhebung auf 2.0 % ist **verworfen**: Das Risiko,
handelbare Low-Vol-Phasen zu unterdrücken (S2-Regime), steht in keinem
Verhältnis zum Nutzen — das Mikrorauschen ist bereits durch 1.5 %
eliminiert (E3 validiert: AUG-Kontrolllauf +27.06R bei 11 Phasen, §5.3).
Die Sweep-Kalibrierung 1.0–2.5 % aus §5.2.1 ist damit **obsolet**; ein
Senkungstest 1.0–1.5 % bliebe nur als optionale Sensitivitäts-Prüfung
offen (nicht geplant).

### 5.4.2 Architektonische Übergabe R1–R4 an `macro_persistence.py` (Tier 2) — Inspektions-Befund

Die R1–R4-Konsolidierung (Mehrtages-Gedächtnis 66.45/64.24) wird — wie in
§5.3 Punkt 4 arretiert — **vollständig an `macro_persistence.py` (Tier 2)
übergeben**. Die reine Lese-Inspektion (keine Änderung) bestätigt, dass die
Schnittstelle die Makro-Abbildung konstruktiv bereits trägt:

1. **Zonen-Pool je Seite** (`MacroLineState`, Z. 114) mit kausaler
   Touch-Verarbeitung (`update_touch`, Z. 225: Zone matchen/erzeugen,
   Zentrum = Remove-Tail-Schnittmenge) und selektivem Löschen an
   Phasengrenzen (`on_phase_boundary`, Z. 261: nur durchschrittene Zonen
   der Bruch-Seite, Gegenseite persistiert als `left_behind`).
2. **Frozen Anker-Abfragen** (Kausalitäts-Schutz, nie Live-Referenzen):
   `best_macro_anchor` (Z. 295, global, Evidenz ≥ `MIN_ZONE_EVIDENCE`,
   R2-Tie-Break) und `best_local_macro_anchor` (Z. 305, distanz- UND
   seitenbegrenzt mit `side_tol`).
3. **Operative Kanten-Auswahl** `resolve_active_edge` (Z. 446, frozen
   `ActiveEdgeDecision`): Tier 1 = lokale Volume-Kante bei bestätigter
   Pivot-Dichte (E2), sonst Tier 2 = Makro-Anker (E3/E5) mit
   Kanten-Kapselung (a_sym) und Überrannt-Filter (`overrun_tol` = 0.075);
   E3-Fallback = lokale Kante als Tier 1 — nie None, Baseline-DNA bleibt.
4. **Rein lesendes Replay/Report:** `macro_replay` (Z. 631) →
   (state_upper, state_lower, PhaseSnapshots), `macro_report` (Z. 720)
   als passiver Spiegel; dependency-frei (nur pandas), `level_schnittmenge`
   wird injiziert (kein Zirkular-Import).

**Fazit:** Kein Handlungsbedarf in der Segmentierungs-Engine. Die
Tier-2-Anbindung der Arbeitskopie an die Makro-Zonen bleibt separates
Folge-Experiment (§7 Punkt 3) — außerhalb dieses Dokuments.

---

## 5.5 Statischer Veto-Trocken-Check AUG (26 Trades) — 03.09.2026

**Prüfobjekt:** `test/stats_trades_MAKRO_AUG.txt` (Rückbau-Lauf, 11 Phasen,
26 Trades, +27.06R). **Modus:** reine Rechenprüfung (kein Lauf).

**Suchmuster gegen die aktiven R1-Referenzfenster (0.25 %-Puffer):**
- R1_U = 66.45 (0.25 % = 0.166) → Puffer **[66.284, 66.450]**; aktiv
  11.08 03:45 → 18.08 03:00 (df 107–564)
- R1_L = 64.24 (0.25 % = 0.160) → Puffer **[64.240, 64.400]**; aktiv
  11.08 08:30 → 13.08 21:15 (df 126–361)
- Kriterium: **LONG** mit Entry im R1_U-Puffer (Chase-Long in die Oberkante)
  bzw. **SHORT** mit Entry im R1_L-Puffer (Chase-Short in die Unterkante).
- Zeit-Anker: df 380 = 14.08 03:00 (Trace-Matrix §4.2; konsistent mit
  4-Bar-Gap je Mitternacht — alle Anker-Paare rechnerisch verifiziert).

**Ergebnis (Preis-Puffer-Kandidaten):**

| Trade | Phase | Richtung | Entry | Puffer (Preis) | R_Result | Entry-Zeit (Bar 405) | aktives Fenster |
|---|---|---|---|---|---|---|---|
| 9 | 4 | SHORT | 64.244 | R1_L [64.240–64.400] **✓** | −1.00 | Fr 14.08 09:15 | **NEIN** (R1_L endete 13.08 21:15) |

**Befund:**
1. **LONG im R1_U-Puffer: 0 Treffer** — kein einziger LONG-Entry des AUG
   liegt in [66.284, 66.450] (LONG-Preise: 63.0–64.7 bzw. 68.0–69.0; Lücke
   64.70 → 67.99).
2. **SHORT im R1_L-Puffer: genau 1 Preis-Kandidat (Trade 9, 64.244).**
   Zeitlich verworfen: Entry-Bar 405 = Fr 14.08 09:15 liegt **12 h nach
   R1_L-Ablauf** (Fensterende df 361 = 13.08 21:15) und **6.25 h nach dem
   R1-Unterbruch** (2-Close down 14.08 03:00, df 380, Trace §4.2 Phase 4).
   Die Kante war zum Entry bereits gebrochen → der SHORT ist ein
   Retest-/Momentum-Trade der gebrochenen Unterstützung, kein Veto-Fall.
3. **Kontext (nicht im Suchmuster, legitime Fade-Seite an R1_U):** die
   SHORTs im oberen Puffer innerhalb des R1_Fensters — T6 (66.294,
   11.08 03:15, +4.59), T10 (66.307, 17.08 18:15, +3.16), T11 (66.376,
   18.08 01:30, +2.98) — sind Fade-Shorts an der Oberkante und profitabel.

**Verdikt:** **0 von 26 Trades** erfüllen das Veto-Kriterium (Preis-Puffer
UND aktives Referenzfenster). Kein Handlungsbedarf, keine Fehl-Entries an
den aktiven R1-Kanten im Rückbau-Lauf.

---

## 6. Tracking-Log

| Datum | Ereignis | Commit/Status |
|---|---|---|
| 03.09.2026 | Isolierte Arbeitskopie `scripts/phasen_makro_swings.py` angelegt (Artefakt-Pfade entkoppelt) | `bd40ad3` |
| 03.09.2026 | Mentor-Urteil: mathematischer Realitätscheck R1-Zerfall, Retail-Falle, 3 Hebel | dieses Dokument |
| 03.09.2026 | Dokumenten-Sicherung `docs/makro_swings_experiment.md` | untracked, noch nicht committet |
| 03.09.2026 | **Statische Trace-Analyse AUG abgeschlossen** (Freigabe Lese-Skript): 12 Phasen, 11 Abbrüche, bitgenau zur Produktion; Hypothese „66.79-Bruch" widerlegt → lokale Kanten 65.198/64.336/64.198; Overshoots +0.03…+0.53 | `test/tmp_makro_swings_trace.py` (gitignored), Befunde in §2.2/§4.2 |
| 03.09.2026 | **Mentor-Urteil: strukturelles Missverständnis** (Zonen-Findung = Bruch-Erkennung über U/L); Konzeption „Hierarchische Balance-Hülle" (§5.1); Leitfragen beantwortet: (1) Etablierungs-Spread-Gate **ja** (relativ), (2) Kanten-Evolution nach außen **ja** (Ratschen-Hülle + Spike-Schutz) | §5.1.3/§5.1.4 |
| 03.09.2026 | **Mentor-Realitätscheck:** 2 Fallstricke (Runaway vor Etablierung; rohe Ratsche durch Docht-Spikes). **Umsetzungs-Spezifikation §5.2 fixiert:** Datenvertrag `MacroEnvelopeConfig`, 3 Schichten (Etablierungs-Gate / Ratschen-Hülle mit Remove-Tail / Not-Reißleine), Umsetzungs-Vertrag E1–E4 minimal-invasiv | §5.2.1–§5.2.5 |
| 03.09.2026 | **Umsetzung E1–E4 in Arbeitskopie** (Freigabe): py_compile OK, Produktion unverändert | `scripts/phasen_makro_swings.py` modifiziert (uncommitted) |
| 03.09.2026 | **Erster AUG-Kontrolllauf E1–E4:** 12→10 Phasen, 27 Sig, +17.71R (−7.26R); Monsterphase 10 (64.5h, 258C) mit 6 Fehl-SHORTs (−6.00R); Reißleinen-Audit (nur 1 Auslöser, Phase 4/89C, korrekt) | `test/tmp_huelle_AUG_lauf.log`, `test/stats_trades_MAKRO_AUG.txt` |
| 03.09.2026 | **Mentor-Urteil: Ende der „Phasen-Alchemie"** — Makro-Sicht exklusiv in `macro_persistence.py` (Tier 2), Phasen bleiben agil. **§5.3-Anpassungsvertrag arretiert:** E3 bleibt, Reißleine auf 46, E4a vollständig zurück | §5.3 |
| 03.09.2026 | **Rückbau R1–R3 ausgeführt** (Freigabe): `envelope_level`+`ENVELOPE_MIN_TOUCHES` entfernt, `RUNAWAY_MIN_CANDLES` 12→46, Bruch-Referenz = lokale Schnittmenge. py_compile OK, Produktion unverändert | `scripts/phasen_makro_swings.py` (uncommitted) |
| 03.09.2026 | **AUG-Kontrolllauf nach Rückbau:** **11 Phasen** (keine Monsterphase), 26 Sig, **+27.06R** (> Baseline +24.97R!), WR 50 %, PF 3.43; 6er-Verlustserie **verschwunden**; Phase-2+3-Verschmelzung bleibt (112C) | `test/tmp_rueckbau_AUG_lauf.log`, `test/stats_trades_MAKRO_AUG.txt` |
| 03.09.2026 | **Spread-Check S2/S1** (Log-Inspektion): nur handelbare Phasen median 3.45 % (S2) / 2.77 % (S1); handelbar < 2.0 %: S2 4/22, S1 8/40 → strukturell ähnliche Regime | `test/tmp_spread_check.py` (gitignored), Befunde §5.4.1 |
| 03.09.2026 | **Dokumenten-Fixierung §5.4:** `MIN_ESTABLISH_SPREAD_PCT` = 1.5 % **verbindlich fixiert**, Anhebung auf 2.0 % **verworfen** (Low-Vol-Unterdrückung S2); R1–R4-Makro-Abbildung architektonisch **vollständig an `macro_persistence.py` (Tier 2)** übergeben (Inspektion abgeschlossen, kein Code-Eingriff) | `73e5166`, dieses Dokument §5.4 |
| 03.09.2026 | **Cleanup I4 + Statischer Veto-Trocken-Check AUG (§5.5):** `tmp_makro_swings_trace.py` gelöscht. 26 Trades rechnerisch gegen R1-Puffer (0.25 %): **0/26 Veto-Treffer** (einziger Preis-Kandidat Trade 9 = SHORT 64.244, zeitlich nach R1_L-Ablauf & R1-Unterbruch verworfen); LONG im R1_U-Puffer: 0 | dieses Dokument, §5.5 |
| 03.09.2026 | **OOS-Vorbereitung §8 (Grenzphasen-Inspektion S2, Log statisch):** Ph8/19/48 etablieren unter E3 vor C 46 (keine Reißleinen-Exposition); **Ph13 kritisch** (1.5 % erst nach ~124 C → 78 C exponiert, keine Auslösung im Kanten-Verlauf); finale-Spread-Distanz ≠ Etablierungs-Verzögerung. OOS-Prüfschritte S1/S2 fixiert | `cd132dc`, dieses Dokument §8 |
| 03.09.2026 | **Phase-13-Close-Verifikation §8.2a (DuckDB read_only):** p0 38.288; max close 38.351 (+0.16 %), min close 37.628 (−1.72 %) in C 46–124; **0** × 2-Close-Bruch der 3 %-Barrieren (39.437/37.139) → **Reißleine NEIN**, E3-Etablierung greift stabil ~C 124 | dieses Dokument, §8.2a |
| 03.09.2026 | **S2-OOS-Lauf §8.4 (isolierte Arbeitskopie, Baseline-Modus, Gesamtjahr 2025):** 52 Phasen (vs. 62 Baseline), 26 handelbare Ranges; 209 Trades (106 L/103 S), WR 34.0 %, **+102.16R** (+8.46R vs. OOS-Referenz +93.70R, +2.28R vs. Baseline +99.88R), PF 1.80; **0 Reißleinen-Auslösungen**; Grenzphasen Ph8/19/48 überleben eigenständig (neue Phasen 8/16/40), **Ph13 → Phase 12 (723 C) verschmolzen, unschädlich** (+1.98R) | `test/tmp_oos_S2_lauf.log`, `test/stats_trades_MAKRO_S2.txt`, `test/phasen_makro_swings_S2.png` (gitignored), dieses Dokument §8.4 |
| 03.09.2026 | **Ursachenanalyse 52-Tage-Lücke §8.5 (statische Inspektion, kein Lauf):** Phase 7 endet 11.04 12:45, Phase 8 startet 02.06 19:30 = **52 Tage / 3237 M15-Kerzen** (Datenintegrität 100 %, keine Lücke > 4 Tage); Ursache = Geburtsanker `birth_h` 34.193 fixierte Bruch-Schwelle 34.533 (0 Kanten-Verschiebungen) → 2-Close-Bruch erst 02.06 19:30/19:45; **kein Seed-Fehlschlag, kein E3-Artefakt** (Baseline v0.4.x identisch); **Stale Phase** blockierte Sequenzer ohne Trades (0 im Fenster) — Spiegelbild zur R1-Fragmentierung | dieses Dokument, §8.5; Quellen `test/tmp_oos_S2_lauf.log`, `test/tmp_default_run_S2.log` |
| 03.09.2026 | **S1-OOS-Lauf §8.6 (Arbeitskopie, Baseline-Modus, 2026-02-05 → 2026-08-28):** 130 Phasen (vs. 139 Base), 49 handelbar; 216 Trades (120 L/96 S), WR 41.7 %, **+172.92R** (−24.3R vs. Baseline +197.26R, −26.73R vs. OOS-Referenz +199.65R), PF 2.57; **0 Reißleinen**; AUG-Anker OK, Tail-Ph130 verschmolzen (154 C). **S1+S2 = +275.08R < Ziel ≥ +292.14R → OOS NICHT freigabefähig.** Delta-Attribution: 17 neue Fenster netto +7.98R (nicht Ursache); **−32.30R aus verändertem Altphasen-Verhalten** | `test/tmp_oos_S1_lauf.log`, `test/stats_trades_MAKRO_S1.txt`, `test/phasen_makro_swings_S1.png` (gitignored), dieses Dokument §8.6 |
| 03.09.2026 | **Bitgenaue Obduktion §8.6 (Inspektion + DuckDB + Zone-Replikation):** (1) **B-Ph46 vs. E3-Ph46**: Base +10.21R (2 Tr, inkl. +10.69R Mo 13.04 00:15) vs. E3 −0.71R (5 Tr) → Δ −8.45R/−10.92R. Ursache bitgenau: E3-Riesenprofil hält L_eff bei 75.116 (Mo 00:15) → Dip-Close 72.896 kein Reclaim, ab 00:30 L_eff 72.639 → nie wieder Kandidat; Base-Profil dünn → L_eff 72.639 schon bei 00:15 → Trade exakt reproduziert (CRV 10.31, Bo 2). E3-up-Bruch Di 05:45 (Schwelle 76.879) vs. Base 05:30 (76.752). (2) **B-Ph132 (R1-Zone)**: Base +8.31R (7 Tr) vs. E3 Ph123+124 +5.14R (3 Tr) → Δ −3.17R; Reißleine exakt: p0 63.926, Schwelle 65.844, Trigger Mo 17.08 03:00/03:15 (C 65.850/65.866, Candle 92), Fr-max-High 65.684 < Schwelle | Helper `test/tmp_obduktion_p46.py`, `test/tmp_obduktion_trace.py`, `test/tmp_obduktion_reissleine.py` (I4, danach löschen), dieses Dokument §8.6 |
| 03.09.2026 | **CRV2-Filter-Negativbefund §8.7 (statistische Log-Analyse, reine Inspektion):** CRV2 je Trade aus Ein/SL/TP2 (Log-3dp) berechnet; Verteilung min 0.98–1.36, Median 3.42–3.60, max 6.0/18.6/18.0; nur 1 Trade < 1.0. Simulation Schwellen 1.0/1.2/1.5 (AUG/S1/S2): **alle Fenster & alle Schwellen netto negativ** (−0.29 … −2.96R) — der Filter spart nur −1.00R-Voll-SL-Treffer und schneidet enge, voll treffende Reversion-Winner ab (R ≈ CRV2 ≈ 1.1–1.5). **Verdikt: CRV2-Filter endgültig verworfen** (kein Mindestraum-Filter auf TP2/Gegenseite); Raum-Filter-Ansatz empirisch abgeschlossen | dieses Dokument §8.7 |
| 03.09.2026 | **Entscheidung Option A — Rückbau E3 arretiert (§8.7):** OOS-Lücke wird in der **Segmentierung** adressiert (nicht Signalebene). Rückbau: `MIN_ESTABLISH_SPREAD_PCT` + Reißleinen-Konstanten (Z. 216–219) entfernen, E3-Gate (Z. 682–687) auf touch-basierte Etablierung (`MIN_ESTABLISH = 4`), Reißleinen-`elif` (Z. 713–722) entfernen → segmentierungs-bitgenau zur Produktions-Baseline (§3-Vergleich direkt möglich). **Revidiert:** §5.3 Pkt. 1 & §5.4.1 (beruhten auf AUG-only-Kalibrierung). Erwartung: S1+S2 ≈ +297.14R ≥ Ziel +292.14R. **Umsetzung erst nach Mentor-Freigabe** (Code-Audit + Diff-Vorschau: §7 Pkt. 12) | dieses Dokument §8.7 |
| 03.09.2026 | **Cleanup I4 (Obduktions-Helper):** `test/tmp_obduktion_p46.py`, `test/tmp_obduktion_trace.py`, `test/tmp_obduktion_reissleine.py` gelöscht (in §8.6 als „am 03.09.2026 gelöscht (§8.7)" vermerkt — Löschung konsistent nachgezogen). OOS-Logs `test/tmp_oos_S1_lauf.log` / `test/tmp_oos_S2_lauf.log` bleiben als Belegquellen (§8.4/§8.6/§8.7) vorerst erhalten | dieses Dokument §8.6/§8.7, §7 Pkt. 5 |
| 03.09.2026 | **Option A ausgeführt (Freigabe erteilt) & verifiziert:** Rückbau E3 + Reißleine in der Arbeitskopie exakt nach §7 Pkt. 12 (Konstanten-Block entfernt, E3-Gate auf Touch-Check Z. 677–680, Reißleinen-`elif` entfernt; 17 Zeilen netto, py_compile OK, keine E3-Identifier mehr). **AUG-Regression exakt bestanden: 12 Ph / 27 Sig / +24.97R** (= Baseline). **S1 exakt bestanden: 139 Ph / 201 Sig / +197.26R** (= S1-Baseline, bitgenau); B-Ph46-Riesenprofil aufgelöst (139 statt 130 Phasen), Referenzfall reproduziert: Phase 46 eigenständig Fr 10.04–Mo 13.04, 2 Tr **+10.21R** inkl. Mo 13.04 00:15 **+10.69R** (§8.6) | `test/tmp_optionA_AUG_lauf.log`, `test/tmp_optionA_S1_lauf.log`, `test/stats_trades_MAKRO_AUG.txt`, `test/stats_trades_MAKRO_S1.txt`, `test/phasen_makro_swings_AUG.png`, `test/phasen_makro_swings_S1.png` (gitignored), dieses Dokument §8.7 |
| 03.09.2026 | **S2-Bestätigungslauf §8.7 (Arbeitskopie `d99abbb`, Gesamtjahr 2025, reine Messung):** **exakt 62 Phasen / 210 Signale / +99.88R** (WR 35.2 %, PF 1.80) = bitgenaue S2-Baseline (§3). **Gesamt S1+S2: 201 Phasen / 411 Signale / +297.14R** — Ziel ≥ +292.14R erreicht (**+5.00R Delta**), OOS-Referenz +293.35R übertroffen. OOS-Lücke empirisch geschlossen → Arbeitskopie `d99abbb` **bitgenau verifiziert & freigabefähig** | `test/tmp_optionA_S2_lauf.log`, `test/stats_trades_MAKRO_S2.txt`, `test/phasen_makro_swings_S2.png` (gitignored), dieses Dokument §8.7 |
| 03.09.2026 | **Tier-2-Zonen-Replay §8.8 (instrumentierter Replay, autorisiert):** Logs enthalten keinen Zonen-Pool-Dump → Helper `test/tmp_zonepool_replay.py` (exec-Import `baseline_mod` von `phasen_volumen_profil.py`, Cut vor Signal-Sektion, echtes unverändertes `macro_persistence.py`; Kausalitäts-Axiom Boundary(p−1) → Scan → Touches(p)). **Fidelity bitgenau:** AUG 27/+24.97R & 25/+34.87R; S2 210/+99.88R & 216/+93.70R; alle Tier-2-Anker exakt (AUG 66.364/66.382; S2 31.309, 4× 29.706, 41.373, 41.347). **S2-Delta:** 209 identisch | 1 entfallen (18.09 07:45 LONG +2.01R) | 7 neu (6× −1.00R an alten LOWER-Ankern + 1× +1.84R) → Δ −6.18R; AUG-Δ +9.90R = Veto (+4.00R) **+** Substitution (Tier-2-Ersatz 66.364) → reines Veto-Gate erreicht die Substitutionsquelle nicht | Logs `test/tmp_zonepool_{AUG,S2}.txt` | dieses Dokument §8.8.1 |
| 03.09.2026 | **Wand-Obduktion §8.8 (Bar-Ebene, 3 Fenster; Helper `test/tmp_wall_obduktion.py`):** AUG 2 Wand-Zeilen (0 FP / 2 TP), S1 30 (14 FP +51.64R / 16 TP), S2 42 (5 FP +23.88R / 37 TP). **Interview-Frage 1 datenwiderlegt:** Intra-Phase-Durchbruch (n_ph > 0) verwirft 100 % der Veto-Wirkung (AUG 2/2, S1 16/16, S2 37/37) — Reclaim feuert nach Seitentausch, „unberührte Wand" existiert praktisch nie. **Frage 2 datenwiderlegt (Achse invertiert):** größtes Veto-Cluster S2-P7 = 38.5–67.3 d alt, schlimmster FP S2-P49 +8.63R = frischeste Wand (d_ph_last 1, 6.4 d); S1 Winner/Loser über denselben Altersbereich. **Sammelwand S2-P49:** 5 Loser + +8.63R-Winner teilen exakt Wand 48.360 — keine Zonen-Regel trennt Versuch 1–5 von 6. **S1-Trigger-Nähe:** P129-Wand 0.05 über Entry (Retail-Falle) | Logs `test/tmp_wall_obduktion_{AUG,S1,S2}.txt` | dieses Dokument §8.8.2 |
| 03.09.2026 | **Veto-Bilanz & Distanz-Check §8.8 (naiv + 1.0R-Klausel; Helper `test/tmp_wall_distance.py`):** Naiv: S1 23 geflaggt (12W/11L, +31.16R) → Blocken kostet −31.16R, S1+S2 ≈ +269.7R < Ziel. **1.0R-Klausel:** 48 geflaggt → 13 rehabilitiert (+13.91R) / 35 verbleibende Veto-Kandidaten kumuliert **+11.51R Netto-Gewinner** (S1 12 Kandidaten +15.25R, AUG 2 +2.00R, S2 21 −1.74R) → S1+S2-Projektion ≈ **+283.6R < +292.14R**. **Verdikt arretiert:** geometrisches Wand-Veto (naiv & mit Klausel) empirisch abgeschlossen — v0.4-AUG-Erfolg kommt aus Tier-2-Kanten-Substitution, nicht LOWER-Wand-Blockade; `macro_persistence.py` unverändert. Optionen (offen): Regime-/Trigger-Hypothese, Veto-Gate-Simulation mit Cooldown-Kaskade, oder Pfad-A-Abschluss | Logs `test/tmp_wall_distance_{AUG,S1,S2}.txt` | dieses Dokument §8.8.3/§8.8.4 |
| 03.09.2026 | **Baseline-Fehltrade-Audit AUG §8.9 (Pfad B, kausaler Replay; Helper `test/tmp_baseline_loss_replay.py`, Log `test/tmp_baseline_loss_replay.txt`):** exec-Import-Cut NACH Baseline-Signal-Loop → 27 original erzeugte Signale, Mapping Log↔Replay **27/27 bitgenau**. **Trigger-Integrität 100 % regelkonform** (Cooldown ≥ 12, CRV ≥ 1.0, Bounce ≥ 2, Reclaim-Bedingung — kein Bug). **13 Voll-SL + 2 Teilverluste** (T3 −0.29R / T22 −0.36R: TP1 = POC erreicht, Restcharge vor TP2 am SL — TP2-Reichweiten-Thema, kein Signalfehler). **Naive Filter datenwiderlegt:** Profilalter (5/12 Winner ebenfalls < 40, T25 Alter 2 +1.83R) und Mikro-Penetration (T22 Pen 0.001 vs. Winner T1/T6/T24 RcDepth 0.005–0.008) trennen Winner/Loser nicht. **Muster A** Expansion-Trap/Kanten-Drift (P5 zweigeteilt: Fr 14.08 Erholung 64.309→65.038, Mo 17.08 Expansion 65.752→65.798; T14/T15 shorteten dieselbe Kante 66.284 + Turn — Kostenstruktur des Fade-Edges), **Muster B** junge Profile (11/15, überlappend), **Muster C** TP2-Reichweite. Nächste Schritte: S1 → S2 → Synthese (strikt sequentiell) | dieses Dokument §8.9 |

---

## 7. Offene Punkte

1. **Zwischenstand §5.3/§5.4 bestätigt:** Der Rückbau R1–R3 ist umgesetzt
   (AUG **+27.06R bei 11 Phasen**, keine Monsterphase, keine 6er-
   Verlustserie, Phase-2+3-Verschmelzung erhalten); `MIN_ESTABLISH_SPREAD_PCT`
   ist mit 1.5 % verbindlich fixiert (2.0 % verworfen, §5.4.1). Der Curve-
   Fitting-Bias (E4a) ist eliminiert.
   **Status 03.09.2026 (nach Option-A-Umsetzung): überholt** — E3 ist
   zurückgebaut (Punkt 12 umgesetzt & verifiziert: AUG 12 Ph / 27 Sig /
   +24.97R; S1 139 Ph / 201 Sig / +197.26R = bitgenaue §3-Baseline).
   Punkt 1 beschrieb den Zwischenstand der Arbeitskopie (Rückbau R1–R3,
   E3 noch aktiv), der nicht mehr existiert; die „1.5 %-Fixierung"
   (§5.4.1) ist durch den Option-A-Entscheid (§8.7) revidiert.
2. **Sweep `min_establish_spread_pct` (1.0–2.5 %) ist obsolet** — durch die
   arretierte 1.5 %-Fixierung (§5.4.1) ersetzt. Optional bliebe nur ein
   Sensitivitäts-Test 1.0–1.5 % (nicht geplant). Eine isolierte
   Quantifizierung der E3-Wirkung (Phase-2+3-Verschmelzung, +6.48R über 5
   Trades in Phase 2) wäre separat möglich, ist aber kein Pflichtpunkt mehr.
   **Status 03.09.2026 (§8.7): durch Option-A-Entscheid obsolet** — der
   E3-Parameter wird zurückgebaut (Punkt 12); ein Sweep entfällt endgültig.
3. **Makro-Persistenz-Anbindung** (`macro_persistence.py`, Tier 2): Die
   Code-Inspektion (§5.4.2) bestätigt die architektonische Übergabe der
   R1–R4-Konsolidierung (Zonen-Pool, frozen Anker-Abfragen,
   `resolve_active_edge`, rein lesendes Replay/Report). Die konkrete
   Anbindung der Arbeitskopie an die Makro-Zonen bleibt separates
   Folge-Experiment **außerhalb** dieses Dokuments.
4. **Git-Commit** der Arbeitskopie (Rückbau-Zustand) nach finaler
   Mentor-Freigabe; Produktions-Baseline bleibt unberührt. Die
   Dokumenten-Fixierung §5.4 ist committet (`73e5166`); §5.5 (Veto-Check)
   ist committbar (Tracking-Log §6).
   **Status 03.09.2026: Freigabe erteilt, Rückbau (Option A) committet**
   — Arbeitskopie = segmentierungs-bitgenaue Produktions-Baseline.
5. Temp-Helper in `test/` nach Abschluss der Explorationsphase löschen (I4):
   `tmp_makro_swings_trace.py` **bereits gelöscht** (03.09.2026);
   `tmp_obduktion_p46.py`, `tmp_obduktion_trace.py`,
   `tmp_obduktion_reissleine.py` **bereits gelöscht** (03.09.2026, §8.7);
   offen: `tmp_reissleinen_audit.py`, `tmp_huelle_e1e4.py`,
   `tmp_rueckbau_r1r3.py`, `tmp_spread_check.py`, `tmp_abort_usage.py`,
   `tmp_huelle_AUG_lauf.log`, `tmp_rueckbau_AUG_lauf.log`; **Belegquellen
   bleiben vorerst erhalten:** `tmp_oos_S1_lauf.log`, `tmp_oos_S2_lauf.log`
   (in §8.4/§8.6/§8.7 als Quellen zitiert — Löschung erst nach finaler
   Freigabe der OOS-Auswertung).
6. **Veto-Check §5.5:** 0/26 Trades im aktiven R1-Puffer → kein
   Handlungsbedarf im Rückbau-Zustand. Der Check ist auf die übrigen
   Makro-Zonen (R2–R4) übertragbar, falls ein Veto-Filter konzipiert wird.
7. **OOS-Prüfplan §8 fixiert** (nach Freigabe): OOS-Lauf S1/S2 der
   Arbeitskopie gegen §3; Reißleinen-Audit; close-basierte Verifikation der
   Ph13-Analogfälle; Grenzphasen-Bucket-Überleben; AUG-Regressionsanker
   (11 Phasen / 26 Sig / +27.06 R).
8. **Phase-13-Close-Verifikation §8.2a erledigt:** Reißleine in Ph13
   **nicht ausgelöst** (0 2-Close-Brüche, Band +0.16 %/−1.72 % um p0) —
   §8.3 Nr. 3 ist für Ph13 abgeschlossen; auf die übrigen Ph13-Analogfälle
   in S1/S2 übertragbar.
9. **OOS-Schritt §8.3 Nr. 1 für S2 erledigt (§8.4):** Der S2-OOS-Lauf der
   Arbeitskopie (E3 1.5 % + Reißleine 46) liefert **+102.16R** bei 209
   Trades / 52 Phasen (PF 1.80, **0 Reißleinen**) — +8.46R über der
   OOS-Referenz v0.4.x (+93.70R) und +2.28R über der Baseline (+99.88R).
   Der **S1-OOS-Lauf ist der nächste offene OOS-Schritt** (§3-Referenz
   +199.65R; S1+S2-Ziel ≥ +292.14R). §8.4 ist committbar (Tracking-Log §6).
10. **OOS-Schritt §8.3 Nr. 1 für S1 erledigt (§8.6) — NICHT bestanden:**
    Der S1-OOS-Lauf der Arbeitskopie (E3 1.5 % + Reißleine 46) liefert
    **+172.92R** bei 216 Trades / 130 Phasen (49 handelbar, PF 2.57,
    **0 Reißleinen**) — **−24.3R vs. Baseline (+197.26R), −26.73R vs.
    OOS-Referenz (+199.65R)**. **S1+S2 = +275.08R < Ziel ≥ +292.14R** →
    Arbeitskopie **OOS-nicht freigabefähig**; bleibt experimentell/
    uncommitted (Punkt 4 gilt weiterhin), Produktions-Baseline unberührt.
11. **Anpassungsoptionen aus §8.6 (offen, keine Umsetzung ohne
    Mentor-Freigabe):** (a) Reclaim-/Zonen-Referenz gegen die
    E3-verschobene Unterkante stabilisieren (Ph46-Muster: L_eff 75.1
    blockt Dip-Reclaims); (b) Wochenend-/Gap-Regel für die Reißleine
    (Ph132-Muster: Trigger erst ab N Bars nach Session-Wiedereröffnung);
    (c) Stale-Phase-Guard (§8.5) & AUG-Tail-Verschmelzung (Ph130, 154 C).
    Jede Anpassung erneut gegen den AUG-Regressionsanker (11 Ph / 26 Sig /
    +27.06R) und die §8.6-Referenzfälle (B-Ph46/B-Ph132) validieren.
12. **Code-Audit E3 — Rückbau Option A (§8.7, 03.09.2026; reine Inspektion,
     kein Code-Eingriff):** Diff-Vorschau für `scripts/phasen_makro_swings.py`
     (Arbeitskopie). Vollständigkeit geprüft: `MIN_ESTABLISH_SPREAD_PCT`
     nur Z. 217/686/716, `RUNAWAY_MIN_CANDLES` nur Z. 218/713,
     `RUNAWAY_MULT` nur Z. 219/716 → die drei Blöcke unten decken alle
     Verwendungen ab; keine Altlasten nach dem Rückbau.

     **(a) Konstanten-Block entfernen (Z. 216–219):**
     ```diff
     -# --- Makro-Balance-Huelle (Experiment, docs/makro_swings_experiment.md S5.2) ---
     -MIN_ESTABLISH_SPREAD_PCT: float = 1.5   # Etablierungs-Gate: rel. Mindest-Spanne (U-L)/L in %
     -RUNAWAY_MIN_CANDLES: int = 46           # Not-Reissleine: Symmetrie zu MIN_PHASE_CANDLES (11.5h)
     -RUNAWAY_MULT: float = 2.0               # Not-Reissleine: Faktor x Etablierungs-Spread-Schwelle
     ```

     **(b) E3-Gate auf touch-basierte Etablierung zurückbauen (Z. 682–687):**
     ```diff
     -        # E3: Etablierungs-Gate - erst ab relativer Mindest-Spanne (U-L)/L
     -        spread_pct = (U - L) / L * 100.0 if (U is not None and L is not None and L > 0) else 0.0
     -        if (est_idx is None and U is not None and L is not None
     -                and n_touches(h_acc, U) + n_touches(l_acc, L) >= MIN_ESTABLISH
     -                and spread_pct >= MIN_ESTABLISH_SPREAD_PCT):
     -            est_idx = j
     +        # Etablierung: touch-basiert (Produktions-Baseline, MIN_ESTABLISH = 4)
     +        if (est_idx is None and U is not None and L is not None
     +                and n_touches(h_acc, U) + n_touches(l_acc, L) >= MIN_ESTABLISH):
     +            est_idx = j
     ```

     **(c) Reißleinen-Zweig entfernen (Z. 713–722):**
     ```diff
     -        elif est_idx is None and (j - i) >= RUNAWAY_MIN_CANDLES and j + 1 < n:
     -            # E4b: Not-Reissleine (Runaway-Guard) - greift nur vor Etablierung
     -            p0 = float(df["close"].iloc[i])
     -            runaway_tol = RUNAWAY_MULT * p0 * MIN_ESTABLISH_SPREAD_PCT / 100.0
     -            if row["close"] > p0 + runaway_tol and df["close"].iloc[j + 1] > p0 + runaway_tol:
     -                brk_idx, brk_dir, brk_kante = j, "up", p0 + runaway_tol
     -                break
     -            if row["close"] < p0 - runaway_tol and df["close"].iloc[j + 1] < p0 - runaway_tol:
     -                brk_idx, brk_dir, brk_kante = j, "down", p0 - runaway_tol
     -                break
     ```

     Nach dem Umbau bleibt im Segmentierungs-Loop nur der normale
     Bruch-Check (Z. 699–712; Bruch-Referenz = lokale Schnittmenge
     `h_ref = max(U, birth_h)` / `l_ref = min(L, birth_l)`, `TOL` 0.34) —
     identisch zur Produktions-Baseline. **Unberührt bleiben:**
     `MIN_PHASE_CANDLES` (Z. 205), `MIN_ESTABLISH` (Z. 207, = 4),
     `MIN_SPREAD_PCT` (Z. 209, post-hoc-Handelbarkeits-Label,
     Z. 839–845), `spread_pct`-Feld der Phasen-Struktur (Z. 126) sowie
     die Signal-Pfade (POC-Gate CRV ≥ 1.0, Z. 1221/1273).
     Erwartung nach Umsetzung: Segmentierung bitgenau zur §3-Baseline →
     S1/S2-OOS ≈ Referenz (+199.65R/+93.70R), S1+S2 ≈ +297.14R ≥ Ziel;
     AUG-Regressionsanker ≈ 12 Ph / 27 Sig / +24.97R.
     Verifikation: py_compile; AUG-Lauf; S1/S2-OOS-Lauf.
     **STATUS 03.09.2026: UMGESETZT & VERIFIZIERT (Freigabe erteilt).**
     py_compile OK; AUG-Regression **exakt 12 Ph / 27 Sig / +24.97R**;
     S1 **exakt 139 Ph / 201 Sig / +197.26R** (= bitgenaue §3-Baseline);
     B-Ph46-Riesenprofil aufgelöst, Referenzfall Mo 13.04 00:15
     (+10.69R, Phase 46 = +10.21R aus 2 Tr) reproduziert (§8.6).
     Belege: `test/tmp_optionA_AUG_lauf.log`, `test/tmp_optionA_S1_lauf.log`
     (gitignored), Tracking-Log §6.

---

## 8. OOS-Prüfplan S1/S2 — Grenzphasen-Inspektion (03.09.2026)

**Vorbereitung des OOS-Laufs (S1/S2) gegen die Arbeitskopie mit E3-Gate
(1.5 %) + Reißleine (46 C).** Reine Log-Inspektion von
`test/tmp_default_run_S2.log` (Baseline, 62 Phasen), keine Läufe.

### 8.1 Grenzphasen (finaler Spread 1.5–2.0 %, handelbar) — E3-Verzögerung

Die 4 S2-Grenzphasen aus §5.4.1 — Wann erreichte die **live**
Kanten-Spanne (U−L)/L erstmals ≥ 1.5 %? (Candle-Zählung ab Phasenstart,
M15; Kanten-Werte aus den OBEN/UNTEN-Entwicklungsketten des Logs):

| Phase | Start → Ende | Candles gesamt | finaler Spread | 1. Fixierung U+L | Live-Spread dort | **1.5 % erreicht bei** | Candles bis 1.5 % |
|---|---|---|---|---|---|---|---|
| Ph8 | Mon 02.06 19:30 → Wed 04.06 12:45 | 158 | 1.57 % | Tue 02:30 (C 28) | **10.19 %** | sofort (C 28) | **~28** |
| Ph13 | Mon 14.07 17:15 → Thu 17.07 14:45 | 267 | 1.81 % | Mon 20:30 (C 13) | 0.23 % → 0.49 % → 0.33 % → 1.11 % | Wed 00:15 (L fällt auf 37.694, U 38.313) | **~124** |
| Ph19 | Fri 22.08 16:45 → Wed 27.08 15:30 | 272 | 1.67 % | Fri 20:45 (C 16) | **4.08 %** | sofort (C 16) | **~16** |
| Ph48 | Wed 29.10 04:15 → Thu 30.10 08:45 | 111 | 1.95 % | Wed 07:00 (C 11) | 0.39 % | Wed 13:45 (U steigt auf 48.386, L 47.383) | **~38** |

**Detail Ph13 (einzige langsame Expansion, Kette):** Mon 20:30 U 38.374 /
L 38.287 = 0.23 % → Tue 00:15 L 38.187 = 0.49 % → Tue 04:30 U 38.313 =
0.33 % (Spread **sinkt** zwischenzeitlich) → Tue 16:30 L 37.891 = 1.11 % →
**Wed 00:15 L 37.694 = 1.64 % ≥ 1.5 %** (nach ~31 h = ~124 C).

### 8.2 Reißleinen-Exposition (46-Candle-Schwelle)

Die Not-Reißleine ist scharf ab C 46, solange `est_idx` fehlt
(`RUNAWAY_MIN_CANDLES = 46`, arretiert §5.3); Auslösung erst bei 2-Close-
Bruch um `runaway_tol` = 3 % von `p0` (Close der Start-Bar):

| Phase | E3-Etablierung (≈ C) | Reißleine scharf? | Exposition | Auslösung im Verlauf? |
|---|---|---|---|---|
| Ph8 | ~28 | **Nein** (vor C 46 etabliert) | 0 C | — |
| Ph13 | ~124 | **Ja** | C 46–124 = **78 C exponiert** | **Nein** (enges Band: L-Kante max −1.7 % von p0 ≈ 38.3, U-Kante +0.2 %; kein 3 %-Move; Close-Näherung über Kanten) |
| Ph19 | ~16 | **Nein** | 0 C | — |
| Ph48 | ~38 | **Nein** (knapp vor C 46) | 0 C (8 C Reserve) | — |

**Befund:**
1. **3 von 4 Grenzphasen (Ph8/19/48) etablieren unter E3 vor C 46** — die
   Reißleine wird nie scharf. Ihre finalen Spreads (1.57–1.95 %) täuschen
   nicht über die **frühe live-Spread-Öffnung** hinweg (Ph8/19 bereits bei
   der ersten Kanten-Fixierung ≥ 4 %).
2. **Ph13 ist der einzige kritische Fall:** langsame Spread-Expansion
   (0.23 % → 1.64 % über 124 C), dadurch 78 Candles Reißleinen-Exposition.
   Eine Auslösung ist im Log nicht erkennbar (Kanten-Band max ~1.9 %
   Gesamtbewegung < 3 %-Schwelle), aber die Close-Daten liegen nicht im
   Log — **close-basierte Verifikation ist Pflichtpunkt des OOS-Laufs**.
3. Die finale-Spread-Distanz zur 1.5 %-Schwelle (1.57–1.95 %) korreliert
   **nicht** mit der Etablierungs-Verzögerung: Ph48 (1.95 %, am nächsten an
   2.0 %) etablierte bei C 38, Ph19 (1.67 %) bei C 16 — entscheidend ist
   die **Expansionsgeschwindigkeit** der live-Kanten, nicht der Endwert.

### 8.2a Close-basierte DuckDB-Verifikation Phase 13 (C 46–124) — erledigt

**Prüfobjekt:** `data/market_data.duckdb` (DuckDB read_only, S2-Fenster
2025), Start-Bar df 12527 = 2025-07-14 17:15 UTC. Temp-Helper
`test/tmp_phase13_close_check.py` (I4-konform, nach Nutzung gelöscht).
**Parameter:** `p0` = close der Start-Bar = **38.288**; Barrieren:
oben `p0 × 1.03` = **39.437**, unten `p0 × 0.97` = **37.139**.

| Bereich | Bars | max close | min close | 2er-Folge > 39.437 | 2er-Folge < 37.139 |
|---|---|---|---|---|---|
| C 46–124 (strikt §8.2) | 79 | **38.351** (+0.16 % vs p0) | **37.628** (−1.72 % vs p0) | **0** | **0** |
| C 40–130 (Sensitivitäts-Puffer) | 91 | 38.351 | 37.628 | **0** | **0** |

**Befund (stichpunktartig):**
- **Reißleinen-Auslösung: NEIN.** Kein einziger 2-Close-Bruch der 3 %-
  Barrieren im exponierten Fenster C 46–124 (und im erweiterten
  Sensitivitäts-Bereich C 40–130).
- Der Markt pendelte in einem engen Band: max **+0.16 %** / min **−1.72 %**
  relativ zu `p0` — die 3 %-Schwellen (±1.149 USD) wurden nie erreicht.
- Der min-Close 37.628 korrespondiert exakt mit der L-Kanten-Evolution aus
  §8.1 (Wed 00:15: L 37.694, Close leicht darunter) — die Kanten-Näherung
  war korrekt.
- **E3-Etablierung greift stabil bei ~C 124** — die Reißleine bleibt in
  Phase 13 ohne reales Risiko; die §8.2-Diagnose „keine Auslösung" ist
  damit **close-basiert verifiziert** (Pflichtpunkt 8.3 Nr. 3 für Ph13
  erledigt).

### 8.3 OOS-Prüfschritte S1/S2 (nach Freigabe)

1. **OOS-Lauf S1/S2** der Arbeitskopie (E3 1.5 % + Reißleine 46): Vergleich
   gegen §3 (S1+S2 ≥ +292.14 R, Baseline-Referenz +297.14 R);
   Phasen-Zählung und Signal-Delta je Fenster dokumentieren.
2. **Reißleinen-Audit:** alle Auslöser im Log (Bruch-Pfad „nicht etabliert"
   ab C 46) tabellarisch erfassen; Ph13-Analogfälle (Etablierung > C 46) in
   S1/S2 zählen.
3. **Close-basierte Verifikation** der Ph13-Analogfälle (DuckDB read_only):
   2-Close-Bruch um 3 % von `p0` mit echten Closes prüfen — nicht über die
   Kanten-Kette nähern.
4. **Grenzphasen-Bucket (1.5–2.0 %) zählen:** Wie viele der handelbaren
   22 (S2) / 40 (S1) überleben E3 unverändert, wie viele werden durch die
   Reißleine vorzeitig beendet, wie viele verlieren den HANDELBAR-Status?
   Ziel: 18/22 (S2) und 32/40 (S1) der ≥ 2.0 %-Phasen bleiben erhalten;
   Verluste nur im dokumentierten Risiko-Bucket.
5. **AUG-Regressionsanker:** Kontrolllauf bleibt bei 11 Phasen / 26 Sig /
   +27.06 R (§5.3) — kein Drift durch allfällige OOS-Anpassungen.

### 8.4 S2-OOS-Lauf (Gesamtjahr 2025) — Befund (03.09.2026)

**Ausführung:** Arbeitskopie `scripts/phasen_makro_swings.py`
(E3-Gate 1.5 % + Reißleine 46 C, arretiert §5.3), Baseline-Modus,
`--start=2025-01-01 --ende=2025-12-01`. Artefakte:
`test/tmp_oos_S2_lauf.log`, `test/stats_trades_MAKRO_S2.txt`,
`test/phasen_makro_swings_S2.png` (alle gitignored).

**Ergebnis-Übersicht:**

| Kennzahl | S2-OOS (E3+Reißleine) | S2 Baseline v0.4.x | S2 OOS-Referenz v0.4.x (`--macro-live`) |
|---|---|---|---|
| Phasen gesamt | **52** | 62 | — |
| Handelbare Ranges | **26** | 22 | — |
| Trades | **209** (106 L / 103 S) | 210 Sig | 216 Sig |
| Win-Rate | **34.0 %** (71/138) | — | — |
| **Summe R** | **+102.16R** | +99.88R | +93.70R |
| Profit-Faktor | **1.80** | — | — |
| Reißleinen-Auslösungen | **0** | — | — |

**Delta:** **+8.46R über der OOS-Referenz** (+93.70R) und **+2.28R über
der Baseline** (+99.88R) — der Rückbau-Zustand (E3 + Reißleine 46, ohne
E4a-Hülle) ist im S2-OOS-Fenster **nicht schlechter, sondern besser** als
beide v0.4.x-Vergleichslinien.

**Grenzphasen-Bucket (§8.1/§8.2, 4 kritische Phasen):**

| alte Phase | neue Phase | Überleben | Trades / R |
|---|---|---|---|
| Ph8 (02.06–04.06, 1.57 %) | **Phase 8** (identisch, 158 C) | **überlebt eigenständig** | 2 Tr / +0.05R |
| Ph13 (14.07–17.07, 1.81 %) | **Phase 12** (14.07–24.07, 723 C) | **verschmolzen** (mit alter Ph12+Ph14) | 15 Tr / +1.98R |
| Ph19 (22.08–27.08, 1.67 %) | **Phase 16** (identisch, 272 C) | **überlebt eigenständig** | 4 Tr / −3.42R |
| Ph48 (29.10–30.10, 1.95 %) | **Phase 40** (29.10–30.10, 117 C) | **überlebt eigenständig** | 2 Tr / +4.27R |

**Befund (stichpunktartig):**
- **Reißleine: 0 Auslösungen im gesamten S2-Jahr** — kein einziger
  Bruch-Pfad „nicht etabliert" ab C 46 (Log-Suche leer). Die in §8.2
  diagnostizierte Ph13-Exposition (78 C) bleibt ohne reale Auslösung —
  konsistent zur close-basierten Verifikation §8.2a.
- **Ph13-Verschmelzung unschädlich:** Die alte Ph13 (langsame
  Spread-Expansion, ~124 C bis E3) wird Teil der 723-C-Mega-Phase 12
  (14.07–24.07) mit 15 Trades / +1.98R — **keine** AUG-artige
  Monsterphase-Verlustserie (Unterschied zur AUG-Monsterphase §5.3: hier
  kein Trend-SHORT-Hagel gegen die wandernde Oberkante; die Phase blieb
  range-artig und die Reclaim-Signale blieben asymmetrisch).
- **Bucket-Ziel §8.3 Nr. 4:** Die ≥ 2.0 %-Phasen bleiben erhalten;
  der dokumentierte Risiko-Bucket (1.5–2.0 %) verliert nur durch die
  Ph13-Verschmelzung eine eigene Phase — ohne Signalverlust (Trades der
  alten Ph13 laufen in Phase 12 weiter).
- **E3 + Reißleine sind OOS-robust:** Phasen-Zählung sinkt von 62 auf 52
  (E3-Verschmelzungswirkung, −10), die handelbaren Ranges steigen von 22
  auf 26 — die E3-Konsolidierung erzeugt keine Handelbarkeits-Verluste.

**Nächster Schritt (§7 Punkt 9):** S1-OOS-Lauf (Vergleich §3: +199.65R;
S1+S2-Ziel ≥ +292.14R) inkl. Reißleinen-Audit und
Grenzphasen-Bucket-Zählung für S1.

### 8.5 Ursachenanalyse der 52-Tage-Segmentierungslücke S2 (Phase 7 -> Phase 8)

**Befund (statische Code- & Daten-Inspektion, 03.09.2026; kein Lauf).**
Quellen: `test/tmp_oos_S2_lauf.log` (E3-Lauf, 52 Phasen),
`test/tmp_default_run_S2.log` (Baseline v0.4.x, 62 Phasen — beide mit
identischer Lücke), DuckDB read_only (`time AT TIME ZONE 'UTC'`).

**Kernfakten:**

1. **Zeitraum & Datenintegrität:** Phase 7 (S2) endet im Log am
   **Fri 11.04 2025 12:45 UTC** (letzter Touch der UNTEN-Kante, 456 C,
   HANDELBAR); die nächste Phase 8 startet erst **Mon 02.06 2025 19:30 UTC**
   (= exakt die Bruch-Bar von Phase 7). **Lücken-Spanne: 52 Tage / 3237
   M15-Kerzen.** Datenintegrität **100 %**: Im Prüffenster 15.04–05.06
   liegen 3302 kontinuierliche Kerzen; alle Unterbrechungen > 1 h sind
   regulär (täglich 22:45→00:00, Wochenende Fr 22:45→Mo 00:00 = 49.2 h,
   Karfreitag 17.04–21.04 = 73.2 h, 26.05 = 3.8 h). Kein einziges
   Datenloch > 4 Tage.

2. **Ursache — Geburtszonen-Anker fixiert die Bruch-Schwelle:**
   Phase 7 erbte aus ihrem Geburtsfenster (31.03 10:00 → 04.04 13:30,
   Pivots um das 34.19-Hoch) `birth_h = 34.193`. Die Bruch-Referenz ist
   geburtszonen-verankert (`h_ref = max(U, birth_h)`, Z. 697–702 in der
   Arbeitskopie) → **obere Bruch-Schwelle = 34.193 + TOL 0.34 = 34.533**.
   Die OBEN-Entwicklung im Log bestätigt die Starre: **0 Verschiebungen,
   Kante konstant 34.193** über die gesamte Phasenlaufzeit. Der Markt
   konsolidierte 52 Tage **unterhalb** dieser Schwelle (max. Close vor
   02.06 19:30: **34.508** am 02.06 19:15 — nie ein einzelner Close >
   34.533, geschweige ein bestätigendes Paar). Erst **02.06 19:30/19:45**
   folgte das erste 2-Close-Paar darüber (34.547 / 34.538) → UP-Bruch →
   Move 329 im Log: „UP Fri 12:45 (31.197) → Mon 19:30 (34.577),
   +3.380 USD in **75.285 min** (= 52,3 Tage)".

3. **Kein Seed-Fehlschlag, kein E3-Artefakt:** Der Segmentierungs-Loop
   verwirft **keine** Seeds (`U <= L`), scheitert **nicht** an
   `MIN_PHASE_CANDLES = 46` (Phase 7 war seit ~07.04 etabliert, der
   Bruch-Check lief die gesamte Zeit) und **nicht** am E3-Gate
   (`MIN_ESTABLISH_SPREAD_PCT`). Die **Baseline v0.4.x ohne E3** (62
   Phasen, `tmp_default_run_S2.log`) zeigt die **identische** Lücke
   (Phase 7 identisch, Phase 8-Start identisch 02.06 19:30) — E3 und
   Reißleine sind damit als Ursache **ausgeschlossen**. Ursache ist
   ausschließlich die Geburtszonen-Verankerung der Bruch-Referenz
   (Baseline-Verhalten, §5.3 R2).

4. **Phänomen — „Stale Phase":** Phase 7 blockierte den Sequenzer über
   52 Tage, ohne selbst Trades zu generieren (verifiziert im Log:
   85 Reclaim-Trades bis 11.04, **0** zwischen 11.04 und 02.06, 4 ab
   02.06). Eine neue Phase wird ausschließlich bei einem Bruch
   initialisiert (`i = brk_idx`, Z. 782) — ohne Break-Ereignis läuft der
   äußere while-Loop die gesamte Lücke in der Iteration von Phase 7.
   **Strukturelle Einordnung:** Spiegelbild zur R1-Fragmentierung (§2):
   Dort sterben Phasen an engen lokalen Kanten zu früh (Fragmentierung),
   hier hält der Geburtsanker eine Phase künstlich am Leben (Verschmelzung/
   Erstarren). Beides ist Tier-1-Segmentierungs-Verhalten, kein Daten- oder
   E3-Problem; eine Auflösung (z. B. Stale-Phase-Guard / altersbasierte
   Kanten-Erneuerung) wäre Gegenstand eines separaten Folge-Experiments.

### 8.6 S1-OOS-Lauf & bitgenaue Obduktion B-Ph46 / E3-Ph46 & B-Ph132 (03.09.2026)

**Ausführung S1-OOS (Arbeitskopie, E3-Gate 1.5 % + Reißleine 46 C):**
`python scripts/phasen_makro_swings.py --start=2026-02-05 --ende=2026-08-28`
(Baseline-Modus). Artefakte: `test/tmp_oos_S1_lauf.log`,
`test/stats_trades_MAKRO_S1.txt`, `test/phasen_makro_swings_S1.png`
(gitignored). **Modus:** Inspektion + DuckDB read_only + bitgenaue
Zone-Replikation (Helper `test/tmp_obduktion_trace.py` u. a., I4-konform,
danach löschen). Kein Produktions-Code berührt.

#### A. S1-OOS-Ergebnis — nicht freigabefähig

| Kennzahl | S1-OOS (E3+Reißleine) | S1 Baseline v0.4.x | S1 OOS-Referenz v0.4.x (`--macro-live`) |
|---|---|---|---|
| Phasen gesamt | **130** | 139 | — |
| Handelbar | **49** | 40 | — |
| Trades | **216** (120 L / 96 S) | 201 Sig | 199 Sig |
| Win-Rate | **41.7 %** (90/126/0) | — | — |
| **Summe R** | **+172.92R** | +197.26R | +199.65R |
| Profit-Faktor | **2.57** | — | — |
| Reißleinen-Auslösungen | **0** | — | — |

- **Delta S1: −24.3R gegen Baseline (201/+197.26R), −26.73R gegen die
  OOS-Referenz (199/+199.65R).** S1+S2 der Arbeitskopie = +172.92 +
  +102.16 (§8.4) = **+275.08R < Ziel ≥ +292.14R** → **OOS nicht
  freigabefähig**; §7-Punkt-9-Frage für S1 ist damit beantwortet (negativ).
- AUG-Verifikation im S1-Lauf: Phase-1/2-Anker ab 21.08 OK. **Tail-Abweichung:**
  3 statt 4 Phasen ab 21.08 — E3-Ph130 (Mi 26.08 03:45 → Do 27.08 19:00,
  154 C, 24H/21L) **verschmilzt** den Base-Split (53 C + 102 C, §5.3-Muster).

**Delta-Attribution (bitgenau geparst, Base 201 Tr/+197.26R → E3 216 Tr/+172.94R,**
Δ ≈ −24.3R; Rundungsdifferenz zu stats +172.92):
- **17 neue handelbare Fenster: +43.18R** (37 E3-Trades) — die Baseline
  hatte dort bereits +35.20R (12 Tr) → **Netto neuer Phasen: +7.98R** →
  nicht die Verlustquelle.
- **Verändertes Verhalten alter Phasen: −32.30R** = gesamte Verlustquelle.
  Haupttäter: **B-Ph46** (Δ−10.92R), **B-Ph132** (Δ−3.17R), B-Ph23
  (+17.79R → +14.13R, Δ−3.66R), diverse Label-/Fenster-Verschiebungen.
- **[HANDELBAR] ist post-hoc-Label, kein Trade-Filter** (größter
  Baseline-Gewinner B-Ph23 war nicht handelbar).

#### B. Obduktion Fall 1 — B-Ph46 vs. E3-Ph46 (09.–14.04.2026)

**Segmentierung:** Base = Ph45 (Do 09.04 19:00 → Fr 10.04 10:45, 60 C) +
Ph46 (Fr 10.04 15:45 → Mo 13.04 17:00, 98 C, HANDELBAR). E3 = **eine**
Phase 46 (Do 09.04 19:00 → Mo 13.04 17:00, 177 C, HANDELBAR) —
Zusammenlegung der Base-Ph45+46 (E3-Bruch-Schwelle Fr Nachmittag nicht
erreicht).

**Trade-Objekte (Bitgenau):**
- **Base-Ph46 (2 Trades, +10.21R):** (1) Signal Fr 10.04 18:00 LONG in_bar
  Ein 76.076 | SL 75.734 | TP1 76.442 | TP2 76.534 | CRV 1.07 | Bo 2 →
  −0.48R. (2) Signal **Mo 13.04 00:15** LONG in_bar Ein **72.901** (Open
  00:30) | SL 72.573 | TP1 **76.284** (=POC) | TP2 76.449 | CRV 10.31 |
  Bo 2 → H1 +10.31R, H2 +10.82R → **+10.69R**.
- **E3-Ph46 (5 Trades, −0.71R):** Do 20:45 −1.00; Fr 01:15 −1.00
  (next_bar); Fr 04:30 −0.47; Fr 10:45 +2.76 (next_bar); Fr 15:15 −1.00.
  Die ersten 3 sind **identisch** mit Base-Ph45; Fr 10:45/15:15 existieren
  nur in E3 (Base-Lücke 10:45–15:45); **beide Base-Ph46-Trades fehlen**
  (Fr 18:00 −0.48 **und** Mo 00:15 +10.69).
- Fenstervergleich (Do 19:00 → Mo 17:00): Base P45+P46 = −2.47 + 10.21 =
  **+7.74R** vs. E3-Ph46 **−0.71R** → **Δ ≈ −8.45R** (bzw. −10.92R gegen
  B-Ph46 allein).

**Warum der +10.69R-Trade im E3-Lauf nicht generiert wird** (bitgenaue
Zone-Replikation `test/tmp_obduktion_trace.py`, 100 % reproduziert):
- Mechanik LONG: Bar k mit `lo[k] < L_eff` (laufende Zonen-Unterkante =
  Volume-Zone-VAL) und `close[k] ≥ L_eff` → in_bar (k+1); sonst
  `close[k+1] ≥ L_eff` → next_bar (k+2); Einstieg nur `< POC`, Bounce ≥ 2,
  Cooldown ≥ 12, CRV ≥ 1.
- **E3-Kontext (Zone Do 19:00 → k):** Bei k = Mo 00:15 ist `L_eff =
  75.116` (Freitags-Profil dominiert; Dip-Volumen noch nicht
  VA-relevant). lo 72.568 < 75.116 ✓, aber close 72.896 **< 75.116** →
  Reclaim fehlt; close[k+1] 73.342 < 75.116 → auch next_bar verneint. Ab
  k = 00:30 fällt `L_eff` auf 72.639 (Dip-Volumen absorbiert) → alle
  späteren Lows (≥ 72.84) ≥ L_eff → **nie wieder Kandidat**. Erster
  Reclaim über ~75.1 erst Mo 18:15+ → **außerhalb Phasenende Mo 17:00**.
- **Base-Kontext (Zone Fr 15:45 → k, dünnes Profil):** Bei k = Mo 00:15
  ist `L_eff = 72.639` → lo 72.568 < L ✓ **und** close 72.896 ≥ L ✓ →
  in_bar @ Mo 00:30 open 72.901 < POC 76.284 ✓, Bounce nb=2 ✓, Cooldown ✓,
  CRV 10.31 ≥ 1 ✓ → **Signal exakt reproduziert** (Trace-Zeile:
  „SIGNAL in_bar @ 00:30 open 72.901, nb=2, CRV=10.31").

**E3-Ph46-Ende / Bruchbar (exakt):** up-Bruch **Di 14.04 05:45**. `h_ref`
= 76.539 (0 U-Shifts seit Fr 21:00) → Schwelle h_ref+TOL = **76.879**.
Closes 05:45 76.930 & 06:00 76.890 > 76.879 → brk_idx 05:45; Ende-Touch
Mo 17:00 (L-Geburtszone 73.598, letzter Touch 73.701). Base-Ph46 dagegen:
h_ref 76.412 → Schwelle **76.752** → Closes 05:30 76.795 + 05:45 76.930 >
76.752 → Bruch schon **05:30** (daher Ph47-Start Base 05:30 vs. E3 05:45,
1 Bar). Down-Bruch-Versuch in E3 Mo 00:15: l_ref = 73.598 (birth_l) →
Schwelle 73.258; nur **ein** Close darunter (00:15 C 72.896), Folge-Close
73.342 ≥ → kein 2-Close → Phase überlebt.

#### C. Obduktion Fall 2 — B-Ph132 (R1-Zone 14.–18.08.2026) / Reißleine

**Baseline Ph132 (Fr 14.08 03:00 → Di 18.08 03:15, 186 C, HANDELBAR,
22H/27L) — 7 Trades +8.31R:** Fr 08:45/11:45/14:45 SHORT je −1.00; Mo
17.08 04:30 −1.00; Mo 07:30 −1.00; Mo 19:00 **+6.71R** (TP2 63.816); Di
18.08 02:15 **+6.60R** (TP2 63.816).

**E3-Zerlegung:** Ph123 (Fr 14.08 03:00 → Fr 09:30 [Touch], 27 C,
**NICHT handelbar**, U 64.035 / L 63.485 → Spread **0.87 % < 1.5 %** →
est_idx **nie** gesetzt) + Ph124 (Mo 17.08 03:00 → Di 18.08 03:15, 94 C,
U 66.468 / L 65.510). **E3-Trades R1-Zone (+5.14R):** Ph123 Fr 08:45 −1.00;
Ph124 Mo 17:45 +3.16 (TP2 65.249); Di 02:15 +2.98 (TP2 65.399) →
**Δ −3.17R** (2 Mo-Shorts entfallen; Gewinner kleiner, weil der TP2 in die
63.8-Zone des 2-Berg-Profils fehlt).

**Reißleine (DuckDB-verifiziert, exakt):**
- p0 = C Fr 14.08 03:00 = **63.926**; Schwelle oben = p0 × 1.03 =
  **65.844** (RUNAWAY_MULT 2.0 × MIN_ESTABLISH_SPREAD_PCT 1.5 %).
- **Kein früherer Trigger:** Fr 14.08 max High 65.684 < 65.844 (auch kein
  intrabar-Kontakt).
- **Erster 2-Close-Trigger: Mo 17.08 03:00 C 65.850 + 03:15 C 65.866** >
  65.844 → brk_idx = Mo 03:00 (Candle **92** ab Phasenstart ≥
  RUNAWAY_MIN_CANDLES 46 ✓).
- Die „3-Tage-Lücke" ist **kein Datenloch**, sondern das reguläre Wochenende;
  die junge, nie etablierte Phase saß über das Wochenende und der
  Montags-Gap-Up trippte die 3 %-Schwelle.
- **Baseline anders:** ohne E3-Spread-Gate etablierte sich Ph132
  (touch-basiert); der Bruch-Check lief gegen die lokale Kante U ≈
  66.33 → 66.47 (+TOL 0.34) — die Mo-Bewegung blieb darunter → Phase
  überlebte und erzeugte die Gewinner-Trades mit TP2 in die 63.8-Zone.

#### D. Muster & Einordnung

1. **E3-Verschmelzung (Riesenprofil) verschiebt die Zonen-Unterkante
   `L_eff` nach oben** → Reclaim-Longs nach tiefen Dips werden unterdrückt
   (Ph46: der Dip-Rebound aus 72.568 blieb unter der Freitags-L_eff 75.116;
   das Phasenende Mo 17:00 schnitt den verspäteten Reclaim ab).
2. **E3-Spread-Gate + Reißleine töten junge, nie etablierte Phasen über
   Wochenenden**, die die Baseline überlebt hätte (Ph132: Gap-Up trippt die
   3 %-Reißleine statt Etablierung am Mo 03:00).
3. Beide Fälle = **−8.45R (Ph46-Window) bzw. −10.92R (B-Ph46-Zuordnung)
   + −3.17R (Ph132)** ≈ −11.6 … −14.1R der −24.3/−26.7R-Deltas; Rest aus
   weiteren Einzel-Phasen-Verschiebungen (u. a. B-Ph23 Δ−3.66R).
4. Deckungsgleich mit dem §5.3-Muster (AUG-Monsterphase): E3-Riesen-Profile
   brechen die Signal-Asymmetrie der Reclaim-Engine — jetzt **OOS über S1
   quantifiziert**. Zusammen mit dem AUG-Tail (Ph130-Verschmelzung) und der
   §8.5-Stale-Phase ist die E3-Verschmelzungsneigung der dominante
   OOS-Schwachpunkt der Arbeitskopie.
5. **Entscheidung:** OOS **nicht freigabefähig** (S1+S2 +275.08R <
   +292.14R-Ziel). Arbeitskopie bleibt experimentell/uncommitted;
   Produktions-Baseline unberührt. Anpassungsoptionen (offen, §7): (a)
   Reclaim-/Zonen-Referenz gegen die E3-verschobene Unterkante
   stabilisieren; (b) Wochenend-/Gap-Regel für die Reißleine (Trigger erst
   ab N Bars nach Session-Wiedereröffnung); (c) Stale-Phase-Guard (§8.5)
   und AUG-Tail-Verschmelzung berücksichtigen. Jede Anpassung erneut gegen
   den AUG-Regressionsanker (11 Ph / 26 Sig / +27.06R).
6. **Helper (I4, danach löschen):** `test/tmp_obduktion_p46.py`,
   `test/tmp_obduktion_trace.py`, `test/tmp_obduktion_reissleine.py` — **am
   03.09.2026 gelöscht (§8.7).**

### 8.7 CRV2-Filter-Negativbefund & Entscheidung Option A (Rückbau E3) — 03.09.2026

**Hintergrund:** §8.6 hat die E3-Verschmelzung zu Riesenprofilen als
dominanten OOS-Schwachpunkt identifiziert (S1+S2 +275.08R < Ziel
+292.14R). Vor der Segmentierungs-Entscheidung wurde eine denkbare
Korrektur auf der **Signalebene** geprüft: ein Mindest-Raum-Filter auf
`crv2` (= |TP2 − Einstieg| / |SL − Einstieg|; TP2 = Box-Ende an der
gegenüberliegenden Kante U/L ± 0.2 %-Puffer; im Code berechnet Z. 1220/1272,
aber **nie als Gate geprüft** — nur Reporting, Z. 1572/1579).

**Empirischer Befund (statistische Log-Analyse, reine Inspektion, 03.09.2026):**
Quellen: `test/tmp_rueckbau_AUG_lauf.log` (26 Tr, +27.06R),
`test/tmp_oos_S1_lauf.log` (216 Tr, +172.94R), `test/tmp_oos_S2_lauf.log`
(209 Tr, +102.18R). CRV2 je Trade aus Ein/SL/TP2 (Log-3dp) berechnet;
Parse bitgenau (CRV-Gegenprobe ±0.01–0.03 Rundung bei großen Werten).
CRV2-Verteilung: min **AUG 1.36 / S1 1.10 / S2 0.98**; Median
3.42/3.44/3.60; max 6.0/18.6/18.0 → Signale mit CRV2 < 1.0 existieren
praktisch nicht (nur 1 S2-Trade).

**Simulation „Filter: Trade entfernen, wenn crv2 < Schwelle" (je Fenster):**

| Fenster | Schwelle | gefiltert | Verlust-Tr | gerettete R | Gewinn-Tr | verlorene R | **Netto-R** |
|---|---|---|---|---|---|---|---|
| AUG | 1.0 | 0 | 0 | 0.00 | 0 | 0.00 | **±0.00** |
| AUG | 1.2 | 0 | 0 | 0.00 | 0 | 0.00 | **±0.00** |
| AUG | 1.5 | 2 | 1 | +1.00 | 1 | −1.29 | **−0.29** |
| S1 | 1.0 | 0 | 0 | 0.00 | 0 | 0.00 | **±0.00** |
| S1 | 1.2 | 2 | 0 | 0.00 | 2 | −2.30 | **−2.30** |
| S1 | 1.5 | 6 | 2 | +2.00 | 4 | −4.96 | **−2.96** |
| S2 | 1.0 | 1 | 0 | 0.00 | 1 | −1.05 | **−1.05** |
| S2 | 1.2 | 2 | 0 | 0.00 | 2 | −2.11 | **−2.11** |
| S2 | 1.5 | 7 | 3 | +3.00 | 4 | −4.63 | **−1.63** |

Alle gefilterten Verluste sind **−1.00R-Voll-SL**; alle gefilterten
Gewinne sind **echte TP1+TP2-Treffer mit kleinem R** (+1.05 … +1.47,
CRV nahe 1.0).

**Wirkung auf S1 & S1+S2 (Anker: stats +172.92/+102.16 → 275.08):**

| Schwelle | S1-Netto | S1 neu | S1+S2-Netto | S1+S2 neu |
|---|---|---|---|---|
| 1.0 | ±0.00 | 172.92R | −1.05 | 274.03R |
| 1.2 | −2.30 | 170.62R | −4.41 | 270.67R |
| 1.5 | −2.96 | 169.96R | −4.59 | 270.49R |

**Befund & Grund:**
1. **In allen Fenstern und allen Schwellen netto negativ** (−0.29R …
   −2.96R). Der Filter spart nur −1.00R-Voll-SL-Treffer und schneidet
   dafür **funktionierende Reversion-Winner** ab, deren R ≈ CRV2 ≈
   1.1–1.5 knapp über der Schwelle liegt — er entfernt exakt die
   „engen, aber voll treffenden Boxen", die das Ergebnis stützen.
2. **Grund:** Das bestehende POC-Gate (CRV ≥ 1.0 auf TP1 = POC,
   Z. 1221/1273) greift bereits — jedes Signal hat mindestens ~1R
   POC-Raum. CRV2 gegen die Gegenseite ist dadurch fast immer ≥ 1.0
   (nur 1 Trade < 1.0 über alle drei Fenster): Eine Mindest-CRV2 ≥ 1.0
   hätte praktisch **keine** Filterwirkung; erst ≥ 1.2/1.5 greift und
   schneidet dann profitable Trades.
3. **Verdikt: CRV2-Filter endgültig verworfen.** Es wird **kein**
   Mindestabstands-/Raum-Filter auf die Gegenseite (TP2/U bzw. L)
   eingeführt; TP2 bleibt reines Box-Ende und CRV2 reine Reporting-Größe.
   AUG-Regressionsanker bestätigt: bei Schwelle 1.5 fiele AUG auf
   +26.77R (Δ−0.29R unter Rückbau-Stand +27.06R).
4. **Konsequenz:** Die OOS-Lücke wird **nicht auf der Signalebene**
   geschlossen. Der Raum-Filter-Ansatz (Vorprüfung im Signal-Loop) ist
   damit empirisch abgeschlossen.

**Entscheidung Option A — Rückbau E3 (arretiert, 03.09.2026):**
- Die OOS-Lücke wird durch **Rückbau des E3-Etablierungs-Gates** in der
  Segmentierung adressiert: `MIN_ESTABLISH_SPREAD_PCT` (1.5 %) entfernen
  → Etablierung wieder **touch-basiert** (`MIN_ESTABLISH = 4`) wie in der
  Produktions-Baseline → keine E3-Verschmelzung zu Riesenprofilen
  (Ph46/Ph130-Muster, §8.6 D) mehr.
- **Damit revidiert:** §5.3 Punkt 1 („E3 bleibt erhalten") und §5.4.1
  („1.5 % verbindlich fixiert") — diese Entscheide beruhten auf
  AUG-only-Kalibrierung; der OOS-Befund §8.6/§8.7 belegt E3 über S1+S2
  als **netto-schädlich** (S1 −24.3/−26.7R; S2-Einzelergebnis +8.46R war
  E3-getragen, aber die S1-Verluste überwiegen im S1+S2-Ziel).
- Die **Reißleine** (RUNAWAY_MIN_CANDLES 46 / RUNAWAY_MULT 2.0) wird
  ebenfalls zurückgebaut: 0 Auslösungen in S1/S2-OOS und im
  Baseline-Modus (est_idx früh) wirkungslos; sie gehört zum selben
  E3-Experiment-Block (Z. 216–219). Ziel: Arbeitskopie wird
  **segmentierungs-bitgenau zur Produktions-Baseline** (Vergleich gegen
  §3 direkt möglich).
- **Erwartung nach Umsetzung:** S1 ≈ Baseline 201 Sig / +197.26R, S2 ≈
  Baseline 210 Sig / +99.88R → S1+S2 ≈ +297.14R ≥ Ziel +292.14R
  (bitgenaue §3-Baseline); AUG ≈ 12 Phasen / 27 Sig / +24.97R.
  Verifikation: py_compile; AUG-Regressionslauf; S1/S2-OOS-Lauf.
- **Umsetzungs-Audit (exakte Zeilen, reine Inspektion, kein Eingriff):**
  Konstanten Z. 216–219 · Gate Z. 682–687 · Reißleinen-Zweig
  Z. 713–722 — Diff-Vorschau siehe §7 Punkt 12 (Code-Audit, 03.09.2026).

**VERIFIKATION nach Umsetzung (03.09.2026, Freigabe erteilt):**
- py_compile OK; keine E3-Identifier mehr im Script (17 Zeilen netto entfernt).
- **AUG-Regressionslauf: exakt 12 Phasen / 27 Signale / +24.97R** —
  bitgenau zur Produktions-Baseline (Erwartung erfüllt).
- **S1-Lauf: exakt 139 Phasen / 201 Signale / +197.26R** — bitgenau zur
  S1-Baseline (Erwartung ~+197.26R erfüllt). Die 9 E3-Verschmelzungen
  (130 → 139 Phasen) sind rückgängig; das B-Ph46-Riesenprofil ist
  aufgelöst (Phase 46 wieder eigenständig: Fr 10.04 15:45 → Mo 13.04 17:00,
  98 C; 2 Trades **+10.21R** inkl. Mo 13.04 00:15 **+10.69R** — exakt der
  §8.6-Referenzfall).
- **S1+S2-Prognose bestätigt (S2-Bestätigungslauf, 03.09.2026):**
  S1 **+197.26R** (201 Sig) + S2 **+99.88R** (210 Sig, gemessen,
  bitgenaue §3-Baseline) = **+297.14R ≥ Ziel +292.14R** (+5.00R Delta;
  OOS-Referenz +293.35R übertroffen). S2-Messung: **62 Phasen /
  210 Signale / +99.88R** (WR 35.2 %, PF 1.80). Damit ist die OOS-Lücke
  empirisch geschlossen; die Arbeitskopie `d99abbb` ist **bitgenau
  verifiziert & freigabefähig** (segmentierungs-bitgenau zur
  Produktions-Baseline).
- Belege (gitignored): `test/tmp_optionA_AUG_lauf.log`,
  `test/tmp_optionA_S1_lauf.log`, `test/tmp_optionA_S2_lauf.log`,
  `test/stats_trades_MAKRO_AUG.txt`, `test/stats_trades_MAKRO_S1.txt`,
  `test/stats_trades_MAKRO_S2.txt`, `test/phasen_makro_swings_AUG.png`,
  `test/phasen_makro_swings_S1.png`, `test/phasen_makro_swings_S2.png`.

### 8.8 Tier-2-Veto-Modell (Wand-Regel) — Negativbefund & Abschluss — 03.09.2026

**Hintergrund & Auftrag (Pfad A, Tier-2-Veto-Modell):** §8.7 hat die
Arbeitskopie `d99abbb` auf **segmentierungs-bitgenaue §3-Baseline**
arretiert (S1+S2 +297.14R ≥ Ziel +292.14R). Der verbleibende offene
Fragekomplex war das **Delta der v0.4.x-`--macro-live`-Referenz**
(S1+S2 +293.35R; AUG +34.87R, S2 +93.70R) gegen die Baseline (AUG
+24.97R, S2 +99.88R): AUG profitiert von der Makro-Anbindung (+9.90R),
S2 verliert (−6.18R). Aufgabe: das S2-Delta auditieren und prüfen, ob
der Tier-2-Mechanismus von **Kanten-Substitution** (v0.4-Modell:
Tier-2-Ersatz der lokalen Ausführungs-Kante durch einen Makro-Anker +
E4-Penetrations-Gate, `macro_persistence.py`) auf ein **reines
Veto-Gate** (`allow_trade: bool`; Invariante N_Macro ≤ N_Base) umgebaut
werden kann. **Wichtig:** `find_reclaim_signals` ist in Produktion
(`phasen_volumen_profil.py`) und Arbeitskopie 100 % identisch —
der gesamte Pfad A ist **reine Analyse/Simulation** in `test/`, kein
Produktions-Eingriff.

**Mentor-Wand-Regel (Referenz-Semantik, 03.09.2026):** Wand =
stehende Makro-Zone der **Gegenseite** (LONG → UPPER, SHORT → LOWER),
**unidirektional**, mit **Evidenz ≥ 2** (`ev2+`) und **aktiver Rolle**
(nicht `left_behind`/überrannt); der Trade müsste die Zone zwischen
Entry und TP1 durchlaufen (inklusiv-Entry / exklusiv-TP1). Die separate
Regel R2 (SL-Raum / Liquiditätsjagd) gehört **nicht** zu Iteration 1.
Die statische Veto-Bilanz §5.5 (R1-Puffer AUG, 0/26) bleibt davon
unberührt — hier wird die **Zonen-Ebene** geprüft.

#### 8.8.1 S2-Delta-Zerlegung (bitgenau, instrumentierter Replay)

Die Lauf-Logs enthalten keinen Zonen-Pool-Dump → Replay-Helper gebaut &
ausgeführt: `test/tmp_zonepool_replay.py` (Muster
`test/tmp_makro_state_proto.py::baseline_mod` = exec-Import von
`phasen_volumen_profil.py`, Cut vor der Signal-Sektion, echtes
unverändertes `macro_persistence.py`; **Kausalitäts-Axiom**: Zonen-Pool
je Phase = Scan-Zustand nach `Boundary(p−1)`, VOR `Touches(p)` — die
Touches der laufenden Phase bauen Zonen erst für Folgephasen auf).
Logs: `test/tmp_zonepool_{AUG,S2}.txt`.

**Fidelity bitgenau bewiesen (Selbstvalidierung gegen die
v0.4.x-Referenz-Artefakte):**

| Fenster | Baseline (Replay) | macro-live (Replay) | Tier-2-Anker (exakt reproduziert) |
|---|---|---|---|
| AUG | 27 Sig / +24.97R ✓ | 25 Sig / +34.87R ✓ | 66.364 `ev2 [1,3]`, 66.382 `ev3 [1,3,4]` ✓ |
| S2 | 210 Sig / +99.88R ✓ | 216 Sig / +93.70R ✓ | 31.309, 4× 29.706, 41.373, 41.347 ✓ |

**S2-Delta (210 → 216 Trades, Δ −6.18R):**

| Komponente | Trades | R |
|---|---|---|
| Identisch (bitgenau) | 209 | — |
| **Entfallen** (vom Veto geblockt) | 1 — P27 18.09 07:45 LONG, Ein 41.326 | **+2.01R verloren** |
| **Neu** (Tier-2-Kanten-Ersatz) | 7 — 28.02 (Anker 31.309), 04.04/07.04/08.04/09.04 (Anker 29.706), 17.09 (Anker 41.373), 18.09 (Anker 41.347) | **−4.16R** (6× −1.00R „Falling-Knife" an alten LOWER-Ankern + 1× +1.84R) |
| **Summe** | −1 +7 | **−6.17R ≈ −6.18R** |

**AUG-Δ +9.90R (+24.97 → +34.87R) — zweiteilig:** (a) **Veto-Effekt**
(+4.00R: 4 Verlust-SHORTs der P5/P7 entfallen), (b) **Substitutions-/
Neu-Effekt** (netto +5.90R, darunter der Tier-2-Ersatz-Kandidat
17.08 17:45 SHORT 66.307 → +6.90R via Anker **66.364**). Die
**Wand-Regel-Bilanz** des Replays zeigt: von den 6 v0.4-entfallenen
AUG-Trades haben nur **2** eine echte LOWER-Wand (14.08 11:45/14:45,
je −1.00R); der +6.71R-Winner 17.08 18:45 und die übrigen 3 Verlierer
haben **keine** Wand → ein reines Veto-Gate **erreicht die
Substitutionsquelle (b) nicht** — es kann v0.4 nur approximieren.

#### 8.8.2 Wand-Obduktion auf Bar-Ebene (3 Fenster) — die 2 Interview-Fragen

Helper `test/tmp_wall_obduktion.py` (Bar-Ebene: Wand-Zeilen je Trade mit
`n_ph` = Intra-Phase-Closes jenseits der Wand, `d_ph_last` = Phasen seit
letztem Touch, Alter in Tagen, Trigger-Nähe). Logs:
`test/tmp_wall_obduktion_{AUG,S1,S2}.txt`.

| Fenster | Wand-Zeilen | FP-Winner (Blocken verlöre sie) | TP-Loser (korrekte Vetoes) | n_ph-Bereich |
|---|---|---|---|---|
| AUG | 2 | 0 | **2** (−1.00R/−1.00R) | 24 (beide) |
| S1 | 30 | **14 (+51.64R)** | 16 | 2–147 |
| S2 | 42 | **5 (+23.88R)** | 37 | 1–387 |

**Antwort Frage 1 — „Intra-Phase-Durchbruch erlischt die Zone": NEIN
(datenwiderlegt).** Die Regel „Wand tot, wenn `n_ph_beyond > 0`"
(`R_ph`) verwirft in **allen** Fenstern 100 % der Veto-Wirkung:
AUG 2/2, S1 16/16, S2 37/37 der TP-Loser-Vetoes entfielen (S2 mit
`≥ 2` noch 36/37, da nur 1 Zeile n_ph = 1 hat). **Grund:** Der Reclaim
feuert nach dem Seitentausch der Phasen-Grenzen — die „Wand" liegt auf
der Seite, von der der Preis gerade gekommen ist → der Preis hat sie
intra-phasig praktisch immer schon durchschritten. Eine „unberührte
Wand" (n_ph = 0) existiert als Veto-Kandidat faktisch nie.

**Antwort Frage 2 — „Frische-Cap": NEIN (Achse invertiert).**
Die größten echten Veto-Cluster sind **alt**, der schlimmste
FP-Winner ist die **frischeste** Wand:

- **S2-P7 (09.–11.04.2025, 10× −1.00R SHORT)** — wertvollstes
  Veto-Cluster — trifft Wände mit Alter **38.5–67.3 d**
  (30.654: 65.7–67.3 d, d_ph_last 4; 30.851: 40.2–41.7 d, d_ph_last 2;
  31.119: 38.5–39.1 d, d_ph_last 2). Jedes Frische-Cap (≤ 30 d o. ä.)
  entfernt exakt diese korrekten Vetoes.
- **S2-P49 (05.11 02:30 LONG, +8.63R)** — schlimmster FP — trifft die
  **frischeste** Wand des Datensatzes (48.360: d_ph_last 1, Alter
  6.4 d).
- **S1:** FP-Winner und TP-Loser liegen über **denselben**
  Altersbereich (0.3–50.7 d) — kein Alters-Schnitt trennt sie.

**Zusatzbefund 1 — S2-P49-Sammelwand:** 5 Verlierer (03.11 21:00 +
04.11 04:15/09:00/12:30/16:45, je −1.00R) **und** der +8.63R-Winner
(05.11 02:30) teilen **exakt dieselbe** Wand 48.360
(`ev2 [44,47]`, n=8, 22.10–29.10). Keine Zonen-Regel (Alter, n, ev,
Distanz) kann Versuch 1–5 von Versuch 6 unterscheiden — die 6
Signale sind bis auf die Tick-Reihenfolge identisch positioniert.

**Zusatzbefund 2 — S1-Trigger-Nähe (Retail-Falle auf Zonen-Ebene):**
Mehrere S1-FP-Winner haben ihre Wand **trigger-nah direkt über dem
Entry** — die Regel behandelt den eigenen Reclaim-Trigger als
Hindernis:

| Trade | Entry | Wand | Abstand Wand−Entry |
|---|---|---|---|
| P129 07.08 19:00 LONG +4.22R | 63.175 | 63.227 | **0.05** |
| P61 01.05 10:45 LONG +3.68R | 73.117 | 73.859 | 0.74 |
| P130 11.08 17:30 LONG +4.47R | 64.597 | 64.916 | 0.32 |

#### 8.8.3 Naive geometrische Veto-Bilanz (statisch, Trade-Ebene)

| Fenster | Baseline | geflaggt (naiv) | davon W/L | Netto-R der Geflaggten | Ergebnis mit Veto |
|---|---|---|---|---|---|
| AUG | 27 / +24.97R | 2 | 0W / 2L | −2.00R | +26.97R ✓ |
| S1 | 201 / +197.26R | 23 | 12W / 11L | **+31.16R** | +166.10R ✗ |
| S2 | 210 / +99.88R | 23 | 3W / 20L | −3.74R | +103.62R ✓ |
| **S1+S2** | +297.14R | 46 | 15W / 31L | +27.42R | **≈ +269.7R < Ziel +292.14R** ✗ |

Die naive Regel blockt in S1 12 Gewinner (u. a. +5.62R, +4.51R, +3.69R,
+3.68R) für 11 Verlierer → **Netto −31.16R**; AUG+S2 (+5.74R) können das
nicht kompensieren. **Die naive Wand-Regel scheitert als Alleinregel.**

#### 8.8.4 Distanz-Check 1.0R-Klausel (Schritt 2/3, ausgeführt)

Datenvertrag `WallDistanceCheck` (frozen): `risk = |entry − sl|`,
`distance_in_r = |wand − entry| / risk`, Veto greift je Trade nur, wenn
**≥ 1 Wand mit distance_in_r ≥ 1.0** (die Wand muss ≥ 1R jenseits des
Entrys liegen, damit der Trade bis dorthin „Raum hat" zu scheitern).
Helper `test/tmp_wall_distance.py`; Logs:
`test/tmp_wall_distance_{AUG,S1,S2}.txt`.

| Fenster | geflaggt (naiv) | rehabilitiert (< 1.0R) | verbleibende Veto-Kandidaten | Rehab-Bilanz | Veto-Bilanz (Blocken) |
|---|---|---|---|---|---|
| AUG | 2 | 0 | 2 (64.278, D 1.62/2.16R) | ±0.00 | −2.00R (2 TP) → **+2.00R** |
| S1 | 23 | 11 | 12 | **+15.91R** gerettet (6W +20.26 − 5L −4.35) | **+15.25R** (6W +21.25 − 6L −6.00) → **−15.25R** |
| S2 | 23 | 2 | 21 | **−2.00R** (2 TP-Loser entgehen dem Block) | −1.74R (3W +16.26 − 18L −18.00) → **+1.74R** |
| **Σ** | 48 | **13 (+13.91R)** | **35** | +13.91R | **+11.51R Netto-Gewinner** → Blocken kostet +11.51R |

**Projektion mit 1.0R-Klausel (S1+S2):** S1 = 197.26 − 15.25 =
**+182.0R**; S2 = 99.88 + 1.74 = **+101.6R** → **S1+S2 ≈ +283.6R < Ziel
+292.14R**. Die Klausel rettet zwar 13/48 falsche Blocker (S1-rehab
+15.91R), aber die 35 verbleibenden Veto-Kandidaten sind kumuliert
**Netto-Gewinner** (+11.51R) — in S1 allein dominieren die FP-Winner
(16.04 +1.81, 23.04 +5.62, 01.05 +3.68, 08.05 +1.98, 11.05 +3.69,
11.08 17:30 +4.47).

**Verdikt (arretiert, analog §8.7-CRV2):** Das geometrische
Wand-Veto-Modell ist — naiv **und** mit 1.0R-Mindestabstand — empirisch
**kein netto-positiver Selektor** über AUG/S1/S2. Der v0.4-Erfolg
(AUG-Konter-Eliminierung) entsteht über die **Tier-2-Kanten-
Substitution** (UPPER-Anker + E4-Penetrations-Gate), nicht über eine
LOWER-Wand-Blockade — die Substitutionsquelle ist im reinen Veto-Gate
strukturell unerreichbar (§8.8.1). Der Tier-2-Umbau auf
`allow_trade`-Veto entfällt damit; `macro_persistence.py` (Tier 2,
eingefroren) bleibt unverändert.

**Offene Optionen (Benutzer-Entscheidung, kein automatischer nächster
Schritt):** (a) Regime-/Trigger-Hypothese (Konter nur in bestimmten
Makro-Zuständen); (b) Veto-Gate-Simulation mit **echter
Tier-2-Cooldown-Kaskade** (Nachbau des v0.4-Substitutionsmechanismus in
der Arbeitskopie, Muster `tmp_v04_kapsel_sim`); (c) Abschluss des
Pfads A ohne weitere Analyse (v0.4-Referenz bleibt wie in §3
eingefroren; Arbeitskopie `d99abbb` = freigegebene Baseline).

**Belege (gitignored, in `test/` als Quellen vorerst erhalten; I4-
Cleanup erst nach Abschluss der Explorationsphase):**
`test/tmp_zonepool_replay.py`, `test/tmp_wall_obduktion.py`,
`test/tmp_wall_distance.py`, Logs `test/tmp_zonepool_{AUG,S2}.txt`,
`test/tmp_wall_obduktion_{AUG,S1,S2}.txt`,
`test/tmp_wall_distance_{AUG,S1,S2}.txt`.

### 8.9 Baseline-Fehltrade-Audit AUG (15 Losses) — Kausale Obduktion & Muster-Befund — 03.09.2026

**Hintergrund & Auftrag (Pfad B, neue Untersuchungsreihe):** Nach dem
Abschluss von Pfad A (§8.8, Tier-2-Veto verworfen) und der
Workspace-Bereinigung (I4) wird die **reine Baseline-Engine**
(`scripts/phasen_volumen_profil.py`, Produktion; Arbeitskopie
`phasen_makro_swings.py` im Baseline-Modus — beide identisch,
`find_reclaim_signals` 100 % bitgenau) auf **systemische Schwachstellen
in den Verlust-Trades** durchleuchtet. Untersuchungsreihenfolge strikt
sequentiell: AUG (2026) → S1 (2026) → S2 (2025). Setup C bleibt
zurückgestellt. **Modus:** reine Code-/Log-/DuckDB-Exploration
(read_only, exec-Import-Cut nach dem Baseline-Signal-Loop), kein
Sandbox-Run, kein Produktivcode.

**Faktenbasis (State of Truth):** `test/stats_trades_AUG.txt`
(Baseline-Block): **27 Trades, 12 W / 15 L, +24.97R, PF 2.83**.
Die anfangs präsentierte 15-Zeilen-Tabelle (abweichende P1-Preise,
P2-LONG, 11/4-Verteilung) wurde als **synthetisches Artefakt eines
früheren Zwischenstands** verworfen; die 15 Verlust-Trades sind die
per Log verifizierten Trades 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 16, 17,
18, 22, 26.

#### 8.9.1 Methodik: bitgenauer kausaler Replay (Phase 1+2)

**Helper:** `test/tmp_baseline_loss_replay.py` → Log
`test/tmp_baseline_loss_replay.txt`. **Vorgehen:** exec-Import von
`scripts/phasen_volumen_profil.py` mit **Cut NACH dem Baseline-
Signal-Loop** (`reclaim_signals.sort`, Z. ~1389) → die **original
erzeugten 27 ReclaimSignal-Objekte** (mit `.phase`, `.trade`,
`.U_laufend/.L_laufend/.POC/.crv/.bounce_nr`, `ts`) stehen im
Namespace — kein eigener Loop-Nachbau, damit keine Replikationsfehler.
**Fidelity:** Mapping Log↔Replay **27/27 bitgenau** (bar_signal,
bar_entry, Richtung, Entry-Preis 1e-9, R ±5e-3), Phasen-Zuordnung
27/27. Pro Trade kausal angereichert: Profilalter (Bars seit
Phasenstart), Kante, POC, POC-Distanz (R), Penetrationstiefe
(hi[k]−U bzw. L−lo[k]), Reclaim-Tiefe (U−cl[k] bzw. cl[k]−L),
Bounce-Nr, Cooldown-Gap, Auflösung (H1/H2-Grund, r1/r2, Exits).

#### 8.9.2 Trigger-Integrität: 100 % regelkonform

**Kein einziger Regelverstoß in den 15 Losses** (und in allen 27):
- **Cooldown ≥ 12 strikt eingehalten:** keine Gap < 12 (P5-Serie:
  None→12→12→48→15; die exakten 12er sind legal am Minimum).
- **POC-Gate CRV ≥ 1.0:** immer erfüllt (Loser-Min 1.04, T9).
- **Bounce ≥ 2:** immer erfüllt (Loser-Min 2).
- **Reclaim-Bedingung** (in_bar: close innerhalb; next_bar:
  close[k+1] innerhalb): per Konstruktion des Original-Codes erfüllt.
- **Kein Lookahead / kein Off-by-One:** der Cut garantiert die
  originale kausale Schleife.

**Verdikt:** Die 15 Losses sind **kein Bug** — sie sind regelkonform
ausgelöste Trades, deren statistische Kostenstruktur untersucht wird.

#### 8.9.3 Die 15 Verlust-Trades (kausal, auditierte Kenngrößen)

| # | Ph | Signal-Zeit | Rc | Entry | R | Alter | Kante | POCdist | Pen | RcDepth | CD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | P1 | 10.08 08:45 | nb | 64.163 | **−0.29** | 36 | 64.177 | 1.85 | 0.096 | 0.020 | 27 |
| 4 | P2 | 10.08 18:00 | ib | 65.098 | −1.00 | **7** | 65.134 | 1.51 | 0.122 | 0.037 | — |
| 5 | P2 | 10.08 21:45 | ib | 65.722 | −1.00 | 22 | 66.019 | 2.11 | **0.007** | 0.299 | 15 |
| 7 | P3 | 11.08 07:30 | ib | 64.702 | −1.00 | **2** | 64.470 | 1.13 | **0.015** | 0.234 | — |
| 8 | P3 | 11.08 12:15 | nb | 64.968 | −1.00 | 21 | 65.029 | 1.65 | 0.093 | 0.053 | — |
| 9 | P5 | 14.08 08:45 | nb | 64.244 | −1.00 | 24 | 64.309 | 1.04 | 0.051 | 0.068 | — |
| 10 | P5 | 14.08 11:45 | nb | 64.750 | −1.00 | 36 | 64.790 | 2.70 | 0.093 | 0.041 | **12** |
| 11 | P5 | 14.08 14:45 | nb | 64.910 | −1.00 | 48 | 65.038 | 3.27 | 0.054 | 0.123 | **12** |
| 12 | P5 | 17.08 03:45 | ib | 65.671 | −1.00 | 96 | 65.752 | 3.18 | 0.120 | 0.081 | 48 |
| 13 | P5 | 17.08 07:30 | ib | 65.769 | −1.00 | 111 | 65.798 | 3.50 | 0.069 | 0.034 | 15 |
| 16 | P6 | 18.08 22:00 | ib | 63.500 | −1.00 | 21 | 63.478 | 1.04 | **0.013** | 0.023 | — |
| 17 | P6 | 19.08 02:00 | ib | 63.011 | −1.00 | 33 | 62.855 | 2.80 | 0.048 | 0.157 | **12** |
| 18 | P7 | 19.08 21:45 | nb | 66.316 | −1.00 | 17 | 66.341 | 1.47 | 0.076 | 0.024 | — |
| 22 | P9 | 24.08 02:15 | ib | 68.974 | **−0.36** | 82 | 68.791 | 1.57 | **0.001** | 0.185 | — |
| 26 | P12 | 27.08 03:15 | ib | 69.041 | −1.00 | 39 | 69.126 | 3.34 | 0.117 | 0.087 | — |

(Zeiten = Signal-Bar; Rc = reclaim in_bar/next_bar; Alter = Bars seit
Phasenstart; POCdist/Pen/RcDepth in USD bzw. R; CD = Cooldown-Gap in
Bars, None = erstes Signal der Richtung in der Phase.)

**Auflösungs-Struktur:**
- **13 Voll-SL:** beide Hälften (25 %/75 %) laufen in den SL
  (H1 = H2 = SL, r1 = r2 = −1.00R; bei SL_TRIGGER am Entry-SL 0.45 %).
- **2 Teilverluste:**
  - **T3** (SHORT, P1, −0.29R): H1 = **TP1 (POC 63.628) +1.85R**
    erreicht, H2 = SL → r = 0.25×(+1.85) − 0.75 = **−0.29R**.
  - **T22** (LONG, P9, −0.36R): H1 = **TP1 (POC 69.461) +1.57R**
    erreicht, H2 = SL → r = 0.25×(+1.57) − 0.75 = **−0.36R**.
  → **Die Trigger-Richtung stimmte** (POC = TP1 wurde sauber erreicht);
    die 75 %-Restcharge wurde am SL (0.45 % über/unter Entry)
    abgeräumt, **bevor** TP2 (Box-Ende ±0.2 %) lief. Das ist ein
    **TP2-Reichweiten-Thema** (TP1→TP2-Strecke zu groß bzw. Markt
    drehte nach TP1 zurück), **kein Signal-/Trigger-Fehler**.

#### 8.9.4 Widerlegung naiver Filter (Kontrollgruppe = 12 Winner)

**Filter-Hypothese 1 — „Profilalter trennt": NEIN.**
11/15 Loser haben Alter < 40, aber **5/12 Winner ebenfalls** — darunter
T25 (P12, **Alter 2**, +1.83R), T1 (P1, Alter 9, +1.29R), T2 (Alter 15,
+1.69R), T19 (Alter 31, +4.26R), T20 (Alter 35, +3.06R). Median:
Loser 33 vs. Winner 56 — Tendenz, aber **kein sauberer Schnitt**:
ein Mindestalter (z. B. ≥ 40) würde T25/T1/T2/T19/T20 (zusammen
+12.21R) opfern. **Profilalter allein ist kein Diskriminator.**

**Filter-Hypothese 2 — „Mikro-Penetration/Reclaim-Tiefe trennt":
NEIN.** T22 verlor mit Penetration **0.001** (1 Cent!), aber T25
(0.016), T1 (0.038), T6 (0.033) gewannen mit ähnlich kleinen
Penetrationen. Reclaim-Tiefe ebenso: Winner T1/T6/T24 haben RcDepth
0.008/0.005/0.008 — **kleiner** als die meisten Loser. Ein
Mindest-Penetrations-/Reclaim-Tiefen-Filter würde die Winner-Klasse
treffen. **Mikro-Trigger sind kein Fehlerbild.**

**Konsequenz:** Die Losses sind nicht über einfache geometrische
Schwellen (Alter, Penetration, Reclaim-Tiefe) von den Winnern
trennbar — eine Filter-Simulation wäre nach §8.7/§8.8-Methodik
zwingend mit der Winner-Kontrollgruppe zu führen, bevor irgendein
Gate in Betracht gezogen würde.

#### 8.9.5 Strukturmuster (institutionelle Kategorisierung)

**Muster A — Expansion-Trap / Kanten-Drift (dominant, 9–11 der 15):**
Der Algorithmus shortet in eine laufende Aufwärtsbewegung bzw. longest
in eine Abwärtsbewegung, während die **kausale Kante (U_zone aus dem
kumulativen Profil ab Phasenstart, Min-Candles = 0) nachzieht**. Die
P5-Serie (T9–T13) ist **zweigeteilt**, nicht homogen:

| Sub-Phase | Trades | Kausale Kante | Marktkontext |
|---|---|---|---|
| Fr 14.08 (Erholung nach R1-Verlassen-Drop) | T9–T11 | 64.309 → 64.790 → **65.038** (zieht nach) | SHORT in die Erholung 64.2 → 65.0 |
| Mo 17.08 (echte Expansion) | T12–T13 | 65.752 → **65.798** (zieht nach) | SHORT in die Expansion → 66.4 |

Kritische Einordnung: **T14/T15 (+6.71R/+6.60R) shorteten exakt
dieselbe Kante 66.284 wenige Bars nach T13 und trafen den Turn.** Die
P5-Verlustserie ist damit die **Kostenstruktur des Fade-Edges**, nicht
ein Einzelfehler — die Trend-Expansion kostet seriell, bevor der Turn
vergütet. Dieselbe Mechanik in P6 (T16/T17: LONG in den Fall 63.5 →
62.8) und P2/P3 (T4/T5/T7/T8: junge Phasen, Kante frisch).

**Muster B — Junge Profile / unfertige POC-Bildung (11/15, überlappend
mit A):** Bei Alter < 40 ist das Volumenprofil noch dünn; die
`_laufende_zone` (kumulativ ab `i_start`) liefert eine Kante, die mit
jeder Bar mitwandert (`MIN_RECLAIM_CANDLES = 0`, Z. 221/1110 —
Signale ab Bar 1 einer Phase). Der „Reclaim" stützt sich auf eine
Kante ohne etablierte institutionelle Relevanz. **Aber:** junge Profile
gewinnen auch (T25 Alter 2, +1.83R) — Muster B ist eine
**Risiko-Konzentration**, kein deterministischer Verlust.

**Muster C — Teilverlust/TP2-Reichweite (T3, T22):** siehe §8.9.3 —
TP1 (POC) erreicht, Restcharge vor TP2 ausgestoppt.

#### 8.9.6 Zwischenfazit AUG & offene nächste Schritte

1. **Trigger-Integrität: 100 % regelkonform** — kein Logikfehler im
   Regelwerk; die 15 Losses sind regelkonforme Kosten des Fade-Edges.
2. **13 Voll-SL = Kosten in Trend-Expansionen (Muster A) und jungen
   Profilen (B); 2 Teilverluste = TP2-Reichweiten-Thema (C), kein
   Signalfehler.**
3. **Naive geometrische Filter (Alter, Penetration, Reclaim-Tiefe)
   sind datenwiderlegt** — die Winner-Kontrollgruppe (T25/T1/T2/T19/T20)
   überlappt die Loser-Klasse.
4. **Nächste Schritte (strikt sequentiell, Benutzer-Freigabe):**
   Schritt 2 = S1-Obduktion (2026, ~90 Verlust-Trades) mit derselben
   Methodik — prüft, ob Muster A/B in S1 dominieren und ob die
   Winner-Überlappung dort kleiner ist; Schritt 3 = S2 (2025,
   Low-Vol-Regime); Schritt 4 = Synthese/Prüfbericht (echter Logikfehler
   vs. statistische Reibungsverluste eines gesunden Edges).

**Belege (gitignored, in `test/` als Quellen vorerst erhalten):**
`test/tmp_baseline_loss_replay.py`, `test/tmp_baseline_loss_replay.txt`
(104 Zeilen, vollständiger Report inkl. Winner-Kontrast und
Phasen-Liste mit i_start/i_ende).
