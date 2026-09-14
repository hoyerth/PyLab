# -*- coding: utf-8 -*-
"""READ-ONLY Warm-up-Probe (H20.47): Kaltstart- vs. Historien-Konvergenz.

Ziel (H20.46 Abschnitt 10.1, freigegeben):
  Ermittlung der minimalen Vorgeschichte N (in BKZ-Handelstagen vor dem
  Analysebeginn 2026-08-10), ab der das AUG-Segment (08-10 .. 08-19 Box bzw.
  .. 08-28 Vollauf) exakt einschwingt und keine Kaltstart-Verzerrung mehr
  zeigt.

Design (bindend, Architekten-Freigabe):
  * Fenster W_k = [S_k, 2026-08-28) -- der RECHTE RAND ist ueber alle Laeufe
    kalenderidentisch (H20.46: rechter Rand ist der einzige legitime
    Zukunftseinfluss).
  * Kalenderanker per ``searchsorted`` auf BKZ (Kanon K6) -- KEINE
    Bar-Konstanten: i0 = '2026-08-10', i1 = '2026-08-19' (H1-Boxende),
    i2 = Fensterende. Es gilt fuer ALLE Laeufe i1-i0 == 644, i2-i0 == 1288.
  * Ein Scan je Fenster (teuer), zwei Trade-Laeufe (billig):
      (A) BOX  : box_end_bar = i1  -> H1-Box-Segment [i0, i1)
      (B) VOLL : box_end_bar = i2  -> H1 [i0, i1) + H2 [i1, i2)
  * Trade-Key ist KALENDERINVARIANT: (entry_rel, richtung, r, sl, exit1_rel,
    exit2_rel) mit *_rel = Bar-Index relativ zu i0. Keine Offset-Arithmetik.
  * Referenz = FESTER Asymptoten-Anker N=500 (Start 2024-09-11), flankiert
    von der Stufen-zu-Stufen-Delta-Messung. Ist der Pinned-Anker (noch) nicht
    gefahren, dient die laengste gemessene Stufe als VORLAEUFIGE Referenz
    (im Protokoll explizit als solche ausgewiesen).
  * Konvergenz EXAKT: dN == 0 UND |dR| <= 1e-9 UND Set-Diff == 0 -- gegen
    die Referenz UND gegen ALLE laengeren Stufen (Plateau-Nachweis).
  * Modus A ausschliesslich (``hook=None``). Adapter (Modus B) bleibt
    AUG-gebunden und wird NICHT importiert (H20.46 Abschnitt 10.2).

Kostenhinweis (empirisch, N=0..40): Der Scan ist O(n * E) mit E ~ 0.031*n,
also praktisch quadratisch; N=500 (~47.500 Bars) bedeutet ~1-2 h Laufzeit.
Deshalb ist die Leiter per ``--leiter`` stufenweise fahrbar und das Protokoll
wird nach JEDER Stufe neu geschrieben (Partialstand ist immer verfuegbar).

Read-only: ``_lade_fenster`` wird ausschliesslich in der geladenen
Modul-INSTANZ durch ein Lambda ersetzt; der ``FENSTER``-Eintrag 'RUN' wird
nach dem Laden sofort wieder entfernt. Keine Datei-, Motor-, Adapter- oder
DB-Mutation. Einzige Schreiboperation: dieses Protokoll
``_chk_warmup_probe_out.txt``.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
PROTOKOLL = ROOT / "test" / "_chk_warmup_probe_out.txt"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

ANALYSE_BEGINN = "2026-08-10"        # i0-Kalenderanker
BOX_ENDE_DATUM = "2026-08-19"        # i1-Kalenderanker
FENSTER_ENDE = "2026-08-28"          # exklusiv
SEGMENT_BARS = 1288                  # i2 - i0 (08-10 .. 08-28 exkl.)
BOX_BARS = 644                       # i1 - i0 (08-10 .. 08-19)

# Vorlauf-Referenzrahmen (nur zum Ableiten der BKZ-Handelstag-Leiter):
# enthaelt die letzten >500 Handelstage vor dem Analysebeginn.
RAHMEN_START = "2023-09-28"

# Log-gespacte Handelstag-Leiter (N = BKZ-Handelstage vor 2026-08-10).
LEITER_N: Tuple[int, ...] = (0, 5, 10, 20, 40, 80, 130, 190, 250, 375, 500)
PINNED_N = 500                       # fester Asymptoten-Anker

# Nullpunkt-Kontrolle (H20.44/H20.46): N=0 == AUG nativ.
ANKER_N0 = {
    "box": (14, 27.327383),          # H1-Box (box_end = 644)
    "voll": (29, 23.389914),         # Vollauf (box_end = 1288)
}
TOL = 1e-9


def _sha(p: Path) -> str:
    """SHA256 einer Datei (Guard gegen Fremdstand)."""
    return hashlib.sha256(p.read_bytes()).hexdigest()


class _StdoutStub:
    """fd-freier stdout-Ersatz (Baseline/V020 haengen beim exec um)."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _load(name: str, p: Path) -> Any:
    """Modul laden, ohne dessen stdout-Umbau auf das echte stdout zu lassen."""
    real = sys.stdout
    try:
        sys.stdout = _StdoutStub()  # type: ignore[assignment]
        spec = importlib.util.spec_from_loader(name, loader=None)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        mod.__file__ = str(p)
        sys.modules[name] = mod
        exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"),
             mod.__dict__)
    finally:
        sys.stdout = real
    return mod


