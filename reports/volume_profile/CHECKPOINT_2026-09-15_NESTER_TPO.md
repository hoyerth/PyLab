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
| B | Aufenthalt/TPO als zweite Dimension (Market Profile), Farbe/Dicke als reiner Indikator, b)-Hypothese als Ereignisstudie | **OFFEN, nur theoretisch bewertet** -- es wurde **nichts gerechnet und nichts geprueft** |

**Arbeitsstand Git:** `HEAD` = `origin/master` = `5a69aa6` (Code) bzw. `8fdbc1e`
(Checkpoint-Doku). Nichts offen ausser `data/backtest_ui_state.json` (untracked,
thematisch fremd, bewusst nicht angefasst).

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
