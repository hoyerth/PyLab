# CHECKPOINT 2026-09-15 -- VolumeProfile/Nester: Level-Schranke (ARRETIERT) + TPO-Fragestellung (OFFEN)

Status: **Zwei Teile.**
1. **Arretiert und gepusht:** Level-Schranke beim Nest-Linking, "1 Territorium = 1 Lauf",
   Chart-Fenster-Ebene aus, Randnester mit Band+POC. Code-Stand = Commit `5a69aa6`
   (`origin/master`), siehe Abschnitt 1.
2. **Offen, nur theoretisch bewertet:** Aufenthalt/TPO als zweite Dimension
   (Market Profile), Farbe als reiner Indikator, b)-Hypothese als Ereignisstudie,
   Fernziel Live-Betrieb. **Es wurde nichts gerechnet und nichts geprueft** -- dieser
   Teil ist ein Fragenkatalog (Abschnitt 6), keine Umsetzung.

## 0. Anker (Stand, verifiziert)

| Datei | Rolle | Stand |
|---|---|---|
| `scripts/volume_profile_nests.py` | Nest-Erkennung (Ketten, Laeufe, Level) | geaendert, Commit `5a69aa6` |
| `scripts/volume_profile_run.py` | Orchestrator/Config/Report/TSV/CLI | geaendert, Commit `5a69aa6` |
| `scripts/volume_profile_chart.py` | PNG-Ausgaben | geaendert, Commit `5a69aa6` |
| `scripts/volume_profile_core.py` | Kern (unberuehrt, eingefrorene Volumenlogik) | unveraendert |
| `scripts/volume_profile_windows.py` | Fensterbildung | unveraendert |
| `scripts/volume_profile_store.py` | Laufzeitspeicher (RAM, keine Ablage) | unveraendert |
| `test/vp_nest_diag.py` | Ketten-Diagnose | geaendert (Level-Toleranz), **untracked** |
| `test/vp_bar_diag.py` | Bar-Zuordnungs-Diagnose | **untracked** |
| `test/vp_sichtprobe.py` | Pixelkontrolle der PNG-Garantiefarben | unveraendert, tracked |
| `test/VolumeZone/reports/volume_profile_SILVER_M15_day_zone_2026-09-01_2026-10-01.*` | Lauf-Ausgaben | neu erzeugt |

Git: `git rev-parse HEAD` = `git rev-parse origin/master` = `5a69aa6`.
Untracked und bewusst NICHT angefasst: `data/backtest_ui_state.json` (thematisch fremd).

## 1. Was arretiert wurde (mit Belegen)

### 1.1 Aenderungen

- **Level-Schranke beim Paaren:** Zwei Berge aufeinanderfolgender Fenster werden nur
  gepaart, wenn sich ihre Kerne ueberlappen **UND** ihre POCs hoechstens
  `link_level_atr` (Default 2,0 ATR; in der Config `nest_link_level_atr`) auseinanderliegen.
  Ohne die Schranke entstanden Sammelobjekte (eine Kette mit POC-Spanne 6,9 ATR).
- **Ein Territorium traegt genau EINEN Lauf:** Liefert eine Kette mehrere
  zusammenhaengende Laeufe, war der Preis zwischenzeitlich weg -- das sind getrennte
  Knoten. Rueckkehr auf ein Level erzeugt ein NEUES Territorium. `NestInstanz.rang` ist
  damit immer 0 (Feld bleibt fuer den Speicher-/TSV-Vertrag); `n_mehrfach` ist strukturell 0
  (Kontrollwert).
- **Territoriums-Id = Position in der Zeit** (Neunummerierung nach `bar_start`), deckt sich
  mit der Report-Reihenfolge (K5).
- **Chart:** `fenster_ebene_zeichnen=False` als Default -- die Fenster-Ebene (Tages-Hauptband,
  Tages-POC, Bereiche/Luecken der Tagessegmente) spann ueber das GANZE Fenster und ueberdeckte
  die errechneten Segmente. Gezeichnet werden nur noch die Nester. Angeschnittene Nester
  bekommen jetzt ebenfalls Band + POC (violett gestrichelt).