def _lade(B: Any, start: str) -> Any:
    """Fenster [start, FENSTER_ENDE) ueber den KANONISCHEN Loader der Baseline.

    Der FENSTER-Eintrag 'RUN' existiert nur waehrend des Aufrufs und wird
    sofort entfernt (keine Fenster-Pollution).
    """
    B.FENSTER["RUN"] = (start, FENSTER_ENDE)
    try:
        return B._lade_fenster("RUN")
    finally:
        del B.FENSTER["RUN"]


def _scan(B: Any, df: Any, cfg: Any) -> Dict[str, Any]:
    """Scan auf df (box_end wird vom Aufrufer gesetzt); Loader nur in-Instanz."""
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=df: _d.copy())  # type: ignore
    try:
        return B._se_scan("AUG", cfg)
    finally:
        B._lade_fenster = original  # type: ignore


def _trades(V: Any, scan: Dict[str, Any], cfg: Any, box: int) -> List[Any]:
    """Trade-Schleife (Modus A) mit erzwungenem box_end_bar = box."""
    s = copy.deepcopy(scan)
    s["box_end_bar"] = int(box)
    eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=cfg)
    ss, _st = eng._se_trades_v020(s, cfg)
    return list(ss)


def _seg(trades: List[Any], i0: int, a: int, b: int
         ) -> Tuple[Dict[Tuple[Any, ...], Any], float]:
    """Kalenderinvariantes Segment-Set (Keys relativ zu i0) + Summe R."""
    out: Dict[Tuple[Any, ...], Any] = {}
    for x in trades:
        e = int(x.entry_bar)
        if a <= e < b:
            key = (e - i0, str(x.richtung), round(float(x.r), 6),
                   round(float(x.sl), 6), int(x.exit1_bar) - i0,
                   int(x.exit2_bar) - i0)
            out[key] = x
    r = float(sum(float(out[k].r) for k in out))
    return out, r


