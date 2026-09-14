# -*- coding: utf-8 -*-
"""READ-ONLY: Kennzahl-Metriken fuer das Ziel-Set (ENTRY-Ref v=12).

Klaerung der D5-Frage: R-Multiples sind per Konstruktion risiko-normiert
(r = PnL / Risk). Die Summe der R ist daher die Kennzahl bei FIXEM RISIKO je
Trade. Bei FIXEM NOTIONAL (konstante Losgroesse) ist dagegen die USD-Summe
massgeblich. Beide werden ausgewiesen.
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


def entferne_stacking(src: str) -> str:
    start = src.index(GSTACK)
    zeilenende = src.index("\r\n", start) + 2
    cpos = src.index("                    continue\r\n", zeilenende)
    cende = cpos + len("                    continue\r\n")
    blk = src[start:cende]
    return src.replace(blk,
                       "            # [RAM] Stacking-Gate deaktiviert\r\n"
                       "            _vor = letzter_trade.get(kd.kid)\r\n", 1)


def entkopple_band(src: str) -> str:
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


def entry_anker_ohne_feld(src: str) -> str:
    return src.replace(
        GCHECK,
        "            _vor_zeit = letzter_trade.get(kd.kid)\r\n"
        "            if (_vor_zeit is not None and\r\n"
        "                    entry_bar - _vor_zeit.entry_bar\r\n"
        "                    < cfg.retest_zyklus_bars):\r\n", 1)


def mit_zyklus(src: str, v: int) -> str:
    return src.replace("retest_zyklus_bars: int = 12",
                       f"retest_zyklus_bars: int = {v}", 1)


BASIS = entferne_stacking(entkopple_band(SRC))
SRC_B12 = mit_zyklus(entry_anker_ohne_feld(BASIS), 12)


def lauf(src: str, name: str):
    mod = load(name, src)
    cfg = mod.StraightEdgeHarnessKonfiguration()
    sc = mod._se_scan("AUG", cfg)
    sc["box_end_bar"] = sc["n"]
    tr, st = mod._se_trades(sc, cfg)
    return tr, st, sc


tr, st, sc = lauf(SRC_B12, "risk_norm_b12")
ts = sc["d"]["ts"]

print("=" * 118)
print("KENNZAHL-METRIKEN -- ENTRY-Ref v=12 (Stacking AUS, Band entkoppelt), AUG Voll n=1288")
print("=" * 118)
print(f"  {'bar':>5} {'zeit':>12} {'K':>4} {'entry':>6} {'E':>8} {'SL':>8} "
      f"{'risk$':>7} {'R':>8} {'PnL$':>8} {'R@meanRisk':>11}")
risks, pnl = [], []
for t in tr:
    r_abs = abs(t.sl - t.entry)
    p = t.r * r_abs
    risks.append(r_abs)
    pnl.append(p)
    print(f"  {t.bar:5d} {ts.iloc[t.bar].strftime('%d.%m %H:%M'):>12} K{t.kid:3d} "
          f"{t.entry_bar:6d} {t.entry:8.3f} {t.sl:8.3f} {r_abs:7.3f} {t.r:+8.2f} "
          f"{p:+8.3f}")

n = len(tr)
mean_risk = sum(risks) / n
sum_r = sum(t.r for t in tr)
sum_pnl = sum(pnl)
print("-" * 118)
print(f"  Trades {n} | Risiko je Trade: min {min(risks):.3f} / median "
      f"{sorted(risks)[n // 2]:.3f} / max {max(risks):.3f} / Mittel {mean_risk:.4f} USD")
print("")
print(f"  METRIK 1 (fixes Risiko je Trade, Standard-R):  Summe R = {sum_r:+.2f} R")
print(f"  METRIK 2 (fixes Notional, USD-PnL):            Summe = {sum_pnl:+.3f} USD")
print(f"  METRIK 3 (Notional in R beim Mittelrisiko):    {sum_pnl / mean_risk:+.2f} R")
print("")
print("  -> R-Summen sind per Konstruktion bereits risiko-normiert (gleiches")
print("     Risiko je Trade). Die frueher genannte Zahl '+33,3 R' war eine")
print("     inkonsistente Einzelkorrektur nur des 564er Trades und ist VERWORFEN.")
print("")
out = [t for t in tr if t.r > 0]
print(f"  Treffer {len(out)}/{n} = {len(out) / n * 100:.1f} % | "
      f"Summe Gewinne {sum(t.r for t in out):+.2f} R | "
      f"Summe Verluste {sum(t.r for t in tr if t.r < 0):+.2f} R | "
      f"Payoff {abs(sum(t.r for t in out) / sum(t.r for t in tr if t.r < 0)):.2f}")
