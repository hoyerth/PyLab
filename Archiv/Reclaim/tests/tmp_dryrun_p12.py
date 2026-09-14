# -*- coding: utf-8 -*-
"""READ-ONLY Trockenübung P12 (Bars 1171-1272) -- Vorbereitung v0.2.

Kein Engine-Patch auf Platte. Vier Fragen:
  A) Existieren K73 (Decke) / K82 (Boden) im AUG-Scan, korrekte Seite?
  B) Laeuft die Fail-Loud-Pruefung fuer P9+P12 durch?
  C) Gibt es V0-Trades im P12-Fenster?
  D) Wie oft liegt ein Sweep im 0.12-%-Band einer P12-Grenzkante?
  E) Was aendert der Adapter (P9+P12) im P12-Fenster? H1-Regression?
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
P = ROOT / "test" / "tmp_kanten_engine_replay.py"

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    P9, Hook2ZielModus, PhasenKanteInfo, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_p12", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan0 = engine._se_scan("AUG", cfg)
n = len(scan0["d"])
scan0["box_end_bar"] = n
d = scan0["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
ts = d["ts"]
alle = list(scan0["edges"]) + list(scan0["seeds"])
by_kid = {e.kid: e for e in alle}
REF = 1259                                  # Audit-Bar (Touch 67.600)
P12_START, P12_END = 1171, 1272

print("=" * 122)
print("A) KANTEN-IDENTITAET im AUG-Scan (Ref-Bar 1259)")
print("=" * 122)
print(f"  {'kid':>4s} {'seite':>6s} {'geb':>5s} {'erster_pivot':>13s} "
      f"{'basis_bei(1259)':>16s} {'touch_conf':>11s} {'aktiv@1259':>11s}")
for kid in (67, 73, 77, 82):
    e = by_kid.get(kid)
    if e is None:
        print(f"  {kid:4d} {'-':>6s} {'-':>5s} {'-':>13s} {'-':>16s} "
              f"{'-':>11s} {'NICHT IM SCAN':>11s}")
        continue
    print(f"  {e.kid:4d} {e.seite:>6s} {e.geburts_bar:5d} "
          f"{e.erster_pivot_bar:13d} {e.basis_bei(REF):16.4f} "
          f"{e.touch_conf(REF):11d} {str(e.ist_aktiv_bei(REF)):>11s}")

print("\n" + "=" * 122)
print("B) FAIL-LOUD-PRUEFUNG P9 + P12")
print("=" * 122)
P12 = PhasenSegmentEintrag(
    phasen_id="P12",
    start_bar=P12_START,
    end_bar=P12_END,
    decke=PhasenKanteInfo(kid=73, provenienz_basis=69.5550),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355),
    ziel_preis_short=67.6355,
    ziel_preis_long=69.5550,
)
katalog = [(e.kid, e.seite, e.basis_bei(REF)) for e in alle]
adapter = PhasenRegimeAdapter(segmente=(P9, P12))
try:
    adapter.verifiziere_gegen_scan(katalog)
    print("  -> OK: P9 + P12 vollstaendig, Seiten korrekt, Basen im Band.")
except ValueError as exc:
    print(f"  -> ValueError (FAIL-LOUD): {exc}")

print("\n" + "=" * 122)
print("C) V0-TRADES im P12-Fenster (1171..1272) + Tri-State je Bar")
print("=" * 122)
ORIG = engine._se_trades
engine._se_trades = ORIG
V0, _ = engine._se_trades(copy.deepcopy(scan0), cfg)
v0_p12 = sorted([t for t in V0 if P12_START <= t.bar <= P12_END],
                key=lambda x: x.bar)
print(f"  V0-Trades im Fenster: {len(v0_p12)}")
for t in v0_p12:
    print(f"    bar {t.bar:4d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M')} "
          f"{t.richtung:5s} K{t.kid:3d} {t.stufe:16s} entry_bar={t.entry_bar} "
          f"entry={t.entry:.4f} sl={t.sl:.4f} tp2={t.tp2:.4f} "
          f"R={t.r:+.4f} {t.resultat}/{t.grund1}")
print("  Tri-State im Fenster: "
      + ", ".join(f"{b}:{adapter.hook_2_ziel(b, 'SHORT').modus.value[:4]}"
                  for b in (1170, 1171, 1200, 1272, 1273)))

print("\n" + "=" * 122)
print("D) SWEEP-IM-BAND der P12-GRENZKANTEN (0.12 %, nur Docht-Defizit)")
print("=" * 122)
decke, boden = by_kid.get(73), by_kid.get(82)
treffer = []
for k in range(P12_START, P12_END + 1):
    for e, richtung, sweep in ((decke, "SHORT", float(hi[k])),
                               (boden, "LONG", float(lo[k]))):
        if e is None:
            continue
        if not (e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1):
            continue
        basis = e.basis_bei(k)
        dist = ((sweep - basis) if richtung == "SHORT"
                else (basis - sweep)) / basis * 100.0
        if abs(dist) <= 0.12:
            treffer.append((k, richtung, e.kid, basis, sweep, dist, dist < 0.0))
print(f"  Treffer: {len(treffer)}")
for k, richtung, kid, basis, sweep, dist, defizit in treffer:
    print(f"    bar {k:4d} {ts.iloc[k].strftime('%d.%m. %H:%M')} {richtung:5s} "
          f"K{kid:3d} basis={basis:.4f} sweep={sweep:.4f} dist={dist:+.4f}% "
          f"-> {'Docht-Defizit (Hook greift)' if defizit else 'Durchstich (Q1)'}")

print("\n" + "=" * 122)
print("E) ADAPTER-LAUF (P9+P12) -- H1-Regression + P12-Wirkung")
print("=" * 122)
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None

A_KANTEN = '''        return max(bars) >= k - cfg.wall_live_bars

    def _im_aussenquartil('''
A_KANTEN_NEW = '''        return max(bars) >= k - cfg.wall_live_bars

    def _seite_kanten(k: int, seite: KantenSeite) -> List[Tuple[int, float]]:
        return [(e.kid, e.basis_bei(k)) for e in seite_edges[seite]
                if _existiert(e, k)]

    _freigabe_kid: Optional[int] = None

    def _im_aussenquartil('''
A_LOOP = '''            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            kd = _kandidat(richtung, k, sweep_px)'''
A_LOOP_NEW = '''            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            _seite: KantenSeite = ("OBEN" if richtung == "SHORT" else "UNTEN")
            _freigabe_kid = _hook.hook_1_freigabe_kid(
                k, sweep_px, richtung, _seite_kanten(k, _seite))
            kd = _kandidat(richtung, k, sweep_px)'''
A_POOL = '''        if not pool:
            return None
        pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))'''
A_POOL_NEW = A_POOL + '''
        if _freigabe_kid is not None:
            pool = [e for e in pool if e.kid != _freigabe_kid]'''
A_M6_OBEN = '''            if seite == "OBEN":
                if b <= sweep_px:
                    continue                    # erreicht -> kein Blocker'''
A_M6_OBEN_NEW = A_M6_OBEN + '''
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue'''
A_M6_UNTEN = '''            else:
                if b >= sweep_px:
                    continue'''
A_M6_UNTEN_NEW = A_M6_UNTEN + '''
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue'''
A_TP2 = '            gegen_basis = geg.basis_bei(k)\n'
A_TP2_NEW = A_TP2 + '''            _h2 = _hook.hook_2_ziel(k, richtung)
            if _h2.modus is _Hook2ZielModus.BLOCKIERT:
                stats["kein_raum"] += 1
                continue
            if _h2.modus is _Hook2ZielModus.PHASE:
                gegen_basis = _h2.ziel_preis
'''
for _name, _s in (("A_KANTEN", A_KANTEN), ("A_LOOP", A_LOOP),
                  ("A_POOL", A_POOL), ("A_M6_OBEN", A_M6_OBEN),
                  ("A_M6_UNTEN", A_M6_UNTEN), ("A_TP2", A_TP2)):
    assert src.count(_s) == 1, _name
patched_src = (src.replace(A_KANTEN, A_KANTEN_NEW)
               .replace(A_LOOP, A_LOOP_NEW)
               .replace(A_POOL, A_POOL_NEW)
               .replace(A_M6_OBEN, A_M6_OBEN_NEW)
               .replace(A_M6_UNTEN, A_M6_UNTEN_NEW)
               .replace(A_TP2, A_TP2_NEW))
ns = dict(engine.__dict__)
ns["_hook"] = adapter
ns["_Hook2ZielModus"] = Hook2ZielModus
exec(compile(patched_src, "<se_trades_p9p12>", "exec"), ns)
PATCHED = ns["_se_trades"]

engine._se_trades = PATCHED
try:
    V1, _ = engine._se_trades(copy.deepcopy(scan0), cfg)
finally:
    engine._se_trades = ORIG

h1_0 = {(t.kid, t.bar): t.r for t in V0 if t.entry_bar < 640}
h1_1 = {(t.kid, t.bar): t.r for t in V1 if t.entry_bar < 640}
ident = (set(h1_0) == set(h1_1)
         and all(abs(h1_0[k] - h1_1[k]) < 1e-12 for k in h1_0))
print(f"  H1: V0 {len(h1_0)}/{sum(h1_0.values()):+.6f} R | "
      f"V1 {len(h1_1)}/{sum(h1_1.values()):+.6f} R -> "
      f"{'BIT-IDENTISCH' if ident else 'ABWEICHUNG'}")
v1_p12 = sorted([t for t in V1 if P12_START <= t.bar <= P12_END],
                key=lambda x: x.bar)
print(f"  P12: V0 {len(v0_p12)} Trades | V1 {len(v1_p12)} Trades")
k0 = {(t.kid, t.bar): t for t in v0_p12}
k1 = {(t.kid, t.bar): t for t in v1_p12}
print(f"  hinzu: {sorted(set(k1) - set(k0)) or '-'}")
print(f"  weg  : {sorted(set(k0) - set(k1)) or '-'}")
for key in sorted(set(k0) & set(k1)):
    a, b = k0[key], k1[key]
    if abs(a.r - b.r) > 1e-9 or abs(a.tp2 - b.tp2) > 1e-9:
        print(f"  Aenderung {key}: R {a.r:+.4f} -> {b.r:+.4f} | "
              f"tp2 {a.tp2:.4f} -> {b.tp2:.4f}")
print(f"  H2 gesamt V0: {sum(t.r for t in V0 if t.entry_bar >= 640):+.4f} R | "
      f"V1: {sum(t.r for t in V1 if t.entry_bar >= 640):+.4f} R")

print("\n" + "=" * 122)
print("F) KASKADEN-TRACE an den Hook-Treffern (mit Freigabe)")
print("=" * 122)
seite_edges = {"OBEN": [e for e in alle if e.seite == "OBEN"],
               "UNTEN": [e for e in alle if e.seite == "UNTEN"]}


def _existiert(e, k):
    return e.ist_aktiv_bei(k) and e.erster_pivot_bar + 2 <= k + 1


def _etabliert(e, k):
    return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars


def _lebt(e, k):
    bars = [b for b, _ in e.wicks if b <= k]
    return bool(bars) and max(bars) >= k - cfg.wall_live_bars


for k, richtung, kid in ((1211, "SHORT", 73), (1259, "LONG", 82),
                         (1271, "SHORT", 73), (1272, "SHORT", 73)):
    seite = "OBEN" if richtung == "SHORT" else "UNTEN"
    sweep = float(hi[k]) if richtung == "SHORT" else float(lo[k])
    print(f"\n  --- bar {k} {ts.iloc[k].strftime('%d.%m. %H:%M')} {richtung} "
          f"sweep={sweep:.4f} ---")

    def _dist(e):
        b = e.basis_bei(k)
        return ((sweep - b) if richtung == "SHORT" else (b - sweep)) / b * 100.0

    pool = []
    for e in seite_edges[seite]:
        if not _existiert(e, k):
            continue
        if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                or e.touch_conf(k) >= 2):
            continue
        if not _etabliert(e, k):
            continue
        pool.append(e)
    for e in seite_edges[seite]:
        if e in pool or not _existiert(e, k) or e.ist_prim_anker:
            continue
        if e.touch_conf(k) >= 2 or not _etabliert(e, k):
            continue
        dd = _dist(e)
        if cfg.sweep_mindestdurchstich_pct < dd <= cfg.max_sweep_ueberdehnung_pct:
            pool.append(e)
    frei = adapter.hook_1_freigabe_kid(
        k, sweep, richtung,
        [(e.kid, e.basis_bei(k)) for e in seite_edges[seite]
         if _existiert(e, k)])
    pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))
    print(f"    Freigabe-kid = {frei}")
    print("    Pool roh     : "
          + str([(e.kid, round(_dist(e), 4)) for e in pool]))
    pool = [e for e in pool if e.kid != frei]
    print("    Pool gefilter: "
          + str([(e.kid, round(_dist(e), 4)) for e in pool]))
    verdikt = "Pool leer -> kein Kandidat"
    kd = None
    for pos, e in enumerate(pool):
        dd = _dist(e)
        if dd < 0.0:
            if _lebt(e, k):
                verdikt = (f"pos{pos} K{e.kid} dist={dd:+.4f}% <0 LEBT "
                           f"-> return None")
                break
            verdikt = f"pos{pos} K{e.kid} dormant -> continue"
            continue
        if dd > cfg.max_sweep_ueberdehnung_pct:
            verdikt = f"pos{pos} K{e.kid} Ueberdehnung -> return None"
            break
        if dd <= cfg.sweep_mindestdurchstich_pct:
            continue
        if pos == 0:
            kd = e
            verdikt = f"pos0 K{e.kid} dist={dd:+.4f}% -> HANDELT (Q1)"
            break
        if e.touch_conf(k) < cfg.min_touches_handelbar:
            verdikt = (f"pos{pos} K{e.kid} V-S={e.touch_conf(k)}<3 -> continue")
            continue
        kd = e
        verdikt = (f"pos{pos} K{e.kid} dist={dd:+.4f}% "
                   f"V-S={e.touch_conf(k)} -> HANDELT")
        break
    print(f"    Kandidat     : {verdikt}")
    if kd is None:
        continue
    basis_k = kd.basis_bei(k)
    aussen = None
    for e in seite_edges[seite]:
        if e is kd or not _existiert(e, k):
            continue
        b = e.basis_bei(k)
        if seite == "OBEN":
            if b <= sweep or (frei is not None and e.kid == frei):
                continue
            if aussen is None or b > aussen.basis_bei(k):
                aussen = e
        else:
            if b >= sweep or (frei is not None and e.kid == frei):
                continue
            if aussen is None or b < aussen.basis_bei(k):
                aussen = e
    if aussen is None:
        print("    M6           : kein Blocker")
    else:
        b = aussen.basis_bei(k)
        d = ((b - basis_k) if seite == "OBEN"
             else (basis_k - b)) / basis_k * 100.0
        wirkt = 0.0 < d <= cfg.max_seed_distanz_pct
        print(f"    M6           : K{aussen.kid} basis={b:.4f} dist={d:+.4f}% "
              f"-> {'BLOCKER' if wirkt else 'ausserhalb 0.75 % -> frei'}")
    h2 = adapter.hook_2_ziel(k, richtung)
    print(f"    Hook 2       : {h2.modus.value} ziel={h2.ziel_preis}")

print("\n" + "=" * 122)
print("G) GATE-LISTEN des Adapter-Laufs im P12-Fenster (welche Sperre greift?)")
print("=" * 122)
engine._se_trades = PATCHED
try:
    _, st1 = engine._se_trades(copy.deepcopy(scan0), cfg)
finally:
    engine._se_trades = ORIG
for key in ("blocker_liste", "quartil_liste", "zyklus_liste",
            "stacking_liste"):
    eintraege = [z for z in st1.get(key, [])
                 if any(f"bar {b:4d} " in z for b in
                        (1211, 1259, 1271, 1272))]
    print(f"\n  {key}: {len(eintraege)} Treffer im P12-Fenster")
    for z in eintraege:
        print(f"    {z}")
print(f"\n  Stats V1 (Auszug): "
      + ", ".join(f"{k}={st1[k]}" for k in
                  ("blocker", "quartil_blockiert", "zyklus_blockiert",
                   "kein_gegner", "kein_raum", "f3", "v_s") if k in st1))
engine._se_trades = ORIG
_, st0 = engine._se_trades(copy.deepcopy(scan0), cfg)
print("  Stats V0 (Auszug): "
      + ", ".join(f"{k}={st0[k]}" for k in
                  ("blocker", "quartil_blockiert", "zyklus_blockiert",
                   "kein_gegner", "kein_raum", "f3", "v_s") if k in st0))
