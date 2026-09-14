# -*- coding: utf-8 -*-
"""AUG26 Schritt 3 (Phasen 1+2, READ-ONLY): endogener Transitions-Detektor.

Physik dieser Datei
-------------------
Es gibt genau EINEN kausalen Zustandsautomaten mit zwei Zustaenden:

    TRANSITION (NO_MANS_LAND, Initialzustand)
        -> BALANCE      wenn (a) Dwell UND (b) Kantenreife erfuellt sind
    BALANCE
        -> TRANSITION   wenn der Close die eingefrorene Balance-Aussenwand
                        um mehr als die Toleranz verlaesst

Es gibt KEINEN Sonderweg fuer den Monatsanfang: Das System startet in
``TRANSITION``; die Vor-Balance ist damit automatisch Teil desselben
Detektors.

Kausalitaet (Zirkelschluss-Guard)
--------------------------------
Jede Entscheidung an Bar ``k`` liest ausschliesslich ``[0 .. k]``:
Fenster ``[k-W+1 .. k]`` fuer Dwell/Kante, ``close[k]`` fuer den Ausbruch.
Kein ``searchsorted`` in die Zukunft, kein Blick auf die Zonen der
Referenzloesung aus Schritt 2.

DEFAULT_PARAMS (anpassbar, PineScript-Konvention)
-------------------------------------------------
Siehe ``DEFAULT_PARAMS`` direkt unterhalb des Docstrings. ``W`` wird im
Sweep variiert; die uebrigen Werte sind arretiert.

Die Engine (``test/tmp_kanten_engine_replay.py``, SHA 53f28e1b...) bleibt
physisch unveraendert; der Gate-Patch wirkt nur im RAM dieses Skripts.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import Hook2ZielModus  # noqa: E402

DEFAULT_PARAMS: Dict[str, object] = {
    "dwell_fenster_W": (24, 36, 48, 72),  # SWEEP-Achse (Bars)
    "dwell_band_pct": 0.80,      # relatives Band um den Cluster-Mittelwert
    "dwell_anteil_min": 0.80,    # min. Anteil Bars vollstaendig im Band
    "kanten_min_touches": 3,     # V-S-Schwelle der etablierten Balance
    "breakout_pct": 0.30,        # Close muss die Aussenwand so weit verlassen
    "balance_mindest_bars": 24,  # kein Flackern: min. Balance-Dauer
}

W_LISTE: Tuple[int, ...] = DEFAULT_PARAMS["dwell_fenster_W"]  # type: ignore
BAND: float = DEFAULT_PARAMS["dwell_band_pct"]  # type: ignore
DWELL_MIN: float = DEFAULT_PARAMS["dwell_anteil_min"]  # type: ignore
MIN_TOUCH: int = DEFAULT_PARAMS["kanten_min_touches"]  # type: ignore
BREAKOUT: float = DEFAULT_PARAMS["breakout_pct"]  # type: ignore
BAL_MIN: int = DEFAULT_PARAMS["balance_mindest_bars"]  # type: ignore

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08",
        "12.08", "13.08", "14.08", "17.08", "18.08", "19.08", "20.08",
        "21.08", "24.08", "25.08", "26.08", "27.08", "28.08", "31.08"]

# Referenz aus Schritt 2 (Anwender-Nullwerte, nur zum Vergleich)
REF_ZB_ZONEN = ((368, 551), (1104, 1479), (1748, 1904))
REF_ZB = (11, -0.991154)
REF_ZE = (9, +1.008846)


def tag(bar: int) -> str:
    i = bar // 92
    return f"{TAGE[i]}({bar - i * 92:02d})" if 0 <= i < len(TAGE) else "?"


# ============================================================ Engine + Patch
spec = importlib.util.spec_from_file_location("engine_s3", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_s3"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

_src = ENGINE_P.read_text(encoding="utf-8")
_ast = ast.parse(_src)
_node = next(x for x in _ast.body
             if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src_base = ast.get_source_segment(_src, _node)
assert src_base is not None

ANKER_Q29 = (
    '                continue\n'
    '            seite: KantenSeite = "OBEN" if richtung == "SHORT" '
    'else "UNTEN"\n'
    '            basis = kd.basis_bei(k)\n')
assert src_base.count(ANKER_Q29) == 1

GATE = (
    '                continue\n'
    '            # --- AUG26/S3: endogener Phasen-Kontext -----------------\n'
    '            if k < _TRANS_START:\n'
    '                stats["vorbalance_blockiert"] = (\n'
    '                    stats.get("vorbalance_blockiert", 0) + 1)\n'
    '                continue\n'
    '            if any(_ta <= k <= _tb for _ta, _tb in _TRANS_ZONEN):\n'
    '                stats["transition_blockiert"] = (\n'
    '                    stats.get("transition_blockiert", 0) + 1)\n'
    '                continue\n'
    '            seite: KantenSeite = "OBEN" if richtung == "SHORT" '
    'else "UNTEN"\n'
    '            basis = kd.basis_bei(k)\n')
src_trans = src_base.replace(ANKER_Q29, GATE)
assert src_trans != src_base

NS: Dict[str, object] = dict(engine.__dict__)
NS["_Hook2ZielModus"] = Hook2ZielModus
NS["_TRANS_ZONEN"] = ()
NS["_TRANS_START"] = 0


# ====================================================== Phase 1: Detektor
def erkenne_zustaende(scan: Dict, W: int, reife_bars: int = 0
                      ) -> Tuple[List[Tuple[int, str]], Dict[str, object]]:
    """Kausaler Zustandsautomat TRANSITION <-> BALANCE.

    Args:
        scan: Scan-Dict der Engine (edges, seeds, d, n).
        W: Dwell-Fensterlaenge in Bars.
        reife_bars: Wenn > 0, muss die Balance-Kante mindestens so alt sein
            (Q24 ``min_wall_alter_bars``). Verhindert, dass ein Fensteranfang
            mit drei fruehen Dochten sofort als Balance durchgeht.

    Returns:
        verlauf: Liste ``(bar, zustand)`` je Umschaltpunkt (nur Wechsel).
        info: Diagnose (erste Balance, Balances, Details).
    """
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    n = int(scan["n"])
    kanten = [e for e in list(scan["edges"]) + list(scan["seeds"])
              if e.touch_anzahl >= MIN_TOUCH]

    zustand = "TRANSITION"
    verlauf: List[Tuple[int, str]] = [(0, "TRANSITION")]
    details: List[Dict[str, object]] = []
    bal: List[Tuple[int, int, float, float]] = []
    zone_hi = zone_lo = 0.0
    bal_start = -1
    k = W - 1
    while k < n:
        a = k - W + 1
        whi = float(hi[a:k + 1].max())
        wlo = float(lo[a:k + 1].min())
        mid = 0.5 * (whi + wlo)
        b_ob = mid * (1.0 + BAND / 100.0)
        b_un = mid * (1.0 - BAND / 100.0)
        drin = sum(1 for j in range(a, k + 1)
                   if lo[j] >= b_un and hi[j] <= b_ob)
        dwell = drin / float(W)
        kante_ok = any(abs(float(e.basis_bei(k)) - mid) / mid * 100.0 <= BAND
                       and (reife_bars <= 0
                            or k - int(e.erster_pivot_bar) >= reife_bars)
                       for e in kanten)

        if zustand == "TRANSITION":
            if dwell >= DWELL_MIN and kante_ok:
                zustand = "BALANCE"
                bal_start = a
                zone_hi, zone_lo = whi, wlo
                verlauf.append((k, "BALANCE"))
                details.append({"art": "BALANCE_START", "bar": k,
                                "dwell": round(dwell, 3),
                                "zone": (round(zone_lo, 4),
                                         round(zone_hi, 4))})
        else:
            bo = (cl[k] > zone_hi * (1.0 + BREAKOUT / 100.0)
                  or cl[k] < zone_lo * (1.0 - BREAKOUT / 100.0))
            if bo and (k - bal_start + 1) >= BAL_MIN:
                bal.append((bal_start, k, zone_lo, zone_hi))
                zustand = "TRANSITION"
                verlauf.append((k, "TRANSITION"))
                details.append({"art": "BALANCE_ENDE", "bar": k,
                                "dwell": round(dwell, 3),
                                "close": round(float(cl[k]), 4),
                                "zone": (round(zone_lo, 4),
                                         round(zone_hi, 4))})
                zone_hi = zone_lo = 0.0
                bal_start = -1
        k += 1
    if zustand == "BALANCE":
        bal.append((bal_start, n - 1, zone_lo, zone_hi))
        details.append({"art": "BALANCE_ENDE", "bar": n - 1,
                        "dwell": None, "close": round(float(cl[-1]), 4),
                        "zone": (round(zone_lo, 4), round(zone_hi, 4))})

    # Transition-Intervalle ableiten (inkl. Initialzustand)
    trans: List[Tuple[int, int]] = []
    lauf: int | None = None
    for (bar, z) in verlauf:
        if z == "TRANSITION" and lauf is None:
            lauf = bar
        elif z == "BALANCE" and lauf is not None:
            trans.append((lauf, bar - 1))
            lauf = None
    if lauf is not None:
        trans.append((lauf, n - 1))
    trans = [(a, b) for (a, b) in trans if b >= a]

    erste_bal = bal[0][0] if bal else None
    info: Dict[str, object] = {
        "verlauf": verlauf, "details": details, "bals": bal,
        "trans": trans, "erste_bal": erste_bal,
        "bal_start_bar": bal[0][0] if bal else 0,
    }
    return verlauf, info


# ====================================================== Phase 2: Sweep-Lauf
def run(fenster: str, label: str) -> None:
    engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
    cfg = engine.StraightEdgeHarnessKonfiguration()
    scan = engine._se_scan(fenster, cfg)  # type: ignore[arg-type]
    n = int(scan["n"])
    scan["box_end_bar"] = n
    ts = list(scan["d"]["ts"])

    print("=" * 108)
    print(f"{label}: ENDOGENER TRANSITIONS-DETEKTOR — SWEEP "
          f"W = {', '.join(str(w) for w in W_LISTE)}")
    print("=" * 108)
    print(f"Engine-SHA (unveraendert) "
          f"{hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:16]}... | "
          f"n = {n} | Band {BAND} % | Dwell-Anteil >= {DWELL_MIN} | "
          f"Touches >= {MIN_TOUCH} | Breakout {BREAKOUT} %")
    print(f"Referenz Schritt 2: ZB (fest) = {REF_ZB[0]} Trades / "
          f"{REF_ZB[1]:+.6f} R   |   ZE = {REF_ZE[0]} / {REF_ZE[1]:+.6f} R")

    erg: List[Tuple[int, Dict[str, object], List, Dict]] = []
    for W in W_LISTE:
        _v, info = erkenne_zustaende(scan, W)
        zonen = tuple(info["trans"])  # type: ignore[arg-type]
        start = int(info["bal_start_bar"])  # type: ignore[arg-type]
        NS["_TRANS_ZONEN"] = zonen
        NS["_TRANS_START"] = start
        exec(compile(src_trans, "<s3>", "exec"), NS)  # noqa: S102
        S, st = NS["_se_trades"](copy.deepcopy(scan), cfg)  # type: ignore
        erg.append((W, info, list(S), dict(st)))

    # ------------------------------------------------------------- Zonen
    print("\n" + "-" * 108)
    print("PHASE 1 — ZUSTANDSVERLAUF je Fenstergroesse")
    print("-" * 108)
    for W, info, _S, _st in erg:
        bals = info["bals"]  # type: ignore[assignment]
        print(f"\n   W = {W:>3} Bars ({W / 4.0:.0f} h)   "
              f"Balances {len(bals)}   erste Balance ab Bar "
              f"{info['erste_bal']} "
              f"({tag(int(info['erste_bal'])) if info['erste_bal'] is not None else '-'})")
        print(f"      {'#':<3}{'Balance-Fenster':<20}{'Tage':<18}"
              f"{'Zone (Boden..Decke)':<26}")
        for i, (a, b, zl, zh) in enumerate(bals, 1):
            print(f"      {i:<3}{f'{a}..{b}':<20}{f'{tag(a)}..{tag(b)}':<18}"
                  f"{f'{zl:.4f}..{zh:.4f}':<26}")
        tr = info["trans"]  # type: ignore[assignment]
        print(f"      TRANSITION-Intervalle ({len(tr)}): "
              f"{[(f'{a}..{b}', tag(a)) for a, b in tr]}")

    # ------------------------------------------- Treffer der Ziel-Zonen
    print("\n" + "-" * 108)
    print("PHASE 1b — REPRODUZIEREN DIE ZONEN DIE ANWENDER-NULLWERTE?")
    print("-" * 108)
    print(f"   Ziel 1: Vor-Balance endet nahe Bar 552 (11.08.)")
    print(f"   Ziel 2: Transition 2 deckt 1104..1479")
    print(f"   Ziel 3: Transition 3 deckt 1748..1904")
    for W, info, _S, _st in erg:
        eb = info["erste_bal"]
        tr = info["trans"]  # type: ignore[assignment]
        # Zone, die 1200 enthaelt
        z2 = next(((a, b) for a, b in tr if a <= 1200 <= b), None)
        z3 = next(((a, b) for a, b in tr if a <= 1800 <= b), None)
        print(f"\n   W = {W:>3}: erste Balance {eb} -> Ziel 552: "
              f"{'TREFFER' if eb is not None and abs(int(eb) - 552) <= 48 else 'ABWEICHUNG'} "
              f"(Delta {int(eb) - 552 if eb is not None else 0:+d})")
        print(f"            Z2 um 1200: {z2}  "
              f"(Ziel 1104..1479)  "
              f"{'TREFFER' if z2 and abs(z2[0] - 1104) <= 48 else 'ABWEICHUNG'}")
        print(f"            Z3 um 1800: {z3}  "
              f"(Ziel 1748..1904)  "
              f"{'TREFFER' if z3 and abs(z3[0] - 1748) <= 48 else 'ABWEICHUNG'}")

    # ---------------------------------------------- Phase 1c: Q24-Reife
    Q24 = int(cfg.min_wall_alter_bars)
    print("\n" + "-" * 108)
    print(f"PHASE 1c (Zusatz) — DETEKTOR + Q24-KANTENREIFE "
          f"(min_wall_alter_bars = {Q24}, Engine-Konstante)")
    print("-" * 108)
    print(f"   Detektor selbst kennt die Reife NICHT; die Kante muss aber "
          f"mindestens {Q24} Bars alt sein.")
    print(f"\n   {'W':>4}{'1. Balance':>12}{'Zonen':>7}"
          f"  {'Z2 um 1200':<16}{'Z3 um 1800':<16}"
          f"{'Trades':>8}{'R':>11}")
    for W in W_LISTE:
        _v, info = erkenne_zustaende(scan, W, reife_bars=Q24)
        tr = info["trans"]  # type: ignore[assignment]
        z2 = next(((a, b) for a, b in tr if a <= 1200 <= b), None)
        z3 = next(((a, b) for a, b in tr if a <= 1800 <= b), None)
        NS["_TRANS_ZONEN"] = tuple(tr)
        NS["_TRANS_START"] = int(info["bal_start_bar"])  # type: ignore
        exec(compile(src_trans, "<s3c>", "exec"), NS)  # noqa: S102
        S, st = NS["_se_trades"](copy.deepcopy(scan), cfg)  # type: ignore
        S = list(S)
        print(f"   {W:>4}{int(info['erste_bal'] or 0):>12}"
              f"{len(tr):>7}  {str(z2):<16}{str(z3):<16}"
              f"{len(S):>8}{sum(float(t.r) for t in S):>+11.4f}")

    # ------------------------------------------------------ Trade-Bilanz
    print("\n" + "-" * 108)
    print("PHASE 2 — TRADE-/PnL-BILANZ je Sweep-Stufe (V0 mit endogenem Gate)")
    print("-" * 108)
    print(f"   {'W':>4}{'Trades':>8}{'Treffer':>9}{'SL':>5}{'R_brutto':>12}"
          f"{'vs ZB':>10}{'vs ZE':>10}{'trans_block':>13}{'vorb_block':>12}")
    for W, info, S, st in erg:
        r = sum(float(t.r) for t in S)
        tr = sum(1 for t in S if float(t.r) > 0)
        sl = sum(1 for t in S if float(t.r) <= -0.999)
        print(f"   {W:>4}{len(S):>8}{tr:>9}{sl:>5}{r:>+12.4f}"
              f"{r - REF_ZB[1]:>+10.4f}{r - REF_ZE[1]:>+10.4f}"
              f"{int(st.get('transition_blockiert', 0)):>13}"
              f"{int(st.get('vorbalance_blockiert', 0)):>12}")

    print(f"\n   Referenz  ZB (fest 368-551/1104-1479/1748-1904): "
          f"{REF_ZB[0]} Trades / {REF_ZB[1]:+.6f} R")
    print(f"   Referenz  ZE (ZB + Grenze 552):                   "
          f"{REF_ZE[0]} Trades / {REF_ZE[1]:+.6f} R")

    # --------------------------------------------- Trade-Signaturen
    print("\n" + "-" * 108)
    print("PHASE 2b — WELCHE TRADES BLEIBEN JE W UEBRIG?")
    print("-" * 108)
    for W, info, S, _st in erg:
        print(f"\n   W = {W:>3}  ({len(S)} Trades, "
              f"{sum(float(t.r) for t in S):+.4f} R):")
        for t in sorted(S, key=lambda x: int(x.entry_bar)):
            print(f"      bar {int(t.entry_bar):>5} "
                  f"{tag(int(t.entry_bar)):<12} {t.richtung:<6} "
                  f"K{int(t.kid):<4} {float(t.r):>+10.4f}  "
                  f"({t.grund1}/{t.grund2})")


run("AUG26", "AUG26")
print("\nENDE AUG26 SCHRITT 3 (PHASE 1+2)")
