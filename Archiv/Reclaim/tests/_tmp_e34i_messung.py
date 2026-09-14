# -*- coding: utf-8 -*-
"""E-34i (read-only) -- Messlauf der drei offenen V019-Renderer-Sollwerte.

Repliziert EXAKT die Lauf-Maschinerie des Renderers
(``test/tmp_png_aug_sichttest.py`` Z. 541-665) -- ohne matplotlib, ohne
PNG-Erzeugung, ohne Schreiben. Gemessen werden:

  * ``referenz_soll``  = Schluessel (bar, kid) von  V1_basis \\ V1_aktiv,
  * ``neu_basis_soll`` = Schluessel (bar, kid) von  V1_aktiv \\ V1_basis
                         (OHNE den G4-Zusatz (1002, 77); der wird im
                         Renderer bei ``g4_aktiv`` automatisch ergaenzt),
  * ``quartett_r_soll``= R je Bar in (903, 980, 981, 1020) aus V1_aktiv.

Ergaenzend: Gesamt-/H1-/H2-/P9-/ZIEL-Kennzahlen zur Gegenprobe.
Adapter (SHA 4f50b6b0...) und Engine (SHA 4a576a76...) bleiben unberuehrt.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus, PhasenRegimeAdapter,
)

P = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUT = ROOT / "test" / "_tmp_e34i_messung_out.txt"
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        _FH.flush()
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_e34i", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]

# ---- Renderer-Patch (Z. 541-642, wortgleich) ------------------------------
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None

A_KANTEN = '''        return max(bars) >= k - cfg.wall_live_bars

    def _im_aussenquartil('''
A_KANTEN_NEW = '''        return max(bars) >= k - cfg.wall_live_bars

    def _basis_wirksam(e: _SEEdgeH, k: int) -> float:
        return _hook.angewandte_basis(k, e.kid, e.basis_bei(k))

    def _seite_kanten(k: int, seite: KantenSeite) -> List[Tuple[int, float]]:
        return [(e.kid, _basis_wirksam(e, k)) for e in seite_edges[seite]
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
A_POOL_NEW = '''        if not pool:
            return None
        pool.sort(key=lambda e: _basis_wirksam(e, k),
                  reverse=(seite == "OBEN"))
        if _freigabe_kid is not None:
            pool = [e for e in pool if e.kid != _freigabe_kid]'''
A_DIST = '''        def _dist(e: _SEEdgeH) -> float:
            basis = e.basis_bei(k)'''
A_DIST_NEW = '''        def _dist(e: _SEEdgeH) -> float:
            basis = _basis_wirksam(e, k)'''
A_M6_OBEN = '''            if seite == "OBEN":
                if b <= sweep_px:'''
A_M6_OBEN_NEW = '''            if seite == "OBEN":
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue
                if b <= sweep_px:'''
A_M6_UNTEN = '''            else:
                if b >= sweep_px:'''
A_M6_UNTEN_NEW = '''            else:
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue
                if b >= sweep_px:'''
A_M6_BASIS = '''            b = e.basis_bei(k)
            if seite == "OBEN":'''
A_M6_BASIS_NEW = '''            b = _basis_wirksam(e, k)
            if seite == "OBEN":'''
A_M6_BASIS_K = '        basis_k = kd.basis_bei(k)'
A_M6_BASIS_K_NEW = '        basis_k = _basis_wirksam(kd, k)'
A_M6_RET = '''        b = aussen.basis_bei(k)
        dist = ((b - basis_k) if seite == "OBEN"'''
A_M6_RET_NEW = '''        b = _basis_wirksam(aussen, k)
        dist = ((b - basis_k) if seite == "OBEN"'''
A_M6_SORT = '                if aussen is None or b > aussen.basis_bei(k):'
A_M6_SORT_NEW = ('                if aussen is None '
                 'or b > _basis_wirksam(aussen, k):')
A_M6_SORT2 = '                if aussen is None or b < aussen.basis_bei(k):'
A_M6_SORT2_NEW = ('                if aussen is None '
                  'or b < _basis_wirksam(aussen, k):')
A_TP2 = '            gegen_basis = geg.basis_bei(k)\n'
A_TP2_NEW = A_TP2 + '''            _h2 = _hook.hook_2_ziel(k, richtung)
            if _h2.modus is _Hook2ZielModus.BLOCKIERT:
                stats["kein_raum"] += 1
                continue
            if _h2.modus is _Hook2ZielModus.PHASE:
                gegen_basis = _h2.ziel_preis
'''
A_KBASIS = '            basis = kd.basis_bei(k)\n'
A_KBASIS_NEW = '            basis = _basis_wirksam(kd, k)\n'

for _name, _s in (("A_KANTEN", A_KANTEN), ("A_LOOP", A_LOOP),
                  ("A_POOL", A_POOL), ("A_DIST", A_DIST),
                  ("A_M6_OBEN", A_M6_OBEN), ("A_M6_UNTEN", A_M6_UNTEN),
                  ("A_M6_BASIS", A_M6_BASIS), ("A_M6_BASIS_K", A_M6_BASIS_K),
                  ("A_M6_RET", A_M6_RET), ("A_M6_SORT", A_M6_SORT),
                  ("A_M6_SORT2", A_M6_SORT2), ("A_TP2", A_TP2),
                  ("A_KBASIS", A_KBASIS)):
    assert src.count(_s) == 1, (_name, src.count(_s))
patched_src = (src.replace(A_KANTEN, A_KANTEN_NEW)
               .replace(A_LOOP, A_LOOP_NEW)
               .replace(A_POOL, A_POOL_NEW)
               .replace(A_DIST, A_DIST_NEW)
               .replace(A_M6_BASIS_K, A_M6_BASIS_K_NEW)
               .replace(A_M6_BASIS, A_M6_BASIS_NEW)
               .replace(A_M6_RET, A_M6_RET_NEW)
               .replace(A_M6_SORT, A_M6_SORT_NEW)
               .replace(A_M6_SORT2, A_M6_SORT2_NEW)
               .replace(A_M6_OBEN, A_M6_OBEN_NEW)
               .replace(A_M6_UNTEN, A_M6_UNTEN_NEW)
               .replace(A_TP2, A_TP2_NEW)
               .replace(A_KBASIS, A_KBASIS_NEW))

ORIG = engine._se_trades
ns = dict(engine.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus


def _lauf(hook: PhasenRegimeAdapter, mit_patch: bool):
    ns["_hook"] = hook
    exec(compile(patched_src, "<se_trades_e34i>", "exec"), ns)
    if not mit_patch:
        return ORIG(copy.deepcopy(scan), cfg)
    engine._se_trades = ns["_se_trades"]
    try:
        return engine._se_trades(copy.deepcopy(scan), cfg)
    finally:
        engine._se_trades = ORIG


print("=" * 104)
print("E-34i MESSLAUF DER V019-RENDERER-SOLLWERTE (read-only, keine PNG)")
print("=" * 104)
print(f"Engine: {P.name} | box_end(AUG)={box_end} | n={n}")
print(f"Adapter default: {[s.phasen_id for s in DEFAULT_ADAPTER.segmente]}")
print(f"Adapter V019   : {[s.phasen_id for s in ADAPTER_V019.segmente]}")

scan["box_end_bar"] = n                       # Voll-Lauf (wie Renderer Z. 507)
V0, _ = _lauf(DEFAULT_ADAPTER, False)
V1_basis, _ = _lauf(DEFAULT_ADAPTER, True)
V1_aktiv, _ = _lauf(ADAPTER_V019, True)

ts = scan["d"]["ts"]


def _key(t):
    return (int(t.bar), int(t.kid))


AKT = {_key(t) for t in V1_aktiv}
BAS = {_key(t) for t in V1_basis}
REFERENZ = [t for t in V1_basis if _key(t) not in AKT]
NEU = [t for t in V1_aktiv if _key(t) not in BAS]

QUARTETT_BARS = (903, 980, 981, 1020)
_q = {t.bar: t for t in V1_aktiv if t.bar in QUARTETT_BARS}

print(f"\nLaenge: V0={len(V0)}  V1_basis={len(V1_basis)}  V1_aktiv={len(V1_aktiv)}"
      f"  delta={len(V1_aktiv) - len(V1_basis)}")
print(f"R: R0={sum(t.r for t in V0):+.6f}  "
      f"RB={sum(t.r for t in V1_basis):+.6f}  "
      f"R1={sum(t.r for t in V1_aktiv):+.6f}")

print("\n--- V1_aktiv (V019) Trades ---")
print(f"  {'bar':>5} {'kid':>4} {'richt':5} {'entry_bar':>9} {'r':>12}")
for t in sorted(V1_aktiv, key=lambda x: x.bar):
    print(f"  {t.bar:>5} {t.kid:>4} {t.richtung:5} {t.entry_bar:>9} "
          f"{t.r:>+12.6f}")

print("\n--- MESSUNG 1: referenz_soll = V1_basis \\ V1_aktiv ---")
ref_keys = [_key(t) for t in sorted(REFERENZ, key=lambda x: x.bar)]
print(f"  REFERENZ n={len(REFERENZ)}  keys={ref_keys}")
print(f"  referenz_soll = {tuple(ref_keys)}")

print("\n--- MESSUNG 2: neu_basis_soll = V1_aktiv \\ V1_basis "
      "(ohne G4-Zusatz) ---")
neu_keys = sorted(_key(t) for t in NEU)
print(f"  NEU n={len(NEU)}  keys={neu_keys}")
g4 = (1002, 77)
neu_ohne = [k for k in neu_keys if k != g4]
print(f"  G4-Zusatz {g4} enthalten: {g4 in neu_keys}")
print(f"  neu_basis_soll (ohne G4) = {tuple(neu_ohne)}")
print(f"  neu_basis_soll (mit G4)  = {tuple(neu_keys)}")

print("\n--- MESSUNG 3: quartett_r_soll (V019) ---")
for t in sorted(_q.values(), key=lambda x: x.bar):
    print(f"  bar {t.bar:>4}: kid={t.kid:<3} r={t.r:+.6f}")
print(f"  quartett_r_soll = "
      f"{tuple((b, round(_q[b].r, 6)) for b in sorted(_q))}")
print(f"  Summe = {sum(t.r for t in _q.values()):+.6f}")
print(f"  kids = {tuple(_q[b].kid for b in sorted(_q))} "
      f"(V018-Soll (67, 67, 73, 67))")

print("\n--- Gegenprobe: Kennzahlen ---")
h1 = [t for t in V1_aktiv if t.entry_bar < box_end]
h2 = [t for t in V1_aktiv if t.entry_bar >= box_end]
ziel = [t for t in V1_aktiv if 1021 <= t.bar <= 1287]
p9 = sum(t.r for t in V1_aktiv if 848 <= t.bar <= 1020)
print(f"  gesamt   : {len(V1_aktiv)} / {sum(t.r for t in V1_aktiv):+.6f} R")
print(f"  H1       : {len(h1)} / {sum(t.r for t in h1):+.6f} R")
print(f"  H2       : {sum(t.r for t in h2):+.6f} R")
print(f"  ZIEL(A1/A2) : {len(ziel)} / {sum(t.r for t in ziel):+.6f} R")
print(f"  P9-Beitrag  : {p9:+.6f} R")

print("\nENDE E-34i")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
