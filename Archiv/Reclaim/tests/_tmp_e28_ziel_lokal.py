# -*- coding: utf-8 -*-
"""E-28 (read-only) -- LOKALISIERUNG des ZIELSYSTEMS (Gegenkante + POC).

Aufruf:  python test/_tmp_e28_ziel_lokal.py <modus> <variante>
         modus    = s2 | aug
         variante = base | geg | geg960 | gegleb | poc | gegpoc | geg960poc | geglebpoc

Saubere 2-Koordinaten-Matrix (X1):
    gegenkante in {global, lokalbasis, lokal960leb}  x  poc in {global, lokal}
    = base / geg / geg960  x  (ohne | poc)

`gegleb` ist KEINE 960er-Variante: die Engine-`_lebt` prueft `wall_live_bars`
= 96 Bars. Sie bleibt nur als 96-Bar-Referenz erhalten und ist als solche
gekennzeichnet; die ratifizierte Referenz ist `geg960`.

Ein Lauf pro Prozess (`_se_trades` mutiert den Kantenzustand -- siehe E-27/F0).

Fensterdefinition (identisch fuer alle drei Referenzen, Anwender-Vorgabe):

    _W(k) = max(0, k - 960)

Gesetzt ist ferner die ratifizierte Q29-Lokalisierung aus E-27 (L960).

FLAG[0]  Gegenkanten-Pool
    0 = unveraendert (globaler Pool)
    1 = Basis im lokalen Fenster:   lo[_W] <= basis <= hi[_W]
    2 = Liveness 96-Bar (Engine-_lebt, wall_live_bars) -- 96-Bar-Referenz
    3 = Liveness 960-Bar: letzter Docht >= k - 960     -- RATIFIZIERT
FLAG[1]  POC-Anker
    0 = poc_start (unveraendert, = Box-Beginn 0)
    1 = poc_start = _W(k)
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import pickle
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
SPLIT = 17692
W960 = 960
MODE = (sys.argv[1] if len(sys.argv) > 1 else "s2").lower()
VAR = (sys.argv[2] if len(sys.argv) > 2 else "base").lower()
OUT = ROOT / "test" / f"_tmp_e28_ziel_{MODE}_{VAR}_out.txt"
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

t0 = time.time()
if MODE == "s2":
    scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
    box_orig = scan["box_end_bar"]
    scan["box_end_bar"] = scan["n"]
    TITEL = "S2"
else:
    # AUG: box_end_bar unveraendert lassen (Box-Grenze 2026-08-19).
    scan = eng._se_scan("AUG", cfg)
    box_orig = scan["box_end_bar"]
    TITEL = "AUG"
N = scan["n"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].to_numpy()
t_lade = time.time() - t0

# --------------------------------------------------------- Varianten-Definition
VARMAP: Dict[str, Tuple[int, int]] = {
    "base": (0, 0),
    "geg": (1, 0),
    "geg960": (3, 0),
    "gegleb": (2, 0),
    "poc": (0, 1),
    "gegpoc": (1, 1),
    "geg960poc": (3, 1),
    "geglebpoc": (2, 1),
}
assert VAR in VARMAP, f"unbekannte Variante {VAR!r}; erlaubt {list(VARMAP)}"
GMOD, PMOD = VARMAP[VAR]
BESCHR = {
    (0, 0): "BASELINE (Q29 lokal 960; Gegenkante global; poc_start=0)",
    (1, 0): "GEGENKANTE lokal 960 (Basis im Fenster)",
    (3, 0): "GEGENKANTE lokal 960-LEBIGKEIT (letzter Docht >= k-960) [RATIFIZIERT]",
    (2, 0): "GEGENKANTE lokal 96-BAR-LEBIGKEIT (wall_live_bars; NICHT ratifiziert)",
    (0, 1): "POC lokal 960 (poc_start = max(0,k-960))",
    (1, 1): "GEGENKANTE lokal (Basis) + POC lokal",
    (3, 1): "GEGENKANTE lokal 960-Lebigk. + POC lokal",
    (2, 1): "GEGENKANTE lokal 96-Bar-Lebigk. + POC lokal",
}[(GMOD, PMOD)]

# ------------------------------------------------------------ AST-Extraktion
quelle = ENGINE_P.read_text(encoding="utf-8")
baum = ast.parse(quelle)
knoten = next(n for n in ast.walk(baum)
              if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
zeilen = quelle.split("\n")
SRC = "\n".join(zeilen[knoten.lineno - 1:knoten.end_lineno])
_n_stat = len(re.findall(r'stats\["(\w+)"\] \+= 1', SRC))
SRC = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', SRC)

ERS = [
    # (1) Richtungszeiger
    ("""        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])""",
     """        for richtung in ("SHORT", "LONG"):
            _CUR[0] = k
            _CUR[1] = richtung
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])"""),
    # (2) Q29 ratifiziert lokal (E-27, Fenster 960)
    ("""        ex_hi = float(np.max(hi[:k + 1]))
        ex_lo = float(np.min(lo[:k + 1]))""",
     """        ex_hi = float(np.max(hi[_W(k):k + 1]))
        ex_lo = float(np.min(lo[_W(k):k + 1]))"""),
    # (3) Gegenkanten-Pool lokalisieren
    ("""        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= k + 1
                and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                     or e.touch_conf(k) >= 2)]""",
     """        _wh = float(np.max(hi[_W(k):k + 1]))
        _wl = float(np.min(lo[_W(k):k + 1]))
        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= k + 1
                and (not _FLAG[0] or (
                     (_wl <= e.basis_bei(k) <= _wh) if _FLAG[0] == 1
                     else (_lebt960(e, k) if _FLAG[0] == 3 else _lebt(e, k))))
                and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                     or e.touch_conf(k) >= 2)]"""),
    # (4) POC-Anker lokalisieren
    ("""            poc = berechne_kausalen_histogramm_poc(
                d, poc_start, k, unter, ober, cfg.num_bins)""",
     """            poc = berechne_kausalen_histogramm_poc(
                d, (_W(k) if _FLAG[1] else poc_start), k, unter, ober,
                cfg.num_bins)"""),
    # (5) Buchfuehrung
    ("""            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue""",
     """            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                _hit(_CUR, "kaskade_leer")
                continue
            _hit(_CUR, "kandidat")"""),
    ("""            if stufe_n == 0:
                continue""",
     """            if stufe_n == 0:
                _hit(_CUR, "stufe0")
                continue"""),
    ("""            letzter_trade[kd.kid] = setup
            setups.append(setup)""",
     """            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")"""),
]
for alt, neu in ERS:
    assert alt in SRC, "Ankertext fehlt:\n" + alt[:100]
    SRC = SRC.replace(alt, neu, 1)

