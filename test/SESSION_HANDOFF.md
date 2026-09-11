# ⛔ EINGEFRORENES HISTORISCHES PROTOKOLL (01.–02.09.2026)

> **Dieses Dokument wird NICHT mehr gepflegt** (eingefroren am 02.09.2026).
> Es dient nur noch als **Archiv/Historie** (verworfene Ansätze, Referenzzahlen,
> Git-Zustand), um Wiederholungen/Re-Tests zu vermeiden.
>
> **⚠️ Erratum (2026-09-11):** Der frühere Bootstrap-Verweis auf
> `docs/reclaim.md` war **falsch** — diese Datei existiert weder im Dateisystem
> noch in git. Der Live-Session-State steht im **jeweils letzten
> Append-Abschnitt** dieser Datei. Verbindliche Zeitbasis ist seit 2026-09-11
> **`docs/ZEITBASIS_KANON.md`** (BKZ = `time AT TIME ZONE 'UTC'`; die frühere
> `Europe/Berlin`-Projektion ist aufgehoben)

---

# Session-Handoff (01.09.2026) – SILVER M15 Setup B (Reclaim/Fakeout)

> **Hinweis:** Diese Datei wurde am 01.09.2026 von `docs/` nach `test/` verschoben (User-Anweisung).
> Test-Dateien gehören in den Unterordner `test/` (Regel aus Agents.md).

## Projekt
- Datei: `scripts/tmp_phasen_volumen_profil.py` (Original, einzige gültige Referenz)
- **REGEL (02.09.): Baseline wird NIE veraendert.** Simulationen/Experimente laufen
  NUR auf Arbeitskopien. Uebernahme ins Hauptskript nur nach User-Freigabe.
- Test-Skripte nur in `test/` (Regel) – **verworfene Diagnose-/Prototyp-Skripte
  liegen in `test/archiv/`** (Aufraeum-Aktion 02.09.):
  - 3-Eck/Boxen-Segmentierung: `test_kausal_box_reife.py`, `test_sweep_cap.py`,
    `test_diag_3eck_v6(_chart/_v7_vmove).py`, `test_diag_box_persistenz.py`
  - SL/Struktur-Regel: `tmp_diag_sl_kante(_rel).py`, `tmp_diag_struktur_regel.py`,
    `tmp_diag_check_0700.py`, `tmp_diag_trade_p7.py`, `tmp_diag_p7p8.py`
  - Zonen-Diagnose August: `test_diag_volumen_zone.py`
  - Helper: `tmp_phasen_volumen_profil_v2.py`; CSV: `silver_m15_ohlc_...csv`
- Aktive Test-Skripte (verbleibend):
  - `test.py` – Standard-Logiktests
  - `test_sweep_kausal_reopt.py` – kausale Re-Optimierung (rcand/bounce/crv/cooldown)
  - `test_validate_2025_kausal.py` – 2-Sample-Validierung (Sample 2: 2025)
- Ergebnisse: (historische Ergebnis-TXT wurden bereits entfernt/committet,
  Kennzahlen stehen in diesem Handoff)
- DB: `data/market_data.duckdb` (SILVER M15, UTC)

## ⚠️ KRITISCH: Lookahead bereinigt (31.08.2026)
- `find_reclaim_signals` wurde umgebaut: **kein finales Zonen-Screening mehr** (früher filterte die finale Phase-Volume-Zone die Kandidaten = Blick in die Zukunft).
- Jetzt: rein sequenzielle Schleife über ALLE Bars der Phase, laufende Zone nur bis Bar k.
- **Effekt:** Performance massiv korrigiert:
  - 2026 (Feb–Aug): 125 Sig/65%/+250.80R → **201 Sig/44%/+197.26R** (CD=12) → **226 Sig/43%/+219.14R** (CD=8, neuer Default)
  - 2025 (Jan–Nov): 84 Sig/63%/+144.14R → **210 Sig/35%/+99.88R** (CD=12) → **240 Sig/35%/+110.79R** (CD=8)
- L4-Datenende-Finalize (Regel 7, D1-Variante) ist bewusst POST-HOC, nur für Grafik – User erlaubt, NICHT fixen.

## ✅ ERLEDIGT (Re-Optimierung auf kausalem Code, 31.08.2026)
- Sweep über MIN_RECLAIM_CANDLES (0–100), bounce (1–3), crv (0.5–2.5), cooldown (8–16), Sample 1 (2026-02-05…08-28).
- **Bestätigt:** MIN_RECLAIM_CANDLES=0, MIN_RECLAIM_BOUNCE=2, MIN_RECLAIM_CRV=1.0 halten auf kausalem Code (Lookahead-Optima waren robust).
- **NEUER DEFAULT:** MIN_SIGNAL_ABSTAND_BARS **12→8** (einziger stabiler Gewinner über beide Samples):
  - CD=8: S1 +219.14R/226 Sig/43% WR (vs. CD=12 +197.26R) | S2 +110.79R/240 Sig (vs. +99.88R)
  - CD=6 bringt weitere +11R/+5R, aber abnehmender Grenznutzen + sinkendes avg R → CD=8 als Knie-Punkt.
  - Verworfen: CD=14 (nur in S1 gut = Overfit), rcand=30 (beide Samples schlechter).
- Kommentar am Parameter im Skript auf kausalen Stand aktualisiert.
- **Kosmetik-Fixes:** Ausgabe-Header nutzt jetzt `TP2_PUFFER_PCT` und `SL_PCT` korrekt (vorher hartkodiert "0.15%" bzw. `:.1f`-Rundung "0.5%" statt 0.45%).

## ✅ ERLEDIGT (Volumenbereich-Diagnose August, 01.09.2026)
**Ausgangslage:** Baseline August = 33 Sig / 39% / +25.01R. Die P5-Signale (14.–18.08) waren Verluste (SHORTs an Zwischen-Kanten 64.7–65.9).

**Diagnose-Befunde:**
1. **Finale vs. laufende Zone:** 30/33 Signale an abweichenden Kanten. Finale Zone = 27 Sig / 78% / +71.06R (Zielmarke, aber Lookahead).
2. **Zonen-Drift:** Laufende Zone am Phasenanfang zu eng (P5: 0.36 USD = 0.56% Breite, final 2.65 = 4.1%).
3. **User-Konzept bestätigt:** Die Aufwärtsbewegung 14.–18.08 (63.8→66.3) ist der **Arm der alten Box (66.45–63.76)**. Die Verlust-Signale sind SHORTs mitten in der Box; die Gewinne = echter Reclaim am oberen Box-Ende.
4. **Segmentierungs-Mangel:** P5 (14.–18.08) hätte gar nicht als eigene Phase generiert werden dürfen:
   - UNTEN-Kante 64.198 hat **nur 1 Touch** (Geburtszone, kein echter Test)
   - **KEINE 3 Eckpunkte** (H-L-H/L-H-L) mit ≥1.5% Weite (alle H-L-H zu eng; L-H-L nur in Bewegungsmitte)
   - Der 3-Touches+1.5%-Filter existiert NUR im nachgelagerten "HANDELBARE RANGES"-Filter, nicht in der Phasen-Generierung
   - Neue Phase startet immer direkt am `brk_idx` des Ausbruchs – OHNE Validierung "echte Box"
   - `MIN_ESTABLISH=4` zählt nur Touches gesamt (H+L), nicht 3 Eckpunkte

**Getestete Ansätze (alle August):**
| Variante | Phasen | Signale | WR | Summe R |
|---|---|---|---|---|
| Baseline (Volume-Kanten, 12 Phasen) | 12 | 33 | 39% | +25.01R |
| Meta-Box+VolZone (EST=12 komplett) | 2 | 28 | 36% | +15.11R |
| Box-Persistenz-Simulation (post-hoc 66.45/63.76) | – | 10 | 40% | +24.50R |
| Zonen-Vererbung (P5 erbt M1-Box-Zone) | – | 28 | 50% | +40.03R |
| **v6 (3-Eckpunkte+1.5%-Weite, Arm=Verschmelzung)** | **3** | **34** | **50%** | **+56.87R** |

**v6-Details (AKTUELLER STAND):**
- **Reife-Regel:** 3 aufeinanderfolgende abwechselnde Pivots (H-L-H/L-H-L), |p1-p3| ≤ 0.30 (gleiche Kante), Weite |p2-p1| ≥ 1.5%
- Reife Phase = eigenes Segment; nicht-reife Phase = **Arm der vorherigen Box** (Pivots wandern zur Box, Signale an deren laufender Volume-Zone)
- **Boxen:** B1=P1 (Arm-Sammlung), B2=P2+P3+P4+P5+P6+P7+P8 (REIF ab 11.08 04:45), B3=P9+P10+P11+P12 (REIF ab 24.08 04:30)
- **Nur 2 Phasen reif:** P2 (L 65.40/H 66.46/L 65.54), P9 (H 69.52/L 68.39/H 69.33)
- Gewinner-Fenster: P3 −3.00R→+9.60R, P5 +6.31R→+18.97R, P6 −2.00R→+11.21R, P9 +9.44R→+12.15R
- Verlierer-Fenster: P7 +2.26R→−3.00R, P10 0→−1.87R, P12 +6.72R→+3.84R

**Verworfene Ansätze:** Meta-Box komplett (EST=12 zu grob für 19.–27.08, M2=11%-Riesenbox → Verlust-SHORTs gegen Trend), Schnittkante, STABIL-Filter (zu streng), v3/v5 (Bruch-Check zu empfindlich/Henne-Ei).

## ✅ ERLEDIGT (SL-Untersuchung + Struktur-Regel, 01.09.2026)

### Diagnose: 04:15-SHORT in P7 (B3) – SL unter der Kante
- Signal 20.08 04:15, Kante U=67.264, Entry 04:30 @ 66.953, SL=67.254 (SL_PCT 0.45% vom Entry) → **SL liegt 0.010 UNTER der Kante**.
- 07:00-High 67.282 ≥ SL → **normaler Kante-Retest stoppt den Trade: −1.00R** (TP1 65.853/TP2 65.666 wurden erst 14:00 erreicht).
- **Kern-Problem systemisch:** `SL_PCT vom Entry` kann in die Struktur rutschen. Der Docstring sagt "SL hinter der Kante", der Code macht aber % vom Entry.
- 07:00-Fakeout: KEIN Signal (laufende Zone hatte sich aufgebläht: POC 65.85→67.04, U 67.264→67.294 → 07:00-High 67.282 < U; zusätzlich e 66.99 < POC 67.04 = POC-Filter). Hypothetisch: Entry 07:15, SL 67.291 → überlebt, +3.26R.

### Kante-SL-Simulation (fixe USD-Puffer, v7-arm August, CRV=1.0)
| Variante | Sig | WR | Summe R | avgR | avgRisk |
|---|---|---|---|---|---|
| entry (Baseline) | 37 | 54% | +65.97R | +1.78 | 0.45% |
| kante+0.00 | 46 | 28% | +45.25R | +0.98 | 0.17% (unrealistisch, SL auf Kante) |
| **kante+0.05** | 42 | 40% | **+121.21R** | +2.89 | 0.24% |
| **kante+0.10** | 40 | 48% | **+105.66R** | +2.64 | 0.31% |
| kante+0.15 | 39 | 54% | +88.54R | +2.27 | 0.39% |
| kante+0.25 | 37 | 59% | +61.22R | +1.65 | 0.54% |
| kante+pct 0.45% | 34 | 59% | +50.96R | +1.50 | 0.60% (Risk zu hoch, CRV-Filter wirft raus) |
- **Überraschung:** kante+0.05–0.15 USD = medianes Risk ENGER als 0.45% Baseline (Einstiege nahe Kante); nur p90-Fälle werden weiter.
- kante+0.00 unrealistisch (Slippage/Spikes); kante+pct verliert (User-Sorge "hohes Risk" bestätigt für große Puffer).

### Relative Kante-Puffer, 2-Sample (v7-arm, CRV=1.0) – `tmp_diag_sl_kante_rel.py`
| Variante | August | Sample 1 (2026) | Sample 2 (2025, OOS) |
|---|---|---|---|
| entry (Baseline) | +65.97R / 54% | +238.07R / 32% | +47.59R / 27% |
| kante+0.10% | +105.59R / 41% | **+399.74R** / 28% | +52.28R / 16% |
| kante+0.15% | **+109.07R** / 50% | +351.56R / 31% | +1.00R / 16% |
| kante+0.20% | +87.49R / 51% | +280.26R / 31% | +31.47R / 20% |
| kante+0.25% | +84.83R / 56% | +226.76R / 32% | +29.74R / 23% |
| kante+0.30% | +72.97R / 56% | +187.35R / 32% | +36.20R / 24% |
- **Fazit: NICHT OOS-robust.** 2026 stark (+68% S1), 2025 kollabiert (WR 16%, kante+0.15% → +1.00R). Klassisches Overfit-Muster.
- Replay-Architektur im Skript: laufende Zone je Bar NUR EINMAL berechnen, SL-Varianten danach per Replay (Cooldown+CRV) → skaliert nicht mit Variantenzahl. Läufe: aug 7s, s1 58s, s2 366s.

### Struktur-Regel (Kanten-Legitimität) + Koppel-Test – `tmp_diag_struktur_regel.py`
- **Regel (User):** Signal nur an legitimen Kanten: (a) Kante nahe Ober-/Unterkante einer FRÜHEREN reifen Box ± TOL, (b) Kante nahe laufender Schnittmengen-Kante der AKTUELLEN Box ab Reifezeitpunkt ("box(reif)"), (c) 3-Eckpunkte (H-L-H/L-H-L) mit |p1-p3|≤0.30 und Weite ≥1.5% in der Box-Historie. Kausal mit Pivot-Lag.
- **August:** filtert korrekt – B3-illegitime SHORTs (67.26/68.27) raus, B1 (Arm ohne Reife) komplett raus, nur der 66.34-"alt"-Short (alte P2-P5-Kante) bleibt. 37→21 Sig, WR 54→67% (kante+0.25%), aber Summe R sinkt (+46.9R entry / +62.3R kante+0.25% vs. +66R Baseline).
- **Sample 1:** 306→189 Sig, Summe R sinkt deutlich (238→146R entry; kante+0.10% nur +198R). Der Filter entfernt auch profitable Signale.
- **Sample 2:** 278→179 Sig, +47.6R→+8.9R (entry). **Regel-Lücke:** 434/550 Kandidaten (79%) passieren über das zu laxe "box(reif)"-Kriterium → in 2025 fast wirkungslos.
- **Kernbefund:** Struktur-Regel in August-WR korrekt, aber über beide Samples renditesenkend. "box(reif)" zu laxe = entspricht NICHT der User-Intention.

