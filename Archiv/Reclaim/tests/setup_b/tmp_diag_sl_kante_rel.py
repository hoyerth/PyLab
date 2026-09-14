# test/tmp_diag_sl_kante_rel.py
"""RELATIVER KANTE-PUFFER statt SL_PCT-vom-Entry - 2-SAMPLE-VALIDIERUNG.

Idee: SL_PCT vom Entry rutscht bei Reclaim-Einstiegen unter die Strukturkante.
Kante-SL = Kante + relativer Puffer % (SHORT: U*(1+pct), LONG: L*(1-pct)).
Der Puffer muss RELATIV sein (SILVER-Preisniveau variiert stark zwischen
Samples), daher: pct in % statt fixer USD.

Fenster:
  - August  : 2026-08-10 .. 2026-08-28  (aktuelle Feinjustierung)
  - Sample 1: 2026-02-05 .. 2026-08-28  (Hauptoptimierung)
  - Sample 2: 2025-01-01 .. 2025-12-01  (Out-of-Sample)

Effizienz: Die laufende Volume-Zone wird je Bar nur EINMAL berechnet und
alle Roh-Kandidaten (Fakeout+Reclaim, e>POC, Bo>=MIN_RECLAIM_BOUNCE)
gesammelt. Die SL-Varianten werden danach per Replay (Cooldown+CRV-Filter)
angewendet -> die teure Zonen-Berechnung skaliert nicht mit der Anzahl
Varianten.

Aufruf: python test/tmp_diag_sl_kante_rel.py [--aug|--s1|--s2|--all]
"""
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

FENSTER = {
    "aug": ("August", ["--start=2026-08-10", "--ende=2026-08-28"]),
    "s1": ("Sample1 2026", ["--start=2026-02-05", "--ende=2026-08-28"]),
    "s2": ("Sample2 2025", ["--start=2025-01-01", "--ende=2025-12-01"]),
}

TOL_KANTE = 0.30
MIN_WEITE_PCT = 1.5
VMOVE_AUSREISSER_PCT = 1.5
VMOVE_ANSTIEG_PCT = 4.0
VMOVE_MAX_BARS = 150

VARIANTEN = [
    ("entry 0.45%", "entry", 0.0),
    ("kante+0.10USD", "kante_fix", 0.10),
    ("kante+0.10%", "kante_rel", 0.10),
    ("kante+0.15%", "kante_rel", 0.15),
    ("kante+0.20%", "kante_rel", 0.20),
    ("kante+0.25%", "kante_rel", 0.25),
    ("kante+0.30%", "kante_rel", 0.30),
]


def load_ns(win_args):
    """Hauptskript bis reclaim_signals = [] laden (mit --start/--ende)."""
    src = SRC.read_text(encoding="utf-8")
    cut = src.index("reclaim_signals = []")
    ns = {"__file__": str(SRC), "__name__": "diag_sl_rel"}
    # CLI-Overrides des Hauptskripts nutzen
    old_argv = sys.argv
    sys.argv = ["tmp_phasen_volumen_profil.py"] + win_args
    t0 = time.time()
    exec(compile(src[:cut], str(SRC), "exec"), ns)
    sys.argv = old_argv
    print(f"[load] {time.time()-t0:.1f}s | {len(ns['phases'])} Phasen | {len(ns['df'])} Bars")
    return ns


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


def vmove_check(P, P_prev, phases, pd, np):
    if P_prev is None or len(P.get("l_prices", [])) == 0:
        return False
    vz_prev = P_prev.get("vol_zone")
    if vz_prev is None:
        return False
    L_ref = vz_prev["L_zone"]
    l_prices = P["l_prices"]
    l_ts = P["l_ts"]
    k = int(np.argmin(l_prices))
    l_min = float(l_prices[k])
    t_tief = l_ts[k]
    if l_min >= L_ref * (1 - VMOVE_AUSREISSER_PCT / 100.0):
        return False
    t_end = t_tief + pd.Timedelta(minutes=VMOVE_MAX_BARS * 15)
    h_max = -np.inf
    for Pk in phases[phases.index(P):]:
        for pr, t in zip(Pk.get("h_prices", []), Pk.get("h_ts", [])):
            if t > t_tief and t <= t_end and pr > h_max:
                h_max = float(pr)
        if Pk["ende"] > t_end:
            break
    if not np.isfinite(h_max):
        return False
    if (h_max - l_min) / l_min * 100.0 < VMOVE_ANSTIEG_PCT:
        return False
    return True


