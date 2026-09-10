# ⛔ EINGEFRORENES HISTORISCHES PROTOKOLL (01.–02.09.2026)

> **Dieses Dokument wird NICHT mehr gepflegt** (eingefroren am 02.09.2026).
> Es dient nur noch als **Archiv/Historie** (verworfene Ansätze, Referenzzahlen,
> Git-Zustand), um Wiederholungen/Re-Tests zu vermeiden.
>
> **👉 Aktueller Live-Session-State + Konzept: `docs/reclaim.md`**
> (dort zuerst lesen = Bootstrap). Diese Datei nur bei Bedarf für tiefe Details.

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
