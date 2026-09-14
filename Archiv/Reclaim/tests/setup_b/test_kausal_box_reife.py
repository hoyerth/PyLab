# test/test_kausal_box_reife.py
"""KAUSALER UMBau der Segmentierung: 3-Eckpunkte REGEL (User, 02.09.2026).

Regel (User-Variante, strikt):
  a) Eine NEUE Phase/Box braucht min. 3 Eckpunkte (H-L-H ODER L-H-L),
     wobei NUR Kanten ausserhalb der alten (offenen) Box zaehlen
     ("start counting any edge that is outside an old phase").
  b) Weite |p2-p1|/min(p1,p2) >= 1.5% (MIN_WEITE_PCT).
  Konsequenz: Ein 2-Close-Ausbruch beendet die Box NICHT automatisch.
  Der Ausbruch wird zunaechst ein "ARM" der alten Box; erst wenn sich
  ausserhalb der alten Box eine echte 3-Eck-Struktur bildet, reift eine
  NEUE Box (alte Box endet, neue Box beginnt). Nie reif bis Datenende
  -> Box bleibt offen (Regel-7-Finalize unveraendert, nur letzte Box).

KAUSALITAET:
  - Basis sind die KAUSALEN Phasen-Kandidaten des Hauptskripts
    (Pivot-Lag PIVOT_LOOKBACK, laufende Linie, 2-Close-Ausbruch).
    Jeder Kandidat ist zum Zeitpunkt seines Ausbruchs vollstaendig
    bekannt -> sequentielle Entscheidung (reif/arm) ist kausal.
  - Die offene Box enthaelt nur Pivots, die VOR dem Kandidaten bekannt
    waren (Arme werden erst NACH der Entscheidung gemerged).
  - KEIN unbeschraenkter Loop: reine Vorwaerts-Iteration ueber die
    Kandidaten-Liste (Terminierungs-Garantie, vgl. S2-Endloslauf 01.09.).

Vergleich:
  - Baseline (bestehende Segmentierung)
  - v6-Regel OHNE Aussen-Filter (reife_check wie test_diag_3eck_v6.py)
  - STRICT (User): 3-Eck nur aus Kanten AUSSERHALB der offenen Box
  - AB_REIFE: Signale je Box erst ab dem Reife-Zeitpunkt (t_reif) der Box
    (Zone laeuft weiter ab Box-Beginn; Box ohne t_reif = erste Box -> ab
    Box-Beginn). Abschaltbar mit --ab-reife=0.

Aufruf:
  python test/test_kausal_box_reife.py                      # August (Default)
  python test/test_kausal_box_reife.py --start=2026-02-05 --ende=2026-08-28   # S1
  # S2 (2025) ist SEHR langsam (vgl. Endlos-Verdacht 01.09.) -> nur --force:
  python test/test_kausal_box_reife.py --start=2025-01-01 --ende=2025-12-01 --force
  python test/test_kausal_box_reife.py --tol-kante=0.30 --weite-pct=1.5
  python test/test_kausal_box_reife.py --ab-reife=0          # ohne Reife-Untergrenze
"""
from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"

# --- Parameter (User-Regel) ---
TOL_KANTE = 0.30       # |p1-p3| <= TOL_KANTE (gleiche Kante)
MIN_WEITE_PCT = 1.5    # min. Weite |p2-p1| in %
STRICT_OUTSIDE = True  # User-Variante: nur Kanten ausserhalb der alten Box
AB_REIFE = True        # Signale je Box erst ab deren Reife-Zeitpunkt (t_reif)
# --- 02.09.2026: Zwei neue Test-Regeln gegen Riesen-Boxen (S1-Kollaps) ---
MAX_ARME_PRO_BOX = 0   # (a) Box-Lebensdauer: max. Phasen/Arme pro Box (0=aus)
MAX_BOX_SPAN_DAYS = 0.0  # (a) max. Kalenderspanne einer Box in Tagen (0=aus)
MAX_KANTEN_ALTER_BARS = 0  # (b) Frische-Kante: max. Alter des letzten Touches
                           #     der getesteten Kante in Bars (0=aus)
MAX_BARS_DEFAULT = 6000  # Schutz gegen versehentliche Riesen-/S2-Laeufe
START = "2026-08-10"
ENDE = "2026-08-28"
_FORCE = False