- **Verdrahtung des neuen Parameters:** Klassenebene der Config, `_nest_parameter`,
  `_parse_cli`, `_validiere` (fail-loud bei < 0), `_store_parameter` (geht in die `run_id`),
  `_NEST_ABWEICHUNGS_FELDER` (Kuerzel `nlev` in Dateiname/Titel), Reportkopf, TSV-Kopf,
  Nest-Abschnitt, Konsolenzeile.

### 1.2 Messwerte des September-Laufs (Default)

| Groesse | Wert |
|---|---|
| Bezugs-ATR (Median der Fenster) | 0.23224 |
| Rasterschritt (`nest_schritt_atr`) | 0.05806 |
| Link-Toleranz (`nest_link_toleranz_atr` = 0) | 0.00000 |
| **Level-Toleranz (`nest_link_level_atr` = 2,0)** | **0.46448** |
| `run_id` Default | `29bc67922d2209fb` |
| Profil | 11 Profile / 11 Fenster, 0 verworfen |
| Territorien | 12 (= Zahl der Nester, 1:1) |
| Nester gueltig / Rand / zu klein | 10 / 2 / 0 |
| ueber eine Fenstergrenze verschmolzen | 3 |
| Territorien mit > 1 Nest | 0 (strukturell) |
| Nestbreite (eigene VA) | median 2.99 ATR |

**Wirkung der Schranke (Vorher/Nachher):**

| | vorher | nachher |
|---|---|---|
| POC-Spanne der weitesten Kette | 06,9 ATR (65.772 -> 67.374) | 1.56 ATR |
| Nest 6 | 357 Bars, 5 Fenster, POC 66.195 (Sammelobjekt) | zerfaellt in 34 / 82 / 184 / 57 Bars (09-04, 09-07, 09-08+09-09, 09-10 frueh) |

**A/B-Gegenprobe `--nest_link_level_atr=0`** (Datei `..._nlev0.*`, eigener `run_id` `4b409b2516b5b887`):

| | nlev = 0 | nlev = 2,0 |
|---|---|---|
| Territorien | 16 | 12 |
| Laeufe gueltig | 14 | 10 |
| verschmolzen | 0 | 3 |

**Sichtprobe `_zonen.png` (Pixelkontrolle, Garantiefarben):** Nest-POC 31.723 px,
Nest am Rand 1.806 px; Zonen-Klammer / POC eindeutig / POC unsicher / weiterer POC je **0 px**
(Fenster-Ebene aus, wie beabsichtigt).

**Berechnungsnachweis ohne UI:** `py_compile` OK fuer nests/run/chart/diag; `vp_nest_diag.py`;
`python -m scripts.volume_profile_run`. Keine UI-Tests, keine Regressionstests (Projektregel).

## 2. Anwender-Beobachtungen a--e (REFERENZWAHRHEIT, unbewiesen)

Diese fuenf Beobachtungen sind der Anlass der ganzen Fragestellung. Sie sind
**Anwender-Sicht** und noch **nicht** gegen die Daten geprueft.

| # | Tag | Beobachtung | Vermutete Ursache im Modell |
|---|---|---|---|
| a | 2026-09-08 | "sieht nach zwei Level aus" | Ein Fenster liefert einen breiten Berg; calibrierbar ueber Aufloesung/Tal/Smoothing |
| b | 2026-09-07 | Ende des Tages kleiner Seitwaerts-Level mit **eigener Balance** | kleiner Berg -> Anteil relativ zum Tagesgipfel winzig -> `min_mountain_pct` verwirft ihn; Volumen sagt "unwichtig", ZEIT sagt "lange dort" |
| c | 2026-09-10 | Ende des Tages ein **eigenes** Nest | gleiche Mechanik wie b), ggf. zusaetzlich Fenstergrenze |
| d | 2026-09-11 | "sogar drei oder gar vier Nester" | ein Berg mit weitem Kern (63,15..64,42) -- mehrere Aufenthaltsniveaus OHNE Volumen-Taeler |
| e | 2026-09-14 | drei Nester | dito; 14.09. steckt heute in einem 219-Bar-Nest (10.09. nachmittags bis 14.09.) |

