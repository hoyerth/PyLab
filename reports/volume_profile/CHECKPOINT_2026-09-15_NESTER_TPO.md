# SESSION-CHECKPOINT 2026-09-15 -- VolumeProfile/Nester (Level-Schranke ARRETIERT) + TPO-Fragestellung (OFFEN)

**Dieses Dokument ist der vollstaendige Einstieg fuer die naechste Session.**
Es traegt alles, was zum Weiterarbeiten noetig ist: Anker, Begriffe, arretierter
Stand mit Belegen, Reproduktion, Anwender-Beobachtungen, Vorgaben, Vorab-Bewertung,
Randbedingungen, den vollstaendigen Fragenkatalog (1--59) und den Startpunkt.

## 0. Zielsetzung und Status (bindend)

**Ziel:** Korrekte **Analyse von Nestern in der HISTORIE.**
**Es gibt keinen Live-Modus dieser Engine und er ist NICHT Ziel.** Live-, Onset-,
Latenz-, Hysterese- und Inkrement-Ueberlegungen sind bewusst entfernt worden und
gehoeren nicht in diese Fragestellung.

| Teil | Inhalt | Status |
|---|---|---|
| A | Level-Schranke beim Nest-Linking, "1 Territorium = 1 Lauf", Chart-Fenster-Ebene aus, Randnester mit Band+POC | **ARRETIERT, committet, gepusht** (`5a69aa6`) |
| B | Aufenthalt/TPO als zweite Dimension (Market Profile), Farbe/Dicke als reiner Indikator, b)-Hypothese als Ereignisstudie | **Stufe A UMGESETZT** (Karte + Belegungskennzahlen, Kern/Chart unberuehrt) -- siehe **Teil 2 ab Abschnitt 12**; Stufe B (zweite Berg-Menge) **nicht** gebaut. **ANZEIGE BLIND** (`TPO_ANZEIGE=False`, Teil 3/Abschnitt 19): Messung bleibt, Report zeigt sie nicht mehr |
| C | **Volumen-Engine feinoptimieren** (Befunde 1/2 des Anwenders: zu lange Boxen, Kalender statt Kurs, 62,9-Berg unerkannt) | **UMGESETZT** (`nest_lauf_im_kern=True` = Lauf am Kernband) -- siehe **Teil 3 ab Abschnitt 18**, Entscheidungen und Messung in **Abschnitt 23**. Sichtpruefung der PNGs durch den Anwender offen | 
| D | **Befunde 3/4 des Anwenders** (10.09. 64,3 klebt an 11.09. 63,4; 02.09. Blase 64,2 und Tief 63,6 unerkannt) | **UMGESETZT** (`valley_rel=0.35 -> 0.60`, `nest_link_level_atr=2.0 -> 1.0`; `min_mountain_pct=4.0` und Mindestgroesse **unveraendert**) -- siehe **Abschnitt 24**. Sichtpruefung: "einiges ist besser, anderes nicht so gut" |
| E | **Befund 5 / NEUE IDEE: Objektbildung durch KURSVERLAUF statt Kalender** ("Wendezonen mit eigenem Volumen", "Volumenprofil je groesserer Bewegung", "Kurs-Follower der Volumen mitzaehlt") | **IDEE-PRUEFUNG, NICHT UMGESETZT -- kein Code, keine Prueflaeufe.** Auflage des Anwenders: erst Idee pruefen, **nicht in dieser Engine**; wenn positiv, in einer **Kopie** arbeiten. Theorie, Vokabular, 3 Hebel (H1/H2/H3), Risiken und 8 Entscheidungsfragen: **Abschnitt 25**. **Auftrag + vollstaendige Antwort des Assistenten fuer morgen:** **Abschnitt 26** |

**Arbeitsstand Git:** `HEAD` = `origin/master` = `06882d4` (Checkpoint-Doku) bzw.
`5a69aa6` (Code). **Aenderungen dieser Runde sind noch NICHT committet** (siehe
Abschnitt 15). Nichts offen ausser `data/backtest_ui_state.json` (untracked,
thematisch fremd, bewusst nicht angefasst).

> **Teil 2 dieses Dokuments (ab Abschnitt 12) ist die Fortschreibung derselben
> Session:** Antworten des Anwenders auf die drei Kernfragen, die Messungen
> dieser Runde, die Entscheidungen und der umgesetzte Stand (Stufe A).
> Die Abschnitte 0--11 darunter bleiben als Ausgangsstand stehen.

## 1. Was die Engine ist (Orientierung fuer den Neueinstieg)

### 1.1 Module

| Modul | Rolle | In dieser Runde |
|---|---|---|
| `scripts/market_segmentation.py` | `load_data` -- Bars laden (BKZ-Garantie) | unveraendert |
| `scripts/volume_profile_windows.py` | Fenster schneiden (day/week/h12/h4/h1/m30) | unveraendert |
| `scripts/volume_profile_core.py` | **Kern**: POC/VAL/VAH, Berge/Segmente, POC-Streuung, Bereiche/Luecken | **unveraendert** (eingefrorene Volumenlogik) |
| `scripts/volume_profile_nests.py` | Nester ueber Fenstergrenzen (Ketten, Laeufe, Level) | **geaendert** |
| `scripts/volume_profile_store.py` | Laufzeitspeicher (RAM, **keine** DB-Ablage) | unveraendert |
| `scripts/volume_profile_run.py` | Orchestrator: Daten -> Fenster -> Kern -> Nester -> Speicher -> Chart; Report/TSV/CLI | **geaendert** |
| `scripts/volume_profile_chart.py` | PNG-Ausgaben (Zonen-Chart + Profil-Grid) | **geaendert** |

### 1.2 Die vier Ebenen

| Ebene | Objekt | Wirkbereich |
|---|---|---|
| 1 | **Fenster** (Tagesprofil) mit **Segmenten/Bergen** | innerhalb EINES Fensters |
| 2 | Hauptband (**Zonen-VA** ab POC, `va_zone_pct`) | innerhalb EINES Fensters |
| 3 | **Bereiche/Luecken** (`zerlege_bereiche`: VA je Segment + Zwischenraeume) | innerhalb EINES Fensters |
| 4 | **Territorien/Nester** ueber Fenstergrenzen (`volume_profile_nests`) | **zwischen** Fenstern |

### 1.3 Begriffe (exakt, wie im Code)

- **BERG** -- Ergebnis der Berg-Erkennung IN EINEM Fenster. Traegt zwei Preisbaender:
  das **ZUTEILUNGSBAND** (Tal zu Tal, lueckenlose Tiling der Preisspanne) und den
  **KERN** (= Berg-Value-Area).
- **KETTE** -- Berge AUFEINANDERFOLGENDER Fenster, deren Kerne sich im Preis
  ueberlappen **UND** deren POCs hoechstens `link_level_atr` auseinanderliegen.
  Die Kette ist ausschliesslich das **Bar-Verzeichnis** des Knotens.
- **NEST** -- EIN **zusammenhaengender Lauf** von Bars (Instanz) mit eigenem
  POC/VAL/VAH, eigenem ATR, eigenem POC-Konsens.
- **TERRITORIUM** -- EIN Lauf einer Kette. **Ein Territorium traegt GENAU EINEN
  Lauf (1:1)**; `NestInstanz.rang` ist damit immer 0. Rueckkehr auf ein Level
  erzeugt ein **NEUES** Territorium, nicht den Wiederbesuch des alten.
- **Zuteilung** -- Jeder Bar wird ueber seinen **CLOSE** dem Berg zugeordnet, in
  dessen Zuteilungsband er schliesst (Bereiche tilen die Spanne) => **jeder Bar
  gehoert genau EINEM Berg**.

## 2. Was arretiert wurde (mit Belegen)

### 2.1 Aenderungen

- **Level-Schranke beim Paaren** (`link_level_atr`, Default **2,0 ATR**; Config-Feld
  `nest_link_level_atr`): Kerne muessen sich ueberlappen **UND** die POCs hoechstens
  2,0 ATR auseinanderliegen. Ohne die Schranke entstanden Sammelobjekte
  (eine Kette mit POC-Spanne **6,9 ATR**).
- **Ein Territorium = ein Lauf** (K5): liefert eine Kette mehrere zusammenhaengende
  Laeufe, war der Preis zwischenzeitlich weg => getrennte Knoten. `n_mehrfach` ist
  strukturell 0 und bleibt als **Kontrollwert** stehen (ungleich 0 = Fehler).
- **Territoriums-`id` = Position in der ZEIT** (Neunummerierung nach `bar_start`);
  deckt sich mit der Report-Reihenfolge.
- **Kette teilen statt Lauf trennen:** Beim Loch im Bar-Index entsteht ein NEUES
  Territorium; damit sind Territorium und Nest 1:1 (Report/TSV/Speicher).
- **Chart:** `fenster_ebene_zeichnen = False` ist Default. Grund: die Fenster-Ebene
  (Tages-Hauptband, Tages-POC-Linie, POCs weiterer Tagessegmente, Bereiche/Luecken
  der Tagessegmente) spannt ueber das **ganze** Fenster (1 Tag) und ueberdeckte die
  errechneten Segmente, die nur ueber ihre eigene Lebensdauer laufen. Gezeichnet
  werden nur noch die **Nester**. `True` bleibt als Gegenprobe-Schalter erhalten.
- **Angeschnittene Nester** bekommen jetzt ebenfalls ihr Band `VAL..VAH` von
  `bar_start` bis `bar_ende` plus eigene POC-Linie -- violett gestrichelt
  (`#8e24aa`), da sie am geladenen Rand weiterlaufen koennen. Vorher: nur eine
  Kante, das Segment fehlte im Bild ganz.
- **Verdrahtung des neuen Parameters** (vollstaendig): Klassenebene der Config +
  Docstring, `_nest_parameter`, `_parse_cli` (float), `_validiere` (fail-loud < 0),
  `_store_parameter` (geht in die **`run_id`**), `_NEST_ABWEICHUNGS_FELDER`
  (Kuerzel **`nlev`** in Dateiname/Titel), Reportkopf, TSV-Kopf, Nest-Abschnitt,
  Konsolenzeile, Aufruf-Beispiel im Modul-Docstring.

### 2.2 Kenngroessen des Default-Laufs (September 2026)

| Groesse | Wert |
|---|---|
| `run_id` | `29bc67922d2209fb` |
| Fenster | 11 Profile aus 11 ausgewerteten, 0 verworfen |
| Mindest-Belegung / Verwurf | 48 Bars / **AUS** (unvollstaendige Fenster bleiben) |
| POC unsicher (Fenster) | 4 von 11 |
| Bezugs-ATR (Median der Fenster) | 0.23224 |
| Rasterschritt (`nest_schritt_atr` = 0,25) | 0.05806 |
| Link-Toleranz (`nest_link_toleranz_atr` = 0) | 0.00000 |
| **Level-Toleranz (`nest_link_level_atr` = 2,0)** | **0.46448** |
| Territorien | **12** (= Zahl der Nester, 1:1) |
| Laeufe roh | 12 |
| Nester gueltig / am Rand / zu klein | **10 / 2 / 0** |
| ueber eine Fenstergrenze verschmolzen | 3 |
| Territorien mit mehr als einem Nest | 0 (strukturell) |
| Dauer | median 15.8 h |
| Nestbreite (eigene VA) | median **2.99** ATR |
| Bereiche / Luecken / Segmente | 16 / 5 / 16 |
| Bereichsbreiten je Fenster | median 4.48 ATR |
| Volumen ausserhalb der Bereiche | median 0.281 |

**Nester des Default-Laufs** (id = terr, `nB` = Bars, `nF` = Fenster):

| id/terr | bars | BKZ | nB | nF | POC | VAL | VAH | B/ATR | Vol | Streu | eint |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0..40 | 09-01 00:00..10:00 | 41 | 1 | 66.486 | 66.105 | 66.749 | 2.68 | 227378 | 0.38 | ja **Rand** |
| 1 | 41..91 | 09-01 10:15..22:45 | 51 | 1 | 64.792 | 64.530 | 65.114 | 2.10 | 98118 | 0.39 | ja |
| 2 | 92..151 | 09-02 00:00..14:45 | 60 | 1 | 64.022 | 63.642 | 64.169 | 2.49 | 100309 | 1.90 | NEIN |
| 3 | 152..183 | 09-02 15:00..22:45 | 32 | 1 | 65.010 | 64.867 | 65.324 | 2.48 | 48931 | 0.73 | ja |
| 4 | 184..251 | 09-03 00:00..16:45 | 68 | 1 | 65.743 | 65.538 | 66.242 | 3.09 | 119375 | 1.03 | NEIN |
| 5 | 252..333 | 09-03 17:00..09-04 14:15 | 82 | 2 | 66.950 | 66.624 | 67.098 | 2.88 | 108521 | 0.74 | ja |
| 6 | 334..367 | 09-04 14:30..22:45 | 34 | 1 | 66.151 | 65.771 | 66.297 | 1.72 | 67916 | 0.94 | ja |
| 7 | 368..449 | 09-07 00:00..20:15 | 82 | 1 | 65.696 | 65.549 | 66.193 | 3.54 | 106443 | 1.48 | NEIN |
| 8 | 450..633 | 09-08 00:00..09-09 22:45 | 184 | 2 | 66.265 | 65.719 | 66.811 | 4.47 | 328928 | 0.71 | ja |
| 9 | 634..690 | 09-10 00:00..14:00 | 57 | 1 | 67.324 | 67.064 | 67.815 | 3.82 | 87768 | 0.88 | ja |
| 10 | 691..909 | 09-10 14:15..09-14 22:45 | 219 | 3 | 63.917 | 63.247 | 64.528 | 5.15 | 414027 | 0.66 | ja |
| 11 | 910..940 | 09-15 00:00..07:30 | 31 | 1 | 63.411 | 63.087 | 63.500 | 2.87 | 43796 | 1.23 | NEIN **Rand** |

*`eint` = POC eindeutig gegenueber dem Rasterschritt (Toleranz 1,0 ATR).*

### 2.3 Wirkung der Schranke

**Vorher/Nachher (Codewechsel, zwei Aenderungen zusammen -- Level-Schranke UND
1:1-Regel):**

| | vorher | nachher |
|---|---|---|
| Territorien / Laeufe roh / Nester | 6 / 8 / 6 | **12 / 12 / 10** |
| Territorien mit > 1 Nest | 2 | **0** |
| weiteste Kette (POC-Spanne) | **6,9 ATR** (65.772 -> 67.374) | **1,56 ATR** |
| Nest `334..690` (357 Bars, 5 Fenster, POC 66.195) | **ein** Sammelobjekt | **vier** Nester: 34 / 82 / 184 / 57 Bars (09-04, 09-07, 09-08+09-09, 09-10 frueh) |

**Reine A/B-Gegenprobe der Level-Schranke** (identischer Code, nur der Parameter
verschieden; Datei `..._nlev0.*`, `run_id` `4b409b2516b5b887`):

