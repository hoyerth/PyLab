# -*- coding: utf-8 -*-
"""V021-Verifikation -- gezielte Einzelpruefungen (keine Regressionstests).

Prueft die drei Pfade und die Fail-Loud-Garantien der additiven Engine
``test/tmp_kanten_engine_v021_replay.py``:

1. LEGACY  -> Baseline bit-identisch (V0 VOLL 14/+42.450970).
2. TRIPEL  -> V020 bit-exakt (AUG BOX 14/+27.327383).
3. SEGMENTWAND -> adapterfreie Messung (kein arretierter Sollwert).
4. Fail-Loud: "AN" ohne Grenzen, "AUS" mit Grenzen, Tripel-Teilbelegung.
5. Read-only: der Master-Scan bleibt nach allen Laeufen unberuehrt.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import importlib  # noqa: E402

V = importlib.import_module("tmp_kanten_engine_v021_replay")
BOX = 644
SOLL_V0 = (14, +42.450970, 8, +38.919584, 6, +3.531386)
SOLL_V020_BOX = (14, +27.327383)


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _ber(tr: Sequence[Any], box: int = BOX) -> Tuple[int, float,
                                                     int, float, int, float]:
    h1 = [float(t.r) for t in tr if int(t.entry_bar) < box]
    h2 = [float(t.r) for t in tr if int(t.entry_bar) >= box]
    return (len(tr), sum(float(t.r) for t in tr),
            len(h1), sum(h1), len(h2), sum(h2))


def _fmt(tr: Sequence[Any]) -> str:
    return ", ".join(f"K{int(t.kid)}@{int(t.entry_bar)}({float(t.r):+.1f})"
                     for t in tr)


def main() -> None:
    B = V._engine()
    ad = importlib.import_module("backtest_lab.phasen_regime_adapter")
    PhK = ad.PhasenKanteInfo

    def grenzen(adapter: Any) -> List[V.Segmentgrenze]:
        return [V.Segmentgrenze(start_bar=int(s.start_bar),
                                end_bar=int(s.end_bar),
                                boden=PhK(kid=int(s.boden.kid),
                                          provenienz_basis=float(
                                              s.boden.provenienz_basis)),
                                decke=PhK(kid=int(s.decke.kid),
                                          provenienz_basis=float(
                                              s.decke.provenienz_basis)),
                                boden_deklariert_literal=(
                                    s.boden_deklariert_literal))
                for s in adapter.segmente]

    scan = B._se_scan("AUG", B.StraightEdgeHarnessKonfiguration())
    assert int(scan["box_end_bar"]) == BOX
    kanten_vor = len(scan["edges"]) + len(scan["seeds"])
    wicks_vor = sum(len(e.wicks)
                    for e in list(scan["edges"]) + list(scan["seeds"]))
    print(f"Scan: n={scan['n']} box={scan['box_end_bar']} "
          f"Kanten={kanten_vor} Wicks={wicks_vor}")
    print("=" * 94)

    # ---------------------------------------------------- 1) LEGACY
    cfg = V.V021KantenKonfiguration()
    assert cfg.ist_legacy
    tr = V._lauf(scan, cfg, box_end=int(scan["n"]))
    n, r, n1, r1, n2, r2 = _ber(tr)
    ok1 = (n, round(r, 6), n1, round(r1, 6), n2, round(r2, 6)) == (
        SOLL_V0[0], SOLL_V0[1], SOLL_V0[2], SOLL_V0[3], SOLL_V0[4],
        SOLL_V0[5])
    print(f"1) LEGACY      n={n:3d} R={r:+11.6f} | H1 {n1}/{r1:+10.6f} | "
          f"H2 {n2}/{r2:+10.6f} | {'OK' if ok1 else 'ABWEICHUNG'}")

    # ---------------------------------------------------- 2) TRIPEL
    cfg_t = V.V021KantenKonfiguration(existenz_modus="NATIV",
                                      m6l_modus="DORMANT_PERMISSIV",
                                      rand_modus="ENDOGEN")
    assert cfg_t.ist_tripel and not cfg_t.hat_tripel_teilbelegung
    tr_t = V._lauf(scan, cfg_t)                      # BOX (box_end = 644)
    nt, rt = len(tr_t), sum(float(t.r) for t in tr_t)
    ok2 = (nt == SOLL_V020_BOX[0] and abs(rt - SOLL_V020_BOX[1]) < 1e-4)
    print(f"2) TRIPEL(BOX) n={nt:3d} R={rt:+11.6f} | soll="
          f"{SOLL_V020_BOX} | {'OK' if ok2 else 'ABWEICHUNG'}")

    # ---------------------------------------------------- 3) SEGMENTWAND
    kausal_g = grenzen(ad.ADAPTER_V019_KAUSAL)
    batch_g = grenzen(ad.ADAPTER_V019)
    print(f"   Grenzen: Batch {[(g.start_bar, g.end_bar) for g in batch_g]}")
    print(f"            Kausal {[(g.start_bar, g.end_bar) for g in kausal_g]}")
    cfg_s = V.V021KantenKonfiguration(segmentwand_modus="AN")
    for nm, gl in (("AN/Batch", batch_g), ("AN/Kausal", kausal_g)):
        tr_s = V._lauf(scan, cfg_s, gl, box_end=int(scan["n"]))
        n, r, n1, r1, n2, r2 = _ber(tr_s)
        print(f"3) SEGMENTWAND {nm:9s} n={n:3d} R={r:+11.6f} | "
              f"H1 {n1}/{r1:+10.6f} | H2 {n2}/{r2:+10.6f}   (adapterfrei)")
    tr_aus = V._lauf(scan, V.V021KantenKonfiguration(),
                     box_end=int(scan["n"]))
    n, r = len(tr_aus), sum(float(t.r) for t in tr_aus)
    print(f"   Vergleich AUS (Legacy): n={n} R={r:+.6f}")
    print(f"   H1-Invarianz AN vs AUS: "
          f"{'OK' if _ber(tr_aus)[2:4] == _ber(tr_s)[2:4] else 'VERLETZT'}")

    # ---------------------------------------------------- 4) FAIL-LOUD
    print("=" * 94)
    faelle = (
        ("AN ohne Grenzen       ",
         lambda: V._se_trades_v021(copy.deepcopy(scan),
                                   V.V021KantenKonfiguration(
                                       segmentwand_modus="AN"))),
        ("AUS mit Grenzen       ",
         lambda: V._se_trades_v021(copy.deepcopy(scan),
                                   V.V021KantenKonfiguration(),
                                   batch_g)),
        ("Tripel-Teilbelegung   ",
         lambda: V._se_trades_v021(
             copy.deepcopy(scan),
             V.V021KantenKonfiguration(existenz_modus="NATIV"))),
        ("atr_periode=0         ",
         lambda: V.V021KantenKonfiguration(atr_periode=0)),
        ("ueberdehnung_seg=0.0  ",
         lambda: V.V021KantenKonfiguration(ueberdehnung_segment_pct=0.0)),
    )
    ok4 = True
    for nm, fn in faelle:
        try:
            fn()
            print(f"4) {nm} -> KEIN Fehler (VERLETZT)")
            ok4 = False
        except ValueError as ex:
            print(f"4) {nm} -> ValueError: {str(ex)[:58]}...")
        except Exception as ex:  # noqa: BLE001
            print(f"4) {nm} -> {type(ex).__name__} (VERLETZT)")
            ok4 = False

    # ---------------------------------------------------- 5) READ-ONLY
    print("=" * 94)
    kanten_nach = len(scan["edges"]) + len(scan["seeds"])
    wicks_nach = sum(len(e.wicks)
                     for e in list(scan["edges"]) + list(scan["seeds"]))
    ok5 = (kanten_vor, wicks_vor) == (kanten_nach, wicks_nach)
    print(f"5) Read-only Master-Scan: Kanten {kanten_vor}->{kanten_nach} | "
          f"Wicks {wicks_vor}->{wicks_nach} | "
          f"{'OK (unberuehrt)' if ok5 else 'MUTIERT'}")

    # Idempotenz: zweimal derselbe Lauf -> identisches Ergebnis
    a = V._lauf(scan, cfg_s, kausal_g, box_end=int(scan["n"]))
    b = V._lauf(scan, cfg_s, kausal_g, box_end=int(scan["n"]))
    ok6 = (_fmt(a) == _fmt(b))
    print(f"6) Idempotenz (2x gleicher Lauf): "
          f"{'OK (bit-identisch)' if ok6 else 'ABWEICHUNG'}")

    print("=" * 94)
    print(f"TRADES LEGACY: {_fmt(tr)}")
    print(f"TRADES AN/Kausal: {_fmt(a)}")
    print(f"GESAMT: {'ALLE PRUEFUNGEN OK' if (ok1 and ok2 and ok4 and ok5 and ok6) else 'ABWEICHUNGEN -- siehe oben'}")


if __name__ == "__main__":
    main()
