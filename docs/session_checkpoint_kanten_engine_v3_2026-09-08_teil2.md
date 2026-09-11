# Session-Checkpoint V3 Straight-Edge — Teil 2 (2026-09-08, Harness-Scharfschaltung)

> **⚠️ Zeitbasis-Erratum (2026-09-11):** Dieses Dokument verwendet den historisch
> überladenen Begriff „Wanduhr" und teils die `Europe/Berlin`-Projektion (+2 h).
> **Verbindlich ist seit 2026-09-11 `docs/ZEITBASIS_KANON.md`:** Rechenbasis ist
> ausschließlich die **Broker-Kerzen-Zeit (BKZ)** = `time AT TIME ZONE 'UTC'`;
> `Europe/Berlin`/`Europe/Budapest` sind reine Anzeige-Dubletten.
> Abschnitte, die bereits `time AT TIME ZONE 'UTC'` nutzen, sind
> kanonkonform; Zeitangaben aus der alten Berlin-Projektion sind um
> −2 h gegen die BKZ verschoben.


> Status: **Harness-Code aktiv (test/tmp_kanten_engine_replay.py, gitignored).**
> D1–D5 scharfgeschaltet, danach 6 Mentoren-Befunde iterativ korrigiert
> (Patch 2–16). `py_compile` grün, AUG-Lauf Exit 0. Offene Arretierungen
> Q18–Q30 für die Wiederaufnahme.
> Vorgänger: `docs/session_checkpoint_kanten_engine_v3_2026-09-08.md`
> (Stand nach Commit `6136058`, vor Schritt 2).

---

## 1. Ausgangslage / Auftrag

Freigabe des Mentors: D1–D5 implementieren, `py_compile`, AUG-Smoke-Lauf
(`--fenster AUG --modus C`), Terminal-Zusammenfassung + 300-dpi-PNG vorlegen.
Danach zwei Sichtprüfungsrunden mit harten Befunden (siehe §4/§5).

Arbeitsumgebung: `.venv\Scripts\python.exe` (duckdb 1.5.5, numpy 2.5.2,
pandas 3.0.5). DB: `data/market_data.duckdb`, strikt
`time AT TIME ZONE 'UTC'`.

---

## 2. Umgesetzte Arretierungen (Code-Stand)

Datei: `test/tmp_kanten_engine_replay.py` (180.400 Zeichen, 22:46).

| Kürzel | Inhalt | Ort |
|---|---|---|
| D1 | `_SEEdgeH`: `ist_prim_anker`, `promoviert_ab_bar`, `letzter_sweep_bar`, `cluster_hoch/tief`, `erster_pivot_bar`; `basis_bei()` friert NUR den Anker ein (Q13) | Z. ~1975–2030 |
| D2 | `_reclaim_stufe()`: Stufen 1/2/3, echter Durchstich (`> touch_band`), Non-Expansion mit `doppeltop_puffer_usd = 0.01` (Q2/Q3/Q17), Sweep-Obergrenze 0.60 % | vor `_SEEdgeH` |
| D3 | `_se_scan`: Sweep-Zweig unverändert (Sweep-Immunität), Promotion nur im Scan-Kontext | Z. ~2078–2095 |
| D4 | `_se_trades`: Regel-2-Kaskade, dynamischer SL-Cluster (kausal), F2-Tracker via `letzter_trade`, SCHLAFEND-Gegenkanten (≥2 Touches, ≥1.5 %) | Z. ~2270–2440 |
| D5 | `_se_report`: `stufe`/`reclaim_bar`/`entry_bar`, H1-Ausweisung, F2-Sperrliste, Promotions-Sektion | Z. ~2440–2520 |
| Q9b | Seed-Promotion **nur ereignisgetrieben** (Seed zählt nur, wenn dieser Bar ihn durchsticht) | `_kandidat` |
| Q24 | `min_wall_alter_bars = 24`: kein Fade des Erst-Durchstichs einer frischen Linie | `_etabliert()` |
| Q25 | `wall_live_bars = 96`: dormante Außenlinien (K3/K4) blockieren die Unterseite nicht; lebende, nicht erreichte Linie sperrt alles innen | `_lebt()` |
| — | In-Band-Schatten: in-band berührte Außenlinie → nächste Linie nach innen | `_kandidat` |
| — | `dist == 0` = Berührung (weiter innen); `dist < 0` = nicht erreicht | `_kandidat` |

