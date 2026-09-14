# -*- coding: utf-8 -*-
"""E-31b (read-only) -- ECHTE DISKRIMINATION? Bruch nur, wenn der Trade NIE lief.

Befund aus E-31/P4-P5: Die Bruch-DISTANZ trennt Gewinner nicht von Verlierern
(Median 0.39 vs 0.36 ATR). Der Unterschied liegt in der VORGESCHICHTE:

    Basis-Verlierer: Bruch nach median  1 Bar, MFE davor 0.40 R
    Basis-Gewinner : Bruch nach median 84 Bar, MFE davor 2.75 R

Hypothese H: Nicht "wie weit bricht es", sondern "hat der Trade vorher
gearbeitet" diskriminiert. Regel:

    Bruch an Kante (n=1 Close jenseits `basis`) schliesst NUR, wenn die
    guenstigste Exkursion bis zum Vortag < mfe_cap R geblieben ist.

Sweep ueber mfe_cap. Pflichtmetriken: USD/Trade, dR Gewinner, Q_stop.
Aufruf: python test/_tmp_e31b_mfe.py <s2|aug>
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
OUT = ROOT / "test" / f"_tmp_e31b_mfe_{MODE}_out.txt"
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
        mfes.append(max(mfes[-1] if mfes else -1e9, exc))
    TR.append({"s": s, "bar": int(s["bar"]), "r1": r1, "r2": r2,
               "ex1": ex1, "ex2": ex2, "base_r": 0.5 * r1 + 0.5 * r2,
               "ms": ms, "crs": crs, "dists": dists, "mfes": mfes,
               "e_bar": e_bar})

RK = np.array([abs(t["s"]["sl"] - t["s"]["entry"]) or 1e-9 for t in TR])
ATRE = np.array([atr14(t["bar"]) for t in TR])
BA = np.array([t["base_r"] for t in TR])
GW, LW = BA > 0, BA <= 0


def first_break(t: Dict) -> Optional[int]:
    ds = t["dists"]
    for j, v in enumerate(ds):
        if v >= 0.0:
            return j
    return None


def wende_an(mfe_cap: float) -> Dict:
    rl = np.zeros(len(TR))
    fired = np.zeros(len(TR), dtype=bool)
    skipped = np.zeros(len(TR), dtype=bool)
    for i, t in enumerate(TR):
        j = first_break(t)
        if j is None:
            rl[i] = t["base_r"]
            continue
        mfe_vor = t["mfes"][j - 1] if j > 0 else -1e9
        if mfe_vor >= mfe_cap:
            rl[i] = t["base_r"]
            skipped[i] = True
            continue
        m = t["ms"][j]
        cr = t["crs"][j]
        r1 = t["r1"] if m >= t["ex1"] else cr
        r2 = t["r2"] if m >= t["ex2"] else cr
        rl[i] = 0.5 * r1 + 0.5 * r2
        fired[i] = True
    usd, usd_b = rl * RK, BA * RK
    f = int(fired.sum())
    fl = int((fired & LW).sum())
    return {"R": float(rl.sum()), "USDn": float(usd.mean()),
            "ATRn": float((usd / ATRE).mean()),
            "Qstop": float((rl <= -1.0 + 1e-9).mean()), "fired": f,
            "skip": int(skipped.sum()),
            "getoetet": int((GW & fired & (rl <= 0)).sum()),
            "dR_Gew": float((rl - BA)[GW].sum()),
            "dR_Verl": float((rl - BA)[LW].sum()),
            "USDd": float((usd - usd_b).sum()),
            "prec": fl / f if f else 0.0,
            "rec": fl / int(LW.sum()) if LW.sum() else 0.0}


def kopf() -> None:
    print(f"   {'mfe_cap':>8}{'R gesamt':>12}{'USD/Tr':>9}{'ATR/Tr':>9}"
          f"{'Q_stop':>8}{'Feuer':>7}{'Skip':>6}{'Prec':>7}{'Rec':>7}"
          f"{'getoetet':>9}{'dR Gew':>10}{'dR Verl':>10}{'USD-D':>10}")


def zeile(cap: float, e: Dict) -> None:
    nm = "aus" if cap >= 1e8 else f"{cap:.2f}"
    print(f"   {nm:>8}{e['R']:>12.4f}{e['USDn']:>+9.4f}{e['ATRn']:>+9.4f}"
          f"{e['Qstop']:>8.3f}{e['fired']:>7}{e['skip']:>6}{e['prec']:>7.3f}"
          f"{e['rec']:>7.3f}{e['getoetet']:>9}{e['dR_Gew']:>+10.2f}"
          f"{e['dR_Verl']:>+10.2f}{e['USDd']:>+10.4f}")


print("=" * 122)
print(f"E-31b MFE-BEDINGTE SCHLIESSUNG -- {MODE.upper()}  n = {len(TR)}")
print("=" * 122)
print(f"   Basis: R {BA.sum():+.6f}  USD/Tr {(BA*RK).mean():+.4f}  "
      f"Q_stop {(BA <= -1e-9).mean():.3f}")
print("")
print("   Regel: Bruch (1 Close jenseits `basis`) schliesst NUR, wenn MFE vor")
print("   dem Bruch < mfe_cap R. Sonst laeuft der Trade unveraendert weiter.")
kopf()
for cap in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 1e9):
    zeile(cap, wende_an(cap))

print("")
print("P6b -- MFE_vor_Bruch der FEUERNDEN Trades, nach Basis-Ausgang")
print(f"   {'Gruppe':<22}{'n':>5}{'p25':>8}{'median':>9}{'p75':>8}{'max':>9}")
for gname, mask in (("Basis-Gewinner", GW), ("Basis-Verlierer", LW)):
    vals = []
    for i, t in enumerate(TR):
        if not mask[i]:
            continue
        j = first_break(t)
        if j is None:
            continue
        vals.append(t["mfes"][j - 1] if j > 0 else -1e9)
    if not vals:
        continue
    v = np.array(vals)
    print(f"   {gname:<22}{len(v):>5}{np.percentile(v,25):>8.2f}"
          f"{np.median(v):>9.2f}{np.percentile(v,75):>8.2f}{v.max():>9.2f}")
print("")
print(f"ENDE E-31b {MODE.upper()}")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