| | `nlev = 0` (nur identische POCs) | `nlev = 2,0` (Default) |
|---|---|---|
| Territorien | **16** | 12 |
| Laeufe gueltig | 14 | 10 |
| verschmolzen ueber Fenstergrenze | **0** | 3 |

Lesart: `inf` (alt) -> Sammelobjekte; `2,0` -> 3 Fenstergrenzen-Paarungen;
`0` -> praktisch keine Paarung mehr (POCs sind nie exakt gleich). Die
Fenstergrenzen-Verbindung haengt also an genau dieser Schranke.

**Sichtprobe `_zonen.png` (Pixelkontrolle der Garantiefarben):**
Nest-POC **31.723 px**, Nest am Rand **1.806 px**; Zonen-Klammer, POC eindeutig,
POC unsicher, POC weiterer Segmente je **0 px** (Fenster-Ebene aus, wie beabsichtigt).
Im `_profile.png` (Profil-Grid) bleiben die Fenster-Ebenen-Farben erwartungsgemaess
belegt.

## 3. Reproduktion (ohne UI, ohne Regressionstests)

```powershell
# Default-Lauf September 2026 (schreibt TXT/TSV/2x PNG)
.venv\Scripts\python.exe -m scripts.volume_profile_run

# Gegenprobe Level-Schranke aus (eigener Dateiname ..._nlev0.*)
.venv\Scripts\python.exe -m scripts.volume_profile_run --nest_link_level_atr=0 --out_dir=test/VolumeZone/_ab

# Ketten-Diagnose (zeigt je Kettenglied Kern-Ueberlappung UND POC-Abstand in ATR)
.venv\Scripts\python.exe test\vp_nest_diag.py

# Bar-Zuordnung des Fensters 2026-09-01 (im Kern? / Zuteilungsband)
.venv\Scripts\python.exe test\vp_bar_diag.py

# Pixelkontrolle der erzeugten PNGs (Garantiefarben)
.venv\Scripts\python.exe test\vp_sichtprobe.py

# Syntax
.venv\Scripts\python.exe -m py_compile scripts\volume_profile_nests.py scripts\volume_profile_run.py scripts\volume_profile_chart.py
```

**Ausgabeort:** `test/VolumeZone/reports/`
Stamm: `volume_profile_SILVER_M15_day_zone_2026-09-01_2026-10-01`
Endungen: `.txt` (Report), `_levels.tsv` (Fenster + Segmente), `_nester.tsv`
(Territorien + Nester, ein Schema/zwei Rollen), `_zonen.png`, `_profile.png`.

**Parameterzusatz bei Abweichung:** `va`/`vaz`/`bins`/`sm`/`val`/`mm`/`vq`/`vmin`
(Profil) und `nstep`/`nlink`/`nlev`/`nmin`/`nanteil`/`npad` (Nester).

**Nuetzliche Schalter:** `--nest_pad_tage=0` (kein Polster), `--va_pct=0.93`
(Baseline-Norm), `--min_bars=40 --unvollstaendige_verwerfen=1`, `--window=week|h4|h12|h1|m30`.

### Test-/Diagnosedateien des Themas

**Alle** unter `test/` sind per Projektregel **untracked** (`test/*` ist in
`.gitignore`); das ist so gewollt.

| Datei | Zweck | Stand |
|---|---|---|
| `test/vp_nest_diag.py` | Kettenliste + POC-Abstand je Glied, Kontrolle gegen `finde_nester` | geaendert (Level-Toleranz mitgespielt) |
| `test/vp_bar_diag.py` | Bar-fuer-Bar-Zuordnung eines Fensters (im Kern?) | vorhanden |
| `test/vp_sichtprobe.py` | Pixelkontrolle der PNG-Garantiefarben | vorhanden |
| `test/vp_nester_ab.py` | A/B-Vergleich zweier `*_nester.tsv` (z. B. Polster vs. ohne) | vorhanden |
| `test/test.py` | Standard-Logik-/DB-Tests der Hausordnung | vorhanden |
| `test/VolumeZone/diag_*.py`, `_probe_*.py` | aeltere Sonden (Sensitivitaet, Achse, Segmente, Store) | Ruhestand |

**Zwei Stolpersteine fuer den Neueinstieg:**
- Versionierte Checkpoints liegen **nicht** unter `test/`, sondern unter
  `reports/<thema>/` (dieser hier: `reports/volume_profile/`). Unter `test/`
  ignoriert `.gitignore` alles (`test/*`, `test/**/*.png`).
- `test/SESSION_HANDOFF.md` ist **eingefrorenes Archiv** eines anderen
  Subsystems (Reclaim/Setup B) und **keine** Quelle fuer dieses Thema.

## 4. Anwender-Beobachtungen a--e (REFERENZWAHRHEIT, noch unbewiesen)

| # | Tag | Beobachtung (Anwender) | Vermutete Ursache im Modell |
|---|---|---|---|
| a | 2026-09-08 | "sieht fuer mich nach zwei Level aus" | Ein Fenster liefert EINEN breiten Berg; Kalibrierung (Aufloesung/Tal/Smoothing) |
| b | 2026-09-07 | Ende des Tages kleiner Seitwaerts-Level mit **klar eigener Balance** | kleiner Berg -> Anteil relativ zum Tagesgipfel winzig -> `min_mountain_pct` verwirft ihn. Volumen sagt "unwichtig", **ZEIT** sagt "lange dort" |
| c | 2026-09-10 | **Ende des Tages ein eigenes Nest** | gleiche Mechanik wie b), ggf. zusaetzlich Fenstergrenze |
| d | 2026-09-11 | "hat sogar drei oder gar vier Nester" | ein Berg mit weitem Kern (63,15..64,42) -- mehrere Aufenthaltsniveaus OHNE Volumen-Taeler |
| e | 2026-09-14 | drei Nester | dito; 14.09. steckt heute in einem 219-Bar-Nest (10.09. nachmittags bis 14.09.) |

**Datenstand-Vorbehalt:** Die heutigen Nester liegen fuer diese fuenf Tage
teilweise anders (siehe Tabelle 2.2: 07.09. = **ein** Nest id 7 mit 82 Bars;
10.09. = Nest id 9 bis 14:00 + Nest id 10 ab 14:15; 11.09./14.09. liegen
zusammen in Nest id 10). Die Beobachtungen sind also weder bestaetigt noch
widerlegt -- sie sind **Referenzwahrheit** und werden gegen die Daten geprueft,
sobald das freigegeben ist.

## 5. Anwender-Vorgaben fuer die naechste Runde (bindend)

- **Farbe/Dicke des POC ist ein REIN VISUELLER Indikator.** Die Daten selbst
  muessen **objektiv** als Grundlage vorhanden sein, damit Statistik darauf
  moeglich ist.
- **Hypothese b) als Ereignisstudie:** Nach einem schnellen Move bildet sich ein
  kleines TPO-Nest mit relativ wenig Volumen -- wie hoch ist die
  Wahrscheinlichkeit, dass es weiter in die **initiale Richtung** geht?
- **TPO-Zaehlung wird fuer noetig gehalten**, um kleine Akkumulationen oder
  Pullbacks von "echten" Volumen-Nestern zu unterscheiden.
- **Offene Frage d):** ob dafuer eine Zaehlung der Bars + Range-Filter + eigener
  Volumenzaehler ausreicht, ist zu untersuchen.
- **Komplexitaets-Sorge:** eine echte, **parallele** TPO-Logik macht die Engine
  "superkomplex".
- **Analyse in der HISTORIE**, kein Live-Modus (siehe Abschnitt 0).

## 6. Theoretische Vorab-Bewertung (Grundlage der Fragen)

- **Die Nest-Schicht kann konstruktionsbedingt nicht INNERHALB eines Fensters
  trennen** ("Innerhalb EINES Fensters wird nie gepaart"). Alles, was innerhalb
  eines Tages liegt, ist fuer sie unerreichbar -- per Parameter oder sonstwie.
- **Kriterien der Berg-Erkennung:** `valley_rel` (Tal relativ zum Gipfel),
  `smooth_win` (glaettet Ein-Bin-Taeler weg), `num_bins` (Aufloesung),
  `min_mountain_pct` (**relativ** zum groessten Berg DESSELBEN Fensters).
- **Zeit existiert bisher nur als Bar-Anzahl** (Bar-Zaehlung im Nest), **nicht als
  Kriterium**: `build_volume_profile` kennt nur Volumen je Preis-Bin.
- **Trend- und Balance-Tage sind ungleich behandelt:** ein Balance-Niveau hat wenig
  Volumen pro Bin, aber viel ZEIT; ein Trend-Bar hat grosses `high-low` und wird dem
  ZIEL-Niveau zugeschrieben. Ein Parametersatz, der b)/d)/e) sichtbar macht,
  zersplittert gleichzeitig alle anderen Tage (Flimmer-Nester).
- **Die Farbe darf NICHT das Gesamtvolumen kodieren:** bei `Laenge ∝ T`,
  `Farbe ∝ V` und `V ≈ T · I` korreliert die Farbe konstruktiv mit der Laenge --
  das Bild sagt dann immer "lang ist auch viel Volumen". Sauber ist
  **Laenge = Zeit**, **Farbe/Dicke = Intensitaet `I = V / Bars`**,
  Produkt = Gesamtvolumen.
- **Drei Ausbaustufen von "TPO"** (Unterschied: was gezaehlt wird):

  | Stufe | Zaehlung | Kann | Kann nicht | Eingriff |
  |---|---|---|---|---|
  | 0 | Bars des Nests, Spanne, `V/Bars` | Intensitaet/Lange benennen | nicht innerhalb eines Berges trennen | keiner |
  | 1 | Bars je **Berg** ueber enger Spanne (Range-Filter + eigener Zaehler) | kleine Akkumulation/Pullback INNERHALB eines erkannten Berges | Level, die kein Berg sind | additiv |
  | 2 | Bar-Belegung je **Preis-Bin** auf dem bestehenden Raster | eigene Level/Taeler aus der Zeit; unabhaengige zweite Meinung zum Volumen | -- (aber: zweite Wahrheit) | zweites Profil je Fenster/Lauf |

- **Das Raster existiert schon:** `schritt_atr * atr_bezug` ist bereits die
  gemeinsame Preisaufloesung aller Nester (`raster_bins`, `raster_schritt`) --
  Stufe 2 braucht **kein neues Raster**.
- **Der Komplexitaetstreiber ist NICHT das Zaehlen, sondern die zweite
  Urteilsinstanz:** zwei Berg-Mengen brauchen eine Regel, wann ein Nest entsteht
  (ODER/UND), ohne die Invariante "jeder Bar in genau EINEM Berg" zu verletzen.
- **Die POC-Kodierung ist ein Beweismittel, kein Detektor:** ein Level, das die
  Erkennung nicht als Nest liefert, hat keinen POC und kann nicht eingefaerbt
  werden. Fuer b), d), e) zeigt die Kodierung allenfalls, dass die bestehenden
  Nester ueberwiegend Zeit-Charakter haben.
- **b) ist ohne Basisrate nicht falschbar:** "58 % Fortsetzung" ist inhaltsleer,
  wenn es ohne Vorbedingung 55 % sind. Zur Ereignisstudie gehoeren
  Ereignisdefinition, Erfolgsmass, Basisrate, Gegenfaelle (Umkehr als eigenes
  Ergebnis), Stichprobenumfang und Mehrfachtest-Absicherung.

## 7. Randbedingungen (Hausordnung, bindend)

- **Keine UI-Tests (PySide6/Qt/WebEngine), keine Regressionstests.** Verifizierung
  nur ueber Logik-/DB-Tests unter `test/`, `py_compile`, statische Analyse,
  Code-Inspektion.
- **Neue Test-Python-Dateien und Test-Datenbanken nur unter `test/`** -- niemals
  Projekt-Root, niemals `data/`.
- **Zeitbasis-Kanon (`docs/ZEITBASIS_KANON.md`):** BKZ
  (`time AT TIME ZONE 'UTC'`) ist die **einzige** Rechenbasis; `Europe/Berlin`
  und `Europe/Budapest` sind reine Anzeige-Dubletten; der Bar-**Index** ist
  Primaerschluessel (K5); Kalendergrenzen dynamisch via `searchsorted` (K6);
  kein nacktes `SELECT time` (K4); das Wort "Wanduhr" ist projektweit verboten.
- **Vektorisierung:** keine Loops in Strategie-/Rechenlogik.
- **Der Begriff "balance" ist verbraucht** (der `balance`-Modus wurde entfernt) --
  das neue Konzept braucht einen eigenen, eindeutigen Namen.
- **Die eingefrorene Volumenlogik (`build_volume_profile`, `va_for_mountain`)
  bleibt unberuehrt** -- Vergleichbarkeit zum archivierten Lauf.
- **Die verworfene Reclaim-Engine bleibt verworfen:** hier wird nichts davon
  nachgebaut und nichts daraus als Vorlage uebernommen (stehende Projektgrenze).
- **Darstellungs-Garantie** (Farben, Kerzen, Trade-Kreise, Sperr-Marker,
  Label-Regeln): `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` §54/§55.

## 8. FRAGENKATALOG (vollstaendig, 59 Fragen)

### A. Datenvertrag und Statistik-Basis

1. Ist der TSV-Export die Rechenbasis der Statistik, oder wird eine Ablage wieder
   eingefuehrt (die Profile sind derzeit bewusst Laufzeitdaten)?
2. Werden `vol`/`n_bars` in *Kern* und *ganz* getrennt gefuehrt (Pflicht fuer jede
   Intensitaetsaussage -- bei angeschnittenen Nestern ist `V/T` heute systematisch
   falsch)?
3. Welche einheitliche Basis gilt fuer Zaehler und Nenner (roh oder gefiltert bei
   `--vol_min`/`--vol_quantil`)?
4. Welche Felder gehoeren in den Datenvertrag: Intensitaet, TPO-Gipfel, TPO-Summe,
   TPO-Breite, Spanne (absolut/ATR), Dwell-Bars, Klassifikation -- fehlt etwas, ist
   etwas ueberfluessig?
5. Wird die Klassifikation "kleine Akkumulation" vs. "Volumennest" als **Regel mit
   Verweis** gespeichert (nicht als nackte Zahl)?
6. Sind die Felder versioniert, damit spaetere Laeufe vergleichbar bleiben?
7. Werden die Felder auch fuer angeschnittene und Flimmer-Laeufe gefuellt (dann
   statistisch nutzbar) oder bleiben sie aussen vor?

### B. TPO-Umfang und Zaehlweise

8. Stufe 0, 1 oder 2 -- und falls 2: ist der Aufstieg von 1 nach 2 spaeter moeglich,
   ohne den Vertrag zu brechen?
9. Wird die Belegung **pro Bin** gezaehlt (echtes TPO) oder **pro Berg** auf der
   engen Spanne (Surrogat)?
10. Preisbezug: Close-Bin (ein Bar = ein Zaehler) oder Bar-Spanne (Bar beruehrt
    Bins)? Close ist deterministisch und doppelzaehlungsfrei; Spanne ist symmetrisch
    zur Volumenverteilung, zaehlt aber mehrfach.