## ⏭️ AKTUELLER ZUSTAND / NÄCHSTE SESSION (01.09.2026)
- **Stand nach SL- & Struktur-Untersuchung:** Kante-SL allein und Struktur-Regel+Kante-SL sind NICHT OOS-robust → **keine Übernahme ins Hauptskript**. Baseline (SL vom Entry) bleibt die robusteste Variante (alle 3 Fenster positiv, WR 27–54%).
- **Nächster logischer Schritt (noch NICHT getestet):** Striktes Struktur-Kriterium (NUR "alt" + "eck", OHNE das zu laxe "box(reif)") – präzise User-Intention. Danach ggf. erneut mit Kante-SL koppeln.
- **User-Anweisung weiterhin:** NICHT eigenmächtig ins Hauptskript einbauen, auf User-Eingabe warten.
- **Offene Punkte für Anpassungen (August):**
  1. P7 (19.–20.08, Aufwärtsbewegung nach Box-Bruch) wird durch breite B2-Zone verschlechtert: −3.00R statt +2.26R (SHORTs gegen Trend an 67.0–67.25)
  2. P10/P11 (25.–26.08): B3-Zone zu breit → −1.87R (LONGs an 67.8–68.3, die weiter fallen)
  3. P12 (26.–27.08): +3.84R statt +6.72R (B3-Zone aus P9-P12 vs. eigene P12-Zone)
  4. B1=P1 ist eine Arm-Sammlung ohne Reife – prüfen ob das so gewollt ist (erste Phase im Datenfenster)
- **Mögliche Stellschrauben (nur nach User-Eingabe):** TOL_KANTE (0.30), MIN_WEITE_PCT (1.5%), COOLDOWN, Signale nur ab Reifezeitpunkt der Box, Reife-Check auf ganzer Box statt je Phase

## Aktuelle Konfiguration (Default-Werte im Skript)
```
TOL=0.34 | VA_PCT=0.93 | MIN_MOUNTAIN_PCT=4.0 | VALLEY_REL=0.15 | MIN_ESTABLISH=4
MIN_RECLAIM_CANDLES=0 | MIN_RECLAIM_BOUNCE=2 | MIN_RECLAIM_CRV=1.0 | MIN_SIGNAL_ABSTAND_BARS=8
SL_PCT=0.45 | TP2_PUFFER_PCT=0.20 | ANTEIL_TP1=25 | TRAILING_PCT=0.0
```
- Achtung: TOL/VA_PCT/MIN_MOUNTAIN_PCT/VALLEY_REL/MIN_ESTABLISH/SL_PCT/TP2_PUFFER_PCT/ANTEIL_TP1 sind noch auf den LOOKAHEAD-Code optimiert (GETESTET-Kommentare = Reihentest 05.02.–28.08.26) – auf kausalem Code bisher NUR cooldown/rcand/bounce/crv neu validiert. Rest optional nachziehen.
- CLI-Overrides vorhanden: `--tol= --va-pct= --mountain-pct= --valley-rel= --establish= --reclaim-candles= --bounce= --crv= --cooldown= --sl-pct= --tp2-puffer= --anteil-tp1= --trailing= --start= --ende= --moves=1`

## Validierung (2 Samples)
- Sample 1: 2026-02-05 → 2026-08-28 (Hauptoptimierung)
- Sample 2: 2025-01-01 → 2025-12-01 (Out-of-Sample, Dez. ausgenommen = nicht repräsentativ)
- Kausal bestätigt: rcand=0/bounce=2/crv=1.0/CD=8 in beiden Samples (CD=8 als einzige Änderung).
- **v6/v7-Segmentierung (3-Eckpunkte):** August fertig, auf Samples nur als v7-arm-Boxenbasis getestet (Kante-SL & Struktur-Regel). Separate Validierung der Segmentierung selbst noch offen (User-Vorgabe: erst August fertig).
- **Kante-SL / Struktur-Regel:** 3-Fenster-Validierung abgeschlossen (01.09.2026) → beide NICHT OOS-robust, keine Übernahme. Details oben.

## Nächste Schritte (offen)
1. ⏳ **Strikte Struktur-Regel testen** (NUR "alt"+"eck", OHNE "box(reif)") – in `tmp_diag_struktur_regel.py` umsetzbar (Kriterium in `kante_legitim` auskommentieren). Danach erneut 3-Fenster-Validierung + ggf. Kante-SL-Kopplung.
2. Danach: v6/v7-Segmentierung auf Sample 1 + Sample 2 validieren (wie CD=8) – erst nach Freigabe.
3. Optional: restliche Parameter (TOL, VA_PCT, SL_PCT, TP2_PUFFER, ANTEIL_TP1) auf kausalem Code nachvalidieren.
4. Setup A (Counter-Trend-Reversal an der Kante) ist noch NICHT implementiert – User will es später.
5. Setup C (Move-Trades) vorhanden, `--moves=1`, evtl. Trailing dort testen (Trailing-Kopie existiert).

## Wichtige Erkenntnisse aus Reihentests (Lookahead-Code, nur noch historisch)
- bounce=2 > 1/3; crv=1.0 optimal; TP2-Puffer 0.20; Anteil 25/75 (Kompromiss WR/R); SL 0.45 robust (Optimum sample-abhängig = Rauschen)
- Trailing: dem festen TP1/TP2 unterlegen (best 0.80: +83.45R vs. +99.73R Baseline alt)
- VA_PCT 1.00 kollabiert (0 Signale); VALLEY_REL Plateau 0.14–0.20; MIN_MOUNTAIN 0–4 identisch

## Regeln
- Keine UI-Tests/Regressionstests; nur `py_compile` + gezielte Logik-Tests in `test/`
- Vektorisierung pur, keine Loops in Strategie (Ausnahme: sequenzieller Signal-Loop ist bewusst, da kausal nötig)
- MT5-Epochs = Berlin-Wanduhr, SQL nutzt strikt `AT TIME ZONE 'UTC'`
- Kommentare/Docstrings Google-Stil; Parameter auf Klassenebene am Dateianfang
- Test-Dateien & Test-DBs gehören in `test/` – **SESSION_HANDOFF.md liegt jetzt auch hier**

## IDEE FUER SPAETER (02.09.2026, User) – KANTENSPEICHER + CONFLUENCE
Alte Kanten sind SEHR wichtig, auch nach Wochen: Sie markieren Liquiditaet,
an der Institutionen reagiert haben. Diese Kanten in einen KANTENSPEICHER
(Level-Gedaechtnis ueber Phasen/Boxen hinweg) aufnehmen und mit CONFLUENCE
bewerten (mehrere historische Reaktionen an derselben Kante = hoehere
Gewichtung). Konzept-Status: gemerkt, noch nicht umgesetzt.
NICHT verwechseln mit Frische-Kanten-Regel (aktuelle Tests): alte Kanten sind
dort als Reclaim-Trigger tabu, im Kantenspeicher aber als Konfluenz-Level wertvoll.

========================================================================
## UPDATE 02.09.2026 – KAUSALE 3-ECK-SEGMENTIERUNG (Prototyp + Befunde)
========================================================================

### GIT-/DATEI-ZUSTAND (WICHTIG, mehrschichtig)
- HEAD = `9b6b28a "Lookahead tests"` (kausale CD=8-Version, committet 09:54).
- INDEX (staged) = Version 7337bfc "Setup B abgeschlossen" (CD=12 + Lookahead
  `vz_full`/`for k in cand`), weil per `git checkout 7337bfc -- file` restauriert.
- WORKTREE (laueft, MASSGEBLICH) = GROSSER REFACTOR, uncommitted (MM):
  Dataclasses (PhaseData/VolumeZone/ReclaimSignal...), Type Hints,
  KAUSALER Signal-Loop (kein finales Screening), ABER CD=12 Default.
  1372 Zeilen. => "BASELINE", die der Prototyp per exec importiert.
  NICHT eigenmaechtig committen/resetten - mit User klaeren.
- PNG/TXT des Hauptskripts ebenfalls modified/untracked.

### test/ BEREINIGT (02.09. frueh): 69 Dateien geloescht. Verbleibend:
SESSION_HANDOFF.md, test.py, test_diag_3eck_v6(_chart/_v7_vmove).py,
test_diag_box_persistenz.py, test_diag_volumen_zone.py,
test_sweep_kausal_reopt.py, test_validate_2025_kausal.py,
test_kausal_box_reife.py  <== NEU (Prototyp),
tmp_diag_check_0700/p7p8/sl_kante/sl_kante_rel/struktur_regel/trade_p7.py,
tmp_phasen_volumen_profil_v2.py.
- CSV erzeugt: scripts/silver_m15_ohlc_2026-08-10_2026-08-28.csv (ts,open,
  high,low,close,tick_volume; 1288 Bars; exakt Hauptskript-SELECT).

### PROTOTYP test_kausal_box_reife.py (kausale 3-Eck-Regel)
- User-Regel: Neue Phase braucht 3 Eckpunkte (H-L-H/L-H-L, |p1-p3|<=0.30,
  Weite >=1.5%), NUR Kanten ausserhalb der alten Box (STRICT).
  Nicht reif = ARM -> merge an offene Box. Kausal (sequentiell, keine Loops
  mit Endlos-Risiko; MAX_BARS_DEFAULT=6000, S2 nur mit --force).
- Import: exec des Hauptskripts bis "reclaim_signals: List[ReclaimSignal]"
  (cut), Namespace als Modul in sys.modules registrieren (Dataclass-Fix).
- CLI: --tol-kante= --weite-pct= --start= --ende= --force --v6 (ohne
  Aussen-Filter) --ab-reife=0|1 --max-arme=N --max-span-days=N
  --kanten-alter-bars=N.
- Vergleich laeuft: Baseline + Boxen-Varianten (setup B auf Boxen).
- t_reif (Reifezeitpunkt) als Signal-Untergrenze implementiert (Zone laeuft
  ab Box-Beginn), Default AB_REIFE=True.

### ERGEBNISSE (kausal, CD=12, Setup B)
Fenster | Variante            | Sig | WR  | Summe R
AUG     | Baseline            | 27  | 44% | +24.97R
AUG     | STRICT (Boxen)      | 31  | 48% | +47.00R   (= v6; Tripel liegen aussen)
AUG     | +Cap 8Arme/14T      | 31  | 48% | +47.00R   (August-Boxen eh klein)
AUG     | +Cap +Frische 96    | 26  | 50% | +38.53R
S1      | Baseline            | 201 | 44% | +197.26R
S1      | STRICT uncapped     | 162 | 28% | +148.85R  (Riesen-Box B21: 30 Ph/47T)
S1      | v6 uncapped         | 218 | 33% | +204.21R
S1      | STRICT + abReife    | 134 | 23% | +97.35R   (schneidet Gewinner ab)
S1      | STRICT + Cap(8/14)  | 209 | 32% | +184.09R  <== Cap repariert S1
S1      | +Cap +Frische 96    | 181 | 35% | +192.50R  (avg R 1.06)

### BEFUNDE / INTERPRETATION
1. v6 reproduziert August exakt Handoff-Boxen (B1=P1, B2=P2-P8 reif 11.08
   04:45, B3=P9-P12 reif 24.08 04:30). STRICT = v6 auf August.
2. Kernproblem S1 = UNBEGRENZTER Arm-Merge -> Riesen-Boxen (B21 30 Phasen,
   24.06-10.08, Box 64.38/54.88 = 10 USD) -> -1R-Reclaim-Longs in Trends.
3. LEBENSDAUER-CAP (8 Arme ODER 14 Tage) repariert S1 (148.85->184.09R),
   laesst August unangetastet (+47R). => Cap-Regel ist der Erfolgsfaktor.
4. FRISCHE-KANTE (Alter<=96 Bars) hilft S1 (+8R, avg 1.06), kostet aber
   August 8.5R. ZWEISCHNEIDIG. Beachte User-Idee (s.u.): alte Kanten sind
   NICHT tabu, sondern wertvoll -> Kantenspeicher-Ansatz statt hartem Filter.
5. abReife (t_reif) ist KONTRAproduktiv (eliminiert profitable Frueh-Signale).
6. S2 (2025) noch NICHT validiert (21.624 Bars, --force noetig, ~6-10 min).
7. Muster wiederholt sich: August stark, S1 schwach => OOS-Vorsicht. Aber Cap
   ist der erste Hebel, der S1 deutlich repariert.

### UPDATE 02.09.2026 (SCHRITT 1 ERLEDIGT) – v6 + LEBENSDAUER-CAP GETESTET
- Aufruf: `test_kausal_box_reife.py --v6 --max-arme=8 --max-span-days=14 --ab-reife=0`
- **Reproduktions-Hinweis:** Die Referenztabelle oben wurde mit `--ab-reife=0`
  erzeugt (AB_REIFE=True Default schneidet Frueh-Signale ab, KEIN Vergleichsmodus).
- Reproduktion bestaetigt: AUG v6+Cap = 31 Sig/48%/+47.00R (exakt), S1 v6 uncapped
  = 218 Sig/+204.21R (exakt).
- **NEU: v6 + Cap(8/14) auf S1 = 221 Sig/34%/+217.44R** → beste S1-Variante:
  uebertrifft v6 uncapped (+204.21R), STRICT+Cap (+184.09R) und Baseline (+197.26R).
- August unveraendert +47.00R (kleine Boxen, Cap greift nicht).
- avg R +0.98 (identisch zu Baseline), mehr Signale durch Boxen-Verschmelzung.

### OFFENE PUNKTE / NAECHSTE SCHRITTE
1. ~~v6+Cap testen~~ **ERLEDIGT** – v6+Cap(8/14) = +217.44R S1 / +47.00R AUG (oben).
2. ⏳ **Cap-Parameter-Sweep** (Arme 6-12, Span 10-21 Tage) auf S1 – LAEUFT 02.09.
3. Danach S2 (2025) validieren (--force).
4. Mgl. Konflikt Frische-Kante vs. Kantenspeicher-Idee aufloesen.
5. Uebernahme ins Hauptskript NUR nach User-Freigabe (Regel!).

### UPDATE 02.09.2026 (SCHRITT 2 ERLEDIGT) – CAP-SWEEP AUF S1 (v6, AB_REIFE=False)
- Sweep-Skript: `test/test_sweep_cap.py` (importiert Prototyp-Funktionen, kartes.
  Produkt ueber --arme=/--span=, 1x Laden + je Kombi Boxen+Signale, ~50-80s/Kombi).
- Grid S1 (2026-02-05..2026-08-28): Arme {6,8,10,12} x Span {10,14,18,21}
  (Tage), danach Feinsweep Span 6-14 + Arme {7,9} um den Knie-Punkt.

**Ergebnis S1 (Summe R):**
| Variante          | Sig | WR  | Summe R |
|---|---|---|---|
| v6 uncapped       | 218 | 33% | +204.21R |
| v6 + Arme8/Span14 | 221 | 34% | +217.44R |
| **v6 + Span10 (Arme 8-12)** | **220** | **35%** | **+228.41R** |

