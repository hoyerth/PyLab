# -*- coding: utf-8 -*-
"""E-26 (read-only, offline) -- WARUM emittiert die Engine in S2-H2 0 LONGs?

Verfahren (kein Neubau der Logik!):
  Die Funktion ``_se_trades`` wird per AST aus der arretierten Engine
  ``test/tmp_kanten_engine_replay.py`` extrahiert und in einem eigenen
  Namespace (Kopie der Engine-Globals) ausgefuehrt. Dabei wird NUR die
  Buchfuehrung ersetzt:
    * ``stats["X"] += 1``            -> ``_hit(_CUR, "X")``
    * nach ``kd = _kandidat(...)``   -> Kandidatendetail wird protokolliert
        - ``kaskade_leer`` wenn ``kd is None``
        - ``kandidat``     wenn ``kd is not None`` (+ Detailzeile)
    * ``stufe_n == 0`` / Dedup / erfolgreicher Setup -> eigene Marker
  Die Entscheidungslogik selbst wird NICHT angetastet.

Zielausgabe: Trichter je Richtung (SHORT/LONG) getrennt fuer H1 und H2,
sowie eine Liste der LONG-Kandidaten in H2 mit dem Gate, an dem sie sterben.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import pickle
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
OUT = ROOT / "test" / "_tmp_e26_long_blockade_out.txt"
SPLIT = 17692
_FH = OUT.open("w", encoding="utf-8", newline="\n")


class _Tee:
    def write(self, s: str) -> int:
        _FH.write(s)
        return sys.__stdout__.write(s)

    def flush(self) -> None:
        _FH.flush()
        sys.__stdout__.flush()


sys.stdout = _Tee()  # type: ignore[assignment]

spec = importlib.util.spec_from_file_location(
    "eng", ENGINE_P)
eng = importlib.util.module_from_spec(spec)
sys.modules["eng"] = eng
spec.loader.exec_module(eng)
cfg = eng.StraightEdgeHarnessKonfiguration()

scan = pickle.loads((ROOT / "test" / "_tmp_s2_scan_cache.pkl").read_bytes())
N = scan["n"]
box_end_cache = scan["box_end_bar"]
# WICHTIG: Der arretierte S2-Cache traegt box_end_bar = 17692 (Split) -- die
# Partition. `_se_trades` haelt sich strikt an `bars < box_end_bar`, daher
# laeuft der Harness fuer die H2-Auswertung bewusst bis n durch. Der Wert wird
# EXPLIZIT gesetzt (nicht als neue Quelle erfunden): Laufgrenze = n.
scan["box_end_bar"] = N
box_end = scan["box_end_bar"]
d = scan["d"]
hi = d["high"].to_numpy(float)
lo = d["low"].to_numpy(float)
cl = d["close"].to_numpy(float)
ts = d["ts"].to_numpy()

# ------------------------------------------------------------ AST-Extraktion
quelle = ENGINE_P.read_text(encoding="utf-8")
baum = ast.parse(quelle)
knoten = next(n for n in ast.walk(baum)
              if isinstance(n, ast.FunctionDef) and n.name == "_se_trades")
zeilen = quelle.split("\n")
SRC = "\n".join(zeilen[knoten.lineno - 1:knoten.end_lineno])
print("=" * 100)
print("E-26 LONG-BLOCKADE -- Instrumentierte `_se_trades` (S2)")
print("=" * 100)
print(f"Engine     : {ENGINE_P.name}  "
      f"SHA {hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:24]}...")
print(f"Funktion   : _se_trades  Zeilen {knoten.lineno}..{knoten.end_lineno}  "
      f"({knoten.end_lineno - knoten.lineno + 1} Zeilen)")
print(f"n {N}  box_end_bar (Cache) {box_end_cache}  -> Laufgrenze {box_end}  "
      f"Split {SPLIT}  (H1 {SPLIT} / H2 {N - SPLIT} Bars)")

# ------------------------------------------------------------ Instrumentierung
vorher = SRC
SRC = re.sub(r'stats\["(\w+)"\] \+= 1', r'_hit(_CUR, "\1")', SRC)
n_stats = len(re.findall(r'stats\["(\w+)"\] \+= 1', vorher))
print(f"Ersetzt    : {n_stats} × `stats[..] += 1` -> `_hit(_CUR, ..)`")

ERS = [
    ("""        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])""",
     """        for richtung in ("SHORT", "LONG"):
            _CUR[0] = k
            _CUR[1] = richtung
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])"""),
    ("""            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                continue""",
     """            kd = _kandidat(richtung, k, sweep_px)
            if kd is None:
                _hit(_CUR, "kaskade_leer")
                continue
            _hit(_CUR, "kandidat")
            _KAND.append((k, richtung, kd.kid, kd.basis_bei(k), sweep_px))"""),
    ("""            if stufe_n == 0:
                continue""",
     """            if stufe_n == 0:
                _hit(_CUR, "stufe0")
                continue"""),
    ("""            if entry_bar in getradete_entry_bars:   # B23-3: Dedup
                continue""",
     """            if entry_bar in getradete_entry_bars:   # B23-3: Dedup
                _hit(_CUR, "dedup")
                continue"""),
    ("""            letzter_trade[kd.kid] = setup
            setups.append(setup)""",
     """            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")"""),
]
for alt, neu in ERS:
    assert alt in SRC, "Ankertext nicht gefunden:\n" + alt[:80]
    SRC = SRC.replace(alt, neu, 1)