11. Ist die Verteilung heute ein gewichtetes Histogramm (=> TPO = Gewicht 1, kein
    zweiter Algorithmus) oder hart auf `tick_volume` verdrahtet (=> Parametrisierung
    der Gewichtung noetig)? **Zu klaeren, sobald freigegeben.**
12. Genauigkeit: bisher **exakte** Rechnung. Ist eine exakte Bin-Belegung ueber
    denselben Pfad moeglich, oder braeuchte es eine Schaetzung
    (`bar_belegung ≈ Δt / Bin-Dauer`)? Eine Schaetzung verdient einen eigenen
    Feldnamen.
13. Wird das bestehende Nest-Raster (`schritt_atr * atr_bezug`) als TPO-Raster
    verwendet (kein neues Raster, Vergleichbarkeit schon da)?
14. Auf welcher Bar-Menge wird gezaehlt: Kernbars, Polsterbars oder beide getrennt?
15. Gilt TPO je Fenster, je Lauf (Nest) oder beides -- und wie werden die beiden
    Ebenen auseinandergehalten?
16. Was passiert mit handelsfreien Zeiten (ausserhalb der BKZ-Achse)? Sie duerfen
    **nicht** als Aufenthalt zaehlen.
17. Braucht TPO ein eigenes TVA (Dwell-Value-Area) analog `va_for_mountain` inkl.
    eigenem Anteilsparameter?
18. Wird TPO aus den **rohen** Bars gezaehlt (Aufenthalt ist physische Zeit) oder aus
    den gefilterten?

### C. Klassifikation und b)-Hypothese

19. Wird die b)-Hypothese als Stats-Studie gefuehrt (mit Basisrate) oder nur als
    Kennzahl/Diagnose?
20. Ereignisdefinition "schneller Move": Kriterium in Bars, Spanne in ATR und
    ATR/Bar, plus Richtung -- welche Schwellen, und werden sie **vorab** festgelegt?
21. "Kleines TPO-Nest" (die Bedingung): ueber Stufe-1- oder Stufe-2-Mass, und mit
    welcher Schwelle (TPO-Gipfel, Spanne in ATR, Intensitaet)?
22. Erfolgsmass der Fortsetzung: neues Extrem >= x ATR in n Bars, oder Close am
    Horizont? Beides ist zulaessig, aber nicht beides gleichzeitig.
23. Horizont: in Bars (K5) -- wie lang, und gibt es mehrere Horizonte (kurz/mittel)
    als getrennte Studien?
24. Wird die **Umkehr** als eigenes Ergebnis ausgewiesen (Erschoepfung) oder nur als
    "nicht fortgesetzt" verbucht?
25. Wird eine **Basisrate** gerechnet (ohne Nest-Filter, und/oder Zufallsniveau)?
26. Wie viele Ereignisse liefert der September ueberhaupt -- und was ist der
    Mindestumfang, unter dem wir "nicht entscheidbar" sagen?
27. Wird gegen Mehrfachtesten abgesichert (feste Schwellen vorab / Korrektur)?
28. Welche Kontrollgroessen werden miterhoben (Tageszeit, Abstand zum Vortagsnest,
    Move-Groesse, ATR-Regime), damit der Befund nicht von einem Stoerfaktor getragen
    wird?
29. Ist die Frage "Fortsetzung" ueberhaupt auf der Nest-Ebene zu stellen, oder
    gehoert sie auf die Bar-Ebene (Nest als Zustand, Ausgang als Bar-Ereignis)?
30. **Look-ahead-Freiheit der Studienbedingung:** Wird die Bedingung ("schneller
    Move", "kleines TPO-Nest") ausschliesslich aus Bars **bis zum Referenzpunkt**
    bestimmt -- ohne Wissen aus Fenstergrenzen, Polster, Glaettung, Median-ATR oder
    dem finalen Nestumfang? Ohne diese Trennung waehlt die Stichprobe sich selbst
    (Survivorship) und die historische Aussage ist unbrauchbar.

### D. Darstellung (Farbe/Dicke = reiner Indikator)

31. Kodiert die Farbe das Gesamtvolumen, die Intensitaet `V/Bars` oder ein TPO-Mass?
    (Farbe auf `V` macht sie zur Laengenkopie -- dann sagt das Bild nichts Neues.)
32. Falls zwei Kanaele: welche Groesse auf Farbe, welche auf Dicke?
33. Skala: linear ueber min..max, Rang/Perzentil oder Klassenstufen?
34. Skala fest je Lauf oder relativ je Bildausschnitt -- und ueber welche Menge (nur
    gueltige Nester)?
35. Wird die benutzte Skala als Text ausgewiesen (Legende oben links, Statistik
    mittig, Titel-/Dateinamen-Zusatz)?
36. Farbraum innerhalb der Nest-Familie mit `#00695c` als einem Endpunkt, oder eigene
    Sequenz -- und wie wird `vp_sichtprobe.py` nachgefuehrt (die 11 Garantiefarben
    sind exakt, Toleranz 12)?
37. Randnester (violett `#8e24aa`, gestrichelt): Kodierung dort ueber Muster/Dicke,
    oder bleiben sie ausgenommen?
38. Wird zusaetzlich das **TPO-Nest** gezeichnet (eigene Objektmenge) oder nur der
    POC des Volumennests eingefaerbt? Ohne eigene Menge ist der 07.09.-Fall (kein
    Volumenberg) im Bild nicht sichtbar.
39. Falls beide Mengen gezeichnet werden: wie werden sie unterscheidbar gehalten
    (Flaeche = Volumennest, Klammer/Punktlinie = TPO-Nest), ohne mit bestehenden
    Konventionen zu kollidieren?
40. Bleibt die Fenster-Ebene (`fenster_ebene_zeichnen`) aus, auch mit Kodierung?

### E. Struktur: innerhalb eines Fensters

41. Sind mehrere Nester **innerhalb eines Tages** (11.09./14.09.) Zielgroesse -- oder
    gilt weiter "ein Tag = ein Fensterprofil, innen wird nicht geteilt"?
42. Falls Split: wirkt die Zeit-Ebene **im** eingefrorenen Kern (`find_mountains`)
    oder als **zweite, getrennte Berg-Menge**, die erst die Nest-Schicht verbindet?
    (Empfehlung: zweite Menge -- Kern unberuehrt.)
43. Ist der 08.09.-Fall ("zwei Level") eine reine Kalibrierungsfrage
    (Aufloesung/Tal/Absolutschwelle) oder ebenfalls ein Zeit-Fall?
44. Alternative fuer innerhalb des Tages: feinere Fensterart (h1/h4) -- ehrlicher
    oder nur Problemverschiebung?
45. Wird `min_mountain_pct` (relativ zum Tagesgipfel) durch eine **absolute** Huerde
    (Bars oder Dwell-Anteil) ergaenzt oder ersetzt -- das ist der eigentliche Hebel
    fuer 07.09./10.09.?
46. Bleibt die Zuteilung der Bars bei Close -> Zuteilungsband (Invariante "jeder Bar
    in genau EINEM Berg")? TPO darf die Zuteilung **nicht** uebernehmen.

### F. Benennung, Invarianten, Kanon

47. "balance" ist verbraucht, "Wanduhr" verboten -- welcher Begriff gilt fuer
    Aufenthalt/TPO (Diskussionsvorschlag: "Belegung" oder "Aufenthalt", mit je einem
    eindeutigen Feldpraefix)?
48. Gehen die neuen Parameter (TPO-Schwellen, Dwell-Tal, absolute Mindestgroesse) in
    `_store_parameter`/`run_id` und in den Dateinamen-Zusatz (wie
    `nstep`/`nlink`/`nlev`)?
49. Zeitbasis: Aufenthalt ausschliesslich ueber Bar-Index/BKZ, Horizonte in Bars --
    bestaetigt (keine Stunden- oder Berlin-Projektion)?
50. Bleiben `rang` (immer 0) und "Territorien mit mehr als einem Nest" (strukturell
    0) als Kontrollfelder oder raus aus Report/TSV?
51. Muss der Bericht die Klassifikationsregel **aussprechen** (Zitat der Regel im
    Report), damit eine Ausgabe ohne Dateiblick zuordenbar ist?

### G. Komplexitaet und Prozess

52. Wo ist die Komplexitaetsgrenze: Stufe 1 als gedeckelter Ausbau (Kennzahl +
    Surrogat) oder Stufe 2 mit zweiter Urteilsinstanz?
53. Falls Stufe 2: ODER- oder UND-Verknuepfung der beiden Berg-Mengen
    (Grundsatzentscheidung, keine Kalibrierung)?
54. Ist TPO als **Kennzahl-Spalte** ausgegeben genug, um die ganze Diskussion zu
    fuehren -- oder brauchst du die zweite Menge, um Entscheidungen zu treffen?
55. Soll der **Nachweis** gerechnet werden, dass ein **einziger** globaler
    Parametersatz (`valley_rel`/`smooth_win`/`num_bins`/`min_mountain_pct`) die
    fuenf Tage (a--e) nicht gleichzeitig sauber liest? Kern unangetastet, keine UI,
    keine Ablage -- erst dieser Nachweis begruendet den Zeit-Zuschnitt.
56. Ausgabeform des Nachweises: Tabelle "Tag x Parametersatz => Nest-Zahl" mit
    ausgewiesener Flimmerquote (ohne Flimmerquote ist eine hoehere Nest-Zahl
    wertlos)?
57. Sollen (a)--(e) als feste **Sichtpruefungs-Sollwerte** (Tag + erwartete
    Nest-Zahl + Charakter) festgehalten werden, damit spaetere Aenderungen daran
    messbar sind?
58. Reihenfolge: erst Kodierung/TPO-Kennzahl (billig, rein Sicht und Statistik) oder
    erst Erkennungskriterium (teuer, Eingriff)?
59. Wird der b)-Hypothese ein eigener Ort gegeben (Statistik-Block/Reportabschnitt),
    damit sie nicht als Nebenprodukt der Darstellung entsteht?

## 9. Die drei Fragen, die alles Weitere festlegen

- **Ist der Split INNERHALB eines Tages Zielgroesse?** (Frage 41) -- Nein => Zeit nur
  als Kennzahl/Darstellung; Ja => zweite Berg-Menge und damit ODER/UND-Entscheidung
  (Frage 53).
- **Ist die Statistik-Basis der TSV-Export oder eine neue Ablage?** (Frage 1) --
  davon haengt ab, ob der Datenvertrag (Fragen 2--7) ueberhaupt exportierbar ist.
- **Ist die Studienbedingung look-ahead-frei?** (Frage 30) -- Nein => die b)-Studie
  waehlt ihre eigene Stichprobe und ist als historische Aussage wertlos.

## 10. Naechste Schritte (VORSCHLAG, nicht beschlossen)

- Fragen 55/56: **Nachweis** rechnen, dass EIN globaler Parametersatz a--e nicht
  gleichzeitig sauber liest (Kern unangetastet, keine UI, keine Ablage, Tabelle
  Tag x Parametersatz mit Flimmerquote). Erst dieser Nachweis begruendet den
  Zeit-Zuschnitt -- bisher ist er nur plausibel.
- Frage 57: a--e als Sichtpruefungs-Sollwerte festschreiben.
- Fragen 1--7: Datenvertrag klaeren (Kern/Ganz, Basis roh/gefiltert, Versionierung)
  -- Voraussetzung fuer JEDE Statistik.
- Frage 30: Look-ahead-Freiheit der Studienbedingung festschreiben.
- Fragen 31--40: Kodierung (billig, rein Sicht) -- entscheidet, ob der teure Eingriff
  noetig ist.

## 11. Startpunkt fuer die naechste Session

1. **Abschnitt 0--3 lesen** (Ziel, Module, arretierter Stand, Reproduktion).
2. **Abschnitt 4--7 lesen** (Beobachtungen a--e, Vorgaben, Vorab-Bewertung, Hausordnung).
3. **Abschnitt 8--9 beantworten** (Fragenkatalog, die drei Kernfragen).
4. Erst danach rechnen. Der naheliegende erste Rechengang steht in Abschnitt 10
   (Fragen 55/56) und ist ausdruecklich **noch nicht freigegeben**.

---

# TEIL 2 -- FORTSCHREIBUNG DERSELBEN SESSION (nach Beantwortung der Kernfragen)

## 12. Antworten des Anwenders auf die drei Kernfragen (bindend)

| Frage | Antwort | Folge |
|---|---|---|
| **41** -- Split innerhalb eines Tages Zielgroesse? | **JA.** Mehrere Nester innerhalb eines Tages sind die Zielgroesse (bis **vier**, optisch sichtbar). Daten- und Analysestruktur muessen darauf vorbereitet sein. **Jedes Nest kann Volumen- ODER Aufenthaltscharakter haben.** | Stufe B ist damit grundsaetzlich erlaubt -- aber nicht auf Vorrat (Abschnitt 14) |
| **1** -- Statistik-Basis? | **TSV-Export.** Reihenfolge bindend: **erst die Engine schrauben, bis die Sichtpruefungen final sind** -- dann den Datenvertrag fuer die Statistik definieren. | Fragen **2--7 vertagt** |
| **30** -- Look-ahead-Freiheit der Studienbedingung? | Der Anwender versteht unter "schnellem Move" **einen Abstand zum vorhergehenden Nest, der ein eigenes Level erlaubt** -- das ist die **bestehende Level-Schranke** (`nest_link_level_atr`, Default 2,0 ATR POC-Abstand), anzuwenden auch auf TPO-Nester. **Rueckwirkendes Rechnen ist in Ordnung**; der Startpunkt eines Nests ist ohnehin erst nach n Bars feststellbar. | keine neue Schwelle; Frage 20 praktisch beantwortet |

**Generelle Direktive (bindend):** Prioritaet hat **immer die Vermeidung
zusaetzlicher Komplexitaet**, ausser es gibt einen **zwingenden Grund**, den wir
dann vereinbaren. Der Anwender kann die Detailfragen nicht beantworten und
**vertraut dem Rat des Assistenten**.

## 13. Messungen dieser Runde (Belege)

### 13.1 Die Sonde `test/vp_belegung_probe.py` (neu)

Drei Sichten auf **dieselbe** Maschinerie (Fenster -> Berge -> Ketten -> Laeufe ->
Level); **nur das Gewicht der Bars ist getauscht**, der Kern ist unangetastet:

| Sicht | Gewicht | Ergebnis (September 2026, SILVER M15) |
|---|---|---|
| **V** | `tick_volume`, ueber die Bar-Spanne verteilt | 12 Territorien / 10 Nester -- **Referenz** |
| **B** | 1 je Bar, ueber die Bar-Spanne verteilt | 11 / 9 -- an **allen 11 Tagen dieselbe Bergzahl wie V**; `nur Belegung = 0` |
| **C** | 1 je Bar, **nur im Close-Bin** (klassisches TPO) | sieht mehr Berge (09-11: 3, 09-10: 6, 09-15: 5), aber inkonsistent |

