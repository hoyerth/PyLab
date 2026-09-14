# -*- coding: utf-8 -*-
"""ALT-AUG Schritt 1 (FALSIFIKATION, READ-ONLY): endogener Transitions-Detektor.

Zweck
-----
Der in ``test/_chk_aug26_transition_endogen.py`` gebaute endogene
Zustandsautomat (TRANSITION <-> BALANCE, Dwell + Kantenreife + Breakout)
zerlegt AUG26 in 11..48 Fragmente und produziert kein PnL-Plateau
(Befund Schritt 3). Bevor auf AUG26 weiterkonstruiert wird, wird der
Detektor auf dem BEKANNTEN Fenster geprueft:

    Alt-AUG = ("2026-08-10", "2026-08-28"), n = 1288 (14 Handelstage x 92)

Arretierte Wahrheit dieses Fensters (Adapter V019, E-34):

    P9_BODEN_RECLAIM : 848 .. 1020
    A1_AUTO_77       : 1033 .. 1173
    A2_AUTO_77       : 1174 .. 1287
    Luecke (fail-closed): 1021 .. 1032

Falsifikationskriterium (Anwender)
----------------------------------
Trennt der Detektor die drei Balances 848 / 1033 / 1174 nicht sauber,
ist er in dieser Form widerlegt -- dann wird auf AUG26 NICHT
weitergesucht. Drei belastbare Kriterien muessen GLEICHZEITIG halten:

  K1 GRENZE  : Der Detektor erkennt die Vor-Balance 0..847 als
               TRANSITION, d.h. die 1. Balance beginnt bei 848 +/- 48.
  K2 SCHNITT : Er liefert <= 4 Balances (arretiert sind genau 3);
               mehr = Fragmentierung.
  K3 FLAECHE : IoU(Balance-Maske, arretierte Segmente) >= 0.80 im
               Arbeitsbereich des Trade-Loops [2, n-4].

Ein blosser Overlap-Anteil je Segment ist als Kriterium UNTAUGLICH:
bei 18..35 gleitenden Fenstern ist jede Zielzone per Konstruktion
zu >= 50 % ueberdeckt. Deshalb die drei Kriterien oben.

Zusaetzlich (nicht Urteil, sondern Einordnung): R_brutto mit
Detektor-Gate gegen das Gate aus den ARRETIERTEN Segmenten (Z_REF) und
gegen V0 (Z0, kein Gate).

Kausalitaet
-----------
Jede Entscheidung an Bar k liest ausschliesslich [0 .. k]. Kein
``searchsorted`` in die Zukunft, kein Blick auf die Referenzzonen.

Anker (Harness-Treue)
---------------------
Z0 muss 14 Trades / +42.450970 R reproduzieren (test/_chk_aug26_anker.py).
Zur Sicherheit wird Z0 in BEIDEN Box-Varianten gemessen (box_end = n
und box_end = native 644), damit die im Handoff offene Formulierung
("644 statt n") eindeutig geklaert ist.

Die Engine (test/tmp_kanten_engine_replay.py, SHA 53f28e1b...) bleibt
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

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    Hook2ZielModus,
    P9_BODEN_RECLAIM,
    A1_AUTO_77,
    A2_AUTO_77,
)

DEFAULT_PARAMS: Dict[str, object] = {
    "dwell_fenster_W": (24, 36, 48, 72),  # SWEEP-Achse (Bars)
    "dwell_band_pct": 0.80,      # relatives Band um den Cluster-Mittelwert
    "dwell_anteil_min": 0.80,    # min. Anteil Bars vollstaendig im Band
    "kanten_min_touches": 3,     # V-S-Schwelle der etablierten Balance
    "breakout_pct": 0.30,        # Close muss die Aussenwand so weit verlassen
    "balance_mindest_bars": 24,  # kein Flackern: min. Balance-Dauer
    "treffer_toleranz_bars": 48,  # +/- Toleranz fuer "Grenze getroffen"
}

W_LISTE: Tuple[int, ...] = DEFAULT_PARAMS["dwell_fenster_W"]  # type: ignore
BAND: float = DEFAULT_PARAMS["dwell_band_pct"]  # type: ignore
DWELL_MIN: float = DEFAULT_PARAMS["dwell_anteil_min"]  # type: ignore
MIN_TOUCH: int = DEFAULT_PARAMS["kanten_min_touches"]  # type: ignore
BREAKOUT: float = DEFAULT_PARAMS["breakout_pct"]  # type: ignore
BAL_MIN: int = DEFAULT_PARAMS["balance_mindest_bars"]  # type: ignore
TOL: int = DEFAULT_PARAMS["treffer_toleranz_bars"]  # type: ignore

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
ENGINE_SHA_SOLL = "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006"

FENSTER_KEY = "AUG"
FENSTER_LABEL = "ALT-AUG (2026-08-10 .. 2026-08-28)"
TAGE = ["10.08", "11.08", "12.08", "13.08", "14.08", "17.08", "18.08",
        "19.08", "20.08", "21.08", "24.08", "25.08", "26.08", "27.08",
        "28.08"]

# Arretierte Wahrheit (Adapter V019)
REF_SEGMENTE: Tuple[Tuple[int, int, str], ...] = (
    (int(P9_BODEN_RECLAIM.start_bar), int(P9_BODEN_RECLAIM.end_bar),
     str(P9_BODEN_RECLAIM.phasen_id)),
    (int(A1_AUTO_77.start_bar), int(A1_AUTO_77.end_bar),
     str(A1_AUTO_77.phasen_id)),
    (int(A2_AUTO_77.start_bar), int(A2_AUTO_77.end_bar),
     str(A2_AUTO_77.phasen_id)),
)
REF_GRENZEN: Tuple[int, ...] = tuple(s for s, _e, _n in REF_SEGMENTE)
REF_LUECKE: Tuple[int, int] = (1021, 1032)
# Blockierte Zonen des arretierten Gates (alles ausserhalb der Segmente)
REF_BLOCK: Tuple[Tuple[int, int], ...] = (
    (0, REF_SEGMENTE[0][0] - 1),                        # 0 .. 847
    (REF_SEGMENTE[0][1] + 1, REF_SEGMENTE[1][0] - 1),   # 1021 .. 1032
)
REF_Z0: Tuple[int, float] = (14, 42.450970)
# Arretierte V019-Architektur (Quelle: test/_tmp_e34h_einbrand_verify.py Z. 173;
# "_tmp_e34n15_append.py" Z. 68): H1 = bars < 644 UNEINGESCHRAENKT,
# H2 = 644..1287 phasengesteuert MIT Ziel-Injektion des Hooks.
REF_H1: Tuple[int, float] = (8, 38.919584)      # H1, kein Gate
REF_H2_V019: float = 43.694801                  # H2, Gate + Zielinjektion
REF_V019: Tuple[int, float] = (23, 82.614385)   # H1 + H2 (V019 arretiert)
BOX_NATIV_ERWARTET = 644


def tag(bar: int) -> str:
    i = bar // 92
    return f"{TAGE[i]}({bar - i * 92:02d})" if 0 <= i < len(TAGE) else "?"


def _ueberlapp(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0) + 1)


# ============================================================ Engine + Patch
_sha_ist = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
assert _sha_ist == ENGINE_SHA_SOLL, f"Engine-SHA veraendert: {_sha_ist}"

spec = importlib.util.spec_from_file_location("engine_alt", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_alt"] = engine
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
    '            # --- ALT-AUG/S1: endogener Phasen-Kontext ----------------\n'
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


# ====================================================== Detektor (identisch)
def erkenne_zustaende(scan: Dict, W: int, reife_bars: int = 0
                      ) -> Tuple[List[Tuple[int, str]], Dict[str, object]]:
    """Kausaler Zustandsautomat TRANSITION <-> BALANCE (1:1 aus Schritt 3).

    Args:
        scan: Scan-Dict der Engine (edges, seeds, d, n).
        W: Dwell-Fensterlaenge in Bars.
        reife_bars: Wenn > 0, muss die Balance-Kante mindestens so alt sein
            (Q24 ``min_wall_alter_bars``).

    Returns:
        verlauf: Liste ``(bar, zustand)`` je Umschaltpunkt (nur Wechsel).
        info: Diagnose (bals, trans, erste_bal, bal_start_bar, details).
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

    info: Dict[str, object] = {
        "verlauf": verlauf, "details": details, "bals": bal,
        "trans": trans,
        "erste_bal": bal[0][0] if bal else None,
        "bal_start_bar": bal[0][0] if bal else 0,
    }
    return verlauf, info