for _a in sys.argv[1:]:
    if _a.startswith("--tol-kante="):
        TOL_KANTE = float(_a.split("=", 1)[1])
    if _a.startswith("--weite-pct="):
        MIN_WEITE_PCT = float(_a.split("=", 1)[1])
    if _a.startswith("--start="):
        START = _a.split("=", 1)[1]
    if _a.startswith("--ende="):
        ENDE = _a.split("=", 1)[1]
    if _a == "--force":
        _FORCE = True
    if _a == "--v6":  # Vergleichsmodus: OHNE Aussen-Filter (wie test_diag_3eck_v6)
        STRICT_OUTSIDE = False
    if _a.startswith("--ab-reife="):
        AB_REIFE = _a.split("=", 1)[1] != "0"
        print(f"==> AB_REIFE={AB_REIFE}")
    if _a.startswith("--max-arme="):
        MAX_ARME_PRO_BOX = int(_a.split("=", 1)[1])
        print(f"==> MAX_ARME_PRO_BOX={MAX_ARME_PRO_BOX}")
    if _a.startswith("--max-span-days="):
        MAX_BOX_SPAN_DAYS = float(_a.split("=", 1)[1])
        print(f"==> MAX_BOX_SPAN_DAYS={MAX_BOX_SPAN_DAYS}")
    if _a.startswith("--kanten-alter-bars="):
        MAX_KANTEN_ALTER_BARS = int(_a.split("=", 1)[1])
        print(f"==> MAX_KANTEN_ALTER_BARS={MAX_KANTEN_ALTER_BARS}")


def load_ns(start: str, ende: str) -> dict:
    """Fuehrt das Hauptskript bis VOR der Signal-Sammlung aus (wie v6).

    Dataclasses im Hauptskript brauchen ein Modul in sys.modules (ihr
    __module__), deshalb wird der exec-Namespace als Modul registriert.
    """
    src = SRC.read_text(encoding="utf-8")
    cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
    mod_name = "_phasen_volumen_profil_import"
    if mod_name not in sys.modules:
        mod = types.ModuleType(mod_name)
        mod.__file__ = str(SRC)
        sys.modules[mod_name] = mod
    else:
        mod = sys.modules[mod_name]
    # Kommandozeilen-Overrides des Hauptskripts fuer das Fenster nutzen:
    sys.argv = [str(SRC), f"--start={start}", f"--ende={ende}"]
    t0 = time.perf_counter()
    exec(compile(src[:cut], str(SRC), "exec"), mod.__dict__)
    print(f"[load] Fenster {start}..{ende}: {len(mod.__dict__['df'])} Bars in "
          f"{time.perf_counter()-t0:.1f}s | {len(mod.__dict__['phases'])} Phasen-Kandidaten")
    return mod.__dict__


def cand_events(P) -> list:
    """Alle bestaetigten Pivot-Events eines Phasen-Kandidaten (zeitlich)."""
    ev = []
    ev += [(t, "H", float(p)) for p, t in zip(P.h_prices, P.h_ts)]
    ev += [(t, "L", float(p)) for p, t in zip(P.l_prices, P.l_ts)]
    ev.sort(key=lambda e: e[0])
    return ev


def box_edges(box: dict) -> tuple:
    """Grenzen der offenen Box aus ihren Pivots (Schnittmengen-Linie)."""
    h = box.get("h", [])
    l = box.get("l", [])
    U = ns["level_schnittmenge"](h, "H") if h else None
    L = ns["level_schnittmenge"](l, "L") if l else None
    return U, L


def find_tripel(events: list, tol_kante: float, min_weite_pct: float):
    """3 aufeinanderfolgende abwechselnde Events (H-L-H/L-H-L) mit |p1-p3|<=tol
    und Weite >= min_weite_pct. Rueckgabe (t_reif, tripel) oder (None, None)."""
    for i in range(len(events) - 2):
        t1, typ1, p1 = events[i]
        t2, typ2, p2 = events[i + 1]
        t3, typ3, p3 = events[i + 2]
        if typ1 == typ2 or typ2 == typ3 or typ1 != typ3:
            continue
        if abs(p1 - p3) > tol_kante:
            continue
        weite = abs(p2 - p1) / min(p1, p2) * 100.0
        if weite >= min_weite_pct:
            return t3, (typ1, p1, typ2, p2, typ3, p3, weite)
    return None, None