**Kernbefund: Sicht B ist wertlos.** Die Verschmierung ueber die Bar-Spanne
loescht genau die Struktur, die gesucht ist -- sie liefert buchstaendig dieselbe
Berg-Zahl wie das Volumen und **keinen einzigen** zusaetzlichen Fund. Damit ist
der eigene Vorschlag "dieselbe Maschinerie mit Gewicht 1 zweimal laufen lassen"
**widerlegt** (und die Vermutung aus Abschnitt 6, TPO sei "nur Gewicht 1",
empirisch erledigt: das gilt nur fuer die Bar-Spanne, nicht fuer den Close).

### 13.2 Aufloesungs-Sweep der Close-Sicht (getragen >= 8 Bars)

| `num_bins` | Berge (Summe) | getragen | Flimmerquote |
|---|---|---|---|
| 15 / 20 | 14 | 14 | 0 % (trennt nichts) |
| 25 / 30 | 17 / 18 | 16 / 17 | 6 % |
| 45 | 24 | 17 | 29 % |
| 60 | 37 | 23 | **38 %** |

Es gibt **keine** Aufloesung, die die fuenf Tage sauber liest: **grob trennt
nicht, fein flimmert.** Das ist der Nachweis im Sinne der Fragen 55/56 -- er
belegt, dass ein **einziger globaler Parametersatz** a--e nicht gleichzeitig
sauber liest.

### 13.3 Zeit-Preis-Karte -- der Grund

Die Karte (Preisband x BKZ-Stunde) zeigt: die beobachteten Nester sind
**Zeit-Platten (Stufen)**, keine Histogramm-Gipfel. Ein Histogramm --
**Volumen wie TPO** -- wirft die Zeitreihenfolge weg und kann eine Zeit-Platte
deshalb nicht von einem gewoehnlichen Gipfel unterscheiden. **Das bestaetigt
Abschnitt 6 empirisch** (dort theoretisch vorab bewertet).

Beispiel **2026-09-14** (Default-Lauf): 31 belegte Preisbaender, davon **14 in
>= 3 verschiedenen Stunden** getragen (max 5 Stunden in einem Band). Die Karte
zeigt die zeitlich gestaffelten Niveau-Gruppen deutlich (Stunden 0--8 oben um
62,5--63,9; Stunden 9--13 darunter; Stunden 15--23 oben um 63,2--64,3).

### 13.4 Referenzwahrheit des Anwenders (bestaetigt, nicht bewiesen)

- **2026-09-11: vier Nester**, eines davon mit Top bei **65**.
- **2026-09-14: fuenf Nester** -- **64 / 63,3 / 62,5 / 62,9 / 63,6** --
  **zeitlich gestaffelt, nicht preissortiert.**

Der Default-Lauf liefert fuer diese Tage heute **1** Nest (11.09. und 14.09.
liegen beide in Territorium 10, `691..909`) -- die Beobachtungen sind also
weiterhin **unbestaetigt**, aber jetzt **messbar** (Karte + Belegungsspalten).

## 14. Entscheidungen dieser Runde

1. **GO fuer Stufe A:** Zeit-Preis-Karte + Belegungskennzahlen + `sorte`
   (Herkunftsmerkmal). **Kein Eingriff in den Kern, kein Eingriff ins Chart.**
2. **Stufe B** (zweite Berg-Menge / Plattenerkennung auf der Bar-Achse) wird
   **nicht auf Vorrat** gebaut. Erst die Sichtpruefung der Karte abwarten, dann
   ein ausdrueckliches Ja.
3. **Die `charakter`-Zuordnungsregel wird NICHT erfunden.** Die Messwerte werden
   gefuehrt; die Regel wird im Report **zitiert**, sobald sie vereinbart ist
   (Fragen 5/51). Der Report sagt das ausdruecklich.
4. **Vorbild fuer die Regel** (Vorschlag, nicht beschlossen): relativ auf die
   **eigene Familie** -- Belegung relativ zum groessten Belegungsberg, analog
   `min_mountain_pct`. Grund: sonst scheitert der 07.09.-Fall (kleiner Berg)
   wieder am Tagesvolumengipfel, genau wie in Abschnitt 6 beschrieben.

## 15. Umgesetzter Stand (Stufe A) -- Code, Ausgabe, Tests

### 15.1 Neu: `scripts/volume_profile_belegung.py`

Eigene, kleine Bibliothek der zweiten Messgroesse (**kein** Eingriff in den
eingefrorenen Kern). Inhalt:

- `bin_indizes(closes, edges)` -- Close -> Bin, **gleiche Regel wie der Kern**
  (`searchsorted` rechts, eins zurueck, auf die Raender geklemmt), damit
  Belegung und Volumen auf **demselben Raster** liegen.
- `belegung_auf_kanten(bars, edges)` -- Belegung je Bin (Summe = Bar-Zahl).
- `BelegungKennzahlen` + `belegung_kennzahlen(bars, edges)`: `n_bars`, `poc`,
  `gipfel_bin`, `gipfel_bars`, `bins_belegt`, `dichte`, Property `leer`.
- `ZeitPreisKarte` + `zeit_preis_karte(bars, band_hoehe, label, bar_start,
  bar_ende, stunden=24)`: Matrix `(Preisbaender, BKZ-Stunden)`; Properties
  `n_baender`, `baender_belegt`, `stunden_je_band`, `baender_ueber_stunden`.
- Konstanten `MAX_BAENDER = 48` (Deckel gegen Report-Sprengung) und
  `KARTE_STUNDEN_MIN = 3` (**reine Ausgabe-Schwelle**, geht in **keine**
  Erkennung/Level/Statistik ein).
- Der Modul-Docstring begruendet die **Close-Zaehlung mit dem Messbeleg**
  (Abschnitt 13.1) und benennt die bekannte Grenze (ein weit laufender Bar traegt
  nur an seinem Endpunkt bei -- Volumen und Belegung sind bewusst nicht
  deckungsgleich).

### 15.2 `scripts/volume_profile_nests.py` (ergaenzt, Kernlogik unberuehrt)

- `NestInstanz` traegt neu: `sorte="volumen"`, `n_bars_vol`, `tpo_poc`,
  `tpo_gipfel_bars`, `tpo_bins`, `tpo_dichte`; neue Properties
  `intensitaet = vol / n_bars_vol` und `gueltig`/`dauer_stunden` (wie gehabt).
- `_instanz_level` liefert zusaetzlich `belegung` und `n_bars_vol`; die Belegung
  wird aus den **rohen** Bars auf den Kanten `prof.edges` gezaehlt, waehrend
  `vol` aus den **gefilterten** Bars kommt.
- **Erkennung unveraendert:** Territorien, Ketten und Level sind identisch --
  die Belegung ist eine zweite **Messung** desselben Objekts, kein Detektor.

### 15.3 `scripts/volume_profile_store.py`

- `SCHEMA_VERSION` **`"1"` -> `"2"`** (neue Felder in `NestObjektZeile`) --
  **das aendert alle `run_id`s**, ist gewollt und dokumentiert.
- `NestObjektZeile` traegt dieselben neuen Felder + Property `intensitaet`.

### 15.4 `scripts/volume_profile_run.py`

- **Neuer Reportabschnitt `ZEIT-PREIS-KARTE`** (`_karte_zeilen`,
  `_karte_zeichen`): je Fenster **mit mindestens einem Nest** eine Textkarte,
  Bandhoehe = `ergebnis.schritt` (d. h. **derselbe Rasterschritt wie die
  Nest-Level**), Spalten = BKZ-Stunde 0..23, Zeichen 1-9/A-Z, Fusszeile
  "belegte Baender / davon ueber Stunden / max Stunden eines Bandes".
- **Nest-Tabelle** um die Belegungsspalten erweitert:
  `| TPO  gB  bins  dicht  int`; **Zusammenfassung** um Belegungs-Medianwerte
  (Gipfel-Bin, belegte Bins, Dichte) und Intensitaet (min/median/max) plus den
  Satz, dass die Charakter-Regel **noch nicht vereinbart** ist.
- **`tsv_nester`**: neue Spalten `sorte`, `n_bars_vol`, `tpo_poc`,
  `tpo_gipfel_bars`, `tpo_bins`, `tpo_dichte`, `intensitaet` (Selbstpruefung der
  Spaltenzahl bleibt aktiv); Kopf-Kommentar erklaert die zwei Basen.
- `report_text(...)` nimmt die Bars entgegen (`df`) -- die Karte braucht sie;
  `main` reicht sie durch.
- Modul-Docstring um den Abschnitt "Belegung (Aufenthalt) und Zeit-Preis-Karte"
  ergaenzt.

### 15.5 Verifikation (Hausordnung: keine UI-, keine Regressionstests)

- `py_compile` ueber alle vier Skripte + `test/test.py`: **OK**.
- `test/test.py`: **110 OK / 0 FAIL** (neu darin: 25 Pruefungen zu Belegung,
  Karte, Karten-Abschnitt, Spaltenvertrag, `intensitaet`).
- Default-Lauf: **erfolgreich**, Ausgabe unter `test/VolumeZone/reports/`
  (Stamm unveraendert, Endungen `.txt`, `_levels.tsv`, `_nester.tsv`, 2x `.png`).

### 15.6 Kenngroessen des neuen Default-Laufs (Stufe A)

| Groesse | alt (Teil 1) | **neu** |
|---|---|---|
| `run_id` | `29bc67922d2209fb` | **`0e0bae87964969b4`** (wegen `SCHEMA_VERSION` 2) |
| Territorien / Nester gueltig | 12 / 10 | 12 / **10** (unveraendert -- Erkennung nicht angetastet) |
| Bezugs-ATR / Rasterschritt | 0.23224 / 0.05806 | **identisch** |
| Belegung: Gipfel-Bin | -- | median **10** Bars, max 16 |
| Belegung: belegte Bins | -- | median **18** |
| Belegung: Dichte | -- | median **3.49** Bars je belegtem Bin |
| Intensitaet (`vol / n_bars_vol`) | -- | median **1713.7**, min 1298.1, max 1997.5 |

**Wichtig:** Die **Erkennung ist bitgleich** geblieben (12/10 Nester wie in
Tabelle 2.2). Die neue Runde hat nur gemessen und ausgegeben -- sie hat die
Streitfrage (Abschnitt 13.4) **nicht** geloest, sondern **messbar** gemacht.

### 15.7 Nicht committet

Alle Aenderungen dieser Runde liegen als **Arbeitsstand** vor:
`scripts/volume_profile_belegung.py` (neu, untracked), geaendert
`scripts/volume_profile_nests.py`, `scripts/volume_profile_store.py`,
`scripts/volume_profile_run.py`, `test/test.py`, `test/vp_belegung_probe.py`
(neu, untracked -- `test/` ist per `.gitignore` generell untracked),
dieses Dokument.

## 16. Was jetzt offen ist (Entscheidungsfragen als Text)

**Zuerst die Sichtpruefung** (das ist der eigentliche Zweck dieser Runde):
Der `ZEIT-PREIS-KARTE`-Abschnitt im Report zeigt je Tag, **wann** auf **welchem**
Preis gestanden wurde. Zu pruefen ist, ob die fuenf Tage (a--e) dort als
**getrennte Stufen** erkennbar sind -- insbesondere 14.09. (fuenf Nester) und
11.09. (vier Nester).

**Danach zu entscheiden:**

1. **Fragen 5/51 -- Klassifikationsregel.** Wie wird aus den zwei Messwerten ein
   `charakter` ("Volumen-" vs. "Aufenthaltsnest")? Welches Mass, welche Schwelle,
   und **relativ wofuer** (eigene Familie -- Vorschlag Abschnitt 14.4 -- oder
   absoluter Wert)? Ohne diese Regel bleibt `charakter` unbesetzt; der Report
   fuehrt die Messwerte und sagt das ausdruecklich.
2. **Fragen 52/53 -- Stufe 1 (Kennzahl) oder Stufe 2 (zweite Berg-Menge)?**
   Erst nach der Sichtpruefung. Bei Stufe 2 ist die ODER/UND-Verknuepfung eine
   **Grundsatzentscheidung**, keine Kalibrierung.
3. **Fragen 38/39 -- eigenes TPO-Nest zeichnen?** Eine zweite Objektmenge im Chart
   braucht eigene Form/Position, damit sie nicht mit den bestehenden
   Konventionen kollidiert. Eigener Schritt, ausdrueckliche Freigabe noetig.
4. **Fragen 2/3 -- Datenvertrag.** Gesetzt ist bisher nur: `n_bars_vol` = Basis
   des Volumens, `n_bars` = **rohe** Bar-Zahl, Belegung = **rohe** Bars. Zu
   bestaetigen ist, ob das die endgueltige Trennung ist.
5. **Frage 10 -- Zaehlweise.** Durch die Messung (Abschnitt 13.1) **faktisch
   entschieden: Close-Bin**; ausdrueckliche Bestaetigung erbeten.
6. **Frage 56 -- Ausgabeform der Karte.** Sie steht jetzt **im Report** (kein
   zusaetzlicher Dateityp); bei langen Zeitraeumen waechst der Report entsprechend
   (Bandzahl je Fenster auf `MAX_BAENDER` = 48 gedeckelt).
7. **Frage 17 -- eigenes TVA (Dwell-Value-Area) analog `va_for_mountain`?**
   Bisher **nicht** gebaut (waere Stufe 2).
8. **Frage 47 -- Begriff.** Umsetzung nutzt **"Belegung"** als Begriff und `tpo_`
   als Feldpraefix; "Wanduhr" bleibt verboten. Formell noch nicht vereinbart.

## 17. Reproduktion dieser Runde

```powershell
# Sonde: Volumen vs. Belegung (drei Sichten), Aufloesungs-Sweep, Zeit-Preis-Karte
.venv\Scripts\python.exe test\vp_belegung_probe.py

# Logik-/DB-Tests (Hausordnung) - enthaelt die 25 neuen Pruefungen
.venv\Scripts\python.exe test\test.py

# Default-Lauf (schreibt den Report inkl. Zeit-Preis-Karte)
.venv\Scripts\python.exe -m scripts.volume_profile_run

# Syntax
.venv\Scripts\python.exe -m py_compile scripts\volume_profile_belegung.py scripts\volume_profile_nests.py scripts\volume_profile_store.py scripts\volume_profile_run.py
```



---

# TEIL 3 -- FORTSCHREIBUNG (Auftrag: TPO blind, dann Volumen-Engine feinoptimieren)

## 18. Arbeitsauftrag dieser Runde (bindend, vom Anwender)

1. **TPO-Funktionalitaet BLIND schalten, ohne den Code zu aendern** (Ausgabe aus,
   Code bleibt). Begruendung: erst die VOLUMEN-Engine feinoptimieren, danach
   TPO/Aufenthalt.
2. **Befund 1:** "8.-10.09. ist niemals eine lange Box und sie endet auch nicht
   in den letzten Handelsminuten -- hier ist der Kurs ganz woanders. Das
   zeitliche Zurechtschneiden, das bis dahin wunderbar funktioniert, geht auf
   einmal nicht mehr."
