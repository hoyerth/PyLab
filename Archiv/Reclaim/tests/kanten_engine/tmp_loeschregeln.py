# -*- coding: utf-8 -*-
"""READ-ONLY: Loeschregeln fuer Zwischenkanten (AUG komplett).

Simuliert das NICHT-ERZEUGEN einer Kante zum Geburtszeitpunkt (deletion at
birth) in einer in-memory gepatchten Modulkopie. Die Engine-Datei bleibt
unveraendert. Geprueft wird: identische Trades? neue Kanten (Folgekanten)?
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"
L: List[str] = []


def out(s: str = "") -> None:
    L.append(s)


def load(name: str, src: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(P)
    sys.modules[name] = mod
    exec(compile(src, str(P), "exec"), mod.__dict__)
    return mod


with open(P, encoding="utf-8", newline="") as f:
    SRC = f.read()
assert SRC.count("\r\n") == SRC.count("\n")

# ---------------------------------------------------------------------------
# A) Instrumentierung der Nutzungspfade (kausal, exakt)
# ---------------------------------------------------------------------------
A1 = "    def _kandidat(richtung: SignalRichtung, k: int,"
assert SRC.count(A1) == 1
I1 = SRC.replace(A1, "    def _kandidat_orig(richtung: SignalRichtung, k: int,", 1)
A2 = "    def _gegenkante(richtung: SignalRichtung, k: int) -> Optional[_SEEdgeH]:"
assert I1.count(A2) == 1
WRAP = (
    "    def _kandidat(richtung: SignalRichtung, k: int,\r\n"
    "                  sweep_px: float) -> Optional[_SEEdgeH]:\r\n"
    "        _r = _kandidat_orig(richtung, k, sweep_px)\r\n"
    "        if _r is not None:\r\n"
    "            KAND_LOG.append((k, richtung, _r.kid))\r\n"
    "        return _r\r\n"
    "\r\n"
    "    def _gegenkante(richtung: SignalRichtung, k: int"
    ") -> Optional[_SEEdgeH]:\r\n"
    "        _r = _gegenkante_orig(richtung, k)\r\n"
    "        if _r is not None:\r\n"
    "            GEGEN_LOG.append((k, richtung, _r.kid))\r\n"
    "        return _r\r\n"
    "\r\n")
I1 = I1.replace(A2, WRAP + A2.replace("    def _gegenkante",
                                     "    def _gegenkante_orig"), 1)
A3 = "    def _blockiert_durch_aussenkante(richtung: SignalRichtung, k: int,"
assert I1.count(A3) == 1
I1 = I1.replace(A3, "    def _blockiert_durch_aussenkante_orig("
                    "richtung: SignalRichtung, k: int,", 1)
A4 = "    def _etabliert(e: _SEEdgeH, k: int) -> bool:"
assert I1.count(A4) == 1
I1 = I1.replace(
    A4,
    "    def _blockiert_durch_aussenkante(richtung: SignalRichtung, k: int,\r\n"
    "                                     kd: _SEEdgeH,\r\n"
    "                                     sweep_px: float"
    ") -> Optional[_SEEdgeH]:\r\n"
    "        _r = _blockiert_durch_aussenkante_orig(richtung, k, kd, sweep_px)\r\n"
    "        if _r is not None:\r\n"
    "            BLK_LOG.append((k, richtung, kd.kid, _r.kid))\r\n"
    "        return _r\r\n"
    "\r\n" + A4, 1)
I1 = I1.replace("MAX_SIGNAL_ZEILEN: int = 60",
                "MAX_SIGNAL_ZEILEN: int = 60\r\n"
                "KAND_LOG: List[Tuple] = []\r\n"
                "GEGEN_LOG: List[Tuple] = []\r\n"
                "BLK_LOG: List[Tuple] = []", 1)

# ---------------------------------------------------------------------------
# B) deletion-at-birth: BLACKLIST (seite, pivot_bar, px_rund)
# ---------------------------------------------------------------------------
A5 = ("                    e = _SEEdgeH(kid=kid_next, seite=seite, basis=px,"
      "\r\n"
      "                                 geburts_bar=mbar, erster_pivot_bar=mbar)"
      "\r\n")
assert SRC.count(A5) == 1
GUARD = ("                    if (seite, mbar, round(px, 3)) in BLACKLIST:"
         "\r\n"
         "                        continue\r\n")
I2 = SRC.replace(A5, GUARD + A5, 1)
I2 = I2.replace("MAX_SIGNAL_ZEILEN: int = 60",
                "MAX_SIGNAL_ZEILEN: int = 60\r\nBLACKLIST: set = set()", 1)

base = load("ke_base", SRC)
inst = load("ke_inst", I1)
sim = load("ke_sim", I2)

cfg = base.StraightEdgeHarnessKonfiguration()

# --- Original-Scan + Instrumentierung (volles Fenster) ----------------------
scan = inst._se_scan("AUG", cfg)
n = len(scan["d"])
scan["box_end_bar"] = n
trades, stats = inst._se_trades(scan, cfg)
kand_kids = {k for _, _, k in inst.KAND_LOG}
gegen_kids = {k for _, _, k in inst.GEGEN_LOG}
blk_kids = {b for _, _, _, b in inst.BLK_LOG}
entry_kids = {t.kid for t in trades}
alle = list(scan["edges"]) + list(scan["seeds"])
edges = scan["edges"]
seeds = scan["seeds"]
ergebnis_kids = sorted(entry_kids)

# --- Aeusserste-Kante-Zeitreihe (O1/O2/O3) ---------------------------------
def existiert(e, k: int) -> bool:
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


def pool_gegen(e, k: int) -> bool:
    return (e.erster_pivot_bar + 2 <= k + 1
            and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                 or e.touch_conf(k) >= 2))


def pool_kand(e, k: int) -> bool:
    if not existiert(e, k):
        return False
    if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
            or e.touch_conf(k) >= 2):
        return False
    return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars


outer: Dict[str, Dict[int, set]] = {"O1": {}, "O2": {}, "O3": {}}
for k in range(n):
    for tag, fn in (("O1", existiert), ("O2", pool_gegen), ("O3", pool_kand)):
        for seite, rev in (("OBEN", True), ("UNTEN", False)):
            cand = [e for e in alle if e.seite == seite and fn(e, k)]
            if cand:
                best = (max if rev else min)(cand, key=lambda e: e.basis_bei(k))
                outer[tag].setdefault(k, set()).add(best.kid)


def ist_outer(kid: int) -> bool:
    return any(kid in outer[t].get(b, ()) for t in outer for b in outer[t])


nie_outer = [e for e in alle if not ist_outer(e.kid)]
nie_outer_ung = [e for e in nie_outer
                 if e.kid not in entry_kids
                 and e.kid not in blk_kids
                 and e.kid not in kand_kids
                 and e.kid not in gegen_kids]


# --- Simulation -------------------------------------------------------------
def sim_loeschen(setups_black: List, label: str) -> Tuple[bool, int, int, Set]:
    """Loescht die Kanten zum Geburtszeitpunkt; vergleicht mit Original."""
    sim.BLACKLIST = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
                     for e in setups_black}
    sc = sim._se_scan("AUG", cfg)
    sc["box_end_bar"] = n
    tr, st = sim._se_trades(sc, cfg)
    neu_alle = list(sc["edges"]) + list(sc["seeds"])
    orig_sig = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3)) for e in alle}
    neu_sig = {(e.seite, e.wicks[0][0], round(e.wicks[0][1], 3))
               for e in neu_alle}
    folge = neu_sig - orig_sig
    orig_tr = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in trades]
    neu_tr = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr]
    ident = neu_tr == orig_tr
    out("")
    out("-" * 118)
    out(f"SIMULATION {label}: {len(setups_black)} Kanten geloescht")
    out("-" * 118)
    out(f"  Kanten danach : {len(neu_alle)} (orig {len(alle)}) | "
        f"edges {len(sc['edges'])} seeds {len(sc['seeds'])}")
    out(f"  Trades        : {len(tr)} (orig {len(trades)}) | "
        f"Netto-R {sum(t.r for t in tr):+.2f} (orig "
        f"{sum(t.r for t in trades):+.2f})")
    out(f"  Trade-Signatur (bar/richt/entry/R) : "
        f"{'IDENTISCH' if ident else 'ABWEICHEND'}")
    if not ident:
        for a, b in zip(orig_tr, neu_tr):
            mark = "" if a == b else "   <<<"
            out(f"      orig {a}  vs  sim {b}{mark}")
    out(f"  FOLGEKANTEN (neue Geburten)  : {len(folge)}")
    for s in sorted(folge, key=lambda x: (x[1], x[2])):
        out(f"      neu: {s[0]:5s} pivot_bar={s[1]:4d} px={s[2]:.3f}")
    out(f"  Trades im Sim-Lauf: {[(t.bar, t.richtung, t.entry_bar) for t in tr]}")
    return ident, len(tr), len(folge), set()


out("#" * 118)
out("# LOESCHREGELN FUER ZWISCHENKANTEN (READ-ONLY) -- AUG komplett")
out(f"# n={n} | Kanten(edges+seeds)={len(alle)} | edges={len(edges)} "
    f"seeds={len(seeds)} | Trades={len(trades)} / "
    f"{sum(t.r for t in trades):+.2f} R")
out("#" * 118)
out("")
out("=" * 118)
out("1. NUTZUNGSKATEGORIEN (exakt instrumentiert, volles Fenster)")
out("=" * 118)
out(f"  Trades (Entry-Kanten)        : {sorted(entry_kids)}")
out(f"  _kandidat-Rueckgaben         : {sorted(kand_kids)}")
out(f"  _blockiert_durch_aussenkante : {sorted(blk_kids)}")
out(f"  _gegenkante-Rueckgaben       : {sorted(gegen_kids)}")
out(f"  Nie aeusserste Kante (O1/O2/O3): {len(nie_outer)} von {len(alle)}")
out(f"  Nie outer UND nie genutzt     : {len(nie_outer_ung)} von {len(alle)}")

# --- Regel-Kandidaten -------------------------------------------------------
R1 = nie_outer_ung
R2 = nie_outer
R3 = [e for e in alle if e.kid not in kand_kids]
R4 = [e for e in alle if e.kid not in kand_kids and e.kid not in gegen_kids
      and e.kid not in blk_kids]
R5 = [e for e in alle if e.touch_anzahl <= 1 and e.kid not in entry_kids]
R6 = [e for e in alle if e.kid not in kand_kids and e.kid not in gegen_kids]

out("")
out("=" * 118)
out("2. REGEL-KANDIDATEN (Umfang)")
out("=" * 118)
for nm, r, txt in (("R1", R1, "nie outer UND nie genutzt"),
                   ("R2", R2, "nie outer (jede Semantik)"),
                   ("R3", R3, "nie von _kandidat zurueckgegeben"),
                   ("R4", R4, "nie kandidat/gegenkante/blocker"),
                   ("R5", R5, "<= 1 Touch und kein Entry"),
                   ("R6", R6, "nie kandidat UND nie gegenkante")):
    out(f"  {nm}: {len(r):3d} Kanten  ({len(r) / len(alle) * 100:5.1f} %)  {txt}")

out("")
out("=" * 118)
out("3. SIMULATION (deletion at birth, in-memory)")
out("=" * 118)
for nm, r in (("R1", R1), ("R2", R2), ("R3", R3), ("R4", R4),
              ("R5", R5), ("R6", R6)):
    sim_loeschen(r, f"{nm} ({len(r)} Kanten)")

# ---------------------------------------------------------------------------
# R7: STRUKTURELLE REGEL -- nur Aussenkanten materialisieren
# Beim Cluster-Zuordnungs-Versuch (cand nicht leer) wird die Kante NICHT
# erzeugt, wenn sie nicht die aeusserste lebende Linie ihrer Seite waere.
# ---------------------------------------------------------------------------
A6 = ("                if cand:\r\n"
      "                    best = max(\r\n")
assert SRC.count(A6) == 1, SRC.count(A6)
R7_GUARD = (
    "                if cand:\r\n"
    "                    if not any(c.ist_prim_anker for c in cand):\r\n"
    "                        _lb = [r for r in cluster[seite]\r\n"
    "                               if _lebt(r, mbar)]\r\n"
    "                        if _lb:\r\n"
    "                            if seite == \"OBEN\":\r\n"
    "                                _au = max(r.basis for r in _lb)\r\n"
    "                                _aeuss_ok = px >= _au\r\n"
    "                            else:\r\n"
    "                                _au = min(r.basis for r in _lb)\r\n"
    "                                _aeuss_ok = px <= _au\r\n"
    "                            if not _aeuss_ok:\r\n"
    "                                R7_LOG.append((mbar, seite, px))\r\n"
    "                                continue\r\n"
)
I3 = SRC.replace(A6, R7_GUARD + A6, 1)
assert I3 != SRC
I3 = I3.replace("MAX_SIGNAL_ZEILEN: int = 60",
                "MAX_SIGNAL_ZEILEN: int = 60\r\nR7_LOG: List[Tuple] = []", 1)
# _lebt wird in _se_scan erst spaeter definiert -> Hilfsfunktion nachziehen.
A7 = "    def _ist_im_band(px: float, basis: float) -> bool:"
assert I3.count(A7) == 1
I3 = I3.replace(
    A7,
    "    def _lebt(e: _SEEdgeH, k: int) -> bool:\r\n"
    "        _b = [b for b, _ in e.wicks if b <= k]\r\n"
    "        return bool(_b) and max(_b) >= k - cfg.wall_live_bars\r\n"
    "\r\n" + A7, 1)
r7 = load("ke_r7", I3)
out("")
out("=" * 118)
out("4. R7 -- STRUKTURELLE REGEL: nur Aussenkanten materialisieren")
out("=" * 118)
sc7 = r7._se_scan("AUG", cfg)
sc7["box_end_bar"] = n
tr7, st7 = r7._se_trades(sc7, cfg)
alle7 = list(sc7["edges"]) + list(sc7["seeds"])
orig_tr = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in trades]
neu_tr7 = [(t.bar, t.richtung, t.entry_bar, round(t.r, 4)) for t in tr7]
out(f"  unterdrueckte Geburten (R7_LOG): {len(r7.R7_LOG)}")
out(f"  Kanten: {len(alle7)} (orig {len(alle)}) | edges {len(sc7['edges'])} "
    f"seeds {len(sc7['seeds'])}")
out(f"  Trades: {len(tr7)} (orig {len(trades)}) | Netto-R "
    f"{sum(t.r for t in tr7):+.2f} (orig {sum(t.r for t in trades):+.2f})")
out(f"  Trade-Signatur: {'IDENTISCH' if neu_tr7 == orig_tr else 'ABWEICHEND'}")
for a, b in zip(orig_tr, neu_tr7):
    out(f"      orig {a}  vs  R7 {b}{'' if a == b else '   <<<'}")
if len(orig_tr) != len(neu_tr7):
    out(f"      orig {len(orig_tr)} vs R7 {len(neu_tr7)} Trades")
out(f"  Trades R7: {[(t.bar, t.richtung, t.entry_bar, t.kid) for t in tr7]}")

txt = "\n".join(L)
print(txt)
with open(ROOT / "test" / "tmp_loeschregeln.txt", "w", encoding="utf-8") as f:
    f.write(txt + "\n")