## 3. Anwender-Vorgaben fuer die naechste Runde (bindend)

1. **Farbe/Dicke des POC ist ein REIN VISUELLER Indikator.** Die Daten selbst muessen
   **objektiv** als Grundlage vorhanden sein, damit Statistik darauf moeglich ist.
2. **Hypothese b) als Ereignisstudie:** Nach einem schnellen Move bildet sich ein kleines
   TPO-Nest mit relativ wenig Volumen -- wie hoch ist die Wahrscheinlichkeit, dass es weiter
   in die **initiale Richtung** geht?
3. **TPO-Zaehlung wird fuer noetig gehalten**, um kleine Akkumulationen oder Pullbacks von
   "echten" Volumen-Nestern zu unterscheiden.
4. **Offene Frage d):** Ob dafuer eine Zaehlung der Bars + Range-Filter + eigener Volumenzaehler
   ausreicht, ist zu untersuchen.
5. **Komplexitaets-Sorge:** Eine echte, **parallele** TPO-Logik macht die Engine "superkomplex".
6. **Fernziel Live-System:** Relevant ist, wie **schnell und sicher der BEGINN eines Nestes**
   gefunden wird. Es gibt Aehnlichkeiten zur **verworfenen Reclaim-Engine** -- diese wird
   **NICHT nachgebaut** (kein Code, keine Logik-Uebernahme, kein Nachschlagen als Vorlage).

## 4. Theoretische Vorab-Bewertung (gilt unveraendert)

1. **Die Nest-Schicht kann konstruktionsbedingt nicht INNERHALB eines Fensters trennen**
   ("Innerhalb EINES Fensters wird nie gepaart"). Alles, was innerhalb eines Tages liegt, ist
   fuer sie unerreichbar -- per Parameter oder sonstwie.
2. **Die Kriterien der Berg-Erkennung sind:** `valley_rel` (Tal relativ zum Gipfel),
   `smooth_win` (glaettet Ein-Bin-Taeler weg), `num_bins` (Aufloesung), `min_mountain_pct`
   (**relativ** zum groessten Berg DESSELBEN Fensters).
3. **Zeit existiert im Modell bisher nur als Bar-Anzahl** (Zuteilung ueber Close), **nicht als
   Kriterium**. `build_volume_profile` kennt nur Volumen je Preis-Bin.
4. **Trend- und Balance-Tage sind nicht gleich behandelt:** Ein Balance-Niveau hat wenig
   Volumen pro Bin, aber viel ZEIT; ein Trend-Bar hat grosses `high-low` und wird dem
   ZIEL-Niveau zugeschrieben. Ein Parametersatz, der b)/d)/e) sichtbar macht, zersplittert
   gleichzeitig alle anderen Tage (Flimmer-Nester).
5. **Die Farbe darf NICHT das Gesamtvolumen kodieren:** Bei `Laenge ∝ T`, `Farbe ∝ V` und
   `V ≈ T · I` korreliert die Farbe konstruktiv mit der Laenge -- das Bild sagt dann immer
   "lang ist auch viel Volumen". Sauber ist **Farbe/Dicke = Intensitaet `I = V / Bars`**
   (Laenge = Zeit, Farbe = Intensitaet, Produkt = Gesamtvolumen).
6. **Drei Ausbaustufen von "TPO"** (Unterschied nur: was gezaehlt wird):

   | Stufe | Zaehlung | Kann | Kann nicht | Eingriff |
   |---|---|---|---|---|
   | 0 | Bars des Nests, Spanne, `V/Bars` | Intensitaet/Lange benennen | nicht innerhalb eines Berges trennen | keiner |
   | 1 | Bars je BERG ueber enger Spanne (Range-Filter + eigener Zaehler) | kleine Akkumulation/Pullback INNERHALB eines erkannten Berges | Level, die kein Berg sind | additiv |
   | 2 | Bar-Belegung je PREIS-BIN auf dem Raster | eigene Level/Taeler aus der Zeit | -- (aber: zweite Wahrheit) | zweites Profil je Fenster/Lauf |

7. **Das Raster existiert schon:** `schritt_atr * atr_bezug` ist bereits die gemeinsame
   Preisaufloesung aller Nester (`raster_bins`, `raster_schritt`) -- Stufe 2 braucht kein
   neues Raster.