Span-Feinsweep bei Arme=8 (S1):
| Span Tage | Sig | WR  | Summe R |
|---|---|---|---|
| 6  | 229 | 35% | +191.28R |
| 7  | 220 | 34% | +173.73R |
| 8  | 221 | 32% | +165.07R |
| 9  | 219 | 34% | +185.82R |
| 9.5 | 220 | 34% | +184.82R |
| **10** | **220** | **35%** | **+228.41R**  <== Peak |
| 10.25 | 220 | 35% | +228.41R |
| 10.5 | 221 | 35% | +227.41R |
| 11 | 221 | 35% | +227.41R |
| 12 | 221 | 35% | +227.41R |
| 13 | 221 | 34% | +217.44R |
| 14 | 221 | 34% | +217.44R |

Arme-Sweep bei Span=10 (S1): Arme 6->+217.67R, 7->+217.17R, **8/9/10/12->+228.41R**
- Arme >=8 sind bei Span=10 NICHT bindend (Cap greift zuerst ueber die Spanne).

### BEFUNDE / INTERPRETATION (SCHRITT 2)
1. **SPAN-CAP ist der eigentliche Erfolgsfaktor**, nicht die Arme-Zahl: Bei
   Span>=13 bindet fast kein Arm-Cap mehr (arme=10/12 uncapped-identisch +204R).
2. **Optimum Span=10 Tage** (Plateau 10.0-10.25, danach 10.5-12 minimal
   schwaechere +227R). Knie-Punkt klar zwischen 9.5 (+184R) und 10 (+228R).
3. Arme-Zahl: >=8 noetig; 8 als Default sicher (bei kleineren Spannen greift
   der Arm-Cap als zweite Sicherung).
4. Neue S1-Referenz: **v6 + MAX_ARME_PRO_BOX=8 + MAX_BOX_SPAN_DAYS=10
   = 220 Sig / 35% / +228.41R / avg +1.04** (vs. Baseline 201/+197.26R).
5. August-Kontrolle unveraendert: Cap greift dort nicht (Boxen klein),
   +47.00R reproduziert.
6. OOS-Vorsicht bleibt: Optimum auf S1 bei 10 Tagen koennte Sample-spezifisch
   sein. S2-Validierung (2025) ist der naechste Test.

### OFFENE PUNKTE / NAECHSTE SCHRITTE (Stand nach Schritt 2)
1. ~~v6+Cap testen~~ **ERLEDIGT**.
2. ~~Cap-Parameter-Sweep~~ **ERLEDIGT** – Optimum **Arme=8 / Span=10 Tage**
   = +228.41R S1 (220 Sig/35%/avg 1.04). Sweep-Skript `test/test_sweep_cap.py`.
3. ⏳ **S2 (2025) validieren** mit v6+Cap(8/10) UND v6+Cap(8/14) zum Vergleich
   (`test_kausal_box_reife.py --v6 --max-arme=8 --max-span-days=10 --ab-reife=0
   --start=2025-01-01 --ende=2025-12-01 --force`, ~6-10 min).
4. Mgl. Konflikt Frische-Kante vs. Kantenspeicher-Idee aufloesen.
5. Uebernahme ins Hauptskript NUR nach User-Freigabe (Regel!).

### UPDATE 02.09.2026 (SCHRITT 3 ERLEDIGT) – S2-OOS-VALIDIERUNG v6+CAP
- S2 = 2025-01-01..2025-12-01, 21.624 Bars, CD=12 (Prototyp-Import = Worktree).
- Laeufe: v6+Cap(8/10) und v6+Cap(8/14), jeweils --ab-reife=0 (Vergleichsmodus).

**3-Fenster-Gesamtbild v6+Cap:**
| Fenster | Variante | Sig | WR  | Summe R |
|---|---|---|---|---|
| AUG | Baseline | 27 | 44% | +24.97R |
| AUG | v6+Cap(8/10) | 31 | 48% | **+47.00R**  (+22R vs. Baseline) |
| S1  | Baseline | 201 | 44% | +197.26R |
| S1  | v6+Cap(8/10) | 220 | 35% | **+228.41R** (+31R vs. Baseline) |
| S1  | v6+Cap(8/14) | 221 | 34% | +217.44R |
| S2  | Baseline | 210 | 35% | **+99.88R** |
| S2  | v6+Cap(8/10) | 242 | 29% | **+65.34R**  (-35R vs. Baseline!) |
| S2  | v6+Cap(8/14) | 231 | 29% | **+89.06R**  (-11R vs. Baseline) |

### BEFUNDE / INTERPRETATION (SCHRITT 3)
1. **NICHT OOS-robust.** v6+Cap gewinnt in August (+22R) und S1 (+31R), verliert
   aber in S2/2025 deutlich (-35R bei span=10, -11R bei span=14) gegen Baseline.
   Dasselbe Overfit-Muster wie Kante-SL und Struktur-Regel zuvor.
2. **span=10 (S1-Optimum) ist auf S2 am schlechtesten** (+65R). Das S1-Optimum
   ist sample-spezifisch. span=14 ist auf S2 naeher an Baseline (+89R), bleibt
   aber unter ihr.
3. Ursache S2-Schwaeche: Boxen-Verschmelzung erzeugt MEHR Signale (242 vs. 210),
   aber mit deutlich schlechterer WR (29% vs. 35%) und avg R 0.27-0.39 vs. 0.48.
   Die Verschmelzung verdichtet Verlust-Signale in 2025-Trendphasen.
4. **Fazit: KEINE Uebernahme ins Hauptskript.** Baseline-Segmentierung bleibt
   die robusteste Variante ueber alle 3 Fenster (positiv, hoechste S2-Summe R).
5. Der 3-Eck-Reife-Mechanismus ist damit als Allein-Hebel verworfen - wie zuvor
   Kante-SL und Struktur-Regel. August-Verbesserungen reproduzieren sich nicht OOS.

### OFFENE PUNKTE / NAECHSTE SCHRITTE (Stand nach Schritt 3)
1. ~~v6+Cap testen~~ **ERLEDIGT** (S1 +228R, aber s.u.).
2. ~~Cap-Parameter-Sweep~~ **ERLEDIGT** (Optimum span=10 nur auf S1).
3. ~~S2 (2025) validieren~~ **ERLEDIGT** – v6+Cap NICHT OOS-robust
   (S2: +65R span10 / +89R span14 vs. Baseline +99.88R). Verworfen.
4. ⏳ **Weiteres Vorgehen mit User klaeren** – moegliche Richtungen:
   a) Segmentierung als Hebel verwerfen (wie Kante-SL/Struktur-Regel), Fokus
      wieder auf Signal-/Parameter-Optimierung der Baseline (CD=8 etc.).
   b) Boxen-Idee NUR fuer August-Sonderfaelle (P7/P10-P12) gezielt nachbauen.
   c) Kantenspeicher+Confluence-Idee (User, 02.09.) als naechstes Konzept.
5. Uebernahme ins Hauptskript NUR nach User-Freigabe (Regel!).

### IDEE (02.09., User) - KANTENSPEICHER + CONFLUENCE [fuer spaeter]
Alte Kanten sind SEHR wichtig, auch nach Wochen: Sie markieren Liquiditaet,
an der Institutionen reagiert haben. Diese Kanten in einen KANTENSPEICHER
(Level-Gedaechtnis ueber Phasen/Boxen hinweg) aufnehmen und mit CONFLUENCE
bewerten (mehrere historische Reaktionen an derselben Kante = hoehere
Gewichtung). Status: gemerkt, NICHT umgesetzt. NICHT verwechseln mit
Frische-Kanten-Regel (dort tabu; im Speicher wertvoll).

### ENTSCHEIDUNGEN 02.09. (ABEND, User) – STRATEGIE, KONZEPT-c, AUFRAEUMUNG
1. **(b) GESTRICHEN:** KEINE Boxen-/Sonderregeln fuer August-Sonderfaelle
   (P7/P10-P12). Kein ex-post-Flicken einzelner Fenster.
2. **(a) STATUS QUO:** Baseline (Segmentierung + SL vom Entry) bleibt
   unveraendert = robusteste Variante ueber alle 3 Fenster. Baseline wird NIE
   direkt veraendert; Simulationen/Experimente laufen NUR auf Arbeitskopien.
   Worktree-Hauptskript `scripts/tmp_phasen_volumen_profil.py` ist massgeblich,
   NICHT eigenmaechtig committen/resetten (mit User klaeren).
3. **(c) ZU DEFINIEREN – KANTENSPEICHER + CONFLUENCE** (naechstes Konzept).
   User-Bausteine fuer die Definition (02.09.):
   - **Zeitliche Abklingung:** wie altern Kanten-Touches? Decay-Gewichtung.
   - **Alte Peaks im Gegenlauf:** fruehere Hochs/Tiefs, die der Preis in der
     Gegenbewegung erneut testet, einrechnen.
   - **Volumenabgleich:** Reaktion an der Kante nur mit Volumen-Bestaetigung.
   - Confluence = mehrere historische Reaktionen an derselben Kante => hoehere
     Gewichtung. LEHRE aus Struktur-Regel: als WEICHES Ranking/Scoring bauen,
     NICHT als harter An/Aus-Filter (harte Filter entfernen profitable Signale).
   - Konzept gleich 3-Fenster-validierbar bauen (AUG/S1/S2), NICHT erst auf
     August/S1 tunen (Lehre aus v6+Cap: S1-Optimum war S2-schwach).
   - Abgrenzung: Frische-Kanten-Regel (alte Kante = tabu als Reclaim-Trigger)
     vs. Kantenspeicher (alte Kante = wertvolles Konfluenz-Level) -> Konflikt
     muss im Konzept aufgeloest werden.
4. **AUFRAEUMUNG 02.09. (ERLEDIGT):**
   - `test/` entruempelt: 14 veraltete Diagnose-/Prototyp-Skripte + Prototyp-CSV
     nach `test/archiv/` verschoben (3-Eck/Boxen, SL/Struktur, Zonen-Diagnose,
     v2-Helper, silver-csv).
   - Verbleibend aktiv in `test/`: SESSION_HANDOFF.md, test.py,
     test_sweep_kausal_reopt.py, test_validate_2025_kausal.py.
   - `scripts/`: nur noch init_*/migrate_*, `tmp_phasen_volumen_profil.*`
     (Hauptskript), `tmp_phasen_move_m15.*` (Setup-C-Referenz).
   - Baseline-Skript unangetastet (MM-Stand).

### OFFEN / NAECHSTE SESSION (nach 02.09.)
- c-Konzept ausdefinieren (Punkte oben) und als Testskript in `test/` bauen
  (Arbeitskopie-Basis, 3-Fenster-Validierung von Anfang an).
- Danach optional: restliche Parameter (TOL, VA_PCT, SL_PCT, TP2_PUFFER,
  ANTEIL_TP1) auf kausalem Code nachvalidieren – NUR auf Arbeitskopie.
- Setup A (Counter-Trend-Reversal) weiterhin spaeter; Setup C (--moves=1)
  mit Trailing optional testen.

---

## Wiederaufnahme 2026-09-10 — v0.20 Baseline und H2-Vorbereitung

> **Präfix.** Der Kopf dieses Dokuments erklärt es zum 02.09.2026 für
> eingefroren. Dieser Abschnitt ist **append-only**; die Historie oben bleibt
> unverändert (Beschluss E7 / Option b).

### Stand (nach Commit `7b9963f`)

| Gegenstand | Wert |
|---|---|
| Addendum | v0.20 / §70 in `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` (`da396a1a…`, 164.207 B) |
| Adapter | `backtest_lab/phasen_regime_adapter.py` `0f3f8765…` (25.783 B) |
| Engine | `test/tmp_kanten_engine_replay.py` `ea2f72a8…` (196.012 B, gitignored → urkundlich) |
| Renderer (vor Auflagen) | `test/tmp_png_aug_sichttest.py` `c730b287…` (73.845 B) |
| Baseline v0.20 | **V015 = 18 Trades / +64,879080 R** (H1 8/+38,964262 bit-fest · H2 10/+25,914818) |
| G4-Treffer | K77@1002 · entry 68.5070 · SL 68.2580 · POC 68.9513 (Anker 848) · TP2 69.8700 → **+3,629016 R** |
| H1-Anker | `d9f35876…` / 899.249 B in V01, V014 **und** V015 |

### Nächster Auftrag — H2-Marktanalyse (Phase P10 ab Bar 1021)

Marktanalyse der H2-Expansion vor der Auflagenkosmetik. Die offenen Auflagen
A-1 … A-4 sind Chart-Hygiene und blockieren die Analyse nicht.

### Auflagen A-1 … A-4 — Beschlüsse E1 … E11 (Grundlage §71)

| # | Beschluss |
|---|---|
| E1 | Rotes Sweep-Kreuz (§32) → Diamond `d`; violettes Q29-`x` (§54.2 R7) bleibt. |
| E2 | **Panel-02-Ausnahme analog A-5**: `LEG_BASIS` + `SWEEP_MARKER_P02="x"` eingefroren → H1-Anker intakt. |
| E3 | V01/V014 bleiben **bit-identisch**; alle Korrekturen nur bei `KONF.auflagen_aktiv`. |
| E4 | Panel 04: 8 Ticks `range(850, 1050, 25)`; C04-7 wird für V016 neu gefasst. |
| E5 | A-3-Offsets: `(1020,67) → (0,-18)`, `(980,67) → (0,22)`; Bars < 640 im Default. |
| E6 | A-4: Zonenlabel `y=0.92` (Axes, `get_xaxis_transform`); P04-Text `(0.82, 0.94)` transAxes. |
| E7 | Dieser Append-Abschnitt. |
| E8 | Neuer Satz **V016** mit eigenem Präfix `aug_sichttest_v016_`; v015 bleibt arretiert. |
| E9 | A-3-Restkollision (Override-Boxen, G4-Label): erst Sichtprüfung, dann nachjustieren. |
| E10 | `Luecke BLOCKIERT` bleibt auf dem Bestandsplatz. |
| E11 | Auflagen-Gate ist das **neue Feld** `auflagen_aktiv` (nicht `g4_aktiv`) — sonst wäre V015 nicht mehr reproduzierbar. |

### Offen nach diesem Schritt

Addendum **v0.21 / §71** (Renderer-Auflagen, Präfix-Schnitt v015/v016,
Erratum E-5 zur Altsatz-Garantie). Sichtprüfung des V016-Satzes durch den
Anwender; A-3-Nachjustierung erst danach.

### V016-Arretierung und Auflagenabschluss (2026-09-10)

