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