**Regel-2-Kaskade (final, von außen nach innen):**
1. Kandidatenpool = existierende Linien (`erster_pivot_bar + 2 <= k + 1`),
   Status AKTIV, Alter ≥ 24 Bars, `ist_prim_anker or touch_conf >= 2`.
2. Zusätzlich Seeds, die **dieser Bar** tatsächlich durchsticht (dist > band).
3. Sortierung außen → innen; je Linie: `dist < 0` → Ende (außer dormante →
   weiter); `dist > 0.60 %` → Ende; `dist <= 0.12 %` → weiter innen;
   sonst: `pos == 0` → handelt (Wand, Q1), sonst V-S ≥ 3 nötig.

---

## 3. Ist-Ergebnis AUG (Stand 22:46)

```
SE_BAND 0.120% | Box < 19.08 (bars < 644) | SE-Kanten 65 (OBEN 33/UNTEN 32)
Seeds 28 | Sweep-Sperren 14 | K33 eliminiert: True | K36 eliminiert: True
Promovierte Primaer-Anker: K6 64.312 (promo 39), K15 66.046 (101),
                           K20 66.459 (229), K3 62.967 (650), K62 68.989 (853)

REGEL-2-TRADES (Box): 5
  SHORT 229 STUFE_2 entry 231 K20 66.459 | TP1 63.676 TP2 63.605 | H1=TP1@386 | +6.92R
  LONG  310 STUFE_1 entry 311 K13 64.723 | H1=TP1@311               | -0.37R
  LONG  398 STUFE_1 entry 399 K5  63.619 | H1=TP1@415               | +5.44R
  SHORT 529 STUFE_2 entry 531 K31 66.327 | H1=TP1@614               | +8.41R
  LONG  639 STUFE_1 entry 640 K1  63.485 | H1=SL@643                | -1.00R
Ablehnungen: kein_Gegner=0 F3=0 F2_Vollrisiko=5 Q8=0 kein_Raum=11
F2-gesperrt: 242/244 (K20, offen bis 398); 530/531/564 (K31, offen bis 639)
```

Artefakte: `test/tmp_v3_straight_edge_harness_AUG.txt` (6.845 B),
`test/kanten_engine_trades_AUG_mC.png` (559.850 B, 300 dpi).

---

## 4. Mentoren-Befunde Runde 1 (3-Touch-Regel) und Korrektur

Befund: 3 SHORTs an Linien mit 2 Touches (K16 Bar 101, K15 Bars 108/229);
keine Trades am 12./17./18.08.; Unterkante korrekt.
Ursache: Q9b-Promotion machte jede 2-Touch-Linie handelbar; mehrere Linien
derselben Wand feuerten gleichzeitig.
Korrektur (P8–P10): strikte V-S ≥ 3 für innere Linien, Regel-2-Kaskade
außen→innen, In-Band-Schatten-Regel, keine Zwischen-Seed-Promotion.

## 5. Mentoren-Befunde Runde 2 (oberste Kante) und Korrektur

1. Zwei unberechtigte SHORTs am 10.08. (Minor-Kante, kein 3-Touch) →
   **Q24** Alters-Gate 24 Bars.
2. 11.08. invalider Short an falscher Kante, obwohl die höhere Kante mit
   1. Touch sichtbar war → **`erster_pivot_bar`** (Wand existiert ab
   Pivot+2 = Bar 109, nicht erst ab Keimung Bar 529).
3. 2. Touch an 66.46 (Bar 107, 03:45) → Bar 107 ist der **level-definierende
   Pivot** (strikt höchstes High ±2) → per Definition kein Touch. Reclaim der
   Wand erst ab Bar 110. **Q26 offen** (definierenden Docht als 1. Touch zählen?).