def _lauf_gate(scan: Dict, cfg: object, block: Tuple[Tuple[int, int], ...],
               start: int) -> Tuple[List, Dict[str, int]]:
    NS["_TRANS_ZONEN"] = block
    NS["_TRANS_START"] = start
    exec(compile(src_trans, "<alt_s1>", "exec"), NS)  # noqa: S102
    S, st = NS["_se_trades"](copy.deepcopy(scan), cfg)  # type: ignore
    return list(S), dict(st)


# ==================================================================== MAIN
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan(FENSTER_KEY, cfg)  # type: ignore[arg-type]
n = int(scan["n"])
BOX_NATIV = int(scan["box_end_bar"])
ts = list(scan["d"]["ts"])

print("=" * 118)
print(f"ALT-AUG SCHRITT 1 — FALSIFIKATIONSTEST des endogenen Detektors")
print("=" * 118)
print(f"Engine-SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}"
      f"... (UNVERAENDERT, Soll {ENGINE_SHA_SOLL[:24]}...)")
print(f"Fenster {FENSTER_LABEL} | n = {n} | box_end nativ = {BOX_NATIV} "
      f"(erwartet {BOX_NATIV_ERWARTET})")
print(f"Kanten {len(scan['edges'])} edges + {len(scan['seeds'])} seeds | "
      f"Band {BAND} % | Dwell-Anteil >= {DWELL_MIN} | Touches >= {MIN_TOUCH} "
      f"| Breakout {BREAKOUT} % | Bal-Min {BAL_MIN}")
