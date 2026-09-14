"""READ-ONLY Parameter-Reihe retest_zyklus_bars auf S1/S2 (SE-Pfad direkt).

Umgeht den Routing-Blocker in main() (--modus C routet S1/S2 auf Alt-C),
OHNE Code-Eingriff: Aufruf von _se_scan/_se_trades direkt.

BEFUND (ungeloest, wichtig): box_end_bar ist im Harness hart auf 2026-08-19
verdrahtet (Z. 2132). Fuer S1 (ab 2026-02-05) ergibt das eine "Box" von
6,5 Monaten; fuer S2 (2025) liegt das Datum hinter dem Datenende -> box_end = n.
Die S1/S2-Zahlen sind daher NICHT arretierbar (sie messen den falschen
Fensterausschnitt), aber sie zeigen die Sensitivitaet der Zyklus-Sperre.

Aufruf:  python test/tmp_param_reihe_S1S2.py [24 16 15 12 3 0]
Ausgabe: test/tmp_param_reihe_S1S2.txt (inkrementell, flush je Variante)
"""
import dataclasses
import io
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, 'test')
import tmp_kanten_engine_replay as H  # noqa: E402

KANDIDATEN: List[int] = ([int(a) for a in sys.argv[1:]]
                         or [24, 16, 15, 12, 3, 0])
FENSTER: List[str] = ["S1", "S2"]
OUT = 'test/tmp_param_reihe_S1S2.txt'

fh = io.open(OUT, "w", encoding="utf-8")


def w(zeile: str = "") -> None:
    fh.write(zeile + "\n")
    fh.flush()


def pf(setups) -> float:
    pos = sum(s.r for s in setups if s.r > 0)
    neg = -sum(s.r for s in setups if s.r < 0)
    if neg == 0:
        return float('inf') if pos > 0 else 0.0
    return pos / neg


w("=" * 116)
w("PARAMETER-REIHE retest_zyklus_bars auf S1/S2  (SE-Pfad direkt, read-only)")
w(f"Kandidaten: {KANDIDATEN}")
w("ACHTUNG: box_end_bar hart auf 2026-08-19 (Z. 2132) -> S1 'Box' = 6,5 Monate,")
w("         S2 = ganzes Jahr. NICHT arretierbar, reine Sensitivitaets-Diagnose.")
w("=" * 116)

ergebnis: Dict[str, Dict[int, Tuple]] = {}
for fenster in FENSTER:
    ergebnis[fenster] = {}
    scan0 = H._se_scan(fenster, H.StraightEdgeHarnessKonfiguration())
    d = scan0["d"]
    w()
    w("-" * 116)
    w(f"FENSTER {fenster}: Bars {scan0['n']} | box_end_bar {scan0['box_end_bar']} "
      f"| erste {d['ts'].iloc[0]} | letzte {d['ts'].iloc[-1]}")
    w(f"  Loop-Bereich: k in [2, {scan0['box_end_bar'] - 3})")
    w("-" * 116)
    w(f"{'zyklus':>7} {'n':>4} {'SummeR':>10} {'GEW':>4} {'VERL':>5} {'PF':>7} "
      f"{'Zyklus':>7} {'Blocker':>8} {'Quartil':>8} {'keinRaum':>9} "
      f"{'keinGeg':>8} {'F3':>4} {'Gate':>10}")
    for z in KANDIDATEN:
        cfg = dataclasses.replace(H.StraightEdgeHarnessKonfiguration(),
                                  retest_zyklus_bars=z)
        scan = H._se_scan(fenster, cfg)
        s, st = H._se_trades(scan, cfg)
        ergebnis[fenster][z] = (scan, s, st)
        gew = sum(1 for x in s if x.resultat == "GEWONNEN")
        verl = sum(1 for x in s if x.resultat == "VERLOREN")
        p = pf(s)
        sr = sum(x.r for x in s)
        p_txt = "inf" if p == float("inf") else f"{p:.2f}"
        gate = "BESTANDEN" if (p >= 1.30 and sr > 0) else "VERFEHLT"
        w(f"{z:>7} {len(s):>4} {sr:>+10.2f} {gew:>4} {verl:>5} {p_txt:>7} "
          f"{st['zyklus_blockiert']:>7} {st['blocker']:>8} "
          f"{st['quartil_blockiert']:>8} {st['kein_raum']:>9} "
          f"{st['kein_gegner']:>8} {st['f3']:>4} {gate:>10}")

    # Differenz gegen Basis 24
    w()
    w("DIFF gegen Basis 24 (Trades hinzu/entfallen):")
    basis = {(x.entry_bar, x.richtung, x.kid) for x in ergebnis[fenster][24][1]}
    for z in KANDIDATEN:
        if z == 24:
            continue
        cur = {(x.entry_bar, x.richtung, x.kid): x
               for x in ergebnis[fenster][z][1]}
        neu = [v for kk, v in cur.items() if kk not in basis]
        weg = [kk for kk in basis if kk not in cur]
        dr = (sum(x.r for x in ergebnis[fenster][z][1])
              - sum(x.r for x in ergebnis[fenster][24][1]))
        w(f"  24 -> {z:3d}: +{len(neu)} neu, -{len(weg)} entfallen, "
          f"DeltaR {dr:+8.2f}")

    # Kennzahlen je Kante (Konzentrationsrisiko)
    w()
    w("TRADE-VERTEILUNG je Kante (Top 12 nach |SummeR|):")
    _scan, s, st = ergebnis[fenster][24][1], None, None
    s24 = ergebnis[fenster][24][1]
    per: Dict[int, List] = {}
    for x in s24:
        per.setdefault(x.kid, []).append(x)
    for kid, lst in sorted(per.items(),
                           key=lambda kv: -abs(sum(x.r for x in kv[1])))[:12]:
        w(f"  K{kid:<5d} n={len(lst):3d} SummeR={sum(x.r for x in lst):+9.2f} "
          f"GEW={sum(1 for x in lst if x.r > 0):3d} "
          f"VERL={sum(1 for x in lst if x.r < 0):3d}")

fh.close()
sys.stdout.reconfigure(encoding="utf-8")
print(f"[fertig] {OUT}")
