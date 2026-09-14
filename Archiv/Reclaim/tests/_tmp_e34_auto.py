# -*- coding: utf-8 -*-
"""E-34 (read-only, AUG) -- ENDOGENE Segmentbildung, ohne Zielwissen.

Frage: lassen sich die Phasengrenzen AUS DEM MARKT ableiten -- ohne jedes
Bar- oder Kanten-Literal aus der Anwender-Vorgabe oder der Handliste?

Zielfreie, kausale Regel ("aeusserste lebende Linie"):

    lebt(e, k)  <=>  letzter BESTAETIGTER Docht b (b + 2 <= k) >= k - LIVE
    decke(k)    = OBEN-Linie mit maximaler Basis unter den lebenden
    boden(k)    = UNTEN-Linie mit minimaler Basis unter den lebenden

    Segmentgrenze = Bar, an dem sich das Paar (decke_kid, boden_kid) aendert.

`LIVE` = cfg.wall_live_bars (96) -- arretiert (2026-09-08), NICHT aus der
Zielvorgabe.  Bestaetigung +2 = Pivot-Kausalitaet der Engine (P1).
KEIN Lookahead: ausschliesslich Dochte b + 2 <= k.

Der einzige uebernommene Wert ist P9 (848..1020) -- die ARRETIERTE v0.1-Phase
(+5.4212 R, §69).  Sie bleibt unveraendert; die Automatik beginnt bei
P9.end_bar + 1 (abgeleitet, kein Literal).

Varianten: Zusammenfassung benachbarter Segmente, wenn
   len < MIN_BARS   ODER   beide Niveaus innerhalb touch_band_pct (0.12)

Aufruf: python test/_tmp_e34_auto.py <RAW|MIN4|MIN8|MIN16|MIN24|MIN48|MIN<n>>

`MIN_BARS` ist seit E-34b ein FREIER PARAMETER fuer Reihenuntersuchungen:
jede ganze Zahl ist zulaessig (`MIN25`, `MIN47`, `MIN49`, ...).  `RAW` ist
gleichbedeutend mit `MIN0`.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    Hook2ZielModus, P9_BODEN_RECLAIM, PhasenKanteInfo, PhasenRegimeAdapter,
    PhasenSegmentEintrag,
)

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
H1_H2 = 644
Z0, Z1 = 1021, 1287           # NUR fuer die Berichterstattung (Zielzone)

_NAMED = {"RAW": 0, "MIN4": 4, "MIN8": 8, "MIN16": 16, "MIN24": 24,
          "MIN48": 48}
VAR = (sys.argv[1] if len(sys.argv) > 1 else "RAW").upper()


def _min_bars_aus(var: str) -> int:
    """`MIN_BARS`-Parameter aufloesen -- benannte Varianten ODER `MIN<n>`.

    Args:
        var: Argument von der Kommandozeile (z. B. ``"RAW"``, ``"MIN49"``).

    Returns:
        Die Mindestsegmentlaenge in Bars (>= 0).

    Raises:
        SystemExit: Wenn das Argument kein gueltiger Parameter ist.
    """
    if var in _NAMED:
        return _NAMED[var]
    m = re.fullmatch(r"MIN(\d+)", var)
    if m:
        return int(m.group(1))
    raise SystemExit(f"unbekannter MIN_BARS-Parameter: {var!r}")


MIN_BARS = _min_bars_aus(VAR)

# Optionaler Audit-Trace: `--trace <bar>` protokolliert die Kanten- und
# Pool-Zustaende genau an diesem Signal-Bar (rein lesend, §E-34c Schritt 1).
TRACE_BAR: Optional[int] = None
if "--trace" in sys.argv:
    TRACE_BAR = int(sys.argv[sys.argv.index("--trace") + 1])

# Varianten-Schalter fuer E-34d (Schritt 1/2): je Schalter ein isolierter
# Eingriff, damit die H1-Invarianz einzeln nachweisbar bleibt.
#   --poola   (a) schlafende Linien belegen keine Pool-Raenge (pos), GLOBAL
#   --poolalok(a) wie oben, aber NUR im automatisch erzeugten Fenster (_zv)
#   --poolhart  Entwurf E-34e: behalten nur `lebt AND dist >= 0`, lokal (_zv)
#   --seglast (c) Segment-Etiketten beim Verschmelzen aus dem LETZTEN Stueck
_FLAG_ZU_MODUS = {"--poola": "global", "--poolalok": "lokal",
                  "--poolhart": "hart"}
POOL_A_MODE: str = ""
for _fl, _m in _FLAG_ZU_MODUS.items():
    if _fl in sys.argv:
        POOL_A_MODE = _m
POOL_HART_GLOBAL: bool = "--poolhartgl" in sys.argv
SEG_LAST: bool = "--seglast" in sys.argv
_VAR_TAG = ("".join(t for t, on in (("_pa", POOL_A_MODE == "global"),
                                    ("_pal", POOL_A_MODE == "lokal"),
                                    ("_ph", POOL_A_MODE == "hart"
                                     and not POOL_HART_GLOBAL),
                                    ("_phg", POOL_A_MODE == "hart"
                                     and POOL_HART_GLOBAL),
                                    ("_sl", SEG_LAST)) if on))
_SUFFIX = ("" if TRACE_BAR is None else f"_trace{TRACE_BAR}") + _VAR_TAG

OUT = ROOT / "test" / f"_tmp_e34_auto_{VAR}{_SUFFIX}_out.txt"
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

spec = importlib.util.spec_from_file_location("eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
scan["box_end_bar"] = n
alle = list(scan["edges"]) + list(scan["seeds"])
katalog = {e.kid: e for e in alle}
LIVE = cfg.wall_live_bars
BAND = cfg.touch_band_pct
P9A, P9B = P9_BODEN_RECLAIM.start_bar, P9_BODEN_RECLAIM.end_bar


def _lebt_kausal(e, k: int) -> bool:
    """Streng kausal: nur BESTAETIGTE Dochte (b + 2 <= k)."""
    b = [bb for bb, _ in e.wicks if bb + 2 <= k]
    return bool(b) and max(b) >= k - LIVE


def ecken(k: int) -> Tuple[Optional[int], Optional[int]]:
    """(decke_kid, boden_kid) = aeusserste lebende Linien, kausal."""
    oben, unten = [], []
    for e in alle:
        if not _lebt_kausal(e, k):
            continue
        (oben if e.seite == "OBEN" else unten).append(e)
    o = max(oben, key=lambda e: e.basis_bei(k)) if oben else None
    u = min(unten, key=lambda e: e.basis_bei(k)) if unten else None
    return (o.kid if o else None), (u.kid if u else None)


# ---------------------------------------------------------- A. Wechselpunkte
print("=" * 112)
print(f"E-34 ENDOGENE SEGMENTBILDUNG -- {VAR}   (AUG, n = {n})")
print("=" * 112)
print(f"Engine {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"Regel: aeusserste LEBENDE Linie, kausal (bestaetigte Dochte b+2<=k); "
      f"LIVE = {LIVE} (arretiert), BAND = {BAND} %")

wechsel: List[Tuple[int, Optional[int], Optional[int], float, float]] = []
vor: Tuple[Optional[int], Optional[int]] = (None, None)
for k in range(2, n):
    cur = ecken(k)
    if cur != vor:
        o = katalog.get(cur[0]) if cur[0] is not None else None
        u = katalog.get(cur[1]) if cur[1] is not None else None
        wechsel.append((k, cur[0], cur[1],
                        float(o.basis_bei(k)) if o else 0.0,
                        float(u.basis_bei(k)) if u else 0.0))
        vor = cur

print("")
print("A. WECHSELPUNKTE der zielfreien Regel (Auszug ab Bar 600):")
print(f"   {'Bar':>5}  {'decke':<22}{'boden':<22}")
for (k, ko, ku, vo, vu) in wechsel:
    if k < 600:
        continue
    so = "-" if ko is None else f"K{ko:<3} {vo:.4f}"
    su = "-" if ku is None else f"K{ku:<3} {vu:.4f}"
    print(f"   {k:>5}  {so:<22}{su:<22}")

print("")
print("B. VALIDIERUNG gegen die ARRETIERTEN (ziel-freien) Definitionen:")
print(f"   arretiert P9        : {P9A}..{P9B}  decke K"
      f"{P9_BODEN_RECLAIM.decke.kid} boden K{P9_BODEN_RECLAIM.boden.kid}")
print("   arretiert P12_RESERVE: 1171..1272 decke K73 boden K82")
print(f"   Regel {P9A}..{P9B}: " + str(
    [(k, ko, ku) for (k, ko, ku, _a, _b) in wechsel if P9A <= k <= P9B]))
print("   Regel 1171..1272: " + str(
    [(k, ko, ku) for (k, ko, ku, _a, _b) in wechsel if 1171 <= k <= 1272]))

# --------------------------------------------------- C. Segmentbildung
START = P9B + 1                      # = 1021, ABGELEITET aus dem arretierten P9
roh: List[List] = []                 # [a, b, decke_kid, boden_kid]
for (k, ko, ku, vo, vu) in wechsel:
    if k < START or ko is None or ku is None:
        continue
    if roh:
        roh[-1][1] = k - 1
    roh.append([k, n - 1, ko, ku])
if not roh:
    raise SystemExit("keine Segmente erzeugt")


def _nah(p: List, s: List) -> bool:
    """Beide Grenzniveaus praktisch gleich (<= touch_band_pct, arretiert)."""
    ko1, ko2 = katalog[p[2]].basis_bei(p[0]), katalog[s[2]].basis_bei(s[0])
    ku1, ku2 = katalog[p[3]].basis_bei(p[0]), katalog[s[3]].basis_bei(s[0])
    return (abs(ko2 - ko1) / ko1 * 100.0 <= BAND
            and abs(ku2 - ku1) / ku1 * 100.0 <= BAND)


def zusammenfassen(segs: List[List], min_bars: int) -> List[List]:
    """Verschmelzen: zu kurz ODER Grenzen praktisch unveraendert.

    ``SEG_LAST`` (Kandidat c) uebernimmt beim Ketten-Verschmelzen die
    Grenz-Kanten aus dem **letzten** Teilstueck statt sie am Start
    einzufrieren.
    """
    out: List[List] = []
    for s in segs:
        if out and ((s[1] - s[0] + 1) < min_bars or _nah(out[-1], s)):
            out[-1][1] = s[1]
            if SEG_LAST:
                out[-1][2] = s[2]
                out[-1][3] = s[3]
        else:
            out.append(list(s))
    return out


SEGS = zusammenfassen(roh, MIN_BARS)
print("")
print(f"C. SEGMENTE (MIN_BARS = {MIN_BARS}):")
for i, (a, b, ko, ku) in enumerate(SEGS):
    print(f"   A{i + 1:<3} {a:>5}..{b:<5} ({b - a + 1:>4} Bars)  "
          f"decke K{ko:<3} {katalog[ko].basis_bei(a):.4f}   "
          f"boden K{ku:<3} {katalog[ku].basis_bei(a):.4f}")

segmente: List[PhasenSegmentEintrag] = [P9_BODEN_RECLAIM]
for i, (a, b, ko, ku) in enumerate(SEGS):
    o, u = katalog[ko], katalog[ku]
    segmente.append(PhasenSegmentEintrag(
        phasen_id=f"A{i + 1}", start_bar=int(a), end_bar=int(b),
        decke=PhasenKanteInfo(kid=int(ko),
                              provenienz_basis=float(o.basis_bei(a))),
        boden=PhasenKanteInfo(kid=int(ku),
                              provenienz_basis=float(u.basis_bei(a))),
        ziel_preis_short=float(u.basis_bei(a)),
        ziel_preis_long=float(o.basis_bei(a))))

adapter = PhasenRegimeAdapter(segmente=tuple(segmente))
AUTO_A, AUTO_B = SEGS[0][0], SEGS[-1][1]


def _zv(kk: int) -> bool:
    """Zielzonen-Fenster: automatisch = im automatisch erzeugten Bereich.

    Kein Bar-Literal aus der Vorgabe.  P9 (arretiert) wird NICHT
    segment-lokal geschaltet -- dort ist nichts zu heilen.
    """
    return AUTO_A <= kk <= AUTO_B and not (P9A <= kk <= P9B)


def _ueb(kk: int) -> float:
    """Ueberdehnungs-Schranke: 0.80 nur im automatischen Bereich."""
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS_ORIG = eng._reclaim_stufe


def _reclaim_stufe_lok(seite, kk, basis, hi, lo, cl, c):
    """Wrapper: Schranke 0.80 segment-lokal (sonst arretierte cfg)."""
    if _zv(kk):
        c = dataclasses.replace(c, max_sweep_ueberdehnung_pct=0.80)
    return _RS_ORIG(seite, kk, basis, hi, lo, cl, c)


# ------------------------------------------------- RAM-Patch (wie E-33)
src_datei = ENGINE_P.read_text(encoding="utf-8")
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
            _CUR[0] = k
            _CUR[1] = richtung
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
                _hit(_CUR, "vakuum")
                continue
            if _h2.modus is _Hook2ZielModus.PHASE:
                gegen_basis = _h2.ziel_preis
'''
A_KBASIS = '            basis = kd.basis_bei(k)\n'
A_KBASIS_NEW = '            basis = _basis_wirksam(kd, k)\n'
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

A_POOLA = '''        if _freigabe_kid is not None:
            pool = [e for e in pool if e.kid != _freigabe_kid]'''
A_POOLA_NEW = A_POOLA + '''
        if _POOL_A(k):
            pool = [e for e in pool
                    if not (_dist(e) < 0.0 and not _lebt(e, k))]
        if _POOL_HART(k):
            pool = [e for e in pool
                    if _lebt(e, k) and _dist(e) >= 0.0]'''

A_TRACE = '            kd = _kandidat(richtung, k, sweep_px)'
TRACE_SNIPPET = '''
            if _TRACE_BAR is not None and k == _TRACE_BAR:
                _sd = ("OBEN" if richtung == "SHORT" else "UNTEN")
                _segk = _hook.aktive_phase_bei(k)
                print("   [TRACE] bar %d %s freigabe_kid=%s seg=%s"
                      % (k, richtung, _freigabe_kid,
                         None if _segk is None else _segk.phasen_id))
                _zeilen = []
                for _e in seite_edges[_sd]:
                    _zeilen.append((
                        _e.kid, _basis_wirksam(_e, k), _e.basis_bei(k),
                        _existiert(_e, k), _lebt(_e, k), _etabliert(_e, k),
                        _e.touch_conf(k), _e.ist_prim_anker,
                        k - _e.erster_pivot_bar,
                        k - _e.letzter_touch_conf(k)))
                for _z in sorted(_zeilen, key=lambda t: -t[1]):
                    print("      K%-3d wirksam=%9.4f basis=%9.4f exist=%-5s "
                          "lebt=%-5s etab=%-5s touch=%d anker=%-5s alter=%4d "
                          "letzter_conf=%3d" % _z)
                _pool = []
                for _e in seite_edges[_sd]:
                    if not _existiert(_e, k):
                        continue
                    if not ((_e.ist_prim_anker and k >= _e.promoviert_ab_bar)
                            or _e.touch_conf(k) >= 2):
                        continue
                    if not _etabliert(_e, k):
                        continue
                    _pool.append(_e)
                print("      POOL (vor Freigabe-Filter): %s"
                      % sorted("K%d" % e.kid for e in _pool))
                if _freigabe_kid is not None:
                    _pool = [e for e in _pool if e.kid != _freigabe_kid]
                print("      POOL (nach Filter):         %s"
                      % sorted("K%d" % e.kid for e in _pool))
                print("      KANDIDAT = %s"
                      % (None if kd is None else
                         "K%d wirksam=%.4f" % (kd.kid, _basis_wirksam(kd, k))))
'''

PATCH = [("A_KANTEN", A_KANTEN, A_KANTEN_NEW), ("A_LOOP", A_LOOP, A_LOOP_NEW),
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
         ("A_M6L", A_M6L, A_M6L_NEW), ("A_SB", A_SB, A_SB_NEW)]
patched = src
for _nm, _s, _new in PATCH:
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)

_n_stat = len(re.findall(r'stats\["(\w+)"\] \+= 1', patched))
patched = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', patched)

if TRACE_BAR is not None:
    assert patched.count(A_TRACE) == 1, patched.count(A_TRACE)
    patched = patched.replace(A_TRACE, A_TRACE + "\n" + TRACE_SNIPPET)

if POOL_A_MODE:
    assert patched.count(A_POOLA) == 1, patched.count(A_POOLA)
    patched = patched.replace(A_POOLA, A_POOLA_NEW)


def _pool_a_aktiv(kk: int) -> bool:
    """Kandidat (a): schlafende Linien belegen keine Pool-Raenge."""
    return POOL_A_MODE == "global" or (POOL_A_MODE == "lokal" and _zv(kk))


def _pool_hart_aktiv(kk: int) -> bool:
    """Entwurf E-34e: nur `lebt AND dist >= 0` behalten (strenger Filter)."""
    return (POOL_A_MODE == "hart"
            and (POOL_HART_GLOBAL or _zv(kk)))

HITS: List[Tuple[int, str, str]] = []
ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_hook"] = adapter
ns["_CUR"] = [0, "?"]
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_TRACE_BAR"] = TRACE_BAR
ns["_POOL_A"] = _pool_a_aktiv
ns["_POOL_HART"] = _pool_hart_aktiv
ns["_reclaim_stufe"] = _reclaim_stufe_lok


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
(ROOT / "test" / f"_tmp_e34_patched_{VAR}.py").write_text(
    patched, encoding="utf-8", newline="\n")
exec(compile(patched, "<se_e34>", "exec"), ns)  # noqa: S102

t1 = time.time()
setups, stats = ns["_se_trades"](copy.deepcopy(scan), cfg)
t_lauf = time.time() - t1

HI = scan["d"]["high"].to_numpy(float)
LO = scan["d"]["low"].to_numpy(float)
CL = scan["d"]["close"].to_numpy(float)
_tr = np.maximum(HI[1:] - LO[1:],
                 np.maximum(np.abs(HI[1:] - CL[:-1]), np.abs(LO[1:] - CL[:-1])))
_tr = np.concatenate([[HI[1] - LO[1]], _tr])


def kz(ss: List) -> Dict[str, float]:
    if not ss:
        return {"n": 0, "R": 0.0, "USDn": 0.0, "Qstop": 0.0}
    r = [float(s.r) for s in ss]
    usd = [float(s.r) * abs(float(s.sl) - float(s.entry)) for s in ss]
    return {"n": len(ss), "R": sum(r), "USDn": sum(usd) / len(ss),
            "Qstop": sum(1 for x in r if x <= -1.0 + 1e-9) / len(ss)}


def schn(name: str) -> List:
    if name == "H1":
        return [s for s in setups if int(s.entry_bar) < H1_H2]
    if name == "H2":
        return [s for s in setups if int(s.entry_bar) >= H1_H2]
    if name == "ZIEL":
        return [s for s in setups if Z0 <= int(s.bar) <= Z1]
    return list(setups)


print("")
print(f"D. ERGEBNIS ({VAR}, {len(setups)} Setups, {t_lauf:.1f}s; "
      f"Auto-Fenster {AUTO_A}..{AUTO_B})")
print(f"   {'Schnitt':<8}{'n':>5}{'R':>14}{'USD/Tr':>11}{'Q_stop':>9}")
for name in ("gesamt", "H1", "H2", "ZIEL"):
    k = kz(schn(name))
    print(f"   {name:<8}{k['n']:>5}{k['R']:>+14.6f}{k['USDn']:>+11.4f}"
          f"{k['Qstop']:>9.3f}")

print("")
print("   ABLEHNUNGEN (Zielzone):")
c = Counter(k for (kk, _r, k) in HITS if Z0 <= kk <= Z1)
print("      " + str(dict(c)))

if TRACE_BAR is not None:
    print("")
    print(f"   AUDIT-TRACE bar {TRACE_BAR} -- Ablehnungsgruende:")
    for (kk, rr, key) in HITS:
        if kk == TRACE_BAR:
            print(f"      {rr:<6} {key}")

print("")
print("   SETUPS (Signal-Bar, Entry-Bar, Richtung, Kante, R):")
for s in sorted(setups, key=lambda x: int(x.bar)):
    tag = " H2" if int(s.entry_bar) >= H1_H2 else ""
    if Z0 <= int(s.bar) <= Z1:
        tag += " ZIEL"
    print(f"      bar {int(s.bar):>5} entry {int(s.entry_bar):>5} "
          f"{s.richtung:<6} K{int(s.kid):<4} R {float(s.r):>+10.5f}{tag}")

print("")
print(f"ENDE E-34 {VAR}")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