def build_boxes_v7(ns):
    """v7-arm Segmentierung: reife Phasen = Segment, V-Move-Phase bleibt Arm,
    Phase nach V-Move startet neues Segment."""
    phases = ns["phases"]
    pd, np = ns["pd"], ns["np"]
    reif_info = []
    vmove_info = []
    for i, P in enumerate(phases, 1):
        reif, t_reif, tripel = reife_check(P)
        P_prev = phases[i - 2] if i >= 2 else None
        vm = vmove_check(P, P_prev, phases, pd, np)
        reif_info.append((P, reif, t_reif))
        vmove_info.append(vm)
    seg_start = [False] * len(phases)
    for i in range(len(phases)):
        if reif_info[i][1]:
            seg_start[i] = True
        elif vmove_info[i]:
            seg_start[i] = False
        if i > 0 and vmove_info[i - 1]:
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
    n = len(ns["df"])
    for k, b in enumerate(boxen):
        if k + 1 < len(boxen):
            b["i_ende"] = min(boxen[k + 1]["i_start"] - 1, n - 1)
        else:
            b["i_ende"] = n - 1
        b["ende"] = ns["df"]["ts"].iloc[b["i_ende"]]
    return boxen


def collect_candidates(ns, box):
    """Sammelt ALLE Roh-Kandidaten einer Box (eine Zone-Berechnung je Bar).

    Kandidat = Fakeout+Reclaim, Entry auf richtiger POC-Seite, Bo>=MIN.
    Cooldown und CRV-Filter werden NICHT angewendet (variante-abhaengig).
    """
    df = ns["df"]
    p = {"i_start": box["i_start"], "i_ende": box["i_ende"],
         "h_prices": box["h"], "h_ts": box["h_ts"],
         "l_prices": box["l"], "l_ts": box["l_ts"]}
    _laufende_zone = ns["_laufende_zone"]
    _bounce_nr = ns["_bounce_nr"]
    hi, lo, cl, op = (df["high"].values, df["low"].values,
                      df["close"].values, df["open"].values)
    ts = df["ts"].values
    pd = ns["pd"]
    cands = []
    for k in range(box["i_start"], box["i_ende"]):
        vz = _laufende_zone(df, p, k)
        if vz is None:
            continue
        U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
        nb_h, nb_l = _bounce_nr(box["h"], box["h_ts"], box["l"], box["l_ts"],
                                pd.Timestamp(ts[k]), U, L)
        if hi[k] > U:
            if cl[k] <= U:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] <= U:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis > POC
                    and nb_h >= ns["MIN_RECLAIM_BOUNCE"]):
                cands.append({"k": k, "ts": pd.Timestamp(ts[k]), "typ": "SHORT",
                              "e_bar": int(e_bar), "e_preis": e_preis,
                              "U": U, "L": L, "POC": POC, "nb": nb_h,
                              "rec": rec, "box": 0})
        if lo[k] < L:
            if cl[k] >= L:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] >= L:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis < POC
                    and nb_l >= ns["MIN_RECLAIM_BOUNCE"]):
                cands.append({"k": k, "ts": pd.Timestamp(ts[k]), "typ": "LONG",
                              "e_bar": int(e_bar), "e_preis": e_preis,
                              "U": U, "L": L, "POC": POC, "nb": nb_l,
                              "rec": rec, "box": 0})
    return cands


def _aufloesen_mit_sl(ns, df, s):
    """Aufloesen mit vorgegebenem SL (kein SL_PCT-vom-Entry-Override)."""
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
        t1, t2, t_sl = _first(lo <= tp1), _first(lo <= tp2), _first(hi >= sl_init)
    else:
        t1, t2, t_sl = _first(hi >= tp1), _first(hi >= tp2), _first(lo <= sl_init)
    if t1 < t_sl:
        r1, ex1, g1 = _r(tp1), tp1, "TP1"
    elif t_sl < n:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    else:
        r1, ex1, g1 = _r(cl[-1]), cl[-1], "ENDE"
    if t2 < t_sl:
        r2, ex2, g2 = _r(tp2), tp2, "TP2"
    elif t_sl < n:
        r2, ex2, g2 = -1.0, sl_init, "SL"
    else:
        r2, ex2, g2 = _r(cl[-1]), cl[-1], "ENDE"
    _w1 = ns["ANTEIL_TP1"] / 100.0
    _w2 = 1.0 - _w1
    if _w2 <= 0:
        r2, g2 = 0.0, "-"
    r_mult = _w1 * r1 + _w2 * r2
    resultat = ("GEWONNEN" if r_mult > 1e-9
                else ("VERLOREN" if r_mult < -1e-9 else "NEUTRAL"))
    return {"r_mult": r_mult, "resultat": resultat, "r1": r1, "r2": r2,
            "exit1": ex1, "exit2": ex2, "grund1": g1, "grund2": g2}


