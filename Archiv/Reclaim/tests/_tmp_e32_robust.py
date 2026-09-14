# -*- coding: utf-8 -*-
"""E-32 (read-only) -- ROBUSTHEIT DES MFE-BRUCH-FILTERS.

Aufruf: python test/_tmp_e32_robust.py <s2|aug>

Phase 1 der Anwender-Vorgabe:
  1.1  Stresstest mfe_cap in [0.25 .. 2.0] R, getrennt nach Halbierungen
       UND nach Volatilitaets-Regimen (Tercile von ATR14/Entry).
  1.2  Verifikation des MFE-Zeitpunkts: strikt kausal, ohne Look-ahead.
       Gegenprobe mit einer absichtlich look-ahead-behafteten Variante.

Grundlage: Setup-Geometrien aus E-29 (`_tmp_e29_setups_*_b60.pkl`),
Kernstandard `geg960poc`. Keine Engine-Aenderung.

Pflichtmetriken (Urkunde E-30/I4): USD/Trade, dR Gewinner; Q_stop deskriptiv.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "eng", ROOT / "test" / "tmp_kanten_engine_replay.py")
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

MODE = (sys.argv[1] if len(sys.argv) > 1 else "s2").lower()
SPLIT = 17692
BINS = 60
OUT = ROOT / "test" / f"_tmp_e32_robust_{MODE}_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

if MODE == "s2":
    scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
else:
    scan = eng._se_scan("AUG", eng.StraightEdgeHarnessKonfiguration())
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
S: List[Dict] = pickle.loads(
    (ROOT / "test" / f"_tmp_e29_setups_{MODE}_b{BINS}.pkl").read_bytes())

_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])


def atr14(k: int) -> float:
    return float(_tr[max(0, k - 13):k + 1].mean())


def sim_halb(entry: float, risk: float, sl: float, ziel: float, e_bar: int,
             short: bool) -> Tuple[float, int]:
    nb = len(hi) - e_bar
    for m in range(nb):
        h, l = float(hi[e_bar + m]), float(lo[e_bar + m])
        if short:
            if h >= sl:
                return -1.0, e_bar + m
            if l <= ziel:
                return (entry - ziel) / risk, e_bar + m
        else:
            if l <= sl:
                return -1.0, e_bar + m
            if h >= ziel:
                return (ziel - entry) / risk, e_bar + m
    return ((entry - float(cl[-1])) if short else
            (float(cl[-1]) - entry)) / risk, e_bar + nb - 1


# ---------------------------------------------------------- Vorberechnung
TR: List[Dict] = []
for s in S:
    e_bar = int(s["entry_bar"])
    entry = float(s["entry"])
    risk = abs(float(s["sl"]) - entry) or 1e-9
    short = s["richtung"] == "SHORT"
    basis = float(s["basis"])
    r1, ex1 = sim_halb(entry, risk, float(s["sl"]), float(s["poc"]), e_bar, short)
    r2, ex2 = sim_halb(entry, risk, float(s["sl"]), float(s["tp2"]), e_bar, short)
    last = max(ex1, ex2)
    ms = list(range(e_bar, last + 1))
    crs, dists, mfes = [], [], []
    for m in ms:
        c = float(cl[m])
        crs.append(((entry - c) if short else (c - entry)) / risk)
        a = atr14(m) or 1e-9
        dists.append(((c - basis) if short else (basis - c)) / a)
        h, l = float(hi[m]), float(lo[m])
        exc = ((entry - l) if short else (h - entry)) / risk
        # MFE STRIKT KAUSAL: nur Bars <= m, und m ist abgeschlossen.
        mfes.append(max(mfes[-1] if mfes else -1e9, exc))
    TR.append({"s": s, "bar": int(s["bar"]), "r1": r1, "r2": r2,
               "ex1": ex1, "ex2": ex2, "base_r": 0.5 * r1 + 0.5 * r2,
               "ms": ms, "crs": crs, "dists": dists, "mfes": mfes,
               "e_bar": e_bar, "atr": atr14(int(s["bar"])),
               "risk": risk, "entry": entry})

RK = np.array([t["risk"] for t in TR])
ATRE = np.array([t["atr"] for t in TR])
ENT = np.array([t["entry"] for t in TR])
BA = np.array([t["base_r"] for t in TR])
GW, LW = BA > 0, BA <= 0
H1M = np.array([t["bar"] < SPLIT for t in TR])
H2M = ~H1M

# Volatilitaets-Tercile (ATR14/Entry, dimensionslos)
volrel = ATRE / ENT
q1, q2 = np.percentile(volrel, [33.333, 66.667])
VMASKS = {"ruhig (T1)": volrel <= q1,
          "mittel (T2)": (volrel > q1) & (volrel <= q2),
          "volatil (T3)": volrel > q2}


def first_break(t: Dict) -> Optional[int]:
    for j, v in enumerate(t["dists"]):
        if v >= 0.0:
            return j
    return None


def wende_an(mfe_cap: float, mask: np.ndarray,
             lookahead: bool = False) -> Dict:
    idx = np.where(mask)[0]
    rl = np.zeros(len(idx))
    fired = np.zeros(len(idx), dtype=bool)
    for k, i in enumerate(idx):
        t = TR[i]
        j = first_break(t)
        if j is None:
            rl[k] = t["base_r"]
            continue
        # kausal: MFE bis zum VORBAR; lookahead: inkl. Bruch-Bar
        ref = t["mfes"][j] if lookahead else (t["mfes"][j - 1] if j > 0 else -1e9)
        if ref >= mfe_cap:
            rl[k] = t["base_r"]
            continue
        m, cr = t["ms"][j], t["crs"][j]
        r1 = t["r1"] if m >= t["ex1"] else cr
        r2 = t["r2"] if m >= t["ex2"] else cr
        rl[k] = 0.5 * r1 + 0.5 * r2
        fired[k] = True
    ba, rk_, at = BA[idx], RK[idx], ATRE[idx]
    usd, usd_b = rl * rk_, ba * rk_
    gw, lw = ba > 0, ba <= 0
    return {"n": len(idx), "R": float(rl.sum()), "USDn": float(usd.mean()),
            "ATRn": float((usd / at).mean()),
            "Qstop": float((rl <= -1.0 + 1e-9).mean()),
            "fired": int(fired.sum()),
            "dR_Gew": float((rl - ba)[gw].sum()),
            "dR_Verl": float((rl - ba)[lw].sum()),
            "USDd": float((usd - usd_b).sum()),
            "getoetet": int((gw & fired & (rl <= 0)).sum()),
            "baseUSDn": float(usd_b.mean())}


CAPS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 1e9)
CAPTXT = {1e9: "aus"}


def ct(c: float) -> str:
    return CAPTXT.get(c, f"{c:.2f}")


def kopf() -> None:
    print(f"   {'cap':>6}{'n':>5}{'USD/Tr':>9}{'Basis':>9}{'Delta':>9}"
          f"{'ATR/Tr':>9}{'Q_stop':>8}{'Feuer':>7}{'dR Gew':>10}"
          f"{'dR Verl':>10}{'USB-D':>9}{'getoetet':>9}")


def zeile(c: float, e: Dict) -> None:
    print(f"   {ct(c):>6}{e['n']:>5}{e['USDn']:>+9.4f}{e['baseUSDn']:>+9.4f}"
          f"{e['USDn']-e['baseUSDn']:>+9.4f}{e['ATRn']:>+9.4f}{e['Qstop']:>8.3f}"
          f"{e['fired']:>7}{e['dR_Gew']:>+10.2f}{e['dR_Verl']:>+10.2f}"
          f"{e['USDd']:>+9.4f}{e['getoetet']:>9}")


print("=" * 120)
print(f"E-32 ROBUSTHEIT DES MFE-BRUCH-FILTERS -- {MODE.upper()}  n = {len(TR)}")
print("=" * 120)
print(f"   Volatilitaets-Tercile (ATR14/Entry): q1 {q1*100:.4f} %  "
      f"q2 {q2*100:.4f} %")

# --------------------------------------------------------------------- 1.2
print("")
print("1.2 -- KAUSALITAETS-VERIFIKATION")
print("   (a) Monotonie der MFE-Reihe je Trade (nicht-fallend)")
mono_ok = True
for t in TR:
    if any(t["mfes"][i] < t["mfes"][i - 1] - 1e-12
           for i in range(1, len(t["mfes"]))):
        mono_ok = False
        break
print(f"       monoton: {mono_ok}  (alle {len(TR)} Trades)")
print("   (b) MFE[j-1] nutzt ausschliesslich Bars e_bar..m-1 -- "
      "Neuberechnung aus dem Bar-Array")
fehler = 0
for t in TR:
    j = first_break(t)
    if j is None or j == 0:
        continue
    eb = t["e_bar"]
    neu = 0.0
    for m in range(eb, t["ms"][j]):
        h, l = float(hi[m]), float(lo[m])
        neu = max(neu, ((t["entry"] - l) if t["s"]["richtung"] == "SHORT"
                        else (h - t["entry"])) / t["risk"])
    if abs(neu - t["mfes"][j - 1]) > 1e-12:
        fehler += 1
print(f"       Abweichungen: {fehler} von {sum(1 for t in TR if first_break(t) not in (None, 0))}"
      " gepruefte Trades")
print("   (c) Gegenprobe look-ahead (MFE inkl. Bruch-Bar) vs. kausal -- S2/gesamt")
ka = wende_an(0.75, np.ones(len(TR), dtype=bool), lookahead=False)
la = wende_an(0.75, np.ones(len(TR), dtype=bool), lookahead=True)
print(f"       kausal   : USD/Tr {ka['USDn']:+.4f}  dR Gew {ka['dR_Gew']:+.2f}  "
      f"Feuer {ka['fired']}")
print(f"       lookahead: USD/Tr {la['USDn']:+.4f}  dR Gew {la['dR_Gew']:+.2f}  "
      f"Feuer {la['fired']}")
print(f"       -> Differenz {la['USDn'] - ka['USDn']:+.4f} USD/Tr (Diskrepanz "
      f"belegt, dass der Zeitpunkt messbar ist)")

# --------------------------------------------------------------------- 1.1a
print("")
print("1.1a -- STRESSTEST nach HALBIERUNG")
for gname, mask in (("GESAMT", np.ones(len(TR), dtype=bool)),
                    ("H1", H1M), ("H2", H2M)):
    print(f"   --- {gname} ---")
    kopf()
    for c in CAPS:
        zeile(c, wende_an(c, mask))
    print("")

# --------------------------------------------------------------------- 1.1b
print("1.1b -- STRESSTEST nach VOLATILITAETS-REGIME")
for gname, mask in VMASKS.items():
    print(f"   --- {gname} (n = {int(mask.sum())}) ---")
    kopf()
    for c in CAPS:
        zeile(c, wende_an(c, mask))
    print("")

# --------------------------------------------------------------------- 1.1c
print("1.1c -- ROBUSTHEITSKENNZAHL: USD/Tr des Cap relativ zur Basis,")
print("       ueber alle 3 Volatilitaets-Regime (Vorzeichen-Stabilitaet)")
print(f"   {'cap':>6}{'T1 ruhe':>10}{'T2 mitte':>10}{'T3 volat':>10}"
      f"{'alle > 0?':>11}{'min Delta':>11}")
for c in CAPS:
    ds = []
    for m in VMASKS.values():
        e = wende_an(c, m)
        ds.append(e["USDn"] - e["baseUSDn"])
    ok = all(abs(x) < 1e-12 or x > 0 for x in ds)
    print(f"   {ct(c):>6}{ds[0]:>+10.4f}{ds[1]:>+10.4f}{ds[2]:>+10.4f}"
          f"{('ja' if ok else 'nein'):>11}{min(ds):>+11.4f}")

# --------------------------------------------------------------------- 1.1d
print("")
print("1.1d -- SCHWELLEN-EMPFEHLUNG: Vergleich 0.75 vs 1.00 ueber ALLE Schnitte")
print(f"   {'Schnitt':<16}{'USD/Tr 0.75':>13}{'USD/Tr 1.00':>13}{'besser':>9}"
      f"{'dR Gew 0.75':>13}{'dR Gew 1.00':>13}")
schnitte = [("gesamt", np.ones(len(TR), dtype=bool)), ("H1", H1M), ("H2", H2M)]
schnitte += list(VMASKS.items())
for gname, mask in schnitte:
    if int(mask.sum()) == 0:
        continue
    a = wende_an(0.75, mask)
    b = wende_an(1.0, mask)
    if abs(a["USDn"] - b["USDn"]) < 1e-12:
        w = "gleich"
    else:
        w = "0.75" if a["USDn"] > b["USDn"] else "1.00"
    print(f"   {gname:<16}{a['USDn']:>+13.4f}{b['USDn']:>+13.4f}{w:>9}"
          f"{a['dR_Gew']:>+13.2f}{b['dR_Gew']:>+13.2f}")
print("")
print(f"ENDE E-32 {MODE.upper()}")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