3. **Befund 2:** "11.-14.09. ist noch schlimmer -- die Box ist so gross, dass sie
   quasi alles beinhaltet. Am 14.09. bei 62,9 ist ein fetter Volumenberg, der
   ueberhaupt nicht erkannt wird -- das ging vorher schon mal besser."

## 19. Umgesetzt: TPO-Anzeige blind (Code bleibt, Rechnung laeuft weiter)

- **Neu in `scripts/volume_profile_run.py`: Modulkonstante `TPO_ANZEIGE = False`**
  (direkt bei `MIN_BARS_HART`, mit Begruendung im Kommentar). Sie schaltet die
  ANZEIGE ab:
  - die Belegungsspalten (`TPO gB bins dicht int`) der Nesttabelle im Report,
  - die Belegungs-Zusammenfassung (`Belegung (Aufenthalt, rohe Bars)`,
    `Intensitaet`) samt Hinweistext,
  - den Reportabschnitt `ZEIT-PREIS-KARTE`.
- **Nicht angetastet:** die Messung selbst (`tpo_*` in `NestInstanz` und
  `NestObjektZeile`), der Laufzeitspeicher und die **TSV-Spalten** (sie sind der
  spaetere DATENVERTRAG der Statistik, Frage 1 -- kein Sichtpruefungs-Text).
- **Beleg:** Default-Lauf schreibt den Report **ohne** TPO (Kontrollsuche nach
  `TPO|ZEIT-PREIS|Belegung|Intensitaet` im TXT: nur die Zeile "Mindest-Belegung",
  ein anderer Begriff). Die Erkennung ist BITGLEICH zum Stand davor:
  **12 Territorien / 10 gueltige Nester / 2 Rand**, `run_id`-Parameter unveraendert.
- **Tests:** `test/test.py` = **110 OK / 0 FAIL** (die TSV-Pruefungen greifen
  weiterhin; die Anzeige-Pruefungen der Karte rufen `_karte_zeilen` direkt --
  sie bleiben gueltig, der Abschnitt ist nur nicht mehr im Report verdrahtet).

## 20. Diagnose der beiden Befunde (Belege, Kern unberuehrt)

Sonde: `test/vp_engine_diag.py` (neu erweitert), Log `test/vp_engine_diag.log`.

### 20.1 Root Cause: nicht die Parameter -- die LAUFGRENZE

Die Nester werden ueber das **ZUTEILUNGSBAND (Tal zu Tal)** geschnitten, gezeichnet
wird aber die **BOX (`VAL..VAH`)**. Gemessen (Abschnitt `ZUTEILUNG JE BERG` der
Sonde): **22--33 % der Bars eines Berges schliessen AUSSERHALB seines eigenen
Kerns**, im Extremfall **6,42 ATR** daneben (09-10, rank 0). Der Lauf laeuft damit
ueber Bars, die der Kurs "ganz woanders" verbracht hat -- genau der Befund 1.

### 20.2 Der harte Beleg: die Laeufe TILEN die Zeitachse

| Laufgrenze (valley_rel=0,15) | Laeufe | gueltig | Flimmer | Bars in einem Lauf | endet am Tagesletzten | beginnt am Tagesersten | ueber Tageswechsel | Nester je Tag (median/max) |
|---|---|---|---|---|---|---|---|---|
| **IST** (Zuteilungsband) | 12 | 10 | 0 | **1033/1033 = 100,0 %** | **6** | 5 | 3 | **1 / 2** |
| Kette (Kern-Union) | 51 | 23 | 27 | 840/1033 = 81,3 % | 1 | 2 | 5 | 2 / 4 |
| Berg (eigener Kern) | 79 | 32 | 46 | 758/1033 = 73,4 % | 1 | 3 | 1 | 3 / 4 |

**Im IST-Stand gehoert JEDER Bar des Zeitraums zu genau einem Nest** (100 %), und
**6 von 10 gueltigen Laeufen beginnen/enden exakt am ersten/letzten Bar eines
BKZ-Tages**. Das ist die Ursache des "zeitlichen Zurechtschneidens": es schneidet
nicht die Zeit des Kurses, sondern der Kalender. "Die Box beinhaltet alles" ist
damit **strukturell**, nicht kalibrierbar.

### 20.3 Befund 1 (08.--10.09.) -- mit Zahlen

| | Lauf | BKZ von .. bis | Bars | Box (VAL..VAH) |
|---|---|---|---|---|
| IST | 542..725 | 09-08 00:00 .. 09-09 22:45 | 184 | 65,719..66,811 |
| IST | 726..782 | 09-10 00:00 .. 09-10 14:00 | 57 | 67,064..67,815 |
| **Kette** | 542..635 | 09-08 00:00 .. 09-09 00:15 | 94 | 65,748..66,514 |
| **Kette** | 637..694 | 09-09 00:45 .. **09-09 15:00** | 58 | 66,006..66,695 |
| **Kette** | 726..756 | 09-10 00:00 .. 09-10 07:30 | 31 | 67,192..67,553 |

Die Zwei-Tage-Box verschwindet: der Lauf endet, **wenn der Close die Box
verlaesst** (09-09 um 15:00, nicht um 22:45) -- das ist das Zurechtschneiden, das
bis 07.09. "wunderbar funktioniert" hat.

### 20.4 Befund 2 (11.--14.09.) -- mit Zahlen

| | Lauf | BKZ von .. bis | Bars | POC |
|---|---|---|---|---|
| IST | 783..1001 | 09-10 14:15 .. 09-14 22:45 | **219** | 63,917 |
| **Kette** | 784..876 | 09-10 14:30 .. 09-11 14:30 | 93 | 63,959 |
| **Kette** | 883..954 | 09-11 16:15 .. 09-14 11:00 | 72 | 63,912 |

Der 62,9-Berg: er **existiert** im Profil (roh 5.595, geglaettet 5.601), wird aber
von `find_mountains` bei `valley_rel=0,15` verschluckt, weil die Talschwelle
**relativ zum kleineren der beiden Nachbargipfel** rechnet (`threshold = min(li,re)
* valley_rel`). Bei **`valley_rel=0,35`** ist er ein eigener Berg -- und wird mit
der Kern-Laufgrenze ein **eigenes Nest** (09-14, Bars 959..968, POC **62,837**,
VAL 62,754, VAH 63,030, 10 Bars, Vol 18.935). Bei 0,15 erscheint er nur als
**1-Bar-Flimmer** (963/972/974).

Belegter Nebenbefund: `valley_rel` ist **nicht** allein loesungsfaehig -- bei 0,50
zersplittert die uebrige Woche (18 Flimmer-Laeufe, IST).

### 20.5 Empfehlung (Messlage, noch NICHT umgesetzt)

- **Kern-Laufgrenze "Kette" waehlen** (nicht "Berg"): "Berg" schneidet genau die
  Klammer weg, fuer die diese Schicht existiert -- Laeufe ueber einen Tageswechsel
  fallen von 5 auf 1. "Kette" haelt den Knoten ueber die Tagesgrenze zusammen
  (5) und bindet den Lauf trotzdem an die Box (81 % Abdeckung statt 100 %).
- **Frage-41-Zielgroesse wird damit ohne zweite Berg-Menge erreicht:**
  Nester je Tag median 2, **max 4** (IST: median 1, max 2). Der Split innerhalb
  eines Tages entsteht aus dem Zeitlauf des Kurses (Close verlaesst die Box und
  kehrt zurueck), NICHT aus einer zweiten Urteilsinstanz.
- **`valley_rel` 0,15 -> 0,35**: noetig fuer den 62,9-Berg (Befund 2), Kosten:
  Flimmer steigt (31 statt 27 Laeufe unter der Mindestgroesse).

## 21. Was offen ist (Entscheidungsfragen als Text)

1. **Laufgrenze:** Wird der Lauf an die BOX gebunden (Variante "Kette": Close muss
   im Kernband der Kette liegen)? Empfehlung: **ja** -- es ist EIN Eingriff in
   `finde_nester`, kein neuer Bauteil, und die Alternative (Status quo) ist
   belegbar die Ursache beider Befunde.
2. **Box-Begriff:** Ist "Box" = Vereinigung der Berg-Value-Areas der gepaarten
   Berge (gemessen), oder soll sie weiter/enger sein (z. B. mit x-ATR Toleranz)?
3. **`valley_rel`:** 0,15 belassen (62,9-Berg bleibt Flimmer) oder 0,35 (62,9 wird
   eigenes Nest, dafuer mehr Kleinteile)?
4. **Flimmerquote:** Mit der Kern-Laufgrenze steigt der Anteil der Laeufe unter der
   Mindestgroesse (`min_bars=8` / `min_anteil_pct=4 %`) auf ~53 %. Bleibt die
   Mindestgroesse, oder wird sie angehoben (weniger, groebere Nester)?
5. **Zeichnung:** Es bleibt bei der gezeichneten Box = `VAL..VAH` der Instanz
   (Darstellungs-Garantie unberuehrt); die Kern-Laufgrenze ist nur das Kriterium
   fuer Anfang und Ende des Laufs. Bestaetigung erbeten.

## 22. Reproduktion dieser Runde

```powershell
# TPO blind: Default-Lauf schreibt den Report OHNE Belegung/Karte (Rechnung bleibt)
.venv\Scripts\python.exe -m scripts.volume_profile_run

# Diagnose: Tagesprofile, Berg-Zuteilung, Tal-Sweep, Nest-Sweep,
# sowie die Gegenprobe "Lauf an der Box" (ist | kette | berg)
.venv\Scripts\python.exe test\vp_engine_diag.py

# Logik-/DB-Tests (Hausordnung)
.venv\Scripts\python.exe test\test.py

# Syntax
.venv\Scripts\python.exe -m py_compile scripts\volume_profile_run.py test\vp_engine_diag.py
```

**Status:** Teil 3 ist **gemessen und belegt, aber NICHT umgesetzt** -- die
Laufgrenze bleibt bis zur Freigabe unveraendert (Abschnitt 21).


## 23. Entscheidungen des Anwenders und ihre Umsetzung (ABGESCHLOSSEN)

| Frage (Abschnitt 21) | Antwort | Umsetzung |
|---|---|---|
| 1 -- Lauf an die Box binden? | **JA** | `NestParameter.lauf_im_kern=True` (Default) + `_bars_im_kern()`; Konfigfeld `nest_lauf_im_kern` |
| 2 -- Box-Begriff? | "weiss nicht" -> **Assistenten-Entscheid: Vereinigung der Berg-Value-Areas der gepaarten Berge; KEINE zusaetzliche ATR-Toleranz** | `_bars_im_kern` = `min(val)..max(vah)` der Kettenberge |
| 3 -- `valley_rel` | **0,35 probieren** | Default `valley_rel=0.35`; 0,15 per `--valley_rel=0.15` als Gegenseite |
| 4 -- Flimmerquote | "weiss nicht" -> **Assistenten-Entscheid: Mindestgroesse unveraendert lassen** (`min_bars=8`, `min_anteil_pct=4 %`) | Flimmer-Laeufe bleiben als Zeile mit Marke `zu klein` sichtbar |
| 5 -- Zeichnung | "weiss nicht" -> **Assistenten-Entscheid: Box bleibt `VAL..VAH` der Instanz (Darstellungs-Garantie unberuehrt)**; der Rest-Abstand wird als Kennzahl ausgewiesen | neue Report-/Konsolenzeile `Box-Abdeckung` |

**Begruendungen zu den drei Assistenten-Entscheiden:**

- **2:** Die Vereinigung der Berg-Value-Areas ist genau das, was als Berg bereits
  erkannt und gemessen ist -- eine zusaetzliche Toleranz waere ein freier
  Parameter ohne Evidenz (und ohne Messung). Die Box ist damit aus den
  vorhandenen Objekten abgeleitet, nicht neu erfunden.
- **4:** Die Mindestgroesse hat zwei Aufgaben: Flimmer aussortieren UND
  kalibrierbar halten, wie viele Laeufe es gibt. Mit der Kern-Laufgrenze sind die
  kurzen Laeufe keine Flimmerer mehr, sondern echte Kurzaufenthalte -- sie
  einfach wegzuwerfen wuerde die Sichtpruefung verfaelschen. Angehoben wird erst,
  wenn die Sichtpruefung zeigt, dass sie stoeren.
- **5:** Die Box ist die Instanz-Value-Area (`va_pct`); sie deckt ihren Lauf
  nicht zu 100 % ab, weil sie per Konstruktion nur 70 % des Volumens umfasst.
  Der Rest-Abstand wird deshalb GEMESSEN statt weggedacht
  (`Box-Abdeckung`), und die Zeichnung bleibt unveraendert.

### 23.1 Messung der umgesetzten Aenderung (Sonde, echte `finde_nester`)

| `valley_rel` | Laufgrenze | Laeufe (gueltig) | Laufbars in einem Nest | endet am Tagesletzten | Nester/N Tag median-max | Box-Abdeckung | groesster Abstand |
|---|---|---|---|---|---|---|---|
| 0,35 (neu) | **Kernband (neu)** | 61 (29) | 846/1033 = 81,9 % | **1** | **2 / 4** | 79,7 % | **1,69 ATR** |
| 0,35 (neu) | Zuteilungsband (alt) | 19 (13) | 1033/1033 = **100 %** | 4 | 1 / 2 | 76,2 % | 2,88 ATR |
| 0,15 (alt) | Kernband | 51 (23) | 840/1033 = 81,3 % | 1 | 2 / 4 | 78,1 % | 3,00 ATR |
| 0,15 (alt) | Zuteilungsband (alt) | 12 (10) | 1033/1033 = **100 %** | **6** | 1 / 2 | 74,3 % | **7,71 ATR** |

**Lauf an der Default-Konfiguration (September 2026, geladener Kern):**
26 gueltige Nester in 57 Territorien (4 ueber eine Fenstergrenze), 30 Flimmer,
2 am Rand; Box-Abdeckung **624/782 = 79,8 %**, groesster Abstand **1,63 ATR**
(vorher: Box-Abdeckung 727/941 = 77,3 %, groesster Abstand 2,88 ATR bei
gleichem `valley_rel`).

### 23.2 Beide Befunde sind adressiert (Belege aus dem Default-Lauf)

**Befund 1 (08.--10.09.) -- das Kalender-Zurechtschneiden ist weg:**

| vorher (ein Lauf) | nachher (Nester des 08./09.09.) |
|---|---|
| 542..725, 09-08 00:00 .. 09-09 22:45, 184 Bars | 30: 09-08 00:00..03:00 (13 B) | 32: 09-08 07:00..09:45 (12 B) | 33: 09-08 10:15..21:30 (46 B) |
| 726..782, 09-10 00:00 .. 14:00, 57 Bars | 35: 09-09 02:30..09:00 (27 B) | 36: 09-09 **10:00..15:00** (21 B) |