def replay(ns, df, cands, sl_art, puffer):
    """Wendet SL-Art + Cooldown + CRV-Filter auf Kandidaten an."""
    COOLDOWN = ns["MIN_SIGNAL_ABSTAND_BARS"]
    MIN_CRV = ns["MIN_RECLAIM_CRV"]
    sl_p = ns["SL_PCT"] / 100.0
    sigs = []
    last_bar = {"SHORT": -10 ** 9, "LONG": -10 ** 9}
    for c in sorted(cands, key=lambda x: x["k"]):
        typ = c["typ"]
        if c["k"] - last_bar[typ] < COOLDOWN:
            continue
        if sl_art == "entry":
            sl = c["e_preis"] * (1 + sl_p) if typ == "SHORT" else c["e_preis"] * (1 - sl_p)
        elif sl_art == "kante_fix":
            sl = c["U"] + puffer if typ == "SHORT" else c["L"] - puffer
        else:  # kante_rel
            sl = c["U"] * (1 + puffer / 100.0) if typ == "SHORT" else c["L"] * (1 - puffer / 100.0)
        tp1 = c["POC"]
        if typ == "SHORT":
            tp2 = c["L"] * (1 + ns["TP2_PUFFER_PCT"] / 100.0)
        else:
            tp2 = c["U"] * (1 - ns["TP2_PUFFER_PCT"] / 100.0)
        risk = abs(sl - c["e_preis"])
        crv = abs(tp1 - c["e_preis"]) / risk if risk > 0 else 0.0
        if crv < MIN_CRV:
            continue
        last_bar[typ] = c["k"]
        s = {"typ": typ, "einstieg_bar": c["e_bar"], "einstieg_preis": c["e_preis"],
             "tp1": tp1, "tp2": tp2, "sl": sl, "POC": c["POC"],
             "ts": c["ts"], "box": c["box"], "crv": crv,
             "sl_risk": abs(sl - c["e_preis"]) / c["e_preis"] * 100.0}
        s.update(_aufloesen_mit_sl(ns, df, s))
        sigs.append(s)
    return sigs


def run_fenster(name, win_args):
    print(f"\n{'='*80}\n=== FENSTER {name} ({win_args[0].split('=')[1]} .. {win_args[1].split('=')[1]}) ===\n")
    t0 = time.time()
    ns = load_ns(win_args)
    df = ns["df"]
    boxen = build_boxes_v7(ns)
    print(f"[boxes] {len(boxen)} Boxen (v7-arm)")
    for bi, b in enumerate(boxen, 1):
        print(f"  B{bi}: P{'+'.join(f'P{p}' for p in b['phasen'])} "
              f"{b['start']:%d.%m %H:%M}-{b['ende']:%d.%m %H:%M}")
    # Kandidaten einmal sammeln
    all_cands = []
    t1 = time.time()
    for bi, b in enumerate(boxen, 1):
        cands = collect_candidates(ns, b)
        for c in cands:
            c["box"] = bi
        all_cands.extend(cands)
    print(f"[cands] {len(all_cands)} Roh-Kandidaten in {time.time()-t1:.1f}s")
    print(f"\n{'Variante':<18} | {'Sig':>4} | {'WR':>4} | {'W/L':>6} | {'SummeR':>8} | {'avgR':>6} | {'avgRisk':>7} | {'avgCRV':>6}")
    for label, art, puff in VARIANTEN:
        sigs = replay(ns, df, all_cands, art, puff)
        w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
        l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
        r = sum(s["r_mult"] for s in sigs)
        nn = len(sigs)
        wr = 100.0 * w / (w + l) if w + l else 0.0
        avg_r = r / nn if nn else 0.0
        avg_risk = sum(s["sl_risk"] for s in sigs) / nn if nn else 0.0
        avg_crv = sum(s["crv"] for s in sigs) / nn if nn else 0.0
        print(f"  {label:<16} | {nn:>4} | {wr:>3.0f}% | {w}/{l:>3} | {r:>+8.2f} | {avg_r:>+6.2f} | {avg_risk:>6.2f}% | {avg_crv:>6.2f}")
    print(f"[total] {time.time()-t0:.1f}s")
    return all_cands


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "aug"
    if mode == "--all":
        for k in FENSTER:
            run_fenster(*FENSTER[k])
    elif mode in FENSTER:
        run_fenster(*FENSTER[mode])
    else:
        print("Modi: aug | s1 | s2 | --all")