def reife_aussen(P, box: dict | None, tol_kante: float, min_weite_pct: float):
    """3-Eckpunkte-Regel.

    - box is None (erster Kandidat): keine alte Box -> (False, None, None)
      (der ERSTE Kandidat startet immer die erste Box).
    - STRICT_OUTSIDE: Es zaehlen NUR Events ausserhalb der alten Box
      (H/L oberhalb U_box bzw. unterhalb L_box). Up-/Down-Seite getrennt.
    - nicht-strikt (--v6): alle Events des Kandidaten (v6-Referenz).
    Rueckgabe: (reif, t_reif, tripel, ref_U, ref_L)
    """
    if box is None:
        return False, None, None, None, None
    events = cand_events(P)
    if not STRICT_OUTSIDE:
        t, trip = find_tripel(events, tol_kante, min_weite_pct)
        return (t is not None), t, trip, None, None
    U, L = box_edges(box)
    ups = [e for e in events if U is not None and e[2] > U]
    downs = [e for e in events if L is not None and e[2] < L]
    t_up, tr_up = find_tripel(ups, tol_kante, min_weite_pct)
    t_dn, tr_dn = find_tripel(downs, tol_kante, min_weite_pct)
    if t_up is not None and (t_dn is None or t_up <= t_dn):
        return True, t_up, tr_up, U, L
    if t_dn is not None:
        return True, t_dn, tr_dn, U, L
    return False, None, None, U, L


def build_boxes(phases, tol_kante: float, min_weite_pct: float,
                max_arme: int = 0, max_span_days: float = 0.0) -> list:
    """Kausaler Box-Aufbau: sequentielle Vorwaerts-Iteration ueber die
    Phasen-Kandidaten (Terminiert garantiert: for-Schleife, i waechst).

    max_arme/max_span_days: Box-Lebensdauer-Cap. Wird ein ARM-Kandidat die
    Box ueber das Cap hinaus verlaengern, wird die Box vorher geschlossen
    und der Kandidat startet als Seed einer frischen Box (die 3-Eck-Reife
    beginnt danach neu gegen die neue Box)."""
    boxes: list = []
    offen: dict | None = None
    n_gecappt = 0

    def _neue_box(P, nr, reif, t_reif):
        return {
            "i_start": P.i_start, "i_ende": P.i_ende,
            "start": P.start, "ende": P.ende,
            "phasen": [nr], "reif": reif, "t_reif": t_reif,
            "h": list(P.h_prices), "h_ts": list(P.h_ts),
            "l": list(P.l_prices), "l_ts": list(P.l_ts),
        }

    def _cap_erreicht(P) -> bool:
        if offen is None:
            return False
        if max_arme > 0 and len(offen["phasen"]) + 1 > max_arme:
            return True
        if max_span_days > 0:
            span = (P.ende - offen["start"]).total_seconds() / 86400.0
            if span > max_span_days:
                return True
        return False

    for nr, P in enumerate(phases, 1):
        reif, t_reif, tripel, ref_U, ref_L = reife_aussen(P, offen, tol_kante, min_weite_pct)
        if reif and offen is not None:
            boxes.append(offen)
            offen = _neue_box(P, nr, True, t_reif)
            lbl = "NEUE BOX (reif)"
        elif offen is None:
            offen = _neue_box(P, nr, False, None)
            lbl = "erste Box (Start)"
        elif _cap_erreicht(P):
            # Cap: Box schliessen, Kandidat als Seed einer frischen Box
            boxes.append(offen)
            offen = _neue_box(P, nr, False, None)
            n_gecappt += 1
            lbl = f"CAP->NEUE BOX (Seed, {n_gecappt})"
        else:
            # ARM: an offene Box anhaengen
            offen["i_ende"] = max(offen["i_ende"], P.i_ende)
            if P.ende > offen["ende"]:
                offen["ende"] = P.ende
            offen["phasen"].append(nr)
            offen["h"].extend(P.h_prices); offen["h_ts"].extend(P.h_ts)
            offen["l"].extend(P.l_prices); offen["l_ts"].extend(P.l_ts)
            lbl = "ARM  -> merge"
        _t = f"{t_reif:%d.%m %H:%M}" if t_reif is not None else "-"
        _tr = ""
        if tripel:
            typ1, p1, typ2, p2, typ3, p3, w = tripel
            _tr = f" | Tripel {typ1} {p1:.2f}/{typ2} {p2:.2f}/{typ3} {p3:.2f} (W {w:.2f}%)"
        print(f"  P{nr:>2} [{lbl:<15}] reif={reif!s:<5} t_reif={_t}{_tr}")
    if offen is not None:
        boxes.append(offen)
    return boxes


