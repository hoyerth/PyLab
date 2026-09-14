# test/_aufraeumen_plan.py
"""Trockenlauf: klassifiziert alle Dateien im Ordner `test` fuer die Aufraeumaktion.

Reine Analyse - es wird NICHTS verschoben oder geloescht. Ergebnis:
  test/_aufraeumen_plan.tsv   (Datei, Zielordner)

Bildung von Bausteinen: Dateien werden ueber ihren "Stamm" gruppiert
(``X.py`` / ``X.txt`` / ``X_out.txt`` / ``X.log`` gehoeren zusammen) und
gemeinsam einem Ziel zugeordnet - Protokolle werden nie vom Skript getrennt.

Ziel-Buckets:
  <root>            -> bleibt in test/ (aktives Thema H2-Phasenregime / Engine)
  setup_c           -> Setup-C-Zweig
  counter_engine    -> Setup-A / Counter-Engine / Makro-Swings
  silver_regime     -> Regime-Modell, Silver-Sanity, S1/S2-Jahreslaeufe
  reclaim_live      -> Reclaim-Live / Snapshot / AVWAP
  kanten_engine     -> abgeschlossene Kanten-Engine-Teiluntersuchungen
  trash             -> Wegwerf-Artefakte (Extraktionen, angewandte Patches, Debugs)
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

TEST = Path(__file__).resolve().parent

# --------------------------------------------------------------------------- #
# 1) Schutzliste: aktives Thema (reports/h2_phasenregime + backtest_lab) -----
# --------------------------------------------------------------------------- #
KEEP_ROOT = {
    "tmp_kanten_engine_replay.py",
    "tmp_png_aug_sichttest.py", "tmp_png_aug_sichttest_out.txt",
    "tmp_test_phasen_regime_adapter.py", "tmp_test_phasen_regime_adapter_out.txt",
    "tmp_hook_semantik_check.py", "tmp_hook_semantik_check_out.txt",
    "tmp_dryrun_p12.py", "tmp_dryrun_p12_out.txt",
    "stats_kanten_engine_replay.txt",
    "kanten_liste_AUG_mC.txt",
    "tmp_v3_straight_edge_harness_AUG.txt",
    "SESSION_HANDOFF.md", "SESSION_START_2026-09-04.md",
    "tmp_png_h1h2_full.py", "tmp_png_h1h2_full_out.txt",
    "tmp_png_h2_zoom.py", "tmp_png_vollzeitraum.py",
    "tmp_h1_entry_ausfuehrung2.py", "tmp_h1_entry_ausfuehrung2_out.txt",
    "tmp_h1_entry_ausfuehrung3.py", "tmp_h1_entry_ausfuehrung3_out.txt",
    "tmp_h1_sl_seitenlage.py", "tmp_h1_sl_seitenlage_out.txt",
    "tmp_se_run_out.txt",
}
AUG_SICHT_PNG = re.compile(r"^aug_sichttest_\d\d_.*\.png$")
AUG_ENGINE_PNG = re.compile(r"^kanten_engine_.*AUG.*\.png$")

# --------------------------------------------------------------------------- #
# 2) Trash-Regeln (Wegwerf-Artefakte), angewendet auf den Baustein-Namen -----
# --------------------------------------------------------------------------- #
TRASH = [
    re.compile(r"^_"),                                    # _extract_*, _commitmsg*
    re.compile(r"^tmp_commit_msg_"),
    re.compile(r"^tmp_doku_|^tmp_doc_patch"),
    re.compile(r"^tmp_patch_"),                           # angewandte Patches
    re.compile(r"^tmp_se_debug\d*$"),
    re.compile(r"^tmp_se_run_err$"),
    re.compile(r"^tmp_q12_readonly_analyse\d*$"),
    re.compile(r"^tmp_diag_(101|1808b?)$"),
    re.compile(r"^tmp_kanten_engine_replay_pre_p\d+.*$"),
    re.compile(r"^reclaim_kanten_engine_spez_pre_.*\.py\.bak$"),
    re.compile(r"^tmp_backup_"),
    re.compile(r"^tmp_param_reihe_S1S2\.(err|log)$"),
    re.compile(r"^__pycache__$"),
    re.compile(r"^tmp_ueberstand_richtig_out$"),
    # abgeschlossene Kanten-Engine-Iterationen (Einmal-Diagnosen)
    re.compile(r"^tmp_h1_entry_(?!ausfuehrung2$|ausfuehrung3$)"),
    re.compile(r"^tmp_h1_gegenkante\d*$"),
    re.compile(r"^tmp_h1_zyklus_ref\d*$"),
    re.compile(r"^tmp_diag_(?!kanten_delta$)"),
    re.compile(r"^tmp_tz_impact\d*$"),
    re.compile(r"^tmp_ts_diag$|^tmp_ts_konsumenten$"),
    re.compile(r"^tmp_rohzeit_bars$|^tmp_zeit_referenz$"),
    re.compile(r"^tmp_r18_timeout$|^tmp_r21_final$"),
    re.compile(r"^tmp_param_reihe$|^tmp_param_pfad_245$|^tmp_param_schwelle_fein$"),
    re.compile(r"^tmp_band_"),
    re.compile(r"^tmp_kanten_hierarchie_"),
    re.compile(r"^tmp_forensik_k20$"),
    re.compile(r"^tmp_verify_p11$|^tmp_p10_hashes$|^tmp_gegenprobe_p11"),
    re.compile(r"^tmp_grep_const$|^tmp_faenger$"),
    re.compile(r"^tmp_anker_check$|^tmp_anker_teil6$"),
    re.compile(r"^tmp_dryrun2b_debug$"),
    re.compile(r"^tmp_v3_se_harness_AUG_pre_p6$"),
    re.compile(r"^tmp_patch_b23"),
]

# --------------------------------------------------------------------------- #
# 3) Themen-Regeln (erste Uebereinstimmung gewinnt) --------------------------
# --------------------------------------------------------------------------- #
TOPIC: list[tuple[str, re.Pattern[str]]] = [
    ("setup_c", re.compile(
        r"^tmp_setup_c_|^setup_c_|^stats_counter_")),
    ("counter_engine", re.compile(
        r"^tmp_counter_engine_|^tmp_check_spez_v2|^replay_modusA_matrix"
        r"|^tmp_makro|^tmp_baseline_loss_replay|^tmp_anchor_audit"
        r"|^tmp_init_phase_audit|^tmp_orphaned_turn|^tmp_zyklus_obduktion"
        r"|^tmp_stresstest_bilanz|^tmp_struktur_vorabcheck"
        r"|^tmp_post_phase_verification|^tmp_phasen_alter_schritt1"
        r"|^tmp_serien_regime_|^tmp_vola_range_audit|^tmp_capitulation_check"
        r"|^tmp_payout_anatomy|^tmp_signature_asymmetry|^tmp_drift_dichte"
        r"|^tmp_dwell_time|^tmp_edge_drift|^tmp_imbalance|^tmp_alpha_landkarte"
        r"|^tmp_consecutive_loss_audit|^tmp_rebound_report|^_rebound_verify"
        r"|^tmp_sanity_silver|^tmp_h1_aug_sanity_report|^tmp_m5_aug_")),
    ("silver_regime", re.compile(
        r"^tmp_regime_|^regime_|^tmp_test_regime|^tmp_sanity_klassifikation"
        r"|^tmp_stufe5_db_scan|^tmp_inspect_freezed|^tmp_diag_regime"
        r"|^tmp_S1_|^tmp_S2_|^tmp_bruch_matrix|^tmp_composite_s1"
        r"|^tmp_tf_s1s2|^tmp_brent|^stats_trades_|^phasen_volumen_profil"
        r"|^tmp_phasen_volumen_profil|^tmp_.*_economic_backtest"
        r"|^tmp_.*_leverage_backtest|^tmp_monats_regime_kontrast"
        r"|^tmp_intermediate_tf")),
    ("reclaim_live", re.compile(
        r"^tmp_reclaim_|^tmp_anchored_vwap|^tmp_check_reclaim|^stats_reclaim_")),
    ("kanten_engine", re.compile(r"^tmp_|^kanten_|^stats_kanten_")),
]


def baustein(name: str) -> str:
    """Stammname ohne Protokoll-Endung (``X_out.txt`` -> ``X``)."""
    stem = Path(name).stem
    if stem.endswith("_out"):
        stem = stem[:-4]
    return stem


def klassifiziere(name: str, stamm: str) -> str:
    """Liefert den Ziel-Bucket fuer einen Dateinamen."""
    if name.endswith(".pyc"):
        return "trash"
    if name in KEEP_ROOT or AUG_SICHT_PNG.match(name) or AUG_ENGINE_PNG.match(name):
        return "<root>"
    for rx in TRASH:
        if rx.search(name) or rx.search(stamm):
            return "trash"
    for thema, rx in TOPIC:
        if rx.search(stamm):
            return thema
    return "<root>"


def main() -> None:
    dateien = sorted(p.name for p in TEST.iterdir() if p.is_file())
    zuordnung = {n: klassifiziere(n, baustein(n)) for n in dateien}
    (TEST / "_aufraeumen_plan.tsv").write_text(
        "\n".join(f"{n}\t{z}" for n, z in zuordnung.items()) + "\n",
        encoding="utf-8")

    c = Counter(zuordnung.values())
    print(f"Dateien im test/-Root: {len(dateien)}")
    for bucket, n in c.most_common():
        print(f"  {bucket:16s} {n:4d}")
    print("\n--- bleibt in test/ (<root>) ---")
    for n, z in zuordnung.items():
        if z == "<root>":
            print("  " + n)


if __name__ == "__main__":
    main()
