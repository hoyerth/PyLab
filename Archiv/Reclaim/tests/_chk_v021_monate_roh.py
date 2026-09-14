# -*- coding: utf-8 -*-
"""Rohdaten-Vorschau MAI/JUN/JUL auf dem V021-Stand (read-only).

Dient der Spezifikation des Monats-Renderers: WAS wird auf den Bildern
tatsaechlich zu sehen sein? Zwei Laeufe je Monat, gleiche Fenster wie
``test/_render_mai_jun_jul.py`` (Vollauf ``box_end_bar = n``):

* ``DEFAULT`` -- reine V021-Defaults. Konstruktionsbedingt der LEGACY-Pfad
  (``cfg.ist_legacy`` -> direkter Aufruf der arretierten Baseline).
* ``TRIPEL``  -- NATIV + DORMANT_PERMISSIV + ENDOGEN (V020-Reproduktion).

Der Ordner ``backtest_lab`` enthaelt KEINE Segmentgrenzen fuer MAI/JUN/JUL
(``ADAPTER_V019*`` traegt ausschliesslich die drei AUG-Segmente
848..1287). ``segmentwand_modus="AN"`` ist dort fail-loud unmoeglich.

Kennzahlen je Lauf: Trades, SumR, Anteil der Fensterrand-Glattstellung
(ENDE) am SumR, SL-Treffer, Risiko-Nenner min/median/max (U4-Beleg),
Top-Trades nach R.

Keine Mutation. Motoren/Adapter byte-identisch (SHA-Guard).

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_v021_monate_roh.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import io
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

V = importlib.import_module("tmp_kanten_engine_v021_replay")

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

MONATE: Tuple[Tuple[str, str, str, str], ...] = (
    ("MAI", "2026-05-01", "2026-06-01", "2026-05-29"),
    ("JUN", "2026-06-01", "2026-07-01", "2026-06-30"),
    ("JUL", "2026-07-01", "2026-08-01", "2026-07-31"),
)
SOLL_LEGACY: Dict[str, Tuple[int, float]] = {
    "MAI": (35, +38.318126), "JUN": (28, -11.421155), "JUL": (21, -4.325355)}
SOLL_TRIPEL: Dict[str, Tuple[int, float]] = {
    "MAI": (58, +40.023743), "JUN": (56, -26.883881), "JUL": (68, -11.395066)}

OUT = ROOT / "test" / "_chk_v021_monate_roh_out.txt"
_Z: List[str] = []


def _z(s: str = "") -> None:
    _Z.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class _StdoutStub:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _lade_fenster_lokal(B: Any, start: str, ende: str) -> Any:
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _monat_scan(B: Any, cfg: Any, start: str, ende: str
                ) -> Tuple[Dict[str, Any], int]:
    d = _lade_fenster_lokal(B, start, ende)
    n = int(len(d))
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", cfg)
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    return scan, n


def _kenngroessen(tr: Sequence[Any]) -> Dict[str, Any]:
    rs = [float(t.r) for t in tr]
    summe = float(sum(rs))
    ende = 0.0
    for t in tr:
        for _r, _g in ((float(t.r1), str(t.grund1)),
                       (float(t.r2), str(t.grund2))):
            if _g == "ENDE":
                ende += 0.5 * _r
    risiko = [abs(float(t.sl) - float(t.entry)) for t in tr]
    risiko_s = sorted(risiko)
    n_sl = sum(1 for t in tr
               if str(t.grund1) == "SL" or str(t.grund2) == "SL")
    n_ende_voll = sum(1 for t in tr
                      if str(t.grund1) == "ENDE" and str(t.grund2) == "ENDE")
    top = sorted(tr, key=lambda t: float(t.r), reverse=True)[:3]
    return {
        "n": len(tr), "sum": summe, "ende": ende,
        "mark": summe - ende, "n_sl": n_sl, "n_ende_voll": n_ende_voll,
        "rmin": min(risiko_s), "rmed": risiko_s[len(risiko_s) // 2],
        "rmax": max(risiko_s), "top": top,
        "n_risk_klein": sum(1 for x in risiko if x < 0.10),
    }


def main() -> None:
    _z("ROHDATEN-VORSCHAU MAI/JUN/JUL auf V021 (Vollauf, BKZ, ohne Offset)")
    _z("=" * 100)
    for p, soll, nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                        (ADAPTER_PFAD, ADAPTER_SHA, "Adapter")):
        ist = _sha(p)
        assert ist == soll, f"Fremdstand {nm}: {ist[:16]}"
        _z(f"SHA {nm:9s} {ist[:16]}...  OK")

    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    _z(f"Adapter-Segmente: {len(ad.ADAPTER_V019.segmente)} "
       f"(AUG: {[(int(s.start_bar), int(s.end_bar)) for s in ad.ADAPTER_V019.segmente]})")
    _z("-> fuer MAI/JUN/JUL existieren KEINE Segmentgrenzen; "
       "segmentwand_modus")
    _z("   ist dort fail-loud nicht auf 'AN' setzbar (ValueError).")
    _z("")

    B = V._engine()
    cfg_h = B.StraightEdgeHarnessKonfiguration()
    cfg_def = V.V021KantenKonfiguration()
    cfg_tri = V.V021KantenKonfiguration(existenz_modus="NATIV",
                                        m6l_modus="DORMANT_PERMISSIV",
                                        rand_modus="ENDOGEN")
    assert cfg_def.ist_legacy and cfg_tri.ist_tripel

    for lab, start, ende, endtag in MONATE:
        scan, n = _monat_scan(B, cfg_h, start, ende)
        ts = scan["d"]["ts"].to_numpy().astype("datetime64[ns]")
        _z("=" * 100)
        _z(f"{lab}  {start} .. {endtag}   Bars 0..{n - 1} (n={n})   "
           f"edges={len(scan['edges'])} seeds={len(scan['seeds'])}   "
           f"wall_live_bars={cfg_h.wall_live_bars} "
           f"touch_band={cfg_h.touch_band_pct} "
           f"min_touches={cfg_h.min_touches_handelbar}")
        for nm, cfg, soll in (("DEFAULT (Legacy)", cfg_def, SOLL_LEGACY[lab]),
                              ("TRIPEL (V020)", cfg_tri, SOLL_TRIPEL[lab])):
            tr = V._lauf(copy.deepcopy(scan), cfg)
            k = _kenngroessen(tr)
            ok = (k["n"] == soll[0]
                  and abs(k["sum"] - round(soll[1], 6)) < 1e-6)
            _z("")
            _z(f"  {nm}   SOLL {soll[0]}/{soll[1]:+.6f}   "
               f"{'OK bit-exakt' if ok else 'ABWEICHUNG'}")
            _z(f"    Trades {k['n']:3d}   SumR {k['sum']:+10.6f}   "
               f"davon markterprobt (TP1/TP2/SL) {k['mark']:+10.6f}   "
               f"Fensterrand ENDE {k['ende']:+10.6f} "
               f"({100.0 * k['ende'] / k['sum'] if k['sum'] else 0.0:+.1f} %)")
            _z(f"    SL-getroffen {k['n_sl']:3d} von {k['n']}   "
               f"|   beide Halften ENDE {k['n_ende_voll']:3d}")
            _z(f"    Risiko |sl-entry| USD:  min {k['rmin']:.4f}   "
               f"median {k['rmed']:.4f}   max {k['rmax']:.4f}   "
               f"|   Nenner < 0.10 USD: {k['n_risk_klein']}")
            _z("    Top-3 nach R:")
            for t in k["top"]:
                _z(f"      K{int(t.kid):<4d} {str(t.richtung):5s} sig "
                   f"{int(t.bar):>5d} entry {int(t.entry_bar):>5d} "
                   f"@ {float(t.entry):.4f} ris {abs(float(t.sl) - float(t.entry)):.4f} "
                   f"tp2Abstand {abs(float(t.tp2) - float(t.entry)):.4f} "
                   f"R {float(t.r):+9.4f}  "
                   f"[{str(t.grund1)}/{str(t.grund2)}]")
        _z("")

    _z("=" * 100)
    _z("VERTRAGS-DRAHTUNG (statische Inspektion der V021-Engine)")
    _z("  Gezaehlt werden echte LESEZUGRIFFE (cfg.<feld> / self.<feld>),")
    _z("  ohne Deklarationszeilen, Validierung und eigene Docstrings.")
    t = (ROOT / "test" / "tmp_kanten_engine_v021_replay.py").read_text(
        encoding="utf-8")
    felder = ("basis_modus", "gegenkante_modus", "fensterrand_exit",
              "min_risk_usd", "atr_risiko_faktor", "atr_periode",
              "existenz_modus", "m6l_modus", "rand_modus",
              "segmentwand_modus", "scan_readonly",
              "ueberdehnung_segment_pct")
    _z("")
    _z(f"  {'Feld':26s} {'Lesezugriffe':>12s}  Status")
    for f in felder:
        pat = re.compile(r"(?:cfg|self)\." + f + r"\b")
        treffer = [(i + 1, ln.strip()) for i, ln in enumerate(t.splitlines())
                   if pat.search(ln)]
        liest = [x for x in treffer
                 if not re.match(rf"^{f}\s*:", x[1])]
        status = "VERDRAHTET" if liest else "INERT (nur deklariert)"
        _z(f"  {f:26s} {len(liest):>12d}  {status}")
        for nr, ln in liest:
            _z(f"        {nr:4d}  {ln[:96]}")
    _z("")
    _z("  KORREKTUR zur ersten Fassung dieser Sonde: min_risk_usd,")
    _z("  atr_risiko_faktor und atr_periode erschienen dort faelschlich als")
    _z("  'VERDRAHTET' -- gezaehlt wurden Felddeklaration, Validierung und")
    _z("  der Rumpf von risiko_floor() selbst.")
    _z("  risiko_effektiv() hat 0 Aufrufstellen; risiko_floor() wird nur von")
    _z("  risiko_effektiv() gerufen. Beide sind toter Code.")
    _z("  Folge: min_risk_usd/atr_risiko_faktor aendern das Bild NICHT,")
    _z("  solange diese Anbindung fehlt (U4 ist in V021 nicht behoben).")
    _z("")
    _z(f"PROTOKOLL: {OUT}")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        _Z.append(f"\nABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}")
    OUT.write_text("\n".join(_Z) + "\n", encoding="utf-8", newline="\n")
    print(f"\nFehler={_fehler}")