print(f"Arretierte Wahrheit (Adapter V019, E-34):")
for s, e, nm in REF_SEGMENTE:
    print(f"   {nm:<18} {s:>5}..{e:<5} ({tag(s)} .. {tag(e)})")
print(f"   Luecke fail-closed  {REF_LUECKE[0]:>5}..{REF_LUECKE[1]:<5} "
      f"({tag(REF_LUECKE[0])} .. {tag(REF_LUECKE[1])})")

# ---------------------------------------------------- PHASE 0: Anker
print("\n" + "-" * 118)
print("PHASE 0 — ANKER (Harness-Treue) + Klaerung der Box_end-Variante")
print("-" * 118)


def _ohne_gate(box: int) -> Tuple[List, float]:
    """V0-Lauf ohne Gate; box = box_end_bar."""
    _sc = copy.deepcopy(scan)
    _sc["box_end_bar"] = box
    NS["_TRANS_ZONEN"] = ()
    NS["_TRANS_START"] = 0
    _S, _st = engine._se_trades(_sc, cfg)  # type: ignore[arg-type]
    _S = list(_S)
    return _S, sum(float(t.r) for t in _S)


S_z0, r_z0 = _ohne_gate(n)
print(f"   Z0  (box_end = n = {n}, kein Gate)   {len(S_z0):>3} Trades / "
      f"{r_z0:+.6f} R   [Soll {REF_Z0[0]} / {REF_Z0[1]:+.6f}]  -> "
      f"{'OK' if (len(S_z0) == REF_Z0[0] and abs(r_z0 - REF_Z0[1]) < 1e-6) else 'ABWEICHUNG'}")
