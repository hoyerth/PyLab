# SESSION-CHECKPOINT SETUP C (04.09.2026)

## Erreichter Meilenstein
- Setup A formal archiviert (docs/counter_engine_experiment.md aktualisiert).
- docs/setup_c_experiment.md angelegt und committet (9cc4097).
- Schritt 1 vollständig abgeschlossen:
  - AUG-Matrix verifiziert (11 Brüche).
  - S1 (138 Brüche) und S2 (61 Brüche) per DuckDB read-only extrahiert.
  - MFE/MAE-Verteilung berechnet und im Prüfbericht fixiert.
  - Kernbefund: 55,1 % Früh-Shakeout in S1 bei 0,45 % SL. Kinetische Energie wächst bis Bar 48 auf median 2,97R (S1) / 2,20R (S2).

## Offene Punkte für morgen
1. Doku-Update: Tracking-Log in docs/setup_c_experiment.md um Teilschritt 1.1–1.4 ergänzen.
2. Schritt 2: Bau des isolierten Lese-Replay-Skripts `test/tmp_setup_c_audit.py` für die 3 Arme:
   - Arm 1: BREAKOUT_RAW (mit 1,5x SMA20 Volumen-Bedingung)
   - Arm 2: BREAKOUT_CONFIRMED (2-Close-Bruch)
   - Arm 3: RETEST_OUTSIDE (Kantenkontakt +/- 0.15 USD mit Close-Verteidigung)
3. Initial-Stop-Architektur: Berücksichtigung des 55-%-Shakeouts (struktureller Stop vs. Puffer-Stop).

## Nachtrag 05.09.2026: Artefakt-Cleanup in test/ abgeschlossen
- **Gelöscht (147 Dateien):** Alle abgeschlossenen Symbol-Testlauf-Artefakte QS-4..QS-8 (Brent/Cocoa/EURUSD/Ger40/NGas PNGs, stats_trades_*, tmp_* Engine-Logs/Sweeps/Params/Reports), GOLD- & MAKRO-Testläufe, SILVER_LONG-Stresstest-Artefakte (inkl. stats_trades_SILVER_LONG_equity.txt), `tmp_monthly_agg.py`, `tmp_dbcheck.py`.
- **Verifiziert:** RESTMATCH 0 / MISSING KEEPERS 0 (gitignored → kein Commit, Working Tree sauber).
- **Erhalten (Setup-C-/Analyse-Kontext):** SILVER-Baseline (phasen_volumen_profil{AUG,S1,S2}.*, stats_trades{AUG,S1,S2}.*), `tmp_phasen_volumen_profil_symbol.py` (Engine-Arbeitskopie), Bruch-Matrizen, Setup-C-Schritt-1-Artefakte, `tmp_setup_c_antworten_f1f3.txt`, generische Symbol-Helper (`tmp_symbol_{params,sweep,equity,summary,vorabcheck}.py`), Session-Handoffs.
- Doku zentraler Ergebnisse bleibt in `docs/archiv/Symbole Testläufe.md` (§§1–26).
