# -*- coding: utf-8 -*-
"""READ-ONLY: E3-Nebenbefund "SL/TP-Seitenlage" (SHORT) - Pruefung.

Ausgangs-Verdacht (Session-Notiz): "SL 66.713 > Entry 66.092 > TP 63.676
wirkt invertiert."

Faktische Pruefung:
  1. Geometrie-Check fuer ALLE 14 Trades: SHORT muss sl > entry > poc > tp2
     erfuellen, LONG spiegelbildlich. Ein "invertierter" SL waere ein Bug.
  2. Lage des SL relativ zur Einstiegs-Kante (basis) und zum Sweep-Extremum.
  3. Sensitivitaet: Was kostet/erloest eine andere SL-Verankerung?
       IST          sl = max(high[k..reclaim_bar]) + 0.05   (arretiert)
       SWEEP_ONLY   sl = high[k] + 0.05                     (nur Sweep-Docht)
       KANTE        sl = basis + 0.05                       (hinter der Kante)
       BUF_{x}      sl = cluster_ext + x                    (Puffer-Sweep)

Kein Eingriff in die Engine - reine RAM-Simulation der Resolution
(_c_loese_trade) mit unveraendertem Entry/POC/TP2.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"

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
             "             pool.append(e)\r\n", 1)
    return s


def b2(src: str) -> str:
    return src.replace(
        GCHECK,
        "            _vor_zeit = letzter_trade.get(kd.kid)\r\n"
        "            if (_vor_zeit is not None and\r\n"
        "                    entry_bar - _vor_zeit.entry_bar\r\n"
        "                    < cfg.retest_zyklus_bars):\r\n", 1)


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


mod = load("e3_check", b2(ohne_band(ohne_gate(SRC))))
cfg = mod.StraightEdgeHarnessKonfiguration()
sc = mod._se_scan("AUG", cfg)
sc["box_end_bar"] = sc["n"]
tr, st = mod._se_trades(sc, cfg)

d = sc["d"]
op = d["open"].to_numpy(dtype=float)
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)

assert len(tr) == 14 and abs(sum(t.r for t in tr) - 40.45) < 0.005, \
    f"Regime-Anker verfehlt: {len(tr)} / {sum(t.r for t in tr):+.2f}"

print("=" * 128)
print("E3-PRUEFUNG: SL/TP-Seitenlage + SL-Verankerung -- Teil-7-Regime, 14 Trades")
print("=" * 128)
print("")
print("  1) GEOMETRIE-CHECK (Pflicht-Invariante je Richtung)")
print(f"  {'bar':>5} {'K':>4} {'Richt':>5} {'basis':>8} {'sweep':>8} {'entry':>8} "
      f"{'sl':>8} {'poc':>8} {'tp2':>8} | {'sl>e>poc>tp2':>12} {'sl>basis':>8}")
verletzungen = 0
for t in tr:
    if t.richtung == "SHORT":
        ok = t.sl > t.entry > t.poc > t.tp2
    else:
        ok = t.sl < t.entry < t.poc < t.tp2
    ueber_basis = (t.sl > t.basis) if t.richtung == "SHORT" else (t.sl < t.basis)
    if not ok:
        verletzungen += 1
    print(f"  {t.bar:5d} K{t.kid:3d} {t.richtung:>5} {t.basis:8.3f} {t.sweep:8.3f} "
          f"{t.entry:8.3f} {t.sl:8.3f} {t.poc:8.3f} {t.tp2:8.3f} | "
          f"{str(ok):>12} {str(ueber_basis):>8}")
print(f"  -> Geometrie-Verletzungen: {verletzungen} / 14 "
      f"(0 = kein invertierter SL; 'sl>basis' = SL jenseits der Kante = korrekt)")

print("")
print("  2) SL-ABSTAND: Sweep-Extremum vs. Cluster-Extremum vs. Kante")
print(f"  {'bar':>5} {'K':>4} {'Richt':>5} {'sweep_ext':>9} {'cluster_ext':>11} "
      f"{'sl_ist':>8} {'risk_ist':>8} {'risk_sweep':>10} {'risk_kante':>10}")
for t in tr:
    k, rb = t.bar, t.reclaim_bar
    if t.richtung == "SHORT":
        sweep_ext = float(hi[k])
        cluster_ext = float(np.max(hi[k:rb + 1]))
        sl_sweep = sweep_ext + cfg.sl_buffer_usd
        sl_kante = t.basis + cfg.sl_buffer_usd
    else:
        sweep_ext = float(lo[k])
        cluster_ext = float(np.min(lo[k:rb + 1]))
        sl_sweep = sweep_ext - cfg.sl_buffer_usd
        sl_kante = t.basis - cfg.sl_buffer_usd
    print(f"  {t.bar:5d} K{t.kid:3d} {t.richtung:>5} {sweep_ext:9.3f} "
          f"{cluster_ext:11.3f} {t.sl:8.3f} {abs(t.sl - t.entry):8.3f} "
          f"{abs(sl_sweep - t.entry):10.3f} {abs(sl_kante - t.entry):10.3f}")

print("")
print("  3) SL-VARIANTEN (Resolution neu gerechnet, Entry/POC/TP2 unveraendert)")
VAR = ("IST", "SWEEP", "KANTE", "BUF_0.02", "BUF_0.10", "BUF_0.20")
sum_r = {v: 0.0 for v in VAR}
sum_usd = {v: 0.0 for v in VAR}
anz = {v: 0 for v in VAR}
detail: dict[int, dict[str, float | None]] = {}
for t in tr:
    k, rb = t.bar, t.reclaim_bar
    if t.richtung == "SHORT":
        cluster_ext = float(np.max(hi[k:rb + 1]))
        sl_map = {
            "IST": cluster_ext + 0.05,
            "SWEEP": float(hi[k]) + 0.05,
            "KANTE": t.basis + 0.05,
            "BUF_0.02": cluster_ext + 0.02,
            "BUF_0.10": cluster_ext + 0.10,
            "BUF_0.20": cluster_ext + 0.20,
        }
    else:
        cluster_ext = float(np.min(lo[k:rb + 1]))
        sl_map = {
            "IST": cluster_ext - 0.05,
            "SWEEP": float(lo[k]) - 0.05,
            "KANTE": t.basis - 0.05,
            "BUF_0.02": cluster_ext - 0.02,
            "BUF_0.10": cluster_ext - 0.10,
            "BUF_0.20": cluster_ext - 0.20,
        }
    detail[t.bar] = {}
    for v in VAR:
        sl = sl_map[v]
        gueltig = (sl > t.entry) if t.richtung == "SHORT" else (sl < t.entry)
        if not gueltig:
            detail[t.bar][v] = None
            continue
        res = mod._c_loese_trade(hi, lo, cl, t.entry_bar, t.entry, t.richtung,
                                 sl, t.poc, t.tp2, cfg.tp1_anteil_pct)
        detail[t.bar][v] = res.r_mult
        sum_r[v] += res.r_mult
        sum_usd[v] += res.r_mult * abs(sl - t.entry)
        anz[v] += 1

print(f"  {'bar':>5} {'K':>4} {'Richt':>5} | " +
      " | ".join(f"{v:>9s}" for v in VAR))
for t in tr:
    zellen = []
    for v in VAR:
        r = detail[t.bar][v]
        zellen.append(f"{'(ung.)':>9s}" if r is None else f"{r:+9.2f}")
    print(f"  {t.bar:5d} K{t.kid:3d} {t.richtung:>5} | " + " | ".join(zellen))
print("-" * 128)
for v in VAR:
    print(f"  {v:9s} | n={anz[v]:2d} | Summe R {sum_r[v]:+8.2f} | "
          f"dR vs IST {sum_r[v] - sum_r['IST']:+8.2f} | "
          f"Summe USD {sum_usd[v]:+8.3f} | dUSD {sum_usd[v] - sum_usd['IST']:+7.3f}")