8. **Der Komplexitaetstreiber ist NICHT das Zaehlen, sondern die zweite Urteilsinstanz:**
   zwei Berg-Mengen brauchen eine Regel, wann ein Nest entsteht (ODER/UND), ohne die
   Invariante "jeder Bar in genau EINEM Berg" zu verletzen.
9. **Die POC-Kodierung ist ein Beweismittel, kein Detektor:** Ein Level, das die Erkennung
   nicht als Nest liefert, hat keinen POC und kann nicht eingefaerbt werden -- fuer b), d), e)
   zeigt die Kodierung allenfalls, dass die bestehenden Nester ueberwiegend Zeit-Charakter
   haben.
10. **b) ist ohne Basisrate nicht falschbar:** "58 % Fortsetzung" ist inhaltsleer, wenn es
    ohne Vorbedingung 55 % sind. Zur Ereignisstudie gehoeren Ereignisdefinition, Erfolgsmass,
    Basisrate, Gegenfaelle (Umkehr als eigenes Ergebnis), Stichprobenumfang und
    Mehrfachtest-Absicherung.

## 5. Randbedingungen (unveraendert bindend)

- **Keine UI-Tests (PySide6/Qt/WebEngine), keine Regressionstests.** Verifizierung nur ueber
  Logik-/DB-Tests in `test/`, Syntax-Checks (`py_compile`), statische Analyse, Code-Inspektion.
- **Neue Test-Python-Dateien und Test-Datenbanken nur unter `test/`** (nie Projekt-Root, nie `data/`).
- **Zeitbasis-Kanon (`docs/ZEITBASIS_KANON.md`):** BKZ ist die einzige Rechenbasis; Bar-Index ist
  Primaerschluessel; Kalendergrenzen dynamisch via `searchsorted`; keine Zeitzonen-Projektion;
  das Wort "Wanduhr" ist projektweit verboten.
- **Vektorisierung:** keine Loops in Strategie-/Rechenlogik. **Klaerungsbedarf:** Live-Inkrement
  je Bar ist ein anderer Modus als der vektorisierte Offline-Lauf -- diese Spannung ist
  ausdruecklich zu adressieren (Frage 69).
- **Der Begriff "balance" ist verbraucht** (der `balance`-Modus wurde entfernt) -- fuer das neue
  Konzept braucht es einen eigenen, eindeutigen Namen.
- **Die eingefrorene Volumenlogik (`build_volume_profile`) bleibt unberuehrt** -- Vergleichbarkeit
  zum archivierten Lauf.
- **Reclaim-Engine:** nur Aehnlichkeitsmarke, **kein Nachbau** (Anwender-Vorgabe).

## 6. FRAGENKATALOG (vollstaendig)

### A. Datenvertrag und Statistik-Basis

1. Ist der TSV-Export die Rechenbasis der Statistik, oder wird eine Ablage wieder eingefuehrt
   (die Profile sind derzeit bewusst Laufzeitdaten)?
2. Werden `vol`/`n_bars` in *Kern* und *ganz* getrennt gefuehrt (Pflicht fuer jede
   Intensitaetsaussage -- bei angeschnittenen Nestern ist `V/T` heute systematisch falsch)?
3. Welche einheitliche Basis gilt fuer Zaehler und Nenner (roh oder gefiltert bei
   `--vol_min`/`--vol_quantil`)?
4. Welche Felder gehoeren in den Datenvertrag: Intensitaet, TPO-Gipfel, TPO-Summe, TPO-Breite,
   Spanne (absolut/ATR), Dwell-Bars, Klassifikation -- fehlt etwas, ist etwas ueberfluessig?
5. Wird die Klassifikation "kleine Akkumulation" vs. "Volumennest" als **Regel mit Verweis**
   gespeichert (nicht als nackte Zahl)?
6. Sind die Felder versioniert, damit spaetere Laeufe vergleichbar bleiben?
7. Werden die Felder auch fuer angeschnittene und Flimmer-Laeufe gefuellt (dann statistisch
   nutzbar) oder bleiben sie aussen vor?