def _bericht(stufen: List[Dict[str, Any]], start_von: Dict[int, str],
             leiter: Tuple[int, ...], n_ht: int, ref_n: int,
             laufzeit: float) -> List[str]:
    """Vollstaendigen Protokolltext aus dem aktuellen Messstand bauen."""
    z: List[str] = []
    z.append("READ-ONLY Warm-up-Probe (H20.47) | AUG-Segment-Stabilitaet")
    z.append("SHA-Guards OK: Baseline 53f28e1b / V020 e79c5c29 / "
             "Adapter 770eda2c (Adapter NICHT importiert)")
    z.append("Analyseanker: i0='2026-08-10', i1='2026-08-19' (Box), "
             "i2=Fensterende '2026-08-28' exkl. | Modus A"
             " (hook=None, universell)")

    z.append("")
    z.append(f"===== LEITER (BKZ-Handelstage vor {ANALYSE_BEGINN}; Kanon "
             f"K1/K4/K6) =====")
    z.append(f"Handelstage im Referenzrahmen: {n_ht} | Leiter: "
             f"{list(leiter)} | Pinned-Anker: N={PINNED_N}")
    z.append(f"{'N':>4s}  {'Start (BKZ)':12s}")
    for N in leiter:
        z.append(f"{N:4d}  {start_von[N]:12s}")

    z.append("")
    z.append("===== MESSUNG: Fenster [Start, 2026-08-28) | rechter Rand "
             "kalenderidentisch =====")
    z.append(f"{'N':>4s} {'n':>6s} {'i0':>6s} {'edges':>5s} {'seeds':>5s} "
             f"{'r21':>4s} {'tomb':>4s} {'warA':>4s} {'tLade':>6s} "
             f"{'tScan':>7s} {'tBox':>6s} {'tVoll':>6s} {'BOX_N':>5s} "
             f"{'BOX_R':>11s} {'VOLL_N':>6s} {'VOLL_R':>11s} {'H2_N':>4s} "
             f"{'H2_R':>11s}")
    for s in stufen:
        z.append(
            f"{s['N']:4d} {s['n']:6d} {s['i0']:6d} {s['edges']:5d} "
            f"{s['seeds']:5d} {s['r21']:4d} {s['tomb']:4d} {s['war']:4d} "
            f"{s['t_lade']:6.1f} {s['t_scan']:7.1f} {s['t_box']:6.1f} "
            f"{s['t_voll']:6.1f} {len(s['s_box']):5d} {s['r_box']:+11.6f} "
            f"{len(s['s_voll']):6d} {s['r_voll']:+11.6f} "
            f"{len(s['s_h2']):4d} {s['r_h2']:+11.6f}")

    if not stufen:
        return z

    ref = next((s for s in stufen if s["N"] == ref_n), stufen[-1])
    pinned_ok = any(s["N"] == PINNED_N for s in stufen)
    z.append("")
    z.append(f"===== DELTA gegen Referenz N={ref['N']} "
             f"(Start {ref['start']}; "
             f"{'Pinned-Anker' if pinned_ok else 'VORLAEUFIG = laengste '
              'gemessene Stufe, Pinned N=500 noch offen'}) =====")
    z.append(f"{'N':>4s} {'dN_BOX':>6s} {'dR_BOX':>12s} {'sd_BOX':>6s} "
             f"{'dN_VOLL':>7s} {'dR_VOLL':>12s} {'sd_VOLL':>7s} "
             f"{'dN_H2':>5s} {'dR_H2':>11s} {'sd_H2':>5s} {'exakt':>6s}")
    for s in stufen:
        dNB = len(s["s_box"]) - len(ref["s_box"])
        dRB = s["r_box"] - ref["r_box"]
        sdB = len(set(s["s_box"]) ^ set(ref["s_box"]))
        dNV = len(s["s_voll"]) - len(ref["s_voll"])
        dRV = s["r_voll"] - ref["r_voll"]
        sdV = len(set(s["s_voll"]) ^ set(ref["s_voll"]))
        dNH = len(s["s_h2"]) - len(ref["s_h2"])
        dRH = s["r_h2"] - ref["r_h2"]
        sdH = len(set(s["s_h2"]) ^ set(ref["s_h2"]))
        exakt = (dNB == 0 and abs(dRB) <= TOL and sdB == 0
                 and dNV == 0 and abs(dRV) <= TOL and sdV == 0)
        z.append(f"{s['N']:4d} {dNB:+6d} {dRB:+12.6f} {sdB:6d} {dNV:+7d} "
                 f"{dRV:+12.6f} {sdV:7d} {dNH:+5d} {dRH:+11.6f} {sdH:5d} "
                 f"{'JA' if exakt else 'nein':>6s}")

    z.append("")
    z.append("===== PLATEAU-NACHWEIS (exakt gegen ALLE laengeren Stufen) =====")
    stabil: Dict[int, bool] = {}
    for s in stufen:
        laenger = [t for t in stufen if t["N"] > s["N"]]
        ok = True
        for t in laenger:
            if (len(s["s_box"]) != len(t["s_box"])
                    or len(set(s["s_box"]) ^ set(t["s_box"])) != 0
                    or abs(s["r_box"] - t["r_box"]) > TOL
                    or len(s["s_voll"]) != len(t["s_voll"])
                    or len(set(s["s_voll"]) ^ set(t["s_voll"])) != 0
                    or abs(s["r_voll"] - t["r_voll"]) > TOL):
                ok = False
                break
        stabil[s["N"]] = ok
        z.append(f"  N={s['N']:4d} ({s['start']}): "
                 f"{'PLATEAU-STABIL' if ok else 'instabil'} "
                 f"({len(laenger)} laengere Stufen geprueft)")

    z.append("")
    z.append("===== VERDIKT =====")
    kandidaten = [s["N"] for s in stufen if stabil[s["N"]]]
    if kandidaten:
        z.append(f"  Minimaler Warm-up (exaktes Plateau, BOX UND VOLL): "
                 f"N_min = {min(kandidaten)} BKZ-Handelstage "
                 f"(Start {start_von[min(kandidaten)]}).")
    else:
        z.append(f"  Bislang KEIN exaktes Plateau (max gemessen "
                 f"N={max(s['N'] for s in stufen)}).")
    for ziel in ("box", "voll"):
        kk = []
        for s in stufen:
            laenger = [t for t in stufen if t["N"] > s["N"]]
            if all(
                    len(s[f"s_{ziel}"]) == len(t[f"s_{ziel}"])
                    and len(set(s[f"s_{ziel}"]) ^ set(t[f"s_{ziel}"])) == 0
                    and abs(s[f"r_{ziel}"] - t[f"r_{ziel}"]) <= TOL
                    for t in laenger):
                kk.append(s["N"])
        z.append(f"  N_min({ziel.upper()}) = "
                 f"{min(kk) if kk else 'noch kein exaktes Plateau'}")
    s0 = next((s for s in stufen if s["N"] == 0), None)
    if s0 is not None:
        z.append(f"  Kaltstart (N=0) gegen N={ref['N']}: BOX dN="
                 f"{len(s0['s_box']) - len(ref['s_box']):+d} dR="
                 f"{s0['r_box'] - ref['r_box']:+.6f} | VOLL dN="
                 f"{len(s0['s_voll']) - len(ref['s_voll']):+d} dR="
                 f"{s0['r_voll'] - ref['r_voll']:+.6f}")

    if s0 is not None:
        z.append("")
        z.append(f"===== DETAIL N=0 (Kaltstart) vs N={ref['N']} =====")
        for ziel, lab in (("s_box", "BOX(H1)"), ("s_voll", "VOLL")):
            a = set(s0[ziel])
            b = set(ref[ziel])
            z.append(f"  {lab}: nur-N0 {len(a - b)}, nur-N{ref['N']} "
                     f"{len(b - a)}, gemeinsam {len(a & b)}")
            for k in sorted(a - b)[:6]:
                z.append(f"      nur-N0    entry_rel={k[0]:4d} {k[1]:5s} "
                         f"r={k[2]:+.6f}")
            for k in sorted(b - a)[:6]:
                z.append(f"      nur-N{ref['N']:<3d} entry_rel={k[0]:4d} "
                         f"{k[1]:5s} r={k[2]:+.6f}")

    z.append("")
    z.append(f"Laufzeit bisher: {laufzeit:.1f}s")
    return z


