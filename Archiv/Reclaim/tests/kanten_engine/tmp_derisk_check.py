"""READ-ONLY: Ist die De-Risk-Semantik (F2/Q11) ein Ersatz fuer M0?

Regel F2/Q11: Re-Trigger an derselben Kante nur, wenn KEINE offene Position
besteht ODER die erste Haelfte (TP1) bereits geschlossen ist.

Messung: Basis = zyklus=0 (M0 ersatzlos entfallen, alle Re-Trigger zugelassen).
Danach Post-Filter: Trade an Kante X wird verworfen, wenn der vorherige Trade
derselben Kante noch offen war (entry_bar < exit1_bar des Vorgaengers).

Exit1-Bar = Bar, in dem TP1 (POC-Haelfte) geschlossen wurde -> exakt die
De-Risk-Bedingung. Kein Code-Eingriff.
"""
import dataclasses
import sys
from typing import Dict, List

sys.path.insert(0, 'test')
import tmp_kanten_engine_replay as H  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
FENSTER = ["AUG", "S1", "S2"]


def lauf(fenster: str, zyklus: int):
    cfg = dataclasses.replace(H.StraightEdgeHarnessKonfiguration(),
                              retest_zyklus_bars=zyklus)
    scan = H._se_scan(fenster, cfg)
    setups, stats = H._se_trades(scan, cfg)
    return setups, stats


def de_risk_filter(setups: List) -> List:
    """F2/Q11: verwirft Re-Trigger, solange der Vorgaenger an derselben
    Kante noch im Vollrisiko war (entry < exit1_bar des Vorgaengers)."""
    behalten: List = []
    letzter: Dict[int, object] = {}
    for x in sorted(setups, key=lambda y: y.entry_bar):
        vor = letzter.get(x.kid)
        if vor is not None and x.entry_bar < vor.exit1_bar:
            continue                      # Vorgaenger noch nicht de-risked
        behalten.append(x)
        letzter[x.kid] = x
    return behalten


def kenn(lst: List) -> str:
    if not lst:
        return "n=0"
    pos = sum(x.r for x in lst if x.r > 0)
    neg = -sum(x.r for x in lst if x.r < 0)
    pfv = (float('inf') if neg == 0 and pos > 0 else
           (pos / neg if neg > 0 else 0.0))
    pf_txt = "inf" if pfv == float('inf') else f"{pfv:.2f}"
    return (f"n={len(lst):3d} SummeR={sum(x.r for x in lst):+8.2f} "
            f"GEW={sum(1 for x in lst if x.r > 0):3d} "
            f"VERL={sum(1 for x in lst if x.r < 0):3d} PF={pf_txt}")


for fenster in FENSTER:
    print("=" * 100)
    print(f"FENSTER {fenster}")
    print("=" * 100)
    for zyklus in (24, 0):
        setups, _st = lauf(fenster, zyklus)
        dr = de_risk_filter(setups)
        print(f"\n  zyklus={zyklus:3d}  IST             : {kenn(setups)}")
        print(f"  zyklus={zyklus:3d}  + De-Risk-Filter: {kenn(dr)}")
        verworfen = [x for x in sorted(setups, key=lambda y: y.entry_bar)
                     if x not in dr]
        for x in verworfen:
            vor = [y for y in setups if y.kid == x.kid
                   and y.entry_bar < x.entry_bar]
            vor = max(vor, key=lambda y: y.entry_bar) if vor else None
            print(f"      VERWORFEN {x.richtung:5s} entry {x.entry_bar:5d} "
                  f"K{x.kid:<4d} R={x.r:+6.2f} | Vorgaenger entry "
                  f"{vor.entry_bar} exit1(TP1) {vor.exit1_bar}"
                  if vor else f"      VERWORFEN {x.entry_bar}")

    # Konkrete AUG-Frage: Trade 245 unter De-Risk?
    if fenster == "AUG":
        setups0, _ = lauf(fenster, 0)
        t231 = next((x for x in setups0 if x.entry_bar == 231), None)
        t245 = next((x for x in setups0 if x.entry_bar == 245), None)
        print("\n  Detail AUG:")
        if t231 and t245:
            print(f"    Trade 231: exit1(TP1)={t231.exit1_bar} "
                  f"exit2(TP2)={t231.exit2_bar} R={t231.r:+.2f}")
            print(f"    Trade 245: entry={t245.entry_bar} R={t245.r:+.2f}")
            print(f"    -> 245 {'ERLAUBT' if t245.entry_bar >= t231.exit1_bar else 'GESPERRT'}"
                  f" (De-Risk-Bedingung entry >= exit1)")
