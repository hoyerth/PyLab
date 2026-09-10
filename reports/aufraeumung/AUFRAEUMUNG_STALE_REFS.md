# Stale Doku-Referenzen nach Aufraeumung test/ (2026-09-10)

Diese Dokumente/Module nennen einen `test/<datei>`-Pfad, der nach dem
Umzug unter `test/<thema>/<datei>` liegt. **Kein Laufzeitbezug** -
geprueft: nur `backtest_lab/phasen_regime_adapter.py` ->
`tmp_kanten_engine_replay.py` ist ein echter Codebezug (unveraendert, bleibt).

**Entscheidung F3 (Anwender):** Korrektur **nur unter `/reports`** (versioniert,
siehe Abschnitt "F3 - ausgeführte Korrekturen"). Die `docs/`-Stellen bleiben
bewusst historisch stehen (Docs werden laut Arbeitsregel ignoriert).

| genannter Pfad | tatsaechlich jetzt | genannt in |
|---|---|---|
| `test/regime_schwellen_freezed.json` | `test/silver_regime/regime_schwellen_freezed.json` | `docs\setup_c_experiment.md`, `scripts\regime_filter.py`, `scripts\setup_c_profil.py` |
| `test/stats_reclaim_snapshot_replay.txt` | `test/reclaim_live/stats_reclaim_snapshot_replay.txt` | `docs\reclaim_historie_index.md` |
| `test/stats_trades_S1.txt` | `test/silver_regime/stats_trades_S1.txt` | `docs\reclaim_historie_index.md` |
| `test/tmp_alpha_landkarte_report.txt` | `test/counter_engine/tmp_alpha_landkarte_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_anchor_audit_AUG.txt` | `test/counter_engine/tmp_anchor_audit_AUG.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_anchored_vwap_l1.py` | `test/reclaim_live/tmp_anchored_vwap_l1.py` | `docs\reclaim_avwap_roadmap.md`, `docs\setup_c_experiment.md` |
| `test/tmp_baseline_loss_replay.txt` | `test/counter_engine/tmp_baseline_loss_replay.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_capitulation_check_report.txt` | `test/counter_engine/tmp_capitulation_check_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_consecutive_loss_audit.txt` | `test/counter_engine/tmp_consecutive_loss_audit.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_counter_engine_pruefbericht_s1s2.txt` | `test/counter_engine/tmp_counter_engine_pruefbericht_s1s2.txt` | `docs\counter_engine_experiment.md` |
| `test/tmp_diag_kanten_delta.txt` | `test/trash/tmp_diag_kanten_delta.txt` | `docs\setup_c_experiment.md` |
| `test/tmp_drift_dichte_v2.txt` | `test/counter_engine/tmp_drift_dichte_v2.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_dwell_time_report.txt` | `test/counter_engine/tmp_dwell_time_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_edge_drift_report.txt` | `test/counter_engine/tmp_edge_drift_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_h1_aug_sanity_report.txt` | `test/counter_engine/tmp_h1_aug_sanity_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_h1_full_run_report.txt` | `test/kanten_engine/tmp_h1_full_run_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_imbalance_report.txt` | `test/counter_engine/tmp_imbalance_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_init_phase_audit_AUG.txt` | `test/counter_engine/tmp_init_phase_audit_AUG.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_kanten_engine_aug_katalog.py` | `test/kanten_engine/tmp_kanten_engine_aug_katalog.py` | `docs\session_checkpoint_kanten_engine_v3_2026-09-06.md` |
| `test/tmp_kanten_engine_b_smoke.py` | `test/kanten_engine/tmp_kanten_engine_b_smoke.py` | `docs\session_checkpoint_kanten_engine_v3_2026-09-06.md` |
| `test/tmp_kanten_engine_basickanten_abgleich.py` | `test/kanten_engine/tmp_kanten_engine_basickanten_abgleich.py` | `docs\session_checkpoint_kanten_engine_v3_2026-09-06.md` |
| `test/tmp_kanten_engine_replay_pre_p9.py` | `test/trash/tmp_kanten_engine_replay_pre_p9.py` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_lookahead_beweis.py` | `test/kanten_engine/tmp_lookahead_beweis.py` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_m5_aug_sanity_report.txt` | `test/counter_engine/tmp_m5_aug_sanity_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_m5_aug_zeit_aequivalent_report.txt` | `test/counter_engine/tmp_m5_aug_zeit_aequivalent_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_orphaned_turns_report.txt` | `test/counter_engine/tmp_orphaned_turns_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_p8_verify.py` | `test/kanten_engine/tmp_p8_verify.py` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_p9_boxend_diag.py` | `test/kanten_engine/tmp_p9_boxend_diag.py` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_p9_gegenueberstellung.py` | `test/kanten_engine/tmp_p9_gegenueberstellung.py` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_param_sweep_report.txt` | `test/kanten_engine/tmp_param_sweep_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_payout_anatomy_report.txt` | `test/counter_engine/tmp_payout_anatomy_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_phasen_volumen_profil_symbol.py` | `test/silver_regime/tmp_phasen_volumen_profil_symbol.py` | `docs\setup_c_experiment.md` |
| `test/tmp_post_phase_verification.txt` | `test/counter_engine/tmp_post_phase_verification.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_rebound_report.txt` | `test/counter_engine/tmp_rebound_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_reclaim_live_frozen_runner.py` | `test/reclaim_live/tmp_reclaim_live_frozen_runner.py` | `docs\reclaim_historie_index.md` |
| `test/tmp_reclaim_live_l1.py` | `test/reclaim_live/tmp_reclaim_live_l1.py` | `docs\reclaim_historie_index.md` |
| `test/tmp_reclaim_snapshot_replay.py` | `test/reclaim_live/tmp_reclaim_snapshot_replay.py` | `docs\reclaim_historie_index.md`, `docs\reclaim_snapshot_spez.md` |
| `test/tmp_regime_freezed.txt` | `test/silver_regime/tmp_regime_freezed.txt` | `docs\setup_c_experiment.md` |
| `test/tmp_regime_oos_2024.txt` | `test/silver_regime/tmp_regime_oos_2024.txt` | `docs\setup_c_experiment.md` |
| `test/tmp_regime_oos_stress.txt` | `test/silver_regime/tmp_regime_oos_stress.txt` | `docs\setup_c_experiment.md` |
| `test/tmp_regime_sweep.txt` | `test/silver_regime/tmp_regime_sweep.txt` | `docs\setup_c_experiment.md` |
| `test/tmp_regime_validation.py` | `test/silver_regime/tmp_regime_validation.py` | `docs\setup_c_experiment.md`, `scripts\setup_c_profil.py` |
| `test/tmp_setup_c_1close.py` | `test/setup_c/tmp_setup_c_1close.py` | `docs\setup_c_experiment.md` |
| `test/tmp_setup_c_audit.py` | `test/setup_c/tmp_setup_c_audit.py` | `docs\session_checkpoint_setup_c_2026-09-04.md`, `docs\setup_c_experiment.md`, `scripts\setup_c_profil.py` |
| `test/tmp_setup_c_avwap_test.py` | `test/setup_c/tmp_setup_c_avwap_test.py` | `docs\setup_c_experiment.md` |
| `test/tmp_setup_c_schritt1_mfe_mae_verteilung.txt` | `test/setup_c/tmp_setup_c_schritt1_mfe_mae_verteilung.txt` | `docs\setup_c_experiment.md` |
| `test/tmp_setup_c_trailing.py` | `test/setup_c/tmp_setup_c_trailing.py` | `docs\setup_c_experiment.md` |
| `test/tmp_setup_c_whipsaw.py` | `test/setup_c/tmp_setup_c_whipsaw.py` | `docs\setup_c_experiment.md` |
| `test/tmp_setup_c_zeitexit.py` | `test/setup_c/tmp_setup_c_zeitexit.py` | `docs\setup_c_experiment.md` |
| `test/tmp_signature_asymmetry_report.txt` | `test/counter_engine/tmp_signature_asymmetry_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_stacking_audit.txt` | `test/kanten_engine/tmp_stacking_audit.txt` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_stresstest_bilanz.txt` | `test/counter_engine/tmp_stresstest_bilanz.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_tf_s1s2_report.txt` | `test/silver_regime/tmp_tf_s1s2_report.txt` | `docs\makro_swings_experiment.md` |
| `test/tmp_v3_genese_audit.py` | `test/kanten_engine/tmp_v3_genese_audit.py` | `docs\reclaim_kanten_engine_spez.md` |
| `test/tmp_v3_soll_kanten_audit.py` | `test/kanten_engine/tmp_v3_soll_kanten_audit.py` | `docs\session_checkpoint_kanten_engine_v3_2026-09-06.md` |
| `test/tmp_v3_straight_edge_audit.py` | `test/kanten_engine/tmp_v3_straight_edge_audit.py` | `docs\reclaim_kanten_engine_spez.md`, `docs\session_checkpoint_kanten_engine_v3_2026-09-08.md` |
| `test/tmp_v3_straight_edge_audit_AUG.txt` | `test/kanten_engine/tmp_v3_straight_edge_audit_AUG.txt` | `docs\session_checkpoint_kanten_engine_v3_2026-09-08.md` |
| `test/tmp_vola_range_audit.txt` | `test/counter_engine/tmp_vola_range_audit.txt` | `docs\makro_swings_experiment.md` |

