# -*- coding: utf-8 -*-
"""E-33 (read-only, AUG) -- ZIELERREICHUNG zweite H2-Haelfte: V-C / V-D.

Aufruf: python test/_tmp_e33_var.py <variante>

Varianten (alle ADDITIV, Basis = arretierter V018-Lauf):
  V018            unveraendert
  VC848           V-C: Q29-Range phasenlokal ab 848 (P9)
  VC_P12          V-C: Q29-Range phasenlokal mit Phasenkette 848/1021/1171
  VD_M6           V-D1: M6-Blocker nur bei LEBENDER Aussenwand (_lebt)
  VD_UEB          V-D2: max_sweep_ueberdehnung_pct 0.60 -> 0.80
  VD_TOUCH        V-D3: min_touches_handelbar 3 -> 2
  VD_SB           V-D4: RECLAIM_AT_OPENING (Ereignis schlaegt Schlafstatus)
  VD_ALL          V-D1+D2+D3+D4
  VC848_VD_ALL    V-C(848) + V-D1+D2+D3+D4
  VC_P12_VD_ALL   V-C(Handliste) + V-D1+D2+D3+D4

Fenster: AUG, box_end_bar bleibt 2026-08-19 (= 644).
H1 = bar <  644          (V018-Grenze)
H2 = bar >= 644
H2b = bar >= 966         (zweite Haelfte von H2)
Ziel = 1021 <= bar <= 1287 (Zielzone P10/P12)
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
BOX_END = 644
H2B = 966
ZIEL0, ZIEL1 = 1021, 1287
DBGB = {1072, 1073, 1122, 1123, 1172, 1173}

VAR = (sys.argv[1] if len(sys.argv) > 1 else "V018")

# ---- Variantenmatrix -------------------------------------------------------
SW: Dict[str, Tuple[int, bool, bool, bool, bool]] = {
    # VC (0=aus, 1=848, 2=Handliste), M6, UEB, TOUCH, SB
    "V018":           (0, False, False, False, False),
    "VC848":          (1, False, False, False, False),
    "VC_P12":         (2, False, False, False, False),
    "VD_M6":          (0, True,  False, False, False),
    "VD_UEB":         (0, False, True,  False, False),
    "VD_TOUCH":       (0, False, False, True,  False),
    "VD_SB":          (0, False, False, False, True),
    "VD_ALL":         (0, True,  True,  True,  True),
    "VC848_VD_ALL":   (1, True,  True,  True,  True),
    "VC_P12_VD_ALL":  (2, True,  True,  True,  True),
}
assert VAR in SW, f"unbekannte Variante {VAR!r}; erlaubt {list(SW)}"
VC, VM6, VUEB, VTOUCH, VSB = SW[VAR]

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

spec = importlib.util.spec_from_file_location("eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)

import dataclasses  # noqa: E402

cfg0 = eng.StraightEdgeHarnessKonfiguration()
cfg = dataclasses.replace(
    cfg0,
    max_sweep_ueberdehnung_pct=(0.80 if VUEB
                                else cfg0.max_sweep_ueberdehnung_pct),
    min_touches_handelbar=(2 if VTOUCH
                           else cfg0.min_touches_handelbar))

t0 = time.time()
scan = eng._se_scan("AUG", cfg0)          # Scan mit arretierter cfg
n = scan["n"]
d = scan["d"]
HI = d["high"].to_numpy(float)
LO = d["low"].to_numpy(float)
CL = d["close"].to_numpy(float)

# ------------------------------------------------------------ AST-Extraktion
quelle = ENGINE_P.read_text(encoding="utf-8")
baum = ast.parse(quelle)
knoten = next(x for x in ast.walk(baum)
              if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
zeilen = quelle.split("\n")
SRC = "\n".join(zeilen[knoten.lineno - 1:knoten.end_lineno])
_n_stat = len(re.findall(r'stats\["(\w+)"\] \+= 1', SRC))
SRC = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', SRC)

ERS: List[Tuple[str, str]] = [
    # (1) Richtungszeiger
    ('''        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])''',
     '''        for richtung in ("SHORT", "LONG"):
            _CUR[0] = k
            _CUR[1] = richtung
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])'''),
    # (2) V-C: Q29-Range phasenlokal
    ('''        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))''',
     '''        _q0 = _PHS(k)
        ex_hi = float(np.max(hi[_q0:k + 1]))
        ex_lo = float(np.min(lo[_q0:k + 1]))'''),
    # (3) V-D1: M6-Blocker nur bei lebender Wand
    ('''            if e is kd or not _existiert(e, k):
                continue''',
     '''            if e is kd or not _existiert(e, k) or (
                    _VM6 and not _lebt(e, k)):
                continue'''),
    # (4) V-D4: RECLAIM_AT_OPENING (Ereignis schlaegt Schlafstatus)
    ('''        if not e.ist_aktiv_bei(k):
            return False
        return e.erster_pivot_bar + 2 <= k + 1''',
     '''        if not e.ist_aktiv_bei(k):
            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == "OBEN"
                   else (lo[k] < e.basis_bei(k)))
            if not (_VSB and _ev):
                return False
        return e.erster_pivot_bar + 2 <= k + 1'''),
    # (5) Diagnose: Kandidatenpool
    ('''        pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))''',
     '''        if _DBG is not None and k in _DBGB:
            _DBG.append("      POOL " + seite + " k=" + str(k) + ": " + " | ".join(
                "K" + str(e.kid) + " b=" + format(e.basis_bei(k), ".3f")
                + " dist=" + format(_dist(e), ".4f")
                + " tc=" + str(e.touch_conf(k))
                + " et=" + str(_etabliert(e, k))
                + " lebt=" + str(_lebt(e, k))
                + " akt=" + str(e.ist_aktiv_bei(k)) for e in pool))
        pool.sort(key=lambda e: e.basis_bei(k), reverse=(seite == "OBEN"))'''),
    # (6) Diagnose: Kandidat
    ('''            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue''',
     '''            kd = _kandidat(richtung, k, sweep_px)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar " + str(k) + " " + richtung
                            + " sweep=" + format(sweep_px, ".3f") + " kd="
                            + ("None" if kd is None else
                               "K" + str(kd.kid) + " basis="
                               + format(kd.basis_bei(k), ".3f")))
            if kd is None:
                continue'''),
    # (7) Diagnose: M6-Blocker
    ('''            if blk is not None:
                _hit(_CUR, "blocker")''',
     '''            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar " + str(k) + " " + richtung
                            + " M6-Blocker=" + ("None" if blk is None else
                                                "K" + str(blk.kid) + " "
                                                + format(blk.basis_bei(k), ".3f")))
            if blk is not None:
                stats["blocker"] += 1'''),
    # (8) Diagnose: Q29
    ('''            if not _im_aussenquartil(richtung, k, sweep_px):
                _hit(_CUR, "quartil_blockiert")''',
     '''            _q_ok = _im_aussenquartil(richtung, k, sweep_px)
            if _DBG is not None and k in _DBGB:
                _ex_hi = float(np.max(hi[:k + 1]))
                _ex_lo = float(np.min(lo[:k + 1]))
                _sp = _ex_hi - _ex_lo
                _dq = (((_ex_hi - sweep_px) if richtung == "SHORT"
                        else (sweep_px - _ex_lo)) / _sp * 100.0) if _sp > 0 else 0.0
                _q0d = _PHS(k)
                _ex_hi2 = float(np.max(hi[_q0d:k + 1]))
                _ex_lo2 = float(np.min(lo[_q0d:k + 1]))
                _sp2 = _ex_hi2 - _ex_lo2
                _dq2 = (((_ex_hi2 - sweep_px) if richtung == "SHORT"
                         else (sweep_px - _ex_lo2)) / _sp2 * 100.0) if _sp2 > 0 else 0.0
                _DBG.append("   bar " + str(k) + " " + richtung + " Q29 global="
                            + format(_dq, ".2f") + "% lokal(" + str(_q0d) + ")="
                            + format(_dq2, ".2f") + "% -> "
                            + ("durch" if _q_ok else "SPERRE"))
            if not _q_ok:
                stats["quartil_blockiert"] += 1'''),
    # (9) Diagnose: Stufe
    ('''            if stufe_n == 0:
                continue''',
     '''            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar " + str(k) + " " + richtung + " Stufe="
                            + str(stufe_n) + " (" + str(stufe_name) + ")")
            if stufe_n == 0:
                continue'''),
    # (10) Diagnose: SETUP
    ('''            letzter_trade[kd.kid] = setup
            setups.append(setup)''',
     '''            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar " + str(k) + " " + richtung + " ==> SETUP K"
                            + str(kd.kid) + " R=" + format(float(trade.r_mult), "+.5f"))'''),
]

for alt, neu in ERS:
    assert alt in SRC, "Ankertext fehlt:\n" + alt[:120]
    SRC = SRC.replace(alt, neu, 1)


def _phs(k: int) -> int:
    """Phasenanker der Q29-Range (nur bei VC>0 wirksam)."""
    if VC == 1:
        return 848 if k >= 848 else 0
    if VC == 2:
        if k >= 1171:
            return 1171
        if k >= 1021:
            return 1021
        if k >= 848:
            return 848
        return 0
    return 0


HITS: List[Tuple[int, str, str]] = []
DBG: List[str] = []
ns: Dict = dict(eng.__dict__)
ns["_CUR"] = [0, "?"]
ns["_PHS"] = _phs
ns["_VM6"] = VM6
ns["_VSB"] = VSB
ns["_DBG"] = DBG
ns["_DBGB"] = DBGB


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
exec(compile(SRC, str(ENGINE_P) + "<e33>", "exec"), ns)  # noqa: S102
fn = ns["_se_trades"]

t1 = time.time()
setups, stats = fn(scan, cfg)
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
    return [s for s in setups if a <= int(s.bar) <= b]


SCHNITTE = [("gesamt", 0, 10 ** 9), ("H1", 0, BOX_END - 1),
            ("H2", BOX_END, 10 ** 9), ("H2b (2. Haelfte)", H2B, 10 ** 9),
            ("ZIELZONE", ZIEL0, ZIEL1)]

print("=" * 108)
print(f"E-33 AUG-ZIELERREICHUNG -- Variante {VAR}")
print("=" * 108)
print(f"Engine : {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"n {n}  box_end_bar {scan['box_end_bar']}  |  VC={VC} M6={VM6} "
      f"UEB={VUEB} TOUCH={VTOUCH} SB={VSB}  |  "
      f"ueberdehnung={cfg.max_sweep_ueberdehnung_pct} "
      f"min_touch={cfg.min_touches_handelbar}")
print(f"Laufzeit {t_lauf:.1f}s   Setups {len(setups)}")
print("")
print(f"   {'Schnitt':<17}{'n':>5}{'R':>15}{'USD/Tr':>11}{'Q_stop':>9}")
for name, a, b in SCHNITTE:
    k = kz(_sel(a, b))
    print(f"   {name:<17}{k['n']:>5}{k['R']:>+15.6f}{k['USDn']:>+11.4f}"
          f"{k['Qstop']:>9.3f}")

print("")
print("   ABLEHNUNGEN:")
print(f"   {'Schnitt':<17}{'kandidat':>9}{'Q29':>7}{'F3':>6}{'Blocker':>9}"
      f"{'Stufe0':>8}{'Zyklus':>8}{'keinRaum':>10}{'keinGeg':>9}{'SETUP':>7}")
for name, a, b in SCHNITTE:
    c = Counter(key for (kk, _r, key) in HITS if a <= kk <= b)
    print(f"   {name:<17}{c['kandidat']:>9}{c['quartil_blockiert']:>7}"
          f"{c['f3']:>6}{c['blocker']:>9}{c['stufe0']:>8}"
          f"{c['zyklus_blockiert']:>8}{c['kein_raum']:>10}"
          f"{c['kein_gegner']:>9}{c['SETUP']:>7}")

print("")
print("   SETUPS der ZIELZONE (bar 1021..1287):")
zs = sorted(_sel(ZIEL0, ZIEL1), key=lambda s: int(s.bar))
if not zs:
    print("      (keine)")
for s in zs:
    print(f"      bar {int(s.bar):>5} {s.richtung:<6} K{int(s.kid):<4} "
          f"entry {float(s.entry):>8.4f} SL {float(s.sl):>8.4f} "
          f"TP2 {float(s.tp2):>8.4f}  R {float(s.r):>+10.5f}  "
          f"{s.stufe}")

print("")
print("   SETUPS in H2 (bar >= 644), vollstaendig:")
for s in sorted(_sel(BOX_END, 10 ** 9), key=lambda s: int(s.bar)):
    print(f"      bar {int(s.bar):>5} {s.richtung:<6} K{int(s.kid):<4} "
          f"R {float(s.r):>+10.5f}  {s.stufe}")

print("")
print("   DIAGNOSE der drei avisierten Bars (1072/1073 - 1122/1123 - 1172/1173):")
for z in DBG:
    print(z)

print("")
print(f"ENDE E-33 {VAR}")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
