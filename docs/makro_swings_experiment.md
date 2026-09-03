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
| 03.09.2026 | **OOS-Vorbereitung §8 (Grenzphasen-Inspektion S2, Log statisch):** Ph8/19/48 etablieren unter E3 vor C 46 (keine Reißleinen-Exposition); **Ph13 kritisch** (1.5 % erst nach ~124 C → 78 C exponiert, keine Auslösung im Kanten-Verlauf); finale-Spread-Distanz ≠ Etablierungs-Verzögerung. OOS-Prüfschritte S1/S2 fixiert | dieses Dokument, §8 |

---

## 7. Offene Punkte

1. **Zwischenstand §5.3/§5.4 bestätigt:** Der Rückbau R1–R3 ist umgesetzt
   (AUG **+27.06R bei 11 Phasen**, keine Monsterphase, keine 6er-
   Verlustserie, Phase-2+3-Verschmelzung erhalten); `MIN_ESTABLISH_SPREAD_PCT`
   ist mit 1.5 % verbindlich fixiert (2.0 % verworfen, §5.4.1). Der Curve-
   Fitting-Bias (E4a) ist eliminiert.
2. **Sweep `min_establish_spread_pct` (1.0–2.5 %) ist obsolet** — durch die
   arretierte 1.5 %-Fixierung (§5.4.1) ersetzt. Optional bliebe nur ein
   Sensitivitäts-Test 1.0–1.5 % (nicht geplant). Eine isolierte
   Quantifizierung der E3-Wirkung (Phase-2+3-Verschmelzung, +6.48R über 5
   Trades in Phase 2) wäre separat möglich, ist aber kein Pflichtpunkt mehr.
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
5. Temp-Helper in `test/` nach Abschluss der Explorationsphase löschen (I4):
   `tmp_makro_swings_trace.py` **bereits gelöscht** (03.09.2026); offen:
   `tmp_reissleinen_audit.py`, `tmp_huelle_e1e4.py`, `tmp_rueckbau_r1r3.py`,
   `tmp_spread_check.py`, `tmp_abort_usage.py`, `tmp_huelle_AUG_lauf.log`,
   `tmp_rueckbau_AUG_lauf.log`.
6. **Veto-Check §5.5:** 0/26 Trades im aktiven R1-Puffer → kein
   Handlungsbedarf im Rückbau-Zustand. Der Check ist auf die übrigen
   Makro-Zonen (R2–R4) übertragbar, falls ein Veto-Filter konzipiert wird.
7. **OOS-Prüfplan §8 fixiert** (nach Freigabe): OOS-Lauf S1/S2 der
   Arbeitskopie gegen §3; Reißleinen-Audit; close-basierte Verifikation der
   Ph13-Analogfälle; Grenzphasen-Bucket-Überleben; AUG-Regressionsanker
   (11 Phasen / 26 Sig / +27.06 R).

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
