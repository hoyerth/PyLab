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

---

## Phase 1 (2026-09-11, e) — Ratifikation: Single-Trade-Artefakt als Disqualifikations-Kriterium

Anwender-Beschluss (Textfassung; **ersetzt** den offenen Block S8). Dies ist
eine **Verfahrensregel** und soll bei Aufhebung des §75-Frosts in die Spez
überführt werden — bis dahin ist dieses Handoff der gültige Verwahrort.

### D0 · Anlass

`VD_K408_409` meldete `+26.524056 R` gegen die Baseline, obwohl **53 von 54**
H2-Trades ausgestoppt wurden. Der gesamte Zuwachs stammt aus **einem** Trade
(`entry 18825`, K517, `risk` 0,2460 USD = 0,45 %: `−1,0 → +33,934350 R`).
Das ist kein Edge, sondern ein Tail-Artefakt. Der frühere Block S8/C ist
damit **ratifiziert und verschärft**.

### D1 · Zwei Pflichtmetriken (ab sofort für **jede** Auswertung)

1. **Einzeltrade-bereinigtes Ergebnis**

   ```
   R_adj = R_gesamt − R_max        (R_max = größter Einzelgewinn im Buch)
   ```

   Zusätzlich auszuweisen: `R_adj` je Partition (H1/H2) gegen den
   Partitions-Bestwert.

2. **Stop-Out-Quotient**

   ```
   Q_stop = N_stop / N_trades      (N_stop = Trades mit r <= −1,0 + 1e-9)
   ```

### D2 · Schwellen (hart, kategorisch)

| Metrik | Schwelle | Folge |
|---|---|---|
| `Q_stop` | **> 0,75** | **Übernahme kategorisch ausgeschlossen** — unabhängig von `R` |
| `R_adj` | **≤ Baseline `R_adj`** | Variante **verworfen** (auch bei positivem `R`-Delta) |
| Vortrag | `R` **und** `R_adj` **und** `Q_stop` | einseitiger `R`-Ausweis ist unzulässig |

Ein positives `R`-Delta bei `Q_stop > 0,75` ist **kein** Verbesserungsnachweis
und darf nicht als solcher berichtet werden.

### D3 · Anwendung auf den S2-Stresstest (Nachrechnung)

| Lauf | H2 `R` | H2 `R_max` | H2 `R_adj` | H2 `Q_stop` | Urteil |
|---|---|---|---|---|---|
| `BASE` (ungepatcht) | −45,589707 | +1,827819 | −47,417526 | 50/54 = **0,926** | **disqualifiziert** |
| `VD_K408_409` | −19,065650 | +33,934350 | **−53,000000** | 53/54 = **0,981** | **disqualifiziert** |
| `VD_K408_409_H` (0,5) | −20,387335 | — | — | 53/54 ≈ **0,981** | **disqualifiziert** |

**Kernaussage:** `R_adj(H2) = −19,065650 − 33,934350 = −53,000000 R` **exakt**
(die verbleibenden 53 Trades sind sämtlich −1,0). Damit ist `VD_K408_409`
adjustiert um **−7,410293 R _schlechter_** als die Baseline-H2. `Q_stop`
liegt in **beiden** Läufen über 0,75 — die gesamte S2-Maschinerie ist unter
D2 disqualifiziert, **nicht nur die Variante**.

> **Definitionseinschränkung:** `R_adj` ist in D3 **partitions-lokal (H2)**
> ausgewiesen, damit die Messpartition vergleichbar bleibt. Der globale
> `R_max` über H1+H2 ist **noch nicht** extrahiert (H1-Einzelzeilen wurden
> nicht gedruckt); H1 ist über alle V-D-Läufe **bit-identisch**
> (245 / −140,466233 R), das H1-`R_max` also eine Konstante und damit
> delta-neutral. Die H2-lokale Zahl ist für den Variantenvergleich
> belastbar, **nicht** als globales `R_adj`.

### D4 · Ratifikation des Entscheidungsblocks

- **(A) Segmentdefinition — ratifiziert:** Umstellung auf „Grenzkanten der
  **laufenden** Konsolidierung" (Lookback 480/960). Die Split-Erstarrung
  (K408/K409) ist empirisch gescheitert. **Umsetzung erst nach (E-20)**
  (siehe Leitfrage 2) und als **additiver** Entwurf; kein Kern-Eingriff.
- **(B) Stop-Geometrie — ratifiziert als vorgelagerter Blocker:** Stop
  orientiert sich künftig an Kanten-Struktur bzw. lokaler Volatilität
  (ATR-Kandidat), nicht an statischen Cent-Puffern
  (`sl_buffer_usd` = 0,05 USD). Solange (B) ungelöst ist, ist die
  Gegenkanten-Diskussion **nachrangig**.
- **(C) Bewertungsmaßstab — ratifiziert:** siehe D1/D2.
- **(D) Commit — ausgeführt:** `de17fdb`
  (`docs(handoff): S2-Stresstest — V-D-Schleife, E-19/E-20`).

**Entwicklungsstopp (Produktivcode):** Kein Einbrand in
`backtest_lab/phasen_regime_adapter.py`, **kein §75**, **kein S1-Cache**,
bis (A) und (B) sauber konzipiert sind. Explorations-Prototypen in `test/`
bleiben zulässig (sie sind nicht Produktivcode), müssen aber `R_adj` und
`Q_stop` mitführen.

---

## Phase 2 / Block E-20 (2026-09-11, f) — POC-Entkopplung: implementiert, gemessen, **nicht bindend**

Freigabe erteilt für den additiven In-Memory-Prototyp. Umgesetzt ist der
Schalter **`poc_quelle`** mit den zwei ratifizierten Werten; die harte
Zulässigkeitsordnung `sl > entry > poc > tp2` (SHORT) blieb **unverändert**.

### E0 · Umsetzung (rein additiv, kein Kern-Eingriff)

Der Renderer-Patch-Slice (`tmp_png_aug_sichttest.py`, Z. 541–660) wird
**unverändert** übernommen und um genau zwei textuelle Ersetzungen erweitert:

```
unter, ober = gegen_basis, basis    ->  _hook.poc_fenster(k, richtung, gegen_basis, basis)
unter, ober = basis, gegen_basis    ->  _hook.poc_fenster(k, richtung, gegen_basis, basis)
```

`poc_fenster` liefert:
- `GEGENKANTE_LEGACY` (Default) → `(gegen_basis, basis)` bzw. `(basis, gegen_basis)`;
- `PHASE_RANGE` → `sorted(boden_kausal, decke_kausal)`, kausal über
  `aufloese_referenz_kausal` + `KantenSicht`; Fallback LEGACY, wenn keine
  aktive Phase oder eine Grenze `None` ist.

Engine-SHA `4a576a76…` **vor und nach allen Läufen unverändert**.

### E1 · Harness-Kontrolle (gültig)

| Kontrolle | Ergebnis |
|---|---|
| `LEGACY_CTRL` H2 `R` vs. `_tmp_s2_vd_stresstest.py` (`VD_K408_409`) | **`−19,065650` — exakt**, `R_adj` `−53,000000`, `Q_stop` `0,981` |

### E2 · Messung (S2-Cache, Partition bei `entry_bar` = 17.692)

H2 ist die Messpartition; H1 ist über **alle** gepatchten Läufe
bit-identisch (245 / −140,466233 R) und daher Kontrolle.

| Lauf | N | R | R_max | R_adj | N_stop | Q_stop | EV | EV_adj |
|---|---|---|---|---|---|---|---|---|
| `BASE` H2 | 54 | −45,589707 | +1,827819 | −47,417525 | 50 | 0,926 | −0,844254 | −0,878102 |
| `LEGACY_CTRL` H2 | 54 | −19,065650 | +33,934350 | **−53,000000** | 53 | **0,981** | −0,353068 | **−0,981481** |
| `PHASE_RANGE` H2 | 54 | −18,697002 | +34,302998 | **−53,000000** | 53 | **0,981** | −0,346241 | **−0,981481** |
| `PR_AUSSEN_NAEHE` H2 | **0** | +0,000000 | — | — | 0 | — | — | — |
| `BASE` gesamt | 299 | −186,055940 | +20,835855 | −206,891794 | 239 | 0,799 | −0,622261 | −0,691946 |

Deltas `PHASE_RANGE` gegen `LEGACY_CTRL` (H2):
**`dR` +0,368648 · `dR_adj` +0,000000 · `dQ_stop` +0,000 · `dEV_adj` +0,000000.**

### E3 · Befund F1 — E-20 ist ein **latenter**, kein bindender Defekt

`R_adj` und `Q_stop` sind zwischen LEGACY und PHASE_RANGE **bit-identisch**.
Der gesamte Unterschied sind **+0,368648 R auf genau EINEM Trade**
(`entry 18825`): `−19,065650 − 33,934350 = −18,697002 − 34,302998 = −53,000000`
**exakt**. Alle 53 übrigen Trades sind in beiden Läufen `−1,000000`.

Ursache: `tp1 = poc` wird in H2 von **1 von 54** Trades vor dem Stop erreicht.
Eine Änderung des POC kann daher nur diesen einen Trade bewegen. Die
Mentor-These „E-20 erklärt die Verluste" ist damit **widerlegt** — die
Verlustquelle liegt ausschließlich in der Stop-Geometrie (Block B).

### E4 · Neuer Befund E-21 — der POC ist ein **Randartefakt** des Fensters

`berechne_kausalen_histogramm_poc` spannt die Bins über `(unter, ober)` und
**clippt** Bars außerhalb in die Rand-Bins (`searchsorted(...)-1` + `np.clip`),
die Glättung (`win=3`) hebt danach Bin 1 über Bin 0. Messung für das Fenster
`(45,7890, 47,1221)` (Segment K408/K409, kausal bis Bar 21553):

| Lage der Bars | Bars | Volumen | Anteil |
|---|---|---|---|
| vollständig **unter** dem Fenster | 17.486 | 17.544.085 | **67,3 %** |
| überlappend | 64 | 124.885 | 0,5 % |
| vollständig innerhalb | 402 | 727.402 | 2,8 % |
| vollständig **über** dem Fenster | 3.602 | 7.663.723 | **29,4 %** |

Bin 0 = 67,3 % · letzter Bin = 29,6 % · **Bins 1…−2 zusammen = 3,1 %**.
`argmax` nach Glättung = **Bin 1** → `POC = 45,8223` = `tp2 + 0,0333 USD`
(**0,073 %** der Basis).

**Konsequenz:** `tp1 = poc` liegt praktisch **auf** `tp2`. Ein SHORT muss die
volle Strecke von ~47–54 USD bis ~45,82 USD laufen, um TP1 zu erreichen — bei
0,14–0,87 % Stop. TP1 ist damit **strukturell unerreichbar vor dem Stop**, in
**beiden** Fensterdefinitionen. Das erklärt `Q_stop = 0,981` mechanisch und
zeigt: die Fenster-Entkopplung (E-20) greift am falschen Ende — solange das
Fenster den Volumenschwerpunkt nicht enthält, ist der „POC" kein
Akzeptanzniveau. **`PHASE_RANGE` mit Split-Kanten erfüllt diese Bedingung
nicht** (67 % des Volumens liegt unterhalb).

### E5 · Neuer Befund E-22 — `R` ist unter degeneriertem Stop **nicht skaleninvariant**

Derselbe Ausreißer-Trade (`entry` 54,2440, Ziel 45,7890, Bewegung 8,4550 USD):

| Stop | risk USD | % von entry | `R` |
|---|---|---|---|
| tatsächlich (Cluster-Extremum + 0,05) | 0,2460 | 0,45 % | **34,3699** |
| hypothetisch 1 % | 0,5424 | 1,00 % | **15,5881** |
| hypothetisch 2 % | 1,0849 | 2,00 % | **7,7933** |

Der „+34-R-Gewinner" ist damit primär ein **Normalisierungsartefakt des zu
engen Stops**, nicht ein Markterfolg. Folge: `R` darf **nicht** über
verschiedene Stop-Settings verglichen werden (Block B). Pflicht für Block B:
Ausweis zusätzlich in **USD-Bewegung** und/oder **ATR-normiert**.

### E6 · Nebenbeobachtungen (Datenstand)

- **54/54 H2-Trades sind SHORT**, bei steigendem Markt (Entry-Preise 47,09 →
  54,24; H2-Spanne 45,53 → 56,53). Das System fadet systematisch den Aufwärtslauf.
- `PR_AUSSEN_NAEHE` liefert weiterhin **0 H2-Trades** (`kein_raum` 14 → 152) —
  auch unter `PHASE_RANGE`. Der Rollen-Envelope-Pfad bleibt handelslos.
- H1-`R_max` ist jetzt extrahiert: **+20,835855** (BASE gesamt `R_adj`
  −206,891794). Damit ist die frühere Definitionseinschränkung (D3) aufgelöst.

### E7 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_s2_e20_poc.py` | `ea2f1f1abcea0dedf9bfda4cb4faa03b234cd022b6fa2ad25f470d6da922888c` | 14.258 |
| `test/_tmp_s2_e20_poc_out.txt` | `2b7a8629b7ffba3c15f19256932cd656de02aa23b4a96754b8241454e9fad333` | 16.805 |
| `test/_tmp_e20_poc_diagnose.py` | `f2ecc7634f3ebfbd1b252ab21258aad1f279ebe6501e8a9b75d269714e8c0e24` | 4.438 |
| `test/_tmp_sha_liste.py` | `eef538cc6f050bc62adbdde9e9900370f4a39ec82ab82aa70dac1e2ba0c676e7` | 1.170 |

`*_stderr.txt` = leer (`e3b0c442…`). Engine `4a576a76…` und VD-Entwurf
`1615a4af…` unverändert.

### E8 · Offene Entscheidungen (Textblock)

1. **POC-Fenster vs. POC-Bars.** E-21 zeigt: das Problem ist nicht nur die
   **Preis**-Grenze (`unter, ober`), sondern auch das **Bar**-Fenster
   (`poc_start = 0`). Soll `poc_start` auf den **Phasen-/Konsolidierungsbeginn**
   (bzw. `k − lookback`) gesetzt werden, damit das Histogramm nur die aktuelle
   Balance abbildet? Ohne das bleibt der POC ein Randartefakt.
2. **Wirklichkeitsnähe `tp1 = poc`.** Ist ein Teilgewinn exakt am POC überhaupt
   die richtige Regel — oder gehört TP1 an eine **Strukturmarke** (z. B.
   Mittelband / 50 % der Phasenrange) und der POC nur zur Filterung?
3. **Block-B-Reihenfolge.** Soll Block B (Stop-Geometrie) **vor** Block A
   kommen? E-22 legt das nahe: solange der Stop degeneriert ist, ist jede
   R-basierte Messung — auch die von Block A — nicht interpretierbar.
4. **Metrik-Normierung für Block B.** Ausweis zusätzlich in USD-Bewegung
   (absolut) und ATR-normiert (relativ)? Beides ist mit E-22 neu zu beschließen.
5. **`JAHR`/L3840 bleibt verboten** (Riesenband-Falle, §12). Für Block A
   bestätigt: 960 = Erkennung, 480 = Bestätigung, Übergabe ereignisgetrieben.

---

## Phase 2 / E-23 (2026-09-11, g) — Offline-Matrix: **der Stop ist nicht das Problem**

Vor dem Aufsetzen von Block B wurde eine **selektions-invariante Offline-Matrix**
gerechnet: die 54 H2-Trades aus `LEGACY_CTRL` sind festgehalten, je Szenario
wird **nur der Engine-eigene Auflöser** `_c_loese_trade` durchgespielt. Laufzeit
< 1 s, kein Engine-Eingriff. Kontrolle: `LEGACY` reproduziert `−19,065650 R`
**exakt**.

**Dual-Ausweis (Beschluss 4) exakt**: `USD = R · risk` (Stück-PnL, da `R` auf
`risk` normiert ist), `ATR/Tr = USD / ATR14(k)` (kausal, BKZ-Reihe).
ATO14 am ersten Signal-Bar = **0,1584 USD**.

### F0 · Die Matrix (54 Trades, H2)

