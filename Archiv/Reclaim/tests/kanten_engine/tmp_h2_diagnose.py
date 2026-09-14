# -*- coding: utf-8 -*-
"""H2-Diagnose (rein lesend): Staffel-Neugeburten in AUG H2 (Bars 644-1288).

Angepasst an die reale _p8-Engine-API:
  * _se_trades(scan, cfg) -> Tuple[List[_SESetup], Dict[str, int]]  (2 Werte)
  * _SESetup-Felder: bar, richtung, kid, entry_bar, r, resultat, exit1_bar
  * scan["n"] existiert; box_end_bar wird gesetzt
  * Import via importlib (test/ ist kein Package)
Keine Schreibzugriffe, kein Engine-Eingriff.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_h2", P)
H2_START: int = 644


@dataclass(frozen=True, slots=True)
class H2KantenBefund:
    kanten_id: int
    seite: str
    geburts_bar: int
    basis_preis: float
    touches_h2: int
    touches_total: int
    war_jemals_aussen: bool
    trades_info: List[str] = field(default_factory=list)
    schlaf_h2: int = 0


def fuehre_h2_diagnose_aus() -> None:
    cfg = engine.StraightEdgeHarnessKonfiguration()
    scan: Dict[str, Any] = engine._se_scan("AUG", cfg)
    n = scan["n"]
    scan["box_end_bar"] = n
    trades, stats = engine._se_trades(scan, cfg)

    edges: List[Any] = scan["edges"]
    seeds: List[Any] = scan["seeds"]
    alle = list(edges) + list(seeds)
    r21_log: List[Tuple[Any, ...]] = scan.get("r21_geloescht") or []
    tombstones: List[Tuple[int, str, float]] = scan.get("tombstones") or []
    war_aussen_ids: Set[int] = set(engine.WAR_AUSSEN_IDS)

    print("=" * 118)
    print(f"H2-DIAGNOSE: BARS {H2_START} BIS {n} (STAFFEL-NEUGEBURTEN) -- AUG")
    print("=" * 118)
    print(f"  Lebende Kanten (edges): {len(edges)} | Seeds: {len(seeds)} | "
          f"Tombstones: {len(tombstones)} | R21-Log: {len(r21_log)}")
    print(f"  Trades gesamt: {len(trades)} | Netto-R "
          f"{sum(t.r for t in trades):+.2f}")
    print("")

    # --- Geburten in H2 (roh, aus dem Scan) --------------------------------
    geb_h2 = [e for e in alle if e.geburts_bar >= H2_START]
    print("-" * 118)
    print(f"A) NEUGEBURTEN AB BAR {H2_START} (roh): {len(geb_h2)}")
    print("-" * 118)
    print(f"  {'K':>4} {'Seite':5s} {'Geburt':>7} {'Pivot':>6} {'Basis':>8} "
          f"{'Touches':>8} {'O1-Aussen':>10} {'Status':>10}")
    for e in sorted(geb_h2, key=lambda x: x.geburts_bar):
        print(f"  {e.kid:>4} {e.seite:5s} {e.geburts_bar:>7} "
              f"{e.erster_pivot_bar:>6} {e.basis:>8.3f} "
              f"{e.touch_anzahl:>8} {str(e.kid in war_aussen_ids):>10} "
              f"{e.status:>10}")

    # --- In H2 geloeschte Kanten / gesperrte Geburten ----------------------
    del_h2 = [r for r in r21_log if r[0] >= H2_START and r[1] >= 0]
    gesp_h2 = [r for r in r21_log if r[0] >= H2_START and r[1] < 0]
    print("")
    print("-" * 118)
    print(f"B) R21-EINGRIFFE IN H2: {len(del_h2)} Loeschungen | "
          f"{len(gesp_h2)} gesperrte Geburten")
    print("-" * 118)
    for r in del_h2:
        print(f"  LOESCHUNG bar {r[0]:4d} K{r[1]:3d} {r[2]:5s} "
              f"basis={r[3]:.3f} pivot={r[4]} alter={r[5]}")
    for r in gesp_h2:
        print(f"  GEBURT GESPERRT bar {r[0]:4d} {r[2]:5s} px={r[3]:.3f}")

    # --- H2-Befunde je lebender Kante --------------------------------------
    h2_befunde: List[H2KantenBefund] = []
    for e in alle:
        touches_h2 = sum(1 for b, _ in e.wicks if b >= H2_START)
        if e.geburts_bar >= H2_START or touches_h2 > 0:
            kanten_trades: List[str] = [
                f"Bar {t.bar} ({t.richtung}) entry={t.entry_bar} "
                f"{t.r:+.2f}R [{t.resultat}]"
                for t in trades
                if t.kid == e.kid and t.bar >= H2_START
            ]
            schlaf_h2 = sum(1 for s, _ in e.schlaf_windows if s >= H2_START)
            h2_befunde.append(H2KantenBefund(
                kanten_id=e.kid, seite=e.seite, geburts_bar=e.geburts_bar,
                basis_preis=round(e.basis, 3), touches_h2=touches_h2,
                touches_total=e.touch_anzahl,
                war_jemals_aussen=(e.kid in war_aussen_ids),
                trades_info=kanten_trades, schlaf_h2=schlaf_h2))
    h2_befunde.sort(key=lambda x: (x.geburts_bar, x.kanten_id))

    print("")
    print("-" * 118)
    print(f"C) H2-RELEVANTE KANTEN (Geburt >= {H2_START} ODER Touch in H2): "
          f"{len(h2_befunde)}")
    print("-" * 118)
    print(f"  {'K':>4} {'Seite':5s} {'Geburt':>7} {'Basis':>8} {'H2-Touch':>9} "
          f"{'Total':>6} {'O1-Aussen':>10} {'SchlafH2':>9}  Trades")
    for b in h2_befunde:
        trade_str = ("; ".join(b.trades_info) if b.trades_info
                     else "keine Trades")
        print(f"  {b.kanten_id:>4} {b.seite:5s} {b.geburts_bar:>7} "
              f"{b.basis_preis:>8.3f} {b.touches_h2:>9} {b.touches_total:>6} "
              f"{str(b.war_jemals_aussen):>10} {b.schlaf_h2:>9}  {trade_str}")

    # --- Staffel-Charakteristik --------------------------------------------
    ob_h2 = [e for e in geb_h2 if e.seite == "OBEN"]
    un_h2 = [e for e in geb_h2 if e.seite == "UNTEN"]
    print("")
    print("-" * 118)
    print("D) STAFFEL-CHARAKTERISTIK (H2)")
    print("-" * 118)
    print(f"  OBEN-Neugeburten : {len(ob_h2)} "
          f"({sorted(e.geburts_bar for e in ob_h2)})")
    print(f"  UNTEN-Neugeburten: {len(un_h2)} "
          f"({sorted(e.geburts_bar for e in un_h2)})")
    if ob_h2:
        print(f"  OBEN-Basis-Spanne : "
              f"{min(e.basis for e in ob_h2):.3f} .. "
              f"{max(e.basis for e in ob_h2):.3f}")
    if un_h2:
        print(f"  UNTEN-Basis-Spanne: "
              f"{min(e.basis for e in un_h2):.3f} .. "
              f"{max(e.basis for e in un_h2):.3f}")
    print(f"  H2-Trades: {[ (t.bar, t.richtung, t.kid, round(t.r,2)) for t in trades if t.bar >= H2_START ]}")
    print(f"  H2-Netto-R: "
          f"{sum(t.r for t in trades if t.bar >= H2_START):+.2f} "
          f"| Box-Netto-R: "
          f"{sum(t.r for t in trades if t.bar < H2_START):+.2f}")


if __name__ == "__main__":
    fuehre_h2_diagnose_aus()