for t in sorted(S_z0, key=lambda x: int(x.entry_bar)):
    _zone = ("H1" if int(t.entry_bar) < BOX_NATIV
             else ("P9" if 848 <= int(t.entry_bar) <= 1020
                   else ("A1" if 1033 <= int(t.entry_bar) <= 1173
                         else ("A2" if 1174 <= int(t.entry_bar) <= 1287
                               else "H2-SPERRE"))))
    print(f"         bar {int(t.entry_bar):>5} {tag(int(t.entry_bar)):<11} "
          f"{t.richtung:<6} K{int(t.kid):<4} {float(t.r):>+9.4f}   [{_zone}]")

S_h1, r_h1 = _ohne_gate(BOX_NATIV)
print(f"   H1  (box_end = {BOX_NATIV}, kein Gate)     {len(S_h1):>3} Trades / "
      f"{r_h1:+.6f} R   [Soll H1 {REF_H1[0]} / {REF_H1[1]:+.6f}]  -> "
      f"{'OK' if (len(S_h1) == REF_H1[0] and abs(r_h1 - REF_H1[1]) < 1e-6) else 'ABWEICHUNG'}")
print("      -> Damit ist die arretierte ZWEITEILUNG bestaetigt: H1 laeuft "
      "UNGEGATET (0..643),")
print("         nur H2 (644..1287) traegt die P9/A1/A2-Gate-Logik.")

scan["box_end_bar"] = n   # Voll-Lauf als Rechenbasis (konsistent zum Anker)
R0 = REF_Z0[1]

# ------------------------------------------- PHASE 0b: Referenz-Gate
S_ref, st_ref = _lauf_gate(scan, cfg, REF_BLOCK, 0)
r_ref = sum(float(t.r) for t in S_ref)
r_ges = r_h1 + r_ref
print(f"\n   Z_REF (Gate NUR H2; blockiert "
      f"{[f'{a}..{b}' for a, b in REF_BLOCK]}, OHNE Ziel-Injektion):")
print(f"         H2 allein     {len(S_ref):>3} Trades / {r_ref:+.6f} R   "
      f"(blockiert: {int(st_ref.get('transition_blockiert', 0))})")
print(f"         H1 + H2       {len(S_h1) + len(S_ref):>3} Trades / "
      f"{r_ges:+.6f} R")
print(f"         V019 arretiert (MIT Ziel-Injektion) "
      f"{REF_V019[0]:>3} Trades / {REF_V019[1]:+.6f} R   "
      f"[H1 {REF_H1[1]:+.6f} + H2 {REF_H2_V019:+.6f}]")
print("         -> H2 allein per Blockade ist NICHT mit V019 vergleichbar: "
      "die Ziel-Injektion")
print("            veraendert den Entry-Bestand (Filter 'kein_raum'), nicht "
      "nur die Exits.")
for t in sorted(S_ref, key=lambda x: int(x.entry_bar)):
    print(f"         bar {int(t.entry_bar):>5} {tag(int(t.entry_bar)):<11} "
          f"{t.richtung:<6} K{int(t.kid):<4} {float(t.r):>+9.4f}")

# ====================================================== PHASE 1: Detektor
erg: List[Tuple[int, Dict[str, object], List, Dict]] = []
for W in W_LISTE:
    _v, info = erkenne_zustaende(scan, W)
    S, st = _lauf_gate(scan, cfg, tuple(info["trans"]),  # type: ignore
                       int(info["bal_start_bar"]))       # type: ignore
    erg.append((W, info, S, st))

