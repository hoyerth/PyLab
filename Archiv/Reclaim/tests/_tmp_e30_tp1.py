# -*- coding: utf-8 -*-
"""E-30 Schritt 1 (read-only) -- ZIELABSTANDS-GEOMETRIE + TP1-DECKELUNG.

Konfiguration: arretierter Kernstandard `geg960poc` (E-28/E-29), num_bins 60.
Datenquelle: die in E-29 gesicherten Setup-Geometrien
(`_tmp_e29_setups_<mode>_b60.pkl`) -- keine Engine-Aenderung.

Drei Auswertungen:
  Z1  Verteilung des Zielabstands Entry -> TP1(POC) und Entry -> TP2,
      je in [R], [ATR14] und [% Kursweg], getrennt H1 / H2.
  Z2  MFE-Anatomie der Stop-Outs: wie weit lief der Trade, wieviel davon
      wurde zurueckgegeben (MFE - End-R)?
  Z3  TP1-DECKEL SWEEP (zwei Skalen):
        Cap_R   : tp1_eff = entry +/- min(|poc-entry|, Cap_R  * risk)
        Cap_ATR : tp1_eff = entry +/- min(|poc-entry|, Cap_ATR * atr14)
      TP2 bleibt unveraendert (Makroziel). Pflichtmetriken je Wert:
      R ges., USD/Trade, ATR/Trade, Q_stop, Gewinner, getoetete Gewinner,
      gerettete Verlierer.

Aufruf: python test/_tmp_e30_tp1.py <s2|aug>
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
OUT = ROOT / "test" / f"_tmp_e30_tp1_{MODE}_out.txt"
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


# ----------------------------------------------------------------- Simulation
def sim_halb(entry: float, risk: float, sl: float, ziel: float, e_bar: int,
             short: bool) -> Tuple[float, int]:
    """Eine Halb-Position gegen Stop/Ziel (Engine-Semantik, Stop gewinnt bei
    Gleichstand). Rueckgabe (r, exit_bar)."""
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


def mfe_bis_stop(entry: float, risk: float, sl: float, e_bar: int,
                 short: bool) -> float:
    """MFE in R bis zum Stop (oder Fensterende)."""
    nb = len(hi) - e_bar
    mfe = 0.0
    for m in range(nb):
        h, l = float(hi[e_bar + m]), float(lo[e_bar + m])
        if short and h >= sl:
            return mfe
        if (not short) and l <= sl:
            return mfe
        mfe = max(mfe, ((entry - l) if short else (h - entry)) / risk)
    return mfe


def trade_r(s: Dict, cap_r: Optional[float] = None,
            cap_atr: Optional[float] = None) -> float:
    e_bar = int(s["entry_bar"])
    entry = float(s["entry"])
    risk = abs(float(s["sl"]) - entry) or 1e-9
    short = s["richtung"] == "SHORT"
    tp1 = float(s["poc"])
    if cap_r is not None:
        tp1 = entry + (-1 if short else 1) * min(abs(tp1 - entry), cap_r * risk)
    elif cap_atr is not None:
        tp1 = entry + (-1 if short else 1) * min(abs(tp1 - entry),
                                                 cap_atr * atr14(int(s["bar"])))
    r1, _ = sim_halb(entry, risk, float(s["sl"]), tp1, e_bar, short)
    r2, _ = sim_halb(entry, risk, float(s["sl"]), float(s["tp2"]), e_bar, short)
    return 0.5 * r1 + 0.5 * r2


def auswertung(cap_r: Optional[float] = None,
               cap_atr: Optional[float] = None) -> Dict:
    rl: List[float] = []
    base_rl: List[float] = []
    for s in S:
        rl.append(trade_r(s, cap_r, cap_atr))
        base_rl.append(float(s["r"]))
    risk = np.array([abs(s["sl"] - s["entry"]) for s in S])
    rl_a, ba = np.array(rl), np.array(base_rl)
    delta = rl_a - ba
    usd, usd_b = rl_a * risk, ba * risk
    atr = np.array([atr14(int(s["bar"])) for s in S])
    tot = len(S)
    gw, lw = ba > 0, ba <= 0
    return {
        "R": float(rl_a.sum()), "USDn": float(usd.mean()),
        "ATRn": float((usd / atr).mean()), "USD": float(usd.sum()),
        "Qstop": float((rl_a <= -1.0 + 1e-9).mean()),
        "gew": int((rl_a > 0).sum()),
        "getoetet": int(((ba > 0) & (rl_a <= 0)).sum()),
        "gerettet": int(((ba <= 0) & (rl_a > 0)).sum()),
        "geaendert": int((np.abs(rl_a - ba) > 1e-9).sum()),
        "dR_Gew": float(delta[gw].sum()) if gw.any() else 0.0,
        "dR_Verl": float(delta[lw].sum()) if lw.any() else 0.0,
        "USDd": float((usd - usd_b).sum()),
        "n": tot,
    }


def zeile(name: str, e: Dict) -> None:
    print(f"{name:<20}{e['R']:>12.5f}{e['USDn']:>+9.4f}{e['ATRn']:>+9.4f}"
          f"{e['Qstop']:>8.3f}{e['getoetet']:>9}{e['gerettet']:>9}"
          f"{e['dR_Gew']:>+11.3f}{e['dR_Verl']:>+10.3f}{e['USDd']:>+11.4f}")


print("=" * 108)
print(f"E-30/S1 ZIELABSTAND + TP1-DECKEL -- {MODE.upper()}  "
      f"Kernstandard geg960poc  n = {len(S)}")
print("=" * 108)
print(f"Engine : {eng.__file__}")

# --------------------------------------------------------------------- Z1
print("")
print("Z1 -- ZIELABSTAENDE (Entry -> TP1/POC  bzw.  Entry -> TP2/Gegenkante)")
print(f"   {'Gruppe':<9}{'Groesse':<10}{'min':>9}{'p25':>9}{'median':>9}"
      f"{'p75':>9}{'p90':>9}{'max':>10}")
for gname, sel in (("gesamt", S),
                   ("H1", [s for s in S if s["bar"] < SPLIT]),
                   ("H2", [s for s in S if s["bar"] >= SPLIT])):
    if not sel:
        continue
    risk = np.array([abs(s["sl"] - s["entry"]) for s in sel])
    dpoc = np.array([abs(s["poc"] - s["entry"]) for s in sel])
    dtp2 = np.array([abs(s["tp2"] - s["entry"]) for s in sel])
    atr = np.array([atr14(int(s["bar"])) for s in sel])
    ent = np.array([s["entry"] for s in sel])
    for label, v in (("d TP1 [R]", dpoc / risk), ("d TP1 [ATR]", dpoc / atr),
                     ("d TP1 [%]", dpoc / ent * 100.0),
                     ("d TP2 [R]", dtp2 / risk), ("d TP2 [ATR]", dtp2 / atr),
                     ("risk [ATR]", risk / atr)):
        print(f"   {gname:<9}{label:<10}{v.min():>9.2f}{np.percentile(v,25):>9.2f}"
              f"{np.median(v):>9.2f}{np.percentile(v,75):>9.2f}"
              f"{np.percentile(v,90):>9.2f}{v.max():>10.2f}")
    print(f"   {'':<9}{'n':<10}{len(sel):>9}")

# --------------------------------------------------------------------- Z2
print("")
print("Z2 -- MFE-ANATOMIE DER STOP-OUTS (r <= -1)")
print(f"   {'Haelfte':<8}{'n_Stop':>7}{'MFE>=1R':>9}{'MFE>=2R':>9}"
      f"{'MFE med':>9}{'Rueckgabe med':>14}{'Anteil MFE gegeben':>20}")
for gname, sel in (("gesamt", S), ("H1", [s for s in S if s["bar"] < SPLIT]),
                   ("H2", [s for s in S if s["bar"] >= SPLIT])):
    stops = [s for s in sel if float(s["r"]) <= -1.0 + 1e-9]
    if not stops:
        continue
    mfes = np.array([mfe_bis_stop(float(s["entry"]),
                                  abs(float(s["sl"]) - float(s["entry"])) or 1e-9,
                                  float(s["sl"]), int(s["entry_bar"]),
                                  s["richtung"] == "SHORT") for s in stops])
    rk = mfes + 1.0                     # Rueckgabe = MFE bis Endstand -1 R
    anteil = np.where(mfes > 0, rk / np.maximum(mfes, 1e-9), 0.0)
    print(f"   {gname:<8}{len(stops):>7}{int((mfes>=1).sum()):>9}"
          f"{int((mfes>=2).sum()):>9}{np.median(mfes):>9.2f}"
          f"{np.median(rk):>14.2f}{np.median(anteil)*100:>19.1f}%")

# --------------------------------------------------------------------- Z3
print("")
print("Z3 -- TP1-DECKEL SWEEP (TP2 unveraendert)")
print(f"   {'Variante':<20}{'R gesamt':>12}{'USD/Tr':>9}{'ATR/Tr':>9}"
      f"{'Q_stop':>8}{'getoetet':>9}{'gerettet':>9}{'dR Gewinner':>12}"
      f"{'dR Verlier':>11}{'USD-Delta':>12}")
print("   " + "-" * 108)
zeile("BASIS (Cap aus)", auswertung())
for c in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0):
    zeile(f"Cap_R   = {c:.2f} R", auswertung(cap_r=c))
print("   " + "-" * 104)
for c in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
    zeile(f"Cap_ATR = {c:.2f} ATR", auswertung(cap_atr=c))
print("")
print("Legende: 'Gew' = Gewinner (r > 0). 'getoetet' = Gewinner der Basis, die")
print("durch den Cap verlieren. 'gerettet' = Verlierer der Basis, die durch den")
print("Cap gewinnen. Pflichtmetrik: getoetet klein, USD/Trade gross.")

# --------------------------------------------------------------------- Z4
# Dekomposition: WOHER kommt R? Beide Haelften sind unabhaengig (Engine).
print("")
print("Z4 -- DEKOMPOSITION DER BEIDEN HAELFTEN (Basis, kein Cap)")
print(f"   {'Gruppe':<8}{'n':>5}{'H1 TP':>7}{'H1 SL':>7}{'H1 ENDE':>9}"
      f"{'H2 TP':>7}{'H2 SL':>7}{'H2 ENDE':>9}"
      f"{'Sum r1':>10}{'Sum r2':>10}{'Beitrag 50/50':>15}")
for gname, sel in (("gesamt", S), ("H1", [s for s in S if s["bar"] < SPLIT]),
                   ("H2", [s for s in S if s["bar"] >= SPLIT])):
    cnt: Dict[str, int] = {"H1 TP": 0, "H1 SL": 0, "H1 ENDE": 0,
                           "H2 TP": 0, "H2 SL": 0, "H2 ENDE": 0}
    s1 = s2 = 0.0
    for s in sel:
        e_bar = int(s["entry_bar"])
        entry = float(s["entry"])
        risk = abs(float(s["sl"]) - entry) or 1e-9
        short = s["richtung"] == "SHORT"
        r1, _ = sim_halb(entry, risk, float(s["sl"]), float(s["poc"]),
                         e_bar, short)
        r2, _ = sim_halb(entry, risk, float(s["sl"]), float(s["tp2"]),
                         e_bar, short)
        # Ziel-Erkennung aus den Halb-Rueckgaben (SL ist per Definition -1.0)
        for pre, ziel, rv in (("H1", float(s["poc"]), r1),
                              ("H2", float(s["tp2"]), r2)):
            if abs(rv + 1.0) < 1e-9:
                cnt[pre + " SL"] += 1
            elif abs(rv - (ziel - entry) / risk * (1 if not short else -1)) < 1e-6:
                cnt[pre + " TP"] += 1
            else:
                cnt[pre + " ENDE"] += 1
        s1 += r1
        s2 += r2
    n = len(sel)
    print(f"   {gname:<8}{n:>5}{cnt['H1 TP']:>7}{cnt['H1 SL']:>7}"
          f"{cnt['H1 ENDE']:>9}{cnt['H2 TP']:>7}{cnt['H2 SL']:>7}"
          f"{cnt['H2 ENDE']:>9}{s1:>+10.3f}{s2:>+10.3f}"
          f"{(0.5*s1+0.5*s2):>+15.3f}")

print("")
print("Z5 -- GEWICHTS-SWEEP w1 (Anteil auf TP1/POC; TP-Ziele unveraendert)")
print("      w1 = tp1_anteil_pct/100. Alternativen zur arretierten 50/50-Teilung.")
print(f"   {'w1':>6}{'w2':>6}{'R gesamt':>13}{'USD/Tr':>9}{'ATR/Tr':>9}"
      f"{'Q_stop':>8}{'R-H1-Anteil':>14}{'R-H2-Anteil':>14}")
_r1v = np.array([sim_halb(float(s["entry"]),
                          abs(float(s["sl"]) - float(s["entry"])) or 1e-9,
                          float(s["sl"]), float(s["poc"]), int(s["entry_bar"]),
                          s["richtung"] == "SHORT")[0] for s in S])
_r2v = np.array([sim_halb(float(s["entry"]),
                          abs(float(s["sl"]) - float(s["entry"])) or 1e-9,
                          float(s["sl"]), float(s["tp2"]), int(s["entry_bar"]),
                          s["richtung"] == "SHORT")[0] for s in S])
_risk = np.array([abs(s["sl"] - s["entry"]) for s in S])
_atr = np.array([atr14(int(s["bar"])) for s in S])
for w1 in (0.0, 0.25, 0.5, 0.75, 1.0):
    rm = w1 * _r1v + (1.0 - w1) * _r2v
    usd = rm * _risk
    print(f"   {w1:>6.2f}{1.0-w1:>6.2f}{rm.sum():>+13.5f}{usd.mean():>+9.4f}"
          f"{(usd/_atr).mean():>+9.4f}{(rm<=-1.0+1e-9).mean():>8.3f}"
          f"{(w1*_r1v).sum():>+14.3f}{((1-w1)*_r2v).sum():>+14.3f}")
print("")
print("   KERNLESUNG: Ist die Halb-2 (TP2 = Gegenkante) ein systematischer")
print("   Verlusttraeger, dann ist nicht die TP1-Weite der Hebel, sondern die")
print("   Aufteilung (w1) bzw. das Vorhandensein der zweiten Haelfte.")
print("")
print(f"ENDE E-30/S1 {MODE.upper()}")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
