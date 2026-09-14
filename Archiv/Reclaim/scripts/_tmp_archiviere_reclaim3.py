"""Reclaim-Archivierung Phase 3: Setup-B-Restbestand aus test/archiv/ einsortieren.

Regel (Weisung 2026-09-14):
  * Setup B (Monolith ``scripts/phasen_volumen_profil.py`` bzw. dessen
    ``reclaim_signals``/``MIN_RECLAIM``/``find_reclaim``-Funktionen) gehoert
    zum Reclaim-Thema -> Archiv/Reclaim.
  * Dubletten werden geloescht.
  * Ohne Setup-B-Bezug -> Themeninsel (test/silver_regime/, test/).

Trockenlauf ist der Default; Ausfuehrung mit ``--scharf``.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUELLE = ROOT / "test" / "archiv"
ZIEL = ROOT / "Archiv" / "Reclaim" / "tests"
SCHARF = "--scharf" in sys.argv

SETUP_B = [
    "test_diag_3eck_v6.py",
    "test_diag_3eck_v6_chart.py",
    "test_diag_3eck_v7_vmove.py",
    "test_diag_box_persistenz.py",
    "test_diag_volumen_zone.py",
    "test_kausal_box_reife.py",
    "test_sweep_cap.py",
    "test_sweep_kausal_reopt.py",
    "test_validate_2025_kausal.py",
    "tmp_anchor_audit.py",
    "tmp_baseline_loss_replay.py",
    "tmp_diag_check_0700.py",
    "tmp_diag_p7p8.py",
    "tmp_diag_sl_kante.py",
    "tmp_diag_sl_kante_rel.py",
    "tmp_diag_struktur_regel.py",
    "tmp_diag_trade_p7.py",
    "tmp_export_s1_s2_csv.py",
    "tmp_gen_S2_monatsauswertung.py",
    "tmp_gen_S2_wirtschaft.py",
    "tmp_init_phase_audit.py",
    "tmp_init_verdichtung.py",
    "tmp_pb_def_vergleich.py",
    "tmp_phasen_volumen_profil_v2.py",
    "tmp_pivot_vol_probe.py",
    "tmp_S1_economic_backtest.py",
    "tmp_S1_leverage_backtest.py",
    "tmp_S1_monatsauswertung.py",
    "tmp_S2_economic_backtest.py",
    "tmp_S2_leverage_backtest.py",
    "tmp_S2_monatsauswertung.py",
    "tmp_scan_funcs.py",
    "tmp_stresstest_bilanz.py",
]

V019_ALT = ["phasen_regime_adapter.py", "SESSION_HANDOFF.md"]

DUBLETTE = ["H2_PHASENREGIME_ADAPTER_SPEZ.md"]

SILVER = [
    "tmp_dd_episode_analyse.py",
    "tmp_monats_regime_kontrast.py",
    "tmp_orphaned_turn_ph7.py",
    "tmp_phasen_alter_schritt1.py",
    "tmp_post_phase_audit.py",
    "tmp_serien_regime_fenster.py",
    "tmp_serien_regime_inventur.py",
    "tmp_struktur_vorabcheck.py",
    "tmp_zyklus_obduktion.py",
    "silver_m15_ohlc_2025-01-01_2025-12-01.csv",
    "silver_m15_ohlc_2026-02-05_2026-08-28.csv",
    "silver_m15_ohlc_2026-08-10_2026-08-28.csv",
]

INFRA = ["tmp_db_inspektion.py", "tmp_obd_sonde.py"]

bewegt: list[tuple[str, str, str, int]] = []
geloescht: list[tuple[str, str, int]] = []
fehler: list[str] = []
log: list[str] = []


def rel(p: Path) -> str:
    """Pfad relativ zum Projektwurzelverzeichnis (POSIX)."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def sha256(p: Path) -> str:
    """SHA256-Hexdigest."""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def schaffe(dateien: list[str], zielordner: Path, etikett: str) -> None:
    """Verschiebt eine Dateiliste in den Zielordner."""
    treffer = 0
    for name in dateien:
        src = QUELLE / name
        if not src.is_file():
            fehler.append(f"QUELLE FEHLT : {rel(src)}")
            continue
        dst = zielordner / name
        if dst.exists():
            fehler.append(f"KOLLISION    : {rel(dst)}")
            continue
        if SCHARF:
            dst.parent.mkdir(parents=True, exist_ok=True)
            digest, groesse = sha256(src), src.stat().st_size
            shutil.move(str(src), str(dst))
        else:
            digest, groesse = "", -1
        bewegt.append((rel(src), rel(dst), digest, groesse))
        treffer += 1
    log.append(f"{etikett:<26} {treffer:>3} Dateien -> {rel(zielordner)}")


def loesche(name: str, grund: str) -> None:
    """Loescht eine Datei (Dublette)."""
    src = QUELLE / name
    if not src.is_file():
        fehler.append(f"QUELLE FEHLT : {rel(src)}")
        return
    digest, groesse = sha256(src), src.stat().st_size
    if SCHARF:
        src.unlink()
    geloescht.append((rel(src), digest, groesse))
    log.append(f"{'DUBLETTE GELOESCHT':<26} {rel(src)}  ({grund})")


def main() -> int:
    """Fuehrt die Einsortierung aus."""
    log.append("TROCKENLAUF" if not SCHARF else "SCHARF")
    log.append(f"Quelle: {rel(QUELLE)}")

    schaffe(SETUP_B, ZIEL / "setup_b", "Setup B -> Reclaim")
    schaffe(V019_ALT, ZIEL / "v019_aug_staging", "Altstand -> v019_staging")
    schaffe(SILVER, ROOT / "test" / "silver_regime", "Themeninsel Silver")
    schaffe(INFRA, ROOT / "test", "Infrastruktur -> test/")
    loesche(DUBLETTE[0], "hash-identisch mit reports/h2_phasenregime/")

    rest = sorted(p.name for p in QUELLE.iterdir() if p.is_file()) if QUELLE.exists() else []
    log.append(f"Rest in test/archiv/: {len(rest)} - {', '.join(rest) if rest else '(leer)'}")

    if SCHARF and QUELLE.exists() and not rest:
        QUELLE.rmdir()
        log.append("test/archiv/ (leer) entfernt")

    if SCHARF:
        mf = ZIEL / "setup_b" / "MANIFEST.sha256"
        zeilen = ["# SHA256  GROESSE  PFAD  URSPRUNG", ""]
        for f in sorted((ZIEL / "setup_b").rglob("*")):
            if f.is_file() and f.name != "MANIFEST.sha256":
                ursprung = next((a for n, a, _, _ in bewegt if n.endswith("/" + f.name)), "-")
                zeilen.append(f"{sha256(f)}  {f.stat().st_size}  {rel(f)}  {ursprung}")
        mf.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        log.append(f"Manifest Setup B: {len(zeilen) - 2} Eintraege -> {rel(mf)}")

    log.append(f"bewegt: {len(bewegt)}   geloescht: {len(geloescht)}   Fehler: {len(fehler)}")
    for f in fehler:
        log.append(f"  {f}")
    text = "\n".join(log)
    print(text)
    (ROOT / "test" / "_tmp_archiviere_reclaim3_out.txt").write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