Die Box endet jetzt dort, wo der Kurs sie verlaesst (09-09 um 15:00, nicht um
22:45) -- 3 gueltige Nester am 08.09. und 3 am 09.09. statt je einem
Zwei-Tage-Sammelobjekt.

**Befund 2 (11.--14.09.) -- der 62,9-Berg ist ein Nest:**

| Id | BKZ | Bars | POC | VAL..VAH | Vol |
|---|---|---|---|---|---|
| **49** | 09-14 12:15 .. 14:30 | 10 | **62,837** | 62,754..63,030 | 18.935 |
| 50 | 09-14 15:00 .. 17:15 | 10 | 62,922 | 62,777..63,068 | 27.468 |
| 52 | 09-14 18:30 .. 21:00 | 11 | 63,638 | 63,548..63,787 | 19.607 |
| 45 | 09-11 16:15 .. 09-14 09:30 | 66 | 63,932 | 63,788..64,479 | 113.378 |

Statt EINER 219-Bar-Box (09-10 14:15 .. 09-14 22:45) stehen jetzt vier getrennte
Nester -- 09-14 traegt **vier** gueltige Nester (Zielgroesse Frage 41).

### 23.3 Was mit der neuen Laufgrenze ausdruecklich NICHT passiert ist

- **Kein Eingriff in den eingefrorenen Kern** (`build_volume_profile`,
  `smooth_vol`, `find_mountains`, `va_for_mountain`): es wurde nur die
  BAR-MENGE bestimmt, aus der ein Lauf besteht. Die Level entstehen weiterhin
  ausschliesslich im Kern aus den Bars des Laufs.
- **Kein Eingriff ins Chart**: die Box bleibt die Instanz-Value-Area.
- **Keine zweite Berg-Menge, keine Zeit-Urteilsinstanz** (Stufe B bleibt offen).
- **Kein Verwurf**: Flimmer-Laeufe bleiben als Zeile erhalten (`zu klein`).

### 23.4 Pruefungen (Hausordnung)

- `test/test.py`: **119 OK / 0 FAIL** (9 neue Pruefungen zur Laufgrenze:
  Kern-Filter, Union der VAs, Zwei-Laeufe-Beleg, Durchreichung Config ->
  `NestParameter`, CLI `--nest_lauf_im_kern=0`, Dateinamen-Suffix `_nkern0`,
  Default `valley_rel=0.35`).
- `py_compile` fuer `volume_profile_nests.py`, `volume_profile_run.py`,
  `test/vp_engine_diag.py` -- OK.
- Sichtpruefung an den PNGs ist **manuell durch den Anwender** (Hausordnung).

### 23.5 Reproduktion der neuen Seiten

```powershell
# Default (neu): Lauf am Kernband, valley_rel 0.35
.venv\Scripts\python.exe -m scripts.volume_profile_run

# Gegenseite A: alte Laufgrenze (Tal zu Tal) - eigener Dateiname ..._nkern0.*
.venv\Scripts\python.exe -m scripts.volume_profile_run --nest_lauf_im_kern=0

# Gegenseite B: alte Tal-Schwelle - eigener Dateiname ..._val0.15.*
.venv\Scripts\python.exe -m scripts.volume_profile_run --valley_rel=0.15

# Beide Gegenseiten zusammen = exakter Vorzustand
.venv\Scripts\python.exe -m scripts.volume_profile_run --valley_rel=0.15 --nest_lauf_im_kern=0

# Sonde (Tagesprofile, Tal-Sweep, Laufgrenze A/B mit Box-Abdeckung)
.venv\Scripts\python.exe test\vp_engine_diag.py
```

**Status:** Umgesetzt und getestet; Sichtpruefung der PNGs durch den Anwender
offen. Aenderungen dieser Runde sind noch **nicht** committet.

---

## 24. Teil 3 (Fortsetzung): die Befunde 3/4 -- Tal-Schwelle und Level-Schranke

### 24.1 Die neuen Befunde des Anwenders (Ausgangslage)

1. "**10.09. 64,3 und 11.09. 63,4 sind zusammengefasst**, obwohl sie weit
   auseinanderliegen (~1 $). Das darf nicht passieren -- der relative Abstand
   darf nicht durch Extrembewegungen voellig aufgeloest werden."
2. "**02.09.:** gleich nach Beginn bei ~64,2 eine Volumenblase (liegt im
   Gesamt-POC des Tages), dazwischen ein Tief auf anderem Level bei 63,6 --
   **beide werden nicht erkannt**, obwohl 63,6 sogar zweimal angetastet wird und
   einen eigenen Volumenberg hat."

### 24.2 Befund 1 -- Ursache ist NICHT der ATR, sondern die LEVEL-Schranke

- Der ATR bewegt sich im Zeitraum nur zwischen **0,144 und 0,265**
  (Median 0,23224). `nest_link_level_atr=2,0` ergibt damit eine Level-Toleranz
  von **0,464478** -- der Faktor ~2, den der Anwender vermutet, ist real.
- Die verklebende Kette (Default, Sonde `test/vp_nest_diag.py`) war:

  | Fenster | rank | Kern | POC | Ueberlappung | POC-Abstand |
  |---|---|---|---|---|---|
  | 2026-09-10 | 1 | 63.849..64.739 | **64.331** | -- | -- |
  | 2026-09-11 | 0 | 63.155..64.424 | **63.968** | **+0.5747** | **1.56 ATR** |
  | 2026-09-14 | 0 | 63.634..64.097 | 63.901 | +0.4635 | 0.29 ATR |

- Die reine **Kern-Ueberlappung** betraegt +0,57 (echte Ueberlappung, nicht
  Toleranz -- `link_toleranz_atr=0,0` ist der Code-Default und bleibt es).
  Die **Kerntoleranz ist damit unwirksam**; das Loch ist die LEVEL-Schranke:
  das ATR ist ein **Tagesmass** und wird als **Level**-Toleranz benutzt.
- Beleg (Sonde, beide Seiten der echten `_baue_ketten`):
  `1,0 ATR` -> **2 Ketten** (getrennt) / `2,0 ATR` -> **1 Kette** (verschmolzen).

### 24.3 Befund 2 -- Ursache ist die Tal-Schwelle (`valley_rel`)

- Bei 02.09. erzeugt `valley_rel=0,35` **zwei** Berge (POC 64,025 und 65,044)
  und **verschluckt den 63,6-Berg** (Prominenz 41 %); der 64,2-Bereich ist mit
  64,03 **verschmolzen** (Sattel nur 63,79 bei 5 % Prominenz).
- Ursache: die relative Talschwelle misst gegen den **kleineren** Nachbargipfel.
  Gipfel-Prominenz der Befundtage: 09-02 66,96 (44 %) / 09-09 67,30 (54 %),
  67,91 (34 %) / 09-11 62,98 (71 %) / 09-14 63,65 (32 %) / 09-03 67,02 (60 %).
- Rasterung der vorhandenen Stellschraube (`vp_engine_diag.py`,
  `berg_sweep_mm` + `parameter_sweep`):

  | valley_rel | 09-02 | 09-14 | Bewertung |
  |---|---|---|---|
  | 0,35 (alt) | 64,03 (63,6 + 64,2 verschmolzen) | --- | Befund bleibt |
  | 0,55 | 64,2 noch verschmolzen | 62,90 da | unzureichend |
  | **0,60** | **64,03 \| 63,69 \| 65,04** | **63,90 \| 62,90 \| 63,33** | **Soll-Struktur** |
  | 0,65 / 0,70 | Tagesmitte zersplittert (4 Berge) | -- | zu viel |

### 24.4 Korrektur der frueheren Empfehlung zu `min_mountain_pct`

`min_mountain_pct` wird **relativ zum groessten Berg des Fensters** geprueft --
deshalb war die Erwartung "63,6 ueber 4 % = 7292" falsch. Messung ueber
`min_mountain_pct` in {4 … 30} bei `valley_rel=0,60`:

```
Tag          mm=4   mm=15  mm=20  mm=25  mm=30
2026-09-08   66.27+66.96   (unveraendert ueber alle Schwellen)
2026-09-09   66.26+67.30+67.91   (unveraendert)
2026-09-10   67.37+64.33+63.66+66.63+65.67 |  4 ab mm=20  |  3 ab mm=25
2026-09-11   63.97+64.40+63.49+64.88   (unveraendert)
2026-09-14   63.90+62.90+63.33   (unveraendert, auch bei mm=30)
```

Der Lauf mit `mm=4` liefert **exakt dieselben** Zahlen wie `mm=15`
(111 Territorien / 35 Laeufe / 649/766 = 84,7 % / 1,02 ATR). Ab `mm=20`
verschwindet der 09-10-Berg **65,67** (13 % Prominenz) -- er traegt dort
ohnehin nur einen 6-Bar-Lauf ("zu klein", keine Box).
**`min_mountain_pct` bleibt daher bei 4,0** (die frueher notierte Empfehlung 20
ist widerlegt).

### 24.5 Entscheidungen des Anwenders (alle vier bestaetigt)

| Frage | Entscheidung | Umsetzung |
|---|---|---|
| 1 Tal-Schwelle `valley_rel` 0,35 -> 0,60 | **ja** | `VolumeProfilConfig.valley_rel = 0.60` (Default) |
| 2 Level-Toleranz `nest_link_level_atr` 2,0 -> 1,0 | **ja** | `VolumeProfilConfig.nest_link_level_atr = 1.0` + `NestParameter.link_level_atr = 1.0` |
| 3 `min_mountain_pct` bleibt 4,0 | **ja** | unveraendert |
| 4 Mindestgroesse (`nest_min_bars=8`, `nest_min_anteil_pct=4,0`) unveraendert | **ja** | unveraendert |

Gegenseiten bleiben per CLI erreichbar: `--valley_rel=0.35` (auch `0.15`) und
`--nest_link_level_atr=2.0` (auch `0`) -- Dateiname traegt die Abweichung
(`_val0.35`, `_nlev2`).

### 24.6 Beleg: die Klebe-Ketten zerfallen (echte Engine, 11 Fenster)

| Sonde | Kette 09-08/09-09/09-10 | Kette 09-10/09-11/09-14 |
|---|---|---|
| A Default (alte Werte) | 09-08 **+** 09-09 **+** 09-10 (66,63) | 09-10 64,331 **+** 09-11 63,968 (1,56 ATR) **+** 09-14 |
| B nur `vr=0.60` | 09-08 + 09-09 + 09-10 | 09-10 63,663 **+** 09-11 63,968 (1,31 ATR) **+** 09-14 -- **klebt weiter** |
| **C `vr=0.60` + `lvl=1.0`** | **09-08 + 09-09** (0,02 ATR) | **09-10 64,331 + 09-11 64,404** (0,31 ATR) sowie **09-10 63,663 + 09-11 63,492 + 09-14 63,331 + 09-15 63,117** (0,69..0,92 ATR); die 09-11er-Kern 63,968 liegt separat |

Damit ist belegt: **Befund 2 loest allein `valley_rel`**, **den Klebe-Riss loest
allein die Level-Schranke** (das ATR als Tagesmass taugte nicht).

### 24.7 Kennzahlen der echten Laeufe (gleicher Zeitraum, 11 Fenster)

| Kennzahl | ALT (Default vorher) | nur `vr=0.6` | **neu (`vr=0.6` + `lvl=1.0`)** |
|---|---|---|---|
| Territorien | 57 | 93 | **111** |
| gueltige Laeufe (Boxen) | 26 | 33 | **35** |
| Flimmer-Laeufe | 30 | 59 | **75** |
| Box-Abdeckung | 79,8 % (624/782) | 83,6 % (678/811) | **84,7 % (649/766)** |
| groesster Abstand zur Box | 1,63 ATR | 1,20 ATR | **1,02 ATR** |
| ueber Fenstergrenze | 4 | 4 | **3** |
| Dauer median / Bars je Nest | 5,1 h / 22 | 3,5 h / -- | **2,8 h / 12** |
| POC eindeutig | -- | -- | 29/35 = **82,9 %** |

Der Default-Lauf erzeugt **denselben `run_id`** wie der vorherige CLI-Lauf
`--valley_rel=0.60 --nest_link_level_atr=1.0` (`657169002705fd1b`) --
die Defaults sind bitgleich zur freigegebenen Kandidatenkonfiguration.

Sichtbare Wirkung im Report (Fenster-Ebene, `Seg` = Zahl der Berge; ALT-Werte
aus `..._nkern0.txt`, das noch mit `valley_rel=0.35` lief):

| Tag | Seg ALT | Seg neu | Bemerkung |
|---|---|---|---|
| 2026-09-02 | 2 | **3** | 64,03 / **63,69** / 65,04 -- 63,6 jetzt erkannt |
| 2026-09-09 | 2 | **3** | 66,26 / 67,30 / 67,91 |
| 2026-09-10 | 4 | **5** | 67,37 / 64,33 / 63,66 / 66,63 / 65,67 |
| 2026-09-11 | 1 | **4** | 63,97 / 64,40 / 63,49 / 64,88 |
| 2026-09-14 | 2 | **3** | 63,90 / **62,90** / 63,33 |

### 24.8 Was ausdruecklich NICHT angefasst wurde

- **Kern** (`volume_profile_core.py`: `build_volume_profile`, `smooth_vol`,
  `find_mountains`, `va_for_mountain`) -- unberuehrt.
- **Laufgrenze** (`nest_lauf_im_kern`, `_bars_im_kern`) -- unberuehrt.
- **Mindestgroessen** (`nest_min_bars=8`, `nest_min_anteil_pct=4,0`) -- unberuehrt
  (die kurzen 09-11-Laeufe mit 8..15 Bars bleiben damit gueltig; eine
  Verschaerfung wuerde sie zu Flimmer machen und die Separation zuruecknehmen).
- **TSV-Datenvertrag** (Spalten) und **Speicher** (`volume_profile_store.py`)
  -- unberuehrt; **TPO-Anzeige** bleibt blind (`TPO_ANZEIGE=False`).

### 24.9 Pruefungen (Hausordnung)

- `python -m py_compile scripts/volume_profile_run.py scripts/volume_profile_nests.py`
  -> OK; ebenso `test/test.py`, `test/vp_nest_diag.py`, `test/vp_engine_diag.py`.
- `test/test.py`: **127 OK / 0 FAIL** (vorher 119; 8 neue Pruefungen:
  Default `valley_rel=0.60`, CLI-Gegenseite, Dateinamen-Suffix `_val0.35`,
  Level-Schranke 1,0 trennt / 2,0 verschmilzt die Klebe-Kette, Defaults in
  Config **und** `NestParameter` samt Durchreichung, CLI-Gegenseite 2,0,
  Mindestgroesse unveraendert, `min_mountain_pct` unveraendert).
- **Keine** UI-, **keine** Regressionstests (Hausordnung); Sichtpruefung der PNGs
  erfolgt **manuell durch den Anwender**.

### 24.10 Reproduktion

