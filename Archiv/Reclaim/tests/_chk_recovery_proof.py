# -*- coding: utf-8 -*-
"""READ-ONLY Wiederherstellungs-Beweis (KORRIGIERT).

Lehre aus dem Reihenfolge-Befund: der Trade-Loop mutiert ``_SEEdgeH``
(``letzter_sweep_bar``/``letzter_signal_bar``/``cluster_hoch``/``cluster_tief``)
IN-PLACE auf dem geteilten Scan. Daher bekommt JEDER Trade-Lauf eine eigene
``copy.deepcopy(scan)``. Der H1/H2-Split erfolgt IMMER an ``box_end`` = 644
(2026-08-19, Kanon K6), auch fuer den VOLL-Lauf (1288).

Fragestellung (Handoff H20.49 §10): Stammt die AUG-SSoT ``14/+27.327383``
aus Baseline oder V020? Und reproduziert die Baseline den V0-nativ-Anker?

Modus A ausschliesslich (hook=None); Adapter NICHT importiert.
Motoren byte-identisch (SHA-Guards).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")


def _sha(p: Path) -> str:
    """SHA256 einer Datei (Guard gegen Fremdstand)."""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _lade(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _scan(B: Any, d: Any, cfg: Any, box: int) -> Dict[str, Any]:
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(box)
    return scan


def _lauf_baseline(B: Any, scan: Dict[str, Any], cfg: Any) -> List[Any]:
    tr, _ = B._se_trades(copy.deepcopy(scan), cfg)   # frische Kopie Pflicht
    return sorted(list(tr), key=lambda x: int(x.entry_bar))


def _lauf_v020(V: Any, scan: Dict[str, Any], cfg: Any, kcfg: Any) -> List[Any]:
    eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    tr, _ = eng._se_trades_v020(copy.deepcopy(scan), cfg)  # frische Kopie
    return sorted(list(tr), key=lambda x: int(x.entry_bar))


def _agg(tr: List[Any], split: int) -> Tuple[int, float, int, float, int, float]:
    """(n, SumR, H1n, H1R, H2n, H2R) mit Split an ``split``."""
    h1 = [float(t.r) for t in tr if int(t.entry_bar) < split]
    h2 = [float(t.r) for t in tr if int(t.entry_bar) >= split]
    return (len(tr), sum(float(t.r) for t in tr),
            len(h1), sum(h1), len(h2), sum(h2))


def main() -> None:
    assert _sha(ROOT / "test" / "tmp_kanten_engine_replay.py") \
        == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(ROOT / "test" / "tmp_kanten_engine_v020_replay.py") \
        == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ROOT / "backtest_lab" / "phasen_regime_adapter.py") \
        == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"
    R = _lade("run_lab_rp2", ROOT / "test" / "run_lab.py")
    B = R._load("basis_rp2", R.BASELINE_PFAD)
    V = R._load("v020_rp2", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    z: List[str] = []
    z.append("WIEDERHERSTELLUNGS-BEWEIS (korrigiert: frische deepcopy je Lauf)")
    z.append("Modus A (hook=None). Split IMMER bei box_end = 644.")
    z.append("")

    # ---------------- AUG -----------------
    d = R._lade_fenster(B, "2026-08-10", "2026-08-28")
    n = int(len(d))
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    box = int(np.searchsorted(ts, np.datetime64("2026-08-19")))
    z.append("=" * 82)
    z.append(f"A) AUG 2026-08-10 .. 2026-08-28 | n={n} | box_end={box}")
    z.append("=" * 82)
    sc_box = _scan(B, d, cfg, box)
    sc_voll = _scan(B, d, cfg, n)

    tb_box = _lauf_baseline(B, sc_box, cfg)
    tb_voll = _lauf_baseline(B, sc_voll, cfg)
    tv_box = _lauf_v020(V, sc_box, cfg, kcfg)
    tv_voll = _lauf_v020(V, sc_voll, cfg, kcfg)

    z.append(f"  {'Lauf':30s} {'n':>4s} {'SumR':>12s} "
             f"{'H1 n':>5s} {'H1 R':>12s} {'H2 n':>5s} {'H2 R':>12s}")
    for label, tr in (("Baseline  BOX(644)", tb_box),
                      ("V020-A    BOX(644)", tv_box),
                      ("Baseline  VOLL(1288)", tb_voll),
                      ("V020-A    VOLL(1288)", tv_voll)):
        nn, s, h1n, h1r, h2n, h2r = _agg(tr, box)
        z.append(f"  {label:30s} {nn:4d} {s:+12.6f} "
                 f"{h1n:5d} {h1r:+12.6f} {h2n:5d} {h2r:+12.6f}")
    z.append("")
    z.append("  Handoff-Soll:")
    z.append("    V0 (nativ, Referenz, = BASELINE) = 14/+42.450970 "
             "(H1 8/+38.919584, H2 6/+3.531386)")
    z.append("    AUG-Box-Kaltstart SSoT (= V020-A) = 14/+27.327383 "
             "(H1 14/+27.327383, H2 15/-3.937470, VOLL 29/+23.389914)")

    # ---------------- MAI/JUN/JUL -----------------
    z.append("")
    z.append("=" * 82)
    z.append("B) Vollmonate (je frische deepcopy) -- Fair-Vergleich")
    z.append("=" * 82)
    z.append(f"  {'Monat':6s} {'BL n':>5s} {'BL SumR':>13s} "
             f"{'V020 n':>7s} {'V020 SumR':>13s} {'n-Faktor':>9s}")
    for lab, start, ende in (("MAI", "2026-05-01", "2026-06-01"),
                             ("JUN", "2026-06-01", "2026-07-01"),
                             ("JUL", "2026-07-01", "2026-08-01")):
        dd = R._lade_fenster(B, start, ende)
        nn = int(len(dd))
        sc = _scan(B, dd, cfg, nn)
        tb = _lauf_baseline(B, sc, cfg)
        tv = _lauf_v020(V, sc, cfg, kcfg)
        z.append(f"  {lab:6s} {len(tb):5d} {sum(float(t.r) for t in tb):+13.6f} "
                 f"{len(tv):7d} {sum(float(t.r) for t in tv):+13.6f} "
                 f"{len(tv) / len(tb):9.2f}x")
    z.append("")
    z.append("  Handoff §5 U1 (KONTAMINIERT -- V020 zuerst, Baseline auf demselben")
    z.append("  Scan-Objekt): Baseline 12/15/5 bzw. V020 58/56/68.")
    z.append("  FAIR (je frische Kopie): siehe Tabelle oben.")

    out = ROOT / "test" / "_chk_recovery_proof_out.txt"
    out.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    for zl in z:
        print(zl)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