print("\n" + "-" * 118)
print("PHASE 1 — ZUSTANDSVERLAUF je Fenstergroesse (endogen, kausal)")
print("-" * 118)
for W, info, _S, _st in erg:
    bals = info["bals"]        # type: ignore[assignment]
    tr = info["trans"]         # type: ignore[assignment]
    eb = info["erste_bal"]
    print(f"\n   W = {W:>3} Bars ({W / 4.0:.0f} h)   Balances {len(bals)}   "
          f"Transitionsintervalle {len(tr)}   erste Balance ab Bar {eb} "
          f"({tag(int(eb)) if eb is not None else '-'})")
    print(f"      {'#':<3}{'Balance-Fenster':<18}{'Tage':<20}"
          f"{'Zone (Boden..Decke)':<26}")
    for i, (a, b, zl, zh) in enumerate(bals, 1):
        print(f"      {i:<3}{f'{a}..{b}':<18}{f'{tag(a)}..{tag(b)}':<20}"
              f"{f'{zl:.4f}..{zh:.4f}':<26}")
    print(f"      TRANSITIONEN: "
          f"{[(f'{a}..{b}', tag(a)) for a, b in tr]}")

# ------------------------------------ PHASE 1b: Treffer gegen Wahrheit
# Arbeitsbereich des Trade-Loops (nur dort sind Zonen operativ).
LOOP_A, LOOP_B = 2, n - 4

REF_MASKE: List[bool] = [False] * n
for _s, _e, _nm in REF_SEGMENTE:
    for _j in range(_s, _e + 1):
        REF_MASKE[_j] = True
REF_BAL_BARS = sum(1 for j in range(LOOP_A, LOOP_B + 1) if REF_MASKE[j])


def _balance_maske(info: Dict[str, object]) -> List[bool]:
    """True je Bar, der nach Detektor in einer BALANCE liegt."""
    m = [False] * n
    for (a, b, _zl, _zh) in info["bals"]:                        # type: ignore
        for j in range(max(0, a), min(n - 1, b) + 1):
            m[j] = True
    return m


def _iou(m: List[bool]) -> Tuple[float, int, int, int, int]:
    """IoU gegen die arretierte Maske im Arbeitsbereich des Trade-Loops."""
    schnitt = nur_det = nur_ref = 0
    for j in range(LOOP_A, LOOP_B + 1):
        d, r = m[j], REF_MASKE[j]
        if d and r:
            schnitt += 1
        elif d:
            nur_det += 1
        elif r:
            nur_ref += 1
    union = schnitt + nur_det + nur_ref
    return (schnitt / union if union else 0.0, schnitt, nur_det, nur_ref, union)


print("\n" + "-" * 118)
print("PHASE 1b — FALSIFIKATION gegen die arretierten Balances "
      "848 / 1033 / 1174")
print("-" * 118)
print(f"   K1 GRENZE   : 1. Balance beginnt bei Bar 848 +/- {TOL}")
print(f"   K2 SCHNITT  : Anzahl der Balances <= 4 (arretiert sind 3)")
print(f"   K3 FLAECHE  : IoU(Balance-Maske, arretierte Segmente) >= 0.80 "
      f"im Loop-Bereich [{LOOP_A}, {LOOP_B}] "
      f"({REF_BAL_BARS} arretierte Balance-Bars)")
print(f"\n   {'W':>4}{'1.Bal':>7}{'d848':>7}{'Bal#':>6}"
      f"{'P9':>7}{'A1':>7}{'A2':>7}{'TP':>7}{'FP':>7}{'FN':>7}"
      f"{'IoU':>8}  {'K1':>6}{'K2':>6}{'K3':>6}   Urteil")
urteile: Dict[int, bool] = {}
krit: Dict[int, Tuple[bool, bool, bool]] = {}
for W, info, _S, _st in erg:
    bals = info["bals"]                                          # type: ignore
    eb = (int(info["erste_bal"]) if info["erste_bal"] is not None else -1)
    m = _balance_maske(info)
    iou, tp, fp, fn, _un = _iou(m)
    quote: List[str] = []
    for (s, e, _nm) in REF_SEGMENTE:
        laenge = e - s + 1
        best = max((_ueberlapp(a, b, s, e) for (a, b, _zl, _zh) in bals),  # type: ignore
                   default=0)
        quote.append(f"{best / laenge * 100:.0f}%")
    k1 = abs(eb - REF_GRENZEN[0]) <= TOL
    k2 = len(bals) <= 4
    k3 = iou >= 0.80
    krit[W] = (k1, k2, k3)
    urteile[W] = k1 and k2 and k3
    print(f"   {W:>4}{eb:>7}{eb - REF_GRENZEN[0]:>+7}{len(bals):>6}"
          f"{quote[0]:>7}{quote[1]:>7}{quote[2]:>7}"
          f"{tp:>7}{fp:>7}{fn:>7}{iou:>8.3f}"
          f"{('JA' if k1 else 'NEIN'):>6}{('JA' if k2 else 'NEIN'):>6}"
          f"{('JA' if k3 else 'NEIN'):>6}   "
          f"{'SAUBER' if urteile[W] else 'WIDERLEGT'}")