### B. TPO-Umfang und Zaehlweise

8. Stufe 0, 1 oder 2 -- und falls 2: ist der Aufstieg von 1 nach 2 spaeter moeglich, ohne den
   Vertrag zu brechen?
9. Wird die Belegung **pro Bin** gezaehlt (echtes TPO) oder **pro Berg** auf der engen Spanne
   (Surrogat)?
10. Preisbezug: Close-Bin (ein Bar = ein Zaehler) oder Bar-Spanne (Bar beruehrt Bins)? Close ist
    deterministisch und doppelzaehlungsfrei; Spanne ist symmetrisch zur Volumenverteilung, zaehlt
    aber mehrfach.
11. Ist die Verteilung heute ein gewichtetes Histogramm (=> TPO = Gewicht 1, kein zweiter
    Algorithmus) oder hart auf `tick_volume` verdrahtet (=> Parametrisierung der Gewichtung
    noetig)? **Zu klaeren, sobald freigegeben.**
12. Genauigkeit: bisher **exakte** Rechnung. Ist eine exakte Bin-Belegung ueber denselben Pfad
    moeglich, oder braeuchte es eine Schaetzung (`bar_belegung ≈ Δt / Bin-Dauer`)? Eine
    Schaetzung verdient einen eigenen Feldnamen.
13. Wird das bestehende Nest-Raster (`schritt_atr * atr_bezug`) als TPO-Raster verwendet
    (kein neues Raster, Vergleichbarkeit schon da)?
14. Auf welcher Bar-Menge wird gezaehlt: Kernbars, Polsterbars oder beide getrennt?
15. Gilt TPO je Fenster, je Lauf (Nest) oder beides -- und wie werden die beiden Ebenen
    auseinandergehalten?
16. Was passiert mit handelsfreien Zeiten (ausserhalb der BKZ-Achse)? Sie duerfen **nicht** als
    Aufenthalt zaehlen.
17. Braucht TPO ein eigenes TVA (Dwell-Value-Area) analog `va_for_mountain` inkl. eigenem
    Anteilsparameter?
18. Wird TPO aus den **rohen** Bars gezaehlt (Aufenthalt ist physische Zeit) oder aus den
    gefilterten?

### C. Klassifikation und b)-Hypothese

19. Wird die b)-Hypothese als Stats-Studie gefuehrt (mit Basisrate) oder nur als
    Kennzahl/Diagnose?
20. Ereignisdefinition "schneller Move": Kriterium in Bars, Spanne in ATR und ATR/Bar, plus
    Richtung -- welche Schwellen, und werden sie **vorab** festgelegt?
21. "Kleines TPO-Nest" (die Bedingung): ueber Stufe-1- oder Stufe-2-Mass, und mit welcher
    Schwelle (TPO-Gipfel, Spanne in ATR, Intensitaet)?
22. Erfolgsmass der Fortsetzung: neues Extrem >= x ATR in n Bars, oder Close am Horizont?
    Beides ist zulaessig, aber nicht beides gleichzeitig.
23. Horizont: in Bars (K5) -- wie lang, und gibt es mehrere Horizonte (kurz/mittel) als
    getrennte Studien?
24. Wird die **Umkehr** als eigenes Ergebnis ausgewiesen (Erschoepfung) oder nur als "nicht
    fortgesetzt" verbucht?
25. Wird eine **Basisrate** gerechnet (ohne Nest-Filter, und/oder Zufallsniveau)?
26. Wie viele Ereignisse liefert der September ueberhaupt -- und was ist der Mindestumfang,
    unter dem wir "nicht entscheidbar" sagen?
27. Wird gegen Mehrfachtesten abgesichert (feste Schwellen vorab / Korrektur)?
28. Welche Kontrollgroessen werden miterhoben (Tageszeit, Abstand zum Vortagsnest, Move-Groesse,
    ATR-Regime), damit der Befund nicht von einem Stoerfaktor getragen wird?
29. Ist die Frage "Fortsetzung" ueberhaupt auf der Nest-Ebene zu stellen, oder gehoert sie auf
    die Bar-Ebene (Nest als Zustand, Ausgang als Bar-Ereignis)?

