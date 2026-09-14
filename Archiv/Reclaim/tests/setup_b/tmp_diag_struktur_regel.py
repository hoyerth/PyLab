# test/tmp_diag_struktur_regel.py
"""STRUKTUR-REGEL (User 01.09.2026): Signale nur an LEGITIMEN Kanten.

Legitim (kausal je Signal-Bar k):
  (a) Kante = Ober-/Unterkante einer FRUEHEREN REIFEN Box +/- TOL_KANTE, ODER
  (b) Kante hat 3-Eckpunkte (H-L-H fuer SHORT / L-H-L fuer LONG) mit
      |p1-p3| <= TOL_KANTE und Weite >= MIN_WEITE_PCT in der Box-Historie
      bis zur Signal-Bar k.

STRIKTE Variante (01.09.2026, Naechste-Schritte-Punkt 1):
  NUR (a) "alt" + (c) "eck" -- das zu laxe (b) "box(reif)" ist AUS.
  Umschaltung: Modul-Konstante STRUKTUR_STRENG bzw. CLI-Flag --lax.

Koppel-Test (Uebernahme-Entscheidung):
  - baseline               : v7-arm + SL vom Entry (ohne Regel)
  - struktur + entry       : nur legitime Kanten, SL vom Entry
  - struktur + kante+0.10% : nur legitime Kanten, SL = Kante*(1+0.10%)
  - struktur + kante+0.15% : dito 0.15%
  - struktur + kante+0.20% : dito 0.20%
  - struktur + kante+0.25% : dito 0.25%

Fenster: aug | s1 | s2 | --all
Aufruf: python test/tmp_diag_struktur_regel.py [aug|s1|s2|--all] [--lax] [--detail]
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

TOL_KANTE = 0.30          # gleiche Kante: |p1-p3| bzw. Kante-Distanz <= TOL
MIN_WEITE_PCT = 1.5       # min. Struktur-Weite in %
VMOVE_AUSREISSER_PCT = 1.5
VMOVE_ANSTIEG_PCT = 4.0
VMOVE_MAX_BARS = 150

# Strikte Struktur-Regel (Naechste-Schritte-Punkt 1, 02.09.2026):
#   True  -> NUR "alt" (fruehere reife Box) + "eck" (3-Eckpunkte).
#            Das zu laxe "box(reif)"-Kriterium (b) ist damit AUS.
#   False -> laxe Variante wie am 01.09.2026 (inkl. "box(reif)").
STRUKTUR_STRENG = True

VARIANTEN = [
    ("baseline", "entry", 0.0, False),
    ("struktur+entry", "entry", 0.0, True),
    ("struktur+kante+0.10%", "kante_rel", 0.10, True),
    ("struktur+kante+0.15%", "kante_rel", 0.15, True),
    ("struktur+kante+0.20%", "kante_rel", 0.20, True),
    ("struktur+kante+0.25%", "kante_rel", 0.25, True),
]


def load_ns(win_args):
    src = SRC.read_text(encoding="utf-8")
    cut = src.index("reclaim_signals = []")
    ns = {"__file__": str(SRC), "__name__": "diag_struktur"}
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
    """v7-arm Segmentierung + reif-Flag je Box."""
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
                      "l": list(P["l_prices"]), "l_ts": list(P["l_ts"]),
                      "reif": bool(reif_info[i][1]),
                      "reif_ts": reif_info[i][2]}
        else:
            if aktive is None:
                aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                          "phasen": [i + 1], "start": P["start"], "ende": P["ende"],
                          "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                          "l": list(P["l_prices"]), "l_ts": list(P["l_ts"]),
                          "reif": bool(reif_info[i][1]),
                          "reif_ts": reif_info[i][2]}
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


def box_events(box, bis_ts):
    """Alle Pivot-Events der Box bis bis_ts, sortiert nach Zeit."""
    ev = []
    for p, t in zip(box["h"], box["h_ts"]):
        if t <= bis_ts:
            ev.append((t, "H", float(p)))
    for p, t in zip(box["l"], box["l_ts"]):
        if t <= bis_ts:
            ev.append((t, "L", float(p)))
    ev.sort(key=lambda x: x[0])
    return ev


def hat_3_eckpunkte(ev, kante, typ, tol_kante=TOL_KANTE,
                    min_weite_pct=MIN_WEITE_PCT):
    """True, wenn Tripel (typ, gegentyp, typ) um kante mit Weite >= 1.5% existiert."""
    for i in range(len(ev) - 2):
        t1, ty1, p1 = ev[i]
        t2, ty2, p2 = ev[i + 1]
        t3, ty3, p3 = ev[i + 2]
        if ty1 == ty2 or ty2 == ty3 or ty1 != ty3:
            continue
        if ty1 != typ:
            continue
        if abs(p1 - kante) > tol_kante or abs(p3 - kante) > tol_kante:
            continue
        weite = abs(p2 - p1) / min(p1, p2) * 100.0
        if weite >= min_weite_pct:
            return True
    return False


def kante_legitim(ns, box, prev_reife, kante, typ, ts_k, level_fx):
    """Legitimitaet einer laufenden Kante (kausal, mit Pivot-Lag).

    (a) Kante nahe der Ober-/Unterkante einer FRUEHEREN reifen Box.
    (b) Kante nahe der laufenden Schnittmengen-Kante der AKTUELLEN Box,
        SOBALD die Box reif ist (Reifezeitpunkt der Startphase erreicht).
    (c) 3-Eckpunkte (H-L-H / L-H-L) mit Weite >= 1.5% in der Box-Historie.
    Rueckgabe: "alt" | "box" | "eck" | None
    """
    pd = ns["pd"]
    lag = ns["PIVOT_LOOKBACK"]
    best = ts_k - pd.Timedelta(minutes=lag * 15)
    # (a) fruehere reife Boxen (finale Pivots, zu diesem Zeitpunkt vollstaendig)
    for b in prev_reife:
        ks = level_fx(b["h"], "H") if typ == "SHORT" else level_fx(b["l"], "L")
        if ks is not None and abs(kante - ks) <= TOL_KANTE:
            return "alt"
    # (b) aktuelle Box, sobald reif: laufende Schnittmengen-Kante bis ts_k
    #     STRIKT (STRUKTUR_STRENG=True): Kriterium AUS -- zu lax, entspricht
    #     nicht der User-Intention (79% der Kandidaten passierten in S2).
    if (not STRUKTUR_STRENG and box.get("reif")
            and box.get("reif_ts") is not None and ts_k >= box["reif_ts"]):
        h_k = [p for p, t in zip(box["h"], box["h_ts"]) if t <= best]
        l_k = [p for p, t in zip(box["l"], box["l_ts"]) if t <= best]
        ks = level_fx(h_k, "H") if typ == "SHORT" else level_fx(l_k, "L")
        if ks is not None and abs(kante - ks) <= TOL_KANTE:
            return "box"
    # (c) 3-Eckpunkte in der Box-Historie bis zum bestaetigten Zeitpunkt
    ev = box_events(box, best)
    if hat_3_eckpunkte(ev, kante, "H" if typ == "SHORT" else "L"):
        return "eck"
    return None


def _profile_vec(lows, highs, vols, num_bins):
    """Vektorisiertes Volume-Profil einer Slice.

    BIT-IDENTISCH zu ns['build_volume_profile'] (gleiche Edges via linspace
    ueber slice-min/max, gleiche Overlap-Verteilung je Bar, gleiche
    Additions-Reihenfolge je Bin). Nur ohne Python-Bar-Loop -> massiv
    schneller fuer Rebuilds.
    """
    lows = np.asarray(lows, dtype=np.float64)
    highs = np.asarray(highs, dtype=np.float64)
    vols = np.asarray(vols, dtype=np.float64)
    if len(lows) == 0:
        return None
    pmin = float(lows.min())
    pmax = float(highs.max())
    if pmax <= pmin:
        return None
    edges = np.linspace(pmin, pmax, num_bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    vol = np.zeros(num_bins, dtype=np.float64)
    ok = (highs > lows) & (vols > 0)
    if ok.any():
        lo = lows[ok]
        hi = highs[ok]
        v = vols[ok]
        lo_b = np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, num_bins - 1)
        hi_b = np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, num_bins - 1)
        single = lo_b == hi_b
        if single.any():
            np.add.at(vol, lo_b[single].astype(np.intp), v[single])
        multi = ~single
        if multi.any():
            lm = lo[multi]
            hm = hi[multi]
            vm = v[multi]
            lower = edges[:-1][None, :]
            upper = edges[1:][None, :]
            ov = np.minimum(hm[:, None], upper) - np.maximum(lm[:, None], lower)
            ov = np.clip(ov, 0.0, None)
            tot = ov.sum(axis=1, keepdims=True)
            tot[tot <= 0.0] = 1.0
            contrib = vm[:, None] * ov / tot
            bins = np.broadcast_to(np.arange(num_bins)[None, :], ov.shape)
            mask = ov > 0.0
            if mask.any():
                np.add.at(vol, bins[mask].astype(np.intp), contrib[mask])
    return {"centers": centers, "edges": edges, "vol": vol,
            "pmin": pmin, "pmax": pmax}


class RunningZone:
    """Inkrementelle, EXAKTE laufende Volume-Zone (kausal, Bar i_start..k).

    Problem (02.09.2026): collect_candidates rief ns['_laufende_zone'] je
    Bar auf = kompletter Volume-Profil-Neuaufbau der Slice i_start..k -> O(B²)
    je Box. Sample2 (ganzes Jahr 2025, lange Ranges) wirkte dadurch wie eine
    Endlosschleife (skalierte auf 10+ min und mehr).

    Loesung: Die Zone wird INKREMENTELL fortgeschrieben:
      - Solange die laufende Range nicht waechst, bleiben die Bin-Edges
        stabil -> neue Bar wird nur in ihr Profil addiert (O(1)).
      - Erst wenn ein neues Tief/Hoch die Range erweitert, wird das
        Slice-Profil vektorisiert neu gebaut (_profile_vec).
    Ergebnis ist BIT-IDENTISCH zu compute_volume_zone(df.iloc[i_start:k+1])
    (gleiche Edges, gleiche Verteilungs-Arithmetik, gleiche Additionsfolge).
    Wird je Fenster an Stichproben gegen die Original-Funktion verifiziert.
    """
    def __init__(self, ns):
        self.ns = ns
        self.reset()

    def reset(self):
        self.vol = None
        self.edges = None
        self.pmin = None
        self.pmax = None
        self.has = False

    # -- Kern: zone fuer Slice i_start..k (k aufsteigend) --
    def update(self, k, i_start, lows, highs, vols):
        if not self.has:
            return self._rebuild(k, i_start, lows, highs, vols)
        if lows[k] < self.pmin or highs[k] > self.pmax:
            return self._rebuild(k, i_start, lows, highs, vols)
        self._add_bar(lows[k], highs[k], vols[k])
        return self._zone()

    def _rebuild(self, k, i_start, lows, highs, vols):
        prof = _profile_vec(lows[i_start:k + 1], highs[i_start:k + 1],
                            vols[i_start:k + 1], int(self.ns.get("NUM_BINS", 60)))
        if prof is None:
            self.has = False
            self.vol = self.edges = None
            self.pmin = float(lows[i_start:k + 1].min())
            self.pmax = float(highs[i_start:k + 1].max())
            return None
        self.vol = prof["vol"]
        self.edges = prof["edges"]
        self.pmin = prof["pmin"]
        self.pmax = prof["pmax"]
        self.has = True
        return self._zone()

    def _add_bar(self, lo, hi, v):
        """Addiert EINE Bar zum bestehenden Profil (exakt wie build_volume_profile)."""
        if hi <= lo or v <= 0:
            return
        edges = self.edges
        nb = len(edges) - 1
        lo_b = int(np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, nb - 1))
        hi_b = int(np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, nb - 1))
        if lo_b == hi_b:
            self.vol[lo_b] += v
        else:
            ov = np.array([max(0.0, min(hi, edges[b + 1]) - max(lo, edges[b]))
                           for b in range(lo_b, hi_b + 1)], dtype=np.float64)
            tot = ov.sum()
            if tot > 0:
                self.vol[lo_b:hi_b + 1] += v * ov / tot

    def _zone(self):
        """Schwaenzchen von compute_volume_zone: smooth -> Berge -> VAH-Huelle."""
        ns = self.ns
        vol_s = ns["smooth_vol"](self.vol)
        mountains = ns["find_mountains"](vol_s)
        if not mountains:
            return None
        dominant = mountains[0][1]
        peaks = [ns["va_for_mountain"](vol_s, self.edges, m, dominant)
                 for m in mountains]
        return {"U_zone": max(p["vah"] for p in peaks),
                "L_zone": min(p["val"] for p in peaks),
                "POC": peaks[0]["poc"],
                "n_mountains": len(peaks)}


def _check_engine(ns, box, n_samples=25):
    """Verifiziert RunningZone gegen compute_volume_zone (Stichproben).

    Bricht mit RuntimeError ab, wenn die inkrementelle Zone von der
    Original-Neuberechnung abweicht. Nur auf der ERSTEN Box je Fenster.
    """
    df = ns["df"]
    lows = df["low"].values
    highs = df["high"].values
    vols = df["tick_volume"].values
    i0 = int(box["i_start"])
    i1 = int(box["i_ende"])
    ks = np.unique(np.linspace(i0, i1 - 1, min(n_samples, max(1, i1 - i0))).astype(int))
    ks = set(ks.tolist())
    eng = RunningZone(ns)
    for k in range(i0, i1):
        vz = eng.update(k, i0, lows, highs, vols)
        if k in ks:
            ref = ns["compute_volume_zone"](df.iloc[i0:k + 1])
            if vz is None or ref is None:
                if not (vz is None and ref is None):
                    raise RuntimeError(
                        f"[engine] None-Mismatch bei k={k}: inkrementell={vz is None} ref={ref is None}")
            else:
                for key in ("U_zone", "L_zone", "POC"):
                    a = float(vz[key])
                    b = float(ref[key])
                    if a != b:
                        raise RuntimeError(
                            f"[engine] {key}-Mismatch bei k={k}: {a:.6f} vs Original {b:.6f}")
    print(f"        engine-OK (Box {box['phasen']}, {i1 - i0} Bars, {len(ks)} Stichproben)")


def collect_candidates(ns, box, prev_reife, level_fx):
    """Sammelt Roh-Kandidaten in EINEM Durchlauf (inkrementelle Zone).

    Rueckgabe: (cands_base, cands_str)
      - cands_base : ALLE Roh-Kandidaten (entspricht struktur=False)
      - cands_str  : nur Kandidaten an LEGITIMEN Kanten (Struktur-Regel),
                     gefiltert ueber kante_legitim -> legit in {"alt","eck"}
    """
    df = ns["df"]
    _bounce_nr = ns["_bounce_nr"]
    lows = df["low"].values
    highs = df["high"].values
    cl = df["close"].values
    op = df["open"].values
    vols = df["tick_volume"].values
    ts = df["ts"].values
    pd = ns["pd"]
    engine = RunningZone(ns)
    cands = []
    for k in range(box["i_start"], box["i_ende"]):
        vz = engine.update(k, box["i_start"], lows, highs, vols)
        if vz is None:
            continue
        U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
        ts_k = pd.Timestamp(ts[k])
        nb_h, nb_l = _bounce_nr(box["h"], box["h_ts"], box["l"], box["l_ts"],
                                ts_k, U, L)
        if highs[k] > U:
            if cl[k] <= U:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] <= U:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis > POC
                    and nb_h >= ns["MIN_RECLAIM_BOUNCE"]):
                legit = kante_legitim(ns, box, prev_reife, U, "SHORT", ts_k, level_fx)
                cands.append({"k": k, "ts": ts_k, "typ": "SHORT",
                              "e_bar": int(e_bar), "e_preis": e_preis,
                              "U": U, "L": L, "POC": POC, "nb": nb_h,
                              "rec": rec, "box": 0, "legit": legit})
        if lows[k] < L:
            if cl[k] >= L:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] >= L:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis < POC
                    and nb_l >= ns["MIN_RECLAIM_BOUNCE"]):
                legit = kante_legitim(ns, box, prev_reife, L, "LONG", ts_k, level_fx)
                cands.append({"k": k, "ts": ts_k, "typ": "LONG",
                              "e_bar": int(e_bar), "e_preis": e_preis,
                              "U": U, "L": L, "POC": POC, "nb": nb_l,
                              "rec": rec, "box": 0, "legit": legit})
    cands_str = [c for c in cands if c["legit"]]
    return cands, cands_str


def _aufloesen_mit_sl(ns, df, s):
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
        else:
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
             "U": c["U"], "L": c["L"],
             "ts": c["ts"], "box": c["box"], "crv": crv,
             "sl_risk": abs(sl - c["e_preis"]) / c["e_preis"] * 100.0,
             "legit": c.get("legit")}
        s.update(_aufloesen_mit_sl(ns, df, s))
        sigs.append(s)
    return sigs


def run_fenster(name, win_args):
    print(f"\n{'='*80}\n=== FENSTER {name} ({win_args[0].split('=')[1]} .. {win_args[1].split('=')[1]}) ===\n")
    t0 = time.time()
    ns = load_ns(win_args)
    df = ns["df"]
    level_fx = ns["level_schnittmenge"]
    boxen = build_boxes_v7(ns)
    print(f"[boxes] {len(boxen)} Boxen (v7-arm) | reif: "
          + ", ".join(f"B{i+1}{'*' if b['reif'] else ''}" for i, b in enumerate(boxen)))
    # Kandidaten: EIN Durchlauf je Box (inkrementelle Zone), Rueckgabe
    # (base, struktur). Vorab Engine-Verifikation an der ersten Box.
    all_cands_base = []
    all_cands_str = []
    t1 = time.time()
    _check_engine(ns, boxen[0]) if boxen else None
    for bi, b in enumerate(boxen, 1):
        t_b = time.time()
        prev_reife = [bx for j, bx in enumerate(boxen) if j < bi - 1 and bx["reif"]]
        cb, cs = collect_candidates(ns, b, prev_reife, level_fx=level_fx)
        for c in cb:
            c["box"] = bi
        all_cands_base.extend(cb)
        all_cands_str.extend(cs)
        print(f"    Box {bi:>2}/{len(boxen)} | Bars {b['i_start']}-{b['i_ende']} "
              f"| cands base {len(cb):>3} str {len(cs):>2} | {time.time()-t_b:5.1f}s")
    print(f"[cands] ohne Regel {len(all_cands_base)} | mit Regel {len(all_cands_str)} in {time.time()-t1:.1f}s")
    n_alt = sum(1 for c in all_cands_str if c["legit"] == "alt")
    n_box = sum(1 for c in all_cands_str if c["legit"] == "box")
    n_eck = sum(1 for c in all_cands_str if c["legit"] == "eck")
    print(f"        legitim: {n_alt} alt | {n_box} box(reif) | {n_eck} eck")
    print(f"\n{'Variante':<22} | {'Sig':>4} | {'WR':>4} | {'W/L':>6} | {'SummeR':>9} | {'avgR':>6} | {'avgRisk':>7} | {'avgCRV':>6}")
    for label, art, puff, struktur in VARIANTEN:
        cands = all_cands_str if struktur else all_cands_base
        sigs = replay(ns, df, cands, art, puff)
        w = sum(1 for s in sigs if s["resultat"] == "GEWONNEN")
        l = sum(1 for s in sigs if s["resultat"] == "VERLOREN")
        r = sum(s["r_mult"] for s in sigs)
        nn = len(sigs)
        wr = 100.0 * w / (w + l) if w + l else 0.0
        avg_r = r / nn if nn else 0.0
        avg_risk = sum(s["sl_risk"] for s in sigs) / nn if nn else 0.0
        avg_crv = sum(s["crv"] for s in sigs) / nn if nn else 0.0
        print(f"  {label:<20} | {nn:>4} | {wr:>3.0f}% | {w}/{l:>3} | {r:>+9.2f} | {avg_r:>+6.2f} | {avg_risk:>6.2f}% | {avg_crv:>6.2f}")
    print(f"[total] {time.time()-t0:.1f}s")
    if "--detail" in sys.argv:
        print("\n=== DETAIL-SIGNALE struktur+entry ===")
        sigs = replay(ns, df, all_cands_str, "entry", 0.0)
        for s in sorted(sigs, key=lambda x: x["ts"]):
            kante = s["U"] if s["typ"] == "SHORT" else s["L"]
            print(f"  B{s['box']} {s['ts']:%d.%m %H:%M} {s['typ']:5s} "
                  f"Kante {kante:.3f} | POC {s['POC']:.3f} | legit={s['legit']} | "
                  f"{s['resultat']} {s['r_mult']:+.2f}R")
    return all_cands_base, all_cands_str


if __name__ == "__main__":
    mode = next((a for a in sys.argv[1:] if a in FENSTER or a == "--all"), "aug")
    if "--lax" in sys.argv:
        STRUKTUR_STRENG = False
    print(f"[modus] Struktur-Regel: {'STRIKT (nur alt+eck, OHNE box(reif))' if STRUKTUR_STRENG else 'LAX (inkl. box(reif))'}")
    if mode == "--all":
        for k in FENSTER:
            run_fenster(*FENSTER[k])
    elif mode in FENSTER:
        run_fenster(*FENSTER[mode])
    else:
        print("Modi: aug | s1 | s2 | --all")