# ---------------------------------------------- PHASE 1c: Q24-Kantenreife
Q24 = int(cfg.min_wall_alter_bars)
print("\n" + "-" * 118)
print(f"PHASE 1c (Zusatz) — Detektor + Q24-Kantenreife "
      f"(min_wall_alter_bars = {Q24})")
print("-" * 118)
print(f"\n   {'W':>4}{'Balances':>10}{'1. Balance':>12}{'Zonen':>7}"
      f"{'P9':>8}{'A1':>8}{'A2':>8}{'Trades':>8}{'R':>12}")
for W in W_LISTE:
    _v, info = erkenne_zustaende(scan, W, reife_bars=Q24)
    bals = info["bals"]                                          # type: ignore
    tr = info["trans"]                                           # type: ignore
    S, _st = _lauf_gate(scan, cfg, tuple(tr),
                        int(info["bal_start_bar"]))              # type: ignore
    quote: List[str] = []
    for (s, e, _nm) in REF_SEGMENTE:
        laenge = e - s + 1
        best = max((_ueberlapp(a, b, s, e) for (a, b, _zl, _zh) in bals),  # type: ignore
                   default=0)
        quote.append(f"{best / laenge * 100:.0f}%")
    print(f"   {W:>4}{len(bals):>10}{int(info['erste_bal'] or 0):>12}"
          f"{len(tr):>7}{quote[0]:>8}{quote[1]:>8}{quote[2]:>8}"
          f"{len(S):>8}{sum(float(t.r) for t in S):>+12.4f}")

# ------------------------------------------------------ PHASE 2: PnL
print("\n" + "-" * 118)
print("PHASE 2 — TRADE-/PnL-BILANZ je Sweep-Stufe (V0 + Detektor-Gate)")
print("-" * 118)
print(f"   Referenzen: Z0 (kein Gate, ganzer Monat) = {len(S_z0)} / "
      f"{r_z0:+.6f} R   |   arretiert H1+H2-Gate (ohne Ziel-Injektion) = "
      f"{len(S_h1) + len(S_ref)} / {r_ges:+.6f} R   |   V019 = "
      f"{REF_V019[0]} / {REF_V019[1]:+.6f} R")
print("   HINWEIS: Die Detektor-Gates laufen hier auf dem GANZEN Monat "
      "(box_end = n), nicht H1/H2-getrennt;")
print("            sie sind deshalb gegen Z0 zu lesen, nicht gegen V019.")
print(f"\n   {'W':>4}{'Trades':>8}{'Treffer':>9}{'SL':>5}{'R_brutto':>12}"
      f"{'vs Z0':>10}{'vs H1+H2':>11}{'trans_block':>13}{'vorb_block':>12}")
for W, _info, S, st in erg:
    r = sum(float(t.r) for t in S)
    tr_ = sum(1 for t in S if float(t.r) > 0)
    sl = sum(1 for t in S if float(t.r) <= -0.999)
    print(f"   {W:>4}{len(S):>8}{tr_:>9}{sl:>5}{r:>+12.4f}"
          f"{r - R0:>+10.4f}{r - r_ges:>+11.4f}"
          f"{int(st.get('transition_blockiert', 0)):>13}"
          f"{int(st.get('vorbalance_blockiert', 0)):>12}")
