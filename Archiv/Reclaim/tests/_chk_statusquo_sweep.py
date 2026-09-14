# -*- coding: utf-8 -*-
"""READ-ONLY Status-Quo-Sweep (H20.48 / Schritt 3): Morphing-Baseline.

Misst die AKTUELLE (nicht-stationaere) Engine ueber 4 autonome Monatsfenster
2026 x 4 `touch_band_pct`-Stufen. Kein Engine-Eingriff, keine DB-Mutation.
Der Sweep ist die Vorher-Baseline, die der Kantenbasis-Fix (Option a)
schlagen muss.

Fenster (Nutzerfreigabe, je Kaltstart ohne Warm-up, Ende exklusiv):
  MRZ 2026-03-02 .. 2026-03-27
  MAI 2026-05-04 .. 2026-05-29
  JUL 2026-07-06 .. 2026-07-31
  AUG 2026-08-03 .. 2026-08-28
Parameter-Achse: touch_band_pct in {0.10, 0.12, 0.14, 0.16}

Modus A (hook=None), Adapter NICHT importiert. Einzige Schreiboperation:
dieses Protokoll + die TSV.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

PROTOKOLL = ROOT / "test" / "_chk_statusquo_sweep_out.txt"
TSV = ROOT / "test" / "_chk_statusquo_sweep.tsv"

FENSTER: Tuple[Tuple[str, str, str], ...] = (
    ("MRZ", "2026-03-02", "2026-03-27"),
    ("MAI", "2026-05-04", "2026-05-29"),
    ("JUL", "2026-07-06", "2026-07-31"),
    ("AUG", "2026-08-03", "2026-08-28"),
)
BANDS: Tuple[float, ...] = (0.10, 0.12, 0.14, 0.16)


def _lade_run_lab() -> Any:
    """run_lab als Modul laden (Wiederverwendung der geprueften Helfer)."""
    p = ROOT / "test" / "run_lab.py"
    spec = importlib.util.spec_from_file_location("run_lab_sweep", p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules["run_lab_sweep"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _lauf(R: Any, B: Any, V: Any, cfg: Any, kcfg: Any, start: str, ende: str
         ) -> Dict[str, Any]:
    """Ein Fenster x Parameter: laden, scannen, Modus-A-Trades, aggregieren."""
    import copy
    import numpy as np

    d = R._lade_fenster(B, start, ende)
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    n = int(len(d))
    scan = R._scan(B, d, cfg) if hasattr(R, "_scan") else None
    if scan is None:
        original = B._lade_fenster
        B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
        try:
            scan = B._se_scan("LAB", cfg)
        finally:
            B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    trades, _st = eng._se_trades_v020(scan, cfg)
    trades = list(trades)
    rs = [float(x.r) for x in trades]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    pf = (sum(pos) / abs(sum(neg))) if neg else float("inf")
    return {
        "n": n, "edges": len(scan["edges"]), "seeds": len(scan["seeds"]),
        "r21": len(scan.get("r21_geloescht", [])),
        "tomb": len(scan.get("tombstones", [])),
        "war": len(B.WAR_AUSSEN_IDS),
        "n_tr": len(rs), "sum_r": float(sum(rs)),
        "win": (100.0 * len(pos) / len(rs)) if rs else 0.0,
        "pf": pf,
        "ts0": str(ts[0])[:10], "ts1": str(ts[-1])[:10],
    }


def main() -> None:
    import dataclasses

    t_ges = time.perf_counter()
    R = _lade_run_lab()
    B = R._load("basis_sweep", R.BASELINE_PFAD)
    V = R._load("v020_sweep", R.V020_PFAD)

    zeilen: List[str] = []
    zeilen.append("READ-ONLY STATUS-QUO-SWEEP (Morphing-Baseline, Modus A)")
    zeilen.append("Engine: basis = mean(alle Dochte) -- nicht stationaer "
                  "(H20.47)")
    zeilen.append("SHAs: Baseline 53f28e1b / V020 e79c5c29 / "
                  "Adapter 770eda2c (Adapter nicht importiert)")
    zeilen.append("Fenster: je Kaltstart (Warm-up = 0), Ende exklusiv; "
                  "box_end_bar = n (Vollauf)")
    zeilen.append("")

    rows: List[Dict[str, Any]] = []
    for lab, start, ende in FENSTER:
        for band in BANDS:
            cfg = dataclasses.replace(
                B.StraightEdgeHarnessKonfiguration(), touch_band_pct=band)
            kcfg = V.V020KantenKonfiguration()
            t0 = time.perf_counter()
            r = _lauf(R, B, V, cfg, kcfg, start, ende)
            r.update({"lab": lab, "start": start, "ende": ende, "band": band,
                      "t": time.perf_counter() - t0})
            rows.append(r)
            print(f"[{lab} band={band:.2f}] n={r['n']:5d} "
                  f"edges={r['edges']:4d} tr={r['n_tr']:3d} "
                  f"R={r['sum_r']:+10.6f} ({r['t']:.1f}s)", flush=True)

        sub = [x for x in rows if x["lab"] == lab]
        zeilen.append(f"--- {lab}: {start} .. {ende} (exkl.)  "
                      f"| n={sub[0]['n']} | erste {sub[0]['ts0']} letzte "
                      f"{sub[0]['ts1']} ---")
        zeilen.append(f"  {'band':>5s} {'edges':>5s} {'seeds':>5s} "
                      f"{'r21':>4s} {'tomb':>4s} {'warA':>4s} "
                      f"{'Trades':>6s} {'SumR':>11s} {'Win%':>6s} "
                      f"{'PF':>7s}")
        for x in sub:
            zeilen.append(
                f"  {x['band']:5.2f} {x['edges']:5d} {x['seeds']:5d} "
                f"{x['r21']:4d} {x['tomb']:4d} {x['war']:4d} "
                f"{x['n_tr']:6d} {x['sum_r']:+11.6f} {x['win']:6.2f} "
                f"{x['pf']:7.4f}")
        zeilen.append("")

    zeilen.append("===== MATRIX SumR (Zeile=Fenster, Spalte=band) =====")
    zeilen.append("  " + "".join(f"{b:>13.2f}" for b in BANDS))
    for lab, _s, _e in FENSTER:
        zl = f"{lab}  "
        for b in BANDS:
            x = next(x for x in rows if x["lab"] == lab and x["band"] == b)
            zl += f"{x['sum_r']:+13.6f}"
        zeilen.append(zl)

    zeilen.append("")
    zeilen.append("===== STREUUNG je Fenster (ueber bands) =====")
    for lab, _s, _e in FENSTER:
        vals = [x["sum_r"] for x in rows if x["lab"] == lab]
        trs = [x["n_tr"] for x in rows if x["lab"] == lab]
        zeilen.append(f"  {lab}: SumR min {min(vals):+.6f} max {max(vals):+.6f} "
                      f"Spanne {max(vals) - min(vals):.6f} | "
                      f"Trades {min(trs)}..{max(trs)}")

    zeilen.append("")
    zeilen.append(f"Laufzeit: {time.perf_counter() - t_ges:.1f}s")

    PROTOKOLL.write_text("\n".join(zeilen) + "\n", encoding="utf-8",
                         newline="\n")
    tsv = ["fenster\tstart\tende\tband\tn\tedges\tseeds\tr21\ttomb\twarA\t"
           "trades\tsum_r\twin_pct\tpf"]
    for x in rows:
        tsv.append(f"{x['lab']}\t{x['start']}\t{x['ende']}\t{x['band']:.2f}\t"
                   f"{x['n']}\t{x['edges']}\t{x['seeds']}\t{x['r21']}\t"
                   f"{x['tomb']}\t{x['war']}\t{x['n_tr']}\t"
                   f"{x['sum_r']:.6f}\t{x['win']:.2f}\t{x['pf']:.4f}")
    TSV.write_text("\n".join(tsv) + "\n", encoding="utf-8", newline="\n")

    for zl in zeilen:
        print(zl)
    print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)")
    print(f"TSV       -> {TSV}  ({TSV.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
