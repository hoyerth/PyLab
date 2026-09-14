# -*- coding: utf-8 -*-
"""READ-ONLY: Verifikation der Mentor-Hook-Semantik (Adapter-Spezifikation).

Frage: WIE muss Regel (A) ("Wand-Docht-Exception") mechanisch angewandt
werden, damit die zwei Benchmark-Trades (K73 @ 980 / 1020) entstehen?

Kandidaten (jeweils OHNE/MIT M6-Blocker-Ausnahme):
  F1 "Freigabe im dist<0-Zweig"        : `continue` statt `return None`
  F2 "Pool-Filter"                     : erreichte Wand faellt aus dem Pool
  F3 "F1 + V-S-Erlass"                 : F1 + innere Linien ohne V-S>=3
  M6 "Blocker-Ausnahme"                : erreichte Wand ist kein M6-Blocker

Kriterium "Wand lieferte Liquiditaet":
  W = exakte Docht-Gleichheit (Bar k hat diesen Sweep-Preis als Docht)
  M = Touch-Band 0.12 % um die Wand-Basis (Mentor-Vorgabe)
Scoping: bar >= 640 (H2) vs. bar >= 848 (P9, Mentor-Vertrag)
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
P = ROOT / "test" / "tmp_kanten_engine_replay.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         mod.__dict__)
    return mod


engine = load("ke_hk", P)
cfg = engine.StraightEdgeHarnessKonfiguration()
scan0 = engine._se_scan("AUG", cfg)
n = len(scan0["d"])
box_end = scan0["box_end_bar"]
scan0["box_end_bar"] = n
ts = scan0["d"]["ts"]

PHASEN = {"P9": (848, 1020, 69.9140, 68.3700),
          "P10": (1030, 1075, 68.2200, 67.5440),
          "P11": (1082, 1134, 69.3435, 68.5250),
          "P12": (1171, 1272, 69.5550, 67.6355)}

# ---------------------------------------------------------------- Hooks
HOOK = {"kriterium": "W", "scope": 640}


def _in_scope(k: int) -> bool:
    if HOOK["scope"] == "PHASE":
        return any(bs <= k <= be for bs, be, _u, _l in PHASEN.values())
    return k >= HOOK["scope"]


def _wand_erreicht(e, k: int, sweep_px: float) -> bool:
    """Wand lieferte Liquiditaet: Sweep erreicht ihre Basis (Kriterium W/M)."""
    basis = e.basis_bei(k)
    if HOOK["kriterium"] == "W":
        return any(b == k and abs(px - sweep_px) < 1e-9 for b, px in e.wicks)
    band = basis * cfg.touch_band_pct / 100.0
    return abs(sweep_px - basis) <= band


def _phasen_ziel(k: int, richtung: str):
    if not _in_scope(k):
        return None
    for _pid, (bs, be, u, l) in PHASEN.items():
        if bs <= k <= be:
            return l if richtung == "SHORT" else u
    return None


engine._in_scope = _in_scope
engine._wand_erreicht = _wand_erreicht
engine._phasen_ziel = _phasen_ziel

# --------------------------------------------------- Quelltext-Patch (RAM)
src_datei = P.read_text(encoding="utf-8")
tree = ast.parse(src_datei)
node = next(x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "_se_trades")
src = ast.get_source_segment(src_datei, node)
assert src is not None

# --- Hook 1a: Pool-Behandlung ---------------------------------------------
H1_OLD = ('        if not pool:\n            return None\n'
          '        pool.sort(key=lambda e: e.basis_bei(k), '
          'reverse=(seite == "OBEN"))')
H1_POOL = (H1_OLD + '\n        # Hook 1a: erreichte Wand faellt aus dem Pool\n'
           '        pool = [e for e in pool\n'
           '                if not (_in_scope(k) and _wand_erreicht(e, k, sweep_px))]')
H1_FLAG = H1_OLD + '\n        _freigabe_ok = True   # F1/F3: Marker fuer dist<0\n'

H2_OLD = ('            if dist < 0.0:\n'
          '                if _lebt(e, k):\n'
          '                    return None                 '
          '# lebende Wand nicht erreicht\n')
H2_CONT = ('            if dist < 0.0:\n'
           '                if _in_scope(k) and _wand_erreicht(e, k, sweep_px):\n'
           '                    continue\n'
           '                if _lebt(e, k):\n'
           '                    return None                 '
           '# lebende Wand nicht erreicht\n')

H3_OLD = ('            if pos == 0:\n'
          '                return e                        '
          '# Q1: Wand handelt (Reclaim=Reife)\n')
H3_ERLASS = (H3_OLD +
             '            if _in_scope(k) and _freigabe_ok:\n'
             '                return e                        # F3: V-S-Erlass\n')

# --- Hook 1b: M6-Blocker-Ausnahme (beide Seiten) ---------------------------
M6_OBEN_OLD = ('            if seite == "OBEN":\n'
               '                if b <= sweep_px:\n'
               '                    continue                    '
               '# erreicht -> kein Blocker\n')
M6_OBEN_NEW = (M6_OBEN_OLD +
               '                if _in_scope(k) and _wand_erreicht(e, k, sweep_px):\n'
               '                    continue                    '
               '# Hook 1b: erreichte Wand kein Blocker\n')
M6_UNTEN_OLD = ('            else:\n'
                '                if b >= sweep_px:\n'
                '                    continue\n')
M6_UNTEN_NEW = (M6_UNTEN_OLD +
                '                if _in_scope(k) and _wand_erreicht(e, k, sweep_px):\n'
                '                    continue                    '
                '# Hook 1b: erreichte Wand kein Blocker\n')

for _name, _s in (("H1_OLD", H1_OLD), ("H2_OLD", H2_OLD), ("H3_OLD", H3_OLD),
                  ("M6_OBEN", M6_OBEN_OLD), ("M6_UNTEN", M6_UNTEN_OLD)):
    assert src.count(_s) == 1, _name

# --- Hook 2: Regel (B) -----------------------------------------------------
B_OLD = '            gegen_basis = geg.basis_bei(k)\n'
B_NEW = (B_OLD +
         '            _pz = _phasen_ziel(k, richtung)\n'
         '            if _pz is not None:\n'
         '                gegen_basis = _pz\n')
assert src.count(B_OLD) == 1


def build(pool: str, m6: bool, kriterium: str, scope: int):
    """Baut die gepatchte _se_trades fuer eine Variante und liefert sie."""
    HOOK.update(dict(kriterium=kriterium, scope=scope))
    s = src
    if pool == "FILTER":
        s = s.replace(H1_OLD, H1_POOL)
    elif pool in ("CONTINUE", "CONTINUE_ERLASS"):
        s = s.replace(H1_OLD, H1_FLAG).replace(H2_OLD, H2_CONT)
        if pool == "CONTINUE_ERLASS":
            s = s.replace(H3_OLD, H3_ERLASS)
    if m6:
        s = s.replace(M6_OBEN_OLD, M6_OBEN_NEW)
        s = s.replace(M6_UNTEN_OLD, M6_UNTEN_NEW)
    s = s.replace(B_OLD, B_NEW)
    ns = dict(engine.__dict__)
    exec(compile(s, "<hook_variante>", "exec"), ns)
    return ns["_se_trades"]


ORIG = engine._se_trades


def run(pool: str, m6: bool, kriterium: str, scope: int):
    engine._se_trades = build(pool, m6, kriterium, scope)
    try:
        ss, st = engine._se_trades(copy.deepcopy(scan0), cfg)
    finally:
        engine._se_trades = ORIG
    return ss, st


VARIANTEN = [
    ("V0 Referenz", None, False, "W", 640),
    ("V1 F1 continue", "CONTINUE", True, "W", 640),
    ("V2 F2 Pool only", "FILTER", False, "W", 640),
    ("V3 F2+M6 W 640", "FILTER", True, "W", 640),
    ("V4 F2+M6 M 640", "FILTER", True, "M", 640),
    ("V5 F2+M6 M 848", "FILTER", True, "M", 848),
    ("V6 F3+M6 M 640", "CONTINUE_ERLASS", True, "M", 640),
    ("V7 F2+M6 M Phase", "FILTER", True, "M", "PHASE"),
]

print("=" * 132)
print("A) HOOK-1-FORMULIERUNGEN: welche erzeugt die zwei Benchmark-Trades?")
print("=" * 132)
print(f"  {'Variante':17s} {'H1 n/R':>17s} {'H2 n/R':>17s} {'K73@980':>10s} "
      f"{'K73@1020':>10s} {'Summe K73':>10s} {'H1 ident.':>10s}")
ergebnis = {}
for name, pool, m6, kri, scope in VARIANTEN:
    if pool is None:
        HOOK.update(dict(kriterium=kri, scope=scope))
        engine._se_trades = ORIG
        try:
            ss, st = engine._se_trades(copy.deepcopy(scan0), cfg)
        finally:
            engine._se_trades = ORIG
    else:
        ss, st = run(pool, m6, kri, scope)
    ergebnis[name] = (ss, st)
    h1t = [t for t in ss if t.entry_bar < 640]
    h2t = [t for t in ss if t.entry_bar >= 640]
    t1 = [t for t in ss if t.kid == 73 and t.bar == 980]
    t2 = [t for t in ss if t.kid == 73 and t.bar == 1020]
    s1 = f"{t1[0].r:+.4f}" if t1 else "-"
    s2 = f"{t2[0].r:+.4f}" if t2 else "-"
    tot = (t1[0].r if t1 else 0.0) + (t2[0].r if t2 else 0.0)
    print(f"  {name:17s} {f'{len(h1t)} / {sum(t.r for t in h1t):+.4f}':>17s} "
          f"{f'{len(h2t)} / {sum(t.r for t in h2t):+.4f}':>17s} "
          f"{s1:>10s} {s2:>10s} {tot:+10.4f}")

# ------------------------------------------------ H1-Regressionsnachweis
h1_ref = {(t.kid, t.bar): t.r for t in ergebnis["V0 Referenz"][0]
          if t.entry_bar < 640}
print("\n" + "=" * 132)
print("B) H1-REGRESSION (Box: entry_bar < 640) gegen V0 = "
      f"{len(h1_ref)} Trades / {sum(h1_ref.values()):+.6f} R")
print("=" * 132)
for name, _, _, _, _ in VARIANTEN:
    ss = ergebnis[name][0]
    h1 = {(t.kid, t.bar): t.r for t in ss if t.entry_bar < 640}
    neu = sorted(set(h1) - set(h1_ref))
    weg = sorted(set(h1_ref) - set(h1))
    diff = [(k, round(h1_ref[k], 6), round(h1[k], 6))
            for k in set(h1) & set(h1_ref) if abs(h1[k] - h1_ref[k]) > 1e-9]
    ok = not neu and not weg and not diff
    print(f"  {name:17s} {'IDENTISCH' if ok else 'VERAENDERT':12s} "
          f"neu={neu or '-'} weg={weg or '-'} Rdiff={diff or '-'}")

# ------------------------------------------------ Detail der Empfehlung
print("\n" + "=" * 132)
print("C) DETAIL (V4 = Pool-Filter + M6-Ausnahme, Kriterium M=0.12 %, Scope 640)")
print("=" * 132)
ss4, st4 = ergebnis["V4 F2+M6 M 640"]
print(f"  {'sig':>4s} {'Zeit':13s} {'kid':>4s} {'stufe':16s} {'entry':>9s} "
      f"{'sl':>9s} {'tp2':>9s} {'poc':>9s} {'risk':>7s} {'R':>9s} "
      f"{'resultat':9s} {'grund1':6s}")
for t in sorted([x for x in ss4 if x.entry_bar >= 640], key=lambda x: x.bar):
    print(f"  {t.bar:4d} {ts.iloc[t.bar].strftime('%d.%m. %H:%M'):13s} "
          f"{t.kid:4d} {t.stufe:16s} {t.entry:9.4f} {t.sl:9.4f} "
          f"{t.tp2:9.4f} {t.poc:9.4f} {abs(t.sl - t.entry):7.4f} "
          f"{t.r:+9.4f} {t.resultat:9s} {t.grund1:6s}")
t73 = [t for t in ss4 if t.kid == 73 and t.bar in (980, 1020)]
print(f"\n  Summe K73 (Benchmark): {sum(t.r for t in t73):+.4f} R")
print(f"  H2 gesamt: {len([t for t in ss4 if t.entry_bar >= 640])} Trades / "
      f"{sum(t.r for t in ss4 if t.entry_bar >= 640):+.4f} R")

# ------------------------------------------------ Nebenwirkungen V0 -> V4
print("\n" + "=" * 132)
print("D) NEBENWIRKUNGEN V0 -> V4 (H2-Trades, Stats)")
print("=" * 132)
h2_0 = {(t.kid, t.bar): t for t in ergebnis["V0 Referenz"][0]
        if t.entry_bar >= 640}
h2_4 = {(t.kid, t.bar): t for t in ss4 if t.entry_bar >= 640}
print(f"  V0 H2 ({len(h2_0)}): " + ", ".join(
    f"K{t.kid}@{t.bar}({t.r:+.2f})" for t in h2_0.values()))
print(f"  V4 H2 ({len(h2_4)}): " + ", ".join(
    f"K{t.kid}@{t.bar}({t.r:+.2f})" for t in h2_4.values()))
print(f"  hinzu: {sorted(set(h2_4) - set(h2_0)) or '-'}")
print(f"  weg  : {sorted(set(h2_0) - set(h2_4)) or '-'}")
for key in sorted(set(h2_0) & set(h2_4)):
    if abs(h2_0[key].r - h2_4[key].r) > 1e-9:
        print(f"  R-Aenderung {key}: {h2_0[key].r:+.4f} -> {h2_4[key].r:+.4f} "
              f"(tp2 {h2_0[key].tp2:.4f} -> {h2_4[key].tp2:.4f})")
s0, s4 = ergebnis["V0 Referenz"][1], st4
print("\n  Stats-Diff:")
for key in sorted(set(s0) & set(s4)):
    if isinstance(s0[key], int) and s0[key] != s4[key]:
        print(f"    {key:22s} V0={s0[key]:6d} V4={s4[key]:6d} "
              f"delta={s4[key] - s0[key]:+6d}")

# ------------------------------------------------ Komposition der Scopes
print("\n" + "=" * 132)
print("E) H2-KOMPOSITION je Scope (Kriterium M): H2 = 640 (Box) | 848 (P9) | PHASE")
print("=" * 132)
for name in ("V3 F2+M6 W 640", "V4 F2+M6 M 640", "V5 F2+M6 M 848",
             "V7 F2+M6 M Phase"):
    ss = ergebnis[name][0]
    h2 = sorted([t for t in ss if t.entry_bar >= 640], key=lambda x: x.bar)
    park = [t for t in h2 if t.entry_bar <= 847]
    rest = [t for t in h2 if t.entry_bar > 847]
    print(f"  {name:19s} " + ", ".join(
        f"K{t.kid}@{t.bar}({t.r:+.2f})" for t in h2))
    print(f"  {'':19s} Park 640..847: {len(park)} / {sum(t.r for t in park):+.4f} R "
          f"| Rest >847: {len(rest)} / {sum(t.r for t in rest):+.4f} R")
