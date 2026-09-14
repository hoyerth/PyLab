# -*- coding: utf-8 -*-
"""run_lab.py -- universeller Modus-A-Runner (beliebiger Zeitraum + Parameter).

Read-only Labor-Werkzeug. Laedt einen FREI GEWAEHLTEN BKZ-Zeitraum, faehrt den
kausalen SE-Scan und die Modus-A-Trade-Schleife und schreibt eine Text-/TSV-
Zusammenfassung nach ``test/run_lab_out.txt`` bzw. ``test/run_lab_trades.tsv``.

Merkmale
--------
* ``--start`` / ``--end``  : beliebiger BKZ-Zeitraum (Kanon K1/K4, keine
  Zeitzonen-Projektion, keine Bar-Konstanten).
* ``--box-end``            : optionale BKZ-Kalendergrenze fuer die H1-Box
  (``searchsorted``). Fehlt sie, ist ``box_end_bar = n`` (Vollauf).
* ``--warmup-tage``        : N BKZ-Handelstage Vorlauf. Sie werden MITGELADEN
  (Kanten-Genese), aber NICHT ausgewertet (Trades erst ab ``entry >= i0``).
  ``0`` = autonomes Fenster (Kaltstart, H20.47: fensterabhaengig).
* ``--param feld=wert``    : beliebig oft; ueberschreibt JEDES Feld von
  ``StraightEdgeHarnessKonfiguration`` (Baseline) oder
  ``V020KantenKonfiguration`` (V020). Kein Hardcoding.
* Modus A ausschliesslich (``hook=None``). Der Adapter (Modus B) bleibt
  AUG-gebunden (H20.46 Abschnitt 6) und wird NICHT importiert.

Wichtige Einschraenkung (H20.47, gemessen)
------------------------------------------
Die Kanten-Basis ist ein laufender Mittelwert ueber alle Dochte
(``basis = mean(wicks)``). Das System ist daher NICHT stationar: Ergebnisse
sind fensterabhaengig, es existiert kein Warm-up-Plateau. Dieser Runner macht
das nicht stationaer -- er macht es MESSBAR und optimierbar.

Read-only: DB nur lesend; ``FENSTER``-Eintrag 'LAB' lebt nur waehrend des
Ladevorgangs. Motoren/Adapter/Handoff bleiben byte-identisch.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import importlib.util
import io
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
AUS_TEXT = ROOT / "test" / "run_lab_out.txt"
AUS_TSV = ROOT / "test" / "run_lab_trades.tsv"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")


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


def _lade_fenster(B: Any, start: str, ende: str) -> Any:
    """Fenster [start, ende) ueber den kanonischen BKZ-Loader der Baseline."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _handelstage(B: Any, ende: str, n_benoetigt: int) -> List[str]:
    """Die letzten ``n_benoetigt`` BKZ-Handelstage vor ``ende`` (aufsteigend).

    Bounded: das Lade-Rueckwaertsfenster wird aus ``n_benoetigt`` grob
    kalendarisch geschaetzt (2 x Handelstage + Puffer) -- keine Volllast.
    """
    von = str(date.fromisoformat(ende)
              - timedelta(days=int(n_benoetigt * 2) + 14))
    d = _lade_fenster(B, von, ende)
    tage = np.unique(d["ts"].to_numpy().astype("datetime64[D]"))
    tage = tage[tage < np.datetime64(ende, "D")]
    if len(tage) < n_benoetigt:
        raise SystemExit(
            f"Zu wenig Vorgeschichte: {len(tage)} < {n_benoetigt} "
            f"(Ladefenster ab {von})")
    return [str(t) for t in tage[-n_benoetigt:]]


def _parse_wert(alt: Any, roh: str) -> Any:
    """CLI-String auf den Typ des bestehenden Feldes konvertieren."""
    if isinstance(alt, bool):
        if roh.strip().lower() in ("1", "true", "ja", "yes", "on"):
            return True
        if roh.strip().lower() in ("0", "false", "nein", "no", "off"):
            return False
        raise ValueError(f"Bool-Wert unlesbar: {roh!r}")
    if isinstance(alt, int):
        return int(roh)
    if isinstance(alt, float):
        return float(roh)
    return str(roh)


