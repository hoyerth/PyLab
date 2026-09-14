# SESSION-START 2026-09-04 — Makro-Swings Experiment / Pfad B (Baseline-Fehltrade-Obduktion)

> **Zweck:** Selbst-bootstrappender Session-Speicher für den Chat-Neustart am 04.09.2026.
> Zuerst DIESE Datei lesen, dann die referenzierten Doku-Abschnitte.
> **Kommunikation:** Deutsch · **Code/Bezeichner:** Englisch · Keine UI-/Regressionstests
> (nur py_compile + Inspektion + gezielte Tests in `test/`).

---

## 🔁 1. WO IST DER STATE OF TRUTH?

**`docs/makro_swings_experiment.md`** (1982 Zeilen, UTF-8) — Tracking-Doku des
Makro-Swings-Experiments mit:
- **§1 Schutz-Invarianten** (verbindliche Regeln)
- **§6 Tracking-Log** (chronologische Commit-/Befund-Historie, 32 Zeilen)
- **§8 OOS-Prüfplan S1/S2** und **§8.8–§8.12** = heutige Arretierungen (siehe unten)
- Belege (gitignored) liegen in `test/` (tmp_*-Dateien), nicht committet.

**Eingefroren / NICHT anfassen:**
- `scripts/phasen_volumen_profil.py` = **Produktions-Baseline** (eingefroren, +297.14R Referenz)
- `scripts/macro_persistence.py` = Tier 2 (eingefroren, rein lesend)
- `scripts/phasen_makro_swings.py` = Arbeitskopie, **bitgenau zur Baseline** (Commit `d99abbb`), arretiert
- `docs/reclaim.md` = SEPARATER Tier-2-/Confluence-Strang (kennt den Makro-Swings-Pfad-B NICHT — nicht verwechseln)
- `test/SESSION_HANDOFF.md` = eingefrorenes historisches Protokoll (01.–02.09.), nur Archiv

---

## 🔁 2. GIT-STAND (HEAD = `15166ab`)

Branch master, **12 Commits vor origin/master** (ungpusht). Letzte 4 heute Abend:

```
15166ab docs: §8.12 Initialisierungsphasen-Audit AUG arretiert (Vakuum-Hypothese datenwiderlegt)
30fc043 docs: §8.11 AUG-Stresstest Anker-Volumen-Ratio-Filter arretiert (Overfit-Verdikt)
7254179 docs: §8.10 Anker-Audit AUG arretiert (Geister-Trades: Veto netto -12.84R schaedlich)
d45ac96 docs: §8.9 Baseline-Fehltrade-Audit AUG arretiert
c9a7c7e docs: S8.8 Tier-2-Veto-Negativbefund (Wand-Regel) arretiert + Tracking-Log S6
b1aa3d7 docs(makro-swings): S2-Messung arretieren (+99.88R, Gesamt S1+S2 = +297.14R abgeschlossen)
d99abbb refactor(makro-swings): Option A ausgefuehrt - Rueckbau E3 & Reissleine (Arbeitskopie), Verifikation bitgenau
```

Untracked (Absicht, nicht committen ohne Rücksprache): `.marimo.toml`,
`Notebooks/03_Backtest_Lab.py`, `data/backtest_ui_state.json`,
`docs/reclaim_v04_mentor_vorlage.md`.

---

## 🔁 3. AKTUELLER ARBEITSSTROM: Pfad B (Baseline-Fehltrade-Obduktion)

**Ziel:** Systemische Schwachstellen in den Verlust-Trades der reinen Baseline-Engine.
**Reihenfolge strikt sequentiell: AUG (fertig) → S1 (NÄCHSTER) → S2 → Synthese.**
Reine Exploration/Doku, kein Produktivcode.

### AUG-Quadrant ABGESCHLOSSEN (4 Arretierungen in docs/makro_swings_experiment.md):

| § | Befund (Kern) |
|---|---|
| §8.9 | **15 Losses** (T3,4,5,7,8,9,10,11,12,13,16,17,18,22,26) aus 27 Baseline (12W/15L/+24.97R/PF 2.83). Trigger **100 % regelkonform** (kein Bug). 13 Voll-SL + 2 Teilverluste (TP2-Reichweite). Naive Filter datenwiderlegt. **Muster A** Expansion-Trap/Kanten-Drift (P5 zweigeteilt; T14/T15 shorteten dieselbe Kante 66.284 + Turn = Kostenstruktur des Fade-Edges), **B** junge Profile, **C** TP2-Reichweite |
| §8.10 | **Anker-Audit (Geister T9/T10/T11/T26):** Distanz trennt nicht, Volumen-Ratio ist Diskriminator (T14/T15 2.40 vs. 0.48–1.07). 66.284-Anker aus P4-Endphase (Bar 286), nicht Phase 2/3. Veto-Bilanz Variante B 1.5×: 12/15 Verlierer geblockt, aber **9/12 Winner fälschlich → Netto −12.84R: Anker-Veto netto-schädlich** |
| §8.11 | **AUG-Stresstest Volumen-Ratio-Filter (alle 27):** Keine der 4 Varianten übertrifft Baseline (AUG nach Filter ≈ +8.0…+12.1R vs. +24.97R; Δ −12.8…−17.0R). Gegencheck: 9/12 Winner geblockt (−23.48R). **Verdikt: KEIN Alpha-Verstärker — blinder Overfit an P5-Cluster; Filter endgültig verworfen** |
| §8.12 | **Initialisierungsphasen-Audit:** Nur 2/27 (T7, T25, Bar 2) in echter Initialisierung; **Geister T9–T11/T26 sind KEINE Initialisierungs-Trades** (0b 23/35/47/38, 7–13 bestätigte Pivots, abgeschlossene Pullbacks). INIT-Kontrast T7 −1.00R vs. T25 +1.83R → nicht verlust-deterministisch. Winner T14/T15 = reifste Struktur (Alter 156/182, 41/48 Pivots). Kerzenschwelle <25 = In-Sample-Fit an T9 (+2.19R), sonst negativ. **Verdikt: Vakuum-Hypothese datenwiderlegt — Geister = Muster A Kanten-Drift** |