print("Injektionen: kaskade_leer/kandidat(+Detail) · stufe0 · dedup · SETUP")

HITS: List[Tuple[int, str, str]] = []
KAND: List[Tuple[int, str, int, float, float]] = []
ns: Dict = dict(eng.__dict__)
ns["_CUR"] = [0, "?"]
ns["_HITS"] = HITS
ns["_KAND"] = KAND


def _hit(cur: List, key: str) -> None:
    HITS.append((cur[0], cur[1], key))


ns["_hit"] = _hit
exec(compile(SRC, str(ENGINE_P) + "<instrumented>", "exec"), ns)  # noqa: S102
fn = ns["_se_trades"]

setups, stats = fn(scan, cfg)
print(f"Ergebnis   : {len(setups)} Setups gesamt  "
      f"(LONG {sum(1 for s in setups if s.richtung == 'LONG')} / "
      f"SHORT {sum(1 for s in setups if s.richtung == 'SHORT')})")

# ------------------------------------------------------------ Trichter-Ausgabe
GATES = ["kandidat", "kaskade_leer", "blocker", "quartil_blockiert", "stufe0",
         "frisch_blockiert", "f3", "zyklus_blockiert", "kein_gegner",
         "kein_raum", "dedup", "SETUP"]
LABEL = {
    "kandidat": "Kaskade liefert Kandidaten",
    "kaskade_leer": "  -> keine Kaskade (kein Kand.)",
    "blocker": "M6 Innenlevel-Blocker",
    "quartil_blockiert": "Q29 Niemandsland-Sperre",
    "stufe0": "  -> _reclaim_stufe == 0",
    "frisch_blockiert": "Q24 Linie zu jung",
    "f3": "Q4 F3-Frische (Sweep-Bar)",
    "zyklus_blockiert": "Q21 Retest-Zyklus",
    "kein_gegner": "Q5 Gegenkante fehlt",
    "kein_raum": "Raum/TP2/POC/Risk-Gate",
    "dedup": "B23-3 Dedup Entry-Bar",
    "SETUP": "==> SETUP erzeugt",
}


def trichter(richtung: str, a: int, b: int, titel: str) -> None:
    c = Counter(key for (k, r, key) in HITS if r == richtung and a <= k < b)
    print("")
    print(f"   {titel}")
    print(f"   {'Gate':<32}{'Haeufigkeit':>13}")
    for g in GATES:
        if c[g]:
            print(f"   {LABEL[g]:<32}{c[g]:>13}")
    print(f"   {'-- Kandidatenbasis':<32}{'':>13}")
    print(f"   Summe Kandidaten            {c['kandidat']:>13}")


print("")
print("=" * 100)
print("TRICHTER (je Richtung, getrennt nach H1/H2)")
print("=" * 100)
for richtung in ("SHORT", "LONG"):
    for (a, b, titel) in ((0, SPLIT, f"{richtung} -- H1 (Bars 0..{SPLIT - 1})"),
                          (SPLIT, N, f"{richtung} -- H2 (Bars {SPLIT}..{N - 1})")):
        trichter(richtung, a, b, titel)

