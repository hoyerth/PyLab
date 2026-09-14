# test/test_diag_3eck_v6.py
"""SEGMENTIERUNG v6: DIREKTE UMSETZUNG der User-Regel.

Regel: Ein NEUES SEGMENT braucht mind. 3 Eckpunkte (H-L-H oder L-H-L,
|p1-p3| <= TOL_KANTE) und mind. 1.5% Weite.
- Reife Phase  -> eigenes Segment (eigene Volume-Zone, Signale wie gehabt)
- Nicht-reife Phase -> ARM der vorherigen Box (Pivots wandern zur Box,
  Signale an der laufenden Volume-Zone der Box)

Kein zusaetzlicher Bruch-Check: Die Segmentierung folgt strikt der
3-Eckpunkte+1.5%-Regel (einfachste Interpretation).

Aufruf: python test/test_diag_3eck_v6.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "test_diag"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
piv = ns["piv"]
_laufende_zone = ns["_laufende_zone"]
_bounce_nr = ns["_bounce_nr"]
_aufloesen = ns["_aufloesen"]
level_schnittmenge = ns["level_schnittmenge"]
pd = ns["pd"]
np = ns["np"]

TOL_KANTE = 0.30       # gleiche Kante: |H1-H2| bzw. |L1-L2| <= TOL_KANTE
MIN_WEITE_PCT = 1.5    # min. Weite in %


def reife_check(P, tol_kante=TOL_KANTE, min_weite_pct=MIN_WEITE_PCT):
    """3-Eckpunkte direkt aus den PIVOTS (H-L-H oder L-H-L).
    Rueckgabe: (reif, t_reif, tripel)"""
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


def find_signals_box(ns, box):
    """Setup B an der laufenden Volume-Zone der Box (kausal ab i_start)."""
    df = ns["df"]
    p = {"i_start": box["i_start"], "i_ende": box["i_ende"],
         "h_prices": box["h"], "h_ts": box["h_ts"],
         "l_prices": box["l"], "l_ts": box["l_ts"]}
    sigs = []
    hi, lo, cl, op = (df["high"].values, df["low"].values,
                      df["close"].values, df["open"].values)
    ts = df["ts"].values
    last_bar = {"SHORT": -10 ** 9, "LONG": -10 ** 9}
    for k in range(box["i_start"], box["i_ende"]):
        vz = _laufende_zone(df, p, k)
        if vz is None:
            continue
        U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
        ts_k = ts[k]
        nb_h, nb_l = _bounce_nr(box["h"], box["h_ts"], box["l"], box["l_ts"],
                                ts_k, U, L)
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
                sl = e_preis * (1 + ns["SL_PCT"] / 100.0)
                tp1 = POC
                tp2 = L * (1 + ns["TP2_PUFFER_PCT"] / 100.0)
                crv = abs(tp1 - e_preis) / abs(sl - e_preis) if sl != e_preis else 0
                if crv >= ns["MIN_RECLAIM_CRV"]:
                    last_bar["SHORT"] = k
                    s = {"typ": "SHORT", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U,
                         "L_laufend": L, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_h}
                    s.update(_aufloesen(df, s))
                    sigs.append(s)
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
                sl = e_preis * (1 - ns["SL_PCT"] / 100.0)
                tp1 = POC
                tp2 = U * (1 - ns["TP2_PUFFER_PCT"] / 100.0)
                crv = abs(tp1 - e_preis) / abs(sl - e_preis) if sl != e_preis else 0
                if crv >= ns["MIN_RECLAIM_CRV"]:
                    last_bar["LONG"] = k
                    s = {"typ": "LONG", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U,
                         "L_laufend": L, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_l}
                    s.update(_aufloesen(df, s))
                    sigs.append(s)
    return sigs


print("=== SEGMENTIERUNG v6: 3-ECKPUNKTE (H-L-H/L-H-L) + 1.5%-WEITE ===")
print("Reife Phase = eigenes Segment | Nicht-reife Phase = Arm der Box")

# 1) Reife je Phase
print("\n--- 1) REIFE JE BASELINE-PHASE ---")
reif_info = []
for i, P in enumerate(phases, 1):
    reif, t_reif, tripel = reife_check(P)
    tr = f"{t_reif:%d.%m %H:%M}" if t_reif is not None else "-"
    tp = ""
    if tripel:
        t1, p1, t2, p2, t3, p3 = tripel
        tp = f" {t1} {p1:.2f}/{t2} {p2:.2f}/{t3} {p3:.2f}"
    print(f"  P{i}: {'REIF' if reif else 'nicht reif':<11} {tr}{tp}")
    reif_info.append((P, reif, t_reif))

# 2) Verschmelzung: reif = eigenes Segment, sonst Arm
print("\n--- 2) BOXEN (Verschmelzung) ---")
boxen = []
aktive = None
for i, (P, reif, t_reif) in enumerate(reif_info):
    if reif:
        if aktive is not None:
            boxen.append(aktive)
        aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                  "phasen": [i + 1], "reif": True, "t_reif": t_reif,
                  "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                  "l": list(P["l_prices"]), "l_ts": list(P["l_ts"]),
                  "start": P["start"], "ende": P["ende"]}
    else:
        if aktive is None:
            aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                      "phasen": [i + 1], "reif": False, "t_reif": None,
                      "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                      "l": list(P["l_prices"]), "l_ts": list(P["l_ts"]),
                      "start": P["start"], "ende": P["ende"]}
        else:
            aktive["i_ende"] = P["i_ende"]
            aktive["ende"] = P["ende"]
            aktive["phasen"].append(i + 1)
            aktive["h"].extend(P["h_prices"])
            aktive["h_ts"].extend(P["h_ts"])
            aktive["l"].extend(P["l_prices"])
            aktive["l_ts"].extend(P["l_ts"])
boxen.append(aktive)

for bi, b in enumerate(boxen, 1):
    ph = "+".join(f"P{p}" for p in b["phasen"])
    u = f"{level_schnittmenge(b['h'], 'H'):.2f}" if b["h"] else "N/A"
    l = f"{level_schnittmenge(b['l'], 'L'):.2f}" if b["l"] else "N/A"
    ra = f"{b['t_reif']:%d.%m %H:%M}" if b.get("t_reif") is not None else "-"
    rstat = "REIF" if b["reif"] else "Arm-Sammlung"
    print(f"  B{bi}: {b['start']:%d.%m %H:%M}-{b['ende']:%d.%m %H:%M} | "
          f"Phasen {ph} | Box {u}/{l} | {rstat} {ra}")

# 3) Signale je Box
print("\n--- 3) SETUP B AUF DEN BOXEN (kausal, ganze Box) ---")
alle = []
for bi, b in enumerate(boxen, 1):
    sigs = find_signals_box(ns, b)
    w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
    l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
    r = sum(s["r_mult"] for s in sigs)
    print(f"  B{bi} ({b['start']:%d.%m}-{b['ende']:%d.%m}): {len(sigs):2d} Sig | "
          f"{w}W/{l}L | {100.0*w/(w+l) if w+l else 0:.0f}% | {r:+8.2f}R")
    for s in sigs:
        s["box"] = bi
        alle.append(s)

w = sum(1 for s in alle if s["resultat"] == "GEWONNEN")
l = sum(1 for s in alle if s["resultat"] == "VERLOREN")
r = sum(s["r_mult"] for s in alle)
nn = len(alle)
print(f"\n  GESAMT v6          : {nn:2d} Sig | {w}W/{l}L | "
      f"{100.0*w/(w+l) if w+l else 0:.0f}% | {r:+8.2f}R | avg {r/nn if nn else 0:+.2f}")
print(f"  BASELINE (Vergl.)  : 33 Sig | 13W/20L | 39% | +25.01R | avg +0.76")

# Baseline-Signale
base = []
for pi, P in enumerate(phases, 1):
    for s in ns["find_reclaim_signals"](df, P):
        s["phase"] = pi
        base.append(s)

print("\n--- 4) VERGLEICH PRO ZEITFENSTER ---")
print(f"{'Fenster':<14} | {'Baseline':>18} | {'v6':>18}")
for pi, P in enumerate(phases, 1):
    t0, t1 = P["start"], P["ende"]
    bs = [s for s in base if t0 <= s["ts"] <= t1]
    ss = [s for s in alle if t0 <= s["ts"] <= t1]
    br = sum(s["r_mult"] for s in bs)
    sr = sum(s["r_mult"] for s in ss)
    print(f"  P{pi} {t0:%d.%m}-{t1:%d.%m} | {len(bs):2d}Sig {br:+7.2f}R | "
          f"{len(ss):2d}Sig {sr:+7.2f}R")

print("\n--- 5) DETAIL-SIGNALE v6 ---")
for s in alle:
    print(f"  B{s['box']} {s['ts']:%d.%m %H:%M} {s['typ']:5s} "
          f"Kante {s['U_laufend'] if s['typ']=='SHORT' else s['L_laufend']:.3f} "
          f"| POC {s['POC']:.3f} | Bo {s['bounce_nr']} | {s['resultat']} {s['r_mult']:+.2f}R")
