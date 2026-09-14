# -*- coding: utf-8 -*-
"""Verifikation v0.14: K67-Phasen-Override 69.87 (FAIL-LOUD, P9-lokal).

Anwender-Entscheidungen 2026-09-10:
  Q1: Phasen-Override im Adapter, KEINE neue Kanten-ID.
  Q2: Fail-Loud Niveau-Override mit strikter Phasenbindung (phase == P9).
  Q3: MITARRETIEREN - vollstaendiges Quartett (903, 980, 981, 1020).
  Q4: BEIDE Werte ausweisen (+7.902085 R v0.1 | +22.285802 R v0.14).

Prueft:
  A  Baseline unveraendert (DEFAULT_ADAPTER, P9 ohne Override).
  B  Fail-Loud: Override-Aufloesung strikt phasen- und kanten-gebunden.
  C  Engine-Lauf MIT Override (In-Memory-Patch, Engine byte-unberuehrt).
  D  Quartett-Arretierung mit den vier R-Werten.
  E  H1-Bit-Identitaet + beide H2-Benchmarks.
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
ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V014, AKTIVE_DEFAULT_SEGMENTE, AKTIVE_SEGMENTE_V014,
    BASELINE_V01_H2_R, BENCHMARK_V014_DELTA_R, BENCHMARK_V014_GESAMT_R,
    BENCHMARK_V014_H2_R, DEFAULT_ADAPTER, K67_OVERRIDE_69_87, P9,
    P9_DIRECT_69_87, P12_RESERVE, QUARTETT_V014_BARS, RESERVE_SEGMENTE,
    Hook2ZielModus, PhasenKanteInfo, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)

FEHLER = []


def pruefe(name: str, ok: bool, detail: str = "") -> None:
    """Protokolliert eine Einzelpruefung (fail-loud im Terminal)."""
    marke = "OK  " if ok else "FEHL"
    print(f"  [{marke}] {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        FEHLER.append(name)


# ------------------------------------------------------------ Engine laden
def load(name, path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), mod.__dict__)
    return mod


engine = load("ke_v014", ENGINE_P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG", cfg)
box_end = scan["box_end_bar"]
scan["box_end_bar"] = scan["n"]

print("=" * 100)
print("A -- BASELINE (DEFAULT_ADAPTER, P9 ohne Override)")
print("=" * 100)
pruefe("Default-Segmente == (P9,)", AKTIVE_DEFAULT_SEGMENTE == (P9,))
pruefe("P9.decke.hat_override() == False", not P9.decke.hat_override())
pruefe("P9-Baseline unveraendert (kid/provenienz)",
       P9.decke.kid == 67 and P9.boden.kid == 77
       and abs(P9.decke.provenienz_basis - 69.9140) < 1e-9)
pruefe("DEFAULT_ADAPTER.segmente == (P9,)",
       DEFAULT_ADAPTER.segmente == (P9,))
pruefe("v0.14-Benchmark-Register konsistent (Delta)",
       abs((BENCHMARK_V014_H2_R - BASELINE_V01_H2_R)
           - BENCHMARK_V014_DELTA_R) < 1e-6,
       f"{BENCHMARK_V014_H2_R} - {BASELINE_V01_H2_R} = "
       f"{BENCHMARK_V014_H2_R - BASELINE_V01_H2_R:.6f}")

print("\n" + "=" * 100)
print("B -- FAIL-LOUD (Phasenbindung strikt)")
print("=" * 100)
pruefe("P9_DIRECT.decke.hat_override() == True",
       P9_DIRECT_69_87.decke.hat_override())
pruefe(f"Override-Wert == {K67_OVERRIDE_69_87}",
       P9_DIRECT_69_87.decke.niveau_override == K67_OVERRIDE_69_87)
pruefe("Boden K77 OHNE Override",
       not P9_DIRECT_69_87.boden.hat_override())

# In-Phase (848..1020): Override fuer K67 wirksam
pruefe("niveau_override_bei(980, 67) == 69.87",
       ADAPTER_V014.niveau_override_bei(980, 67) == K67_OVERRIDE_69_87)
pruefe("niveau_override_bei(1020, 67) == 69.87",
       ADAPTER_V014.niveau_override_bei(1020, 67) == K67_OVERRIDE_69_87)
# Kante nicht Teil des Segments -> kein Override
pruefe("niveau_override_bei(980, 73) is None (fremde Kante)",
       ADAPTER_V014.niveau_override_bei(980, 73) is None)
# Unterhalb des Scopes / ausserhalb der Phase -> kein Override
for _k in (847, 1021, 1100, 640, 200):
    pruefe(f"niveau_override_bei({_k}, 67) is None (ausserhalb P9)",
           ADAPTER_V014.niveau_override_bei(_k, 67) is None)
# angewandte_basis faellt auf die Engine zurueck
pruefe("angewandte_basis(980, 67, 69.9687) == 69.87",
       abs(ADAPTER_V014.angewandte_basis(980, 67, 69.9687)
           - K67_OVERRIDE_69_87) < 1e-12)
pruefe("angewandte_basis(1100, 67, 69.9000) == 69.9000 (Engine)",
       abs(ADAPTER_V014.angewandte_basis(1100, 67, 69.9000) - 69.9000) < 1e-12)

# Negativproben (Fail-Loud muss werfen)
def _wirft(segmente, name: str) -> None:
    try:
        PhasenRegimeAdapter(segmente=segmente).verifiziere_niveau_overrides()
        pruefe(name, False, "kein ValueError")
    except ValueError as exc:
        pruefe(name, True, str(exc)[:78])


_wirft((PhasenSegmentEintrag(
    phasen_id="X", start_bar=848, end_bar=1020,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140,
                          niveau_override=-1.0),
    boden=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
    ziel_preis_short=68.3700, ziel_preis_long=69.9140),),
    "Fail-Loud: negativer Override abgelehnt")
_wirft((PhasenSegmentEintrag(
    phasen_id="X", start_bar=848, end_bar=1020,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140,
                          niveau_override=float("nan")),
    boden=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
    ziel_preis_short=68.3700, ziel_preis_long=69.9140),),
    "Fail-Loud: NaN-Override abgelehnt")
_wirft((PhasenSegmentEintrag(
    phasen_id="X", start_bar=848, end_bar=1020,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140,
                          niveau_override=75.0),
    boden=PhasenKanteInfo(kid=77, provenienz_basis=68.3700),
    ziel_preis_short=68.3700, ziel_preis_long=69.9140),),
    "Fail-Loud: Override ausserhalb Provenienz-Toleranz abgelehnt")
pruefe("Positivprobe: ADAPTER_V014 verifiziert ohne Exception", True,
       "beim Import erzwungen")

print("\n" + "=" * 100)
print("C -- ENGINE-LAUF (In-Memory-Patch, Engine byte-unberuehrt)")
print("=" * 100)

# --- RAM-Patch (identisch zur bewaehrten Injektion, + Override-Anbindung) --
src_datei = ENGINE_P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)

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
# Kandidat: dist + Basis gegen das WIRKSAME Niveau rechnen
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
A_M6_BASIS_K = '''        basis_k = kd.basis_bei(k)'''
A_M6_BASIS_K_NEW = '''        basis_k = _basis_wirksam(kd, k)'''
A_M6_RET = '''        b = aussen.basis_bei(k)
        dist = ((b - basis_k) if seite == "OBEN"'''
A_M6_RET_NEW = '''        b = _basis_wirksam(aussen, k)
        dist = ((b - basis_k) if seite == "OBEN"'''
A_M6_SORT = '''                if aussen is None or b > aussen.basis_bei(k):'''
A_M6_SORT_NEW = '''                if aussen is None or b > _basis_wirksam(aussen, k):'''
A_M6_SORT2 = '''                if aussen is None or b < aussen.basis_bei(k):'''
A_M6_SORT2_NEW = '''                if aussen is None or b < _basis_wirksam(aussen, k):'''
A_TP2 = '            gegen_basis = geg.basis_bei(k)\n'
A_TP2_NEW = A_TP2 + '''            _h2 = _hook.hook_2_ziel(k, richtung)
            if _h2.modus is _Hook2ZielModus.BLOCKIERT:
                stats["kein_raum"] += 1
                continue
            if _h2.modus is _Hook2ZielModus.PHASE:
                gegen_basis = _h2.ziel_preis
'''
# Kandidat-Basis (fuer TP2/SL/Rechnung) auf das wirksame Niveau heben
A_KBASIS = '            basis = kd.basis_bei(k)\n'
A_KBASIS_NEW = '            basis = _basis_wirksam(kd, k)\n'
for _n, _s in (("A_KANTEN", A_KANTEN), ("A_LOOP", A_LOOP), ("A_POOL", A_POOL),
               ("A_DIST", A_DIST), ("A_M6_OBEN", A_M6_OBEN),
               ("A_M6_UNTEN", A_M6_UNTEN), ("A_M6_BASIS", A_M6_BASIS),
               ("A_M6_BASIS_K", A_M6_BASIS_K), ("A_M6_RET", A_M6_RET),
               ("A_M6_SORT", A_M6_SORT), ("A_M6_SORT2", A_M6_SORT2),
               ("A_TP2", A_TP2), ("A_KBASIS", A_KBASIS)):
    assert src.count(_s) == 1, (_n, src.count(_s))
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


def lauf(hook, mit_patch: bool):
    ns = dict(engine.__dict__)
    ns["_hook"] = hook
    ns["_Hook2ZielModus"] = Hook2ZielModus
    exec(compile(patched_src, "<se_trades_v014>", "exec"), ns)
    if mit_patch:
        engine._se_trades = ns["_se_trades"]
        try:
            return engine._se_trades(copy.deepcopy(scan), cfg)
        finally:
            engine._se_trades = ORIG
    return ORIG(copy.deepcopy(scan), cfg)


ORIG = engine._se_trades
V0b, S0b = lauf(DEFAULT_ADAPTER, False)          # v0.1-Baseline (referenz)
V1b, S1b = lauf(DEFAULT_ADAPTER, True)           # ueber die Injektion
V1o, S1o = lauf(ADAPTER_V014, True)              # v0.14-Override

R0, R1b, R1o = (sum(t.r for t in V0b), sum(t.r for t in V1b),
                sum(t.r for t in V1o))
h1_b = [t for t in V1b if t.entry_bar < box_end]
h2_b = [t for t in V1b if t.entry_bar >= box_end]
h1_o = [t for t in V1o if t.entry_bar < box_end]
h2_o = [t for t in V1o if t.entry_bar >= box_end]

pruefe("V0-Referenz reproduziert (14 / +40.445143)",
       len(V0b) == 14 and abs(R0 - 40.445143) < 1e-5,
       f"{len(V0b)} / {R0:+.6f}")
pruefe("v0.1-Baseline ueber Injektion bit-identisch (15 / +46.866348)",
       len(V1b) == 15 and abs(R1b - 46.866348) < 1e-5,
       f"{len(V1b)} / {R1b:+.6f}")
pruefe("v0.1 H1 unveraendert (8 / +38.964262)",
       len(h1_b) == 8 and abs(sum(t.r for t in h1_b) - 38.964262) < 1e-6)
pruefe("v0.1 H2 == BASELINE_V01_H2_R",
       len(h2_b) == 7 and abs(sum(t.r for t in h2_b) - BASELINE_V01_H2_R) < 1e-5,
       f"{len(h2_b)} / {sum(t.r for t in h2_b):+.6f}")

print("\n" + "=" * 100)
print("D -- QUARTETT-ARRETIERUNG (Q3: kein Cherry-Picking)")
print("=" * 100)
print(f"  {'bar':>5} {'kid':>4} {'stufe':<16} {'entry_b':>7} {'entry':>9} "
      f"{'sl':>9} {'tp2':>9} {'R':>10}")
q = {}
for t in sorted(V1o, key=lambda x: x.bar):
    marke = "  <== Quartett" if t.bar in QUARTETT_V014_BARS else ""
    print(f"  {t.bar:>5} {t.kid:>4} {t.stufe:<16} {t.entry_bar:>7} "
          f"{t.entry:>9.4f} {t.sl:>9.4f} {t.tp2:>9.4f} {t.r:>+10.4f}{marke}")
    if t.bar in QUARTETT_V014_BARS:
        q[t.bar] = t

pruefe("Quartett vollstaendig (903, 980, 981, 1020)",
       sorted(q) == list(QUARTETT_V014_BARS), f"{sorted(q)}")
SOLL_R = {903: 4.1198, 980: 9.9877, 981: 2.6943, 1020: 3.0032}
for _b, _r in SOLL_R.items():
    _ist = q[_b].r if _b in q else float("nan")
    pruefe(f"R @Bar {_b} == {_r:+.4f}", abs(_ist - _r) < 1e-4,
           f"ist {_ist:+.4f}")
pruefe("Quartett-Summe == +19.8049 R",
       abs(sum(q[_b].r for _b in SOLL_R) - 19.8049) < 1e-4,
       f"{sum(q[_b].r for _b in SOLL_R):+.6f}")
pruefe("Quartett-Kanten: 903+980+1020=K67, 981=K73",
       q[903].kid == 67 and q[980].kid == 67 and q[1020].kid == 67
       and q[981].kid == 73)
pruefe("Stufen: 980/981/1020 = STUFE_1_IN_BAR, 903 = STUFE_2_KERZE_2",
       q[980].stufe == "STUFE_1_IN_BAR" and q[981].stufe == "STUFE_1_IN_BAR"
       and q[1020].stufe == "STUFE_1_IN_BAR"
       and q[903].stufe == "STUFE_2_KERZE_2")

print("\n" + "=" * 100)
print("E -- ENTKOPPLUNG & BEIDE BENCHMARKS (Q4)")
print("=" * 100)
pruefe("H1 mit Override bit-identisch (8 / +38.964262)",
       len(h1_o) == 8 and abs(sum(t.r for t in h1_o) - 38.964262) < 1e-6,
       f"{len(h1_o)} / {sum(t.r for t in h1_o):+.6f}")
pruefe("H2 v0.14 == BENCHMARK_V014_H2_R",
       len(h2_o) == 9 and abs(sum(t.r for t in h2_o) - BENCHMARK_V014_H2_R) < 1e-4,
       f"{len(h2_o)} / {sum(t.r for t in h2_o):+.6f}")
pruefe("Gesamt v0.14 == BENCHMARK_V014_GESAMT_R",
       len(V1o) == 17 and abs(R1o - BENCHMARK_V014_GESAMT_R) < 1e-4,
       f"{len(V1o)} / {R1o:+.6f}")
pruefe("Delta == BENCHMARK_V014_DELTA_R",
       abs((R1o - R1b) - BENCHMARK_V014_DELTA_R) < 1e-4,
       f"{R1o - R1b:+.6f}")
pruefe("BEIDE Benchmarks ausgewiesen (keiner verdraengt)",
       abs(BASELINE_V01_H2_R - 7.902085) < 1e-9
       and abs(BENCHMARK_V014_H2_R - 22.285802) < 1e-9)
pruefe("Reserve unveraendert inert (P12 nicht in V014)",
       RESERVE_SEGMENTE == (P12_RESERVE,)
       and P12_RESERVE not in AKTIVE_SEGMENTE_V014)
pruefe("H2 v0.14 bringt genau 2 Zusatztrades (9 vs 7)",
       len(h2_o) - len(h2_b) == 2)
pruefe("P9-Beitrag v0.14 == +19.8049 R",
       abs(sum(t.r for t in h2_o if 848 <= t.bar <= 1020) - 19.8049) < 1e-4,
       f"{sum(t.r for t in h2_o if 848 <= t.bar <= 1020):+.6f}")

print("\n" + "=" * 100)
if FEHLER:
    print(f"GESAMT: {len(FEHLER)} FEHLSCHLAG/-(e) -> {FEHLER}")
    sys.exit(1)
print("GESAMT: ALLE PRUEFUNGEN OK")
print("=" * 100)