### D. Darstellung (Farbe/Dicke = reiner Indikator)

30. Kodiert die Farbe das Gesamtvolumen, die Intensitaet `V/Bars` oder ein TPO-Mass? (Farbe auf
    `V` macht sie zur Laengenkopie -- dann sagt das Bild nichts Neues.)
31. Falls zwei Kanaele: welche Groesse auf Farbe, welche auf Dicke?
32. Skala: linear ueber min..max, Rang/Perzentil oder Klassenstufen?
33. Skala fest je Lauf oder relativ je Bildausschnitt -- und ueber welche Menge (nur gueltige
    Nester)?
34. Wird die benutzte Skala als Text ausgewiesen (Legende oben links, Statistik mittig,
    Titel-/Dateinamen-Zusatz)?
35. Farbraum innerhalb der Nest-Familie mit `#00695c` als einem Endpunkt, oder eigene Sequenz --
    und wie wird `vp_sichtprobe.py` nachgefuehrt (die 11 Garantiefarben sind exakt, Toleranz 12)?
36. Randnester (violett `#8e24aa`, gestrichelt): Kodierung dort ueber Muster/Dicke, oder bleiben
    sie ausgenommen?
37. Wird zusaetzlich das **TPO-Nest** gezeichnet (eigene Objektmenge) oder nur der POC des
    Volumennests eingefaerbt? Ohne eigene Menge ist der 07.09.-Fall (kein Volumenberg) im Bild
    nicht sichtbar.
38. Falls beide Mengen gezeichnet werden: wie werden sie unterscheidbar gehalten (Flaeche =
    Volumennest, Klammer/Punktlinie = TPO-Nest), ohne mit bestehenden Konventionen zu kollidieren?
39. Bleibt die Fenster-Ebene (`fenster_ebene_zeichnen`) aus, auch mit Kodierung?

### E. Struktur: innerhalb eines Fensters

40. Sind mehrere Nester **innerhalb eines Tages** (11.09./14.09.) Zielgroesse -- oder gilt weiter
    "ein Tag = ein Fensterprofil, innen wird nicht geteilt"?
41. Falls Split: wirkt die Zeit-Ebene **im** eingefrorenen Kern (`find_mountains`) oder als
    **zweite, getrennte Berg-Menge**, die erst die Nest-Schicht verbindet? (Empfehlung: zweite
    Menge -- Kern unberuehrt.)
42. Ist der 08.09.-Fall ("zwei Level") eine reine Kalibrierungsfrage
    (Aufloesung/Tal/Absolutschwelle) oder ebenfalls ein Zeit-Fall?
43. Alternative fuer innerhalb des Tages: feinere Fensterart (h1/h4) -- ehrlicher oder nur
    Problemverschiebung?
44. Wird `min_mountain_pct` (relativ zum Tagesgipfel) durch eine **absolute** Huerde (Bars oder
    Dwell-Anteil) ergaenzt oder ersetzt -- das ist der eigentliche Hebel fuer 07.09./10.09.?
