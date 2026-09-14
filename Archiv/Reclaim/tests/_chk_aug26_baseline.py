# -*- coding: utf-8 -*-
"""AUG26 Schritte 1+2 (READ-ONLY): Baseline V0/V1_basis + Cluster der Roh-Segmente.

Schritt 1 -- Nackte Kanten-Baseline auf AUG26 (n=1932, box_end=1104):
    V0        = Engine native (ORIG._se_trades)
    V1_basis  = 13 Renderer-Bestands-Patches, DEFAULT_ADAPTER (1 Segment)
  Kennzahlen: Trades, Winrate, R_brutto, R_realisiert (b), R_untergrenze (a),
  Q_stop, Long/Short, max. Concurrency je Richtung.

Schritt 2 -- Forensik der 96 Roh-Segmente:
  Cluster-Analyse der Preisplateaus (Decke/Boden), Distanzmatrix,
  Nachweis welche Roh-Segmente via _nah (touch_band_pct) zusammengehoeren.

Keine Regel-/Produktivaenderung; keine PNG-Erzeugung.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    DEFAULT_ADAPTER,
    Hook2ZielModus,
)

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN_P = ROOT / "test" / "tmp_png_aug_sichttest.py"

spec = importlib.util.spec_from_file_location("engine", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = scan["n"]
BOX = int(scan["box_end_bar"])
scan["box_end_bar"] = n
d = scan["d"]
ts = list(d["ts"])
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
W = cfg.tp1_anteil_pct / 100.0
alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {int(e.kid): e for e in alle}
BAND = cfg.touch_band_pct

# ------------------------------------------------ 13 Bestands-Patches (AST)
ren = REN_P.read_text(encoding="utf-8")
ren_tree = ast.parse(ren)
basis: Dict[str, str] = {}
for _node in ren_tree.body:
    if isinstance(_node, ast.Assign) and len(_node.targets) == 1 \
            and isinstance(_node.targets[0], ast.Name) \
            and _node.targets[0].id.startswith("A_"):
        try:
            exec(compile(ast.get_source_segment(ren, _node), "<a_>", "exec"),  # noqa: S102
                 basis)
        except Exception:  # noqa: BLE001
            pass

_src_datei = ENGINE_P.read_text(encoding="utf-8")
_src_tree = ast.parse(_src_datei)
_src_node = next(x for x in _src_tree.body
                 if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src_base = ast.get_source_segment(_src_datei, _src_node)
assert src_base is not None
src13 = src_base
_KETTE = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
for _nm in _KETTE:
    assert src13.count(basis[_nm]) == 1, (_nm, src13.count(basis[_nm]))
    src13 = src13.replace(basis[_nm], basis[_nm + "_NEW"])

ns: Dict[str, object] = dict(engine.__dict__)
ns["_hook"] = DEFAULT_ADAPTER
ns["_Hook2ZielModus"] = Hook2ZielModus
ORIG = engine._se_trades

print("=" * 104)
print("AUG26 -- SCHRITT 1: NACKTE KANTEN-BASELINE (V0 / V1_basis)")
print("=" * 104)
print(f"n = {n} Bars | box_end(19.08.) = Bar {BOX} = {ts[BOX]} | "
      f"Spanne {lo.min():.4f}..{hi.max():.4f}")
print(f"Kanten: {len(scan['edges'])} edges + {len(scan['seeds'])} seeds")


def _max_conc(setups: List, richtung: str) -> int:
    ev = []
    for t in setups:
        if t.richtung != richtung:
            continue
        a = int(t.entry_bar)
        b = max(int(t.exit1_bar), int(t.exit2_bar))
        ev.append((a, 1))
        ev.append((b, -1))
    ev.sort(key=lambda x: (x[0], x[1]))
    cur = mx = 0
    for _, dv in ev:
        cur += dv
        mx = max(mx, cur)
    return mx


def _lauf(quelle: str) -> Tuple[List, Dict]:
    ns["_hook"] = DEFAULT_ADAPTER
    if quelle is src_base:
        setups, st = ORIG(copy.deepcopy(scan), cfg)
    else:
        exec(compile(quelle, "<basis>", "exec"), ns)  # noqa: S102
        setups, st = ns["_se_trades"](copy.deepcopy(scan), cfg)  # type: ignore
    return list(setups), dict(st)


def _report(name: str, S: List, ST: Dict) -> None:
    brutto = sum(float(t.r) for t in S)
    b = sum((0.0 if t.grund1 == "ENDE" else W * float(t.r1))
            + (0.0 if t.grund2 == "ENDE" else (1.0 - W) * float(t.r2)) for t in S)
    a_set = [t for t in S if t.grund1 != "ENDE" and t.grund2 != "ENDE"]
    a = sum(W * float(t.r1) + (1.0 - W) * float(t.r2) for t in a_set)
    lng = [t for t in S if t.richtung == "LONG"]
    sht = [t for t in S if t.richtung == "SHORT"]
    gew = sum(1 for t in S if float(t.r) > 0)
    stop = sum(1 for t in S if float(t.r) <= -0.999)
    h1 = [t for t in S if int(t.entry_bar) < BOX]
    h2 = [t for t in S if int(t.entry_bar) >= BOX]
    w1 = [t for t in S if int(t.entry_bar) <= 459]
    alt = [t for t in S if 460 <= int(t.entry_bar) <= 1747]
    print(f"\n   --- {name} ---")
    print(f"   Trades      : {len(S)}   (LONG {len(lng)} / SHORT {len(sht)})")
    print(f"   Winrate     : {100.0 * gew / len(S) if S else 0:.1f} %   "
          f"({gew}/{len(S)})")
    print(f"   R_brutto    : {brutto:+.6f}")
    print(f"   R_realis.(b): {b:+.6f}   R_untergr.(a): {a:+.6f} "
          f"({len(a_set)} Trades ohne ENDE)")
    print(f"   Q_stop      : {stop}/{len(S)} "
          f"({100.0 * stop / len(S) if S else 0:.1f} %) volle SL")
    print(f"   H1 (<{BOX}) : {len(h1)} / {sum(float(t.r) for t in h1):+.6f}   "
          f"H2 (>=): {len(h2)} / {sum(float(t.r) for t in h2):+.6f}")
    print(f"   Max-Concur. : LONG {_max_conc(S, 'LONG')} / "
          f"SHORT {_max_conc(S, 'SHORT')}   "
          f"(Cap {cfg.max_gleichzeitig_je_richtung})")
    print(f"   Woche 1 (0..459)      : {len(w1)} / "
          f"{sum(float(t.r) for t in w1):+.6f}")
    print(f"   Altes AUG (460..1747) : {len(alt)} / "
          f"{sum(float(t.r) for t in alt):+.6f}")
    print(f"   stats: concurrency_blockiert="
          f"{int(ST.get('concurrency_blockiert', -1))}  "
          f"v_s={int(ST.get('v_s', -1))}  kein_raum="
          f"{int(ST.get('kein_raum', -1))}")


V0, ST0 = _lauf(src_base)
V1, ST1 = _lauf(src13)
_report("V0 (Engine native, ankerfrei)", V0, ST0)
_report("V1_basis (13 Bestands-Patches, DEFAULT_ADAPTER)", V1, ST1)

print("\n   V0-Trades (alle):")
for t in sorted(V0, key=lambda x: int(x.bar)):
    print(f"      bar {int(t.bar):>5} entry {int(t.entry_bar):>5} "
          f"{t.richtung:<6} K{int(t.kid):<4} R {float(t.r):>+10.5f}  "
          f"({t.grund1}/{t.grund2})")

# ============================================================ SCHRITT 2
print("\n\n" + "=" * 104)
print("AUG26 -- SCHRITT 2: FORENSIK DER ROH-SEGMENTE (Cluster der Preisplateaus)")
print("=" * 104)


def _lebt_kausal(e, k: int) -> bool:
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]
    return bool(b) and max(b) >= k - cfg.wall_live_bars


def ecken(k: int) -> Tuple[Optional[int], Optional[int]]:
    oben, unten = [], []
    for e in alle:
        if not _lebt_kausal(e, k):
            continue
        (oben if e.seite == "OBEN" else unten).append(e)
    o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
    u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
    return (int(o.kid) if o else None), (int(u.kid) if u else None)


wechsel: List[Tuple[int, Optional[int], Optional[int]]] = []
vor: Optional[Tuple[Optional[int], Optional[int]]] = None
for k in range(2, n):
    cur = ecken(k)
    if cur == (None, None) or cur == vor:
        continue
    vor = cur
    wechsel.append((k, cur[0], cur[1]))

roh: List[List[int]] = []
for (k, ko, ku) in wechsel:
    if ko is None or ku is None:
        continue
    if roh:
        roh[-1][1] = k - 1
    roh.append([k, n - 1, ko, ku])

print(f"\nRoh-Segmente: {len(roh)}  (Laengen: "
      f"{sum(1 for s in roh if s[1] - s[0] + 1 < 77)} unter 77 Bars)")
print(f"\n   {'#':<4}{'Fenster':<14}{'Bars':>5}  {'Decke':<18}{'Boden':<18}"
      f"{'Startzeit'}")
for i, s in enumerate(roh, 1):
    vo = katalog[s[2]].basis_bei(s[0])
    vu = katalog[s[3]].basis_bei(s[0])
    print(f"   {i:<4}{f'{s[0]}..{s[1]}':<14}{s[1] - s[0] + 1:>5}  "
          f"{f'K{s[2]} {vo:.4f}':<18}{f'K{s[3]} {vu:.4f}':<18}{ts[s[0]]}")

# --- Cluster: zusammenhaengende Roh-Segmente mit _nah-verwandten Grenzen
print("\n" + "-" * 104)
print("CLUSTER (Preisplateau): zusammenhaengende Roh-Segmente, deren Grenzen "
      f"je <= {BAND}% abweichen ODER die kuerzer als 77 Bars sind")
print("-" * 104)


def _nah(p: List[int], s: List[int]) -> bool:
    ko1, ko2 = katalog[p[2]].basis_bei(p[0]), katalog[s[2]].basis_bei(s[0])
    ku1, ku2 = katalog[p[3]].basis_bei(p[0]), katalog[s[3]].basis_bei(s[0])
    return (abs(ko2 - ko1) / ko1 * 100.0 <= BAND
            and abs(ku2 - ku1) / ku1 * 100.0 <= BAND)


# Variante A: mit Laengenregel (Status quo)
def _merge(segs: List[List[int]], min_bars: int,
           use_len: bool) -> List[List[int]]:
    out: List[List[int]] = []
    for s in segs:
        if out and ((use_len and (s[1] - s[0] + 1) < min_bars)
                    or _nah(out[-1], s)):
            out[-1][1] = s[1]
        else:
            out.append(list(s))
    return out


for tag, use_len in (("Status quo (Laenge 77 ODER nah)", True),
                     ("nur nah (keine Laengenregel)", False)):
    segs = _merge(roh, 77, use_len)
    print(f"\n   {tag}: {len(segs)} Segmente")
    for i, s in enumerate(segs, 1):
        vo = katalog[s[2]].basis_bei(s[0])
        vu = katalog[s[3]].basis_bei(s[0])
        ist_lo, ist_hi = float(lo[s[0]:s[1] + 1].min()), float(hi[s[0]:s[1] + 1].max())
        aus = int(((hi[s[0]:s[1] + 1] > vo) |
                   (lo[s[0]:s[1] + 1] < vu)).sum())
        print(f"      {i}: {s[0]:>5}..{s[1]:<5} ({s[1] - s[0] + 1:>4} Bars) "
              f"K{s[2]}/{s[3]}  Korridor {vu:.4f}..{vo:.4f}  "
              f"IST {ist_lo:.4f}..{ist_hi:.4f}  ausserhalb {aus}")

# --- Nachweis: welche Roh-Segmente sind mit ihrem Vorgaenger _nah?
print("\n" + "-" * 104)
print("NACHWEIS _nah() an der Roh-Kette (welche Grenze bricht das Band?)")
print("-" * 104)
brueche, nahs = [], []
for i in range(1, len(roh)):
    p, s = roh[i - 1], roh[i]
    ko1, ko2 = katalog[p[2]].basis_bei(p[0]), katalog[s[2]].basis_bei(s[0])
    ku1, ku2 = katalog[p[3]].basis_bei(p[0]), katalog[s[3]].basis_bei(s[0])
    do = abs(ko2 - ko1) / ko1 * 100.0
    du = abs(ku2 - ku1) / ku1 * 100.0
    (nahs if _nah(p, s) else brueche).append((i, s[0], do, du,
                                              s[1] - s[0] + 1))
print(f"   Uebergaenge nah  (<= {BAND}%): {len(nahs)}")
print(f"   Uebergaenge fern (>  {BAND}%): {len(brueche)}")
print(f"\n   Die {min(len(brueche), 20)} groessten Grenzspruenge (Decke/Boden):")
print(f"      {'#':<4}{'ab Bar':<8}{'dDecke%':>10}{'dBoden%':>10}{'Laenge':>8}")
for (i, k, do, du, ln) in sorted(brueche, key=lambda z: -max(z[2], z[3]))[:20]:
    print(f"      {i:<4}{k:<8}{do:>10.3f}{du:>10.3f}{ln:>8}")

# --- Preisplateau-Histogramm: wie oft ist eine Kante Grenze?
print("\n" + "-" * 104)
print("KANTEN-ROLLE im Rohverlauf (wie oft ist eine Kante Decke/Boden?)")
print("-" * 104)
from collections import Counter  # noqa: E402
co = Counter(s[2] for s in roh)
cu = Counter(s[3] for s in roh)
print("   Top-Decken:")
for kid, c in co.most_common(10):
    print(f"      K{kid:<4} {c:>3}x   {katalog[kid].basis_bei(0):.4f}  "
          f"({katalog[kid].seite})")
print("   Top-Boeden:")
for kid, c in cu.most_common(10):
    print(f"      K{kid:<4} {c:>3}x   {katalog[kid].basis_bei(0):.4f}  "
          f"({katalog[kid].seite})")

print("\nENDE AUG26 SCHRITTE 1+2")
