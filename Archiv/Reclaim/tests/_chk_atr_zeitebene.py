# -*- coding: utf-8 -*-
"""READ-ONLY ATR-Zeitebenen-Sonde -- M15 vs. H1 vs. H4 gegen die Stop-Distanzen.

Auftrag (Anwender, 14.09.2026, H20.52 Paragraph 6 / Beschluss F4 + F9)
---------------------------------------------------------------------
"Messen vor Entscheiden": Vor V022 wird NICHT angenommen, dass ein H1-ATR(14)
bindet. Gemessen wird, ob und ab welcher Zeitebene ein kausaler ATR(14) die
reale Stop-Distanz der 84 Baseline-Trades (35 + 28 + 21) erreicht.

Hintergrund: ATR(14) M15 liegt bei 0.22-0.35 USD, die reale Stop-Distanz bei
0.41-0.48 USD. Die Klammer ``0.50 * ATR`` bindet auf M15 daher nie (H20.52
Paragraph 6). Ob H1 oder H4 bindet, ist NICHT gemessen -- diese Sonde
schliesst die Luecke.

Kausalitaet (verbindlich)
-------------------------
Zwei Fallen werden ausdruecklich vermieden:

1. KEINE Zeitzonen-Projektion. Das Bucketing ist INDEX-BASIERT (H1 = je 4
   M15-Bars, H4 = je 16) -- nicht wall-clock-basiert. Damit ist es kanon-sicher
   (K1/K4) und exakt kausal.
2. KEIN Lookahead. Fuer M15-Bar ``i`` wird ausschliesslich der LETZTE
   ABGESCHLOSSENE Bucket verwendet: ``j - 1`` wenn ``i % faktor != faktor-1``,
   sonst ``j`` selbst. Ein noch offener Bucket darf nie eingehen.

Warmup-Bias (Beschluss F17)
---------------------------
ATR(14) H1 braucht 14 H1-Bars = 56 M15-Bars Vorlauf, H4 entsprechend 224.
Zwei Varianten werden NEBENEINANDER ausgewiesen:

    (a) fensterlokal  -- die ATR-Reihe startet am Monatsersten (Kaltstart).
    (b) Ueberhang     -- die ATR-Reihe startet einen Monat frueher; das
                         Fenster wird erst bei der Auswertung beschnitten.

(a) allein waere eine stille Verfaelschung: ein echtes H1/H4-Bar kreuzt
Monatsgrenzen. Der Vergleich (a) - (b) ist der Kausalitaets-Bias.

Grenze der Sonde
----------------
Die Sonde beantwortet "KANN ``k * ATR`` binden", NICHT "SOLL es". Der Wert
darf NIE in die Engine wandern: jede Aenderung am R-Nenner verschiebt den
arretierten MESSSTAND (H20.51 Paragraph 9).

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_atr_zeitebene.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V021_PFAD = ROOT / "test" / "tmp_kanten_engine_v021_replay.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V021_SHA = (
    "cda9e5b189ed4137198795e1547cec00436dffe64222434bb6ec4c448e598e89")

# (Label, Monatsstart, Monatsende exkl., Ueberhang-Start)
MONATE: Tuple[Tuple[str, str, str, str], ...] = (
    ("MAI", "2026-05-01", "2026-06-01", "2026-04-01"),
    ("JUN", "2026-06-01", "2026-07-01", "2026-05-01"),
    ("JUL", "2026-07-01", "2026-08-01", "2026-06-01"),
)
SOLL_TRADES: Dict[str, Tuple[int, float]] = {
    "MAI": (35, 38.318126), "JUN": (28, -11.421155), "JUL": (21, -4.325355)}
# Kreuzprobe der M15-Variante (a) gegen H20.52 Paragraph 6 (F2-Tabelle).
SOLL_ATR_M15_MED: Dict[str, float] = {
    "MAI": 0.3521, "JUN": 0.3054, "JUL": 0.2210}

PERIODE = 14
KLAMMER = (0.50, 1.00)
AUFLOESUNGEN: Tuple[Tuple[str, int], ...] = (("M15", 1), ("H1", 4), ("H4", 16))

OUT = ROOT / "test" / "_chk_atr_zeitebene_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pruefe_anker() -> None:
    for p, soll in ((BASELINE_PFAD, BASELINE_SHA), (V021_PFAD, V021_SHA)):
        ist = _sha(p)
        if ist != soll:
            raise RuntimeError(
                f"Fremdstand {p.name}: {ist[:16]}... != {soll[:16]}...")


def _med(v: np.ndarray) -> str:
    """Median als Text; leere Reihe -> 'n/a' (Warmup kann alles verschlucken)."""
    return f"{float(np.median(v)):.4f}" if len(v) else "n/a"


def _true_range(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray) -> np.ndarray:
    """TR-Reihe (verbatim die Konvention aus ``_chk_u3_spec_beleg``)."""
    n = len(cl)
    tr = np.empty(n, dtype=float)
    tr[0] = hi[0] - lo[0]
    for i in range(1, n):
        tr[i] = max(hi[i] - lo[i], abs(hi[i] - cl[i - 1]),
                    abs(lo[i] - cl[i - 1]))
    return tr


def _wilder_rma(tr: np.ndarray, periode: int) -> np.ndarray:
    """Wilder-Glaettung mit Seed ``mean(tr[1:periode+1])``.

    Identisch zu ``_chk_u3_spec_beleg._atr_wilder`` -- die Kreuzprobe der
    M15-Mediane gegen die F2-Tabelle haengt an genau dieser Konvention.
    ``tr[0]`` geht NICHT in den Seed ein (Index-Konvention des Bestands).
    """
    n = len(tr)
    atr = np.full(n, np.nan, dtype=float)
    if n <= periode:
        return atr
    atr[periode] = float(np.mean(tr[1:periode + 1]))
    for i in range(periode + 1, n):
        atr[i] = (atr[i - 1] * (periode - 1) + tr[i]) / periode
    return atr


def _atr_zeitebene(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray,
                   faktor: int, periode: int) -> np.ndarray:
    """ATR(``periode``) auf Buckets der Breite ``faktor``, M15-aligned.

    Args:
        hi: High der M15-Reihe.
        lo: Low der M15-Reihe.
        cl: Close der M15-Reihe.
        faktor: 1 = M15, 4 = H1, 16 = H4 (index-basiert).
        periode: Wilder-Periode.

    Returns:
        Array in M15-Laenge. ``nan`` solange kein ABGESCHLOSSENER Bucket mit
        gueltigem ATR vorliegt (Warmup -- gezaehlt, nicht verworfen).
    """
    n = len(cl)
    if faktor == 1:
        return _wilder_rma(_true_range(hi, lo, cl), periode)
    nb = (n + faktor - 1) // faktor
    b_hi = np.empty(nb, dtype=float)
    b_lo = np.empty(nb, dtype=float)
    b_cl = np.empty(nb, dtype=float)
    for j in range(nb):
        a = j * faktor
        b = min(a + faktor, n)
        b_hi[j] = float(np.max(hi[a:b]))
        b_lo[j] = float(np.min(lo[a:b]))
        b_cl[j] = float(cl[b - 1])
    btr = np.empty(nb, dtype=float)
    btr[0] = b_hi[0] - b_lo[0]
    for j in range(1, nb):
        btr[j] = max(b_hi[j] - b_lo[j], abs(b_hi[j] - b_cl[j - 1]),
                     abs(b_lo[j] - b_cl[j - 1]))
    atr_b = _wilder_rma(btr, periode)
    out = np.full(n, np.nan, dtype=float)
    for i in range(n):
        j = i // faktor
        # letzter ABGESCHLOSSENER Bucket vor Bar i (kein Lookahead)
        cj = j if (i % faktor == faktor - 1) else j - 1
        if 0 <= cj < nb:
            out[i] = atr_b[cj]
    return out


def _lade_fenster(B: Any, start: str, ende: str) -> Any:
    """Fenster laden (BKZ). ``'LAB'`` lebt nur waehrend des Ladevorgangs."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _monat(B: Any, V: Any, start: str, ende: str
           ) -> Tuple[List[Any], Any]:
    """V021-Baseline-Trades + Rohdaten des Monats (Default-Vertrag)."""
    d = _lade_fenster(B, start, ende)
    n = int(len(d))
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    tr = sorted(V._lauf(scan, V.V021KantenKonfiguration(), box_end=n),
                key=lambda t: int(t.entry_bar))
    return tr, d