| Szenario | N | ablehn | R | R_adj | N_stop | Q_stop | USD/Tr | ATR/Tr |
|---|---|---|---|---|---|---|---|---|
| `LEGACY` | 54 | 0 | −19,065650 | −53,000000 | 53 | 0,981 | −0,0328 | −0,0463 |
| `POC_W480` (`poc_start` = k−480) | 53 | 1 | −15,193612 | −46,921717 | 51 | 0,962 | −0,0201 | +0,0585 |
| `POC_W960` (`poc_start` = k−960) | 54 | 0 | −16,193612 | −47,921717 | 52 | 0,963 | −0,0217 | +0,0412 |
| **`POC_SPLIT`** (`poc_start` = 17.692) | 52 | 2 | −13,250791 | −44,978896 | 49 | 0,942 | **−0,0072** | **+0,1335** |
| `TP1_MID` (tp1 = Mittelband 46,4556) | 54 | 0 | −19,984858 | −53,000000 | 53 | 0,981 | −0,0370 | −0,0792 |
| `POC_W960_MID` | 54 | 0 | −19,984858 | −53,000000 | 53 | 0,981 | −0,0370 | −0,0792 |
| `STOP_ATR15` (sl = max(sl, entry+1,5·ATR)) | 54 | 0 | **−2,138860** | −36,073209 | 52 | 0,963 | −0,0378 | −0,0011 |
| `STOP_ATR15_W960` | 54 | 0 | −2,116077 | **−33,844182** | 51 | 0,944 | −0,0379 | +0,0073 |
| `STOP_PCT1` (1 % Mindestabstand) | 54 | 0 | −22,074521 | −37,463965 | 51 | 0,944 | **−0,1998** | −1,3120 |
| `STOP_PCT1_W960` | 54 | 0 | −20,632475 | −35,021373 | 49 | **0,907** | −0,1878 | −1,1431 |
| `STOP_ATR30` (3·ATR) | 54 | 0 | −14,111940 | −35,985401 | 51 | 0,944 | −0,1697 | −0,7875 |
| `STOP_ATR50` (5·ATR) | 54 | 0 | −28,867164 | −41,991241 | 51 | 0,944 | −0,4673 | −2,6729 |
| `STOP_ATR50_W960` | 54 | 0 | −23,972801 | −36,243614 | 47 | 0,870 | −0,4053 | −2,2197 |

Risiko-Verteilung (USD): `LEGACY` 0,0410 / Median 0,1465 / 0,6460 ·
`STOP_ATR15` 0,1256 / 0,2320 / 0,6985 · `STOP_PCT1` 0,4685 / 0,5097 / 0,6460.

### F1 · Befund — die Stop-Verbreiterung ist ein **Normalisierungsartefakt**

`STOP_ATR15` verbessert `R_adj` von −53,000000 auf **−36,073209** (+16,93 R) —
aber `USD/Tr` **verschlechtert sich** von −0,0328 auf **−0,0378**, und
`ATR/Tr` bleibt ≈ 0. Der scheinbare Gewinn ist **allein** die R-Kompression
durch den größeren Nenner (`risk`), also genau das in **E-22** beschriebene
Artefakt. **USD ist die Wahrheit; R ist es nicht.**

Weiter: `Q_stop` fällt von 0,981 nur auf 0,963/0,944 und **erreicht in keinem
Szenario die Schwelle 0,75** (Bestwert `STOP_ATR50_W960` = 0,870). Eine
Verdopplung des Stops (1,5 → 3 · ATR) senkt `Q_stop` **nicht**
(51/54 beide), verschlechtert `USD/Tr` aber auf −0,170.

**⇒ Die Mentor-Hypothese „der Stop ist zu eng, der Markt atmet breiter" ist
durch die Daten widerlegt.** Die Trades sterben nicht am Mikrorauschen,
sondern weil sie **54/54 gegen den Trend** stehen; ein weiterer Stop verliert
pro Trade **mehr**, nicht weniger.

### F2 · Befund — der **POC** ist der reale (kleine) Hebel, `tp1` praktisch irrelevant

- `TP1_MID` und `POC_W960_MID` sind **identisch** zu `LEGACY` in `R_adj`
  (−53,000000) und `N_stop` (53): die TP1-Wahl ändert **ausschließlich den
  einen Gewinner**. Für die 53 Verlierer wird TP1 **nie** vor dem SL erreicht.
  ⇒ `tp1 = poc` vs. `tp1 = Mittelband` ist **kein Hebel** (E-21 bleibt als
  Diagnose richtig, aber als Fix wirkungslos).
- `POC_SPLIT` verbessert `USD/Tr` auf **−0,0072** (von −0,0328; Faktor 4,6)
  und `ATR/Tr` auf **+0,1335**; `N_stop` fällt 53 → 49. Das ist ein
  **echter** Effekt: ein höher liegender POC macht TP1 für einige Trades
  erreichbar. Aber der Bestwert bleibt **negativ**.
- **`POC_SPLIT` ist ein Grenzfall**: `poc_start` = 17.692 → alle Bars ab Split
  liegen über der Range → Clamping in den **obersten** Bin → `tp1` = 47,0888
  = konstant `tp2` + 1,2998. Der Effekt kommt also aus einem weiteren
  Randartefakt, nicht aus einem echten Akzeptanzniveau (E-21 bleibt gültig).

### F3 · Blocker — `poc_start = segment.start_bar` ist **nicht definiert**

`SegmentVD('P_K408_409', …, erwarteter_start_bar=None)` — das endogene
Segment hat **keinen** Start-Bar. Der in Beschluss 1 verlangte Fix
(`poc_start = segment.start_bar`) ist damit **erst nach Block A** verfügbar
(zirkuläre Abhängigkeit: POC-Sanierung braucht das Phasenfenster, das Block A
liefert). Proxy für eine Zwischenmessung: `poc_start = k − 960` (bzw. 480).

### F4 · Bilanz und Empfehlung (Textblock — Entscheidung offen)

1. **Kein Szenario erreicht ein positives Ergebnis.** Alle 13 Läufe bleiben
   bei negativem `USD/Tr` und `Q_stop ≥ 0,870` → nach **D2** **sämtlich
   disqualifiziert**.
2. **Die Priorität kehrt sich um.** Nach `USD/Tr` ist **POC/Bar-Fenster** der
   wirksame Hebel (Faktor 4,6), die **Stop-Verbreiterung schadet**. Die
   Beschlussfolge „(B) vor (A)" ist auf Basis von F1 **nicht mehr gestützt**.
3. **Der eigentliche Edge fehlt im Einstieg**, nicht im Exit: 54/54
   Counter-Trend-Shorts (`USD/Tr` bleibt in **allen** Exit-Varianten negativ).
   Der Regime-/Expansionsfilter (Block A) ist damit **nicht Vorbereitung,
   sondern die Kernmaßnahme**.
4. **Offene Entscheidung (Anwender):** Bleibt es bei (B) zuerst — oder wird
   auf **POC-Fenster zuerst** (mit `poc_start = k − 960` als Proxy, da
   `segment.start_bar` fehlt) umgestellt und Block A **vorgezogen**?
   Eine dritte Option: zuerst den **Regime-Filter** isoliert messen
   (Short-Verbot bei Expansion über `decke`), weil F3/F1 auf die
   Einstiegsseite zeigen.

**Kein Produktivcode, kein §75, kein S1-Cache.** Die Offline-Matrix ist
read-only und hat den Engine-SHA `4a576a76…` nicht berührt.

### F5 · Erratum E-23 (Präzision)

Die E-22-Tabelle hatte `entry · 0,01` auf `0,5424` und `entry · 0,02` auf
`1,0849` **gerundet**; korrekt ist `entry · 1 % = 0,542440` bzw.
`1,084880`. R exakt:

| risk | % | R |
|---|---|---|
| 0,244098 | 0,45 % | 34,637727 |
| 0,542440 | 1,00 % | **15,586977** (Handoff sagte 15,5881) |
| 1,084880 | 2,00 % | **7,793489** (Handoff sagte 7,7933) |
| 0,246000 | tatsächlich | 34,369919 |

Die Korrektur ist < 0,002 R und ändert keine Aussage.

### F6 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e23_offline_matrix.py` | `7e888a35c660d17b1264d5e252a37d39667642419797e58ebbdee48d483929d9` | 9.709 |
| `test/_tmp_e23_offline_matrix_out.txt` | `392cc3f050edeb6a22221bb5e0fbbf872abd974e41c499bfecce1f4e71a982fd` | 5.612 |

---

## Phase 2 / E-24 (2026-09-11, h) — Regime-Gate-Analyse: **der Bruch liegt vor dem ersten Trade**

Read-only, offline (`_tmp_e24_regime_gate.py`, Laufzeit < 1 s): die 54
LEGACY-H2-Trades sind festgehalten, je Gate-Variante wird **nur die Selektion**
variiert. Engine-SHA `4a576a76…` unberührt.

Zwei Decken-Definitionen × `n_closes` ∈ {1, 2, 3} × Puffer ∈ {0 %, 0,5 %}.

### F0 · Befund — der Erstbruch liegt **5 Bars vor dem ersten Signal**

| Ereignis | Bar | Zeit (BKZ) |
|---|---|---|
| erster Close > `K408` (47,1221) | **17.707** | 2025-10-01T03:45 |
| erster Bar mit **2** Closes > 47,1221 | **17.708** | 2025-10-01T04:00 |
| erster Bar mit **3** Closes > 47,1221 | 17.709 | 2025-10-01T04:15 |
| **erster Trade-Signal-Bar k** | **17.712** | — |
| erster Entry | 17.713 | — |

Das `K408`-Dach (Split-Konsolidierung, 47,1221) war zum Zeitpunkt des ersten
Signals **bereits seit 5 Bars gebrochen**. Das System hatte **keinerlei
Regime-Wahrnehmung**: `close > STATIC` gilt für **52 von 54** Trades.

### F1 · Gate-Matrix (Short-Verbot bei Expansion)

| Decke | n | Puffer | behalten | gefiltert | R | R_adj | USD/Tr | ATR/Tr | N_stop | Q_stop |
|---|---|---|---|---|---|---|---|---|---|---|
| `STATIC` | 1/2/3 | 0 % / 0,5 % | **2** | **52** | −2,000000 | −2,000000 | −0,2060 | −1,3964 | 2 | **1,000** |
| `ROLL` | 1/2/3 | 0 % | 53 | 1 | −18,065650 | −52,000000 | −0,0265 | −0,0058 | 52 | 0,981 |
| `ROLL` | 1/2/3 | 0,5 % | 54 | 0 | −19,065650 | −53,000000 | −0,0328 | −0,0463 | 53 | 0,981 |

**Die Parameter `n_closes` und Puffer sind empirisch wirkungslos** — sämtliche
Zellen sind in jeder Decken-Zeile identisch. Die einzige wirksame Variable ist
die **Wahl der Decke**.

### F2 · Befund — beide Decken-Definitionen sind als Gate unbrauchbar

- **`STATIC` (K408 = 47,1221) = Not-Aus, kein Filter.** Es überleben genau die
  zwei Trades, deren Signal-Bar **unter** dem Dach lag (`k` 17.712 mit
  `close` 47,0870 und `k` 17.871 mit 46,8490) — und **beide verlieren**
  (−1,0 R). `Q_stop` = **2/2 = 1,000**. Der absolute USD-Verlust sinkt von
  −1,77 auf −0,41, aber das ist die Aussage „**am besten gar nicht handeln**",
  nicht ein Edge.
- **`ROLL` (laufende Außenwand) = inert.** Nur **1 von 54** Trades liegt über
  der rollenden Decke (`entry` 18.465, `close` 51,2550 > 51,2200). Ursache:
  die rollende Außenwand **folgt dem Preis** — ab Bar ~18.824 steht sie
  konstant bei 54,3610, während die Closes 48–54 bleiben. Ein
  Expansionsdetektor, der sich mit dem Markt mitbewegt, kann keinen Bruch
  detektieren.

**⇒ Aus `F2` folgt eine harte Design-Bedingung:** Ein Expansions-Gate braucht
ein **festes (deklariertes) Niveau**, das nicht mit dem Preis wandert — aber
ein **dauerhaft** festes Niveau wird nach dem ersten Bruch zum Not-Aus. Das
Niveau muss daher **je Konsolidierung neu deklariert** werden. Genau das ist
Block A — und damit ist Block A **nicht** optional, sondern die
Voraussetzung für jedes Regime-Gate.

### F3 · Antwort auf Klärungsfrage 1 (N Closes vs. N Closes + Puffer)

**Die Frage ist empirisch nicht diskriminierend.** `n_closes` 1/2/3 und
Puffer 0 %/0,5 % liefern **identische** Ergebnisse in allen 12 Zellen. Der
Grund: nach dem Erstbruch liegt der Preis so weit über dem Niveau, dass jede
Schwelle 1..3 und jeder Puffer bis 0,5 % gleichzeitig erfüllt ist. **Empfehlung:**
die Gate-Parameter **nicht** feinjustieren; die Freiheitsgrade liegen in der
**Niveau-Semantik** (fest + periodisch neu deklariert) und in der
**Rückkehr-Bedingung** (wann darf wieder gehandelt werden).

### F4 · Präzisierung von Leitfrage 2 (Anzahl eliminierter Shorts)

**52 von 54** würden durch ein 2-Close-Gate über `K408` eliminiert. Das ist
**kein Erfolg**: die zwei Überlebenden sind beide Verlierer, und das Gate
entspricht einem Handelsverbot in 96 % der Fälle. Die relevante Zahl ist
nicht „wie viele werden gefiltert", sondern: **der Bruch lag vor dem ersten
Signal** (`F0`) — die Handelszone war zum Start bereits ungültig.

### F5 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e24_regime_gate.py` | `08444abe2805d7507c51b0e25d92414d55068dbbdd4255358178422dc2706eba` | 8.128 |
| `test/_tmp_e24_regime_gate_out.txt` | `a5fcf2e308689ce3ddea656f5e61b77bbea74b8f24b1787e68cf184e6cd9a252` | 5.348 |

### F6 · Offene Entscheidungen (Textblock)