```powershell
# Neuer Default (valley_rel 0.60, Level-Toleranz 1.0 ATR)
.venv\Scripts\python.exe -m scripts.volume_profile_run

# Gegenseite A: alte Level-Schranke (2,0 ATR)
.venv\Scripts\python.exe -m scripts.volume_profile_run --nest_link_level_atr=2.0

# Gegenseite B: alte Tal-Schwelle (0,35)
.venv\Scripts\python.exe -m scripts.volume_profile_run --valley_rel=0.35

# Ketten-Diagnose (Parameter werden an den Orchestrator durchgereicht)
.venv\Scripts\python.exe test\vp_nest_diag.py --nur_befund
.venv\Scripts\python.exe test\vp_nest_diag.py --nur_befund --valley_rel=0.35
.venv\Scripts\python.exe test\vp_nest_diag.py --nur_befund --nest_link_level_atr=2.0

# Berg-Diagnose (Tal-Sweep, min_mountain_pct-Sweep, Laufgrenze A/B)
.venv\Scripts\python.exe test\vp_engine_diag.py
```

**Status:** Umgesetzt, gemessen, getestet. Sichtpruefung der PNGs durch den
Anwender offen; Aenderungen sind noch **nicht** committet.

---

## 25. Befund 5 / NEUE IDEE: Objektbildung durch KURSVERLAUF statt Kalender

> **STATUS: NICHT UMGESETZT. Kein Code geaendert. KEINE Prueflaeufe** (ausdrueckliche
> Ansage des Anwenders: "nur theoretisch"). **Auflage:** nicht in dieser Engine
> umsetzen -- erst die Idee pruefen, danach ggf. **in einer Kopie** arbeiten.
> Dieser Abschnitt ist **Theorie + Vokabular + Entscheidungsfragen**, damit die
> Diskussion der naechsten Runde nicht bei null beginnt.

### 25.1 Wortlaut des Anwenders (Ausgangspunkt)

> "einiges ist besser, anderes nicht so gut -- wir muessen morgen die engine logik
> nochmal ueberarbeiten -- es geht nicht nur um die dicksten volumen, sondern auch
> wendezonen mit eigenem volumen, das zwar nicht so gross ist wie der grosse poc,
> aber klar preislich abgesetzt sind und ein eigenes volumen gebildet haben - wir
> benoetigen quasii ein volumenprofil fuer jede groessere bewegung - ggf. ist das
> tagesfenster gar nicht der richtige ansatz, sondern ein kurs follower, der
> volumen (und spaeter verweildauer) mitzaehlt und so die nester definiert"

### 25.2 Der Rest-Befund, der die Idee ausgeloest hat (harte Zahlen aus Abschnitt 24)

- **09-02:** der 63,6-Berg **ist** seit Abschnitt 24.5 erkannt (eigener Berg
  **63,69**). Die **Blase bei 64,2 bleibt jedoch mit 64,03 verschmolzen** -- der
  Sattel zwischen beiden liegt bei 63,79 mit nur **5 % Prominenz**; der 63,6-Berg
  hat 41 %. Der Anwender sieht dort **zwei** Objekte, die Dichte liefert **eines**.
- Damit ist der Rest-Befund **kein Kalender- und kein Parameter-Schaden**, sondern
  ein **Eigenschaftsproblem der Dichte**: die 64,2er-Zone ist in der *aggregierten*
  Verteilung eine **Schulter** (kein Modus), in der *zeitlichen* Abfolge aber eine
  **Wende**. Eine reine Volumen-/Rang-Engine kann sie per Konstruktion nicht sehen.
- **Genau das** ist der Kern der Anwender-These "es geht nicht nur um die dicksten
  Volumen" -- und der Rest-Befund ist ihr Beweis.

### 25.3 Theoretische Einordnung (Vokabular fuer die naechste Runde)

- **Marktprofil-Sprache** (das, was der Anwender beschreibt, hat Namen):
  **Node / HVN** (Volumenknoten), **LVN** (duenne Flaeche), **Excess**
  (Rejection-Tail = "Wendezone"), **Balance/Rotation** (Anhaenger mit eigener
  Value Area) gegen **Imbalance/Bewegung** (Trend, duenn). Eine "Wendezone mit
  eigenem Volumen" ist im Marktprofil ein **Node mit Excess**; der **LVN daneben**
  ist der Trenner. ==> Zu pruefen ist, ob wir diese Begriffe uebernehmen (sie sind
  projektweit noch nicht vergeben; "balance" allein ist **verbraucht**, siehe
  Abschnitt 7) -- **vor** jeder Verwendung als Kanon-Begriff gegen eine Quelle
  absichern, nicht aus dem Gedaechtnis festschreiben.
- **Der heutige Trenner ist relativ und rangbasiert.** `valley_rel` misst gegen den
  **kleineren Nachbargipfel**, `min_mountain_pct` gegen den **groessten Berg des
  Fensters**. Beide vergleichen mit einem **Maximalwert** -- der nicht-robustesten
  Kennzahl einer Verteilung. Ein kleinerer, aber eigenstaendiger Knoten verliert
  konstruktiv gegen den Tagesriesen. **Das ist die Ursache der Wendezonen-Blindheit.**
- **Der natuerliche Trenner ist strukturell, nicht metrisch:** zwei Objekte sind
  verschieden, wenn **zwischen** ihnen ein **LVN** liegt, den der Kurs als Bewegung
  durchquert hat. Kein ATR, keine Tageskonstante, kein Rang. Der ATR ist ein
  **Tagesmass** und als **Preisabstand** nur begrenzt gueltig -- genau die Klage aus
  Abschnitt 24.2.
- **Grenze der Dichte (wichtiger Denkschritt):** "Wende" ist eine
  **Pfad**-Eigenschaft (angekommen -- abgewiesen -- weggegangen), keine
  Dichte-Eigenschaft. Eine Dichte-Engine ist **strukturell blind** fuer Wendezonen,
  die keine Dichtemodi sind. ==> Der Kurs-Follower ist nicht bloss eine andere
  Segmentierung, er ist die **einzige** Moeglichkeit, den Pfad ueberhaupt zu sehen.
  **Die Intuition des Anwenders ist damit theoretisch begruendet.**
- **Zwei Merkmale des Pfades liegen bereits vor und werden nicht als Kriterium
  benutzt:**
  - **Verweildauer / TPO** -- gemessen in `scripts/volume_profile_belegung.py`
    (Belegung je Bin, `tpo_poc`, `tpo_gipfel_bars`, `tpo_dichte`), aber per
    Anwenderentscheidung **blind geschaltet** (`TPO_ANZEIGE=False`,
    Abschnitt 19): heute *Dekoration*, morgen moeglicherweise *Kriterium*.
    Ein Wendezonen-Knoten zeigt sich in der **Zeit** oft schaerfer als im Volumen
    (Volumen wird in Bewegungsphasen durch grosse Prints aufgeblaeht).
  - **Anzahl der Anlaeufe (Beruehrungen)** -- zusammenhaengende Laeufe im
    Preisfenster = Funktion `_laeufe`. Sie **wird schon berechnet**, aber mit
    **umgekehrter** Bedeutung benutzt: der **2. Lauf = NEUES Territorium**
    (Abschnitt 24, "1 Territorium = 1 Lauf"). Fuer die Wendezonen-Hypothese ist ein
    2./3. Lauf dagegen eine **Bestaetigung derselben Zone** -- der Anwender sagt
    ausdruecklich "63,6 wird sogar **zweimal** angetastet". **Dieselbe Primitive,
    zwei Lesarten -- das ist eine semantische Entscheidung, keine Programmierfrage.**
- **Warnung (Skalenfalle):** einen **Kalender**-Parameter durch einen **ATR**-Parameter
  zu ersetzen, **verlagert** das Problem nur. Jede Schwelle in ATR-Einheiten hat
  dieselbe Degeneration, die der Anwender am 10./11.09. bemaengelt hat
  ("der relative Abstand darf nicht durch Extrembewegungen voellig aufgeloest
  werden"). ==> Bevorzugt **strukturelle** Grenzen (LVN/Breakout) und **robuste**
  Referenzen (Anteil am Gesamtvolumen, Perzentil der Bin-Verteilung, Median statt
  Maximum).

### 25.4 Drei Hebel (nach Aufwand und Wirkung getrennt -- nicht vermischen)

| Hebel | Was | Wirkung auf den Rest-Befund (64,2er-Zone) | Kosten / Risiko |
|---|---|---|---|
| **H1 Kriterium statt Rang** (Dichte) | Modus-/Excess-Bestimmung mit **absoluter** Volumenschwelle und **strukturellem** Trenner (LVN) statt Rang relativ zum Fenstermaximum | sieht **jeden** Knoten mit eigener Masse -- **nicht** den Schulter-Fall | mittel; Kern unangetastet, aber neuer Segmenter |
| **H2 Pfad-Kriterium** | **Verweildauer** und **Anzahl der Anlaeufe** werden **Auswahl**-Kriterien (statt Anzeige) | **genau** der Schulter-Fall wird sichtbar (Zeitkonzentration + Wiederkehr, statt Dichtemaximum) | klein bis mittel -- die **Messung existiert schon** |
| **H3 Kurs-Follower** (neue Engine) | Segmentierung **endogen** aus dem Kursverlauf; Objekt entsteht/endet durch **Marktereignis** (Breakout/Rejection), nicht durch Kalender | loest H1 und H2 mit -- und **entfernt die Kalendernaht samt Kellenschicht** | gross: Paradigmenwechsel (siehe 25.6) |

**Empfohlene Reihenfolge: H2 -> H1 -> H3.** Begruendung: **H3 ist die groesste
Aenderung mit dem groessten Risiko**, und der konkrete Rest-Befund ist ein
**H2-Fall** (Wiederkehr + Verweildauer), **kein** Segmentierungsfall. Ausserdem
gilt die Direktive aus Abschnitt 12: **Komplexitaet nur mit zwingendem Grund.**

### 25.5 Der Kurs-Follower -- Praezisierung

**Zu unterscheidende Einheiten (die eigentliche Streitfrage):**

- **Leg / Bewegung** (Imbalance): gerichteter Abschnitt zwischen zwei
  Umkehrpunkten. Ein Profil "je Bewegung" sammelt das Volumen **vorwiegend am
  Start- und am Endknoten** -- es zeigt also wieder auf die Knoten zurueck. Als
  **Objektdefinition** ist die Leg deshalb **wahrscheinlich der falsche Traeger**.
- **Rotation / Balance** (Anhaenger): Folge von Legs **innerhalb** einer Preisspanne,
  begrenzt durch **Initiative-Moves** (Ausbruch = Ende der Rotation). Das Objekt mit
  "eigenem Volumen, klar preislich abgesetzt" ist die **Rotation**.
  ==> **Zielobjekt ist die Rotation, nicht die Bewegung.** Das ist im Kern genau
  das, was die **Kellenschicht heute muehsam aus Tagesfenstern zusammensetzt** --
  nur mit dem **Kalender** als Naht und dem **Fenster** als Container.

**Zwei Bauformen:**

- **a) Struktur-Segmentierung (Swing/ZigZag, offline):** einfacher und
  nachvollziehbar; aber die **Swing-Schwelle ist der neue willkuerliche Parameter**
  (und in ATR-Einheiten wieder skalenanfaellig, siehe 25.3).
- **b) Zustandsmaschine Balance/Imbalance (online, kausal):** ein Objekt "ist in
  Rotation", solange der Preis innerhalb der entstehenden Value Area rotiert; ein
  **Ausbruch beendet** es. Deterministisch, kausal, **ohne Kalender**.
  Risiko: leichte **Hysterese** (Start/Stop der Ansammlung). Fuer die **Historie**
  ist eine **einmalige** kausale Wanderung zulaessig -- sie muss aber
  **deterministisch und reproduzierbar** sein (gleicher Input -> gleicher
  `run_id`), sonst ist der Report nicht vergleichbar.
  (Die Abschnitt-0-Klausel "kein Live-Modus, keine Hysterese-Fragen" ist damit
  **nicht** verletzt -- sie verbietet Live/Forecast, nicht eine kausale
  Rueckwaerts-Wanderung.)

**Architektonische Entlastung:** `build_volume_profile` und `va_for_mountain` (der
**eingefrorene Kern**) sind **agnostisch dafuer, WIE die Bar-Menge entstanden ist**.
Ein Follower braucht deshalb **keinen neuen Kern**, sondern nur einen neuen
**Segmenter** (Erzeuger der Bar-Mengen). Der Kern kann unveraendert weiterlaufen --
**das ist der guenstigste Teil der Nachricht und der Grund, warum "Kopie" tractable ist.**

**Was dabei ehrlich verloren ginge:** die **Kellenschicht** existiert **nur**, um die
Kalendernaht zu reparieren -- sie waere **ueberfluessig** (Vereinfachung!). Aber die
**fensterbezogenen Kennzahlen** des Reports (POC-Unsicherheit, Streuung, `lobe2`,
`eindeutig`, Segmentzahl, Bereiche/Luecken, `va_zone_pct`) **verlieren ihre
Bezugsbasis**; das sind heute ca. **60 % des Reports**.
==> **Follower nicht als Ersatz bauen, sondern als zweite, unabhaengige Sicht**;
das Kalenderfenster wird **degradiert** (Rhythmus-/Label-Eigenschaft der Objekte,
z. B. "in welcher Session entstanden"), **nicht geloescht**.

**Wiederverwendung statt drittem Dialekt:** das Projekt hat bereits einen
**kausalen, barweisen Zustand mit Kantenliste** (Phasenregime/Kanten: `basis_bei(k)`,
Pivot-Maskierung +2, Kanten-Labels; Code u. a. `test/tmp_kanten_engine_replay.py`,
Regelwerk `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` §54/§55) und in
`test/tmp_kanten_engine_replay.py` offenbar auch eine **Replay-Maschinerie**.
==> **Zuerst pruefen, ob das MUSTER (nicht unbedingt der Code) uebernommen werden
kann** -- sonst entsteht fuer dieselbe Sache ein **dritter Dialekt** (Anwender- und
Projektregel: erst ergaenzen, nichts neu erfinden).

### 25.6 Risiken (vor jedem Code zu beantworten)

1. **Ueber-Segmentierung:** ein Follower mit enger Schwelle zerfaellt in
   Kleinstobjekte -- dasselbe **Flimmer**-Problem wie heute, nur ohne Kalender als
   Entschuldigung. Heute schon: **75 von 119 Rohlaeufen = 63 %** Flimmer.
2. **Pfad- und Startabhaengigkeit:** wo faengt die Ansammlung an? Es braucht einen
   **dokumentierten deterministischen Start** (z. B. erster Bar des geladenen
   Bereichs), sonst ist der Report nicht reproduzierbar -- dieselbe Fehlerklasse
   wie das verbotene maschinenabhaengige `SELECT time` (K4).
3. **Zirkularitaet:** definiere ich die Objekte aus dem Volumen und messe dann ihr
   Volumen, messe ich meine **eigene Eingabe**. Eine externe Validierung (Verhalten
   **nach** der Zone) ist eine **andere** Frage und darf nicht in die Definition
   geschmuggelt werden.
