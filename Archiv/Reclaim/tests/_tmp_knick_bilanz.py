# -*- coding: utf-8 -*-
"""READ-ONLY: Knick-Bilanz ueber ALLE Kanten + Regel-Kandidaten."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_bilanz", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
d = scan["d"]
ts = d["ts"].tolist()
kanten = list(scan["edges"]) + list(scan["seeds"])

print(f"n={n} | edges={len(scan['edges'])} seeds={len(scan['seeds'])} "
      f"| gesamt={len(kanten)}")
print()

kinked, flach, anker = [], [], []
for e in kanten:
    werte = []
    for k in range(n):
        v = e.basis_bei(k)
        if not werte or abs(v - werte[-1]) > 1e-12:
            werte.append(v)
    jumps = len(werte) - 1
    if e.ist_prim_anker:
        anker.append(e.kid)
    if jumps >= 1:
        kinked.append((e.kid, e.seite, e.touch_anzahl, jumps,
                       werte[0], werte[-1]))
    else:
        flach.append(e.kid)

print(f"GEKNICKTE Linien (>=1 Sprung): {len(kinked)} von {len(kanten)}")
print(f"FLACHE Linien               : {len(flach)} von {len(kanten)}")
print(f"Primaer-Anker (eingefroren) : {len(anker)} {sorted(anker)}")
print()
print("Top-20 nach Sprungzahl:")
print("  kid  seite  touches  spruenge   v_start -> v_ende      spanne")
for kid, seite, tc, j, v0, v1 in sorted(kinked, key=lambda x: -x[3])[:20]:
    print(f"  {kid:4d} {seite:6s} {tc:7d} {j:9d}   {v0:.4f} -> {v1:.4f}"
          f"   {v1 - v0:+.4f}")
print()

# Regel-Kandidaten
print("Regel-Kandidaten je Kante (Zielniveau am Fensterende):")
print("  kid  seite   mean      letzter   min(Hoch)/max(Tief)   erster")
zeige = [73, 82, 67, 77, 76, 59]
for kid in zeige:
    e = next((x for x in kanten if x.kid == kid), None)
    if e is None:
        continue
    p = [q for _, q in e.wicks]
    if not p:
        continue
    m = sum(p) / len(p)
    letzt = p[-1]
    engst = min(p) if e.seite == "OBEN" else max(p)
    print(f"  {kid:4d} {e.seite:6s} {m:9.4f} {letzt:9.4f} {engst:19.4f} "
          f"{p[0]:9.4f}   (n={len(p)})")

print()
print("Impact-Vergleich (alle Kanten, Fensterende):")
for name, regel in (
        ("letzter Touch", lambda e, p: p[-1]),
        ("engste Kante (min Hoch / max Tief)",
         lambda e, p: min(p) if e.seite == "OBEN" else max(p)),
        ("erster Touch", lambda e, p: p[0]),
):
    max_d, sum_d, n_geaendert = 0.0, 0.0, 0
    for e in kanten:
        p = [q for _, q in e.wicks]
        if not p:
            continue
        m = sum(p) / len(p)
        v = regel(e, p)
        d_ = abs(v - m)
        if d_ > 1e-9:
            n_geaendert += 1
        sum_d += d_
        max_d = max(max_d, d_)
    print(f"  {name:36s} geaendert {n_geaendert:3d}/{len(kanten)} | "
          f"max |delta| {max_d:.4f} USD | summe {sum_d:.3f} USD")
sys.exit(0)
