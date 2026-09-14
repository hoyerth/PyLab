# -*- coding: utf-8 -*-
"""E-34n/2 — Entscheidungs-Trace V019 (read-only).

Zweck: Beantwortung der Anwender-Punkte 4/5/6 — *welche* Bars hatten einen
gueltigen Kandidaten und *warum* wurde er verworfen ("verpasste Chancen"),
und wann genau hat der Adapter-Hook (ZP-4) selbst blockiert.

Vorgehen: identisches AST-Geruest wie _tmp_e34n1_geometrie.py (Basis-13-
Literale + ZP-4-Funktion werden aus dem Renderer geholt, NICHT importiert),
danach werden **nach** Anwendung von ZP-4 zusaetzliche ``_T.append(...)``-
Sonden in den Quelltext genaeht. Kein Schreiben in Adapter/Engine.

Ausgabe: stdout + test/_tmp_e34n2_out.txt.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, ADAPTER_V019, DEFAULT_ADAPTER, Hook2ZielModus,
)

ENG = ROOT / "test" / "tmp_kanten_engine_replay.py"
REN = ROOT / "test" / "tmp_png_aug_sichttest.py"
OUT = ROOT / "test" / "_tmp_e34n2_out.txt"
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

# ------------------------------------------------- Renderer-Regeln per AST
ren_txt = REN.read_text(encoding="utf-8")
ren_tree = ast.parse(ren_txt)
RENNS: dict = {}
for _n in ren_tree.body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id.startswith("A_"):
        exec(compile(ast.get_source_segment(ren_txt, _n), "<a_>", "exec"),  # noqa: S102
             RENNS)
    if isinstance(_n, ast.FunctionDef) \
            and _n.name == "_wende_zielzonen_patches_v019":
        exec(compile(ast.get_source_segment(ren_txt, _n), "<zp4>", "exec"),  # noqa: S102
             RENNS)
assert "_wende_zielzonen_patches_v019" in RENNS, "ZP-4-Funktion nicht gefunden"

# ---------------------------------------------------------------- Engine
src_datei = ENG.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


print("=" * 118)
print("E-34n/2  ENTSCHEIDUNGS-TRACE V019 (read-only)")
print("=" * 118)
print(f"Engine SHA {hashlib.sha256(ENG.read_bytes()).hexdigest()[:24]}...")
print(f"Renderer SHA {hashlib.sha256(REN.read_bytes()).hexdigest()[:24]}...")

eng = load("ke_e34n2", ENG)
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
d = scan["d"]
ts = d["ts"]
op = d["open"].to_numpy(dtype=float)
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)

print(f"n={n} | box_end(raw)={scan['box_end_bar']}")
scan["box_end_bar"] = n

_ORDER = ("A_KANTEN", "A_LOOP", "A_POOL", "A_DIST", "A_M6_BASIS_K",
          "A_M6_BASIS", "A_M6_RET", "A_M6_SORT", "A_M6_SORT2", "A_M6_OBEN",
          "A_M6_UNTEN", "A_TP2", "A_KBASIS")
patched = src
for _nm in _ORDER:
    _s, _new = RENNS[_nm], RENNS[_nm + "_NEW"]
    assert patched.count(_s) == 1, (_nm, patched.count(_s))
    patched = patched.replace(_s, _new)
patched = RENNS["_wende_zielzonen_patches_v019"](patched)


def rep(s: str, old: str, new: str, n_erwartet: int = 1) -> str:
    _c = s.count(old)
    assert _c == n_erwartet, (old[:60], _c, n_erwartet)
    return s.replace(old, new)


# ---------------- Sonden einaehen (NACH ZP-4!) ----------------------------
# (1) Kandidat ueberhaupt vorhanden?
patched = rep(
    patched,
    '            # --- M6: Innenlevel-Blocker',
    '            _T.append((k, richtung, "KANDIDAT", int(kd.kid)))\n'
    '            # --- M6: Innenlevel-Blocker')
# (2) Die Zaehler-Sperren (eindeutige Strings)
patched = rep(patched, 'stats["blocker"] += 1',
              'stats["blocker"] += 1; _T.append((k, richtung, "BLOCKER", '
              'int(kd.kid)))')
patched = rep(patched, 'stats["quartil_blockiert"] += 1',
              'stats["quartil_blockiert"] += 1; _T.append((k, richtung, '
              '"QUARTIL", int(kd.kid)))')
patched = rep(patched, 'stats["f3"] += 1',
              'stats["f3"] += 1; _T.append((k, richtung, "F3", int(kd.kid)))')
patched = rep(patched, 'stats["zyklus_blockiert"] += 1',
              'stats["zyklus_blockiert"] += 1; _T.append((k, richtung, '
              '"ZYKLUS", int(kd.kid)))')
patched = rep(patched, 'stats["kein_gegner"] += 1',
              'stats["kein_gegner"] += 1; _T.append((k, richtung, '
              '"KEIN_GEGNER", int(kd.kid)))')
patched = rep(patched, 'stats["frisch_blockiert"] += 1',
              'stats["frisch_blockiert"] += 1; _T.append((k, richtung, '
              '"FRISCH_JUNG", int(e.kid)))')
# (3) Die 9 kein_raum-Stellen positionell etikettieren.
#     Reihenfolge im ZP-4-gepatchten Quelltext:
#     1 = Adapter-Hook BLOCKIERT (von A_TP2_NEW eingewebt)
_RAUM = 'stats["kein_raum"] += 1'
_RAUM_TAGS = ("H2_BLOCKIERT", "RAUM_SHORT_UNTER", "RAUM_SHORT_MINDIST",
              "RAUM_LONG_UEBER", "RAUM_LONG_MINDIST", "RAUM_POC",
              "RAUM_SHORT_ORDNUNG", "RAUM_LONG_ORDNUNG", "RAUM_RISK")
_parts = patched.split(_RAUM)
assert len(_parts) == len(_RAUM_TAGS) + 1, (len(_parts), len(_RAUM_TAGS) + 1)
patched = _parts[0]
for _tag, _rest in zip(_RAUM_TAGS, _parts[1:]):
    patched += (f'_T.append((k, richtung, "{_tag}", int(kd.kid))); '
                f'{_RAUM}' + _rest)
assert patched.count(_RAUM) == len(_RAUM_TAGS)
# (4) Dedup / Trade / G4
patched = rep(
    patched,
    '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
    '                continue',
    '            if entry_bar in getradete_entry_bars:   # B23-3: Dedup\n'
    '                _T.append((k, richtung, "DEDUP_ENTRY", int(kd.kid)))\n'
    '                continue')
patched = rep(
    patched,
    '            getradete_entry_bars.add(entry_bar)',
    '            _T.append((k, richtung, "TRADE", int(kd.kid)))\n'
    '            getradete_entry_bars.add(entry_bar)')
patched = rep(
    patched,
    '                getradete_entry_bars.add(_eb_g4)',
    '                _T.append((_k_g4, "LONG", "TRADE_G4", '
    'int(_spec_g4.boden_kid)))\n'
    '                getradete_entry_bars.add(_eb_g4)')
# (5) _kandidat-interne Ausgaenge (sonst stumm)
patched = rep(
    patched,
    '        if not pool:\n            return None\n        pool.sort(',
    '        if not pool:\n'
    '            _T.append((k, richtung, "POOL_LEER", -1))\n'
    '            return None\n        pool.sort(')
patched = rep(
    patched,
    '                    return None                 '
    '# lebende Wand nicht erreicht',
    '                    _T.append((k, richtung, "WAND_UNERREICHT", '
    'int(e.kid)))\n'
    '                    return None                 '
    '# lebende Wand nicht erreicht')
patched = rep(
    patched,
    '                return None                     '
    '# Ueberdehnung, kein Reclaim',
    '                _T.append((k, richtung, "UEBERDEHNUNG", int(e.kid)))\n'
    '                return None                     '
    '# Ueberdehnung, kein Reclaim')
patched = rep(
    patched,
    '            return e\n        return None',
    '            _T.append((k, richtung, "INNEN_STUMM", int(e.kid)))\n'
    '            return e\n        return None')
patched = rep(
    patched,
    '            if stufe_n == 0:\n                continue',
    '            if stufe_n == 0:\n'
    '                _T.append((k, richtung, "STUFE0_KEIN_RECLAIM", '
    'int(kd.kid)))\n'
    '                continue')
print("Alle 17 Sonden eingenaeht (fail-loud geprueft).")

SEG = ADAPTER_V019.segmente
AUTO_A, AUTO_B = SEG[1].start_bar, SEG[-1].end_bar
P9A, P9B = SEG[0].start_bar, SEG[0].end_bar
print(f"V019-Segmente: P9 {P9A}..{P9B} | AUTO {AUTO_A}..{AUTO_B} "
      f"| n_seg={len(SEG)}")
_HOOK = [DEFAULT_ADAPTER]


def _zv(kk: int) -> bool:
    return (len(_HOOK[0].segmente) > 1
            and AUTO_A <= kk <= AUTO_B and not (P9A <= kk <= P9B))


def _ueb(kk: int) -> float:
    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct


_RS = eng._reclaim_stufe


def _rs_lok(seite, kk, basis, h, l, c, cc):
    if _zv(kk):
        cc = dataclasses.replace(cc, max_sweep_ueberdehnung_pct=0.80)
    return _RS(seite, kk, basis, h, l, c, cc)


ORIG = eng._se_trades
ns = dict(eng.__dict__)
ns["_Hook2ZielModus"] = Hook2ZielModus
ns["_zv"] = _zv
ns["_ueb"] = _ueb
ns["_reclaim_stufe"] = _rs_lok


def _lauf(hook):
    ns["_T"] = []
    ns["_hook"] = hook
    _HOOK[0] = hook
    exec(compile(patched, "<se_e34n2>", "exec"), ns)
    eng._se_trades = ns["_se_trades"]
    try:
        res = eng._se_trades(copy.deepcopy(scan), cfg)
    finally:
        eng._se_trades = ORIG
    return res, ns["_T"]


(V19, st), T19 = _lauf(ADAPTER_V019)
(V18, st18), T18 = _lauf(ADAPTER_V015)
print(f"V19: {len(V19)} Trades / {sum(t.r for t in V19):+.6f} R  "
      f"| Trace-Eintraege {len(T19)}")
print(f"V18: {len(V18)} Trades / {sum(t.r for t in V18):+.6f} R  "
      f"| Trace-Eintraege {len(T18)}")

WIN_A, WIN_B = 1000, n - 1


def _zeit(k: int) -> str:
    return ts.iloc[k].strftime("%d.%m. %H:%M")


print("\n" + "=" * 118)
print(f"1) TRACE im Zielzonen-Fenster  bar {WIN_A}..{WIN_B}  (V019)")
print("=" * 118)
print(f"{'bar':>5} {'BKZ':>12} {'rich':>5}  {'Ereignis':<16} kid")
for (k, richtung, ev, kid) in sorted(T19, key=lambda x: (x[0], x[1])):
    if WIN_A <= k <= WIN_B:
        kk = "-" if kid is None or kid < 0 else str(kid)
        print(f"{k:>5} {_zeit(k):>12} {richtung:>5}  {ev:<16} {kk}")

print("\n" + "=" * 118)
print("2) EREIGNIS-BILANZ je Bar/Direction im Fenster (Kandidat -> Ausgang)")
print("=" * 118)
_zell: dict = {}
for (k, richtung, ev, kid) in T19:
    if WIN_A <= k <= WIN_B:
        _zell.setdefault((k, richtung), []).append((ev, kid))
for (k, richtung) in sorted(_zell):
    _seq = " -> ".join(f"{e}({kk if kk and kk > 0 else '-'})"
                       for e, kk in _zell[(k, richtung)])
    _o = f"O{op[k]:.3f} H{hi[k]:.3f} L{lo[k]:.3f} C{cl[k]:.3f}"
    print(f"{k:>5} {_zeit(k):>12} {richtung:>5}  {_o}  {_seq}")

print("\n" + "=" * 118)
print("3) SPERR-LISTEN (Adapter/Engine) im Fenster")
print("=" * 118)
for _name in ("blocker_liste", "quartil_liste", "zyklus_liste"):
    _l = [z for z in st.get(_name, []) if int(z.split()[1]) >= WIN_A]
    print(f"\n  [{_name}]  n(gesamt)={len(st.get(_name, []))}  "
          f"n(Fenster)={len(_l)}")
    for _z in _l:
        print("    " + _z)

print("\n" + "=" * 118)
print("4) ANWENDER-ZEITEN  +-4 Bars  (Trace + Gates + K82)")
print("=" * 118)
_k82 = next((e for e in list(scan["edges"]) + list(scan["seeds"])
             if int(e.kid) == 82), None)
_tskey = {ts.iloc[i].strftime("%d.%m. %H:%M"): i for i in range(n)}
ZIELE = (("25.08. 04:45", "Lower3 Touch 1"),
         ("25.08. 11:00", "Lower3 Touch 2"),
         ("25.08. 15:00", "Lower3 Touch 3 (67.488)"),
         ("26.08. 17:00", "Lower3 Touch 4 (auf Kante)"),
         ("27.08. 15:45", "Lower3 Touch 5 (67.6)"),
         ("27.08. 17:45", "Frontrunner"))
for _txt, _lbl in ZIELE:
    _b = _tskey.get(_txt)
    print(f"\n  {_txt} BKZ  ->  {_lbl}   bar={_b}")
    if _b is None:
        print("    KEIN Bar mit diesem Zeitstempel")
        continue
    for _k in range(_b - 4, _b + 5):
        if not 0 <= _k < n:
            continue
        _mk = " <<<" if _k == _b else "    "
        _o = f"O{op[_k]:.4f} H{hi[_k]:.4f} L{lo[_k]:.4f} C{cl[_k]:.4f}"
        _k82s = ""
        if _k82 is not None:
            _k82s = (f" | K82 bei={_k82.basis_bei(_k):.4f} "
                     f"tc={_k82.touch_conf(_k)} "
                     f"akt={_k82.ist_aktiv_bei(_k)}")
        _ev = [f"{e}/{r}({kk})" for (kk2, r, e, kk) in T19 if kk2 == _k]
        print(f"    {_k:>5} {_zeit(_k):>12} {_o}{_k82s}{_mk}  "
              f"{' '.join(_ev) if _ev else ''}")

print("\n" + "=" * 118)
print("5) ZAEHLER, die WAEHREND des Laufs entstanden sind")
print("=" * 118)
from collections import Counter  # noqa: E402
_c19 = Counter(e for (k, r, e, kid) in T19 if WIN_A <= k <= n - 1)
_c18 = Counter(e for (k, r, e, kid) in T18 if WIN_A <= k <= n - 1)
for _e in sorted(set(_c19) | set(_c18)):
    print(f"  {_e:<16} V19={_c19.get(_e, 0):>4}   V18={_c18.get(_e, 0):>4}")

print("\nENDE E-34n/2")
_FH.close()
sys.stdout = sys.__stdout__
print("geschrieben: " + str(OUT))
