# Session-Checkpoint V3 Straight-Edge (SILVER M15) — 2026-09-08

> **⚠️ Zeitbasis-Erratum (2026-09-11):** Dieses Dokument verwendet den historisch
> überladenen Begriff „Wanduhr" und teils die `Europe/Berlin`-Projektion (+2 h).
> **Verbindlich ist seit 2026-09-11 `docs/ZEITBASIS_KANON.md`:** Rechenbasis ist
> ausschließlich die **Broker-Kerzen-Zeit (BKZ)** = `time AT TIME ZONE 'UTC'`;
> `Europe/Berlin`/`Europe/Budapest` sind reine Anzeige-Dubletten.
> Abschnitte, die bereits `time AT TIME ZONE 'UTC'` nutzen, sind
> kanonkonform; Zeitangaben aus der alten Berlin-Projektion sind um
> −2 h gegen die BKZ verschoben.


> Status: **Erkundungs-/Analyse-/Dokumentationsphase.** Kein Feature-Code-Compile
> ohne Freigabe. Fortsetzung später — dieser Checkpoint stellt den vollständigen
> Kontext wieder her (Stand nach Commit `b253175`, vor Schritt 2).

## 1. Projektregeln (bindend)

- Arbeitsverzeichnis `F:\Python\PyLab` (Win, PyCharm). Keine UI-/Regressions-Tests;
  Verifikation nur via `python -m py_compile`, isolierte Logik-Tests in `test/`
  (nie im Root/data). Test-Python/`*.duckdb` immer in `test/`.
- Wanduhr-Invariante: MT5-Epochs Berlin-encoded; SQL nutzt strikt
  `time AT TIME ZONE 'UTC'`, tz-naiv. M15-Fenster exakt frozen.
