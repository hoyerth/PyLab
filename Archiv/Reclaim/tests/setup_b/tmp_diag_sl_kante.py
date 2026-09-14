# test/tmp_diag_sl_kante.py
"""SIMULATION: KANTE-BASIERTER SL statt SL_PCT-vom-Entry (v7-arm Segmentierung).

Hypothese (User): SL_PCT vom Entry rutscht bei Reclaim-Einstiegen in die
Struktur (SL UNTER der Kante) -> normaler Kante-Retest stoppt den Trade.
Kante-basierter SL = Kante + Puffer (fuer SHORT: U + puffer; LONG: L - puffer).

Risiko (User): Kante-SL ist weiter weg -> hoeheres Risk -> kleineres R je
Trade und CRV faellt unter MIN_RECLAIM_CRV -> Signale fallen durch.

Simuliert wird auf der v7-arm-Segmentierung (B1..B4, August):
  Varianten: entry (Baseline, SL_PCT vom Entry)
             kante+0.00 / +0.05 / +0.10 / +0.15 (DENSITY_BAND) / +0.25
             kante+pct (Kante * (1+SL_PCT%) - analog, aber von der Kante)
  CRV-Modus: - "crv1"  = MIN_RECLAIM_CRV=1.0 beibehalten
             - "crv0"  = CRV-Filter aus (nur e>POC / Bo / CD behalten)
Aufruf: python test/tmp_diag_sl_kante.py [crv1|crv0]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"
src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "sl_kante_diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
_laufende_zone = ns["_laufende_zone"]
_bounce_nr = ns["_bounce_nr"]
_aufloesen = ns["_aufloesen"]
level_schnittmenge = ns["level_schnittmenge"]
pd = ns["pd"]
np = ns["np"]

TOL_KANTE = 0.30
MIN_WEITE_PCT = 1.5
CRV_MODE = sys.argv[1] if len(sys.argv) > 1 else "crv1"

# --- V-MOVE-Filter-Parameter (wie v7 arm) ---
VMOVE_AUSREISSER_PCT = 1.5
VMOVE_ANSTIEG_PCT = 4.0
VMOVE_MAX_BARS = 150


def reife_check(P, tol_kante=TOL_KANTE, min_weite_pct=MIN_WEITE_PCT):
    h_prices = P.get("h_prices", P.get("h", []))
    h_ts = P.get("h_ts", [])
    l_prices = P.get("l_prices", P.get("l", []))
    l_ts = P.get("l_ts", [])
    events = sorted([(t, "H", float(p)) for p, t in zip(h_prices, h_ts)] +
                    [(t, "L", float(p)) for p, t in zip(l_prices, l_ts)])
    for i in range(len(events) - 2):
        t1, typ1, p1 = events[i]
        t2, typ2, p2 = events[i + 1]
        t3, typ3, p3 = events[i + 2]
        if typ1 == typ2 or typ2 == typ3:
            continue
        if typ1 != typ3:
            continue
        if abs(p1 - p3) > tol_kante:
            continue
        weite = abs(p2 - p1) / min(p1, p2) * 100.0
        if weite >= min_weite_pct:
            return True, t3, (typ1, p1, typ2, p2, typ3, p3)
    return False, None, None


def vmove_check(P, P_prev):
    if P_prev is None or len(P.get("l_prices", [])) == 0:
        return False, None, None, None, None, None
    vz_prev = P_prev.get("vol_zone")
    if vz_prev is None:
        return False, None, None, None, None, None
    L_ref = vz_prev["L_zone"]
    l_prices = P["l_prices"]
    l_ts = P["l_ts"]
    k = int(np.argmin(l_prices))
    l_min = float(l_prices[k])
    t_tief = l_ts[k]
    ausreisser = (L_ref - l_min) / L_ref * 100.0
    if l_min >= L_ref * (1 - VMOVE_AUSREISSER_PCT / 100.0):
        return False, None, None, None, None, None
    t_end = t_tief + pd.Timedelta(minutes=VMOVE_MAX_BARS * 15)
    h_max = -np.inf
    for Pk in phases[phases.index(P):]:
        for pr, t in zip(Pk.get("h_prices", []), Pk.get("h_ts", [])):
            if t > t_tief and t <= t_end and pr > h_max:
                h_max = float(pr)
        if Pk["ende"] > t_end:
            break
    if not np.isfinite(h_max):
        return False, None, None, None, None, None
    anstieg = (h_max - l_min) / l_min * 100.0
    if anstieg < VMOVE_ANSTIEG_PCT:
        return False, None, None, None, None, None
    return True, t_tief, l_min, h_max, ausreisser, anstieg


# --- Segmentierung (v7 arm) ---
reif_info = []
vmove_info = []
for i, P in enumerate(phases, 1):
    reif, t_reif, tripel = reife_check(P)
    P_prev = phases[i - 2] if i >= 2 else None
    vm, t_v, p_v, h_v, ausr, anst = vmove_check(P, P_prev)
    reif_info.append((P, reif, t_reif))
    vmove_info.append((vm, t_v, p_v, h_v, ausr, anst))

seg_start = [False] * len(phases)
for i in range(len(phases)):
    reif = reif_info[i][1]
    vm = vmove_info[i][0]
    if reif:
        seg_start[i] = True
    elif vm:
        seg_start[i] = False
    if i > 0 and vmove_info[i - 1][0]:
        seg_start[i] = True

boxen = []
aktive = None
for i, P in enumerate(phases):
    if seg_start[i]:
        if aktive is not None:
            boxen.append(aktive)
        aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                  "phasen": [i + 1], "start": P["start"], "ende": P["ende"],
                  "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                  "l": list(P["l_prices"]), "l_ts": list(P["l_ts"])}
    else:
        if aktive is None:
            aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                      "phasen": [i + 1], "start": P["start"], "ende": P["ende"],
                      "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                      "l": list(P["l_prices"]), "l_ts": list(P["l_ts"])}
        else:
            aktive["i_ende"] = P["i_ende"]
            aktive["ende"] = P["ende"]
            aktive["phasen"].append(i + 1)
            aktive["h"].extend(P["h_prices"])
            aktive["h_ts"].extend(P["h_ts"])
            aktive["l"].extend(P["l_prices"])
            aktive["l_ts"].extend(P["l_ts"])
if aktive is not None:
    boxen.append(aktive)
n = len(df)
for k, b in enumerate(boxen):
    if k + 1 < len(boxen):
        b["i_ende"] = min(boxen[k + 1]["i_start"] - 1, n - 1)
    else:
        b["i_ende"] = n - 1
    b["ende"] = df["ts"].iloc[b["i_ende"]]

print(f"Boxen v7-arm: {len(boxen)}")
for bi, b in enumerate(boxen, 1):
    print(f"  B{bi}: P{'+'.join(f'P{p}' for p in b['phasen'])} "
          f"{b['start']:%d.%m %H:%M}-{b['ende']:%d.%m %H:%M}")


def _aufloesen_mit_sl(df, s):
    """Wie ns['_aufloesen'], nutzt aber den vorgegebenen SL (s['sl'])
    statt intern SL_PCT vom Entry. Konservativ: SL und TP gleiche Bar -> SL zuerst.
    """
    e_bar = s["einstieg_bar"]
    entry = s["einstieg_preis"]
    typ = s["typ"]
    tp1, tp2 = s["tp1"], s["tp2"]
    sl_init = float(s["sl"])
    hi = df["high"].values[e_bar:]
    lo = df["low"].values[e_bar:]
    cl = df["close"].values[e_bar:]
    n = len(hi)
    risk = abs(sl_init - entry)
    if risk <= 0:
        risk = 1e-9

    def _first(mask):
        return int(np.argmax(mask)) if mask.any() else n

    def _r(exit_price):
        return ((entry - exit_price) / risk if typ == "SHORT"
                else (exit_price - entry) / risk)

    if typ == "SHORT":
        t1 = _first(lo <= tp1)
        t2 = _first(lo <= tp2)
        t_sl_i = _first(hi >= sl_init)
    else:
        t1 = _first(hi >= tp1)
        t2 = _first(hi >= tp2)
        t_sl_i = _first(lo <= sl_init)

    # Haelfte 1: TP1 (POC)
    if t1 < t_sl_i:
        r1, ex1, g1 = _r(tp1), tp1, "TP1"
    elif t_sl_i < t1:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    elif t_sl_i < n:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    else:
        r1, ex1, g1 = _r(cl[-1]), cl[-1], "ENDE"

    # Haelfte 2: TP2, SL bleibt am Einstiegs-SL (kein Nachzug)
    t_sl2 = t_sl_i
    if t2 < t_sl2:
        r2, ex2, g2 = _r(tp2), tp2, "TP2"
    elif t_sl2 < n:
        r2, ex2, g2 = _r(sl_init), sl_init, "SL"
    else:
        r2, ex2, g2 = _r(cl[-1]), cl[-1], "ENDE"

    _w1 = ns["ANTEIL_TP1"] / 100.0
    _w2 = 1.0 - _w1
    if _w2 <= 0:
        r2, g2 = 0.0, "-"
    r_mult = _w1 * r1 + _w2 * r2
    resultat = ("GEWONNEN" if r_mult > 1e-9
                else ("VERLOREN" if r_mult < -1e-9 else "NEUTRAL"))
    return {"r1": r1, "r2": r2, "exit1": ex1, "exit2": ex2,
            "grund1": g1, "grund2": g2,
            "pnl": r_mult * risk, "r_mult": r_mult, "resultat": resultat,
            "tp1_hit": g1 == "TP1", "tp2_hit": g2 == "TP2",
            "sl_hit1": g1 == "SL", "sl_hit2": g2 == "SL",
            "sl_init": sl_init}


def find_signals_sl(ns, box, sl_art, puffer, crv_mode):
    """find_signals_box mit SL-Variante.

    sl_art:
      "entry"   : SL = Entry * (1 +/- SL_PCT%)  (Baseline)
      "kante"   : SL = Kante + puffer            (SHORT: U+p, LONG: L-p)
      "kante_pct": SL = Kante * (1 +/- SL_PCT%)  (analog Entry-Formel, aber von Kante)
    crv_mode: "crv1" nutzt MIN_RECLAIM_CRV, "crv0" deaktiviert den CRV-Filter.
    """
    df = ns["df"]
    p = {"i_start": box["i_start"], "i_ende": box["i_ende"],
         "h_prices": box["h"], "h_ts": box["h_ts"],
         "l_prices": box["l"], "l_ts": box["l_ts"]}
    sigs = []
    hi, lo, cl, op = (df["high"].values, df["low"].values,
                      df["close"].values, df["open"].values)
    ts = df["ts"].values
    last_bar = {"SHORT": -10 ** 9, "LONG": -10 ** 9}
    sl_p = ns["SL_PCT"] / 100.0
    for k in range(box["i_start"], box["i_ende"]):
        vz = _laufende_zone(df, p, k)
        if vz is None:
            continue
        U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
        ts_k = ts[k]
        nb_h, nb_l = _bounce_nr(box["h"], box["h_ts"], box["l"], box["l_ts"],
                                ts_k, U, L)
        # --- SHORT ---
        if hi[k] > U:
            if cl[k] <= U:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] <= U:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis > POC
                    and nb_h >= ns["MIN_RECLAIM_BOUNCE"]
                    and k - last_bar["SHORT"] >= ns["MIN_SIGNAL_ABSTAND_BARS"]):
                if sl_art == "entry":
                    sl = e_preis * (1 + sl_p)
                elif sl_art == "kante_pct":
                    sl = U * (1 + sl_p)
                else:
                    sl = U + puffer
                tp1 = POC
                tp2 = L * (1 + ns["TP2_PUFFER_PCT"] / 100.0)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else 0
                if crv_mode == "crv0" or crv >= ns["MIN_RECLAIM_CRV"]:
                    last_bar["SHORT"] = k
                    s = {"typ": "SHORT", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U,
                         "L_laufend": L, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_h}
                    s.update(_aufloesen_mit_sl(df, s))
                    s["sl_risk"] = abs(sl - e_preis) / e_preis * 100.0
                    sigs.append(s)
        # --- LONG ---
        if lo[k] < L:
            if cl[k] >= L:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] >= L:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis < POC
                    and nb_l >= ns["MIN_RECLAIM_BOUNCE"]
                    and k - last_bar["LONG"] >= ns["MIN_SIGNAL_ABSTAND_BARS"]):
                if sl_art == "entry":
                    sl = e_preis * (1 - sl_p)
                elif sl_art == "kante_pct":
                    sl = L * (1 - sl_p)
                else:
                    sl = L - puffer
                tp1 = POC
                tp2 = U * (1 - ns["TP2_PUFFER_PCT"] / 100.0)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else 0
                if crv_mode == "crv0" or crv >= ns["MIN_RECLAIM_CRV"]:
                    last_bar["LONG"] = k
                    s = {"typ": "LONG", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U,
                         "L_laufend": L, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_l}
                    s.update(_aufloesen_mit_sl(df, s))
                    s["sl_risk"] = abs(sl - e_preis) / e_preis * 100.0
                    sigs.append(s)
    return sigs


def auswertung(sigs, label):
    w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
    l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
    r = sum(s["r_mult"] for s in sigs)
    nn = len(sigs)
    wr = 100.0 * w / (w + l) if w + l else 0.0
    avg_r = r / nn if nn else 0.0
    avg_risk = sum(s["sl_risk"] for s in sigs) / nn if nn else 0.0
    avg_crv = sum(s["crv"] for s in sigs) / nn if nn else 0.0
    print(f"  {label:<22} {nn:2d} Sig | {w}W/{l}L | {wr:3.0f}% | {r:+7.2f}R | "
          f"avg {avg_r:+.2f} | avgRisk {avg_risk:.2f}% | avgCRV {avg_crv:.2f}")
    return {"n": nn, "w": w, "l": l, "r": r, "wr": wr, "avg": avg_r,
            "risk": avg_risk, "crv": avg_crv}


print(f"\n=== SIMULATION SL-VARIANTEN (CRV-Modus: {CRV_MODE}) ===")
print("Label: kante+PUFFER = SL = Kante + PUFFER USD (SHORT: U+p, LONG: L-p)")
varianten = [
    ("entry (Baseline)", "entry", 0.0),
    ("kante+0.00", "kante", 0.00),
    ("kante+0.05", "kante", 0.05),
    ("kante+0.10", "kante", 0.10),
    ("kante+0.15 (DB)", "kante", 0.15),
    ("kante+0.25", "kante", 0.25),
    ("kante+pct (0.45%)", "kante_pct", 0.0),
]
gesamt = {}
for label, art, puff in varianten:
    alle = []
    for bi, b in enumerate(boxen, 1):
        sigs = find_signals_sl(ns, b, art, puff, CRV_MODE)
        for s in sigs:
            s["box"] = bi
        alle.extend(sigs)
    gesamt[label] = alle
    auswertung(alle, label)

# B3-Detail
print(f"\n=== B3-DETAIL (P7+P8) je Variante ===")
for label, art, puff in varianten:
    sigs = [s for s in gesamt[label] if s["box"] == 3]
    w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
    l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
    r = sum(s["r_mult"] for s in sigs)
    nn = len(sigs)
    wr = 100.0 * w / (w + l) if w + l else 0.0
    print(f"  {label:<22} {nn:2d} Sig | {w}W/{l}L | {wr:3.0f}% | {r:+7.2f}R")

# Vergleich je Trade fuer B3 (alle Varianten nebeneinander)
print(f"\n=== B3 TRADE-FÜR-TRADE Vergleich ===")
alle_b3 = gesamt["entry (Baseline)"]
alle_b3_sorted = sorted([s for s in alle_b3 if s["box"] == 3], key=lambda s: s["ts"])
for s_ref in alle_b3_sorted:
    ts = s_ref["ts"]
    print(f"\n  {ts:%d.%m %H:%M} {s_ref['typ']} (Entry {s_ref['einstieg_preis']:.3f}):")
    for label, art, puff in varianten:
        sigs = [s for s in gesamt[label] if s["box"] == 3 and s["ts"] == ts and s["typ"] == s_ref["typ"]]
        if sigs:
            s = sigs[0]
            kante = s["U_laufend"] if s["typ"] == "SHORT" else s["L_laufend"]
            print(f"    {label:<22} Kante {kante:.3f} | SL {s['sl']:.3f} "
                  f"(Risk {s['sl_risk']:.2f}%) | CRV {s['crv']:.2f} | "
                  f"{s['resultat']} {s['r_mult']:+.2f}R")
        else:
            print(f"    {label:<22} (kein Signal - CRV-Filter)")

# CRV-Ausfall-Statistik fuer kante+0.10 (repraesentativ)
print(f"\n=== CRV-AUSFALL (MIN_RECLAIM_CRV={ns['MIN_RECLAIM_CRV']}) fuer kante+0.10 ===")
alle_roh = []
for bi, b in enumerate(boxen, 1):
    sigs = find_signals_sl(ns, b, "kante", 0.10, "crv0")
    for s in sigs:
        s["box"] = bi
    alle_roh.extend(sigs)
print(f"  Signale ohne CRV-Filter: {len(alle_roh)}")
gefiltert = [s for s in alle_roh if s["crv"] < ns["MIN_RECLAIM_CRV"]]
print(f"  Davon CRV < 1.0 (fallen in crv1 raus): {len(gefiltert)}")
for s in gefiltert:
    print(f"    B{s['box']} {s['ts']:%d.%m %H:%M} {s['typ']} CRV {s['crv']:.2f} "
          f"| Risk {s['sl_risk']:.2f}% | Entry {s['einstieg_preis']:.3f} | "
          f"SL {s['sl']:.3f} | {s['resultat']} {s['r_mult']:+.2f}R")

# Risk-Verteilung fuer kante+0.10 vs. entry
print(f"\n=== RISK-VERTEILUNG (sl_risk = |SL-Entry| / Entry in %) ===")
for label in ["entry (Baseline)", "kante+0.10", "kante+0.25", "kante+pct (0.45%)"]:
    sigs = gesamt[label]
    risks = sorted(s["sl_risk"] for s in sigs)
    if not risks:
        continue
    pct50 = risks[len(risks) // 2]
    pct90 = risks[int(len(risks) * 0.9) - 1]
    mx = max(risks)
    ueber = sum(1 for r in risks if r > 0.45)
    print(f"  {label:<22} n={len(risks):2d} | min {risks[0]:.2f}% | median {pct50:.2f}% | "
          f"p90 {pct90:.2f}% | max {mx:.2f}% | >0.45%: {ueber} Trades")

# Die groessten Risk-Ausreisser bei kante+0.10 zeigen
print(f"\n=== GROESSTE RISK-AUSREISSER bei kante+0.10 (Top 5) ===")
top = sorted(gesamt["kante+0.10"], key=lambda s: -s["sl_risk"])[:5]
for s in top:
    kante = s["U_laufend"] if s["typ"] == "SHORT" else s["L_laufend"]
    print(f"  B{s['box']} {s['ts']:%d.%m %H:%M} {s['typ']} Entry {s['einstieg_preis']:.3f} "
          f"| Kante {kante:.3f} | SL {s['sl']:.3f} | Risk {s['sl_risk']:.2f}% | "
          f"{s['resultat']} {s['r_mult']:+.2f}R")
