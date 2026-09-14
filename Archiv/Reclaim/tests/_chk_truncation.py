# -*- coding: utf-8 -*-
"""READ-ONLY Truncation-Probe v2 (H20.46): Zukunft vs. Historie isoliert.

Korrektur gegenueber v1: In v1 variierte ``box_end_bar`` mit dem Datenende
(T < 644), sodass die Trade-Schleife selbst wanderte. Hier wird ``box_end_bar``
JE EXPERIMENT FIXIERT und nur das geladene DATENENDE variiert.

Experiment A -- ZUKUNFT (Look-Ahead):
  Fuer festes BOX wird der Scan auf ``data[:T]`` gefahren (T >= BOX) und
  ``scan["box_end_bar"] = BOX`` erzwungen. Die Trade-Schleife
  ``range(2, BOX-3)`` ist damit identisch; nur die mitgeladenen Bars
  [BOX, T) aendern Kanten (R21/Cluster/kid). Differieren die Trades mit
  entry < BOX gegenueber T = 1288, so ist das reiner Zukunftseinfluss.

Experiment B -- HISTORIE (Start-Erweiterung):
  Vergleich AUG (Start 08-10) gegen [08-03..08-28] (Start 08-03, gleiches
  Ende). Beide Scans erhalten box_end fest = ihrer Box-Grenze; verglichen
  wird der gemeinsame H1-Bereich. Ergebnis zeigt, ob zusaetzliche
  VORGESCHICHTE das AUG-Ergebnis veraendert (kausal legitim, aber
  fensterabhaengig -- KEIN Look-Ahead).

Read-only: ``_lade_fenster`` wird nur in der Modul-Instanz ersetzt. Einzige
Schreiboperation: dieses Protokoll ``_chk_truncation_out.txt``.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
PROTOKOLL = ROOT / "test" / "_chk_truncation_out.txt"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

N_FULL = 1288
FENSTER = "AUG"
OFFSET_B = 460                      # [08-03 .. ] vs [08-10 ..]
BOX_A = (644, 800, 1000, 1200)
T_KAND = (644, 700, 800, 900, 1000, 1100, 1200, 1288)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class _Stub:
    """fd-freier stdout-Ersatz (Baseline haengt beim exec sys.stdout um)."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _load(name: str, p: Path) -> Any:
    real = sys.stdout
    try:
        sys.stdout = _Stub()  # type: ignore[assignment]
        spec = importlib.util.spec_from_loader(name, loader=None)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        mod.__file__ = str(p)
        sys.modules[name] = mod
        exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"),
             mod.__dict__)
    finally:
        sys.stdout = real
    return mod


def _tkey(x: Any) -> Tuple[int, str, int]:
    return (int(x.entry_bar), str(x.richtung), int(round(float(x.r) * 1e6)))