_FLAG: List[int] = [GMOD, PMOD]


def _w(k: int) -> int:
    return max(0, k - W960)


def _lebt960(e, k: int) -> bool:
    """Engine-`_lebt`-Semantik (Q25), aber mit Fensterweite 960 statt
    `cfg.wall_live_bars` (= 96). Nur der lokale Docht-Zeitstempel zaehlt."""
    bars = [b for b, _ in e.wicks if b <= k]
    if not bars:
        return False
    return max(bars) >= k - W960


HITS: List[Tuple[int, str, str]] = []
ns: Dict = dict(eng.__dict__)
ns["_CUR"] = [0, "?"]
ns["_W"] = _w
ns["_lebt960"] = _lebt960
ns["_FLAG"] = _FLAG


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
exec(compile(SRC, str(ENGINE_P) + "<e28>", "exec"), ns)  # noqa: S102
fn = ns["_se_trades"]

# --------------------------------------------------------------- Kennzahlen
_tr = np.maximum(hi[1:] - lo[1:],
                 np.maximum(np.abs(hi[1:] - cl[:-1]), np.abs(lo[1:] - cl[:-1])))
_tr = np.concatenate([[hi[1] - lo[1]], _tr])


def atr14(k: int) -> float:
    return float(_tr[max(0, k - 13):k + 1].mean())


def kz(ss: List) -> Dict[str, float]:
    if not ss:
        return {"n": 0, "R": 0.0, "R_adj": 0.0, "USD": 0.0, "USDn": 0.0,
                "ATRn": 0.0, "Qstop": 0.0}
    r = [float(s.r) for s in ss]
    usd = [float(s.r) * abs(float(s.sl) - float(s.entry)) for s in ss]
    at = [u / atr14(int(s.bar)) for u, s in zip(usd, ss)]
    rmax = max([0.0] + [x for x in r if x > 0])
    nstop = sum(1 for x in r if x <= -1.0 + 1e-9)
    return {"n": len(ss), "R": sum(r), "R_adj": sum(r) - rmax, "USD": sum(usd),
            "USDn": sum(usd) / len(ss), "ATRn": sum(at) / len(ss),
            "Qstop": nstop / len(ss)}