def sig_stats(sigs) -> tuple:
    n = len(sigs)
    w = sum(1 for s in sigs if s.trade and s.trade.resultat == "GEWONNEN")
    l = sum(1 for s in sigs if s.trade and s.trade.resultat == "VERLOREN")
    r = sum(s.trade.r_mult for s in sigs if s.trade)
    return n, w, l, r


def _bar_idx(df, t) -> int | None:
    """Bar-Index zum Zeitstempel t (t stammt aus P.h_ts/l_ts = df ts)."""
    hits = np.flatnonzero(df["ts"].values == np.datetime64(t))
    return int(hits[0]) if len(hits) else None


def _kanten_alter_bars(ns, df, p, sig) -> int | None:
    """Alter des letzten Touches der getesteten Kante in Bars (fuer sig).

    Kante = sig.U_laufend (SHORT) bzw. sig.L_laufend (LONG). Touch = Pivot
    der Box innerhalb DENSITY_BAND um die Kante, zeitlich <= sig.ts.
    Rueckgabe: sig.bar - Bar(letzter Touch), oder None wenn kein Touch
    (dann gilt die Kante als NICHT durch Preisaktion getestet -> fuer die
    Frische-Regel nicht handelbar).
    """
    band = ns["DENSITY_BAND"]
    if sig.typ == "SHORT":
        cand = [t for pr, t in zip(p.h_prices, p.h_ts)
                if abs(pr - sig.U_laufend) <= band and t <= sig.ts]
    else:
        cand = [t for pr, t in zip(p.l_prices, p.l_ts)
                if abs(pr - sig.L_laufend) <= band and t <= sig.ts]
    if not cand:
        return None
    idx = _bar_idx(df, max(cand))
    if idx is None:
        return None
    return int(sig.bar) - idx


