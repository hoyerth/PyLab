# -*- coding: utf-8 -*-
"""READ-ONLY 2x2x2-Dekompensation: Gate x Band x Zyklus-Referenz.

Beantwortet die Frage "welcher Anteil stammt woraus" fuer §7.2 Teil 7.
AUG Voll-Fenster n=1288, je Zelle frischer _se_scan, RAM-Kopien der Engine.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()

G3O = ("        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
       "        if not (hi[k] > basis and band < dist_o\r\n"
       "                <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G3U = ("    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
       "    if not (lo[k] < basis and band < dist_u\r\n"
       "            <= cfg.max_sweep_ueberdehnung_pct):\r\n")
G2 = ("            if dist <= cfg.touch_band_pct:\r\n"
      "                continue                        # Beruehrung/in-band (Schatten)\r\n")
G2S = ("            if cfg.touch_band_pct < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
       "                pool.append(e)\r\n")
GSTACK = "            _vor = letzter_trade.get(kd.kid)"
GCHECK = "            if k - kd.letzter_sweep_bar < cfg.retest_zyklus_bars:\r\n"
for nm, an in (("G3O", G3O), ("G3U", G3U), ("G2", G2), ("G2S", G2S),
               ("GCHECK", GCHECK)):
    assert SRC.count(an) == 1, f"Anker {nm}: {SRC.count(an)} Treffer"
assert SRC.count(GSTACK) == 1


def ohne_gate(src: str) -> str:
    start = src.index(GSTACK)
    zeilenende = src.index("\r\n", start) + 2
    cpos = src.index("                    continue\r\n", zeilenende)
    cende = cpos + len("                    continue\r\n")
    return src.replace(src[start:cende],
                       "            # [RAM] Stacking-Gate deaktiviert\r\n"
                       "            _vor = letzter_trade.get(kd.kid)\r\n", 1)


def ohne_band(src: str) -> str:
    s = src.replace(
        G3O, "        dist_o = (hi[k] - basis) / basis * 100.0\r\n"
             "        if not (hi[k] > basis and 0.0 < dist_o\r\n"
             "                <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G3U, "    dist_u = (basis - lo[k]) / basis * 100.0\r\n"
             "    if not (lo[k] < basis and 0.0 < dist_u\r\n"
             "            <= cfg.max_sweep_ueberdehnung_pct):\r\n", 1)
    s = s.replace(
        G2, "            if dist <= 0.0:\r\n"
            "                continue                        # nur Durchstich zaehlt\r\n", 1)
    s = s.replace(
        G2S, "            if 0.0 < d <= cfg.max_sweep_ueberdehnung_pct:\r\n"
             "                pool.append(e)\r\n", 1)
    return s


def b2(src: str) -> str:
    return src.replace(
        GCHECK,
        "            _vor_zeit = letzter_trade.get(kd.kid)\r\n"
        "            if (_vor_zeit is not None and\r\n"
        "                    entry_bar - _vor_zeit.entry_bar\r\n"
        "                    < cfg.retest_zyklus_bars):\r\n", 1)


def lauf(src: str, name: str):
    mod = load(name, src)
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = sc["n"]
    tr, st = mod._se_trades(sc, cfg)
    return tr, st


print("=" * 118)
print("2x2x2-DEKOMPOSITION (AUG Voll n=1288) -- Gate x Band-Kopplung x Zyklus-Referenz")
print("=" * 118)
print(f"  {'Gate':>6} | {'Band':>12} | {'Uhr':>10} | {'Trades':>6} | {'Netto-R':>8} | "
      f"{'dR vs V0':>9} | K20-Pfade 12.08.")
print("-" * 118)
base_r = None
for gate_aus in (False, True):
    for band_aus in (False, True):
        for b2_aus in (False, True):
            src = SRC
            if gate_aus:
                src = ohne_gate(src)
            if band_aus:
                src = ohne_band(src)
            if b2_aus:
                src = b2(src)
            tr, st = lauf(src, f"dek_{int(gate_aus)}{int(band_aus)}{int(b2_aus)}")
            r = sum(t.r for t in tr)
            if base_r is None:
                base_r = r
            k20 = [t for t in tr if t.kid == 20 and 200 < t.bar < 300]
            k20s = " | ".join(f"{t.bar}->{t.entry_bar} {t.r:+.2f}R" for t in k20) or "-"
            print(f"  {'AUS' if gate_aus else 'AN':>6} | "
                  f"{'entkoppelt' if band_aus else '0.12 %':>12} | "
                  f"{'ENTRY-Ref' if b2_aus else 'SWEEP-Ref':>10} | "
                  f"{len(tr):6d} | {r:+8.2f} | {r - base_r:+9.2f} | {k20s}")

print("")
print("  Lesehilfe: 'AN/0.12 %/SWEEP-Ref' = arretierter Ist-Stand (V0).")
print("  B2 ist in JEDER Zelle mit 'ENTRY-Ref' aktiv (retest_zyklus_bars = 12).")