Sichtprüfung durch Anwender erfolgreich abgeschlossen (VOTUM: OK).

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/tmp_png_aug_sichttest.py` | `ca0db364f6955c29c103e10e16935428115cc47c8a937c86df2d6431791cd3e3` | 79.314 B |
| `test/aug_sichttest_v016_01_gesamt.png` | `1ac695a40ed0241f0db135e6c1dd8f303b32a17ab4c42d6b5193ed7abf25ac10` | 2.117.515 B |
| `test/aug_sichttest_v016_02_h1_box.png` | `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04` | 899.249 B |
| `test/aug_sichttest_v016_03_h2_phasen.png` | `81cae5e376cd9d7dd76597b3a941c3d1bd2358fadb258eb734dca85f7df11b72` | 1.760.655 B |
| `test/aug_sichttest_v016_04_p9_regime.png` | `b18e2a55d83368d0436a2fa00357ce3aa69a93ee8326641dfbd555828a6edccc` | 1.210.084 B |
| `test/aug_sichttest_v016_05_kantenkarte.png` | `00d56362423941f9d794d837313052d24d8a94fcd517b9b529de0dc7cb299b9f` | 2.122.100 B |
| `test/tmp_png_aug_sichttest_v016_out.txt` | `2969723c6abb9b8f97512a84d15ff3e95fecb91398cdc72b4195c98b113578d7` | 5.520 B |

H1-Regressionsanker `d9f35876…` (899.249 B) über alle 4 Generationen (V01, V014, V015, V016) byte-identisch verifiziert.

**Benchmark V016:** 18 Trades / +64,879080 R (H1 8 / +38,964262 · H2 10 / +25,914818).
Auflagen A-1 … A-4 sind damit abgeschlossen; Beschlüsse E1 … E11 und die Errata
E-5 / E-11 / E-12 sind in Addendum **v0.21 / §71** der Adapter-Spez dokumentiert.

**Wichtig (Erratum E-12):** V014 Panel 03 ist seit v0.20 **nicht mehr**
byte-identisch zu v0.17 — in der v0.20-Statistikzeile `_p9z` wurde die
`QUARTETT_R`-Trennung nicht auf den G4-Modus gegatet. Historischer Hash
`a055b243…` (1.695.409 B, gültig v0.17–v0.19) ist ab v0.20 überholt; aktuell
`f8505d124c3dddf3…` (1.694.382 B). V01 und V015 sind davon **nicht** betroffen
(je 5/5 byte-identisch). Nicht neu arretiert.

---

## Einbrand 2026-09-10 — Engine-Generation V017 (Addendum v0.22 / §72)

### Was passiert ist

Die Kanten-Knick-Forensik hat gezeigt: die kausale Kantenlinie ist die
**institutionelle Liquiditätsgrenze**, nicht der Mittelwert der Dochte. Die
Engine wurde daher auf **Regel F** umgestellt und eingebrannt.

**Die gesamte Änderung ist EIN Hunk** (+3/−1) in `_SEEdgeH.basis_bei` (Z. 2118):

```diff
-        return float(np.mean(px)) if px else self.basis
+        if px:
+            return float(min(px) if self.seite == "OBEN" else max(px))
+        return float(self.wicks[0][1])
```

Der dritte Teil heilt zugleich den **M6-Look-ahead** (`k = erster_pivot_bar + 1`
fiel auf das End-Mittel = Zukunft zurück). Die Heilung ist **handelsneutral**,
korrigiert aber einen journalierten Wert kausal: M6-Blocker Bar 658 meldet
`K48 62.562` → **`62.577`** (erster bekannter Docht).

### Sollwerte V017

| Kennzahl | V016 | **V017** |
|---|---|---|
| V0 / R0 | 14 / +40,445143 | **14 / +42,450970** |
| V1_basis / R_B | 15 / +46,866348 | **14 / +47,815697** |
| **V1_aktiv / R1** | 18 / +64,879080 | **17 / +65,835576** |
| **H1** | 8 / +38,964262 | **7 / +39,919584** |
| H2 | +25,914818 | **+25,915992** |
| P9-Regimebeitrag | +23,433938 | **+23,435111** |
| Delta (R1 − R_B) | +18,012732 | **+18,019879** |
| Quartett-R | +19,804922 | **+19,806095** |
| G4 `K77@1002` | +3,629016 | **+3,629016** (bit-identisch) |
| Niveauwechsel sichtbar | 205 | **66** |
| Linien mit Netto-Preiswechsel | 54 | **41** |
| Sperr-Marker Q29 / M6 | 57 / 23 | **69 / 24** |
| lebende Kanten | 59 + 14 = 73 | **59 + 14 = 73** |

**H1-Entries V017:** 231, 245, 399, 491, 510, 531, 565.
Entfallen gegenüber V016: `K8@383` (−0,401786), `K16@492` (−0,482566),
`K8@620` (−1,000000); neu: `K16@490`, `K16@509`. Die fünf gemeinsamen Trades
wandern im R mit den Kantenpreisen.

**H2-Quartett:** K67@903 +4,119775 · K67@980 +9,987676 · K73@981 +2,695488 ·
K67@1020 +3,003157 = **+19,806095** (K67-Anteil +17,110608).

### P-1 · P-2 · P-3 (Renderer-Beschlüsse)

| # | Umsetzung |
|---|---|
| P-1 | `--probe-praefix` **ERSETZT** das Präfix (`PRAEFIX = PROBE_PRAEFIX or KONF.ausgabe_praefix`), 5 PNG-Stellen + Protokollpfad |
| P-2 | Engine-Kennung und Niveauwechsel-Zeile strikt `if _V17:` gegatet — **vorher ungated** und damit Eingriff ins V016-Protokoll; nach der Gatelung wieder `2969723c…` / 5.520 B |
| P-3 | Neues Feld `netto_preiswechsel_baseline`; Wortlaut: `Linien mit Netto-Preiswechsel: 41 (Baseline 54) \| Niveauwechsel gesamt: 66 (Baseline 205)` |

`--mode`-Default bleibt **V014**; V017 nur explizit.

### Artefakte und Arretierung

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` (**neu**) | `4a3567659990586cb507f51e10575bdc9b64d82745523034c206b188e19f7298` | 196.083 |
| `test/_tmp_backup_engine_pre_v017.py` (Vorgänger) | `ea2f72a8de81d632909da72d79b158b0760e6dfc05c6c9047559a4fbf7d437a5` | 196.012 |
| `test/tmp_png_aug_sichttest.py` (**neu**) | `3d6a4788788375576ce37e4658598d4d0b7cbf8b44bb48e087d3185cef656c1e` | 92.915 |
| `test/_tmp_backup_renderer_pre_v017.py` (Vorgänger) | `ca0db364f6955c29c103e10e16935428115cc47c8a937c86df2d6431791cd3e3` | 79.314 |
| `backtest_lab/phasen_regime_adapter.py` (unverändert) | `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` | 25.783 |
| `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` (§72, getrackt) | `73cd8924980cf1a394106f3ed257185958b856be401a134054c32f3ab4486a33` | 196.078 |

> Die Spez-Hash ist **Blob- und Worktree-Hash zugleich** (beide `73cd8924…`,
> LF, 3.951 Zeilen) und damit unabhängig von `core.autocrlf=true`. Vorsicht
> bleibt geboten: nur `docs/artefakte/aug_p11/**` ist in `.gitattributes` per
> `-text` geschützt — für die Spez liegt der Anker im **Blob**, der Worktree
> könnte bei einem frischen Checkout CRLF erhalten.

**Produktionssatz V017** (`aug_sichttest_v017_01..05.png`)

| Panel | SHA256 | Bytes |
|---|---|---|
| `01_gesamt` | `550091f5359df47b7868e13bd1f1b734cb0c17e2e3109b30e53bd9aedf43010e` | 2.071.320 |
| `02_h1_box` | `42427164f88f9e93513d724eb7822b46d711c3ce990e5592f5bd220dd7250a2b` | 874.523 |
| `03_h2_phasen` | `85926341eb86c84d60a9e2e6edebce489e2198a5c498b6aecf13b4c6898612dd` | 1.717.237 |
| `04_p9_regime` | `b53095565c4d4fdd7b758d40b469ac3fa085a0e80188d9807d69c54171738842` | 1.195.065 |
| `05_kantenkarte` | `91c8dd6164f4410b1b9009728e9ff8a0b2ca74f26718123018df90602892b5f1` | 2.069.665 |
| Protokoll `tmp_png_aug_sichttest_v017_out.txt` | `866308081f94f2311337547ba32e1968f72ec4bef13b021658ca35e3889b4750` | 5.044 |

**Zero-Trust-Probesatz** (prä-Einbrand, Kandidaten-Engine): `probe_v017_01..05.png`
(`8aa8d690…` / `42427164…` / `6a74f186…` / `d4b85aa5…` / `6777deeb…`) und
Protokoll `_tmp_probe_v017_out.txt` `996ef9ab…` / 4.960 B. Nur Panel 01/03/04/05
differieren zum Produktionssatz — sie nennen den **Engine-Dateinamen**;
Panel 02 ist in beiden Sätzen bit-identisch (`42427164…`).

### Errata

- **E-13 (neu): Altsatz-Garantie geöffnet.** `K73@1020` existiert in V017 schon
  im v0.1-Referenzlauf nicht mehr → `REFERENZ` schrumpft auf `(980, 73)`.
- **E-14 (neu): V01-Protokoll ist historisch.** `test/tmp_png_aug_sichttest_out.txt`
  (9.784 B) ist ein **Konsolen-Mitschnitt in UTF-16 LE** mit dem Wortlaut der
  v0.1-Ära. Kein Reproduktionsartefakt; die V01-**PNGs** sind 5/5 bit-identisch.
- **E-12 bleibt**: V014 Panel 03 (`f8505d12…` / 1.694.382 B) — per A/B-Test
  belegt, dass P-1…P-3 das **nicht** verursacht haben.

### Generationsbindung — Fail-Loud und Rückweg (WICHTIG)

Nach dem Einbrand tragen V01 … V016 **nicht mehr** mit der ausgelieferten
Engine. Das ist gewollt und fail-loud, **nicht** still:

```text
python test/tmp_png_aug_sichttest.py --mode V016
AssertionError: (14, 42.450969915773506)      # Z. 639, erster Assert, keine PNG
```

Rückweg (erprobt, 5/5 PNG je Modus byte-identisch):

```text
python test/tmp_png_aug_sichttest.py --mode V016 ^
    --engine test/_tmp_backup_engine_pre_v017.py
```

`--engine` akzeptiert ausschließlich Pfade innerhalb `test/`.

### Verifikation (gezielt, keine Regressionstests)

`py_compile` OK · Assert-Parität 5/5 Modi OK · V015 und V016 Satz **und**
Protokoll byte-identisch (`b7c4142a…` / `2969723c…`) · V01 5/5 PNG identisch ·
A/B-Neutralität P-1…P-3 belegt · Rückweg V01/V016 belegt · G4 bit-identisch ·
73 Kanten-IDs stabil · M6-Heilung isoliert (A/B/C) · H1 V016↔V017 direkt
verglichen.

### Offen

1. **`test/` ist gitignored** (`.gitignore:63`): nur **diese Datei** ist
   getrackt; Engine, Renderer, Backups, PNG und Protokolle sind untracked →
   Arretierung **urkundlich über SHA256**, **kein** `git add -f`.
2. `SWEEP_MARKER_P02` weiterhin deklariert, nicht referenziert (§71.7).
3. E-12 nicht neu arretiert.
4. **Nächster Auftrag:** H2-Marktanalyse (Phase P10 ab Bar 1021) — unverändert.

---

## Exploration 2026-09-10 — H2-Reststrecke, Zeitbasis-Forensik, Phasen-Versatz