def find_reclaim_signals_ab(ns, df, p, sig_start, min_candles=None,
                            min_bounce=None, min_crv=None, cooldown_bars=None):
    """Kopie von find_reclaim_signals (Hauptskript) mit Signal-Untergrenze.

    sig_start: fruehester Bar-Index, ab dem Signale erzeugt werden.
    Die laufende Volume-Zone wird weiter ab p.i_start (Box-Beginn)
    berechnet (_laufende_zone nutzt p.i_start) - nur der Signal-Loop und
    das Cooldown beginnen bei sig_start (kausal, keine Vor-Reife-Signale).
    """
    np_ = ns["np"]
    if min_candles is None:
        min_candles = ns["MIN_RECLAIM_CANDLES"]
    if min_bounce is None:
        min_bounce = ns["MIN_RECLAIM_BOUNCE"]
    if min_crv is None:
        min_crv = ns["MIN_RECLAIM_CRV"]
    if cooldown_bars is None:
        cooldown_bars = ns["MIN_SIGNAL_ABSTAND_BARS"]
    sigs = []
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values
    op = df["open"].values
    ts = df["ts"].values
    last_bar = {"SHORT": -10**9, "LONG": -10**9}
    tp2_puffer = ns["TP2_PUFFER_PCT"] / 100.0
    sl_p = ns["SL_PCT"] / 100.0
    k0 = max(p.i_start, int(sig_start))
    for k in range(k0, p.i_ende):
        if k - p.i_start + 1 < min_candles:
            continue
        vz = ns["_laufende_zone"](df, p, k)
        if vz is None:
            continue
        U, L, POC = vz.U_zone, vz.L_zone, vz.POC
        if not ((hi[k] > U) or (lo[k] < L)):
            continue
        ts_k = ns["pd"].Timestamp(ts[k])
        nb_h, nb_l = ns["_bounce_nr"](p.h_prices, p.h_ts, p.l_prices, p.l_ts,
                                      ts_k, U, L)
        if hi[k] > U:
            if cl[k] <= U:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 1 <= p.i_ende and cl[k + 1] <= U:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if (reclaim is not None and e_bar is not None and e_bar <= p.i_ende
                    and e_preis > POC and nb_h >= min_bounce
                    and k - last_bar["SHORT"] >= cooldown_bars):
                sl = e_preis * (1.0 + sl_p)
                tp1 = POC
                tp2 = L * (1.0 + tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np_.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np_.nan
                if not np_.isnan(crv) and crv >= min_crv:
                    last_bar["SHORT"] = k
                    sig = ns["ReclaimSignal"](
                        typ="SHORT", bar=int(k), ts=ts_k, reclaim=reclaim,
                        einstieg_bar=int(e_bar), einstieg_preis=e_preis,
                        U_laufend=U, L_laufend=L, POC=POC, tp1=tp1, tp2=tp2,
                        sl=sl, crv=crv, crv2=crv2, bounce_nr=nb_h)
                    sig.trade = ns["_aufloesen"](df, sig)
                    sigs.append(sig)
        if lo[k] < L:
            if cl[k] >= L:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 1 <= p.i_ende and cl[k + 1] >= L:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if (reclaim is not None and e_bar is not None and e_bar <= p.i_ende
                    and e_preis < POC and nb_l >= min_bounce
                    and k - last_bar["LONG"] >= cooldown_bars):
                sl = e_preis * (1.0 - sl_p)
                tp1 = POC
                tp2 = U * (1.0 - tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np_.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np_.nan
                if not np_.isnan(crv) and crv >= min_crv:
                    last_bar["LONG"] = k
                    sig = ns["ReclaimSignal"](
                        typ="LONG", bar=int(k), ts=ts_k, reclaim=reclaim,
                        einstieg_bar=int(e_bar), einstieg_preis=e_preis,
                        U_laufend=U, L_laufend=L, POC=POC, tp1=tp1, tp2=tp2,
                        sl=sl, crv=crv, crv2=crv2, bounce_nr=nb_l)
                    sig.trade = ns["_aufloesen"](df, sig)
                    sigs.append(sig)
    return sigs


def run_boxes(df, boxes, ab_reife: bool = True) -> list:
    """Setup B auf jeder Box.

    ab_reife=True: Signal-Start = Bar-Index des Box-Reife-Zeitpunkts (t_reif).
    Boxen ohne t_reif (erste/Seed-Box) -> Signal-Start = Box-Beginn.
    """
    alle = []
    for bi, b in enumerate(boxes, 1):
        p = SimpleNamespace(i_start=b["i_start"], i_ende=b["i_ende"],
                            h_prices=b["h"], h_ts=b["h_ts"],
                            l_prices=b["l"], l_ts=b["l_ts"])
        sig_start = p.i_start
        ab_txt = ""
        if ab_reife and b.get("t_reif") is not None:
            idx = _bar_idx(df, b["t_reif"])
            if idx is not None:
                sig_start = idx
                ab_txt = f" (ab Reife {b['t_reif']:%d.%m %H:%M})"
            else:
                print(f"  WARNUNG: t_reif {b['t_reif']} nicht in df gefunden "
                      f"-> Box-Beginn")
        if sig_start > p.i_start:
            sigs = find_reclaim_signals_ab(ns, df, p, sig_start)
        else:
            sigs = ns["find_reclaim_signals"](df, p)
        # (b) Frische-Kanten-Regel: nur Signale, deren getestete Kante einen
        # Touch innerhalb der letzten MAX_KANTEN_ALTER_BARS Bars hatte.
        if MAX_KANTEN_ALTER_BARS > 0:
            vorher = len(sigs)
            sigs = [s for s in sigs
                    if (a := _kanten_alter_bars(ns, df, p, s)) is not None
                    and a <= MAX_KANTEN_ALTER_BARS]
            if vorher != len(sigs):
                print(f"      [Frische-Kante] {vorher} -> {len(sigs)} Signale "
                      f"(Alter <= {MAX_KANTEN_ALTER_BARS} Bars)")
        n, w, l, r = sig_stats(sigs)
        ph = "+".join(f"P{x}" for x in b["phasen"])
        print(f"  B{bi} ({b['start']:%d.%m}-{b['ende']:%d.%m}) Phasen {ph}: "
              f"{n:2d} Sig | {w}W/{l}L | {r:+8.2f}R{ab_txt}")
        alle += list(sigs)
    return alle


# ==============================================================================
if __name__ == "__main__":
    t_start = time.perf_counter()
    ns = load_ns(START, ENDE)
    df = ns["df"]
    n_bars = len(df)
    if n_bars > MAX_BARS_DEFAULT and not _FORCE:
        print(f"\nABBRUCH: Fenster hat {n_bars} Bars > MAX_BARS_DEFAULT "
              f"({MAX_BARS_DEFAULT}). S1/S2-Laeufe sind sehr langsam/"
              f"risikobehaftet (vgl. S2-Endlos-Verdacht 01.09.). "
              f"Mit --force wirklich starten.")
        sys.exit(2)
    phases = ns["phases"]

    mode = "STRICT (User: nur Kanten ausserhalb der alten Box)" if STRICT_OUTSIDE \
        else "v6-Referenz (alle Kanten des Kandidaten)"
    print(f"\n=== Kausale 3-Eck-Segmentierung | {mode} | "
          f"TOL_KANTE={TOL_KANTE} | MIN_WEITE_PCT={MIN_WEITE_PCT} ===")

    print("\n--- 1) ENTSCHEIDUNG JE PHASEN-KANDIDAT (kausal, sequentiell) ---")
    print(f"    (Caps: MAX_ARME_PRO_BOX={MAX_ARME_PRO_BOX} | "
          f"MAX_BOX_SPAN_DAYS={MAX_BOX_SPAN_DAYS})")
    boxes = build_boxes(phases, TOL_KANTE, MIN_WEITE_PCT,
                        max_arme=MAX_ARME_PRO_BOX,
                        max_span_days=MAX_BOX_SPAN_DAYS)

    print("\n--- 2) BOXEN (Verschmelzung, Arme = an alte Box) ---")
    for bi, b in enumerate(boxes, 1):
        U, L = box_edges(b)
        u_s = f"{U:.2f}" if U is not None else "N/A"
        l_s = f"{L:.2f}" if L is not None else "N/A"
        r_s = "REIF" if b["reif"] else "Arm-Sammlung"
        ra = f"{b['t_reif']:%d.%m %H:%M}" if b.get("t_reif") is not None else "-"
        ph = "+".join(f"P{x}" for x in b["phasen"])
        print(f"  B{bi}: {b['start']:%d.%m %H:%M}-{b['ende']:%d.%m %H:%M} | "
              f"Phasen {ph} | Box {u_s}/{l_s} | {r_s} {ra}")

    print("\n--- 3) SIGNALE (Setup B auf den Boxen, kausal) ---")
    reife_txt = "ab Box-Reife (t_reif)" if AB_REIFE else "ab Box-Beginn (ohne Reife-Untergrenze)"
    print(f"    (Signal-Start: {reife_txt})")
    alle = run_boxes(df, boxes, ab_reife=AB_REIFE)
    n, w, l, r = sig_stats(alle)
    nn = len(alle)
    print(f"\n  GESAMT Boxen    : {nn:2d} Sig | {w}W/{l}L | "
          f"{100.0*w/(w+l) if w+l else 0:.0f}% | {r:+8.2f}R | avg "
          f"{r/nn if nn else 0:+.2f}")

    print("\n--- 4) BASELINE (bestehende Segmentierung) ---")
    base = []
    for pi, P in enumerate(phases, 1):
        for s in ns["find_reclaim_signals"](df, P):
            s.phase = pi
            base.append(s)
    nb, wb, lb, rb = sig_stats(base)
    print(f"  BASELINE        : {nb:2d} Sig | {wb}W/{lb}L | "
          f"{100.0*wb/(wb+lb) if wb+lb else 0:.0f}% | {rb:+8.2f}R | avg "
          f"{rb/nb if nb else 0:+.2f}")

    print(f"\n  LAUFZEIT gesamt : {time.perf_counter()-t_start:.1f}s "
          f"| KEIN Endlos-Loop (for-Iteration, terminiert)")
