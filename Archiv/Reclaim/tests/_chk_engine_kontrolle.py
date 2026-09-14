# -*- coding: utf-8 -*-
"""READ-ONLY Kontroll- und Ursachensonde MAI/JUN/JUL (Fast-Modus, keine Fixes).

Abschnitte
----------
A) 20.05.2026: Richtungsumfeld (welche Seite wurde gesweept, welche Kanten
   existierten, warum wurde eine LONG statt SHORT genommen?).
B) Richtungs-Audit je Monat: SHORT<->OBEN / LONG<->UNTEN, Lage von
   ``entry``/``sweep``/``basis``, Anteil LONG/SHORT.
C) Baseline ``_se_trades`` vs. V020 ``_se_trades_v020`` (ist der Fehler
   V020-spezifisch oder in der arretierten Baseline angelegt?).
D) Kontrolle A -- Risiko-Klammer: effektives R = R * risk/max(risk, floor)
   mit floor in USD und floor = k * ATR(14,M15).
E) Kontrolle B -- ENDE-Bereinigung: Haelften mit ``grund == "ENDE"`` auf 0.
F) ATR(14)-Statistik je Monat (Bezugsgroesse fuer die Klammer).

Read-only: DB nur lesend, Motoren/Adapter/Handoff byte-identisch.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

PROTOKOLL = ROOT / "test" / "_chk_engine_kontrolle_out.txt"

MONATE = (("MAI", "2026-05-01", "2026-06-01"),
          ("JUN", "2026-06-01", "2026-07-01"),
          ("JUL", "2026-07-01", "2026-08-01"))
TAG_2005 = "2026-05-20"


def _lade(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _fenster(B: Any, start: str, ende: str) -> Any:
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _scan(B: Any, d: Any, cfg: Any, n: int) -> Dict[str, Any]:
    import copy
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    return scan


def _atr14(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray) -> np.ndarray:
    """Wilder-ATR(14) auf M15 (True Range, rekursiv, kausal)."""
    n = len(cl)
    tr = np.empty(n, dtype=float)
    tr[0] = hi[0] - lo[0]
    for i in range(1, n):
        tr[i] = max(hi[i] - lo[i], abs(hi[i] - cl[i - 1]),
                    abs(lo[i] - cl[i - 1]))
    atr = np.full(n, np.nan, dtype=float)
    if n <= 14:
        return atr
    atr[14] = float(np.mean(tr[1:15]))
    for i in range(15, n):
        atr[i] = (atr[i - 1] * 13.0 + tr[i]) / 14.0
    return atr


def _kanten_bei(alle: List[Any], k: int, seite: str
                ) -> List[Tuple[int, float, bool, int]]:
    """(kid, basis_bei(k), prim_anker, touch_conf) existierender Kanten."""
    out = []
    for e in alle:
        if str(e.seite) != seite or int(e.erster_pivot_bar) + 2 > k + 1:
            continue
        out.append((int(e.kid), float(e.basis_bei(k)),
                    bool(e.ist_prim_anker), int(e.touch_conf(k))))
    return sorted(out, key=lambda x: x[1])


def main() -> None:
    R = _lade("run_lab_kt", ROOT / "test" / "run_lab.py")
    B = R._load("basis_kt", R.BASELINE_PFAD)
    V = R._load("v020_kt", R.V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    z: List[str] = []
    z.append("KONTROLL- UND URSACHENSONDE MAI/JUN/JUL (read-only, keine Fixes)")
    z.append("")

    daten: Dict[str, Dict[str, Any]] = {}
    for lab, start, ende in MONATE:
        d = _fenster(B, start, ende)
        n = int(len(d))
        scan = _scan(B, d, cfg, n)
        eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
        tr_v, st_v = eng._se_trades_v020(scan, cfg)
        tr_v = sorted(list(tr_v), key=lambda x: int(x.entry_bar))
        tr_b, st_b = B._se_trades(scan, cfg)
        tr_b = sorted(list(tr_b), key=lambda x: int(x.entry_bar))
        atr = _atr14(d["high"].to_numpy(dtype=float),
                     d["low"].to_numpy(dtype=float),
                     d["close"].to_numpy(dtype=float))
        daten[lab] = {"d": d, "n": n, "scan": scan, "v": tr_v, "b": tr_b,
                      "atr": atr, "st_v": st_v, "st_b": st_b}

    # ==================================================== A) 20.05. Richtung
    d = daten["MAI"]["d"]
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    n = daten["MAI"]["n"]
    i20 = int(np.searchsorted(ts, np.datetime64(TAG_2005)))
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    alle = list(daten["MAI"]["scan"]["edges"]) + \
        list(daten["MAI"]["scan"]["seeds"])
    z.append("========== A) RICHTUNGSUMFELD 20.05.2026 (MAI) ==========")
    z.append(f"Bar fuer {TAG_2005} (erster Bar des Tages) = {i20} | n={n}")
    z.append(f"  {'bar':>5s} {'ts':19s} {'open':>8s} {'high':>8s} "
             f"{'low':>8s} {'close':>8s}   Richtungssignal")
    for k in range(max(2, i20 - 4), min(n, i20 + 100)):
        r = []
        if k - 1 >= 0 and min(op[k - 1], cl[k - 1]) > 0:
            pass
        r.append("SHORT-sweep" if hi[k] > hi[k - 1] else "")
        r.append("LONG-sweep" if lo[k] < lo[k - 1] else "")
        z.append(f"  {k:5d} {str(ts[k])[:19]:19s} {op[k]:8.4f} {hi[k]:8.4f} "
                 f"{lo[k]:8.4f} {cl[k]:8.4f}   {' '.join(x for x in r if x)}")
    z.append("")
    for k in (i20 - 1, i20, i20 + 1, i20 + 2):
        ob = _kanten_bei(alle, k, "OBEN")
        un = _kanten_bei(alle, k, "UNTEN")
        z.append(f"  bar {k:5d}  hi={hi[k]:.4f} lo={lo[k]:.4f} "
                 f"cl={cl[k]:.4f}")
        z.append(f"      OBEN-Kanten (kid, basis_bei, prim, touchn): "
                 + (", ".join(f"K{a}({b:.4f},{'P' if c else '-'},t{tc})"
                              for a, b, c, tc in ob) or "keine"))
        z.append(f"      UNTEN-Kanten: "
                 + (", ".join(f"K{a}({b:.4f},{'P' if c else '-'},t{tc})"
                              for a, b, c, tc in un) or "keine"))
    z.append("  TRADES im Umfeld bar-1 .. bar+100:")
    for t in daten["MAI"]["v"]:
        if i20 - 1 <= int(t.entry_bar) <= i20 + 100:
            z.append(f"    #{daten['MAI']['v'].index(t) + 1:3d} K{int(t.kid):3d} "
                     f"{str(t.richtung):5s} bar={int(t.bar):5d} "
                     f"entry_bar={int(t.entry_bar):5d} "
                     f"entry={float(t.entry):.4f} basis={float(t.basis):.4f} "
                     f"sweep={float(t.sweep):.4f} sl={float(t.sl):.4f} "
                     f"tp2={float(t.tp2):.4f} R={float(t.r):+.4f}")
    z.append("")

    # ============================================== B) Richtungs-Audit
    z.append("========== B) RICHTUNGSAUDIT (SHORT<->OBEN / LONG<->UNTEN) ==========")
    for lab, _s, _e in MONATE:
        tr = daten[lab]["v"]
        bad = []
        n_long = sum(1 for t in tr if str(t.richtung) == "LONG")
        n_short = len(tr) - n_long
        for t in tr:
            ok = True
            k = int(t.bar)
            if str(t.richtung) == "SHORT":
                ok = float(t.sweep) >= float(t.basis)
            else:
                ok = float(t.sweep) <= float(t.basis)
            if not ok:
                bad.append((int(t.kid), str(t.richtung), k, float(t.sweep),
                            float(t.basis)))
        z.append(f"  {lab}: {len(tr)} Trades ({n_long} LONG / {n_short} SHORT) "
                 f"| Sweep-Seite-Inkonsistenzen: {len(bad)}"
                 + ("" if not bad else f" -> {bad[:5]}"))
        # LONG/SHORT getrennt: mittleres R, Trefferquote
        for richt in ("LONG", "SHORT"):
            xs = [t for t in tr if str(t.richtung) == richt]
            if not xs:
                continue
            rs = [float(t.r) for t in xs]
            sl_n = sum(1 for t in xs if str(t.grund2) == "SL")
            z.append(f"      {richt:5s}: n={len(xs):3d} SumR={sum(rs):+10.4f} "
                     f"| SL-Quote(H2) {100.0 * sl_n / len(xs):5.1f} % | "
                     f"|sl-entry| median "
                     f"{float(np.median([abs(float(t.sl) - float(t.entry)) for t in xs])):.4f}")
    z.append("")

    # ============================================== C) Baseline vs V020
    z.append("========== C) BASELINE _se_trades  vs  V020 _se_trades_v020 ==========")
    z.append(f"  {'Monat':5s} {'Baseline n':>10s} {'Baseline SumR':>14s} "
             f"{'V020 n':>7s} {'V020 SumR':>12s}")
    for lab, _s, _e in MONATE:
        rb = [float(t.r) for t in daten[lab]["b"]]
        rv = [float(t.r) for t in daten[lab]["v"]]
        z.append(f"  {lab:5s} {len(rb):10d} {sum(rb):+14.6f} "
                 f"{len(rv):7d} {sum(rv):+12.6f}")
    z.append("")

    # ================================= D) Risiko-Klammer / E) ENDE
    z.append("========== D) KONTROLLE A -- RISIKO-KLAMMER ==========")
    z.append("  effektives R = R * risk / max(risk, floor)  "
             "(floor USD bzw. floor = k*ATR14)")
    for lab, _s, _e in MONATE:
        tr = daten[lab]["v"]
        atr = daten[lab]["atr"]
        atr_med = float(np.nanmedian(atr))
        base = sum(float(t.r) for t in tr)
        z.append(f"  {lab}: ATR14-Median(M15) = {atr_med:.4f} USD | "
                 f"Legacy-SumR {base:+.6f}")
        for floor_name, floor in (
                ("0.20 USD", 0.20), ("0.30 USD", 0.30), ("0.50 USD", 0.50),
                ("1.0 USD", 1.0),
                ("0.5*ATR", 0.5 * atr_med), ("1.0*ATR", 1.0 * atr_med),
                ("1.5*ATR", 1.5 * atr_med)):
            s = 0.0
            n_geklemmt = 0
            for t in tr:
                risk = abs(float(t.sl) - float(t.entry))
                m = max(risk, float(floor))
                if m > risk + 1e-12:
                    n_geklemmt += 1
                s += float(t.r) * risk / m
            z.append(f"      floor {floor_name:9s} ({floor:6.4f} USD): "
                     f"SumR {s:+10.6f} R  |  geklemmt {n_geklemmt:3d}/"
                     f"{len(tr)}  |  Top-Trade-Anteil "
                     f"{100.0 * max(float(t.r) * abs(float(t.sl) - float(t.entry)) / max(abs(float(t.sl) - float(t.entry)), float(floor)) for t in tr) / s if s != 0 else float('nan'):6.1f} %")
    z.append("")
    z.append("========== E) KONTROLLE B -- ENDE-BEREINIGUNG ==========")
    z.append("  Haelften mit grund == 'ENDE' auf r=0 gesetzt (kein MTM-Exit)")
    for lab, _s, _e in MONATE:
        tr = daten[lab]["v"]
        w1 = cfg.tp1_anteil_pct / 100.0
        w2 = 1.0 - w1
        base = sum(float(t.r) for t in tr)
        s = 0.0
        for t in tr:
            r1 = 0.0 if str(t.grund1) == "ENDE" else float(t.r1)
            r2 = 0.0 if str(t.grund2) == "ENDE" else float(t.r2)
            s += w1 * r1 + w2 * r2
        z.append(f"  {lab}: Legacy-SumR {base:+10.6f}  ->  ENDE-bereinigt "
                 f"{s:+10.6f}  (Delta {s - base:+.6f})")
    z.append("")
    z.append("========== F) ATR(14) JE MONAT ==========")
    for lab, _s, _e in MONATE:
        atr = daten[lab]["atr"]
        v = atr[~np.isnan(atr)]
        z.append(f"  {lab}: min {v.min():.4f} | p25 {np.percentile(v, 25):.4f} "
                 f"| median {np.median(v):.4f} | p75 "
                 f"{np.percentile(v, 75):.4f} | max {v.max():.4f} USD")

    PROTOKOLL.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")
    for zl in z:
        print(zl)
    print(f"\n-> {PROTOKOLL}")


if __name__ == "__main__":
    main()