> **Supersedes:** `### Offen` Punkt 4 („Nächster Auftrag: H2-Marktanalyse") —
> Exploration **erledigt**, **Entscheidungen offen**. Abschnitt ist
> **append-only**; nichts oberhalb wurde verändert.

**Invarianten (Worktree clean, HEAD `f181b64`):** Engine
`4a3567659990586c…` / 196.083 B · Renderer `3d6a478878837557…` / 92.915 B ·
Adapter `0f3f8765b1682910…` / 25.783 B. **Keine Projektdatei geändert.**
Alle Nachweise read-only (Wegwerf-Skripte in `test/`, gitignored).

### N1 Grundbefund — letzter Signal-Bar 1020

Produktions-Trace (Instrumentierung des im Renderer erzeugten `patched_src`,
Original-Namespace; Inertheit 17 / +65,835576 belegt):

| Lauf | Trd | R1 | letzter Signal-Bar |
|---|---|---|---|
| V0 ungepatcht | 14 | +42,450970 | K67@1020 |
| V1_basis (v0.1) | 14 | +47,815697 | K67@1020 |
| V1_aktiv (V017) | 17 | +65,835576 | K67@1020 |

Nach Bar 1020 existiert **kein Motor-Signal** — Zielzone 1021..1287 durchgehend
vakuumiert (siehe N4).

### N2 Sperrkette der vier avisierten Trades

| Trade | Bar | Bruchpunkt |
|---|---|---|
| K73 Short 26.08. 04:30 | 1122/1123 | `kd=K73` (69,6380, +0,10195 %) → **M6-Blocker K67** 69,8990, Abstand 0,3748 % ≤ 0,75 %; Q29 hätte 3,905 % → Vakuum |
| K82 Long 25.08. 15:00/15:45 | 1072/1073 | K82 nur 2 Dochte (< `min_touches_handelbar 3`) → Kandidat K62 → **Q29-SPERRE** (65,94/66,29 % vs. 25 %) |
| K82 Long 26.08. 17:00 | 1172 | K82 im Schlaf-Fenster [1074, 1174); Pool {K48,K3,K17,K63,K60}; K63 V-S≥3, K60 Überdehnung 0,7076 % > 0,60 % → `kd=None` |
| K82 Long 27.08. 15:45 | 1259 | K82 wach, Basis 67,5530 → dist −0,0696 % < 0 → `_kandidat=None` |
| K73 3. Docht | 1211 | K73 dist −0,0388 % → None |
| K73 4. Docht | 1272 | `kd=K73` → M6-Blocker K67 wie #1 |

Schlaf-Mechanik `_se_scan` Z. 2204–2208 / 2266–2279: `_akzeptiere` schließt
Fenster auf `bar+2`; K82 `[(1074,1174)]`, an Bar 1173 `_existiert`=True, aber
`_lebt`=False.

**Erratum E-15:** Vorübergabe-Notiz „1172/1259 sind **nicht** Q29-gesperrt"
ist falsch — der Q29-Log führt nur Bars bis zum Kandidaten. Beide enden schon
in `_kandidat`, sind aber zusätzlich Q29-gesperrt (66,37 % / 67,79 %).

### N3 Zeitbasis-Befund (Entscheidung offen)

**Symptom:** `d["ts"]` liegt +2 h gegen die Broker-Kerzen (7/7 Marken).

- Spalte `ohlcv_bars.time` = **TIMESTAMP WITH TIME ZONE**; DuckDB-Session-TZ
  = `Europe/Budapest` (= Berlin).
- Engine `_lade_fenster` Docstring Z. 592 + Datenvertrag Z. 66–68 verlangen
  `AT TIME ZONE 'UTC'`; SELECT **Z. 600** nutzt `AT TIME ZONE 'Europe/Berlin'`
  (zweite Projektion), WHERE Z. 604 f wieder `UTC`.
- Rohwert K73-Docht `2026-08-26 06:30:00+02:00` → UTC **04:30** = Broker-Kerze;
  Berlin 06:30 = `d["ts"]`.
- Renderer Z. 702–711 verankert Berlin (`AXIS_TZ_OFFSET_H=0`); AGENTS.md
  widerspricht teils und schützt zugleich Z. 600 („Eingefrorene Ausnahme",
  veralteter SHA `3ba15c72…`, veraltete H1-Zahlen `8/+38.964262` aus V016).

| Bar | Broker/Marke | Motor-ts (=Anzeige) | Docht |
|---|---|---|---|
| 1122 | K73 26.08. 04:30 | 06:30 | H 69,7090 |
| 1211 | K73 27.08. 03:45 | 05:45 | H 69,6110 |
| 1272 | K73 27.08. 19:00 | 21:00 | H 69,7140 |
| 1031 | K82 25.08. 04:45 | 06:45 | L 67,5350 |
| 1056 | K82 25.08. 11:00 | 13:00 | L 67,5530 |
| 1072/1075 | K82 25.08. 15:00/15:45 | 17:00/17:45 | L 67,4880 / 67,4200 |
| 1172 | K82 26.08. 17:00 | 19:00 | L 67,4940 |
| 1259 | K82 27.08. 15:45 | 17:45 | L 67,6000 |

**Fix-Kopplung (gemessen):** Z. 600 → `'UTC'` verschiebt `d["ts"]` um −2 h,
**Trades/R unverändert (17 / +65,835576)**, aber `box_end_bar` 640 → **644**
(+4 Bars), H1-Partition 7/+39,919584 → **8/+38,919584**, H2 10/+25,915992 →
6/+3,531386; Kipphebel = Grenztrade `K1 entry_bar 640, r −1,000000`; Muster
stimmt mit AGENTS.md (`8→9`), Zahlen = V016-Generation. Zusatz: H1-Schnitt
lag bisher bei 18.08. 22:00 statt 19.08. 00:00 Wanduhr.

**Erratum:** `docs/reclaim.md` **existiert nicht** (FS und git), wird aber im
Kopf dieser Datei als „Bootstrap, dort zuerst lesen" geführt.

### N4 Phasen-Versatz im Zielbereich (1021..1287 vs. P9)

| Größe | P9 | Ziel | Δ |
|---|---|---|---|
| Oberkante | 70,0000 (@881) | 69,7140 (@1272) | −0,2860 |
| Unterkante | 68,2880 (@1000) | 67,4200 (@1075) | **−0,8680** |
| Bandmitte | 69,1440 | 68,5670 | −0,5770 |
| Bandbreite | 1,7120 | 2,2940 | **+0,5820 (+34 %)** |

Asymmetrisch nach unten. **Kantenzuständigkeit wechselt:** Decke K67 69,8990 →
**K73** 69,6110 (Provenienz 69,6785); Boden K77 68,4130 → **K82** 67,6000 +
**K85** 67,4200 (Einzeldocht @1075 = Monatstief = Erstd­ocht). Neue
Zuständigkeit entsteht aus Erstd­ochten von Extrema → **Regel-Lücke:** ein
V-Extremum ist Einzeldocht, wird erst bei `pivot_bar+2` bestätigt → am Bar
1075 leerer Pool, Wendepunkt strukturell 2 Bars zu spät.

**Zigzag 1021..1287:** 69 bestätigte Pivots (38 H/31 L), 1 je 3,9 Bars, 55
vollständige Schwünge; Median 59 Pips, Max 215, Min 20; ≥0,30 USD 50/55,
≥0,50 35/55, **≥1,00 USD nur 8/55 (15 %)** → `V3_TP_MINDIST_PCT=1,5 %`
(≈1,02 USD) kalibriert dieses feine Zigzag **zu grob**.

**Vakuum-Karte (nur P9):** 0..847 MAKRO · 848..1020 PHASE (P9) ·
**1021..1170 BLOCKIERT** (150 Bars / 37,5 h) · 1171..1272 BLOCKIERT ·
1273..1287 BLOCKIERT. Mit P12 wird 1171..1272 PHASE. Die 4 größten Schwünge
≥1,00 USD bleiben immer gesperrt: 1023→1031 (**2,1490**), 1075→1083 (1,4660),
1116→1122 (1,5260), 1162→1165 (1,0690).

**Motoren-Hebel isoliert** (ohne P12, Zielzone überall 0):

| Variante | Trd | R1 | H1 | H2 |
|---|---|---|---|---|
| IST | 17 | +65,835576 | 7/+39,919584 | 10/+25,915992 |
| V1 M6 nur bei lebender Wand | 18 | +56,960394 | 6/+33,044402 | 12/+23,915992 |
| **V2 Q29 phasenlokal ab 848** | 18 | +64,835576 | **7/+39,919584 (gratis)** | 11/+24,915992 |
| V3 Q29 phasenlokal ab 1021 | 17 | +65,835576 | 7/+39,919584 | 10/+25,915992 |
| V6 V1+V3+Überdehnung 0,80 | 18 | +55,572569 | 6/+33,044402 | 12/+22,528167 |
| V7 V1+V3+0,80+V-S≥2 | 23 | +65,404492 | 7/+32,580278 | 16/+32,824214 |

**P12-Kombinationen (korrekt angehängt):**

| Variante | Trd | R1 | H1 | H2 | Ziel |
|---|---|---|---|---|---|
| IST | 17 | +65,835576 | 7/+39,919584 | 10/+25,915992 | 0 |
| **K1 + P12 (nur Adapter)** | **17** | **+65,835576 (inert)** | 7/+39,919584 | 10/+25,915992 | 0 |
| K2 K1+M6 lebend | 21 | +63,096583 | 6/+33,044402 | 15/+30,052181 | 3 |
| K3 K2+Überdehnung 0,80 | 21 | +61,708758 | 6/+33,044402 | 15/+28,664356 | 3 |
| K4 K3+Q29 aus | 27 | +57,991740 | 11/+30,327383 | 16/+27,664356 | 3 |
| K5 K4+V-S≥2 | 31 | **+68,253054** | 11/+30,292650 | 20/+37,960404 | 3 |

Die 3 Zielzonen-Trades (K2..K5 unverändert): `K76@1211 → entry 1214, STUFE_3,
+5,881508` · `K76@1268 → entry 1269, STUFE_1, −1,000000` · `K73@1272 →
entry 1273, STUFE_1, +1,254682` = **+6,136190 R**.

**H1-Kosten:** M6-Liveness global −6,875182 · Q29 aus global −9,592201 ·
V-S≥2 global −9,626934 · **Q29 phasenlokal ab 848 = 0,000000** → H1 muss
nicht geopfert werden, wenn alles segmentgebunden über Route A läuft.

**Harness-Lehre:** `dataclasses.replace(adapter, segmente=(P9,P12))` ersetzte
das **aktive** `P9_DIRECT_69_87` (Override 69,87) durch override-loses `P9`
→ exakt v0.1 (14/+47,815697); Trace-Diff: Bar 903 `freigabe None → 67`.
**Regel: Segmente ANHÄNGEN (`tuple(a.segmente)+(neu,)`), nie neu bauen**;
Guard `assert seg.decke.hat_override()`.

**Variantenlandkarte:** V-A Segment-Erweiterung P10+P12 (engine-inert, K1;
ohne endogene Fenstererkennung in S1/S2 unbrauchbar) · V-B M6-Liveness
segmentgebunden (+6,136190 R, H1-Kosten 0) · **V-C Q29 phasenlokal (H1-gratis,
H2 −1,000000 — sauberster Kandidat)** · V-D Kantenzuständigkeit endogen (Kern
für S1/S2) · V-E Range-Neubildung · V-F Ziel segment-relativ · V-G arretieren.
**Testbarkeits-Zwang:** P12 (1171..1272) ist Handliste für 08/2026 → in S1/S2
wertlos; eine Phasen-Regel muss den Versatz **endogen** erkennen.
S1 = 2026-02-05..08-28; S2 = 2025-01-01..12-01.

### N5 Offene Entscheidungsfragen (an Anwender)

**Zeitbasis:**
1. Z. 600 → `'UTC'` + Neu-Arretierung als **V018** (`box_end 644`, H1
   `8/+38,919584`, H2 `6/+3,531386`)? Oder Berlin-Anzeige behalten +
   Drei-Spalten-Konvention `Bar | Broker/Kerzen | Anzeige (+02:00)`?
2. AGENTS.md entschärfen: „Wanduhr" durch „**Kerzen-Zeit = `time AT TIME ZONE
   'UTC'`; `Europe/Berlin` = Anzeige-Dublette, nie Rechenbasis**" ersetzen?
3. `docs/reclaim.md`-Erratum korrigieren?
4. PNG-Neuproduktion (V017-Bilder tragen +2-h-Labels)?

**Phasen-Versatz:**
1. Reihenfolge: erst V-C allein (beweist H1-Erhalt) oder direkt
   V-A+V-B+V-C+V-D?
2. Topologie: neues Segment (Adapter) oder neue Motoren-Regel (Engine-SHA neu)
   — oder beides mit klarer Rollentrennung?
3. Vakuum 1021..1170: bleibt die Abwärtsstrecke (größter Schwung) gesperrt?
4. Zwei-Bar-Latenz: Ausnahme von `pivot_bar+2` für neue Einzeldocht-Extreme?
   (berührt H1)
5. `V3_TP_MINDIST_PCT` segment-relativ oder global lassen?
6. Zeitbasis vorziehen (eine Arretierung) oder Phasen-Regel zuerst (zwei)?

Weiterhin offen aus V017-Abnahme: Aufräum-Umfang in `test/`; `--mode
V01..V016` automatisch pinnen oder fail-loud; V01-Protokoll neu als UTF-8
arretieren (E-14); A-3-Nachjustierung (E9) + Sichtprüfung V017-Satz.

### N6 Read-only-Nachweise (alle `test/`, gitignored, nichts geschrieben)

`_tmp_explo_h2rest.py`/`_out.txt` ·
`_tmp_explo_prodtrace.py`/`_prodtr_out.txt` (1.408 Z.)/`_prodtr_report.txt`
(**Kernbeweis**) · `_tmp_explo_schlaf.py` · `_tmp_explo_mikro.py` ·
`_tmp_explo_whatif.py` · `_tmp_explo_p12.py` · `_tmp_explo_laeufe.py` ·
`_tmp_explo_trace_1172_1259.py` · `_tmp_zeitbasis_check.py`/`_check2.py` ·
`_tmp_zeitbasis_kopplung.py` · `_tmp_phasenversatz.py` · `_tmp_vakuum_p12.py` ·
`_tmp_p12_korrekt.py` · `_tmp_p12_diff.py` · `_tmp_hook_diff.py` ·
`_tmp_trace_diff.py` + `_tmp_tracediff_ist/p12.txt`. Wegwerf-Engine
`test/_tmp_engine_v017trace.py` wieder gelöscht.

---

## Einbrand 2026-09-11 — Engine-Generation V018 (Addendum v0.23 / §73) + Zeitbasis-Bereinigung S0–S4

> Antwort auf die **N5-Entscheidungsfragen** (Zeitbasis) aus der Exploration
> 2026-09-10: alle vier sind entschieden und umgesetzt.

### Was passiert ist

Stufenweise Bereinigung der Zeitbasis (SSoT `docs/ZEITBASIS_KANON.md`):

| Stufe | Inhalt | Commit |
|---|---|---|
| S0 | Read-only-Audit (703 Fundstellen / 130 Dateien) | — |
| S1 | Kanon als SSoT, Agents.md bereinigt, Kopf-Errata | `8826639` |
| S2 | Nomenklatur-Sweep „Wanduhr" → BKZ (AST-neutral) | `9b2e585` |
| S3.4 | Inline-Marker „historisch überholt" in 3 Alt-Protokollen | `64fc154` |
| S4 | Peripherie auf BKZ (tz_offset_hours entfernt) | `50912f2` |
| S3 | Engine/Renderer **V018** (Engine in `test/`, gitignored) | urkundlich |

**Antworten auf N5 (Zeitbasis):**
1. **Z. 600 → `'UTC'`** (Weg A) — neu arretiert als **V018**; `box_end` dynamisch
   **644**; der Grenztrade `K1@640` (r = −1,000000) kippt von H2 nach H1.
2. AGENTS.md entschärft — Kanon ist verbindlich.
3. `docs/reclaim.md`-Erratum korrigiert (Datei existiert nicht).
4. **PNG-Neuproduktion verworfen** — V01…V017 bleiben historische Zeitzeugen,
   nur der V018-Satz ist Produktionsreferenz.

### Sollwerte V018 (Adapter v0.1)

| Kennzahl | V017 | **V018** |
|---|---|---|
| V0 (Baseline) | 14 / +42,450970 | 14 / +42,450970 |
| V1_basis | 14 / +47,815697 | 14 / +47,815697 |
| **V1_aktiv** | 17 / +65,835576 | **17 / +65,835576** |
| H1 | 7 / +39,919584 | **8 / +38,919584** |
| H2 | 10 / +25,915992 | **9 / +26,915992** |
| n / box_end | 1288 / 640 | **1288 / 644** |

`K1@640` ist der **einzige** Trade, der die Box-Grenze wechselt (H2 → H1);
Gesamtsummen bit-identisch. **E-15:** H1/H2-Split ist ab V018
generationsgebunden — generationenübergreifende H1/H2-Vergleiche unzulässig.

### Artefakte (SHA-Anker, `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| Engine V018 `tmp_kanten_engine_replay.py` | `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` | 196.649 |
| Backup V017 `_tmp_backup_engine_pre_v018.py` | `4a3567659990586cb507f51e10575bdc9b64d82745523034c206b188e19f7298` | 196.083 |
| Renderer V018 `tmp_png_aug_sichttest.py` | `0d145ef4c5ea0aa9b9b158c00bd54d97bfb1abd68e4a2a32f4e496fcea1f6fc7` | 97.160 |
| Adapter (unverändert) `backtest_lab/phasen_regime_adapter.py` | `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` | 25.783 |
| Protokoll `tmp_png_aug_sichttest_v018_out.txt` | `d0e2ad537e55eed26a902690f95827fb2b5aa20bc82a12fe450bbc1cfa2c1d97` | 5.048 |

Produktionssatz `aug_sichttest_v018_01..05.png`: SHAs und Bytes in
`reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` **§73.7**.

### S4 — Peripherie auf BKZ

`tz_offset_hours` projektweit entfernt; SQL überall `AT TIME ZONE 'UTC'`:

- `algos/chart_engine.py`, `algos/chart_plugins.py` (neu `_EPOCH`/`_epoch_sec`,
  ersetzt 5× `int(...timestamp())`), `signal_lab/quick_look.py`,
  `signal_lab/run_definition.py` (`available_date_range`), `signal_lab/sweep_runner.py`.
- `Notebooks/00_DB_Service.py`, `01_Chart_Inspector.py`, `02_Signal_Lab.py`.
- `backtest_lab/db.py`: neue **öffentliche Anzeige-Dublette** `to_display_bp(series)`
  (delegiert an `_fmt_wallclock_series`); `_to_utc_naive()` als BKZ-Garantie.
- `backtest_lab/ui.py`: `_format_created_at` → `db.to_display_bp` (kein Zugriff
  auf modul-private Namen mehr).

**Verifikation (Hausregel: keine UI-/Regressionstests):**
`py_compile` 10/10 OK · `test/test.py` **48 OK / 0 FAIL** ·
`_epoch_sec(t) == int(t.timestamp())` für tz-naive (inkl. DST-Randfälle) ·
`available_date_range() ==` direkte BKZ-MIN/MAX-Abfrage ·
`ui._format_created_at == db.to_display_bp` (naive + tz-aware) ·
Engine/Renderer/Adapter-SHAs unverändert.

### Generationsbindung — Fail-Loud und Rückweg

Unverändertes Prinzip (§72.10), jetzt V017 ⇄ V018: `--mode V017` mit V018-Engine
bricht **vor dem ersten PNG** ab (`EXIT 1`); Rückweg explizit:

```text
python test/tmp_png_aug_sichttest.py --mode V017 ^
    --engine test/_tmp_backup_engine_pre_v018.py
```

Alle arretierten Sätze V01…V017 bleiben damit reproduzierbar
(V017-Protokoll numerisch unverändert).

### Offen

1. **Kein Renderer-Backup `pre_v018`** — der V017-Renderer (`3d6a4788…` /
   92.915 B) wurde in place überschrieben; nur urkundlich (SHA) erhalten.
   Wirkung nicht betroffen: V018-Renderer führt die V017-Literalzweige weiter.
2. `SWEEP_MARKER_P02` (deklariert, nicht referenziert) — unverändert.
3. E-12 (V014-P03) nicht neu arretiert.
4. **Nächster Auftrag unverändert:** H2-Marktanalyse (Phase P10 ab Bar 1021).

---

## Exploration 2026-09-11 (b) — H2-Zielzone: Fundament, Rollenbeweis, Kausalfaktor, Hook-1a/1b-Messkampagne, Gegenkanten-Wahl

> **Append-only.** Alles read-only, Wegwerf-Skripte in `test/` (gitignored).
> **Invarianten während der gesamten Kampagne:** Engine
> `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` /
> 196.649 B · Renderer `0d145ef4c5ea0aa9…` / 97.160 B · Adapter
> `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` /
> 25.783 B → **keine Projektdatei geändert.**

### P0 · Fundament-Sperrvermerk B1–B4 (Blocker für S1/S2)

| Befund | Inhalt |
|---|---|
| **B1** | `box_end_bar` ist in `_se_scan` **hart** auf `np.datetime64("2026-08-19")` gesetzt (Z. 2200). Fensterabhängig entstehen: AUG `n 1288 / box_end 644` · S1 (2026-02-05..08-28, 13.289 Bars) `box_end 12.645`, H2 bleibt **644** · S2 (2025-01-01..12-01, 21.624 Bars) `box_end 21.624`, **H2 = 0** |
| **B2** | Shift = `box_end(W) − 644`: S1 Δ **+12.001** → P9 (848) landet auf 12.849 = **2026-08-21 05:00 BKZ** (kalendarisch identisch zu AUG); S2 Δ **+20.980** → **alle** Adapter-Anker außerhalb |
| **B3** | Preisspannen: AUG 62,5480–70,0000 (μ 66,4367) · S1 54,7510–96,3910 (μ 71,6784) · S2 **28,2860–56,5250** (μ 37,7355). Adapter-Niveaus 67,6355 / 68,4000 / 69,8700 / 69,9140 liegen in **S2 vollständig oberhalb** des Marktes |
| **B4** | `kid` = **fensterlokaler** Auto-Increment (Z. 2272–2274, `kid_next += 1`) → K-P-Nummern sind **nicht** fensterübergreifend stabil |

**Weg:** `_se_scan` benutzt `box_end_bar` **nur 3×** (Docstring 2157, Berechnung
2200, Ablage 2330) → die Discovery ist unabhängig. `scan["box_end_bar"]` darf
deshalb **außerhalb** (also nach dem Scan) gesetzt werden; genau das tun alle
folgenden Messungen (`scan["box_end_bar"] = n`).

### P1 · Rollenbeweis (Rangfamilie) + Kausalfaktor

- **K67 = Rang 0 auf allen 267 H2-Bars** (Menge der existierenden Kanten ==
  `_kandidat`-Pool für den Außenrang). Divergenzen ausschließlich `→ KNone`
  (leerer Pool): OBEN 30/440 · UNTEN 0/440.
- **K82 = Rang 10 (42 Bars) / Rang 11 (114 Bars), in 111 Bars nicht existent**
  → die Rangfamilie `{AUSSEN, INNEN_1}` kann K82 **strukturell nicht**
  adressieren. Das ist der Grund, warum eine reine Rang-Erweiterung scheitert.
- **Lookahead-Beleg:** Fenster-Hoch 70,0000 @ **Bar 881**, Fenster-Tief 62,5480
  @ **Bar 673** — beide **≥ 644** (H2). Der Norm-Nenner 7,4520 ist damit
  Fenster-(Lookahead-)Größe; Box-only = **3,8090**, Kantenbasen bei Bar 643 =
  **3,4920**. Range-Verhältnis × Range = 1,9564 × 67,6355 = **132,3234** →
  **Dimensionsfehler** belegt.
- Bei Bar 643 (`box_end`) sind **K20 (66,4590)** und **K3 (62,9670)** die
  äußersten Kanten — K67/K82 existieren dort **nicht**.

### P2 · August-Replikationsbeweis (R0…R3)

| Lauf | Bindung | Trd | R | H1 | H2 |
|---|---|---|---|---|---|
| R0 | `kid` + PHASE | 17 | +65,835576 | 8/+38,919584 | 9/+26,915992 |
| **R1** | **`ROLLE(AUSSEN_OBEN)` + PHASE** | **17** | **+65,835576** | 8/+38,919584 | 9/+26,915992 |
| R2 | `kid` + MAKRO | 18 | +51,255680 | 8/+38,919584 | 10/+12,336096 |
| R3 | `ROLLE` + MAKRO | 18 | +51,255680 | 8/+38,919584 | 10/+12,336096 |

- **BEWEIS 1 (Resolver) BESTANDEN:** R0 == R1 **bit-identisch**, Δ `+0 / +0,000000000`.
- **BEWEIS 2 (Niveau) = −14,579896 R:** Keys verloren ∅, gewonnen `[(853,59)]`.
  Einzelvergleich der 5 gemeinsamen P9-Trades: (903,67) 4,119775→1,633441 ·
  (980,67) 9,987676→4,542254 · (981,73) 2,695488→**−1,000000** · (1002,77)
  3,629016→3,629016 (invariant) · (1020,67) 3,003157→1,050505; alle `tp2`
  68,3700 → **62,5770** (K48 Makro).
- `RECLAIM_AT_OPENING` blieb in R1 **inert** (kein `EVENT_ROLE_UNRESOLVED`-Log).

**Referenzwerte V018 (Adapter v0.1) — gelten unverändert:** V0 14/+42,450970 ·
V1_aktiv 17/+65,835576 · H1 8/+38,919584 · H2 9/+26,915992 · `box_end` 644 ·
n 1288. Laufgrenze `range(2, box_end-3)` ⇒ Bars **1285–1287 werden nie iteriert**.

### P3 · Hook-1a/1b-Messkampagne (Bandbreite `touch_band_pct`)

| Variante | Trd | R | H1 | H2 | 1a/1b | Entry-Neg |
|---|---|---|---|---|---|---|
| REF (0,12 %) | 17 | +65,835576 | 8/+38,919584 | 9/+26,915992 | 7/4 | OK |
| (i) 0,75 % nur 1**b** | 18 | +74,616528 | ✔ | 10/+35,696944 | 0/5 | OK |
| (ii) 0,75 % nur 1**a** | 16 | +63,140088 | ✔ | 8/+24,220504 | 95/0 | OK |
| (iii) 0,75 % 1a+1b | **20** | **+99,239447** | ✔ | 12/+60,319862 | 95/14 | **VERLETZT** |
| CTRL Kanäle global AUS | 16 | +63,140088 | ✔ | 8/+24,220504 | 0/0 | OK |
| REPLIKA Fenster 1021..1287 | 20 | +99,239447 | ✔ | — | 95/14 | VERLETZT |
| **(iv-A) endogen [1075..1287]** | **19** | **+77,312016** | ✔ | 11/+38,392432 | 57/9 | **OK** |
| (iv-B) mit `existiert`-Gate | 17 | +65,835576 | ✔ | 9/+26,915992 | 5/2 | OK |

**Neue Trades:** `(1122,73)` +10,221758 (nur 1**b** nötig; K67 dort **dormant**)
· `(1272,73)` +1,254682 (nur 1**b**) · **`(1022,73)` +21,927431 (1a UND 1b**;
Q1-Promotion: K67 dort lebend, K73 V-S = 2 < 3**)**. Entry-Negativkontrolle
1023..1031 kippt durch (1022 → Entry 1023). Endogener Trigger: **ohne**
`existiert`-Gate `k = 1075` (K82 `STUFE_1_IN_BAR`); **mit** Gate leer.

**Kanalanalyse:** Die M6-Blindstelle ist ein **Bandbreiten-Mismatch**
(`touch_band_pct 0,12` vs. M6 `max_seed_distanz_pct 0,75`) — **kein**
Liveness-Problem. Nur 3 M6-Sperren im gesamten Fenster, alle K67-dormant.
Freigabe-Volumen: 0,12 % → 5 Bars (P9) / **0** (P10); 0,75 % → 82 / 33
(28 dormant).

### P4 · Gegenkanten-Wahl und `RECLAIM_AT_OPENING` — **neuer Befund**

`test/_tmp_gegenkante_probe.py` `3c7fbfa8ded6b08e6e3479fe4b4c5cffa913ab404b2d6513f74721dae478bb11` (11.547 B) ·
Out `f3a7f82e3af3abd0a9849571481ada1d5e45cee9f2c4a30d811bdd65723663a3` (6.314 B).
Vier Zielmechanismen bei **konstanter** kid-Bindung (P9 arrestiert):

| Mechanismus | Anker | Trd | R | Δ zu PHASE |
|---|---|---|---|---|
| Z0 `PHASE` (Bestand) | Literal 68,3700 / 69,8700 | 17 | +65,835576 | — |
| Z1 `MAKRO` (Engine `_gegenkante`) | K48 **62,5770** | 18 | +51,255680 | **−14,579896** |
| **Z2 `SEG_BODEN` (kausal)** | K77 `basis_bei` **68,3920** | 17 | **+65,504879** | **−0,330697** |
| Z3 `INNEN_UNTEN_1` | K49 62,8590 | 18 | +51,255680 | −14,579896 |

**Z2 ist der Treffer:** die **phaseneigene** Gegenkante (kausal über
`basis_bei`) reproduziert die Baseline zu **99,5 %** — ohne jeden Preis-Literal,
ohne neuen Trade, ohne `−1,0R`-Stop. Die Differenz ist reiner Preis-Drift
(68,3700 → 68,3920, d. h. −0,0220 USD Zielnähe).
Z1/Z3 vernichten zusammen **−14,579896 R**; **Z3 == Z1 bit-identisch** (gleiche
Trades, gleiche R, nur tp2-Label differiert) ⇒ in diesen Trades bindet `tp2`
nachweislich **nicht**, der Verlust entsteht allein aus den beiden
`−1,000000`-Stops (853 K59, 981 K73).

**Kernbestätigung der Mentor-Kritik:** P9's `ziel_preis_short` **68,3700** ist
**identisch** mit `P9.boden.provenienz_basis` (K77) — die Phase zielt bereits
auf ihre **eigene** Gegenkante, nicht auf die Makrowand. Der Fehler war nie
`GEGENKANTE_RELATIV` als Prinzip, sondern die **Wahl** der Gegenkante
(Engine `_gegenkante`, Q5/Q14 → äußerste Makrowand).

**Drei neue Präzisierungen:**

1. **`INNEN_UNTEN_1` ist falsch implementiert.** Der UNTEN-Pool wird nach
   `basis_bei` **aufsteigend** sortiert → Rang 1 ist wieder eine Makro-Kante
   (K49 62,8590). „Nächste relevante Innenwand der aktuellen Range" heißt
   **Nähe zum Signalpreis**, nicht absolute Höhe. Z2 (phaseneigene Gegenkante)
   trifft die Intention bereits; eine Rang-Regel muss auf **Nähe** ranken.
2. **`basis_bei` hat einen Pre-Birth-Lookahead-Fallback.** `K77.basis_bei(903)
   = 68,3920`, obwohl `existiert(K77, 903) = False` (Pivot erst 934,
   `geburts_bar` 991). Ursache: `_SEEdgeH.basis_bei` fällt bei leerem
   `px`-Filter auf `self.wicks[0][1]` zurück = der **erste** Docht der Kante =
   Zukunft. In Z2 war **genau der Trade (903, SHORT)** davon betroffen.
   Bei 980/1002/1020 ist der Wert kausal (Pivot 934 + 2 ≤ k).
3. **K82 schläft genau über dem Reclaim-Ereignis.** `K82.schlaf_windows =
   [(1074, 1174)]`, `basis_bei(1075) = 67,5530`; die Kerze 1075
   (`L 67,4200 < 67,5530 < C 67,6780`) ist ein **sauberer `STUFE_1_IN_BAR`-
   Reclaim** — aber `existiert(K82, 1075) = False` (`ist_aktiv_bei =
   False`). Er löst genau **1 Bar** nach dem Einschlafen aus (Sweep-Bar 1072 →
   Fenster ab 1074). Das erklärt mechanisch den P3-Befund „(iv-B) mit Gate =
   Rückfall auf Baseline". Zweitbefund: `K67` (OBEN) liefert in
   [1021, 1288) **kein** Reclaim ≥ 1 → der M6-K67-Pfad ist dort strukturell
   leer.
4. **Ereignis-Bestätigung 1002:** `lo 68,3080 < 68,4000 < cl 68,5090`,
   `K77.touch_conf(1002) = 3` (erstmals ≥ `min_touches_handelbar`) — genau
   **eine** UNTEN-Kante mit Reclaim ≥ 1: **K77 (Stufe 1)**. Das stützt
   `RECLAIM_AT_OPENING` empirisch an Bar 1002 (Datenlage) — der Adapter-Pfad
   muss aber auf den `existiert`-Fallstrick (Punkt 2) getestet werden.

### P5 · Kanten-Sextett und Gate-Histogramm (H2-Fenster)

**Sextett:** K67 OBEN 69,9458 (Pivot 873, V-S 4→5) · K73 OBEN 69,6785 ·
K76 OBEN 69,5183 · K77 UNTEN 68,3597 · K82 UNTEN 67,5455 (Pivot 1031) ·
K85 UNTEN 67,4200 (Einzeldocht, V-S bleibt 1). Im ganzen Fenster **keine**
Außenkanten-Migration: Decke bleibt K67 (kurzfristig K48 im Süden), Boden K48
(62,5770).

**Gate-Histogramm (534 = 267 Bars × 2):** `KANDIDAT_NONE` 503 · Q29 21 ·
`M6(K67)` 3 (1122 / 1123 / 1272, alle dormant) · `STUFE0` 1 ·
`HOOK2_BLOCKIERT` 0 · PASS 6 → **nur 19 Bars mit Kandidat**.

**Schlaf-Fenster (Auszug):** K77 `[(1031,1159),(1165,1210),(1244,None)]` ·
K82 `[(1074,1174)]` · K67 `[]` (nie schlafend).

### P6 · Artefakt-Anker dieser Kampagne (`test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `_tmp_explo_v018_phase1.py` | `909ad0046deff42c8d797732f878cfffe665596e1d9cc38eac0eb174e8c66e45` | 28.201 |
| `_tmp_explo_v018_phase2.py` | `888f28148ac15714d5d02718a10d1ffec77eacbd030e3f053e30987f53c2c2f1` | — |
| `_tmp_explo_v018_phase3a.py` | `c23d71c63ffa3671b874ce686584e727b41ca9bc991d611985956c69811d0240` | — |
| `_tmp_explo_v018_phase3_messung.py` | `6c09fb0bac8c2a9f5197e95f30e995ee4b09a69fbb651ec35e3a902955ccc74a` | — |
| `_tmp_phase1_rollenbeweis.py` | `3db4b2fb9520727a7e75e585aabf2b1486a4c88c4ef054ef18d78332dc187840` | — |
| `_tmp_phase2_1_kausalfaktor.py` | `b9ff4046a5c58a7780972694d28665544d9fcda4edd29d85fde9dcae58c29f8c` | — |
| `_tmp_aug_replikation.py` | `da360d0e79aa704103738a23e557ff11a7a53cd4da8befe73b65f570fe3791bc` | 16.131 |
| `_tmp_aug_replikation_out.txt` | `b0f428d302238cd5cd6165535e503a9906e3bd6b295b16b9b027a376682c9eba` | 3.959 |
| `_tmp_vd_vertrag_entwurf.py` (aktuell) | `984be912e3904e634f0d38d2fdebba216dc8e6c9fdb2b707ba9290cf6ace9b46` | 22.486 |
| **`_tmp_gegenkante_probe.py`** | `3c7fbfa8ded6b08e6e3479fe4b4c5cffa913ab404b2d6513f74721dae478bb11` | 11.547 |
| **`_tmp_gegenkante_probe_out.txt`** | `f3a7f82e3af3abd0a9849571481ada1d5e45cee9f2c4a30d811bdd65723663a3` | 6.314 |

**Pickle-Pipeline validiert (bit-identisch):** AUG `14 / +42,450970` → Pickle
78,6 KiB → Reload → `14 / +42,450970`, Δ 0, Keys identisch. **`type(...)
.__module__ == 'rr_pkl'`** ⟹ der Loader-Name muss beim Laden auf den
Registrierungsnamen gesetzt werden (`sys.modules["tmp_kanten_engine_replay"]`).

## V-D-Datenvertrag (Entwurf, ratifiziert)

11 Top-Level-Typen (`KantenRolle`, `NiveauModus`, `KantenReferenz`,
`SchliessModus`, `SchliessKriterium`, `OeffnungsModus`, `OeffnungsTrigger`,
`SegmentVD`, `PhasenDynamikModus`, `PhasenDynamikErgebnis`, `VDAdapterEntwurf`).
Beschlüsse: `KantenRolle` um **`RECLAIM_AT_OPENING`** erweitert
(Ereignisfamilie, `ist_rang`-Property, `.seite` raises, `.rang → None`) ·
**`PROVENIENZ_SKALIERT` ersatzlos entfernt**, `GEGENKANTE_RELATIV` =
Ebene-2-Default · `ziel_preis()` mit **Clamping** (SHORT `max`, LONG `min`) ·
`aufloese_rolle` wirft `ValueError` für Ereignisrollen (gehört in `hook_4`) ·
`SchliessKriterium` `bruch_bars=2`, `puffer_pct=0.0`, `timeout_bars=96`
(Hybrid = Option C, übernimmt Engine-Q-Semantik Z. 2284–2292) ·
`hook_4_phasen_dynamik(bar_idx, marktdaten: Mapping)` bestätigt.

## Entscheidungsfragen (an Anwender)

1. **Zielmechanismus:** `SEG_BODEN` (phaseneigene Gegenkante über kausales
   `basis_bei`) als **Ersatz** für die Engine-Makrowand in
   `GEGENKANTE_RELATIV` ratifizieren? Messlage: +65,504879 / 17 Trades gegen
   MAKRO +51,255680 / 18.
2. **Ranking-Regel:** `INNEN_1` auf **Nähe zum Signalpreis** umbauen (statt
   `basis_bei`-aufsteigend)? Erst danach ist die Rangfamilie aussagekräftig.
3. **`basis_bei`-Fallback** (`wicks[0][1]` bei leerem `px` = Pre-Birth-Lookahead):
   als Engine-Korrektur (V019) einbrennen oder Adapter-seitig per
   `existiert`-Guard abfangen? Berührt Baselines (M6-Heilung V017 analog).
4. **K82-Schlaf vs. Reclaim 1075** (1 Bar): `existiert`/`ist_aktiv_bei`-Gate für
   das **Ereignis** `RECLAIM_AT_OPENING` lockern (Schlaf-Fenster überbrücken)
   oder die Oeffnungs-Erkennung auf `_reclaim_stufe` **ohne** Pool-Gate stützen?
5. **`RECLAIM_AT_OPENING` an 1002** verifiziert (K77, Stufe 1, touch_conf 3) —
   Rolle so bestätigen?
6. **S2-Scan freigeben?** (`scan["box_end_bar"]` außerhalb setzen, Loader-Name
   fixieren, Pickle `test/_tmp_s2_scan_cache.pkl`) — erst dann erste
   OOS-Messung auf Ebene 2. Achtung B1–B3: S2-Preisspanne liegt **komplett
   unter** allen Adapter-Niveaus; K-P-Nummern sind fensterlokal.
7. Dokumentation: Befunde als Addendum **§74** in die Adapter-Spez
   (`reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md`) überführen?

---

## Umsetzung 2026-09-11 (c) — v0.24-Ratifizierung: Zielmechanismus, Ranking, Kausalität, Sleep-Bypass + S2-Cache

> **Append-only.** Alle Invarianten unverändert: Engine
> `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` ·
> Renderer `0d145ef4c5ea0aa9…` · Adapter `0f3f8765b1682910…` (jeweils nach dem
> Lauf re-verifiziert). **Kein Projektcode geändert** — nur der V-D-**Entwurf**
> (gitignored), `test/test.py` (gitignored) und die Adapter-**Spez** (getrackt).

### R1 · Die vier ratifizierten Punkte

| # | Beschluss | Umsetzung |
|---|---|---|
| **1** | `GegenkantenWahl.PHASE_EIGEN` ersetzt die Engine-Makrowand in `GEGENKANTE_RELATIV` | neues Enum + `SegmentVD.gegenkante_wahl` (Default `PHASE_EIGEN`); `MAKRO_ENGINE` für endogene Segmente **fail-loud verboten** |
| **2** | `RangModus.NAEHE` für die Innenränge (`|basis − sweep_px|`) | neues Enum + `SegmentVD.rang_modus` (Default `NAEHE`); `sortiere_nach_naehe` |
| **3** | Pre-Birth-Lookahead **adapter-seitig** kapseln — **kein V019** | neue Dataklasse `KantenSicht` (`kausal_existent`, `basis_kausal → None`) |
| **4** | `RECLAIM_AT_OPENING`: Ereignis schlägt Status | `OeffnungsTrigger.ignoriere_schlafstatus=True` + `aufloese_reclaim_at_opening` (filtert nur Kausalität) |

Alle Änderungen **rein additiv** — die Engine-identischen Auflöser
(`sortiere_seite_kanten`, `aufloese_rolle`, `aufloese_referenz`, `ziel_preis`)
bleiben unverändert daneben stehen; die kausal-gehärteten Varianten heißen
`*_kausal`. **Nichts überschrieben.**

### R2 · Verifikation (Hausregel: keine UI-/Regressionstests)

`py_compile` OK · `test/test.py` **75 OK / 0 FAIL** (27 neue V-D-Checks).
Enthalten: Kausalitätsgrenze (`Pivot+2 == k+1`), `NAEHE` vs. `ABSOLUT`
(K82 67,545 vs. K49 62,859), `PHASE_EIGEN` SHORT/LONG (K77 68,392 / K67
69,9458), `ziel_preis_kausal` (68,392 — **kein Literal**),
`MAKRO_ENGINE`-Verbot, Sleep-Bypass synthetisch **und** als Integration gegen
den arretierten AUG-Scan (K77 Pre-Birth, K82-Schlaf am Ereignis-Bar,
K82-Reclaim Bar 1075 = `STUFE_1_IN_BAR`).

### R3 · S2-Cache (`_tmp_s2_scan_pipeline.py`)

| Größe | Wert |
|---|---|
| `_se_scan('S2')` Laufzeit | **410,7 s** (21624 Bars) |
| n / `box_end` (hart 2026-08-19) | 21.624 / **21.624 == n** ⇒ B1 bestätigt |
| Split **2025-10-01** | **Bar 17.692** (2025-10-01T00:00 BKZ) |
| H1 / H2 | 17.692 / **3.932** Bars |
| Kanten | 411 edges + 37 seeds, `kid` 0..562 (fensterlokal ⇒ B4) |
| Preisspanne | 28,2860 .. 56,5250 (mean close 37,7355) |
| August-Literale | **alle oberhalb** des S2-Maximums ⇒ B3 bestätigt |
| Pickle `test/_tmp_s2_scan_cache.pkl` | 1.254.468 B · `a86ad1801c054ad039ee55a11f44f661eb9f651afb1e702af4e690548b1b2e2b` |
| Roundtrip | Keys identisch · Fidelity-Lauf (`box_end=3000`) **bit-identisch** (27 / −16,939020) |
| Rollenprobe H2 (Stride 3, 1.311 Bars) | leerer Pool **0** · `AUSSEN_*` 1.311/1.311 · `PHASE_EIGEN` 1.311/1.311 · `RECLAIM_AT_OPENING` **890** |

**Auflagen eingehalten:** Split-Kalenderkante gesetzt (nicht die Bar-Konstante),
Loader-Name fixiert (`sys.modules["tmp_kanten_engine_replay"]`, Frisch-Prozess
simuliert), **kein** August-Literal verwendet (alle Größen sind reine
Scan-/Marktwerte).

**Einschränkung (offen):** Die Rollenprobe nutzt `AUSSEN_OBEN`/`AUSSEN_UNTEN`
als Segmentgrenzen — das ist ein **Auflösbarkeits-Test des Pfades**, **keine**
finale S2-Segmentdefinition. Die phasen-eigene Gegenkante (Punkt 1) setzt
voraus, dass das Segment seine **eigene** Konsolidierung deklariert; das ist in
S2 noch nicht bestimmt.

### R4 · Dokumentation

- Addendum **v0.24 / §74** in `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md`:
  Urkunde vorher `5b902df40ac7493431f7dbd97ffc9fb9bd577fa9f0e87a1646e878da99e7b69f`
  (207.666 B / 4.213 Z., LF) → **nachher**
  `142d658c914da91c2a852d027a627817abc4fd3352921cdb123f521cf64a3230`
  (**220.428 B / 4.427 Z.**). Regelbestand jetzt §54 + §66…§74;
  **neue Errata E-16 · E-17 · E-18**.
- Einmaliges Append-Werkzeug `test/_tmp_append_spez74.py` nach Gebrauch
  **gelöscht** (kein Archivwert — der Inhalt liegt in der Spez).

### R5 · Neue Artefakt-Anker (SHA256, `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_vd_vertrag_entwurf.py` (v0.24) | `1615a4aff5b1231be652ffc418d981662a049508cc9a82aa8c420cee7a20983a` | 44.429 |
| `test/test.py` (75 OK) | `25bc8d11ab35a06bf0f93e1a270d782dc41057b12c239637efc4f36706a0a348` | 13.909 |
| `test/_tmp_s2_scan_pipeline.py` | `1a87c1a65dab378282a54bec0e99eb09d9bd3e9e69ce34abfbebaa44de7a2118` | 9.062 |
| `test/_tmp_s2_scan_pipeline_out.txt` | `c3d439efd025d5f5e97572bc434c9b50be2a13457ecc6e53fae71ba7b9d99319` | 4.445 |
| `test/_tmp_s2_scan_cache.pkl` | `a86ad1801c054ad039ee55a11f44f661eb9f651afb1e702af4e690548b1b2e2b` | 1.254.468 |
| Spez (getrackt, §74) | `142d658c914da91c2a852d027a627817abc4fd3352921cdb123f521cf64a3230` | 220.428 |

### R6 · Antwort auf die zwei Leitfragen

**1. S2 ausschließlich mit relativer `SEG_BODEN`/`SEG_DECKE`-Exit-Logik?**
**Ja — bestätigt und so umgesetzt.** Die S2-Rollenprobe verwendet
ausschließlich `kausales basis_bei(k)` (kein Literal, kein Engine-`_gegenkante`);
die Auflage „kein August-Niveau" ist maschinell belegt (alle vier Literale
liegen oberhalb des S2-Maximums 56,5250).