def _arrays(d: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (d["ts"].to_numpy().astype("datetime64[ns]"),
            d["high"].to_numpy(dtype=float), d["low"].to_numpy(dtype=float),
            d["close"].to_numpy(dtype=float))


def main() -> None:
    _z("ATR-ZEITEBENEN-SONDE (read-only, keine Handelswirkung)")
    _z("=" * 100)
    _pruefe_anker()
    _z(f"SHA Baseline {BASELINE_SHA[:16]}...  OK")
    _z(f"SHA V021     {V021_SHA[:16]}...  OK")
    _z("")
    _z("Kausalitaet: index-basiertes Bucketing (keine Zeitzonen-Projektion),")
    _z("nur der LETZTE ABGESCHLOSSENE Bucket geht ein. Wilder RMA, Seed =")
    _z("mean(TR[1..14]) -- identisch zu _chk_u3_spec_beleg._atr_wilder.")
    _z("")

    V = importlib.import_module("tmp_kanten_engine_v021_replay")
    B = V._engine()

    ergebnis: Dict[str, Dict[str, Any]] = {}
    for lab, start, ende, vor in MONATE:
        tr, d = _monat(B, V, start, ende)
        soll_n, soll_r = SOLL_TRADES[lab]
        ist_r = round(float(sum(float(t.r) for t in tr)), 6)
        assert (len(tr), ist_r) == (soll_n, round(soll_r, 6)), (
            f"{lab}: Soll ({soll_n}, {soll_r}) != Ist ({len(tr)}, {ist_r})")
        stops = np.array([abs(float(t.sl) - float(t.entry)) for t in tr])
        bars = np.array([int(t.bar) for t in tr], dtype=int)
        ebars = np.array([int(t.entry_bar) for t in tr], dtype=int)

        # --- Variante (b): Ueberhang -----------------------------------
        dv = _lade_fenster(B, vor, ende)
        tsv, hiv, lov, clv = _arrays(dv)
        off = int(np.searchsorted(tsv, np.datetime64(start)))
        assert (len(tsv) - off) == len(d), (
            f"{lab}: Ueberhang-Offset {off} inkonsistent "
            f"({len(tsv)} - {off} != {len(d)})")

        # --- Variante (a): fensterlokal --------------------------------
        _ts_a, hi_a, lo_a, cl_a = _arrays(d)
        if not np.allclose(hi_a, hiv[off:]) or not np.allclose(cl_a, clv[off:]):
            raise RuntimeError(f"{lab}: Ueberhangsfenster nicht deckungsgleich.")

        ergebnis[lab] = {"stop": [float(s) for s in stops]}
        for name, fak in AUFLOESUNGEN:
            atr_a = _atr_zeitebene(hi_a, lo_a, cl_a, fak, PERIODE)
            atr_b = _atr_zeitebene(hiv, lov, clv, fak, PERIODE)[off:]
            for var, atr in (("a", atr_a), ("b", atr_b)):
                fin = atr[np.isfinite(atr)]
                ergebnis[lab][f"{name}_{var}"] = {
                    "bar": [float(atr[b]) for b in bars],
                    "entry": [float(atr[b]) for b in ebars],
                    "alle_med": (float(np.median(fin)) if len(fin)
                                 else float("nan")),
                    "alle_n": int(len(fin)),
                }

        _z(f"===== {lab}  {start} .. {ende} exkl.  |  n={len(d)}  |  "
           f"Trades {len(tr)} / {ist_r:+.6f} R  |  Ueberhang ab {vor} "
           f"(offset {off} Bars) =====")
        _z(f"  Stop |sl-entry| USD:  min {stops.min():.4f}  median "
           f"{float(np.median(stops)):.4f}  max {stops.max():.4f}")
        _z("")
        _z(f"  {'Aufl':>4s} {'Var':>3s} {'ATR@bar med':>12s} "
           f"{'ATR@entry med':>14s} {'ATR min':>9s} {'ATR max':>9s} "
           f"{'nan@bar':>8s} {'k*ATR>Stop 0.50':>16s} {'1.00':>11s}")
        _z("  " + "-" * 96)
        for name, _fak in AUFLOESUNGEN:
            for var in ("a", "b"):
                e = ergebnis[lab][f"{name}_{var}"]
                vb = np.array(e["bar"], dtype=float)
                ve = np.array(e["entry"], dtype=float)
                finb = vb[np.isfinite(vb)]
                finv = ve[np.isfinite(ve)]
                nan_b = int((~np.isfinite(vb)).sum())
                zeile = (f"  {name:>4s} {var:>3s} "
                         f"{_med(finb):>12s} {_med(finv):>14s} "
                         f"{(f'{finb.min():.4f}' if len(finb) else 'n/a'):>9s} "
                         f"{(f'{finb.max():.4f}' if len(finb) else 'n/a'):>9s} "
                         f"{nan_b:>8d} ")
                for k in KLAMMER:
                    tref = sum(1 for a, s in zip(vb, stops)
                               if np.isfinite(a) and k * a > s)
                    zeile += f"{tref:>7d}/{len(stops):<6d} "
                _z(zeile)
        _z("")

        # --- Kreuzprobe M15 (a) gegen die F2-Tabelle -------------------
        # H20.52 Paragraph 6 (F2) misst den Median ueber ALLE gueltigen Bars
        # der Fensterreihe. Der Median an den TRADE-Bars ist eine ANDERE
        # Population (Signal-Bars sind systematisch leicht volatiler) und
        # darf daher NICHT gegen die F2-Zahl gehalten werden. Beide werden
        # getrennt ausgewiesen -- die Konvention selbst ist der Pruefpunkt.
        med_all = float(ergebnis[lab]["M15_a"]["alle_med"])
        v = np.array(ergebnis[lab]["M15_a"]["bar"], dtype=float)
        fin = v[np.isfinite(v)]
        med_bar = float(np.median(fin)) if len(fin) else float("nan")
        soll = SOLL_ATR_M15_MED[lab]
        ok_konv = abs(round(med_all, 4) - soll) <= 0.0002
        _z(f"  KREUZPROBE M15 (a):")
        _z(f"    Median ueber ALLE gueltigen Bars (F2-Population) "
           f"{med_all:.4f} vs. F2-Soll {soll:.4f}  ->  "
           f"{'OK (Konvention bit-identisch)' if ok_konv else 'ABWEICHUNG'}")
        _z(f"    Median an den TRADE-Bars (andere Population): "
           f"{med_bar:.4f}  (n={len(fin)})  -- nicht F2-vergleichbar")
        _z("")

    # ---------------- Vergleich (a) vs (b) ---------------------------------
    _z("=" * 100)
    _z("WARMUP-BIAS: Median-ATR@bar, Variante (a) fensterlokal vs. (b) Ueberhang")
    _z(f"  {'Fenster':>7s} {'Aufl':>4s} {'(a) med':>10s} {'(b) med':>10s} "
       f"{'Delta':>10s} {'Delta %':>9s}")
    _z("  " + "-" * 56)
    for lab, _s, _e, _v in MONATE:
        for name, _fak in AUFLOESUNGEN:
            a = np.array(ergebnis[lab][f"{name}_a"]["bar"], dtype=float)
            b = np.array(ergebnis[lab][f"{name}_b"]["bar"], dtype=float)
            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]
            if not len(a) or not len(b):
                _z(f"  {lab:>7s} {name:>4s} {'n/a':>10s} {'n/a':>10s} "
                   f"{'n/a':>10s} {'n/a':>9s}")
                continue
            ma, mb = float(np.median(a)), float(np.median(b))
            d = mb - ma
            _z(f"  {lab:>7s} {name:>4s} {ma:>10.4f} {mb:>10.4f} {d:>+10.4f} "
               f"{100.0 * d / ma if ma else 0.0:>+8.2f}%")
    _z("")

    # ---------------- Gesamtlage ------------------------------------------
    _z("=" * 100)
    _z("GESAMTLAGE (84 Trades) -- wie oft bindet k*ATR die reale Stop-Distanz?")
    _z(f"  {'Aufl':>4s} {'Var':>3s} {'ATR med':>9s} {'Stop med':>9s} "
       f"{'0.50*ATR med':>13s} {'1.00*ATR med':>13s} "
       f"{'bindet 0.50':>12s} {'bindet 1.00':>12s}")
    _z("  " + "-" * 84)
    for name, _fak in AUFLOESUNGEN:
        for var in ("a", "b"):
            atr: List[float] = []
            stop: List[float] = []
            for lab, _s, _e, _v in MONATE:
                vb = ergebnis[lab][f"{name}_{var}"]["bar"]
                for a, s in zip(vb, ergebnis[lab]["stop"]):
                    if np.isfinite(a):
                        atr.append(float(a))
                        stop.append(float(s))
            if not atr:
                _z(f"  {name:>4s} {var:>3s}   -- keine gueltigen ATR-Werte --")
                continue
            ma = float(np.median(atr))
            ms = float(np.median(stop))
            b05 = sum(1 for a, s in zip(atr, stop) if 0.50 * a > s)
            b10 = sum(1 for a, s in zip(atr, stop) if 1.00 * a > s)
            _z(f"  {name:>4s} {var:>3s} {ma:>9.4f} {ms:>9.4f} "
               f"{0.50 * ma:>13.4f} {1.00 * ma:>13.4f} "
               f"{b05:>6d}/{len(atr):<5d} {b10:>6d}/{len(atr):<5d}")
    _z("")
    _z("LESEHILFE: 'bindet x' zaehlt Trades, bei denen k*ATR die reale")
    _z("Stop-Distanz UEBERSTEIGT. Nur dann wuerde die Klammer wirken. Die")
    _z("Sonde beantwortet 'KANN', nicht 'SOLL' -- kein Wert darf in die Engine.")
    _z("")
    _z(f"PROTOKOLL: {OUT}")

    OUT.write_text("\n".join(_Z) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        OUT.write_text(f"ABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}",
                       encoding="utf-8")
    print(f"\nFehler={_fehler}")
