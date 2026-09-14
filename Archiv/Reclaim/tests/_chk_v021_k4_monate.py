# -*- coding: utf-8 -*-
"""K4 -- Tripel-Probe MAI / JUN / JUL gegen die arretierten Sollwerte.

Auftrag (K4, Freigabe erteilt)
------------------------------
Pruefen, ob der **Tripel-Pfad** der additiven V021-Engine
(``existenz_modus="NATIV"`` + ``m6l_modus="DORMANT_PERMISSIV"`` +
``rand_modus="ENDOGEN"``) die drei arretierten Monatswerte bit-exakt
reproduziert -- dieselben Zahlen, die ``test/_render_mai_jun_jul.py``
(SHA ``930a77daded836d1``) als Erfolgsbedingung fuehrt:

    MAI  58 / +40.023743
    JUN  56 / -26.883881
    JUL  68 / -11.3950657

Warum das kein Selbstlaeufer ist
--------------------------------
Der Monatslauf verlangt zwei Dinge, die der AUG-Pfad nicht braucht:
1. eine laufzeit-gepatchte Fensterquelle (``_lade_fenster`` liefert den
   Monatsschnitt, ``FENSTER["LAB"]`` wird nur temporaer gesetzt), und
2. den Vollauf ``box_end_bar = n`` (Renderer-Konvention L-B) -- NICHT die
   Kalenderkante.
Die V021-Engine kennt beides nicht; die Probe muss es liefern. Damit prueft
K4 genau die Naht: Vertrag -> Delegation -> Fremdfenster.

Kontrollen (fail-loud, jede Abweichung bricht ab)
-------------------------------------------------
* SHA-Guard Basis / V020 / Adapter vor jedem Lauf.
* Sollwert-Vergleich Trades UND SumR (Toleranz 1e-6).
* Gegenprobe LEGACY je Monat (kein Sollwert, nur Protokoll).
* Idempotenz: derselbe Monat zweimal -> gleiche Trade-Signatur.

READ-ONLY. Motoren/Adapter/Renderer/Handoff bleiben byte-identisch.

Aufruf:
    .venv\\Scripts\\python.exe test\\_chk_v021_k4_monate.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import importlib  # noqa: E402

V = importlib.import_module("tmp_kanten_engine_v021_replay")

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
BASELINE_SHA = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

MONATE: Tuple[Tuple[str, str, str, str], ...] = (
    ("MAI", "2026-05-01", "2026-06-01", "2026-05-29"),
    ("JUN", "2026-06-01", "2026-07-01", "2026-06-30"),
    ("JUL", "2026-07-01", "2026-08-01", "2026-07-31"),
)
# Quelle: test/_chk_mai_juli_diag_out.txt, arretiert in _render_mai_jun_jul.py
SOLL: Dict[str, Tuple[int, float]] = {
    "MAI": (58, 40.023743), "JUN": (56, -26.883881), "JUL": (68, -11.3950657)}

OUT = ROOT / "test" / "_chk_v021_k4_monate_out.txt"
_ZEILEN: List[str] = []


def _z(s: str = "") -> None:
    _ZEILEN.append(s)
    print(s)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _assert_shas() -> None:
    for p, soll, nm in ((BASELINE_PFAD, BASELINE_SHA, "Baseline"),
                        (V020_PFAD, V020_SHA, "V020"),
                        (ADAPTER_PFAD, ADAPTER_SHA, "Adapter")):
        ist = _sha(p)
        assert ist == soll, (
            f"Fremdstand {nm}: {p.name} {ist[:16]}... != {soll[:16]}...")
        _z(f"SHA {nm:9s} {ist[:16]}...  OK")


class _StdoutStub:
    """fd-freier stdout-Ersatz (die Basis haengt beim Import stdout um)."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _lade_fenster_lokal(B: Any, start: str, ende: str) -> Any:
    """Monatsschnitt aus der Basis-Fensterquelle (temporaerer LAB-Eintrag)."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _monat_scan(B: Any, cfg: Any, start: str, ende: str
                ) -> Tuple[Dict[str, Any], int, Any]:
    """Scan eines Monatsfensters; ``box_end_bar = n`` (Vollauf)."""
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
    return scan, n, d


def _sig(tr: Sequence[Any]) -> str:
    return "|".join(f"K{int(t.kid)}@{int(t.entry_bar)}({float(t.r):+.6f})"
                    for t in tr)


def main() -> None:
    _z("K4 -- TRIPEL MAI/JUN/JUL (V021-Delegation) gegen arretierte Sollwerte")
    _z("=" * 88)
    _assert_shas()
    _z("")

    B = V._engine()
    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    _ = ad  # Adapter wird nur ueber den SHA-Guard beruehrt (hook=None-Pfad)
    cfg_harness = B.StraightEdgeHarnessKonfiguration()
    cfg_tripel = V.V021KantenKonfiguration(existenz_modus="NATIV",
                                           m6l_modus="DORMANT_PERMISSIV",
                                           rand_modus="ENDOGEN")
    cfg_legacy = V.V021KantenKonfiguration()
    assert cfg_tripel.ist_tripel and not cfg_tripel.hat_tripel_teilbelegung
    assert cfg_legacy.ist_legacy

    _z(f"Vertrag: {'NATIV':6s} + {'DORMANT_PERMISSIV':18s} + {'ENDOGEN':8s} "
       f"-> ist_tripel={cfg_tripel.ist_tripel}")
    _z(f"Fenster: BKZ-Schnitt je Monat, Vollauf box_end_bar = n "
       f"(Renderer-Konvention)")
    _z("")

    alle_ok = True
    for lab, start, ende, endtag in MONATE:
        scan, n, _d = _monat_scan(B, cfg_harness, start, ende)
        ts = scan["d"]["ts"].to_numpy().astype("datetime64[ns]")
        assert str(ts[0])[:10] == start, f"{lab}: Start {ts[0]} != {start}"
        assert int(scan["box_end_bar"]) == n

        tr_t = V._lauf(copy.deepcopy(scan), cfg_tripel)
        tr_l = V._lauf(copy.deepcopy(scan), cfg_legacy)
        r_t = round(float(sum(float(t.r) for t in tr_t)), 6)
        r_l = round(float(sum(float(t.r) for t in tr_l)), 6)
        soll_n, soll_r = SOLL[lab]
        ok_n = len(tr_t) == soll_n
        ok_r = abs(r_t - round(soll_r, 6)) < 1e-6
        ok = bool(ok_n and ok_r)
        alle_ok = alle_ok and ok

        _z(f"----- {lab}  {start} .. {endtag} (BKZ, ohne Offset)  "
           f"Bars 0..{n - 1} | n={n} | edges={len(scan['edges'])} "
           f"seeds={len(scan['seeds'])}")
        _z(f"  TRIPEL  Trades {len(tr_t):3d}  SumR {r_t:+12.6f}   "
           f"SOLL {soll_n:3d} / {soll_r:+12.6f}   "
           f"{'OK bit-exakt' if ok else 'ABWEICHUNG'}")
        _z(f"  LEGACY  Trades {len(tr_l):3d}  SumR {r_l:+12.6f}   "
           f"(ohne Sollwert -- nur Protokoll)")
        _z(f"  Delta Tripel - Legacy: Trades {len(tr_t) - len(tr_l):+d}  "
           f"SumR {r_t - r_l:+.6f}")
        _z(f"  Kids Tripel: "
           f"{', '.join('K' + str(int(t.kid)) for t in tr_t)}")

        tr_t2 = V._lauf(copy.deepcopy(scan), cfg_tripel)
        idem = _sig(tr_t) == _sig(tr_t2)
        _z(f"  Idempotenz (2. Lauf, frischer deepcopy): "
           f"{'OK bit-identisch' if idem else 'ABWEICHUNG'}")
        if not idem:
            alle_ok = False
        _z("")

        if not ok:
            _z(f"  SOLL-ABWEICHUNG {lab}: ist=({len(tr_t)}, {r_t}) "
               f"soll=({soll_n}, {soll_r})")
            raise AssertionError(f"K4 {lab}: Soll nicht reproduziert")

    _z("=" * 88)
    _z(f"K4 GESAMT: {'ALLE DREI MONATE BIT-EXAKT' if alle_ok else 'ABWEICHUNG'}")
    _z(f"K4-Bedeutung: der Tripel-Pfad der V021-Engine ist auf FREMDEN "
       f"Fenstern deckungsgleich")
    _z(f"              mit dem arretierten Modus A (hook=None, V020). "
       f"Die Naht haelt.")
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
        _ZEILEN.append(f"\nABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}")
    OUT.write_text("\n".join(_ZEILEN) + "\n", encoding="utf-8", newline="\n")
    print(f"\nFehler={_fehler}")