# ------------------------------------------------------------ LONG-Detail H2
print("")
print("=" * 100)
print("LONG-KANDIDATEN IN H2 -- vollstaendige Liste (mit Sterbe-Gate)")
print("=" * 100)
_lk = [(k, kid, basis, sweep) for (k, r, kid, basis, sweep) in KAND
       if r == "LONG" and k >= SPLIT]
print(f"   Kandidaten (kd is not None): {len(_lk)}")
if _lk:
    # Sterbe-Gate praezise: letzter Hit NACH dem 'kandidat'-Marker derselben
    # (Bar, Richtung); 'kaskade_leer' gehoert definitionsgemaess nicht dazu.
    tot: Dict[int, str] = {}
    offen: Dict[int, bool] = {}
    for (k, r, key) in HITS:
        if r != "LONG":
            continue
        if key == "kandidat":
            offen[k] = True
            continue
        if key == "kaskade_leer":
            continue
        if offen.get(k) and k not in tot:
            tot[k] = key
    print(f"   {'Bar':>7}{'Datum':<13}{'Kante':>6}{'Basis':>9}{'Sweep':>9}"
          f"   {'Sterbe-Gate':<26}")
    for (k, kid, basis, sweep) in _lk:
        g = tot.get(k, "-- (kein Folge-Gate erfasst)")
        print(f"   {k:>7}{str(np.datetime64(ts[k], 'D')):<13}K{kid:<5}"
              f"{basis:>9.4f}{sweep:>9.4f}   {g:<26}")

# ------------------------------------------------------------ Q29-Tiefenanalyse
print("")
print("=" * 100)
print("Q29-TIEFENANALYSE -- warum die Sperre im Trend systematisch LONG trifft")
print("=" * 100)
print(f"   Q29 vergleicht das Sweep-Extremum mit dem LAUFENDEN GESAMT-Extrem")
print(f"   (ex_hi/ex_lo ueber Bars 0..k, NICHT das lokale Fenster):")
print(f"     SHORT: distanz = (ex_hi - hi[k]) / (ex_hi - ex_lo) * 100")
print(f"     LONG : distanz = (lo[k] - ex_lo) / (ex_hi - ex_lo) * 100")
print(f"   Handelbar nur bei distanz <= {cfg.quartil_distanz_pct} %.")
print("")
print(f"   {'Bar':>7}{'Datum':<13}{'ex_lo':>9}{'ex_hi':>9}{'Spanne':>9}"
      f"{'LONG-Schwelle':>15}{'lo[k]':>9}{'Q29-Dist':>10}  Status")
for _k in range(SPLIT, N, 240):
    _exl = float(np.min(lo[:_k + 1]))
    _exh = float(np.max(hi[:_k + 1]))
    _sp = _exh - _exl
    _thr = _exl + cfg.quartil_distanz_pct / 100.0 * _sp
    _d = (_k, )
    print(f"   {_k:>7}{str(np.datetime64(ts[_k], 'D')):<13}{_exl:>9.4f}"
          f"{_exh:>9.4f}{_sp:>9.4f}{_thr:>15.4f}{float(lo[_k]):>9.4f}"
          f"{(float(lo[_k]) - _exl) / _sp * 100:>9.1f}%  "
          f"{'FREI' if float(lo[_k]) <= _thr else 'GESPERRT'}")
print("")
_exl_e = float(np.min(lo[:N]))
_exh_e = float(np.max(hi[:N]))
print(f"   Ende: ex_lo {_exl_e:.4f}  ex_hi {_exh_e:.4f}  "
      f"Spanne {_exh_e - _exl_e:.4f}")
print(f"   LONG-Schwelle waere lo[k] <= "
      f"{_exl_e + cfg.quartil_distanz_pct / 100.0 * (_exh_e - _exl_e):.4f} USD")
print(f"   H2-Tief ist aber {float(lo[SPLIT:].min()):.4f} USD -> "
      f"Abstand zur Schwelle "
      f"{float(lo[SPLIT:].min()) - (_exl_e + cfg.quartil_distanz_pct / 100.0 * (_exh_e - _exl_e)):.4f} USD")