45. Bleibt die Zuteilung der Bars bei Close -> Zuteilungsband (Invariante "jeder Bar in genau
    EINEM Berg")? TPO darf die Zuteilung **nicht** uebernehmen.

### F. Benennung, Invarianten, Kanon

46. "balance" ist verbraucht, "Wanduhr" verboten -- welcher Begriff gilt fuer Aufenthalt/TPO
    (Diskussionsvorschlag: "Belegung" oder "Aufenthalt", mit je einem eindeutigen Feldpraefix)?
47. Gehen die neuen Parameter (TPO-Schwellen, Dwell-Tal, absolute Mindestgroesse) in
    `_store_parameter`/`run_id` und in den Dateinamen-Zusatz (wie `nstep`/`nlink`/`nlev`)?
48. Zeitbasis: Aufenthalt ausschliesslich ueber Bar-Index/BKZ, Horizonte in Bars -- bestaetigt
    (keine Stunden- oder Berlin-Projektion)?
49. Bleiben `rang` (immer 0) und "Territorien mit mehr als einem Nest" (strukturell 0) als
    Kontrollfelder oder raus aus Report/TSV?
50. Muss der Bericht die Klassifikationsregel **aussprechen** (Zitat der Regel im Report), damit
    eine Ausgabe ohne Dateiblick zuordenbar ist?

### G. Komplexitaet und Prozess

51. Wo ist die Komplexitaetsgrenze: Stufe 1 als gedeckelter Ausbau (Kennzahl + Surrogat) oder
    Stufe 2 mit zweiter Urteilsinstanz?
52. Falls Stufe 2: ODER- oder UND-Verknuepfung der beiden Berg-Mengen (Grundsatzentscheidung,
    keine Kalibrierung)?
53. Ist TPO als **Kennzahl-Spalte** ausgegeben genug, um die ganze Diskussion zu fuehren -- oder
    brauchst du die zweite Menge, um Entscheidungen zu treffen?
54. Soll der **Nachweis** gerechnet werden, dass ein **einziger** globaler Parametersatz
    (`valley_rel`/`smooth_win`/`num_bins`/`min_mountain_pct`) die fuenf Tage (a--e) nicht
    gleichzeitig sauber liest? Kern unangetastet, keine UI, keine Ablage -- erst dieser Nachweis
    begruendet den Zeit-Zuschnitt.
55. Ausgabeform des Nachweises: Tabelle "Tag x Parametersatz => Nest-Zahl" mit ausgewiesener
    Flimmerquote (ohne Flimmerquote ist eine hoehere Nest-Zahl wertlos)?
56. Sollen (a)--(e) als feste **Sichtpruefungs-Sollwerte** (Tag + erwartete Nest-Zahl + Charakter)
    festgehalten werden, damit spaetere Aenderungen daran messbar sind?
57. Reihenfolge: erst Kodierung/TPO-Kennzahl (billig, rein Sicht und Statistik) oder erst
    Erkennungskriterium (teuer, Eingriff)?
58. Wird der b)-Hypothese ein eigener Ort gegeben (Statistik-Block/Reportabschnitt), damit sie
    nicht als Nebenprodukt der Darstellung entsteht?

### H. LIVE-BETRIEB (Fernziel): Beginn-Erkennung -- schnell UND sicher

*Randbedingung: Aehnlichkeiten zur verworfenen Reclaim-Engine werden nur BENANNT, nichts wird
dort nachgebaut oder als Vorlage herangezogen.*

59. Wann genau gilt ein Nest als **begonnen**? Formale Definition des Onset-Zeitpunkts (erster
    Bar, an dem welche Kriterien halten) -- nicht als Gefuehl.
60. Wird ein Onset **sofort** gemeldet (kleine Latenz, Fehlstarts moeglich) oder erst nach
    **Bestaetigung** (n Bars / weitere Kriterien)? Das ist der Kern-Trade-off zwischen "schnell"
    und "sicher" -- er ist zu BENENNEN, nicht als Menue zu waehlen.
61. Nach welchem Kriterium wird bestaetigt: n Bars im Band, x ATR Ruecklauf, Volumenbestaetigung,
    TPO-Belegung, oder eine Kombination?
62. Zwei Zeitpunkte je Nest strikt trennen: `onset` (erstmalig feststellbar, kausal) und `final`
    (nach Abschluss, retrospektiv). Werden beide im Datenvertrag gefuehrt, und weist jede
    Statistik aus, welchen sie benutzt?
63. **Kausalitaet/No-Lookahead:** Welche Felder sind kausal (nur Bars <= t) und welche
    retrospektiv (Fenstergrenzen, Polster, Glaettung, Median-ATR, finaler POC)? Ohne diese
    Trennung ist die b)-Studie ein Survivorship-Artefakt.
64. Latenz-Budget in **BARS** (K5) ausdruecken; Millisekunden nur als Betriebsgroesse
    (maschinenabhaengig) -- in welcher Einheit wird das Budget festgelegt?
65. Wie viel Historie braucht die Erkennung (Warm-up: ATR, Median der Fenster-ATR, Fensterlaenge,
    Glaettungsfenster)?
66. Wie oft aendert sich die Aussage "Nest existiert" **rueckwirkend** (Revisionen je Nest)? Ein
    Stabilitaetsmass ist Pflicht, sonst ist die Live-Aussage nicht vertrauenswuerdig.