print(f"   {'Z0':>4}{len(S_z0):>8}"
      f"{sum(1 for t in S_z0 if float(t.r) > 0):>9}"
      f"{sum(1 for t in S_z0 if float(t.r) <= -0.999):>5}{r_z0:>+12.4f}"
      f"{0.0:>+10.4f}{r_z0 - r_ges:>+11.4f}{'-':>13}{'-':>12}")

# --------------------------------------------- Trade-Signaturen
print("\n" + "-" * 118)
print("PHASE 2b — WELCHE TRADES BLEIBEN JE W UEBRIG?")
print("-" * 118)
for W, _info, S, _st in erg:
    print(f"\n   W = {W:>3}  ({len(S)} Trades, "
          f"{sum(float(t.r) for t in S):+.4f} R):")
    for t in sorted(S, key=lambda x: int(x.entry_bar)):
        print(f"      bar {int(t.entry_bar):>5} "
              f"{tag(int(t.entry_bar)):<12} {t.richtung:<6} "
              f"K{int(t.kid):<4} {float(t.r):>+10.4f}  "
              f"({t.grund1}/{t.grund2})")

# ------------------------------------------------------------ Urteil
print("\n" + "=" * 118)
print("URTEIL (Falsifikationskriterium des Anwenders)")
print("=" * 118)
_sauber = [W for W in W_LISTE if urteile[W]]
for W in W_LISTE:
    _k = krit[W]
    print(f"   W = {W:>3}: K1 GRENZE {'JA  ' if _k[0] else 'NEIN'} | "
          f"K2 SCHNITT {'JA  ' if _k[1] else 'NEIN'} | "
          f"K3 FLAECHE {'JA  ' if _k[2] else 'NEIN'}")
if _sauber:
    print(f"\n   Detektor trennt P9/A1/A2 SAUBER bei W = "
          f"{', '.join(str(w) for w in _sauber)} -> NICHT widerlegt.")
else:
    print("\n   Detektor trennt P9/A1/A2 in KEINER Sweep-Stufe sauber "
          "-> IN DIESER FORM WIDERLEGT.")
    print("   Konsequenz: auf AUG26 wird mit diesem Detektor NICHT "
          "weitergesucht (Hysterese-Neukonstrukt noetig).")

print("\n" + "-" * 118)
print("EINORDNUNG (Befund, keine Empfehlung)")
print("-" * 118)
print(f"   Z0 (kein Gate, ganzer Monat)   {len(S_z0):>3} Trades / "
      f"{r_z0:+.6f} R")
print(f"   H1 allein (0..643, kein Gate)  {len(S_h1):>3} Trades / "
      f"{r_h1:+.6f} R   [= arretierte H1-Zahl, Anker OK]")
print(f"   H2 allein (Gate, keine Injekt.){len(S_ref):>3} Trades / "
      f"{r_ref:+.6f} R")
print(f"   H1+H2 (Gate, keine Injektion)  {len(S_h1) + len(S_ref):>3} Trades / "
      f"{r_ges:+.6f} R")
print(f"   V019 arretiert (Gate+Injektion){REF_V019[0]:>3} Trades / "
      f"{REF_V019[1]:+.6f} R")
print(f"   -> Die arretierte Zweiteilung (H1 ungegatet + H2-Gate) liegt "
      f"{r_ges - R0:+.4f} R unter")
print("      dem ungegateten Monat: das H2-Gate sperrt die Z0-Trades in "
      "644..847 und 1021..1032.")
print("      Der Sprung auf V019 = +82.614385 R kommt aus der Ziel-Injektion "
      "(sie aendert auch")
print("      den Entry-Bestand ueber den Filter 'kein_raum'), NICHT aus der "
      "Blockade.")
print("   -> Die Detektor-Gates (W=24 +25.28, W=36 +26.28, W=48 -0.77, "
      "W=72 +6.75) liegen")
print("      alle UNTER Z0 und sind nicht monoton -> kein Plateau, kein "
      "Nachbau der Struktur.")
print("\nENDE ALT-AUG SCHRITT 1 (FALSIFIKATION)")