def _schreibe(z: List[str]) -> None:
    PROTOKOLL.write_text("\n".join(z) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="H20.47 Warm-up-Probe (read-only)")
    ap.add_argument("--leiter", default=",".join(str(x) for x in LEITER_N),
                    help="Komma-Liste der N-Stufen (BKZ-Handelstage)")
    args = ap.parse_args()
    leiter: Tuple[int, ...] = tuple(
        int(x) for x in str(args.leiter).split(",") if x.strip() != "")

    t_ges = time.perf_counter()

    # --- 0. SHA-Guards -----------------------------------------------------
    assert _sha(BASELINE_PFAD) == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(V020_PFAD) == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ADAPTER_PFAD) == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"

    B = _load("basis_warm", BASELINE_PFAD)
    V = _load("v020_warm", V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()

    # --- 1. BKZ-Handelstag-Leiter ableiten ---------------------------------
    rahmen = _lade(B, RAHMEN_START)
    ts_rahmen = rahmen["ts"].to_numpy().astype("datetime64[ns]")
    tage = np.unique(ts_rahmen.astype("datetime64[D]"))
    anchor_d = np.datetime64(ANALYSE_BEGINN, "D")
    vor = tage[tage < anchor_d]
    assert len(vor) >= max(leiter), "zu wenig Vorgeschichte im Rahmen"
    start_von: Dict[int, str] = {0: ANALYSE_BEGINN}
    for N in leiter:
        if N > 0:
            start_von[N] = str(vor[-N])
    print(f"[leiter] {len(vor)} Handelstage verfuegbar; Leiter={list(leiter)}",
          flush=True)

    # --- 2. Messung je Stufe (Protokoll nach JEDER Stufe aktualisiert) ------
    stufen: List[Dict[str, Any]] = []
    for N in leiter:
        t0 = time.perf_counter()
        d = _lade(B, start_von[N])
        t_lade = time.perf_counter() - t0
        ts = d["ts"].to_numpy().astype("datetime64[ns]")
        n = int(len(d))
        i0 = int(np.searchsorted(ts, np.datetime64(ANALYSE_BEGINN)))
        i1 = int(np.searchsorted(ts, np.datetime64(BOX_ENDE_DATUM)))
        i2 = n
        assert i1 - i0 == BOX_BARS, f"N={N}: i1-i0={i1 - i0} != {BOX_BARS}"
        assert i2 - i0 == SEGMENT_BARS, \
            f"N={N}: i2-i0={i2 - i0} != {SEGMENT_BARS}"

        t1 = time.perf_counter()
        scan = _scan(B, d, cfg)
        t_scan = time.perf_counter() - t1
        t2 = time.perf_counter()
        tr_box = _trades(V, scan, cfg, i1)
        t_box = time.perf_counter() - t2
        t3 = time.perf_counter()
        tr_voll = _trades(V, scan, cfg, i2)
        t_voll = time.perf_counter() - t3

        s_box, r_box = _seg(tr_box, i0, i0, i1)
        s_voll, r_voll = _seg(tr_voll, i0, i0, i2)
        s_h1v, r_h1v = _seg(tr_voll, i0, i0, i1)
        s_h2, r_h2 = _seg(tr_voll, i0, i1, i2)

        if N == 0:
            assert (len(s_box), round(r_box, 6)) == ANKER_N0["box"], \
                f"N=0 Box-Anker verletzt: {len(s_box)}/{r_box:.6f}"
            assert (len(s_voll), round(r_voll, 6)) == ANKER_N0["voll"], \
                f"N=0 Voll-Anker verletzt: {len(s_voll)}/{r_voll:.6f}"

        stufen.append({
            "N": N, "start": start_von[N], "n": n, "i0": i0, "i1": i1,
            "i2": i2, "edges": len(scan["edges"]),
            "seeds": len(scan["seeds"]),
            "r21": len(scan.get("r21_geloescht", [])),
            "tomb": len(scan.get("tombstones", [])),
            "war": len(B.WAR_AUSSEN_IDS),
            "s_box": s_box, "r_box": r_box,
            "s_voll": s_voll, "r_voll": r_voll,
            "s_h1v": s_h1v, "r_h1v": r_h1v,
            "s_h2": s_h2, "r_h2": r_h2,
            "t_lade": t_lade, "t_scan": t_scan, "t_box": t_box,
            "t_voll": t_voll, "t_stufe": time.perf_counter() - t0,
        })
        _schreibe(_bericht(stufen, start_von, leiter, len(tage), PINNED_N,
                           time.perf_counter() - t_ges))
        print(f"[stufe N={N:4d}] n={n:6d} i0={i0:6d} "
              f"edges={len(scan['edges']):4d} box={len(s_box):3d}/"
              f"{r_box:+.6f} voll={len(s_voll):3d}/{r_voll:+.6f} "
              f"[lade {t_lade:.1f}s scan {t_scan:.1f}s box {t_box:.1f}s "
              f"voll {t_voll:.1f}s | total {time.perf_counter() - t_ges:.1f}s]",
              flush=True)

    z = _bericht(stufen, start_von, leiter, len(tage), PINNED_N,
                 time.perf_counter() - t_ges)
    _schreibe(z)
    for zl in z:
        print(zl)
    print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
