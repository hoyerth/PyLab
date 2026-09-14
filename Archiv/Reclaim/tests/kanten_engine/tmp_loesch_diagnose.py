# -*- coding: utf-8 -*-
"""READ-ONLY: Diskriminator-Tabelle der R18-Loeschungen -- AUG komplett.

Warum sind genau K1/K31/K51/K54 schaedlich und die uebrigen 36 harmlos?
Fuer jede geloeschte Kante werden alle kausalen und ex-post Merkmale
gegenuebergestellt (Dormanz, Reaktivierung, Aussenrolle, Promotion,
Nutzungspfade).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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

# --- Instrumentierung der Nutzungspfade (wie tmp_loeschregeln.py) ----------
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

# --- R18-Pruning (in-memory) fuer die Loeschzeitpunkte ---------------------
A = ("                if aussen and e.status == \"AKTIV\":\r\n"
     "                    e.status = \"SCHLAFEND\"\r\n"
     "                    e.schlaf_windows.append((k, None))\r\n")
assert SRC.count(A) == 1
PRUNE = (
    A + "\r\n"
    "        if RULE_MODE == \"R18\":\r\n"
    "            for _seite in (\"OBEN\", \"UNTEN\"):\r\n"
    "                _keep = []\r\n"
    "                for _e in cluster[_seite]:\r\n"
    "                    _alt = k - _e.erster_pivot_bar\r\n"
    "                    _loeschen = False\r\n"
    "                    if (_alt >= cfg.wall_live_bars\r\n"
    "                            and not _e.ist_prim_anker):\r\n"
    "                        _n = _e.touch_conf(k)\r\n"
    "                        _lb = [r for r in cluster[_seite]\r\n"
    "                               if _lebt_scan(r, k)]\r\n"
    "                        _ist_aussen = True\r\n"
    "                        if _lb:\r\n"
    "                            if _seite == \"OBEN\":\r\n"
    "                                _ist_aussen = _e.basis >= max(\r\n"
    "                                    r.basis for r in _lb)\r\n"
    "                            else:\r\n"
    "                                _ist_aussen = _e.basis <= min(\r\n"
    "                                    r.basis for r in _lb)\r\n"
    "                        _geschuetzt = _e.kid in WAR_AUSSEN\r\n"
    "                        if _ist_aussen:\r\n"
    "                            WAR_AUSSEN.add(_e.kid)\r\n"
    "                        if _n < 2 and not _ist_aussen and not _geschuetzt:\r\n"
    "                            _letzter = max(b for b, _ in _e.wicks if b <= k)\r\n"
    "                            if k - _letzter >= 96:\r\n"
    "                                _loeschen = True\r\n"
    "                    if _loeschen:\r\n"
    "                        PRUNE_LOG.append((k, _e.kid, _e.seite,\r\n"
    "                                          round(_e.basis, 3), _alt))\r\n"
    "                    else:\r\n"
    "                        _keep.append(_e)\r\n"
    "                cluster[_seite] = _keep\r\n")
p18 = SRC.replace(A, PRUNE, 1)
p18 = p18.replace("MAX_SIGNAL_ZEILEN: int = 60",
                  "MAX_SIGNAL_ZEILEN: int = 60\r\n"
                  "RULE_MODE: str = \"\"\r\nPRUNE_LOG: List[Tuple] = []\r\n"
                  "WAR_AUSSEN: set = set()", 1)
A5 = "    for k in range(n):\r\n        mbar = k - 2\r\n"
assert p18.count(A5) == 1
p18 = p18.replace(
    A5,
    "    def _lebt_scan(e: _SEEdgeH, kk: int) -> bool:\r\n"
    "        _b = [b for b, _ in e.wicks if b <= kk]\r\n"
    "        return bool(_b) and max(_b) >= kk - cfg.wall_live_bars\r\n"
    "\r\n" + A5, 1)

base = load("ke_b", SRC)
inst = load("ke_i", I1)
m18 = load("ke_18", p18)
cfg = base.StraightEdgeHarnessKonfiguration()

scan0 = inst._se_scan("AUG", cfg)
n = len(scan0["d"])
scan0["box_end_bar"] = n
tr0, _ = inst._se_trades(scan0, cfg)
alle = list(scan0["edges"]) + list(scan0["seeds"])
kid2e = {e.kid: e for e in alle}
kand = {k for _, _, k in inst.KAND_LOG}
gegen = {k for _, _, k in inst.GEGEN_LOG}
blk = {b for _, _, _, b in inst.BLK_LOG}
entry = {t.kid for t in tr0}

# --- Aussenrolle (3 Semantiken) -------------------------------------------
def existiert(e, k: int) -> bool:
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


def pool_gegen(e, k: int) -> bool:
    return (e.erster_pivot_bar + 2 <= k + 1
            and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                 or e.touch_conf(k) >= 2))


def pool_kand(e, k: int) -> bool:
    return (existiert(e, k) and pool_gegen(e, k)
            and k - e.erster_pivot_bar >= cfg.min_wall_alter_bars)


aussen_kids: set = set()
for k in range(n):
    for fn in (existiert, pool_gegen, pool_kand):
        for seite, rev in (("OBEN", True), ("UNTEN", False)):
            cand = [e for e in alle if e.seite == seite and fn(e, k)]
            if cand:
                best = (max if rev else min)(cand, key=lambda e: e.basis_bei(k))
                aussen_kids.add(best.kid)

m18.RULE_MODE = "R18"
m18.PRUNE_LOG = []
m18.WAR_AUSSEN = set()
m18._se_scan("AUG", cfg)
del_bar = {p[1]: p[0] for p in m18.PRUNE_LOG}
del_alt = {p[1]: p[4] for p in m18.PRUNE_LOG}

harmlos = [7, 14, 18, 19, 22, 27, 28, 33, 36, 37, 38, 41, 43, 44, 46, 47, 49,
           50, 52, 55, 56, 60, 61, 65, 67, 68, 69, 70, 76, 77, 81, 82, 86]
schaedlich = [1, 31, 51, 54]

out("#" * 118)
out("# DISKRIMINATOR-TABELLE: R18-Loeschungen (READ-ONLY) -- AUG komplett")
out(f"# n={n} | Original {len(tr0)} Trades / {sum(t.r for t in tr0):+.2f} R")
out("#" * 118)
out("")
out("Spalten: K=kid, Seite, Pivot=erster_pivot_bar, Touch=Touch-Anzahl,")
out("  Del=Loeschbar, Dormanz=Del - letzter Touch, Reaktiv=Touches NACH Del,")
out("  Aussen=je aeusserste Linie (O1/O2/O3), Promo=Primaer-Anker,")
out("  K/G/B/E = je von _kandidat/_gegenkante/_blocker/Entry genutzt,")
out("  Harmlos = Einzel-Loeschung signaturneutral.")
out("")
hdr = (f"  {'K':>4} {'Seite':5s} {'Pivot':>5} {'Touch':>5} {'Del':>5} "
       f"{'Dorm':>5} {'Reakt':>5} {'Aussen':>6} {'Promo':>5} "
       f"{'K':>2}{'G':>2}{'B':>2}{'E':>2} {'Harmlos':>7}")
out(hdr)
out("  " + "-" * (len(hdr) - 2))
rows = []
for kid in sorted(set(harmlos) | set(schaedlich)):
    e = kid2e.get(kid)
    if e is None:
        continue
    dbar = del_bar.get(kid, -1)
    # Dormanz KAUSAL zum Loeschzeitpunkt (nur rohe Touches <= dbar)
    _roh = [b for b, _ in e.wicks if b <= dbar] if dbar >= 0 else []
    reakt = sum(1 for b, _ in e.wicks if b > dbar)
    rows.append((
        kid, e.seite, e.wicks[0][0], len(e.wicks), dbar,
        (dbar - max(_roh)) if _roh else -1, reakt,
        kid in aussen_kids, e.ist_prim_anker,
        kid in kand, kid in gegen, kid in blk, kid in entry,
        kid in harmlos))
for r in sorted(rows, key=lambda x: (x[13], x[0])):
    out(f"  {r[0]:>4} {r[1]:5s} {r[2]:>5} {r[3]:>5} {r[4]:>5} {r[5]:>5} "
        f"{r[6]:>5} {str(r[7]):>6} {str(r[8]):>5} {str(r[9]):>2}{str(r[10]):>2}"
        f"{str(r[11]):>2}{str(r[12]):>2} {'JA' if r[13] else 'NEIN':>7}")

out("")
out("=" * 118)
out("MERKMALS-VERGLEICH")
out("=" * 118)
for label, gruppe in (("SCHAEDLICH", schaedlich), ("HARMLOS", harmlos)):
    g = [r for r in rows if r[0] in gruppe]
    if not g:
        continue
    out(f"{label} (n={len(g)}):")
    out(f"  Aussen (je O1/O2/O3) : {sum(1 for r in g if r[7])}/{len(g)}")
    out(f"  Promoviert (Anker)   : {sum(1 for r in g if r[8])}/{len(g)}")
    out(f"  je _kandidat         : {sum(1 for r in g if r[9])}/{len(g)}")
    out(f"  je _gegenkante       : {sum(1 for r in g if r[10])}/{len(g)}")
    out(f"  je _blocker          : {sum(1 for r in g if r[11])}/{len(g)}")
    out(f"  je Entry             : {sum(1 for r in g if r[12])}/{len(g)}")
    out(f"  Reaktivierung > 0    : {sum(1 for r in g if r[6] > 0)}/{len(g)}")
    out(f"  Touch-Anzahl min/max : {min(r[3] for r in g)}/"
        f"{max(r[3] for r in g)}")
    out(f"  Dormanz min/max      : {min(r[5] for r in g)}/"
        f"{max(r[5] for r in g)}")
out("")
out("KERN: Schaedlich sind ausschliesslich Kanten, die NACH der Loeschung")
out("wieder Kontakt finden und danach konsumiert werden (Revival).")

txt = "\n".join(L)
print(txt)
with open(ROOT / "test" / "tmp_loesch_diagnose.txt", "w",
          encoding="utf-8") as f:
    f.write(txt + "\n")