67. Flattern: Wie wird verhindert, dass ein Nest bei jedem Bar erscheint/verschwindet
    (Hysterese/Deadband)? Wird die Hysterese als Parameter extern gefuehrt?
68. Wird der Onset auf **demselben Rechenpfad** gefunden wie die Offline-Erkennung (ein Pfad, zwei
    Modi) oder als zweite, parallele Erkennung (doppelte Wahrheit)?
69. Inkrementelle Rechnung: Ist die TPO-Belegung je Bin inkrementell (O(1) je Bar) berechenbar,
    oder wird je Bar alles neu gerechnet? **Klaerung des Widerspruchs** Vektorisierungsgebot vs.
    Live-Inkrement.
70. Wenn ein Nest nachtraeglich verschmilzt oder geteilt wird: Was passiert mit einer bereits
    gemeldeten Live-Aussage (Korrekturmeldung, stille Revision, Sperre)?
71. Wird der Beginn ueberhaupt **handelbar** erreicht, oder liegt er systematisch nach dem Impuls
    (siehe b)? Das entscheidet, ob Onset-Erkennung wirtschaftlich ist.
72. Datenpfad live: dieselbe DuckDB? Bricht der Laufzeitspeicher bei Neustart? Muss der Zustand
    neu aufgebaut werden -- und wie lange dauert das?
73. Ausgabeform des Onset (Push-Trigger, Polling, Statussatz je Bar) -- was soll das Live-System
    abholen?
74. Wie wird ausgeschlossen, dass die Onset-Definition durch das spaetere Ergebnis beeinflusst
    wird (Testverfahren: erst Onset festlegen, dann Ausgang messen -- Walk-Forward)?
75. Wird die Grenze zur verworfenen Reclaim-Engine hier festgeschrieben (kein Code, keine
    Doku-Uebernahme, nur Analogie)? **Anwender-Vorgabe -- bitte bestaetigen.**
76. Gilt fuer die Live-Aussage derselbe Unsicherheitsbegriff (POC-Konsens) oder braucht sie einen
    eigenen Sicherheitsbegriff?
77. Ist Stufe 2 im Livebetrieb ueberhaupt vertretbar (Kosten je Bar), oder gilt Stufe 2 nur
    offline fuer die Statistik, waehrend live eine kausal verfuegbare Kennzahl laeuft?

## 7. Naechste Schritte (VORSCHLAG, nicht beschlossen)

1. Fragen 54/55: Nachweis rechnen, dass EIN globaler Parametersatz a--e nicht gleichzeitig sauber
   liest (Kern unangetastet, keine UI, keine Ablage, Tabelle Tag x Parametersatz mit
   Flimmerquote). -- Erst dieser Nachweis begruendet den Zeit-Zuschnitt.
2. Frage 56: a--e als Sichtpruefungs-Sollwerte festschreiben.
3. Fragen 1--7: Datenvertrag klaeren (Kern vs. ganz, Basis roh/gefiltert, Versionierung) --
   Voraussetzung fuer JEDE Statistik.
4. Fragen 59--63: Onset/`final`-Trennung und Kausalitaet -- Voraussetzung fuer die Live-Faehigkeit
   UND fuer die Ehrlichkeit der b)-Studie.
5. Fragen 30--39: Kodierung (billig, rein Sicht) -- entscheidet, ob der teure Eingriff noetig ist.

## 8. Die drei Fragen, die alles Weitere festlegen

1. **Ist der Split INNERHALB eines Tages Zielgroesse?** (Frage 40) -- Nein => Zeit nur als
   Kennzahl/Darstellung; Ja => zweite Berg-Menge und damit ODER/UND-Entscheidung (Frage 52).
2. **Ist die Statistik-Basis der TSV-Export oder eine neue Ablage?** (Frage 1) -- davon haengt ab,
   ob der Datenvertrag (Fragen 2--7) ueberhaupt exportierbar ist.
3. **Sind Onset und final getrennte Felder?** (Frage 62) -- Nein => die b)-Studie misst sich selbst
   (Survivorship) und die Live-Frage bleibt unbeantwortbar.