print("")
print("   Die 5 GELUNGENEN H1-LONGs (Vergleichsgruppe):")
for s in setups:
    if s.richtung == "LONG":
        _a = float(np.min(lo[:s.bar + 1]))
        _b = float(np.max(hi[:s.bar + 1]))
        _dd = (float(lo[s.bar]) - _a) / (_b - _a) * 100.0
        print(f"      Bar {s.bar:>6} ({np.datetime64(ts[s.bar], 'D')})  "
              f"K{s.kid:<4}  Dist {_dd:>5.1f}%  R {s.r:>+8.5f}  "
              f"close {s.trigger_close:.4f}")

# ------------------------------------------------------------ Kanten-Inventar
print("")
print("=" * 100)
print("UNTEN-KANTEN-INVENTAR (Grundlage des LONG-Pfads)")
print("=" * 100)
alle = list(scan["edges"]) + list(scan["seeds"])
_unt = [e for e in alle if e.seite == "UNTEN"]
print(f"   UNTEN-Kanten gesamt: {len(_unt)}  /  OBEN-Kanten: "
      f"{len(alle) - len(_unt)}")
print("   (Tabellenausschnitt: nur kausal-zum-Split existente UNTEN-Kanten "
      "mit Basis >= 45,00 USD)")
print(f"   {'kid':>5}{'basis':>10}{'pivot':>8}{'status':>12}"
      f"{'letzter Docht':>15}{'lebend bei Split':>18}")
_relev = []
for e in sorted(_unt, key=lambda x: -x.basis):
    if e.erster_pivot_bar + 2 > SPLIT + 1:
        continue
    if float(e.basis_bei(SPLIT)) < 45.0:
        continue
    bars = [b for b, _ in e.wicks if b <= SPLIT]
    last = max(bars) if bars else -1
    lebt = bool(bars) and last >= SPLIT - cfg.wall_live_bars
    _relev.append((e, last, lebt))
print(f"   --> {len(_relev)} relevante Kanten")
for e, last, lebt in _relev:
    print(f"   {e.kid:>5}{float(e.basis_bei(SPLIT)):>10.4f}"
          f"{e.erster_pivot_bar:>8}{str(e.status):>12}{last:>15}"
          f"{('JA' if lebt else 'nein'):>18}")

# --------------------------------------------- Minimalbedingung LONG (Analyse)
print("")
print("=" * 100)
print("MINIMALBEDINGUNG DES LONG-PFADS -- wie oft strukturell ueberhaupt moeglich?")
print("=" * 100)
print("   LONG verlangt: eine UNTEN-Kante wird vom Bar-Low DURCHSTOCHEN")
print("   (dist = (basis - lo[k])/basis > sweep_mindestdurchstich_pct).")
print(f"   sweep_mindestdurchstich_pct = {cfg.sweep_mindestdurchstich_pct}"
      f"   max_sweep_ueberdehnung_pct = {cfg.max_sweep_ueberdehnung_pct}")
_ex = [e for e in _unt if e.erster_pivot_bar + 2 <= SPLIT + 1]
print(f"   bei Split kausal existente UNTEN-Kanten: {len(_ex)}")
_h2 = [k for k in range(SPLIT, N)
       if any(lo[k] < e.basis_bei(k) for e in _ex)]
print(f"   H2-Bars mit lo[k] unter IRGENDEINER kausalen UNTEN-Basis: "
      f"{len(_h2)} / {N - SPLIT}")
_low_h2 = float(lo[SPLIT:].min())
print(f"   H2-Tief {_low_h2:.4f}  (Split-close {cl[SPLIT]:.4f})")
_unter = sorted({(e.kid, round(float(e.basis_bei(SPLIT)), 4)) for e in _ex
                 if e.basis_bei(SPLIT) > _low_h2})
print(f"   UNTEN-Basen bei Split, die im H2 NIEMALS unterschritten werden "
      f"({len(_unter)}):")
for kid, b in _unter[:40]:
    print(f"      K{kid:<4} {b:>9.4f}   (H2-Tief {_low_h2:.4f}, "
          f"Abstand {b - _low_h2:>7.4f} USD)")

_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