---

## F3 - ausgeführte Korrekturen (nur unter `/reports`)

Die folgenden 6 Stellen in `reports/` wurden am 2026-09-10 korrigiert. Es wurde
**ausschliesslich der Skriptpfad in der Provenienz-Kopfzeile (Zeile 2)**
angepasst - keine Zahl, kein Messwert, keine weitere Zeile beruehrt:

| Datei (reports/) | Zeile | alt | neu |
|---|---|---|---|
| `setup_c/setup_c_avwap_AUG.txt` | 2 | `test/tmp_setup_c_avwap_test.py` | `test/setup_c/tmp_setup_c_avwap_test.py` |
| `setup_c/setup_c_pullback_AUG.txt` | 2 | `test/tmp_setup_c_pullback_test.py` | `test/setup_c/tmp_setup_c_pullback_test.py` |
| `setup_c/setup_c_rebound_AUG.txt` | 2 | `test/tmp_setup_c_rebound_test.py` | `test/setup_c/tmp_setup_c_rebound_test.py` |
| `setup_c/setup_c_swing_AUG.txt` | 2 | `test/tmp_setup_c_swing_reversal.py` | `test/setup_c/tmp_setup_c_swing_reversal.py` |
| `setup_c/setup_c_swing_S1.txt` | 2 | `test/tmp_setup_c_swing_reversal.py` | `test/setup_c/tmp_setup_c_swing_reversal.py` |
| `setup_c/setup_c_swing_S2.txt` | 2 | `test/tmp_setup_c_swing_reversal.py` | `test/setup_c/tmp_setup_c_swing_reversal.py` |

**Nicht korrigiert (bewusst):**

- alle `docs/`-Stellen der Tabelle oben (historische Experiment-Protokolle,
  Docs werden laut Arbeitsregel ignoriert),
- `reports/h2_phasenregime/CHECKPOINT_2026-09-09.md` und
  `H2_PHASENREGIME_ADAPTER_SPEZ.md`: **alle** dort genannten `test/`-Pfade
  zeigen weiterhin korrekt auf `test/`-Root (Hot-Set, Entscheidung F4),
  lediglich der zurueckgeholte `tmp_audit_kandidat_trace_out.txt` wurde
  wieder nach `test/` gelegt - die Referenz stimmt damit unveraendert.
