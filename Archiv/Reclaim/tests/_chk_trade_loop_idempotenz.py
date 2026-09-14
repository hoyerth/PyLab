# -*- coding: utf-8 -*-
"""READ-ONLY Nachweis: der Trade-Loop ist nicht idempotent (Scan-Mutation).

Befund (H20.49-Folge): ``_se_trades``/``_se_trades_v020`` schreiben IN-PLACE
auf die ``_SEEdgeH``-Objekte des geteilten Scans:

    kd.letzter_signal_bar = k
    kd.letzter_sweep_bar  = k          # -> F3-Filter (L2646) blockt 2. Lauf
    kd.cluster_hoch / kd.cluster_tief  = ...

Folgen
------
1. Zweimaliger Lauf auf DEMSELBEN ``scan``-Objekt liefert andere Zahlen
   (F3 sperrt Wiedereintritte, weil ``letzter_sweep_bar`` vorgerueckt ist).
2. Zwei Motoren nacheinander auf demselben ``scan`` kontaminieren sich
   gegenseitig (z. B. Baseline nach V020).
3. Gueltig sind nur Laeufe auf einer FRISCHEN ``copy.deepcopy(scan)``.

Dieses Skript belegt (a) die Nicht-Idempotenz, (b) die betroffenen Felder und
(c) die Kontamination der Handoff-§5-U1-Baseline. Modus A (hook=None),
Adapter NICHT importiert, Motoren byte-identisch (SHA-Guards).
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

AUS = ROOT / "test" / "_chk_trade_loop_idempotenz_out.txt"


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


def _scan(B: Any, d: Any, cfg: Any) -> Dict[str, Any]:
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        return B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore


def _felder(scan: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for e in list(scan["edges"]) + list(scan["seeds"]):
        out[int(e.kid)] = {f.name: getattr(e, f.name)
                           for f in dataclasses.fields(e)}
    return out


def _run_baseline(B: Any, scan: Dict[str, Any], cfg: Any) -> Tuple[int, float]:
    tr, _ = B._se_trades(scan, cfg)
    tr = list(tr)
    return len(tr), sum(float(x.r) for x in tr)


def _run_v020(V: Any, scan: Dict[str, Any], cfg: Any, kcfg: Any
              ) -> Tuple[int, float]:
    eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    tr, _ = eng._se_trades_v020(scan, cfg)
    tr = list(tr)
    return len(tr), sum(float(x.r) for x in tr)


def main() -> None:
    assert _sha(ROOT / "test" / "tmp_kanten_engine_replay.py") \
        == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(ROOT / "test" / "tmp_kanten_engine_v020_replay.py") \
        == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ROOT / "backtest_lab" / "phasen_regime_adapter.py") \
        == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"

    R = _lade("run_lab_fl", ROOT / "test" / "run_lab.py")
    B = R._load("basis_fl", R.BASELINE_PFAD)
    V = R._load("v020_fl", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    d = R._lade_fenster(B, "2026-05-01", "2026-06-01")
    scan = _scan(B, d, cfg)
    scan["box_end_bar"] = int(len(d))

    z: List[str] = []
    z.append("TRADE-LOOP IDEMPOTENZ-NACHWEIS (read-only, MAI-Vollmonat)")
    z.append("SHA-Guards OK: Baseline 53f28e1b / V020 e79c5c29 / "
             "Adapter 770eda2c")
    z.append("")

    # --- A) Feldmutation -----------------------------------------------------
    for name, ist_v020 in (("BASELINE", False), ("V020", True)):
        sc = copy.deepcopy(scan)
        f0 = _felder(sc)
        if ist_v020:
            r1 = _run_v020(V, sc, cfg, kcfg)
            r2 = _run_v020(V, sc, cfg, kcfg)
        else:
            r1 = _run_baseline(B, sc, cfg)
            r2 = _run_baseline(B, sc, cfg)
        f1 = _felder(sc)
        geaendert: Dict[str, List[str]] = {}
        for kid in f0:
            for fld in f0[kid]:
                a, b = f0[kid][fld], f1[kid][fld]
                if a != b or type(a) is not type(b):
                    geaendert.setdefault(fld, []).append(
                        f"K{kid}: {a!r} -> {b!r}")
        z.append(f"### {name}: 1.Lauf n={r1[0]} R={r1[1]:+.6f} | "
                 f"2.Lauf n={r2[0]} R={r2[1]:+.6f}  "
                 f"-> {'NICHT idempotent' if r1 != r2 else 'idempotent'}")
        if not geaendert:
            z.append("  keine Feldaenderung")
        for fld, xs in sorted(geaendert.items()):
            z.append(f"  Feld '{fld}': {len(xs)} Kanten mutiert")
            for x in xs[:4]:
                z.append(f"      {x}")
        z.append("")

    # --- B) Reihenfolge-Kontamination ---------------------------------------
    z.append("### Reihenfolge-Kontamination (gleiches scan-Objekt)")
    sc = copy.deepcopy(scan)
    v1 = _run_v020(V, sc, cfg, kcfg)
    b_after_v = _run_baseline(B, sc, cfg)
    z.append(f"  V020 zuerst        : V020={v1[0]}/{v1[1]:+.6f}")
    z.append(f"  Baseline danach    : BL  ={b_after_v[0]}/{b_after_v[1]:+.6f}")
    sc2 = copy.deepcopy(scan)
    b1 = _run_baseline(B, sc2, cfg)
    v_after_b = _run_v020(V, sc2, cfg, kcfg)
    z.append(f"  Baseline zuerst    : BL  ={b1[0]}/{b1[1]:+.6f}")
    z.append(f"  V020 danach        : V020={v_after_b[0]}/{v_after_b[1]:+.6f}")
    sc3 = copy.deepcopy(scan)
    b_frisch = _run_baseline(B, sc3, cfg)
    sc4 = copy.deepcopy(scan)
    v_frisch = _run_v020(V, sc4, cfg, kcfg)
    z.append(f"  FAIR (je frische Kopie): BL={b_frisch[0]}/{b_frisch[1]:+.6f}"
             f" | V020={v_frisch[0]}/{v_frisch[1]:+.6f}")
    z.append("")
    z.append("  Handoff §5 U1 nennt fuer MAI Baseline 12/-5.959839 -- das ist")
    z.append("  die Baseline NACH V020 auf demselben Objekt (kontaminiert).")

    AUS.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    for zl in z:
        print(zl)
    print(f"\n-> {AUS}")


if __name__ == "__main__":
    main()