def _scan_box(B: Any, v020: Any, cfg: Any, kcfg: Any, df: Any, box: int
              ) -> Tuple[List[Any], Dict[str, Any]]:
    """Scan auf df mit erzwungenem box_end=box; Rueckgabe (Trades, Scan)."""
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=df: _d.copy())  # type: ignore
    try:
        scan = B._se_scan(FENSTER, cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan["box_end_bar"] = int(box)
    eng = v020.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    ss, _st = eng._se_trades_v020(copy.deepcopy(scan), cfg)
    return list(ss), scan


def main() -> None:
    zeilen: List[str] = []
    assert _sha(BASELINE_PFAD) == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(V020_PFAD) == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ADAPTER_PFAD) == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"
    zeilen.append("SHA-Guards OK: Baseline 53f28e1b / V020 e79c5c29 / "
                  "Adapter 770eda2c")

    B = _load("basis_tr2", BASELINE_PFAD)
    v020 = _load("v020_tr2", V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = v020.V020KantenKonfiguration()

    d_aug = B._lade_fenster(FENSTER)
    assert len(d_aug) == N_FULL, f"AUG n={len(d_aug)}"

    zeilen.append("")
    zeilen.append("===== EXPERIMENT A: ZUKUNFT (fixes BOX, variables "
                  "Datenende T) =====")
    zeilen.append("  Trades mit entry < BOX; Referenz ist T=1288.")
    any_future = False
    for BOX in BOX_A:
        ref, scan_ref = _scan_box(B, v020, cfg, kcfg,
                                  d_aug.iloc[:N_FULL], BOX)
        ref_h = {_tkey(x) for x in ref if int(x.entry_bar) < BOX}
        ref_n = len(ref_h)
        ref_r = float(sum(x.r for x in ref if int(x.entry_bar) < BOX))
        zeilen.append("")
        zeilen.append(f"  --- BOX={BOX} (Referenz T=1288: {ref_n} / "
                      f"{ref_r:+.6f}) ---")
        zeilen.append(f"    {'T':>5s} {'edges':>6s} {'seeds':>6s} "
                      f"{'r21log':>7s} {'tomb':>5s} {'warAus':>7s} "
                      f"{'n<BOX':>6s} {'R<BOX':>12s} {'dN':>3s} {'dR':>12s} "
                      f"{'diff':>5s}")
        for T in T_KAND:
            if T < BOX:
                continue
            tr, scan = _scan_box(B, v020, cfg, kcfg, d_aug.iloc[:T], BOX)
            sel = [x for x in tr if int(x.entry_bar) < BOX]
            s = {_tkey(x) for x in sel}
            n, r = len(sel), float(sum(x.r for x in sel))
            dN, dR = n - ref_n, r - ref_r
            if s != ref_h:
                any_future = True
            zeilen.append(
                f"    {T:5d} {len(scan['edges']):6d} {len(scan['seeds']):6d} "
                f"{len(scan.get('r21_geloescht', [])):7d} "
                f"{len(scan.get('tombstones', [])):5d} "
                f"{len(B.WAR_AUSSEN_IDS):7d} {n:6d} {r:+12.6f} {dN:+3d} "
                f"{dR:+12.6f} {len(s ^ ref_h):5d}")
            if s != ref_h:
                for tk in sorted(ref_h - s)[:4]:
                    zeilen.append(f"        FEHLT entry={tk[0]} {tk[1]:5s} "
                                  f"r={tk[2] / 1e6:+.6f}")
                for tk in sorted(s - ref_h)[:4]:
                    zeilen.append(f"        DAZU  entry={tk[0]} {tk[1]:5s} "
                                  f"r={tk[2] / 1e6:+.6f}")

    # --- Experiment B: Start-Erweiterung -----------------------------------
    zeilen.append("")
    zeilen.append("===== EXPERIMENT B: HISTORIE (Start 08-03 vs 08-10, "
                  "gleiches Ende 08-28) =====")
    d_ext = B._lade_fenster("S1")  # S1 = 2026-02-05..2026-08-28 (enthaelt AUG)
    ts_ext = d_ext["ts"].to_numpy().astype("datetime64[ns]")
    ts_aug = d_aug["ts"].to_numpy().astype("datetime64[ns]")
    pos = int(np.searchsorted(ts_ext, ts_aug[0]))
    assert bool(np.array_equal(ts_ext[pos:pos + N_FULL], ts_aug)), \
        "AUG nicht als Segment in S1 gefunden"
    zeilen.append(f"  AUG liegt in S1 bei Offset {pos}; "
                  f"S1[..pos+N] == AUG per np.array_equal bestaetigt.")
    # S1-Scan mit box_end = pos + 644 (Kalendergrenze 2026-08-19)
    #
    # Hinweis: S1 enthaelt sehr viel Vorgeschichte (ab 2026-02-05).
    tr_aug, scan_aug = _scan_box(B, v020, cfg, kcfg, d_aug, 644)
    aug_h = {_tkey(x) for x in tr_aug if int(x.entry_bar) < 644}
    tr_s1, scan_s1 = _scan_box(B, v020, cfg, kcfg, d_ext, pos + 644)
    s1_h = {(int(x.entry_bar) - pos, str(x.richtung),
             int(round(float(x.r) * 1e6))) for x in tr_s1
            if pos <= int(x.entry_bar) < pos + 644}
    zeilen.append(f"  AUG (Start 08-10): {len(aug_h)} H1-Trades")
    zeilen.append(f"  S1  (Start 02-05): {len(s1_h)} H1-Trades im "
                  f"AUG-Segment")
    zeilen.append(f"  Set-Differenz: {len(aug_h ^ s1_h)}  "
                  f"(nur-AUG {len(aug_h - s1_h)}, nur-S1 {len(s1_h - aug_h)})")
    for tk in sorted(aug_h - s1_h)[:6]:
        zeilen.append(f"      nur-AUG entry={tk[0]} {tk[1]:5s} "
                      f"r={tk[2] / 1e6:+.6f}")
    for tk in sorted(s1_h - aug_h)[:6]:
        zeilen.append(f"      nur-S1  entry={tk[0]} {tk[1]:5s} "
                      f"r={tk[2] / 1e6:+.6f}")

    zeilen.append("")
    zeilen.append("===== VERDIKT =====")
    zeilen.append(f"  A) Zukunftseinfluss auf abgeschlossene Trades: "
                  f"{'JA (Look-Ahead)' if any_future else 'NEIN'}.")
    zeilen.append(f"  B) Historieneinfluss (frueherer Start): "
                  f"{'JA' if aug_h != s1_h else 'NEIN'} "
                  f"(kausal legitim, aber fensterabhaengig).")

    PROTOKOLL.write_text("\n".join(zeilen) + "\n", encoding="utf-8",
                         newline="\n")
    for zl in zeilen:
        print(zl)
    print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
