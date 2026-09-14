# -*- coding: utf-8 -*-
"""READ-ONLY: Entry-Ausfuehrung - kausale Limit-Varianten in R UND USD.

Ziel: Die Frage "spezielle Entry-Logik fuer ALLE Entries" quantitativ
beantworten - ohne In-Sample-Tuning und ohne Engine-Eingriff.

Regime (RAM-Patch wie tmp_h1_zyklus_ref3): Stacking AUS, Band entkoppelt,
Zyklus-Uhr auf Entry-Referenz (Teil 7) -> 14 Trades / +40.45 R.

Varianten (alle kausal - kein Wissen ueber kuenftige Opens):
  IST  Market open[entry_bar]                       (arretiert)
  ZK   Limit an der Basis auf der Plan-Bar;
       kein Kontakt -> Market close[Plan-Bar]       (keine Verzoegerung)
  G3   Limit an der Basis, 3 Bars gueltig;
       kein Fill -> Market open[Plan-Bar+3]
  F3   Limit an der Basis, 3 Bars gueltig;
       kein Fill -> Trade entfaellt
  L3   Limit an der Basis ab Reclaim-Bar, 3 Bars gueltig;
       kein Fill -> Trade entfaellt (Order-Verfall)

Fill-Semantik: Order liegt an der Basis (SHORT: Verkauf >= Basis /
LONG: Kauf <= Basis). Fill, sobald die Bar-Range die Basis beruehrt; ein
Open jenseits der Basis (GuensƟger Gap) fuellt sofort zum Open.
SL/TP bleiben unveraendert (SL strukturell am Sweep-Extremum).
Zusaetzlich wird je Variante die USD-Summe (fixe Losgroesse = 1 USD je
1 USD Risiko) ausgewiesen, um Risiko-Kompression von echtem Marktvorteil
zu trennen.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

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
             "                pool.append(e)\r\n", 1)
    return s


def b2(src: str) -> str:
    return src.replace(
        GCHECK,
        "            _vor_zeit = letzter_trade.get(kd.kid)\r\n"
        "            if (_vor_zeit is not None and\r\n"
        "                    entry_bar - _vor_zeit.entry_bar\r\n"
        "                    < cfg.retest_zyklus_bars):\r\n", 1)


BASIS = b2(ohne_band(ohne_gate(SRC)))


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


mod = load("entry_ausf2", BASIS)
cfg = mod.StraightEdgeHarnessKonfiguration()
sc = mod._se_scan("AUG", cfg)
sc["box_end_bar"] = sc["n"]
tr, st = mod._se_trades(sc, cfg)

d = sc["d"]
op = d["open"].to_numpy(dtype=float)
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
n = len(hi)


def fill_an_basis(t, b0: int, b1: int):
    """Erster Fill in [b0, b1] an der Basis; (bar, preis, modus) | None."""
    for b in range(b0, min(b1 + 1, n)):
        if t.richtung == "SHORT":
            if op[b] >= t.basis:                    # guenstiger Gap
                return b, float(op[b]), "gap"
            if hi[b] >= t.basis:
                return b, t.basis, "limit"
        else:
            if op[b] <= t.basis:
                return b, float(op[b]), "gap"
            if lo[b] <= t.basis:
                return b, t.basis, "limit"
    return None


def aufl(t, eb: int, px: float):
    res = mod._c_loese_trade(hi, lo, cl, eb, px, t.richtung,
                             t.sl, t.poc, t.tp2, cfg.tp1_anteil_pct)
    risk = abs(t.sl - px)
    return res.r_mult, res.r_mult * risk, risk, res.grund1


VAR = ("IST", "SC", "ZK", "G3", "F3", "L3")
sum_r = {v: 0.0 for v in VAR}
sum_usd = {v: 0.0 for v in VAR}
zeilen = []

for t in tr:
    eb0 = t.entry_bar
    out = {}
    # IST
    r, u, risk, g = aufl(t, eb0, float(op[eb0]))
    out["IST"] = (eb0, float(op[eb0]), r, u, risk, g, "market")
    # SC: Signal-Close (reclaim_bar) statt Open der Plan-Bar
    r, u, risk, g = aufl(t, t.reclaim_bar, float(cl[t.reclaim_bar]))
    out["SC"] = (t.reclaim_bar, float(cl[t.reclaim_bar]), r, u, risk, g, "close")
    # ZK: Limit auf Plan-Bar, sonst Market-Close der Plan-Bar
    f = fill_an_basis(t, eb0, eb0)
    if f is not None:
        r, u, risk, g = aufl(t, f[0], f[1])
        out["ZK"] = (f[0], f[1], r, u, risk, g, f[2])
    else:
        r, u, risk, g = aufl(t, eb0, float(cl[eb0]))
        out["ZK"] = (eb0, float(cl[eb0]), r, u, risk, g, "close")
    # G3: Limit 3 Bars, sonst Market open[eb+3]
    f = fill_an_basis(t, eb0, eb0 + 2)
    if f is not None:
        r, u, risk, g = aufl(t, f[0], f[1])
        out["G3"] = (f[0], f[1], r, u, risk, g, f[2])
    else:
        fb = min(eb0 + 3, n - 1)
        r, u, risk, g = aufl(t, fb, float(op[fb]))
        out["G3"] = (fb, float(op[fb]), r, u, risk, g, "fallback")
    # F3: Limit 3 Bars, sonst entfaellt
    f = fill_an_basis(t, eb0, eb0 + 2)
    out["F3"] = (None, None, None, None, None, None, "verworfen") if f is None \
        else (f[0], f[1], *aufl(t, f[0], f[1]), f[2])
    # L3: Limit ab Reclaim-Bar (Order liegt beim Reclaim-Close), 3 Bars
    f = fill_an_basis(t, t.reclaim_bar, t.reclaim_bar + 2)
    out["L3"] = (None, None, None, None, None, None, "verworfen") if f is None \
        else (f[0], f[1], *aufl(t, f[0], f[1]), f[2])
    for v in VAR:
        if out[v][2] is not None:
            sum_r[v] += out[v][2]
            sum_usd[v] += out[v][3]
    zeilen.append((t, out))

print("=" * 128)
print("ENTRY-AUSFUEHRUNG (kausal) -- arretiertes Teil-7-Regime, AUG Voll, 14 Trades")
print("=" * 128)
print("  IST = arretiert (Market open[eb]). Alle anderen Varianten tauschen NUR die")
print("  Fill-Mechanik; Signal-Erzeugung, SL, TP1/POC, TP2 bleiben bit-identisch.")
print("")
for v in VAR:
    print(f"  {v:4s} | {sum(1 for _t, o in zeilen if o[v][2] is not None):3d} Trades | "
          f"{sum_r[v]:+8.2f} R | {sum_usd[v]:+8.3f} USD | "
          f"dR {sum_r[v] - sum_r['IST']:+7.2f} | dUSD {sum_usd[v] - sum_usd['IST']:+7.3f}")
print("")
print(f"  {'bar':>5} {'K':>4} {'Stufe':>17} {'basis':>8} | " +
      " | ".join(f"{v:>22s}" for v in VAR))
print(f"  {'':>5} {'':>4} {'':>17} {'':>8} | " +
      " | ".join(f"{'bar   entry      R':>22s}" for v in VAR))
for t, o in zeilen:
    zellen = []
    for v in VAR:
        eb, px, r, u, risk, g, m = o[v]
        if eb is None:
            zellen.append(f"{'(verworfen)':>22s}")
        else:
            zellen.append(f"{eb:5d} {px:8.3f} {r:+6.2f}")
    print(f"  {t.bar:5d} K{t.kid:3d} {t.stufe:>17} {t.basis:8.3f} | " +
          " | ".join(zellen))

print("")
print("  RISIKO-KOMPRESSION vs. MARKTVORTEIL (je Trade, Variante G3)")
print(f"  {'bar':>5} {'K':>4} {'risk_ist':>9} {'risk_G3':>8} {'R_ist':>7} {'R_G3':>7} "
      f"{'USD_ist':>8} {'USD_G3':>8} {'dUSD':>7}")
for t, o in zeilen:
    a, b = o["IST"], o["G3"]
    print(f"  {t.bar:5d} K{t.kid:3d} {a[4]:9.3f} {b[4]:8.3f} {a[2]:+7.2f} "
          f"{b[2]:+7.2f} {a[3]:+8.3f} {b[3]:+8.3f} {b[3] - a[3]:+7.3f}")
