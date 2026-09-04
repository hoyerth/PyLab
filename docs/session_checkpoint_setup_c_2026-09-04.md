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
