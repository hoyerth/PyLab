# -*- coding: utf-8 -*-
"""AUG26 Schritt 2 (READ-ONLY): Transitions-Filter als Trockenlauf.

Ziel: V0 auf AUG26 mit harter Blockade waehrend der drei bekannten
Transitionen (07.08. / 19.-21.08. / 28.08.) und Messung des PnL-Deltas.

Umsetzung (adaptergefuehrter Phasen-Kontext, Option B):
  * Die Zonen kommen als ``_TRANS_ZONEN`` aus dem PhasenKontext-Vertrag.
  * Konsumiert wird ueber EINEN AST-Patch (``A_TRANS_GATE``) nach der
    Q29-Sperre. ``test/tmp_kanten_engine_replay.py`` bleibt physisch
    unveraendert (SHA 53f28e1b...); V014-V019 bleiben byte-identisch,
    weil der Patch nur in diesem Skript im RAM wirkt.
  * Blockade auf SIGNAL-Ebene (nicht Ergebnis-Filter): der Bar wird gar
    nicht verarbeitet, damit Concurrency-Schranke und Entry-Dedup
    korrekt frei bleiben.

Zonen-Varianten als Null-Referenz der gemessenen Intervalle.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import Hook2ZielModus  # noqa: E402

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
spec = importlib.util.spec_from_file_location("engine_s2", ENGINE_P)
engine = importlib.util.module_from_spec(spec)
sys.modules["engine_s2"] = engine
spec.loader.exec_module(engine)  # type: ignore[union-attr]

engine.FENSTER["AUG26"] = ("2026-08-03", "2026-09-01")  # type: ignore[index]
cfg = engine.StraightEdgeHarnessKonfiguration()
scan = engine._se_scan("AUG26", cfg)  # type: ignore[arg-type]
n = scan["n"]
scan["box_end_bar"] = n
ts = list(scan["d"]["ts"])
W = cfg.tp1_anteil_pct / 100.0

TAGE = ["03.08", "04.08", "05.08", "06.08", "07.08", "10.08", "11.08",
        "12.08", "13.08", "14.08", "17.08", "18.08", "19.08", "20.08",
        "21.08", "24.08", "25.08", "26.08", "27.08", "28.08", "31.08"]


def tag(bar: int) -> str:
    i = bar // 92
    return f"{TAGE[i]}({bar - i * 92:02d})" if i < len(TAGE) else "?"


# ------------------------------------------------------------- Patch-Anker
_src = ENGINE_P.read_text(encoding="utf-8")
_ast = ast.parse(_src)
_node = next(x for x in _ast.body
             if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src_base = ast.get_source_segment(_src, _node)
assert src_base is not None

ANKER_Q29 = (
    '                continue\n'
    '            seite: KantenSeite = "OBEN" if richtung == "SHORT" '
    'else "UNTEN"\n'
    '            basis = kd.basis_bei(k)\n')
assert src_base.count(ANKER_Q29) == 1, src_base.count(ANKER_Q29)

GATE = (
    '                continue\n'
    '            # --- AUG26/S2: Transitionssperre (No Man\'s Land) ----------\n'
    '            # Zonen + Vor-Balance-Grenze kommen aus dem PhasenKontext-\n'
    '            # Vertrag; die Engine exekutiert nur. Signal-Ebene:\n'
    '            # Concurrency und Entry-Bar-Dedup bleiben frei.\n'
    '            if k < _TRANS_START:\n'
    '                stats["vorbalance_blockiert"] = (\n'
    '                    stats.get("vorbalance_blockiert", 0) + 1)\n'
    '                continue\n'
    '            if any(_ta <= k <= _tb for _ta, _tb in _TRANS_ZONEN):\n'
    '                stats["transition_blockiert"] = (\n'
    '                    stats.get("transition_blockiert", 0) + 1)\n'
    '                _TRANS_LOG.append((k, richtung, int(kd.kid)))\n'
    '                continue\n'
    '            seite: KantenSeite = "OBEN" if richtung == "SHORT" '
    'else "UNTEN"\n'
    '            basis = kd.basis_bei(k)\n')

src_trans = src_base.replace(ANKER_Q29, GATE)
assert src_trans != src_base

ns: Dict[str, object] = dict(engine.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_TRANS_ZONEN"] = ()
ns["_TRANS_START"] = 0
ns["_TRANS_LOG"] = []

print("=" * 104)
print("AUG26 SCHRITT 2: TRANSITIONS-FILTER (TROCKENLAUF, read-only)")
print("=" * 104)
print(f"Engine unveraendert: SHA "
      f"{hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()[:16]}...  "
      f"| n = {n} | box_end = {int(scan['box_end_bar'])}")
print(f"Patch: A_TRANS_GATE (Q29-Anker, 1 Ersetzung) -> "
      f"{len(src_trans) - len(src_base):+d} Zeichen")


def _lauf(zonen: Tuple[Tuple[int, int], ...],
          start: int = 0) -> Tuple[List, Dict, List]:
    ns["_TRANS_ZONEN"] = zonen
    ns["_TRANS_START"] = start
    _log: List = ns["_TRANS_LOG"]  # type: ignore[assignment]
    _log.clear()
    if not zonen and start == 0:
        S, st = engine._se_trades(copy.deepcopy(scan), cfg)
    else:
        exec(compile(src_trans, "<trans>", "exec"), ns)  # noqa: S102
        S, st = ns["_se_trades"](copy.deepcopy(scan), cfg)  # type: ignore
    return list(S), dict(st), list(_log)


def _kenn(S: List) -> Dict[str, float]:
    return {
        "n": len(S),
        "r": sum(float(t.r) for t in S),
        "treffer": sum(1 for t in S if float(t.r) > 0),
        "sl": sum(1 for t in S if float(t.r) <= -0.999),
    }


VARIANTEN: List[Tuple[str, Tuple[Tuple[int, int], ...], int]] = [
    ("Z0  Referenz (keine Sperre)", (), 0),
    ("ZA  Kern        07.08 368-476 | 19-21.08 1104-1479 | 28.08 1748-1904",
     ((368, 476), (1104, 1479), (1748, 1904)), 0),
    ("ZB  Gestreckt   07.08 368-551 | 19-21.08 1104-1479 | 28.08 1748-1904",
     ((368, 551), (1104, 1479), (1748, 1904)), 0),
    ("ZC  Kalendertage 07.-10.08 368-551 | 19.-21.08 1104-1379 | 28.08 1748-1839",
     ((368, 551), (1104, 1379), (1748, 1839)), 0),
    ("ZD  Rohschnitt   07.08 ab 385 | 19-21.08 ab 1105 | 28.08 ab 1788",
     ((385, 551), (1105, 1479), (1788, 1904)), 0),
    ("ZE  ZB + Vor-Balance-Grenze Bar 552 (11.08.)",
     ((368, 551), (1104, 1479), (1748, 1904)), 552),
]

ergeb: List[Tuple[str, List, Dict, List]] = []
for _name, _zonen, _start in VARIANTEN:
    _S, _st, _log = _lauf(_zonen, _start)
    ergeb.append((_name, _S, _st, _log))

# --------------------------------------------------------------- Anker-Check
_base = _kenn(ergeb[0][1])
assert _base["n"] == 18 and abs(_base["r"] + 7.991154) < 1e-6, _base

print("\n" + "-" * 104)
print("ERGEBNIS (Signal-Ebene blockiert; Kennzahlen nach Lauf)")
print("-" * 104)
print(f"   {'Variante':<62}{'Trades':>7}{'Treffer':>9}{'SL':>5}"
      f"{'R_brutto':>12}{'Delta':>10}")
for _name, _S, _st, _log in ergeb:
    k = _kenn(_S)
    print(f"   {_name:<62}{k['n']:>7}{k['treffer']:>9}{k['sl']:>5.0f}"
          f"{k['r']:>+12.4f}{k['r'] - _base['r']:>+10.4f}")

# ------------------------------------------------- Elimination je Variante
_base_sig = {(int(t.entry_bar), int(t.kid)): float(t.r)
             for t in ergeb[0][1]}
print("\n" + "-" * 104)
print("ELIMINIERTE TRADES je Variante (Vergleich gegen Z0)")
print("-" * 104)
for _name, _S, _st, _log in ergeb[1:]:
    _sig = {(int(t.entry_bar), int(t.kid)) for t in _S}
    _weg = [(b, k, r) for (b, k), r in sorted(_base_sig.items())
            if (b, k) not in _sig]
    _neu = [(int(t.entry_bar), int(t.kid), float(t.r)) for t in _S
            if (int(t.entry_bar), int(t.kid)) not in _base_sig]
    print(f"\n   {_name}")
    print(f"      eliminiert : {len(_weg)}   Summe "
          f"{sum(r for _, _, r in _weg):+.4f} R   [Vollverluste: "
          f"{sum(1 for _, _, r in _weg if r <= -0.999)}/{len(_weg)}]")
    for b, k, r in _weg:
        print(f"         bar {b:>5} {tag(b):<12} K{k:<4} {r:+.4f}")
    if _neu:
        print(f"      hinzugekommen: {len(_neu)}")
        for b, k, r in _neu:
            print(f"         bar {b:>5} {tag(b):<12} K{k:<4} {r:+.4f}")

# ------------------------------------------------------ Blockade-Diagnostik
print("\n" + "-" * 104)
print("BLOCKADE-DIAGNOSTIK (Signal-Bars je Variante)")
print("-" * 104)
for _name, _S, _st, _log in ergeb[1:]:
    _kinder = sorted({kid for _b, _r, kid in _log})
    print(f"   {_name.split()[0]:<4} transition_blockiert="
          f"{int(_st.get('transition_blockiert', 0)):>3}  "
          f"vorbalance_blockiert="
          f"{int(_st.get('vorbalance_blockiert', 0)):>3}  "
          f"| betroffene Kanten: "
          f"{[f'K{kid}' for kid in _kinder]}")

# ------------------------------------------------------- Rest-Ausserhalb
for _idx, _lbl in ((2, "ZB (nur Transitionen gesperrt)"),
                   (5, "ZE (Transitionen + Vor-Balance < 552)")):
    print("\n" + "-" * 104)
    print(f"REST-TRADES: {_lbl}")
    print("-" * 104)
    _S = ergeb[_idx][1]
    for t in sorted(_S, key=lambda x: int(x.entry_bar)):
        print(f"   bar {int(t.entry_bar):>5} {tag(int(t.entry_bar)):<12} "
              f"{t.richtung:<6} K{int(t.kid):<4} {float(t.r):>+10.4f}  "
              f"({t.grund1}/{t.grund2})")
    _w = [float(t.r) for t in _S]
    print(f"   SUMME {sum(_w):+.6f} R  bei {len(_S)} Trades  "
          f"(Treffer {sum(1 for r in _w if r > 0)}/{len(_S)}, "
          f"SL {sum(1 for r in _w if r <= -0.999)})")
print("\nENDE AUG26 SCHRITT 2")