1. **Rückkehr-Bedingung fehlt.** Das Gate sagt nur, wann Shorts **verboten**
   sind. Es fehlt die symmetrische Regel, **wann ein Reclaim wieder feuern
   darf** („Ausbruchszone zurückgeholt" / neue Balance). Ohne sie ist das
   Gate einseitig.
2. **Niveau-Deklaration.** Wie wird das feste Niveau je Konsolidierung
   bestimmt und wann neu deklariert? Kandidaten: `AUSSEN_OBEN` zum
   Phasenbeginn eingefroren; oder der Hochpunkt der letzten
   `PREISNAH`-Konsolidierung (`§12`: K408 → K494 → K547).
3. **Scope.** Gilt das Gate nur für SHORT (Expansion nach oben) oder
   symmetrisch auch für LONG (Expansion nach unten)? In H2 gibt es 0 LONGs —
   in H1/S1 aber nicht.
4. **Reihenfolge.** Bleibt es bei Block A zuerst? `F2` sagt **ja**, aber die
   Analyse zeigt: Block A muss das **Niveau-Deklarationsverfahren** liefern,
   sonst ist das Gate wirkungslos.

---

## Phase 2 / E-25 (2026-09-11, i) — Regime-Zustandsautomat: **das Gate ist anti-selektiv**

Der in E-24 (`F2`) geforderte Zustandsautomat wurde als read-only
Vorwärts-Simulation implementiert und gegen die 54 H2-Trades (LEGACY-Basis,
`tp2` = 45,7890) gemessen. **Ergebnis vorweg: jede untersuchte
Deklarationsquelle erzeugt `Q_stop` = 1,000 und tötet den einzigen Trade mit
positivem USD.**

### F1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e25_state_machine.py` | `ac00748ed82646e2f4cd08d4a7056bb887b8f30b386957e2a85de1f1176406e0` | 17.923 |
| `test/_tmp_e25_state_machine_out.txt` | `ffad99061b0d306304df96d48dbeac923c6eaae9cc9a42c6e227b25294016164` | 7.029 |
| `test/_tmp_e25_probe.py` | `fcc9283ecd415c0e47bd500f10cf17faa9204ad616a89c2c6260ad8339e48007` | 2.358 |
| `test/_tmp_show_tail.py` | `7c816c136b23f93605cb280e0975ff12eac23ebf7eda95936f8f3eed48874a70` | 671 |
| `test/_tmp_grep.py` | `5aeedceb72ea39b72fc1da01433b3ac33b9ae365823318db38430145b130fc1c` | 525 |

### F2 · Q3 — ATR-Ordnungen (USD)

| Bar | Datum (BKZ) | ATR14 | ATR480 | ATR960 | 1,5 · ATR960 |
|---|---|---|---|---|---|
| 17.692 | 2025-10-01T00:00 | 0,0759 | 0,1206 | 0,1073 | 0,1609 |
| 18.172 | 2025-10-08T05:00 | 0,1539 | 0,1359 | 0,1282 | 0,1924 |
| 18.824 | 2025-10-17T08:00 | 0,1272 | 0,2312 | 0,1933 | 0,2899 |
| 20.000 | 2025-11-05T03:15 | 0,1504 | 0,1495 | 0,1656 | 0,2484 |
| 21.552 | 2025-11-28T02:45 | 0,1107 | 0,1687 | 0,1885 | 0,2827 |

Vergleichsgrößen: Split-Konsolidierung K408/K409 = **1,3331 USD** · §12-Kette
1,19–2,98 USD · typische 96-Bar-Range 0,7–0,9 USD · H2-Spanne 10,9950 USD.
⇒ Die Spec-Schwelle `Spanne < 1,5 · ATR960` (0,161–0,290 USD) liegt um den
Faktor **≈ 7–10 zu niedrig** für die Objekte, die sie finden soll.

### F3 · Q1 — Pfad A ist nicht diskriminierend

- **Erstbruch** (2 Closes > 47,1221): Bar **17.708** (2025-10-01T04:00).
- **Pfad A** (2 konsekutive Closes zurück unter das Dach) feuert bei Bar
  **17.713** — 5 Bars nach dem Bruch und **1 Bar vor dem ersten Entry**
  (17.713). Danach **202 Bars** mit erfüllter Bedingung (erste fünf
  17.713…17.717, letzte fünf 19.988…19.994).
- Varianten: 3 Closes < Decke → 193 Treffer (erster 17.714) · 2 Closes <
  Mittelband 46,4556 → 27 (erster 17.851) · 1 Close < Mittelband → 34 (17.850) ·
  2 Closes < Boden 45,7890 → 3 (erster 19.478).

⇒ Pfad A öffnet sofort wieder und bleibt nahezu durchgehend offen. Als
Rückkehr-Bedingung **untauglich**; allein Pfad B könnte diskriminieren.

### F4 · Q2 — Pfad B in der ratifizierten Form findet **nichts**

`≥ 3 Pivots (touch_conf ≥ 3)` im 480er-Fenster, **beidseitig**, mit
`Spanne < 1,5 · ATR960`: **0 Deklarationen** über ganz H2.
Kalibrierung `Spanne < m · ATR960`:

| m | 1,5 | 3,0 | 5,0 | 10,0 | 20,0 |
|---|---|---|---|---|---|
| Deklarationen | 0 | 0 | 0 | **2** | 15 |

Erste Niveaus bei m = 10: `K@18.326 49,0520/47,7200` · `K@20.761
51,2840/50,3900`. Sensitivität (m = 10): `min_touch` 2 → 1–2,
3 → 2–4, 4 → 2–5 Deklarationen; `min_pivots` 4 setzt m=10/touch=2 auf 0.

### F5 · Erratum E-25 — die §12-Kette ist **kein** Pfad-B-Objekt

Die §12-Auflösung (äußerste **lebende** Kante im 960er-Fenster) ist ein anderes
Objekt als eine Pivot-Balance: sie liegt konstruktionsbedingt am Fensterrand
(40-Tage-Hoch/Tief) und ist damit **nicht durchbrechbar**; der Pivot-Ansatz
liefert dagegen **innere** Bänder (49,05/47,72). Beide sind nicht ineinander
überführbar. ⇒ Das Kalibrierungsziel „m reproduziert die §12-Kette" ist
**falsifiziert**.

### F6 · Q2e — das `L960`-Verfahren reproduziert §12 **exakt** (validiert)

| Bar | §12-Soll (Decke/Boden) | `_paar_l960` (Ist) | Status |
|---|---|---|---|
| 17.692 | K408 47,1221 / K409 45,7890 | 47,1221 / 45,7890 | **identisch** |
| 18.172 | K436 48,6289 / K424 47,3247 | 48,6289 / 47,3247 | **identisch** |
| 18.652 | K494 52,4444 / K493 50,4759 | 52,4444 / 50,4759 | **identisch** |
| 19.612 | K429 48,3972 / K404 46,7691 | 48,3972 / 46,7691 | **identisch** |
| 20.572 | K547 54,2750 / K484 51,4427 | 54,2750 / 51,4427 | **identisch** |

Zwischenwerte (Schritt 480): 19.132 → 49,3040/47,6879 · 20.092 →
48,2710/47,0418 · 21.052 → 52,3420/50,2749 · 21.532 → 53,8797/52,6873.
⇒ Der Neu-Deklarations-Primitiv ist **reproduzierbar**; Pfad B muss auf ihm
aufsetzen, nicht auf Pivot-Touch-Zählung.

### F7 · Q2d — Entscheidend: alle Gates sind anti-selektiv

| Quelle | Neu-Dekl. | Zustände BAL/EXO/EXU | erlaubt | verboten | R (erlaubt) | R_adj | USD/Tr | ATR/Tr | Q_stop | getötete Gewinner |
|---|---|---|---|---|---|---|---|---|---|---|
| **OHNE GATE (54)** | – | 3932/0/0 | 54 | 0 | −19,065650 | −53,000000 | −0,0328 | −0,0463 | 0,981 | – |
| PIVOT m=10 | 2 | 1259/2161/512 | 17 | 37 | −17,000000 | −17,000000 | −0,1581 | −1,2133 | **1,000** | 1 |
| PIVOT m=20 | 18 | 1282/1098/1552 | 30 | 24 | −30,000000 | −30,000000 | −0,1679 | −1,2129 | **1,000** | 1 |
| L960-SEG | 228 | 3396/467/69 | 46 | 8 | −46,000000 | −46,000000 | −0,1915 | −1,2526 | **1,000** | 1 |
| STATIC K408 (E-24) | – | – | 2 | 52 | −2,000000 | −2,000000 | −0,2050 | – | **1,000** | 1 |

Die OHNE-GATE-Zeile reproduziert E-23/`LEGACY` **bit-identisch** (R
−19,065650 · R_adj −53,000000 · USD/Tr −0,0328 · ATR/Tr −0,0463 · Q_stop
0,981) — die Risikobasis `|sl − open[entry_bar]|` ist damit gegen E-23
abgeglichen (Avg-Risiko 0,1919 USD, Summen-USD −1,7711).

Entscheidende Zahlen:

- Der **einzige** Trade mit `R > 0` ist `k` 18.824 mit **R +33,934350**. Er wird
  von **allen** Gate-Varianten verboten.
- **Summen-USD:** OHNE GATE **−1,7711** · PIVOT m=10 −2,6877 · PIVOT m=20
  −5,0370 · L960-SEG −8,8090. **Jedes Gate verschlechtert den Gesamt-USD.**
- `R_adj` erscheint bei allen Varianten besser (−17 / −30 / −46 ≫ −53), aber nur,
  weil der Wegfall des Gewinners `R_max` vernichtet: `R_adj = R` **ohne jeden
  positiven Beitrag**. Nach `D2` wären alle drei zulässig — **`D1`
  (`Q_stop` > 0,75) schließt sie alle kategorisch aus.**

### F8 · Interpretation (kein Auswahlmenü)

1. Ein Regime-Gate, das nach dem Bruch **Short verbietet**, verbietet in H2 den
   Regelfall: alle 54 Trades sind SHORT, und laut E-24 `F0` war die Handelszone
   bereits beim ersten Signal ungültig.
2. Das Gate ist **kein Filter, sondern eine Auswahl der Verlierer**. Die Ursache
   liegt nicht in der Güte des Zustandsautomaten, sondern darin, dass der
   einzige Gewinner **im** Expansionsbereich liegt — das Gate entfernt genau die
   Prämie, die die Strategie trägt.
3. Der einzige Gewinner ist zudem ein **Artefakt der `tp2`-Umstellung**
   (`VD_K408_409`, E-20): unter der Baseline (`tp2` 28,4320) ist derselbe Trade
   ein Stop. Was das Gate tötet, ist die V-D-Zielwahl — kein Edge.

### F9 · Offene Entscheidungen (Textblock)

1. **Pfad B neu definieren.** Der Pivot-Ansatz ist widerlegt (E-25); das
   validierte Verfahren ist `L960` (§12, reproduzierbar nach F6). Offen ist die
   **Breitenbedingung**: §12-Bänder sind 1,19–2,98 USD breit (≈ 6–16 · ATR960).
   Soll Pfad B **ohne** Spannen-Kriterium arbeiten — jede `L960`-Neuauflösung
   ist eine neue Balance — oder mit `Spanne < m · ATR960`, m ∈ [10, 16]?
2. **Neu-Deklarations-Takt.** `L960` wechselt in H2 **228×** (≈ alle 17 Bars)
   und setzt jedes Mal auf `BALANCE` zurück; der Automat wird dadurch weitgehend
   inert (3396/3932 Bars `BALANCE`). Ist die Hybrid-Schließung (Neu-Deklaration
   **nur** aus `EXPANSION_*` heraus) verbindlich?
3. **Gate-Richtung prüfen.** Da alle H2-Trades SHORT sind und der Automat nur
   SHORT verbietet, ist „Gate aktiv" derzeit deckungsgleich mit „Handel
   eingestellt". Ist das der Zweck — oder soll das Gate **LONG freigeben**?
4. **`R` / `R_adj` als führende Metrik.** `R_adj` erweist sich hier als
   **irreführend** (besser, obwohl der USD schlechter wird). Bleibt Beschluss 4
   (USD/ATR führend, R sekundär) bestehen — und wird `R_adj` künftig **neben**
   `USD/Tr` ausgewiesen, statt als Zulassungskriterium zu dienen?

Bis zu diesen Entscheidungen unverändert: **kein Einbrand in
`backtest_lab/phasen_regime_adapter.py`, kein §75, kein S1-Cache.**

---

## Phase 2 / E-26 (2026-09-11, j) — Long-Blockade: **Q29 referenziert das Gesamt-Extrem**

Beantwortet Phase 2 des Explorationsplans: *„Warum emittiert die Engine in
S2-H2 exakt 0 Long-Trades?"* Antwort: **nicht wegen `KANDIDAT_NONE`, nicht
wegen fehlender Pivots und nicht wegen der Makrowaende — sondern weil Q29
(`_im_aussenquartil`) seinen Bezug auf das laufende **Gesamt**-Extrem seit
Bar 0 nimmt.** Im Aufwaertstrend ist die Long-Seite dadurch strukturell
gesperrt.

### F1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e26_long_blockade.py` | `9a4b9143d81985379d3a98430026983da42dfe14ef7054aba8d8cee8f53e57e1` | 13.298 |
| `test/_tmp_e26_long_blockade_out.txt` | `4694c867c0362fdbb4834cb2e7e7e130bd66fcf571798da723c70d4c7221dfb2` | 19.895 |
| `test/_tmp_slice.py` | `3d8562869f9f4697c9ea25db7264989f72f849772adc36a840f54e1b917e1edb` | 406 |

### F2 · Verfahren (kein Neubau der Logik) und Fidelity-Nachweis

`_se_trades` wird per **AST** aus der arretierten Engine extrahiert
(Zeilen **2361..2769**, 409 Zeilen), in einer Kopie der Engine-Globals
ausgefuehrt und **ausschliesslich in der Buchfuehrung** ersetzt:

- `stats["X"] += 1` → `_hit(_CUR, "X")` — **14 Ersetzungen**;
- nach `kd = _kandidat(...)`: `kaskade_leer` bzw. `kandidat` + Detailzeile;
- `stufe_n == 0` → `stufe0`; Dedup → `dedup`; erfolgreicher Abschluss → `SETUP`;
- `_CUR[0] = k`, `_CUR[1] = richtung` am Kopf der Richtungsschleife.

Die Entscheidungslogik bleibt **byte-gleich**. **Fidelity-Nachweis:**
Laufgrenze `scan["box_end_bar"] = n` (der Cache traegt dort 17.692 = Split)
liefert **299 Setups (LONG 5 / SHORT 294)** — identisch zur in
`_tmp_s2_vd_stresstest.py` gemessenen `BASE`-Menge (299). Damit ist die
Instrumentierung als verhaltensneutral belegt.

### F3 · Trichter je Richtung und Haelfte

| Richtung / Haelfte | Kandidaten | M6 | **Q29** | `stufe0` | Q24 jung | Zyklus | Raum | **SETUP** |
|---|---|---|---|---|---|---|---|---|
| SHORT H1 | 1972 | 286 | 301 | 611 | 112 | 520 | 14 | **240** |
| SHORT H2 | 334 | 46 | 14 | 136 | 43 | 84 | 0 | **54** |
| LONG H1 | 894 | 0 | **882** | 5 | 60 | 2 | 0 | **5** |
| LONG H2 | 144 | 0 | **144** | 0 | 28 | 0 | 0 | **0** |

**Jeder einzelne** LONG-Kandidat in H2 (144/144, 100 %) stirbt an Q29. Kein
einziger erreicht `_reclaim_stufe`. Die vollstaendige Kandidatenliste steht in
`_tmp_e26_long_blockade_out.txt` Z. 100..211; **alle** Zeilen tragen das
Sterbe-Gate `quartil_blockiert`.

### F4 · Ursache: Q29 vergleicht mit dem Gesamt-Extrem (Zeilen 2434/2435)

```python
ex_hi = float(np.max(hi[:k + 1]))     # <-- seit Bar 0, NICHT lokales Fenster
ex_lo = float(np.min(lo[:k + 1]))
distanz = ((ex_hi - sweep_px) if richtung == "SHORT"
           else (sweep_px - ex_lo)) / spanne * 100.0
return distanz <= cfg.quartil_distanz_pct          # 25.0
```

Gemessene Zeitreihe (Ausschnitt, H2):

| Bar | Datum | `ex_lo` | `ex_hi` | Spanne | LONG-Schwelle | `lo[k]` | Q29-Dist | Status |
|---|---|---|---|---|---|---|---|---|
| 17.692 | 2025-10-01 | 28,2860 | 47,1580 | 18,8720 | 33,0040 | 46,6110 | 97,1 % | GESPERRT |
| 18.172 | 2025-10-08 | 28,2860 | 48,7500 | 20,4640 | 33,4020 | 48,3120 | 97,9 % | GESPERRT |
| 18.652 | 2025-10-15 | 28,2860 | 53,5030 | 25,2170 | 34,5902 | 52,7040 | 96,8 % | GESPERRT |
| 20.092 | 2025-11-06 | 28,2860 | 54,4460 | 26,1600 | 34,8260 | 47,7500 | 74,4 % | GESPERRT |
| 21.532 | 2025-11-27 | 28,2860 | 54,4460 | 26,1600 | 34,8260 | 53,2470 | 95,4 % | GESPERRT |

**Endstand: `ex_lo` = 28,2860 (seit dem Fensterbeginn nie revisited,
eingefroren), `ex_hi` = 56,5250, Spanne 28,2390.**
Die LONG-Schwelle waere `lo[k] ≤ 35,3458 USD`. Das **H2-Tief ist 45,5300** —
**10,1842 USD ueber der Schwelle**. Q29-Distanzen liegen in H2 bei
**74,4 % bis 98,2 %**; die Zulassungsschwelle ist **25 %**.

⇒ Ein LONG ist in H2 **nicht unwahrscheinlich, sondern unmoeglich** — es sei
denn, der Preis kehrt auf ≤ 35,35 USD (Jahrestief) zurueck.

### F5 · Vergleichsgruppe: die 5 gelungenen H1-LONGs

| Bar | Datum | Kante | Q29-Dist | R | close |
|---|---|---|---|---|---|
| 6.120 | 2025-04-04 | K20 | 15,5 % | −1,00000 | 29,7770 |
| 6.121 | 2025-04-04 | K6 | 8,6 % | −1,00000 | 29,6430 |
| 6.131 | 2025-04-04 | K2 | 5,5 % | −1,00000 | 29,3650 |
| 6.323 | 2025-04-08 | K14 | 21,7 % | −1,00000 | 29,7660 |
| 6.343 | 2025-04-09 | K6 | 16,3 % | **+16,71116** | 29,4980 |

Alle fünf LONGs des gesamten S2-Fensters liegen im **April 2025** bei
**29,3–29,8 USD** — also unmittelbar am Jahrestief, wo Q29-Distanzen von
5,5–21,7 % (≤ 25 %) ueberhaupt erreichbar sind. Das ist die
Bestaetigungsgruppe: der LONG-Pfad feuert **nur am globalen Tief**, nie im
Trend.

### F6 · Interpretation

1. **Die Engine ist nicht marktblind, sondern Q29-blind.** Die Diagnose
   „54 Shorts bei 0 Longs in einem 11-USD-Aufwaertstrend" hat eine rein
   mechanische Ursache: Q29 misst die Distanz zum **laufenden Gesamt-Extrem**.
   In einem Trend waechst `ex_hi` mit dem Preis, waehrend `ex_lo` einfriert —
   die Long-Seite wird dadurch **monoton zugesperrt**, die Short-Seite
   (Distanz zu `ex_hi`) bleibt offen.
2. **Dieselbe Fehlerklasse wie E-17/E-25:** ein Gate, dessen Referenz ein
   **globales/lookback-weites Extrem** statt eines **lokalen, regime-relativen**
   ist. In Trendphasen wird diese Referenz stale.
3. **Konsequenz fuer Beschluss 3 (Long-Freigabe).** Ein Zustandswechsel nach
   `EXPANSION_OBEN` kann **keine** Longs erzeugen, solange Q29 unveraendert
   gegen das Gesamt-Extrem prueft. Die „Long-Freigabe" ist damit **kein
   Automaten-, sondern ein Q29-Problem** und muss vor jeder Automatikarbeit
   entschieden werden.

### F7 · Ratifizierte Entscheidungen (Anwender, 2026-09-11 j)

1. **Pfad B = `L960` rein strukturell, ohne ATR-Spannenschwelle.** Eine starre
   `m · ATR960`-Schwelle ist Kurvenanpassung an eine empirisch nicht
   existierende Pivot-Dichte (E-25). Die `L960`-Grenzen aus §12 (Spannweiten
   1,19–2,98 USD) spiegeln die tatsaechlichen Fensterraender.
2. **Hybrid-Schliessung verbindlich.** Eine neue Balance darf **nur** nach
   formaler Terminierung des vorherigen Regimes durch `STRUKTUR_BRUCH`
   (2 Closes jenseits des Bands) gesucht und deklariert werden. Das
   kontinuierliche Zuruecksetzen (228 freie Resets) ist ausgeschlossen; es
   hebelt den Zustandsautomaten aus (3396/3932 Bars `BALANCE`).
3. **Gate-Richtung: Long-Freigabe zwingend pruefen** — siehe F6.3 (Q29-Blocker
   vorgelagert).
4. **Metrik-Hierarchie geaendert: `USD/Trade` ist fuehrend** (mit `ATR/Trade`
   als beigeordneter Normierung). `R` und `R_adj` sind **nur deskriptiv**;
   `R_adj` ist als Zulassungskriterium **degradiert** — eine Metrik, die bei
   −8,81 USD besser aussieht als bei −1,77 USD, darf keine Weichen stellen.

**Folge fuer Phase 1 (`D2`):** Das Kriterium „`R_adj` ≤ Baseline-`R_adj` →
verworfen" ist damit **ausgesetzt**. `D1` bleibt in Kraft:
**`Q_stop` > 0,75 → Uebernahme kategorisch ausgeschlossen.**

### F8 · Offene Entscheidungen (Textblock)

1. **Q29-Referenz.** Drei Wege sind denkbar und muessen entschieden werden:
   (a) Q29 ganz auf lokale Fenster (480/960) umstellen;
   (b) Q29 richtungsasymmetrisch fuehren (SHORT Gesamt-Extrem, LONG lokales
   Tief); (c) Q29 fuer den LONG-Pfad abschalten und die Auswahl dem
   Zustandsautomaten ueberlassen. Ohne Entscheidung bleibt die Long-Seite tot.
2. **Geltungsbereich.** Aendert die Q29-Korrektur die 294 SHORTs? `_im_aussen
   quartil` ist richtungsunabhaengig kodiert — jede Aenderung trifft auch
   SHORT und damit die Baseline. Es muss daher zuerst geklaert werden, ob die
   Q29-Korrektur **regressionsfrei** (SHORT-Ergebnisse bit-identisch) moeglich
   ist oder ob sie S2 neu aufsetzt.
3. **Reihenfolge.** E-26 liegt **vor** der Automatikarbeit. Es wird
   vorgeschlagen: erst Q29-Entscheidung, danach Hybrid-Schliessung auf `L960`,
   zuletzt der Zustandsautomat.
4. **Beschluss 4 verlangt Nachlauf:** Die Phase-1-Ratifikation (`D1`–`D4`)
   ist um die Degradierung von `R_adj` zu korrigieren. Bis dahin gilt der
   Stand in F7.4.

Bis zu diesen Entscheidungen unveraendert: **kein Einbrand in
`backtest_lab/phasen_regime_adapter.py`, kein §75, kein S1-Cache.**

---

## Phase 2 / E-27 (2026-09-11, k) — Q29-Lokalisierung: **die Long-Seite ist heilbar**

Ratifiziert wurde Weg **(a)**: Q29 symmetrisch auf das lokale Erkennungsfenster
umstellen — keine Richtungs-Asymmetrie, kein Abschalten. Gemessen wurden
`GLOBAL (0..k)` als Kontrolle und `LOKAL 960` / `LOKAL 480`.

### F0 · Erratum der Messmethodik (wichtig, betrifft alle kuenftigen Laeufe)

`_se_trades` **mutiert den Kantenzustand** (`letzter_signal_bar`,
`letzter_sweep_bar`, `cluster_hoch`, `cluster_tief`). Mehrere Q29-Varianten in
**einem** Prozess sind daher **kontaminiert** — der erste E-27-Entwurf lieferte
genau deshalb falsche Werte (`LOKAL 960` = 106 Setups / 51 SHORTs). Der
kontaminierte Output wurde geloescht. **Regel: ein Variantenlauf = ein
Prozess.** Alle unten genannten Zahlen stammen aus je einem frischen Prozess.

### F1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e27_q29_lokal.py` | `3489afacb03bf79e25827b76277b39565e0b113c2346ad06493b344d23d0ad26` | 8.750 |
| `test/_tmp_e27_q29_lokal_s2_0_out.txt` | `cadd1fd91c9b83880cef2552b0d5221cd0d1f1c134a1ff017f73c8e80f9f55e2` | 33.676 |
| `test/_tmp_e27_q29_lokal_s2_960_out.txt` | `03109fb9cf857d311d4537731820b04e4a82d716029eed4dbc775063bc333dcc` | 29.565 |
| `test/_tmp_e27_q29_lokal_s2_480_out.txt` | `a98e18f5909cf845dae7d9073367218866b12e03499326d19d170c1977a1b1f4` | 35.398 |
| `test/_tmp_e27_q29_lokal_aug_0_out.txt` | `a4e6b7db0c65fc1800247406109e2b0b6860074f18dd3144de5d6fd4fda6726f` | 2.233 |
| `test/_tmp_e27_q29_lokal_aug_960_out.txt` | `1f08e73abe6aa9a9785d38cbe85f8eab527528ca617604a21ec945543a9fd9ac` | 2.231 |
| `test/_tmp_e27_q29_lokal_aug_480_out.txt` | `104d579f6c0238a71fb025e849f4cdb296161cc0d4cfa6bd36f34826a8bb1c44` | 2.123 |

**Eingriff (einzige Aenderung, Zeilen 2434/2435 der Engine):**

```python
ex_hi = float(np.max(hi[:k + 1]))       # vorher: global seit Bar 0
ex_lo = float(np.min(lo[:k + 1]))
# -> _a29 = _LB0(k)   # 0 = global; k-LB+1 fuer lokalen Lookback
ex_hi = float(np.max(hi[_a29:k + 1]))
ex_lo = float(np.min(lo[_a29:k + 1]))
```

### F2 · Schritt 1 — S2 (Laufgrenze `box_end_bar = n` = 21.624, Split 17.692)

| Variante | n ges. | R ges. | R_adj | USD | USD/Tr | ATR/Tr | Q_stop | LONG | SHORT | H1 n | H2 n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **GLOBAL 0..k** | 299 | −186,055940 | −206,891794 | −20,1030 | −0,0672 | −0,9094 | 0,799 | 5 | 294 | 245 | 54 |
| **LOKAL 960** | 261 | **−70,813603** | −91,649458 | **−5,3805** | −0,0206 | −0,3367 | 0,667 | **59** | 202 | 221 | 40 |
| **LOKAL 480** | 315 | −90,046026 | −123,416092 | −10,0489 | −0,0319 | −0,4306 | **0,644** | 82 | 233 | 260 | 55 |

Nur H2:

| Variante | H2 n | H2 R | H2 R_adj | H2 USD/Tr | H2 ATR/Tr | H2 Q_stop |
|---|---|---|---|---|---|---|
| GLOBAL 0..k | 54 | −45,589707 | −47,417525 | −0,1698 | −1,1273 | 0,926 |
| LOKAL 960 | 40 | **−10,859370** | −30,300143 | −0,0664 | −0,4939 | 0,775 |
| LOKAL 480 | 55 | **−8,039071** | −41,409136 | −0,0758 | −0,3293 | 0,727 |

**Fidelity:** `GLOBAL` reproduziert die `BASE`-Baseline **bit-identisch**
(299 Setups, R −186,055940, H2 54 / −45,589707, LONG 5 / SHORT 294).

### F3 · Der Q29-Durchlass (Kernfrage des Anwenders)

| Variante | Haelfte | Richtung | Kandidaten | Q29-Sperre | passiert | Anteil | SETUP |
|---|---|---|---|---|---|---|---|
| GLOBAL | H2 | LONG | 144 | **144** | 0 | **0,0 %** | 0 |
| GLOBAL | H2 | SHORT | 334 | 14 | 320 | 95,8 % | 54 |
| **LOKAL 960** | H2 | LONG | 144 | **102** | **42** | **29,2 %** | **11** |
| **LOKAL 960** | H2 | SHORT | 334 | 144 | 190 | 56,9 % | 29 |
| **LOKAL 480** | H2 | LONG | 144 | **62** | **82** | **56,9 %** | **19** |
| **LOKAL 480** | H2 | SHORT | 334 | 102 | 232 | 69,5 % | 36 |

Vollstaendig (auch H1):

| Variante | Haelfte | Richtung | Kandidaten | Q29 | passiert | Anteil | SETUP |
|---|---|---|---|---|---|---|---|
| GLOBAL | H1 | SHORT | 1972 | 301 | 1671 | 84,7 % | 240 |
| GLOBAL | H1 | LONG | 894 | 882 | 12 | 1,3 % | 5 |
| LOKAL 960 | H1 | SHORT | 1972 | 720 | 1252 | 63,5 % | 173 |
| LOKAL 960 | H1 | LONG | 894 | 672 | 222 | 24,8 % | 48 |
| LOKAL 480 | H1 | SHORT | 1972 | 579 | 1393 | 70,6 % | 197 |
| LOKAL 480 | H1 | LONG | 894 | 565 | 329 | 36,8 % | 63 |

**LONG H2: 0,0 % → 29,2 % (960) bzw. 56,9 % (480) Durchlass.**
Der Automat bekommt damit erstmals ueberhaupt LONG-Material (11 bzw. 19 Setups).

### F4 · Die Long-Seite traegt sofort PnL (Beispiele H2, LOKAL 960)

| Bar | Datum (BKZ) | Richtung | Kante | R | entry | sl | tp2 |
|---|---|---|---|---|---|---|---|
| 19.040 | 2025-10-21T16:00 | LONG | K451 | −1,00000 | 48,8960 | 48,7290 | 54,3610 |
| 19.285 | 2025-10-24T08:15 | LONG | K435 | −0,25290 | 48,2800 | 48,0000 | 54,3610 |
| 19.293 | 2025-10-24T10:15 | LONG | K444 | **+0,17525** | 47,8820 | 47,7830 | 54,3610 |
| 19.398 | 2025-10-27T12:30 | LONG | K424 | −0,01726 | 47,3920 | 47,2580 | 54,3610 |
| **19.957** | **2025-11-04T15:30** | **LONG** | **K415** | **+19,44077** | 46,9940 | 46,8030 | 54,3610 |

(Unter `LOKAL 480` feuert derselbe K415-Cluster bei Bar 19.993 mit **R
+33,37007**.) Die Short-Seite verliert dabei ihren toxischen Kern: H2-SHORTs
54 → 29 (960) bzw. 36 (480), das H2-R verbessert sich von −45,59 auf −10,86
(960) bzw. −8,04 (480).

### F5 · Schritt 2 — August-Baseline: **unter 960 strukturell identisch**

Der AUG-Lauf hat `box_end_bar = **644**` (2026-08-19) bei `n = 1288`. Fuer
**jeden** Bar der Box gilt `k ≤ 644 < 960` ⇒ `_a29 = max(0, k − 960 + 1) = 0`
⇒ die Q29-Referenz ist **bit-identisch** zum bisherigen Verhalten. Die
August-Baseline (V018: 17 Trades / +65,835576 R) ist unter `LOKAL 960` daher
**konstruktionsbedingt nicht beruehrbar** — unabhaengig von der
Hook-Verdrahtung.

| AUG-Variante | Setups | R ges. | R_adj | USD/Tr | Q_stop |
|---|---|---|---|---|---|
| GLOBAL 0..k | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 |
| **LOKAL 960** | **8** | **+38,919584** | **+23,049550** | **+1,4077** | **0,125** |
| LOKAL 480 | 7 | +39,267031 | +23,396996 | +1,6134 | 0,143 |

`LOKAL 960` ist **zeilenweise identisch** zu `GLOBAL` (auch die Trade-Liste).
`LOKAL 480` verliert genau einen Trade (Bar 509 SHORT K16, R −0,34745).

**Praezisierung zur Baseline:** Der unbewehrte Engine-Lauf liefert in AUG
**8 Setups / +38,919584 R**. Die arretierte Zahl **17 Trades / +65,835576 R**
stammt aus dem **adapter-verdrahteten** Renderer-Harness (Hook-1-Freigabe,
`REF 0,12 %`), nicht aus `_se_trades` allein. Beide Groessen sind daher
auseinanderzuhalten; die Invarianz unter 960 gilt fuer **beide** (sie folgt
aus `_a29 = 0`, nicht aus der Hook-Verdrahtung).

### F6 · Bereinigung D1–D4 (Nachlauf Phase 1, ratifiziert)

| Kennung | Vorher | **Jetzt verbindlich** |
|---|---|---|
| `D1` | `Q_stop > 0,75` → kategorisch ausgeschlossen | **bestaetigt** — hartes Ausschlusskriterium |
| `D2` | `R_adj ≤ Baseline-R_adj` → verworfen | **SUSPENDIERT** (irrefuehrend, s. E-25/F7) |
| `D3` | Vortrag R, R_adj, Q_stop | **ersetzt**: fuehrend **`USD/Trade` > 0** und **`ATR/Trade`**; `R`/`R_adj` nur deskriptiv |
| `D4` | Dual-Ausweis USD/ATR | **bestaetigt** |

**Harte Gate-Bedingungen (Stand jetzt):** `Q_stop ≤ 0,75` **und**
`USD/Trade > 0`.

**Konsequenz fuer E-27 (ehrliche Bilanz):** Keine der drei S2-Varianten
erfuellt `USD/Trade > 0` —

| Variante | Q_stop ≤ 0,75? | USD/Trade > 0? | Verdikt |
|---|---|---|---|
| GLOBAL 0..k | nein (0,799) | nein (−0,0672) | verworfen |
| LOKAL 960 | ja (0,667) | **nein** (−0,0206) | **verworfen** |
| LOKAL 480 | ja (0,644) | **nein** (−0,0319) | **verworfen** |

Die Lokalisierung **heilt die Mechanik** (Long-Seite oeffnet, `Q_stop` faellt
unter 0,75, R −186 → −71), aber sie erzeugt **noch kein positives
Erwartungswert-Signal**. Der Restverlust sitzt in der Gegenkante (`tp2`
28,4320 / POC auf dem Niveau 32,3–32,8 — d. h. die Ziele liegen weit ausserhalb
der aktuellen Handelsspanne).

### F7 · Interpretation

1. **E-26 bestaetigt und verschaerft:** Q29 war nicht nur ein Long-Blocker,
   sondern ein **globaler Trend-Blindmacher**. Seine Lokalisierung auf das
   Erkennungsfenster ist die erste Massnahme in S2, die die Bilanz in
   **beiden** Richtungen verbessert.
2. **Die §12-Fensterlogik ist jetzt durchgaengig konsistent:** `L960` steuert
   bereits die Balance-Deklaration (E-25/F6). Q29 nutzt dasselbe Fenster.
   Damit gibt es in S2 **eine** Zeitbasis fuer Struktur und Quartil.
3. **960 ist gegenueber 480 zu bevorzugen** — nicht wegen der S2-Zahlen
   (480 ist dort sogar leicht besser), sondern wegen (a) der
   `box_end < LB`-Invarianz, die die AUG-Baseline **beweisbar** schuetzt, und
   (b) der Deckungsgleichheit mit dem Block-A-Erkennungsfenster.
   `LOKAL 480` verletzt die AUG-Baseline (1 Trade).
4. **Der naechste Blocker ist die Zielgeometrie, nicht das Gate.** Mit
   geoeffneter Long-Seite zeigt sich: `tp2`/POC liegen bei den H2-Trades
   weiterhin auf dem Niveau der Januar-Struktur (28,43 / 32,5). Das ist
   dieselbe Krankheit wie E-25/F5 — eine **globale** Referenz im
   Zielsystem.

### F8 · Offene Entscheidungen (Textblock)

1. **Fensterwahl verbindlich machen.** Vorzuschlagen ist `Q29 = L960`
   (Deckung mit Block A, AUG-Baseline beweisbar invariant). `LOKAL 480` waere
   zu verwerfen. Gegenstimmen sind ueber die S2-Zahlen allein nicht zu
   begruenden, wohl aber ueber den AUG-Schutz.
2. **Gegenkante/`tp2` lokalisieren.** Der Restverlust (−0,0206 USD/Tr) sitzt
   nachweislich im Zielsystem: `tp2` 28,4320 und POC-Niveaus 32,3–32,8 bei
   H2-Kursen 46–54. Soll `_gegenkante` ebenfalls auf `L960` lokalisiert werden
   — dieselbe Operation, die Q29 geheilt hat?
3. **`tp1_anteil_pct` / POC-Fenster.** `berechne_kausalen_histogramm_poc`
   arbeitet mit `poc_start = 0` (Box-Beginn) — das ist die dritte globale
   Referenz im System. Ueberpruefen, ob auch sie auf `L960` gehoert.
4. **Reihenfolge bestaetigen.** Nach F8.2/F8.3 (Zielsystem) kann die
   Hybrid-Schliessung auf `L960` und erst danach der Zustandsautomat folgen.
5. **D3-Gate `USD/Trade > 0`.** Es ist derzeit **von keiner Variante**
   erfuellt. Zu klaeren, ob das Gate als *Zulassungs*- oder als
   *Zielkriterium* gilt (d. h. ob eine mechanisch geheilte, aber noch
   negative Variante weiterverfolgt werden darf).

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache.**

---

## Phase 2 / E-28 (2026-09-11, l) — Zielsystem-Lokalisierung: **beide Gates erstmals erfuellt**

Ratifiziert und gemessen wurde das **komplette Zielsystem-Buendel** in dem
Fenster, das E-27 fuer Q29 etabliert hat:

    _W(k) = max(0, k - 960)

angewandt auf die **drei** globalen Referenzen der Engine:

1. **Q29** (`_im_aussenquartil`, Z. 2434/2435) — bereits E-27 ratifiziert,
   hier als Konstante mitgefuehrt.
2. **Gegenkante** (`_gegenkante`, Z. 2554 ff.) — der Pool, aus dem `tp2`
   gewaehlt wird.
3. **POC-Anker** (`poc_start`, `berechne_kausalen_histogramm_poc`) — bisher
   `0` (Box-Beginn).

### G0 · Erratum der Variante `gegleb` — 96-Bar-Artefakt

Der E-28-Entwurf hatte eine Variante `gegleb` als „Liveness im Fenster"
etiketiert und dabei `_lebt` (Engine, Z. 2413) verwendet. `_lebt` prueft
jedoch gegen **`cfg.wall_live_bars = 96`** (Q25), **nicht** 960. `gegleb` ist
damit **keine 960er-Variante**, sondern ein 96-Bar-Fenster — und sie ist die
**einzige** Variante, die die AUG-Baseline veraendert (R 38,92 → 26,19;
s. G5). Sie ist als **Artefakt verworfen**. Die ratifizierte
Liveness-Variante heisst `geg960`:

```python
max(b for b, _ in e.wicks if b <= k) >= k - 960   # geg960 (ratifiziert)
max(b for b, _ in e.wicks if b <= k) >= k -   96   # _lebt (Q25-Konstante)
```

Nebenbefund: `geg` (Basis im Fenster) und `geg960` liefern in S2
**nahezu identische** Ergebnisse (s. G3) — die beiden Formulierungen von
„lokal" sind innerhalb des 960er-Fensters austauschbar. Das ist eine
Robustheitsaussage, kein Zufall: die Fensterkante `_W(k)` schneidet den Pool
bereits strukturell, die Liveness ist dann nur noch eine Nachfilterung.

### G1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e28_ziel_lokal.py` | `2c144660f4551e7e4d0f4033d2be7f390774efec50383900b75ee9f6788397f1` | 11.709 |
| `test/_tmp_e28_run_all.py` | `63b7091250c495e899d6e777404b691856667aa6d20cbb6633dbda10afe788a7` | 1.287 |
| `test/_tmp_e28_sammel.py` | `0f9ee198b8a650c62d027fd231bebef799b6e7920aa0fb7c99520b9ac461e08d` | 2.371 |
| `test/_tmp_e28_ziel_s2_base_out.txt` | `d77283a1ab41a1a7486a0855605753908798191e4cb315c0075d2b0341093d94` | 24.210 |
| `test/_tmp_e28_ziel_s2_geg_out.txt` | `0e252b409394140e4f5bf449e321e246974a16dbbc70fcada16f2623b33cdfde` | 24.016 |
| `test/_tmp_e28_ziel_s2_geg960_out.txt` | `2714d89720d95fe3bd299bd7edcc0660e91e7803524658a1341a9e856ccf0cee` | 24.052 |
| `test/_tmp_e28_ziel_s2_poc_out.txt` | `c47480ea5e3824704efa0bea3550f96db9c86a4b7580e13e6c400e408c54a68c` | 25.843 |
| `test/_tmp_e28_ziel_s2_gegpoc_out.txt` | `52ab02c8fad4fa357ba1668bfaf91a2dcb3b7ba3ac75205e6419065bc2e4caf9` | 25.065 |
| `test/_tmp_e28_ziel_s2_geg960poc_out.txt` | `480e8adeaccd65cf23260c22bc13e0b4ea2d3778d5d40f0d791c35473dc324a7` | 25.075 |
| `test/_tmp_e28_ziel_aug_base_out.txt` | `6b67edac07ecd7406b529969e9e1c850571b9f40ab5e84dc2f5008a36109fe72` | 2.190 |
| `test/_tmp_e28_ziel_aug_geg_out.txt` | `66c5452868b4a55f5e4c94d90ac606e7634d4defa2cd8e8276f5796ee3dd1dfb` | 2.171 |
| `test/_tmp_e28_ziel_aug_geg960_out.txt` | `e95e89d96af860d898f9a8df89f5cf5e10f827198103ccdb293bd08e39f681a7` | 2.207 |
| `test/_tmp_e28_ziel_aug_poc_out.txt` | `af77a52e61efe5aa402ec8f7e78be64c3ca0da593e95f681c14321c5c1ee4bdc` | 2.172 |
| `test/_tmp_e28_ziel_aug_gegpoc_out.txt` | `070dcf4042d7da4c1884a26ddb455ca237dc5a3e62840ffbf6d8ae6f9f02539b` | 2.174 |
| `test/_tmp_e28_ziel_aug_geg960poc_out.txt` | `904e009200633f1f6229f8028c8e5ab50f9a2a08667822a417e5b278cd11966c` | 2.184 |
| `test/_tmp_e28_ziel_aug_gegleb_out.txt` | `df87ae0133254a0b2a174711e8be7c9efbaf1d61cd02921b84f3d0fd9bbaf540` | 2.178 |
| `test/_tmp_e28_ziel_aug_geglebpoc_out.txt` | `2b22c8876b906aeb1daf0ef4e3e78725e0a320dbf16d8a8c5608f27d5292351e` | 2.181 |

**Eingriffe (drei, alle additiv zu E-27):**

```python
# (2) Gegenkanten-Pool -- _gegenkante, vor dem max/min
_wh = float(np.max(hi[_W(k):k + 1]))
_wl = float(np.min(lo[_W(k):k + 1]))
pool = [e for e in seite_edges[gegenseite]
        if e.erster_pivot_bar + 2 <= k + 1
        and (not _FLAG[0] or (
             (_wl <= e.basis_bei(k) <= _wh) if _FLAG[0] == 1   # geg
             else (_lebt960(e, k) if _FLAG[0] == 3 else _lebt(e, k))))  # geg960
        and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
             or e.touch_conf(k) >= 2)]

# (3) POC-Anker
poc = berechne_kausalen_histogramm_poc(
    d, (_W(k) if _FLAG[1] else poc_start), k, unter, ober, cfg.num_bins)
```

### G2 · Methodik

Ein Lauf = ein Prozess (E-27/F0); **parallele** Prozesse sind zulaessig, die
Isolation ist pro Prozess (`_se_trades` mutiert `letzter_signal_bar`,
`letzter_sweep_bar`, `cluster_hoch`, `cluster_tief`). `_tmp_e28_run_all.py`
startet alle sechs Varianten in sechs Prozessen; Gesamtlaufzeit **153,7 s**.
Die S2-Laufgrenze ist `box_end_bar = n = 21.624` (Split 17.692). In AUG bleibt
`box_end_bar = 644` unveraendert.

### G3 · S2 — saubere 2-Koordinaten-Matrix (`box_end_bar = n = 21.624`)

`gegenkante ∈ {global, lokalbasis (`geg`), lokal960leb (`geg960`)}` ×
`poc ∈ {global, lokal}`:

| Variante | Gegenk. | POC | Setups | R ges. | R_adj | USD/Tr | ATR/Tr | Q_stop | Gew% | Trade-SHA |
|---|---|---|---|---|---|---|---|---|---|---|
| `base` | global | global | 261 | −70,813603 | −91,649458 | **−0,0206** | −0,3367 | 0,667 | 11,5 | `5a73d37ad2441d49` |
| `geg` | lokal-Basis | global | 259 | +17,686977 | −14,184964 | **+0,0192** | +0,2379 | 0,772 | 7,7 | `82df0037a790e2bd` |
| `geg960` | lokal-960leb | global | 259 | +16,853088 | −15,018853 | **+0,0189** | +0,2331 | 0,772 | 7,7 | `5d0001abed977302` |
| `poc` | global | lokal | 280 | −3,856257 | −27,289551 | **+0,0315** | +0,1638 | 0,782 | 14,3 | `e970721fb1e0ece7` |
| **`gegpoc`** | lokal-Basis | lokal | 271 | **+55,878629** | **+28,807016** | **+0,0526** | **+0,3890** | **0,742** | 12,9 | `9baa8c360c6897c0` |
| **`geg960poc`** | lokal-960leb | lokal | 271 | **+55,871446** | **+28,799833** | **+0,0526** | **+0,3890** | **0,742** | 12,9 | `f9c2a3dd59c8be1d` |

Halbierung:

| Variante | H1 n | H1 R | H1 USD/Tr | H1 Q_stop | H2 n | H2 R | H2 USD/Tr | H2 Q_stop |
|---|---|---|---|---|---|---|---|---|
| `base` | 221 | −59,954233 | −0,0123 | 0,647 | 40 | −10,859370 | −0,0664 | 0,775 |
| `geg` | 219 | +7,189615 | +0,0077 | 0,767 | 40 | +10,497363 | +0,0822 | 0,800 |
| `geg960` | 219 | +6,355726 | +0,0073 | 0,767 | 40 | +10,497363 | +0,0822 | 0,800 |
| `poc` | 239 | −11,914974 | +0,0221 | 0,766 | 41 | +8,058718 | +0,0862 | 0,878 |
| **`gegpoc`** | 232 | +12,126065 | +0,0186 | 0,728 | 39 | **+43,752564** | **+0,2549** | 0,821 |
| **`geg960poc`** | 232 | +12,126065 | +0,0186 | 0,728 | 39 | **+43,745381** | **+0,2549** | 0,821 |

### G4 · Kernbefund: das Gate faellt nur unter **beiden** Koordinaten

| | POC global | POC lokal |
|---|---|---|
| **Gegenkante global** | `base`: USD −0,0206 · Q 0,667 → **Gate nein** | `poc`: USD +0,0315 · Q 0,782 → **Gate nein** |
| **Gegenkante lokal** | `geg`/`geg960`: USD +0,019 · Q 0,772 → **Gate nein** | `gegpoc`/`geg960poc`: USD **+0,0526** · Q **0,742** → **GATE JA** |

Drei Aussagen:

1. **Beide Gates sind erstmals erfuellt.** `USD/Trade > 0` **und**
   `Q_stop ≤ 0,75` — ausschliesslich in der Zelle (lokal, lokal). Jede
   Einzelmassnahme scheitert: die Gegenkante allein kippt USD knapp positiv
   (`+0,019`), reisst aber `Q_stop` ueber 0,75 (0,772); der POC allein kippt
   USD positiver (`+0,0315`), `Q_stop` bleibt aber 0,782. Erst die Kombination
   senkt `Q_stop` auf 0,742 **und** hebt USD/Tr auf +0,0526.
2. **Der POC ist der groessere Hebel, die Gegenkante die Qualitaetssicherung.**
   `R_adj` springt von −14,18 (`geg`) auf **+28,81** (`gegpoc`) — das
   Ergebnis ist **nicht** von einem einzelnen Ausreisser getragen. Unter
   `base` ist `R_adj` −91,65 (der beste Trade wird entfernt und die Bilanz
   bricht ein).
3. **Wirkung auf H2 ist stark, aber richtungsunabhaengig verankert.** H2-R
   −10,86 → **+43,75**; H2-USD/Tr −0,066 → **+0,2549**. H1 bleibt mit
   +12,13 R schwach positiv (USD/Tr +0,0186). Der Gewinner ist also **nicht**
   ein H2-Sonderfall: H1 dreht von −59,95 auf +12,13.

**Achtung (offen, G7):** H2-`Q_stop` = **0,821** liegt ueber 0,75. Das
Gesamt-`Q_stop` (0,742) sind die Tore passiert, die H2-Teilmenge nicht. Nach
`D1` waere ein `Q_stop > 0,75` kategorisch auszuschliessen — hier ist zu
entscheiden, ob `D1` auf Gesamt oder Halbierung angewandt wird.

### G5 · Schritt 2 — AUG: das ratifizierte Buendel ist **beweisbar inert**

`box_end_bar = 644 < 960` ⇒ `_W(k) = 0` fuer **jeden** Box-Bar ⇒ alle drei
Lokalisierungen sind bit-identisch zu `GLOBAL`; `_lebt960` ist fuer jeden
Docht trivial wahr.

| AUG-Variante | Setups | R ges. | R_adj | USD/Tr | Q_stop | Trade-SHA | Verdikt |
|---|---|---|---|---|---|---|---|
| `base` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | Referenz |
| `geg` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `geg960` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `poc` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `gegpoc` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `geg960poc` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `gegleb` (96) | 8 | +26,190829 | +16,946994 | +1,0115 | 0,250 | `c67a27814486df2b` | **Artefakt** |
| `geglebpoc` (96) | 8 | +26,190829 | +16,946994 | +1,0115 | 0,250 | `c67a27814486df2b` | **Artefakt** |

Die August-Baseline (V018: 17 Trades / +65,835576 R bzw. unbewehrte
`_se_trades` 8 Setups / +38,919584 R) ist unter dem **ratifizierten** Buendel
**byte-identisch** geschuetzt. Der Beweis ist konstruktiv (`_W(k) = 0`), nicht
empirisch — er haengt an keiner Hook-Verdrahtung.

### G6 · Ehrliche Bilanz E-28 (Vergleich zu E-27/F6)

| Groesse | E-27 (`base` = Q29 lokal 960) | **E-28 (`geg960poc`)** |
|---|---|---|
| Setups (S2) | 261 | 271 |
| R ges. | −70,813603 | **+55,871446** |
| R_adj | −91,649458 | **+28,799833** |
| USD/Trade | −0,0206 | **+0,0526** |
| ATR/Trade | −0,3367 | **+0,3890** |
| Q_stop | 0,667 | 0,742 |
| H2 R | −10,859370 | **+43,745381** |
| H2 USD/Tr | −0,0664 | **+0,2549** |
| Gate `USD/Trade > 0` | **verletzt** | **erfuellt** |
| Gate `Q_stop ≤ 0,75` | erfuellt | **erfuellt** |

Damit ist erstmals in S2 eine Konfiguration vorhanden, die **beide** in E-27/F6
festgelegten harten Gates passiert. Die Lokalisierung hat sich als das
richtige **Werkzeug** erwiesen: dieselbe Operation (`_W(k) = max(0, k−960)`)
heilt Q29, die Gegenkante **und** den POC-Anker.

### G7 · Offene Entscheidungen (Textblock)

1. **`D1`-Reichweite.** Gesamt-`Q_stop` 0,742 (≤ 0,75), H2-`Q_stop` 0,821
   (> 0,75). Vorgeschlagen wird: `D1` gilt fuer die **Gesamtbilanz** (und
   die Halbierungen werden nur deskriptiv mitgefuehrt), weil bei n = 39 die
   H2-Rate statistisch nicht belastbar ist. Gegenposition: `D1` als
   *Halbierungs*-Gate verwerfen `gegpoc` sofort. Zu entscheiden.
2. **`geg` vs. `geg960`.** Beide sind in S2 nahezu deckungsgleich. Meine
   Empfehlung: **`geg960`** ratifizieren, weil es die *eine* Semantik
   (`_W(k) = 960`) konsequent weitertraegt und die 96-Bar-Konstante
   `wall_live_bars` (Q25) unangetastet laesst. `geg` bleibt deskriptiv.
3. **`tp1_anteil_pct`.** Noch offen: ob der TP1-Anteil (50 %) an die
   lokalisierte Gegenkante gekoppelt werden muss (bisher nicht Gegenstand der
   Messung).
4. **POC-Bins.** `num_bins = 60` wurde bei lokalem Fenster (960 statt 21.624
   Bars) **nicht** nachkalibriert. Die Bin-Breite aendert sich damit
   strukturell. Zu pruefen, ob `num_bins` bei lokalem `poc_start` skaliert
   werden muss.
5. **Reihenfolge.** Nach Zielsystem: **Hybrid-Schliessung auf `L960`**, danach
   der Zustandsautomat (`BALANCE`/`EXPANSION_OBEN`/`EXPANSION_UNTEN`).

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache, keine S1-Untersuchung.**

---

## Phase 2 / E-29 (2026-09-11, m) — Binning-Audit & H2-Stop-Out-Anatomie: **die Rausch- und die Stop-Hypothese sind falsifiziert**

Auftrag (Anwender-Freigabe): (1) `geg960poc` als Kernstandard arretieren,
(2) `num_bins = 60` bei 960 Bars rein datenseitig pruefen, (3) Ursachen der
H2-Stop-Outs lokalisieren, (4) Hybrid-Schliessung auf `L960` vorbereiten.
Alle Messungen read-only; **keine** Aenderung an Engine oder Adapter.

### H0 · Reproduktions-Fidelity

Der E-29-Harness reproduziert `geg960poc` aus E-28 **bit-identisch**:
271 Setups · R +55,871446 · USD +14,2466 · USD/Tr +0,0526 · ATR/Tr +0,3890 ·
Q_stop 0,742 · H1 232 / H2 39. Die POC-Diagnose-Replikation ist gegen den
Engine-Rueckgabewert per `assert` abgesichert (Abweichung < 1e-9).

### H1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e29_audit.py` | `7a51c1fa74f047ed0e02b2d32ffd757d1112471db028ece82fc666b630016e1b` | 16.962 |
| `test/_tmp_e29_run_all.py` | `ea56621aa73b9942c55fcf9c94ac33d554f482901eb0a0b7674837077efc09ac` | 1.159 |
| `test/_tmp_e29_sammel.py` | `0ec406e0d46669a0ad46e2a0eceb5102c0d7a699d4e3b7e4e66c426121884d28` | 2.592 |
| `test/_tmp_e29_h2.py` | `e7fcc3fdcdcd2c65fcae41cbfce770e44b1aa2d410c4c5b198c2f897a1bf14f3` | 1.837 |
| `test/_tmp_e29_be.py` | `9208bac371f6ac5fd98f224c262015a2da3de8a02bfd944752e7c4559329caff` | 5.911 |
| `test/_tmp_e29_risk.py` | `2a25882723423ec5cb918d1955b8338fefb374f7708cb32c5dcc6ff703a9840d` | 2.459 |
| `test/_tmp_e29_diag.py` | `20e73d125853bacf78222f8f3df964ab68b4862ffb94d61e6fc6d89598f70466` | 1.068 |
| `test/_tmp_e29_setups_s2_b60.pkl` | `17865f660bae248e8d7b173af084ed8c09bf4eb713de53c0448f7abb6910724c` | 37.384 |
| `test/_tmp_e29_setups_aug_b60.pkl` | `35ad8b0c70ea53c47b2d037b0633bbc79127c6d90aa8bc55e192844d65d1f017` | 1.270 |
| `test/_tmp_e29_audit_s2_b60_out.txt` | `ed359babb90f24be971e97b213ae91a50e61b0073297f4ad9353c90caabede25` | 28.388 |
| `test/_tmp_e29_audit_aug_b60_out.txt` | `d60b6739cda5088ad7251201b657dca6bd7167e5c5aa5da08215e62f45505372` | 3.080 |

**Kernmechanik (Engine Z. 1586-1647, unveraendert):** `rm = 0,5·r1 + 0,5·r2`,
`r1 = -1` bei SL, `tp1 = POC`, `tp2 = Gegenkante`. Daraus folgt **exakt**:
`rm <= -1` ist nur moeglich, wenn **beide** Haelften am Stop enden. Q_stop
ist also **keine Glaettungs- oder Ausreisserfrage**, sondern die Aussage:

> Q_stop = Anteil der Trades, bei denen der Preis **den POC nie vor dem Stop
> beruehrt hat**.

Diese Identitaet ist der Schluessel zu allen weiteren Lesarten.

### H2 · T1 — Binning-Oekonomie: **keine ungefuellten Bins, keine Rauschsorge**

| `num_bins` | Fenster-Bars median | Preisspanne median | Bin-Breite median | leere Bins |
|---|---|---|---|---|
| 10 | 961 | 2,0355 | 0,203550 | **0** (0,0 %) |
| 15 | 961 | 2,0355 | 0,135700 | **0** (0,0 %) |
| 20 | 961 | 2,0250 | 0,101250 | **0** (0,0 %) |
| 30 | 961 | 2,0150 | 0,067167 | **0** (0,0 %) |
| 40 | 961 | 1,9660 | 0,049150 | **0** (0,0 %) |
| 60 | 961 | 1,9015 | 0,031692 | **0** (0,0 %) |

Die Sorge „960 Bars auf 60 Bins ⇒ jedes Bin zu schmal ⇒ zufaellige Docht-Peaks"
ist **empirisch falsifiziert**: bei **jeder** Aufloesung von 10 bis 60 Bins ist
**kein einziges Bin leer**. Ursache: die Binnung laeuft nicht ueber die Zeit,
sondern ueber den **Preisraum `[unter, ober]` = [Gegenkante, Einstiegskante]**
(Median ~2,0 USD) bei ~961 Bars — jedes Bin wird von vielen Bars getroffen.
Die POC-Aufrufe steigen von 284 (b10) auf 308 (b60), weil der POC selbst
ueber die Ordnungsbedingung `sl < entry < poc < tp2` auf die Annahme
zurueckwirkt.

### H3 · T2 — Binning-Sweep S2 (`box_end_bar = n`, Kernstandard `geg960poc`)

| `num_bins` | Setups | R ges. | USD/Tr | ATR/Tr | Q_stop | H1 n | H2 n | H2 R | H2 USD/Tr |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 284 | +38,280775 | +0,0395 | +0,3797 | 0,810 | 243 | 41 | +17,531395 | +0,1498 |
| 15 | 284 | +31,006989 | +0,0367 | +0,3359 | 0,806 | 243 | 41 | +16,859602 | +0,1478 |
| 20 | 283 | +31,610277 | +0,0384 | +0,3334 | 0,784 | 242 | 41 | +17,384518 | +0,1533 |
| 30 | 280 | +31,505286 | +0,0395 | +0,3439 | 0,761 | 239 | 41 | +16,901548 | +0,1513 |
| 40 | 279 | +56,479291 | +0,0509 | +0,4160 | 0,746 | 238 | 41 | +42,091396 | +0,2228 |
| **60** | **271** | **+55,871446** | **+0,0526** | **+0,3890** | **0,742** | 232 | 39 | **+43,745381** | **+0,2549** |

Kein Rausch-Muster, sondern ein **monotoner Effekt mit Plateau bei 40-60**:
mit groeberem Bin springt der POC auf ein groeberes Niveau (Bin-Mitte), was die
Zielwahl verschlechtert. Der Anteil des Max-Bins steigt von 4,50 % (b60) auf
17,27 % (b10) — der POC wird also **nicht verrauscht, sondern unspezifisch**.

**Die harte Grenze kommt jedoch von AUG** (Tabelle H4): `num_bins` ist ein
**globaler** Parameter und **nicht** lokalisiert. Schon `num_bins = 40`
veraendert die August-Baseline. Damit ist die Entscheidung nicht
Geschmackssache, sondern erzwungen.

### H4 · `num_bins` ist AUG-kritisch — 60 bleibt

| `num_bins` | AUG Setups | AUG R ges. | AUG USD/Tr | AUG Q_stop |
|---|---|---|---|---|
| 10 | **9** | +36,272980 | +1,0953 | 0,333 |
| 15 | **9** | +35,934863 | +1,0970 | 0,333 |
| 20 | **9** | +34,683981 | +1,0655 | 0,333 |
| 30 | **9** | +35,597659 | +1,0890 | 0,222 |
| 40 | 8 | +36,488272 | +1,2566 | 0,125 |
| **60** | **8** | **+38,919584** | **+1,4077** | **0,125** |

`num_bins = 40` verschiebt den V018-Anker (R +38,919584 → +36,488272), und
`<= 30` erzeugt **einen zusaetzlichen Trade** (9 statt 8). Es gibt hier —
anders als bei der Lokalisierung (`_W(k) = 0` ⇒ konstruktive Inertheit) —
**keine** Invarianz. **Verdikt: `num_bins = 60` bleibt arretiert.** Der
Binning-Audit ist damit abgeschlossen und *beendet*, nicht offen.

### H5 · H2-Stop-Out-Anatomie (Rekonstruktion aus gespeicherter Geometrie)

H2 (`n = 39`): **32 STOP** (r <= -1) · 3 Teil-SL · 4 ok.
Der Median-Abstand Entry -> TP1(POC) betraegt **13,29 R** (Maximum 74,32 R).

| Kenngroesse | Wert |
|---|---|
| Stop-Outs mit **MFE >= 1,0 R** (hat funktioniert, dann gedreht) | **18 von 32** |
| Stop-Outs mit MFE < 0,5 R (nie in Bewegung) | 10 von 32 |
| d_POC (Entry -> TP1) min / median / max | 0,15 / **13,29** / 74,32 |
| risk (USD) min / median / max | 0,0410 / 0,1670 / 0,4090 |

Die H2-Stop-Outs sind also **kein** gleichfoermiges Bild: 18 Trades waren
zwischenzeitlich im Gewinn (teils > 20 R), 10 waren sofort falsch. Das ist
genau die Signatur eines **fehlenden Verlust-Managements**, nicht einer
falschen Richtung.

### H6 · Risiko-Kalibrierung — die Stop-Hypothese ist **falsifiziert**

Meine Arbeitshypothese aus H5 ("der Stop ist degeneriert, E-22") haelt der
Messung **nicht** stand:

| Datensatz | Haelfte | risk/Entry % (med) | **risk/ATR14 (med)** | d_POC [R] (med) | ATR14 med |
|---|---|---|---|---|---|
| S2 | gesamt | 0,302 | 1,36 | 6,72 | 0,0868 |
| S2 | H1 | 0,301 | 1,40 | 5,86 | 0,0752 |
| **S2** | **H2** | 0,348 | **0,96** | **13,29** | 0,1664 |
| AUG | H1 | 0,385 | 1,27 | 4,43 | 0,1906 |

Der strukturelle Stop liegt bei **~1 ATR14** — das ist ein *normaler*, kein
degenerierter Stop. Das eigentliche Missverhaeltnis sitzt im **Ziel**: TP1
(= POC) liegt in H2 bei **~13 ATR14** Entfernung (Entry an der Aussenwand,
POC in der **Mitte der lokalen Spanne ~2,0 USD ≈ 4,2 % Kursweg**). Der Trade
muss also unmittelbar ~4 % gegen die Bewegung laufen, bevor die erste Haelfte
bezahlt wird — in einem **Trendabschnitt**.

**Kernsatz E-29:** Nicht der Stop ist zu eng, sondern **das Ziel ist zu weit** —
und zwar systematisch, weil Q29 den Einstieg an die *Aussenwand* legt,
waehrend der POC die *Mitte* der Spanne markiert.

### H7 · Break-Even-Studie: **Falsifikation** des naheliegenden Fixes

Pfadgenau, ohne Look-ahead (Stop-Wechsel wirkt ab dem Folgebar; bei Gleichstand
im selben Bar gewinnt der Stop, identisch zur Engine). Schwellwert `x` =
MFE-Schwelle fuer Stop auf Einstand.

S2 (`n = 271`):

| Variante | R ges. | **USD/Tr** | ATR/Tr | Q_stop | geaenderte Trades |
|---|---|---|---|---|---|
| **BASIS (arretiert, kein BE)** | +55,871446 | **+0,0526** | +0,3890 | 0,742 | 0 |
| BE-Stop ab +0,25 R | -17,140669 | +0,0010 | -0,0608 | **0,269** | 190 |
| BE-Stop ab +0,50 R | -8,149865 | +0,0024 | -0,0152 | 0,339 | 165 |
| BE-Stop ab +0,75 R | +13,778437 | +0,0181 | +0,0874 | 0,387 | 145 |
| BE-Stop ab +1,00 R | +27,425888 | +0,0218 | +0,2040 | 0,424 | 130 |
| BE-Stop ab +1,50 R | +63,010310 | +0,0457 | +0,3647 | 0,506 | 104 |
| BE-Stop ab +2,00 R | +61,897816 | +0,0497 | +0,4086 | 0,579 | 77 |
| BE-Stop ab +3,00 R | +45,473281 | +0,0434 | +0,3456 | 0,646 | 52 |
| BE +1,00 R + Trail 0,5 R | +19,006714 | +0,0114 | +0,0645 | 0,424 | 141 |
| BE +2,00 R + Trail 0,5 R | +1,904968 | -0,0018 | +0,0064 | 0,579 | 91 |

AUG (`n = 8`) bestaetigt: BE-Stop ab +0,25 R halbiert den Ertrag
(USD/Tr +1,4077 → +0,4960); erst ab +3,00 R ist er neutral
(+1,4135, eine einzige geaenderte Position = Rauschen).

**Zwei Schlussfolgerungen, beide unangenehm:**

1. **Kein Break-Even-Wert verbessert das führende Maß.** Q_stop faellt von
   0,742 auf 0,269 — und `USD/Trade` von +0,0526 auf +0,0010. Bei +1,50 R
   *steigt* `R` auf +63,01, waehrend `USD/Trade` auf +0,0457 **faellt**:
   die R-Summe und das USD-Maß laufen auseinander (erneut die D2/D3-Lehre —
   `R` ist ungewichtet, `USD/Trade` gewichtet mit dem Risiko).
2. **`Q_stop` ist als Optimierungsziel untauglich und spielfaehig.** Es laesst
   sich trivial auf 0,269 druecken, waehrend das System schlechter wird. Als
   *Ausschluss*-Kriterium (`D1`) bleibt es brauchbar; als *Ziel* ist es
   verboten. **H2/Q_stop = 0,821 ist damit nicht der eigentliche Defekt.**

### H8 · Hybrid-Schliessung: beide Schranken gemessen

Als Naetherung fuer den Strukturbruch dient die Einstiegskante (Basis); als
Bruch gilt der erste Close jenseits dieser Kante vor dem Stop.

| Sicht | Regel | R ges. | USD/Tr | Q_stop | Gewinner getoetet |
|---|---|---|---|---|---|
| Basis | – | +55,871446 | +0,0526 | 0,742 | – |
| **T4b (obere Schranke)** | Bruch-Exit **nur** auf Verlust-Trades (ex post) | **+115,099620** | **+0,0836** | **0,351** | 0 |
| **T4c (untere Schranke)** | Bruch-Exit mechanisch auf **alle** Trades | **-52,613531** | +0,0031 | 0,742 | **18 von 35** |

AUG analog: T4c toetet **4 von 5** Gewinnern (-26,835559 R;
USD/Tr +1,4077 → +0,1469).

Die Spanne zwischen +115,10 und -52,61 R ist **vollstaendig** eine Frage der
**Diskrimination** — nicht der Exit-Mechanik. Ein nackter Close-Bruch ist ein
Whipsaw-Generator; er braucht den Zustandsautomaten (Block A), der Rauschen
von echter Neu-Deklaration trennt. Das ist die **quantifizierte**
Arbeitsanweisung fuer Schritt 3: die Hybrid-Schliessung ist **genau dann**
wertvoll, wenn ihre Trennschaerfe nahe an T4b heranreicht.

### H9 · Ratifizierungen (Anwender-Freigabe, 2026-09-11 m)

1. **`geg960poc` ist der verbindliche Kernstandard fuer `L960`** — Q29 lokal
   960, Gegenkante lokal 960-Lebigkeit, POC-Anker lokal 960. Die Varianten
   `base`, `geg`, `poc`, `gegpoc` sind als **abgearbeitet** archiviert;
   `gegleb`/`geglebpoc` sind als **96-Bar-Artefakt** verworfen (E-28/G0).
2. **`D1` gilt fuer die Gesamtbilanz** (Q_stop = 0,742 <= 0,75). Die
   H2-Teilquote (0,821) ist bei `n = 39` statistisch nicht belastbar und wird
   **nicht** als Abbruchkriterium angewandt — sie bleibt aber als sekundaerer
   Beobachtungspunkt notiert.
3. **`tp1_anteil_pct = 50 %` bleibt unveraendert** (kein zweiter Hebel
   gleichzeitig).
4. **`num_bins = 60` bleibt arretiert** — nicht wegen S2, sondern wegen des
   AUG-Ankers (H4).
5. **Reihenfolge bestaetigt:** Zielsystem arretiert -> Binning geprueft
   (erledigt, geschlossen) -> **Hybrid-Schliessung auf `L960`** -> Zustandsautomat.

### H10 · Offene Entscheidungen (Textblock)

1. **Zielgeometrie statt Stop-Management.** Der Kernbefund (H6) ist ein
   **Ziel**-Problem: TP1 = POC liegt in H2 bei ~13 ATR. Zwei Wege sind
   denkbar: (a) eine **Obergrenze** fuer den Zielabstand einfuehren
   (`V3_TP_MINDIST_PCT = 1,5 %` ist eine *Unter*grenze — es gibt keine
   Obergrenze), oder (b) die **Einstiegsseite** relativieren (Q29 an der
   Aussenwand ist in einem Trendabschnitt strukturell benachteiligt). Zu
   entscheiden ist, welcher Weg zuerst gemessen wird.
2. **`H7` verlangt eine Zieldefinition.** Soll die Hybrid-Schliessung auf
   `USD/Trade` optimiert werden (Empfehlung) und `Q_stop` **nur** als
   Ausschlusskriterium gefuehrt werden? Das ist die direkte Konsequenz aus
   der Antagonie in H7.
3. **Whipsaw-Kontrolle als Pflichtmetrik.** T4c zeigt die Untergrenze. Fuer
   jede Hybrid-Variante ist kuenftig **mit** zu berichten, wie viele
   *Gewinner* sie toetet (Analogon zu E-25 „getoetete Gewinner").
4. **Fortfuehrung read-only** trotz unbefriedigender H2-Teilquote — bestaetigt;
   ein Einbrand bleibt ausgeschlossen.

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache, keine S1-Untersuchung.**

---

## Phase 2 / E-30 Schritt 1 (2026-09-11, n) — Zielabstand & TP1-Deckelung: **auch der Ziel-Hebel ist falsifiziert**

Auftrag (Anwender-Freigabe): (1) Zielabstands-Geometrie vermessen,
(2) pruefen, welcher **TP1-Deckel** die 18 H2-Trades mit `MFE >= 1 R`
monetarisiert haette, ohne das TP2-Makroziel anzutasten. Read-only; die
Messung laeuft vollstaendig ueber die in E-29 gesicherten Setup-Geometrien
(`_tmp_e29_setups_*_b60.pkl`) und die identische Halb-Exit-Semantik der
Engine (Z. 1596-1647) — **keine** Engine- oder Adapter-Aenderung.

### I0 · Reproduktions-Fidelity

Der Offline-Simulator reproduziert die arretierte Bilanz **bit-identisch**:
S2 `0,5·Σr1 + 0,5·Σr2 = 0,5·(+49,004) + 0,5·(+62,739) = +55,871` — exakt der
E-28/E-29-Wert. AUG analog `+38,920`. Die Ziel-Erkennung deckt sich mit den
von der Engine gespeicherten `grund1`: **201 SL / 70 TP1** (S2), **1 SL / 7 TP1**
(AUG). **ENDE-Exits treten in der armierten Konfiguration nicht auf (0)** —
bei ~1 ATR Stop wird praktisch immer entweder der Stop oder das Ziel
beruehrt.

### I1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e30_tp1.py` | `112c8e9c4d3b08f56b875319b9f5f07acfd4bcd79fca91eecaeb7a111bc4b070` | 13.041 |
| `test/_tmp_e30_tp1_s2_out.txt` | `03e5a62d550faac8a3b9a6065731d0f181183b64ab043f78d5cc6ce47392405e` | 6.664 |
| `test/_tmp_e30_tp1_aug_out.txt` | `02e7ebeec4e00bfc7ed59f3a4a5eb08882a5f52274004d47bae7f26cb695efb4` | 6.082 |

### I2 · Z1 — Zielabstaende

| Gruppe | Groesse | min | p25 | **median** | p75 | p90 | max |
|---|---|---|---|---|---|---|---|
| gesamt | d TP1 [R] | 0,01 | 1,87 | 6,72 | 13,41 | 22,18 | 74,32 |
| gesamt | d TP1 [ATR] | 0,01 | 3,05 | 9,72 | 19,09 | 26,70 | 45,03 |
| gesamt | d TP1 [%] | 0,00 | 0,78 | 2,17 | 4,47 | 7,61 | 14,83 |
| gesamt | d TP2 [R] | 3,70 | 14,03 | 20,20 | 28,88 | 42,74 | 121,85 |
| **H1** | d TP1 [R] | 0,01 | 1,62 | **5,86** | 11,94 | 18,65 | 48,06 |
| **H2** | d TP1 [R] | 0,15 | 5,82 | **13,29** | 29,18 | 44,40 | 74,32 |
| H2 | d TP1 [ATR] | 0,22 | 6,81 | **18,90** | 24,27 | 29,11 | 45,03 |
| H2 | d TP1 [%] | 0,04 | 2,83 | **5,95** | 8,46 | 9,50 | 10,56 |
| H2 | d TP2 [R] | 13,29 | 20,56 | **32,72** | 51,60 | 65,64 | 121,85 |
| H2 | risk [ATR] | 0,32 | 0,68 | **0,96** | 1,84 | 2,07 | 3,12 |

Der H2-Befund ist bestaetigt und praezisiert: **TP1 liegt bei 13,29 R /
18,90 ATR / 5,95 % Kursweg**, waehrend der Stop nur **0,96 ATR** entfernt ist.
Das Verhaeltnis Ziel:Stop betraegt in H2 also ≈ **20 : 1**.

### I3 · Z2 — MFE-Anatomie der Stop-Outs

| Haelfte | n_Stop | MFE >= 1 R | MFE >= 2 R | MFE median | Rueckgabe median |
|---|---|---|---|---|---|
| gesamt | 201 | 86 | 44 | 0,69 | 1,69 |
| H1 | 169 | 68 | 35 | 0,58 | 1,58 |
| **H2** | **32** | **18** | **9** | **1,16** | **2,16** |

Die 18 H2-Trades mit `MFE >= 1 R` sind damit **nicht** als Gruppe von
"Gewinnern, die man haette retten muessen" bestaetigt: der Median-MFE aller
32 H2-Stop-Outs liegt bei **1,16 R** — die meisten liefen also knapp 1 R weit
und drehten dann. Das genuegt, um die Break-Even-Falle (E-29/H7) zu
erklaeren, aber es genuegt **nicht** fuer einen profitablen Teil-Exit.

### I4 · Z3 — TP1-Deckelung: **jeder Deckel verschlechtert `USD/Trade`**

Pflichtmetriken (Anwender-Vorgabe). `dR Gewinner` = R-Summe der Aenderung auf
den Basis-Gewinnern; `dR Verlier` analog auf den Basis-Verlierern.

S2 (`n = 271`, Basis `USD/Tr = +0,0526`):

| Variante | R ges. | USD/Tr | Q_stop | getoetet | gerettet | **dR Gewinner** | dR Verlier | USD-Delta |
|---|---|---|---|---|---|---|---|---|
| **BASIS** | +55,87145 | **+0,0526** | 0,742 | 0 | 0 | 0,000 | 0,000 | 0,0000 |
| Cap_R = 0,50 R | +25,36122 | +0,0318 | 0,339 | 15 | 0 | **-112,137** | +81,626 | **-5,6232** |
| Cap_R = 1,00 R | +37,23478 | +0,0382 | 0,424 | 14 | 2 | **-104,637** | +86,000 | **-3,8844** |
| Cap_R = 1,25 R | +35,98478 | +0,0353 | 0,476 | **0** | 72 | **-100,887** | +81,000 | **-4,6816** |
| Cap_R = 1,50 R | +38,65852 | +0,0356 | 0,506 | **0** | 64 | -97,213 | +80,000 | -4,6045 |
| Cap_R = 2,00 R | +31,30330 | +0,0323 | 0,579 | **0** | 44 | -90,568 | +66,000 | -5,4946 |
| Cap_R = 4,00 R | +31,98029 | +0,0338 | 0,675 | 0 | 18 | -68,891 | +45,000 | -5,0957 |
| Cap_R = 8,00 R | +44,78918 | +0,0397 | 0,716 | 0 | 7 | -42,582 | +31,500 | -3,4762 |
| Cap_ATR = 1,50 | +36,98218 | +0,0379 | 0,450 | 7 | 40 | -103,702 | +84,813 | -3,9848 |
| Cap_ATR = 2,00 | +35,79321 | +0,0361 | 0,509 | 3 | 43 | -98,678 | +78,600 | -4,4747 |

AUG (`n = 8`, Basis `USD/Tr = +1,4077`) verhaelt sich **noch schaerfer**: in
**jeder** Zeile ist `dR Verlier = 0` (kein einziger Verlierer wird gerettet)
und `dR Gewinner < 0`; das beste Cap (`Cap_R = 8 R`) bleibt mit `+1,3753`
unter der Basis.

**Kernaussage I4: In *keinem* der 21 getesteten Deckel-Werte erreicht
`USD/Trade` die Basis.** Der Deckel schmaelert die Gewinner immer staerker,
als er Verlierer rettet (S2: -112 gegen +82 R; AUG: reine Zerstoerung).

**Methodik-Erweiterung (bindend, aus I4):** Der Sign-Flip-Zaehler
"getoetete Gewinner" ist **zu grob**. Bei `Cap_R >= 1,25 R` meldet er **0**
getoetete Gewinner — und trotzdem verliert die Variante **-4,68 USD**. Die
richtige Pflichtmetrik ist **`dR Gewinner`** (R-Schmaelerung auf den
Basis-Gewinnern), nicht nur der Vorzeichenwechsel.

### I5 · Z4 — Dekomposition: **beide Haelften tragen, keine ist ein Verlusttraeger**

| Gruppe | n | H1 TP | H1 SL | H2 TP | H2 SL | Σ r1 | Σ r2 | 0,5·Σ(r1+r2) |
|---|---|---|---|---|---|---|---|---|
| gesamt | 271 | **70** | 201 | **20** | 251 | +49,004 | +62,739 | +55,871 |
| H1 | 232 | 63 | 169 | 17 | 215 | -2,844 | +27,096 | +12,126 |
| H2 | 39 | 7 | 32 | 3 | 36 | **+51,849** | +35,642 | +43,745 |

Damit ist die Arbeitsannahme aus Z5 ("die zweite Haelfte ist ein
Verlusttraeger") fuer die arretierte Konfiguration **widerlegt**: die
TP2-Haelfte (Gegenkante) traegt mit **+62,74 R sogar mehr** bei als die
TP1-Haelfte (POC, +49,00 R). Der Grund liegt im Lotterieprofil: TP2 wird nur
in **20 von 271** Faellen erreicht (7,4 %), dann aber mit grossem Hebel
(Median-`d TP2` = 20,20 R); TP1 wird in **70 von 271** Faellen erreicht
(25,8 %). **H2 wird von der TP1-Haelfte dominiert** (+51,85 der +43,75 R
Beitrag) — genau die Haelfte, die der Deckel kaputtmachen wuerde.

### I6 · Z5 — Gewichts-Sweep `w1`: monoton, aber **nicht zulassungsfaehig**

`w1 = tp1_anteil_pct / 100` (TP-Ziele unveraendert):

| w1 | S2 R ges. | S2 USD/Tr | S2 Q_stop | AUG R ges. | AUG USD/Tr | AUG Q_stop |
|---|---|---|---|---|---|---|
| 0,00 | +62,73853 | +0,0656 | **0,926** | +47,13183 | +1,6606 | 0,375 |
| 0,25 | +59,30499 | +0,0591 | 0,742 | +43,02571 | +1,5341 | 0,125 |
| **0,50 (arretiert)** | **+55,87145** | **+0,0526** | **0,742** | **+38,91958** | **+1,4077** | **0,125** |
| 0,75 | +52,43791 | +0,0461 | 0,742 | +34,81346 | +1,2812 | 0,125 |
| 1,00 | +49,00436 | +0,0395 | 0,742 | +30,70734 | +1,1547 | 0,125 |

Die Wirkung ist **monoton in `w1`** (je weniger Gewicht auf der nahen
TP1-Haelfte, desto besser `USD/Trade`). Zwei Gruende, sie **nicht** zu
verfolgen:

1. **`w1 = 0` verletzt `D1`** (`Q_stop = 0,926 > 0,75`). Der beste USD-Wert
   liegt genau auf der Grenze des zulaessigen Bereichs — ein Warnsignal,
   nicht eine Empfehlung.
2. **`tp1_anteil_pct` ist AUG-kritisch** — wie `num_bins` (E-29/H4), nicht wie
   die Lokalisierung. Die Aenderung 50 → 25 verschiebt den August-Anker von
   `+38,91958` auf `+43,02571`, d. h. V018 wird **nicht** geschuetzt. Eine
   Invarianz gibt es hier nicht.

Hinzu kommt: der Effekt haengt in S2 an **20** und in AUG an **5**
TP2-Treffern. Das ist eine statistisch nicht tragfaehige Grundlage fuer eine
Parameteraenderung. **`tp1_anteil_pct = 50 % bleibt arretiert** (Anwender-Vorgabe
E-29/H9.3).

### I7 · Ehrliche Bilanz E-30/S1 — **drei Hebel getestet, drei falsifiziert**

| Hebel | Ergebnis | Verdikt |
|---|---|---|
| Break-Even-Stop (E-29/H7) | `USD/Tr` faellt in *jedem* Wert | verworfen |
| **TP1-Deckelung (I4)** | `USD/Tr` faellt in *jedem* der 21 Werte | **verworfen** |
| Gewicht `w1` (I6) | monoton besser, aber grenzwertig + AUG-kritisch + n=20/5 | **verworfen** |

**Kernbefund E-30/S1:** Die arretierte Zielgeometrie ist **nicht defekt**.
Der grosse H2-Zielabstand (13,29 R) ist **die Kehrseite des billigen Stops**
(0,96 ATR) — nicht eine Fehlkalibrierung. Wer `R` misst, sieht grosse Zahlen;
wer `USD/Trade` misst, sieht ein System, das beide Haelften profitabel nutzt.
Die Mentor-Warnung ("13 R gegen die Physik des Orderbuchs") ist damit
**empirisch nicht bestaetigt**: genau die weiten Ziele tragen den Ertrag.

Der verbleibende Hebel liegt folglich **nicht** in der Zielgeometrie, sondern
in **(a) der Diskriminationsschaerfe der Schliessung** (E-29/H8: Spanne
+115,10 bis -52,61 R) — das ist Schritt 2 — oder **(b) der Trade-Auswahl**
(Einstiegsseite). Die Einstiegsseite ist durch I5 nicht entlastet: 25,8 %
TP1-Trefferquote bzw. 7,4 % TP2-Trefferquote sind die eigentliche Kennzahl,
an der eine Verbesserung ansetzen muss.

### I8 · Offene Entscheidungen (Textblock)

1. **Zielgeometrie ist geschlossen.** Alle drei Ziel-/Exit-Hebel sind
   gemessen und verworfen. Vorgeschlagen wird, den Zielabstand **nicht**
   weiter zu bearbeiten und direkt zu **Schritt 2 (Diskrimination der
   Hybrid-Schliessung)** ueberzugehen.
2. **Einstiegsseite als zweiter Kandidat.** Die Trefferquoten (TP1 25,8 % /
   TP2 7,4 %) sind der eigentliche Engpass. Zu entscheiden ist, ob parallel
   zur Hybrid-Schliessung die Einstiegsseite (Q29-Quartil, `V3_TP_MINDIST_PCT`,
   12-Bar-Zyklus, Cluster) vermessen werden soll — oder erst nach Schritt 3.
3. **Pflichtmetrik erweitert.** Ab jetzt ist **`dR Gewinner`** (nicht nur der
   Sign-Flip) zu berichten (I4). `Q_stop` bleibt reines Ausschluss-Gate (`D1`).
4. **Kein Parameterwechsel ohne Anker-Pruefung.** `tp1_anteil_pct` und
   `num_bins` sind AUG-kritisch; jede Aenderung an ihnen bricht V018. Diese
   Klasse von Parametern ist vor jeder Messung zu kennzeichnen.

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache, keine S1-Untersuchung.**

---

## Phase 2 / E-31 + E-31b (2026-09-11, o) — Diskrimination der Hybrid-Schliessung: **der Abstand trennt nicht, die Vorgeschichte trennt**

Auftrag (Anwender-Freigabe, Schritt 2): die Spanne zwischen der oberen
Schranke `T4b` (+115,10 R) und der unteren Schranke `T4c` (-52,61 R) auf
`L960` vermessen — **welche kausale Marktstruktur unterscheidet die
berechtigten Stopp-Outs von den getoeteten Gewinnern?**

Grundlage: Setup-Geometrien aus E-29 (`_tmp_e29_setups_*_b60.pkl`),
Kernstandard `geg960poc`. Reine Offline-Simulation ueber die Halb-Exit-Semantik
der Engine (Z. 1596-1647) — **keine** Engine- oder Adapter-Aenderung.
Pflichtmetriken (Urkunde E-30/I4): `USD/Trade`, **`dR Gewinner`**, `Q_stop`.

### K0 · Praezisierung gegenueber E-29/H8

E-29/H8 hat den Bruch-Exit als "Close jenseits der Einstiegskante" gemessen,
dabei aber den **Gesamt-R** des Trades durch den **Einzel-Halb-R** am
Bruch-Close ersetzt (und damit auch Haelften, die bereits natuerlich
geschlossen waren). E-31 schliesst **praezise je noch offener Haelfte**: eine
Haelfte, die TP1/TP2/SL bereits erreicht hat, behaelt ihr Ergebnis. Die
Zahlen weichen daher deutlich ab; die Richtung des Befunds nicht.

### K1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e31_break_disk.py` | `2537f2f01a24273ca20ce045008f2cbe718fc8a53c40195bfd9975165d69ede4` | 11.393 |
| `test/_tmp_e31b_mfe.py` | `7248d49e86c43278cc5fbd7fc17267782810439075ec69bb2a993fdd13932acb` | 7.601 |
| `test/_tmp_e31_break_disk_s2_out.txt` | `5a09019e5dfb193fc155c7e9e2af7f747977f928c8fc89b860c968244f1a8b01` | 5.254 |
| `test/_tmp_e31_break_disk_aug_out.txt` | `1b906a3205c69143405f892445c484332a227337d2feb15903eaddef2ffc0be5` | 5.252 |
| `test/_tmp_e31b_mfe_s2_out.txt` | `02c798e3041dce89168f1a4a811588d596877c7a5767cb1b1e2752cb34ff60d5` | 1.926 |
| `test/_tmp_e31b_mfe_aug_out.txt` | `b75c028e672c3b38aaf793f30d31b8610f162e34ec46b44f7674b2d7dd5951ef` | 1.934 |

Fidelity: der Simulator reproduziert die arretierte Basis bit-identisch
(S2 R +55,871446 · USD/Tr +0,0526 · AUG R +38,919584 · USD/Tr +1,4077).

### K2 · Antwort auf die Bruch-Kausalitaet: **beide Achsen sind untauglich**

Gemessen wurde die 2D-Matrix `n_consec ∈ {1,2,3}` konsekutive Closes ×
`d ∈ {0; 0,25; 0,5; 1,0} × ATR14(m)` (Abstand am **Bruch-Bar**, kausal).
Zusaetzlich die Variante `loss_only`.

S2 (`n = 271`, Basis USD/Tr +0,0526), Auszug:

| n | d [ATR] | R ges. | USD/Tr | Q_stop | Feuer | Prec | Rec | getoetet | dR Gew | dR Verl |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0,00 | +89,6785 | **+0,0684** | 0,299 | 254 | 0,917 | 0,987 | 8 | -40,59 | +74,40 |
| 1 | 0,25 | +66,9792 | +0,0583 | 0,391 | 246 | 0,915 | 0,953 | 7 | -39,32 | +50,42 |
| 1 | 0,50 | +55,0180 | +0,0530 | 0,498 | 216 | 0,921 | 0,843 | 5 | -31,51 | +30,66 |
| 1 | 1,00 | +55,3783 | +0,0524 | 0,616 | 147 | 0,918 | 0,572 | 2 | -11,26 | +10,76 |
| 2 | 0,00 | +59,0935 | +0,0566 | 0,491 | 146 | 0,911 | 0,564 | 6 | -36,14 | +39,36 |
| 2 | 0,50 | +42,8859 | +0,0489 | 0,594 | 79 | 0,899 | 0,301 | 5 | -29,96 | +16,97 |
| 3 | 0,50 | +60,8976 | +0,0571 | 0,642 | 48 | 0,979 | 0,199 | 1 | -6,65 | +11,68 |

**Auf S2 verbessert der naive Bruch-Exit (n=1, d=0) `USD/Trade` um +30 %**
(+0,0526 → +0,0684) und drueckt `Q_stop` auf 0,299. **Auf AUG kippt das
Vorzeichen:**

| | S2 | AUG |
|---|---|---|
| Basis USD/Tr | +0,0526 | +1,4077 |
| n=1, d=0 | **+0,0684** | **+1,0798** (−23 %) |
| Feuerungen | 254 / 271 | 3 / 8 |
| getoetete Gewinner | 8 | 1 |

**Der naive Bruch-Exit generalisiert nicht** — er ist eine Regime-Wette
("schliesst fast alles"), keine Diskrimination. Der Grund: er feuert auf S2
in **94 %** aller Trades, auf AUG in 38 %.

### K3 · Der entscheidende Negativbefund — der Abstand trennt NICHT

`P5` vergleicht die Bruch-Distanz der Basis-Gewinner gegen die der
Basis-Verlierer (n=1, d=0):

| Gruppe | p25 | median | p75 | Anteil < 0,25 ATR | Anteil < 0,5 ATR |
|---|---|---|---|---|---|
| Basis-Gewinner | 0,18 | **0,39** | 0,48 | 33,3 % | 76,2 % |
| Basis-Verlierer | 0,17 | **0,36** | 0,77 | 35,6 % | 60,9 % |

**Die Verteilungen sind praktisch identisch.** Kein Mindestabstand, keine
`n_consec`-Schwelle kann Gewinner von Verlierern trennen — die Antwort auf
die Anwenderfrage lautet: **weder 2 Closes noch ein ATR-Mindestabstand.**

### K4 · Der Diskriminator: **die Vorgeschichte (MFE vor dem Bruch)**

`P4`/`P6b` zeigen, wo der Unterschied wirklich liegt:

| Gruppe | n (mit Bruch) | Bruch nach … Bars (med) | Dist [ATR] (med) | **MFE vor Bruch (med)** | base_R med |
|---|---|---|---|---|---|
| Basis-Gewinner | 21 | **84,0** | 0,39 | **2,75 R** | +2,81 |
| Basis-Verlierer | 233 | **1,0** | 0,36 | **0,23 R** | −1,00 |

**Nicht "wie weit bricht es", sondern "hat der Trade vorher gearbeitet"
diskriminiert.** Verlierer brechen nach **1 Bar** mit MFE 0,23 R; Gewinner
brechen nach **84 Bars** mit MFE 2,75 R.

### K5 · E-31b — die MFE-bedingte Schliessung generalisiert

Regel: Bruch schliesst **nur**, wenn `MFE vor dem Bruch < mfe_cap R`.

S2 (`n = 271`, Basis +0,0526):

| mfe_cap | R ges. | USD/Tr | ATR/Tr | Q_stop | Feuer | Skip | Prec | Rec | getoetet | **dR Gew** | dR Verl |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,25 | +74,1463 | +0,0633 | +0,4991 | 0,520 | 121 | 133 | 0,967 | 0,496 | 4 | −17,77 | +36,05 |
| 0,50 | +82,4036 | +0,0672 | +0,5473 | 0,472 | 142 | 112 | 0,972 | 0,585 | 4 | **−17,77** | +44,30 |
| **0,75** | **+89,3250** | **+0,0727** | **+0,5952** | **0,435** | 158 | 96 | 0,975 | 0,653 | **4** | **−17,77** | +51,23 |
| 1,00 | +80,7729 | +0,0698 | +0,5794 | 0,395 | 175 | 79 | 0,966 | 0,716 | 6 | −33,17 | +58,07 |
| 1,50 | +84,2742 | +0,0713 | +0,5903 | 0,362 | 196 | 58 | 0,964 | 0,801 | 7 | −35,83 | +64,23 |
| aus | +89,6785 | +0,0684 | +0,5717 | 0,299 | 254 | 0 | 0,917 | 0,987 | 8 | −40,59 | +74,40 |

AUG (`n = 8`, Basis +1,4077):

| mfe_cap | R ges. | USD/Tr | Q_stop | Feuer | Skip | getoetet | dR Gew | dR Verl |
|---|---|---|---|---|---|---|---|---|
| **0,25–1,25** | **+39,7798** | **+1,4330** | 0,000 | 1 | 2 | **0** | **+0,00** | +0,86 |
| 1,50–3,00 | +32,7511 | +1,0798 | 0,000 | 2 | 1 | 1 | −7,03 | +0,86 |
| aus | +32,7511 | +1,0798 | 0,000 | 3 | 0 | 1 | −7,03 | +0,86 |

**Der MFE-Cap repariert genau den AUG-Schaden des naiven Bruchs**
(+1,0798 → +1,4330). Verdikt:

1. **S2: +0,0526 → +0,0727 USD/Trade (+38 %)** bei `Q_stop` 0,435 ≤ 0,75.
2. **`dR Gewinner` halbiert sich: −40,59 → −17,77 R** (Cap 0,75).
3. **Getoetete Gewinner: 8 → 4.**
4. **AUG: keine Verschlechterung** (+1,4330 vs +1,4077), `dR Gewinner = 0`.
5. Die Regel ist **kausal** (MFE bis zum Vortag) und **generalisierend** —
   anders als der naive Bruch (K2).

**Ehrliche Einschraenkung:** auf AUG feuert der Cap in nur **1 von 8** Trades;
der AUG-"Zugewinn" (+0,0253 USD/Tr) ruht auf einem einzigen Trade. AUG ist
damit **neutral, nicht bestaetigend**. Die S2-Verbesserung dagegen ist breit
(158 Feuerungen, `dR Verl +51,23`).

### K6 · Abstand zur oberen Schranke

| | R | USD/Tr |
|---|---|---|
| Basis | +55,8714 | +0,0526 |
| **E-31b, Cap 0,75** | **+89,3250** | **+0,0727** |
| `T4b` obere Schranke (E-29, ex post) | +115,10 | +0,0836 |

Die Regel schliesst **~65 %** der Luecke zur ex-post-idealen Schranke
((0,0727−0,0526)/(0,0836−0,0526) = 0,0201/0,0310) und **~78 %** in `R`.

### K7 · Offene Entscheidungen (Textblock)

1. **Parameterwahl `mfe_cap`.** S2 bevorzugt 0,75 (bester `USD/Trade` und
   bester `dR Gewinner`), AUG ist im Band 0,25–1,25 indifferent.
   Vorgeschlagen wird **`mfe_cap = 0,75 R`** (S2-optimum mit maximalem
   Gewinnerschutz) — alternativ `1,0 R` als runde, PineScript-taugliche Zahl
   (S2: +0,0698, `dR Gew −33,17`). Zu entscheiden.
2. **AUG-Evidenz ist duenn** (1 Feuerung). Zu klaeren, ob vor dem Einbrand
   eine dritte Datenreihe (oder eine H1/H2-getrennte AUG-Auswertung)
   herangezogen werden soll.
3. **Interaktion mit `D1`.** Die Regel drueckt `Q_stop` deutlich unter 0,75
   (0,435). Da `Q_stop` nur Ausschluss-Gate ist, darf das **nicht** als
   Begruendung zaehlen — massgeblich ist `USD/Trade` (+0,0727) und
   `dR Gewinner` (−17,77).
4. **Naechster Schritt.** Formulierung als Schliesskriterium im Vertragsentwurf
   (`SchliessKriterium`) inkl. Type Hints. Vorher ist zu entscheiden, ob die
   Bedingung als **Regime-Ende** (Zustandsautomat, Block A) oder als
   **Stop-Variante** (Engine-seitig) implementiert wird — die Wirkung ist
   identisch, die Verdrahtung nicht.

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache, keine S1-Untersuchung.**