**2. Freigabe zur Aktualisierung des Entwurfs (Punkte 1–4) + §74?**
**Beides ausgeführt.** Entwurf `1615a4af…` (44.429 B) mit den vier Punkten;
Addendum §74 eingepflegt (`142d658c…`, 220.428 B); `test/test.py` 75 OK / 0 FAIL.
Die Produktionsdatei `backtest_lab/phasen_regime_adapter.py` blieb unberührt.

### R7 · Offen (unverändert bzw. neu)

1. **S2-Segmentdefinition** (welche Rolle trägt in S2 `decke`/`boden`?) — der
   Pfad ist bewiesen, die Semantik nicht.
2. **Erste OOS-Messung auf Ebene 2 in S2** (relative Baseline als Maßstab,
   nicht die AUG-Baseline — E-15 sinngemäß).
3. **`INNEN_1`-Rangregel** ist implementiert/getestet, aber im
   Produktions-Adapter **noch nicht verdrahtet** (bewusst additiv).
4. **S1-Cache** (2026-02-05..08-28) noch nicht erzeugt.
5. §73.10-Punkte (Renderer-Backup `pre_v018`, `SWEEP_MARKER_P02`, E-12):
   unverändert offen.

---

## S2-Stresstest 2026-09-11 (d) — V-D-Schleife gegen die S2-Baseline