4. Valide Reclaims 12./17./18.08. → 12.08. (229→231) und 17.08. (529→531)
   feuern jetzt; 18.08. (564) ist **erkannt**, aber F2-gesperrt (529er offen
   bis 639, TP1 erst 614). **KORREKTUR 2026-09-09:** Der frühere
   Hypothesenwert „+1.49R / Entry 65.618" war falsch — `open[568]` gehört zur
   Stufe-1-Execution. Korrekt ist die Stufe-3-Kette Sweep 564 → 565 → 566 →
   **Entry `open[567] = 65.988`** (SL 66.586, TP2 = K1 kausal 63.4745) →
   **≈ +3.1 … +3.3 R**. **Q21 inzwischen arretiert (retest_zyklus_bars = 24).**

## 6. Offene Arretierungen (Wiederaufnahme)

- **Q18/Q30** — TP2 bei LONG 398: K20 (66.459) hat bei k=398 nur 1 Touch →
  K31 (66.327) wird TP2. Anker als Gegenkante ohne 2-Touch-Gate zulassen?
- **Q19** — Promotion von K6 (64.312) prüfen: Soll Promotion nur echte
  Range-Außen-Extreme treffen?
- **Q20** — Trade 101/108 an K15 (beide SHORTs, Verlierer) — mit Q24 jetzt
  eliminiert; Regel bestätigen.
- **Q21** — F2-Geltungsdauer: (a) unverändert, (b) nur innerhalb
  Reclaim-Schwung-Fenster (z. B. 6 Bars), (c) H1=SL hebt F2 auf.
  Entscheidet, ob 18.08. (und 245) feuern.
- **Q26** — Level-definierender Docht als 1. Touch zählen?
- **Q27** — Q24-Schwelle 24 Bars (Alternative 48) bestätigen.
- **Q28** — Q25-Liveness 96 Bars (1 Handelstag) bestätigen.
- **Q29** — LONG 310 (K13, 64.723) neu aufgetreten: gewünscht oder
  Zusatzkriterium (nur bereits gesweepte Wände) nötig?
- **Q23** — TP2 des 529er = 63.474 (K1) — bestätigen.

## 7. Technische Notizen für morgen

- **Edit-Tool gesperrt** (>100 KB, gitignored): Änderungen ausschließlich über
  verifizierte Patch-Skripte `test/tmp_patch_d1_d5_p*.py` (Zähl-Assertion,
  Abbruch ohne Schreiben, Backup vorher).
- **Rollback-Kette:** `test/tmp_kanten_engine_replay_pre_patch2..16.py`.
- **PNG-Fehler „OSError [Errno 22]"** tritt sporadisch beim Schreiben auf
  (Windows-Lock); Workaround: Lauf mit `> test\tmp_se_run_out.txt 2>&1`,
  danach erneut ausführen — Datei wird korrekt erzeugt.
- **Bar 243 High = 66.528** (Checkpoint §8 korrekt; Spez Z. 902 zeigte
  versehentlich den Close 66.523 → reine Doku-Korrektur offen).
- **Nicht committen:** `test/` ist gitignored; Docs-Änderungen (Spez-Korrektur
  Z. 902, ggf. Arretierungs-Nachtrag) müssen separat committet werden.

## 8. Daten-Anker (AUG, M15, Wanduhr)

- Box 10.08 00:00 … < 19.08 (Bar 644). Fenster AUG 2026-08-10 … < 08-28.
- Bar 85 (10.08 21:15) H 66.046 = K15-Pivot; Bar 101 H 66.223 (Sweep),
  Bar 107 (11.08 03:45) H **66.459** = K20-Pivot; Bar 229 H 66.776 →
  Reclaim 230 (66.419) → Entry 231 (66.424).
- Bar 242 H 66.663 → 243 H 66.528 → 244 C 66.090 → Entry 245 (66.092) = F2.
- Bar 529 H 66.538 (+0.119 %, in-band) → 530 C 66.515 → Entry 531 (66.324)
  an K31 (66.327); Bar 564 H 66.530 → 565 → Entry 568 (65.618) = F2.
- Bar 398 L 63.485 → C 63.757 → Entry 399 (63.763) an K5 (63.619) = +5.44R.
- Bar 1071 (25.08) bzw. post-Box: K62 68.989 (promo 853), K3 ab Bar 650.
