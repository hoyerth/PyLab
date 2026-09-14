# Setup C — archiviert (stillgelegt am 2026-09-14)

**Status: BEENDET. Kein Handelspfad. Kein Edge nachgewiesen.**

Dieses Verzeichnis ist ein eingefrorenes Archiv. Es wird nicht weiterentwickelt.
Die Module sind lauffähig erhalten (siehe „Reproduzierbarkeit"), aber nicht mehr
Teil der Produktion. Nachfolger: die Engine **Volume Balance**.

---

## 1. Was Setup C war

Ein Ausbruchs-Setup auf der eingefrorenen Phasen-Segmentierung der
Produktions-Baseline (`scripts/phasen_volumen_profil.py`, v0.4.0-baseline-frozen,
+297,14R). Die Kette:

```
Pivots (Lookback 2)
  -> Schnittmengen-/Dichte-Linie (density_band 0.15 USD)
  -> Phasen-Etablierung (min_establish 4 Touches, min_phase_candles 46)
  -> 2-Close-Bruch (Toleranz TOL 0.34 USD) [Stufe 0]
  -> Volumen-Durchstoss an der kausalen Kante [Stufe 1]
  -> Entry Open(trigger+1) [Stufe 2]
  -> F4-Stop intrabar (Puffer 0.15 USD) [Stufe 3]
  -> Exit F4 intrabar (Vorrang) oder Close entry+48/96
```

Drei Arme wurden parallel geführt: `RAW` (Volumen-Durchstoss, der Handelspfad),
`CONFIRMED` (Einstieg `Open(brk_idx+2)`, kausal sauber) und `RETEST`
(Pullback an die gebrochene Kante).

## 2. Warum beendet — die Befunde

### 2.1 Ein Lookahead trug praktisch den gesamten Ertrag

Der Auswahlfilter des ursprünglichen „RAW-Cluster A" war
`vorlauf_bars <= 1`. `vorlauf` ist der Abstand Trigger-Bar → 2-Close-Bruch,
und er wurde **im Einstiegs-Bar entschieden, bevor `close[brk_idx]` und
`close[brk_idx+1]` bekannt waren**. Attribution über MAI–AUG 2026:
10 von 23 Cluster-A-Trades mit `vorlauf == 1` trugen ~100 % der Summe;
die übrigen 13 mit `vorlauf == 0` ergaben +0,14R (N48) bzw. −1,38R (N96).

Der Filter wurde entfernt (Commit `a720101`). Seither ist der Pfad kausal
sauber — und die Erträge sind entsprechend dünner.

### 2.2 Der einzige saubere kausale Arm trägt nicht

Nach Entfernung des Lookaheads, live-kausal, 73 Trades, 4 Monate SILVER M15:

| Arm | N48 | N96 | TR300 |
|---|---|---|---|
| RAW (live-kausal) | +36,74R (PF 1,84) | +42,92R (PF 1,85) | +24,01R (PF 1,76) |
| **CONFIRMED** (kausal sauber) | **+5,10R** | **+8,75R** | **+2,45R** (PF ≈ 1,1) |
| RETEST | negativ | negativ | negativ |

Die Live-Summe stammt zu ~70 % aus **Mai** (N48 pro Monat: MAI +25,70 ·
JUN +1,67 · JUL +11,12 · AUG −1,75). Ein einzelner Monat trägt das Ergebnis.

### 2.3 Brent M15 überträgt den Befund nicht

Dieselben vier Monate (MAI–AUG 2026), Brent M15, 65 Trades:

| Modus | sum R | PF | MDD |
|---|---|---|---|
| BASE N48 | **−13,11R** | 0,73 | −20,49R |
| BASE N96 | **−3,10R** | 0,94 | −20,66R |
| TR N300 | **−11,16R** | 0,71 | −18,81R |

Der Silber-Befund war also instrumentenspezifisch, nicht strukturell.

### 2.4 Der Detektor erkennt keine Balance (fairer Test)

Der erste Testlauf schien das Gegenteil zu zeigen (Range-Perzentil 0,0 %).
Das war ein **Testfehler**: verglichen wurde der Dichte-Linien-Range
`U_final − L_final` (liegt *innerhalb* der Extreme) gegen den rohen
`max − min`-Range eines Zufallsfensters — nahezu tautologisch.

Fairer Test (roher `max(high) − min(low)` des Phasenfensters gegen
Zufallsfenster **gleicher Länge**):

| Symbol | Perzentil (median) | Range < 50 % aller Zufallsfenster |
|---|---|---|
| SILVER | **48,8 %** | 50,0 % |
| Brent | **45,9 %** | 55,7 % |

Ein Phasenfenster, das Setup C „Balance" nennt, hat denselben Gesamt-Range
wie ein beliebiges Fenster gleicher Länge. **Die Segmentierung isoliert
keine Kompression.**

Beitragender Konstruktionsfehler: `TOL` und `density_band` sind **absolute
USD-Schwellen**, nicht vol-normalisiert.

| | ATR(20) median | `TOL=0,34` | `density_band=0,15` |
|---|---|---|---|
| SILVER | 0,2635 | **1,29 ATR** | 0,57 ATR |
| Brent | 0,3830 | **0,89 ATR** | 0,39 ATR |

Dieselbe Konstante bedeutet pro Instrument etwas anderes.

### 2.5 Der Markt hat die Struktur — aber sie sagt nur die Größe

Detektor-unabhängig, über realisierte Volatilität (`rv_10 / rv_96`),
Expansion = Range der nächsten 48/96 Bars, ATR-normiert:

* Spearman(compression, expansion) = **−0,24 … −0,32** (SILVER),
  **−0,24 … −0,27** (Brent) — **gleiches Vorzeichen in allen 8 Monat×Symbol-Zellen**.
* Quintile streng monoton: engstes Volatilitäts-Quintil → 9,8–10,3 ATR,
  weitestes → 7,0–7,2 ATR (Verhältnis 1,41–1,49).
* Engste 10 %: **+1,7 bis +3,5 ATR** mehr Expansion, p < 0,001.

Also: **nicht** „zu volatil, keine Balance". Die Kompression ist da und stabil.
Sie sagt die **Amplitude**, nicht die **Richtung**.

### 2.6 Die Richtung ist der Bruch — und der Bruch sagt nichts

Mit perfektem Kompressions-Detektor (die eigene Segmentierung vollständig
umgangen), Entry `Open(t+1)`, ATR-normiert, signed:

| Symbol | N | MOM | p |
|---|---|---|---|
| SILVER | 48 | −0,19 ATR | 0,80 |
| SILVER | 96 | +0,03 ATR | 0,46 |
| Brent | 48 | −0,74 ATR (ANTI +0,74, p=0,001) | 0,999 |
| Brent | 96 | −0,37 ATR (DRIFT +1,62, p=0,000) | 0,82 |

Die „signifikanten" Zellen **widersprechen sich im Vorzeichen**: Brent N48 →
Mean-Reversion, Brent N96 → Momentum. Monatlich dasselbe Muster
(MOM N96 SILVER: MAI +0,11 · JUN +0,64 · JUL +0,94 · **AUG −1,31**;
Brent: **MAI −1,90** · JUN +0,53 · JUL +1,45 · **AUG −2,27**).
12 Einzeltests ohne Multi-Test-Korrektur, Vorzeichenwechsel über Horizont
und Monat → Rauschen, kein Edge.

### 2.7 Fazit

Die Prämisse „Ausbruch aus Balance → Fortsetzung" ist **nicht getragen** —
aber nicht, weil der Markt unerkennbar wäre, sondern weil der Ausbruch
nichts über die Fortsetzung aussagt. Ein besserer Detektor würde eine
widerlegte Idee präziser abbilden.

## 3. Was NICHT archiviert wurde (geteilte Infrastruktur)

Diese Module liegen weiterhin unter `scripts/` und sind **nicht** Setup-C-exklusiv:

| Modul | Grund |
|---|---|
| `scripts/market_segmentation.py` | Extraktion aus der **eingefrorenen Produktions-Baseline** `phasen_volumen_profil.py`. Wird von `regime_filter.py` importiert und ist Ausgangspunkt für Volume Balance. |
| `scripts/regime_filter.py` | Stufe-5-Modul (Regime-Klassifikation, §2.16). Eigenständige Bibliothek; von Setup C nur optional im Gate-Pfad genutzt. |

Die archivierten Skripte importieren diese beiden weiterhin als `scripts.*`
und bleiben damit bei laufendem Projekt-Root reproduzierbar.

## 4. Verzeichnisübersicht

```
Archiv/Setup C/
  README.md                     <- dieses Dokument
  scripts/                      setup_c_profil.py, setup_c_chart.py, setup_c_konsolidat.py
  docs/                         setup_c_experiment.md, session_checkpoint_setup_c_2026-09-04.md
  reports/setup_c/              alle Lauf-Artefakte (TXT/TSV/PNG), Silber + Brent
  tests/setup_c/                alte Sonden (tmp_setup_c_*), inkl. regime_stufe5/
  tests/setup_c/silber_backup/  SHA-Belege der Silber-Bitgenauigkeit (2026-09-14)
  tests/setup_c/silber_recheck/ Gegenproben-Laeufe
  tests/_ref_baseline_pre_ema/  §2.14-Referenzanker AUG/S1/S2
  diagnose/                     die Messungen zu Abschnitt 2.4–2.6
```

### Diagnose-Skripte (`diagnose/`)

| Datei | Zweck |
|---|---|
| `diag_phase_tragfaehigkeit.py` | v1 — **enthält den voreingenommenen Tightness-Test** (dokumentierter Fehler) |
| `diag_phase_tragfaehigkeit_v2.py` | v2 — fairer Tightness-Test + Follow-Through-Null |
| `diag_balance_struktur.py` | v3 — Compression→Expansion, detektorunabhängig |
| `diag_richtung.py` | v4 — Richtungsvorhersagbarkeit |
| `recheck_silber_setup_c.py` | Bitgenauigkeits-Gegenprobe nach dem Symbol/Timeframe-Umbau |
| `hash_silber_referenz.py` | SHA256-Vergleich der Silber-Referenzartefakte |

Die zugehörigen CSV-Ausgaben liegen unter `tests/setup_c/`.

## 5. Reproduzierbarkeit

Vom Projekt-Root aus bleiben die Module lauffähig (Namespace-Import
`scripts.*`; der `sys.path`-Guard greift beim Direktaufruf):

```powershell
.venv\Scripts\python.exe -X utf8 "Archiv/Setup C/scripts/setup_c_profil.py" `
    --start=2026-08-01 --ende=2026-09-01 --bezeichnung=REF
```

Der Report-Ordner in `TrendConfig.report_dir` zeigt absolut auf
`<projekt>/reports/setup_c` — **für einen Archiv-Lauf `report_dir` explizit
umsetzen**, sonst wird der (nicht mehr existierende) Produktionspfad angelegt.

## 6. Übergabe an Volume Balance

Verwertbar:

1. `load_data()` in `scripts/market_segmentation.py` — BKZ-korrektes Lesen
   (`time AT TIME ZONE 'UTC'`), parametrisiert nach Symbol/Timeframe.
2. Die Kausalitäts-Disziplin: Entry erst am Open der Folge-Bar, Kanten aus
   `U_hist`/`L_hist`, Volumen mit `shift(1)`. Der Lookahead-Befund aus 2.1
   ist die Lehre daraus.
3. Der Messapparat aus `diagnose/` als Abnahmekriterium: **jedes** neue
   Signal muss sich gegen einen Permutations-Null behaupten, bevor es
   gehandelt wird.

Nicht verwertbar: die Phasen-/Balance-Definition (Abschnitt 2.4) und der
2-Close-Bruch als Fortsetzungs-Signal (Abschnitt 2.6).

## 7. Offene Punkte / Warnung

* Die Archivierung berührt `scripts/regime_filter.py` **nicht**. Entscheidung
  offen, ob das Stufe-5-Modul mit seinem Lastenheft (`docs/setup_c_experiment.md`,
  jetzt in diesem Archiv) eigenständig weitergeführt oder ebenfalls stillgelegt wird.
* `test/tmp_kanten_engine_replay.py`, `test/_tmp_vd_vertrag_entwurf.py` und
  `test/CHECKPOINT_2026-09-13_AUG26.md` gehören zur **Kanten-Engine (Setup B)**,
  nicht zu Setup C, und wurden bewusst nicht angefasst — sie sind über
  SHA256-Anker in `CHECKPOINT_2026-09-13_AUG26.md` referenziert.
* `test/SESSION_HANDOFF.md` ist ein eingefrorenes Protokoll und referenziert
  weiterhin die alten `setup_c_*`-Pfade. Es wurde nicht verändert.
* Stichprobenumfang aller Befunde: 4 Monate, 2 Instrumente, 1 Timeframe (M15).
