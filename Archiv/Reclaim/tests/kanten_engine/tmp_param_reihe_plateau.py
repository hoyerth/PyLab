"""READ-ONLY Plateau-/Schwellen-Messung retest_zyklus_bars auf AUG.

Ergaenzt test/tmp_param_reihe.py (Kandidaten 12/16/20/24) um:
  * Schwelle 13 (242 - 229 = 13) -> ab wann ist Bar 245 frei?
  * Plateau 8/4 (Doku-Nachtrag) und 0 (Sperre ersatzlos entfallen).
  * Toxizitaet (Doppel-Verluste je Kante) + parallele Exposition je Variante.

Kein Code-Eingriff, kein Schreiben in Produktivpfade.
"""
import dataclasses
import io
import sys
from typing import List

sys.path.insert(0, 'test')
import tmp_kanten_engine_replay as H  # noqa: E402

KANDIDATEN: List[int] = [24, 20, 16, 13, 12, 8, 4, 3, 2, 1, 0]
OUT = 'test/tmp_param_reihe_plateau.txt'


def lauf(zyklus: int):
    """Frischer Scan je Variante (_se_trades mutiert die Kantenobjekte)."""
    cfg = dataclasses.replace(H.StraightEdgeHarnessKonfiguration(),
                              retest_zyklus_bars=zyklus)
    scan = H._se_scan('AUG', cfg)
    setups, stats = H._se_trades(scan, cfg)
    return setups, stats


def pf(setups) -> float:
    pos = sum(s.r for s in setups if s.r > 0)
    neg = -sum(s.r for s in setups if s.r < 0)
    if neg == 0:
        return float('inf') if pos > 0 else 0.0
    return pos / neg


erg = {z: lauf(z) for z in KANDIDATEN}
L: List[str] = []


def w(zeile: str = "") -> None:
    L.append(zeile)


w("=" * 108)
w("PLATEAU-/SCHWELLEN-MESSUNG  retest_zyklus_bars  (AUG, Box, Loop bis k=641)")
w("read-only, je Variante FRISCHER _se_scan (Kantenmutations-Falle)")
w("=" * 108)
w(f"{'zyklus':>7} {'n':>3} {'SummeR':>8} {'GEW':>4} {'VERL':>5} {'PF':>6} "
  f"{'Zyklus':>7} {'Blocker':>8} {'Quartil':>8} {'F3':>4} {'245':>4} "
  f"{'Ueberl':>7} {'Tox':>4}")
for z in KANDIDATEN:
    s, st = erg[z]
    gew = sum(1 for x in s if x.resultat == "GEWONNEN")
    verl = sum(1 for x in s if x.resultat == "VERLOREN")
    p = pf(s)
    p_txt = "inf" if p == float("inf") else f"{p:.2f}"
    b245 = "JA" if any(x.entry_bar == 245 for x in s) else "-"
    spans = sorted((x.entry_bar, max(x.exit1_bar, x.exit2_bar), x) for x in s)
    over = sum(1 for i in range(len(spans)) for j in range(i + 1, len(spans))
               if spans[j][0] <= spans[i][1])
    per: dict = {}
    for x in s:
        per.setdefault((x.kid, x.richtung), []).append(x)
    tox = 0
    for lst in per.values():
        for a, b in zip(lst, lst[1:]):
            if a.r < 0 and b.r < 0:
                tox += 1
    w(f"{z:>7} {len(s):>3} {sum(x.r for x in s):>+8.2f} {gew:>4} {verl:>5} "
      f"{p_txt:>6} {st['zyklus_blockiert']:>7} {st['blocker']:>8} "
      f"{st['quartil_blockiert']:>8} {st['f3']:>4} {b245:>4} "
      f"{over:>7} {tox:>4}")

w()
w("-" * 108)
w("TRADELISTEN 13 / 3 / 2 / 0 (Schwelle + untere Plateaugrenze)")
w("-" * 108)
for z in (13, 3, 2, 0):
    s = sorted(erg[z][0], key=lambda x: x.entry_bar)
    w(f"\nzyklus={z}  n={len(s)}  SummeR {sum(x.r for x in s):+.2f}")
    for x in s:
        w(f"  {x.richtung:5s} sweep {x.bar:4d} entry {x.entry_bar:4d} "
          f"K{x.kid:<3d} {x.stufe:16s} E={x.entry:.3f} SL={x.sl:.3f} "
          f"R={x.r:+.2f} exit1={x.exit1_bar} exit2={x.exit2_bar} "
          f"{x.resultat}")

w()
w("-" * 108)
w("PARALLELE EXPOSITION (Ueberlappungen) je Variante")
w("-" * 108)
for z in KANDIDATEN:
    s = sorted(erg[z][0], key=lambda x: x.entry_bar)
    spans = [(x.entry_bar, max(x.exit1_bar, x.exit2_bar), x) for x in s]
    over = []
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            if b[0] <= a[1]:
                over.append((a[2], b[2]))
    w(f"\nzyklus={z}: {len(over)} Ueberlappung(en)")
    for a, b in over:
        w(f"  entry {a.entry_bar} K{a.kid} (exit {max(a.exit1_bar, a.exit2_bar)},"
          f" R {a.r:+.2f})  <->  entry {b.entry_bar} K{b.kid} "
          f"(exit {max(b.exit1_bar, b.exit2_bar)}, R {b.r:+.2f})")

text = "\n".join(L)
with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write(text + "\n")
sys.stdout.reconfigure(encoding="utf-8")
print(text)
print(f"\n[geschrieben] {OUT}")