- Commit-Signatur: „Generated with [Continue](https://continue.dev) /
  Co-Authored-By: Continue <noreply@continue.dev>".
- **Prämisse:** Entscheidungen als Textblock mit Antworten/Begründung, KEINE
  Menü-Auswahl durch die IDE.
- Prämisse/Invariante: `meter_schema`/`default_params` auf Klassenebene direkt
  unter Header-Docstring (anwendbar auf SE-Konfigurations-Dataclasses).

## 2. Arretierte Commits (Docs) — Kette

- `69e9698` — §7.2 Straight-Edge-Revision (E1–E5): U2-Revokation, Cluster-Keimung
  ≥2 Dochte, SE_BAND 0.11/0.115/0.12 %, Außenkanten-Prinzip, Histogramm-POC,
  Box-Phase 10.–18.08. als Eichmaßstab.
- `a771e04` — §7.2-Nachtrag **Sweep-Immunität**: Reclaim-Dochte bilden nie neue
  Linien; 3 Lücken-Korrekturen (Grace k+2, Referenz inkl. Singleton-Seeds,
  In-Band-Vorrang); `touch_band_pct = 0.12` arretiert; V-S ≥ 3;
  Gültigkeitskorridor Überdehnung [0,478; 0,625] %.
- `b253175` — §7.2-Nachtrag **Dreistufige Reclaim-Hierarchie & Sweep-Immunität**
  (2026-09-08, nach Sichtprüfung): Primär-Anker 66,459 USD ab Bar 107 als
  unverrückbare Grundlinie; `STUFE_1_IN_BAR` (Entry k+1), `STUFE_2_KERZE_2`
  (Bsp. Sweep 229 → Reclaim 230 → Entry Open 231), `STUFE_3_KERZE_3`
  (Bsp. Sweep 242 → Zwischenbar 243 → Reclaim 244 → Entry Open 245; temporär
  aktiv, S1/S2-Entbehrlichkeitsprüfung); Sweep-Immunität über alle 3 Stufen;
  SL = Extremum ± 0,05; TP1 = POC (60 Bins, t ≤ k) 50 %; TP2 = äußere
  Gegenkante (≥2 Touches, ≥1,5 % Distanz, AKTIV/SCHLAFEND); Datenvertrag
  `ReclaimTriggerKonfiguration`/`ReclaimSignalEvent` mit `stufe`-Ausweisung.

## 3. Audit-Referenz (read-only, abgenommen)

- Datei: `test/tmp_v3_straight_edge_audit.py` (rein lesend, gitignored).
  Enthält `SweepImmunitaetKonfiguration`, `ist_sweep_einer_bestehenden_referenz`,
  `AuditNachweisErgebnis` (ist_perfekt), `_scan_se`, `_zaehle_setups`, `_soll_zonen`.
- **Nachweis (Band-Sweep 0.110/0.115/0.120):** 0.120 → SE 65, Seeds offen 29,
  14 Sweep-Sperren, K33 (Bar 229/66.776) + K36 (Bar 242/66.663) **eliminiert**,
  Soll-Zonen **5/5 7/7 4/4 3/3**, V-S 3 (Bars 398/527/639), V-2 7.
  `ist_perfekt = True`. Blockierte Vorläufer: Bars 9/39/42/101 (OBEN, Reclaims)
  + post-Box-Regime 650/745–764/853/859 — als Marktbereinigung abgenommen.
- Artefakte: `test/tmp_v3_straight_edge_audit_AUG.txt`,
  `test/kanten_engine_straight_edge_AUG.png`.
- In-Band-Vorrang kalibriert: K23-Keim-Dochte 529 (+0,119 %) / 565 (+0,116 %)
  bleiben unter arretiertem 0.12 → K23 (66.511) bleibt als zweite Upper-Sub-Linie.

## 4. SE-Harness (Schritt B/C, ausgeführt, gitignored)

- Datei: `test/tmp_kanten_engine_replay.py` (nach SE-Einbau ~4100 Zeilen;
  **Datei auf LF normalisiert**; `import os` ergänzt; Alt-A/B/C-Strukturen
  unangetastet). Additiver SE-Block vor dem REPLAY-Abschnitt mit:
  `StraightEdgeHarnessKonfiguration` (0.12 / min_touches 3 / ueberdehnung 0.60 /
  grace 2 / sl_buffer 0.05 / split 50 / bins 60),
  `berechne_kausalen_histogramm_poc` (60 Bins, volumengew. Überlapp, win=3),
  `ist_sweep_einer_bestehenden_referenz_se` (any-Reclaim),
  `_SEEdgeH` (Mittel-Basis, schlaf_windows), `_se_scan`, `_se_trades`,
  `_se_report`, `_zeichne_se_png`, `_replay_c_se_main`.
- `main()`: `--modus C --fenster AUG` → SE-Harness (`_replay_c_se_main`);
  S1/S2 → Alt-C-Referenz (`_lauf_c`).
- **Lauf-Ergebnis (`--fenster AUG --modus C`):** SE-Kanten 65 (OBEN 33/UNTEN 32),
  ≥3 Touches 49, Seeds offen 29, Sweep-Sperren 14 (K33/K36 eliminiert).
  3 V-S-Trades (in_bar, Box): LONG 398 an K5 +5,44R (TP1-POC 64.770, TP2 66.327);
  SHORT 527 an K31 −1,00R (SL 66.428 — Fehlschlag, innere Kante statt Wand);
  LONG 639 an K1 −1,00R. Artefakte: `test/tmp_v3_straight_edge_harness_AUG.txt`,
  `test/kanten_engine_trades_AUG_mC.png` (300 dpi).

## 5. Sichtprüfungs-Befunde (Mentor, daten-verifiziert) — Motivation für `b253175`

Oberkante:
1. Erster Peak 10.08 (Bar 85 H 66.046 = K15) erscheint als eigene Linie, nicht
   Teil der Wand; ebenso K16 (65.905, Touches 90/96/114).
2. 3. Touch am 11.08 (K16 Bar 114 H 65.938, C 65.790 ≤ 65.905 = echter Reclaim)
   ohne Signal — p+2-Puffer: `touch_conf(114)=2 < 3` → V-S verweigert.
3. Wand-Reclaims 17.08 verpasst: echte Wand K20 (66.511, Touches 107→529→565)
   erreicht in der Box nie ≥3 bestätigte Touches VOR einem Reclaim; stattdessen
   triggert innere K31 (66.36) bei Bar 527 → SL (Markt läuft zur Wand 66.53).

Unterkante:
4. Frühe Zone 63.7 in K5 (63.633) + K8 (63.758) gesplittet; Reclaims 380
   (L 63.716) / 386 (L 63.663) durchstechen die äußerste K5 nicht → stumm;
   erst tiefer Reclaim 398 (L 63.485, C 63.757) löst korrekt aus.
   K24-Minor-Reclaim Bar 361 (13.08 21:15) korrekt stumm (innere Linie).

## 6. Interview-Antworten (2026-09-08, maßgeblich für Schritt 2)

### F1 — Reife-Bedingung an Bar 229: **JA, Freigabe ohne vorherigen 2. Touch.**
- Die Decke 66,459 (Bar 107) ist ab Bestätigung (Bar 109) als **äußerste aktive
  OBEN-Referenz** reclaim-handelbar. Ein 2. Touch vor dem ersten Reclaim ist
  logisch unmöglich (K23-Klemme: Wand erreicht ≥3 nie vor Reclaim in der Box).
- Die Reclaim-Bestätigung (Stufe 1/2/3) IST die operative Reife (Gegenwehr
  sichtbar). Filter bleiben: nur äußerste Referenz der Seite (inkl. Singleton-
  Primär-Anker = laufendes Range-Extremum), Überdehnung ≤ 0,60 %, Stufen-Reclaim.
  Innere Linien/Seeds stumm (kein Barcode). In-Band-Dochte = keine Sweeps.
- **Implementierung:** RANGE_AUSSENGRENZE = äußerste AKTIVE Referenz **inkl.
  ungekeimtem Primär-Anker**; Anker unverrückbar (Sweeps werden nicht
  eingemittelt, nicht als balancierende Touches gutgeschrieben).

### F2 — Positionsverwaltung 231 vs. 245: **F3-Sperre mit De-Risk-Freigabe.**
- Gleiche kanten_id (107er-Anker). Solange der 231er-Trade läuft und KEINE Hälfte
  TP1 erreicht hat → F3 blockiert 245er (kein Stacking). Sobald Hälfte 1 TP1
  erreicht (50 % de-riskt) → neuer Trigger freigegeben (eigene Position/SL/TP).
  F3-Frische: Sweep-Docht selbst zählt als frischer Kontakt (242 > letzte
  Signal-Bar 231).
- Konkret: 231er-Short läuft in Abfall (Bar 242 L 65.598) → TP1 (POC im Korridor
  66.459→Gegenkante) wird vor 244/245 erreicht → 245er-Einstieg regelkonform frei.
- **Implementierung:** `offen_bis`-Sperre je kanten_id ersetzen durch:
  Einstieg frei wenn (a) kein offener Trade an der Kante ODER (b) offener Trade
  hat TP1 erreicht (Hälfte 1 geschlossen). Trade-Tracker braucht Exit-Status H1.

## 7. Nächste Schritte (nach Wiederaufnahme, Freigabe abwarten)

- **Schritt 2:** Additive Implementierung in `test/tmp_kanten_engine_replay.py`
  (`_se_trades`): (a) dreistufige Reclaim-Auswertung (STUFE_1/2/3) an der
  äußersten Referenz inkl. Primär-Anker; (b) Sweep-Immunität für alle getriggerten
  Reclaim-Dochte (Dochtspitze keim-gesperrt, aber Trade erlaubt); (c) kausaler
  60-Bin-Histogramm-POC für TP1; (d) Positions-Logik F2 (De-Risk-Freigabe);
  (e) `stufe`-Ausweisung im Report (STUFE_1_IN_BAR an Open k+1, STUFE_2 an k+2,
  STUFE_3 an k+3).
- Erwartung: **Bar 229 → Reclaim 230 → Entry Open 231** (Stufe 2) und
  **Bar 242 → Zwischenbar 243 → Reclaim 244 → Entry Open 245** (Stufe 3) feuern
  exakt spezifikationskonform an der Grundlinie 66,459.
- **Schritt 3:** `python -m py_compile test/tmp_kanten_engine_replay.py`.
- **Schritt 4:** `python test/tmp_kanten_engine_replay.py --fenster AUG --modus C`
  → PNG `test/kanten_engine_trades_AUG_mC.png` (300 dpi) + Trade-Tabelle zur
  Sichtprüfung (Trades an 231/245; kein 527er-Fehlshort an innerer K31 mehr;
  Reclaim-Long 380/386-Frage für Unterkante separat prüfen).

## 8. Daten-Anker (AUG, M15, Wanduhr — für schnelle Wiederaufnahme)

- Box: 10.08 00:00 … < 19.08 (Bar 644). Fenster AUG: 2026-08-10 … < 08-28.
- Bar 85 (10.08 21:15) H 66.046 · Bar 90/96 (10./11.08) K16 65.905 ·
  Bar 101 (11.08 02:15) H 66.223 (sweep-gesperrt, ref 66.046) ·
  **Bar 107 (11.08 03:45) H 66.459 / C 66.311 = Primär-Anker** ·
  Bar 114 (11.08 05:30) H 65.938 C 65.790 (K16-3.Touch-Reclaim, p+2-Lücke).
- Bar 229 (12.08 11:15) H 66.776 C 66.471 → Reclaim-Close 230 (66.419) [Stufe 2].
- Bar 242 (12.08 14:30) H 66.663 L 65.598 C 66.480 → Zwischenbar 243 (H 66.528)
  → Reclaim-Close 244 (66.090) [Stufe 3].
- Bar 380 (14.08 03:00) L 63.716 C 63.926 · Bar 386 (14.08 04:30) L 63.663
  C 64.001 (K5 63.633 nicht durchstochen → stumm) · Bar 398 (14.08 07:30)
  L 63.485 C 63.757 (K5-Reclaim ✓ +5,44R).
- Bar 529 (17.08 17:15) H 66.538 (+0,119 % in-band, K23-Touch) → Reclaim 530
  (66.322) · Bar 564 (18.08 03:00) H 66.530 C 66.433 (K23, 2. best. Touch erst
  später) · Bar 565 H 66.536 → Kollaps 566/567 (L 65.404).
