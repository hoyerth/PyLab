# -*- coding: utf-8 -*-
"""READ-ONLY: Entry-AUSFUEHRUNG (Fill-Mechanik) - kausal, R + USD.

Frage des Users: "Wir hatten in 0.4 eine spezielle Entry-Logik - pruefe, ob
es uns hier auch hilft - nicht speziell diesen Entry, sondern fuer ALLE."

Befund-Vorlauf: v0.4 (Baseline v0.4.0, frozen) hat KEINE eigene Fill-Logik.
Entry = open[k+1] (in_bar) / open[k+2] (next_bar) - identisch zu V3
(git show 7337bfc:scripts/tmp_phasen_volumen_profil.py bestaetigt).
Die "spezielle Logik" von v0.4 liegt in der KANTEN-AUSWAHL (Tier-1/2,
Kapselung, Cooldown-Asymmetrie) - nicht in der Ausfuehrung.

Diese Messung prueft daher die einzige noch offene Ausfuehrungs-Frage:
Bringt eine Limit-/Retrace-Fill-Mechanik fuer ALLE 14 Trades einen
echten (USD-)Vorteil oder nur R-Kompression?

Regime (RAM-Patch, wie tmp_h1_zyklus_ref3, Teil 7 arretiert):
  Stacking AUS, Band entkoppelt, Zyklus-Uhr auf Entry-Referenz
  -> 14 Trades / +40.45 R / +12.768 USD (IST).

Varianten (ALLE strikt kausal):
  IST  Market open[entry_bar]                       (arretiert)
  SC   Entry am Signal-Close (reclaim_bar)          (Setup-C-Sensitivitaet
                                                    "entry = close[k]")
  ZK   Limit an der Basis auf der Plan-Bar; kein Kontakt -> close[Plan-Bar]
  L{n} Limit an der Basis, ab Plan-Bar n Bars gueltig;
       kein Fill -> Market open[Plan-Bar+n]
  F{n} wie L{n}, aber kein Fill -> Trade entfaellt

AUSDRUECKLICH NICHT ENTHALTEN: "Limit ab Reclaim-Bar" - der Reclaim-Bar IST
der Signal-Bar (entry_bar = reclaim_bar + 1), ein Fill dort waere ein
Same-Bar-Fill = Lookahead (haette in einem ersten Entwurf +49 R ausgewiesen).

USD-Konvention: fixes Risiko-Budget (1 USD je 1 USD Stop-Distanz) - die
USD-Summe ist damit die risikoneutrale Gegenprobe zur R-Summe.
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


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


mod = load("entry_ausf3", b2(ohne_band(ohne_gate(SRC))))
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

assert len(tr) == 14 and abs(sum(t.r for t in tr) - 40.45) < 0.005, \
    f"Regime-Anker verfehlt: {len(tr)} Trades / {sum(t.r for t in tr):+.2f} R"


def fill_an_basis(t, b0: int, b1: int):
    """Erster kausaler Fill in [b0, b1] an der Basis; (bar, preis) | None."""
    for b in range(b0, min(b1 + 1, n)):
        if t.richtung == "SHORT":
            if op[b] >= t.basis:                    # guenstiger Gap -> Open
                return b, float(op[b])
            if hi[b] >= t.basis:
                return b, t.basis
        else:
            if op[b] <= t.basis:
                return b, float(op[b])
            if lo[b] <= t.basis:
                return b, t.basis
    return None


def aufl(t, eb: int, px: float):
    res = mod._c_loese_trade(hi, lo, cl, eb, px, t.richtung,
                             t.sl, t.poc, t.tp2, cfg.tp1_anteil_pct)
    risk = abs(t.sl - px)
    return res.r_mult, res.r_mult * risk, risk


VAR = ("IST", "SC", "ZK", "L1", "L2", "L3", "L5", "L8", "F1", "F3")
sum_r = {v: 0.0 for v in VAR}
sum_usd = {v: 0.0 for v in VAR}
anz = {v: 0 for v in VAR}
zeilen = []

for t in tr:
    eb0 = t.entry_bar
    out = {}
    out["IST"] = (*aufl(t, eb0, float(op[eb0])), eb0, float(op[eb0]))
    out["SC"] = (*aufl(t, t.reclaim_bar, float(cl[t.reclaim_bar])),
                 t.reclaim_bar, float(cl[t.reclaim_bar]))
    f = fill_an_basis(t, eb0, eb0)
    if f is None:
        out["ZK"] = (*aufl(t, eb0, float(cl[eb0])), eb0, float(cl[eb0]))
    else:
        out["ZK"] = (*aufl(t, f[0], f[1]), f[0], f[1])
    for N in (1, 2, 3, 5, 8):
        f = fill_an_basis(t, eb0, eb0 + N - 1)
        if f is None:
            fb = min(eb0 + N, n - 1)
            out[f"L{N}"] = (*aufl(t, fb, float(op[fb])), fb, float(op[fb]))
        else:
            out[f"L{N}"] = (*aufl(t, f[0], f[1]), f[0], f[1])
    for N in (1, 3):
        f = fill_an_basis(t, eb0, eb0 + N - 1)
        out[f"F{N}"] = (None, None, None, None, None) if f is None else \
            (*aufl(t, f[0], f[1]), f[0], f[1])
    for v in VAR:
        if out[v][0] is not None:
            sum_r[v] += out[v][0]
            sum_usd[v] += out[v][1]
            anz[v] += 1
    zeilen.append((t, out))

print("=" * 118)
print("ENTRY-AUSFUEHRUNG (Fill-Mechanik, strikt kausal) - Teil-7-Regime, AUG Voll")
print("=" * 118)
print("  Regime-Anker OK: 14 Trades | +40.45 R | +12.768 USD (IST).")
print("  Getauscht wird NUR die Fill-Mechanik - Signal-Erzeugung, SL, TP bleiben")
print("  bit-identisch. 'Limit' liegt an der Kanten-Basis (non-expansiv).")
print("")
print(f"  {'Var':>4} | {'n':>3} | {'Summe R':>9} | {'dR':>7} | "
      f"{'Summe USD':>10} | {'dUSD':>8} | Bemerkung")
BEM = {
    "IST": "arretiert: Market open[entry_bar]",
    "SC": "Entry am Signal-Close (Setup-C-Sensitivitaet)",
    "ZK": "Limit auf Plan-Bar, sonst close[Plan-Bar]",
    "L1": "Limit 1 Bar, sonst Market-Fallback",
    "L2": "Limit 2 Bars, sonst Market-Fallback",
    "L3": "Limit 3 Bars, sonst Market-Fallback",
    "L5": "Limit 5 Bars, sonst Market-Fallback",
    "L8": "Limit 8 Bars, sonst Market-Fallback",
    "F1": "Limit 1 Bar, sonst Trade entfaellt",
    "F3": "Limit 3 Bars, sonst Trade entfaellt",
}
for v in VAR:
    print(f"  {v:>4} | {anz[v]:3d} | {sum_r[v]:+9.2f} | "
          f"{sum_r[v] - sum_r['IST']:+7.2f} | {sum_usd[v]:+10.3f} | "
          f"{sum_usd[v] - sum_usd['IST']:+8.3f} | {BEM[v]}")

print("")
print("  TRADE-EBENE (nur Varianten mit USD-Zuwachs bzw. groesstem dR)")
print(f"  {'bar':>5} {'K':>4} {'Stufe':>17} {'basis':>8} | "
      f"{'IST R':>7} {'IST $':>8} | {'L3 R':>7} {'L3 $':>8} | "
      f"{'F3 R':>7} {'F3 $':>8} | {'SC R':>7} {'SC $':>8}")
for t, o in zeilen:
    def z(v, i):
        return "(  --  )" if o[v][0] is None else f"{o[v][i]:+7.2f}" if i == 0 \
            else f"{o[v][i]:+8.3f}"
    print(f"  {t.bar:5d} K{t.kid:3d} {t.stufe:>17} {t.basis:8.3f} | "
          f"{z('IST', 0)} {z('IST', 1)} | {z('L3', 0)} {z('L3', 1)} | "
          f"{z('F3', 0)} {z('F3', 1)} | {z('SC', 0)} {z('SC', 1)}")

print("")
print("  RISIKO-KOMPRESSION vs. MARKTVORTEIL (Variante L3, je Trade)")
print(f"  {'bar':>5} {'K':>4} {'risk_ist':>9} {'risk_L3':>8} {'R_ist':>7} "
      f"{'R_L3':>7} {'$ ist':>8} {'$ L3':>8} {'d$':>7}")
for t, o in zeilen:
    a, b = o["IST"], o["L3"]
    print(f"  {t.bar:5d} K{t.kid:3d} {a[2]:9.3f} {b[2]:8.3f} {a[0]:+7.2f} "
          f"{b[0]:+7.2f} {a[1]:+8.3f} {b[1]:+8.3f} {b[1] - a[1]:+7.3f}")
