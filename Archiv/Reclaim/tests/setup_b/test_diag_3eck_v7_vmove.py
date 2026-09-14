# test/test_diag_3eck_v7_vmove.py
"""SEGMENTIERUNG v7: v6 (3-Eckpunkte+1.5%) + V-MOVE-FILTER.

User-Regel (01.09.2026): Der grosse V-Move am 18./19.08 (Riesen-Ausreisser
nach unten auf 62.548 + Riesen-Anstieg danach auf 68.972 = +10.27%) ist ein
TREND-AUSSCHLAG / DEVELOPMENT und sollte die alte Phase INVALIDIEREN -> das
Verhalten muss als Phasenuebergang erkannt werden.

V-MOVE-FILTER (pro Baseline-Phase P, i >= 2):
1. AUSREISSER: tiefster L-Pivot von P liegt mind. VMOVE_AUSREISSER_PCT
   unter der Volume-L-Zone der VORHERIGEN Phase (etablierte Range vor dem Move).
2. ANSTIEG: ein H-Pivot nach dem Tief (bis VMOVE_MAX_BARS spaeter, ueber
   Folgephasen) liegt mind. VMOVE_ANSTIEG_PCT ueber dem Tief.
Beide Bedingungen -> Phase ist ein "V-MOVE" (= Development, invalidiert
die laufende Box).

SEGMENTIERUNG (Mode):
- "arm"      : V-Move-Phase bleibt letzter Arm der Box, die FOLGENDE Phase
               startet ein neues Segment (V = Uebergang, alte Box endet).
- "solo"     : V-Move-Phase wird eigenes Segment (Crash-Zone), Folgephasen
               haengen als Arme an.
- "uebergang": V-Move-Phase wird eigenes Segment UND die folgende Phase
               startet zusaetzlich ein neues Segment.

Vergleich: Baseline (12 Phasen) | v6 (3-Eckpunkte) | v7 (v6 + V-Move).

Aufruf: python test/test_diag_3eck_v7_vmove.py [mode]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "test_diag_3eck_v7_vmove"}
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

TOL_KANTE = 0.30          # gleiche Kante: |H1-H2| bzw. |L1-L2| <= TOL_KANTE
MIN_WEITE_PCT = 1.5       # min. Weite in %

# --- V-MOVE-FILTER-PARAMETER (optional per CLI uebersteuerbar) ---
VMOVE_AUSREISSER_PCT = 1.5   # L-Pivot > X% unter der L-Zone der Vor-Phase
VMOVE_ANSTIEG_PCT = 4.0      # H-Pivot danach > X% ueber dem Tief
VMOVE_MAX_BARS = 150         # Anstieg innerhalb max. X M15-Bars nach dem Tief
VMOVE_MODE = sys.argv[1] if len(sys.argv) > 1 else "arm"
for _a in sys.argv[1:]:
    if _a.startswith("--ausr="):
        VMOVE_AUSREISSER_PCT = float(_a.split("=", 1)[1])
    if _a.startswith("--anst="):
        VMOVE_ANSTIEG_PCT = float(_a.split("=", 1)[1])
    if _a.startswith("--bars="):
        VMOVE_MAX_BARS = int(_a.split("=", 1)[1])

print(f"V-MOVE-FILTER: Ausreisser < {VMOVE_AUSREISSER_PCT}% unter Vor-Zone | "
      f"Anstieg > {VMOVE_ANSTIEG_PCT}% | max {VMOVE_MAX_BARS} Bars | Mode={VMOVE_MODE}")


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


def vmove_check(P, P_prev):
    """V-Move-Detektion: Riesen-Ausreisser nach unten + Riesen-Anstieg danach.

    Rueckgabe: (vmove, t_tief, tief_preis, hoch_preis, ausreisser_pct, anstieg_pct)
    """
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
    # Anstieg danach: H-Pivots aus P und Folgephasen bis VMOVE_MAX_BARS
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


def run_segmentierung(segment_start):
    """Baut Boxen aus segment_start-Flags je Phase (1-basiert).

    LUEKEN-FIX: Die Phasen im Hauptskript haben Luecken (z.B. P5 endet
    18.08 03:15, P6 beginnt 18.08 17:00). Diese Luecken gehoeren zur alten
    Box (dort gilt noch der alte Kontext, bis die neue Box startet).
    i_ende jeder Box wird daher bis zum Start der naechsten Box erweitert
    (bzw. bis Datenende fuer die letzte Box).
    """
    boxen = []
    aktive = None
    for i, P in enumerate(phases):
        if segment_start[i]:
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
    # LUEKEN-FIX: i_ende bis zum Start der naechsten Box erweitern
    n = len(df)
    for k, b in enumerate(boxen):
        if k + 1 < len(boxen):
            b["i_ende"] = min(boxen[k + 1]["i_start"] - 1, n - 1)
        else:
            b["i_ende"] = n - 1
        b["ende"] = df["ts"].iloc[b["i_ende"]]
    return boxen


def signale_je_box(boxen):
    """Signale je Box + finale Volume-Zonen (nur fuer Vergleich)."""
    alle = []
    for bi, b in enumerate(boxen, 1):
        sigs = find_signals_box(ns, b)
        w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
        l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
        r = sum(s["r_mult"] for s in sigs)
        b["sigs"] = sigs
        b["n_w"], b["n_l"], b["sum_r"] = w, l, r
        for s in sigs:
            s["box"] = bi
            alle.append(s)
    return alle


print("\n=== 1) REIFE + V-MOVE JE PHASE ===")
reif_info = []
vmove_info = []
for i, P in enumerate(phases, 1):
    reif, t_reif, tripel = reife_check(P)
    P_prev = phases[i - 2] if i >= 2 else None
    vm, t_v, p_v, h_v, ausr, anst = vmove_check(P, P_prev)
    reif_info.append((P, reif, t_reif))
    vmove_info.append((vm, t_v, p_v, h_v, ausr, anst))
    tr = f"{t_reif:%d.%m %H:%M}" if t_reif is not None else "-"
    tv = f"{t_v:%d.%m %H:%M}" if t_v is not None else "-"
    ausr_s = f"{ausr:.1f}%" if ausr is not None else "-"
    anst_s = f"{anst:.1f}%" if anst is not None else "-"
    flag = ("REIF" if reif else "") + (" | V-MOVE" if vm else "")
    print(f"  P{i}: {flag:<14} Reif {tr:<12} V-Tief {tv:<12} "
          f"Ausr {ausr_s:>5} Anst {anst_s:>5}")

# Segment-Start-Flags je Mode
print(f"\n=== 2) SEGMENTIERUNG Mode={VMOVE_MODE} ===")
seg_start = [False] * len(phases)
for i in range(len(phases)):
    reif = reif_info[i][1]
    vm = vmove_info[i][0]
    if reif:
        seg_start[i] = True
    elif vm:
        if VMOVE_MODE in ("solo", "uebergang"):
            seg_start[i] = True
        else:  # "arm": V-Move-Phase bleibt Arm
            seg_start[i] = False
    # Phase NACH einem V-Move startet ebenfalls ein neues Segment
    # (V = Uebergang: die alte Box ist invalidiert, danach beginnt neue Range)
    if VMOVE_MODE in ("uebergang", "arm") and i > 0 and vmove_info[i - 1][0]:
        seg_start[i] = True

boxen = run_segmentierung(seg_start)
for bi, b in enumerate(boxen, 1):
    ph = "+".join(f"P{p}" for p in b["phasen"])
    u = f"{level_schnittmenge(b['h'], 'H'):.2f}" if b["h"] else "N/A"
    l = f"{level_schnittmenge(b['l'], 'L'):.2f}" if b["l"] else "N/A"
    print(f"  B{bi}: {b['start']:%d.%m %H:%M}-{b['ende']:%d.%m %H:%M} | Phasen {ph} | Box {u}/{l}")

# 3) Signale
alle = signale_je_box(boxen)
w = sum(1 for s in alle if s["resultat"] == "GEWONNEN")
l = sum(1 for s in alle if s["resultat"] == "VERLOREN")
r = sum(s["r_mult"] for s in alle)
nn = len(alle)
print(f"\n=== 3) ERGEBNIS v7 (Mode={VMOVE_MODE}) ===")
for bi, b in enumerate(boxen, 1):
    ph = "+".join(f"P{p}" for p in b["phasen"])
    _w, _l, _r = b["n_w"], b["n_l"], b["sum_r"]
    _wr = 100.0 * _w / (_w + _l) if (_w + _l) else 0.0
    print(f"  B{bi} ({ph}): {len(b['sigs']):2d} Sig | {_w}W/{_l}L | {_wr:.0f}% | {_r:+8.2f}R")
print(f"  GESAMT v7          : {nn:2d} Sig | {w}W/{l}L | "
      f"{100.0*w/(w+l) if w+l else 0:.0f}% | {r:+8.2f}R | avg {r/nn if nn else 0:+.2f}")
print(f"  v6 (ohne V-Move)   : 34 Sig | 17W/17L | 50% | +56.87R | avg +1.67")
print(f"  BASELINE (Vergl.)  : 33 Sig | 13W/20L | 39% | +25.01R | avg +0.76")

# 4) Vergleich pro Zeitfenster
base = []
for pi, P in enumerate(phases, 1):
    for s in ns["find_reclaim_signals"](df, P):
        s["phase"] = pi
        base.append(s)

# v6-Referenz-Boxen (reif = Segment, sonst Arm) fuer den Vergleich
seg_start_v6 = [False] * len(phases)
for i in range(len(phases)):
    seg_start_v6[i] = reif_info[i][1]
boxen_v6 = run_segmentierung(seg_start_v6)
alle_v6 = signale_je_box(boxen_v6)

print("\n--- 4) VERGLEICH PRO ZEITFENSTER ---")
print(f"{'Fenster':<14} | {'Baseline':>16} | {'v6':>16} | {'v7':>16}")
for pi, P in enumerate(phases, 1):
    t0, t1 = P["start"], P["ende"]
    bs = [s for s in base if t0 <= s["ts"] <= t1]
    ss6 = [s for s in alle_v6 if t0 <= s["ts"] <= t1]
    ss7 = [s for s in alle if t0 <= s["ts"] <= t1]
    br = sum(s["r_mult"] for s in bs)
    r6 = sum(s["r_mult"] for s in ss6)
    r7 = sum(s["r_mult"] for s in ss7)
    print(f"  P{pi} {t0:%d.%m}-{t1:%d.%m} | {len(bs):2d}Sig {br:+7.2f}R | "
          f"{len(ss6):2d}Sig {r6:+7.2f}R | {len(ss7):2d}Sig {r7:+7.2f}R")

print("\n--- 5) DETAIL-SIGNALE v7 ---")
for s in alle:
    print(f"  B{s['box']} {s['ts']:%d.%m %H:%M} {s['typ']:5s} "
          f"Kante {s['U_laufend'] if s['typ']=='SHORT' else s['L_laufend']:.3f} "
          f"| POC {s['POC']:.3f} | Bo {s['bounce_nr']} | {s['resultat']} {s['r_mult']:+.2f}R")
