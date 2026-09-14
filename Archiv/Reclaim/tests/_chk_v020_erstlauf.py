# -*- coding: utf-8 -*-
"""READ-ONLY Beobachtungslauf: V020-Kanten-Engine (Stufe B) gegen AUG.

Beobachtend, KEIN R-Pin, KEINE Baseline-Mutation. Der Motor mutiert
Kantenobjekte -> je Modus eine eigene deepcopy.

Modi:  A  = hook=None, wertedomaene=None            (V020-Regeln pur)
       A2 = hook=None, wertedomaene=ADAPTER_KAUSAL  (isoliert Override)
       B  = hook=ADAPTER_KAUSAL, wertedomaene=...   (voller DI-Betrieb)

Referenzlinien (KEINE Ziele, NICHT identisch zu V020):
  V0 nativ            14 Trades / +42.450970 R  (globales Q29, rohe Basis)
  V1_kausal           23 Trades / +85.577150 R  (ZP-4/ZP-5 + P9-Override)

Verifikation: SHA-Guards auf V020 e79c5c29, Baseline 53f28e1b, Adapter
770eda2c. Keine operativen Dateien werden geschrieben.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
PROTOKOLL = ROOT / "test" / "_chk_v020_erstlauf_out.txt"

V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")
FENSTER = "AUG"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
    return mod


def _rand_quellen(v020: Any, edges: List[Any], kidx: Dict[int, Any],
                  hook: Any, n: int) -> Dict[str, int]:
    """Read-only Nebenprobe: Verteilung der Marktrand-Quellen je Bar."""
    eng = v020.V020KantenEngine(hook=hook, wertedomaene=None,
                                cfg=v020.V020KantenKonfiguration())
    z: Dict[str, int] = {}
    for k in range(2, n - 3):
        refs = eng._referenzen(edges, k)
        r = eng._marktrand([refs[int(e.kid)] for e in edges], k, kidx)
        key = r.quelle if r is not None else "undefiniert"
        z[key] = z.get(key, 0) + 1
    return z


def _lauf(v020: Any, scan: Dict[str, Any], bcfg: Any, label: str,
          hook: Optional[Any], wd: Optional[Any], box_nativ: int) -> None:
    eng = v020.V020KantenEngine(hook=hook, wertedomaene=wd,
                                cfg=v020.V020KantenKonfiguration())
    sc = copy.deepcopy(scan)                      # M1: Mutationsschutz
    setups, st = eng._se_trades_v020(sc, bcfg)
    r_sum = sum(t.r for t in setups)
    h1 = [t for t in setups if t.entry_bar < box_nativ]
    h2 = [t for t in setups if t.entry_bar >= box_nativ]
    nl = sum(1 for t in setups if t.richtung == "LONG")
    ns = sum(1 for t in setups if t.richtung == "SHORT")
    print(f"--- Modus {label} ---")
    print(f"  Trades {len(setups):3d} / R {r_sum:+12.6f}")
    print(f"  H1 {len(h1):2d}/{sum(t.r for t in h1):+10.6f} | "
          f"H2 {len(h2):2d}/{sum(t.r for t in h2):+10.6f}")
    print(f"  LONG {nl:2d}/{sum(t.r for t in setups if t.richtung == 'LONG'):+10.6f} | "
          f"SHORT {ns:2d}/{sum(t.r for t in setups if t.richtung == 'SHORT'):+10.6f}")
    print(f"  quartil_undefiniert {st['quartil_undefiniert']:4d} | "
          f"quartil_blockiert {st['quartil_blockiert']:4d} | "
          f"blocker {st['blocker']:4d} | kein_raum {st['kein_raum']:4d} | "
          f"kein_gegner {st['kein_gegner']:3d} | zyklus {st['zyklus_blockiert']:3d} | "
          f"f3 {st['f3']:3d} | frisch {st['frisch_blockiert']:3d} | "
          f"conc {st['concurrency_blockiert']:3d}")
    for t in sorted(setups, key=lambda x: (x.entry_bar, x.kid)):
        print(f"    bar {t.bar:5d} entry {t.entry_bar:5d} K{t.kid:<3d} "
              f"{t.richtung:5s} {t.r:+10.6f}")


def main() -> None:
    for p, soll in ((V020_PFAD, V020_SHA_SOLL),
                    (BASELINE_PFAD, BASELINE_SHA_SOLL),
                    (ADAPTER_PFAD, ADAPTER_SHA_SOLL)):
        ist = _sha(p)
        assert ist == soll, (p.name, ist, soll)
    print("SHA-Guards OK: V020 e79c5c29 / Baseline 53f28e1b / Adapter 770eda2c")

    v020 = _load("v020_erstlauf", V020_PFAD)
    from backtest_lab.phasen_regime_adapter import (  # noqa: E402
        ADAPTER_V019_KAUSAL)
    B = v020.baseline()
    bcfg = B.StraightEdgeHarnessKonfiguration()
    scan = B._se_scan(FENSTER, bcfg)
    n = int(scan["n"])
    box_nativ = int(scan["box_end_bar"])
    scan["box_end_bar"] = n                       # Voll-Lauf (Konvention)
    edges = list(scan["edges"])
    kidx = {int(e.kid): e for e in edges}
    print(f"FENSTER {FENSTER} n={n} box_end_nativ={box_nativ} "
          f"edges={len(edges)} seeds={len(scan['seeds'])} "
          f"adapter_segmente={len(ADAPTER_V019_KAUSAL.segmente)}")

    for label, hook, wd in (("A", None, None),
                            ("A2", None, ADAPTER_V019_KAUSAL),
                            ("B", ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL)):
        _lauf(v020, scan, bcfg, label, hook, wd, box_nativ)

    for label, hook in (("A", None), ("B", ADAPTER_V019_KAUSAL)):
        print(f"Randquellen {label}: "
              f"{_rand_quellen(v020, edges, kidx, hook, n)}")


class _Tee:
    """Spiegelt die Ausgabe auf Terminal und Protokolldatei."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.buf: List[str] = []

    def write(self, s: str) -> int:
        self.buf.append(s)
        return self._real.write(s)

    def flush(self) -> None:
        self._real.flush()


if __name__ == "__main__":
    _real = sys.stdout
    _tee = _Tee(_real)
    sys.stdout = _tee  # type: ignore[assignment]
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        traceback.print_exc()
        print(f"ABBRUCH: {type(exc).__name__}: {exc}")
    finally:
        sys.stdout = _real
        PROTOKOLL.write_text("".join(_tee.buf), encoding="utf-8")
        print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)"
              f"  Fehler={_fehler}")
