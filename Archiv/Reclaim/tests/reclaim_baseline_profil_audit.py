# test/reclaim_baseline_profil_audit.py
"""Baseline-Signal-Profil-Diagnose (REINE DIAGNOSE - kein Fix, kein Store).

Mentor-Review 02.09. (Schritt 2): Bevor die Range-Generation im Store
nachgebildet wird, muss die exakte empirische Anatomie der Baseline-
Signale offen liegen. Fuer jedes Baseline-Signal (S1/S2/AUG) werden
kausale Zustandsgroessen erfasst:

  * phase_age_bars       : Bars seit Phasenstart (k - p.i_start)
  * bounces_this_edge    : Tests der GEHANDELTEN Zonen-Kante bis Signal
                           (nb, Baseline-_bounce_nr gegen laufende Zone)
  * bounces_opp_edge     : Tests der GEGENKANTE bis Signal (gleiche Zone)
  * combined_touches     : bounces_this_edge + bounces_opp_edge
  * piv_h / piv_l        : Roh-Pivot-Tests der Phase (h_ts/l_ts <= Signal-ts)
                           - Struktur-Sicht der Etablierung (MIN_ESTABLISH)
  * dist_to_last_break   : Bars seit dem 2-Close-Bruch der Vorphase
                           (brk_idx der letzten Phase mit break_dir)
  * bars_to_phase_end    : Bars bis Phasenende (klein = Signal nahe Bruch/
                           Phasen-Ende; post-hoc Kontext)
  * phase_ended_by_break : ob die Phase spaeter durch Bruch endete (post-hoc)
  * trade: resultat, r_mult, reclaim, typ, crv, crv2

Kausalitaet: bounces_*/piv_* werden NUR aus Daten bis zur Signal-Bar k
gebildet (p.h_prices/p.h_ts enthalten genau die bis Phase-Ende gesammelten
Pivots; Filter <= s.ts macht sie kausal). bars_to_phase_end und
phase_ended_by_break sind als post-hoc Kontext markiert (nicht fuer die
Signal-Entscheidung, nur fuer die Kohorten-Analyse).

Aufruf:  python test/reclaim_baseline_profil_audit.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
import types
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC_BASELINE = ROOT / "scripts" / "phasen_volumen_profil.py"
OUT_DIR = Path(__file__).resolve().parent

WINDOWS: List[Tuple[str, str, str]] = [
    ("AUG", "2026-08-10", "2026-08-28"),
    ("S1", "2026-02-05", "2026-08-28"),
    ("S2", "2025-01-01", "2025-12-01"),
]

# Baseline-Referenz (CD=12) zur Verifikation des Laufes
EXPECTED: Dict[str, Tuple[int, float]] = {
    "AUG": (27, +24.97),
    "S1": (201, +197.26),
    "S2": (210, +99.88),
}

METRICS: List[str] = [
    "phase_age_bars", "bounces_this_edge", "bounces_opp_edge",
    "combined_touches", "piv_h", "piv_l", "dist_to_last_break",
    "bars_to_phase_end",
]


def load_baseline(start: str, ende: str) -> dict:
    """Fuehrt die Baseline bis vor den Signal-Scan aus (exec-cut).

    Liefert den Modul-Namespace mit df, phases, find_reclaim_signals,
    _bounce_nr, _laufende_zone, _aufloesen etc. Konsolenausgabe wird
    unterdrueckt (nur Fehler werden durchgereicht).
    """
    src = SRC_BASELINE.read_text(encoding="utf-8")
    cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
    mod_name = f"_phasen_bpa_{start}_{ende}"
    if mod_name in sys.modules:
        return sys.modules[mod_name].__dict__
    mod = types.ModuleType(mod_name)
    mod.__file__ = str(SRC_BASELINE)
    sys.modules[mod_name] = mod
    sys.argv = [str(SRC_BASELINE), f"--start={start}", f"--ende={ende}"]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(src[:cut], str(SRC_BASELINE), "exec"), mod.__dict__)
    if "phases" not in mod.__dict__:
        raise RuntimeError(f"Baseline exec fehlgeschlagen ({start}..{ende}): "
                           f"{buf.getvalue()[-2000:]}")
    return mod.__dict__


def collect(name: str, start: str, ende: str) -> Tuple[pd.DataFrame, dict]:
    """Fuehrt Baseline aus und erfasst je Signal die Profil-Groessen."""
    ns = load_baseline(start, ende)
    df: pd.DataFrame = ns["df"]
    phases = ns["phases"]
    find_reclaim_signals = ns["find_reclaim_signals"]
    _bounce_nr = ns["_bounce_nr"]

    refs: List = []
    for i_p, p in enumerate(phases, 1):
        for s in find_reclaim_signals(df, p):
            s.phase = i_p
            refs.append(s)
    refs.sort(key=lambda s: s.ts)

    # letzte Phase mit break_dir je Phasenindex (fuer dist_to_last_break)
    last_brk_idx: Dict[int, Optional[int]] = {}
    last_brk_dir: Dict[int, Optional[str]] = {}
    cur_brk: Optional[int] = None
    cur_dir: Optional[str] = None
    for i_p in range(1, len(phases) + 1):
        last_brk_idx[i_p] = cur_brk
        last_brk_dir[i_p] = cur_dir
        p = phases[i_p - 1]
        if p.break_dir is not None and p.brk_idx is not None:
            cur_brk = p.brk_idx
            cur_dir = p.break_dir

    rows: List[dict] = []
    for s in refs:
        p = phases[s.phase - 1]
        assert s.trade is not None
        ts_k = s.ts
        # Bounce-Counts gegen die laufende Zone (Entscheidungszustand)
        n_h, n_l = _bounce_nr(p.h_prices, p.h_ts, p.l_prices, p.l_ts,
                              ts_k, s.U_laufend, s.L_laufend)
        if s.typ == "SHORT":
            this_edge, opp_edge = n_h, n_l
        else:
            this_edge, opp_edge = n_l, n_h
        # Roh-Pivot-Counts der Phase bis zum Signal (kausal)
        c_h = sum(1 for t in p.h_ts if t <= ts_k)
        c_l = sum(1 for t in p.l_ts if t <= ts_k)
        prev_brk = last_brk_idx[s.phase]
        rows.append({
            "window": name,
            "phase": s.phase,
            "ts": ts_k,
            "typ": s.typ,
            "reclaim": s.reclaim,
            "bar": s.bar,
            "phase_start_bar": p.i_start,
            "phase_age_bars": s.bar - p.i_start,
            "bounces_this_edge": int(this_edge),
            "bounces_opp_edge": int(opp_edge),
            "combined_touches": int(this_edge + opp_edge),
            "piv_h": c_h,
            "piv_l": c_l,
            "dist_to_last_break": (s.bar - prev_brk) if prev_brk is not None else np.nan,
            "prev_break_dir": last_brk_dir[s.phase],
            "bars_to_phase_end": p.i_ende - s.bar,
            "phase_ended_by_break": p.break_dir is not None,
            "entry": s.einstieg_preis,
            "crv": s.crv,
            "crv2": s.crv2,
            "resultat": s.trade.resultat,
            "r_mult": s.trade.r_mult,
        })
    return pd.DataFrame(rows), {"df": df, "phases": phases, "ns": ns}


def _q_txt(vals: np.ndarray) -> str:
    a = np.asarray(vals, dtype=float)
    a = a[~np.isnan(a)]
    if not len(a):
        return "  -  "
    q = np.percentile(a, [25, 50, 75])
    return f"{q[0]:7.0f} | {q[1]:6.0f} | {q[2]:6.0f}"


def report(name: str, d: pd.DataFrame) -> None:
    dec = d[d["resultat"] != "NEUTRAL"]
    wins = d[d["resultat"] == "GEWONNEN"]
    loss = d[d["resultat"] == "VERLOREN"]
    sum_r = d["r_mult"].sum()
    wr = 100.0 * len(wins) / len(dec) if len(dec) else 0.0
    exp_n, exp_r = EXPECTED.get(name, (None, None))
    ok = (len(d) == exp_n and abs(sum_r - exp_r) < 0.05) if exp_n else False
    print(f"\n{'#' * 100}")
    print(f"# BASELINE-PROFIL {name}: {len(d)} Signale | WR {wr:.0f}% | "
          f"Summe R {sum_r:+.2f} | Referenz {exp_n}/{exp_r:+.2f} "
          f"{'OK' if ok else 'ABWEICHUNG'}")
    print(f"{'#' * 100}")
    print(f"{'Metrik':22s} | {'Kohorte':9s} | {'n':>4s} | "
          f"{'p25':>7s} | {'Median':>6s} | {'p75':>6s}")
    print("-" * 78)
    for m in METRICS:
        for label, sub in (("alle", d), ("GEW", wins), ("VER", loss)):
            if sub.empty:
                continue
            print(f"{m:22s} | {label:9s} | {len(sub):4d} | "
                  f"{_q_txt(sub[m].values)}")
    # Typ-/Reclaim-Mix
    sh = (d["typ"] == "SHORT").sum()
    print(f"\n  Mix: {sh} SHORT / {len(d) - sh} LONG | "
          f"Reclaim in_bar {(d['reclaim'] == 'in_bar').sum()} / "
          f"next_bar {(d['reclaim'] == 'next_bar').sum()}")
    print(f"  Phase spaeter durch Bruch geendet (post-hoc): "
          f"{d['phase_ended_by_break'].sum()}/{len(d)}")


def main() -> None:
    t_all = time.time()
    frames: Dict[str, pd.DataFrame] = {}
    for name, start, ende in WINDOWS:
        t0 = time.time()
        print(f"\n>>> Baseline-Lauf {name} ({start} - {ende}) ...", flush=True)
        d, _ctx = collect(name, start, ende)
        csv_p = OUT_DIR / f"tmp_baseline_profil_{name}.csv"
        d.to_csv(csv_p, index=False, encoding="utf-8")
        print(f">>> {name}: {len(d)} Signale in {time.time() - t0:.0f}s | CSV {csv_p.name}")
        report(name, d)
        frames[name] = d

    # ---- Gewinner-DNA kreuzstabil (Median je Fenster) ----
    print(f"\n{'=' * 100}")
    print("GEWINNER-DNA kreuzstabil (Median je Fenster; p25-p75 in Klammern)")
    print("=" * 100)
    hdr = f"{'Metrik':22s} | {'Kohorte':4s} | {'AUG':>18s} | {'S1':>18s} | {'S2':>18s}"
    print(hdr)
    print("-" * 100)
    for m in METRICS:
        cells = []
        for name in ("AUG", "S1", "S2"):
            d = frames[name]
            g = d[d["resultat"] == "GEWONNEN"][m].values
            a = np.asarray(g, dtype=float)
            a = a[~np.isnan(a)]
            if not len(a):
                cells.append("  -  ")
            else:
                q = np.percentile(a, [25, 50, 75])
                cells.append(f"{q[0]:6.0f} {q[1]:5.0f} {q[2]:6.0f}")
        print(f"{m:22s} | {'GEW':4s} | {cells[0]:>18s} | {cells[1]:>18s} | {cells[2]:>18s}")
    print("\nLegende Gewinner-DNA: p25 | MEDIAN | p75 (Bars bzw. Anzahl Touches)")
    print(f"Gesamtzeit: {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
