# -*- coding: utf-8 -*-
"""READ-ONLY R-SIMULATION (Mentor-Go 2026-09-09): L4-Geburts-Anker-Adapter.

KEIN Engine-Patch, KEINE Aenderung an scripts/, H1-Baseline unberuehrt.
Der Adapter wird ausschliesslich als DATEN-MUTATION auf einer Deepcopy des
Scans + einem gezielten Monkeypatch der Basis-Freeze-Regel emuliert.

Adapter-Umfang (Mentor-Audit 1-4):
  - L4: Phasen-Wand-Kanten werden vom 2-Touch-Gate befreit
        (ist_prim_anker=True, promoviert ab Phasenstart).
  - K73 als P12-Decke (Mentor: Ziel-Touch-Traegerschaft, nicht Level-Naehe).
  - L1 (Q29 lokal) und L3 (M6 lokal) GESTRICHEN -> globales Q29/M6 bleibt.
  - Transition Zone bars 640..847: geparkt (Post-Filter), separat ausgewiesen.
  - Praezisierung: L2 (Reife-Neustart) wird als eigene Variante gefahren,
    weil K67s Signal bei Bar 881 nur 8 Bars nach Pivot 873 liegt und die
    globale 24-Bar-Reife sonst blockt.

Varianten:
  V0 Referenz (unmutiert)
  V1 L4 allein
  V2 L4 + Reife-Neustart ab Phasenstart (Mentor-Entscheid, falls L4 allein
     nicht traegt)
"""
from __future__ import annotations

import copy
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_r", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan0 = engine._se_scan("AUG", cfg)
n = len(scan0["d"])
box_end_ref = scan0["box_end_bar"]
scan0["box_end_bar"] = n
d = scan0["d"]
ts = d["ts"]

# --- Phasen-Wand-Mapping (aus Trockenuebung 2, K73-Override per Mentor) -----
PHASEN_WAND = {
    "P9":  (848, 1020, "K67", "K77"),
    "P10": (1030, 1075, "K84", "K82"),
    "P11": (1082, 1134, "K78", "K86"),
    "P12": (1171, 1272, "K73", "K82"),
}
# Geburts-Anker je Kante = fruehester Phasenstart, in dem sie Wand ist
ANKER_START: dict[int, int] = {}
for pid, (bs, be, dk, bk) in PHASEN_WAND.items():
    for kid_s in (dk, bk):
        kid = int(kid_s[1:])
        if kid not in ANKER_START or bs < ANKER_START[kid]:
            ANKER_START[kid] = bs

print("=" * 128)
print("L4-GEBURTS-ANKER-ADAPTER | Phasen-Wand-Mapping")
print("=" * 128)
for pid, (bs, be, dk, bk) in PHASEN_WAND.items():
    print(f"  {pid:4s} bars {bs:4d}..{be:4d} | Decke={dk:4s} Boden={bk:4s}")
print(f"  Geburts-Anker-Freigabe ab: "
      f"{ {f'K{k}': v for k, v in sorted(ANKER_START.items())} }")

ORIG_BASIS_BEI = engine._SEEdgeH.basis_bei


def _basis_bei_kausal(self, k: int) -> float:
    """Kausales Mittel der Dochte -- OHNE Prim-Anker-Freeze (L4-spezifisch).

    Der Adapter befreit die Wand vom 2-Touch-Gate; die Linie soll dabei ihre
    kausale Mittel-Basis behalten (kein Q13-Einfrieren).
    """
    px = [p for b, p in self.wicks if b + 2 <= k]
    return float(np.mean(px)) if px else self.basis


def _mutate(sc: dict, reife_neustart: bool) -> dict:
    alle = list(sc["edges"]) + list(sc["seeds"])
    for e in alle:
        if e.kid in ANKER_START:
            e.ist_prim_anker = True
            e.promoviert_ab_bar = ANKER_START[e.kid]
            if reife_neustart:
                e.erster_pivot_bar = ANKER_START[e.kid]
    return sc


def run(anker: bool, reife_neustart: bool, nofreeze: bool) -> tuple:
    sc = copy.deepcopy(scan0)
    if anker:
        sc = _mutate(sc, reife_neustart)
    if nofreeze:
        engine._SEEdgeH.basis_bei = _basis_bei_kausal
    try:
        setups, stats = engine._se_trades(sc, cfg)
    finally:
        engine._SEEdgeH.basis_bei = ORIG_BASIS_BEI
    return setups, stats


# Isolations-Matrix: Anker (L4) x Reife-Neustart (L2) x Freeze-Aufhebung
REF, _ = run(False, False, False)
V_freeze, _ = run(False, False, True)          # nur Freeze aufgehoben
V_l4f, _ = run(True, False, True)              # L4 + Freeze weg
V_l4r_f, _ = run(True, True, True)             # L4 + L2 + Freeze weg
V_l4r, _ = run(True, True, False)              # L4 + L2, Q13-Freeze bleibt
V_l4, _ = run(True, False, False)              # L4 allein, Freeze bleibt
V1, V2 = V_l4f, V_l4r_f


def _sum(ss) -> float:
    return float(sum(t.r for t in ss))


