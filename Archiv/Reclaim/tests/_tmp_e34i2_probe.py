# -*- coding: utf-8 -*-
"""E-34i/2 (read-only) -- GEGENPROBE: Ursache der V019-Inertheit.

Frage: Reproduziert der Renderer-Patch allein die V019-Zahlen (23/+82.614385)?
Messung E-34i: NEIN -- er liefert V018 (17/+65.835576), ZIEL 0 Trades.

Hypothese: V019 braucht ZUSAETZLICH die four engine-level Zielzonen-Patches aus
`test/_tmp_e34_auto.py`: A_UEB1 (Ueberdehnung 0.80 segment-lokal), A_VC
(Extremum ab Segmentstart), A_M6L, A_SB -- plus die Injektion `_zv`/`_ueb`
und den `_reclaim_stufe`-Wrapper.

Hier wird der Renderer-Patch um EXAKT diese vier erweitert und erneut
gemessen. Kein PNG, kein Schreiben (Engine/Adapter unberuehrt).
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus,
    PhasenRegimeAdapter,
)

P = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUT = ROOT / "test" / "_tmp_e34i2_probe_out.txt"
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


eng = load("ke_e34i2", P)
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n

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

# ---- Die vier ZUSATZ-Patches aus _tmp_e34_auto.py -------------------------
A_UEB1 = '            if dist > cfg.max_sweep_ueberdehnung_pct:'
A_UEB1_NEW = '            if dist > _ueb(k):'
A_VC = '''        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))'''
A_VC_NEW = '''        _q0 = 0
        if _zv(k):
            _sq = _hook.aktive_phase_bei(k)
            if _sq is not None:
                _q0 = int(_sq.start_bar)
        ex_hi = float(np.max(hi[_q0:k + 1]))
        ex_lo = float(np.min(lo[_q0:k + 1]))'''
A_M6L = '''            if e is kd or not _existiert(e, k):
                continue'''
A_M6L_NEW = '''            if e is kd or not _existiert(e, k) or (
                    _zv(k) and not _lebt(e, k)):
                continue'''
A_SB = '''        if not e.ist_aktiv_bei(k):
            return False
        return e.erster_pivot_bar + 2 <= k + 1'''
A_SB_NEW = '''        if not e.ist_aktiv_bei(k):
            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == "OBEN"
                   else (lo[k] < e.basis_bei(k)))
            if not (_zv(k) and _ev):
                return False
        return e.erster_pivot_bar + 2 <= k + 1'''

PATCH = (("A_KANTEN", A_KANTEN, A_KANTEN_NEW), ("A_LOOP", A_LOOP, A_LOOP_NEW),
         ("A_POOL", A_POOL, A_POOL_NEW), ("A_DIST", A_DIST, A_DIST_NEW),
         ("A_M6_BASIS_K", A_M6_BASIS_K, A_M6_BASIS_K_NEW),
         ("A_M6_BASIS", A_M6_BASIS, A_M6_BASIS_NEW),
         ("A_M6_RET", A_M6_RET, A_M6_RET_NEW),
         ("A_M6_SORT", A_M6_SORT, A_M6_SORT_NEW),
         ("A_M6_SORT2", A_M6_SORT2, A_M6_SORT2_NEW),
         ("A_M6_OBEN", A_M6_OBEN, A_M6_OBEN_NEW),
         ("A_M6_UNTEN", A_M6_UNTEN, A_M6_UNTEN_NEW),
         ("A_TP2", A_TP2, A_TP2_NEW), ("A_KBASIS", A_KBASIS, A_KBASIS_NEW),
         ("A_UEB1", A_UEB1, A_UEB1_NEW), ("A_VC", A_VC, A_VC_NEW),
         ("A_M6L", A_M6L, A_M6L_NEW), ("A_SB", A_SB, A_SB_NEW))

patched = src
for _nm, _s, _new in PATCH:
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)

# Zielzonen-Fenster aus dem Adapter (1033..1287), P9 ausgenommen.
AUTO_A = ADAPTER_V019.segmente[1].start_bar
AUTO_B = ADAPTER_V019.segmente[-1].end_bar
P9A = ADAPTER_V019.segmente[0].start_bar
P9B = ADAPTER_V019.segmente[0].end_bar


def _zv(kk: int) -> bool:
    return AUTO_A <= kk <= AUTO_B and not (P9A <= kk <= P9B)


def _ueb(kk: int) -> float:
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS_ORIG = eng._reclaim_stufe


def _reclaim_stufe_lok(seite, kk, basis, hi, lo, cl, c):
    if _zv(kk):
        c = dataclasses.replace(c, max_sweep_ueberdehnung_pct=0.80)
    return _RS_ORIG(seite, kk, basis, hi, lo, cl, c)


ORIG = eng._se_trades
ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _reclaim_stufe_lok


def _lauf(hook):
    ns["_hook"] = hook
    exec(compile(patched, "<se_e34i2>", "exec"), ns)
    eng._se_trades = ns["_se_trades"]
    try:
        return eng._se_trades(copy.deepcopy(scan), cfg)
    finally:
        eng._se_trades = ORIG


print("=" * 100)
print("E-34i/2 GEGENPROBE: Renderer-Patch + 4 E-34-Zielzonen-Patches")
print("=" * 100)
print(f"Zielzonen-Fenster: {AUTO_A}..{AUTO_B} (P9 {P9A}..{P9B} ausgenommen)")

# --- HAZARD-TEST: un-gegatetes _zv auf die v0.1-BASIS (DEFAULT_ADAPTER) ----
_basis, _ = _lauf(DEFAULT_ADAPTER)
print(f"\n[HAZARD] DEFAULT_ADAPTER (v0.1-Basis) unter UN-gegatetem _zv:")
print(f"   V1_basis = {len(_basis)} / {sum(t.r for t in _basis):+.6f} R "
      f"(Soll/arretiert: 14 / +47.815697) -> "
      f"{'UNVERAENDERT' if len(_basis) == 14 and abs(sum(t.r for t in _basis) - 47.815697) < 1e-5 else 'VERAENDERT (GATE-ZWANG!)'}")

# --- HAZARD-TEST 2: un-gegatetes Patchset auf den ALT-Modus V018 -----------
_v18, _ = _lauf(ADAPTER_V015)
print(f"\n[HAZARD] ADAPTER_V015 (V018) unter UN-gegatetem Zielzonen-Patchset:")
print(f"   V018 = {len(_v18)} / {sum(t.r for t in _v18):+.6f} R "
      f"(abgenommen: 17 / +65.835576) -> "
      f"{'UNVERAENDERT' if len(_v18) == 17 and abs(sum(t.r for t in _v18) - 65.835576) < 1e-5 else 'VERAENDERT (QUELLTEXT-GATE ZWINGEND!)'}")

setups, _st = _lauf(ADAPTER_V019)

h1 = [t for t in setups if t.entry_bar < box_end]
h2 = [t for t in setups if t.entry_bar >= box_end]
ziel = [t for t in setups if 1021 <= t.bar <= 1287]
print(f"\ngesamt : {len(setups)} / {sum(t.r for t in setups):+.6f} R "
      f"(Soll V019: 23 / +82.614385)")
print(f"H1     : {len(h1)} / {sum(t.r for t in h1):+.6f} R "
      f"(Soll 8 / +38.919584)")
print(f"H2     : {sum(t.r for t in h2):+.6f} R (Soll +43.694801)")
print(f"ZIEL   : {len(ziel)} / {sum(t.r for t in ziel):+.6f} R "
      f"(Soll 6 / +16.778809)")

print("\n--- ZIEL-Trades (1021..1287) ---")
for t in sorted(ziel, key=lambda x: x.bar):
    print(f"  bar {t.bar:>4} kid {t.kid:>3} {t.richtung:5} "
          f"entry_bar {t.entry_bar:>4} r {t.r:+.6f}")

print("\n--- Alle Trades ---")
for t in sorted(setups, key=lambda x: x.bar):
    print(f"  bar {t.bar:>4} kid {t.kid:>3} {t.richtung:5} "
          f"entry_bar {t.entry_bar:>4} r {t.r:+.6f}")

treffer = (len(setups) == 23 and abs(sum(t.r for t in setups) - 82.614385) < 1e-4
           and len(ziel) == 6
           and abs(sum(t.r for t in ziel) - 16.778809) < 1e-4)
print(f"\nURSACHE BESTAETIGT (V019 braucht die 4 Zusatz-Patches): {treffer}")
print("\nENDE E-34i/2")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