Freigabe „weiter" auf den letzten offenen Punkt (§74.7 / R7): der **Schritt 3**
des Plans — die V-D-Schleife (PHASE_EIGEN + `RangModus.NAEHE` + `KantenSicht`)
über den arretierten S2-Scan, gegen die S2-Baseline. Engine-SHA
`4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`
**vor und nach allen Läufen unverändert**; kein Projektdatei-Eingriff.

### S1 · Harness-Verankerung (die beiden gültigen Selbstkontrollen)

Der RAM-Patch `patched_src` wird unverändert aus `test/tmp_png_aug_sichttest.py`
(Zeilen 541–660) bezogen — dieselbe Verdrahtung wie in der P4-Probe.

| Kontrolle | Ergebnis | Wert |
|---|---|---|
| `BASE` (ungepatcht) vs. `_tmp_s2_baseline_ref.py` | **exakt** | 299 / −186,055940 R (H1 245 / −140,466233 · H2 54 / −45,589707) |
| `MAKRO` (gepatcht, `hook_2_ziel → MAKRO_ENGINE`) vs. `BASE` | **bit-identisch** | 299 / −186,055940 R, alle `stats` gleich |

⇒ Der Patch-Harness ist **treu**: die gepatchte Engine reproduziert ohne
Ziel-Override die ungepatchte bit-genau. Buchs-Trennung eingehalten
(`box_end` = 17.692 Partition, `scan['box_end_bar']` = 21.624 Laufgrenze).

