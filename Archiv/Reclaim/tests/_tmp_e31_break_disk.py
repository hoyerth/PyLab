# -*- coding: utf-8 -*-
"""E-31 (read-only) -- DISKRIMINATION DER HYBRID-SCHLIESSUNG.

Aufruf: python test/_tmp_e31_break_disk.py <s2|aug>

Frage (Anwender, Schritt 2): Welche kausale Bruchbedingung am Schliess-Bar
trennt die *berechtigten* Stopp-Outs von jenen Gewinnern, die ein pauschaler
Bruch-Exit toeten wuerde?

Grundlage: die in E-29 gesicherten Setup-Geometrien
(`_tmp_e29_setups_<mode>_b60.pkl`), Kernstandard `geg960poc`, num_bins 60.
Keine Engine-Aenderung -- reine Offline-Simulation ueber dieselbe
Halb-Exit-Semantik wie `_c_loese_trade` (Engine Z. 1596-1647).

Regelfamilie (kausal, am Close des Bars m):
    Ein "Bruch" liegt vor, wenn die letzten `n_consec` Closes die
    Einstiegskante (`basis`) um mindestens `d_thresh * ATR14(m)`
    ueberschritten haben (Richtung: gegen die Position).

Wirkung: die feuernde Regel schliesst die zu diesem Zeitpunkt noch offenen
Haelften zum Close von m; eine bereits natuerlich geschlossene Haelfte
behaelt ihr Ergebnis. Optional `loss_only`: nur schliessen, wenn die
Position zum Bruchzeitpunkt nicht im Gewinn steht.

Pflichtmetriken (Metrik-Urkunde E-30/I4): USD/Trade, dR Gewinner, Q_stop.
Zusaetzlich Diskriminationsguete: Precision (Anteil der Feuerungen auf
Basis-Verlierern), Recall (Anteil der Basis-Verlierer mit Feuerung).
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
OUT = ROOT / "test" / f"_tmp_e31_break_disk_{MODE}_out.txt"
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
    """Eine Halb-Position (Engine-Semantik, Stop gewinnt bei Gleichstand)."""
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


# ------------------------------------------------- Vorberechnung je Trade
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
        atr = atr14(m) or 1e-9
        dists.append((((c - basis) if short else (basis - c)) / atr))
        h, l = float(hi[m]), float(lo[m])
        exc = ((entry - l) if short else (h - entry)) / risk
        mfes.append(max(mfes[-1] if mfes else 0.0, exc))
    TR.append({"s": s, "bar": int(s["bar"]), "entry": entry, "risk": risk,
               "short": short, "basis": basis, "r1": r1, "r2": r2,
               "ex1": ex1, "ex2": ex2, "base_r": 0.5 * r1 + 0.5 * r2,
               "ms": ms, "crs": crs, "dists": dists, "mfes": mfes,
               "e_bar": e_bar})

RK = np.array([t["risk"] for t in TR])
ATRE = np.array([atr14(t["bar"]) for t in TR])
BA = np.array([t["base_r"] for t in TR])
GW, LW = BA > 0, BA <= 0


def find_break(t: Dict, n_consec: int, d_thresh: float) -> Optional[int]:
    ds = t["dists"]
    for j in range(len(ds)):
        if j + 1 < n_consec:
            continue
        if all(ds[j - i] >= d_thresh for i in range(n_consec)):
            return j
    return None


def wende_an(n_consec: int, d_thresh: float, loss_only: bool = False) -> Dict:
    rl = np.zeros(len(TR))
    fired = np.zeros(len(TR), dtype=bool)
    for i, t in enumerate(TR):
        j = find_break(t, n_consec, d_thresh)
        if j is None:
            rl[i] = t["base_r"]
            continue
        m, cr = t["ms"][j], t["crs"][j]
        r1 = t["r1"] if m >= t["ex1"] else cr
        r2 = t["r2"] if m >= t["ex2"] else cr
        br = 0.5 * r1 + 0.5 * r2
        if loss_only and br > 0:
            rl[i] = t["base_r"]
            continue
        rl[i] = br
        fired[i] = True
    usd = rl * RK
    usd_b = BA * RK
    f = int(fired.sum())
    fl = int((fired & LW).sum())
    return {"R": float(rl.sum()), "USDn": float(usd.mean()),
            "ATRn": float((usd / ATRE).mean()),
            "Qstop": float((rl <= -1.0 + 1e-9).mean()),
            "fired": f, "getoetet": int((GW & fired & (rl <= 0)).sum()),
            "dR_Gew": float((rl - BA)[GW].sum()),
            "dR_Verl": float((rl - BA)[LW].sum()),
            "USDd": float((usd - usd_b).sum()),
            "prec": fl / f if f else 0.0,
            "rec": fl / int(LW.sum()) if LW.sum() else 0.0}


def kopf() -> None:
    print(f"   {'n':>2} {'d_ATR':>6}{'R gesamt':>12}{'USD/Tr':>9}{'ATR/Tr':>9}"
          f"{'Q_stop':>8}{'Feuer':>7}{'Prec':>7}{'Rec':>7}{'getoetet':>9}"
          f"{'dR Gew':>10}{'dR Verl':>10}{'USD-D':>10}")


def zeile(n_c: int, d_t: float, e: Dict) -> None:
    print(f"   {n_c:>2} {d_t:>6.2f}{e['R']:>12.4f}{e['USDn']:>+9.4f}"
          f"{e['ATRn']:>+9.4f}{e['Qstop']:>8.3f}{e['fired']:>7}{e['prec']:>7.3f}"
          f"{e['rec']:>7.3f}{e['getoetet']:>9}{e['dR_Gew']:>+10.2f}"
          f"{e['dR_Verl']:>+10.2f}{e['USDd']:>+10.4f}")


print("=" * 118)
print(f"E-31 DISKRIMINATION DER HYBRID-SCHLIESSUNG -- {MODE.upper()}  "
      f"n = {len(TR)}  (Kernstandard geg960poc)")
print("=" * 118)
print(f"Engine : {eng.__file__}")

# --------------------------------------------------------------------- P0
print("")
print("P0 -- FIDELITAET (Basis ohne Regel)")
print(f"   R gesamt {BA.sum():+.6f}   USD/Tr {(BA*RK).mean():+.4f}   "
      f"ATR/Tr {((BA*RK)/ATRE).mean():+.4f}   Q_stop "
      f"{(BA <= -1.0+1e-9).mean():.3f}")

# --------------------------------------------------------------------- P1
print("")
print("P1 -- NAIVER BRUCH (n=1, d=0) -- Abgleich mit E-29/T4c")
print(f"   {'Kennzahl':<22}{'Basis':>14}{'Regel':>14}{'Differenz':>14}")
e1 = wende_an(1, 0.0)
for lab, a, b in (("R gesamt", BA.sum(), e1["R"]),
                  ("USD/Trade", (BA * RK).mean(), e1["USDn"]),
                  ("ATR/Trade", ((BA * RK) / ATRE).mean(), e1["ATRn"]),
                  ("Q_stop", (BA <= -1e-9).mean(), e1["Qstop"])):
    print(f"   {lab:<22}{a:>14.4f}{b:>14.4f}{b - a:>+14.4f}")
print(f"   {'getoetete Gewinner':<22}{0:>14}{e1['getoetet']:>14}")
print(f"   {'dR Gewinner':<22}{0.0:>14.4f}{e1['dR_Gew']:>+14.4f}")
print(f"   {'dR Verlierer':<22}{0.0:>14.4f}{e1['dR_Verl']:>+14.4f}")
print(f"   Preisfall: Feuerungen {e1['fired']}, Precision {e1['prec']:.3f}, "
      f"Recall {e1['rec']:.3f}")
print("")
print("   Hinweis: E-29/T4c ersetzte den GESAMT-R eines Trades durch den")
print("   EINZEL-Halb-R am Bruch-Close (und traf damit auch laufende Gewinner")
print("   im Plus). Hier wird praezise je offener Haelfte geschlossen; die")
print("   Zahlen weichen deshalb ab -- die Richtung des Befunds nicht.")

# --------------------------------------------------------------------- P2
print("")
print("P2 -- REGEL-SWEEP 'always' (Schliessung unabhaengig vom P&L-Stand)")
kopf()
for nc in (1, 2, 3):
    for dt in (0.0, 0.25, 0.5, 1.0):
        zeile(nc, dt, wende_an(nc, dt, loss_only=False))

# --------------------------------------------------------------------- P3
print("")
print("P3 -- REGEL-SWEEP 'loss_only' (schliesst nur ohne Gewinn; dR Gewinner "
      "strukturell 0)")
kopf()
for nc in (1, 2, 3):
    for dt in (0.0, 0.25, 0.5, 1.0):
        zeile(nc, dt, wende_an(nc, dt, loss_only=True))

# --------------------------------------------------------------------- P4
print("")
print("P4 -- MARKTSTRUKTUR AM ERSTEN BRUCH (n=1, d=0): was unterscheidet "
      "Basis-Gewinner von Basis-Verlierern?")
print(f"   {'Gruppe':<26}{'n':>5}{'Bruch@+bars':>12}{'Dist[ATR]':>11}"
      f"{'MFE_vor[Bruc]':>14}{'base_R med':>12}{'base_R Summe':>14}")
gruppen = (("Basis-Gewinner (r>0)", GW), ("Basis-Verlierer (r<=0)", LW))
for gname, mask in gruppen:
    bb, dd, mm, bb_r = [], [], [], []
    for i, t in enumerate(TR):
        if not mask[i]:
            continue
        j = find_break(t, 1, 0.0)
        if j is None:
            continue
        bb.append(t["ms"][j] - t["e_bar"])
        dd.append(t["dists"][j])
        mm.append(t["mfes"][j - 1] if j > 0 else t["mfes"][j])
        bb_r.append(t["base_r"])
    if not bb:
        continue
    bb_, dd_, mm_ = np.array(bb), np.array(dd), np.array(mm)
    print(f"   {gname:<26}{len(bb):>5}{np.median(bb_):>12.1f}"
          f"{np.median(dd_):>11.2f}{np.median(mm_):>14.2f}"
          f"{np.median(bb_r):>12.2f}{sum(bb_r):>+14.2f}")
print("")
print("   (MFE_vor[Bruc] = guenstigste Exkursion VOR dem Bruch-Bar, in R.)")

# --------------------------------------------------------------------- P5
print("")
print("P5 -- TRENNSCHAERFE: Verteilung der Bruch-Distanz (n=1, d=0)")
print(f"   {'Gruppe':<26}{'p25':>8}{'median':>9}{'p75':>8}"
      f"{'Anteil Dist<0.25 ATR':>22}{'Anteil Dist<0.5 ATR':>21}")
for gname, mask in gruppen:
    dd = []
    for i, t in enumerate(TR):
        if not mask[i]:
            continue
        j = find_break(t, 1, 0.0)
        if j is not None:
            dd.append(t["dists"][j])
    if not dd:
        continue
    dd_ = np.array(dd)
    print(f"   {gname:<26}{np.percentile(dd_,25):>8.2f}"
          f"{np.median(dd_):>9.2f}{np.percentile(dd_,75):>8.2f}"
          f"{(dd_ < 0.25).mean()*100:>21.1f}%{(dd_ < 0.5).mean()*100:>20.1f}%")
print("")
print(f"ENDE E-31 {MODE.upper()}")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
