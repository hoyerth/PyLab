# -*- coding: utf-8 -*-
"""E-33 (read-only, AUG) -- ZIELERREICHUNG Zielzone: V-C / V-D.

Aufruf: python test/_tmp_e33_aug.py <variante>

Reproduziert den PRODUKTIONS-Pfad (Renderer V018): scan["box_end_bar"] = n,
Adapter-Hooks in `_se_trades`, Partition ueber `entry_bar` bei 644.

Varianten:
  V018   (P9)                            -- arretierte Referenz
  VC     (P9) + Q29 phasenlokal
  VD1    (P9) + M6-Blocker nur lebende Wand
  VD2    (P9) + Ueberdehnung 0.60 -> 0.80
  VD4    (P9) + RECLAIM_AT_OPENING (Ereignis schlaegt Schlafstatus)
  Z_FULL (P9, 1021..1287)
  Z_10   (P9, 1021..1170)
  Z_12   (P9, 1171..1287)
  Z_FULL_VD  (P9, 1021..1287) + VC + VD1 + VD2 + VD4
  Z_1012_VD  (P9, 1021..1170, 1171..1287) + VC + VD1 + VD2 + VD4
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
    AKTIVE_SEGMENTE_V015, Hook2ZielModus, P9, P9_BODEN_RECLAIM,
    PhasenKanteInfo, PhasenRegimeAdapter, PhasenSegmentEintrag,
)

# Produktions-Adapter der arretierten V018-Generation (§72/§73):
# ADAPTER_V015 = P9_BODEN_RECLAIM (K67-Override 69.87 + Boden-Literal 68.40).
P9P = AKTIVE_SEGMENTE_V015

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
H1_H2 = 644
H2B = 966
Z0, Z1 = 1021, 1287

VAR = (sys.argv[1] if len(sys.argv) > 1 else "V018")
DBGB = {1072, 1073, 1122, 1123, 1172, 1173}

OUT = ROOT / "test" / f"_tmp_e33_aug_{VAR}_out.txt"
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

# ------------------------------------------------------- Engine + Scan
spec = importlib.util.spec_from_file_location("eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

cfg0 = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg0)
n = scan["n"]
box_end = scan["box_end_bar"]
scan["box_end_bar"] = n                 # Voll-Lauf (Produktionspfad)
alle_kanten = list(scan["edges"]) + list(scan["seeds"])

HI = scan["d"]["high"].to_numpy(float)
LO = scan["d"]["low"].to_numpy(float)
CL = scan["d"]["close"].to_numpy(float)


def _kante(kid: int):
    return next(e for e in alle_kanten if e.kid == kid)


# --------------------------------------------------- Segment-Definitionen
def _seg(pid: str, a: int, b: int, decke_kid: int,
         boden_kid: int) -> PhasenSegmentEintrag:
    dk, bo = _kante(decke_kid), _kante(boden_kid)
    assert dk.seite == "OBEN" and bo.seite == "UNTEN", (pid, dk.seite, bo.seite)
    ref = min(max(a, 0), n - 1)
    return PhasenSegmentEintrag(
        phasen_id=pid, start_bar=a, end_bar=b,
        decke=PhasenKanteInfo(kid=decke_kid,
                              provenienz_basis=float(dk.basis_bei(ref))),
        boden=PhasenKanteInfo(kid=boden_kid,
                              provenienz_basis=float(bo.basis_bei(ref))),
        ziel_preis_short=float(bo.basis_bei(ref)),
        ziel_preis_long=float(dk.basis_bei(ref)))


SEG_FULL = _seg("ZIEL", Z0, Z1, 73, 82)
SEG_10 = _seg("P10", Z0, 1170, 73, 82)
SEG_12 = _seg("P12", 1171, Z1, 73, 82)
# Spielart: Phasenboden = Monatstief K85 (67.4200, Erstd­ocht @1075) statt K82.
SEG_10B = _seg("P10b", Z0, 1170, 73, 85)
SEG_12B = _seg("P12b", 1171, Z1, 73, 85)

# --- Variantenmatrix --------------------------------------------------------
#        segmente                    VC     M6     UEB    SB
SW: Dict[str, Tuple[Tuple, bool, bool, bool, bool, bool]] = {
    "V018":          (P9P,                     False, False, False, False, False),
    "VC":            (P9P,                     True,  False, False, False, False),
    "VD1":           (P9P,                     False, True,  False, False, False),
    "VD2":           (P9P,                     False, False, True,  False, False),
    "VD4":           (P9P,                     False, False, False, True,  False),
    "VD_ALL":        (P9P,                     True,  True,  True,  True,  False),
    "Z_FULL":        (P9P + (SEG_FULL,),       False, False, False, False, False),
    "Z_10":          (P9P + (SEG_10,),         False, False, False, False, False),
    "Z_12":          (P9P + (SEG_12,),         False, False, False, False, False),
    "Z_FULL_VD":     (P9P + (SEG_FULL,),       True,  True,  True,  True,  False),
    "Z_1012_VD":     (P9P + (SEG_10, SEG_12),  True,  True,  True,  True,  False),
    "Z_FULL_LOKAL":  (P9P + (SEG_FULL,),       True,  True,  True,  True,  True),
    "Z_1012_LOKAL":  (P9P + (SEG_10, SEG_12),  True,  True,  True,  True,  True),
    "Z_B85_LOKAL":   (P9P + (SEG_10B, SEG_12B), True, True,  True,  True,  True),
    "Z_B85_VD":      (P9P + (SEG_10B, SEG_12B), True, True,  True,  True,  False),
    "Z_12_LOKAL":    (P9P + (SEG_12,),         True,  True,  True,  True,  True),
    "Z_10_LOKAL":    (P9P + (SEG_10,),         True,  True,  True,  True,  True),
}
assert VAR in SW, f"unbekannte Variante {VAR!r}; erlaubt {list(SW)}"
SEGMENTE, VC, VM6, VUEB, VSB, VLOK = SW[VAR]

adapter = PhasenRegimeAdapter(segmente=tuple(SEGMENTE))
cfg = cfg0          # Ueberdehnung wird per `_ueb` gesteuert (global oder lokal)


def _zv(kk: int) -> bool:
    """Zielzonen-Fenster (segment-lokale Schalterwirkung)."""
    return Z0 <= kk <= Z1


def _ueb(kk: int) -> float:
    """Wirksame Ueberdehnungs-Schranke am Bar kk."""
    if VUEB and (not VLOK or _zv(kk)):
        return 0.80
    return cfg0.max_sweep_ueberdehnung_pct


_RS_ORIG = eng._reclaim_stufe


def _reclaim_stufe_lok(seite, kk, basis, hi, lo, cl, c):
    """Wrapper: Ueberdehnung segment-lokal (sonst arretierte cfg)."""
    if VUEB and (not VLOK or _zv(kk)):
        c = dataclasses.replace(c, max_sweep_ueberdehnung_pct=0.80)
    return _RS_ORIG(seite, kk, basis, hi, lo, cl, c)

# ------------------------------------------------- RAM-Patch (Produktionspfad)
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

PATCH = [("A_KANTEN", A_KANTEN, A_KANTEN_NEW), ("A_LOOP", A_LOOP, A_LOOP_NEW),
         ("A_POOL", A_POOL, A_POOL_NEW), ("A_DIST", A_DIST, A_DIST_NEW),
         ("A_M6_BASIS_K", A_M6_BASIS_K, A_M6_BASIS_K_NEW),
         ("A_M6_BASIS", A_M6_BASIS, A_M6_BASIS_NEW),
         ("A_M6_RET", A_M6_RET, A_M6_RET_NEW),
         ("A_M6_SORT", A_M6_SORT, A_M6_SORT_NEW),
         ("A_M6_SORT2", A_M6_SORT2, A_M6_SORT2_NEW),
         ("A_M6_OBEN", A_M6_OBEN, A_M6_OBEN_NEW),
         ("A_M6_UNTEN", A_M6_UNTEN, A_M6_UNTEN_NEW),
         ("A_TP2", A_TP2, A_TP2_NEW), ("A_KBASIS", A_KBASIS, A_KBASIS_NEW)]
patched = src
for _nm, _s, _new in PATCH:
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)

# ---- E-33-Zusaetze auf den bereits gepatchten Quelltext --------------------
_n_stat = len(re.findall(r'stats\["(\w+)"\] \+= 1', patched))
patched = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', patched)

ZUS: List[Tuple[str, str, str]] = [
    ("Z_CUR", '''            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            _seite: KantenSeite = ("OBEN" if richtung == "SHORT" else "UNTEN")''',
     '''            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            _seite: KantenSeite = ("OBEN" if richtung == "SHORT" else "UNTEN")
            _CUR[0] = k
            _CUR[1] = richtung'''),
    ("Z_VC", '''        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))''',
     '''        _q0 = 0
        if _VC and (not _LOK or _zv(k)):
            _sq = _hook.aktive_phase_bei(k)
            if _sq is not None:
                _q0 = int(_sq.start_bar)
        ex_hi = float(np.max(hi[_q0:k + 1]))
        ex_lo = float(np.min(lo[_q0:k + 1]))'''),
    ("Z_M6", '''            if e is kd or not _existiert(e, k):
                continue''',
     '''            if e is kd or not _existiert(e, k) or (
                    _VM6 and (not _LOK or _zv(k)) and not _lebt(e, k)):
                continue'''),
    ("Z_SB", '''        if not e.ist_aktiv_bei(k):
            return False
        return e.erster_pivot_bar + 2 <= k + 1''',
     '''        if not e.ist_aktiv_bei(k):
            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == "OBEN"
                   else (lo[k] < e.basis_bei(k)))
            if not (_VSB and (not _LOK or _zv(k)) and _ev):
                return False
        return e.erster_pivot_bar + 2 <= k + 1'''),
    ("Z_UEB", 'cfg.max_sweep_ueberdehnung_pct', '_ueb(k)'),
]
for _nm, _s, _new in ZUS:
    assert patched.count(_s) >= 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)

# ---- Zieldiagnose (nur fuer _DBGB) -----------------------------------------
_DBGTXT = ('if _DBG is not None and k in _DBGB: '
           '_DBG.append("   bar %d %s %s" % (k, richtung, "%s"))')


def _dbg_vor(key: str, text: str, indent: int) -> None:
    """Setzt eine DBG-Zeile vor jede Fundstelle (exakte Einrueckung).

    Der Anker traegt ein fuehrendes ``\\n``, damit eine Zeile mit MEHR
    Einrueckung nicht als Teilstring-Treffer die Zeile zerschneidet.
    """
    global patched
    pad = " " * indent
    zeile = pad + ('if _DBG is not None and k in _DBGB: _DBG.append('
                   '"   bar %d %s ' + text + '" % (k, richtung))')
    anker = "\n" + pad + '_hit(_CUR, "' + key + '")'
    assert anker in patched, anker
    patched = patched.replace(
        anker, "\n" + zeile + "\n" + pad + '_hit(_CUR, "' + key + '")')


_dbga = [("kein_raum", "kein_raum", 20),
         ("kein_raum", "kein_raum", 16),
         ("kein_gegner", "kein_gegner (keine Gegenkante)", 16),
         ("zyklus_blockiert", "Zyklus-Sperre", 16),
         ("f3", "F3-Frische", 16),
         ("vakuum", "REGIME-VAKUUM", 16)]
for _a, _t, _i in _dbga:
    _dbg_vor(_a, _t, _i)

Z2: List[Tuple[str, str, str]] = [
    ("Z_DBG_KD", '''            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue''',
     '''            kd = _kandidat(richtung, k, sweep_px)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s sweep=%.4f kd=%s" % (
                    k, richtung, sweep_px,
                    "None" if kd is None else "K%d b=%.4f" % (
                        kd.kid, _basis_wirksam(kd, k))))
            if kd is None:
                continue'''),
    ("Z_DBG_M6", '''            if blk is not None:
                _hit(_CUR, "blocker")''',
     '''            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s M6-Blocker=%s" % (
                    k, richtung, "None" if blk is None else "K%d" % blk.kid))
            if blk is not None:
                _hit(_CUR, "blocker")'''),
    ("Z_DBG_Q29", '''            if not _im_aussenquartil(richtung, k, sweep_px):
                _hit(_CUR, "quartil_blockiert")''',
     '''            _q_ok = _im_aussenquartil(richtung, k, sweep_px)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s Q29 -> %s" % (
                    k, richtung, "durch" if _q_ok else "SPERRE"))
            if not _q_ok:
                _hit(_CUR, "quartil_blockiert")'''),
    ("Z_DBG_ST", '''            if stufe_n == 0:
                continue''',
     '''            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s Stufe=%d" % (k, richtung, stufe_n))
            if stufe_n == 0:
                continue'''),
    ("Z_DBG_GEO", '''            entry = float(op[entry_bar])
            tp2 = gegen_basis''',
     '''            entry = float(op[entry_bar])
            tp2 = gegen_basis
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s GEO sl=%.4f e=%.4f poc=%.4f "
                            "tp2=%.4f basis=%.4f" % (
                                k, richtung, sl, entry, poc, tp2, basis))'''),
    ("Z_DBG_SETUP", '''            letzter_trade[kd.kid] = setup
            setups.append(setup)''',
     '''            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s ==> SETUP K%d R=%+.5f" % (
                    k, richtung, kd.kid, float(trade.r_mult)))'''),
]
for _nm, _s, _new in Z2:
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)

HITS: List[Tuple[int, str, str]] = []
DBG: List[str] = []
ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_hook"] = adapter
ns["_CUR"] = [0, "?"]
ns["_VC"] = VC
ns["_VM6"] = VM6
ns["_VSB"] = VSB
ns["_LOK"] = VLOK
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _reclaim_stufe_lok
ns["_DBG"] = DBG
ns["_DBGB"] = DBGB


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
(ROOT / "test" / "_tmp_e33_patched.py").write_text(patched, encoding="utf-8",
                                                   newline="\n")
exec(compile(patched, "<se_e33>", "exec"), ns)  # noqa: S102

t1 = time.time()
setups, stats = ns["_se_trades"](copy.deepcopy(scan), cfg)
t_lauf = time.time() - t1


# --------------------------------------------------------------- Kennzahlen
_tr = np.maximum(HI[1:] - LO[1:],
                 np.maximum(np.abs(HI[1:] - CL[:-1]), np.abs(LO[1:] - CL[:-1])))
_tr = np.concatenate([[HI[1] - LO[1]], _tr])


def atr14(k: int) -> float:
    return float(_tr[max(0, k - 13):k + 1].mean())


def kz(ss: List) -> Dict[str, float]:
    if not ss:
        return {"n": 0, "R": 0.0, "USDn": 0.0, "Qstop": 0.0}
    r = [float(s.r) for s in ss]
    usd = [float(s.r) * abs(float(s.sl) - float(s.entry)) for s in ss]
    return {"n": len(ss), "R": sum(r), "USDn": sum(usd) / len(ss),
            "Qstop": sum(1 for x in r if x <= -1.0 + 1e-9) / len(ss)}


def _sel(a: int, b: int) -> List:
    """Selektion ueber den SIGNAL-Bar (s.bar)."""
    return [s for s in setups if a <= int(s.bar) <= b]


SCHNITTE = [("gesamt", 0, 10 ** 9),
            ("H1 (entry<644)", -10 ** 9, 10 ** 9),
            ("H2 (entry>=644)", -10 ** 9, 10 ** 9),
            ("H2b (entry>=966)", -10 ** 9, 10 ** 9),
            ("ZIELZONE (bar)", Z0, Z1)]


def _schn(name: str) -> List:
    if name.startswith("H1"):
        return [s for s in setups if int(s.entry_bar) < H1_H2]
    if name.startswith("H2 "):
        return [s for s in setups if int(s.entry_bar) >= H1_H2]
    if name.startswith("H2b"):
        return [s for s in setups if int(s.entry_bar) >= H2B]
    if name.startswith("ZIEL"):
        return _sel(Z0, Z1)
    return list(setups)


print("=" * 110)
print(f"E-33 AUG-ZIELERREICHUNG -- Variante {VAR}")
print("=" * 110)
print(f"Engine : {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"n {n}  box_end(Kalender) {box_end}  Laufgrenze {scan['box_end_bar']}")
print(f"Segmente: {[(s.phasen_id, s.start_bar, s.end_bar) for s in adapter.segmente]}")
print(f"Schalter: VC={VC} M6={VM6} UEB={VUEB} SB={VSB}  "
      f"ueberdehnung={cfg.max_sweep_ueberdehnung_pct}")
print(f"Laufzeit {t_lauf:.1f}s   Setups {len(setups)}")
print("")
print(f"   {'Schnitt':<19}{'n':>5}{'R':>14}{'USD/Tr':>11}{'Q_stop':>9}")
for name, _a, _b in SCHNITTE:
    k = kz(_schn(name))
    print(f"   {name:<19}{k['n']:>5}{k['R']:>+14.6f}{k['USDn']:>+11.4f}"
          f"{k['Qstop']:>9.3f}")

print("")
print("   ABLEHNUNGS-TRICHTER (Signal-Bar):")
print(f"   {'Schnitt':<19}{'Q29':>7}{'F3':>6}{'Blocker':>9}{'Stufe0':>8}"
      f"{'Zyklus':>8}{'keinRaum':>10}{'Vakuum':>8}{'keinGeg':>9}{'SETUP':>7}")
for name, _a, _b in SCHNITTE:
    if name.startswith("H1"):
        rr = [h for h in HITS if h[0] < H1_H2]
    elif name.startswith("H2 "):
        rr = [h for h in HITS if h[0] >= H1_H2]
    elif name.startswith("H2b"):
        rr = [h for h in HITS if h[0] >= H2B]
    elif name.startswith("ZIEL"):
        rr = [h for h in HITS if Z0 <= h[0] <= Z1]
    else:
        rr = HITS
    c = Counter(k for (_k, _r, k) in rr)
    print(f"   {name:<19}{c['quartil_blockiert']:>7}{c['f3']:>6}"
          f"{c['blocker']:>9}{c['stufe0']:>8}{c['zyklus_blockiert']:>8}"
          f"{c['kein_raum']:>10}{c['vakuum']:>8}{c['kein_gegner']:>9}"
          f"{c['SETUP']:>7}")

print("")
print("   ALLE SETUPS (Signal-Bar, Entry-Bar, Richtung, kid, R):")
for s in sorted(setups, key=lambda x: int(x.bar)):
    tag = ""
    if int(s.entry_bar) >= H1_H2:
        tag += " H2"
    if Z0 <= int(s.bar) <= Z1:
        tag += " ZIEL"
    print(f"      bar {int(s.bar):>5} entry {int(s.entry_bar):>5} "
          f"{s.richtung:<6} K{int(s.kid):<4} R {float(s.r):>+10.5f} "
          f"{s.stufe:<16}{tag}")

print("")
print("   DIAGNOSE der drei avisierten Bars (1072/1073 - 1122/1123 - 1172/1173):")
for z in DBG:
    print(z)

print("")
print("ENDE E-33 " + VAR)
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