### Kernaussage AUG: Die 15 Losses sind regelkonforme Kosten des Fade-Edges —
kein Anker-Mangel, kein Volumen-Filter, kein Initialisierungs-Vakuum trennt sie
von den 12 Winnern. Kein Filter-Kandidat hat die AUG-Prüfung bestanden.

---

## 🔁 4. NÄCHSTER SCHRITT: S1-Obduktion (Schritt 2 von Pfad B)

**Auftrag laut Plan (§8.10.4/§8.12.6):** S1 = 2026-02-05 → 2026-08-28,
**216 Baseline-Trades** (aus `test/stats_trades_MAKRO_S1.txt`, Baseline-Block),
~90 Verlust-Trades. Gleiche Methodik wie AUG (§8.9.1):
1. exec-Import-Replay der Baseline (`scripts/phasen_volumen_profil.py`, Cut nach
   `reclaim_signals.sort`) → Mapping bitgenau gegen stats_trades-Log
2. Trigger-Integrität (Cooldown ≥ 12, CRV ≥ 1.0, Bounce ≥ 2, Reclaim)
3. Filter-Kontrast Winner/Loser (Alter, Penetration, Anker, Pullback-Struktur)
4. Muster A/B/C-Dominanz prüfen; danach S2 (2025, Low-Vol), dann Synthese

**Verfügbare AUG-Helfer als Methodik-Vorlage (in `test/`, gitignored):**
- `tmp_baseline_loss_replay.py/.txt` — exec-Import-Replay + Audit-Anreicherung
- `tmp_anchor_audit.py` + `tmp_anchor_audit_AUG.txt` — Anker/Pivot-Pool-Audit
- `tmp_pivot_vol_probe.py` — Volumen-Ratio-Sondierung
- `tmp_stresstest_bilanz.py/.txt` — Filter-Bilanz-Rechnung
- `tmp_init_phase_audit.py/_AUG.txt`, `tmp_pb_def_vergleich.py`, `tmp_init_verdichtung.py` — Initialisierungs-Audit
- Referenz-Logs: `test/stats_trades_AUG.txt` (27 Trades, Bar-Indizes), `test/stats_trades_MAKRO_S1.txt`, `test/stats_trades_MAKRO_S2.txt`

---

## 🔁 5. KONTEXT-RAHMEN (für schnellen Wiedereinstieg)

- **Projekt:** Quant-Desktop-App, SILVER M15, DuckDB (`data/market_data.duckdb`, UTC,
  MT5-Epochs = Berlin-Wanduhr, SQL strikt `AT TIME ZONE 'UTC'`).
- **Baseline-Referenz (v0.4.x):** AUG +24.97R (27 Trades), S1 +197.26R (201 Sig),
  S2 +99.88R (210 Sig) → **S1+S2 = +297.14R** (Ziel ≥ +292.14R erreicht, OOS freigabefähig).
  Alle Experimente laufen auf Arbeitskopien; Baseline wird NIE verändert.
- **Reclaim-Kontext (docs/reclaim.md):** Tier-2-Veto-Modell (Wand-Regel) negativ
  (§8.8), CRV2-Filter negativ (§8.7), E3-Rückbau (Option A) arretiert — diese Stränge
  sind abgeschlossen, NICHT wieder aufrollen.
- **Regeln:** Keine Loops in Strategie-Logik (Ausnahme kausaler Signal-Loop);
  Parametrisierung; Test-Dateien nur in `test/`; keine UI-/Regressionstests;
  Commit-Signatur „Generated with [Continue](https://continue.dev) /
  Co-Authored-By: Continue <noreply@continue.dev>".

---

## ✅ SICHERUNG BESTÄTIGT (03.09.2026, 23:00)

- Alle 4 heutigen Audits (§8.9–§8.12) sind in `docs/makro_swings_experiment.md`
  arretiert und committet (HEAD `15166ab`, siehe §2).
- Tracking-Log §6 führt 32 Zeilen (vollständige Historie inkl. heute).
- Beleg-Helfer und Logs liegen in `test/` (gitignored, bleiben bis Abschluss der
  Explorationsphase erhalten — I4-Cleanup erst NACH S1/S2/Synthese).
- DIESE Datei ist der neue Bootstrap für morgen.