4. **Parameterzahl:** heute ca. 10 Nest-Parameter. Der Follower darf **nicht mit
   mehr** enden -- Ziel **2 bis 3** (Mindestmasse, **struktureller** Trenner,
   Verweildauer), Trenner **nicht** in ATR.
5. **Verlust des Session-Fakts:** das Tagesfenster ist auch ein **Liquiditaets-/
   Session-Fakt** (Broker-Tag, Sessiongrenzen). Als *Container* falsch, als *Label*
   wertvoll (siehe 25.5).
6. **Zeitbasis-Kanon:** ein Follower ist besonders gefaehrdet, eine Zeit-/
   Session-Artefakt-Grenze einzuschmuggeln. Es gilt unveraendert: BKZ
   (`time AT TIME ZONE 'UTC'`) ist die **einzige** Rechenbasis, **Bar-Index =
   Primaerschluessel** (K5), Kalendergrenzen per `searchsorted` (K6); "Wanduhr"
   bleibt verboten.
7. **Zwei "Aufenthalt"-Definitionen:** die bestehende Belegung zaehlt
   **1 Bar = 1 Zaehler im Close-Bin** (Abschnitt 13.1/15.1). Eine Verweildauer ueber
   die **Bar-Spanne** (TPO-Standard) ist eine **zweite, andere** Groesse und
   **muss einen eigenen Namen und ein eigenes Feldpraefix tragen** -- sonst
   verschmelzen zwei unvereinbare Masse (Frage 10/11 des Katalogs).

### 25.7 Entscheidungsfragen (Textblock -- Vorgabe: keine Auswahlmenues)

1. **Traegt das neue Objekt die Rotation (Balance) oder die Bewegung (Leg)?**
   (Empfehlung des Assistenten: **Rotation** -- siehe 25.5.)
2. **Bauform (a) Struktur-Swing oder (b) Zustandsmaschine Balance/Imbalance?**
3. **Zweite Sicht oder Ersatz** -- bleibt das Tagesfenster als *Label* am Objekt
   erhalten (Empfehlung: **ja**), oder wird es ganz entfernt?
4. **Verweildauer:** eigene zweite Groesse (TPO ueber die **Bar-Spanne**) oder
   bleibt es bei **1 Bar = 1 Zaehler** (Close-Bin)? Beides ist zulaessig, aber
   nicht gleichzeitig unter demselben Namen.
5. **Anlaeufe:** bleibt **2. Lauf = neues Nest** (heute), oder wird der 2./3. Lauf
   eine **Bestaetigung derselben Zone** (Wendezonen-These)?
6. **Reihenfolge:** soll **H2** (Verweildauer + Anlaeufe als *Kriterium*) **vor**
   dem Follower geprueft werden -- im heutigen Code, weil die Messung schon
   existiert und kein neuer Bauteil noetig ist?
7. **Kopie:** eigenes Modul (z. B. `scripts/volume_profile_follow.py`) mit
   **unangetastetem Kern**, oder Arbeitskopie des Orchestrators?
8. **Erfolgskriterium VOR dem Bau festlegen:** welche Objekte muessen getroffen
   werden (Vorschlag: 09-02 inklusive der **64,2er-** und der **63,69er**-Zone,
   09-10/09-11 getrennt, 09-14 mit **62,90**), und **wie viele Objekte sind zu
   viel**? Ohne Flimmerquote ist eine hoehere Objektzahl wertlos (Frage 56).

### 25.8 Status und Grenzen dieses Abschnitts

- **Kein Code geaendert, keine Prueflaeufe durchgefuehrt** (Ansage des Anwenders).
- Alles in 25.2 stammt aus **gemessenen** Zahlen dieses Dokuments (Abschnitt 24);
  alles in 25.3 bis 25.6 ist **Theorie und Bewertung** und **nicht** gemessen.
- Die Begriffe aus 25.3 sind **Vorschlaege** und vor einer Kanonisierung gegen
  eine Quelle zu pruefen (sie sind hier bewusst als *Vokabular zur Diskussion*
  eingetragen, nicht als Projektbegriffe).
- **Naechster Schritt laut Anwender:** morgen die Engine-Logik ueberarbeiten;
  danach ggf. eine **Kopie** -- erst nach Pruefung der Idee (Abschnitt 25.7).

---

## 26. Auftrag des Anwenders + vollstaendige Antwort des Assistenten (fuer morgen festgehalten)

> **Zweck dieses Abschnitts:** der Anwender hat ausdruecklich verlangt, seine
> **Anfrage** und die **komplette Antwort** als Checkpoint fuer die naechste
> Session zu speichern. Damit beginnt morgen nichts bei null, und die
> Argumentation ist nicht aus dem Gedaechtnis zu rekonstruieren.
> **Es wurde nichts gerechnet und nichts geaendert.**

### 26.1 Die Anfrage (Wortlaut, exakt)

> "einiges ist besser, anderes nicht so gut - wir müssen morgen die engine logik
> nochmal überarbeiten - es geht nicht nur um die dicksten volumen, sondern auch
> wendezonen mit eigenem volumen, das zwar nicht so groß ist wie der große poc,
> aber klar preislich abgesetzt sind und ein eigenes volumen gebildet haben - wir
> benötigen quasii ein volumenprofil für jede grössere bewegung - ggf. ist das
> tagesfenster gar nicht dser richtige ansatz, sondern ein kurs follower, der
> volumen (und später verweildauer) mitzählt und so die nester definiert - dies
> aber nicht in dieser engine umsetzen ==> erst idee prüfen und ggf. mit einer
> kopie daran arbeiten ==> bitte mit in den checkpoint einbauen ==> was ist deine
> meinung (nur theoretisch, keine prüfläufe)"

**Daraus abgeleitete Auflagen (bindend):**

1. **Nicht in dieser Engine umsetzen.**
2. **Erst die Idee pruefen**; wenn positiv, **in einer Kopie** arbeiten.
3. **Nur theoretisch** -- keine Prueflaeufe.
4. Im Checkpoint dokumentieren (erledigt: Abschnitt 25 **und** dieser Abschnitt).
5. Meinung des Assistenten ist gefragt.

### 26.2 Antwort des Assistenten (vollstaendig, wie gegeben)

**1) Die Diagnose ist richtig -- aber der scharfe Punkt ist nicht Kalender vs. Kurs.**
Der Rest-Befund 09-02 ist **ein Tag, ein Fenster**. Der 64,2-Bereich fehlt
trotzdem. Also: der Follower haette ihn auch nicht, denn das Problem ist das
**Auswahlkriterium**, nicht der Container. Heute wird gegen ein **Maximum**
gemessen: `valley_rel` gegen den *kleineren Nachbargipfel*, `min_mountain_pct`
gegen den *groessten Berg des Fensters*. Das Maximum ist die nicht-robusteste
Kennzahl einer Verteilung -- ein kleinerer, aber eigenstaendiger Knoten
**verliert konstruktiv** gegen den Tagesriesen. **Das** ist die
Wendezonen-Blindheit, nicht der Kalender.

**2) Der harte Satz zum 64,2-Fall: er ist volumenmaessig kein eigener Knoten.**
Der Sattel zwischen 64,2 und 64,03 liegt bei **5 % Prominenz** (63,6 hat 41 %).
Die 64,2er-Blase liegt laut der eigenen Beobachtung des Anwenders *im
Gesamt-POC des Tages* -- sie **ist** also die Schulter von 64,03. Der Anwender
sieht dort trotzdem zwei Objekte, weil der **Preisweg** anders war (hingekommen,
abgewiesen, weggegangen). Wichtige Konsequenz: **"Wende" ist eine
Pfad-Eigenschaft, Dichte ist blind dafuer.** Damit ist die Intuition nicht nur
plausibel, sondern die einzige Moeglichkeit -- aber sie verschiebt die
Objektdefinition: ein *Volumen*-Objekt und ein *Verhaltens*-Objekt sind zwei
verschiedene Dinge. Werden sie ein Objekttyp, braucht es wieder eine
ODER/UND-Regel, nur diesmal auf Objekt-Ebene -- das ist die alte Frage 53, jetzt
an der Wurzel.

**3) "Profil fuer jede groessere Bewegung" -- die Bewegung ist wahrscheinlich der
falsche Traeger.**
Eine Bewegung (Leg) ist **Imbalance**; ihr Volumen sitzt am **Start- und
Endknoten**, das Profil zeigt also wieder auf die Knoten zurueck. Das Objekt mit
"eigenem Volumen, klar preislich abgesetzt" ist die **Rotation/Balance**
(Anhaengsel zwischen zwei Initiative-Moves). Genau die setzt die Kellenschicht
heute muehsam aus Tagesfenstern zusammen -- mit dem **Kalender als Naht**.
Zielobjekt ist also die Rotation, nicht die Bewegung.

**4) Zwei Merkmale des Pfades liegen schon im Projekt und werden nicht als
Kriterium benutzt.**

- **Verweildauer:** gemessen (`scripts/volume_profile_belegung.py`), aber per
  Anwenderentscheidung blind geschaltet (`TPO_ANZEIGE=False`) -- heute
  Dekoration, morgen Kriterium. Zeit ist robuster als Volumen; Volumen wird in
  Bewegungsphasen durch grosse Prints aufgeblaeht.
- **Anzahl der Anlaeufe:** `_laeufe` wird schon berechnet, aber mit
  **umgekehrter** Bedeutung (2. Lauf = *neues* Territorium). Der Anwender sagt
  selbst "63,6 wird zweimal angetastet" -- fuer die Wendezonen-These ist der
  2. Lauf eine **Bestaetigung derselben Zone**. Gleiche Primitive, zwei Lesarten:
  das ist eine **semantische Entscheidung**, keine Programmierfrage.

**5) Der beste Trenner ist strukturell, nicht metrisch.**
Zwei Objekte sind verschieden, wenn **zwischen** ihnen ein **LVN** liegt, den
der Kurs als Bewegung durchquert hat. Kein ATR, keine Tageskonstante -- und
genau das erfuellt die Forderung "der relative Abstand darf nicht durch
Extrembewegungen aufgeloest werden" **automatisch**.

**6) Skalenfalle, die nicht wiederholt werden darf:** einen
**Kalender**-Parameter durch einen **ATR**-Parameter zu ersetzen, **verlagert**
das Problem nur. Ein Swing-Threshold in ATR-Einheiten hat exakt die Degeneration,
die am 10./11.09. beanstandet wurde.

**7) Der wichtigste Punkt zur Umsetzbarkeit:** `build_volume_profile` /
`va_for_mountain` sind **agnostisch dafuer, wie die Bar-Menge entstanden ist**.
Ein Follower braucht also **keinen neuen Kern**, nur einen neuen **Segmenter**.
Deshalb ist "Kopie" tractable. Und: die Kellenschicht wuerde **ueberfluessig**
(Vereinfachung) -- aber die fenster-bezogenen Kennzahlen (POC-Unsicherheit,
Streuung, `lobe2`, Bereiche/Luecken, `va_zone_pct`) verlieren ihre Bezugsbasis,
das sind **~60 % des Reports**. ==> Follower als **zweite Sicht**, Kalenderfenster
**degradieren** (Label "in welcher Session entstanden"), **nicht loeschen**.

### 26.3 Empfohlene Reihenfolge des Assistenten: H2 -> H1 -> H3

| | Hebel | Findet die 64,2er-Zone? | Kosten |
|---|---|---|---|
| **H2** | Verweildauer + Anlaeufe als **Kriterium** (Messung existiert schon) | **ja** (Zeitkonzentration + Wiederkehr) | klein |
| **H1** | absolutes Mindestmass + **LVN**-Trenner statt Rang | nur Masse-Faelle | mittel |
| **H3** | Kurs-Follower (neue Engine) | loest H1+H2, entfernt die Kalendernaht | gross |

Begruendung: der konkrete Rest-Befund ist ein **H2-Fall**, kein
Segmentierungsfall -- und die Projekt-Direktive "Komplexitaet nur mit zwingendem
Grund" (Abschnitt 12) spricht dagegen, mit H3 anzufangen.

### 26.4 Zwei billige Vorab-Pruefungen (vor jedem Code)

1. **Erst pruefen, ob das Muster im Projekt schon existiert.** Es gibt bereits
   einen kausalen, barweisen Zustand mit Kantenliste (Phasenregime/Kanten:
   `basis_bei(k)`, Pivot-Maskierung +2) und eine Replay-Maschinerie
   (`test/tmp_kanten_engine_replay.py`, Regelwerk
   `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` §54/§55). Wird das
   nicht geprueft, entsteht fuer dieselbe Sache ein **dritter Dialekt**.
2. **Erfolgskriterium vor dem Bau festlegen** -- inklusive *wie viele Objekte zu
   viel sind*. Heute sind **75 von 119 Rohlaeufen = 63 % Flimmer**; ohne
   Flimmerquote ist eine hoehere Objektzahl wertlos (Frage 56).

### 26.5 Pflicht-Vorbehalt des Assistenten

Eine "Wendezone" braucht eine **pruefbare** Definition (angekommen, >= T
verweilt, innerhalb <= n Bars abgewiesen, mindestens einmal zurueckgekehrt).
Ohne sie ist der Follower nur eine andere Segmentierung mit anderen Parametern --
und **nicht falsifizierbar**.

### 26.6 Die Fragen fuer morgen (Kurzfassung; ausfuehrlich in 25.7)

1. Objekt = **Rotation** oder **Bewegung**?
2. Bauform: **(a) Swing-Struktur** oder **(b) Zustandsmaschine Balance/Imbalance**?
3. **Zweite Sicht** oder Ersatz -- bleibt das Tagesfenster als *Label*?
4. Verweildauer: **eigene zweite Groesse** (Bar-Spanne/TPO) oder bleibt
   **1 Bar = 1 Zaehler**?
5. **2. Lauf = neues Nest** (heute) oder **Bestaetigung derselben Zone**?
6. **H2 zuerst** im heutigen Code pruefen (Messung existiert)?
7. **Kopie**: eigenes Modul (`scripts/volume_profile_follow.py`) mit
   unangetastetem Kern, oder Arbeitskopie des Orchestrators?
8. **Erfolgskriterium** vorab: 09-02 inkl. 64,2 **und** 63,69, 09-10/09-11
   getrennt, 09-14 mit 62,90 -- und die **Flimmer-Obergrenze**?

### 26.7 Stand (unveraendert)

- **Kein Code geaendert, kein Lauf ausgefuehrt, nichts committet.**
- Die Defaults dieser Runde (`valley_rel=0.60`, `nest_link_level_atr=1.0`,
  `min_mountain_pct=4.0`, Mindestgroesse unveraendert) bleiben **unberuehrt**;
  `test/test.py` steht bei **127 OK / 0 FAIL** (Stand vor dieser Notiz).
- Alles in 26.2/26.3 ist **Meinung und Theorie**, nicht gemessen. Gemessen sind
  nur die Zahlen, die aus Abschnitt 24 zitiert werden (Sattel 5 %, 63,6-Berg
  41 %, 75/119 Flimmer).