def _box(ss):
    return [t for t in ss if t.entry_bar < box_end_ref]


def _h2(ss):
    return [t for t in ss if t.entry_bar >= box_end_ref]


def _park(ss):
    return [t for t in ss if t.entry_bar >= 848]


print("\n" + "=" * 128)
print("A) KENNZAHLEN-VERGLEICH (Isolations-Matrix)")
print("=" * 128)
print(f"  {'Variante':44s} {'ges':>4s} {'R ges':>9s} {'Box n':>5s} "
      f"{'R Box':>9s} {'H2 n':>4s} {'R H2':>8s} {'Park n':>6s} {'R Park':>8s}")
matrix = [
    ("V0 Referenz (unmutiert)", REF),
    ("V_freeze  nur Q13-Freeze aufgehoben", V_freeze),
    ("V_l4      L4 allein (Freeze bleibt)", V_l4),
    ("V_l4f     L4 + Freeze weg", V_l4f),
    ("V_l4r     L4 + L2 (Freeze bleibt)", V_l4r),
    ("V_l4r_f   L4 + L2 + Freeze weg", V_l4r_f),
]
for name, ss in matrix:
    b, h = _box(ss), _h2(ss)
    print(f"  {name:44s} {len(ss):4d} {_sum(ss):+9.4f} {len(b):5d} "
          f"{_sum(b):+9.4f} {len(h):4d} {_sum(h):+8.4f} "
          f"{len(_park(h)):6d} {_sum(_park(h)):+8.4f}")

print("\n" + "=" * 128)
print("B) V2 TRADE-LISTE (L4 + Reife-Neustart), H2 ab Bar 848")
print("=" * 128)
print(f"{'sig':>4s} {'Zeit':14s} {'Richt':6s} {'kid':>4s} {'stufe':16s} "
      f"{'entry':>9s} {'sl':>9s} {'tp2':>9s} {'poc':>9s} {'risk':>7s} "
      f"{'R':>7s} {'resultat':9s} {'grund1':7s} {'exit2':>9s}")
for t in V2:
    if t.entry_bar < 848:
        continue
    print(f"{t.bar:4d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):14s} "
          f"{t.richtung:6s} {t.kid:4d} {t.stufe:16s} {t.entry:9.4f} "
          f"{t.sl:9.4f} {t.tp2:9.4f} {t.poc:9.4f} {abs(t.sl - t.entry):7.4f} "
          f"{t.r:+7.4f} {t.resultat:9s} {t.grund1:7s} "
          f"{ts.iloc[t.exit2_bar].strftime('%d.%m. %H:%M'):>9s}")

print("\n" + "=" * 128)
print("C) K67-DETAIL (Upper1 69.90, P9) -- Trade-Herkunft je Variante")
print("=" * 128)
for name, ss in matrix:
    k67 = [t for t in ss if t.kid == 67]
    print(f"  {name:44s} {len(k67)} Trades "
          f"({', '.join(f'bar {t.bar} entry {t.entry_bar} {t.r:+.4f} R' for t in k67) or '-'})")
print(f"\n  R-Summe K67 in V_l4r_f: "
      f"{_sum([t for t in V_l4r_f if t.kid == 67]):+.4f} R")

print("\n" + "=" * 128)
print("D) STACKING / UEBERLAPPUNG (V2)")
print("=" * 128)
entry_bars = [t.entry_bar for t in V2]
dupes = sorted({b for b in entry_bars if entry_bars.count(b) > 1})
print(f"  mehrfach belegte Entry-Bars: {dupes if dupes else 'keine'}")
pro_kid: dict[int, list] = {}
for t in V2:
    pro_kid.setdefault(t.kid, []).append(t)
for kid, lst in sorted(pro_kid.items()):
    if len(lst) > 1:
        ueber = 0
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i], lst[j]
                if a.entry_bar <= b.exit2_bar and b.entry_bar <= a.exit2_bar:
                    ueber += 1
        print(f"  K{kid}: {len(lst)} Trades, zeitliche Ueberlappungen={ueber}")
print("  (V3 erzwingt max. 1 offene Position je Kante ueber den "
      f"{cfg.retest_zyklus_bars}-Bar-Zyklus ab Entry)")

print("\n" + "=" * 128)
print("E) DELTA GEGEN ARRETIERTE REFERENZ (V0)")
print("=" * 128)
ka = {(t.kid, t.bar) for t in REF}
kb = {(t.kid, t.bar) for t in V2}
print(f"  neu (V2 - V0): "
      + (", ".join(f"K{k}@bar{b}" for k, b in sorted(kb - ka)) or "-"))
print(f"  weg (V0 - V2): "
      + (", ".join(f"K{k}@bar{b}" for k, b in sorted(ka - kb)) or "-"))
for kid in sorted({k for k, _ in ka | kb}):
    ra = _sum([t for t in REF if t.kid == kid])
    rb = _sum([t for t in V2 if t.kid == kid])
    if abs(ra - rb) > 1e-9:
        print(f"  K{kid:<3d} R: V0={ra:+8.4f} -> V2={rb:+8.4f} "
              f"(delta {rb - ra:+8.4f})")
