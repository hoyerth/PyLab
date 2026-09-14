# -*- coding: utf-8 -*-
"""READ-ONLY: Kanten-Aufraeumen (AUG, volles Fenster 0-1287).

Ziel: Kanten identifizieren, die nie gebraucht werden (Zwischenlevel), und
kausale Loeschregeln testen, ohne Folgekanten (Aussenkanten-Nachfolge) zu
gefaehrden. Die Engine-Datei wird NICHT veraendert -- Simulationen laufen auf
in-memory gepatchten Modulkopien.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

ke = load("ke_base", SRC)
cfg = ke.StraightEdgeHarnessKonfiguration()
scan = ke._se_scan("AUG", cfg)
n = len(scan["d"])
box_end = scan["box_end_bar"]
alle = list(scan["edges"]) + list(scan["seeds"])
edges = scan["edges"]
seeds = scan["seeds"]
hi = scan["d"]["high"].to_numpy(dtype=float)
lo = scan["d"]["low"].to_numpy(dtype=float)

# --- Trades im VOLLEN Fenster ------------------------------------------------
scan_full = ke._se_scan("AUG", cfg)
scan_full["box_end_bar"] = n
trades, stats = ke._se_trades(scan_full, cfg)

out("#" * 118)
out("# KANTEN-AUFRAEUMEN (READ-ONLY) -- AUG volles Fenster")
out(f"# n={n} bars | box_end={box_end} | Kanten(>=2)={len(edges)} | "
    f"Seeds(<2)={len(seeds)} | Trades={len(trades)}")
out("#" * 118)
out("")


def existiert(e, k: int) -> bool:
    if not e.ist_aktiv_bei(k):
        return False
    return e.erster_pivot_bar + 2 <= k + 1


def lebt(e, k: int) -> bool:
    bars = [b for b, _ in e.wicks if b <= k]
    return bool(bars) and max(bars) >= k - cfg.wall_live_bars


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


# --- Per-Bar: wer ist die aeusserste Kante (3 Semantiken) --------------------
oben = [e for e in alle if e.seite == "OBEN"]
unten = [e for e in alle if e.seite == "UNTEN"]
outer_O1: Dict[int, set] = {}   # _existiert (Blocker-Semantik)
outer_O2: Dict[int, set] = {}   # _gegenkante-Pool
outer_O3: Dict[int, set] = {}   # _kandidat-Pool
outer_live: Dict[int, set] = {}  # _existiert UND _lebt
for k in range(n):
    for tag, fn, pool in (("O1", existiert, outer_O1),
                          ("O2", pool_gegen, outer_O2),
                          ("O3", pool_kand, outer_O3)):
        for seite, lst, rev in (("OBEN", oben, True), ("UNTEN", unten, False)):
            cand = [e for e in lst if fn(e, k)]
            if cand:
                best = (max if rev else min)(cand, key=lambda e: e.basis_bei(k))
                pool.setdefault(k, set()).add(best.kid)
    for seite, lst, rev in (("OBEN", oben, True), ("UNTEN", unten, False)):
        cand = [e for e in lst if existiert(e, k) and lebt(e, k)]
        if cand:
            best = (max if rev else min)(cand, key=lambda e: e.basis_bei(k))
            outer_live.setdefault(k, set()).add(best.kid)


def war_outer(kid: int, pool: Dict[int, set]) -> int:
    return sum(1 for k, s in pool.items() if kid in s)


# --- Nutzung im Trade-Pfad ---------------------------------------------------
entry_kids = {t.kid for t in trades}
tp2_werte = {round(t.tp2, 3) for t in trades}
blk_txt = stats.get("blocker_liste") or []
blk_kids = set()
for z in blk_txt:
    if "Aussenwand K" in z:
        blk_kids.add(int(z.split("Aussenwand K")[1].split()[0]))
zyklus_txt = stats.get("zyklus_liste") or []
zyk_kids = set(int(z.split("K")[1].split()[0]) for z in zyklus_txt)
stack_txt = stats.get("stacking_liste") or []
stack_kids = set(int(z.split("K")[1].split()[0]) for z in stack_txt)

# --- Inventar ---------------------------------------------------------------
out("=" * 118)
out("1. INVENTAR ALLER KANTEN (volles AUG, sortiert nach Seite/Basis)")
out("=" * 118)
out("  kid seite  basis    geb  pivot  n  status      O1    O2    O3  live | "
    "Entry Gegner Blocker Zyklus Stack")
out("-" * 118)
for e in sorted(alle, key=lambda e: (e.seite, e.basis)):
    ist_geg = any(abs(e.basis_bei(n - 1) - t) < 0.002 for t in tp2_werte)
    out(f"  K{e.kid:3d} {e.seite:5s} {e.basis:8.3f} {e.geburts_bar:4d} "
        f"{e.erster_pivot_bar:5d} {e.touch_anzahl:2d} "
        f"{'PRIM' if e.ist_prim_anker else e.status:11s} "
        f"{war_outer(e.kid, outer_O1):5d} {war_outer(e.kid, outer_O2):5d} "
        f"{war_outer(e.kid, outer_O3):5d} {war_outer(e.kid, outer_live):5d} | "
        f"{'X' if e.kid in entry_kids else '.':5s} "
        f"{'X' if ist_geg else '.':6s} "
        f"{'X' if e.kid in blk_kids else '.':7s} "
        f"{'X' if e.kid in zyk_kids else '.':6s} "
        f"{'X' if e.kid in stack_kids else '.'}")

# --- Klassen ---------------------------------------------------------------
nie_outer = [e for e in alle if war_outer(e.kid, outer_O1) == 0
             and war_outer(e.kid, outer_O2) == 0
             and war_outer(e.kid, outer_O3) == 0]
genutzt = set(entry_kids) | set(blk_kids) | set(zyk_kids) | set(stack_kids)
kandidaten = [e for e in nie_outer if e.kid not in genutzt]

out("")
out("=" * 118)
out("2. KLASSIFIKATION")
out("=" * 118)
out(f"  Kanten gesamt (edges+seeds)      : {len(alle)}")
out(f"  davon 'edges' (>=2 Touches)      : {len(edges)}")
out(f"  davon 'seeds' (<2 Touches)       : {len(seeds)}")
out(f"  NIE aeusserste Kante (O1/O2/O3)  : {len(nie_outer)}")
out(f"  ... davon zusaetzlich nie genutzt: {len(kandidaten)}")
out(f"  jemals als Entry-Kante           : {len(entry_kids)} -> {sorted(entry_kids)}")
out(f"  jemals als Blocker               : {len(blk_kids)} -> {sorted(blk_kids)}")
out(f"  jemals Zyklus-Sperre             : {len(zyk_kids)} -> {sorted(zyk_kids)}")
out(f"  jemals Stacking-Sperre           : {len(stack_kids)} -> {sorted(stack_kids)}")
out("")
out("  Loesch-Kandidaten (nie outer, nie genutzt):")
for e in sorted(kandidaten, key=lambda e: (e.seite, e.basis)):
    out(f"    K{e.kid:3d} {e.seite:5s} basis={e.basis:8.3f} geb={e.geburts_bar:4d} "
        f"n={e.touch_anzahl} status={e.status}")
out("")
out("  Nie-outer, ABER genutzt (bleiben!):")
for e in sorted([x for x in nie_outer if x.kid in genutzt],
                key=lambda e: (e.seite, e.basis)):
    tags = []
    if e.kid in entry_kids:
        tags.append("ENTRY")
    if e.kid in blk_kids:
        tags.append("BLOCKER")
    if e.kid in zyk_kids:
        tags.append("ZYKLUS")
    if e.kid in stack_kids:
        tags.append("STACK")
    out(f"    K{e.kid:3d} {e.seite:5s} basis={e.basis:8.3f} geb={e.geburts_bar:4d} "
        f"n={e.touch_anzahl} -> {','.join(tags)}")

txt = "\n".join(L)
print(txt)
with open(ROOT / "test" / "tmp_kanten_aufraeumen.txt", "w",
          encoding="utf-8") as f:
    f.write(txt + "\n")