def _setze_params(cfg: Any, kcfg: Any, paare: List[Tuple[str, str]]
                  ) -> Tuple[Any, Any, List[str]]:
    """Parameter-Overrides auf die passende der beiden Configs anwenden."""
    b_felder = {f.name: f for f in dataclasses.fields(cfg)}
    v_felder = {f.name: f for f in dataclasses.fields(kcfg)}
    log: List[str] = []
    for name, roh in paare:
        if name in b_felder:
            cfg = dataclasses.replace(
                cfg, **{name: _parse_wert(getattr(cfg, name), roh)})
            log.append(f"Baseline.{name} = {getattr(cfg, name)!r}")
        elif name in v_felder:
            kcfg = dataclasses.replace(
                kcfg, **{name: _parse_wert(getattr(kcfg, name), roh)})
            log.append(f"V020.{name} = {getattr(kcfg, name)!r}")
        else:
            raise KeyError(
                f"Unbekanntes Parameterfeld {name!r}. "
                f"Baseline: {sorted(b_felder)} | V020: {sorted(v_felder)}")
    return cfg, kcfg, log


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Universeller Modus-A-Runner (read-only Labor)")
    ap.add_argument("--start", required=True, help="BKZ-Start (YYYY-MM-DD)")
    ap.add_argument("--end", required=True, help="BKZ-Ende exklusiv")
    ap.add_argument("--box-end", default=None,
                    help="BKZ-Kalendergrenze der H1-Box (Default: --end)")
    ap.add_argument("--warmup-tage", type=int, default=0,
                    help="N BKZ-Handelstage Vorlauf (nur Kanten, nicht Trades)")
    ap.add_argument("--param", action="append", default=[],
                    metavar="FELD=WERT", help="Config-Override (mehrfach)")
    ap.add_argument("--out", default=str(AUS_TEXT))
    ap.add_argument("--trades-tsv", default=str(AUS_TSV))
    ap.add_argument("--json", default=None,
                    help="optionaler JSON-Kurzbericht (maschinenlesbar)")
    args = ap.parse_args()

    t_ges = time.perf_counter()
    assert _sha(BASELINE_PFAD) == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(V020_PFAD) == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ADAPTER_PFAD) == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"

    B = _load("basis_lab", BASELINE_PFAD)
    V = _load("v020_lab", V020_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = V.V020KantenKonfiguration()

    paare: List[Tuple[str, str]] = []
    for s in args.param:
        if "=" not in s:
            raise ValueError(f"--param erwartet FELD=WERT, bekam {s!r}")
        k, v = s.split("=", 1)
        paare.append((k.strip(), v.strip()))
    cfg, kcfg, param_log = _setze_params(cfg, kcfg, paare)

    # --- Warm-up-Vorlauf kalendarisch bestimmen ----------------------------
    start_soll = str(args.start)
    if args.warmup_tage > 0:
        ht = _handelstage(B, start_soll, args.warmup_tage)
        start_lade = ht[0]
    else:
        start_lade = start_soll
    ende = str(args.end)

    t0 = time.perf_counter()
    d = _lade_fenster(B, start_lade, ende)
    t_lade = time.perf_counter() - t0
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    n = int(len(d))
    if n == 0:
        raise SystemExit(f"Leeres Fenster [{start_lade}, {ende})")
    i0 = int(np.searchsorted(ts, np.datetime64(start_soll)))
    box_datum = str(args.box_end) if args.box_end else ende
    box_end = int(np.searchsorted(ts, np.datetime64(box_datum)))
    if args.box_end is None:
        box_end = n

    # --- Scan + Modus-A-Trade-Schleife -------------------------------------
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        t1 = time.perf_counter()
        scan = B._se_scan("LAB", cfg)
        t_scan = time.perf_counter() - t1
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(box_end)
    eng = V.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    t2 = time.perf_counter()
    trades, _st = eng._se_trades_v020(scan, cfg)
    trades = list(trades)
    t_trades = time.perf_counter() - t2

    # --- Auswertung (nur Trades ab Analysebeginn i0) -----------------------
    sel = [x for x in trades if int(x.entry_bar) >= i0]
    sel.sort(key=lambda x: (int(x.entry_bar), str(x.richtung)))
    rs = [float(x.r) for x in sel]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    summe = float(sum(rs))
    pf = (sum(pos) / abs(sum(neg))) if neg else float("inf")
    win = (100.0 * len(pos) / len(rs)) if rs else 0.0
    h1 = [x for x in sel if int(x.entry_bar) < box_end]
    h2 = [x for x in sel if int(x.entry_bar) >= box_end]

    def _agg(xs: List[Any]) -> Tuple[int, float]:
        return len(xs), float(sum(float(x.r) for x in xs))

    n_h1, r_h1 = _agg(h1)
    n_h2, r_h2 = _agg(h2)

    # --- Protokoll ---------------------------------------------------------
    z: List[str] = []
    z.append("RUN-LAB (Modus A, read-only) | universeller Zeitraum-Runner")
    z.append("Zeitbasis: BKZ = time AT TIME ZONE 'UTC' (Kanon K1/K4)")
    z.append(f"Analysefenster : {start_soll} .. {ende} (exkl.)")
    z.append(f"Ladefenster    : {start_lade} .. {ende} (exkl.)  "
             f"| Warm-up: {args.warmup_tage} BKZ-Handelstage")
    z.append(f"Box-Grenze     : {box_datum} -> box_end_bar={box_end} "
             f"| i0={i0} | n={n}")
    z.append(f"Modus          : A (hook=None) -- Adapter NICHT importiert")
    z.append(f"Parameter      : {'; '.join(param_log) if param_log else 'Defaults'}")
    z.append(f"SHAs           : Baseline 53f28e1b / V020 e79c5c29 / "
             f"Adapter 770eda2c (nur Guard)")
    z.append("")
    z.append("===== KENNZAHLEN (nur Trades mit entry >= i0) =====")
    z.append(f"  Trades gesamt : {len(sel)}")
    z.append(f"  Summe R       : {summe:+.6f}")
    z.append(f"  Win-Rate      : {win:.2f} %  ({len(pos)} pos / {len(neg)} neg)")
    z.append(f"  Profit-Faktor : {pf:.4f}")
    z.append(f"  H1 (<box_end) : {n_h1} / {r_h1:+.6f}")
    z.append(f"  H2 (>=box_end): {n_h2} / {r_h2:+.6f}")
    z.append("")
    z.append("===== KANTENZUSTAND (global, fensterabhaengig) =====")
    z.append(f"  edges={len(scan['edges'])} seeds={len(scan['seeds'])} "
             f"r21={len(scan.get('r21_geloescht', []))} "
             f"tomb={len(scan.get('tombstones', []))} "
             f"warA={len(B.WAR_AUSSEN_IDS)}")
    z.append("")
    z.append("===== TRADES =====")
    z.append(f"{'#':>3s} {'KID':>4s} {'Richt':5s} {'entry_rel':>9s} "
             f"{'entry_ts':19s} {'SL':>9s} {'TP2':>9s} {'exit1':>6s} "
             f"{'exit2':>6s} {'stufe':18s} {'R':>10s}")
    for i, x in enumerate(sel, 1):
        eb = int(x.entry_bar)
        z.append(
            f"{i:3d} {int(x.kid):4d} {str(x.richtung):5s} {eb - i0:9d} "
            f"{str(ts[eb])[:19]:19s} {float(x.sl):9.4f} {float(x.tp2):9.4f} "
            f"{int(x.exit1_bar) - i0:6d} {int(x.exit2_bar) - i0:6d} "
            f"{str(x.stufe):18s} {float(x.r):+10.6f}")
    z.append("")
    z.append(f"Laufzeit: lade {t_lade:.1f}s | scan {t_scan:.1f}s | "
             f"trades {t_trades:.1f}s | gesamt {time.perf_counter() - t_ges:.1f}s")
    z.append("HINWEIS (H20.47): basis = mean(alle Dochte) -> nicht stationaer; "
             "Ergebnisse sind fensterabhaengig.")

    Path(args.out).write_text("\n".join(z) + "\n", encoding="utf-8",
                              newline="\n")

    # --- Trade-TSV (maschinenlesbar) ---------------------------------------
    tsv = ["kid\trichtung\tentry_rel\tentry_ts\tsl\ttp2\texit1_rel\t"
           "exit2_rel\tstufe\tr"]
    for x in sel:
        eb = int(x.entry_bar)
        tsv.append(f"{int(x.kid)}\t{x.richtung}\t{eb - i0}\t{ts[eb]}\t"
                   f"{float(x.sl):.4f}\t{float(x.tp2):.4f}\t"
                   f"{int(x.exit1_bar) - i0}\t{int(x.exit2_bar) - i0}\t"
                   f"{x.stufe}\t{float(x.r):.6f}")
    Path(args.trades_tsv).write_text("\n".join(tsv) + "\n", encoding="utf-8",
                                     newline="\n")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "start": start_soll, "end": ende, "start_lade": start_lade,
            "warmup_tage": args.warmup_tage, "box_datum": box_datum,
            "box_end_bar": box_end, "i0": i0, "n": n,
            "parameter": param_log, "trades": len(sel),
            "summe_r": round(summe, 6), "win_rate_pct": round(win, 2),
            "profit_faktor": (None if pf == float("inf") else round(pf, 4)),
            "h1_n": n_h1, "h1_r": round(r_h1, 6),
            "h2_n": n_h2, "h2_r": round(r_h2, 6),
            "edges": len(scan["edges"]), "seeds": len(scan["seeds"]),
            "r21": len(scan.get("r21_geloescht", [])),
            "tomb": len(scan.get("tombstones", [])),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for zl in z:
        print(zl)
    print(f"\nText   -> {args.out}")
    print(f"Trades -> {args.trades_tsv}")


if __name__ == "__main__":
    main()