def ziel_metrik(ss: List) -> Dict[str, float]:
    """Erreichbarkeit des Ziels: Distanz entry->tp2 und Haltedauer."""
    if not ss:
        return {"dabs": 0.0, "dpct": 0.0, "halt": 0.0, "gew": 0.0}
    dabs = [abs(float(s.tp2) - float(s.entry)) for s in ss]
    dpct = [abs(float(s.tp2) - float(s.entry)) / float(s.entry) * 100.0
            for s in ss]
    halt = [int(s.exit2_bar) - int(s.entry_bar) for s in ss]
    return {"dabs": sum(dabs) / len(dabs), "dpct": sum(dpct) / len(dpct),
            "halt": sum(halt) / len(halt),
            "gew": sum(1 for s in ss if float(s.r) > 0) / len(ss) * 100.0}


t1 = time.time()
setups, stats = fn(scan, cfg)
t_lauf = time.time() - t1
alle_s = list(setups)
h1 = [s for s in alle_s if int(s.bar) < SPLIT]
h2 = [s for s in alle_s if int(s.bar) >= SPLIT]

print("=" * 104)
print(f"E-28 ZIELSYSTEM-LOKALISIERUNG -- {TITEL}  Variante {VAR.upper()}")
print("=" * 104)
print(f"   {BESCHR}")
print(f"Engine : {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"n {N}  box_end_bar {box_orig} -> Laufgrenze {scan['box_end_bar']}  |  "
      f"Fenster _W(k) = max(0, k-{W960})  |  Q29 lokal 960 (ratifiziert)")
print(f"Instrumentierung: {_n_stat} × stats-Hook, Q29/Gegenkante/POC-Injektion, "
      f"_CUR-Zeiger")
print(f"Laufzeit {t_lauf:.1f}s   Setups {len(alle_s)}")

for name, sset in (("gesamt", alle_s), ("H1", h1), ("H2", h2)):
    k = kz(sset)
    z = ziel_metrik(sset)
    print(f"   {name:<7}: n {k['n']:>4}  R {k['R']:+.6f}  R_adj "
          f"{k['R_adj']:+.6f}  USD {k['USD']:+.4f}  USD/Tr {k['USDn']:+.4f}  "
          f"ATR/Tr {k['ATRn']:+.4f}  Q_stop {k['Qstop']:.3f}  "
          f"|ziel|/e {z['dpct']:>5.2f}%  halt {z['halt']:>5.1f}  "
          f"Gew% {z['gew']:>4.1f}")
print(f"   LONG  : n {sum(1 for s in alle_s if s.richtung == 'LONG'):>4}"
      f"   SHORT: n {sum(1 for s in alle_s if s.richtung == 'SHORT'):>4}")

print("")
print("   Q29-TRICHTER + Zielsystem-Sperren:")
print(f"   {'Haelfte':<7}{'Richtung':<8}{'Kand.':>7}{'Q29':>6}{'SETUP':>7}"
      f"{'keinGeg':>9}")
for hname, a, b in (("H1", 0, SPLIT), ("H2", SPLIT, N)):
    for richtung in ("SHORT", "LONG"):
        c = Counter(key for (kk, r, key) in HITS
                    if r == richtung and a <= kk < b)
        print(f"   {hname:<7}{richtung:<8}{c['kandidat']:>7}"
              f"{c['quartil_blockiert']:>6}{c['SETUP']:>7}"
              f"{c['kein_gegner']:>9}")

print("")
print("   ERREICHBARKEIT DES ZIELS (Bar, Richtung, Kante, entry, tp2, "
      "Distanz %, R, Haltedauer):")
for s in sorted(alle_s, key=lambda x: int(x.bar)):
    _dp = abs(float(s.tp2) - float(s.entry)) / float(s.entry) * 100.0
    print(f"      {int(s.bar):>6} {s.richtung:<6}K{int(s.kid):<4} "
          f"e {float(s.entry):>8.4f}  tp2 {float(s.tp2):>8.4f}  "
          f"d {_dp:>6.2f}%  R {float(s.r):>+10.5f}  "
          f"halt {int(s.exit2_bar) - int(s.entry_bar):>5}")

print("")
print(f"ENDE {TITEL} {VAR}   Gesamtlaufzeit {time.time() - t0:.1f}s")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