### S2 · E-19 — der P4-AUG-Wert ist **kein** gültiger Fidelity-Anker

Der Versuch, den arretierten P4-Messwert `Z2 = 17 / +65,504879 R` über
`VD_K67_77 @ start 848` nachzuvollziehen, ergibt **13 / +45,347845 R** und ist
**kein** Harness-Fehler. Ursache: der Stress-Harness verdrahtet
`hook_1_freigabe_kid → None` und `hook_3_boden_reclaim → G4/P9`; die P4-Probe
hatte eine eigene `hook_1`-Freigabelogik (`L2Adapter.hook_1_freigabe_kid`).
Die 2×2-Isolation im **eigenen** Harness:

| Lauf | Trd | R |
|---|---|---|
| `kausal=F ov=F` | 14 | +48,976861 |
| `kausal=F ov=T` | 16 | +62,862379 |
| `kausal=T ov=F` | 14 | +48,976861 |
| `kausal=T ov=T` | 15 | +58,812459 |

⇒ Der K67-Override **69,87** (statt Provenienz 69,914) bewegt das AUG-Ergebnis
um **+13,89 R**; die Kausalitätsschranke ist in diesem Harness **wirkungslos**
(14 == 14), weil der G4-Zweig eigene Eintritte liefert. **E-19:** AUG-Zahlen
sind harness-gebunden und dürfen **nicht** als Fidelity-Anker für S2 dienen —
gültig ist allein `MAKRO == BASE`.

### S3 · S2-Ergebnis (n = 21.624; Partition bei `entry_bar` = 17.692)

| Lauf | Trd | R gesamt | H1 Trd | H1 R | H2 Trd | H2 R | H2+ |
|---|---|---|---|---|---|---|---|
| `BASE` (ungepatcht) | 299 | −186,055940 | 245 | −140,466233 | 54 | −45,589707 | 4 |
| `MAKRO` (Kontrolle) | 299 | −186,055940 | 245 | −140,466233 | 54 | −45,589707 | 4 |
| `VD_AUSSEN_ABS` (Rollen `AUSSEN_*`, ABSOLUT) | 299 | −186,055940 | 245 | −140,466233 | 54 | −45,589707 | 4 |
| `VD_NAEHE_ENV` (Rollen `AUSSEN_*`, NAEHE) | 245 | −140,466233 | 245 | −140,466233 | **0** | +0,000000 | 0 |
| **`VD_K408_409`** (kid, PHASE_EIGEN) | 299 | **−159,531883** | 245 | −140,466233 | 54 | **−19,065650** | 1 |
| `VD_K408_409_H` (`ziel_anteil` = 0,5) | 299 | −160,853568 | 245 | −140,466233 | 54 | −20,387335 | 1 |

- **H1 ist in allen V-D-Läufen bit-identisch** (`start_scope_bar` = 17.692) —
  H1 ist **Kontrolle**, nicht Messung; die gesamte Differenz liegt im H2.
- **`VD_AUSSEN_ABS` == `BASE`** beweist positiv: die Baseline-Exit-Logik **ist**
  die Riesenband-Falle (`AUSSEN_UNTEN` löst auf **K172 28,4255** auf; jedes
  `tp2` = 28,4320 wird nie erreicht).
- **`VD_NAEHE_ENV`** (jeweils nächste Wand je Seite) erzeugt **0 H2-Trades**
  (`kein_raum` 14 → 152): keine Verlustquelle, aber auch kein Handel.
- `kein_gegner` 0 · `blocker` 332 · `quartil_blockiert` 1341 · `kein_raum` 14
  sind in `BASE` und `VD_K408_409` **identisch** ⇒ **identische Trade-Menge**,
  nur `tp2` (und damit `poc`) differiert.

### S4 · Warum die +26,52 R trügen (E-20)

**Alle 54 H2-Trades sind SHORT** (kein einziger LONG). `tp2`: 28,4320 → 45,7890 (K409).

- **Ein Ausreißer** `entry 18825` (Signal-Bar 18824, K517): `sl` 54,4900 ·
  `entry` 54,2440 · **`risk` 0,2460 USD (0,45 %)** → **R −1,000000 → +33,934350**.
  Der Markt fällt danach tatsächlich bis 45,5300 (Bar ~19.480) — der Trade ist
  **kausal und nicht degeneriert**.
- **Vier echte kleine Gewinner werden zerstört**: 19584 `+0,802929` · 20071
  `+1,827819` · 20241 `+0,739141` · 20272 `+1,040405` → alle `−1,000000`.
- **Ursache (E-20):** `gegen_basis` speist **zugleich** das POC-Fenster
  `(unter, ober)` in `_se_trades`. Ein nahes `tp2` verengt die Range → das POC
  wandert zur Unterkante → Hälfte 1 (`tp1 = poc`) erreicht ihren Trigger nicht
  mehr vor dem SL (`_c_loese_trade` löst **beide Hälften unabhängig über das
  gesamte Restfenster** auf, nicht sequenziell).
- Bilanz H2: 53 × (−1,0) + **+33,93** = −19,07 R. **Ein einziger Trade trägt die
  gesamte „Verbesserung".**

**⇒ Der V-D-Stresstest liefert in S2 KEINEN Edge.** H2 bleibt mit **−19,07 R**
tief negativ, gesamt **−159,53 R**. Die Stop-Geometrie (risk 0,14–0,87 %, Ziele
1,3–8,5 USD entfernt) erzeugt 53/54 Stop-outs.

### S5 · Endogene Öffnung im H2 (Teil C)

`aufloese_reclaim_at_opening` (Sleep-Bypass) über alle 3.932 H2-Bars:

- **K408 (Kandidatendecke): 19** Ereignisse · **K409 (Kandidatenboden): 1**.
- Schwerpunkte: `K439 48,5520 (67×)` · `K433 48,2590 (55×)` · `K437 48,4140
  (53×)` · `K436 48,6100 (52×)` … — rund **1,3–1,8 USD oberhalb** der
  Split-Konsolidierung.

⇒ §12 bestätigt: H2 expandiert nach oben, **K408 wird durchbrochen**;
K408/K409 sind **nicht** die H2-Handelszone.

### S6 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_s2_segment_kandidaten.py` | `c15022a018136c4d6afe628cdb2fb0d1ecf53371720304354f0b181062e36242` | 14.305 |
| `test/_tmp_s2_segment_kandidaten_out.txt` | `cc3e4533b9d8c5ea615b8a2c516757d8e17fe6cd21d000d81404c1d3b80c6b85` | 10.162 |
| `test/_tmp_s2_baseline_ref.py` | `4cc658ed6bf12499ce4d9e3693bbe4a36a6dcfd4d92f46135cdda83db44a6383` | 4.148 |
| `test/_tmp_s2_baseline_ref_out.txt` | `e029c1b863c201cc9653bc23432d63fe032e00216c48c2434c8efcda98d18d3b` | 394.484 |
| `test/_tmp_s2_vd_stresstest.py` | `4da8165dd5070005b72492646bff4c6601aaa20fe6d629f82570d5952c8fc16d` | 12.300 |
| `test/_tmp_s2_vd_stresstest_out.txt` | `15e7f29c31fed2703e305b758cf05edd8a76df7524b7d73281a7e6cb263ec554` | 6.263 |
| `test/_tmp_s2_vd_detail.py` | `9488e3d44ea59a106e566c3854721461e896eef3a223a1b3a50fde7b6096640d` | 10.890 |
| `test/_tmp_s2_vd_detail_out.txt` | `496d3cf78ab7f12fe91435616140f7adcc3f2c81d36a079711cf74af452ac585` | 7.316 |
| `test/_tmp_s2_vd_risiko.py` | `874fc1cdf3cb675736dd67441da2934af416a05b63c149d5b6caae2b3c5ee805` | 2.862 |
| `test/_tmp_sha_liste.py` | `48d9117b93d0e35abdc80176b90793a6c6cd3fee329280e9af52d09706fecadd` | 952 |
| Engine `test/tmp_kanten_engine_replay.py` | `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` | 196.649 |
| VD-Entwurf `test/_tmp_vd_vertrag_entwurf.py` | `1615a4aff5b1231be652ffc418d981662a049508cc9a82aa8c420cee7a20983a` | 44.429 |

`*_stderr.txt` beider Läufe sind **leer** (`e3b0c442…` = Leerdatei-SHA);
`*_stdout.txt` spiegeln die `*_out.txt` (plus Abschlusszeile).

### S7 · Neue Errata

- **E-19** — Der P4-AUG-Wert `Z2` (17 / +65,504879) ist **harness-gebunden**
  (`hook_1_freigabe_kid`/G4-Verdrahtung der Probe) und mit dem Stress-Harness
  nicht reproduzierbar. AUG-Zahlen sind **kein** Fidelity-Anker für S2.
- **E-20** — `gegen_basis` ist **kein reiner Exit-Anker**: es definiert zugleich
  das POC-Fenster `(unter, ober)`. Jede Änderung der Gegenkanten-Wahl verändert
  damit **TP1** und kann Gewinner in Verlierer kippen. Eine isolierte Bewertung
  „Gegenkante besser/schlechter" ist über `gegen_basis` allein **nicht** möglich.

### S8 · Offene Entscheidung (Textblock — keine Auswahl)

**Die S2-Segmentdefinition ist entschieden worden, aber das Ergebnis widerlegt
die naheliegende Wahl.** Gemessen sind drei Lagen:

1. **Riesenband** (`AUSSEN_*` absolut) — identisch zur Baseline (−186,06 R),
   also die Falle selbst. **Verworfen.**
2. **Split-Konsolidierung K408/K409** (kausal, PHASE_EIGEN) — reproduziert die
   Absicht (+26,52 R), aber der Gewinn ist **ein Einzeltrade-Artefakt** (E-20).
3. **Neuauflösung im H2** (die Ereignisse liegen bei K439/K433 48,3–48,6) —
   **noch nicht gemessen**.

Daraus folgen drei Entscheidungen, die der Anwender treffen muss, bevor
irgendetwas verdrahtet wird:

- **(A) Segmentdefinition.** Bleibt es bei „die Grenzkanten der Konsolidierung
  **zum Split**" (dann ist S2 negativ, aber das Verfahren ist bewiesen) — oder
  wird Ebene 2 auf „die Grenzkanten der **laufenden** Konsolidierung"
  (Lookback-Fenster, z. B. 480/960 Bars, jeweils neu aufgelöst) umgestellt?
  Die Messung in §12 zeigt, dass genau das die stabile Struktur ist
  (`17692 K408/K409` → `18652 K494/K493` → `20572 K547/K484`).

- **(B) Stop-Geometrie.** Vor jeder weiteren Segmentarbeit: Ist ein Stop von
  0,14–0,87 % (Median ~0,25 %) bei einer Jahres-Spanne von 66,7 % und
  H2-Bewegungen von 10,99 USD überhaupt sinnvoll? Bei 53/54 Stop-outs in H2
  ist die Gegenkanten-Diskussion **nachrangig** — die Verlustquelle sitzt im
  Stop/Target-Verhältnis, nicht in der Zielwahl.

- **(C) Bewertungsmaßstab.** Ist ein Ergebnis, das von **einem** Trade
  (+33,93 R bei 0,2460 USD risk) getragen wird, überhaupt als „Verbesserung"
  zulässig? Ohne diese Klärung ist jede V-D-Zahl in S2 nicht entscheidungsfähig
  (E-20). Vorschlag zur Entscheidung: Ausweis **mit und ohne** den größten
  Einzeltrade, plus Stop-Out-Quotient je Lauf.

Bis zu diesen drei Entscheidungen gilt: **keine Verdrahtung in den
Produktionsadapter**, kein §75-Addendum, kein S1-Cache.

### S9 · Offen (Stand nach dem Stresstest)

1. **S2-Segmentdefinition** — siehe S8/A (nicht mehr „welche Rolle", sondern
   „statisch zum Split" vs. „laufend neu aufgelöst").
2. **Stop-Geometrie** — S8/B (neuer, vorgelagerter Blocker).
3. **Bewertungsmaßstab** — S8/C (Einzeltrade-Ausweis).
4. **Erste OOS-Messung auf Ebene 2 in S2** — erst nach 1–3.
5. **`INNEN_1`-Rangregel** im Produktions-Adapter **nicht** verdrahtet.
6. **S1-Cache** (2026-02-05..08-28) noch nicht erzeugt.
7. §73.10-Punkte (Renderer-Backup `pre_v018`, `SWEEP_MARKER_P02`, E-12): offen.
8. **Plattform-Regel offen:** künftige Spez-Appends **müssen** im LF-Zustand
   erfolgen (sonst kippt der Blob-SHA) — noch nicht als Regel verankert.
